import React, { useState, useMemo, useEffect } from 'react';
import { motion } from 'framer-motion';
import { FileText, Filter, Eye, Loader2, Download, Inbox, X, Edit, Save, ChevronLeft, ChevronRight } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog';
import { ScrollArea } from '@/components/ui/scroll-area';
import { format, isValid, parseISO } from 'date-fns';
import { ptBR } from 'date-fns/locale';
import { safeFormatDate } from '@/lib/dateUtils';
import { useToast } from '@/components/ui/use-toast';
import { apiClient } from '@/lib/apiClient';
import { useAuth } from '@/contexts/AuthContext';
import { atualizarRelatorio, baixarPdfRelatorio, buscarRelatorio } from '@/services/api';
import RichTextEditor from '@/components/ui/rich-text-editor';
import BulkReportDownloadModal from './BulkReportDownloadModal';

const statusStyles = {
  'Finalizado': 'bg-green-100 text-green-800',
  'Rascunho': 'bg-yellow-100 text-yellow-800',
  'Não iniciado': 'bg-red-100 text-red-800',
};

const PAGE_SIZE = 20;

const ReportsView = ({ data, turmas, onReportUpdated }) => {
  const { toast } = useToast();
  const { user } = useAuth();
  const [turmaFilter, setTurmaFilter] = useState('all');
  const [bimestreFilter, setBimestreFilter] = useState('all');
  const [bimestres, setBimestres] = useState([]);
  const [bimestreLabels, setBimestreLabels] = useState([]);
  const [selectedReport, setSelectedReport] = useState(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [proxiedContent, setProxiedContent] = useState(null);
  const [loadingContent, setLoadingContent] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [draftContent, setDraftContent] = useState('');
  const [persistedContent, setPersistedContent] = useState('');
  const [savingEdit, setSavingEdit] = useState(false);
  const getFallbackBimestreLabel = (inicio, fim) => {
    if (!inicio || !fim) return null;
    const mesInicio = inicio.getMonth() + 1;
    const bimestre = mesInicio <= 3 ? 1 : mesInicio <= 6 ? 2 : mesInicio <= 9 ? 3 : 4;
    return `${bimestre}º Bimestre`;
  };
  const formatPeriodoLabel = (periodo) => {
    if (!periodo) return 'Período não informado';

    // Se for um objeto Date, formatar diretamente
    if (periodo instanceof Date && isValid(periodo)) {
      return format(periodo, 'dd/MM/yyyy', { locale: ptBR });
    }

    // Se não for string, tentar converter para Date primeiro
    if (typeof periodo !== 'string') {
      const dateObj = new Date(periodo);
      if (isValid(dateObj)) {
        return format(dateObj, 'dd/MM/yyyy', { locale: ptBR });
      }
      return 'Período inválido';
    }

    // Se já é um label de bimestre, retornar como está
    if (periodo.includes('º Bimestre')) return periodo;

    // Função auxiliar para tentar parse de data em vários formatos
    const tryParseDate = (str) => {
      // Primeiro tenta parseISO (formato "2025-11-15")
      let date = parseISO(str);
      if (isValid(date)) return date;
      // Depois tenta new Date() (funciona com "Sat Nov 15 2025...")
      date = new Date(str);
      if (isValid(date)) return date;
      return null;
    };

    // Tentar fazer parse de um intervalo "data - data"
    const partes = periodo.split(' - ');
    if (partes.length >= 2) {
      // Pode ter mais de 2 partes se a data tiver " - " no meio (ex: GMT-0300)
      // Tentamos identificar onde está a segunda data pelo padrão
      let inicio = null;
      let fim = null;

      // Se tem exatamente 2 partes, é o caso simples
      if (partes.length === 2) {
        inicio = tryParseDate(partes[0].trim());
        fim = tryParseDate(partes[1].trim());
      } else {
        // Caso complexo: "Sat Nov 15 2025 00:00:00 GMT-0300 (...) - Tue Nov 25 2025 00:00:00 GMT-0300 (...)"
        // Precisa encontrar onde dividir corretamente
        const fullMatch = periodo.match(/^(.+?\d{4}[^-]*?)\s*-\s*(.+)$/);
        if (fullMatch) {
          inicio = tryParseDate(fullMatch[1].trim());
          fim = tryParseDate(fullMatch[2].trim());
        }
      }

      if (inicio && fim && isValid(inicio) && isValid(fim)) {
        const inicioMs = inicio.getTime();
        const fimMs = fim.getTime();
        const bimestreEncontrado = bimestres.find(bimestre => {
          const dataInicio = new Date(bimestre.data_inicio).getTime();
          const dataFim = new Date(bimestre.data_fim).getTime();
          return inicioMs >= dataInicio && fimMs <= dataFim;
        });
        if (bimestreEncontrado?.label) {
          return bimestreEncontrado.label;
        }
        const fallbackLabel = getFallbackBimestreLabel(inicio, fim);
        if (fallbackLabel) {
          return fallbackLabel;
        }
        return `${format(inicio, 'dd/MM/yyyy', { locale: ptBR })} - ${format(fim, 'dd/MM/yyyy', { locale: ptBR })}`;
      }
    }

    // Tentar parse como data única
    const dataUnica = tryParseDate(periodo);
    if (dataUnica && isValid(dataUnica)) {
      return format(dataUnica, 'dd/MM/yyyy', { locale: ptBR });
    }

    return periodo;
  };

  useEffect(() => {
    const fetchBimestres = async () => {
      if (!user?.user_metadata?.instituicao_id) return;
      const { data, error } = await apiClient
        .from('periodos_avaliativos')
        .select('id, descricao, data_inicio, data_fim')
        .eq('instituicao_id', user.user_metadata.instituicao_id)
        .order('data_inicio', { ascending: true });

      if (error) {
        console.error('Error fetching períodos:', error);
      } else {
        const periodosOrdenados = (data || []).map(periodo => ({
          ...periodo,
          label: periodo.descricao,
        }));
        const labels = [...new Set(periodosOrdenados.map(p => p.label))];
        setBimestres(periodosOrdenados);
        setBimestreLabels(labels);
      }
    };
    fetchBimestres();
  }, [user]);

  const getStatus = (report) => {
    if (!report) return 'Não iniciado';
    // Prefer o flag calculado no backend; quando indisponível (ex.: report já
    // carregado com conteudo), cai no mesmo heurístico antigo.
    if (typeof report.finalizado === 'boolean') {
      return report.finalizado ? 'Finalizado' : 'Rascunho';
    }
    if (!report.conteudo) return 'Não iniciado';
    if (report.conteudo.length > 50) return 'Finalizado';
    return 'Rascunho';
  };

  const filteredData = useMemo(() => {
    if (!data) return [];
    return data.filter(report => {
      const turmaNome = report.criancas?.turmas?.nome || report.turma_nome || '';
      const turmaMatch = turmaFilter === 'all' || turmaNome === turmaFilter;
      const periodoLabel = formatPeriodoLabel(report.periodo);
      const bimestreMatch = bimestreFilter === 'all' || periodoLabel === bimestreFilter;
      return turmaMatch && bimestreMatch;
    });
  }, [data, turmaFilter, bimestreFilter, bimestres]);

  const [currentPage, setCurrentPage] = useState(1);

  const totalPages = Math.max(1, Math.ceil(filteredData.length / PAGE_SIZE));

  // Resetar para página 1 quando filtros mudam; clamp quando a lista encolhe
  // (por exemplo após uma edição que muda o conjunto filtrado).
  useEffect(() => {
    setCurrentPage(1);
  }, [turmaFilter, bimestreFilter]);

  useEffect(() => {
    if (currentPage > totalPages) {
      setCurrentPage(totalPages);
    }
  }, [totalPages, currentPage]);

  const pagedData = useMemo(() => {
    const start = (currentPage - 1) * PAGE_SIZE;
    return filteredData.slice(start, start + PAGE_SIZE);
  }, [filteredData, currentPage]);

  const pageStartIndex = filteredData.length === 0 ? 0 : (currentPage - 1) * PAGE_SIZE + 1;
  const pageEndIndex = Math.min(currentPage * PAGE_SIZE, filteredData.length);

  const handleViewReport = async (report) => {
    if (getStatus(report) === 'Não iniciado') {
      toast({
        variant: "destructive",
        title: "Ação não permitida",
        description: "Este relatório ainda não foi iniciado pelo professor.",
      });
      return;
    }

    setSelectedReport(report);
    setProxiedContent(null);
    setIsModalOpen(true);
    setLoadingContent(true);
    setIsEditing(false);
    setDraftContent('');
    setPersistedContent('');
    try {
      // A listagem omite `conteudo` (TextField grande) para acelerar o load
      // da página do coordenador. Busca o HTML completo só quando o modal abre.
      // O backend já re-assina as URLs S3 dos <img> em detalhe_relatorio,
      // então o browser pode carregar as imagens direto — sem passar por
      // `/proxy-imagem/` uma vez por imagem (era o gargalo do spinner).
      const conteudo = report.conteudo
        ?? (await buscarRelatorio(report.id))?.conteudo
        ?? '';
      setSelectedReport((prev) => (prev && prev.id === report.id ? { ...prev, conteudo } : prev));
      setProxiedContent(conteudo);
      setPersistedContent(conteudo);
      setDraftContent(conteudo);
    } catch (err) {
      console.error('Erro ao carregar conteúdo do relatório:', err);
      toast({
        variant: 'destructive',
        title: 'Erro ao carregar relatório',
        description: 'Não foi possível buscar o conteúdo. Tente novamente.',
      });
      setProxiedContent('');
    } finally {
      setLoadingContent(false);
    }
  };

  const closeModal = () => {
    setIsModalOpen(false);
    setSelectedReport(null);
    setProxiedContent(null);
    setIsEditing(false);
    setDraftContent('');
    setPersistedContent('');
  };

  const persistDraft = async () => {
    if (!selectedReport?.id) return;
    await atualizarRelatorio(selectedReport.id, { conteudo: draftContent });
    setPersistedContent(draftContent);
    // Reflete o novo conteudo no selectedReport para que getStatus/download
    // vejam o valor atualizado sem precisar re-abrir o modal.
    setSelectedReport((prev) => prev ? { ...prev, conteudo: draftContent } : prev);
    onReportUpdated?.({ id: selectedReport.id, conteudo: draftContent });
  };

  const handleSaveEdit = async () => {
    if (!selectedReport?.id) return;
    setSavingEdit(true);
    try {
      await persistDraft();
      toast({
        title: 'Relatório atualizado',
        description: 'As alterações foram salvas com sucesso.',
      });
      setIsEditing(false);
      // Pós-save: o draftContent já reflete o que acabamos de persistir.
      // Não proxiamos imagens aqui — o browser carrega do S3 direto.
      setProxiedContent(draftContent);
    } catch (error) {
      console.error('Erro ao salvar relatório:', error);
      toast({
        variant: 'destructive',
        title: 'Erro ao salvar',
        description: 'Não foi possível salvar as alterações. Tente novamente.',
      });
    } finally {
      setSavingEdit(false);
    }
  };

  const toggleEditing = () => {
    if (isEditing && draftContent !== persistedContent) {
      // Reverte mudanças não salvas ao voltar para visualização.
      setDraftContent(persistedContent);
    }
    setIsEditing((prev) => !prev);
  };

  const [downloadingId, setDownloadingId] = useState(null);
  const [selectedIds, setSelectedIds] = useState(() => new Set());
  const [isBulkModalOpen, setIsBulkModalOpen] = useState(false);
  const [bulkReports, setBulkReports] = useState([]);

  const selectableFilteredIds = useMemo(
    () => filteredData
      .filter((r) => getStatus(r) === 'Finalizado')
      .map((r) => String(r.id)),
    [filteredData],
  );

  const allFilteredSelected = selectableFilteredIds.length > 0
    && selectableFilteredIds.every((id) => selectedIds.has(id));
  const someFilteredSelected = !allFilteredSelected
    && selectableFilteredIds.some((id) => selectedIds.has(id));

  const toggleOne = (reportId) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      const key = String(reportId);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  const toggleAllFiltered = () => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (allFilteredSelected) {
        selectableFilteredIds.forEach((id) => next.delete(id));
      } else {
        selectableFilteredIds.forEach((id) => next.add(id));
      }
      return next;
    });
  };

  const clearSelection = () => setSelectedIds(new Set());

  const handleBulkDownload = () => {
    const chosen = filteredData
      .filter((r) => selectedIds.has(String(r.id)) && getStatus(r) === 'Finalizado')
      .map((r) => ({
        id: String(r.id),
        nome: r.criancas?.nome_completo || r.crianca_nome || 'Estudante',
        turma: r.criancas?.turmas?.nome || r.turma_nome || null,
        periodo: formatPeriodoLabel(r.periodo),
      }));
    if (chosen.length === 0) {
      toast({
        variant: 'destructive',
        title: 'Nenhum relatório selecionado',
        description: 'Selecione ao menos um relatório finalizado.',
      });
      return;
    }
    setBulkReports(chosen);
    setIsBulkModalOpen(true);
  };

  const handleDownloadPdf = async (report) => {
    if (getStatus(report) !== 'Finalizado') {
       toast({
        variant: "destructive",
        title: "Download não disponível",
        description: "O relatório precisa estar finalizado para ser baixado.",
      });
      return;
    }

    setDownloadingId(report.id);
    try {
      // Se há edição pendente no modal para este relatório, persiste antes
      // — caso contrário o backend regeneraria o PDF com o conteudo antigo.
      if (
        selectedReport?.id === report.id
        && draftContent
        && draftContent !== persistedContent
      ) {
        await persistDraft();
        toast({
          title: 'Alterações salvas',
          description: 'Suas edições foram salvas antes do download.',
        });
      }

      const { blob, filename } = await baixarPdfRelatorio(report.id);
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (error) {
      toast({
        variant: "destructive",
        title: "Erro ao gerar PDF",
        description: error?.message || "Não foi possível exportar o relatório.",
      });
    } finally {
      setDownloadingId(null);
    }
  };

  if (!data) {
    return (
      <div className="flex justify-center items-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-purple-500" />
      </div>
    );
  }

  return (
    <Card className="bg-white/50 overflow-x-auto">
      <CardHeader>
        <CardTitle className="flex items-center gap-3 text-xl">
          <FileText className="h-6 w-6 text-green-500" />
          Acompanhamento de Relatórios
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex flex-col sm:flex-row gap-4 mb-6">
          <Select value={turmaFilter} onValueChange={setTurmaFilter}>
            <SelectTrigger className="w-full sm:w-[200px]">
              <Filter className="h-4 w-4 mr-2 text-gray-400" />
              <SelectValue placeholder="Filtrar por Turma" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Todas as Turmas</SelectItem>
              {(turmas || []).map(turma => (
                <SelectItem key={turma.id} value={turma.nome}>{turma.nome}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select value={bimestreFilter} onValueChange={setBimestreFilter}>
            <SelectTrigger className="w-full sm:w-[200px]">
              <Filter className="h-4 w-4 mr-2 text-gray-400" />
              <SelectValue placeholder="Filtrar por Período" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Todos os Períodos</SelectItem>
              {bimestreLabels.map(label => (
                  <SelectItem key={label} value={label}>{label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {selectedIds.size > 0 && (
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-4 p-3 rounded-lg border border-purple-200 bg-purple-50">
            <span className="text-sm text-purple-900 font-medium">
              {selectedIds.size} relatório{selectedIds.size > 1 ? 's' : ''} selecionado{selectedIds.size > 1 ? 's' : ''}
            </span>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={clearSelection}>
                Limpar seleção
              </Button>
              <Button size="sm" onClick={handleBulkDownload}>
                <Download className="h-4 w-4 mr-2" />
                Baixar {selectedIds.size} PDF{selectedIds.size > 1 ? 's' : ''} (ZIP)
              </Button>
            </div>
          </div>
        )}

        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
          {!data || data.length === 0 ? (
            <div className="flex flex-col items-center justify-center text-center py-16 text-gray-500">
              <Inbox className="h-12 w-12 text-gray-400 mb-4" />
              <p className="font-semibold text-lg">Nenhum relatório para exibir.</p>
              <p className="text-sm mt-1">Quando os relatórios forem criados, eles aparecerão aqui.</p>
            </div>
          ) : filteredData.length === 0 ? (
            <div className="text-center py-12 text-gray-500">
              <p>Nenhum relatório encontrado para os filtros selecionados.</p>
            </div>
          ) : (
            <>
              <div className="md:hidden space-y-4">
                {pagedData.map(report => {
                  const isFinalizado = getStatus(report) === 'Finalizado';
                  const isChecked = selectedIds.has(String(report.id));
                  return (
                  <Card key={report.id} className="p-4">
                    <div className="flex items-start gap-3">
                      <Checkbox
                        className="mt-1"
                        checked={isChecked}
                        disabled={!isFinalizado}
                        onCheckedChange={() => toggleOne(report.id)}
                        aria-label="Selecionar relatório"
                      />
                      <div className="flex-1 min-w-0">
                    <div className="font-bold">{report.criancas?.nome_completo || report.crianca_nome || 'Nome não disponível'}</div>
                    <div className="text-sm text-gray-600">{report.criancas?.turmas?.nome || report.turma_nome || 'Turma'} | {formatPeriodoLabel(report.periodo)}</div>
                    <div className="text-xs text-gray-500 mt-1">
                      Prof: {report.professor_nome || report.revisado_por?.nome || 'Não informado'} - {safeFormatDate(report.data_criacao, 'dd/MM/yyyy')}
                    </div>
                    <div className="flex justify-between items-center mt-2">
                      <span className={`px-2 py-1 rounded-full text-xs font-semibold ${statusStyles[getStatus(report)]}`}>
                        {getStatus(report)}
                      </span>
                      <div className="flex gap-2">
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleViewReport(report)}
                          >
                            <Eye className="h-4 w-4" />
                        </Button>
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleDownloadPdf(report)}
                            disabled={getStatus(report) !== 'Finalizado' || downloadingId === report.id}
                          >
                            {downloadingId === report.id ? (
                              <Loader2 className="h-4 w-4 animate-spin" />
                            ) : (
                              <Download className="h-4 w-4" />
                            )}
                        </Button>
                      </div>
                    </div>
                      </div>
                    </div>
                  </Card>
                  );
                })}
              </div>

              <div className="hidden md:block">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-10">
                        <Checkbox
                          checked={
                            allFilteredSelected ? true : (someFilteredSelected ? 'indeterminate' : false)
                          }
                          onCheckedChange={toggleAllFiltered}
                          disabled={selectableFilteredIds.length === 0}
                          aria-label="Selecionar todos os relatórios filtrados"
                        />
                      </TableHead>
                      <TableHead>Criança</TableHead>
                      <TableHead>Turma</TableHead>
                      <TableHead>Bimestre</TableHead>
                      <TableHead>Professor</TableHead>
                      <TableHead>Data</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Ações</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {pagedData.map((report) => (
                      <TableRow key={report.id}>
                        <TableCell className="w-10">
                          <Checkbox
                            checked={selectedIds.has(String(report.id))}
                            disabled={getStatus(report) !== 'Finalizado'}
                            onCheckedChange={() => toggleOne(report.id)}
                            aria-label="Selecionar relatório"
                          />
                        </TableCell>
                        <TableCell className="font-medium">{report.criancas?.nome_completo || report.crianca_nome || 'Nome não disponível'}</TableCell>
                        <TableCell>{report.criancas?.turmas?.nome || report.turma_nome || 'Turma'}</TableCell>
                        <TableCell>{formatPeriodoLabel(report.periodo)}</TableCell>
                        <TableCell>{report.professor_nome || report.revisado_por?.nome || 'Não informado'}</TableCell>
                        <TableCell>{safeFormatDate(report.data_criacao, 'dd/MM/yyyy')}</TableCell>
                        <TableCell>
                          <span className={`px-2 py-1 rounded-full text-xs font-semibold ${statusStyles[getStatus(report)]}`}>
                            {getStatus(report)}
                          </span>
                        </TableCell>
                        <TableCell>
                          <div className="flex gap-2">
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleViewReport(report)}
                            >
                              <Eye className="h-4 w-4 mr-2" />
                              Visualizar
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleDownloadPdf(report)}
                              disabled={getStatus(report) !== 'Finalizado' || downloadingId === report.id}
                            >
                              {downloadingId === report.id ? (
                                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                              ) : (
                                <Download className="h-4 w-4 mr-2" />
                              )}
                              {downloadingId === report.id ? 'Gerando...' : 'Baixar'}
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>

              {filteredData.length > PAGE_SIZE && (
                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mt-4 pt-4 border-t">
                  <span className="text-sm text-gray-600">
                    Exibindo {pageStartIndex}–{pageEndIndex} de {filteredData.length} relatório{filteredData.length > 1 ? 's' : ''}
                  </span>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                      disabled={currentPage === 1}
                    >
                      <ChevronLeft className="h-4 w-4 mr-1" />
                      Anterior
                    </Button>
                    <span className="text-sm text-gray-700 px-2">
                      Página {currentPage} de {totalPages}
                    </span>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                      disabled={currentPage === totalPages}
                    >
                      Próxima
                      <ChevronRight className="h-4 w-4 ml-1" />
                    </Button>
                  </div>
                </div>
              )}
            </>
          )}
        </motion.div>
      </CardContent>

      {/* Modal de Visualização do Relatório */}
      <Dialog open={isModalOpen} onOpenChange={setIsModalOpen}>
        <DialogContent className="max-w-3xl max-h-[90vh]">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <FileText className="h-5 w-5 text-purple-600" />
              Relatório de {selectedReport?.criancas?.nome_completo || selectedReport?.crianca_nome || 'Estudante'}
            </DialogTitle>
            <DialogDescription>
              {selectedReport?.criancas?.turmas?.nome || selectedReport?.turma_nome || 'Turma'} | {formatPeriodoLabel(selectedReport?.periodo)}
            </DialogDescription>
          </DialogHeader>

          <ScrollArea className="max-h-[60vh] pr-4">
            {selectedReport && (
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <span className="font-semibold text-gray-600">Professor:</span>
                    <p>{selectedReport.professor_nome || selectedReport.revisado_por?.nome || 'Não informado'}</p>
                  </div>
                  <div>
                    <span className="font-semibold text-gray-600">Data de Criação:</span>
                    <p>{safeFormatDate(selectedReport.data_criacao, 'dd/MM/yyyy')}</p>
                  </div>
                  <div>
                    <span className="font-semibold text-gray-600">Status:</span>
                    <span className={`ml-2 px-2 py-1 rounded-full text-xs font-semibold ${statusStyles[getStatus(selectedReport)]}`}>
                      {getStatus(selectedReport)}
                    </span>
                  </div>
                </div>

                <div className="border-t pt-4">
                  <h4 className="font-semibold text-gray-700 mb-2">Conteúdo do Relatório:</h4>
                  {loadingContent ? (
                    <div className="flex justify-center items-center py-8">
                      <Loader2 className="h-6 w-6 animate-spin text-purple-500" />
                    </div>
                  ) : isEditing ? (
                    <RichTextEditor
                      content={draftContent}
                      onUpdate={setDraftContent}
                      editable={true}
                      placeholder="Digite o conteúdo do relatório..."
                    />
                  ) : (
                    <RichTextEditor
                      content={proxiedContent || selectedReport.conteudo || 'Conteúdo não disponível.'}
                      editable={false}
                    />
                  )}
                </div>
              </div>
            )}
          </ScrollArea>

          <div className="flex justify-between items-center gap-2 pt-4 border-t">
            <div>
              {!loadingContent && selectedReport && (
                <Button
                  variant="outline"
                  onClick={toggleEditing}
                  disabled={savingEdit}
                >
                  {isEditing ? (
                    <>
                      <Eye className="h-4 w-4 mr-2" />
                      Visualizar
                    </>
                  ) : (
                    <>
                      <Edit className="h-4 w-4 mr-2" />
                      Editar
                    </>
                  )}
                </Button>
              )}
            </div>
            <div className="flex gap-2">
              <Button variant="outline" onClick={closeModal}>
                Fechar
              </Button>
              {isEditing && (
                <Button
                  onClick={handleSaveEdit}
                  disabled={savingEdit || !draftContent.trim() || draftContent === persistedContent}
                  className="bg-purple-600 hover:bg-purple-700"
                >
                  {savingEdit ? (
                    <>
                      <Save className="h-4 w-4 mr-2 animate-pulse" />
                      Salvando...
                    </>
                  ) : (
                    <>
                      <Save className="h-4 w-4 mr-2" />
                      Salvar Alterações
                    </>
                  )}
                </Button>
              )}
              {!isEditing && selectedReport && getStatus(selectedReport) === 'Finalizado' && (
                <Button
                  onClick={() => handleDownloadPdf(selectedReport)}
                  disabled={downloadingId === selectedReport.id}
                >
                  {downloadingId === selectedReport.id ? (
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  ) : (
                    <Download className="h-4 w-4 mr-2" />
                  )}
                  {downloadingId === selectedReport.id ? 'Gerando...' : 'Baixar PDF'}
                </Button>
              )}
            </div>
          </div>
        </DialogContent>
      </Dialog>

      <BulkReportDownloadModal
        isOpen={isBulkModalOpen}
        onClose={() => setIsBulkModalOpen(false)}
        reports={bulkReports}
      />
    </Card>
  );
};

export default ReportsView;
