from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db import transaction
from django.http import JsonResponse
from sales.models import Sale
from .models import CorteCaja
from decimal import Decimal
import json

@login_required
def cortes_list(request):
    """Lista de cortes de caja del cajero"""
    if request.user.role != 'CASHIER':
        messages.error(request, "No tienes permiso para acceder a esta página.")
        return redirect('no_permission')
    
    cortes = CorteCaja.objects.filter(
        branch=request.user.branch,
        cajero=request.user
    ).order_by('-fecha_apertura')
    
    # Calcular conteos por estado
    cortes_con_estado = {
        'ABIERTO': cortes.filter(estado='ABIERTO').count(),
        'CERRADO': cortes.filter(estado='CERRADO').count(),
    }
    
    # Verificar si hay un corte abierto
    corte_activo = cortes.filter(estado='ABIERTO').first()
    
    return render(request, 'cajero/cashregister/list.html', {
        'cortes': cortes,
        'cortes_con_estado': cortes_con_estado,
        'corte_activo': corte_activo
    })

@login_required
def iniciar_corte(request):
    """Iniciar un nuevo corte de caja"""
    if request.user.role != 'CASHIER':
        return JsonResponse({'error': 'No autorizado'}, status=403)
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            monto_inicial = Decimal(str(data.get('monto_inicial', 0)))
            
            # Verificar si ya hay un corte abierto
            corte_activo = CorteCaja.objects.filter(
                branch=request.user.branch,
                cajero=request.user,
                estado='ABIERTO'
            ).first()
            
            if corte_activo:
                return JsonResponse({'error': 'Ya tienes un corte de caja abierto'}, status=400)
            
            # Crear nuevo corte
            corte = CorteCaja.objects.create(
                branch=request.user.branch,
                cajero=request.user,
                monto_inicial=monto_inicial,
                estado='ABIERTO'
            )
            
            return JsonResponse({
                'success': True,
                'corte_id': corte.id,
                'message': 'Corte de caja iniciado correctamente'
            })
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    
    return JsonResponse({'error': 'Método no permitido'}, status=405)

@login_required
def detalle_corte(request, corte_id):
    """Ver detalles de un corte específico"""
    if request.user.role != 'CASHIER':
        messages.error(request, "No tienes permiso para acceder a esta página.")
        return redirect('no_permission')
    
    corte = get_object_or_404(
        CorteCaja, 
        id=corte_id, 
        branch=request.user.branch,
        cajero=request.user
    )
    
    # Calcular totales
    ventas = corte.ventas.all()
    total_ventas = sum(venta.total for venta in ventas)
    cantidad_ventas = ventas.count()
    
    return render(request, 'cajero/cashregister/detail.html', {
        'corte': corte,
        'ventas': ventas,
        'total_ventas': total_ventas,
        'cantidad_ventas': cantidad_ventas
    })

@login_required
@transaction.atomic
def cerrar_corte(request, corte_id):
    """Cerrar un corte de caja"""
    if request.user.role != 'CASHIER':
        return JsonResponse({'error': 'No autorizado'}, status=403)
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            monto_real = Decimal(str(data.get('monto_real', 0)))
            observaciones = data.get('observaciones', '')
            
            corte = get_object_or_404(
                CorteCaja, 
                id=corte_id, 
                branch=request.user.branch,
                cajero=request.user,
                estado='ABIERTO'
            )
            
            # Obtener ventas desde el último corte
            ultimo_corte = CorteCaja.objects.filter(
                branch=request.user.branch,
                cajero=request.user,
                estado='CERRADO'
            ).order_by('-fecha_cierre').first()
            
            fecha_desde = ultimo_corte.fecha_cierre if ultimo_corte else timezone.now().replace(hour=0, minute=0, second=0)
            
            # Obtener ventas realizadas desde entonces
            ventas = Sale.objects.filter(
                branch=request.user.branch,
                cashier=request.user,
                created_at__gte=fecha_desde,
                created_at__lte=timezone.now()
            )
            
            # Calcular totales usando Decimal
            total_sistema = Decimal('0')
            for venta in ventas:
                total_sistema += venta.total
            
            diferencia = monto_real - total_sistema
            
            # Actualizar corte
            corte.fecha_cierre = timezone.now()
            corte.total_ventas = total_sistema
            corte.monto_final_sistema = total_sistema
            corte.monto_final_real = monto_real
            corte.diferencia = diferencia
            corte.observaciones = observaciones
            corte.estado = 'CERRADO'
            corte.ventas.set(ventas)
            corte.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Corte de caja cerrado correctamente',
                'total_sistema': float(total_sistema),
                'total_real': float(monto_real),
                'diferencia': float(diferencia)
            })
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    
    return JsonResponse({'error': 'Método no permitido'}, status=405)

@login_required
def resumen_corte_api(request, corte_id):
    """API para obtener resumen del corte en tiempo real"""
    if request.user.role != 'CASHIER':
        return JsonResponse({'error': 'No autorizado'}, status=403)
    
    try:
        corte = get_object_or_404(
            CorteCaja, 
            id=corte_id, 
            branch=request.user.branch,
            cajero=request.user
        )
        
        # Calcular ventas del día
        ventas_hoy = Sale.objects.filter(
            branch=request.user.branch,
            cashier=request.user,
            created_at__date=timezone.now().date()
        )
        
        total_hoy = Decimal('0')
        for venta in ventas_hoy:
            total_hoy += venta.total
        
        cantidad_hoy = ventas_hoy.count()
        
        return JsonResponse({
            'corte_id': corte.id,
            'estado': corte.estado,
            'fecha_apertura': corte.fecha_apertura.strftime('%d/%m/%Y %H:%M'),
            'monto_inicial': float(corte.monto_inicial),
            'total_hoy': float(total_hoy),
            'cantidad_ventas_hoy': cantidad_hoy
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)
    
@login_required
def contar_dinero(request, corte_id):
    """Vista para que el cajero cuente el dinero físico"""
    if request.user.role != 'CASHIER':
        messages.error(request, "No tienes permiso para acceder a esta página.")
        return redirect('no_permission')
    
    corte = get_object_or_404(
        CorteCaja, 
        id=corte_id, 
        branch=request.user.branch,
        cajero=request.user,
        estado='ABIERTO'
    )
    
    # Obtener ventas del día para mostrar
    ventas_hoy = Sale.objects.filter(
        branch=request.user.branch,
        cashier=request.user,
        created_at__date=timezone.now().date()
    )
    
    total_ventas_hoy = sum(venta.total for venta in ventas_hoy)
    cantidad_ventas = ventas_hoy.count()
    
    # Calcular total esperado (monto inicial + ventas)
    total_esperado = corte.monto_inicial + total_ventas_hoy
    
    return render(request, 'cajero/cashregister/contar_dinero.html', {
        'corte': corte,
        'total_ventas_hoy': total_ventas_hoy,
        'cantidad_ventas': cantidad_ventas,
        'total_esperado': total_esperado
    })