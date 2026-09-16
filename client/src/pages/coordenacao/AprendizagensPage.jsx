import React, { useEffect, useMemo, useState } from 'react';
import { useCoordinatorData } from '@/components/coordinator/v2/CoordinatorDataContext';
import { authFetch, API_BASE_URL } from '@/services/api';
import { formatLeituraLabel } from '@/lib/observationUtils';
import './aprendizagens.css';

// Colunas de produções (classificação mais recente por criança no período).
const PRODUCOES = [
  { key: 'escrita', emoji: '✏️', label: 'Escrita' },
  { key: 'desenho', emoji: '🎨', label: 'Desenho' },
  { key: 'leitura', emoji: '📖', label: 'Leitura' },
];
const rotuloProducao = (key, cell) => {
  if (!cell || !cell.classe) return '—';
  return key === 'leitura' ? formatLeituraLabel(cell.classe) : cell.classe;
};

/*
 * Estado da marcação (0–3) → classe/símbolo/rótulo.
 *
 * Os rótulos dizem FREQUÊNCIA DE REGISTRO, não nível de desenvolvimento: o
 * número é a contagem de vezes que a professora marcou o indicador no Registro
 * Guiado (`resposta` é sempre "Sim"; não há registro de "não consegue"). Os
 * nomes antigos — "Às vezes / Em desenvolvimento / Desenvolvido" — prometiam
 * uma avaliação que o instrumento não faz: três marcações numa semana atenta
 * viravam "Desenvolvido", e uma criança que consolidou a habilidade há meses
 * aparecia como "Às vezes" só porque a professora passou a marcar outros
 * indicadores.
 */
const ESTADOS = {
  0: { cls: 'naoObs', sym: '—', label: 'Sem registro' },
  1: { cls: 'asVezes', sym: '~', label: 'Registrado 1×' },
  2: { cls: 'emDesenv', sym: '↑', label: 'Registrado 2×' },
  3: { cls: 'desenv', sym: '✓', label: 'Registrado 3× ou mais' },
};

const campoEmoji = (campo = '') => {
  const c = campo.toLowerCase();
  if (c.includes('portug') || c.includes('língua') || c.includes('lingua') || c.includes('escuta') || c.includes('linguagem')) return '📖';
  if (c.includes('matem') || c.includes('número') || c.includes('numero') || c.includes('quantidade')) return '🔢';
  if (c.includes('art') || c.includes('traço') || c.includes('traco') || c.includes('cor')) return '🎨';
  if (c.includes('corpo') || c.includes('físic') || c.includes('fisic') || c.includes('moviment')) return '🤸';
  if (c.includes('ciên') || c.includes('cien') || c.includes('natur')) return '🔬';
  if (c.includes('hist') || c.includes('geo') || c.includes('eu') || c.includes('outro')) return '💖';
  return '•';
};

