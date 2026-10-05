from django.contrib import admin

from .models import (
    Instituicao, Escola, Especialista, Usuario, Turma, UsuarioTurma,
    Disciplina, UsuarioDisciplina, Aluno, Projeto,
    Producao, ProducaoAluno,
    RegistroEscrita, RegistroDesenho, RegistroLeitura,
    CampoPedagogico, HabilidadeBNCC, Pergunta, PerguntaEspecialista,
    RegistroObservacao, ObservacaoTranscricao,
    PlanejamentoSemanal, PlanejamentoDiario, PlanejamentoHabilidade,
    PeriodoAvaliativo, RelatorioTemplate, Relatorio,
    Notificacao, MetaPAEE, SessaoEspecialista, SessaoPAEEMeta, TarefaPAEE,
    DispositivoGravador, DispositivoGravadorTurma, CodigoPareamento,
    CodigoPareamentoTurma, AudioDispositivo,
    PromptCategoria, PromptTemplate, OpenAIUsage, CoordenacaoCache,
    LogAuditoria, PermissaoUsuario,
    Ticket, RespostaTicket, AnexoTicket,
    TemplateDocumento, Contrato,
)


# ============================================================
# Núcleo: Instituição, Escola, Usuário
# ============================================================

@admin.register(Instituicao)
class InstituicaoAdmin(admin.ModelAdmin):
    list_display = ['nome', 'cnpj', 'cidade', 'estado', 'ativa', 'criado_em']
    list_filter = ['ativa', 'estado']
    search_fields = ['nome', 'cnpj', 'email_institucional']


@admin.register(Escola)
class EscolaAdmin(admin.ModelAdmin):
    list_display = ['nome', 'instituicao', 'tipo_unidade', 'cidade', 'ativa']
    list_filter = ['ativa', 'tipo_unidade', 'instituicao']
    search_fields = ['nome', 'cnpj']
    autocomplete_fields = ['instituicao']


@admin.register(Especialista)
class EspecialistaAdmin(admin.ModelAdmin):
    list_display = ['tipo_especialista', 'escola', 'instituicao']
    list_filter = ['tipo_especialista', 'instituicao']
    search_fields = ['tipo_especialista']
    autocomplete_fields = ['escola', 'instituicao']


@admin.register(Usuario)
class UsuarioAdmin(admin.ModelAdmin):
    list_display = ['nome', 'email', 'nivel', 'escola', 'instituicao', 'is_active', 'is_staff']
    list_filter = ['nivel', 'is_active', 'is_staff', 'instituicao']
    search_fields = ['nome', 'email']
    autocomplete_fields = ['escola', 'instituicao', 'especialista']
    exclude = ['password']
    readonly_fields = ['last_login']


@admin.register(Turma)
class TurmaAdmin(admin.ModelAdmin):
    list_display = ['nome', 'escola', 'turno', 'ano_letivo', 'etapa', 'ativa']
    list_filter = ['ativa', 'turno', 'etapa', 'ano_letivo', 'escola']
    search_fields = ['nome']
    autocomplete_fields = ['escola', 'instituicao']


@admin.register(UsuarioTurma)
class UsuarioTurmaAdmin(admin.ModelAdmin):
    list_display = ['usuario', 'turma', 'data_vinculo']
    autocomplete_fields = ['usuario', 'turma']


@admin.register(Disciplina)
class DisciplinaAdmin(admin.ModelAdmin):
    list_display = ['nome', 'escola', 'ativo']
    list_filter = ['ativo', 'escola']
    search_fields = ['nome']
    autocomplete_fields = ['escola', 'instituicao']


@admin.register(UsuarioDisciplina)
class UsuarioDisciplinaAdmin(admin.ModelAdmin):
    list_display = ['usuario', 'disciplina', 'escola']
    autocomplete_fields = ['usuario', 'disciplina', 'escola', 'instituicao']


