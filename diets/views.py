from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.forms import modelformset_factory
from .models import DietCajero, DietCajeroItem, DietBaseIngredient, Diet
from branches.models import Branch
from products.models import Product
from users.decorators import role_required

@login_required
@role_required(['ADMIN'])
def diet_list(request):
    diets = Diet.objects.all()
    return render(request, "admin/diets/list.html", {"diets": diets})

@login_required
@role_required(['ADMIN'])
def diet_create(request):
    # ✅ Cambiar extra a 5 y permitir hasta 50 formularios
    IngredientFormSet = modelformset_factory(
        DietBaseIngredient,
        fields=("product", "kilos"),
        extra=10,
        can_delete=True,
        max_num=50,
        validate_max=False
    )

    # ✅ Obtener productos que son ingredientes
    products = Product.objects.filter(is_active=True, is_ingredient=True)

    if request.method == "POST":
        name = request.POST.get("name")
        description = request.POST.get("description")
        branches_ids = request.POST.getlist("branches")

        formset = IngredientFormSet(request.POST, queryset=DietBaseIngredient.objects.none())

        if formset.is_valid():
            total = 0
            valid_ingredients = 0
            for form in formset:
                if form.cleaned_data and not form.cleaned_data.get("DELETE", False):
                    total += form.cleaned_data.get("kilos", 0)
                    valid_ingredients += 1

            print(f"Total: {total}, Ingredientes válidos: {valid_ingredients}")  # Debug

            if total != 1000:
                messages.error(request, f"La suma debe ser exactamente 1000 kg. Actual: {total} kg")
                return render(request, "admin/diets/form.html", {
                    "formset": formset,
                    "branches": Branch.objects.all(),
                    "products": products,
                })

            if valid_ingredients == 0:
                messages.error(request, "Debes agregar al menos un ingrediente")
                return render(request, "admin/diets/form.html", {
                    "formset": formset,
                    "branches": Branch.objects.all(),
                    "products": products,
                })

            # Crear dieta base
            diet = Diet.objects.create(
                name=name,
                description=description,
                created_by=request.user
            )

            # Asignar sucursales
            diet.branches.set(branches_ids)

            # Crear ingredientes base
            for form in formset:
                if form.cleaned_data and not form.cleaned_data.get("DELETE", False):
                    ingredient = form.save(commit=False)
                    ingredient.diet = diet
                    ingredient.save()

            # Crear dietas para cajeros
            for branch_id in branches_ids:
                branch = Branch.objects.get(id=branch_id)
                diet_cajero = DietCajero.objects.create(
                    diet_base=diet,
                    branch=branch,
                    created_by=request.user
                )
                
                base_ingredients = DietBaseIngredient.objects.filter(diet=diet)
                for base_ing in base_ingredients:
                    DietCajeroItem.objects.create(
                        diet=diet_cajero,
                        product=base_ing.product,
                        kilos=float(base_ing.kilos)
                    )

            messages.success(request, "Dieta creada correctamente y asignada a cajeros.")
            return redirect("diets:diet_list")

    else:
        formset = IngredientFormSet(queryset=DietBaseIngredient.objects.none())

    return render(request, "admin/diets/form.html", {
        "formset": formset,
        "branches": Branch.objects.all(),
        "products": products,
    })

@login_required
@role_required(['CASHIER'])
def diet_cajero_view(request, diet_id, branch_id):
    diet = get_object_or_404(DietCajero, id=diet_id, branch_id=branch_id)
    items = diet.items.select_related('product').all()

    if request.method == 'POST':
        updated = {}
        for item in items:
            value = request.POST.get(f'kilos_{item.id}')
            if value:
                updated[item.id] = float(value)

        # Aplicar proporcionalidad solo al primer editado
        for item in items:
            base_value = item.diet.diet_base.base_ingredients.get(product=item.product).kilos
            if item.id in updated:
                factor = updated[item.id] / base_value
                for i in items:
                    base_i = i.diet.diet_base.base_ingredients.get(product=i.product).kilos
                    i.kilos = round(base_i * factor, 2)
                    i.save()
                break

        return redirect('diets:diet_cajero_view', diet_id=diet.id, branch_id=branch_id)

    return render(request, 'cajero/diets/view.html', {
        'diet': diet,
        'items': items,
    })

@login_required
@role_required(['CASHIER'])
def diet_cajero_list(request):
    branch = request.user.branch
    diets = DietCajero.objects.filter(branch=branch).select_related('diet_base', 'created_by')
    return render(request, "cajero/diets/list.html", {"diets": diets})

@login_required
@role_required(['ADMIN'])
def diet_detail(request, pk):
    """Ver detalles de una dieta específica"""
    diet = get_object_or_404(Diet, pk=pk)
    
    # Calcular estadísticas
    ingredients_count = diet.base_ingredients.count()
    branches_count = diet.branches.count()
    
    return render(request, 'admin/diets/detail.html', {
        'diet': diet,
        'ingredients_count': ingredients_count,
        'branches_count': branches_count,
    })

