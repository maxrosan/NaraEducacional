import { useCallback, useEffect, useMemo, useState } from 'react';
import { useLocation, useSearchParams } from 'react-router-dom';
import { API_BASE_URL, authFetch, listarEscolas } from '@/services/api';
// Compartilhado entre TemplateEscolherModeloPage, TemplateEditorPage e
// TemplatesListPage. Mantém a MESMA estrutura HTML/classes que o backend usa
// para gerar o PDF (api/services/relatorio_capa.py) — a prévia na tela do
// coordenador precisa ser pixel-idêntica ao relatório final.

export const MODELOS = [
  { id: 'classico', nome: 'Clássico NARA', desc: 'O modelo tradicional, organizado e informativo.' },
  { id: 'memorias', nome: 'Memórias da Infância', desc: 'Uma capa afetiva com destaque para a foto da criança.' },
  { id: 'mascote', nome: 'Com a Nara', desc: 'Uma capa acolhedora com a mascote da plataforma.' },
  { id: 'natureza', nome: 'Pequenas Descobertas', desc: 'Uma capa delicada inspirada na natureza e na aprendizagem.' },
  { id: 'essencial', nome: 'Essencial', desc: 'Uma capa limpa, elegante e fácil de identificar.' },
];

// Asset estático da mascote (imagem real). Precisa existir em
// client/public/mascote-nara.png (preview) E em
// server/api/static/mascote-nara.png (PDF final, servido pelo Django).
export const MASCOTE_IMG_URL = '/mascote-nara.png';

// Precisa bater com _VARS_POR_MATIZ em server/api/services/relatorio_pdf.py
export const PALETAS = {
  padrao: {
    nome: 'Cores originais do modelo',
    desc: 'Como o modelo foi desenhado',
    amostra: ['#9b87d4', '#8bc4a0'],
    cores: {}, // vazio = nenhuma variável é sobrescrita, usa o CSS padrão do sistema
  },
  nara: {
    nome: 'NARA',
    desc: 'Lilás e verde-claro',
    amostra: ['#9b87d4', '#8bc4a0'],
    cores: {
      roxo: { base: '#9b87d4', escuro: '#6b5db0', claro: '#e8e2f7', ultraClaro: '#f4f1fc' },
      verde: { base: '#8bc4a0', escuro: '#5a9b74', claro: '#dff0e6', ultraClaro: '#f0f8f3' },
      amarelo: { base: '#f9c74f', escuro: '#b8860b', claro: '#fef8e3' },
      coral: { base: '#f4827a', escuro: '#c0392b', claro: '#fde8e7' },
      azul: { base: '#74b3e8', escuro: '#1a4a8a', claro: '#e3f1fb' },
    },
  },
  natureza: {
    nome: 'Natureza',
    desc: 'Verde, bege e terracota',
    amostra: ['#7A9B76', '#C9A66B'],
    cores: {
      roxo: { base: '#7A9B76', escuro: '#55754F', claro: '#E3EDE0', ultraClaro: '#F1F6EF' },
      verde: { base: '#C9A66B', escuro: '#9C7A45', claro: '#F3E9D6', ultraClaro: '#FAF5EC' },
      amarelo: { base: '#D98E4A', escuro: '#A8632B', claro: '#F7E2CE' },
      coral: { base: '#B5651D', escuro: '#8A4A14', claro: '#F0DCC7' },
      azul: { base: '#8FA998', escuro: '#63806D', claro: '#E5EEE7' },
    },
  },
  afetiva: {
    nome: 'Afetiva',
    desc: 'Rosa suave, lilás e creme',
    amostra: ['#8B6BC4', '#F2B6C4'],
    cores: {
      roxo: { base: '#8B6BC4', escuro: '#63489C', claro: '#EDE3F7', ultraClaro: '#F7F2FC' },
      verde: { base: '#9FCBA6', escuro: '#6FA37B', claro: '#E3F3E6', ultraClaro: '#F2FAF3' },
      amarelo: { base: '#F2B6C4', escuro: '#C97A8C', claro: '#FCEAEE' },
      coral: { base: '#E8917F', escuro: '#B85A48', claro: '#FBE4DE' },
      azul: { base: '#C9A6E0', escuro: '#9B6FC2', claro: '#F1E8F8' },
    },
  },
  alegre: {
    nome: 'Alegre',
    desc: 'Amarelo suave, azul e coral',
    amostra: ['#F2B705', '#4FA3D1'],
    cores: {
      roxo: { base: '#F2B705', escuro: '#C48F00', claro: '#FDF0C4', ultraClaro: '#FFFAEA' },
      verde: { base: '#4FA3D1', escuro: '#2E7BA8', claro: '#DCEEF7', ultraClaro: '#EFF7FB' },
      amarelo: { base: '#F2B705', escuro: '#C48F00', claro: '#FDF0C4' },
      coral: { base: '#E85D5D', escuro: '#B33E3E', claro: '#FBDEDE' },
      azul: { base: '#4FA3D1', escuro: '#2E7BA8', claro: '#DCEEF7' },
    },
  },
  institucional: {
    nome: 'Institucional',
    desc: 'Azul, cinza e branco',
    amostra: ['#3D5A80', '#98C1D9'],
    cores: {
      roxo: { base: '#3D5A80', escuro: '#293F57', claro: '#DCE5EE', ultraClaro: '#EEF2F7' },
      verde: { base: '#6A8CAF', escuro: '#4A6883', claro: '#E1EAF1', ultraClaro: '#F1F5F9' },
      amarelo: { base: '#E0A458', escuro: '#A8763A', claro: '#FBEEDD' },
      coral: { base: '#BC4B51', escuro: '#8E3438', claro: '#F5DCDD' },
      azul: { base: '#98C1D9', escuro: '#5F92AC', claro: '#E7F1F6' },
    },
  },
};

// ---------------- Cor personalizada (2 cores -> tons derivados) ----------------
// A personalização por cor da escola afeta só roxo (cor principal) e verde
// (cor secundária) — as duas únicas usadas em alguma capa. Os outros 3
// matizes (amarelo/coral/azul) são só das seções do CORPO do relatório e
// ficam no padrão do sistema, pra "BNCC" continuar coral etc.

function hexToRgb(hex) {
  const h = hex.replace('#', '');
  return {
    r: parseInt(h.substring(0, 2), 16),
    g: parseInt(h.substring(2, 4), 16),
    b: parseInt(h.substring(4, 6), 16),
  };
}

