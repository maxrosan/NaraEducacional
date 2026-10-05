"""Serviços de domínio para geração de relatórios pedagógicos com IA."""

import json
import re
import datetime
import logging
from datetime import timedelta
from collections import Counter
from pathlib import Path

from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.forms.models import model_to_dict

from django.utils.html import escape

from api.storage import get_foto_url, get_logo_url

from api.models import (
    Aluno,
    Escola,
    Instituicao,
    ObservacaoTranscricao,
    PeriodoAvaliativo,
    Pergunta,
    PlanejamentoSemanal,
    ProducaoAluno,
    RegistroDesenho,
    RegistroEscrita,
    RegistroObservacao,
    RelatorioTemplate,
)
from api.openai_client import get_openai_client
from api.storage import refresh_presigned_url

from api.services.guarda_idioma import criar_completion_com_guarda
from api.services.html_seguro import fechar_html
from api.services.prompt_resolver import resolver_prompt
from api.services.relatorio_capa import renderizar_capa, ELEMENTOS_VISIVEIS_PADRAO
from api.escopo import filtro_oficiais_e_da_escola

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"

GPT_MODEL = "gpt-5.4-mini"
MAX_TOKENS = 1200

# Chaves fixas das seções do corpo do relatório — cada uma corresponde a
# conteúdo real gerado em gerar_relatorio_com_ia. O coordenador pode renomear,
# reordenar e ocultar, mas NUNCA criar uma seção com chave fora deste conjunto
# (não haveria conteúdo real por trás dela).
_SECOES_PADRAO = [
    {"chave": "atividades", "titulo": "O que vivemos juntos neste período", "visivel": True},
    {"chave": "relato", "titulo": "Relato Individual", "visivel": True},
    {"chave": "producoes", "titulo": "Análise das Produções", "visivel": True},
    {"chave": "portfolio", "titulo": "Portfólio da Criança", "visivel": True},
    {"chave": "bncc", "titulo": "Acompanhamento por Habilidades da BNCC", "visivel": True},
    {"chave": "conclusao", "titulo": "Conclusão da Professora", "visivel": True},
]
_TITULOS_PADRAO = {item["chave"]: item["titulo"] for item in _SECOES_PADRAO}
_CHAVES_VALIDAS = set(_TITULOS_PADRAO.keys())

# Ícone fixo por seção (não é personalizável — só o título e a visibilidade são).
_ICONES_SECAO = {
    "atividades": "🌱",
    "relato": "👦",
    "portfolio": "📸",
    "bncc": "📋",
    "conclusao": "💛",
}

# ── Rede de segurança contra vazamento de idioma da IA ──────────────
# A guarda vive em api/services/guarda_idioma.py, compartilhada com os
# outros serviços que geram texto por IA (análise de produções, extração de
# observações, planejamento). Aqui fica só o adaptador com a assinatura que
# as seções do relatório já usavam.


# Placeholder de prompt que ninguém substituiu: `{habilidades_bncc}` e
# `{analises_producoes}` iam literalmente para a IA no relato desde abril.
_PLACEHOLDER_RE = re.compile(r"\{[a-z_]+\}")


def _sem_placeholder_sobrando(conteudo, log_prefix="[OPENAI]"):
    """Troca por "(não informado)" o placeholder que chegou até aqui sem
    substituição, e registra. Os prompts são editáveis por escola: um
    placeholder novo, ou com erro de digitação, não pode virar texto cru na
    frente da IA."""
    if not isinstance(conteudo, str):
        return conteudo
    sobrando = sorted(set(_PLACEHOLDER_RE.findall(conteudo)))
    if not sobrando:
        return conteudo
    logger.warning("%s Placeholder sem substituição no prompt: %s", log_prefix, ", ".join(sobrando))
    return _PLACEHOLDER_RE.sub("(não informado)", conteudo)


def _preencher_prompt(template, **valores):
    """Substitui `{chave}` pelos valores, tolerando None/números.

    `str.replace` com None lança TypeError — e como cada seção engole
    exceções, um `idade=None` derrubava a seção inteira para o fallback sem
    nenhuma pista no log. Aqui None/vazio vira "Não informado".
    """
    resultado = template or ""
    for chave, valor in valores.items():
        texto = "Não informado" if valor is None or str(valor).strip() == "" else str(valor)
        resultado = resultado.replace("{" + chave + "}", texto)
    return resultado


def _tem_placeholder(template, chave):
    return ("{" + chave + "}") in (template or "")


def _texto_para_html(texto):
    """Texto puro (com quebras de linha) -> parágrafos HTML escapados.
    Usado nos fallbacks, para não jogar texto cru com \\n dentro de um <p>."""
    blocos = [b.strip() for b in re.split(r"\n\s*\n", texto or "") if b.strip()]
    return "".join(
        "<p>" + "<br>".join(escape(linha) for linha in bloco.splitlines()) + "</p>"
        for bloco in blocos
    )


# Schema da seção de atividades: o código sempre fez json.loads esperando
# {"texto": ...}, mas não impunha o formato — resposta em texto livre caía no
# fallback e o relatório saía com o planejamento cru.
_SCHEMA_ATIVIDADES = {
    "type": "json_schema",
    "json_schema": {
        "name": "secao_atividades",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "texto": {
                    "type": "string",
                    "description": "Narrativa da seção 'O que vivemos juntos' em HTML (parágrafos <p>), sem título.",
                },
            },
            "required": ["texto"],
        },
    },
}


def _gerar_com_guarda_idioma(
    openai_client, *, model, messages, max_completion_tokens,
    usuario=None, response_format=None, log_prefix="[OPENAI]",
):
    """Chama chat.completions.create com a guarda de idioma
    (guarda_idioma.criar_completion_com_guarda): a regra de idioma entra no
    prompt de toda chamada e, se a resposta ainda vier com letra de outro
    alfabeto, tenta de novo com a regra reforçada e só então remove os
    trechos estranhos — nunca bloqueia a geração do relatório.

    Retorna o texto bruto (str) da resposta; quem chamar continua fazendo o
    parsing específico da seção (JSON, code fences etc.) normalmente.
    """
    kwargs = {"model": model, "max_completion_tokens": max_completion_tokens}
    if response_format is not None:
        kwargs["response_format"] = response_format

    # Só a mensagem de instrução (o template do prompt); a de dados traz texto
    # da professora, que pode ter chaves por conta própria.
    if messages:
        messages = [dict(messages[0], content=_sem_placeholder_sobrando(messages[0].get("content"), log_prefix))] + list(messages[1:])

    return criar_completion_com_guarda(
        openai_client,
        messages=messages,
        usuario=usuario,
        log_prefix=log_prefix,
        **kwargs,
    )

def _normalizar_elementos(template):
    """Valida template.config['elementos'] (JSON sem schema garantido).
    Chave desconhecida é ignorada; chave ausente cai no padrão (visível)."""
    bruto = (template.config or {}).get('elementos') if template and isinstance(template.config, dict) else None
    elementos = dict(ELEMENTOS_VISIVEIS_PADRAO)
    if isinstance(bruto, dict):
        for chave in ELEMENTOS_VISIVEIS_PADRAO:
            if chave in bruto:
                elementos[chave] = bool(bruto[chave])
    return elementos


def _normalizar_items_sumario(template):
    """
    Valida e normaliza `template.items_sumario` (JSONField, sem schema
    garantido no banco). Protege contra:
    - template=None (sem template ativo) -> usa a ordem/títulos padrão;
    - JSON vazio, malformado ou não-lista -> idem;
    - itens com `chave` desconhecida ou duplicada -> ignorados;
    - seção fixa nova que não existe em templates salvos antes dela -> entra
      no fim, visível, com título padrão (não desaparece silenciosamente).
    """
    bruto = getattr(template, 'items_sumario', None) if template else None
    if not bruto or not isinstance(bruto, list):
        return [dict(item) for item in _SECOES_PADRAO]

    normalizado = []
    chaves_vistas = set()
    for item in bruto:
        if not isinstance(item, dict):
            continue
        chave = item.get('chave')
        if chave not in _CHAVES_VALIDAS or chave in chaves_vistas:
            continue
        chaves_vistas.add(chave)
        normalizado.append({
            'chave': chave,
            'titulo': (item.get('titulo') or '').strip() or _TITULOS_PADRAO[chave],
            'visivel': bool(item.get('visivel', True)),
        })

    for chave, titulo in _TITULOS_PADRAO.items():
        if chave not in chaves_vistas:
            normalizado.append({'chave': chave, 'titulo': titulo, 'visivel': True})

    return normalizado

