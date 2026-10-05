"""Rede de segurança contra vazamento de idioma nas respostas da IA.

Modelos de raciocínio ocasionalmente intercalam uma palavra em outro alfabeto
no meio de um texto majoritariamente em português — o caso que originou este
módulo foi "do corpo em მოძრაობ movimento" num relatório (მოძრაობ =
"movimento" em georgiano). Não é alucinação de conteúdo: o significado fica
certo, muda só a grafia. Mas a palavra chega ao relatório da família como
ruído, e é isso que a guarda evita.

Três camadas, nesta ordem:

1. ``REGRA_IDIOMA`` no prompt de TODA chamada — prevenção. Antes a regra só
   entrava no retry, ou seja, só depois de o vazamento já ter acontecido.
2. Uma nova tentativa, com a regra reforçada, quando a resposta ainda vem
   contaminada.
3. Remoção cirúrgica dos trechos em outro alfabeto, como último recurso.
   Nunca bloqueia a geração: um relatório sem uma palavra é melhor que
   nenhum relatório.

A checagem é uma ALLOWLIST, e não uma lista de alfabetos proibidos. A versão
anterior era blocklist (hebraico, árabe, cirílico, devanágari, kana, CJK,
hangul) e o georgiano simplesmente não estava nela — uma lista de proibidos
nunca fica completa, são mais de 150 scripts no Unicode. Aqui a regra é
inversa: letra fora do alfabeto latino é vazamento. Pontuação, dígitos,
símbolos e emoji passam sem restrição.

Só se aplica a texto GERADO pela IA. Texto escrito ou editado pela professora
nunca passa por aqui — se ela quiser escrever uma palavra em outro alfabeto, é
intenção dela, e a guarda não tem nada a dizer sobre isso.
"""

import json
import logging
import re
import unicodedata

logger = logging.getLogger(__name__)


# A regra NÃO diz "use apenas o alfabeto latino". Foi a primeira redação, e o
# modelo leu como "sem acento": relatórios saíram com "nao", "tambem",
# "familia" — 4 de 11 no ambiente de teste, contra 0 de 226 antes de a regra ir
# em toda chamada. A acentuação é pedida explicitamente, e o que se proíbe são
# os OUTROS alfabetos, pelo nome.
REGRA_IDIOMA = (
    "\n\nREGRA DE IDIOMA (OBRIGATÓRIA, PRIORIDADE MÁXIMA): responda sempre e "
    "exclusivamente em português do Brasil, do início ao fim do texto, com a "
    "ortografia e a acentuação corretas do português (á, â, ã, à, é, ê, í, ó, "
    "ô, õ, ú, ç) — escreva \"não\", \"também\", \"família\", nunca \"nao\", "
    "\"tambem\", \"familia\". Nunca inclua palavras, nomes, expressões ou "
    "caracteres de outro idioma ou de outro sistema de escrita (georgiano, "
    "hebraico, aramaico, árabe, cirílico, grego, devanágari, chinês, japonês, "
    "coreano, etc.), mesmo que isolados no meio de uma frase em português."
)

_REGRA_IDIOMA_REFORCO = (
    "\n\nATENÇÃO: a resposta anterior a esta instrução veio com uma palavra em "
    "outro sistema de escrita no meio do texto em português. Reescreva do zero "
    "e revise antes de responder: cada palavra do texto tem de estar em "
    "português, com a acentuação normal do português."
)

_REGRA_ACENTUACAO_REFORCO = (
    "\n\nATENÇÃO: a resposta anterior a esta instrução veio SEM ACENTOS "
    "(\"nao\", \"tambem\", \"familia\"...). Reescreva do zero com a acentuação "
    "correta do português em todas as palavras: não, também, família, você, "
    "criança, produção, análise, através, então."
)

# Blocos Unicode de letras do alfabeto latino. Inclui os estendidos (nomes
# próprios estrangeiros como "Łukasz" ou "Zoë") e o IPA, que aparece em
# notação fonética nos materiais de alfabetização.
_FAIXAS_LETRA_LATINA = (
    (0x0041, 0x005A),  # A-Z
    (0x0061, 0x007A),  # a-z
    (0x00AA, 0x00AA),  # ª
    (0x00B5, 0x00B5),  # µ (sinal de micro)
    (0x00BA, 0x00BA),  # º
    (0x00C0, 0x024F),  # Latin-1 acentuado + Latino Estendido A e B
    (0x0250, 0x02AF),  # IPA (notação fonética)
    (0x02B0, 0x02FF),  # letras modificadoras (ʰ, ˈ)
    (0x1D00, 0x1DBF),  # extensões fonéticas
    (0x1E00, 0x1EFF),  # Latino Estendido Adicional
    (0x2C60, 0x2C7F),  # Latino Estendido C
    (0xA720, 0xA7FF),  # Latino Estendido D
    (0xAB30, 0xAB6F),  # Latino Estendido E
    (0xFB00, 0xFB06),  # ligaturas latinas (ﬁ, ﬂ)
)

