import os
import requests
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.conf import settings

from api.models import Usuario


def solicitar_recuperacao(email: str) -> None:
    """
    Gera token e envia e-mail de recuperação.
    Não levanta exceção se o e-mail não existir (evita enumeração).
    """
    try:
        usuario = Usuario.objects.get(email=email, ativo=True)
    except Usuario.DoesNotExist:
        return  # silencioso por segurança

    uid = urlsafe_base64_encode(force_bytes(usuario.pk))
    token = default_token_generator.make_token(usuario)

    frontend_url = os.getenv('FRONTEND_URL', 'http://localhost:5173')
    mailtrap_token = os.getenv('MAILTRAP_API_TOKEN', '')
    default_from_email = os.getenv('DEFAULT_FROM_EMAIL', 'hello@edunuvem.com')
    reset_link = f"{frontend_url}/redefinir-senha?uid={uid}&token={token}"

    print(f"E-mail enviado para {email}! Link: {reset_link}")

    try:
        response = requests.post(
            'https://send.api.mailtrap.io/api/send',
            headers={
                'Authorization': f'Bearer {mailtrap_token}',
                'Content-Type': 'application/json',
            },
            json={
                'from': {'email': default_from_email, 'name': 'Nara - Recuperação de senha'},
                'to': [{'email': email}],
                'subject': 'Redefinição de senha – NARA',
                'html': (
                    f'<p>Olá, {usuario.nome}!</p>'
                    f'<p>Clique no link para redefinir sua senha:</p>'
                    f'<p><a href="{reset_link}">{reset_link}</a></p>'
                    f'<p>Este link expira em 1 hora.</p>'
                ),
                'category': 'Password Reset',
            },
        )
        response.raise_for_status()
        print("E-mail enviado com sucesso!")
    except requests.HTTPError as e:
        print(f"Falha ao enviar e-mail: {e.response.status_code} {e.response.text}")
    except Exception as e:
        print(f"Falha ao enviar e-mail: {e}")


def confirmar_nova_senha(uid: str, token: str, nova_senha: str) -> None:
    """
    Valida o token e salva a nova senha.
    Levanta ValueError em caso de link inválido/expirado.
    """
    try:
        pk = force_str(urlsafe_base64_decode(uid))
        usuario = Usuario.objects.get(pk=pk)
    except (TypeError, ValueError, Usuario.DoesNotExist):
        raise ValueError('Link inválido')

    if not default_token_generator.check_token(usuario, token):
        raise ValueError('Link inválido ou expirado')

    usuario.set_password(nova_senha)
    usuario.save()


def alterar_senha_logado(usuario, senha_atual: str, nova_senha: str) -> None:
    """
    Troca a senha do usuário autenticado após validar a senha atual.
    Levanta ValueError com mensagem amigável em caso de falha.
    """
    if not usuario.check_password(senha_atual):
        raise ValueError('Senha atual incorreta')

    if senha_atual == nova_senha:
        raise ValueError('A nova senha deve ser diferente da senha atual')

    if len(nova_senha) < 8:
        raise ValueError('A senha deve ter pelo menos 8 caracteres')

    try:
        validate_password(nova_senha, user=usuario)
    except ValidationError as exc:
        raise ValueError(' '.join(exc.messages)) from exc

    usuario.set_password(nova_senha)
    usuario.save(update_fields=['password'])