from django.db import models

class Branch(models.Model):
    name = models.CharField(max_length=100)
    address = models.TextField()
    phone = models.CharField(
        max_length=20, 
        blank=True, 
        verbose_name="Teléfono",
        help_text="Número de teléfono de la sucursal (ej: 55 1234 5678)"
    )
    is_active = models.BooleanField(default=True)
    can_transfer = models.BooleanField(
        default=False, 
        verbose_name="Puede hacer transferencias",
        help_text="Permite a los cajeros de esta sucursal realizar transferencias de productos"
    )
    can_manage_finished = models.BooleanField(  # ✅ NUEVO CAMPO
        default=False,
        verbose_name="Puede gestionar productos terminados",
        help_text="Permite a los cajeros de esta sucursal preparar productos terminados a partir de recetas"
    )

    def __str__(self):
        return self.name