from django.db import models
from django.conf import settings
from products.models import Product
from branches.models import Branch
from django.utils import timezone

class PurchasePrice(models.Model):
    """Historial de precios de compra por producto y sucursal"""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='purchase_prices')
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name='purchase_prices')
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Precio de compra")
    valid_from = models.DateTimeField(default=timezone.now, verbose_name="Válido desde")
    valid_to = models.DateTimeField(null=True, blank=True, verbose_name="Válido hasta")
    is_active = models.BooleanField(default=True, verbose_name="Activo")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True, verbose_name="Notas")

    class Meta:
        ordering = ['-valid_from']
        verbose_name = "Precio de compra"
        verbose_name_plural = "Precios de compra"
        indexes = [
            models.Index(fields=['product', 'branch', '-valid_from']),
        ]

    def __str__(self):
        return f"{self.product.name} - ${self.price} ({self.branch.name})"

    def save(self, *args, **kwargs):
        # Si este precio es activo, desactivar otros precios activos del mismo producto/sucursal
        if self.is_active:
            PurchasePrice.objects.filter(
                product=self.product,
                branch=self.branch,
                is_active=True
            ).exclude(pk=self.pk).update(
                is_active=False,
                valid_to=timezone.now()
            )
        super().save(*args, **kwargs)


class ProfitSummary(models.Model):
    """Resumen de ganancias por período"""
    PERIOD_CHOICES = (
        ('daily', 'Diario'),
        ('weekly', 'Semanal'),
        ('monthly', 'Mensual'),
        ('yearly', 'Anual'),
    )
    
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name='profit_summaries')
    period = models.CharField(max_length=20, choices=PERIOD_CHOICES)
    date = models.DateField()  # Fecha del período (para diario es la fecha, para mensual es primer día del mes)
    
    # Totales
    total_sales = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_profit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    avg_margin = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    # Estadísticas
    total_transactions = models.IntegerField(default=0)
    total_items_sold = models.IntegerField(default=0)
    
    # Metadatos
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date']
        unique_together = ['branch', 'period', 'date']
        verbose_name = "Resumen de ganancias"
        verbose_name_plural = "Resúmenes de ganancias"

    def __str__(self):
        return f"{self.branch.name} - {self.get_period_display()} {self.date}"


class ProductProfitability(models.Model):
    """Rentabilidad por producto"""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='profitability')
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name='product_profitability')
    date = models.DateField()  # Fecha del análisis
    
    # Estadísticas
    units_sold = models.IntegerField(default=0)
    revenue = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    profit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    margin = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    # Precios promedio
    avg_sale_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    avg_cost_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    class Meta:
        ordering = ['-date', '-profit']
        unique_together = ['product', 'branch', 'date']
        verbose_name = "Rentabilidad de producto"
        verbose_name_plural = "Rentabilidad de productos"

    def __str__(self):
        return f"{self.product.name} - {self.date}"