"""Renderização da capa do relatório, uma implementação por modelo de
RelatorioTemplate. Único ponto de entrada: renderizar_capa(modelo, contexto).

A partir desta versão, o HTML é montado inteiramente em Python (arrays +
join, igual ao renderCapa em client/src/lib/templateRelatorioShared.js) —
os elementos da capa são condicionais (items_sumario, config.elementos),
o que não dava pra fazer só com placeholders de texto num .format() fixo.
As duas implementações (esta e a do frontend) precisam continuar batendo:
qualquer mudança aqui provavelmente também vale lá, e vice-versa.
"""

import re

MASCOTE_IMG_URL = '/static/mascote-nara.png'
_RODAPE_NARA_HTML = '<span class="rodape-nara">NARAEDU • naraeducacional.com</span>'

_TIPO_RELATORIO_PADRAO = 'Relatório Individual'
_TITULO_RELATORIO_PADRAO = 'Relatório de Acompanhamento da Aprendizagem'
_FRASE_DESTAQUE_PADRAO = {
    'mascote': 'Meu caminho de aprendizagens',
    'natureza': 'Pequenas descobertas, grandes aprendizagens',
}

# Bate com ELEMENTOS_VISIVEIS_PADRAO em templateRelatorioShared.js.
ELEMENTOS_VISIVEIS_PADRAO = {
    'age': True,
    'teacher': True,
    'date': True,
    'cnpj': True,
    'contact': True,
    'naraLogo': True,
    'mascot': False,
    'content': True,
    'footerPhrase': True,
}


def _el(contexto):
    """Mescla os elementos vindos do contexto sobre o padrão — defensivo,
    mesmo que gerar_relatorio_com_ia já normalize antes de chamar aqui."""
    return {**ELEMENTOS_VISIVEIS_PADRAO, **(contexto.get('elementos') or {})}


def _abreviar_nome_composto(nome, limite_caracteres=20):
    """Abrevia os nomes do meio (mantém primeiro e último por extenso) até
    caber no limite de caracteres — evita que nomes compostos longos
    quebrem linha na capa. Ex., limite=20:
        "Amélia Medeiros Araújo Soares" -> "Amélia M. A. Soares"

    Preposições/conectivos em minúsculo ("de", "da", "dos", "e"...) não são
    abreviados — já são curtos, e "d." fica estranho.

    limite_caracteres varia por modelo (fonte e largura do container
    diferem) — calibrado a partir do CSS de cada capa em
    client/src/styles/relatorio-editor.css; ajustar aqui se algum nome
    real ainda estourar visualmente em algum modelo.
    """
    nome = (nome or '').strip()
    partes = nome.split()
    if len(partes) <= 2 or len(nome) <= limite_caracteres:
        return nome

    primeiro, ultimo = partes[0], partes[-1]
    meio = partes[1:-1]

    def montar(indices_abreviados):
        pedacos = [primeiro]
        for i, parte in enumerate(meio):
            if i in indices_abreviados and not parte.islower():
                pedacos.append(f'{parte[0]}.')
            else:
                pedacos.append(parte)
        pedacos.append(ultimo)
        return ' '.join(pedacos)

    # abrevia progressivamente da esquerda pra direita, só o suficiente
    # pra caber — nomes só um pouco longos perdem só um nome do meio.
    abreviados = set()
    candidato = montar(abreviados)
    for i, parte in enumerate(meio):
        if len(candidato) <= limite_caracteres:
            break
        if not parte.islower():
            abreviados.add(i)
            candidato = montar(abreviados)

    return candidato


def _mascote_img_html():
    return f'<img src="{MASCOTE_IMG_URL}" alt="Mascote NARA" />'


def _rodape_classico_essencial(footer_phrase_html, el, nara_html):
    # naraLogo/footerPhrase desativados a pedido — mesmo padrão de
    # templateRelatorioShared.js (código comentado, não só default).
    partes = []
    # if el['footerPhrase'] and footer_phrase_html:
    #     partes.append(footer_phrase_html)
    # if el['naraLogo']:
    #     partes.append(nara_html)
    return ''.join(partes)


# ---------------- Ícones e decorações SVG (fiéis ao protótipo/frontend) ----------------
# Precisam bater byte-a-byte (estrutura, não indentação) com os equivalentes
# _ICONE_*/_*_SVG em client/src/lib/templateRelatorioShared.js.

_ICONE_TURMA = '<svg width="15" height="15" viewBox="0 0 24 24" fill="none"><circle cx="9" cy="9" r="3.2" stroke="currentColor" stroke-width="1.8"/><circle cx="16.5" cy="10" r="2.4" stroke="currentColor" stroke-width="1.6"/><path d="M3.5 18.5c.6-3 3-4.6 5.5-4.6s4.9 1.6 5.5 4.6" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/><path d="M16 14.2c2 .3 3.7 1.7 4.2 4.3" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>'

