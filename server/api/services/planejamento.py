"""
Helpers compartilhados pelos endpoints de planejamento semanal/diário.

`perguntas_bncc.habilidade_bncc` é a fonte canônica de habilidades BNCC.
O catálogo `habilidades_bncc` (FK do `PlanejamentoHabilidade`) começa vazio
e é populado on-demand pelo `resolver_habilidade_bncc`: quando um código
aparece pela primeira vez, a entrada é materializada com os metadados
extraídos de `PerguntaBNCC`.
"""

from __future__ import annotations

import logging
from typing import Optional

from api.models import HabilidadeBNCC, PerguntaBNCC, PlanejamentoSemanal, Turma

logger = logging.getLogger(__name__)

# Aliases de compatibilidade expostos pelo PlanejamentoSemanalSerializer
# (semana_referencia/id_professor) que precisam ser traduzidos para os campos
# reais do modelo quando chegam em `ordering`.
ORDERING_ALIASES = {
    'semana_referencia': 'semana_inicio',
    'id_professor': 'professora_id',
}


def listar_planejamentos_filtrados(
    instituicao_id=None,
    turma_id=None,
    professora_id=None,
    semana_gte=None,
    semana_lte=None,
    ordering='-semana_inicio',
):
    """
    Monta o queryset de ``PlanejamentoSemanal`` aplicando os filtros do
    frontend. `semana_referencia`/`id_professor` são apenas aliases de leitura
    no serializer — aqui o filtro de data mapeia para ``semana_inicio`` e o
    ordering é traduzido para o campo real do modelo (preservando o ``-``).
    """
    queryset = PlanejamentoSemanal.objects.all().prefetch_related('dias')

    if instituicao_id:
        turmas_ids = list(
            Turma.objects.filter(instituicao_id=instituicao_id).values_list('id', flat=True)
        )
        turmas_ids_str = [str(tid) for tid in turmas_ids]
        queryset = queryset.filter(turma_id__in=turmas_ids_str)

    if turma_id:
        queryset = queryset.filter(turma_id=turma_id)

    if professora_id:
        queryset = queryset.filter(professora_id=professora_id)

    # O frontend pode enviar datas em ISO com timezone; usamos só YYYY-MM-DD.
    if semana_gte:
        if 'T' in semana_gte:
            semana_gte = semana_gte.split('T')[0]
        queryset = queryset.filter(semana_inicio__gte=semana_gte)
    if semana_lte:
        if 'T' in semana_lte:
            semana_lte = semana_lte.split('T')[0]
        queryset = queryset.filter(semana_inicio__lte=semana_lte)

    ordering = ordering or '-semana_inicio'
    prefixo = '-' if ordering.startswith('-') else ''
    campo = ordering.lstrip('-')
    campo = ORDERING_ALIASES.get(campo, campo)
    queryset = queryset.order_by(f'{prefixo}{campo}')

    return queryset


def resolver_habilidade_bncc(referencia) -> Optional[HabilidadeBNCC]:
    """
    Aceita id (UUID/inteiro) ou código BNCC (ex.: ``EI03EO01``, ``EF01LP01``).

    Procura primeiro em ``habilidades_bncc``; se não existir, tenta em
    ``perguntas_bncc.habilidade_bncc`` e materializa a entrada no catálogo
    a partir dos metadados da pergunta. Retorna ``None`` quando o código não
    aparece em nenhuma das duas tabelas.
    """
    if referencia is None:
        return None
    ref = str(referencia).strip()
    if not ref:
        return None

    try:
        habilidade = (
            HabilidadeBNCC.objects.filter(id=ref).first()
            or HabilidadeBNCC.objects.filter(codigo=ref).first()
        )
    except (ValueError, TypeError):
        habilidade = HabilidadeBNCC.objects.filter(codigo=ref).first()

    if habilidade is not None:
        return habilidade

    pergunta = (
        PerguntaBNCC.objects.filter(habilidade_bncc=ref)
        .exclude(habilidade_bncc__isnull=True)
        .exclude(habilidade_bncc__exact='')
        .first()
    )
    if pergunta is None:
        return None

    descricao = (pergunta.pergunta_norma or pergunta.pergunta or '').strip()
    componente = (pergunta.area_conhecimento or pergunta.campo_experiencia or '').strip()
    ano_serie = (pergunta.faixa_etaria or '').strip()
    campo_atuacao = (pergunta.campo_experiencia or '').strip() or None

    habilidade, criado = HabilidadeBNCC.objects.get_or_create(
        codigo=ref,
        defaults={
            'descricao': descricao,
            'componente_curricular': componente,
            'ano_serie': ano_serie,
            'campo_atuacao': campo_atuacao,
        },
    )
    if criado:
        logger.info(
            "Habilidade BNCC %s materializada no catálogo a partir de perguntas_bncc.",
            ref,
        )
    return habilidade
