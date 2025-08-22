from django.apps import AppConfig

class WorkOrderConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "work_order"
    verbose_name = "Órdenes de Trabajo"

    def ready(self):
        from . import signals  # noqa
