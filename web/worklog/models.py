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

    technician = models.ForeignKey(User, on_delete=models.CASCADE, related_name='worklogs')
    collaborator = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='collaborations')
    start = models.DateTimeField()
    end = models.DateTimeField()
    task_type = models.CharField(max_length=20, choices=TASK_TYPES)
    other_task_type = models.CharField(max_length=100, blank=True, null=True)
    description = models.TextField()
    work_order = models.CharField(max_length=50, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    audio_file = models.FileField(upload_to='worklog_audios/', null=True, blank=True)

    def duration(self):
        return round((self.end - self.start).total_seconds() / 3600, 2)  # Horas redondeadas

    def __str__(self):
        return f"{self.technician} - {self.start.date()} - {self.task_type}"
