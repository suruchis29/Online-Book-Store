from django.contrib import admin
from django.urls import path, include
from . import settings
from django.conf.urls.static import static
from two_factor.urls import urlpatterns as two_factor_urls


urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('store.urls')),
    path('cart/', include('cart.urls')),
    path('', include(two_factor_urls)),
    

   
    

    
    
] + static(settings.MEDIA_URL,document_root = settings.MEDIA_ROOT)

