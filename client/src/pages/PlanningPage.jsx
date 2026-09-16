import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Helmet } from 'react-helmet-async';
import { useNavigate, useParams } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  ArrowLeft,
  Calendar as CalendarIcon,
  Users,
  FileText,
  Loader2,
  AlertTriangle,
  Save,
  RefreshCcw,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';
import { format, addDays, startOfWeek, parseISO } from 'date-fns';
import { safeFormatDate } from '@/lib/dateUtils';
import { ptBR } from 'date-fns/locale';
import { apiClient } from '@/lib/apiClient';
import { useAuth } from '@/contexts/AuthContext';
import { apiService } from '@/services/api';

import { Button } from '@/components/ui/button';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { Calendar } from '@/components/ui/calendar';
import { Label } from '@/components/ui/label';
import { useToast } from '@/components/ui/use-toast';
import { cn } from '@/lib/utils';
import { Card, CardContent } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { generateFamilyPlanningPdf } from '@/lib/pdfGenerator';
import DayPlanForm from '@/components/planning/DayPlanForm';
import DataDivergenteDialog from '@/components/planning/DataDivergenteDialog';
import ImportarParaSemanaAtualDialog from '@/components/planning/ImportarParaSemanaAtualDialog';
import ProfessorNavbar from '@/components/teacher/ProfessorNavBar';

const weekDays = ['segunda', 'terca', 'quarta', 'quinta', 'sexta'];
const dayNames = {
  segunda: 'Segunda-feira',
  terca: 'Terça-feira',
  quarta: 'Quarta-feira',
  quinta: 'Quinta-feira',
  sexta: 'Sexta-feira',
};

/**
 * Wrapper de TabsList que habilita scroll horizontal e mostra chevrons
 * de navegação quando há abas fora do viewport (típico em telas estreitas).
 */
function ScrollableTabsList({ children, className = '' }) {
  const scrollRef = useRef(null);
  const [canScrollLeft, setCanScrollLeft] = useState(false);
  const [canScrollRight, setCanScrollRight] = useState(false);

  const updateScrollState = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    setCanScrollLeft(el.scrollLeft > 0);
    setCanScrollRight(el.scrollLeft + el.clientWidth < el.scrollWidth - 1);
  }, []);

  useEffect(() => {
    updateScrollState();
    const el = scrollRef.current;
    if (!el) return;
    el.addEventListener('scroll', updateScrollState, { passive: true });
    window.addEventListener('resize', updateScrollState);
    return () => {
      el.removeEventListener('scroll', updateScrollState);
      window.removeEventListener('resize', updateScrollState);
    };
  }, [updateScrollState]);

  const scrollBy = (offset) => {
    scrollRef.current?.scrollBy({ left: offset, behavior: 'smooth' });
  };

  return (
    <div className="relative">
      {canScrollLeft && (
        <button
          type="button"
          aria-label="Rolar para a esquerda"
          onClick={() => scrollBy(-200)}
          className="absolute left-2 top-1/2 -translate-y-1/2 z-10 h-8 w-8 flex items-center justify-center rounded-full bg-white shadow border hover:bg-gray-50"
        >
          <ChevronLeft className="h-4 w-4 text-gray-600" />
        </button>
      )}
      <TabsList
        ref={scrollRef}
        className={cn(
          'overflow-x-auto flex-nowrap scroll-smooth',
          '[&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]',
          className
        )}
      >
        {children}
      </TabsList>
      {canScrollRight && (
        <button
          type="button"
          aria-label="Rolar para a direita"
          onClick={() => scrollBy(200)}
          className="absolute right-2 top-1/2 -translate-y-1/2 z-10 h-8 w-8 flex items-center justify-center rounded-full bg-white shadow border hover:bg-gray-50"
        >
          <ChevronRight className="h-4 w-4 text-gray-600" />
        </button>
      )}
    </div>
  );
}

function emptyDay() {
  return {
    atividades_propostas: '',
    prompt_ia: '',
    habilidades: [],
    arquivo_storage_key: null,
    arquivo_url: null,
    arquivo_nome_original: null,
    arquivo_content_type: null,
  };
}

function emptyPlanning() {
  return weekDays.reduce((acc, day) => ({ ...acc, [day]: emptyDay() }), {});
}

function emptyDayUiState() {
  return weekDays.reduce(
    (acc, day) => ({
      ...acc,
      [day]: {
        uploading: false,
        gerandoAtividades: false,
        gerandoBncc: false,
        bnccError: null,
        bnccOrigem: null,
        bnccMensagem: null,
        atividadesSugeridas: '',
      },
    }),
    {}
  );
}

