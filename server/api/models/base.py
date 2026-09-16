from django.db import models
from django.utils import timezone
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
import uuid


### MODELS DE AUTENTICAÇÃO E USUÁRIOS ###

class UsuarioManager(BaseUserManager):
    """Manager customizado para o modelo Usuario"""

    def create_user(self, email, password=None, **extra_fields):
        """Cria e salva um usuário comum"""
        if not email:
            raise ValueError('O campo email é obrigatório')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        """Cria e salva um superusuário"""
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('perfil', 'admin')
        extra_fields.setdefault('ativo', True)

        return self.create_user(email, password, **extra_fields)


class Instituicao(models.Model):
    """Escola ou instituição de ensino"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nome = models.CharField(max_length=200, verbose_name="Nome da Instituição")
    cnpj = models.CharField(max_length=18, unique=True, null=True, blank=True)
    email_institucional = models.EmailField(null=True, blank=True, verbose_name="Email Institucional")
    endereco = models.CharField(max_length=300, blank=True)
    cidade = models.CharField(max_length=100, blank=True)
    estado = models.CharField(max_length=2, blank=True, db_column='uf')
    telefone = models.CharField(max_length=20, blank=True)
    logo_url = models.URLField(max_length=500, null=True, blank=True, verbose_name="URL do Logo")
    logo_storage_key = models.CharField(max_length=500, null=True, blank=True, verbose_name="Chave do Logo no Storage")
    tipo_relatorio = models.CharField(max_length=50, default='texto_e_evidencia', blank=True)
    report_settings = models.JSONField(default=dict, blank=True, verbose_name="Configurações de Relatório")
    ordem_relatorio = models.JSONField(default=list, blank=True, verbose_name="Ordem das Seções")
    ativa = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'instituicoes'
        managed = True
        verbose_name = 'Instituição'
        verbose_name_plural = 'Instituições'

    def __str__(self):
        return self.nome


class Usuario(AbstractBaseUser, PermissionsMixin):
    """Modelo de usuário do sistema (autenticação Django)"""

    PERFIS = [
        ('admin', 'Administrador'),
        ('coordenador', 'Coordenador Pedagógico'),
        ('professor', 'Professor'),  # legado — não usar em novos cadastros
        ('professor_infantil', 'Professor Educação Infantil'),
        ('professor_fundamental', 'Professor Ensino Fundamental'),
        ('professor_especialista', 'Professor Especialista'),
        ('especialista', 'Especialista'),
    ]

    # Fonte única de verdade para "é um perfil de professor, de qualquer tipo".
    # Usado em toda lógica que hoje trata professor/professor_especialista como
    # equivalentes (filtros de turma, alertas, indicadores). Ao criar um novo
    # tipo de professor no futuro, adicionar aqui propaga automaticamente para
    # todos os pontos que importam esta constante — em vez de listas soltas
    # duplicadas pelo código, que é como professor_infantil/professor_fundamental
    # ficaram invisíveis nessas áreas quando foram criados.
    PERFIS_PROFESSOR = [
        'professor',
        'professor_infantil',
        'professor_fundamental',
        'professor_especialista',
    ]

    TIPOS_ESPECIALISTA = [
        ('psicopedagogo', 'Psicopedagogo'),
        ('psicologo', 'Psicólogo'),
        ('fonoaudiologo', 'Fonoaudiólogo'),
        ('terapeuta_ocupacional', 'Terapeuta Ocupacional'),
        ('outro', 'Outro'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True, verbose_name="Email")
    nome = models.CharField(max_length=200, verbose_name="Nome Completo")
    perfil = models.CharField(max_length=30, choices=PERFIS, default='professor')
    tipo_especialista = models.CharField(
        max_length=30,
        choices=TIPOS_ESPECIALISTA,
        null=True,
        blank=True,
        verbose_name="Tipo de Especialista"
    )
    instituicao = models.ForeignKey(
        Instituicao,
        on_delete=models.CASCADE,
        related_name='usuarios',
        verbose_name="Instituição",
        null=True,
        blank=True
    )
    disciplinas = models.ManyToManyField(
        'Disciplina',
        through='UsuarioDisciplina',
        related_name='professores',
        verbose_name="Disciplinas"
    )
    ativo = models.BooleanField(default=True, verbose_name="Usuário Ativo")
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = UsuarioManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['nome']

    class Meta:
        db_table = 'usuarios'
        managed = True
        verbose_name = 'Usuário'
        verbose_name_plural = 'Usuários'

    def __str__(self):
        return f"{self.nome} ({self.get_perfil_display()})"


class Disciplina(models.Model):
    """Disciplina vinculada a uma instituição (ex: Matemática, Português)"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    instituicao = models.ForeignKey(
        Instituicao,
        on_delete=models.CASCADE,
        related_name='disciplinas',
        verbose_name="Instituição"
    )
    nome = models.CharField(max_length=100, verbose_name="Nome da Disciplina")
    ativo = models.BooleanField(default=True, verbose_name="Disciplina Ativa")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'disciplinas'
        managed = True
        verbose_name = 'Disciplina'
        verbose_name_plural = 'Disciplinas'
        ordering = ['nome']
        constraints = [
            models.UniqueConstraint(
                fields=['instituicao', 'nome'],
                name='unique_disciplina_por_instituicao'
            ),
        ]

    def __str__(self):
        return self.nome


