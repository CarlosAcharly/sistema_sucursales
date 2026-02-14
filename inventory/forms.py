from django import forms
from .models import Inventory
from .models import Transfer


class InventoryForm(forms.ModelForm):

    class Meta:
        model = Inventory
        fields = ['branch', 'product', 'stock']

        widgets = {
            'branch': forms.Select(attrs={'class': 'form-control'}),
            'product': forms.Select(attrs={'class': 'form-control'}),
            'stock': forms.NumberInput(attrs={'class': 'form-control'}),
        }


class TransferForm(forms.ModelForm):

    class Meta:
        model = Transfer
        fields = ['from_branch', 'to_branch', 'product', 'quantity']
