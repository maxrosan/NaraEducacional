import React, { useState, useEffect, useCallback } from 'react';
import { Helmet } from 'react-helmet-async';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { apiClient } from '@/lib/apiClient';
import { useAuth } from '@/contexts/AuthContext';
import { useToast } from '@/components/ui/use-toast';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { ArrowLeft, FileText, User, Loader2, ChevronRight } from 'lucide-react';
import ProfessorNavbar from '@/components/teacher/ProfessorNavBar';

const ReportSelectionPage = () => {
  const navigate = useNavigate();
  const { toast } = useToast();
  const { user, turmaAtiva } = useAuth();
  const [turmas, setTurmas] = useState([]);
  const [criancas, setCriancas] = useState([]);
  const [selectedTurma, setSelectedTurma] = useState('');
  const [loading, setLoading] = useState(true);
  const [loadingCriancas, setLoadingCriancas] = useState(false);
  const [showTurmaSelect, setShowTurmaSelect] = useState(false);

  const fetchCriancas = useCallback(async (turmaId) => {
    if (!turmaId) {
      setCriancas([]);
      return;
    }
    setLoadingCriancas(true);
    try {
      const { data, error } = await apiClient
        .from('criancas')
        .select('id, nome_completo')
        .eq('turma_id', turmaId)
        .order('nome_completo');
      if (error) throw error;
      setCriancas(data);
    } catch (error) {
      toast({ variant: 'destructive', title: 'Erro ao buscar crianças', description: error.message });
    } finally {
      setLoadingCriancas(false);
    }
  }, [toast]);

  const handleTurmaChange = useCallback((turmaId) => {
    setSelectedTurma(turmaId);
    setCriancas([]);
    fetchCriancas(turmaId);
  }, [fetchCriancas]);

  const fetchTurmas = useCallback(async () => {
    if (!user) return;
    setLoading(true);
    try {
      const { data: userTurmasData, error: userTurmasError } = await apiClient
        .from('usuario_turmas')
        .select('turma_id')
        .eq('usuario_id', user.id);

      if (userTurmasError) throw userTurmasError;

      const turmaIds = userTurmasData.map(ut => ut.turma_id);
      if (turmaIds.length === 0) {
        setTurmas([]);
        setShowTurmaSelect(false);
        setLoading(false);
        return;
      }

      const { data: turmasData, error: turmasError } = await apiClient
        .from('turmas')
        .select('id, nome')
        .in('id', turmaIds);

      if (turmasError) throw turmasError;

      setTurmas(turmasData);

      setTurmas(turmasData);
      // Sempre usar turmaAtiva do contexto (ou primeira disponível)
      const turmaAlvo = turmasData.find(t => t.id === turmaAtiva?.id) || turmasData[0];
      setShowTurmaSelect(turmasData.length > 1);
      handleTurmaChange(turmaAlvo.id);

    } catch (error) {
      toast({ variant: 'destructive', title: 'Erro ao buscar turmas', description: error.message });
    } finally {
      setLoading(false);
    }
  }, [user, toast, handleTurmaChange, turmaAtiva]);

  useEffect(() => {
    fetchTurmas();
  }, [fetchTurmas]);

  useEffect(() => {
    if (!turmas.length) return;
    if (turmaAtiva?.id && turmaAtiva.id !== selectedTurma) {
      handleTurmaChange(turmaAtiva.id);
    }
  }, [turmaAtiva?.id, turmas, selectedTurma, handleTurmaChange]);

  return (
    <>
      <Helmet>
        <title>NARA - Gerar Relatórios</title>
        <meta name="description" content="Selecione a turma e a criança para gerar o relatório." />
      </Helmet>
      <div className="bg-[#F5F3FA] min-h-screen">
        <ProfessorNavbar />

        <div className="bg-white border-b shadow-sm">
          <div className="container mx-auto px-4 sm:px-6 lg:px-8 py-4 flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Button variant="ghost" size="icon" onClick={() => navigate('/')}>
                <ArrowLeft className="h-6 w-6 text-gray-600" />
              </Button>
            </div>
            <h1 className="text-md font-bold text-gray-800 flex items-center gap-2"> Gerar Relatórios</h1>
          </div>
        </div>

        <main className="container mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}>
            <Card className="max-w-2xl mx-auto">
              <CardHeader>
                <CardTitle>Selecione a Criança</CardTitle>
              </CardHeader>
              <CardContent className="space-y-6">
                {loading ? (
                  <div className="flex justify-center items-center p-8"><Loader2 className="h-8 w-8 animate-spin text-roxo-principal" /></div>
                ) : (
                  <>
                    <div className="space-y-2">
                      <label className="font-medium">Crianças</label>
                      {loadingCriancas ? (
                        <div className="flex justify-center items-center p-4 border rounded-md"><Loader2 className="h-6 w-6 animate-spin text-roxo-principal" /></div>
                      ) : criancas.length > 0 ? (
                        <ul className="border rounded-md divide-y">
                          {criancas.map(crianca => (
                            <li key={crianca.id}>
                              <Button
                                variant="ghost"
                                className="w-full justify-between h-auto min-h-12 px-4 py-2"
                                onClick={() => navigate(`/relatorios/${crianca.id}`)}
                              >
                                <div className="flex items-start gap-3 text-left min-w-0">
                                  <User className="h-5 w-5 text-gray-500 flex-shrink-0 mt-0.5" />
                                  <span className="text-left break-words">{crianca.nome_completo}</span>
                                </div>
                                <ChevronRight className="h-5 w-5 text-gray-400 flex-shrink-0" />
                              </Button>
                            </li>
                          ))}
                        </ul>
                      ) : (
                        <div className="text-center p-8 border-2 border-dashed rounded-lg">
                          <p className="text-gray-500">
                            {selectedTurma ? 'Nenhuma criança encontrada nesta turma.' : 'Selecione uma turma para ver as crianças.'}
                          </p>
                        </div>
                      )}
                    </div>
                  </>
                )}
              </CardContent>
            </Card>
          </motion.div>
        </main>
      </div>
    </>
  );
};

export default ReportSelectionPage;