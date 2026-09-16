from datetime import timedelta
from django.utils import timezone
from django.db.models import Max

from api.models import (
    ConfiguracaoRegistro,
    Crianca,
    PeriodoAvaliativo,
    ProducaoFotoCrianca,
    RegistroDesenho,
    RegistroEscrita,
    RegistroObservacao,
    Turma,
    Usuario,
    UsuarioTurma,
)

FREQ_DAYS = {
    'diario': 1,
    'semanal': 7,
    'quinzenal': 15,
}

FREQ_LABELS = {
    'diario': 'Di\u00e1rio',
    'semanal': 'Semanal',
    'quinzenal': 'Quinzenal',
}


def _has_active_periodo(instituicao_id):
    """Return True if the institution has an active evaluation period today."""
    today = timezone.localdate()
    return PeriodoAvaliativo.objects.filter(
        instituicao_id=instituicao_id,
        data_inicio__lte=today,
        data_fim__gte=today,
    ).exists()


def _get_turma_configs(turma_ids):
    """Return {turma_id_str: ConfiguracaoRegistro} for turmas that have a config."""
    configs = ConfiguracaoRegistro.objects.filter(turma_id__in=turma_ids)
    return {str(c.turma_id): c for c in configs}


def _most_recent_dates_per_child(criancas, turma_id, professor_id):
    """
    For a list of children in one turma, compute the most recent record date
    across all 4 record sources. Returns {crianca_id_str: date or None}.
    """
    crianca_ids = [str(c.id) for c in criancas]
    crianca_names = {str(c.id): c.nome_completo for c in criancas}
    turma_id_str = str(turma_id)

    # 1) RegistroObservacao — by crianca_id + professor_id
    obs_dates = dict(
        RegistroObservacao.objects.filter(
            crianca_id__in=crianca_ids,
            professor_id=professor_id,
        ).values_list('crianca_id').annotate(latest=Max('data_observacao'))
    )

    # 2) RegistroEscrita — by turma_id, grouped by nome_aluno
    escrita_dates = dict(
        RegistroEscrita.objects.filter(
            turma_id=turma_id_str,
        ).values_list('nome_aluno').annotate(latest=Max('data_criacao'))
    )

    # 3) RegistroDesenho — by turma_id, grouped by nome_aluno
    desenho_dates = dict(
        RegistroDesenho.objects.filter(
            turma_id=turma_id_str,
        ).values_list('nome_aluno').annotate(latest=Max('data_criacao'))
    )

    # 4) ProducaoFotoCrianca → ProducaoFoto.data_registro
    portfolio_dates = dict(
        ProducaoFotoCrianca.objects.filter(
            crianca_id__in=crianca_ids,
        ).values_list('crianca_id').annotate(
            latest=Max('producao_foto__data_registro')
        )
    )

    result = {}
    today = timezone.localdate()
    for cid_str in crianca_ids:
        dates = []

        # obs — keyed by UUID
        obs_val = obs_dates.get(cid_str)
        if obs_val:
            dates.append(obs_val)

        # escrita/desenho — keyed by nome_aluno (case-insensitive match)
        nome = crianca_names.get(cid_str, '')
        for name_key, dt in escrita_dates.items():
            if nome.lower() in name_key.lower() or name_key.lower() in nome.lower():
                dates.append(dt.date() if hasattr(dt, 'date') else dt)
                break
        for name_key, dt in desenho_dates.items():
            if nome.lower() in name_key.lower() or name_key.lower() in nome.lower():
                dates.append(dt.date() if hasattr(dt, 'date') else dt)
                break

        # portfolio — keyed by crianca_id string
        port_val = portfolio_dates.get(cid_str)
        if port_val:
            dates.append(port_val if not hasattr(port_val, 'date') else port_val)

        result[cid_str] = max(dates) if dates else None

    return result


