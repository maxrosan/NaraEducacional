"""Views de relatório pedagógico: geração com IA, PDF (unitário e em lote) e
a lista paginada da coordenação.

O CRUD de `Relatorio` (detalhe, edição, revisão, exclusão) fica em
`views/avaliacao.py`. A invalidação do PDF ao editar e a remoção do PDF ao
excluir são feitas pelos signals (`api/signals.py`), para qualquer caminho.
"""

import io
import json
import logging
import secrets
import uuid
import zipfile

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.db.models.functions import Length, Substr
from django.http import HttpResponse, StreamingHttpResponse
from django.utils import timezone

from api.escopo import aluno_com_vinculo, buscar_no_escopo, resolver_escola_painel
from api.models import Aluno, PeriodoAvaliativo, Relatorio
from api.services.pdf_renderer import (
    RendererBusy,
    RendererError,
    RendererTimeout,
    RendererUnavailable,
)
from api.services.relatorio import (
    buscar_dados_estudante_para_relatorio,
    gerar_relatorio_com_ia,
    obter_periodo_avaliativo_corrente,
)
from api.services.relatorio_pdf import build_filename, ensure_pdf
from api.storage import (
    generate_presigned_url,
    is_s3_configured,
    upload_bytes_to_storage,
)
from api.views.coordenacao_cache import recorte_da_requisicao

logger = logging.getLogger(__name__)

# Teto de IDs por request. ZIP cresce linear, então limitamos por memória
# e pelo tempo total antes do timeout do Gunicorn.
_BULK_PDF_MAX_IDS = 100
# TTL do ZIP no S3: curto porque o usuário deve baixar logo após gerar.
_BULK_ZIP_TTL_SECONDS = 24 * 60 * 60


def _erro(mensagem, codigo=status.HTTP_400_BAD_REQUEST):
    return Response({'error': mensagem}, status=codigo)


def _resposta_relatorio_gerado(relatorio_gerado, periodo):
    return Response({
        'success': True,
        'content': relatorio_gerado['content'],
        'period': periodo,
        'generatedAt': timezone.now().isoformat(),
        'suggestions': relatorio_gerado.get('suggestions', []),
        'metadata': relatorio_gerado.get('metadata', {}),
        'capa_template_id': relatorio_gerado.get('capa_template_id'),
    }, status=status.HTTP_200_OK)


