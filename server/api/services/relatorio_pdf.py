"""Orquestração da geração de PDF dos relatórios.

Monta o HTML final (shell + CSS + conteúdo + imagens inline), aciona o serviço
`report_generator` e cacheia o PDF no S3 via `pdf_storage_key`.
"""

import base64
import html as _html
import io
import logging
import mimetypes
import os
import re
import secrets
import time
import unicodedata
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import parse_qs, urlparse

import httpx
from PIL import Image, ImageOps
from django.utils import timezone

from api.models import Crianca, Relatorio, RegistroDesenho, RegistroEscrita
from api.services.pdf_renderer import render_html_to_pdf
from api.storage import (
    delete_from_s3,
    extract_storage_key_from_url,
    generate_presigned_url,
    is_s3_configured,
    refresh_presigned_url,
    upload_bytes_to_storage,
)

logger = logging.getLogger(__name__)

_CSS_PATH = Path(__file__).resolve().parent.parent / "static" / "pdf" / "relatorio.css"

# Cap por imagem ao embutir como data: URI (evita explodir memória do Chromium).
_MAX_IMAGE_BYTES = 10 * 1024 * 1024
_IMAGE_FETCH_TIMEOUT = 15.0

# Alvo para recompressão: A4 tem ~210mm ≈ 794px @96dpi. 1400px cobre retina
# sem estourar o PDF. JPEG 80 é indistinguível a olho nu para fotos.
_MAX_IMAGE_DIMENSION = 500
_JPEG_QUALITY = 60

# Fallback para outras URLs relativas que não sejam /api/arquivo/<hash>/
# (essas passam a ser resolvidas direto do banco/storage, sem round-trip HTTP
# — ver `_ARQUIVO_URL_RE` e `_inline_registro_por_hash` abaixo). Mantido só
# por segurança para casos residuais; hoje não deveria ser mais exercitado
# pela galeria de produções do relatório.
_INTERNAL_API_BASE = os.getenv("INTERNAL_API_BASE", "http://localhost:8001").rstrip("/")

# Casa com a URL gerada por `_quadro_producao` em services/relatorio.py:
# "/api/arquivo/<hash>/" (opcionalmente com querystring, ex.: "?rot=90").
_ARQUIVO_URL_RE = re.compile(r'^/api/arquivo/(?P<hash>[^/?]+)/?(?:\?(?P<qs>.*))?$')


def _load_css() -> str:
    """CSS padrão do sistema (tema global), usado como base para todo
    relatório — com ou sem template, e é sobre ele que as variáveis de
    paleta do template (quando houver) são aplicadas por cima."""
    try:
        css = _CSS_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        logger.warning(
            "CSS do PDF NÃO encontrado em %s. Rode `npm run copy:pdf-css` no client.",
            _CSS_PATH,
        )
        return ""
    logger.debug("CSS do PDF carregado de %s (%s bytes)", _CSS_PATH, len(css))
    return css


# Tons válidos por matiz — precisa bater com as variáveis declaradas em
# client/src/styles/relatorio-editor.css (bloco .ProseMirror { ... }).
# 'roxo'/'verde' têm 4 tons; 'amarelo'/'coral'/'azul' têm 3 (sem ultraClaro,
# porque o CSS não referencia --amarelo-ultra-claro/--coral-ultra-claro/
# --azul-ultra-claro em lugar nenhum hoje).
_VARS_POR_MATIZ = {
    'roxo': ['base', 'escuro', 'claro', 'ultraClaro'],
    'verde': ['base', 'escuro', 'claro', 'ultraClaro'],
    'amarelo': ['base', 'escuro', 'claro'],
    'coral': ['base', 'escuro', 'claro'],
    'azul': ['base', 'escuro', 'claro'],
}
_SUFIXO_CSS = {'base': '', 'escuro': '-escuro', 'claro': '-claro', 'ultraClaro': '-ultra-claro'}
_HEX_RE = re.compile(r'#[0-9a-fA-F]{6}')