@admin.register(Aluno)
class AlunoAdmin(admin.ModelAdmin):
    list_display = ['nome_completo', 'turma', 'escola', 'status_vinculo', 'data_nascimento']
    list_filter = ['status_vinculo', 'genero', 'escola']
    search_fields = ['nome_completo', 'nome_responsavel']
    autocomplete_fields = ['turma', 'escola', 'instituicao']


@admin.register(Projeto)
class ProjetoAdmin(admin.ModelAdmin):
    list_display = ['nome', 'escola', 'status', 'data_inicio', 'data_fim']
    list_filter = ['status', 'escola']
    search_fields = ['nome']
    autocomplete_fields = ['escola', 'instituicao']


# ============================================================
# Portfólio
# ============================================================

class ProducaoAlunoInline(admin.TabularInline):
    model = ProducaoAluno
    extra = 0
    autocomplete_fields = ['aluno']


@admin.register(Producao)
class ProducaoAdmin(admin.ModelAdmin):
    list_display = ['titulo', 'tipo', 'turma', 'escola', 'professor', 'data_registro']
    list_filter = ['tipo', 'escola']
    search_fields = ['titulo', 'arquivo_nome']
    autocomplete_fields = ['turma', 'professor', 'projeto', 'escola', 'instituicao']
    inlines = [ProducaoAlunoInline]


@admin.register(ProducaoAluno)
class ProducaoAlunoAdmin(admin.ModelAdmin):
    list_display = ['producao', 'aluno', 'destaque', 'incluir_relatorio']
    list_filter = ['destaque', 'incluir_relatorio']
    autocomplete_fields = ['producao', 'aluno']


# ============================================================
# Registros de análise (escrita, desenho, leitura)
# ============================================================

@admin.register(RegistroEscrita)
class RegistroEscritaAdmin(admin.ModelAdmin):
    list_display = ['aluno', 'etapa', 'turma', 'professor', 'criado_em']
    list_filter = ['etapa', 'escola']
    autocomplete_fields = ['aluno', 'turma', 'professor', 'escola', 'instituicao']


@admin.register(RegistroDesenho)
class RegistroDesenhoAdmin(admin.ModelAdmin):
    list_display = ['aluno', 'atividade', 'fase_desenho', 'turma', 'criado_em']
    list_filter = ['fase_desenho', 'escola']
    autocomplete_fields = ['aluno', 'turma', 'professor', 'escola', 'instituicao']


@admin.register(RegistroLeitura)
class RegistroLeituraAdmin(admin.ModelAdmin):
    list_display = ['aluno', 'status', 'classe_predita', 'classe_escolhida', 'criado_em']
    list_filter = ['status', 'escola']
    search_fields = ['nara_job_id']
    autocomplete_fields = ['aluno', 'turma', 'professor', 'escola', 'instituicao']


# ============================================================
# Pedagógico: campos, BNCC, perguntas, observações
# ============================================================

@admin.register(CampoPedagogico)
class CampoPedagogicoAdmin(admin.ModelAdmin):
    list_display = ['nome', 'etapa', 'escola', 'ativo']
    list_filter = ['etapa', 'ativo']
    search_fields = ['nome']
    autocomplete_fields = ['escola', 'instituicao']


@admin.register(HabilidadeBNCC)
class HabilidadeBNCCAdmin(admin.ModelAdmin):
    list_display = ['codigo', 'componente_curricular', 'ano_serie', 'ativa']
    list_filter = ['componente_curricular', 'ativa']
    search_fields = ['codigo', 'descricao']


@admin.register(Pergunta)
class PerguntaAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'origem', 'faixa_etaria', 'escola', 'ativa']
    list_filter = ['origem', 'ativa', 'faixa_etaria']
    search_fields = ['pergunta', 'faixa_etaria']
    autocomplete_fields = ['campo_experiencia', 'habilidade_bncc', 'escola', 'instituicao']

