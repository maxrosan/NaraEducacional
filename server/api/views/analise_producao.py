"""Views para upload e análise de produções infantis (escrita e desenho)."""

import base64
import io
import logging
import os

import httpx
from PIL import Image, ImageOps

from django.core.exceptions import ValidationError
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import redirect
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.models import Aluno, RegistroDesenho, RegistroEscrita, Turma
from api.storage import generate_presigned_url
from api.throttles import UploadRateThrottle
from api.ia_utils import (
    ALLOWED_IMAGE_EXTENSIONS,
    ALLOWED_IMAGE_MIME_TYPES,
    MAX_IMAGE_SIZE_BYTES,
    check_rate_limit,
    gerar_nome_arquivo_seguro,
    validate_uploaded_file,
)
from api.services.analise_producao import (
    analisar_desenho,
    analisar_escrita,
    atualizar_classificacao_registro,
    idade_do_aluno,
    salvar_registro_desenho,
    salvar_registro_escrita,
    upload_para_s3,
)
from api.services.fases_producao import FASES_DESENHO, FASES_ESCRITA, NAO_CLASSIFICAVEL

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers do upload
# ---------------------------------------------------------------------------

def _get_cliente_id(request):
    """Extrai cliente_id (instituicao_id) do usuário autenticado."""
    return str(request.user.instituicao_id) if getattr(request.user, 'instituicao_id', None) else None


def _erro(mensagem: str, status_code: int, **extra) -> Response:
    return Response({'error': mensagem}, status=status_code, **extra)


def _preparar_upload(request, tipo: str):
    """Validações comuns a escrita e desenho.

    Retorna ``(contexto, None)`` em caso de sucesso ou ``(None, Response)`` com o erro.
    ``contexto`` traz: arquivo, file_bytes, aluno, turma, arquivo_nome, file_hash, arquivo_path.
    """
    if 'arquivo' not in request.FILES:
        return None, _erro('Nenhum arquivo foi enviado', status.HTTP_400_BAD_REQUEST)

    allowed, retry_after = check_rate_limit(request, f"upload_{tipo}")
    if not allowed:
        return None, _erro(
            'Limite de requisições de upload excedido. Tente novamente em alguns segundos.',
            status.HTTP_429_TOO_MANY_REQUESTS,
            headers={'Retry-After': str(retry_after)},
        )

    arquivo = request.FILES['arquivo']
    validation_error = validate_uploaded_file(
        arquivo, ALLOWED_IMAGE_MIME_TYPES, ALLOWED_IMAGE_EXTENSIONS,
        MAX_IMAGE_SIZE_BYTES, f"imagem de {tipo}",
    )
    if validation_error:
        mensagem, status_code = validation_error
        return None, _erro(mensagem, status_code)

    aluno_id = request.POST.get('alunoId')
    if not aluno_id:
        return None, _erro("Campo 'alunoId' é obrigatório.", status.HTTP_400_BAD_REQUEST)
    try:
        aluno = Aluno.objects.select_related('turma').get(id=aluno_id)
    except (Aluno.DoesNotExist, ValueError, ValidationError):  # UUID malformado -> ValidationError
        return None, _erro('Aluno não encontrado.', status.HTTP_404_NOT_FOUND)

    # Turma: a enviada pelo front (se pertencer à escola do aluno) ou a atual do aluno.
    turma = aluno.turma
    turma_id = request.POST.get('turmaId')
    if turma_id and str(turma_id) != str(aluno.turma_id):
        try:
            turma = Turma.objects.get(id=turma_id, escola_id=aluno.escola_id)
        except (Turma.DoesNotExist, ValueError, ValidationError):
            return None, _erro('Turma não encontrada para este aluno.', status.HTTP_404_NOT_FOUND)

    arquivo_nome, file_hash = gerar_nome_arquivo_seguro(aluno.nome_completo, arquivo.name)
    file_bytes = arquivo.read()
    arquivo_path = upload_para_s3(file_bytes, tipo, arquivo_nome, arquivo.content_type)

    return {
        'arquivo': arquivo,
        'file_bytes': file_bytes,
        'aluno': aluno,
        'turma': turma,
        'arquivo_nome': arquivo_nome,
        'file_hash': file_hash,
        'arquivo_path': arquivo_path,
    }, None


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


