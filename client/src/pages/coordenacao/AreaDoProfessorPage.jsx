import React, { useMemo, useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useCoordinatorData } from '@/components/coordinator/v2/CoordinatorDataContext';
import { toValidDate } from '@/lib/dateUtils';
import { formatDistanceToNow } from 'date-fns';
import { ptBR } from 'date-fns/locale';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { perfilLabelDocente } from '@/constants/perfis';

const PAGE_SIZE = 20;

const lastLoginLabel = (last) => {
  const d = toValidDate(last);
  return d ? formatDistanceToNow(d, { addSuffix: true, locale: ptBR }) : 'Nunca acessou';
};

export default function AreaDoProfessorPage() {
  const { loading, dashboardData, viewData } = useCoordinatorData();
  const navigate = useNavigate();
  const professores = useMemo(() => [...(viewData?.professores || [])].sort((a, b) => (a.nome || '').localeCompare(b.nome || '', 'pt')), [viewData]);
  const [sel, setSel] = useState('');

  useEffect(() => { if (!sel && professores.length) setSel(String(professores[0].id)); }, [professores, sel]);

  const prof = professores.find((p) => String(p.id) === String(sel));
  const turmas = viewData?.turmas || [];
  const planning = viewData?.planning || [];
  const criancas = viewData?.criancas || [];
  const alerts = viewData?.alerts || [];
  const comRelatorio = useMemo(() => new Set(dashboardData?.criancasRelatorioFinalizadoIds || []), [dashboardData]);

  const [turmaSel, setTurmaSel] = useState('');

  const [tab, setTab] = useState('todas');

  const [page, setPage] = useState(1);

  useEffect(() => {
    const profAtual = professores.find((p) => String(p.id) === String(sel));
    const nomesTurmasAtual = profAtual?.turmas || [];
    const primeira = turmas.find((t) => nomesTurmasAtual.includes(t.nome));
    setTurmaSel(primeira ? String(primeira.id) : '');
    setTab('todas');
    setPage(1);
  }, [sel]);

  useEffect(() => { setPage(1); }, [turmaSel, tab]);

  const dados = useMemo(() => {
    if (!prof) return null;
    const nomesTurmas = prof.turmas || [];
    const turmaIds = turmas.filter((t) => nomesTurmas.includes(t.nome)).map((t) => String(t.id));
    const planos = planning.filter((p) => String(p.id_professor || p.professora_id) === String(prof.id));
    const planosFin = planos.filter((p) => p.status === 'Finalizado').length;
    const atencaoTodas = alerts.filter((a) => a.type === 'registro' && a.turma_nome && nomesTurmas.includes(a.turma_nome));
    // Relatórios pendentes = crianças das turmas da prof. sem relatório finalizado.
    const relPend = criancas.filter((c) => turmaIds.includes(String(c.turma_id)) && !comRelatorio.has(String(c.id))).length;
    return { nomesTurmas, turmaIds, planos, planosFin, atencaoTodas, relPend };
  }, [prof, turmas, planning, criancas, comRelatorio, alerts]);

  const turmasDoProf = useMemo(
    () => turmas.filter((t) => (dados?.nomesTurmas || []).includes(t.nome)),
    [turmas, dados]
  );

  const turmaSelNome = useMemo(
    () => turmasDoProf.find((t) => String(t.id) === String(turmaSel))?.nome || null,
    [turmasDoProf, turmaSel]
  );

  const atencaoFiltrada = useMemo(() => {
    if (!dados) return [];
    if (!turmaSelNome) return dados.atencaoTodas;
    return dados.atencaoTodas.filter((a) => a.turma_nome === turmaSelNome);
  }, [dados, turmaSelNome]);

  const turmaIdToNome = useMemo(() => {
    const map = new Map();
    turmas.forEach((t) => map.set(String(t.id), t.nome));
    return map;
  }, [turmas]);

  const todasCriancas = useMemo(() => {
    if (!dados) return [];
    const ids = turmaSel ? [String(turmaSel)] : dados.turmaIds;
    return criancas
      .filter((c) => ids.includes(String(c.turma_id)))
      .map((c) => ({ ...c, turma_nome: turmaIdToNome.get(String(c.turma_id)) || '—' }))
      .sort((a, b) => (a.nome_completo || '').localeCompare(b.nome_completo || '', 'pt'));
  }, [criancas, dados, turmaSel, turmaIdToNome]);

  const listaAtiva = tab === 'atencao' ? atencaoFiltrada : todasCriancas;
  const totalPages = Math.max(1, Math.ceil(listaAtiva.length / PAGE_SIZE));

  useEffect(() => {
    if (page > totalPages) setPage(totalPages);
  }, [totalPages, page]);

  const pageStart = listaAtiva.length === 0 ? 0 : (page - 1) * PAGE_SIZE + 1;
  const pageEnd = Math.min(page * PAGE_SIZE, listaAtiva.length);
  const pagedAtencao = tab === 'atencao' ? atencaoFiltrada.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE) : [];
  const pagedTodas = tab === 'todas' ? todasCriancas.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE) : [];

  if (loading || !dashboardData) {
    return <main className="content"><div className="coord-loader"><div className="coord-spin" /></div></main>;
  }

  return (
    <main className="content">
      <div className="page-header">
        <div>
          <h1 className="page-title">Área do professor</h1>
          <p className="page-subtitle">Visão da coordenação sobre o dia a dia de cada professora (somente leitura)</p>
        </div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <select
            className="coord-select"
            value={sel}
            onChange={(e) => setSel(e.target.value)}
            style={{
              padding: '10px 14px',
              borderRadius: 10,
              border: '1px solid #d1d5db',
              background: '#fff',
              color: '#1f2937',
              fontSize: 14,
              fontWeight: 600,
              cursor: 'pointer',
              boxShadow: '0 1px 2px rgba(0,0,0,0.06)',
            }}
          >
            {professores.map((p) => <option key={p.id} value={p.id}>{p.nome}</option>)}
          </select>
          <select
            className="coord-select"
            value={turmaSel}
            onChange={(e) => setTurmaSel(e.target.value)}
            disabled={turmasDoProf.length === 0}
            aria-label="Selecionar turma"
            style={{
              padding: '10px 14px',
              borderRadius: 10,
              border: '1px solid #d1d5db',
              background: turmasDoProf.length === 0 ? '#f3f4f6' : '#fff',
              color: turmasDoProf.length === 0 ? '#9ca3af' : '#1f2937',
              fontSize: 14,
              fontWeight: 600,
              cursor: turmasDoProf.length === 0 ? 'default' : 'pointer',
              boxShadow: '0 1px 2px rgba(0,0,0,0.06)',
            }}
          >
            {turmasDoProf.length === 0 ? (
              <option value="">Sem turma vinculada</option>
            ) : (
              turmasDoProf.map((t) => <option key={t.id} value={t.id}>{t.nome}</option>)
            )}
          </select>
        </div>
      </div>

      {!prof || !dados ? (
        <div className="empty-hint">Selecione uma professora.</div>
      ) : (
        <>
          <div className="summary-bar">
            <div className="summary-item"><div className="summary-label">Turmas</div><div className="summary-value">{dados.nomesTurmas.length}</div></div>
            <div className="summary-item"><div className="summary-label">Planos finalizados (semana)</div><div className="summary-value">{dados.planosFin}<span className="summary-suffix">/{dados.nomesTurmas.length || 1}</span></div></div>
            <div className="summary-item"><div className="summary-label">Crianças em atenção</div><div className="summary-value">{atencaoFiltrada.length}</div></div>
            <div className="summary-item"><div className="summary-label">Relatórios pendentes</div><div className="summary-value">{dados.relPend}</div></div>
          </div>

          <section className="section">
            <div className="section-head">
              <div>
                <h2 className="section-title">{prof.nome}</h2>
                <p className="section-subtitle">{perfilLabelDocente(prof.perfil)} · último acesso {lastLoginLabel(prof.last_login)}</p>
              </div>
            </div>
          </section>

          <section className="section">
            <div className="section-head">
              <div>
                <h2 className="section-title">Crianças</h2>
                <p className="section-subtitle">
                  {turmaSelNome ? <>Turma <strong>{turmaSelNome}</strong> de</> : 'Turmas de'} {prof.nome}
                </p>
              </div>
            </div>

            <div
              role="tablist"
              style={{ display: 'flex', gap: 4, borderBottom: '1px solid var(--border-light, #e5e7eb)', marginBottom: 16 }}
            >
              <button
                type="button"
                role="tab"
                aria-selected={tab === 'todas'}
                onClick={() => setTab('todas')}
                style={{
                  padding: '10px 16px',
                  marginBottom: -1,
                  fontSize: 14,
                  fontWeight: 600,
                  color: tab === 'todas' ? 'var(--purple, #7c3aed)' : '#6b7280',
                  background: 'transparent',
                  border: 'none',
                  borderBottom: tab === 'todas' ? '2px solid var(--purple, #7c3aed)' : '2px solid transparent',
                  cursor: 'pointer',
                }}
              >
                Todas as crianças ({todasCriancas.length})
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={tab === 'atencao'}
                onClick={() => setTab('atencao')}
                style={{
                  padding: '10px 16px',
                  marginBottom: -1,
                  fontSize: 14,
                  fontWeight: 600,
                  color: tab === 'atencao' ? 'var(--purple, #7c3aed)' : '#6b7280',
                  background: 'transparent',
                  border: 'none',
                  borderBottom: tab === 'atencao' ? '2px solid var(--purple, #7c3aed)' : '2px solid transparent',
                  cursor: 'pointer',
                }}
              >
                Precisam de atenção ({atencaoFiltrada.length})
              </button>
            </div>

            {tab === 'atencao' ? (
              atencaoFiltrada.length === 0 ? (
                <div className="empty-hint">Nenhuma criança sem registro recente. 🎉</div>
              ) : (
                <div className="table-wrap">
                  <table className="coord-table">
                    <thead><tr><th>Criança</th><th>Turma</th><th>Situação</th></tr></thead>
                    <tbody>
                      {pagedAtencao.map((a) => (
                        <tr key={a.id} style={{ cursor: 'pointer' }} onClick={() => a.crianca_id && navigate(`/coordenacao/crianca/${a.crianca_id}`)}>
                          <td className="td-strong">
                            {a.crianca_nome}
                            <span className="pill pill-critical" style={{ marginLeft: 8 }}>Atenção</span>
                          </td>
                          <td>{a.turma_nome}</td>
                          <td><span className="pill pill-critical">Há +15 dias</span></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )
            ) : (
              todasCriancas.length === 0 ? (
                <div className="empty-hint">Nenhuma criança encontrada.</div>
              ) : (
                <div className="table-wrap">
                  <table className="coord-table">
                    <thead><tr><th>Criança</th><th>Turma</th></tr></thead>
                    <tbody>
                      {pagedTodas.map((c) => (
                        <tr key={c.id} style={{ cursor: 'pointer' }} onClick={() => navigate(`/coordenacao/crianca/${c.id}`)}>
                          <td className="td-strong">{c.nome_completo}</td>
                          <td>{c.turma_nome}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )
            )}

            {listaAtiva.length > PAGE_SIZE && (
              <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: 12, marginTop: 16, paddingTop: 16, borderTop: '1px solid var(--border-light, #e5e7eb)' }}>
                <span style={{ fontSize: 13, color: '#6b7280' }}>
                  Exibindo {pageStart}–{pageEnd} de {listaAtiva.length} criança{listaAtiva.length > 1 ? 's' : ''}
                </span>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <button
                    type="button"
                    className="filter-chip"
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                    disabled={page === 1}
                    style={{ display: 'inline-flex', alignItems: 'center', gap: 4, opacity: page === 1 ? 0.5 : 1, cursor: page === 1 ? 'default' : 'pointer' }}
                  >
                    <ChevronLeft size={14} /> Anterior
                  </button>
                  <span style={{ fontSize: 13, color: '#6b7280' }}>Página {page} de {totalPages}</span>
                  <button
                    type="button"
                    className="filter-chip"
                    onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                    disabled={page === totalPages}
                    style={{ display: 'inline-flex', alignItems: 'center', gap: 4, opacity: page === totalPages ? 0.5 : 1, cursor: page === totalPages ? 'default' : 'pointer' }}
                  >
                    Próxima <ChevronRight size={14} />
                  </button>
                </div>
              </div>
            )}
          </section>
        </>
      )}
    </main>
  );
}