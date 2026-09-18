import os
from typing import Optional, Tuple

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from PIL import Image
import io
import pillow_heif
pillow_heif.register_heif_opener()

def is_s3_configured() -> bool:
    """
    Verifica se as variáveis necessárias para uso do S3 estão presentes.
    """
    return all(
        [
            os.getenv("AWS_ACCESS_KEY_ID"),
            os.getenv("AWS_SECRET_ACCESS_KEY"),
            os.getenv("AWS_S3_BUCKET_NAME"),
        ]
    )


def _get_s3_client():
    """
    Retorna cliente S3 configurado com a região indicada.
    Usa assinatura V4 para compatibilidade com todas as regiões.
    """
    from botocore.config import Config

    region = os.getenv("AWS_REGION", "us-east-1")
    config = Config(
        signature_version='s3v4',
        region_name=region
    )
    return boto3.client("s3", config=config, region_name=region)


def generate_presigned_url(key: str, expires_in_seconds: int = 3600) -> Optional[str]:
    """
    Gera URL pré-assinada para acesso ao objeto armazenado.
    """
    if not is_s3_configured():
        return None

    bucket = os.getenv("AWS_S3_BUCKET_NAME")
    try:
        client = _get_s3_client()
        return client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=expires_in_seconds,
        )
    except (BotoCoreError, ClientError) as error:
        print(f"[S3] Falha ao gerar URL pré-assinada: {error}")
        return None


def extract_storage_key_from_url(url: str) -> Optional[str]:
    """
    Extrai o storage_key (caminho do arquivo) de uma URL S3.

    Exemplo:
    Input: https://bucket.s3.amazonaws.com/portfolio/id/file.jpg?X-Amz-...
    Output: portfolio/id/file.jpg
    """
    if not url:
        return None

    try:
        from urllib.parse import urlparse, unquote
        parsed = urlparse(url)
        # Remove a barra inicial do path
        path = parsed.path.lstrip('/')
        # Decodifica caracteres URL-encoded
        return unquote(path)
    except Exception:
        return None


def refresh_presigned_url(url: str, expires_in_seconds: int = 3600) -> Optional[str]:
    """
    Regenera a URL presigned a partir de uma URL S3 existente.
    Se a URL não for do S3 ou ocorrer erro, retorna a URL original.
    """
    if not url or not is_s3_configured():
        return url

    bucket = os.getenv("AWS_S3_BUCKET_NAME", "")

    # Verifica se é uma URL do nosso bucket S3
    if bucket not in url:
        return url

    storage_key = extract_storage_key_from_url(url)
    if not storage_key:
        return url

    new_url = generate_presigned_url(storage_key, expires_in_seconds)
    return new_url if new_url else url


def upload_bytes_to_storage(
    key: str, content: bytes, content_type: Optional[str] = None
) -> Tuple[str, Optional[str]]:
    """
    Envia conteúdo binário para S3.

    Retorna uma tupla (path/key armazenado, url).
    Levanta exceção se o upload falhar.
    """
     # ── ajuste pra testar geração de pdf localmente sem s3 (quando S3 não está configurado ou credenciais inválidas) ──
    if not is_s3_configured():
        local_base = os.getenv("LOCAL_STORAGE_PATH", "/tmp/nara_storage")
        normalized_key = key.lstrip("/")
        local_path = os.path.join(local_base, normalized_key)
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        with open(local_path, "wb") as f:
            f.write(content)
        # Retorna o path local como "url" para dev
        return normalized_key, f"file://{local_path}"

    normalized_key = key.lstrip("/")
    presign_ttl = int(os.getenv("AWS_PRESIGNED_TTL_SECONDS", "3600"))

    bucket = os.getenv("AWS_S3_BUCKET_NAME")
    extra_args = {"ContentType": content_type} if content_type else {}

    try:
        client = _get_s3_client()
        client.put_object(
            Bucket=bucket,
            Key=normalized_key,
            Body=content,
            **extra_args,
        )
        url = generate_presigned_url(normalized_key, presign_ttl)
        if not url:
            raise RuntimeError("Falha ao gerar URL pré-assinada após upload.")
        return normalized_key, url
    except (BotoCoreError, ClientError) as error:
        print(f"[S3] Falha ao fazer upload para S3: {error}")
        raise RuntimeError(f"Erro ao enviar arquivo para o servidor: {error}") from error

