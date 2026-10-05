"""
server/api/services/openai_usage.py

Serviço para registrar uso da API OpenAI silenciosamente.
Nunca lança exceções — falhas são apenas logadas, sem impactar o fluxo principal.

Uso em qualquer serviço que chame a OpenAI:

    from api.services.openai_usage import registrar_uso_openai

    # Exemplo 1 — passando a resposta bruta da OpenAI (modo preferido)
    response = client.chat.completions.create(...)
    registrar_uso_openai(
        response=response,
        usuario=request.user,  # ou None se não houver contexto
    )

    # Exemplo 2 — passando valores manuais (ex: Whisper, que não retorna usage padrão)
    registrar_uso_openai(
        input_tokens=total_segundos_de_audio,   # Whisper cobra por segundo
        output_tokens=0,
        model='whisper-1',
        input_cost=custo_calculado,
        output_cost=Decimal('0'),
        total_cost=custo_calculado,
        usuario=request.user,
    )
"""

import logging
from decimal import Decimal

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tabela de preços por modelo (USD por token)
# Atualize conforme as mudanças na página de pricing da OpenAI.
# Fonte: https://openai.com/api/pricing/
# ---------------------------------------------------------------------------
PRECOS_POR_MODELO: dict[str, dict[str, Decimal]] = {
    # gpt-5.4-mini — $0.75/1M input, $4.50/1M output
    "gpt-5.4-mini": {
        "input":  Decimal("0.00000075"),
        "output": Decimal("0.0000045"),
    },
    "gpt-5.4-mini-2026-03-17": {
        "input":  Decimal("0.00000075"),
        "output": Decimal("0.0000045"),
    },

    # gpt-5.4 — $2.50/1M input, $15.00/1M output
    "gpt-5.4": {
        "input":  Decimal("0.0000025"),
        "output": Decimal("0.000015"),
    },

    "gpt-5.4-2026-03-05": {
    "input":  Decimal("0.0000025"),   # mesmo que gpt-5.4
    "output": Decimal("0.000015"),
    },

    # gpt-5.4-nano — $0.20/1M input, $1.25/1M output
    "gpt-5.4-nano": {
        "input":  Decimal("0.0000002"),
        "output": Decimal("0.00000125"),
    },

    # gpt-5 — $1.25/1M input, $10.00/1M output
    "gpt-5": {
        "input":  Decimal("0.00000125"),
        "output": Decimal("0.00001"),
    },

    # gpt-5-mini — $0.25/1M input, $2.00/1M output
    "gpt-5-mini": {
        "input":  Decimal("0.00000025"),
        "output": Decimal("0.000002"),
    },

    # gpt-4.1 — $2.00/1M input, $8.00/1M output
    "gpt-4.1": {
        "input":  Decimal("0.000002"),
        "output": Decimal("0.000008"),
    },

    # gpt-4.1-mini — $0.40/1M input, $1.60/1M output
    "gpt-4.1-mini": {
        "input":  Decimal("0.0000004"),
        "output": Decimal("0.0000016"),
    },
    # GPT-4o
    "gpt-4o": {
        "input":  Decimal("0.000005"),    # $5,00 / 1M tokens
        "output": Decimal("0.000015"),    # $15,00 / 1M tokens
    },
    "gpt-4o-2024-11-20": {
        "input":  Decimal("0.0000025"),   # $2,50 / 1M tokens (cached)
        "output": Decimal("0.000010"),
    },
    # GPT-4o mini
    "gpt-4o-mini": {
        "input":  Decimal("0.00000015"),  # $0,15 / 1M tokens
        "output": Decimal("0.0000006"),   # $0,60 / 1M tokens
    },
    "gpt-4o-mini-2024-07-18": {
        "input":  Decimal("0.00000015"),
        "output": Decimal("0.0000006"),
    },
    # GPT-4 Turbo
    "gpt-4-turbo": {
        "input":  Decimal("0.00001"),
        "output": Decimal("0.00003"),
    },
    # GPT-3.5 Turbo
    "gpt-3.5-turbo": {
        "input":  Decimal("0.0000005"),
        "output": Decimal("0.0000015"),
    },
    # Whisper — cobrança por minuto de áudio ($0,006/min)
    # Representamos input_tokens como "segundos de áudio" para fins de registro.
    # O custo é calculado externamente e passado diretamente.
    "whisper-1": {
        "input":  Decimal("0"),
        "output": Decimal("0"),
    },
    # Embeddings
    "text-embedding-3-small": {
        "input":  Decimal("0.00000002"),
        "output": Decimal("0"),
    },
    "text-embedding-3-large": {
        "input":  Decimal("0.00000013"),
        "output": Decimal("0"),
    },
}


