from django import forms
from .models import WorkOrder
from django.contrib.auth import get_user_model

User = get_user_model()

class WorkOrderForm(forms.ModelForm):
    class Meta:
        model = WorkOrder
        fields = ["numero","cliente","titulo","descripcion","prioridad","estado","asignado_a","fecha_limite"]
        widgets = {"fecha_limite": forms.DateTimeInput(attrs={"type": "datetime-local"})}
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Filtrar estados según tipo de usuario
        if self.user and hasattr(self.user, 'user_type'):
            is_tecnico = self.user.user_type == 'tecnico'
            if is_tecnico:
                # Los técnicos no pueden ver ni seleccionar A_FACTURAR y FACTURADA
                restricted_choices = [
                    choice for choice in self.fields['estado'].choices 
                    if choice[0] not in ['a_facturar', 'facturada']
                ]
                self.fields['estado'].choices = restricted_choices

class WorkOrderFilterForm(forms.Form):
    # Búsqueda general
    search = forms.CharField(
        required=False,
        label="Buscar",
        widget=forms.TextInput(attrs={
            'placeholder': 'Buscar por cliente, CUIT, número OT, título...',
            'class': 'form-control'
        })
    )
    
    # Filtros específicos
    cliente = forms.CharField(
        required=False,
        label="Cliente",
        widget=forms.TextInput(attrs={
            'placeholder': 'Buscar cliente...',
            'class': 'form-control',
            'data-min-chars': '4'
        })
    )
    
    cuit = forms.CharField(
        required=False,
        label="CUIT",
        widget=forms.TextInput(attrs={
            'placeholder': 'Buscar por CUIT...',
            'class': 'form-control'
        })
    )
    
    numero_ot = forms.CharField(
        required=False,
        label="Número OT",
        widget=forms.TextInput(attrs={
            'placeholder': 'Buscar número OT...',
            'class': 'form-control'
        })
    )
    
    titulo = forms.CharField(
        required=False,
        label="Título",
        widget=forms.TextInput(attrs={
            'placeholder': 'Buscar en título...',
            'class': 'form-control'
        })
    )
    
    prioridad = forms.ChoiceField(
        choices=[('', '---------')] + WorkOrder.Prioridad.choices,
        required=False,
        label="Prioridad",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    estado = forms.ChoiceField(
        choices=[('', '---------')] + WorkOrder.Estado.choices,
        required=False,
        label="Estado",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Filtrar estados según tipo de usuario
        if self.user and hasattr(self.user, 'user_type'):
            is_tecnico = self.user.user_type == 'tecnico'
            if is_tecnico:
                # Los técnicos no pueden filtrar por A_FACTURAR y FACTURADA
                restricted_choices = [
                    choice for choice in self.fields['estado'].choices 
                    if choice[0] not in ['a_facturar', 'facturada']
                ]
                self.fields['estado'].choices = restricted_choices
    
    asignado_a = forms.ModelChoiceField(
        queryset=User.objects.filter(user_type='tecnico').order_by('first_name', 'last_name'),
        required=False,
        label="Asignado a",
        empty_label="---------",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    # Ordenamiento
    ordenar_por = forms.ChoiceField(
        choices=[
            ('-fecha_creacion', 'Fecha de creación (más reciente)'),
            ('fecha_creacion', 'Fecha de creación (más antigua)'),
            ('fecha_limite', 'Fecha límite (más próxima)'),
            ('-fecha_limite', 'Fecha límite (más lejana)'),
            ('prioridad', 'Prioridad (ascendente)'),
            ('-prioridad', 'Prioridad (descendente)'),
            ('estado', 'Estado (ascendente)'),
            ('-estado', 'Estado (descendente)'),
            ('numero', 'Número OT (ascendente)'),
            ('-numero', 'Número OT (descendente)'),
        ],
        required=False,
        label="Ordenar por",
        initial='-fecha_creacion',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    # Filtros de fecha
    fecha_desde = forms.DateField(
        required=False,
        label="Fecha desde",
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        })
    )
    
    fecha_hasta = forms.DateField(
        required=False,
        label="Fecha hasta",
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        })
    )
    
    # Estado de vencimiento
    estado_vencimiento = forms.ChoiceField(
        choices=[
            ('', '---------'),
            ('vencidas', 'Vencidas'),
            ('por_vencer', 'Por vencer'),
            ('sin_limite', 'Sin fecha límite'),
        ],
        required=False,
        label="Estado de vencimiento",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
