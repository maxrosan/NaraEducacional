"""Configuração do Gunicorn — fonte única para todos os deploys.

Antes estes valores viviam duplicados na linha de comando do Dockerfile.prod e
do docker-compose.prod.yml. Com seis backends rodando a mesma base de código em
instâncias separadas, qualquer ajuste precisava ser replicado à mão nos dois
lugares — e divergiu. Aqui ficam num arquivo só, invocado com `-c`.
"""

import os


def _env_int(nome: str, padrao: int) -> int:
    """Lê um inteiro do ambiente, caindo no padrão se ausente ou inválido.

    O deploy é feito pelo painel do EasyPanel, onde uma variável mal digitada
    passa despercebida: preferimos subir com o padrão a derrubar o processo.
    """
    try:
        return int(os.getenv(nome, "").strip() or padrao)
    except ValueError:
        return padrao


bind = os.getenv("GUNICORN_BIND", "0.0.0.0:80")

# 2 workers, não 3. São 6 backends Django na mesma máquina de 8 cores,
# compartilhada com ~20 containers: com 3 cada, eram 18 processos gunicorn
# disputando 8 cores, e cada worker carrega sua própria cópia de Django,
# Pillow e boto3. A fórmula usual (2*cores+1) pressupõe uma aplicação dona da
# máquina, o que não é o caso.
#
# Não baixar para 1: os workers são síncronos e a geração de relatório com IA
# leva até 120s — com um único worker, uma dessas requisições trava o serviço.
workers = _env_int("GUNICORN_WORKERS", 2)

timeout = _env_int("GUNICORN_TIMEOUT", 120)

# Reciclagem de workers. Os processos ficaram no ar de 20/07 até 27/08 sem
# nunca reiniciar, chegando a 3 GB cada com CPU ociosa (0,1%) — 17,3 GB no
# total, dos quais 8,7 GB voltaram só reiniciando os containers.
#
# A causa apontada na época era a redução de ruído, que rodava dentro do worker
# e alocava arrays do tamanho do áudio; o glibc não devolvia essas arenas ao SO
# e o RSS ficava preso na marca d'água mais alta. Essa etapa foi removida por
# inteiro em setembro de 2026 — o preparo do áudio hoje é uma chamada de ffmpeg,
# em streaming e com memória constante.
#
# A reciclagem fica como rede de segurança para o que ainda aloca grande dentro
# do worker, sobretudo o processamento de imagens (api/storage.py,
# api/views/analise_producao.py, api/services/relatorio_pdf.py). Mas note que
# ela é medida em requisições, não em tempo: com o tráfego baixo destas
# instâncias, 500 requisições podem levar semanas, então não conte com ela para
# conter um crescimento rápido.
max_requests = _env_int("GUNICORN_MAX_REQUESTS", 500)

# O jitter é obrigatório: sem ele os workers atingem o limite na mesma
# requisição e reiniciam todos juntos, derrubando a capacidade do serviço de
# uma vez. Com jitter, cada worker recicla num ponto diferente.
max_requests_jitter = _env_int("GUNICORN_MAX_REQUESTS_JITTER", 50)

# A reciclagem é graciosa: o worker termina a requisição em andamento antes de
# sair, então um relatório em geração não é interrompido no meio.
graceful_timeout = _env_int("GUNICORN_GRACEFUL_TIMEOUT", 30)

accesslog = "-"
errorlog = "-"
loglevel = os.getenv("GUNICORN_LOG_LEVEL", "info")
