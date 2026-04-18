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
import json
from decimal import Decimal

# ✅ Importar función para obtener precio de compra
from earnings.views import get_purchase_price_at_date


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
                    status="PENDING",
                    inventory_added=False
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
    """API para obtener detalles del pedido en formato JSON (incluyendo presupuesto)"""
    try:
        # Para admin: puede ver cualquier pedido
        if request.user.role == "ADMIN":
            order = Order.objects.prefetch_related('items__product').get(id=order_id)
        else:
            # Para cajero: solo puede ver pedidos de su sucursal
            order = Order.objects.prefetch_related('items__product').get(
                id=order_id, 
                branch=request.user.branch
            )
        
        items = []
        total_budget = Decimal('0')
        
        for item in order.items.all():
            # ✅ Obtener precio de compra en la fecha del pedido
            purchase_price = get_purchase_price_at_date(item.product.id, order.created_at)
            budget = Decimal(str(item.kilos)) * purchase_price
            total_budget += budget
            
            items.append({
                'id': item.id,
                'product_id': item.product.id,
                'name': item.product.name,
                'kilos': float(item.kilos),
                'purchase_price': float(purchase_price),  # ✅ Precio de compra por kg
                'budget': float(budget),  # ✅ Presupuesto total para este producto
                'can_delete': order.status == "PENDING",
                'original_kilos': float(item.kilos)
            })
        
        data = {
            'id': order.id,
            'status': order.status,
            'status_display': order.get_status_display(),
            'date': order.created_at.strftime('%d/%m/%Y %H:%M'),
            'branch': order.branch.name,
            'cashier': order.created_by.get_full_name() or order.created_by.username,
            'total_kilos': float(order.total_kilos()),
            'total_budget': float(total_budget),  # ✅ Presupuesto total del pedido
            'items_count': order.items_count(),
            'items': items,
            'can_edit': order.status == "PENDING",
            'inventory_added': order.inventory_added
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
    from inventory.models import Inventory, InventoryMovement
    
    order = get_object_or_404(Order, id=order_id, branch=request.user.branch)
    
    # VERIFICACIONES ESTRICTAS
    if order.inventory_added:
        logger.warning(f"Intento de agregar pedido #{order_id} que ya tiene inventory_added=True")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'error': 'Este pedido ya fue agregado al inventario anteriormente.'
            }, status=400)
        messages.error(request, "Este pedido ya fue agregado al inventario anteriormente.")
        return redirect("orders:cashier_orders")
    
    if order.status != "COMPLETED":
        logger.warning(f"Intento de agregar pedido #{order_id} con estado {order.status}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'error': 'Solo se pueden agregar al inventario pedidos completados.'
            }, status=400)
        messages.error(request, "Solo se pueden agregar al inventario pedidos completados.")
        return redirect("orders:cashier_orders")
    
    if request.method == "POST":
        items_added = 0
        items_errors = 0
        results = []
        
        # REFRESCAR para asegurar que no cambió
        order.refresh_from_db()
        
        # Verificar nuevamente después del refresh
        if order.inventory_added:
            logger.error(f"Pedido #{order_id} cambió a inventory_added=True justo antes de procesar")
            return JsonResponse({
                'success': False,
                'error': 'El pedido ya fue procesado por otra solicitud.'
            }, status=400)
        
        logger.info(f"Procesando pedido #{order_id} para agregar a inventario. Items: {order.items.count()}")
        
        for item in order.items.all():
            try:
                kilos = float(item.kilos)
                
                # IMPORTANTE: El inventario usa IntegerField, así que redondeamos al entero más cercano
                cantidad = int(round(kilos))
                
                logger.info(f"Item: {item.product.name}, kilos original: {kilos}, cantidad a agregar: {cantidad}")
                
                if cantidad <= 0:
                    logger.warning(f"Cantidad no válida para {item.product.name}: {kilos}")
                    results.append({
                        'product': item.product.name,
                        'status': 'skipped',
                        'message': f'Cantidad no válida: {kilos} kg'
                    })
                    continue
                
                inventory, created = Inventory.objects.get_or_create(
                    branch=order.branch,
                    product=item.product,
                    defaults={'stock': 0}
                )
                
                stock_antes = inventory.stock
                inventory.stock += cantidad
                inventory.save()
                
                InventoryMovement.objects.create(
                    inventory=inventory,
                    quantity=cantidad,
                    movement_type='IN'
                )
                
                logger.info(f"Inventario actualizado: {inventory.product.name} - Stock antes: {stock_antes}, después: {inventory.stock}")
                
                results.append({
                    'product': item.product.name,
                    'status': 'success',
                    'kilos_original': kilos,
                    'unidades_agregadas': cantidad,
                    'stock_anterior': stock_antes,
                    'stock_nuevo': inventory.stock
                })
                
                items_added += 1
                
            except Exception as e:
                items_errors += 1
                logger.error(f"Error al procesar item {item.id}: {str(e)}")
                results.append({
                    'product': item.product.name,
                    'status': 'error',
                    'message': str(e)
                })
        
        # Marcar el pedido como agregado al inventario SOLO si al menos un item se agregó
        if items_added > 0:
            order.inventory_added = True
            order.save()
            logger.info(f"Pedido #{order.id} marcado como inventory_added=True. Items agregados: {items_added}")
        else:
            logger.warning(f"Pedido #{order.id} no se marcó como inventory_added porque no se agregaron items")
        
        # Si es una petición AJAX, devolver JSON
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': items_added > 0,
                'items_added': items_added,
                'items_errors': items_errors,
                'results': results,
                'message': f'{items_added} productos agregados al inventario.'
            })
        
        # Si es una petición normal, hacer redirect con mensajes
        if items_added > 0:
            messages.success(request, f'{items_added} productos del pedido #{order.id} agregados al inventario.')
        if items_errors > 0:
            messages.error(request, f'Hubo {items_errors} error(es) al procesar el pedido.')
            
        return redirect("orders:cashier_orders")
    
    return redirect("orders:cashier_orders")


