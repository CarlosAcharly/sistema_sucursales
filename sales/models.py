from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class Sale(models.Model):
    STATUS_CHOICES = (
        ('ACTIVE', 'Activa'),
        ('CANCELLED', 'Cancelada'),
    )
    
    PAYMENT_CHOICES = (
        ('CASH', 'Efectivo'),
        ('TRANSFER', 'Transferencia'),
    )
    
    branch = models.ForeignKey('branches.Branch', on_delete=models.CASCADE)
    cashier = models.ForeignKey(User, on_delete=models.CASCADE)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ACTIVE')
    payment_method = models.CharField(max_length=20, choices=PAYMENT_CHOICES, default='CASH')  # ✅ NUEVO CAMPO
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancelled_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='cancelled_sales')
    cancellation_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    cliente_nombre = models.CharField(max_length=200, blank=True, default='Cliente Mostrador', verbose_name="Nombre del cliente")
    cliente_direccion = models.CharField(max_length=500, blank=True, verbose_name="Dirección")
    cliente_telefono = models.CharField(max_length=50, blank=True, verbose_name="Teléfono")

    def __str__(self):
        return f"Venta #{self.id} - {self.branch}"
    
    def items_count(self):
        return self.items.count()
    
class SaleItem(models.Model):
    PRICE_TYPE_CHOICES = (
        ('kg', 'Por Kg'),
        ('bulk', 'Por Bulto'),
        ('wholesale', 'Mayoreo'),
        ('special', 'Especial'),
    )
    
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE)
    quantity = models.DecimalField(max_digits=10, decimal_places=3, verbose_name="Cantidad")
    price = models.DecimalField(max_digits=10, decimal_places=2)
    price_type = models.CharField(max_length=20, choices=PRICE_TYPE_CHOICES, default='kg')

    def subtotal(self):
        return self.quantity * self.price
    
    def __str__(self):
        return f"{self.product.name} x{self.quantity} ({self.get_price_type_display()})"