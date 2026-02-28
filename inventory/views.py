from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from users.decorators import role_required
from .forms import InventoryForm, TransferForm
from .models import Inventory, InventoryMovement, Transfer, TransferItem
from products.models import Product
from django.shortcuts import get_object_or_404
from django.db import transaction
from .models import Transfer
from branches.models import Branch
from django.contrib import messages
from django.http import JsonResponse
import json
from django.utils import timezone



@login_required
@role_required(['ADMIN', 'SUPERADMIN', 'CASHIER'])
def inventory_list(request):
    user = request.user
    branches = Branch.objects.filter(is_active=True)  # Obtener todas las sucursales activas para el filtro
    
    # Filtrar inventario según el rol del usuario
    if user.role in ['ADMIN', 'SUPERADMIN']:
        inventory = Inventory.objects.select_related('product', 'branch').all()
    elif user.role == 'CASHIER':
        inventory = Inventory.objects.select_related('product', 'branch').filter(branch=user.branch)
        # Los cajeros solo ven su propia sucursal, así que el filtro no aplica
        branches = branches.filter(id=user.branch.id) if user.branch else branches
    else:
        inventory = Inventory.objects.none()
        branches = Branch.objects.none()

    return render(request, 'admin/inventory/list.html', {
        'inventory': inventory,
        'branches': branches
    })



@login_required
@role_required(['ADMIN', 'SUPERADMIN'])
def inventory_create(request):
    # Obtener parámetros de la URL
    branch_id = request.GET.get('branch')
    product_id = request.GET.get('product')
    
    initial_data = {}
    existing_inventory = None
    
    # Si vienen con parámetros, buscar si ya existe el inventario
    if branch_id and product_id:
        try:
            existing_inventory = Inventory.objects.get(
                branch_id=branch_id,
                product_id=product_id
            )
            # Si ya existe, establecer el stock inicial como 1 por defecto para agregar
            initial_data['stock'] = 1
        except Inventory.DoesNotExist:
            pass
    
    if request.method == 'POST':
        # Si estamos agregando stock a un inventario existente
        if existing_inventory:
            # Obtener la cantidad a agregar del formulario
            cantidad_a_agregar = int(request.POST.get('stock', 1))
            
            # Actualizar el stock existente
            existing_inventory.stock += cantidad_a_agregar
            existing_inventory.save()
            
            # Crear movimiento de entrada
            InventoryMovement.objects.create(
                inventory=existing_inventory,
                quantity=cantidad_a_agregar,
                movement_type='IN'
            )
            
            messages.success(request, f'Se agregaron {cantidad_a_agregar} unidades a {existing_inventory.product.name}')
            return redirect('inventory_list')
        
        # Si es un inventario nuevo
        else:
            form = InventoryForm(request.POST)
            if form.is_valid():
                inventory = form.save()
                
                # Crear movimiento automático tipo ENTRADA
                InventoryMovement.objects.create(
                    inventory=inventory,
                    quantity=inventory.stock,
                    movement_type='IN'
                )
                
                messages.success(request, f'Inventario creado para {inventory.product.name}')
                return redirect('inventory_list')
            else:
                # Si hay errores, mostrar el formulario con los errores
                return render(request, 'admin/inventory/form.html', {
                    'form': form,
                    'existing_inventory': existing_inventory,
                    'selected_branch': branch_id,
                    'selected_product': product_id,
                })
    else:
        # GET request - mostrar formulario
        form = InventoryForm(initial=initial_data)
    
    return render(request, 'admin/inventory/form.html', {
        'form': form,
        'existing_inventory': existing_inventory,
        'selected_branch': branch_id,
        'selected_product': product_id,
    })

@login_required
@role_required(['ADMIN', 'SUPERADMIN'])
def transfer_list(request):
    transfers = Transfer.objects.select_related(
        'from_branch', 'to_branch', 'created_by'
    ).prefetch_related('items__product').order_by('-created_at')
    
    # Estadísticas
    total_transfers = transfers.count()
    pending_transfers = transfers.filter(status='PENDING').count()
    completed_transfers = transfers.filter(status='COMPLETED').count()
    
    return render(request, 'admin/transfers/list.html', {
        'transfers': transfers,
        'total_transfers': total_transfers,
        'pending_transfers': pending_transfers,
        'completed_transfers': completed_transfers,
    })


@login_required
@role_required(['ADMIN', 'SUPERADMIN'])
def transfer_create(request):
    if request.method == 'POST':
        form = TransferForm(request.POST)
        
        if form.is_valid():
            transfer = form.save(commit=False)
            transfer.created_by = request.user
            transfer.save()
            
            # Procesar los items
            products = request.POST.getlist('product[]')
            quantities = request.POST.getlist('quantity[]')
            items_added = 0
            
            for i, product_id in enumerate(products):
                if product_id and quantities[i]:
                    quantity = int(quantities[i])
                    if quantity > 0:
                        TransferItem.objects.create(
                            transfer=transfer,
                            product_id=product_id,
                            quantity=quantity
                        )
                        items_added += 1
            
            if items_added == 0:
                transfer.delete()
                messages.error(request, 'Debes agregar al menos un producto a la transferencia.')
                return redirect('transfer_create')
            
            messages.success(request, f'Transferencia #{transfer.id} creada con {items_added} producto(s).')
            return redirect('transfer_detail', transfer_id=transfer.id)
    else:
        form = TransferForm()
    
    branches = Branch.objects.filter(is_active=True)
    products = Product.objects.filter(is_active=True)
    
    return render(request, 'admin/transfers/form.html', {
        'form': form,
        'branches': branches,
        'products': products,
    })


