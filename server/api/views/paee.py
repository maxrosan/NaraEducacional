"""Endpoints de MetaPAEE, SessaoEspecialista, SessaoPAEEMeta e TarefaPAEE."""

from django.core.exceptions import ValidationError
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.escopo import buscar_no_escopo, filtrar_por, pode_gerenciar, professor_vinculado_turma
from api.models import MetaPAEE, SessaoEspecialista, SessaoPAEEMeta, TarefaPAEE, Aluno
from api.serializers import (
    MetaPAEESerializer, SessaoEspecialistaSerializer, SessaoPAEEMetaSerializer, TarefaPAEESerializer,
)

NIVEIS_ESPECIALISTA = ('especialista', 'professor_especialista')

# O que um professor (sem gestão de PAEE) pode alterar numa tarefa.
CAMPOS_CONCLUSAO_TAREFA = ('concluida', 'observacao_professor', 'data_conclusao')


# ---------------------------------------------------------------------------
# Permissões
# ---------------------------------------------------------------------------

def _pode_criar_paee(user):
    """Gestão (admin/coordenador/superadmin) ou especialista."""
    return pode_gerenciar(user) or user.nivel in NIVEIS_ESPECIALISTA


def _pode_editar_do_especialista(user, obj):
    """Meta e sessão: gestão edita qualquer uma; especialista só as próprias."""
    return pode_gerenciar(user) or obj.usuario_especialista_id == user.id


# ---------------------------------------------------------------------------
# Respostas comuns
# ---------------------------------------------------------------------------

def _sem_permissao():
    return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)


def _nao_encontrado(mensagem):
    return Response({'error': mensagem}, status=status.HTTP_404_NOT_FOUND)


def _obrigatorio(campo):
    return Response({'error': f'Campo {campo} é obrigatório.'}, status=status.HTTP_400_BAD_REQUEST)


def _aluno_do_body(request):
    """Retorna (aluno, erro) a partir do campo `aluno` do body."""
    aluno_id = request.data.get('aluno')
    if not aluno_id:
        return None, _obrigatorio('aluno')
    aluno = buscar_no_escopo(Aluno, aluno_id)
    if aluno is None:
        return None, _nao_encontrado('Aluno não encontrado.')
    return aluno, None


