"""Views para upload e análise de produções infantis (escrita e desenho).

Único caminho de criação de RegistroEscrita/RegistroDesenho (as rotas REST
genéricas de criação foram removidas): aqui o arquivo é validado, enviado ao
storage, analisado pela IA e o registro é gravado com os campos `arquivo_*`
— que no serializer são read-only.

Permissão: gestão, ou professor vinculado à turma do aluno (mesma regra dos
demais registros pedagógicos). Revisar a classificação: gestão ou o autor.
"""

import base64
import io
import logging

from PIL import Image, ImageOps

from django.http import Http404, HttpResponse
from django.shortcuts import redirect
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.escopo import aluno_do_body, cliente_id_do_usuario, dono_ou_gestao
from api.ia_utils import (
    ALLOWED_IMAGE_EXTENSIONS,
    ALLOWED_IMAGE_MIME_TYPES,
    MAX_IMAGE_SIZE_BYTES,
    gerar_nome_arquivo_seguro,
    validate_uploaded_file,
)
from api.models import RegistroDesenho, RegistroEscrita
from api.services.analise_producao import (
    analisar_desenho,
    analisar_escrita,
    atualizar_classificacao_registro,
    idade_do_aluno,
    salvar_registro_desenho,
    salvar_registro_escrita,
)
from api.services.fases_producao import FASES_DESENHO, FASES_ESCRITA, NAO_CLASSIFICAVEL
from api.storage import (
    delete_from_storage,
    download_bytes_from_storage,
    generate_presigned_url,
    is_s3_configured,
    upload_bytes_to_storage,
)
from api.throttles import UploadRateThrottle

logger = logging.getLogger(__name__)

_MODELS_POR_TIPO = {'escrita': RegistroEscrita, 'desenho': RegistroDesenho}


def _erro(mensagem: str, status_code: int, **extra) -> Response:
    return Response({'error': mensagem}, status=status_code, **extra)


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------

def _preparar_upload(request, tipo: str):
    """Validações comuns a escrita e desenho + envio do arquivo ao storage.

    Retorna ``(contexto, None)`` ou ``(None, Response)``. ``contexto`` traz:
    arquivo, file_bytes, aluno, turma, arquivo_nome, file_hash, arquivo_path.

    O rate limit é o `UploadRateThrottle` dos endpoints (DRF) — não há um
    segundo contador aqui.
    """
    arquivo = request.FILES.get('arquivo')
    if arquivo is None:
        return None, _erro('Nenhum arquivo foi enviado', status.HTTP_400_BAD_REQUEST)

    validation_error = validate_uploaded_file(
        arquivo, ALLOWED_IMAGE_MIME_TYPES, ALLOWED_IMAGE_EXTENSIONS,
        MAX_IMAGE_SIZE_BYTES, f"imagem de {tipo}",
    )
    if validation_error:
        mensagem, status_code = validation_error
        return None, _erro(mensagem, status_code)

    aluno, erro = aluno_do_body(request, campo='alunoId')
    if erro:
        return None, erro

    # A turma do registro é sempre a do aluno (mesma regra da leitura).
    turma_id = request.data.get('turmaId')
    if turma_id and str(turma_id) != str(aluno.turma_id):
        return None, _erro('A turma informada não é a turma do aluno.', status.HTTP_400_BAD_REQUEST)

    arquivo_nome, file_hash = gerar_nome_arquivo_seguro(aluno.nome_completo, arquivo.name)
    file_bytes = arquivo.read()

    # Falha no storage = falha da requisição. Não há mais fallback para o
    # disco do container (efêmero: o arquivo sumiria no próximo deploy e o
    # registro ficaria apontando para o nada). Sem S3 configurado, o próprio
    # `upload_bytes_to_storage` grava no LOCAL_STORAGE_PATH (dev).
    arquivo_path, _url = upload_bytes_to_storage(
        key=f"{tipo}/{arquivo_nome}", content=file_bytes,
        content_type=arquivo.content_type or 'image/jpeg',
    )

    return {
        'arquivo': arquivo,
        'file_bytes': file_bytes,
        'aluno': aluno,
        'turma': aluno.turma,
        'arquivo_nome': arquivo_nome,
        'file_hash': file_hash,
        'arquivo_path': arquivo_path,
    }, None


def _descartar_upload(ctx):
    """Análise ou gravação falhou depois do upload: apaga o arquivo órfão."""
    if ctx and ctx.get('arquivo_path'):
        delete_from_storage(ctx['arquivo_path'])  # best-effort, nunca levanta


def _campos_arquivo(ctx: dict) -> dict:
    """Campos `arquivo_*` comuns a salvar_registro_escrita/desenho."""
    arquivo = ctx['arquivo']
    return {
        'aluno': ctx['aluno'],
        'turma': ctx['turma'],
        'arquivo_nome': ctx['arquivo_nome'],
        'file_hash': ctx['file_hash'],
        'arquivo_path': ctx['arquivo_path'],
        'arquivo_original': arquivo.name,
        'tamanho_arquivo': len(ctx['file_bytes']),
        'tipo_arquivo': arquivo.content_type or 'image/unknown',
    }


