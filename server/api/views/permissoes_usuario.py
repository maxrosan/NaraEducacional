"""Endpoints de LogAuditoria (só leitura) e PermissaoUsuario."""

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.models import LogAuditoria, PermissaoUsuario, Usuario
from api.serializers import LogAuditoriaSerializer, PermissaoUsuarioSerializer
from api.tenancy import is_superadmin as _is_superadmin


def _pode_gerenciar(user):
    return _is_superadmin(user) or user.nivel in ('admin', 'coordenador')


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_logs_auditoria(request):
    if not _pode_gerenciar(request.user):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    logs = LogAuditoria.objects.all()
    tabela = request.query_params.get('tabela_afetada')
    if tabela:
        logs = logs.filter(tabela_afetada=tabela)
    return Response(LogAuditoriaSerializer(logs.order_by('-criado_em')[:200], many=True).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def detalhe_log_auditoria(request, log_id):
    if not _pode_gerenciar(request.user):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    try:
        log = LogAuditoria.objects.get(id=log_id)
    except LogAuditoria.DoesNotExist:
        return Response({'error': 'Log não encontrado.'}, status=status.HTTP_404_NOT_FOUND)
    return Response(LogAuditoriaSerializer(log).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_permissoes_usuario(request):
    if not _pode_gerenciar(request.user):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    permissoes = PermissaoUsuario.objects.all()
    usuario_id = request.query_params.get('usuario')
    if usuario_id:
        permissoes = permissoes.filter(usuario_id=usuario_id)
    return Response(PermissaoUsuarioSerializer(permissoes, many=True).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def criar_permissao_usuario(request):
    user = request.user
    if not _pode_gerenciar(user):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    usuario_id = request.data.get('usuario')
    if not usuario_id:
        return Response({'error': 'Campo usuario é obrigatório.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        alvo = Usuario.objects.get(id=usuario_id)
    except Usuario.DoesNotExist:
        return Response({'error': 'Usuário não encontrado.'}, status=status.HTTP_404_NOT_FOUND)

    if not _is_superadmin(user) and str(alvo.instituicao_id) != str(user.instituicao_id):
        return Response({'error': 'Usuário fora da sua instituição.'}, status=status.HTTP_403_FORBIDDEN)

    escola_id = alvo.escola_id or (user.escola_id if user.nivel == 'coordenador' else request.data.get('escola'))
    if not escola_id:
        return Response({'error': 'Não foi possível determinar a escola do override.'},
                         status=status.HTTP_400_BAD_REQUEST)

    serializer = PermissaoUsuarioSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    permissao = serializer.save(
        usuario=alvo, concedido_por=user, escola_id=escola_id, instituicao_id=alvo.instituicao_id,
    )
    return Response(PermissaoUsuarioSerializer(permissao).data, status=status.HTTP_201_CREATED)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def deletar_permissao_usuario(request, permissao_id):
    if not _pode_gerenciar(request.user):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    try:
        permissao = PermissaoUsuario.objects.get(id=permissao_id)
    except PermissaoUsuario.DoesNotExist:
        return Response({'error': 'Permissão não encontrada.'}, status=status.HTTP_404_NOT_FOUND)

    permissao.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)