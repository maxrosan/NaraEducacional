import React, { useState, useEffect, useCallback } from 'react';
import { Helmet } from 'react-helmet-async';
import { motion, AnimatePresence } from 'framer-motion';
import {
  LayoutDashboard,
  CalendarDays,
  FileText,
  Users,
  Bell,
  BarChart2,
  Loader2,
  RefreshCw,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';
import { LogOut } from 'lucide-react';
import DashboardView from '@/components/coordinator/DashboardView';
import PlanningView from '@/components/coordinator/PlanningView';
import ReportsView from '@/components/coordinator/ReportsView';
import TeachersView from '@/components/coordinator/TeachersView';
import AlertsView from '@/components/coordinator/AlertsView';
import IndicatorView from '@/components/coordinator/IndicatorView';
import { useToast } from '@/components/ui/use-toast';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';
import { apiClient } from '@/lib/apiClient';
import { authFetch, API_BASE_URL, apiService } from '@/services/api';
import { startOfWeek, endOfWeek, startOfYear, formatISO, parseISO, format } from 'date-fns';
import { safeFormatDate } from '@/lib/dateUtils';
import NotificationsBell from '@/components/notifications/NotificationsBell';
import { PERFIS_PROFESSOR } from '@/constants/perfis';

const navItems = [
  { id: 'dashboard', label: 'Visão Geral', icon: LayoutDashboard },
  { id: 'planning', label: 'Planejamentos', icon: CalendarDays },
  { id: 'reports', label: 'Relatórios', icon: FileText },
  { id: 'teachers', label: 'Professores', icon: Users },
  { id: 'alerts', label: 'Alertas', icon: Bell },
  //{ id: 'indicators', label: 'Indicadores', icon: BarChart2, path: '/coordenacao/indicadores' },
  { id: 'indicators', label: 'Indicadores', icon: BarChart2 },
];
const activeViewStorageKey = 'coordinatorActiveView';
const coordinatorViewIds = navItems.filter(item => !item.path).map(item => item.id);

const resolveInitialView = () => {
  if (typeof window === 'undefined') return 'dashboard';
  const storedView = window.localStorage.getItem(activeViewStorageKey);
  return coordinatorViewIds.includes(storedView) ? storedView : 'dashboard';
};

function CoordinatorHomePage({ onOpenFeedbackModal }) {
  const { toast } = useToast();
  const navigate = useNavigate();
  const { user, signOut } = useAuth();

  const [activeView, setActiveView] = useState(resolveInitialView);
  const [dashboardData, setDashboardData] = useState(null);
  const [viewData, setViewData] = useState({
    planning: [],
    reports: [],
    alerts: [],
    turmas: [],
    professores: [],
    criancas: [],
  });
  const [cacheGeradoEm, setCacheGeradoEm] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshingCache, setRefreshingCache] = useState(false);
  const [refreshBloqueadoHoje, setRefreshBloqueadoHoje] = useState(false);

  const instituicaoId = user?.user_metadata?.instituicao_id ?? user?.instituicao_id ?? null;
  const refreshStorageKey = instituicaoId
    ? `coordCacheRefresh:${instituicaoId}:${format(new Date(), 'yyyy-MM-dd')}`
    : null;

  useEffect(() => {
    if (refreshStorageKey && window.localStorage.getItem(refreshStorageKey)) {
      setRefreshBloqueadoHoje(true);
    }
  }, [refreshStorageKey]);

  const handleRefreshCache = useCallback(async () => {
    if (refreshingCache || refreshBloqueadoHoje) return;
    setRefreshingCache(true);
    try {
      // O backend só enfileira (202); quem regenera é o worker do scheduler,
      // que pode levar até ~30 min. Não fazemos polling: avisamos e liberamos.
      await apiService.atualizarCacheCoordenacao();
      // Bloqueia novos cliques no dia assim que a task entra na fila.
      if (refreshStorageKey) window.localStorage.setItem(refreshStorageKey, '1');
      setRefreshBloqueadoHoje(true);
      toast({
        title: 'Atualização solicitada',
        description: 'O recálculo foi enfileirado e pode levar até 30 minutos. Recarregue a página mais tarde para ver os novos números.',
      });
    } catch (err) {
      console.error('Falha ao atualizar indicadores da coordenação:', err);
      toast({
        variant: 'destructive',
        title: 'Não foi possível atualizar',
        description: 'Tente novamente mais tarde.',
      });
    } finally {
      setRefreshingCache(false);
    }
  }, [refreshingCache, refreshBloqueadoHoje, refreshStorageKey, toast]);

  const fetchData = useCallback(async () => {
    if (!user) return;
    setLoading(true);

    try {
      const instituicao_id = user.user_metadata?.instituicao_id ?? user.instituicao_id;

      if (!instituicao_id) {
        throw new Error("ID da instituição não encontrado para o coordenador.");
      }

      const now = new Date();
      const startOfCurrentWeek = startOfWeek(now, { weekStartsOn: 1 });
      const endOfCurrentWeek = endOfWeek(now, { weekStartsOn: 1 });
      const startOfCurrentYear = startOfYear(now);

      const dataInicioSemana = format(startOfCurrentWeek, 'yyyy-MM-dd');
      const dataFimSemana = format(endOfCurrentWeek, 'yyyy-MM-dd');

      const [
        contagemSemanaRes,
        { data: turmas, error: turmasError },
        { data: planejamentos, error: planError },
        { data: relatoriosData, error: relError },
        { data: criancas, error: criancasError },
        { data: usuarios, error: usuariosError },
        cacheCoordenacao,
      ] = await Promise.all([
        authFetch(`${API_BASE_URL}/analytics/contagem-registros/?instituicao_id=${instituicao_id}&data_inicio=${dataInicioSemana}&data_fim=${dataFimSemana}`).then(r => r.json()),
        apiClient.from('turmas').select('id, nome').eq('instituicao_id', instituicao_id),
        apiClient.from('planejamentos').select('*, turmas:turma_id(nome), usuarios:id_professor(nome)').eq('instituicao_id', instituicao_id).gte('semana_referencia', formatISO(startOfCurrentWeek)).lte('semana_referencia', formatISO(endOfCurrentWeek)),
        apiClient.from('relatorios').select(`
          id,
          id_crianca,
          periodo,
          data_criacao,
          finalizado,
          revisado_por,
          criancas!inner(nome_completo, turma_id, turmas(nome))
        `).eq('instituicao_id', instituicao_id).gte('data_criacao', format(startOfCurrentYear, 'yyyy-MM-dd')),
        apiClient.from('criancas').select('id, nome_completo, turma_id').eq('instituicao_id', instituicao_id),
        apiClient.from('usuarios').select('id, nome, perfil, email, last_login, usuario_turmas!left(turma_id)').eq('instituicao_id', instituicao_id).limit(100),
        apiService.buscarCacheCoordenacao().catch((err) => {
          console.error('Cache da coordenação indisponível:', err);
          return { payload: null, gerado_em: null };
        }),
      ]);

      const errors = { turmasError, planError, relError, criancasError, usuariosError };
      const errorMessages = Object.entries(errors)
        .filter(([, error]) => error)
        .map(([key, error]) => `${key.replace('Error', '')}: ${error.message}`)
        .join('; ');

      if (errorMessages) {
        console.error("Erros de leitura na API:", errors);
        throw new Error(`Erro ao buscar dados: ${errorMessages}`);
      }

      const cachePayload = cacheCoordenacao?.payload || null;
      setCacheGeradoEm(cacheCoordenacao?.gerado_em || null);
      const bnccUsageData = cachePayload?.bncc_usage || [];

      const turmasList = turmas || [];
      const totalTurmas = turmasList.length;
      const planejamentosList = planejamentos || [];
      const criancasList = criancas || [];
      const usuariosList = usuarios || [];
      const professoresBase = usuariosList.filter(usuario => PERFIS_PROFESSOR.includes(usuario.perfil));
      const turmasById = new Map(turmasList.map(turma => [String(turma.id), turma]));
      const criancasById = new Map(criancasList.map(crianca => [String(crianca.id), crianca]));
      const usuariosById = new Map(usuariosList.map(usuario => [String(usuario.id), usuario]));
      const professores = professoresBase.map((professor) => {
        const turmasVinculadas = (professor.usuario_turmas || [])
          .map(vt => turmasById.get(String(vt.turma_id))?.nome)
          .filter(Boolean);
        return {
          ...professor,
          turmas: Array.from(new Set(turmasVinculadas)),
        };
      });
      const planejamentosFinalizados = planejamentosList.filter(p => p.dias?.some(d => d.atividades?.length > 0 || d.atividades_propostas?.length > 0)).length;

      const criancasComRegistroRecente = new Set(
        cachePayload?.criancas_com_registro_recente_15d || []
      );
      const alunosSemRegistro = criancasList.length - criancasComRegistroRecente.size;

      const relatoriosList = relatoriosData || [];
      const professorMaisRecentePorCrianca = new Map();
      Object.entries(cachePayload?.professor_mais_recente_por_crianca || {}).forEach(
        ([criancaId, info]) => {
          if (!info?.professor_id || !info?.data_observacao) return;
          professorMaisRecentePorCrianca.set(String(criancaId), {
            professorId: info.professor_id,
            data: parseISO(info.data_observacao),
          });
        }
      );
      const relatoriosEnriquecidos = relatoriosList.map((relatorio) => {
        const crianca = criancasById.get(String(relatorio.id_crianca));
        const turma = crianca?.turma_id ? turmasById.get(String(crianca.turma_id)) : null;
        const revisadoPorId = typeof relatorio.revisado_por === 'object'
          ? relatorio.revisado_por?.id
          : relatorio.revisado_por;
        const professorId = revisadoPorId || professorMaisRecentePorCrianca.get(String(relatorio.id_crianca))?.professorId;
        const professor = professorId ? usuariosById.get(String(professorId)) : null;
        return {
          ...relatorio,
          crianca_nome: crianca?.nome_completo,
          turma_nome: turma?.nome,
          turma_id: crianca?.turma_id || null,
          professor_nome: professor?.nome,
        };
      });
      const relatoriosFinalizados = relatoriosList.filter(r => r.finalizado).length;

      const alerts = [];
      const alunosSemRegistroRecente = criancasList.filter(c => !criancasComRegistroRecente.has(c.id));
      alunosSemRegistroRecente.forEach((crianca, index) => {
          alerts.push({
              id: `alert-reg-${index}`,
              icon: 'UserX',
              title: 'Criança sem registro recente',
              description: `A criança ${crianca.nome_completo} não possui registros há mais de 15 dias.`,
              teacher: 'Professor(a) responsável',
              action: 'Lembrar Professor(a)',
              type: 'registro',
              target: 'coordenador'
          });
      });

      const professoresPendentesPlanejamento = professores.filter(p => !planejamentosList.some(plan => String(plan.id_professor || plan.professora_id) === String(p.id)));
      professoresPendentesPlanejamento.forEach((prof, index) => {
          alerts.push({
              id: `alert-plan-${index}`,
              icon: 'CalendarX',
              title: 'Professor com planejamento pendente',
              description: `O(A) professor(a) ${prof.nome} ainda não finalizou o planejamento para a semana.`,
              teacher: prof.nome,
              action: 'Notificar Professor(a)',
              type: 'planejamento',
              target: 'coordenador'
          });
      });

      setDashboardData({
        weeklyObservations: contagemSemanaRes
          ? (contagemSemanaRes.analises_escrita || 0) + (contagemSemanaRes.analises_desenho || 0) + (contagemSemanaRes.registros_livres || 0) + (contagemSemanaRes.registros_observacao || 0)
          : 0,
        planningsFinished: `${planejamentosFinalizados}/${totalTurmas}`,
        studentsWithoutRecords: alunosSemRegistro,
        planningProgress: totalTurmas > 0 ? (planejamentosFinalizados / totalTurmas) * 100 : 0,
        planningPending: totalTurmas - planejamentosFinalizados,
        reportsFinished: relatoriosFinalizados,
        reportsTotal: criancasList.length,
        reportsPending: criancasList.length - relatoriosFinalizados,
        reportProgress: criancasList.length > 0 ? (relatoriosFinalizados / criancasList.length) * 100 : 0,
        bnccUsageData: bnccUsageData,
        // Indicadores pesados pré-computados no cache (D-1). IndicatorView usa
        // este bloco para evitar o fetch completo de registros_observacao.
        indicadores: cachePayload?.indicadores || null,
        turmas: turmas || [],
        planejamentos: planejamentosList,
        professores,
      });

      setViewData({
        planning: planejamentosList.map(p => ({...p, status: p.dias?.some(d => d.atividades?.length > 0 || d.atividades_propostas?.length > 0) ? 'Finalizado' : 'Pendente'})),
        reports: relatoriosEnriquecidos,
        alerts,
        turmas: turmas || [],
        professores: professores,
        criancas: criancasList,
      });

    } catch (error) {
      console.error("Error fetching coordinator data:", error);
      toast({
        variant: "destructive",
        title: "Erro ao carregar dados",
        description: error.message || "Não foi possível buscar os dados do painel. Tente novamente mais tarde.",
      });
    } finally {
      setLoading(false);
    }
  }, [user, toast]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    window.localStorage.setItem(activeViewStorageKey, activeView);
  }, [activeView]);

  const handleNavClick = (item) => {
    if (item.path) {
      navigate(item.path, { state: { dashboardData } });
    } else {
      setActiveView(item.id);
    }
  };

  const renderActiveView = () => {
    if (loading) {
      return (
        <div className="flex justify-center items-center h-96">
          <Loader2 className="h-12 w-12 animate-spin text-purple-600" />
        </div>
      );
    }
    switch (activeView) {
      case 'indicators':
        return <IndicatorView dashboardData={dashboardData} />;
      case 'dashboard':
        return <DashboardView data={dashboardData} onFeedbackClick={onOpenFeedbackModal} />;
      case 'planning':
        return <PlanningView data={viewData.planning} turmas={viewData.turmas} professores={viewData.professores} />;
      case 'reports':
        return (
          <ReportsView
            data={viewData.reports}
            turmas={viewData.turmas}
            onReportUpdated={({ id, conteudo }) => {
              // Atualização otimista: evita refetch do dashboard inteiro
              // só para refletir uma edição de relatório.
              setViewData((prev) => ({
                ...prev,
                reports: prev.reports.map((r) =>
                  String(r.id) === String(id)
                    ? { ...r, conteudo, finalizado: Boolean(conteudo && conteudo.length > 50) }
                    : r,
                ),
              }));
            }}
          />
        );
      case 'teachers':
        return <TeachersView professores={viewData.professores} turmas={viewData.turmas} />;
      case 'alerts':
        return <AlertsView data={viewData.alerts} onFeedbackClick={onOpenFeedbackModal} />;
      default:
        return <DashboardView data={dashboardData} onFeedbackClick={onOpenFeedbackModal} />;
    }
  };

  return (
    <>
      <Helmet>
        <title>NARA - Painel da Coordenação</title>
        <meta name="description" content="Painel de controle para a coordenação pedagógica." />
      </Helmet>

      <div className="bg-[#F5F3FA] min-h-screen">
        <header className="sticky top-0 bg-white/80 backdrop-blur-sm z-20 shadow-sm">
          <div className="container mx-auto px-4 sm:px-6 lg:px-8 py-4 flex items-center justify-between">
            <div className="flex items-center gap-4">
               <img  alt="NARA icon logo" className="h-12 w-auto sm:h-14" src="/nara-logo.png" />
              <div className="w-px h-8 bg-gray-200 hidden sm:block"></div>
              <span className="font-bold text-gray-800 hidden sm:block">
                {user
                  ? `${user.user_metadata?.nome ?? user.nome ?? ''} (${user.user_metadata?.perfil ?? user.perfil ?? ''})`
                  : 'Carregando...'}
              </span>
            </div>
            
            <div className="flex items-center gap-2 md:gap-4">
                <NotificationsBell />
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <span className="font-semibold text-gray-600 rounded-md px-3 py-1 cursor-pointer hover:bg-gray-100 transition-colors flex items-center gap-2">
                      <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path stroke="none" d="M0 0h24v24H0z" fill="none" /><path d="M8 7a4 4 0 1 0 8 0a4 4 0 0 0 -8 0" /><path d="M6 21v-2a4 4 0 0 1 4 -4h4a4 4 0 0 1 4 4v2" /></svg>
                      
                    </span>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    <DropdownMenuItem onClick={signOut}>
                      <LogOut className="mr-2 h-4 w-4" />
                      Sair
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
            </div>
          </div>
        </header>

        <nav className="bg-white shadow-md sticky top-[72px] md:top-[76px] z-10">
            <div className="container mx-auto px-4 sm:px-6 lg:px-8">
                <div className="flex items-center justify-between sm:justify-start space-x-0 sm:space-x-4 overflow-x-auto py-2">
                    {navItems.map(item => (
                        <Button
                            key={item.id}
                            variant="ghost"
                            onClick={() => handleNavClick(item)}
                            className={`flex-1 sm:flex-none flex items-center justify-center gap-2 px-2 sm:px-3 py-2 rounded-lg transition-colors text-xs sm:text-base ${activeView === item.id ? 'bg-[#D7CDEB] text-[#8A63D2] font-bold' : 'text-gray-600 hover:bg-gray-100'}`}
                        >
                            <item.icon className={`h-5 w-5 ${activeView === item.id ? 'text-[#8A63D2]' : 'text-gray-500'}`} />
                            <span className="whitespace-nowrap hidden sm:inline">{item.label}</span>
                        </Button>
                    ))}
                </div>
            </div>
        </nav>

        <main className="container mx-auto px-4 sm:px-6 lg:px-8 py-8">
            <div className="mb-4 text-xs flex items-center gap-2">
              <span className={`inline-block w-2 h-2 rounded-full ${cacheGeradoEm ? 'bg-emerald-500' : 'bg-amber-500'}`}></span>
              {cacheGeradoEm ? (
                <span className="text-gray-500 flex items-center gap-2 flex-wrap">
                  Indicadores de observações atualizados em{' '}
                  {safeFormatDate(cacheGeradoEm, "dd/MM/yyyy 'às' HH:mm")}
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={handleRefreshCache}
                    disabled={refreshingCache || refreshBloqueadoHoje}
                    title={refreshBloqueadoHoje ? 'Atualização já solicitada hoje' : 'A atualização pode levar até 30 minutos'}
                    className="h-6 px-2 text-[#8A63D2] hover:bg-[#D7CDEB]/40 disabled:opacity-50"
                  >
                    {refreshingCache ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <RefreshCw className="h-3.5 w-3.5" />
                    )}
                    <span className="ml-1">Atualizar</span>
                  </Button>
                  <span className="text-gray-400">
                    {refreshBloqueadoHoje
                      ? 'Atualização solicitada — pode levar até 30 min.'
                      : '(a atualização pode levar até 30 min)'}
                  </span>
                </span>
              ) : (
                <span className="text-amber-700">
                  Indicadores de observações ainda não foram gerados pelo scheduler. Os contadores podem estar incompletos.
                </span>
              )}
            </div>
            <AnimatePresence mode="wait">
                <motion.div
                    key={activeView}
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -20 }}
                    transition={{ duration: 0.3 }}
                >
                    {renderActiveView()}
                </motion.div>
            </AnimatePresence>
        </main>
      </div>
    </>
  );
}

export default CoordinatorHomePage;
