"""
Testes E2E para o CRUD de perguntas (especialistas e BNCC)
e integração com turma/aluno.

Cobre:
  - Especialistas (/admin/perguntas): Create, Read, Update, Delete
  - BNCC (/admin/perguntas-bncc): Create, Read, Update, Delete
  - Integração: turma + aluno + perguntas filtradas por nível
"""

import uuid

from playwright.sync_api import Page, expect

from conftest import ir_para_aba_admin

# Sufixo único por execução
SUFIXO = uuid.uuid4().hex[:6]

# Dados — Perguntas Especialistas
PERGUNTA_ESP = f"Como a criança interage {SUFIXO}?"
PERGUNTA_ESP_EDITADA = f"Como a criança interage editada {SUFIXO}?"
REFERENCIA_ESP = f"EI{SUFIXO[:4]}"

# Dados — Perguntas BNCC
PERGUNTA_BNCC = f"Demonstra curiosidade {SUFIXO}?"
PERGUNTA_BNCC_EDITADA = f"Demonstra curiosidade editada {SUFIXO}?"

# Dados — Turma e Aluno
NOME_TURMA = f"Turma Pgta {SUFIXO}"
NOME_ALUNO = f"Aluno Pgta {SUFIXO}"
RESPONSAVEL = f"Resp Pgta {SUFIXO}"

# Constantes
CAMPO = "O eu, o outro e o nós"
NIVEL = "Nível 5"

# Pergunta BNCC de integração (permanece após os testes)
PERGUNTA_INTEG = f"Integração turma-aluno {SUFIXO}?"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def selecionar_campo_experiencia(page: Page, campo: str) -> None:
    """Abre o CreatableCampoSelect no dialog e seleciona o campo."""
    dialog = page.get_by_role("dialog")
    dialog.get_by_text("Selecione ou digite um Campo de Experiência").click()
    # .last evita conflito com textos iguais na tabela/accordion
    page.get_by_text(campo, exact=True).last.click()


# ---------------------------------------------------------------------------
# 1. Perguntas de Especialistas — /admin/perguntas
# ---------------------------------------------------------------------------

def test_lista_perguntas_especialistas_visivel(admin_page: Page):
    """Verifica tabela de perguntas especialistas com headers corretos."""
    page = admin_page
    ir_para_aba_admin(page, "perguntas")

    expect(page.get_by_text("Perguntas dos Especialistas (Livres)")).to_be_visible(timeout=10_000)

    tabela = page.get_by_role("table")
    expect(tabela).to_be_visible()

    for header in [
        "Campo de Experiência", "Nível", "Pergunta Facilitadora",
        "Referência (BNCC)", "Status", "Ações",
    ]:
        expect(tabela.get_by_role("columnheader", name=header)).to_be_visible()


def test_cadastrar_pergunta_especialista(admin_page: Page):
    """Cria pergunta de especialista e verifica na tabela."""
    page = admin_page
    ir_para_aba_admin(page, "perguntas")

    page.get_by_role("button", name="Nova Pergunta").click()
    dialog = page.get_by_role("dialog")
    expect(dialog).to_be_visible()

    selecionar_campo_experiencia(page, CAMPO)

    # Nível (primeiro combobox do dialog)
    dialog.get_by_role("combobox").first.click()
    page.get_by_role("option", name=NIVEL, exact=True).click()

    dialog.locator("#pergunta_facilitadora").fill(PERGUNTA_ESP)
    dialog.locator("#referencia_norma").fill(REFERENCIA_ESP)

    dialog.get_by_role("button", name="Salvar").click()

    expect(page.get_by_text("Pergunta salva com sucesso!").first).to_be_visible(timeout=8_000)
    expect(page.get_by_role("row").filter(has_text=PERGUNTA_ESP)).to_be_visible(timeout=5_000)


def test_editar_pergunta_especialista(admin_page: Page):
    """Edita a pergunta criada e verifica atualização na tabela."""
    page = admin_page
    ir_para_aba_admin(page, "perguntas")

    linha = page.get_by_role("row").filter(has_text=PERGUNTA_ESP)
    expect(linha).to_be_visible(timeout=10_000)

    # Primeiro botão na coluna Ações = Editar
    linha.get_by_role("button").first.click()

    dialog = page.get_by_role("dialog")
    expect(dialog).to_be_visible(timeout=5_000)

    campo = dialog.locator("#pergunta_facilitadora")
    expect(campo).to_have_value(PERGUNTA_ESP)
    campo.fill(PERGUNTA_ESP_EDITADA)

    dialog.get_by_role("button", name="Salvar").click()

    expect(page.get_by_text("Pergunta salva com sucesso!").first).to_be_visible(timeout=8_000)
    expect(page.get_by_role("row").filter(has_text=PERGUNTA_ESP_EDITADA)).to_be_visible(timeout=5_000)