_ICONE_PROFESSORA = '<svg width="15" height="15" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="8.4" r="3.6" stroke="currentColor" stroke-width="1.8"/><path d="M5 19.4c.8-3.6 3.6-5.4 7-5.4s6.2 1.8 7 5.4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>'

_ICONE_PERIODO = '<svg width="15" height="15" viewBox="0 0 24 24" fill="none"><rect x="3.4" y="5" width="17.2" height="15.5" rx="3" stroke="currentColor" stroke-width="1.8"/><path d="M3.4 9.6h17.2M8 3.4v3.4M16 3.4v3.4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/><circle cx="8.4" cy="14" r="1.2" fill="currentColor"/><circle cx="12" cy="14" r="1.2" fill="currentColor"/><circle cx="15.6" cy="14" r="1.2" fill="currentColor"/></svg>'

_ICONE_ANO = '<svg width="15" height="15" viewBox="0 0 24 24" fill="none"><path d="M12 3.6l2.5 5.3 5.7.7-4.2 4 1.1 5.7-5.1-2.9-5.1 2.9 1.1-5.7-4.2-4 5.7-.7z" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/></svg>'

_ICONE_DATA = '<svg width="15" height="15" viewBox="0 0 24 24" fill="none"><rect x="3.4" y="5" width="17.2" height="15.5" rx="3" stroke="currentColor" stroke-width="1.8"/><path d="M3.4 9.6h17.2M8 3.4v3.4M16 3.4v3.4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/><path d="M8 14.4h8" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>'

_ICONE_CIRCULO_IDADE = '<svg width="15" height="15" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="8.4" stroke="currentColor" stroke-width="1.8"/><path d="M9 10.6v.2M15 10.6v.2" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"/><path d="M9 14.6c1.8 1.7 4.2 1.7 6 0" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>'

_ICONE_HEART_SEPARADOR = '<svg viewBox="0 0 24 24" fill="none"><path d="M12 20c-5-3.5-9-7-9-11.2C3 5.6 5.3 3.4 8 3.4c1.9 0 3.3 1 4 2.4.7-1.4 2.1-2.4 4-2.4 2.7 0 5 2.2 5 5.4C21 13 17 16.5 12 20z" fill="var(--roxo)" opacity=".65"/></svg>'

_SPRIG_SVG = '<svg viewBox="0 0 40 90" fill="none"><path d="M20 88V16" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"/><path d="M20 60c-3-14-12-20-17-19 0 13 7 21 17 19zM20 44c3-14 12-20 17-19 0 13-7 21-17 19zM20 28c-3-12-10-16-15-15 0 11 6 17 15 15z" fill="currentColor" opacity=".85"/></svg>'

_LEAF_SVG = '''
  <svg class="capa-memorias-leaf" viewBox="0 0 120 200" fill="none" aria-hidden="true">
    <path d="M60 196V44" stroke="var(--roxo)" stroke-width="4" stroke-linecap="round"/>
    <path d="M60 150c-8-30-30-42-52-38 2 30 24 48 52 38zM60 116c8-30 30-42 52-38-2 30-24 48-52 38zM60 84c-8-28-26-38-46-34 2 26 20 42 46 34z" fill="var(--roxo)" opacity=".8"/>
  </svg>'''

_DOTS_SVG = '''
  <svg class="capa-memorias-dots" viewBox="0 0 80 80" aria-hidden="true">
    {circulos}
  </svg>'''.format(
    circulos=''.join(
        f'<circle cx="{x}" cy="{y}" r="4.4" fill="var(--verde)" opacity=".75"/>'
        for y in (8, 28, 48, 68)
        for x in (8, 28, 48, 68)
    )
)

_WAVE_SVG = '''
  <svg class="capa-memorias-wave" viewBox="0 0 794 60" preserveAspectRatio="none" aria-hidden="true">
    <path d="M0 44C160 4 300 4 420 26s240 34 374-8" fill="none" stroke="var(--roxo)" stroke-width="2" opacity=".5"/>
  </svg>'''

_NARA_LOCK_HTML = '''
  <div class="capa-memorias-nara-lock">
    <svg viewBox="0 0 40 36" aria-hidden="true" width="34" height="30">
      <path d="M20 32.5C11.5 26.8 3.5 21 3.5 13.4 3.5 8.2 7.3 4.6 11.7 4.6c3.1 0 5.9 1.8 7.4 4.4" fill="none" stroke="var(--verde)" stroke-width="3.4" stroke-linecap="round"/>
      <path d="M20 32.5c8.5-5.7 16.5-11.5 16.5-19.1 0-5.2-3.8-8.8-8.2-8.8-4.6 0-8.3 4-8.3 9.9v11.4" fill="none" stroke="var(--roxo)" stroke-width="3.4" stroke-linecap="round"/>
    </svg>
    <div>
      <div class="nara-word">NARA<em>EDU</em></div>
      <div class="nara-sub">Núcleo de Acompanhamento<br>e Registro da Aprendizagem</div>
    </div>
  </div>'''

