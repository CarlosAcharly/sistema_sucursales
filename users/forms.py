from django import forms
from .models import User

class UserForm(forms.ModelForm):

    password = forms.CharField(
        widget=forms.PasswordInput,
        required=False
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'role', 'branch', 'password', 'is_active']

    def clean(self):
        cleaned_data = super().clean()
        role = cleaned_data.get('role')
        branch = cleaned_data.get('branch')

        # SUPERADMIN no debe tener sucursal
        if role == 'SUPERADMIN':
            cleaned_data['branch'] = None

        # CASHIER debe tener sucursal
        if role == 'CASHIER' and not branch:
            self.add_error('branch', 'El cajero debe tener una sucursal asignada.')

        return cleaned_data
