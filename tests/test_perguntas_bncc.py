"""
Testes visuais (Playwright) — Perguntas BNCC: CRUD no admin e fluxo do professor.

Cobre os cenários:
  1. CRUD completo de perguntas no painel admin (/admin/perguntas-bncc):
     - Criar pergunta → aparece na listagem
     - Editar pergunta → texto atualizado na listagem
     - Excluir pergunta → removida da listagem
     - Validação: campos obrigatórios mantêm o dialog aberto

  2. Filtros na listagem admin:
     - Filtrar por Nível/Faixa Etária exibe apenas perguntas do nível selecionado
     - Filtrar por Campo de Experiência exibe apenas perguntas do campo selecionado

  3. Integração: admin cria pergunta → professor a vê em /registro
     - Admin cria turma com faixa "Nível 4" e pergunta com "Nível 4"
     - Admin cria professor vinculado à turma
     - Professor faz login → é redirecionado para /registro/{turmaId}
     - A pergunta aparece no accordeon após expandir o campo

  4. Professor preenche e submete observação guiada:
     - Admin cria aluno na turma
     - Professor abre o accordeon do campo, marca checkbox do aluno
     - Clica em "Salvar Observação" → toast de sucesso

Detalhes de implementação:
  • RUN_ID (uuid hex de 8 chars) é gerado uma vez por execução e sufixado em todos
    os textos de perguntas, nomes e emails. Isso evita conflito com dados de runs
    anteriores (o banco não tem unique constraint no texto da pergunta).
  • CreatableCampoSelect é um dropdown customizado (NÃO é Radix Select).
    Trigger: div com texto "Selecione ou digite um Campo de Experiência"
    Busca: input com placeholder "Buscar ou criar novo campo..."
    Opções: dentro de <div class="py-1">, cada opção é <span>{campo}</span>
  • Faixa etária no dialog NovaPerguntaForm: Radix Select (SelectTrigger = combobox)
    único combobox no dialog, sem id explícito.
  • Accordion no admin: defaultValue = todos os campos (todos expandidos após fetch).
  • Accordion no professor (GuidedObservationContent): defaultValue = [] (todos fechados).
  • Tab "Guiado": TabsTrigger renderiza como "⇡ Guiado"; get_by_role("tab", name="Guiado")
    faz substring match no accessible name — sem necessidade do emoji.
  • Senha do professor capturada do campo #password (type="text") antes de salvar.
  • getShortName("Aluno BNCC {RUN_ID}") → "Aluno BNCC" (primeiras 2 palavras).

Pré-requisitos para rodar:
  1. Frontend rodando em NARA_BASE_URL (padrão: http://localhost:5173)
  2. Backend rodando em http://localhost:8001
  3. Usuário admin configurado em tests/.env (NARA_ADMIN_EMAIL / NARA_ADMIN_PASSWORD)
  4. venv ativado e dependências instaladas:
       pip install -r tests/requirements.txt
       playwright install chromium
  5. Executar:
       pytest tests/test_perguntas_bncc.py -v
"""

import re
import uuid

import pytest
from playwright.sync_api import Browser, Page, expect

from conftest import BASE_URL, fazer_login, ir_para_aba_admin, selecionar_radix
from test_turma_visibilidade import criar_usuario_e_capturar_senha

# ---------------------------------------------------------------------------
# RUN_ID — sufixo único por execução para evitar conflito com dados de runs
# anteriores (o banco não tem unique constraint no texto da pergunta, portanto
# re-executar o teste sem RUN_ID cria duplicatas que quebram as asserções).
# ---------------------------------------------------------------------------

RUN_ID = uuid.uuid4().hex[:8]

# ---------------------------------------------------------------------------
# Constantes — campos/faixas são padrão BNCC (sem sufixo); textos e entidades
# recebem RUN_ID para serem únicos a cada execução.
# ---------------------------------------------------------------------------

CAMPO_PADRAO = "Corpo, gestos e movimentos"
CAMPO_SECUNDARIO = "O eu, o outro e o nós"
FAIXA_PADRAO = "Nível 4"
FAIXA_SECUNDARIA = "Nível 3"

