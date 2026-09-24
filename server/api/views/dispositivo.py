"""Views REST do gravador de áudio (dispositivo físico do relato individual).

Endpoints da plataforma (sessão da professora logada):
  * ``POST   /api/dispositivos/codigo/``        — gera código de pareamento
  * ``GET    /api/dispositivos/``               — lista os dispositivos da professora
  * ``DELETE /api/dispositivos/<id>/revogar/``  — revoga (token para de funcionar)

Endpoints do dispositivo (Bearer token do próprio aparelho):
  * ``POST /api/dispositivos/parear/``              — troca código por token (SEM token)
  * ``POST /api/dispositivos/audio/``               — envia o WAV
  * ``GET  /api/dispositivos/audio/<upload_id>/``   — feedback da gravação (LED/bipe)
  * ``GET  /api/dispositivos/status/``              — sanity check + último áudio

Princípio: o dispositivo envia SÓ o áudio; professora/turma/instituição vêm do
vínculo no banco. Nada de identidade no payload.
"""

from __future__ import annotations

import logging

from rest_framework import status
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
    throttle_classes,
)
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle

from django.db.models import Count

from api.models import AudioDispositivo, DispositivoGravador, Turma, Usuario
from api.services import dispositivo as dispositivo_service
from api.throttles import UploadRateThrottle

logger = logging.getLogger(__name__)


class PareamentoRateThrottle(AnonRateThrottle):
    """Rate-limit do pareamento: é o único endpoint sem token, então precisa
    de freio contra força bruta no código."""

    scope = 'pareamento'


NIVEIS_GESTAO = {'admin', 'coordenador', 'superadmin'}


def _e_gestor(usuario) -> bool:
    return bool(getattr(usuario, 'is_superuser', False)) or getattr(usuario, 'nivel', '') in NIVEIS_GESTAO


def _serializar_dispositivo(d: DispositivoGravador, total_audios=None) -> dict:
    dados = {
        'id': str(d.id),
        'device_id': d.device_id,
        'nome': d.nome,
        'professora_id': str(d.professor_id) if d.professor_id else None,
        'professora_nome': getattr(d.professor, 'nome', ''),
        'turmas': [
            {'id': str(t.id), 'nome': t.nome} for t in d.turmas.all()
        ],
        'turma_ativa_id': str(d.turma_ativa_id) if d.turma_ativa_id else None,
        'turma_ativa_nome': getattr(d.turma_ativa, 'nome', ''),
        'ativo': d.ativo,
        'last_seen': d.visto_ultimo.isoformat() if d.visto_ultimo else None,
        'data_criacao': d.criado_em.isoformat() if d.criado_em else None,
    }
    if total_audios is not None:
        dados['total_audios'] = total_audios
    return dados


def _serializar_audio(a: AudioDispositivo) -> dict:
    """Estado de um áudio, do ponto de vista do gravador.

    `feedback` é o resumo que o firmware consome; os demais campos existem para
    diagnóstico da equipe (logs, suporte) e não precisam ser lidos pelo aparelho.
    """
    return {
        'upload_id': str(a.upload_id),
        'status': a.status,
        'feedback': a.feedback,
        'turma': (
            {'id': str(a.turma_id), 'nome': a.turma.nome} if a.turma_id else None
        ),
        'turma_resultado': a.turma_resultado,
        'turma_anunciada': a.turma_anunciada_texto,
        'alunos_identificados': a.alunos_identificados or [],
        'nomes_nao_identificados': a.nomes_nao_identificados or [],
        'total_observacoes': a.total_observacoes,
        'erro_codigo': a.erro_codigo,
        'data_recebimento': a.data_recebimento.isoformat() if a.data_recebimento else None,
        'data_processamento': (
            a.data_processamento.isoformat() if a.data_processamento else None
        ),
    }


def _token_do_header(request) -> str:
    header = request.META.get('HTTP_AUTHORIZATION', '')
    if header.lower().startswith('bearer '):
        return header[7:].strip()
    return ''


def _erro(exc: dispositivo_service.DispositivoServiceError) -> Response:
    return Response(
        {'error': str(exc), 'codigo': exc.codigo}, status=exc.http_status,
    )