# ---------------------------------------------------------------------------
# Metas PAEE
# ---------------------------------------------------------------------------

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_metas_paee(request):
    metas = filtrar_por(MetaPAEE.objects.all(), request, 'aluno', Aluno, 'aluno')
    return Response(MetaPAEESerializer(metas.order_by('-criado_em'), many=True).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def criar_meta_paee(request):
    user = request.user
    if not _pode_criar_paee(user):
        return _sem_permissao()

    aluno, erro = _aluno_do_body(request)
    if erro:
        return erro

    serializer = MetaPAEESerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    meta = serializer.save(
        aluno=aluno, usuario_especialista=user, turma_id=aluno.turma_id,
        escola_id=aluno.escola_id, instituicao_id=aluno.instituicao_id,
    )
    return Response(MetaPAEESerializer(meta).data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def detalhe_meta_paee(request, meta_id):
    meta = buscar_no_escopo(MetaPAEE, meta_id)
    if meta is None:
        return _nao_encontrado('Meta PAEE não encontrada.')
    return Response(MetaPAEESerializer(meta).data)


@api_view(['PATCH', 'PUT'])
@permission_classes([IsAuthenticated])
def atualizar_meta_paee(request, meta_id):
    meta = buscar_no_escopo(MetaPAEE, meta_id)
    if meta is None:
        return _nao_encontrado('Meta PAEE não encontrada.')
    if not _pode_editar_do_especialista(request.user, meta):
        return _sem_permissao()

    partial = request.method == 'PATCH'
    serializer = MetaPAEESerializer(meta, data=request.data, partial=partial)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data)


# ---------------------------------------------------------------------------
# Sessões do especialista
# ---------------------------------------------------------------------------

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_sessoes_especialista(request):
    sessoes = filtrar_por(SessaoEspecialista.objects.all(), request, 'aluno', Aluno, 'aluno')
    return Response(SessaoEspecialistaSerializer(sessoes.order_by('-data_atendimento'), many=True).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def criar_sessao_especialista(request):
    user = request.user
    if not _pode_criar_paee(user):
        return _sem_permissao()

    aluno, erro = _aluno_do_body(request)
    if erro:
        return erro

    serializer = SessaoEspecialistaSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    sessao = serializer.save(
        aluno=aluno, usuario_especialista=user, turma_id=aluno.turma_id,
        escola_id=aluno.escola_id, instituicao_id=aluno.instituicao_id,
    )
    return Response(SessaoEspecialistaSerializer(sessao).data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def detalhe_sessao_especialista(request, sessao_id):
    sessao = buscar_no_escopo(SessaoEspecialista, sessao_id)
    if sessao is None:
        return _nao_encontrado('Sessão não encontrada.')
    return Response(SessaoEspecialistaSerializer(sessao).data)


@api_view(['PATCH', 'PUT'])
@permission_classes([IsAuthenticated])
def atualizar_sessao_especialista(request, sessao_id):
    sessao = buscar_no_escopo(SessaoEspecialista, sessao_id)
    if sessao is None:
        return _nao_encontrado('Sessão não encontrada.')
    if not _pode_editar_do_especialista(request.user, sessao):
        return _sem_permissao()

    partial = request.method == 'PATCH'
    serializer = SessaoEspecialistaSerializer(sessao, data=request.data, partial=partial)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data)


# ---------------------------------------------------------------------------
# Vínculo sessão ↔ meta
# ---------------------------------------------------------------------------

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_metas_sessao(request, sessao_id):
    sessao = buscar_no_escopo(SessaoEspecialista, sessao_id)
    if sessao is None:
        return _nao_encontrado('Sessão não encontrada.')

    vinculos = SessaoPAEEMeta.objects.filter(sessao_especialista=sessao).select_related('meta_paee')
    return Response(SessaoPAEEMetaSerializer(vinculos, many=True).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def vincular_meta_sessao(request, sessao_id):
    sessao = buscar_no_escopo(SessaoEspecialista, sessao_id)
    if sessao is None:
        return _nao_encontrado('Sessão não encontrada.')
    if not _pode_editar_do_especialista(request.user, sessao):
        return _sem_permissao()

    meta_id = request.data.get('meta_paee')
    if not meta_id:
        return _obrigatorio('meta_paee')

    meta = buscar_no_escopo(MetaPAEE, meta_id)
    if meta is None:
        return _nao_encontrado('Meta PAEE não encontrada.')

    if meta.aluno_id != sessao.aluno_id:
        return Response({'error': 'A meta precisa ser do mesmo aluno da sessão.'},
                        status=status.HTTP_400_BAD_REQUEST)

    vinculo, criado = SessaoPAEEMeta.objects.get_or_create(sessao_especialista=sessao, meta_paee=meta)
    status_code = status.HTTP_201_CREATED if criado else status.HTTP_200_OK
    return Response(SessaoPAEEMetaSerializer(vinculo).data, status=status_code)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def desvincular_meta_sessao(request, sessao_id, meta_id):
    sessao = buscar_no_escopo(SessaoEspecialista, sessao_id)
    if sessao is None:
        return _nao_encontrado('Sessão não encontrada.')
    if not _pode_editar_do_especialista(request.user, sessao):
        return _sem_permissao()

    try:
        deletados, _ = SessaoPAEEMeta.objects.filter(sessao_especialista=sessao, meta_paee_id=meta_id).delete()
    except (ValidationError, ValueError):  # meta_id malformado
        deletados = 0
    if not deletados:
        return _nao_encontrado('Vínculo não encontrado.')
    return Response(status=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Tarefas PAEE
# ---------------------------------------------------------------------------

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_tarefas_paee(request):
    tarefas = filtrar_por(TarefaPAEE.objects.all(), request, 'meta_paee', MetaPAEE, 'meta_paee')
    return Response(TarefaPAEESerializer(tarefas.order_by('-criado_em'), many=True).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def criar_tarefa_paee(request):
    if not _pode_criar_paee(request.user):
        return _sem_permissao()

    meta_id = request.data.get('meta_paee')
    if not meta_id:
        return _obrigatorio('meta_paee')

    meta = buscar_no_escopo(MetaPAEE, meta_id)
    if meta is None:
        return _nao_encontrado('Meta PAEE não encontrada.')

    serializer = TarefaPAEESerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    tarefa = serializer.save(meta_paee=meta, escola_id=meta.escola_id, instituicao_id=meta.instituicao_id)
    return Response(TarefaPAEESerializer(tarefa).data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def detalhe_tarefa_paee(request, tarefa_id):
    tarefa = buscar_no_escopo(TarefaPAEE, tarefa_id)
    if tarefa is None:
        return _nao_encontrado('Tarefa não encontrada.')
    return Response(TarefaPAEESerializer(tarefa).data)


@api_view(['PATCH', 'PUT'])
@permission_classes([IsAuthenticated])
def atualizar_tarefa_paee(request, tarefa_id):
    """
    Qualquer professor vinculado à turma do aluno da meta pode marcar a
    tarefa como concluída. Edição do resto do conteúdo fica restrita a
    quem gerencia PAEE (admin/coordenador/especialista).
    """
    user = request.user
    tarefa = buscar_no_escopo(TarefaPAEE, tarefa_id)
    if tarefa is None:
        return _nao_encontrado('Tarefa não encontrada.')

    gerencia_paee = _pode_criar_paee(user)
    if not gerencia_paee and not professor_vinculado_turma(user, tarefa.meta_paee.aluno.turma_id):
        return _sem_permissao()

    if gerencia_paee:
        data = request.data
    else:
        data = {k: request.data.get(k) for k in CAMPOS_CONCLUSAO_TAREFA if k in request.data}

    serializer = TarefaPAEESerializer(tarefa, data=data, partial=True)
    serializer.is_valid(raise_exception=True)
    tarefa_atualizada = serializer.save()

    # Olha o valor já validado/salvo, não o do body: em multipart,
    # `concluida` chega como a string "false", que é truthy.
    if (
        not gerencia_paee
        and 'concluida' in data
        and tarefa_atualizada.concluida
        and tarefa_atualizada.professor_conclusao_id is None
    ):
        tarefa_atualizada.professor_conclusao = user
        tarefa_atualizada.save(update_fields=['professor_conclusao'])

    return Response(TarefaPAEESerializer(tarefa_atualizada).data)