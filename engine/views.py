from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.template.defaulttags import register
import pyodbc
import json
from .models import AnalyseTable, AnalyseBase
from .analyser import AnalyseurTables
from servers.models import Server

from django import template
register = template.Library()

@register.filter
def filter_by_serveur_base(analyses_bases, serveur_id_base):
    """Filtre les analyses par serveur et base"""
    serveur_id, base_nom = serveur_id_base.split('|')
    return analyses_bases.filter(
        serveur_id=int(serveur_id),
        base_donnees=base_nom
    ).first()

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
    total_problemes = 0
    for ab in analyses_bases:
        total_problemes += ab.tables_sans_pk + ab.tables_sans_index + ab.tables_jamais_utilisees
    
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
        'total_problemes': total_problemes,
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
                
                # NOUVEAU CALCUL DU SCORE
                score = 100
                for data in tables_data:
                    # Pénalités par table
                    if not data['a_pk']:
                        score -= 5
                    if not data['a_index']:
                        score -= 3
                    if data['jamais_utilisee']:
                        score -= 2
                    
                    # Bonus
                    score += min(data['nb_fk'] * 2, 5)
                    score += min(data['nb_check'] * 2, 3)
                    score += min(data['nb_procedures'], 3)
                    score += min(data['nb_vues'], 2)
                    
                    # Pénalités sur les données
                    if data['nb_lignes'] > 0:
                        # Doublons
                        ratio_doublons = data['nb_doublons'] / data['nb_lignes']
                        if ratio_doublons > 0.1:
                            score -= 3
                        elif ratio_doublons > 0.05:
                            score -= 2
                        elif ratio_doublons > 0.01:
                            score -= 1
                        
                        # Colonnes NULLables
                        if data['nb_colonnes'] > 0:
                            ratio_null = data['nb_nullables'] / data['nb_colonnes']
                            if ratio_null > 0.5:
                                score -= 2
                            elif ratio_null > 0.3:
                                score -= 1

                score = max(0, min(100, round(score, 2)))
                
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
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            question = data.get('question', '').lower()
            
            if 'null' in question:
                response = "🔍 Les valeurs NULL sont des données manquantes."
            elif 'table' in question:
                response = "📁 Chaque table est analysée (PK, index, taille, etc.)"
            elif 'base' in question:
                response = "💾 Vous pouvez analyser différentes bases"
            elif 'bonjour' in question:
                response = "👋 Bonjour ! Je suis votre assistant"
            elif 'merci' in question:
                response = "😊 Avec plaisir !"
            else:
                response = "🤔 Posez-moi des questions sur les tables, bases, NULL..."
            
            return JsonResponse({'response': response, 'success': True})
        except Exception as e:
            return JsonResponse({'response': f"Erreur: {str(e)}", 'success': False})
    return JsonResponse({'response': 'Méthode non autorisée', 'success': False})