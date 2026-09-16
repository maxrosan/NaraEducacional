"""Modelos do gravador de áudio (dispositivo físico do relato individual).

Um microfone ESP32 sem tela/teclado, pareado a uma professora + turma pela
própria plataforma. O dispositivo envia apenas o WAV; a identidade vem SEMPRE
do vínculo no banco (nunca do payload).

Decisões de desenho (ver conversa de planejamento):
  - Token por dispositivo, guardado como HASH (o valor claro só aparece uma vez,
    na resposta do pareamento). Formato: "<uuid-do-dispositivo>.<segredo>" —
    o id localiza a linha e o segredo é conferido contra o hash.
  - Pareamento por código curto de uso único gerado pela professora logada,
    que escolhe a turma na hora (resolve a falta de UI no dispositivo).
  - Uma professora pode atender VÁRIAS turmas: o dispositivo tem M2M `turmas`
    e o pareamento por nome busca entre as crianças de todas elas.
  - `AudioDispositivo` guarda um SNAPSHOT de professora/turma/instituição no
    momento do upload: repareamento futuro não reescreve o histórico.
  - `(dispositivo, upload_id)` unique é a chave da idempotência: retry do
    firmware não duplica relato.
  - Data do registro é carimbada pelo SERVIDOR (ESP32 pode ter relógio errado).
  - `instituicao` presente em todos os modelos, pronto para o multi-tenant.
"""

import uuid

from django.db import models
from django.utils import timezone


class DispositivoGravador(models.Model):
    """Gravador físico pareado a uma professora + turma."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    device_id = models.CharField(
        max_length=100, unique=True, db_index=True,
        verbose_name='Identificador do hardware (MAC/serial)',
    )
    nome = models.CharField(
        max_length=120, blank=True, default='',
        verbose_name='Nome amigável (ex.: Gravador Sala 5C)',
    )
    token_hash = models.CharField(
        max_length=128, verbose_name='Hash do token de acesso',
    )
    professora = models.ForeignKey(
        'Usuario', on_delete=models.CASCADE, related_name='dispositivos_gravador',
        verbose_name='Professora vinculada',
    )
    # Professora pode dar aula em mais de uma turma: `turmas` é o ESCOPO de
    # permissão (onde este gravador pode registrar) e `turma_ativa` é a turma
    # corrente, trocada pela própria fala ("estou na turma Nível 5") durante o
    # processamento — persiste entre gravações até ela anunciar outra.
    turmas = models.ManyToManyField(
        'Turma', blank=True, related_name='dispositivos_gravador',
        db_table='dispositivos_gravador_turmas', verbose_name='Turmas atendidas',
    )
    turma_ativa = models.ForeignKey(
        'Turma', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='dispositivos_com_turma_ativa',
        verbose_name='Turma ativa (definida por voz)',
    )
    instituicao = models.ForeignKey(
        'Instituicao', on_delete=models.CASCADE, related_name='dispositivos_gravador',
    )
    ativo = models.BooleanField(default=True, verbose_name='Ativo (não revogado)')
    revogado_em = models.DateTimeField(null=True, blank=True)
    last_seen = models.DateTimeField(
        null=True, blank=True, verbose_name='Último contato do dispositivo',
    )
    data_criacao = models.DateTimeField(default=timezone.now)
    data_atualizacao = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'dispositivos_gravador'
        verbose_name = 'Dispositivo gravador'
        verbose_name_plural = 'Dispositivos gravadores'
        ordering = ['-data_criacao']
        indexes = [
            models.Index(fields=['instituicao', 'ativo']),
        ]

    def __str__(self):
        estado = 'ativo' if self.ativo else 'revogado'
        return f"{self.nome or self.device_id} ({estado})"


class CodigoPareamento(models.Model):
    """Código curto de uso único que vincula um gravador à professora+turma.

    Gerado pela professora logada na plataforma (que escolhe a turma) e
    digitado no portal de configuração do próprio dispositivo.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    codigo = models.CharField(max_length=12, db_index=True, verbose_name='Código')
    professora = models.ForeignKey(
        'Usuario', on_delete=models.CASCADE, related_name='codigos_pareamento',
    )
    turmas = models.ManyToManyField(
        'Turma', blank=True, related_name='codigos_pareamento',
        db_table='codigos_pareamento_turmas', verbose_name='Turmas do vínculo',
    )
    instituicao = models.ForeignKey(
        'Instituicao', on_delete=models.CASCADE, related_name='codigos_pareamento',
    )
    expira_em = models.DateTimeField(verbose_name='Expira em')
    usado_em = models.DateTimeField(null=True, blank=True)
    dispositivo = models.ForeignKey(
        DispositivoGravador, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='codigos_usados', verbose_name='Dispositivo que consumiu',
    )
    data_criacao = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'codigos_pareamento'
        verbose_name = 'Código de pareamento'
        verbose_name_plural = 'Códigos de pareamento'
        ordering = ['-data_criacao']

    def __str__(self):
        return f"{self.codigo} ({'usado' if self.usado_em else 'pendente'})"

    @property
    def valido(self) -> bool:
        return self.usado_em is None and self.expira_em > timezone.now()