# Marcas combinantes aceitas: as do latino — acento em forma decomposta (NFD),
# onde "ã" chega como "a" + U+0303 — e as que compõem emoji, que são marcas por
# categoria Unicode mas não pertencem a alfabeto nenhum (o seletor de variação
# do ❤️ é uma delas; sem esta faixa o coração viraria "❤" e o emoji de teclado
# perderia a moldura).
_FAIXAS_MARCA_PERMITIDA = (
    (0x0300, 0x036F),    # diacríticos combinantes
    (0x1AB0, 0x1AFF),    # diacríticos estendidos
    (0x1DC0, 0x1DFF),    # diacríticos suplementares
    (0x20D0, 0x20FF),    # diacríticos e molduras para símbolos
    (0xFE00, 0xFE0F),    # seletores de variação (apresentação de emoji)
    (0xFE20, 0xFE2F),    # meias-marcas combinantes
    (0xE0100, 0xE01EF),  # seletores de variação suplementares
)


def _em_faixa(ch: str, faixas) -> bool:
    codigo = ord(ch)
    return any(inicio <= codigo <= fim for inicio, fim in faixas)


def _e_vazamento(ch: str) -> bool:
    """Decide se um caractere é sinal de troca de alfabeto pelo modelo.

    Só letras, marcas e dígitos têm alfabeto. Pontuação, símbolos, emoji e
    espaço em branco são neutros e passam sempre — inclusive os emoji que os
    prompts pedem no texto para a família.
    """
    categoria = unicodedata.category(ch)
    if categoria.startswith("L"):
        return not _em_faixa(ch, _FAIXAS_LETRA_LATINA)
    if categoria in ("Mn", "Mc", "Me"):
        return not _em_faixa(ch, _FAIXAS_MARCA_PERMITIDA)
    if categoria == "Nd":
        # Dígitos arábico-índicos, devanágari, fullwidth: mesmo vazamento,
        # em forma numérica.
        return not ("0" <= ch <= "9")
    return False


def contem_script_estranho(texto: str) -> bool:
    """Detecta letra de alfabeto que não deveria aparecer em texto em português."""
    if not texto:
        return False
    return any(_e_vazamento(ch) for ch in texto)


def _amostra_estranha(texto: str, limite: int = 5) -> str:
    """Os caracteres estranhos encontrados, em notação U+XXXX, para o log.

    O log vai para o Sentry e não deve carregar o texto do relatório (dado de
    criança), então só os pontos de código e o nome do script.
    """
    vistos = []
    for ch in texto:
        if not _e_vazamento(ch) or ch in vistos:
            continue
        vistos.append(ch)
        if len(vistos) >= limite:
            break
    partes = []
    for ch in vistos:
        try:
            nome = unicodedata.name(ch).split()[0]
        except ValueError:
            nome = "DESCONHECIDO"
        partes.append(f"U+{ord(ch):04X}({nome})")
    return " ".join(partes)


# Palavras que não existem em português sem acento. Lista curta e
# conservadora de propósito: só entra palavra frequente em texto pedagógico e
# que sem acento não é outra palavra válida ("esta", "e", "ate" ficam de fora).
# O sufixo -cao/-coes pega a família inteira de "produção", "relação",
# "atenção"... A varredura ignora tags e chaves de JSON — class="producao-quadro"
# é do template e "classificacao" é chave do schema da análise, não texto.
_SEM_ACENTO_RE = re.compile(
    r"\b(?:nao|tambem|voces?|entao|atraves|familias?|criancas?|analises?|"
    r"sequencias?|experiencias?|historias?|musicas?|numeros?|matematica|"
    r"[a-z]+(?:cao|coes))\b",
    re.IGNORECASE,
)
_TAG_RE = re.compile(r"<[^>]*>")
_CHAVE_JSON_RE = re.compile(r'"[^"\\]*"\s*:')
# Escapes do JSON cru: "\nAo mesmo tempo" tem o "n" do escape colado no "Ao"
# e vira "nAo" — lido como "nao". Foi o falso positivo que disparou uma nova
# tentativa desnecessária na análise de desenho, e a nova tentativa degenerou.
_ESCAPE_JSON_RE = re.compile(r'\\(?:u[0-9a-fA-F]{4}|.)')


