"""Endpoints de Aluno."""

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.models import Aluno, Turma, Escola
from api.serializers import AlunoSerializer


def _is_superadmin(user):
    return user.is_superuser or user.nivel == 'superadmin'


def _pode_gerenciar(user):
    return _is_superadmin(user) or user.nivel in ('admin', 'coordenador')


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_alunos(request):
    """Já filtrado pelo TenantManager. Aceita ?turma=<uuid> pra filtrar por turma."""
    alunos = Aluno.objects.all()
    turma_id = request.query_params.get('turma')
    if turma_id:
        alunos = alunos.filter(turma_id=turma_id)
    return Response(AlunoSerializer(alunos.order_by('nome_completo'), many=True).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def criar_aluno(request):
    user = request.user
    if not _pode_gerenciar(user):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    turma_id = request.data.get('turma')
    if not turma_id:
        return Response({'error': 'Campo turma é obrigatório.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        turma = Turma.objects.get(id=turma_id)  # já respeita o escopo do TenantManager
    except Turma.DoesNotExist:
        return Response({'error': 'Turma não encontrada.'}, status=status.HTTP_404_NOT_FOUND)

    if not _is_superadmin(user) and user.nivel == 'admin' and str(turma.instituicao_id) != str(user.instituicao_id):
        return Response({'error': 'Turma não pertence à sua instituição.'}, status=status.HTTP_403_FORBIDDEN)
    if user.nivel == 'coordenador' and str(turma.escola_id) != str(user.escola_id):
        return Response({'error': 'Turma não pertence à sua escola.'}, status=status.HTTP_403_FORBIDDEN)

    serializer = AlunoSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    aluno = serializer.save(
        turma=turma, escola_id=turma.escola_id, instituicao_id=turma.instituicao_id,
    )
    return Response(AlunoSerializer(aluno).data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def detalhe_aluno(request, aluno_id):
    try:
        aluno = Aluno.objects.get(id=aluno_id)
    except Aluno.DoesNotExist:
        return Response({'error': 'Aluno não encontrado.'}, status=status.HTTP_404_NOT_FOUND)
    return Response(AlunoSerializer(aluno).data)


@api_view(['PATCH', 'PUT'])
@permission_classes([IsAuthenticated])
def atualizar_aluno(request, aluno_id):
    if not _pode_gerenciar(request.user):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    try:
        aluno = Aluno.objects.get(id=aluno_id)
    except Aluno.DoesNotExist:
        return Response({'error': 'Aluno não encontrado.'}, status=status.HTTP_404_NOT_FOUND)

    data = dict(request.data)
    nova_turma_id = data.get('turma')
    if nova_turma_id and str(nova_turma_id) != str(aluno.turma_id):
        try:
            nova_turma = Turma.objects.get(id=nova_turma_id)
        except Turma.DoesNotExist:
            return Response({'error': 'Turma não encontrada.'}, status=status.HTTP_404_NOT_FOUND)
        if str(nova_turma.escola_id) != str(aluno.escola_id):
            return Response({'error': 'Não é possível mover o aluno para uma turma de outra escola.'},
                             status=status.HTTP_400_BAD_REQUEST)

    partial = request.method == 'PATCH'
    serializer = AlunoSerializer(aluno, data=data, partial=partial)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data)