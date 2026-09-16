import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { format, parseISO } from 'date-fns';
import { ptBR } from 'date-fns/locale';
import { useCoordinatorData } from '@/components/coordinator/v2/CoordinatorDataContext';
import { campoExperienciaMap, componenteCurricularMap, formatLeituraLabel } from '@/lib/observationUtils';

const firstName = (nome) => (nome || '').trim().split(/\s+/)[0] || '';

/* emojis por campo de experiência (fiel ao mockup) */
const CAMPO_EMOJI = {
  // Campos de experiência (Educação Infantil)
  'Escuta, fala, pensamento e imaginação': '💭',
  'Espaços, tempos, quantidades, relações e transformações': '🔢',
  'Traços, sons, cores e formas': '🎨',
  'O eu, o outro e o nós': '👥',
  'Corpo, gestos e movimentos': '🏃',
  // Componentes curriculares (Ensino Fundamental)
  'Língua Portuguesa': '📖',
  'Matemática': '🔢',
  'Ciências': '🔬',
  'História': '🏛️',
  'Geografia': '🌎',
  'Arte': '🎨',
  'Educação Física': '⚽',
  'Filosofia': '💡',
};

/* Colunas da tabela de produção docente. Cada uma ordena por clique.
   O Total é a soma BRUTA das quatro — nesta base, registros respondem por 88%
   dele, então ordenar por Total dá quase a mesma ordem que ordenar por
   Registros (13 de 15 posições iguais). O tooltip diz de que ele é feito, para
   não ser lido como "quem produziu mais". */
const COLUNAS_PRODUCAO = [
  { k: 'nome', label: 'Professora' },
  {
    k: 'total',
    label: 'Total',
    titulo: 'Total',
    ajuda: 'soma de registros, relatórios, planejamentos e portfólios',
    num: true,
    destaque: true,
  },
  // Rotulos curtos: o cabecalho define a largura minima da coluna, e
  // "PLANEJAMENTOS" por extenso espremia o nome ate virar "Lorenzo Za…".
  // O title traz o termo completo.
  { k: 'registros', label: 'Reg.', titulo: 'Registros', num: true },
  { k: 'relatorios', label: 'Rel.', titulo: 'Relatórios', num: true },
  { k: 'planejamentos', label: 'Planos', titulo: 'Planejamentos', num: true },
  { k: 'portfolios', label: 'Portf.', titulo: 'Portfólios', num: true },
];

/* "Lorenzo Duarte Zanetti" -> "Lorenzo Zanetti". Numa coluna estreita o nome
   inteiro virava "Lorenzo Du…"; primeiro + ultimo sobrenome identifica a
   pessoa e cabe. O nome completo fica no title da celula. */
const nomeCurto = (nome = '') => {
  const p = nome.trim().split(/\s+/);
  return p.length > 2 ? `${p[0]} ${p[p.length - 1]}` : nome;
};

const GridIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="3" width="7" height="7" rx="1.5" /><rect x="14" y="3" width="7" height="7" rx="1.5" /><rect x="3" y="14" width="7" height="7" rx="1.5" /><rect x="14" y="14" width="7" height="7" rx="1.5" /></svg>
);