def get_logo_url(instituicao) -> Optional[str]:
    """
    Devolve uma URL válida para o logo da instituição, regenerando a
    presigned URL a partir da storage_key quando necessário.

    Isso evita o problema de logo_url expirar (presigned URLs do S3 têm
    TTL de AWS_PRESIGNED_TTL_SECONDS, default 3600s) e nunca serem
    renovadas — o mesmo padrão usado em ensure_pdf() para relatórios.
    """
    if not instituicao.logo_url and not instituicao.logo_storage_key:
        return None

    if not is_s3_configured():
        # Ambiente local/dev sem S3: logo_url é um path "file://" fixo,
        # não expira, então não há nada a regenerar.
        return instituicao.logo_url or None

    storage_key = instituicao.logo_storage_key

    # Backfill: registros antigos podem só ter logo_url (já expirada)
    # sem logo_storage_key preenchido. Tenta recuperar a key a partir
    # da URL salva.
    if not storage_key and instituicao.logo_url:
        storage_key = extract_storage_key_from_url(instituicao.logo_url)

    if not storage_key:
        # Não há como recuperar — precisa de novo upload.
        return None

    presign_ttl = int(os.getenv("AWS_PRESIGNED_TTL_SECONDS", "3600"))
    presigned = generate_presigned_url(storage_key, presign_ttl)

    if not presigned:
        return None

    # Persiste a key recuperada e/ou a URL renovada, evitando repetir
    # esse trabalho a cada request.
    update_fields = []
    if instituicao.logo_storage_key != storage_key:
        instituicao.logo_storage_key = storage_key
        update_fields.append('logo_storage_key')
    if instituicao.logo_url != presigned:
        instituicao.logo_url = presigned
        update_fields.append('logo_url')

    if update_fields:
        instituicao.save(update_fields=update_fields)

    return presigned


def copy_within_storage(
    src_key: str, dst_key: str, content_type: Optional[str] = None
) -> str:
    """
    Copia um objeto dentro do storage (server-side copy no S3; cópia de
    arquivo no fallback local de dev).

    Retorna a key de destino normalizada.
    Levanta ``FileNotFoundError`` se a origem não existe (ex.: objeto
    temporário expirado por lifecycle rule) e ``RuntimeError`` para os
    demais erros.
    """
    src_key = (src_key or "").lstrip("/")
    dst_key = (dst_key or "").lstrip("/")
    if not src_key or not dst_key:
        raise FileNotFoundError("Chave de origem/destino vazia.")

    if not is_s3_configured():
        import shutil

        local_base = os.getenv("LOCAL_STORAGE_PATH", "/tmp/nara_storage")
        src_path = os.path.join(local_base, src_key)
        dst_path = os.path.join(local_base, dst_key)
        if not os.path.exists(src_path):
            raise FileNotFoundError(src_path)
        os.makedirs(os.path.dirname(dst_path), exist_ok=True)
        shutil.copyfile(src_path, dst_path)
        return dst_key

    bucket = os.getenv("AWS_S3_BUCKET_NAME")
    extra_args = {"ContentType": content_type, "MetadataDirective": "REPLACE"} if content_type else {}
    try:
        client = _get_s3_client()
        client.copy_object(
            Bucket=bucket,
            Key=dst_key,
            CopySource={"Bucket": bucket, "Key": src_key},
            **extra_args,
        )
        return dst_key
    except ClientError as error:
        code = (error.response.get("Error") or {}).get("Code", "")
        if code in ("NoSuchKey", "404"):
            raise FileNotFoundError(src_key) from error
        print(f"[S3] Falha ao copiar {src_key} -> {dst_key}: {error}")
        raise RuntimeError(f"Erro ao copiar arquivo no servidor: {error}") from error
    except BotoCoreError as error:
        print(f"[S3] Falha ao copiar {src_key} -> {dst_key}: {error}")
        raise RuntimeError(f"Erro ao copiar arquivo no servidor: {error}") from error


