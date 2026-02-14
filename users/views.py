from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from users.models import User
from users.decorators import role_required
from .forms import UserForm


@role_required(['SUPERADMIN'])
def user_list(request):

    users = User.objects.select_related('branch').all().order_by('role', 'username')

    context = {
        'users': users
    }

    return render(request, 'superadmin/users/list.html', context)


@login_required
def redirect_by_role(request):

    user = request.user

    if not user.is_active:
        return redirect('login')

    if user.is_superadmin():
        return redirect('superadmin_dashboard')

    if user.is_admin():
        return redirect('admin_dashboard')

    if user.is_cashier():
        if not user.branch:
            return redirect('login')
        return redirect('pos')

    return redirect('login')

def user_create(request):

    if request.method == 'POST':
        form = UserForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)

            if form.cleaned_data['password']:
                user.set_password(form.cleaned_data['password'])

            user.save()
            return redirect('users:user_list')

    else:
        form = UserForm()

    return render(request, 'superadmin/users/form.html', {
        'form': form,
        'title': 'Crear Usuario'
    })

from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required

@role_required(['SUPERADMIN'])
def user_update(request, pk):

    user_instance = get_object_or_404(User, pk=pk)

    if request.method == 'POST':
        form = UserForm(request.POST, instance=user_instance)
        if form.is_valid():
            user = form.save(commit=False)

            password = form.cleaned_data.get('password')
            if password:
                user.set_password(password)

            user.save()
            return redirect('users:user_list')
    else:
        form = UserForm(instance=user_instance)

    return render(request, 'superadmin/users/form.html', {
        'form': form,
        'title': 'Editar Usuario'
    })