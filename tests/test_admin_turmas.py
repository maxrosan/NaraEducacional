"""
Testes visuais (Playwright) — Adição de turmas no painel administrativo do Nara.

Cobre cenários:
  • Criar turma simples (sem professor)
  • Criar turma com professor associado
  • Criar múltiplas turmas em sequência
  • Validação de campos obrigatórios

Pré-requisitos para rodar:
  1. Frontend rodando em http://localhost:5173 (ou NARA_BASE_URL)
  2. Backend rodando em http://localhost:8001
  3. Banco populado com `python manage.py seed_dev_data`
  4. venv ativado e dependências instaladas:
       pip install -r tests/requirements.txt
       playwright install chromium
  5. Executar:
       pytest tests/test_admin_turmas.py -v
"""

import re
import pytest
from playwright.sync_api import Page, expect

from conftest import ir_para_aba_admin, selecionar_radix


# ---------------------------------------------------------------------------
# Helper local
# ---------------------------------------------------------------------------

def abrir_dialog_nova_turma(page: Page) -> None:
    """Clica no botão 'Nova Turma' e aguarda o dialog abrir."""
    page.get_by_role("button", name=re.compile(r"Nova Turma", re.IGNORECASE)).click()
    expect(page.get_by_role("dialog")).to_be_visible(timeout=5_000)


def preencher_turma(
    page: Page,
    nome: str,
    faixa_etaria: str,
    turno: str,
    ano_letivo: str = "2026",
) -> None:
    """Preenche os campos de texto e select da turma."""
    page.locator("#nome").fill(nome)
    page.locator("#faixa_etaria").fill(faixa_etaria)
    selecionar_radix(page, "turno", turno)

    # Ano letivo já vem preenchido, mas garante o valor correto
    campo_ano = page.locator("#ano_letivo")
    campo_ano.fill("")
    campo_ano.fill(ano_letivo)


def salvar_e_confirmar(page: Page, nome_turma: str) -> None:
    """Clica em Salvar e verifica que a turma aparece na listagem."""
    page.get_by_role("button", name="Salvar").click()

    # Dialog deve fechar
    expect(page.get_by_role("dialog")).to_be_hidden(timeout=8_000)

    # Nome deve aparecer na tabela
    expect(page.get_by_text(nome_turma)).to_be_visible(timeout=8_000)


# ---------------------------------------------------------------------------
# Testes — Criação de turma única
# ---------------------------------------------------------------------------

class TestAdicionarTurma:
    """Testa criação de turmas individuais."""

    def test_criar_turma_manha(self, admin_page: Page):
        ir_para_aba_admin(admin_page, "turmas")

        abrir_dialog_nova_turma(admin_page)
        preencher_turma(
            admin_page,
            nome="Turma Manhã PW",
            faixa_etaria="3 anos",
            turno="Manhã",
        )
        salvar_e_confirmar(admin_page, "Turma Manhã PW")

    def test_criar_turma_tarde(self, admin_page: Page):
        ir_para_aba_admin(admin_page, "turmas")

        abrir_dialog_nova_turma(admin_page)
        preencher_turma(
            admin_page,
            nome="Turma Tarde PW",
            faixa_etaria="4 anos",
            turno="Tarde",
        )
        salvar_e_confirmar(admin_page, "Turma Tarde PW")

    def test_criar_turma_integral(self, admin_page: Page):
        ir_para_aba_admin(admin_page, "turmas")

        abrir_dialog_nova_turma(admin_page)
        preencher_turma(
            admin_page,
            nome="Turma Integral PW",
            faixa_etaria="5 anos",
            turno="Integral",
        )
        salvar_e_confirmar(admin_page, "Turma Integral PW")

    def test_criar_turma_com_professor(self, admin_page: Page):
        """Cria turma e vincula um professor existente (do seed)."""
        ir_para_aba_admin(admin_page, "turmas")

        abrir_dialog_nova_turma(admin_page)
        preencher_turma(
            admin_page,
            nome="Turma Com Professor PW",
            faixa_etaria="2 anos",
            turno="Manhã",
        )

        # Seleciona o primeiro professor disponível (se existir)
        select_prof = admin_page.locator("#professor_id")
        select_prof.click()

        # Obtém todas as opções disponíveis (exceto "Nenhum")
        opcoes = admin_page.get_by_role("option").all()
        professores = [op for op in opcoes if op.inner_text() != "Nenhum"]

        if professores:
            professores[0].click()
        else:
            # Sem professores cadastrados: fecha dropdown e prossegue sem vinculação
            admin_page.keyboard.press("Escape")

        salvar_e_confirmar(admin_page, "Turma Com Professor PW")