_FONTES = {
    'a': {'titulo': "'Nunito', 'Trebuchet MS', 'Segoe UI', sans-serif", 'corpo': "'Lora', Georgia, 'Times New Roman', serif"},
    'b': {'titulo': "'Playfair Display', Georgia, 'Times New Roman', serif", 'corpo': "'PT Serif', Georgia, serif"},
    'c': {'titulo': "'Merriweather', Georgia, serif", 'corpo': "'Nunito', 'Trebuchet MS', 'Segoe UI', sans-serif"},
}

_CORES_TEXTO = {
    'grafite': '#332F42',
    'ameixa': '#4A3A6B',
    'verde': '#31513A',
    'terracota': '#8A4A34',
}


def _montar_css_vars_tipografia(template) -> str:
    """Gera --fonte-titulo/--fonte-corpo/--escala-nome/--escala-titulo/
    --cor-texto-capa a partir de template.config — mesma lógica de
    cssVarsTipografia() em templateRelatorioShared.js."""
    config = template.config if isinstance(template.config, dict) else {}
    fonte = _FONTES.get(config.get('fonteCombo'), _FONTES['a'])

    def _escala(valor):
        try:
            n = float(valor)
        except (TypeError, ValueError):
            n = 100
        return max(80, min(120, n)) / 100

    declaracoes = [
        f"--fonte-titulo: {fonte['titulo']};",
        f"--fonte-corpo: {fonte['corpo']};",
        f"--escala-nome: {_escala(config.get('nomeTamanho', 100))};",
        f"--escala-titulo: {_escala(config.get('tituloTamanho', 100))};",
    ]

    cor_hex = _CORES_TEXTO.get(config.get('corTexto'))
    if cor_hex:
        declaracoes.append(f"--cor-texto-capa: {cor_hex};")

    return ".ProseMirror {\n  " + "\n  ".join(declaracoes) + "\n}"

def _montar_css_vars_do_template(template) -> str:
    """Gera um bloco `.ProseMirror { --roxo: ...; }` a partir de
    template.config['paleta'], sobrescrevendo só os matizes que o
    coordenador de fato customizou.

    Concatenado DEPOIS de `_load_css()` no <style> final: a cascata CSS
    resolve sozinha — matizes ausentes/malformados mantêm o valor padrão
    do CSS base, sem precisar de lógica extra aqui.

    `config` é JSON vindo de um formulário do coordenador (nunca confiável
    por padrão), então cada valor é validado como hex de 6 dígitos antes de
    entrar no CSS — nunca injeta string arbitrária num <style>.
    """
    paleta = (template.config or {}).get('paleta') if template.config else None
    if not isinstance(paleta, dict) or not paleta:
        return ""

    declaracoes = []
    for matiz, tons in _VARS_POR_MATIZ.items():
        cores_matiz = paleta.get(matiz)
        if not isinstance(cores_matiz, dict):
            continue
        for tom in tons:
            valor = cores_matiz.get(tom)
            if not isinstance(valor, str) or not _HEX_RE.fullmatch(valor):
                continue
            declaracoes.append(f'--{matiz}{_SUFIXO_CSS[tom]}: {valor};')

    if not declaracoes:
        return ""

    return ".ProseMirror {\n  " + "\n  ".join(declaracoes) + "\n}"


def _resolve_css(relatorio: Relatorio) -> str:
    base_css = _load_css()

    template_id = getattr(relatorio, "template_id", None)
    if not template_id:
        return base_css

    template = getattr(relatorio, "template", None)
    if template is None:
        # Evita side-effect de import circular no topo do módulo.
        from api.models import RelatorioTemplate
        template = RelatorioTemplate.objects.filter(id=template_id).first()

    if template is None:
        logger.warning(
            "relatorio=%s referencia template=%s que não existe mais; usando tema padrão.",
            relatorio.id, template_id,
        )
        return base_css

    if not template.ativo:
        logger.info(
            "relatorio=%s usa template=%s que está inativo; renderizando com ele mesmo assim "
            "(inativo só bloqueia NOVAS escolhas, não afeta relatórios já vinculados).",
            relatorio.id, template_id,
        )

    vars_css = _montar_css_vars_do_template(template)
    if vars_css:
        logger.debug(
            "Paleta do template=%s aplicada ao relatorio=%s.",
            template_id, relatorio.id,
        )
    else:
        logger.debug(
            "template=%s (relatorio=%s) sem paleta customizada (config vazio/sem 'paleta'); "
            "usando cores padrão do sistema.",
            template_id, relatorio.id,
        )

    vars_tipografia = _montar_css_vars_tipografia(template)
    if vars_tipografia:
        logger.debug(
            "Tipografia do template=%s aplicada ao relatorio=%s.",
            template_id, relatorio.id,
        )

    return base_css + "\n" + vars_css + "\n" + vars_tipografia

