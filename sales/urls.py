from django.urls import path
from . import views

urlpatterns = [
    path('pos/', views.pos_view, name='pos'),
    path('', views.sales_list, name='sales_list'),
    path('dashboard/', views.cajero_dashboard, name='cajero_dashboard'),

]
