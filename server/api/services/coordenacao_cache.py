"""
Gera e persiste o snapshot D-1 dos agregados consumidos pela página de
coordenação (`CoordinatorHomePage.jsx`) e pela página de indicadores
(`IndicatorView.jsx`).

A query original (`apiClient.from('registros_observacao').select(...)` com 30
dias) chegava a ~850 KB por instituição. Este serviço pré-computa apenas os
agregados que a UI de fato consome e guarda em `CoordenacaoCache`.

Importante: o backend é *single-tenant por escola* — cada deploy tem o seu
próprio banco. Por isso a agregação **não filtra por `instituicao_id`**:
`criancas.instituicao_id` pode ser um UUID diferente do `NARA_INSTITUICAO_ID`
configurado no ambiente (que serve apenas de chave do cache). Todo registro
presente no banco pertence à escola servida por este backend.
"""

from __future__ import annotations

import logging
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from django.db import transaction
from django.db.models import Max, Min
from django.utils import timezone

from api.models import (
    Crianca,
    CoordenacaoCache,
    ObservacaoTranscricao,
    PerguntaBNCC,
    PeriodoAvaliativo,
    PlanejamentoHabilidade,
    PlanejamentoSemanal,
    ProducaoCrianca,
    ProducaoFoto,
    RegistroDesenho,
    RegistroEscrita,
    RegistroLeitura,
    RegistroObservacao,
    Relatorio,
    Turma,
    UsuarioTurma,
)

logger = logging.getLogger(__name__)


# v3: adiciona `planos_por_turma_campo`/`heatmap_campos`/`periodo_descricao`
#     (cobertura de planejamentos por campo BNCC por turma no período vigente).
# v4: adiciona `planos_sem_habilidade_por_turma` (planos do período sem nenhuma
#     habilidade BNCC vinculada — coluna "Sem habilidade vinculada" do heatmap).
# v5: adiciona `criancas_com_relatorio_finalizado` (ids das crianças com pelo
#     menos um relatório finalizado) — permite à coordenação parar de carregar
#     TODOS os relatórios no front (status por criança + contadores por turma).
# v6: adiciona `ranking_professores` (produção docente no período vigente:
#     registros, relatórios, planejamentos e portfólios por professor).
# v7: adiciona `alfabetizacao` (distribuição % das crianças por classe de
#     escrita e leitura no período vigente, com fatia "Sem classificação").
# v8: adiciona `bncc_usage_por_turma` (mesma janela do `bncc_usage` global, mas
#     quebrado por turma — alimenta o select de turma do "Mapa de utilização BNCC").
CACHE_SCHEMA_VERSION = '8'
JANELA_DIAS = 30
JANELA_REGISTRO_RECENTE_DIAS = 15
SEMANAS_ENGAJAMENTO = 4


def sem_acento_min(s: str | None) -> str:
    """Minúsculo, sem acento, sem espaços nas pontas — para casar texto livre."""
    s = (s or '').strip().lower()
    return ''.join(
        c for c in unicodedata.normalize('NFKD', s) if not unicodedata.combining(c)
    )


def _registros_do_periodo(data_inicio: date, data_fim: date):
    """Todos os registros do período avaliativo, no banco desta escola.

    NÃO filtra por `instituicao_id`: o banco é dedicado a uma escola, então
    todo `RegistroObservacao` pertence a ela. Filtrar por `NARA_INSTITUICAO_ID`
    (que não precisa casar com `criancas.instituicao_id`) zerava o resultado.
    """
    return RegistroObservacao.objects.filter(
        data_observacao__gte=data_inicio,
        data_observacao__lte=data_fim,
    ).values_list('crianca_id', 'professor_id', 'data_observacao', 'pergunta_id')


def diagnosticar_cache(
    data_referencia: date | None = None,
    janela_dias: int = JANELA_DIAS,
) -> dict[str, Any]:
    """Reúne contagens que explicam *por que* um payload sai vazio.

    Não computa o snapshot — apenas mede o universo de dados do banco (a
    escola) visível na janela. Usado pelo warning de payload vazio e pelo
    management command `refresh_coordenacao_cache`.
    """
    if data_referencia is None:
        data_referencia = timezone.localdate() - timedelta(days=1)
    data_inicio = data_referencia - timedelta(days=janela_dias)

    registros = RegistroObservacao.objects.all()
    extremos = registros.aggregate(
        min_d=Min('data_observacao'), max_d=Max('data_observacao')
    )
    n_janela = registros.filter(
        data_observacao__gte=data_inicio,
        data_observacao__lte=data_referencia,
    ).count()

    return {
        'data_referencia': data_referencia.isoformat(),
        'data_inicio_janela': data_inicio.isoformat(),
        'janela_dias': janela_dias,
        'total_criancas_banco': Crianca.objects.count(),
        'total_registros_banco': registros.count(),
        'registros_na_janela': n_janela,
        'data_observacao_min': extremos['min_d'].isoformat() if extremos['min_d'] else None,
        'data_observacao_max': extremos['max_d'].isoformat() if extremos['max_d'] else None,
    }


def _semana_inicio(d: date) -> date:
    """Segunda-feira da semana de `d` (weekStartsOn = Monday, igual ao front)."""
    return d - timedelta(days=d.weekday())


