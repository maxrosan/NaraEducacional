from django.contrib import admin
from .models import (
    AudioDispositivo,
    CodigoPareamento,
    DispositivoGravador,
    MetaPAEE,
    RegistroEscrita,
    RegistroDesenho,
    SessaoEspecialista,
    TarefaPAEE,
)

@admin.register(RegistroEscrita)
class RegistroEscritaAdmin(admin.ModelAdmin):
    list_display = ['nome_aluno', 'etapa_ia', 'professora', 'data_criacao']
    list_filter = ['etapa_ia', 'data_criacao', 'serie_aluno']
    search_fields = ['nome_aluno', 'professora', 'turma_id']
    readonly_fields = ['data_criacao', 'data_atualizacao', 'arquivo_hash']
    
    fieldsets = (
        ('Informações do Aluno', {
            'fields': ('nome_aluno', 'turma_id', 'serie_aluno')
        }),
        ('Arquivo', {
            'fields': ('arquivo_nome', 'arquivo_hash', 'arquivo_path', 'arquivo_original', 'tamanho_arquivo', 'tipo_arquivo')
        }),
        ('Análise da IA', {
            'fields': ('etapa_ia', 'analise_detalhada')
        }),
        ('Professora', {
            'fields': ('professora', 'anotacoes_professora')
        }),
        ('Metadados', {
            'fields': ('data_criacao', 'data_atualizacao')
        }),
    )

@admin.register(RegistroDesenho)
class RegistroDesenhoAdmin(admin.ModelAdmin):
    list_display = ['nome_aluno', 'fase_desenho', 'atividade', 'professora', 'data_criacao']
    list_filter = ['fase_desenho', 'serie_aluno', 'data_criacao']
    search_fields = ['nome_aluno', 'professora', 'atividade']
    readonly_fields = ['arquivo_hash', 'data_criacao', 'data_atualizacao']
    
    fieldsets = (
        ('Dados do Aluno', {
            'fields': ('nome_aluno', 'turma_id', 'serie_aluno')
        }),
        ('Atividade', {
            'fields': ('atividade', 'contexto')
        }),
        ('Análise da IA', {
            'fields': ('fase_desenho', 'elementos_detectados', 'analise_detalhada')
        }),
        ('Professora', {
            'fields': ('professora', 'anotacoes_professora')
        }),
        ('Arquivo', {
            'fields': ('arquivo_nome', 'arquivo_hash', 'arquivo_original', 'tamanho_arquivo', 'tipo_arquivo')
        }),
        ('Timestamps', {
            'fields': ('data_criacao', 'data_atualizacao')
        })
    )


@admin.register(SessaoEspecialista)
class SessaoEspecialistaAdmin(admin.ModelAdmin):
    list_display = ['crianca', 'especialista', 'data_atendimento', 'status']
    list_filter = ['status', 'data_atendimento']
    search_fields = ['crianca__nome_completo', 'especialista__nome']
    readonly_fields = ['data_criacao', 'data_atualizacao']
    filter_horizontal = ['metas_trabalhadas']


@admin.register(MetaPAEE)
class MetaPAEEAdmin(admin.ModelAdmin):
    list_display = ['crianca', 'categoria', 'especialista', 'inicio', 'fim', 'status']
    list_filter = ['categoria', 'status', 'inicio']
    search_fields = ['crianca__nome_completo', 'especialista__nome', 'objetivo']
    readonly_fields = ['data_criacao', 'data_atualizacao']


@admin.register(TarefaPAEE)
class TarefaPAEEAdmin(admin.ModelAdmin):
    list_display = ['meta', 'concluida', 'professor_conclusao', 'data_conclusao']
    list_filter = ['concluida']
    search_fields = ['descricao', 'meta__crianca__nome_completo']
    readonly_fields = ['data_criacao', 'data_atualizacao']


@admin.register(DispositivoGravador)
class DispositivoGravadorAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'professora', 'turma_ativa', 'ativo', 'last_seen']
    list_filter = ['ativo', 'instituicao']
    search_fields = ['device_id', 'nome', 'professora__nome']
    readonly_fields = ['token_hash', 'data_criacao', 'data_atualizacao', 'last_seen']
    filter_horizontal = ['turmas']


@admin.register(CodigoPareamento)
class CodigoPareamentoAdmin(admin.ModelAdmin):
    list_display = ['codigo', 'professora', 'expira_em', 'usado_em']
    list_filter = ['instituicao']
    search_fields = ['codigo', 'professora__nome']
    readonly_fields = ['data_criacao']
    filter_horizontal = ['turmas']


@admin.register(AudioDispositivo)
class AudioDispositivoAdmin(admin.ModelAdmin):
    list_display = [
        'upload_id', 'dispositivo', 'professora', 'turma', 'turma_resultado',
        'status', 'total_observacoes', 'data_recebimento',
    ]
    list_filter = ['status', 'turma_resultado', 'instituicao']
    search_fields = ['upload_id', 'sha256', 'professora__nome', 'transcricao']
    readonly_fields = [
        'data_recebimento', 'data_processamento', 'sha256', 'arquivo_path',
        'transcricao', 'alunos_identificados', 'nomes_nao_identificados',
        'total_observacoes', 'erro_codigo', 'erro_processamento',
    ]

# Register your models here.