# CRUD
TEXTO_CRIAR = f"A criança equilibra-se sobre um pé (criar) {RUN_ID}?"
TEXTO_EDITAR_ORIGINAL = f"A criança equilibra-se sobre um pé (editar) {RUN_ID}?"
TEXTO_EDITAR_NOVO = f"A criança equilibra-se sobre um pé (editado) {RUN_ID}?"
TEXTO_DELETAR = f"A criança rola objetos ao chão (deletar) {RUN_ID}?"

# Filtro
TEXTO_FILTRO_NIVEL4 = f"A criança pula em dois pés (Nível 4 filtro) {RUN_ID}?"
TEXTO_FILTRO_NIVEL3 = f"A criança rasteja em superfícies (Nível 3 filtro) {RUN_ID}?"
TEXTO_FILTRO_CORPO = f"A criança movimenta os braços livremente (campo Corpo) {RUN_ID}?"
TEXTO_FILTRO_EU = f"A criança nomeia colegas pelo nome (campo Eu) {RUN_ID}?"

# Integração: admin cria pergunta → professor vê em /registro
NOME_TURMA_INTEG = f"Turma BNCC Integ {RUN_ID}"
NOME_PROFESSOR_INTEG = f"Prof. BNCC Integ {RUN_ID}"
EMAIL_PROFESSOR_INTEG = f"prof.bncc.integ.{RUN_ID}@teste.nara"
TEXTO_INTEGRACAO = f"A criança demonstra coordenação motora fina (integ) {RUN_ID}?"

# Submissão: professor preenche observação
NOME_TURMA_SUBMIT = f"Turma BNCC Submit {RUN_ID}"
NOME_PROFESSOR_SUBMIT = f"Prof. BNCC Submit {RUN_ID}"
EMAIL_PROFESSOR_SUBMIT = f"prof.bncc.submit.{RUN_ID}@teste.nara"
NOME_ALUNO_SUBMIT = f"Aluno BNCC {RUN_ID}"
TEXTO_SUBMISSAO = f"A criança equilibra-se ao saltar (submit) {RUN_ID}?"


# ---------------------------------------------------------------------------
# Helpers locais
# ---------------------------------------------------------------------------


def ir_para_pagina_bncc(page: Page) -> None:
    """Navega para /admin/perguntas-bncc e aguarda carregamento."""
    page.goto(f"{BASE_URL}/admin/perguntas-bncc", timeout=60_000)
    page.wait_for_load_state("networkidle", timeout=60_000)


def abrir_dialog_nova_pergunta(page: Page) -> None:
    """Clica no botão 'Nova Pergunta' e aguarda o dialog abrir."""
    page.get_by_role("button", name=re.compile(r"Nova Pergunta", re.IGNORECASE)).click()
    expect(page.get_by_role("dialog")).to_be_visible(timeout=5_000)


def selecionar_campo_experiencia(page: Page, campo: str) -> None:
    """
    Seleciona um Campo de Experiência no CreatableCampoSelect (dropdown customizado).

    O trigger é um div (não um combobox Radix). Após clicar, aparece um input de busca
    e a lista de opções dentro de div.py-1. Cada opção é renderizada como <span>{campo}</span>.
    """
    # Clica no trigger (mostra "Selecione ou digite um Campo de Experiência" quando vazio,
    # ou o valor atual quando já selecionado)
    page.get_by_text("Selecione ou digite um Campo de Experiência").click()

    # Digita no campo de busca para filtrar as opções
    page.get_by_placeholder("Buscar ou criar novo campo...").fill(campo)

    # Clica na opção com o texto exato do campo dentro do container .py-1
    page.locator(".py-1").get_by_text(campo, exact=True).click()


def selecionar_faixa_etaria_dialog(page: Page, faixa: str) -> None:
    """
    Seleciona a faixa etária no dialog de criação/edição de pergunta.

    Usa o único button[role='combobox'] dentro do dialog aberto
    (o CreatableCampoSelect usa um div, não um combobox, portanto não há conflito).
    """
    dialog = page.get_by_role("dialog")
    dialog.locator("button[role='combobox']").click()
    page.get_by_role("option", name=faixa, exact=True).click()


def preencher_nova_pergunta(page: Page, campo: str, faixa: str, texto: str) -> None:
    """Preenche os campos obrigatórios do formulário de nova pergunta."""
    selecionar_campo_experiencia(page, campo)
    selecionar_faixa_etaria_dialog(page, faixa)
    page.locator("#pergunta").fill(texto)