def test_excluir_pergunta_especialista(admin_page: Page):
    """Exclui a pergunta editada e verifica remoção."""
    page = admin_page
    ir_para_aba_admin(page, "perguntas")

    linha = page.get_by_role("row").filter(has_text=PERGUNTA_ESP_EDITADA)
    expect(linha).to_be_visible(timeout=10_000)

    # Segundo botão = Excluir (abre Dialog de confirmação)
    linha.get_by_role("button").nth(1).click()

    dialog = page.get_by_role("dialog")
    expect(dialog).to_be_visible(timeout=5_000)
    expect(dialog.get_by_text("Confirmar Exclusão")).to_be_visible()
    expect(dialog.get_by_text("Tem certeza que deseja excluir esta pergunta?")).to_be_visible()

    dialog.get_by_role("button", name="Excluir").click()

    expect(page.get_by_text("Pergunta deletada com sucesso!").first).to_be_visible(timeout=8_000)
    expect(page.get_by_role("row").filter(has_text=PERGUNTA_ESP_EDITADA)).not_to_be_visible(timeout=5_000)


def test_cancelar_exclusao_pergunta_especialista(admin_page: Page):
    """Cancela a exclusão e verifica que a pergunta permanece."""
    page = admin_page
    ir_para_aba_admin(page, "perguntas")

    primeira_linha = page.get_by_role("row").nth(1)  # pula header
    expect(primeira_linha).to_be_visible(timeout=10_000)
    texto = primeira_linha.get_by_role("cell").nth(2).inner_text()

    primeira_linha.get_by_role("button").nth(1).click()

    dialog = page.get_by_role("dialog")
    expect(dialog).to_be_visible(timeout=5_000)

    dialog.get_by_role("button", name="Cancelar").click()
    expect(dialog).not_to_be_visible(timeout=3_000)

    expect(page.get_by_role("row").filter(has_text=texto)).to_be_visible()


# ---------------------------------------------------------------------------
# 2. Perguntas BNCC — /admin/perguntas-bncc
# ---------------------------------------------------------------------------

def test_pagina_perguntas_bncc_visivel(admin_page: Page):
    """Verifica que a página de gestão BNCC carrega corretamente."""
    page = admin_page
    ir_para_aba_admin(page, "perguntas-bncc")

    expect(page.get_by_text("Gestão de Perguntas BNCC")).to_be_visible(timeout=10_000)
    expect(page.get_by_role("button", name="Nova Pergunta")).to_be_visible()
    expect(page.get_by_role("button", name="Gerenciar Campos")).to_be_visible()


def test_cadastrar_pergunta_bncc(admin_page: Page):
    """Cria pergunta BNCC e verifica no accordion."""
    page = admin_page
    ir_para_aba_admin(page, "perguntas-bncc")

    page.get_by_role("button", name="Nova Pergunta").first.click()
    dialog = page.get_by_role("dialog")
    expect(dialog).to_be_visible(timeout=5_000)
    expect(dialog.get_by_text("Nova Pergunta BNCC")).to_be_visible()

    selecionar_campo_experiencia(page, CAMPO)

    # Nível/Faixa Etária (único combobox no dialog)
    dialog.get_by_role("combobox").click()
    page.get_by_role("option", name=NIVEL, exact=True).click()

    dialog.locator("#pergunta").fill(PERGUNTA_BNCC)
    dialog.locator("#habilidade_bncc").fill("EI03TS01")

    dialog.get_by_role("button", name="Salvar Pergunta").click()

    expect(page.get_by_text("Pergunta criada com sucesso!").first).to_be_visible(timeout=8_000)
    expect(page.get_by_text(PERGUNTA_BNCC)).to_be_visible(timeout=5_000)


def test_editar_pergunta_bncc(admin_page: Page):
    """Edita pergunta BNCC e verifica atualização."""
    page = admin_page
    ir_para_aba_admin(page, "perguntas-bncc")

    expect(page.get_by_text(PERGUNTA_BNCC)).to_be_visible(timeout=10_000)

    # Localiza o card da pergunta no accordion
    card = page.locator("div.p-4.bg-gray-50").filter(has_text=PERGUNTA_BNCC)
    card.get_by_role("button", name="Editar").click()

    dialog = page.get_by_role("dialog")
    expect(dialog).to_be_visible(timeout=5_000)
    expect(dialog.get_by_text("Editar Pergunta BNCC")).to_be_visible()

    # Primeiro textarea = Pergunta Facilitadora
    textarea = dialog.locator("textarea").first
    textarea.fill(PERGUNTA_BNCC_EDITADA)

    dialog.get_by_role("button", name="Salvar Alterações").click()

    expect(page.get_by_text("Pergunta atualizada!").first).to_be_visible(timeout=8_000)
    expect(page.get_by_text(PERGUNTA_BNCC_EDITADA)).to_be_visible(timeout=5_000)


