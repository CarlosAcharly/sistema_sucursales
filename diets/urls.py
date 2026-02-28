from django.urls import path
from . import views

app_name = "diets"

urlpatterns = [
    # Admin
    path("", views.diet_list, name="diet_list"),
    path("nuevo/", views.diet_create, name="diet_create"),
    path('<int:pk>/', views.diet_detail, name='diet_detail'),
    path('<int:pk>/edit/', views.diet_edit, name='diet_edit'),

    # Cajero
    path("cajero/", views.diet_cajero_list, name="diets_cajero_list"),
    path("cajero/<int:diet_id>/<int:branch_id>/", views.diet_cajero_view, name="diet_cajero_view"),
]
