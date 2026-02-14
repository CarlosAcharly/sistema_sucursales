from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):

    ROLE_CHOICES = (
        ('SUPERADMIN', 'Super Admin'),
        ('ADMIN', 'Admin'),
        ('CASHIER', 'Cajero'),
    )

    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    branch = models.ForeignKey(
        'branches.Branch',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    def is_superadmin(self):
        return self.role == 'SUPERADMIN'

    def is_admin(self):
        return self.role == 'ADMIN'

    def is_cashier(self):
        return self.role == 'CASHIER'
    
    def save(self, *args, **kwargs):

        # SUPERADMIN no debe tener sucursal
        if self.role == 'SUPERADMIN':
            self.branch = None

        # CASHIER debe tener sucursal
        if self.role == 'CASHIER' and not self.branch:
            raise ValueError("Un cajero debe tener una sucursal asignada.")

        super().save(*args, **kwargs)