def _recompress_image(content: bytes, content_type: str) -> Tuple[bytes, str]:
    """Redimensiona e recomprime a imagem para reduzir o tamanho do PDF final.

    O Chromium embute imagens no PDF na resolução original — uma foto de 4000px
    vira 4000px no PDF mesmo renderizada a 600px. Downscale + JPEG 80 derruba
    PDFs de ~40MB para ~3MB sem perda perceptível. PNG com alpha permanece PNG.
    Em caso de erro, devolve os bytes originais sem propagar a exceção.
    """
    try:
        with Image.open(io.BytesIO(content)) as img:
            # EXIF orientation: câmeras costumam gravar rotacionado.
            img = ImageOps.exif_transpose(img)
            original_size = img.size
            has_alpha = img.mode in ("RGBA", "LA") or (
                img.mode == "P" and "transparency" in img.info
            )

            if max(img.size) > _MAX_IMAGE_DIMENSION:
                img.thumbnail((_MAX_IMAGE_DIMENSION, _MAX_IMAGE_DIMENSION), Image.LANCZOS)

            buf = io.BytesIO()
            if has_alpha:
                # Logos/ícones com transparência: mantém PNG.
                if img.mode == "P":
                    img = img.convert("RGBA")
                img.save(buf, format="PNG", optimize=True)
                new_type = "image/png"
            else:
                if img.mode != "RGB":
                    img = img.convert("RGB")
                img.save(buf, format="JPEG", quality=_JPEG_QUALITY, optimize=True, progressive=True)
                new_type = "image/jpeg"

            new_bytes = buf.getvalue()

        if len(new_bytes) >= len(content):
            # Recompressão não ajudou (ex.: já era pequeno/otimizado).
            return content, content_type

        logger.debug(
            "Imagem recomprimida: %s %s bytes -> %s %s bytes (%s -> %s)",
            content_type,
            len(content),
            new_type,
            len(new_bytes),
            original_size,
            img.size,
        )
        return new_bytes, new_type
    except Exception:
        logger.exception("Falha ao recomprimir imagem (type=%s, %s bytes)", content_type, len(content))
        return content, content_type


def _svg_erro_data_uri(mensagem: str) -> str:
    """Gera um quadro vermelho com o motivo da falha, para servir de placeholder
    visível no PDF quando uma imagem de /api/arquivo/<hash>/ não pôde ser
    inlined. Uso temporário de diagnóstico — remover depois de confirmar a
    causa em produção (sem acesso a logs do servidor)."""
    texto = _html.escape(mensagem)[:160]
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="420" height="110">'
        '<rect width="100%" height="100%" fill="#fee2e2" stroke="#dc2626" stroke-width="2"/>'
        '<text x="10" y="18" font-family="monospace" font-size="12" '
        'font-weight="bold" fill="#991b1b">[DEBUG] imagem não carregada:</text>'
        '<foreignObject x="10" y="24" width="400" height="80">'
        '<div xmlns="http://www.w3.org/1999/xhtml" '
        'style="font-family:monospace;font-size:10px;color:#991b1b;'
        'word-wrap:break-word;line-height:1.3;">' + texto + '</div>'
        '</foreignObject>'
        '</svg>'
    )
    encoded = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"


