# branches/forms.py
from django import forms
from .models import Branch

class BranchForm(forms.ModelForm):
    class Meta:
        model = Branch
        fields = ['name', 'address', 'phone', 'is_active', 'can_transfer']
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
            'phone': forms.TextInput(attrs={
                'class': 'facebook-input',
                'placeholder': 'Ej: 55 1234 5678',
                'style': 'padding-left: 40px !important;'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'facebook-checkbox'
            }),
            'can_transfer': forms.CheckboxInput(attrs={
                'class': 'facebook-checkbox'
            })
        }
        labels = {
            'name': 'Nombre de la sucursal',
            'address': 'Dirección completa',
            'phone': 'Teléfono',
            'is_active': 'Sucursal activa',
            'can_transfer': 'Permitir transferencias'
        }