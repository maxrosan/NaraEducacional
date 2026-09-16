"""
Teste de exatidão: as perguntas mostradas ao professor na aba "Guiado" devem ser
EXATAMENTE as perguntas do banco para a faixa etária da turma vinculada.
Nenhuma pergunta de outra faixa deveria aparecer.

Motivação técnica:
  • O frontend usa apiClient.ilike('faixa_etaria', '%Nível 4%'), que o apiClient
    traduz para ?faixa_etaria__icontains=Nível 4.
  • O backend (views_rest.listar_perguntas_bncc) lê request.GET.get('faixa_etaria')
    (exact match), não 'faixa_etaria__icontains'. Isso significa que o filtro pode
    não ser aplicado, e TODAS as perguntas de TODOS os níveis podem ser retornadas.
  • Este teste expõe esse comportamento verificando contagem e visibilidade exatas.

Estratégia de isolamento:
  • RUN_ID único por execução: zero perguntas pré-existentes contaminarão a contagem,
    pois os textos das perguntas contêm RUN_ID (hash aleatório de 8 hex chars).
  • São criadas exatamente 3 perguntas "Nível 4" + 1 pergunta "Nível 3" (decoy),
    todas com CAMPO_PADRAO = "Corpo, gestos e movimentos" e textos contendo RUN_ID.
  • A turma tem faixa_etaria = "Nível 4".
  • Esperado: professor vê exatamente 3 perguntas com RUN_ID. Decoy NÃO aparece.
  • Se o backend retornar todas as perguntas (sem filtrar por faixa), 4 aparecerão
    (decoy incluído) e o teste falhará — expondo o bug.

Por que não criar um campo exclusivo (CAMPO_UNICO) via UI?
  • O dialog de criação de campo customizado ("Criar novo Campo de Experiência") depende
    do endpoint POST /api/campos-experiencia/criar/, que pode falhar com erros de JSON/CSRF
    em alguns ambientes de staging, tornando o teste frágil.
  • Usar CAMPO_PADRAO (campo pré-existente da BNCC) + filtro por RUN_ID no texto das
    perguntas garante isolamento equivalente sem depender de criação de campo via UI.

Contagem:
  • Após expandir o AccordionItem de CAMPO_PADRAO, conta div.bg-lavanda-claro que
    contêm RUN_ID no texto (usando .filter(has_text=RUN_ID)) dentro do
    [role='region'][data-state='open'].
  • Se o backend filtrar corretamente: count = 3 (decoy excluído). ✓
  • Se o backend retornar todas as faixas: count = 4 (decoy incluído). ✗ Bug exposto.

Pré-requisitos:
  pytest tests/test_bncc_exatidao_guiado.py -v
"""

import re
import uuid

import pytest
from playwright.sync_api import Browser, Page, expect

from conftest import BASE_URL, fazer_login
from test_perguntas_bncc import (
    CAMPO_PADRAO,
    FAIXA_PADRAO,
    FAIXA_SECUNDARIA,
    criar_pergunta_bncc,
    criar_professor_e_capturar_senha,
    criar_turma_para_bncc,
)

# ---------------------------------------------------------------------------
# RUN_ID e constantes
# ---------------------------------------------------------------------------

RUN_ID = uuid.uuid4().hex[:8]

# 3 perguntas que DEVEM aparecer (faixa da turma = FAIXA_PADRAO = "Nível 4")
TEXTO_Q1 = f"Exatidão pergunta 1 nível 4 {RUN_ID}?"
TEXTO_Q2 = f"Exatidão pergunta 2 nível 4 {RUN_ID}?"
TEXTO_Q3 = f"Exatidão pergunta 3 nível 4 {RUN_ID}?"

# 1 pergunta DECOY: mesmo campo, faixa diferente → NÃO deve aparecer para turma Nível 4
TEXTO_DECOY = f"Exatidão decoy nível 3 {RUN_ID}?"

NOME_TURMA = f"Turma Exatidão {RUN_ID}"
NOME_PROFESSOR = f"Prof. Exatidão {RUN_ID}"
EMAIL_PROFESSOR = f"prof.exatidao.{RUN_ID}@teste.nara"

