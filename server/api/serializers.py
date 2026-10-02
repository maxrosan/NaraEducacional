"""
Serializers para a API REST do multi-nara.
Provê conversão entre models Django e JSON para endpoints RESTful.
"""

from django.utils import timezone
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .escopo import validar_professores_disciplina, validar_professores_turma

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


def _mesmo_nome(a, b):
    """Compara nomes sem diferenciar maiúsculas, inclusive acentuadas.

    Feito no Python (casefold) e não com `__iexact`: no Postgres o iexact vira
    UPPER(), que depende do locale do banco; no locale "C" o UPPER não converte
    letras acentuadas ('Á' ≠ UPPER('á')). As queries que chamam isto já filtram
    por escola (e ano/nascimento), então sobram poucos registros.
    """
    return (a or '').strip().casefold() == (b or '').strip().casefold()


def _primeiro_com_nome(queryset, campo, nome):
    return next((obj for obj in queryset if _mesmo_nome(getattr(obj, campo), nome)), None)


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
            'etapa', 'ordem', 'idade_min', 'idade_max', 'frequencia_registro',
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
        return (
            not _mesmo_nome(self._valor(attrs, 'nome'), self.instance.nome)
            or self._valor(attrs, 'ano_letivo') != self.instance.ano_letivo
        )

    def _checar_nome_duplicado(self, escola_id, attrs):
        nome = self._valor(attrs, 'nome')
        ano = self._valor(attrs, 'ano_letivo')
        # Sem constraint no banco: esta checagem é a regra. A view trava a linha
        # da escola durante validação + save para não haver corrida.
        # _base_manager: sem recorte de tenant; o filtro por escola já delimita.
        existentes = Turma._base_manager.filter(escola_id=escola_id, ano_letivo=ano)
        if self.instance is not None:
            existentes = existentes.exclude(pk=self.instance.pk)
        existente = _primeiro_com_nome(existentes, 'nome', nome)
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
            'etapa', 'ordem', 'idade_min', 'idade_max', 'frequencia_registro',
            'escola', 'escola_nome', 'professores',
        ]
        read_only_fields = fields


class TurmaFrequenciaSerializer(serializers.ModelSerializer):
    """Linha da tela Registros (só leitura). Enxuto de propósito: sem
    professores nem campos de cadastro. Depende da view fazer
    select_related('escola') e .only() nestes campos
    (ver views/turma.py::listar_frequencias_registro)."""
    escola_nome = serializers.CharField(source='escola.nome', read_only=True)

    class Meta:
        model = Turma
        fields = [
            'id', 'nome', 'turno', 'ano_letivo', 'etapa', 'ativa',
            'escola', 'escola_nome', 'frequencia_registro',
        ]
        read_only_fields = fields


class AtualizarFrequenciaSerializer(serializers.Serializer):
    """Body do PATCH /turmas/frequencia-registro/atualizar/.

    Informe UM dos alvos:
      turmas: [uuid, ...]  — as turmas indicadas (máx. 200)
      escola: uuid         — todas as turmas ATIVAS da escola
    """
    LIMITE_TURMAS = 200

    frequencia_registro = serializers.ChoiceField(choices=Turma.FREQUENCIAS_REGISTRO)
    turmas = serializers.ListField(
        child=serializers.UUIDField(), required=False, allow_empty=False,
        max_length=LIMITE_TURMAS,
    )
    escola = serializers.UUIDField(required=False)

    def validate(self, attrs):
        if bool(attrs.get('turmas')) == bool(attrs.get('escola')):
            raise serializers.ValidationError('Informe `turmas` ou `escola` (apenas um dos dois).')
        return attrs


def _sincronizar_professores_disciplina(disciplina, usuarios):
    """Deixa a disciplina vinculada exatamente a `usuarios`."""
    desejados = {u.id for u in usuarios}
    vinculos = UsuarioDisciplina.objects.filter(disciplina=disciplina)
    atuais = set(vinculos.values_list('usuario_id', flat=True))
    vinculos.exclude(usuario_id__in=desejados).delete()
    UsuarioDisciplina.objects.bulk_create([
        UsuarioDisciplina(
            disciplina=disciplina, usuario=u,
            escola_id=disciplina.escola_id, instituicao_id=disciplina.instituicao_id,
        )
        for u in usuarios if u.id not in atuais
    ])


