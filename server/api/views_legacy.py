from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status
from .throttles import UploadRateThrottle
from django.http import FileResponse, Http404
from django.shortcuts import redirect
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.forms.models import model_to_dict
import json
import hashlib
import os
import time
import random
import difflib
import re
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.core.cache import cache
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from .models import RegistroEscrita, RegistroDesenho
from .openai_client import get_openai_client
from .storage import upload_bytes_to_storage, refresh_presigned_url, extract_storage_key_from_url, generate_presigned_url
import requests as http_requests
import base64
import tempfile
import logging
from collections import Counter
from .serializers import ProducaoCriancaSerializer
from django.db.models import Q

# Removido: librosa, numpy, pydub - análise de leitura agora usa 100% IA (GPT-4o-audio-preview)
import traceback

from .models import (
    HabilidadeBNCC,
    PerguntaBNCC,
    PlanejamentoSemanal,
    PlanejamentoDiario,
    PlanejamentoHabilidade,
    ObservacaoTranscricao,
    ProducaoFoto,
    ProducaoFotoCrianca,
    Crianca,
    RegistroObservacao,
    ProducaoCrianca,
    Instituicao,
)
from datetime import datetime, timedelta
from django.utils.dateparse import parse_date

import datetime

logger = logging.getLogger(__name__)

def _extrair_json_de_resposta_ia(conteudo: str) -> dict:
    """
    Normaliza respostas da IA e tenta extrair JSON válido, tolerando blocos ```json.
    """
    if not conteudo:
        return {}

    texto = conteudo.strip()

    if texto.startswith("```"):
        texto = re.sub(r"^```(?:json)?\\s*", "", texto, flags=re.IGNORECASE)
        texto = re.sub(r"\\s*```$", "", texto)

    if "{" in texto and "}" in texto:
        inicio = texto.find("{")
        fim = texto.rfind("}")
        if inicio != -1 and fim != -1 and fim > inicio:
            texto = texto[inicio:fim + 1]

    return json.loads(texto) if texto else {}

def _get_int_env(var_name: str, default: int) -> int:
    """
    Obtém valor inteiro de variável de ambiente com fallback seguro.
    """
    try:
        return int(os.getenv(var_name, default))
    except (TypeError, ValueError):
        return int(default)


def _get_float_env(var_name: str, default: float) -> float:
    """
    Obtém valor float de variável de ambiente com fallback seguro.
    """
    try:
        return float(os.getenv(var_name, default))
    except (TypeError, ValueError):
        return float(default)


# Configurações de validação e timeout (valores padrão podem ser sobrescritos por variáveis de ambiente)
MAX_IMAGE_SIZE_BYTES = _get_int_env("MAX_IMAGE_UPLOAD_MB", 10) * 1024 * 1024
MAX_AUDIO_SIZE_BYTES = _get_int_env("MAX_AUDIO_UPLOAD_MB", 50) * 1024 * 1024
IA_REQUEST_TIMEOUT_SECONDS = _get_float_env("IA_REQUEST_TIMEOUT_SECONDS", 45)
IA_AUDIO_TIMEOUT_SECONDS = _get_float_env("IA_AUDIO_TIMEOUT_SECONDS", IA_REQUEST_TIMEOUT_SECONDS)
UPLOAD_RATE_LIMIT = _get_int_env("UPLOAD_RATE_LIMIT_PER_MINUTE", 10)
UPLOAD_RATE_WINDOW_SECONDS = _get_int_env("UPLOAD_RATE_LIMIT_WINDOW_SECONDS", 60)

ALLOWED_IMAGE_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/jpg",
    "image/heic",
    "image/heif",
}
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}


# Mapa extensão -> mime type canônico. Usado quando o navegador não envia um
# Content-Type confiável (vazio ou "application/octet-stream") — comum em
# arquivos HEIC/HEIF fora do Safari.
CANONICAL_MIME_BY_EXTENSION = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".heic": "image/heic",
    ".heif": "image/heif",
}


def resolve_mime_type(file_obj, allowed_types):
    """Retorna um mime type confiável para persistir e mandar ao storage.

    Prioriza o Content-Type do navegador quando já é um dos aceitos; caso
    contrário, infere pela extensão do nome do arquivo.
    """
    content_type = (file_obj.content_type or "").lower()
    if content_type in allowed_types:
        return content_type
    extension = os.path.splitext(file_obj.name)[1].lower()
    return CANONICAL_MIME_BY_EXTENSION.get(extension, content_type or "application/octet-stream")

ALLOWED_AUDIO_MIME_TYPES = {
    "audio/wav",
    "audio/x-wav",
    "audio/mpeg",
    "audio/mp3",
    "audio/webm",
    "audio/ogg",
    "audio/m4a",
}
ALLOWED_AUDIO_EXTENSIONS = {".wav", ".mp3", ".mpeg", ".webm", ".ogg", ".m4a"}

THREAD_POOL = ThreadPoolExecutor(max_workers=4)


def run_with_timeout(func, timeout_seconds, *args, **kwargs):
    """
    Executa uma função em thread pool com timeout.
    """
    future = THREAD_POOL.submit(func, *args, **kwargs)
    try:
        return future.result(timeout=timeout_seconds)
    except FuturesTimeoutError:
        raise TimeoutError(f"Operação excedeu o limite de {timeout_seconds} segundos.")


def validate_uploaded_file(file_obj, allowed_types, allowed_extensions, max_size_bytes, contexto):
    """
    Valida tipo e tamanho do arquivo enviado, retornando uma tupla (mensagem, status) em caso de erro.
    """
    if file_obj.size > max_size_bytes:
        limite_mb = max_size_bytes / (1024 * 1024)
        return (
            f"Arquivo de {contexto} excede o limite de {limite_mb:.0f}MB. Comprima o arquivo antes de enviar.",
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
        )

    content_type = (file_obj.content_type or "").lower()
    extension = os.path.splitext(file_obj.name)[1].lower()

    if content_type not in allowed_types and extension not in allowed_extensions:
        formatos_aceitos = sorted({*allowed_types, *{f'*{ext}' for ext in allowed_extensions}})
        return (
            f"Formato não permitido para {contexto}. Utilize formatos aceitos: {', '.join(formatos_aceitos)}.",
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
        )

    return None


def check_rate_limit(request, prefix: str):
    """
    Aplica rate limiting por IP para uploads, com janela deslizante simples.
    Retorna tupla (permitido, retry_after_segundos).
    """
    ip_addr = request.META.get("REMOTE_ADDR", "unknown")
    key = f"rl:{prefix}:{ip_addr}"
    now = time.time()

    stored = cache.get(key)
    if stored:
        count, expires_at = stored
        if now > expires_at:
            count = 0
            expires_at = now + UPLOAD_RATE_WINDOW_SECONDS
    else:
        count = 0
        expires_at = now + UPLOAD_RATE_WINDOW_SECONDS

    count += 1
    ttl = max(int(expires_at - now), 1)
    cache.set(key, (count, expires_at), timeout=ttl)

    if count > UPLOAD_RATE_LIMIT:
        retry_after = int(expires_at - now)
        return False, max(retry_after, 1)

    return True, None



def gerar_nome_arquivo_seguro(nome_aluno, arquivo_original):
    """
    Gera um nome de arquivo seguro usando hash para evitar conflitos
    """
    timestamp = str(int(time.time()))
    random_value = str(random.randint(1000, 9999))
    
    # Limpar nome do aluno (remover caracteres especiais)
    nome_limpo = ''.join(c for c in nome_aluno if c.isalnum() or c in (' ', '-', '_')).strip()
    nome_limpo = nome_limpo.replace(' ', '_').replace('-', '_')
    
    # Criar hash baseado em nome + timestamp + random
    hash_input = f"{nome_limpo}_{timestamp}_{random_value}".encode('utf-8')
    file_hash = hashlib.md5(hash_input).hexdigest()[:12]
    
    # Extrair extensão segura
    extensao = 'jpg'  # default
    if '.' in arquivo_original:
        ext_original = arquivo_original.split('.')[-1].lower()
        # Permitir apenas extensões seguras
        extensoes_permitidas = ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp']
        if ext_original in extensoes_permitidas:
            extensao = ext_original
    
    return f"{file_hash}_{nome_limpo}_{timestamp}.{extensao}", file_hash


