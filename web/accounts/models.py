from django.contrib.auth.models import AbstractUser
from django.db import models

class CustomUser(AbstractUser):
    USER_TYPES = [
        ('admin', 'Administrador'),
        ('tecnico', 'Técnico'),
        ('operador', 'Operador'),
        ('supervisor', 'Supervisor'),
    ]
    
    user_type = models.CharField(
        max_length=20,
        choices=USER_TYPES,
        default='operador',
        verbose_name='Tipo de Usuario'
    )
    
    telegram_chat_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name='Chat ID de Telegram'
    )
    
    is_2fa_enabled = models.BooleanField(
        default=False,
        verbose_name='2FA Habilitado'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # --- ADD THESE RELATED_NAME ARGUMENTS ---
    groups = models.ManyToManyField(
        'auth.Group',
        related_name='customuser_set', # Unique related_name for CustomUser groups
        blank=True,
        help_text='The groups this user belongs to. A user will get all permissions granted to each of their groups.',
        verbose_name='groups',
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        related_name='customuser_permissions_set', # Unique related_name for CustomUser permissions
        blank=True,
        help_text='Specific permissions for this user.',
        verbose_name='user permissions',
    )
    # ----------------------------------------
    
    class Meta:
        verbose_name = 'Usuario'
        verbose_name_plural = 'Usuarios'
    
    def __str__(self):
        return f"{self.username} ({self.get_user_type_display()})"
    
    def can_manage_users(self):
        return self.user_type == 'admin'