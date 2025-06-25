from django.db import models

class Client(models.Model):
    razon_social = models.CharField(max_length=255, unique=True, verbose_name="Razón Social o Nombre del Cliente")
    cuit = models.CharField(max_length=13, unique=True, verbose_name="CUIT/CUIL", help_text="Formato: XX-XXXXXXXX-X (sin guiones)")
    ciudad = models.CharField(max_length=100, verbose_name="Ciudad")
    provincia = models.CharField(max_length=100, verbose_name="Provincia")
    codigo_postal = models.CharField(max_length=10, blank=True, null=True, verbose_name="Código Postal")
    telefono = models.CharField(max_length=50, blank=True, null=True, verbose_name="Teléfono de Contacto")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"
        ordering = ['razon_social'] # Ordenar por razón social por defecto

    def __str__(self):
        return self.razon_social