def _gerar(request, aluno, periodo):
    """Busca os dados do aluno e chama a IA. Mesma lógica para os dois endpoints."""
    dados_estudante = buscar_dados_estudante_para_relatorio(str(aluno.id), periodo)
    nome_professora = getattr(request.user, 'nome', '') or 'Professora'
    return gerar_relatorio_com_ia(
        aluno.nome_completo, dados_estudante, periodo, str(aluno.id),
        nome_professora=nome_professora,
        usuario=request.user,
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def gerar_relatorio(request):
    """
    Gerar relatório usando IA baseado nos dados do estudante.
    Body: {crianca_id, periodo}. Gestão, ou professor vinculado à turma do aluno.
    O nome usado é sempre o do cadastro (`nome_crianca` do body é ignorado).
    """
    crianca_id = request.data.get('crianca_id')
    periodo = request.data.get('periodo', {})
    if not crianca_id:
        return _erro('ID da criança é obrigatório')

    aluno, erro = aluno_com_vinculo(request.user, crianca_id)
    if erro:
        return erro

    try:
        return _resposta_relatorio_gerado(_gerar(request, aluno, periodo), periodo)
    except Exception:
        logger.exception("Erro ao gerar relatório com IA.", extra={"crianca_id": str(crianca_id)})
        return _erro('Erro ao gerar relatório', status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def gerar_relatorio_por_crianca(request, crianca_id):
    """
    Gerar relatório para uma criança usando período avaliativo.
    Aceita periodo_id no body (período da ESCOLA do aluno); se ausente, usa o
    período corrente.
    """
    aluno, erro = aluno_com_vinculo(request.user, crianca_id)
    if erro:
        return erro

    periodo_id = request.data.get('periodo_id')
    if periodo_id:
        periodo_obj = buscar_no_escopo(PeriodoAvaliativo, periodo_id)
        if periodo_obj is None or periodo_obj.escola_id != aluno.escola_id:
            return _erro('Período avaliativo não encontrado', status.HTTP_404_NOT_FOUND)
    else:
        periodo_obj = obter_periodo_avaliativo_corrente(aluno.instituicao_id, aluno.escola_id)
        if not periodo_obj:
            return _erro('Nenhum período avaliativo encontrado para esta escola', status.HTTP_404_NOT_FOUND)

    periodo = {
        'type': periodo_obj.tipo_periodo,
        'startDate': str(periodo_obj.data_inicio),
        'endDate': str(periodo_obj.data_fim),
        'descricao': periodo_obj.descricao,
    }

    try:
        return _resposta_relatorio_gerado(_gerar(request, aluno, periodo), periodo)
    except Exception:
        logger.exception("Erro ao gerar relatório por criança.", extra={"crianca_id": str(crianca_id)})
        return _erro('Erro ao gerar relatório', status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def baixar_pdf_relatorio(request, relatorio_id):
    """Devolve o PDF do relatório, renderizando via report_generator se necessário.

    Se o PDF já estiver cacheado no S3 (via `pdf_storage_key`), devolve os bytes
    daquele objeto. Caso contrário, renderiza, faz upload no S3 e devolve os bytes.
    """
    import time as _time
    t0 = _time.monotonic()
    user_id = getattr(request.user, 'id', None)
    logger.info(
        'baixar_pdf_relatorio solicitado: relatorio=%s user=%s',
        relatorio_id,
        user_id,
    )

    # TenantManager: fora do escopo = inexistente. (A checagem manual de
    # instituição que existia aqui barrava o superadmin, que não tem uma.)
    relatorio = buscar_no_escopo(Relatorio, relatorio_id)
    if relatorio is None:
        logger.warning('Relatório %s não encontrado', relatorio_id)
        return _erro('Relatório não encontrado', status.HTTP_404_NOT_FOUND)

    try:
        pdf_bytes, cached, _presigned = ensure_pdf(relatorio)
    except RendererBusy:
        logger.warning('Renderer BUSY (503) para relatorio=%s', relatorio_id)
        return Response(
            {'error': 'Serviço de geração de PDF ocupado. Tente novamente em instantes.'},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    except RendererTimeout:
        logger.warning('Renderer TIMEOUT (504) para relatorio=%s', relatorio_id)
        return Response(
            {'error': 'Tempo limite atingido ao gerar o PDF.'},
            status=status.HTTP_504_GATEWAY_TIMEOUT,
        )
    except RendererUnavailable:
        logger.warning('Renderer UNAVAILABLE (502) para relatorio=%s', relatorio_id)
        return Response(
            {'error': 'Serviço de geração de PDF indisponível.'},
            status=status.HTTP_502_BAD_GATEWAY,
        )
    except RendererError:
        logger.exception('Erro ao renderizar PDF do relatório %s', relatorio_id)
        return _erro('Falha ao gerar PDF.', status.HTTP_500_INTERNAL_SERVER_ERROR)
    except Exception:  # noqa: BLE001
        logger.exception('Erro inesperado ao gerar PDF do relatório %s', relatorio_id)
        return _erro('Erro ao gerar PDF.', status.HTTP_500_INTERNAL_SERVER_ERROR)

    filename = build_filename(relatorio)
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    response['X-Pdf-Cached'] = 'true' if cached else 'false'
    logger.info(
        'baixar_pdf_relatorio concluído: relatorio=%s cached=%s filename=%s bytes=%s total=%.0f ms',
        relatorio_id,
        cached,
        filename,
        len(pdf_bytes),
        (_time.monotonic() - t0) * 1000,
    )
    return response


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def bulk_pdf_relatorios(request):
    """Gera PDFs de múltiplos relatórios, empacota em ZIP no S3 e devolve a URL.

    Resposta: stream NDJSON (application/x-ndjson). Cada linha é um JSON:
      {"type":"progress","id":"<uuid>","status":"generating"}
      {"type":"progress","id":"<uuid>","status":"ready","filename":"..."}
      {"type":"progress","id":"<uuid>","status":"error","error":"..."}
      {"type":"done","download_url":"<presigned>","zip_filename":"...",
       "success_count":N,"fail_count":M,"failed":[{"id":"...","error":"..."}]}

    Sequencial (um PDF por vez) para manter a ordem dos eventos previsível.
    Progresso pode ser trocado por paralelismo futuramente (ThreadPool +
    queue.Queue), mas hoje o cache do S3 torna lote aquecido quase instantâneo.
    """
    if not is_s3_configured():
        return Response(
            {'error': 'Download em lote requer S3 configurado.'},
            status=status.HTTP_501_NOT_IMPLEMENTED,
        )

    ids = request.data.get('ids') or []
    if not isinstance(ids, list) or not ids:
        return Response(
            {'error': 'Envie um array não vazio em "ids".'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if len(ids) > _BULK_PDF_MAX_IDS:
        return Response(
            {'error': f'Máximo de {_BULK_PDF_MAX_IDS} relatórios por lote.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # UUID malformado quebraria o filter(id__in=...) inteiro (500): vira "não encontrado".
    ids_validos = []
    for rid in ids:
        try:
            ids_validos.append(str(uuid.UUID(str(rid))))
        except (ValueError, TypeError, AttributeError):
            pass

    # TenantManager: relatório fora do escopo do usuário = não encontrado.
    # Preserva a ordem solicitada (depois do fetch, reindexa por ID).
    relatorios_by_id = {str(r.id): r for r in Relatorio.objects.filter(id__in=ids_validos)}

    missing, ordered = [], []
    for rid in ids:
        rel = relatorios_by_id.get(str(rid))
        if rel is None:
            missing.append(str(rid))
        else:
            ordered.append(rel)

    if not ordered:
        return Response(
            {'error': 'Nenhum relatório válido encontrado.', 'ids': missing},
            status=status.HTTP_404_NOT_FOUND,
        )

    user_id = getattr(request.user, 'id', None)
    logger.info(
        'bulk_pdf_relatorios iniciado: total=%s missing=%s user=%s',
        len(ordered), len(missing), user_id,
    )

    def _event(payload: dict) -> bytes:
        return (json.dumps(payload, ensure_ascii=False) + '\n').encode('utf-8')

    def stream():
        import time as _time
        t0 = _time.monotonic()
        zip_buf = io.BytesIO()
        # ZIP_STORED: PDFs já são praticamente incompressíveis; evita o custo
        # de CPU do DEFLATE sem inchar significativamente o arquivo final.
        zf = zipfile.ZipFile(zip_buf, mode='w', compression=zipfile.ZIP_STORED)
        used_filenames: set[str] = set()
        failed: list[dict] = []
        success_count = 0

        # Reporta relatórios inexistentes como falha logo no início para
        # o cliente mostrar na lista.
        for rid in missing:
            failed.append({'id': rid, 'error': 'Relatório não encontrado.'})
            yield _event({
                'type': 'progress', 'id': rid,
                'status': 'error', 'error': 'Relatório não encontrado.',
            })

        for rel in ordered:
            rid = str(rel.id)
            yield _event({'type': 'progress', 'id': rid, 'status': 'generating'})
            try:
                pdf_bytes, cached, _url = ensure_pdf(rel)
                filename = build_filename(rel)
                # build_filename já tem sufixo aleatório, mas guardamos por
                # precaução contra colisões inesperadas no ZIP.
                if filename in used_filenames:
                    stem, ext = filename.rsplit('.', 1) if '.' in filename else (filename, 'pdf')
                    filename = f'{stem}_{secrets.token_hex(2)}.{ext}'
                used_filenames.add(filename)
                zf.writestr(filename, pdf_bytes)
                success_count += 1
                logger.info(
                    'bulk_pdf_relatorios: relatorio=%s cached=%s bytes=%s filename=%s',
                    rid, cached, len(pdf_bytes), filename,
                )
                yield _event({
                    'type': 'progress', 'id': rid,
                    'status': 'ready', 'filename': filename, 'cached': cached,
                })
            except (RendererBusy, RendererTimeout, RendererUnavailable, RendererError) as exc:
                logger.warning('bulk_pdf_relatorios: falha do renderer relatorio=%s: %s', rid, exc)
                failed.append({'id': rid, 'error': str(exc) or exc.__class__.__name__})
                yield _event({
                    'type': 'progress', 'id': rid,
                    'status': 'error', 'error': str(exc) or exc.__class__.__name__,
                })
            except Exception:  # noqa: BLE001
                logger.exception('bulk_pdf_relatorios: erro inesperado relatorio=%s', rid)
                failed.append({'id': rid, 'error': 'Erro ao gerar PDF.'})
                yield _event({
                    'type': 'progress', 'id': rid,
                    'status': 'error', 'error': 'Erro ao gerar PDF.',
                })

        # Fechamento do ZIP + materialização dos bytes podem levar segundos
        # para lotes grandes. Avisa o cliente que saiu do loop por-relatório.
        yield _event({'type': 'zipping', 'file_count': success_count})
        zf.close()
        zip_bytes = zip_buf.getvalue()

        if success_count == 0:
            # Não gasta S3 quando não há nada para entregar.
            logger.info('bulk_pdf_relatorios: nenhum PDF gerado, pulando upload do ZIP.')
            yield _event({
                'type': 'done', 'download_url': None, 'zip_filename': None,
                'success_count': 0, 'fail_count': len(failed), 'failed': failed,
            })
            return

        timestamp = timezone.now().strftime('%Y%m%d-%H%M%S')
        token = secrets.token_hex(4)
        zip_filename = f'relatorios_{timestamp}.zip'
        zip_key = f'relatorios-bulk/{timestamp}-{token}.zip'
        # Upload ao S3 é a parte mais demorada depois do loop; sinaliza antes
        # de bloquear para o cliente mostrar "Enviando ZIP…".
        yield _event({
            'type': 'uploading',
            'file_count': success_count,
            'size_bytes': len(zip_bytes),
        })
        try:
            _stored_key, presigned = upload_bytes_to_storage(
                zip_key, zip_bytes, content_type='application/zip',
            )
            # Ajusta o TTL do presigned para 24h (o default do storage é 1h).
            long_lived = generate_presigned_url(_stored_key, _BULK_ZIP_TTL_SECONDS)
            download_url = long_lived or presigned
        except Exception:  # noqa: BLE001
            logger.exception('bulk_pdf_relatorios: falha ao enviar ZIP para S3')
            yield _event({
                'type': 'done', 'download_url': None, 'zip_filename': zip_filename,
                'success_count': success_count, 'fail_count': len(failed),
                'failed': failed,
                'error': 'ZIP gerado, mas o envio para o armazenamento falhou.',
            })
            return

        logger.info(
            'bulk_pdf_relatorios concluído: ok=%s fail=%s zip=%s bytes=%s total=%.0f ms',
            success_count, len(failed), zip_key, len(zip_bytes),
            (_time.monotonic() - t0) * 1000,
        )
        yield _event({
            'type': 'done',
            'download_url': download_url,
            'zip_filename': zip_filename,
            'success_count': success_count,
            'fail_count': len(failed),
            'failed': failed,
        })

    response = StreamingHttpResponse(stream(), content_type='application/x-ndjson')
    # Nginx/proxies reversos bufferizam streamings por padrão; este header
    # pede para repassar os chunks imediatamente ao cliente.
    response['X-Accel-Buffering'] = 'no'
    response['Cache-Control'] = 'no-cache'
    return response


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_relatorios_coordenacao(request):
    """Lista PAGINADA de relatórios para a coordenação (lazy loading).

    Faz a paginação no servidor (limit/offset), a ordenação (por padrão
    `-criado_em`) e os filtros (`turma_id`, `status` fin/pend) — para escolas
    com milhares de relatórios não trafegarem a lista inteira. Nunca carrega
    `conteudo`: o flag `finalizado` vem de LENGTH(SUBSTRING(conteudo,1,51)) > 50
    (mesmo critério das demais listas).

    Escola e recorte de tempo seguem o MESMO contrato das demais telas da
    coordenação (`escopo.resolver_escola_painel` e
    `views.coordenacao_cache.recorte_da_requisicao`): coordenador vê a própria
    escola; admin/superadmin informam `?escola_id=`; recorte por `periodo_id`
    ou `data_inicio`+`data_fim` (default: período vigente). Sem isso a lista
    viria do banco inteiro enquanto os cards da mesma tela mostram só o
    período selecionado.

    Resposta: `{ count, results: [...] }` com `crianca_nome`/`turma_nome` já
    resolvidos (joins só da página corrente).
    """
    escola_id, erro = resolver_escola_painel(request)
    if erro:
        return erro

    recorte, erro = recorte_da_requisicao(request, escola_id)
    if erro:
        return erro

    turma_id = request.GET.get('turma_id')
    status_f = (request.GET.get('status') or 'all').lower()
    # `data_criacao` é o nome antigo, aceito por compatibilidade com o frontend.
    ordering = (request.GET.get('ordering') or '-criado_em').replace('data_criacao', 'criado_em')

    try:
        limit = max(1, min(int(request.GET.get('limit', 25)), 100))
    except (TypeError, ValueError):
        limit = 25
    try:
        offset = max(0, int(request.GET.get('offset', 0)))
    except (TypeError, ValueError):
        offset = 0

    qs = Relatorio.objects.annotate(
        conteudo_length=Length(Substr('conteudo', 1, 51))
    ).defer('conteudo').filter(escola_id=escola_id)

    if recorte:
        qs = qs.filter(
            criado_em__date__gte=recorte.data_inicio,
            criado_em__date__lte=recorte.data_fim,
        )

    # Filtro por turma: relatórios dos alunos daquela turma.
    if turma_id:
        try:
            qs = qs.filter(aluno__turma_id=uuid.UUID(str(turma_id)))
        except ValueError:
            qs = qs.none()

    # Filtro por status (finalizado = conteúdo com mais de 50 chars).
    if status_f in ('fin', 'finalizado', 'finalizados'):
        qs = qs.filter(conteudo_length__gt=50)
    elif status_f in ('pend', 'pendente', 'pendentes'):
        qs = qs.filter(conteudo_length__lte=50)

    # Ordenação restrita a campos seguros (evita FieldError de aliases).
    campo = ordering.lstrip('-')
    if campo not in ('criado_em', 'periodo'):
        ordering = '-criado_em'
    qs = qs.order_by(ordering, '-criado_em')

    total = qs.count()
    pagina = list(qs.select_related('revisado_por')[offset:offset + limit])

    # Enriquecimento só da página corrente (nomes de aluno e turma).
    alunos = {
        str(a.id): a
        for a in Aluno.objects.filter(id__in=[r.aluno_id for r in pagina])
        .select_related('turma').only('id', 'nome_completo', 'turma_id', 'turma__nome')
    }

    results = []
    for r in pagina:
        a = alunos.get(str(r.aluno_id))
        turma = a.turma if (a and a.turma_id) else None
        results.append({
            'id': str(r.id),
            # Chaves antigas mantidas para o frontend (id_crianca/crianca_nome/data_criacao).
            'id_crianca': str(r.aluno_id),
            'crianca_nome': a.nome_completo if a else None,
            'turma_id': str(turma.id) if turma else None,
            'turma_nome': turma.nome if turma else None,
            'periodo': r.periodo,
            'data_criacao': r.criado_em.isoformat() if r.criado_em else None,
            'finalizado': (r.conteudo_length or 0) > 50,
            'revisado_por': str(r.revisado_por) if r.revisado_por_id else None,
        })

    return Response({'count': total, 'results': results}, status=status.HTTP_200_OK)