from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Avg
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.template.defaulttags import register
import json
import time

from django import template

import pyodbc

from .analyser import AnalyseurTables
from .models import AnalyseBase, AnalyseTable, LLMResponseLog
from .ollama_client import OllamaError, chat_with_model
from servers.models import Server

register = template.Library()

@register.filter
def filter_by_serveur_base(analyses_bases, serveur_id_base):
    """Filtre les analyses par serveur et base"""
    serveur_id, base_nom = serveur_id_base.split('|')
    return analyses_bases.filter(
        serveur_id=int(serveur_id),
        base_donnees=base_nom
    ).first()


def _build_analyses_summary(max_bases: int = 50) -> list[dict]:
    """Construit un résumé compact des analyses de bases pour le prompt LLM.

    On ne garde que la dernière analyse par couple (serveur, base) et on limite
    le nombre total de bases pour ne pas saturer le contexte du modèle.
    """

    latest_by_key: dict[tuple[int, str], AnalyseBase] = {}
    for analyse in AnalyseBase.objects.select_related("serveur").order_by(
        "serveur_id", "base_donnees", "-date_analyse"
    ):
        key = (analyse.serveur_id, analyse.base_donnees)
        if key not in latest_by_key:
            latest_by_key[key] = analyse

    # On convertit en dictionnaires simples et on trie par score décroissant
    summary: list[dict] = []
    for (serveur_id, base), analyse in latest_by_key.items():
        summary.append(
            {
                "serveur_id": serveur_id,
                "serveur_nom": analyse.serveur.name,
                "base": analyse.base_donnees,
                "score": analyse.score,
                "nb_tables": analyse.nb_tables,
                "tables_sans_pk": analyse.tables_sans_pk,
                "tables_sans_index": analyse.tables_sans_index,
                "tables_jamais_utilisees": analyse.tables_jamais_utilisees,
                "nb_procedures": analyse.nb_procedures,
                "nb_vues": analyse.nb_vues,
                "nb_fk_total": analyse.nb_fk_total,
                "date_analyse": analyse.date_analyse.isoformat(),
            }
        )

    summary.sort(key=lambda x: x.get("score", 0), reverse=True)
    return summary[:max_bases]

@login_required
def dashboard(request):
    """Tableau de bord avec résumé des bases et détails des tables"""
    
    # Récupérer TOUS les serveurs
    serveurs = Server.objects.all()  # ← AJOUTE CETTE LIGNE
    
    # Récupérer toutes les analyses de bases (résumé)
    analyses_bases = AnalyseBase.objects.all().order_by('-date_analyse')
    
    # Récupérer toutes les tables analysées
    tables = AnalyseTable.objects.all().order_by('-date_analyse')
    
    # Organiser les tables par base
    tables_par_base = {}
    for table in tables:
        if table.base_donnees not in tables_par_base:
            tables_par_base[table.base_donnees] = []
        tables_par_base[table.base_donnees].append(table)
    
    # Calculer les statistiques pour les cartes
    total_tables = tables.count()
    top_base = (
        AnalyseBase.objects.select_related('serveur')
        .order_by(
            '-score',
            'tables_sans_pk',
            'tables_sans_index',
            '-nb_fk_total',
            '-date_analyse',
        )
        .first()
    )
    avg_score = analyses_bases.aggregate(avg=Avg('score'))['avg'] or 0
    
    # Filtre personnalisé
    from django.template.defaulttags import register
    @register.filter
    def get_item(dictionary, key):
        return dictionary.get(key)
    
    return render(request, 'engine/dashboard.html', {
        'serveurs': serveurs,  # ← AJOUTE ICI
        'analyses_bases': analyses_bases,
        'tables_par_base': tables_par_base,
        'total_tables': total_tables,
        'top_base': top_base,
        'avg_score': avg_score,
        'active_menu': 'dashboard'
    })
@login_required
def lancer_analyse(request):
    if request.method == 'POST':
        serveur_id = request.POST.get('serveur')
        
        # Récupérer les bases sélectionnées
        bases_list = request.POST.getlist('bases')
        
        if not bases_list:
            messages.error(request, "❌ Veuillez sélectionner au moins une base")
            return redirect('engine:lancer_analyse')
        
        try:
            serveur = Server.objects.get(id=serveur_id)
            bases_analysees = []
            
            for base_donnees in bases_list:
                # Lancer l'analyseur
                analyseur = AnalyseurTables(serveur, base_donnees)
                analyseur.connecter()
                tables_data = analyseur.analyser_toutes_tables()
                analyseur.fermer()
                
                # Sauvegarder les résultats des tables
                tables_sans_pk = 0
                tables_sans_index = 0
                tables_jamais_utilisees = 0
                total_fk = 0
                total_procedures = 0
                total_vues = 0
                
                for data in tables_data:
                    # Création de l'analyse table
                    AnalyseTable.objects.create(
                        serveur=serveur,
                        base_donnees=base_donnees,
                        **data
                    )
                    if not data['a_pk']:
                        tables_sans_pk += 1
                    if not data['a_index']:
                        tables_sans_index += 1
                    if data['jamais_utilisee']:
                        tables_jamais_utilisees += 1
                    total_fk += data['nb_fk']
                    total_procedures += data['nb_procedures']
                    total_vues += data['nb_vues']
                
                # NOUVEAU CALCUL DU SCORE (moyenne des scores par table)
                table_scores = []
                for data in tables_data:
                    table_score = 100

                    # Pénalités par table
                    if not data['a_pk']:
                        table_score -= 5
                    if not data['a_index']:
                        table_score -= 3
                    if data['jamais_utilisee']:
                        table_score -= 2

                    # Bonus
                    table_score += min(data['nb_fk'] * 2, 5)
                    table_score += min(data['nb_check'] * 2, 3)
                    table_score += min(data['nb_procedures'], 3)
                    table_score += min(data['nb_vues'], 2)

                    # Pénalités sur les données
                    if data['nb_lignes'] > 0:
                        # Doublons
                        if data['nb_doublons'] > 0:
                            ratio_doublons = data['nb_doublons'] / data['nb_lignes']
                            if ratio_doublons > 0.1:
                                table_score -= 3
                            elif ratio_doublons > 0.05:
                                table_score -= 2
                            elif ratio_doublons > 0.01:
                                table_score -= 1

                        # Colonnes NULLables
                        if data['nb_colonnes'] > 0:
                            ratio_null = data['nb_nullables'] / data['nb_colonnes']
                            if ratio_null > 0.5:
                                table_score -= 2
                            elif ratio_null > 0.3:
                                table_score -= 1

                    table_scores.append(max(0, min(100, round(table_score, 2))))

                score = round(sum(table_scores) / len(table_scores), 2) if table_scores else 0
                
                # CRÉATION DE L'ANALYSE BASE
                AnalyseBase.objects.create(
                    serveur=serveur,
                    base_donnees=base_donnees,
                    nb_tables=len(tables_data),
                    tables_sans_pk=tables_sans_pk,
                    tables_sans_index=tables_sans_index,
                    tables_jamais_utilisees=tables_jamais_utilisees,
                    nb_procedures=total_procedures,
                    nb_vues=total_vues,
                    nb_fk_total=total_fk,
                    score=score
                )
                
                bases_analysees.append(base_donnees)
                print(f"✅ Base {base_donnees} sauvegardée avec score {score}")
            
            messages.success(request, f"✅ Analyse terminée - {len(bases_analysees)} base(s) analysée(s): {', '.join(bases_analysees)}")
            return redirect('engine:dashboard')
            
        except Exception as e:
            messages.error(request, f"❌ Erreur: {str(e)}")
            return redirect('engine:lancer_analyse')
    
    serveurs = Server.objects.filter(is_active=True)
    return render(request, 'engine/lancer.html', {
        'serveurs': serveurs,
        'active_menu': 'moteur'
    })
    

@login_required
def detail_base(request, base_nom):
    """Détail d'une base avec toutes ses tables"""
    analyses = AnalyseTable.objects.filter(
        base_donnees=base_nom
    ).order_by('-date_analyse', 'table_name')[:100]
    
    # Dernière analyse de la base
    derniere_base = AnalyseBase.objects.filter(
        base_donnees=base_nom
    ).first()
    
    context = {
        'base_nom': base_nom,
        'analyses': analyses,
        'derniere_base': derniere_base,
        'active_menu': 'dashboard'
    }
    return render(request, 'engine/detail_base.html', context)

