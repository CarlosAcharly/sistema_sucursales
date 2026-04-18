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
from decimal import Decimal
from django.db.models import Q


# =============================
# FUNCIÓN AUXILIAR PARA VERIFICAR PERMISO DE TRANSFERENCIA
# =============================

def user_can_transfer(user):
    """Verifica si el usuario puede hacer transferencias"""
    # Superadmin y Admin siempre pueden
    if user.role in ['SUPERADMIN', 'ADMIN']:
        return True
    # Cajero: verificar que su sucursal tenga permiso
    if user.role == 'CASHIER' and user.branch and user.branch.can_transfer:
        return True
    return False


# =============================
# INVENTARIO
# =============================

@login_required
@role_required(['ADMIN', 'SUPERADMIN', 'CASHIER'])
def inventory_list(request):
    user = request.user
    branches = Branch.objects.filter(is_active=True)
    
    # Filtrar inventario según el rol del usuario
    if user.role in ['ADMIN', 'SUPERADMIN']:
        inventory = Inventory.objects.select_related('product', 'branch').all()
    elif user.role == 'CASHIER':
        inventory = Inventory.objects.select_related('product', 'branch').filter(branch=user.branch)
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
    branch_id = request.GET.get('branch')
    product_id = request.GET.get('product')
    
    initial_data = {}
    existing_inventory = None
    
    if branch_id and product_id:
        try:
            existing_inventory = Inventory.objects.get(
                branch_id=branch_id,
                product_id=product_id
            )
            initial_data['stock'] = 1
        except Inventory.DoesNotExist:
            pass
    
    if request.method == 'POST':
        if existing_inventory:
            cantidad_a_agregar = int(request.POST.get('stock', 1))
            existing_inventory.stock += cantidad_a_agregar
            existing_inventory.save()
            
            InventoryMovement.objects.create(
                inventory=existing_inventory,
                quantity=cantidad_a_agregar,
                movement_type='IN'
            )
            
            messages.success(request, f'Se agregaron {cantidad_a_agregar} unidades a {existing_inventory.product.name}')
            return redirect('inventory_list')
        else:
            form = InventoryForm(request.POST)
            if form.is_valid():
                inventory = form.save()
                InventoryMovement.objects.create(
                    inventory=inventory,
                    quantity=inventory.stock,
                    movement_type='IN'
                )
                messages.success(request, f'Inventario creado para {inventory.product.name}')
                return redirect('inventory_list')
            else:
                return render(request, 'admin/inventory/form.html', {
                    'form': form,
                    'existing_inventory': existing_inventory,
                    'selected_branch': branch_id,
                    'selected_product': product_id,
                })
    else:
        form = InventoryForm(initial=initial_data)
    
    return render(request, 'admin/inventory/form.html', {
        'form': form,
        'existing_inventory': existing_inventory,
        'selected_branch': branch_id,
        'selected_product': product_id,
    })


# =============================
# TRANSFERENCIAS - ACTUALIZADO CON TEMPLATES SEGÚN ROL
# =============================

@login_required
def transfer_list(request):
    """Lista de transferencias - Acceso para ADMIN, SUPERADMIN y CAJEROS con permiso"""
    if not user_can_transfer(request.user):
        messages.error(request, "No tienes permiso para acceder a esta página.")
        return redirect('transfer_list')
    
    # Para cajeros, solo ver transferencias de su sucursal (como origen o destino)
    if request.user.role == 'CASHIER':
        transfers = Transfer.objects.filter(
            Q(from_branch=request.user.branch) | Q(to_branch=request.user.branch)
        ).select_related('from_branch', 'to_branch', 'created_by').prefetch_related('items__product').order_by('-created_at')
    else:
        transfers = Transfer.objects.select_related(
            'from_branch', 'to_branch', 'created_by'
        ).prefetch_related('items__product').order_by('-created_at')
    
    total_transfers = transfers.count()
    pending_transfers = transfers.filter(status='PENDING').count()
    completed_transfers = transfers.filter(status='COMPLETED').count()
    
    # ✅ Seleccionar template según el rol
    if request.user.role == 'CASHIER':
        template_name = 'cajero/transfers/list.html'
    else:
        template_name = 'admin/transfers/list.html'
    
    return render(request, template_name, {
        'transfers': transfers,
        'total_transfers': total_transfers,
        'pending_transfers': pending_transfers,
        'completed_transfers': completed_transfers,
        'is_cashier': request.user.role == 'CASHIER'
    })


