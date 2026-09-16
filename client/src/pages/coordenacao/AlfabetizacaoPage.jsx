import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useCoordinatorData } from '@/components/coordinator/v2/CoordinatorDataContext';
import { authFetch, API_BASE_URL } from '@/services/api';
import { formatLeituraLabel } from '@/lib/observationUtils';

const PAGE_SIZE = 25;

const MODALIDADES = [
  { key: 'leitura', emoji: '📖', name: 'Leitura' },
  { key: 'escrita', emoji: '✏️', name: 'Escrita' },
];

export default function AlfabetizacaoPage() {
  const { loading, dashboardData, viewData, periodoId, intervalo, periodoInfo } = useCoordinatorData();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const modalidade = MODALIDADES.some((m) => m.key === searchParams.get('modalidade'))
    ? searchParams.get('modalidade')
    : 'leitura';
  const classe = searchParams.get('classe') || '';

  const turmas = useMemo(
    () => [...(viewData?.turmas || [])].sort((a, b) => (a.nome || '').localeCompare(b.nome || '', 'pt')),
    [viewData],
  );

  // Classes disponíveis para o seletor, derivadas da mesma distribuição do card (cache v7).
  const alfa = dashboardData?.alfabetizacao || null;
  const classesDaModalidade = useMemo(
    () => (alfa?.[modalidade] || []).map((r) => r.classe),
    [alfa, modalidade],
  );

  const [turmaId, setTurmaId] = useState('all');
  const [page, setPage] = useState(0);
  const [rows, setRows] = useState([]);
  const [total, setTotal] = useState(0);
  const [carregando, setCarregando] = useState(false);
  const [erro, setErro] = useState(false);

  const setModalidade = (m) => { setSearchParams({ modalidade: m, ...(classe ? { classe } : {}) }); setPage(0); };
  const setClasse = (c) => { setSearchParams({ modalidade, ...(c ? { classe: c } : {}) }); setPage(0); };

  // Reset de paginação ao trocar filtros de query.
  useEffect(() => { setPage(0); }, [modalidade, classe, turmaId]);

  useEffect(() => {
    if (!classe) { setRows([]); setTotal(0); return; }
    let cancel = false;
    setCarregando(true);
    setErro(false);
    const params = new URLSearchParams({
      modalidade,
      classe,
      limit: String(PAGE_SIZE),
      offset: String(page * PAGE_SIZE),
    });
    if (turmaId !== 'all') params.set('turma_id', turmaId);
    // Mesmo recorte do card que trouxe o usuário até aqui — sem isto, clicar
    // num número do 2º bimestre listaria as crianças do período vigente.
    if (intervalo) {
      params.set('data_inicio', intervalo.inicio);
      params.set('data_fim', intervalo.fim);
    } else if (periodoId) {
      params.set('periodo_id', periodoId);
    }
    authFetch(`${API_BASE_URL}/coordenacao/alfabetizacao-criancas/?${params.toString()}`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error('Falha ao carregar crianças'))))
      .then((d) => { if (cancel) return; setRows(d.results || []); setTotal(d.count || 0); })
      .catch((e) => { if (cancel) return; console.error(e); setErro(true); setRows([]); setTotal(0); })
      .finally(() => { if (!cancel) setCarregando(false); });
    return () => { cancel = true; };
  }, [modalidade, classe, turmaId, page, periodoId, intervalo]);

  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const modInfo = MODALIDADES.find((m) => m.key === modalidade);
  // Rótulo legível: a leitura grava o valor cru ("silabico"); a escrita já vem formatada.
  const rotuloClasse = (c) => (modalidade === 'leitura' ? formatLeituraLabel(c) : c);

  if (loading || !dashboardData) {
    return <main className="content"><div className="coord-loader"><div className="coord-spin" /></div></main>;
  }

  return (
    <main className="content">
      <div className="page-header">
        <div>
          <h1 className="page-title">{modInfo.emoji} Crianças por classificação · {modInfo.name}</h1>
          <p className="page-subtitle">
            {classe ? <>Classe <strong>{rotuloClasse(classe)}</strong>{periodoInfo?.descricao ? <> · {periodoInfo.descricao}</> : null} · {total} {total === 1 ? 'criança' : 'crianças'}</> : 'Escolha uma classificação para listar as crianças'}
          </p>
        </div>
        <button className="card-link" onClick={() => navigate('/coordenacao')}>← Voltar ao pulso</button>
      </div>

      <section className="section">
        <div className="section-head">
          <div>
            <h2 className="section-title">Filtros</h2>
            <p className="section-subtitle">Modalidade, classificação e turma</p>
          </div>
          <div className="coord-filters">
            <select className="coord-select" value={modalidade} onChange={(e) => setModalidade(e.target.value)}>
              {MODALIDADES.map((m) => <option key={m.key} value={m.key}>{m.emoji} {m.name}</option>)}
            </select>
            <select className="coord-select" value={classe} onChange={(e) => setClasse(e.target.value)}>
              <option value="">Selecione a classificação…</option>
              {classesDaModalidade.map((c) => <option key={c} value={c}>{rotuloClasse(c)}</option>)}
              {classe && !classesDaModalidade.includes(classe) && <option value={classe}>{rotuloClasse(classe)}</option>}
            </select>
            <select className="coord-select" value={turmaId} onChange={(e) => setTurmaId(e.target.value)}>
              <option value="all">Todas as turmas</option>
              {turmas.map((t) => <option key={t.id} value={t.id}>{t.nome}</option>)}
            </select>
          </div>
        </div>

        {!classe ? (
          <div className="empty-hint">Selecione uma classificação acima (ou clique numa classe no card "Pulso da alfabetização").</div>
        ) : carregando ? (
          <div className="coord-loader" style={{ minHeight: 160 }}><div className="coord-spin" /></div>
        ) : erro ? (
          <div className="empty-hint">Não foi possível carregar as crianças. Tente novamente.</div>
        ) : rows.length === 0 ? (
          <div className="empty-hint">Nenhuma criança nesta classificação com os filtros selecionados.</div>
        ) : (
          <>
            <div className="table-wrap">
              <table className="coord-table">
                <thead>
                  <tr>
                    <th style={{ width: 56 }}>#</th>
                    <th>Criança</th>
                    <th>Turma</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((c, i) => (
                    <tr key={c.crianca_id}>
                      <td>{page * PAGE_SIZE + i + 1}</td>
                      <td className="td-strong">{c.nome || '—'}</td>
                      <td>{c.turma_nome || '—'}</td>
                    </tr>
                  ))}
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
    </main>
  );
}