class DisciplinaSerializer(serializers.ModelSerializer):
    """
    Cadastro de disciplina (mesmo padrão do TurmaSerializer).

    Criação: a view passa `context={'escola_id': ...}`, porque `escola` é
    read_only e as checagens de nome e de professores dependem dela.

    Nome único por escola sem diferenciar maiúsculas ("Matemática" =
    "matemática"). O banco tem UniqueConstraint(escola, nome), mas ela
    diferencia maiúsculas; a regra completa é esta checagem, e a view trava a
    linha da escola durante validação + save.

    `professores` (opcional, só escrita): ids de usuários. Quando enviada, os
    vínculos passam a ser exatamente essa lista, na mesma transação.
    """
    escola_nome = serializers.CharField(source='escola.nome', read_only=True)
    professores = serializers.ListField(
        child=serializers.UUIDField(), write_only=True, required=False,
    )

    class Meta:
        model = Disciplina
        fields = ['id', 'nome', 'ativo', 'escola', 'escola_nome', 'instituicao', 'professores', 'criado_em']
        read_only_fields = ['id', 'escola', 'instituicao', 'criado_em']

    def _escola_id(self):
        if self.instance is not None:
            return self.instance.escola_id
        return self.context.get('escola_id')

    def validate(self, attrs):
        escola_id = self._escola_id()
        if escola_id and self._mudou_nome(attrs):
            self._checar_nome_duplicado(escola_id, attrs['nome'])
        if 'professores' in attrs:
            attrs['professores'] = self._validar_professores(escola_id, attrs['professores'])
        return attrs

    def _mudou_nome(self, attrs):
        """Na edição, só checa se o nome mudou (fora maiúsculas): uma disciplina
        que já estava duplicada antes da regra continua editável."""
        if 'nome' not in attrs:
            return False
        if self.instance is None:
            return True
        return not _mesmo_nome(attrs['nome'], self.instance.nome)

    def _checar_nome_duplicado(self, escola_id, nome):
        existentes = Disciplina._base_manager.filter(escola_id=escola_id)
        if self.instance is not None:
            existentes = existentes.exclude(pk=self.instance.pk)
        existente = _primeiro_com_nome(existentes, 'nome', nome)
        if existente is None:
            return
        mensagem = f'Já existe a disciplina "{existente.nome}" nesta escola.'
        if not existente.ativo:
            mensagem += ' Ela está desativada: reative-a na aba Inativas.'
        raise serializers.ValidationError({'nome': [mensagem]})

    def _validar_professores(self, escola_id, ids):
        if escola_id is None:
            raise serializers.ValidationError({'professores': ['Escola da disciplina não definida.']})
        ja_vinculados = []
        if self.instance is not None:
            ja_vinculados = UsuarioDisciplina.objects.filter(
                disciplina=self.instance,
            ).values_list('usuario_id', flat=True)
        usuarios, erro = validar_professores_disciplina(escola_id, ids, ja_vinculados)
        if erro:
            raise serializers.ValidationError({'professores': [erro]})
        return usuarios

    def create(self, validated_data):
        professores = validated_data.pop('professores', None)
        disciplina = super().create(validated_data)
        if professores is not None:
            _sincronizar_professores_disciplina(disciplina, professores)
        return disciplina

    def update(self, instance, validated_data):
        professores = validated_data.pop('professores', None)
        disciplina = super().update(instance, validated_data)
        if professores is not None:
            _sincronizar_professores_disciplina(disciplina, professores)
        return disciplina


class ProfessorDaDisciplinaSerializer(serializers.ModelSerializer):
    """Vínculo resumido para a listagem de disciplinas."""
    usuario_nome = serializers.CharField(source='usuario.nome', read_only=True)
    usuario_nivel = serializers.CharField(source='usuario.nivel', read_only=True)

    class Meta:
        model = UsuarioDisciplina
        fields = ['usuario', 'usuario_nome', 'usuario_nivel']


