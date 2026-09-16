import React, { useState, useEffect } from 'react';
import { FileText, Download, Eye, Calendar, User, Trash2 } from 'lucide-react';
import { format } from 'date-fns';
import { ptBR } from 'date-fns/locale';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { useToast } from '@/components/ui/use-toast';
import ViewReportModal from './ViewReportModal';
import { listarRelatorios, deletarRelatorio, baixarPdfRelatorio } from '@/services/api';

function ReportsBlock({ studentId, studentName, turmaId, turmaName, refreshTrigger, instituicaoId, readOnly = false }) {
  const [reports, setReports] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedReport, setSelectedReport] = useState(null);
  const [isViewModalOpen, setIsViewModalOpen] = useState(false);
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

  const fetchReports = async () => {
    if (!studentId) return;
    
    try {
      const data = await listarRelatorios({ id_crianca: studentId });
      const dedupedReports = dedupeReportsByPeriod(data || []);
      setReports(dedupedReports);
    } catch (error) {
      console.error('Erro ao carregar relatórios:', error);
      toast({
        variant: 'destructive',
        title: 'Erro',
        description: 'Não foi possível carregar os relatórios anteriores.'
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchReports();
  }, [studentId, toast, refreshTrigger]);

  const formatDate = (dateString) => {
    try {
      return format(new Date(dateString), 'dd/MM/yyyy', { locale: ptBR });
    } catch {
      return dateString;
    }
  };

  const getStatusBadge = (periodo) => (
    <Badge variant="default" className="text-xs">
      {periodo || 'Sem período'}
    </Badge>
  );

  const handleViewReport = (report) => {
    setSelectedReport(report);
    setIsViewModalOpen(true);
  };

  const handleCloseViewModal = () => {
    setIsViewModalOpen(false);
    setSelectedReport(null);
  };

  const handleReportUpdated = () => {
    // Atualizar a lista quando um relatório for editado
    fetchReports();
  };

  const handleDeleteReport = async (reportId) => {
    if (!window.confirm('Tem certeza que deseja excluir este relatório? Esta ação não pode ser desfeita.')) {
      return;
    }
    try {
      await deletarRelatorio(reportId);
      toast({
        title: 'Relatório excluído',
        description: 'O relatório foi excluído com sucesso.',
      });
      fetchReports();
    } catch (error) {
      console.error('Erro ao deletar relatório:', error);
      toast({
        variant: 'destructive',
        title: 'Erro',
        description: 'Não foi possível excluir o relatório.',
      });
    }
  };

  const [downloadingId, setDownloadingId] = useState(null);

  const handleDownloadReport = async (reportId) => {
    setDownloadingId(reportId);
    try {
      const { blob, filename } = await baixarPdfRelatorio(reportId);
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);

      toast({
        title: 'PDF gerado',
        description: 'O relatório foi baixado com sucesso.'
      });
    } catch (error) {
      console.error('Erro ao gerar PDF do relatório:', error);
      toast({
        variant: 'destructive',
        title: 'Erro no download',
        description: error?.message || 'Não foi possível gerar o PDF do relatório.'
      });
    } finally {
      setDownloadingId(null);
    }
  };

  if (loading) {
    return (
      <Card className="w-full">
        <CardHeader>
          <div className="flex items-center gap-3">
            <div className="p-2 bg-roxo-principal/10 rounded-lg">
              <FileText className="h-5 w-5 text-roxo-principal" />
            </div>
            <div>
              <CardTitle className="text-xl text-gray-900">Relatórios Gerados</CardTitle>
              <CardDescription>Histórico de relatórios bimestrais</CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="flex justify-center items-center py-8">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-roxo-principal"></div>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="w-full">
      <CardHeader>
        <div className="flex items-center gap-3">
          <div className="p-2 bg-roxo-principal/10 rounded-lg">
            <FileText className="h-5 w-5 text-roxo-principal" />
          </div>
          <div>
            <CardTitle className="text-xl text-gray-900">Relatórios Gerados</CardTitle>
            <CardDescription>
              Histórico de relatórios de {studentName}
            </CardDescription>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {reports.length === 0 ? (
          <div className="text-center py-8">
            <FileText className="h-12 w-12 text-gray-400 mx-auto mb-4" />
            <p className="text-gray-500 text-sm">
              Nenhum relatório anterior encontrado para este estudante.
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            {reports.map((report) => (
              <div
                key={report.id}
                className="flex flex-col sm:flex-row sm:items-center sm:justify-between p-3 sm:p-4 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors gap-3"
              >
                <div className="flex items-center gap-3 sm:gap-4 min-w-0">
                  <div className="p-2 bg-blue-100 rounded-lg shrink-0">
                    <FileText className="h-4 w-4 text-blue-600" />
                  </div>
                  <div className="min-w-0">
                    <h4 className="font-medium text-gray-900 text-sm sm:text-base truncate">
                      {report.periodo}
                    </h4>
                    <div className="flex flex-wrap items-center gap-2 sm:gap-4 text-xs sm:text-sm text-gray-500 mt-1">
                      <div className="flex items-center gap-1">
                        <User className="h-3 w-3" />
                        <span className="truncate max-w-[120px] sm:max-w-none">{report.professor_nome || 'N\u00e3o informado'}</span>
                      </div>
                      <div className="flex items-center gap-1">
                        <Calendar className="h-3 w-3" />
                        {formatDate(report.data_criacao)}
                      </div>
                    </div>
                  </div>
                </div>
                <div className="flex flex-wrap items-center gap-2 sm:gap-3 sm:shrink-0">
                  {getStatusBadge(report.periodo)}
                  <div className="flex flex-wrap gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleViewReport(report)}
                      className="flex items-center gap-1 text-xs sm:text-sm"
                    >
                      <Eye className="h-3 w-3" />
                      <span>Visualizar</span>
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleDownloadReport(report.id)}
                      disabled={downloadingId === report.id}
                      className="flex items-center gap-1 text-xs sm:text-sm"
                    >
                      {downloadingId === report.id ? (
                        <div className="h-3 w-3 animate-spin rounded-full border-2 border-current border-t-transparent" />
                      ) : (
                        <Download className="h-3 w-3" />
                      )}
                      <span>{downloadingId === report.id ? 'Gerando...' : 'Download'}</span>
                    </Button>
                    {!readOnly && (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleDeleteReport(report.id)}
                        className="flex items-center gap-1 text-red-600 hover:text-red-700 hover:bg-red-50 text-xs sm:text-sm"
                      >
                        <Trash2 className="h-3 w-3" />
                        <span>Excluir</span>
                      </Button>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>

      {/* Modal de Visualização de Relatório */}
      <ViewReportModal
        isOpen={isViewModalOpen}
        onClose={handleCloseViewModal}
        reportData={selectedReport}
        studentName={studentName}
        studentId={studentId}
        turmaId={turmaId}
        turmaName={turmaName}
        onReportUpdated={handleReportUpdated}
        instituicaoId={instituicaoId}
        readOnly={readOnly}
      />
    </Card>
  );
}

export default ReportsBlock;