def _registro_por_hash(arquivo_hash: str):
    """Localiza o RegistroEscrita/RegistroDesenho pelo arquivo_hash.

    Retorna (registro, tipo) ou (None, None) se não encontrado — espelha a
    lógica de lookup de `views.servir_arquivo`.
    """
    try:
        return RegistroEscrita.objects.get(arquivo_hash=arquivo_hash), "escrita"
    except RegistroEscrita.DoesNotExist:
        pass
    try:
        return RegistroDesenho.objects.get(arquivo_hash=arquivo_hash), "desenho"
    except RegistroDesenho.DoesNotExist:
        return None, None


def _ler_bytes_do_registro(registro, tipo: str) -> Tuple[Optional[bytes], Optional[str], Optional[str]]:
    """Lê os bytes do arquivo de um registro direto do storage (S3 ou disco
    local), sem passar por HTTP. Espelha a resolução de path/key feita em
    `views.servir_arquivo`, mas devolve bytes em vez de redirect/FileResponse.

    Retorna (bytes, content_type, motivo_erro). `motivo_erro` só é preenchido
    quando `bytes` é None.
    """
    arquivo_path = registro.arquivo_path or ""
    content_type = registro.tipo_arquivo or "application/octet-stream"

    if not os.path.isabs(arquivo_path) and not os.path.exists(arquivo_path):
        if not is_s3_configured():
            motivo = f"S3 não configurado neste ambiente (arquivo_path='{arquivo_path}')"
            logger.warning(
                "S3 não configurado; não foi possível ler '%s' (hash=%s) para inline no PDF.",
                arquivo_path, registro.arquivo_hash,
            )
            return None, None, motivo

        s3_key = arquivo_path
        if arquivo_path.startswith("uploads/"):
            s3_key = f"{tipo}/{registro.arquivo_nome}"

        try:
            import boto3
            from botocore.config import Config
            from botocore.exceptions import BotoCoreError, ClientError

            region = os.getenv("AWS_REGION", "us-east-1")
            bucket = os.getenv("AWS_S3_BUCKET_NAME")
            client = boto3.client(
                "s3", config=Config(signature_version="s3v4", region_name=region), region_name=region,
            )
            obj = client.get_object(Bucket=bucket, Key=s3_key.lstrip("/"))
            return obj["Body"].read(), obj.get("ContentType") or content_type, None
        except (BotoCoreError, ClientError) as exc:
            motivo = f"S3 get_object falhou: bucket={os.getenv('AWS_S3_BUCKET_NAME')} key={s3_key} erro={exc}"
            logger.exception(
                "Falha ao ler '%s' do S3 para inline no PDF (hash=%s).", s3_key, registro.arquivo_hash,
            )
            return None, None, motivo

    # Path absoluto, ou relativo que já existe no disco local (ex.: fallback
    # local de `upload_para_s3` quando o S3 falhou no momento do upload) —
    # mesma condição de `views.servir_arquivo` para o branch "serve local".
    try:
        with open(arquivo_path, "rb") as f:
            return f.read(), content_type, None
    except OSError as exc:
        motivo = f"Falha ao abrir arquivo local '{arquivo_path}': {exc}"
        logger.exception("Falha ao ler arquivo local para inline: %s", arquivo_path)
        return None, None, motivo


def _rotacionar_bytes(content: bytes, graus: int) -> Optional[bytes]:
    """Rotaciona a imagem (mesma regra visual do `?rot=` em servir_arquivo:
    ângulo é o de rotação à esquerda). Retorna None em caso de erro."""
    try:
        with Image.open(io.BytesIO(content)) as img:
            img = ImageOps.exif_transpose(img)
            girada = img.rotate(graus, expand=True)
            buf = io.BytesIO()
            girada.save(buf, format="JPEG", quality=90)
            return buf.getvalue()
    except Exception:
        logger.exception("Falha ao rotacionar imagem em %s graus para inline no PDF.", graus)
        return None


