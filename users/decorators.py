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


# =============================
# ✅ NUEVO DECORADOR: Permiso para transferencias
# =============================

def transfer_permission_required(view_func):
    """
    Decorador para verificar si el usuario tiene permiso para acceder a transferencias.
    - SUPERADMIN y ADMIN siempre pueden
    - CAJEROS: solo si su sucursal tiene el campo can_transfer = True
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            raise PermissionDenied
        
        # Superadmin y Admin siempre pueden
        if request.user.role in ['SUPERADMIN', 'ADMIN']:
            return view_func(request, *args, **kwargs)
        
        # Cajero: verificar que su sucursal tenga permiso
        if request.user.role == 'CASHIER':
            if request.user.branch and request.user.branch.can_transfer:
                return view_func(request, *args, **kwargs)
        
        # Si no cumple ninguna condición, denegar acceso
        raise PermissionDenied
    
    return wrapper


# =============================
# ✅ DECORADOR PARA PROCESAR TRANSFERENCIAS (solo admin/superadmin)
# =============================

def process_transfer_permission_required(view_func):
    """
    Decorador específico para procesar transferencias.
    Solo SUPERADMIN y ADMIN pueden procesar transferencias.
    Los cajeros NO pueden procesar, solo crear y ver.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            raise PermissionDenied
        
        # Solo Superadmin y Admin pueden procesar
        if request.user.role not in ['SUPERADMIN', 'ADMIN']:
            raise PermissionDenied
        
        return view_func(request, *args, **kwargs)
    
    return wrapper