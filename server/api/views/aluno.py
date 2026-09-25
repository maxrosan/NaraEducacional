"""Endpoints de Aluno."""

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.escopo import buscar_no_escopo, pode_gerenciar, pode_ver_escola
from api.models import Aluno, Turma
from api.serializers import AlunoSerializer


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_alunos(request):
    """Já filtrado pelo TenantManager. Aceita ?turma=<uuid> pra filtrar por turma."""
    alunos = Aluno.objects.all()
    turma_id = request.query_params.get('turma')
    if turma_id:
        turma = buscar_no_escopo(Turma, turma_id)
        if turma is None:  # inexistente, fora do escopo ou UUID malformado
            return Response([])
        alunos = alunos.filter(turma=turma)
    return Response(AlunoSerializer(alunos.order_by('nome_completo'), many=True).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def criar_aluno(request):
    user = request.user
    if not pode_gerenciar(user):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    turma_id = request.data.get('turma')
    if not turma_id:
        return Response({'error': 'Campo turma é obrigatório.'}, status=status.HTTP_400_BAD_REQUEST)

    turma = buscar_no_escopo(Turma, turma_id)
    if turma is None:
        return Response({'error': 'Turma não encontrada.'}, status=status.HTTP_404_NOT_FOUND)

    # O TenantManager já barrou turmas fora do escopo; isto é a segunda camada.
    if not pode_ver_escola(user, turma.escola):
        return Response({'error': 'Turma fora do seu escopo.'}, status=status.HTTP_403_FORBIDDEN)

    serializer = AlunoSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    aluno = serializer.save(
        turma=turma, escola_id=turma.escola_id, instituicao_id=turma.instituicao_id,
    )
    return Response(AlunoSerializer(aluno).data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def detalhe_aluno(request, aluno_id):
    aluno = buscar_no_escopo(Aluno, aluno_id)
    if aluno is None:
        return Response({'error': 'Aluno não encontrado.'}, status=status.HTTP_404_NOT_FOUND)
    return Response(AlunoSerializer(aluno).data)


@api_view(['PATCH', 'PUT'])
@permission_classes([IsAuthenticated])
def atualizar_aluno(request, aluno_id):
    if not pode_gerenciar(request.user):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    aluno = buscar_no_escopo(Aluno, aluno_id)
    if aluno is None:
        return Response({'error': 'Aluno não encontrado.'}, status=status.HTTP_404_NOT_FOUND)

    nova_turma_id = request.data.get('turma')
    if nova_turma_id and str(nova_turma_id) != str(aluno.turma_id):
        nova_turma = buscar_no_escopo(Turma, nova_turma_id)
        if nova_turma is None:
            return Response({'error': 'Turma não encontrada.'}, status=status.HTTP_404_NOT_FOUND)
        if nova_turma.escola_id != aluno.escola_id:
            return Response({'error': 'Não é possível mover o aluno para uma turma de outra escola.'},
                            status=status.HTTP_400_BAD_REQUEST)

    partial = request.method == 'PATCH'
    serializer = AlunoSerializer(aluno, data=request.data, partial=partial)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data)