# Ilustração de exemplo — usada quando não há foto real da criança (upload
# ainda não existe no backend). É decorativa, não representa nenhuma
# criança específica.
_FOTO_PLACEHOLDER_SVG = '''
  <svg viewBox="0 0 400 480" preserveAspectRatio="xMidYMid slice" aria-label="Foto de exemplo">
    <rect width="400" height="480" fill="var(--roxo-ultra-claro)"/>
    <rect x="0" y="0" width="400" height="270" fill="var(--roxo-claro)"/>
    <rect x="24" y="70" width="120" height="10" rx="5" fill="#D3C6B2"/>
    <rect x="256" y="120" width="120" height="10" rx="5" fill="#D3C6B2"/>
    <g fill="var(--verde)" opacity=".55">
      <ellipse cx="52" cy="52" rx="26" ry="16" transform="rotate(-24 52 52)"/>
      <ellipse cx="96" cy="40" rx="22" ry="13" transform="rotate(16 96 40)"/>
      <ellipse cx="340" cy="70" rx="30" ry="18" transform="rotate(20 340 70)"/>
      <ellipse cx="300" cy="42" rx="20" ry="12" transform="rotate(-14 300 42)"/>
    </g>
    <g fill="#C29A72" opacity=".85">
      <path d="M282 128h58l-8 46h-42z"/>
      <path d="M40 150h48l-6 40H46z"/>
    </g>
    <rect x="150" y="380" width="100" height="100" fill="var(--roxo-ultra-claro)"/>
    <path d="M200 356c66 0 104 44 112 124H88c8-80 46-124 112-124z" fill="var(--branco)"/>
    <g fill="#DCC9DC" opacity=".9">
      <circle cx="150" cy="430" r="6"/>
      <circle cx="238" cy="452" r="5"/>
      <circle cx="182" cy="466" r="5"/>
    </g>
    <path d="M182 320h36v52h-36z" fill="#EFC3A4"/>
    <ellipse cx="200" cy="216" rx="82" ry="88" fill="#5A3B2E"/>
    <circle cx="200" cy="226" r="72" fill="#F0CBAA"/>
    <ellipse cx="132" cy="226" rx="18" ry="34" fill="#5A3B2E"/>
    <ellipse cx="268" cy="226" rx="18" ry="34" fill="#5A3B2E"/>
    <ellipse cx="176" cy="228" rx="9" ry="11" fill="#3A2A22"/>
    <ellipse cx="226" cy="228" rx="9" ry="11" fill="#3A2A22"/>
    <circle cx="173" cy="224" r="3" fill="#fff"/>
    <circle cx="223" cy="224" r="3" fill="#fff"/>
    <path d="M180 262c8 16 32 16 40 0 0 20-40 20-40 0z" fill="#fff"/>
    <path d="M180 262c8 16 32 16 40 0" fill="none" stroke="#B4685E" stroke-width="3" stroke-linecap="round"/>
  </svg>'''

_SPARKS_MASCOTE_SVG = '''
  <svg class="capa-mascote-sparks" viewBox="0 0 794 1123" preserveAspectRatio="none" aria-hidden="true">
    <g fill="none" stroke="var(--roxo)" stroke-width="3" stroke-linecap="round" opacity=".55">
      <path d="M120 330c60-40 130 10 100 60s-110 20-96-40"/>
    </g>
    <g stroke="var(--verde)" stroke-width="3.4" fill="none" stroke-linecap="round" opacity=".9">
      <path d="M228 402l-14 12M244 420l-16 10M232 442l-10-14"/>
      <path d="M566 398l14 12M552 420l16 10M562 442l10-14"/>
    </g>
    <g fill="none" stroke="var(--amarelo)" stroke-width="3" stroke-linejoin="round" opacity=".9">
      <path d="M86 300l6 12 13 2-9 9 2 13-12-6-12 6 2-13-9-9 13-2z"/>
      <path d="M700 250l5 10 11 2-8 8 2 11-10-5-10 5 2-11-8-8 11-2z"/>
    </g>
    <g fill="none" stroke="#F498B4" stroke-width="3.4" stroke-linecap="round" opacity=".9">
      <path d="M642 176c-6-9-19-6-19 3 0 8 11 14 19 20 8-6 19-12 19-20 0-9-13-12-19-3z"/>
      <path d="M470 892c-5-7-15-5-15 2 0 6 9 11 15 16 6-5 15-10 15-16 0-7-10-9-15-2z"/>
    </g>
    <g fill="none" stroke="var(--verde)" stroke-width="3.4" stroke-linecap="round" opacity=".85">
      <path d="M120 620c-6-9-19-6-19 3 0 8 11 14 19 20 8-6 19-12 19-20 0-9-13-12-19-3z"/>
    </g>
  </svg>'''

