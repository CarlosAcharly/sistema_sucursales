from django import forms
from .models import Inventory, Transfer, TransferItem

class InventoryForm(forms.ModelForm):
    class Meta:
        model = Inventory
        fields = ['branch', 'product', 'stock']
        widgets = {
            'branch': forms.Select(attrs={'class': 'form-control'}),
            'product': forms.Select(attrs={'class': 'form-control'}),
            'stock': forms.NumberInput(attrs={'class': 'form-control'}),
        }
    
    def clean_stock(self):
        stock = self.cleaned_data.get('stock')
        if stock < 0:
            raise forms.ValidationError('El stock no puede ser negativo.')
        return stock


class TransferForm(forms.ModelForm):
    class Meta:
        model = Transfer
        fields = ['from_branch', 'to_branch', 'notes']
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }


class TransferItemForm(forms.ModelForm):
    class Meta:
        model = TransferItem
        fields = ['product', 'quantity']
        widgets = {
            'product': forms.Select(attrs={'class': 'form-control product-select'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control quantity-input', 'min': '1'}),
        }