def _carregar_prompt(nome_arquivo: str) -> str:
    return (_PROMPTS_DIR / nome_arquivo).read_text(encoding="utf-8")


def obter_periodo_avaliativo_corrente(instituicao_id, escola_id=None):
    """
    Retorna o período avaliativo corrente (o que abrange hoje) ou, na falta
    dele, o mais recente. `PeriodoAvaliativo` pertence a uma ESCOLA: quando
    `escola_id` é informado, só os períodos daquela escola são considerados —
    escolas da mesma instituição podem ter calendários diferentes.
    """
    today = timezone.now().date()
    base = PeriodoAvaliativo.objects.filter(instituicao_id=instituicao_id)
    if escola_id:
        base = base.filter(escola_id=escola_id)

    periodo = (
        base.filter(data_inicio__lte=today, data_fim__gte=today)
        .order_by('-data_inicio')
        .first()
    )
    return periodo or base.order_by('-data_inicio').first()


def _strip_code_fences(text):
    """Remove markdown code fences (```html ... ```) that LLMs sometimes wrap around HTML."""
    text = text.strip()
    if text.startswith('```'):
        text = text.split('\n', 1)[-1] if '\n' in text else text[3:]
        if text.endswith('```'):
            text = text[:-3]
        text = text.strip()
    return text


def parse_timestamp_safely(timestamp_value):
    """
    Parse timestamp safely with multiple fallback strategies.
    """
    if not timestamp_value:
        return datetime.datetime.now().strftime('%d/%m/%Y')

    if not isinstance(timestamp_value, str):
        timestamp_value = str(timestamp_value)

    try:
        if '+' in timestamp_value or 'Z' in timestamp_value:
            dt_obj = datetime.datetime.fromisoformat(timestamp_value.replace('Z', '+00:00'))
            return dt_obj.strftime('%d/%m/%Y')
    except Exception:
        pass

    try:
        dt_obj = datetime.datetime.fromisoformat(timestamp_value)
        return dt_obj.strftime('%d/%m/%Y')
    except Exception:
        pass

    formats = [
        '%Y-%m-%dT%H:%M:%S.%f%z',
        '%Y-%m-%dT%H:%M:%S%z',
        '%Y-%m-%dT%H:%M:%S.%f',
        '%Y-%m-%dT%H:%M:%S',
        '%Y-%m-%d %H:%M:%S',
        '%Y-%m-%d',
    ]
    for fmt in formats:
        try:
            dt_obj = datetime.datetime.strptime(timestamp_value.replace('Z', '+0000'), fmt)
            return dt_obj.strftime('%d/%m/%Y')
        except Exception:
            continue

    try:
        if len(timestamp_value) >= 10:
            date_part = timestamp_value[:10]
            if '-' in date_part:
                parts = date_part.split('-')
                if len(parts) == 3:
                    return f"{parts[2]}/{parts[1]}/{parts[0]}"
    except Exception:
        pass

    return datetime.datetime.now().strftime('%d/%m/%Y')


def buscar_dados_estudante_para_relatorio(crianca_id, periodo):
    """
    Buscar dados do aluno no Postgres para geração do relatório.

    O aluno é lido pelo `TenantManager`: fora do escopo do usuário, nada é
    retornado (e nenhum dado vinculado a ele é consultado).
    """
    dados = {
        'observacoes': [],
        'producoes': [],
        'registros': [],
        'info_crianca': {},
    }

    try:
        aluno = Aluno.objects.select_related('turma').filter(id=crianca_id).first()
        if not aluno:
            logger.warning("Aluno não encontrado (ou fora do escopo) para relatório.", extra={"crianca_id": str(crianca_id)})
            return dados

        info = model_to_dict(aluno)
        # model_to_dict devolve FKs pelo nome do campo ('turma'); o resto do
        # serviço lê as chaves *_id — expõe as duas formas.
        info.update({
            'id': str(aluno.id),
            'turma_id': aluno.turma_id,
            'escola_id': aluno.escola_id,
            'instituicao_id': aluno.instituicao_id,
            'turma_nome': aluno.turma.nome if aluno.turma_id else '',
        })
        if aluno.data_nascimento:
            today = datetime.date.today()
            born = aluno.data_nascimento
            age_years = today.year - born.year - ((today.month, today.day) < (born.month, born.day))
            info['idade'] = f"{age_years} anos"
        dados['info_crianca'] = info

        dados['observacoes'] = list(
            RegistroObservacao.objects.filter(aluno_id=aluno.id)
            .order_by('-data_observacao')[:20]
            .values()
        )

        # Portfólio: vínculos ProducaoAluno → Producao (N-para-N).
        vinculos = (
            ProducaoAluno.objects.filter(aluno_id=aluno.id)
            .select_related('producao', 'producao__projeto')
        )
        data_inicio = parse_date(periodo.get('startDate') or periodo.get('start_date') or '') if periodo else None
        data_fim = parse_date(periodo.get('endDate') or periodo.get('end_date') or '') if periodo else None
        if data_inicio:
            vinculos = vinculos.filter(producao__data_registro__gte=data_inicio)
        if data_fim:
            vinculos = vinculos.filter(producao__data_registro__lte=data_fim)

        dados['producoes'] = []
        for v in vinculos.order_by('-producao__data_registro')[:15]:
            p = v.producao
            dados['producoes'].append({
                'id': p.id,
                'arquivo_url': refresh_presigned_url(p.arquivo_url),
                'arquivo_nome': p.arquivo_nome,
                'tipo_midia': p.tipo,
                'data_registro': str(p.data_registro) if p.data_registro else '',
                'tags': p.tags or [],
                'titulo': p.titulo or (p.projeto.nome if p.projeto_id else '') or p.arquivo_nome,
                # Legenda preenchida pelo professor/coordenador no vínculo aluno ↔ produção
                'legenda': v.legenda or '',
            })

        logger.info(
            "Dados coletados do Postgres para relatório.",
            extra={
                "crianca_id": str(crianca_id),
                "observacoes": len(dados['observacoes']),
                "producoes": len(dados['producoes']),
            },
        )
    except Exception:
        logger.exception("Erro ao buscar dados do relatório no Postgres.", extra={"crianca_id": str(crianca_id)})

    return dados


def buscar_relatos_individuais_crianca(nome_crianca, periodo, aluno_id=None):
    """
    Buscar relatos individuais do aluno na tabela ObservacaoTranscricao.

    Vínculo principal: FK `aluno`. Transcrições em que a IA não conseguiu
    confirmar a criança ficam com `aluno=None` e só o nome cru em `aluno_nome`
    — essas entram por nome exato, para não perder relatos antigos.
    """
    try:
        if periodo.get('type') == 'bimestre':
            data_fim = datetime.date.today()
            data_inicio = data_fim - timedelta(days=90)
        else:
            data_inicio = parse_date(periodo.get('start_date') or periodo.get('startDate')) or (datetime.date.today() - timedelta(days=90))
            data_fim = parse_date(periodo.get('end_date') or periodo.get('endDate')) or datetime.date.today()
    except Exception:
        data_fim = datetime.date.today()
        data_inicio = data_fim - timedelta(days=90)

    logger.info("Buscando relatos individuais.", extra={
        "nome_crianca": nome_crianca, "data_inicio": str(data_inicio), "data_fim": str(data_fim),
    })

    vinculo = Q(aluno__isnull=True, aluno_nome__iexact=nome_crianca)
    if aluno_id:
        vinculo |= Q(aluno_id=aluno_id)

    observacoes = ObservacaoTranscricao.objects.filter(
        vinculo,
        data_observacao__gte=data_inicio,
        data_observacao__lte=data_fim,
    ).select_related('professor').order_by('data_observacao')

    relatos_encontrados = [
        {
            'data': obs.data_observacao.isoformat() if obs.data_observacao else None,
            'observacao': obs.observacao_texto,
            'professora': obs.professor.nome if obs.professor_id else '',
            'turma_id': str(obs.turma_id) if obs.turma_id else None,
            'metadados': obs.metadados_ia or {},
        }
        for obs in observacoes
    ]

    logger.info("Relatos encontrados.", extra={
        "nome_crianca": nome_crianca, "total": len(relatos_encontrados),
    })
    return relatos_encontrados


