import React, { useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useCoordinatorData } from '@/components/coordinator/v2/CoordinatorDataContext';
import { safeFormatDate } from '@/lib/dateUtils';
import './turmaDetalhe.css';

const initials = (nome = '') => nome.trim().split(/\s+/).slice(0, 2).map((w) => w[0] || '').join('').toUpperCase() || '–';
const turmaBadge = (nome = '') => {
  const num = (nome.match(/\d+/) || [''])[0];
  const letters = nome.match(/[A-Z]/g) || [];
  return num ? `${num}${letters[letters.length - 1] || ''}` : (nome.replace(/[^A-Za-zÀ-ú]/g, '').slice(0, 2).toUpperCase() || '–');
};

export default function TurmaDetalhePage() {
  const { turmaId } = useParams();
  const navigate = useNavigate();
  const { loading, dashboardData, viewData } = useCoordinatorData();

  const turma = (viewData?.turmas || []).find((t) => String(t.id) === String(turmaId));
  const recentes = new Set(dashboardData?.criancasRecentesIds || []);
  const profRecente = dashboardData?.professorRecentePorCrianca || {};
  const comRelatorio = new Set(dashboardData?.criancasRelatorioFinalizadoIds || []);

  const alunos = useMemo(() => {
    const cris = (viewData?.criancas || []).filter((c) => String(c.turma_id) === String(turmaId));
    return cris.map((c) => {
      const pr = profRecente[String(c.id)] || {};
      return {
        id: c.id,
        nome: c.nome_completo,
        recente: recentes.has(String(c.id)),
        ultimaObs: pr.data || null,
        ultimoProf: pr.nome || null,
        relatorioFinalizado: comRelatorio.has(String(c.id)),
      };
    }).sort((a, b) => (a.nome || '').localeCompare(b.nome || '', 'pt'));
  }, [viewData, turmaId, recentes, profRecente, comRelatorio]);

  if (loading || !dashboardData) {
    return <main className="content"><div className="coord-loader"><div className="coord-spin" /></div></main>;
  }

  const profsDaTurma = (dashboardData.professores || []).filter((p) => (p.turmas || []).includes(turma?.nome)).map((p) => p.nome);

  return (
    <main className="content">
      <div className="breadcrumb">
        <button onClick={() => navigate('/coordenacao/turmas')}>Crianças e turmas</button>
        <span className="breadcrumb-sep">›</span>
        <span>{turma?.nome || 'Turma'}</span>
      </div>

      <section className="turma-hero">
        <div className="turma-hero-badge">{turmaBadge(turma?.nome || '')}</div>
        <div className="turma-hero-info">
          <div className="turma-hero-name">{turma?.nome || 'Turma'}</div>
          <div className="turma-hero-meta">
            {profsDaTurma.length > 0 ? <>Prof. <strong>{profsDaTurma.join(', ')}</strong> · </> : null}
            <strong>{alunos.length} crianças</strong>
          </div>
        </div>
        <button className="btn btn-primary" onClick={() => navigate('/coordenacao/relatorios')}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><path d="M14 2v6h6" /></svg>
          Relatórios da turma
        </button>
      </section>

      <section className="section">
        <div className="section-head">
          <div>
            <h2 className="section-title">Inventário por aluno</h2>
            <p className="section-subtitle">Clique em um aluno para abrir o perfil · {alunos.length} crianças</p>
          </div>
        </div>

        {alunos.length === 0 ? (
          <div className="empty-hint">Nenhuma criança vinculada a esta turma.</div>
        ) : (
          <div className="table-wrap">
            <table className="coord-table">
              <thead>
                <tr>
                  <th>Aluno</th>
                  <th>Registro recente</th>
                  <th>Última observação</th>
                  <th>Último(a) professor(a)</th>
                  <th>Relatório</th>
                </tr>
              </thead>
              <tbody>
                {alunos.map((a) => (
                  <tr key={a.id} style={{ cursor: 'pointer' }} onClick={() => navigate(`/coordenacao/crianca/${a.id}`)}>
                    <td>
                      <div className="aluno-info">
                        <div className="aluno-avatar">{initials(a.nome)}</div>
                        <div className="aluno-nome">{a.nome}</div>
                      </div>
                    </td>
                    <td><span className={`pill ${a.recente ? 'pill-ok' : 'pill-critical'}`}>{a.recente ? 'Em dia' : 'Há +15 dias'}</span></td>
                    <td>{a.ultimaObs ? safeFormatDate(a.ultimaObs, 'dd/MM/yyyy') : '—'}</td>
                    <td>{a.ultimoProf || '—'}</td>
                    <td><span className={`pill ${a.relatorioFinalizado ? 'pill-ok' : 'pill-warn'}`}>{a.relatorioFinalizado ? 'Finalizado' : 'Pendente'}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </main>
  );
}
