"""
Configuration des URLs principales du projet e_agri
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

# NE PAS importer de vues ici !
# Toutes les vues sont dans agri_market/views.py

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # Toutes les routes de l'application agri_market
    # Le '' signifie que la racine du site pointe vers agri_market
    path('', include('agri_market.urls')),
]

# Servir les fichiers médias en développement
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
