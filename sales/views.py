from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from users.decorators import role_required
from inventory.models import Inventory, InventoryMovement
from .models import Sale, SaleItem
from products.models import Product
from django.utils.timezone import now
from django.db.models import Sum, Count
import json
from django.http import JsonResponse
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
import logging
import traceback
from branches.models import Branch
import pytz  # Asegúrate de tener pytz instalado


logger = logging.getLogger(__name__)


# =============================
# 🧑‍💼 CAJERO
# =============================

# sales/views.py - Modificar la parte de creación de la venta
@login_required
@role_required(['CASHIER'])
@transaction.atomic
def pos_view(request):
    branch = request.user.branch
    inventory = Inventory.objects.filter(
        branch=branch,
        stock__gt=0
    ).select_related('product')

    if request.method == 'POST':
        data = json.loads(request.body)
        cart = data.get('cart', [])
        cliente_data = data.get('cliente', {})
        payment_method = data.get('payment_method', 'CASH')  # ✅ Obtener método de pago

        if not cart:
            return JsonResponse({'error': 'Carrito vacío'}, status=400)

        sale = Sale.objects.create(
            branch=branch,
            cashier=request.user,
            total=0,
            cliente_nombre=cliente_data.get('nombre', 'Cliente Mostrador'),
            cliente_direccion=cliente_data.get('direccion', ''),
            cliente_telefono=cliente_data.get('telefono', ''),
            payment_method=payment_method  # ✅ Guardar método de pago
        )

        total_sale = Decimal('0')

        for item in cart:
            product_id = item['id']
            quantity = Decimal(str(item['quantity'])) 
            price_type = item.get('price_type', 'kg')

            inventory_item = Inventory.objects.filter(
                branch=branch,
                product_id=product_id
            ).first()

            if not inventory_item:
                transaction.set_rollback(True)
                return JsonResponse({'error': f'Producto no encontrado en inventario'}, status=400)
            
            if inventory_item.stock < quantity:
                transaction.set_rollback(True)
                return JsonResponse({
                    'error': f'Stock insuficiente para {inventory_item.product.name}. Disponible: {inventory_item.stock} kg, solicitado: {quantity} kg'
                }, status=400)

            price = Decimal(str(item['price']))
            subtotal = price * quantity
            total_sale += subtotal

            SaleItem.objects.create(
                sale=sale,
                product=inventory_item.product,
                quantity=quantity,
                price=price,
                price_type=price_type
            )

            inventory_item.stock -= quantity
            inventory_item.save()

            InventoryMovement.objects.create(
                inventory=inventory_item,
                quantity=-quantity,
                movement_type='SALE'
            )

        sale.total = total_sale
        sale.save()

        return JsonResponse({
            'success': True,
            'venta_id': sale.id
        })

    return render(request, 'cajero/pos.html', {
        'inventory': inventory
    })
@login_required
@role_required(['CASHIER'])
def sales_list(request):
    branch = request.user.branch
    
    # Obtener la fecha actual en la zona horaria local
    local_tz = timezone.get_current_timezone()
    now_local = timezone.localtime(timezone.now())
    today = now_local.date()
    yesterday = today - timedelta(days=1)
    
    # Obtener todas las ventas de la sucursal
    sales = Sale.objects.filter(branch=branch).prefetch_related('items__product').order_by('-created_at')
    
    # Ventas de hoy (solo activas para estadísticas)
    sales_today_active = sales.filter(
        created_at__date=today, 
        status='ACTIVE'
    )
    sales_today_count = sales_today_active.count()
    total_today = sales_today_active.aggregate(total=Sum('total'))['total'] or Decimal('0')
    
    # Ventas de ayer (solo activas)
    sales_yesterday_active = Sale.objects.filter(
        branch=branch, 
        status='ACTIVE',
        created_at__date=yesterday
    )
    total_yesterday = sales_yesterday_active.aggregate(total=Sum('total'))['total'] or Decimal('0')
    
    # Calcular porcentaje de crecimiento
    if total_yesterday > 0:
        increase_today = total_today - total_yesterday
        sales_today_percent = ((total_today - total_yesterday) / total_yesterday) * 100
    else:
        increase_today = total_today
        sales_today_percent = 100 if total_today > 0 else 0
    
    # Calcular ticket promedio
    if sales_today_count > 0:
        average_ticket = total_today / sales_today_count
    else:
        average_ticket = Decimal('0')
    
    # Total general de ventas (solo activas)
    total_sum = sales.filter(status='ACTIVE').aggregate(total=Sum('total'))['total'] or Decimal('0')
    
    return render(request, 'cajero/sales_list.html', {
        'sales': sales,
        'sales_today': sales_today_count,
        'total_today': total_today,
        'increase_today': increase_today,
        'sales_today_percent': round(sales_today_percent, 1),
        'average_ticket': average_ticket,
        'total_sum': total_sum,
    })

