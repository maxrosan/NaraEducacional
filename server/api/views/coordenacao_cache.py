"""
Endpoints do painel da coordenação.

- GET  /api/coordenacao/cache/       — payload agregado, calculado ao vivo
- GET  /api/coordenacao/periodos/    — períodos avaliativos pro seletor
- POST /api/internal/coordenacao/refresh/  — grava snapshot (token interno,
  chamado pelo worker/scheduler externo — mantido só por compatibilidade;
  nada no caminho normal do produto depende disso, ver docstring de
  `atualizar_cache_coordenacao` no service)

O painel é sempre de UMA escola (`gerar_payload_coordenacao` é escola-scoped).
Qual escola: `escopo.resolver_escola_painel`. Qual intervalo:
`recorte_da_requisicao` (abaixo) — os dois também são usados por
`views/alfabetizacao_criancas.py` e `views/indicadores_turma.py`, para que
todas as telas da coordenação sigam o mesmo contrato.
"""

from __future__ import annotations

import hmac
import logging
from datetime import date

from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from api.models import PeriodoAvaliativo
from api.services.coordenacao_cache import (
    JANELA_DIAS,
    MAX_DIAS_RECORTE,
    RecorteInvalido,
    atualizar_cache_coordenacao,
    gerar_payload_coordenacao,
    resolver_recorte,
)
from api.escopo import resolver_escola_painel

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Recorte (compartilhado pelas telas da coordenação)
# ---------------------------------------------------------------------------

def _parse_data(valor: str | None) -> date | None:
    """`YYYY-MM-DD` → date. Levanta ValueError em formato inválido."""
    return date.fromisoformat(valor) if valor else None


def recorte_da_requisicao(request, escola_id, periodo_id=None):
    """Retorna `(recorte, erro)`. Precedência: data_inicio+data_fim >
    periodo_id > período vigente hoje.

    `recorte` pode ser None legitimamente (escola sem período vigente).
    `periodo_id` explícito sobrescreve o da query string (usado pelo
    `indicadores_turma`, que ainda aceita o parâmetro legado `periodo`).
    """
    try:
        data_inicio = _parse_data(request.GET.get('data_inicio'))
        data_fim = _parse_data(request.GET.get('data_fim'))
    except ValueError:
        return None, Response(
            {'error': 'Datas inválidas (use YYYY-MM-DD).'}, status=status.HTTP_400_BAD_REQUEST,
        )

    if periodo_id is None:
        periodo_id = request.GET.get('periodo_id') or None

    try:
        recorte = resolver_recorte(
            escola_id, periodo_id=periodo_id, data_inicio=data_inicio, data_fim=data_fim,
        )
    except RecorteInvalido as exc:
        return None, Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    except (PeriodoAvaliativo.DoesNotExist, ValidationError, ValueError):
        return None, Response(
            {'error': 'Período avaliativo não encontrado.'}, status=status.HTTP_404_NOT_FOUND,
        )
    return recorte, None


# ---------------------------------------------------------------------------
# Refresh interno (compatibilidade com o scheduler externo)
# ---------------------------------------------------------------------------

def _check_internal_token(request) -> bool:
    expected = getattr(settings, 'NARA_INTERNAL_TOKEN', None)
    if not expected:
        return False
    provided = request.META.get('HTTP_X_INTERNAL_TOKEN', '')
    return hmac.compare_digest(str(expected), str(provided))


@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def refresh_coordenacao_cache(request):
    """
    Recomputa o snapshot da coordenação para uma escola.
    Autenticação: header `X-Internal-Token` casado com `NARA_INTERNAL_TOKEN`.
    Body (JSON): {"escola_id": "uuid" (obrigatório), "data_referencia": "YYYY-MM-DD" (default: ontem), "janela_dias": 30}
    """
    if not _check_internal_token(request):
        return Response({'error': 'Token interno inválido ou ausente.'}, status=status.HTTP_401_UNAUTHORIZED)

    body = request.data or {}
    escola_id = body.get('escola_id')
    if not escola_id:
        return Response({'error': 'escola_id é obrigatório no body.'}, status=status.HTTP_400_BAD_REQUEST)

    data_referencia_raw = body.get('data_referencia')
    try:
        data_referencia = date.fromisoformat(data_referencia_raw) if data_referencia_raw else None
    except ValueError:
        return Response({'error': 'data_referencia inválida (use YYYY-MM-DD).'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        janela_dias = int(body.get('janela_dias') or JANELA_DIAS)
    except (TypeError, ValueError):
        return Response({'error': 'janela_dias deve ser um número inteiro.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        obj = atualizar_cache_coordenacao(escola_id=escola_id, data_referencia=data_referencia, janela_dias=janela_dias)
    except Exception:
        logger.exception('Falha ao gerar cache da coordenação.', extra={'escola_id': str(escola_id)})
        return Response({'error': 'Erro ao gerar cache.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return Response(
        {
            'escola_id': str(obj.escola_id),
            'data_referencia': obj.data_referencia.isoformat(),
            'janela_dias': obj.janela_dias,
            'versao_schema': obj.versao_schema,
        },
        status=status.HTTP_200_OK,
    )


# ---------------------------------------------------------------------------
# Painel
# ---------------------------------------------------------------------------

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_cache_coordenacao(request):
    """Agregados do painel da coordenação — calculado ao vivo a cada requisição.

    Query params: data_inicio + data_fim (têm precedência sobre periodo_id,
    limitado a MAX_DIAS_RECORTE dias), periodo_id (default: o vigente hoje).
    """
    escola_id, erro = resolver_escola_painel(request)
    if erro:
        return erro

    recorte, erro = recorte_da_requisicao(request, escola_id)
    if erro:
        return erro

    agora = timezone.now()
    try:
        payload = gerar_payload_coordenacao(escola_id, recorte)
    except Exception:
        logger.exception(
            'Falha ao gerar agregados da coordenação.',
            extra={'escola_id': str(escola_id), 'periodo_id': recorte.periodo_id if recorte else None},
        )
        return Response({'error': 'Erro ao calcular os indicadores.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return Response(
        {
            'escola_id': str(escola_id),
            'periodo_id': recorte.periodo_id if recorte else None,
            'periodo_descricao': recorte.descricao if recorte else None,
            'periodo_personalizado': bool(recorte and recorte.personalizado),
            'gerado_em': agora.isoformat(),
            'payload': payload,
        },
        status=status.HTTP_200_OK,
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_periodos_coordenacao(request):
    """Períodos avaliativos da escola pro seletor da coordenação."""
    escola_id, erro = resolver_escola_painel(request)
    if erro:
        return erro

    hoje = timezone.localdate()
    periodos = PeriodoAvaliativo.objects.filter(escola_id=escola_id).order_by('-data_inicio')
    vigente = resolver_recorte(escola_id)

    return Response(
        {
            'periodo_vigente_id': vigente.periodo_id if vigente else None,
            'max_dias_intervalo': MAX_DIAS_RECORTE,
            'periodos': [
                {
                    'id': str(p.id),
                    'descricao': p.descricao,
                    'tipo_periodo': p.tipo_periodo,
                    'data_inicio': p.data_inicio.isoformat(),
                    'data_fim': p.data_fim.isoformat(),
                    'em_curso': p.data_inicio <= hoje <= p.data_fim,
                }
                for p in periodos
            ],
        },
        status=status.HTTP_200_OK,
    )