class AudioDispositivo(models.Model):
    """Cada upload de WAV vindo de um gravador.

    Professora/turma/instituição são snapshot do vínculo no momento do envio.
    """

    STATUS_CHOICES = [
        ('recebido', 'Recebido (aguardando processamento)'),
        ('processando', 'Processando'),
        ('processado', 'Processado (observações geradas)'),
        ('comando', 'Comando de sala (só anunciou a turma)'),
        ('falhou', 'Falha no processamento'),
    ]

    # Como a turma deste áudio foi decidida. É isso que o firmware consulta
    # para dar retorno à professora (LED/bipe), já que o aparelho não tem tela.
    TURMA_RESULTADO_CHOICES = [
        ('', 'Ainda não processado'),
        ('anunciada', 'Anunciada na fala e autorizada'),
        ('nao_autorizada', 'Anunciada na fala, mas fora do escopo do dispositivo'),
        ('ativa', 'Turma ativa corrente (nada foi anunciado)'),
        ('unica', 'Única turma do dispositivo'),
        ('indefinida', 'Não foi possível determinar a turma'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dispositivo = models.ForeignKey(
        DispositivoGravador, on_delete=models.PROTECT, related_name='audios',
    )
    # Snapshot da identidade no momento do upload (repareamento não reescreve histórico)
    professora = models.ForeignKey(
        'Usuario', on_delete=models.SET_NULL, null=True, related_name='audios_dispositivo',
    )
    # Turma deste áudio. No upload é apenas PROVISÓRIA (a turma ativa corrente),
    # porque a fala ainda não foi transcrita; o processamento a substitui pela
    # turma realmente anunciada. Fica nula quando não dá para decidir.
    turma = models.ForeignKey(
        'Turma', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='audios_dispositivo',
    )
    instituicao = models.ForeignKey(
        'Instituicao', on_delete=models.CASCADE, related_name='audios_dispositivo',
    )
    upload_id = models.UUIDField(
        verbose_name='UUID gerado pelo firmware (idempotência)',
    )
    sha256 = models.CharField(max_length=64, verbose_name='SHA-256 do arquivo')
    tamanho_arquivo = models.PositiveIntegerField(verbose_name='Tamanho (bytes)')
    duracao_seg = models.PositiveIntegerField(null=True, blank=True)
    arquivo_path = models.CharField(max_length=500, verbose_name='Chave no storage')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='recebido')
    erro_processamento = models.TextField(blank=True, default='')
    erro_codigo = models.CharField(
        max_length=40, blank=True, default='',
        verbose_name='Código do erro (legível por máquina, para o firmware)',
    )

    # --- Resultado do processamento (base do feedback ao gravador) ---
    transcricao = models.TextField(
        blank=True, default='',
        verbose_name='Transcrição completa do áudio',
    )
    turma_resultado = models.CharField(
        max_length=20, choices=TURMA_RESULTADO_CHOICES, blank=True, default='',
        verbose_name='Como a turma foi decidida',
    )
    turma_anunciada_texto = models.CharField(
        max_length=200, blank=True, default='',
        verbose_name='Nome de turma reconhecido na fala',
    )
    observacao = models.ForeignKey(
        'ObservacaoTranscricao', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='audios_dispositivo',
        verbose_name='Primeira observação gerada (atalho para o relato)',
    )
    total_observacoes = models.PositiveSmallIntegerField(
        default=0, verbose_name='Quantas observações o áudio gerou',
    )
    alunos_identificados = models.JSONField(
        default=list, blank=True,
        verbose_name='Nomes pareados com crianças da turma',
    )
    nomes_nao_identificados = models.JSONField(
        default=list, blank=True,
        verbose_name='Nomes citados que não bateram com nenhuma criança',
    )
    # Carimbo do SERVIDOR (o ESP32 pode ter relógio dessincronizado)
    data_recebimento = models.DateTimeField(default=timezone.now, db_index=True)
    data_processamento = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'audios_dispositivo'
        verbose_name = 'Áudio de dispositivo'
        verbose_name_plural = 'Áudios de dispositivos'
        ordering = ['-data_recebimento']
        constraints = [
            models.UniqueConstraint(
                fields=['dispositivo', 'upload_id'],
                name='uniq_audio_por_dispositivo_upload',
            ),
        ]
        indexes = [
            models.Index(fields=['instituicao', '-data_recebimento']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"Áudio {self.upload_id} ({self.get_status_display()})"

    @property
    def feedback(self) -> dict:
        """Resumo pronto para o firmware acender LED/bipar, sem interpretar nada.

        ``sinal`` é o único campo que o aparelho precisa ler:
          * ``aguardando`` — ainda processando, consultar de novo;
          * ``ok``         — turma resolvida e pelo menos uma criança registrada;
          * ``atencao``    — o áudio entrou, mas algo ficou incompleto
            (turma não autorizada, turma indefinida, nome não reconhecido);
          * ``erro``       — falhou, nada foi registrado.
        """
        if self.status in ('recebido', 'processando'):
            return {'sinal': 'aguardando', 'mensagem': 'Processando a gravação...'}

        turma_nome = getattr(self.turma, 'nome', '')

        if self.status == 'comando':
            # Ela só trocou de sala. Fez tudo certo — não pode acender alerta.
            return {
                'sinal': 'ok',
                'mensagem': f'Turma {turma_nome} selecionada. Pode gravar o relato.',
            }

        if self.status == 'falhou':
            if self.turma_resultado == 'nao_autorizada':
                return {
                    'sinal': 'atencao',
                    'mensagem': (
                        f'A turma "{self.turma_anunciada_texto}" não está liberada '
                        'para este gravador.'
                    ),
                }
            if self.turma_resultado == 'indefinida':
                return {
                    'sinal': 'atencao',
                    'mensagem': 'Não identifiquei a turma. Diga, por exemplo, '
                                '"estou na turma Nível 3A" e grave de novo.',
                }
            if self.erro_codigo == 'nenhum_aluno':
                return {
                    'sinal': 'atencao',
                    'mensagem': f'{turma_nome}: nenhuma criança foi reconhecida na fala.'.strip(': '),
                }
            return {
                'sinal': 'erro',
                'mensagem': self.erro_processamento or 'Não foi possível processar a gravação.',
            }

        # processado
        partes = []
        if turma_nome:
            partes.append(turma_nome)
        partes.append(
            f'{self.total_observacoes} '
            f'{"criança registrada" if self.total_observacoes == 1 else "crianças registradas"}'
        )
        mensagem = ' · '.join(partes)

        if self.nomes_nao_identificados:
            return {
                'sinal': 'atencao',
                'mensagem': (
                    f'{mensagem}. Não reconheci: '
                    f'{", ".join(self.nomes_nao_identificados)}.'
                ),
            }
        return {'sinal': 'ok', 'mensagem': mensagem}