@admin.register(PerguntaEspecialista)
class PerguntaEspecialistaAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'nivel', 'status', 'usuario_especialista']
    list_filter = ['status', 'nivel']
    search_fields = ['pergunta']
    autocomplete_fields = ['campo_experiencia', 'habilidade_bncc', 'usuario_especialista', 'escola', 'instituicao']


@admin.register(RegistroObservacao)
class RegistroObservacaoAdmin(admin.ModelAdmin):
    list_display = ['aluno', 'resposta', 'data_observacao', 'professor']
    list_filter = ['escola']
    autocomplete_fields = ['pergunta', 'pergunta_especialista', 'aluno', 'professor', 'escola', 'instituicao']


@admin.register(ObservacaoTranscricao)
class ObservacaoTranscricaoAdmin(admin.ModelAdmin):
    list_display = ['aluno_nome', 'aluno', 'turma', 'tipo_observacao', 'data_observacao']
    list_filter = ['tipo_observacao', 'escola']
    search_fields = ['aluno_nome']
    autocomplete_fields = ['aluno', 'turma', 'professor', 'escola', 'instituicao']


# ============================================================
# Planejamento
# ============================================================

class PlanejamentoDiarioInline(admin.TabularInline):
    model = PlanejamentoDiario
    extra = 0
    fields = ['dia_semana', 'data', 'atividades_propostas']


@admin.register(PlanejamentoSemanal)
class PlanejamentoSemanalAdmin(admin.ModelAdmin):
    list_display = ['turma', 'semana_inicio', 'semana_fim', 'ano_letivo', 'professor']
    list_filter = ['ano_letivo', 'escola']
    search_fields = ['turma__nome']
    autocomplete_fields = ['turma', 'professor', 'escola', 'instituicao']
    inlines = [PlanejamentoDiarioInline]


@admin.register(PlanejamentoDiario)
class PlanejamentoDiarioAdmin(admin.ModelAdmin):
    list_display = ['planejamento_semanal', 'dia_semana', 'data']
    list_filter = ['dia_semana', 'escola']
    search_fields = ['planejamento_semanal__turma__nome', 'atividades_propostas']
    autocomplete_fields = ['planejamento_semanal', 'escola', 'instituicao']


@admin.register(PlanejamentoHabilidade)
class PlanejamentoHabilidadeAdmin(admin.ModelAdmin):
    list_display = ['planejamento_diario', 'habilidade_bncc']
    autocomplete_fields = ['planejamento_diario', 'habilidade_bncc']


# ============================================================
# Avaliação e relatórios
# ============================================================

@admin.register(PeriodoAvaliativo)
class PeriodoAvaliativoAdmin(admin.ModelAdmin):
    list_display = ['descricao', 'tipo_periodo', 'ano', 'numero', 'escola']
    list_filter = ['tipo_periodo', 'ano', 'escola']
    autocomplete_fields = ['escola', 'instituicao']


@admin.register(RelatorioTemplate)
class RelatorioTemplateAdmin(admin.ModelAdmin):
    list_display = ['nome', 'modelo', 'escola', 'ativo']
    list_filter = ['modelo', 'ativo', 'escola']
    search_fields = ['nome']
    autocomplete_fields = ['escola', 'instituicao']


@admin.register(Relatorio)
class RelatorioAdmin(admin.ModelAdmin):
    list_display = ['aluno', 'periodo', 'template', 'revisado_por', 'escola', 'criado_em']
    list_filter = ['escola']
    autocomplete_fields = ['aluno', 'template', 'revisado_por', 'escola', 'instituicao']


# ============================================================
# Notificações e PAEE
# ============================================================

@admin.register(Notificacao)
class NotificacaoAdmin(admin.ModelAdmin):
    list_display = ['titulo', 'tipo', 'usuario', 'remetente', 'lido_em', 'criado_em']
    list_filter = ['tipo', 'escola']
    search_fields = ['titulo', 'conteudo']
    autocomplete_fields = ['usuario', 'remetente', 'escola', 'instituicao']


