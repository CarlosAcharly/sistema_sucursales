from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.db import transaction
from users.decorators import role_required
from inventory.models import Inventory, InventoryMovement
from .models import Sale, SaleItem
from products.models import Product
from django.utils.timezone import now
from django.db.models import Sum, Count
from inventory.models import Inventory
from .models import Sale, SaleItem
import json
from django.http import JsonResponse
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

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
    today = timezone.now().date()
    yesterday = today - timedelta(days=1)
    
    # Obtener todas las ventas de la sucursal
    sales = Sale.objects.filter(branch=branch).prefetch_related('items__product').order_by('-created_at')
    
    # Ventas de hoy
    sales_today = sales.filter(created_at__date=today)
    sales_today_count = sales_today.count()
    total_today = sales_today.aggregate(total=Sum('total'))['total'] or Decimal('0')
    
    # Ventas de ayer
    sales_yesterday = Sale.objects.filter(branch=branch, created_at__date=yesterday)
    total_yesterday = sales_yesterday.aggregate(total=Sum('total'))['total'] or Decimal('0')
    
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
    
    # Total general de ventas
    total_sum = sales.aggregate(total=Sum('total'))['total'] or Decimal('0')
    
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
            'items': items
        }
        
        return JsonResponse(data)
        
    except Sale.DoesNotExist:
        return JsonResponse({'error': 'Venta no encontrada'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)