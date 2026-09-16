import React, { useState, useEffect, useCallback } from 'react';
import { Helmet } from 'react-helmet-async';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { ArrowLeft, User, Save, Sparkles, CheckCircle, Loader2, Users } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useToast } from '@/components/ui/use-toast';
import { Textarea } from '@/components/ui/textarea';
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { apiClient } from '@/lib/apiClient';
import { useAuth } from '@/contexts/AuthContext';

function SpecialistReportPage() {
  const navigate = useNavigate();
  const { toast } = useToast();
  const { user } = useAuth();

  const [especialista, setEspecialista] = useState(null);
  const [turmas, setTurmas] = useState([]);
  const [selectedTurma, setSelectedTurma] = useState('');
  const [students, setStudents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadingStudents, setLoadingStudents] = useState(false);

  const fetchInitialData = useCallback(async () => {
    if (!user) return;
    setLoading(true);

    const { data: userData, error: userError } = await apiClient
      .from('usuarios')
      .select('id, nome, instituicao_id, tipo_especialista')
      .eq('id', user.id)
      .single();

    if (userError || !userData) {
      toast({ variant: 'destructive', title: 'Erro', description: 'Não foi possível carregar dados do especialista.' });
      setLoading(false);
      return;
    }
    setEspecialista(userData);

    const { data: turmasData, error: turmasError } = await apiClient
      .from('turmas')
      .select('id, nome')
      .eq('instituicao_id', userData.instituicao_id);

    if (turmasError) {
      toast({ variant: 'destructive', title: 'Erro ao buscar turmas.' });
    } else {
      setTurmas(turmasData);
    }

    setLoading(false);
  }, [user, toast]);

  useEffect(() => {
    fetchInitialData();
  }, [fetchInitialData]);

  const handleTurmaChange = async (turmaId) => {
    setSelectedTurma(turmaId);
    if (!turmaId) {
      setStudents([]);
      return;
    }
    setLoadingStudents(true);
    const { data: criancasData, error } = await apiClient
      .from('criancas')
      .select('id, nome_completo')
      .eq('turma_id', turmaId);

    if (error) {
      toast({ variant: 'destructive', title: 'Erro ao buscar alunos.' });
      setStudents([]);
    } else {
      // Idealmente, buscaríamos as observações salvas aqui.
      const studentsWithObservation = criancasData.map(c => ({ ...c, observation: '', saved: false }));
      setStudents(studentsWithObservation);
    }
    setLoadingStudents(false);
  };
  
  const handleObservationChange = (studentId, text) => {
    setStudents(prev => 
      prev.map(s => s.id === studentId ? { ...s, observation: text, saved: false } : s)
    );
  };

  const handleSave = (studentId) => {
    const student = students.find(s => s.id === studentId);
    // Aqui iria a lógica para salvar no banco via API (tabela `observacoes_especialistas` ou similar)
    console.log('Salvando observação:', student?.observation);
    setStudents(prev => 
      prev.map(s => s.id === studentId ? { ...s, saved: true } : s)
    );
    toast({
      title: '✅ Observação salva!',
      description: 'Sua contribuição foi registrada com sucesso.',
      className: 'bg-green-100 border-green-300 text-green-800',
    });
  };
  
  const handleAISuggestion = (studentId) => {
    toast({
      title: '🚧 Funcionalidade em construção',
      description: 'A sugestão da IA será implementada em breve!',
    });
  };

  if (loading) {
    return <div className="flex items-center justify-center h-screen"><Loader2 className="h-8 w-8 animate-spin" /></div>;
  }

  return (
    <>
      <Helmet>
        <title>NARA - Relatório do Especialista</title>
        <meta name="description" content="Registre suas observações para as turmas." />
      </Helmet>

      <div className="bg-[#F5F3FA] min-h-screen">
        <header className="sticky top-0 bg-white/80 backdrop-blur-sm z-20 shadow-sm">
          <div className="container mx-auto px-4 sm:px-6 lg:px-8 py-4 flex items-center justify-between">
            <div className="flex items-center gap-2 sm:gap-4">
              <Button variant="ghost" size="icon" onClick={() => navigate(-1)}>
                <ArrowLeft className="h-6 w-6 text-gray-600" />
              </Button>
              <div>
                 <h1 className="text-lg sm:text-xl font-bold text-gray-800">Relatórios do Especialista</h1>
                 <p className="text-xs sm:text-sm text-gray-500">{especialista?.tipo_especialista}</p>
              </div>
            </div>
            <img  alt="NARA icon logo" className="h-12 w-auto sm:h-14" src="/nara-logo.png" />
          </div>
        </header>

        <main className="container mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <motion.div 
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-white p-6 rounded-2xl shadow-lg border border-gray-100 mb-8"
          >
            <h2 className="text-xl font-bold text-gray-800">Olá, {especialista?.nome}!</h2>
            <p className="text-gray-600 mt-1">Selecione uma turma para adicionar suas observações para o relatório bimestral.</p>
             <Select onValueChange={handleTurmaChange} value={selectedTurma}>
                <SelectTrigger className="mt-4 max-w-sm">
                    <SelectValue placeholder="Selecione a turma" />
                </SelectTrigger>
                <SelectContent>
                    {turmas.map(turma => (
                        <SelectItem key={turma.id} value={turma.id}>{turma.nome}</SelectItem>
                    ))}
                </SelectContent>
            </Select>
          </motion.div>

          {loadingStudents ? (
             <div className="flex items-center justify-center py-10"><Loader2 className="h-8 w-8 animate-spin" /></div>
          ) : selectedTurma && (
            <Accordion type="single" collapsible className="w-full space-y-4">
              {students.map((student, index) => (
                <motion.div
                  key={student.id}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.5, delay: index * 0.05 }}
                >
                  <AccordionItem value={`item-${student.id}`} className="bg-white rounded-2xl shadow-md border border-gray-100 overflow-hidden">
                    <AccordionTrigger className="px-6 py-4 hover:no-underline">
                      <div className="flex items-center justify-between w-full">
                        <div className="flex items-center gap-3">
                          <div className="bg-gray-100 p-2 rounded-full">
                            <User className="h-5 w-5 text-gray-600" />
                          </div>
                          <span className="font-bold text-gray-800">{student.nome_completo}</span>
                        </div>
                        {student.saved && (
                          <div className="flex items-center gap-1 text-xs text-green-600 bg-green-100 px-2 py-1 rounded-full">
                            <CheckCircle className="h-4 w-4" />
                            <span>Salvo</span>
                          </div>
                        )}
                      </div>
                    </AccordionTrigger>
                    <AccordionContent className="px-6 pb-6">
                      <Textarea
                        placeholder="Descreva aqui suas observações sobre o desenvolvimento da criança em sua área..."
                        value={student.observation}
                        onChange={(e) => handleObservationChange(student.id, e.target.value)}
                        className="min-h-[100px] text-base"
                        rows={4}
                      />
                      <div className="flex justify-end gap-2 mt-4">
                        <Button variant="ghost" onClick={() => handleAISuggestion(student.id)}>
                          <Sparkles className="h-4 w-4 mr-2" />
                          Sugestão IA
                        </Button>
                        <Button className="bg-[#C3ECD4] hover:bg-[#B0E4C1] text-gray-800 font-bold btn-hover" onClick={() => handleSave(student.id)}>
                          <Save className="h-4 w-4 mr-2" />
                          Salvar
                        </Button>
                      </div>
                    </AccordionContent>
                  </AccordionItem>
                </motion.div>
              ))}
            </Accordion>
          )}
        </main>
      </div>
    </>
  );
}

export default SpecialistReportPage;
