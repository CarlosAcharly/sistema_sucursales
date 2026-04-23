# finished/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from decimal import Decimal
from users.decorators import role_required
from .models import FinishedRecipe, FinishedRecipeIngredient, FinishedProduction
from products.models import Product
from inventory.models import Inventory, InventoryMovement
from django.forms import inlineformset_factory
from .forms import FinishedRecipeForm


# =============================
# VISTAS PARA CAJERO
# =============================

@login_required
@role_required(['CASHIER'])
def recipe_list(request):
    """Lista de recetas disponibles para la sucursal"""
    if not request.user.branch.can_manage_finished:
        messages.error(request, "Tu sucursal no tiene permiso para gestionar productos terminados.")
        return redirect('sales:cajero_dashboard')
    
    recipes = FinishedRecipe.objects.filter(is_active=True, deleted=False).order_by('name')
    
    return render(request, 'cajero/finished/recipe_list.html', {
        'recipes': recipes
    })


@login_required
@role_required(['CASHIER'])
def recipe_detail(request, recipe_id):
    """Detalle de una receta (ingredientes y producción)"""
    if not request.user.branch.can_manage_finished:
        messages.error(request, "Tu sucursal no tiene permiso para gestionar productos terminados.")
        return redirect('sales:cajero_dashboard')
    
    recipe = get_object_or_404(FinishedRecipe, id=recipe_id, is_active=True, deleted=False)
    ingredients = recipe.ingredients.select_related('product').all()
    
    # Verificar stock disponible de cada ingrediente
    stock_status = []
    all_available = True
    
    for ingredient in ingredients:
        inventory = Inventory.objects.filter(
            branch=request.user.branch,
            product=ingredient.product
        ).first()
        
        available_stock = inventory.stock if inventory else 0
        is_available = available_stock >= ingredient.kilos
        
        stock_status.append({
            'product': ingredient.product,
            'required': float(ingredient.kilos),
            'available': float(available_stock),
            'is_available': is_available
        })
        
        if not is_available:
            all_available = False
    
    # Historial de producciones
    productions = FinishedProduction.objects.filter(
        recipe=recipe,
        branch=request.user.branch
    ).order_by('-produced_at')[:10]
    
    return render(request, 'cajero/finished/recipe_detail.html', {
        'recipe': recipe,
        'ingredients': ingredients,
        'stock_status': stock_status,
        'all_available': all_available,
        'productions': productions,
        'total_kg': recipe.total_kg()
    })


@login_required
@role_required(['CASHIER'])
@transaction.atomic
def produce_recipe(request, recipe_id):
    """Producir una receta (descontar ingredientes, agregar producto terminado)"""
    if request.method != 'POST':
        return redirect('finished:recipe_list')
    
    if not request.user.branch.can_manage_finished:
        messages.error(request, "Tu sucursal no tiene permiso para gestionar productos terminados.")
        return redirect('sales:cajero_dashboard')
    
    recipe = get_object_or_404(FinishedRecipe, id=recipe_id, is_active=True, deleted=False)
    ingredients = recipe.ingredients.select_related('product').all()
    
    if not ingredients.exists():
        messages.error(request, "Esta receta no tiene ingredientes configurados.")
        return redirect('finished:recipe_detail', recipe_id=recipe.id)
    
    quantity = Decimal(str(recipe.total_kg()))
    notes = request.POST.get('notes', '')
    
    # Validar stock de todos los ingredientes
    for ingredient in ingredients:
        inventory = Inventory.objects.filter(
            branch=request.user.branch,
            product=ingredient.product
        ).first()
        
        if not inventory or inventory.stock < ingredient.kilos:
            messages.error(
                request,
                f"Stock insuficiente para {ingredient.product.name}. "
                f"Disponible: {inventory.stock if inventory else 0} kg, Requerido: {ingredient.kilos} kg"
            )
            return redirect('finished:recipe_detail', recipe_id=recipe.id)
    
    # 1. Descontar ingredientes del inventario
    for ingredient in ingredients:
        inventory = Inventory.objects.get(
            branch=request.user.branch,
            product=ingredient.product
        )
        inventory.stock -= ingredient.kilos
        inventory.save()
        
        InventoryMovement.objects.create(
            inventory=inventory,
            quantity=-ingredient.kilos,
            movement_type='PRODUCTION_OUT'
        )
    
    # 2. Agregar producto terminado al inventario
    finished_product = recipe.finished_product
    inventory_finished, created = Inventory.objects.get_or_create(
        branch=request.user.branch,
        product=finished_product,
        defaults={'stock': 0}
    )
    inventory_finished.stock += quantity
    inventory_finished.save()
    
    InventoryMovement.objects.create(
        inventory=inventory_finished,
        quantity=quantity,
        movement_type='PRODUCTION_IN'
    )
    
    # 3. Registrar la producción
    FinishedProduction.objects.create(
        recipe=recipe,
        branch=request.user.branch,
        produced_by=request.user,
        quantity=quantity,
        notes=notes
    )
    
    messages.success(
        request,
        f"✅ '{recipe.name}' producido correctamente. "
        f"Se produjeron {quantity} kg de {finished_product.name}."
    )
    
    return redirect('finished:recipe_list')


# =============================
# VISTAS PARA ADMINISTRADOR
# =============================

