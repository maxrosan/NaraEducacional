import React, { useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useCoordinatorData } from '@/components/coordinator/v2/CoordinatorDataContext';
import './bncc.css';

const turmaBadge = (nome = '') => {
  const num = (nome.match(/\d+/) || [''])[0];
  const letters = nome.match(/[A-Z]/g) || [];
  return num ? `${num}${letters[letters.length - 1] || ''}` : (nome.replace(/[^A-Za-zÀ-ú]/g, '').slice(0, 2).toUpperCase() || '–');
};

const campoMeta = (campo = '') => {
  const c = campo.toLowerCase();
  if (c.includes('corpo')) return { cls: 'corpo', emoji: '🏃' };
  if (c.includes('eu') || c.includes('outro')) return { cls: 'eu', emoji: '👥' };
  if (c.includes('escuta') || c.includes('fala') || c.includes('língua') || c.includes('lingua')) return { cls: 'escuta', emoji: '💭' };
  if (c.includes('espaço') || c.includes('espaco') || c.includes('quantidade') || c.includes('matem')) return { cls: 'espacos', emoji: '🔢' };
  if (c.includes('traço') || c.includes('traco') || c.includes('cor')) return { cls: 'tracos', emoji: '🎨' };
  return { cls: 'eu', emoji: '•' };
};

export default function BnccPorTurmaPage() {
  const { turmaId } = useParams();
  const navigate = useNavigate();
  const { loading, dashboardData, viewData } = useCoordinatorData();

  const turma = (viewData?.turmas || []).find((t) => String(t.id) === String(turmaId));
  const porTurmaCampo = dashboardData?.indicadores?.por_turma_campo || {};
  const campos = porTurmaCampo[String(turmaId)] || porTurmaCampo[turmaId] || {};

  const rows = useMemo(() => {
    const total = Object.values(campos).reduce((s, n) => s + (n || 0), 0);
    return Object.entries(campos)
      .map(([campo, count]) => ({ campo, count, pct: total > 0 ? Math.round((count / total) * 100) : 0, ...campoMeta(campo) }))
      .sort((a, b) => b.count - a.count);
  }, [campos]);

  if (loading || !dashboardData) {
    return <main className="content"><div className="coord-loader"><div className="coord-spin" /></div></main>;
  }

  return (
    <main className="content">
      <div className="breadcrumb">
        <button onClick={() => navigate('/coordenacao/aprendizagens')}>Aprendizagens consolidadas</button>
        <span className="breadcrumb-sep">›</span>
        <span>{turma?.nome || 'Turma'} · BNCC</span>
      </div>

      <section className="turma-hero">
        <div className="turma-hero-badge">{turmaBadge(turma?.nome || '')}</div>
        <div className="turma-hero-info">
          <div className="turma-hero-name">{turma?.nome || 'Turma'}</div>
          <div className="turma-hero-meta">Distribuição dos registros pelos campos de experiência da BNCC</div>
        </div>
      </section>

      <section className="section">
        <div className="section-head">
          <div>
            <h2 className="section-title">Cobertura BNCC por campo</h2>
            <p className="section-subtitle">% dos registros da turma em cada campo de experiência</p>
          </div>
        </div>

        {rows.length === 0 ? (
          <div className="empty-hint">Sem registros BNCC para esta turma no cache.</div>
        ) : (
          rows.map((r) => (
            <div className="field-row" key={r.campo}>
              <div className="field-row-head">
                <span className="field-row-name"><span className={`field-circle b-${r.cls}`} /> {r.emoji} {r.campo}</span>
                <span className="field-row-value">{r.count} reg. · {r.pct}%</span>
              </div>
              <div className="field-bar"><div className={`field-bar-fill b-${r.cls}`} style={{ width: `${r.pct}%` }} /></div>
            </div>
          ))
        )}
      </section>

      <div className="ai-disclaimer" style={{ marginTop: 4, padding: '16px 20px', background: 'var(--amber-bg)', borderRadius: 14, borderLeft: '4px solid var(--amber)', fontSize: 12.5, lineHeight: 1.5 }}>
        <div><strong style={{ color: 'var(--amber)' }}>Nota:</strong> mostra a distribuição dos registros por campo (dado real do cache). A cobertura "realizado ÷ planejado" por turma depende de cruzar com as habilidades dos planejamentos, ainda não disponível no cache.</div>
      </div>
    </main>
  );
}
