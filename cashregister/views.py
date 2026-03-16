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
from django.contrib.admin.views.decorators import staff_member_required
from branches.models import Branch
from django.db.models import Sum, Count, Q
from django.utils.dateparse import parse_date

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
    
    # Obtener ventas del corte (solo activas)
    ventas = corte.ventas.filter(status='ACTIVE')
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
    
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)
    
    try:
        # Parsear JSON
        if not request.body:
            return JsonResponse({'error': 'Cuerpo de la petición vacío'}, status=400)
        
        data = json.loads(request.body)
        monto_real = data.get('monto_real')
        
        if monto_real is None:
            return JsonResponse({'error': 'El campo monto_real es requerido'}, status=400)
        
        try:
            monto_real = Decimal(str(monto_real))
        except:
            return JsonResponse({'error': 'El monto_real debe ser un número válido'}, status=400)
        
        observaciones = data.get('observaciones', '')
        
        # Obtener el corte
        corte = get_object_or_404(
            CorteCaja, 
            id=corte_id, 
            branch=request.user.branch,
            cajero=request.user,
            estado='ABIERTO'
        )
        
        # Obtener SOLO ventas ACTIVAS desde la apertura del corte
        ventas_a_cerrar = Sale.objects.filter(
            Q(status='ACTIVE') & (
                Q(branch=request.user.branch, cashier=request.user, created_at__gte=corte.fecha_apertura) |
                Q(branch=request.user.branch, cashier=request.user, cortes__isnull=True, created_at__lt=corte.fecha_apertura)
            )
        ).distinct().order_by('created_at')
        
        # Calcular total de ventas (solo activas)
        total_sistema = Decimal('0')
        for venta in ventas_a_cerrar:
            total_sistema += venta.total
        
        # Calcular total esperado (monto inicial + ventas activas)
        total_esperado = corte.monto_inicial + total_sistema
        diferencia = monto_real - total_esperado
        
        # Asignar las ventas al corte
        for venta in ventas_a_cerrar:
            venta.cortes.add(corte)
        
        # Actualizar corte
        corte.fecha_cierre = timezone.now()
        corte.total_ventas = total_sistema
        corte.monto_final_sistema = total_esperado
        corte.monto_final_real = monto_real
        corte.diferencia = diferencia
        corte.observaciones = observaciones
        corte.estado = 'CERRADO'
        corte.save()
        
        return JsonResponse({
            'success': True,
            'message': f'Corte de caja cerrado correctamente. {ventas_a_cerrar.count()} ventas procesadas.',
            'total_sistema': float(total_esperado),
            'total_real': float(monto_real),
            'diferencia': float(diferencia),
            'cantidad_ventas': ventas_a_cerrar.count()
        })
        
    except json.JSONDecodeError as e:
        return JsonResponse({'error': f'JSON inválido: {str(e)}'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

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
        
        if corte.estado == 'ABIERTO':
            # Para corte abierto: ventas desde apertura y sin asignar
            ventas = Sale.objects.filter(
                Q(status='ACTIVE') & (
                    Q(branch=request.user.branch, cashier=request.user, created_at__gte=corte.fecha_apertura) |
                    Q(branch=request.user.branch, cashier=request.user, cortes__isnull=True, created_at__lt=corte.fecha_apertura)
                )
            ).distinct()
        else:
            # Para corte cerrado: ventas ya asignadas
            ventas = corte.ventas.all()
        
        total = Decimal('0')
        for venta in ventas:
            total += venta.total
        
        cantidad = ventas.count()
        
        return JsonResponse({
            'corte_id': corte.id,
            'estado': corte.estado,
            'fecha_apertura': corte.fecha_apertura.strftime('%d/%m/%Y %H:%M'),
            'monto_inicial': float(corte.monto_inicial),
            'total_ventas': float(total),
            'cantidad_ventas': cantidad,
            'total_esperado': float(corte.monto_inicial + total)
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
    
    # ✅ CORREGIDO: Usar Q(status='ACTIVE') & con paréntesis correctos
    ventas_totales = Sale.objects.filter(
        Q(status='ACTIVE') & (
            Q(branch=request.user.branch, cashier=request.user, created_at__gte=corte.fecha_apertura) |
            Q(branch=request.user.branch, cashier=request.user, cortes__isnull=True, created_at__lt=corte.fecha_apertura)
        )
    ).distinct().order_by('created_at')
    
    total_ventas = sum(venta.total for venta in ventas_totales)
    cantidad_ventas = ventas_totales.count()
    
    # Calcular total esperado (monto inicial + ventas)
    total_esperado = corte.monto_inicial + total_ventas
    
    return render(request, 'cajero/cashregister/contar_dinero.html', {
        'corte': corte,
        'total_ventas_hoy': total_ventas,
        'cantidad_ventas': cantidad_ventas,
        'total_esperado': total_esperado,
        'ventas': ventas_totales[:10]  # Solo últimas 10 para el template
    })

@staff_member_required
def admin_cortes_list(request):
    """Vista de administrador para ver todos los cortes de caja"""
    if not request.user.is_staff:
        messages.error(request, "No tienes permiso para acceder a esta página.")
        return redirect('no_permission')
    
    # Obtener filtros de la URL
    sucursal_id = request.GET.get('sucursal', '')
    fecha_desde = request.GET.get('desde', '')
    fecha_hasta = request.GET.get('hasta', '')
    estado = request.GET.get('estado', '')
    
    # Base queryset con optimización de consultas
    cortes = CorteCaja.objects.select_related(
        'branch', 'cajero'
    ).prefetch_related('ventas').order_by('-fecha_apertura')
    
    # Aplicar filtros
    if sucursal_id:
        cortes = cortes.filter(branch_id=sucursal_id)
    
    if estado:
        cortes = cortes.filter(estado=estado)
    
    if fecha_desde:
        fecha_desde_parsed = parse_date(fecha_desde)
        if fecha_desde_parsed:
            cortes = cortes.filter(fecha_apertura__date__gte=fecha_desde_parsed)
    
    if fecha_hasta:
        fecha_hasta_parsed = parse_date(fecha_hasta)
        if fecha_hasta_parsed:
            cortes = cortes.filter(fecha_apertura__date__lte=fecha_hasta_parsed)
    
    # Estadísticas globales
    estadisticas = {
        'total_cortes': cortes.count(),
        'total_ventas': sum(corte.total_ventas for corte in cortes),
        'total_diferencia': sum(corte.diferencia for corte in cortes),
        'cortes_abiertos': cortes.filter(estado='ABIERTO').count(),
        'cortes_cerrados': cortes.filter(estado='CERRADO').count(),
    }
    
    # Resumen por sucursal
    sucursales_data = []
    for sucursal in Branch.objects.filter(is_active=True):
        cortes_sucursal = cortes.filter(branch=sucursal)
        if cortes_sucursal.exists():
            sucursales_data.append({
                'id': sucursal.id,
                'nombre': sucursal.name,
                'total_cortes': cortes_sucursal.count(),
                'total_ventas': sum(c.total_ventas for c in cortes_sucursal),
                'total_diferencia': sum(c.diferencia for c in cortes_sucursal),
                'abiertos': cortes_sucursal.filter(estado='ABIERTO').count(),
                'cerrados': cortes_sucursal.filter(estado='CERRADO').count(),
            })
    
    # Estadísticas por mes (para gráfica)
    meses_data = []
    from collections import defaultdict
    from calendar import month_name
    
    ventas_por_mes = defaultdict(Decimal)
    cortes_por_mes = defaultdict(int)
    
    for corte in cortes:
        mes = corte.fecha_apertura.strftime('%Y-%m')
        ventas_por_mes[mes] += corte.total_ventas
        cortes_por_mes[mes] += 1
    
    for mes in sorted(ventas_por_mes.keys()):
        año, mes_num = mes.split('-')
        nombre_mes = month_name[int(mes_num)]
        meses_data.append({
            'mes': f"{nombre_mes} {año}",
            'ventas': float(ventas_por_mes[mes]),
            'cortes': cortes_por_mes[mes]
        })
    
    return render(request, 'admin/cashregister/list.html', {
        'cortes': cortes[:50],  # Limitamos a 50 para rendimiento
        'sucursales': Branch.objects.filter(is_active=True),
        'estados': CorteCaja.ESTADO_CHOICES,
        'filtros': {
            'sucursal': sucursal_id,
            'desde': fecha_desde,
            'hasta': fecha_hasta,
            'estado': estado,
        },
        'estadisticas': estadisticas,
        'sucursales_data': sucursales_data,
        'meses_data': meses_data,
    })

@staff_member_required
def admin_corte_detail(request, corte_id):
    """Vista de administrador para ver detalle de un corte específico"""
    if not request.user.is_staff:
        messages.error(request, "No tienes permiso para acceder a esta página.")
        return redirect('no_permission')
    
    corte = get_object_or_404(
        CorteCaja.objects.select_related('branch', 'cajero'),
        id=corte_id
    )
    
    # Obtener ventas del corte con sus items
    ventas = corte.ventas.all().prefetch_related('items__product').order_by('-created_at')
    
    # Estadísticas detalladas
    total_ventas = sum(venta.total for venta in ventas)
    
    # Agrupar ventas por hora
    ventas_por_hora = {}
    for venta in ventas:
        hora = venta.created_at.strftime('%H:00')
        if hora not in ventas_por_hora:
            ventas_por_hora[hora] = {'cantidad': 0, 'total': Decimal('0')}
        ventas_por_hora[hora]['cantidad'] += 1
        ventas_por_hora[hora]['total'] += venta.total
    
    ventas_por_hora = [{'hora': k, 'cantidad': v['cantidad'], 'total': float(v['total'])} 
                      for k, v in sorted(ventas_por_hora.items())]
    
    return render(request, 'admin/cashregister/detail.html', {
        'corte': corte,
        'ventas': ventas,
        'total_ventas': total_ventas,
        'ventas_por_hora': ventas_por_hora,
    })

@staff_member_required
def admin_corte_export(request, corte_id):
    """Exportar corte a PDF/Excel (opcional)"""
    if not request.user.is_staff:
        return JsonResponse({'error': 'No autorizado'}, status=403)
    
    # Aquí puedes implementar la exportación a PDF o Excel
    # Por ahora solo respondemos que está en desarrollo
    return JsonResponse({'message': 'Funcionalidad en desarrollo'}, status=200)