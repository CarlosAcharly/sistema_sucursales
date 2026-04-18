from django import forms
from .models import Branch

class BranchForm(forms.ModelForm):
    class Meta:
        model = Branch
        fields = ['name', 'address', 'is_active', 'can_transfer']  # ✅ Agregar can_transfer
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'facebook-input',
                'placeholder': 'Ej: Sucursal Centro'
            }),
            'address': forms.Textarea(attrs={
                'class': 'facebook-input',
                'rows': 3,
                'placeholder': 'Ej: Av. Principal #123'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'facebook-checkbox'
            }),
            'can_transfer': forms.CheckboxInput(attrs={  # ✅ Nuevo widget
                'class': 'facebook-checkbox'
            })
        }
        labels = {
            'name': 'Nombre de la sucursal',
            'address': 'Dirección completa',
            'is_active': 'Sucursal activa',
            'can_transfer': 'Permitir transferencias'  # ✅ Nueva etiqueta
        }