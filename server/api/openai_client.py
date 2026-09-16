import os
from functools import lru_cache
from openai import OpenAI


@lru_cache(maxsize=1)
def get_openai_client() -> OpenAI:
    """
    Retorna uma instância do cliente OpenAI configurada via variável de ambiente.
    Inclui timeout padrão configurável e levanta erro explícito quando a chave não está disponível
    para evitar credenciais hardcoded.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    timeout_env = os.getenv("OPENAI_TIMEOUT_SECONDS", "30")

    try:
        timeout_seconds = float(timeout_env)
    except ValueError:
        timeout_seconds = 30.0

    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY não configurada. Defina a variável de ambiente para habilitar os recursos de IA."
        )

    return OpenAI(api_key=api_key, timeout=timeout_seconds)
