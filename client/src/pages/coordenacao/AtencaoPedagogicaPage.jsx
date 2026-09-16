import React, { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useCoordinatorData } from '@/components/coordinator/v2/CoordinatorDataContext';
import { useToast } from '@/components/ui/use-toast';
import './atencao.css';

const PAGE_SIZE = 15;

const KindIcon = ({ kind }) => {
  if (kind === 'warning') return <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" /><path d="M12 9v4M12 17h.01" /></svg>;
  if (kind === 'info') return <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="9" /><path d="M12 16v-4M12 8h.01" /></svg>;
  return <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="9" /><path d="M12 8v4M12 16h.01" /></svg>;
};

const kindClass = (k) => (k === 'warning' ? 'warn' : k === 'info' ? 'info' : 'crit');
const kindLabel = (k) => (k === 'warning' ? 'Atenção' : k === 'info' ? 'Informativo' : 'Crítico');

const TYPE_FILTERS = [
  { key: 'all', label: 'Todos' },
  { key: 'critical', label: 'Crítico' },
  { key: 'warning', label: 'Atenção' },
];

export default function AtencaoPedagogicaPage() {
  const { loading, dashboardData, viewData } = useCoordinatorData();
  const { toast } = useToast();
  const navigate = useNavigate();
  const [typeF, setTypeF] = useState('all');
  const [page, setPage] = useState(0);

  const alerts = viewData?.alerts || [];

  const criticos = alerts.filter((a) => (a.kind || 'critical') === 'critical').length;
  const atencao = alerts.filter((a) => a.kind === 'warning').length;
  const informativos = alerts.filter((a) => a.kind === 'info').length;

  const filtered = useMemo(() => {
    return alerts.filter((a) => typeF === 'all' || (a.kind || 'critical') === typeF);
  }, [alerts, typeF]);

  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const pageSafe = Math.min(page, pageCount - 1);
  const rows = filtered.slice(pageSafe * PAGE_SIZE, pageSafe * PAGE_SIZE + PAGE_SIZE);

  const acao = (msg) => toast({ title: 'Ação registrada', description: msg });

  if (loading || !dashboardData) {
    return <main className="content"><div className="coord-loader"><div className="coord-spin" /></div></main>;
  }

  return (
    <main className="content">
      <div className="page-header">
        <div>
          <h1 className="page-title">Atenção pedagógica</h1>
          <p className="page-subtitle">Sinais detectados pela Nara a partir dos registros da equipe</p>
        </div>
      </div>

      <div className="atn-summary-bar">
        <div className="atn-summary-item">
          <div className="atn-summary-icon crit"><KindIcon kind="critical" /></div>
          <div className="atn-summary-info"><div className="atn-summary-label">Críticos</div><div className="atn-summary-value">{criticos}</div></div>
        </div>
        <div className="atn-summary-item">
          <div className="atn-summary-icon warn"><KindIcon kind="warning" /></div>
          <div className="atn-summary-info"><div className="atn-summary-label">Atenção</div><div className="atn-summary-value">{atencao}</div></div>
        </div>
        <div className="atn-summary-item">
          <div className="atn-summary-icon info"><KindIcon kind="info" /></div>
          <div className="atn-summary-info"><div className="atn-summary-label">Informativos</div><div className="atn-summary-value">{informativos}</div></div>
        </div>
      </div>

      <div className="filter-bar">
        <span className="filter-label">Tipo:</span>
        {TYPE_FILTERS.map((f) => (
          <button key={f.key} className={`filter-chip ${typeF === f.key ? 'active' : ''}`} onClick={() => { setTypeF(f.key); setPage(0); }}>{f.label}</button>
        ))}
      </div>

      {filtered.length === 0 && <div className="empty-hint">Nenhum sinal de atenção no momento. 🎉</div>}

      {rows.map((a) => {
        const k = kindClass(a.kind);
        return (
          <div className={`alert-card ${k}`} key={a.id}>
            <div className="alert-head">
              <div className="alert-icon-circle"><KindIcon kind={a.kind || 'critical'} /></div>
              <div className="alert-content">
                <div className="alert-meta-top">
                  <span className="alert-pill">{kindLabel(a.kind)}</span>
                  {a.turma_nome && <span className="alert-time">{a.turma_nome}</span>}
                </div>
                <h3 className="alert-title">{a.crianca_nome ? a.crianca_nome : a.title}</h3>
                <p className="alert-desc">{a.description}</p>
              </div>
            </div>
            <div className="alert-actions">
              {a.type === 'registro' ? (
                <button className="action-btn primary" onClick={() => acao(`Lembrete enviado sobre ${a.crianca_nome || 'a criança'}.`)}>{a.action || 'Lembrar professor(a)'}</button>
              ) : (
                <button className="action-btn primary" onClick={() => acao(`Professor(a) ${a.teacher || ''} notificado(a).`)}>{a.action || 'Notificar professor(a)'}</button>
              )}
              <button className="action-btn" onClick={() => navigate('/coordenacao/professoras')}>Ver equipe</button>
              <button className="action-btn" onClick={() => acao('Sinal arquivado.')}>Arquivar</button>
            </div>
          </div>
        );
      })}

      {pageCount > 1 && (
        <div className="coord-pager">
          <button disabled={pageSafe === 0} onClick={() => setPage(pageSafe - 1)}>Anterior</button>
          <span>Página {pageSafe + 1} de {pageCount}</span>
          <button disabled={pageSafe >= pageCount - 1} onClick={() => setPage(pageSafe + 1)}>Próxima</button>
        </div>
      )}

      <div className="ai-disclaimer">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0, color: 'var(--amber)' }}><circle cx="12" cy="12" r="9" /><path d="M12 8v4M12 16h.01" /></svg>
        <div><strong>Sinais, não veredictos.</strong> A Nara aponta padrões a partir do que foi registrado para apoiar a conversa pedagógica — a leitura final é sempre da coordenação e da professora.</div>
      </div>
    </main>
  );
}
