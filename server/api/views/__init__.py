from api.views_legacy import *
from api.views_rest import *
from api.views.audio import upload_audio  # noqa: F811 — sobrescreve a versão legada
from api.views.relatorio import gerar_relatorio, gerar_relatorio_por_crianca, deletar_relatorio_view, baixar_pdf_relatorio, bulk_pdf_relatorios, atualizar_relatorio, detalhe_relatorio, listar_relatorios_coordenacao  # noqa: F811 — sobrescreve a versão legada
from api.views.analise_producao import upload_e_analise_escrita, upload_e_analise_desenho, servir_arquivo, atualizar_classificacao  # noqa: F811, F401 — sobrescreve a versão legada
from api.views.crianca import listar_criancas  # noqa: F811 — sobrescreve a versão legada
from api.views.coordenacao_cache import refresh_coordenacao_cache, listar_cache_coordenacao  # noqa: F401
from api.views.indicadores_turma import indicadores_turma  # noqa: F401
from api.views.alfabetizacao_criancas import alfabetizacao_criancas  # noqa: F401
from api.views.planejamento import (  # noqa: F401, F811 — sobrescreve legados
    aplicar_planejamento_em_semanas,
    atualizar_planejamento_semanal,
    criar_planejamento_semanal,
    listar_planejamentos,
    processar_arquivo_planejamento,
    sugerir_atividades_planejamento,
    sugerir_bncc_planejamento,
)
from api.views.leitura import (  # noqa: F401
    iniciar_analise_leitura,
    status_analise_leitura,
    confirmar_analise_leitura,
    cancelar_analise_leitura,
    deletar_analise_leitura,
    listar_registros_leitura,
)
from api.views.auth import alterar_senha  # noqa: F401
from api.views.dispositivo import (  # noqa: F401
    atualizar_dispositivo,
    consultar_audio,
    gerar_codigo_pareamento,
    listar_dispositivos,
    parear,
    reativar_dispositivo,
    revogar_dispositivo,
    status_dispositivo,
    upload_audio_dispositivo,
)