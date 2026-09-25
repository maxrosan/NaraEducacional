"""Views REST para o fluxo de Análise de Leitura.

Endpoints (ver ``urls.py``):

* ``GET    /api/leitura/``                       — lista registros confirmados de um aluno
* ``POST   /api/leitura/analisar/``              — inicia a análise
* ``GET    /api/leitura/<id>/status/``           — consulta o status / probabilidades
* ``POST   /api/leitura/<id>/confirmar/``        — confirma a classe escolhida e salva o áudio no S3
* ``DELETE /api/leitura/<id>/``                  — cancela um registro pendente / exclui

Autorização: dono do registro, gestão (``admin``/``coordenador``/superadmin)
ou especialista (``especialista``/``professor_especialista``). Para iniciar uma
análise, quem não é privilegiado precisa estar vinculado à turma do aluno —
mesma regra dos demais registros pedagógicos.
"""

from __future__ import annotations

import logging
from datetime import date

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.escopo import aluno_do_body, buscar_no_escopo, pode_gerenciar
from api.models import Aluno, RegistroLeitura
from api.services import leitura as leitura_service
from api.throttles import UploadRateThrottle

logger = logging.getLogger(__name__)

NIVEIS_ESPECIALISTA = ('especialista', 'professor_especialista')


# ---------------------------------------------------------------------------
# Permissões
# ---------------------------------------------------------------------------

def _privilegiado(user) -> bool:
    """Vê/mexe em registros de leitura de qualquer professor do escopo."""
    return pode_gerenciar(user) or user.nivel in NIVEIS_ESPECIALISTA


def _pode_mexer(registro: RegistroLeitura, user) -> bool:
    return registro.professor_id == user.id or _privilegiado(user)


def _registro_ou_erro(request, registro_id):
    """Retorna (registro, erro): 404 fora do escopo/malformado, 403 sem permissão."""
    registro = buscar_no_escopo(RegistroLeitura, registro_id)
    if registro is None:
        return None, Response({'error': 'Registro não encontrado.'}, status=status.HTTP_404_NOT_FOUND)
    if not _pode_mexer(registro, request.user):
        return None, Response({'error': 'Sem permissão para acessar este registro.'},
                              status=status.HTTP_403_FORBIDDEN)
    return registro, None


# ---------------------------------------------------------------------------
# Serialização
# ---------------------------------------------------------------------------

def _serializar(registro: RegistroLeitura) -> dict:
    return {
        'id': registro.id,
        'status': registro.status,
        'aluno_id': str(registro.aluno_id),
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
        'criado_em': registro.criado_em.isoformat() if registro.criado_em else None,
    }


def _resposta_service(fn, *args, **kwargs):
    """Executa uma operação do service e devolve (registro, erro)."""
    try:
        return fn(*args, **kwargs), None
    except leitura_service.LeituraServiceError as exc:
        return None, Response({'error': str(exc)}, status=exc.http_status)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_registros_leitura(request):
    """Lista registros confirmados de um aluno, opcionalmente filtrados por período.

    Query params: ``aluno_id`` (obrigatório), ``data_inicio`` e ``data_fim`` (YYYY-MM-DD).
    Quem não é privilegiado vê só os registros que ele mesmo gravou.
    """
    aluno_id = request.GET.get('aluno_id')
    if not aluno_id:
        return Response({'error': "Parâmetro 'aluno_id' é obrigatório."}, status=status.HTTP_400_BAD_REQUEST)

    aluno = buscar_no_escopo(Aluno, aluno_id)
    if aluno is None:
        return Response({'error': 'Aluno não encontrado.'}, status=status.HTTP_404_NOT_FOUND)

    data_inicio = request.GET.get('data_inicio') or None
    data_fim = request.GET.get('data_fim') or None
    try:
        for valor in (data_inicio, data_fim):
            if valor:
                date.fromisoformat(valor)
    except ValueError:
        return Response({'error': 'Datas inválidas (use YYYY-MM-DD).'}, status=status.HTTP_400_BAD_REQUEST)

    registros = leitura_service.listar_confirmados(
        aluno_id=aluno.id, data_inicio=data_inicio, data_fim=data_fim,
    )

    if not _privilegiado(request.user):
        ids_visiveis = set(
            RegistroLeitura.objects.filter(aluno=aluno, professor=request.user).values_list('id', flat=True)
        )
        registros = [r for r in registros if r['id'] in ids_visiveis]

    return Response({'registros': registros})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([UploadRateThrottle])
def iniciar_analise_leitura(request):
    """Recebe ``audio`` + ``aluno_id`` (+ opcional ``turma_id``) e enfileira no NaraNN."""
    arquivo = request.FILES.get('audio')
    if not arquivo:
        return Response({'error': "Campo 'audio' é obrigatório."}, status=status.HTTP_400_BAD_REQUEST)

    # Privilegiado (gestão/especialista) grava para qualquer aluno do escopo;
    # professor, só para alunos das turmas em que está vinculado.
    aluno, erro = aluno_do_body(request, campo='aluno_id', exigir_vinculo=not _privilegiado(request.user))
    if erro:
        return erro

    # `turma_id` é legado: a turma do registro é sempre a do aluno. Se vier
    # outra, recusa em vez de gravar um registro inconsistente.
    turma_id = request.data.get('turma_id')
    if turma_id and str(turma_id) != str(aluno.turma_id):
        return Response({'error': 'A turma informada não é a turma do aluno.'},
                        status=status.HTTP_400_BAD_REQUEST)

    registro, erro = _resposta_service(
        leitura_service.iniciar_analise,
        arquivo=arquivo, aluno=aluno, turma=aluno.turma, professor=request.user,
    )
    if erro:
        return erro
    return Response(_serializar(registro), status=status.HTTP_202_ACCEPTED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def status_analise_leitura(request, registro_id):
    """Atualiza o registro consultando o NaraNN e devolve o estado atual."""
    registro, erro = _registro_ou_erro(request, registro_id)
    if erro:
        return erro

    registro, erro = _resposta_service(leitura_service.consultar_status, registro)
    if erro:
        return erro
    return Response(_serializar(registro))


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def confirmar_analise_leitura(request, registro_id):
    """Recebe ``classe_escolhida`` (+ opcional ``anotacoes_professora``) e finaliza o registro."""
    registro, erro = _registro_ou_erro(request, registro_id)
    if erro:
        return erro

    registro, erro = _resposta_service(
        leitura_service.confirmar,
        registro,
        classe_escolhida=request.data.get('classe_escolhida') or '',
        anotacoes=request.data.get('anotacoes_professora') or '',
    )
    if erro:
        return erro
    return Response(_serializar(registro))


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def cancelar_analise_leitura(request, registro_id):
    """Cancela um registro pendente."""
    registro, erro = _registro_ou_erro(request, registro_id)
    if erro:
        return erro

    registro, erro = _resposta_service(leitura_service.cancelar, registro)
    if erro:
        return erro
    return Response(_serializar(registro))


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def deletar_analise_leitura(request, registro_id):
    """Exclui definitivamente um registro de leitura (qualquer status).

    Usado pelo botão de exclusão do bloco "Análises de Leitura" do relatório
    (`ReadingAnalysisBlock`), que lista registros CONFIRMADOS — os quais o
    `cancelar` rejeita. Autorização: mesma regra dos demais endpoints.
    """
    registro, erro = _registro_ou_erro(request, registro_id)
    if erro:
        return erro

    try:
        leitura_service.excluir(registro)
    except Exception:
        logger.exception("Erro ao excluir registro de leitura %s", registro_id)
        return Response({'error': 'Erro ao excluir o registro.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return Response({'success': True})