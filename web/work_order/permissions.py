from django.contrib.auth.mixins import UserPassesTestMixin


class NotTecnicoRequiredMixin(UserPassesTestMixin):
    """
    Mixin que verifica que el usuario NO sea técnico.
    Los técnicos solo pueden ver, no pueden crear/editar.
    """
    
    def test_func(self):
        user = self.request.user
        if not user.is_authenticated:
            return False
        # Verificar si el usuario NO es de tipo técnico
        return getattr(user, 'user_type', '') != 'tecnico'