def download_bytes_from_storage(key: str) -> bytes:
    """
    Lê um objeto do storage e devolve o conteúdo em memória (S3 ou fallback
    local de dev).

    Levanta ``FileNotFoundError`` quando o objeto não existe (expirado por
    lifecycle rule, key errada) e ``RuntimeError`` para os demais erros — o
    chamador decide se marca o registro como falho ou tenta de novo depois.
    """
    key = (key or "").lstrip("/")
    if not key:
        raise FileNotFoundError("Chave vazia.")

    if not is_s3_configured():
        local_base = os.getenv("LOCAL_STORAGE_PATH", "/tmp/nara_storage")
        local_path = os.path.join(local_base, key)
        if not os.path.exists(local_path):
            raise FileNotFoundError(local_path)
        with open(local_path, "rb") as f:
            return f.read()

    bucket = os.getenv("AWS_S3_BUCKET_NAME")
    try:
        client = _get_s3_client()
        resposta = client.get_object(Bucket=bucket, Key=key)
        return resposta["Body"].read()
    except ClientError as error:
        code = (error.response.get("Error") or {}).get("Code", "")
        if code in ("NoSuchKey", "404"):
            raise FileNotFoundError(key) from error
        raise RuntimeError(f"Erro ao baixar arquivo do servidor: {error}") from error
    except BotoCoreError as error:
        raise RuntimeError(f"Erro ao baixar arquivo do servidor: {error}") from error


def delete_from_storage(key: str) -> bool:
    """
    Remove um objeto do storage (S3 ou fallback local de dev).
    Best-effort: retorna False em erro, nunca levanta.
    """
    if not key:
        return False
    if is_s3_configured():
        return delete_from_s3(key)

    local_base = os.getenv("LOCAL_STORAGE_PATH", "/tmp/nara_storage")
    local_path = os.path.join(local_base, key.lstrip("/"))
    try:
        os.remove(local_path)
        return True
    except OSError:
        return False


def delete_from_s3(key: str) -> bool:
    """Remove um objeto do S3. Retorna True se deletado com sucesso."""
    if not is_s3_configured() or not key:
        return False

    bucket = os.getenv("AWS_S3_BUCKET_NAME")
    try:
        client = _get_s3_client()
        client.delete_object(Bucket=bucket, Key=key.lstrip("/"))
        print(f"[S3] Objeto deletado: {key}")
        return True
    except (BotoCoreError, ClientError) as error:
        print(f"[S3] Falha ao deletar do S3: {error}")
        return False
    
def compress_image(content: bytes, max_dimension: int = 800, quality: int = 80) -> Tuple[bytes, str]:
    """
    Redimensiona e comprime uma imagem antes do upload.

    Retorna (bytes_comprimidos, content_type). Sempre converte para JPEG
    (menor tamanho que PNG para fotos), removendo transparência se houver.
    """
    image = Image.open(io.BytesIO(content))

    # Remove transparência (RGBA/P) convertendo para RGB com fundo branco,
    # já que JPEG não suporta canal alpha.
    if image.mode in ('RGBA', 'P', 'LA'):
        background = Image.new('RGB', image.size, (255, 255, 255))
        image = image.convert('RGBA')
        background.paste(image, mask=image.split()[-1])
        image = background
    elif image.mode != 'RGB':
        image = image.convert('RGB')

    # Redimensiona mantendo proporção, só se for maior que o limite.
    image.thumbnail((max_dimension, max_dimension), Image.LANCZOS)

    buffer = io.BytesIO()
    image.save(buffer, format='JPEG', quality=quality, optimize=True)
    return buffer.getvalue(), 'image/jpeg'

def get_foto_url(aluno) -> Optional[str]:
    """
    Devolve uma URL válida para a foto da criança, regenerando a presigned
    URL a partir da storage_key quando necessário. Mesmo padrão de
    get_logo_url / ensure_pdf.
    """
    if not aluno.foto_url and not aluno.foto_storage_key:
        return None

    if not is_s3_configured():
        return aluno.foto_url or None

    storage_key = aluno.foto_storage_key

    if not storage_key and aluno.foto_url:
        storage_key = extract_storage_key_from_url(aluno.foto_url)

    if not storage_key:
        return None

    presign_ttl = int(os.getenv("AWS_PRESIGNED_TTL_SECONDS", "3600"))
    presigned = generate_presigned_url(storage_key, presign_ttl)

    if not presigned:
        return None

    update_fields = []
    if aluno.foto_storage_key != storage_key:
        aluno.foto_storage_key = storage_key
        update_fields.append('foto_storage_key')
    if aluno.foto_url != presigned:
        aluno.foto_url = presigned
        update_fields.append('foto_url')

    if update_fields:
        aluno.save(update_fields=update_fields)

    return presigned