"""
Serializers para a API REST do multi-nara.
Provê conversão entre models Django e JSON para endpoints RESTful.
"""

from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .escopo import validar_professores_turma

from .models import (
    Usuario, Instituicao, Escola, Especialista, Turma, UsuarioTurma,
    Disciplina, UsuarioDisciplina, Aluno, Projeto, Producao, ProducaoAluno,
    RegistroEscrita, RegistroDesenho, RegistroLeitura,
    CampoPedagogico, HabilidadeBNCC, Pergunta, PerguntaEspecialista,
    RegistroObservacao, ObservacaoTranscricao,
    PlanejamentoSemanal,
    PeriodoAvaliativo, RelatorioTemplate, Relatorio,
    Notificacao, MetaPAEE, SessaoEspecialista, SessaoPAEEMeta, TarefaPAEE,
    Ticket, RespostaTicket, AnexoTicket, LogAuditoria, PermissaoUsuario,
    TemplateDocumento, Contrato, PromptCategoria, PromptTemplate,
)


def _sincronizar_professores(turma, usuarios):
    """Deixa a turma vinculada exatamente a `usuarios` (remove e cria o que mudou)."""
    desejados = {u.id for u in usuarios}
    vinculos = UsuarioTurma.objects.filter(turma=turma)
    atuais = set(vinculos.values_list('usuario_id', flat=True))
    vinculos.exclude(usuario_id__in=desejados).delete()
    UsuarioTurma.objects.bulk_create(
        [UsuarioTurma(turma=turma, usuario=u) for u in usuarios if u.id not in atuais]
    )