_NATUREZA_TOPDEC_ESQUERDA_SVG = '''
  <svg class="capa-natureza-topdec-esquerda" viewBox="0 0 330 340" fill="none" aria-hidden="true">
    <g opacity=".85">
      <path d="M40 320C40 200 70 120 130 60" stroke="var(--verde)" stroke-width="3" opacity=".5"/>
      <g fill="var(--verde)"><ellipse cx="52" cy="248" rx="34" ry="19" transform="rotate(-28 52 248)"/><ellipse cx="86" cy="196" rx="30" ry="17" transform="rotate(-40 86 196)"/><ellipse cx="34" cy="180" rx="26" ry="15" transform="rotate(20 34 180)"/><ellipse cx="112" cy="140" rx="27" ry="15" transform="rotate(-52 112 140)"/></g>
      <g fill="var(--roxo-claro)"><circle cx="150" cy="86" r="9"/><circle cx="168" cy="64" r="7"/><circle cx="136" cy="60" r="6"/><ellipse cx="188" cy="112" rx="7" ry="12" transform="rotate(24 188 112)"/></g>
      <g fill="#C9BFA6"><circle cx="86" cy="292" r="7"/><circle cx="122" cy="264" r="5"/></g>
    </g>
  </svg>'''

_NATUREZA_TOPDEC_DIREITA_SVG = '''
  <svg class="capa-natureza-topdec-direita" viewBox="0 0 250 300" fill="none" aria-hidden="true">
    <g opacity=".8">
      <g fill="#C9D6DE"><ellipse cx="96" cy="52" rx="44" ry="22"/><ellipse cx="140" cy="44" rx="30" ry="18"/></g>
      <g fill="var(--verde)"><ellipse cx="212" cy="150" rx="30" ry="17" transform="rotate(30 212 150)"/><ellipse cx="180" cy="196" rx="26" ry="15" transform="rotate(-16 180 196)"/></g>
      <g fill="var(--coral)" opacity=".9"><path d="M120 118c-12-8-26-2-26 8s16 14 26 8c10 6 26 2 26-8s-14-16-26-8z"/></g>
      <path d="M146 126c20 14 44 6 58-16" stroke="var(--coral)" stroke-width="2" stroke-dasharray="4 6" fill="none"/>
      <g fill="var(--roxo)" opacity=".7"><ellipse cx="52" cy="214" rx="8" ry="16" transform="rotate(-18 52 214)"/><ellipse cx="66" cy="188" rx="7" ry="14" transform="rotate(12 66 188)"/><ellipse cx="40" cy="186" rx="7" ry="13" transform="rotate(-40 40 186)"/></g>
    </g>
  </svg>'''

_NATUREZA_BOT_SVG = '''
  <svg class="capa-natureza-bot" viewBox="0 0 794 300" fill="none" aria-hidden="true">
    <path d="M300 300c40-60 110-70 150-130" stroke="#D8C9A8" stroke-width="26" stroke-linecap="round" opacity=".55"/>
    <g fill="var(--verde)" opacity=".9"><ellipse cx="120" cy="250" rx="46" ry="24" transform="rotate(-20 120 250)"/><ellipse cx="60" cy="214" rx="38" ry="20" transform="rotate(24 60 214)"/><ellipse cx="686" cy="244" rx="42" ry="22" transform="rotate(22 686 244)"/><ellipse cx="736" cy="200" rx="34" ry="18" transform="rotate(-18 736 200)"/></g>
    <g transform="translate(196,150)">
      <path d="M40 130V52" stroke="#6F8C56" stroke-width="7" stroke-linecap="round"/>
      <path d="M40 84c-6-26-34-38-64-32 2 28 30 42 64 32z" fill="#7FA162"/>
      <path d="M40 66c8-24 34-34 60-28-2 26-28 38-60 28z" fill="#93B473"/>
      <ellipse cx="40" cy="136" rx="42" ry="16" fill="#C6A889"/>
    </g>
    <g fill="var(--coral)" opacity=".75"><circle cx="470" cy="120" r="8"/><circle cx="520" cy="160" r="5"/></g>
  </svg>'''


