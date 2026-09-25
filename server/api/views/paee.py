"""Endpoints de MetaPAEE, SessaoEspecialista, SessaoPAEEMeta e TarefaPAEE."""

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.models import MetaPAEE, SessaoEspecialista, SessaoPAEEMeta, TarefaPAEE, Aluno, UsuarioTurma
from api.serializers import (
    MetaPAEESerializer, SessaoEspecialistaSerializer, SessaoPAEEMetaSerializer, TarefaPAEESerializer,
)
from api.tenancy import is_superadmin as _is_superadmin

NIVEIS_ESPECIALISTA = ('especialista', 'professor_especialista')


def _pode_gerenciar_geral(user):
    return _is_superadmin(user) or user.nivel in ('admin', 'coordenador')


def _pode_criar_paee(user):
    return _pode_gerenciar_geral(user) or user.nivel in NIVEIS_ESPECIALISTA


def _professor_vinculado_turma(usuario, turma):
    return UsuarioTurma.objects.filter(usuario=usuario, turma=turma).exists()


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_metas_paee(request):
    metas = MetaPAEE.objects.all()
    aluno_id = request.query_params.get('aluno')
    if aluno_id:
        metas = metas.filter(aluno_id=aluno_id)
    return Response(MetaPAEESerializer(metas.order_by('-criado_em'), many=True).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def criar_meta_paee(request):
    user = request.user
    if not _pode_criar_paee(user):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    aluno_id = request.data.get('aluno')
    if not aluno_id:
        return Response({'error': 'Campo aluno é obrigatório.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        aluno = Aluno.objects.get(id=aluno_id)
    except Aluno.DoesNotExist:
        return Response({'error': 'Aluno não encontrado.'}, status=status.HTTP_404_NOT_FOUND)

    serializer = MetaPAEESerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    meta = serializer.save(
        aluno=aluno, usuario_especialista=user, escola_id=aluno.escola_id, instituicao_id=aluno.instituicao_id,
    )
    return Response(MetaPAEESerializer(meta).data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def detalhe_meta_paee(request, meta_id):
    try:
        meta = MetaPAEE.objects.get(id=meta_id)
    except MetaPAEE.DoesNotExist:
        return Response({'error': 'Meta PAEE não encontrada.'}, status=status.HTTP_404_NOT_FOUND)
    return Response(MetaPAEESerializer(meta).data)


def _pode_editar_meta(user, meta):
    if _pode_gerenciar_geral(user):
        return True
    return meta.usuario_especialista_id == user.id


@api_view(['PATCH', 'PUT'])
@permission_classes([IsAuthenticated])
def atualizar_meta_paee(request, meta_id):
    try:
        meta = MetaPAEE.objects.get(id=meta_id)
    except MetaPAEE.DoesNotExist:
        return Response({'error': 'Meta PAEE não encontrada.'}, status=status.HTTP_404_NOT_FOUND)
    if not _pode_editar_meta(request.user, meta):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    partial = request.method == 'PATCH'
    serializer = MetaPAEESerializer(meta, data=request.data, partial=partial)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_sessoes_especialista(request):
    sessoes = SessaoEspecialista.objects.all()
    aluno_id = request.query_params.get('aluno')
    if aluno_id:
        sessoes = sessoes.filter(aluno_id=aluno_id)
    return Response(SessaoEspecialistaSerializer(sessoes.order_by('-data_atendimento'), many=True).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def criar_sessao_especialista(request):
    user = request.user
    if not _pode_criar_paee(user):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    aluno_id = request.data.get('aluno')
    if not aluno_id:
        return Response({'error': 'Campo aluno é obrigatório.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        aluno = Aluno.objects.get(id=aluno_id)
    except Aluno.DoesNotExist:
        return Response({'error': 'Aluno não encontrado.'}, status=status.HTTP_404_NOT_FOUND)

    serializer = SessaoEspecialistaSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    sessao = serializer.save(
        aluno=aluno, usuario_especialista=user, escola_id=aluno.escola_id, instituicao_id=aluno.instituicao_id,
    )
    return Response(SessaoEspecialistaSerializer(sessao).data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def detalhe_sessao_especialista(request, sessao_id):
    try:
        sessao = SessaoEspecialista.objects.get(id=sessao_id)
    except SessaoEspecialista.DoesNotExist:
        return Response({'error': 'Sessão não encontrada.'}, status=status.HTTP_404_NOT_FOUND)
    return Response(SessaoEspecialistaSerializer(sessao).data)


def _pode_editar_sessao(user, sessao):
    if _pode_gerenciar_geral(user):
        return True
    return sessao.usuario_especialista_id == user.id


@api_view(['PATCH', 'PUT'])
@permission_classes([IsAuthenticated])
def atualizar_sessao_especialista(request, sessao_id):
    try:
        sessao = SessaoEspecialista.objects.get(id=sessao_id)
    except SessaoEspecialista.DoesNotExist:
        return Response({'error': 'Sessão não encontrada.'}, status=status.HTTP_404_NOT_FOUND)
    if not _pode_editar_sessao(request.user, sessao):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    partial = request.method == 'PATCH'
    serializer = SessaoEspecialistaSerializer(sessao, data=request.data, partial=partial)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_metas_sessao(request, sessao_id):
    try:
        sessao = SessaoEspecialista.objects.get(id=sessao_id)
    except SessaoEspecialista.DoesNotExist:
        return Response({'error': 'Sessão não encontrada.'}, status=status.HTTP_404_NOT_FOUND)

    vinculos = SessaoPAEEMeta.objects.filter(sessao_especialista=sessao).select_related('meta_paee')
    return Response(SessaoPAEEMetaSerializer(vinculos, many=True).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def vincular_meta_sessao(request, sessao_id):
    try:
        sessao = SessaoEspecialista.objects.get(id=sessao_id)
    except SessaoEspecialista.DoesNotExist:
        return Response({'error': 'Sessão não encontrada.'}, status=status.HTTP_404_NOT_FOUND)

    if not _pode_editar_sessao(request.user, sessao):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    meta_id = request.data.get('meta_paee')
    if not meta_id:
        return Response({'error': 'Campo meta_paee é obrigatório.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        meta = MetaPAEE.objects.get(id=meta_id)
    except MetaPAEE.DoesNotExist:
        return Response({'error': 'Meta PAEE não encontrada.'}, status=status.HTTP_404_NOT_FOUND)

    if str(meta.aluno_id) != str(sessao.aluno_id):
        return Response({'error': 'A meta precisa ser do mesmo aluno da sessão.'},
                         status=status.HTTP_400_BAD_REQUEST)

    vinculo, criado = SessaoPAEEMeta.objects.get_or_create(sessao_especialista=sessao, meta_paee=meta)
    status_code = status.HTTP_201_CREATED if criado else status.HTTP_200_OK
    return Response(SessaoPAEEMetaSerializer(vinculo).data, status=status_code)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def desvincular_meta_sessao(request, sessao_id, meta_id):
    try:
        sessao = SessaoEspecialista.objects.get(id=sessao_id)
    except SessaoEspecialista.DoesNotExist:
        return Response({'error': 'Sessão não encontrada.'}, status=status.HTTP_404_NOT_FOUND)

    if not _pode_editar_sessao(request.user, sessao):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    deletados, _ = SessaoPAEEMeta.objects.filter(sessao_especialista=sessao, meta_paee_id=meta_id).delete()
    if not deletados:
        return Response({'error': 'Vínculo não encontrado.'}, status=status.HTTP_404_NOT_FOUND)
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_tarefas_paee(request):
    tarefas = TarefaPAEE.objects.all()
    meta_id = request.query_params.get('meta_paee')
    if meta_id:
        tarefas = tarefas.filter(meta_paee_id=meta_id)
    return Response(TarefaPAEESerializer(tarefas.order_by('-criado_em'), many=True).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def criar_tarefa_paee(request):
    user = request.user
    if not _pode_criar_paee(user):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    meta_id = request.data.get('meta_paee')
    if not meta_id:
        return Response({'error': 'Campo meta_paee é obrigatório.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        meta = MetaPAEE.objects.get(id=meta_id)
    except MetaPAEE.DoesNotExist:
        return Response({'error': 'Meta PAEE não encontrada.'}, status=status.HTTP_404_NOT_FOUND)

    serializer = TarefaPAEESerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    tarefa = serializer.save(meta_paee=meta, escola_id=meta.escola_id, instituicao_id=meta.instituicao_id)
    return Response(TarefaPAEESerializer(tarefa).data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def detalhe_tarefa_paee(request, tarefa_id):
    try:
        tarefa = TarefaPAEE.objects.get(id=tarefa_id)
    except TarefaPAEE.DoesNotExist:
        return Response({'error': 'Tarefa não encontrada.'}, status=status.HTTP_404_NOT_FOUND)
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
    try:
        tarefa = TarefaPAEE.objects.get(id=tarefa_id)
    except TarefaPAEE.DoesNotExist:
        return Response({'error': 'Tarefa não encontrada.'}, status=status.HTTP_404_NOT_FOUND)

    aluno = tarefa.meta_paee.aluno
    pode_gerenciar = _pode_criar_paee(user)
    pode_concluir = pode_gerenciar or _professor_vinculado_turma(user, aluno.turma)

    if not pode_concluir:
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    data = dict(request.data)
    if not pode_gerenciar:
        data = {k: v for k, v in data.items() if k in ('concluida', 'observacao_professor', 'data_conclusao')}

    serializer = TarefaPAEESerializer(tarefa, data=data, partial=True)
    serializer.is_valid(raise_exception=True)
    tarefa_atualizada = serializer.save()

    if not pode_gerenciar and data.get('concluida') and tarefa_atualizada.professor_conclusao_id is None:
        tarefa_atualizada.professor_conclusao = user
        tarefa_atualizada.save(update_fields=['professor_conclusao'])

    return Response(TarefaPAEESerializer(tarefa_atualizada).data)