"""
Matriz de indicadores do Registro Guiado por turma (tela "Aprendizagens
consolidadas" da coordenação).

Para uma turma + período avaliativo, devolve a matriz aluno × indicador com o
ESTADO de cada marcação (0–3), além das categorias (campos), dos alunos e do
resumo por estado.

Modelo de marcação do Guiado: a professora toca de 1x a 3x por indicador/aluno
(`MAX_MARCACOES = 3`), e cada toque vira uma linha em `RegistroObservacao`
(`resposta='Sim'`). Logo o **nível** = nº de registros daquele (aluno, pergunta)
no período:
  0 → Não observado · 1 → Às vezes · 2 → Em desenvolvimento · 3 → Desenvolvido

Mudanças de schema em relação ao legado:
  - `Crianca` → `Aluno`; `crianca_id` → `aluno_id` em todo lugar.
  - `PerguntaBNCC` → `Pergunta` (`faixa_etaria` continua texto — ver correção
    registrada no MIGRACAO_LEGADO.md — e `campo_experiencia` agora é FK pra
    `CampoPedagogico`, não texto: usa `campo_experiencia__nome`).
  - `RegistroEscrita`/`RegistroDesenho` ganharam `aluno` E `turma` como FK de
    verdade — a função `_producoes_por_aluno` não precisa mais casar por
    nome (`_norm_nome`/`nome_aluno`), simplificando bastante.
  - `data_criacao` → `criado_em`; `PerguntaBNCC.created_at` → `Pergunta.criado_em`.
  - Escopo por `escola_id`, resolvido a partir da própria turma pedida.

Permissão (`escopo.pode_ver_escola`) e recorte
(`views.coordenacao_cache.recorte_da_requisicao`) seguem o contrato comum das
telas da coordenação.
"""

from __future__ import annotations

from collections import OrderedDict, defaultdict

from django.core.exceptions import ValidationError
from django.db.models import Count
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from api.models import Aluno, PeriodoAvaliativo, Pergunta, RegistroDesenho, RegistroEscrita, RegistroLeitura, RegistroObservacao, Turma
from api.services.coordenacao_cache import _padronizar_faixa
from api.escopo import filtro_oficiais_e_da_escola, pode_ver_escola
from api.services.fases_producao import fase_desenho_canonica
from api.views.coordenacao_cache import recorte_da_requisicao

NIVEL_MAX = 3


