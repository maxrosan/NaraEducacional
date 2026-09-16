"""
Testes de UI para períodos avaliativos — professor, coordenador e administrador.

Estratégia: busca o período ativo via API (usando a sessão autenticada do browser)
e compara EXATAMENTE com o que aparece na interface de cada perfil.

Pré-requisitos:
  1. Frontend em NARA_BASE_URL (padrão http://localhost:5173)
  2. Backend rodando
  3. Credenciais configuradas em tests/.env
  4. Pelo menos um período avaliativo cadastrado com data_inicio <= hoje <= data_fim

Executar:
    pytest tests/test_periodos_avaliativos.py -v
"""

import json
from datetime import date

import pytest
from playwright.sync_api import Page, expect

from conftest import BASE_URL, ir_para_aba_admin


# ---------------------------------------------------------------------------
# Helper: busca períodos via API usando a sessão do browser
# ---------------------------------------------------------------------------

def buscar_periodo_ativo(page: Page) -> dict | None:
    """
    Faz GET /api/periodos-avaliativos/ com a sessão autenticada da página
    e retorna o período cujas datas cobrem hoje, ou None se não houver.
    """
    hoje = date.today().isoformat()
    api_url = f"/api/periodos-avaliativos/?data_inicio__lte={hoje}&data_fim__gte={hoje}&limit=1"

    resultado = page.evaluate(f"""async () => {{
        const resp = await fetch("{api_url}", {{
            credentials: "include",
            headers: {{ "Content-Type": "application/json" }}
        }});
        if (!resp.ok) return null;
        const data = await resp.json();
        return Array.isArray(data) ? data[0] ?? null : null;
    }}""")

    return resultado


def buscar_todos_periodos(page: Page) -> list:
    """Retorna todos os períodos cadastrados via API."""
    resultado = page.evaluate("""async () => {
        const resp = await fetch("/api/periodos-avaliativos/", {
            credentials: "include",
            headers: { "Content-Type": "application/json" }
        });
        if (!resp.ok) return [];
        const data = await resp.json();
        return Array.isArray(data) ? data : [];
    }""")

    return resultado or []


# ---------------------------------------------------------------------------
# Admin — aba Períodos
# ---------------------------------------------------------------------------

class TestAdminPeriodos:
    """Admin deve ver na tabela exatamente os períodos cadastrados na API."""

    def test_aba_periodos_acessivel(self, admin_page: Page):
        """A aba Períodos carrega sem erro."""
        ir_para_aba_admin(admin_page, "periodos")
        expect(admin_page.get_by_text("Períodos Avaliativos")).to_be_visible(timeout=10_000)

    def test_admin_ve_todos_os_periodos_cadastrados(self, admin_page: Page):
        """Cada período retornado pela API deve aparecer na tabela da UI."""
        ir_para_aba_admin(admin_page, "periodos")
        admin_page.wait_for_load_state("networkidle")

        periodos = buscar_todos_periodos(admin_page)
        assert len(periodos) > 0, (
            "Nenhum período encontrado na API. Cadastre ao menos um período antes de rodar os testes."
        )

        for periodo in periodos:
            descricao = periodo["descricao"]
            expect(admin_page.get_by_role("cell", name=descricao, exact=True)).to_be_visible(timeout=5_000), (
                f"Período '{descricao}' cadastrado na API não aparece na tabela do admin."
            )

    def test_admin_ve_periodo_ativo_na_tabela(self, admin_page: Page):
        """O período ativo (cobre hoje) deve estar visível na tabela."""
        ir_para_aba_admin(admin_page, "periodos")
        admin_page.wait_for_load_state("networkidle")

        periodo = buscar_periodo_ativo(admin_page)
        assert periodo is not None, (
            f"Nenhum período ativo para hoje ({date.today().isoformat()}) foi encontrado na API. "
            "Verifique as datas cadastradas."
        )

        descricao = periodo["descricao"]
        expect(admin_page.get_by_role("cell", name=descricao, exact=True)).to_be_visible(timeout=5_000)

    def test_admin_pode_abrir_formulario_novo_periodo(self, admin_page: Page):
        """Botão 'Novo Período' abre o formulário de cadastro."""
        ir_para_aba_admin(admin_page, "periodos")
        admin_page.wait_for_load_state("networkidle")

        admin_page.get_by_role("button", name="Novo Período").click()

        expect(admin_page.get_by_role("dialog")).to_be_visible(timeout=5_000)
        expect(admin_page.get_by_label("Descrição")).to_be_visible()
        expect(admin_page.get_by_label("Data de Início")).to_be_visible()
        expect(admin_page.get_by_label("Data de Fim")).to_be_visible()

        admin_page.get_by_role("button", name="Cancelar").click()


# ---------------------------------------------------------------------------
# Professor — badge de período na home
# ---------------------------------------------------------------------------