@login_required
def transfer_create(request):
    """Crear nueva transferencia - Acceso para ADMIN, SUPERADMIN y CAJEROS con permiso"""
    if not user_can_transfer(request.user):
        messages.error(request, "No tienes permiso para acceder a esta página.")
        return redirect('transfer_list')
    
    branches = Branch.objects.filter(is_active=True)
    products = Product.objects.filter(is_active=True)
    
    # Para cajeros: from_branch es fijo (su sucursal)
    if request.user.role == 'CASHIER':
        if request.method == 'POST':
            to_branch_id = request.POST.get('to_branch')
            notes = request.POST.get('notes', '')
            
            if not to_branch_id:
                messages.error(request, 'Debes seleccionar una sucursal de destino.')
                return redirect('transfer_create')
            
            # Crear la transferencia
            transfer = Transfer.objects.create(
                from_branch=request.user.branch,
                to_branch_id=to_branch_id,
                created_by=request.user,
                notes=notes,
                status='PENDING'
            )
            
            # Procesar los items
            products_list = request.POST.getlist('product[]')
            quantities_list = request.POST.getlist('quantity[]')
            items_added = 0
            
            for i, product_id in enumerate(products_list):
                if product_id and quantities_list[i]:
                    try:
                        quantity = Decimal(str(quantities_list[i]))
                        if quantity > 0:
                            TransferItem.objects.create(
                                transfer=transfer,
                                product_id=product_id,
                                quantity=quantity
                            )
                            items_added += 1
                    except (ValueError, DecimalException):
                        continue
            
            if items_added == 0:
                transfer.delete()
                messages.error(request, 'Debes agregar al menos un producto a la transferencia.')
                return redirect('transfer_create')
            
            messages.success(request, f'Transferencia #{transfer.id} creada con {items_added} producto(s).')
            return redirect('transfer_detail', transfer_id=transfer.id)
        
        # GET: preparar formulario para cajero
        form = TransferForm(initial={'from_branch': request.user.branch})
        # Deshabilitar el campo from_branch
        form.fields['from_branch'].disabled = True
        
        # Filtrar sucursales de destino (excluir la propia)
        branches = branches.exclude(id=request.user.branch.id)
        
        # ✅ Template para cajero
        template_name = 'cajero/transfers/form.html'
        
    else:
        # Admin / Superadmin
        if request.method == 'POST':
            form = TransferForm(request.POST)
            if form.is_valid():
                transfer = form.save(commit=False)
                transfer.created_by = request.user
                transfer.save()
                
                products_list = request.POST.getlist('product[]')
                quantities_list = request.POST.getlist('quantity[]')
                items_added = 0
                
                for i, product_id in enumerate(products_list):
                    if product_id and quantities_list[i]:
                        try:
                            quantity = Decimal(str(quantities_list[i]))
                            if quantity > 0:
                                TransferItem.objects.create(
                                    transfer=transfer,
                                    product_id=product_id,
                                    quantity=quantity
                                )
                                items_added += 1
                        except (ValueError, DecimalException):
                            continue
                
                if items_added == 0:
                    transfer.delete()
                    messages.error(request, 'Debes agregar al menos un producto a la transferencia.')
                    return redirect('transfer_create')
                
                messages.success(request, f'Transferencia #{transfer.id} creada con {items_added} producto(s).')
                return redirect('transfer_detail', transfer_id=transfer.id)
        else:
            form = TransferForm()
        
        # ✅ Template para admin
        template_name = 'admin/transfers/form.html'
    
    return render(request, template_name, {
        'form': form,
        'branches': branches,
        'products': products,
        'is_cashier': request.user.role == 'CASHIER',
        'user_branch': request.user.branch if request.user.role == 'CASHIER' else None
    })