def _formatar_secao_bncc_html(perguntas_bncc, respostas_sim_por_pergunta):
    """Formata a seção BNCC como tabela com badges coloridos."""
    if not perguntas_bncc or not respostas_sim_por_pergunta:
        return "<p>Sem registros de observação BNCC para o período especificado.</p>"

    linhas = []
    for pergunta in perguntas_bncc:
        qtd = respostas_sim_por_pergunta.get(pergunta.id, 0)

        if qtd >= 3:
            badge_class = "badge-desenvolvido"
            badge_label = "🟢 Desenvolvido"
        elif qtd == 2:
            badge_class = "badge-desenvolvendo"
            badge_label = "🟡 Em desenvolvimento"
        elif qtd == 1:
            badge_class = "badge-avezes"
            badge_label = "🟠 Às vezes"
        else:
            badge_class = "badge-nao-observado"
            badge_label = "⚪ Não observado"
            continue # Não processe pergunta sem resposta

        codigo = pergunta.habilidade_bncc.codigo if pergunta.habilidade_bncc_id else ""
        texto = pergunta.pergunta or ""
        linhas.append(
            f'<tr><td><strong>{codigo}</strong> — {texto}</td>'
            f'<td><span class="badge-status {badge_class}">{badge_label}</span></td></tr>'
        )

    return (
        '<table class="bncc-tabela">'
        '<thead><tr><th>Habilidade</th><th>Status</th></tr></thead>'
        '<tbody>' + "\n".join(linhas) + '</tbody>'
        '</table>'
    )


def _formatar_secao_portfolio_html(producoes):
    """Formata o portfólio da criança como grid com miniaturas."""
    fotos = [p for p in producoes if p.get('arquivo_url')]
    if not fotos:
        return "<p>Sem fotos no portfólio para o período.</p>"

    itens = []
    for foto in fotos:
        url = foto['arquivo_url']
        titulo = foto.get('titulo') or ''
        legenda_vinculo = foto.get('legenda') or ''

        data = ''
        if foto.get('data_registro'):
            try:
                dt = parse_date(str(foto['data_registro']))
                data = dt.strftime('%d/%m/%Y') if dt else ''
            except Exception:
                pass

        # Monta a legenda: texto do vínculo (se houver) + data
        partes = [p for p in [legenda_vinculo, f'Data: {data}' if data else ''] if p]
        legenda = ' — '.join(partes)

        legenda_html = f'<div class="portfolio-legenda">{legenda}</div>' if legenda else ''

        itens.append(
            f'<div class="portfolio-item">'
            f'<div class="portfolio-foto"><img src="{url}" alt="{titulo}" /></div>'
            f'{legenda_html}'
            f'</div>'
        )

    return '<div class="portfolio-grid">' + "\n".join(itens) + '</div>'


def _calcular_datas_periodo(periodo):
    """Retorna (data_inicio, data_fim) a partir do dict de período."""
    if periodo.get('type') == 'bimestre':
        data_fim = timezone.now().date()
        data_inicio = data_fim - timedelta(days=90)
    else:
        data_inicio = parse_date(periodo.get('startDate')) or (timezone.now().date() - timedelta(days=90))
        data_fim = parse_date(periodo.get('endDate')) or timezone.now().date()
    return data_inicio, data_fim


def _gerar_secao_atividades(info_crianca, periodo, nome_crianca, usuario=None, escola_id=None):
    """Seção 1: O que vivemos juntos — busca planejamentos e gera narrativa via IA."""
    o_que_vivemos_juntos = ""
    tem_atividade = False

    try:
        turma_id = info_crianca.get('turma_id')
        logger.debug("[PLANEJAMENTOS] turma_id=%s", turma_id)

        if turma_id:
            inicio_periodo, fim_periodo = _calcular_datas_periodo(periodo)
            logger.debug("[PLANEJAMENTOS] período de busca: %s a %s", inicio_periodo, fim_periodo)

            planejamentos = PlanejamentoSemanal.objects.filter(
                turma_id=turma_id,
                semana_inicio__gte=inicio_periodo,
                semana_inicio__lte=fim_periodo,
            ).order_by('semana_inicio')
            planejamentos = list(planejamentos)

            logger.debug("[PLANEJAMENTOS] encontrados %d planejamentos", len(planejamentos))

            if planejamentos:
                o_que_vivemos_juntos += "ATIVIDADES E EXPERIÊNCIAS DESENVOLVIDAS:\n\n"

                for planejamento in planejamentos:
                    semana_str = f"Semana de {planejamento.semana_inicio.strftime('%d/%m')} a {planejamento.semana_fim.strftime('%d/%m')}"
                    o_que_vivemos_juntos += f"📅 {semana_str}\n"

                    dias = planejamento.planejamentos_diarios.all().order_by('data')
                    for dia in dias:
                        if dia.atividades_propostas:
                            dia_nome = dia.dia_semana.title().replace('_', '-')
                            o_que_vivemos_juntos += f"• {dia_nome}: {dia.atividades_propostas}\n"

                        habilidades_dia = dia.planejamentos_habilidades.select_related('habilidade_bncc')
                        if habilidades_dia:
                            codigos_bncc = [h.habilidade_bncc.codigo for h in habilidades_dia]
                            o_que_vivemos_juntos += f"  (Habilidades BNCC: {', '.join(codigos_bncc)})\n"

                    o_que_vivemos_juntos += "\n"
                    tem_atividade = True

                logger.debug("[RELATÓRIO] %d planejamentos semanais adicionados", len(planejamentos))
            else:
                logger.debug("[PLANEJAMENTOS] nenhum planejamento no período; usando texto padrão")
                o_que_vivemos_juntos = "Neste período, desenvolvemos diversas atividades pedagógicas focadas no desenvolvimento integral da criança.\n\n"
        else:
            logger.debug("[PLANEJAMENTOS] aluno sem turma; usando texto padrão")
            o_que_vivemos_juntos = "Atividades desenvolvidas conforme planejamento pedagógico da turma.\n\n"

    except Exception:
        logger.exception("Erro ao buscar planejamentos para o relatório.")
        o_que_vivemos_juntos = "Diversas experiências de aprendizagem foram vivenciadas durante este período.\n\n"

    if not tem_atividade:
        return _texto_para_html(o_que_vivemos_juntos)

    try:
        logger.debug("[OPENAI] enviando prompt da seção de atividades")
        turma_nome = info_crianca.get('turma_nome', 'Não informado')
        idade = info_crianca.get('idade', 'Não informada')

        # ── Categoria específica para atividades ──────────────────
        prompt_template = resolver_prompt(
            "Relatórios - Atividades",
            escola_id=escola_id,
            fallback_arquivo="relatorio_atividades.txt",
        )

        prompt = _preencher_prompt(
            prompt_template,
            turma=turma_nome,
            idade=idade,
            planejamentos=o_que_vivemos_juntos,
        )
        # Se o prompt já embute os planejamentos, não manda de novo como
        # mensagem do usuário (antes ia duas vezes e comia o limite de tokens).
        if _tem_placeholder(prompt_template, "planejamentos"):
            mensagem_usuario = "Gere a seção conforme as instruções, usando os planejamentos acima."
        else:
            mensagem_usuario = o_que_vivemos_juntos
        openai_client = get_openai_client()

        raw_content = _gerar_com_guarda_idioma(
            openai_client,
            model=GPT_MODEL,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": mensagem_usuario},
            ],
            max_completion_tokens=MAX_TOKENS,
            usuario=usuario,
            response_format=_SCHEMA_ATIVIDADES,
            log_prefix="[OPENAI-ATIVIDADES]",
        )

        parsed = json.loads(_strip_code_fences(raw_content))
        texto = (parsed.get('texto') or '').strip()
        if not texto:
            raise ValueError("Resposta JSON sem campo 'texto'.")

        logger.debug("[OPENAI] narrativa validada (%d caracteres)", len(texto))
        return texto
    except RuntimeError as openai_config_error:
        logger.error("[OPENAI] configuração ausente: %s", openai_config_error)
        return "<p>A geração automática de narrativa está temporariamente indisponível.</p>"
    except Exception:
        logger.exception("[OPENAI] falha ao gerar a seção de atividades.")
        return _texto_para_html(o_que_vivemos_juntos) or "<p>Diversas experiências de aprendizagem foram vivenciadas durante este período.</p>"


