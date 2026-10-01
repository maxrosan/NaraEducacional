"""Endpoints de Pergunta e PerguntaEspecialista.

Pergunta é um cadastro "oficial OU customizado": as oficiais (escola e
instituição nulas) valem para todas as escolas, sem exceção; cada escola pode
criar perguntas a mais. PerguntaEspecialista pertence sempre a uma escola.

O `campo_experiencia` de uma pergunta segue a mesma regra: precisa ser um
campo oficial ou da própria escola da pergunta (pergunta oficial → só campo
oficial). O serializer aceita qualquer id (`CampoPedagogico.todos`) para não
barrar os oficiais; o recorte é feito aqui, em `_campo_invalido`.

PerguntaEspecialista tem referência BNCC obrigatória (ver
PerguntaEspecialistaSerializer). Não há exclusão: registros de observação
apontam para a pergunta, então ela é desativada (status = inativa).
"""

import uuid

from django.core.paginator import Paginator
from django.db.models import Count, Q
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.escopo import (
    SEM_ESCOLA_OFICIAL, buscar_no_escopo, buscar_oficial_ou_da_escola, buscar_visivel, dono_ou_gestao,
    eh_especialista, filtrar_por, filtro_visiveis, pode_editar, pode_gerenciar, resolver_escopo_criacao,
)
from api.models import CampoPedagogico, Escola, Pergunta, PerguntaEspecialista
from api.serializers import PerguntaSerializer, PerguntaEspecialistaSerializer


def _sem_permissao():
    return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)


def _nao_encontrado():
    return Response({'error': 'Pergunta não encontrada.'}, status=status.HTTP_404_NOT_FOUND)


PERGUNTAS_POR_PAGINA = 10
PERGUNTAS_POR_PAGINA_MAX = 50
STATUS_PERGUNTA = ('ativa', 'inativa')


def _param_int(valor, padrao, minimo, maximo):
    try:
        return max(minimo, min(int(valor), maximo))
    except (TypeError, ValueError):
        return padrao


def _campo_invalido(request, escola_id):
    """Se o body informa `campo_experiencia`, ele precisa ser oficial ou da
    escola `escola_id` (None = pergunta oficial → só campo oficial).
    Retorna `erro` ou None."""
    campo_id = request.data.get('campo_experiencia')
    if not campo_id:
        return None
    if buscar_oficial_ou_da_escola(CampoPedagogico, campo_id, escola_id) is None:
        return Response({'error': 'Campo de experiência não encontrado para esta escola.'},
                        status=status.HTTP_400_BAD_REQUEST)
    return None


def _salvar_edicao(request, obj, serializer_class):
    partial = request.method == 'PATCH'
    serializer = serializer_class(obj, data=request.data, partial=partial)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data)


