from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.db.models import Sum, Avg, Count, Q, F, ExpressionWrapper, DecimalField
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.http import JsonResponse
from datetime import timedelta, datetime
from decimal import Decimal
import json
import calendar

from users.decorators import role_required
from products.models import Product
from branches.models import Branch
from sales.models import Sale, SaleItem
from .models import PurchasePrice, ProfitSummary, ProductProfitability
from .forms import PurchasePriceForm, DateRangeForm


# =============================
# 💰 PRECIOS DE COMPRA
# =============================

@login_required
@role_required(['ADMIN', 'SUPERADMIN'])
def purchase_price_list(request):
    """Lista de precios de compra actuales"""
    branch_id = request.GET.get('branch')
    product_id = request.GET.get('product')
    
    prices = PurchasePrice.objects.filter(is_active=True).select_related('product', 'branch', 'created_by')
    
    if branch_id:
        prices = prices.filter(branch_id=branch_id)
    if product_id:
        prices = prices.filter(product_id=product_id)
    
    # Agrupar por producto para mostrar el precio actual
    current_prices = {}
    for price in prices:
        key = f"{price.product_id}_{price.branch_id}"
        if key not in current_prices:
            current_prices[key] = price
    
    branches = Branch.objects.filter(is_active=True)
    products = Product.objects.filter(is_active=True)
    
    return render(request, 'admin/earnings/purchase_price_list.html', {
        'current_prices': current_prices.values(),
        'branches': branches,
        'products': products,
        'selected_branch': branch_id,
        'selected_product': product_id,
    })


@login_required
@role_required(['ADMIN', 'SUPERADMIN'])
def purchase_price_create(request):
    """Crear nuevo precio de compra"""
    if request.method == 'POST':
        form = PurchasePriceForm(request.POST)
        if form.is_valid():
            price = form.save(commit=False)
            price.created_by = request.user
            price.save()
            messages.success(request, f'Precio de compra actualizado para {price.product.name}')
            return redirect('earnings:purchase_price_list')
    else:
        form = PurchasePriceForm(initial={
            'product': request.GET.get('product'),
            'branch': request.GET.get('branch')
        })
    
    return render(request, 'admin/earnings/purchase_price_form.html', {
        'form': form,
        'title': 'Nuevo Precio de Compra'
    })


@login_required
@role_required(['ADMIN', 'SUPERADMIN'])
def purchase_price_history(request, product_id, branch_id):
    """Historial de precios de un producto en una sucursal"""
    product = get_object_or_404(Product, id=product_id)
    branch = get_object_or_404(Branch, id=branch_id)
    
    prices = PurchasePrice.objects.filter(
        product=product,
        branch=branch
    ).order_by('-valid_from').select_related('created_by')
    
    return render(request, 'admin/earnings/purchase_price_history.html', {
        'product': product,
        'branch': branch,
        'prices': prices
    })


# =============================
# 📊 FUNCIONES AUXILIARES PARA CÁLCULOS
# =============================

def get_purchase_price_at_date(product_id, branch_id, date):
    """Obtiene el precio de compra de un producto en una fecha específica"""
    price = PurchasePrice.objects.filter(
        product_id=product_id,
        branch_id=branch_id,
        valid_from__lte=date
    ).order_by('-valid_from').first()
    
    return price.price if price else Decimal('0')


def calculate_item_profit(item):
    """Calcula la ganancia de un item de venta"""
    # Obtener el precio de compra en la fecha de la venta
    purchase_price = get_purchase_price_at_date(
        item.product_id,
        item.sale.branch_id,
        item.sale.created_at
    )
    
    cost = purchase_price * item.quantity
    revenue = item.price * item.quantity
    profit = revenue - cost
    margin = (profit / revenue * 100) if revenue > 0 else 0
    
    return {
        'cost': cost,
        'revenue': revenue,
        'profit': profit,
        'margin': margin,
        'purchase_price': purchase_price
    }


def calculate_sale_profit(sale):
    """Calcula la ganancia de una venta completa"""
    total_revenue = Decimal('0')
    total_cost = Decimal('0')
    items_data = []
    
    for item in sale.items.all():
        item_profit = calculate_item_profit(item)
        total_revenue += item_profit['revenue']
        total_cost += item_profit['cost']
        items_data.append({
            'item': item,
            **item_profit
        })
    
    total_profit = total_revenue - total_cost
    margin = (total_profit / total_revenue * 100) if total_revenue > 0 else 0
    
    return {
        'revenue': total_revenue,
        'cost': total_cost,
        'profit': total_profit,
        'margin': margin,
        'items': items_data
    }


