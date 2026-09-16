"""
Matriz de indicadores do Registro Guiado por turma (tela "Aprendizagens
consolidadas" da coordenação).

Para uma turma + período avaliativo, devolve a matriz criança × indicador com o
ESTADO de cada marcação (0–3), além das categorias (campos), das crianças e do
resumo por estado.

Modelo de marcação do Guiado: a professora toca de 1x a 3x por indicador/criança
(`MAX_MARCACOES = 3`), e cada toque vira uma linha em `RegistroObservacao`
(`resposta='Sim'`). Logo o **nível** = nº de registros daquela (criança, pergunta)
no período:
  0 → Não observado · 1 → Às vezes · 2 → Em desenvolvimento · 3 → Desenvolvido
"""

from __future__ import annotations

import re
import unicodedata
from collections import OrderedDict, defaultdict
from datetime import date

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Count

from api.models import (
    Crianca,
    PerguntaBNCC,
    PeriodoAvaliativo,
    RegistroDesenho,
    RegistroEscrita,
    RegistroLeitura,
    RegistroObservacao,
    Turma,
)
from api.services.fases_producao import fase_desenho_canonica

NIVEL_MAX = 3


def _norm_nome(s: str | None) -> str:
    """Normaliza nome (minúsculo, sem acentos) para casar escrita/desenho ↔ criança."""
    s = (s or '').strip().lower()
    return ''.join(c for c in unicodedata.normalize('NFKD', s) if not unicodedata.combining(c))


def _producoes_por_crianca(turma_id, criancas, recorte):
    """Para a turma, devolve {crianca_id: {escrita, desenho, leitura}} com a
    classificação do ÚLTIMO registro de cada modalidade no recorte (ou geral, se
    `recorte` é None). Cada valor é `{classe, data}` ou `None`.

    Recebe o `Recorte` (período avaliativo OU intervalo de datas), não o dict do
    período: com intervalo à mão não existe período casado, e usar o dict fazia
    as produções ignorarem o filtro enquanto a matriz o respeitava.

    Escrita/desenho não têm `crianca_id` — casam por nome+turma (`_norm_nome`).
    Leitura casa por `crianca_id` e só conta `status='confirmado'`.
    """
    # Mapa nome_normalizado -> crianca_id (para escrita/desenho).
    id_por_nome = {_norm_nome(c['nome_completo']): str(c['id']) for c in criancas}
    crianca_ids = {str(c['id']) for c in criancas}

    producoes = {cid: {'escrita': None, 'desenho': None, 'leitura': None} for cid in crianca_ids}

    def _em_periodo(qs, campo='data_criacao'):
        if recorte:
            return qs.filter(**{
                f'{campo}__date__gte': recorte.data_inicio,
                f'{campo}__date__lte': recorte.data_fim,
            })
        return qs

    # Escrita: último etapa_ia por nome (ordem asc → o último vence).
    esc = _em_periodo(RegistroEscrita.objects.filter(turma_id=str(turma_id)))
    for nome_aluno, etapa, data in esc.order_by('data_criacao').values_list(
        'nome_aluno', 'etapa_ia', 'data_criacao'
    ):
        cid = id_por_nome.get(_norm_nome(nome_aluno))
        if cid and etapa:
            producoes[cid]['escrita'] = {'classe': etapa, 'data': data.date().isoformat()}

    # Desenho: última fase_desenho por nome (valores legados → rótulo canônico).
    des = _em_periodo(RegistroDesenho.objects.filter(turma_id=str(turma_id)))
    for nome_aluno, fase, data in des.order_by('data_criacao').values_list(
        'nome_aluno', 'fase_desenho', 'data_criacao'
    ):
        cid = id_por_nome.get(_norm_nome(nome_aluno))
        if cid and fase:
            producoes[cid]['desenho'] = {'classe': fase_desenho_canonica(fase), 'data': data.date().isoformat()}

    # Leitura: última classe_escolhida confirmada por crianca.
    lei = _em_periodo(
        RegistroLeitura.objects.filter(crianca_id__in=crianca_ids, status='confirmado')
        .exclude(classe_escolhida='')
    )
    for crianca_id, classe, data in lei.order_by('data_criacao').values_list(
        'crianca_id', 'classe_escolhida', 'data_criacao'
    ):
        cid = str(crianca_id)
        if cid in producoes and classe:
            producoes[cid]['leitura'] = {'classe': classe, 'data': data.date().isoformat()}

    return producoes