function rgbToHex({ r, g, b }) {
  const c = (v) => Math.round(Math.max(0, Math.min(255, v))).toString(16).padStart(2, '0');
  return `#${c(r)}${c(g)}${c(b)}`;
}

function misturar(hex, alvo, quantidade) {
  const a = hexToRgb(hex);
  const b = hexToRgb(alvo);
  return rgbToHex({
    r: a.r + (b.r - a.r) * quantidade,
    g: a.g + (b.g - a.g) * quantidade,
    b: a.b + (b.b - a.b) * quantidade,
  });
}

export function derivarTons(base) {
  return {
    base,
    escuro: misturar(base, '#000000', 0.28),
    claro: misturar(base, '#ffffff', 0.78),
    ultraClaro: misturar(base, '#ffffff', 0.92),
  };
}

export function montarPaletaPersonalizada(corPrincipal, corSecundaria) {
  return {
    nome: 'Cores da escola',
    desc: 'Personalizada',
    amostra: [corPrincipal, corSecundaria],
    cores: {
      roxo: derivarTons(corPrincipal),
      verde: derivarTons(corSecundaria),
      // amarelo/coral/azul de propósito ausentes: cssVarsPaleta() só
      // sobrescreve o que existir aqui, o resto cai no padrão do sistema.
    },
  };
}

function hslToHex(h, s, l) {
  s /= 100;
  l /= 100;
  const k = (n) => (n + h / 30) % 12;
  const a = s * Math.min(l, 1 - l);
  const f = (n) => l - a * Math.max(-1, Math.min(k(n) - 3, Math.min(9 - k(n), 1)));
  const toHex = (x) => Math.round(255 * x).toString(16).padStart(2, '0');
  return `#${toHex(f(0))}${toHex(f(8))}${toHex(f(4))}`;
}

export function sortearCoresQueCombinam() {
  const hue1 = Math.floor(Math.random() * 360);
  const hue2 = (hue1 + 140 + Math.floor(Math.random() * 40)) % 360;
  return {
    principal: hslToHex(hue1, 55, 62),
    secundaria: hslToHex(hue2, 55, 68),
  };
}

// Precisa bater com _SECOES_PADRAO em server/api/services/relatorio.py
export const SECOES_PADRAO = [
  { chave: 'atividades', titulo: 'O que vivemos juntos neste período', visivel: true },
  { chave: 'relato', titulo: 'Relato Individual', visivel: true },
  { chave: 'producoes', titulo: 'Análise das Produções', visivel: true },
  { chave: 'portfolio', titulo: 'Portfólio', visivel: true },
  { chave: 'bncc', titulo: 'Acompanhamento por Habilidades da BNCC', visivel: true },
  { chave: 'conclusao', titulo: 'Conclusão da Professora', visivel: true },
];

// ---------------- Elementos visíveis (dropdown "Textos e elementos visíveis") ----------------
// Bate com RelatorioTemplate.suporta_*() no backend (server/api/models).
// 'photo' fica de fora deste objeto de propósito: já é controlado pelo
// mesmo `usaFotoCrianca` da seção "Foto da criança" (mesmo campo, dois
// lugares no painel — igual ao protótipo, onde t-photo e v-photo são o
// mesmo state.show.photo).
export const ELEMENTOS_VISIVEIS_PADRAO = {
  age: true,
  teacher: true,
  date: true,
  cnpj: true,
  contact: true,
  naraLogo: false, // Ocultado a pedido — era `true`. Mantido comentado para reativar fácil.
  mascot: false,
  content: true,
  footerPhrase: false, // Ocultado a pedido — era `true`. Mantido comentado para reativar fácil.
};

// true = o coordenador pode ligar/desligar; false = elemento não existe
// nesse modelo, o toggle fica travado.
// 'memorias.age' é false: a capa de Memórias, fiel à referência, não tem
// slot de "idade" na fileira de metadados (só turma/professora/período/
// ano/data) — diferente dos outros modelos, que têm.
export const CAPACIDADES_ELEMENTOS = {
  classico: { age: true, teacher: true, date: true, cnpj: true, contact: true, naraLogo: true, mascot: false, content: true, footerPhrase: true },
  memorias: { age: false, teacher: true, date: true, cnpj: false, contact: false, naraLogo: true, mascot: false, content: false, footerPhrase: true },
  mascote: { age: true, teacher: true, date: true, cnpj: false, contact: false, naraLogo: true, mascot: true, content: false, footerPhrase: true },
  natureza: { age: true, teacher: true, date: true, cnpj: false, contact: false, naraLogo: true, mascot: false, content: false, footerPhrase: true },
  essencial: { age: true, teacher: true, date: true, cnpj: true, contact: true, naraLogo: true, mascot: true, content: false, footerPhrase: true },
};

// Modelos com a seção "Imagem principal" (bate com suporta_imagem_principal()).
export const MODELOS_COM_IMAGEM_PRINCIPAL = ['mascote', 'essencial'];

// Modelos com controle de alinhamento (bate com suporta_alinhamento()).
export const MODELOS_COM_ALINHAMENTO = ['natureza', 'essencial'];

// ---------------- Tipografia (dropdown "Tipografia") ----------------
// Combinações de fonte usam fontes de verdade via Google Fonts (não fontes
// do sistema operacional) — garante aparência igual em qualquer computador.
export const FONTES = {
  a: {
    nome: 'Suave e moderna',
    titulo: "'Nunito', 'Trebuchet MS', 'Segoe UI', sans-serif",
    corpo: "'Lora', Georgia, 'Times New Roman', serif",
  },
  b: {
    nome: 'Clássica e elegante',
    titulo: "'Playfair Display', Georgia, 'Times New Roman', serif",
    corpo: "'PT Serif', Georgia, serif",
  },
  c: {
    nome: 'Editorial e serena',
    titulo: "'Merriweather', Georgia, serif",
    corpo: "'Nunito', 'Trebuchet MS', 'Segoe UI', sans-serif",
  },
};

export const CORES_TEXTO = [
  { id: 'auto', nome: 'Automática', valor: null },
  { id: 'grafite', nome: 'Grafite', valor: '#332F42' },
  { id: 'ameixa', nome: 'Ameixa', valor: '#4A3A6B' },
  { id: 'verde', nome: 'Verde escuro', valor: '#31513A' },
  { id: 'terracota', nome: 'Terracota', valor: '#8A4A34' },
];

export const TIPOGRAFIA_PADRAO = {
  fonteCombo: 'a',
  corTexto: 'auto',
  nomeTamanho: 100, // 80-120, em %
  tituloTamanho: 100, // 80-120, em %
  alinhamento: 'left', // só usado em modelos de MODELOS_COM_ALINHAMENTO
};

