import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useCoordinatorData } from '@/components/coordinator/v2/CoordinatorDataContext';
import { apiClient } from '@/lib/apiClient';
import { startOfWeek, endOfWeek, parseISO, format, formatISO, isValid } from 'date-fns';
import { ptBR } from 'date-fns/locale';
import './planejamentos.css';

const DIAS = [
  { key: 'segunda', abbr: 'Seg', label: 'Segunda-feira' },
  { key: 'terca', abbr: 'Ter', label: 'Terça-feira' },
  { key: 'quarta', abbr: 'Qua', label: 'Quarta-feira' },
  { key: 'quinta', abbr: 'Qui', label: 'Quinta-feira' },
  { key: 'sexta', abbr: 'Sex', label: 'Sexta-feira' },
];

const turmaBadge = (nome = '') => {
  const num = (nome.match(/\d+/) || [''])[0];
  const letters = nome.match(/[A-Z]/g) || [];
  const letter = num ? (letters[letters.length - 1] || '') : '';
  if (num) return `${num}${letter}`;
  return nome.replace(/[^A-Za-zÀ-ú]/g, '').slice(0, 2).toUpperCase() || '–';
};

const dayHasContent = (dia) => Boolean(
  (dia?.atividades_propostas && dia.atividades_propostas.trim()) ||
  (dia?.atividades && dia.atividades.trim()) ||
  dia?.arquivo_storage_key
);

