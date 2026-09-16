import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useCoordinatorData } from '@/components/coordinator/v2/CoordinatorDataContext';
import { apiService, authFetch, API_BASE_URL } from '@/services/api';
import { useToast } from '@/components/ui/use-toast';
import { parseISO, isValid } from 'date-fns';
import { useReportGeneration } from '@/hooks/useReportGeneration';
import ReportGenerationLoading from '@/components/report/ReportGenerationLoading';
import ReportEditorModal from '@/components/report/ReportEditorModal';
import ViewReportModal from '@/components/report/ViewReportModal';

const PAGE_SIZE = 25;
const MIN_MODAL_MS = 650; // tempo mínimo visível do modal "Baixando…" (evita piscar quando o PDF já está em cache)
const FETCH_CHUNK = 100; // tamanho de página ao buscar TODOS os relatórios do período (ver fetchTodosRelatorios)

const bimestreLabel = (periodo) => {
  if (!periodo) return '—';
  let dt = null;
  if (typeof periodo === 'string') dt = parseISO(periodo);
  else if (periodo instanceof Date) dt = periodo;
  if (dt && isValid(dt)) {
    const m = dt.getMonth() + 1;
    const b = m <= 3 ? 1 : m <= 6 ? 2 : m <= 9 ? 3 : 4;
    return `${b}º Bimestre`;
  }
  return String(periodo);
};

/**
 * Botão de ação para um aluno que ainda não tem relatório gerado no período
 * selecionado. Reaproveita o mesmo hook usado pelo professor (ReportHeader.jsx):
 * gera com IA -> abre o editor pra revisão -> salva.
 */
function GerarRelatorioAction({ aluno, periodo, onGerado }) {
  const {
    isEditorOpen,
    loading,
    loadingStep,
    generatedReport,
    closeEditor,
    handleGenerateReport,
    handleSaveReport,
  } = useReportGeneration(aluno.id, aluno.nome, onGerado, periodo?.descricao);

  const handleClick = () => {
    if (!periodo) return;
    handleGenerateReport(periodo);
  };

  return (
    <>
      <button
        className="icon-btn"
        style={{ width: 'auto', padding: '0 10px', gap: 6, whiteSpace: 'nowrap' }}
        title={periodo ? 'Gerar relatório para este período' : 'Selecione um período'}
        disabled={loading || !periodo}
        onClick={handleClick}
      >
        {loading ? 'Gerando…' : 'Gerar relatório'}
      </button>

      {loading && (
        <ReportGenerationLoading step={loadingStep} studentName={aluno.nome} />
      )}

      <ReportEditorModal
        isOpen={isEditorOpen}
        onClose={closeEditor}
        onSave={handleSaveReport}
        reportData={generatedReport}
        studentName={aluno.nome}
        period={generatedReport?.period}
      />
    </>
  );
}

