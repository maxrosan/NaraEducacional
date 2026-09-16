"""
Teste focado: pergunta BNCC criada pelo admin aparece na aba "Guiado" para o professor.

Cobre apenas o caminho crítico:
  1. Admin cria turma com faixa_etaria = "Nível 4".
  2. Admin cria pergunta BNCC com faixa_etaria = "Nível 4"
     e campo = "Corpo, gestos e movimentos".
  3. Admin cria professor vinculado à turma.
  4. Professor faz login → redirecionado automaticamente para /registro/{turmaId}.
  5. Professor clica explicitamente na aba "Guiado".
  6. Professor expande o accordion do campo de experiência.
  7. A pergunta criada pelo admin está visível.

Por que este teste existe separado de test_perguntas_bncc.py?
  • test_perguntas_bncc.py mistura CRUD, filtros, integração e submissão.
    Este arquivo testa apenas a visibilidade da pergunta na aba Guiado,
    tornando a falha mais rápida de diagnosticar.

Detalhes de implementação:
  • RUN_ID único por execução garante dados frescos sem conflito com runs anteriores.
  • A faixa_etaria da turma deve ser "Nível 4" (texto livre, não Select) para que
    fetchQuestionsByFaixaEtaria encontre as perguntas via ILIKE %4%.
  • Após login o professor vai para /home-professor; é necessário navegar para /registro
    para acionar o redirect automático para /registro/{turmaId} (1 turma vinculada).
  • TabsTrigger renderiza "⇡ Guiado"; get_by_role("tab", name="Guiado") usa substring
    match no accessible name — o emoji não precisa ser incluído.
  • O accordion do campo inicia fechado (defaultValue=[]) na visão do professor;
    é necessário clicar no AccordionTrigger para expandir.

Pré-requisitos:
  1. Frontend rodando em NARA_BASE_URL
  2. Backend rodando em http://localhost:8001
  3. Admin configurado em tests/.env
  4. venv ativado com dependências instaladas
  5. Executar: pytest tests/test_pergunta_bncc_guiado.py -v
"""

import re
import uuid

import pytest
from playwright.sync_api import Browser, Page, expect

from conftest import BASE_URL, fazer_login, ir_para_aba_admin, selecionar_radix
from test_perguntas_bncc import (
    CAMPO_PADRAO,
    FAIXA_PADRAO,
    criar_pergunta_bncc,
    criar_professor_e_capturar_senha,
    criar_turma_para_bncc,
    ir_para_pagina_bncc,
)

# ---------------------------------------------------------------------------
# RUN_ID — sufixo único para dados criados nesta execução
# ---------------------------------------------------------------------------

RUN_ID = uuid.uuid4().hex[:8]

NOME_TURMA = f"Turma Guiado Visib {RUN_ID}"
NOME_PROFESSOR = f"Prof. Guiado Visib {RUN_ID}"
EMAIL_PROFESSOR = f"prof.guiado.visib.{RUN_ID}@teste.nara"
TEXTO_PERGUNTA = f"A criança demonstra equilíbrio ao caminhar (guiado visib) {RUN_ID}?"


# ---------------------------------------------------------------------------
# Teste
# ---------------------------------------------------------------------------


class TestPerguntaBnccApareceTelaProfessor:
    """
    Verifica que uma pergunta BNCC cadastrada pelo admin é visível
    na aba Guiado da tela de registro do professor.
    """

    def test_pergunta_bncc_aparece_na_aba_guiado(
        self, admin_page: Page, browser: Browser
    ) -> None:
        """
        Passos:
          1. Admin cria turma "Nível 4".
          2. Admin cria pergunta BNCC "Nível 4" / "Corpo, gestos e movimentos".
          3. Admin cria professor vinculado à turma.
          4. Professor faz login → redirecionado para /registro/{turmaId}.
          5. Professor clica na aba "Guiado".
          6. Professor expande o accordion do campo.
          7. A pergunta está visível.
        """
        # ------------------------------------------------------------------ #
        # Passo 1 — Turma                                                     #
        # faixa_etaria é campo texto livre; deve conter "4" para que          #
        # fetchQuestionsByFaixaEtaria encontre perguntas "Nível 4" via ILIKE. #
        # ------------------------------------------------------------------ #
        criar_turma_para_bncc(admin_page, NOME_TURMA, FAIXA_PADRAO)

        # ------------------------------------------------------------------ #
        # Passo 2 — Pergunta BNCC                                             #
        # ------------------------------------------------------------------ #
        criar_pergunta_bncc(admin_page, CAMPO_PADRAO, FAIXA_PADRAO, TEXTO_PERGUNTA)

        # ------------------------------------------------------------------ #
        # Passo 3 — Professor vinculado à turma                               #
        # ------------------------------------------------------------------ #
        senha = criar_professor_e_capturar_senha(
            admin_page, NOME_PROFESSOR, EMAIL_PROFESSOR, NOME_TURMA
        )

        # ------------------------------------------------------------------ #
        # Passos 4-7 — Professor verifica a aba Guiado em contexto isolado    #
        # ------------------------------------------------------------------ #
        with browser.new_context() as ctx:
            prof_page = ctx.new_page()
            fazer_login(prof_page, EMAIL_PROFESSOR, senha)

            # Após login o professor vai para /home-professor.
            # Navegar para /registro aciona o redirect automático
            # para /registro/{turmaId} quando há exatamente 1 turma vinculada.
            prof_page.goto(f"{BASE_URL}/registro")
            prof_page.wait_for_url(
                re.compile(r"/registro/[0-9a-f-]{36}$"), timeout=10_000
            )

            # Passo 4 — Página de registro carregada com a turma
            expect(prof_page.get_by_text("Tipo de registro")).to_be_visible(
                timeout=8_000
            )

            # Passo 5 — Seleciona explicitamente a aba "Guiado"
            # O trigger renderiza "⇡ Guiado"; name faz substring match.
            prof_page.get_by_role("tab", name="Guiado").click()

            # Passo 6 — Expande o accordion do campo de experiência
            # GuidedObservationContent: accordion inicia fechado (defaultValue=[])
            prof_page.get_by_role("button", name=CAMPO_PADRAO).click()

            # Passo 7 — A pergunta deve estar visível no conteúdo expandido
            expect(prof_page.get_by_text(TEXTO_PERGUNTA)).to_be_visible(
                timeout=8_000
            )