class TurmaSerializer(serializers.ModelSerializer):
    """
    Cadastro de turma.

    Criação: a view passa `context={'escola_id': ...}` (vinda do
    resolver_escopo_criacao), porque `escola` é read_only aqui e as checagens
    de nome duplicado e de professores dependem dela.

    `professores` (opcional, só escrita): lista de ids de usuários. Quando
    enviada, os vínculos da turma passam a ser exatamente essa lista. A view
    salva dentro de transaction.atomic(): turma e vínculos gravam juntos.
    """
    escola_nome = serializers.CharField(source='escola.nome', read_only=True)
    professores = serializers.ListField(
        child=serializers.UUIDField(), write_only=True, required=False,
    )

    class Meta:
        model = Turma
        fields = [
            'id', 'nome', 'faixa_etaria', 'turno', 'ano_letivo', 'ativa',
            'etapa', 'ordem', 'idade_min', 'idade_max',
            'escola', 'escola_nome', 'instituicao', 'professores',
            'criado_em', 'atualizado_em',
        ]
        read_only_fields = ['id', 'escola', 'instituicao', 'criado_em', 'atualizado_em']
        extra_kwargs = {
            'idade_min': {'min_value': 0, 'max_value': 18},
            'idade_max': {'min_value': 0, 'max_value': 18},
            'ordem': {'min_value': 0},
        }

    def _escola_id(self):
        if self.instance is not None:
            return self.instance.escola_id
        return self.context.get('escola_id')

    def _valor(self, attrs, campo):
        """Valor final do campo: o enviado ou, no PATCH, o que já está salvo."""
        if campo in attrs:
            return attrs[campo]
        if self.instance is not None:
            return getattr(self.instance, campo)
        return Turma._meta.get_field(campo).get_default()

    def validate_ano_letivo(self, valor):
        valor = str(valor).strip()
        if not (valor.isdigit() and len(valor) == 4 and 2000 <= int(valor) <= 2100):
            raise serializers.ValidationError('Informe um ano letivo entre 2000 e 2100.')
        return valor

    def validate(self, attrs):
        idade_min = self._valor(attrs, 'idade_min')
        idade_max = self._valor(attrs, 'idade_max')
        if idade_min is not None and idade_max is not None and idade_min > idade_max:
            raise serializers.ValidationError(
                {'idade_max': ['A idade máxima não pode ser menor que a mínima.']}
            )

        escola_id = self._escola_id()
        if escola_id and self._mudou_nome_ou_ano(attrs):
            self._checar_nome_duplicado(escola_id, attrs)

        if 'professores' in attrs:
            attrs['professores'] = self._validar_professores(escola_id, attrs['professores'])
        return attrs

    def _mudou_nome_ou_ano(self, attrs):
        """Na edição, só checa duplicidade se nome ou ano mudaram de fato.

        O formulário sempre reenvia o nome; sem isso, uma turma que já estava
        duplicada antes desta regra não poderia mais ser editada (nem para
        trocar o turno) até alguém renomeá-la.
        """
        if self.instance is None:
            return True
        nome = self._valor(attrs, 'nome')
        return (
            nome.casefold() != (self.instance.nome or '').casefold()
            or self._valor(attrs, 'ano_letivo') != self.instance.ano_letivo
        )

    def _checar_nome_duplicado(self, escola_id, attrs):
        nome = self._valor(attrs, 'nome')
        ano = self._valor(attrs, 'ano_letivo')
        # Sem constraint no banco: esta checagem é a regra. A view trava a linha
        # da escola durante validação + save para não haver corrida.
        # _base_manager: sem recorte de tenant; o filtro por escola já delimita.
        existentes = Turma._base_manager.filter(
            escola_id=escola_id, ano_letivo=ano, nome__iexact=nome,
        )
        if self.instance is not None:
            existentes = existentes.exclude(pk=self.instance.pk)
        existente = existentes.first()
        if existente is None:
            return
        mensagem = f'Já existe a turma "{existente.nome}" nesta escola em {ano}.'
        if not existente.ativa:
            mensagem += ' Ela está desativada: reative-a na aba Inativas.'
        raise serializers.ValidationError({'nome': [mensagem]})

    def _validar_professores(self, escola_id, ids):
        if escola_id is None:
            raise serializers.ValidationError({'professores': ['Escola da turma não definida.']})
        ja_vinculados = []
        if self.instance is not None:
            ja_vinculados = UsuarioTurma.objects.filter(turma=self.instance).values_list('usuario_id', flat=True)
        usuarios, erro = validar_professores_turma(escola_id, ids, ja_vinculados)
        if erro:
            raise serializers.ValidationError({'professores': [erro]})
        return usuarios

    def create(self, validated_data):
        professores = validated_data.pop('professores', None)
        turma = super().create(validated_data)
        if professores is not None:
            _sincronizar_professores(turma, professores)
        return turma

    def update(self, instance, validated_data):
        professores = validated_data.pop('professores', None)
        turma = super().update(instance, validated_data)
        if professores is not None:
            _sincronizar_professores(turma, professores)
        return turma


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


class ProfessorDaTurmaSerializer(serializers.ModelSerializer):
    """Vínculo resumido para a listagem (mesmas chaves do UsuarioTurmaSerializer)."""
    usuario_nome = serializers.CharField(source='usuario.nome', read_only=True)
    usuario_nivel = serializers.CharField(source='usuario.nivel', read_only=True)

    class Meta:
        model = UsuarioTurma
        fields = ['usuario', 'usuario_nome', 'usuario_nivel']


class TurmaListaSerializer(serializers.ModelSerializer):
    """
    Linha da listagem paginada de turmas (só leitura).

    Traz os professores junto para a tela não fazer uma chamada a
    /turmas/<id>/professores/ por turma. Depende da view fazer
    select_related('escola') e o Prefetch em `professores_listagem`
    (ver views/turma.py::listar_turmas); sem isso volta o N+1.
    """
    escola_nome = serializers.CharField(source='escola.nome', read_only=True)
    professores = ProfessorDaTurmaSerializer(source='professores_listagem', many=True, read_only=True)

    class Meta:
        model = Turma
        fields = [
            'id', 'nome', 'faixa_etaria', 'turno', 'ano_letivo', 'ativa',
            'etapa', 'ordem', 'idade_min', 'idade_max',
            'escola', 'escola_nome', 'professores',
        ]
        read_only_fields = fields


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
            'id', 'professor', 'turma', 'escola', 'instituicao', 'criado_em', 'atualizado_em',
        ]