def gerar_alertas_professor(professor_id, instituicao_id, data_referencia=None):
    """
    Generate per-child alerts for a professor based on ConfiguracaoRegistro frequency.
    Returns [] if no active PeriodoAvaliativo or no configured frequencies.
    """
    if not _has_active_periodo(instituicao_id):
        return []

    professor_id_str = str(professor_id)
    today = data_referencia or timezone.localdate()

    # Get turmas the professor is linked to
    turma_ids = list(
        UsuarioTurma.objects.filter(usuario_id=professor_id)
        .values_list('turma_id', flat=True)
    )
    if not turma_ids:
        return []

    configs = _get_turma_configs(turma_ids)
    if not configs:
        return []

    # Fetch turma names for alert messages
    turma_names = dict(
        Turma.objects.filter(id__in=turma_ids).values_list('id', 'nome')
    )

    alertas = []
    for turma_id in turma_ids:
        turma_id_str = str(turma_id)
        config = configs.get(turma_id_str)
        if not config:
            continue

        max_days = FREQ_DAYS.get(config.frequencia_registro)
        if not max_days:
            continue

        criancas = list(
            Crianca.objects.filter(turma_id=turma_id, status_vinculo='ativo')
        )
        if not criancas:
            continue

        recent_dates = _most_recent_dates_per_child(criancas, turma_id, professor_id)
        turma_nome = turma_names.get(turma_id, 'Turma')
        freq_label = FREQ_LABELS.get(config.frequencia_registro, config.frequencia_registro)

        for crianca in criancas:
            cid = str(crianca.id)
            last_date = recent_dates.get(cid)

            if last_date and (today - last_date).days <= max_days:
                continue  # within threshold

            dias = (today - last_date).days if last_date else None
            chave = f'no-record-{professor_id_str}-{cid}-{turma_id_str}'

            if dias is not None:
                resumo = (
                    f'{crianca.nome_completo} ({turma_nome}) sem registro '
                    f'h\u00e1 {dias} dias. Frequ\u00eancia esperada: {freq_label}.'
                )
                conteudo = (
                    f'A crian\u00e7a {crianca.nome_completo} da turma {turma_nome} '
                    f'n\u00e3o possui registros nos \u00faltimos {dias} dias.\n'
                    f'Frequ\u00eancia de registro configurada: {freq_label} '
                    f'(a cada {max_days} dia(s)).\n'
                    f'Por favor, registre atividades para manter o acompanhamento atualizado.'
                )
            else:
                resumo = (
                    f'{crianca.nome_completo} ({turma_nome}) ainda n\u00e3o possui '
                    f'nenhum registro. Frequ\u00eancia esperada: {freq_label}.'
                )
                conteudo = (
                    f'A crian\u00e7a {crianca.nome_completo} da turma {turma_nome} '
                    f'ainda n\u00e3o possui nenhum registro.\n'
                    f'Frequ\u00eancia de registro configurada: {freq_label} '
                    f'(a cada {max_days} dia(s)).\n'
                    f'Por favor, registre atividades para manter o acompanhamento atualizado.'
                )

            alertas.append({
                'id': chave,
                'tipo': 'registro-frequencia',
                'titulo': f'{crianca.nome_completo} sem registro recente',
                'resumo': resumo,
                'conteudo': conteudo,
                'criado_em': timezone.now().isoformat(),
                'dados': {
                    'professor_id': professor_id_str,
                    'crianca_id': cid,
                    'crianca_nome': crianca.nome_completo,
                    'turma_id': turma_id_str,
                    'turma_nome': turma_nome,
                    'dias_sem_registro': dias,
                    'frequencia_esperada': config.frequencia_registro,
                },
            })

    return alertas


def gerar_alertas_coordenacao(instituicao_id, data_referencia=None):
    """
    Generate per-child alerts for all professors in the institution.
    Returns [] if no active PeriodoAvaliativo.
    """
    if not _has_active_periodo(instituicao_id):
        return []

    # Get all active professors in the institution
    professor_ids = (
        UsuarioTurma.objects.filter(turma__instituicao_id=instituicao_id)
        .values_list('usuario_id', flat=True)
        .distinct()
    )
    professores = list(
        Usuario.objects.filter(
            id__in=professor_ids,
            perfil__in=Usuario.PERFIS_PROFESSOR,
            ativo=True,
        ).values_list('id', 'nome')
    )

    alertas = []
    for prof_id, prof_nome in professores:
        prof_alertas = gerar_alertas_professor(prof_id, instituicao_id, data_referencia)
        # Enrich with professor name for coordination view
        for alerta in prof_alertas:
            alerta['dados']['professor_nome'] = prof_nome
            alerta['titulo'] = f'{prof_nome}: {alerta["titulo"]}'
        alertas.extend(prof_alertas)

    return alertas