# ---------------------------------------------------------------------------
# Plataforma (professora logada)
# ---------------------------------------------------------------------------

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def gerar_codigo_pareamento(request):
    """Gera um código de pareamento para vincular um gravador.

    Body opcional:
      * ``turma_ids``     — lista de turmas que o aparelho poderá atender (a
        professora troca entre elas por voz durante a gravação);
      * ``professora_id`` — só para **admin/coordenador** (tela de Cadastros),
        que parea dispositivos em nome de uma professora. Para os demais
        perfis, o código é sempre da professora logada.
    """
    turma_ids = request.data.get('turma_ids') or []
    if isinstance(turma_ids, str):
        turma_ids = [turma_ids]
    turmas = list(Turma.objects.filter(id__in=turma_ids)) if turma_ids else []
    if len(turmas) != len(set(str(t) for t in turma_ids)):
        return Response(
            {'error': 'Turma não encontrada.', 'codigo': 'turma_inexistente'},
            status=status.HTTP_404_NOT_FOUND,
        )

    professora = request.user
    professora_id = request.data.get('professora_id')
    if professora_id and str(professora_id) != str(request.user.id):
        if not _e_gestor(request.user):
            return Response(
                {'error': 'Sem permissão para gerar código para outra professora.',
                 'codigo': 'sem_permissao'},
                status=status.HTTP_403_FORBIDDEN,
            )
        professora = Usuario.objects.filter(id=professora_id).first()
        if not professora:
            return Response(
                {'error': 'Professora não encontrada.', 'codigo': 'professora_inexistente'},
                status=status.HTTP_404_NOT_FOUND,
            )
        if dispositivo_service.instituicoes_divergem(
            professora.instituicao_id, request.user.instituicao_id,
        ):
            return Response(
                {'error': 'Professora de outra instituição.', 'codigo': 'outra_instituicao'},
                status=status.HTTP_403_FORBIDDEN,
            )

    try:
        codigo = dispositivo_service.gerar_codigo_pareamento(professora, turmas=turmas)
    except dispositivo_service.DispositivoServiceError as exc:
        return _erro(exc)

    return Response(
        {
            'codigo': codigo.codigo,
            'expira_em': codigo.expira_em.isoformat(),
            'validade_minutos': dispositivo_service.CODIGO_VALIDADE_MINUTOS,
            'turmas': [{'id': str(t.id), 'nome': t.nome} for t in codigo.turmas.all()],
            'professora_id': str(codigo.professor_id),
            'professora_nome': getattr(codigo.professor, 'nome', ''),
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_dispositivos(request):
    """Lista dispositivos.

    * professora → só os dela ("Meus dispositivos");
    * admin/coordenador → todos da instituição (tela de Cadastros), com a
      contagem de áudios recebidos (diagnóstico "o gravador está funcionando?").
    """
    qs = DispositivoGravador.objects.select_related(
        'professor', 'turma_ativa',
    ).prefetch_related('turmas')
    if _e_gestor(request.user):
        # Filtro explícito além do TenantManager: gestor vê só a própria
        # instituição (superadmin sem instituição vê todos).
        if request.user.instituicao_id:
            qs = qs.filter(instituicao_id=request.user.instituicao_id)
    else:
        qs = qs.filter(professor=request.user)

    qs = qs.annotate(_total_audios=Count('audios'))
    return Response({
        'dispositivos': [
            _serializar_dispositivo(d, total_audios=d._total_audios) for d in qs
        ],
    })


def _dispositivo_editavel(request, dispositivo_id):
    """Retorna `(dispositivo, resposta_de_erro)` aplicando a regra de permissão."""
    dispositivo = (
        DispositivoGravador.objects
        .select_related('professor', 'turma_ativa')
        .prefetch_related('turmas')
        .filter(id=dispositivo_id)
        .first()
    )
    if not dispositivo:
        return None, Response(
            {'error': 'Dispositivo não encontrado.'}, status=status.HTTP_404_NOT_FOUND,
        )
    if _e_gestor(request.user):
        if dispositivo_service.instituicoes_divergem(
            dispositivo.instituicao_id, request.user.instituicao_id,
        ):
            return None, Response(
                {'error': 'Dispositivo de outra instituição.'},
                status=status.HTTP_403_FORBIDDEN,
            )
    elif dispositivo.professor_id != request.user.id:
        return None, Response(
            {'error': 'Sem permissão para gerenciar este dispositivo.'},
            status=status.HTTP_403_FORBIDDEN,
        )
    return dispositivo, None


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def atualizar_dispositivo(request, dispositivo_id):
    """Atualiza nome e/ou vínculo (professora, turma) do dispositivo.

    Trocar o vínculo aqui NÃO exige mexer no aparelho: o token continua válido
    e a identidade dos áudios é resolvida no momento do upload. Os áudios já
    recebidos preservam o vínculo antigo (snapshot em `AudioDispositivo`).
    """
    dispositivo, erro = _dispositivo_editavel(request, dispositivo_id)
    if erro:
        return erro

    if 'nome' in request.data:
        dispositivo.nome = (request.data.get('nome') or '').strip()[:120]

    if 'professora_id' in request.data:
        professora = Usuario.objects.filter(id=request.data.get('professora_id')).first()
        if not professora:
            return Response(
                {'error': 'Professora não encontrada.', 'codigo': 'professora_inexistente'},
                status=status.HTTP_404_NOT_FOUND,
            )
        if dispositivo_service.instituicoes_divergem(
            professora.instituicao_id, dispositivo.instituicao_id,
        ):
            return Response(
                {'error': 'Professora de outra instituição.', 'codigo': 'outra_instituicao'},
                status=status.HTTP_403_FORBIDDEN,
            )
        if not professora.escola_id:
            return Response(
                {'error': 'A professora precisa estar vinculada a uma escola.', 'codigo': 'sem_escola'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        dispositivo.professor = professora
        dispositivo.escola_id = professora.escola_id

    novas_turmas = None
    if 'turma_ids' in request.data:
        turma_ids = request.data.get('turma_ids') or []
        if isinstance(turma_ids, str):
            turma_ids = [turma_ids]
        novas_turmas = list(Turma.objects.filter(id__in=turma_ids)) if turma_ids else []
        if len(novas_turmas) != len(set(str(t) for t in turma_ids)):
            return Response(
                {'error': 'Turma não encontrada.', 'codigo': 'turma_inexistente'},
                status=status.HTTP_404_NOT_FOUND,
            )
        for turma in novas_turmas:
            if str(turma.escola_id) != str(dispositivo.escola_id):
                return Response(
                    {'error': 'Turma de outra escola.', 'codigo': 'outra_escola'},
                    status=status.HTTP_403_FORBIDDEN,
                )

    dispositivo.save(update_fields=['nome', 'professor', 'escola', 'atualizado_em'])
    if novas_turmas is not None:
        dispositivo.turmas.set(novas_turmas)
        # Turma ativa fora do novo escopo deixa de valer.
        if dispositivo.turma_ativa_id and all(
            t.id != dispositivo.turma_ativa_id for t in novas_turmas
        ):
            dispositivo.turma_ativa = None
            dispositivo.save(update_fields=['turma_ativa', 'atualizado_em'])

    dispositivo.refresh_from_db()
    logger.info(
        "[DISPOSITIVO] %s atualizado por %s (professora=%s turmas=%s)",
        dispositivo.device_id, request.user.id, dispositivo.professor_id,
        list(dispositivo.turmas.values_list('id', flat=True)),
    )
    return Response({'success': True, 'dispositivo': _serializar_dispositivo(dispositivo)})


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def revogar_dispositivo(request, dispositivo_id):
    """Revoga o dispositivo: o token deixa de funcionar imediatamente."""
    dispositivo, erro = _dispositivo_editavel(request, dispositivo_id)
    if erro:
        return erro

    dispositivo_service.revogar_dispositivo(dispositivo)
    return Response({'success': True, 'dispositivo': _serializar_dispositivo(dispositivo)})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def reativar_dispositivo(request, dispositivo_id):
    """Reativa um dispositivo revogado.

    O token antigo continua inválido (foi regerado ou perdido): o aparelho
    precisa ser pareado de novo — a reativação serve para casos de revogação
    por engano antes de qualquer novo pareamento.
    """
    dispositivo, erro = _dispositivo_editavel(request, dispositivo_id)
    if erro:
        return erro

    dispositivo.ativo = True
    dispositivo.revogado_em = None
    dispositivo.save(update_fields=['ativo', 'revogado_em', 'atualizado_em'])
    return Response({'success': True, 'dispositivo': _serializar_dispositivo(dispositivo)})


# ---------------------------------------------------------------------------
# Dispositivo (firmware)
# ---------------------------------------------------------------------------

@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([PareamentoRateThrottle])
def parear(request):
    """Troca um código de pareamento pelo token permanente do dispositivo.

    Body: ``{"codigo": "A1B2C3", "device_id": "<mac/serial>", "nome": "opcional"}``
    O token claro é devolvido UMA única vez — o firmware precisa persistí-lo.
    """
    try:
        dispositivo, token = dispositivo_service.parear_dispositivo(
            codigo=request.data.get('codigo', ''),
            device_id=(request.data.get('device_id') or '').strip(),
            nome=(request.data.get('nome') or '').strip(),
        )
    except dispositivo_service.DispositivoServiceError as exc:
        return _erro(exc)

    return Response(
        {
            'success': True,
            'token': token,
            'dispositivo': _serializar_dispositivo(dispositivo),
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])  # a autorização real é o token do dispositivo
@throttle_classes([UploadRateThrottle])
def upload_audio_dispositivo(request):
    """Recebe o WAV do gravador e confirma o recebimento.

    Header: ``Authorization: Bearer <token>``
    Multipart: ``arquivo`` (WAV), ``upload_id`` (UUID do firmware),
    ``sha256`` (opcional), ``duracao_seg`` (opcional).

    Responde rápido (o processamento é assíncrono) e é idempotente por
    ``(dispositivo, upload_id)``: retry não duplica relato.
    """
    try:
        dispositivo = dispositivo_service.autenticar_dispositivo(_token_do_header(request))
    except dispositivo_service.DispositivoServiceError as exc:
        return _erro(exc)

    arquivo = request.FILES.get('arquivo')
    if not arquivo:
        return Response(
            {'error': 'Arquivo de áudio é obrigatório.', 'codigo': 'arquivo_ausente'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    duracao = request.data.get('duracao_seg')
    try:
        duracao = int(duracao) if duracao not in (None, '') else None
    except (TypeError, ValueError):
        duracao = None

    try:
        audio, criado = dispositivo_service.registrar_audio(
            dispositivo=dispositivo,
            conteudo=arquivo.read(),
            upload_id=request.data.get('upload_id'),
            sha256_informado=(request.data.get('sha256') or '').strip(),
            duracao_seg=duracao,
        )
    except dispositivo_service.DispositivoServiceError as exc:
        return _erro(exc)
    except Exception:  # noqa: BLE001
        logger.exception("Erro ao registrar áudio do dispositivo %s", dispositivo.device_id)
        return Response(
            {'error': 'Erro interno ao salvar o áudio.', 'codigo': 'erro_interno'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    return Response(
        {
            'recebido': True,
            'duplicado': not criado,
            'audio_id': str(audio.id),
            'upload_id': str(audio.upload_id),
            'sha256': audio.sha256,
            'status': audio.status,
            'data_recebimento': audio.data_recebimento.isoformat(),
        },
        status=status.HTTP_201_CREATED if criado else status.HTTP_200_OK,
    )


@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def consultar_audio(request, upload_id):
    """Feedback de UMA gravação — é assim que a professora sabe o que aconteceu.

    O gravador não tem tela, e turma e crianças só são conhecidas **depois** da
    transcrição. Então o firmware envia o WAV, espera alguns segundos e consulta
    aqui até ``feedback.sinal`` sair de ``aguardando``:

      * ``ok``         → LED verde / bipe curto;
      * ``atencao``    → LED amarelo / dois bipes (entrou, mas incompleto:
        turma não autorizada, turma indefinida ou nome não reconhecido);
      * ``erro``       → LED vermelho.

    ``feedback.mensagem`` é texto pronto em português, caso o aparelho ganhe
    display ou alto-falante depois. Nenhum outro campo precisa ser interpretado.
    """
    try:
        dispositivo = dispositivo_service.autenticar_dispositivo(_token_do_header(request))
    except dispositivo_service.DispositivoServiceError as exc:
        return _erro(exc)

    audio = (
        AudioDispositivo.objects
        .select_related('turma')
        .filter(dispositivo=dispositivo, upload_id=upload_id)
        .first()
    )
    if not audio:
        return Response(
            {'error': 'Áudio não encontrado para este dispositivo.',
             'codigo': 'audio_inexistente'},
            status=status.HTTP_404_NOT_FOUND,
        )

    return Response(_serializar_audio(audio))


@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def status_dispositivo(request):
    """Sanity check do firmware: confirma que o token vale e devolve o vínculo.

    Inclui `ultimo_audio` para o aparelho conseguir dar retorno com **uma única
    chamada** quando não guardou o `upload_id` (ex.: reboot no meio do envio).
    """
    try:
        dispositivo = dispositivo_service.autenticar_dispositivo(_token_do_header(request))
    except dispositivo_service.DispositivoServiceError as exc:
        return _erro(exc)

    ultimo = (
        AudioDispositivo.objects
        .select_related('turma')
        .filter(dispositivo=dispositivo)
        .order_by('-data_recebimento')
        .first()
    )
    return Response({
        'ok': True,
        'dispositivo': _serializar_dispositivo(dispositivo),
        'ultimo_audio': _serializar_audio(ultimo) if ultimo else None,
    })