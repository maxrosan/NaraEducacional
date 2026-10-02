"""Serviço de processamento de áudio: transcrição, extração de observações e pareamento de alunos."""

import json
import difflib
import logging
import os
import subprocess

from openai import APIConnectionError

from api.openai_client import get_openai_client
from api.transcription import get_transcription_backend
from api.ia_utils import run_with_timeout, IA_REQUEST_TIMEOUT_SECONDS

from api.services.openai_usage import registrar_uso_openai, registrar_uso_whisper
from api.services.prompt_resolver import resolver_prompt

logger = logging.getLogger(__name__)


class InvalidAudioError(ValueError):
    """Áudio inválido ou corrompido que não pode ser decodificado."""


# Trechos que o ffmpeg emite quando o arquivo em si está quebrado. Distinguem
# um áudio corrompido (erro do usuário, 422) de uma falha de ambiente (500).
_FFMPEG_INVALID_INPUT_MARKERS = (
    "Invalid data found when processing input",
    "moov atom not found",
    "End of file",
    "could not find codec parameters",
)

# O ffmpeg trabalha em streaming, então isto é generoso de sobra: 10 min de
# áudio convertem em ~2s. Existe só para não pendurar o worker se o processo
# travar, e cabe com folga no timeout de 120s do Gunicorn, que ainda precisa
# cobrir a transcrição e a extração via GPT na mesma requisição.
_FFMPEG_TIMEOUT_SEGUNDOS = int(os.getenv("AUDIO_FFMPEG_TIMEOUT", "").strip() or 60)

# Modelo que extrai nomes e observações da transcrição. Constante para que os
# metadados da resposta não repitam a string à mão e saiam de sincronia.
MODELO_EXTRACAO = "gpt-5.4"

# Prompt padrão usado como fallback quando não há registro no banco
_PROMPT_VOZ_FALLBACK = """Você é um assistente especializado em análise de observações pedagógicas. Analise a transcrição a seguir de uma professora falando sobre seus alunos e extraia:

1. NOMES DOS ALUNOS mencionados
2. OBSERVAÇÕES específicas sobre cada aluno

TRANSCRIÇÃO:
{transcricao}

Responda APENAS em formato JSON válido, seguindo exatamente esta estrutura:
{{
    "nomes_alunos": ["Nome Completo 1", "Nome Completo 2"],
    "observacoes": ["observação detalhada do aluno 1", "observação detalhada do aluno 2"]
}}

REGRAS:
- Extraia APENAS nomes que foram explicitamente mencionados na transcrição
- NÃO invente nomes ou observações que não estejam na transcrição
- Se não encontrar nomes específicos, retorne arrays vazios
- Se a transcrição estiver vazia ou incompreensível, retorne arrays vazios
- As observações devem ser completas e educacionalmente relevantes
- Mantenha a ordem: primeiro nome corresponde à primeira observação
- Não inclua explicações, apenas o JSON"""


def descartar_derivados(arquivo_path: str) -> None:
    """Apaga o WAV derivado de ``arquivo_path`` (``_converted``).

    Ele não é referenciado por nenhum outro fluxo — só existe entre o upload e a
    transcrição — e é bem maior que o áudio comprimido original, porque é PCM
    16 kHz. Antes ficava em uploads/audio para sempre.
    """
    base, _ = os.path.splitext(arquivo_path)
    try:
        os.remove(f"{base}_converted.wav")
    except OSError:
        pass


def converter_para_wav(arquivo_path: str) -> str:
    """
    Normaliza o áudio para WAV 16 kHz mono, que é o formato que o Whisper espera.
    Retorna o path do arquivo convertido, ou o original se o ffmpeg falhar por um
    motivo que não seja arquivo corrompido.

    Aqui já houve uma etapa de redução de ruído (``noisereduce``), removida em
    setembro de 2026. O Whisper não precisa dela: foi treinado em 680 mil horas
    de áudio real e ruidoso, e a robustez está dentro do modelo. Pior, o spectral
    gating do noisereduce introduz o artefato clássico da subtração espectral
    ("musical noise") e come justamente o que é de baixa energia — fala baixa e
    consoantes fricativas. Ela custava 18s num áudio de 30s e 59s num de 10min,
    dentro do timeout de 120s do Gunicorn, e tinha entrado sem justificativa
    registrada. O ffmpeg sozinho leva 0,6-2s e trabalha em streaming, com
    memória constante.
    """
    base, _ = os.path.splitext(arquivo_path)
    arquivo_wav = f"{base}_converted.wav"

    try:
        resultado = subprocess.run(
            # -hide_banner porque sem ele a versão e a lista de flags de
            # compilação ocupam os primeiros ~1500 caracteres do stderr e
            # empurram a mensagem de erro para fora do trecho que vai ao log.
            ["ffmpeg", "-hide_banner", "-y", "-i", arquivo_path,
             "-ar", "16000", "-ac", "1", arquivo_wav],
            capture_output=True,
            timeout=_FFMPEG_TIMEOUT_SEGUNDOS,
        )
        codigo = resultado.returncode
        # O motivo da falha é a última coisa que o ffmpeg imprime.
        detalhe = resultado.stderr.decode(errors="replace")[-500:].strip()
    except subprocess.TimeoutExpired:
        # subprocess.run já matou o ffmpeg, mas ele pode ter deixado um WAV pela
        # metade — descartado logo abaixo, junto com os demais casos de falha.
        codigo, detalhe = None, f"tempo limite de {_FFMPEG_TIMEOUT_SEGUNDOS}s excedido"

    if codigo == 0:
        logger.info("[FFMPEG] Convertido para WAV: %s -> %s", arquivo_path, arquivo_wav)
        return arquivo_wav

    descartar_derivados(arquivo_path)

    if any(marca.lower() in detalhe.lower() for marca in _FFMPEG_INVALID_INPUT_MARKERS):
        logger.warning("[FFMPEG] Áudio inválido: %s | %s", arquivo_path, detalhe)
        raise InvalidAudioError(
            "Arquivo de áudio inválido ou corrompido — não foi possível decodificar."
        )

    # Falha de ambiente, não do arquivo: vale tentar transcrever o original, que
    # o Whisper aceita em vários formatos.
    logger.warning("[FFMPEG] Falha na conversão, usando áudio original: %s", detalhe)
    return arquivo_path


