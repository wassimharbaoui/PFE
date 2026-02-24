from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
import pyodbc
import json
from .models import AnalyseResultat
from servers.models import Server

@login_required
def dashboard(request):
    analyses = AnalyseResultat.objects.all().order_by('-date_analyse')[:20]
    derniere = analyses.first()
    
    # Calculer le total des tables analysées
    total_tables = 0
    somme_scores = 0
    for a in analyses:
        total_tables += a.nombre_tables
        somme_scores += a.score_qualite
    
    # Calculer la moyenne des scores
    if analyses:
        moyenne = round(somme_scores / len(analyses), 1)
    else:
        moyenne = 0
    
    return render(request, 'engine/dashboard.html', {
        'analyses': analyses,
        'dernier_score': derniere.score_qualite if derniere else 100,
        'total_tables': total_tables,
        'moyenne': moyenne,
        'active_menu': 'dashboard'
    })

@login_required
def lancer_analyse(request):
    if request.method == 'POST':
        serveur_id = request.POST.get('serveur')
        base_donnees = request.POST.get('base_donnees')
        
        try:
            serveur = Server.objects.get(id=serveur_id)
            
            conn_str = (
                f"DRIVER={{ODBC Driver 17 for SQL Server}};"
                f"SERVER={serveur.ip_address},{serveur.port};"
                f"DATABASE={base_donnees};"
                f"UID={serveur.username};"
                f"PWD={serveur.password};"
                f"TrustServerCertificate=yes;"
            )
            
            conn = pyodbc.connect(conn_str, timeout=30)
            cursor = conn.cursor()
            
            # Récupérer toutes les tables
            cursor.execute("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE = 'BASE TABLE'")
            tables = [row[0] for row in cursor.fetchall()]
            
            total_lignes = 0
            total_null = 0
            total_doublons = 0
            total_anomalies = 0
            
            for table in tables:
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    lignes = cursor.fetchone()[0]
                    total_lignes += lignes
                    
                    if lignes > 0:
                        cursor.execute(f"SELECT TOP 0 * FROM {table}")
                        colonnes = [col[0] for col in cursor.description]
                        
                        for col in colonnes:
                            cursor.execute(f"SELECT COUNT(*) FROM {table} WHERE {col} IS NULL")
                            total_null += cursor.fetchone()[0]
                        
                        if len(colonnes) > 0:
                            cols_str = ','.join(colonnes)
                            cursor.execute(f"SELECT COUNT(*) - COUNT(DISTINCT CONCAT({cols_str})) FROM {table}")
                            total_doublons += cursor.fetchone()[0] or 0
                        
                        cursor.execute(f"""
                            SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS 
                            WHERE TABLE_NAME = '{table}' 
                            AND DATA_TYPE IN ('int', 'decimal', 'float', 'money')
                        """)
                        for col in [r[0] for r in cursor.fetchall()]:
                            cursor.execute(f"SELECT COUNT(*) FROM {table} WHERE {col} < 0")
                            total_anomalies += cursor.fetchone()[0] or 0
                            
                except Exception as e:
                    print(f"Erreur sur table {table}: {e}")
                    continue
            
            conn.close()
            
            if total_lignes > 0:
                max_erreurs = total_lignes * 3
                total_erreurs = total_null + total_doublons + total_anomalies
                score = 100 - (min(total_erreurs, max_erreurs) / max_erreurs * 100)
                score = round(max(0, min(100, score)), 2)
            else:
                score = 100
            
            AnalyseResultat.objects.create(
                serveur=serveur,
                base_donnees=base_donnees,
                nombre_tables=len(tables),
                total_lignes=total_lignes,
                total_null=total_null,
                total_doublons=total_doublons,
                total_anomalies=total_anomalies,
                score_qualite=score
            )
            
            messages.success(request, f"✅ Analyse terminée - Score: {score}%")
            
        except Exception as e:
            messages.error(request, f"❌ Erreur: {str(e)}")
        
        return redirect('engine:dashboard')
    
    serveurs = Server.objects.filter(is_active=True)
    return render(request, 'engine/lancer.html', {
        'serveurs': serveurs,
        'active_menu': 'moteur'
    })

@login_required
def get_databases_ajax(request):
    """Récupère les bases de données d'un serveur (celles associées au serveur)"""
    serveur_id = request.GET.get('serveur_id')
    
    try:
        serveur = Server.objects.get(id=serveur_id)
        
        # Récupérer les bases associées au serveur
        bases_associees = serveur.get_databases_list()
        
        return JsonResponse({'success': True, 'databases': bases_associees})
        
    except Exception as e:
       
     return JsonResponse({'success': False, 'error': str(e)})
    
@login_required
def chatbot_api(request):
    """API simple pour le chatbot"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            question = data.get('question', '').lower()
            
            # Réponses basées sur des mots-clés
            if 'null' in question or 'valeur vide' in question or 'manquant' in question:
                response = "🔍 Les valeurs NULL sont des données manquantes. Dans votre dashboard, la colonne 'NULL' montre combien de valeurs vides ont été trouvées."
            
            elif 'score' in question or 'note' in question:
                response = "📊 Le score est calculé ainsi : 100 - (nombre d'erreurs / (lignes × 3) × 100). Plus le score est proche de 100%, meilleure est la qualité de vos données."
            
            elif 'doublon' in question or 'double' in question or 'unique' in question:
                response = "🔄 Les doublons sont des lignes identiques. Ils sont détectés en comparant toutes les colonnes. Moins il y a de doublons, mieux c'est !"
            
            elif 'anomalie' in question or 'negatif' in question or 'négatif' in question:
                response = "⚠️ Les anomalies sont des valeurs négatives dans les colonnes numériques (âge, prix, quantité, etc.). Cela peut indiquer des erreurs de saisie."
            
            elif 'table' in question or 'combien de table' in question:
                response = "📁 Le nombre de tables analysées est affiché dans votre dashboard. Chaque table est analysée automatiquement."
            
            elif 'base' in question or 'database' in question:
                response = "💾 Vous pouvez analyser différentes bases de données. Sélectionnez un serveur, puis une base dans le menu 'Moteur'."
            
            elif 'bonjour' in question or 'salut' in question or 'hello' in question:
                response = "👋 Bonjour ! Je suis votre assistant Data Quality. Posez-moi des questions sur les scores, les NULL, les doublons ou les anomalies."
            
            elif 'merci' in question:
                response = "😊 Avec plaisir ! N'hésitez pas si vous avez d'autres questions."
            
            else:
                response = "🤔 Je n'ai pas compris votre question. Essayez de demander : 'Comment est calculé le score ?', 'C'est quoi les valeurs NULL ?', 'Que sont les anomalies ?'"
            
            return JsonResponse({'response': response, 'success': True})
            
        except Exception as e:
            return JsonResponse({'response': f"Erreur: {str(e)}", 'success': False})
    
    return JsonResponse({'response': 'Méthode non autorisée', 'success': False})
