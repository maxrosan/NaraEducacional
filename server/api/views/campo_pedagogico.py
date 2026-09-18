"""Endpoints de CampoPedagogico e HabilidadeBNCC (tabela global)."""

from django.db.models import Q
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.models import CampoPedagogico, HabilidadeBNCC
from api.serializers import CampoPedagogicoSerializer, HabilidadeBNCCSerializer


def _is_superadmin(user):
    return user.is_superuser or user.nivel == 'superadmin'


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

    if _is_superadmin(user):
        campos = CampoPedagogico.todos.all()
    elif user.nivel == 'admin':
        if user.instituicao_id is None:
            campos = CampoPedagogico.todos.filter(escola__isnull=True)
        else:
            campos = CampoPedagogico.todos.filter(
                Q(instituicao_id=user.instituicao_id) | Q(escola__isnull=True, instituicao__isnull=True),
            )
    else:
        if user.escola_id is None:
            campos = CampoPedagogico.todos.filter(escola__isnull=True)
        else:
            campos = CampoPedagogico.todos.filter(
                Q(escola_id=user.escola_id) | Q(escola__isnull=True),
            )

    return Response(CampoPedagogicoSerializer(campos.order_by('nome'), many=True).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def criar_campo_pedagogico(request):
    user = request.user
    if not _pode_gerenciar(user):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    if _is_superadmin(user):
        escola_id = request.data.get('escola')
        instituicao_id = request.data.get('instituicao')
    elif user.nivel == 'admin':
        if user.instituicao_id is None:
            return Response({'error': 'Usuário sem instituição vinculada.'}, status=status.HTTP_400_BAD_REQUEST)
        instituicao_id = user.instituicao_id
        escola_id = request.data.get('escola')
    else:  # coordenador
        if user.escola_id is None:
            return Response({'error': 'Usuário sem escola vinculada.'}, status=status.HTTP_400_BAD_REQUEST)
        instituicao_id = user.instituicao_id
        escola_id = user.escola_id

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

    if campo.escola_id is None:
        pass  # oficial: todo mundo vê
    elif not _is_superadmin(user) and str(campo.instituicao_id) != str(user.instituicao_id):
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

    if campo.escola_id is None and not _is_superadmin(user):
        return Response({'error': 'Só superadmin pode editar campos oficiais.'}, status=status.HTTP_403_FORBIDDEN)
    if not _is_superadmin(user) and str(campo.instituicao_id) != str(user.instituicao_id):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

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