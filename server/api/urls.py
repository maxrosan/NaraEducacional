from django.urls import path
from . import views
from . import views_rest
from .views.analytics import contagem_registros, participacao_docente
from .views.coordenacao_cache import (
    listar_cache_coordenacao,
    listar_periodos_coordenacao,
    refresh_coordenacao_cache,
)

urlpatterns = [
    path('hello/', views.hello_world, name='hello_world'),
    path('health/', views.health_check, name='health_check'),
    path('analise-escrita/', views.analise_de_escrita, name='analise_escrita'),
    path('upload-escrita/', views.upload_e_analise_escrita, name='upload_escrita'),
    path('listar-uploads/', views.listar_uploads, name='listar_uploads'),
    path('salvar-anotacoes/', views.salvar_anotacoes_professora, name='salvar_anotacoes'),
    path('registros-escrita/', views.listar_registros_escrita, name='listar_registros_escrita'),
    path('registros-escrita/<int:registro_id>/deletar/', views_rest.deletar_registro_escrita, name='deletar_registro_escrita'),
    path('registros-desenho/', views.listar_registros_desenho, name='listar_registros_desenho'),
    path('registros-desenho/<int:registro_id>/deletar/', views_rest.deletar_registro_desenho, name='deletar_registro_desenho'),
    path('registros-aluno/<str:nome_aluno>/', views.registros_por_aluno, name='registros_por_aluno'),
    path('buscar-registros-aluno/', views.registros_por_aluno, name='buscar_registros_aluno'),
    path('arquivo/<str:arquivo_hash>/', views.servir_arquivo, name='servir_arquivo'),
    path('proxy-imagem/', views.proxy_imagem_s3, name='proxy_imagem_s3'),
    path('upload-desenho/', views.upload_e_analise_desenho, name='upload_desenho'),
    path('upload-audio/', views.upload_audio, name='upload_audio'),
    path('salvar-observacoes-transcricao/', views.salvar_observacoes_transcricao, name='salvar_observacoes_transcricao'),
    path('buscar-observacoes-transcricao/', views.buscar_observacoes_transcricao, name='buscar_observacoes_transcricao'),

    # Análise de Leitura (NaraNN)
    path('leitura/', views.listar_registros_leitura, name='listar_registros_leitura'),
    path('leitura/analisar/', views.iniciar_analise_leitura, name='iniciar_analise_leitura'),
    path('leitura/<int:registro_id>/status/', views.status_analise_leitura, name='status_analise_leitura'),
    path('leitura/<int:registro_id>/confirmar/', views.confirmar_analise_leitura, name='confirmar_analise_leitura'),
    path('leitura/<int:registro_id>/', views.cancelar_analise_leitura, name='cancelar_analise_leitura'),

    path('habilidades-bncc/', views.listar_habilidades_bncc, name='listar_habilidades_bncc'),
    path('habilidades-bncc/criar/', views.criar_habilidade_bncc, name='criar_habilidade_bncc'),
    
    # URLs para Planejamento
    path('planejamento/', views.criar_planejamento_semanal, name='criar_planejamento_semanal'),
    path('planejamento/processar-arquivo/', views.processar_arquivo_planejamento, name='processar_arquivo_planejamento'),
    path('planejamento/aplicar-em-semanas/', views.aplicar_planejamento_em_semanas, name='aplicar_planejamento_em_semanas'),
    path('planejamento/sugerir-atividades/', views.sugerir_atividades_planejamento, name='sugerir_atividades_planejamento'),
    path('planejamento/sugerir-bncc/', views.sugerir_bncc_planejamento, name='sugerir_bncc_planejamento'),
    path('planejamento/<str:turma_id>/', views.buscar_planejamento_semanal, name='buscar_planejamento_semanal'),
    path('planejamento/atualizar/<int:planejamento_id>/', views.atualizar_planejamento_semanal, name='atualizar_planejamento_semanal'),
    path('planejamentos/turma/<str:turma_id>/', views.listar_planejamentos_turma, name='listar_planejamentos_turma'),

    # URLs para Relatórios
    path('gerar-relatorio/', views.gerar_relatorio, name='gerar_relatorio'),
    path('gerar-relatorio/<uuid:crianca_id>/', views.gerar_relatorio_por_crianca, name='gerar_relatorio_por_crianca'),
    path('relatorios/<uuid:relatorio_id>/deletar/', views.deletar_relatorio_view, name='deletar_relatorio'),

    # URLs para Portfólio (Produções N-to-N)
    path('portfolio/upload/', views.upload_producao_portfolio, name='upload_producao_portfolio'),
    path('portfolio/listar/', views.listar_producoes_portfolio, name='listar_producoes_portfolio'),
    path('portfolio/vinculo/<int:vinculo_id>/', views.atualizar_vinculo_producao, name='atualizar_vinculo_producao'),
    path('portfolio/vinculos/lote/', views.atualizar_vinculos_portfolio_lote, name='atualizar_vinculos_portfolio_lote'),
    path('portfolio/excluir/<int:producao_id>/', views.excluir_producao_portfolio, name='excluir_producao_portfolio'),
    path('producoes-criancas/upload/', views.upload_producao_crianca, name='upload_producao_crianca'),
    path('instituicoes/<uuid:instituicao_id>/logo/', views.upload_logo_instituicao, name='upload_logo_instituicao'),

    # URL para Melhoria de Texto com IA
    path('melhorar-texto/', views.melhorar_texto, name='melhorar_texto'),

    # =============================================================================
    # URLs REST para substituir chamadas diretas ao banco
    # =============================================================================

    # Crianças (Alunos)
    path('criancas/', views.listar_criancas, name='listar_criancas'),
    path('criancas/criar/', views_rest.criar_crianca, name='criar_crianca'),
    path('criancas/<uuid:crianca_id>/', views_rest.detalhe_crianca, name='detalhe_crianca'),
    path('criancas/<uuid:crianca_id>/atualizar/', views_rest.atualizar_crianca, name='atualizar_crianca'),
    path('criancas/<uuid:crianca_id>/deletar/', views_rest.deletar_crianca, name='deletar_crianca'),
    path('criancas/<uuid:crianca_id>/registros-voz/', views_rest.listar_observacoes_transcricao_crianca, name='listar_observacoes_transcricao_crianca'),
    path('criancas/<uuid:crianca_id>/metas-paee/', views_rest.listar_metas_paee_crianca, name='listar_metas_paee_crianca'),
    path('criancas/<uuid:crianca_id>/foto/', views_rest.upload_foto_crianca, name='upload_foto_crianca'),

    # Relatórios
    path('relatorios/', views_rest.listar_relatorios, name='listar_relatorios'),
    path('relatorios/salvar/', views_rest.salvar_relatorio, name='salvar_relatorio'),
    path('relatorios/<uuid:relatorio_id>/', views.detalhe_relatorio, name='detalhe_relatorio'),
    path('relatorios/<uuid:relatorio_id>/atualizar/', views.atualizar_relatorio, name='atualizar_relatorio'),
    path('relatorios/<uuid:relatorio_id>/pdf/', views_rest.upload_pdf_relatorio, name='upload_pdf_relatorio'),
    path('relatorios/<uuid:relatorio_id>/pdf/refresh/', views_rest.refresh_pdf_relatorio, name='refresh_pdf_relatorio'),
    path('relatorios/<uuid:relatorio_id>/pdf/download/', views.baixar_pdf_relatorio, name='baixar_pdf_relatorio'),
    path('relatorios/bulk-pdf/', views.bulk_pdf_relatorios, name='bulk_pdf_relatorios'),
    path('relatorios/coordenacao/', views.listar_relatorios_coordenacao, name='listar_relatorios_coordenacao'),

    # Registros de Observação
    path('observacoes/', views_rest.listar_registros_observacao, name='listar_registros_observacao'),
    path('observacoes/criar/', views_rest.criar_registro_observacao, name='criar_registro_observacao'),
    path('observacoes/lote/', views_rest.criar_registros_observacao_lote, name='criar_registros_observacao_lote'),

    # Relatos individuais (ObservacaoTranscricao)
    path('observacoes-transcricao/<int:observacao_id>/deletar/', views_rest.deletar_observacao_transcricao, name='deletar_observacao_transcricao'),

    # Produções (Portfólio das crianças)
    path('producoes-criancas/', views_rest.listar_producoes_crianca, name='listar_producoes_crianca'),
    path('producoes-criancas/criar/', views_rest.criar_producao_crianca, name='criar_producao_crianca'),
    path('producoes-criancas/<uuid:producao_id>/deletar/', views_rest.deletar_producao_crianca, name='deletar_producao_crianca'),
    path('producoes-criancas/<uuid:producao_id>/atualizar/', views_rest.atualizar_producao_crianca, name='atualizar_producao_crianca'),

    # Perguntas BNCC
    path('perguntas-bncc/', views_rest.listar_perguntas_bncc, name='listar_perguntas_bncc'),
    path('perguntas-bncc/criar/', views_rest.criar_pergunta_bncc, name='criar_pergunta_bncc'),
    path('perguntas-bncc/<uuid:pergunta_id>/atualizar/', views_rest.atualizar_pergunta_bncc, name='atualizar_pergunta_bncc'),
    path('perguntas-bncc/<uuid:pergunta_id>/deletar/', views_rest.deletar_pergunta_bncc, name='deletar_pergunta_bncc'),

    # Perguntas de Especialistas
    path('perguntas-especialistas/', views_rest.listar_perguntas_especialistas, name='listar_perguntas_especialistas'),
    path('perguntas-especialistas/criar/', views_rest.criar_pergunta_especialista, name='criar_pergunta_especialista'),
    path('perguntas-especialistas/<uuid:pergunta_id>/atualizar/', views_rest.atualizar_pergunta_especialista, name='atualizar_pergunta_especialista'),
    path('perguntas-especialistas/<uuid:pergunta_id>/deletar/', views_rest.deletar_pergunta_especialista, name='deletar_pergunta_especialista'),

    # Especialistas
    path('especialistas/minhas-criancas/', views_rest.listar_criancas_especialista, name='listar_criancas_especialista'),
    path('especialistas/registros-voz/', views_rest.listar_registros_voz_especialista, name='listar_registros_voz_especialista'),

    # --- Gravador de áudio (dispositivo físico do relato individual) ---
    path('dispositivos/', views.listar_dispositivos, name='listar_dispositivos'),
    path('dispositivos/codigo/', views.gerar_codigo_pareamento, name='gerar_codigo_pareamento'),
    path('dispositivos/parear/', views.parear, name='parear_dispositivo'),
    path('dispositivos/audio/', views.upload_audio_dispositivo, name='upload_audio_dispositivo'),
    path('dispositivos/audio/<uuid:upload_id>/', views.consultar_audio, name='consultar_audio_dispositivo'),
    path('dispositivos/status/', views.status_dispositivo, name='status_dispositivo'),
    path('dispositivos/<uuid:dispositivo_id>/', views.atualizar_dispositivo, name='atualizar_dispositivo'),
    path('dispositivos/<uuid:dispositivo_id>/revogar/', views.revogar_dispositivo, name='revogar_dispositivo'),
    path('dispositivos/<uuid:dispositivo_id>/reativar/', views.reativar_dispositivo, name='reativar_dispositivo'),

    # Calendário
    path('calendario-bimestres/', views_rest.listar_calendario_bimestres, name='listar_calendario_bimestres'),

    # Períodos avaliativos
    path('periodos-avaliativos/', views_rest.listar_periodos_avaliativos, name='listar_periodos_avaliativos'),
    path('periodos-avaliativos/criar/', views_rest.criar_periodo_avaliativo, name='criar_periodo_avaliativo'),
    path('periodos-avaliativos/<uuid:periodo_id>/atualizar/', views_rest.atualizar_periodo_avaliativo, name='atualizar_periodo_avaliativo'),
    path('periodos-avaliativos/<uuid:periodo_id>/deletar/', views_rest.deletar_periodo_avaliativo, name='deletar_periodo_avaliativo'),

    # Turmas
    path('turmas/', views_rest.listar_turmas, name='listar_turmas'),
    path('turmas/<uuid:turma_id>/', views_rest.detalhe_turma, name='detalhe_turma'),
    path('turmas/criar/', views_rest.criar_turma, name='criar_turma'),
    path('turmas/<uuid:turma_id>/atualizar/', views_rest.atualizar_turma, name='atualizar_turma'),
    path('turmas/<uuid:turma_id>/deletar/', views_rest.deletar_turma, name='deletar_turma'),

    # Configurações de registro
    path('configuracoes-registro/', views_rest.listar_configuracoes_registro, name='listar_configuracoes_registro'),
    path('configuracoes-registro/criar/', views_rest.criar_configuracao_registro, name='criar_configuracao_registro'),
    path('configuracoes-registro/<uuid:configuracao_id>/atualizar/', views_rest.atualizar_configuracao_registro, name='atualizar_configuracao_registro'),

    # Projetos
    path('projetos/', views_rest.listar_projetos, name='listar_projetos'),
    path('projetos/criar/', views_rest.criar_projeto, name='criar_projeto'),
    path('projetos/<uuid:projeto_id>/atualizar/', views_rest.atualizar_projeto, name='atualizar_projeto'),
    path('projetos/<uuid:projeto_id>/deletar/', views_rest.deletar_projeto, name='deletar_projeto'),

    # Instituições
    path('instituicoes/', views_rest.listar_instituicoes, name='listar_instituicoes'),
    path('instituicoes/criar/', views_rest.criar_instituicao, name='criar_instituicao'),
    path('instituicoes/<uuid:instituicao_id>/', views_rest.detalhe_instituicao, name='detalhe_instituicao'),
    path('instituicoes/<uuid:instituicao_id>/atualizar/', views_rest.atualizar_instituicao, name='atualizar_instituicao'),

    # Usuários
    path('usuarios/', views_rest.listar_usuarios, name='listar_usuarios'),
    path('usuarios/criar/', views_rest.criar_usuario, name='criar_usuario'),
    path('usuarios/<uuid:usuario_id>/', views_rest.detalhe_usuario, name='detalhe_usuario'),
    path('usuarios/<uuid:usuario_id>/atualizar/', views_rest.atualizar_usuario, name='atualizar_usuario'),
    path('usuarios/<uuid:usuario_id>/deletar/', views_rest.deletar_usuario, name='deletar_usuario'),

    # Autenticação (sessão Django)
    path('auth/csrf/', views_rest.get_csrf_token, name='auth_csrf'),
    path('auth/login/', views_rest.auth_login, name='auth_login'),
    path('auth/logout/', views_rest.auth_logout, name='auth_logout'),
    path('auth/me/', views_rest.auth_me, name='auth_me'),

    # Endpoints auxiliares (compatibilidade frontend)
    path('usuario-turmas/', views_rest.listar_usuario_turmas, name='listar_usuario_turmas'),
    path('usuario-turmas/criar/', views_rest.criar_usuario_turma, name='criar_usuario_turma'),
    path('usuario-turmas/deletar/', views_rest.deletar_usuario_turma, name='deletar_usuario_turma'),

    # Mensagens da Coordenação
    path('mensagens-coordenacao/', views_rest.listar_mensagens_coordenacao, name='listar_mensagens_coordenacao'),
    path('mensagens-coordenacao/criar/', views_rest.criar_mensagem_coordenacao, name='criar_mensagem_coordenacao'),
    path('mensagens-lidas/', views_rest.listar_mensagens_lidas, name='listar_mensagens_lidas'),
    path('mensagens-lidas/criar/', views_rest.marcar_mensagem_lida, name='marcar_mensagem_lida'),

    # Alertas Lidos
    path('alertas-lidos/', views_rest.listar_alertas_lidos, name='listar_alertas_lidos'),
    path('alertas-lidos/criar/', views_rest.criar_alerta_lido, name='criar_alerta_lido'),

    # Alertas do sistema
    path('alertas/', views_rest.listar_alertas, name='listar_alertas'),
    path('alertas/detalhe/', views_rest.detalhe_alerta, name='detalhe_alerta'),

    # Indicadores
    path('indicadores/linguagem/', views_rest.listar_indicador_linguagem, name='listar_indicador_linguagem'),
    path('indicadores/participacao-docente/', participacao_docente, name='participacao_docente'),

    # Planejamentos (endpoint geral para substituir consultas diretas)
    path('planejamentos/', views.listar_planejamentos, name='listar_planejamentos_geral'),

    # Séries / Configuração de Faixas Etárias
    path('series-config/', views_rest.listar_series_config, name='listar_series_config'),
    path('series-config/criar/', views_rest.criar_serie_config, name='criar_serie_config'),
    path('series-config/<uuid:serie_id>/atualizar/', views_rest.atualizar_serie_config, name='atualizar_serie_config'),
    path('series-config/<uuid:serie_id>/deletar/', views_rest.deletar_serie_config, name='deletar_serie_config'),

    # Campos de Experiência Customizados (com ícones)
    path('campos-experiencia/', views_rest.listar_campos_experiencia_customizados, name='listar_campos_experiencia'),
    path('campos-experiencia/criar/', views_rest.criar_campo_experiencia_customizado, name='criar_campo_experiencia'),
    path('campos-experiencia/<uuid:campo_id>/atualizar/', views_rest.atualizar_campo_experiencia_customizado, name='atualizar_campo_experiencia'),
    path('campos-experiencia/<uuid:campo_id>/deletar/', views_rest.deletar_campo_experiencia_customizado, name='deletar_campo_experiencia'),

    path('auth/recuperar-senha/', views_rest.recuperar_senha, name='auth_recuperar_senha'),
    path('auth/confirmar-senha/', views_rest.confirmar_senha, name='auth_confirmar_senha'),

    # Templates de Relatório (modelo de capa + config visual + items_sumario)
    path('templates-relatorio/', views_rest.listar_templates_relatorio, name='listar_templates_relatorio'),
    path('templates-relatorio/criar/', views_rest.criar_template_relatorio, name='criar_template_relatorio'),
    path('templates-relatorio/<uuid:template_id>/', views_rest.detalhe_template_relatorio, name='detalhe_template_relatorio'),
    path('templates-relatorio/<uuid:template_id>/atualizar/', views_rest.atualizar_template_relatorio, name='atualizar_template_relatorio'),
    path('templates-relatorio/<uuid:template_id>/deletar/', views_rest.deletar_template_relatorio, name='deletar_template_relatorio'),
    path('templates-relatorio/<uuid:template_id>/ativar/', views_rest.ativar_template_relatorio, name='ativar_template_relatorio'),
    
    # Analytics
    path('analytics/contagem-registros/', contagem_registros, name='contagem_registros'),

    # Cache da Coordenação (snapshot D-1 gerado por worker externo)
    path('coordenacao/cache/', listar_cache_coordenacao, name='listar_cache_coordenacao'),
    path('coordenacao/periodos/', listar_periodos_coordenacao, name='listar_periodos_coordenacao'),
    # As duas abaixo tinham view escrita e importada em views/__init__.py, mas
    # nunca chegaram a ser roteadas — as telas Aprendizagens e o drill-down de
    # Alfabetização recebiam 404 do backend.
    # (relatorios/coordenacao/ ja esta declarada na secao de Relatorios acima.)
    path('coordenacao/indicadores-turma/', views.indicadores_turma, name='indicadores_turma'),
    path('coordenacao/alfabetizacao-criancas/', views.alfabetizacao_criancas, name='alfabetizacao_criancas'),
    path('internal/cache/coordenacao/', refresh_coordenacao_cache, name='refresh_cache_coordenacao'),

    # Disciplinas
    path('disciplinas/', views_rest.listar_disciplinas, name='listar_disciplinas'),
    path('disciplinas/criar/', views_rest.criar_disciplina, name='criar_disciplina'),
    path('disciplinas/<uuid:disciplina_id>/atualizar/', views_rest.atualizar_disciplina, name='atualizar_disciplina'),
    path('disciplinas/<uuid:disciplina_id>/deletar/', views_rest.deletar_disciplina, name='deletar_disciplina'),

    # Vínculo Usuário-Disciplina
    path('usuario-disciplinas/', views_rest.listar_usuario_disciplinas, name='listar_usuario_disciplinas'),
    path('usuario-disciplinas/criar/', views_rest.criar_usuario_disciplina, name='criar_usuario_disciplina'),
    path('usuario-disciplinas/<uuid:vinculo_id>/deletar/', views_rest.deletar_usuario_disciplina, name='deletar_usuario_disciplina'),

    #Prompts
    path('prompts/categorias/', views_rest.listar_categorias_prompt, name='listar_categorias_prompt'),
    path('prompts/categorias/criar/', views_rest.criar_categoria_prompt, name='criar_categoria_prompt'),
    path('prompts/salvar/', views_rest.salvar_prompt, name='salvar_prompt'),
]