def _duas_cores_antes_virgula(texto):
    """A palavra logo antes da vírgula fica em destaque (--coral), o resto
    no tom padrão. Bate com _duasCoresAntesVirgula em templateRelatorioShared.js."""
    return re.sub(r'(\S+,)', r'<em>\1</em>', texto, count=1)


# ---------------- Renderizadores por modelo ----------------

def _renderizar_capa_classico(contexto):
    el = _el(contexto)
    logo_html = contexto.get('logo_escola_html') or ''

    detalhes = [
        f'<div class="capa-detalhe-item"><span class="capa-detalhe-icone">🎓</span><div><label>Turma</label><span>{contexto["turma_nome"]}</span></div></div>',
        f'<div class="capa-detalhe-item"><span class="capa-detalhe-icone">📅</span><div><label>Período</label><span>{contexto["periodo_label"]}</span></div></div>',
    ]
    if el['date']:
        detalhes.append(
            f'<div class="capa-detalhe-item"><span class="capa-detalhe-icone">📝</span><div><label>Data de Geração</label><span>{contexto["data_geracao"]}</span></div></div>'
        )
    if el['age'] and contexto.get('idade'):
        detalhes.append(
            f'<div class="capa-detalhe-item"><span class="capa-detalhe-icone">👶</span><div><label>Idade</label><span>{contexto["idade"]}</span></div></div>'
        )
    if el['teacher']:
        detalhes.append(
            f'<div class="capa-detalhe-item"><span class="capa-detalhe-icone">👩‍🏫</span><div><label>Professora</label><span>{contexto.get("professora_nome", "Professora")}</span></div></div>'
        )

    endereco_linhas = []
    if el['cnpj'] and contexto.get('escola_cnpj'):
        endereco_linhas.append(f'<div class="capa-escola-endereco">{contexto["escola_cnpj"]}</div>')
    if el['contact'] and contexto.get('escola_contato'):
        endereco_linhas.append(f'<div class="capa-escola-endereco">{contexto["escola_contato"]}</div>')

    sumario_bloco = ''
    if el['content']:
        cores = ['var(--verde)', 'var(--azul)', 'var(--roxo)', 'var(--amarelo)', 'var(--coral)', '#ffb347']
        visiveis = [i for i in contexto['items_sumario'] if i['visivel']]
        itens_html = ''.join(
            f'<div class="capa-sumario-item"><span class="capa-sum-dot" style="background:{cores[i % 6]};"></span>{item["titulo"]}</div>'
            for i, item in enumerate(visiveis)
        )
        sumario_bloco = (
            '<div class="capa-sumario">'
            '<div class="capa-sumario-titulo">Conteúdo do Relatório</div>'
            f'<div class="capa-sumario-itens">{itens_html}</div>'
            '</div>'
        )

    rodape_frase = '<span class="rodape-nota">💫 Relatório elaborado com base em observações sistemáticas e análise do desenvolvimento integral da criança.</span>'

    return (
        '<div class="pagina capa">'
        '<div class="barra-topo"></div>'
        '<div class="capa-escola">'
        f'<div class="capa-logo">{logo_html}</div>'
        f'<div class="capa-escola-nome">{contexto["escola_nome"]}</div>'
        f'{"".join(endereco_linhas)}'
        '</div>'
        '<div class="capa-hero">'
        '<div class="capa-hero-deco"></div>'
        '<div class="capa-hero-conteudo">'
        f'<div class="capa-tipo-doc">{contexto.get("tipo_relatorio") or _TIPO_RELATORIO_PADRAO}</div>'
        f'<div class="capa-periodo-label">{contexto["periodo_label"]}</div>'
        '<div class="capa-hero-linha"></div>'
        f'<div class="capa-nome-crianca">{_abreviar_nome_composto(contexto["nome_crianca"], limite_caracteres=40)}</div>'
        '</div>'
        '</div>'
        f'<div class="capa-detalhes">{"".join(detalhes)}</div>'
        f'{sumario_bloco}'
        f'<div class="rodape">{_rodape_classico_essencial(rodape_frase, el, _RODAPE_NARA_HTML)}</div>'
        '<div class="barra-rodape"></div>'
        '</div>'
    )