def _resposta_base(ctx: dict) -> dict:
    """Campos de resposta comuns (formato mantido para o frontend)."""
    arquivo = ctx['arquivo']
    return {
        'success': True,
        'arquivo_salvo': ctx['arquivo_path'],
        'arquivo_nome': ctx['arquivo_nome'],
        'arquivo_hash': ctx['file_hash'],
        'arquivo_original': arquivo.name,
        'arquivo_url': ctx['arquivo_path'],
        'alunoId': str(ctx['aluno'].id),
        'nomeAluno': ctx['aluno'].nome_completo,
        'turmaId': str(ctx['turma'].id),
    }


def _analise_base(ctx: dict) -> dict:
    arquivo = ctx['arquivo']
    return {
        'arquivo_processado': True,
        'arquivo_id': ctx['file_hash'],
        'tamanho_arquivo': len(ctx['file_bytes']),
        'tipo_arquivo': arquivo.content_type,
    }


# ---------------------------------------------------------------------------
# Endpoints de upload + análise
# ---------------------------------------------------------------------------

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([UploadRateThrottle])
def upload_e_analise_escrita(request):
    """Upload + análise de escrita. Body (multipart): arquivo, alunoId, turmaId (opcional)."""
    ctx = None
    try:
        ctx, erro = _preparar_upload(request, "escrita")
        if erro:
            return erro

        aluno = ctx['aluno']
        analise_completa, etapa_detectada = analisar_escrita(
            aluno.nome_completo,
            base64.b64encode(ctx['file_bytes']).decode("utf-8"),
            idade=idade_do_aluno(aluno),
            usuario=request.user,
            cliente_id=cliente_id_do_usuario(request.user),
        )
        descricao = f"ANÁLISE TÉCNICA:\n{analise_completa}"

        salvar_registro_escrita(
            professor=request.user,
            etapa_ia=etapa_detectada,
            analise_detalhada=descricao,
            **_campos_arquivo(ctx),
        )

        return Response({
            **_resposta_base(ctx),
            'nomeArquivo': ctx['arquivo'].name,
            'analise': {
                'descricao': descricao,
                'fase_escrita': etapa_detectada,
                'fases_validas': FASES_ESCRITA + [NAO_CLASSIFICAVEL],
                **_analise_base(ctx),
            },
        })

    except Exception:
        logger.exception("Erro no upload/análise de escrita")
        _descartar_upload(ctx)
        return _erro('Erro interno no servidor', status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([UploadRateThrottle])
def upload_e_analise_desenho(request):
    """Upload + análise de desenho. Body (multipart): arquivo, alunoId, turmaId, atividade, contexto."""
    ctx = None
    try:
        ctx, erro = _preparar_upload(request, "desenho")
        if erro:
            return erro

        aluno = ctx['aluno']
        atividade = request.data.get('atividade') or 'Desenho Livre'
        contexto = request.data.get('contexto', '')

        analise_completa, fase_desenho, elementos_detectados = analisar_desenho(
            aluno.nome_completo,
            base64.b64encode(ctx['file_bytes']).decode("utf-8"),
            idade=idade_do_aluno(aluno),
            usuario=request.user,
            cliente_id=cliente_id_do_usuario(request.user),
        )

        salvar_registro_desenho(
            professor=request.user,
            atividade=atividade,
            contexto=contexto,
            fase_desenho=fase_desenho,
            elementos_detectados=elementos_detectados,
            analise_detalhada=analise_completa,
            **_campos_arquivo(ctx),
        )

        return Response({
            **_resposta_base(ctx),
            'atividade': atividade,
            'contexto': contexto,
            'analise': {
                'descricao': analise_completa,
                'fase_desenho': fase_desenho,
                'fases_validas': FASES_DESENHO + [NAO_CLASSIFICAVEL],
                'elementos': elementos_detectados,
                'desenvolvimento': fase_desenho,
                **_analise_base(ctx),
            },
        })

    except Exception:
        logger.exception("Erro no upload/análise de desenho")
        _descartar_upload(ctx)
        return _erro('Erro interno no servidor', status.HTTP_500_INTERNAL_SERVER_ERROR)


# ---------------------------------------------------------------------------
# Revisão da classificação
# ---------------------------------------------------------------------------

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def atualizar_classificacao(request):
    """Atualiza a classificação de um registro de escrita/desenho quando a
    professora discorda da sugestão da IA (modal de confirmação do frontend).
    Só o autor do registro ou a gestão.

    Body: { tipo: 'escrita'|'desenho', arquivo_hash, classificacao }
    """
    tipo = (request.data.get('tipo') or '').strip()
    arquivo_hash = (request.data.get('arquivo_hash') or '').strip()
    classificacao = (request.data.get('classificacao') or '').strip()

    if not tipo or not arquivo_hash or not classificacao:
        return _erro('tipo, arquivo_hash e classificacao são obrigatórios', status.HTTP_400_BAD_REQUEST)

    model = _MODELS_POR_TIPO.get(tipo)
    if model is None:
        return _erro("tipo deve ser 'escrita' ou 'desenho'", status.HTTP_400_BAD_REQUEST)

    registro = model.objects.filter(arquivo_hash=arquivo_hash).first()  # TenantManager
    if registro is None:
        return _erro('Registro não encontrado', status.HTTP_404_NOT_FOUND)
    if not dono_ou_gestao(request.user, registro):
        return _erro('Sem permissão.', status.HTTP_403_FORBIDDEN)

    try:
        registro = atualizar_classificacao_registro(
            tipo=tipo,
            arquivo_hash=arquivo_hash,
            classificacao=classificacao,
            revisado_por=getattr(request.user, 'email', None) or None,
        )
    except ValueError as e:
        return _erro(str(e), status.HTTP_400_BAD_REQUEST)
    except Exception:
        logger.exception("Erro ao atualizar classificação")
        return _erro('Erro interno no servidor', status.HTTP_500_INTERNAL_SERVER_ERROR)

    return Response({
        'success': True,
        'registro_id': str(registro.id),
        'tipo': tipo,
        'classificacao': classificacao,
    })


# ---------------------------------------------------------------------------
# Servir arquivo
# ---------------------------------------------------------------------------

def _buscar_registro_por_hash(arquivo_hash: str):
    """Retorna (registro, tipo) procurando em escrita e depois desenho
    (TenantManager: fora do escopo = inexistente); Http404 se não achar."""
    for tipo, model in _MODELS_POR_TIPO.items():
        registro = model.objects.filter(arquivo_hash=arquivo_hash).first()
        if registro:
            return registro, tipo
    raise Http404("Registro não encontrado")


def _chave_storage(registro, tipo: str) -> str:
    """Key do arquivo no storage.

    Registros antigos gravados pelo fallback de disco (``uploads/...`` ou
    caminho absoluto) tiveram a cópia enviada ao storage como
    ``<tipo>/<arquivo_nome>`` — é essa key que vale para eles.
    """
    path = registro.arquivo_path or ''
    if not path or path.startswith('uploads/') or path.startswith('/'):
        return f"{tipo}/{registro.arquivo_nome}"
    return path


def _aplicar_rotacao(content: bytes, graus: int) -> bytes | None:
    """Gira a imagem em `graus` (positivo = anti-horário/esquerda, convenção do
    Pillow) APÓS normalizar o EXIF. Retorna JPEG ou None se falhar."""
    try:
        img = Image.open(io.BytesIO(content))
        img = ImageOps.exif_transpose(img)
        img = img.rotate(graus, expand=True)
        if img.mode != 'RGB':
            img = img.convert('RGB')
        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=85, optimize=True)
        return buf.getvalue()
    except Exception:
        logger.exception("Falha ao rotacionar imagem (%s graus)", graus)
        return None