# Quantidade de perguntas com RUN_ID esperadas na aba Guiado para CAMPO_PADRAO
PERGUNTAS_ESPERADAS = 3


# ---------------------------------------------------------------------------
# Teste
# ---------------------------------------------------------------------------


class TestBnccExatidaoGuiado:
    """
    Verifica que o professor vê na aba Guiado EXATAMENTE as perguntas do banco
    correspondentes à faixa etária da sua turma — nem mais, nem menos.
    """

    def test_somente_perguntas_da_faixa_da_turma_aparecem(
        self, admin_page: Page, browser: Browser
    ) -> None:
        """
        Cenário:
          • CAMPO_PADRAO ("Corpo, gestos e movimentos"):
            3 perguntas "Nível 4" + 1 decoy "Nível 3", todas com RUN_ID no texto.
          • Turma tem faixa_etaria = "Nível 4".
          • Esperado: exatamente 3 cards com RUN_ID no accordion expandido.
          • Decoy "Nível 3" NÃO deve aparecer (não contém RUN_ID... espera, contém).

        A contagem usa .filter(has_text=RUN_ID) para isolar nossas perguntas das
        pré-existentes no banco. Se o backend retornar todas as faixas, o decoy
        (que também tem RUN_ID) aparecerá e a contagem será 4 → teste falha.
        """
        # ------------------------------------------------------------------ #
        # Captura de console JS e respostas de rede do admin (depuração)     #
        # ------------------------------------------------------------------ #
        admin_console: list[str] = []
        api_debug: list[str] = []

        def _on_admin_console(msg) -> None:
            nivel = msg.type.upper()
            fonte = ""
            try:
                loc = msg.location
                if loc and loc.get("url"):
                    fonte = f"  ← {loc['url']}:{loc.get('lineNumber', '?')}"
            except Exception:
                pass
            admin_console.append(f"[{nivel}] {msg.text}{fonte}")

        def _on_admin_pageerror(exc) -> None:
            admin_console.append(f"[PAGEERROR] {exc}")

        def _on_admin_response(resp) -> None:
            if "perguntas-bncc" in resp.url or "campos-experiencia" in resp.url:
                try:
                    body = resp.body().decode("utf-8", errors="replace")
                except Exception as exc:
                    body = f"<erro ao ler body: {exc}>"
                api_debug.append(
                    f"[{resp.status}] {resp.url}\n  Body: {body[:400]}"
                )

        admin_page.on("console", _on_admin_console)
        admin_page.on("pageerror", _on_admin_pageerror)
        admin_page.on("response", _on_admin_response)

        try:
            # -------------------------------------------------------------- #
            # Setup: turma                                                    #
            # -------------------------------------------------------------- #
            criar_turma_para_bncc(admin_page, NOME_TURMA, FAIXA_PADRAO)

            # -------------------------------------------------------------- #
            # Setup: perguntas no banco (todas em CAMPO_PADRAO, textos únicos #
            # via RUN_ID — isola nossas perguntas das pré-existentes)         #
            #                                                                  #
            # 3 perguntas Nível 4: devem aparecer para o professor             #
            # 1 decoy  Nível 3:   NÃO deve aparecer para turma Nível 4        #
            # -------------------------------------------------------------- #
            criar_pergunta_bncc(admin_page, CAMPO_PADRAO, FAIXA_PADRAO, TEXTO_Q1)
            criar_pergunta_bncc(admin_page, CAMPO_PADRAO, FAIXA_PADRAO, TEXTO_Q2)
            criar_pergunta_bncc(admin_page, CAMPO_PADRAO, FAIXA_PADRAO, TEXTO_Q3)
            criar_pergunta_bncc(admin_page, CAMPO_PADRAO, FAIXA_SECUNDARIA, TEXTO_DECOY)

            # -------------------------------------------------------------- #
            # Setup: professor vinculado à turma                              #
            # -------------------------------------------------------------- #
            senha = criar_professor_e_capturar_senha(
                admin_page, NOME_PROFESSOR, EMAIL_PROFESSOR, NOME_TURMA
            )

        finally:
            # Sempre imprime o debug do admin (visível com pytest -s ou em falhas)
            if admin_console:
                print("\n\n===== Console JS Admin (Chromium) =====")
                for linha in admin_console:
                    print(linha)
                print("=======================================\n")
            if api_debug:
                print("\n\n===== Respostas API Admin (/perguntas-bncc/, /campos-experiencia/) =====")
                for linha in api_debug:
                    print(linha)
                print("=======================================================================\n")

        # ------------------------------------------------------------------ #
        # Verificação: professor na aba Guiado                               #
        # ------------------------------------------------------------------ #
        with browser.new_context() as ctx:
            prof_page = ctx.new_page()

            # ---------------------------------------------------------------- #
            # Captura de console JS do professor para depuração.               #
            # Visível com `pytest -s`; em falhas o pytest exibe automaticamente #
            # ---------------------------------------------------------------- #
            js_console: list[str] = []

            def _on_console(msg) -> None:
                nivel = msg.type.upper()
                fonte = ""
                try:
                    loc = msg.location
                    if loc and loc.get("url"):
                        fonte = f"  ← {loc['url']}:{loc.get('lineNumber', '?')}"
                except Exception:
                    pass
                js_console.append(f"[{nivel}] {msg.text}{fonte}")

            def _on_pageerror(exc) -> None:
                js_console.append(f"[PAGEERROR] {exc}")

            prof_page.on("console", _on_console)
            prof_page.on("pageerror", _on_pageerror)

            try:
                fazer_login(prof_page, EMAIL_PROFESSOR, senha)

                # Navega para /registro para acionar redirect → /registro/{turmaId}
                prof_page.goto(f"{BASE_URL}/registro")
                prof_page.wait_for_url(
                    re.compile(r"/registro/[0-9a-f-]{36}$"), timeout=10_000
                )

                # Página carregada
                expect(prof_page.get_by_text("Tipo de registro")).to_be_visible(
                    timeout=8_000
                )

                # Seleciona explicitamente a aba Guiado
                prof_page.get_by_role("tab", name="Guiado").click()

                # Expande o accordion para CAMPO_PADRAO
                # campoExperienciaMap["Corpo, gestos e movimentos"].name = "Corpo, gestos e movimentos"
                prof_page.get_by_role("button", name=CAMPO_PADRAO).click()

                # ------------------------------------------------------------ #
                # Asserções de conteúdo: as 3 perguntas de FAIXA_PADRAO         #
                # devem estar visíveis; a decoy NÃO deve estar visível.         #
                # ------------------------------------------------------------ #
                expect(prof_page.get_by_text(TEXTO_Q1)).to_be_visible(timeout=8_000)
                expect(prof_page.get_by_text(TEXTO_Q2)).to_be_visible(timeout=8_000)
                expect(prof_page.get_by_text(TEXTO_Q3)).to_be_visible(timeout=8_000)
                expect(prof_page.get_by_text(TEXTO_DECOY)).not_to_be_visible()

                # ------------------------------------------------------------ #
                # Asserção de contagem: exatamente PERGUNTAS_ESPERADAS cards    #
                # com RUN_ID no accordion aberto.                               #
                #                                                               #
                # Filtramos por has_text=RUN_ID para isolar nossas perguntas    #
                # das pré-existentes no banco (que não têm RUN_ID no texto).    #
                #                                                               #
                # Se o backend não filtrar por faixa_etaria (bug), o decoy      #
                # (Nível 3, também com RUN_ID) aparece → count = 4 → falha.    #
                # ------------------------------------------------------------ #
                open_region = prof_page.locator(
                    "[role='region'][data-state='open']"
                )
                question_cards = open_region.locator("div.bg-lavanda-claro").filter(
                    has_text=RUN_ID
                )
                expect(question_cards).to_have_count(
                    PERGUNTAS_ESPERADAS, timeout=8_000
                )

            finally:
                if js_console:
                    print("\n\n===== Console JS Professor (Chromium) =====")
                    for linha in js_console:
                        print(linha)
                    print("===========================================\n")
