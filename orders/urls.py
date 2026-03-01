from django.urls import path
from . import views

app_name = "orders"

urlpatterns = [
    # Cajero
    path("nuevo/", views.create_order, name="create_order"),
    path("mis-pedidos/", views.cashier_orders, name="cashier_orders"),
    path("api/<int:order_id>/", views.order_detail_api, name="order_detail_api"),
    path("<int:order_id>/cancelar/", views.cancel_order, name="cancel_order"),
    path("<int:order_id>/agregar-inventario/", views.add_order_to_inventory, name="add_order_to_inventory"),

    # Admin
    path("admin/", views.admin_orders, name="admin_orders"),
    path("admin/<int:order_id>/aprobar/", views.approve_order, name="approve_order"),
    path("item/<int:item_id>/eliminar/", views.delete_order_item, name="delete_item"),
    path("item/<int:item_id>/actualizar/", views.update_order_item, name="update_item"),
    path("admin/<int:order_id>/batch-update/", views.batch_update_order, name="batch_update_order"),
]