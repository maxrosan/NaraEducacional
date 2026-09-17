"""
Serializers para a API REST do multi-nara.
Provê conversão entre models Django e JSON para endpoints RESTful.
"""

from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import (
    Usuario, Instituicao, Escola, Especialista, Turma, UsuarioTurma,
    Disciplina, UsuarioDisciplina, Aluno, Projeto, Producao, ProducaoAluno,
)


class TurmaSerializer(serializers.ModelSerializer):
    escola_nome = serializers.CharField(source='escola.nome', read_only=True)

    class Meta:
        model = Turma
        fields = [
            'id', 'nome', 'faixa_etaria', 'turno', 'ano_letivo', 'ativa',
            'etapa', 'ordem', 'idade_min', 'idade_max',
            'escola', 'escola_nome', 'instituicao',
            'criado_em', 'atualizado_em',
        ]
        read_only_fields = ['id', 'escola', 'instituicao', 'criado_em', 'atualizado_em']


class UsuarioTurmaSerializer(serializers.ModelSerializer):
    usuario_nome = serializers.CharField(source='usuario.nome', read_only=True)
    usuario_email = serializers.CharField(source='usuario.email', read_only=True)
    usuario_nivel = serializers.CharField(source='usuario.nivel', read_only=True)

    class Meta:
        model = UsuarioTurma
        fields = [
            'id', 'usuario', 'usuario_nome', 'usuario_email', 'usuario_nivel',
            'turma', 'data_vinculo', 'criado_em',
        ]
        read_only_fields = ['id', 'turma', 'criado_em']


class DisciplinaSerializer(serializers.ModelSerializer):
    escola_nome = serializers.CharField(source='escola.nome', read_only=True)

    class Meta:
        model = Disciplina
        fields = ['id', 'nome', 'ativo', 'escola', 'escola_nome', 'instituicao', 'criado_em']
        read_only_fields = ['id', 'escola', 'instituicao', 'criado_em']


class UsuarioDisciplinaSerializer(serializers.ModelSerializer):
    usuario_nome = serializers.CharField(source='usuario.nome', read_only=True)
    disciplina_nome = serializers.CharField(source='disciplina.nome', read_only=True)

    class Meta:
        model = UsuarioDisciplina
        fields = [
            'id', 'usuario', 'usuario_nome', 'disciplina', 'disciplina_nome',
            'escola', 'instituicao', 'criado_em', 'atualizado_em',
        ]
        read_only_fields = ['id', 'escola', 'instituicao', 'criado_em', 'atualizado_em']


class InstituicaoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Instituicao
        fields = [
            'id', 'nome', 'cnpj', 'email_institucional', 'endereco',
            'cidade', 'estado', 'telefone', 'logo_url', 'ativa',
            'criado_em', 'atualizado_em',
        ]
        read_only_fields = ['id', 'criado_em', 'atualizado_em']


class EscolaSerializer(serializers.ModelSerializer):
    instituicao_nome = serializers.CharField(source='instituicao.nome', read_only=True)

    class Meta:
        model = Escola
        fields = [
            'id', 'instituicao', 'instituicao_nome', 'nome', 'tipo_unidade',
            'cnpj', 'endereco', 'cidade', 'estado', 'telefone', 'ativa',
            'tipo_relatorio', 'report_settings', 'ordem_relatorio',
            'criado_em', 'atualizado_em',
        ]
        read_only_fields = ['id', 'instituicao', 'criado_em', 'atualizado_em']


class EspecialistaSerializer(serializers.ModelSerializer):
    escola_nome = serializers.CharField(source='escola.nome', read_only=True, default=None)
    instituicao_nome = serializers.CharField(source='instituicao.nome', read_only=True)

    class Meta:
        model = Especialista
        fields = [
            'id', 'tipo_especialista', 'escola', 'escola_nome',
            'instituicao', 'instituicao_nome', 'criado_em', 'atualizado_em',
        ]
        read_only_fields = ['id', 'instituicao', 'criado_em', 'atualizado_em']

    def validate_escola(self, escola):
        instituicao_id = self.context.get('instituicao_id')
        if escola is not None and instituicao_id and str(escola.instituicao_id) != str(instituicao_id):
            raise serializers.ValidationError('A escola informada não pertence à instituição do usuário.')
        return escola


