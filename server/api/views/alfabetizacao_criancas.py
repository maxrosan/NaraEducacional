"""
Drill-down "alunos por classe de alfabetização" (tela de coordenação).

Ao clicar numa classe no card "Pulso da alfabetização", abre-se a lista de
todos os alunos naquela fase (escrita ou leitura) no período avaliativo
vigente, com filtro por turma e paginação server-side.

A regra de "última classificação por aluno no período" é a MESMA do card —
mora em `services/coordenacao_cache.alunos_por_classe_alfabetizacao` — então
os números da lista e da distribuição nunca divergem. A lista é computada ao
vivo (não vem de cache), garantindo frescor.
"""

from __future__ import annotations

from datetime import date

from django.core.exceptions import ValidationError
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from api.models import Escola, PeriodoAvaliativo, Turma
from api.services.coordenacao_cache import (
    RecorteInvalido,
    alunos_por_classe_alfabetizacao,
    resolver_recorte,
)

MODALIDADES = ('escrita', 'leitura')


def _is_superadmin(user):
    return user.is_superuser or user.nivel == 'superadmin'


def _resolver_escola_id(request):
    """Escola sobre a qual calcular o painel. Coordenador usa sempre a
    própria; admin/superadmin precisam informar ?escola_id= explicitamente
    (podem gerenciar mais de uma escola)."""
    user = request.user
    if user.nivel == 'coordenador':
        return user.escola_id, None

    escola_id = request.GET.get('escola_id')
    if not escola_id:
        return None, Response(
            {'error': 'Parâmetro escola_id é obrigatório para este nível.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if _is_superadmin(user):
        return escola_id, None

    if user.nivel == 'admin':
        pertence = Escola.objects.filter(id=escola_id, instituicao_id=user.instituicao_id).exists()
        if not pertence:
            return None, Response(
                {'error': 'Escola não pertence à sua instituição.'}, status=status.HTTP_403_FORBIDDEN,
            )
        return escola_id, None

    return None, Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)


def _parse_data(valor: str | None) -> date | None:
    """`YYYY-MM-DD` → date. Levanta ValueError em formato inválido."""
    if not valor:
        return None
    return date.fromisoformat(valor)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def alfabetizacao_criancas(request):
    """Lista paginada de alunos numa classe de alfabetização (escrita|leitura)."""
    escola_id, erro = _resolver_escola_id(request)
    if erro:
        return erro

    modalidade = (request.GET.get('modalidade') or '').strip().lower()
    classe = (request.GET.get('classe') or '').strip()
    turma_id = request.GET.get('turma_id') or None

    if modalidade not in MODALIDADES:
        return Response(
            {'error': "modalidade deve ser 'escrita' ou 'leitura'"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if not classe:
        return Response({'error': 'classe é obrigatória'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        limit = max(1, min(int(request.GET.get('limit', 25)), 200))
    except (TypeError, ValueError):
        limit = 25
    try:
        offset = max(0, int(request.GET.get('offset', 0)))
    except (TypeError, ValueError):
        offset = 0

    try:
        recorte = resolver_recorte(
            escola_id,
            periodo_id=request.GET.get('periodo_id') or None,
            data_inicio=_parse_data(request.GET.get('data_inicio')),
            data_fim=_parse_data(request.GET.get('data_fim')),
        )
    except (RecorteInvalido, ValueError) as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    except (PeriodoAvaliativo.DoesNotExist, ValidationError):
        return Response({'error': 'Período avaliativo não encontrado.'}, status=status.HTTP_404_NOT_FOUND)

    todos = alunos_por_classe_alfabetizacao(escola_id, recorte, modalidade, classe, turma_id)
    count = len(todos)
    page = todos[offset:offset + limit]

    turma_ids = {r['turma_id'] for r in page if r['turma_id']}
    nomes = {}
    if turma_ids:
        nomes = {
            str(t['id']): t['nome']
            for t in Turma.objects.filter(id__in=turma_ids).values('id', 'nome')
        }
    for r in page:
        r['turma_nome'] = nomes.get(r['turma_id'] or '', None)

    return Response(
        {'count': count, 'results': page, 'modalidade': modalidade, 'classe': classe},
        status=status.HTTP_200_OK,
    )