// Gera as CSS vars de tipografia pra sobrepor no preview (mesmo padrão de
// cssVarsPaleta) — precisa bater com o que o backend aplica no PDF.
export function cssVarsTipografia(tipografia) {
  const t = { ...TIPOGRAFIA_PADRAO, ...tipografia };
  const fonte = FONTES[t.fonteCombo] || FONTES.a;
  const vars = {
    '--fonte-titulo': fonte.titulo,
    '--fonte-corpo': fonte.corpo,
    '--escala-nome': String(Math.min(120, Math.max(80, t.nomeTamanho)) / 100),
    '--escala-titulo': String(Math.min(120, Math.max(80, t.tituloTamanho)) / 100),
  };
  const cor = CORES_TEXTO.find((c) => c.id === t.corTexto);
  if (cor && cor.valor) vars['--cor-texto-capa'] = cor.valor;
  return vars;
}

// Dados fictícios só para a prévia (o relatório real usa dados da criança/turma).
export const DADOS_PREVIA = {
  nomeCrianca: 'Helena Martins',
  turma: 'Infantil 4',
  periodo: '1º Bimestre',
  anoLetivo: String(new Date().getFullYear()),
  professora: 'Ana Ribeiro',
  dataGeracao: new Date().toLocaleDateString('pt-BR'),
  idade: '4 anos',
};

// *** Memórias ***
// ---------------- Ícones e decorações SVG ----------------

const _ICONE_TURMA = `<svg width="15" height="15" viewBox="0 0 24 24" fill="none"><circle cx="9" cy="9" r="3.2" stroke="currentColor" stroke-width="1.8"/><circle cx="16.5" cy="10" r="2.4" stroke="currentColor" stroke-width="1.6"/><path d="M3.5 18.5c.6-3 3-4.6 5.5-4.6s4.9 1.6 5.5 4.6" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/><path d="M16 14.2c2 .3 3.7 1.7 4.2 4.3" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>`;

const _ICONE_PROFESSORA = `<svg width="15" height="15" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="8.4" r="3.6" stroke="currentColor" stroke-width="1.8"/><path d="M5 19.4c.8-3.6 3.6-5.4 7-5.4s6.2 1.8 7 5.4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>`;

const _ICONE_PERIODO = `<svg width="15" height="15" viewBox="0 0 24 24" fill="none"><rect x="3.4" y="5" width="17.2" height="15.5" rx="3" stroke="currentColor" stroke-width="1.8"/><path d="M3.4 9.6h17.2M8 3.4v3.4M16 3.4v3.4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/><circle cx="8.4" cy="14" r="1.2" fill="currentColor"/><circle cx="12" cy="14" r="1.2" fill="currentColor"/><circle cx="15.6" cy="14" r="1.2" fill="currentColor"/></svg>`;

const _ICONE_ANO = `<svg width="15" height="15" viewBox="0 0 24 24" fill="none"><path d="M12 3.6l2.5 5.3 5.7.7-4.2 4 1.1 5.7-5.1-2.9-5.1 2.9 1.1-5.7-4.2-4 5.7-.7z" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/></svg>`;

const _ICONE_DATA = `<svg width="15" height="15" viewBox="0 0 24 24" fill="none"><rect x="3.4" y="5" width="17.2" height="15.5" rx="3" stroke="currentColor" stroke-width="1.8"/><path d="M3.4 9.6h17.2M8 3.4v3.4M16 3.4v3.4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/><path d="M8 14.4h8" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>`;

const _LEAF_SVG = `
  <svg class="capa-memorias-leaf" viewBox="0 0 120 200" fill="none" aria-hidden="true">
    <path d="M60 196V44" stroke="var(--roxo)" stroke-width="4" stroke-linecap="round"/>
    <path d="M60 150c-8-30-30-42-52-38 2 30 24 48 52 38zM60 116c8-30 30-42 52-38-2 30-24 48-52 38zM60 84c-8-28-26-38-46-34 2 26 20 42 46 34z" fill="var(--roxo)" opacity=".8"/>
  </svg>`;

const _DOTS_SVG = `
  <svg class="capa-memorias-dots" viewBox="0 0 80 80" aria-hidden="true">
    ${[8, 28, 48, 68].flatMap((y) => [8, 28, 48, 68].map((x) => `<circle cx="${x}" cy="${y}" r="4.4" fill="var(--verde)" opacity=".75"/>`)).join('')}
  </svg>`;

const _WAVE_SVG = `
  <svg class="capa-memorias-wave" viewBox="0 0 794 60" preserveAspectRatio="none" aria-hidden="true">
    <path d="M0 44C160 4 300 4 420 26s240 34 374-8" fill="none" stroke="var(--roxo)" stroke-width="2" opacity=".5"/>
  </svg>`;

const _NARA_LOCK_HTML = `
  <div class="capa-memorias-nara-lock">
    <svg viewBox="0 0 40 36" aria-hidden="true" width="34" height="30">
      <path d="M20 32.5C11.5 26.8 3.5 21 3.5 13.4 3.5 8.2 7.3 4.6 11.7 4.6c3.1 0 5.9 1.8 7.4 4.4" fill="none" stroke="var(--verde)" stroke-width="3.4" stroke-linecap="round"/>
      <path d="M20 32.5c8.5-5.7 16.5-11.5 16.5-19.1 0-5.2-3.8-8.8-8.2-8.8-4.6 0-8.3 4-8.3 9.9v11.4" fill="none" stroke="var(--roxo)" stroke-width="3.4" stroke-linecap="round"/>
    </svg>
    <div>
      <div class="nara-word">NARA<em>EDU</em></div>
      <div class="nara-sub">Núcleo de Acompanhamento<br>e Registro da Aprendizagem</div>
    </div>
  </div>`;

// *** Com a Nara ***
// Ilustração de exemplo — usada quando não há foto real da criança (upload
// ainda não existe no backend). É decorativa, não representa nenhuma
// criança específica. Cores da parede/prateleiras acompanham a paleta
// (--roxo/--verde); tons de pele/cabelo/madeira ficam fixos, por
// representarem elementos reais, não identidade visual da marca.
const _FOTO_PLACEHOLDER_SVG = `
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
  </svg>`;

const _ICONE_CIRCULO_IDADE = `<svg width="15" height="15" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="8.4" stroke="currentColor" stroke-width="1.8"/><path d="M9 10.6v.2M15 10.6v.2" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"/><path d="M9 14.6c1.8 1.7 4.2 1.7 6 0" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>`;

