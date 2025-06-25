from django.contrib import admin
from .models import Client

@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ('razon_social', 'cuit', 'ciudad', 'provincia', 'telefono', 'created_at')
    search_fields = ('razon_social', 'cuit', 'ciudad', 'provincia', 'telefono')
    list_filter = ('provincia', 'ciudad')
    readonly_fields = ('created_at', 'updated_at')