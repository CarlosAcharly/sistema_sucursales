from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from users.decorators import role_required
from branches.models import Branch
from users.models import User
from products.models import Product
from inventory.models import Inventory
from django.db.models import Sum, Count
from django.utils.timezone import now
from sales.models import Sale
from inventory.models import Inventory

@login_required
@role_required(['SUPERADMIN'])
def superadmin_dashboard(request):

    today = now().date()

    total_branches = Branch.objects.count()
    total_users = User.objects.count()
    total_products = Product.objects.count()

    # Ventas globales
    total_sales = Sale.objects.count()
    total_revenue = Sale.objects.aggregate(
        total=Sum('total')
    )['total'] or 0

    # Ventas hoy
    sales_today = Sale.objects.filter(
        created_at__date=today
    ).aggregate(total=Sum('total'))['total'] or 0

    # Ventas por sucursal
    sales_by_branch = Sale.objects.values(
        'branch__name'
    ).annotate(
        total=Sum('total')
    ).order_by('-total')

    # Inventario bajo global
    low_stock = Inventory.objects.filter(stock__lte=5).count()

    context = {
        'total_branches': total_branches,
        'total_users': total_users,
        'total_products': total_products,
        'total_sales': total_sales,
        'total_revenue': total_revenue,
        'sales_today': sales_today,
        'sales_by_branch': sales_by_branch,
        'low_stock': low_stock,
    }

    return render(request, 'superadmin/dashboard.html', context)

@login_required
@role_required(['ADMIN'])
def admin_dashboard(request):

    total_products = Product.objects.count()
    total_inventory = Inventory.objects.count()

    context = {
        'total_products': total_products,
        'total_inventory': total_inventory,
    }

    return render(request, 'admin/dashboard.html', context)

@login_required
@role_required(['CASHIER'])
def pos_view(request):

    products = Inventory.objects.filter(branch=request.user.branch)

    return render(request, 'cajero/pos.html', {'products': products})