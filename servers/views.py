from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from .models import Server
from .forms import ServerForm
from engine.models import AnalyseResultat  # ← IMPORTANT: Ajoute cette ligne
import pyodbc

@login_required
def server_list(request):
    servers = Server.objects.all()
    
    # Calculer le nombre total de bases surveillées
    total_bases = 0
    for server in servers:
        total_bases += len(server.get_databases_list())
    
    # Calculer le nombre total d'analyses effectuées
    total_analyses = AnalyseResultat.objects.count()
    
    return render(request, 'servers/server_list.html', {
        'servers': servers,
        'total_bases': total_bases,
        'total_analyses': total_analyses,
        'active_menu': 'parametrage'
    })

@login_required
def server_add(request):
    if request.method == 'POST':
        form = ServerForm(request.POST)
        if form.is_valid():
            server = form.save(commit=False)
            server.password = request.POST.get('password_input', '')
            # Récupérer les bases de données
            databases = request.POST.getlist('databases[]')
            server.databases = ','.join([db for db in databases if db])
            server.save()
            messages.success(request, f"Le serveur '{server.name}' a été ajouté avec succès ✅")
            return redirect('servers:server_list')
    else:
        form = ServerForm()
    
    return render(request, 'servers/server_form.html', {
        'form': form,
        'action': 'Ajouter',
        'active_menu': 'parametrage'
    })

@login_required
def get_databases_ajax(request):
    """Récupère TOUTES les bases de données d'un serveur"""
    ip = request.GET.get('ip')
    port = request.GET.get('port', '1433')
    user = request.GET.get('user')
    password = request.GET.get('password')
    
    try:
        conn_str = (
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={ip},{port};"
            f"UID={user};"
            f"PWD={password};"
            f"TrustServerCertificate=yes;"
        )
        conn = pyodbc.connect(conn_str, timeout=5)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT name FROM sys.databases 
            WHERE name NOT IN ('master', 'tempdb', 'model', 'msdb')
            ORDER BY name
        """)
        databases = [row[0] for row in cursor.fetchall()]
        conn.close()
        return JsonResponse({'success': True, 'databases': databases})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def server_edit(request, pk):
    server = get_object_or_404(Server, pk=pk)
    if request.method == 'POST':
        form = ServerForm(request.POST, instance=server)
        if form.is_valid():
            server = form.save(commit=False)
            server.password = request.POST.get('password_input', server.password)
            # Récupérer les bases de données
            databases = request.POST.getlist('databases[]')
            server.databases = ','.join([db for db in databases if db])
            server.save()
            messages.success(request, f"Le serveur '{server.name}' a été modifié avec succès ✅")
            return redirect('servers:server_list')
    else:
        form = ServerForm(instance=server)
    
    existing_databases = server.get_databases_list()
    
    return render(request, 'servers/server_form.html', {
        'form': form,
        'action': 'Modifier',
        'server': server,
        'existing_databases': existing_databases,
        'active_menu': 'parametrage'
    })

@login_required
def server_delete(request, pk):
    server = get_object_or_404(Server, pk=pk)
    if request.method == 'POST':
        server_name = server.name
        server.delete()
        messages.success(request, f"Le serveur '{server_name}' a été supprimé avec succès ✅")
        return redirect('servers:server_list')
    return render(request, 'servers/server_confirm_delete.html', {
        'server': server,
        'active_menu': 'parametrage'
    })