# =============================
# 🧑‍💼 ADMIN - NUEVAS FUNCIONALIDADES
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
        # Usar el servicio complete_order que SOLO cambia el estado
        complete_order(order)
        messages.success(request, f'Pedido #{order.id} aprobado exitosamente. El cajero podrá agregarlo al inventario.')
        return redirect("orders:admin_orders")
    
    return redirect("orders:admin_orders")


@login_required
def delete_order_item(request, item_id):
    """Eliminar un item específico de un pedido (solo para admin)"""
    if request.user.role != "ADMIN":
        return JsonResponse({'error': 'No autorizado'}, status=403)
    
    if request.method == "POST":
        try:
            item = get_object_or_404(OrderItem, id=item_id)
            order = item.order
            
            if order.status != "PENDING":
                return JsonResponse({'error': 'Solo se pueden modificar pedidos pendientes.'}, status=400)
            
            product_name = item.product.name
            item.delete()
            
            return JsonResponse({
                'success': True,
                'message': f'Producto "{product_name}" eliminado del pedido #{order.id}.',
                'new_total_kilos': float(order.total_kilos()),
                'new_items_count': order.items_count()
            })
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    
    return JsonResponse({'error': 'Método no permitido'}, status=405)


@login_required
def update_order_item(request, item_id):
    """Actualizar la cantidad de un item específico de un pedido (solo para admin)"""
    if request.user.role != "ADMIN":
        return JsonResponse({'error': 'No autorizado'}, status=403)
    
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            new_kilos = float(data.get('kilos', 0))
            
            item = get_object_or_404(OrderItem, id=item_id)
            order = item.order
            
            if order.status != "PENDING":
                return JsonResponse({'error': 'Solo se pueden modificar pedidos pendientes.'}, status=400)
            
            if new_kilos <= 0:
                return JsonResponse({'error': 'La cantidad debe ser mayor a 0.'}, status=400)
            
            old_kilos = float(item.kilos)
            item.kilos = new_kilos
            item.save()
            
            return JsonResponse({
                'success': True,
                'message': f'Cantidad actualizada de {item.product.name}: {old_kilos} kg → {new_kilos} kg',
                'new_total_kilos': float(order.total_kilos()),
                'new_items_count': order.items_count()
            })
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    
    return JsonResponse({'error': 'Método no permitido'}, status=405)


@login_required
def batch_update_order(request, order_id):
    """Actualizar múltiples items de un pedido a la vez (solo para admin)"""
    if request.user.role != "ADMIN":
        return JsonResponse({'error': 'No autorizado'}, status=403)
    
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            updates = data.get('updates', [])  # Lista de {id: item_id, kilos: new_kilos}
            deletes = data.get('deletes', [])  # Lista de item_ids a eliminar
            
            order = get_object_or_404(Order, id=order_id)
            
            if order.status != "PENDING":
                return JsonResponse({'error': 'Solo se pueden modificar pedidos pendientes.'}, status=400)
            
            results = {
                'updated': [],
                'deleted': [],
                'errors': []
            }
            
            # Procesar actualizaciones
            with transaction.atomic():
                for update in updates:
                    try:
                        item = OrderItem.objects.get(id=update['id'], order=order)
                        old_kilos = float(item.kilos)
                        new_kilos = float(update['kilos'])
                        
                        if new_kilos <= 0:
                            results['errors'].append({
                                'id': update['id'],
                                'error': 'La cantidad debe ser mayor a 0'
                            })
                            continue
                        
                        item.kilos = new_kilos
                        item.save()
                        
                        results['updated'].append({
                            'id': item.id,
                            'product': item.product.name,
                            'old_kilos': old_kilos,
                            'new_kilos': new_kilos
                        })
                        
                    except OrderItem.DoesNotExist:
                        results['errors'].append({
                            'id': update['id'],
                            'error': 'Item no encontrado'
                        })
                    except Exception as e:
                        results['errors'].append({
                            'id': update['id'],
                            'error': str(e)
                        })
                
                # Procesar eliminaciones
                for item_id in deletes:
                    try:
                        item = OrderItem.objects.get(id=item_id, order=order)
                        product_name = item.product.name
                        item.delete()
                        
                        results['deleted'].append({
                            'id': item_id,
                            'product': product_name
                        })
                        
                    except OrderItem.DoesNotExist:
                        results['errors'].append({
                            'id': item_id,
                            'error': 'Item no encontrado'
                        })
                        pass
                    except Exception as e:
                        results['errors'].append({
                            'id': item_id,
                            'error': str(e)
                        })
            
            return JsonResponse({
                'success': True,
                'results': results,
                'new_total_kilos': float(order.total_kilos()),
                'new_items_count': order.items_count(),
                'message': f'Actualizados: {len(results["updated"])} productos, Eliminados: {len(results["deleted"])} productos'
            })
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    
    return JsonResponse({'error': 'Método no permitido'}, status=405)


@login_required
def order_items_api(request, order_id):
    """API para obtener los items de un pedido"""
    try:
        order = Order.objects.get(id=order_id, branch=request.user.branch)
        items = []
        for item in order.items.all():
            items.append({
                'id': item.id,
                'name': item.product.name,
                'kilos': float(item.kilos),
                'product_id': item.product.id
            })
        
        return JsonResponse({
            'success': True,
            'items': items,
            'total_items': len(items),
            'total_kilos': float(order.total_kilos())
        })
    except Order.DoesNotExist:
        return JsonResponse({'error': 'Pedido no encontrado'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)