def _producoes_por_aluno(turma_id, alunos, recorte):
    """Para a turma, devolve {aluno_id: {escrita, desenho, leitura}} com a
    classificação do ÚLTIMO registro de cada modalidade no recorte (ou geral,
    se `recorte` é None). Cada valor é `{classe, data}` ou `None`.

    `RegistroEscrita`/`RegistroDesenho` têm `aluno` como FK de verdade no
    schema novo — sem o casamento por nome que o legado precisava.
    """
    aluno_ids = {str(a['id']) for a in alunos}
    producoes = {aid: {'escrita': None, 'desenho': None, 'leitura': None} for aid in aluno_ids}

    def _em_periodo(qs, campo='criado_em'):
        if recorte:
            return qs.filter(**{
                f'{campo}__date__gte': recorte.data_inicio,
                f'{campo}__date__lte': recorte.data_fim,
            })
        return qs

    esc = _em_periodo(RegistroEscrita.objects.filter(turma_id=turma_id))
    for aluno_id, etapa, data in esc.order_by('criado_em').values_list('aluno_id', 'etapa_ia', 'criado_em'):
        aid = str(aluno_id)
        if aid in producoes and etapa:
            producoes[aid]['escrita'] = {'classe': etapa, 'data': data.date().isoformat()}

    des = _em_periodo(RegistroDesenho.objects.filter(turma_id=turma_id))
    for aluno_id, fase, data in des.order_by('criado_em').values_list('aluno_id', 'fase_desenho', 'criado_em'):
        aid = str(aluno_id)
        if aid in producoes and fase:
            producoes[aid]['desenho'] = {'classe': fase_desenho_canonica(fase), 'data': data.date().isoformat()}

    lei = _em_periodo(
        RegistroLeitura.objects.filter(aluno_id__in=aluno_ids, status='confirmado').exclude(classe_escolhida='')
    )
    for aluno_id, classe, data in lei.order_by('criado_em').values_list('aluno_id', 'classe_escolhida', 'criado_em'):
        aid = str(aluno_id)
        if aid in producoes and classe:
            producoes[aid]['leitura'] = {'classe': classe, 'data': data.date().isoformat()}

    return producoes


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def indicadores_turma(request):
    """Matriz aluno × indicador (estado 0–3) de uma turma, no recorte da coordenação.

    Aceita o mesmo contrato de recorte das demais telas: `periodo_id`, ou
    `data_inicio`+`data_fim`. O parâmetro legado `periodo` continua sendo
    lido, para não quebrar links antigos.
    """
    turma_id = request.GET.get('turma_id')
    periodo_id = request.GET.get('periodo_id') or request.GET.get('periodo') or None
    if not turma_id:
        return Response({'error': 'turma_id é obrigatório'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        turma = Turma.objects.select_related('escola').filter(id=turma_id).first()
    except (ValidationError, ValueError):  # turma_id malformado
        turma = None
    if not turma:
        return Response({'error': 'turma não encontrada'}, status=status.HTTP_404_NOT_FOUND)

    if not pode_ver_escola(request.user, turma.escola):
        return Response({'error': 'Sem permissão.'}, status=status.HTTP_403_FORBIDDEN)

    recorte, erro = recorte_da_requisicao(request, turma.escola_id, periodo_id=periodo_id)
    if erro:
        return erro

    faixa = _padronizar_faixa(turma.faixa_etaria)

    # Indicadores (perguntas) da faixa, agrupados por campo de experiência:
    # oficiais (comuns a todas as escolas) + customizadas desta escola.
    base_perguntas = Pergunta.todos.filter(filtro_oficiais_e_da_escola(turma.escola_id))

    def _perguntas_da_faixa(**filtro_faixa):
        return list(
            base_perguntas.filter(**filtro_faixa)
            .values('id', 'pergunta', 'campo_experiencia__nome', 'area_conhecimento')
            .order_by('campo_experiencia__nome', 'criado_em')
        )

    perguntas = _perguntas_da_faixa(faixa_etaria=faixa)
    if not perguntas and faixa:
        perguntas = _perguntas_da_faixa(faixa_etaria__icontains=faixa)
    pergunta_ids = [p['id'] for p in perguntas]

    alunos = list(
        Aluno.objects.filter(turma_id=turma_id)
        .exclude(status_vinculo='inativo')
        .values('id', 'nome_completo')
        .order_by('nome_completo')
    )
    aluno_ids = [a['id'] for a in alunos]

    periodos = list(
        PeriodoAvaliativo.objects.filter(escola_id=turma.escola_id)
        .values('id', 'descricao', 'data_inicio', 'data_fim')
        .order_by('data_inicio')
    )
    sel = next((p for p in periodos if recorte and str(p['id']) == str(recorte.periodo_id)), None)

    regs = RegistroObservacao.objects.filter(aluno_id__in=aluno_ids, pergunta_id__in=pergunta_ids)
    if recorte:
        regs = regs.filter(data_observacao__gte=recorte.data_inicio, data_observacao__lte=recorte.data_fim)
    contagens = regs.values('aluno_id', 'pergunta_id').annotate(n=Count('id'))

    matriz: dict[str, dict[str, int]] = defaultdict(dict)
    for row in contagens:
        nivel = min(row['n'], NIVEL_MAX)
        matriz[str(row['aluno_id'])][str(row['pergunta_id'])] = nivel

    categorias: "OrderedDict[str, list]" = OrderedDict()
    for p in perguntas:
        campo = p['campo_experiencia__nome'] or 'Outros'
        categorias.setdefault(campo, []).append({'id': str(p['id']), 'label': p['pergunta']})

    resumo = {'naoObs': 0, 'asVezes': 0, 'emDesenv': 0, 'desenv': 0}
    for a in aluno_ids:
        linha = matriz.get(str(a), {})
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

    producoes = _producoes_por_aluno(turma_id, alunos, recorte)

    return Response({
        'turma': {'id': str(turma.id), 'nome': turma.nome, 'faixa': turma.faixa_etaria},
        'periodos': [{'id': str(p['id']), 'descricao': p['descricao']} for p in periodos],
        'periodo_selecionado': str(sel['id']) if sel else None,
        'recorte_descricao': recorte.descricao if recorte else None,
        'alunos': [{'id': str(a['id']), 'nome': a['nome_completo']} for a in alunos],
        'categorias': [{'campo': k, 'perguntas': v} for k, v in categorias.items()],
        'matriz': {k: dict(v) for k, v in matriz.items()},
        'producoes': producoes,
        'resumo': resumo,
        'total_marcacoes': len(aluno_ids) * len(pergunta_ids),
    }, status=status.HTTP_200_OK)