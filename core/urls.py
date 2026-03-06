"""
URL configuration for core project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from users.views import redirect_by_role
from dashboard.views import superadmin_dashboard, admin_dashboard
from sales.views import pos_view
from django.urls import include
from django.contrib.auth import views as auth_views
from . import views


urlpatterns = [
    path('', views.landing_page, name='landing'),

    path('admin/', admin.site.urls),
    path('redirect/', redirect_by_role, name='redirect'),
    path('superadmin/', superadmin_dashboard, name='superadmin_dashboard'),
    path('panel-admin/', admin_dashboard, name='admin_dashboard'),
    path('sales/', include('sales.urls')),
    path('products/', include('products.urls')),
    path('inventory/', include('inventory.urls')),
    path('branches/', include('branches.urls')),
    path('users/', include('users.urls')),
    path("dietas/", include("diets.urls")),
    path("orders/", include("orders.urls")),
    path('cashregister/', include('cashregister.urls')),
    path("earnings/", include("earnings.urls")),



    path('login/', auth_views.LoginView.as_view(template_name='login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),


]