_SEM_BNCC = "Nenhuma habilidade da BNCC registrada para a criança no período."
_SEM_PRODUCOES = "Nenhuma produção (escrita ou desenho) analisada no período."
_TAG_HTML_RE = re.compile(r"<[^>]+>")


def _insumo_ou_ausente(texto, ausente):
    """Texto para o prompt; sem dado (vazio, "Sem registros…", "Erro…"), a frase
    que diz à IA que não há — nunca campo em branco, que ela leria como
    esquecimento do sistema."""
    limpo = _TAG_HTML_RE.sub("", texto or "").strip()
    if not limpo or limpo.startswith((
        "Sem ", "Erro ", "Não foi possível", "A análise automática", "A geração automática",
    )):
        return ausente
    return limpo


def _gerar_secao_relatos(nome_crianca, periodo, info_crianca, usuario=None, escola_id=None,
                        habilidades_bncc=None, analises_producoes=None):
    """Seção 2: Relatos individuais — busca observações e gera narrativa via IA."""
    relatos_individuais = buscar_relatos_individuais_crianca(
        nome_crianca, periodo, aluno_id=info_crianca.get('id'),
    )
    logger.debug("[RELATOS] %d relatos individuais encontrados", len(relatos_individuais))

    if not relatos_individuais:
        return "<p>Sem relatos para o período.</p>"

    observacoes_texto = "OBSERVAÇÕES DA PROFESSORA\n\n"
    for i, relato in enumerate(relatos_individuais, 1):
        data_formatada = parse_timestamp_safely(relato.get('data', ''))
        observacoes_texto += f"{i}. {data_formatada} - {relato.get('observacao', '')}\n\n"

    logger.debug("[RELATÓRIO] %d relatos individuais adicionados", len(relatos_individuais))

    turma_nome = info_crianca.get('turma_nome', 'Não informado')
    idade = info_crianca.get('idade', 'Não informada')

    try:
        # ── Categoria específica para relato individual ────────────
        prompt_template = resolver_prompt(
            "Relatórios - Relato Individual",
            escola_id=escola_id,
            fallback_arquivo="relatorio_relato_individual.txt",
        )
        prompt = _preencher_prompt(
            prompt_template,
            nome_aluno=nome_crianca,
            turma=turma_nome,
            idade=idade,
            observacoes=observacoes_texto,
            habilidades_bncc=_insumo_ou_ausente(habilidades_bncc, _SEM_BNCC),
            analises_producoes=_insumo_ou_ausente(analises_producoes, _SEM_PRODUCOES),
        )
        # Observações já embutidas no prompt -> não reenviar como mensagem.
        if _tem_placeholder(prompt_template, "observacoes"):
            mensagem_usuario = "Escreva o relato individual conforme as instruções, usando as observações acima."
        else:
            mensagem_usuario = observacoes_texto
        openai_client = get_openai_client()

        raw_content = _gerar_com_guarda_idioma(
            openai_client,
            model=GPT_MODEL,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": mensagem_usuario},
            ],
            max_completion_tokens=MAX_TOKENS,
            usuario=usuario,
            log_prefix="[OPENAI-RELATOS]",
        )

        secao_relatos = _strip_code_fences(raw_content)
        logger.debug("[OPENAI-RELATOS] análise recebida (%d caracteres)", len(secao_relatos))
    except RuntimeError as openai_config_error:
        logger.error("[OPENAI-RELATOS] configuração ausente: %s", openai_config_error)
        secao_relatos = "<p>A análise automática dos relatos está indisponível.</p>"
    except Exception:
        logger.exception("[OPENAI-RELATOS] falha na chamada da OpenAI.")
        secao_relatos = "<p>Não foi possível gerar o relato individual automaticamente neste momento.</p>"

    return secao_relatos


# Schema imposto à IA (independe do texto do prompt — inclusive dos editados no
# banco via PromptTemplate): separa as análises por modalidade para que cada uma
# viva num quadro/página próprios do relatório.
_SCHEMA_PRODUCOES = {
    "type": "json_schema",
    "json_schema": {
        "name": "analises_producoes",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "analise_escrita": {
                    "type": ["string", "null"],
                    "description": "Análise das produções de ESCRITA em HTML (só <p>, máx. 3), sem títulos. null se não houver registros de escrita.",
                },
                "analise_desenho": {
                    "type": ["string", "null"],
                    "description": "Análise das produções de DESENHO em HTML (só <p>, máx. 3), sem títulos. null se não houver registros de desenho.",
                },
            },
            "required": ["analise_escrita", "analise_desenho"],
        },
    },
}


def _analise_falhou(registro) -> bool:
    return (registro.analise_detalhada or '').lstrip().startswith('FALHA NA ANÁLISE')