class ProducaoAlunoSerializer(serializers.ModelSerializer):
    aluno_nome = serializers.CharField(source='aluno.nome_completo', read_only=True)

    class Meta:
        model = ProducaoAluno
        fields = [
            'id', 'legenda', 'legenda_ia', 'destaque', 'incluir_relatorio',
            'producao', 'aluno', 'aluno_nome', 'criado_em', 'atualizado_em',
        ]
        read_only_fields = ['id', 'producao', 'aluno', 'criado_em', 'atualizado_em']


class RegistroEscritaSerializer(serializers.ModelSerializer):
    aluno_nome = serializers.CharField(source='aluno.nome_completo', read_only=True)
    professor_nome = serializers.CharField(source='professor.nome', read_only=True)

    class Meta:
        model = RegistroEscrita
        fields = [
            'id', 'etapa', 'arquivo_nome', 'arquivo_hash', 'arquivo_path',
            'arquivo_original', 'tamanho_arquivo', 'tipo_arquivo', 'etapa_ia',
            'analise_detalhada', 'anotacoes_professora',
            'aluno', 'aluno_nome', 'turma', 'professor', 'professor_nome',
            'escola', 'instituicao', 'criado_em', 'atualizado_em',
        ]
        read_only_fields = [
            'id', 'aluno', 'turma', 'professor', 'escola', 'instituicao', 'criado_em', 'atualizado_em',
            'arquivo_nome', 'arquivo_hash', 'arquivo_path', 'arquivo_original', 'tamanho_arquivo', 'tipo_arquivo',
        ]


class RegistroDesenhoSerializer(serializers.ModelSerializer):
    aluno_nome = serializers.CharField(source='aluno.nome_completo', read_only=True)
    professor_nome = serializers.CharField(source='professor.nome', read_only=True)

    class Meta:
        model = RegistroDesenho
        fields = [
            'id', 'etapa', 'atividade', 'contexto', 'fase_desenho',
            'elementos_detectados', 'analise_detalhada', 'anotacoes_professora',
            'arquivo_nome', 'arquivo_hash', 'arquivo_path', 'arquivo_original',
            'tamanho_arquivo', 'tipo_arquivo',
            'aluno', 'aluno_nome', 'turma', 'professor', 'professor_nome',
            'escola', 'instituicao', 'criado_em', 'atualizado_em',
        ]
        read_only_fields = [
            'id', 'aluno', 'turma', 'professor', 'escola', 'instituicao', 'criado_em', 'atualizado_em',
            'arquivo_nome', 'arquivo_hash', 'arquivo_path', 'arquivo_original', 'tamanho_arquivo', 'tipo_arquivo',
        ]


class RegistroLeituraSerializer(serializers.ModelSerializer):
    aluno_nome = serializers.CharField(source='aluno.nome_completo', read_only=True)
    professor_nome = serializers.CharField(source='professor.nome', read_only=True)

    class Meta:
        model = RegistroLeitura
        fields = [
            'id', 'nara_job_id', 'status', 'arquivo_path', 'arquivo_nome',
            'arquivo_hash', 'tamanho_arquivo', 'tipo_arquivo', 'duracao_seg',
            'pieces', 'feat_dim', 'classe_predita', 'classe_escolhida',
            'probabilidades', 'anotacoes_professora',
            'aluno', 'aluno_nome', 'turma', 'professor', 'professor_nome',
            'escola', 'instituicao', 'criado_em', 'atualizado_em',
        ]
        read_only_fields = [
            'id', 'turma', 'professor', 'escola', 'instituicao', 'criado_em', 'atualizado_em',
        ]


