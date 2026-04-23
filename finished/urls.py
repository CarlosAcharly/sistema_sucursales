# finished/urls.py
from django.urls import path
from . import views

app_name = 'finished'

urlpatterns = [
    # URLs para CAJERO
    path('', views.recipe_list, name='recipe_list'),
    path('<int:recipe_id>/', views.recipe_detail, name='recipe_detail'),
    path('<int:recipe_id>/produce/', views.produce_recipe, name='produce_recipe'),
    
    # ✅ URLs para ADMIN
    path('admin/', views.admin_recipe_list, name='admin_finished_recipe_list'),
    path('admin/create/', views.admin_recipe_create, name='admin_finished_recipe_create'),
    path('admin/<int:recipe_id>/', views.admin_recipe_detail, name='admin_finished_recipe_detail'),
    path('admin/<int:recipe_id>/edit/', views.admin_recipe_edit, name='admin_finished_recipe_edit'),
    path('admin/<int:recipe_id>/toggle-status/', views.admin_recipe_toggle_status, name='admin_finished_recipe_toggle_status'),
]