from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from users.decorators import role_required
from branches.models import Branch
from users.models import User
from products.models import Product
from inventory.models import Inventory
from django.db.models import Sum, Count, Q
from django.utils.timezone import now
from sales.models import Sale
from cashregister.models import CorteCaja
from datetime import timedelta

@login_required
@role_required(['SUPERADMIN'])
def superadmin_dashboard(request):
    today = now().date()

    total_branches = Branch.objects.count()
    total_users = User.objects.count()
    total_products = Product.objects.count()

    # ✅ CORREGIDO: Ventas globales (solo activas)
    total_sales = Sale.objects.filter(status='ACTIVE').count()
    total_revenue = Sale.objects.filter(status='ACTIVE').aggregate(
        total=Sum('total')
    )['total'] or 0

    # ✅ CORREGIDO: Ventas hoy (solo activas)
    sales_today = Sale.objects.filter(
        status='ACTIVE',
        created_at__date=today
    ).aggregate(total=Sum('total'))['total'] or 0

    # ✅ CORREGIDO: Ventas por sucursal (solo activas)
    sales_by_branch = Sale.objects.filter(
        status='ACTIVE'
    ).values(
        'branch__name'
    ).annotate(
        total=Sum('total')
    ).order_by('-total')

    # Inventario bajo global (sin cambios)
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
    today = now().date()
    first_day_month = today.replace(day=1)
    
    # ===== VARIABLES ORIGINALES (INTACTAS) =====
    total_products = Product.objects.count()
    total_inventory = Inventory.objects.count()
    
    # Productos recientes (últimos 5)
    latest_products = Product.objects.order_by('-created_at')[:5]
    
    # Stock bajo (todos los productos con stock bajo, sin filtrar por sucursal)
    low_stock_items = Inventory.objects.filter(stock__lte=5).select_related('product', 'branch')
    
    # ===== NUEVAS VARIABLES PARA CORTES DE CAJA =====
    # Verificar si el usuario tiene sucursal asignada
    user_branch = getattr(request.user, 'branch', None)
    
    if user_branch:
        # ✅ CORREGIDO: Ventas del día (solo activas)
        sales_today = Sale.objects.filter(
            status='ACTIVE',
            branch=user_branch,
            created_at__date=today
        ).aggregate(total=Sum('total'))['total'] or 0
        
        sales_count_today = Sale.objects.filter(
            status='ACTIVE',
            branch=user_branch,
            created_at__date=today
        ).count()
        
        # Cortes activos (sin cambios)
        active_cuts = CorteCaja.objects.filter(
            branch=user_branch,
            estado='ABIERTO'
        )
        active_cuts_count = active_cuts.count()
        
        # ✅ CORREGIDO: Ventas del mes (solo activas)
        monthly_sales = Sale.objects.filter(
            status='ACTIVE',
            branch=user_branch,
            created_at__date__gte=first_day_month,
            created_at__date__lte=today
        ).aggregate(total=Sum('total'))['total'] or 0
        
        # Últimos cortes (5 más recientes) - sin cambios
        recent_cuts = CorteCaja.objects.filter(
            branch=user_branch
        ).select_related('cajero').order_by('-fecha_apertura')[:5]
        
        # Stock bajo por sucursal - sin cambios
        low_stock_by_branch = {
            user_branch.name: low_stock_items.filter(branch=user_branch)
        }
        
        total_inventory_items = Inventory.objects.filter(
            branch=user_branch
        ).aggregate(total=Sum('stock'))['total'] or 0
        
        # Transferencias de la sucursal - sin cambios
        try:
            from transfers.models import Transfer
            total_transfers = Transfer.objects.filter(
                Q(from_branch=user_branch) | Q(to_branch=user_branch)
            ).count()
            pending_transfers = Transfer.objects.filter(
                Q(from_branch=user_branch) | Q(to_branch=user_branch),
                status='PENDING'
            ).count()
        except:
            total_transfers = 0
            pending_transfers = 0
        
        # Dietas de la sucursal - sin cambios
        try:
            from diets.models import Diet
            total_diets = Diet.objects.filter(
                branch=user_branch
            ).count()
            active_diets = Diet.objects.filter(
                branch=user_branch,
                is_active=True
            ).count()
        except:
            total_diets = 0
            active_diets = 0
            
    else:
        # El admin no tiene sucursal asignada - mostrar datos de todas las sucursales
        # ✅ CORREGIDO: Solo ventas activas
        sales_today = Sale.objects.filter(
            status='ACTIVE',
            created_at__date=today
        ).aggregate(total=Sum('total'))['total'] or 0
        
        sales_count_today = Sale.objects.filter(
            status='ACTIVE',
            created_at__date=today
        ).count()
        
        active_cuts_count = CorteCaja.objects.filter(
            estado='ABIERTO'
        ).count()
        
        # ✅ CORREGIDO: Ventas del mes (solo activas)
        monthly_sales = Sale.objects.filter(
            status='ACTIVE',
            created_at__date__gte=first_day_month,
            created_at__date__lte=today
        ).aggregate(total=Sum('total'))['total'] or 0
        
        recent_cuts = CorteCaja.objects.all().select_related(
            'branch', 'cajero'
        ).order_by('-fecha_apertura')[:5]
        
        # Stock bajo agrupado por sucursal - sin cambios
        low_stock_by_branch = {}
        for item in low_stock_items:
            branch_name = item.branch.name if item.branch else "Sin sucursal"
            if branch_name not in low_stock_by_branch:
                low_stock_by_branch[branch_name] = []
            low_stock_by_branch[branch_name].append(item)
        
        total_inventory_items = Inventory.objects.aggregate(
            total=Sum('stock')
        )['total'] or 0
        
        # Transferencias globales - sin cambios
        try:
            from transfers.models import Transfer
            total_transfers = Transfer.objects.count()
            pending_transfers = Transfer.objects.filter(status='PENDING').count()
        except:
            total_transfers = 0
            pending_transfers = 0
        
        # Dietas globales - sin cambios
        try:
            from diets.models import Diet
            total_diets = Diet.objects.count()
            active_diets = Diet.objects.filter(is_active=True).count()
        except:
            total_diets = 0
            active_diets = 0
    
    # Conteo de productos con precio (global) - sin cambios
    products_with_price = Product.objects.exclude(
        Q(price_kg__isnull=True) & 
        Q(price_bulk__isnull=True) & 
        Q(price_wholesale__isnull=True) & 
        Q(price_special__isnull=True)
    ).count()
    
    low_stock_count = low_stock_items.count()
    
    # ===== CONTEXTO COMBINADO =====
    context = {
        # Variables originales
        'total_products': total_products,
        'total_inventory': total_inventory,
        'latest_products': latest_products,
        'low_stock': low_stock_items,
        
        # Nuevas variables para el dashboard mejorado
        'total_sales_today': sales_today,
        'sales_count_today': sales_count_today,
        'active_cuts_count': active_cuts_count,
        'monthly_sales': monthly_sales,
        'recent_cuts': recent_cuts,
        'low_stock_by_branch': low_stock_by_branch,
        'products_with_price': products_with_price,
        'total_inventory_items': total_inventory_items,
        'low_stock_count': low_stock_count,
        'total_transfers': total_transfers,
        'pending_transfers': pending_transfers,
        'total_diets': total_diets,
        'active_diets': active_diets,
        'current_date': now(),
        'total_branches': Branch.objects.count(),
        'user_has_branch': user_branch is not None,
        'user_branch_name': user_branch.name if user_branch else "Todas las sucursales"
    }
    
    return render(request, 'admin/dashboard.html', context)