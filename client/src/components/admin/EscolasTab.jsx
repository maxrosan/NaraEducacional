import { useCallback, useEffect, useMemo, useState } from 'react';
import { listarResumoEscolas } from '@/services/api';

/*
 * Dashboard do admin (/admin/dashboard): escolas da rede com dados reais de
 * GET /api/admin/dashboard/.
 *
 * Visual do protótipo "Escolas contratantes" mantido. Ficaram de fora os
 * blocos que dependem de dados que o backend ainda não tem: Health Score,
 * engajamento, ocupação de plano, tokens de IA, último acesso e impersonate.
 * Quando existirem, entram no `totais` do resumo e ganham espaço no card.
 */

const DIAS_RECENTE = 7;

function iniciais(nome = '') {
  const partes = nome.trim().split(/\s+/).filter((p) => p.length > 2 || /^[A-ZÁÉÍÓÚ]/.test(p));
  const base = partes.length ? partes : nome.trim().split(/\s+/);
  if (base.length === 1) return base[0].slice(0, 2).toUpperCase();
  return (base[0][0] + base[base.length - 1][0]).toUpperCase();
}

function localizacao(e) {
  const partes = [e.cidade, e.estado].filter(Boolean);
  return partes.length ? partes.join(' · ') : 'Localização não informada';
}

function diasDesde(iso) {
  if (!iso) return null;
  return Math.floor((Date.now() - new Date(iso).getTime()) / 86400000);
}

function textoUltimoRegistro(iso) {
  const dias = diasDesde(iso);
  if (dias === null) return 'sem registros';
  if (dias <= 0) return 'hoje';
  if (dias === 1) return 'há 1 dia';
  return `há ${dias} dias`;
}

/** Situação da escola, usada na cor do card, no selo e nos filtros. */
function situacao(e) {
  if (!e.ativa) return 'inativa';
  const dias = diasDesde(e.ultimo_registro);
  return dias !== null && dias < DIAS_RECENTE ? 'em-atividade' : 'sem-registros';
}

const SITUACOES = {
  'em-atividade': { rotulo: 'Em atividade', classe: 'school-great', fundo: '#E8F5E9', cor: '#4CAF50' },
  'sem-registros': { rotulo: 'Sem registros recentes', classe: 'school-attention', fundo: '#FFF3E0', cor: '#FFA726' },
  inativa: { rotulo: 'Inativa', classe: 'school-inactive', fundo: '#E5E7EB', cor: '#6B7280' },
};

/** Situações que pedem ação do admin. */
function pendencias(e) {
  const { turmas, professores, coordenadores } = e.totais;
  const lista = [];
  if (turmas === 0) lista.push('Nenhuma turma ativa');
  if (turmas > 0 && professores === 0) lista.push('Nenhum professor cadastrado');
  if (coordenadores === 0) lista.push('Sem coordenação cadastrada');
  return lista;
}

const numero = (n) => n.toLocaleString('pt-BR');

