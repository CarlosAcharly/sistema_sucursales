from django.db import models
from django.conf import settings
from branches.models import Branch
from sales.models import Sale
from django.utils import timezone

class CorteCaja(models.Model):
    ESTADO_CHOICES = (
        ('ABIERTO', 'Abierto'),
        ('CERRADO', 'Cerrado'),
    )
    
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name='cortes')
    cajero = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    fecha_apertura = models.DateTimeField(default=timezone.now)
    fecha_cierre = models.DateTimeField(null=True, blank=True)
    monto_inicial = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Totales calculados
    total_ventas = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_efectivo = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_tarjeta = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_transferencia = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Diferencias
    monto_final_sistema = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    monto_final_real = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    diferencia = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    observaciones = models.TextField(blank=True)
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='ABIERTO')
    
    # Ventas incluidas en este corte
    ventas = models.ManyToManyField(Sale, related_name='cortes')
    
    # Metadatos
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-fecha_apertura']
        verbose_name = 'Corte de Caja'
        verbose_name_plural = 'Cortes de Caja'
    
    def __str__(self):
        return f"Corte #{self.id} - {self.branch.name} - {self.fecha_apertura.strftime('%d/%m/%Y')}"
    
    def duracion(self):
        if self.fecha_cierre:
            delta = self.fecha_cierre - self.fecha_apertura
            horas = delta.seconds // 3600
            minutos = (delta.seconds % 3600) // 60
            return f"{horas}h {minutos}m"
        return "En curso"
    
    def calcular_totales(self):
        """Calcula los totales de ventas asociadas a este corte"""
        total = 0
        efectivo = 0
        tarjeta = 0
        transferencia = 0
        
        for venta in self.ventas.all():
            total += venta.total
            # Como no tenemos método de pago, asumimos todo en efectivo
            # Esto lo puedes ajustar después
            efectivo += venta.total
        
        return {
            'total': total,
            'efectivo': efectivo,
            'tarjeta': tarjeta,
            'transferencia': transferencia,
        }