const _ICONE_HEART_SEPARADOR = `<svg viewBox="0 0 24 24" fill="none"><path d="M12 20c-5-3.5-9-7-9-11.2C3 5.6 5.3 3.4 8 3.4c1.9 0 3.3 1 4 2.4.7-1.4 2.1-2.4 4-2.4 2.7 0 5 2.2 5 5.4C21 13 17 16.5 12 20z" fill="var(--roxo)" opacity=".65"/></svg>`;

// Confetes decorativos (rabisco, marcas, estrelas, corações) — coordenadas
// absolutas na página inteira (viewBox 0 0 794 1123), fiéis ao protótipo.
const _SPARKS_MASCOTE_SVG = `
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
  </svg>`;

// *** Pequenas Descobertas ***
const _SPRIG_SVG = `<svg viewBox="0 0 40 90" fill="none"><path d="M20 88V16" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"/><path d="M20 60c-3-14-12-20-17-19 0 13 7 21 17 19zM20 44c3-14 12-20 17-19 0 13-7 21-17 19zM20 28c-3-12-10-16-15-15 0 11 6 17 15 15z" fill="currentColor" opacity=".85"/></svg>`;

const _NATUREZA_TOPDEC_ESQUERDA_SVG = `
  <svg class="capa-natureza-topdec-esquerda" viewBox="0 0 330 340" fill="none" aria-hidden="true">
    <g opacity=".85">
      <path d="M40 320C40 200 70 120 130 60" stroke="var(--verde)" stroke-width="3" opacity=".5"/>
      <g fill="var(--verde)"><ellipse cx="52" cy="248" rx="34" ry="19" transform="rotate(-28 52 248)"/><ellipse cx="86" cy="196" rx="30" ry="17" transform="rotate(-40 86 196)"/><ellipse cx="34" cy="180" rx="26" ry="15" transform="rotate(20 34 180)"/><ellipse cx="112" cy="140" rx="27" ry="15" transform="rotate(-52 112 140)"/></g>
      <g fill="var(--roxo-claro)"><circle cx="150" cy="86" r="9"/><circle cx="168" cy="64" r="7"/><circle cx="136" cy="60" r="6"/><ellipse cx="188" cy="112" rx="7" ry="12" transform="rotate(24 188 112)"/></g>
      <g fill="#C9BFA6"><circle cx="86" cy="292" r="7"/><circle cx="122" cy="264" r="5"/></g>
    </g>
  </svg>`;

const _NATUREZA_TOPDEC_DIREITA_SVG = `
  <svg class="capa-natureza-topdec-direita" viewBox="0 0 250 300" fill="none" aria-hidden="true">
    <g opacity=".8">
      <g fill="#C9D6DE"><ellipse cx="96" cy="52" rx="44" ry="22"/><ellipse cx="140" cy="44" rx="30" ry="18"/></g>
      <g fill="var(--verde)"><ellipse cx="212" cy="150" rx="30" ry="17" transform="rotate(30 212 150)"/><ellipse cx="180" cy="196" rx="26" ry="15" transform="rotate(-16 180 196)"/></g>
      <g fill="var(--coral)" opacity=".9"><path d="M120 118c-12-8-26-2-26 8s16 14 26 8c10 6 26 2 26-8s-14-16-26-8z"/></g>
      <path d="M146 126c20 14 44 6 58-16" stroke="var(--coral)" stroke-width="2" stroke-dasharray="4 6" fill="none"/>
      <g fill="var(--roxo)" opacity=".7"><ellipse cx="52" cy="214" rx="8" ry="16" transform="rotate(-18 52 214)"/><ellipse cx="66" cy="188" rx="7" ry="14" transform="rotate(12 66 188)"/><ellipse cx="40" cy="186" rx="7" ry="13" transform="rotate(-40 40 186)"/></g>
    </g>
  </svg>`;

const _NATUREZA_BOT_SVG = `
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
  </svg>`;

// O título tem 2 cores: a palavra logo antes da vírgula fica em destaque
// (--coral), o resto no tom padrão. Funciona automaticamente com a frase
// padrão ("Pequenas descobertas, grandes aprendizagens" -> "descobertas,"
// vira <em>) e degrada bem pra texto customizado sem vírgula (fica tudo
// em uma cor só, sem quebrar).
function _duasCoresAntesVirgula(texto) {
  return texto.replace(/(\S+,)/, '<em>$1</em>');
}

