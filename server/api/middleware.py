from django.http import HttpResponse
from django.utils.deprecation import MiddlewareMixin

from .tenancy import set_current_tenant, clear_current_tenant


class TenantMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        set_current_tenant(self._resolve_tenant(request))
        try:
            response = self.get_response(request)
        finally:
            clear_current_tenant()
        return response

    def _resolve_tenant(self, request):
        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated:
            return None

        if user.is_superuser or user.nivel in ('superadmin', 'vendedor', 'suporte'):
            return None

        if user.nivel == 'admin':
            if user.instituicao_id is None:
                return None
            return ('instituicao', user.instituicao_id)

        if user.escola_id is None:
            return None
        return ('escola', user.escola_id)


class PlanejamentoCorsMiddleware(MiddlewareMixin):
    def __init__(self, get_response=None):
        self.get_response = get_response
        self.planejamento_endpoints = [
            '/api/planejamento/',
            '/api/planejamento/atualizar/',
            '/api/planejamentos/turma/',
            '/api/planejamento/processar-arquivo/',
            '/api/planejamento/sugerir-atividades/',
            '/api/planejamento/sugerir-bncc/',
            '/api/habilidades-bncc/criar/',
            '/api/habilidades-bncc/'
        ]
        super().__init__(get_response)

    def _is_planejamento(self, request):
        return any(ep in request.path for ep in self.planejamento_endpoints)

    def _get_origin(self, request):
        return request.META.get('HTTP_ORIGIN', '')

    def process_request(self, request):
        if request.method == 'OPTIONS' and self._is_planejamento(request):
            response = HttpResponse()
            origin = self._get_origin(request)
            response['Access-Control-Allow-Origin'] = origin
            response['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
            response['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-Requested-With, X-CSRFToken, ngrok-skip-browser-warning'
            response['Access-Control-Max-Age'] = '86400'
            response['Access-Control-Allow-Credentials'] = 'true'
            return response
        return None

    def process_response(self, request, response):
        if self._is_planejamento(request):
            origin = self._get_origin(request)
            response['Access-Control-Allow-Origin'] = origin
            response['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
            response['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-Requested-With, X-CSRFToken, ngrok-skip-browser-warning'
            response['Access-Control-Allow-Credentials'] = 'true'
            response['Access-Control-Expose-Headers'] = 'Content-Type, X-CSRFToken'
        return response