class CampoPedagogicoSerializer(serializers.ModelSerializer):
    escola_nome = serializers.CharField(source='escola.nome', read_only=True, default=None)

    class Meta:
        model = CampoPedagogico
        fields = [
            'id', 'nome', 'etapa', 'icone', 'cor', 'ativo',
            'escola', 'escola_nome', 'instituicao', 'criado_em', 'atualizado_em',
        ]
        read_only_fields = ['id', 'criado_em', 'atualizado_em', 'escola', 'instituicao']


class HabilidadeBNCCSerializer(serializers.ModelSerializer):
    class Meta:
        model = HabilidadeBNCC
        fields = [
            'id', 'codigo', 'descricao', 'componente_curricular', 'ano_serie',
            'campo_atuacao', 'ativa', 'criado_em', 'atualizado_em',
        ]
        read_only_fields = ['id', 'criado_em', 'atualizado_em']


class PerguntaSerializer(serializers.ModelSerializer):
    escola_nome = serializers.CharField(source='escola.nome', read_only=True, default=None)
    # `todos`: o TenantManager esconderia os campos oficiais (escola nula).
    # O recorte oficial + escola da pergunta é feito na view (_campo_invalido).
    campo_experiencia = serializers.PrimaryKeyRelatedField(
        queryset=CampoPedagogico.todos.all(), required=False, allow_null=True,
    )

    class Meta:
        model = Pergunta
        fields = [
            'id', 'pergunta', 'pergunta_norma', 'area_conhecimento', 'origem', 'ativa',
            'faixa_etaria', 'campo_experiencia', 'habilidade_bncc',
            'escola', 'escola_nome', 'instituicao', 'criado_em', 'atualizado_em',
        ]
        read_only_fields = ['id', 'criado_em', 'atualizado_em', 'escola', 'instituicao']


class PerguntaEspecialistaSerializer(serializers.ModelSerializer):
    usuario_especialista_nome = serializers.CharField(source='usuario_especialista.nome', read_only=True)
    # `todos`: o TenantManager esconderia os campos oficiais (escola nula).
    # O recorte oficial + escola da pergunta é feito na view (_campo_invalido).
    campo_experiencia = serializers.PrimaryKeyRelatedField(
        queryset=CampoPedagogico.todos.all(), required=False, allow_null=True,
    )

    class Meta:
        model = PerguntaEspecialista
        fields = [
            'id', 'pergunta', 'pergunta_facilitadora', 'nivel', 'status',
            'campo_experiencia', 'habilidade_bncc',
            'usuario_especialista', 'usuario_especialista_nome',
            'escola', 'instituicao', 'criado_em', 'atualizado_em',
        ]
        read_only_fields = [
            'id', 'usuario_especialista', 'escola', 'instituicao', 'criado_em', 'atualizado_em',
        ]


class RegistroObservacaoSerializer(serializers.ModelSerializer):
    aluno_nome = serializers.CharField(source='aluno.nome_completo', read_only=True)
    # `todos`: o TenantManager esconderia as perguntas oficiais (escola nula).
    # O recorte oficial + escola do aluno é feito na view (_pergunta_invalida).
    pergunta = serializers.PrimaryKeyRelatedField(
        queryset=Pergunta.todos.all(), required=False, allow_null=True,
    )

    class Meta:
        model = RegistroObservacao
        fields = [
            'id', 'resposta', 'observacao', 'data_observacao',
            'pergunta', 'pergunta_especialista',
            'aluno', 'aluno_nome', 'professor', 'escola', 'instituicao',
            'criado_em', 'atualizado_em',
        ]
        read_only_fields = ['id', 'aluno', 'professor', 'escola', 'instituicao', 'criado_em', 'atualizado_em']

    def validate(self, attrs):
        pergunta = attrs.get('pergunta', getattr(self.instance, 'pergunta', None))
        pergunta_especialista = attrs.get('pergunta_especialista', getattr(self.instance, 'pergunta_especialista', None))
        if bool(pergunta) == bool(pergunta_especialista):
            raise serializers.ValidationError(
                'Preencha exatamente um dos dois: pergunta OU pergunta_especialista (não os dois, não nenhum).'
            )
        return attrs