def _renderizar_capa_memorias(contexto):
    el = _el(contexto)
    logo_html = contexto.get('logo_escola_html') or ''
    nome_exibido = _abreviar_nome_composto(contexto['nome_crianca'], limite_caracteres=20)

    meta = [f'<div class="capa-memorias-meta-item"><span class="icone-svg">{_ICONE_TURMA}</span><span class="rotulo">{contexto["turma_nome"]}</span></div>']
    if el['teacher']:
        meta.append(f'<div class="capa-memorias-meta-item"><span class="icone-svg">{_ICONE_PROFESSORA}</span><span class="rotulo">{contexto.get("professora_nome", "Professora")}</span></div>')
    meta.append(f'<div class="capa-memorias-meta-item"><span class="icone-svg">{_ICONE_PERIODO}</span><span class="rotulo">{contexto["periodo_label"]}</span></div>')
    meta.append(f'<div class="capa-memorias-meta-item"><span class="icone-svg">{_ICONE_ANO}</span><span class="rotulo">{contexto.get("ano_letivo", "")}</span></div>')
    if el['date']:
        meta.append(f'<div class="capa-memorias-meta-item"><span class="icone-svg">{_ICONE_DATA}</span><span class="rotulo">{contexto["data_geracao"]}</span></div>')

    foto_html = contexto.get('foto_crianca_html') or _FOTO_PLACEHOLDER_SVG

    logo_bloco = f'<div class="capa-logo">{logo_html}</div>' if logo_html else '<div class="capa-memorias-logo-placeholder">LOGO DA<br>ESCOLA</div>'

    rodape_frase = '<div class="frase">Cada infância guarda um jeito<br>único de aprender e florescer.</div>'
    rodape_partes = []
    # naraLogo/footerPhrase desativados a pedido — mesmo padrão do JS.
    # if el['naraLogo']:
    #     rodape_partes.append(_NARA_LOCK_HTML)
    # if el['footerPhrase']:
    #     rodape_partes.append(rodape_frase)

    return (
        '<div class="pagina capa capa-memorias">'
        '<div class="capa-memorias-blob b1"></div>'
        '<div class="capa-memorias-blob b2"></div>'
        f'{_LEAF_SVG}'
        f'{_DOTS_SVG}'
        '<div class="capa-memorias-topo">'
        f'{logo_bloco}'
        f'<div class="capa-memorias-escola-nome">{contexto["escola_nome"]}</div>'
        f'<div class="capa-memorias-kicker">{contexto.get("tipo_relatorio") or _TIPO_RELATORIO_PADRAO}</div>'
        f'<div class="capa-memorias-nome-crianca">{nome_exibido}</div>'
        '</div>'
        f'<div class="capa-memorias-foto-wrap"><div class="capa-memorias-foto-arco">{foto_html}</div></div>'
        f'<div class="capa-memorias-meta">{"".join(meta)}</div>'
        f'{_WAVE_SVG}'
        f'<div class="capa-memorias-rodape">{"".join(rodape_partes)}</div>'
        '</div>'
    )


def _renderizar_capa_mascote(contexto):
    el = _el(contexto)
    logo_html = contexto.get('logo_escola_html') or ''
    imagem_principal = contexto.get('imagem_principal') or 'nenhuma'
    mostrar_mascote = el['mascot'] and imagem_principal == 'mascote'

    linhas_def = [(_ICONE_TURMA, 'roxo', contexto['turma_nome'])]
    if el['teacher']:
        linhas_def.append((_ICONE_PROFESSORA, 'verde', contexto.get('professora_nome', 'Professora')))
    linhas_def.append((_ICONE_PERIODO, 'coral', contexto['periodo_label']))
    linhas_def.append((_ICONE_ANO, 'amarelo', contexto.get('ano_letivo', '')))
    if el['age'] and contexto.get('idade'):
        linhas_def.append((_ICONE_CIRCULO_IDADE, 'azul', contexto['idade']))
    if el['date']:
        linhas_def.append((_ICONE_DATA, 'roxo', contexto['data_geracao']))

    def _cor_texto(cor):
        return f'var(--{cor}-escuro)' if cor in ('roxo', 'verde') else f'var(--{cor})'

    linhas_html = ''.join(
        f'<div class="r"><span class="ic" style="background:var(--{cor}-claro);color:{_cor_texto(cor)};">{icone}</span><span class="tx">{texto}</span></div>'
        for icone, cor, texto in linhas_def
    )

    logo_bloco = f'<div class="capa-logo">{logo_html}</div>' if logo_html else '<div class="capa-mascote-logo-placeholder">LOGO DA<br>ESCOLA</div>'
    ilustracao_html = f'<div class="capa-mascote-ilustracao">{_mascote_img_html()}</div>' if mostrar_mascote else ''

    rodape_frase = '<div class="frase">Observar, acolher e<br>registrar cada descoberta.</div>'
    rodape_partes = []
    # naraLogo/footerPhrase desativados a pedido — mesmo padrão do JS.
    # if el['naraLogo']:
    #     rodape_partes.append(_NARA_LOCK_HTML)
    # if el['naraLogo'] and el['footerPhrase']:
    #     rodape_partes.append(f'<span class="capa-mascote-heart-sep">{_ICONE_HEART_SEPARADOR}</span>')
    # if el['footerPhrase']:
    #     rodape_partes.append(rodape_frase)

    return (
        '<div class="pagina capa capa-mascote">'
        '<div class="capa-mascote-blob b1"></div>'
        '<div class="capa-mascote-blob b2"></div>'
        '<div class="capa-mascote-blob b3"></div>'
        f'{_SPARKS_MASCOTE_SVG}'
        '<div class="capa-mascote-head">'
        f'{logo_bloco}'
        f'<div class="capa-mascote-escola-nome">{contexto["escola_nome"]}</div>'
        '</div>'
        f'<div class="capa-mascote-kicker">{contexto.get("titulo_relatorio") or _TITULO_RELATORIO_PADRAO}</div>'
        f'<div class="capa-mascote-titulo">{contexto.get("frase_destaque") or _FRASE_DESTAQUE_PADRAO["mascote"]}</div>'
        '<div class="capa-mascote-swoosh"></div>'
        f'<div class="capa-mascote-pill">{_abreviar_nome_composto(contexto["nome_crianca"], limite_caracteres=26)}</div>'
        '<div class="capa-mascote-corpo">'
        f'<div class="capa-mascote-infocard">{linhas_html}</div>'
        f'{ilustracao_html}'
        '</div>'
        f'<div class="capa-mascote-rodape">{"".join(rodape_partes)}</div>'
        '</div>'
    )


