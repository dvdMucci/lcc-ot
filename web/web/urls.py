from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from accounts.views import dashboard # Importa el dashboard de tu app 'accounts'

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', dashboard, name='dashboard'), # Redirección de la raíz al dashboard
    path('dashboard/', dashboard, name='dashboard'),
    path('worklog/', include('worklog.urls')), # Incluye las URLs de la aplicación 'worklog'
    path('work_order/', include('work_order.urls')), # Incluye las URLs de la aplicación 'work_order'
    path('clients/', include('clients.urls')), # Incluye las URLs de la aplicación 'clients'
    path('accounts/', include('accounts.urls')), # Incluye las URLs de la aplicación 'accounts'
] # + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)  # Comentado por seguridad