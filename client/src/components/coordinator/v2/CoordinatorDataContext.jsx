import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { apiClient } from '@/lib/apiClient';
import { authFetch, API_BASE_URL, apiService } from '@/services/api';
import { useToast } from '@/components/ui/use-toast';
import { startOfWeek, endOfWeek, formatISO, parseISO, format } from 'date-fns';
import { PERFIS_PROFESSOR } from '@/constants/perfis';

/*
 * Contexto compartilhado da nova coordenação.
 * Centraliza UMA carga de dados para todas as telas do layout (evita refetch
 * por tela).
 *
 * Tudo é recortado pelo PERÍODO AVALIATIVO selecionado — o select vive no
 * layout e vale para as 8 abas. Os agregados pesados (indicadores, BNCC,
 * ranking, alfabetização) são calculados ao vivo pelo backend a cada troca de
 * período; o snapshot D-1 pré-computado deixou de ser necessário quando a
 * janela passou a ser um bimestre em vez da história inteira da escola.
 */

const CoordinatorDataContext = createContext(null);

/*
 * Etapas da carga, na ordem em que fazem sentido para quem lê. Cada uma é uma
 * busca independente disparada em paralelo; o rótulo aparece no status
 * enquanto ela não termina, então a mensagem reflete o que de fato ainda está
 * pendente — não um roteiro fixo.
 */
const PASSOS = [
  ['registros', 'contagem de registros'],
  ['turmas', 'turmas'],
  ['planejamentos', 'planejamentos'],
  ['criancas', 'crianças'],
  ['professoras', 'professoras'],
  ['indicadores', 'indicadores do período'],
];

/** ['a', 'b', 'c'] → 'a, b e c' */
function listarEmPortugues(itens) {
  if (itens.length <= 1) return itens[0] || '';
  return `${itens.slice(0, -1).join(', ')} e ${itens[itens.length - 1]}`;
}

export function useCoordinatorData() {
  const ctx = useContext(CoordinatorDataContext);
  if (!ctx) throw new Error('useCoordinatorData precisa estar dentro de <CoordinatorDataProvider>');
  return ctx;
}