export default function AprendizagensPage() {
  const { loading, viewData, periodoId, intervalo, periodoInfo } = useCoordinatorData();
  const turmas = useMemo(
    () => [...(viewData?.turmas || [])].sort((a, b) => (a.nome || '').localeCompare(b.nome || '', 'pt')),
    [viewData],
  );

  const [turmaId, setTurmaId] = useState('');
  const [data, setData] = useState(null);
  const [carregando, setCarregando] = useState(false);
  const [erro, setErro] = useState(false);

  // Turma inicial = primeira da lista.
  useEffect(() => {
    if (!turmaId && turmas.length) setTurmaId(String(turmas[0].id));
  }, [turmas, turmaId]);

  useEffect(() => {
    if (!turmaId) return;
    let cancel = false;
    setCarregando(true);
    setErro(false);
    const params = new URLSearchParams({ turma_id: turmaId });
    // Recorte vem do seletor do layout — para ver o consolidado do ano, a
    // coordenação escolhe "Escolher datas…" e abre o intervalo lá.
    if (intervalo) {
      params.set('data_inicio', intervalo.inicio);
      params.set('data_fim', intervalo.fim);
    } else if (periodoId) {
      params.set('periodo_id', periodoId);
    }
    authFetch(`${API_BASE_URL}/coordenacao/indicadores-turma/?${params.toString()}`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error('Falha ao carregar indicadores'))))
      .then((d) => { if (!cancel) setData(d); })
      .catch((e) => { if (cancel) return; console.error(e); setErro(true); setData(null); })
      .finally(() => { if (!cancel) setCarregando(false); });
    return () => { cancel = true; };
  }, [turmaId, periodoId, intervalo]);

  // Lista achatada de indicadores na ordem das categorias.
  const indicadores = useMemo(
    () => (data?.categorias || []).flatMap((cat) => cat.perguntas.map((p) => ({ ...p, campo: cat.campo }))),
    [data],
  );

  const resumo = data?.resumo || { naoObs: 0, asVezes: 0, emDesenv: 0, desenv: 0 };
  const totalMarc = data?.total_marcacoes || 0;
  const pct = (n) => (totalMarc > 0 ? Math.round((n / totalMarc) * 100) : 0);

  const exportarCsv = () => {
    if (!data) return;
    const head = ['Criança', ...PRODUCOES.map((p) => p.label), ...indicadores.map((i) => `"${(i.label || '').replace(/"/g, "'")}"`)];
    const linhas = (data.criancas || []).map((c) => {
      const row = data.matriz?.[String(c.id)] || {};
      const prod = data.producoes?.[String(c.id)] || {};
      return [
        `"${c.nome}"`,
        ...PRODUCOES.map((p) => `"${rotuloProducao(p.key, prod[p.key])}"`),
        ...indicadores.map((i) => ESTADOS[row[String(i.id)] || 0].label),
      ].join(',');
    });
    const csv = [head.join(','), ...linhas].join('\n');
    const blob = new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `indicadores_${(data.turma?.nome || 'turma').replace(/\s+/g, '_')}.csv`;
    document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url);
  };

  if (loading) {
    return <main className="content"><div className="coord-loader"><div className="coord-spin" /></div></main>;
  }

  return (
    <main className="content">
      <div className="page-header">
        <div>
          <h1 className="page-title">Aprendizagens consolidadas</h1>
          <p className="page-subtitle">
            Indicadores marcados no Registro Guiado{data?.turma ? ` · ${data.turma.nome}` : ''}{periodoInfo?.descricao ? ` · ${periodoInfo.descricao}` : ''}
          </p>
        </div>
      </div>

      {/* FILTRO: turma. O período vem do seletor do layout, comum a todas as abas. */}
      <div className="filter-bar">
        <span className="filter-label">Turma:</span>
        {turmas.map((t) => (
          <button key={t.id} className={`filter-chip ${String(turmaId) === String(t.id) ? 'active' : ''}`} onClick={() => setTurmaId(String(t.id))}>{t.nome}</button>
        ))}
      </div>

      {/* RESUMO POR ESTADO */}
      <div className="state-summary">
        {[
          { k: 'naoObs', label: 'Sem registro' },
          { k: 'asVezes', label: 'Registrado 1×' },
          { k: 'emDesenv', label: 'Registrado 2×' },
          { k: 'desenv', label: 'Registrado 3× ou mais' },
        ].map((s) => (
          <div className="state-card" key={s.k}>
            <div className={`state-indicator ${s.k}`}>{Object.values(ESTADOS).find((e) => e.cls === s.k)?.sym}</div>
            <div className="state-info">
              <div className="state-label">{s.label}</div>
              <div className="state-value">{resumo[s.k]}</div>
              <div className="state-pct">{pct(resumo[s.k])}% das marcações possíveis</div>
            </div>
          </div>
        ))}
      </div>

      {/* TABELA DE INDICADORES */}
      <div className="ind-table-wrap">
        <div className="table-header">
          <div>
            <div className="table-title">{data?.turma?.nome || 'Turma'} · Tabela de indicadores
              <span className="tip" tabIndex={0} data-tip="Cada célula é o estado da aprendizagem da criança naquele indicador, conforme marcado no Registro Guiado (1x=às vezes, 2x=em desenvolvimento, 3x=desenvolvido). Filtro: período avaliativo selecionado.">i</span>
            </div>
            <div className="table-subtitle">{(data?.criancas || []).length} crianças · {indicadores.length} indicadores</div>
          </div>
          <div className="table-actions">
            <button className="btn btn-secondary" onClick={exportarCsv} disabled={!data || indicadores.length === 0}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3" /></svg>
              Exportar
            </button>
          </div>
        </div>

        {carregando ? (
          <div className="coord-loader" style={{ minHeight: 160 }}><div className="coord-spin" /></div>
        ) : erro ? (
          <div className="empty-hint">Não foi possível carregar os indicadores desta turma.</div>
        ) : indicadores.length === 0 || (data?.criancas || []).length === 0 ? (
          <div className="empty-hint">Sem indicadores cadastrados para a faixa desta turma, ou turma sem crianças.</div>
        ) : (
          <>
            <table className="indicators-table">
              <thead>
                <tr>
                  <th rowSpan={2} style={{ verticalAlign: 'bottom', paddingBottom: 16 }}>Criança</th>
                  <th colSpan={PRODUCOES.length} className="category">📦 Produções</th>
                  {(data?.categorias || []).map((cat) => (
                    <th key={cat.campo} colSpan={cat.perguntas.length} className="category">{campoEmoji(cat.campo)} {cat.campo}</th>
                  ))}
                </tr>
                <tr>
                  {PRODUCOES.map((p) => (
                    <th key={p.key} className="prod-col">{p.emoji} {p.label}</th>
                  ))}
                  {indicadores.map((i) => (
                    <th key={i.id} className="rotated"><div title={i.label}>{i.label}</div></th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {(data?.criancas || []).map((c) => {
                  const row = data.matriz?.[String(c.id)] || {};
                  const prod = data.producoes?.[String(c.id)] || {};
                  return (
                    <tr key={c.id}>
                      <td className="name">{c.nome}</td>
                      {PRODUCOES.map((p) => {
                        const cell = prod[p.key];
                        return (
                          <td className="prod-cell" key={p.key} title={cell?.data ? `Último registro: ${cell.data}` : 'Sem registro no período'}>
                            {rotuloProducao(p.key, cell)}
                          </td>
                        );
                      })}
                      {indicadores.map((i) => {
                        const est = ESTADOS[row[String(i.id)] || 0];
                        return (
                          <td className="cell-center" key={i.id}>
                            <span className={`cell-mark ${est.cls}`} title={est.label}>{est.sym}</span>
                          </td>
                        );
                      })}
                    </tr>
                  );
                })}
              </tbody>
            </table>

            <div className="legend">
              {[
                { k: 'naoObs', label: 'Não observado' },
                { k: 'asVezes', label: 'Às vezes' },
                { k: 'emDesenv', label: 'Em desenvolvimento' },
                { k: 'desenv', label: 'Desenvolvido' },
              ].map((s) => (
                <div className="legend-item" key={s.k}><span className={`legend-dot ${s.k}`} />{s.label}</div>
              ))}
            </div>
          </>
        )}
      </div>

      <div className="ai-disclaimer" style={{ marginTop: 16, padding: '16px 20px', background: 'var(--amber-bg)', borderRadius: 14, borderLeft: '4px solid var(--amber)', fontSize: 12.5, lineHeight: 1.5 }}>
        <div><strong style={{ color: 'var(--amber)' }}>Nota:</strong> a "Hipótese de escrita" (categoria nominal) e o "Banco de hipóteses" do mockup dependem da modalidade Análise e ainda não estão incluídos — esta versão entrega a matriz de indicadores do Guiado. A Nara só relata o que foi observado.</div>
      </div>
    </main>
  );
}
