"""Autenticação JWT que também define o tenant da requisição.

Por que não basta o `TenantMiddleware`: a autenticação do DRF (JWT) só acontece
DENTRO da view, depois de todos os middlewares. Quando o middleware roda,
`request.user` ainda é `AnonymousUser` para qualquer chamada com
`Authorization: Bearer ...` — o escopo ficaria sempre `None` (sem filtro).

Aqui o escopo é definido no momento exato em que o usuário é identificado,
antes das permissões e do corpo da view. O `TenantMiddleware` continua
responsável por limpar o escopo ao fim da requisição.
"""

from rest_framework_simplejwt.authentication import JWTAuthentication

from .tenancy import resolver_escopo, set_current_tenant


class TenantJWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        resultado = super().authenticate(request)
        if resultado is not None:
            user, _token = resultado
            set_current_tenant(resolver_escopo(user))
        return resultado