export function renderCapa(modeloId, ctx) {
  const logoHtml = ctx.logoUrl ? `<img src="${ctx.logoUrl}" alt="${ctx.escolaNome}">` : '';
  const el = { ...ELEMENTOS_VISIVEIS_PADRAO, ...(ctx.elementos || {}) };
  const imagemPrincipal = ctx.imagemPrincipal || 'nenhuma';
  const mostrarMascote = el.mascot && imagemPrincipal === 'mascote';
  const mascoteImgHtml = `<img src="${MASCOTE_IMG_URL}" alt="Mascote NARA" />`;
  const rodapeNaraHtml = '<span class="rodape-nara">NARAEDU • naraeducacional.com</span>';

  switch (modeloId) {
    case 'memorias': {
      const meta = [];
      meta.push(`<div class="capa-memorias-meta-item"><span class="icone-svg">${_ICONE_TURMA}</span><span class="rotulo">${DADOS_PREVIA.turma}</span></div>`);
      if (el.teacher) meta.push(`<div class="capa-memorias-meta-item"><span class="icone-svg">${_ICONE_PROFESSORA}</span><span class="rotulo">${DADOS_PREVIA.professora}</span></div>`);
      meta.push(`<div class="capa-memorias-meta-item"><span class="icone-svg">${_ICONE_PERIODO}</span><span class="rotulo">${DADOS_PREVIA.periodo}</span></div>`);
      meta.push(`<div class="capa-memorias-meta-item"><span class="icone-svg">${_ICONE_ANO}</span><span class="rotulo">${DADOS_PREVIA.anoLetivo}</span></div>`);
      if (el.date) meta.push(`<div class="capa-memorias-meta-item"><span class="icone-svg">${_ICONE_DATA}</span><span class="rotulo">${DADOS_PREVIA.dataGeracao}</span></div>`);

      const fotoHtml = ctx.fotoCriancaHtml || _FOTO_PLACEHOLDER_SVG;

      const logoBloco = logoHtml
        ? `<div class="capa-logo">${logoHtml}</div>`
        : '<div class="capa-memorias-logo-placeholder">LOGO DA<br>ESCOLA</div>';

      return `
        <div class="pagina capa capa-memorias">
          <div class="capa-memorias-blob b1"></div>
          <div class="capa-memorias-blob b2"></div>
          ${_LEAF_SVG}
          ${_DOTS_SVG}
          <div class="capa-memorias-topo">
            ${logoBloco}
            <div class="capa-memorias-escola-nome">${ctx.escolaNome}</div>
            <div class="capa-memorias-kicker">${ctx.tipoRelatorio || 'Relatório Individual'}</div>
            <div class="capa-memorias-nome-crianca">${DADOS_PREVIA.nomeCrianca}</div>
          </div>
          <div class="capa-memorias-foto-wrap"><div class="capa-memorias-foto-arco">${fotoHtml}</div></div>
          <div class="capa-memorias-meta">${meta.join('')}</div>
          ${_WAVE_SVG}
          <div class="capa-memorias-rodape">
            ${/* Ocultado a pedido, mesmo se o template salvo tiver true — mantido comentado p/ reativar.
            el.naraLogo ? _NARA_LOCK_HTML : */ ''}
            ${/* el.footerPhrase ? '<div class="frase">Cada infância guarda um jeito<br>único de aprender e florescer.</div>' : */ ''}
          </div>
        </div>`;
    }

    case 'mascote': {
      const linhas = [
        { icone: _ICONE_TURMA, cor: 'roxo', texto: DADOS_PREVIA.turma },
      ];
      if (el.teacher) linhas.push({ icone: _ICONE_PROFESSORA, cor: 'verde', texto: DADOS_PREVIA.professora });
      linhas.push({ icone: _ICONE_PERIODO, cor: 'coral', texto: DADOS_PREVIA.periodo });
      linhas.push({ icone: _ICONE_ANO, cor: 'amarelo', texto: DADOS_PREVIA.anoLetivo });
      if (el.age) linhas.push({ icone: _ICONE_CIRCULO_IDADE, cor: 'azul', texto: DADOS_PREVIA.idade });
      if (el.date) linhas.push({ icone: _ICONE_DATA, cor: 'roxo', texto: DADOS_PREVIA.dataGeracao });

      const linhasHtml = linhas
        .map(
          (l) =>
            `<div class="r"><span class="ic" style="background:var(--${l.cor}-claro);color:var(--${l.cor}${l.cor === 'roxo' || l.cor === 'verde' ? '-escuro' : ''});">${l.icone}</span><span class="tx">${l.texto}</span></div>`
        )
        .join('');

      const logoBloco = logoHtml
        ? `<div class="capa-logo">${logoHtml}</div>`
        : '<div class="capa-mascote-logo-placeholder">LOGO DA<br>ESCOLA</div>';

      return `
        <div class="pagina capa capa-mascote">
          <div class="capa-mascote-blob b1"></div>
          <div class="capa-mascote-blob b2"></div>
          <div class="capa-mascote-blob b3"></div>
          ${_SPARKS_MASCOTE_SVG}
          <div class="capa-mascote-head">
            ${logoBloco}
            <div class="capa-mascote-escola-nome">${ctx.escolaNome}</div>
          </div>
          <div class="capa-mascote-kicker">${ctx.tituloRelatorio || 'Relatório de Acompanhamento da Aprendizagem'}</div>
          <div class="capa-mascote-titulo">${ctx.fraseDestaque || 'Meu caminho de aprendizagens'}</div>
          <div class="capa-mascote-swoosh"></div>
          <div class="capa-mascote-pill">${DADOS_PREVIA.nomeCrianca}</div>
          <div class="capa-mascote-corpo">
            <div class="capa-mascote-infocard">${linhasHtml}</div>
            ${mostrarMascote ? `<div class="capa-mascote-ilustracao">${mascoteImgHtml}</div>` : ''}
          </div>
          <div class="capa-mascote-rodape">
            ${/* Ocultado a pedido, mesmo se o template salvo tiver true — mantido comentado p/ reativar.
            el.naraLogo ? _NARA_LOCK_HTML : */ ''}
            ${/* el.naraLogo && el.footerPhrase ? `<span class="capa-mascote-heart-sep">${_ICONE_HEART_SEPARADOR}</span>` : */ ''}
            ${/* el.footerPhrase ? '<div class="frase">Observar, acolher e<br>registrar cada descoberta.</div>' : */ ''}
          </div>
        </div>`;
    }

    case 'natureza': {
      const meta = [];
      const metaItem = (texto) => `<div class="capa-natureza-meta-item"><span class="icone-svg">${_SPRIG_SVG}</span><span class="rotulo">${texto}</span></div>`;
      meta.push(metaItem(DADOS_PREVIA.turma));
      if (el.teacher) meta.push(metaItem(DADOS_PREVIA.professora));
      meta.push(metaItem(DADOS_PREVIA.periodo));
      meta.push(metaItem(DADOS_PREVIA.anoLetivo));
      if (el.age) meta.push(metaItem(DADOS_PREVIA.idade));
      if (el.date) meta.push(metaItem(DADOS_PREVIA.dataGeracao));

      const logoBloco = logoHtml
        ? `<div class="capa-logo">${logoHtml}</div>`
        : '<div class="capa-natureza-logo-placeholder">LOGO DA<br>ESCOLA</div>';

      const fraseHtml = _duasCoresAntesVirgula(ctx.fraseDestaque || 'Pequenas descobertas, grandes aprendizagens');

      // Diferente do Memórias: sem foto real, o círculo fica vazio (só a
      // borda tracejada) — é assim na referência, sem ilustração de exemplo.
      const fotoHtml = ctx.fotoCriancaHtml || '';

      return `
        <div class="pagina capa capa-natureza">
          ${_NATUREZA_TOPDEC_ESQUERDA_SVG}
          ${_NATUREZA_TOPDEC_DIREITA_SVG}
          ${_NATUREZA_BOT_SVG}
          <div class="capa-natureza-head">
            ${logoBloco}
            <div class="capa-natureza-escola-nome">${ctx.escolaNome}</div>
          </div>
          <div class="capa-natureza-bloco align-${ctx.alinhamento === 'center' ? 'center' : 'left'}">
            <div class="capa-natureza-kicker">${ctx.tituloRelatorio || 'Relatório de Acompanhamento da Aprendizagem'}</div>
            <div class="capa-natureza-titulo">${fraseHtml}</div>
            <div class="capa-natureza-namerow">
              <span class="capa-natureza-sprig">${_SPRIG_SVG}</span>
              <span class="capa-natureza-nome-crianca">${DADOS_PREVIA.nomeCrianca}</span>
              <div class="capa-natureza-foto">${fotoHtml}</div>
            </div>
          </div>
          <div class="capa-natureza-divider"></div>
          <div class="capa-natureza-meta">${meta.join('')}</div>
          <div class="capa-natureza-rodape">
            ${/* Ocultado a pedido, mesmo se o template salvo tiver true — mantido comentado p/ reativar.
            el.naraLogo ? _NARA_LOCK_HTML : */ ''}
            ${/* el.footerPhrase ? '<div class="capa-natureza-frase-linha"><span class="dot"></span><div class="frase">Cada descoberta revela novas possibilidades de aprender.</div><span class="dot"></span></div>' : */ ''}
          </div>
        </div>`;
    }

    case 'essencial': {
      const enderecoLinhas = [];
      if (el.cnpj && ctx.escolaCnpj) enderecoLinhas.push(ctx.escolaCnpj);
      if (el.contact && ctx.escolaContato) enderecoLinhas.push(ctx.escolaContato);
      const linhaContato = enderecoLinhas.join(' · ');

      const metaLista = [{ lb: 'Turma', vl: DADOS_PREVIA.turma }];
      if (el.teacher) metaLista.push({ lb: 'Professora', vl: DADOS_PREVIA.professora });
      metaLista.push({ lb: 'Período', vl: DADOS_PREVIA.periodo });
      metaLista.push({ lb: 'Ano letivo', vl: DADOS_PREVIA.anoLetivo });
      if (el.age) metaLista.push({ lb: 'Idade', vl: DADOS_PREVIA.idade });
      if (el.date) metaLista.push({ lb: 'Data de geração', vl: DADOS_PREVIA.dataGeracao });
      const metaHtml = metaLista
        .map((m) => `<div class="capa-essencial-meta-item"><span class="rotulo">${m.lb}</span><span class="valor">${m.vl}</span></div>`)
        .join('');

      const logoBloco = logoHtml
        ? `<div class="capa-logo">${logoHtml}</div>`
        : '<div class="capa-essencial-logo-placeholder">LOGO DA<br>ESCOLA</div>';

      const bandConteudo = mostrarMascote
        ? `<div class="capa-essencial-mascote-wrap">${mascoteImgHtml}</div>`
        : '<div class="capa-essencial-marca-fallback">NARA<br>EDU</div>';

      return `
        <div class="pagina capa capa-essencial">
          <div class="capa-essencial-band">${bandConteudo}</div>
          <div class="capa-essencial-head">
            ${logoBloco}
            <span class="capa-essencial-divisor"></span>
            <div>
              <div class="capa-essencial-escola-nome">${ctx.escolaNome}</div>
              ${linhaContato ? `<div class="capa-essencial-escola-linha">${linhaContato}</div>` : ''}
            </div>
          </div>
          <div class="capa-essencial-bloco align-${ctx.alinhamento === 'center' ? 'center' : 'left'}">
            <div class="capa-essencial-kicker">${ctx.tituloRelatorio || 'Relatório de Acompanhamento da Aprendizagem'}</div>
            <div class="capa-essencial-titulo">${ctx.tipoRelatorio || 'Relatório Individual'}</div>
            <div class="capa-essencial-regua"><span class="linha"></span><span class="circulo"></span></div>
            <div class="capa-essencial-nome-crianca">${DADOS_PREVIA.nomeCrianca}</div>
          </div>
          <div class="capa-essencial-meta">${metaHtml}</div>
          <div class="capa-essencial-greenline"></div>
          <div class="capa-essencial-rodape">
            ${/* Ocultado a pedido, mesmo se o template salvo tiver true — mantido comentado p/ reativar.
            el.naraLogo ? _NARA_LOCK_HTML : */ ''}
            ${/* el.footerPhrase ? '<div class="frase">Acompanhar com atenção.<br>Registrar com sensibilidade.</div>' : */ ''}
            ${/* el.naraLogo ? '<div class="site">naraedu.com.br</div>' : */ ''}
          </div>
        </div>`;
    }

    case 'classico':
    default: {
      const detalhes = [];
      detalhes.push(`<div class="capa-detalhe-item"><span class="capa-detalhe-icone">🎓</span><div><label>Turma</label><span>${DADOS_PREVIA.turma}</span></div></div>`);
      detalhes.push(`<div class="capa-detalhe-item"><span class="capa-detalhe-icone">📅</span><div><label>Período</label><span>${DADOS_PREVIA.periodo}</span></div></div>`);
      if (el.date) detalhes.push(`<div class="capa-detalhe-item"><span class="capa-detalhe-icone">📝</span><div><label>Data de Geração</label><span>${DADOS_PREVIA.dataGeracao}</span></div></div>`);
      if (el.age) detalhes.push(`<div class="capa-detalhe-item"><span class="capa-detalhe-icone">👶</span><div><label>Idade</label><span>${DADOS_PREVIA.idade}</span></div></div>`);
      if (el.teacher) detalhes.push(`<div class="capa-detalhe-item"><span class="capa-detalhe-icone">👩‍🏫</span><div><label>Professora</label><span>${DADOS_PREVIA.professora}</span></div></div>`);

      const enderecoLinhas = [];
      if (el.cnpj && ctx.escolaCnpj) enderecoLinhas.push(`<div class="capa-escola-endereco">${ctx.escolaCnpj}</div>`);
      if (el.contact && ctx.escolaContato) enderecoLinhas.push(`<div class="capa-escola-endereco">${ctx.escolaContato}</div>`);

      const itensSumarioHtml = (ctx.itemsSumario || SECOES_PADRAO)
        .filter((i) => i.visivel)
        .map(
          (item, i) =>
            `<div class="capa-sumario-item"><span class="capa-sum-dot" style="background:${['var(--verde)', 'var(--azul)', 'var(--roxo)', 'var(--amarelo)', 'var(--coral)', '#ffb347'][i % 6]
            };"></span>${item.titulo}</div>`
        )
        .join('');

      return `
        <div class="pagina capa">
          <div class="barra-topo"></div>
          <div class="capa-escola">
            <div class="capa-logo">${logoHtml}</div>
            <div class="capa-escola-nome">${ctx.escolaNome}</div>
            ${enderecoLinhas.join('')}
          </div>
          <div class="capa-hero">
            <div class="capa-hero-deco"></div>
            <div class="capa-hero-conteudo">
              <div class="capa-tipo-doc">${ctx.tipoRelatorio || 'Relatório Individual'}</div>
              <div class="capa-periodo-label">${DADOS_PREVIA.periodo}</div>
              <div class="capa-hero-linha"></div>
              <div class="capa-nome-crianca">${DADOS_PREVIA.nomeCrianca}</div>
            </div>
          </div>
          <div class="capa-detalhes">${detalhes.join('')}</div>
          ${el.content ? `
          <div class="capa-sumario">
            <div class="capa-sumario-titulo">Conteúdo do Relatório</div>
            <div class="capa-sumario-itens">${itensSumarioHtml}</div>
          </div>` : ''}
          <div class="rodape">
            ${/* Ocultado a pedido, mesmo se o template salvo tiver true — mantido comentado p/ reativar.
            el.footerPhrase ? '<span class="rodape-nota">💫 Relatório elaborado com base em observações sistemáticas e análise do desenvolvimento integral da criança.</span>' : */ ''}
            ${/* el.naraLogo ? rodapeNaraHtml : */ ''}
          </div>
          <div class="barra-rodape"></div>
        </div>`;
    }
  }
}