def _renderizar_capa_natureza(contexto):
    el = _el(contexto)
    logo_html = contexto.get('logo_escola_html') or ''
    classe_align = 'left' if contexto.get('alinhamento') == 'left' else 'center'

    meta = [f'<div class="capa-natureza-meta-item"><span class="icone-svg">{_SPRIG_SVG}</span><span class="rotulo">{contexto["turma_nome"]}</span></div>']
    if el['teacher']:
        meta.append(f'<div class="capa-natureza-meta-item"><span class="icone-svg">{_SPRIG_SVG}</span><span class="rotulo">{contexto.get("professora_nome", "Professora")}</span></div>')
    meta.append(f'<div class="capa-natureza-meta-item"><span class="icone-svg">{_SPRIG_SVG}</span><span class="rotulo">{contexto["periodo_label"]}</span></div>')
    meta.append(f'<div class="capa-natureza-meta-item"><span class="icone-svg">{_SPRIG_SVG}</span><span class="rotulo">{contexto.get("ano_letivo", "")}</span></div>')
    if el['age'] and contexto.get('idade'):
        meta.append(f'<div class="capa-natureza-meta-item"><span class="icone-svg">{_SPRIG_SVG}</span><span class="rotulo">{contexto["idade"]}</span></div>')
    if el['date']:
        meta.append(f'<div class="capa-natureza-meta-item"><span class="icone-svg">{_SPRIG_SVG}</span><span class="rotulo">{contexto["data_geracao"]}</span></div>')

    logo_bloco = f'<div class="capa-logo">{logo_html}</div>' if logo_html else '<div class="capa-natureza-logo-placeholder">LOGO DA<br>ESCOLA</div>'

    frase = contexto.get('frase_destaque') or _FRASE_DESTAQUE_PADRAO['natureza']
    frase_html = _duas_cores_antes_virgula(frase)

    foto_html = contexto.get('foto_crianca_html') or ''

    rodape_frase = '<div class="frase">Cada descoberta revela novas possibilidades de aprender.</div>'
    rodape_partes = []
    # naraLogo/footerPhrase desativados a pedido — mesmo padrão do JS.
    # if el['naraLogo']:
    #     rodape_partes.append(_NARA_LOCK_HTML)
    # if el['footerPhrase']:
    #     rodape_partes.append(rodape_frase)

    return (
        '<div class="pagina capa capa-natureza">'
        f'{_NATUREZA_TOPDEC_ESQUERDA_SVG}'
        f'{_NATUREZA_TOPDEC_DIREITA_SVG}'
        f'{_NATUREZA_BOT_SVG}'
        '<div class="capa-natureza-head">'
        f'{logo_bloco}'
        f'<div class="capa-natureza-escola-nome">{contexto["escola_nome"]}</div>'
        '</div>'
        f'<div class="capa-natureza-bloco align-{classe_align}">'
        f'<div class="capa-natureza-kicker">{contexto.get("titulo_relatorio") or _TITULO_RELATORIO_PADRAO}</div>'
        f'<div class="capa-natureza-titulo">{frase_html}</div>'
        '<div class="capa-natureza-namerow">'
        f'<span class="capa-natureza-sprig">{_SPRIG_SVG}</span>'
        f'<span class="capa-natureza-nome-crianca">{_abreviar_nome_composto(contexto["nome_crianca"], limite_caracteres=22)}</span>'
        f'<div class="capa-natureza-foto">{foto_html}</div>'
        '</div>'
        '</div>'
        '<div class="capa-natureza-divider"></div>'
        f'<div class="capa-natureza-meta">{"".join(meta)}</div>'
        f'<div class="capa-natureza-rodape">{"".join(rodape_partes)}</div>'
        '</div>'
    )


