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