def _inline_registro_por_hash(arquivo_hash: str, rot: Optional[str]) -> Optional[str]:
    """Resolve um `<img src="/api/arquivo/<hash>/">` direto do banco/storage,
    sem round-trip HTTP pelo próprio backend. Retorna data: URI.

    Modo diagnóstico temporário: em caso de falha, em vez de devolver None
    (o que faz `_inline_all_images` manter a tag <img> original e a imagem
    ficar invisível/quebrada sem explicação), devolve um placeholder visual
    com o motivo exato do erro — assim dá pra diagnosticar direto pelo PDF
    baixado, sem precisar de acesso a logs do servidor.
    """
    registro, tipo = _registro_por_hash(arquivo_hash)
    if registro is None:
        motivo = f"Nenhum RegistroEscrita/RegistroDesenho encontrado para arquivo_hash='{arquivo_hash}'"
        logger.warning("Registro não encontrado para arquivo_hash=%s (inline PDF).", arquivo_hash)
        return _svg_erro_data_uri(motivo)

    content, content_type, motivo = _ler_bytes_do_registro(registro, tipo)
    if content is None:
        return _svg_erro_data_uri(motivo or "motivo desconhecido")

    if rot in ("90", "180", "270"):
        girado = _rotacionar_bytes(content, int(rot))
        if girado is not None:
            content, content_type = girado, "image/jpeg"

    content, content_type = _recompress_image(content, content_type)
    encoded = base64.b64encode(content).decode("ascii")
    return f"data:{content_type};base64,{encoded}"


def _inline_image(url: str) -> Optional[str]:
    """Baixa uma imagem e devolve um data: URI. Retorna None se falhar."""
    start = time.monotonic()
    try:
        with httpx.Client(timeout=_IMAGE_FETCH_TIMEOUT, follow_redirects=True) as client:
            response = client.get(url)
        elapsed = (time.monotonic() - start) * 1000
        if response.status_code != 200:
            logger.warning(
                "Imagem retornou status %s em %.0f ms: %s",
                response.status_code,
                elapsed,
                url,
            )
            return None
        content = response.content
        if len(content) > _MAX_IMAGE_BYTES:
            logger.warning(
                "Imagem excede limite inline (%s bytes > %s): %s",
                len(content),
                _MAX_IMAGE_BYTES,
                url,
            )
            return None
        content_type = response.headers.get("content-type")
        if not content_type:
            guessed, _ = mimetypes.guess_type(urlparse(url).path)
            content_type = guessed or "image/jpeg"
        content_type = content_type.split(";", 1)[0].strip()

        original_bytes = len(content)
        content, content_type = _recompress_image(content, content_type)
        encoded = base64.b64encode(content).decode("ascii")
        logger.debug(
            "Imagem inlined em %.0f ms: %s bytes (orig=%s), type=%s, origem=%s",
            elapsed,
            len(content),
            original_bytes,
            content_type,
            url,
        )
        return f"data:{content_type};base64,{encoded}"
    except Exception:
        logger.exception("Falha ao baixar imagem para inline: %s", url)
        return None


_IMG_SRC_RE = re.compile(r'(<img\b[^>]*?\bsrc=)(["\'])(?P<url>[^"\']+)\2', re.IGNORECASE)