# ============================================================
# Pergunta
# ============================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_perguntas(request):
    perguntas = Pergunta.todos.filter(filtro_visiveis(request.user))

    faixa_etaria = request.query_params.get('faixa_etaria')
    if faixa_etaria:
        perguntas = perguntas.filter(faixa_etaria=faixa_etaria)

    return Response(PerguntaSerializer(perguntas, many=True).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def criar_pergunta(request):
    user = request.user
    if not pode_gerenciar(user):
        return _sem_permissao()

    escola_id, instituicao_id, erro = resolver_escopo_criacao(user, request.data, sem_escola=SEM_ESCOLA_OFICIAL)
    if erro:
        return erro

    erro = _campo_invalido(request, escola_id)
    if erro:
        return erro

    serializer = PerguntaSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    pergunta = serializer.save(instituicao_id=instituicao_id, escola_id=escola_id)
    return Response(PerguntaSerializer(pergunta).data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def detalhe_pergunta(request, pergunta_id):
    pergunta = buscar_visivel(Pergunta, pergunta_id, request.user)
    if pergunta is None:
        return _nao_encontrado()
    return Response(PerguntaSerializer(pergunta).data)


@api_view(['PATCH', 'PUT'])
@permission_classes([IsAuthenticated])
def atualizar_pergunta(request, pergunta_id):
    user = request.user
    if not pode_gerenciar(user):
        return _sem_permissao()

    pergunta = buscar_visivel(Pergunta, pergunta_id, user)
    if pergunta is None:
        return _nao_encontrado()

    erro = pode_editar(user, pergunta)  # oficial: só superadmin
    if erro:
        return erro

    erro = _campo_invalido(request, pergunta.escola_id)
    if erro:
        return erro
    return _salvar_edicao(request, pergunta, PerguntaSerializer)


# ============================================================
# PerguntaEspecialista (sempre de uma escola; TenantManager)
# ============================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_perguntas_especialistas(request):
    """
    GET /perguntas-especialistas/ — já vem recortado pelo TenantManager.

    Query params (todos opcionais):
      status=ativa|inativa   filtra pelo status
      escola=<uuid>          fora do escopo/malformado → vazio
      nivel=<texto>          ex.: "Nível 3", "2º ANO"
      campo=<uuid>           campo de experiência
      busca=<texto>          parte da pergunta ou do código BNCC
      page=<n>               liga a paginação (fora do intervalo → última)
      page_size=<n>          padrão 10, máximo 50

    SEM `page`: array simples (mais recentes primeiro), como antes — o
    formulário de observação usa a lista completa.

    COM `page`:
      {
        "count": 37, "pagina": 1, "total_paginas": 4, "page_size": 10,
        "totais": {"ativas": 30, "inativas": 7},   # p/ as abas
        "results": [ ...PerguntaEspecialistaSerializer... ]
      }
    """
    base = filtrar_por(PerguntaEspecialista.objects.all(), request, 'escola', Escola, 'escola')
    # Campo oficial não passa pelo TenantManager; como `base` já está no escopo,
    # filtrar pelo id é seguro. Id malformado → vazio.
    campo_id = request.query_params.get('campo')
    if campo_id:
        try:
            base = base.filter(campo_experiencia_id=uuid.UUID(str(campo_id)))
        except ValueError:
            base = base.none()
    nivel = (request.query_params.get('nivel') or '').strip()
    if nivel:
        base = base.filter(nivel=nivel)
    busca = (request.query_params.get('busca') or '').strip()
    if busca:
        base = base.filter(
            Q(pergunta__icontains=busca) | Q(pergunta_facilitadora__icontains=busca)
            | Q(habilidade_bncc__codigo__icontains=busca)
        )

    status_pedido = request.query_params.get('status')
    perguntas = base.filter(status=status_pedido) if status_pedido in STATUS_PERGUNTA else base
    perguntas = perguntas.select_related(
        'campo_experiencia', 'habilidade_bncc', 'escola', 'usuario_especialista',
    ).order_by('-criado_em', 'id')

    if 'page' not in request.query_params:
        return Response(PerguntaEspecialistaSerializer(perguntas, many=True).data)

    page_size = _param_int(
        request.query_params.get('page_size'),
        PERGUNTAS_POR_PAGINA, 1, PERGUNTAS_POR_PAGINA_MAX,
    )
    pagina = Paginator(perguntas, page_size).get_page(request.query_params.get('page'))

    # Totais das abas respeitam os outros filtros, mas não o de status.
    totais = base.aggregate(
        ativas=Count('id', filter=Q(status='ativa')),
        inativas=Count('id', filter=Q(status='inativa')),
    )
    totais = {chave: valor or 0 for chave, valor in totais.items()}

    return Response({
        'count': pagina.paginator.count,
        'pagina': pagina.number,
        'total_paginas': pagina.paginator.num_pages,
        'page_size': page_size,
        'totais': totais,
        'results': PerguntaEspecialistaSerializer(pagina.object_list, many=True).data,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def criar_pergunta_especialista(request):
    """Gestão (admin/coordenador/superadmin) cria na escola escolhida, pela
    mesma regra dos outros cadastros (coordenador: sempre a própria escola).
    Especialista cria na própria escola. Quem cria fica registrado em
    `usuario_especialista`."""
    user = request.user
    if pode_gerenciar(user):
        escola_id, instituicao_id, erro = resolver_escopo_criacao(user, request.data)
        if erro:
            return erro
    elif eh_especialista(user):
        if user.escola_id is None or user.instituicao_id is None:
            return Response({'error': 'Usuário sem escola/instituição vinculada.'},
                            status=status.HTTP_400_BAD_REQUEST)
        escola_id, instituicao_id = user.escola_id, user.instituicao_id
    else:
        return _sem_permissao()

    # _base_manager: a escola já foi resolvida dentro do escopo do usuário.
    if not Escola._base_manager.filter(id=escola_id, ativa=True).exists():
        return Response({'error': 'Não é possível criar perguntas em uma escola desativada.'},
                        status=status.HTTP_400_BAD_REQUEST)

    erro = _campo_invalido(request, escola_id)
    if erro:
        return erro

    serializer = PerguntaEspecialistaSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    pergunta = serializer.save(
        usuario_especialista=user, escola_id=escola_id, instituicao_id=instituicao_id,
    )
    return Response(PerguntaEspecialistaSerializer(pergunta).data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def detalhe_pergunta_especialista(request, pergunta_id):
    pergunta = buscar_no_escopo(PerguntaEspecialista, pergunta_id)
    if pergunta is None:
        return _nao_encontrado()
    return Response(PerguntaEspecialistaSerializer(pergunta).data)


@api_view(['PATCH', 'PUT'])
@permission_classes([IsAuthenticated])
def atualizar_pergunta_especialista(request, pergunta_id):
    pergunta = buscar_no_escopo(PerguntaEspecialista, pergunta_id)
    if pergunta is None:
        return _nao_encontrado()

    if not dono_ou_gestao(request.user, pergunta, campo_dono='usuario_especialista_id'):
        return _sem_permissao()

    erro = _campo_invalido(request, pergunta.escola_id)
    if erro:
        return erro
    return _salvar_edicao(request, pergunta, PerguntaEspecialistaSerializer)