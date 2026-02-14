from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from users.decorators import role_required
from .forms import InventoryForm, TransferForm
from .models import Inventory, InventoryMovement
from django.db import transaction
from .models import Transfer


@login_required
@role_required(['ADMIN', 'SUPERADMIN', 'CASHIER'])
def inventory_list(request):

    user = request.user

    if user.role in ['ADMIN', 'SUPERADMIN']:
        inventory = Inventory.objects.select_related('product', 'branch')

    elif user.role == 'CASHIER':
        inventory = Inventory.objects.select_related(
            'product', 'branch'
        ).filter(branch=user.branch)

    else:
        inventory = Inventory.objects.none()

    return render(request, 'admin/inventory/list.html', {
        'inventory': inventory
    })


@login_required
@role_required(['ADMIN', 'SUPERADMIN'])
def inventory_create(request):

    form = InventoryForm(request.POST or None)

    if form.is_valid():
        inventory = form.save()

        # Crear movimiento automático tipo ENTRADA
        InventoryMovement.objects.create(
            inventory=inventory,
            quantity=inventory.stock,
            movement_type='IN'
        )

        return redirect('inventory_list')

    return render(request, 'admin/inventory/form.html', {
        'form': form
    })

@login_required
@role_required(['ADMIN', 'SUPERADMIN'])
@transaction.atomic
def transfer_create(request):

    form = TransferForm(request.POST or None)

    if form.is_valid():

        transfer = form.save(commit=False)
        transfer.created_by = request.user

        from_inventory = Inventory.objects.filter(
            branch=transfer.from_branch,
            product=transfer.product
        ).first()

        if not from_inventory or from_inventory.stock < transfer.quantity:
            form.add_error(None, "Stock insuficiente en sucursal origen.")
        else:
            # Restar stock origen
            from_inventory.stock -= transfer.quantity
            from_inventory.save()

            InventoryMovement.objects.create(
                inventory=from_inventory,
                quantity=transfer.quantity,
                movement_type='OUT'
            )

            # Obtener o crear inventario destino
            to_inventory, created = Inventory.objects.get_or_create(
                branch=transfer.to_branch,
                product=transfer.product,
                defaults={'stock': 0}
            )

            # Sumar stock destino
            to_inventory.stock += transfer.quantity
            to_inventory.save()

            InventoryMovement.objects.create(
                inventory=to_inventory,
                quantity=transfer.quantity,
                movement_type='IN'
            )

            transfer.save()

            return redirect('transfer_list')

    return render(request, 'admin/transfers/form.html', {'form': form})

@login_required
@role_required(['ADMIN', 'SUPERADMIN'])
def transfer_list(request):

    transfers = Transfer.objects.select_related(
        'from_branch', 'to_branch', 'product'
    ).order_by('-created_at')

    return render(request, 'admin/transfers/list.html', {
        'transfers': transfers
    })
