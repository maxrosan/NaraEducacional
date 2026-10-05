# Os módulos de view são importados diretamente onde são usados
# (ex: urls.py faz `from .views.auth import LoginView, ...`).
#
# Conforme cada recurso for reconstruído para o schema multi-tenant,
# os imports correspondentes voltam a ser adicionados aqui — hoje só
# `auth.py` existe de fato; o resto (crianca, relatorio, planejamento,
# leitura, dispositivo, analise_producao, coordenacao_cache,
# indicadores_turma, alfabetizacao_criancas, audio) é código legado
# ainda não portado.