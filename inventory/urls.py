from django.urls import path
from . import views

urlpatterns = [
    path('', views.inventory_list, name='inventory_list'),
    path('create/', views.inventory_create, name='inventory_create'),
    path('transfers/', views.transfer_list, name='transfer_list'),
    path('transfers/create/', views.transfer_create, name='transfer_create'),

]