def _comparativo_periodos(
    recorte,
    total_habilidades: int,
    total_criancas: int,
) -> dict[str, Any]:
    """Resumo do recorte selecionado e do anterior (espelha IndicatorView).

    Busca os próprios registros: o scan principal de `gerar_indicadores_bncc` é
    limitado ao recorte, e aqui é preciso enxergar também o anterior.

    O "anterior" depende do tipo de recorte: para um período avaliativo é o
    período cadastrado que termina antes dele; para um intervalo escolhido à
    mão é o intervalo imediatamente anterior de mesma duração — assim a
    comparação continua sendo entre janelas do mesmo tamanho.
    """
    if not recorte:
        return {'periodoAtual': None, 'periodoAnterior': None}

    def resumo(p):
        if not p:
            return None
        ini, fim = p['data_inicio'], p['data_fim']
        habs: set[str] = set()
        profs: set[str] = set()
        crcs: set[str] = set()
        for crianca_id, professor_id, _data_obs, pergunta_id in _registros_do_periodo(ini, fim):
            if pergunta_id:
                habs.add(str(pergunta_id))
            if professor_id:
                profs.add(str(professor_id))
            if crianca_id:
                crcs.add(str(crianca_id))
        return {
            'id': str(p['id']) if p.get('id') else None,
            'descricao': p['descricao'],
            'data_inicio': ini.isoformat(),
            'data_fim': fim.isoformat(),
            'coberturaPercentual': round(len(habs) / total_habilidades * 100) if total_habilidades else 0,
            'professoresAtivos': len(profs),
            'criancasEmAlerta': max(0, total_criancas - len(crcs)),
        }

    atual = {
        'id': recorte.periodo_id,
        'descricao': recorte.descricao,
        'data_inicio': recorte.data_inicio,
        'data_fim': recorte.data_fim,
    }

    if recorte.personalizado:
        # Janela imediatamente anterior, de mesma duração.
        dias = (recorte.data_fim - recorte.data_inicio).days
        fim_ant = recorte.data_inicio - timedelta(days=1)
        ini_ant = fim_ant - timedelta(days=dias)
        anterior = {
            'id': None,
            'descricao': f"{ini_ant.strftime('%d/%m/%Y')} – {fim_ant.strftime('%d/%m/%Y')}",
            'data_inicio': ini_ant,
            'data_fim': fim_ant,
        }
    else:
        anterior = None
        for p in PeriodoAvaliativo.objects.filter(
            data_fim__lt=recorte.data_inicio
        ).order_by('-data_fim').values('id', 'descricao', 'data_inicio', 'data_fim')[:1]:
            anterior = p

    return {'periodoAtual': resumo(atual), 'periodoAnterior': resumo(anterior)}


# ---------------------------------------------------------------------------
# Tabelas de referência (catálogo BNCC + mapa criança→turma).
# São tabelas pequenas; cada agregado abaixo consulta esses mapas em memória.
# ---------------------------------------------------------------------------

def _carregar_referencias_perguntas() -> tuple[dict[str, str], int, dict[str, int]]:
    """Catálogo BNCC: campo de cada pergunta + totais por campo e no geral.

    Retorna `(campo_por_pergunta, total_habilidades, total_por_campo)`. Perguntas
    sem `campo_experiencia` caem no bucket 'Outros' (mesmo critério da UI).
    """
    perguntas = list(PerguntaBNCC.objects.values_list('id', 'campo_experiencia'))
    campo_por_pergunta = {str(pid): (campo or 'Outros') for pid, campo in perguntas}
    total_por_campo: dict[str, int] = defaultdict(int)
    for campo in campo_por_pergunta.values():
        total_por_campo[campo] += 1
    return campo_por_pergunta, len(perguntas), total_por_campo


def _carregar_crianca_turma() -> tuple[dict[str, str | None], int]:
    """Mapa `crianca_id -> turma_id` (string ou None) + total de crianças."""
    crianca_turma = {
        str(cid): (str(tid) if tid else None)
        for cid, tid in Crianca.objects.values_list('id', 'turma_id')
    }
    return crianca_turma, len(crianca_turma)


def _carregar_faixas_das_turmas() -> tuple[dict[str, set[str]], dict[str, int]]:
    """Base para o denominador da cobertura BNCC por turma.

    Retorna:
      - `perguntas_da_turma`: `turma_id -> {pergunta_id}` da faixa etária dela;
      - `criancas_por_turma`: `turma_id -> nº de crianças`.

    O produto dos dois é o total de células "criança × habilidade" possíveis
    naquela turma — o denominador. Ele muda por turma porque muda tanto o nº de
    crianças quanto o catálogo da faixa (13 na Educação Infantil, 20 no 1º ano).

    O casamento de faixa é normalizado (sem acento, minúsculo, sem espaços
    extras) porque `turmas.faixa_etaria` e `perguntas_bncc.faixa_etaria` são
    texto livre e divergem em acentuação na base ("Nivel 2" x "Nível 2").
    """
    def _chave(s):
        return sem_acento_min(s)

    perguntas_por_faixa: dict[str, set[str]] = defaultdict(set)
    for pid, faixa in PerguntaBNCC.objects.values_list('id', 'faixa_etaria'):
        perguntas_por_faixa[_chave(faixa)].add(str(pid))

    perguntas_da_turma: dict[str, set[str]] = {}
    for tid, faixa in Turma.objects.values_list('id', 'faixa_etaria'):
        perguntas_da_turma[str(tid)] = perguntas_por_faixa.get(_chave(faixa), set())

    criancas_por_turma: dict[str, int] = defaultdict(int)
    for (tid,) in Crianca.objects.exclude(turma_id=None).values_list('turma_id'):
        criancas_por_turma[str(tid)] += 1

    return perguntas_da_turma, criancas_por_turma


# ---------------------------------------------------------------------------
# Agregados de `gerar_indicadores_bncc` — um helper por "parâmetro" do payload.
# Todos recebem `registros_list` (lista já materializada de tuplas
# (crianca_id, professor_id, data_observacao, pergunta_id)) e fazem uma
# passada em memória. A passada é O(n) e barata frente ao scan no banco; manter
# uma função por métrica deixa claro ONDE mexer p/ alterar ou somar um cálculo.
# ---------------------------------------------------------------------------

def _cobertura_habilidades(
    registros_list: list,
    campo_por_pergunta: dict[str, str],
) -> tuple[set[str], dict[str, set[str]]]:
    """Cobertura BNCC da escola: quais habilidades foram usadas, agrupadas por campo.

    Retorna `(habilidades_usadas, usadas_por_campo)` — sets de `pergunta_id`.
    Alimenta `habilidades_usadas`, `campos_ativos`, `cobertura_por_campo` e
    `habilidades_pendentes_ids`.
    """
    habilidades_usadas: set[str] = set()
    usadas_por_campo: dict[str, set[str]] = defaultdict(set)
    for _crianca_id, _professor_id, _data_obs, pergunta_id in registros_list:
        if pergunta_id:
            pid = str(pergunta_id)
            habilidades_usadas.add(pid)
            usadas_por_campo[campo_por_pergunta.get(pid, 'Outros')].add(pid)
    return habilidades_usadas, usadas_por_campo


