from django.db import models

class Branch(models.Model):
    name = models.CharField(max_length=100)
    address = models.TextField()
    is_active = models.BooleanField(default=True)
    can_transfer = models.BooleanField(
        default=False, 
        verbose_name="Puede hacer transferencias",
        help_text="Permite a los cajeros de esta sucursal realizar transferencias de productos"
    )

    def __str__(self):
        return self.name