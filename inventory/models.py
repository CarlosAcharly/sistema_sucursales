from django.db import models

class Inventory(models.Model):
    branch = models.ForeignKey('branches.Branch', on_delete=models.CASCADE)
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE)
    stock = models.DecimalField(max_digits=10, decimal_places=3, default=0)  # ✅ Cambiado a DecimalField

    class Meta:
        unique_together = ('branch', 'product')

    def __str__(self):
        return f"{self.product.name} - {self.branch.name} - {self.stock} kg"


class InventoryMovement(models.Model):
    MOVEMENT_TYPES = (
        ('IN', 'Entrada'),
        ('OUT', 'Salida'),
        ('SALE', 'Venta'),  # ✅ Agregar tipo de movimiento para ventas
        ('TRANSFER_OUT', 'Transferencia Salida'),
        ('TRANSFER_IN', 'Transferencia Entrada'),
    )

    inventory = models.ForeignKey(Inventory, on_delete=models.CASCADE, related_name='movements')
    quantity = models.DecimalField(max_digits=10, decimal_places=3)  # ✅ Cambiado a DecimalField
    movement_type = models.CharField(max_length=20, choices=MOVEMENT_TYPES)
    reference_id = models.IntegerField(null=True, blank=True)  # Para referenciar la transferencia
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.movement_type} - {self.quantity} kg"


class Transfer(models.Model):
    STATUS_CHOICES = (
        ('PENDING', 'Pendiente'),
        ('COMPLETED', 'Completada'),
        ('CANCELLED', 'Cancelada'),
    )
    
    from_branch = models.ForeignKey('branches.Branch', on_delete=models.CASCADE, related_name='transfers_out')
    to_branch = models.ForeignKey('branches.Branch', on_delete=models.CASCADE, related_name='transfers_in')
    created_by = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    def total_items(self):
        return self.items.count()
    
    def total_quantity(self):
        return sum(item.quantity for item in self.items.all())

    def __str__(self):
        return f"Transferencia #{self.id} ({self.from_branch} → {self.to_branch})"


class TransferItem(models.Model):
    transfer = models.ForeignKey(Transfer, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE)
    quantity = models.DecimalField(max_digits=10, decimal_places=3)  # ✅ Cambiado a DecimalField
    
    class Meta:
        unique_together = ('transfer', 'product')

    def __str__(self):
        return f"{self.product.name} - {self.quantity} kg"