function PlanningPage() {
  const navigate = useNavigate();
  const { turmaId } = useParams();
  const { user, turmaAtiva } = useAuth();
  const { toast } = useToast();

  const [date, setDate] = useState(new Date());
  const [turmas, setTurmas] = useState([]);
  const [selectedTurma, setSelectedTurma] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [planejamentoExistente, setPlanejamentoExistente] = useState(null);
  const [planningData, setPlanningData] = useState(emptyPlanning());
  const [uiByDay, setUiByDay] = useState(emptyDayUiState());
  const [dataDivergenteDialog, setDataDivergenteDialog] = useState(null);
  const [importarParaAtualDialog, setImportarParaAtualDialog] = useState(null);
  const pendingApplyRef = useRef(null);

  const weekStart = startOfWeek(date, { weekStartsOn: 1 });
  const semanaInicioFormatada = format(weekStart, 'yyyy-MM-dd');

  // Resetar UI states quando muda turma/semana.
  useEffect(() => {
    setUiByDay(emptyDayUiState());
  }, [selectedTurma?.id, semanaInicioFormatada]);

  // Buscar turmas vinculadas ao usuário
  useEffect(() => {
    const fetchTurmas = async () => {
      if (!user) return;
      setLoading(true);
      try {
        const { data, error } = await apiClient
          .from('usuario_turmas')
          .select(`turma:turmas(*)`)
          .eq('usuario_id', user.id);

        if (error) throw error;

        const dataList = Array.isArray(data) ? data : [data];
        const fetchedTurmas = dataList.map((item) => item?.turma ?? item).filter(Boolean);
        setTurmas(fetchedTurmas);

        if (fetchedTurmas.length > 0) {
          if (!turmaId) {
            const turmaAlvo = fetchedTurmas.find(t => t.id === turmaAtiva?.id) || fetchedTurmas[0];
            navigate(`/planejamento/semanal/${turmaAlvo.id}`, { replace: true });
            return;
          }
          const currentTurma = fetchedTurmas.find((t) => t.id === turmaId);
          if (currentTurma) {
            setSelectedTurma(currentTurma);
          } else {
            navigate(`/planejamento/semanal/${fetchedTurmas[0].id}`, { replace: true });
            return;
          }
        }
      } catch (error) {
        toast({
          variant: 'destructive',
          title: 'Erro ao buscar turmas',
          description: error.message,
        });
      } finally {
        setLoading(false);
      }
    };

    fetchTurmas();
  }, [user, turmaId, navigate, toast, turmaAtiva]);

  // Buscar planejamento existente quando turma ou semana mudar
  useEffect(() => {
    const buscarPlanejamentoExistente = async () => {
      if (!selectedTurma) return;

      try {
        const response = await apiService.buscarPlanejamentoSemanal(
          selectedTurma.id,
          semanaInicioFormatada
        );

        const novo = emptyPlanning();
        if (response.encontrado) {
          setPlanejamentoExistente(response.planejamento);
          Object.keys(response.planejamento.dias || {}).forEach((dia) => {
            const d = response.planejamento.dias[dia] || {};
            novo[dia] = {
              atividades_propostas: d.atividades_propostas || '',
              prompt_ia: d.prompt_ia || '',
              arquivo_storage_key: d.arquivo_storage_key || null,
              arquivo_url: d.arquivo_url || null,
              arquivo_nome_original: d.arquivo_nome_original || null,
              arquivo_content_type: d.arquivo_content_type || null,
              habilidades: Array.isArray(d.habilidades) ? d.habilidades : [],
            };
          });
        } else {
          setPlanejamentoExistente(null);
        }

        // Aplica upload pendente da semana (vindo do diálogo de ajuste,
        // quando o arquivo cobre uma semana diferente da que estava na tela).
        const pending = pendingApplyRef.current;
        if (pending && pending.semanaAlvo === semanaInicioFormatada) {
          const { diasParaAplicar = [], arquivoMeta } = pending;
          for (const item of diasParaAplicar) {
            if (!item?.dia_semana || !weekDays.includes(item.dia_semana)) continue;
            novo[item.dia_semana] = {
              ...novo[item.dia_semana],
              atividades_propostas: item.atividades || '',
              arquivo_storage_key: arquivoMeta?.storage_key || null,
              arquivo_url: arquivoMeta?.arquivo_url || null,
              arquivo_nome_original: arquivoMeta?.arquivo_nome_original || null,
              arquivo_content_type: arquivoMeta?.arquivo_content_type || null,
            };
          }
          pendingApplyRef.current = null;
          if (diasParaAplicar.length > 0) {
            toast({
              title: '📄 Arquivo aplicado na semana detectada',
              description: `${diasParaAplicar.length} ${diasParaAplicar.length === 1 ? 'dia preenchido' : 'dias preenchidos'
                } a partir do arquivo enviado.`,
            });
          }
        }

        setPlanningData(novo);
      } catch (error) {
        console.error('Erro ao buscar planejamento:', error);
      }
    };

    buscarPlanejamentoExistente();
  }, [selectedTurma?.id, semanaInicioFormatada, toast]);

  const handleTurmaChange = (newTurmaId) => {
    navigate(`/planejamento/semanal/${newTurmaId}`);
  };

  useEffect(() => {
    if (!turmaId || turmas.length === 0) return;
    if (turmaAtiva?.id && turmaAtiva.id !== turmaId) {
      handleTurmaChange(turmaAtiva.id);
    }
  }, [turmaAtiva?.id, turmaId, turmas]);

  const handleDataChange = (day, field, value) => {
    setPlanningData((prev) => ({
      ...prev,
      [day]: { ...prev[day], [field]: value },
    }));
  };

  const setDayUi = useCallback((day, patch) => {
    setUiByDay((prev) => ({
      ...prev,
      [day]: { ...prev[day], ...patch },
    }));
  }, []);

  // ---- Upload de arquivo --------------------------------------------------

  /**
   * Agrupa os itens `{data, dia_semana, atividades}` por semana
   * (segunda-feira) → Map<"yyyy-MM-dd", item[]>.
   */
  const agruparPorSemana = (atividadesPorDia) => {
    const mapa = new Map();
    for (const item of atividadesPorDia || []) {
      if (!item?.data) continue;
      let dataObj;
      try {
        dataObj = parseISO(item.data);
      } catch {
        continue;
      }
      if (!dataObj || Number.isNaN(dataObj.getTime())) continue;
      const inicioSemana = startOfWeek(dataObj, { weekStartsOn: 1 });
      const chave = format(inicioSemana, 'yyyy-MM-dd');
      if (!mapa.has(chave)) {
        mapa.set(chave, []);
      }
      mapa.get(chave).push(item);
    }
    return mapa;
  };

  /** Aplica os itens de uma semana no `planningData` (sobrescreve sem perguntar). */
  const aplicarDiasNaSemanaAtual = useCallback(
    (diasDaSemana, arquivoMeta, fallbackFile = null) => {
      setPlanningData((prev) => {
        const novo = { ...prev };
        for (const item of diasDaSemana || []) {
          const dia = item.dia_semana;
          if (!weekDays.includes(dia)) continue;
          novo[dia] = {
            ...novo[dia],
            atividades_propostas: item.atividades || '',
            arquivo_storage_key: arquivoMeta?.storage_key || null,
            arquivo_url: arquivoMeta?.arquivo_url || null,
            arquivo_nome_original:
              arquivoMeta?.arquivo_nome_original || fallbackFile?.name || null,
            arquivo_content_type:
              arquivoMeta?.arquivo_content_type || fallbackFile?.type || null,
          };
        }
        return novo;
      });
    },
    []
  );

  /** Salva server-side as semanas que NÃO são a atual via aplicar-em-semanas. */
  const salvarSemanasExtras = useCallback(
    async (semanasExtras, arquivoMeta) => {
      if (!selectedTurma || semanasExtras.length === 0) return;
      const semanasPayload = semanasExtras.map(([semanaInicio, dias]) => ({
        semana_inicio: semanaInicio,
        dias: dias.reduce((acc, item) => {
          acc[item.dia_semana] = { atividades_propostas: item.atividades || '' };
          return acc;
        }, {}),
      }));
      await apiService.aplicarPlanejamentoEmSemanas({
        turma_id: selectedTurma.id,
        professora_id: user?.id,
        professora_nome: user?.user_metadata?.full_name || user?.email,
        arquivo: arquivoMeta?.storage_key
          ? {
            storage_key: arquivoMeta.storage_key,
            arquivo_nome_original: arquivoMeta.arquivo_nome_original || null,
            arquivo_content_type: arquivoMeta.arquivo_content_type || null,
          }
          : null,
        semanas: semanasPayload,
      });
    },
    [selectedTurma, user]
  );

  const handleUploadFile = useCallback(
    async (day, file) => {
      if (!selectedTurma) {
        toast({
          variant: 'destructive',
          title: 'Selecione uma turma',
          description: 'Selecione uma turma antes de anexar arquivos.',
        });
        return;
      }
      setDayUi(day, { uploading: true });
      try {
        const result = await apiService.processarArquivoPlanejamento(
          selectedTurma.id,
          day,
          file
        );

        const arquivoMeta = {
          storage_key: result.storage_key || null,
          arquivo_url: result.arquivo_url || null,
          arquivo_nome_original: result.arquivo_nome_original || file.name,
          arquivo_content_type: result.arquivo_content_type || file.type,
        };

        const dias = Array.isArray(result.atividades_por_dia)
          ? result.atividades_por_dia
          : [];

        // Fallback: IA não conseguiu separar por dia. Comportamento antigo:
        // mostra a sugestão pendente no dia clicado.
        if (dias.length === 0) {
          setPlanningData((prev) => ({
            ...prev,
            [day]: {
              ...prev[day],
              arquivo_storage_key: arquivoMeta.storage_key,
              arquivo_url: arquivoMeta.arquivo_url,
              arquivo_nome_original: arquivoMeta.arquivo_nome_original,
              arquivo_content_type: arquivoMeta.arquivo_content_type,
            },
          }));
          if (result.atividades_sugeridas) {
            setDayUi(day, { atividadesSugeridas: result.atividades_sugeridas });
            toast({
              title: '📄 Arquivo processado',
              description:
                'Não foi possível separar por dia. Revise e aplique a sugestão no dia desejado.',
            });
          }
          return;
        }

        const porSemana = agruparPorSemana(dias);

        if (porSemana.has(semanaInicioFormatada)) {
          // Caso bom: a semana atual está coberta. Aplica direto e auto-salva
          // o que sobrar.
          const diasDaSemana = porSemana.get(semanaInicioFormatada);
          aplicarDiasNaSemanaAtual(diasDaSemana, arquivoMeta, file);

          const extras = [...porSemana.entries()].filter(
            ([k]) => k !== semanaInicioFormatada
          );
          if (extras.length > 0) {
            try {
              await salvarSemanasExtras(extras, arquivoMeta);
              const lista = extras
                .map(([k]) =>
                  `${format(parseISO(k), 'dd/MM', { locale: ptBR })} a ${format(
                    addDays(parseISO(k), 4),
                    'dd/MM',
                    { locale: ptBR }
                  )}`
                )
                .join(', ');
              toast({
                title: '📄 Atividades aplicadas',
                description: `${diasDaSemana.length} dia(s) preenchidos nesta semana. Outras semanas salvas: ${lista}.`,
              });
            } catch (error) {
              toast({
                variant: 'destructive',
                title: 'Atividades aplicadas, mas falha ao salvar outras semanas',
                description: error.message || 'Tente reenviar o arquivo.',
              });
            }
          } else {
            toast({
              title: '📄 Atividades aplicadas',
              description: `${diasDaSemana.length} dia(s) preenchidos a partir do arquivo.`,
            });
          }
          return;
        }

        // Nenhuma data bate com a semana atual: dialog para a professora decidir.
        const semanasOrdenadas = [...porSemana.keys()]
          .map((k) => parseISO(k))
          .sort((a, b) => a.getTime() - b.getTime());
        setDataDivergenteDialog({
          day,
          file,
          arquivoMeta,
          porSemana,
          semanasDetectadasInicio: semanasOrdenadas,
          evidencia: result.data_detectada?.evidencia || '',
        });
      } catch (error) {
        toast({
          variant: 'destructive',
          title: 'Erro ao processar arquivo',
          description: error.message || 'Não foi possível ler o arquivo enviado.',
        });
      } finally {
        setDayUi(day, { uploading: false });
      }
    },
    [
      selectedTurma,
      semanaInicioFormatada,
      setDayUi,
      toast,
      aplicarDiasNaSemanaAtual,
      salvarSemanasExtras,
    ]
  );

  const handleDataDivergenteManter = useCallback(() => {
    if (!dataDivergenteDialog) {
      setDataDivergenteDialog(null);
      return;
    }
    const { porSemana, arquivoMeta, file, semanasDetectadasInicio } =
      dataDivergenteDialog;
    setDataDivergenteDialog(null);
    setImportarParaAtualDialog({
      porSemana,
      arquivoMeta,
      file,
      semanasDoArquivo: semanasDetectadasInicio,
    });
  }, [dataDivergenteDialog]);

  const handleImportarParaSemanaAtual = useCallback(() => {
    if (!importarParaAtualDialog) return;
    const { porSemana, arquivoMeta, file, semanasDoArquivo } =
      importarParaAtualDialog;

    // Pega só os dias da PRIMEIRA semana detectada (5 dias úteis).
    const primeiraSemana = [...semanasDoArquivo].sort(
      (a, b) => a.getTime() - b.getTime()
    )[0];
    const primeiraSemanaFmt = format(primeiraSemana, 'yyyy-MM-dd');
    const diasOrigem = porSemana.get(primeiraSemanaFmt) || [];

    // Mapeia cada dia para a data correspondente da semana atual,
    // preservando o dia_semana.
    const diasMapeados = diasOrigem
      .filter((item) => weekDays.includes(item.dia_semana))
      .map((item) => {
        const offset = weekDays.indexOf(item.dia_semana);
        const novaData = format(addDays(weekStart, offset), 'yyyy-MM-dd');
        return { ...item, data: novaData };
      });

    if (diasMapeados.length === 0) {
      toast({
        title: 'Nada para importar',
        description: 'O arquivo não tinha dias úteis para a semana atual.',
      });
      setImportarParaAtualDialog(null);
      return;
    }

    aplicarDiasNaSemanaAtual(diasMapeados, arquivoMeta, file);
    toast({
      title: '📄 Atividades importadas',
      description: `${diasMapeados.length} dia(s) preenchidos na semana atual a partir do arquivo.`,
    });
    setImportarParaAtualDialog(null);
  }, [importarParaAtualDialog, weekStart, aplicarDiasNaSemanaAtual, toast]);

  const handleDescartarImportar = useCallback(() => {
    setImportarParaAtualDialog(null);
    toast({
      title: 'Arquivo descartado',
      description: 'A semana selecionada foi mantida. Nenhum dia foi preenchido.',
    });
  }, [toast]);

  const handleDataDivergenteAjustar = useCallback(async () => {
    if (!dataDivergenteDialog) return;
    const { porSemana, arquivoMeta, semanasDetectadasInicio } = dataDivergenteDialog;
    const primeiraSemana = semanasDetectadasInicio[0];
    const primeiraSemanaFmt = format(primeiraSemana, 'yyyy-MM-dd');
    const diasPrimeiraSemana = porSemana.get(primeiraSemanaFmt) || [];

    // Primeiro: salva server-side TODAS as semanas detectadas (assim, mesmo
    // a "primeira" já existe quando o useEffect recarregar a turma + semana).
    try {
      await salvarSemanasExtras([...porSemana.entries()], arquivoMeta);
    } catch (error) {
      toast({
        variant: 'destructive',
        title: 'Falha ao salvar semanas detectadas',
        description: error.message || 'Tente reenviar o arquivo.',
      });
      return;
    }

    // Marca a primeira semana como "pendente de aplicação visual" para que
    // o useEffect popule a tela ao recarregar.
    pendingApplyRef.current = {
      semanaAlvo: primeiraSemanaFmt,
      diasParaAplicar: diasPrimeiraSemana,
      arquivoMeta,
    };
    setDate(primeiraSemana);
    setDataDivergenteDialog(null);
  }, [dataDivergenteDialog, salvarSemanasExtras, toast]);

  const handleRemoverArquivo = (day) => {
    setPlanningData((prev) => ({
      ...prev,
      [day]: {
        ...prev[day],
        arquivo_storage_key: null,
        arquivo_url: null,
        arquivo_nome_original: null,
        arquivo_content_type: null,
      },
    }));
  };

  // ---- Assistente de IA: sugerir atividades ------------------------------
  const handleSugerirAtividades = useCallback(
    async (day, prompt) => {
      setDayUi(day, { gerandoAtividades: true, atividadesSugeridas: '' });
      try {
        const contextoTurma = selectedTurma?.nome ? `Turma: ${selectedTurma.nome}` : '';
        const result = await apiService.sugerirAtividadesPlanejamento({
          prompt,
          ano_serie: selectedTurma?.faixa_etaria || '',
          contexto: contextoTurma,
        });
        setDayUi(day, { atividadesSugeridas: result.atividades_sugeridas || '' });
      } catch (error) {
        toast({
          variant: 'destructive',
          title: 'Não foi possível gerar atividades',
          description: error.message || 'Tente novamente em instantes.',
        });
      } finally {
        setDayUi(day, { gerandoAtividades: false });
      }
    },
    [selectedTurma, setDayUi, toast]
  );

  const handleAplicarAtividadesSugeridas = (day, modo) => {
    const sugestao = uiByDay[day]?.atividadesSugeridas || '';
    if (!sugestao) return;
    setPlanningData((prev) => {
      const atual = prev[day]?.atividades_propostas || '';
      const novo =
        modo === 'anexar' && atual
          ? `${atual.trimEnd()}\n\n${sugestao}`
          : sugestao;
      return { ...prev, [day]: { ...prev[day], atividades_propostas: novo } };
    });
    setDayUi(day, { atividadesSugeridas: '' });
  };

  // ---- Sugerir BNCC ------------------------------------------------------
  const handleSugerirBncc = useCallback(
    async (day) => {
      const atividades = planningData[day]?.atividades_propostas || '';
      if (atividades.trim().length < 10) {
        setDayUi(day, {
          bnccError: 'Preencha as Atividades Propostas antes de gerar a BNCC.',
        });
        return;
      }
      setDayUi(day, {
        gerandoBncc: true,
        bnccError: null,
        bnccMensagem: null,
        bnccOrigem: null,
      });
      try {
        const result = await apiService.sugerirBnccPlanejamento({
          atividades_texto: atividades,
          ano_serie: selectedTurma?.faixa_etaria || '',
          limite: 6,
        });
        setPlanningData((prev) => ({
          ...prev,
          [day]: { ...prev[day], habilidades: result.habilidades || [] },
        }));
        setDayUi(day, {
          bnccOrigem: result.origem || null,
          bnccMensagem: result.mensagem || null,
        });
      } catch (error) {
        setDayUi(day, {
          bnccError: error.message || 'Erro ao gerar habilidades BNCC.',
        });
      } finally {
        setDayUi(day, { gerandoBncc: false });
      }
    },
    [planningData, selectedTurma, setDayUi]
  );

  // ---- Salvar -----------------------------------------------------------
  const handleSave = async () => {
    if (!selectedTurma || !user) {
      toast({
        variant: 'destructive',
        title: 'Erro',
        description: 'Selecione uma turma antes de salvar.',
      });
      return;
    }

    setSaving(true);
    try {
      // Payload: cada dia com os 4 campos + chips de habilidades como códigos.
      const diasPayload = weekDays.reduce((acc, day) => {
        const d = planningData[day] || emptyDay();
        acc[day] = {
          atividades_propostas: d.atividades_propostas || '',
          prompt_ia: d.prompt_ia || '',
          arquivo_storage_key: d.arquivo_storage_key || null,
          arquivo_nome_original: d.arquivo_nome_original || null,
          arquivo_content_type: d.arquivo_content_type || null,
          habilidades: (d.habilidades || []).map((h) => h.codigo).filter(Boolean),
        };
        return acc;
      }, {});

      const dadosPlanejamento = {
        turma_id: selectedTurma.id,
        semana_inicio: semanaInicioFormatada,
        professora_id: user.id,
        professora_nome: user.user_metadata?.full_name || user.email,
        dias: diasPayload,
      };

      let response;
      if (planejamentoExistente) {
        response = await apiService.atualizarPlanejamentoSemanal(
          planejamentoExistente.id,
          { dias: diasPayload }
        );
      } else {
        response = await apiService.criarPlanejamentoSemanal(dadosPlanejamento);
      }

      if (response.success) {
        toast({
          title: '✅ Planejamento salvo!',
          description: 'Suas alterações foram salvas com sucesso.',
          className: 'bg-green-100 border-green-300 text-green-800',
        });

        // Recarregar para refletir novos arquivo_url presigned + ids das habilidades.
        const dadosAtualizados = await apiService.buscarPlanejamentoSemanal(
          selectedTurma.id,
          semanaInicioFormatada
        );
        if (dadosAtualizados.encontrado) {
          setPlanejamentoExistente(dadosAtualizados.planejamento);
          const novo = emptyPlanning();
          Object.keys(dadosAtualizados.planejamento.dias || {}).forEach((dia) => {
            const d = dadosAtualizados.planejamento.dias[dia] || {};
            novo[dia] = {
              atividades_propostas: d.atividades_propostas || '',
              prompt_ia: d.prompt_ia || '',
              arquivo_storage_key: d.arquivo_storage_key || null,
              arquivo_url: d.arquivo_url || null,
              arquivo_nome_original: d.arquivo_nome_original || null,
              arquivo_content_type: d.arquivo_content_type || null,
              habilidades: Array.isArray(d.habilidades) ? d.habilidades : [],
            };
          });
          setPlanningData(novo);
        }
      }
    } catch (error) {
      console.error('Erro ao salvar planejamento:', error);
      toast({
        variant: 'destructive',
        title: 'Erro ao salvar',
        description: error.message || 'Ocorreu um erro ao salvar o planejamento.',
      });
    } finally {
      setSaving(false);
    }
  };

  const handleGeneratePdf = (type) => {
    toast({
      title: `📥 Gerando PDF para ${type}...`,
      description: 'Seu arquivo estará pronto em instantes.',
    });

    const weekEnd = addDays(weekStart, 4);
    const sameMonth = format(weekStart, 'MM') === format(weekEnd, 'MM');
    const sameYear = format(weekStart, 'yyyy') === format(weekEnd, 'yyyy');
    const weekPeriodLabel =
      sameMonth && sameYear
        ? `${format(weekStart, 'dd', { locale: ptBR })} a ${format(weekEnd, "dd 'de' LLLL", { locale: ptBR })}`
        : `${format(weekStart, "dd 'de' LLLL", { locale: ptBR })} a ${format(weekEnd, "dd 'de' LLLL", { locale: ptBR })}`;

    const reportData = {
      turmaName: selectedTurma?.nome || 'Turma não selecionada',
      weekPeriod: weekPeriodLabel,
      dailyPlans: weekDays.map((day) => ({
        day: dayNames[day],
        date: format(addDays(weekStart, weekDays.indexOf(day)), 'dd/MM/yyyy'),
        activities: planningData[day].atividades_propostas || '',
        skills: (planningData[day].habilidades || []).map((h) => ({
          codigo: h.codigo,
          descricao: h.descricao || '',
        })),
      })),
    };

    if (type === 'família') {
      generateFamilyPlanningPdf(reportData);
    } else {
      toast({
        title: '🚧 PDF para Coordenação em breve!',
        description: 'Esta funcionalidade será implementada em breve.',
      });
    }
  };

  const renderContent = () => {
    if (loading) {
      return (
        <div className="flex items-center justify-center h-64">
          <Loader2 className="h-8 w-8 text-roxo-principal animate-spin" />
          <p className="ml-4 text-texto-medio">Carregando dados...</p>
        </div>
      );
    }

    if (turmas.length === 0) {
      return (
        <Card className="mt-6 border-dashed border-gray-300 bg-gray-50 text-center shadow-none">
          <CardContent className="p-8">
            <AlertTriangle className="mx-auto h-12 w-12 text-yellow-500" />
            <h3 className="mt-4 text-lg font-semibold text-gray-800">Nenhuma turma vinculada</h3>
            <p className="mt-2 text-sm text-gray-600">
              Você ainda não tem nenhuma turma vinculada. Aguarde o administrador configurar
              sua turma para começar a planejar.
            </p>
          </CardContent>
        </Card>
      );
    }

    if (!selectedTurma) {
      return (
        <Card className="mt-6 border-dashed border-gray-300 bg-gray-50 text-center shadow-none">
          <CardContent className="p-8">
            <Users className="mx-auto h-12 w-12 text-roxo-principal" />
            <h3 className="mt-4 text-lg font-semibold text-gray-800">Selecione uma turma</h3>
            <p className="mt-2 text-sm text-gray-600">
              Por favor, selecione uma turma no menu acima para começar o planejamento.
            </p>
          </CardContent>
        </Card>
      );
    }

    return (
      <>
        <Card className="border-none shadow-lg">
          <CardContent className="p-0">
            <Tabs defaultValue="segunda" className="w-full">
              <ScrollableTabsList className="px-6">
                {weekDays.map((day) => (
                  <TabsTrigger key={day} value={day} className="capitalize">
                    {dayNames[day]}
                  </TabsTrigger>
                ))}
              </ScrollableTabsList>
              <div className="p-6 bg-white rounded-b-2xl">
                {weekDays.map((day) => (
                  <TabsContent key={day} value={day}>
                    <DayPlanForm
                      day={day}
                      dayName={dayNames[day]}
                      date={format(addDays(weekStart, weekDays.indexOf(day)), 'dd/MM/yyyy')}
                      data={planningData[day]}
                      onDataChange={(field, value) => handleDataChange(day, field, value)}
                      onUploadFile={(file) => handleUploadFile(day, file)}
                      onSugerirAtividades={(prompt) => handleSugerirAtividades(day, prompt)}
                      onSugerirBncc={() => handleSugerirBncc(day)}
                      onRemoverArquivo={() => handleRemoverArquivo(day)}
                      onAplicarAtividadesSugeridas={(modo) =>
                        handleAplicarAtividadesSugeridas(day, modo)
                      }
                      uploading={uiByDay[day]?.uploading || false}
                      gerandoAtividades={uiByDay[day]?.gerandoAtividades || false}
                      gerandoBncc={uiByDay[day]?.gerandoBncc || false}
                      bnccError={uiByDay[day]?.bnccError || null}
                      bnccOrigem={uiByDay[day]?.bnccOrigem || null}
                      bnccMensagem={uiByDay[day]?.bnccMensagem || null}
                      atividadesSugeridas={uiByDay[day]?.atividadesSugeridas || ''}
                    />
                  </TabsContent>
                ))}
              </div>
            </Tabs>
          </CardContent>
        </Card>

        <div className="mt-8 flex flex-col sm:flex-row justify-between items-center gap-4">
          <div className="flex items-center gap-2 text-sm text-gray-600">
            {planejamentoExistente && (
              <>
                <RefreshCcw className="h-4 w-4" />
                Última atualização:{' '}
                {safeFormatDate(planejamentoExistente.data_modificacao, 'dd/MM/yyyy HH:mm')}
              </>
            )}
          </div>

          <div className="flex flex-col sm:flex-row gap-4">
            <Button
              size="lg"
              variant="outline"
              className="bg-white"
              onClick={() => handleGeneratePdf('família')}
            >
              <FileText className="h-4 w-4 mr-2" /> PDF para Família
            </Button>
            <Button
              size="lg"
              className="bg-verde-menta text-texto-escuro hover:bg-opacity-80 btn-hover"
              onClick={handleSave}
              disabled={saving}
            >
              {saving ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  <span>Salvando...</span>
                </>
              ) : (
                <>
                  <Save className="h-4 w-4 mr-2" />
                  <span>
                    {planejamentoExistente ? 'Atualizar Planejamento' : 'Salvar Planejamento'}
                  </span>
                </>
              )}
            </Button>
          </div>
        </div>
      </>
    );
  };

  return (
    <>
      <Helmet>
        <title>NARA - Planejamento Semanal</title>
        <meta name="description" content="Crie e gerencie o planejamento semanal da sua turma." />
      </Helmet>

      <div className="bg-lavanda-claro min-h-screen">
        <ProfessorNavbar />

        <div className="bg-white border-b shadow-sm">
          <div className="container mx-auto px-4 sm:px-6 lg:px-8 py-3 flex items-center justify-between">
            <Button variant="ghost" size="icon" onClick={() => navigate('/home-professor')}>
              <ArrowLeft className="h-6 w-6 text-texto-medio" />
            </Button>
            <h1 className="text-md font-bold text-texto-escuro">Planejamento</h1>
            {/* <img alt="NARA icon logo" className="h-12 w-auto sm:h-14" src="/nara-logo.png" /> */}
          </div>
        </div>

        <main className="container mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
          >
            <Card className="mb-6 border-none shadow-lg">
              <CardContent className="p-6">
                <div className="grid grid-cols-1 gap-4 items-end">
                  <div className="space-y-1">
                    <Label className="font-semibold text-gray-700 flex items-center gap-2">
                      <CalendarIcon className="h-4 w-4" /> Semana
                    </Label>
                    <Popover>
                      <PopoverTrigger asChild>
                        <Button
                          variant={'outline'}
                          className={cn(
                            'w-full justify-start text-left font-normal',
                            !date && 'text-muted-foreground'
                          )}
                          disabled={!selectedTurma}
                        >
                          <CalendarIcon className="mr-2 h-4 w-4" />
                          {date ? (
                            `${format(weekStart, 'dd/MM')} - ${format(addDays(weekStart, 4), 'dd/MM/yyyy')}`
                          ) : (
                            <span>Escolha uma data</span>
                          )}
                        </Button>
                      </PopoverTrigger>
                      <PopoverContent className="w-auto p-0">
                        <Calendar
                          mode="single"
                          selected={date}
                          onSelect={setDate}
                          initialFocus
                          locale={ptBR}
                        />
                      </PopoverContent>
                    </Popover>
                  </div>
                </div>
              </CardContent>
            </Card>

            {renderContent()}
          </motion.div>
        </main>
      </div>

      <DataDivergenteDialog
        open={Boolean(dataDivergenteDialog)}
        semanaSelecionadaInicio={weekStart}
        semanasDetectadasInicio={dataDivergenteDialog?.semanasDetectadasInicio || []}
        evidencia={dataDivergenteDialog?.evidencia}
        onManter={handleDataDivergenteManter}
        onAjustar={handleDataDivergenteAjustar}
      />

      <ImportarParaSemanaAtualDialog
        open={Boolean(importarParaAtualDialog)}
        semanaSelecionadaInicio={weekStart}
        semanasDoArquivo={importarParaAtualDialog?.semanasDoArquivo || []}
        onImportar={handleImportarParaSemanaAtual}
        onDescartar={handleDescartarImportar}
      />
    </>
  );
}

export default PlanningPage;