@login_required
@role_required(['CASHIER'])
def cajero_dashboard(request):
    branch = request.user.branch
    today = now().date()

    sales_today = Sale.objects.filter(
        branch=branch,
        created_at__date=today
    )

    total_today = sales_today.aggregate(total=Sum('total'))['total'] or 0
    sales_today_count = sales_today.count()

    items_today = SaleItem.objects.filter(
        sale__branch=branch,
        sale__created_at__date=today
    ).aggregate(total=Sum('quantity'))['total'] or 0

    low_stock = Inventory.objects.filter(
        branch=branch,
        stock__lte=5
    ).select_related('product')[:10]

    # Calcular ventas de ayer para porcentaje
    yesterday = today - timedelta(days=1)
    sales_yesterday = Sale.objects.filter(
        branch=branch,
        created_at__date=yesterday
    ).aggregate(total=Sum('total'))['total'] or 0

    if sales_yesterday > 0:
        sales_today_percent = ((total_today - sales_yesterday) / sales_yesterday) * 100
    else:
        sales_today_percent = 100 if total_today > 0 else 0

    # Ticket promedio
    if sales_today_count > 0:
        average_ticket = total_today / sales_today_count
    else:
        average_ticket = 0

    # Últimas 5 ventas
    recent_sales = Sale.objects.filter(
        branch=branch
    ).prefetch_related('items').order_by('-created_at')[:5]

    return render(request, 'cajero/dashboard.html', {
        'total_today': total_today,
        'items_today': items_today,
        'low_stock': low_stock,
        'sales_today_count': sales_today_count,
        'sales_today_percent': round(sales_today_percent, 1),
        'average_ticket': average_ticket,
        'recent_sales': recent_sales,
        'today': today
    })


# sales/views.py - Agregar payment_method al JSON
@login_required
def sale_detail_api(request, sale_id):
    """API para obtener detalles de una venta"""
    try:
        sale = Sale.objects.prefetch_related('items__product').get(
            id=sale_id,
            branch=request.user.branch
        )
        
        items = []
        subtotal = 0
        
        for item in sale.items.all():
            quantity = float(item.quantity) if item.quantity else 0
            price = float(item.price) if item.price else 0
            item_subtotal = quantity * price
            subtotal += item_subtotal
            
            items.append({
                'id': item.id,
                'product_name': item.product.name,
                'quantity': quantity,
                'price': price,
                'price_type': item.price_type,
                'price_type_display': item.get_price_type_display(),
                'subtotal': item_subtotal
            })
        
        data = {
            'id': sale.id,
            'date': sale.created_at.strftime('%d/%m/%Y %H:%M'),
            'total': float(sale.total),
            'subtotal': subtotal,
            'cashier': sale.cashier.get_full_name() or sale.cashier.username,
            'branch': sale.branch.name,
            'items': items,
            'status': sale.status,
            'status_display': sale.get_status_display(),
            'payment_method': sale.payment_method,  # ✅ Agregar método de pago
            'payment_method_display': sale.get_payment_method_display(),  # ✅ Texto del método
            'cliente_nombre': sale.cliente_nombre,
            'cliente_direccion': sale.cliente_direccion,
            'cliente_telefono': sale.cliente_telefono
        }
        
        return JsonResponse(data)
        
    except Sale.DoesNotExist:
        return JsonResponse({'error': 'Venta no encontrada'}, status=404)
    except Exception as e:
        import traceback
        print(f"Error en sale_detail_api: {str(e)}")
        print(traceback.format_exc())
        return JsonResponse({'error': str(e)}, status=500)
    
    
# =============================
# 🧑‍💼 ADMINISTRADOR
# =============================