class DisciplinaListaSerializer(serializers.ModelSerializer):
    """
    Linha da listagem paginada de disciplinas (só leitura), com os professores
    embutidos. Depende da view fazer select_related('escola') e o Prefetch em
    `professores_listagem` (ver views/disciplina.py::listar_disciplinas).
    """
    escola_nome = serializers.CharField(source='escola.nome', read_only=True)
    professores = ProfessorDaDisciplinaSerializer(source='professores_listagem', many=True, read_only=True)

    class Meta:
        model = Disciplina
        fields = ['id', 'nome', 'ativo', 'escola', 'escola_nome', 'professores']
        read_only_fields = fields


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


NIVEIS_COM_TIPO_ESPECIALISTA = ('especialista', 'professor_especialista')


class UsuarioSerializer(serializers.ModelSerializer):
    """Serializer para o model Usuario (leitura — usado no payload de login, em
    /me/ e na lista completa de /usuarios/).

    Em listas, a view faz select_related('escola', 'instituicao', 'especialista');
    sem isso, cada usuário custa até 3 queries extras.
    """

    escola_nome = serializers.CharField(source='escola.nome', read_only=True, default=None)
    instituicao_nome = serializers.CharField(source='instituicao.nome', read_only=True, default=None)
    tipo_especialista = serializers.CharField(source='especialista.tipo_especialista', read_only=True, default=None)

    class Meta:
        model = Usuario
        fields = [
            'id', 'nome', 'email', 'numero', 'nivel',
            'escola', 'escola_nome', 'instituicao', 'instituicao_nome',
            'especialista', 'tipo_especialista', 'is_active',
        ]
        read_only_fields = fields


class _TurmaDoUsuarioSerializer(serializers.ModelSerializer):
    turma_nome = serializers.CharField(source='turma.nome', read_only=True)

    class Meta:
        model = UsuarioTurma
        fields = ['turma', 'turma_nome']


class _DisciplinaDoUsuarioSerializer(serializers.ModelSerializer):
    disciplina_nome = serializers.CharField(source='disciplina.nome', read_only=True)

    class Meta:
        model = UsuarioDisciplina
        fields = ['disciplina', 'disciplina_nome']


class UsuarioListaSerializer(UsuarioSerializer):
    """
    Linha da listagem paginada de usuários, com turmas e disciplinas embutidas
    (a tela de edição já abre preenchida, sem requisição extra). Depende dos
    Prefetch em `turmas_listagem` e `disciplinas_listagem` da view.
    """
    turmas = _TurmaDoUsuarioSerializer(source='turmas_listagem', many=True, read_only=True)
    disciplinas = _DisciplinaDoUsuarioSerializer(source='disciplinas_listagem', many=True, read_only=True)

    class Meta(UsuarioSerializer.Meta):
        fields = UsuarioSerializer.Meta.fields + ['turmas', 'disciplinas']
        read_only_fields = fields