def get_profit_stats(queryset):
    """Calcula estadísticas de ganancia para un queryset de ventas"""
    total_revenue = Decimal('0')
    total_cost = Decimal('0')
    total_profit = Decimal('0')
    margins = []
    count = 0
    
    for sale in queryset.prefetch_related('items', 'items__product'):
        sale_profit = calculate_sale_profit(sale)
        total_revenue += sale_profit['revenue']
        total_cost += sale_profit['cost']
        total_profit += sale_profit['profit']
        if sale_profit['margin'] is not None:
            margins.append(sale_profit['margin'])
        count += 1
    
    avg_margin = sum(margins) / len(margins) if margins else 0
    
    return {
        'total_sales': total_revenue,
        'total_cost': total_cost,
        'total_profit': total_profit,
        'avg_margin': avg_margin,
        'count': count,
    }


# =============================
# 📊 DASHBOARD DE GANANCIAS
# =============================

@login_required
@role_required(['ADMIN', 'SUPERADMIN'])
def profit_dashboard(request):
    """Dashboard principal de ganancias"""
    today = timezone.now().date()
    
    # Obtener filtros
    branch_id = request.GET.get('branch')
    
    # Query base de ventas
    sales_query = Sale.objects.filter(status='ACTIVE')
    if branch_id:
        sales_query = sales_query.filter(branch_id=branch_id)
    
    # Ventas de hoy
    sales_today = sales_query.filter(created_at__date=today)
    profit_today = get_profit_stats(sales_today)
    
    # Ventas de ayer
    yesterday = today - timedelta(days=1)
    sales_yesterday = sales_query.filter(created_at__date=yesterday)
    profit_yesterday = get_profit_stats(sales_yesterday)
    
    # Ventas de la semana
    week_start = today - timedelta(days=today.weekday())
    sales_week = sales_query.filter(created_at__date__gte=week_start)
    profit_week = get_profit_stats(sales_week)
    
    # Ventas del mes
    month_start = today.replace(day=1)
    sales_month = sales_query.filter(created_at__date__gte=month_start)
    profit_month = get_profit_stats(sales_month)
    
    # Ventas del año
    year_start = today.replace(month=1, day=1)
    sales_year = sales_query.filter(created_at__date__gte=year_start)
    profit_year = get_profit_stats(sales_year)
    
    # Productos más rentables del mes
    top_products = []
    product_stats = {}
    
    # Obtener todas las ventas del mes
    monthly_sales = sales_query.filter(created_at__date__gte=month_start)
    
    for sale in monthly_sales.prefetch_related('items__product'):
        for item in sale.items.all():
            key = item.product_id
            if key not in product_stats:
                product_stats[key] = {
                    'name': item.product.name,
                    'quantity': 0,
                    'revenue': Decimal('0'),
                    'cost': Decimal('0'),
                    'profit': Decimal('0'),
                    'margins': []
                }
            
            purchase_price = get_purchase_price_at_date(
                item.product_id,
                sale.branch_id,
                sale.created_at
            )
            
            item_revenue = item.price * item.quantity
            item_cost = purchase_price * item.quantity
            item_profit = item_revenue - item_cost
            item_margin = (item_profit / item_revenue * 100) if item_revenue > 0 else 0
            
            product_stats[key]['quantity'] += item.quantity
            product_stats[key]['revenue'] += item_revenue
            product_stats[key]['cost'] += item_cost
            product_stats[key]['profit'] += item_profit
            product_stats[key]['margins'].append(item_margin)
    
    # Convertir a lista y ordenar
    for product_id, stats in product_stats.items():
        top_products.append({
            'product__id': product_id,
            'product__name': stats['name'],
            'total_sold': stats['quantity'],
            'total_revenue': stats['revenue'],
            'total_cost': stats['cost'],
            'total_profit': stats['profit'],
            'avg_margin': sum(stats['margins']) / len(stats['margins']) if stats['margins'] else 0
        })
    
    top_products = sorted(top_products, key=lambda x: x['total_profit'], reverse=True)[:10]
    
    # Tendencia diaria (últimos 30 días)
    last_30_days = []
    for i in range(30):
        day = today - timedelta(days=i)
        day_sales = sales_query.filter(created_at__date=day)
        stats = get_profit_stats(day_sales)
        last_30_days.append({
            'date': day.strftime('%d/%m'),
            'profit': float(stats['total_profit']),
            'sales': float(stats['total_sales']),
            'count': stats['count']
        })
    
    # Ventas por hora (hoy)
    hourly_sales = []
    for hour in range(6, 23):  # 6 AM a 10 PM
        hour_sales = sales_today.filter(created_at__hour=hour)
        stats = get_profit_stats(hour_sales)
        hourly_sales.append({
            'hour': f"{hour:02d}:00",
            'profit': float(stats['total_profit']),
            'count': stats['count']
        })
    
    branches = Branch.objects.filter(is_active=True)
    
    # Calcular cambio diario
    daily_change = 0
    if profit_yesterday['total_profit'] > 0:
        daily_change = ((profit_today['total_profit'] - profit_yesterday['total_profit']) / profit_yesterday['total_profit']) * 100
    
    # Promedio semanal
    weekly_avg = profit_week['total_profit'] / 7 if profit_week['count'] > 0 else 0
    
    # Proyección mensual
    monthly_projection = 0
    if today.day > 0 and profit_month['count'] > 0:
        monthly_projection = (profit_month['total_profit'] / today.day) * 30
    
    context = {
        'branches': branches,
        'selected_branch': branch_id,
        
        # Resúmenes
        'profit_today': profit_today,
        'profit_yesterday': profit_yesterday,
        'profit_week': profit_week,
        'profit_month': profit_month,
        'profit_year': profit_year,
        
        # Comparativas
        'daily_change': daily_change,
        'weekly_avg': weekly_avg,
        'monthly_projection': monthly_projection,
        
        # Datos para gráficos
        'top_products': top_products,
        'last_30_days': last_30_days,
        'hourly_sales': hourly_sales,
        
        # JSON para gráficos
        'last_30_days_json': json.dumps(last_30_days),
        'hourly_sales_json': json.dumps(hourly_sales),
        'top_products_json': json.dumps(top_products, default=str),
    }
    
    return render(request, 'admin/earnings/profit_dashboard.html', context)