# ---------------------------------------------------------------------------
# Testes — Múltiplas turmas em sequência
# ---------------------------------------------------------------------------

class TestAdicionarMultiplasTurmas:
    """Testa cadastro de várias turmas seguidas na mesma sessão."""

    TURMAS = [
        ("Berçário I PW",    "0 a 1 ano",  "Manhã",    "2026"),
        ("Berçário II PW",   "1 a 2 anos", "Tarde",    "2026"),
        ("Maternal I PW",    "2 anos",     "Manhã",    "2026"),
        ("Maternal II PW",   "3 anos",     "Tarde",    "2026"),
        ("Pré I PW",         "4 anos",     "Integral", "2026"),
        ("Pré II PW",        "5 anos",     "Manhã",    "2026"),
    ]

    def test_cadastrar_multiplas_turmas(self, admin_page: Page):
        """Cadastra todas as turmas definidas em TURMAS e verifica a listagem."""
        ir_para_aba_admin(admin_page, "turmas")

        for nome, faixa, turno, ano in self.TURMAS:
            abrir_dialog_nova_turma(admin_page)
            preencher_turma(admin_page, nome=nome, faixa_etaria=faixa, turno=turno, ano_letivo=ano)
            salvar_e_confirmar(admin_page, nome)

        # Confirma que todas as turmas aparecem na tabela
        for nome, *_ in self.TURMAS:
            expect(admin_page.get_by_text(nome)).to_be_visible()

    def test_cadastrar_turmas_anos_diferentes(self, admin_page: Page):
        """Cria turmas para anos letivos diferentes."""
        ir_para_aba_admin(admin_page, "turmas")

        turmas_anos = [
            ("Turma 2025 PW", "3 anos", "Manhã", "2025"),
            ("Turma 2026 PW", "4 anos", "Tarde", "2026"),
        ]

        for nome, faixa, turno, ano in turmas_anos:
            abrir_dialog_nova_turma(admin_page)
            preencher_turma(admin_page, nome=nome, faixa_etaria=faixa, turno=turno, ano_letivo=ano)
            salvar_e_confirmar(admin_page, nome)

        for nome, *_ in turmas_anos:
            expect(admin_page.get_by_text(nome)).to_be_visible()


# ---------------------------------------------------------------------------
# Testes — Validação de campos obrigatórios
# ---------------------------------------------------------------------------

class TestValidacaoTurma:
    """Verifica que campos obrigatórios impedem envio do formulário."""

    def test_salvar_sem_nome_nao_fecha_dialog(self, admin_page: Page):
        ir_para_aba_admin(admin_page, "turmas")

        abrir_dialog_nova_turma(admin_page)

        # Preenche só faixa e turno, deixa nome vazio
        admin_page.locator("#faixa_etaria").fill("3 anos")
        selecionar_radix(admin_page, "turno", "Manhã")

        admin_page.get_by_role("button", name="Salvar").click()

        # Dialog deve permanecer aberto (validação HTML5)
        expect(admin_page.get_by_role("dialog")).to_be_visible()

    def test_salvar_sem_turno_nao_fecha_dialog(self, admin_page: Page):
        ir_para_aba_admin(admin_page, "turmas")

        abrir_dialog_nova_turma(admin_page)

        admin_page.locator("#nome").fill("Turma Sem Turno PW")
        admin_page.locator("#faixa_etaria").fill("3 anos")
        # Turno não selecionado

        admin_page.get_by_role("button", name="Salvar").click()

        expect(admin_page.get_by_role("dialog")).to_be_visible()
