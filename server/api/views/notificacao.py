"""Endpoints de Notificacao."""

from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.models import Notificacao, Usuario
from api.serializers import NotificacaoSerializer
from api.tenancy import is_superadmin as _is_superadmin


def _pode_enviar(user):
    return _is_superadmin(user) or user.nivel in ('admin', 'coordenador')


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_minhas_notificacoes(request):
    """Inbox do usuário logado. ?lidas=false pra filtrar só as não lidas."""
    notificacoes = Notificacao.objects.filter(usuario=request.user)
    if request.query_params.get('lidas') == 'false':
        notificacoes = notificacoes.filter(lido_em__isnull=True)
    return Response(NotificacaoSerializer(notificacoes.order_by('-criado_em'), many=True).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def criar_notificacao(request):
    user = request.user
    if not _pode_enviar(user):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    destinatario_id = request.data.get('usuario')
    if not destinatario_id:
        return Response({'error': 'Campo usuario (destinatário) é obrigatório.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        destinatario = Usuario.objects.get(id=destinatario_id)
    except Usuario.DoesNotExist:
        return Response({'error': 'Usuário destinatário não encontrado.'}, status=status.HTTP_404_NOT_FOUND)

    if not _is_superadmin(user) and str(destinatario.instituicao_id) != str(user.instituicao_id):
        return Response({'error': 'Destinatário fora da sua instituição.'}, status=status.HTTP_403_FORBIDDEN)

    serializer = NotificacaoSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    notificacao = serializer.save(
        remetente=user, usuario=destinatario,
        escola_id=destinatario.escola_id, instituicao_id=destinatario.instituicao_id,
    )
    return Response(NotificacaoSerializer(notificacao).data, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def marcar_notificacao_lida(request, notificacao_id):
    try:
        notificacao = Notificacao.objects.get(id=notificacao_id, usuario=request.user)
    except Notificacao.DoesNotExist:
        return Response({'error': 'Notificação não encontrada.'}, status=status.HTTP_404_NOT_FOUND)

    if notificacao.lido_em is None:
        notificacao.lido_em = timezone.now()
        notificacao.save(update_fields=['lido_em', 'atualizado_em'])

    return Response(NotificacaoSerializer(notificacao).data)