def salvar_e_confirmar_pergunta(page: Page, texto: str) -> None:
    """Clica em 'Salvar Pergunta', aguarda o dialog fechar e verifica o texto na listagem."""
    page.get_by_role("button", name="Salvar Pergunta").click()
    expect(page.get_by_role("dialog")).to_be_hidden(timeout=8_000)
    expect(page.get_by_text(texto)).to_be_visible(timeout=8_000)


def criar_pergunta_bncc(
    page: Page, campo: str, faixa: str, texto: str
) -> None:
    """Cria uma pergunta BNCC completa: abre dialog → preenche → salva."""
    ir_para_pagina_bncc(page)
    abrir_dialog_nova_pergunta(page)
    preencher_nova_pergunta(page, campo, faixa, texto)
    salvar_e_confirmar_pergunta(page, texto)


def _localizar_card_pergunta(page: Page, texto: str):
    """
    Retorna o locator do card da pergunta que contém exatamente o texto informado.

    A estrutura de cada card é:
      <div class="p-4 bg-gray-50 rounded-lg border ...">
        <p class="font-semibold text-gray-800">{pergunta}</p>
        <button title="Editar">...</button>
        <button title="Excluir">...</button>
      </div>

    Usa .last para obter o elemento mais interno que satisfaz ambos os filtros.
    """
    return (
        page.locator("div")
        .filter(has=page.get_by_text(texto, exact=True))
        .filter(has=page.locator("button[title='Editar']"))
        .last
    )


def clicar_editar_pergunta(page: Page, texto: str) -> None:
    """Abre o dialog de edição da pergunta que contém o texto informado."""
    card = _localizar_card_pergunta(page, texto)
    card.locator("button[title='Editar']").click()
    expect(page.get_by_role("dialog")).to_be_visible(timeout=5_000)


def clicar_excluir_pergunta(page: Page, texto: str) -> None:
    """Clica no botão de exclusão e confirma no dialog de confirmação."""
    card = _localizar_card_pergunta(page, texto)
    card.locator("button[title='Excluir']").click()

    # Dialog de confirmação: "Confirmar Exclusão" com botão "Excluir" destrutivo
    confirm_dialog = page.get_by_role("dialog")
    expect(confirm_dialog).to_be_visible(timeout=5_000)
    confirm_dialog.get_by_role("button", name="Excluir").click()
    expect(confirm_dialog).to_be_hidden(timeout=8_000)


def criar_turma_para_bncc(page: Page, nome: str, faixa: str) -> None:
    """
    Cria uma turma via painel admin com a faixa etária como texto livre
    (campo #faixa_etaria no formulário de turma).

    O campo faixa_etaria da turma é um input de texto (não Radix Select),
    portanto deve conter a string exata usada nas perguntas BNCC, ex: "Nível 4".
    Isso garante que fetchQuestionsByFaixaEtaria encontre as perguntas via ILIKE.
    """
    ir_para_aba_admin(page, "turmas")
    page.get_by_role("button", name=re.compile(r"Nova Turma", re.IGNORECASE)).click()
    expect(page.get_by_role("dialog")).to_be_visible(timeout=5_000)

    page.locator("#nome").fill(nome)
    page.locator("#faixa_etaria").fill(faixa)
    selecionar_radix(page, "turno", "Manhã")

    page.get_by_role("button", name="Salvar").click()
    expect(page.get_by_role("dialog")).to_be_hidden(timeout=8_000)
    expect(page.get_by_text(nome)).to_be_visible(timeout=8_000)


def criar_professor_e_capturar_senha(
    page: Page, nome: str, email: str, nome_turma: str
) -> str:
    """
    Cria um usuário com perfil Professor, vincula à turma informada
    e retorna a senha gerada automaticamente.
    """
    return criar_usuario_e_capturar_senha(
        page,
        nome=nome,
        email=email,
        perfil_label="Professor",
        nome_turma=nome_turma,
    )


