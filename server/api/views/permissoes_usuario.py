"""Endpoints de LogAuditoria (só leitura) e PermissaoUsuario."""

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.escopo import buscar_no_escopo, filtrar_por, pode_gerenciar
from api.models import Escola, LogAuditoria, PermissaoUsuario, Usuario
from api.serializers import LogAuditoriaSerializer, PermissaoUsuarioSerializer
from api.tenancy import is_superadmin

_LIMITE_LOGS = 200


def _sem_permissao(mensagem='Sem permissão.'):
    return Response({'error': mensagem}, status=status.HTTP_403_FORBIDDEN)


def _erro(mensagem, codigo=status.HTTP_400_BAD_REQUEST):
    return Response({'error': mensagem}, status=codigo)


# ============================================================
# LogAuditoria (só leitura)
# ============================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_logs_auditoria(request):
    if not pode_gerenciar(request.user):
        return _sem_permissao()

    logs = LogAuditoria.objects.all()
    tabela = request.query_params.get('tabela_afetada')
    if tabela:
        logs = logs.filter(tabela_afetada=tabela)
    return Response(LogAuditoriaSerializer(logs.order_by('-criado_em')[:_LIMITE_LOGS], many=True).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def detalhe_log_auditoria(request, log_id):
    if not pode_gerenciar(request.user):
        return _sem_permissao()

    log = buscar_no_escopo(LogAuditoria, log_id)
    if log is None:
        return _erro('Log não encontrado.', status.HTTP_404_NOT_FOUND)
    return Response(LogAuditoriaSerializer(log).data)


# ============================================================
# PermissaoUsuario (override de permissão por usuário)
# ============================================================

def _escola_do_override(user, alvo, informada):
    """Escola do override. Retorna (escola_id, erro).

    Usuário de escola → a escola dele. Usuário da rede (admin, sem escola) →
    a `escola` do body, que precisa ser da mesma instituição do alvo.
    """
    if alvo.escola_id:
        return alvo.escola_id, None
    if user.nivel == 'coordenador':
        return user.escola_id, None
    if not informada:
        return None, _erro('Campo escola é obrigatório para usuário sem escola.')
    escola = buscar_no_escopo(Escola, informada)
    if escola is None or escola.instituicao_id != alvo.instituicao_id:
        return None, _erro('A escola informada não pertence à instituição do usuário.')
    return escola.id, None


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_permissoes_usuario(request):
    if not pode_gerenciar(request.user):
        return _sem_permissao()

    permissoes = filtrar_por(PermissaoUsuario.objects.all(), request, 'usuario', Usuario, 'usuario')
    return Response(PermissaoUsuarioSerializer(permissoes, many=True).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def criar_permissao_usuario(request):
    user = request.user
    if not pode_gerenciar(user):
        return _sem_permissao()

    usuario_id = request.data.get('usuario')
    if not usuario_id:
        return _erro('Campo usuario é obrigatório.')

    alvo = buscar_no_escopo(Usuario, usuario_id)
    if alvo is None:
        return _erro('Usuário não encontrado.', status.HTTP_404_NOT_FOUND)

    # Conceder permissão a si mesmo seria auto-promoção.
    if alvo.id == user.id and not is_superadmin(user):
        return _sem_permissao('Você não pode alterar as próprias permissões.')

    if not is_superadmin(user) and alvo.instituicao_id != user.instituicao_id:
        return _sem_permissao('Usuário fora da sua instituição.')
    if alvo.instituicao_id is None:
        return _erro('Usuário sem instituição vinculada.')

    escola_id, erro = _escola_do_override(user, alvo, request.data.get('escola'))
    if erro:
        return erro

    serializer = PermissaoUsuarioSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    # UniqueConstraint(usuario, modulo, escola, acao): o serializer não a
    # valida (escola é read-only) — sem isto, duplicado vira 500.
    duplicado = PermissaoUsuario._base_manager.filter(
        usuario=alvo, escola_id=escola_id,
        modulo=serializer.validated_data.get('modulo'), acao=serializer.validated_data.get('acao'),
    ).exists()
    if duplicado:
        return _erro('Já existe um override para este usuário, módulo e ação nesta escola.')

    permissao = serializer.save(
        usuario=alvo, concedido_por=user, escola_id=escola_id, instituicao_id=alvo.instituicao_id,
    )
    return Response(PermissaoUsuarioSerializer(permissao).data, status=status.HTTP_201_CREATED)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def deletar_permissao_usuario(request, permissao_id):
    user = request.user
    if not pode_gerenciar(user):
        return _sem_permissao()

    permissao = buscar_no_escopo(PermissaoUsuario, permissao_id)
    if permissao is None:
        return _erro('Permissão não encontrada.', status.HTTP_404_NOT_FOUND)

    if permissao.usuario_id == user.id and not is_superadmin(user):
        return _sem_permissao('Você não pode alterar as próprias permissões.')

    permissao.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)