from django import forms
from .models import WorkLog
from django.contrib.auth import get_user_model

User = get_user_model()

class WorkLogFilterForm(forms.Form):
    technician = forms.ModelChoiceField(
        queryset=User.objects.all(),
        required=False,
        label="Técnico"
    )
    task_type = forms.ChoiceField(
        choices=[('', '---------')] + WorkLog.TASK_TYPES,
        required=False,
        label="Tipo de tarea"
    )
    date = forms.DateField(required=False, label="Día", widget=forms.DateInput(attrs={'type': 'date'}))
    week = forms.DateField(required=False, label="Semana (inicio)", widget=forms.DateInput(attrs={'type': 'date'}))
    month = forms.DateField(required=False, label="Mes", widget=forms.DateInput(attrs={'type': 'month'}))
    start_date = forms.DateField(required=False, label="Desde", widget=forms.DateInput(attrs={'type': 'date'}))
    end_date = forms.DateField(required=False, label="Hasta", widget=forms.DateInput(attrs={'type': 'date'}))


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
