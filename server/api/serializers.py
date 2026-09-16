"""
Serializers para a API REST NARA.
Provê conversão entre models Django e JSON para endpoints RESTful.
"""

from rest_framework import serializers
from .models import (
    Crianca,
    Relatorio,
    PerguntaBNCC,
    PerguntaEspecialista,
    CampoExperienciaCustomizado,
    RegistroObservacao,
    ProducaoCrianca,
    Projeto,
    CalendarioBimestre,
    PeriodoAvaliativo,
    Turma,
    ConfiguracaoRegistro,
    Instituicao,
    Usuario,
    UsuarioTurma,
    MensagemCoordenacao,
    MensagemLida,
    AlertaLido,
    PlanejamentoSemanal,
    PlanejamentoDiario,
    SerieConfig,
    PromptTemplate,
    PromptCategoria,
    RelatorioTemplate,
    Disciplina,
    UsuarioDisciplina,
)


class SerieConfigSerializer(serializers.ModelSerializer):
    """Serializer para o model SerieConfig."""

    class Meta:
        model = SerieConfig
        fields = [
            'id',
            'nome',
            'etapa',
            'ordem',
            'idade_min',
            'idade_max',
            'ativa',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class CriancaSerializer(serializers.ModelSerializer):
    """Serializer para o model Crianca."""

    foto_url = serializers.SerializerMethodField()

    class Meta:
        model = Crianca
        fields = [
            'id',
            'nome_completo',
            'data_nascimento',
            'genero',
            'turma_id',
            'instituicao_id',
            'nome_responsavel',
            'telefone_responsavel',
            'status_vinculo',
            'observacoes',
            'foto_url',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']

    def get_foto_url(self, obj):
        from api.storage import get_foto_url
        return get_foto_url(obj)


class CriancaListSerializer(serializers.ModelSerializer):
    """Serializer resumido para listagens de crianças."""
    turma_nome = serializers.SerializerMethodField()
    foto_url = serializers.SerializerMethodField()

    class Meta:
        model = Crianca
        fields = [
            'id', 'nome_completo', 'data_nascimento', 'turma_id',
            'instituicao_id', 'nome_responsavel', 'telefone_responsavel',
            'status_vinculo', 'turma_nome', 'foto_url',
        ]

    def get_turma_nome(self, obj):
        cache = self.context.get('turma_names')
        if cache is not None:
            return cache.get(obj.turma_id)
        try:
            return Turma.objects.only('nome').get(id=obj.turma_id).nome
        except Turma.DoesNotExist:
            return None

    def get_foto_url(self, obj):
        from api.storage import get_foto_url
        return get_foto_url(obj)


class RelatorioSerializer(serializers.ModelSerializer):
    """Serializer completo (inclui conteudo)."""

    template_nome = serializers.CharField(
        source='template.nome',
        read_only=True,
        default=None
    )
    template_config = serializers.SerializerMethodField()

    class Meta:
        model = Relatorio
        fields = [
            'id',
            'id_crianca',
            'periodo',
            'conteudo',
            'revisado_por',
            'pdf_url',
            'template',
            'template_nome',
            'template_config',
            'instituicao_id',
            'data_criacao',
        ]
        read_only_fields = ['id', 'data_criacao']

    def get_template_config(self, obj):
        if not obj.template_id or not obj.template:
            return None
        return obj.template.config


class RelatorioListSerializer(serializers.ModelSerializer):
    """Serializer para listagens."""

    finalizado = serializers.SerializerMethodField()

    template_nome = serializers.CharField(
        source='template.nome',
        read_only=True,
        default=None
    )

    class Meta:
        model = Relatorio
        fields = [
            'id',
            'id_crianca',
            'periodo',
            'revisado_por',
            'pdf_url',
            'template',
            'template_nome',
            'instituicao_id',
            'data_criacao',
            'finalizado',
        ]
        read_only_fields = ['id', 'data_criacao']

    def get_finalizado(self, obj):
        length = getattr(obj, 'conteudo_length', None)

        if length is None:
            length = len(obj.conteudo or '')

        return bool(length and length > 50)


class RelatorioCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Relatorio
        fields = ['id_crianca', 'periodo', 'conteudo', 'instituicao_id', 'template']
        extra_kwargs = {'template': {'required': False, 'allow_null': True}}

    def validate(self, data):
        template = data.get('template')
        instituicao_id = self.context.get('instituicao_id')
        if template and str(template.instituicao_id) != str(instituicao_id):
            raise serializers.ValidationError(
                {'template': 'Template não pertence à instituição do usuário.'}
            )
        return data


class RelatorioTemplateSerializer(serializers.ModelSerializer):
    modelo_display = serializers.CharField(
        source='get_modelo_display',
        read_only=True
    )

    class Meta:
        model = RelatorioTemplate
        fields = [
            'id',
            'instituicao_id',
            'nome',
            'modelo',
            'modelo_display',
            'usa_foto_crianca',
            'config',
            'items_sumario',
            'ativo',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'instituicao_id',
            'created_at',
            'updated_at',
        ]


class RelatorioTemplateListSerializer(serializers.ModelSerializer):
    modelo_display = serializers.CharField(
        source='get_modelo_display',
        read_only=True
    )

    class Meta:
        model = RelatorioTemplate
        fields = [
            'id',
            'nome',
            'modelo',
            'modelo_display',
            'usa_foto_crianca',
            'ativo',
            'updated_at',
        ]
        
class PerguntaBNCCSerializer(serializers.ModelSerializer):
    """Serializer para o model PerguntaBNCC."""

    class Meta:
        model = PerguntaBNCC
        fields = [
            'id',
            'faixa_etaria',
            'campo_experiencia',
            'pergunta',
            'pergunta_norma',
            'habilidade_bncc',
            'area_conhecimento',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class PerguntaEspecialistaSerializer(serializers.ModelSerializer):
    """Serializer para o model PerguntaEspecialista."""

    class Meta:
        model = PerguntaEspecialista
        fields = [
            'id',
            'instituicao_id',
            'especialidade',
            'campo_experiencia',
            'nivel',
            'pergunta',
            'pergunta_facilitadora',
            'referencia_norma',
            'status',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']

    def validate(self, attrs):
        pergunta_facilitadora = attrs.get('pergunta_facilitadora')
        referencia_norma = attrs.get('referencia_norma')

        if self.instance:
            if not pergunta_facilitadora:
                pergunta_facilitadora = self.instance.pergunta_facilitadora
            if not referencia_norma:
                referencia_norma = self.instance.referencia_norma

        if not pergunta_facilitadora:
            raise serializers.ValidationError({'pergunta_facilitadora': 'Campo obrigatório.'})
        if not referencia_norma:
            raise serializers.ValidationError({'referencia_norma': 'Campo obrigatório.'})

        if not attrs.get('pergunta'):
            attrs['pergunta'] = pergunta_facilitadora

        return attrs


class CampoExperienciaCustomizadoSerializer(serializers.ModelSerializer):
    """Serializer para o model CampoExperienciaCustomizado."""

    class Meta:
        model = CampoExperienciaCustomizado
        fields = [
            'id',
            'instituicao_id',
            'nome',
            'icone',
            'cor',
            'ativo',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class RegistroObservacaoSerializer(serializers.ModelSerializer):
    """Serializer para o model RegistroObservacao."""

    class Meta:
        model = RegistroObservacao
        fields = [
            'id',
            'crianca_id',
            'pergunta_id',
            'resposta',
            'observacao',
            'professor_id',
            'data_observacao',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class ProducaoCriancaSerializer(serializers.ModelSerializer):
    """Serializer para o model ProducaoCrianca."""

    class Meta:
        model = ProducaoCrianca
        fields = [
            'id',
            'crianca_id',
            'turma_id',
            'professor_id',
            'tipo',
            'titulo',
            'descricao',
            'arquivo_url',
            'projeto',
            'data_registro',
            'instituicao_id',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class ProjetoSerializer(serializers.ModelSerializer):
    """Serializer para o model Projeto."""

    class Meta:
        model = Projeto
        fields = [
            'id',
            'nome_projeto',
            'descricao',
            'data_inicio',
            'data_fim',
            'status',
            'instituicao_id',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class CalendarioBimestreSerializer(serializers.ModelSerializer):
    """Serializer para o model CalendarioBimestre."""

    class Meta:
        model = CalendarioBimestre
        fields = [
            'id',
            'ano',
            'bimestre',
            'data_inicio',
            'data_fim',
            'instituicao_id',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class PeriodoAvaliativoSerializer(serializers.ModelSerializer):
    """Serializer para o model PeriodoAvaliativo."""

    class Meta:
        model = PeriodoAvaliativo
        fields = [
            'id',
            'descricao',
            'tipo_periodo',
            'data_inicio',
            'data_fim',
            'instituicao_id',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class TurmaSerializer(serializers.ModelSerializer):
    """Serializer para o model Turma."""

    class Meta:
        model = Turma
        fields = [
            'id',
            'nome',
            'faixa_etaria',
            'turno',
            'ano_letivo',
            'instituicao_id',
            'ativa',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class ConfiguracaoRegistroSerializer(serializers.ModelSerializer):
    """Serializer para o model ConfiguracaoRegistro."""

    class Meta:
        model = ConfiguracaoRegistro
        fields = [
            'id',
            'turma_id',
            'frequencia_registro',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
        extra_kwargs = {
            # Permitir comportamento de upsert no endpoint de criação.
            'turma_id': {'validators': []},
        }

class InstituicaoSerializer(serializers.ModelSerializer):
    """Serializer para o model Instituicao."""

    logo_url = serializers.SerializerMethodField()

    class Meta:
        model = Instituicao
        fields = [
            'id',
            'nome',
            'cnpj',
            'email_institucional',
            'endereco',
            'cidade',
            'estado',
            'telefone',
            'logo_url',
            'tipo_relatorio',
            'report_settings',
            'ordem_relatorio',
            'ativa',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']

    def get_logo_url(self, obj):
        from api.storage import get_logo_url
        return get_logo_url(obj)
    
class UsuarioSerializer(serializers.ModelSerializer):
    """Serializer para o model Usuario."""
    instituicao_id = serializers.PrimaryKeyRelatedField(
        source='instituicao',
        queryset=Instituicao.objects.all(),
        required=False,
        allow_null=True,
    )
    usuario_turmas = serializers.SerializerMethodField()

    def get_usuario_turmas(self, obj):
        return [
            {'turma_id': str(vinculo.turma_id)}
            for vinculo in obj.turmas.all()
        ]

    class Meta:
        model = Usuario
        fields = [
            'id',
            'email',
            'nome',
            'perfil',
            'tipo_especialista',
            'instituicao_id',
            'ativo',
            'usuario_turmas',
            'created_at',
            'last_login',
        ]
        read_only_fields = ['id', 'created_at', 'last_login']


class UsuarioTurmaSerializer(serializers.ModelSerializer):
    """Serializer para o model UsuarioTurma."""
    usuario_id = serializers.UUIDField(source='usuario.id')
    turma_id = serializers.UUIDField(source='turma.id')
    turma = TurmaSerializer(read_only=True)

    class Meta:
        model = UsuarioTurma
        fields = ['usuario_id', 'turma_id', 'turma', 'data_vinculo']
        read_only_fields = ['data_vinculo']
        extra_kwargs = {'password': {'write_only': True}}


class MensagemCoordenacaoSerializer(serializers.ModelSerializer):
    """Serializer para o model MensagemCoordenacao."""

    class Meta:
        model = MensagemCoordenacao
        fields = [
            'id',
            'titulo',
            'conteudo',
            'remetente',
            'instituicao_id',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class MensagemLidaSerializer(serializers.ModelSerializer):
    """Serializer para o model MensagemLida."""
    mensagem_id = serializers.UUIDField(source='mensagem.id', read_only=True)

    class Meta:
        model = MensagemLida
        fields = [
            'id',
            'mensagem_id',
            'usuario_id',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class MensagemLidaCreateSerializer(serializers.Serializer):
    """Serializer para criar registro de mensagem lida."""
    mensagem_id = serializers.UUIDField()
    usuario_id = serializers.UUIDField()


class AlertaLidoSerializer(serializers.ModelSerializer):
    """Serializer para o model AlertaLido."""

    class Meta:
        model = AlertaLido
        fields = [
            'id',
            'usuario_id',
            'alerta_tipo',
            'alerta_chave',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']
        # Idempotência de (usuario_id, alerta_tipo, alerta_chave) é tratada na
        # view criar_alerta_lido — repetir o POST devolve 200 com o registro
        # existente. O UniqueTogetherValidator auto-gerado pelo ModelSerializer
        # transformaria isso em 400, então removemos os validators de Meta.
        validators = []


class PlanejamentoDiarioSerializer(serializers.ModelSerializer):
    """Serializer para o model PlanejamentoDiario (formato simplificado)."""
    # Campo 'atividades' para compatibilidade com frontend (mapeia atividades_propostas)
    atividades = serializers.CharField(source='atividades_propostas', read_only=True)
    arquivo_url = serializers.SerializerMethodField()

    class Meta:
        model = PlanejamentoDiario
        fields = [
            'id',
            'dia_semana',
            'data',
            'atividades_propostas',
            'atividades',  # Alias para compatibilidade
            'prompt_ia',
            'arquivo_storage_key',
            'arquivo_url',
            'arquivo_nome_original',
            'arquivo_content_type',
            'data_criacao',
            'data_modificacao',
        ]
        read_only_fields = ['id', 'data_criacao', 'data_modificacao', 'arquivo_url']

    def get_arquivo_url(self, obj):
        # Importação local para evitar circularidade ao importar settings antes
        # do app estar pronto.
        from .services.planejamento_ia import regenerar_url_arquivo

        return regenerar_url_arquivo(obj.arquivo_storage_key)


class PlanejamentoSemanalSerializer(serializers.ModelSerializer):
    """Serializer para o model PlanejamentoSemanal."""
    dias = PlanejamentoDiarioSerializer(many=True, read_only=True)
    # Campos para compatibilidade com frontend
    semana_referencia = serializers.DateField(source='semana_inicio', read_only=True)
    id_professor = serializers.CharField(source='professora_id', read_only=True)
    turmas = serializers.SerializerMethodField()
    usuarios = serializers.SerializerMethodField()

    class Meta:
        model = PlanejamentoSemanal
        fields = [
            'id',
            'turma_id',
            'semana_inicio',
            'semana_fim',
            'semana_referencia',  # Alias para compatibilidade
            'professora_id',
            'id_professor',  # Alias para compatibilidade
            'professora_nome',
            'ano_letivo',
            'dias',
            'turmas',  # Nome da turma nested
            'usuarios',  # Nome do professor nested
            'data_criacao',
            'data_modificacao',
        ]
        read_only_fields = ['id', 'data_criacao', 'data_modificacao']

    def get_turmas(self, obj):
        """Retorna dados da turma no formato esperado pelo frontend."""
        try:
            turma = Turma.objects.filter(id=obj.turma_id).first()
            if turma:
                return {'nome': turma.nome}
        except Exception:
            pass
        return {'nome': f'Turma {obj.turma_id}'}

    def get_usuarios(self, obj):
        """Retorna dados do professor no formato esperado pelo frontend."""
        return {'nome': obj.professora_nome}

class PromptTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model  = PromptTemplate
        fields = ['id', 'prompt_global', 'personalizado', 'categoria', 'cliente_id']


class PromptCategoriaSerializer(serializers.ModelSerializer):
    template = serializers.SerializerMethodField()

    class Meta:
        model  = PromptCategoria
        fields = ['id', 'titulo', 'ativo', 'template']

    def get_template(self, obj):
        cliente_id = self.context.get('cliente_id')

        # Busca o registro do cliente (sem excluir por personalizado vazio —
        # cada categoria tem uma única linha contendo tanto prompt_global
        # quanto personalizado, então o registro do cliente é sempre o que
        # deve ser retornado quando existir, mesmo que personalizado
        # esteja vazio).
        template = None
        if cliente_id:
            template = (
                obj.templates
                .filter(cliente_id=cliente_id)
                .order_by('-id')
                .first()
            )
        if template is None:
            template = (
                obj.templates
                .filter(cliente_id__isnull=True)
                .order_by('-id')
                .first()
            )

        return PromptTemplateSerializer(template).data if template else None

class DisciplinaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Disciplina
        fields = ['id', 'instituicao', 'nome', 'ativo', 'created_at']
        read_only_fields = ['id', 'created_at']


class UsuarioDisciplinaSerializer(serializers.ModelSerializer):
    disciplina_nome = serializers.CharField(source='disciplina.nome', read_only=True)

    class Meta:
        model = UsuarioDisciplina
        fields = ['id', 'usuario', 'disciplina', 'disciplina_nome', 'instituicao', 'created_at']
        read_only_fields = ['id', 'created_at']

    def validate(self, data):
        usuario = data.get('usuario') or getattr(self.instance, 'usuario', None)
        disciplina = data.get('disciplina') or getattr(self.instance, 'disciplina', None)
        if usuario and usuario.perfil != 'professor_fundamental':
            raise serializers.ValidationError(
                'Apenas usuários com perfil professor_fundamental podem ser vinculados a disciplinas.'
            )
        if usuario and disciplina and usuario.instituicao_id != disciplina.instituicao_id:
            raise serializers.ValidationError(
                'Usuário e disciplina devem pertencer à mesma instituição.'
            )
        return data