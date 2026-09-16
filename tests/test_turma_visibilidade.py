"""
Testes visuais (Playwright) — Visibilidade de turma para professor e coordenador.

Cobre o fluxo completo de ponta a ponta:
  1. Admin cria uma turma no painel administrativo.
  2. Admin cria um usuário professor e o vincula à turma recém-criada.
  3. Admin cria um usuário coordenador.
  4. Professor faz login → turma está acessível em /registro.
  5. Coordenador faz login → turma aparece no filtro da aba Professores em /coordenacao.

Detalhes de implementação:
  • A senha do usuário criado pelo admin é gerada aleatoriamente e exibida no campo
    #password (type="text") do formulário. O teste a captura antes de salvar.
  • A turma é vinculada ao professor via checkbox "Turmas Vinculadas" no formulário
    de criação de usuário (Label htmlFor="turma-{id}").
  • Professor com exatamente 1 turma é redirecionado automaticamente de /registro
    para /registro/{turmaId}, confirmando que a turma está acessível.
  • Coordenadores visualizam todas as turmas da instituição (filtro por instituicao_id),
    sem necessidade de vínculo explícito; a turma aparece no select da aba Professores.

Pré-requisitos para rodar:
  1. Frontend rodando em NARA_BASE_URL (padrão: http://localhost:5173)
  2. Backend rodando em http://localhost:8001
  3. Usuário admin configurado em tests/.env (NARA_ADMIN_EMAIL / NARA_ADMIN_PASSWORD)
  4. venv ativado e dependências instaladas:
       pip install -r tests/requirements.txt
       playwright install chromium
  5. Executar:
       pytest tests/test_turma_visibilidade.py -v
"""

import re
from typing import Optional

import pytest
from playwright.sync_api import Browser, Page, expect

from conftest import BASE_URL, fazer_login, ir_para_aba_admin, selecionar_radix

# ---------------------------------------------------------------------------
# Constantes (nomes únicos para não colidir com dados pré-existentes no banco)
# ---------------------------------------------------------------------------

NOME_TURMA = "Turma Visibilidade PW"
NOME_PROFESSOR = "Prof. Visibilidade PW"
EMAIL_PROFESSOR = "prof.visibilidade.pw@teste.nara"
NOME_COORD = "Coord. Visibilidade PW"
EMAIL_COORD = "coord.visibilidade.pw@teste.nara"


# ---------------------------------------------------------------------------
# Helpers locais
# ---------------------------------------------------------------------------


def criar_turma(page: Page, nome: str) -> None:
    """Cria uma turma no painel admin sem professor pré-selecionado."""
    ir_para_aba_admin(page, "turmas")

    page.get_by_role("button", name=re.compile(r"Nova Turma", re.IGNORECASE)).click()
    expect(page.get_by_role("dialog")).to_be_visible(timeout=5_000)

    page.locator("#nome").fill(nome)
    page.locator("#faixa_etaria").fill("4 anos")
    selecionar_radix(page, "turno", "Manhã")

    page.get_by_role("button", name="Salvar").click()
    expect(page.get_by_role("dialog")).to_be_hidden(timeout=8_000)
    expect(page.get_by_text(nome)).to_be_visible(timeout=8_000)


def criar_usuario_e_capturar_senha(
    page: Page,
    nome: str,
    email: str,
    perfil_label: str,
    nome_turma: Optional[str] = None,
) -> str:
    """
    Cria um usuário via painel admin, captura a senha gerada automaticamente
    e, opcionalmente, vincula uma turma pelo checkbox "Turmas Vinculadas".

    Retorna a senha gerada para uso no login subsequente.
    """
    ir_para_aba_admin(page, "usuarios")

    page.get_by_role("button", name=re.compile(r"Novo Usuário", re.IGNORECASE)).click()
    expect(page.get_by_role("dialog")).to_be_visible(timeout=5_000)

    page.locator("#nome").fill(nome)
    page.locator("#email").fill(email)
    selecionar_radix(page, "perfil", perfil_label)

    # O campo #password é type="text" e já vem preenchido com uma senha aleatória
    # gerada por generatePassword() no UserFormDialog. Captura antes de salvar.
    senha = page.locator("#password").input_value()

    if nome_turma:
        # Seção "Turmas Vinculadas": checkbox associado ao label com o nome da turma
        # (renderizado como <Label htmlFor="turma-{id}">{turma.nome}</Label>)
        page.get_by_label(nome_turma).check()

    page.get_by_role("button", name="Salvar").click()
    expect(page.get_by_role("dialog")).to_be_hidden(timeout=8_000)
    expect(page.get_by_text(nome)).to_be_visible(timeout=8_000)

    return senha


