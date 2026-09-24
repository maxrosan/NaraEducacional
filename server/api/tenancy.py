"""Escopo de tenant da requisição corrente (lido pelo `TenantManager`).

O escopo é uma tupla ``(nivel, valor)``:

* ``None``                         — perfil GLOBAL (superuser, superadmin, suporte,
                                     vendedor) ou requisição sem usuário (ex.: firmware
                                     autenticado por token próprio). Sem filtro.
* ``('instituicao', <id>)``        — admin: vê a instituição inteira.
* ``('escola', <id>)``             — demais perfis: só a própria escola.
* ``('nenhum', None)``             — usuário NÃO global sem o vínculo que o perfil exige
                                     (ex.: professor sem escola). Não vê nada.

Fica num ContextVar: vale para a requisição (e para código chamado dentro dela)
sem vazar entre requisições concorrentes.
"""

from contextvars import ContextVar
from typing import Optional, Tuple

Escopo = Optional[Tuple[str, object]]

NIVEIS_GLOBAIS = frozenset({'superadmin', 'suporte', 'vendedor'})
ESCOPO_NENHUM: Tuple[str, None] = ('nenhum', None)

_current_scope: ContextVar[Escopo] = ContextVar("current_scope", default=None)


def resolver_escopo(user) -> Escopo:
    """Traduz o usuário autenticado no escopo de tenant."""
    if user is None or not getattr(user, 'is_authenticated', False):
        return None

    if getattr(user, 'is_superuser', False) or getattr(user, 'nivel', None) in NIVEIS_GLOBAIS:
        return None

    if user.nivel == 'admin':
        return ('instituicao', user.instituicao_id) if user.instituicao_id else ESCOPO_NENHUM

    return ('escola', user.escola_id) if user.escola_id else ESCOPO_NENHUM


def set_current_tenant(scope: Escopo) -> None:
    _current_scope.set(scope)


def get_current_tenant() -> Escopo:
    return _current_scope.get()


def clear_current_tenant() -> None:
    _current_scope.set(None)