import React, { useState, useEffect } from 'react';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import RichTextEditor from '@/components/ui/rich-text-editor';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';
import { useToast } from '@/components/ui/use-toast';
import { 
  FileText, 
  Save, 
  Download, 
  Eye, 
  Edit, 
  Clock,
  User,
  Calendar,
  X
} from 'lucide-react';
import { format } from 'date-fns';
import { ptBR } from 'date-fns/locale';
import {
  atualizarRelatorio,
  baixarPdfRelatorio,
  buscarRelatorio,
} from '@/services/api';

function ViewReportModal({
  isOpen,
  onClose,
  reportData,
  studentName,
  studentId,
  turmaId,
  turmaName,
  onReportUpdated,
  instituicaoId,
  readOnly = false
}) {
  const [content, setContent] = useState('');
  const [persistedContent, setPersistedContent] = useState('');
  const [templateConfig, setTemplateConfig] = useState(null);
  const [isEditing, setIsEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(false);
  const [generatingPdf, setGeneratingPdf] = useState(false);
  const { toast } = useToast();

  // Buscar conteúdo completo do relatório quando o modal abrir
  useEffect(() => {
    const fetchReportContent = async () => {
      if (!isOpen || !reportData?.id) return;

      setLoading(true);
      try {
        const data = await buscarRelatorio(reportData.id);
        const rawContent = data?.conteudo || 'Conteúdo não disponível para este relatório.';
        // O backend já re-assina URLs S3 em detalhe_relatorio; o browser carrega
        // as imagens direto, sem um POST /proxy-imagem/ por imagem.
        setContent(rawContent);
        setPersistedContent(rawContent);
        // Paleta/tipografia do template usado para gerar este relatório — sem
        // isso o RichTextEditor cai no tema padrão em vez das cores reais
        // configuradas (mesmo campo que ReportEditorModal já usa).
        setTemplateConfig(data?.template_config || null);
      } catch (error) {
        console.error('Erro ao carregar conteúdo do relatório:', error);
        setContent('Erro ao carregar conteúdo do relatório.');
        setPersistedContent('');
        setTemplateConfig(null);
        toast({
          variant: 'destructive',
          title: 'Erro',
          description: 'Não foi possível carregar o conteúdo do relatório.'
        });
      } finally {
        setLoading(false);
      }
    };

    fetchReportContent();
  }, [isOpen, reportData?.id, toast]);

  // Limpar estado quando modal fechar
  useEffect(() => {
    if (!isOpen) {
      setContent('');
      setPersistedContent('');
      setTemplateConfig(null);
      setIsEditing(false);
      setSaving(false);
      setLoading(false);
    }
  }, [isOpen]);

  const persistContent = async () => {
    await atualizarRelatorio(reportData.id, { conteudo: content });
    setPersistedContent(content);
    if (onReportUpdated) onReportUpdated();
  };

  const handleSave = async () => {
    if (!reportData?.id) return;

    setSaving(true);
    try {
      await persistContent();
      toast({
        title: 'Relatório atualizado!',
        description: 'As alterações foram salvas com sucesso.',
      });
      setIsEditing(false);
    } catch (error) {
      console.error('Erro ao salvar relatório:', error);
      toast({
        variant: 'destructive',
        title: 'Erro ao salvar',
        description: 'Não foi possível salvar as alterações. Tente novamente.',
      });
    } finally {
      setSaving(false);
    }
  };

  const handleDownloadPdf = async () => {
    if (!reportData?.id || !content) return;
    setGeneratingPdf(true);
    try {
      // Auto-save quando há edição pendente — senão o PDF renderizado pelo backend
      // não refletiria o que o usuário está vendo.
      if (content !== persistedContent) {
        await persistContent();
        toast({
          title: 'Alterações salvas',
          description: 'Suas edições foram salvas antes do download.',
        });
      }

      const { blob, filename } = await baixarPdfRelatorio(reportData.id);
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Erro ao gerar PDF do relatório:', error);
      toast({
        variant: 'destructive',
        title: 'Erro ao gerar PDF',
        description: error?.message || 'Não foi possível gerar o PDF. Tente novamente.',
      });
    } finally {
      setGeneratingPdf(false);
    }
  };

  const formatDate = (dateString) => {
    if (!dateString) return 'Data não disponível';
    try {
      return format(new Date(dateString), 'dd/MM/yyyy HH:mm', { locale: ptBR });
    } catch {
      return 'Data inválida';
    }
  };

  const plainText = content.replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim();
  const wordCount = plainText ? plainText.split(/\s+/).length : 0;
  const characterCount = plainText.length;

  if (!reportData) return null;

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-4xl max-h-[90vh] overflow-hidden flex flex-col">
        <DialogHeader className="flex-shrink-0">
          <DialogTitle className="flex items-center gap-2">
            <FileText className="h-5 w-5 text-roxo-principal" />
            Visualizar Relatório
          </DialogTitle>
          <DialogDescription>
            Relatório de {studentName} - {reportData.periodo}
          </DialogDescription>
        </DialogHeader>

        {loading ? (
          <div className="flex-1 flex justify-center items-center py-8">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-roxo-principal"></div>
          </div>
        ) : (
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
                    <Badge variant="outline">{reportData.periodo}</Badge>
                  </div>
                  <div className="flex items-center gap-2">
                    <Clock className="h-4 w-4 text-gray-500" />
                    <span className="font-medium">Criado em:</span>
                    <span>{formatDate(reportData.data_criacao)}</span>
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
                  {!readOnly && (
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
                  )}
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleDownloadPdf}
                    className="flex items-center gap-1"
                    disabled={generatingPdf}
                  >
                    <Download className="h-3 w-3" />
                    Download PDF
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
          </div>
        )}

        {/* Ações */}
        <div className="flex-shrink-0 flex justify-between items-center pt-4 border-t">
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={handleDownloadPdf}
              className="flex items-center gap-1"
              disabled={generatingPdf}
            >
              <Download className="h-3 w-3" />
              Download PDF
            </Button>
          </div>
          
          <div className="flex gap-2">
            <Button
              variant="outline"
              onClick={onClose}
              disabled={saving}
            >
              <X className="mr-2 h-4 w-4" />
              Fechar
            </Button>
            {isEditing && (
              <Button
                onClick={handleSave}
                disabled={saving || !content.trim()}
                className="bg-roxo-principal hover:bg-roxo-principal/90"
              >
                {saving ? (
                  <>
                    <Save className="mr-2 h-4 w-4 animate-pulse" />
                    Salvando...
                  </>
                ) : (
                  <>
                    <Save className="mr-2 h-4 w-4" />
                    Salvar Alterações
                  </>
                )}
              </Button>
            )}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

export default ViewReportModal;