export default function RelatoriosPage() {
  const { loading, dashboardData, viewData, user, periodoId, intervalo, periodoInfo } = useCoordinatorData();
  const { toast } = useToast();
  const [turma, setTurma] = useState('all');
  const [status, setStatus] = useState('all');
  const [page, setPage] = useState(0);
  const [baixando, setBaixando] = useState(null);

  // Todos os relatórios do período/turma selecionados (não paginado no
  // servidor: buscamos todas as páginas e paginamos no cliente depois de
  // cruzar com a lista de alunos — ver comentário em fetchTodosRelatorios).
  const [relatorios, setRelatorios] = useState([]);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState(false);
  const [refreshTick, setRefreshTick] = useState(0);
  const [linhaEditando, setLinhaEditando] = useState(null);

  const turmas = viewData?.turmas || [];
  const criancas = viewData?.criancas || [];
  const instId = user?.user_metadata?.instituicao_id ?? user?.instituicao_id ?? null;

  const turmasById = useMemo(() => new Map(turmas.map((t) => [String(t.id), t.nome])), [turmas]);

  // Resolve o nome do professor: revisado_por -> mapa de professoras;
  // senão, professor do registro mais recente (cache); senão "—".
  const profById = useMemo(() => {
    const m = new Map();
    (dashboardData?.professores || []).forEach((p) => m.set(String(p.id), p.nome));
    return m;
  }, [dashboardData]);
  const profRecente = dashboardData?.professorRecentePorCrianca || {};
  const nomeProfessor = (r) =>
    (r.revisado_por && profById.get(String(r.revisado_por))) ||
    profRecente[String(r.id_crianca)]?.nome ||
    '—';

  // Busca TODOS os relatórios do período/turma selecionados (percorre as
  // páginas do endpoint existente até esgotar). Precisamos do conjunto
  // completo — não só da página atual — porque o cruzamento com a lista de
  // alunos (para mostrar quem ainda não tem relatório) é feito no cliente.
  const fetchTodosRelatorios = useCallback(async () => {
    if (!instId) return [];
    let acc = [];
    let offset = 0;
    // eslint-disable-next-line no-constant-condition
    while (true) {
      const params = new URLSearchParams({
        instituicao_id: instId,
        limit: String(FETCH_CHUNK),
        offset: String(offset),
        ordering: '-data_criacao',
      });
      if (turma !== 'all') params.set('turma_id', turma);
      if (intervalo) {
        params.set('data_inicio', intervalo.inicio);
        params.set('data_fim', intervalo.fim);
      } else if (periodoId) {
        params.set('periodo_id', periodoId);
      }
      const res = await authFetch(`${API_BASE_URL}/relatorios/coordenacao/?${params.toString()}`);
      if (!res.ok) throw new Error('Falha ao carregar relatórios');
      const data = await res.json();
      const results = data.results || [];
      acc = acc.concat(results);
      const total = typeof data.count === 'number' ? data.count : acc.length;
      if (results.length < FETCH_CHUNK || acc.length >= total) break;
      offset += FETCH_CHUNK;
    }
    return acc;
  }, [instId, turma, periodoId, intervalo]);

  useEffect(() => {
    if (!instId) return;
    let cancel = false;
    setCarregando(true);
    setErro(false);
    fetchTodosRelatorios()
      .then((results) => { if (!cancel) setRelatorios(results); })
      .catch((e) => {
        if (cancel) return;
        console.error(e);
        setErro(true);
        setRelatorios([]);
      })
      .finally(() => { if (!cancel) setCarregando(false); });
    return () => { cancel = true; };
  }, [fetchTodosRelatorios, refreshTick]);

  // Reseta a página ao trocar qualquer filtro (turma, status ou período global).
  useEffect(() => { setPage(0); }, [turma, status, periodoId, intervalo]);

  // Lista completa: um item por aluno da turma filtrada, com o relatório
  // correspondente (se existir) para o período selecionado. Isto substitui a
  // listagem antiga, que só mostrava alunos que já tinham relatório.
  const alunosComRelatorio = useMemo(() => {
    const alunosFiltrados = criancas.filter(
      (c) => turma === 'all' || String(c.turma_id) === String(turma)
    );
    const relatorioPorAluno = new Map(relatorios.map((r) => [String(r.id_crianca), r]));

    return alunosFiltrados
      .map((aluno) => {
        const report = relatorioPorAluno.get(String(aluno.id)) || null;
        return {
          id: report ? `rel-${report.id}` : `aluno-${aluno.id}`,
          aluno: { id: aluno.id, nome: aluno.nome_completo, turma_id: aluno.turma_id },
          turma_nome: turmasById.get(String(aluno.turma_id)) || '—',
          report,
        };
      })
      .sort((a, b) => (a.aluno.nome || '').localeCompare(b.aluno.nome || '', 'pt-BR'));
  }, [criancas, turma, relatorios, turmasById]);

  const linhasFiltradas = useMemo(() => {
    if (status === 'all') return alunosComRelatorio;
    if (status === 'fin') return alunosComRelatorio.filter((l) => l.report?.finalizado);
    // 'pend': sem relatório OU relatório ainda não finalizado.
    return alunosComRelatorio.filter((l) => !l.report?.finalizado);
  }, [alunosComRelatorio, status]);

  const total = linhasFiltradas.length;
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const rows = useMemo(
    () => linhasFiltradas.slice(page * PAGE_SIZE, page * PAGE_SIZE + PAGE_SIZE),
    [linhasFiltradas, page]
  );

  const handleDownload = async (r) => {
    if (!r.finalizado) {
      toast({ variant: 'destructive', title: 'Relatório não finalizado', description: 'Só é possível baixar relatórios finalizados.' });
      return;
    }
    setBaixando(r.id);
    const inicio = Date.now();
    try {
      // baixarPdfRelatorio só faz o fetch e devolve { blob, filename } — quem
      // dispara o download no navegador é aqui (object URL + <a download>).
      const { blob, filename } = await apiService.baixarPdfRelatorio(r.id);
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = filename || `relatorio_${r.id}.pdf`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (e) {
      console.error(e);
      toast({ variant: 'destructive', title: 'Erro ao baixar', description: e?.message || 'Não foi possível gerar o PDF.' });
    } finally {
      // Mantém o modal "Baixando…" visível por um tempo mínimo (não atrasa o
      // download, só o fechamento — evita piscar quando o PDF já está em cache).
      const restante = MIN_MODAL_MS - (Date.now() - inicio);
      if (restante > 0) await new Promise((res) => setTimeout(res, restante));
      setBaixando(null);
    }
  };

  // Chamado pelo GerarRelatorioAction após salvar um relatório novo: refaz a
  // busca para a linha do aluno passar a mostrar "Baixar" em vez de "Gerar".
  const handleRelatorioGerado = () => setRefreshTick((t) => t + 1);

  if (loading || !dashboardData) {
    return <main className="content"><div className="coord-loader"><div className="coord-spin" /></div></main>;
  }

  return (
    <main className="content">
      <div className="page-header">
        <div>
          <h1 className="page-title">Relatórios</h1>
          <p className="page-subtitle">
            Relatórios pedagógicos por aluno{periodoInfo?.descricao ? ` · ${periodoInfo.descricao}` : ''}
          </p>
        </div>
      </div>

      {/* RESUMO (contadores via cache — não dependem da lista paginada) */}
      <div className="summary-bar">
        <div className="summary-item purple">
          {/* `reportsTotal` é o nº de CRIANÇAS ativas, não de relatórios —
              é o denominador ("quantos se espera"), não um total realizado. */}
          <div className="summary-label">Relatórios previstos</div>
          <div className="summary-value">{dashboardData.reportsTotal}</div>
          <div className="summary-detail">um por aluno ativo</div>
        </div>
        <div className="summary-item green">
          <div className="summary-label">Finalizados</div>
          <div className="summary-value">{dashboardData.reportsFinished}</div>
          <div className="summary-detail">{Math.round(dashboardData.reportProgress)}% concluídos</div>
        </div>
        <div className="summary-item amber">
          <div className="summary-label">Pendentes</div>
          <div className="summary-value">{dashboardData.reportsPending}</div>
          <div className="summary-detail">ainda sem finalização</div>
        </div>
        <div className="summary-item green">
          <div className="summary-label">Progresso</div>
          <div className="summary-value">{Math.round(dashboardData.reportProgress)}<span className="summary-suffix">%</span></div>
          <div className="progress-bar" style={{ marginTop: 8 }}><div className="progress-bar-fill green" style={{ width: `${Math.round(dashboardData.reportProgress)}%` }} /></div>
        </div>
      </div>

      <section className="section">
        <div className="section-head">
          <div>
            <h2 className="section-title">Relatórios por aluno</h2>
            <p className="section-subtitle">{total} {total === 1 ? 'aluno' : 'alunos'} · ordenados por nome</p>
          </div>
          <div className="coord-filters">
            <select className="coord-select" value={turma} onChange={(e) => setTurma(e.target.value)}>
              <option value="all">Todas as turmas</option>
              {turmas.map((t) => <option key={t.id} value={t.id}>{t.nome}</option>)}
            </select>
            <select className="coord-select" value={status} onChange={(e) => setStatus(e.target.value)}>
              <option value="all">Todos os status</option>
              <option value="fin">Finalizados</option>
              <option value="pend">Pendentes</option>
            </select>
          </div>
        </div>

        {carregando ? (
          <div className="coord-loader" style={{ minHeight: 160 }}><div className="coord-spin" /></div>
        ) : erro ? (
          <div className="empty-hint">Não foi possível carregar os relatórios. Tente novamente.</div>
        ) : rows.length === 0 ? (
          <div className="empty-hint">Nenhum aluno encontrado com os filtros selecionados.</div>
        ) : (
          <>
            <div className="table-wrap">
              <table className="coord-table">
                <thead>
                  <tr>
                    <th>Aluno</th>
                    <th>Turma</th>
                    <th>Professor(a)</th>
                    <th>Período</th>
                    <th>Status</th>
                    <th style={{ textAlign: 'center' }}>Editar</th>
                    <th style={{ textAlign: 'right' }}>Ações</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((linha) => {
                    const r = linha.report;
                    return (
                    <tr key={linha.id}>
                      <td className="td-strong">{linha.aluno.nome || '—'}</td>
                      <td>{linha.turma_nome || '—'}</td>
                      <td>{r ? nomeProfessor(r) : '—'}</td>
                      <td>{r ? bimestreLabel(r.periodo) : (periodoInfo?.descricao || '—')}</td>
                      <td>
                        <span className={`pill ${r?.finalizado ? 'pill-ok' : 'pill-warn'}`}>{r?.finalizado ? 'Finalizado' : 'Pendente'}</span>
                      </td>
                      <td style={{ textAlign: 'center' }}>
                        {r ? (
                          <button
                            className="icon-btn"
                            style={{ width: 'auto', padding: '0 10px', gap: 6, whiteSpace: 'nowrap' }}
                            title="Editar relatório"
                            onClick={() => setLinhaEditando(linha)}
                          >
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 20h9" /><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z" /></svg>
                            <span>Editar</span>
                          </button>
                        ) : (
                          <span style={{ color: 'var(--gray-400, #9ca3af)' }}>—</span>
                        )}
                      </td>
                      <td style={{ textAlign: 'right' }}>
                        {r ? (
                          <button
                            className="icon-btn"
                            style={{ width: 'auto', padding: '0 10px', gap: 6, whiteSpace: 'nowrap' }}
                            title={r.finalizado ? 'Baixar PDF' : 'Disponível quando finalizado'}
                            disabled={!r.finalizado || baixando === r.id}
                            onClick={() => handleDownload(r)}
                          >
                            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3" /></svg>
                            <span>Baixar</span>
                          </button>
                        ) : (
                          <GerarRelatorioAction
                            aluno={linha.aluno}
                            periodo={periodoInfo}
                            onGerado={handleRelatorioGerado}
                          />
                        )}
                      </td>
                    </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            {pageCount > 1 && (
              <div className="coord-pager">
                <button disabled={page === 0} onClick={() => setPage(page - 1)}>Anterior</button>
                <span>Página {page + 1} de {pageCount}</span>
                <button disabled={page >= pageCount - 1} onClick={() => setPage(page + 1)}>Próxima</button>
              </div>
            )}
          </>
        )}
      </section>

      {linhaEditando && (
        <ViewReportModal
          isOpen={!!linhaEditando}
          onClose={() => setLinhaEditando(null)}
          reportData={linhaEditando.report}
          studentName={linhaEditando.aluno.nome}
          studentId={linhaEditando.aluno.id}
          turmaId={linhaEditando.aluno.turma_id}
          turmaName={linhaEditando.turma_nome}
          onReportUpdated={handleRelatorioGerado}
          instituicaoId={instId}
        />
      )}

      {baixando && (
        <div className="coord-busy-overlay">
          <div className="coord-busy-modal">
            <div className="coord-spin" />
            <div>
              <div className="coord-busy-title">Baixando relatório…</div>
              <div className="coord-busy-sub">
                {rows.find((l) => String(l.report?.id) === String(baixando))?.aluno?.nome
                  ? `Gerando o PDF de ${rows.find((l) => String(l.report?.id) === String(baixando)).aluno.nome}.`
                  : 'Buscando o arquivo.'}
                {' '}Isso pode levar alguns segundos.
              </div>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}