"""Serviço de análise de produções infantis (escrita e desenho): upload S3, análise via IA e persistência."""

import json
import logging
import os
from datetime import date

from api.models import RegistroEscrita, RegistroDesenho
from api.openai_client import get_openai_client
from api.storage import upload_bytes_to_storage
from api.ia_utils import run_with_timeout, IA_REQUEST_TIMEOUT_SECONDS

from api.services.fases_producao import (
    FASES_ESCRITA,
    FASES_DESENHO,
    NAO_CLASSIFICAVEL,
    FASE_NAO_IDENTIFICADA,
    detectar_fase_em_texto,
)
from api.services.openai_usage import registrar_uso_openai
from api.services.prompt_resolver import resolver_prompt

logger = logging.getLogger(__name__)

# Varredura usada só no fallback textual do desenho (quando a IA não devolve JSON).
ELEMENTOS_DESENHO_CONHECIDOS = ("casa", "sol", "árvore", "pessoa", "animal", "flor", "carro", "família", "nuvem")


# ---------------------------------------------------------------------------
# Upload para S3 (com fallback em disco local)
# ---------------------------------------------------------------------------

def upload_para_s3(file_bytes: bytes, tipo: str, arquivo_nome: str, content_type: str) -> str:
    """Envia o arquivo ao S3 e retorna a *key*; se falhar, grava em ``uploads/<tipo>/`` e retorna o caminho local."""
    s3_key = f"{tipo}/{arquivo_nome}"
    try:
        _, url = upload_bytes_to_storage(
            key=s3_key,
            content=file_bytes,
            content_type=content_type or "image/jpeg",
        )
        if url:
            logger.info("[S3] Upload de %s concluído: %s", tipo, url)
            return s3_key
        logger.warning("[S3] Upload de %s não retornou URL; usando disco local.", tipo)
    except Exception as e:
        logger.warning("[S3] Falha no upload de %s para S3: %s", tipo, e)

    upload_dir = f"uploads/{tipo}"
    os.makedirs(upload_dir, exist_ok=True)
    local_path = os.path.join(upload_dir, arquivo_nome)
    with open(local_path, "wb") as f:
        f.write(file_bytes)
    return local_path


# ---------------------------------------------------------------------------
# Helpers de prompt e validação
# ---------------------------------------------------------------------------

def idade_do_aluno(aluno) -> str:
    """Idade em anos completos a partir de ``aluno.data_nascimento`` (ou "Não informada")."""
    nasc = getattr(aluno, "data_nascimento", None)
    if not nasc:
        return "Não informada"
    hoje = date.today()
    anos = hoje.year - nasc.year - ((hoje.month, hoje.day) < (nasc.month, nasc.day))
    return f"{anos} anos"


def _extrair_primeiro_nome(nome: str) -> str:
    partes = (nome or "").split()
    return partes[0] if partes else ""


def _montar_prompt(tipo: str, fallback_arquivo: str, nome_aluno: str, idade: str, cliente_id: str | None) -> str:
    template = resolver_prompt(tipo, cliente_id=cliente_id, fallback_arquivo=fallback_arquivo)
    primeiro_nome = _extrair_primeiro_nome(nome_aluno)
    return (
        template
        .replace("{nome_aluno}", primeiro_nome)
        .replace("{primeiro_nome}", primeiro_nome)
        .replace("{idade}", idade)
    )


def _classificacao_valida(classificacao: str, fases: list[str]) -> bool:
    return classificacao in fases or classificacao == NAO_CLASSIFICAVEL


# ---------------------------------------------------------------------------
# Análise via IA
# ---------------------------------------------------------------------------

def _chamar_openai_com_imagem(
    prompt: str,
    imagem_base64: str,
    temperature: float = 0.7,
    usuario=None,
    response_format: dict | None = None,
    max_tokens: int = 800,
) -> str:
    """Envia imagem + prompt para a OpenAI e retorna o texto (ou JSON) da análise."""
    openai_client = get_openai_client()

    def _call():
        kwargs = dict(
            model="gpt-5.4-mini",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{imagem_base64}"}},
                ],
            }],
            max_completion_tokens=max_tokens,
            temperature=temperature,
            timeout=IA_REQUEST_TIMEOUT_SECONDS,
        )
        if response_format:
            kwargs["response_format"] = response_format
        return openai_client.chat.completions.create(**kwargs)

    response = run_with_timeout(_call, IA_REQUEST_TIMEOUT_SECONDS)
    registrar_uso_openai(response=response, usuario=usuario)
    return response.choices[0].message.content.strip()


