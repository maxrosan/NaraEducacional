"""Endpoints de Turma."""

from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Count, F, Prefetch, Q
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.escopo import buscar_no_escopo, filtrar_por, pode_gerenciar, resolver_escopo_criacao
from api.models import Escola, Turma, Usuario, UsuarioTurma
from api.serializers import TurmaListaSerializer, TurmaSerializer, UsuarioTurmaSerializer

TURMAS_POR_PAGINA = 10
TURMAS_POR_PAGINA_MAX = 50


def _turma_nao_encontrada():
    return Response({'error': 'Turma não encontrada.'}, status=status.HTTP_404_NOT_FOUND)


def _param_bool(valor):
    """'true'/'false' (e variações) → bool; ausente ou inválido → None (sem filtro)."""
    if valor is None:
        return None
    valor = valor.strip().lower()
    if valor in ('true', '1', 'sim'):
        return True
    if valor in ('false', '0', 'nao', 'não'):
        return False
    return None


def _param_int(valor, padrao, minimo, maximo):
    try:
        return max(minimo, min(int(valor), maximo))
    except (TypeError, ValueError):
        return padrao


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_turmas(request):
    """
    GET /turmas/ — já vem recortado pelo TenantManager (admin: turmas da rede;
    coordenador/professor: da própria escola; superadmin: todas).

    Query params (todos opcionais):
      ativa=true|false   filtra pelo status
      escola=<uuid>      filtra por escola (fora do escopo/malformado → vazio)
      page=<n>           liga a paginação (página fora do intervalo → última)
      page_size=<n>      padrão 10, máximo 50

    SEM `page`: devolve um array simples, como antes — outras telas chamam
    listarTurmas() e esperam o array.

    COM `page`:
      {
        "count": 37, "pagina": 1, "total_paginas": 4, "page_size": 10,
        "totais": {"ativas": 30, "inativas": 7},   # p/ os contadores das abas
        "results": [ ...TurmaListaSerializer (com `professores`)... ]
      }

    Custo fixo por página, independente do nº de turmas: count, página,
    prefetch dos vínculos e totais (4 queries).
    """
    base = filtrar_por(Turma.objects.all(), request, 'escola', Escola, 'escola')

    ativa = _param_bool(request.query_params.get('ativa'))
    turmas = base if ativa is None else base.filter(ativa=ativa)

    # Mesma ordem que a tela usava no front: escola, ordem (vazias por último), nome.
    # `id` no fim deixa a ordem estável entre páginas quando há empates.
    turmas = turmas.order_by(
        'escola__nome', F('ordem').asc(nulls_last=True), 'nome', 'id',
    )

    if 'page' not in request.query_params:
        return Response(TurmaSerializer(turmas.select_related('escola'), many=True).data)

    turmas = turmas.select_related('escola').prefetch_related(
        Prefetch(
            'usuario_turmas',
            queryset=UsuarioTurma.objects.select_related('usuario').order_by('usuario__nome'),
            to_attr='professores_listagem',
        ),
    )

    page_size = _param_int(
        request.query_params.get('page_size'),
        TURMAS_POR_PAGINA, 1, TURMAS_POR_PAGINA_MAX,
    )
    pagina = Paginator(turmas, page_size).get_page(request.query_params.get('page'))

    # Totais das abas respeitam o filtro de escola, mas não o de `ativa`.
    totais = base.aggregate(
        ativas=Count('id', filter=Q(ativa=True)),
        inativas=Count('id', filter=Q(ativa=False)),
    )
    # Em queryset vazio (qs.none()), Django < 4.0 devolve None em vez de 0.
    totais = {chave: valor or 0 for chave, valor in totais.items()}

    return Response({
        'count': pagina.paginator.count,
        'pagina': pagina.number,
        'total_paginas': pagina.paginator.num_pages,
        'page_size': page_size,
        'totais': totais,
        'results': TurmaListaSerializer(pagina.object_list, many=True).data,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def criar_turma(request):
    user = request.user
    if not pode_gerenciar(user):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    escola_id, instituicao_id, erro = resolver_escopo_criacao(user, request.data)
    if erro:
        return erro

    serializer = TurmaSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    turma = serializer.save(instituicao_id=instituicao_id, escola_id=escola_id)
    return Response(TurmaSerializer(turma).data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def detalhe_turma(request, turma_id):
    turma = buscar_no_escopo(Turma, turma_id)
    if turma is None:
        return _turma_nao_encontrada()
    return Response(TurmaSerializer(turma).data)


@api_view(['PATCH', 'PUT'])
@permission_classes([IsAuthenticated])
def atualizar_turma(request, turma_id):
    if not pode_gerenciar(request.user):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    turma = buscar_no_escopo(Turma, turma_id)
    if turma is None:
        return _turma_nao_encontrada()

    # escola/instituicao são read_only no TurmaSerializer: a turma não muda de dono.
    partial = request.method == 'PATCH'
    serializer = TurmaSerializer(turma, data=request.data, partial=partial)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_professores_turma(request, turma_id):
    turma = buscar_no_escopo(Turma, turma_id)
    if turma is None:
        return _turma_nao_encontrada()

    vinculos = UsuarioTurma.objects.filter(turma=turma).select_related('usuario')
    return Response(UsuarioTurmaSerializer(vinculos, many=True).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def vincular_professor_turma(request, turma_id):
    if not pode_gerenciar(request.user):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    turma = buscar_no_escopo(Turma, turma_id)
    if turma is None:
        return _turma_nao_encontrada()

    usuario_id = request.data.get('usuario')
    if not usuario_id:
        return Response({'error': 'Campo usuario é obrigatório.'}, status=status.HTTP_400_BAD_REQUEST)

    usuario = buscar_no_escopo(Usuario, usuario_id)
    if usuario is None:
        return Response({'error': 'Usuário não encontrado.'}, status=status.HTTP_404_NOT_FOUND)

    if usuario.escola_id != turma.escola_id:
        return Response({'error': 'O usuário precisa pertencer à mesma escola da turma.'},
                        status=status.HTTP_400_BAD_REQUEST)

    vinculo, criado = UsuarioTurma.objects.get_or_create(usuario=usuario, turma=turma)
    status_code = status.HTTP_201_CREATED if criado else status.HTTP_200_OK
    return Response(UsuarioTurmaSerializer(vinculo).data, status=status_code)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def desvincular_professor_turma(request, turma_id, usuario_id):
    if not pode_gerenciar(request.user):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    turma = buscar_no_escopo(Turma, turma_id)
    if turma is None:
        return _turma_nao_encontrada()

    try:
        deletados, _ = UsuarioTurma.objects.filter(turma=turma, usuario_id=usuario_id).delete()
    except (ValidationError, ValueError):  # usuario_id malformado
        deletados = 0
    if not deletados:
        return Response({'error': 'Vínculo não encontrado.'}, status=status.HTTP_404_NOT_FOUND)

    return Response(status=status.HTTP_204_NO_CONTENT)