def _gerar_secao_producoes(nome_crianca, aluno_id, periodo=None, usuario=None, escola_id=None):
    """Seção 3: Produções — busca registros de escrita/desenho e gera narrativa via IA.

    Uma única chamada à OpenAI (categoria "Relatórios - Produções" preservada),
    com `response_format` estruturado separando as análises por modalidade.
    Retorna um dict:

      - ``escrita`` / ``desenho``: ``{'texto': str|None, 'registro_img': registro|None}``
        — texto da modalidade + produção mais recente com imagem (o quadro da página).
      - ``fallback_texto``: blob único quando o JSON falhou, houve erro na IA ou
        não há produções (aciona a página única no layout antigo).
      - ``texto_conclusao``: insumo textual para a seção de conclusão.
    """
    # Por FK: o antigo `nome_aluno__icontains` misturava crianças de nomes
    # parecidos ("Ana" casava com "Mariana").
    registros_escrita = RegistroEscrita.objects.filter(aluno_id=aluno_id)
    registros_desenho = RegistroDesenho.objects.filter(aluno_id=aluno_id)

    # Restringe ao período do relatório (quando disponível).
    if periodo:
        data_inicio, data_fim = _calcular_datas_periodo(periodo)
        registros_escrita = registros_escrita.filter(
            criado_em__date__gte=data_inicio, criado_em__date__lte=data_fim
        )
        registros_desenho = registros_desenho.filter(
            criado_em__date__gte=data_inicio, criado_em__date__lte=data_fim
        )

    # Análise que falhou (IA fora do ar, tempo esgotado, JSON que não abriu)
    # não é insumo: o texto "FALHA NA ANÁLISE TÉCNICA" iria para a IA que
    # escreve a seção e de lá para a família. A professora vê a falha na tela
    # de produções e manda de novo.
    registros_escrita = [r for r in registros_escrita.order_by('-criado_em') if not _analise_falhou(r)]
    registros_desenho = [r for r in registros_desenho.order_by('-criado_em') if not _analise_falhou(r)]
    logger.debug("[PRODUÇÕES] %d escritas e %d desenhos no período", len(registros_escrita), len(registros_desenho))

    resultado = {
        'escrita': {'texto': None, 'registro_img': None},
        'desenho': {'texto': None, 'registro_img': None},
        'fallback_texto': None,
        'texto_conclusao': '',
    }

    if not registros_escrita and not registros_desenho:
        logger.debug("[PRODUÇÕES] nenhuma produção no período")
        resultado['fallback_texto'] = "<p>Sem produções registradas para o período.</p>"
        resultado['texto_conclusao'] = resultado['fallback_texto']
        return resultado

    com_imagem_escrita = [r for r in registros_escrita if r.arquivo_hash]
    com_imagem_desenho = [r for r in registros_desenho if r.arquivo_hash]

    # ── Insumo textual para a IA: classificações + análises detalhadas ──
    partes_texto = ["ANÁLISES DE PRODUÇÕES\n"]
    for i, registro in enumerate(registros_escrita, 1):
        data_fmt = registro.criado_em.strftime('%d/%m/%Y')
        partes_texto.append(
            f"\nESCRITA {i} ({data_fmt}) — etapa: {registro.etapa_ia or 'não informada'}\n"
            f"{registro.analise_detalhada or ''}"
        )
    for i, registro in enumerate(registros_desenho, 1):
        data_fmt = registro.criado_em.strftime('%d/%m/%Y')
        partes_texto.append(
            f"\nDESENHO {i} ({data_fmt}) — fase: {registro.fase_desenho or 'não informada'}\n"
            f"{registro.analise_detalhada or ''}"
        )
    insumo_ia = "\n".join(partes_texto)

    try:
        # ── Categoria única preservada (prompts customizados no banco seguem
        # valendo); a separação por modalidade é garantida pelo SCHEMA.
        prompts_producoes = (
            resolver_prompt(
                "Relatórios - Produções",
                escola_id=escola_id,
                fallback_arquivo="relatorio_producoes.txt",
            )
        )
        prompts_producoes = _preencher_prompt(
            prompts_producoes, nome_crianca=nome_crianca, nome_aluno=nome_crianca,
        )
        openai_client = get_openai_client()

        raw_content = _gerar_com_guarda_idioma(
            openai_client,
            model=GPT_MODEL,
            messages=[
                {"role": "system", "content": prompts_producoes},
                {"role": "user", "content": insumo_ia},
            ],
            max_completion_tokens=MAX_TOKENS,
            usuario=usuario,
            response_format=_SCHEMA_PRODUCOES,
            log_prefix="[OPENAI-PRODUCOES]",
        )

        bruto = _strip_code_fences(raw_content)
        logger.debug("[OPENAI-PRODUCOES] análise recebida (%d caracteres)", len(bruto))
        try:
            dados = json.loads(bruto)
            resultado['escrita']['texto'] = (dados.get('analise_escrita') or '').strip() or None
            resultado['desenho']['texto'] = (dados.get('analise_desenho') or '').strip() or None
            if not resultado['escrita']['texto'] and not resultado['desenho']['texto']:
                raise ValueError("JSON sem nenhuma análise preenchida")
        except (ValueError, TypeError) as parse_error:
            # Degradação graciosa: blob único na página antiga.
            logger.warning("[PRODUÇÕES] resposta fora do schema (%s); usando fallback de página única.", parse_error)
            resultado['fallback_texto'] = bruto
    except RuntimeError as openai_config_error:
        logger.error("[OPENAI] configuração ausente para produções: %s", openai_config_error)
        resultado['fallback_texto'] = "<p>Não foi possível gerar a análise das produções.</p>"
    except Exception:
        logger.exception("[OPENAI] falha ao analisar as produções.")
        resultado['fallback_texto'] = "<p>Não foi possível gerar a análise das produções.</p>"

    # ── Quadros: produção mais recente com imagem de cada modalidade
    # (só quando a análise estruturada daquela modalidade existe). ──
    if resultado['fallback_texto'] is None:
        if resultado['escrita']['texto'] and com_imagem_escrita:
            resultado['escrita']['registro_img'] = com_imagem_escrita[0]
        if resultado['desenho']['texto'] and com_imagem_desenho:
            resultado['desenho']['registro_img'] = com_imagem_desenho[0]

    # ── Insumo para a conclusão ──
    if resultado['fallback_texto'] is not None:
        resultado['texto_conclusao'] = resultado['fallback_texto']
    else:
        partes = []
        if resultado['escrita']['texto']:
            partes.append(f"ANÁLISE DE ESCRITA:\n{resultado['escrita']['texto']}")
        if resultado['desenho']['texto']:
            partes.append(f"ANÁLISE DE DESENHO:\n{resultado['desenho']['texto']}")
        resultado['texto_conclusao'] = "\n\n".join(partes)

    return resultado


def _gerar_secao_bncc(crianca_id, periodo, escola_id=None):
    """Seção 4: BNCC — agrega observações e formata HTML com bolinhas coloridas."""
    secao_texto = ""
    perguntas_bncc = []
    respostas_sim_por_pergunta = Counter()

    try:
        logger.debug(
            "Inicio da seção BNCC para relatório.",
            extra={"crianca_id": str(crianca_id), "periodo": periodo},
        )

        if not crianca_id:
            raise Exception("crianca_id não disponível")

        logger.info(
            "Iniciando agregação BNCC para relatório.",
            extra={"crianca_id": str(crianca_id), "tipo_periodo": periodo.get('type')},
        )

        data_inicio, data_fim = _calcular_datas_periodo(periodo)

        logger.info(
            "Buscando registros de observação no Postgres para BNCC.",
            extra={"crianca_id": str(crianca_id), "data_inicio": str(data_inicio), "data_fim": str(data_fim)},
        )

        # `todos` (sem tenant) + filtro manual: perguntas oficiais (escola nula)
        # OU customizadas pela escola do aluno — o TenantManager esconderia
        # as oficiais de quem tem escopo de escola.
        perguntas_bncc = list(
            Pergunta.todos.filter(ativa=True)
            .filter(filtro_oficiais_e_da_escola(escola_id))
            .select_related('habilidade_bncc')
        )

        registros_queryset = RegistroObservacao.objects.filter(
            aluno_id=crianca_id,
            data_observacao__gte=data_inicio,
            data_observacao__lte=data_fim,
        )
        registros_sim = registros_queryset.filter(resposta__iexact='sim').values_list('pergunta_id', flat=True)
        respostas_sim_por_pergunta = Counter(registros_sim)

        if perguntas_bncc and respostas_sim_por_pergunta:
            secao_texto = "ANÁLISE DE HABILIDADES BNCC\n\n"

            for pergunta in perguntas_bncc:
                respostas_sim = respostas_sim_por_pergunta.get(pergunta.id, 0)

                if respostas_sim == 0:
                    status_resposta = "NENHUMA"
                elif respostas_sim == 1:
                    status_resposta = "uma vez"
                elif respostas_sim == 2:
                    status_resposta = "duas vezes"
                else:
                    status_resposta = f"{respostas_sim} vezes"

                codigo = pergunta.habilidade_bncc.codigo if pergunta.habilidade_bncc_id else ''
                secao_texto += f"({codigo}) {pergunta.pergunta or ''}: {status_resposta}\n"

            logger.info(
                "Perguntas BNCC agregadas no relatório.",
                extra={"total_perguntas": len(perguntas_bncc), "crianca_id": str(crianca_id)},
            )
        else:
            secao_texto = "<p>Sem registros de observação BNCC para o período especificado.</p>"
            logger.info(
                "Sem dados suficientes para análise BNCC.",
                extra={"crianca_id": str(crianca_id)},
            )

    except Exception:
        logger.exception("Erro ao buscar dados de observação BNCC.")
        secao_texto = "<p>Erro ao recuperar dados de observação BNCC.</p>"

    logger.debug(
        "Resumo BNCC gerado para IA.",
        extra={"tamanho_texto": len(secao_texto)},
    )

    secao_bncc_html = _formatar_secao_bncc_html(perguntas_bncc, respostas_sim_por_pergunta)
    return secao_texto, secao_bncc_html


# Assinatura da IA que sobrou de prompts antigos (inclusive editados via banco):
# remove um <p> final de despedida/assinatura para não duplicar com o bloco fixo.
_ASSINATURA_IA_RE = re.compile(
    r'<p>(?:(?!</p>).)*?(?:Com carinho|class="nome"|class="cargo")(?:(?!</p>).)*(?:</p>)?\s*$',
    re.IGNORECASE | re.DOTALL,
)


# Parágrafo de despedida/assinatura escrito pela IA, em QUALQUER posição.
# A regex acima só pega o último parágrafo; quando a IA emite algo depois da
# assinatura (visto em relatório real: uma linha solta vinda do planejamento),
# a assinatura dela sobrevivia e o PDF saía com duas — a da IA grudada,
# "Com carinho,SilvanaProfessora da Turma", e logo abaixo a do backend.
_PARAGRAFO_RE = re.compile(r'<p\b[^>]*>.*?</p>', re.IGNORECASE | re.DOTALL)
_DESPEDIDA_RE = re.compile(
    r'^\s*(com carinho|com afeto|com amor|carinhosamente|atenciosamente|'
    r'um abraço|abraços|um grande abraço)\b',
    re.IGNORECASE,
)
# Despedida de verdade é curta. Parágrafo longo que por acaso começa com
# "Com carinho, ela cuidou das plantas..." é conteúdo e fica.
_DESPEDIDA_MAX_CARACTERES = 120


