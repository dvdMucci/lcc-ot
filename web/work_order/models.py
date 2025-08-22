from django.db import models
from django.conf import settings
from django.utils import timezone
from clients.models import Client

class WorkOrder(models.Model):
    class Prioridad(models.TextChoices):
        BAJA = "baja", "Baja"
        MEDIA = "media", "Media"
        ALTA = "alta", "Alta"
        URGENTE = "urgente", "Urgente"

    class Estado(models.TextChoices):
        ABIERTA = "abierta", "Abierta"
        EN_PROCESO = "en_proceso", "En proceso"
        PAUSADA = "pausada", "Pausada"
        CERRADA = "cerrada", "Cerrada"

    numero = models.CharField(max_length=30, unique=True, help_text="Identificador de la OT (p.ej. OT-2025-001)")
    cliente = models.ForeignKey(Client, on_delete=models.PROTECT, related_name="ordenes")
    titulo = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True)
    prioridad = models.CharField(max_length=10, choices=Prioridad.choices, default=Prioridad.MEDIA)
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.ABIERTA)

    asignado_a = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="ordenes_asignadas",
    )

    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_limite = models.DateTimeField(null=True, blank=True)
    fecha_cierre = models.DateTimeField(null=True, blank=True)

    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="ordenes_creadas",
    )
    actualizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="ordenes_actualizadas",
    )
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Orden de Trabajo"
        verbose_name_plural = "Órdenes de Trabajo"
        ordering = ["-fecha_creacion"]

    def __str__(self):
        return f"{self.numero} – {self.titulo}"

    def cerrar(self, usuario=None):
        self.estado = self.Estado.CERRADA
        self.fecha_cierre = timezone.now()
        if usuario:
            self.actualizado_por = usuario
        self.save(update_fields=["estado", "fecha_cierre", "actualizado_por", "actualizado_en"])


class WorkOrderAttachment(models.Model):
    orden = models.ForeignKey(WorkOrder, on_delete=models.CASCADE, related_name="adjuntos")
    archivo = models.FileField(upload_to="workorders/")
    descripcion = models.CharField(max_length=255, blank=True)
    subido_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    subido_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Adjunto de Orden"
        verbose_name_plural = "Adjuntos de Orden"