@login_required
@role_required(['ADMIN', 'SUPERADMIN'])
def profit_report(request):
    """Reporte detallado de ganancias con filtros"""
    form = DateRangeForm(request.GET or {'period': 'month'})
    report_data = None
    
    if form.is_valid():
        period = form.cleaned_data['period']
        branch = form.cleaned_data['branch']
        
        # Determinar rango de fechas
        today = timezone.now().date()
        
        if period == 'today':
            date_from = today
            date_to = today
        elif period == 'yesterday':
            date_from = today - timedelta(days=1)
            date_to = date_from
        elif period == 'week':
            date_from = today - timedelta(days=today.weekday())
            date_to = today
        elif period == 'month':
            date_from = today.replace(day=1)
            date_to = today
        else:  # custom
            date_from = form.cleaned_data['date_from']
            date_to = form.cleaned_data['date_to'] or today
        
        if date_from and date_to:
            # Obtener ventas en el rango
            sales_query = Sale.objects.filter(
                status='ACTIVE',
                created_at__date__gte=date_from,
                created_at__date__lte=date_to
            ).order_by('-created_at')
            
            if branch:
                sales_query = sales_query.filter(branch=branch)
            
            sales = sales_query.prefetch_related('items__product')
            
            # Estadísticas generales
            stats = get_profit_stats(sales)
            
            # Ventas por día
            daily_stats = []
            current_date = date_from
            while current_date <= date_to:
                day_sales = sales_query.filter(created_at__date=current_date)
                day_stats = get_profit_stats(day_sales)
                if day_stats['count'] > 0:
                    daily_stats.append({
                        'date': current_date,
                        'stats': day_stats
                    })
                current_date += timedelta(days=1)
            
            # Productos en el período
            products_stats = []
            product_totals = {}
            
            for sale in sales:
                for item in sale.items.all():
                    key = item.product_id
                    if key not in product_totals:
                        product_totals[key] = {
                            'name': item.product.name,
                            'quantity': 0,
                            'revenue': Decimal('0'),
                            'cost': Decimal('0'),
                            'profit': Decimal('0'),
                            'margins': []
                        }
                    
                    purchase_price = get_purchase_price_at_date(
                        item.product_id,
                        sale.branch_id,
                        sale.created_at
                    )
                    
                    item_revenue = item.price * item.quantity
                    item_cost = purchase_price * item.quantity
                    item_profit = item_revenue - item_cost
                    item_margin = (item_profit / item_revenue * 100) if item_revenue > 0 else 0
                    
                    product_totals[key]['quantity'] += item.quantity
                    product_totals[key]['revenue'] += item_revenue
                    product_totals[key]['cost'] += item_cost
                    product_totals[key]['profit'] += item_profit
                    product_totals[key]['margins'].append(item_margin)
            
            for product_id, totals in product_totals.items():
                products_stats.append({
                    'product__id': product_id,
                    'product__name': totals['name'],
                    'quantity': totals['quantity'],
                    'revenue': totals['revenue'],
                    'cost': totals['cost'],
                    'profit': totals['profit'],
                    'margin': sum(totals['margins']) / len(totals['margins']) if totals['margins'] else 0
                })
            
            products_stats = sorted(products_stats, key=lambda x: x['profit'], reverse=True)
            
            report_data = {
                'date_from': date_from,
                'date_to': date_to,
                'branch': branch,
                'stats': stats,
                'daily_stats': daily_stats,
                'products_stats': products_stats,
                'sales': sales[:50],  # Últimas 50 ventas
            }
    
    return render(request, 'admin/earnings/profit_report.html', {
        'form': form,
        'report': report_data
    })


