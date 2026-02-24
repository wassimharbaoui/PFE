from django.urls import path
from . import views

app_name = 'servers'

urlpatterns = [
    path('', views.server_list, name='server_list'),
    path('add/', views.server_add, name='server_add'),
    path('edit/<int:pk>/', views.server_edit, name='server_edit'),
    path('delete/<int:pk>/', views.server_delete, name='server_delete'),
    path('ajax/get-databases/', views.get_databases_ajax, name='get_databases'),
]