function CardEscola({ escola, indice, onClick }) {
  const sit = SITUACOES[situacao(escola)];
  const { alunos, turmas, professores, coordenadores, registros_30d: registros } = escola.totais;
  const avisos = pendencias(escola);
  const recente = situacao(escola) === 'em-atividade';
  const clicavel = Boolean(onClick);

  return (
    <div
      className={`school-card ${sit.classe} ${clicavel ? '' : 'is-static'}`}
      style={{ animationDelay: `${0.05 + indice * 0.03}s` }}
      {...(clicavel && {
        role: 'button',
        tabIndex: 0,
        onClick: () => onClick(escola),
        onKeyDown: (ev) => { if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); onClick(escola); } },
      })}
    >
      {!escola.ativa && (
        <div className="inactive-banner">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"/><line x1="4.93" y1="4.93" x2="19.07" y2="19.07"/></svg>
          <span><strong>Inativa</strong> · a equipe não acessa a plataforma</span>
        </div>
      )}

      <div className="school-card-head">
        <div className="school-avatar" style={escola.ativa ? undefined : { filter: 'grayscale(1) opacity(0.6)' }}>
          {iniciais(escola.nome)}
        </div>
        <div className="school-info">
          <div className="school-name">{escola.nome}</div>
          <div className="school-meta">
            {localizacao(escola)}
            {escola.tipo_unidade ? ` · ${escola.tipo_unidade === 'matriz' ? 'Matriz' : 'Filial'}` : ''}
          </div>
        </div>
        <span className="health-pill" style={{ background: sit.fundo, color: sit.cor }}>
          <span className="health-dot" style={{ background: sit.cor, animation: escola.ativa ? undefined : 'none' }} />
          {sit.rotulo}
        </span>
      </div>

      <div className="school-stats">
        <div className="stat-item"><div className="stat-label">Alunos ativos</div><div className="stat-value">{numero(alunos)}</div></div>
        <div className="stat-item"><div className="stat-label">Turmas</div><div className="stat-value">{numero(turmas)}</div></div>
        <div className="stat-item"><div className="stat-label">Registros 30d</div><div className="stat-value">{numero(registros)}</div></div>
      </div>

      {avisos.length > 0 ? (
        <div className="school-alerts">
          {avisos.map((a) => <div key={a} className="school-alert">{a}</div>)}
        </div>
      ) : (
        <div className="school-ok">Equipe e turmas cadastradas.</div>
      )}

      <div className="school-footer">
        <div className="footer-info">
          <span className="footer-item"><strong>{professores}</strong> prof.</span>
          <span className="footer-item"><strong>{coordenadores}</strong> coord.</span>
          <span
            className={`footer-access ${recente ? 'access-recent' : 'access-late'}`}
            title="Data do registro pedagógico mais recente da escola"
          >
            <span className="access-dot" style={recente ? undefined : { animation: 'none' }} />
            último registro {textoUltimoRegistro(escola.ultimo_registro)}
          </span>
        </div>
      </div>
    </div>
  );
}

const FILTROS = [
  { chave: 'todas', rotulo: 'Todas' },
  { chave: 'em-atividade', rotulo: 'Em atividade' },
  { chave: 'sem-registros', rotulo: 'Sem registros recentes' },
  { chave: 'inativa', rotulo: 'Inativas' },
];

function normalizar(texto = '') {
  return texto.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
}