def _inline_all_images(html: str) -> str:
    """Substitui src de <img> por data: URIs quando possível."""
    cache: dict[str, Optional[str]] = {}
    counters = {"total": 0, "inlined": 0, "skipped_data": 0, "failed": 0}

    def _replace(match: re.Match) -> str:
        raw_url = match.group("url")
        # O HTML armazenado costuma vir com entidades escapadas (&amp;, &#x2F;...),
        # o que quebra as URLs assinadas do S3. Precisamos desfazer para baixar.
        url = _html.unescape(raw_url)
        counters["total"] += 1
        if url.startswith("data:"):
            counters["skipped_data"] += 1
            return match.group(0)

        if url not in cache:
            match_arquivo = _ARQUIVO_URL_RE.match(url)
            if match_arquivo:
                # /api/arquivo/<hash>/ (galeria de produções escrita/desenho):
                # resolve direto do banco/storage, sem round-trip HTTP pelo
                # próprio backend (evita depender de INTERNAL_API_BASE).
                qs = parse_qs(match_arquivo.group("qs") or "")
                rot = (qs.get("rot") or [None])[0]
                cache[url] = _inline_registro_por_hash(match_arquivo.group("hash"), rot)
            elif url.startswith("/"):
                # Outras URLs relativas residuais: mantém o comportamento antigo.
                fetch_url = f"{_INTERNAL_API_BASE}{url}"
                cache[url] = _inline_image(fetch_url)
            else:
                # URLs assinadas podem ter expirado (logo da escola, anexos antigos).
                # Re-assina se for do nosso bucket; noop caso contrário.
                fetch_url = refresh_presigned_url(url) or url
                cache[url] = _inline_image(fetch_url)
        data_uri = cache[url]
        if not data_uri:
            counters["failed"] += 1
            return match.group(0)
        counters["inlined"] += 1
        return f'{match.group(1)}"{data_uri}"'

    start = time.monotonic()
    result = _IMG_SRC_RE.sub(_replace, html)
    # Tamanho aproximado do payload de imagens no HTML final (base64 + overhead).
    inlined_bytes = sum(len(v) for v in cache.values() if v)
    logger.info(
        "Inline de imagens concluído em %.0f ms: total=%s inlined=%s falhas=%s já_data=%s (únicas=%s, ~%.1f MB em data:URIs)",
        (time.monotonic() - start) * 1000,
        counters["total"],
        counters["inlined"],
        counters["failed"],
        counters["skipped_data"],
        len(cache),
        inlined_bytes / (1024 * 1024),
    )
    return result


_PRINT_OVERRIDES = """
@page { size: A4; margin: 0; }
html, body { margin: 0; padding: 0; background: #fff; }
body > .ProseMirror { width: 210mm; margin: 0 auto; font-size: 15px; }
body > .ProseMirror .pagina {
  width: 210mm;
  min-height: 297mm;
  box-sizing: border-box;
  margin: 0;
  page-break-after: always;
  break-after: page;
}
body > .ProseMirror .pagina.capa {
  height: auto;
  max-height: 297mm;
  overflow: visible;
}
body > .ProseMirror .pagina:last-child {
  page-break-after: auto;
  break-after: auto;
}
body > .ProseMirror .capa p,
body > .ProseMirror .rodape p,
body > .ProseMirror .secao-header p,
body > .ProseMirror .ficha-item p,
body > .ProseMirror .portfolio-legenda p,
body > .ProseMirror .header-escola p {
  margin: 0;
  padding: 0;
}
body > .ProseMirror > p:empty {
  display: none;
}
"""


def _build_full_html(relatorio: Relatorio) -> str:
    css = _resolve_css(relatorio)
    conteudo_original = relatorio.conteudo or ""
    logger.debug(
        "Montando HTML para relatorio=%s (conteudo=%s bytes, css=%s bytes)",
        relatorio.id,
        len(conteudo_original),
        len(css),
    )
    conteudo = _inline_all_images(conteudo_original)
    html = (
        "<!doctype html>"
        "<html lang=\"pt-BR\">"
        "<head>"
        "<meta charset=\"utf-8\">"
        f"<title>Relatório {relatorio.id}</title>"
        f"<style>{css}</style>"
        f"<style>{_PRINT_OVERRIDES}</style>"
        "</head>"
        "<body>"
        # Escopo .ProseMirror replica o container usado no client, onde o CSS se aplica.
        f"<div class=\"ProseMirror\">{conteudo}</div>"
        "</body>"
        "</html>"
    )
    logger.debug("HTML final montado: %s bytes (relatorio=%s)", len(html), relatorio.id)
    return html


_FILENAME_SANITIZE_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return _FILENAME_SANITIZE_RE.sub("_", normalized).strip("._-") or "relatorio"


def build_filename(relatorio: Relatorio) -> str:
    """Nome de arquivo com sufixo aleatório para evitar colisões em downloads."""
    nome = "Estudante"
    crianca = Crianca.objects.filter(id=relatorio.id_crianca).only("nome_completo").first()
    if crianca and crianca.nome_completo:
        nome = crianca.nome_completo
    periodo = _slugify(relatorio.periodo or "periodo")[:40]
    estudante = _slugify(nome)[:60]
    suffix = secrets.token_hex(4)
    return f"relatorio_{estudante}_{periodo}_{suffix}.pdf"


