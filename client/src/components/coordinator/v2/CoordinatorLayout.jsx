import React, { useState, useEffect, useRef } from 'react';
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { Helmet } from 'react-helmet-async';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';
import { LogOut, Loader2 } from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';
import { useToast } from '@/components/ui/use-toast'; // ajuste o caminho se o hook estiver em outro lugar (ex: '@/hooks/use-toast')
import { safeFormatDate } from '@/lib/dateUtils';
import { apiService } from '@/services/api';
import { apiClient } from '@/lib/apiClient';
import { CoordinatorDataProvider, useCoordinatorData } from './CoordinatorDataContext';
import './coordTheme.css';

/* Ícones da tabbar (portados 1:1 dos mockups) */
const Icon = ({ d, children, ...p }) => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...p}>
    {children || <path d={d} />}
  </svg>
);

const TABS = [
  { to: '/coordenacao', end: true, title: 'Pulso da escola', svg: (<><rect x="3" y="3" width="7" height="7" rx="1.5" /><rect x="14" y="3" width="7" height="7" rx="1.5" /><rect x="3" y="14" width="7" height="7" rx="1.5" /><rect x="14" y="14" width="7" height="7" rx="1.5" /></>) },
  { to: '/coordenacao/planejamentos', title: 'Planejamentos', svg: (<><rect x="3" y="4" width="18" height="18" rx="2" /><path d="M16 2v4M8 2v4M3 10h18" /></>) },
  { to: '/coordenacao/relatorios', title: 'Relatórios', svg: (<><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><path d="M14 2v6h6M16 13H8M16 17H8M10 9H8" /></>) },
  { to: '/coordenacao/templates/escolher-modelo', title: 'Templates de capa', svg: (<><rect x="3" y="3" width="18" height="18" rx="2" /><path d="M3 9h18" /><circle cx="7.5" cy="6" r="0.8" fill="currentColor" stroke="none" /></>) },
  { to: '/coordenacao/turmas', title: 'Crianças e turmas', svg: (<><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" /><circle cx="9" cy="7" r="4" /><path d="M23 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75" /></>) },
  { to: '/coordenacao/professoras', title: 'Professoras', svg: (<><path d="M21.42 10.922a1 1 0 0 0-.019-1.838L12.83 5.18a2 2 0 0 0-1.66 0L2.6 9.08a1 1 0 0 0 0 1.832l8.57 3.908a2 2 0 0 0 1.66 0z" /><path d="M22 10v6" /><path d="M6 12.5V16a6 3 0 0 0 12 0v-3.5" /></>) },
  { to: '/coordenacao/area-do-professor', title: 'Área do professor', svg: (<><rect x="2" y="7" width="20" height="14" rx="2" /><path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16" /></>) },
  { to: '/coordenacao/atencao', title: 'Atenção pedagógica', badgeKey: 'alerts', svg: (<><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" /><path d="M13.73 21a2 2 0 0 1-3.46 0" /></>) },
  { to: '/coordenacao/aprendizagens', title: 'Aprendizagens consolidadas', svg: (<><line x1="18" y1="20" x2="18" y2="10" /><line x1="12" y1="20" x2="12" y2="4" /><line x1="6" y1="20" x2="6" y2="14" /></>) },
];

/* Valor sentinela do <select> para o modo "escolher datas". */
const MODO_INTERVALO = '__intervalo__';

const hojeISO = () => new Date().toISOString().slice(0, 10);

/** Mensagem de erro do intervalo, ou null se estiver válido. */
function validarIntervalo({ inicio, fim }, maxDias) {
  if (!inicio || !fim) return null;         // ainda preenchendo
  if (inicio > fim) return 'A data inicial é depois da final.';
  const dias = Math.round((new Date(fim) - new Date(inicio)) / 86400000) + 1;
  if (dias > maxDias) return `Máximo de ${maxDias} dias (pedido: ${dias}).`;
  return null;
}

function Shell() {
  const { user, signOut } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const { toast } = useToast();
  const {
    viewData, cacheGeradoEm, loading, statusCarregamento,
    periodos, periodoId, periodoSelecionado,
    intervalo, maxDiasIntervalo, selecionarPeriodo, selecionarIntervalo,
  } = useCoordinatorData();

  // Datas ainda sendo digitadas — só viram recorte de verdade no "Aplicar",
  // senão cada tecla dispararia um recálculo no servidor.
  const [rascunho, setRascunho] = useState(null);

  // --- Notificações (sino) ---
  // Dropdown próprio (sem depender de @/components/ui/popover) para evitar
  // problemas de layout caso esse componente não exista/esteja incompleto
  // no projeto. NotificationDetailPage exige ?tipo=...&chave=... na URL,
  // então nunca podemos navegar direto para /notificacoes sem escolher um
  // alerta específico da lista primeiro.
  const notifWrapRef = useRef(null);
  const [alertsOpen, setAlertsOpen] = useState(false);
  const [alertsList, setAlertsList] = useState([]);
  const [alertsLoading, setAlertsLoading] = useState(false);

  // Fecha o dropdown ao clicar fora dele.
  useEffect(() => {
    if (!alertsOpen) return;
    const handleClickOutside = (event) => {
      if (notifWrapRef.current && !notifWrapRef.current.contains(event.target)) {
        setAlertsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [alertsOpen]);

  useEffect(() => {
    if (!alertsOpen || !user) return;
    let cancelled = false;

    const fetchAlerts = async () => {
      setAlertsLoading(true);
      try {
        const data = await apiService.listarAlertas();
        if (!cancelled) setAlertsList(Array.isArray(data) ? data : []);
      } catch (error) {
        if (!cancelled) {
          toast({
            variant: 'destructive',
            title: 'Erro ao carregar alertas',
            description: 'Não foi possível buscar as notificações.',
          });
        }
      } finally {
        if (!cancelled) setAlertsLoading(false);
      }
    };

    fetchAlerts();
    return () => { cancelled = true; };
  }, [alertsOpen, user, toast]);

  const handleOpenAlertDetail = async (alert) => {
    if (!user) return;

    try {
      await apiClient.from('alertas_lidos').insert({
        usuario_id: user.id,
        alerta_tipo: alert.tipo,
        alerta_chave: alert.id,
      });
      setAlertsList((prev) => prev.filter((item) => item.id !== alert.id));
    } catch (error) {
      // Falha ao marcar como lido não deve bloquear a navegação até o detalhe.
    } finally {
      const params = new URLSearchParams({ tipo: alert.tipo, chave: alert.id });
      navigate(`/notificacoes?${params.toString()}`);
      setAlertsOpen(false);
    }
  };
  // --- Fim notificações ---

  const emModoIntervalo = !!rascunho || !!intervalo;
  const rascunhoAtual = rascunho
    || (intervalo ? { inicio: intervalo.inicio, fim: intervalo.fim } : { inicio: '', fim: '' });
  const erroIntervalo = validarIntervalo(rascunhoAtual, maxDiasIntervalo);

  const badges = { alerts: viewData?.alerts?.length || 0 };

  const isActive = (tab) => {
    if (tab.end) return location.pathname === tab.to;
    return location.pathname === tab.to || location.pathname.startsWith(tab.to + '/');
  };

  return (
    <div className="coord-shell">
      <Helmet>
        <title>NARA · Coordenação</title>
        <meta name="description" content="Painel de coordenação pedagógica NARA." />
      </Helmet>

      <header className="topbar">
        <Link to="/" className="logo-block">
          <img className="logo-icon" src="/nara-logo.png" alt="NARAEDU" width="38" height="38" />
          <div className="logo-text-wrap">
            <span className="logo-text">NARAEDU</span>
            <span className="logo-text-sub">NÚCLEO DE ACOMPANHAMENTO<br />E REGISTRO DA APRENDIZAGEM</span>
          </div>
        </Link>
        <div className="topbar-right">
          <div className="notif-wrap" ref={notifWrapRef}>
            <button
              type="button"
              className="bell-btn"
              title="Notificações"
              onClick={() => setAlertsOpen((prev) => !prev)}
            >
              <Icon width="22" height="22"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" /><path d="M13.73 21a2 2 0 0 1-3.46 0" /></Icon>
              {alertsList.length > 0 && <span className="bell-dot" />}
            </button>

            {alertsOpen && (
              <div className="notif-panel">
                <div className="notif-head">
                  <span className="notif-title">Notificações</span>
                  {alertsList.length > 0 && (
                    <span className="notif-count">{alertsList.length} não lida(s)</span>
                  )}
                </div>

                {alertsLoading ? (
                  <div className="notif-loading">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    <span>Carregando alertas...</span>
                  </div>
                ) : alertsList.length === 0 ? (
                  <p className="notif-empty">Nenhuma notificação pendente.</p>
                ) : (
                  <ul className="notif-list">
                    {alertsList.map((alert) => (
                      <li key={alert.id}>
                        <button
                          type="button"
                          className="notif-item"
                          onClick={() => handleOpenAlertDetail(alert)}
                        >
                          {alert.titulo || alert.mensagem || 'Ver detalhe do alerta'}
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}
          </div>

          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button className="avatar-btn" title={user?.user_metadata?.nome ?? user?.nome ?? 'Perfil'}>
                <Icon width="22" height="22"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" /><circle cx="12" cy="7" r="4" /></Icon>
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={signOut}>
                <LogOut className="mr-2 h-4 w-4" /> Sair
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </header>

      <nav className="tabbar">
        {TABS.map((tab) => (
          <NavLink
            key={tab.to}
            to={tab.to}
            end={tab.end}
            className={`tab ${isActive(tab) ? 'active' : ''}`}
            title={tab.title}
          >
            <Icon>{tab.svg}</Icon>
            {tab.badgeKey && badges[tab.badgeKey] > 0 && (
              <span className="tab-badge">{badges[tab.badgeKey]}</span>
            )}
          </NavLink>
        ))}
      </nav>

      <div className="cache-line">
        <label htmlFor="periodo-coordenacao" className="periodo-label">Período</label>
        <select
          id="periodo-coordenacao"
          className="periodo-select"
          value={emModoIntervalo ? MODO_INTERVALO : (periodoId || '')}
          disabled={loading}
          onChange={(e) => {
            const v = e.target.value;
            if (v === MODO_INTERVALO) {
              // Semeia o intervalo com o período que estava selecionado, para
              // a coordenadora ajustar a partir de algo conhecido.
              const base = periodoSelecionado;
              setRascunho({
                inicio: base?.data_inicio || hojeISO(),
                fim: base?.data_fim || hojeISO(),
              });
            } else {
              setRascunho(null);
              selecionarPeriodo(v || null);
            }
          }}
        >
          {periodos.length === 0 && <option value="">Nenhum período cadastrado</option>}
          {periodos.map((p) => (
            <option key={p.id} value={p.id}>
              {p.descricao}{p.em_curso ? ' (em curso)' : ''}
            </option>
          ))}
          <option value={MODO_INTERVALO}>Escolher datas…</option>
        </select>

        {!emModoIntervalo && periodoSelecionado && (
          <span className="periodo-intervalo">
            {safeFormatDate(periodoSelecionado.data_inicio, 'dd/MM/yyyy')}
            {' – '}
            {safeFormatDate(periodoSelecionado.data_fim, 'dd/MM/yyyy')}
          </span>
        )}

        {emModoIntervalo && (
          <span className="periodo-datas">
            <input
              type="date"
              className="periodo-data-input"
              aria-label="Data inicial"
              value={rascunhoAtual.inicio}
              onChange={(e) => setRascunho({ ...rascunhoAtual, inicio: e.target.value })}
            />
            <span aria-hidden="true">–</span>
            <input
              type="date"
              className="periodo-data-input"
              aria-label="Data final"
              value={rascunhoAtual.fim}
              onChange={(e) => setRascunho({ ...rascunhoAtual, fim: e.target.value })}
            />
            <button
              type="button"
              className="cache-refresh"
              disabled={loading || !!erroIntervalo || !rascunhoAtual.inicio || !rascunhoAtual.fim}
              onClick={() => selecionarIntervalo(rascunhoAtual.inicio, rascunhoAtual.fim)}
            >
              Aplicar
            </button>
            {erroIntervalo && <span style={{ color: 'var(--amber)' }}>{erroIntervalo}</span>}
          </span>
        )}

        <span className="cache-sep" aria-hidden="true">·</span>

        {loading ? (
          <span className="carregando-status" role="status" aria-live="polite">
            <span className="carregando-spin" aria-hidden="true" />
            {statusCarregamento || 'Carregando…'}
          </span>
        ) : cacheGeradoEm ? (
          <span style={{ color: 'var(--text-light)' }}>
            Todos os números desta tela se referem ao recorte selecionado.
            Atualizado agora ({safeFormatDate(cacheGeradoEm, 'HH:mm')}).
          </span>
        ) : (
          <span style={{ color: 'var(--amber)' }}>
            Não foi possível calcular os indicadores — os contadores podem estar incompletos.
          </span>
        )}
      </div>

      <Outlet />
    </div>
  );
}

export default function CoordinatorLayout() {
  return (
    <CoordinatorDataProvider>
      <Shell />
    </CoordinatorDataProvider>
  );
}