@login_required
@role_required(['ADMIN', 'SUPERADMIN'])
def admin_sales_list(request):
    """Lista de ventas para administradores con filtros por período"""
    user = request.user
    
    # Obtener filtros de período
    period = request.GET.get('period', 'all')
    selected_date = request.GET.get('date', '')
    selected_month = request.GET.get('month', '')
    selected_year = request.GET.get('year', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    # Base queryset
    sales = Sale.objects.select_related(
        'branch', 'cashier', 'cancelled_by'
    ).prefetch_related('items').all().order_by('-created_at')
    
    # Aplicar filtros de período
    if period == 'day' and selected_date:
        sales = sales.filter(created_at__date=selected_date)
        period_label = f"Día: {selected_date}"
    elif period == 'month' and selected_month:
        year, month = selected_month.split('-')
        sales = sales.filter(
            created_at__year=year,
            created_at__month=month
        )
        period_label = f"Mes: {selected_month}"
    elif period == 'year' and selected_year:
        sales = sales.filter(created_at__year=selected_year)
        period_label = f"Año: {selected_year}"
    elif period == 'range' and date_from and date_to:
        sales = sales.filter(
            created_at__date__gte=date_from,
            created_at__date__lte=date_to
        )
        period_label = f"Del {date_from} al {date_to}"
    else:
        period_label = "Todos los tiempos"
    
    # ✅ CORREGIDO: Ventas activas para estadísticas
    ventas_activas = sales.filter(status='ACTIVE')
    ventas_canceladas = sales.filter(status='CANCELLED')
    
    # Estadísticas del período
    total_sales = sales.count()  # Total general (para la tabla)
    total_ventas_activas = ventas_activas.count()
    total_amount = ventas_activas.aggregate(total=Sum('total'))['total'] or 0
    active_sales = ventas_activas.count()
    cancelled_sales = ventas_canceladas.count()  # ✅ CORREGIDO: Usar el queryset directamente
    
    # Ticket promedio (solo sobre ventas activas)
    average_ticket = total_amount / total_ventas_activas if total_ventas_activas > 0 else 0
    
    # Resumen por sucursal (solo ventas activas)
    branch_summary = ventas_activas.values(
        'branch__name'
    ).annotate(
        total_sales=Count('id'),
        total_amount=Sum('total'),
        active_count=Count('id')  # Todas son activas aquí
    ).order_by('branch__name')
    
    # Obtener canceladas por sucursal por separado
    canceladas_por_sucursal = ventas_canceladas.values(
        'branch__name'
    ).annotate(
        cancelled_count=Count('id')
    ).order_by('branch__name')
    
    # Combinar datos
    branch_data = {}
    
    # Primero, agregar activas
    for item in branch_summary:
        branch_data[item['branch__name']] = {
            'branch__name': item['branch__name'],
            'total_sales': item['total_sales'],
            'total_amount': item['total_amount'] or 0,
            'active_count': item['active_count'],
            'cancelled_count': 0,
            'avg_ticket': (item['total_amount'] / item['total_sales']) if item['total_sales'] > 0 else 0
        }
    
    # Luego, agregar canceladas
    for item in canceladas_por_sucursal:
        branch_name = item['branch__name']
        if branch_name in branch_data:
            branch_data[branch_name]['cancelled_count'] = item['cancelled_count']
            branch_data[branch_name]['total_sales'] += item['cancelled_count']  # Sumar al total de ventas
        else:
            # Sucursal con solo canceladas
            branch_data[branch_name] = {
                'branch__name': branch_name,
                'total_sales': item['cancelled_count'],
                'total_amount': 0,
                'active_count': 0,
                'cancelled_count': item['cancelled_count'],
                'avg_ticket': 0
            }
    
    # Calcular porcentajes
    total_period_amount = total_amount
    for branch_name, data in branch_data.items():
        if total_period_amount > 0:
            data['percentage'] = (data['total_amount'] / total_period_amount) * 100
        else:
            data['percentage'] = 0
    
    return render(request, 'admin/sales/list.html', {
        'sales': sales,
        'total_sales': total_sales,
        'total_amount': total_amount,
        'active_sales': active_sales,
        'cancelled_sales': cancelled_sales,  # ✅ Ahora muestra el total correcto
        'total_period': total_amount,
        'average_ticket': average_ticket,
        'branches': Branch.objects.filter(is_active=True),
        'branch_summary': branch_data.values(),
        'period_label': period_label,
        'selected_period': period,
        'selected_date': selected_date,
        'selected_month': selected_month,
        'selected_year': selected_year,
        'date_from': date_from,
        'date_to': date_to,
    })

@login_required
@role_required(['ADMIN', 'SUPERADMIN'])
def admin_sale_detail(request, sale_id):
    """Detalle de venta para administradores"""
    try:
        sale = get_object_or_404(
            Sale.objects.select_related('branch', 'cashier', 'cancelled_by'),
            id=sale_id
        )
        
        items = []
        for item in sale.items.all():
            items.append({
                'id': item.id,
                'product_name': item.product.name,
                'quantity': item.quantity,
                'price': float(item.price),
                'price_type': item.get_price_type_display(),
                'subtotal': float(item.quantity * item.price)
            })
        
        # Si es una petición AJAX, devolver JSON
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            data = {
                'id': sale.id,
                'date': sale.created_at.strftime('%d/%m/%Y %H:%M'),
                'branch': sale.branch.name,
                'cashier': sale.cashier.get_full_name() or sale.cashier.username,
                'total': float(sale.total),
                'status': sale.status,
                'status_display': sale.get_status_display(),
                'cancelled_at': sale.cancelled_at.strftime('%d/%m/%Y %H:%M') if sale.cancelled_at else None,
                'cancelled_by': sale.cancelled_by.get_full_name() or sale.cancelled_by.username if sale.cancelled_by else None,
                'cancellation_reason': sale.cancellation_reason,
                'items': items
            }
            return JsonResponse(data)
        
        # Si es una petición normal, renderizar template
        return render(request, 'admin/sales/detail.html', {
            'sale': sale,
            'items': items
        })
        
    except Sale.DoesNotExist:
        messages.error(request, 'Venta no encontrada')
        return redirect('sales:admin_sales_list')


@login_required
@role_required(['ADMIN', 'SUPERADMIN'])
@transaction.atomic
def cancel_sale(request, sale_id):
    """Cancelar una venta y revertir el inventario"""
    logger.info(f"Iniciando cancelación de venta #{sale_id} por usuario {request.user.username}")
    
    if request.method != 'POST':
        logger.warning(f"Método no permitido: {request.method}")
        return JsonResponse({'error': 'Método no permitido'}, status=405)
    
    try:
        sale = get_object_or_404(Sale, id=sale_id)
        logger.info(f"Venta encontrada: #{sale.id}, estado: {sale.status}, total: {sale.total}")
        
        if sale.status == 'CANCELLED':
            logger.warning(f"Intento de cancelar venta ya cancelada #{sale_id}")
            return JsonResponse({'error': 'Esta venta ya está cancelada'}, status=400)
        
        # Obtener datos de la solicitud
        try:
            data = json.loads(request.body)
            reason = data.get('reason', '')
            logger.info(f"Motivo de cancelación: '{reason}'")
        except json.JSONDecodeError as e:
            logger.error(f"Error al decodificar JSON: {e}")
            return JsonResponse({'error': 'Datos inválidos'}, status=400)
        
        with transaction.atomic():
            # Revertir cada item al inventario
            items_reverted = 0
            for item in sale.items.all():
                logger.info(f"Procesando item: {item.product.name}, cantidad: {item.quantity}")
                
                # ✅ Usar Decimal para stock
                inventory, created = Inventory.objects.get_or_create(
                    branch=sale.branch,
                    product=item.product,
                    defaults={'stock': Decimal('0')}
                )
                
                stock_antes = inventory.stock
                # ✅ Sumar la cantidad (Decimal)
                inventory.stock += item.quantity
                inventory.save()
                
                # Registrar movimiento de reversión
                InventoryMovement.objects.create(
                    inventory=inventory,
                    quantity=item.quantity,
                    movement_type='IN'
                )
                
                logger.info(f"Inventario actualizado: {inventory.product.name} - {stock_antes} → {inventory.stock}")
                items_reverted += 1
            
            # Actualizar la venta
            sale.status = 'CANCELLED'
            sale.cancelled_at = timezone.now()
            sale.cancelled_by = request.user
            sale.cancellation_reason = reason
            sale.save()
            
            logger.info(f"Venta #{sale.id} cancelada exitosamente. Items revertidos: {items_reverted}")
        
        return JsonResponse({
            'success': True,
            'message': f'Venta #{sale.id} cancelada exitosamente',
            'total_refunded': float(sale.total),
            'items_reverted': items_reverted
        })
        
    except Sale.DoesNotExist:
        logger.error(f"Venta #{sale_id} no encontrada")
        return JsonResponse({'error': 'Venta no encontrada'}, status=404)
    except Exception as e:
        logger.error(f"Error al cancelar venta #{sale_id}: {str(e)}")
        logger.error(traceback.format_exc())
        return JsonResponse({'error': str(e)}, status=400)