@login_required
def get_databases_ajax(request):
    """Récupère les bases de données d'un serveur"""
    serveur_id = request.GET.get('serveur_id')
    
    try:
        serveur = Server.objects.get(id=serveur_id)
        bases_associees = serveur.get_databases_list()
        return JsonResponse({'success': True, 'databases': bases_associees})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def chatbot_api(request):
    """API pour le chatbot"""
    if request.method != "POST":
        return JsonResponse({"response": "Méthode non autorisée", "success": False}, status=405)

    try:
        data = json.loads(request.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return JsonResponse({"success": False, "error": "JSON invalide"}, status=400)

    question: str = (data.get("question") or "").strip()
    if not question:
        return JsonResponse({"success": False, "error": "La question est vide"}, status=400)
    question_lower = question.lower()

    # Détermination du mode : "chat général" ou "analyse des bases".
    question_words = [
        "quelle",
        "quelles",
        "quel ",
        "quels",
        "pourquoi",
        "comment",
        "combien",
        "quand",
        "est-ce",
        "peux-tu",
        "peux tu",
        "donne",
        "explique",
    ]
    db_words = [
        "base",
        "bases",
        "table",
        "tables",
        "serveur",
        "serveurs",
        "qualité",
        "qualite",
        "score",
        "fk",
        "index",
        "pk",
        "doublon",
        "doublons",
        "contrainte",
        "contraintes",
        "null",
        "donnée",
        "donnees",
        "données",
    ]

    has_question_word = ("?" in question_lower) or any(w in question_lower for w in question_words)
    has_db_word = any(w in question_lower for w in db_words)

    analysis_mode = has_question_word and has_db_word

    # Mode conversationnel simple : salutation, présentation, questions générales.
    if not analysis_mode:
        if any(word in question_lower for word in ["bonjour", "salut", "hello", "bonsoir", "coucou"]):
            chat_answer = (
                "Bonjour ! Je suis l'assistant de votre plateforme de gouvernance des données. "
                "Je peux vous aider à analyser vos serveurs, bases et tables, ou répondre à vos "
                "questions sur la qualité des données. Par quoi voulez-vous commencer ?"
            )
        elif (
            "poser des questions" in question_lower
            or "aide" in question_lower
            or "question" in question_lower
            or "questions" in question_lower
        ):
            chat_answer = (
                "Je suis là pour vous aider sur vos bases de données. "
                "Par exemple, vous pouvez me demander : 'Quelle est la meilleure base sur le "
                "serveur test 1 et pourquoi ?' ou 'Quelles sont les faiblesses de la base Test3 ?'"
            )
        else:
            chat_answer = (
                "Je suis votre chatbot Data Quality. Posez-moi des questions sur vos serveurs, "
                "bases ou tables (meilleure base, points faibles, recommandations, etc.) et je "
                "vous répondrai en me basant sur les analyses existantes."
            )

        return JsonResponse(
            {
                "success": True,
                "results": [
                    {
                        "model": "assistant",
                        "answer": chat_answer,
                        "latency_ms": 0,
                        "error": None,
                    }
                ],
            }
        )

    # À partir d'ici : mode "analyse" utilisant les LLM et les métriques.

    # Modèle déployé (fixe) pour le chatbot.
    requested_models = ["qwen2.5:7b"]

    # Construction du contexte à partir des dernières analyses de bases
    analyses_summary = _build_analyses_summary(max_bases=30)
    analyses_json = json.dumps(analyses_summary, ensure_ascii=False)

    system_prompt = (
        "Tu es un expert en gouvernance des données et en qualité des données "
        "sur des bases SQL Server. Tu réponds toujours en français, de façon "
        "claire et synthétique (quelques phrases et éventuellement une courte "
        "liste à puces). Concentre-toi uniquement sur la question posée et sur "
        "les métriques fournies. Ne mentionne jamais l'IA, le modèle, le prompt "
        "ou l'encadrant. Ne produis pas de titres comme 'Réponse à l'Encadrant'."
    )

    user_content = (
        "Voici un résumé des dernières analyses de bases de données sous "
        "forme de JSON. Chaque entrée correspond à une base analysée :\n\n"
        f"{analyses_json}\n\n"
        "Question de l'utilisateur :\n"
        f"{question}\n\n"
        "Réponds en t'appuyant sur ces métriques (score, nombre de tables, "
        "tables sans PK/index, tables jamais utilisées, procédures, vues, FK). "
        "Explique brièvement ton raisonnement puis donne une réponse "
        "synthétique et professionnelle."
    )

    results: list[dict] = []

    # Ici, on ne fixe plus de limite stricte sur le nombre de tokens générés
    # (max_tokens). Les modèles peuvent donc produire des réponses complètes,
    # au prix d'un temps de réponse plus long.

    for model_name in requested_models:
        start = time.perf_counter()
        try:
            answer, _ = chat_with_model(
                model_name,
                system_prompt,
                user_content,
                temperature=0.2,
            )
            duration_ms = (time.perf_counter() - start) * 1000

            LLMResponseLog.objects.create(
                model_name=model_name,
                question=question,
                answer=answer,
                latency_ms=duration_ms,
            )

            results.append(
                {
                    "model": model_name,
                    "answer": answer,
                    "latency_ms": round(duration_ms, 2),
                    "error": None,
                }
            )
        except OllamaError as exc:
            results.append(
                {
                    "model": model_name,
                    "answer": "",
                    "latency_ms": None,
                    "error": str(exc),
                }
            )
        except Exception as exc:  # garde-fou générique
            results.append(
                {
                    "model": model_name,
                    "answer": "",
                    "latency_ms": None,
                    "error": f"Erreur inattendue: {exc}",
                }
            )

    return JsonResponse({"success": True, "results": results})
