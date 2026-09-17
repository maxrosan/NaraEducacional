"""Endpoints de autenticação."""

import logging

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView

from api.services.password_reset import (
    alterar_senha_logado,
    solicitar_recuperacao,
    confirmar_nova_senha,
)
from api.serializers import LoginSerializer, UsuarioSerializer

logger = logging.getLogger(__name__)


class LoginView(TokenObtainPairView):
    """Login: devolve access/refresh token + dados do usuário logado."""
    serializer_class = LoginSerializer


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def me(request):
    """Retorna os dados do usuário autenticado (nivel, escola, instituicao, etc.)."""
    return Response(UsuarioSerializer(request.user).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def alterar_senha(request):
    """Altera a senha do usuário logado (requer senha atual)."""
    senha_atual = request.data.get('senha_atual', '')
    nova_senha = request.data.get('nova_senha', '')
    confirmar_senha_campo = request.data.get('confirmar_senha', '')

    if not senha_atual or not nova_senha:
        return Response(
            {'error': 'Senha atual e nova senha são obrigatórias'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if confirmar_senha_campo and nova_senha != confirmar_senha_campo:
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


@api_view(['POST'])
@permission_classes([AllowAny])
def recuperar_senha(request):
    """Solicita o e-mail de recuperação de senha. Sempre responde 200 (evita enumeração de e-mails)."""
    email = request.data.get('email', '')
    if not email:
        return Response({'error': 'Email é obrigatório'}, status=status.HTTP_400_BAD_REQUEST)

    solicitar_recuperacao(email)
    return Response({'message': 'Se o e-mail existir, um link de recuperação foi enviado.'})


@api_view(['POST'])
@permission_classes([AllowAny])
def confirmar_senha(request):
    """Confirma o token de recuperação e define a nova senha."""
    uid = request.data.get('uid', '')
    token = request.data.get('token', '')
    nova_senha = request.data.get('nova_senha', '')

    if not uid or not token or not nova_senha:
        return Response(
            {'error': 'uid, token e nova_senha são obrigatórios'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        confirmar_nova_senha(uid, token, nova_senha)
        return Response({'message': 'Senha redefinida com sucesso!'})
    except ValueError as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)