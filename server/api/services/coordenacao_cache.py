"""
Gera os agregados consumidos pela página de coordenação (`CoordinatorHomePage`)
e pela página de indicadores (`IndicatorView`).

Portado do legado com as seguintes mudanças de schema (não é só renomeação):

  - `Crianca` → `Aluno`.
  - `PerguntaBNCC` (1 tabela, campo_experiencia/faixa_etaria em texto livre)
    virou 3 conceitos separados: `Pergunta.campo_experiencia` (FK pra
    `CampoPedagogico`), `Pergunta.faixa_etaria` (FK DIRETA pra `Turma` — não
    precisa mais de fuzzy-match de texto) e `Pergunta.habilidade_bncc` (FK
    pra `HabilidadeBNCC`, catálogo oficial).
  - `ProducaoCrianca`/`ProducaoFoto` (2 tabelas) → `Producao` + `ProducaoAluno`
    (junção).
  - `RegistroEscrita`/`RegistroDesenho` ganharam `aluno` como FK de verdade
    (no legado só tinham `nome_aluno` texto) — a alfabetização e a evidência
    recente usam o id direto, sem fuzzy-match de nome.
  - `data_criacao` → `criado_em`; `PlanejamentoSemanal.professora_id` →
    `.professor_id`; `Relatorio.id_crianca` → `.aluno_id`.
  - Multi-tenant: toda função recebe `escola_id` e filtra por ele
    explicitamente — não confia no TenantManager/contexto de request, porque
    este service também roda fora do ciclo request/response (ex.: management
    command, worker). O legado era single-tenant e não filtrava por nada.
  - `Pergunta` pode ser oficial (escola nula) ou customizada pela escola —
    `_perguntas_visiveis` combina as duas, mesmo padrão usado no resto da API.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from django.db import transaction
from django.db.models import Count, Max, Min, Q
from django.db.models.functions import Length, Substr
from django.utils import timezone

from api.models import (
    Aluno, CoordenacaoCache, ObservacaoTranscricao, PeriodoAvaliativo,
    Pergunta, PlanejamentoHabilidade, PlanejamentoSemanal, Producao, ProducaoAluno,
    RegistroDesenho, RegistroEscrita, RegistroLeitura, RegistroObservacao,
    Relatorio, Turma, UsuarioTurma,
)
from api.services.fases_producao import FASES_ESCRITA as ORDEM_ESCRITA

logger = logging.getLogger(__name__)

CACHE_SCHEMA_VERSION = '8'
JANELA_DIAS = 30
JANELA_REGISTRO_RECENTE_DIAS = 15
SEMANAS_ENGAJAMENTO = 4
SEM_CLASSIFICACAO = 'Sem classificação'
MAX_DIAS_RECORTE = 366


def sem_acento_min(s: str | None) -> str:
    """Minúsculo, sem acento, sem espaços nas pontas — para casar texto livre."""
    s = (s or '').strip().lower()
    return ''.join(c for c in unicodedata.normalize('NFKD', s) if not unicodedata.combining(c))


def _norm_nome(s: str | None) -> str:
    return sem_acento_min(s)


def _padronizar_faixa(faixa: str | None) -> str:
    """Normaliza o rótulo de nível pra casar `Turma.faixa_etaria` com
    `Pergunta.faixa_etaria`: "Nível 5-A" → "Nível 5", "1º ANO B" → "1º ANO".
    Espelha `getStandardizedFaixaEtaria` do frontend (observationUtils).
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
    if low in ('adaptação', 'adaptacao'):
        return 'Adaptação'
    m = re.search(r'N[íi]vel\s*(\d+)', t, re.IGNORECASE)
    if m:
        return f'Nível {m.group(1)}'
    m = re.search(r'(\d+)\s*º?\s*ANO', t, re.IGNORECASE)
    if m:
        return f'{m.group(1)}º ANO'
    return t


def _perguntas_visiveis(escola_id):
    """Perguntas oficiais (escola nula) + customizadas desta escola."""
    return Pergunta.todos.filter(Q(escola_id=escola_id) | Q(escola__isnull=True))


def _registros_do_periodo(escola_id, data_inicio: date, data_fim: date):
    """Registros de observação da escola, no período. Tupla
    `(aluno_id, professor_id, data_observacao, pergunta_id)`."""
    return RegistroObservacao.objects.filter(
        escola_id=escola_id,
        data_observacao__gte=data_inicio,
        data_observacao__lte=data_fim,
    ).values_list('aluno_id', 'professor_id', 'data_observacao', 'pergunta_id')


def _limites(recorte) -> tuple[date | None, date | None]:
    if not recorte:
        return None, None
    return recorte.data_inicio, recorte.data_fim


