"""
Serializers para a API REST do multi-nara.
Provê conversão entre models Django e JSON para endpoints RESTful.
"""

from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import Usuario, Instituicao, Escola, Especialista, Turma


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