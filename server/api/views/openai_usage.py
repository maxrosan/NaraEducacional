import hashlib
import logging
from datetime import date

from django.core.cache import cache
from django.http import JsonResponse
from django.db.models import Count, Max, Sum
from django.db.models.functions import TruncDay
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from api.models import OpenAIUsage
from api.tenancy import is_superadmin

logger = logging.getLogger(__name__)

# TTL do cache do summary em segundos (5 minutos)
_SUMMARY_CACHE_TTL = 300


# ─── Autenticação ─────────────────────────────────────────────────────────────

def _admin_required(request) -> JsonResponse | None:
    """Só admin (da própria instituição) e superadmin (todas) veem o consumo."""
    user = request.user
    if is_superadmin(user):
        return None
    if getattr(user, "nivel", "") == "admin":
        if not user.instituicao_id:
            # Sem isso, `_escopo` filtraria instituicao_id=None e mostraria
            # justamente os registros sem dono (uso do sistema).
            return JsonResponse({"error": "Usuário sem instituição vinculada."}, status=403)
        return None
    return JsonResponse({"error": "Acesso restrito a administradores."}, status=403)


def _datas_validas(data_inicio, data_fim) -> JsonResponse | None:
    """Valida `YYYY-MM-DD` antes da query (senão vira 500 no except genérico)."""
    try:
        for valor in (data_inicio, data_fim):
            if valor:
                date.fromisoformat(valor)
    except ValueError:
        return JsonResponse({"error": "Datas inválidas (use YYYY-MM-DD)."}, status=400)
    return None


def _escopo(request, qs):
    """Filtro explícito por instituição, além do TenantManager.

    Retorna (queryset, id_do_escopo) — o id entra na chave do cache para que o
    resumo de uma instituição nunca seja servido para outra.
    """
    if is_superadmin(request.user):
        return qs, "todas"
    inst = request.user.instituicao_id
    return qs.filter(instituicao_id=inst), str(inst)


def _aplicar_filtros(qs, model_filter, usuario_filter, data_inicio, data_fim):
    if model_filter:
        qs = qs.filter(model=model_filter)
    if usuario_filter:
        qs = qs.filter(usuario_id=usuario_filter)
    if data_inicio:
        qs = qs.filter(criado_em__date__gte=data_inicio)
    if data_fim:
        qs = qs.filter(criado_em__date__lte=data_fim)
    return qs


def _cache_key(prefix: str, **filtros) -> str:
    """Gera chave de cache única baseada nos filtros ativos."""
    partes = ":".join(f"{k}={v}" for k, v in sorted(filtros.items()) if v)
    digest = hashlib.md5(partes.encode()).hexdigest()[:8]
    return f"{prefix}:{digest}"