class UsuarioWriteSerializer(serializers.ModelSerializer):
    """Serializer de escrita para Usuario — lida com hash de senha via set_password.

    Campos opcionais, só escrita, gravados na mesma transação (a view usa
    transaction.atomic):

    * `turmas`: ids de turmas. Os vínculos passam a ser exatamente essa lista.
      Só para níveis vinculáveis a turma, e só turmas da escola do usuário.
    * `disciplinas`: ids de disciplinas. Idem; só para professor_fundamental.
    * `tipo_especialista`: para especialista/professor_especialista. Liga o
      usuário ao registro de Especialista (catálogo por rede+escola) desse tipo,
      criando-o se ainda não existir.

    Se a escola do usuário mudar e `turmas`/`disciplinas` não vierem, os
    vínculos antigos (da escola anterior) são removidos.
    """

    password = serializers.CharField(write_only=True, required=False, min_length=8)
    turmas = serializers.ListField(child=serializers.UUIDField(), write_only=True, required=False)
    disciplinas = serializers.ListField(child=serializers.UUIDField(), write_only=True, required=False)
    tipo_especialista = serializers.ChoiceField(
        choices=Especialista._meta.get_field('tipo_especialista').choices,
        write_only=True, required=False, allow_null=True, allow_blank=True,
    )

    class Meta:
        model = Usuario
        fields = [
            'id', 'nome', 'email', 'numero', 'nivel',
            'escola', 'instituicao', 'especialista', 'is_active', 'password',
            'turmas', 'disciplinas', 'tipo_especialista',
        ]
        read_only_fields = ['id']

    def _valor(self, attrs, campo):
        if campo in attrs:
            return attrs[campo]
        return getattr(self.instance, campo, None)

    def _id(self, valor):
        return getattr(valor, 'pk', valor)

    def validate(self, attrs):
        nivel = self._valor(attrs, 'nivel')
        escola_id = self._id(self._valor(attrs, 'escola'))
        instituicao_id = self._id(self._valor(attrs, 'instituicao'))

        if 'turmas' in attrs:
            attrs['turmas'] = self._validar_turmas(attrs['turmas'], nivel, escola_id)
        if 'disciplinas' in attrs:
            attrs['disciplinas'] = self._validar_disciplinas(attrs['disciplinas'], nivel, escola_id)

        if nivel not in NIVEIS_COM_TIPO_ESPECIALISTA:
            attrs.pop('tipo_especialista', None)
            if 'nivel' in attrs:  # deixou de ser especialista: desfaz a ligação
                attrs['especialista'] = None
        elif attrs.get('tipo_especialista'):
            if instituicao_id is None:
                raise serializers.ValidationError(
                    {'tipo_especialista': ['O usuário precisa estar vinculado a uma instituição.']}
                )
            attrs['_especialista_chave'] = (instituicao_id, escola_id, attrs.pop('tipo_especialista'))
        else:
            attrs.pop('tipo_especialista', None)
        return attrs

    def _validar_turmas(self, ids, nivel, escola_id):
        if not ids:
            return []
        from .escopo import NIVEIS_VINCULAVEIS_TURMA
        if nivel not in NIVEIS_VINCULAVEIS_TURMA:
            raise serializers.ValidationError({'turmas': ['Este perfil não pode ser vinculado a turmas.']})
        turmas = list(Turma._base_manager.filter(id__in=ids))
        if len(turmas) != len(set(ids)) or any(t.escola_id != escola_id for t in turmas):
            raise serializers.ValidationError({'turmas': ['Todas as turmas precisam ser da escola do usuário.']})
        return turmas

    def _validar_disciplinas(self, ids, nivel, escola_id):
        if not ids:
            return []
        from .escopo import NIVEIS_VINCULAVEIS_DISCIPLINA
        if nivel not in NIVEIS_VINCULAVEIS_DISCIPLINA:
            raise serializers.ValidationError(
                {'disciplinas': ['Só professores do Ensino Fundamental podem ter disciplinas.']}
            )
        disciplinas = list(Disciplina._base_manager.filter(id__in=ids))
        if len(disciplinas) != len(set(ids)) or any(d.escola_id != escola_id for d in disciplinas):
            raise serializers.ValidationError(
                {'disciplinas': ['Todas as disciplinas precisam ser da escola do usuário.']}
            )
        return disciplinas

    def _aplicar_especialista(self, validated_data):
        chave = validated_data.pop('_especialista_chave', None)
        if chave is None:
            return
        instituicao_id, escola_id, tipo = chave
        especialista = Especialista._base_manager.filter(
            instituicao_id=instituicao_id, escola_id=escola_id, tipo_especialista=tipo,
        ).order_by('criado_em').first()
        if especialista is None:
            especialista = Especialista._base_manager.create(
                instituicao_id=instituicao_id, escola_id=escola_id, tipo_especialista=tipo,
            )
        validated_data['especialista'] = especialista

    def _sincronizar_vinculos(self, usuario, turmas, disciplinas, escola_mudou):
        if turmas is None and escola_mudou:
            turmas = []
        if disciplinas is None and escola_mudou:
            disciplinas = []
        if turmas is not None:
            desejadas = {t.pk for t in turmas}
            vinculos = UsuarioTurma.objects.filter(usuario=usuario)
            atuais = set(vinculos.values_list('turma_id', flat=True))
            vinculos.exclude(turma_id__in=desejadas).delete()
            UsuarioTurma.objects.bulk_create(
                [UsuarioTurma(usuario=usuario, turma=t) for t in turmas if t.pk not in atuais]
            )
        if disciplinas is not None:
            desejadas = {d.pk for d in disciplinas}
            vinculos = UsuarioDisciplina.objects.filter(usuario=usuario)
            atuais = set(vinculos.values_list('disciplina_id', flat=True))
            vinculos.exclude(disciplina_id__in=desejadas).delete()
            UsuarioDisciplina.objects.bulk_create([
                UsuarioDisciplina(
                    usuario=usuario, disciplina=d, escola_id=d.escola_id, instituicao_id=d.instituicao_id,
                )
                for d in disciplinas if d.pk not in atuais
            ])

    def create(self, validated_data):
        turmas = validated_data.pop('turmas', None)
        disciplinas = validated_data.pop('disciplinas', None)
        self._aplicar_especialista(validated_data)
        password = validated_data.pop('password', None)
        if not password:
            raise serializers.ValidationError({'password': 'Senha é obrigatória na criação.'})
        usuario = Usuario(**validated_data)
        usuario.set_password(password)
        usuario.save()
        self._sincronizar_vinculos(usuario, turmas, disciplinas, escola_mudou=False)
        return usuario

    def update(self, instance, validated_data):
        turmas = validated_data.pop('turmas', None)
        disciplinas = validated_data.pop('disciplinas', None)
        self._aplicar_especialista(validated_data)
        escola_anterior = instance.escola_id
        password = validated_data.pop('password', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        self._sincronizar_vinculos(
            instance, turmas, disciplinas, escola_mudou=instance.escola_id != escola_anterior,
        )
        return instance


class AlunoSerializer(serializers.ModelSerializer):
    """
    Cadastro de aluno.

    Criação: a view passa `context={'escola_id': ...}` (a escola vem da turma),
    porque `escola` é read_only aqui e a checagem de duplicidade depende dela.
    A view também trava a linha da escola durante validação + save (ver
    views/aluno.py::_validar_e_salvar), como em turmas.

    Listagem: a view faz select_related('turma', 'escola'); sem isso,
    `turma_nome` e `escola_nome` custam 2 queries por aluno.
    """
    turma_nome = serializers.CharField(source='turma.nome', read_only=True)
    escola_nome = serializers.CharField(source='escola.nome', read_only=True)
    # Só leitura: a foto muda pelo endpoint /alunos/<id>/foto/.
    foto_url = serializers.SerializerMethodField()

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

    def _valor(self, attrs, campo):
        """Valor final do campo: o enviado ou, no PATCH, o que já está salvo."""
        if campo in attrs:
            return attrs[campo]
        return getattr(self.instance, campo, None)

    def get_foto_url(self, aluno):
        """URL pré-assinada nova a cada leitura (a salva expira em ~1h). Assinar
        é um cálculo local, sem rede e sem gravar nada (ao contrário de
        storage.get_foto_url, que salva o aluno) — barato até em listagens."""
        from .storage import generate_presigned_url, is_s3_configured
        if aluno.foto_storage_key and is_s3_configured():
            return generate_presigned_url(aluno.foto_storage_key) or aluno.foto_url
        return aluno.foto_url or None

    def validate_data_nascimento(self, valor):
        if valor and valor > timezone.localdate():
            raise serializers.ValidationError('A data de nascimento não pode ser no futuro.')
        return valor

    def validate_telefone_responsavel(self, valor):
        if not valor:
            return valor
        valor = valor.strip()
        digitos = ''.join(c for c in valor if c.isdigit())
        # 10–11 dígitos (DDD + número); até 13 com o código do país (55).
        if not 10 <= len(digitos) <= 13:
            raise serializers.ValidationError('Informe o telefone com DDD, ex.: (84) 99999-9999.')
        return valor

    def validate(self, attrs):
        turma = attrs.get('turma')
        mudou_turma = turma is not None and (self.instance is None or turma.pk != self.instance.turma_id)
        if mudou_turma:
            self._checar_turma(turma)

        escola_id = self.instance.escola_id if self.instance is not None else self.context.get('escola_id')
        if escola_id and self._mudou_nome_ou_nascimento(attrs):
            self._checar_duplicado(escola_id, attrs)
        return attrs

    def _checar_turma(self, turma):
        if self.instance is not None and turma.escola_id != self.instance.escola_id:
            raise serializers.ValidationError(
                {'turma': ['Não é possível mover o aluno para uma turma de outra escola.']}
            )
        if not turma.ativa:
            raise serializers.ValidationError({'turma': ['A turma escolhida está desativada.']})

    def _mudou_nome_ou_nascimento(self, attrs):
        """Na edição, só checa duplicidade se nome ou nascimento mudaram de fato:
        um par que já estava duplicado antes da regra continua editável."""
        if self.instance is None:
            return True
        return (
            not _mesmo_nome(self._valor(attrs, 'nome_completo'), self.instance.nome_completo)
            or self._valor(attrs, 'data_nascimento') != self.instance.data_nascimento
        )

    def _checar_duplicado(self, escola_id, attrs):
        """Mesmo nome (sem diferenciar maiúsculas) + mesma data de nascimento na
        mesma escola é quase certamente o mesmo aluno cadastrado duas vezes
        (ex.: planilha de importação enviada de novo). Sem data de nascimento
        não dá para distinguir homônimos, então não bloqueia."""
        nascimento = self._valor(attrs, 'data_nascimento')
        if not nascimento:
            return
        existentes = Aluno._base_manager.filter(
            escola_id=escola_id, data_nascimento=nascimento,
        ).select_related('turma')
        if self.instance is not None:
            existentes = existentes.exclude(pk=self.instance.pk)
        existente = _primeiro_com_nome(existentes, 'nome_completo', self._valor(attrs, 'nome_completo'))
        if existente is None:
            return
        mensagem = (
            f'{existente.nome_completo}, nascido(a) em {nascimento:%d/%m/%Y}, '
            f'já está cadastrado(a) nesta escola (turma {existente.turma.nome}).'
        )
        if existente.status_vinculo != 'ativo':
            mensagem += f' O cadastro está como "{existente.get_status_vinculo_display()}": reative-o em vez de criar outro.'
        raise serializers.ValidationError({'nome_completo': [mensagem]})


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


class _ReferenciaBNCCMixin:
    """Referência BNCC obrigatória, comum às duas perguntas (Pergunta e
    PerguntaEspecialista).

    A tela informa o CÓDIGO em `referencia_bncc` (ex.: "EI03EO01"); a
    habilidade é localizada no catálogo sem diferenciar maiúsculas. O id em
    `habilidade_bncc` também é aceito.
    - Criação: referência obrigatória.
    - Edição: não pode ser removida; registros antigos sem referência
      continuam editáveis (ex.: desativar) até alguém informá-la.
    - Habilidade desativada no catálogo não pode ser escolhida de novo; quem
      já a usa continua como está.
    """

    def _validar_referencia(self, attrs):
        if 'referencia_bncc' in attrs:
            codigo = (attrs.pop('referencia_bncc') or '').strip()
            if not codigo:
                raise serializers.ValidationError({'referencia_bncc': ['Informe a referência BNCC.']})
            habilidade = HabilidadeBNCC._base_manager.filter(codigo__iexact=codigo).first()
            if habilidade is None:
                raise serializers.ValidationError(
                    {'referencia_bncc': [f'O código "{codigo}" não foi encontrado no catálogo da BNCC.']}
                )
            attrs['habilidade_bncc'] = habilidade

        habilidade = attrs.get('habilidade_bncc')
        if self.instance is None:
            if habilidade is None:
                raise serializers.ValidationError({'referencia_bncc': ['Informe a referência BNCC.']})
        elif 'habilidade_bncc' in attrs and habilidade is None:
            raise serializers.ValidationError({'referencia_bncc': ['A referência BNCC não pode ser removida.']})

        mudou = habilidade is not None and (
            self.instance is None or habilidade.pk != self.instance.habilidade_bncc_id
        )
        if mudou and not habilidade.ativa:
            raise serializers.ValidationError(
                {'referencia_bncc': [f'A habilidade {habilidade.codigo} está desativada no catálogo da BNCC.']}
            )
        return attrs


class PerguntaSerializer(_ReferenciaBNCCMixin, serializers.ModelSerializer):
    """
    Pergunta BNCC: oficial (escola nula, vale para todas) ou da escola.
    Referência BNCC obrigatória (ver _ReferenciaBNCCMixin).

    Em listas, a view faz select_related('campo_experiencia', 'habilidade_bncc', 'escola').
    """
    escola_nome = serializers.CharField(source='escola.nome', read_only=True, default=None)
    campo_experiencia_nome = serializers.CharField(source='campo_experiencia.nome', read_only=True, default=None)
    campo_experiencia_icone = serializers.CharField(source='campo_experiencia.icone', read_only=True, default=None)
    habilidade_bncc_codigo = serializers.CharField(source='habilidade_bncc.codigo', read_only=True, default=None)
    habilidade_bncc_descricao = serializers.CharField(source='habilidade_bncc.descricao', read_only=True, default=None)
    referencia_bncc = serializers.CharField(write_only=True, required=False, allow_blank=True, max_length=20)
    # `todos`: o TenantManager esconderia os campos oficiais (escola nula).
    # O recorte oficial + escola da pergunta é feito na view (_campo_invalido).
    campo_experiencia = serializers.PrimaryKeyRelatedField(
        queryset=CampoPedagogico.todos.all(), required=False, allow_null=True,
    )

    class Meta:
        model = Pergunta
        fields = [
            'id', 'pergunta', 'pergunta_norma', 'area_conhecimento', 'origem', 'ativa', 'faixa_etaria',
            'campo_experiencia', 'campo_experiencia_nome', 'campo_experiencia_icone',
            'habilidade_bncc', 'habilidade_bncc_codigo', 'habilidade_bncc_descricao', 'referencia_bncc',
            'escola', 'escola_nome', 'instituicao', 'criado_em', 'atualizado_em',
        ]
        read_only_fields = ['id', 'criado_em', 'atualizado_em', 'escola', 'instituicao']

    def validate(self, attrs):
        return self._validar_referencia(attrs)


class PerguntaEspecialistaSerializer(_ReferenciaBNCCMixin, serializers.ModelSerializer):
    """
    Pergunta livre de especialista (tela "Perguntas" do admin).

    Referência BNCC obrigatória (ver _ReferenciaBNCCMixin).

    Em listas, a view faz select_related('campo_experiencia', 'habilidade_bncc',
    'escola', 'usuario_especialista') por causa dos campos *_nome/_codigo.
    """
    usuario_especialista_nome = serializers.CharField(source='usuario_especialista.nome', read_only=True)
    escola_nome = serializers.CharField(source='escola.nome', read_only=True)
    campo_experiencia_nome = serializers.CharField(source='campo_experiencia.nome', read_only=True, default=None)
    campo_experiencia_icone = serializers.CharField(source='campo_experiencia.icone', read_only=True, default=None)
    habilidade_bncc_codigo = serializers.CharField(source='habilidade_bncc.codigo', read_only=True, default=None)
    habilidade_bncc_descricao = serializers.CharField(source='habilidade_bncc.descricao', read_only=True, default=None)
    referencia_bncc = serializers.CharField(write_only=True, required=False, allow_blank=True, max_length=20)
    # `todos`: o TenantManager esconderia os campos oficiais (escola nula).
    # O recorte oficial + escola da pergunta é feito na view (_campo_invalido).
    campo_experiencia = serializers.PrimaryKeyRelatedField(
        queryset=CampoPedagogico.todos.all(), required=False, allow_null=True,
    )

    class Meta:
        model = PerguntaEspecialista
        fields = [
            'id', 'pergunta', 'pergunta_facilitadora', 'nivel', 'status',
            'campo_experiencia', 'campo_experiencia_nome', 'campo_experiencia_icone',
            'habilidade_bncc', 'habilidade_bncc_codigo', 'habilidade_bncc_descricao', 'referencia_bncc',
            'usuario_especialista', 'usuario_especialista_nome',
            'escola', 'escola_nome', 'instituicao', 'criado_em', 'atualizado_em',
        ]
        read_only_fields = [
            'id', 'usuario_especialista', 'escola', 'instituicao', 'criado_em', 'atualizado_em',
        ]

    def validate(self, attrs):
        return self._validar_referencia(attrs)


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
    """
    Cadastro de período avaliativo.

    Criação: a view passa `context={'escola_id': ...}` (vinda do
    resolver_escopo_criacao), porque `escola` é read_only e a checagem de
    sobreposição depende dela. A view trava a linha da escola durante
    validação + save (ver views/avaliacao.py::_validar_e_salvar_periodo).

    Listagem: a view faz select_related('escola') por causa de `escola_nome`.
    """
    escola_nome = serializers.CharField(source='escola.nome', read_only=True)

    class Meta:
        model = PeriodoAvaliativo
        fields = [
            'id', 'descricao', 'tipo_periodo', 'ano', 'numero',
            'data_inicio', 'data_fim', 'escola', 'escola_nome', 'instituicao',
            'criado_em', 'atualizado_em',
        ]
        read_only_fields = ['id', 'escola', 'instituicao', 'criado_em', 'atualizado_em']
        extra_kwargs = {
            'ano': {'min_value': 2000, 'max_value': 2100},
            'numero': {'min_value': 1, 'max_value': 12},
        }

    def _valor(self, attrs, campo):
        """Valor final do campo: o enviado ou, no PATCH, o que já está salvo."""
        if campo in attrs:
            return attrs[campo]
        return getattr(self.instance, campo, None)

    def validate(self, attrs):
        inicio = self._valor(attrs, 'data_inicio')
        fim = self._valor(attrs, 'data_fim')
        if inicio and fim and fim < inicio:
            raise serializers.ValidationError(
                {'data_fim': ['A data de fim não pode ser anterior à data de início.']}
            )

        # Sem ano informado, usa o do início (é o que as telas filtram/mostram).
        if inicio and self._valor(attrs, 'ano') is None:
            attrs['ano'] = inicio.year

        escola_id = self.instance.escola_id if self.instance is not None else self.context.get('escola_id')
        campos_da_regra = ('data_inicio', 'data_fim', 'tipo_periodo')
        if escola_id and inicio and fim and (self.instance is None or any(c in attrs for c in campos_da_regra)):
            self._checar_sobreposicao(escola_id, attrs, inicio, fim)
        return attrs

    def _checar_sobreposicao(self, escola_id, attrs, inicio, fim):
        """Dois períodos do MESMO tipo na mesma escola não podem ter datas em
        comum (ex.: 1º e 2º bimestre se cruzando). Tipos diferentes podem: um
        período anual convive com os bimestres dentro dele."""
        tipo = self._valor(attrs, 'tipo_periodo')
        conflitos = PeriodoAvaliativo._base_manager.filter(
            escola_id=escola_id, tipo_periodo=tipo,
            data_inicio__lte=fim, data_fim__gte=inicio,
        )
        if self.instance is not None:
            conflitos = conflitos.exclude(pk=self.instance.pk)
        conflito = conflitos.order_by('data_inicio').first()
        if conflito is None:
            return
        raise serializers.ValidationError({'data_inicio': [
            f'As datas se sobrepõem ao período "{conflito.descricao}" '
            f'({conflito.data_inicio:%d/%m/%Y} a {conflito.data_fim:%d/%m/%Y}), do mesmo tipo, nesta escola.'
        ]})


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
        base = PromptTemplate._base_manager.filter(categoria=categoria).order_by('-criado_em')

        if escola_id:
            personalizado = base.filter(escola_id=escola_id).first()
            if personalizado and personalizado.personalizado.strip():
                return {'origem': 'personalizado', 'texto': personalizado.personalizado}

        global_tpl = base.filter(escola__isnull=True, instituicao__isnull=True).first()
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