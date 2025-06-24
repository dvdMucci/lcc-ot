from django.contrib import admin
from django.contrib.auth.admin import UserAdmin # El UserAdmin base de Django
from .models import CustomUser
from .forms import CustomUserCreationForm, CustomUserChangeForm

@admin.register(CustomUser) # Registra tu modelo CustomUser en el admin
class CustomUserAdmin(UserAdmin):
    add_form = CustomUserCreationForm # Formulario para crear usuarios desde el admin
    form = CustomUserChangeForm # Formulario para editar usuarios desde el admin
    model = CustomUser # El modelo asociado
    list_display = ['username', 'email', 'user_type', 'is_2fa_enabled', 'telegram_chat_id', 'is_active'] # Campos a mostrar en la lista
    list_filter = ['user_type', 'is_2fa_enabled', 'is_active', 'date_joined'] # Campos para filtrar
    fieldsets = UserAdmin.fieldsets + ( # Campos adicionales en el formulario de edición
        ('Información Adicional', {
            'fields': ('user_type', 'telegram_chat_id', 'is_2fa_enabled')
        }),
    )
    add_fieldsets = UserAdmin.add_fieldsets + ( # Campos adicionales en el formulario de creación
        ('Información Adicional', {
            'fields': ('user_type', 'email')
        }),
    )