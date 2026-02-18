from django import forms
from .models import Branch

class BranchForm(forms.ModelForm):
    class Meta:
        model = Branch
        fields = ['name', 'address', 'is_active']
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
            })
        }
        labels = {
            'name': 'Nombre de la sucursal',
            'address': 'Dirección completa',
            'is_active': 'Sucursal activa'
        }