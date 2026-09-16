from django.utils import timezone
from django.db.models import Count

from api.models import PeriodoAvaliativo, Turma, Crianca, RegistroEscrita, ObservacaoTranscricao


def obter_periodo_ativo(instituicao_id, periodo_id=None, data_referencia=None):
    """
    Retorna o período avaliativo ativo para a instituição.
    """
    referencia = data_referencia or timezone.localdate()
    queryset = PeriodoAvaliativo.objects.filter(instituicao_id=instituicao_id)

    if periodo_id:
        return queryset.filter(id=periodo_id).first()

    return queryset.filter(data_inicio__lte=referencia, data_fim__gte=referencia).order_by('-data_inicio').first()


def _contar_criancas_por_turma(turmas_ids):
    return {
        str(item['turma_id']): item['total']
        for item in Crianca.objects.filter(turma_id__in=turmas_ids)
        .values('turma_id')
        .annotate(total=Count('id'))
    }


def _contar_unicos_por_turma(valores, chave_turma):
    contagem = {}
    for item in valores:
        turma_id = item.get(chave_turma)
        if not turma_id:
            continue
        turma_id = str(turma_id)
        identificador = item.get('crianca_id') or item.get('aluno_nome') or item.get('nome_aluno')
        if not identificador:
            continue
        contagem.setdefault(turma_id, set()).add(str(identificador))
    return {turma_id: len(ids) for turma_id, ids in contagem.items()}


def calcular_desenvolvimento_linguagem(instituicao_id, periodo, turma_ids=None):
    """
    Calcula o indicador de desenvolvimento de linguagem por turma.
    """
    if not periodo:
        return []

    turmas_queryset = Turma.objects.filter(instituicao_id=instituicao_id)
    if turma_ids:
        turmas_queryset = turmas_queryset.filter(id__in=turma_ids)

    turmas = list(turmas_queryset)
    if not turmas:
        return []

    turmas_ids = [turma.id for turma in turmas]
    turmas_ids_str = [str(turma_id) for turma_id in turmas_ids]

    criancas_por_turma = _contar_criancas_por_turma(turmas_ids)

    inicio = periodo.data_inicio
    fim = periodo.data_fim

    leitura_qs = ObservacaoTranscricao.objects.filter(
        turma_id__in=turmas_ids_str,
        tipo_observacao='LEITURA_ORAL',
        data_observacao__gte=inicio,
        data_observacao__lte=fim,
    ).values('turma_id', 'crianca_id', 'aluno_nome')

    fala_qs = ObservacaoTranscricao.objects.filter(
        turma_id__in=turmas_ids_str,
        tipo_observacao__in=['TRANSCRICAO_IA', 'OBSERVACAO_MANUAL'],
        data_observacao__gte=inicio,
        data_observacao__lte=fim,
    ).values('turma_id', 'crianca_id', 'aluno_nome')

    escrita_qs = RegistroEscrita.objects.filter(
        turma_id__in=turmas_ids_str,
        data_criacao__date__gte=inicio,
        data_criacao__date__lte=fim,
    ).values('turma_id', 'nome_aluno')

    leitura_por_turma = _contar_unicos_por_turma(leitura_qs, 'turma_id')
    fala_por_turma = _contar_unicos_por_turma(fala_qs, 'turma_id')
    escrita_por_turma = _contar_unicos_por_turma(escrita_qs, 'turma_id')

    resultados = []

    for turma in turmas:
        turma_id_str = str(turma.id)
        total_criancas = criancas_por_turma.get(turma_id_str, 0)

        def calcular_percentual(total):
            if total_criancas == 0:
                return 0
            return min(100, round((total / total_criancas) * 100))

        leitura_percent = calcular_percentual(leitura_por_turma.get(turma_id_str, 0))
        escrita_percent = calcular_percentual(escrita_por_turma.get(turma_id_str, 0))
        fala_percent = calcular_percentual(fala_por_turma.get(turma_id_str, 0))
        percentual_final = round((leitura_percent + escrita_percent + fala_percent) / 3)

        resultados.append(
            {
                'turma_id': turma_id_str,
                'turma_nome': turma.nome,
                'turma_turno': turma.turno,
                'total_criancas': total_criancas,
                'leitura_percentual': leitura_percent,
                'escrita_percentual': escrita_percent,
                'fala_percentual': fala_percent,
                'percentual_final': percentual_final,
            }
        )

    return resultados
