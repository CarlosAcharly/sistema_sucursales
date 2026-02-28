from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class Sale(models.Model):
    branch = models.ForeignKey('branches.Branch', on_delete=models.CASCADE)
    cashier = models.ForeignKey(User, on_delete=models.CASCADE)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

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
    quantity = models.IntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    price_type = models.CharField(max_length=20, choices=PRICE_TYPE_CHOICES, default='kg')

    def subtotal(self):
        return self.quantity * self.price
    
    def __str__(self):
        return f"{self.product.name} x{self.quantity} ({self.get_price_type_display()})"