export function CoordinatorDataProvider({ children }) {
  const { user } = useAuth();
  const { toast } = useToast();

  const [dashboardData, setDashboardData] = useState(null);
  const [viewData, setViewData] = useState({
    planning: [], reports: [], alerts: [], turmas: [], professores: [], criancas: [],
  });
  const [cacheGeradoEm, setCacheGeradoEm] = useState(null);
  const [loading, setLoading] = useState(true);
  // { chave: 'pendente' | 'ok' | 'erro' } por etapa da carga.
  const [progresso, setProgresso] = useState({});

  // Recorte de tempo que dirige TODOS os números da coordenação: um período
  // avaliativo cadastrado OU um intervalo de datas escolhido à mão.
  const [periodos, setPeriodos] = useState([]);
  const [periodoId, setPeriodoId] = useState(null);
  const [intervalo, setIntervalo] = useState(null);   // { inicio, fim } em YYYY-MM-DD
  const [periodoInfo, setPeriodoInfo] = useState(null);
  const [maxDiasIntervalo, setMaxDiasIntervalo] = useState(366);

  // Carrega a lista de períodos uma vez e seleciona o vigente.
  useEffect(() => {
    if (!user) return;
    let cancelado = false;
    (async () => {
      try {
        const { periodos: lista, periodo_vigente_id, max_dias_intervalo } =
          await apiService.buscarPeriodosCoordenacao();
        if (cancelado) return;
        setPeriodos(lista || []);
        if (max_dias_intervalo) setMaxDiasIntervalo(max_dias_intervalo);
        setPeriodoId(prev => prev ?? (periodo_vigente_id || lista?.[0]?.id || null));
      } catch (err) {
        console.error('Falha ao carregar períodos avaliativos:', err);
        toast({
          variant: 'destructive',
          title: 'Não foi possível carregar os períodos',
          description: 'Os indicadores serão exibidos no período vigente.',
        });
        setPeriodos([]);
      }
    })();
    return () => { cancelado = true; };
  }, [user, toast]);

  const periodoSelecionado = periodos.find(p => p.id === periodoId) || null;

  // Trocar de período limpa o intervalo à mão, e vice-versa: os dois recortes
  // são exclusivos, e deixar os dois "ativos" na tela confunde quem lê.
  const selecionarPeriodo = useCallback((id) => {
    setIntervalo(null);
    setPeriodoId(id);
  }, []);

  const selecionarIntervalo = useCallback((inicio, fim) => {
    if (!inicio || !fim) return;
    setIntervalo({ inicio, fim });
  }, []);

  const fetchData = useCallback(async () => {
    if (!user) return;
    // Espera a lista de períodos resolver antes da primeira carga, para não
    // buscar o vigente e logo em seguida rebuscar o mesmo período.
    if (periodos.length > 0 && !periodoId) return;
    setLoading(true);
    setProgresso(Object.fromEntries(PASSOS.map(([chave]) => [chave, 'pendente'])));

    // Marca cada etapa assim que ela termina, para o status refletir o que
    // ainda falta em vez de um texto genérico.
    const rastrear = (chave, promessa) => promessa.then(
      (valor) => { setProgresso(p => ({ ...p, [chave]: 'ok' })); return valor; },
      (erro) => { setProgresso(p => ({ ...p, [chave]: 'erro' })); throw erro; },
    );

    try {
      const instituicao_id = user.user_metadata?.instituicao_id ?? user.instituicao_id;
      if (!instituicao_id) throw new Error('ID da instituição não encontrado para o coordenador.');

      // Recorte das consultas feitas aqui no front — o mesmo que vai para o
      // backend. Precedência: intervalo à mão > período avaliativo > semana
      // corrente (quando não há período cadastrado), para a tela não ficar vazia.
      const periodo = periodos.find(p => p.id === periodoId) || null;
      const now = new Date();
      let inicioRecorte;
      let fimRecorte;
      if (intervalo) {
        inicioRecorte = parseISO(intervalo.inicio);
        fimRecorte = parseISO(intervalo.fim);
      } else if (periodo) {
        inicioRecorte = parseISO(periodo.data_inicio);
        fimRecorte = parseISO(periodo.data_fim);
      } else {
        inicioRecorte = startOfWeek(now, { weekStartsOn: 1 });
        fimRecorte = endOfWeek(now, { weekStartsOn: 1 });
      }
      const dataInicio = format(inicioRecorte, 'yyyy-MM-dd');
      const dataFim = format(fimRecorte, 'yyyy-MM-dd');

      const [
        contagemSemanaRes,
        { data: turmas, error: turmasError },
        { data: planejamentos, error: planError },
        { data: criancas, error: criancasError },
        { data: usuarios, error: usuariosError },
        cacheCoordenacao,
      ] = await Promise.all([
        rastrear('registros', authFetch(`${API_BASE_URL}/analytics/contagem-registros/?instituicao_id=${instituicao_id}&data_inicio=${dataInicio}&data_fim=${dataFim}`).then(r => r.json())),
        rastrear('turmas', apiClient.from('turmas').select('id, nome').eq('instituicao_id', instituicao_id)),
        rastrear('planejamentos', apiClient.from('planejamentos').select('*, turmas:turma_id(nome), usuarios:id_professor(nome)').eq('instituicao_id', instituicao_id).gte('semana_referencia', formatISO(inicioRecorte)).lte('semana_referencia', formatISO(fimRecorte))),
        // Relatórios NÃO são mais carregados em lista aqui (lazy loading): a
        // RelatoriosPage pagina via endpoint próprio. O status/contadores por
        // criança vêm do agregado `criancas_com_relatorio_finalizado`.
        rastrear('criancas', apiClient.from('criancas').select('id, nome_completo, turma_id').eq('instituicao_id', instituicao_id)),
        rastrear('professoras', apiClient.from('usuarios').select('id, nome, perfil, email, last_login, usuario_turmas!left(turma_id)').eq('instituicao_id', instituicao_id).limit(100)),
        rastrear('indicadores', apiService.buscarCacheCoordenacao(
          intervalo
            ? { dataInicio: intervalo.inicio, dataFim: intervalo.fim }
            : { periodoId }
        )).catch((err) => {
          console.error('Indicadores da coordenação indisponíveis:', err);
          toast({
            variant: 'destructive',
            title: 'Não foi possível calcular os indicadores',
            description: err.message,
          });
          return { payload: null, gerado_em: null };
        }),
      ]);

      const errors = { turmasError, planError, criancasError, usuariosError };
      const errorMessages = Object.entries(errors)
        .filter(([, error]) => error)
        .map(([key, error]) => `${key.replace('Error', '')}: ${error.message}`)
        .join('; ');
      if (errorMessages) {
        console.error('Erros de leitura na API:', errors);
        throw new Error(`Erro ao buscar dados: ${errorMessages}`);
      }

      const cachePayload = cacheCoordenacao?.payload || null;
      setCacheGeradoEm(cacheCoordenacao?.gerado_em || null);
      setPeriodoInfo(cachePayload ? {
        id: cachePayload.periodo_id,
        descricao: cachePayload.periodo_descricao,
        dataInicio: cachePayload.periodo_data_inicio,
        dataFim: cachePayload.periodo_data_fim,
        emCurso: cachePayload.periodo_em_curso,
        personalizado: cachePayload.periodo_personalizado,
      } : null);
      const bnccUsageData = cachePayload?.bncc_usage || [];
      const bnccUsagePorTurma = cachePayload?.bncc_usage_por_turma || {};
      const engajamentoSemanal = cachePayload?.indicadores?.semanal_4s || [];

      const turmasList = turmas || [];
      const totalTurmas = turmasList.length;
      const planejamentosList = planejamentos || [];
      const criancasList = criancas || [];
      const usuariosList = usuarios || [];
      const professoresBase = usuariosList.filter(u => PERFIS_PROFESSOR.includes(u.perfil));
      const turmasById = new Map(turmasList.map(t => [String(t.id), t]));
      const criancasById = new Map(criancasList.map(c => [String(c.id), c]));
      const usuariosById = new Map(usuariosList.map(u => [String(u.id), u]));
      const professores = professoresBase.map((professor) => {
        const turmasVinculadas = (professor.usuario_turmas || [])
          .map(vt => turmasById.get(String(vt.turma_id))?.nome)
          .filter(Boolean);
        return { ...professor, turmas: Array.from(new Set(turmasVinculadas)) };
      });
      // Finalizado = TODOS os dias do plano têm atividade. O critério antigo
      // ("algum dia") chamava de finalizado um plano com 1 de 5 dias
      // preenchidos — na base, 47 dos 165 planos são parciais assim.
      const diaTemAtividade = (d) => (d?.atividades?.length > 0 || d?.atividades_propostas?.length > 0);
      // Contamos TURMAS com pelo menos um plano finalizado, não planos: o
      // denominador é o total de turmas, e num período inteiro cada turma tem
      // várias semanas de planejamento — contar planos fazia o numerador passar
      // do denominador (ex.: "21/17").
      const planejamentosFinalizadosList = planejamentosList.filter(
        p => Array.isArray(p.dias) && p.dias.length > 0 && p.dias.every(diaTemAtividade)
      );
      const planejamentosFinalizados = new Set(
        planejamentosFinalizadosList.map(p => String(p.turma_id)).filter(id => id && id !== 'null')
      ).size;

      // Evidência = qualquer registro pedagógico (marcação, relato, escrita,
      // desenho, portfólio). Antes o alerta olhava só marcação BNCC e acusava
      // como esquecidas crianças documentadas por relato de áudio.
      const criancasComRegistroRecente = new Set(
        cachePayload?.criancas_com_evidencia_recente
        || cachePayload?.criancas_com_registro_recente_15d
        || []
      );
      const alunosSemRegistro = criancasList.length - criancasComRegistroRecente.size;
      // mapa criança -> { professorNome, data } a partir do cache (para drill-downs)
      const profRecentePorCrianca = {};
      Object.entries(cachePayload?.professor_mais_recente_por_crianca || {}).forEach(([cid, info]) => {
        if (!info?.professor_id) return;
        const prof = usuariosById.get(String(info.professor_id));
        profRecentePorCrianca[String(cid)] = { nome: prof?.nome || null, data: info.data_observacao || null };
      });

      // Crianças com pelo menos um relatório finalizado (agregado do cache) —
      // substitui o carregamento completo dos relatórios para status/contadores.
      const criancasComRelatorioFinalizado = new Set(
        (cachePayload?.criancas_com_relatorio_finalizado || []).map(String)
      );
      const relatoriosFinalizados = criancasComRelatorioFinalizado.size;

      const alerts = [];
      const alunosSemRegistroRecente = criancasList.filter(c => !criancasComRegistroRecente.has(c.id));
      alunosSemRegistroRecente.forEach((crianca, index) => {
        const turma = crianca?.turma_id ? turmasById.get(String(crianca.turma_id)) : null;
        alerts.push({
          id: `alert-reg-${index}`, icon: 'UserX', kind: 'critical',
          title: 'Criança sem registro recente',
          crianca_nome: crianca.nome_completo, crianca_id: crianca.id,
          turma_nome: turma?.nome || null,
          description: `A criança ${crianca.nome_completo} não possui registros há mais de 15 dias.`,
          teacher: 'Professor(a) responsável', action: 'Lembrar Professor(a)', type: 'registro', target: 'coordenador',
        });
      });
      const professoresPendentesPlanejamento = professores.filter(p => !planejamentosList.some(plan => String(plan.id_professor || plan.professora_id) === String(p.id)));
      professoresPendentesPlanejamento.forEach((prof, index) => {
        alerts.push({
          id: `alert-plan-${index}`, icon: 'CalendarX', kind: 'warning',
          title: 'Professor com planejamento pendente',
          description: `O(A) professor(a) ${prof.nome} ainda não finalizou o planejamento para a semana.`,
          teacher: prof.nome, action: 'Notificar Professor(a)', type: 'planejamento', target: 'coordenador',
        });
      });

      setDashboardData({
        weeklyObservations: contagemSemanaRes
          ? (contagemSemanaRes.analises_escrita || 0) + (contagemSemanaRes.analises_desenho || 0) + (contagemSemanaRes.registros_livres || 0) + (contagemSemanaRes.registros_observacao || 0)
          : 0,
        // Composição do total acima. Somar marcação de chip com análise de
        // produção e relato de áudio esconde realidades pedagógicas bem
        // diferentes — a tela mostra o total E o desdobramento.
        registrosPorTipo: {
          marcacoes: contagemSemanaRes?.registros_observacao || 0,
          relatos: contagemSemanaRes?.registros_livres || 0,
          escrita: contagemSemanaRes?.analises_escrita || 0,
          desenho: contagemSemanaRes?.analises_desenho || 0,
        },
        planningsFinished: `${planejamentosFinalizados}/${totalTurmas}`,
        planningsFinishedCount: planejamentosFinalizados,
        totalTurmas,
        studentsWithoutRecords: alunosSemRegistro,
        planningProgress: totalTurmas > 0 ? (planejamentosFinalizados / totalTurmas) * 100 : 0,
        planningPending: totalTurmas - planejamentosFinalizados,
        reportsFinished: relatoriosFinalizados,
        reportsTotal: criancasList.length,
        reportsPending: criancasList.length - relatoriosFinalizados,
        reportProgress: criancasList.length > 0 ? (relatoriosFinalizados / criancasList.length) * 100 : 0,
        bnccUsageData,
        bnccUsagePorTurma,
        engajamentoSemanal,
        indicadores: cachePayload?.indicadores || null,
        alfabetizacao: cachePayload?.alfabetizacao || null,
        saudePedagogica: cachePayload?.saude_pedagogica ?? cachePayload?.indicadores?.saude_pedagogica ?? null,
        professoresCount: professoresBase.length,
        criancasRecentesIds: Array.from(criancasComRegistroRecente).map(String),
        criancasRelatorioFinalizadoIds: Array.from(criancasComRelatorioFinalizado),
        professorRecentePorCrianca: profRecentePorCrianca,
        // Heatmap "Cobertura BNCC × Turmas" (planos do período avaliativo vigente, via cache)
        planosPorTurmaCampo: cachePayload?.planos_por_turma_campo || {},
        heatmapCampos: cachePayload?.heatmap_campos || [],
        periodoDescricao: cachePayload?.periodo_descricao || null,
        planosSemHabilidadePorTurma: cachePayload?.planos_sem_habilidade_por_turma || {},
        // Ranking de produção docente no período, para o card de saúde.
        rankingProfessores: cachePayload?.ranking_professores || [],
        turmas: turmas || [],
        planejamentos: planejamentosList,
        professores,
      });

      setViewData({
        planning: planejamentosList.map(p => ({ ...p, status: p.dias?.some(d => d.atividades?.length > 0 || d.atividades_propostas?.length > 0) ? 'Finalizado' : 'Pendente' })),
        alerts,
        turmas: turmas || [],
        professores,
        criancas: criancasList,
      });
    } catch (error) {
      console.error('Error fetching coordinator data:', error);
      toast({ variant: 'destructive', title: 'Erro ao carregar dados', description: error.message || 'Não foi possível buscar os dados do painel. Tente novamente mais tarde.' });
    } finally {
      setLoading(false);
    }
  }, [user, toast, periodoId, periodos, intervalo]);

  useEffect(() => { fetchData(); }, [fetchData]);

  // Texto do que ainda está pendente. Vira null quando tudo terminou.
  const pendentes = PASSOS
    .filter(([chave]) => progresso[chave] === 'pendente')
    .map(([, rotulo]) => rotulo);
  const statusCarregamento = pendentes.length === 0
    ? null
    : pendentes.length === 1 && pendentes[0] === 'indicadores do período'
      // O agregado é o passo caro; quando é o único que falta, vale dizer que
      // está *calculando*, não "carregando" — é trabalho de servidor.
      ? 'Calculando indicadores do período…'
      : `Carregando ${listarEmPortugues(pendentes)}…`;

  const value = {
    user,
    loading,
    statusCarregamento,
    progresso,
    dashboardData,
    viewData,
    cacheGeradoEm,
    // Seleção do recorte — os controles vivem no CoordinatorLayout e valem
    // para todas as abas, porque todas leem deste mesmo contexto.
    periodos,
    periodoId,
    periodoSelecionado,
    periodoInfo,
    intervalo,
    maxDiasIntervalo,
    selecionarPeriodo,
    selecionarIntervalo,
    refetch: fetchData,
  };

  return (
    <CoordinatorDataContext.Provider value={value}>
      {children}
    </CoordinatorDataContext.Provider>
  );
}

export default CoordinatorDataContext;
