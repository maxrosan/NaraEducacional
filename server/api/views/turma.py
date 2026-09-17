"""Endpoints de Turma."""

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.models import Turma, Escola
from api.serializers import TurmaSerializer


def _is_superadmin(user):
    return user.is_superuser or user.nivel == 'superadmin'


def _pode_gerenciar(user):
    return _is_superadmin(user) or user.nivel in ('admin', 'coordenador')


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_turmas(request):
    """
    Já vem filtrado pelo TenantManager: admin vê as da instituição,
    demais níveis vêem as da própria escola, superadmin vê tudo.
    """
    turmas = Turma.objects.all().order_by('nome')
    return Response(TurmaSerializer(turmas, many=True).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def criar_turma(request):
    user = request.user
    if not _pode_gerenciar(user):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    if _is_superadmin(user):
        instituicao_id = request.data.get('instituicao')
        escola_id = request.data.get('escola')
        if not instituicao_id or not escola_id:
            return Response({'error': 'Campos instituicao e escola são obrigatórios.'},
                             status=status.HTTP_400_BAD_REQUEST)
    elif user.nivel == 'admin':
        if user.instituicao_id is None:
            return Response({'error': 'Usuário sem instituição vinculada.'}, status=status.HTTP_400_BAD_REQUEST)
        instituicao_id = user.instituicao_id
        escola_id = request.data.get('escola')
        if not escola_id or not Escola.objects.filter(id=escola_id, instituicao_id=instituicao_id).exists():
            return Response({'error': 'Campo escola é obrigatório e precisa pertencer à sua instituição.'},
                             status=status.HTTP_400_BAD_REQUEST)
    else:  # coordenador
        if user.escola_id is None:
            return Response({'error': 'Usuário sem escola vinculada.'}, status=status.HTTP_400_BAD_REQUEST)
        instituicao_id = user.instituicao_id
        escola_id = user.escola_id

    serializer = TurmaSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    turma = serializer.save(instituicao_id=instituicao_id, escola_id=escola_id)
    return Response(TurmaSerializer(turma).data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def detalhe_turma(request, turma_id):
    try:
        turma = Turma.objects.get(id=turma_id)
    except Turma.DoesNotExist:
        return Response({'error': 'Turma não encontrada.'}, status=status.HTTP_404_NOT_FOUND)
    return Response(TurmaSerializer(turma).data)


@api_view(['PATCH', 'PUT'])
@permission_classes([IsAuthenticated])
def atualizar_turma(request, turma_id):
    if not _pode_gerenciar(request.user):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    try:
        turma = Turma.objects.get(id=turma_id)
    except Turma.DoesNotExist:
        return Response({'error': 'Turma não encontrada.'}, status=status.HTTP_404_NOT_FOUND)

    partial = request.method == 'PATCH'
    serializer = TurmaSerializer(turma, data=request.data, partial=partial)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data)