def _storage_key_for(relatorio: Relatorio) -> str:
    timestamp = timezone.now().strftime("%Y%m%d%H%M%S")
    suffix = secrets.token_hex(3)
    return f"relatorios/{relatorio.id}/{timestamp}-{suffix}.pdf"


def ensure_pdf(relatorio: Relatorio) -> Tuple[bytes, bool, Optional[str]]:
    """Garante que o PDF existe e o devolve.

    Retorna `(pdf_bytes, cached, presigned_url)`:
      - `cached=True` quando o PDF veio direto do S3 (não renderizou de novo);
      - `presigned_url` é `None` quando S3 não está configurado — nesse caso
        os bytes vêm direto do renderer sem cache persistente.
    """
    start = time.monotonic()
    s3_on = is_s3_configured()
    logger.info(
        "ensure_pdf iniciado: relatorio=%s s3=%s pdf_storage_key=%s pdf_url=%s",
        relatorio.id,
        "configurado" if s3_on else "desabilitado",
        "presente" if relatorio.pdf_storage_key else "ausente",
        "presente" if relatorio.pdf_url else "ausente",
    )

    if s3_on:
        storage_key = relatorio.pdf_storage_key
        if not storage_key and relatorio.pdf_url:
            storage_key = extract_storage_key_from_url(relatorio.pdf_url)
            if storage_key:
                logger.debug(
                    "storage_key derivado de pdf_url para relatorio=%s: %s",
                    relatorio.id,
                    storage_key,
                )

        if storage_key:
            logger.info(
                "Tentando cache hit no S3 para relatorio=%s (key=%s)",
                relatorio.id,
                storage_key,
            )
            pdf_bytes = _download_from_s3(storage_key)
            if pdf_bytes is not None:
                presigned = generate_presigned_url(storage_key)
                if relatorio.pdf_storage_key != storage_key and presigned:
                    relatorio.pdf_storage_key = storage_key
                    relatorio.pdf_url = presigned
                    relatorio.save(update_fields=["pdf_storage_key", "pdf_url"])
                    logger.debug(
                        "pdf_storage_key preenchido a partir da URL antiga (relatorio=%s)",
                        relatorio.id,
                    )
                logger.info(
                    "Cache HIT: PDF do relatorio=%s servido do S3 (%s bytes, %.0f ms)",
                    relatorio.id,
                    len(pdf_bytes),
                    (time.monotonic() - start) * 1000,
                )
                return pdf_bytes, True, presigned
            # Chave inválida/objeto sumiu: cai para regeneração.
            logger.warning(
                "Cache MISS (key órfã): pdf_storage_key=%s não encontrada no S3. Regerando. (relatorio=%s)",
                storage_key,
                relatorio.id,
            )
            relatorio.pdf_storage_key = None
            relatorio.pdf_url = None
        else:
            logger.info(
                "Cache MISS: nenhum pdf_storage_key registrado para relatorio=%s. Gerando pela primeira vez.",
                relatorio.id,
            )
    else:
        logger.info(
            "S3 desabilitado — gerando PDF do relatorio=%s sem cache.",
            relatorio.id,
        )

    logger.info("Iniciando renderização do relatorio=%s", relatorio.id)
    t_build = time.monotonic()
    html = _build_full_html(relatorio)
    t_render_start = time.monotonic()
    logger.info(
        "HTML pronto em %.0f ms (%s bytes). Enviando para o renderer... (relatorio=%s)",
        (t_render_start - t_build) * 1000,
        len(html),
        relatorio.id,
    )
    pdf_bytes = render_html_to_pdf(html)
    t_rendered = time.monotonic()
    logger.info(
        "Renderer devolveu PDF em %.0f ms (%s bytes, relatorio=%s)",
        (t_rendered - t_render_start) * 1000,
        len(pdf_bytes),
        relatorio.id,
    )

    if not s3_on:
        logger.info(
            "Retornando bytes direto (sem upload S3) para relatorio=%s. Total ensure_pdf=%.0f ms",
            relatorio.id,
            (time.monotonic() - start) * 1000,
        )
        return pdf_bytes, False, None

    new_key = _storage_key_for(relatorio)
    logger.info(
        "Fazendo upload do PDF para S3: relatorio=%s key=%s (%s bytes)",
        relatorio.id,
        new_key,
        len(pdf_bytes),
    )
    t_upload_start = time.monotonic()
    stored_key, presigned = upload_bytes_to_storage(
        new_key, pdf_bytes, content_type="application/pdf"
    )
    logger.info(
        "Upload concluído em %.0f ms (key=%s, relatorio=%s)",
        (time.monotonic() - t_upload_start) * 1000,
        stored_key,
        relatorio.id,
    )
    relatorio.pdf_storage_key = stored_key
    relatorio.pdf_url = presigned
    relatorio.save(update_fields=["pdf_storage_key", "pdf_url"])
    logger.info(
        "PDF do relatório gerado e armazenado. relatorio=%s storage_key=%s total=%.0f ms",
        relatorio.id,
        stored_key,
        (time.monotonic() - start) * 1000,
    )
    return pdf_bytes, False, presigned


