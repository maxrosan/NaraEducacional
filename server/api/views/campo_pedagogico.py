"""Endpoints de CampoPedagogico e HabilidadeBNCC (tabela global).

CampoPedagogico é um cadastro "oficial OU customizado": os oficiais (escola e
instituição nulas) valem para todas as escolas; cada escola pode criar os
seus. Leitura/busca pelo manager `todos` + `escopo.filtro_visiveis`.
"""

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.escopo import (
    SEM_ESCOLA_OFICIAL, buscar_no_escopo, buscar_visivel, filtro_visiveis, pode_editar, pode_gerenciar,
    resolver_escopo_criacao,
)
from api.models import CampoPedagogico, HabilidadeBNCC
from api.serializers import CampoPedagogicoSerializer, HabilidadeBNCCSerializer
from api.tenancy import is_superadmin


def _sem_permissao():
    return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)


def _nao_encontrado(mensagem):
    return Response({'error': mensagem}, status=status.HTTP_404_NOT_FOUND)


def _salvar_edicao(request, obj, serializer_class):
    partial = request.method == 'PATCH'
    serializer = serializer_class(obj, data=request.data, partial=partial)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data)


# ============================================================
# CampoPedagogico
# ============================================================

_CAMPO_NAO_ENCONTRADO = 'Campo pedagógico não encontrado.'


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_campos_pedagogicos(request):
    campos = CampoPedagogico.todos.filter(filtro_visiveis(request.user))
    return Response(CampoPedagogicoSerializer(campos.order_by('nome'), many=True).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def criar_campo_pedagogico(request):
    user = request.user
    if not pode_gerenciar(user):
        return _sem_permissao()

    escola_id, instituicao_id, erro = resolver_escopo_criacao(user, request.data, sem_escola=SEM_ESCOLA_OFICIAL)
    if erro:
        return erro

    serializer = CampoPedagogicoSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    campo = serializer.save(instituicao_id=instituicao_id, escola_id=escola_id)
    return Response(CampoPedagogicoSerializer(campo).data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def detalhe_campo_pedagogico(request, campo_id):
    campo = buscar_visivel(CampoPedagogico, campo_id, request.user)
    if campo is None:
        return _nao_encontrado(_CAMPO_NAO_ENCONTRADO)
    return Response(CampoPedagogicoSerializer(campo).data)


@api_view(['PATCH', 'PUT'])
@permission_classes([IsAuthenticated])
def atualizar_campo_pedagogico(request, campo_id):
    user = request.user
    if not pode_gerenciar(user):
        return _sem_permissao()

    campo = buscar_visivel(CampoPedagogico, campo_id, user)
    if campo is None:
        return _nao_encontrado(_CAMPO_NAO_ENCONTRADO)

    erro = pode_editar(user, campo)  # oficial: só superadmin
    if erro:
        return erro
    return _salvar_edicao(request, campo, CampoPedagogicoSerializer)


# ============================================================
# HabilidadeBNCC — tabela 100% global, sem escola/instituicao.
# Leitura livre pra qualquer autenticado; escrita só superadmin
# (é o catálogo oficial da BNCC, não algo que cada escola edita).
# ============================================================

_HABILIDADE_NAO_ENCONTRADA = 'Habilidade não encontrada.'


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_habilidades_bncc(request):
    habilidades = HabilidadeBNCC.objects.all().order_by('codigo')
    componente = request.query_params.get('componente_curricular')
    if componente:
        habilidades = habilidades.filter(componente_curricular=componente)
    return Response(HabilidadeBNCCSerializer(habilidades, many=True).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def criar_habilidade_bncc(request):
    if not is_superadmin(request.user):
        return _sem_permissao()

    serializer = HabilidadeBNCCSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    habilidade = serializer.save()
    return Response(HabilidadeBNCCSerializer(habilidade).data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def detalhe_habilidade_bncc(request, habilidade_id):
    habilidade = buscar_no_escopo(HabilidadeBNCC, habilidade_id)  # tabela global: só trata id malformado
    if habilidade is None:
        return _nao_encontrado(_HABILIDADE_NAO_ENCONTRADA)
    return Response(HabilidadeBNCCSerializer(habilidade).data)


@api_view(['PATCH', 'PUT'])
@permission_classes([IsAuthenticated])
def atualizar_habilidade_bncc(request, habilidade_id):
    if not is_superadmin(request.user):
        return _sem_permissao()

    habilidade = buscar_no_escopo(HabilidadeBNCC, habilidade_id)
    if habilidade is None:
        return _nao_encontrado(_HABILIDADE_NAO_ENCONTRADA)
    return _salvar_edicao(request, habilidade, HabilidadeBNCCSerializer)