def diagnosticar_cache(
    escola_id, data_referencia: date | None = None, janela_dias: int = JANELA_DIAS,
) -> dict[str, Any]:
    """Contagens que explicam *por que* um payload sai vazio (não computa o snapshot)."""
    if data_referencia is None:
        data_referencia = timezone.localdate() - timedelta(days=1)
    data_inicio = data_referencia - timedelta(days=janela_dias)

    registros = RegistroObservacao.objects.filter(escola_id=escola_id)
    extremos = registros.aggregate(min_d=Min('data_observacao'), max_d=Max('data_observacao'))
    n_janela = registros.filter(
        data_observacao__gte=data_inicio, data_observacao__lte=data_referencia,
    ).count()

    return {
        'data_referencia': data_referencia.isoformat(),
        'data_inicio_janela': data_inicio.isoformat(),
        'janela_dias': janela_dias,
        'total_alunos_escola': Aluno.objects.filter(escola_id=escola_id).count(),
        'total_registros_escola': registros.count(),
        'registros_na_janela': n_janela,
        'data_observacao_min': extremos['min_d'].isoformat() if extremos['min_d'] else None,
        'data_observacao_max': extremos['max_d'].isoformat() if extremos['max_d'] else None,
    }


def _semana_inicio(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _comparativo_periodos(escola_id, recorte, total_habilidades: int, total_alunos: int) -> dict[str, Any]:
    """Resumo do recorte selecionado e do anterior (espelha IndicatorView)."""
    if not recorte:
        return {'periodoAtual': None, 'periodoAnterior': None}

    def resumo(p):
        if not p:
            return None
        ini, fim = p['data_inicio'], p['data_fim']
        habs: set[str] = set()
        profs: set[str] = set()
        alunos: set[str] = set()
        for aluno_id, professor_id, _data_obs, pergunta_id in _registros_do_periodo(escola_id, ini, fim):
            if pergunta_id:
                habs.add(str(pergunta_id))
            if professor_id:
                profs.add(str(professor_id))
            if aluno_id:
                alunos.add(str(aluno_id))
        return {
            'id': str(p['id']) if p.get('id') else None,
            'descricao': p['descricao'],
            'data_inicio': ini.isoformat(),
            'data_fim': fim.isoformat(),
            'coberturaPercentual': round(len(habs) / total_habilidades * 100) if total_habilidades else 0,
            'professoresAtivos': len(profs),
            'criancasEmAlerta': max(0, total_alunos - len(alunos)),
        }

    atual = {
        'id': recorte.periodo_id, 'descricao': recorte.descricao,
        'data_inicio': recorte.data_inicio, 'data_fim': recorte.data_fim,
    }

    if recorte.personalizado:
        dias = (recorte.data_fim - recorte.data_inicio).days
        fim_ant = recorte.data_inicio - timedelta(days=1)
        ini_ant = fim_ant - timedelta(days=dias)
        anterior = {
            'id': None,
            'descricao': f"{ini_ant.strftime('%d/%m/%Y')} – {fim_ant.strftime('%d/%m/%Y')}",
            'data_inicio': ini_ant, 'data_fim': fim_ant,
        }
    else:
        anterior = None
        for p in PeriodoAvaliativo.objects.filter(
            escola_id=escola_id, data_fim__lt=recorte.data_inicio,
        ).order_by('-data_fim').values('id', 'descricao', 'data_inicio', 'data_fim')[:1]:
            anterior = p

    return {'periodoAtual': resumo(atual), 'periodoAnterior': resumo(anterior)}


# ---------------------------------------------------------------------------
# Tabelas de referência (catálogo BNCC visível pra escola + mapa aluno→turma)
# ---------------------------------------------------------------------------

def _carregar_referencias_perguntas(escola_id) -> tuple[dict[str, str], int, dict[str, int]]:
    """Retorna `(campo_por_pergunta, total_perguntas, total_por_campo)`."""
    perguntas = list(_perguntas_visiveis(escola_id).values_list('id', 'campo_experiencia__nome'))
    campo_por_pergunta = {str(pid): (campo or 'Outros') for pid, campo in perguntas}
    total_por_campo: dict[str, int] = defaultdict(int)
    for campo in campo_por_pergunta.values():
        total_por_campo[campo] += 1
    return campo_por_pergunta, len(perguntas), total_por_campo


def _carregar_aluno_turma(escola_id) -> tuple[dict[str, str | None], int]:
    """Mapa `aluno_id -> turma_id` (string) + total de alunos ativos na escola."""
    aluno_turma = {
        str(aid): (str(tid) if tid else None)
        for aid, tid in Aluno.objects.filter(escola_id=escola_id).values_list('id', 'turma_id')
    }
    return aluno_turma, len(aluno_turma)


def _carregar_faixas_das_turmas(escola_id) -> tuple[dict[str, set[str]], dict[str, int]]:
    """Base do denominador da cobertura BNCC por turma.

    `Pergunta.faixa_etaria` é um rótulo de NÍVEL em texto (não FK) — casa com
    `Turma.faixa_etaria` via `_padronizar_faixa`, o que permite turmas
    paralelas (5º Ano A, 5º Ano B) compartilharem o mesmo conjunto de
    perguntas do nível.
    """
    perguntas_por_faixa: dict[str, set[str]] = defaultdict(set)
    for pid, faixa in _perguntas_visiveis(escola_id).exclude(
        faixa_etaria='',
    ).values_list('id', 'faixa_etaria'):
        faixa_padrao = _padronizar_faixa(faixa)
        if faixa_padrao:
            perguntas_por_faixa[faixa_padrao].add(str(pid))

    turmas = list(Turma.objects.filter(escola_id=escola_id).values('id', 'faixa_etaria'))
    faixa_por_turma = {str(t['id']): _padronizar_faixa(t['faixa_etaria']) for t in turmas}

    perguntas_da_turma: dict[str, set[str]] = {
        turma_id: perguntas_por_faixa.get(faixa, set())
        for turma_id, faixa in faixa_por_turma.items()
    }

    alunos_por_turma: dict[str, int] = defaultdict(int)
    for (tid,) in Aluno.objects.filter(escola_id=escola_id).exclude(turma_id=None).values_list('turma_id'):
        alunos_por_turma[str(tid)] += 1

    return perguntas_da_turma, dict(alunos_por_turma)


# ---------------------------------------------------------------------------
# Agregados de `gerar_indicadores_bncc`
# ---------------------------------------------------------------------------

def _cobertura_habilidades(
    registros_list: list, campo_por_pergunta: dict[str, str],
) -> tuple[set[str], dict[str, set[str]]]:
    habilidades_usadas: set[str] = set()
    usadas_por_campo: dict[str, set[str]] = defaultdict(set)
    for _aluno_id, _professor_id, _data_obs, pergunta_id in registros_list:
        if pergunta_id:
            pid = str(pergunta_id)
            habilidades_usadas.add(pid)
            usadas_por_campo[campo_por_pergunta.get(pid, 'Outros')].add(pid)
    return habilidades_usadas, usadas_por_campo


def _cobertura_por_turma(
    registros_list: list,
    aluno_turma: dict[str, str | None],
    campo_por_pergunta: dict[str, str],
    perguntas_da_turma: dict[str, set[str]] | None = None,
) -> tuple[dict[str, int], dict[str, set[str]], dict[str, dict[str, int]], dict[str, set[tuple]]]:
    por_turma_registros: dict[str, int] = defaultdict(int)
    por_turma_habs: dict[str, set[str]] = defaultdict(set)
    por_turma_campo: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    por_turma_pares: dict[str, set[tuple]] = defaultdict(set)

    for aluno_id, _professor_id, _data_obs, pergunta_id in registros_list:
        turma = aluno_turma.get(str(aluno_id))
        if not turma:
            continue
        por_turma_registros[turma] += 1
        if not pergunta_id:
            continue
        pid = str(pergunta_id)
        por_turma_habs[turma].add(pid)
        por_turma_campo[turma][campo_por_pergunta.get(pid, 'Outros')] += 1

        da_faixa = perguntas_da_turma.get(turma) if perguntas_da_turma else None
        if da_faixa is None or pid in da_faixa:
            por_turma_pares[turma].add((str(aluno_id), pid))

    return por_turma_registros, por_turma_habs, por_turma_campo, por_turma_pares


def _engajamento_semanal(registros_list: list, data_referencia: date) -> list[list]:
    semanas: list[list] = []
    for i in range(SEMANAS_ENGAJAMENTO - 1, -1, -1):
        ini = _semana_inicio(data_referencia) - timedelta(weeks=i)
        semanas.append([ini, ini + timedelta(days=6), 0])
    for _aluno_id, _professor_id, data_obs, _pergunta_id in registros_list:
        if not data_obs:
            continue
        for semana in semanas:
            if semana[0] <= data_obs <= semana[1]:
                semana[2] += 1
                break
    return semanas


def _formatar_cobertura_por_campo(
    usadas_por_campo: dict[str, set[str]], total_por_campo: dict[str, int],
) -> list[dict[str, Any]]:
    return sorted(
        (
            {
                'campo': campo,
                'usadas': len(usadas_por_campo.get(campo, set())),
                'total': total,
                'percent': round(len(usadas_por_campo.get(campo, set())) / total * 100) if total else 0,
            }
            for campo, total in total_por_campo.items()
        ),
        key=lambda x: -x['percent'],
    )


def gerar_indicadores_bncc(escola_id, periodo, data_referencia: date | None = None) -> dict[str, Any]:
    """Agregados pesados de `IndicatorView`, limitados ao período avaliativo e à escola."""
    campo_por_pergunta, total_habilidades, total_por_campo = _carregar_referencias_perguntas(escola_id)
    aluno_turma, total_alunos = _carregar_aluno_turma(escola_id)
    perguntas_da_turma, alunos_por_turma = _carregar_faixas_das_turmas(escola_id)

    ini, fim = _limites(periodo)
    if ini and fim:
        registros_list = list(_registros_do_periodo(escola_id, ini, fim))
    else:
        registros_list = list(
            RegistroObservacao.objects.filter(escola_id=escola_id).values_list(
                'aluno_id', 'professor_id', 'data_observacao', 'pergunta_id'
            )
        )

    if data_referencia is None:
        hoje = timezone.localdate()
        data_referencia = min(fim, hoje) if fim else hoje

    habilidades_usadas, usadas_por_campo = _cobertura_habilidades(registros_list, campo_por_pergunta)
    por_turma_registros, por_turma_habs, por_turma_campo, por_turma_pares = _cobertura_por_turma(
        registros_list, aluno_turma, campo_por_pergunta, perguntas_da_turma,
    )
    semanas = _engajamento_semanal(registros_list, data_referencia)

    return {
        'total_habilidades': total_habilidades,
        'habilidades_usadas': len(habilidades_usadas),
        'campos_ativos': sum(1 for s in usadas_por_campo.values() if s),
        'cobertura_por_campo': _formatar_cobertura_por_campo(usadas_por_campo, total_por_campo),
        'habilidades_pendentes_ids': sorted(pid for pid in campo_por_pergunta if pid not in habilidades_usadas),
        'por_turma': {
            turma: {
                'registros': por_turma_registros.get(turma, 0),
                'habilidades_usadas': len(por_turma_habs.get(turma, set())),
                'cobertura_pares': len(por_turma_pares.get(turma, set())),
                'cobertura_total': alunos_por_turma.get(turma, 0) * len(perguntas_da_turma.get(turma, ())),
            }
            for turma in set(por_turma_registros) | set(por_turma_habs) | set(alunos_por_turma)
        },
        'por_turma_campo': {t: dict(c) for t, c in por_turma_campo.items()},
        'semanal_4s': [{'semana_inicio': ini.isoformat(), 'registros': n} for ini, _fim, n in semanas],
        'comparativo_periodos': _comparativo_periodos(escola_id, periodo, total_habilidades, total_alunos),
    }


# ---------------------------------------------------------------------------
# Agregados de `gerar_payload_coordenacao`
# ---------------------------------------------------------------------------

def _bncc_usage_da_janela(escola_id, registros: list) -> list[dict]:
    contagem_por_pergunta: dict[str, int] = defaultdict(int)
    for _aluno_id, _professor_id, _data_obs, pergunta_id in registros:
        if pergunta_id:
            contagem_por_pergunta[str(pergunta_id)] += 1
    if not contagem_por_pergunta:
        return []

    campos_por_pergunta = {
        str(pid): campo
        for pid, campo in _perguntas_visiveis(escola_id).filter(
            id__in=list(contagem_por_pergunta.keys())
        ).values_list('id', 'campo_experiencia__nome')
        if campo
    }

    contagem_por_campo: dict[str, int] = defaultdict(int)
    for pid, count in contagem_por_pergunta.items():
        campo = campos_por_pergunta.get(pid)
        if campo:
            contagem_por_campo[campo] += count
    return [
        {'campo_experiencia': campo, 'count': count}
        for campo, count in sorted(contagem_por_campo.items(), key=lambda kv: -kv[1])
    ]


def _bncc_usage_por_turma(escola_id, registros: list) -> dict[str, list[dict]]:
    aluno_turma, _ = _carregar_aluno_turma(escola_id)

    contagem: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    perguntas_presentes: set[str] = set()
    for aluno_id, _professor_id, _data_obs, pergunta_id in registros:
        if not pergunta_id:
            continue
        turma = aluno_turma.get(str(aluno_id))
        if not turma:
            continue
        pid = str(pergunta_id)
        contagem[turma][pid] += 1
        perguntas_presentes.add(pid)

    if not perguntas_presentes:
        return {}

    campos_por_pergunta = {
        str(pid): campo
        for pid, campo in _perguntas_visiveis(escola_id).filter(
            id__in=list(perguntas_presentes)
        ).values_list('id', 'campo_experiencia__nome')
        if campo
    }

    saida: dict[str, list[dict]] = {}
    for turma, por_pergunta in contagem.items():
        por_campo: dict[str, int] = defaultdict(int)
        for pid, count in por_pergunta.items():
            campo = campos_por_pergunta.get(pid)
            if campo:
                por_campo[campo] += count
        if por_campo:
            saida[turma] = [
                {'campo_experiencia': campo, 'count': count}
                for campo, count in sorted(por_campo.items(), key=lambda kv: -kv[1])
            ]
    return saida


def _criancas_com_registro_recente(registros: list, limite_recente) -> list[str]:
    recentes: set[str] = set()
    for aluno_id, _professor_id, data_obs, _pergunta_id in registros:
        if data_obs >= limite_recente:
            recentes.add(str(aluno_id))
    return sorted(recentes)


def _criancas_com_evidencia_recente(escola_id, data_inicio, data_fim) -> list[str]:
    """Fontes: RegistroObservacao, ObservacaoTranscricao (id direto ou por
    nome), RegistroEscrita/RegistroDesenho (id direto), ProducaoAluno."""
    alunos = list(Aluno.objects.filter(escola_id=escola_id).values('id', 'nome_completo'))
    id_por_nome = {_norm_nome(a['nome_completo']): str(a['id']) for a in alunos}
    ids_validos = {str(a['id']) for a in alunos}

    com_evidencia: set[str] = set()

    def _por_id(valores):
        for aid in valores:
            if aid and str(aid) in ids_validos:
                com_evidencia.add(str(aid))

    def _por_nome(nomes):
        for nome in nomes:
            aid = id_por_nome.get(_norm_nome(nome))
            if aid:
                com_evidencia.add(aid)

    _por_id(
        RegistroObservacao.objects.filter(
            escola_id=escola_id, data_observacao__gte=data_inicio, data_observacao__lte=data_fim,
        ).values_list('aluno_id', flat=True)
    )

    transcricoes = ObservacaoTranscricao.objects.filter(
        escola_id=escola_id, data_observacao__gte=data_inicio, data_observacao__lte=data_fim,
    ).values_list('aluno_id', 'aluno_nome')
    _por_id(aid for aid, _nome in transcricoes if aid)
    _por_nome(nome for aid, nome in transcricoes if not aid)

    for modelo in (RegistroEscrita, RegistroDesenho):
        _por_id(
            modelo.objects.filter(
                escola_id=escola_id, criado_em__date__gte=data_inicio, criado_em__date__lte=data_fim,
            ).values_list('aluno_id', flat=True)
        )

    _por_id(
        ProducaoAluno.objects.filter(
            producao__escola_id=escola_id,
            producao__data_registro__gte=data_inicio,
            producao__data_registro__lte=data_fim,
        ).values_list('aluno_id', flat=True)
    )

    return sorted(com_evidencia)


def _professor_mais_recente_por_crianca(registros: list) -> dict[str, dict]:
    mais_recente: dict[str, dict] = {}
    for aluno_id, professor_id, data_obs, _pergunta_id in registros:
        aid = str(aluno_id)
        atual = mais_recente.get(aid)
        if atual is None or data_obs > date.fromisoformat(atual['data_observacao']):
            mais_recente[aid] = {
                'professor_id': str(professor_id) if professor_id else None,
                'data_observacao': data_obs.isoformat(),
            }
    return mais_recente


def _periodo_avaliativo_vigente(escola_id, data_referencia):
    qs = PeriodoAvaliativo.objects.filter(escola_id=escola_id)
    vigente = qs.filter(
        data_inicio__lte=data_referencia, data_fim__gte=data_referencia,
    ).order_by('-data_inicio').first()
    if vigente:
        return vigente
    return qs.filter(data_inicio__lte=data_referencia).order_by('-data_inicio').first()


@dataclass(frozen=True)
class Recorte:
    """A janela de tempo que dirige todo o painel da coordenação."""
    data_inicio: date
    data_fim: date
    descricao: str
    periodo_id: str | None = None
    personalizado: bool = False


class RecorteInvalido(ValueError):
    """Intervalo pedido pelo usuário que não dá para atender."""


def _recorte_de_periodo(periodo) -> Recorte | None:
    if not periodo:
        return None
    return Recorte(
        data_inicio=periodo.data_inicio, data_fim=periodo.data_fim,
        descricao=periodo.descricao, periodo_id=str(periodo.id),
    )


def resolver_recorte(
    escola_id,
    periodo_id=None,
    data_inicio: date | None = None,
    data_fim: date | None = None,
    data_referencia: date | None = None,
) -> Recorte | None:
    """1. data_inicio+data_fim → personalizado; 2. periodo_id → aquele período
    (desta escola); 3. nada → o que contém data_referencia (default: hoje)."""
    if data_inicio or data_fim:
        if not (data_inicio and data_fim):
            raise RecorteInvalido('Informe data_inicio e data_fim juntos.')
        if data_inicio > data_fim:
            raise RecorteInvalido('data_inicio não pode ser depois de data_fim.')
        dias = (data_fim - data_inicio).days + 1
        if dias > MAX_DIAS_RECORTE:
            raise RecorteInvalido(f'Intervalo de {dias} dias excede o máximo de {MAX_DIAS_RECORTE}.')
        return Recorte(
            data_inicio=data_inicio, data_fim=data_fim,
            descricao=f"{data_inicio.strftime('%d/%m/%Y')} – {data_fim.strftime('%d/%m/%Y')}",
            personalizado=True,
        )

    if periodo_id:
        return _recorte_de_periodo(PeriodoAvaliativo.objects.get(id=periodo_id, escola_id=escola_id))

    if data_referencia is None:
        data_referencia = timezone.localdate()
    return _recorte_de_periodo(_periodo_avaliativo_vigente(escola_id, data_referencia))


def _planos_por_turma_campo(escola_id, periodo):
    if periodo is None:
        return {}, [], None, {}

    planos_do_periodo = list(
        PlanejamentoSemanal.objects.filter(
            escola_id=escola_id,
            semana_inicio__gte=periodo.data_inicio, semana_inicio__lte=periodo.data_fim,
        ).values_list('id', 'turma_id')
    )

    linhas = PlanejamentoHabilidade.objects.filter(
        planejamento_diario__escola_id=escola_id,
        planejamento_diario__planejamento_semanal__semana_inicio__gte=periodo.data_inicio,
        planejamento_diario__planejamento_semanal__semana_inicio__lte=periodo.data_fim,
    ).values_list(
        'planejamento_diario__planejamento_semanal__turma_id',
        'planejamento_diario__planejamento_semanal_id',
        'habilidade_bncc__componente_curricular',
    )

    planos_por_chave: dict[tuple[str, str], set] = defaultdict(set)
    planos_com_habilidade: set = set()
    for turma_id, plano_id, campo in linhas:
        planos_com_habilidade.add(plano_id)
        if not campo:
            continue
        planos_por_chave[(str(turma_id), campo)].add(plano_id)

    por_turma_campo: dict[str, dict[str, int]] = defaultdict(dict)
    total_por_campo: dict[str, int] = defaultdict(int)
    for (turma_id, campo), plano_ids in planos_por_chave.items():
        n = len(plano_ids)
        por_turma_campo[turma_id][campo] = n
        total_por_campo[campo] += n

    sem_habilidade: dict[str, int] = defaultdict(int)
    for plano_id, turma_id in planos_do_periodo:
        if plano_id not in planos_com_habilidade:
            sem_habilidade[str(turma_id)] += 1

    campos_ordenados = [campo for campo, _ in sorted(total_por_campo.items(), key=lambda kv: -kv[1])]
    return dict(por_turma_campo), campos_ordenados, periodo.descricao, dict(sem_habilidade)


def _criancas_com_relatorio_finalizado(escola_id, periodo) -> list[str]:
    ini, fim = _limites(periodo)
    qs = Relatorio.objects.filter(escola_id=escola_id)
    if ini and fim:
        qs = qs.filter(criado_em__date__gte=ini, criado_em__date__lte=fim)

    ids = (
        qs.annotate(_cl=Length(Substr('conteudo', 1, 51)))
        .filter(_cl__gt=50)
        .values_list('aluno_id', flat=True)
        .distinct()
    )
    return sorted({str(i) for i in ids})


def _ranking_professores(escola_id, periodo) -> list[dict]:
    ini, fim = _limites(periodo)

    contagens: dict[str, dict[str, int]] = defaultdict(
        lambda: {'registros': 0, 'relatorios': 0, 'planejamentos': 0, 'portfolios': 0}
    )

    def _credita(pid, chave, n=1):
        if pid:
            contagens[str(pid)][chave] += n

    regs = RegistroObservacao.objects.filter(escola_id=escola_id)
    if ini and fim:
        regs = regs.filter(data_observacao__gte=ini, data_observacao__lte=fim)
    for row in regs.values('professor_id').annotate(n=Count('id')):
        _credita(row['professor_id'], 'registros', row['n'])

    plans = PlanejamentoSemanal.objects.filter(escola_id=escola_id)
    if ini and fim:
        plans = plans.filter(semana_inicio__gte=ini, semana_inicio__lte=fim)
    for row in plans.values('professor_id').annotate(n=Count('id')):
        _credita(row['professor_id'], 'planejamentos', row['n'])

    portfolio = Producao.objects.filter(escola_id=escola_id)
    if ini and fim:
        portfolio = portfolio.filter(data_registro__gte=ini, data_registro__lte=fim)
    for row in portfolio.values('professor_id').annotate(n=Count('id')):
        _credita(row['professor_id'], 'portfolios', row['n'])

    aluno_turma, _ = _carregar_aluno_turma(escola_id)
    turma_profs: dict[str, list[str]] = defaultdict(list)
    for tid, uid in UsuarioTurma.objects.filter(turma__escola_id=escola_id).values_list('turma_id', 'usuario_id'):
        turma_profs[str(tid)].append(str(uid))

    rels = Relatorio.objects.filter(escola_id=escola_id)
    if ini and fim:
        rels = rels.filter(criado_em__date__gte=ini, criado_em__date__lte=fim)
    for (aluno_id,) in rels.values_list('aluno_id'):
        turma = aluno_turma.get(str(aluno_id))
        if not turma:
            continue
        for uid in turma_profs.get(turma, []):
            _credita(uid, 'relatorios', 1)

    ranking = []
    for pid, m in contagens.items():
        total = m['registros'] + m['relatorios'] + m['planejamentos'] + m['portfolios']
        ranking.append({'professor_id': pid, **m, 'total': total})
    ranking.sort(key=lambda x: -x['total'])
    return ranking


# ---------------------------------------------------------------------------
# Bloco de alfabetização
# ---------------------------------------------------------------------------

def _mapas_alfabetizacao(escola_id, periodo):
    """Retorna `(alunos, escrita_por_aluno, leitura_por_aluno, periodo)`."""
    ini, fim = _limites(periodo)

    alunos = list(
        Aluno.objects.filter(escola_id=escola_id)
        .exclude(status_vinculo='inativo')
        .values('id', 'nome_completo', 'turma_id')
    )

    esc_qs = RegistroEscrita.objects.filter(escola_id=escola_id)
    if ini and fim:
        esc_qs = esc_qs.filter(criado_em__date__gte=ini, criado_em__date__lte=fim)
    escrita_por_aluno: dict[str, str] = {}
    for aluno_id, etapa in esc_qs.order_by('criado_em').values_list('aluno_id', 'etapa_ia'):
        if etapa:
            escrita_por_aluno[str(aluno_id)] = etapa

    lei_qs = RegistroLeitura.objects.filter(
        escola_id=escola_id, status='confirmado',
    ).exclude(classe_escolhida='')
    if ini and fim:
        lei_qs = lei_qs.filter(criado_em__date__gte=ini, criado_em__date__lte=fim)
    leitura_por_aluno: dict[str, str] = {}
    for aluno_id, classe in lei_qs.order_by('criado_em').values_list('aluno_id', 'classe_escolhida'):
        if classe:
            leitura_por_aluno[str(aluno_id)] = classe

    return alunos, escrita_por_aluno, leitura_por_aluno, periodo


def _classe_do_aluno(a, modalidade, escrita_por_aluno, leitura_por_aluno) -> str:
    if modalidade == 'escrita':
        return escrita_por_aluno.get(str(a['id'])) or SEM_CLASSIFICACAO
    return leitura_por_aluno.get(str(a['id'])) or SEM_CLASSIFICACAO


def alunos_por_classe_alfabetizacao(
    escola_id, periodo, modalidade: str, classe: str, turma_id: str | None = None,
) -> list[dict]:
    alunos, escrita_por_aluno, leitura_por_aluno, _ = _mapas_alfabetizacao(escola_id, periodo)
    res: list[dict] = []
    for a in alunos:
        if turma_id and str(a['turma_id']) != str(turma_id):
            continue
        if _classe_do_aluno(a, modalidade, escrita_por_aluno, leitura_por_aluno) == classe:
            res.append({
                'aluno_id': str(a['id']),
                'nome': a['nome_completo'],
                'turma_id': str(a['turma_id']) if a['turma_id'] else None,
            })
    res.sort(key=lambda x: (x['nome'] or '').lower())
    return res


def _alfabetizacao(escola_id, periodo) -> dict:
    alunos, escrita_por_aluno, leitura_por_aluno, _ = _mapas_alfabetizacao(escola_id, periodo)
    total = len(alunos)

    esc_dist: dict[str, int] = defaultdict(int)
    lei_dist: dict[str, int] = defaultdict(int)
    for a in alunos:
        esc_dist[_classe_do_aluno(a, 'escrita', escrita_por_aluno, leitura_por_aluno)] += 1
        lei_dist[_classe_do_aluno(a, 'leitura', escrita_por_aluno, leitura_por_aluno)] += 1

    def _ordenar(dist: dict[str, int], ordem_fixa: list[str]) -> list[dict]:
        chaves = [k for k in ordem_fixa if k in dist]
        chaves += sorted(
            (k for k in dist if k not in ordem_fixa and k != SEM_CLASSIFICACAO),
            key=lambda k: -dist[k],
        )
        if SEM_CLASSIFICACAO in dist:
            chaves.append(SEM_CLASSIFICACAO)
        return [{'classe': k, 'count': dist[k]} for k in chaves]

    return {
        'total_criancas': total,
        'escrita': _ordenar(esc_dist, ORDEM_ESCRITA),
        'leitura': _ordenar(lei_dist, []),
    }


# ---------------------------------------------------------------------------
# Orquestração final
# ---------------------------------------------------------------------------

def gerar_payload_coordenacao(escola_id, recorte) -> dict:
    """Agregados do painel da coordenação para uma escola e um recorte de tempo."""
    periodo = recorte
    ini, fim = _limites(periodo)
    hoje = timezone.localdate()

    registros = list(_registros_do_periodo(escola_id, ini, fim)) if ini and fim else []

    fim_efetivo = min(fim, hoje) if fim else hoje
    limite_recente = fim_efetivo - timedelta(days=JANELA_REGISTRO_RECENTE_DIAS)

    (
        planos_por_turma_campo, heatmap_campos, periodo_descricao, planos_sem_habilidade_por_turma,
    ) = _planos_por_turma_campo(escola_id, periodo)

    return {
        'versao_schema': CACHE_SCHEMA_VERSION,
        'escola_id': str(escola_id),
        'periodo_id': recorte.periodo_id if recorte else None,
        'periodo_descricao': recorte.descricao if recorte else periodo_descricao,
        'periodo_data_inicio': ini.isoformat() if ini else None,
        'periodo_data_fim': fim.isoformat() if fim else None,
        'periodo_em_curso': bool(ini and fim and ini <= hoje <= fim),
        'periodo_personalizado': bool(recorte and recorte.personalizado),
        'bncc_usage': _bncc_usage_da_janela(escola_id, registros),
        'bncc_usage_por_turma': _bncc_usage_por_turma(escola_id, registros),
        'criancas_com_registro_recente_15d': _criancas_com_registro_recente(registros, limite_recente),
        'criancas_com_evidencia_recente': _criancas_com_evidencia_recente(
            escola_id, limite_recente, fim_efetivo,
        ),
        'professor_mais_recente_por_crianca': _professor_mais_recente_por_crianca(registros),
        'indicadores': gerar_indicadores_bncc(escola_id, periodo),
        'planos_por_turma_campo': planos_por_turma_campo,
        'heatmap_campos': heatmap_campos,
        'planos_sem_habilidade_por_turma': planos_sem_habilidade_por_turma,
        'criancas_com_relatorio_finalizado': _criancas_com_relatorio_finalizado(escola_id, periodo),
        'ranking_professores': _ranking_professores(escola_id, periodo),
        'alfabetizacao': _alfabetizacao(escola_id, periodo),
    }


@transaction.atomic
def atualizar_cache_coordenacao(
    escola_id: str, data_referencia: date | None = None, janela_dias: int = JANELA_DIAS,
) -> CoordenacaoCache:
    """DESATIVADO — grava um snapshot em `CoordenacaoCache`.

    O painel calcula os agregados por período avaliativo a cada requisição
    (~70 ms), então nada no caminho de request chama isto. Mantida de
    propósito: os snapshots já gravados são o único histórico diário que
    existe. Sem poda de retenção (removida no legado; ver comentário
    original — apagava dados que eram o próprio motivo de manter a tabela).
    """
    if data_referencia is None:
        data_referencia = timezone.localdate() - timedelta(days=1)

    recorte = resolver_recorte(escola_id, data_referencia=data_referencia)
    payload = gerar_payload_coordenacao(escola_id, recorte)

    payload_vazio = (
        not payload['bncc_usage']
        and not payload['criancas_com_registro_recente_15d']
        and not payload['professor_mais_recente_por_crianca']
    )
    if payload_vazio:
        diag = diagnosticar_cache(escola_id, data_referencia, janela_dias)
        logger.warning(
            'CoordenacaoCache gerado VAZIO (escola=%s). Diagnostico: %s.',
            escola_id, diag,
        )
    else:
        logger.info(
            'CoordenacaoCache gerado para escola=%s data_ref=%s: bncc=%d criancas_recentes=%d professores=%d',
            escola_id, data_referencia.isoformat(),
            len(payload['bncc_usage']), len(payload['criancas_com_registro_recente_15d']),
            len(payload['professor_mais_recente_por_crianca']),
        )

    from api.models import Escola
    instituicao_id = Escola.objects.filter(id=escola_id).values_list('instituicao_id', flat=True).first()

    obj, _ = CoordenacaoCache.objects.update_or_create(
        escola_id=escola_id,
        data_referencia=data_referencia,
        defaults={
            'payload': payload,
            'janela_dias': janela_dias,
            'versao_schema': CACHE_SCHEMA_VERSION,
            'instituicao_id': instituicao_id,
        },
    )

    return obj