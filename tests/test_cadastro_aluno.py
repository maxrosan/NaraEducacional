"""
Testes Playwright para o formulário de cadastro de aluno (StudentFormDialog).

Cobre o bug em que o phoneValue do react-imask era '' no momento do submit,
causando falha de validação mesmo com o telefone visualmente preenchido.
"""

from playwright.sync_api import Page, expect

from conftest import ir_para_aba_admin


# ---------------------------------------------------------------------------
# Helpers locais
# ---------------------------------------------------------------------------

def abrir_dialog_cadastro(page: Page) -> None:
    """Clica no botão principal de cadastro e aguarda o dialog abrir."""
    page.get_by_role("button", name="Cadastrar Novo Aluno").click()
    expect(page.get_by_role("dialog")).to_be_visible()


def preencher_data_nascimento(page: Page, ano: str, mes_index: int, dia: str) -> None:
    """
    Abre o datepicker, navega até ano/mês e clica no dia.

    Parâmetros:
        ano       — ex: "2015"
        mes_index — índice 0-based do mês (0=jan … 11=dez)
        dia       — texto do dia, ex: "15"
    """
    page.get_by_role("dialog").get_by_text("Selecione a data").click()

    # react-day-picker v8: .rdp-dropdown_year/.rdp-dropdown_month são divs wrapper;
    # o <select> nativo fica dentro delas.
    page.locator(".rdp-dropdown_year select").select_option(ano)
    page.locator(".rdp-dropdown_month select").select_option(index=mes_index)

    # Clica no dia (pode haver dois gridcells com o mesmo texto em semanas que
    # se repetem — .first garante que pegamos o primeiro visível)
    page.get_by_role("gridcell", name=dia).first.click()


def preencher_telefone(page: Page, digitos: str) -> None:
    """
    Digita o telefone no campo mascarado.
    Usa type() (tecla a tecla) para que o iMask processe cada caractere.
    """
    campo = page.get_by_role("dialog").locator("#telefone_responsavel")
    campo.click()
    campo.type(digitos)


def selecionar_primeira_turma(page: Page) -> None:
    """Abre o select de turma e escolhe a primeira opção disponível."""
    page.get_by_role("dialog").get_by_text("Selecione a turma").click()
    page.get_by_role("option").first.click()


# ---------------------------------------------------------------------------
# Testes
# ---------------------------------------------------------------------------

def test_cadastro_completo_com_telefone(admin_page: Page):
    """
    Cenário principal: preenche todos os campos, incluindo o telefone,
    e verifica que o formulário é aceito sem erro de validação.

    Antes do fix, phoneValue (react-imask) chegava como '' no submit,
    causando o toast de "campos obrigatórios" mesmo com tudo preenchido.
    """
    page = admin_page
    ir_para_aba_admin(page, "alunos")
    abrir_dialog_cadastro(page)

    dialog = page.get_by_role("dialog")

    dialog.locator("#nome_completo").fill("Aluno Teste Playwright")
    dialog.locator("#nome_responsavel").fill("Responsável Playwright")
    preencher_telefone(page, "11987654321")
    preencher_data_nascimento(page, ano="2015", mes_index=4, dia="15")
    selecionar_primeira_turma(page)

    dialog.get_by_role("button", name="Cadastrar Aluno").click()

    # Toast de sucesso confirma que phoneValue foi capturado corretamente
    expect(page.get_by_text("Aluno cadastrado com sucesso.").first).to_be_visible(timeout=8_000)
    # Dialog fecha automaticamente após sucesso
    expect(dialog).not_to_be_visible(timeout=5_000)


def test_cadastro_falha_sem_telefone(admin_page: Page):
    """
    Submete o formulário sem preencher o telefone.
    Verifica que a mensagem de validação é exibida e o dialog permanece aberto.
    """
    page = admin_page
    ir_para_aba_admin(page, "alunos")
    abrir_dialog_cadastro(page)

    dialog = page.get_by_role("dialog")

    dialog.locator("#nome_completo").fill("Aluno Sem Telefone")
    dialog.locator("#nome_responsavel").fill("Responsável Sem Telefone")
    # Telefone intencionalmente em branco
    preencher_data_nascimento(page, ano="2015", mes_index=4, dia="15")
    selecionar_primeira_turma(page)

    dialog.get_by_role("button", name="Cadastrar Aluno").click()

    expect(
        page.get_by_text("Por favor, preencha todos os campos obrigatórios.").first
    ).to_be_visible(timeout=5_000)
    expect(dialog).to_be_visible()  # dialog não fecha com erro


def test_telefone_nao_apagado_ao_editar_outros_campos(admin_page: Page):
    """
    Regressão direta do bug relatado:
    digita o telefone primeiro e depois altera os demais campos.
    Verifica que o valor do telefone (com máscara) permanece intacto e
    que o formulário é submetido com sucesso.
    """
    page = admin_page
    ir_para_aba_admin(page, "alunos")
    abrir_dialog_cadastro(page)

    dialog = page.get_by_role("dialog")
    telefone = dialog.locator("#telefone_responsavel")

    # 1. Digita o telefone ANTES dos outros campos
    telefone.click()
    telefone.type("11987654321")

    # 2. Preenche os demais campos (interações que antes apagavam o phoneValue)
    dialog.locator("#nome_completo").fill("Aluno Regressão Telefone")
    dialog.locator("#nome_responsavel").fill("Responsável Regressão")
    selecionar_primeira_turma(page)
    preencher_data_nascimento(page, ano="2015", mes_index=4, dia="15")

    # 3. Confirma que a máscara aplicou o valor e ele não foi apagado
    expect(telefone).to_have_value("(11) 98765-4321")

    # 4. Submete e verifica sucesso
    dialog.get_by_role("button", name="Cadastrar Aluno").click()
    expect(page.get_by_text("Aluno cadastrado com sucesso.").first).to_be_visible(timeout=8_000)


def test_dialog_reseta_telefone_ao_reabrir(admin_page: Page):
    """
    Verifica que, ao fechar e reabrir o dialog, o campo de telefone
    começa vazio (sem resíduo de sessão anterior).

    Antes do fix, setPhoneValue('') estava comentado, então o valor
    podia persistir entre aberturas do dialog.
    """
    page = admin_page
    ir_para_aba_admin(page, "alunos")

    # Primeira abertura: digita telefone e fecha sem salvar
    abrir_dialog_cadastro(page)
    dialog = page.get_by_role("dialog")
    preencher_telefone(page, "11987654321")
    page.keyboard.press("Escape")
    expect(dialog).not_to_be_visible(timeout=3_000)

    # Segunda abertura: campo deve estar vazio
    abrir_dialog_cadastro(page)
    dialog = page.get_by_role("dialog")
    expect(dialog.locator("#telefone_responsavel")).to_have_value("")
