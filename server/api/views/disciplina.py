"""Endpoints de Disciplina e do vínculo Usuario-Disciplina."""

from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Prefetch, Q
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.escopo import (
    buscar_no_escopo, filtrar_por, pode_gerenciar, resolver_escopo_criacao,
    validar_professores_disciplina,
)
from api.models import Disciplina, Escola, Usuario, UsuarioDisciplina
from api.serializers import (
    DisciplinaListaSerializer, DisciplinaSerializer, UsuarioDisciplinaSerializer,
)

# Mantida por compatibilidade (outras views podem importá-la). A regra de quem
# pode ser vinculado vive em escopo.NIVEIS_VINCULAVEIS_DISCIPLINA.
NIVEL_COM_DISCIPLINA = 'professor_fundamental'

DISCIPLINAS_POR_PAGINA = 10
DISCIPLINAS_POR_PAGINA_MAX = 50


def _sem_permissao():
    return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)


def _disciplina_ou_404(disciplina_id):
    """Retorna (disciplina, erro)."""
    disciplina = buscar_no_escopo(Disciplina, disciplina_id)
    if disciplina is None:
        return None, Response({'error': 'Disciplina não encontrada.'}, status=status.HTTP_404_NOT_FOUND)
    return disciplina, None


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


def _validar_e_salvar(serializer, escola_travada_id, **extra):
    """Valida e salva disciplina + vínculos numa transação, com a escola travada.

    O nome único sem diferenciar maiúsculas é checado no serializer; a trava
    (SELECT ... FOR UPDATE na escola) impede que duas requisições simultâneas
    passem ambas pela checagem. A UniqueConstraint(escola, nome) do banco
    continua valendo para nomes exatamente iguais.

    `escola_travada_id` tem esse nome (e não `escola_id`) porque `escola_id`
    também chega em `**extra` para o serializer.save() na criação.
    """
    with transaction.atomic():
        list(Escola._base_manager.select_for_update().filter(pk=escola_travada_id).values_list('pk', flat=True))
        serializer.is_valid(raise_exception=True)
        return serializer.save(**extra)


