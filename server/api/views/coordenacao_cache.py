"""
Endpoints para o snapshot pré-computado (D-1) do painel da coordenação.

- POST /api/internal/cache/coordenacao/  (token interno)
    Chamado pelo worker central (scheduler). Re-gera o cache para uma
    instituição a partir dos registros_observacao dos últimos 30 dias.
- GET  /api/coordenacao/cache/            (sessão do coordenador)
    Consumido pelo frontend; retorna o payload agregado mais recente.
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
from api.services.scheduler_client import (
    SchedulerNaoConfigurado,
    enfileirar_refresh_coordenacao,
)

logger = logging.getLogger(__name__)


def _parse_data(valor: str | None) -> date | None:
    """`YYYY-MM-DD` → date. Levanta ValueError em formato inválido."""
    if not valor:
        return None
    return date.fromisoformat(valor)


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
    Recomputa o cache da coordenação para a instituição informada.
    Autenticação: header `X-Internal-Token` casado com `NARA_INTERNAL_TOKEN`.
    Body (JSON, opcional):
        {
          "instituicao_id": "uuid",   # obrigatório
          "data_referencia": "YYYY-MM-DD",  # default: ontem
          "janela_dias": 30
        }
    """
    if not _check_internal_token(request):
        return Response(
            {'error': 'Token interno inválido ou ausente.'},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    body = request.data or {}
    # Backend por instituição: NARA_INSTITUICAO_ID do .env é a fonte de
    # verdade. O body é apenas fallback (útil em deploys multi-tenant).
    instituicao_id = (
        getattr(settings, 'NARA_INSTITUICAO_ID', '') or body.get('instituicao_id')
    )
    if not instituicao_id:
        return Response(
            {'error': 'instituicao_id não configurado (defina NARA_INSTITUICAO_ID ou envie no body).'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    data_referencia_raw = body.get('data_referencia')
    try:
        data_referencia = (
            date.fromisoformat(data_referencia_raw) if data_referencia_raw else None
        )
    except ValueError:
        return Response(
            {'error': 'data_referencia inválida (use YYYY-MM-DD).'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    janela_dias = int(body.get('janela_dias') or JANELA_DIAS)

    try:
        obj = atualizar_cache_coordenacao(
            instituicao_id=instituicao_id,
            data_referencia=data_referencia,
            janela_dias=janela_dias,
        )
    except Exception:
        logger.exception(
            'Falha ao gerar cache da coordenação.',
            extra={'instituicao_id': str(instituicao_id)},
        )
        return Response(
            {'error': 'Erro ao gerar cache.'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    return Response(
        {
            'instituicao_id': str(obj.instituicao_id),
            'data_referencia': obj.data_referencia.isoformat(),
            'janela_dias': obj.janela_dias,
            'versao_schema': obj.versao_schema,
            'gerado_em': obj.gerado_em.isoformat(),
        },
        status=status.HTTP_200_OK,
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def refresh_coordenacao_cache_sessao(request):
    """Enfileira no scheduler o refresh do cache a pedido do coordenador.

    Diferente de `refresh_coordenacao_cache` (token interno, usado pelo
    worker), aqui a autenticação é por sessão e o perfil precisa ser
    coordenador/admin. O backend não regenera o cache no request: ele apenas
    publica a task `tasks.refresh_coordenacao_cache` no broker do scheduler
    e responde 202. O worker chama de volta o endpoint interno e atualiza o
    snapshot — o frontend faz polling no GET até `gerado_em` mudar.
    """
    user = request.user
    if getattr(user, 'perfil', None) not in ('coordenador', 'admin'):
        return Response(
            {'error': 'Apenas coordenação pode atualizar os indicadores.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        task_id = enfileirar_refresh_coordenacao()
    except SchedulerNaoConfigurado:
        logger.exception('Scheduler não configurado para refresh sob demanda.')
        return Response(
            {'error': 'Atualização sob demanda indisponível (scheduler não configurado).'},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    except Exception:
        logger.exception('Falha ao enfileirar refresh da coordenação no scheduler.')
        return Response(
            {'error': 'Não foi possível acionar a atualização. Tente novamente mais tarde.'},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    return Response(
        {'status': 'enfileirado', 'task_id': task_id},
        status=status.HTTP_202_ACCEPTED,
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_cache_coordenacao(request):
    """Agregados do painel da coordenação para um período avaliativo.

    Calculado **ao vivo** a cada requisição. O snapshot pré-computado deixou de
    ser necessário quando o payload passou a ser recortado por período: com a
    janela limitada a um bimestre o custo fica em ~70 ms e, ao contrário da
    varredura cumulativa anterior, não cresce com a história da escola.

    Query params:
        data_inicio + data_fim (opcionais, YYYY-MM-DD) - intervalo à mão; têm
            precedência sobre `periodo_id`. Limitado a MAX_DIAS_RECORTE dias.
        periodo_id (opcional)     - período avaliativo; default: o vigente hoje.
        instituicao_id (opcional) - fallback se o user não tiver instituicao_id.
    """
    user = request.user
    # Backend por instituição: NARA_INSTITUICAO_ID do .env é a fonte de
    # verdade. Se não estiver configurado, cai para Usuario.instituicao
    # (modelo legado/multi-tenant) e por fim para query string.
    instituicao_id = (
        getattr(settings, 'NARA_INSTITUICAO_ID', '')
        or getattr(user, 'instituicao_id', None)
        or request.GET.get('instituicao_id')
    )
    if not instituicao_id:
        return Response(
            {'error': 'instituição não encontrada (defina NARA_INSTITUICAO_ID).'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    periodo_id = request.GET.get('periodo_id') or None
    try:
        data_inicio = _parse_data(request.GET.get('data_inicio'))
        data_fim = _parse_data(request.GET.get('data_fim'))
    except ValueError:
        return Response(
            {'error': 'Datas inválidas (use YYYY-MM-DD).'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        recorte = resolver_recorte(
            periodo_id=periodo_id, data_inicio=data_inicio, data_fim=data_fim
        )
    except RecorteInvalido as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    except (PeriodoAvaliativo.DoesNotExist, ValidationError, ValueError):
        return Response(
            {'error': 'Período avaliativo não encontrado.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    agora = timezone.now()
    try:
        payload = gerar_payload_coordenacao(instituicao_id, recorte)
    except Exception:
        logger.exception(
            'Falha ao gerar agregados da coordenação.',
            extra={'instituicao_id': str(instituicao_id), 'periodo_id': periodo_id},
        )
        return Response(
            {'error': 'Erro ao calcular os indicadores.'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    return Response(
        {
            'instituicao_id': str(instituicao_id),
            'periodo_id': recorte.periodo_id if recorte else None,
            'periodo_descricao': recorte.descricao if recorte else None,
            'periodo_personalizado': bool(recorte and recorte.personalizado),
            # `gerado_em` == agora: o payload é sempre fresco. Mantido no
            # contrato porque o front exibe quando os números foram calculados.
            'gerado_em': agora.isoformat(),
            'agora': agora.isoformat(),
            'payload': payload,
        },
        status=status.HTTP_200_OK,
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_periodos_coordenacao(request):
    """Períodos avaliativos disponíveis no select da coordenação.

    Mais recentes primeiro, marcando qual contém a data de hoje — é o que a
    tela seleciona por padrão.
    """
    hoje = timezone.localdate()
    periodos = PeriodoAvaliativo.objects.all().order_by('-data_inicio')
    vigente = resolver_recorte()

    return Response(
        {
            'periodo_vigente_id': vigente.periodo_id if vigente else None,
            # Teto do intervalo à mão, para a tela avisar antes de enviar.
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
