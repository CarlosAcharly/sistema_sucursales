from inventory.models import Inventory, InventoryMovement

def complete_order(order):

    for item in order.items.all():

        inventory, created = Inventory.objects.get_or_create(
            branch=order.branch,
            product=item.product,
            defaults={"stock": 0}
        )

        inventory.stock += int(item.kilos)
        inventory.save()

        InventoryMovement.objects.create(
            inventory=inventory,
            quantity=int(item.kilos),
            movement_type="IN"
        )

    order.status = "COMPLETED"
    order.save()