export function cssVarsPaleta(paleta) {
  const vars = {};
  const sufixo = { base: '', escuro: '-escuro', claro: '-claro', ultraClaro: '-ultra-claro' };
  Object.entries(paleta.cores).forEach(([matiz, tons]) => {
    Object.entries(tons).forEach(([tom, valor]) => {
      vars[`--${matiz}${sufixo[tom]}`] = valor;
    });
  });
  return vars;
}

// ---------------- API ----------------
// Camada de compatibilidade: as páginas de template (lista, escolher modelo,
// editor) ainda chamam as rotas do sistema antigo. Aqui elas viram as rotas
// do backend multi-tenant, autenticadas por JWT (authFetch), sem sessão,
// cookie nem CSRF:
//   /api/templates-relatorio/...            → /relatorio-templates/...
//   POST /api/templates-relatorio/<id>/ativar/ → PATCH .../<id>/atualizar/ {ativo: true}
//     (o backend desativa os outros templates da escola)
//   /api/auth/me/                           → /me/
//   PUT de atualização                      → PATCH (só os campos enviados)

function traduzirRota(url, method, body) {
  let caminho = url.replace(/^\/api(?=\/)/, '');
  caminho = caminho.replace(/^\/templates-relatorio(?=\/)/, '/relatorio-templates');
  caminho = caminho.replace(/^\/auth\/me\/$/, '/me/');

  const ativar = caminho.match(/^\/relatorio-templates\/([^/]+)\/ativar\/$/);
  if (ativar) {
    return { caminho: `/relatorio-templates/${ativar[1]}/atualizar/`, method: 'PATCH', body: { ativo: true } };
  }
  if (method === 'PUT' && /\/atualizar\/$/.test(caminho)) method = 'PATCH';
  return { caminho, method, body };
}