def _obter_duracao_audio(arquivo_path: str) -> float:
    """Retorna a duração do áudio em segundos. Retorna 0.0 se falhar.

    Usa ffprobe, que já vem com o ffmpeg da imagem. Antes era ``soundfile.info``,
    e soundfile deixou de ser dependência do projeto.
    """
    try:
        resultado = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                arquivo_path,
            ],
            capture_output=True,
            timeout=15,
        )
        if resultado.returncode == 0:
            return float(resultado.stdout.decode(errors="replace").strip())
    except Exception:
        pass

    try:
        tamanho = os.path.getsize(arquivo_path)
        return tamanho / 32000
    except Exception:
        return 0.0


def transcrever_audio(arquivo_path: str, usuario=None) -> str:
    """
    Transcreve áudio usando o backend configurado em ``TRANSCRIPTION_PROVIDER``.
    """
    backend = get_transcription_backend()
    logger.info("[WHISPER] Backend ativo: %s", backend.name)
    transcricao = backend.transcribe(arquivo_path, language="pt")
    try:
        # Backends sem `model` (o faster-whisper local) caem no preço 0 da
        # tabela: rodam em máquina própria e não são despesa de API.
        registrar_uso_whisper(
            duracao_segundos=_obter_duracao_audio(arquivo_path),
            usuario=usuario,
            modelo=getattr(backend, "model", ""),
        )
    except Exception:
        pass
    return transcricao


def modelo_transcricao_ativo() -> str:
    """Nome do modelo que o backend configurado usaria, para os metadados da
    resposta. Backends self-hosted não têm ``model``."""
    return getattr(get_transcription_backend(), "model", "") or "faster-whisper (local)"


def extrair_observacoes(transcricao: str, escola_id: str = None) -> dict:
    """
    Usa GPT para extrair nomes de alunos e observações da transcrição.
    O prompt é resolvido pelo banco (categoria "Voz"), com fallback para o
    prompt padrão definido em _PROMPT_VOZ_FALLBACK.
    Retorna {"nomes_alunos": [...], "observacoes": [...]}.
    """
    if not transcricao or len(transcricao.strip()) < 10:
        raise ValueError("Transcrição vazia ou muito curta para extrair observações.")

    # Resolve prompt do banco com fallback para o padrão
    prompt_template = resolver_prompt("Voz", escola_id=escola_id) or _PROMPT_VOZ_FALLBACK
    prompt = prompt_template.replace("{transcricao}", transcricao)

    openai_client = get_openai_client()

    def _extrair():
        return openai_client.chat.completions.create(
            model=MODELO_EXTRACAO,
            messages=[{"role": "user", "content": prompt}],
            max_completion_tokens=2000,
            temperature=0.3,
            timeout=IA_REQUEST_TIMEOUT_SECONDS,
            response_format={"type": "json_object"},
        )

    try:
        response = run_with_timeout(_extrair, IA_REQUEST_TIMEOUT_SECONDS)
    except APIConnectionError as e:
        logger.error("[IA EXTRAÇÃO] Falha de conexão com a OpenAI durante extração: %s", e)
        raise ConnectionError("Falha de conexão com o serviço de análise.") from e

    # Áudio do dispositivo não tem usuário: a escola vem do contexto.
    registrar_uso_openai(response=response, usuario=None, escola_id=escola_id)
    choice = response.choices[0]
    resultado_ia = (choice.message.content or "").strip()

    if getattr(choice, "finish_reason", None) == "length":
        logger.error(
            "[IA EXTRAÇÃO] Resposta truncada por limite de tokens (%d chars). Resultado: %s...",
            len(resultado_ia), resultado_ia[:200],
        )
        raise ValueError(
            "A transcrição é muito longa para ser processada de uma vez. "
            "Tente gravar áudios mais curtos."
        )

    resultado_limpo = resultado_ia
    if resultado_limpo.startswith("```json"):
        resultado_limpo = resultado_limpo.replace("```json", "").replace("```", "").strip()
    elif resultado_limpo.startswith("```"):
        resultado_limpo = resultado_limpo.replace("```", "").strip()

    try:
        dados = json.loads(resultado_limpo)
    except json.JSONDecodeError as e:
        logger.error("[IA ERRO] JSON inválido da IA: %s | Resultado: %s...", e, resultado_ia[:200])
        raise ValueError("Não foi possível interpretar a resposta da IA.") from e

    nomes = dados.get("nomes_alunos", [])
    observacoes = dados.get("observacoes", [])

    if not nomes or not observacoes:
        logger.warning("[IA EXTRAÇÃO] Arrays vazios retornados pela IA. Resultado: %s...", resultado_ia[:200])
        raise ValueError("Não foi possível identificar alunos no áudio.")

    logger.info("[IA EXTRAÇÃO] Extraídos %d alunos da transcrição", len(nomes))
    return {"nomes_alunos": nomes, "observacoes": observacoes}