class ObservacaoTranscricaoSerializer(serializers.ModelSerializer):
    aluno_nome_vinculado = serializers.CharField(source='aluno.nome_completo', read_only=True, default=None)

    class Meta:
        model = ObservacaoTranscricao
        fields = [
            'id', 'aluno_nome', 'observacao_texto', 'tipo_observacao', 'data_observacao',
            'transcricao_completa', 'metadados_ia',
            'aluno', 'aluno_nome_vinculado', 'turma', 'professor',
            'escola', 'instituicao', 'criado_em', 'atualizado_em',
        ]
        read_only_fields = ['id', 'turma', 'professor', 'escola', 'instituicao', 'criado_em', 'atualizado_em']


class PlanejamentoSemanalSerializer(serializers.ModelSerializer):
    turma_nome = serializers.CharField(source='turma.nome', read_only=True)
    professor_nome = serializers.CharField(source='professor.nome', read_only=True)

    class Meta:
        model = PlanejamentoSemanal
        fields = [
            'id', 'semana_inicio', 'semana_fim', 'ano_letivo',
            'turma', 'turma_nome', 'professor', 'professor_nome',
            'escola', 'instituicao', 'criado_em', 'atualizado_em',
        ]
        read_only_fields = [
            'id', 'turma', 'professor', 'escola', 'instituicao', 'criado_em', 'atualizado_em',
        ]


class PeriodoAvaliativoSerializer(serializers.ModelSerializer):
    class Meta:
        model = PeriodoAvaliativo
        fields = [
            'id', 'descricao', 'tipo_periodo', 'ano', 'numero',
            'data_inicio', 'data_fim', 'escola', 'instituicao', 'criado_em', 'atualizado_em',
        ]
        read_only_fields = ['id', 'escola', 'instituicao', 'criado_em', 'atualizado_em']


class RelatorioTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = RelatorioTemplate
        fields = [
            'id', 'nome', 'modelo', 'usa_foto_aluno', 'config', 'items_sumario',
            'ativo', 'escola', 'instituicao', 'criado_em', 'atualizado_em',
        ]
        read_only_fields = ['id', 'escola', 'instituicao', 'criado_em', 'atualizado_em']


class RelatorioSerializer(serializers.ModelSerializer):
    aluno_nome = serializers.CharField(source='aluno.nome_completo', read_only=True)
    revisado_por_nome = serializers.CharField(source='revisado_por.nome', read_only=True, default=None)

    class Meta:
        model = Relatorio
        fields = [
            'id', 'conteudo', 'pdf_url', 'periodo',
            'aluno', 'aluno_nome', 'template',
            'revisado_por', 'revisado_por_nome',
            'escola', 'instituicao', 'criado_em', 'atualizado_em',
        ]
        read_only_fields = [
            'id', 'aluno', 'pdf_url', 'revisado_por', 'escola', 'instituicao', 'criado_em', 'atualizado_em',
        ]


class NotificacaoSerializer(serializers.ModelSerializer):
    remetente_nome = serializers.CharField(source='remetente.nome', read_only=True, default=None)

    class Meta:
        model = Notificacao
        fields = [
            'id', 'tipo', 'titulo', 'conteudo', 'lido_em',
            'remetente', 'remetente_nome', 'usuario', 'escola', 'instituicao',
            'criado_em', 'atualizado_em',
        ]
        read_only_fields = [
            'id', 'remetente', 'usuario', 'escola', 'instituicao', 'criado_em', 'atualizado_em',
        ]


