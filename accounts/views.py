from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from servers.models import Server
from engine.models import AnalyseBase  # ← Changé ici (plus AnalyseResultat)

@login_required
def welcome(request):
    # Statistiques pour la page d'accueil
    servers_count = Server.objects.count()
    
    databases_count = 0
    for server in Server.objects.all():
        databases_count += len(server.get_databases_list())
    
    analyses_count = AnalyseBase.objects.count()  # ← Changé ici
    
    return render(request, 'welcome.html', {
        'servers_count': servers_count,
        'databases_count': databases_count,
        'analyses_count': analyses_count
    })

def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            return redirect('welcome')
        else:
            messages.error(request, 'Nom d\'utilisateur ou mot de passe incorrect')
    
    return render(request, 'accounts/login.html')

def logout_view(request):
    logout(request)
    return redirect('login')