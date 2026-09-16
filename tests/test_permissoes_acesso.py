"""
Testes de permissões de acesso por perfil de usuário.

Verifica que cada perfil só acessa as páginas que lhe são permitidas:
  • professor       → apenas /home-professor e rotas de professor
  • coordenador     → /coordenacao; NÃO acessa /admin
  • admin           → /admin e /coordenacao

Pré-requisitos:
  1. Frontend rodando em http://localhost:5173 (ou NARA_BASE_URL)
  2. Backend rodando em http://localhost:8001
  3. Usuários de teste criados no banco:
       - professor@nara.dev  (perfil=professor)
       - coordenador@nara.dev (perfil=coordenador)
       - admin@nara.dev      (perfil=admin)
     Ajuste as credenciais em tests/.env se necessário.
  4. Executar:
       pytest tests/test_permissoes_acesso.py -v
"""

import pytest
from playwright.sync_api import Page, expect

from conftest import BASE_URL


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def esta_na_pagina_de_login(page: Page) -> bool:
    """Retorna True se a URL atual é a página de login."""
    return page.url.rstrip("/") in (
        f"{BASE_URL}",
        f"{BASE_URL}/",
        f"{BASE_URL}/login",
    )


def acessa_url_e_aguarda(page: Page, path: str) -> None:
    page.goto(f"{BASE_URL}{path}")
    page.wait_for_load_state("networkidle")


# ---------------------------------------------------------------------------
# Professor — deve acessar apenas rotas de professor
# ---------------------------------------------------------------------------

class TestProfessorAcesso:
    """Professor só deve ver suas próprias páginas."""

    def test_professor_redireciona_para_home_professor_apos_login(self, professor_page: Page):
        """Após login, professor vai para /home-professor."""
        assert "/home-professor" in professor_page.url or "/registro" in professor_page.url, (
            f"Professor redirecionado para URL inesperada: {professor_page.url}"
        )

    def test_professor_nao_acessa_admin(self, professor_page: Page):
        """Professor não pode acessar /admin — deve ser redirecionado."""
        acessa_url_e_aguarda(professor_page, "/admin")

        assert esta_na_pagina_de_login(professor_page) or "/admin" not in professor_page.url, (
            f"Professor acessou /admin indevidamente. URL atual: {professor_page.url}"
        )

    def test_professor_nao_acessa_admin_usuarios(self, professor_page: Page):
        """Professor não pode acessar /admin/usuarios."""
        acessa_url_e_aguarda(professor_page, "/admin/usuarios")

        assert esta_na_pagina_de_login(professor_page) or "/admin" not in professor_page.url, (
            f"Professor acessou /admin/usuarios indevidamente. URL atual: {professor_page.url}"
        )

    def test_professor_nao_acessa_coordenacao(self, professor_page: Page):
        """Professor não pode acessar /coordenacao."""
        acessa_url_e_aguarda(professor_page, "/coordenacao")

        assert esta_na_pagina_de_login(professor_page) or "/coordenacao" not in professor_page.url, (
            f"Professor acessou /coordenacao indevidamente. URL atual: {professor_page.url}"
        )

    def test_professor_acessa_home_professor(self, professor_page: Page):
        """Professor consegue acessar sua própria home."""
        acessa_url_e_aguarda(professor_page, "/home-professor")
        assert "/home-professor" in professor_page.url, (
            f"Professor não conseguiu acessar /home-professor. URL atual: {professor_page.url}"
        )


# ---------------------------------------------------------------------------
# Coordenador — acessa /coordenacao mas NÃO /admin
# ---------------------------------------------------------------------------

