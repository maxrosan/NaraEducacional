"""Processamento assíncrono dos áudios vindos do gravador físico.

Fecha o ciclo que o upload deixa em aberto: `AudioDispositivo` entra como
`recebido` e aqui vira relato individual.

    baixa o WAV do storage
      → transcreve
      → decide a TURMA pela própria fala ("estou na turma Nível 3A")
      → busca as crianças dessa turma no banco
      → extrai e pareia os nomes citados
      → grava uma ObservacaoTranscricao por criança

Diferenças em relação ao fluxo web (`views/audio.py`), que motivaram um módulo
próprio em vez de reuso direto:

  * **uma gravação só.** O comando de sala e o relato vêm no MESMO áudio, então
    a turma precisa ser resolvida a partir da transcrição, antes da extração —
    não dá para receber `turmaId` pronto;
  * **não existe frontend.** A lista de alunos vem do banco (`Crianca` da turma
    resolvida), não de um JSON enviado pelo navegador;
  * **não existe tela.** Todo desfecho — inclusive os ruins — é gravado de forma
    estruturada (`turma_resultado`, `erro_codigo`, `nomes_nao_identificados`)
    para o firmware conseguir dar retorno à professora por LED/bipe.

Regra de ouro: **na dúvida, não registra.** Turma não autorizada ou indefinida
falha o áudio em vez de gravar observação na sala errada — o áudio continua no
storage e pode ser reprocessado depois de ajustar o vínculo.
"""

from __future__ import annotations

import logging
import os
import tempfile

from django.db import transaction
from django.utils import timezone

from api.models import AudioDispositivo, Aluno, ObservacaoTranscricao, Turma
from api.services.audio import (
    InvalidAudioError,
    converter_para_wav,
    extrair_observacoes,
    parear_alunos_com_turma,
    transcrever_audio,
)
from api.services import dispositivo as dispositivo_service
from api.storage import download_bytes_from_storage

logger = logging.getLogger(__name__)


class AudioNaoProcessavel(Exception):
    """Falha definitiva: reprocessar sem mudar nada dá o mesmo resultado."""

    def __init__(self, mensagem: str, codigo: str):
        super().__init__(mensagem)
        self.codigo = codigo


def _alunos_da_turma(turma_id) -> list[dict]:
    """Crianças ativas da turma no formato que `parear_alunos_com_turma` espera."""
    return [
        {'id': str(c.id), 'nome_completo': c.nome_completo}
        for c in Aluno.objects.filter(
            turma_id=turma_id, status_vinculo='ativo',
        ).only('id', 'nome_completo')
    ]


def _transcrever(audio: AudioDispositivo) -> str:
    """Baixa o WAV do storage e transcreve, limpando o temporário no fim."""
    try:
        conteudo = download_bytes_from_storage(audio.arquivo_path)
    except FileNotFoundError as exc:
        raise AudioNaoProcessavel(
            'Arquivo de áudio não encontrado no storage.', 'arquivo_ausente',
        ) from exc

    caminho = None
    processado = None
    try:
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
            tmp.write(conteudo)
            caminho = tmp.name

        try:
            processado = converter_para_wav(caminho)
        except InvalidAudioError as exc:
            raise AudioNaoProcessavel(
                'Áudio corrompido ou em formato não suportado.', 'audio_invalido',
            ) from exc

        texto = (transcrever_audio(processado) or '').strip()
        if not texto:
            raise AudioNaoProcessavel(
                'A transcrição voltou vazia (gravação sem fala?).', 'transcricao_vazia',
            )
        return texto
    finally:
        for path in {caminho, processado}:
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass


def _resolver_turma(audio: AudioDispositivo, transcricao: str):
    """Decide a turma pela fala e persiste o diagnóstico no registro."""
    dispositivo = audio.dispositivo

    # Universo para detectar "falou uma turma que não é dela": as turmas da
    # instituição do dispositivo. Sem isso, uma turma alheia seria só ignorada
    # e o relato acabaria na turma anterior — silenciosamente.
    turmas_instituicao = Turma.objects.filter(
        instituicao_id=dispositivo.instituicao_id,
    ).only('id', 'nome')

    resolucao = dispositivo_service.resolver_turma_do_audio(
        dispositivo, transcricao=transcricao, turmas_instituicao=turmas_instituicao,
    )
    audio.turma = resolucao.turma
    audio.turma_resultado = resolucao.resultado
    audio.turma_anunciada_texto = resolucao.anunciada_texto

    if resolucao.resultado == 'nao_autorizada':
        raise AudioNaoProcessavel(
            f'A turma "{resolucao.anunciada_texto}" não está liberada para este gravador.',
            'turma_nao_autorizada',
        )
    if resolucao.turma is None:
        raise AudioNaoProcessavel(
            'Não foi possível identificar a turma da gravação. O gravador atende '
            'mais de uma turma e nenhuma foi anunciada na fala.',
            'turma_indefinida',
        )
    return resolucao.turma


def _gravar_observacoes(audio: AudioDispositivo, turma, transcricao: str, pareados: list):
    """Cria uma ObservacaoTranscricao por criança pareada."""
    professor = audio.professor
    criadas = []
    for item in pareados:
        criadas.append(ObservacaoTranscricao.objects.create(
            aluno_nome=item['aluno_nome'],
            aluno_id=item.get('crianca_id') or None,
            observacao_texto=item['observacao'],
            tipo_observacao='TRANSCRICAO_IA',
            data_observacao=timezone.localdate(),
            turma=turma,
            professor=professor,
            escola=audio.escola,
            instituicao=audio.instituicao,
            transcricao_completa=transcricao,
            metadados_ia={
                'origem': 'gravador',
                'device_id': audio.dispositivo.device_id,
                'audio_id': str(audio.id),
                'upload_id': str(audio.upload_id),
                'confianca': item.get('confianca'),
                'nome_original_detectado': item.get('nome_original_detectado'),
                'metodo_match': item.get('metodo_match'),
                'turma_resultado': audio.turma_resultado,
            },
        ))
    return criadas