export default function EscolasTab({ onEscolaClick }) {
  const [escolas, setEscolas] = useState([]);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState(null);
  const [busca, setBusca] = useState('');
  const [filtro, setFiltro] = useState('todas');

  const carregar = useCallback(async () => {
    setCarregando(true);
    setErro(null);
    try {
      setEscolas(await listarResumoEscolas());
    } catch (e) {
      setErro(e.message || 'Não foi possível carregar as escolas.');
    } finally {
      setCarregando(false);
    }
  }, []);

  useEffect(() => { carregar(); }, [carregar]);

  const contagemPorFiltro = useMemo(() => {
    const c = { todas: escolas.length, 'em-atividade': 0, 'sem-registros': 0, inativa: 0 };
    escolas.forEach((e) => { c[situacao(e)] += 1; });
    return c;
  }, [escolas]);

  const totais = useMemo(() => {
    const ativas = escolas.filter((e) => e.ativa);
    const soma = (campo) => ativas.reduce((s, e) => s + e.totais[campo], 0);
    return {
      ativas: ativas.length,
      alunos: soma('alunos'),
      professores: soma('professores'),
      registros: soma('registros_30d'),
    };
  }, [escolas]);

  const visiveis = useMemo(() => {
    const termo = normalizar(busca.trim());
    return escolas.filter((e) => {
      if (filtro !== 'todas' && situacao(e) !== filtro) return false;
      if (!termo) return true;
      return normalizar(`${e.nome} ${e.cidade} ${e.estado}`).includes(termo);
    });
  }, [escolas, busca, filtro]);

  return (
    <>
      <style>{`
        .escolas-tab { font-family: 'Poppins', -apple-system, sans-serif; font-size: 14px; line-height: 1.5; -webkit-font-smoothing: antialiased; }

        .escolas-tab .admin-header { margin-bottom: 28px; animation: et-fadeIn 0.5s ease-out; }
        .escolas-tab .admin-title { font-size: 28px; font-weight: 800; color: #1A1A2E; letter-spacing: -0.5px; margin-bottom: 4px; }
        .escolas-tab .admin-subtitle { font-size: 14px; color: #6B7280; }

        .escolas-tab .global-stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 28px; }
        .escolas-tab .global-stat { background: #FFFFFF; border-radius: 14px; padding: 16px 18px; border: 1px solid #F3F4F6; transition: all 0.18s; animation: et-fadeUp 0.5s ease-out backwards; }
        .escolas-tab .global-stat:hover { border-color: #EDE7F6; transform: translateY(-2px); box-shadow: 0 8px 24px rgba(126,91,190,0.08); }
        .escolas-tab .gs-label { font-size: 10px; color: #6B7280; font-weight: 700; text-transform: uppercase; letter-spacing: 0.6px; margin-bottom: 6px; display: flex; align-items: center; }
        .escolas-tab .gs-value { font-size: 22px; font-weight: 800; color: #1A1A2E; line-height: 1; letter-spacing: -0.5px; }
        .escolas-tab .gs-value small { font-size: 12px; color: #6B7280; font-weight: 600; margin-left: 2px; }
        .escolas-tab .gs-trend { font-size: 11px; font-weight: 600; margin-top: 6px; }
        .escolas-tab .gs-trend.up { color: #4CAF50; }
        .escolas-tab .gs-trend.down { color: #EF5350; }
        .escolas-tab .gs-trend.flat { color: #6B7280; }

        .escolas-tab .admin-filters { background: #FFFFFF; border-radius: 14px; padding: 14px 16px; display: flex; gap: 10px; flex-wrap: wrap; align-items: center; margin-bottom: 20px; border: 1px solid #F3F4F6; }
        .escolas-tab .admin-search { flex: 1; min-width: 240px; position: relative; }
        .escolas-tab .admin-search input { width: 100%; padding: 9px 14px 9px 36px; background: #F5F5F7; border: 1px solid #E5E7EB; border-radius: 10px; color: #1A1A2E; font-family: inherit; font-size: 13px; }
        .escolas-tab .admin-search input:focus { outline: none; border-color: #7E5BBE; background: white; }
        .escolas-tab .admin-search input::placeholder { color: #9CA3AF; }
        .escolas-tab .admin-search svg { position: absolute; left: 12px; top: 50%; transform: translateY(-50%); color: #9CA3AF; }
        .escolas-tab .filter-chip { padding: 7px 13px; border-radius: 99px; background: #F5F5F7; border: none; color: #6B7280; font-size: 12px; font-weight: 600; cursor: pointer; font-family: inherit; transition: all 0.15s; }
        .escolas-tab .filter-chip:hover { background: #F5F0FB; color: #7E5BBE; }
        .escolas-tab .filter-chip.active { background: #EDE7F6; color: #7E5BBE; }

        .escolas-tab .schools-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(min(100%, 380px), 1fr)); gap: 18px; }

        .escolas-tab .school-card { background: #FFFFFF; border: 1px solid #F3F4F6; border-radius: 18px; padding: 0; overflow: hidden; transition: all 0.2s; cursor: pointer; text-decoration: none; color: inherit; display: block; animation: et-fadeUp 0.5s ease-out backwards; }
        .escolas-tab .school-card:hover { border-color: #EDE7F6; transform: translateY(-3px); box-shadow: 0 12px 32px rgba(126,91,190,0.10); }
        .escolas-tab .school-card.school-risk { border-left: 4px solid #EF5350; }
        .escolas-tab .school-card.school-attention { border-left: 4px solid #FFA726; }
        .escolas-tab .school-card.school-good { border-left: 4px solid #5C9CE6; }
        .escolas-tab .school-card.school-great { border-left: 4px solid #4CAF50; }

        .escolas-tab .school-card-head { padding: 16px 20px 12px; display: flex; align-items: center; gap: 12px; border-bottom: 1px solid #F3F4F6; }
        .escolas-tab .school-avatar { width: 44px; height: 44px; border-radius: 12px; background: linear-gradient(135deg, #EDE7F6, #A5D6A7); color: #4A3370; display: flex; align-items: center; justify-content: center; font-size: 13px; font-weight: 800; flex-shrink: 0; }
        .escolas-tab .school-info { flex: 1; min-width: 0; }
        .escolas-tab .school-name { font-size: 15px; font-weight: 700; color: #1A1A2E; line-height: 1.2; }
        .escolas-tab .school-meta { font-size: 11px; color: #6B7280; margin-top: 3px; }
        .escolas-tab .health-pill { display: inline-flex; align-items: center; gap: 6px; padding: 4px 10px; border-radius: 99px; font-size: 11px; font-weight: 700; flex-shrink: 0; }
        .escolas-tab .health-dot { width: 6px; height: 6px; border-radius: 50%; animation: et-pulse 2.5s infinite; }

        .escolas-tab .school-stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; padding: 14px 20px; background: #FAFAFB; border-bottom: 1px solid #F3F4F6; }
        .escolas-tab .stat-item { text-align: center; }
        .escolas-tab .stat-label { font-size: 9.5px; color: #6B7280; text-transform: uppercase; letter-spacing: 0.5px; font-weight: 700; margin-bottom: 4px; }
        .escolas-tab .stat-value { font-size: 20px; font-weight: 800; color: #1A1A2E; letter-spacing: -0.3px; line-height: 1; }
        .escolas-tab .stat-value small { font-size: 10px; color: #6B7280; font-weight: 600; margin-left: 1px; }

        .escolas-tab .school-bars { padding: 14px 20px; border-bottom: 1px solid #F3F4F6; }
        .escolas-tab .bar-row { margin-bottom: 12px; }
        .escolas-tab .bar-row:last-child { margin-bottom: 0; }
        .escolas-tab .bar-row-label { display: flex; justify-content: space-between; font-size: 11px; color: #6B7280; font-weight: 500; margin-bottom: 4px; }
        .escolas-tab .bar-row-value { font-weight: 700; color: #1A1A2E; }
        .escolas-tab .bar-row-value.bar-good { color: #4CAF50; }
        .escolas-tab .bar-row-value.bar-warn { color: #FFA726; }
        .escolas-tab .bar-row-value.bar-crit { color: #EF5350; }
        .escolas-tab .bar-track { height: 6px; background: #F5F5F7; border-radius: 99px; overflow: hidden; }
        .escolas-tab .bar-fill { height: 100%; border-radius: 99px; transition: width 0.8s cubic-bezier(0.16,1,0.3,1); }
        .escolas-tab .bar-fill-good { background: #4CAF50; }
        .escolas-tab .bar-fill-warn { background: #FFA726; }
        .escolas-tab .bar-fill-crit { background: #EF5350; }

        .escolas-tab .school-footer { padding: 12px 20px; background: #FAFAFB; display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
        .escolas-tab .footer-info { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; font-size: 11px; color: #6B7280; }
        .escolas-tab .footer-info strong { color: #1A1A2E; font-weight: 700; }
        .escolas-tab .footer-item { display: inline-flex; align-items: center; gap: 4px; }
        .escolas-tab .footer-access { display: inline-flex; align-items: center; gap: 5px; padding: 2px 8px; border-radius: 99px; font-size: 10px; font-weight: 700; }
        .escolas-tab .footer-access.access-recent { background: #E8F5E9; color: #4CAF50; }
        .escolas-tab .footer-access.access-late { background: #FFEBEE; color: #EF5350; }
        .escolas-tab .access-dot { width: 5px; height: 5px; border-radius: 50%; background: currentColor; animation: et-pulse 2.5s infinite; }
        .escolas-tab .footer-actions { display: flex; gap: 6px; }
        .escolas-tab .impersonate-btn { display: inline-flex; align-items: center; gap: 5px; padding: 6px 11px; border-radius: 8px; border: 1px solid #E5E7EB; background: #FFFFFF; color: #2F2F42; font-size: 11px; font-weight: 700; cursor: pointer; font-family: inherit; transition: all 0.15s; }
        .escolas-tab .impersonate-btn:hover { background: #EDE7F6; border-color: #7E5BBE; color: #7E5BBE; }

        .escolas-tab .tip { display: inline-flex; align-items: center; justify-content: center; width: 14px; height: 14px; border-radius: 50%; border: 1.5px solid #9CA3AF; color: #9CA3AF; font-size: 9px; font-weight: 700; cursor: help; position: relative; margin-left: 6px; background: transparent; line-height: 1; vertical-align: middle; }
        .escolas-tab .tip:hover { border-color: #7E5BBE; color: #7E5BBE; background: #F5F0FB; }
        .escolas-tab .tip::before { content: attr(data-tip); position: absolute; bottom: calc(100% + 10px); left: 50%; transform: translateX(-50%) translateY(6px); background: #1A1A2E; color: white; padding: 10px 12px; border-radius: 8px; font-size: 11px; font-weight: 400; line-height: 1.5; width: max-content; max-width: 260px; white-space: normal; text-align: left; opacity: 0; visibility: hidden; pointer-events: none; transition: all 0.18s; z-index: 100; box-shadow: 0 12px 32px rgba(0,0,0,0.2); }
        .escolas-tab .tip:hover::before { opacity: 1; visibility: visible; transform: translateX(-50%) translateY(0); }

        .escolas-tab .school-card.school-inactive { border-left: 4px solid #9CA3AF; opacity: 0.85; background: #FAFAFB; position: relative; }
        .escolas-tab .school-card.school-inactive:hover { opacity: 1; }
        .escolas-tab .inactive-banner { background: #6B7280; color: white; padding: 7px 16px; font-size: 11px; font-weight: 600; display: flex; align-items: center; gap: 7px; }
        .escolas-tab .inactive-banner strong { font-weight: 800; }

        .escolas-tab .school-card.is-static { cursor: default; }
        .escolas-tab .school-card.is-static:hover { transform: none; }
        .escolas-tab .school-alerts { padding: 12px 20px; border-bottom: 1px solid #F3F4F6; display: flex; flex-direction: column; gap: 6px; }
        .escolas-tab .school-alert { display: flex; align-items: center; gap: 8px; font-size: 12px; font-weight: 600; color: #B26A00; }
        .escolas-tab .school-alert::before { content: ''; width: 6px; height: 6px; border-radius: 50%; background: #FFA726; flex-shrink: 0; }
        .escolas-tab .school-ok { padding: 12px 20px; border-bottom: 1px solid #F3F4F6; font-size: 12px; color: #6B7280; }
        .escolas-tab .state-box { background: #FFFFFF; border: 1px solid #F3F4F6; border-radius: 18px; padding: 32px; text-align: center; color: #6B7280; }
        .escolas-tab .state-box strong { display: block; color: #1A1A2E; font-size: 15px; margin-bottom: 4px; }
        .escolas-tab .state-box.error { border-color: #FFCDD2; background: #FFF5F5; color: #C62828; }
        .escolas-tab .state-box button { margin-top: 14px; }
        .escolas-tab .skeleton { background: linear-gradient(90deg, #F5F5F7 25%, #EDEDF0 50%, #F5F5F7 75%); background-size: 200% 100%; animation: et-shimmer 1.4s infinite; border-radius: 18px; height: 230px; }
        @keyframes et-shimmer { from { background-position: 200% 0; } to { background-position: -200% 0; } }
        @media (prefers-reduced-motion: reduce) {
          .escolas-tab *, .escolas-tab *::before { animation: none !important; transition: none !important; }
        }

        @keyframes et-fadeIn { from { opacity: 0; } to { opacity: 1; } }
        @keyframes et-fadeUp { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
        @keyframes et-pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }

        @media (max-width: 1100px) {
          .escolas-tab .global-stats { grid-template-columns: repeat(2, 1fr); }
          .escolas-tab .schools-grid { grid-template-columns: 1fr; }
        }
        @media (max-width: 600px) {
          .escolas-tab .global-stats { grid-template-columns: repeat(2, 1fr); }
          .escolas-tab .school-stats { grid-template-columns: 1fr 1fr; }
        }
      `}</style>

      <div className="escolas-tab">
        <div className="admin-header">
          <h1 className="admin-title">Escolas da rede</h1>
          <div className="admin-subtitle">
            {carregando
              ? 'Carregando escolas...'
              : `${totais.ativas} ${totais.ativas === 1 ? 'escola ativa' : 'escolas ativas'} de ${escolas.length} cadastradas`}
          </div>
        </div>

        {!erro && (
          <div className="global-stats">
            <div className="global-stat" style={{ animationDelay: '0.05s' }}>
              <div className="gs-label">Escolas ativas</div>
              <div className="gs-value">{carregando ? '–' : totais.ativas}<small>/{carregando ? '–' : escolas.length}</small></div>
            </div>
            <div className="global-stat" style={{ animationDelay: '0.08s' }}>
              <div className="gs-label">Alunos ativos</div>
              <div className="gs-value">{carregando ? '–' : numero(totais.alunos)}</div>
            </div>
            <div className="global-stat" style={{ animationDelay: '0.11s' }}>
              <div className="gs-label">Professores</div>
              <div className="gs-value">{carregando ? '–' : numero(totais.professores)}</div>
            </div>
            <div className="global-stat" style={{ animationDelay: '0.14s' }}>
              <div className="gs-label">
                Registros 30 dias
                <span className="tip" tabIndex={0} data-tip="Soma dos registros de observação, escrita, desenho e leitura criados nas escolas ativas nos últimos 30 dias.">i</span>
              </div>
              <div className="gs-value">{carregando ? '–' : numero(totais.registros)}</div>
            </div>
          </div>
        )}

        {!carregando && !erro && escolas.length > 0 && (
          <div className="admin-filters">
            <div className="admin-search">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/></svg>
              <input
                type="text"
                placeholder="Buscar escola ou cidade..."
                aria-label="Buscar escola ou cidade"
                value={busca}
                onChange={(ev) => setBusca(ev.target.value)}
              />
            </div>
            {FILTROS.map((f) => (
              <button
                key={f.chave}
                type="button"
                className={`filter-chip ${filtro === f.chave ? 'active' : ''}`}
                aria-pressed={filtro === f.chave}
                onClick={() => setFiltro(f.chave)}
              >
                {f.rotulo} ({contagemPorFiltro[f.chave]})
              </button>
            ))}
          </div>
        )}

        {carregando && (
          <div className="schools-grid">
            <div className="skeleton" />
            <div className="skeleton" />
          </div>
        )}

        {!carregando && erro && (
          <div className="state-box error" role="alert">
            <strong>Não foi possível carregar as escolas.</strong>
            {erro}
            <div>
              <button type="button" className="impersonate-btn" onClick={carregar}>Tentar novamente</button>
            </div>
          </div>
        )}

        {!carregando && !erro && escolas.length === 0 && (
          <div className="state-box">
            <strong>Nenhuma escola cadastrada nesta rede.</strong>
            As escolas cadastradas aparecem aqui com alunos, turmas e atividade.
          </div>
        )}

        {!carregando && !erro && escolas.length > 0 && visiveis.length === 0 && (
          <div className="state-box">
            <strong>Nenhuma escola encontrada.</strong>
            Ajuste a busca ou escolha outro filtro.
          </div>
        )}

        {!carregando && !erro && visiveis.length > 0 && (
          <div className="schools-grid">
            {visiveis.map((escola, i) => (
              <CardEscola key={escola.id} escola={escola} indice={i} onClick={onEscolaClick} />
            ))}
          </div>
        )}
      </div>
    </>
  );
}