class UsuarioDisciplina(models.Model):
    """Vínculo N:N entre professor_fundamental e disciplinas, escopado por instituição"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    usuario = models.ForeignKey(
        Usuario,
        on_delete=models.CASCADE,
        related_name='usuario_disciplinas',
        verbose_name="Usuário"
    )
    disciplina = models.ForeignKey(
        Disciplina,
        on_delete=models.CASCADE,
        related_name='usuario_disciplinas',
        verbose_name="Disciplina"
    )
    instituicao = models.ForeignKey(
        Instituicao,
        on_delete=models.CASCADE,
        related_name='usuario_disciplinas',
        verbose_name="Instituição"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'usuario_disciplinas'
        managed = True
        verbose_name = 'Vínculo Usuário-Disciplina'
        verbose_name_plural = 'Vínculos Usuário-Disciplina'
        constraints = [
            models.UniqueConstraint(
                fields=['usuario', 'disciplina'],
                name='unique_usuario_disciplina'
            ),
        ]
        indexes = [
            models.Index(fields=['usuario'], name='usuario_disc_usuario_idx'),
            models.Index(fields=['instituicao'], name='usuario_disc_instit_idx'),
        ]

    def __str__(self):
        return f"{self.usuario.nome} - {self.disciplina.nome}"
class SerieConfig(models.Model):
    """Configuração de séries/faixas etárias disponíveis para turmas."""
    ETAPAS = [
        ('educacao_infantil', 'Educação Infantil'),
        ('ensino_fundamental', 'Ensino Fundamental'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nome = models.CharField(max_length=50, verbose_name="Nome da Série")
    etapa = models.CharField(max_length=30, choices=ETAPAS, verbose_name="Etapa de Ensino")
    ordem = models.IntegerField(verbose_name="Ordem de Exibição")
    idade_min = models.IntegerField(null=True, blank=True, verbose_name="Idade Mínima (anos)")
    idade_max = models.IntegerField(null=True, blank=True, verbose_name="Idade Máxima (anos)")
    ativa = models.BooleanField(default=True, verbose_name="Ativa")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'series_config'
        managed = True
        ordering = ['etapa', 'ordem']
        verbose_name = 'Configuração de Série'
        verbose_name_plural = 'Configurações de Séries'

    def __str__(self):
        return f"{self.nome} ({self.get_etapa_display()})"


class Turma(models.Model):
    """Turma/Classe de alunos"""
    TURNOS = [
        ('manha', 'Manhã'),
        ('tarde', 'Tarde'),
        ('integral', 'Integral'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nome = models.CharField(max_length=100, verbose_name="Nome da Turma")
    faixa_etaria = models.CharField(max_length=50, verbose_name="Faixa Etária/Série", blank=True, default='')
    turno = models.CharField(max_length=20, choices=TURNOS, default='manha')
    ano_letivo = models.CharField(max_length=10, default='2025')
    instituicao_id = models.UUIDField(db_index=True, verbose_name="ID da Instituição", null=True, blank=True)
    ativa = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'turmas'
        managed = True
        verbose_name = 'Turma'
        verbose_name_plural = 'Turmas'

    def __str__(self):
        return f"{self.nome} - {self.faixa_etaria} ({self.ano_letivo})"


class ConfiguracaoRegistro(models.Model):
    """Configuração de frequência de registros por turma."""
    FREQUENCIAS = [
        ('diario', 'Diário'),
        ('semanal', 'Semanal'),
        ('quinzenal', 'Quinzenal'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    turma_id = models.UUIDField(db_index=True, unique=True, verbose_name="ID da Turma")
    frequencia_registro = models.CharField(max_length=20, choices=FREQUENCIAS, verbose_name="Frequência de Registro")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'configuracoes_registro'
        managed = True
        verbose_name = 'Configuração de Registro'
        verbose_name_plural = 'Configurações de Registro'

    def __str__(self):
        return f"{self.turma_id} - {self.frequencia_registro}"


class UsuarioTurma(models.Model):
    """Relação N-para-N entre Usuários e Turmas"""
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='turmas')
    turma = models.ForeignKey(Turma, on_delete=models.CASCADE, related_name='professores')
    data_vinculo = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'usuario_turmas'
        unique_together = ('usuario', 'turma')
        verbose_name = 'Vínculo Usuário-Turma'
        verbose_name_plural = 'Vínculos Usuário-Turma'

    def __str__(self):
        return f"{self.usuario.nome} → {self.turma.nome}"


### MODELS DE REGISTROS PEDAGÓGICOS ###

class RegistroEscrita(models.Model):
    """
    Modelo para armazenar registros de análise de escrita das crianças
    """
    # Informações básicas do registro
    nome_aluno = models.CharField(max_length=200, verbose_name="Nome do Aluno")
    turma_id = models.CharField(max_length=100, verbose_name="ID da Turma")
    serie_aluno = models.CharField(max_length=100, default="Educação Infantil", verbose_name="Série do Aluno")
    
    # Informações do arquivo
    arquivo_nome = models.CharField(max_length=255, verbose_name="Nome do Arquivo")
    arquivo_hash = models.CharField(max_length=50, unique=True, verbose_name="Hash do Arquivo")
    arquivo_path = models.CharField(max_length=500, verbose_name="Caminho do Arquivo")
    arquivo_original = models.CharField(max_length=255, verbose_name="Nome Original do Arquivo")
    tamanho_arquivo = models.IntegerField(verbose_name="Tamanho do Arquivo (bytes)")
    tipo_arquivo = models.CharField(max_length=100, verbose_name="Tipo do Arquivo")
    
    # Análise da IA
    etapa_ia = models.CharField(max_length=100, verbose_name="Etapa Sugerida pela IA")
    analise_detalhada = models.TextField(verbose_name="Análise Detalhada da IA")
    
    # Informações da professora
    professora = models.CharField(max_length=200, verbose_name="Professora que Submeteu")
    anotacoes_professora = models.TextField(blank=True, null=True, verbose_name="Anotações Adicionais da Professora")
    
    # Metadados
    data_criacao = models.DateTimeField(default=timezone.now, verbose_name="Data de Criação")
    data_atualizacao = models.DateTimeField(auto_now=True, verbose_name="Data de Atualização")
    
    class Meta:
        verbose_name = "Registro de Escrita"
        verbose_name_plural = "Registros de Escrita"
        ordering = ['-data_criacao']
    
    def __str__(self):
        return f"{self.nome_aluno} - {self.etapa_ia} - {self.data_criacao.strftime('%d/%m/%Y')}"

# Create your models here.

class RegistroDesenho(models.Model):
    # Dados do aluno
    nome_aluno = models.CharField(max_length=200)
    turma_id = models.CharField(max_length=100)
    serie_aluno = models.CharField(max_length=100)
    
    # Dados da atividade
    atividade = models.CharField(max_length=200, default='Desenho Livre')
    contexto = models.TextField(blank=True)
    
    # Análise da IA
    fase_desenho = models.CharField(max_length=100)  # Ex: "Esquemático", "Pré-esquemático"
    elementos_detectados = models.JSONField(default=list)  # Lista de elementos encontrados
    analise_detalhada = models.TextField()  # Análise completa da IA
    
    # Dados da professora
    professora = models.CharField(max_length=200)
    anotacoes_professora = models.TextField(blank=True)
    
    # Metadados do arquivo
    arquivo_nome = models.CharField(max_length=300)
    arquivo_hash = models.CharField(max_length=50, unique=True)
    arquivo_path = models.CharField(max_length=500)
    arquivo_original = models.CharField(max_length=300)
    tamanho_arquivo = models.BigIntegerField()
    tipo_arquivo = models.CharField(max_length=100)
    
    # Timestamps
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'registro_desenho'
        verbose_name = 'Registro de Desenho'
        verbose_name_plural = 'Registros de Desenho'
        ordering = ['-data_criacao']
    
    def __str__(self):
        return f"Desenho de {self.nome_aluno} - {self.fase_desenho}"


class RegistroLeitura(models.Model):
    """
    Registro de uma análise de leitura feita pelo microserviço NaraNN.

    Estados:
      - ``pendente``    análise em andamento no NaraNN.
      - ``analisado``   probabilidades prontas, aguardando a professora confirmar.
      - ``confirmado``  a professora confirmou a classe; o áudio foi movido
        para a pasta definitiva ``audio/leitura/<classe>/`` no S3.
      - ``falhou``      erro no NaraNN ou o áudio temporário em
        ``audio/leitura/_pendentes/`` expirou antes da confirmação.
      - ``cancelado``   cancelado pela professora.
    """

    STATUS_CHOICES = [
        ('pendente', 'Análise em andamento no NaraNN'),
        ('analisado', 'Análise pronta — aguardando confirmação da professora'),
        ('confirmado', 'Confirmado pela professora'),
        ('falhou', 'Falhou'),
        ('cancelado', 'Cancelado'),
    ]

    crianca = models.ForeignKey(
        'Crianca',
        on_delete=models.CASCADE,
        related_name='registros_leitura',
    )
    turma = models.ForeignKey(
        'Turma',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='registros_leitura',
    )
    professor = models.ForeignKey(
        'Usuario',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='registros_leitura',
    )

    nara_job_id = models.CharField(max_length=64, blank=True, default='')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pendente')

    arquivo_path = models.CharField(max_length=500, blank=True, default='')
    arquivo_nome = models.CharField(max_length=255)
    arquivo_hash = models.CharField(max_length=64, unique=True)
    tamanho_arquivo = models.BigIntegerField(default=0)
    tipo_arquivo = models.CharField(max_length=50, default='audio/ogg')

    duracao_seg = models.FloatField(null=True, blank=True)
    pieces = models.IntegerField(null=True, blank=True)
    feat_dim = models.IntegerField(null=True, blank=True)

    classe_predita = models.CharField(max_length=50, blank=True, default='')
    classe_escolhida = models.CharField(max_length=50, blank=True, default='')
    probabilidades = models.JSONField(default=dict, blank=True)

    anotacoes_professora = models.TextField(blank=True, default='')

    data_criacao = models.DateTimeField(default=timezone.now)
    data_atualizacao = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'registro_leitura'
        verbose_name = 'Registro de Leitura'
        verbose_name_plural = 'Registros de Leitura'
        ordering = ['-data_criacao']
        indexes = [
            models.Index(fields=['crianca', '-data_criacao']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"Leitura de {self.crianca_id} - {self.classe_escolhida or 'pendente'}"


### Habilidades BNCC
    
class HabilidadeBNCC(models.Model):
    """
    Tabela para armazenar as habilidades da BNCC
    """
    codigo = models.CharField(max_length=20, unique=True)  # Ex: EF01LP01
    descricao = models.TextField()
    componente_curricular = models.CharField(max_length=100)  # Ex: Língua Portuguesa
    ano_serie = models.CharField(max_length=50)  # Ex: 1º ano
    campo_atuacao = models.CharField(max_length=200, blank=True, null=True)
    ativa = models.BooleanField(default=True)
    data_criacao = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'habilidades_bncc'
        verbose_name = 'Habilidade BNCC'
        verbose_name_plural = 'Habilidades BNCC'
    
    def __str__(self):
        return f"{self.codigo} - {self.descricao[:50]}..."

class PlanejamentoSemanal(models.Model):
    """
    Planejamento semanal de uma turma
    """
    turma_id = models.CharField(max_length=50)  # ID da turma no banco principal
    semana_inicio = models.DateField()  # Data de início da semana (segunda-feira)
    semana_fim = models.DateField()  # Data de fim da semana (sexta-feira)
    professora_id = models.CharField(max_length=50)  # ID da professora
    professora_nome = models.CharField(max_length=200)
    ano_letivo = models.IntegerField(default=2025)
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_modificacao = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'planejamentos_semanais'
        unique_together = ('turma_id', 'semana_inicio')  # Uma turma pode ter apenas um planejamento por semana
        verbose_name = 'Planejamento Semanal'
        verbose_name_plural = 'Planejamentos Semanais'
    
    def __str__(self):
        return f"Planejamento Turma {self.turma_id} - {self.semana_inicio} a {self.semana_fim}"

class PlanejamentoDiario(models.Model):
    """
    Planejamento de um dia específico dentro da semana
    """
    DIAS_SEMANA = [
        ('segunda', 'Segunda-feira'),
        ('terca', 'Terça-feira'),
        ('quarta', 'Quarta-feira'),
        ('quinta', 'Quinta-feira'),
        ('sexta', 'Sexta-feira'),
    ]
    
    planejamento_semanal = models.ForeignKey(
        PlanejamentoSemanal,
        on_delete=models.CASCADE,
        related_name='dias'
    )
    dia_semana = models.CharField(max_length=10, choices=DIAS_SEMANA)
    data = models.DateField()  # Data específica do dia
    atividades_propostas = models.TextField(blank=True, null=True)
    # Texto livre que a professora digita no Assistente de IA para gerar
    # sugestões de atividades — guardado para reabrir pré-preenchido.
    prompt_ia = models.TextField(blank=True, null=True)
    # Arquivo (PDF/DOC/DOCX) opcional anexado pela professora; armazenado no S3.
    arquivo_storage_key = models.CharField(max_length=500, blank=True, null=True)
    arquivo_nome_original = models.CharField(max_length=255, blank=True, null=True)
    arquivo_content_type = models.CharField(max_length=100, blank=True, null=True)
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_modificacao = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'planejamentos_diarios'
        unique_together = ('planejamento_semanal', 'dia_semana')
        verbose_name = 'Planejamento Diário'
        verbose_name_plural = 'Planejamentos Diários'
    
    def __str__(self):
        return f"{self.planejamento_semanal} - {self.get_dia_semana_display()}"

class PlanejamentoHabilidade(models.Model):
    """
    Relação entre planejamento diário e habilidades da BNCC
    """
    planejamento_diario = models.ForeignKey(
        PlanejamentoDiario, 
        on_delete=models.CASCADE, 
        related_name='habilidades'
    )
    habilidade_bncc = models.ForeignKey(
        HabilidadeBNCC, 
        on_delete=models.CASCADE, 
        related_name='planejamentos'
    )
    observacao_habilidade = models.TextField(blank=True, null=True)  # Como será trabalhada
    data_criacao = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'planejamentos_habilidades'
        unique_together = ('planejamento_diario', 'habilidade_bncc')
        verbose_name = 'Habilidade no Planejamento'
        verbose_name_plural = 'Habilidades nos Planejamentos'
    
    def __str__(self):
        return f"{self.planejamento_diario} - {self.habilidade_bncc.codigo}"


### MODELS DE OBSERVAÇÕES ###

class ObservacaoTranscricao(models.Model):
    """
    Armazena observações pedagógicas extraídas de transcrição de áudio.
    Substitui o armazenamento em logs JSON por persistência no banco de dados.
    """
    TIPOS_OBSERVACAO = [
        ('TRANSCRICAO_IA', 'Transcrição com IA'),
        ('OBSERVACAO_MANUAL', 'Observação Manual'),
        ('LEITURA_ORAL', 'Análise de Leitura Oral'),
    ]

    # Dados do aluno
    aluno_nome = models.CharField(max_length=200, verbose_name="Nome do Aluno")
    crianca_id = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="ID da Criança",
        db_index=True
    )

    # Dados da observação
    observacao_texto = models.TextField(verbose_name="Texto da Observação")
    tipo_observacao = models.CharField(
        max_length=30,
        choices=TIPOS_OBSERVACAO,
        default='TRANSCRICAO_IA',
        verbose_name="Tipo de Observação"
    )
    data_observacao = models.DateField(
        default=timezone.now,
        verbose_name="Data da Observação",
        db_index=True
    )

    # Dados da turma e professora
    turma_id = models.CharField(
        max_length=100,
        verbose_name="ID da Turma",
        db_index=True
    )
    turma_nome = models.CharField(
        max_length=200,
        blank=True,
        default='',
        verbose_name="Nome da Turma"
    )
    professora_id = models.CharField(max_length=100, verbose_name="ID da Professora")
    professora_nome = models.CharField(max_length=200, verbose_name="Nome da Professora")

    # Metadados da IA (armazena confiança, timestamps, modelo usado, etc.)
    metadados_ia = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Metadados da Análise de IA"
    )

    # Transcrição completa (opcional, para referência)
    transcricao_completa = models.TextField(
        blank=True,
        default='',
        verbose_name="Transcrição Completa do Áudio"
    )

    # Timestamps
    data_criacao = models.DateTimeField(auto_now_add=True, verbose_name="Data de Criação")
    data_atualizacao = models.DateTimeField(auto_now=True, verbose_name="Data de Atualização")

    class Meta:
        db_table = 'observacoes_transcricao'
        verbose_name = 'Observação de Transcrição'
        verbose_name_plural = 'Observações de Transcrição'
        ordering = ['-data_observacao', '-data_criacao']
        indexes = [
            models.Index(fields=['turma_id', 'data_observacao']),
            models.Index(fields=['aluno_nome']),
            models.Index(fields=['professora_id']),
        ]

    def __str__(self):
        return f"{self.aluno_nome} - {self.data_observacao.strftime('%d/%m/%Y')} ({self.get_tipo_observacao_display()})"


### MODELS DE PORTFÓLIO (N-para-N: 1 foto → N alunos) ###

class ProducaoFoto(models.Model):
    """
    Armazena fotos/mídias do portfólio.
    Uma foto pode ser vinculada a múltiplos alunos através de ProducaoFotoCrianca.
    """
    TIPOS_MIDIA = [
        ('foto', 'Fotografia'),
        ('video', 'Vídeo'),
        ('desenho', 'Desenho'),
        ('escrita', 'Escrita'),
    ]

    # Dados do arquivo
    arquivo_url = models.URLField(max_length=500, verbose_name="URL do Arquivo (S3)")
    arquivo_nome = models.CharField(max_length=255, verbose_name="Nome Original do Arquivo")
    arquivo_hash = models.CharField(max_length=64, unique=True, verbose_name="Hash do Arquivo")
    tamanho_bytes = models.BigIntegerField(verbose_name="Tamanho em Bytes")
    tipo_midia = models.CharField(max_length=20, choices=TIPOS_MIDIA, default='foto')
    mime_type = models.CharField(max_length=100, default='image/jpeg')

    # Contexto pedagógico
    turma_id = models.CharField(max_length=100, verbose_name="ID da Turma", db_index=True)
    professora_id = models.CharField(max_length=100, verbose_name="ID da Professora")
    professora_nome = models.CharField(max_length=200, verbose_name="Nome da Professora")
    projeto = models.CharField(max_length=200, blank=True, default='', verbose_name="Projeto Vinculado")
    tags = models.JSONField(default=list, blank=True, verbose_name="Tags de Contexto")

    # Metadados
    data_registro = models.DateField(default=timezone.now, verbose_name="Data do Registro")
    data_upload = models.DateTimeField(auto_now_add=True, verbose_name="Data do Upload")
    data_atualizacao = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'producoes_fotos'
        verbose_name = 'Produção (Foto/Mídia)'
        verbose_name_plural = 'Produções (Fotos/Mídias)'
        ordering = ['-data_registro', '-data_upload']
        indexes = [
            models.Index(fields=['turma_id', 'data_registro']),
            models.Index(fields=['professora_id']),
            models.Index(fields=['projeto']),
        ]

    def __str__(self):
        return f"{self.arquivo_nome} - {self.data_registro.strftime('%d/%m/%Y')}"


class ProducaoFotoCrianca(models.Model):
    """
    Tabela de vínculos N-para-N entre fotos e crianças.
    Permite legendas individuais para cada criança na mesma foto.
    """
    producao_foto = models.ForeignKey(
        ProducaoFoto,
        on_delete=models.CASCADE,
        related_name='vinculos_criancas',
        verbose_name="Foto/Mídia"
    )
    crianca_id = models.CharField(max_length=100, verbose_name="ID da Criança", db_index=True)
    crianca_nome = models.CharField(max_length=200, verbose_name="Nome da Criança")

    # Legenda individual para esta criança nesta foto
    legenda = models.TextField(blank=True, default='', verbose_name="Legenda Individual")
    legenda_ia = models.TextField(blank=True, default='', verbose_name="Legenda Sugerida pela IA")

    # Flags
    destaque = models.BooleanField(default=False, verbose_name="Destaque no Portfólio")
    incluir_relatorio = models.BooleanField(default=False, verbose_name="Incluir no Relatório")

    # Timestamps
    data_vinculo = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'producoes_fotos_criancas'
        verbose_name = 'Vínculo Foto-Criança'
        verbose_name_plural = 'Vínculos Foto-Criança'
        unique_together = ('producao_foto', 'crianca_id')
        indexes = [
            models.Index(fields=['crianca_id']),
            models.Index(fields=['producao_foto', 'crianca_id']),
        ]

    def __str__(self):
        return f"{self.crianca_nome} em {self.producao_foto.arquivo_nome}"


### MODELS DO BANCO PRINCIPAL ###
### Estes models refletem tabelas do Postgres ###


class Crianca(models.Model):
    """
    Espelho da tabela 'criancas' no Postgres.
    Representa alunos/crianças matriculados.
    managed=False significa que Django não altera o schema desta tabela.
    """
    STATUS_VINCULO = [
        ('ativo', 'Ativo'),
        ('inativo', 'Inativo'),
        ('transferido', 'Transferido'),
    ]
    GENERO_CHOICES = [
        ('M', 'Masculino'),
        ('F', 'Feminino'),
        ('O', 'Outro'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nome_completo = models.CharField(max_length=200, verbose_name="Nome Completo")
    data_nascimento = models.DateField(null=True, blank=True, verbose_name="Data de Nascimento")
    genero = models.CharField(max_length=1, choices=GENERO_CHOICES, null=True, blank=True)
    turma_id = models.UUIDField(db_index=True, verbose_name="ID da Turma")
    instituicao_id = models.UUIDField(db_index=True, verbose_name="ID da Instituição")
    nome_responsavel = models.CharField(max_length=200, blank=True, null=True)
    telefone_responsavel = models.CharField(max_length=20, blank=True, null=True)
    status_vinculo = models.CharField(max_length=20, choices=STATUS_VINCULO, default='ativo')
    observacoes = models.TextField(blank=True, null=True)
    foto_url = models.URLField(max_length=500, null=True, blank=True, verbose_name="URL da Foto")
    foto_storage_key = models.CharField(max_length=500, null=True, blank=True, verbose_name="Chave da Foto no Storage")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'criancas'
        managed = True
        verbose_name = 'Criança'
        verbose_name_plural = 'Crianças'
        ordering = ['nome_completo']

    def __str__(self):
        return self.nome_completo

class Relatorio(models.Model):
    """
    Espelho da tabela 'relatorios' no Postgres.
    Armazena relatórios gerados para crianças.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    id_crianca = models.UUIDField(db_index=True, verbose_name="ID da Criança")
    periodo = models.CharField(max_length=500, verbose_name="Período do Relatório")
    conteudo = models.TextField(verbose_name="Conteúdo do Relatório")
    revisado_por = models.UUIDField(null=True, blank=True, verbose_name="Revisado Por")
    pdf_url = models.URLField(max_length=500, null=True, blank=True, verbose_name="URL do PDF")
    pdf_storage_key = models.CharField(
        max_length=500,
        null=True,
        blank=True,
        verbose_name="Chave do PDF no Storage",
    )
    template = models.ForeignKey(
        'RelatorioTemplate',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='relatorios',
        verbose_name='Template de PDF utilizado',
    )
    instituicao_id = models.UUIDField(db_index=True, verbose_name="ID da Instituição")
    data_criacao = models.DateTimeField(auto_now_add=True, verbose_name="Data de Criação")

    class Meta:
        db_table = 'relatorios'
        managed = True
        verbose_name = 'Relatório'
        verbose_name_plural = 'Relatórios'
        ordering = ['-data_criacao']
        constraints = [
            models.UniqueConstraint(
                fields=['id_crianca', 'periodo', 'instituicao_id'],
                name='unique_relatorio_crianca_periodo_instituicao',
            )
        ]

    def __str__(self):
        return f"Relatório {self.id_crianca} - {self.periodo}"
