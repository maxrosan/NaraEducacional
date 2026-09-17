from contextvars import ContextVar
from typing import Optional, Tuple

_current_scope: ContextVar[Optional[Tuple[str, str]]] = ContextVar(
    "current_scope", default=None
)


def set_current_tenant(scope: Optional[Tuple[str, str]]) -> None:
    _current_scope.set(scope)


def get_current_tenant() -> Optional[Tuple[str, str]]:
    return _current_scope.get()


def clear_current_tenant() -> None:
    _current_scope.set(None)