def criar_aluno_na_turma(
    page: Page, nome_aluno: str, nome_turma: str
) -> None:
    """
    Cadastra um aluno via painel admin (/admin/alunos) e o vincula à turma.

    Fluxo:
      1. Navega para /admin/alunos
      2. Abre o dialog "Cadastrar Novo Aluno"
      3. Preenche: nome_completo, data (clica no dia 15 do mês atual),
                   nome_responsavel, telefone, turma
      4. Submete e verifica que o aluno aparece na listagem

    Notas de implementação:
      • O Popover do calendário não fecha automaticamente ao selecionar uma data.
        Pressionar Escape fecha apenas o Popover (camada Radix mais interna),
        mantendo o Dialog principal aberto.
      • Após o Escape, o Popover permanece no DOM com role="dialog" e
        data-state="closed". Por isso o dialog principal é localizado pelo nome
        (aria-labelledby = "Cadastrar Novo Aluno") — get_by_role("dialog") sem
        qualificação resolveria para 2 elementos e causaria violação de strict mode.
      • O SelectTrigger da turma NÃO tem id explícito no StudentFormDialog.
        Após fechar o calendário, é o único button[role='combobox'] dentro do dialog.
      • O botão submit é buscado com main_dialog.get_by_role("button", name="Cadastrar Aluno")
        para evitar confusão com o trigger externo "Cadastrar Novo Aluno" (que contém
        "Cadastrar Aluno" como substring no match do Playwright).
      • O telefone usa IMask "(00) 00000-0000"; fill() dispara um único evento `input`
        que o hook useIMask processa corretamente para atualizar phoneValue (React state
        lido pelo handleSubmit). type() pode ter race condition com o estado React.
    """
    ir_para_aba_admin(page, "alunos")

    page.get_by_role(
        "button", name=re.compile(r"Cadastrar Novo Aluno", re.IGNORECASE)
    ).click()

    # Qualifica o dialog pelo nome (aria-labelledby) para evitar conflito com
    # o Popover do calendário, que também tem role="dialog" e pode permanecer
    # no DOM com data-state="closed" após ser fechado.
    main_dialog = page.get_by_role("dialog", name="Cadastrar Novo Aluno")
    expect(main_dialog).to_be_visible(timeout=5_000)

    # Nome completo
    page.locator("#nome_completo").fill(nome_aluno)

    # Data de nascimento: abre popover e clica no dia 15 do mês visível
    page.get_by_role("button", name=re.compile(r"Selecione a data", re.IGNORECASE)).click()
    page.get_by_role("gridcell", name="15").first.click()

    # Fecha o Popover do calendário via Escape.
    # Radix fecha apenas a camada mais interna (o Popover), mantendo o Dialog aberto.
    # Após o Escape, o Popover (role="dialog", data-state="closed") ainda fica no DOM,
    # por isso usamos o locator qualificado pelo nome do dialog principal.
    page.keyboard.press("Escape")
    expect(main_dialog).to_be_visible(timeout=2_000)

    # Nome do responsável
    page.locator("#nome_responsavel").fill("Responsável BNCC PW")

    # Telefone com máscara IMask "(00) 00000-0000".
    # fill() dispara um único evento `input` com o valor completo — mais confiável
    # que type() (que envia teclas individuais) para garantir que o hook useIMask
    # atualize phoneValue antes de o handleSubmit ler a validação.
    phone_input = page.locator("#telefone_responsavel")
    phone_input.fill("11999990000")
    # Aguarda o IMask processar o valor e atualizar o estado React
    expect(phone_input).not_to_be_empty()

    # Turma — SelectTrigger sem id; após fechar o calendário é o único combobox no dialog
    main_dialog.locator("button[role='combobox']").click()
    page.get_by_role("option", name=nome_turma, exact=True).click()

    # Submete — escopa ao main_dialog para não confundir com "Cadastrar Novo Aluno"
    # (que contém "Cadastrar Aluno" como substring e está no DOM fora do dialog)
    main_dialog.get_by_role("button", name="Cadastrar Aluno").click()
    expect(main_dialog).to_be_hidden(timeout=15_000)
    expect(page.get_by_text(nome_aluno)).to_be_visible(timeout=8_000)


# ---------------------------------------------------------------------------
# TestCrudPerguntaBNCC
# ---------------------------------------------------------------------------


