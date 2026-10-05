"""Recuperação e troca de senha.

Segurança:
  * O link de redefinição carrega um token válido: NUNCA vai para log/stdout.
    Quem lê os logs do container conseguiria assumir a conta.
  * `solicitar_recuperacao` não revela se o e-mail existe (evita enumeração).
  * A validade do link vem de `settings.PASSWORD_RESET_TIMEOUT` — o texto do
    e-mail é derivado dela, para não prometer um prazo que não é o real.
"""

import logging

import requests
from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError
from django.utils.encoding import force_bytes, force_str
from django.utils.html import escape
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

from api.models import Usuario

logger = logging.getLogger(__name__)

MAILTRAP_SEND_URL = 'https://send.api.mailtrap.io/api/send'
MAILTRAP_TIMEOUT_SECONDS = 10
SENHA_MIN_CARACTERES = 8


def _descrever_validade(segundos: int) -> str:
    """3600 -> '1 hora'; 7200 -> '2 horas'; 1800 -> '30 minutos'."""
    horas, resto = divmod(int(segundos), 3600)
    if horas and not resto:
        return f"{horas} hora{'s' if horas > 1 else ''}"
    minutos = int(segundos) // 60
    return f"{minutos} minuto{'s' if minutos != 1 else ''}"


def _validar_nova_senha(usuario, nova_senha: str) -> None:
    """Regras comuns à troca (logado) e à redefinição (por link).

    A checagem de tamanho é feita à mão antes dos validadores do Django só
    para ter a mensagem em português (LANGUAGE_CODE está em en-us).
    """
    if len(nova_senha) < SENHA_MIN_CARACTERES:
        raise ValueError(f'A senha deve ter pelo menos {SENHA_MIN_CARACTERES} caracteres')
    try:
        validate_password(nova_senha, user=usuario)
    except ValidationError as exc:
        raise ValueError(' '.join(exc.messages)) from exc


def solicitar_recuperacao(email: str) -> None:
    """Gera o token e envia o e-mail de recuperação.

    Não levanta exceção se o e-mail não existir nem se o envio falhar: a
    resposta para o cliente é sempre a mesma (evita enumeração de contas).
    """
    try:
        usuario = Usuario.objects.get(email=email, is_active=True)
    except Usuario.DoesNotExist:
        return

    if not settings.MAILTRAP_API_TOKEN:
        logger.error('MAILTRAP_API_TOKEN não configurado; e-mail de recuperação não enviado.',
                     extra={'usuario_id': str(usuario.pk)})
        return

    uid = urlsafe_base64_encode(force_bytes(usuario.pk))
    token = default_token_generator.make_token(usuario)
    reset_link = f"{settings.FRONTEND_URL}/redefinir-senha?uid={uid}&token={token}"
    validade = _descrever_validade(settings.PASSWORD_RESET_TIMEOUT)

    try:
        response = requests.post(
            MAILTRAP_SEND_URL,
            headers={
                'Authorization': f'Bearer {settings.MAILTRAP_API_TOKEN}',
                'Content-Type': 'application/json',
            },
            json={
                'from': {'email': settings.DEFAULT_FROM_EMAIL, 'name': 'Nara - Recuperação de senha'},
                'to': [{'email': email}],
                'subject': 'Redefinição de senha – NARA',
                'html': (
                    f'<p>Olá, {escape(usuario.nome)}!</p>'
                    f'<p>Clique no link para redefinir sua senha:</p>'
                    f'<p><a href="{reset_link}">{reset_link}</a></p>'
                    f'<p>Este link expira em {validade}.</p>'
                ),
                'category': 'Password Reset',
            },
            timeout=MAILTRAP_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        logger.info('E-mail de recuperação enviado.', extra={'usuario_id': str(usuario.pk)})
    except requests.HTTPError as exc:
        # O corpo da resposta do Mailtrap não contém o link, só a mensagem de erro.
        logger.error('Mailtrap recusou o e-mail de recuperação: %s %s',
                     exc.response.status_code, exc.response.text[:500],
                     extra={'usuario_id': str(usuario.pk)})
    except requests.RequestException:
        logger.exception('Falha de rede ao enviar e-mail de recuperação.',
                         extra={'usuario_id': str(usuario.pk)})


def confirmar_nova_senha(uid: str, token: str, nova_senha: str) -> None:
    """Valida o token e salva a nova senha.

    Levanta ValueError em caso de link inválido/expirado ou senha fraca.
    """
    try:
        pk = force_str(urlsafe_base64_decode(uid))
        usuario = Usuario.objects.get(pk=pk, is_active=True)
    except (TypeError, ValueError, Usuario.DoesNotExist, ValidationError):
        raise ValueError('Link inválido')

    if not default_token_generator.check_token(usuario, token):
        raise ValueError('Link inválido ou expirado')

    _validar_nova_senha(usuario, nova_senha)

    usuario.set_password(nova_senha)
    usuario.save(update_fields=['password'])


def alterar_senha_logado(usuario, senha_atual: str, nova_senha: str) -> None:
    """Troca a senha do usuário autenticado após validar a senha atual.

    Levanta ValueError com mensagem amigável em caso de falha.
    """
    if not usuario.check_password(senha_atual):
        raise ValueError('Senha atual incorreta')

    if senha_atual == nova_senha:
        raise ValueError('A nova senha deve ser diferente da senha atual')

    _validar_nova_senha(usuario, nova_senha)

    usuario.set_password(nova_senha)
    usuario.save(update_fields=['password'])