from django import forms
from .models import WorkOrder

class WorkOrderForm(forms.ModelForm):
    class Meta:
        model = WorkOrder
        fields = ["numero","cliente","titulo","descripcion","prioridad","estado","asignado_a","fecha_limite"]
        widgets = {"fecha_limite": forms.DateTimeInput(attrs={"type": "datetime-local"})}
