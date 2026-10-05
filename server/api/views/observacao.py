"""Endpoints de RegistroObservacao e ObservacaoTranscricao.

Regras (iguais às dos demais registros pedagógicos):
  * leitura: todos do escopo (TenantManager);
  * criação: gestão, ou professor vinculado à turma;
  * edição/exclusão: gestão, ou o professor autor.
"""

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.escopo import (
    aluno_do_body, buscar_no_escopo, buscar_oficial_ou_da_escola, dono_ou_gestao, filtrar_por,
    pode_gerenciar, professor_vinculado_turma,
)
from api.models import RegistroObservacao, ObservacaoTranscricao, Aluno, Pergunta, Turma
from api.serializers import RegistroObservacaoSerializer, ObservacaoTranscricaoSerializer


def _sem_permissao(mensagem='Sem permissão.'):
    return Response({'error': mensagem}, status=status.HTTP_403_FORBIDDEN)


def _nao_encontrado(mensagem):
    return Response({'error': mensagem}, status=status.HTTP_404_NOT_FOUND)


def _obj_ou_erro(request, model, obj_id, msg_nao_encontrado, editar=False):
    """Retorna (obj, erro). Com `editar=True` também checa a permissão."""
    obj = buscar_no_escopo(model, obj_id)
    if obj is None:
        return None, _nao_encontrado(msg_nao_encontrado)
    if editar and not dono_ou_gestao(request.user, obj):
        return None, _sem_permissao()
    return obj, None


def _salvar_edicao(request, obj, serializer_class):
    partial = request.method == 'PATCH'
    serializer = serializer_class(obj, data=request.data, partial=partial)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data)


# ============================================================
# RegistroObservacao
# ============================================================

_OBS_NAO_ENCONTRADA = 'Registro não encontrado.'


def _pergunta_invalida(request, escola_id):
    """Se o body informa `pergunta`, ela precisa ser oficial ou customizada da
    escola do registro (perguntas oficiais valem para todas as escolas).
    Retorna `erro` ou None.

    O serializer aceita qualquer id (`Pergunta.todos`) justamente para não
    barrar as oficiais; o recorte por escola é feito aqui.
    """
    pergunta_id = request.data.get('pergunta')
    if not pergunta_id:
        return None
    if buscar_oficial_ou_da_escola(Pergunta, pergunta_id, escola_id) is None:
        return Response({'error': 'Pergunta não encontrada para a escola deste aluno.'},
                        status=status.HTTP_400_BAD_REQUEST)
    return None


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_registros_observacao(request):
    registros = filtrar_por(RegistroObservacao.objects.all(), request, 'aluno', Aluno, 'aluno')
    return Response(RegistroObservacaoSerializer(registros.order_by('-data_observacao'), many=True).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def criar_registro_observacao(request):
    aluno, erro = aluno_do_body(request)
    if erro:
        return erro

    erro = _pergunta_invalida(request, aluno.escola_id)
    if erro:
        return erro

    serializer = RegistroObservacaoSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    registro = serializer.save(
        aluno=aluno, professor=request.user, escola_id=aluno.escola_id, instituicao_id=aluno.instituicao_id,
    )
    return Response(RegistroObservacaoSerializer(registro).data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def detalhe_registro_observacao(request, registro_id):
    registro, erro = _obj_ou_erro(request, RegistroObservacao, registro_id, _OBS_NAO_ENCONTRADA)
    if erro:
        return erro
    return Response(RegistroObservacaoSerializer(registro).data)


@api_view(['PATCH', 'PUT'])
@permission_classes([IsAuthenticated])
def atualizar_registro_observacao(request, registro_id):
    registro, erro = _obj_ou_erro(request, RegistroObservacao, registro_id, _OBS_NAO_ENCONTRADA, editar=True)
    if erro:
        return erro

    erro = _pergunta_invalida(request, registro.escola_id)
    if erro:
        return erro
    return _salvar_edicao(request, registro, RegistroObservacaoSerializer)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def deletar_registro_observacao(request, registro_id):
    registro, erro = _obj_ou_erro(request, RegistroObservacao, registro_id, _OBS_NAO_ENCONTRADA, editar=True)
    if erro:
        return erro
    registro.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


# ============================================================
# ObservacaoTranscricao
# ============================================================

_TRANSC_NAO_ENCONTRADA = 'Observação não encontrada.'


def _aluno_fora_da_turma(request, turma_id):
    """Se o body vincula um aluno, ele precisa existir no escopo e ser da turma.
    Retorna `erro` ou None. `aluno` nulo/ausente é permitido (transcrição sem
    criança identificada)."""
    aluno_id = request.data.get('aluno')
    if not aluno_id:
        return None
    aluno = buscar_no_escopo(Aluno, aluno_id)
    if aluno is None:
        return _nao_encontrado('Aluno não encontrado.')
    if aluno.turma_id != turma_id:
        return Response({'error': 'O aluno precisa pertencer à turma da observação.'},
                        status=status.HTTP_400_BAD_REQUEST)
    return None


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_observacoes_transcricao(request):
    observacoes = ObservacaoTranscricao.objects.all()
    observacoes = filtrar_por(observacoes, request, 'turma', Turma, 'turma')
    observacoes = filtrar_por(observacoes, request, 'aluno', Aluno, 'aluno')
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

    turma = buscar_no_escopo(Turma, turma_id)
    if turma is None:
        return _nao_encontrado('Turma não encontrada.')

    if not pode_gerenciar(user) and not professor_vinculado_turma(user, turma.id):
        return _sem_permissao('Você não está vinculado a essa turma.')

    erro = _aluno_fora_da_turma(request, turma.id)
    if erro:
        return erro

    serializer = ObservacaoTranscricaoSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    observacao = serializer.save(
        turma=turma, professor=user, escola_id=turma.escola_id, instituicao_id=turma.instituicao_id,
    )
    return Response(ObservacaoTranscricaoSerializer(observacao).data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def detalhe_observacao_transcricao(request, observacao_id):
    observacao, erro = _obj_ou_erro(request, ObservacaoTranscricao, observacao_id, _TRANSC_NAO_ENCONTRADA)
    if erro:
        return erro
    return Response(ObservacaoTranscricaoSerializer(observacao).data)


@api_view(['PATCH', 'PUT'])
@permission_classes([IsAuthenticated])
def atualizar_observacao_transcricao(request, observacao_id):
    observacao, erro = _obj_ou_erro(
        request, ObservacaoTranscricao, observacao_id, _TRANSC_NAO_ENCONTRADA, editar=True,
    )
    if erro:
        return erro

    erro = _aluno_fora_da_turma(request, observacao.turma_id)
    if erro:
        return erro
    return _salvar_edicao(request, observacao, ObservacaoTranscricaoSerializer)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def deletar_observacao_transcricao(request, observacao_id):
    observacao, erro = _obj_ou_erro(
        request, ObservacaoTranscricao, observacao_id, _TRANSC_NAO_ENCONTRADA, editar=True,
    )
    if erro:
        return erro
    observacao.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)