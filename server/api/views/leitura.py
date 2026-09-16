"""Views REST para o fluxo de Análise de Leitura.

Quatro endpoints (ver ``urls.py``):

* ``POST  /api/leitura/analisar/``               — inicia a análise
* ``GET   /api/leitura/<id>/status/``            — consulta o status / probabilidades
* ``POST  /api/leitura/<id>/confirmar/``         — confirma a classe escolhida e salva o áudio no S3
* ``DELETE /api/leitura/<id>/``                  — cancela um registro pendente

Autorização: dono do registro, ``admin``, ``coordenador`` ou
``especialista``/``professor_especialista``.
"""

from __future__ import annotations

import logging

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.models import Crianca, RegistroLeitura, Turma
from api.services import leitura as leitura_service
from api.throttles import UploadRateThrottle

logger = logging.getLogger(__name__)


_PERFIS_PRIVILEGIADOS = {'admin', 'coordenador', 'especialista', 'professor_especialista'}


def _pode_ver(registro: RegistroLeitura, usuario) -> bool:
    if not usuario or not usuario.is_authenticated:
        return False
    if registro.professor_id == usuario.id:
        return True
    return getattr(usuario, 'perfil', '') in _PERFIS_PRIVILEGIADOS


def _serializar(registro: RegistroLeitura) -> dict:
    return {
        'id': registro.id,
        'status': registro.status,
        'crianca_id': str(registro.crianca_id),
        'turma_id': str(registro.turma_id) if registro.turma_id else None,
        'nara_job_id': registro.nara_job_id or None,
        'classe_predita': registro.classe_predita or None,
        'classe_escolhida': registro.classe_escolhida or None,
        'probabilidades': registro.probabilidades or {},
        'duracao_seg': registro.duracao_seg,
        'pieces': registro.pieces,
        'feat_dim': registro.feat_dim,
        'arquivo_path': registro.arquivo_path or None,
        'anotacoes_professora': registro.anotacoes_professora,
        'data_criacao': registro.data_criacao.isoformat() if registro.data_criacao else None,
    }


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_registros_leitura(request):
    """Lista registros confirmados de uma criança, opcionalmente filtrados por período.

    Query params: ``crianca_id`` (obrigatório), ``data_inicio`` e ``data_fim`` (YYYY-MM-DD).
    Permissão: dono dos registros, ``admin``, ``coordenador`` ou especialista.
    """
    crianca_id = request.GET.get('crianca_id') or request.GET.get('criancaId')
    if not crianca_id:
        return Response({'error': "Parâmetro 'crianca_id' é obrigatório."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        Crianca.objects.get(id=crianca_id)
    except (Crianca.DoesNotExist, ValueError):
        return Response({'error': 'Criança não encontrada.'}, status=status.HTTP_404_NOT_FOUND)

    # Filtro de visibilidade: professor só vê os próprios; perfis privilegiados veem tudo.
    perfil = getattr(request.user, 'perfil', '')
    apenas_proprios = perfil not in _PERFIS_PRIVILEGIADOS

    registros = leitura_service.listar_confirmados(
        crianca_id=crianca_id,
        data_inicio=request.GET.get('data_inicio') or None,
        data_fim=request.GET.get('data_fim') or None,
    )

    if apenas_proprios:
        ids_visiveis = set(
            RegistroLeitura.objects.filter(
                crianca_id=crianca_id,
                professor_id=request.user.id,
            ).values_list('id', flat=True)
        )
        registros = [r for r in registros if r['id'] in ids_visiveis]

    return Response({'registros': registros})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([UploadRateThrottle])
def iniciar_analise_leitura(request):
    """Recebe ``audio`` + ``crianca_id`` (+ opcional ``turma_id``) e enfileira no NaraNN."""
    arquivo = request.FILES.get('audio')
    if not arquivo:
        return Response({'error': "Campo 'audio' é obrigatório."}, status=status.HTTP_400_BAD_REQUEST)

    crianca_id = request.POST.get('crianca_id') or request.POST.get('criancaId')
    if not crianca_id:
        return Response({'error': "Campo 'crianca_id' é obrigatório."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        crianca = Crianca.objects.get(id=crianca_id)
    except (Crianca.DoesNotExist, ValueError):
        return Response({'error': 'Criança não encontrada.'}, status=status.HTTP_404_NOT_FOUND)

    turma = None
    turma_id = request.POST.get('turma_id') or request.POST.get('turmaId')
    if turma_id:
        try:
            turma = Turma.objects.get(id=turma_id)
        except (Turma.DoesNotExist, ValueError):
            turma = None

    try:
        registro = leitura_service.iniciar_analise(
            arquivo=arquivo,
            crianca=crianca,
            turma=turma,
            professor=request.user,
        )
    except leitura_service.LeituraServiceError as exc:
        return Response({'error': str(exc)}, status=exc.http_status)

    return Response(_serializar(registro), status=status.HTTP_202_ACCEPTED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def status_analise_leitura(request, registro_id: int):
    """Atualiza o registro consultando o NaraNN e devolve o estado atual."""
    try:
        registro = RegistroLeitura.objects.get(id=registro_id)
    except RegistroLeitura.DoesNotExist:
        return Response({'error': 'Registro não encontrado.'}, status=status.HTTP_404_NOT_FOUND)

    if not _pode_ver(registro, request.user):
        return Response({'error': 'Sem permissão para acessar este registro.'}, status=status.HTTP_403_FORBIDDEN)

    try:
        registro = leitura_service.consultar_status(registro)
    except leitura_service.LeituraServiceError as exc:
        return Response({'error': str(exc)}, status=exc.http_status)

    return Response(_serializar(registro))


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def confirmar_analise_leitura(request, registro_id: int):
    """Recebe ``classe_escolhida`` (+ opcional ``anotacoes_professora``) e finaliza o registro."""
    try:
        registro = RegistroLeitura.objects.get(id=registro_id)
    except RegistroLeitura.DoesNotExist:
        return Response({'error': 'Registro não encontrado.'}, status=status.HTTP_404_NOT_FOUND)

    if not _pode_ver(registro, request.user):
        return Response({'error': 'Sem permissão para acessar este registro.'}, status=status.HTTP_403_FORBIDDEN)

    payload = request.data or {}
    classe_escolhida = payload.get('classe_escolhida') or payload.get('classeEscolhida') or ''
    anotacoes = payload.get('anotacoes_professora') or payload.get('anotacoesProfessora') or ''

    try:
        registro = leitura_service.confirmar(
            registro,
            classe_escolhida=classe_escolhida,
            anotacoes=anotacoes,
        )
    except leitura_service.LeituraServiceError as exc:
        return Response({'error': str(exc)}, status=exc.http_status)

    return Response(_serializar(registro))


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def cancelar_analise_leitura(request, registro_id: int):
    """Cancela um registro pendente."""
    try:
        registro = RegistroLeitura.objects.get(id=registro_id)
    except RegistroLeitura.DoesNotExist:
        return Response({'error': 'Registro não encontrado.'}, status=status.HTTP_404_NOT_FOUND)

    if not _pode_ver(registro, request.user):
        return Response({'error': 'Sem permissão para acessar este registro.'}, status=status.HTTP_403_FORBIDDEN)

    try:
        registro = leitura_service.cancelar(registro)
    except leitura_service.LeituraServiceError as exc:
        return Response({'error': str(exc)}, status=exc.http_status)

    return Response(_serializar(registro))


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def deletar_analise_leitura(request, registro_id: int):
    """Exclui definitivamente um registro de leitura (qualquer status).

    Usado pelo botão de exclusão do bloco "Análises de Leitura" do relatório
    (`ReadingAnalysisBlock`), que lista registros CONFIRMADOS — os quais o
    `cancelar` rejeita. Autorização: mesma regra dos demais endpoints
    (`_pode_ver`: dono do registro ou perfil privilegiado).
    """
    try:
        registro = RegistroLeitura.objects.get(id=registro_id)
    except RegistroLeitura.DoesNotExist:
        return Response({'error': 'Registro não encontrado.'}, status=status.HTTP_404_NOT_FOUND)

    if not _pode_ver(registro, request.user):
        return Response({'error': 'Sem permissão para acessar este registro.'}, status=status.HTTP_403_FORBIDDEN)

    try:
        leitura_service.excluir(registro)
    except Exception:
        logger.exception("Erro ao excluir registro de leitura %s", registro_id)
        return Response({'error': 'Erro ao excluir o registro.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return Response({'success': True})