"""Endpoints de Notificacao."""

from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.escopo import buscar_no_escopo, pode_gerenciar
from api.models import Notificacao, Usuario
from api.serializers import NotificacaoSerializer
from api.tenancy import is_superadmin


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
    """Gestão envia para usuários do próprio escopo (o TenantManager já limita
    a busca do destinatário: coordenador → escola, admin → rede)."""
    user = request.user
    if not pode_gerenciar(user):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    destinatario_id = request.data.get('usuario')
    if not destinatario_id:
        return Response({'error': 'Campo usuario (destinatário) é obrigatório.'}, status=status.HTTP_400_BAD_REQUEST)

    destinatario = buscar_no_escopo(Usuario, destinatario_id)
    if destinatario is None:
        return Response({'error': 'Usuário destinatário não encontrado.'}, status=status.HTTP_404_NOT_FOUND)

    if not is_superadmin(user) and destinatario.instituicao_id != user.instituicao_id:
        return Response({'error': 'Destinatário fora da sua instituição.'}, status=status.HTTP_403_FORBIDDEN)

    # Notificacao.instituicao é obrigatória: usuários de sistema (suporte,
    # vendedor, superadmin) não têm instituição e não recebem notificação aqui.
    if destinatario.instituicao_id is None:
        return Response({'error': 'Destinatário sem instituição vinculada.'}, status=status.HTTP_400_BAD_REQUEST)

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
    notificacao = buscar_no_escopo(Notificacao, notificacao_id)
    if notificacao is None or notificacao.usuario_id != request.user.id:
        return Response({'error': 'Notificação não encontrada.'}, status=status.HTTP_404_NOT_FOUND)

    if notificacao.lido_em is None:
        notificacao.lido_em = timezone.now()
        notificacao.save(update_fields=['lido_em', 'atualizado_em'])

    return Response(NotificacaoSerializer(notificacao).data)