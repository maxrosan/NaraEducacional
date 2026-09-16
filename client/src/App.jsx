import React, { useState } from 'react';
import { Routes, Route, useLocation } from 'react-router-dom';
import LoginPage from '@/pages/LoginPage';
import ProfessorHomePage from '@/pages/ProfessorHomePage';
import NewObservationPage from '@/pages/NewObservationPage';
import PlanningPage from '@/pages/PlanningPage';
import PortfolioPage from '@/pages/PortfolioPage';
import PortfoliosPage from '@/pages/PortfoliosPage';
import PortfolioTimelinePage from '@/pages/PortfolioTimelinePage';
import ReportSelectionPage from '@/pages/ReportSelectionPage';
import BimonthlyReportPage from '@/pages/BimonthlyReportPage';
import SpecialistReportPage from '@/pages/SpecialistReportPage';
import CoordinatorHomePage from '@/pages/CoordinatorHomePage';
import CoordinatorLayout from '@/components/coordinator/v2/CoordinatorLayout';
import PulsoDaEscolaPage from '@/pages/coordenacao/PulsoDaEscolaPage';
import PlanejamentosPage from '@/pages/coordenacao/PlanejamentosPage';
import RelatoriosPage from '@/pages/coordenacao/RelatoriosPage';
import TemplatesListPage from '@/pages/coordenacao/TemplatesListPage';
import TemplateEscolherModeloPage from '@/pages/coordenacao/TemplateEscolherModeloPage';
import TemplateEditorPage from '@/pages/coordenacao/TemplateEditorPage';
import ProfessorasPage from '@/pages/coordenacao/ProfessorasPage';
import AtencaoPedagogicaPage from '@/pages/coordenacao/AtencaoPedagogicaPage';
import AprendizagensPage from '@/pages/coordenacao/AprendizagensPage';
import TurmasPage from '@/pages/coordenacao/TurmasPage';
import TurmaDetalhePage from '@/pages/coordenacao/TurmaDetalhePage';
import CriancaPage from '@/pages/coordenacao/CriancaPage';
import BnccPorTurmaPage from '@/pages/coordenacao/BnccPorTurmaPage';
import AlfabetizacaoPage from '@/pages/coordenacao/AlfabetizacaoPage';
import AreaDoProfessorPage from '@/pages/coordenacao/AreaDoProfessorPage';
import PlaceholderPage from '@/pages/coordenacao/PlaceholderPage';
import SpecialistHomePage from '@/pages/SpecialistHomePage';
import IndicatorsPage from '@/pages/IndicatorsPage';
import AdminPage from '@/pages/AdminPage';
import BnccQuestionsPage from '@/pages/BnccQuestionsPage';
import GuidedObservationPage from '@/pages/GuidedObservationPage';
import RecordingPage from '@/pages/RecordingPage';
import ProjectsPage from '@/pages/ProjectsPage';
import NotificationDetailPage from '@/pages/NotificationDetailPage';
import FeedbackModal from '@/components/coordinator/FeedbackModal';
import ProtectedRoute from '@/components/ProtectedRoute';
import { toast } from '@/components/ui/use-toast';
import ForgotPasswordPage from '@/pages/ForgotPasswordPage';
import ResetPasswordPage from '@/pages/ResetPasswordPage';
import InstallPWAButton from '@/components/pwa/InstallPWAButton';
import BiometricSetupPrompt from '@/components/auth/BiometricSetupPrompt';
import AppLockScreen from '@/components/auth/AppLockScreen';
import { useAuth } from '@/contexts/AuthContext';

// Fluxo novo do especialista (substitui SpecialistObservationPage)
import SpecialistChildProfilePage from '@/pages/SpecialistChildProfilePage';
import SpecialistRegistrationPage from '@/pages/SpecialistRegistrationPage';
import SpecialistCreatePAEEPage from '@/pages/SpecialistCreatePAEEPage';
import SpecialistVoiceRecordsPage from './pages/SpecialistVoiceRecordsPage';

import * as Sentry from "@sentry/react";