def verificar_turma_visivel_professor(page: Page, nome_turma: str) -> None:
    """
    Verifica que o professor consegue acessar sua turma em /registro.

    Com exatamente uma turma vinculada via usuario_turmas, o sistema redireciona
    automaticamente de /registro para /registro/{turmaId}. A mudança de URL
    confirma o acesso, e a exibição de "Tipo de registro" confirma que a página
    carregou com sucesso para aquela turma.
    """
    page.goto(f"{BASE_URL}/registro")

    # Com 1 turma, o app chama navigate('/registro/{id}', { replace: true })
    page.wait_for_url(re.compile(r"/registro/[0-9a-f-]{36}$"), timeout=10_000)

    # A etapa "Tipo de registro" confirma que a turma foi carregada
    expect(page.get_by_text("Tipo de registro")).to_be_visible(timeout=8_000)


def verificar_turma_visivel_coordenador(page: Page, nome_turma: str) -> None:
    """
    Verifica que a turma está visível para o coordenador em /coordenacao.

    Coordenadores visualizam automaticamente todas as turmas da instituição
    (filtro por instituicao_id), sem precisar de vínculo direto na usuario_turmas.
    A turma aparece como opção no select de filtro da aba Professores.
    """
    page.goto(f"{BASE_URL}/coordenacao")
    page.wait_for_load_state("networkidle")

    # Navega para a aba Professores usando o botão Ghost no menu de navegação
    page.get_by_role("button", name="Professores").click()
    page.wait_for_load_state("networkidle")

    # Abre o select de filtro de turmas (exibe "Todas as Turmas" por padrão)
    # As turmas são populadas a partir de viewData.turmas (todas da instituição)
    page.locator("button[role='combobox']:has-text('Todas as Turmas')").click()

    # A turma criada pelo admin deve aparecer como opção
    expect(page.get_by_role("option", name=nome_turma)).to_be_visible(timeout=8_000)


# ---------------------------------------------------------------------------
# Testes
# ---------------------------------------------------------------------------


class TestTurmaVisibilidadeProfessorCoordenador:
    """
    Fluxo completo: admin cria turma e usuários; professor e coordenador
    conseguem visualizá-la após login com suas respectivas contas.
    """

    def test_admin_cria_turma_professor_e_coordenador_visualizam(
        self,
        admin_page: Page,
        browser: Browser,
    ) -> None:
        """
        Passos:
          1. Admin cria a turma "Turma Visibilidade PW".
          2. Admin cria "Prof. Visibilidade PW" vinculando-o à turma pelo checkbox.
          3. Admin cria "Coord. Visibilidade PW" (sem vínculo explícito de turma).
          4. Professor faz login → é redirecionado para /registro/{turmaId},
             confirmando que a turma está acessível.
          5. Coordenador faz login → encontra a turma no filtro da aba Professores
             em /coordenacao, confirmando visibilidade institucional.
        """
        # ------------------------------------------------------------------ #
        # Passo 1 — Admin cria a turma                                        #
        # ------------------------------------------------------------------ #
        criar_turma(admin_page, NOME_TURMA)

        # ------------------------------------------------------------------ #
        # Passo 2 — Admin cria o professor e vincula à turma                  #
        # ------------------------------------------------------------------ #
        senha_professor = criar_usuario_e_capturar_senha(
            admin_page,
            nome=NOME_PROFESSOR,
            email=EMAIL_PROFESSOR,
            perfil_label="Professor",
            nome_turma=NOME_TURMA,
        )

        # ------------------------------------------------------------------ #
        # Passo 3 — Admin cria o coordenador                                  #
        # Coordenadores veem todas as turmas da instituição automaticamente;   #
        # não há necessidade de vinculá-los explicitamente à turma.            #
        # ------------------------------------------------------------------ #
        senha_coord = criar_usuario_e_capturar_senha(
            admin_page,
            nome=NOME_COORD,
            email=EMAIL_COORD,
            perfil_label="Coordenador",
        )

        # ------------------------------------------------------------------ #
        # Passo 4 — Professor faz login e verifica visibilidade da turma       #
        # Contexto isolado garante sessão independente da sessão de admin.     #
        # ------------------------------------------------------------------ #
        with browser.new_context() as ctx_prof:
            prof_page = ctx_prof.new_page()
            fazer_login(prof_page, EMAIL_PROFESSOR, senha_professor)
            verificar_turma_visivel_professor(prof_page, NOME_TURMA)

        # ------------------------------------------------------------------ #
        # Passo 5 — Coordenador faz login e verifica visibilidade da turma     #
        # ------------------------------------------------------------------ #
        with browser.new_context() as ctx_coord:
            coord_page = ctx_coord.new_page()
            fazer_login(coord_page, EMAIL_COORD, senha_coord)
            verificar_turma_visivel_coordenador(coord_page, NOME_TURMA)
