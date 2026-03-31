from django.urls import path
from . import views

app_name = 'engine'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('lancer/', views.lancer_analyse, name='lancer_analyse'),
    path('base/<str:base_nom>/', views.detail_base, name='detail_base'),  # ← Ajoute
    path('ajax/get-databases/', views.get_databases_ajax, name='get_databases_ajax'),
    path('chatbot-api/', views.chatbot_api, name='chatbot_api'),
]