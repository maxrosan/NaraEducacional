"""Endpoints de Producao (portfólio) e do vínculo com Aluno."""

from django.core.exceptions import ValidationError
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.escopo import buscar_no_escopo, filtrar_por, pode_gerenciar, professor_vinculado_turma
from api.models import Producao, ProducaoAluno, Turma, Aluno
from api.serializers import ProducaoSerializer, ProducaoAlunoSerializer


def _sem_permissao(mensagem='Sem permissão.'):
    return Response({'error': mensagem}, status=status.HTTP_403_FORBIDDEN)


def _nao_encontrado(mensagem):
    return Response({'error': mensagem}, status=status.HTTP_404_NOT_FOUND)


def _pode_editar_producao(user, producao):
    """Gestão edita qualquer produção do escopo; professor, só as próprias."""
    return pode_gerenciar(user) or producao.professor_id == user.id


def _producao_ou_erro(request, producao_id, editar=False):
    """Retorna (producao, erro). Com `editar=True` também checa a permissão.

    É SEMPRE por aqui que as rotas de vínculo chegam à produção: o
    ProducaoAluno não tem TenantManager, então o escopo vem da produção.
    """
    producao = buscar_no_escopo(Producao, producao_id)
    if producao is None:
        return None, _nao_encontrado('Produção não encontrada.')
    if editar and not _pode_editar_producao(request.user, producao):
        return None, _sem_permissao()
    return producao, None


# ---------------------------------------------------------------------------
# Produção
# ---------------------------------------------------------------------------

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_producoes(request):
    """Já filtrado pelo TenantManager. Aceita ?turma=<uuid> e ?aluno=<uuid>."""
    producoes = Producao.objects.all()
    producoes = filtrar_por(producoes, request, 'turma', Turma, 'turma')
    if request.query_params.get('aluno'):
        producoes = filtrar_por(producoes, request, 'aluno', Aluno, 'producao_alunos__aluno').distinct()
    return Response(ProducaoSerializer(producoes.order_by('-criado_em'), many=True).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def criar_producao(request):
    user = request.user
    turma_id = request.data.get('turma')
    if not turma_id:
        return Response({'error': 'Campo turma é obrigatório.'}, status=status.HTTP_400_BAD_REQUEST)

    turma = buscar_no_escopo(Turma, turma_id)
    if turma is None:
        return _nao_encontrado('Turma não encontrada.')

    # Professor: só pode subir produção pra turma em que está vinculado.
    if not pode_gerenciar(user) and not professor_vinculado_turma(user, turma.id):
        return _sem_permissao('Você não está vinculado a essa turma.')

    serializer = ProducaoSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    producao = serializer.save(
        turma=turma, professor=user, escola_id=turma.escola_id, instituicao_id=turma.instituicao_id,
    )
    return Response(ProducaoSerializer(producao).data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def detalhe_producao(request, producao_id):
    producao, erro = _producao_ou_erro(request, producao_id)
    if erro:
        return erro
    return Response(ProducaoSerializer(producao).data)


@api_view(['PATCH', 'PUT'])
@permission_classes([IsAuthenticated])
def atualizar_producao(request, producao_id):
    producao, erro = _producao_ou_erro(request, producao_id, editar=True)
    if erro:
        return erro

    partial = request.method == 'PATCH'
    serializer = ProducaoSerializer(producao, data=request.data, partial=partial)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def deletar_producao(request, producao_id):
    producao, erro = _producao_ou_erro(request, producao_id, editar=True)
    if erro:
        return erro

    producao.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Vínculo produção ↔ aluno
# ---------------------------------------------------------------------------

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_alunos_producao(request, producao_id):
    producao, erro = _producao_ou_erro(request, producao_id)
    if erro:
        return erro

    vinculos = ProducaoAluno.objects.filter(producao=producao).select_related('aluno')
    return Response(ProducaoAlunoSerializer(vinculos, many=True).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def vincular_aluno_producao(request, producao_id):
    producao, erro = _producao_ou_erro(request, producao_id, editar=True)
    if erro:
        return erro

    aluno_id = request.data.get('aluno')
    if not aluno_id:
        return Response({'error': 'Campo aluno é obrigatório.'}, status=status.HTTP_400_BAD_REQUEST)

    aluno = buscar_no_escopo(Aluno, aluno_id)
    if aluno is None:
        return _nao_encontrado('Aluno não encontrado.')

    if aluno.turma_id != producao.turma_id:
        return Response({'error': 'O aluno precisa pertencer à mesma turma da produção.'},
                        status=status.HTTP_400_BAD_REQUEST)

    existente = ProducaoAluno.objects.filter(producao=producao, aluno=aluno).first()
    if existente:
        return Response(ProducaoAlunoSerializer(existente).data, status=status.HTTP_200_OK)

    # Serializer (e não request.data cru) para converter legenda/destaque/
    # incluir_relatorio: em multipart, "false" chega como string truthy.
    serializer = ProducaoAlunoSerializer(data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    vinculo = serializer.save(producao=producao, aluno=aluno)
    return Response(ProducaoAlunoSerializer(vinculo).data, status=status.HTTP_201_CREATED)


@api_view(['PATCH', 'PUT'])
@permission_classes([IsAuthenticated])
def atualizar_vinculo_producao_aluno(request, producao_id, vinculo_id):
    producao, erro = _producao_ou_erro(request, producao_id, editar=True)
    if erro:
        return erro

    try:
        vinculo = ProducaoAluno.objects.filter(id=vinculo_id, producao=producao).first()
    except (ValidationError, ValueError):  # vinculo_id malformado
        vinculo = None
    if vinculo is None:
        return _nao_encontrado('Vínculo não encontrado.')

    partial = request.method == 'PATCH'
    serializer = ProducaoAlunoSerializer(vinculo, data=request.data, partial=partial)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def desvincular_aluno_producao(request, producao_id, aluno_id):
    producao, erro = _producao_ou_erro(request, producao_id, editar=True)
    if erro:
        return erro

    try:
        deletados, _ = ProducaoAluno.objects.filter(producao=producao, aluno_id=aluno_id).delete()
    except (ValidationError, ValueError):  # aluno_id malformado
        deletados = 0
    if not deletados:
        return _nao_encontrado('Vínculo não encontrado.')

    return Response(status=status.HTTP_204_NO_CONTENT)