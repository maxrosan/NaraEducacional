"""
Helpers compartilhados pelos endpoints de planejamento semanal/diário.

No schema novo, `HabilidadeBNCC` já é o catálogo oficial — `Pergunta.habilidade_bncc`
é uma FK de verdade pra lá (não um código texto solto como no legado), então
`resolver_habilidade_bncc` não precisa mais materializar nada: só busca no
catálogo por id ou código.
"""

from __future__ import annotations

import logging
import uuid as uuid_lib
from typing import Optional

from api.models import HabilidadeBNCC, PlanejamentoSemanal, Turma

logger = logging.getLogger(__name__)

# Aliases de compatibilidade expostos pelo PlanejamentoSemanalSerializer
# (semana_referencia/id_professor) que precisam ser traduzidos para os campos
# reais do modelo quando chegam em `ordering`.
ORDERING_ALIASES = {
    'semana_referencia': 'semana_inicio',
    'id_professor': 'professor_id',
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

    `professora_id` é mantido como nome de parâmetro por compatibilidade com
    quem já chama esta função — filtra pelo campo `professor` do model.
    """
    queryset = PlanejamentoSemanal.objects.all().prefetch_related('planejamentos_diarios')

    if instituicao_id:
        turmas_ids = list(
            Turma.objects.filter(instituicao_id=instituicao_id).values_list('id', flat=True)
        )
        turmas_ids_str = [str(tid) for tid in turmas_ids]
        queryset = queryset.filter(turma_id__in=turmas_ids_str)

    if turma_id:
        queryset = queryset.filter(turma_id=turma_id)

    if professora_id:
        queryset = queryset.filter(professor_id=professora_id)

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
    Aceita id (int), uuid ou código BNCC (ex.: ``EI03EO01``, ``EF01LP01``).
    Busca direto no catálogo — não materializa nada, já que HabilidadeBNCC
    é a fonte de verdade no schema novo (Pergunta a referencia via FK, o
    que já garante que qualquer código em uso existe no catálogo).
    """
    if referencia is None:
        return None
    ref = str(referencia).strip()
    if not ref:
        return None

    if ref.isdigit():
        encontrada = HabilidadeBNCC.objects.filter(id=int(ref)).first()
        if encontrada:
            return encontrada
    else:
        try:
            encontrada = HabilidadeBNCC.objects.filter(uuid=uuid_lib.UUID(ref)).first()
            if encontrada:
                return encontrada
        except ValueError:
            pass  # não é uuid: segue para o código BNCC
    return HabilidadeBNCC.objects.filter(codigo=ref).first()