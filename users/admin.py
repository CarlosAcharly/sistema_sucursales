from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):

    fieldsets = UserAdmin.fieldsets + (
        ('Información adicional', {
            'fields': ('role', 'branch'),
        }),
    )

    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Información adicional', {
            'fields': ('role', 'branch'),
        }),
    )

    list_display = (
        'username',
        'email',
        'role',
        'branch',
        'is_staff',
        'is_active'
    )
