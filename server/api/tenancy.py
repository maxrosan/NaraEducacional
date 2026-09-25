"""Escopo de tenant da requisição corrente (lido pelo `TenantManager`).

O escopo é uma tupla ``(nivel, valor)``:

* ``None``                         — perfil GLOBAL (superuser, superadmin, suporte,
                                     vendedor) ou requisição sem usuário (ex.: firmware
                                     autenticado por token próprio). Sem filtro.
* ``('instituicao', <id>)``        — admin: vê a instituição inteira.
* ``('escola', <id>)``             — demais perfis: só a própria escola.
* ``('nenhum', None)``             — usuário NÃO global sem o vínculo que o perfil exige
                                     (ex.: professor sem escola). Não vê nada.

Dois conceitos distintos, ambos definidos SÓ aqui:

* `eh_global`     — ESCOPO: enxerga todas as instituições (regra do TenantManager).
* `is_superadmin` — PRIVILÉGIO: pode alterar qualquer coisa, inclusive registros
                    oficiais. Suporte e vendedor são globais, mas NÃO superadmin.

Fica num ContextVar: vale para a requisição (e para código chamado dentro dela)
sem vazar entre requisições concorrentes.
"""

from contextvars import ContextVar
from typing import Optional, Tuple

Escopo = Optional[Tuple[str, object]]

NIVEIS_GLOBAIS = frozenset({'superadmin', 'suporte', 'vendedor'})
ESCOPO_NENHUM: Tuple[str, None] = ('nenhum', None)

_current_scope: ContextVar[Escopo] = ContextVar("current_scope", default=None)


# ---------------------------------------------------------------------------
# Quem é quem
# ---------------------------------------------------------------------------

def _autenticado(user) -> bool:
    return user is not None and getattr(user, 'is_authenticated', False)


def eh_global(user) -> bool:
    """Escopo: enxerga todas as instituições (mesma regra do TenantManager)."""
    if not _autenticado(user):
        return False
    return bool(getattr(user, 'is_superuser', False) or getattr(user, 'nivel', None) in NIVEIS_GLOBAIS)


def is_superadmin(user) -> bool:
    """Privilégio: pode alterar qualquer coisa, inclusive registros oficiais."""
    if not _autenticado(user):
        return False
    return bool(getattr(user, 'is_superuser', False) or getattr(user, 'nivel', None) == 'superadmin')


# ---------------------------------------------------------------------------
# Escopo da requisição
# ---------------------------------------------------------------------------

def resolver_escopo(user) -> Escopo:
    """Traduz o usuário autenticado no escopo de tenant."""
    if not _autenticado(user):
        return None

    if eh_global(user):
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


# ---------------------------------------------------------------------------
# Helpers para views e serviços
# ---------------------------------------------------------------------------

def chave_cache_escopo() -> str:
    """Fragmento de chave de cache que identifica o escopo corrente.

    Todo `cache.set` que guarda resultado de query DEVE incluir isto na chave.
    O TenantManager filtra a query, mas o cache não: sem o escopo na chave, o
    resultado calculado para um usuário é servido a outro de escopo diferente.
    """
    escopo = get_current_tenant()
    if escopo is None:
        return 'global'
    nivel, valor = escopo
    return f'{nivel}-{valor}'