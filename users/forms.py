from django import forms
from .models import User
from branches.models import Branch

class UserForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput,
        required=False,
        label="Contraseña"
    )
    
    # Campo para múltiples sucursales (solo para ADMIN)
    branches = forms.ModelMultipleChoiceField(
        queryset=Branch.objects.filter(is_active=True),
        required=False,
        widget=forms.SelectMultiple(attrs={
            'class': 'fb-select-multiple',
            'size': 5
        }),
        label="Sucursales asignadas"
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'role', 'branch', 'branches', 'password', 'is_active']
        widgets = {
            'branch': forms.Select(attrs={'class': 'fb-select'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Si estamos editando un usuario existente, cargar sus branches
        if self.instance and self.instance.pk:
            self.initial['branches'] = self.instance.branches.all()
        
        # Configurar campos según el rol
        self.fields['branch'].required = False
        self.fields['branch'].label = "Sucursal (solo para Cajero)"
        self.fields['branches'].label = "Sucursales asignadas (solo para Admin)"
        
        # Agregar help_text
        self.fields['branch'].help_text = "Selecciona la sucursal para el cajero"
        self.fields['branches'].help_text = "Mantén presionado Ctrl para seleccionar múltiples sucursales"

    def clean(self):
        cleaned_data = super().clean()
        role = cleaned_data.get('role')
        branch = cleaned_data.get('branch')
        branches = cleaned_data.get('branches')

        # SUPERADMIN no debe tener sucursales
        if role == 'SUPERADMIN':
            cleaned_data['branch'] = None
            cleaned_data['branches'] = []

        # CASHIER debe tener una sucursal
        if role == 'CASHIER':
            if not branch:
                self.add_error('branch', 'El cajero debe tener una sucursal asignada.')
            # Limpiar branches múltiples
            cleaned_data['branches'] = []

        # ADMIN debe tener al menos una sucursal
        if role == 'ADMIN':
            if not branches or len(branches) == 0:
                self.add_error('branches', 'El administrador debe tener al menos una sucursal asignada.')
            # Limpiar branch simple
            cleaned_data['branch'] = None

        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        
        if commit:
            user.save()
        
        # Guardar relaciones many-to-many
        if user.pk:
            if user.role == 'ADMIN':
                user.branches.set(self.cleaned_data.get('branches', []))
            else:
                user.branches.clear()
        
        return user