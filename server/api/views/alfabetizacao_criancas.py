"""
Drill-down "crianças por classe de alfabetização" (tela de coordenação).

Ao clicar numa classe no card "Pulso da alfabetização", abre-se a lista de todas
as crianças naquela fase (escrita ou leitura) no período avaliativo vigente, com
filtro por turma e paginação server-side.

A regra de "última classificação por criança no período" é a MESMA do card — mora
em `services/coordenacao_cache.criancas_por_classe_alfabetizacao` — então os números
da lista e da distribuição nunca divergem. A lista é computada ao vivo (não vem do
cache, que guarda só os totais), garantindo frescor.
"""

from __future__ import annotations

from datetime import date

from django.core.exceptions import ValidationError
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from api.models import PeriodoAvaliativo, Turma
from api.services.coordenacao_cache import (
    RecorteInvalido,
    criancas_por_classe_alfabetizacao,
    resolver_recorte,
)


def _parse_data(valor: str | None) -> date | None:
    """`YYYY-MM-DD` → date. Levanta ValueError em formato inválido."""
    if not valor:
        return None
    return date.fromisoformat(valor)

MODALIDADES = ('escrita', 'leitura')


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def alfabetizacao_criancas(request):
    """Lista paginada de crianças numa classe de alfabetização (escrita|leitura)."""
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

    # Mesmo recorte do painel: sem parâmetro cai no período vigente, e o
    # drill-down continua batendo com o card que o usuário clicou.
    try:
        recorte = resolver_recorte(
            periodo_id=request.GET.get('periodo_id') or None,
            data_inicio=_parse_data(request.GET.get('data_inicio')),
            data_fim=_parse_data(request.GET.get('data_fim')),
        )
    except (RecorteInvalido, ValueError) as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    except (PeriodoAvaliativo.DoesNotExist, ValidationError):
        return Response(
            {'error': 'Período avaliativo não encontrado.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    todas = criancas_por_classe_alfabetizacao(recorte, modalidade, classe, turma_id)
    count = len(todas)
    page = todas[offset:offset + limit]

    # Resolve nome da turma só para a página atual.
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