def encontrar_aluno_mais_proximo(nome_detectado, alunos_turma):
    """
    Encontra o aluno mais próximo na turma usando similaridade de nomes.
    """
    if not alunos_turma or not nome_detectado:
        return None

    melhor_match = None
    melhor_score = 0

    nome_detectado_norm = nome_detectado.lower().strip()
    partes_detectado = nome_detectado_norm.split()

    for aluno in alunos_turma:
        nome_aluno = aluno.get("nome_completo", "").lower().strip()
        partes_aluno = nome_aluno.split()

        score_completo = difflib.SequenceMatcher(None, nome_detectado_norm, nome_aluno).ratio()

        primeiro_detectado = partes_detectado[0] if partes_detectado else ""
        primeiro_aluno = partes_aluno[0] if partes_aluno else ""
        score_primeiro = difflib.SequenceMatcher(None, primeiro_detectado, primeiro_aluno).ratio()

        score_composto = 0
        metodo = "primeiro_nome"

        if len(partes_detectado) >= 2 and len(partes_aluno) >= 2:
            nome_composto_detectado = " ".join(partes_detectado[:2])
            nome_composto_aluno = " ".join(partes_aluno[:2])
            score_composto = difflib.SequenceMatcher(
                None, nome_composto_detectado, nome_composto_aluno
            ).ratio()
            if score_composto > 0.7:
                metodo = "nome_composto"

        if score_composto > 0.7:
            score_final = score_composto
        elif score_completo > 0.5:
            score_final = max(score_completo, score_primeiro * 0.7)
            metodo = "completo" if score_completo > score_primeiro * 0.7 else "primeiro_nome"
        else:
            score_final = score_primeiro * 0.6

        if score_final > melhor_score and score_final > 0.55:
            melhor_score = score_final
            melhor_match = {"aluno": aluno, "score": score_final, "metodo": metodo}
            logger.debug(
                "[MATCH DEBUG] '%s' -> '%s' | composto=%.2f completo=%.2f primeiro=%.2f final=%.2f",
                nome_detectado, nome_aluno, score_composto, score_completo, score_primeiro, score_final,
            )

    return melhor_match


def parear_alunos_com_turma(nomes_extraidos, observacoes, alunos_turma):
    """
    Para cada nome extraído pela IA, tenta encontrar o aluno correspondente na turma.
    Retorna {"pareados": [...], "nao_pareados": [...]}.
    """
    pareados = []
    nao_pareados = []

    num = min(len(nomes_extraidos), len(observacoes))

    for i in range(num):
        nome_detectado = nomes_extraidos[i]
        observacao = observacoes[i]

        match = encontrar_aluno_mais_proximo(nome_detectado, alunos_turma)

        if match:
            logger.info(
                "[MATCH] '%s' -> '%s' (score: %.2f, método: %s)",
                nome_detectado, match["aluno"]["nome_completo"], match["score"], match["metodo"],
            )
            pareados.append({
                "aluno_nome": match["aluno"]["nome_completo"],
                "observacao": observacao,
                "confianca": round(match["score"], 2),
                "nome_original_detectado": nome_detectado,
                "score_similaridade": round(match["score"], 2),
                "metodo_match": match["metodo"],
            })
        else:
            logger.warning("[NO MATCH] '%s' não encontrou correspondência na turma", nome_detectado)
            nao_pareados.append({
                "nome_original_detectado": nome_detectado,
                "observacao": observacao,
            })

    return {"pareados": pareados, "nao_pareados": nao_pareados}