def _remover_assinaturas_da_ia(html):
    """Tira do corpo da carta todo parágrafo que seja assinatura/despedida da
    IA — a assinatura oficial é anexada pelo backend (_montar_assinatura_html).

    Critérios, em ordem de certeza:
      - usa `class="nome"`/`class="cargo"`: marcação do prompt antigo, que só
        existe em assinatura;
      - texto visível curto que começa com uma fórmula de despedida.
    """
    def _talvez_remover(m):
        paragrafo = m.group(0)
        if re.search(r'class="(nome|cargo)"', paragrafo, re.IGNORECASE):
            return ''
        texto = re.sub(r'<[^>]+>', ' ', paragrafo)
        texto = re.sub(r'\s+', ' ', texto).strip()
        if len(texto) <= _DESPEDIDA_MAX_CARACTERES and _DESPEDIDA_RE.match(texto):
            return ''
        return paragrafo

    return _PARAGRAFO_RE.sub(_talvez_remover, html or '')


def _montar_assinatura_html(nome_professora):
    """Bloco fixo de assinatura da conclusão — montado pelo backend, e não pela
    IA, porque o prompt antigo pedia <span class="nome">/<span class="cargo">
    (sem CSS correspondente e com HTML malformado), o que rendia
    "Com carinho,LeticiaProfessora da Turma" tudo colado. As classes abaixo já
    têm estilo em relatorio-editor.css / static/pdf/relatorio.css."""
    return (
        '<div class="conclusao-assinatura"><div class="assinatura-linha">'
        '<div class="assinatura-despedida">Com carinho,</div>'
        f'<div class="assinatura-nome">{nome_professora}</div>'
        '<div class="assinatura-cargo">Professora da Turma</div>'
        '</div></div>'
    )


def _gerar_secao_conclusao(
    nome_crianca, secao_relatos, secao_producoes, secao_registros_observacao,
    analise_completa, turma_nome, nome_professora, idade, usuario=None, escola_id=None,
):
    """Seção final: Conclusão da Professora — carta à família via IA.

    O texto vem da IA; a assinatura é SEMPRE anexada pelo backend
    (`_montar_assinatura_html`), com limpeza defensiva caso um prompt antigo
    (ex.: editado no banco) ainda faça a IA emitir a própria assinatura."""
    # ── Categoria específica para conclusão ────────────────────────
    template_prompt = resolver_prompt(
        "Relatórios - Conclusão",
        escola_id=escola_id,
        fallback_arquivo="relatorio_conclusao.txt",
    )

    # Insumos "sem dado" (ex.: "<p>Sem registros de observação BNCC...</p>",
    # "<p>Erro ao recuperar...</p>") viram uma frase explícita para a IA,
    # como já acontecia no relato.
    relato_ia = _insumo_ou_ausente(secao_relatos, "Sem relatos individuais registrados no período.")
    atividades_ia = _insumo_ou_ausente(analise_completa, "Sem planejamentos registrados no período.")
    bncc_ia = _insumo_ou_ausente(secao_registros_observacao, _SEM_BNCC)
    producoes_ia = _insumo_ou_ausente(secao_producoes, _SEM_PRODUCOES)

    prompt = _preencher_prompt(
        template_prompt,
        nome_aluno=nome_crianca,
        turma=turma_nome,
        idade=idade,
        nome_professora=nome_professora,
        relato_individual=relato_ia,
        habilidades_bncc=bncc_ia,
        analises_producoes=producoes_ia,
        atividades=atividades_ia,
    )

    # Só manda no contexto o que o prompt ainda não embutiu (antes o relato
    # ia duas vezes: no {relato_individual} e no bloco abaixo).
    blocos = [f"Nome da criança: {nome_crianca}"]
    if not _tem_placeholder(template_prompt, "relato_individual"):
        blocos.append(f"--- RELATO INDIVIDUAL ---\n{relato_ia}")
    if not _tem_placeholder(template_prompt, "atividades"):
        blocos.append(f"--- O QUE VIVEMOS JUNTOS ---\n{atividades_ia}")
    if not _tem_placeholder(template_prompt, "habilidades_bncc"):
        blocos.append(f"--- HABILIDADES BNCC ---\n{bncc_ia}")
    if not _tem_placeholder(template_prompt, "analises_producoes"):
        blocos.append(f"--- ANÁLISES DE PRODUÇÕES ---\n{producoes_ia}")
    contexto = "\n\n".join(blocos) + "\n"

    assinatura = _montar_assinatura_html(nome_professora)

    try:
        openai_client = get_openai_client()

        raw_content = _gerar_com_guarda_idioma(
            openai_client,
            model=GPT_MODEL,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": contexto},
            ],
            max_completion_tokens=MAX_TOKENS,
            usuario=usuario,
            log_prefix="[OPENAI-CONCLUSAO]",
        )

        secao_conclusao = _strip_code_fences(raw_content)
        logger.debug("[OPENAI-CONCLUSAO] análise recebida (%d caracteres)", len(secao_conclusao))
        # Remove assinatura/despedida que a IA ainda possa ter emitido — em
        # qualquer posição, não só no fim (ver _remover_assinaturas_da_ia)...
        secao_conclusao = _remover_assinaturas_da_ia(secao_conclusao)
        secao_conclusao = _ASSINATURA_IA_RE.sub("", secao_conclusao).rstrip()
        if not secao_conclusao:
            logger.warning("[OPENAI-CONCLUSAO] resposta vazia da IA.")
            secao_conclusao = "<p>Não foi possível gerar a conclusão automaticamente neste momento.</p>"
        # ...e anexa o bloco fixo, estilizado pelo CSS do relatório.
        return secao_conclusao + assinatura
    except RuntimeError as openai_config_error:
        logger.error("[OPENAI] configuração ausente para conclusão: %s", openai_config_error)
        return "<p>Não foi possível gerar a conclusão.</p>" + assinatura
    except Exception:
        # Antes devolvia "" — o relatório saía sem conclusão E sem assinatura.
        logger.exception("[OPENAI] falha ao gerar a conclusão.")
        return "<p>Não foi possível gerar a conclusão automaticamente neste momento.</p>" + assinatura


def _dados_cabecalho(info_crianca) -> dict:
    """Dados do cabeçalho/capa do relatório: nome, CNPJ, contato e logo.

    Texto vem da ESCOLA do aluno (a unidade), com fallback campo a campo para a
    INSTITUIÇÃO (a mantenedora) quando a escola não tem o dado preenchido.
    O logo só existe na instituição e passa por `get_logo_url`, que renova a
    URL pré-assinada do S3 — `logo_url` salvo no banco expira em ~1h.

    Tudo sai escapado: estes valores entram em HTML que o Chromium do
    report_generator renderiza.
    """
    vazio = {'escola_nome': '', 'escola_cnpj': '', 'escola_contato': '', 'logo_escola_html': ''}

    escola = None
    if info_crianca.get('escola_id'):
        escola = (
            Escola.objects.select_related('instituicao')
            .filter(id=info_crianca['escola_id'])
            .first()
        )
    inst = escola.instituicao if escola else None
    if inst is None and info_crianca.get('instituicao_id'):
        inst = Instituicao.objects.filter(id=info_crianca['instituicao_id']).first()
    if escola is None and inst is None:
        return vazio

    def campo(nome):
        valor = getattr(escola, nome, '') if escola else ''
        return valor or (getattr(inst, nome, '') if inst else '') or ''

    nome = campo('nome')
    cnpj = campo('cnpj')
    cidade, estado = campo('cidade'), campo('estado')

    partes_contato = []
    if campo('endereco'):
        partes_contato.append(escape(campo('endereco')))
    if cidade:
        partes_contato.append(escape(f'{cidade} — {estado}' if estado else cidade))
    if campo('telefone'):
        partes_contato.append(f"Tel: {escape(campo('telefone'))}")

    logo_html = ''
    logo_url = get_logo_url(inst) if inst else None
    if logo_url:
        logo_html = f'<img src="{escape(logo_url)}" alt="{escape(nome)}">'

    return {
        'escola_nome': escape(nome),
        'escola_cnpj': f'CNPJ: {escape(cnpj)}' if cnpj else '',
        'escola_contato': ' | '.join(partes_contato),
        'logo_escola_html': logo_html,
    }


