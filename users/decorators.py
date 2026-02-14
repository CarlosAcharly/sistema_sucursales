from django.core.exceptions import PermissionDenied
from functools import wraps

def role_required(allowed_roles=None):
    if allowed_roles is None:
        allowed_roles = []

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):

            if not request.user.is_authenticated:
                raise PermissionDenied

            if request.user.role not in allowed_roles:
                raise PermissionDenied

            if request.user.role == 'CASHIER':
                if not request.user.branch or not request.user.branch.is_active:
                    raise PermissionDenied

            return view_func(request, *args, **kwargs)

        return wrapper
    return decorator