@login_required
@role_required(['ADMIN', 'SUPERADMIN'])
def transfer_detail(request, transfer_id):
    transfer = get_object_or_404(
        Transfer.objects.select_related('from_branch', 'to_branch', 'created_by')
        .prefetch_related('items__product'),
        id=transfer_id
    )
    
    # Verificar disponibilidad de stock para cada item
    stock_status = []
    all_available = True
    
    for item in transfer.items.all():
        inventory = Inventory.objects.filter(
            branch=transfer.from_branch,
            product=item.product
        ).first()
        
        available_stock = inventory.stock if inventory else 0
        is_available = available_stock >= item.quantity
        
        stock_status.append({
            'item': item,
            'available_stock': available_stock,
            'is_available': is_available,
            'needs': max(0, item.quantity - available_stock) if not is_available else 0
        })
        
        if not is_available:
            all_available = False
    
    return render(request, 'admin/transfers/detail.html', {
        'transfer': transfer,
        'stock_status': stock_status,
        'all_available': all_available,
    })


@login_required
@role_required(['ADMIN', 'SUPERADMIN'])
@transaction.atomic
def transfer_process(request, transfer_id):
    transfer = get_object_or_404(Transfer, id=transfer_id)
    
    if transfer.status != 'PENDING':
        messages.error(request, 'Esta transferencia ya ha sido procesada.')
        return redirect('transfer_detail', transfer_id=transfer.id)
    
    if request.method == 'POST':
        # Verificar stock disponible
        all_available = True
        for item in transfer.items.all():
            inventory = Inventory.objects.filter(
                branch=transfer.from_branch,
                product=item.product
            ).first()
            
            if not inventory or inventory.stock < item.quantity:
                all_available = False
                messages.error(
                    request, 
                    f'Stock insuficiente para {item.product.name}. '
                    f'Disponible: {inventory.stock if inventory else 0}, Requerido: {item.quantity}'
                )
        
        if not all_available:
            return redirect('transfer_detail', transfer_id=transfer.id)
        
        # Procesar la transferencia
        for item in transfer.items.all():
            # Restar del origen
            from_inventory = Inventory.objects.get(
                branch=transfer.from_branch,
                product=item.product
            )
            from_inventory.stock -= item.quantity
            from_inventory.save()
            
            InventoryMovement.objects.create(
                inventory=from_inventory,
                quantity=item.quantity,
                movement_type='TRANSFER_OUT',
                reference_id=transfer.id
            )
            
            # Agregar al destino
            to_inventory, created = Inventory.objects.get_or_create(
                branch=transfer.to_branch,
                product=item.product,
                defaults={'stock': 0}
            )
            to_inventory.stock += item.quantity
            to_inventory.save()
            
            InventoryMovement.objects.create(
                inventory=to_inventory,
                quantity=item.quantity,
                movement_type='TRANSFER_IN',
                reference_id=transfer.id
            )
        
        transfer.status = 'COMPLETED'
        transfer.completed_at = timezone.now()
        transfer.save()
        
        messages.success(request, f'Transferencia #{transfer.id} completada exitosamente.')
        return redirect('transfer_detail', transfer_id=transfer.id)
    
    return redirect('transfer_detail', transfer_id=transfer.id)


@login_required
@role_required(['ADMIN', 'SUPERADMIN'])
def transfer_cancel(request, transfer_id):
    transfer = get_object_or_404(Transfer, id=transfer_id)
    
    if transfer.status != 'PENDING':
        messages.error(request, 'Solo se pueden cancelar transferencias pendientes.')
        return redirect('transfer_detail', transfer_id=transfer.id)
    
    if request.method == 'POST':
        transfer.status = 'CANCELLED'
        transfer.save()
        messages.success(request, f'Transferencia #{transfer.id} cancelada.')
        return redirect('transfer_list')
    
    return redirect('transfer_detail', transfer_id=transfer.id)


@login_required
@role_required(['ADMIN', 'SUPERADMIN'])
def get_branch_inventory(request):
    """API para obtener el inventario de una sucursal"""
    branch_id = request.GET.get('branch_id')
    if not branch_id:
        return JsonResponse({'error': 'Branch ID required'}, status=400)
    
    inventory = Inventory.objects.filter(
        branch_id=branch_id,
        stock__gt=0
    ).select_related('product').order_by('product__name')
    
    data = [{
        'id': item.product.id,
        'name': item.product.name,
        'stock': item.stock,
        'description': item.product.description,
        'is_ingredient': item.product.is_ingredient,
    } for item in inventory]
    
    return JsonResponse({'inventory': data})