def montar_pagina_relatorio(icone, titulo, corpo_html, *, logo_escola_html='',
                            escola_nome='', linha_identificacao=''):
    """Uma `.pagina` A4 completa (cabeçalho, seção, rodapé).

    É a unidade que o paginador da impressão (api/static/pdf/paginacao.js)
    mede e, quando passa da folha, clona para a continuação — então esta
    marcação é contrato com ele: `.pagina` > `.header-escola` ... `.secao-header
    h2` + `.secao-body` ... `.rodape`. No nível do módulo (e não aninhada em
    gerar_relatorio_com_ia) para o teste de paginação contra o renderizador de
    verdade montar exatamente a mesma página que a produção.

    O corpo passa por `fechar_html`: é onde entra o texto da IA, e uma tag
    cortada nele (`</final` sem `>`) já aninhou o relatório inteiro dentro de
    uma seção. Nenhum corpo sai daqui desequilibrado.
    """
    corpo_html = fechar_html(corpo_html)
    return (
        '<div class="pagina">'
        '<div class="barra-topo"></div>'
        '<div class="header-escola">'
        f'<div class="logo-escola">{logo_escola_html}</div>'
        '<div class="escola-info">'
        f'<h1>{escola_nome}</h1>'
        f'<p>{linha_identificacao}</p>'
        '</div>'
        '</div>'
        '<div class="conteudo">'
        '<div class="secao sec-producoes">'
        f'<div class="secao-header"><span class="icone">{icone}</span><h2>{titulo}</h2></div>'
        f'<div class="secao-body">{corpo_html}</div>'
        '</div>'
        '</div>'
        '<div class="rodape">'
        '<span class="rodape-nota">💫 Relatório elaborado com base em observações sistemáticas e análise do desenvolvimento integral da criança.</span>'
        '<span class="rodape-nara">NARAEDU • naraeducacional.com</span>'
        '</div>'
        '<div class="barra-rodape"></div>'
        '</div>'
    )


