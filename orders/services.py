from inventory.models import Inventory, InventoryMovement

def complete_order(order):
    """
    Completa un pedido (lo marca como COMPLETED)
    Esta función SOLO cambia el estado, NO modifica el inventario
    """
    if order.status != "PENDING":
        return order
    
    # Solo cambiar el estado, NO agregar al inventario
    order.status = "COMPLETED"
    # NO tocar inventory_added aquí, eso lo hace el cajero
    order.save()
    
    return order