class CampoExperienciaCustomizado(models.Model):
    """
    Campos de Experiência customizados criados pelos administradores.
    Permite adicionar novos campos além dos padrão da BNCC com ícone personalizado.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    instituicao_id = models.UUIDField(db_index=True, null=True, blank=True, verbose_name="ID da Instituição")
    nome = models.CharField(max_length=200, verbose_name="Nome do Campo de Experiência")
    icone = models.CharField(max_length=50, default='BookOpen', verbose_name="Nome do Ícone (Lucide)")
    cor = models.CharField(max_length=20, null=True, blank=True, verbose_name="Cor (hex)")
    ativo = models.BooleanField(default=True, verbose_name="Ativo")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'campos_experiencia_customizados'
        managed = True
        verbose_name = 'Campo de Experiência Customizado'
        verbose_name_plural = 'Campos de Experiência Customizados'
        unique_together = ('instituicao_id', 'nome')
        indexes = [
            models.Index(fields=['instituicao_id', 'ativo']),
        ]

    def __str__(self):
        return self.nome

class RelatorioTemplate(models.Model):
    MODELO_CHOICES = [
        ('classico', 'Clássico NARA'),
        ('memorias', 'Memórias da Infância'),
        ('mascote', 'Com a Nara'),
        ('natureza', 'Pequenas Descobertas'),
        ('essencial', 'Essencial'),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    instituicao_id = models.UUIDField(
        db_index=True,
        verbose_name="ID da Instituição"
    )

    nome = models.CharField(
        max_length=100,
        verbose_name="Nome dado pela escola a este template"
    )

    modelo = models.CharField(
        max_length=20,
        choices=MODELO_CHOICES,
        verbose_name="Modelo base"
    )

    usa_foto_crianca = models.BooleanField(
        null=True,
        blank=True,
        default=None,
        verbose_name="Usa foto da criança na capa"
    )

    config = models.JSONField(
        default=dict,
        verbose_name="Configuração de personalização"
    )

    items_sumario = models.JSONField(
        default=list,
        verbose_name="Itens do sumário (ordem e visibilidade)"
    )

    ativo = models.BooleanField(
        default=False,
        verbose_name="Ativa (vale para os próximos relatórios)"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'relatorio_templates'
        managed = True
        verbose_name = 'Template de Relatório'
        verbose_name_plural = 'Templates de Relatório'
        ordering = ['-updated_at']

        indexes = [
            models.Index(
                fields=['instituicao_id', 'ativo'],
                name='rel_tpl_inst_ativo_idx',
            ),
        ]

        constraints = [
            models.UniqueConstraint(
                fields=['instituicao_id', 'modelo'],
                name='unique_template_por_modelo_instituicao',
            ),
            models.UniqueConstraint(
                fields=['instituicao_id'],
                condition=models.Q(ativo=True),
                name='unique_template_ativo_por_instituicao',
            ),
        ]

    def __str__(self):
        return (
            f"{self.nome} ({self.get_modelo_display()})"
            f"{' — ativa' if self.ativo else ''}"
        )

    def suporta_foto(self) -> bool:
        return self.modelo == 'memorias'

    def suporta_imagem_principal(self) -> bool:
        return self.modelo in ('mascote', 'essencial')

    def suporta_lista_conteudo(self) -> bool:
        return self.modelo == 'classico'

    def suporta_alinhamento(self) -> bool:
        return self.modelo in ('natureza', 'essencial')

class PerguntaBNCC(models.Model):
    """
    Espelho da tabela 'perguntas_bncc' no Postgres.
    Perguntas de avaliação baseadas nas competências BNCC.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    faixa_etaria = models.CharField(max_length=50, verbose_name="Faixa Etária")
    campo_experiencia = models.CharField(max_length=200, verbose_name="Campo de Experiência")
    pergunta = models.TextField(verbose_name="Pergunta Facilitadora")
    pergunta_norma = models.TextField(null=True, blank=True, verbose_name="Pergunta Original da Norma BNCC")
    habilidade_bncc = models.CharField(max_length=50, null=True, blank=True, verbose_name="Código Habilidade BNCC")
    area_conhecimento = models.CharField(max_length=200, null=True, blank=True, verbose_name="Área do Conhecimento")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'perguntas_bncc'
        managed = True
        verbose_name = 'Pergunta BNCC'
        verbose_name_plural = 'Perguntas BNCC'

    def __str__(self):
        return f"{self.faixa_etaria} - {self.pergunta[:50]}..."