def gerar_relatorio_com_ia(nome_crianca, dados_estudante, periodo, crianca_id, nome_professora='Professora', usuario=None):
    """
    Gerar relatório usando IA com base nos dados do estudante.
    Orquestra as seções: atividades, relatos individuais, produções, BNCC e conclusão.

    O RelatorioTemplate ativo da instituição do usuário (quando existe) define
    a capa por inteiro — modelo, textos, cores, elementos visíveis e
    tipografia — renderizada por `renderizar_capa` (api/services/relatorio_capa.py,
    que monta o HTML condicionalmente em Python; não usa mais os antigos
    relatorio_capa_*.html). A implementação espelha renderCapa() em
    client/src/lib/templateRelatorioShared.js — qualquer mudança de comportamento
    aqui provavelmente também vale lá.

    Campos de config lidos (todos com fallback seguro se ausentes/malformados):
      - items_sumario: título, ordem e visibilidade de cada seção do corpo
      - tipoRelatorio / tituloRelatorio / fraseDestaque: textos da capa
      - elementos: os 9 toggles de "Textos e elementos visíveis"
      - imagemPrincipal: 'mascote' | 'nenhuma' (só mascote/essencial)
      - alinhamento: 'left' | 'center' (só natureza/essencial)
      - paleta / fonteCombo / corTexto / nomeTamanho / tituloTamanho: aplicados
        no CSS por relatorio_pdf.py, não aqui

    Sem template ativo (ou instituição não resolvida), usa a capa 'classico'
    e todos os valores padrão do sistema.
    """
    # Resolve a instituição (usada para o template de relatório ativo).
    # A instituição vem do ALUNO (não do usuário): perfis globais (superadmin,
    # suporte) não têm instituição, e mesmo assim o relatório precisa usar o
    # template e os prompts da instituição da criança.
    info_crianca = dados_estudante.get('info_crianca', {})
    inst_aluno = info_crianca.get('instituicao_id')
    inst_usuario = getattr(usuario, 'instituicao_id', None) if usuario else None
    instituicao_id = str(inst_aluno or inst_usuario) if (inst_aluno or inst_usuario) else None
    # Prompt personalizado é POR ESCOLA — a do aluno.
    escola_id = str(info_crianca['escola_id']) if info_crianca.get('escola_id') else None

    # RelatorioTemplate pertence a uma ESCOLA (unique escola+modelo). Filtrar só
    # por instituição devolvia o template ativo de qualquer escola da rede —
    # para um admin, o aluno da escola B podia sair com a capa da escola A.
    template_ativo = None
    escola_id_aluno = info_crianca.get('escola_id')
    if escola_id_aluno:
        template_ativo = (
            RelatorioTemplate.objects
            .filter(escola_id=escola_id_aluno, ativo=True)
            .order_by('-atualizado_em')
            .first()
        )
    elif instituicao_id:
        template_ativo = (
            RelatorioTemplate.objects
            .filter(instituicao_id=instituicao_id, ativo=True)
            .order_by('-atualizado_em')
            .first()
        )
    items_sumario = _normalizar_items_sumario(template_ativo)
    elementos = _normalizar_elementos(template_ativo)

    # config é JSON sem schema garantido no banco — nunca confia direto.
    config_template = (template_ativo.config or {}) if template_ativo and isinstance(template_ativo.config, dict) else {}

    def _texto_config(chave, padrao):
        valor = config_template.get(chave)
        return valor.strip() if isinstance(valor, str) and valor.strip() else padrao

    tipo_relatorio = _texto_config('tipoRelatorio', 'Relatório Individual')
    titulo_relatorio = _texto_config('tituloRelatorio', 'Relatório de Acompanhamento da Aprendizagem')
    # frase_destaque não tem um único padrão (varia por modelo — mascote vs.
    # natureza), então passa None quando vazio e deixa o default específico
    # de cada _renderizar_capa_* em relatorio_capa.py resolver.
    frase_destaque = config_template.get('fraseDestaque')
    frase_destaque = frase_destaque.strip() if isinstance(frase_destaque, str) and frase_destaque.strip() else None

    imagem_principal = config_template.get('imagemPrincipal')
    if imagem_principal not in ('mascote', 'nenhuma'):
        imagem_principal = 'nenhuma'

    alinhamento = config_template.get('alinhamento')
    if alinhamento not in ('left', 'center'):
        alinhamento = None

    if periodo.get('descricao'):
        periodo_label = periodo['descricao']
    elif periodo.get('type') == 'bimestre' and periodo.get('bimester'):
        periodo_label = f"{periodo.get('bimester')}o Bimestre"
    else:
        periodo_label = "Período não especificado"

    num_observacoes = len(dados_estudante.get('observacoes', []))
    num_producoes = len(dados_estudante.get('producoes', []))
    turma_nome = info_crianca.get('turma_nome', 'Não informado')
    idade = info_crianca.get('idade', '')

    # As seções são SEMPRE geradas via IA, mesmo que o coordenador tenha
    # ocultado alguma no template — a conclusão usa o texto de todas como
    # contexto (secao_relatos, producoes, secao_registros_observacao), então
    # ocultar uma seção não deve empobrecer a análise das outras.
    analise_completa = _gerar_secao_atividades(info_crianca, periodo, nome_crianca, usuario=usuario, escola_id=escola_id)
    # Produções e BNCC ANTES do relato: o prompt do relato cruza as
    # observações com as duas ({habilidades_bncc}, {analises_producoes}).
    producoes = _gerar_secao_producoes(nome_crianca, crianca_id, periodo=periodo, usuario=usuario, escola_id=escola_id)
    secao_registros_observacao, secao_bncc = _gerar_secao_bncc(crianca_id, periodo, escola_id=info_crianca.get('escola_id'))
    secao_relatos = _gerar_secao_relatos(
        nome_crianca, periodo, info_crianca, usuario=usuario, escola_id=escola_id,
        habilidades_bncc=secao_registros_observacao,
        analises_producoes=producoes['texto_conclusao'],
    )
    secao_conclusao = _gerar_secao_conclusao(
        nome_crianca, secao_relatos, producoes['texto_conclusao'], secao_registros_observacao,
        analise_completa, turma_nome, nome_professora, idade or 'Não informada', usuario=usuario, escola_id=escola_id,
    )
    secao_portfolio = _formatar_secao_portfolio_html(dados_estudante.get('producoes', []))
    data_geracao = timezone.now().strftime('%d/%m/%Y')

    cabecalho = _dados_cabecalho(info_crianca)
    escola_nome = cabecalho['escola_nome']
    escola_cnpj = cabecalho['escola_cnpj']
    escola_contato = cabecalho['escola_contato']
    logo_escola_html = cabecalho['logo_escola_html']

    # ── Páginas montadas aqui, e não no template, para que páginas ocultadas
    # pelo coordenador (items_sumario) simplesmente não existam no relatório. ──
    def _pagina_relatorio(icone, titulo, corpo_html):
        """Uma `.pagina` A4 completa (header/rodapé) com uma seção `sec-producoes`."""
        return montar_pagina_relatorio(
            icone, titulo, corpo_html,
            logo_escola_html=logo_escola_html,
            escola_nome=escola_nome,
            linha_identificacao=f'{nome_crianca} &nbsp;|&nbsp; {periodo_label} &nbsp;|&nbsp; {tipo_relatorio}',
        )

    def _quadro_producao(registro, texto, rotulo, emoji):
        """Quadro da análise: imagem da produção CENTRALIZADA no topo (na
        orientação original, com altura limitada pelo CSS para não estourar a
        página A4) e o texto da análise abaixo, em largura total."""
        img_html = ''
        if registro is not None:
            data_fmt = registro.criado_em.strftime('%d/%m/%Y')
            img_html = (
                '<div class="producao-quadro-img">'
                f'<img src="/api/arquivo/{registro.arquivo_hash}/" alt="{rotulo}" />'
                f'<span class="producao-galeria-label">{emoji} {rotulo} — {data_fmt}</span>'
                '</div>'
            )
        return (
            f'<div class="producao-quadro">{img_html}'
            f'<div class="producao-quadro-texto">{texto}</div></div>'
        )

    # Título de "produções" pode ter sido customizado no items_sumario — os
    # sufixos de escrita/desenho continuam fixos (são sub-modalidades).
    titulo_producoes = next((i['titulo'] for i in items_sumario if i['chave'] == 'producoes'), _TITULOS_PADRAO['producoes'])

    if producoes['fallback_texto'] is not None:
        # Sem separação por modalidade (erro/JSON inválido/sem produções):
        # página única no layout antigo.
        paginas_analise_producoes = _pagina_relatorio(
            '🎨', titulo_producoes, producoes['fallback_texto']
        )
    else:
        paginas_analise_producoes = ''
        if producoes['escrita']['texto']:
            paginas_analise_producoes += _pagina_relatorio(
                '✏️', f'{titulo_producoes} — Escrita',
                _quadro_producao(producoes['escrita']['registro_img'], producoes['escrita']['texto'], 'Escrita', '✏️'),
            )
        if producoes['desenho']['texto']:
            paginas_analise_producoes += _pagina_relatorio(
                '🎨', f'{titulo_producoes} — Desenho',
                _quadro_producao(producoes['desenho']['registro_img'], producoes['desenho']['texto'], 'Desenho', '🎨'),
            )

    # ── Monta as páginas do corpo na ordem/visibilidade do items_sumario ──
    corpo_por_chave = {
        'atividades': analise_completa,
        'relato': secao_relatos,
        'portfolio': secao_portfolio,
        'bncc': secao_bncc,
        'conclusao': secao_conclusao,
    }

    paginas_corpo = []
    for item in items_sumario:
        if not item['visivel']:
            continue
        chave = item['chave']
        if chave == 'producoes':
            if paginas_analise_producoes:
                paginas_corpo.append(paginas_analise_producoes)
            continue
        corpo_html = corpo_por_chave.get(chave)
        if corpo_html is None:
            continue
        paginas_corpo.append(_pagina_relatorio(_ICONES_SECAO[chave], item['titulo'], corpo_html))

    paginas_corpo_html = ''.join(paginas_corpo)

    # ── Capa: escolhida pelo modelo do template ativo (ou 'classico' por
    # padrão) e renderizada por api/services/relatorio_capa.py. ──
    modelo = template_ativo.modelo if template_ativo else 'classico'

    # foto_crianca_html: só os modelos 'memorias'/'natureza' exibem foto real
    # na capa (RelatorioTemplate.suporta_foto()), e só quando o template
    # ativo tem usa_foto_aluno=True.
    foto_crianca_html = ''
    if template_ativo and template_ativo.usa_foto_aluno and modelo == 'memorias':
        crianca_obj = Aluno.objects.filter(id=crianca_id).first()
        if crianca_obj:
            foto_url_atual = get_foto_url(crianca_obj)
            if foto_url_atual:
                foto_crianca_html = (
                    f'<img src="{foto_url_atual}" alt="{nome_crianca}" '
                    'style="width:100%;height:100%;object-fit:cover;" />'
                )
    ano_letivo = periodo.get('year') or str(timezone.now().year)

    capa_html = renderizar_capa(modelo, {
        'nome_crianca': nome_crianca,
        'periodo_label': periodo_label,
        'turma_nome': turma_nome,
        'data_geracao': data_geracao,
        'idade': idade,
        'escola_nome': escola_nome,
        'escola_cnpj': escola_cnpj,
        'escola_contato': escola_contato,
        'logo_escola_html': logo_escola_html,
        'items_sumario': items_sumario,
        'foto_crianca_html': foto_crianca_html,
        'ano_letivo': ano_letivo,
        'professora_nome': nome_professora,
        'tipo_relatorio': tipo_relatorio,
        'titulo_relatorio': titulo_relatorio,
        'frase_destaque': frase_destaque,
        'elementos': elementos,
        'imagem_principal': imagem_principal,
        'alinhamento': alinhamento,
    })

    corpo_source = _carregar_prompt("relatorio_template.html")
    corpo_html = corpo_source.format(paginas_corpo=paginas_corpo_html)

    conteudo = capa_html + corpo_html

    return {
        'content': conteudo,
        'suggestions': [
            'Considere adicionar exemplos especificos de situacoes observadas.',
            'Inclua informacoes sobre projetos especificos desenvolvidos no periodo.',
            'Mencione a participacao da familia no processo educativo.',
            'Descreva estrategias pedagogicas que foram especialmente eficazes.',
            'Adicione metas especificas para o proximo periodo.',
        ],
        'metadata': {
            'aiModel': 'Sistema Nara IA - v1.0 (Mock)',
            'generationTime': '2m 30s',
            'basedOnObservations': num_observacoes,
            'basedOnProductions': num_producoes,
            'dataQuality': 'Alta' if num_observacoes > 10 else 'Media' if num_observacoes > 5 else 'Baixa',
            'templateAtivo': str(template_ativo.id) if template_ativo else None,
            'templateConfig': config_template if template_ativo else None,
            'modeloCapa': modelo,
        },
    }

# Captura <img ... src="..."> ou <img ... src='...'>; o group(3) é o valor do src.
_IMG_SRC_PATTERN = re.compile(
    r'(<img\b[^>]*?\bsrc\s*=\s*)(["\'])(.*?)\2',
    re.IGNORECASE | re.DOTALL,
)


def refresh_img_urls_in_html(html):
    """Re-assina URLs S3 pré-assinadas em `<img src="...">` dentro do HTML.

    Usado na listagem de um relatório para que o browser possa carregar as
    imagens diretamente do S3 (sem round-trip extra pelo `/proxy-imagem/`
    por imagem). `refresh_presigned_url` já retorna a URL original quando
    ela não pertence ao bucket configurado ou quando S3 não está configurado,
    então o rewrite é seguro para HTML misto e para ambientes sem S3.
    """
    if not html:
        return html

    def _replace(match):
        prefix, quote, src = match.group(1), match.group(2), match.group(3)
        if not src or src.startswith('data:'):
            return match.group(0)
        refreshed = refresh_presigned_url(src) or src
        return f'{prefix}{quote}{refreshed}{quote}'

    return _IMG_SRC_PATTERN.sub(_replace, html)