class MetaPAEESerializer(serializers.ModelSerializer):
    aluno_nome = serializers.CharField(source='aluno.nome_completo', read_only=True)
    usuario_especialista_nome = serializers.CharField(source='usuario_especialista.nome', read_only=True)

    class Meta:
        model = MetaPAEE
        fields = [
            'id', 'categoria', 'inicio', 'fim', 'objetivo', 'criterio', 'estrategia', 'status',
            'aluno', 'aluno_nome', 'usuario_especialista', 'usuario_especialista_nome', 'turma',
            'escola', 'instituicao', 'criado_em', 'atualizado_em',
        ]
        read_only_fields = [
            'id', 'aluno', 'usuario_especialista', 'turma', 'escola', 'instituicao', 'criado_em', 'atualizado_em',
        ]


class SessaoEspecialistaSerializer(serializers.ModelSerializer):
    aluno_nome = serializers.CharField(source='aluno.nome_completo', read_only=True)
    usuario_especialista_nome = serializers.CharField(source='usuario_especialista.nome', read_only=True)

    class Meta:
        model = SessaoEspecialista
        fields = [
            'id', 'data_atendimento', 'duracao', 'resumo', 'status',
            'aluno', 'aluno_nome', 'usuario_especialista', 'usuario_especialista_nome', 'turma',
            'escola', 'instituicao', 'criado_em', 'atualizado_em',
        ]
        read_only_fields = [
            'id', 'aluno', 'usuario_especialista', 'turma', 'escola', 'instituicao', 'criado_em', 'atualizado_em',
        ]


class SessaoPAEEMetaSerializer(serializers.ModelSerializer):
    meta_paee_objetivo = serializers.CharField(source='meta_paee.objetivo', read_only=True)

    class Meta:
        model = SessaoPAEEMeta
        fields = ['id', 'sessao_especialista', 'meta_paee', 'meta_paee_objetivo', 'criado_em']
        read_only_fields = ['id', 'sessao_especialista', 'criado_em']


class TarefaPAEESerializer(serializers.ModelSerializer):
    professor_conclusao_nome = serializers.CharField(source='professor_conclusao.nome', read_only=True, default=None)

    class Meta:
        model = TarefaPAEE
        fields = [
            'id', 'descricao', 'concluida', 'observacao_professor', 'data_conclusao',
            'meta_paee', 'professor_conclusao', 'professor_conclusao_nome',
            'escola', 'instituicao', 'criado_em', 'atualizado_em',
        ]
        read_only_fields = [
            'id', 'meta_paee', 'professor_conclusao', 'escola', 'instituicao', 'criado_em', 'atualizado_em',
        ]


class AnexoTicketSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnexoTicket
        fields = ['id', 'arquivo_url', 'arquivo_nome', 'mime_type', 'tamanho_bytes',
                  'ticket', 'ticket_reply', 'criado_em']
        read_only_fields = ['id', 'ticket', 'ticket_reply', 'criado_em']


class RespostaTicketSerializer(serializers.ModelSerializer):
    usuario_nome = serializers.CharField(source='usuario.nome', read_only=True)
    anexos = AnexoTicketSerializer(many=True, read_only=True)

    class Meta:
        model = RespostaTicket
        fields = ['id', 'descricao', 'usuario', 'usuario_nome', 'ticket', 'anexos', 'criado_em', 'atualizado_em']
        read_only_fields = ['id', 'usuario', 'ticket', 'criado_em', 'atualizado_em']


class TicketSerializer(serializers.ModelSerializer):
    usuario_solicitante_nome = serializers.CharField(source='usuario_solicitante.nome', read_only=True)
    responsavel_nome = serializers.CharField(source='responsavel.nome', read_only=True, default=None)

    class Meta:
        model = Ticket
        fields = [
            'id', 'protocolo', 'titulo', 'descricao', 'status', 'categoria', 'prioridade',
            'usuario_solicitante', 'usuario_solicitante_nome', 'escola', 'instituicao',
            'responsavel', 'responsavel_nome', 'criado_em', 'atualizado_em',
        ]
        read_only_fields = [
            'id', 'protocolo', 'usuario_solicitante', 'escola', 'instituicao', 'criado_em', 'atualizado_em',
        ]