@login_required
@role_required(['ADMIN', 'SUPERADMIN'])
def admin_recipe_list(request):
    """Lista de recetas para administrador"""
    recipes = FinishedRecipe.objects.filter(deleted=False).order_by('name')
    return render(request, 'admin/finished/list.html', {'recipes': recipes})


@login_required
@role_required(['ADMIN', 'SUPERADMIN'])
def admin_recipe_detail(request, recipe_id):
    """Detalle de receta para administrador"""
    recipe = get_object_or_404(FinishedRecipe, id=recipe_id, deleted=False)
    ingredients = recipe.ingredients.select_related('product').all()
    productions = FinishedProduction.objects.filter(recipe=recipe).order_by('-produced_at')[:50]
    
    return render(request, 'admin/finished/detail.html', {
        'recipe': recipe,
        'ingredients': ingredients,
        'productions': productions
    })


@login_required
@role_required(['ADMIN', 'SUPERADMIN'])
def admin_recipe_create(request):
    """Crear nueva receta"""
    IngredientFormSet = inlineformset_factory(
        FinishedRecipe,
        FinishedRecipeIngredient,
        fields=['product', 'kilos'],
        extra=1,
        can_delete=True
    )
    
    if request.method == 'POST':
        form = FinishedRecipeForm(request.POST)
        formset = IngredientFormSet(request.POST, instance=FinishedRecipe())
        
        if form.is_valid() and formset.is_valid():
            recipe = form.save(commit=False)
            recipe.created_by = request.user
            recipe.save()
            formset.instance = recipe
            formset.save()
            
            messages.success(request, f'✅ Receta "{recipe.name}" creada correctamente.')
            return redirect('finished:admin_finished_recipe_detail', recipe_id=recipe.id)
        else:
            if form.errors:
                messages.error(request, f'Error en el formulario: {form.errors}')
            if formset.errors:
                messages.error(request, f'Error en ingredientes: {formset.errors}')
    else:
        form = FinishedRecipeForm()
        formset = IngredientFormSet(instance=FinishedRecipe())
    
    ingredients_list = Product.objects.filter(is_ingredient=True, is_active=True).order_by('name')
    
    return render(request, 'admin/finished/form.html', {
        'form': form,
        'ingredient_formset': formset,
        'ingredients_list': ingredients_list
    })


@login_required
@role_required(['ADMIN', 'SUPERADMIN'])
def admin_recipe_edit(request, recipe_id):
    """Editar receta existente"""
    recipe = get_object_or_404(FinishedRecipe, id=recipe_id, deleted=False)
    
    IngredientFormSet = inlineformset_factory(
        FinishedRecipe,
        FinishedRecipeIngredient,
        fields=['product', 'kilos'],
        extra=1,
        can_delete=True
    )
    
    if request.method == 'POST':
        form = FinishedRecipeForm(request.POST, instance=recipe)
        formset = IngredientFormSet(request.POST, instance=recipe)
        
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            messages.success(request, f'✅ Receta "{recipe.name}" actualizada correctamente.')
            return redirect('finished:admin_finished_recipe_detail', recipe_id=recipe.id)
        else:
            if form.errors:
                messages.error(request, f'Error en el formulario: {form.errors}')
            if formset.errors:
                messages.error(request, f'Error en ingredientes: {formset.errors}')
    else:
        form = FinishedRecipeForm(instance=recipe)
        formset = IngredientFormSet(instance=recipe)
    
    ingredients_list = Product.objects.filter(is_ingredient=True, is_active=True).order_by('name')
    
    return render(request, 'admin/finished/form.html', {
        'form': form,
        'ingredient_formset': formset,
        'ingredients_list': ingredients_list,
        'is_edit': True
    })


@login_required
@role_required(['ADMIN', 'SUPERADMIN'])
def admin_recipe_toggle_status(request, recipe_id):
    """Activar/Desactivar receta"""
    recipe = get_object_or_404(FinishedRecipe, id=recipe_id, deleted=False)
    
    if request.method == 'POST':
        recipe.is_active = not recipe.is_active
        recipe.save()
        status = "activada" if recipe.is_active else "desactivada"
        messages.success(request, f'✅ Receta "{recipe.name}" {status} correctamente.')
    
    return redirect('finished:admin_finished_recipe_detail', recipe_id=recipe.id)


@login_required
@role_required(['ADMIN', 'SUPERADMIN'])
def admin_recipe_delete(request, recipe_id):
    """Eliminación lógica de receta"""
    recipe = get_object_or_404(FinishedRecipe, id=recipe_id, deleted=False)
    
    if request.method == 'POST':
        recipe_name = recipe.name
        recipe.soft_delete()
        messages.success(request, f'✅ Receta "{recipe_name}" eliminada correctamente.')
        return redirect('finished:admin_finished_recipe_list')
    
    return redirect('finished:admin_finished_recipe_list')


@login_required
@role_required(['ADMIN', 'SUPERADMIN'])
def admin_productions_list(request):
    """Lista de todas las producciones (admin)"""
    productions = FinishedProduction.objects.select_related(
        'recipe', 'branch', 'produced_by'
    ).order_by('-produced_at')[:100]
    
    return render(request, 'admin/finished/productions.html', {
        'productions': productions
    })