from django.urls import path
from . import views

app_name = 'users'

urlpatterns = [
    path('usuarios/', views.user_list, name='user_list'),
    path('usuarios/nuevo/', views.user_create, name='user_create'),
    path('usuarios/<int:pk>/editar/', views.user_update, name='user_update'),
]
