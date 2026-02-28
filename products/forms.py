from django import forms
from .models import Product

class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['name', 'description', 'price_kg', 'price_bulk', 'price_wholesale', 'price_special', 'is_active', 'is_ingredient']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        # Validar que al menos tenga un precio
        if not any([
            cleaned_data.get('price_kg'),
            cleaned_data.get('price_bulk'),
            cleaned_data.get('price_wholesale'),
            cleaned_data.get('price_special')
        ]):
            raise forms.ValidationError("Debes configurar al menos un precio para el producto.")
        return cleaned_data