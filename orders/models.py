from django.db import models
from django.conf import settings
from branches.models import Branch
from products.models import Product
from django.db.models import Sum


class Order(models.Model):
    STATUS_CHOICES = (
        ("PENDING", "Pendiente"),
        ("APPROVED", "Aprobado"),
        ("COMPLETED", "Completado"),
        ("CANCELLED", "Cancelado"),
    )

    branch = models.ForeignKey(
        Branch,
        on_delete=models.CASCADE,
        related_name="orders"
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="PENDING"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    
    # Nuevo campo para tracking de inventario
    inventory_added = models.BooleanField(
        default=False,
        help_text="Indica si los productos de este pedido ya fueron agregados al inventario"
    )

    def total_kilos(self):
        """Calcula la suma de todos los kilos de los items del pedido"""
        total = self.items.aggregate(total=Sum('kilos'))['total']
        return float(total) if total else 0
    
    def items_count(self):
        """Retorna la cantidad de productos en el pedido"""
        return self.items.count()

    def __str__(self):
        return f"Pedido #{self.id} - {self.branch.name}"


class OrderItem(models.Model):
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="items"
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE
    )

    kilos = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    def __str__(self):
        return f"{self.product.name} - {self.kilos} kg"