class PerguntaEspecialista(models.Model):
    """
    Perguntas livres cadastradas pelos especialistas (vinculadas à instituição).
    O campo_experiencia define o agrupamento no formulário de observação do professor.
    """
    STATUS_CHOICES = [
        ('ativa', 'Ativa'),
        ('inativa', 'Inativa'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    instituicao_id = models.UUIDField(db_index=True, null=True, blank=True, verbose_name="ID da Instituição")
    especialidade = models.CharField(max_length=100, null=True, blank=True, verbose_name="Especialidade (Legado)")
    campo_experiencia = models.CharField(max_length=200, verbose_name="Campo de Experiência", db_index=True)
    nivel = models.CharField(max_length=50, verbose_name="Nível de Ensino")
    pergunta = models.TextField(null=True, blank=True, verbose_name="Pergunta")
    pergunta_facilitadora = models.TextField(verbose_name="Pergunta Facilitadora")
    referencia_norma = models.CharField(max_length=50, verbose_name="Referência da Norma (Código BNCC)")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ativa')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'perguntas_especialistas'
        managed = True
        verbose_name = 'Pergunta de Especialista'
        verbose_name_plural = 'Perguntas de Especialistas'

    def __str__(self):
        return f"{self.especialidade} - {self.nivel} - {self.pergunta_facilitadora[:50]}..."


class RegistroObservacao(models.Model):
    """
    Espelho da tabela 'registros_observacao' no Postgres.
    Observações diárias feitas pelos professores sobre as crianças.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    crianca_id = models.UUIDField(db_index=True, verbose_name="ID da Criança")
    pergunta_id = models.UUIDField(null=True, blank=True, verbose_name="ID da Pergunta BNCC")
    resposta = models.CharField(max_length=50, null=True, blank=True, verbose_name="Resposta")
    observacao = models.TextField(null=True, blank=True, verbose_name="Observação")
    professor_id = models.UUIDField(db_index=True, verbose_name="ID do Professor")
    data_observacao = models.DateField(db_index=True, verbose_name="Data da Observação")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'registros_observacao'
        managed = True
        verbose_name = 'Registro de Observação'
        verbose_name_plural = 'Registros de Observação'
        ordering = ['-data_observacao']

    def __str__(self):
        return f"Observação {self.crianca_id} - {self.data_observacao}"


class ProducaoCrianca(models.Model):
    """
    Espelho da tabela 'producoes_criancas' no Postgres.
    Produções e trabalhos das crianças (portfólio).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    crianca_id = models.UUIDField(db_index=True, verbose_name="ID da Criança")
    turma_id = models.UUIDField(db_index=True, null=True, blank=True, verbose_name="ID da Turma")
    professor_id = models.UUIDField(null=True, blank=True, verbose_name="ID do Professor")
    tipo = models.CharField(max_length=50, default='foto', verbose_name="Tipo de Produção")
    titulo = models.CharField(max_length=200, null=True, blank=True, verbose_name="Título")
    descricao = models.TextField(null=True, blank=True, verbose_name="Descrição")
    arquivo_url = models.URLField(max_length=500, null=True, blank=True, verbose_name="URL do Arquivo")
    projeto = models.CharField(max_length=200, null=True, blank=True, verbose_name="Projeto Vinculado")
    data_registro = models.DateField(null=True, blank=True, verbose_name="Data do Registro")
    instituicao_id = models.UUIDField(null=True, blank=True, verbose_name="ID da Instituição")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'producoes_criancas'
        managed = True
        verbose_name = 'Produção da Criança'
        verbose_name_plural = 'Produções das Crianças'
        ordering = ['-data_registro']

    def __str__(self):
        return f"{self.tipo} - {self.titulo or 'Sem título'}"


class Projeto(models.Model):
    """
    Espelho da tabela 'projetos' no Postgres.
    Projetos pedagógicos.
    """
    STATUS_CHOICES = [
        ('Em andamento', 'Em Andamento'),
        ('Finalizado', 'Finalizado'),
        ('Planejado', 'Planejado'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nome_projeto = models.CharField(max_length=200, verbose_name="Nome do Projeto")
    descricao = models.TextField(null=True, blank=True, verbose_name="Descrição")
    data_inicio = models.DateField(null=True, blank=True, verbose_name="Data de Início")
    data_fim = models.DateField(null=True, blank=True, verbose_name="Data de Término")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Em andamento')
    instituicao_id = models.UUIDField(db_index=True, verbose_name="ID da Instituição")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'projetos'
        managed = True
        verbose_name = 'Projeto'
        verbose_name_plural = 'Projetos'

    def __str__(self):
        return self.nome_projeto


class CalendarioBimestre(models.Model):
    """
    Espelho da tabela 'calendario_bimestres' no Postgres.
    Calendário de bimestres letivos.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ano = models.IntegerField(verbose_name="Ano Letivo")
    bimestre = models.IntegerField(verbose_name="Número do Bimestre")
    data_inicio = models.DateField(verbose_name="Data de Início")
    data_fim = models.DateField(verbose_name="Data de Término")
    instituicao_id = models.UUIDField(null=True, blank=True, verbose_name="ID da Instituição")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'calendario_bimestres'
        managed = True
        verbose_name = 'Calendário de Bimestre'
        verbose_name_plural = 'Calendário de Bimestres'

    def __str__(self):
        return f"{self.ano} - {self.bimestre}º Bimestre"


class PeriodoAvaliativo(models.Model):
    """
    Períodos avaliativos configurados pela instituição.
    """
    TIPOS_PERIODO = [
        ('bimestral', 'Bimestral'),
        ('trimestral', 'Trimestral'),
        ('semestral', 'Semestral'),
        ('anual', 'Anual'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    descricao = models.CharField(max_length=200, verbose_name="Descrição do Período")
    tipo_periodo = models.CharField(max_length=20, choices=TIPOS_PERIODO, verbose_name="Tipo do Período")
    data_inicio = models.DateField(verbose_name="Data de Início")
    data_fim = models.DateField(verbose_name="Data de Fim")
    instituicao_id = models.UUIDField(db_index=True, verbose_name="ID da Instituição")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'periodos_avaliativos'
        managed = True
        verbose_name = 'Período Avaliativo'
        verbose_name_plural = 'Períodos Avaliativos'
        ordering = ['-data_inicio']
        indexes = [
            models.Index(fields=['instituicao_id', 'data_inicio', 'data_fim']),
        ]

    def __str__(self):
        return f"{self.descricao} ({self.get_tipo_periodo_display()})"


class MensagemCoordenacao(models.Model):
    """
    Mensagens enviadas pela coordenação para os professores.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    titulo = models.CharField(max_length=200, verbose_name="Título", blank=True, null=True)
    conteudo = models.TextField(verbose_name="Conteúdo")
    remetente = models.CharField(max_length=200, verbose_name="Nome do Remetente")
    instituicao_id = models.UUIDField(db_index=True, verbose_name="ID da Instituição", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'mensagens_coordenacao'
        managed = True
        verbose_name = 'Mensagem da Coordenação'
        verbose_name_plural = 'Mensagens da Coordenação'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.titulo or 'Sem título'} - {self.remetente}"


class MensagemLida(models.Model):
    """
    Registra quais mensagens foram lidas por cada usuário.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    mensagem = models.ForeignKey(
        MensagemCoordenacao,
        on_delete=models.CASCADE,
        related_name='leituras',
        verbose_name="Mensagem"
    )
    usuario_id = models.UUIDField(db_index=True, verbose_name="ID do Usuário")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'mensagens_lidas'
        managed = True
        verbose_name = 'Mensagem Lida'
        verbose_name_plural = 'Mensagens Lidas'
        unique_together = ('mensagem', 'usuario_id')

    def __str__(self):
        return f"Mensagem {self.mensagem_id} lida por {self.usuario_id}"


class AlertaLido(models.Model):
    """
    Registra quais alertas do sistema foram lidos por cada usuário.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    usuario_id = models.UUIDField(db_index=True, verbose_name="ID do Usuário")
    alerta_tipo = models.CharField(max_length=50, verbose_name="Tipo do Alerta")
    alerta_chave = models.CharField(max_length=200, verbose_name="Chave do Alerta")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'alertas_lidos'
        managed = True
        verbose_name = 'Alerta Lido'
        verbose_name_plural = 'Alertas Lidos'
        unique_together = ('usuario_id', 'alerta_tipo', 'alerta_chave')

    def __str__(self):
        return f"Alerta {self.alerta_tipo}/{self.alerta_chave} lido por {self.usuario_id}"


class CoordenacaoCache(models.Model):
    """
    Snapshot pré-computado (D-1) dos agregados que o painel da coordenação
    consome. Gerado por worker externo via endpoint interno para evitar a
    chamada pesada de 30 dias de registros_observacao no carregamento da
    página.
    """
    id = models.BigAutoField(primary_key=True)
    instituicao_id = models.UUIDField(db_index=True, verbose_name="ID da Instituição")
    data_referencia = models.DateField(db_index=True, verbose_name="Data de Referência (D-1)")
    janela_dias = models.PositiveIntegerField(default=30, verbose_name="Janela (dias)")
    payload = models.JSONField(verbose_name="Payload agregado")
    versao_schema = models.CharField(max_length=20, default='1', verbose_name="Versão do Schema")
    gerado_em = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'coordenacao_cache'
        managed = True
        verbose_name = 'Cache da Coordenação'
        verbose_name_plural = 'Caches da Coordenação'
        unique_together = ('instituicao_id', 'data_referencia')
        indexes = [
            models.Index(fields=['instituicao_id', '-data_referencia']),
        ]
        ordering = ['-data_referencia']

    def __str__(self):
        return f"CoordenacaoCache {self.instituicao_id} @ {self.data_referencia}"


class OpenAIUsage(models.Model):
    """Registro de cada chamada à API OpenAI: tokens consumidos e custos em USD.

    Alimentado em best-effort pelo serviço `api.services.openai_usage` após cada
    resposta bem-sucedida da API — falha de persistência aqui nunca pode
    derrubar a chamada de IA real.
    """
    id = models.BigAutoField(primary_key=True)
    usuario = models.ForeignKey(
        'Usuario',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='consumos_openai',
        verbose_name="Usuário responsável pela chamada",
    )
    input_tokens = models.BigIntegerField(verbose_name="Tokens de entrada")
    image_tokens = models.BigIntegerField(default=0, verbose_name="Tokens de imagem")
    output_tokens = models.BigIntegerField(verbose_name="Tokens de saída")
    input_cost = models.DecimalField(max_digits=14, decimal_places=8, verbose_name="Custo de entrada (USD)")
    output_cost = models.DecimalField(max_digits=14, decimal_places=8, verbose_name="Custo de saída (USD)")
    total_cost = models.DecimalField(max_digits=14, decimal_places=8, verbose_name="Custo total (USD)")
    model = models.CharField(max_length=100, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'openai_usage'
        managed = True
        verbose_name = 'Uso da API OpenAI'
        verbose_name_plural = 'Usos da API OpenAI'
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['model', '-created_at']),
            models.Index(fields=['usuario', '-created_at']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"OpenAIUsage #{self.id} {self.model or '?'} (${self.total_cost})"