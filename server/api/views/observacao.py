"""Endpoints de RegistroObservacao e ObservacaoTranscricao."""

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.models import RegistroObservacao, ObservacaoTranscricao, Aluno, Turma, UsuarioTurma
from api.serializers import RegistroObservacaoSerializer, ObservacaoTranscricaoSerializer
from api.tenancy import is_superadmin as _is_superadmin


def _pode_gerenciar_geral(user):
    return _is_superadmin(user) or user.nivel in ('admin', 'coordenador')


def _professor_vinculado_turma(usuario, turma):
    return UsuarioTurma.objects.filter(usuario=usuario, turma=turma).exists()


def _pode_editar(user, registro):
    if _pode_gerenciar_geral(user):
        return True
    return registro.professor_id == user.id


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_registros_observacao(request):
    registros = RegistroObservacao.objects.all()
    aluno_id = request.query_params.get('aluno')
    if aluno_id:
        registros = registros.filter(aluno_id=aluno_id)
    return Response(RegistroObservacaoSerializer(registros.order_by('-data_observacao'), many=True).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def criar_registro_observacao(request):
    user = request.user
    aluno_id = request.data.get('aluno')
    if not aluno_id:
        return Response({'error': 'Campo aluno é obrigatório.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        aluno = Aluno.objects.get(id=aluno_id)
    except Aluno.DoesNotExist:
        return Response({'error': 'Aluno não encontrado.'}, status=status.HTTP_404_NOT_FOUND)

    if not _pode_gerenciar_geral(user) and not _professor_vinculado_turma(user, aluno.turma):
        return Response({'error': 'Você não está vinculado à turma desse aluno.'},
                         status=status.HTTP_403_FORBIDDEN)

    serializer = RegistroObservacaoSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    registro = serializer.save(
        aluno=aluno, professor=user, escola_id=aluno.escola_id, instituicao_id=aluno.instituicao_id,
    )
    return Response(RegistroObservacaoSerializer(registro).data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def detalhe_registro_observacao(request, registro_id):
    try:
        registro = RegistroObservacao.objects.get(id=registro_id)
    except RegistroObservacao.DoesNotExist:
        return Response({'error': 'Registro não encontrado.'}, status=status.HTTP_404_NOT_FOUND)
    return Response(RegistroObservacaoSerializer(registro).data)


@api_view(['PATCH', 'PUT'])
@permission_classes([IsAuthenticated])
def atualizar_registro_observacao(request, registro_id):
    try:
        registro = RegistroObservacao.objects.get(id=registro_id)
    except RegistroObservacao.DoesNotExist:
        return Response({'error': 'Registro não encontrado.'}, status=status.HTTP_404_NOT_FOUND)
    if not _pode_editar(request.user, registro):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    partial = request.method == 'PATCH'
    serializer = RegistroObservacaoSerializer(registro, data=request.data, partial=partial)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def deletar_registro_observacao(request, registro_id):
    try:
        registro = RegistroObservacao.objects.get(id=registro_id)
    except RegistroObservacao.DoesNotExist:
        return Response({'error': 'Registro não encontrado.'}, status=status.HTTP_404_NOT_FOUND)
    if not _pode_editar(request.user, registro):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)
    registro.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_observacoes_transcricao(request):
    observacoes = ObservacaoTranscricao.objects.all()
    turma_id = request.query_params.get('turma')
    if turma_id:
        observacoes = observacoes.filter(turma_id=turma_id)
    aluno_id = request.query_params.get('aluno')
    if aluno_id:
        observacoes = observacoes.filter(aluno_id=aluno_id)
    return Response(ObservacaoTranscricaoSerializer(observacoes.order_by('-data_observacao'), many=True).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def criar_observacao_transcricao(request):
    """
    Criação manual/básica. A geração automática a partir do áudio transcrito
    (preenchendo transcricao_completa, metadados_ia, etc.) fica pra quando
    construirmos a integração de transcrição de áudio.
    """
    user = request.user
    turma_id = request.data.get('turma')
    if not turma_id:
        return Response({'error': 'Campo turma é obrigatório.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        turma = Turma.objects.get(id=turma_id)
    except Turma.DoesNotExist:
        return Response({'error': 'Turma não encontrada.'}, status=status.HTTP_404_NOT_FOUND)

    if not _pode_gerenciar_geral(user) and not _professor_vinculado_turma(user, turma):
        return Response({'error': 'Você não está vinculado a essa turma.'},
                         status=status.HTTP_403_FORBIDDEN)

    serializer = ObservacaoTranscricaoSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    observacao = serializer.save(
        turma=turma, professor=user, escola_id=turma.escola_id, instituicao_id=turma.instituicao_id,
    )
    return Response(ObservacaoTranscricaoSerializer(observacao).data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def detalhe_observacao_transcricao(request, observacao_id):
    try:
        observacao = ObservacaoTranscricao.objects.get(id=observacao_id)
    except ObservacaoTranscricao.DoesNotExist:
        return Response({'error': 'Observação não encontrada.'}, status=status.HTTP_404_NOT_FOUND)
    return Response(ObservacaoTranscricaoSerializer(observacao).data)


@api_view(['PATCH', 'PUT'])
@permission_classes([IsAuthenticated])
def atualizar_observacao_transcricao(request, observacao_id):
    try:
        observacao = ObservacaoTranscricao.objects.get(id=observacao_id)
    except ObservacaoTranscricao.DoesNotExist:
        return Response({'error': 'Observação não encontrada.'}, status=status.HTTP_404_NOT_FOUND)
    if not _pode_editar(request.user, observacao):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    partial = request.method == 'PATCH'
    serializer = ObservacaoTranscricaoSerializer(observacao, data=request.data, partial=partial)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def deletar_observacao_transcricao(request, observacao_id):
    try:
        observacao = ObservacaoTranscricao.objects.get(id=observacao_id)
    except ObservacaoTranscricao.DoesNotExist:
        return Response({'error': 'Observação não encontrada.'}, status=status.HTTP_404_NOT_FOUND)
    if not _pode_editar(request.user, observacao):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)
    observacao.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)