def test_excluir_pergunta_bncc(admin_page: Page):
    """Exclui pergunta BNCC e verifica remoção."""
    page = admin_page
    ir_para_aba_admin(page, "perguntas-bncc")

    expect(page.get_by_text(PERGUNTA_BNCC_EDITADA)).to_be_visible(timeout=10_000)

    card = page.locator("div.p-4.bg-gray-50").filter(has_text=PERGUNTA_BNCC_EDITADA)
    card.get_by_role("button", name="Excluir").click()

    dialog = page.get_by_role("dialog")
    expect(dialog).to_be_visible(timeout=5_000)
    expect(dialog.get_by_text("Confirmar Exclusão")).to_be_visible()

    dialog.get_by_role("button", name="Excluir").click()

    expect(page.get_by_text("Pergunta excluída com sucesso!").first).to_be_visible(timeout=8_000)
    expect(page.get_by_text(PERGUNTA_BNCC_EDITADA)).not_to_be_visible(timeout=5_000)


# ---------------------------------------------------------------------------
# 3. Integração: turma + aluno + perguntas por nível
# ---------------------------------------------------------------------------

def test_criar_turma_nivel_5(admin_page: Page):
    """Cria turma de teste com Faixa Etária Nível 5."""
    page = admin_page
    ir_para_aba_admin(page, "turmas")

    page.get_by_role("button", name="Nova Turma").click()
    dialog = page.get_by_role("dialog")
    expect(dialog).to_be_visible(timeout=5_000)

    dialog.locator("#nome").fill(NOME_TURMA)

    dialog.locator("#faixa_etaria").click()
    page.get_by_role("option", name=NIVEL, exact=True).click()

    dialog.locator("#turno").click()
    page.get_by_role("option", name="Manhã", exact=True).click()

    dialog.get_by_role("button", name="Salvar").click()

    expect(page.get_by_text("Turma criada com sucesso!").first).to_be_visible(timeout=8_000)
    expect(page.get_by_role("row").filter(has_text=NOME_TURMA)).to_be_visible(timeout=5_000)


def test_criar_aluno_na_turma(admin_page: Page):
    """Cria aluno vinculado à turma de teste."""
    page = admin_page
    ir_para_aba_admin(page, "alunos")

    page.get_by_role("button", name="Cadastrar Novo Aluno").click()
    dialog = page.get_by_role("dialog")
    expect(dialog).to_be_visible()

    dialog.locator("#nome_completo").fill(NOME_ALUNO)
    dialog.locator("#nome_responsavel").fill(RESPONSAVEL)

    tel = dialog.locator("#telefone_responsavel")
    tel.click()
    tel.type("11987654321")

    dialog.get_by_text("Selecione a data").click()
    page.locator(".rdp-dropdown_year select").select_option("2019")
    page.locator(".rdp-dropdown_month select").select_option(index=0)
    page.get_by_role("gridcell", name="10").first.click()

    dialog.get_by_text("Selecione a turma").click()
    page.get_by_role("option").filter(has_text=NOME_TURMA).click()

    dialog.get_by_role("button", name="Cadastrar Aluno").click()

    expect(page.get_by_text("Aluno cadastrado com sucesso.").first).to_be_visible(timeout=8_000)
    expect(page.get_by_role("row").filter(has_text=NOME_ALUNO)).to_be_visible(timeout=5_000)


def test_pergunta_bncc_visivel_para_nivel_do_aluno(admin_page: Page):
    """
    Cria pergunta BNCC para Nível 5 e verifica que aparece ao filtrar
    por esse nível — o mesmo da turma do aluno criado.

    O formulário de observação (/registro/{turmaId}) busca perguntas BNCC
    pela faixa etária da turma, então perguntas Nível 5 aparecem
    automaticamente para alunos em turmas Nível 5.
    """
    page = admin_page

    # 1. Criar pergunta BNCC para Nível 5
    ir_para_aba_admin(page, "perguntas-bncc")

    page.get_by_role("button", name="Nova Pergunta").first.click()
    dialog = page.get_by_role("dialog")
    expect(dialog).to_be_visible()

    selecionar_campo_experiencia(page, CAMPO)

    dialog.get_by_role("combobox").click()
    page.get_by_role("option", name=NIVEL, exact=True).click()

    dialog.locator("#pergunta").fill(PERGUNTA_INTEG)

    dialog.get_by_role("button", name="Salvar Pergunta").click()
    expect(page.get_by_text("Pergunta criada com sucesso!").first).to_be_visible(timeout=8_000)

    # 2. Filtrar por Nível 5 — pergunta deve aparecer
    page.locator("[role='combobox']").filter(has_text="Filtrar por Nível").click()
    page.get_by_role("option", name=NIVEL, exact=True).click()

    expect(page.get_by_text(PERGUNTA_INTEG)).to_be_visible(timeout=5_000)

    # 3. Confirmar que a turma do aluno tem o mesmo nível
    ir_para_aba_admin(page, "turmas")
    linha_turma = page.get_by_role("row").filter(has_text=NOME_TURMA)
    expect(linha_turma).to_be_visible(timeout=10_000)
    expect(linha_turma.get_by_role("cell").nth(1)).to_have_text(NIVEL)