export default function PulsoDaEscolaPage() {
  const navigate = useNavigate();
  const { loading, statusCarregamento, dashboardData, viewData, user, periodoInfo } = useCoordinatorData();
  // Filtro de turma do "Mapa de utilização da BNCC" ('' = Geral / todas as turmas).
  const [bnccTurma, setBnccTurma] = useState('');
  // Ordenação da tabela de produção docente (clique no cabeçalho).
  const [ordemProd, setOrdemProd] = useState({ k: 'total', asc: false });
  const alternarOrdem = (k) =>
    setOrdemProd((o) => (o.k === k ? { k, asc: !o.asc } : { k, asc: k === 'nome' }));

  if (loading || !dashboardData) {
    return (
      <main className="content">
        <div className="coord-loader">
          <div className="coord-spin" />
          <p className="coord-loader-status" role="status" aria-live="polite">
            {statusCarregamento || 'Carregando…'}
          </p>
        </div>
      </main>
    );
  }

  const d = dashboardData;
  const alerts = viewData?.alerts || [];
  const nome = firstName(user?.user_metadata?.nome ?? user?.nome);

  // Recorte vigente na tela — rotula os cards para não restar dúvida de que
  // janela cada número representa.
  const periodoNome = periodoInfo?.descricao || null;
  const periodoEmCurso = periodoInfo?.emCurso !== false;
  // "No 2º BIMESTRE" x "Entre 01/03 e 31/03": um bimestre tem nome, um
  // intervalo à mão não — a preposição muda junto.
  // Composição do total de registros — mostra do que o número é feito.
  const composicaoRegistros = (() => {
    const t = d.registrosPorTipo;
    if (!t) return null;
    const partes = [
      [t.marcacoes, 'marcações'],
      [t.relatos, 'relatos'],
      [t.escrita, 'análises de escrita'],
      [t.desenho, 'análises de desenho'],
    ].filter(([n]) => n > 0).map(([n, rot]) => `${n} ${rot}`);
    return partes.length ? partes.join(' · ') : null;
  })();

  const recorteFrase = !periodoNome
    ? 'No período'
    : periodoInfo?.personalizado
      ? `Entre ${periodoNome.replace(' – ', ' e ')}`
      : `No ${periodoNome}`;

  // --- BNCC: distribuição de registros por campo (dados via cache: bncc_usage) ---
  // Geral = bncc_usage agregado; por turma = bncc_usage_por_turma[turmaId] (mesma janela).
  const bnccTurmas = [...(viewData?.turmas || [])].sort((a, b) => (a.nome || '').localeCompare(b.nome || '', 'pt'));
  const usage = bnccTurma ? (d.bnccUsagePorTurma?.[bnccTurma] || []) : (d.bnccUsageData || []);

  // --- Engajamento docente semanal (cache: indicadores.semanal_4s) ---
  const engajamentoData = (d.engajamentoSemanal || []).map((s) => {
    let semana = 'Semana';
    try { semana = `Semana ${format(parseISO(s.semana_inicio), 'dd/MM', { locale: ptBR })}`; } catch { /* mantém fallback */ }
    return { semana, registros: s.registros || 0 };
  });
  const temEngajamento = engajamentoData.some((s) => s.registros > 0);
  const totalUsage = usage.reduce((s, u) => s + (u.count || 0), 0);

  /*
   * O mapa é montado em BLOCOS por taxonomia. Antes iterava só os 5 campos de
   * experiência e jogava todo o Fundamental numa linha "Outros" — 44% das
   * marcações da escola, com Língua Portuguesa (a mais registrada de todas)
   * sem linha própria.
   *
   * Campos de experiência e componentes curriculares são réguas diferentes da
   * BNCC; ficam em blocos separados, cada um com seu próprio percentual, para
   * não sugerir que "Matemática" e "Corpo, gestos e movimentos" são
   * comparáveis entre si.
   */
  const montarBloco = (titulo, mapa) => {
    const chaves = Object.keys(mapa);
    const linhas = chaves
      .map((campo) => {
        const entry = usage.find((u) => u.campo_experiencia === campo);
        return { campo, count: entry ? entry.count : 0 };
      })
      .filter((l) => l.count > 0);
    const total = linhas.reduce((s, l) => s + l.count, 0);
    if (!total) return null;

    // Limiar relativo ao nº de categorias do bloco: com 5 campos a média é
    // 20%, com 8 componentes é 12,5%. Um corte fixo pintaria todo o
    // Fundamental de vermelho só por ter mais categorias.
    const media = 100 / chaves.length;
    return {
      titulo,
      total,
      linhas: linhas
        .map(({ campo, count }) => {
          const pct = Math.round((count / total) * 100);
          const cls = pct >= media ? 'good' : pct >= media * 0.6 ? 'attention' : 'critical';
          return { campo, name: mapa[campo].name, emoji: CAMPO_EMOJI[campo] || '•', pct, count, cls };
        })
        .sort((a, b) => b.pct - a.pct),
    };
  };

  const blocosBncc = [
    montarBloco('Campos de experiência · Educação Infantil', campoExperienciaMap),
    montarBloco('Componentes curriculares · Ensino Fundamental', componenteCurricularMap),
  ].filter(Boolean);

  // Categorias que não estão em nenhum dos dois mapas (cadastro fora do
  // padrão). Não somem em silêncio: viram um bloco próprio.
  const conhecidas = { ...campoExperienciaMap, ...componenteCurricularMap };
  const semClassificacao = usage.filter((u) => !(u.campo_experiencia in conhecidas) && u.count > 0);
  if (semClassificacao.length) {
    const total = semClassificacao.reduce((s, u) => s + u.count, 0);
    blocosBncc.push({
      titulo: 'Fora do catálogo',
      total,
      linhas: [...semClassificacao]
        .sort((a, b) => b.count - a.count)
        .map((u) => ({
          campo: u.campo_experiencia,
          name: u.campo_experiencia,
          emoji: '•',
          pct: Math.round((u.count / total) * 100),
          count: u.count,
          cls: 'neutral',
        })),
    });
  }

  const bnccTemDado = totalUsage > 0;

  // --- Crianças invisíveis: nomes a partir dos alertas de registro ---
  const semRegistro = alerts.filter((a) => a.type === 'registro' && a.crianca_nome);
  const tags = semRegistro.slice(0, 4).map((a) => a.crianca_nome);
  const extras = semRegistro.length - tags.length;

  // --- Alfabetização e Saúde pedagógica: dependem do cache (podem não existir ainda) ---
  const alfa = d.alfabetizacao;
  const alfaTotal = alfa?.total_criancas || 0;
  const alfaPct = (n) => (alfaTotal > 0 ? Math.round((n / alfaTotal) * 100) : 0);
  const temAlfa = !!alfa && alfaTotal > 0 && ((alfa.escrita || []).length > 0 || (alfa.leitura || []).length > 0);

  // --- Ranking de produção docente (período vigente, via cache) ---
  const profNome = new Map((d.professores || []).map((p) => [String(p.id), p.nome]));
  const rankRows = (d.rankingProfessores || [])
    .map((r) => ({ ...r, nome: profNome.get(String(r.professor_id)) }))
    .filter((r) => r.nome && r.total > 0); // só professoras conhecidas com produção

  const rankRowsOrdenadas = [...rankRows].sort((a, b) => {
    const { k, asc } = ordemProd;
    const va = a[k], vb = b[k];
    const cmp = typeof va === 'string'
      ? String(va).localeCompare(String(vb), 'pt')
      : (va || 0) - (vb || 0);
    return asc ? cmp : -cmp;
  });

  return (
    <main className="content">
      <div className="greeting">
        <h1 className="greeting-title">Oi, {nome || 'coordenação'}!</h1>
        <p className="greeting-sub">
          {`${recorteFrase}: `}
          <span className="greeting-highlight">{d.weeklyObservations} registros</span>
          {' '}feitos por <span className="greeting-highlight">{d.professoresCount} professoras</span>. Alguns sinais merecem sua atenção logo abaixo.
        </p>
      </div>

      {/* ===== TOP 4 CARDS ===== */}
      <div className="top-grid">
        <div className="card green">
          <div className="card-head">
            <div className="card-title-wrap"><div className="card-title">Registros no Período</div></div>
            <svg className="card-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="20" x2="18" y2="10" /><line x1="12" y1="20" x2="12" y2="4" /><line x1="6" y1="20" x2="6" y2="14" /></svg>
          </div>
          <div className="card-number">{d.weeklyObservations}</div>
          {/* Desdobramento: marcação de chip e relato de áudio somam no mesmo
              total, mas são esforços e evidências pedagógicas diferentes. */}
          <div className="card-desc">{composicaoRegistros || 'Registros da equipe'}</div>
        </div>

        <div className="card blue">
          <div className="card-head">
            <div className="card-title-wrap"><div className="card-title">Planejamentos Finalizados</div></div>
            <svg className="card-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="4" width="18" height="18" rx="2" /><path d="M16 2v4M8 2v4M3 10h18M9 16l2 2 4-4" /></svg>
          </div>
          <div className="card-number">{d.planningsFinishedCount}<span className="frac">/{d.totalTurmas}</span></div>
          <div className="card-desc">Turmas com planejamento no período</div>
        </div>

        <div className="card red">
          <div className="card-head">
            {/* Não é "precisam de atenção": a lacuna é de registro, não da
                criança. O alerta considera qualquer forma de registro. */}
            <div className="card-title-wrap"><div className="card-title">Crianças sem Registro Recente</div></div>
            <svg className="card-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" /><circle cx="9" cy="7" r="4" /></svg>
          </div>
          <div className="card-number">{d.studentsWithoutRecords}</div>
          <div className="card-desc">
            {periodoEmCurso
              ? 'Sem registros nos últimos 15 dias'
              : 'Sem registros nos 15 dias finais do período'}
          </div>
          <button className="card-link" onClick={() => navigate('/coordenacao/atencao')}>
            Enviar devolutiva
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M5 12h14M13 5l7 7-7 7" /></svg>
          </button>
        </div>

        <div className="card purple">
          <div className="card-head">
            <div className="card-title-wrap"><div className="card-title">Relatórios do Período</div></div>
            <svg className="card-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><path d="M14 2v6h6" /></svg>
          </div>
          <div className="card-number">{d.reportsFinished}<span className="frac">/{d.reportsTotal}</span></div>
          <div className="card-desc">{Math.round(d.reportProgress)}% concluídos</div>
          <div className="progress-bar"><div className="progress-bar-fill green" style={{ width: `${Math.round(d.reportProgress)}%` }} /></div>
        </div>
      </div>

      {/* ===== MAPA BNCC + ALFABETIZAÇÃO ===== */}
      <div className="double-grid">
        <div className="bncc-block">
          <div className="block-head">
            <div className="block-head-left">
              <svg className="block-mini-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z" /><circle cx="12" cy="10" r="3" /></svg>
              <div>
                <div className="block-title-wrap"><span className="block-title">Mapa de utilização da BNCC</span></div>
                <div className="block-subtitle">Distribuição de registros por campo de experiência{bnccTurma ? ' · por turma' : ' · geral'}</div>
              </div>
            </div>
            <div className="block-head-actions">
              <select className="coord-select bncc-turma-select" value={bnccTurma} onChange={(e) => setBnccTurma(e.target.value)} title="Filtrar por turma">
                <option value="">Geral (todas as turmas)</option>
                {bnccTurmas.map((t) => <option key={t.id} value={String(t.id)}>{t.nome}</option>)}
              </select>
              <button className="icon-link" title="Ver detalhamento por turma" onClick={() => navigate('/coordenacao/aprendizagens')}><GridIcon /></button>
            </div>
          </div>

          {!bnccTemDado && <div className="empty-hint">Sem registros suficientes para o mapa da BNCC.</div>}
          {bnccTemDado && blocosBncc.map((bloco) => (
            <div className="bncc-bloco" key={bloco.titulo}>
              {/* O título só aparece quando há mais de um bloco: numa turma de
                  uma etapa só, ele seria ruído. */}
              {blocosBncc.length > 1 && (
                <div className="bncc-bloco-titulo">
                  {bloco.titulo}
                  <span className="bncc-bloco-total">{bloco.total} registros</span>
                </div>
              )}
              {bloco.linhas.map((r) => (
                <div className="bncc-row" key={r.campo} title={`${r.count} registros`}>
                  <div className="bncc-bar-emoji">{r.emoji}</div>
                  <div className="bncc-info">
                    <div className="bncc-label"><span className="bncc-name">{r.name}</span><span className="bncc-pct">{r.pct}%</span></div>
                    <div className="bncc-bar-wrap"><div className={`bncc-bar ${r.cls}`} style={{ width: `${r.pct}%` }} /></div>
                  </div>
                </div>
              ))}
            </div>
          ))}
        </div>

        <div className="alfa-block">
          <div className="block-head">
            <div className="block-head-left">
              <svg className="block-mini-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" /><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" /></svg>
              <div>
                <div className="block-title-wrap"><span className="block-title">Pulso da alfabetização</span></div>
                <div className="block-subtitle">% das crianças por classificação{periodoNome ? ` · ${periodoNome}` : ''}</div>
              </div>
            </div>
            <button className="icon-link" title="Ver detalhamento por turma" onClick={() => navigate('/coordenacao/alfabetizacao')}><GridIcon /></button>
          </div>

          {!temAlfa ? (
            <div className="empty-hint">Distribuição de alfabetização ainda não disponível no cache.</div>
          ) : (
            <div className="alfa-dist-wrap">
              {[{ key: 'leitura', emoji: '📖', name: 'Leitura' }, { key: 'escrita', emoji: '✏️', name: 'Escrita' }].map((m) => (
                <div className="alfa-dist-group" key={m.key}>
                  <div className="alfa-dist-title">{m.emoji} {m.name} <span className="alfa-dist-total">· {alfaTotal} crianças</span></div>
                  {(alfa[m.key] || []).length === 0 ? (
                    <div className="alfa-dist-empty">Sem dados no período.</div>
                  ) : (alfa[m.key] || []).map((row) => {
                    const pct = alfaPct(row.count);
                    const sem = row.classe === 'Sem classificação';
                    const rotulo = m.key === 'leitura' ? formatLeituraLabel(row.classe) : row.classe;
                    const irParaLista = () =>
                      navigate(`/coordenacao/alfabetizacao?modalidade=${m.key}&classe=${encodeURIComponent(row.classe)}`);
                    return (
                      <div
                        className="bncc-row bncc-row-clickable"
                        key={row.classe}
                        role="button"
                        tabIndex={0}
                        title={`Ver ${row.count} ${row.count === 1 ? 'criança' : 'crianças'} · ${rotulo}`}
                        onClick={irParaLista}
                        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); irParaLista(); } }}
                      >
                        <div className="bncc-info">
                          <div className="bncc-label"><span className="bncc-name">{rotulo}</span><span className="bncc-pct">{pct}%</span></div>
                          <div className="bncc-bar-wrap"><div className="bncc-bar" style={{ width: `${pct}%`, background: sem ? 'var(--text-light)' : 'var(--purple)' }} /></div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* ===== FINAL GRID ===== */}
      <div className="final-grid">
        <div className="indicator-card">
          <div className="indicator-card-bg" />
          <div className="indicator-head"><span className="indicator-title">Saúde pedagógica institucional</span></div>
          <div className="indicator-subtitle">Produção docente{periodoNome ? ` · ${periodoNome}` : ''}</div>
          {rankRows.length === 0 ? (
            <div className="indicator-meta" style={{ marginTop: 10 }}>Dados ainda não calculados.</div>
          ) : (
            <>
              <div className="prod-scroll">
                <table className="prod-table">
                  <thead>
                    <tr>
                      {COLUNAS_PRODUCAO.map((c) => (
                        <th
                          key={c.k}
                          className={`${c.num ? 'num' : ''} ${c.destaque ? 'destaque' : ''} ${ordemProd.k === c.k ? 'sorted' : ''}`}
                          onClick={() => alternarOrdem(c.k)}
                          onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); alternarOrdem(c.k); } }}
                          tabIndex={0}
                          role="columnheader"
                          aria-sort={ordemProd.k === c.k ? (ordemProd.asc ? 'ascending' : 'descending') : 'none'}
                          title={c.ajuda
                            ? `${c.titulo}: ${c.ajuda}. Clique para ordenar.`
                            : `Ordenar por ${c.titulo || c.label}`}
                          aria-label={c.ajuda
                            ? `${c.titulo}, ${c.ajuda}`
                            : (c.titulo || c.label)}
                        >
                          {c.label}
                          <span className="sort-arrow" aria-hidden="true">
                            {ordemProd.k === c.k ? (ordemProd.asc ? '▲' : '▼') : '↕'}
                          </span>
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {rankRowsOrdenadas.map((r) => (
                      <tr key={r.professor_id}>
                        <td className="prod-nome" title={r.nome}>{nomeCurto(r.nome)}</td>
                        <td className={`num destaque ${r.total ? '' : 'prod-zero'}`}>{r.total}</td>
                        {['registros', 'relatorios', 'planejamentos', 'portfolios'].map((k) => (
                          <td className={`num ${r[k] ? '' : 'prod-zero'}`} key={k}>{r[k]}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {/* Sem coluna de total: somar marcação de chip com relatório e
                  planejamento mistura unidades incomparáveis, e ordenar pessoas
                  por essa soma vira cobrança sobre um número que não significa
                  esforço equivalente. Cada coluna ordena por si. */}
              <div className="prod-nota">
                Total = soma bruta das quatro colunas. Relatórios contam por turma
                da criança — a base não guarda autoria.
              </div>
            </>
          )}
        </div>

        <div className="invisible-card">
          <div className="invisible-head"><span className="invisible-title">Crianças invisíveis</span></div>
          <div className="invisible-subtitle">Sem registro há mais de 14 dias</div>
          <div className="invisible-number">{d.studentsWithoutRecords}</div>
          <p className="invisible-desc">Cada criança merece estar no radar pedagógico. Estas precisam de uma observação registrada nos próximos dias.</p>
          {tags.length > 0 && (
            <div className="tags-wrap">
              {tags.map((t, i) => <span className="tag" key={i}>{t}</span>)}
              {extras > 0 && <span className="tag">+{extras} outras</span>}
            </div>
          )}
          <button className="btn-primary" onClick={() => navigate('/coordenacao/atencao')}>
            Ver todas e atribuir registro
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M5 12h14M13 5l7 7-7 7" /></svg>
          </button>
        </div>
      </div>

      {/* ===== ENGAJAMENTO DOCENTE SEMANAL ===== */}
      <div className="engajamento-block">
        <div className="block-head">
          <div className="block-head-left">
            <svg className="block-mini-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="22 7 13.5 15.5 8.5 10.5 2 17" /><polyline points="16 7 22 7 22 13" /></svg>
            <div>
              <div className="block-title-wrap"><span className="block-title">Engajamento Docente Semanal</span></div>
              <div className="block-subtitle">Evolução de registros nas últimas 4 semanas</div>
            </div>
          </div>
        </div>
        {!temEngajamento ? (
          <div className="empty-hint">Sem registros nas últimas semanas para o gráfico de engajamento.</div>
        ) : (
          <div className="engajamento-chart">
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={engajamentoData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border-light)" />
                <XAxis dataKey="semana" fontSize={12} tickLine={false} axisLine={{ stroke: 'var(--border-light)' }} />
                <YAxis allowDecimals={false} fontSize={12} tickLine={false} axisLine={false} />
                <Tooltip contentStyle={{ backgroundColor: 'white', border: '1px solid var(--border-light)', borderRadius: 8 }} cursor={{ fill: 'var(--purple-softer)' }} />
                <Bar dataKey="registros" name="Registros" fill="#34D399" radius={[4, 4, 0, 0]} maxBarSize={90} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      <div className="manifesto">
        <div className="manifesto-icon">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z" /></svg>
        </div>
        <div className="manifesto-text">
          <strong>A Nara só relata o que foi observado.</strong> O silêncio sobre uma habilidade não é juízo de ausência — é honestidade pedagógica.
        </div>
      </div>
    </main>
  );
}