class UsuarioSerializer(serializers.ModelSerializer):
    """Serializer para o model Usuario (leitura — usado no payload de login e em /me/)."""

    escola_nome = serializers.CharField(source='escola.nome', read_only=True, default=None)
    instituicao_nome = serializers.CharField(source='instituicao.nome', read_only=True, default=None)

    class Meta:
        model = Usuario
        fields = [
            'id', 'nome', 'email', 'numero', 'nivel',
            'escola', 'escola_nome', 'instituicao', 'instituicao_nome',
            'especialista', 'is_active',
        ]
        read_only_fields = fields


class UsuarioWriteSerializer(serializers.ModelSerializer):
    """Serializer de escrita para Usuario — lida com hash de senha via set_password."""

    password = serializers.CharField(write_only=True, required=False, min_length=8)

    class Meta:
        model = Usuario
        fields = [
            'id', 'nome', 'email', 'numero', 'nivel',
            'escola', 'instituicao', 'especialista', 'is_active', 'password',
        ]
        read_only_fields = ['id']

    def create(self, validated_data):
        password = validated_data.pop('password', None)
        if not password:
            raise serializers.ValidationError({'password': 'Senha é obrigatória na criação.'})
        usuario = Usuario(**validated_data)
        usuario.set_password(password)
        usuario.save()
        return usuario

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance


class AlunoSerializer(serializers.ModelSerializer):
    turma_nome = serializers.CharField(source='turma.nome', read_only=True)
    escola_nome = serializers.CharField(source='escola.nome', read_only=True)

    class Meta:
        model = Aluno
        fields = [
            'id', 'nome_completo', 'data_nascimento', 'genero',
            'nome_responsavel', 'telefone_responsavel', 'status_vinculo',
            'observacoes', 'foto_url', 'turma', 'turma_nome',
            'escola', 'escola_nome', 'instituicao',
            'criado_em', 'atualizado_em',
        ]
        read_only_fields = ['id', 'escola', 'instituicao', 'criado_em', 'atualizado_em']


class ProjetoSerializer(serializers.ModelSerializer):
    escola_nome = serializers.CharField(source='escola.nome', read_only=True)

    class Meta:
        model = Projeto
        fields = [
            'id', 'nome', 'descricao', 'status', 'data_inicio', 'data_fim',
            'escola', 'escola_nome', 'instituicao', 'criado_em', 'atualizado_em',
        ]
        read_only_fields = ['id', 'escola', 'instituicao', 'criado_em', 'atualizado_em']


class ProducaoSerializer(serializers.ModelSerializer):
    professor_nome = serializers.CharField(source='professor.nome', read_only=True)
    turma_nome = serializers.CharField(source='turma.nome', read_only=True)

    class Meta:
        model = Producao
        fields = [
            'id', 'tipo', 'titulo', 'descricao', 'arquivo_url', 'arquivo_nome',
            'arquivo_hash', 'mime_type', 'tamanho_bytes', 'tags', 'data_registro',
            'turma', 'turma_nome', 'professor', 'professor_nome', 'projeto',
            'escola', 'instituicao', 'criado_em', 'atualizado_em',
        ]
        read_only_fields = [
            'id', 'professor', 'escola', 'instituicao', 'criado_em', 'atualizado_em',
        ]


class ProducaoAlunoSerializer(serializers.ModelSerializer):
    aluno_nome = serializers.CharField(source='aluno.nome_completo', read_only=True)

    class Meta:
        model = ProducaoAluno
        fields = [
            'id', 'legenda', 'legenda_ia', 'destaque', 'incluir_relatorio',
            'producao', 'aluno', 'aluno_nome', 'criado_em', 'atualizado_em',
        ]
        read_only_fields = ['id', 'producao', 'criado_em', 'atualizado_em']


class LoginSerializer(TokenObtainPairSerializer):
    """
    Login customizado: além do access/refresh token padrão do SimpleJWT,
    devolve os dados do usuário logado — o frontend não precisa fazer uma
    segunda chamada só pra saber nivel/escola/instituicao.
    """

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['nivel'] = user.nivel
        token['escola_id'] = str(user.escola_id) if user.escola_id else None
        token['instituicao_id'] = str(user.instituicao_id) if user.instituicao_id else None
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        data['usuario'] = UsuarioSerializer(self.user).data
        return data