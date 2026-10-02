"""Consulta do consumo da API OpenAI (tabela `openai_usage`). Só superadmin.

O registro é feito por `services/openai_usage.registrar_uso_openai`; aqui só
se lê. O consumo é da plataforma inteira (todas as redes), por isso a tela é
exclusiva do superadmin e as consultas usam `_base_manager` (sem recorte de
tenant) com filtros explícitos.

Filtros (query string, todos opcionais) — valem para os dois endpoints:
  model=<nome>                 ex.: gpt-5.4-mini, whisper-1
  data_inicio=AAAA-MM-DD       inclusive
  data_fim=AAAA-MM-DD          inclusive
  instituicao=<uuid>           a rede
  escola=<uuid>                a unidade
Valor malformado é ignorado (não vira 500).
"""

import uuid

from django.core.paginator import Paginator
from django.db.models import Count, Max, Sum
from django.db.models.functions import TruncDate
from django.utils.dateparse import parse_date
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.models import OpenAIUsage
from api.tenancy import is_superadmin

REGISTROS_POR_PAGINA = 10
REGISTROS_POR_PAGINA_MAX = 100
TOP_N = 10


def _sem_permissao():
    return Response({'error': 'Acesso restrito ao superadmin.'}, status=status.HTTP_403_FORBIDDEN)


def _data(valor):
    try:
        return parse_date(valor or '')
    except ValueError:  # formato certo, data impossível (ex.: 2026-02-31)
        return None


def _uuid(valor):
    try:
        return uuid.UUID(str(valor)) if valor else None
    except ValueError:
        return None


def _filtrar(request):
    params = request.query_params
    qs = OpenAIUsage._base_manager.all()

    if params.get('model'):
        qs = qs.filter(model=params['model'])
    if inicio := _data(params.get('data_inicio')):
        qs = qs.filter(criado_em__date__gte=inicio)
    if fim := _data(params.get('data_fim')):
        qs = qs.filter(criado_em__date__lte=fim)
    if instituicao := _uuid(params.get('instituicao')):
        qs = qs.filter(instituicao_id=instituicao)
    if escola := _uuid(params.get('escola')):
        qs = qs.filter(escola_id=escola)
    return qs


def _num(valor):
    """Decimal/None → float (os gráficos do recharts precisam de número)."""
    return float(valor or 0)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def resumo_uso_openai(request):
    """
    GET /admin/openai-usage/summary/

    {
      "totais": {"total_cost", "registros", "input_tokens", "output_tokens", "ultimo_uso"},
      "por_dia": [{"dia": "AAAA-MM-DD", "custo"}],
      "por_modelo": [{"model", "custo", "registros"}],
      "top_usuarios": [{"usuario_id", "nome", "custo", "registros"}],
      "top_escolas": [{"escola_id", "nome", "instituicao_nome", "custo", "registros"}],
      "modelos_disponiveis": ["..."]       # sem filtro, para o select da tela
    }
    """
    if not is_superadmin(request.user):
        return _sem_permissao()

    base = _filtrar(request)

    totais = base.aggregate(
        total_cost=Sum('total_cost'),
        registros=Count('id'),
        input_tokens=Sum('input_tokens'),
        output_tokens=Sum('output_tokens'),
        ultimo_uso=Max('criado_em'),
    )

    por_dia = (
        base.annotate(dia=TruncDate('criado_em'))
        .values('dia').annotate(custo=Sum('total_cost')).order_by('dia')
    )
    por_modelo = (
        base.values('model')
        .annotate(custo=Sum('total_cost'), registros=Count('id')).order_by('-custo')
    )
    top_usuarios = (
        base.filter(usuario__isnull=False)
        .values('usuario_id', 'usuario__nome')
        .annotate(custo=Sum('total_cost'), registros=Count('id')).order_by('-custo')[:TOP_N]
    )
    top_escolas = (
        base.filter(escola__isnull=False)
        .values('escola_id', 'escola__nome', 'escola__instituicao__nome')
        .annotate(custo=Sum('total_cost'), registros=Count('id')).order_by('-custo')[:TOP_N]
    )
    modelos = (
        OpenAIUsage._base_manager.exclude(model__isnull=True).exclude(model='')
        .values_list('model', flat=True).distinct().order_by('model')
    )

    return Response({
        'totais': {
            'total_cost': _num(totais['total_cost']),
            'registros': totais['registros'] or 0,
            'input_tokens': totais['input_tokens'] or 0,
            'output_tokens': totais['output_tokens'] or 0,
            'ultimo_uso': totais['ultimo_uso'],
        },
        'por_dia': [{'dia': d['dia'].isoformat(), 'custo': _num(d['custo'])} for d in por_dia if d['dia']],
        'por_modelo': [
            {'model': m['model'] or '(sem modelo)', 'custo': _num(m['custo']), 'registros': m['registros']}
            for m in por_modelo
        ],
        'top_usuarios': [
            {'usuario_id': u['usuario_id'], 'nome': u['usuario__nome'] or '(sem nome)',
             'custo': _num(u['custo']), 'registros': u['registros']}
            for u in top_usuarios
        ],
        'top_escolas': [
            {'escola_id': e['escola_id'], 'nome': e['escola__nome'],
             'instituicao_nome': e['escola__instituicao__nome'],
             'custo': _num(e['custo']), 'registros': e['registros']}
            for e in top_escolas
        ],
        'modelos_disponiveis': list(modelos),
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listar_uso_openai(request):
    """
    GET /admin/openai-usage/?page=&page_size=   (+ filtros)

    {
      "registros": [{"id", "created_at", "model", "input_tokens", "image_tokens",
                     "output_tokens", "total_cost", "usuario": {"id","nome"}|null,
                     "escola": {"id","nome"}|null, "instituicao": {"id","nome"}|null}],
      "paginacao": {"page", "page_size", "total", "total_pages"}
    }
    """
    if not is_superadmin(request.user):
        return _sem_permissao()

    try:
        page_size = max(1, min(int(request.query_params.get('page_size', REGISTROS_POR_PAGINA)), REGISTROS_POR_PAGINA_MAX))
    except (TypeError, ValueError):
        page_size = REGISTROS_POR_PAGINA

    qs = _filtrar(request).select_related('usuario', 'escola', 'instituicao').order_by('-criado_em', '-id')
    pagina = Paginator(qs, page_size).get_page(request.query_params.get('page'))

    def _ref(obj):
        return {'id': obj.id, 'nome': getattr(obj, 'nome', '')} if obj else None

    return Response({
        'registros': [
            {
                'id': r.id,
                'created_at': r.criado_em,
                'model': r.model,
                'input_tokens': r.input_tokens,
                'image_tokens': r.image_tokens,
                'output_tokens': r.output_tokens,
                'total_cost': str(r.total_cost),
                'usuario': _ref(r.usuario),
                'escola': _ref(r.escola),
                'instituicao': _ref(r.instituicao),
            }
            for r in pagina.object_list
        ],
        'paginacao': {
            'page': pagina.number,
            'page_size': page_size,
            'total': pagina.paginator.count,
            'total_pages': pagina.paginator.num_pages,
        },
    })