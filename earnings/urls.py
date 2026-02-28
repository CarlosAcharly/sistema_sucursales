from django.urls import path
from . import views

app_name = 'earnings'

urlpatterns = [
    # Precios de compra
    path('purchase-prices/', views.purchase_price_list, name='purchase_price_list'),
    path('purchase-prices/create/', views.purchase_price_create, name='purchase_price_create'),
    path('purchase-prices/history/<int:product_id>/<int:branch_id>/', views.purchase_price_history, name='purchase_price_history'),
    
    # Dashboard de ganancias
    path('dashboard/', views.profit_dashboard, name='profit_dashboard'),
    path('report/', views.profit_report, name='profit_report'),
    path('by-product/', views.profit_by_product, name='profit_by_product'),
]