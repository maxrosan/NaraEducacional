"""
Testes visuais (Playwright) — Adição de usuários no painel administrativo do Nara.

Cobre os perfis:
  • professor
  • professor_especialista
  • coordenador
  • especialista  (com tipo de especialista)
  • admin

Pré-requisitos para rodar:
  1. Frontend rodando em http://localhost:5173 (ou NARA_BASE_URL)
  2. Backend rodando em http://localhost:8001
  3. Banco populado com `python manage.py seed_dev_data`
  4. venv ativado e dependências instaladas:
       pip install -r tests/requirements.txt
       playwright install chromium
  5. Executar:
       pytest tests/test_admin_usuarios.py -v
"""

import re
import pytest
from playwright.sync_api import Page, expect

from conftest import ir_para_aba_admin, selecionar_radix


# ---------------------------------------------------------------------------
# Helper local
# ---------------------------------------------------------------------------

def abrir_dialog_novo_usuario(page: Page) -> None:
    """Clica no botão 'Novo Usuário' e aguarda o dialog abrir."""
    page.get_by_role("button", name=re.compile(r"Novo Usuário", re.IGNORECASE)).click()
    expect(page.get_by_role("dialog")).to_be_visible(timeout=5_000)


def preencher_campos_base(page: Page, nome: str, email: str) -> None:
    """Preenche nome e email no formulário de usuário."""
    page.locator("#nome").fill(nome)
    page.locator("#email").fill(email)


def salvar_e_confirmar(page: Page, nome_usuario: str) -> None:
    """Clica em Salvar e verifica que o usuário aparece na listagem."""
    page.get_by_role("button", name="Salvar").click()

    # Dialog deve fechar
    expect(page.get_by_role("dialog")).to_be_hidden(timeout=8_000)

    # Nome deve aparecer na tabela
    expect(page.get_by_text(nome_usuario)).to_be_visible(timeout=8_000)


# ---------------------------------------------------------------------------
# Testes
# ---------------------------------------------------------------------------

class TestAdicionarProfessor:
    """Testa criação de usuário com perfil 'professor'."""

    def test_adicionar_professor_simples(self, admin_page: Page):
        ir_para_aba_admin(admin_page, "usuarios")

        abrir_dialog_novo_usuario(admin_page)

        preencher_campos_base(
            admin_page,
            nome="Professora Teste Playwright",
            email="prof.playwright@teste.nara",
        )

        selecionar_radix(admin_page, "perfil", "Professor")

        salvar_e_confirmar(admin_page, "Professora Teste Playwright")

    def test_adicionar_professor_especialista(self, admin_page: Page):
        ir_para_aba_admin(admin_page, "usuarios")

        abrir_dialog_novo_usuario(admin_page)

        preencher_campos_base(
            admin_page,
            nome="Prof. Especialista Playwright",
            email="prof.esp.playwright@teste.nara",
        )

        selecionar_radix(admin_page, "perfil", "Professor Especialista")

        # Tipo de especialista é obrigatório para esse perfil
        selecionar_radix(admin_page, "tipo_especialista", "Psicopedagogo")

        salvar_e_confirmar(admin_page, "Prof. Especialista Playwright")


class TestAdicionarCoordenador:
    """Testa criação de usuário com perfil 'coordenador'."""

    def test_adicionar_coordenador(self, admin_page: Page):
        ir_para_aba_admin(admin_page, "usuarios")

        abrir_dialog_novo_usuario(admin_page)

        preencher_campos_base(
            admin_page,
            nome="Coordenador Playwright",
            email="coord.playwright@teste.nara",
        )

        selecionar_radix(admin_page, "perfil", "Coordenador")

        salvar_e_confirmar(admin_page, "Coordenador Playwright")


class TestAdicionarEspecialista:
    """Testa criação de usuários com perfil 'especialista' para cada tipo."""

    @pytest.mark.parametrize("tipo_label,nome", [
        ("Psicólogo", "Psicólogo Playwright"),
        ("Psicopedagogo", "Psicopedagogo Playwright"),
        ("Fonoaudiólogo", "Fono Playwright"),
        ("Terapeuta Ocupacional", "TO Playwright"),
    ])
    def test_adicionar_especialista_por_tipo(self, admin_page: Page, tipo_label: str, nome: str):
        ir_para_aba_admin(admin_page, "usuarios")

        abrir_dialog_novo_usuario(admin_page)

        email = f"{nome.lower().replace(' ', '.')}@teste.nara"
        preencher_campos_base(admin_page, nome=nome, email=email)

        selecionar_radix(admin_page, "perfil", "Especialista")
        selecionar_radix(admin_page, "tipo_especialista", tipo_label)

        salvar_e_confirmar(admin_page, nome)

    def test_adicionar_especialista_tipo_outro(self, admin_page: Page):
        ir_para_aba_admin(admin_page, "usuarios")

        abrir_dialog_novo_usuario(admin_page)

        preencher_campos_base(
            admin_page,
            nome="Nutricionista Playwright",
            email="nutri.playwright@teste.nara",
        )

        selecionar_radix(admin_page, "perfil", "Especialista")
        selecionar_radix(admin_page, "tipo_especialista", "Outro")

        # Campo de texto livre para tipo personalizado
        admin_page.locator("#tipo_especialista_outro").fill("Nutricionista")

        salvar_e_confirmar(admin_page, "Nutricionista Playwright")


class TestAdicionarAdmin:
    """Testa criação de usuário com perfil 'admin'."""

    def test_adicionar_administrador(self, admin_page: Page):
        ir_para_aba_admin(admin_page, "usuarios")

        abrir_dialog_novo_usuario(admin_page)

        preencher_campos_base(
            admin_page,
            nome="Admin Playwright",
            email="admin.playwright@teste.nara",
        )

        selecionar_radix(admin_page, "perfil", "Administrador")

        salvar_e_confirmar(admin_page, "Admin Playwright")


class TestCamposObrigatorios:
    """Verifica que o formulário exige campos obrigatórios."""

    def test_salvar_sem_perfil_nao_fecha_dialog(self, admin_page: Page):
        ir_para_aba_admin(admin_page, "usuarios")

        abrir_dialog_novo_usuario(admin_page)

        preencher_campos_base(
            admin_page,
            nome="Usuário Sem Perfil",
            email="semperfil@teste.nara",
        )

        # Não seleciona perfil — deve falhar validação nativa do browser
        admin_page.get_by_role("button", name="Salvar").click()

        # Dialog permanece aberto
        expect(admin_page.get_by_role("dialog")).to_be_visible()