def _calcular_custo(
    model: str,
    input_tokens: int,
    output_tokens: int,
    image_tokens: int = 0,
) -> tuple[Decimal, Decimal, Decimal]:
    """Calcula input_cost, output_cost e total_cost a partir do modelo e tokens."""
    precos = PRECOS_POR_MODELO.get(model, {
        "input":  Decimal("0"),
        "output": Decimal("0"),
    })
    input_cost  = precos["input"]  * Decimal(input_tokens)
    output_cost = precos["output"] * Decimal(output_tokens)
    total_cost  = input_cost + output_cost
    return input_cost, output_cost, total_cost


def registrar_uso_openai(
    *,
    # --- Modo 1: passe a resposta bruta da OpenAI (chat.completions.create) ---
    response=None,
    # --- Modo 2: passe os valores diretamente ---
    input_tokens:  int     | None = None,
    output_tokens: int     | None = None,
    image_tokens:  int            = 0,
    model:         str     | None = None,
    input_cost:    Decimal | None = None,
    output_cost:   Decimal | None = None,
    total_cost:    Decimal | None = None,
    # --- Contexto ---
    usuario=None,
    escola_id=None,
    instituicao_id=None,
) -> None:
    """
    Registra o uso da API OpenAI na tabela `openai_usage`.

    Garante que NUNCA vai lançar uma exceção — é seguro chamar em qualquer
    ponto do código sem se preocupar com rollback ou tratamento de erro.

    Parâmetros:
        response    — objeto de resposta do openai-python SDK (modo preferido).
        input_tokens / output_tokens — usados quando `response` não está disponível.
        model       — nome do modelo (ex: 'gpt-4o', 'whisper-1').
        input_cost  — custo de entrada em USD; se None, calculado pela tabela interna.
        output_cost — custo de saída em USD; se None, calculado pela tabela interna.
        total_cost  — custo total em USD; se None, soma de input + output.
        usuario     — instância de Usuario (pode ser None para chamadas de sistema).
        escola_id / instituicao_id — tenant do consumo. Quem chama e sabe a
                      escola do contexto (a do aluno, a do áudio) deve passar:
                      é mais preciso que a do usuário (admin não tem escola).
                      Sem eles, vêm do usuário; a instituição, da escola.
    """
    try:
        # ── Extrai dados da resposta OpenAI (modo 1) ────────────────────────
        if response is not None:
            usage = getattr(response, "usage", None)
            if usage is None:
                logger.debug("[openai_usage] Resposta sem campo `usage` — ignorando registro.")
                return

            input_tokens  = getattr(usage, "prompt_tokens",     0)
            output_tokens = getattr(usage, "completion_tokens", 0)

            # Tokens de imagem vêm dentro de prompt_tokens_details (gpt-4o)
            details = getattr(usage, "prompt_tokens_details", None)
            if details:
                image_tokens = getattr(details, "image_tokens", 0) or 0

            if model is None:
                model = getattr(response, "model", None)

        # ── Validação mínima ─────────────────────────────────────────────────
        if input_tokens is None or output_tokens is None:
            logger.warning(
                "[openai_usage] Chamado sem tokens suficientes para registrar. "
                "Passe `response` ou `input_tokens` + `output_tokens` explicitamente."
            )
            return

        # ── Calcula custos se não fornecidos ─────────────────────────────────
        if input_cost is None or output_cost is None or total_cost is None:
            ic, oc, tc = _calcular_custo(
                model or "",
                input_tokens,
                output_tokens,
                image_tokens,
            )
            input_cost  = input_cost  if input_cost  is not None else ic
            output_cost = output_cost if output_cost is not None else oc
            total_cost  = total_cost  if total_cost  is not None else tc

        # ── Tenant do consumo ────────────────────────────────────────────────
        # Antes as colunas escola/instituicao ficavam sempre NULL: o custo não
        # podia ser separado por escola nem por rede.
        from api.models import Escola, OpenAIUsage  # import tardio para evitar circular imports

        if escola_id is None and usuario is not None:
            escola_id = getattr(usuario, "escola_id", None)
        if instituicao_id is None:
            if escola_id is not None:
                instituicao_id = (
                    Escola._base_manager.filter(pk=escola_id)
                    .values_list("instituicao_id", flat=True).first()
                )
            elif usuario is not None:
                instituicao_id = getattr(usuario, "instituicao_id", None)

        # ── Persiste ─────────────────────────────────────────────────────────

        OpenAIUsage.objects.create(
            input_tokens=int(input_tokens),
            image_tokens=int(image_tokens),
            output_tokens=int(output_tokens),
            input_cost=input_cost,
            output_cost=output_cost,
            total_cost=total_cost,
            model=model,
            usuario=usuario,
            escola_id=escola_id,
            instituicao_id=instituicao_id,
        )

        logger.debug(
            "[openai_usage] Registrado: model=%s in=%d out=%d custo=$%s",
            model, input_tokens, output_tokens, total_cost,
        )

    except Exception as exc:
        # Nunca deixar que falha de auditoria quebre o fluxo principal
        logger.warning("[openai_usage] Falha ao registrar uso (não crítico): %s", exc)


