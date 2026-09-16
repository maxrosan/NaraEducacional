import React, { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useCoordinatorData } from '@/components/coordinator/v2/CoordinatorDataContext';
import './turmas.css';

const turmaBadge = (nome = '') => {
  const num = (nome.match(/\d+/) || [''])[0];
  const letters = nome.match(/[A-Z]/g) || [];
  const letter = num ? (letters[letters.length - 1] || '') : '';
  if (num) return `${num}${letter}`;
  return nome.replace(/[^A-Za-zÀ-ú]/g, '').slice(0, 2).toUpperCase() || '–';
};

// Agrupador de nível: "Nível 4 — A" -> "Nível 4"; "1º ANO B" -> "1º ANO"
const grupoNivel = (nome = '') => {
  const m = nome.match(/(N[íi]vel\s*\d+|\d+\s*º?\s*ANO|Maternal\s*\w*|Pré\s*\w*)/i);
  return m ? m[0].replace(/\s+/g, ' ').trim() : nome.split(/[—-]/)[0].trim();
};

export default function TurmasPage() {
  const { loading, dashboardData, viewData } = useCoordinatorData();
  const navigate = useNavigate();
  const [search, setSearch] = useState('');
  const [nivel, setNivel] = useState('all');

  const turmas = viewData?.turmas || [];
  const criancas = viewData?.criancas || [];
  const professores = viewData?.professores || [];
  const comRelatorio = useMemo(() => new Set(dashboardData?.criancasRelatorioFinalizadoIds || []), [dashboardData]);
  const porTurma = dashboardData?.indicadores?.por_turma || {};

  // turma nome -> professor nome (via professores[].turmas[])
  const profPorTurmaNome = useMemo(() => {
    const m = new Map();
    professores.forEach((p) => (p.turmas || []).forEach((tn) => { if (!m.has(tn)) m.set(tn, p.nome); }));
    return m;
  }, [professores]);

  const cards = useMemo(() => {
    return turmas.map((t) => {
      const criancasTurma = criancas.filter((c) => String(c.turma_id) === String(t.id));
      const nCri = criancasTurma.length;
      const nRel = criancasTurma.filter((c) => comRelatorio.has(String(c.id))).length;
      const pt = porTurma[String(t.id)] || porTurma[t.id] || {};
      return {
        id: t.id,
        nome: t.nome,
        prof: profPorTurmaNome.get(t.nome) || '—',
        criancas: nCri,
        registros: pt.registros || 0,
        // Cobertura BNCC: pares criança×habilidade observados, sobre o total
        // possível (crianças da turma × habilidades da faixa etária dela).
        // O número sozinho não era comparável entre turmas — "20" era cobertura
        // total no 1º ano (20 habilidades) e impossível na Educação Infantil (13).
        cobertura: pt.cobertura_pares || 0,
        coberturaTotal: pt.cobertura_total || 0,
        relatorios: nRel,
        grupo: grupoNivel(t.nome),
      };
    }).sort((a, b) => a.nome.localeCompare(b.nome, 'pt'));
  }, [turmas, criancas, comRelatorio, porTurma, profPorTurmaNome]);

  const niveis = useMemo(() => Array.from(new Set(cards.map((c) => c.grupo))).slice(0, 6), [cards]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return cards.filter((c) => {
      const nOk = nivel === 'all' || c.grupo === nivel;
      const qOk = !q || c.nome.toLowerCase().includes(q) || c.prof.toLowerCase().includes(q);
      return nOk && qOk;
    });
  }, [cards, search, nivel]);

  const totalCriancas = criancas.length;
  const totalRelatorios = comRelatorio.size;

  if (loading || !dashboardData) {
    return <main className="content"><div className="coord-loader"><div className="coord-spin" /></div></main>;
  }

  return (
    <main className="content">
      <div className="page-header">
        <div>
          <h1 className="page-title">Crianças e turmas</h1>
          <p className="page-subtitle">{turmas.length} turmas · {totalCriancas} crianças</p>
        </div>
      </div>

      <div className="summary-bar">
        <div className="summary-item"><div className="summary-label">Turmas</div><div className="summary-value">{turmas.length}</div></div>
        <div className="summary-item"><div className="summary-label">Crianças</div><div className="summary-value">{totalCriancas}</div></div>
        <div className="summary-item"><div className="summary-label">Professoras</div><div className="summary-value">{professores.length}</div></div>
        <div className="summary-item"><div className="summary-label">Relatórios finalizados</div><div className="summary-value">{totalRelatorios}</div></div>
      </div>

      <div className="filter-bar">
        <div className="search-box">
          <svg className="search-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="7" /><path d="m21 21-4.3-4.3" /></svg>
          <input className="search-input" type="text" placeholder="Buscar turma ou professora…" value={search} onChange={(e) => setSearch(e.target.value)} />
        </div>
        <span className="filter-label">Nível:</span>
        <button className={`filter-chip ${nivel === 'all' ? 'active' : ''}`} onClick={() => setNivel('all')}>Todos</button>
        {niveis.map((n) => (
          <button key={n} className={`filter-chip ${nivel === n ? 'active' : ''}`} onClick={() => setNivel(n)}>{n}</button>
        ))}
      </div>

      {filtered.length === 0 && <div className="empty-hint">Nenhuma turma encontrada.</div>}

      <div className="turmas-grid">
        {filtered.map((t) => (
          <div className="turma-card" key={t.id} onClick={() => navigate(`/coordenacao/turmas/${t.id}`)}>
            <div className="turma-header">
              <div className="turma-identity">
                <div className="turma-badge">{turmaBadge(t.nome)}</div>
                <div>
                  <div className="turma-name">{t.nome}</div>
                  <div className="turma-meta">Prof. {t.prof} · {t.criancas} crianças</div>
                </div>
              </div>
              <span className={`pill ${t.registros > 0 ? 'pill-ok' : 'pill-warn'}`}>{t.registros > 0 ? 'Ativa' : 'Sem registros'}</span>
            </div>
            <div className="turma-inventory">
              <div className="inv-mini"><div className="inv-mini-icon">🧒</div><div className="inv-mini-value">{t.criancas}</div><div className="inv-mini-label">Crianças</div></div>
              <div className="inv-mini"><div className="inv-mini-icon">📝</div><div className="inv-mini-value">{t.registros}</div><div className="inv-mini-label">Registros</div></div>
              <div
                className="inv-mini"
                title={t.coberturaTotal
                  ? `${t.cobertura} de ${t.coberturaTotal} pares criança×habilidade observados (${t.criancas} crianças × habilidades da faixa)`
                  : 'Sem habilidades BNCC cadastradas para a faixa desta turma'}
              >
                <div className="inv-mini-icon">📍</div>
                <div className="inv-mini-value">
                  {t.coberturaTotal ? `${Math.round((t.cobertura / t.coberturaTotal) * 100)}%` : '—'}
                </div>
                <div className="inv-mini-label">Cobertura BNCC</div>
              </div>
              <div className="inv-mini"><div className="inv-mini-icon">📊</div><div className="inv-mini-value">{t.relatorios}</div><div className="inv-mini-label">Relatórios</div></div>
            </div>
            <div className="turma-footer">
              <div className="turma-footer-info">Ver inventário por aluno</div>
              <svg className="turma-arrow" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M9 18l6-6-6-6" /></svg>
            </div>
          </div>
        ))}
      </div>
    </main>
  );
}
