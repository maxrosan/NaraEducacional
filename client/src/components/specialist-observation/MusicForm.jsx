import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Music, Loader2 } from 'lucide-react';
import { Label } from '@/components/ui/label';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { Textarea } from '@/components/ui/textarea';
import { apiClient } from '@/lib/apiClient';
import { getStandardizedFaixaEtaria } from '@/lib/observationUtils';
import { useToast } from '@/components/ui/use-toast';

const FormRow = ({ question, index, onAnswerChange }) => (
  <motion.div
    initial={{ opacity: 0, y: 10 }}
    animate={{ opacity: 1, y: 0 }}
    transition={{ delay: index * 0.1 }}
  >
    <Label className="font-semibold text-gray-700">{question.pergunta_facilitadora || question.pergunta}</Label>
    <RadioGroup 
      className="flex flex-wrap gap-4 mt-2"
      onValueChange={(value) => onAnswerChange(question.id, value)}
    >
      {['Sim', 'Parcialmente', 'Não'].map(option => (
        <Label key={option} className="flex items-center space-x-2 cursor-pointer bg-white p-3 rounded-lg border-2 border-transparent has-[:checked]:border-purple-300">
          <RadioGroupItem value={option} id={`${question.id}-${option}`} />
          <span>{option}</span>
        </Label>
      ))}
    </RadioGroup>
  </motion.div>
);

const MusicForm = ({ turmaNivel }) => {
  const { toast } = useToast();
  const [questions, setQuestions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [answers, setAnswers] = useState({});

  useEffect(() => {
    const fetchQuestions = async () => {
      if (!turmaNivel) return;
      setLoading(true);
      const nivelNormalizado = getStandardizedFaixaEtaria(turmaNivel);
      const { data, error } = await apiClient
        .from('perguntas_especialistas')
        .select('*')
        .ilike('nivel', `%${nivelNormalizado}%`)
        .eq('especialidade', 'Música');

      if (error) {
        toast({
          title: 'Erro ao buscar perguntas de música.',
          description: error.message,
          variant: 'destructive',
        });
        setQuestions([]);
      } else {
        setQuestions(data);
      }
      setLoading(false);
    };

    fetchQuestions();
  }, [turmaNivel, toast]);
  
  const handleAnswerChange = (questionId, value) => {
    setAnswers(prev => ({...prev, [questionId]: value}));
  };

  return (
    <div className="space-y-6">
      <h3 className="text-lg font-bold text-gray-800 flex items-center gap-2">
        <Music className="h-5 w-5 text-purple-600" />
        Registro de Música ({turmaNivel || 'Selecione a turma'})
      </h3>
      {loading ? (
        <div className="flex justify-center items-center py-8">
          <Loader2 className="h-8 w-8 animate-spin text-purple-500" />
        </div>
      ) : questions.length > 0 ? (
        questions.map((q, index) => <FormRow key={q.id} question={q} index={index} onAnswerChange={handleAnswerChange} />)
      ) : (
        <p className="text-center text-gray-500 py-8">Nenhuma pergunta de música encontrada para este nível. Verifique a configuração no painel administrativo.</p>
      )}
      <div>
        <Label htmlFor="music-complementary" className="font-semibold text-gray-700">Observação complementar (opcional)</Label>
        <Textarea id="music-complementary" placeholder="Descreva aqui outros pontos relevantes..." className="mt-2" />
      </div>
    </div>
  );
};

export default MusicForm;