# ---------------------------------------------------------------------------
# Helper para transcrição — calcula custo por duração de áudio
# ---------------------------------------------------------------------------

# Preço por minuto de áudio, por modelo de transcrição da OpenAI. Um modelo
# ausente daqui custa 0: é o caso do faster-whisper local, que roda em máquina
# própria e não deve entrar como despesa de API.
PRECO_POR_MINUTO_TRANSCRICAO = {
    "gpt-transcribe":         Decimal("0.0045"),
    "gpt-4o-transcribe":      Decimal("0.006"),
    "gpt-4o-mini-transcribe": Decimal("0.003"),
    "whisper-1":              Decimal("0.006"),
}


def registrar_uso_whisper(
    *,
    duracao_segundos: float,
    usuario=None,
    modelo: str = "whisper-1",
    escola_id=None,
    instituicao_id=None,
) -> None:
    """
    Registra uso da transcrição com base na duração do áudio.

    A cobrança é por minuto, arredondada para cima ao segundo mais próximo.
    Usamos `input_tokens` para armazenar os segundos de áudio (convenção
    interna). O preço depende do modelo — antes era fixo no do whisper-1, o que
    passou a errar quando o padrão virou gpt-transcribe, 25% mais barato.
    """
    preco_minuto = PRECO_POR_MINUTO_TRANSCRICAO.get(modelo, Decimal("0"))
    custo_por_segundo = preco_minuto / Decimal("60")

    segundos = int(duracao_segundos) + (1 if duracao_segundos % 1 > 0 else 0)
    custo    = custo_por_segundo * Decimal(segundos)

    registrar_uso_openai(
        input_tokens=segundos,
        output_tokens=0,
        model=modelo,
        input_cost=custo,
        output_cost=Decimal("0"),
        total_cost=custo,
        usuario=usuario,
        escola_id=escola_id,
        instituicao_id=instituicao_id,
    )