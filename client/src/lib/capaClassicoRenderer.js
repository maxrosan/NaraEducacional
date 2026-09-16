// Porta fiel (mesma lógica, mesmo HTML gerado) de renderM1/coverVars/naraLock/ICON
// do NARA-capas-relatorio-prototipo.html — só a fonte de dados muda (nosso
// estado React em vez do `state` global do protótipo).

export const esc = (s) =>
  String(s == null ? '' : s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

export const cut = (s, n) => {
  s = String(s == null ? '' : s);
  return s.length > n ? s.slice(0, n - 1) + '…' : s;
};

export const up = (s) => String(s || '').toLocaleUpperCase('pt-BR');

export const ICON = {
  turma: '<svg width="19" height="19" viewBox="0 0 24 24" fill="none"><circle cx="9" cy="9" r="3.2" stroke="currentColor" stroke-width="1.8"/><circle cx="16.5" cy="10" r="2.4" stroke="currentColor" stroke-width="1.6"/><path d="M3.5 18.5c.6-3 3-4.6 5.5-4.6s4.9 1.6 5.5 4.6" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/><path d="M16 14.2c2 .3 3.7 1.7 4.2 4.3" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>',
  periodo: '<svg width="19" height="19" viewBox="0 0 24 24" fill="none"><rect x="3.4" y="5" width="17.2" height="15.5" rx="3" stroke="currentColor" stroke-width="1.8"/><path d="M3.4 9.6h17.2M8 3.4v3.4M16 3.4v3.4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/><circle cx="8.4" cy="14" r="1.2" fill="currentColor"/><circle cx="12" cy="14" r="1.2" fill="currentColor"/><circle cx="15.6" cy="14" r="1.2" fill="currentColor"/></svg>',
  data: '<svg width="19" height="19" viewBox="0 0 24 24" fill="none"><rect x="3.4" y="5" width="17.2" height="15.5" rx="3" stroke="currentColor" stroke-width="1.8"/><path d="M3.4 9.6h17.2M8 3.4v3.4M16 3.4v3.4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/><path d="M8 14.4h8" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>',
  idade: '<svg width="19" height="19" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="8.4" stroke="currentColor" stroke-width="1.8"/><path d="M9 10.6v.2M15 10.6v.2" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"/><path d="M9 14.6c1.8 1.7 4.2 1.7 6 0" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>',
  prof: '<svg width="19" height="19" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="8.4" r="3.6" stroke="currentColor" stroke-width="1.8"/><path d="M5 19.4c.8-3.6 3.6-5.4 7-5.4s6.2 1.8 7 5.4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>',
  lista: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none"><rect x="5" y="3.4" width="14" height="17.2" rx="2.6" stroke="currentColor" stroke-width="1.8"/><path d="M9 3v2.4h6V3" stroke="currentColor" stroke-width="1.8"/><path d="M8.6 10.4h6.8M8.6 14.2h4.6" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/></svg>',
};

// Paleta e tipografia fixas (Nível 1 do sistema real: sem picker de cor/fonte
// ainda — usa sempre a identidade padrão do modelo Clássico).
const DEFAULT_TOKENS = {
  p: '#6D5BB5',
  s: '#8FC79A',
  bg: '#FFFFFF',
  ink: '#3A3550',
  fhead: "'Trebuchet MS','Segoe UI',system-ui,sans-serif",
  fbody: "'Segoe UI',system-ui,-apple-system,'Helvetica Neue',sans-serif",
  fserif: "Georgia,'Times New Roman',serif",
  fhand: "'Segoe Print','Bradley Hand','Comic Sans MS',cursive",
  nsize: 1,
  tsize: 1,
};

const PALETTES = {
  original: {
    p: '#6D5BB5',
    s: '#8FC79A',
  },

  nara: {
    p: '#6D5BB5',
    s: '#9FD3A8',
  },

  natureza: {
    p: '#55703F',
    s: '#C57B57',
  },

  afetiva: {
    p: '#8B6BC4',
    s: '#E9A7BC',
  },

  alegre: {
    p: '#4E8FD1',
    s: '#F2C14E',
  },

  institucional: {
    p: '#2F5B92',
    s: '#8A97A6',
  },
};

const FONT_COMBOS = {
  a: {
    fhead: "'Trebuchet MS','Segoe UI',system-ui,sans-serif",
    fbody: "'Segoe UI',system-ui,-apple-system,'Helvetica Neue',sans-serif",
    fserif: "Georgia,'Times New Roman',serif",
    fhand: "'Segoe Print','Bradley Hand','Comic Sans MS',cursive",
  },

  b: {
    fhead: "Georgia,'Times New Roman',serif",
    fbody: "'Segoe UI',system-ui,-apple-system,'Helvetica Neue',sans-serif",
    fserif: "'Palatino Linotype','Book Antiqua',Georgia,serif",
    fhand: "'Segoe Script','Brush Script MT',cursive",
  },

  c: {
    fhead: "'Palatino Linotype','Book Antiqua',Georgia,serif",
    fbody: "'Trebuchet MS','Segoe UI',sans-serif",
    fserif: "'Palatino Linotype','Book Antiqua',Georgia,serif",
    fhand: "'Trebuchet MS','Segoe UI',sans-serif",
  },
};

const TEXT_COLORS = {
  auto: null,
  grafite: '#332F42',
  ameixa: '#4A3A6B',
  verde: '#31513A',
  terracota: '#8A4A34',
};

function readableOn(hex) {
  const c = String(hex || '').replace('#', '');

  if (c.length !== 6) {
    return '#FFFFFF';
  }

  const v = (i) => parseInt(c.substr(i, 2), 16) / 255;

  const f = (x) =>
    x <= 0.03928
      ? x / 12.92
      : Math.pow((x + 0.055) / 1.055, 2.4);

  const L =
    0.2126 * f(v(0)) +
    0.7152 * f(v(2)) +
    0.0722 * f(v(4));

  return L > 0.48 ? '#2A2540' : '#FFFFFF';
}

function resolveTokens(config = {}) {
  const paletteId = config?.palette || 'original';

  const palette =
    paletteId === 'personalizada'
      ? {
        p: config?.custom?.p || DEFAULT_TOKENS.p,
        s: config?.custom?.s || DEFAULT_TOKENS.s,
      }
      : PALETTES[paletteId] || PALETTES.original;

  const type = config?.type || {};

  const fonts =
    FONT_COMBOS[type.combo] ||
    FONT_COMBOS.a;

  const textColor =
    TEXT_COLORS[type.textColor] ||
    null;

  return {
    ...DEFAULT_TOKENS,

    p: palette.p,
    s: palette.s,

    fhead: fonts.fhead,
    fbody: fonts.fbody,
    fserif: fonts.fserif,
    fhand: fonts.fhand,

    cink: textColor || readableOn(palette.p),

    nsize: Number(type.nameSize) || 1,
    tsize: Number(type.titleSize) || 1,
  };
}

export function coverVarsStyle(config = {}) {
  const tokens = resolveTokens(config);

  const {
    p,
    s,
    bg,
    ink,
    fhead,
    fbody,
    fserif,
    fhand,
    nsize,
    tsize,
  } = tokens;

  return [
    `--p:${p}`,
    `--s:${s}`,
    `--pale:color-mix(in srgb, ${p} 13%, #fff)`,
    `--pOn:${readableOn(p)}`,
    `--cbg:${bg}`,
    `--cink:${ink}`,
    `--fhead:${fhead}`,
    `--fbody:${fbody}`,
    `--fserif:${fserif}`,
    `--fhand:${fhand}`,
    `--nsize:${nsize}`,
    `--tsize:${tsize}`,
  ].join(';');
}

function naraLock(w) {
  const h = Math.round(w * 0.3);

  return `<div class="nara-lock" style="width:${w}px">
    <svg style="width:${Math.round(h * 1.1)}px;height:${h}px;flex:none" viewBox="0 0 40 36" aria-hidden="true">
      <path
        d="M20 32.5C11.5 26.8 3.5 21 3.5 13.4 3.5 8.2 7.3 4.6 11.7 4.6c3.1 0 5.9 1.8 7.4 4.4"
        fill="none"
        stroke="var(--s)"
        stroke-width="3.4"
        stroke-linecap="round"
      />
      <path
        d="M20 32.5c8.5-5.7 16.5-11.5 16.5-19.1 0-5.2-3.8-8.8-8.2-8.8-4.6 0-8.3 4-8.3 9.9v11.4"
        fill="none"
        stroke="var(--p)"
        stroke-width="3.4"
        stroke-linecap="round"
      />
    </svg>

    <div>
      <div class="nara-word" style="font-size:${Math.round(w * 0.215)}px">
        <b>NARA</b><i>EDU</i>
      </div>
    </div>
  </div>`;
}

function logoNode(logoUrl) {
  const inner = logoUrl ? `<img src="${logoUrl}" alt="">` : `LOGO DA<br>ESCOLA`;
  return `<div class="solidbox logo">${inner}</div>`;
}

/**
 * Monta o HTML da capa Clássico (.cover.m1), pixel-a-pixel igual ao
 * `renderM1` do protótipo. `dados` são os valores de PREVIEW (escola/criança
 * de exemplo — nunca os reais, que só existem no momento da geração de um
 * relatório de verdade). `config` é o mesmo objeto salvo em
 * RelatorioCapaTemplate.config.
 */
export function renderCapaClassicoHTML(dados, config) {
  const show = config?.show || {};
  const content = config?.content || [];

  const inst = [];
  if (show.cnpj && dados.escolaCnpj) inst.push('CNPJ: ' + esc(dados.escolaCnpj));
  if (show.contact) {
    if (dados.escolaEndereco) inst.push(esc(dados.escolaEndereco));
    if (dados.escolaTelefone) inst.push('Tel: ' + esc(dados.escolaTelefone));
  }

  const cards = [
    ['turma', 'Turma', dados.turma],
    ['periodo', 'Período', dados.periodo],
  ];
  if (show.date !== false) cards.push(['data', 'Data de geração', dados.dataGeracao]);
  if (show.age) cards.push(['idade', 'Idade', dados.idade]);
  if (show.teacher) cards.push(['prof', 'Professora', dados.professora]);

  const mostrarConteudo = show.content !== false && content.length > 0;

  return `<div class="cover m1">
    <div class="toprule"></div>
    ${logoNode(dados.logoUrl)}
    <div class="school" data-fit>${esc(cut(dados.escolaNome, 46))}</div>
    ${inst.length ? `<div class="inst">${inst.join(' &nbsp;|&nbsp; ')}</div>` : ''}
    <div class="hero">
      <div class="kicker">${esc(cut(up(dados.tipoRelatorio), 40))}</div>
      <div class="period" data-fit>${esc(cut(up(dados.periodo), 26))}</div>
      <div class="dash"></div>
      <div class="name" data-fit>${esc(cut(dados.nomeCrianca, 38))}</div>
    </div>
    <div class="cards" style="grid-template-columns:repeat(${cards.length},1fr)">
      ${cards.map((c) => `<div class="card"><span class="ic" style="color:var(--p)">${ICON[c[0]]}</span><div><div class="lb">${esc(up(c[1]))}</div><div class="vl">${esc(cut(c[2] || '—', 18))}</div></div></div>`).join('')}
    </div>
    ${mostrarConteudo ? `<div class="content${content.length > 6 ? ' dense' : ''}">
      <div class="ch"><span class="ic" style="color:var(--p)">${ICON.lista}</span><h4>Conteúdo do relatório</h4></div>
      <ol>${content.map((t, i) => `<li><b>${i + 1}</b><span>${esc(cut(t, 62))}</span></li>`).join('')}</ol>
    </div>` : ''}
    <div class="foot">
      ${/* Ocultado a pedido — mantido comentado para facilitar reativação futura.
      show.naraLogo !== false ? naraLock(150) : */ '<div></div>'}
      ${/* Ocultado a pedido — mantido comentado para facilitar reativação futura.
      show.footerPhrase !== false ? `<div class="phrase">Relatório elaborado com base em observações sistemáticas<br>e análise do desenvolvimento integral da criança.</div>` : */ '<div class="phrase"></div>'}
      <div class="site">naraedu.com</div>
    </div>
    <div class="botrule"></div><div class="botrule g"></div>
  </div>`;
}

/** Dados de preview fixos (a "criança-exemplo" do protótipo) — nunca
 * persistidos, só usados pra desenhar a prévia enquanto o coordenador edita. */
export const DADOS_PREVIEW = {
  escolaNome: 'Escola Caminhos da Infância',
  escolaCnpj: '00.000.000/0000-00',
  escolaEndereco: 'Currais Novos',
  escolaTelefone: '(84) 0000-0000',
  logoUrl: null,
  tipoRelatorio: 'Relatório individual',
  periodo: '1º bimestre',
  dataGeracao: '27/07/2026',
  nomeCrianca: 'Helena Martins',
  turma: 'Infantil 4',
  idade: '4 anos',
  professora: 'Ana',
};