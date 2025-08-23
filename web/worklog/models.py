from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class WorkLog(models.Model):
    TASK_TYPES = [
        ('Taller', 'Taller'),
        ('Campo', 'Campo'),
        ('Diligencia', 'Diligencia'),
        ('Otros', 'Otros'),
    ]

    STATUS_CHOICES = [
        ('pendiente', 'Pendiente'),
        ('en_proceso', 'En Proceso'),
        ('completada', 'Completada'),
        ('cancelada', 'Cancelada'),
    ]

    technician = models.ForeignKey(User, on_delete=models.CASCADE, related_name='worklogs')
    collaborator = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='collaborations')
    start = models.DateTimeField()
    end = models.DateTimeField()
    task_type = models.CharField(max_length=20, choices=TASK_TYPES)
    other_task_type = models.CharField(max_length=100, blank=True, null=True)
    description = models.TextField()
    work_order = models.CharField(max_length=50, null=True, blank=True)
    work_order_ref = models.ForeignKey(
        'work_order.WorkOrder', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name="worklogs"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pendiente')

    # Campos de auditoría - con valores por defecto para migración
    created_by = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='created_worklogs',
        null=True,  # Temporal para migración
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_by = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='updated_worklogs', 
        null=True, 
        blank=True
    )
    updated_at = models.DateTimeField(auto_now=True)
    audio_file = models.FileField(upload_to='worklog_audios/', null=True, blank=True)

    def duration(self):
        return round((self.end - self.start).total_seconds() / 3600, 2)  # Horas redondeadas

    def __str__(self):
        return f"{self.technician} - {self.start.date()} - {self.task_type}"

    def save(self, *args, **kwargs):
        # Si no hay created_by, usar technician como creador
        if not self.created_by:
            self.created_by = self.technician
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = 'Registro de Trabajo'
        verbose_name_plural = 'Registros de Trabajo'
        ordering = ['-start']


class WorkLogHistory(models.Model):
    """Modelo para rastrear el historial de cambios en las tareas"""
    worklog = models.ForeignKey(WorkLog, on_delete=models.CASCADE, related_name='history')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='worklog_changes')
    action = models.CharField(max_length=50)  # 'created', 'updated', 'deleted'
    field_name = models.CharField(max_length=100, null=True, blank=True)
    old_value = models.TextField(null=True, blank=True)
    new_value = models.TextField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)

    class Meta:
        verbose_name = 'Historial de Cambios'
        verbose_name_plural = 'Historial de Cambios'
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.action} en {self.worklog} por {self.user} - {self.timestamp}"