@login_required
@role_required(['ADMIN'])
def diet_edit(request, pk):
    """Editar una dieta existente"""
    diet = get_object_or_404(Diet, pk=pk)
    
    IngredientFormSet = modelformset_factory(
        DietBaseIngredient,
        fields=("product", "kilos"),
        extra=10,
        can_delete=True,
        max_num=50,
        validate_max=False
    )
    
    products = Product.objects.filter(is_active=True, is_ingredient=True)
    
    if request.method == "POST":
        name = request.POST.get("name")
        description = request.POST.get("description")
        branches_ids = request.POST.getlist("branches")
        
        formset = IngredientFormSet(
            request.POST,
            queryset=DietBaseIngredient.objects.filter(diet=diet)
        )
        
        if formset.is_valid():
            total = 0
            valid_ingredients = 0
            saved_ingredients = []  # Lista para almacenar los objetos guardados
            
            for form in formset:
                if form.cleaned_data and not form.cleaned_data.get("DELETE", False):
                    kilos = form.cleaned_data.get("kilos", 0)
                    if kilos and kilos > 0:
                        total += kilos
                        valid_ingredients += 1
            
            if abs(total - 1000) > 0.01:
                messages.error(request, f"La suma debe ser exactamente 1000 kg. Actual: {total:.2f} kg")
                return render(request, "admin/diets/edit.html", {
                    "diet": diet,
                    "formset": formset,
                    "branches": Branch.objects.filter(is_active=True),
                    "products": products,
                })
            
            if valid_ingredients == 0:
                messages.error(request, "Debes agregar al menos un ingrediente")
                return render(request, "admin/diets/edit.html", {
                    "diet": diet,
                    "formset": formset,
                    "branches": Branch.objects.filter(is_active=True),
                    "products": products,
                })
            
            # Actualizar dieta base
            diet.name = name
            diet.description = description
            diet.save()
            
            # Actualizar sucursales
            diet.branches.set(branches_ids)
            
            # Guardar los nuevos ingredientes base y guardar sus IDs
            saved_product_ids = []  # Lista de IDs de productos guardados
            
            for form in formset:
                if form.cleaned_data and not form.cleaned_data.get("DELETE", False):
                    if form.cleaned_data.get("product") and form.cleaned_data.get("kilos", 0) > 0:
                        ingredient = form.save(commit=False)
                        ingredient.diet = diet
                        ingredient.save()
                        saved_ingredients.append(ingredient)
                        saved_product_ids.append(ingredient.product_id)
                elif form.cleaned_data.get("DELETE", False) and form.instance.pk:
                    form.instance.delete()
            
            # ========== ACTUALIZAR DIETAS DE CAJEROS ==========
            # Obtener todas las dietas de cajero asociadas a esta dieta base
            dietas_cajero = DietCajero.objects.filter(diet_base=diet)
            
            for diet_cajero in dietas_cajero:
                # Para cada dieta de cajero, actualizar sus items
                for base_ing in saved_ingredients:
                    # Buscar si ya existe un item para este producto en la dieta del cajero
                    item, created = DietCajeroItem.objects.get_or_create(
                        diet=diet_cajero,
                        product=base_ing.product,
                        defaults={'kilos': float(base_ing.kilos)}
                    )
                    if not created:
                        # Si ya existe, actualizar los kilos
                        item.kilos = float(base_ing.kilos)
                        item.save()
                
                # Eliminar items de productos que ya no están en la dieta base
                for item in diet_cajero.items.all():
                    if item.product_id not in saved_product_ids:
                        item.delete()
            
            # ========== ACTUALIZAR DIETAS PARA NUEVAS SUCURSALES ==========
            for branch_id in branches_ids:
                branch = Branch.objects.get(id=branch_id)
                diet_cajero, created = DietCajero.objects.get_or_create(
                    diet_base=diet,
                    branch=branch,
                    defaults={'created_by': request.user}
                )
                
                if created:
                    # Si es nueva, crear todos los items
                    for base_ing in saved_ingredients:
                        DietCajeroItem.objects.create(
                            diet=diet_cajero,
                            product=base_ing.product,
                            kilos=float(base_ing.kilos)
                        )
            
            # Eliminar dietas de cajero para sucursales que ya no están asignadas
            DietCajero.objects.filter(diet_base=diet).exclude(branch_id__in=branches_ids).delete()
            
            messages.success(request, f'Dieta "{diet.name}" actualizada correctamente.')
            return redirect("diets:diet_detail", pk=diet.pk)
        else:
            messages.error(request, "Error en los datos del formulario. Verifica los ingredientes.")
            return render(request, "admin/diets/edit.html", {
                "diet": diet,
                "formset": formset,
                "branches": Branch.objects.filter(is_active=True),
                "products": products,
            })
    else:
        formset = IngredientFormSet(queryset=DietBaseIngredient.objects.filter(diet=diet))
    
    return render(request, "admin/diets/edit.html", {
        "diet": diet,
        "formset": formset,
        "branches": Branch.objects.filter(is_active=True),
        "products": products,
    })