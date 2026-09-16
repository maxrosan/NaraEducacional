import React, { useState, useEffect, useCallback } from 'react';
import { Helmet } from 'react-helmet-async';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { ArrowLeft, Users, Save, Star, Loader2, Camera, CopyCheck as Checkbox, Brain, ToyBrick, Puzzle, Music, Globe } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { useToast } from '@/components/ui/use-toast';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Step } from '@/components/observations/Step';
import { FreeObservationBlock } from '@/components/observations/FreeObservationBlock';
import { useAuth } from '@/contexts/AuthContext';
import { apiClient } from '@/lib/apiClient';

import MusicForm from '@/components/specialist-observation/MusicForm';
import PsychomotricityForm from '@/components/specialist-observation/PsychomotricityForm';
import EnglishForm from '@/components/specialist-observation/EnglishForm';
import PsychologyForm from '@/components/specialist-observation/PsychologyForm';
import PsychoPedagogyForm from '@/components/specialist-observation/PsychoPedagogyForm';

const specialistProfiles = {
  'Música': { name: 'Música', component: MusicForm, icon: Music },
  'Psicomotricidade': { name: 'Psicomotricidade', component: PsychomotricityForm, icon: ToyBrick },
  'Inglês': { name: 'Inglês', component: EnglishForm, icon: Globe },
  'Psicologia': { name: 'Psicologia', component: PsychologyForm, icon: Brain },
  'Psicopedagogia': { name: 'Psicopedagogia', component: PsychoPedagogyForm, icon: Puzzle },
};

function SpecialistObservationPage() {
  const navigate = useNavigate();
  const { toast } = useToast();
  const { user } = useAuth();
  const [especialista, setEspecialista] = useState(null);
  const [loading, setLoading] = useState(true);
  const [turmas, setTurmas] = useState([]);
  const [criancas, setCriancas] = useState([]);
  const [selectedTurma, setSelectedTurma] = useState('');
  const [selectedCrianca, setSelectedCrianca] = useState('');
  const [integrateToReport, setIntegrateToReport] = useState(true);

  const SpecialistFormComponent = especialista?.tipo_especialista ? specialistProfiles[especialista.tipo_especialista]?.component : null;
  const SpecialistIcon = especialista?.tipo_especialista ? specialistProfiles[especialista.tipo_especialista]?.icon : Star;
  
  const fetchInitialData = useCallback(async () => {
    if (!user) return;
    setLoading(true);

    const { data: userData, error: userError } = await apiClient
      .from('usuarios')
      .select('id, nome, instituicao_id, tipo_especialista')
      .eq('id', user.id)
      .single();

    if (userError || !userData) {
      toast({ variant: 'destructive', title: 'Erro ao carregar dados do especialista.' });
      setLoading(false);
      return;
    }
    setEspecialista(userData);

    const { data: turmasData, error: turmasError } = await apiClient
      .from('turmas')
      .select('id, nome, faixa_etaria')
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
    setSelectedCrianca('');
    if (!turmaId) {
      setCriancas([]);
      return;
    }
    const { data, error } = await apiClient
      .from('criancas')
      .select('id, nome_completo')
      .eq('turma_id', turmaId);
    
    if (error) {
      toast({ variant: 'destructive', title: 'Erro ao buscar crianças da turma.' });
    } else {
      setCriancas(data);
    }
  };

  const handleSave = () => {
    if (!selectedTurma || !selectedCrianca) {
      toast({
        title: '⚠️ Campos obrigatórios',
        description: 'Por favor, selecione a turma e a criança.',
        variant: 'destructive',
      });
      return;
    }
    toast({
      title: '🚧 Funcionalidade em construção!',
      description: 'A lógica para salvar os dados do formulário ainda será implementada.',
    });
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center h-screen">
        <Loader2 className="h-8 w-8 animate-spin" />
      </div>
    );
  }

  return (
    <>
      <Helmet>
        <title>NARA - Registro de Especialista</title>
        <meta name="description" content="Registre sua observação especializada." />
      </Helmet>

      <div className="bg-[#F5F3FA] min-h-screen">
        <header className="sticky top-0 bg-white/80 backdrop-blur-sm z-10 shadow-sm">
          <div className="container mx-auto px-4 sm:px-6 lg:px-8 py-4 flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Button variant="ghost" size="icon" onClick={() => navigate(-1)}>
                <ArrowLeft className="h-6 w-6 text-gray-600" />
              </Button>
              <h1 className="text-xl font-bold text-gray-800">Registro de Especialista ({especialista?.tipo_especialista})</h1>
            </div>
            <img  alt="NARA icon logo" className="h-12 w-auto sm:h-14" src="/nara-logo.png" />
          </div>
        </header>

        <main className="container mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <Step title="Seleção Inicial" icon={<Users className="h-5 w-5" />}>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <Select onValueChange={handleTurmaChange} value={selectedTurma}>
                <SelectTrigger><SelectValue placeholder="Selecione a turma" /></SelectTrigger>
                <SelectContent>
                  {turmas.map((turma) => (
                    <SelectItem key={turma.id} value={turma.id}>{turma.nome}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Select onValueChange={setSelectedCrianca} value={selectedCrianca} disabled={!selectedTurma}>
                <SelectTrigger><SelectValue placeholder="Selecione a criança" /></SelectTrigger>
                <SelectContent>
                  {criancas.map(student => (
                     <SelectItem key={student.id} value={student.id}>{student.nome_completo}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </Step>
          
          <AnimatePresence>
          {selectedTurma && selectedCrianca && (
            <>
              <Step title={`Registro de ${especialista?.tipo_especialista || 'Especialista'}`} icon={<SpecialistIcon className="h-5 w-5" />}>
                {SpecialistFormComponent && <SpecialistFormComponent turmaNivel={turmas.find(t => t.id === selectedTurma)?.faixa_etaria} />}
              </Step>
              
              <Step title="Mídias Complementares" icon={<Camera className="h-5 w-5" />}>
                <FreeObservationBlock students={criancas} />
              </Step>
              
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5, delay: 0.2 }}
                className="mt-8 flex flex-col items-center gap-4"
              >
                <div className="flex items-center space-x-2 bg-white p-3 rounded-lg">
                    <Checkbox id="integrate" checked={integrateToReport} onCheckedChange={setIntegrateToReport} />
                    <Label htmlFor="integrate">Integrar ao relatório bimestral da criança.</Label>
                </div>
                <Button
                  size="lg"
                  className="bg-[#C3ECD4] hover:bg-[#B0E4C1] text-gray-800 font-bold rounded-full w-full max-w-md btn-hover"
                  onClick={handleSave}
                >
                  <Save className="h-5 w-5 mr-2" />
                  Salvar Observação
                </Button>
              </motion.div>
            </>
          )}
          </AnimatePresence>
        </main>
      </div>
    </>
  );
}

export default SpecialistObservationPage;
