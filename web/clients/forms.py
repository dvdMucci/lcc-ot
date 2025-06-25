from django import forms
from .models import Client

class ClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = [
            'razon_social',
            'cuit',
            'ciudad',
            'provincia',
            'codigo_postal',
            'telefono'
        ]
        widgets = {
            'razon_social': forms.TextInput(attrs={'class': 'form-control'}),
            'cuit': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: 20-XXXXXXXX-2'}),
            'ciudad': forms.TextInput(attrs={'class': 'form-control'}),
            'provincia': forms.TextInput(attrs={'class': 'form-control'}),
            'codigo_postal': forms.TextInput(attrs={'class': 'form-control'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control'}),
        }
        labels = {
            'razon_social': 'Razón Social / Nombre',
            'cuit': 'CUIT/CUIL',
            'ciudad': 'Ciudad',
            'provincia': 'Provincia',
            'codigo_postal': 'Código Postal',
            'telefono': 'Teléfono de Contacto',
        }

    def clean_cuit(self):
        cuit = self.cleaned_data['cuit']
        # Eliminar guiones o espacios para la validación de unicidad
        cuit_cleaned = cuit.replace('-', '').replace(' ', '')

        # Validar formato básico (ej. 11 o 13 dígitos)
        if not cuit_cleaned.isdigit() or not (len(cuit_cleaned) == 11 or len(cuit_cleaned) == 13):
            raise forms.ValidationError("El CUIT/CUIL debe contener solo números y tener 11 o 13 dígitos (sin guiones para la validación).")

        # Verificar unicidad (excluyendo el propio cliente si es edición)
        if self.instance.pk: # Si es una edición
            if Client.objects.filter(cuit=cuit).exclude(pk=self.instance.pk).exists():
                raise forms.ValidationError("Ya existe un cliente con este CUIT/CUIL.")
        else: # Si es una creación
            if Client.objects.filter(cuit=cuit).exists():
                raise forms.ValidationError("Ya existe un cliente con este CUIT/CUIL.")
        
        return cuit