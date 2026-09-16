"""Endpoints de autenticação fora do legado."""

import logging

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.services.password_reset import alterar_senha_logado

logger = logging.getLogger(__name__)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def alterar_senha(request):
    """Altera a senha do usuário logado (requer senha atual)."""
    senha_atual = request.data.get('senha_atual', '')
    nova_senha = request.data.get('nova_senha', '')
    confirmar_senha = request.data.get('confirmar_senha', '')

    if not senha_atual or not nova_senha:
        return Response(
            {'error': 'Senha atual e nova senha são obrigatórias'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if confirmar_senha and nova_senha != confirmar_senha:
        return Response(
            {'error': 'A confirmação não coincide com a nova senha'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        alterar_senha_logado(request.user, senha_atual, nova_senha)
        logger.info('Senha alterada com sucesso: %s', request.user.email)
        return Response({'message': 'Senha alterada com sucesso!'})
    except ValueError as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
