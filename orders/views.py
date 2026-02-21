from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from products.models import Product
from .models import Order, OrderItem
from inventory.models import Inventory, InventoryMovement
from django.db import transaction
from .services import complete_order
import logging

logger = logging.getLogger(__name__)


# =============================
# 🧑‍💼 CAJERO
# =============================

@login_required
def create_order(request):
    if request.user.role != "CASHIER":
        messages.error(request, "No tienes permiso para acceder a esta página.")
        return redirect("no_permission")

    products = Product.objects.all()
    branch = request.user.branch

    if request.method == "POST":
        # Obtener listas de productos y kilos
        product_ids = request.POST.getlist("product")
        kilos_list = request.POST.getlist("kilos")
        
        # Depuración - mostrar en consola
        logger.info(f"Product IDs recibidos: {product_ids}")
        logger.info(f"Kilos recibidos: {kilos_list}")
        
        # Validar que haya al menos un producto
        if not product_ids:
            messages.error(request, "Debes agregar al menos un producto.")
            return redirect("orders:create_order")
        
        # Filtrar solo productos con kilos válidos
        items_to_create = []
        for i, (product_id, kilos) in enumerate(zip(product_ids, kilos_list)):
            try:
                if kilos and kilos.strip():
                    kilos_float = float(kilos)
                    if kilos_float > 0:
                        items_to_create.append({
                            'product_id': product_id,
                            'kilos': kilos_float
                        })
                        logger.info(f"Producto {i+1}: ID={product_id}, Kilos={kilos_float}")
            except (ValueError, TypeError) as e:
                logger.warning(f"Error al procesar kilos '{kilos}': {e}")
                continue
        
        if not items_to_create:
            messages.error(request, "Debes ingresar cantidades válidas para al menos un producto.")
            return redirect("orders:create_order")
        
        # Crear el pedido con transacción atómica
        try:
            with transaction.atomic():
                order = Order.objects.create(
                    branch=branch,
                    created_by=request.user,
                    status="PENDING"
                )
                
                # Crear todos los items
                created_items = []
                for item_data in items_to_create:
                    item = OrderItem.objects.create(
                        order=order,
                        product_id=item_data['product_id'],
                        kilos=item_data['kilos']
                    )
                    created_items.append(item)
                
                logger.info(f"Pedido #{order.id} creado con {len(created_items)} productos")
                messages.success(
                    request, 
                    f"Pedido #{order.id} creado exitosamente con {len(created_items)} productos."
                )
                
        except Exception as e:
            logger.error(f"Error al crear pedido: {str(e)}")
            messages.error(request, f"Error al crear el pedido: {str(e)}")
            return redirect("orders:create_order")
        
        return redirect("orders:cashier_orders")

    return render(request, "cajero/orders/create.html", {
        "products": products
    })


@login_required
def cashier_orders(request):
    if request.user.role != "CASHIER":
        messages.error(request, "No tienes permiso para acceder a esta página.")
        return redirect("no_permission")

    orders = Order.objects.filter(
        branch=request.user.branch
    ).prefetch_related('items').order_by("-created_at")

    # Calcular estadísticas
    pending_count = orders.filter(status="PENDING").count()
    completed_count = orders.filter(status="COMPLETED").count()
    total_kilos = sum(order.total_kilos() for order in orders)

    return render(request, "cajero/orders/list.html", {
        "orders": orders,
        "pending_count": pending_count,
        "completed_count": completed_count,
        "total_kilos": total_kilos
    })


@login_required
def order_detail_api(request, order_id):
    """API para obtener detalles del pedido en formato JSON"""
    try:
        order = Order.objects.prefetch_related('items__product').get(
            id=order_id, 
            branch=request.user.branch
        )
        data = {
            'id': order.id,
            'status': order.status,
            'date': order.created_at.strftime('%d/%m/%Y %H:%M'),
            'products': [
                {
                    'name': item.product.name,
                    'kilos': float(item.kilos)
                }
                for item in order.items.all()
            ]
        }
        return JsonResponse(data)
    except Order.DoesNotExist:
        return JsonResponse({'error': 'Pedido no encontrado'}, status=404)