def invalidate_pdf_cache(relatorio: Relatorio) -> bool:
    """Descarta o PDF cacheado de um relatório.

    Usado após edições de `conteudo`: `ensure_pdf` trata a presença de
    `pdf_storage_key` como cache válido e devolveria bytes obsoletos. Zerar
    os campos força a próxima renderização. Também remove o objeto do S3
    para não acumular órfãos.

    Retorna True se havia algo para invalidar.
    """
    old_key = relatorio.pdf_storage_key
    if not old_key and not relatorio.pdf_url:
        return False

    relatorio.pdf_storage_key = None
    relatorio.pdf_url = None
    relatorio.save(update_fields=["pdf_storage_key", "pdf_url"])

    if old_key and is_s3_configured():
        try:
            delete_from_s3(old_key)
        except Exception:  # noqa: BLE001
            # Falha ao deletar S3 não deve derrubar a edição; o objeto vira
            # um órfão de storage até ser coletado por rotina externa.
            logger.exception(
                "Falha ao remover PDF obsoleto do S3 (relatorio=%s key=%s)",
                relatorio.id, old_key,
            )

    logger.info(
        "PDF cache invalidado para relatorio=%s (key anterior=%s)",
        relatorio.id, old_key,
    )
    return True


def _download_from_s3(key: str) -> Optional[bytes]:
    """Baixa os bytes de um objeto do S3. Retorna None em caso de erro/ausência."""
    if not is_s3_configured():
        return None
    start = time.monotonic()
    try:
        import boto3
        from botocore.config import Config
        from botocore.exceptions import BotoCoreError, ClientError

        region = os.getenv("AWS_REGION", "us-east-1")
        bucket = os.getenv("AWS_S3_BUCKET_NAME")
        normalized_key = key.lstrip("/")
        logger.debug(
            "Buscando objeto no S3: bucket=%s key=%s region=%s",
            bucket,
            normalized_key,
            region,
        )
        client = boto3.client(
            "s3",
            config=Config(signature_version="s3v4", region_name=region),
            region_name=region,
        )
        obj = client.get_object(Bucket=bucket, Key=normalized_key)
        data = obj["Body"].read()
        logger.info(
            "Download S3 OK em %.0f ms: key=%s (%s bytes)",
            (time.monotonic() - start) * 1000,
            normalized_key,
            len(data),
        )
        return data
    except (BotoCoreError, ClientError) as exc:
        logger.warning(
            "Falha ao baixar PDF do S3 em %.0f ms (key=%s): %s",
            (time.monotonic() - start) * 1000,
            key,
            exc,
        )
        return None
    except Exception:
        logger.exception("Erro inesperado ao baixar PDF do S3: %s", key)
        return None