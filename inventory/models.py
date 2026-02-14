from django.db import models


class Inventory(models.Model):
    branch = models.ForeignKey(
        'branches.Branch',
        on_delete=models.CASCADE
    )
    product = models.ForeignKey(
        'products.Product',
        on_delete=models.CASCADE
    )
    stock = models.IntegerField(default=0)

    class Meta:
        unique_together = ('branch', 'product')

    def __str__(self):
        return f"{self.product.name} - {self.branch.name}"


class InventoryMovement(models.Model):

    MOVEMENT_TYPES = (
        ('IN', 'Entrada'),
        ('OUT', 'Salida'),
    )

    inventory = models.ForeignKey(
        Inventory,
        on_delete=models.CASCADE,
        related_name='movements'
    )

    quantity = models.IntegerField()
    movement_type = models.CharField(max_length=10, choices=MOVEMENT_TYPES)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.movement_type} - {self.quantity}"

class Transfer(models.Model):

    from_branch = models.ForeignKey(
        'branches.Branch',
        on_delete=models.CASCADE,
        related_name='transfers_out'
    )

    to_branch = models.ForeignKey(
        'branches.Branch',
        on_delete=models.CASCADE,
        related_name='transfers_in'
    )

    product = models.ForeignKey(
        'products.Product',
        on_delete=models.CASCADE
    )

    quantity = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    created_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True
    )

    def __str__(self):
        return f"{self.product.name} ({self.from_branch} → {self.to_branch})"