def _renderizar_capa_essencial(contexto):
    el = _el(contexto)
    logo_html = contexto.get('logo_escola_html') or ''
    imagem_principal = contexto.get('imagem_principal') or 'nenhuma'
    mostrar_mascote = el['mascot'] and imagem_principal == 'mascote'
    classe_align = 'center' if contexto.get('alinhamento') == 'center' else 'left'

    endereco_linhas = []
    if el['cnpj'] and contexto.get('escola_cnpj'):
        endereco_linhas.append(contexto['escola_cnpj'])
    if el['contact'] and contexto.get('escola_contato'):
        endereco_linhas.append(contexto['escola_contato'])
    linha_contato = ' · '.join(endereco_linhas)

    meta_lista = [('Turma', contexto['turma_nome'])]
    if el['teacher']:
        meta_lista.append(('Professora', contexto.get('professora_nome', 'Professora')))
    meta_lista.append(('Período', contexto['periodo_label']))
    meta_lista.append(('Ano letivo', contexto.get('ano_letivo', '')))
    if el['age'] and contexto.get('idade'):
        meta_lista.append(('Idade', contexto['idade']))
    if el['date']:
        meta_lista.append(('Data de geração', contexto['data_geracao']))
    meta_html = ''.join(
        f'<div class="capa-essencial-meta-item"><span class="rotulo">{lb}</span><span class="valor">{vl}</span></div>'
        for lb, vl in meta_lista
    )

    logo_bloco = f'<div class="capa-logo">{logo_html}</div>' if logo_html else '<div class="capa-essencial-logo-placeholder">LOGO DA<br>ESCOLA</div>'

    band_conteudo = (
        f'<div class="capa-essencial-mascote-wrap">{_mascote_img_html()}</div>'
        if mostrar_mascote else
        '<div class="capa-essencial-marca-fallback">NARA<br>EDU</div>'
    )

    rodape_frase = '<div class="frase">Acompanhar com atenção.<br>Registrar com sensibilidade.</div>'
    rodape_partes = []
    # naraLogo/footerPhrase desativados a pedido — mesmo padrão do JS.
    # if el['naraLogo']:
    #     rodape_partes.append(_NARA_LOCK_HTML)
    # if el['footerPhrase']:
    #     rodape_partes.append(rodape_frase)
    # if el['naraLogo']:
    #     rodape_partes.append('<div class="site">naraedu.com.br</div>')

    return (
        '<div class="pagina capa capa-essencial">'
        f'<div class="capa-essencial-band">{band_conteudo}</div>'
        '<div class="capa-essencial-head">'
        f'{logo_bloco}'
        '<span class="capa-essencial-divisor"></span>'
        '<div>'
        f'<div class="capa-essencial-escola-nome">{contexto["escola_nome"]}</div>'
        f'{f"<div class=capa-essencial-escola-linha>{linha_contato}</div>" if linha_contato else ""}'
        '</div>'
        '</div>'
        f'<div class="capa-essencial-bloco align-{classe_align}">'
        f'<div class="capa-essencial-kicker">{contexto.get("titulo_relatorio") or _TITULO_RELATORIO_PADRAO}</div>'
        f'<div class="capa-essencial-titulo">{contexto.get("tipo_relatorio") or _TIPO_RELATORIO_PADRAO}</div>'
        '<div class="capa-essencial-regua"><span class="linha"></span><span class="circulo"></span></div>'
        f'<div class="capa-essencial-nome-crianca">{_abreviar_nome_composto(contexto["nome_crianca"], limite_caracteres=24)}</div>'
        '</div>'
        f'<div class="capa-essencial-meta">{meta_html}</div>'
        '<div class="capa-essencial-greenline"></div>'
        f'<div class="capa-essencial-rodape">{"".join(rodape_partes)}</div>'
        '</div>'
    )


_RENDERIZADORES = {
    'classico': _renderizar_capa_classico,
    'memorias': _renderizar_capa_memorias,
    'mascote': _renderizar_capa_mascote,
    'natureza': _renderizar_capa_natureza,
    'essencial': _renderizar_capa_essencial,
}


def renderizar_capa(modelo, contexto):
    renderizador = _RENDERIZADORES.get(modelo, _renderizar_capa_classico)
    return renderizador(contexto)