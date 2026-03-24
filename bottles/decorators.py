from django.core.exceptions import PermissionDenied
from functools import wraps

def role_required(required_role):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):

            print("ACCESS CHECK:", request.user.username, request.user.role)

            if request.user.role != required_role:
                raise PermissionDenied  # BLOCK

            return view_func(request, *args, **kwargs)

        return wrapper
    return decorator