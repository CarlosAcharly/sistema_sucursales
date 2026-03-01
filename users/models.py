from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):

    ROLE_CHOICES = (
        ('SUPERADMIN', 'Super Admin'),
        ('ADMIN', 'Admin'),
        ('CASHIER', 'Cajero'),
    )

    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    
    # Para CASHIER - una sola sucursal (campo existente)
    branch = models.ForeignKey(
        'branches.Branch',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cashiers'
    )
    
    # Para ADMIN - múltiples sucursales (nuevo campo)
    branches = models.ManyToManyField(
        'branches.Branch',
        blank=True,
        related_name='admins'
    )

    def is_superadmin(self):
        return self.role == 'SUPERADMIN'

    def is_admin(self):
        return self.role == 'ADMIN'

    def is_cashier(self):
        return self.role == 'CASHIER'
    
    def get_branches_display(self):
        """Retorna las sucursales del usuario según su rol"""
        if self.is_superadmin():
            return "Todas las sucursales"
        elif self.is_admin():
            return ", ".join([b.name for b in self.branches.all()]) or "Sin sucursales"
        elif self.is_cashier() and self.branch:
            return self.branch.name
        return "Sin sucursal"
    
    def save(self, *args, **kwargs):
        # SUPERADMIN no debe tener sucursales
        if self.role == 'SUPERADMIN':
            self.branch = None
            # Limpiar branches many-to-many después de guardar
            self._clear_branches = True
        
        # CASHIER debe tener una sucursal
        if self.role == 'CASHIER' and not self.branch:
            raise ValueError("Un cajero debe tener una sucursal asignada.")
        
        # ADMIN puede tener múltiples sucursales (no validación especial)
        
        super().save(*args, **kwargs)
        
        # Si es SUPERADMIN, limpiar branches después de guardar
        if hasattr(self, '_clear_branches') and self._clear_branches:
            self.branches.clear()