function App() {
  const [isFeedbackModalOpen, setFeedbackModalOpen] = useState(false);
  const [feedbackContext, setFeedbackContext] = useState({ teacher: '', type: '' });
  const location = useLocation();
  const { user } = useAuth();

  const handleOpenFeedbackModal = (teacher, type) => {
    setFeedbackContext({ teacher, type });
    setFeedbackModalOpen(true);
  };

  const handleCloseFeedbackModal = () => {
    setFeedbackModalOpen(false);
  };

  const coordinatorHomePageElement = (
    <CoordinatorHomePage onOpenFeedbackModal={handleOpenFeedbackModal} />
  );

  return (
    <>
      <FeedbackModal
        isOpen={isFeedbackModalOpen}
        onClose={handleCloseFeedbackModal}
        teacherName={feedbackContext.teacher}
        feedbackType={feedbackContext.type}
      />

      {/*
        Renderizado uma única vez aqui, fora das rotas, para não remontar
        (e re-registrar os listeners de beforeinstallprompt) a cada navegação.
        Só aparece quando há usuário logado — nunca na tela de login.
      */}
      {user && <InstallPWAButton />}
      {user && <BiometricSetupPrompt />}
      {user && <AppLockScreen />}

      <Sentry.ErrorBoundary
        onError={(error, componentStack, eventId) => {
          console.error('[Sentry ErrorBoundary]', { error, componentStack, eventId });
        }}
        fallback={({ error, resetError }) => (
          <div className="flex flex-col items-center justify-center min-h-screen gap-4">
            <p className="text-lg text-red-600">Algo deu errado ao carregar esta página.</p>
            <button
              onClick={() => { resetError(); window.location.href = '/'; }}
              className="px-4 py-2 bg-roxo-principal text-white rounded"
            >
              Voltar ao início
            </button>
          </div>
        )}
      >

        <Routes>
          {/* Rota pública - Login */}
          <Route path="/" element={<LoginPage />} />
          <Route path="/login" element={<LoginPage />} />

          {/* Rotas protegidas - Admin */}
          <Route path="/admin" element={
            <ProtectedRoute allowedRoles={['admin']}>
              <AdminPage />
            </ProtectedRoute>
          } />

          <Route path="/admin/:tab" element={
            <ProtectedRoute allowedRoles={['admin']}>
              <AdminPage />
            </ProtectedRoute>
          } />

          <Route path="/admin/perguntas-bncc" element={
            <ProtectedRoute allowedRoles={['admin']}>
              <BnccQuestionsPage />
            </ProtectedRoute>
          } />

          {/* Rotas protegidas - Professor */}
          <Route path="/home-professor" element={<ProtectedRoute><ProfessorHomePage /></ProtectedRoute>} />
          <Route path="/registro" element={<ProtectedRoute><NewObservationPage /></ProtectedRoute>} />
          <Route path="/registro/:turmaId" element={<ProtectedRoute><NewObservationPage /></ProtectedRoute>} />
          <Route path="/gravacao" element={<ProtectedRoute><RecordingPage /></ProtectedRoute>} />
          <Route path="/registro-guiado/:turmaId" element={<ProtectedRoute><GuidedObservationPage /></ProtectedRoute>} />
          <Route path="/planejamento/semanal" element={<ProtectedRoute><PlanningPage /></ProtectedRoute>} />
          <Route path="/planejamento/semanal/:turmaId" element={<ProtectedRoute><PlanningPage /></ProtectedRoute>} />
          <Route path="/projetos" element={<ProtectedRoute><ProjectsPage /></ProtectedRoute>} />
          <Route path="/portfolios" element={<ProtectedRoute><PortfoliosPage /></ProtectedRoute>} />
          <Route path="/portfolio/:studentId" element={<ProtectedRoute><PortfolioPage /></ProtectedRoute>} />
          <Route path="/portfolio-timeline/:studentId" element={<ProtectedRoute><PortfolioTimelinePage /></ProtectedRoute>} />
          <Route path="/relatorios" element={<ProtectedRoute><ReportSelectionPage /></ProtectedRoute>} />
          <Route path="/relatorios/:studentId" element={<ProtectedRoute><BimonthlyReportPage /></ProtectedRoute>} />
          <Route path="/professor/indicadores/:turmaId" element={<ProtectedRoute><IndicatorsPage /></ProtectedRoute>} />
          <Route path="/notificacoes" element={<ProtectedRoute><NotificationDetailPage /></ProtectedRoute>} />

          {/* Rotas protegidas - Especialista */}
          <Route path="/especialistas" element={<ProtectedRoute><SpecialistHomePage /></ProtectedRoute>} />
          <Route path="/especialistas/registros-voz" element={<SpecialistVoiceRecordsPage />} />
          <Route path="/especialistas/registrar" element={<SpecialistRegistrationPage />} />
          <Route path="/especialistas/paee/criar" element={<ProtectedRoute><SpecialistCreatePAEEPage /></ProtectedRoute>} />

          {/* Fluxo por criança (substitui o antigo /observacoes-especialista e /registro-especialista) */}
          <Route path="/especialistas/crianca/:criancaId" element={<ProtectedRoute><SpecialistChildProfilePage /></ProtectedRoute>} />
          <Route path="/especialistas/crianca/:criancaId/registrar" element={<ProtectedRoute><SpecialistRegistrationPage /></ProtectedRoute>} />
          <Route path="/especialistas/crianca/:criancaId/paee/criar" element={<ProtectedRoute><SpecialistCreatePAEEPage /></ProtectedRoute>} />

          {/* Contribuição para o relatório bimestral — fluxo existente, não alterado */}
          <Route path="/contribuicao-relatorio" element={<ProtectedRoute><SpecialistReportPage /></ProtectedRoute>} />
          <Route path="/relatorios-especialista/:turmaId" element={<ProtectedRoute><SpecialistReportPage /></ProtectedRoute>} />

          {/* Rotas protegidas - Coordenador (NOVO layout NARAEDU, tela a tela) */}
          <Route path="/coordenacao" element={<ProtectedRoute allowedRoles={['admin', 'coordenador']}><CoordinatorLayout /></ProtectedRoute>}>
            <Route index element={<PulsoDaEscolaPage />} />
            <Route path="planejamentos" element={<PlanejamentosPage />} />
            <Route path="relatorios" element={<RelatoriosPage />} />
            <Route path="templates" element={<TemplatesListPage />} />
            <Route path="templates/escolher-modelo" element={<TemplateEscolherModeloPage />} />
            <Route path="templates/nova" element={<TemplateEditorPage />} />
            <Route path="templates/:templateId" element={<TemplateEditorPage />} />
            <Route path="turmas" element={<TurmasPage />} />
            <Route path="turmas/:turmaId" element={<TurmaDetalhePage />} />
            <Route path="professoras" element={<ProfessorasPage />} />
            <Route path="area-do-professor" element={<AreaDoProfessorPage />} />
            <Route path="atencao" element={<AtencaoPedagogicaPage />} />
            <Route path="aprendizagens" element={<AprendizagensPage />} />
            <Route path="bncc/:turmaId" element={<BnccPorTurmaPage />} />
            <Route path="alfabetizacao" element={<AlfabetizacaoPage />} />
            <Route path="alfabetizacao/:turmaId" element={<AlfabetizacaoPage />} />
            <Route path="crianca/:criancaId" element={<CriancaPage />} />
          </Route>
          {/* Layout antigo preservado para rollback/comparação durante a migração */}
          <Route path="/coordenacao-legacy" element={<ProtectedRoute allowedRoles={['admin', 'coordenador']}>{coordinatorHomePageElement}</ProtectedRoute>} />

          {/* Rotas públicas - Recuperação de senha */}
          <Route path="/esqueci-senha" element={<ForgotPasswordPage />} />
          <Route path="/redefinir-senha" element={<ResetPasswordPage />} />
        </Routes>
      </Sentry.ErrorBoundary>
    </>
  );
}

export default App;