# ---------------------------------------------------------------------------
# Saída estruturada (JSON Schema com enum de fases)
# ---------------------------------------------------------------------------
# O modelo é OBRIGADO pelo schema a escolher uma fase do enum (ou "Não
# classificável"), eliminando o antigo substring match sobre texto livre que
# deixava registros presos em "Análise em processamento" quando a redação da
# IA variava (gênero, acento, vocabulário do prompt ≠ lista do código).

def _schema_analise(nome: str, fases: list[str], com_elementos: bool = False) -> dict:
    propriedades = {
        "classificacao": {
            "type": "string",
            "enum": fases + [NAO_CLASSIFICAVEL],
            "description": "Fase predominante no conjunto das produções, ou 'Não classificável' se a imagem não permitir classificação segura.",
        },
        "classificacao_emergente": {
            "type": ["string", "null"],
            "enum": fases + [None],
            "description": "Só em transição sustentada: a fase que está chegando. Caso contrário, null.",
        },
        "confianca": {
            "type": "string",
            "enum": ["alta", "baixa"],
            "description": "'baixa' quando há menos de duas produções identificáveis ou a leitura da imagem é parcial.",
        },
        "justificativa_tecnica": {
            "type": "string",
            "description": "Evidências observáveis que sustentam a classificação, em vocabulário técnico, para a professora.",
        },
        "para_familia": {
            "type": "string",
            "description": "Texto para a família, seguindo todas as regras de linguagem do prompt (sem nomes técnicos).",
        },
    }
    if com_elementos:
        propriedades["elementos_detectados"] = {
            "type": "array",
            "items": {"type": "string"},
            "description": "Elementos visíveis no desenho (ex.: casa, sol, figura humana). Vazio se não classificável.",
        }
    return {
        "type": "json_schema",
        "json_schema": {
            "name": nome,
            "strict": True,
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": propriedades,
                "required": list(propriedades.keys()),
            },
        },
    }


def _parse_resposta_estruturada(raw: str, fases: list[str]) -> dict | None:
    """Valida o JSON da IA. Retorna o dict ou None (para acionar o fallback textual)."""
    try:
        dados = json.loads(raw)
        classificacao = (dados.get("classificacao") or "").strip()
        if not _classificacao_valida(classificacao, fases):
            logger.warning("[ANALISE] Classificação fora do enum: %r", classificacao)
            return None
        return dados
    except (json.JSONDecodeError, AttributeError, TypeError) as e:
        logger.warning("[ANALISE] Resposta não é JSON válido (%s); usando fallback textual.", e)
        return None


def _rotulo_composto(dados: dict) -> str:
    """Rótulo humano: fase (+ transição) (+ ressalva de confiança)."""
    rotulo = dados["classificacao"]
    if dados.get("classificacao_emergente"):
        rotulo += f" (em transição para {dados['classificacao_emergente']})"
    if dados.get("confianca") == "baixa" and dados["classificacao"] != NAO_CLASSIFICAVEL:
        rotulo += " — baixa confiança"
    return rotulo


def _montar_texto(cabecalho: str, dados: dict) -> str:
    partes = [f"{cabecalho}: {_rotulo_composto(dados)}"]
    if (dados.get("justificativa_tecnica") or "").strip():
        partes.append(dados["justificativa_tecnica"].strip())
    if (dados.get("para_familia") or "").strip():
        partes.append(f"PARA FAMÍLIA:\n{dados['para_familia'].strip()}")
    return "\n\n".join(partes)