# ---------------------------------------------------------------------------
# Endpoints de upload + análise
# ---------------------------------------------------------------------------

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([UploadRateThrottle])
def upload_e_analise_escrita(request):
    """Upload + análise de escrita. Body (multipart): arquivo, alunoId, turmaId (opcional)."""
    try:
        ctx, erro = _preparar_upload(request, "escrita")
        if erro:
            return erro

        aluno, arquivo, file_bytes = ctx['aluno'], ctx['arquivo'], ctx['file_bytes']

        analise_completa, etapa_detectada = analisar_escrita(
            aluno.nome_completo,
            base64.b64encode(file_bytes).decode("utf-8"),
            idade=idade_do_aluno(aluno),
            usuario=request.user,
            cliente_id=_get_cliente_id(request),
        )
        descricao = f"ANÁLISE TÉCNICA:\n{analise_completa}"

        salvar_registro_escrita(
            aluno=aluno,
            turma=ctx['turma'],
            professor=request.user,
            arquivo_nome=ctx['arquivo_nome'],
            file_hash=ctx['file_hash'],
            arquivo_path=ctx['arquivo_path'],
            arquivo_original=arquivo.name,
            tamanho_arquivo=len(file_bytes),
            tipo_arquivo=arquivo.content_type or 'image/unknown',
            etapa_ia=etapa_detectada,
            analise_detalhada=descricao,
        )

        return Response({
            **_resposta_base(ctx),
            'nomeArquivo': arquivo.name,
            'analise': {
                'descricao': descricao,
                'fase_escrita': etapa_detectada,
                'fases_validas': FASES_ESCRITA + [NAO_CLASSIFICAVEL],
                'arquivo_processado': True,
                'arquivo_id': ctx['file_hash'],
                'tamanho_arquivo': len(file_bytes),
                'tipo_arquivo': arquivo.content_type,
            },
        })

    except Exception:
        logger.exception("Erro no upload/análise de escrita")
        return _erro('Erro interno no servidor', status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([UploadRateThrottle])
def upload_e_analise_desenho(request):
    """Upload + análise de desenho. Body (multipart): arquivo, alunoId, turmaId, atividade, contexto."""
    try:
        ctx, erro = _preparar_upload(request, "desenho")
        if erro:
            return erro

        aluno, arquivo, file_bytes = ctx['aluno'], ctx['arquivo'], ctx['file_bytes']
        atividade = request.POST.get('atividade') or 'Desenho Livre'
        contexto = request.POST.get('contexto', '')

        analise_completa, fase_desenho, elementos_detectados = analisar_desenho(
            aluno.nome_completo,
            base64.b64encode(file_bytes).decode("utf-8"),
            idade=idade_do_aluno(aluno),
            usuario=request.user,
            cliente_id=_get_cliente_id(request),
        )

        salvar_registro_desenho(
            aluno=aluno,
            turma=ctx['turma'],
            professor=request.user,
            atividade=atividade,
            contexto=contexto,
            arquivo_nome=ctx['arquivo_nome'],
            file_hash=ctx['file_hash'],
            arquivo_path=ctx['arquivo_path'],
            arquivo_original=arquivo.name,
            tamanho_arquivo=len(file_bytes),
            tipo_arquivo=arquivo.content_type or 'image/unknown',
            fase_desenho=fase_desenho,
            elementos_detectados=elementos_detectados,
            analise_detalhada=analise_completa,
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
                'arquivo_processado': True,
                'arquivo_id': ctx['file_hash'],
                'tamanho_arquivo': len(file_bytes),
                'tipo_arquivo': arquivo.content_type,
            },
        })

    except Exception:
        logger.exception("Erro no upload/análise de desenho")
        return _erro('Erro interno no servidor', status.HTTP_500_INTERNAL_SERVER_ERROR)


