"""Logout por blacklist do refresh token (POST /api/auth/logout/)."""
from rest_framework_simplejwt.tokens import RefreshToken

from .base import CenarioMultiTenant

URL_LOGOUT = '/api/auth/logout/'
URL_REFRESH = '/api/auth/refresh/'


class LogoutTests(CenarioMultiTenant):

    def _refresh(self):
        return str(RefreshToken.for_user(self.prof_a1))

    def test_refresh_nao_serve_mais_depois_do_logout(self):
        refresh = self._refresh()

        r = self.client.post(URL_LOGOUT, {'refresh': refresh}, format='json')
        self.assertEqual(r.status_code, 200, r.content)

        r = self.client.post(URL_REFRESH, {'refresh': refresh}, format='json')
        self.assertEqual(r.status_code, 401, r.content)

    def test_logout_funciona_com_access_token_vencido_no_header(self):
        """O front pode mandar um Bearer expirado; o logout não pode responder 401."""
        self.client.credentials(HTTP_AUTHORIZATION='Bearer token.invalido.qualquer')
        r = self.client.post(URL_LOGOUT, {'refresh': self._refresh()}, format='json')
        self.assertEqual(r.status_code, 200, r.content)

    def test_logout_eh_idempotente(self):
        refresh = self._refresh()
        self.assertEqual(self.client.post(URL_LOGOUT, {'refresh': refresh}, format='json').status_code, 200)
        self.assertEqual(self.client.post(URL_LOGOUT, {'refresh': refresh}, format='json').status_code, 200)

    def test_token_malformado_responde_200_sem_erro(self):
        r = self.client.post(URL_LOGOUT, {'refresh': 'nao-e-um-jwt'}, format='json')
        self.assertEqual(r.status_code, 200, r.content)

    def test_sem_refresh_responde_400(self):
        r = self.client.post(URL_LOGOUT, {}, format='json')
        self.assertEqual(r.status_code, 400, r.content)

    def test_logout_nao_afeta_outras_sessoes_do_usuario(self):
        """Sair num aparelho não derruba o outro (cada login tem seu refresh)."""
        celular, notebook = self._refresh(), self._refresh()
        self.client.post(URL_LOGOUT, {'refresh': celular}, format='json')

        r = self.client.post(URL_REFRESH, {'refresh': notebook}, format='json')
        self.assertEqual(r.status_code, 200, r.content)