class TestCrudPerguntaBNCC:
    """
    CRUD completo de perguntas BNCC no painel admin.
    Cada método usa um texto único para não interferir nos demais testes.
    """

    def test_criar_pergunta_aparece_na_listagem(self, admin_page: Page) -> None:
        """Admin cria uma pergunta; ela deve aparecer na listagem do accordeon."""
        criar_pergunta_bncc(admin_page, CAMPO_PADRAO, FAIXA_PADRAO, TEXTO_CRIAR)

    def test_editar_pergunta_atualiza_texto(self, admin_page: Page) -> None:
        """Admin cria e edita uma pergunta; o texto novo deve aparecer na listagem."""
        # Garante que a pergunta original existe
        criar_pergunta_bncc(admin_page, CAMPO_PADRAO, FAIXA_PADRAO, TEXTO_EDITAR_ORIGINAL)

        # Abre o dialog de edição
        clicar_editar_pergunta(admin_page, TEXTO_EDITAR_ORIGINAL)

        # Altera o texto da pergunta no textarea (sem id na edição)
        dialog = admin_page.get_by_role("dialog")
        textarea = dialog.locator("textarea").first
        textarea.clear()
        textarea.fill(TEXTO_EDITAR_NOVO)

        # Salva as alterações
        admin_page.get_by_role("button", name="Salvar Alterações").click()
        expect(dialog).to_be_hidden(timeout=8_000)

        # Novo texto deve aparecer; texto antigo não deve mais aparecer
        expect(admin_page.get_by_text(TEXTO_EDITAR_NOVO)).to_be_visible(timeout=8_000)
        expect(admin_page.get_by_text(TEXTO_EDITAR_ORIGINAL)).not_to_be_visible()

    def test_deletar_pergunta_remove_da_listagem(self, admin_page: Page) -> None:
        """Admin cria e exclui uma pergunta; ela deve sumir da listagem."""
        criar_pergunta_bncc(admin_page, CAMPO_PADRAO, FAIXA_PADRAO, TEXTO_DELETAR)

        # Exclui com confirmação
        clicar_excluir_pergunta(admin_page, TEXTO_DELETAR)

        # Texto não deve mais estar visível na página
        expect(admin_page.get_by_text(TEXTO_DELETAR)).not_to_be_visible(timeout=8_000)

    def test_validacao_campos_obrigatorios_mantem_dialog(self, admin_page: Page) -> None:
        """Tentar salvar sem preencher os campos obrigatórios mantém o dialog aberto."""
        ir_para_pagina_bncc(admin_page)
        abrir_dialog_nova_pergunta(admin_page)

        # Não preenche nenhum campo — apenas clica em Salvar
        admin_page.get_by_role("button", name="Salvar Pergunta").click()

        # O dialog deve continuar aberto (validação interna exibe toast de erro)
        expect(admin_page.get_by_role("dialog")).to_be_visible(timeout=3_000)


# ---------------------------------------------------------------------------
# TestFiltroPerguntaBNCC
# ---------------------------------------------------------------------------


