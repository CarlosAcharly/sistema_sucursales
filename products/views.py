from django.contrib import messages  
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from users.decorators import role_required
from .models import Product
from .forms import ProductForm

@login_required
@role_required(['ADMIN'])
def product_list(request):
    products = Product.objects.all()
    return render(request, 'admin/products/list.html', {'products': products})


@login_required
@role_required(['ADMIN'])
def product_create(request):
    form = ProductForm(request.POST or None)

    if form.is_valid():
        form.save()
        return redirect('product_list')

    return render(request, 'admin/products/form.html', {'form': form})


@login_required
@role_required(['ADMIN'])
def product_edit(request, pk):
    product = get_object_or_404(Product, pk=pk)
    form = ProductForm(request.POST or None, instance=product)

    if form.is_valid():
        form.save()
        return redirect('product_list')

    return render(request, 'admin/products/form.html', {'form': form})


@login_required
@role_required(['ADMIN'])
def product_delete(request, pk):
    product = get_object_or_404(Product, pk=pk)
    
    # Solo permitir eliminación por método POST
    if request.method == 'POST':
        product_name = product.name
        product.delete()
        messages.success(request, f'Producto "{product_name}" eliminado exitosamente.')
        return redirect('product_list')
    
    # Si alguien intenta acceder por GET, redirigir a la lista con mensaje de error
    messages.error(request, 'Método no permitido. Por favor, use el botón de eliminar.')
    return redirect('product_list')