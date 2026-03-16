from django import forms
from .models import PurchasePrice
from products.models import Product
from branches.models import Branch

class PurchasePriceForm(forms.ModelForm):
    class Meta:
        model = PurchasePrice
        fields = ['product', 'price', 'notes']  # ✅ Eliminado 'branch'
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['product'].queryset = Product.objects.filter(is_active=True)
        self.fields['product'].widget.attrs.update({'class': 'product-select'})
        self.fields['price'].widget.attrs.update({
            'class': 'price-input',
            'step': '0.01',
            'min': '0'
        })
        
        # Si estamos editando (ya hay instancia), mostrar información del precio actual
        if self.instance and self.instance.pk:
            self.fields['product'].disabled = True  # No permitir cambiar producto en edición


class DateRangeForm(forms.Form):
    PERIOD_CHOICES = (
        ('today', 'Hoy'),
        ('yesterday', 'Ayer'),
        ('week', 'Esta semana'),
        ('month', 'Este mes'),
        ('custom', 'Personalizado'),
    )
    
    period = forms.ChoiceField(choices=PERIOD_CHOICES, required=True)
    date_from = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    date_to = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    branch = forms.ModelChoiceField(queryset=Branch.objects.filter(is_active=True), required=False)