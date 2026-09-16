"""Modelos do PAEE — Plano de Atendimento Educacional Especializado.

Área do especialista: sessões de atendimento com o aluno, metas com objetivo/
critério/estratégia e tarefas atribuídas ao professor. Somente os modelos —
a lógica de negócio (endpoints, pipeline de resumo via IA, telas) vem depois.

Decisões de desenho (ver CHANGELOG):
  - FKs reais para Crianca/Usuario/Turma/Instituicao (nada de casamento por
    nome, a fragilidade conhecida de RegistroEscrita/RegistroDesenho).
  - `turma`/`instituicao` são denormalizações derivadas do aluno na criação —
    nunca informadas pelo cliente da API.
  - SessaoEspecialista NÃO persiste transcrição nem áudio (privacidade): o áudio vive
    num temporário durante o processamento e só o `resumo` (gerado pela IA e
    editável pelo especialista) é gravado. `status` cobre a janela assíncrona.
  - MetaPAEE.status é ciclo de vida pedagógico (julgado pelo especialista contra
    o `criterio`), não estado técnico.
  - TarefaPAEE usa bool `concluida` (só dois estados); o especialista é
    derivável de `meta.especialista` (fonte única, sem FK duplicada).
"""

import uuid

from django.db import models
from django.utils import timezone


class MetaPAEE(models.Model):
    """Meta do PAEE criada pelo especialista para um aluno."""

    CATEGORIAS = [
        ('comunicacao', 'Comunicação e Linguagem'),
        ('motora', 'Desenvolvimento Motor'),
        ('socioemocional', 'Socioemocional'),
        ('cognitiva', 'Cognitiva'),
        ('avd', 'Atividades de Vida Diária'),
        ('academica', 'Acadêmica'),
    ]

    STATUS_CHOICES = [
        ('ativa', 'Ativa'),
        ('alcancada', 'Alcançada'),
        ('encerrada', 'Encerrada'),
        ('revisada', 'Revisada'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    crianca = models.ForeignKey(
        'Crianca', on_delete=models.CASCADE, related_name='metas_paee',
        verbose_name='Aluno',
    )
    especialista = models.ForeignKey(
        'Usuario', on_delete=models.SET_NULL, null=True,
        related_name='metas_aee_criadas', verbose_name='Especialista',
    )
    turma = models.ForeignKey(
        'Turma', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='metas_paee',
    )
    instituicao = models.ForeignKey(
        'Instituicao', on_delete=models.CASCADE, related_name='metas_paee',
    )
    categoria = models.CharField(max_length=30, choices=CATEGORIAS)
    inicio = models.DateField(verbose_name='Início da meta')
    fim = models.DateField(verbose_name='Fim previsto da meta')
    objetivo = models.TextField(verbose_name='Objetivo')
    criterio = models.TextField(verbose_name='Critério de sucesso')
    estrategia = models.TextField(verbose_name='Estratégia')
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='ativa',
        verbose_name='Status da meta',
    )
    data_criacao = models.DateTimeField(default=timezone.now)
    data_atualizacao = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'metas_paee'
        verbose_name = 'Meta PAEE'
        verbose_name_plural = 'Metas PAEE'
        ordering = ['-data_criacao']

    def __str__(self):
        return f"Meta PAEE ({self.get_categoria_display()}) — {self.crianca_id}"


class SessaoEspecialista(models.Model):
    """Sessão de atendimento entre o especialista e o aluno.

    O resumo é gerado pela IA (prompt "PAEE - Resumo de Sessão") a partir do
    áudio da sessão e editado pelo especialista; transcrição e áudio são
    transientes e nunca persistidos.
    """

    STATUS_CHOICES = [
        ('pendente', 'Processamento em andamento'),
        ('processado', 'Resumo gerado'),
        ('falhou', 'Falha no processamento'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    crianca = models.ForeignKey(
        'Crianca', on_delete=models.CASCADE, related_name='sessoes_especialista',
        verbose_name='Aluno',
    )
    especialista = models.ForeignKey(
        'Usuario', on_delete=models.SET_NULL, null=True,
        related_name='sessoes_especialista', verbose_name='Especialista',
    )
    turma = models.ForeignKey(
        'Turma', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='sessoes_especialista',
    )
    instituicao = models.ForeignKey(
        'Instituicao', on_delete=models.CASCADE, related_name='sessoes_especialista',
    )
    metas_trabalhadas = models.ManyToManyField(
        MetaPAEE, blank=True, related_name='sessoes',
        db_table='sessoes_paee_metas',
        verbose_name='Metas trabalhadas na sessão',
    )
    data_atendimento = models.DateField(verbose_name='Data do atendimento')
    duracao = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='Duração (minutos)',
    )
    resumo = models.TextField(
        blank=True, default='',
        verbose_name='Resumo da sessão (IA, editável pelo especialista)',
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='pendente',
    )
    data_criacao = models.DateTimeField(default=timezone.now)
    data_atualizacao = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'sessoes_especialista'
        verbose_name = 'Sessão Especialista'
        verbose_name_plural = 'Sessões Especialista'
        ordering = ['-data_atendimento', '-data_criacao']

    def __str__(self):
        return f"Sessão Especialista {self.data_atendimento} — {self.crianca_id}"


class TarefaPAEE(models.Model):
    """Tarefa criada pelo especialista (via meta) para o professor cumprir.

    O especialista responsável é `meta.especialista` (fonte única);
    criança/turma/instituição também derivam da meta.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    meta = models.ForeignKey(
        MetaPAEE, on_delete=models.CASCADE, related_name='tarefas',
    )
    descricao = models.TextField(verbose_name='Descrição da tarefa')
    concluida = models.BooleanField(default=False)
    professor_conclusao = models.ForeignKey(
        'Usuario', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='tarefas_aee_concluidas',
        verbose_name='Professor que concluiu',
    )
    observacao_professor = models.TextField(
        blank=True, default='',
        verbose_name='Observação do professor ao concluir',
    )
    data_conclusao = models.DateTimeField(null=True, blank=True)
    data_criacao = models.DateTimeField(default=timezone.now)
    data_atualizacao = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tarefas_paee'
        verbose_name = 'Tarefa PAEE'
        verbose_name_plural = 'Tarefas PAEE'
        ordering = ['concluida', '-data_criacao']

    def __str__(self):
        estado = 'concluída' if self.concluida else 'pendente'
        return f"Tarefa PAEE ({estado}) — meta {self.meta_id}"
