from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views.auth import LoginView, me, alterar_senha, recuperar_senha, confirmar_senha
from .views.health import health
from .views.instituicao import (
    listar_instituicoes,
    criar_instituicao,
    detalhe_instituicao,
    atualizar_instituicao,
)
from .views.escola import (
    listar_escolas,
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
    criar_registro_escrita,
    detalhe_registro_escrita,
    atualizar_registro_escrita,
    deletar_registro_escrita,
    listar_registros_desenho,
    criar_registro_desenho,
    detalhe_registro_desenho,
    atualizar_registro_desenho,
    deletar_registro_desenho,
    listar_registros_leitura,
    criar_registro_leitura,
    detalhe_registro_leitura,
    atualizar_registro_leitura,
    deletar_registro_leitura,
)
from .views.campo_pedagogico import (
    listar_campos_pedagogicos,
    criar_campo_pedagogico,
    detalhe_campo_pedagogico,
    atualizar_campo_pedagogico,
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

urlpatterns = [
    path('health/', health, name='health'),

    # Autenticação (JWT)
    path('auth/login/', LoginView.as_view(), name='login'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
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
    path('registros-escrita/criar/', criar_registro_escrita, name='criar_registro_escrita'),
    path('registros-escrita/<uuid:registro_id>/', detalhe_registro_escrita, name='detalhe_registro_escrita'),
    path('registros-escrita/<uuid:registro_id>/atualizar/', atualizar_registro_escrita, name='atualizar_registro_escrita'),
    path('registros-escrita/<uuid:registro_id>/deletar/', deletar_registro_escrita, name='deletar_registro_escrita'),

    # Registros de Desenho
    path('registros-desenho/', listar_registros_desenho, name='listar_registros_desenho'),
    path('registros-desenho/criar/', criar_registro_desenho, name='criar_registro_desenho'),
    path('registros-desenho/<uuid:registro_id>/', detalhe_registro_desenho, name='detalhe_registro_desenho'),
    path('registros-desenho/<uuid:registro_id>/atualizar/', atualizar_registro_desenho, name='atualizar_registro_desenho'),
    path('registros-desenho/<uuid:registro_id>/deletar/', deletar_registro_desenho, name='deletar_registro_desenho'),

    # Registros de Leitura
    path('registros-leitura/', listar_registros_leitura, name='listar_registros_leitura'),
    path('registros-leitura/criar/', criar_registro_leitura, name='criar_registro_leitura'),
    path('registros-leitura/<uuid:registro_id>/', detalhe_registro_leitura, name='detalhe_registro_leitura'),
    path('registros-leitura/<uuid:registro_id>/atualizar/', atualizar_registro_leitura, name='atualizar_registro_leitura'),
    path('registros-leitura/<uuid:registro_id>/deletar/', deletar_registro_leitura, name='deletar_registro_leitura'),

    # Campos Pedagógicos
    path('campos-pedagogicos/', listar_campos_pedagogicos, name='listar_campos_pedagogicos'),
    path('campos-pedagogicos/criar/', criar_campo_pedagogico, name='criar_campo_pedagogico'),
    path('campos-pedagogicos/<uuid:campo_id>/', detalhe_campo_pedagogico, name='detalhe_campo_pedagogico'),
    path('campos-pedagogicos/<uuid:campo_id>/atualizar/', atualizar_campo_pedagogico, name='atualizar_campo_pedagogico'),

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
]