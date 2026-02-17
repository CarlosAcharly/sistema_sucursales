from django import forms
from diets.models import DietCajeroItem


class DietCajeroItemForm(forms.ModelForm):
    class Meta:
        model = DietCajeroItem
        fields = ['kilos']
        widgets = {
            'kilos': forms.NumberInput(attrs={'step': '0.01', 'min': '0'})
        }