from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('accounts.urls')),
    path('parametrage/', include('servers.urls')),
    path('moteur/', include('engine.urls')),
    # Pas besoin de ligne logout ici car c'est dans accounts.urls
]