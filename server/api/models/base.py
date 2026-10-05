from django.db import models
from django.utils import timezone
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
import uuid as uuid_lib

from ..managers import TenantManager


class UsuarioManager(TenantManager, BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('O campo email é obrigatório')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('nivel', 'superadmin')
        extra_fields.setdefault('is_active', True)
        return self.create_user(email, password, **extra_fields)


class ModeloBase(models.Model):
    """Base de TODOS os models do sistema.

    * ``id``   — inteiro (bigint auto-incremento). É a chave primária e o que
                 TODAS as chaves estrangeiras referenciam (``escola_id``,
                 ``instituicao_id``...). Nunca expor em URL.
    * ``uuid`` — identificador público, separado do id. É o que aparece nas
                 URLs da API (ver ``api/converters.py``), para não expor ids
                 sequenciais.
    """
    id = models.BigAutoField(primary_key=True)
    uuid = models.UUIDField(default=uuid_lib.uuid4, unique=True, editable=False)

    class Meta:
        abstract = True


class Instituicao(ModeloBase):
    nome = models.CharField(max_length=200, verbose_name="Nome da Instituição")
    cnpj = models.CharField(max_length=18, unique=True, null=True, blank=True)
    email_institucional = models.EmailField(max_length=254, null=True, blank=True)
    endereco = models.CharField(max_length=300, blank=True)
    cidade = models.CharField(max_length=100, blank=True)
    estado = models.CharField(max_length=2, blank=True, db_column='uf')
    telefone = models.CharField(max_length=20, blank=True)
    logo_url = models.URLField(max_length=500, null=True, blank=True)
    logo_storage_key = models.CharField(max_length=500, null=True, blank=True)
    ativa = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'instituicoes'
        managed = True
        verbose_name = 'Instituição'
        verbose_name_plural = 'Instituições'

    def __str__(self):
        return self.nome


class Escola(ModeloBase):
    TIPOS_UNIDADE = [
        ('matriz', 'Matriz'),
        ('filial', 'Filial'),
    ]

    instituicao = models.ForeignKey(
        'Instituicao', on_delete=models.CASCADE, related_name='escolas',
    )
    nome = models.CharField(max_length=200, verbose_name="Nome da Escola")
    tipo_unidade = models.CharField(max_length=20, choices=TIPOS_UNIDADE, blank=True)
    cnpj = models.CharField(max_length=18, unique=True, null=True, blank=True)
    endereco = models.CharField(max_length=300, blank=True)
    cidade = models.CharField(max_length=100, blank=True)
    estado = models.CharField(max_length=2, blank=True, db_column='uf')
    telefone = models.CharField(max_length=20, blank=True)
    ativa = models.BooleanField(default=True)
    tipo_relatorio = models.CharField(max_length=50, default='texto_e_evidencia', blank=True)
    report_settings = models.JSONField(default=dict, blank=True)
    ordem_relatorio = models.JSONField(default=list, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'escolas'
        managed = True
        verbose_name = 'Escola'
        verbose_name_plural = 'Escolas'
        constraints = [
            models.UniqueConstraint(
                fields=['instituicao', 'nome'],
                name='unique_escola_por_instituicao',
            ),
        ]
        indexes = [
            models.Index(fields=['instituicao', 'ativa']),
        ]

    def __str__(self):
        return f"{self.nome} ({self.instituicao.nome})"


class Especialista(ModeloBase):
    TIPOS_ESPECIALISTA = [
        ('psicopedagogo', 'Psicopedagogo'),
        ('psicologo', 'Psicólogo'),
        ('fonoaudiologo', 'Fonoaudiólogo'),
        ('terapeuta_ocupacional', 'Terapeuta Ocupacional'),
        ('outro', 'Outro'),
    ]

    tipo_especialista = models.CharField(max_length=30, choices=TIPOS_ESPECIALISTA)
    escola = models.ForeignKey(
        'Escola', on_delete=models.SET_NULL, related_name='especialistas',
        null=True, blank=True,
    )
    instituicao = models.ForeignKey(
        'Instituicao', on_delete=models.CASCADE, related_name='especialistas',
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    objects = TenantManager()

    class Meta:
        db_table = 'especialistas'
        managed = True
        verbose_name = 'Especialista'
        verbose_name_plural = 'Especialistas'
        indexes = [
            models.Index(fields=['escola']),
            models.Index(fields=['instituicao']),
        ]

    def __str__(self):
        return self.get_tipo_especialista_display()


class Usuario(ModeloBase, AbstractBaseUser, PermissionsMixin):
    NIVEIS = [
        ('superadmin', 'Super Administrador'),
        ('admin', 'Administrador'),
        ('coordenador', 'Coordenador Pedagógico'),
        ('professor_infantil', 'Professor Educação Infantil'),
        ('professor_fundamental', 'Professor Ensino Fundamental'),
        ('professor_especialista', 'Professor Especialista'),
        ('especialista', 'Especialista'),
        ('vendedor', 'Vendedor'),
        ('suporte', 'Suporte'),
    ]
    NIVEIS_PROFESSOR = [
        'professor_infantil',
        'professor_fundamental',
        'professor_especialista',
    ]

    email = models.EmailField(unique=True, verbose_name="Email")
    nome = models.CharField(max_length=200, verbose_name="Nome Completo")
    numero = models.CharField(max_length=10, null=True, blank=True)
    nivel = models.CharField(max_length=30, choices=NIVEIS, default='professor_infantil')

    instituicao = models.ForeignKey(
        'Instituicao', on_delete=models.SET_NULL, related_name='usuarios',
        null=True, blank=True,
    )
    escola = models.ForeignKey(
        'Escola', on_delete=models.SET_NULL, related_name='usuarios',
        null=True, blank=True,
    )
    especialista = models.ForeignKey(
        'Especialista', on_delete=models.SET_NULL, related_name='usuarios',
        null=True, blank=True,
    )

    disciplinas = models.ManyToManyField(
        'Disciplina', through='UsuarioDisciplina', related_name='professores',
    )

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    objects = UsuarioManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['nome']

    class Meta:
        db_table = 'usuarios'
        managed = True
        verbose_name = 'Usuário'
        verbose_name_plural = 'Usuários'
        indexes = [
            models.Index(fields=['escola']),
            models.Index(fields=['instituicao']),
            models.Index(fields=['especialista']),
        ]

    def __str__(self):
        return f"{self.nome} ({self.get_nivel_display()})"


class Turma(ModeloBase):
    TURNOS = [
        ('manha', 'Manhã'),
        ('tarde', 'Tarde'),
        ('integral', 'Integral'),
    ]
    ETAPAS = [
        ('educacao_infantil', 'Educação Infantil'),
        ('ensino_fundamental', 'Ensino Fundamental'),
    ]
    # De quanto em quanto tempo a professora deve registrar a turma.
    # Substitui a tabela `configuracoes_registro` do sistema antigo (1:1 com turma).
    FREQUENCIAS_REGISTRO = [
        ('semanal', 'Semanal'),
        ('quinzenal', 'Quinzenal'),
        ('mensal', 'Mensal'),
    ]

    nome = models.CharField(max_length=100)
    faixa_etaria = models.CharField(max_length=50, blank=True, default='')
    turno = models.CharField(max_length=20, choices=TURNOS, default='manha')
    ano_letivo = models.CharField(max_length=10, default='2025')
    ativa = models.BooleanField(default=True)
    etapa = models.CharField(max_length=30, choices=ETAPAS, blank=True, null=True)
    ordem = models.IntegerField(null=True, blank=True)
    idade_min = models.IntegerField(null=True, blank=True)
    idade_max = models.IntegerField(null=True, blank=True)
    frequencia_registro = models.CharField(
        max_length=20, choices=FREQUENCIAS_REGISTRO, default='semanal',
    )
    escola = models.ForeignKey('Escola', on_delete=models.CASCADE, related_name='turmas')
    instituicao = models.ForeignKey('Instituicao', on_delete=models.CASCADE, related_name='turmas')
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    objects = TenantManager()

    class Meta:
        db_table = 'turmas'
        managed = True
        verbose_name = 'Turma'
        verbose_name_plural = 'Turmas'
        indexes = [
            models.Index(fields=['escola', 'ativa']),
        ]

    def __str__(self):
        return f"{self.nome} - {self.faixa_etaria} ({self.ano_letivo})"


class UsuarioTurma(ModeloBase):
    usuario = models.ForeignKey('Usuario', on_delete=models.CASCADE, related_name='usuario_turmas')
    turma = models.ForeignKey('Turma', on_delete=models.CASCADE, related_name='usuario_turmas')
    data_vinculo = models.DateTimeField(default=timezone.now)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'usuario_turmas'
        managed = True
        verbose_name = 'Vínculo Usuário-Turma'
        verbose_name_plural = 'Vínculos Usuário-Turma'
        constraints = [
            models.UniqueConstraint(fields=['usuario', 'turma'], name='unique_usuario_turma'),
        ]

    def __str__(self):
        return f"{self.usuario.nome} → {self.turma.nome}"


class Disciplina(ModeloBase):
    nome = models.CharField(max_length=100)
    ativo = models.BooleanField(default=True)
    escola = models.ForeignKey('Escola', on_delete=models.CASCADE, related_name='disciplinas')
    instituicao = models.ForeignKey('Instituicao', on_delete=models.CASCADE, related_name='disciplinas')
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    objects = TenantManager()

    class Meta:
        db_table = 'disciplinas'
        managed = True
        verbose_name = 'Disciplina'
        verbose_name_plural = 'Disciplinas'
        ordering = ['nome']
        constraints = [
            models.UniqueConstraint(fields=['escola', 'nome'], name='unique_disciplina_por_escola'),
        ]

    def __str__(self):
        return self.nome


class UsuarioDisciplina(ModeloBase):
    usuario = models.ForeignKey('Usuario', on_delete=models.CASCADE, related_name='usuario_disciplinas')
    disciplina = models.ForeignKey('Disciplina', on_delete=models.CASCADE, related_name='usuario_disciplinas')
    escola = models.ForeignKey('Escola', on_delete=models.CASCADE, related_name='usuario_disciplinas')
    instituicao = models.ForeignKey('Instituicao', on_delete=models.CASCADE, related_name='usuario_disciplinas')
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    objects = TenantManager()

    class Meta:
        db_table = 'usuario_disciplinas'
        managed = True
        verbose_name = 'Vínculo Usuário-Disciplina'
        verbose_name_plural = 'Vínculos Usuário-Disciplina'
        constraints = [
            models.UniqueConstraint(fields=['usuario', 'disciplina'], name='unique_usuario_disciplina'),
        ]
        indexes = [
            models.Index(fields=['usuario']),
            models.Index(fields=['escola']),
        ]

    def __str__(self):
        return f"{self.usuario.nome} - {self.disciplina.nome}"


class Aluno(ModeloBase):
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

    nome_completo = models.CharField(max_length=200, verbose_name="Nome Completo")
    data_nascimento = models.DateField(null=True, blank=True)
    genero = models.CharField(max_length=1, choices=GENERO_CHOICES, null=True, blank=True)
    nome_responsavel = models.CharField(max_length=200, blank=True, null=True)
    telefone_responsavel = models.CharField(max_length=20, blank=True, null=True)
    status_vinculo = models.CharField(max_length=20, choices=STATUS_VINCULO, default='ativo')
    observacoes = models.TextField(blank=True, null=True)
    foto_url = models.URLField(max_length=500, null=True, blank=True)
    foto_storage_key = models.CharField(max_length=500, null=True, blank=True)

    turma = models.ForeignKey('Turma', on_delete=models.CASCADE, related_name='alunos')
    escola = models.ForeignKey('Escola', on_delete=models.CASCADE, related_name='alunos')
    instituicao = models.ForeignKey('Instituicao', on_delete=models.CASCADE, related_name='alunos')

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    objects = TenantManager()

    class Meta:
        db_table = 'alunos'
        managed = True
        verbose_name = 'Aluno'
        verbose_name_plural = 'Alunos'
        ordering = ['nome_completo']
        indexes = [
            models.Index(fields=['escola', 'status_vinculo']),
            models.Index(fields=['turma']),
        ]

    def __str__(self):
        return self.nome_completo


class Projeto(ModeloBase):
    STATUS_CHOICES = [
        ('em_andamento', 'Em Andamento'),
        ('concluido', 'Concluído'),
        ('cancelado', 'Cancelado'),
    ]

    nome = models.CharField(max_length=200)
    descricao = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='em_andamento')
    data_inicio = models.DateField(null=True, blank=True)
    data_fim = models.DateField(null=True, blank=True)

    escola = models.ForeignKey('Escola', on_delete=models.CASCADE, related_name='projetos')
    instituicao = models.ForeignKey('Instituicao', on_delete=models.CASCADE, related_name='projetos')

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    objects = TenantManager()

    class Meta:
        db_table = 'projetos'
        managed = True
        verbose_name = 'Projeto'
        verbose_name_plural = 'Projetos'
        indexes = [
            models.Index(fields=['escola', 'status']),
        ]

    def __str__(self):
        return self.nome

class Producao(ModeloBase):
    TIPOS = [
        ('foto', 'Foto'),
        ('video', 'Vídeo'),
        ('audio', 'Áudio'),
        ('documento', 'Documento'),
    ]

    tipo = models.CharField(max_length=20, choices=TIPOS, default='foto')
    titulo = models.CharField(max_length=200, blank=True, null=True)
    descricao = models.TextField(blank=True, null=True)
    arquivo_url = models.URLField(max_length=500, null=True, blank=True)
    arquivo_nome = models.CharField(max_length=255, null=True, blank=True)
    arquivo_hash = models.CharField(max_length=64, unique=True)
    mime_type = models.CharField(max_length=100, default='image/jpeg')
    tamanho_bytes = models.BigIntegerField(null=True, blank=True)
    tags = models.JSONField(default=list, blank=True)
    data_registro = models.DateField(null=True, blank=True)

    turma = models.ForeignKey('Turma', on_delete=models.CASCADE, related_name='producoes')
    professor = models.ForeignKey(
        'Usuario', on_delete=models.PROTECT, related_name='producoes',
    )
    projeto = models.ForeignKey(
        'Projeto', on_delete=models.SET_NULL, related_name='producoes',
        null=True, blank=True,
    )
    escola = models.ForeignKey('Escola', on_delete=models.CASCADE, related_name='producoes')
    instituicao = models.ForeignKey('Instituicao', on_delete=models.CASCADE, related_name='producoes')

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    objects = TenantManager()

    class Meta:
        db_table = 'producoes'
        managed = True
        verbose_name = 'Produção'
        verbose_name_plural = 'Produções'
        indexes = [
            models.Index(fields=['escola', 'data_registro']),
            models.Index(fields=['turma']),
        ]

    def __str__(self):
        return self.titulo or self.arquivo_nome or str(self.id)


class ProducaoAluno(ModeloBase):
    legenda = models.TextField(blank=True, default='')
    legenda_ia = models.TextField(blank=True, default='')
    destaque = models.BooleanField(default=False)
    incluir_relatorio = models.BooleanField(default=False)

    producao = models.ForeignKey('Producao', on_delete=models.CASCADE, related_name='producao_alunos')
    aluno = models.ForeignKey('Aluno', on_delete=models.CASCADE, related_name='producao_alunos')

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'producoes_alunos'
        managed = True
        verbose_name = 'Produção do Aluno'
        verbose_name_plural = 'Produções dos Alunos'
        constraints = [
            models.UniqueConstraint(fields=['producao', 'aluno'], name='unique_producao_aluno'),
        ]

    def __str__(self):
        return f"{self.aluno.nome_completo} - {self.producao_id}"
class RegistroEscrita(ModeloBase):
    ETAPAS = [
        ('educacao_infantil', 'Educação Infantil'),
        ('ensino_fundamental', 'Ensino Fundamental'),
    ]

    etapa = models.CharField(max_length=30, choices=ETAPAS, blank=True, null=True)
    arquivo_nome = models.CharField(max_length=255)
    arquivo_hash = models.CharField(max_length=50, unique=True)
    arquivo_path = models.CharField(max_length=500)
    arquivo_original = models.CharField(max_length=255)
    tamanho_arquivo = models.IntegerField()
    tipo_arquivo = models.CharField(max_length=100)
    etapa_ia = models.CharField(max_length=100, blank=True, null=True)
    analise_detalhada = models.TextField(blank=True, null=True)
    anotacoes_professora = models.TextField(blank=True, null=True)

    aluno = models.ForeignKey('Aluno', on_delete=models.CASCADE, related_name='registros_escrita')
    turma = models.ForeignKey('Turma', on_delete=models.CASCADE, related_name='registros_escrita')
    professor = models.ForeignKey('Usuario', on_delete=models.PROTECT, related_name='registros_escrita')
    escola = models.ForeignKey('Escola', on_delete=models.CASCADE, related_name='registros_escrita')
    instituicao = models.ForeignKey('Instituicao', on_delete=models.CASCADE, related_name='registros_escrita')

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    objects = TenantManager()

    class Meta:
        db_table = 'registro_escrita'
        managed = True
        verbose_name = 'Registro de Escrita'
        verbose_name_plural = 'Registros de Escrita'
        ordering = ['-criado_em']
        indexes = [
            models.Index(fields=['aluno', '-criado_em']),
            models.Index(fields=['escola']),
        ]

    def __str__(self):
        return f"{self.aluno.nome_completo} - {self.etapa_ia or 'sem etapa'}"


class RegistroDesenho(ModeloBase):
    ETAPAS = [
        ('educacao_infantil', 'Educação Infantil'),
        ('ensino_fundamental', 'Ensino Fundamental'),
    ]

    etapa = models.CharField(max_length=30, choices=ETAPAS, blank=True, null=True)
    atividade = models.CharField(max_length=200, default='Desenho Livre')
    contexto = models.TextField(blank=True, null=True)
    fase_desenho = models.CharField(max_length=100, blank=True, null=True)
    elementos_detectados = models.JSONField(default=list, blank=True)
    analise_detalhada = models.TextField(blank=True, null=True)
    anotacoes_professora = models.TextField(blank=True, null=True)
    arquivo_nome = models.CharField(max_length=300)
    arquivo_hash = models.CharField(max_length=50, unique=True)
    arquivo_path = models.CharField(max_length=500)
    arquivo_original = models.CharField(max_length=300)
    tamanho_arquivo = models.BigIntegerField()
    tipo_arquivo = models.CharField(max_length=100)

    aluno = models.ForeignKey('Aluno', on_delete=models.CASCADE, related_name='registros_desenho')
    turma = models.ForeignKey('Turma', on_delete=models.CASCADE, related_name='registros_desenho')
    professor = models.ForeignKey('Usuario', on_delete=models.PROTECT, related_name='registros_desenho')
    escola = models.ForeignKey('Escola', on_delete=models.CASCADE, related_name='registros_desenho')
    instituicao = models.ForeignKey('Instituicao', on_delete=models.CASCADE, related_name='registros_desenho')

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    objects = TenantManager()

    class Meta:
        db_table = 'registro_desenho'
        managed = True
        verbose_name = 'Registro de Desenho'
        verbose_name_plural = 'Registros de Desenho'
        ordering = ['-criado_em']
        indexes = [
            models.Index(fields=['aluno', '-criado_em']),
            models.Index(fields=['escola']),
        ]

    def __str__(self):
        return f"Desenho de {self.aluno.nome_completo} - {self.fase_desenho or 'sem fase'}"

class RegistroLeitura(ModeloBase):
    STATUS_CHOICES = [
        ('pendente', 'Análise em andamento no NaraNN'),
        ('analisado', 'Análise pronta — aguardando confirmação da professora'),
        ('confirmado', 'Confirmado pela professora'),
        ('falhou', 'Falhou'),
        ('cancelado', 'Cancelado'),
    ]

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

    aluno = models.ForeignKey('Aluno', on_delete=models.CASCADE, related_name='registros_leitura')
    professor = models.ForeignKey('Usuario', on_delete=models.PROTECT, related_name='registros_leitura')
    turma = models.ForeignKey('Turma', on_delete=models.CASCADE, related_name='registros_leitura')
    escola = models.ForeignKey('Escola', on_delete=models.CASCADE, related_name='registros_leitura')
    instituicao = models.ForeignKey('Instituicao', on_delete=models.CASCADE, related_name='registros_leitura')

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    objects = TenantManager()

    class Meta:
        db_table = 'registro_leitura'
        managed = True
        verbose_name = 'Registro de Leitura'
        verbose_name_plural = 'Registros de Leitura'
        ordering = ['-criado_em']
        indexes = [
            models.Index(fields=['aluno', '-criado_em']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"Leitura de {self.aluno.nome_completo} - {self.classe_escolhida or 'pendente'}"

class CampoPedagogico(ModeloBase):
    ETAPAS = [
        ('educacao_infantil', 'Educação Infantil'),
        ('ensino_fundamental', 'Ensino Fundamental'),
    ]

    nome = models.CharField(max_length=200)
    etapa = models.CharField(max_length=30, choices=ETAPAS, blank=True, null=True)
    icone = models.CharField(max_length=50, default='BookOpen', blank=True)
    cor = models.CharField(max_length=20, blank=True, null=True)
    ativo = models.BooleanField(default=True)

    # escola/instituicao nulos = campo padrão do sistema (BNCC);
    # preenchidos = customizado por uma escola específica.
    escola = models.ForeignKey(
        'Escola', on_delete=models.CASCADE, related_name='campos_pedagogicos',
        null=True, blank=True,
    )
    instituicao = models.ForeignKey(
        'Instituicao', on_delete=models.CASCADE, related_name='campos_pedagogicos',
        null=True, blank=True,
    )

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    objects = TenantManager()
    todos = models.Manager()  # sem filtro de tenant — necessário pra combinar "oficial (nulo) OU da minha escola"

    class Meta:
        db_table = 'campos_pedagogicos'
        managed = True
        verbose_name = 'Campo Pedagógico'
        verbose_name_plural = 'Campos Pedagógicos'
        constraints = [
            models.UniqueConstraint(fields=['escola', 'nome'], name='unique_campo_pedagogico_por_escola'),
        ]

    def __str__(self):
        return self.nome


class HabilidadeBNCC(ModeloBase):
    codigo = models.CharField(max_length=20, unique=True)
    descricao = models.TextField()
    componente_curricular = models.CharField(max_length=100, blank=True, null=True)
    ano_serie = models.CharField(max_length=50, blank=True, null=True)
    campo_atuacao = models.CharField(max_length=200, blank=True, null=True)
    ativa = models.BooleanField(default=True)

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'habilidades_bncc'
        managed = True
        verbose_name = 'Habilidade BNCC'
        verbose_name_plural = 'Habilidades BNCC'

    def __str__(self):
        return f"{self.codigo} - {self.descricao[:50]}"

class Pergunta(ModeloBase):
    ORIGENS = [
        ('bncc', 'BNCC (obrigatória)'),
        ('escola', 'Customizada pela Escola'),
    ]

    pergunta = models.TextField()
    pergunta_norma = models.TextField(blank=True, null=True)
    area_conhecimento = models.TextField(blank=True, null=True)
    origem = models.CharField(max_length=20, choices=ORIGENS, default='bncc')
    ativa = models.BooleanField(default=True)

    # Texto, não FK: é um rótulo de NÍVEL ("Nível 5", "1º Ano"), compartilhado
    # por turmas paralelas (5º Ano A, 5º Ano B) — uma FK pra Turma amarraria
    # a pergunta a uma turma só. Casa com Turma.faixa_etaria via normalização
    # de texto (ver services/coordenacao_cache._padronizar_faixa).
    faixa_etaria = models.CharField(max_length=50, blank=True, default='')
    campo_experiencia = models.ForeignKey(
        'CampoPedagogico', on_delete=models.SET_NULL, related_name='perguntas',
        null=True, blank=True,
    )
    habilidade_bncc = models.ForeignKey(
        'HabilidadeBNCC', on_delete=models.SET_NULL, related_name='perguntas',
        null=True, blank=True,
    )

    # nulos = pergunta oficial BNCC; preenchidos = customizada pela escola.
    escola = models.ForeignKey(
        'Escola', on_delete=models.CASCADE, related_name='perguntas',
        null=True, blank=True,
    )
    instituicao = models.ForeignKey(
        'Instituicao', on_delete=models.CASCADE, related_name='perguntas',
        null=True, blank=True,
    )

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    objects = TenantManager()
    todos = models.Manager()  # sem filtro de tenant — necessário pra combinar "oficial (nulo) OU da minha escola"

    class Meta:
        db_table = 'perguntas'
        managed = True
        verbose_name = 'Pergunta'
        verbose_name_plural = 'Perguntas'
        indexes = [
            models.Index(fields=['escola', 'ativa']),
        ]

    def __str__(self):
        return self.pergunta[:80]


class PerguntaEspecialista(ModeloBase):
    STATUS_CHOICES = [
        ('ativa', 'Ativa'),
        ('inativa', 'Inativa'),
    ]

    pergunta = models.TextField()
    pergunta_facilitadora = models.TextField(blank=True, null=True)
    nivel = models.CharField(max_length=50, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ativa')

    campo_experiencia = models.ForeignKey(
        'CampoPedagogico', on_delete=models.SET_NULL, related_name='perguntas_especialistas',
        null=True, blank=True,
    )
    habilidade_bncc = models.ForeignKey(
        'HabilidadeBNCC', on_delete=models.SET_NULL, related_name='perguntas_especialistas',
        null=True, blank=True,
    )
    # Aponta direto pra Usuario, não pra Especialista (assim está no DBML).
    usuario_especialista = models.ForeignKey(
        'Usuario', on_delete=models.PROTECT, related_name='perguntas_especialistas',
    )
    escola = models.ForeignKey('Escola', on_delete=models.CASCADE, related_name='perguntas_especialistas')
    instituicao = models.ForeignKey('Instituicao', on_delete=models.CASCADE, related_name='perguntas_especialistas')

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    objects = TenantManager()

    class Meta:
        db_table = 'perguntas_especialistas'
        managed = True
        verbose_name = 'Pergunta de Especialista'
        verbose_name_plural = 'Perguntas de Especialistas'
        indexes = [
            models.Index(fields=['escola', 'status']),
        ]

    def __str__(self):
        return self.pergunta[:80]

class RegistroObservacao(ModeloBase):
    resposta = models.CharField(max_length=50, blank=True, null=True)
    observacao = models.TextField(blank=True, null=True)
    data_observacao = models.DateField(null=True, blank=True)

    # Apenas um dos dois deve ser preenchido — validado na aplicação, não no banco.
    pergunta = models.ForeignKey(
        'Pergunta', on_delete=models.SET_NULL, related_name='registros_observacao',
        null=True, blank=True,
    )
    pergunta_especialista = models.ForeignKey(
        'PerguntaEspecialista', on_delete=models.SET_NULL, related_name='registros_observacao',
        null=True, blank=True,
    )

    aluno = models.ForeignKey('Aluno', on_delete=models.CASCADE, related_name='registros_observacao')
    professor = models.ForeignKey('Usuario', on_delete=models.PROTECT, related_name='registros_observacao')
    escola = models.ForeignKey('Escola', on_delete=models.CASCADE, related_name='registros_observacao')
    instituicao = models.ForeignKey('Instituicao', on_delete=models.CASCADE, related_name='registros_observacao')

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    objects = TenantManager()

    class Meta:
        db_table = 'registros_observacao'
        managed = True
        verbose_name = 'Registro de Observação'
        verbose_name_plural = 'Registros de Observação'
        indexes = [
            models.Index(fields=['aluno', '-data_observacao']),
            models.Index(fields=['escola']),
        ]

    def __str__(self):
        return f"{self.aluno.nome_completo} - {self.data_observacao}"

class ObservacaoTranscricao(ModeloBase):
    aluno_nome = models.CharField(max_length=200, blank=True, null=True)
    observacao_texto = models.TextField(blank=True, null=True)
    tipo_observacao = models.CharField(max_length=30, default='TRANSCRICAO_IA')
    data_observacao = models.DateField(null=True, blank=True)
    transcricao_completa = models.TextField(blank=True, default='')
    metadados_ia = models.JSONField(default=dict, blank=True)

    # Nullable: a transcrição pode não ter conseguido identificar a criança
    # com segurança — aluno_nome guarda o nome cru extraído, aluno é o
    # vínculo confirmado (quando existe).
    aluno = models.ForeignKey(
        'Aluno', on_delete=models.SET_NULL, related_name='observacoes_transcricao',
        null=True, blank=True,
    )
    turma = models.ForeignKey('Turma', on_delete=models.CASCADE, related_name='observacoes_transcricao')
    professor = models.ForeignKey('Usuario', on_delete=models.PROTECT, related_name='observacoes_transcricao')
    escola = models.ForeignKey('Escola', on_delete=models.CASCADE, related_name='observacoes_transcricao')
    instituicao = models.ForeignKey('Instituicao', on_delete=models.CASCADE, related_name='observacoes_transcricao')

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    objects = TenantManager()

    class Meta:
        db_table = 'observacoes_transcricao'
        managed = True
        verbose_name = 'Observação de Transcrição'
        verbose_name_plural = 'Observações de Transcrição'
        indexes = [
            models.Index(fields=['turma', '-data_observacao']),
            models.Index(fields=['escola']),
        ]

    def __str__(self):
        return f"{self.aluno_nome or 'não identificado'} - {self.data_observacao}"
class PlanejamentoSemanal(ModeloBase):
    semana_inicio = models.DateField()
    semana_fim = models.DateField()
    ano_letivo = models.IntegerField(default=2027)

    turma = models.ForeignKey('Turma', on_delete=models.CASCADE, related_name='planejamentos_semanais')
    professor = models.ForeignKey('Usuario', on_delete=models.PROTECT, related_name='planejamentos_semanais')
    escola = models.ForeignKey('Escola', on_delete=models.CASCADE, related_name='planejamentos_semanais')
    instituicao = models.ForeignKey('Instituicao', on_delete=models.CASCADE, related_name='planejamentos_semanais')

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    objects = TenantManager()

    class Meta:
        db_table = 'planejamentos_semanais'
        managed = True
        verbose_name = 'Planejamento Semanal'
        verbose_name_plural = 'Planejamentos Semanais'
        constraints = [
            models.UniqueConstraint(fields=['turma', 'semana_inicio'], name='unique_planejamento_semanal_turma'),
        ]

    def __str__(self):
        return f"{self.turma.nome} - {self.semana_inicio}"


class PlanejamentoDiario(ModeloBase):
    DIAS_SEMANA = [
        ('segunda', 'Segunda-feira'),
        ('terca', 'Terça-feira'),
        ('quarta', 'Quarta-feira'),
        ('quinta', 'Quinta-feira'),
        ('sexta', 'Sexta-feira'),
    ]

    dia_semana = models.CharField(max_length=10, choices=DIAS_SEMANA, blank=True, null=True)
    data = models.DateField(null=True, blank=True)
    atividades_propostas = models.TextField(blank=True, null=True)
    prompt_ia = models.TextField(blank=True, null=True)
    arquivo_nome_original = models.CharField(max_length=255, blank=True, null=True)
    arquivo_storage_key = models.CharField(max_length=500, blank=True, null=True)
    arquivo_content_type = models.CharField(max_length=100, blank=True, null=True)

    planejamento_semanal = models.ForeignKey(
        'PlanejamentoSemanal', on_delete=models.CASCADE, related_name='planejamentos_diarios',
    )
    # O DBML não lista Ref explícito pra escola/instituicao nessa tabela,
    # mas os campos estão marcados [not null] — mantive as FKs seguindo o
    # padrão do resto do schema.
    escola = models.ForeignKey('Escola', on_delete=models.CASCADE, related_name='planejamentos_diarios')
    instituicao = models.ForeignKey('Instituicao', on_delete=models.CASCADE, related_name='planejamentos_diarios')

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    objects = TenantManager()

    class Meta:
        db_table = 'planejamentos_diarios'
        managed = True
        verbose_name = 'Planejamento Diário'
        verbose_name_plural = 'Planejamentos Diários'
        constraints = [
            models.UniqueConstraint(
                fields=['planejamento_semanal', 'dia_semana'],
                name='unique_planejamento_diario_dia',
            ),
        ]

    def __str__(self):
        return f"{self.planejamento_semanal} - {self.get_dia_semana_display()}"


class PlanejamentoHabilidade(ModeloBase):
    observacao_habilidade = models.TextField(blank=True, null=True)

    habilidade_bncc = models.ForeignKey(
        'HabilidadeBNCC', on_delete=models.CASCADE, related_name='planejamentos_habilidades',
    )
    planejamento_diario = models.ForeignKey(
        'PlanejamentoDiario', on_delete=models.CASCADE, related_name='planejamentos_habilidades',
    )

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'planejamentos_habilidades'
        managed = True
        verbose_name = 'Habilidade do Planejamento'
        verbose_name_plural = 'Habilidades do Planejamento'
        constraints = [
            models.UniqueConstraint(
                fields=['planejamento_diario', 'habilidade_bncc'],
                name='unique_planejamento_habilidade',
            ),
        ]

    def __str__(self):
        return f"{self.planejamento_diario} - {self.habilidade_bncc.codigo}"

class PeriodoAvaliativo(ModeloBase):
    TIPOS_PERIODO = [
        ('bimestral', 'Bimestral'),
        ('trimestral', 'Trimestral'),
        ('semestral', 'Semestral'),
        ('anual', 'Anual'),
    ]

    descricao = models.CharField(max_length=200)
    tipo_periodo = models.CharField(max_length=20, choices=TIPOS_PERIODO)
    ano = models.IntegerField(null=True, blank=True)
    numero = models.IntegerField(null=True, blank=True)
    data_inicio = models.DateField()
    data_fim = models.DateField()

    escola = models.ForeignKey('Escola', on_delete=models.CASCADE, related_name='periodos_avaliativos')
    instituicao = models.ForeignKey('Instituicao', on_delete=models.CASCADE, related_name='periodos_avaliativos')

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    objects = TenantManager()

    class Meta:
        db_table = 'periodos_avaliativos'
        managed = True
        verbose_name = 'Período Avaliativo'
        verbose_name_plural = 'Períodos Avaliativos'
        ordering = ['-data_inicio']
        indexes = [
            models.Index(fields=['escola', 'data_inicio', 'data_fim']),
        ]

    def __str__(self):
        return f"{self.descricao} ({self.get_tipo_periodo_display()})"


class RelatorioTemplate(ModeloBase):
    nome = models.CharField(max_length=100)
    modelo = models.CharField(max_length=20)
    usa_foto_aluno = models.BooleanField(default=False)
    config = models.JSONField(default=dict, blank=True)
    items_sumario = models.JSONField(default=list, blank=True)
    ativo = models.BooleanField(default=False)

    escola = models.ForeignKey('Escola', on_delete=models.CASCADE, related_name='relatorio_templates')
    instituicao = models.ForeignKey('Instituicao', on_delete=models.CASCADE, related_name='relatorio_templates')

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    objects = TenantManager()

    class Meta:
        db_table = 'relatorio_templates'
        managed = True
        verbose_name = 'Template de Relatório'
        verbose_name_plural = 'Templates de Relatório'
        constraints = [
            models.UniqueConstraint(fields=['escola', 'modelo'], name='unique_relatorio_template_por_escola'),
        ]

    def __str__(self):
        return self.nome


class Relatorio(ModeloBase):
    conteudo = models.TextField(blank=True, null=True)
    pdf_url = models.URLField(max_length=500, null=True, blank=True)
    pdf_storage_key = models.CharField(max_length=500, null=True, blank=True)
    periodo = models.TextField(blank=True, null=True)

    aluno = models.ForeignKey('Aluno', on_delete=models.CASCADE, related_name='relatorios')
    template = models.ForeignKey(
        'RelatorioTemplate', on_delete=models.SET_NULL, related_name='relatorios',
        null=True, blank=True,
    )
    revisado_por = models.ForeignKey(
        'Usuario', on_delete=models.SET_NULL, related_name='relatorios_revisados',
        null=True, blank=True,
    )
    escola = models.ForeignKey('Escola', on_delete=models.CASCADE, related_name='relatorios')
    instituicao = models.ForeignKey('Instituicao', on_delete=models.CASCADE, related_name='relatorios')

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    objects = TenantManager()

    class Meta:
        db_table = 'relatorios'
        managed = True
        verbose_name = 'Relatório'
        verbose_name_plural = 'Relatórios'
        constraints = [
            models.UniqueConstraint(fields=['aluno', 'escola'], name='unique_relatorio_aluno_escola'),
        ]

    def __str__(self):
        return f"Relatório de {self.aluno.nome_completo} ({self.periodo})"

class Notificacao(ModeloBase):
    tipo = models.CharField(max_length=50)
    titulo = models.CharField(max_length=200, blank=True, null=True)
    conteudo = models.TextField(blank=True, null=True)
    lido_em = models.DateTimeField(null=True, blank=True)

    # Nulo = alerta gerado pelo próprio sistema, não por outro usuário.
    remetente = models.ForeignKey(
        'Usuario', on_delete=models.SET_NULL, related_name='notificacoes_enviadas',
        null=True, blank=True,
    )
    usuario = models.ForeignKey('Usuario', on_delete=models.CASCADE, related_name='notificacoes')
    escola = models.ForeignKey(
        'Escola', on_delete=models.CASCADE, related_name='notificacoes',
        null=True, blank=True,
    )
    instituicao = models.ForeignKey('Instituicao', on_delete=models.CASCADE, related_name='notificacoes')

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    objects = TenantManager()

    class Meta:
        db_table = 'notificacoes'
        managed = True
        verbose_name = 'Notificação'
        verbose_name_plural = 'Notificações'
        ordering = ['-criado_em']
        indexes = [
            models.Index(fields=['usuario', '-criado_em']),
        ]

    def __str__(self):
        return f"{self.titulo or self.tipo} → {self.usuario.nome}"


class MetaPAEE(ModeloBase):
    STATUS_CHOICES = [
        ('ativa', 'Ativa'),
        ('concluida', 'Concluída'),
        ('cancelada', 'Cancelada'),
    ]

    categoria = models.CharField(max_length=30, blank=True, null=True)
    inicio = models.DateField(null=True, blank=True)
    fim = models.DateField(null=True, blank=True)
    objetivo = models.TextField(blank=True, null=True)
    criterio = models.TextField(blank=True, null=True)
    estrategia = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ativa')

    aluno = models.ForeignKey('Aluno', on_delete=models.CASCADE, related_name='metas_paee')
    usuario_especialista = models.ForeignKey(
        'Usuario', on_delete=models.PROTECT, related_name='metas_paee',
    )
    # Nullable: a turma do aluno pode mudar ao longo do tempo, a meta continua valendo.
    turma = models.ForeignKey(
        'Turma', on_delete=models.SET_NULL, related_name='metas_paee',
        null=True, blank=True,
    )
    escola = models.ForeignKey('Escola', on_delete=models.CASCADE, related_name='metas_paee')
    instituicao = models.ForeignKey('Instituicao', on_delete=models.CASCADE, related_name='metas_paee')

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    objects = TenantManager()

    class Meta:
        db_table = 'metas_paee'
        managed = True
        verbose_name = 'Meta PAEE'
        verbose_name_plural = 'Metas PAEE'
        indexes = [
            models.Index(fields=['aluno', 'status']),
        ]

    def __str__(self):
        return f"{self.aluno.nome_completo} - {self.categoria or 'sem categoria'}"


class SessaoEspecialista(ModeloBase):
    STATUS_CHOICES = [
        ('pendente', 'Pendente'),
        ('realizada', 'Realizada'),
        ('cancelada', 'Cancelada'),
    ]

    data_atendimento = models.DateField(null=True, blank=True)
    duracao = models.IntegerField(null=True, blank=True, help_text="Duração em minutos")
    resumo = models.TextField(blank=True, default='')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pendente')

    aluno = models.ForeignKey('Aluno', on_delete=models.CASCADE, related_name='sessoes_especialista')
    usuario_especialista = models.ForeignKey(
        'Usuario', on_delete=models.PROTECT, related_name='sessoes_especialista',
    )
    turma = models.ForeignKey(
        'Turma', on_delete=models.SET_NULL, related_name='sessoes_especialista',
        null=True, blank=True,
    )
    escola = models.ForeignKey('Escola', on_delete=models.CASCADE, related_name='sessoes_especialista')
    instituicao = models.ForeignKey('Instituicao', on_delete=models.CASCADE, related_name='sessoes_especialista')

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    objects = TenantManager()

    class Meta:
        db_table = 'sessoes_especialista'
        managed = True
        verbose_name = 'Sessão de Especialista'
        verbose_name_plural = 'Sessões de Especialista'
        indexes = [
            models.Index(fields=['aluno', '-data_atendimento']),
        ]

    def __str__(self):
        return f"{self.aluno.nome_completo} - {self.data_atendimento}"


class SessaoPAEEMeta(ModeloBase):
    sessao_especialista = models.ForeignKey(
        'SessaoEspecialista', on_delete=models.CASCADE, related_name='sessao_metas',
    )
    meta_paee = models.ForeignKey(
        'MetaPAEE', on_delete=models.CASCADE, related_name='sessao_metas',
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'sessoes_paee_metas'
        managed = True
        verbose_name = 'Meta da Sessão PAEE'
        verbose_name_plural = 'Metas da Sessão PAEE'
        constraints = [
            models.UniqueConstraint(
                fields=['sessao_especialista', 'meta_paee'],
                name='unique_sessao_meta_paee',
            ),
        ]

    def __str__(self):
        return f"{self.sessao_especialista} - {self.meta_paee}"


class TarefaPAEE(ModeloBase):
    descricao = models.TextField(blank=True, null=True)
    concluida = models.BooleanField(default=False)
    observacao_professor = models.TextField(blank=True, default='')
    data_conclusao = models.DateTimeField(null=True, blank=True)

    meta_paee = models.ForeignKey('MetaPAEE', on_delete=models.CASCADE, related_name='tarefas')
    professor_conclusao = models.ForeignKey(
        'Usuario', on_delete=models.SET_NULL, related_name='tarefas_paee_concluidas',
        null=True, blank=True,
    )
    escola = models.ForeignKey('Escola', on_delete=models.CASCADE, related_name='tarefas_paee')
    instituicao = models.ForeignKey('Instituicao', on_delete=models.CASCADE, related_name='tarefas_paee')

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    objects = TenantManager()

    class Meta:
        db_table = 'tarefas_paee'
        managed = True
        verbose_name = 'Tarefa PAEE'
        verbose_name_plural = 'Tarefas PAEE'
        indexes = [
            models.Index(fields=['meta_paee', 'concluida']),
        ]

    def __str__(self):
        return f"{self.descricao[:60] if self.descricao else self.id}"


class DispositivoGravador(ModeloBase):
    device_id = models.CharField(max_length=100, unique=True)
    nome = models.CharField(max_length=120, blank=True, default='')
    token_hash = models.CharField(max_length=128, blank=True, null=True)
    ativo = models.BooleanField(default=True)
    revogado_em = models.DateTimeField(null=True, blank=True)
    visto_ultimo = models.DateTimeField(null=True, blank=True)

    professor = models.ForeignKey('Usuario', on_delete=models.PROTECT, related_name='dispositivos_gravador')
    turma_ativa = models.ForeignKey(
        'Turma', on_delete=models.SET_NULL, related_name='dispositivos_com_turma_ativa',
        null=True, blank=True,
    )
    escola = models.ForeignKey('Escola', on_delete=models.CASCADE, related_name='dispositivos_gravador')
    instituicao = models.ForeignKey('Instituicao', on_delete=models.CASCADE, related_name='dispositivos_gravador')
    turmas = models.ManyToManyField(
        'Turma', through='DispositivoGravadorTurma', related_name='dispositivos_gravadores',
    )

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    objects = TenantManager()

    class Meta:
        db_table = 'dispositivos_gravador'
        managed = True
        verbose_name = 'Dispositivo Gravador'
        verbose_name_plural = 'Dispositivos Gravadores'
        indexes = [
            models.Index(fields=['escola', 'ativo']),
        ]

    def __str__(self):
        return self.nome or self.device_id


class DispositivoGravadorTurma(ModeloBase):
    dispositivo = models.ForeignKey(
        'DispositivoGravador', on_delete=models.CASCADE, related_name='turmas_vinculadas',
    )
    turma = models.ForeignKey('Turma', on_delete=models.CASCADE, related_name='dispositivos_vinculados')

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'dispositivos_gravador_turmas'
        managed = True
        verbose_name = 'Turma do Dispositivo'
        verbose_name_plural = 'Turmas dos Dispositivos'
        constraints = [
            models.UniqueConstraint(fields=['dispositivo', 'turma'], name='unique_dispositivo_turma'),
        ]

    def __str__(self):
        return f"{self.dispositivo} - {self.turma.nome}"


class CodigoPareamento(ModeloBase):
    codigo = models.CharField(max_length=12)
    expira_em = models.DateTimeField(null=True, blank=True)
    usado_em = models.DateTimeField(null=True, blank=True)

    professor = models.ForeignKey('Usuario', on_delete=models.PROTECT, related_name='codigos_pareamento')
    dispositivo = models.ForeignKey(
        'DispositivoGravador', on_delete=models.SET_NULL, related_name='codigos_pareamento',
        null=True, blank=True,
    )
    escola = models.ForeignKey('Escola', on_delete=models.CASCADE, related_name='codigos_pareamento')
    instituicao = models.ForeignKey('Instituicao', on_delete=models.CASCADE, related_name='codigos_pareamento')
    turmas = models.ManyToManyField(
        'Turma', through='CodigoPareamentoTurma', related_name='codigos_pareamento_relacionados',
    )

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    objects = TenantManager()

    @property
    def valido(self):
        """Uso único e ainda dentro da validade — não foi consumido nem expirou."""
        if self.usado_em is not None:
            return False
        if self.expira_em is not None and timezone.now() > self.expira_em:
            return False
        return True

    class Meta:
        db_table = 'codigos_pareamento'
        managed = True
        verbose_name = 'Código de Pareamento'
        verbose_name_plural = 'Códigos de Pareamento'
        indexes = [
            models.Index(fields=['codigo']),
        ]

    def __str__(self):
        return self.codigo


class CodigoPareamentoTurma(ModeloBase):
    codigo_pareamento = models.ForeignKey(
        'CodigoPareamento', on_delete=models.CASCADE, related_name='turmas_vinculadas',
    )
    turma = models.ForeignKey('Turma', on_delete=models.CASCADE, related_name='codigos_pareamento_vinculados')

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'codigos_pareamento_turmas'
        managed = True
        verbose_name = 'Turma do Código de Pareamento'
        verbose_name_plural = 'Turmas dos Códigos de Pareamento'
        constraints = [
            models.UniqueConstraint(
                fields=['codigo_pareamento', 'turma'], name='unique_codigo_pareamento_turma',
            ),
        ]

    def __str__(self):
        return f"{self.codigo_pareamento.codigo} - {self.turma.nome}"


class AudioDispositivo(ModeloBase):
    STATUS_CHOICES = [
        ('recebido', 'Recebido'),
        ('processando', 'Processando'),
        ('processado', 'Processado'),
        ('falhou', 'Falhou'),
        ('comando', 'Comando de sala (sem relato)'),
    ]

    upload_id = models.UUIDField()
    sha256 = models.CharField(max_length=64, blank=True, null=True)
    tamanho_arquivo = models.IntegerField(null=True, blank=True)
    duracao_seg = models.IntegerField(null=True, blank=True)
    arquivo_path = models.CharField(max_length=500, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='recebido')
    erro_processamento = models.TextField(blank=True, default='')
    erro_codigo = models.CharField(max_length=40, blank=True, default='')
    transcricao = models.TextField(blank=True, default='')
    turma_resultado = models.CharField(max_length=20, blank=True, default='')
    turma_anunciada_texto = models.CharField(max_length=200, blank=True, default='')
    total_observacoes = models.SmallIntegerField(default=0)
    alunos_identificados = models.JSONField(default=list, blank=True)
    nomes_nao_identificados = models.JSONField(default=list, blank=True)
    data_recebimento = models.DateTimeField(null=True, blank=True)
    data_processamento = models.DateTimeField(null=True, blank=True)

    dispositivo = models.ForeignKey('DispositivoGravador', on_delete=models.CASCADE, related_name='audios')
    professor = models.ForeignKey(
        'Usuario', on_delete=models.SET_NULL, related_name='audios_dispositivo',
        null=True, blank=True,
    )
    turma = models.ForeignKey(
        'Turma', on_delete=models.SET_NULL, related_name='audios_dispositivo',
        null=True, blank=True,
    )
    observacao = models.ForeignKey(
        'ObservacaoTranscricao', on_delete=models.SET_NULL, related_name='audios_origem',
        null=True, blank=True,
    )
    escola = models.ForeignKey('Escola', on_delete=models.CASCADE, related_name='audios_dispositivo')
    instituicao = models.ForeignKey('Instituicao', on_delete=models.CASCADE, related_name='audios_dispositivo')

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    objects = TenantManager()

    class Meta:
        db_table = 'audios_dispositivo'
        managed = True
        verbose_name = 'Áudio do Dispositivo'
        verbose_name_plural = 'Áudios dos Dispositivos'
        constraints = [
            models.UniqueConstraint(
                fields=['dispositivo', 'upload_id'], name='unique_audio_por_dispositivo_upload',
            ),
        ]
        indexes = [
            models.Index(fields=['escola', 'data_recebimento']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"{self.dispositivo} - {self.status}"

    @property
    def feedback(self):
        """
        Resumo pro firmware decidir LED/bipe. Construído a partir de status/
        turma_resultado/erro_codigo — não veio de nenhuma fonte legada que
        tivéssemos (só sabíamos que a view consome `audio.feedback`), então
        é uma implementação nova, não um port fiel. Ajustar se o
        comportamento esperado pelo firmware for diferente.
        """
        if self.status in ('recebido', 'processando'):
            return {'sinal': 'aguardando', 'mensagem': 'Processando o áudio...'}

        if self.status == 'falhou':
            return {
                'sinal': 'erro',
                'mensagem': f'Falha ao processar: {self.erro_processamento or self.erro_codigo or "erro desconhecido"}',
            }

        if self.status == 'comando':
            return {
                'sinal': 'ok',
                'mensagem': f'Turma trocada para "{self.turma.nome}".' if self.turma_id else 'Comando de troca de turma recebido.',
            }

        # status == 'processado'
        if self.turma_resultado == 'nao_autorizada':
            return {
                'sinal': 'atencao',
                'mensagem': f'Turma "{self.turma_anunciada_texto}" não autorizada para este gravador.',
            }
        if self.turma_resultado == 'indefinida':
            return {'sinal': 'atencao', 'mensagem': 'Não foi possível identificar a turma.'}
        if self.nomes_nao_identificados:
            return {
                'sinal': 'atencao',
                'mensagem': f'{len(self.nomes_nao_identificados)} nome(s) não reconhecido(s) na gravação.',
            }
        return {'sinal': 'ok', 'mensagem': 'Áudio processado com sucesso.'}


class PromptCategoria(ModeloBase):
    titulo = models.CharField(max_length=200)
    ativo = models.BooleanField(default=True)

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'prompt_categorias'
        managed = True
        verbose_name = 'Categoria de Prompt'
        verbose_name_plural = 'Categorias de Prompt'

    def __str__(self):
        return self.titulo


class PromptTemplate(ModeloBase):
    prompt_global = models.TextField(blank=True, default='')
    personalizado = models.TextField(blank=True, default='')

    categoria = models.ForeignKey('PromptCategoria', on_delete=models.CASCADE, related_name='templates')
    # nulos = prompt padrão do sistema; preenchidos = customizado pela escola.
    escola = models.ForeignKey(
        'Escola', on_delete=models.CASCADE, related_name='prompt_templates',
        null=True, blank=True,
    )
    instituicao = models.ForeignKey(
        'Instituicao', on_delete=models.CASCADE, related_name='prompt_templates',
        null=True, blank=True,
    )

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    objects = TenantManager()

    class Meta:
        db_table = 'prompt_templates'
        managed = True
        verbose_name = 'Template de Prompt'
        verbose_name_plural = 'Templates de Prompt'

    def __str__(self):
        return f"{self.categoria.titulo} - {self.escola or 'padrão do sistema'}"


class OpenAIUsage(ModeloBase):
    input_tokens = models.BigIntegerField()
    image_tokens = models.BigIntegerField(default=0)
    output_tokens = models.BigIntegerField()
    input_cost = models.DecimalField(max_digits=14, decimal_places=8)
    output_cost = models.DecimalField(max_digits=14, decimal_places=8)
    total_cost = models.DecimalField(max_digits=14, decimal_places=8)
    model = models.CharField(max_length=100, null=True, blank=True)

    usuario = models.ForeignKey(
        'Usuario', on_delete=models.SET_NULL, related_name='consumos_openai',
        null=True, blank=True,
    )
    escola = models.ForeignKey(
        'Escola', on_delete=models.SET_NULL, related_name='consumos_openai',
        null=True, blank=True,
    )
    instituicao = models.ForeignKey(
        'Instituicao', on_delete=models.SET_NULL, related_name='consumos_openai',
        null=True, blank=True,
    )

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    objects = TenantManager()

    class Meta:
        db_table = 'openai_usage'
        managed = True
        verbose_name = 'Uso da API OpenAI'
        verbose_name_plural = 'Usos da API OpenAI'
        ordering = ['-criado_em']
        indexes = [
            models.Index(fields=['-criado_em']),
            models.Index(fields=['model', '-criado_em']),
            models.Index(fields=['usuario', '-criado_em']),
            models.Index(fields=['escola', '-criado_em']),
        ]

    def __str__(self):
        return f"OpenAIUsage #{self.id} {self.model or '?'} (${self.total_cost})"


class CoordenacaoCache(ModeloBase):
    data_referencia = models.DateField(db_index=True)
    janela_dias = models.PositiveIntegerField(default=30)
    payload = models.JSONField()
    versao_schema = models.CharField(max_length=20, default='1')

    escola = models.ForeignKey('Escola', on_delete=models.CASCADE, related_name='coordenacao_cache')
    instituicao = models.ForeignKey('Instituicao', on_delete=models.CASCADE, related_name='coordenacao_cache')

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    objects = TenantManager()

    class Meta:
        db_table = 'coordenacao_cache'
        managed = True
        verbose_name = 'Cache da Coordenação'
        verbose_name_plural = 'Caches da Coordenação'
        ordering = ['-data_referencia']
        constraints = [
            models.UniqueConstraint(
                fields=['escola', 'data_referencia'], name='unique_coordenacao_cache_escola_data',
            ),
        ]
        indexes = [
            models.Index(fields=['escola', '-data_referencia']),
        ]

    def __str__(self):
        return f"CoordenacaoCache {self.escola_id} @ {self.data_referencia}"

class TemplateDocumento(ModeloBase):
    TIPOS = [
        ('contrato', 'Contrato'),
        ('termo', 'Termo'),
        ('outro', 'Outro'),
    ]

    titulo = models.CharField(max_length=200)
    documento = models.TextField()
    tipo = models.CharField(max_length=30, choices=TIPOS, default='contrato')
    ativo = models.BooleanField(default=True)

    responsavel = models.ForeignKey(
        'Usuario', on_delete=models.PROTECT, related_name='templates_documentos_responsavel',
    )
    criado_por = models.ForeignKey(
        'Usuario', on_delete=models.PROTECT, related_name='templates_documentos_criados',
    )
    atualizado_por = models.ForeignKey(
        'Usuario', on_delete=models.SET_NULL, related_name='templates_documentos_atualizados',
        null=True, blank=True,
    )
    escola = models.ForeignKey(
        'Escola', on_delete=models.CASCADE, related_name='templates_documentos',
        null=True, blank=True,
    )
    instituicao = models.ForeignKey(
        'Instituicao', on_delete=models.CASCADE, related_name='templates_documentos',
        null=True, blank=True,
    )

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    objects = TenantManager()

    class Meta:
        db_table = 'templates_documentos'
        managed = True
        verbose_name = 'Template de Documento'
        verbose_name_plural = 'Templates de Documento'

    def __str__(self):
        return self.titulo


class Contrato(ModeloBase):
    STATUS_CHOICES = [
        ('rascunho', 'Rascunho'),
        ('gerado', 'Gerado'),
        ('enviado_assinatura', 'Enviado para Assinatura'),
        ('assinado', 'Assinado'),
        ('cancelado', 'Cancelado'),
    ]

    documento = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='rascunho')
    arquivo_url = models.URLField(max_length=500, null=True, blank=True)

    template = models.ForeignKey(
        'TemplateDocumento', on_delete=models.SET_NULL, related_name='contratos',
        null=True, blank=True,
    )
    escola = models.ForeignKey('Escola', on_delete=models.CASCADE, related_name='contratos')
    instituicao = models.ForeignKey('Instituicao', on_delete=models.CASCADE, related_name='contratos')
    responsavel = models.ForeignKey(
        'Usuario', on_delete=models.PROTECT, related_name='contratos_responsavel',
    )
    gerado_por = models.ForeignKey(
        'Usuario', on_delete=models.PROTECT, related_name='contratos_gerados',
    )
    atualizado_por = models.ForeignKey(
        'Usuario', on_delete=models.SET_NULL, related_name='contratos_atualizados',
        null=True, blank=True,
    )

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    objects = TenantManager()

    class Meta:
        db_table = 'contratos'
        managed = True
        verbose_name = 'Contrato'
        verbose_name_plural = 'Contratos'
        indexes = [
            models.Index(fields=['escola', 'status']),
        ]

    def __str__(self):
        return f"Contrato {self.id} - {self.escola.nome} ({self.status})"

class Ticket(ModeloBase):
    STATUS_CHOICES = [
        ('em_aberto', 'Em Aberto'),
        ('em_atendimento', 'Em Atendimento'),
        ('resolvido', 'Resolvido'),
    ]
    CATEGORIAS = [
        ('sugestao', 'Sugestão'),
        ('duvida', 'Dúvida'),
        ('mau_funcionamento', 'Mau Funcionamento'),
        ('solicitacao_acesso', 'Solicitação de Acesso'),
        ('financeiro', 'Financeiro'),
    ]
    PRIORIDADES = [
        ('alta', 'Alta'),
        ('media', 'Média'),
        ('baixa', 'Baixa'),
    ]

    protocolo = models.CharField(max_length=20, unique=True)
    titulo = models.CharField(max_length=200)
    descricao = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='em_aberto')
    categoria = models.CharField(max_length=30, choices=CATEGORIAS)
    prioridade = models.CharField(max_length=10, choices=PRIORIDADES, default='media')

    usuario_solicitante = models.ForeignKey(
        'Usuario', on_delete=models.PROTECT, related_name='tickets_solicitados',
    )
    escola = models.ForeignKey(
        'Escola', on_delete=models.SET_NULL, related_name='tickets',
        null=True, blank=True,
    )
    instituicao = models.ForeignKey(
        'Instituicao', on_delete=models.SET_NULL, related_name='tickets',
        null=True, blank=True,
    )
    responsavel = models.ForeignKey(
        'Usuario', on_delete=models.SET_NULL, related_name='tickets_atendidos',
        null=True, blank=True,
    )

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    objects = TenantManager()

    class Meta:
        db_table = 'tickets'
        managed = True
        verbose_name = 'Ticket'
        verbose_name_plural = 'Tickets'
        ordering = ['-criado_em']

    def __str__(self):
        return f"{self.protocolo} - {self.titulo}"


class RespostaTicket(ModeloBase):
    descricao = models.TextField()

    usuario = models.ForeignKey('Usuario', on_delete=models.PROTECT, related_name='respostas_tickets')
    escola = models.ForeignKey(
        'Escola', on_delete=models.SET_NULL, related_name='respostas_tickets',
        null=True, blank=True,
    )
    instituicao = models.ForeignKey(
        'Instituicao', on_delete=models.SET_NULL, related_name='respostas_tickets',
        null=True, blank=True,
    )
    ticket = models.ForeignKey('Ticket', on_delete=models.CASCADE, related_name='respostas')

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    objects = TenantManager()

    class Meta:
        db_table = 'respostas_tickets'
        managed = True
        verbose_name = 'Resposta de Ticket'
        verbose_name_plural = 'Respostas de Tickets'
        ordering = ['criado_em']

    def __str__(self):
        return f"Resposta ao {self.ticket.protocolo}"


class AnexoTicket(ModeloBase):
    arquivo_url = models.URLField(max_length=500)
    arquivo_nome = models.CharField(max_length=255, blank=True, null=True)
    mime_type = models.CharField(max_length=100, blank=True, null=True)
    tamanho_bytes = models.BigIntegerField(null=True, blank=True)

    ticket = models.ForeignKey(
        'Ticket', on_delete=models.CASCADE, related_name='anexos',
        null=True, blank=True,
    )
    ticket_reply = models.ForeignKey(
        'RespostaTicket', on_delete=models.CASCADE, related_name='anexos',
        null=True, blank=True,
    )

    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'anexos_tickets'
        managed = True
        verbose_name = 'Anexo de Ticket'
        verbose_name_plural = 'Anexos de Tickets'

    def __str__(self):
        return self.arquivo_nome or str(self.id)

class LogAuditoria(ModeloBase):
    ACOES = [
        ('create', 'Criação'),
        ('update', 'Atualização'),
        ('delete', 'Exclusão'),
    ]

    acao = models.CharField(max_length=20, choices=ACOES)
    tabela_afetada = models.CharField(max_length=100)
    registro_id = models.BigIntegerField()  # id (int) do registro afetado
    alteracoes = models.JSONField(default=dict, blank=True)
    ip = models.CharField(max_length=255, blank=True, null=True)

    usuario = models.ForeignKey(
        'Usuario', on_delete=models.SET_NULL, related_name='logs_auditoria',
        null=True, blank=True,
    )
    escola = models.ForeignKey(
        'Escola', on_delete=models.SET_NULL, related_name='logs_auditoria',
        null=True, blank=True,
    )
    instituicao = models.ForeignKey(
        'Instituicao', on_delete=models.SET_NULL, related_name='logs_auditoria',
        null=True, blank=True,
    )

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    objects = TenantManager()

    class Meta:
        db_table = 'logs_auditoria'
        managed = True
        verbose_name = 'Log de Auditoria'
        verbose_name_plural = 'Logs de Auditoria'
        ordering = ['-criado_em']
        indexes = [
            models.Index(fields=['tabela_afetada', 'registro_id']),
            models.Index(fields=['usuario', 'criado_em']),
            models.Index(fields=['-criado_em']),
        ]

    def __str__(self):
        return f"{self.acao} em {self.tabela_afetada}#{self.registro_id}"


class PermissaoUsuario(ModeloBase):
    ACOES = [
        ('criar', 'Criar'),
        ('ver', 'Ver'),
        ('editar', 'Editar'),
        ('deletar', 'Deletar'),
    ]

    modulo = models.CharField(max_length=100)
    acao = models.CharField(max_length=20, choices=ACOES)
    concedido = models.BooleanField()

    usuario = models.ForeignKey('Usuario', on_delete=models.CASCADE, related_name='permissoes')
    escola = models.ForeignKey('Escola', on_delete=models.CASCADE, related_name='permissoes_usuario')
    instituicao = models.ForeignKey('Instituicao', on_delete=models.CASCADE, related_name='permissoes_usuario')
    concedido_por = models.ForeignKey(
        'Usuario', on_delete=models.SET_NULL, related_name='permissoes_concedidas',
        null=True, blank=True,
    )

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    objects = TenantManager()

    class Meta:
        db_table = 'permissoes_usuario'
        managed = True
        verbose_name = 'Permissão de Usuário'
        verbose_name_plural = 'Permissões de Usuário'
        constraints = [
            models.UniqueConstraint(
                fields=['usuario', 'modulo', 'escola', 'acao'],
                name='unique_permissao_usuario',
            ),
        ]

    def __str__(self):
        return f"{self.usuario.nome} - {self.modulo}/{self.acao} ({'concedido' if self.concedido else 'revogado'})"