# ============================================================
# Disciplina
# ============================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_disciplinas(request):
    """
    GET /disciplinas/ — já vem recortado pelo TenantManager.

    Query params (todos opcionais):
      ativo=true|false   filtra pelo status
      escola=<uuid>      filtra por escola (fora do escopo/malformado → vazio)
      busca=<texto>      parte do nome (sem diferenciar maiúsculas)
      page=<n>           liga a paginação (fora do intervalo → última)
      page_size=<n>      padrão 10, máximo 50

    SEM `page`: devolve um array simples, como antes (outras telas usam a lista
    completa, ex.: selects de disciplina).

    COM `page`:
      {
        "count": 12, "pagina": 1, "total_paginas": 2, "page_size": 10,
        "totais": {"ativas": 10, "inativas": 2},   # p/ os contadores das abas
        "results": [ ...DisciplinaListaSerializer (com `professores`)... ]
      }

    Custo fixo por página: count, página, prefetch dos vínculos e totais.
    """
    base = filtrar_por(Disciplina.objects.all(), request, 'escola', Escola, 'escola')
    busca = (request.query_params.get('busca') or '').strip()
    if busca:
        base = base.filter(nome__icontains=busca)

    ativo = _param_bool(request.query_params.get('ativo'))
    disciplinas = base if ativo is None else base.filter(ativo=ativo)
    disciplinas = disciplinas.select_related('escola').order_by('escola__nome', 'nome', 'id')

    if 'page' not in request.query_params:
        return Response(DisciplinaSerializer(disciplinas, many=True).data)

    disciplinas = disciplinas.prefetch_related(
        Prefetch(
            'usuario_disciplinas',
            queryset=UsuarioDisciplina.objects.select_related('usuario').order_by('usuario__nome'),
            to_attr='professores_listagem',
        ),
    )

    page_size = _param_int(
        request.query_params.get('page_size'),
        DISCIPLINAS_POR_PAGINA, 1, DISCIPLINAS_POR_PAGINA_MAX,
    )
    pagina = Paginator(disciplinas, page_size).get_page(request.query_params.get('page'))

    # Totais das abas respeitam escola e busca, mas não o filtro `ativo`.
    totais = base.aggregate(
        ativas=Count('id', filter=Q(ativo=True)),
        inativas=Count('id', filter=Q(ativo=False)),
    )
    totais = {chave: valor or 0 for chave, valor in totais.items()}

    return Response({
        'count': pagina.paginator.count,
        'pagina': pagina.number,
        'total_paginas': pagina.paginator.num_pages,
        'page_size': page_size,
        'totais': totais,
        'results': DisciplinaListaSerializer(pagina.object_list, many=True).data,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def criar_disciplina(request):
    user = request.user
    if not pode_gerenciar(user):
        return _sem_permissao()

    escola_id, instituicao_id, erro = resolver_escopo_criacao(user, request.data)
    if erro:
        return erro

    # _base_manager: o resolver já garantiu que a escola é do escopo do usuário.
    if not Escola._base_manager.filter(id=escola_id, ativa=True).exists():
        return Response({'error': 'Não é possível criar disciplinas em uma escola desativada.'},
                        status=status.HTTP_400_BAD_REQUEST)

    serializer = DisciplinaSerializer(data=request.data, context={'escola_id': escola_id})
    disciplina = _validar_e_salvar(serializer, escola_id, instituicao_id=instituicao_id, escola_id=escola_id)
    return Response(DisciplinaSerializer(disciplina).data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def detalhe_disciplina(request, disciplina_id):
    disciplina, erro = _disciplina_ou_404(disciplina_id)
    if erro:
        return erro
    return Response(DisciplinaSerializer(disciplina).data)


@api_view(['PATCH', 'PUT'])
@permission_classes([IsAuthenticated])
def atualizar_disciplina(request, disciplina_id):
    if not pode_gerenciar(request.user):
        return _sem_permissao()

    disciplina, erro = _disciplina_ou_404(disciplina_id)
    if erro:
        return erro

    # escola/instituicao são read_only: a disciplina não muda de dono.
    partial = request.method == 'PATCH'
    serializer = DisciplinaSerializer(disciplina, data=request.data, partial=partial)
    disciplina = _validar_e_salvar(serializer, disciplina.escola_id)
    return Response(DisciplinaSerializer(disciplina).data)


# ============================================================
# Vínculo usuário ↔ disciplina
# ============================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_professores_disciplina(request, disciplina_id):
    disciplina, erro = _disciplina_ou_404(disciplina_id)
    if erro:
        return erro

    vinculos = UsuarioDisciplina.objects.filter(disciplina=disciplina).select_related('usuario', 'disciplina')
    return Response(UsuarioDisciplinaSerializer(vinculos, many=True).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def vincular_usuario_disciplina(request, disciplina_id):
    if not pode_gerenciar(request.user):
        return _sem_permissao()

    disciplina, erro = _disciplina_ou_404(disciplina_id)
    if erro:
        return erro

    usuario_id = request.data.get('usuario')
    if not usuario_id:
        return Response({'error': 'Campo usuario é obrigatório.'}, status=status.HTTP_400_BAD_REQUEST)

    usuario = buscar_no_escopo(Usuario, usuario_id)
    if usuario is None:
        return Response({'error': 'Usuário não encontrado.'}, status=status.HTTP_404_NOT_FOUND)

    # Mesma regra do salvamento com `professores`: escola, ativo e nível.
    ja_vinculados = UsuarioDisciplina.objects.filter(disciplina=disciplina).values_list('usuario_id', flat=True)
    _, erro = validar_professores_disciplina(disciplina.escola_id, [usuario.id], ja_vinculados)
    if erro:
        return Response({'error': erro}, status=status.HTTP_400_BAD_REQUEST)

    vinculo, criado = UsuarioDisciplina.objects.get_or_create(
        usuario=usuario, disciplina=disciplina,
        defaults={'escola_id': disciplina.escola_id, 'instituicao_id': disciplina.instituicao_id},
    )
    status_code = status.HTTP_201_CREATED if criado else status.HTTP_200_OK
    return Response(UsuarioDisciplinaSerializer(vinculo).data, status=status_code)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def desvincular_usuario_disciplina(request, disciplina_id, usuario_id):
    if not pode_gerenciar(request.user):
        return _sem_permissao()

    disciplina, erro = _disciplina_ou_404(disciplina_id)
    if erro:
        return erro

    try:
        deletados, _ = UsuarioDisciplina.objects.filter(disciplina=disciplina, usuario_id=usuario_id).delete()
    except (ValidationError, ValueError):  # usuario_id malformado
        deletados = 0
    if not deletados:
        return Response({'error': 'Vínculo não encontrado.'}, status=status.HTTP_404_NOT_FOUND)

    return Response(status=status.HTTP_204_NO_CONTENT)