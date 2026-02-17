from django.db import models
from django.conf import settings
from branches.models import Branch
from products.models import Product
from django.core.exceptions import ValidationError
from django.db.models import Sum

# Dieta base (creada por admin)
class Diet(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True
    )
    branches = models.ManyToManyField(Branch, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def total_base_kilos(self):
        total = self.base_ingredients.aggregate(total=Sum('kilos'))['total']
        return total or 0

    def clean(self):
        if self.pk and self.total_base_kilos() != 1000:
            raise ValidationError("La suma de los ingredientes debe ser exactamente 1000 kg.")

    def __str__(self):
        return self.name


class DietBaseIngredient(models.Model):
    diet = models.ForeignKey(
        Diet,
        on_delete=models.CASCADE,
        related_name="base_ingredients"
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        limit_choices_to={'is_ingredient': True}
    )
    kilos = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        unique_together = ('diet', 'product')

    def __str__(self):
        return f"{self.product.name} - {self.kilos} kg"


# Dieta flexible para cajero
class DietCajero(models.Model):
    diet_base = models.ForeignKey(
        Diet,
        on_delete=models.CASCADE,
        related_name='flex_diets'
    )
    branch = models.ForeignKey(
        Branch,
        on_delete=models.CASCADE,
        related_name='diets_cajero'
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.diet_base.name} - {self.branch.name}"


class DietCajeroItem(models.Model):
    diet = models.ForeignKey(
        DietCajero,
        on_delete=models.CASCADE,
        related_name='items'
    )
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    kilos = models.FloatField(default=0)  # Editable por cajero

    class Meta:
        unique_together = ('diet', 'product')

    def __str__(self):
        return f"{self.product.name} - {self.kilos} kg"
