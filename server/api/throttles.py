"""
Throttle classes customizadas para rate limiting.
"""

from rest_framework.throttling import SimpleRateThrottle


class UploadRateThrottle(SimpleRateThrottle):
    """
    Throttle específico para endpoints de upload.
    Limite: 10 requisições por minuto por IP.
    """
    scope = 'uploads'

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            ident = request.user.pk
        else:
            ident = self.get_ident(request)

        return self.cache_format % {
            'scope': self.scope,
            'ident': ident
        }
