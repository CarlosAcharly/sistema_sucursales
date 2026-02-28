from django.db import models

class Product(models.Model):
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True, verbose_name="Descripción")  # Cambiamos barcode por description
    # Precios
    price_kg = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Precio por Kg")
    price_bulk = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Precio por Bulto")
    price_wholesale = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Precio Mayoreo")
    price_special = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Precio Especial")
    
    is_active = models.BooleanField(default=True, verbose_name="Activo")
    is_ingredient = models.BooleanField(default=False, verbose_name="Es ingrediente")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de creación")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Última actualización")

    class Meta:
        verbose_name = "Producto"
        verbose_name_plural = "Productos"
        ordering = ['name']

    def __str__(self):
        return self.name
    
    def get_first_available_price(self):
        """Retorna el primer precio disponible (prioridad: kg, bulto, mayoreo, especial)"""
        if self.price_kg:
            return self.price_kg
        if self.price_bulk:
            return self.price_bulk
        if self.price_wholesale:
            return self.price_wholesale
        if self.price_special:
            return self.price_special
        return None
    
    def has_any_price(self):
        """Verifica si el producto tiene al menos un precio configurado"""
        return any([self.price_kg, self.price_bulk, self.price_wholesale, self.price_special])