def perdeu_acentuacao(texto: str) -> bool:
    """Detecta texto em português escrito sem acentos ("nao", "familia").

    Não é vazamento de idioma, mas é o mesmo tipo de defeito: a família lê
    um relatório com cara de digitado às pressas. Aparece quando o modelo
    entende alguma instrução como "só ASCII".
    """
    if not texto:
        return False
    so_texto = _ESCAPE_JSON_RE.sub(" ", texto)
    so_texto = _CHAVE_JSON_RE.sub(" ", _TAG_RE.sub(" ", so_texto))
    return bool(_SEM_ACENTO_RE.search(so_texto))


def _json_valido(texto: str) -> bool:
    """A resposta é um JSON que abre? Tolera a cerca ```json que alguns
    modelos põem em volta."""
    bruto = (texto or "").strip()
    if bruto.startswith("```"):
        bruto = bruto.split("\n", 1)[1] if "\n" in bruto else ""
        bruto = bruto.rsplit("```", 1)[0]
    try:
        json.loads(bruto)
        return True
    except (ValueError, TypeError):
        return False


# Sobras de pontuação e espaço depois de apagar uma palavra do meio da frase.
_ESPACO_DUPLO_RE = re.compile(r"[^\S\n]{2,}")
_ESPACO_ANTES_PONTUACAO_RE = re.compile(r"[^\S\n]+([,.;:!?)\]}])")
_ESPACO_DEPOIS_ABERTURA_RE = re.compile(r"([(\[{])[^\S\n]+")
_ESPACO_EM_VOLTA_DA_QUEBRA_RE = re.compile(r"[^\S\n]*\n[^\S\n]*")


def remover_script_estranho(texto: str) -> str:
    """Apaga os trechos em outro alfabeto e costura o que sobra.

    Troca cada caractere estranho por um espaço em vez de simplesmente
    deletá-lo — assim "a"+"ბ"+"b" não vira a palavra inventada "ab" — e depois
    fecha o espaço que sobrou: "do corpo em მოძრაობ movimento" sai como "do
    corpo em movimento", e não com o buraco de dois espaços que apareceu no
    PDF do caso original.

    Seguro para HTML e para JSON: tags, atributos e escapes são todos ASCII,
    e trocar um caractere por espaço não desbalanceia nem um nem outro.
    """
    if not texto:
        return texto
    limpo = "".join(" " if _e_vazamento(ch) else ch for ch in texto)
    limpo = _ESPACO_DUPLO_RE.sub(" ", limpo)
    limpo = _ESPACO_ANTES_PONTUACAO_RE.sub(r"\1", limpo)
    limpo = _ESPACO_DEPOIS_ABERTURA_RE.sub(r"\1", limpo)
    limpo = _ESPACO_EM_VOLTA_DA_QUEBRA_RE.sub("\n", limpo)
    return limpo.strip()


def _anexar_regra(conteudo, regra: str):
    """Anexa a regra ao conteúdo de uma mensagem, seja texto puro ou lista de
    partes (o formato das chamadas com imagem)."""
    if isinstance(conteudo, str):
        return conteudo + regra
    if isinstance(conteudo, list):
        partes = [dict(p) if isinstance(p, dict) else p for p in conteudo]
        for parte in partes:
            if isinstance(parte, dict) and parte.get("type") == "text":
                parte["text"] = (parte.get("text") or "") + regra
                return partes
        partes.append({"type": "text", "text": regra.strip()})
        return partes
    return conteudo


def aplicar_regra_idioma(messages, *, reforcada: bool = False, acentuacao: bool = False):
    """Devolve uma cópia das mensagens com a regra de idioma anexada ao prompt.

    A regra vai na primeira mensagem, que é onde este código sempre põe a
    instrução — `system` nas gerações de texto, `user` nas chamadas com
    imagem, que não têm mensagem de sistema. `reforcada` e `acentuacao`
    acrescentam o reforço de cada defeito, para a nova tentativa.
    """
    if not messages:
        return messages
    regra = (
        REGRA_IDIOMA
        + (_REGRA_IDIOMA_REFORCO if reforcada else "")
        + (_REGRA_ACENTUACAO_REFORCO if acentuacao else "")
    )
    reforcadas = [dict(m) for m in messages]
    reforcadas[0]["content"] = _anexar_regra(reforcadas[0].get("content"), regra)
    return reforcadas