def _falha_analise(exc: Exception, producao: str) -> tuple[str, str]:
    """Converte uma exceção da chamada à IA em (texto_para_o_registro, rótulo).

    ``producao`` é "a escrita" ou "o desenho", usado só na mensagem.
    """
    if isinstance(exc, RuntimeError):
        logger.error("[OPENAI ERROR] Configuração ausente: %s", exc)
        return (
            "FALHA NA ANÁLISE TÉCNICA:\nA configuração da OpenAI não está disponível. "
            "Configure a variável OPENAI_API_KEY e tente novamente.",
            "Configuração OpenAI ausente",
        )
    if isinstance(exc, TimeoutError):
        logger.error("[OPENAI ERROR] Tempo limite excedido na análise de %s.", producao)
        return (
            f"FALHA NA ANÁLISE TÉCNICA:\nTempo limite excedido na análise de {producao}. "
            "Envie um arquivo mais leve ou tente novamente mais tarde.",
            "Tempo excedido",
        )
    logger.error("[OPENAI ERROR] Erro na chamada da OpenAI: %s", exc)
    return (
        f"FALHA NA ANÁLISE TÉCNICA:\nNão foi possível analisar {producao} automaticamente. "
        "Envie a imagem novamente ou classifique manualmente.",
        "Falha na OpenAI",
    )


def analisar_escrita(nome_aluno: str, imagem_base64: str, idade: str = "Não informada", usuario=None, cliente_id: str = None) -> tuple[str, str]:
    """
    Analisa imagem de escrita infantil via IA.
    Retorna (analise_completa, etapa_detectada).
    """
    logger.info("[OPENAI] Enviando prompt para análise da escrita de %s", nome_aluno)
    try:
        raw = _chamar_openai_com_imagem(
            _montar_prompt("Escrita", "escrita.txt", nome_aluno, idade, cliente_id),
            imagem_base64,
            usuario=usuario,
            response_format=_schema_analise("analise_escrita", FASES_ESCRITA),
            max_tokens=1500,
        )
    except Exception as e:
        return _falha_analise(e, "a escrita")

    logger.info("[OPENAI] Análise recebida com %d caracteres", len(raw))

    dados = _parse_resposta_estruturada(raw, FASES_ESCRITA)
    if dados:
        return _montar_texto("ETAPA DA ESCRITA", dados), dados["classificacao"]

    # Fallback: JSON inválido (ex.: prompt do banco desativou o formato) —
    # match textual normalizado (acento/gênero), nunca "em processamento".
    etapa = detectar_fase_em_texto(raw, FASES_ESCRITA) or FASE_NAO_IDENTIFICADA
    return raw, etapa


def analisar_desenho(nome_aluno: str, imagem_base64: str, idade: str = "Não informada", usuario=None, cliente_id: str = None) -> tuple[str, str, list]:
    """
    Analisa imagem de desenho infantil via IA.
    Retorna (analise_completa, fase_desenho, elementos_detectados).
    """
    logger.info("[OPENAI] Enviando prompt para análise do desenho de %s", nome_aluno)
    try:
        raw = _chamar_openai_com_imagem(
            _montar_prompt("Desenho", "desenho.txt", nome_aluno, idade, cliente_id),
            imagem_base64,
            usuario=usuario,
            response_format=_schema_analise("analise_desenho", FASES_DESENHO, com_elementos=True),
            max_tokens=1500,
        )
    except Exception as e:
        texto, rotulo = _falha_analise(e, "o desenho")
        return texto, rotulo, []

    logger.info("[OPENAI] Análise de desenho recebida com %d caracteres", len(raw))

    dados = _parse_resposta_estruturada(raw, FASES_DESENHO)
    if dados:
        elementos = [e.strip() for e in (dados.get("elementos_detectados") or []) if e and e.strip()]
        return _montar_texto("FASE DO DESENHO", dados), dados["classificacao"], elementos

    # Fallback: JSON inválido — match textual normalizado + varredura de elementos.
    fase = detectar_fase_em_texto(raw, FASES_DESENHO) or FASE_NAO_IDENTIFICADA
    raw_lower = raw.lower()
    elementos = [el.title() for el in ELEMENTOS_DESENHO_CONHECIDOS if el in raw_lower]
    return raw, fase, elementos


# ---------------------------------------------------------------------------
# Revisão da classificação pela professora
# ---------------------------------------------------------------------------

