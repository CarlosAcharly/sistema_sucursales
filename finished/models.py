# finished/models.py
from django.db import models
from django.conf import settings
from django.db.models import Sum
from django.utils import timezone


class FinishedRecipe(models.Model):
    """Receta de producto terminado"""
    name = models.CharField(max_length=150, verbose_name="Nombre de la receta")
    description = models.TextField(blank=True, verbose_name="Descripción")
    
    # Producto terminado que se genera
    finished_product = models.OneToOneField(
        'products.Product',
        on_delete=models.PROTECT,
        related_name='recipe',
        limit_choices_to={'is_finished': True}
    )
    
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    
    # Soft delete
    deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = "Receta"
        verbose_name_plural = "Recetas"
        ordering = ['name']
    
    def total_kg(self):
        """Total de kilos de ingredientes necesarios para una unidad"""
        total = self.ingredients.aggregate(total=Sum('kilos'))['total'] or 0
        return float(total)
    
    def ingredients_count(self):
        return self.ingredients.count()
    
    def soft_delete(self):
        self.deleted = True
        self.is_active = False
        self.deleted_at = timezone.now()
        self.save()
    
    def restore(self):
        self.deleted = False
        self.is_active = True
        self.deleted_at = None
        self.save()
    
    def __str__(self):
        return self.name


class FinishedRecipeIngredient(models.Model):
    """Ingredientes de una receta"""
    recipe = models.ForeignKey(
        FinishedRecipe,
        on_delete=models.CASCADE,
        related_name='ingredients'
    )
    product = models.ForeignKey(
        'products.Product',
        on_delete=models.CASCADE,
        limit_choices_to={'is_ingredient': True}
    )
    kilos = models.DecimalField(max_digits=10, decimal_places=3, verbose_name="Cantidad (kg)")
    
    class Meta:
        unique_together = ('recipe', 'product')
        verbose_name = "Ingrediente de receta"
        verbose_name_plural = "Ingredientes de receta"
    
    def __str__(self):
        return f"{self.product.name} - {self.kilos} kg"


class FinishedProduction(models.Model):
    """Registro de producción de producto terminado"""
    recipe = models.ForeignKey(
        FinishedRecipe,
        on_delete=models.CASCADE,
        related_name='productions'
    )
    branch = models.ForeignKey(
        'branches.Branch',
        on_delete=models.CASCADE
    )
    produced_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True
    )
    quantity = models.DecimalField(
        max_digits=14,
        decimal_places=3,
        verbose_name="Cantidad producida (kg)"
    )
    notes = models.TextField(blank=True, verbose_name="Notas")
    produced_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-produced_at']
        verbose_name = "Producción"
        verbose_name_plural = "Producciones"
    
    def __str__(self):
        return f"{self.recipe.name} - {self.quantity} kg - {self.branch.name}"