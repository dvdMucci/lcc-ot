from django import forms
from .models import WorkLog

class WorkLogForm(forms.ModelForm):
    class Meta:
        model = WorkLog
        fields = ['start', 'end', 'task_type', 'other_task_type', 'description', 'collaborator', 'work_order']
        widgets = {
            'start': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'end': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'description': forms.Textarea(attrs={'rows': 5}),
        }

    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get('start')
        end = cleaned_data.get('end')
        task_type = cleaned_data.get('task_type')
        other_task_type = cleaned_data.get('other_task_type')

        if start and end and end <= start:
            raise forms.ValidationError("La hora de finalización debe ser posterior a la de inicio.")

        if task_type == 'Otros' and not other_task_type:
            raise forms.ValidationError("Debe especificar el tipo de tarea si eligió 'Otros'.")