class TestProfessorPeriodo:
    """Professor deve ver no badge exatamente a descrição do período ativo cadastrado."""

    def test_professor_badge_exibe_descricao_exata_do_periodo(self, professor_page: Page):
        """
        Busca o período ativo na API e verifica que o badge exibe
        EXATAMENTE a mesma descrição — sem "undefined", "Período de Férias"
        ou qualquer outro texto incorreto.
        """
        professor_page.goto(f"{BASE_URL}/home-professor")
        professor_page.wait_for_load_state("networkidle")

        periodo = buscar_periodo_ativo(professor_page)
        assert periodo is not None, (
            f"Nenhum período ativo para hoje ({date.today().isoformat()}) foi encontrado na API. "
            "Verifique as datas cadastradas em /admin/periodos."
        )

        descricao_esperada = periodo["descricao"]

        badge = professor_page.locator("header div.rounded-full").first
        expect(badge).to_be_visible(timeout=8_000)

        texto_exibido = badge.inner_text().strip()
        assert texto_exibido == descricao_esperada, (
            f"Badge do professor exibe '{texto_exibido}', "
            f"mas o período cadastrado é '{descricao_esperada}'."
        )

    def test_professor_nao_ve_undefined(self, professor_page: Page):
        """Badge não pode exibir 'undefined' ou texto vazio."""
        professor_page.goto(f"{BASE_URL}/home-professor")
        professor_page.wait_for_load_state("networkidle")

        badge = professor_page.locator("header div.rounded-full").first
        expect(badge).to_be_visible(timeout=8_000)

        texto = badge.inner_text().strip()
        assert "undefined" not in texto.lower(), (
            f"Badge exibe '{texto}' — campo descricao não está sendo lido corretamente."
        )
        assert texto != "", "Badge de período está vazio."

    def test_professor_nao_ve_periodo_de_ferias(self, professor_page: Page):
        """Badge não deve mostrar 'Período de Férias' quando há um período ativo cadastrado."""
        professor_page.goto(f"{BASE_URL}/home-professor")
        professor_page.wait_for_load_state("networkidle")

        periodo = buscar_periodo_ativo(professor_page)
        if periodo is None:
            pytest.skip("Nenhum período ativo hoje — 'Período de Férias' seria o comportamento correto.")

        badge = professor_page.locator("header div.rounded-full").first
        expect(badge).to_be_visible(timeout=8_000)

        texto = badge.inner_text().strip()
        assert texto != "Período de Férias", (
            "Badge exibe 'Período de Férias' mesmo havendo um período ativo cadastrado. "
            f"Período esperado: '{periodo['descricao']}'."
        )


# ---------------------------------------------------------------------------
# Coordenador — aba Relatórios com seletor de períodos avaliativos
# ---------------------------------------------------------------------------

def ir_para_aba_relatorios(page: Page) -> None:
    """Navega para /coordenacao e clica na aba Relatórios."""
    page.goto(f"{BASE_URL}/coordenacao")
    page.wait_for_load_state("networkidle")
    page.get_by_role("button", name="Relatórios").click()
    page.wait_for_load_state("networkidle")


class TestCoordenadorPeriodo:
    """Coordenador deve ver os períodos avaliativos cadastrados no seletor da aba Relatórios."""

    def test_coordenacao_carrega(self, coordenador_page: Page):
        """Página /coordenacao carrega sem redirecionar para login."""
        coordenador_page.goto(f"{BASE_URL}/coordenacao")
        coordenador_page.wait_for_load_state("networkidle")

        assert "/login" not in coordenador_page.url, (
            f"Coordenador foi redirecionado para login. URL atual: {coordenador_page.url}"
        )

    def test_coordenador_ve_seletor_de_periodo_na_aba_relatorios(self, coordenador_page: Page):
        """O seletor de período existe e exibe 'Todos os Períodos' na aba Relatórios."""
        ir_para_aba_relatorios(coordenador_page)

        expect(coordenador_page.get_by_text("Todos os Períodos", exact=True)).to_be_visible(timeout=8_000)

    def test_coordenador_ve_todos_os_periodos_no_seletor(self, coordenador_page: Page):
        """
        Abre o dropdown de período e verifica que cada período cadastrado
        na API aparece como opção EXATAMENTE com sua descrição.
        """
        ir_para_aba_relatorios(coordenador_page)

        periodos = buscar_todos_periodos(coordenador_page)
        assert len(periodos) > 0, (
            "Nenhum período cadastrado na API. Cadastre ao menos um período em /admin/periodos."
        )

        # Abre o dropdown clicando no trigger do Select de período
        coordenador_page.get_by_text("Todos os Períodos", exact=True).click()

        for periodo in periodos:
            descricao = periodo["descricao"]
            expect(
                coordenador_page.get_by_role("option", name=descricao, exact=True)
            ).to_be_visible(timeout=5_000), (
                f"Período '{descricao}' cadastrado na API não aparece no seletor do coordenador."
            )

        # Fecha o dropdown
        coordenador_page.keyboard.press("Escape")

    def test_coordenador_ve_periodo_ativo_no_seletor(self, coordenador_page: Page):
        """
        O período ativo (que cobre hoje) deve aparecer como opção no seletor,
        com a descrição exata cadastrada pelo admin.
        """
        ir_para_aba_relatorios(coordenador_page)

        periodo = buscar_periodo_ativo(coordenador_page)
        if periodo is None:
            pytest.skip(f"Nenhum período ativo para hoje ({date.today().isoformat()}).")

        descricao = periodo["descricao"]

        coordenador_page.get_by_text("Todos os Períodos", exact=True).click()

        expect(
            coordenador_page.get_by_role("option", name=descricao, exact=True)
        ).to_be_visible(timeout=5_000), (
            f"Período ativo '{descricao}' não aparece no seletor da aba Relatórios."
        )

        coordenador_page.keyboard.press("Escape")
