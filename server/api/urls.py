from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views.auth import LoginView, logout, me, alterar_senha, recuperar_senha, confirmar_senha
from .views.health import health
from .views.instituicao import (
    listar_instituicoes,
    criar_instituicao,
    detalhe_instituicao,
    atualizar_instituicao,
)
from .views.escola import (
    listar_escolas,
    resumo_escolas,
    criar_escola,
    detalhe_escola,
    atualizar_escola,
)
from .views.especialista import (
    listar_especialistas,
    criar_especialista,
    detalhe_especialista,
    atualizar_especialista,
)
from .views.usuario import (
    listar_usuarios,
    criar_usuario,
    detalhe_usuario,
    atualizar_usuario,
)
from .views.turma import (
    listar_turmas,
    criar_turma,
    detalhe_turma,
    atualizar_turma,
    listar_professores_turma,
    vincular_professor_turma,
    desvincular_professor_turma,
    listar_frequencias_registro,
    atualizar_frequencia_registro,
)
from .views.disciplina import (
    listar_disciplinas,
    criar_disciplina,
    detalhe_disciplina,
    atualizar_disciplina,
    listar_professores_disciplina,
    vincular_usuario_disciplina,
    desvincular_usuario_disciplina,
)
from .views.aluno import (
    listar_alunos,
    criar_aluno,
    detalhe_aluno,
    atualizar_aluno,
    enviar_foto_aluno,
)
from .views.projeto import (
    listar_projetos,
    criar_projeto,
    detalhe_projeto,
    atualizar_projeto,
)
from .views.producao import (
    listar_producoes,
    criar_producao,
    detalhe_producao,
    atualizar_producao,
    deletar_producao,
    listar_alunos_producao,
    vincular_aluno_producao,
    atualizar_vinculo_producao_aluno,
    desvincular_aluno_producao,
)
from .views.registro import (
    listar_registros_escrita,
    detalhe_registro_escrita,
    atualizar_registro_escrita,
    deletar_registro_escrita,
    listar_registros_desenho,
    detalhe_registro_desenho,
    atualizar_registro_desenho,
    deletar_registro_desenho,
)
from .views.leitura import (
    listar_registros_leitura,
    iniciar_analise_leitura,
    status_analise_leitura,
    confirmar_analise_leitura,
    cancelar_analise_leitura,
    deletar_analise_leitura,
)
from .views.campo_pedagogico import (
    listar_campos_pedagogicos,
    criar_campo_pedagogico,
    detalhe_campo_pedagogico,
    atualizar_campo_pedagogico,
    desativar_campo_pedagogico,
    listar_habilidades_bncc,
    criar_habilidade_bncc,
    detalhe_habilidade_bncc,
    atualizar_habilidade_bncc,
)
from .views.pergunta import (
    listar_perguntas,
    criar_pergunta,
    detalhe_pergunta,
    atualizar_pergunta,
    listar_perguntas_especialistas,
    criar_pergunta_especialista,
    detalhe_pergunta_especialista,
    atualizar_pergunta_especialista,
)
from .views.observacao import (
    listar_registros_observacao,
    criar_registro_observacao,
    detalhe_registro_observacao,
    atualizar_registro_observacao,
    deletar_registro_observacao,
    listar_observacoes_transcricao,
    criar_observacao_transcricao,
    detalhe_observacao_transcricao,
    atualizar_observacao_transcricao,
    deletar_observacao_transcricao,
)
from .views.planejamento import (
    listar_planejamentos,
    processar_arquivo_planejamento,
    sugerir_atividades_planejamento,
    sugerir_bncc_planejamento,
    criar_planejamento_semanal,
    atualizar_planejamento_semanal,
    aplicar_planejamento_em_semanas,
)
from .views.avaliacao import (
    listar_periodos_avaliativos,
    criar_periodo_avaliativo,
    detalhe_periodo_avaliativo,
    atualizar_periodo_avaliativo,
    excluir_periodo_avaliativo,
    listar_relatorio_templates,
    criar_relatorio_template,
    detalhe_relatorio_template,
    atualizar_relatorio_template,
    listar_relatorios,
    criar_relatorio,
    detalhe_relatorio,
    atualizar_relatorio,
    revisar_relatorio,
    deletar_relatorio,
)
from .views.notificacao import (
    listar_minhas_notificacoes,
    criar_notificacao,
    marcar_notificacao_lida,
)
from .views.paee import (
    listar_metas_paee,
    criar_meta_paee,
    detalhe_meta_paee,
    atualizar_meta_paee,
    listar_sessoes_especialista,
    criar_sessao_especialista,
    detalhe_sessao_especialista,
    atualizar_sessao_especialista,
    listar_metas_sessao,
    vincular_meta_sessao,
    desvincular_meta_sessao,
    listar_tarefas_paee,
    criar_tarefa_paee,
    detalhe_tarefa_paee,
    atualizar_tarefa_paee,
)
from .views.dispositivo import (
    gerar_codigo_pareamento,
    listar_dispositivos,
    atualizar_dispositivo,
    revogar_dispositivo,
    reativar_dispositivo,
    parear,
    upload_audio_dispositivo,
    consultar_audio,
    status_dispositivo,
)
from .views.ticket import (
    listar_tickets,
    criar_ticket,
    detalhe_ticket,
    atualizar_ticket,
    listar_respostas_ticket,
    responder_ticket,
    anexar_arquivo_ticket,
    anexar_arquivo_resposta,
)
from .views.permissoes_usuario import (
    listar_logs_auditoria,
    detalhe_log_auditoria,
    listar_permissoes_usuario,
    criar_permissao_usuario,
    deletar_permissao_usuario,
)
from .views.template_documento import (
    listar_templates_documento,
    criar_template_documento,
    detalhe_template_documento,
    atualizar_template_documento,
    listar_contratos,
    criar_contrato,
    detalhe_contrato,
    atualizar_contrato,
)
from .views.alfabetizacao_criancas import alfabetizacao_criancas
from .views.coordenacao_cache import (
    refresh_coordenacao_cache,
    listar_cache_coordenacao,
    listar_periodos_coordenacao,
)
from .views.indicadores_turma import indicadores_turma
from .views.analytics import contagem_registros, participacao_docente
from .views.prompts import (
    listar_prompt_categorias,
    salvar_prompt_template,
    criar_prompt_categoria,
    atualizar_prompt_categoria,
    deletar_prompt_categoria,
)
from .views.analise_producao import (
    upload_e_analise_escrita,
    upload_e_analise_desenho,
    atualizar_classificacao,
    servir_arquivo,
)
from .views.audio import upload_audio
# detalhe/atualizar/deletar de relatório vêm de views.avaliacao (acima);
# daqui só as funcionalidades que não existem lá.
from .views.relatorio import (
    gerar_relatorio,
    gerar_relatorio_por_crianca,
    baixar_pdf_relatorio,
    bulk_pdf_relatorios,
    listar_relatorios_coordenacao,
)

