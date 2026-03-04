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
import pytz  # Asegúrate de tener pytz instalado


logger = logging.getLogger(__name__)


# =============================
# 🧑‍💼 CAJERO
# =============================

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

        if not cart:
            return JsonResponse({'error': 'Carrito vacío'}, status=400)

        sale = Sale.objects.create(
            branch=branch,
            cashier=request.user,
            total=0
        )

        total_sale = 0

        for item in cart:
            product_id = item['id']
            quantity = int(item['quantity'])
            price_type = item.get('price_type', 'kg')

            inventory_item = Inventory.objects.filter(
                branch=branch,
                product_id=product_id
            ).first()

            if not inventory_item or inventory_item.stock < quantity:
                transaction.set_rollback(True)
                return JsonResponse({'error': f'Stock insuficiente para {inventory_item.product.name}'}, status=400)

            price = Decimal(str(item['price']))
            subtotal = price * quantity
            total_sale += subtotal

            # Crear SaleItem con tipo de precio
            SaleItem.objects.create(
                sale=sale,
                product=inventory_item.product,
                quantity=quantity,
                price=price,
                price_type=price_type
            )

            # Descontar stock
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
            item_subtotal = item.quantity * float(item.price)
            subtotal += item_subtotal
            
            items.append({
                'id': item.id,
                'product_name': item.product.name,
                'quantity': item.quantity,
                'price': float(item.price),
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
            # ✅ AGREGAR ESTOS CAMPOS
            'status': sale.status,
            'status_display': sale.get_status_display()
        }
        
        return JsonResponse(data)
        
    except Sale.DoesNotExist:
        return JsonResponse({'error': 'Venta no encontrada'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

# =============================
# 🧑‍💼 ADMINISTRADOR
# =============================

@login_required
@role_required(['ADMIN', 'SUPERADMIN'])
def admin_sales_list(request):
    """Lista de ventas para administradores"""
    user = request.user
    
    # Obtener todas las ventas
    sales = Sale.objects.select_related(
        'branch', 'cashier', 'cancelled_by'
    ).prefetch_related('items').all().order_by('-created_at')
    
    # Estadísticas
    total_sales = sales.count()
    total_amount = sales.aggregate(total=Sum('total'))['total'] or 0
    active_sales = sales.filter(status='ACTIVE').count()
    cancelled_sales = sales.filter(status='CANCELLED').count()
    
    # Ventas de hoy
    today = timezone.now().date()
    sales_today = sales.filter(created_at__date=today)
    total_today = sales_today.aggregate(total=Sum('total'))['total'] or 0
    
    # Obtener todas las sucursales para el filtro
    from branches.models import Branch
    branches = Branch.objects.filter(is_active=True)
    
    return render(request, 'admin/sales/list.html', {
        'sales': sales,
        'total_sales': total_sales,
        'total_amount': total_amount,
        'active_sales': active_sales,
        'cancelled_sales': cancelled_sales,
        'sales_today': sales_today.count(),
        'total_today': total_today,
        'branches': branches,
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
                
                inventory, created = Inventory.objects.get_or_create(
                    branch=sale.branch,
                    product=item.product,
                    defaults={'stock': 0}
                )
                
                stock_antes = inventory.stock
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