def gerar_com_guarda_idioma(chamar, messages, *, log_prefix="[IA]", remover_no_fim=True):
    """Executa `chamar(messages)` com as três camadas da guarda em volta.

    `chamar` recebe a lista de mensagens (já com a regra de idioma) e devolve o
    texto bruto da resposta; quem chama segue fazendo o parsing específico
    (JSON, code fences etc.) normalmente.

    `remover_no_fim=False` desliga a terceira camada e devolve o texto como
    veio. É o modo das chamadas de EXTRAÇÃO, em que a IA reproduz o texto da
    professora (arquivo de planejamento, transcrição de voz) em vez de
    escrever o seu: ali uma palavra em outro alfabeto provavelmente é da
    professora, e apagá-la seria adulterar o que ela escreveu. Essas saídas
    passam pela revisão dela antes de valerem, e o relatório final é gerado de
    novo com a guarda inteira.

    Texto sem acento ("nao", "familia") também dispara a nova tentativa, mas
    só no modo de geração: numa extração, texto sem acento é como a
    professora escreveu. Se persistir, o texto segue como veio — não há como
    acentuar com segurança.
    """
    checar_acentuacao = remover_no_fim
    texto = chamar(aplicar_regra_idioma(messages)) or ""
    estranho = contem_script_estranho(texto)
    sem_acento = checar_acentuacao and perdeu_acentuacao(texto)
    if not estranho and not sem_acento:
        return texto

    if estranho:
        logger.warning(
            "%s Vazamento de idioma na resposta da IA (%s); tentando novamente com a regra reforçada.",
            log_prefix, _amostra_estranha(texto),
        )
    if sem_acento:
        logger.warning(
            "%s Resposta da IA sem acentuação; tentando novamente com a regra reforçada.",
            log_prefix,
        )
    texto_retry = chamar(
        aplicar_regra_idioma(messages, reforcada=estranho, acentuacao=sem_acento)
    ) or ""

    # A nova tentativa nunca troca uma resposta estruturalmente válida por uma
    # quebrada. Caso real (análise de desenho no ambiente de teste): a primeira
    # resposta era um JSON válido; a nova tentativa degenerou em lixo até o
    # limite de tokens, o JSON não fechou e a análise foi gravada crua, com a
    # fase errada. Aqui fica a primeira — limpa do alfabeto estranho, se for o
    # caso, que é a terceira camada de sempre.
    if _json_valido(texto) and not _json_valido(texto_retry):
        logger.error(
            "%s Nova tentativa veio com JSON quebrado; mantida a primeira resposta.",
            log_prefix,
        )
        if estranho and remover_no_fim:
            return remover_script_estranho(texto)
        return texto

    if not contem_script_estranho(texto_retry):
        if checar_acentuacao and perdeu_acentuacao(texto_retry):
            logger.error(
                "%s Resposta da IA continuou sem acentuação após nova tentativa; mantida como veio.",
                log_prefix,
            )
        return texto_retry

    if not remover_no_fim:
        logger.warning(
            "%s Alfabeto estranho persistiu após nova tentativa (%s); mantido, porque numa extração o texto é da professora.",
            log_prefix, _amostra_estranha(texto_retry),
        )
        return texto_retry

    logger.error(
        "%s Vazamento de idioma persistiu após nova tentativa (%s); removendo os trechos em outro alfabeto.",
        log_prefix, _amostra_estranha(texto_retry),
    )
    return remover_script_estranho(texto_retry)


def criar_completion_com_guarda(
    openai_client, *, messages, usuario=None, log_prefix="[IA]", executor=None,
    remover_no_fim=True, **kwargs
):
    """`chat.completions.create` com a guarda de idioma em volta.

    `kwargs` vai direto para a API (model, max_completion_tokens/max_tokens,
    temperature, response_format, timeout...), então cada serviço mantém os
    parâmetros que já usava. `executor` envolve a chamada — é por onde os
    serviços passam o `run_with_timeout`.

    Retorna o texto bruto da resposta.
    """
    # Import local: openai_usage importa models, e este módulo é importado por
    # serviços carregados durante o setup do Django.
    from api.services.openai_usage import registrar_uso_openai

    def _chamar(mensagens):
        def _call():
            return openai_client.chat.completions.create(messages=mensagens, **kwargs)

        response = executor(_call) if executor else _call()
        registrar_uso_openai(response=response, usuario=usuario)
        return response.choices[0].message.content or ""

    return gerar_com_guarda_idioma(
        _chamar, messages, log_prefix=log_prefix, remover_no_fim=remover_no_fim,
    )
