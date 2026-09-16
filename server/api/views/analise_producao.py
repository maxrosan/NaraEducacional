"""Views para upload e análise de produções infantis (escrita e desenho)."""

import base64
import io
import logging
import os

import httpx
from PIL import Image, ImageOps

from django.http import Http404, HttpResponse
from django.shortcuts import redirect
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from datetime import date

from api.models import Crianca, RegistroEscrita, RegistroDesenho
from api.throttles import UploadRateThrottle
from api.storage import generate_presigned_url
from api.views_legacy import (
    validate_uploaded_file,
    check_rate_limit,
    gerar_nome_arquivo_seguro,
    ALLOWED_IMAGE_MIME_TYPES,
    ALLOWED_IMAGE_EXTENSIONS,
    MAX_IMAGE_SIZE_BYTES,
)
from api.services.analise_producao import (
    upload_para_s3,
    analisar_escrita,
    analisar_desenho,
    atualizar_classificacao_registro,
    salvar_registro_escrita,
    salvar_registro_desenho,
)
from api.services.fases_producao import FASES_ESCRITA, FASES_DESENHO, NAO_CLASSIFICAVEL

logger = logging.getLogger(__name__)


def _get_cliente_id(request):
    """Extrai cliente_id (instituicao_id) do usuário autenticado."""
    return str(request.user.instituicao_id) if getattr(request.user, 'instituicao_id', None) else None


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([UploadRateThrottle])
def upload_e_analise_escrita(request):
    """Endpoint para upload de arquivo e análise de escrita. Requer autenticação."""
    try:
        if 'arquivo' not in request.FILES:
            return Response({'error': 'Nenhum arquivo foi enviado'}, status=status.HTTP_400_BAD_REQUEST)

        allowed, retry_after = check_rate_limit(request, "upload_escrita")
        if not allowed:
            return Response(
                {'error': 'Limite de requisições de upload excedido. Tente novamente em alguns segundos.'},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
                headers={'Retry-After': str(retry_after)},
            )

        arquivo = request.FILES['arquivo']
        nome_aluno = request.POST.get('nomeAluno', '')
        serie_aluno = request.POST.get('serieAluno', '')
        turma_id = request.POST.get('turmaId', '')

        validation_error = validate_uploaded_file(
            arquivo, ALLOWED_IMAGE_MIME_TYPES, ALLOWED_IMAGE_EXTENSIONS,
            MAX_IMAGE_SIZE_BYTES, "imagem de escrita",
        )
        if validation_error:
            mensagem, status_code = validation_error
            return Response({'error': mensagem}, status=status_code)

        if not nome_aluno or not serie_aluno:
            return Response({'error': 'Nome do aluno e série são obrigatórios'}, status=status.HTTP_400_BAD_REQUEST)

        arquivo_nome, file_hash = gerar_nome_arquivo_seguro(nome_aluno, arquivo.name)
        file_bytes = arquivo.read()
        imagem_base64 = base64.b64encode(file_bytes).decode("utf-8")

        arquivo_path = upload_para_s3(file_bytes, "escrita", arquivo_nome, arquivo.content_type)

        idade_str = "Não informada"
        crianca = Crianca.objects.filter(nome_completo__icontains=nome_aluno).first()
        if crianca and crianca.data_nascimento:
            hoje = date.today()
            anos = hoje.year - crianca.data_nascimento.year - (
                (hoje.month, hoje.day) < (crianca.data_nascimento.month, crianca.data_nascimento.day)
            )
            idade_str = f"{anos} anos"

        analise_completa, etapa_detectada = analisar_escrita(
            nome_aluno,
            imagem_base64,
            idade=idade_str,
            usuario=request.user,
            cliente_id=_get_cliente_id(request),
        )

        salvar_registro_escrita(
            nome_aluno=nome_aluno,
            turma_id=turma_id,
            serie_aluno=serie_aluno,
            arquivo_nome=arquivo_nome,
            file_hash=file_hash,
            arquivo_path=arquivo_path,
            arquivo_original=arquivo.name,
            tamanho_arquivo=len(file_bytes),
            tipo_arquivo=arquivo.content_type or 'image/unknown',
            etapa_ia=etapa_detectada,
            analise_detalhada=f"ANÁLISE TÉCNICA:\n{analise_completa}",
        )

        return Response({
            'success': True,
            'arquivo_salvo': arquivo_path,
            'arquivo_nome': arquivo_nome,
            'arquivo_hash': file_hash,
            'arquivo_original': arquivo.name,
            'arquivo_url': arquivo_path,
            'nomeAluno': nome_aluno,
            'serieAluno': serie_aluno,
            'nomeArquivo': arquivo.name,
            'turmaId': turma_id,
            'analise': {
                'descricao': f"ANÁLISE TÉCNICA:\n{analise_completa}",
                'fase_escrita': etapa_detectada,
                'fases_validas': FASES_ESCRITA + [NAO_CLASSIFICAVEL],
                'arquivo_processado': True,
                'arquivo_id': file_hash,
                'tamanho_arquivo': len(file_bytes),
                'tipo_arquivo': arquivo.content_type,
            },
        })

    except Exception as e:
        logger.exception("Erro no upload/análise de escrita")
        return Response(
            {'error': 'Erro interno no servidor', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([UploadRateThrottle])
def upload_e_analise_desenho(request):
    """Endpoint para upload de arquivo e análise de desenho. Requer autenticação."""
    try:
        if 'arquivo' not in request.FILES:
            return Response({'error': 'Nenhum arquivo foi enviado'}, status=status.HTTP_400_BAD_REQUEST)

        allowed, retry_after = check_rate_limit(request, "upload_desenho")
        if not allowed:
            return Response(
                {'error': 'Limite de requisições de upload excedido. Tente novamente em alguns segundos.'},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
                headers={'Retry-After': str(retry_after)},
            )

        arquivo = request.FILES['arquivo']
        nome_aluno = request.POST.get('nomeAluno', '')
        serie_aluno = request.POST.get('serieAluno', '')
        turma_id = request.POST.get('turmaId', '')
        atividade = request.POST.get('atividade', 'Desenho Livre')
        contexto = request.POST.get('contexto', '')
        professora = request.POST.get('professora', 'Sistema')

        validation_error = validate_uploaded_file(
            arquivo, ALLOWED_IMAGE_MIME_TYPES, ALLOWED_IMAGE_EXTENSIONS,
            MAX_IMAGE_SIZE_BYTES, "imagem de desenho",
        )
        if validation_error:
            mensagem, status_code = validation_error
            return Response({'error': mensagem}, status=status_code)

        if not nome_aluno or not serie_aluno:
            return Response({'error': 'Nome do aluno e série são obrigatórios'}, status=status.HTTP_400_BAD_REQUEST)

        arquivo_nome, file_hash = gerar_nome_arquivo_seguro(nome_aluno, arquivo.name)
        file_bytes = arquivo.read()
        imagem_base64 = base64.b64encode(file_bytes).decode("utf-8")

        arquivo_path = upload_para_s3(file_bytes, "desenho", arquivo_nome, arquivo.content_type)

        idade_str = "Não informada"
        crianca = Crianca.objects.filter(nome_completo__icontains=nome_aluno).first()
        if crianca and crianca.data_nascimento:
            hoje = date.today()
            anos = hoje.year - crianca.data_nascimento.year - (
                (hoje.month, hoje.day) < (crianca.data_nascimento.month, crianca.data_nascimento.day)
            )
            idade_str = f"{anos} anos"

        analise_completa, fase_desenho, elementos_detectados = analisar_desenho(
            nome_aluno,
            imagem_base64,
            idade=idade_str,
            usuario=request.user,
            cliente_id=_get_cliente_id(request),
        )

        salvar_registro_desenho(
            nome_aluno=nome_aluno,
            turma_id=turma_id,
            serie_aluno=serie_aluno,
            atividade=atividade,
            contexto=contexto,
            arquivo_nome=arquivo_nome,
            file_hash=file_hash,
            arquivo_path=arquivo_path,
            arquivo_original=arquivo.name,
            tamanho_arquivo=len(file_bytes),
            tipo_arquivo=arquivo.content_type or 'image/unknown',
            fase_desenho=fase_desenho,
            elementos_detectados=elementos_detectados,
            analise_detalhada=analise_completa,
            professora=professora,
        )

        return Response({
            'success': True,
            'arquivo_salvo': arquivo_path,
            'arquivo_nome': arquivo_nome,
            'arquivo_hash': file_hash,
            'arquivo_original': arquivo.name,
            'arquivo_url': arquivo_path,
            'nomeAluno': nome_aluno,
            'serieAluno': serie_aluno,
            'turmaId': turma_id,
            'atividade': atividade,
            'contexto': contexto,
            'analise': {
                'descricao': analise_completa,
                'fase_desenho': fase_desenho,
                'fases_validas': FASES_DESENHO + [NAO_CLASSIFICAVEL],
                'elementos': elementos_detectados,
                'desenvolvimento': fase_desenho,
                'arquivo_processado': True,
                'arquivo_id': file_hash,
                'tamanho_arquivo': len(file_bytes),
                'tipo_arquivo': arquivo.content_type,
            },
        })

    except Exception as e:
        logger.exception("Erro no upload/análise de desenho")
        return Response(
            {'error': 'Erro interno no servidor', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


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
        return Response(
            {'error': 'tipo, arquivo_hash e classificacao são obrigatórios'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        registro = atualizar_classificacao_registro(
            tipo=tipo,
            arquivo_hash=arquivo_hash,
            classificacao=classificacao,
            professora=getattr(request.user, 'email', None) or None,
        )
    except ValueError as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    except (RegistroEscrita.DoesNotExist, RegistroDesenho.DoesNotExist):
        return Response({'error': 'Registro não encontrado'}, status=status.HTTP_404_NOT_FOUND)
    except Exception:
        logger.exception("Erro ao atualizar classificação")
        return Response({'error': 'Erro interno no servidor'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return Response({
        'success': True,
        'registro_id': str(registro.id),
        'tipo': tipo,
        'classificacao': classificacao,
    })


def _bytes_do_registro(registro, tipo):
    """Bytes do arquivo do registro (disco local ou S3). None se falhar."""
    path = registro.arquivo_path or ''
    try:
        if path and (os.path.isabs(path) or os.path.exists(path)):
            with open(path, 'rb') as f:
                return f.read()
        s3_key = path
        if not s3_key or s3_key.startswith('uploads/'):
            s3_key = f"{tipo}/{registro.arquivo_nome}"
        url = generate_presigned_url(s3_key)
        if not url:
            return None
        resposta = httpx.get(url, timeout=15.0, follow_redirects=True)
        if resposta.status_code == 200:
            return resposta.content
    except Exception:
        logger.exception("Falha ao obter bytes do arquivo %s", registro.arquivo_hash)
    return None


def _aplicar_rotacao(content: bytes, graus: int):
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
    try:
        registro = None
        tipo = None
        try:
            registro = RegistroEscrita.objects.get(arquivo_hash=arquivo_hash)
            tipo = 'escrita'
        except RegistroEscrita.DoesNotExist:
            try:
                registro = RegistroDesenho.objects.get(arquivo_hash=arquivo_hash)
                tipo = 'desenho'
            except RegistroDesenho.DoesNotExist:
                raise Http404("Registro não encontrado")

        rot = request.GET.get('rot', '')
        if rot in ('90', '180', '270'):
            conteudo = _bytes_do_registro(registro, tipo)
            if conteudo:
                girada = _aplicar_rotacao(conteudo, int(rot))
                if girada is not None:
                    resposta = HttpResponse(girada, content_type='image/jpeg')
                    resposta['Cache-Control'] = 'private, max-age=3600'
                    resposta['X-Content-Type-Options'] = 'nosniff'
                    return resposta
            # Falhou a rotação: cai no fluxo normal (imagem original).

        arquivo_path = registro.arquivo_path

        if not os.path.isabs(arquivo_path) and not os.path.exists(arquivo_path):
            s3_key = arquivo_path
            if arquivo_path.startswith('uploads/'):
                s3_key = f"{tipo}/{registro.arquivo_nome}"

            url = generate_presigned_url(s3_key)
            if url:
                return redirect(url)
            raise Http404("Arquivo não encontrado no S3")

        from django.http import FileResponse
        response = FileResponse(
            open(arquivo_path, 'rb'),
            content_type=registro.tipo_arquivo or 'application/octet-stream',
        )
        response['Content-Disposition'] = f'inline; filename="{registro.arquivo_nome}"'
        response['X-Content-Type-Options'] = 'nosniff'
        return response

    except Http404:
        raise
    except Exception as e:
        return Response(
            {'error': 'Erro ao servir arquivo', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )