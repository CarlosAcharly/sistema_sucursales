from django.urls import path
from . import views

app_name = 'sales'  # IMPORTANTE: Agregar el namespace

urlpatterns = [
    # Cajero
    path('pos/', views.pos_view, name='pos'),
    path('', views.sales_list, name='sales_list'),
    path('dashboard/', views.cajero_dashboard, name='cajero_dashboard'),
    path('api/<int:sale_id>/', views.sale_detail_api, name='sale_detail_api'),
    
    # Admin - Nuevas rutas
    path('admin/', views.admin_sales_list, name='admin_sales_list'),
    path('admin/<int:sale_id>/', views.admin_sale_detail, name='admin_sale_detail'),
    path('admin/<int:sale_id>/cancelar/', views.cancel_sale, name='cancel_sale'),
]