export default function PlanejamentosPage() {
  const { loading, dashboardData, viewData, user } = useCoordinatorData();
  const [termPlans, setTermPlans] = useState(null);
  const [planoSel, setPlanoSel] = useState(null);

  const instId = user?.user_metadata?.instituicao_id ?? user?.instituicao_id ?? null;

  // Calendário do bimestre: planos do ano letivo agrupados por semana (fetch leve).
  useEffect(() => {
    let cancel = false;
    if (!instId) return;
    (async () => {
      const { data } = await apiClient.from('planejamentos')
        .select('id, turma_id, semana_referencia, semana_inicio')
        .eq('instituicao_id', instId);
      if (!cancel) setTermPlans(data || []);
    })();
    return () => { cancel = true; };
  }, [instId]);

  const plans = viewData?.planning || [];

  // ===== Semana visualizada (clique no calendário troca a semana) =====
  const currentMondayKey = format(startOfWeek(new Date(), { weekStartsOn: 1 }), 'yyyy-MM-dd');
  const [semanaSel, setSemanaSel] = useState(null); // monday yyyy-MM-dd; null = semana atual
  const [semanaPlans, setSemanaPlans] = useState(null);
  const [loadingSemana, setLoadingSemana] = useState(false);

  const selecionarSemana = useCallback(async (weekKey) => {
    // Semana atual: usa o que já veio no contexto (viewData.planning).
    if (!weekKey || weekKey === currentMondayKey) {
      setSemanaSel(null);
      setSemanaPlans(null);
      return;
    }
    setSemanaSel(weekKey);
    setLoadingSemana(true);
    try {
      const monday = parseISO(weekKey);
      const fim = endOfWeek(monday, { weekStartsOn: 1 });
      const { data } = await apiClient.from('planejamentos')
        .select('*, turmas:turma_id(nome), usuarios:id_professor(nome)')
        .eq('instituicao_id', instId)
        .gte('semana_referencia', formatISO(monday))
        .lte('semana_referencia', formatISO(fim));
      const mapped = (data || []).map((p) => ({
        ...p,
        status: p.dias?.some((d) => d.atividades?.length > 0 || d.atividades_propostas?.length > 0) ? 'Finalizado' : 'Pendente',
      }));
      setSemanaPlans(mapped);
    } catch (e) {
      console.error('Falha ao carregar planos da semana selecionada:', e);
      setSemanaPlans([]);
    } finally {
      setLoadingSemana(false);
    }
  }, [currentMondayKey, instId]);

  // Fonte ativa de planos: semana selecionada (se houver) ou semana atual.
  const activePlans = semanaSel ? (semanaPlans || []) : plans;

  const planRows = useMemo(() => {
    return [...activePlans].sort((a, b) => (a.turmas?.nome || '').localeCompare(b.turmas?.nome || '', 'pt'));
  }, [activePlans]);

  const planosSemana = plans.length;
  const emConstrucao = plans.filter((p) => p.status !== 'Finalizado').length;

  const semanaAtivaLabel = useMemo(() => {
    const m = semanaSel ? parseISO(semanaSel) : startOfWeek(new Date(), { weekStartsOn: 1 });
    const e = endOfWeek(m, { weekStartsOn: 1 });
    return `${format(m, 'dd/MM')} a ${format(e, 'dd/MM/yyyy')}`;
  }, [semanaSel]);

  // ===== Heatmap "Cobertura BNCC × Turmas" (recorte selecionado no layout) =====
  const ptc = dashboardData?.planosPorTurmaCampo || {};
  const heatmapCampos = dashboardData?.heatmapCampos || [];
  const periodoDescricao = dashboardData?.periodoDescricao || null;
  // Sufixo reaproveitado nos tooltips e mensagens vazias, para todos citarem o
  // mesmo recorte em vez de dizerem "vigente" fixo.
  const rotuloPeriodo = periodoDescricao ? ` no ${periodoDescricao}` : ' no período selecionado';
  const semHab = dashboardData?.planosSemHabilidadePorTurma || {};
  const temHeatmap = heatmapCampos.length > 0 || Object.keys(ptc).length > 0 || Object.keys(semHab).length > 0;

  const turmasOrdenadas = useMemo(
    () => [...(viewData?.turmas || [])].sort((a, b) => (a.nome || '').localeCompare(b.nome || '', 'pt')),
    [viewData],
  );
  const profPorTurmaNome = useMemo(() => {
    const m = new Map();
    (dashboardData?.professores || []).forEach((p) => (p.turmas || []).forEach((tn) => { if (!m.has(tn)) m.set(tn, p.nome); }));
    return m;
  }, [dashboardData]);
  // Mapa id do professor -> nome real (o campo do planejamento guarda o e-mail).
  const profNomePorId = useMemo(() => {
    const m = new Map();
    (dashboardData?.professores || []).forEach((p) => m.set(String(p.id), p.nome));
    return m;
  }, [dashboardData]);
  // Resolve o nome real da professora de um plano (id -> turma -> fallback).
  const nomeProfessora = useCallback((p) => {
    const nomeTurma = p.turmas?.nome;
    return (
      profNomePorId.get(String(p.id_professor || p.professora_id)) ||
      (nomeTurma && profPorTurmaNome.get(nomeTurma)) ||
      p.usuarios?.nome ||
      p.professora_nome ||
      '—'
    );
  }, [profNomePorId, profPorTurmaNome]);

  // Linhas do heatmap: TODAS as turmas com algum plano no período
  // (têm cobertura BNCC em `ptc` e/ou planos sem habilidade em `semHab`).
  const heatRows = useMemo(() => {
    if (!temHeatmap) return [];
    return turmasOrdenadas
      .filter((t) => ptc[String(t.id)] || semHab[String(t.id)])
      .map((t) => ({
        id: t.id,
        nome: t.nome,
        prof: profPorTurmaNome.get(t.nome) || null,
        celulas: heatmapCampos.map((c) => (ptc[String(t.id)]?.[c] || 0)),
        semHab: semHab[String(t.id)] || 0,
      }));
  }, [temHeatmap, turmasOrdenadas, ptc, heatmapCampos, semHab, profPorTurmaNome]);

  // Derivações dos cards sobre TODAS as turmas ativas — não só as que já
  // marcam BNCC. Restringir às que marcam invertia o incentivo: uma turma que
  // não vinculava habilidade nenhuma não gerava lacuna, então quanto pior a
  // adesão, melhor o indicador ficava. Turma sem vínculo passa a contar como
  // lacuna em todos os campos, que é o que ela é pedagogicamente.
  const { coberturaMediaTxt, lacunasCount, lacunasTurmas, turmasSemVinculo } = useMemo(() => {
    const ids = (turmasOrdenadas || []).map((t) => String(t.id));
    if (heatmapCampos.length === 0 || ids.length === 0) {
      return { coberturaMediaTxt: '—', lacunasCount: null, lacunasTurmas: 0, turmasSemVinculo: 0 };
    }
    const totalCampos = heatmapCampos.length;
    let somaCobertos = 0;
    let lacunas = 0;
    let turmasComLacuna = 0;
    let semVinculo = 0;
    ids.forEach((id) => {
      const cobertos = heatmapCampos.filter((c) => (ptc[id]?.[c] || 0) > 0).length;
      somaCobertos += cobertos;
      const zeros = totalCampos - cobertos;
      lacunas += zeros;
      if (zeros > 0) turmasComLacuna += 1;
      if (cobertos === 0) semVinculo += 1;
    });
    const media = somaCobertos / ids.length;
    return {
      coberturaMediaTxt: `${media.toFixed(1).replace('.', ',')}`,
      lacunasCount: lacunas,
      lacunasTurmas: turmasComLacuna,
      turmasSemVinculo: semVinculo,
    };
  }, [ptc, heatmapCampos, turmasOrdenadas]);

  const heatClass = (n) => (n === 0 ? 'h0' : n === 1 ? 'h1' : n === 2 ? 'h2' : n <= 4 ? 'h3' : n <= 6 ? 'h4' : 'h5');
  const campoEmoji = (campo = '') => {
    const c = campo.toLowerCase();
    if (c.includes('portug') || c.includes('língua') || c.includes('lingua') || c.includes('escuta')) return '📖';
    if (c.includes('matem') || c.includes('espaço') || c.includes('espaco') || c.includes('quantidade')) return '🔢';
    if (c.includes('art') || c.includes('traço') || c.includes('traco') || c.includes('cor')) return '🎨';
    if (c.includes('corpo') || c.includes('físic') || c.includes('fisic') || c.includes('moviment')) return '🤸';
    if (c.includes('eu') || c.includes('outro') || c.includes('hist') || c.includes('geo') || c.includes('ciên') || c.includes('cien')) return '💖';
    return '📚';
  };

  const weeks = useMemo(() => {
    if (!termPlans) return null;
    const byWeek = new Map();
    termPlans.forEach((p) => {
      const ref = p.semana_referencia || p.semana_inicio;
      if (!ref) return;
      const dt = parseISO(ref);
      if (!isValid(dt)) return;
      const monday = startOfWeek(dt, { weekStartsOn: 1 });
      const key = format(monday, 'yyyy-MM-dd');
      if (!byWeek.has(key)) byWeek.set(key, { monday, turmas: new Set() });
      byWeek.get(key).turmas.add(String(p.turma_id));
    });
    const list = [...byWeek.values()].sort((a, b) => a.monday - b.monday);
    const currentMonday = startOfWeek(new Date(), { weekStartsOn: 1 });
    // janela: até 9 semanas terminando na semana atual (ou últimas 9)
    const idxCurrent = list.findIndex((w) => format(w.monday, 'yyyy-MM-dd') === format(currentMonday, 'yyyy-MM-dd'));
    let windowList = list;
    if (list.length > 9) {
      const end = idxCurrent >= 0 ? Math.min(list.length, idxCurrent + 2) : list.length;
      windowList = list.slice(Math.max(0, end - 9), end);
    }
    return windowList.map((w, i) => {
      const cmp = format(w.monday, 'yyyy-MM-dd') === format(currentMonday, 'yyyy-MM-dd')
        ? 'current' : (w.monday < currentMonday ? 'past' : 'future');
      const end = endOfWeek(w.monday, { weekStartsOn: 1 });
      return {
        key: format(w.monday, 'yyyy-MM-dd'),
        label: cmp === 'current' ? 'ATUAL' : `SEM ${i + 1}`,
        dates: `${format(w.monday, 'dd', { locale: ptBR })}–${format(end, 'dd MMM', { locale: ptBR })}`,
        plans: w.turmas.size,
        cls: cmp,
      };
    });
  }, [termPlans]);

  const semanaLabel = useMemo(() => {
    const m = startOfWeek(new Date(), { weekStartsOn: 1 });
    const e = endOfWeek(m, { weekStartsOn: 1 });
    return `${format(m, 'dd/MM')} a ${format(e, 'dd/MM/yyyy')}`;
  }, []);

  if (loading || !dashboardData) {
    return <main className="content"><div className="coord-loader"><div className="coord-spin" /></div></main>;
  }

  return (
    <main className="content">
      <div className="page-header">
        <div>
          <h1 className="page-title">Planejamentos</h1>
          <p className="page-subtitle">{dashboardData.totalTurmas} turmas · semana de {semanaLabel}</p>
        </div>
      </div>

      {/* RESUMO */}
      <div className="summary-bar">
        <div className="summary-item green">
          <div className="summary-label">Planos da semana</div>
          <div className="summary-value">{planosSemana}</div>
          <div className="summary-detail">de {dashboardData.totalTurmas} turmas ativas</div>
        </div>
        <div className="summary-item purple">
          <div className="summary-label">Cobertura BNCC planejada
            <span className="tip" tabIndex={0} data-tip={`Média de componentes/campos da BNCC contemplados por turma nos planos${rotuloPeriodo}.`}>i</span>
          </div>
          <div className="summary-value">{coberturaMediaTxt}{temHeatmap && <span className="summary-suffix">/{heatmapCampos.length}</span>}</div>
          <div className="summary-detail">{temHeatmap ? 'campos por turma (média)' : 'aguardando dados do cache'}</div>
        </div>
        <div className="summary-item amber">
          <div className="summary-label">Planos em construção</div>
          <div className="summary-value">{emConstrucao}</div>
          <div className="summary-detail">sem atividades em algum dia</div>
        </div>
        <div className="summary-item red">
          <div className="summary-label">Lacunas pedagógicas
            <span className="tip" tabIndex={0} data-tip={`Pares turma×campo sem nenhum plano contemplando o campo${rotuloPeriodo}.`}>i</span>
          </div>
          <div className="summary-value">{lacunasCount == null ? '—' : lacunasCount}</div>
          <div className="summary-detail">
            {lacunasCount == null
              ? 'aguardando dados'
              : `em ${lacunasTurmas} ${lacunasTurmas === 1 ? 'turma' : 'turmas'}${turmasSemVinculo > 0 ? ` · ${turmasSemVinculo} sem nenhum vínculo BNCC` : ''}`}
          </div>
        </div>
      </div>

      {/* PLANOS DA SEMANA */}
      <section className="section">
        <div className="section-head">
          <div>
            <h2 className="section-title">{semanaSel ? 'Planos da semana' : 'Planos desta semana'}</h2>
            <p className="section-subtitle">{semanaAtivaLabel}</p>
          </div>
          <div className="week-nav">
            <span className="week-nav-label">{semanaSel ? 'Semana selecionada' : 'Semana atual'}</span>
            {semanaSel && (
              <button onClick={() => selecionarSemana(currentMondayKey)} title="Voltar para a semana atual">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M3 12a9 9 0 1 0 9-9 9 9 0 0 0-6.36 2.64L3 8" /><path d="M3 3v5h5" /></svg>
              </button>
            )}
          </div>
        </div>

        {loadingSemana ? (
          <div className="coord-loader" style={{ minHeight: 120 }}><div className="coord-spin" /></div>
        ) : planRows.length === 0 ? (
          <div className="empty-hint">Nenhum plano registrado nesta semana.</div>
        ) : planRows.map((p) => {
          const dias = p.dias || [];
          const diasComConteudo = DIAS.filter((d) => dayHasContent(dias.find((x) => x.dia_semana === d.key))).length;
          const pct = Math.round((diasComConteudo / DIAS.length) * 100);
          const finalizado = p.status === 'Finalizado';
          const nome = p.turmas?.nome || `Turma ${p.turma_id}`;
          const prof = nomeProfessora(p);
          const tituloDia = dias.map((x) => x.atividades_propostas || x.atividades).find((t) => t && t.trim());
          const titulo = tituloDia ? tituloDia.trim().slice(0, 80) : 'Plano semanal';
          return (
            <div className="plan-row" key={p.id} onClick={() => setPlanoSel(p)} role="button" tabIndex={0}>
              <div className="plan-turma">
                <div className="plan-turma-badge">{turmaBadge(nome)}</div>
                <div className="plan-turma-info">
                  <div className="plan-turma-name">{nome}</div>
                  <div className="plan-turma-prof">{prof}</div>
                </div>
              </div>
              <div className="plan-content">
                <div className="plan-title">{titulo}</div>
                <div className="plan-fields">
                  {DIAS.map((d) => {
                    const on = dayHasContent(dias.find((x) => x.dia_semana === d.key));
                    return <span key={d.key} className={`field-chip ${on ? 'day-on' : 'day-off'}`}>{d.abbr}</span>;
                  })}
                </div>
              </div>
              <div className="plan-status">
                <span className={`pill ${finalizado ? 'pill-ok' : 'pill-warn'}`}>{finalizado ? 'Em execução' : 'Em construção'}</span>
                <div className="plan-progress"><div className="plan-progress-fill" style={{ width: `${pct}%`, background: finalizado ? 'var(--green)' : 'var(--amber)' }} /></div>
                <span className="plan-progress-pct">{pct}%</span>
              </div>
            </div>
          );
        })}
      </section>

      {/* HEATMAP BNCC × TURMAS (planos do recorte selecionado) */}
      <section className="section">
        <div className="section-head">
          <div>
            <h2 className="section-title">Mapa de cobertura BNCC × Turmas
              <span className="tip" tabIndex={0} data-tip={`Cada célula mostra quantos planos da turma contemplam aquele campo/componente${rotuloPeriodo}. Quanto mais escuro, maior a presença. Cinza = ausente.`}>i</span>
            </h2>
            <p className="section-subtitle">Quantos planos contemplam cada campo{periodoDescricao ? ` · ${periodoDescricao}` : ''}</p>
          </div>
        </div>

        {!temHeatmap ? (
          <div className="empty-hint">Cobertura por plano indisponível{rotuloPeriodo}.</div>
        ) : heatRows.length === 0 ? (
          <div className="empty-hint">Nenhum plano com habilidades BNCC{rotuloPeriodo}.</div>
        ) : (
          <>
            <div className="heatmap-wrap">
              <table className="heatmap">
                <thead>
                  <tr>
                    <th className="row-label" />
                    {heatmapCampos.map((c) => (
                      <th className="col-label" key={c}><span className="col-emoji">{campoEmoji(c)}</span>{c}</th>
                    ))}
                    <th className="col-label nohab-col"><span className="col-emoji">⚠️</span>Sem habilidade<br />vinculada</th>
                  </tr>
                </thead>
                <tbody>
                  {heatRows.map((r) => (
                    <tr key={r.id}>
                      <th className="row-label">{r.nome}{r.prof ? ` · ${r.prof}` : ''}</th>
                      {r.celulas.map((n, i) => (
                        <td className={heatClass(n)} key={i} title={`${n} ${n === 1 ? 'plano' : 'planos'}`}>{n === 0 ? '—' : n}</td>
                      ))}
                      <td className={r.semHab > 0 ? 'nohab' : 'h0'} title={`${r.semHab} ${r.semHab === 1 ? 'plano sem BNCC' : 'planos sem BNCC'}`}>{r.semHab === 0 ? '—' : r.semHab}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="heatmap-legend">
              <div className="heatmap-legend-item"><span className="legend-square h0" />Ausente</div>
              <div className="heatmap-legend-item"><span className="legend-square h1" />1 plano</div>
              <div className="heatmap-legend-item"><span className="legend-square h2" />2 planos</div>
              <div className="heatmap-legend-item"><span className="legend-square h3" />3–4 planos</div>
              <div className="heatmap-legend-item"><span className="legend-square h4" />5–6 planos</div>
              <div className="heatmap-legend-item"><span className="legend-square h5" />7+ planos</div>
              <div className="heatmap-legend-item"><span className="legend-square nohab" />Planos sem BNCC vinculada</div>
            </div>
          </>
        )}
      </section>

      {/* CALENDÁRIO */}
      <section className="section">
        <div className="section-head">
          <div>
            <h2 className="section-title">Calendário de planejamento</h2>
            <p className="section-subtitle">Clique em uma semana para ver os planos dela acima</p>
          </div>
        </div>
        {!weeks && <div className="empty-hint">Carregando calendário…</div>}
        {weeks && weeks.length === 0 && <div className="empty-hint">Sem planos registrados no período.</div>}
        {weeks && weeks.length > 0 && (
          <div className="calendar-bar" style={{ gridTemplateColumns: `repeat(${Math.min(9, weeks.length)}, 1fr)` }}>
            {weeks.map((w) => {
              const ativa = semanaSel ? w.key === semanaSel : w.cls === 'current';
              return (
              <div
                className={`calendar-week ${w.cls}${ativa ? ' selected' : ''}`}
                key={w.key}
                role="button"
                tabIndex={0}
                onClick={() => selecionarSemana(w.key)}
              >
                <div className="week-num">{w.label}</div>
                <div className="week-dates">{w.dates}</div>
                <div className="week-plans">{w.plans} {w.plans === 1 ? 'plano' : 'planos'}</div>
              </div>
              );
            })}
          </div>
        )}
      </section>

      <div className="manifesto">
        <div className="manifesto-icon">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z" /></svg>
        </div>
        <div className="manifesto-text">
          <strong>Planejar não é preencher campos — é dar intencionalidade ao olhar.</strong> A Nara mostra a coerência entre o que foi planejado e o que foi efetivamente vivido com as crianças, sem transformar a docência em prestação de contas burocrática.
        </div>
      </div>

      {planoSel && (() => {
        const dias = planoSel.dias || [];
        const diasComConteudo = DIAS.filter((d) => dayHasContent(dias.find((x) => x.dia_semana === d.key))).length;
        const pct = Math.round((diasComConteudo / DIAS.length) * 100);
        const finalizado = planoSel.status === 'Finalizado';
        const nome = planoSel.turmas?.nome || `Turma ${planoSel.turma_id}`;
        const prof = nomeProfessora(planoSel);
        const tituloDia = dias.map((x) => x.atividades_propostas || x.atividades).find((t) => t && t.trim());
        return (
          <div className="plan-modal-overlay" onClick={() => setPlanoSel(null)}>
            <div className="plan-modal" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true">
              <div className="plan-modal-head">
                <div className="plan-modal-id">
                  <div className="plan-modal-badge">{turmaBadge(nome)}</div>
                  <div style={{ minWidth: 0 }}>
                    <div className="plan-modal-turma">{nome}</div>
                    <div className="plan-modal-sub">Prof. {prof} · semana de {semanaLabel}</div>
                  </div>
                </div>
                <button className="plan-modal-close" onClick={() => setPlanoSel(null)} title="Fechar" aria-label="Fechar">×</button>
              </div>

              <div className="plan-modal-status">
                <span className={`pill ${finalizado ? 'pill-ok' : 'pill-warn'}`}>{finalizado ? 'Em execução' : 'Em construção'}</span>
                <div className="plan-progress" style={{ width: 100 }}><div className="plan-progress-fill" style={{ width: `${pct}%`, background: finalizado ? 'var(--green)' : 'var(--amber)' }} /></div>
                <span className="plan-progress-pct">{pct}% dos dias preenchidos</span>
              </div>

              {tituloDia && <div className="plan-modal-title">{tituloDia.trim()}</div>}

              <div>
                {DIAS.map((d) => {
                  const dia = dias.find((x) => x.dia_semana === d.key);
                  const txt = (dia?.atividades_propostas || dia?.atividades || '').trim();
                  return (
                    <div className="plan-modal-day" key={d.key}>
                      <div className="plan-modal-day-name">{d.label}</div>
                      <div className="plan-modal-day-body">{txt ? txt : <span className="muted">Sem atividade registrada</span>}</div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        );
      })()}
    </main>
  );
}
