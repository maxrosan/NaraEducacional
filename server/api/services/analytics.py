from django.core.cache import cache

from api.models import (
    Turma,
    Aluno,
    RegistroEscrita,
    RegistroDesenho,
    RegistroObservacao,
    Usuario,
    UsuarioTurma,
    Producao,
    Relatorio,
    PlanejamentoSemanal,
    ObservacaoTranscricao,
)


def contar_registros_instituicao(instituicao_id, data_inicio=None, data_fim=None):
    """Conta registros enviados no período, para toda a instituição (todas as escolas)."""
    cache_key = f"contagem_registros_{instituicao_id}_{data_inicio}_{data_fim}"

    resultado = cache.get(cache_key)
    if resultado is not None:
        return resultado

    turma_ids = list(
        Turma.objects.filter(instituicao_id=instituicao_id).values_list('id', flat=True)
    )
    turma_ids_str = [str(t) for t in turma_ids]

    aluno_ids = list(
        Aluno.objects.filter(instituicao_id=instituicao_id).values_list('id', flat=True)
    )

    qs_escrita = RegistroEscrita.objects.filter(turma_id__in=turma_ids_str)
    qs_desenho = RegistroDesenho.objects.filter(turma_id__in=turma_ids_str)
    qs_livres = ObservacaoTranscricao.objects.filter(turma_id__in=turma_ids_str)
    qs_observacao = RegistroObservacao.objects.filter(aluno_id__in=aluno_ids)

    if data_inicio:
        qs_escrita = qs_escrita.filter(criado_em__date__gte=data_inicio)
        qs_desenho = qs_desenho.filter(criado_em__date__gte=data_inicio)
        qs_livres = qs_livres.filter(data_observacao__gte=data_inicio)
        qs_observacao = qs_observacao.filter(data_observacao__gte=data_inicio)

    if data_fim:
        qs_escrita = qs_escrita.filter(criado_em__date__lte=data_fim)
        qs_desenho = qs_desenho.filter(criado_em__date__lte=data_fim)
        qs_livres = qs_livres.filter(data_observacao__lte=data_fim)
        qs_observacao = qs_observacao.filter(data_observacao__lte=data_fim)

    resultado = {
        'analises_escrita': qs_escrita.count(),
        'analises_desenho': qs_desenho.count(),
        'registros_livres': qs_livres.count(),
        'registros_observacao': qs_observacao.count(),
    }

    cache.set(cache_key, resultado, timeout=300)  # 5 minutos

    return resultado


def get_participacao_docente(instituicao_id, data_inicio=None):
    """Produção docente por professor, para toda a instituição."""
    cache_key = f"get_participacao_docente_{instituicao_id}_{data_inicio}"
    resultado = cache.get(cache_key)
    if resultado is not None:
        return resultado

    professores = Usuario.objects.filter(
        instituicao_id=instituicao_id,
        nivel__in=Usuario.NIVEIS_PROFESSOR,
        is_active=True,
    )

    resultado = []
    for prof in professores:
        prof_id_str = str(prof.id)

        turma_ids = list(
            UsuarioTurma.objects.filter(usuario_id=prof.id).values_list('turma_id', flat=True)
        )
        turma_ids_str = [str(t) for t in turma_ids]

        qs_observacao = RegistroObservacao.objects.filter(professor_id=prof.id)
        qs_escrita = RegistroEscrita.objects.filter(turma_id__in=turma_ids_str)
        qs_desenho = RegistroDesenho.objects.filter(turma_id__in=turma_ids_str)
        qs_livres = ObservacaoTranscricao.objects.filter(turma_id__in=turma_ids_str)
        qs_planejamentos = PlanejamentoSemanal.objects.filter(professor_id=prof.id)
        qs_portfolio = Producao.objects.filter(professor_id=prof.id)

        aluno_ids = list(
            Aluno.objects.filter(turma_id__in=turma_ids).values_list('id', flat=True)
        ) if turma_ids else []
        qs_relatorios = (
            Relatorio.objects.filter(aluno_id__in=aluno_ids) if aluno_ids else Relatorio.objects.none()
        )

        if data_inicio:
            qs_observacao = qs_observacao.filter(data_observacao__gte=data_inicio)
            qs_escrita = qs_escrita.filter(criado_em__date__gte=data_inicio)
            qs_desenho = qs_desenho.filter(criado_em__date__gte=data_inicio)
            qs_livres = qs_livres.filter(data_observacao__gte=data_inicio)
            qs_planejamentos = qs_planejamentos.filter(semana_inicio__gte=data_inicio)
            qs_portfolio = qs_portfolio.filter(data_registro__gte=data_inicio)
            qs_relatorios = qs_relatorios.filter(criado_em__date__gte=data_inicio)

        registros = (
            qs_observacao.count()
            + qs_escrita.count()
            + qs_desenho.count()
            + qs_livres.count()
        )

        resultado.append({
            'professor_id': prof_id_str,
            'professor_nome': prof.nome,
            'registros_pedagogicos': registros,
            'relatorios_entregues': qs_relatorios.count(),
            'planejamentos_realizados': qs_planejamentos.count(),
            'portfolio_itens': qs_portfolio.count(),
        })

    resultado.sort(key=lambda x: x['professor_nome'])

    cache.set(cache_key, resultado, timeout=300)  # 5 minutos

    return resultado