def atualizar_classificacao_registro(tipo: str, arquivo_hash: str, classificacao: str, revisado_por: str | None = None):
    """Substitui a classificação sugerida pela IA pela escolhida pela professora.

    Chamado quando, no modal de confirmação, a professora discorda da sugestão.
    Valida contra a taxonomia canônica, atualiza o campo (`etapa_ia` ou
    `fase_desenho`) e registra a revisão no fim de `analise_detalhada` para
    auditoria. O `professor` que criou o registro é preservado; quem revisou
    fica apenas na nota. Retorna o registro atualizado.

    Levanta ValueError para tipo/classificação inválidos e
    RegistroEscrita.DoesNotExist / RegistroDesenho.DoesNotExist se o hash não existe.
    """
    if tipo == "escrita":
        fases_validas = FASES_ESCRITA
        modelo, campo = RegistroEscrita, "etapa_ia"
    elif tipo == "desenho":
        fases_validas = FASES_DESENHO
        modelo, campo = RegistroDesenho, "fase_desenho"
    else:
        raise ValueError(f"Tipo inválido: {tipo!r} (esperado 'escrita' ou 'desenho')")

    classificacao = (classificacao or "").strip()
    if not _classificacao_valida(classificacao, fases_validas):
        raise ValueError(f"Classificação inválida: {classificacao!r}")

    registro = modelo.objects.get(arquivo_hash=arquivo_hash)
    anterior = getattr(registro, campo)
    if anterior == classificacao:
        return registro  # nada a fazer

    setattr(registro, campo, classificacao)
    nota = (
        f"\n\nCLASSIFICAÇÃO REVISADA PELA PROFESSORA"
        f"{f' ({revisado_por})' if revisado_por else ''}: "
        f"{classificacao} (IA havia sugerido: {anterior})"
    )
    registro.analise_detalhada = (registro.analise_detalhada or "") + nota
    registro.save(update_fields=[campo, "analise_detalhada", "atualizado_em"])
    logger.info(
        "[REVISAO] %s %s: %r -> %r (revisado_por=%s)",
        tipo, arquivo_hash, anterior, classificacao, revisado_por,
    )
    return registro


# ---------------------------------------------------------------------------
# Persistência
# ---------------------------------------------------------------------------

def _vinculos(aluno, turma, professor) -> dict:
    """FKs obrigatórias de todo registro de produção (multi-tenant)."""
    return {
        "aluno": aluno,
        "turma": turma,
        "professor": professor,
        "escola_id": turma.escola_id,
        "instituicao_id": turma.instituicao_id,
        "etapa": turma.etapa,
    }


def _criar_registro(modelo, rotulo: str, **campos):
    """Cria o registro no banco. Erros NÃO são engolidos: sobem para a view."""
    registro = modelo.objects.create(anotacoes_professora="", **campos)
    logger.info("[DATABASE] Registro de %s salvo com ID: %s", rotulo, registro.id)
    return registro


def salvar_registro_escrita(
    *, aluno, turma, professor, arquivo_nome, file_hash,
    arquivo_path, arquivo_original, tamanho_arquivo, tipo_arquivo,
    etapa_ia, analise_detalhada,
) -> RegistroEscrita:
    """Persiste um RegistroEscrita no banco e o retorna."""
    return _criar_registro(
        RegistroEscrita, "escrita",
        **_vinculos(aluno, turma, professor),
        arquivo_nome=arquivo_nome,
        arquivo_hash=file_hash,
        arquivo_path=arquivo_path,
        arquivo_original=arquivo_original,
        tamanho_arquivo=tamanho_arquivo,
        tipo_arquivo=tipo_arquivo,
        etapa_ia=etapa_ia,
        analise_detalhada=analise_detalhada,
    )


def salvar_registro_desenho(
    *, aluno, turma, professor, atividade, contexto,
    arquivo_nome, file_hash, arquivo_path, arquivo_original,
    tamanho_arquivo, tipo_arquivo, fase_desenho, elementos_detectados,
    analise_detalhada,
) -> RegistroDesenho:
    """Persiste um RegistroDesenho no banco e o retorna."""
    return _criar_registro(
        RegistroDesenho, "desenho",
        **_vinculos(aluno, turma, professor),
        atividade=atividade or "Desenho Livre",
        contexto=contexto,
        arquivo_nome=arquivo_nome,
        arquivo_hash=file_hash,
        arquivo_path=arquivo_path,
        arquivo_original=arquivo_original,
        tamanho_arquivo=tamanho_arquivo,
        tipo_arquivo=tipo_arquivo,
        fase_desenho=fase_desenho,
        elementos_detectados=elementos_detectados,
        analise_detalhada=analise_detalhada,
    )