class TarefaPAEEInline(admin.TabularInline):
    model = TarefaPAEE
    extra = 0
    fields = ['descricao', 'concluida', 'data_conclusao']


@admin.register(MetaPAEE)
class MetaPAEEAdmin(admin.ModelAdmin):
    list_display = ['aluno', 'categoria', 'status', 'inicio', 'fim', 'usuario_especialista']
    list_filter = ['status', 'categoria', 'escola']
    search_fields = ['aluno__nome_completo', 'objetivo']
    autocomplete_fields = ['aluno', 'usuario_especialista', 'turma', 'escola', 'instituicao']
    inlines = [TarefaPAEEInline]


@admin.register(SessaoEspecialista)
class SessaoEspecialistaAdmin(admin.ModelAdmin):
    list_display = ['aluno', 'data_atendimento', 'duracao', 'status', 'usuario_especialista']
    list_filter = ['status', 'escola']
    search_fields = ['aluno__nome_completo', 'resumo']
    autocomplete_fields = ['aluno', 'usuario_especialista', 'turma', 'escola', 'instituicao']


@admin.register(SessaoPAEEMeta)
class SessaoPAEEMetaAdmin(admin.ModelAdmin):
    list_display = ['sessao_especialista', 'meta_paee']
    autocomplete_fields = ['sessao_especialista', 'meta_paee']


@admin.register(TarefaPAEE)
class TarefaPAEEAdmin(admin.ModelAdmin):
    list_display = ['meta_paee', 'descricao', 'concluida', 'data_conclusao']
    list_filter = ['concluida', 'escola']
    autocomplete_fields = ['meta_paee', 'professor_conclusao', 'escola', 'instituicao']


# ============================================================
# Dispositivos gravadores e áudios
# ============================================================

@admin.register(DispositivoGravador)
class DispositivoGravadorAdmin(admin.ModelAdmin):
    list_display = ['nome', 'device_id', 'professor', 'turma_ativa', 'ativo', 'visto_ultimo']
    list_filter = ['ativo', 'escola']
    search_fields = ['device_id', 'nome']
    autocomplete_fields = ['professor', 'turma_ativa', 'escola', 'instituicao']


@admin.register(DispositivoGravadorTurma)
class DispositivoGravadorTurmaAdmin(admin.ModelAdmin):
    list_display = ['dispositivo', 'turma']
    autocomplete_fields = ['dispositivo', 'turma']


@admin.register(CodigoPareamento)
class CodigoPareamentoAdmin(admin.ModelAdmin):
    list_display = ['codigo', 'professor', 'dispositivo', 'expira_em', 'usado_em']
    search_fields = ['codigo']
    list_filter = ['escola']
    autocomplete_fields = ['professor', 'dispositivo', 'escola', 'instituicao']


@admin.register(CodigoPareamentoTurma)
class CodigoPareamentoTurmaAdmin(admin.ModelAdmin):
    list_display = ['codigo_pareamento', 'turma']
    autocomplete_fields = ['codigo_pareamento', 'turma']


@admin.register(AudioDispositivo)
class AudioDispositivoAdmin(admin.ModelAdmin):
    list_display = ['dispositivo', 'status', 'turma_resultado', 'total_observacoes', 'data_recebimento']
    list_filter = ['status', 'escola']
    autocomplete_fields = ['dispositivo', 'professor', 'turma', 'observacao', 'escola', 'instituicao']


# ============================================================
# IA / Prompts / Cache
# ============================================================

@admin.register(PromptCategoria)
class PromptCategoriaAdmin(admin.ModelAdmin):
    list_display = ['titulo', 'ativo']
    list_filter = ['ativo']
    search_fields = ['titulo']


