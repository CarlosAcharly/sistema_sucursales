from django.urls import path
from . import views

app_name = 'cashregister'

urlpatterns = [
    path('', views.cortes_list, name='list'),
    path('iniciar/', views.iniciar_corte, name='iniciar'),
    path('<int:corte_id>/', views.detalle_corte, name='detail'),
    path('<int:corte_id>/cerrar/', views.cerrar_corte, name='cerrar'),
    path('api/<int:corte_id>/', views.resumen_corte_api, name='api'),
    path('<int:corte_id>/contar/', views.contar_dinero, name='contar_dinero'),

    # URLs para administradores
    path('admin/cortes/', views.admin_cortes_list, name='admin_list'),
    path('admin/corte/<int:corte_id>/', views.admin_corte_detail, name='admin_detail'),
    path('admin/corte/<int:corte_id>/exportar/', views.admin_corte_export, name='admin_export'),
]