urlpatterns = [
    path('health/', health, name='health'),

    # Autenticação (JWT)
    path('auth/login/', LoginView.as_view(), name='login'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('auth/logout/', logout, name='logout'),
    path('auth/alterar-senha/', alterar_senha, name='alterar_senha'),
    path('auth/recuperar-senha/', recuperar_senha, name='recuperar_senha'),
    path('auth/confirmar-senha/', confirmar_senha, name='confirmar_senha'),
    path('me/', me, name='me'),

    # Instituições
    path('instituicoes/', listar_instituicoes, name='listar_instituicoes'),
    path('instituicoes/criar/', criar_instituicao, name='criar_instituicao'),
    path('instituicoes/<uuid:instituicao_id>/', detalhe_instituicao, name='detalhe_instituicao'),
    path('instituicoes/<uuid:instituicao_id>/atualizar/', atualizar_instituicao, name='atualizar_instituicao'),

    # Escolas
    path('escolas/', listar_escolas, name='listar_escolas'),
    # Dashboard do admin (/admin/dashboard no front): escolas da rede com os totais.
    path('admin/dashboard/', resumo_escolas, name='admin_dashboard'),
    path('escolas/criar/', criar_escola, name='criar_escola'),
    path('escolas/<uuid:escola_id>/', detalhe_escola, name='detalhe_escola'),
    path('escolas/<uuid:escola_id>/atualizar/', atualizar_escola, name='atualizar_escola'),

    # Especialistas
    path('especialistas/', listar_especialistas, name='listar_especialistas'),
    path('especialistas/criar/', criar_especialista, name='criar_especialista'),
    path('especialistas/<uuid:especialista_id>/', detalhe_especialista, name='detalhe_especialista'),
    path('especialistas/<uuid:especialista_id>/atualizar/', atualizar_especialista, name='atualizar_especialista'),

    # Usuários
    path('usuarios/', listar_usuarios, name='listar_usuarios'),
    path('usuarios/criar/', criar_usuario, name='criar_usuario'),
    path('usuarios/<uuid:usuario_id>/', detalhe_usuario, name='detalhe_usuario'),
    path('usuarios/<uuid:usuario_id>/atualizar/', atualizar_usuario, name='atualizar_usuario'),

    # Turmas
    path('turmas/', listar_turmas, name='listar_turmas'),
    path('turmas/criar/', criar_turma, name='criar_turma'),
    path('turmas/frequencia-registro/', listar_frequencias_registro, name='listar_frequencias_registro'),
    path('turmas/frequencia-registro/atualizar/', atualizar_frequencia_registro,
         name='atualizar_frequencia_registro'),
    path('turmas/<uuid:turma_id>/', detalhe_turma, name='detalhe_turma'),
    path('turmas/<uuid:turma_id>/atualizar/', atualizar_turma, name='atualizar_turma'),
    path('turmas/<uuid:turma_id>/professores/', listar_professores_turma, name='listar_professores_turma'),
    path('turmas/<uuid:turma_id>/professores/vincular/', vincular_professor_turma, name='vincular_professor_turma'),
    path('turmas/<uuid:turma_id>/professores/<uuid:usuario_id>/desvincular/',
         desvincular_professor_turma, name='desvincular_professor_turma'),

    # Disciplinas
    path('disciplinas/', listar_disciplinas, name='listar_disciplinas'),
    path('disciplinas/criar/', criar_disciplina, name='criar_disciplina'),
    path('disciplinas/<uuid:disciplina_id>/', detalhe_disciplina, name='detalhe_disciplina'),
    path('disciplinas/<uuid:disciplina_id>/atualizar/', atualizar_disciplina, name='atualizar_disciplina'),
    path('disciplinas/<uuid:disciplina_id>/professores/', listar_professores_disciplina, name='listar_professores_disciplina'),
    path('disciplinas/<uuid:disciplina_id>/professores/vincular/', vincular_usuario_disciplina, name='vincular_usuario_disciplina'),
    path('disciplinas/<uuid:disciplina_id>/professores/<uuid:usuario_id>/desvincular/',
         desvincular_usuario_disciplina, name='desvincular_usuario_disciplina'),

    # Alunos
    path('alunos/', listar_alunos, name='listar_alunos'),
    path('alunos/criar/', criar_aluno, name='criar_aluno'),
    path('alunos/<uuid:aluno_id>/', detalhe_aluno, name='detalhe_aluno'),
    path('alunos/<uuid:aluno_id>/atualizar/', atualizar_aluno, name='atualizar_aluno'),
    path('alunos/<uuid:aluno_id>/foto/', enviar_foto_aluno, name='enviar_foto_aluno'),

    # Projetos
    path('projetos/', listar_projetos, name='listar_projetos'),
    path('projetos/criar/', criar_projeto, name='criar_projeto'),
    path('projetos/<uuid:projeto_id>/', detalhe_projeto, name='detalhe_projeto'),
    path('projetos/<uuid:projeto_id>/atualizar/', atualizar_projeto, name='atualizar_projeto'),

    # Produções (Portfólio)
    path('producoes/', listar_producoes, name='listar_producoes'),
    path('producoes/criar/', criar_producao, name='criar_producao'),
    path('producoes/<uuid:producao_id>/', detalhe_producao, name='detalhe_producao'),
    path('producoes/<uuid:producao_id>/atualizar/', atualizar_producao, name='atualizar_producao'),
    path('producoes/<uuid:producao_id>/deletar/', deletar_producao, name='deletar_producao'),
    path('producoes/<uuid:producao_id>/alunos/', listar_alunos_producao, name='listar_alunos_producao'),
    path('producoes/<uuid:producao_id>/alunos/vincular/', vincular_aluno_producao, name='vincular_aluno_producao'),
    path('producoes/<uuid:producao_id>/alunos/<uuid:vinculo_id>/atualizar/',
         atualizar_vinculo_producao_aluno, name='atualizar_vinculo_producao_aluno'),
    path('producoes/<uuid:producao_id>/alunos/<uuid:aluno_id>/desvincular/',
         desvincular_aluno_producao, name='desvincular_aluno_producao'),

    # Registros de Escrita
    path('registros-escrita/', listar_registros_escrita, name='listar_registros_escrita'),
    path('registros-escrita/<uuid:registro_id>/', detalhe_registro_escrita, name='detalhe_registro_escrita'),
    path('registros-escrita/<uuid:registro_id>/atualizar/', atualizar_registro_escrita, name='atualizar_registro_escrita'),
    path('registros-escrita/<uuid:registro_id>/deletar/', deletar_registro_escrita, name='deletar_registro_escrita'),

    # Registros de Desenho
    path('registros-desenho/', listar_registros_desenho, name='listar_registros_desenho'),
    path('registros-desenho/<uuid:registro_id>/', detalhe_registro_desenho, name='detalhe_registro_desenho'),
    path('registros-desenho/<uuid:registro_id>/atualizar/', atualizar_registro_desenho, name='atualizar_registro_desenho'),
    path('registros-desenho/<uuid:registro_id>/deletar/', deletar_registro_desenho, name='deletar_registro_desenho'),

    # Produções com análise por IA (escrita/desenho) e arquivo original
    path('upload-escrita/', upload_e_analise_escrita, name='upload_e_analise_escrita'),
    path('upload-desenho/', upload_e_analise_desenho, name='upload_e_analise_desenho'),
    path('registros/classificacao/', atualizar_classificacao, name='atualizar_classificacao'),
    path('arquivo/<str:arquivo_hash>/', servir_arquivo, name='servir_arquivo'),

    # Áudio de observação (upload pela plataforma)
    path('upload-audio/', upload_audio, name='upload_audio'),

    # Registros de Leitura
    path('leitura/', listar_registros_leitura, name='listar_registros_leitura'),
    path('leitura/analisar/', iniciar_analise_leitura, name='iniciar_analise_leitura'),
    path('leitura/<uuid:registro_id>/status/', status_analise_leitura, name='status_analise_leitura'),
    path('leitura/<uuid:registro_id>/confirmar/', confirmar_analise_leitura, name='confirmar_analise_leitura'),
    path('leitura/<uuid:registro_id>/deletar/', deletar_analise_leitura, name='deletar_analise_leitura'),
    path('leitura/<uuid:registro_id>/', cancelar_analise_leitura, name='cancelar_analise_leitura'),

    # Campos Pedagógicos
    path('campos-pedagogicos/', listar_campos_pedagogicos, name='listar_campos_pedagogicos'),
    path('campos-pedagogicos/criar/', criar_campo_pedagogico, name='criar_campo_pedagogico'),
    path('campos-pedagogicos/<uuid:campo_id>/', detalhe_campo_pedagogico, name='detalhe_campo_pedagogico'),
    path('campos-pedagogicos/<uuid:campo_id>/atualizar/', atualizar_campo_pedagogico, name='atualizar_campo_pedagogico'),
    path('campos-pedagogicos/<uuid:campo_id>/desativar/', desativar_campo_pedagogico, name='desativar_campo_pedagogico'),

    # Habilidades BNCC (catálogo global)
    path('habilidades-bncc/', listar_habilidades_bncc, name='listar_habilidades_bncc'),
    path('habilidades-bncc/criar/', criar_habilidade_bncc, name='criar_habilidade_bncc'),
    path('habilidades-bncc/<uuid:habilidade_id>/', detalhe_habilidade_bncc, name='detalhe_habilidade_bncc'),
    path('habilidades-bncc/<uuid:habilidade_id>/atualizar/', atualizar_habilidade_bncc, name='atualizar_habilidade_bncc'),

    # Perguntas (formulário de observação)
    path('perguntas/', listar_perguntas, name='listar_perguntas'),
    path('perguntas/criar/', criar_pergunta, name='criar_pergunta'),
    path('perguntas/<uuid:pergunta_id>/', detalhe_pergunta, name='detalhe_pergunta'),
    path('perguntas/<uuid:pergunta_id>/atualizar/', atualizar_pergunta, name='atualizar_pergunta'),

    # Perguntas de Especialista
    path('perguntas-especialistas/', listar_perguntas_especialistas, name='listar_perguntas_especialistas'),
    path('perguntas-especialistas/criar/', criar_pergunta_especialista, name='criar_pergunta_especialista'),
    path('perguntas-especialistas/<uuid:pergunta_id>/', detalhe_pergunta_especialista, name='detalhe_pergunta_especialista'),
    path('perguntas-especialistas/<uuid:pergunta_id>/atualizar/', atualizar_pergunta_especialista, name='atualizar_pergunta_especialista'),

    # Registros de Observação
    path('registros-observacao/', listar_registros_observacao, name='listar_registros_observacao'),
    path('registros-observacao/criar/', criar_registro_observacao, name='criar_registro_observacao'),
    path('registros-observacao/<uuid:registro_id>/', detalhe_registro_observacao, name='detalhe_registro_observacao'),
    path('registros-observacao/<uuid:registro_id>/atualizar/', atualizar_registro_observacao, name='atualizar_registro_observacao'),
    path('registros-observacao/<uuid:registro_id>/deletar/', deletar_registro_observacao, name='deletar_registro_observacao'),

    # Observações de Transcrição
    path('observacoes-transcricao/', listar_observacoes_transcricao, name='listar_observacoes_transcricao'),
    path('observacoes-transcricao/criar/', criar_observacao_transcricao, name='criar_observacao_transcricao'),
    path('observacoes-transcricao/<uuid:observacao_id>/', detalhe_observacao_transcricao, name='detalhe_observacao_transcricao'),
    path('observacoes-transcricao/<uuid:observacao_id>/atualizar/', atualizar_observacao_transcricao, name='atualizar_observacao_transcricao'),
    path('observacoes-transcricao/<uuid:observacao_id>/deletar/', deletar_observacao_transcricao, name='deletar_observacao_transcricao'),

    # Planejamento (fluxo com IA)
    path('planejamento/', listar_planejamentos, name='listar_planejamentos'),
    path('planejamento/processar-arquivo/', processar_arquivo_planejamento, name='processar_arquivo_planejamento'),
    path('planejamento/sugerir-atividades/', sugerir_atividades_planejamento, name='sugerir_atividades_planejamento'),
    path('planejamento/sugerir-bncc/', sugerir_bncc_planejamento, name='sugerir_bncc_planejamento'),
    path('planejamento/criar/', criar_planejamento_semanal, name='criar_planejamento_semanal'),
    path('planejamento/<uuid:planejamento_id>/atualizar/', atualizar_planejamento_semanal, name='atualizar_planejamento_semanal'),
    path('planejamento/aplicar-em-semanas/', aplicar_planejamento_em_semanas, name='aplicar_planejamento_em_semanas'),

    # Períodos Avaliativos
    path('periodos-avaliativos/', listar_periodos_avaliativos, name='listar_periodos_avaliativos'),
    path('periodos-avaliativos/criar/', criar_periodo_avaliativo, name='criar_periodo_avaliativo'),
    path('periodos-avaliativos/<uuid:periodo_id>/', detalhe_periodo_avaliativo, name='detalhe_periodo_avaliativo'),
    path('periodos-avaliativos/<uuid:periodo_id>/atualizar/', atualizar_periodo_avaliativo, name='atualizar_periodo_avaliativo'),
    path('periodos-avaliativos/<uuid:periodo_id>/excluir/', excluir_periodo_avaliativo, name='excluir_periodo_avaliativo'),

    # Templates de Relatório
    path('relatorio-templates/', listar_relatorio_templates, name='listar_relatorio_templates'),
    path('relatorio-templates/criar/', criar_relatorio_template, name='criar_relatorio_template'),
    path('relatorio-templates/<uuid:template_id>/', detalhe_relatorio_template, name='detalhe_relatorio_template'),
    path('relatorio-templates/<uuid:template_id>/atualizar/', atualizar_relatorio_template, name='atualizar_relatorio_template'),

    # Relatórios
    # Rotas com segmento fixo ('bulk-pdf', 'coordenacao') ficam antes das com
    # <uuid:...> por clareza — o conversor uuid já não as capturaria.
    path('relatorios/bulk-pdf/', bulk_pdf_relatorios, name='bulk_pdf_relatorios'),
    path('relatorios/coordenacao/', listar_relatorios_coordenacao, name='listar_relatorios_coordenacao'),
    path('relatorios/<uuid:relatorio_id>/pdf/download/', baixar_pdf_relatorio, name='baixar_pdf_relatorio'),
    path('gerar-relatorio/', gerar_relatorio, name='gerar_relatorio'),
    path('gerar-relatorio/<uuid:crianca_id>/', gerar_relatorio_por_crianca, name='gerar_relatorio_por_crianca'),
    path('relatorios/', listar_relatorios, name='listar_relatorios'),
    path('relatorios/criar/', criar_relatorio, name='criar_relatorio'),
    path('relatorios/<uuid:relatorio_id>/', detalhe_relatorio, name='detalhe_relatorio'),
    path('relatorios/<uuid:relatorio_id>/atualizar/', atualizar_relatorio, name='atualizar_relatorio'),
    path('relatorios/<uuid:relatorio_id>/revisar/', revisar_relatorio, name='revisar_relatorio'),
    path('relatorios/<uuid:relatorio_id>/deletar/', deletar_relatorio, name='deletar_relatorio'),

    # Notificações
    path('notificacoes/', listar_minhas_notificacoes, name='listar_minhas_notificacoes'),
    path('notificacoes/criar/', criar_notificacao, name='criar_notificacao'),
    path('notificacoes/<uuid:notificacao_id>/marcar-lida/', marcar_notificacao_lida, name='marcar_notificacao_lida'),

    # Metas PAEE
    path('metas-paee/', listar_metas_paee, name='listar_metas_paee'),
    path('metas-paee/criar/', criar_meta_paee, name='criar_meta_paee'),
    path('metas-paee/<uuid:meta_id>/', detalhe_meta_paee, name='detalhe_meta_paee'),
    path('metas-paee/<uuid:meta_id>/atualizar/', atualizar_meta_paee, name='atualizar_meta_paee'),

    # Sessões de Especialista
    path('sessoes-especialista/', listar_sessoes_especialista, name='listar_sessoes_especialista'),
    path('sessoes-especialista/criar/', criar_sessao_especialista, name='criar_sessao_especialista'),
    path('sessoes-especialista/<uuid:sessao_id>/', detalhe_sessao_especialista, name='detalhe_sessao_especialista'),
    path('sessoes-especialista/<uuid:sessao_id>/atualizar/', atualizar_sessao_especialista, name='atualizar_sessao_especialista'),
    path('sessoes-especialista/<uuid:sessao_id>/metas/', listar_metas_sessao, name='listar_metas_sessao'),
    path('sessoes-especialista/<uuid:sessao_id>/metas/vincular/', vincular_meta_sessao, name='vincular_meta_sessao'),
    path('sessoes-especialista/<uuid:sessao_id>/metas/<uuid:meta_id>/desvincular/',
         desvincular_meta_sessao, name='desvincular_meta_sessao'),

    # Tarefas PAEE
    path('tarefas-paee/', listar_tarefas_paee, name='listar_tarefas_paee'),
    path('tarefas-paee/criar/', criar_tarefa_paee, name='criar_tarefa_paee'),
    path('tarefas-paee/<uuid:tarefa_id>/', detalhe_tarefa_paee, name='detalhe_tarefa_paee'),
    path('tarefas-paee/<uuid:tarefa_id>/atualizar/', atualizar_tarefa_paee, name='atualizar_tarefa_paee'),

    # Dispositivos gravadores — plataforma
    path('dispositivos/codigo/', gerar_codigo_pareamento, name='gerar_codigo_pareamento'),
    path('dispositivos/', listar_dispositivos, name='listar_dispositivos'),
    path('dispositivos/<uuid:dispositivo_id>/', atualizar_dispositivo, name='atualizar_dispositivo'),
    path('dispositivos/<uuid:dispositivo_id>/revogar/', revogar_dispositivo, name='revogar_dispositivo'),
    path('dispositivos/<uuid:dispositivo_id>/reativar/', reativar_dispositivo, name='reativar_dispositivo'),

    # Dispositivos gravadores — firmware (sem token de usuário)
    path('dispositivos/parear/', parear, name='parear_dispositivo'),
    path('dispositivos/audio/', upload_audio_dispositivo, name='upload_audio_dispositivo'),
    path('dispositivos/audio/<uuid:upload_id>/', consultar_audio, name='consultar_audio'),
    path('dispositivos/status/', status_dispositivo, name='status_dispositivo'),

    # Tickets
    path('tickets/', listar_tickets, name='listar_tickets'),
    path('tickets/criar/', criar_ticket, name='criar_ticket'),
    path('tickets/<uuid:ticket_id>/', detalhe_ticket, name='detalhe_ticket'),
    path('tickets/<uuid:ticket_id>/atualizar/', atualizar_ticket, name='atualizar_ticket'),
    path('tickets/<uuid:ticket_id>/respostas/', listar_respostas_ticket, name='listar_respostas_ticket'),
    path('tickets/<uuid:ticket_id>/responder/', responder_ticket, name='responder_ticket'),
    path('tickets/<uuid:ticket_id>/anexar/', anexar_arquivo_ticket, name='anexar_arquivo_ticket'),
    path('tickets/respostas/<uuid:resposta_id>/anexar/', anexar_arquivo_resposta, name='anexar_arquivo_resposta'),

    # Auditoria e Permissões
    path('logs-auditoria/', listar_logs_auditoria, name='listar_logs_auditoria'),
    path('logs-auditoria/<int:log_id>/', detalhe_log_auditoria, name='detalhe_log_auditoria'),
    path('permissoes-usuario/', listar_permissoes_usuario, name='listar_permissoes_usuario'),
    path('permissoes-usuario/criar/', criar_permissao_usuario, name='criar_permissao_usuario'),
    path('permissoes-usuario/<uuid:permissao_id>/deletar/', deletar_permissao_usuario, name='deletar_permissao_usuario'),

    # Documentos e Contratos
    path('templates-documento/', listar_templates_documento, name='listar_templates_documento'),
    path('templates-documento/criar/', criar_template_documento, name='criar_template_documento'),
    path('templates-documento/<uuid:template_id>/', detalhe_template_documento, name='detalhe_template_documento'),
    path('templates-documento/<uuid:template_id>/atualizar/', atualizar_template_documento, name='atualizar_template_documento'),
    path('contratos/', listar_contratos, name='listar_contratos'),
    path('contratos/criar/', criar_contrato, name='criar_contrato'),
    path('contratos/<uuid:contrato_id>/', detalhe_contrato, name='detalhe_contrato'),
    path('contratos/<uuid:contrato_id>/atualizar/', atualizar_contrato, name='atualizar_contrato'),

    # Coordenação — drill-down de alfabetização
    path('coordenacao/alfabetizacao/alunos/', alfabetizacao_criancas, name='alfabetizacao_criancas'),
    path('coordenacao/cache/', listar_cache_coordenacao, name='listar_cache_coordenacao'),
    path('coordenacao/periodos/', listar_periodos_coordenacao, name='listar_periodos_coordenacao'),
    path('internal/coordenacao/refresh/', refresh_coordenacao_cache, name='refresh_coordenacao_cache'),
    path('coordenacao/indicadores-turma/', indicadores_turma, name='indicadores_turma'),
    path('analytics/contagem-registros/', contagem_registros, name='contagem_registros'),
    path('analytics/participacao-docente/', participacao_docente, name='participacao_docente'),

    # Biblioteca de Prompts (IA)
    path('prompts/categorias/', listar_prompt_categorias, name='listar_prompt_categorias'),
    path('prompts/categorias/criar/', criar_prompt_categoria, name='criar_prompt_categoria'),
    path('prompts/categorias/<uuid:categoria_id>/atualizar/', atualizar_prompt_categoria, name='atualizar_prompt_categoria'),
    path('prompts/categorias/<uuid:categoria_id>/deletar/', deletar_prompt_categoria, name='deletar_prompt_categoria'),
    path('prompts/salvar/', salvar_prompt_template, name='salvar_prompt_template'),
]