import React, { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useCoordinatorData } from '@/components/coordinator/v2/CoordinatorDataContext';
import { toValidDate } from '@/lib/dateUtils';
import { formatDistanceToNow, differenceInDays } from 'date-fns';
import { ptBR } from 'date-fns/locale';
import { perfilLabelDocente as perfilLabel } from '@/constants/perfis';
import './professoras.css';

const initials = (nome = '') => nome.trim().split(/\s+/).slice(0, 2).map((w) => w[0] || '').join('').toUpperCase() || '–';

/*
 * Status derivado APENAS da recência do último login.
 *
 * Os rótulos descrevem frequência de acesso, não qualidade do trabalho:
 * "Saudável" e "Apoio" prometiam um diagnóstico pedagógico que o dado não
 * sustenta — a conta é só "há quantos dias entrou no sistema".
 *
 * "Nunca acessou" tem chave própria (antes caía em `apoio`): quem nunca entrou
 * provavelmente está com a conta não ativada — problema de onboarding, ação
 * diferente de quem se afastou depois de usar.
 */
const EXPLICACAO_STATUS = 'Baseado no último acesso ao sistema';

const statusFromLogin = (last) => {
  const d = toValidDate(last);
  if (!d) return { label: 'Nunca acessou', cls: 'pill-critical', key: 'nunca' };
  const days = differenceInDays(new Date(), d);
  if (days <= 7) return { label: 'Uso frequente', cls: 'pill-ok', key: 'frequente' };
  if (days <= 30) return { label: 'Uso ocasional', cls: 'pill-warn', key: 'ocasional' };
  return { label: 'Pouco uso', cls: 'pill-critical', key: 'pouco' };
};

const lastLoginLabel = (last) => {
  const d = toValidDate(last);
  if (!d) return 'Nunca acessou';
  return formatDistanceToNow(d, { addSuffix: true, locale: ptBR });
};

const STATUS_FILTERS = [
  { key: 'all', label: 'Todas' },
  { key: 'frequente', label: 'Uso frequente' },
  { key: 'ocasional', label: 'Uso ocasional' },
  { key: 'pouco', label: 'Pouco uso' },
  { key: 'nunca', label: 'Nunca acessou' },
];

