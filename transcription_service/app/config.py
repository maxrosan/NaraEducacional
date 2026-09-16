"""Configuração do serviço de transcrição carregada do ambiente."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Modelo Whisper: "tiny", "base", "small", "medium", "large-v3", "distil-large-v3"
    # ou um repo HF (ex.: "deepdml/faster-whisper-large-v3-turbo-ct2" para turbo).
    model_size: str = Field(default="large-v3", alias="MODEL_SIZE")

    # "cpu" ou "cuda"
    device: str = Field(default="cpu", alias="DEVICE")

    # "int8" (CPU), "float16" (GPU), "int8_float16" (GPU quantizado)
    compute_type: str = Field(default="int8", alias="COMPUTE_TYPE")

    # Número de threads usadas em device=cpu. 0 = auto (usa todos os núcleos).
    cpu_threads: int = Field(default=0, alias="CPU_THREADS")

    # Quantos segmentos processar em paralelo (faster-whisper)
    num_workers: int = Field(default=1, alias="NUM_WORKERS")

    # Diretório onde o modelo é cacheado (monte um volume persistente aqui)
    model_cache: str = Field(default="/models", alias="MODEL_CACHE")

    # Quantos workers consomem a fila em paralelo. Mantém o mesmo nome de env por
    # compatibilidade com deploys existentes, mas agora significa "worker threads"
    # e não mais "semáforo de admissão".
    max_concurrent: int = Field(default=2, alias="MAX_CONCURRENT")

    # Capacidade máxima da fila interna. POST /transcribe responde 429 quando
    # esta capacidade é excedida, com header Retry-After.
    queue_max_size: int = Field(default=50, alias="QUEUE_MAX_SIZE")

    # Quanto tempo (segundos) jobs terminais ficam acessíveis via GET /jobs/{id}
    # antes do janitor purgá-los da memória (e remover o áudio temp associado).
    job_ttl_seconds: int = Field(default=3600, alias="JOB_TTL_SECONDS")

    # Intervalo do janitor (segundos) que varre jobs expirados.
    janitor_interval_seconds: int = Field(default=60, alias="JANITOR_INTERVAL_SECONDS")

    # Idioma padrão (código ISO-639-1). None = detecção automática.
    default_language: str = Field(default="pt", alias="DEFAULT_LANGUAGE")

    # Ativa filtro de VAD (Voice Activity Detection) do faster-whisper
    vad_filter: bool = Field(default=True, alias="VAD_FILTER")

    # Beam size usado na decodificação. 1 = greedy (rápido), 5 = padrão, maior = melhor qualidade.
    beam_size: int = Field(default=5, alias="BEAM_SIZE")

    # Token compartilhado obrigatório em requisições (header X-Internal-Token)
    internal_token: str = Field(default="", alias="INTERNAL_TOKEN")

    # Tamanho máximo de arquivo aceito (em MB)
    max_upload_mb: int = Field(default=100, alias="MAX_UPLOAD_MB")

    # Porta HTTP
    port: int = Field(default=8000, alias="PORT")

    # Log level
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # Sentry (opcional)
    sentry_dsn: str = Field(default="", alias="SENTRY_DSN")
    sentry_environment: str = Field(default="development", alias="SENTRY_ENVIRONMENT")


settings = Settings()
