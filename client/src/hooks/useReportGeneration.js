import { useState, useEffect } from 'react';
import { useToast } from '@/components/ui/use-toast';
import { gerarRelatorioPorCrianca, salvarRelatorio } from '@/services/api';
import { apiClient } from '@/lib/apiClient';
import { format } from 'date-fns';
import { ptBR } from 'date-fns/locale';

/**
 * Hook para gerenciar o fluxo completo de geração de relatórios
 */
export function useReportGeneration(studentId, studentName, onReportSaved, currentPeriodLabel = null) {
  const [isEditorOpen, setIsEditorOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [loadingStep, setLoadingStep] = useState('collecting');
  const [generatedReport, setGeneratedReport] = useState(null);
  const [existingReports, setExistingReports] = useState([]);
  const [currentPeriodReport, setCurrentPeriodReport] = useState(null);
  const { toast } = useToast();

  const dedupeReportsByPeriod = (reports) => {
    const reportMap = new Map();
    reports.forEach((report) => {
      if (!report?.periodo) return;
      const existing = reportMap.get(report.periodo);
      if (!existing || new Date(report.data_criacao) > new Date(existing.data_criacao)) {
        reportMap.set(report.periodo, report);
      }
    });
    return Array.from(reportMap.values()).sort(
      (a, b) => new Date(b.data_criacao) - new Date(a.data_criacao)
    );
  };

  const fetchExistingReports = async () => {
    if (!studentId) return;
    try {
      const { data, error } = await apiClient
        .from('relatorios')
        .select('id, periodo, data_criacao, pdf_url')
        .eq('id_crianca', studentId)
        .order('data_criacao', { ascending: false });

      if (!error && data) {
        const dedupedReports = dedupeReportsByPeriod(data);
        setExistingReports(dedupedReports);
        if (currentPeriodLabel) {
          const reportForPeriod = dedupedReports.find(r => r.periodo === currentPeriodLabel) || null;
          setCurrentPeriodReport(reportForPeriod);
        }
      }
    } catch (err) {
      console.error('Erro ao buscar relatórios existentes:', err);
    }
  };

  useEffect(() => {
    fetchExistingReports();
  }, [studentId, currentPeriodLabel]);

  const closeEditor = () => {
    setIsEditorOpen(false);
    setGeneratedReport(null);
  };

  /**
   * Simula o processamento de geração de relatório com steps
   */
  const simulateReportGeneration = async () => {
    const steps = ['collecting', 'analyzing', 'generating', 'finalizing'];
    const delays = [3000, 5000, 4000, 2000];

    for (let i = 0; i < steps.length; i++) {
      setLoadingStep(steps[i]);
      await new Promise(resolve => setTimeout(resolve, delays[i]));
    }
  };

  /**
   * Formata a label do período para salvamento
   */
  const formatPeriodLabel = (periodData) => {
    if (periodData.descricao) return periodData.descricao;
    const startFormatted = periodData.startDate instanceof Date
      ? format(periodData.startDate, 'dd/MM/yyyy', { locale: ptBR })
      : periodData.startDate;
    const endFormatted = periodData.endDate instanceof Date
      ? format(periodData.endDate, 'dd/MM/yyyy', { locale: ptBR })
      : periodData.endDate;
    return `${startFormatted} - ${endFormatted}`;
  };

  /**
   * Inicia o processo de geração de relatório
   * @param {Object} periodoAvaliativo - Objeto do período avaliativo selecionado { id, descricao, data_inicio, data_fim }
   */
  const handleGenerateReport = async (periodoAvaliativo) => {
    setLoading(true);

    try {
      await simulateReportGeneration();

      const relatorioGerado = await gerarRelatorioPorCrianca(studentId, periodoAvaliativo.id);

      const reportWithPeriod = {
        ...relatorioGerado,
        period: periodoAvaliativo,
      };

      setGeneratedReport(reportWithPeriod);
      setIsEditorOpen(true);

      toast({
        title: 'Relatório gerado com sucesso!',
        description: 'O relatório foi criado usando IA baseada nos dados do estudante.',
      });

    } catch (error) {
      console.error('Erro ao gerar relatório:', error);

      toast({
        variant: 'destructive',
        title: 'Erro ao gerar relatório',
        description: error.message || 'Não foi possível gerar o relatório. Tente novamente.',
      });
    } finally {
      setLoading(false);
    }
  };

  /**
   * Salva o relatório editado
   */
  const handleSaveReport = async (reportData, { keepOpen = false } = {}) => {
    try {
      const { apiClient } = await import('@/lib/apiClient');
      const { data: instData, error: instError } = await apiClient
        .from('instituicoes')
        .select('id')
        .limit(1)
        .single();

      if (instError) {
        console.warn('Erro ao buscar instituição, salvando sem instituicao_id:', instError);
      }

      const dadosParaSalvar = {
        id_crianca: studentId,
        periodo: reportData.period ? formatPeriodLabel(reportData.period) : 'Período não especificado',
        conteudo: reportData.content,
        instituicao_id: instData?.id || null,
      };

      const resultado = await salvarRelatorio(dadosParaSalvar);
      const relatorio = resultado?.already_exists ? resultado.relatorio : resultado;

      if (resultado?.already_exists) {
        toast({
          title: 'Relatório já existente',
          description: 'Este período já possui um relatório. Exibindo o registro disponível.',
        });
      } else {
        toast({
          title: 'Relatório salvo!',
          description: 'O relatório foi salvo com sucesso no sistema.',
        });
      }

      await fetchExistingReports();

      if (onReportSaved) {
        onReportSaved();
      }

      if (!keepOpen) {
        closeEditor();
      }

      return relatorio;

    } catch (error) {
      console.error('Erro ao salvar relatório:', error);
      toast({
        variant: 'destructive',
        title: 'Erro ao salvar',
        description: 'Não foi possível salvar o relatório. Tente novamente.',
      });
      throw error;
    }
  };

  return {
    // Estados
    isEditorOpen,
    loading,
    loadingStep,
    generatedReport,
    currentPeriodReport,

    // Ações
    closeEditor,
    handleGenerateReport,
    handleSaveReport,
    refreshExistingReports: fetchExistingReports,
  };
}