@api_view(['GET'])
def hello_world(request):
    """
    Simple Hello World API endpoint
    """
    return Response({
        'message': 'Hello World from Nara API!',
        'status': 'success',
        'version': '1.0.0'
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
def health_check(request):
    """
    Health check endpoint
    """
    return Response({
        'status': 'healthy',
        'message': 'API is running properly'
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
def analise_de_escrita(request):
    """
    API endpoint para análise de escrita (apenas metadados - versão simples)
    """
    try:
        nome_aluno = request.data.get('nomeAluno', '')
        serie_aluno = request.data.get('serieAluno', '')
        nome_arquivo = request.data.get('nomeArquivo', '')
        turma_id = request.data.get('turmaId', '')
        
        resultado = {
            'nomeAluno': nome_aluno,
            'serieAluno': serie_aluno,
            'nomeArquivo': nome_arquivo,
            'turmaId': turma_id,
            'analise': {
                'descricao': f"Análise simples da escrita de {nome_aluno}. Arquivo: {nome_arquivo}.",
                'fase_escrita': 'Em análise',
                'data_analise': "2025-07-28"
            }
        }
        
        return Response(resultado, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response(
            {'error': 'Erro interno no servidor', 'details': str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    
@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([UploadRateThrottle])
def upload_e_analise_escrita(request):
    """
    API endpoint para upload de arquivo e análise de escrita.
    Requer autenticação. Rate limit: 10 req/min.
    """
    try:
        # Verificar se o arquivo foi enviado
        if 'arquivo' not in request.FILES:
            return Response(
                {'error': 'Nenhum arquivo foi enviado'}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        allowed, retry_after = check_rate_limit(request, "upload_escrita")
        if not allowed:
            return Response(
                {'error': 'Limite de requisições de upload excedido. Tente novamente em alguns segundos.'},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
                headers={'Retry-After': str(retry_after)}
            )
        
        arquivo = request.FILES['arquivo']
        nome_aluno = request.POST.get('nomeAluno', '')
        serie_aluno = request.POST.get('serieAluno', '')
        turma_id = request.POST.get('turmaId', '')

        validation_error = validate_uploaded_file(
            arquivo,
            ALLOWED_IMAGE_MIME_TYPES,
            ALLOWED_IMAGE_EXTENSIONS,
            MAX_IMAGE_SIZE_BYTES,
            "imagem de escrita"
        )
        if validation_error:
            mensagem, status_code = validation_error
            return Response({'error': mensagem}, status=status_code)
        
        # Validar dados obrigatórios
        if not nome_aluno or not serie_aluno:
            return Response(
                {'error': 'Nome do aluno e série são obrigatórios'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Criar diretório de uploads se não existir
        upload_dir = 'uploads/escrita'
        os.makedirs(upload_dir, exist_ok=True)
        
        # Gerar nome de arquivo seguro com hash
        arquivo_nome, file_hash = gerar_nome_arquivo_seguro(nome_aluno, arquivo.name)
        arquivo_path = os.path.join(upload_dir, arquivo_nome)
        
        with open(arquivo_path, 'wb+') as destination:
            for chunk in arquivo.chunks():
                destination.write(chunk)

        with open(arquivo_path, "rb") as f:
                file_bytes = f.read()
                imagem_base64 = base64.b64encode(file_bytes).decode("utf-8")

        # Upload para S3
        s3_key = f"escrita/{arquivo_nome}"
        arquivo_url = None
        try:
            _, arquivo_url = upload_bytes_to_storage(
                key=s3_key,
                content=file_bytes,
                content_type=arquivo.content_type or "image/jpeg",
            )
            if arquivo_url:
                arquivo_path = s3_key
                print(f"[S3] Upload de escrita concluído: {arquivo_url}")
        except Exception as storage_error:
            print(f"[S3] Falha no upload para S3: {storage_error}")
        
        # Log do upload realizado
        print(f"[UPLOAD] Arquivo salvo: {arquivo_nome}")
        print(f"[UPLOAD] Hash gerado: {file_hash}")
        print(f"[UPLOAD] Aluno: {nome_aluno}")
        print(f"[UPLOAD] Tamanho: {arquivo.size} bytes")

        # Prompt para análise de escrita com OpenAI
        prompt = f"""
Atue como uma especialista em psicogênese da língua escrita, clonando a sensibilidade e a inteligência de Emilia Ferreiro e Ana Teberosky. Analise com profundidade a escrita infantil de {nome_aluno} a partir dos seguintes pilares: hipótese da criança sobre o sistema de escrita, correspondência sonora, uso de letras e estrutura da palavra.

🔍 Etapas da Análise:

Observe cuidadosamente a imagem da escrita infantil anexada.

Classifique com precisão em uma das fases da psicogênese:
- Pré-silábica
- Silábica sem valor sonoro
- Silábica com valor sonoro
- Silábico-alfabética
- Alfabética

Fundamente sua análise com base nos critérios observacionais de Ferreiro e Teberosky, sem copiar trechos teóricos nem soar como ChatGPT.

🧠 Formato da Resposta:
A resposta deve conter duas partes obrigatórias:

PARTE 1 – ANÁLISE TÉCNICA (máx. 4 linhas)
Use linguagem clara, direta e objetiva. Traga o nome da fase da escrita e os principais indícios observados.

PARTE 2 – PARA FAMÍLIA (mais detalhada)
Fale como se estivesse explicando para a mãe, o pai que não conhece termos técnicos. Use exemplos simples, metáforas acessíveis e um tom afetivo, como numa conversa entre gente que cuida junto.

Evite termos como "hipótese", "fonema", "notação", "grafema". Prefira expressões como "ela está tentando entender que...", "nesse momento, é como se ele pensasse que...".

🎯 Importante:
Evite parecer uma máquina. Sua fala deve tocar o coração de quem lê. Traduza o conhecimento com humanidade, sem perder a precisão.
"""
        
        try:
            # Chamar OpenAI para análise
            print(f"[OPENAI] Enviando prompt para análise da escrita de {nome_aluno}")

            openai_client = get_openai_client()

            def _analise_escrita_openai():
                return openai_client.chat.completions.create(
                    model="gpt-4o",
                    messages=[{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{imagem_base64}"
                                }
                            }
                        ]
                    }],
                    max_tokens=800,
                    timeout=IA_REQUEST_TIMEOUT_SECONDS
                )

            response = run_with_timeout(
                _analise_escrita_openai,
                IA_REQUEST_TIMEOUT_SECONDS
            )
            
            
            analise_completa = response.choices[0].message.content.strip()
            print(f"[OPENAI] Análise recebida com {len(analise_completa)} caracteres")
            
            # Extrair a fase da escrita da análise
            etapa_detectada = "Análise em processamento"
            
            # Procurar pela fase mencionada na análise
            fases_possiveis = ['Pré-silábica', 'Silábica sem valor sonoro', 'Silábica com valor sonoro', 'Silábico-alfabética', 'Alfabética']
            analise_lower = analise_completa.lower()
            for fase in fases_possiveis:
                if fase.lower() in analise_lower:
                    etapa_detectada = fase
                    break
            
        except RuntimeError as openai_config_error:
            print(f"[OPENAI ERROR] Configuração ausente: {openai_config_error}")
            analise_completa = f"FALHA NA ANÁLISE TÉCNICA:\nA configuração da OpenAI não está disponível. Configure a variável OPENAI_API_KEY e tente novamente."
            etapa_detectada = "Configuração OpenAI ausente"
        except TimeoutError:
            analise_completa = (
                "FALHA NA ANÁLISE TÉCNICA:\nTempo limite excedido para análise automática. "
                "Tente novamente com um arquivo mais leve ou verifique a conexão."
            )
            etapa_detectada = "Tempo excedido"
        except Exception as openai_error:
            print(f"[OPENAI ERROR] Erro na chamada da OpenAI: {openai_error}")
            # Fallback para análise mock em caso de erro
            analise_completa = f"FALHA NA ANÁLISE TÉCNICA:\nA escrita de {nome_aluno} está em processo de análise. Aguarde o processamento completo.\n\nPARA FAMÍLIA:\nEstamos analisando a escrita de {nome_aluno} com muito carinho. Em breve teremos uma análise detalhada sobre o desenvolvimento da escrita."
            etapa_detectada = "Falha na OpenAI"

        # Salvar no banco de dados
        try:
            registro = RegistroEscrita.objects.create(
                nome_aluno=nome_aluno,
                turma_id=turma_id,
                serie_aluno=serie_aluno,
                arquivo_nome=arquivo_nome,
                arquivo_hash=file_hash,
                arquivo_path=arquivo_path,
                arquivo_original=arquivo.name,
                tamanho_arquivo=arquivo.size,
                tipo_arquivo=arquivo.content_type or 'image/unknown',
                etapa_ia=etapa_detectada,
                analise_detalhada=f"ANÁLISE TÉCNICA:\n{analise_completa}",
                professora="Sistema",  # Por enquanto, depois vamos integrar com autenticação
                anotacoes_professora=""
            )
            
            print(f"[DATABASE] Registro salvo com ID: {registro.id}")
            
        except Exception as db_error:
            print(f"[DATABASE ERROR] Erro ao salvar no banco: {db_error}")
            # Continua mesmo se houver erro no banco - pelo menos retorna a análise
        
        resultado = {
            'success': True,
            'arquivo_salvo': arquivo_path,
            'arquivo_nome': arquivo_nome,
            'arquivo_hash': file_hash,
            'arquivo_original': arquivo.name,
            'arquivo_url': arquivo_url or arquivo_path,
            'nomeAluno': nome_aluno,
            'serieAluno': serie_aluno,
            'nomeArquivo': arquivo.name,
            'turmaId': turma_id,
            'analise': {
                'descricao': f"ANÁLISE TÉCNICA:\n{analise_completa}",
                'fase_escrita': etapa_detectada,
                'arquivo_processado': True,
                'arquivo_id': file_hash,
                'tamanho_arquivo': arquivo.size,
                'tipo_arquivo': arquivo.content_type,
                'data_analise': "2025-07-28"
            }
        }
        
        return Response(resultado, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response(
            {'error': 'Erro interno no servidor', 'details': str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
def listar_uploads(request):
    """
    API endpoint para listar arquivos enviados (para debug)
    """
    try:
        upload_dir = 'uploads/escrita'
        if not os.path.exists(upload_dir):
            return Response({'arquivos': []}, status=status.HTTP_200_OK)
        
        arquivos = []
        for arquivo in os.listdir(upload_dir):
            arquivo_path = os.path.join(upload_dir, arquivo)
            if os.path.isfile(arquivo_path):
                stat = os.stat(arquivo_path)
                arquivos.append({
                    'nome': arquivo,
                    'tamanho': stat.st_size,
                    'data_criacao': time.ctime(stat.st_ctime),
                    'hash_id': arquivo.split('_')[0] if '_' in arquivo else 'unknown'
                })
        
        return Response({
            'total_arquivos': len(arquivos),
            'arquivos': arquivos
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response(
            {'error': 'Erro ao listar arquivos', 'details': str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
def salvar_anotacoes_professora(request):
    """
    API endpoint para salvar as anotações adicionais da professora
    """
    try:
        arquivo_hash = request.data.get('arquivo_hash', '')
        anotacoes = request.data.get('anotacoes', '')
        professora = request.data.get('professora', 'Professora')
        
        if not arquivo_hash:
            return Response(
                {'error': 'Hash do arquivo é obrigatório'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Buscar o registro pelo hash do arquivo
        try:
            registro = RegistroEscrita.objects.get(arquivo_hash=arquivo_hash)
            registro.anotacoes_professora = anotacoes
            registro.professora = professora
            registro.save()
            
            return Response({
                'success': True,
                'message': 'Anotações da professora salvas com sucesso',
                'registro_id': registro.id
            }, status=status.HTTP_200_OK)
            
        except RegistroEscrita.DoesNotExist:
            return Response(
                {'error': 'Registro não encontrado'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
    except Exception as e:
        return Response(
            {'error': 'Erro interno no servidor', 'details': str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
def listar_registros_escrita(request):
    """
    API endpoint para listar todos os registros de escrita
    """
    try:
        registros = RegistroEscrita.objects.all().order_by('-data_criacao')
        
        dados = []
        for registro in registros:
            dados.append({
                'id': registro.id,
                'nome_aluno': registro.nome_aluno,
                'turma_id': registro.turma_id,
                'serie_aluno': registro.serie_aluno,
                'etapa_ia': registro.etapa_ia,
                'professora': registro.professora,
                'arquivo_nome': registro.arquivo_nome,
                'arquivo_hash': registro.arquivo_hash,
                'data_criacao': registro.data_criacao.strftime('%d/%m/%Y %H:%M'),
                'tem_anotacoes': bool(registro.anotacoes_professora)
            })
        
        return Response({
            'total_registros': len(dados),
            'registros': dados
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response(
            {'error': 'Erro ao listar registros', 'details': str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
def registros_por_aluno(request, nome_aluno=None):
    """
    API endpoint para buscar registros de escrita e desenho de um aluno específico.
    Suporta filtros opcionais: data_inicio, data_fim.
    """
    try:
        if not nome_aluno:
            nome_aluno = request.GET.get('nome_aluno', '')
        data_inicio = request.GET.get('data_inicio')
        data_fim = request.GET.get('data_fim')

        # Buscar registros de escrita
        registros_escrita = RegistroEscrita.objects.filter(
            nome_aluno__icontains=nome_aluno
        )
        if data_inicio:
            registros_escrita = registros_escrita.filter(data_criacao__date__gte=data_inicio)
        if data_fim:
            registros_escrita = registros_escrita.filter(data_criacao__date__lte=data_fim)
        registros_escrita = registros_escrita.order_by('-data_criacao')

        registros_data = []

        # Processar registros de escrita
        for registro in registros_escrita:
            analise_resumida = registro.analise_detalhada[:120] + '...' if len(registro.analise_detalhada) > 120 else registro.analise_detalhada
            
            registros_data.append({
                'id': f"escrita_{registro.id}",
                'tipo': 'escrita',
                'nome_aluno': registro.nome_aluno,
                'data_criacao': registro.data_criacao.strftime('%d/%m/%Y às %H:%M'),
                'data_criacao_timestamp': registro.data_criacao.timestamp(),
                'etapa_ia': registro.etapa_ia,
                'analise_resumida': analise_resumida,
                'analise_completa': registro.analise_detalhada,
                'anotacoes_professora': registro.anotacoes_professora or '',
                'professora': registro.professora,
                'arquivo_nome': registro.arquivo_nome,
                'arquivo_hash': registro.arquivo_hash,
                'serie_aluno': registro.serie_aluno,
                'turma_id': registro.turma_id,
                'tamanho_arquivo': registro.tamanho_arquivo,
                'tipo_arquivo': registro.tipo_arquivo
            })
        
        # Buscar registros de desenho
        registros_desenho = RegistroDesenho.objects.filter(
            nome_aluno__icontains=nome_aluno
        )
        if data_inicio:
            registros_desenho = registros_desenho.filter(data_criacao__date__gte=data_inicio)
        if data_fim:
            registros_desenho = registros_desenho.filter(data_criacao__date__lte=data_fim)
        registros_desenho = registros_desenho.order_by('-data_criacao')
        
        # Processar registros de desenho
        for registro in registros_desenho:
            analise_resumida = registro.analise_detalhada[:120] + '...' if len(registro.analise_detalhada) > 120 else registro.analise_detalhada
            
            registros_data.append({
                'id': f"desenho_{registro.id}",
                'tipo': 'desenho',
                'nome_aluno': registro.nome_aluno,
                'data_criacao': registro.data_criacao.strftime('%d/%m/%Y às %H:%M'),
                'data_criacao_timestamp': registro.data_criacao.timestamp(),
                'etapa_ia': registro.fase_desenho,
                'elementos_detectados': registro.elementos_detectados,
                'atividade': registro.atividade,
                'contexto': registro.contexto,
                'analise_resumida': analise_resumida,
                'analise_completa': registro.analise_detalhada,
                'anotacoes_professora': registro.anotacoes_professora or '',
                'professora': registro.professora,
                'arquivo_nome': registro.arquivo_nome,
                'arquivo_hash': registro.arquivo_hash,
                'serie_aluno': registro.serie_aluno,
                'turma_id': registro.turma_id,
                'tamanho_arquivo': registro.tamanho_arquivo,
                'tipo_arquivo': registro.tipo_arquivo
            })
        
        # Ordenar todos os registros por data decrescente
        registros_ordenados = sorted(registros_data, key=lambda x: x['data_criacao_timestamp'], reverse=True)
        
        # Remover o timestamp para não interferir na serialização
        for registro in registros_ordenados:
            del registro['data_criacao_timestamp']
        
        return Response({
            'success': True,
            'registros': registros_ordenados,
            'total': len(registros_ordenados),
            'total_escrita': len([r for r in registros_ordenados if r['tipo'] == 'escrita']),
            'total_desenho': len([r for r in registros_ordenados if r['tipo'] == 'desenho']),
            'aluno': nome_aluno
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response(
            {'error': 'Erro ao buscar registros do aluno', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
def servir_arquivo(request, arquivo_hash):
    """
    API endpoint para servir arquivos de escrita e desenho.
    Redireciona para URL pré-assinada do S3 ou serve do disco local como fallback.
    """
    try:
        # Buscar registro em escrita ou desenho
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

        arquivo_path = registro.arquivo_path

        # Se arquivo_path é uma S3 key (não começa com / nem com drive letter)
        # ou se o arquivo local não existe, tentar S3
        local_path = arquivo_path if os.path.isabs(arquivo_path) else f"/tmp/nara_storage/{arquivo_path}"
        is_s3_key = not os.path.isabs(arquivo_path) and not os.path.exists(local_path)

        if is_s3_key:
            # arquivo_path já é a S3 key (ex: "desenho/arquivo.jpg")
            s3_key = arquivo_path
            # Para registros antigos com caminho local, reconstruir a key
            if arquivo_path.startswith('uploads/'):
                s3_key = f"{tipo}/{registro.arquivo_nome}"

            url = generate_presigned_url(s3_key)
            if url:
                return redirect(url)
            raise Http404("Arquivo não encontrado no S3")

        # Fallback: servir do disco local
        response = FileResponse(
            open(local_path, 'rb'),
            content_type=registro.tipo_arquivo or 'application/octet-stream'
        )
        response['Content-Disposition'] = f'inline; filename="{registro.arquivo_nome}"'
        response['X-Content-Type-Options'] = 'nosniff'
        return response

    except Http404:
        raise
    except Exception as e:
        return Response(
            {'error': 'Erro ao servir arquivo', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def proxy_imagem_s3(request):
    """
    Proxy para buscar imagem do S3 e retornar como base64 data URL.
    Evita problemas de CORS ao gerar PDF no frontend.
    Recebe: { "url": "https://...s3..." }
    Retorna: { "data_url": "data:image/jpeg;base64,..." }
    """
    url = request.data.get('url', '')
    if not url:
        return Response({'error': 'URL é obrigatória'}, status=status.HTTP_400_BAD_REQUEST)

    # Renovar presigned URL caso esteja expirada
    url = refresh_presigned_url(url)

    try:
        resp = http_requests.get(url, timeout=15)
        resp.raise_for_status()
        content_type = resp.headers.get('Content-Type', 'image/jpeg')
        b64 = base64.b64encode(resp.content).decode('ascii')
        return Response({'data_url': f'data:{content_type};base64,{b64}'})
    except Exception as e:
        return Response(
            {'error': 'Erro ao buscar imagem', 'details': str(e)},
            status=status.HTTP_502_BAD_GATEWAY,
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([UploadRateThrottle])
def upload_e_analise_desenho(request):
    """
    API endpoint para upload de arquivo e análise de desenho.
    Requer autenticação. Rate limit: 10 req/min.
    """
    try:
        # Verificar se o arquivo foi enviado
        if 'arquivo' not in request.FILES:
            return Response(
                {'error': 'Nenhum arquivo foi enviado'}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        allowed, retry_after = check_rate_limit(request, "upload_desenho")
        if not allowed:
            return Response(
                {'error': 'Limite de requisições de upload excedido. Tente novamente em alguns segundos.'},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
                headers={'Retry-After': str(retry_after)}
            )
        
        arquivo = request.FILES['arquivo']
        nome_aluno = request.POST.get('nomeAluno', '')
        serie_aluno = request.POST.get('serieAluno', '')
        turma_id = request.POST.get('turmaId', '')
        atividade = request.POST.get('atividade', 'Desenho Livre')
        contexto = request.POST.get('contexto', '')
        professora = request.POST.get('professora', 'Sistema')

        validation_error = validate_uploaded_file(
            arquivo,
            ALLOWED_IMAGE_MIME_TYPES,
            ALLOWED_IMAGE_EXTENSIONS,
            MAX_IMAGE_SIZE_BYTES,
            "imagem de desenho"
        )
        if validation_error:
            mensagem, status_code = validation_error
            return Response({'error': mensagem}, status=status_code)
        
        # Validar dados obrigatórios
        if not nome_aluno or not serie_aluno:
            return Response(
                {'error': 'Nome do aluno e série são obrigatórios'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Criar diretório de uploads se não existir
        upload_dir = 'uploads/desenho'
        os.makedirs(upload_dir, exist_ok=True)
        
        # Gerar nome de arquivo seguro com hash
        arquivo_nome, file_hash = gerar_nome_arquivo_seguro(nome_aluno, arquivo.name)
        arquivo_path = os.path.join(upload_dir, arquivo_nome)
        
        with open(arquivo_path, 'wb+') as destination:
            for chunk in arquivo.chunks():
                destination.write(chunk)

        with open(arquivo_path, "rb") as f:
            file_bytes = f.read()
            imagem_base64 = base64.b64encode(file_bytes).decode("utf-8")

        # Upload para S3
        s3_key = f"desenho/{arquivo_nome}"
        arquivo_url = None
        try:
            _, arquivo_url = upload_bytes_to_storage(
                key=s3_key,
                content=file_bytes,
                content_type=arquivo.content_type or "image/jpeg",
            )
            if arquivo_url:
                arquivo_path = s3_key
                print(f"[S3] Upload de desenho concluído: {arquivo_url}")
        except Exception as storage_error:
            print(f"[S3] Falha no upload para S3: {storage_error}")
        
        # Log do upload realizado
        print(f"[UPLOAD DESENHO] Arquivo salvo: {arquivo_nome}")
        print(f"[UPLOAD DESENHO] Hash gerado: {file_hash}")
        print(f"[UPLOAD DESENHO] Aluno: {nome_aluno}")
        print(f"[UPLOAD DESENHO] Atividade: {atividade}")

        # Prompt para análise de desenho com OpenAI
        prompt = f"""
 Análise do Desenho Infantil com Base no Desenvolvimento Gráfico
Atue como uma especialista em psicologia do desenho infantil, clonando a sensibilidade de Arno Stern, a escuta ativa de Loris Malaguzzi e os conhecimentos de Luquet e Lowenfeld sobre os estágios gráficos da infância.

Sua missão é analisar o desenho de uma criança com profundidade, delicadeza e escuta genuína. A análise deve considerar tanto aspectos técnicos quanto emocionais, revelando o que o desenho expressa sobre o desenvolvimento e a visão de mundo da criança.

Sua resposta deve conter duas partes obrigatórias:

PARTE 1 – Análise Técnica (objetiva, até 4 linhas)
Classifique o desenho em um dos estágios do desenvolvimento gráfico:
Rabisco desorganizado, Rabisco controlado, Pré-esquemático, Esquemático, Realismo inicial ou Realismo visual.

Observe traços como: organização no espaço, forma humana, uso de cores, presença de detalhes, estrutura narrativa, simetria, proporção etc.

Use linguagem técnica simples, clara e sem excesso de termos acadêmicos.

PARTE 2 – Explicação Popular e Acolhedora (foco nos pais)
Traduza a análise para uma linguagem afetiva, acessível e próxima das famílias.

Explique com carinho o que o desenho da criança nos mostra:
– como ela enxerga o mundo
– o que ela está aprendendo a expressar
– que tipo de pensamento, emoção ou vivência pode estar sendo colocado no papel

Evite termos técnicos como "fase esquemática". Prefira:
“Agora ela está aprendendo a desenhar com mais intenção”,
“Olha como ela já começa a representar pessoas com braços e pernas!”,
“Ela ainda não está preocupada com realidade, mas em mostrar o que sente”.

Inclua metáforas simples, como:
“O papel vira o palco das emoções dela”,
“Ela pinta o que sente mais do que o que vê”,
“O desenho dela é um jeito de conversar com o mundo sem palavras”.

Traga encorajamento e orientação sensível. Por exemplo:
“Mesmo que pareça um rabisco, é uma conversa cheia de intenção”
"""
        
        try:
            # Chamar OpenAI para análise
            print(f"[OPENAI] Enviando prompt para análise do desenho de {nome_aluno}")

            openai_client = get_openai_client()

            def _analise_desenho_openai():
                return openai_client.chat.completions.create(
                    model="gpt-4o",
                    messages=[{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{imagem_base64}"
                                }
                            }
                        ]
                    }],
                    max_tokens=800,
                    temperature=0.7,
                    timeout=IA_REQUEST_TIMEOUT_SECONDS
                )

            response = run_with_timeout(
                _analise_desenho_openai,
                IA_REQUEST_TIMEOUT_SECONDS
            )
            
            analise_completa = response.choices[0].message.content.strip()
            print(f"[OPENAI] Análise de desenho recebida com {len(analise_completa)} caracteres")
            
            # Extrair elementos e fase do desenho
            fase_desenho = "Análise em processamento"
            elementos_detectados = []
            
            # Procurar por fases típicas mencionadas na análise
            fases_possiveis = ['Rabisco', 'Pré-esquemático', 'Esquemático', 'Realismo', 'Pseudonaturalista']
            analise_lower = analise_completa.lower()
            for fase in fases_possiveis:
                if fase.lower() in analise_lower:
                    fase_desenho = fase
                    break
            
            # Procurar por elementos comuns
            elementos_comuns = ['casa', 'sol', 'árvore', 'pessoa', 'animal', 'flor', 'carro', 'família', 'nuvem']
            for elemento in elementos_comuns:
                if elemento in analise_lower:
                    elementos_detectados.append(elemento.title())
            
        except RuntimeError as openai_config_error:
            print(f"[OPENAI ERROR] Configuração ausente: {openai_config_error}")
            analise_completa = f"FALHA NA ANÁLISE TÉCNICA:\nA configuração da OpenAI não está disponível. Configure a variável OPENAI_API_KEY e tente novamente."
            fase_desenho = "Configuração OpenAI ausente"
            elementos_detectados = []
        except TimeoutError:
            analise_completa = (
                "FALHA NA ANÁLISE TÉCNICA:\nTempo limite excedido na análise do desenho. "
                "Envie um arquivo menor ou tente novamente mais tarde."
            )
            fase_desenho = "Tempo excedido"
            elementos_detectados = []
        except Exception as openai_error:
            print(f"[OPENAI ERROR] Erro na chamada da OpenAI: {openai_error}")
            # Fallback para análise mock em caso de erro
            analise_completa = f"ANÁLISE TÉCNICA:\nO desenho de {nome_aluno} está em processo de análise. Aguarde o processamento completo.\n\nPARA FAMÍLIA:\nEstamos analisando o desenho de {nome_aluno} com muito carinho. Em breve teremos uma análise detalhada sobre o desenvolvimento artístico."
            fase_desenho = "Aguardando análise"
            elementos_detectados = ["Elementos em análise"]

        # Salvar no banco de dados
        try:
            registro = RegistroDesenho.objects.create(
                nome_aluno=nome_aluno,
                turma_id=turma_id,
                serie_aluno=serie_aluno,
                atividade=atividade,
                contexto=contexto,
                arquivo_nome=arquivo_nome,
                arquivo_hash=file_hash,
                arquivo_path=arquivo_path,
                arquivo_original=arquivo.name,
                tamanho_arquivo=arquivo.size,
                tipo_arquivo=arquivo.content_type or 'image/unknown',
                fase_desenho=fase_desenho,
                elementos_detectados=elementos_detectados,
                analise_detalhada=analise_completa,
                professora=professora,
                anotacoes_professora=""
            )
            
            print(f"[DATABASE] Registro de desenho salvo com ID: {registro.id}")
            
        except Exception as db_error:
            print(f"[DATABASE ERROR] Erro ao salvar desenho no banco: {db_error}")

        resultado = {
            'success': True,
            'arquivo_salvo': arquivo_path,
            'arquivo_nome': arquivo_nome,
            'arquivo_hash': file_hash,
            'arquivo_original': arquivo.name,
            'arquivo_url': arquivo_url or arquivo_path,
            'nomeAluno': nome_aluno,
            'serieAluno': serie_aluno,
            'turmaId': turma_id,
            'atividade': atividade,
            'contexto': contexto,
            'analise': {
                'descricao': analise_completa,
                'fase_desenho': fase_desenho,
                'elementos': elementos_detectados,
                'desenvolvimento': fase_desenho,
                'arquivo_processado': True,
                'arquivo_id': file_hash,
                'tamanho_arquivo': arquivo.size,
                'tipo_arquivo': arquivo.content_type,
                'data_analise': "2025-08-03"
            }
        }
        
        return Response(resultado, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response(
            {'error': 'Erro interno no servidor', 'details': str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
def listar_registros_desenho(request):
    """
    API endpoint para listar todos os registros de desenho
    """
    try:
        registros = RegistroDesenho.objects.all().order_by('-data_criacao')
        
        dados = []
        for registro in registros:
            dados.append({
                'id': registro.id,
                'tipo': 'desenho',
                'nome_aluno': registro.nome_aluno,
                'turma_id': registro.turma_id,
                'serie_aluno': registro.serie_aluno,
                'fase_desenho': registro.fase_desenho,
                'elementos_detectados': registro.elementos_detectados,
                'atividade': registro.atividade,
                'contexto': registro.contexto,
                'professora': registro.professora,
                'arquivo_nome': registro.arquivo_nome,
                'arquivo_hash': registro.arquivo_hash,
                'data_criacao': registro.data_criacao.strftime('%d/%m/%Y %H:%M'),
                'data_criacao_iso': registro.data_criacao.isoformat(),
                'tem_anotacoes': bool(registro.anotacoes_professora),
                'analise_resumida': registro.analise_detalhada[:150] + '...' if len(registro.analise_detalhada) > 150 else registro.analise_detalhada,
                'analise_completa': registro.analise_detalhada
            })
        
        return Response({
            'total_registros': len(dados),
            'registros': dados
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response(
            {'error': 'Erro ao listar registros de desenho', 'details': str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
def listar_todas_producoes(request):
    """
    API endpoint para listar todas as produções (escrita + desenho) ordenadas por data
    """
    try:
        # Buscar registros de escrita
        registros_escrita = RegistroEscrita.objects.all()
        producoes = []
        
        for registro in registros_escrita:
            producoes.append({
                'id': f"escrita_{registro.id}",
                'tipo': 'escrita',
                'nome_aluno': registro.nome_aluno,
                'turma_id': registro.turma_id,
                'serie_aluno': registro.serie_aluno,
                'etapa_detectada': registro.etapa_ia,
                'atividade': 'Análise de Escrita',
                'professora': registro.professora,
                'arquivo_nome': registro.arquivo_nome,
                'arquivo_hash': registro.arquivo_hash,
                'data_criacao': registro.data_criacao,
                'data_criacao_str': registro.data_criacao.strftime('%d/%m/%Y %H:%M'),
                'tem_anotacoes': bool(registro.anotacoes_professora),
                'analise_resumida': registro.analise_detalhada[:150] + '...' if len(registro.analise_detalhada) > 150 else registro.analise_detalhada,
                'analise_completa': registro.analise_detalhada,
                'icone': 'PenTool',
                'cor': 'roxo'
            })
        
        # Buscar registros de desenho
        registros_desenho = RegistroDesenho.objects.all()
        
        for registro in registros_desenho:
            producoes.append({
                'id': f"desenho_{registro.id}",
                'tipo': 'desenho',
                'nome_aluno': registro.nome_aluno,
                'turma_id': registro.turma_id,
                'serie_aluno': registro.serie_aluno,
                'etapa_detectada': registro.fase_desenho,
                'elementos_detectados': registro.elementos_detectados,
                'atividade': registro.atividade,
                'contexto': registro.contexto,
                'professora': registro.professora,
                'arquivo_nome': registro.arquivo_nome,
                'arquivo_hash': registro.arquivo_hash,
                'data_criacao': registro.data_criacao,
                'data_criacao_str': registro.data_criacao.strftime('%d/%m/%Y %H:%M'),
                'tem_anotacoes': bool(registro.anotacoes_professora),
                'analise_resumida': registro.analise_detalhada[:150] + '...' if len(registro.analise_detalhada) > 150 else registro.analise_detalhada,
                'analise_completa': registro.analise_detalhada,
                'icone': 'Palette',
                'cor': 'azul'
            })
        
        # Ordenar todas as produções por data decrescente
        producoes_ordenadas = sorted(producoes, key=lambda x: x['data_criacao'], reverse=True)
        
        # Remover o campo data_criacao (datetime) para serialização JSON
        for producao in producoes_ordenadas:
            del producao['data_criacao']
        
        return Response({
            'total_producoes': len(producoes_ordenadas),
            'total_escrita': len([p for p in producoes_ordenadas if p['tipo'] == 'escrita']),
            'total_desenho': len([p for p in producoes_ordenadas if p['tipo'] == 'desenho']),
            'producoes': producoes_ordenadas
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response(
            {'error': 'Erro ao listar produções', 'details': str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def salvar_observacoes_transcricao(request):
    """
    Salva as observações editadas da transcrição de áudio no banco de dados.
    Requer autenticação.
    """
    try:
        # Dados enviados pelo frontend
        turma_id = request.data.get('turma_id')
        professora_id = request.data.get('professora_id') 
        professora_nome = request.data.get('professora_nome', 'Sistema')
        transcricao_completa = request.data.get('transcricao_completa', '')
        alunos_observacoes = request.data.get('alunos_observacoes', [])
        metadados = request.data.get('metadados', {})
        
        print(f"[SALVAR TRANSCRICAO] Recebidos dados: turma={turma_id}, prof={professora_nome}, alunos={len(alunos_observacoes)}")
        
        # Validações
        if not turma_id:
            return Response({'error': 'ID da turma é obrigatório'}, status=status.HTTP_400_BAD_REQUEST)
        
        if not professora_id:
            return Response({'error': 'ID da professora é obrigatório'}, status=status.HTTP_400_BAD_REQUEST)
        
        if not alunos_observacoes:
            return Response({'error': 'Pelo menos uma observação de aluno é obrigatória'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Buscar informações da turma para validação
        turma_nome = f'Turma {turma_id}'  # Valor padrão
        
        observacoes_salvas = []
        observacoes_erro = []
        
        # Data atual para as observações
        data_observacao = timezone.now().date()
        
        # Salvar observação para cada aluno usando Django ORM
        for obs_aluno in alunos_observacoes:
            try:
                aluno_nome = obs_aluno.get('aluno_nome', '').strip()
                observacao_texto = obs_aluno.get('observacao', '').strip()

                if not aluno_nome or not observacao_texto:
                    print(f"[AVISO] Observação ignorada - nome ou texto vazio: {aluno_nome}")
                    continue

                # ID opcional da criança (se disponível no payload)
                crianca_id = obs_aluno.get('crianca_id', None)

                # Preparar metadados da IA
                metadados_ia = {
                    'origem': 'transcricao_audio',
                    'confianca': obs_aluno.get('confianca', 0),
                    'nome_original_detectado': obs_aluno.get('nome_original_detectado', ''),
                    'metodo_match': obs_aluno.get('metodo_match', ''),
                    'score_similaridade': obs_aluno.get('score_similaridade', 0),
                    'timestamp_audio': {
                        'inicio': obs_aluno.get('timestamp_inicio', ''),
                        'fim': obs_aluno.get('timestamp_fim', '')
                    },
                    'modelo_ia': metadados.get('modelo_ia_usado', 'whisper-1'),
                    'qualidade_audio': metadados.get('qualidade_audio', 'boa'),
                }

                # Criar observação no banco de dados usando Django ORM
                observacao = ObservacaoTranscricao.objects.create(
                    aluno_nome=aluno_nome,
                    crianca_id=crianca_id,
                    observacao_texto=observacao_texto,
                    tipo_observacao='TRANSCRICAO_IA',
                    data_observacao=data_observacao,
                    turma_id=turma_id,
                    turma_nome=turma_nome,
                    professora_id=professora_id,
                    professora_nome=professora_nome,
                    metadados_ia=metadados_ia,
                    transcricao_completa=transcricao_completa[:2000] if len(transcricao_completa) > 2000 else transcricao_completa
                )

                observacoes_salvas.append({
                    'id': observacao.id,
                    'aluno_nome': aluno_nome,
                    'crianca_id': crianca_id,
                    'observacao': observacao_texto[:100] + '...' if len(observacao_texto) > 100 else observacao_texto,
                    'data_observacao': data_observacao.isoformat(),
                    'metadados': metadados_ia
                })

                print(f"[SALVO] Observação para {aluno_nome} registrada com ID: {observacao.id}")
                print(f"[DETALHES] Observação: {observacao_texto[:50]}...")

            except Exception as obs_error:
                error_msg = f"Erro ao processar observação para {obs_aluno.get('aluno_nome', 'Aluno desconhecido')}: {str(obs_error)}"
                print(f"[ERRO OBSERVACAO] {error_msg}")
                observacoes_erro.append(error_msg)
        
        # Preparar resposta
        total_enviadas = len(alunos_observacoes)
        total_salvas = len(observacoes_salvas)
        total_erros = len(observacoes_erro)
        
        resultado = {
            'sucesso': total_salvas > 0,
            'total_enviadas': total_enviadas,
            'total_salvas': total_salvas,
            'total_erros': total_erros,
            'observacoes_salvas': observacoes_salvas,
            'erros': observacoes_erro if observacoes_erro else None,
            'turma_id': turma_id,
            'turma_nome': turma_nome,
            'professora_nome': professora_nome,
            'data_observacao': data_observacao.isoformat(),
            'metadados_salvamento': {
                'timestamp': timezone.now().isoformat(),
                'modelo_ia': metadados.get('modelo_ia_usado', 'whisper-1'),
                'total_alunos_detectados': metadados.get('total_alunos', total_enviadas),
                'confianca_geral': metadados.get('confianca_geral', 0)
            }
        }
        
        if total_salvas == 0:
            return Response({
                'error': 'Nenhuma observação foi salva',
                'detalhes': resultado
            }, status=status.HTTP_400_BAD_REQUEST)
        elif total_erros > 0:
            print(f"[RESULTADO PARCIAL] {total_salvas}/{total_enviadas} observações salvas, {total_erros} erros")
            return Response(resultado, status=status.HTTP_206_PARTIAL_CONTENT)
        else:
            print(f"[RESULTADO SUCESSO] {total_salvas}/{total_enviadas} observações salvas com sucesso")
            return Response(resultado, status=status.HTTP_201_CREATED)
            
    except Exception as e:
        print(f"[ERRO GERAL] Erro ao salvar observações da transcrição: {str(e)}")
        return Response(
            {'error': 'Erro interno no servidor ao salvar observações', 'details': str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
def buscar_observacoes_transcricao(request):
    """
    Busca observações de transcrição para um aluno específico usando Django ORM.
    Suporta filtros por turma_id e data_inicio/data_fim.
    """
    from django.db.models import Q

    try:
        nome_aluno = request.GET.get('nome_aluno')
        crianca_id = (request.GET.get('crianca_id') or '').strip()
        turma_id = request.GET.get('turma_id')
        data_inicio = request.GET.get('data_inicio')
        data_fim = request.GET.get('data_fim')

        # Vínculo com a criança: `crianca_id` é o identificador confiável, mas
        # está vazio na maioria dos registros antigos — daí o fallback por nome.
        # O casamento por nome é EXATO de propósito: com `icontains`, o bloco de
        # relatos da "Ana" trazia junto os de "Ana Clara" e "Mariana", sem a
        # professora ter como saber de quem era cada um. Mesma estratégia de
        # `listar_observacoes_transcricao_crianca` em views_rest.
        nome_aluno_busca = (nome_aluno or '').strip()
        if crianca_id and not nome_aluno_busca:
            nome_aluno_busca = (
                Crianca.objects.filter(id=crianca_id)
                .values_list('nome_completo', flat=True)
                .first()
            ) or ''

        clausulas = []
        if crianca_id:
            clausulas.append(Q(crianca_id=crianca_id))
        if nome_aluno_busca:
            clausulas.append(Q(aluno_nome__iexact=nome_aluno_busca))

        if not clausulas:
            return Response(
                {'error': 'Informe crianca_id ou nome_aluno'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        filtro_vinculo = clausulas[0]
        for clausula in clausulas[1:]:
            filtro_vinculo |= clausula

        queryset = ObservacaoTranscricao.objects.filter(filtro_vinculo)

        # Filtros opcionais
        if turma_id:
            queryset = queryset.filter(turma_id=turma_id)

        if data_inicio:
            queryset = queryset.filter(data_observacao__gte=data_inicio)

        if data_fim:
            queryset = queryset.filter(data_observacao__lte=data_fim)

        # Ordenar por data (mais recente primeiro)
        queryset = queryset.order_by('-data_observacao', '-data_criacao')

        # Limitar resultados para performance
        queryset = queryset[:100]

        # Serializar resultados
        observacoes_encontradas = []
        for obs in queryset:
            observacoes_encontradas.append({
                'id': obs.id,
                'texto': obs.observacao_texto,
                'data': obs.data_criacao.isoformat(),
                'data_observacao': obs.data_observacao.isoformat(),
                'professora': obs.professora_nome,
                # Necessário para o frontend decidir quem pode excluir o relato.
                'professora_id': obs.professora_id,
                'turma_id': obs.turma_id,
                'turma_nome': obs.turma_nome,
                'metadados': obs.metadados_ia,
                'tipo': obs.tipo_observacao,
                'crianca_id': obs.crianca_id
            })

        return Response({
            'observacoes': observacoes_encontradas,
            'total': len(observacoes_encontradas),
            'aluno_nome': nome_aluno_busca
        })

    except Exception as e:
        print(f"[ERRO] Erro ao buscar observações da transcrição: {str(e)}")
        return Response(
            {'error': 'Erro interno no servidor', 'details': str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
def listar_habilidades_bncc(request):
    """
    Lista todas as habilidades da BNCC ativas
    """
    try:
        componente = request.GET.get('componente', None)
        ano_serie = request.GET.get('ano_serie', None)
        
        habilidades = HabilidadeBNCC.objects.filter(ativa=True)
        
        if componente:
            habilidades = habilidades.filter(componente_curricular__icontains=componente)
        
        if ano_serie:
            habilidades = habilidades.filter(ano_serie__icontains=ano_serie)
        
        dados = []
        for habilidade in habilidades:
            dados.append({
                'id': habilidade.id,
                'codigo': habilidade.codigo,
                'descricao': habilidade.descricao,
                'componente_curricular': habilidade.componente_curricular,
                'ano_serie': habilidade.ano_serie,
                'campo_atuacao': habilidade.campo_atuacao
            })
        
        return Response({
            'habilidades': dados,
            'total': len(dados)
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response(
            {'error': 'Erro ao listar habilidades BNCC', 'details': str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['POST'])
def criar_habilidade_bncc(request):
    """
    Cria uma nova habilidade da BNCC
    """
    try:
        data = request.data
        
        # Validar campos obrigatórios
        campos_obrigatorios = ['codigo', 'descricao', 'componente_curricular', 'ano_serie']
        for campo in campos_obrigatorios:
            if not data.get(campo):
                return Response(
                    {'error': f'Campo {campo} é obrigatório'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Verificar se já existe uma habilidade com o mesmo código
        if HabilidadeBNCC.objects.filter(codigo=data['codigo']).exists():
            return Response(
                {'error': 'Já existe uma habilidade com este código'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Criar a habilidade
        habilidade = HabilidadeBNCC.objects.create(
            codigo=data['codigo'],
            descricao=data['descricao'],
            componente_curricular=data['componente_curricular'],
            ano_serie=data['ano_serie'],
            campo_atuacao=data.get('campo_atuacao', ''),
            ativa=True
        )
        
        return Response({
            'success': True,
            'message': 'Habilidade BNCC criada com sucesso',
            'habilidade': {
                'id': habilidade.id,
                'codigo': habilidade.codigo,
                'descricao': habilidade.descricao,
                'componente_curricular': habilidade.componente_curricular,
                'ano_serie': habilidade.ano_serie,
                'campo_atuacao': habilidade.campo_atuacao
            }
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        return Response(
            {'error': 'Erro ao criar habilidade BNCC', 'details': str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
def criar_planejamento_semanal(request):
    """
    Cria um novo planejamento semanal (formato simplificado: cada dia tem
    apenas atividades_propostas, prompt_ia, arquivo_* e habilidades).
    """
    try:
        turma_id = request.data.get('turma_id')
        semana_inicio_raw = request.data.get('semana_inicio')
        professora_id = request.data.get('professora_id')
        professora_nome = request.data.get('professora_nome')
        planejamento_dias = request.data.get('dias', {})

        if not all([turma_id, semana_inicio_raw, professora_id, professora_nome]):
            return Response(
                {'error': 'Campos obrigatórios: turma_id, semana_inicio, professora_id, professora_nome'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            semana_inicio = parse_date(semana_inicio_raw)
        except (TypeError, ValueError):
            semana_inicio = None

        if not semana_inicio:
            return Response(
                {'error': 'semana_inicio inválida. Use o formato YYYY-MM-DD.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Calcular fim da semana (sexta-feira)
        dias_ate_sexta = 4 - semana_inicio.weekday()  # weekday(): 0=segunda, 4=sexta
        semana_fim = semana_inicio + timedelta(days=dias_ate_sexta)

        # Verificar se já existe planejamento para esta turma/semana
        planejamento_existente = PlanejamentoSemanal.objects.filter(
            turma_id=turma_id,
            semana_inicio=semana_inicio
        ).first()

        if planejamento_existente:
            return Response(
                {'error': 'Já existe um planejamento para esta turma nesta semana'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Criar planejamento semanal
        planejamento = PlanejamentoSemanal.objects.create(
            turma_id=turma_id,
            semana_inicio=semana_inicio,
            semana_fim=semana_fim,
            professora_id=professora_id,
            professora_nome=professora_nome,
        )

        dias_semana = ['segunda', 'terca', 'quarta', 'quinta', 'sexta']
        dias_criados = []

        for i, dia in enumerate(dias_semana):
            data_dia = semana_inicio + timedelta(days=i)
            dados_dia = planejamento_dias.get(dia, {}) or {}

            planejamento_diario = PlanejamentoDiario.objects.create(
                planejamento_semanal=planejamento,
                dia_semana=dia,
                data=data_dia,
                atividades_propostas=dados_dia.get('atividades_propostas', '') or '',
                prompt_ia=dados_dia.get('prompt_ia', '') or '',
                arquivo_storage_key=dados_dia.get('arquivo_storage_key') or None,
                arquivo_nome_original=dados_dia.get('arquivo_nome_original') or None,
                arquivo_content_type=dados_dia.get('arquivo_content_type') or None,
            )

            # Adicionar habilidades da BNCC para este dia. Aceita ID (legado)
            # ou código (formato novo vindo de perguntas_bncc).
            habilidades_ids = dados_dia.get('habilidades', []) or []
            for ref in habilidades_ids:
                habilidade = _resolver_habilidade_bncc(ref)
                if habilidade is None:
                    logger.warning("Habilidade BNCC não encontrada: %s", ref)
                    continue
                PlanejamentoHabilidade.objects.create(
                    planejamento_diario=planejamento_diario,
                    habilidade_bncc=habilidade,
                )

            dias_criados.append({
                'dia': dia,
                'data': data_dia.isoformat(),
                'habilidades_count': len(habilidades_ids),
            })

        return Response({
            'success': True,
            'planejamento_id': planejamento.id,
            'turma_id': turma_id,
            'semana_inicio': semana_inicio.isoformat(),
            'semana_fim': semana_fim.isoformat(),
            'dias_criados': dias_criados,
        }, status=status.HTTP_201_CREATED)

    except Exception as e:
        logger.exception("Erro ao criar planejamento semanal.")
        return Response(
            {'error': 'Erro ao criar planejamento semanal', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


def _resolver_habilidade_bncc(referencia):
    """
    Aceita referência como id (UUID/inteiro) OU como código BNCC (ex.: EI03EO01).
    Devolve a HabilidadeBNCC correspondente ou None.
    """
    if referencia is None:
        return None
    ref = str(referencia).strip()
    if not ref:
        return None
    # Tenta como id primeiro (numérico ou UUID), depois como código.
    try:
        return HabilidadeBNCC.objects.filter(id=ref).first() or HabilidadeBNCC.objects.filter(codigo=ref).first()
    except (ValueError, TypeError):
        return HabilidadeBNCC.objects.filter(codigo=ref).first()

@api_view(['GET'])
def buscar_planejamento_semanal(request, turma_id):
    """
    Busca o planejamento semanal de uma turma para uma semana específica
    no formato simplificado (4 campos por dia + arquivo).
    """
    from .services.planejamento_ia import regenerar_url_arquivo

    try:
        semana_inicio = request.GET.get('semana_inicio')
        if not semana_inicio:
            return Response(
                {'error': 'Parâmetro semana_inicio é obrigatório'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            semana_inicio_date = parse_date(semana_inicio)
        except (TypeError, ValueError):
            semana_inicio_date = None

        if not semana_inicio_date:
            return Response(
                {'error': 'Parâmetro semana_inicio inválido. Use o formato YYYY-MM-DD.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        planejamento = PlanejamentoSemanal.objects.filter(
            turma_id=turma_id,
            semana_inicio=semana_inicio_date
        ).first()

        if not planejamento:
            return Response({
                'encontrado': False,
                'planejamento': None,
            }, status=status.HTTP_200_OK)

        dias_data = {}
        for dia_obj in planejamento.dias.all():
            habilidades = []
            for ph in dia_obj.habilidades.select_related('habilidade_bncc').all():
                habilidades.append({
                    'id': ph.habilidade_bncc.id,
                    'codigo': ph.habilidade_bncc.codigo,
                    'descricao': ph.habilidade_bncc.descricao,
                    'componente': ph.habilidade_bncc.componente_curricular,
                })

            dias_data[dia_obj.dia_semana] = {
                'atividades_propostas': dia_obj.atividades_propostas or '',
                'prompt_ia': dia_obj.prompt_ia or '',
                'arquivo_storage_key': dia_obj.arquivo_storage_key or None,
                'arquivo_url': regenerar_url_arquivo(dia_obj.arquivo_storage_key),
                'arquivo_nome_original': dia_obj.arquivo_nome_original or None,
                'arquivo_content_type': dia_obj.arquivo_content_type or None,
                'habilidades': habilidades,
                'data': dia_obj.data.isoformat(),
            }

        resultado = {
            'encontrado': True,
            'planejamento': {
                'id': planejamento.id,
                'turma_id': planejamento.turma_id,
                'semana_inicio': planejamento.semana_inicio.isoformat(),
                'semana_fim': planejamento.semana_fim.isoformat(),
                'professora_nome': planejamento.professora_nome,
                'data_criacao': planejamento.data_criacao.isoformat(),
                'data_modificacao': planejamento.data_modificacao.isoformat(),
                'dias': dias_data,
            }
        }

        return Response(resultado, status=status.HTTP_200_OK)

    except Exception as e:
        logger.exception("Erro ao buscar planejamento semanal.")
        return Response(
            {'error': 'Erro ao buscar planejamento semanal', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['PUT'])
def atualizar_planejamento_semanal(request, planejamento_id):
    """
    Atualiza um planejamento semanal existente. Quando o arquivo de um dia
    troca (ou é removido), o objeto antigo é apagado do S3 para evitar lixo.
    """
    from .services.planejamento_ia import remover_arquivo_planejamento

    try:
        planejamento = PlanejamentoSemanal.objects.get(id=planejamento_id)

        planejamento_dias = request.data.get('dias', {}) or {}

        for dia_nome, dados_dia in planejamento_dias.items():
            if not isinstance(dados_dia, dict):
                continue
            dia_obj = planejamento.dias.filter(dia_semana=dia_nome).first()
            if not dia_obj:
                continue

            if 'atividades_propostas' in dados_dia:
                dia_obj.atividades_propostas = dados_dia.get('atividades_propostas') or ''
            if 'prompt_ia' in dados_dia:
                dia_obj.prompt_ia = dados_dia.get('prompt_ia') or ''

            # Arquivo: detectar troca/remoção e limpar S3 do anterior.
            if 'arquivo_storage_key' in dados_dia:
                novo_key = dados_dia.get('arquivo_storage_key') or None
                key_anterior = dia_obj.arquivo_storage_key
                if key_anterior and key_anterior != novo_key:
                    remover_arquivo_planejamento(key_anterior)
                dia_obj.arquivo_storage_key = novo_key
                dia_obj.arquivo_nome_original = dados_dia.get('arquivo_nome_original') or None
                dia_obj.arquivo_content_type = dados_dia.get('arquivo_content_type') or None

            dia_obj.save()

            if 'habilidades' in dados_dia:
                dia_obj.habilidades.all().delete()
                for ref in dados_dia.get('habilidades') or []:
                    habilidade = _resolver_habilidade_bncc(ref)
                    if habilidade is None:
                        logger.warning("Habilidade BNCC não encontrada: %s", ref)
                        continue
                    PlanejamentoHabilidade.objects.create(
                        planejamento_diario=dia_obj,
                        habilidade_bncc=habilidade,
                    )

        # Atualiza data_modificacao do semanal mesmo sem campos próprios novos.
        planejamento.save(update_fields=['data_modificacao'])

        return Response({
            'success': True,
            'message': 'Planejamento atualizado com sucesso',
            'planejamento_id': planejamento.id,
        }, status=status.HTTP_200_OK)

    except PlanejamentoSemanal.DoesNotExist:
        return Response(
            {'error': 'Planejamento não encontrado'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.exception("Erro ao atualizar planejamento semanal.")
        return Response(
            {'error': 'Erro ao atualizar planejamento', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
def listar_planejamentos_turma(request, turma_id):
    """
    Lista todos os planejamentos semanais de uma turma
    """
    try:
        # Filtros opcionais
        inicio_periodo = request.GET.get('inicio_periodo')
        fim_periodo = request.GET.get('fim_periodo')
        
        planejamentos = PlanejamentoSemanal.objects.filter(turma_id=turma_id)
        
        if inicio_periodo:
            planejamentos = planejamentos.filter(semana_inicio__gte=inicio_periodo)
        if fim_periodo:
            planejamentos = planejamentos.filter(semana_inicio__lte=fim_periodo)
            
        planejamentos = planejamentos.order_by('-semana_inicio')
        
        dados = []
        for planejamento in planejamentos:
            # Buscar planejamentos diários relacionados
            planejamentos_diarios = PlanejamentoDiario.objects.filter(
                planejamento_semanal=planejamento
            )
            
            # Definir ordem dos dias da semana
            ordem_dias = ['segunda', 'terca', 'quarta', 'quinta', 'sexta']
            
            dias_dados = []
            for dia_nome in ordem_dias:
                try:
                    dia = planejamentos_diarios.get(dia_semana=dia_nome)
                    
                    # Buscar habilidades do dia
                    habilidades_dia = PlanejamentoHabilidade.objects.filter(
                        planejamento_diario=dia
                    ).select_related('habilidade_bncc')
                    
                    habilidades = []
                    for ph in habilidades_dia:
                        habilidades.append({
                            'id': ph.habilidade_bncc.id,
                            'codigo': ph.habilidade_bncc.codigo,
                            'descricao': ph.habilidade_bncc.descricao
                        })
                    
                    dias_dados.append({
                        'id': dia.id,
                        'dia_semana': dia.dia_semana,
                        'atividades_propostas': dia.atividades_propostas,
                        'arquivo_nome_original': dia.arquivo_nome_original,
                        'habilidades': habilidades,
                    })
                except PlanejamentoDiario.DoesNotExist:
                    # Se não houver planejamento para este dia, pular
                    continue
            
            dados.append({
                'id': planejamento.id,
                'semana_inicio': planejamento.semana_inicio.strftime('%Y-%m-%d'),
                'semana_fim': planejamento.semana_fim.strftime('%Y-%m-%d'),
                'data_criacao': planejamento.data_criacao.strftime('%Y-%m-%d %H:%M:%S'),
                'data_modificacao': planejamento.data_modificacao.strftime('%Y-%m-%d %H:%M:%S'),
                'dias': dias_dados
            })
        
        return Response({
            'planejamentos': dados,
            'total': len(dados)
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response(
            {'error': 'Erro ao listar planejamentos da turma', 'details': str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# gerar_relatorio and all helpers moved to:
#   views/relatorio.py  — HTTP layer
#   services/relatorio.py — business logic


# =============================================================================
# ENDPOINTS DE PORTFÓLIO (Produções N-to-N)
# =============================================================================

@csrf_exempt
@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([UploadRateThrottle])
def upload_logo_instituicao(request, instituicao_id):
    """
    Upload de logo da instituição para S3 e atualização do campo logo_url.
    """
    try:
        if request.user.perfil not in ['admin', 'coordenador']:
            return Response({'error': 'Sem permissão'}, status=status.HTTP_403_FORBIDDEN)

        if 'arquivo' not in request.FILES:
            return Response(
                {'error': 'Nenhum arquivo foi enviado'},
                status=status.HTTP_400_BAD_REQUEST
            )

        arquivo = request.FILES['arquivo']
        validation_error = validate_uploaded_file(
            arquivo,
            ALLOWED_IMAGE_MIME_TYPES,
            ALLOWED_IMAGE_EXTENSIONS,
            MAX_IMAGE_SIZE_BYTES,
            "logo"
        )
        if validation_error:
            mensagem, status_code = validation_error
            return Response({'error': mensagem}, status=status_code)

        instituicao = Instituicao.objects.get(id=instituicao_id)

        arquivo.seek(0)
        file_hash = hashlib.sha256(arquivo.read()).hexdigest()
        arquivo.seek(0)
        extensao = os.path.splitext(arquivo.name)[1].lower()
        storage_path = f"logos/{instituicao_id}/{file_hash}{extensao}"

        storage_key, arquivo_url = upload_bytes_to_storage(
            storage_path,
            arquivo.read(),
            arquivo.content_type
        )

        # Antes salvava só logo_url (URL pré-assinada, expira em 1h).
        # Agora também persiste a storage_key, que é permanente, para
        # permitir regenerar a URL sob demanda quando ela expirar.
        instituicao.logo_storage_key = storage_key
        instituicao.logo_url = arquivo_url
        instituicao.save(update_fields=['logo_storage_key', 'logo_url'])

        logger.info(
            "Logo da instituição atualizado.",
            extra={"instituicao_id": str(instituicao_id), "storage_key": storage_key},
        )

        return Response({'success': True, 'logo_url': arquivo_url}, status=status.HTTP_200_OK)
    except Instituicao.DoesNotExist:
        return Response(
            {'error': 'Instituição não encontrada'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.exception("Erro ao fazer upload do logo da instituição.")
        return Response(
            {'error': 'Erro ao fazer upload do logo', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@csrf_exempt
@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([UploadRateThrottle])
def upload_producao_crianca(request):
    """
    Upload de produção da criança (mídia simples) com armazenamento no S3.
    """
    try:
        if 'arquivo' not in request.FILES:
            return Response(
                {'error': 'Nenhum arquivo foi enviado'},
                status=status.HTTP_400_BAD_REQUEST
            )

        arquivo = request.FILES['arquivo']
        crianca_id = request.POST.get('crianca_id', '')
        turma_id = request.POST.get('turma_id', '')
        professor_id = request.POST.get('professor_id', '')
        instituicao_id = request.POST.get('instituicao_id', '')
        tipo = request.POST.get('tipo') or request.POST.get('tipo_producao') or 'midia'
        descricao = request.POST.get('descricao', '')
        titulo = request.POST.get('titulo', '')
        projeto = request.POST.get('projeto', '')
        data_registro_str = request.POST.get('data_registro', '')

        if not crianca_id or not turma_id or not professor_id:
            return Response(
                {'error': 'crianca_id, turma_id e professor_id são obrigatórios'},
                status=status.HTTP_400_BAD_REQUEST
            )

        validation_error = validate_uploaded_file(
            arquivo,
            ALLOWED_IMAGE_MIME_TYPES,
            ALLOWED_IMAGE_EXTENSIONS,
            MAX_IMAGE_SIZE_BYTES,
            "imagem"
        )
        if validation_error:
            mensagem, status_code = validation_error
            return Response({'error': mensagem}, status=status_code)

        data_registro = parse_date(data_registro_str) if data_registro_str else timezone.now().date()
        if not data_registro:
            data_registro = timezone.now().date()

        arquivo.seek(0)
        file_hash = hashlib.sha256(arquivo.read()).hexdigest()
        arquivo.seek(0)
        extensao = os.path.splitext(arquivo.name)[1].lower()
        storage_path = f"producoes-criancas/{turma_id}/{file_hash}{extensao}"

        storage_key, arquivo_url = upload_bytes_to_storage(
            storage_path,
            arquivo.read(),
            arquivo.content_type
        )

        producao = ProducaoCrianca.objects.create(
            crianca_id=crianca_id,
            turma_id=turma_id,
            professor_id=professor_id,
            instituicao_id=instituicao_id or None,
            tipo=tipo,
            titulo=titulo,
            descricao=descricao,
            arquivo_url=arquivo_url,
            projeto=projeto,
            data_registro=data_registro
        )

        logger.info(
            "Produção da criança criada.",
            extra={"crianca_id": str(crianca_id), "producao_id": str(producao.id), "storage_key": storage_key},
        )

        return Response(ProducaoCriancaSerializer(producao).data, status=status.HTTP_201_CREATED)
    except Exception as e:
        logger.exception("Erro ao fazer upload de produção da criança.")
        return Response(
            {'error': 'Erro ao fazer upload da produção', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
@csrf_exempt
@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([UploadRateThrottle])
def upload_producao_portfolio(request):
    """
    Upload de produção (foto/mídia) com vínculo N-to-N com crianças.
    Suporta upload de uma mídia vinculada a múltiplas crianças.
    Rate limit: 10 req/min.

    Espera:
    - arquivo: arquivo de imagem/vídeo
    - turma_id: ID da turma
    - professora_id: ID da professora
    - professora_nome: Nome da professora
    - criancas: JSON array com [{crianca_id, crianca_nome, legenda?}]
    - tipo_midia: 'foto' | 'video' | 'desenho' | 'escrita' (default: 'foto')
    - projeto: Nome do projeto vinculado (opcional)
    - tags: JSON array de tags (opcional)
    - data_registro: Data do registro YYYY-MM-DD (opcional, default: hoje)
    """
    try:
        # Validar arquivo enviado
        if 'arquivo' not in request.FILES:
            return Response(
                {'error': 'Nenhum arquivo foi enviado'},
                status=status.HTTP_400_BAD_REQUEST
            )

        arquivo = request.FILES['arquivo']
        turma_id = request.POST.get('turma_id', '')
        professora_id = request.POST.get('professora_id', '')
        professora_nome = request.POST.get('professora_nome', '')
        tipo_midia = request.POST.get('tipo_midia', 'foto')
        projeto = request.POST.get('projeto', '')
        tags_json = request.POST.get('tags', '[]')
        criancas_json = request.POST.get('criancas', '[]')
        data_registro_str = request.POST.get('data_registro', '')

        # Validar campos obrigatórios
        if not turma_id:
            return Response(
                {'error': 'turma_id é obrigatório'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not professora_id or not professora_nome:
            return Response(
                {'error': 'professora_id e professora_nome são obrigatórios'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Parse das crianças
        try:
            criancas = json.loads(criancas_json)
            if not isinstance(criancas, list) or len(criancas) == 0:
                return Response(
                    {'error': 'Pelo menos uma criança deve ser vinculada'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except json.JSONDecodeError:
            return Response(
                {'error': 'Formato inválido para criancas'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Parse das tags
        try:
            tags = json.loads(tags_json) if tags_json else []
        except json.JSONDecodeError:
            tags = []

        # Parse da data de registro
        if data_registro_str:
            data_registro = parse_date(data_registro_str)
            if not data_registro:
                data_registro = timezone.now().date()
        else:
            data_registro = timezone.now().date()

        # Validar tipo de arquivo
        validation_error = validate_uploaded_file(
            arquivo,
            ALLOWED_IMAGE_MIME_TYPES,
            ALLOWED_IMAGE_EXTENSIONS,
            MAX_IMAGE_SIZE_BYTES,
            "imagem"
        )
        if validation_error:
            mensagem, status_code = validation_error
            return Response({'error': mensagem}, status=status_code)

        # Gerar hash do arquivo
        arquivo.seek(0)
        file_hash = hashlib.sha256(arquivo.read()).hexdigest()
        arquivo.seek(0)

        # Verificar se já existe arquivo com mesmo hash
        if ProducaoFoto.objects.filter(arquivo_hash=file_hash).exists():
            producao_existente = ProducaoFoto.objects.get(arquivo_hash=file_hash)
            return Response({
                'error': 'Arquivo duplicado',
                'message': 'Este arquivo já foi enviado anteriormente',
                'producao_id': producao_existente.id,
                'arquivo_url': refresh_presigned_url(producao_existente.arquivo_url)
            }, status=status.HTTP_409_CONFLICT)

        # Upload para storage (S3)
        arquivo_content = arquivo.read()
        arquivo.seek(0)
        mime_type_resolvido = resolve_mime_type(arquivo, ALLOWED_IMAGE_MIME_TYPES)

        # Definir path no storage
        extensao = os.path.splitext(arquivo.name)[1].lower()
        storage_path = f"portfolio/{turma_id}/{file_hash}{extensao}"

        # Fazer upload para o storage
        try:
            storage_key, arquivo_url = upload_bytes_to_storage(
                storage_path,
                arquivo_content,
                mime_type_resolvido,
            )
        except Exception as upload_error:
            print(f"[ERRO UPLOAD S3] {str(upload_error)}")
            return Response(
                {'error': 'Falha no upload do arquivo para o storage'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # Criar registro da produção
        producao = ProducaoFoto.objects.create(
            arquivo_url=arquivo_url,
            arquivo_nome=arquivo.name,
            arquivo_hash=file_hash,
            tamanho_bytes=len(arquivo_content),
            tipo_midia=tipo_midia,
            mime_type=mime_type_resolvido,
            turma_id=turma_id,
            professora_id=professora_id,
            professora_nome=professora_nome,
            projeto=projeto,
            tags=tags,
            data_registro=data_registro
        )

        # Criar vínculos com as crianças
        vinculos_criados = []
        for crianca in criancas:
            crianca_id = crianca.get('crianca_id', '')
            crianca_nome = crianca.get('crianca_nome', '')
            legenda = crianca.get('legenda', '')

            if not crianca_id or not crianca_nome:
                continue

            vinculo = ProducaoFotoCrianca.objects.create(
                producao_foto=producao,
                crianca_id=crianca_id,
                crianca_nome=crianca_nome,
                legenda=legenda
            )
            vinculos_criados.append({
                'id': vinculo.id,
                'crianca_id': vinculo.crianca_id,
                'crianca_nome': vinculo.crianca_nome,
                'legenda': vinculo.legenda
            })

        return Response({
            'success': True,
            'producao': {
                'id': producao.id,
                'arquivo_url': producao.arquivo_url,
                'arquivo_nome': producao.arquivo_nome,
                'tipo_midia': producao.tipo_midia,
                'data_registro': str(producao.data_registro),
                'projeto': producao.projeto,
                'tags': producao.tags
            },
            'vinculos': vinculos_criados,
            'total_criancas': len(vinculos_criados)
        }, status=status.HTTP_201_CREATED)

    except Exception as e:
        print(f"[ERRO UPLOAD PORTFOLIO] {str(e)}")
        traceback.print_exc()
        return Response(
            {'error': 'Erro interno no servidor', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_producoes_portfolio(request):
    """
    Lista produções do portfólio com filtros.

    Parâmetros de query:
    - turma_id: Filtrar por turma (obrigatório)
    - crianca_id: Filtrar por criança específica
    - tipo_midia: Filtrar por tipo (foto, video, desenho, escrita)
    - projeto: Filtrar por projeto
    - data_inicio: Data inicial (YYYY-MM-DD)
    - data_fim: Data final (YYYY-MM-DD)
    - destaque: Filtrar apenas destaques (true/false)
    - incluir_relatorio: Filtrar marcados para relatório (true/false)
    """
    try:
        turma_id = request.GET.get('turma_id', '')
        crianca_id = request.GET.get('crianca_id', '')
        tipo_midia = request.GET.get('tipo_midia', '')
        projeto = request.GET.get('projeto', '')
        data_inicio = request.GET.get('data_inicio', '')
        data_fim = request.GET.get('data_fim', '')
        destaque = request.GET.get('destaque', '')
        incluir_relatorio = request.GET.get('incluir_relatorio', '')

        if not turma_id:
            return Response(
                {'error': 'turma_id é obrigatório'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Query base
        queryset = ProducaoFoto.objects.filter(turma_id=turma_id)

        # Aplicar filtros
        if tipo_midia:
            queryset = queryset.filter(tipo_midia=tipo_midia)

        if projeto:
            queryset = queryset.filter(projeto__icontains=projeto)

        if data_inicio:
            data_inicio_parsed = parse_date(data_inicio)
            if data_inicio_parsed:
                queryset = queryset.filter(data_registro__gte=data_inicio_parsed)

        if data_fim:
            data_fim_parsed = parse_date(data_fim)
            if data_fim_parsed:
                queryset = queryset.filter(data_registro__lte=data_fim_parsed)

        # Se filtrar por criança, buscar produções vinculadas
        if crianca_id:
            producoes_ids = ProducaoFotoCrianca.objects.filter(
                crianca_id=crianca_id
            ).values_list('producao_foto_id', flat=True)
            queryset = queryset.filter(id__in=producoes_ids)

            # Filtros adicionais no vínculo
            if destaque.lower() == 'true':
                producoes_ids_destaque = ProducaoFotoCrianca.objects.filter(
                    crianca_id=crianca_id,
                    destaque=True
                ).values_list('producao_foto_id', flat=True)
                queryset = queryset.filter(id__in=producoes_ids_destaque)

            if incluir_relatorio.lower() == 'true':
                producoes_ids_relatorio = ProducaoFotoCrianca.objects.filter(
                    crianca_id=crianca_id,
                    incluir_relatorio=True
                ).values_list('producao_foto_id', flat=True)
                queryset = queryset.filter(id__in=producoes_ids_relatorio)

        # Ordenar por data mais recente
        queryset = queryset.order_by('-data_registro', '-data_upload')

        # Montar resposta com vínculos
        producoes = []
        for producao in queryset[:100]:  # Limitar a 100 resultados
            vinculos = ProducaoFotoCrianca.objects.filter(producao_foto=producao)

            # Regenerar URL presigned se necessário (URLs expiram após 1h)
            arquivo_url = refresh_presigned_url(producao.arquivo_url)

            producoes.append({
                'id': producao.id,
                'arquivo_url': arquivo_url,
                'arquivo_nome': producao.arquivo_nome,
                'tipo_midia': producao.tipo_midia,
                'mime_type': producao.mime_type,
                'data_registro': str(producao.data_registro),
                'projeto': producao.projeto,
                'tags': producao.tags,
                'professora_nome': producao.professora_nome,
                'criancas': [{
                    'id': v.id,
                    'crianca_id': v.crianca_id,
                    'crianca_nome': v.crianca_nome,
                    'legenda': v.legenda,
                    'legenda_ia': v.legenda_ia,
                    'destaque': v.destaque,
                    'incluir_relatorio': v.incluir_relatorio
                } for v in vinculos]
            })

        return Response({
            'success': True,
            'total': len(producoes),
            'producoes': producoes
        }, status=status.HTTP_200_OK)

    except Exception as e:
        print(f"[ERRO LISTAR PORTFOLIO] {str(e)}")
        return Response(
            {'error': 'Erro interno no servidor', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def atualizar_vinculo_producao(request, vinculo_id):
    """
    Atualiza um vínculo foto-criança (legenda, destaque, incluir_relatorio).

    Espera no body:
    - legenda: Nova legenda (opcional)
    - destaque: boolean (opcional)
    - incluir_relatorio: boolean (opcional)
    """
    try:
        try:
            vinculo = ProducaoFotoCrianca.objects.get(id=vinculo_id)
        except ProducaoFotoCrianca.DoesNotExist:
            return Response(
                {'error': 'Vínculo não encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )

        data = request.data

        if 'legenda' in data:
            vinculo.legenda = data['legenda']

        if 'destaque' in data:
            vinculo.destaque = bool(data['destaque'])

        if 'incluir_relatorio' in data:
            vinculo.incluir_relatorio = bool(data['incluir_relatorio'])

        if 'legenda_ia' in data:
            vinculo.legenda_ia = data['legenda_ia']

        vinculo.save()

        return Response({
            'success': True,
            'vinculo': {
                'id': vinculo.id,
                'crianca_id': vinculo.crianca_id,
                'crianca_nome': vinculo.crianca_nome,
                'legenda': vinculo.legenda,
                'legenda_ia': vinculo.legenda_ia,
                'destaque': vinculo.destaque,
                'incluir_relatorio': vinculo.incluir_relatorio
            }
        }, status=status.HTTP_200_OK)

    except Exception as e:
        print(f"[ERRO ATUALIZAR VINCULO] {str(e)}")
        return Response(
            {'error': 'Erro interno no servidor', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def atualizar_vinculos_portfolio_lote(request):
    """
    Atualiza vínculos de portfólio em lote.

    Espera no body:
    - vinculo_ids: lista de IDs dos vínculos
    - incluir_relatorio: boolean (opcional)
    - destaque: boolean (opcional)
    """
    try:
        data = request.data or {}
        vinculo_ids = data.get('vinculo_ids') or []
        incluir_relatorio = data.get('incluir_relatorio', None)
        destaque = data.get('destaque', None)

        if not isinstance(vinculo_ids, list) or not vinculo_ids:
            return Response(
                {'error': 'Lista de vínculos é obrigatória.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if incluir_relatorio is None and destaque is None:
            return Response(
                {'error': 'Informe ao menos um campo para atualização.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        def parse_boolean(value):
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                return value.strip().lower() in {'true', '1', 'yes', 'sim'}
            return bool(value)

        campos_atualizacao = {}
        if incluir_relatorio is not None:
            campos_atualizacao['incluir_relatorio'] = parse_boolean(incluir_relatorio)
        if destaque is not None:
            campos_atualizacao['destaque'] = parse_boolean(destaque)

        queryset = ProducaoFotoCrianca.objects.filter(id__in=vinculo_ids)
        total_encontrados = queryset.count()
        if total_encontrados == 0:
            return Response(
                {'error': 'Nenhum vínculo encontrado para atualização.'},
                status=status.HTTP_404_NOT_FOUND
            )

        queryset.update(**campos_atualizacao)

        return Response(
            {
                'success': True,
                'total_encontrados': total_encontrados,
                'total_atualizados': total_encontrados,
            },
            status=status.HTTP_200_OK
        )

    except Exception as e:
        print(f"[ERRO ATUALIZAR VINCULOS LOTE] {str(e)}")
        return Response(
            {'error': 'Erro interno no servidor', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def excluir_producao_portfolio(request, producao_id):
    """
    Exclui uma produção do portfólio e todos os seus vínculos.
    """
    try:
        try:
            producao = ProducaoFoto.objects.get(id=producao_id)
        except ProducaoFoto.DoesNotExist:
            return Response(
                {'error': 'Produção não encontrada'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Guardar informações para resposta
        arquivo_url = producao.arquivo_url
        arquivo_nome = producao.arquivo_nome

        # Excluir (cascade vai remover vínculos automaticamente)
        producao.delete()

        return Response({
            'success': True,
            'message': 'Produção excluída com sucesso',
            'arquivo_excluido': arquivo_nome
        }, status=status.HTTP_200_OK)

    except Exception as e:
        print(f"[ERRO EXCLUIR PORTFOLIO] {str(e)}")
        return Response(
            {'error': 'Erro interno no servidor', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# =============================================================================
# ENDPOINT DE MELHORIA DE TEXTO (IA)
# =============================================================================

@api_view(['POST'])
@permission_classes([AllowAny])  # Permitir acesso sem auth para facilitar uso
def melhorar_texto(request):
    """
    Melhora um texto pedagógico usando IA.
    Mantém o tom profissional e adequado para educação infantil.

    Espera no body:
    - texto: Texto original a ser melhorado
    - contexto: Contexto adicional (opcional) - 'observacao', 'relatorio', 'legenda'
    - faixa_etaria: Faixa etária das crianças (opcional)
    """
    try:
        data = request.data
        texto_original = data.get('texto', '').strip()
        contexto = data.get('contexto', 'observacao')
        faixa_etaria = data.get('faixa_etaria', 'Educação Infantil')

        if not texto_original:
            return Response(
                {'error': 'Texto é obrigatório'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if len(texto_original) > 5000:
            return Response(
                {'error': 'Texto muito longo (máximo 5000 caracteres)'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Configuração de timeout
        timeout_seconds = _get_int_env('IA_REQUEST_TIMEOUT_SECONDS', 30)

        # Prompt pedagógico baseado no contexto
        prompts_por_contexto = {
            'observacao': f"""Você é um especialista em educação infantil. Melhore o texto abaixo mantendo:
- Tom profissional e técnico adequado para relatórios pedagógicos
- Referências implícitas aos campos de experiência da BNCC
- Linguagem positiva e construtiva
- Foco no desenvolvimento da criança

Faixa etária: {faixa_etaria}

Texto original:
{texto_original}

Retorne APENAS o texto melhorado, sem explicações.""",

            'relatorio': f"""Você é um especialista em educação infantil. Reescreva o texto abaixo para um relatório pedagógico formal:
- Use linguagem técnica adequada
- Mantenha objetividade
- Destaque aspectos do desenvolvimento
- Inclua sugestões pedagógicas quando apropriado

Faixa etária: {faixa_etaria}

Texto original:
{texto_original}

Retorne APENAS o texto melhorado, sem explicações.""",

            'legenda': f"""Você é um especialista em educação infantil. Melhore esta legenda de foto/vídeo:
- Seja conciso mas descritivo
- Destaque o momento pedagógico capturado
- Use linguagem adequada para portfólio escolar

Texto original:
{texto_original}

Retorne APENAS a legenda melhorada, sem explicações."""
        }

        prompt = prompts_por_contexto.get(contexto, prompts_por_contexto['observacao'])

        # Chamar OpenAI com timeout
        def call_openai():
            openai_client = get_openai_client()
            response = openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Você é um assistente pedagógico especializado em educação infantil brasileira."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1000,
                temperature=0.7
            )
            return response.choices[0].message.content.strip()

        # Executar com timeout
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(call_openai)
            try:
                texto_melhorado = future.result(timeout=timeout_seconds)
            except FuturesTimeoutError:
                return Response(
                    {'error': 'Tempo limite excedido. Tente novamente com um texto menor.'},
                    status=status.HTTP_504_GATEWAY_TIMEOUT
                )

        return Response({
            'success': True,
            'texto_original': texto_original,
            'texto_melhorado': texto_melhorado,
            'contexto': contexto,
            'caracteres_original': len(texto_original),
            'caracteres_melhorado': len(texto_melhorado)
        }, status=status.HTTP_200_OK)

    except Exception as e:
        print(f"[ERRO MELHORAR TEXTO] {str(e)}")
        traceback.print_exc()
        return Response(
            {'error': 'Erro ao processar texto com IA', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