export default function ProfessorasPage() {
  const { loading, dashboardData, viewData } = useCoordinatorData();
  const navigate = useNavigate();
  const [statusF, setStatusF] = useState('all');
  const [search, setSearch] = useState('');

  // Drill-down produções: { prof, turmaId|null } — modal em 2 etapas (turma → aluno).
  const [drill, setDrill] = useState(null);

  const professores = viewData?.professores || [];
  const todasTurmas = viewData?.turmas || [];
  const todasCriancas = viewData?.criancas || [];

  // Turmas (com id) vinculadas à professora — resolvidas por nome (viewData traz só nomes).
  const turmasDaProfessora = (prof) => {
    const nomes = prof?.turmas || [];
    return todasTurmas
      .filter((t) => nomes.includes(t.nome))
      .sort((a, b) => (a.nome || '').localeCompare(b.nome || '', 'pt'));
  };
  const alunosDaTurma = (turmaId) =>
    todasCriancas
      .filter((c) => String(c.turma_id) === String(turmaId))
      .sort((a, b) => (a.nome_completo || '').localeCompare(b.nome_completo || '', 'pt'));

  // Abre o modal já na etapa de alunos quando a professora tem só uma turma.
  const abrirDrill = (prof) => {
    const ts = turmasDaProfessora(prof);
    setDrill({ prof, turmaId: ts.length === 1 ? String(ts[0].id) : null });
  };
  const irParaCrianca = (criancaId) => {
    setDrill(null);
    navigate(`/coordenacao/crianca/${criancaId}`);
  };

  const enriched = useMemo(() => {
    return [...professores]
      .map((p) => ({ ...p, _status: statusFromLogin(p.last_login) }))
      .sort((a, b) => (a.nome || '').localeCompare(b.nome || '', 'pt'));
  }, [professores]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return enriched.filter((p) => {
      const sOk = statusF === 'all' || p._status.key === statusF;
      const qOk = !q || (p.nome || '').toLowerCase().includes(q);
      return sOk && qOk;
    });
  }, [enriched, statusF, search]);

  // "Pouco uso" e "Nunca acessou" contam separado: a primeira é afastamento,
  // a segunda quase sempre é conta não ativada — a ação da coordenação difere.
  const poucoUso = enriched.filter((p) => p._status.key === 'pouco').length;
  const nuncaAcessaram = enriched.filter((p) => p._status.key === 'nunca').length;
  const acessaramRecente = enriched.filter((p) => p._status.key === 'frequente').length;

  if (loading || !dashboardData) {
    return <main className="content"><div className="coord-loader"><div className="coord-spin" /></div></main>;
  }

  return (
    <main className="content">
      <div className="page-header">
        <div>
          <h1 className="page-title">Equipe docente</h1>
          <p className="page-subtitle">{enriched.length} professoras · acompanhamento de engajamento</p>
        </div>
      </div>

      <div className="summary-bar">
        <div className="summary-item">
          <div className="summary-label">Professoras ativas</div>
          <div className="summary-value">{enriched.length}</div>
        </div>
        <div className="summary-item">
          <div className="summary-label">Acessaram na última semana</div>
          <div className="summary-value">{acessaramRecente}</div>
        </div>
        <div className="summary-item">
          {/* Não é "precisam de apoio": o dado é recência de login, não
              qualidade do trabalho. O rótulo diz o que a conta mede. */}
          <div className="summary-label">Sem acesso há 30 dias</div>
          <div className="summary-value">{poucoUso}</div>
        </div>
        <div className="summary-item">
          <div className="summary-label">Nunca acessaram</div>
          <div className="summary-value">{nuncaAcessaram}</div>
        </div>
      </div>

      <div className="filter-bar">
        <div className="search-box">
          <svg className="search-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="7" /><path d="m21 21-4.3-4.3" /></svg>
          <input className="search-input" type="text" placeholder="Buscar professora…" value={search} onChange={(e) => setSearch(e.target.value)} />
        </div>
        <span className="filter-label">Status:</span>
        {STATUS_FILTERS.map((f) => (
          <button key={f.key} className={`filter-chip ${statusF === f.key ? 'active' : ''}`} onClick={() => setStatusF(f.key)}>{f.label}</button>
        ))}
      </div>

      {filtered.length === 0 && <div className="empty-hint">Nenhuma professora encontrada.</div>}

      {filtered.map((p) => {
        const turmas = p.turmas || [];
        return (
          <div className="teacher-card" key={p.id}>
            <div className="teacher-head">
              <div className="teacher-avatar">{initials(p.nome)}</div>
              <div className="teacher-identity">
                <div className="teacher-name">{p.nome}</div>
                <div className="teacher-role">{perfilLabel(p.perfil)}{turmas.length > 0 ? ` · ${turmas.join(' · ')}` : ' · sem turma vinculada'}</div>
              </div>
              <div className="teacher-status">
                {/* title: mesmo "Uso frequente" não diz uso de quê — o dado é login. */}
                <span className={`pill ${p._status.cls}`} title={EXPLICACAO_STATUS}>{p._status.label}</span>
                <button className="teacher-prod-btn" onClick={() => abrirDrill(p)}>
                  Ver produções por turma
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round"><path d="M9 18l6-6-6-6" /></svg>
                </button>
              </div>
            </div>

            <div className="teacher-metrics">
              <div className="metric-block">
                <div className="metric-label">Último acesso</div>
                <div className="metric-value" style={{ fontSize: 14 }}>{lastLoginLabel(p.last_login)}</div>
              </div>
              <div className="metric-block">
                <div className="metric-label">Turmas</div>
                <div className="modalities">
                  {turmas.length === 0 && <span className="metric-sub">—</span>}
                  {turmas.map((t, i) => <span key={i} className="mod-pill voz">{t}</span>)}
                </div>
              </div>
              <div className="metric-block">
                <div className="metric-label">E-mail</div>
                <div className="metric-sub" style={{ wordBreak: 'break-all' }}>{p.email || '—'}</div>
              </div>
            </div>
          </div>
        );
      })}

      <div className="manifesto">
        <div className="manifesto-icon">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z" /></svg>
        </div>
        <div className="manifesto-text">
          <strong>Acompanhar não é vigiar.</strong> Os sinais de engajamento existem para a coordenação oferecer apoio a quem precisa — nunca para ranquear ou cobrar a docência.
        </div>
      </div>

      {drill && (() => {
        const turmas = turmasDaProfessora(drill.prof);
        const turmaSel = turmas.find((t) => String(t.id) === String(drill.turmaId));
        const alunos = turmaSel ? alunosDaTurma(turmaSel.id) : [];
        const naEtapaAlunos = !!turmaSel;
        // "Voltar" só faz sentido se há mais de uma turma para escolher.
        const podeVoltar = naEtapaAlunos && turmas.length > 1;
        return (
          <div className="prod-modal-overlay" onClick={() => setDrill(null)}>
            <div className="prod-modal" onClick={(e) => e.stopPropagation()}>
              <div className="prod-modal-head">
                <div>
                  <div className="prod-modal-title">{drill.prof.nome}</div>
                  <div className="prod-modal-sub">
                    {naEtapaAlunos
                      ? <>Produções · <strong>{turmaSel.nome}</strong> · escolha o aluno</>
                      : 'Escolha a turma para ver as produções'}
                  </div>
                </div>
                <button className="prod-modal-close" onClick={() => setDrill(null)} aria-label="Fechar">✕</button>
              </div>

              <div className="prod-modal-body">
                {!naEtapaAlunos ? (
                  turmas.length === 0 ? (
                    <div className="empty-hint">Esta professora não tem turma vinculada.</div>
                  ) : (
                    <div className="prod-chip-grid">
                      {turmas.map((t) => (
                        <button key={t.id} className="prod-chip" onClick={() => setDrill({ ...drill, turmaId: String(t.id) })}>
                          <span className="prod-chip-name">{t.nome}</span>
                          <span className="prod-chip-count">{alunosDaTurma(t.id).length} crianças</span>
                        </button>
                      ))}
                    </div>
                  )
                ) : (
                  <>
                    {podeVoltar && (
                      <button className="prod-back" onClick={() => setDrill({ ...drill, turmaId: null })}>‹ Trocar turma</button>
                    )}
                    {alunos.length === 0 ? (
                      <div className="empty-hint">Nenhuma criança nesta turma.</div>
                    ) : (
                      <div className="prod-aluno-list">
                        {alunos.map((a) => (
                          <button key={a.id} className="prod-aluno-row" onClick={() => irParaCrianca(a.id)}>
                            <span className="prod-aluno-avatar">{initials(a.nome_completo)}</span>
                            <span className="prod-aluno-nome">{a.nome_completo}</span>
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round"><path d="M9 18l6-6-6-6" /></svg>
                          </button>
                        ))}
                      </div>
                    )}
                  </>
                )}
              </div>
            </div>
          </div>
        );
      })()}
    </main>
  );
}