async function handleJson(res) {
  if (res.status === 204) return {};
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    // DRF devolve {campo: ["msg"]} na validação; o resto vem em error/detail.
    const campos = data && typeof data === 'object' && !Array.isArray(data)
      ? Object.values(data).flat(Infinity).filter((m) => typeof m === 'string').join(' ')
      : '';
    throw new Error(data.error || data.detail || campos || `Erro ${res.status}`);
  }
  return data;
}

async function requisitar(url, method = 'GET', body) {
  const rota = traduzirRota(url, method, body);
  const options = { method: rota.method };
  if (rota.body !== undefined && rota.method !== 'GET' && rota.method !== 'DELETE') {
    options.headers = { 'Content-Type': 'application/json' };
    options.body = JSON.stringify(rota.body);
  }
  return handleJson(await authFetch(`${API_BASE_URL}${rota.caminho}`, options));
}

/** Mantida só por compatibilidade: o backend novo não usa CSRF (JWT). */
export async function getCsrfToken() {
  return '';
}

export const apiGet = (url) => requisitar(url, 'GET');
export const apiPost = (url, body) => requisitar(url, 'POST', body);
export const apiPut = (url, body) => requisitar(url, 'PUT', body);
export const apiDelete = (url) => requisitar(url, 'DELETE');

// Cabeçalho da prévia no mesmo critério de _dados_cabecalho
// (server/api/services/relatorio.py): dados da ESCOLA, com fallback campo a
// campo para a INSTITUIÇÃO; o logo vem da instituição.
// `escolaUuid` = UUID da escola que está sendo configurada; sem ela, a do
// usuário. URLs da API sempre levam o UUID (o id inteiro vai só no body).
export async function fetchInstituicao(escolaUuid) {
  const vazio = { nome: 'Sua Escola', cnpj: '', contato: '', logoUrl: null };
  try {
    let instituicaoUuid = null;
    if (!escolaUuid) {
      const me = await apiGet('/me/');
      escolaUuid = me.escola_uuid;
      instituicaoUuid = me.instituicao_uuid;
    }
    const escola = escolaUuid ? await apiGet(`/escolas/${escolaUuid}/`).catch(() => null) : null;
    instituicaoUuid = escola?.instituicao_uuid ?? instituicaoUuid;
    const inst = instituicaoUuid ? await apiGet(`/instituicoes/${instituicaoUuid}/`).catch(() => null) : null;
    if (!escola && !inst) return vazio;

    const campo = (nome) => (escola && escola[nome]) || (inst && inst[nome]) || '';
    const cidade = campo('cidade');
    const estado = campo('estado');

    const partesContato = [];
    if (campo('endereco')) partesContato.push(campo('endereco'));
    if (cidade) partesContato.push(estado ? `${cidade} — ${estado}` : cidade);
    if (campo('telefone')) partesContato.push(`Tel: ${campo('telefone')}`);

    return {
      nome: campo('nome') || 'Sua Escola',
      cnpj: campo('cnpj') ? `CNPJ: ${campo('cnpj')}` : '',
      contato: partesContato.join(' | '),
      logoUrl: (inst && inst.logo_url) || null,
    };
  } catch {
    return vazio;
  }
}

/** Modelo (ex.: "classico") do template ativo da escola (`escolaUuid`, ou a
 * do usuário), ou null. Mesmo retorno de antes — só passou a ser por escola. */
export async function fetchModeloAtivo(escolaUuid) {
  try {
    if (!escolaUuid) {
      const me = await apiGet('/me/');
      escolaUuid = me.escola_uuid;
    }
    const url = escolaUuid ? `/relatorio-templates/?escola=${escolaUuid}&ativo=1` : '/relatorio-templates/?ativo=1';
    const ativo = ((await apiGet(url)) || []).find((t) => t.ativo);
    return ativo ? ativo.modelo : null;
  } catch (error) {
    console.error('Erro ao buscar modelo ativo:', error);
    return null;
  }
}