class TestFiltroPerguntaBNCC:
    """
    Testa os filtros de Nível/Faixa Etária e Campo de Experiência na listagem admin.

    Lógica de filtro no frontend:
      - nivelFilter: p.faixa_etaria.includes(nivelFilter.replace('Nível ', ''))
        Ex.: "Nível 4" → verifica se faixa_etaria inclui "4"
      - campoFilter: p.campo_experiencia === campoFilter (igualdade exata)
    """

    def test_filtrar_por_faixa_etaria_exibe_apenas_nivel_correto(
        self, admin_page: Page
    ) -> None:
        """
        Cria uma pergunta Nível 4 e uma Nível 3; aplica filtro Nível 4 e verifica
        que apenas a pergunta de Nível 4 fica visível.
        """
        # Cria as duas perguntas
        criar_pergunta_bncc(admin_page, CAMPO_PADRAO, FAIXA_PADRAO, TEXTO_FILTRO_NIVEL4)
        criar_pergunta_bncc(admin_page, CAMPO_PADRAO, FAIXA_SECUNDARIA, TEXTO_FILTRO_NIVEL3)

        # Volta à página (já está nela após criar)
        ir_para_pagina_bncc(admin_page)

        # Aplica o filtro de Nível 4 — SelectTrigger com placeholder "Filtrar por Nível/Faixa Etária"
        admin_page.locator(
            "button[role='combobox']"
        ).filter(has_text=re.compile(r"Filtrar por Nível", re.IGNORECASE)).click()
        admin_page.get_by_role("option", name=FAIXA_PADRAO, exact=True).click()

        # Pergunta de Nível 4 deve estar visível; Nível 3 não
        expect(admin_page.get_by_text(TEXTO_FILTRO_NIVEL4)).to_be_visible(timeout=8_000)
        expect(admin_page.get_by_text(TEXTO_FILTRO_NIVEL3)).not_to_be_visible()

    def test_filtrar_por_campo_experiencia_exibe_apenas_campo_correto(
        self, admin_page: Page
    ) -> None:
        """
        Cria uma pergunta em 'Corpo, gestos e movimentos' e outra em 'O eu, o outro e o nós';
        aplica filtro de campo e verifica que apenas o campo selecionado aparece.
        """
        # Cria as duas perguntas em campos distintos
        criar_pergunta_bncc(admin_page, CAMPO_PADRAO, FAIXA_PADRAO, TEXTO_FILTRO_CORPO)
        criar_pergunta_bncc(admin_page, CAMPO_SECUNDARIO, FAIXA_PADRAO, TEXTO_FILTRO_EU)

        ir_para_pagina_bncc(admin_page)

        # Aplica filtro por CAMPO_PADRAO
        # O SelectItem exibe campoExperienciaMap[campo]?.name || campo — para os campos padrão,
        # o nome no mapa é igual ao próprio campo, portanto podemos usar o texto exato.
        admin_page.locator(
            "button[role='combobox']"
        ).filter(has_text=re.compile(r"Filtrar por Campo", re.IGNORECASE)).click()
        admin_page.get_by_role("option", name=CAMPO_PADRAO, exact=True).click()

        # Pergunta do campo filtrado deve aparecer; do outro não
        expect(admin_page.get_by_text(TEXTO_FILTRO_CORPO)).to_be_visible(timeout=8_000)
        expect(admin_page.get_by_text(TEXTO_FILTRO_EU)).not_to_be_visible()


# ---------------------------------------------------------------------------
# TestIntegracaoBNCC
# ---------------------------------------------------------------------------


class TestIntegracaoBNCC:
    """
    Fluxo de integração: admin cria pergunta BNCC e turma com mesma faixa etária;
    professor faz login e encontra a pergunta ao abrir o accordeon do campo.
    """

    def test_admin_cria_pergunta_professor_ve_em_registro(
        self, admin_page: Page, browser: Browser
    ) -> None:
        """
        Passos:
          1. Admin cria turma com faixa_etaria = "Nível 4".
          2. Admin cria pergunta BNCC com faixa_etaria = "Nível 4".
          3. Admin cria professor vinculado à turma.
          4. Professor faz login → redirecionado para /registro/{turmaId}.
          5. Abre o accordeon do campo → a pergunta está visível.
        """
        # Passo 1 — Cria a turma com faixa etária "Nível 4"
        criar_turma_para_bncc(admin_page, NOME_TURMA_INTEG, FAIXA_PADRAO)

        # Passo 2 — Cria a pergunta BNCC
        criar_pergunta_bncc(admin_page, CAMPO_PADRAO, FAIXA_PADRAO, TEXTO_INTEGRACAO)

        # Passo 3 — Cria o professor e o vincula à turma
        senha_professor = criar_professor_e_capturar_senha(
            admin_page, NOME_PROFESSOR_INTEG, EMAIL_PROFESSOR_INTEG, NOME_TURMA_INTEG
        )

        # Passo 4 — Professor faz login em contexto isolado
        with browser.new_context() as ctx:
            prof_page = ctx.new_page()
            fazer_login(prof_page, EMAIL_PROFESSOR_INTEG, senha_professor)

            # Após login o professor vai para /home-professor; navega para /registro
            # para acionar o redirecionamento automático para /registro/{turmaId}
            prof_page.goto(f"{BASE_URL}/registro")
            prof_page.wait_for_url(
                re.compile(r"/registro/[0-9a-f-]{36}$"), timeout=10_000
            )

            # Passo 5 — Seleciona explicitamente a aba "Guiado" e verifica a pergunta
            # O Step "Tipo de registro" sinaliza que a página carregou com a turma
            expect(prof_page.get_by_text("Tipo de registro")).to_be_visible(timeout=8_000)

            # TabsTrigger value="guiado" renderiza como "⇡ Guiado".
            # get_by_role("tab", name="Guiado") faz substring match no accessible name.
            prof_page.get_by_role("tab", name="Guiado").click()

            # Clica no AccordionTrigger do campo para expandir o conteúdo guiado
            prof_page.get_by_role("button", name=CAMPO_PADRAO).click()

            # A pergunta deve aparecer no conteúdo expandido da aba Guiado
            expect(
                prof_page.get_by_text(TEXTO_INTEGRACAO)
            ).to_be_visible(timeout=8_000)