def _cobertura_por_turma(
    registros_list: list,
    crianca_turma: dict[str, str | None],
    campo_por_pergunta: dict[str, str],
    perguntas_da_turma: dict[str, set[str]] | None = None,
) -> tuple[dict[str, int], dict[str, set[str]], dict[str, dict[str, int]], dict[str, set[tuple]]]:
    """Atividade por turma: registros, habilidades, contagem por campo e cobertura.

    Retorna `(por_turma_registros, por_turma_habs, por_turma_campo, por_turma_pares)`.
    Registros de crianças sem turma são ignorados em todos os mapas.

    `por_turma_pares` é a métrica de COBERTURA: o conjunto de pares
    `(crianca_id, pergunta_id)` distintos. Se 6 crianças foram marcadas numa
    mesma habilidade, contam 6 — enquanto `por_turma_habs` contaria 1. Marcar a
    mesma criança 3× na mesma habilidade continua contando 1, porque a pergunta
    é "esta criança foi observada nesta habilidade?", não "quantas vezes".

    Isso responde uma pergunta que `por_turma_habs` não respondia: as três
    turmas de 1º ano mostravam "20 de 20 habilidades" e pareciam idênticas,
    quando cobriam 339, 368 e 339 pares de um máximo diferente cada uma.

    Com `perguntas_da_turma`, os pares ficam restritos às habilidades da faixa
    etária da turma. Sem esse filtro, criança que mudou de turma leva junto as
    marcações da faixa anterior (`RegistroObservacao` não guarda turma, só
    `crianca_id`), e a cobertura passava de 100% — na base atual, uma turma de
    Nível 2 aparecia com 45 habilidades num catálogo de 13.
    """
    por_turma_registros: dict[str, int] = defaultdict(int)
    por_turma_habs: dict[str, set[str]] = defaultdict(set)
    por_turma_campo: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    por_turma_pares: dict[str, set[tuple]] = defaultdict(set)

    for crianca_id, _professor_id, _data_obs, pergunta_id in registros_list:
        turma = crianca_turma.get(str(crianca_id))
        if not turma:
            continue
        por_turma_registros[turma] += 1
        if not pergunta_id:
            continue
        pid = str(pergunta_id)
        por_turma_habs[turma].add(pid)
        por_turma_campo[turma][campo_por_pergunta.get(pid, 'Outros')] += 1

        # Cobertura: só habilidades da faixa da turma (quando conhecida).
        da_faixa = perguntas_da_turma.get(turma) if perguntas_da_turma else None
        if da_faixa is None or pid in da_faixa:
            por_turma_pares[turma].add((str(crianca_id), pid))

    return por_turma_registros, por_turma_habs, por_turma_campo, por_turma_pares


def _engajamento_semanal(registros_list: list, data_referencia: date) -> list[list]:
    """Nº de registros em cada uma das últimas `SEMANAS_ENGAJAMENTO` semanas (Mon–Sun).

    Retorna uma lista de `[inicio, fim, contagem]` em ordem cronológica,
    terminando na semana de `data_referencia`.
    """
    semanas: list[list] = []
    for i in range(SEMANAS_ENGAJAMENTO - 1, -1, -1):
        ini = _semana_inicio(data_referencia) - timedelta(weeks=i)
        semanas.append([ini, ini + timedelta(days=6), 0])
    for _crianca_id, _professor_id, data_obs, _pergunta_id in registros_list:
        if not data_obs:
            continue
        for semana in semanas:
            if semana[0] <= data_obs <= semana[1]:
                semana[2] += 1
                break
    return semanas


def _formatar_cobertura_por_campo(
    usadas_por_campo: dict[str, set[str]],
    total_por_campo: dict[str, int],
) -> list[dict[str, Any]]:
    """Monta a lista `cobertura_por_campo` (% de habilidades usadas por campo), desc."""
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