// ---------------- Escola em configuração ----------------
// Template é POR ESCOLA. A escola vai na URL (?escola=<uuid>) para acompanhar a
// navegação lista → escolher modelo → editor (e vir de Admin → Relatórios).
// Sem ?escola, usa a escola do usuário ou, na falta, a primeira ativa do
// escopo — e grava na URL. Coordenador só enxerga a própria (o backend recorta).
//
// Regra do sistema: na URL (rota ou query string) vai o UUID; no body vai o
// id inteiro. Por isso o hook devolve os dois:
//   * escolaUuid — o que está na URL; use em links e em chamadas GET;
//   * escolaId   — o id (int) da mesma escola; use no body de POST/PATCH.

const PARECE_ID = /^\d+$/;

export function useEscolaTemplate() {
  const [searchParams, setSearchParams] = useSearchParams();
  const escolaUuid = searchParams.get('escola') || null;
  const [escolas, setEscolas] = useState([]);
  const [pronto, setPronto] = useState(false);

  /** Troca a escola em configuração. Recebe o UUID da escola. */
  const trocarEscola = useCallback((uuid) => {
    setSearchParams((atual) => {
      const novo = new URLSearchParams(atual);
      if (uuid) novo.set('escola', String(uuid)); else novo.delete('escola');
      return novo;
    }, { replace: true });
  }, [setSearchParams]);

  useEffect(() => {
    let cancelado = false;
    (async () => {
      try {
        const [lista, me] = await Promise.all([listarEscolas(), apiGet('/me/').catch(() => ({}))]);
        if (cancelado) return;
        const ativas = (lista || []).filter((e) => e.ativa !== false);
        setEscolas(ativas);
        let atual = escolaUuid;
        if (atual && PARECE_ID.test(atual)) {
          // Link/favorito antigo com ?escola=<id>: troca pelo uuid da mesma escola.
          atual = ativas.find((e) => String(e.id) === atual)?.uuid || null;
          if (atual) trocarEscola(atual);
        }
        if (!atual) {
          const propria = me.escola_uuid ? String(me.escola_uuid) : '';
          const padrao = ativas.find((e) => String(e.uuid) === propria) || ativas[0];
          trocarEscola(padrao ? padrao.uuid : null);
        }
      } catch {
        // Sem a lista de escolas a tela segue com o que vier na URL.
      } finally {
        if (!cancelado) setPronto(true);
      }
    })();
    return () => { cancelado = true; };
    // Só na montagem: a troca de escola depois é feita pelo seletor.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /** Acrescenta ?escola=<uuid> a uma rota (de tela ou de GET na API). */
  const comEscola = useCallback((rota, uuid = escolaUuid) => {
    if (!uuid) return rota;
    return `${rota}${rota.includes('?') ? '&' : '?'}escola=${uuid}`;
  }, [escolaUuid]);

  const escolaAtual = escolas.find((e) => String(e.uuid) === String(escolaUuid)) || null;
  const escolaId = escolaAtual ? escolaAtual.id : null;
  // `pronto` só quando a escola já está decidida (ou não há nenhuma) e não é
  // um ?escola=<id> antigo esperando a troca pelo uuid.
  const decidida = Boolean(escolaUuid) && !PARECE_ID.test(escolaUuid);
  return {
    escolaUuid, escolaId, escolas, escolaAtual, trocarEscola, comEscola,
    pronto: pronto && (decidida || escolas.length === 0),
  };
}

// ---------------- Rotas das telas de template ----------------
// As mesmas telas abrem em dois lugares, cada um com a SUA navbar:
//   * coordenação: /coordenacao/templates/...  (layout do coordenador)
//   * painel admin: /admin/capa?...            (aba do AdminPage)
// Os links internos seguem o lugar onde a tela está aberta, para o usuário
// não ser jogado para o layout do outro perfil.
// `editar(uuid)` recebe o UUID do template (t.uuid), nunca o id.

export function useRotasTemplate() {
  const { pathname } = useLocation();
  const noAdmin = pathname.startsWith('/admin');
  return useMemo(() => (noAdmin
    ? {
      noAdmin: true,
      modelos: '/admin/capa',
      nova: (modelo) => `/admin/capa?tela=nova&modelo=${modelo}`,
      editar: (uuid) => `/admin/capa?template=${uuid}`,
    }
    : {
      noAdmin: false,
      modelos: '/coordenacao/templates/escolher-modelo',
      nova: (modelo) => `/coordenacao/templates/nova?modelo=${modelo}`,
      editar: (uuid) => `/coordenacao/templates/${uuid}`,
    }), [noAdmin]);
}

// ---------------- Template novo com a configuração padrão ----------------
// Usado pelo "Selecionar" de um modelo que a escola ainda não tinha: cria o
// template já pronto para uso, sem passar pelo editor. Mesmos valores
// iniciais do TemplateEditorPage para um template novo — se mudar um, mude
// o outro.
// `itemsSumario`: a ordem/visibilidade em uso na escola (trocar a capa não
// deve desfazer o que foi configurado em "Ordem das seções").
export function templatePadraoDoModelo(modeloId, nomeEscola, itemsSumario) {
  const modelo = MODELOS.find((m) => m.id === modeloId);
  const comMascote = MODELOS_COM_IMAGEM_PRINCIPAL.includes(modeloId);
  return {
    nome: `${modelo?.nome || 'Template'} — ${nomeEscola || 'Sua Escola'}`,
    modelo: modeloId,
    usa_foto_aluno: false,
    config: {
      paleta: PALETAS.padrao.cores,
      tipoRelatorio: 'Relatório Individual',
      tituloRelatorio: 'Relatório de Acompanhamento da Aprendizagem',
      fraseDestaque: '',
      elementos: { ...ELEMENTOS_VISIVEIS_PADRAO, mascot: comMascote },
      imagemPrincipal: comMascote ? 'mascote' : 'nenhuma',
      fonteCombo: TIPOGRAFIA_PADRAO.fonteCombo,
      corTexto: TIPOGRAFIA_PADRAO.corTexto,
      nomeTamanho: TIPOGRAFIA_PADRAO.nomeTamanho,
      tituloTamanho: TIPOGRAFIA_PADRAO.tituloTamanho,
      alinhamento: null,
    },
    items_sumario: (Array.isArray(itemsSumario) && itemsSumario.length ? itemsSumario : SECOES_PADRAO)
      .map((item) => ({ ...item })),
  };
}