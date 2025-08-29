# middleware.py
from django.http import HttpResponseForbidden
from django.conf import settings
import ipaddress

class AdminIPRestrictMiddleware:
    """
    Middleware que restringe acceso al panel admin por IP
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Verificar si es una ruta de admin
        if request.path.startswith('/admin/'):
            client_ip = self.get_client_ip(request)
            
            # Verificar si la IP está en la lista permitida
            if not self.is_ip_allowed(client_ip):
                return HttpResponseForbidden(
                    "Acceso denegado: IP no autorizada para administración"
                )
        
        return self.get_response(request)

    def get_client_ip(self, request):
        """Obtiene la IP real del cliente"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip

    def is_ip_allowed(self, client_ip):
        """Verifica si la IP está en la lista permitida"""
        allowed_ips = getattr(settings, 'ADMIN_ALLOWED_IPS', ['172.29.0.0/16'])
        
        try:
            client_ip_obj = ipaddress.ip_address(client_ip)
            for allowed_ip in allowed_ips:
                if '/' in allowed_ip:  # Es una red (ej: 192.168.1.0/24)
                    if client_ip_obj in ipaddress.ip_network(allowed_ip, strict=False):
                        return True
                else:  # Es una IP específica
                    if str(client_ip_obj) == allowed_ip:
                        return True
            return False
        except:
            return False