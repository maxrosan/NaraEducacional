import React, { useState, useEffect } from 'react';
import { Helmet } from 'react-helmet-async';
import { useNavigate, useParams } from 'react-router-dom';
import { useToast } from '@/components/ui/use-toast';
import { BookOpen, MessageSquare, FileText } from 'lucide-react';
import ReportHeader from '@/components/report/ReportHeader';
import IaBlock from '@/components/report/IaBlock';
import WeeklyPlanningsBlock from '@/components/report/WeeklyPlanningsBlock';
import IndividualReportBlock from '@/components/report/IndividualReportBlock';
import ProductionAnalysisBlock from '@/components/report/ProductionAnalysisBlock';
import ReadingAnalysisBlock from '@/components/report/ReadingAnalysisBlock';
import PortfolioGalleryBlock from '@/components/report/PortfolioGalleryBlock';
import SpecialistReportBlock from '@/components/report/SpecialistReportBlock';
import SkillsMatrixBlock from '@/components/report/SkillsMatrixBlock';
import ReportsBlock from '@/components/report/ReportsBlock';
import ReportFooter from '@/components/report/ReportFooter';
import ProfessorNavbar from '@/components/teacher/ProfessorNavBar';
import { useAuth } from '@/contexts/AuthContext';
import { getCurrentBimester, fetchPeriodosAvaliativos } from '@/lib/dateUtils';
import { buscarCrianca, buscarInstituicao, listarTurmas } from '@/services/api';
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || import.meta.env.VITE_API_URL || '';
function BimonthlyReportPage() {
  const { studentId } = useParams();
  const navigate = useNavigate();
  const { toast } = useToast();
  const { user } = useAuth();
  const [loading, setLoading] = useState(true);
  const [student, setStudent] = useState(null);
  const [reportData, setReportData] = useState({});
  const [refreshReports, setRefreshReports] = useState(0);
  const [periodos, setPeriodos] = useState([]);
  const [selectedPeriodo, setSelectedPeriodo] = useState(null);
  const [portfolioItems, setPortfolioItems] = useState([]);
  const triggerReportsRefresh = () => {
    setRefreshReports(prev => prev + 1);
  };
  useEffect(() => {
    const fetchReportData = async () => {
      if (!studentId || !user) return;
      setLoading(true);
      try {
        const studentInfo = await buscarCrianca(studentId);
        if (!studentInfo) throw new Error('Criança não encontrada.');
        let turmaInfo = null;
        let instituicaoInfo = null;
        if (studentInfo.turma_id) {
          const turmas = await listarTurmas({ id: studentInfo.turma_id });
          turmaInfo = Array.isArray(turmas) ? turmas[0] : turmas;
          if (turmaInfo?.instituicao_id) {
            instituicaoInfo = await buscarInstituicao(turmaInfo.instituicao_id);
          }
        }
        if (!instituicaoInfo && studentInfo.instituicao_id) {
          instituicaoInfo = await buscarInstituicao(studentInfo.instituicao_id);
        }
        const instituicaoId = turmaInfo?.instituicao_id || studentInfo.instituicao_id;
        const bimesterObj = await getCurrentBimester(instituicaoId);
        const allPeriodos = await fetchPeriodosAvaliativos(instituicaoId);
        setPeriodos(allPeriodos);
        if (bimesterObj) {
          setSelectedPeriodo(bimesterObj);
        } else if (allPeriodos.length > 0) {
          setSelectedPeriodo(allPeriodos[allPeriodos.length - 1]);
        }
        setStudent({
          ...studentInfo,
          turma_nome: turmaInfo?.nome || '',
          logo_url: instituicaoInfo?.logo_url || '',
          periodo: bimesterObj?.descricao || 'Período não definido',
          instituicao_id: instituicaoId,
        });
        setReportData({
          introText: '',
          individualReport: '',
          productions: [],
          specialists: { 'Música': '', 'Psicomotricidade': '', 'Inglês': '' },
          skills: [],
          conclusion: '',
          sources: []
        });
      } catch (error) {
        toast({ variant: 'destructive', title: 'Erro ao carregar relatório', description: error.message });
        const fallback = user?.perfil === 'coordenador' ? '/coordenacao' : '/relatorios';
        navigate(fallback);
      } finally {
        setLoading(false);
      }
    };
    fetchReportData();
  }, [studentId, user, navigate, toast]);
  useEffect(() => {
    const fetchPortfolio = async () => {
      if (!student?.turma_id || !studentId || !selectedPeriodo) {
        setPortfolioItems([]);
        return;
      }
      try {
        const params = new URLSearchParams({
          turma_id: student.turma_id,
          crianca_id: studentId,
        });
        if (selectedPeriodo.data_inicio) params.set('data_inicio', selectedPeriodo.data_inicio);
        if (selectedPeriodo.data_fim) params.set('data_fim', selectedPeriodo.data_fim);
        const response = await fetch(`${API_BASE_URL}/api/portfolio/listar/?${params}`, {
          credentials: 'include',
        });
        if (!response.ok) throw new Error('Erro ao buscar portfólio');
        const data = await response.json();
        const items = (data.producoes || []).map(p => ({
          id: p.id,
          url: p.arquivo_url,
          tag: p.tags || p.tipo_midia || '',
        }));
        setPortfolioItems(items);
      } catch (err) {
        console.error('Erro ao carregar portfólio:', err);
        setPortfolioItems([]);
      }
    };
    fetchPortfolio();
  }, [student, studentId, selectedPeriodo]);
  const handleFieldChange = (field, value) => {
    setReportData(prev => ({ ...prev, [field]: value }));
  };
  const handleSpecialistChange = (specialist, value) => {
    setReportData(prev => ({
      ...prev,
      specialists: { ...prev.specialists, [specialist]: value }
    }));
  };
  if (loading) {
    return <div className="flex justify-center items-center h-screen">Carregando relatório...</div>;
  }
  if (!student) {
    return <div className="flex justify-center items-center h-screen">Não foi possível carregar os dados.</div>;
  }
  return (
    <>
      <Helmet>
        <title>Relatório Bimestral: {student.nome_completo}</title>
        <meta name="description" content={`Visualize e edite o relatório bimestral de ${student.nome_completo}.`} />
      </Helmet>
      <div className="bg-lavanda-claro pb-24">
        <ProfessorNavbar />
        <ReportHeader
          student={student}
          onReportSaved={triggerReportsRefresh}
          periodos={periodos}
          selectedPeriodo={selectedPeriodo}
          onPeriodoChange={setSelectedPeriodo}
        />
        <main className="container mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
          <WeeklyPlanningsBlock turmaId={student.turma_id} periodo={selectedPeriodo} />
          <IndividualReportBlock
            content={reportData.individualReport}
            onContentChange={(val) => handleFieldChange('individualReport', val)}
            sources={reportData.sources}
            isPlaceholder={!reportData.individualReport}
            nomeAluno={student.nome_completo}
            criancaId={studentId}
            periodo={selectedPeriodo}
          />
          <ProductionAnalysisBlock nomeAluno={student.nome_completo} periodo={selectedPeriodo} />
          <ReadingAnalysisBlock criancaId={studentId} periodo={selectedPeriodo} />
          <PortfolioGalleryBlock photos={portfolioItems} />
          <SpecialistReportBlock reports={reportData.specialists} onReportChange={handleSpecialistChange} />
          <SkillsMatrixBlock
            criancaId={studentId}
            turmaId={student?.turma_id}
            instituicaoId={student?.instituicao_id}
            selectedPeriodo={selectedPeriodo}
          />
          <IaBlock
            title="Conclusão da Professora"
            content={reportData.conclusion}
            onContentChange={(val) => handleFieldChange('conclusion', val)}
            icon={<MessageSquare className="h-5 w-5 text-roxo-principal" />}
            badgeText="Sugestão da IA"
            isPlaceholder={!reportData.conclusion}
          />
          <ReportsBlock
            studentId={studentId}
            studentName={student.nome_completo}
            turmaId={student.turma_id}
            turmaName={student.turma_nome}
            refreshTrigger={refreshReports}
            instituicaoId={student?.instituicao_id}
          />
        </main>
        <ReportFooter />
      </div>
    </>
  );
}
export default BimonthlyReportPage;