# ---------------------------------------------------------------------------
# Revisão da classificação
# ---------------------------------------------------------------------------

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def atualizar_classificacao(request):
    """Atualiza a classificação de um registro de escrita/desenho quando a
    professora discorda da sugestão da IA (modal de confirmação do frontend).

    Body: { tipo: 'escrita'|'desenho', arquivo_hash, classificacao }
    """
    tipo = (request.data.get('tipo') or '').strip()
    arquivo_hash = (request.data.get('arquivo_hash') or '').strip()
    classificacao = (request.data.get('classificacao') or '').strip()

    if not tipo or not arquivo_hash or not classificacao:
        return _erro('tipo, arquivo_hash e classificacao são obrigatórios', status.HTTP_400_BAD_REQUEST)

    try:
        registro = atualizar_classificacao_registro(
            tipo=tipo,
            arquivo_hash=arquivo_hash,
            classificacao=classificacao,
            revisado_por=getattr(request.user, 'email', None) or None,
        )
    except ValueError as e:
        return _erro(str(e), status.HTTP_400_BAD_REQUEST)
    except (RegistroEscrita.DoesNotExist, RegistroDesenho.DoesNotExist):
        return _erro('Registro não encontrado', status.HTTP_404_NOT_FOUND)
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
    """Retorna (registro, tipo) procurando em escrita e depois desenho; Http404 se não achar."""
    registro = RegistroEscrita.objects.filter(arquivo_hash=arquivo_hash).first()
    if registro:
        return registro, 'escrita'
    registro = RegistroDesenho.objects.filter(arquivo_hash=arquivo_hash).first()
    if registro:
        return registro, 'desenho'
    raise Http404("Registro não encontrado")


def _caminho_local(registro) -> str | None:
    """Caminho em disco se o arquivo existir localmente (fallback do upload), senão None."""
    path = registro.arquivo_path or ''
    return path if path and os.path.exists(path) else None


def _s3_key(registro, tipo: str) -> str:
    """Key no S3. Registros de fallback local (``uploads/...``) usam ``<tipo>/<arquivo_nome>``."""
    path = registro.arquivo_path or ''
    if not path or path.startswith('uploads/') or os.path.isabs(path):
        return f"{tipo}/{registro.arquivo_nome}"
    return path


def _bytes_do_registro(registro, tipo: str) -> bytes | None:
    """Bytes do arquivo do registro (disco local ou S3). None se falhar."""
    try:
        local = _caminho_local(registro)
        if local:
            with open(local, 'rb') as f:
                return f.read()
        url = generate_presigned_url(_s3_key(registro, tipo))
        if not url:
            return None
        resposta = httpx.get(url, timeout=15.0, follow_redirects=True)
        if resposta.status_code == 200:
            return resposta.content
    except Exception:
        logger.exception("Falha ao obter bytes do arquivo %s", registro.arquivo_hash)
    return None


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


@api_view(['GET'])
def servir_arquivo(request, arquivo_hash):
    """
    Serve arquivos de escrita/desenho.
    Redireciona para URL pré-assinada do S3 ou serve do disco local como fallback.

    Query `?rot=90|180|270`: serve a imagem ROTACIONADA on-the-fly (usada pelo
    quadro de "Análise de Produções" do relatório para fotos paisagem — regra:
    girar 90° à esquerda na exibição; o arquivo salvo não é alterado).
    """
    registro, tipo = _buscar_registro_por_hash(arquivo_hash)

    try:
        rot = request.GET.get('rot', '')
        if rot in ('90', '180', '270'):
            conteudo = _bytes_do_registro(registro, tipo)
            girada = _aplicar_rotacao(conteudo, int(rot)) if conteudo else None
            if girada is not None:
                resposta = HttpResponse(girada, content_type='image/jpeg')
                resposta['Cache-Control'] = 'private, max-age=3600'
                resposta['X-Content-Type-Options'] = 'nosniff'
                return resposta
            # Falhou a rotação: cai no fluxo normal (imagem original).

        local = _caminho_local(registro)
        if local:
            response = FileResponse(
                open(local, 'rb'),
                content_type=registro.tipo_arquivo or 'application/octet-stream',
            )
            response['Content-Disposition'] = f'inline; filename="{registro.arquivo_nome}"'
            response['X-Content-Type-Options'] = 'nosniff'
            return response

        url = generate_presigned_url(_s3_key(registro, tipo))
        if url:
            return redirect(url)
        raise Http404("Arquivo não encontrado no S3")

    except Http404:
        raise
    except Exception:
        logger.exception("Erro ao servir arquivo %s", arquivo_hash)
        return _erro('Erro ao servir arquivo', status.HTTP_500_INTERNAL_SERVER_ERROR)