# ---------------------------------------------------------------------------
# TestProfessorPreencheObservacao
# ---------------------------------------------------------------------------


class TestProfessorPreencheObservacao:
    """
    Fluxo completo: professor seleciona um aluno numa pergunta guiada e submete.
    Verifica que o toast de sucesso é exibido após "Salvar Observação".
    """

    def test_professor_seleciona_aluno_e_submete_observacao(
        self, admin_page: Page, browser: Browser
    ) -> None:
        """
        Passos:
          1. Admin cria turma com faixa "Nível 4".
          2. Admin cria pergunta BNCC com faixa "Nível 4".
          3. Admin cria professor vinculado à turma.
          4. Admin cadastra aluno na turma.
          5. Professor faz login → /registro/{turmaId}.
          6. Expande o accordeon do campo.
          7. Marca o checkbox do aluno na pergunta.
          8. Clica em "Salvar Observação".
          9. Toast "✅ Registro salvo com sucesso!" aparece.
        """
        # Passo 1 — Turma
        criar_turma_para_bncc(admin_page, NOME_TURMA_SUBMIT, FAIXA_PADRAO)

        # Passo 2 — Pergunta BNCC
        criar_pergunta_bncc(admin_page, CAMPO_PADRAO, FAIXA_PADRAO, TEXTO_SUBMISSAO)

        # Passo 3 — Professor
        senha_professor = criar_professor_e_capturar_senha(
            admin_page, NOME_PROFESSOR_SUBMIT, EMAIL_PROFESSOR_SUBMIT, NOME_TURMA_SUBMIT
        )

        # Passo 4 — Aluno
        criar_aluno_na_turma(admin_page, NOME_ALUNO_SUBMIT, NOME_TURMA_SUBMIT)

        # Passo 5 — Login do professor
        with browser.new_context() as ctx:
            prof_page = ctx.new_page()
            fazer_login(prof_page, EMAIL_PROFESSOR_SUBMIT, senha_professor)

            # Após login o professor vai para /home-professor; navega para /registro
            # para acionar o redirecionamento automático para /registro/{turmaId}
            prof_page.goto(f"{BASE_URL}/registro")
            prof_page.wait_for_url(
                re.compile(r"/registro/[0-9a-f-]{36}$"), timeout=10_000
            )

            # Passo 6 — Seleciona explicitamente a aba "Guiado" e expande o accordion
            expect(prof_page.get_by_text("Tipo de registro")).to_be_visible(timeout=8_000)

            # Clica no tab "Guiado" (texto real: "⇡ Guiado"; name faz substring match)
            prof_page.get_by_role("tab", name="Guiado").click()

            prof_page.get_by_role("button", name=CAMPO_PADRAO).click()

            # A pergunta criada pelo admin deve aparecer dentro do accordeon expandido
            # (GuidedObservationContent filtra por faixa_etaria da turma via ILIKE)
            expect(prof_page.get_by_text(TEXTO_SUBMISSAO)).to_be_visible(timeout=8_000)

            # Passo 7 — Marca o checkbox do aluno
            # GuidedObservationContent: Label com getShortName(nome_completo) = primeiras 2 palavras
            # "Aluno BNCC {RUN_ID}" → primeiras 2 palavras = "Aluno BNCC"
            nome_curto = " ".join(NOME_ALUNO_SUBMIT.split()[:2])  # "Aluno BNCC"
            prof_page.get_by_label(nome_curto).check()

            # Passo 8 — Salva a observação
            prof_page.get_by_role("button", name="Salvar Observação").click()

            # Passo 9 — Verifica o toast de sucesso
            expect(
                prof_page.get_by_text("Registro salvo com sucesso!")
            ).to_be_visible(timeout=10_000)
