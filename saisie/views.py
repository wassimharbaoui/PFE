from django.http import HttpResponse  # Pour la vue hello qu'on garde
from .models import Client
from django.shortcuts import render, redirect, get_object_or_404
from .forms import ClientForm

def hello(request):
    """
    Page d'accueil avec liens vers les fonctionnalités principales
    """
    return render(request, 'saisie/accueil.html')

def liste_clients(request):
    """
    Vue pour afficher la liste de tous les clients.
    Récupère tous les clients dans la base et les envoie au template.
    """
    clients = Client.objects.all()  # SELECT * FROM client
    return render(request, 'saisie/liste.html', {'clients': clients})

def ajouter_client(request):
    """
    Vue pour ajouter un nouveau client.
    GET : Affiche le formulaire vide
    POST : Traite le formulaire soumis
    """
    if request.method == 'POST':
        # Formulaire soumis : on vérifie et on sauvegarde
        form = ClientForm(request.POST)
        if form.is_valid():
            form.save()  # Sauvegarde dans la base de données
            return redirect('liste_clients')  # Redirection vers la liste
    else:
        # Premier accès : formulaire vide
        form = ClientForm()
    
    return render(request, 'saisie/ajouter.html', {'form': form})


def modifier_client(request, pk):
    """
    Vue pour modifier un client existant.
    pk = Primary Key (ID du client dans la base)
    """
    client = get_object_or_404(Client, pk=pk)
    
    if request.method == 'POST':
        form = ClientForm(request.POST, instance=client)
        if form.is_valid():
            form.save()
            return redirect('liste_clients')
    else:
        form = ClientForm(instance=client)
    
    return render(request, 'saisie/modifier.html', {'form': form, 'client': client})

def supprimer_client(request, pk):
    """
    Vue pour supprimer un client.
    """
    client = get_object_or_404(Client, pk=pk)
    
    if request.method == 'POST':
        client.delete()
        return redirect('liste_clients')
    
    return render(request, 'saisie/supprimer.html', {'client': client})