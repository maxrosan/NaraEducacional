"""
Testes E2E para o CRUD completo de alunos.

Cobre: listar (Read), cadastrar (Create), editar (Update),
excluir (Delete) e cancelar exclusão.
"""

import uuid

from playwright.sync_api import Page, expect

from conftest import ir_para_aba_admin

# Nome único para evitar colisões entre execuções
SUFIXO = uuid.uuid4().hex[:6]
NOME_ALUNO = f"Aluno CRUD {SUFIXO}"
NOME_ALUNO_EDITADO = f"Aluno CRUD Editado {SUFIXO}"
RESPONSAVEL = f"Responsável CRUD {SUFIXO}"
TELEFONE_DIGITOS = "11987654321"


# ---------------------------------------------------------------------------
# Helpers locais (similares aos de test_cadastro_aluno.py)
# ---------------------------------------------------------------------------

def abrir_dialog_cadastro(page: Page) -> None:
    page.get_by_role("button", name="Cadastrar Novo Aluno").click()
    expect(page.get_by_role("dialog")).to_be_visible()


def preencher_telefone(page: Page, digitos: str) -> None:
    campo = page.get_by_role("dialog").locator("#telefone_responsavel")
    campo.click()
    campo.type(digitos)


def preencher_data_nascimento(page: Page, ano: str, mes_index: int, dia: str) -> None:
    page.get_by_role("dialog").get_by_text("Selecione a data").click()
    page.locator(".rdp-dropdown_year select").select_option(ano)
    page.locator(".rdp-dropdown_month select").select_option(index=mes_index)
    page.get_by_role("gridcell", name=dia).first.click()


def selecionar_primeira_turma(page: Page) -> None:
    page.get_by_role("dialog").get_by_text("Selecione a turma").click()
    page.get_by_role("option").first.click()


# ---------------------------------------------------------------------------
# Testes
# ---------------------------------------------------------------------------

def test_lista_alunos_visivel(admin_page: Page):
    """Verifica que a tabela de alunos é visível com os headers corretos."""
    page = admin_page
    ir_para_aba_admin(page, "alunos")

    tabela = page.get_by_role("table")
    expect(tabela).to_be_visible(timeout=10_000)

    for header in ["Nome Completo", "Data de Nasc.", "Turma", "Responsável", "Telefone", "Ações"]:
        expect(tabela.get_by_role("columnheader", name=header)).to_be_visible()


def test_cadastrar_aluno(admin_page: Page):
    """Cadastra um novo aluno e verifica que aparece na tabela."""
    page = admin_page
    ir_para_aba_admin(page, "alunos")
    abrir_dialog_cadastro(page)

    dialog = page.get_by_role("dialog")
    dialog.locator("#nome_completo").fill(NOME_ALUNO)
    dialog.locator("#nome_responsavel").fill(RESPONSAVEL)
    preencher_telefone(page, TELEFONE_DIGITOS)
    preencher_data_nascimento(page, ano="2015", mes_index=4, dia="15")
    selecionar_primeira_turma(page)

    dialog.get_by_role("button", name="Cadastrar Aluno").click()

    expect(page.get_by_text("Aluno cadastrado com sucesso.").first).to_be_visible(timeout=8_000)
    expect(dialog).not_to_be_visible(timeout=5_000)

    # Aluno deve aparecer na tabela
    expect(page.get_by_role("row").filter(has_text=NOME_ALUNO)).to_be_visible(timeout=5_000)


def test_editar_aluno(admin_page: Page):
    """Edita o nome do aluno criado e verifica a atualização na tabela."""
    page = admin_page
    ir_para_aba_admin(page, "alunos")

    # Localiza a linha do aluno
    linha = page.get_by_role("row").filter(has_text=NOME_ALUNO)
    expect(linha).to_be_visible(timeout=10_000)

    # Clica no botão de edição (primeiro botão ghost/icon na coluna Ações)
    linha.get_by_role("button").first.click()

    dialog = page.get_by_role("dialog")
    expect(dialog).to_be_visible(timeout=5_000)
    expect(dialog.get_by_text("Editar Aluno")).to_be_visible()

    # Verifica campo pré-preenchido e altera o nome
    nome_input = dialog.locator("#nome_completo")
    expect(nome_input).to_have_value(NOME_ALUNO)
    nome_input.fill(NOME_ALUNO_EDITADO)

    dialog.get_by_role("button", name="Salvar Alterações").click()

    expect(page.get_by_text("Aluno atualizado com sucesso.").first).to_be_visible(timeout=8_000)
    expect(dialog).not_to_be_visible(timeout=5_000)

    # Nome atualizado na tabela
    expect(page.get_by_role("row").filter(has_text=NOME_ALUNO_EDITADO)).to_be_visible(timeout=5_000)


def test_excluir_aluno(admin_page: Page):
    """Exclui o aluno editado e verifica que desaparece da tabela."""
    page = admin_page
    ir_para_aba_admin(page, "alunos")

    linha = page.get_by_role("row").filter(has_text=NOME_ALUNO_EDITADO)
    expect(linha).to_be_visible(timeout=10_000)

    # Botão de exclusão é o segundo botão (após o de edição)
    linha.get_by_role("button").nth(1).click()

    # AlertDialog de confirmação
    alert = page.get_by_role("alertdialog")
    expect(alert).to_be_visible(timeout=5_000)
    expect(alert.get_by_text("Você tem certeza?")).to_be_visible()

    page.get_by_role("button", name="Sim, excluir").click()

    expect(page.get_by_text("Aluno desativado com sucesso.").first).to_be_visible(timeout=8_000)

    # Aluno não deve mais aparecer
    expect(page.get_by_role("row").filter(has_text=NOME_ALUNO_EDITADO)).not_to_be_visible(timeout=5_000)


def test_cancelar_exclusao(admin_page: Page):
    """Cancela a exclusão e verifica que o aluno permanece na tabela."""
    page = admin_page
    ir_para_aba_admin(page, "alunos")

    # Usa qualquer aluno existente na tabela (primeira linha de dados)
    primeira_linha = page.get_by_role("row").nth(1)  # nth(0) é o header
    expect(primeira_linha).to_be_visible(timeout=10_000)
    nome_aluno = primeira_linha.get_by_role("cell").first.inner_text()

    # Clica no botão de exclusão
    primeira_linha.get_by_role("button").nth(1).click()

    alert = page.get_by_role("alertdialog")
    expect(alert).to_be_visible(timeout=5_000)

    # Cancela
    page.get_by_role("button", name="Cancelar").click()
    expect(alert).not_to_be_visible(timeout=3_000)

    # Aluno ainda está na tabela
    expect(page.get_by_role("row").filter(has_text=nome_aluno)).to_be_visible()
