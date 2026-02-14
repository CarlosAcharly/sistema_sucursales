from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from users.decorators import role_required
from .models import Branch
from .forms import BranchForm


@login_required
@role_required(['SUPERADMIN'])
def branch_list(request):
    branches = Branch.objects.all().order_by('-id')
    return render(request, 'superadmin/branches/list.html', {
        'branches': branches
    })


@login_required
@role_required(['SUPERADMIN'])
def branch_create(request):

    if request.method == 'POST':
        form = BranchForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('branch_list')
    else:
        form = BranchForm()

    return render(request, 'superadmin/branches/form.html', {
        'form': form,
        'title': 'Crear Sucursal'
    })


@login_required
@role_required(['SUPERADMIN'])
def branch_edit(request, pk):

    branch = get_object_or_404(Branch, pk=pk)

    if request.method == 'POST':
        form = BranchForm(request.POST, instance=branch)
        if form.is_valid():
            form.save()
            return redirect('branch_list')
    else:
        form = BranchForm(instance=branch)

    return render(request, 'superadmin/branches/form.html', {
        'form': form,
        'title': 'Editar Sucursal'
    })


@login_required
@role_required(['SUPERADMIN'])
def branch_toggle(request, pk):

    branch = get_object_or_404(Branch, pk=pk)
    branch.is_active = not branch.is_active
    branch.save()

    return redirect('branch_list')
