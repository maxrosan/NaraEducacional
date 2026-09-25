"""Endpoints de Instituicao (topo da hierarquia multi-tenant)."""

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.models import Instituicao
from api.serializers import InstituicaoSerializer
from api.tenancy import is_superadmin as _is_superadmin


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_instituicoes(request):
    """Lista todas as instituições. Só superadmin."""
    if not _is_superadmin(request.user):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    instituicoes = Instituicao.objects.all().order_by('nome')
    return Response(InstituicaoSerializer(instituicoes, many=True).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def criar_instituicao(request):
    """Cria uma nova instituição. Só superadmin."""
    if not _is_superadmin(request.user):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    serializer = InstituicaoSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def detalhe_instituicao(request, instituicao_id):
    """Detalhe de uma instituição. Superadmin vê qualquer uma; admin só a própria."""
    if not _is_superadmin(request.user) and str(request.user.instituicao_id) != str(instituicao_id):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    try:
        instituicao = Instituicao.objects.get(id=instituicao_id)
    except Instituicao.DoesNotExist:
        return Response({'error': 'Instituição não encontrada.'}, status=status.HTTP_404_NOT_FOUND)

    return Response(InstituicaoSerializer(instituicao).data)


@api_view(['PATCH', 'PUT'])
@permission_classes([IsAuthenticated])
def atualizar_instituicao(request, instituicao_id):
    """Atualiza uma instituição. Superadmin edita qualquer uma; admin só a própria."""
    if not _is_superadmin(request.user) and str(request.user.instituicao_id) != str(instituicao_id):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    try:
        instituicao = Instituicao.objects.get(id=instituicao_id)
    except Instituicao.DoesNotExist:
        return Response({'error': 'Instituição não encontrada.'}, status=status.HTTP_404_NOT_FOUND)

    partial = request.method == 'PATCH'
    serializer = InstituicaoSerializer(instituicao, data=request.data, partial=partial)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data)