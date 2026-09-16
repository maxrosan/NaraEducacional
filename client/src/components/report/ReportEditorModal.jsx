import React, { useState, useRef, useEffect } from 'react';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';
import RichTextEditor from '@/components/ui/rich-text-editor';
import { baixarPdfRelatorio } from '@/services/api';
import { useToast } from '@/components/ui/use-toast';
import {
  FileText,
  Save,
  Download,
  RefreshCw,
  Loader2,
  Eye,
  Edit,
  Sparkles,
  Clock,
  User,
  Calendar
} from 'lucide-react';
import { format } from 'date-fns';
import { ptBR } from 'date-fns/locale';
import { safeFormatDate } from '@/lib/dateUtils';

function ReportEditorModal({ 
  isOpen, 
  onClose, 
  onSave, 
  reportData, 
  studentName, 
  period,
  loading = false 
}) {
  const [content, setContent] = useState('');
  const [persistedContent, setPersistedContent] = useState('');
  const [savedReportId, setSavedReportId] = useState(null);
  const [isEditing, setIsEditing] = useState(true);
  const [saving, setSaving] = useState(false);
  const [generatingPdf, setGeneratingPdf] = useState(false);
  const { toast } = useToast();

  // Config de paleta/tipografia do template usado pra gerar este relatório —
  // cobre os dois formatos possíveis de reportData: recém-gerado (vem em
  // .metadata.templateConfig, ver gerar_relatorio_com_ia) ou já salvo e
  // reaberto depois (vem em .template_config, ver RelatorioSerializer).
  const templateConfig = reportData?.template_config || reportData?.metadata?.templateConfig || null;

  // Atualizar conteúdo quando reportData mudar
  useEffect(() => {
    console.log('🔄 [ReportEditorModal] reportData updated:', reportData);
    if (reportData?.content) {
      setContent(reportData.content);
      setPersistedContent('');
      setSavedReportId(null);
    }
  }, [reportData]);

  // Debug log para verificar props
  useEffect(() => {
    console.log('🏗️ [ReportEditorModal] Props:', {
      isOpen,
      reportData,
      studentName,
      period,
      contentState: content
    });
  }, [isOpen, reportData, studentName, period, content]);

  const handleSave = async () => {
    setSaving(true);
    try {
      await onSave({
        content,
        period,
        studentName,
        generatedAt: new Date().toISOString()
      });
    } finally {
      setSaving(false);
    }
  };

  const handleDownloadPdf = async () => {
    if (!content) return;
    setGeneratingPdf(true);
    try {
      let relatorioId = savedReportId;

      // Auto-save quando há edição pendente — o PDF é renderizado pelo backend
      // a partir do conteúdo persistido, então precisamos salvar antes.
      if (!relatorioId || content !== persistedContent) {
        const relatorio = await onSave(
          {
            content,
            period,
            studentName,
            generatedAt: new Date().toISOString(),
          },
          { keepOpen: true }
        );
        if (!relatorio?.id) {
          throw new Error('Não foi possível obter o identificador do relatório após salvar.');
        }
        relatorioId = relatorio.id;
        setSavedReportId(relatorio.id);
        setPersistedContent(content);
      }

      const { blob, filename } = await baixarPdfRelatorio(relatorioId);
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Erro ao gerar PDF:', err);
      toast({
        variant: 'destructive',
        title: 'Erro ao gerar PDF',
        description: err?.message || 'Não foi possível gerar o PDF. Tente novamente.',
      });
    } finally {
      setGeneratingPdf(false);
    }
  };

  const handleRegenerateSection = () => {
    console.log('Regenerar seção específica');
  };

  const formatPeriod = (period) => {
    if (period?.startDate && period?.endDate) {
      const start = safeFormatDate(period.startDate, 'dd/MM/yyyy', { locale: ptBR });
      const end = safeFormatDate(period.endDate, 'dd/MM/yyyy', { locale: ptBR });
      if (!start || !end) return 'Período não definido';
      return `${start} - ${end}`;
    }
    return 'Período não definido';
  };

  const plainText = content.replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim();
  const wordCount = plainText ? plainText.split(/\s+/).length : 0;
  const characterCount = plainText.length;

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-4xl max-h-[90vh] overflow-hidden flex flex-col">
        <DialogHeader className="flex-shrink-0">
          <DialogTitle className="flex items-center gap-2">
            <FileText className="h-5 w-5 text-roxo-principal" />
            Editor de Relatório
          </DialogTitle>
          <DialogDescription>
            Visualize e edite o relatório gerado para {studentName}
          </DialogDescription>
        </DialogHeader>

        <div className="flex-1 overflow-auto space-y-4">
          {/* Informações do Relatório */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium">Informações do Relatório</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
                <div className="flex items-center gap-2">
                  <User className="h-4 w-4 text-gray-500" />
                  <span className="font-medium">Estudante:</span>
                  <span>{studentName}</span>
                </div>
                <div className="flex items-center gap-2">
                  <Calendar className="h-4 w-4 text-gray-500" />
                  <span className="font-medium">Período:</span>
                  <Badge variant="outline">{formatPeriod(period)}</Badge>
                </div>
                <div className="flex items-center gap-2">
                  <Clock className="h-4 w-4 text-gray-500" />
                  <span className="font-medium">Gerado em:</span>
                  <span>
                    {reportData?.generatedAt
                      ? safeFormatDate(reportData.generatedAt, 'dd/MM/yyyy HH:mm', { locale: ptBR }, 'Agora')
                      : 'Agora'
                    }
                  </span>
                </div>
              </div>
              
              {/* Estatísticas do texto */}
              <Separator />
              <div className="flex gap-4 text-xs text-gray-500">
                <span>{wordCount} palavras</span>
                <span>{characterCount} caracteres</span>
                <span>~{Math.ceil(wordCount / 250)} min de leitura</span>
              </div>
            </CardContent>
          </Card>

          {/* Conteúdo do Relatório */}
          <Card className="flex-1">
            <CardHeader className="flex-row items-center justify-between pb-3">
              <CardTitle className="text-sm font-medium">Conteúdo do Relatório</CardTitle>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setIsEditing(!isEditing)}
                  className="flex items-center gap-1"
                >
                  {isEditing ? (
                    <>
                      <Eye className="h-3 w-3" />
                      Visualizar
                    </>
                  ) : (
                    <>
                      <Edit className="h-3 w-3" />
                      Editar
                    </>
                  )}
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleRegenerateSection}
                  className="flex items-center gap-1"
                  disabled={loading}
                >
                  <Sparkles className="h-3 w-3" />
                  Regenerar
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              <RichTextEditor
                content={content}
                onUpdate={setContent}
                editable={isEditing}
                placeholder="Digite o conteúdo do relatório..."
                templateConfig={templateConfig}
              />
            </CardContent>
          </Card>

          {/* Sugestões da IA */}
          {reportData?.suggestions && (
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-medium flex items-center gap-2">
                  <Sparkles className="h-4 w-4 text-roxo-principal" />
                  Sugestões da IA
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {reportData.suggestions.map((suggestion, index) => (
                    <div key={index} className="p-3 bg-blue-50 rounded-md text-sm">
                      <p className="text-blue-800">{suggestion}</p>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </div>

        {/* Ações */}
        <div className="flex-shrink-0 flex justify-between items-center pt-4 border-t">
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              className="flex items-center gap-1"
              onClick={handleDownloadPdf}
              disabled={generatingPdf || !content}
            >
              {generatingPdf ? (
                <Loader2 className="h-3 w-3 animate-spin" />
              ) : (
                <Download className="h-3 w-3" />
              )}
              <span>{generatingPdf ? 'Gerando...' : 'Download PDF'}</span>
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={handleRegenerateSection}
              disabled={loading}
              className="flex items-center gap-1"
            >
              <RefreshCw className="h-3 w-3" />
              Regenerar Tudo
            </Button>
          </div>
          
          <div className="flex gap-2">
            <Button
              variant="outline"
              onClick={onClose}
              disabled={saving}
            >
              Cancelar
            </Button>
            <Button
              onClick={handleSave}
              disabled={saving || !content.trim()}
              className="bg-roxo-principal hover:bg-roxo-principal/90"
            >
              {saving ? (
                <>
                  <Save className="mr-2 h-4 w-4 animate-pulse" />
                  <span>Salvando...</span>
                </>
              ) : (
                <>
                  <Save className="mr-2 h-4 w-4" />
                  <span>Salvar Relatório</span>
                </>
              )}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

export default ReportEditorModal;