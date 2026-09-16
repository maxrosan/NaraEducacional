from functools import wraps
from rest_framework.response import Response
from rest_framework import status

def requer_perfil(*perfis):
    def decorator(func):
        @wraps(func)
        def wrapper(request, *args, **kwargs):
            if not request.user or not request.user.is_authenticated:
                return Response({'error': 'Não autenticado'}, status=status.HTTP_401_UNAUTHORIZED)
            if request.user.perfil not in perfis:
                return Response({'error': 'Sem permissão'}, status=status.HTTP_403_FORBIDDEN)
            return func(request, *args, **kwargs)
        return wrapper
    return decorator