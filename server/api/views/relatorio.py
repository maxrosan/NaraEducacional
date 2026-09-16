"""View para geração de relatórios pedagógicos com IA."""

import io
import json
import logging
import secrets
import zipfile
from datetime import date

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.http import HttpResponse, StreamingHttpResponse
from django.utils import timezone

from api.models import Crianca, PeriodoAvaliativo, Relatorio, Turma
from api.services.pdf_renderer import (
    RendererBusy,
    RendererError,
    RendererTimeout,
    RendererUnavailable,
)
from api.services.relatorio import (
    buscar_dados_estudante_para_relatorio,
    deletar_relatorio,
    gerar_relatorio_com_ia,
    obter_periodo_avaliativo_corrente,
    refresh_img_urls_in_html,
)
from api.serializers import RelatorioSerializer
from api.services.relatorio_pdf import (
    build_filename,
    ensure_pdf,
    invalidate_pdf_cache,
)
from api.storage import (
    generate_presigned_url,
    is_s3_configured,
    upload_bytes_to_storage,
)

logger = logging.getLogger(__name__)

# Teto de IDs por request. ZIP cresce linear, então limitamos por memória
# e pelo tempo total antes do timeout do Gunicorn.
_BULK_PDF_MAX_IDS = 100
# TTL do ZIP no S3: curto porque o usuário deve baixar logo após gerar.
_BULK_ZIP_TTL_SECONDS = 24 * 60 * 60


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def gerar_relatorio(request):
    """
    Gerar relatório usando IA baseado nos dados do estudante.
    Requer autenticação.
    """
    crianca_id = None
    try:
        dados = request.data
        crianca_id = dados.get('crianca_id')
        nome_crianca = dados.get('nome_crianca', 'Estudante')
        periodo = dados.get('periodo', {})

        if not crianca_id:
            return Response(
                {'error': 'ID da criança é obrigatório'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        dados_estudante = buscar_dados_estudante_para_relatorio(crianca_id, periodo)
        nome_professora = getattr(request.user, 'nome', '') or 'Professora'
        relatorio_gerado = gerar_relatorio_com_ia(
            nome_crianca, dados_estudante, periodo, crianca_id,
            nome_professora=nome_professora,
            usuario=request.user,
        )

        return Response({
            'success': True,
            'content': relatorio_gerado['content'],
            'period': periodo,
            'generatedAt': timezone.now().isoformat(),
            'suggestions': relatorio_gerado.get('suggestions', []),
            'metadata': relatorio_gerado.get('metadata', {}),
            'capa_template_id': relatorio_gerado.get('capa_template_id'),
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.exception("Erro ao gerar relatório com IA.", extra={"crianca_id": str(crianca_id)})
        return Response(
            {'error': 'Erro ao gerar relatório', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def gerar_relatorio_por_crianca(request, crianca_id):
    """
    Gerar relatório para uma criança usando período avaliativo.
    Aceita periodo_id no body; se ausente, usa o período corrente da instituição.
    """
    try:
        crianca = Crianca.objects.filter(id=crianca_id).first()
        if not crianca:
            return Response(
                {'error': 'Criança não encontrada'},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Resolver período avaliativo
        periodo_id = request.data.get('periodo_id')
        if periodo_id:
            periodo_obj = PeriodoAvaliativo.objects.filter(id=periodo_id).first()
            if not periodo_obj:
                return Response(
                    {'error': 'Período avaliativo não encontrado'},
                    status=status.HTTP_404_NOT_FOUND,
                )
        else:
            periodo_obj = obter_periodo_avaliativo_corrente(crianca.instituicao_id)
            if not periodo_obj:
                return Response(
                    {'error': 'Nenhum período avaliativo encontrado para esta instituição'},
                    status=status.HTTP_404_NOT_FOUND,
                )

        periodo = {
            'type': periodo_obj.tipo_periodo,
            'startDate': str(periodo_obj.data_inicio),
            'endDate': str(periodo_obj.data_fim),
            'descricao': periodo_obj.descricao,
        }

        dados_estudante = buscar_dados_estudante_para_relatorio(crianca_id, periodo)
        nome_professora = getattr(request.user, 'nome', '') or 'Professora'
        relatorio_gerado = gerar_relatorio_com_ia(
            crianca.nome_completo, dados_estudante, periodo, crianca_id,
            nome_professora=nome_professora,
            usuario=request.user,
        )

        return Response({
            'success': True,
            'content': relatorio_gerado['content'],
            'period': periodo,
            'generatedAt': timezone.now().isoformat(),
            'suggestions': relatorio_gerado.get('suggestions', []),
            'metadata': relatorio_gerado.get('metadata', {}),
            'capa_template_id': relatorio_gerado.get('capa_template_id'),
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.exception("Erro ao gerar relatório por criança.", extra={"crianca_id": str(crianca_id)})
        return Response(
            {'error': 'Erro ao gerar relatório', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


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

    relatorio = Relatorio.objects.filter(id=relatorio_id).first()
    if not relatorio:
        logger.warning('Relatório %s não encontrado', relatorio_id)
        return Response(
            {'error': 'Relatório não encontrado'},
            status=status.HTTP_404_NOT_FOUND,
        )

    if hasattr(request.user, 'instituicao_id') and relatorio.instituicao_id:
        if request.user.instituicao_id != relatorio.instituicao_id:
            logger.warning(
                'Permissão negada: user_inst=%s relatorio_inst=%s relatorio=%s',
                request.user.instituicao_id,
                relatorio.instituicao_id,
                relatorio_id,
            )
            return Response(
                {'error': 'Permissão negada para este relatório.'},
                status=status.HTTP_403_FORBIDDEN,
            )

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
    except RendererError as exc:
        logger.exception('Erro ao renderizar PDF do relatório %s', relatorio_id)
        return Response(
            {'error': 'Falha ao gerar PDF.', 'details': str(exc)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception('Erro inesperado ao gerar PDF do relatório %s', relatorio_id)
        return Response(
            {'error': 'Erro ao gerar PDF.', 'details': str(exc)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

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


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def atualizar_relatorio(request, relatorio_id):
    """Atualiza um relatório existente.

    Se `conteudo` ou `template` vierem no payload e forem diferentes do que
    está no banco, o PDF cacheado é invalidado — caso contrário `ensure_pdf`
    devolveria bytes obsoletos no próximo download.
    """
    try:
        relatorio = Relatorio.objects.get(id=relatorio_id)
    except Relatorio.DoesNotExist:
        return Response(
            {'error': 'Relatório não encontrado'},
            status=status.HTTP_404_NOT_FOUND,
        )

    novo_conteudo = request.data.get('conteudo')
    conteudo_mudou = (
        novo_conteudo is not None and novo_conteudo != relatorio.conteudo
    )

    template_mudou = (
        'template' in request.data
        and str(relatorio.template_id or '') != str(request.data.get('template') or '')
    )

    serializer = RelatorioSerializer(relatorio, data=request.data, partial=True)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    try:
        relatorio = serializer.save()
        if conteudo_mudou or template_mudou:
            invalidate_pdf_cache(relatorio)
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "Erro ao atualizar relatório.", extra={"relatorio_id": str(relatorio_id)}
        )
        return Response(
            {'error': 'Erro ao atualizar relatório', 'details': str(exc)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    return Response(
        RelatorioSerializer(relatorio).data, status=status.HTTP_200_OK,
    )

@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def deletar_relatorio_view(request, relatorio_id):
    """
    Deletar relatório e seu PDF do S3.
    """
    try:
        resultado = deletar_relatorio(relatorio_id)
        if not resultado['success']:
            return Response(
                {'error': resultado.get('error', 'Erro ao deletar relatório')},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(resultado, status=status.HTTP_200_OK)
    except Exception as e:
        logger.exception("Erro ao deletar relatório.", extra={"relatorio_id": str(relatorio_id)})
        return Response(
            {'error': 'Erro ao deletar relatório', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


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

    # Preserva a ordem solicitada (depois do fetch, vamos reindexar por ID).
    relatorios_qs = Relatorio.objects.filter(id__in=ids)
    relatorios_by_id = {str(r.id): r for r in relatorios_qs}

    user_inst = getattr(request.user, 'instituicao_id', None)
    missing, forbidden, ordered = [], [], []
    for rid in ids:
        rel = relatorios_by_id.get(str(rid))
        if rel is None:
            missing.append(str(rid))
            continue
        if user_inst and rel.instituicao_id and rel.instituicao_id != user_inst:
            forbidden.append(str(rid))
            continue
        ordered.append(rel)

    if forbidden:
        logger.warning(
            'bulk_pdf_relatorios: acesso negado para %s relatórios (user_inst=%s)',
            len(forbidden), user_inst,
        )
        return Response(
            {'error': 'Permissão negada para um ou mais relatórios.', 'ids': forbidden},
            status=status.HTTP_403_FORBIDDEN,
        )
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
            except Exception as exc:  # noqa: BLE001
                logger.exception('bulk_pdf_relatorios: erro inesperado relatorio=%s', rid)
                failed.append({'id': rid, 'error': str(exc)})
                yield _event({
                    'type': 'progress', 'id': rid,
                    'status': 'error', 'error': str(exc),
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
        except Exception as exc:  # noqa: BLE001
            logger.exception('bulk_pdf_relatorios: falha ao enviar ZIP para S3')
            yield _event({
                'type': 'done', 'download_url': None, 'zip_filename': zip_filename,
                'success_count': success_count, 'fail_count': len(failed),
                'failed': failed,
                'error': f'ZIP gerado mas upload ao S3 falhou: {exc}',
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
    `-data_criacao`) e os filtros (`instituicao_id`, `turma_id`, `status`
    fin/pend) — para escolas com milhares de relatórios não trafegarem a lista
    inteira. Nunca carrega `conteudo`: o flag `finalizado` vem de
    LENGTH(SUBSTRING(conteudo,1,51)) > 50 (mesmo critério das demais listas).

    Aceita também o recorte de tempo da coordenação (`periodo_id`, ou
    `data_inicio`+`data_fim`). Sem ele a lista viria do banco inteiro enquanto
    os cards da mesma tela mostram só o período selecionado — dois números
    contraditórios lado a lado.

    Resposta: `{ count, results: [...] }` com `crianca_nome`/`turma_nome` já
    resolvidos (joins só da página corrente).
    """
    from django.db.models.functions import Length, Substr

    from api.services.coordenacao_cache import RecorteInvalido, resolver_recorte

    instituicao_id = request.GET.get('instituicao_id')
    turma_id = request.GET.get('turma_id')
    status_f = (request.GET.get('status') or 'all').lower()
    ordering = request.GET.get('ordering') or '-data_criacao'

    try:
        limit = max(1, min(int(request.GET.get('limit', 25)), 100))
    except (TypeError, ValueError):
        limit = 25
    try:
        offset = max(0, int(request.GET.get('offset', 0)))
    except (TypeError, ValueError):
        offset = 0

    # Recorte de tempo — mesmo contrato do painel da coordenação.
    def _data(valor):
        return date.fromisoformat(valor) if valor else None

    try:
        recorte = resolver_recorte(
            periodo_id=request.GET.get('periodo_id') or None,
            data_inicio=_data(request.GET.get('data_inicio')),
            data_fim=_data(request.GET.get('data_fim')),
        )
    except (RecorteInvalido, ValueError) as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception:
        return Response(
            {'error': 'Período avaliativo não encontrado.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    qs = Relatorio.objects.annotate(
        conteudo_length=Length(Substr('conteudo', 1, 51))
    ).defer('conteudo')

    if instituicao_id:
        qs = qs.filter(instituicao_id=instituicao_id)

    if recorte:
        qs = qs.filter(
            data_criacao__date__gte=recorte.data_inicio,
            data_criacao__date__lte=recorte.data_fim,
        )

    # Filtro por turma: relatórios das crianças daquela turma.
    if turma_id:
        crianca_ids_turma = list(
            Crianca.objects.filter(turma_id=turma_id).values_list('id', flat=True)
        )
        qs = qs.filter(id_crianca__in=crianca_ids_turma)

    # Filtro por status (finalizado = conteúdo com mais de 50 chars).
    if status_f in ('fin', 'finalizado', 'finalizados'):
        qs = qs.filter(conteudo_length__gt=50)
    elif status_f in ('pend', 'pendente', 'pendentes'):
        qs = qs.filter(conteudo_length__lte=50)

    # Ordenação restrita a campos seguros (evita FieldError de aliases).
    campo = ordering.lstrip('-')
    if campo not in ('data_criacao', 'periodo'):
        ordering = '-data_criacao'
    qs = qs.order_by(ordering, '-data_criacao')

    total = qs.count()
    pagina = list(qs[offset:offset + limit])

    # Enriquecimento só da página corrente (nomes de criança e turma).
    crianca_ids = [r.id_crianca for r in pagina]
    criancas = {
        str(c.id): c
        for c in Crianca.objects.filter(id__in=crianca_ids).only(
            'id', 'nome_completo', 'turma_id'
        )
    }
    turma_ids = {str(c.turma_id) for c in criancas.values() if c.turma_id}
    turmas = {
        str(t.id): t.nome
        for t in Turma.objects.filter(id__in=list(turma_ids)).only('id', 'nome')
    }

    results = []
    for r in pagina:
        c = criancas.get(str(r.id_crianca))
        turma_id_c = str(c.turma_id) if (c and c.turma_id) else None
        results.append({
            'id': str(r.id),
            'id_crianca': str(r.id_crianca),
            'crianca_nome': c.nome_completo if c else None,
            'turma_id': turma_id_c,
            'turma_nome': turmas.get(turma_id_c) if turma_id_c else None,
            'periodo': r.periodo,
            'data_criacao': r.data_criacao.isoformat() if r.data_criacao else None,
            'finalizado': (r.conteudo_length or 0) > 50,
            'revisado_por': str(r.revisado_por) if r.revisado_por else None,
        })

    return Response({'count': total, 'results': results}, status=status.HTTP_200_OK)


@api_view(['GET'])
def detalhe_relatorio(request, relatorio_id):
    """Retorna detalhes de um relatório específico.

    O HTML em `conteudo` pode conter URLs S3 pré-assinadas já expiradas. Antes
    de devolver, re-assinamos o `src` de cada `<img>` que aponta para o bucket
    configurado. Assim o browser consegue carregar as imagens diretamente do
    S3 (uma única conexão TLS reutilizada), evitando o loop antigo de um
    POST `/proxy-imagem/` por imagem no frontend.
    """
    try:
        relatorio = Relatorio.objects.get(id=relatorio_id)
        serializer = RelatorioSerializer(relatorio)
        data = dict(serializer.data)
        conteudo = data.get('conteudo')
        if conteudo:
            data['conteudo'] = refresh_img_urls_in_html(conteudo)
        return Response(data, status=status.HTTP_200_OK)
    except Relatorio.DoesNotExist:
        return Response(
            {'error': 'Relatório não encontrado'},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        logger.exception("Erro ao buscar relatório.", extra={"relatorio_id": str(relatorio_id)})
        return Response(
            {'error': 'Erro ao buscar relatório', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )