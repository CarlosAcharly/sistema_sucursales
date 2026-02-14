from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.db import transaction
from users.decorators import role_required
from inventory.models import Inventory, InventoryMovement
from .models import Sale, SaleItem
from products.models import Product
from django.utils.timezone import now
from django.db.models import Sum
from inventory.models import Inventory
from .models import Sale, SaleItem
import json
from django.http import JsonResponse

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

            inventory_item = Inventory.objects.filter(
                branch=branch,
                product_id=product_id
            ).first()

            if not inventory_item or inventory_item.stock < quantity:
                transaction.set_rollback(True)
                return JsonResponse({'error': f'Stock insuficiente para {inventory_item.product.name}'}, status=400)

            price = inventory_item.product.price
            subtotal = price * quantity
            total_sale += subtotal

            # Crear SaleItem
            SaleItem.objects.create(
                sale=sale,
                product=inventory_item.product,
                quantity=quantity,
                price=price
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

        return JsonResponse({'success': True})

    return render(request, 'cajero/pos.html', {
        'inventory': inventory
    })


@login_required
@role_required(['CASHIER'])
def sales_list(request):
    branch = request.user.branch
    sales = Sale.objects.filter(branch=branch).order_by('-created_at')
    return render(request, 'cajero/sales_list.html', {'sales': sales})

@login_required
@role_required(['CASHIER'])
def cajero_dashboard(request):

    branch = request.user.branch
    today = now().date()

    sales_today = Sale.objects.filter(
        branch=branch,
        created_at__date=today
    )

    total_today = sales_today.aggregate(
        total=Sum('total')
    )['total'] or 0

    items_today = SaleItem.objects.filter(
        sale__branch=branch,
        sale__created_at__date=today
    ).aggregate(
        total=Sum('quantity')
    )['total'] or 0

    low_stock = Inventory.objects.filter(
        branch=branch,
        stock__lte=5
    )

    return render(request, 'cajero/dashboard.html', {
        'total_today': total_today,
        'items_today': items_today,
        'low_stock': low_stock
    })