@login_required
def transfer_detail(request, transfer_id):
    """Detalle de transferencia - Acceso para ADMIN, SUPERADMIN y CAJEROS con permiso"""
    if not user_can_transfer(request.user):
        messages.error(request, "No tienes permiso para acceder a esta página.")
        return redirect('transfer_list')
    
    transfer = get_object_or_404(
        Transfer.objects.select_related('from_branch', 'to_branch', 'created_by')
        .prefetch_related('items__product'),
        id=transfer_id
    )
    
    # Verificar que el cajero tenga acceso a esta transferencia (solo si es de su sucursal)
    if request.user.role == 'CASHIER':
        if transfer.from_branch != request.user.branch and transfer.to_branch != request.user.branch:
            messages.error(request, "No tienes permiso para ver esta transferencia.")
            return redirect('transfer_list')
    
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
    
    # ✅ Seleccionar template según el rol
    if request.user.role == 'CASHIER':
        template_name = 'cajero/transfers/detail.html'
    else:
        template_name = 'admin/transfers/detail.html'
    
    return render(request, template_name, {
        'transfer': transfer,
        'stock_status': stock_status,
        'all_available': all_available,
        'is_cashier': request.user.role == 'CASHIER'
    })


@login_required
@transaction.atomic
def transfer_process(request, transfer_id):
    """Procesar transferencia - Acceso para ADMIN, SUPERADMIN y CAJEROS con permiso"""
    if not user_can_transfer(request.user):
        messages.error(request, "No tienes permiso para procesar transferencias.")
        return redirect('transfer_list')
    
    transfer = get_object_or_404(Transfer, id=transfer_id)
    
    if transfer.status != 'PENDING':
        messages.error(request, 'Esta transferencia ya ha sido procesada.')
        return redirect('transfer_detail', transfer_id=transfer.id)
    
    # Verificar que el cajero tenga acceso a esta transferencia
    if request.user.role == 'CASHIER':
        if transfer.from_branch != request.user.branch:
            messages.error(request, "No tienes permiso para procesar esta transferencia.")
            return redirect('transfer_list')
    
    if request.method == 'POST':
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
        
        for item in transfer.items.all():
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
        return redirect('transfer_list')
    
    return redirect('transfer_detail', transfer_id=transfer.id)


@login_required
def transfer_cancel(request, transfer_id):
    """Cancelar transferencia - Acceso para ADMIN, SUPERADMIN y CAJEROS con permiso"""
    if not user_can_transfer(request.user):
        messages.error(request, "No tienes permiso para acceder a esta página.")
        return redirect('transfer_list')
    
    transfer = get_object_or_404(Transfer, id=transfer_id)
    
    # Verificar que el cajero tenga acceso a esta transferencia (solo si es de su sucursal)
    if request.user.role == 'CASHIER':
        if transfer.from_branch != request.user.branch:
            messages.error(request, "No tienes permiso para cancelar esta transferencia.")
            return redirect('transfer_list')
    
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
        'stock': float(item.stock),
        'description': item.product.description,
        'is_ingredient': item.product.is_ingredient,
    } for item in inventory]
    
    return JsonResponse({'inventory': data})


@login_required
@role_required(['ADMIN', 'SUPERADMIN'])
def inventory_edit(request, inventory_id):
    """Editar un registro de inventario existente"""
    inventory = get_object_or_404(Inventory, id=inventory_id)
    
    if request.method == 'POST':
        form = InventoryForm(request.POST, instance=inventory)
        if form.is_valid():
            form.save()
            messages.success(request, f'✅ Inventario de {inventory.product.name} actualizado correctamente.')
            return redirect('inventory_list')
        else:
            messages.error(request, '❌ Por favor corrige los errores en el formulario.')
    else:
        form = InventoryForm(instance=inventory)
    
    return render(request, 'admin/inventory/edit.html', {
        'form': form,
        'inventory': inventory,
        'is_edit': True
    })