class TestCoordenadorAcesso:
    """Coordenador acessa coordenação mas não o painel de admin."""

    def test_coordenador_redireciona_para_coordenacao_apos_login(self, coordenador_page: Page):
        """Após login, coordenador vai para /coordenacao."""
        assert "/coordenacao" in coordenador_page.url, (
            f"Coordenador redirecionado para URL inesperada: {coordenador_page.url}"
        )

    def test_coordenador_acessa_coordenacao(self, coordenador_page: Page):
        """Coordenador consegue acessar /coordenacao."""
        acessa_url_e_aguarda(coordenador_page, "/coordenacao")
        assert "/coordenacao" in coordenador_page.url, (
            f"Coordenador não conseguiu acessar /coordenacao. URL atual: {coordenador_page.url}"
        )

    def test_coordenador_nao_acessa_admin(self, coordenador_page: Page):
        """Coordenador não pode acessar /admin."""
        acessa_url_e_aguarda(coordenador_page, "/admin")

        assert esta_na_pagina_de_login(coordenador_page) or "/admin" not in coordenador_page.url, (
            f"Coordenador acessou /admin indevidamente. URL atual: {coordenador_page.url}"
        )

    def test_coordenador_nao_acessa_admin_usuarios(self, coordenador_page: Page):
        """Coordenador não pode acessar /admin/usuarios."""
        acessa_url_e_aguarda(coordenador_page, "/admin/usuarios")

        assert esta_na_pagina_de_login(coordenador_page) or "/admin" not in coordenador_page.url, (
            f"Coordenador acessou /admin/usuarios indevidamente. URL atual: {coordenador_page.url}"
        )


# ---------------------------------------------------------------------------
# Admin — acessa tudo
# ---------------------------------------------------------------------------

class TestAdminAcesso:
    """Admin deve acessar tanto /admin quanto /coordenacao."""

    def test_admin_redireciona_para_admin_apos_login(self, admin_page: Page):
        """Após login, admin vai para /admin."""
        assert "/admin" in admin_page.url, (
            f"Admin redirecionado para URL inesperada: {admin_page.url}"
        )

    def test_admin_acessa_painel_admin(self, admin_page: Page):
        """Admin consegue acessar /admin."""
        acessa_url_e_aguarda(admin_page, "/admin")
        assert "/admin" in admin_page.url, (
            f"Admin não conseguiu acessar /admin. URL atual: {admin_page.url}"
        )

    def test_admin_acessa_usuarios(self, admin_page: Page):
        """Admin consegue acessar /admin/usuarios."""
        acessa_url_e_aguarda(admin_page, "/admin/usuarios")
        assert "/admin" in admin_page.url, (
            f"Admin não conseguiu acessar /admin/usuarios. URL atual: {admin_page.url}"
        )

    def test_admin_acessa_coordenacao(self, admin_page: Page):
        """Admin consegue acessar /coordenacao."""
        acessa_url_e_aguarda(admin_page, "/coordenacao")
        assert "/coordenacao" in admin_page.url, (
            f"Admin não conseguiu acessar /coordenacao. URL atual: {admin_page.url}"
        )


# ---------------------------------------------------------------------------
# Acesso sem autenticação
# ---------------------------------------------------------------------------

class TestSemAutenticacao:
    """Rotas protegidas redirecionam para login quando não autenticado."""

    def test_anonimo_nao_acessa_admin(self, page: Page):
        acessa_url_e_aguarda(page, "/admin")
        assert esta_na_pagina_de_login(page), (
            f"Usuário não autenticado acessou /admin. URL atual: {page.url}"
        )

    def test_anonimo_nao_acessa_coordenacao(self, page: Page):
        acessa_url_e_aguarda(page, "/coordenacao")
        assert esta_na_pagina_de_login(page), (
            f"Usuário não autenticado acessou /coordenacao. URL atual: {page.url}"
        )

    def test_anonimo_nao_acessa_home_professor(self, page: Page):
        acessa_url_e_aguarda(page, "/home-professor")
        assert esta_na_pagina_de_login(page), (
            f"Usuário não autenticado acessou /home-professor. URL atual: {page.url}"
        )
