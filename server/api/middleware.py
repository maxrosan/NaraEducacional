from django.http import HttpResponse
from django.utils.deprecation import MiddlewareMixin

from .tenancy import clear_current_tenant, resolver_escopo, set_current_tenant


class TenantMiddleware:
    """Define o escopo para requisições autenticadas por SESSÃO (ex.: Django admin)
    e SEMPRE limpa o escopo ao fim da requisição.

    Requisições da API com JWT recebem o escopo em
    `api.authentication.TenantJWTAuthentication`, porque aqui o usuário do JWT
    ainda não foi identificado.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        set_current_tenant(resolver_escopo(getattr(request, "user", None)))
        try:
            response = self.get_response(request)
        finally:
            clear_current_tenant()
        return response


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