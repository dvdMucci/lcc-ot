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
    status = forms.ChoiceField(
        choices=[('', '---------')] + WorkLog.STATUS_CHOICES,
        required=False,
        label="Estado"
    )
    date = forms.DateField(required=False, label="Día", widget=forms.DateInput(attrs={'type': 'date'}))
    week = forms.DateField(required=False, label="Semana (inicio)", widget=forms.DateInput(attrs={'type': 'date'}))
    month = forms.DateField(required=False, label="Mes", widget=forms.DateInput(attrs={'type': 'month'}))
    start_date = forms.DateField(required=False, label="Desde", widget=forms.DateInput(attrs={'type': 'date'}))
    end_date = forms.DateField(required=False, label="Hasta", widget=forms.DateInput(attrs={'type': 'date'}))


class WorkLogForm(forms.ModelForm):
    # Campo personalizado para órdenes de trabajo activas
    work_order = forms.ModelChoiceField(
        queryset=None,  # Se establecerá en __init__
        required=False,
        empty_label="Seleccionar orden de trabajo (opcional)",
        label="Orden de trabajo"
    )
    
    class Meta:
        model = WorkLog
        fields = [
            'start', 'end', 'task_type', 'other_task_type',
            'general_ops_subtype', 'warranty', 'field_city', 'field_km_one_way',
            'description', 'collaborator', 'work_order', 'status'
        ]
        widgets = {
            'start': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'end': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'description': forms.Textarea(attrs={'rows': 5}),
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Restringir estados para técnicos
        if self.user and hasattr(self.user, 'groups'):
            is_tecnico = self.user.groups.filter(name__iregex="^t[eé]cnico$").exists()
            if is_tecnico:
                # Los técnicos no pueden usar 'abierta' y 'cerrada'
                restricted_choices = [
                    choice for choice in self.fields['status'].choices 
                    if choice[0] not in ['abierta', 'cerrada']
                ]
                self.fields['status'].choices = restricted_choices
        
        # Intentar importar WorkOrder y establecer el queryset
        try:
            from work_order.models import WorkOrder
            # Filtrar solo órdenes activas (no cerradas ni canceladas)
            active_orders = WorkOrder.objects.exclude(
                estado__in=['cerrada', 'cancelada']
            ).order_by('-fecha_creacion')
            self.fields['work_order'].queryset = active_orders
        except ImportError:
            # Si no se puede importar WorkOrder, mantener el campo como CharField
            self.fields['work_order'] = forms.CharField(
                max_length=50,
                required=False,
                label="Orden de trabajo (opcional)",
                help_text="Ingrese el número de orden de trabajo"
            )

    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get('start')
        end = cleaned_data.get('end')
        task_type = cleaned_data.get('task_type')
        other_task_type = cleaned_data.get('other_task_type')
        general_ops_subtype = cleaned_data.get('general_ops_subtype')
        warranty = cleaned_data.get('warranty')
        field_city = cleaned_data.get('field_city')
        field_km_one_way = cleaned_data.get('field_km_one_way')

        if start and end and end <= start:
            raise forms.ValidationError("La hora de finalización debe ser posterior a la de inicio.")

        if task_type == 'Otros' and not other_task_type:
            raise forms.ValidationError("Debe especificar el tipo de tarea si eligió 'Otros'.")

        if task_type == 'Operaciones generales' and not general_ops_subtype:
            raise forms.ValidationError("Debe seleccionar un subtipo para 'Operaciones generales'.")

        if task_type in ['Taller', 'Campo']:
            # warranty es opcional, pero el campo existe; no hay validación extra
            pass

        if task_type == 'Campo':
            if not field_city:
                raise forms.ValidationError("Debe especificar la ciudad para tareas de 'Campo'.")
            if field_km_one_way is None:
                raise forms.ValidationError("Debe especificar los kilómetros de ida para tareas de 'Campo'.")
            if field_km_one_way is not None and field_km_one_way < 0:
                raise forms.ValidationError("Los kilómetros de ida deben ser un número positivo.")

        return cleaned_data


class WorkLogEditForm(forms.ModelForm):
    """Formulario para editar tareas existentes"""
    # Campo personalizado para órdenes de trabajo activas
    work_order = forms.ModelChoiceField(
        queryset=None,  # Se establecerá en __init__
        required=False,
        empty_label="Seleccionar orden de trabajo (opcional)",
        label="Orden de trabajo"
    )
    
    class Meta:
        model = WorkLog
        fields = [
            'start', 'end', 'task_type', 'other_task_type',
            'general_ops_subtype', 'warranty', 'field_city', 'field_km_one_way',
            'description', 'collaborator', 'work_order', 'status'
        ]
        widgets = {
            'start': forms.DateTimeInput(attrs={'type': 'text', 'class': 'form-control'}),
            'end': forms.DateTimeInput(attrs={'type': 'text', 'class': 'form-control'}),
            'description': forms.Textarea(attrs={'rows': 5}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Restringir estados para técnicos
        if self.user and hasattr(self.user, 'groups'):
            is_tecnico = self.user.groups.filter(name__iregex="^t[eé]cnico$").exists()
            if is_tecnico:
                # Los técnicos no pueden usar 'abierta' y 'cerrada'
                restricted_choices = [
                    choice for choice in self.fields['status'].choices 
                    if choice[0] not in ['abierta', 'cerrada']
                ]
                self.fields['status'].choices = restricted_choices
        
        # Intentar importar WorkOrder y establecer el queryset
        try:
            from work_order.models import WorkOrder
            # Filtrar solo órdenes activas (no cerradas ni canceladas)
            active_orders = WorkOrder.objects.exclude(
                estado__in=['cerrada', 'cancelada']
            ).order_by('-fecha_creacion')
            self.fields['work_order'].queryset = active_orders
        except ImportError:
            # Si no se puede importar WorkOrder, mantener el campo como CharField
            self.fields['work_order'] = forms.CharField(
                max_length=50,
                required=False,
                label="Orden de trabajo (opcional)",
                help_text="Ingrese el número de orden de trabajo"
            )
        
        # Si no es admin/supervisor, limitar edición de algunos campos si existen
        # TEMPORALMENTE COMENTADO PARA DEBUG
        # if self.user and not (self.user.is_staff or getattr(self.user, 'user_type', '') in ['admin', 'supervisor']):
        #     for field_name in ['start', 'end']:
        #         if field_name in self.fields:
        #             self.fields[field_name].widget.attrs['readonly'] = True

    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get('start')
        end = cleaned_data.get('end')
        task_type = cleaned_data.get('task_type')
        other_task_type = cleaned_data.get('other_task_type')
        general_ops_subtype = cleaned_data.get('general_ops_subtype')
        field_city = cleaned_data.get('field_city')
        field_km_one_way = cleaned_data.get('field_km_one_way')

        if start and end and end <= start:
            raise forms.ValidationError("La hora de finalización debe ser posterior a la de inicio.")

        if task_type == 'Otros' and not other_task_type:
            raise forms.ValidationError("Debe especificar el tipo de tarea si eligió 'Otros'.")

        if task_type == 'Operaciones generales' and not general_ops_subtype:
            raise forms.ValidationError("Debe seleccionar un subtipo para 'Operaciones generales'.")

        if task_type == 'Campo':
            if not field_city:
                raise forms.ValidationError("Debe especificar la ciudad para tareas de 'Campo'.")
            if field_km_one_way is None:
                raise forms.ValidationError("Debe especificar los kilómetros de ida para tareas de 'Campo'.")
            if field_km_one_way is not None and field_km_one_way < 0:
                raise forms.ValidationError("Los kilómetros de ida deben ser un número positivo.")

        return cleaned_data