def gerar_indicadores_bncc(periodo, data_referencia: date | None = None) -> dict[str, Any]:
    """Agregados PESADOS de `IndicatorView` (página Indicadores), no período.

    Esses dados eram montados no navegador a partir do *fetch completo* de
    `registros_observacao` da instituição — a maior carga on-the-fly do
    coordenador. Aqui fazemos um único scan no servidor e devolvemos só os
    agregados que a UI consome. Como o banco é single-tenant por escola, não
    filtramos por instituição.

    O scan é **limitado ao período avaliativo**. Antes varria a tabela inteira
    ("cobertura é cumulativa"), o que respondia "quanto a escola já cobriu desde
    sempre" — número que só crescia e que não permitia comparar bimestres. Agora
    responde "quanto foi coberto NESTE período", que é o recorte que a
    coordenação escolhe na tela. A comparação com o período anterior continua
    disponível em `comparativo_periodos`.

    Esta função é só a ORQUESTRADORA: carrega as tabelas de referência, faz o
    scan e delega cada métrica a um helper `_...` acima. Para alterar o cálculo
    de um parâmetro, edite o helper correspondente; para adicionar um parâmetro
    novo, escreva um helper que receba `registros_list` e some a chave ao dict.
    """
    campo_por_pergunta, total_habilidades, total_por_campo = _carregar_referencias_perguntas()
    crianca_turma, total_criancas = _carregar_crianca_turma()
    perguntas_da_turma, criancas_por_turma = _carregar_faixas_das_turmas()

    ini, fim = _limites(periodo)
    if ini and fim:
        registros_list = list(_registros_do_periodo(ini, fim))
    else:
        # Sem período avaliativo cadastrado, não há recorte possível: mantém o
        # comportamento antigo (tudo) para a tela não ficar vazia.
        registros_list = list(
            RegistroObservacao.objects.values_list(
                'crianca_id', 'professor_id', 'data_observacao', 'pergunta_id'
            )
        )

    # Âncora das últimas 4 semanas: o fim do período, ou hoje se ele ainda corre.
    if data_referencia is None:
        hoje = timezone.localdate()
        data_referencia = min(fim, hoje) if fim else hoje

    habilidades_usadas, usadas_por_campo = _cobertura_habilidades(
        registros_list, campo_por_pergunta
    )
    por_turma_registros, por_turma_habs, por_turma_campo, por_turma_pares = _cobertura_por_turma(
        registros_list, crianca_turma, campo_por_pergunta, perguntas_da_turma
    )
    semanas = _engajamento_semanal(registros_list, data_referencia)

    return {
        'total_habilidades': total_habilidades,
        'habilidades_usadas': len(habilidades_usadas),
        'campos_ativos': sum(1 for s in usadas_por_campo.values() if s),
        'cobertura_por_campo': _formatar_cobertura_por_campo(usadas_por_campo, total_por_campo),
        'habilidades_pendentes_ids': sorted(
            pid for pid in campo_por_pergunta if pid not in habilidades_usadas
        ),
        'por_turma': {
            turma: {
                'registros': por_turma_registros.get(turma, 0),
                # Mantido: nº de habilidades distintas tocadas (sem filtro de faixa).
                'habilidades_usadas': len(por_turma_habs.get(turma, set())),
                # Cobertura: pares criança×habilidade observados, e o total de
                # células possíveis (crianças da turma × habilidades da faixa).
                'cobertura_pares': len(por_turma_pares.get(turma, set())),
                'cobertura_total': (
                    criancas_por_turma.get(turma, 0) * len(perguntas_da_turma.get(turma, ()))
                ),
            }
            for turma in set(por_turma_registros) | set(por_turma_habs) | set(criancas_por_turma)
        },
        'por_turma_campo': {t: dict(c) for t, c in por_turma_campo.items()},
        'semanal_4s': [
            {'semana_inicio': ini.isoformat(), 'registros': n}
            for ini, _fim, n in semanas
        ],
        'comparativo_periodos': _comparativo_periodos(
            periodo, total_habilidades, total_criancas
        ),
    }


# ---------------------------------------------------------------------------
# Agregados de `gerar_payload_coordenacao` — operam sobre os registros DA JANELA
# (`_registros_da_janela`), não sobre o banco inteiro como os indicadores acima.
# ---------------------------------------------------------------------------

