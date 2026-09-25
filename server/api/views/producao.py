"""Endpoints de Producao (portfólio) e do vínculo com Aluno."""

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.models import Producao, ProducaoAluno, Turma, Aluno, UsuarioTurma
from api.serializers import ProducaoSerializer, ProducaoAlunoSerializer
from api.tenancy import is_superadmin as _is_superadmin


def _pode_gerenciar_geral(user):
    """Admin/coordenador/superadmin gerenciam qualquer produção do escopo deles."""
    return _is_superadmin(user) or user.nivel in ('admin', 'coordenador')


def _professor_vinculado_turma(usuario, turma):
    return UsuarioTurma.objects.filter(usuario=usuario, turma=turma).exists()


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_producoes(request):
    """Já filtrado pelo TenantManager. Aceita ?turma=<uuid> e ?aluno=<uuid>."""
    producoes = Producao.objects.all()

    turma_id = request.query_params.get('turma')
    if turma_id:
        producoes = producoes.filter(turma_id=turma_id)

    aluno_id = request.query_params.get('aluno')
    if aluno_id:
        producoes = producoes.filter(producao_alunos__aluno_id=aluno_id).distinct()

    return Response(ProducaoSerializer(producoes.order_by('-criado_em'), many=True).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def criar_producao(request):
    user = request.user
    turma_id = request.data.get('turma')
    if not turma_id:
        return Response({'error': 'Campo turma é obrigatório.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        turma = Turma.objects.get(id=turma_id)  # já respeita o escopo do TenantManager
    except Turma.DoesNotExist:
        return Response({'error': 'Turma não encontrada.'}, status=status.HTTP_404_NOT_FOUND)

    if not _pode_gerenciar_geral(user):
        # Professor: só pode subir produção pra turma em que está vinculado.
        if not _professor_vinculado_turma(user, turma):
            return Response({'error': 'Você não está vinculado a essa turma.'},
                             status=status.HTTP_403_FORBIDDEN)

    serializer = ProducaoSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    producao = serializer.save(
        turma=turma, professor=user, escola_id=turma.escola_id, instituicao_id=turma.instituicao_id,
    )
    return Response(ProducaoSerializer(producao).data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def detalhe_producao(request, producao_id):
    try:
        producao = Producao.objects.get(id=producao_id)
    except Producao.DoesNotExist:
        return Response({'error': 'Produção não encontrada.'}, status=status.HTTP_404_NOT_FOUND)
    return Response(ProducaoSerializer(producao).data)


def _pode_editar_producao(user, producao):
    if _pode_gerenciar_geral(user):
        return True
    return producao.professor_id == user.id


@api_view(['PATCH', 'PUT'])
@permission_classes([IsAuthenticated])
def atualizar_producao(request, producao_id):
    try:
        producao = Producao.objects.get(id=producao_id)
    except Producao.DoesNotExist:
        return Response({'error': 'Produção não encontrada.'}, status=status.HTTP_404_NOT_FOUND)

    if not _pode_editar_producao(request.user, producao):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    partial = request.method == 'PATCH'
    serializer = ProducaoSerializer(producao, data=request.data, partial=partial)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def deletar_producao(request, producao_id):
    try:
        producao = Producao.objects.get(id=producao_id)
    except Producao.DoesNotExist:
        return Response({'error': 'Produção não encontrada.'}, status=status.HTTP_404_NOT_FOUND)

    if not _pode_editar_producao(request.user, producao):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    producao.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_alunos_producao(request, producao_id):
    try:
        producao = Producao.objects.get(id=producao_id)
    except Producao.DoesNotExist:
        return Response({'error': 'Produção não encontrada.'}, status=status.HTTP_404_NOT_FOUND)

    vinculos = ProducaoAluno.objects.filter(producao=producao).select_related('aluno')
    return Response(ProducaoAlunoSerializer(vinculos, many=True).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def vincular_aluno_producao(request, producao_id):
    try:
        producao = Producao.objects.get(id=producao_id)
    except Producao.DoesNotExist:
        return Response({'error': 'Produção não encontrada.'}, status=status.HTTP_404_NOT_FOUND)

    if not _pode_editar_producao(request.user, producao):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    aluno_id = request.data.get('aluno')
    if not aluno_id:
        return Response({'error': 'Campo aluno é obrigatório.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        aluno = Aluno.objects.get(id=aluno_id)
    except Aluno.DoesNotExist:
        return Response({'error': 'Aluno não encontrado.'}, status=status.HTTP_404_NOT_FOUND)

    if str(aluno.turma_id) != str(producao.turma_id):
        return Response({'error': 'O aluno precisa pertencer à mesma turma da produção.'},
                         status=status.HTTP_400_BAD_REQUEST)

    vinculo, criado = ProducaoAluno.objects.get_or_create(
        producao=producao, aluno=aluno,
        defaults={
            'legenda': request.data.get('legenda', ''),
            'destaque': request.data.get('destaque', False),
            'incluir_relatorio': request.data.get('incluir_relatorio', False),
        },
    )
    status_code = status.HTTP_201_CREATED if criado else status.HTTP_200_OK
    return Response(ProducaoAlunoSerializer(vinculo).data, status=status_code)


@api_view(['PATCH', 'PUT'])
@permission_classes([IsAuthenticated])
def atualizar_vinculo_producao_aluno(request, producao_id, vinculo_id):
    try:
        vinculo = ProducaoAluno.objects.get(id=vinculo_id, producao_id=producao_id)
    except ProducaoAluno.DoesNotExist:
        return Response({'error': 'Vínculo não encontrado.'}, status=status.HTTP_404_NOT_FOUND)

    if not _pode_editar_producao(request.user, vinculo.producao):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    partial = request.method == 'PATCH'
    serializer = ProducaoAlunoSerializer(vinculo, data=request.data, partial=partial)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def desvincular_aluno_producao(request, producao_id, aluno_id):
    try:
        producao = Producao.objects.get(id=producao_id)
    except Producao.DoesNotExist:
        return Response({'error': 'Produção não encontrada.'}, status=status.HTTP_404_NOT_FOUND)

    if not _pode_editar_producao(request.user, producao):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    deletados, _ = ProducaoAluno.objects.filter(producao=producao, aluno_id=aluno_id).delete()
    if not deletados:
        return Response({'error': 'Vínculo não encontrado.'}, status=status.HTTP_404_NOT_FOUND)

    return Response(status=status.HTTP_204_NO_CONTENT)