@login_required
@role_required(['ADMIN', 'SUPERADMIN'])
def profit_by_product(request):
    """Análisis de rentabilidad por producto"""
    branch_id = request.GET.get('branch')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    if not date_from:
        date_from = (timezone.now().date() - timedelta(days=30)).isoformat()
    if not date_to:
        date_to = timezone.now().date().isoformat()
    
    date_from_obj = datetime.strptime(date_from, '%Y-%m-%d').date()
    date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').date()
    
    # Obtener ventas en el rango
    sales_query = Sale.objects.filter(
        status='ACTIVE',
        created_at__date__gte=date_from_obj,
        created_at__date__lte=date_to_obj
    ).prefetch_related('items__product')
    
    if branch_id:
        sales_query = sales_query.filter(branch_id=branch_id)
    
    # Calcular estadísticas por producto
    product_stats = {}
    total_revenue = Decimal('0')
    total_cost = Decimal('0')
    total_profit = Decimal('0')
    
    for sale in sales_query:
        for item in sale.items.all():
            key = item.product_id
            if key not in product_stats:
                product_stats[key] = {
                    'product__id': item.product_id,
                    'product__name': item.product.name,
                    'product__description': item.product.description,
                    'units_sold': 0,
                    'transactions': set(),
                    'revenue': Decimal('0'),
                    'cost': Decimal('0'),
                    'profit': Decimal('0'),
                    'margins': [],
                    'sale_prices': [],
                    'purchase_prices': []
                }
            
            purchase_price = get_purchase_price_at_date(
                item.product_id,
                sale.branch_id,
                sale.created_at
            )
            
            item_revenue = item.price * item.quantity
            item_cost = purchase_price * item.quantity
            item_profit = item_revenue - item_cost
            item_margin = (item_profit / item_revenue * 100) if item_revenue > 0 else 0
            
            product_stats[key]['units_sold'] += item.quantity
            product_stats[key]['transactions'].add(sale.id)
            product_stats[key]['revenue'] += item_revenue
            product_stats[key]['cost'] += item_cost
            product_stats[key]['profit'] += item_profit
            product_stats[key]['margins'].append(item_margin)
            product_stats[key]['sale_prices'].append(item.price)
            product_stats[key]['purchase_prices'].append(purchase_price)
            
            total_revenue += item_revenue
            total_cost += item_cost
            total_profit += item_profit
    
    # Convertir a lista y calcular promedios
    products_list = []
    for stats in product_stats.values():
        stats['transactions'] = len(stats['transactions'])
        stats['avg_margin'] = sum(stats['margins']) / len(stats['margins']) if stats['margins'] else 0
        stats['avg_sale_price'] = sum(stats['sale_prices']) / len(stats['sale_prices']) if stats['sale_prices'] else 0
        stats['avg_cost_price'] = sum(stats['purchase_prices']) / len(stats['purchase_prices']) if stats['purchase_prices'] else 0
        products_list.append(stats)
    
    products_list = sorted(products_list, key=lambda x: x['profit'], reverse=True)
    
    branches = Branch.objects.filter(is_active=True)
    
    return render(request, 'admin/earnings/profit_by_product.html', {
        'products_stats': products_list,
        'totals': {
            'total_revenue': total_revenue,
            'total_cost': total_cost,
            'total_profit': total_profit,
        },
        'branches': branches,
        'selected_branch': branch_id,
        'date_from': date_from,
        'date_to': date_to,
    })