@login_required
def cancel_order(request, order_id):
    """Cancelar un pedido pendiente"""
    order = get_object_or_404(Order, id=order_id, branch=request.user.branch)
    
    if order.status != "PENDING":
        messages.error(request, "Solo se pueden cancelar pedidos pendientes.")
        return redirect("orders:cashier_orders")
    
    if request.method == "POST":
        order.status = "CANCELLED"
        order.save()
        messages.success(request, f'Pedido #{order.id} cancelado exitosamente.')
        return redirect("orders:cashier_orders")
    
    return redirect("orders:cashier_orders")


@login_required
@transaction.atomic
def add_order_to_inventory(request, order_id):
    """Agregar productos de un pedido completado al inventario"""
    order = get_object_or_404(Order, id=order_id, branch=request.user.branch)
    
    if order.status != "COMPLETED":
        messages.error(request, "Solo se pueden agregar al inventario pedidos completados.")
        return redirect("orders:cashier_orders")
    
    if request.method == "POST":
        items_added = 0
        for item in order.items.all():
            inventory, created = Inventory.objects.get_or_create(
                branch=order.branch,
                product=item.product,
                defaults={'stock': 0}
            )
            # Usar float en lugar de int para mantener precisión
            inventory.stock += float(item.kilos)
            inventory.save()
            
            InventoryMovement.objects.create(
                inventory=inventory,
                quantity=float(item.kilos),
                movement_type='IN',
                description=f"Agregado desde pedido #{order.id}"
            )
            items_added += 1
        
        messages.success(
            request, 
            f'{items_added} productos del pedido #{order.id} agregados al inventario.'
        )
        return redirect("orders:cashier_orders")
    
    return redirect("orders:cashier_orders")


# =============================
# 🧑‍💼 ADMIN
# =============================

@login_required
def admin_orders(request):
    if request.user.role != "ADMIN":
        messages.error(request, "No tienes permiso para acceder a esta página.")
        return redirect("no_permission")

    orders = Order.objects.all().select_related(
        'branch', 'created_by'
    ).prefetch_related('items').order_by("-created_at")

    # Calcular estadísticas
    pending_count = orders.filter(status="PENDING").count()
    completed_count = orders.filter(status="COMPLETED").count()
    total_kilos = sum(order.total_kilos() for order in orders)

    return render(request, "admin/orders/list.html", {
        "orders": orders,
        "pending_count": pending_count,
        "completed_count": completed_count,
        "total_kilos": total_kilos
    })


@login_required
@transaction.atomic
def approve_order(request, order_id):
    """Aprobar un pedido pendiente"""
    if request.user.role != "ADMIN":
        messages.error(request, "No tienes permiso para acceder a esta página.")
        return redirect("no_permission")

    order = get_object_or_404(Order, id=order_id)
    
    if order.status != "PENDING":
        messages.error(request, "Este pedido no está pendiente de aprobación.")
        return redirect("orders:admin_orders")
    
    if request.method == "POST":
        # Usar el servicio complete_order
        complete_order(order)
        messages.success(request, f'Pedido #{order.id} aprobado exitosamente.')
        return redirect("orders:admin_orders")
    
    return redirect("orders:admin_orders")


@login_required
def delete_order_item(request, item_id):
    """Eliminar un item específico de un pedido (solo para admin)"""
    if request.user.role != "ADMIN":
        messages.error(request, "No tienes permiso para acceder a esta página.")
        return redirect("no_permission")

    item = get_object_or_404(OrderItem, id=item_id)
    order = item.order
    
    if order.status != "PENDING":
        messages.error(request, "Solo se pueden modificar pedidos pendientes.")
        return redirect("orders:admin_orders")
    
    if request.method == "POST":
        product_name = item.product.name
        item.delete()
        messages.success(request, f'Producto "{product_name}" eliminado del pedido #{order.id}.')
        return redirect("orders:admin_orders")
    
    return redirect("orders:admin_orders")