def _padronizar_faixa(faixa: str | None) -> str:
    """Normaliza a faixa da turma para casar com `PerguntaBNCC.faixa_etaria`.

    Espelha `getStandardizedFaixaEtaria` do front (observationUtils): "Nível 5-A"
    → "Nível 5", "1º ANO B" → "1º ANO", etc.
    """
    if not faixa:
        return ''
    t = faixa.strip()
    low = t.lower()
    if 'bebês' in low or 'bebes' in low:
        return 'Bebês'
    if 'crianças bem pequenas' in low or 'criancas bem pequenas' in low:
        return 'Crianças bem pequenas'
    if 'crianças pequenas' in low or 'criancas pequenas' in low:
        return 'Crianças pequenas'
    if low == 'adaptação' or low == 'adaptacao':
        return 'Adaptação'
    m = re.search(r'N[íi]vel\s*(\d+)', t, re.IGNORECASE)
    if m:
        return f'Nível {m.group(1)}'
    m = re.search(r'(\d+)\s*º?\s*ANO', t, re.IGNORECASE)
    if m:
        return f'{m.group(1)}º ANO'
    return t


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def indicadores_turma(request):
    """Matriz criança × indicador (estado 0–3) de uma turma, no recorte da coordenação.

    Aceita o mesmo contrato de recorte das demais telas: `periodo_id`, ou
    `data_inicio`+`data_fim`. O parâmetro legado `periodo` (id do
    PeriodoAvaliativo) continua sendo lido, para não quebrar links antigos.

    Sem nenhum deles, cai no período avaliativo vigente — antes o default era
    "sem filtro de data" (todo o histórico), o que divergia do recorte que o
    resto do painel exibia.
    """
    from api.services.coordenacao_cache import RecorteInvalido, resolver_recorte

    turma_id = request.GET.get('turma_id')
    periodo_id = request.GET.get('periodo_id') or request.GET.get('periodo') or None
    if not turma_id:
        return Response({'error': 'turma_id é obrigatório'}, status=status.HTTP_400_BAD_REQUEST)

    def _data(valor):
        return date.fromisoformat(valor) if valor else None

    try:
        recorte = resolver_recorte(
            periodo_id=periodo_id,
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

    turma = Turma.objects.filter(id=turma_id).first()
    if not turma:
        return Response({'error': 'turma não encontrada'}, status=status.HTTP_404_NOT_FOUND)

    faixa = _padronizar_faixa(turma.faixa_etaria)

    # Indicadores (perguntas) da faixa, agrupados por campo de experiência.
    perguntas = list(
        PerguntaBNCC.objects.filter(faixa_etaria=faixa)
        .values('id', 'pergunta', 'campo_experiencia', 'area_conhecimento')
        .order_by('campo_experiencia', 'created_at')
    )
    if not perguntas and faixa:
        perguntas = list(
            PerguntaBNCC.objects.filter(faixa_etaria__icontains=faixa)
            .values('id', 'pergunta', 'campo_experiencia', 'area_conhecimento')
            .order_by('campo_experiencia', 'created_at')
        )
    pergunta_ids = [p['id'] for p in perguntas]

    # Crianças ativas da turma.
    criancas_qs = Crianca.objects.filter(turma_id=turma_id)
    try:
        criancas_qs = criancas_qs.exclude(status_vinculo='inativo')
    except Exception:
        pass
    criancas = list(criancas_qs.values('id', 'nome_completo').order_by('nome_completo'))
    crianca_ids = [c['id'] for c in criancas]

    # Períodos avaliativos — mantidos na resposta para quem já os consome.
    periodos = list(
        PeriodoAvaliativo.objects.values('id', 'descricao', 'data_inicio', 'data_fim')
        .order_by('data_inicio')
    )
    sel = next(
        (p for p in periodos if recorte and str(p['id']) == str(recorte.periodo_id)),
        None,
    )

    # Contagem de marcações por (criança, pergunta) → nível.
    regs = RegistroObservacao.objects.filter(
        crianca_id__in=crianca_ids, pergunta_id__in=pergunta_ids
    )
    if recorte:
        regs = regs.filter(
            data_observacao__gte=recorte.data_inicio,
            data_observacao__lte=recorte.data_fim,
        )
    contagens = regs.values('crianca_id', 'pergunta_id').annotate(n=Count('id'))

    matriz: dict[str, dict[str, int]] = defaultdict(dict)
    for row in contagens:
        nivel = min(row['n'], NIVEL_MAX)
        matriz[str(row['crianca_id'])][str(row['pergunta_id'])] = nivel

    # Categorias (campos) com seus indicadores, na ordem das perguntas.
    categorias: "OrderedDict[str, list]" = OrderedDict()
    for p in perguntas:
        campo = p['campo_experiencia'] or 'Outros'
        categorias.setdefault(campo, []).append({'id': str(p['id']), 'label': p['pergunta']})

    # Resumo por estado (cobre TODAS as células possíveis, inclusive 0).
    resumo = {'naoObs': 0, 'asVezes': 0, 'emDesenv': 0, 'desenv': 0}
    for c in crianca_ids:
        linha = matriz.get(str(c), {})
        for pid in pergunta_ids:
            nivel = linha.get(str(pid), 0)
            if nivel == 0:
                resumo['naoObs'] += 1
            elif nivel == 1:
                resumo['asVezes'] += 1
            elif nivel == 2:
                resumo['emDesenv'] += 1
            else:
                resumo['desenv'] += 1

    producoes = _producoes_por_crianca(turma_id, criancas, recorte)

    return Response({
        'turma': {'id': str(turma.id), 'nome': turma.nome, 'faixa': turma.faixa_etaria},
        'periodos': [
            {'id': str(p['id']), 'descricao': p['descricao']} for p in periodos
        ],
        'periodo_selecionado': str(sel['id']) if sel else None,
        'recorte_descricao': recorte.descricao if recorte else None,
        'criancas': [{'id': str(c['id']), 'nome': c['nome_completo']} for c in criancas],
        'categorias': [{'campo': k, 'perguntas': v} for k, v in categorias.items()],
        'matriz': {k: dict(v) for k, v in matriz.items()},
        'producoes': producoes,
        'resumo': resumo,
        'total_marcacoes': len(crianca_ids) * len(pergunta_ids),
    }, status=status.HTTP_200_OK)
