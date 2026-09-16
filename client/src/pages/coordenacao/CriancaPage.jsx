import React, { useEffect, useMemo, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useCoordinatorData } from '@/components/coordinator/v2/CoordinatorDataContext';
import { useAuth } from '@/contexts/AuthContext';
import { safeFormatDate, getCurrentBimester, fetchPeriodosAvaliativos } from '@/lib/dateUtils';
import { authFetch, API_BASE_URL } from '@/services/api';
import WeeklyPlanningsBlock from '@/components/report/WeeklyPlanningsBlock';
import IndividualReportBlock from '@/components/report/IndividualReportBlock';
import ProductionAnalysisBlock from '@/components/report/ProductionAnalysisBlock';
import ReadingAnalysisBlock from '@/components/report/ReadingAnalysisBlock';
import PortfolioGalleryBlock from '@/components/report/PortfolioGalleryBlock';
import SkillsMatrixBlock from '@/components/report/SkillsMatrixBlock';
import ReportsBlock from '@/components/report/ReportsBlock';
import './crianca.css';

const initials = (nome = '') => nome.trim().split(/\s+/).slice(0, 2).map((w) => w[0] || '').join('').toUpperCase() || '–';

export default function CriancaPage() {
  const { criancaId } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const { loading, dashboardData, viewData } = useCoordinatorData();

  const instituicaoId = user?.user_metadata?.instituicao_id ?? user?.instituicao_id ?? null;

  const crianca = useMemo(() => (viewData?.criancas || []).find((c) => String(c.id) === String(criancaId)), [viewData, criancaId]);
  const turma = (viewData?.turmas || []).find((t) => String(t.id) === String(crianca?.turma_id));
  const recente = (dashboardData?.criancasRecentesIds || []).includes(String(criancaId));
  const pr = (dashboardData?.professorRecentePorCrianca || {})[String(criancaId)] || {};
  const temRelatorioFinalizado = (dashboardData?.criancasRelatorioFinalizadoIds || []).includes(String(criancaId));

  // Conteúdo pedagógico carregado direto do banco (não do cache), por período.
  const [periodos, setPeriodos] = useState([]);
  const [selectedPeriodo, setSelectedPeriodo] = useState(null);
  const [portfolioItems, setPortfolioItems] = useState([]);

  useEffect(() => {
    if (!instituicaoId) return;
    let cancel = false;
    (async () => {
      try {
        const [bimestre, todos] = await Promise.all([
          getCurrentBimester(instituicaoId),
          fetchPeriodosAvaliativos(instituicaoId),
        ]);
        if (cancel) return;
        setPeriodos(todos || []);
        setSelectedPeriodo(bimestre || (todos && todos.length ? todos[todos.length - 1] : null));
      } catch (e) {
        if (!cancel) console.error('Erro ao carregar períodos:', e);
      }
    })();
    return () => { cancel = true; };
  }, [instituicaoId]);

  useEffect(() => {
    if (!crianca?.turma_id || !criancaId || !selectedPeriodo) { setPortfolioItems([]); return; }
    let cancel = false;
    (async () => {
      try {
        const params = new URLSearchParams({ turma_id: crianca.turma_id, crianca_id: criancaId });
        if (selectedPeriodo.data_inicio) params.set('data_inicio', selectedPeriodo.data_inicio);
        if (selectedPeriodo.data_fim) params.set('data_fim', selectedPeriodo.data_fim);
        const r = await authFetch(`${API_BASE_URL}/portfolio/listar/?${params.toString()}`);
        if (!r.ok) throw new Error('Erro ao buscar portfólio');
        const data = await r.json();
        if (cancel) return;
        setPortfolioItems((data.producoes || []).map((p) => ({ id: p.id, url: p.arquivo_url, tag: p.tags || p.tipo_midia || '' })));
      } catch (e) {
        if (!cancel) { console.error('Erro ao carregar portfólio:', e); setPortfolioItems([]); }
      }
    })();
    return () => { cancel = true; };
  }, [crianca?.turma_id, criancaId, selectedPeriodo]);

  if (loading || !dashboardData) {
    return <main className="content"><div className="coord-loader"><div className="coord-spin" /></div></main>;
  }

  if (!crianca) {
    return (
      <main className="content">
        <div className="breadcrumb"><button onClick={() => navigate('/coordenacao/turmas')}>Crianças e turmas</button></div>
        <div className="empty-hint">Criança não encontrada.</div>
      </main>
    );
  }

  return (
    <main className="content">
      <div className="breadcrumb">
        <button onClick={() => navigate('/coordenacao/turmas')}>Crianças e turmas</button>
        <span className="breadcrumb-sep">›</span>
        {turma && <><button onClick={() => navigate(`/coordenacao/turmas/${turma.id}`)}>{turma.nome}</button><span className="breadcrumb-sep">›</span></>}
        <span>{crianca.nome_completo}</span>
      </div>

      <section className="child-hero">
        <div className="child-avatar">{initials(crianca.nome_completo)}</div>
        <div className="child-identity">
          <h1 className="child-name">{crianca.nome_completo}</h1>
          <div className="child-meta">
            <div className="child-meta-item">📚 <strong>{turma?.nome || 'Sem turma'}</strong></div>
            {pr.nome && <div className="child-meta-item">👩‍🏫 Prof. <strong>{pr.nome}</strong></div>}
            <div className="child-meta-item">🗓️ Registro recente: <strong>{recente ? 'Em dia' : 'Há +15 dias'}</strong></div>
          </div>
        </div>
        <div className="child-actions">
          <button className="btn btn-secondary" onClick={() => navigate('/coordenacao/atencao')}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" /></svg>
            Conversar com a equipe
          </button>
        </div>
      </section>

      {!recente && (
        <div className="child-alert">
          <div className="child-alert-icon"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="9" /><path d="M12 8v4M12 16h.01" /></svg></div>
          <div className="child-alert-body">
            <strong>Atenção pedagógica:</strong> {crianca.nome_completo} não possui registros nos últimos 15 dias. Vale combinar uma observação com a professora responsável.
          </div>
        </div>
      )}

      <section className="section">
        <h2 className="section-title">📂 Acompanhamento</h2>
        <div className="section-subtitle">Informações consolidadas a partir do cache da coordenação</div>
        <div className="inventory-grid" style={{ marginTop: 14 }}>
          <div className="inv-card">
            <div className={`inv-icon ${recente ? 'report' : 'evidence'}`}>🗓️</div>
            <div className="inv-value">{recente ? 'Em dia' : 'Há +15 dias'}</div>
            <div className="inv-label">Registro recente</div>
          </div>
          <div className="inv-card">
            <div className="inv-icon text">📝</div>
            <div className="inv-value">{pr.data ? safeFormatDate(pr.data, 'dd/MM/yyyy') : '—'}</div>
            <div className="inv-label">Última observação</div>
          </div>
          <div className="inv-card">
            <div className="inv-icon audio">👩‍🏫</div>
            <div className="inv-value" style={{ fontSize: 15 }}>{pr.nome || '—'}</div>
            <div className="inv-label">Último(a) professor(a)</div>
          </div>
          <div className="inv-card">
            <div className="inv-icon report">📊</div>
            <div className="inv-value" style={{ fontSize: 15 }}>{temRelatorioFinalizado ? 'Finalizado' : 'Pendente'}</div>
            <div className="inv-label">Relatório do bimestre</div>
          </div>
        </div>
      </section>

      <section className="section">
        <div className="section-head">
          <div>
            <h2 className="section-title">📋 Conteúdo pedagógico da criança</h2>
            <div className="section-subtitle">Mesma visão da professora, somente leitura · carregado do banco</div>
          </div>
          <div className="coord-filters">
            <select
              className="coord-select"
              value={selectedPeriodo?.id || ''}
              onChange={(e) => setSelectedPeriodo(periodos.find((p) => String(p.id) === e.target.value) || null)}
            >
              {periodos.length === 0 && <option value="">Período vigente</option>}
              {periodos.map((p) => <option key={p.id} value={p.id}>{p.descricao}</option>)}
            </select>
          </div>
        </div>

        <div className="child-report-blocks">
          <WeeklyPlanningsBlock turmaId={crianca.turma_id} periodo={selectedPeriodo} />
          {/* Relatos individuais (ObservacaoTranscricao). `isPlaceholder` rende
              só a lista, sem o editor de texto do relatório bimestral. */}
          <IndividualReportBlock
            isPlaceholder
            readOnly
            nomeAluno={crianca.nome_completo}
            criancaId={criancaId}
            periodo={selectedPeriodo}
          />
          <ProductionAnalysisBlock nomeAluno={crianca.nome_completo} periodo={selectedPeriodo} readOnly />
          <ReadingAnalysisBlock criancaId={criancaId} periodo={selectedPeriodo} readOnly />
          <PortfolioGalleryBlock photos={portfolioItems} />
          <SkillsMatrixBlock
            criancaId={criancaId}
            turmaId={crianca.turma_id}
            instituicaoId={instituicaoId}
            selectedPeriodo={selectedPeriodo}
            readOnly
          />
          <ReportsBlock
            studentId={criancaId}
            studentName={crianca.nome_completo}
            turmaId={crianca.turma_id}
            turmaName={turma?.nome || ''}
            instituicaoId={instituicaoId}
            readOnly
          />
        </div>
      </section>
    </main>
  );
}
