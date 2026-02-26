from django.contrib import admin
from .models import CorteCaja

@admin.register(CorteCaja)
class CorteCajaAdmin(admin.ModelAdmin):
    list_display = ['id', 'branch', 'cajero', 'fecha_apertura', 'fecha_cierre', 'total_ventas', 'diferencia', 'estado']
    list_filter = ['estado', 'branch', 'fecha_apertura']
    search_fields = ['id', 'cajero__username', 'branch__name']
    readonly_fields = ['created_at', 'updated_at']