def _marcar_falha(audio: AudioDispositivo, mensagem: str, codigo: str) -> AudioDispositivo:
    audio.status = 'falhou'
    audio.erro_processamento = mensagem
    audio.erro_codigo = codigo
    audio.data_processamento = timezone.now()
    audio.save()
    logger.warning(
        "[GRAVADOR] Áudio %s falhou (%s): %s", audio.upload_id, codigo, mensagem,
    )
    return audio


def processar_audio(audio: AudioDispositivo) -> AudioDispositivo:
    """Processa um áudio recebido. Nunca levanta: o desfecho fica no registro.

    Idempotente na prática: só age sobre `recebido`/`falhou`; um áudio já
    `processado`/`comando` é devolvido sem tocar em nada (evita relato duplicado
    se o worker rodar duas vezes).
    """
    if audio.status in ('processado', 'comando'):
        return audio

    audio.status = 'processando'
    audio.erro_processamento = ''
    audio.erro_codigo = ''
    audio.save(update_fields=['status', 'erro_processamento', 'erro_codigo'])

    try:
        transcricao = _transcrever(audio)
        audio.transcricao = transcricao

        turma = _resolver_turma(audio, transcricao)

        escola_id = str(audio.escola_id) if audio.escola_id else None
        try:
            extraido = extrair_observacoes(transcricao, escola_id=escola_id)
        except ValueError as exc:
            # Nenhum nome citado. Se ela ANUNCIOU a turma, isso não é erro: é uma
            # gravação só para trocar de sala ("estou na turma Nível 3A"), que é
            # como a professora usa o aparelho quando separa comando e relato em
            # dois áudios. Alertar aqui acenderia luz amarela em quem fez tudo
            # certo — e a troca de sala já foi efetivada acima.
            if audio.turma_resultado == 'anunciada':
                audio.status = 'comando'
                audio.data_processamento = timezone.now()
                audio.save()
                logger.info(
                    "[GRAVADOR] Áudio %s é comando de sala: turma ativa = %s",
                    audio.upload_id, turma.nome,
                )
                return audio
            raise AudioNaoProcessavel(str(exc), 'nenhum_aluno') from exc

        alunos = _alunos_da_turma(turma.id)
        if not alunos:
            raise AudioNaoProcessavel(
                f'A turma {turma.nome} não tem crianças ativas cadastradas.',
                'turma_sem_criancas',
            )

        resultado = parear_alunos_com_turma(
            extraido['nomes_alunos'], extraido['observacoes'], alunos,
        )
        pareados = resultado['pareados']
        nao_pareados = [
            item['nome_original_detectado'] for item in resultado['nao_pareados']
        ]

        # Reanexa o id da criança (parear_alunos_com_turma só devolve o nome)
        por_nome = {a['nome_completo']: a['id'] for a in alunos}
        for item in pareados:
            item['crianca_id'] = por_nome.get(item['aluno_nome'])

        audio.nomes_nao_identificados = nao_pareados

        if not pareados:
            raise AudioNaoProcessavel(
                'Nenhuma criança da turma foi reconhecida na fala'
                + (f' (nomes citados: {", ".join(nao_pareados)}).' if nao_pareados else '.'),
                'nenhum_aluno',
            )

        with transaction.atomic():
            criadas = _gravar_observacoes(audio, turma, transcricao, pareados)
            audio.observacao = criadas[0] if criadas else None
            audio.total_observacoes = len(criadas)
            audio.alunos_identificados = [c.aluno_nome for c in criadas]
            audio.status = 'processado'
            audio.data_processamento = timezone.now()
            audio.save()

        logger.info(
            "[GRAVADOR] Áudio %s processado: turma=%s (%s), %d observação(ões)",
            audio.upload_id, turma.nome, audio.turma_resultado, len(criadas),
        )
        return audio

    except AudioNaoProcessavel as exc:
        return _marcar_falha(audio, str(exc), exc.codigo)
    except (ConnectionError, TimeoutError) as exc:
        # Transitório: volta para a fila em vez de queimar o áudio.
        audio.status = 'recebido'
        audio.erro_processamento = f'Serviço indisponível, será tentado de novo: {exc}'
        audio.erro_codigo = 'servico_indisponivel'
        audio.save()
        logger.warning("[GRAVADOR] Áudio %s adiado: %s", audio.upload_id, exc)
        return audio
    except Exception as exc:  # noqa: BLE001 — o worker não pode morrer por um áudio
        logger.exception("[GRAVADOR] Erro inesperado no áudio %s", audio.upload_id)
        return _marcar_falha(audio, f'Erro interno: {exc}', 'erro_interno')


def processar_pendentes(limite: int = 20) -> dict:
    """Processa a fila de áudios `recebido`, do mais antigo para o mais novo."""
    pendentes = list(
        AudioDispositivo.objects
        .filter(status='recebido')
        .select_related('dispositivo', 'professor', 'turma')
        .order_by('data_recebimento')[:limite]
    )

    resumo = {
        'total': len(pendentes), 'processados': 0, 'comandos': 0,
        'falhas': 0, 'adiados': 0,
    }
    for audio in pendentes:
        resultado = processar_audio(audio)
        if resultado.status == 'processado':
            resumo['processados'] += 1
        elif resultado.status == 'comando':
            resumo['comandos'] += 1
        elif resultado.status == 'recebido':
            resumo['adiados'] += 1
        else:
            resumo['falhas'] += 1
    return resumo