from django.urls import path
from . import views

urlpatterns = [
    path('', views.hello, name='hello'),
    path('clients/', views.liste_clients, name='liste_clients'),
    path('clients/ajouter/', views.ajouter_client, name='ajouter_client'),
    path('clients/modifier/<int:pk>/', views.modifier_client, name='modifier_client'),
    path('clients/supprimer/<int:pk>/', views.supprimer_client, name='supprimer_client'),
]