# ─── Endpoint 1: Summary (com cache) ─────────────────────────────────────────

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def openai_usage_summary(request):
    """
    GET /api/admin/openai-usage/summary/

    Retorna totais agregados, série temporal, breakdown por modelo e top usuários.
    Resultado cacheado por 5 minutos — ideal para cards e gráficos.

    Query params (opcionais — afetam o cache key):
        model        — filtra por modelo
        data_inicio  — YYYY-MM-DD
        data_fim     — YYYY-MM-DD
    """
    erro = _admin_required(request)
    if erro:
        return erro

    model_filter = request.GET.get("model", "").strip() or None
    data_inicio  = request.GET.get("data_inicio", "").strip() or None
    data_fim     = request.GET.get("data_fim", "").strip() or None

    erro = _datas_validas(data_inicio, data_fim)
    if erro:
        return erro

    base_qs, escopo = _escopo(request, OpenAIUsage.objects.all())
    key = _cache_key(
        "openai_summary",
        escopo=escopo,
        model=model_filter or "",
        di=data_inicio or "",
        df=data_fim or "",
    )

    cached = cache.get(key)
    if cached:
        cached["_cache"] = "HIT"
        return JsonResponse(cached)

    try:
        qs = _aplicar_filtros(base_qs, model_filter, None, data_inicio, data_fim)

        # ── Totais globais ────────────────────────────────────────────────
        totais = qs.aggregate(
            total_input_tokens=Sum("input_tokens"),
            total_output_tokens=Sum("output_tokens"),
            total_image_tokens=Sum("image_tokens"),
            total_cost=Sum("total_cost"),
            total_registros=Count("id"),
            ultimo_uso=Max("criado_em"),
        )

        # ── Série temporal (por dia) ──────────────────────────────────────
        por_dia = list(
            qs.annotate(dia=TruncDay("criado_em"))
              .values("dia")
              .annotate(
                  custo=Sum("total_cost"),
                  registros=Count("id"),
                  input_tokens=Sum("input_tokens"),
                  output_tokens=Sum("output_tokens"),
              )
              .order_by("dia")
        )

        # ── Breakdown por modelo ──────────────────────────────────────────
        por_modelo = list(
            qs.values("model")
              .annotate(
                  custo=Sum("total_cost"),
                  registros=Count("id"),
                  input_tokens=Sum("input_tokens"),
                  output_tokens=Sum("output_tokens"),
              )
              .order_by("-custo")
        )

        # ── Top 10 usuários ───────────────────────────────────────────────
        top_usuarios = list(
            qs.filter(usuario__isnull=False)
              .values("usuario__id", "usuario__nome")
              .annotate(custo=Sum("total_cost"), registros=Count("id"))
              .order_by("-custo")[:10]
        )

        # ── Modelos disponíveis (para o filtro do frontend) ───────────────
        modelos_disponiveis = list(
            base_qs
              .exclude(model__isnull=True)
              .values_list("model", flat=True)
              .distinct()
              .order_by("model")
        )

        payload = {
            "_cache": "MISS",
            "totais": {
                "input_tokens":  totais["total_input_tokens"]  or 0,
                "output_tokens": totais["total_output_tokens"] or 0,
                "image_tokens":  totais["total_image_tokens"]  or 0,
                "total_cost":    str(totais["total_cost"] or "0"),
                "registros":     totais["total_registros"]     or 0,
                "ultimo_uso":    totais["ultimo_uso"].isoformat() if totais["ultimo_uso"] else None,
            },
            "por_dia": [
                {
                    "dia":           item["dia"].strftime("%Y-%m-%d"),
                    "custo":         str(item["custo"]),
                    "registros":     item["registros"],
                    "input_tokens":  item["input_tokens"],
                    "output_tokens": item["output_tokens"],
                }
                for item in por_dia
            ],
            "por_modelo": [
                {
                    "model":         item["model"] or "desconhecido",
                    "custo":         str(item["custo"]),
                    "registros":     item["registros"],
                    "input_tokens":  item["input_tokens"],
                    "output_tokens": item["output_tokens"],
                }
                for item in por_modelo
            ],
            "top_usuarios": [
                {
                    "usuario_id": str(item["usuario__id"]),
                    "nome":       item["usuario__nome"] or "Sem nome",
                    "custo":      str(item["custo"]),
                    "registros":  item["registros"],
                }
                for item in top_usuarios
            ],
            "modelos_disponiveis": modelos_disponiveis,
        }

        cache.set(key, payload, _SUMMARY_CACHE_TTL)
        return JsonResponse(payload)

    except Exception as exc:
        logger.error("[openai_summary] Erro: %s", exc, exc_info=True)
        return JsonResponse({"error": "Erro interno ao carregar summary."}, status=500)


# ─── Endpoint 2: Registros paginados (sem cache) ──────────────────────────────

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def listar_openai_usage(request):
    """
    GET /api/admin/openai-usage/

    Retorna registros detalhados paginados. Sem cache — sempre atualizado.

    Query params:
        model        — filtra por modelo
        usuario_id   — filtra por UUID do usuário
        data_inicio  — YYYY-MM-DD
        data_fim     — YYYY-MM-DD
        page         — página atual (default 1)
        page_size    — itens por página (default 10, máx 100)
    """
    erro = _admin_required(request)
    if erro:
        return erro

    model_filter   = request.GET.get("model", "").strip() or None
    usuario_filter = request.GET.get("usuario_id", "").strip() or None
    data_inicio    = request.GET.get("data_inicio", "").strip() or None
    data_fim       = request.GET.get("data_fim", "").strip() or None

    erro = _datas_validas(data_inicio, data_fim)
    if erro:
        return erro

    try:
        page      = max(1, int(request.GET.get("page", 1)))
        page_size = min(100, max(1, int(request.GET.get("page_size", 10))))
    except (ValueError, TypeError):
        page, page_size = 1, 10

    try:
        qs, _ = _escopo(request, OpenAIUsage.objects.select_related("usuario"))
        qs = _aplicar_filtros(qs, model_filter, usuario_filter, data_inicio, data_fim)

        total_registros = qs.count()
        offset          = (page - 1) * page_size
        registros_page  = qs[offset: offset + page_size]

        registros_data = [
            {
                "id":            r.id,
                "model":         r.model,
                "input_tokens":  r.input_tokens,
                "image_tokens":  r.image_tokens,
                "output_tokens": r.output_tokens,
                "input_cost":    str(r.input_cost),
                "output_cost":   str(r.output_cost),
                "total_cost":    str(r.total_cost),
                "created_at":    r.criado_em.isoformat(),  # chave mantida para o frontend
                "usuario": {
                    "id":   str(r.usuario.id) if r.usuario else None,
                    "nome": getattr(r.usuario, "nome", str(r.usuario)) if r.usuario else "Sistema",
                },
            }
            for r in registros_page
        ]

        return JsonResponse({
            "registros": registros_data,
            "paginacao": {
                "total":       total_registros,
                "page":        page,
                "page_size":   page_size,
                "total_pages": max(1, (total_registros + page_size - 1) // page_size),
            },
        })

    except Exception as exc:
        logger.error("[openai_usage_list] Erro: %s", exc, exc_info=True)
        return JsonResponse({"error": "Erro interno ao carregar registros."}, status=500)