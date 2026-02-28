from django.urls import path
from . import views

urlpatterns = [
    path('', views.inventory_list, name='inventory_list'),
    path('create/', views.inventory_create, name='inventory_create'),
    
    # Transferencias
    path('transfers/', views.transfer_list, name='transfer_list'),
    path('transfers/create/', views.transfer_create, name='transfer_create'),
    path('transfers/<int:transfer_id>/', views.transfer_detail, name='transfer_detail'),
    path('transfers/<int:transfer_id>/process/', views.transfer_process, name='transfer_process'),
    path('transfers/<int:transfer_id>/cancel/', views.transfer_cancel, name='transfer_cancel'),
    
    # API
    path('api/branch-inventory/', views.get_branch_inventory, name='branch_inventory_api'),
]