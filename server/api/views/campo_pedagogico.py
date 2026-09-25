"""Endpoints de CampoPedagogico e HabilidadeBNCC (tabela global)."""

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.escopo import SEM_ESCOLA_OFICIAL, filtro_visiveis, pode_editar, pode_ver, resolver_escopo_criacao
from api.models import CampoPedagogico, HabilidadeBNCC
from api.serializers import CampoPedagogicoSerializer, HabilidadeBNCCSerializer
from api.tenancy import is_superadmin as _is_superadmin


def _pode_gerenciar(user):
    return _is_superadmin(user) or user.nivel in ('admin', 'coordenador')


# ============================================================
# CampoPedagogico — usa o manager `todos` (sem tenant), filtro manual
# pra combinar "oficial (escola nula) OU da minha escola/instituição".
# ============================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_campos_pedagogicos(request):
    user = request.user

    campos = CampoPedagogico.todos.filter(filtro_visiveis(user))

    return Response(CampoPedagogicoSerializer(campos.order_by('nome'), many=True).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def criar_campo_pedagogico(request):
    user = request.user
    if not _pode_gerenciar(user):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

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
    user = request.user
    try:
        campo = CampoPedagogico.todos.get(id=campo_id)
    except CampoPedagogico.DoesNotExist:
        return Response({'error': 'Campo pedagógico não encontrado.'}, status=status.HTTP_404_NOT_FOUND)

    if not pode_ver(user, campo):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    return Response(CampoPedagogicoSerializer(campo).data)


@api_view(['PATCH', 'PUT'])
@permission_classes([IsAuthenticated])
def atualizar_campo_pedagogico(request, campo_id):
    user = request.user
    if not _pode_gerenciar(user):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    try:
        campo = CampoPedagogico.todos.get(id=campo_id)
    except CampoPedagogico.DoesNotExist:
        return Response({'error': 'Campo pedagógico não encontrado.'}, status=status.HTTP_404_NOT_FOUND)

    erro = pode_editar(user, campo)
    if erro:
        return erro

    partial = request.method == 'PATCH'
    serializer = CampoPedagogicoSerializer(campo, data=request.data, partial=partial)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data)


# ============================================================
# HabilidadeBNCC — tabela 100% global, sem escola/instituicao.
# Leitura livre pra qualquer autenticado; escrita só superadmin
# (é o catálogo oficial da BNCC, não algo que cada escola edita).
# ============================================================

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
    if not _is_superadmin(request.user):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    serializer = HabilidadeBNCCSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    habilidade = serializer.save()
    return Response(HabilidadeBNCCSerializer(habilidade).data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def detalhe_habilidade_bncc(request, habilidade_id):
    try:
        habilidade = HabilidadeBNCC.objects.get(id=habilidade_id)
    except HabilidadeBNCC.DoesNotExist:
        return Response({'error': 'Habilidade não encontrada.'}, status=status.HTTP_404_NOT_FOUND)
    return Response(HabilidadeBNCCSerializer(habilidade).data)


@api_view(['PATCH', 'PUT'])
@permission_classes([IsAuthenticated])
def atualizar_habilidade_bncc(request, habilidade_id):
    if not _is_superadmin(request.user):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    try:
        habilidade = HabilidadeBNCC.objects.get(id=habilidade_id)
    except HabilidadeBNCC.DoesNotExist:
        return Response({'error': 'Habilidade não encontrada.'}, status=status.HTTP_404_NOT_FOUND)

    partial = request.method == 'PATCH'
    serializer = HabilidadeBNCCSerializer(habilidade, data=request.data, partial=partial)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data)