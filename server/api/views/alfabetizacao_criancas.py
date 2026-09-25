"""
Drill-down "alunos por classe de alfabetização" (tela de coordenação).

Ao clicar numa classe no card "Pulso da alfabetização", abre-se a lista de
todos os alunos naquela fase (escrita ou leitura) no recorte selecionado,
com filtro por turma e paginação server-side.

A regra de "última classificação por aluno no período" é a MESMA do card —
mora em `services/coordenacao_cache.alunos_por_classe_alfabetizacao` — então
os números da lista e da distribuição nunca divergem. A lista é computada ao
vivo (não vem de cache), garantindo frescor.

Escola e recorte seguem o contrato comum das telas da coordenação:
`escopo.resolver_escola_painel` e `views.coordenacao_cache.recorte_da_requisicao`.
"""

from __future__ import annotations

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.models import Turma
from api.services.coordenacao_cache import alunos_por_classe_alfabetizacao
from api.escopo import resolver_escola_painel
from api.views.coordenacao_cache import recorte_da_requisicao

MODALIDADES = ('escrita', 'leitura')


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def alfabetizacao_criancas(request):
    """Lista paginada de alunos numa classe de alfabetização (escrita|leitura)."""
    escola_id, erro = resolver_escola_painel(request)
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

    recorte, erro = recorte_da_requisicao(request, escola_id)
    if erro:
        return erro

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