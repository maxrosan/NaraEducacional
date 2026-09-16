"""
Configuração do scheduler central (Celery beat + worker) responsável por
acionar a geração do cache de coordenação em cada escola.

Cada escola é um stack isolado (front + back + DB). Este scheduler não acessa
o banco das escolas: ele chama o endpoint HTTP interno de cada backend com um
token compartilhado.

Fontes do registry (na ordem de prioridade):
  1. Variável ``ESCOLAS_JSON`` — JSON com um array de escolas. Recomendado
     para ambientes onde a infra é imutável (Easypanel/Kubernetes).
  2. Variável ``ESCOLAS_YAML`` — o mesmo conteúdo em YAML.
  3. Arquivo apontado por ``ESCOLAS_REGISTRY_PATH`` (default
     ``./escolas.yaml``) — conveniente para desenvolvimento local.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import yaml


DEFAULT_REGISTRY_PATH = Path(os.getenv(
    'ESCOLAS_REGISTRY_PATH',
    str(Path(__file__).parent / 'escolas.yaml'),
))


@dataclass(frozen=True)
class Escola:
    id: str
    nome: str
    backend_url: str
    internal_token: str
    # Opcional: cada backend é deployado para uma única instituição e
    # resolve o seu próprio UUID via NARA_INSTITUICAO_ID. Mantido para
    # compatibilidade com setups multi-tenant.
    instituicao_id: str = ''

    @property
    def refresh_url(self) -> str:
        base = self.backend_url.rstrip('/')
        return f'{base}/api/internal/cache/coordenacao/'


def _resolve_token(raw: str | None) -> str:
    """Allow tokens to be referenced by env var name with the ``env:`` prefix."""
    if not raw:
        return ''
    if raw.startswith('env:'):
        return os.getenv(raw[len('env:'):], '')
    return raw


def _extract_escolas_list(data: Any) -> Iterable[dict]:
    """Aceita tanto ``{escolas: [...]}`` quanto um array no topo."""
    if isinstance(data, dict):
        return data.get('escolas') or []
    if isinstance(data, list):
        return data
    return []


def _build_escolas(raw_items: Iterable[dict]) -> list[Escola]:
    resultado: list[Escola] = []
    for item in raw_items:
        try:
            resultado.append(
                Escola(
                    id=str(item['id']),
                    nome=str(item.get('nome') or item['id']),
                    backend_url=str(item['backend_url']),
                    internal_token=_resolve_token(item.get('internal_token')),
                    instituicao_id=str(item.get('instituicao_id') or ''),
                )
            )
        except KeyError as exc:
            raise ValueError(
                f'Entrada inválida no registry de escolas: faltando {exc.args[0]!r}'
            ) from exc
    return resultado


def load_escolas(path: Path | str | None = None) -> list[Escola]:
    # 1) JSON embutido em env var.
    escolas_json = os.getenv('ESCOLAS_JSON')
    if escolas_json and escolas_json.strip():
        try:
            data = json.loads(escolas_json)
        except json.JSONDecodeError as exc:
            raise ValueError(f'ESCOLAS_JSON inválido: {exc}') from exc
        return _build_escolas(_extract_escolas_list(data))

    # 2) YAML embutido em env var.
    escolas_yaml = os.getenv('ESCOLAS_YAML')
    if escolas_yaml and escolas_yaml.strip():
        data = yaml.safe_load(escolas_yaml) or {}
        return _build_escolas(_extract_escolas_list(data))

    # 3) Arquivo YAML (fallback, útil em dev local).
    registry_path = Path(path) if path else DEFAULT_REGISTRY_PATH
    if not registry_path.exists():
        return []

    with registry_path.open('r', encoding='utf-8') as fh:
        data = yaml.safe_load(fh) or {}
    return _build_escolas(_extract_escolas_list(data))
