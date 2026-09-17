"""Endpoints de Especialista."""

from django.db.models import Q
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.models import Especialista
from api.serializers import EspecialistaSerializer


def _is_superadmin(user):
    return user.is_superuser or user.nivel == 'superadmin'


def _pode_gerenciar(user):
    return _is_superadmin(user) or user.nivel == 'admin'


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_especialistas(request):
    """
    Superadmin vê todos. Admin vê os da própria instituição.
    Demais níveis veem os da própria escola + os "da rede" (sem escola específica).
    """
    user = request.user

    if _is_superadmin(user):
        especialistas = Especialista.objects.all()
    elif user.nivel == 'admin':
        if user.instituicao_id is None:
            return Response([])
        especialistas = Especialista.objects.filter(instituicao_id=user.instituicao_id)
    else:
        if user.instituicao_id is None:
            return Response([])
        especialistas = Especialista.objects.filter(
            Q(escola_id=user.escola_id) | Q(escola__isnull=True),
            instituicao_id=user.instituicao_id,
        )

    return Response(EspecialistaSerializer(especialistas, many=True).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def criar_especialista(request):
    """Cria um especialista. Superadmin informa instituicao no body; admin usa sempre a própria."""
    user = request.user
    if not _pode_gerenciar(user):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    if user.nivel == 'admin':
        if user.instituicao_id is None:
            return Response({'error': 'Usuário sem instituição vinculada.'}, status=status.HTTP_400_BAD_REQUEST)
        instituicao_id = user.instituicao_id
    else:
        instituicao_id = request.data.get('instituicao')
        if not instituicao_id:
            return Response({'error': 'Campo instituicao é obrigatório.'}, status=status.HTTP_400_BAD_REQUEST)

    serializer = EspecialistaSerializer(data=request.data, context={'instituicao_id': instituicao_id})
    serializer.is_valid(raise_exception=True)
    serializer.save(instituicao_id=instituicao_id)
    return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def detalhe_especialista(request, especialista_id):
    user = request.user
    try:
        especialista = Especialista.objects.get(id=especialista_id)
    except Especialista.DoesNotExist:
        return Response({'error': 'Especialista não encontrado.'}, status=status.HTTP_404_NOT_FOUND)

    if _is_superadmin(user):
        pass
    elif str(especialista.instituicao_id) != str(user.instituicao_id):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)
    elif user.nivel != 'admin' and especialista.escola_id and str(especialista.escola_id) != str(user.escola_id):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    return Response(EspecialistaSerializer(especialista).data)


@api_view(['PATCH', 'PUT'])
@permission_classes([IsAuthenticated])
def atualizar_especialista(request, especialista_id):
    user = request.user
    if not _pode_gerenciar(user):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    try:
        especialista = Especialista.objects.get(id=especialista_id)
    except Especialista.DoesNotExist:
        return Response({'error': 'Especialista não encontrado.'}, status=status.HTTP_404_NOT_FOUND)

    if not _is_superadmin(user) and str(especialista.instituicao_id) != str(user.instituicao_id):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    partial = request.method == 'PATCH'
    serializer = EspecialistaSerializer(
        especialista, data=request.data, partial=partial,
        context={'instituicao_id': especialista.instituicao_id},
    )
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data)