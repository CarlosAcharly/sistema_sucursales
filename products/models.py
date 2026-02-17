from django.db import models

class Product(models.Model):
    name = models.CharField(max_length=150)
    barcode = models.CharField(max_length=100, unique=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=True)
    is_ingredient = models.BooleanField(default=False)


    def __str__(self):
        return self.name