def _bncc_usage_da_janela(registros: list) -> list[dict[str, Any]]:
    """Contagem de registros por `campo_experiencia` na janela (campo já resolvido).

    Conta REGISTROS (não habilidades distintas): soma quantas observações caíram
    em cada campo. Faz uma query extra só nas perguntas presentes na janela.
    """
    contagem_por_pergunta: dict[str, int] = defaultdict(int)
    for _crianca_id, _professor_id, _data_obs, pergunta_id in registros:
        if pergunta_id:
            contagem_por_pergunta[str(pergunta_id)] += 1
    if not contagem_por_pergunta:
        return []

    campos_por_pergunta = {
        str(pid): campo
        for pid, campo in PerguntaBNCC.objects.filter(
            id__in=list(contagem_por_pergunta.keys())
        ).values_list('id', 'campo_experiencia')
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


def _bncc_usage_por_turma(registros: list) -> dict[str, list[dict[str, Any]]]:
    """Igual ao `_bncc_usage_da_janela`, mas quebrado por turma da criança.

    Sobre a MESMA janela do `bncc_usage` global, agrupa por `turma_id ->
    campo_experiencia -> count`, mapeando a criança à sua turma. Alimenta o
    select de turma do card "Mapa de utilização da BNCC" — somar todas as turmas
    reproduz o global (descontadas as crianças sem turma).
    Retorna `{ turma_id: [{campo_experiencia, count} ordenado desc] }`.
    """
    crianca_turma, _ = _carregar_crianca_turma()

    # Conta (turma, pergunta) na janela; resolve o campo só das perguntas presentes.
    contagem: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    perguntas_presentes: set[str] = set()
    for crianca_id, _professor_id, _data_obs, pergunta_id in registros:
        if not pergunta_id:
            continue
        turma = crianca_turma.get(str(crianca_id))
        if not turma:
            continue
        pid = str(pergunta_id)
        contagem[turma][pid] += 1
        perguntas_presentes.add(pid)

    if not perguntas_presentes:
        return {}

    campos_por_pergunta = {
        str(pid): campo
        for pid, campo in PerguntaBNCC.objects.filter(
            id__in=list(perguntas_presentes)
        ).values_list('id', 'campo_experiencia')
        if campo
    }

    saida: dict[str, list[dict[str, Any]]] = {}
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


def _criancas_com_registro_recente(registros: list, limite_recente: date) -> list[str]:
    """IDs (ordenados) das crianças com ao menos um registro em/após `limite_recente`."""
    recentes: set[str] = set()
    for crianca_id, _professor_id, data_obs, _pergunta_id in registros:
        if data_obs >= limite_recente:
            recentes.add(str(crianca_id))
    return sorted(recentes)


def _criancas_com_evidencia_recente(data_inicio: date, data_fim: date) -> list[str]:
    """IDs das crianças com QUALQUER registro pedagógico na janela.

    O alerta de "sem registro recente" olhava só `RegistroObservacao` (a
    marcação de chip do Registro Guiado). Uma criança documentada por relato de
    áudio, análise de escrita/desenho ou portfólio era contada como esquecida —
    medido numa janela real da base, 6 de 8 crianças alertadas tinham relato de
    áudio no mesmo período.

    Fontes consideradas (todas com data própria):
      - RegistroObservacao  → crianca_id direto
      - ObservacaoTranscricao → crianca_id quando existe, senão aluno_nome
      - RegistroEscrita / RegistroDesenho → só por nome (não têm crianca_id)
      - ProducaoCrianca → crianca_id direto

    O casamento por nome é normalizado (`_norm_nome`) e restrito a nomes de
    crianças cadastradas; nomes que não batem são ignorados em silêncio, como
    no resto do serviço.
    """
    criancas = list(Crianca.objects.values('id', 'nome_completo'))
    id_por_nome = {_norm_nome(c['nome_completo']): str(c['id']) for c in criancas}
    ids_validos = {str(c['id']) for c in criancas}

    com_evidencia: set[str] = set()

    def _por_id(valores):
        for cid in valores:
            if cid and str(cid) in ids_validos:
                com_evidencia.add(str(cid))

    def _por_nome(nomes):
        for nome in nomes:
            cid = id_por_nome.get(_norm_nome(nome))
            if cid:
                com_evidencia.add(cid)

    _por_id(
        RegistroObservacao.objects.filter(
            data_observacao__gte=data_inicio, data_observacao__lte=data_fim
        ).values_list('crianca_id', flat=True)
    )

    transcricoes = ObservacaoTranscricao.objects.filter(
        data_observacao__gte=data_inicio, data_observacao__lte=data_fim
    ).values_list('crianca_id', 'aluno_nome')
    _por_id(cid for cid, _nome in transcricoes if cid)
    _por_nome(nome for cid, nome in transcricoes if not cid)

    for modelo in (RegistroEscrita, RegistroDesenho):
        _por_nome(
            modelo.objects.filter(
                data_criacao__date__gte=data_inicio, data_criacao__date__lte=data_fim
            ).values_list('nome_aluno', flat=True)
        )

    _por_id(
        ProducaoCrianca.objects.filter(
            data_registro__gte=data_inicio, data_registro__lte=data_fim
        ).values_list('crianca_id', flat=True)
    )

    return sorted(com_evidencia)


def _professor_mais_recente_por_crianca(registros: list) -> dict[str, dict[str, Any]]:
    """Para cada criança, o professor e a data do registro mais recente na janela."""
    mais_recente: dict[str, dict[str, Any]] = {}
    for crianca_id, professor_id, data_obs, _pergunta_id in registros:
        cid = str(crianca_id)
        atual = mais_recente.get(cid)
        if atual is None or data_obs > date.fromisoformat(atual['data_observacao']):
            mais_recente[cid] = {
                'professor_id': str(professor_id) if professor_id else None,
                'data_observacao': data_obs.isoformat(),
            }
    return mais_recente


def _periodo_avaliativo_vigente(data_referencia: date):
    """Período avaliativo que contém `data_referencia`.

    Fallback: o período mais recente que já começou (caso `data_referencia` caia
    fora de qualquer intervalo configurado). Single-tenant: não filtra por
    instituição (o banco é de uma escola só).
    """
    qs = PeriodoAvaliativo.objects.all()
    vigente = (
        qs.filter(data_inicio__lte=data_referencia, data_fim__gte=data_referencia)
        .order_by('-data_inicio')
        .first()
    )
    if vigente:
        return vigente
    return qs.filter(data_inicio__lte=data_referencia).order_by('-data_inicio').first()


@dataclass(frozen=True)
class Recorte:
    """A janela de tempo que dirige TODO o painel da coordenação.

    Pode ser um período avaliativo cadastrado (`periodo_id` preenchido) ou um
    intervalo de datas escolhido à mão na tela. O resto do serviço só enxerga
    `data_inicio`/`data_fim`, então os dois casos passam pelo mesmo caminho.
    """
    data_inicio: date
    data_fim: date
    descricao: str
    periodo_id: str | None = None
    personalizado: bool = False


class RecorteInvalido(ValueError):
    """Intervalo pedido pelo usuário que não dá para atender."""


# Teto do intervalo à mão. Existe porque o custo do painel escala com o volume
# de registros DENTRO da janela: foi por limitar a janela que o snapshot
# pré-computado pôde sair. Um ano cobre qualquer pergunta pedagógica real
# ("o ano letivo inteiro") sem reabrir a porta para a varredura sem fim.
MAX_DIAS_RECORTE = 366


def _recorte_de_periodo(periodo) -> Recorte | None:
    if not periodo:
        return None
    return Recorte(
        data_inicio=periodo.data_inicio,
        data_fim=periodo.data_fim,
        descricao=periodo.descricao,
        periodo_id=str(periodo.id),
    )


def resolver_recorte(
    periodo_id=None,
    data_inicio: date | None = None,
    data_fim: date | None = None,
    data_referencia: date | None = None,
) -> Recorte | None:
    """A janela que a tela pediu, em ordem de precedência.

    1. `data_inicio`+`data_fim` → intervalo personalizado;
    2. `periodo_id` → aquele período avaliativo;
    3. nada → o período que contém `data_referencia` (default: hoje).

    Levanta `RecorteInvalido` para intervalo malformado e
    `PeriodoAvaliativo.DoesNotExist` para id inexistente, para a view distinguir
    400 de 404 em vez de silenciosamente mostrar outra janela.
    """
    if data_inicio or data_fim:
        if not (data_inicio and data_fim):
            raise RecorteInvalido('Informe data_inicio e data_fim juntos.')
        if data_inicio > data_fim:
            raise RecorteInvalido('data_inicio não pode ser depois de data_fim.')
        dias = (data_fim - data_inicio).days + 1
        if dias > MAX_DIAS_RECORTE:
            raise RecorteInvalido(
                f'Intervalo de {dias} dias excede o máximo de {MAX_DIAS_RECORTE}.'
            )
        return Recorte(
            data_inicio=data_inicio,
            data_fim=data_fim,
            descricao=f"{data_inicio.strftime('%d/%m/%Y')} – {data_fim.strftime('%d/%m/%Y')}",
            personalizado=True,
        )

    if periodo_id:
        return _recorte_de_periodo(PeriodoAvaliativo.objects.get(id=periodo_id))

    if data_referencia is None:
        data_referencia = timezone.localdate()
    return _recorte_de_periodo(_periodo_avaliativo_vigente(data_referencia))


def _limites(recorte) -> tuple[date | None, date | None]:
    """`(data_inicio, data_fim)` do recorte, ou `(None, None)` se não houver."""
    if not recorte:
        return None, None
    return recorte.data_inicio, recorte.data_fim


def _planos_por_turma_campo(periodo):
    """Cobertura de planejamentos por campo BNCC por turma, no período selecionado.

    Conta **planos distintos** (`PlanejamentoSemanal`): um plano conta 1× para um
    campo se qualquer habilidade de qualquer um dos seus dias pertence àquele
    campo. Alimenta o heatmap "Cobertura BNCC × Turmas" da tela de Planejamentos.

    Retorna `(por_turma_campo, campos_ordenados, periodo_descricao, sem_habilidade)`:
      - `por_turma_campo`: `{ turma_id: { campo: nº de planos } }`
      - `campos_ordenados`: campos presentes, ordenados por nº total de planos desc
      - `periodo_descricao`: descrição do período avaliativo usado (ou None)
      - `sem_habilidade`: `{ turma_id: nº de planos sem NENHUMA habilidade BNCC }`
    """
    if periodo is None:
        return {}, [], None, {}

    # Todos os planos (PlanejamentoSemanal) do período, por turma — base para
    # contar os que ficaram SEM habilidade BNCC vinculada.
    planos_do_periodo = list(
        PlanejamentoSemanal.objects.filter(
            semana_inicio__gte=periodo.data_inicio,
            semana_inicio__lte=periodo.data_fim,
        ).values_list('id', 'turma_id')
    )

    # `HabilidadeBNCC` agrupa por `componente_curricular` (ex.: "Língua
    # Portuguesa", "Matemática") — não tem `campo_experiencia` (esse campo vive
    # em `PerguntaBNCC`). Para esta escola, o componente curricular é o mesmo
    # agrupamento por matéria que o `bncc_usage`/`por_turma_campo` dos registros
    # exibe, então o heatmap de planos fica consistente com as demais telas.
    linhas = PlanejamentoHabilidade.objects.filter(
        planejamento_diario__planejamento_semanal__semana_inicio__gte=periodo.data_inicio,
        planejamento_diario__planejamento_semanal__semana_inicio__lte=periodo.data_fim,
    ).values_list(
        'planejamento_diario__planejamento_semanal__turma_id',
        'planejamento_diario__planejamento_semanal_id',
        'habilidade_bncc__componente_curricular',
    )

    # (turma_id, campo) -> conjunto de planos distintos; e o conjunto de planos
    # que têm ALGUMA habilidade vinculada (independente do componente).
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

    campos_ordenados = [
        campo for campo, _ in sorted(total_por_campo.items(), key=lambda kv: -kv[1])
    ]
    return dict(por_turma_campo), campos_ordenados, periodo.descricao, dict(sem_habilidade)


def _criancas_com_relatorio_finalizado(periodo) -> list[str]:
    """IDs (ordenados) das crianças com relatório FINALIZADO no período.

    Finalizado = `conteudo` com mais de 50 chars (mesmo critério das listas),
    medido via LENGTH(SUBSTRING(conteudo,1,51)) para não detoastar a coluna.
    Alimenta os contadores/status de relatório por criança/turma na coordenação,
    para o front não precisar carregar todos os relatórios.

    Recortado pelo período avaliativo: antes contava desde sempre, e a
    coordenação via "relatórios finalizados" somando anos anteriores.
    """
    from django.db.models.functions import Length, Substr

    ini, fim = _limites(periodo)
    qs = Relatorio.objects.all()
    if ini and fim:
        qs = qs.filter(data_criacao__date__gte=ini, data_criacao__date__lte=fim)

    ids = (
        qs.annotate(_cl=Length(Substr('conteudo', 1, 51)))
        .filter(_cl__gt=50)
        .values_list('id_crianca', flat=True)
        .distinct()
    )
    return sorted({str(i) for i in ids})


def _ranking_professores(periodo) -> list[dict[str, Any]]:
    """Produção docente por professor no período avaliativo selecionado.

    Métricas por professor: `registros`, `relatorios`, `planejamentos`,
    `portfolios` e o `total` (soma). "Relatórios gerados pela professora" =
    relatórios das crianças das turmas da professora — `Relatorio` não tem campo
    de autor, então usamos o vínculo `UsuarioTurma` (criança → turma → professor).
    Sem `PeriodoAvaliativo` configurado, conta tudo (sem filtro de data).
    Retorna lista ordenada por `total` desc (só ids; o nome é resolvido no front).
    """
    from django.db.models import Count

    ini, fim = _limites(periodo)

    contagens: dict[str, dict[str, int]] = defaultdict(
        lambda: {'registros': 0, 'relatorios': 0, 'planejamentos': 0, 'portfolios': 0}
    )

    def _credita(pid, chave, n=1):
        if pid:
            contagens[str(pid)][chave] += n

    # Registros
    regs = RegistroObservacao.objects.all()
    if ini and fim:
        regs = regs.filter(data_observacao__gte=ini, data_observacao__lte=fim)
    for row in regs.values('professor_id').annotate(n=Count('id')):
        _credita(row['professor_id'], 'registros', row['n'])

    # Planejamentos
    plans = PlanejamentoSemanal.objects.all()
    if ini and fim:
        plans = plans.filter(semana_inicio__gte=ini, semana_inicio__lte=fim)
    for row in plans.values('professora_id').annotate(n=Count('id')):
        _credita(row['professora_id'], 'planejamentos', row['n'])

    # Portfólios (fotos + produções)
    pf = ProducaoFoto.objects.all()
    if ini and fim:
        pf = pf.filter(data_registro__gte=ini, data_registro__lte=fim)
    for row in pf.values('professora_id').annotate(n=Count('id')):
        _credita(row['professora_id'], 'portfolios', row['n'])
    pc = ProducaoCrianca.objects.all()
    if ini and fim:
        pc = pc.filter(data_registro__gte=ini, data_registro__lte=fim)
    for row in pc.values('professor_id').annotate(n=Count('id')):
        _credita(row['professor_id'], 'portfolios', row['n'])

    # Relatórios: das crianças das turmas da professora (via UsuarioTurma).
    crianca_turma = {
        str(cid): (str(tid) if tid else None)
        for cid, tid in Crianca.objects.values_list('id', 'turma_id')
    }
    turma_profs: dict[str, list[str]] = defaultdict(list)
    for tid, uid in UsuarioTurma.objects.values_list('turma_id', 'usuario_id'):
        turma_profs[str(tid)].append(str(uid))
    rels = Relatorio.objects.all()
    if ini and fim:
        rels = rels.filter(data_criacao__date__gte=ini, data_criacao__date__lte=fim)
    for (crianca_id,) in rels.values_list('id_crianca'):
        turma = crianca_turma.get(str(crianca_id))
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


# Fonte única da progressão (Ferreiro) — ver api/services/fases_producao.py.
from api.services.fases_producao import FASES_ESCRITA as ORDEM_ESCRITA  # noqa: E402

SEM_CLASSIFICACAO = 'Sem classificação'


def _norm_nome(s: str | None) -> str:
    """Normaliza nome (minúsculo, sem acentos) para casar escrita↔criança."""
    return sem_acento_min(s)


def _mapas_alfabetizacao(periodo):
    """Base compartilhada entre a distribuição (card) e a lista por classe (drill-down).

    Para o período avaliativo selecionado, retorna
    `(criancas, escrita_por_aluno, leitura_por_crianca, periodo)`:
      - `criancas`: lista de dicts `{id, nome_completo, turma_id}` das crianças ativas.
      - `escrita_por_aluno`: `{(nome_norm, str(turma_id)): etapa_ia}` — último registro do
        período (casado por nome+turma, pois `RegistroEscrita` não tem `crianca_id`).
      - `leitura_por_crianca`: `{str(crianca_id): classe_escolhida}` — última classe
        confirmada do período.
    A regra de "última classificação por criança no período" mora aqui, então o card e o
    drill-down nunca divergem.
    """
    ini, fim = _limites(periodo)

    criancas = list(
        Crianca.objects.exclude(status_vinculo='inativo')
        .values('id', 'nome_completo', 'turma_id')
    )

    # Escrita: último etapa_ia por (nome_norm, turma) no período (ordem asc → o último vence).
    esc_qs = RegistroEscrita.objects.all()
    if ini and fim:
        esc_qs = esc_qs.filter(data_criacao__date__gte=ini, data_criacao__date__lte=fim)
    escrita_por_aluno: dict[tuple[str, str], str] = {}
    for nome_aluno, turma_id, etapa in esc_qs.order_by('data_criacao').values_list(
        'nome_aluno', 'turma_id', 'etapa_ia'
    ):
        if etapa:
            escrita_por_aluno[(_norm_nome(nome_aluno), str(turma_id))] = etapa

    # Leitura: última classe_escolhida confirmada por criança no período.
    lei_qs = RegistroLeitura.objects.filter(status='confirmado').exclude(classe_escolhida='')
    if ini and fim:
        lei_qs = lei_qs.filter(data_criacao__date__gte=ini, data_criacao__date__lte=fim)
    leitura_por_crianca: dict[str, str] = {}
    for crianca_id, classe in lei_qs.order_by('data_criacao').values_list(
        'crianca_id', 'classe_escolhida'
    ):
        if classe:
            leitura_por_crianca[str(crianca_id)] = classe

    return criancas, escrita_por_aluno, leitura_por_crianca, periodo


def _classe_da_crianca(c, modalidade, escrita_por_aluno, leitura_por_crianca) -> str:
    """Classe de alfabetização de uma criança numa modalidade ('escrita'|'leitura')."""
    if modalidade == 'escrita':
        chave = (_norm_nome(c['nome_completo']), str(c['turma_id']) if c['turma_id'] else '')
        return escrita_por_aluno.get(chave) or SEM_CLASSIFICACAO
    return leitura_por_crianca.get(str(c['id'])) or SEM_CLASSIFICACAO


def criancas_por_classe_alfabetizacao(
    periodo, modalidade: str, classe: str, turma_id: str | None = None
) -> list[dict[str, Any]]:
    """Lista (ordenada por nome) das crianças cuja classificação no período é `classe`.

    Usa a mesma regra de "última classificação por criança no período" que alimenta o card.
    Inclui o bucket "Sem classificação". A paginação fica a cargo do chamador (view).
    """
    criancas, escrita_por_aluno, leitura_por_crianca, _ = _mapas_alfabetizacao(periodo)
    res: list[dict[str, Any]] = []
    for c in criancas:
        if turma_id and str(c['turma_id']) != str(turma_id):
            continue
        if _classe_da_crianca(c, modalidade, escrita_por_aluno, leitura_por_crianca) == classe:
            res.append({
                'crianca_id': str(c['id']),
                'nome': c['nome_completo'],
                'turma_id': str(c['turma_id']) if c['turma_id'] else None,
            })
    res.sort(key=lambda x: (x['nome'] or '').lower())
    return res


def _alfabetizacao(periodo) -> dict[str, Any]:
    """Distribuição das crianças por classe de ESCRITA e LEITURA no período selecionado.

    Para cada criança ativa, pega a classificação do **último registro do
    período avaliativo** (ver `_mapas_alfabetizacao`). Crianças sem registro no
    período entram em "Sem classificação". Denominador = todas as crianças ativas. Retorna
    `{ total_criancas, escrita: [{classe,count}], leitura: [...] }` — a % é calculada no front.
    """
    criancas, escrita_por_aluno, leitura_por_crianca, _ = _mapas_alfabetizacao(periodo)
    total = len(criancas)

    esc_dist: dict[str, int] = defaultdict(int)
    lei_dist: dict[str, int] = defaultdict(int)
    for c in criancas:
        esc_dist[_classe_da_crianca(c, 'escrita', escrita_por_aluno, leitura_por_crianca)] += 1
        lei_dist[_classe_da_crianca(c, 'leitura', escrita_por_aluno, leitura_por_crianca)] += 1

    def _ordenar(dist: dict[str, int], ordem_fixa: list[str]) -> list[dict[str, Any]]:
        # Ordem fixa primeiro (escrita), depois desconhecidas por frequência, "Sem" por último.
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


def gerar_payload_coordenacao(instituicao_id: str, recorte) -> dict[str, Any]:
    """Agregados do painel da coordenação para um recorte de tempo.

    `instituicao_id` é usado apenas como chave/echo (o frontend lê por ele). A
    agregação cobre todo o banco da escola.

    TODO o payload é limitado ao `recorte` — um período avaliativo ou um
    intervalo de datas escolhido na tela. É isso que dispensou o snapshot
    pré-computado: com a janela limitada, o custo é proporcional à atividade
    dentro dela e não cresce com a história acumulada da escola.

    Orquestradora: busca os registros do recorte uma vez e delega cada chave a
    um helper `_...` acima. Para mexer no cálculo de um parâmetro, edite o
    helper correspondente; para adicionar um, escreva um helper sobre
    `registros` e some a chave ao dict.
    """
    periodo = recorte  # os helpers só enxergam data_inicio/data_fim/descricao
    ini, fim = _limites(periodo)
    hoje = timezone.localdate()

    if ini and fim:
        registros = list(_registros_do_periodo(ini, fim))
    else:
        registros = []

    # "Sem registro recente" é sempre relativo ao fim do recorte: no período
    # corrente isso é "há 15 dias"; num período passado, os últimos 15 dias
    # daquele bimestre.
    fim_efetivo = min(fim, hoje) if fim else hoje
    limite_recente = fim_efetivo - timedelta(days=JANELA_REGISTRO_RECENTE_DIAS)

    (
        planos_por_turma_campo,
        heatmap_campos,
        periodo_descricao,
        planos_sem_habilidade_por_turma,
    ) = _planos_por_turma_campo(periodo)

    return {
        'versao_schema': CACHE_SCHEMA_VERSION,
        'instituicao_id': str(instituicao_id),
        # Identificação do recorte, para o front rotular os cards.
        'periodo_id': recorte.periodo_id if recorte else None,
        'periodo_descricao': recorte.descricao if recorte else periodo_descricao,
        'periodo_data_inicio': ini.isoformat() if ini else None,
        'periodo_data_fim': fim.isoformat() if fim else None,
        'periodo_em_curso': bool(ini and fim and ini <= hoje <= fim),
        'periodo_personalizado': bool(recorte and recorte.personalizado),
        'bncc_usage': _bncc_usage_da_janela(registros),
        'bncc_usage_por_turma': _bncc_usage_por_turma(registros),
        # Mantido para compatibilidade: só marcações BNCC, como antes.
        'criancas_com_registro_recente_15d': _criancas_com_registro_recente(
            registros, limite_recente
        ),
        # É esta que alimenta o alerta — considera todas as formas de registro.
        'criancas_com_evidencia_recente': _criancas_com_evidencia_recente(
            limite_recente, fim_efetivo
        ),
        'professor_mais_recente_por_crianca': _professor_mais_recente_por_crianca(registros),
        'indicadores': gerar_indicadores_bncc(periodo),
        # Heatmap "Cobertura BNCC × Turmas" (planejamentos do período)
        'planos_por_turma_campo': planos_por_turma_campo,
        'heatmap_campos': heatmap_campos,
        'planos_sem_habilidade_por_turma': planos_sem_habilidade_por_turma,
        # Crianças com relatório finalizado no período.
        'criancas_com_relatorio_finalizado': _criancas_com_relatorio_finalizado(periodo),
        # Ranking de produção docente no período, para o card de saúde.
        'ranking_professores': _ranking_professores(periodo),
        # Distribuição de escrita/leitura das crianças no período.
        'alfabetizacao': _alfabetizacao(periodo),
    }


@transaction.atomic
def atualizar_cache_coordenacao(
    instituicao_id: str,
    data_referencia: date | None = None,
    janela_dias: int = JANELA_DIAS,
) -> CoordenacaoCache:
    """DESATIVADO — grava um snapshot em `CoordenacaoCache`.

    O painel da coordenação passou a calcular os agregados por período
    avaliativo a cada requisição (~70 ms, custo estável), então nada no caminho
    de request chama isto, e a tarefa do scheduler está desligada.

    A função e a tabela foram mantidas de propósito: os snapshots já gravados
    são o único histórico diário que existe. **A poda de retenção foi removida**
    — ela apagava tudo com mais de 30 dias a cada execução, e manter os dados
    era justamente o motivo de não derrubar a tabela.
    """
    if data_referencia is None:
        data_referencia = timezone.localdate() - timedelta(days=1)

    recorte = resolver_recorte(data_referencia=data_referencia)
    payload = gerar_payload_coordenacao(instituicao_id, recorte)

    payload_vazio = (
        not payload['bncc_usage']
        and not payload['criancas_com_registro_recente_15d']
        and not payload['professor_mais_recente_por_crianca']
    )
    if payload_vazio:
        # Snapshot vazio quase nunca é o estado real esperado pela coordenação;
        # logamos as contagens do banco para distinguir "sem dados na janela"
        # de outros problemas sem precisar abrir o banco.
        diag = diagnosticar_cache(data_referencia, janela_dias)
        logger.warning(
            'CoordenacaoCache gerado VAZIO (instituicao=%s). Diagnostico: %s. '
            'O banco tem %s registro(s) no total; nenhum entre %s e %s. '
            'Cheque se ha registros_observacao recentes ou ajuste a janela.',
            instituicao_id,
            diag,
            diag['total_registros_banco'],
            diag['data_inicio_janela'],
            diag['data_referencia'],
        )
    else:
        logger.info(
            'CoordenacaoCache gerado para instituicao=%s data_ref=%s: '
            'bncc=%d criancas_recentes=%d professores=%d',
            instituicao_id,
            data_referencia.isoformat(),
            len(payload['bncc_usage']),
            len(payload['criancas_com_registro_recente_15d']),
            len(payload['professor_mais_recente_por_crianca']),
        )

    obj, _ = CoordenacaoCache.objects.update_or_create(
        instituicao_id=instituicao_id,
        data_referencia=data_referencia,
        defaults={
            'payload': payload,
            'janela_dias': janela_dias,
            'versao_schema': CACHE_SCHEMA_VERSION,
        },
    )

    # Sem poda de retenção: ver docstring. Os snapshots antigos são preservados.

    return obj