class LogAuditoriaSerializer(serializers.ModelSerializer):
    usuario_nome = serializers.CharField(source='usuario.nome', read_only=True, default=None)

    class Meta:
        model = LogAuditoria
        fields = [
            'id', 'acao', 'tabela_afetada', 'registro_id', 'alteracoes', 'ip',
            'usuario', 'usuario_nome', 'escola', 'instituicao', 'criado_em',
        ]
        read_only_fields = fields


class PermissaoUsuarioSerializer(serializers.ModelSerializer):
    usuario_nome = serializers.CharField(source='usuario.nome', read_only=True)
    concedido_por_nome = serializers.CharField(source='concedido_por.nome', read_only=True, default=None)

    class Meta:
        model = PermissaoUsuario
        fields = [
            'id', 'modulo', 'acao', 'concedido', 'usuario', 'usuario_nome',
            'escola', 'instituicao', 'concedido_por', 'concedido_por_nome',
            'criado_em', 'atualizado_em',
        ]
        read_only_fields = [
            'id', 'escola', 'instituicao', 'concedido_por', 'criado_em', 'atualizado_em',
        ]


class TemplateDocumentoSerializer(serializers.ModelSerializer):
    class Meta:
        model = TemplateDocumento
        fields = [
            'id', 'titulo', 'documento', 'tipo', 'ativo',
            'responsavel', 'criado_por', 'atualizado_por',
            'escola', 'instituicao', 'criado_em', 'atualizado_em',
        ]
        read_only_fields = ['id', 'criado_por', 'atualizado_por', 'criado_em', 'atualizado_em', 'escola', 'instituicao']


class ContratoSerializer(serializers.ModelSerializer):
    escola_nome = serializers.CharField(source='escola.nome', read_only=True)

    class Meta:
        model = Contrato
        fields = [
            'id', 'documento', 'status', 'arquivo_url', 'template',
            'escola', 'escola_nome', 'instituicao',
            'responsavel', 'gerado_por', 'atualizado_por',
            'criado_em', 'atualizado_em',
        ]
        read_only_fields = [
            'id', 'gerado_por', 'atualizado_por', 'escola', 'instituicao', 'criado_em', 'atualizado_em',
        ]


class PromptTemplateSerializer(serializers.ModelSerializer):
    instituicao_nome = serializers.CharField(source='instituicao.nome', read_only=True, default=None)

    class Meta:
        model = PromptTemplate
        fields = [
            'id', 'categoria', 'prompt_global', 'personalizado',
            'escola', 'instituicao', 'instituicao_nome', 'criado_em', 'atualizado_em',
        ]
        read_only_fields = ['id', 'categoria', 'criado_em', 'atualizado_em', 'escola', 'instituicao']


class PromptCategoriaSerializer(serializers.ModelSerializer):
    """
    `template_resolvido` usa o `escola_id` do contexto (a escola escolhida
    na tela) pra mostrar qual texto está valendo de fato para ela agora — o
    mesmo critério de `resolver_prompt` (personalizado da escola > global >
    vazio), sem o fallback pra arquivo .txt, que não faz sentido nessa tela.
    """
    template_resolvido = serializers.SerializerMethodField()

    class Meta:
        model = PromptCategoria
        fields = ['id', 'titulo', 'ativo', 'template_resolvido', 'criado_em', 'atualizado_em']
        read_only_fields = ['id', 'criado_em', 'atualizado_em']

    def get_template_resolvido(self, categoria):
        escola_id = self.context.get('escola_id')
        templates = list(categoria.templates.all())

        if escola_id:
            personalizado = next(
                (t for t in templates if str(t.escola_id) == str(escola_id)), None,
            )
            if personalizado and personalizado.personalizado.strip():
                return {'origem': 'personalizado', 'texto': personalizado.personalizado}

        global_tpl = next((t for t in templates if t.escola_id is None and t.instituicao_id is None), None)
        if global_tpl and global_tpl.prompt_global.strip():
            return {'origem': 'global', 'texto': global_tpl.prompt_global}

        return {'origem': 'vazio', 'texto': ''}


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