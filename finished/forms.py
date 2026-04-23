# finished/forms.py
from django import forms

from products.models import Product
from .models import FinishedRecipe



class FinishedRecipeForm(forms.ModelForm):
    class Meta:
        model = FinishedRecipe
        fields = ['name', 'description', 'finished_product', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'fb-input', 'placeholder': 'Ej: SMC Engorda Terminado'}),
            'description': forms.Textarea(attrs={'class': 'fb-input', 'rows': 3, 'placeholder': 'Descripción de la dieta...'}),
            'finished_product': forms.Select(attrs={'class': 'fb-input'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'fb-checkbox'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filtrar solo productos marcados como terminados
        self.fields['finished_product'].queryset = Product.objects.filter(
            is_finished=True, 
            is_active=True
        ).order_by('name')