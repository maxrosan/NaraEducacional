import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Download, Eye, ArrowLeft } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { useAuth } from '@/contexts/AuthContext';
import { useReportGeneration } from '@/hooks/useReportGeneration';
import ReportGenerationLoading from './ReportGenerationLoading';
import ReportEditorModal from './ReportEditorModal';
import ViewReportModal from './ViewReportModal';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || import.meta.env.VITE_API_URL || '';

function abreviarPeriodo(texto) {
  if (!texto) return '';
  const match = texto.match(/(\d+º?)\s*([A-Za-zÀ-ÿ])/);
  if (match) return `${match[1]} ${match[2].toUpperCase()}`;
  return texto
    .split(' ')
    .filter(Boolean)
    .map((p) => p[0]?.toUpperCase())
    .join('. ');
}

async function fetchAllPages(url) {
  let results = [];
  let nextUrl = url;
  while (nextUrl) {
    const response = await fetch(nextUrl, { credentials: 'include' });
    if (!response.ok) throw new Error('Erro ao buscar dados de disciplinas');
    const data = await response.json();
    results = results.concat(data.results ?? data);
    nextUrl = data.next || null;
  }
  return results;
}

function ReportHeader({ student, onReportSaved, periodos = [], selectedPeriodo, onPeriodoChange }) {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [isViewModalOpen, setIsViewModalOpen] = useState(false);

  // Controla se o botão "Gerar"/"Regerar" pode ser exibido.
  // Só se aplica a professor_fundamental: ele precisa lecionar TODAS as
  // disciplinas ativas da instituição (Disciplina.ativo=True) para poder
  // gerar o relatório. Outros perfis não são afetados por essa checagem.
  const [canGenerateReport, setCanGenerateReport] = useState(
    () => user?.perfil !== 'professor_fundamental'
  );

  useEffect(() => {
    if (!user || !student?.instituicao_id) return;

    if (user.perfil !== 'professor_fundamental') {
      setCanGenerateReport(true);
      return;
    }

    let cancelled = false;
    (async () => {
      try {
        const [disciplinas, vinculos] = await Promise.all([
          fetchAllPages(`${API_BASE_URL}/api/disciplinas/?instituicao_id=${student.instituicao_id}`),
          fetchAllPages(`${API_BASE_URL}/api/usuario-disciplinas/?usuario_id=${user.id}&instituicao_id=${student.instituicao_id}`),
        ]);
        if (cancelled) return;

        const ativasIds = new Set(disciplinas.filter(d => d.ativo).map(d => d.id));
        const vinculadasIds = new Set(vinculos.map(v => v.disciplina));
        const lecionaTodas = [...ativasIds].every(id => vinculadasIds.has(id));

        setCanGenerateReport(lecionaTodas);
      } catch (error) {
        console.error('Erro ao verificar disciplinas do professor:', error);
        if (!cancelled) {
          // fail-safe: em caso de erro, esconde o botão em vez de liberar indevidamente
          setCanGenerateReport(false);
        }
      }
    })();

    return () => { cancelled = true; };
  }, [user, student?.instituicao_id]);

  const {
    isEditorOpen,
    loading,
    loadingStep,
    generatedReport,
    currentPeriodReport,
    closeEditor,
    handleGenerateReport,
    handleSaveReport,
    refreshExistingReports,
  } = useReportGeneration(student.id, student.nome_completo, onReportSaved, selectedPeriodo?.descricao);

  const handlePeriodoSelect = (periodoId) => {
    const periodo = periodos.find(p => p.id === periodoId);
    if (periodo) onPeriodoChange(periodo);
  };

  const handleGenerate = () => {
    if (!selectedPeriodo) return;
    handleGenerateReport(selectedPeriodo);
  };

  return (
    <>
      <div className="bg-white border-b shadow-sm">
        <div className="container mx-auto px-4 sm:px-6 lg:px-8 py-3 flex items-center justify-between gap-2">
          <div className="flex items-center gap-2 min-w-0">
            <Button variant="ghost" size="icon" className="shrink-0" onClick={() => navigate(-1)}>
              <ArrowLeft className="h-6 w-6 text-gray-600" />
            </Button>
            <div className="min-w-0">
              <h1 className="text-sm sm:text-xl font-bold text-texto-escuro leading-tight truncate">{student.nome_completo}</h1>
              <p className="text-xs sm:text-sm text-texto-medio">{student.turma_nome}</p>
            </div>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            {periodos.length > 0 && (
              <Select value={selectedPeriodo?.id || ''} onValueChange={handlePeriodoSelect}>
                <SelectTrigger className="w-[68px] sm:w-[200px] text-xs sm:text-sm px-2 sm:px-3">
                  <span className="sm:hidden font-medium truncate">
                    {abreviarPeriodo(selectedPeriodo?.descricao) || '–'}
                  </span>
                  <span className="hidden sm:contents">
                    <SelectValue placeholder="Período avaliativo" />
                  </span>
                </SelectTrigger>
                <SelectContent>
                  {periodos.map((p) => (
                    <SelectItem key={p.id} value={p.id}>{p.descricao}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}

            {currentPeriodReport && (
              <Button variant="outline" size="sm" className="text-xs sm:text-sm px-2 sm:px-3" onClick={() => setIsViewModalOpen(true)}>
                <Eye className="h-4 w-4" />
                <span className="hidden sm:inline sm:ml-2">Visualizar</span>
              </Button>
            )}

            {canGenerateReport && (
              <Button size="sm" className="text-xs sm:text-sm px-2 sm:px-3" onClick={handleGenerate} disabled={loading || !selectedPeriodo}>
                <Download className="h-4 w-4" />
                <span className="ml-1 sm:ml-2">{currentPeriodReport ? 'Regerar' : 'Gerar'}</span>
              </Button>
            )}
          </div>
        </div>
      </div>

      {loading && (
        <ReportGenerationLoading step={loadingStep} studentName={student.nome_completo} />
      )}

      <ReportEditorModal
        isOpen={isEditorOpen}
        onClose={closeEditor}
        onSave={handleSaveReport}
        reportData={generatedReport}
        studentName={student.nome_completo}
        period={generatedReport?.period}
      />

      <ViewReportModal
        isOpen={isViewModalOpen}
        onClose={() => setIsViewModalOpen(false)}
        reportData={currentPeriodReport}
        studentName={student.nome_completo}
        studentId={student.id}
        turmaId={student.turma_id}
        turmaName={student.turma_nome}
        onReportUpdated={refreshExistingReports}
      />
    </>
  );
}

export default ReportHeader;