@admin.register(PromptTemplate)
class PromptTemplateAdmin(admin.ModelAdmin):
    list_display = ['categoria', 'escola']
    list_filter = ['categoria', 'escola']
    autocomplete_fields = ['categoria', 'escola', 'instituicao']


@admin.register(OpenAIUsage)
class OpenAIUsageAdmin(admin.ModelAdmin):
    list_display = ['model', 'usuario', 'escola', 'total_cost', 'criado_em']
    list_filter = ['model', 'escola']
    autocomplete_fields = ['usuario', 'escola', 'instituicao']
    date_hierarchy = 'criado_em'


@admin.register(CoordenacaoCache)
class CoordenacaoCacheAdmin(admin.ModelAdmin):
    list_display = ['escola', 'data_referencia', 'janela_dias', 'versao_schema']
    list_filter = ['escola']
    autocomplete_fields = ['escola', 'instituicao']


# ============================================================
# Auditoria e permissões
# ============================================================

@admin.register(LogAuditoria)
class LogAuditoriaAdmin(admin.ModelAdmin):
    list_display = ['acao', 'tabela_afetada', 'registro_id', 'usuario', 'criado_em']
    list_filter = ['acao', 'tabela_afetada']
    date_hierarchy = 'criado_em'
    autocomplete_fields = ['usuario', 'escola', 'instituicao']


@admin.register(PermissaoUsuario)
class PermissaoUsuarioAdmin(admin.ModelAdmin):
    list_display = ['usuario', 'modulo', 'acao', 'concedido', 'escola']
    list_filter = ['modulo', 'acao', 'concedido']
    autocomplete_fields = ['usuario', 'escola', 'instituicao', 'concedido_por']


# ============================================================
# Tickets de suporte
# ============================================================

class RespostaTicketInline(admin.TabularInline):
    model = RespostaTicket
    extra = 0
    fields = ['usuario', 'descricao', 'criado_em']
    readonly_fields = ['criado_em']
    autocomplete_fields = ['usuario']


class AnexoTicketInline(admin.TabularInline):
    model = AnexoTicket
    extra = 0
    fk_name = 'ticket'


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ['protocolo', 'titulo', 'status', 'categoria', 'prioridade', 'usuario_solicitante', 'responsavel']
    list_filter = ['status', 'categoria', 'prioridade']
    search_fields = ['protocolo', 'titulo']
    autocomplete_fields = ['usuario_solicitante', 'escola', 'instituicao', 'responsavel']
    inlines = [RespostaTicketInline, AnexoTicketInline]


@admin.register(RespostaTicket)
class RespostaTicketAdmin(admin.ModelAdmin):
    list_display = ['ticket', 'usuario', 'criado_em']
    search_fields = ['descricao', 'ticket__protocolo']
    autocomplete_fields = ['ticket', 'usuario', 'escola', 'instituicao']


@admin.register(AnexoTicket)
class AnexoTicketAdmin(admin.ModelAdmin):
    list_display = ['arquivo_nome', 'ticket', 'ticket_reply', 'tamanho_bytes']
    autocomplete_fields = ['ticket', 'ticket_reply']


# ============================================================
# Documentos e contratos
# ============================================================

@admin.register(TemplateDocumento)
class TemplateDocumentoAdmin(admin.ModelAdmin):
    list_display = ['titulo', 'tipo', 'ativo', 'responsavel', 'criado_por']
    list_filter = ['tipo', 'ativo']
    search_fields = ['titulo']
    autocomplete_fields = ['responsavel', 'criado_por', 'atualizado_por', 'escola', 'instituicao']


@admin.register(Contrato)
class ContratoAdmin(admin.ModelAdmin):
    list_display = ['id', 'escola', 'status', 'template', 'responsavel', 'gerado_por', 'criado_em']
    list_filter = ['status', 'escola']
    autocomplete_fields = ['template', 'escola', 'instituicao', 'responsavel', 'gerado_por', 'atualizado_por']