def _resposta_imagem(conteudo: bytes, content_type: str, nome: str | None = None) -> HttpResponse:
    resposta = HttpResponse(conteudo, content_type=content_type)
    if nome:
        resposta['Content-Disposition'] = f'inline; filename="{nome}"'
    resposta['Cache-Control'] = 'private, max-age=3600'
    resposta['X-Content-Type-Options'] = 'nosniff'
    return resposta


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def servir_arquivo(request, arquivo_hash):
    """
    Serve arquivos de escrita/desenho: redireciona para a URL pré-assinada do
    S3 ou, sem S3 (dev), devolve os bytes do storage local.

    Query `?rot=90|180|270`: serve a imagem ROTACIONADA on-the-fly (usada pelo
    quadro de "Análise de Produções" do relatório para fotos paisagem — regra:
    girar 90° à esquerda na exibição; o arquivo salvo não é alterado).
    """
    registro, tipo = _buscar_registro_por_hash(arquivo_hash)
    chave = _chave_storage(registro, tipo)

    try:
        rot = request.GET.get('rot', '')
        if rot in ('90', '180', '270'):
            girada = _aplicar_rotacao(download_bytes_from_storage(chave), int(rot))
            if girada is not None:
                return _resposta_imagem(girada, 'image/jpeg')
            # Falhou a rotação: cai no fluxo normal (imagem original).

        if is_s3_configured():
            url = generate_presigned_url(chave)
            if url:
                return redirect(url)
            raise Http404("Arquivo não encontrado no S3")

        return _resposta_imagem(
            download_bytes_from_storage(chave),
            registro.tipo_arquivo or 'application/octet-stream',
            registro.arquivo_nome,
        )

    except FileNotFoundError:
        raise Http404("Arquivo não encontrado")
    except Http404:
        raise
    except Exception:
        logger.exception("Erro ao servir arquivo %s", arquivo_hash)
        return _erro('Erro ao servir arquivo', status.HTTP_500_INTERNAL_SERVER_ERROR)