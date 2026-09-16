import React from 'react';
import { motion } from 'framer-motion';
import { ToyBrick } from 'lucide-react';
import { Label } from '@/components/ui/label';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { Textarea } from '@/components/ui/textarea';

const questions = [
  { id: 'q1', text: 'Demonstrou domínio corporal nas atividades propostas?', options: ['Sim', 'Parcial', 'Não'] },
  { id: 'q2', text: 'Houve equilíbrio, coordenação ou lateralidade observável?', options: ['Sim', 'Pouco', 'Não'] },
  { id: 'q3', text: 'Engajamento geral da criança:', options: ['Alto', 'Médio', 'Baixo', 'Não observável'] },
];

const FormRow = ({ question, index }) => (
  <motion.div
    initial={{ opacity: 0, y: 10 }}
    animate={{ opacity: 1, y: 0 }}
    transition={{ delay: index * 0.1 }}
  >
    <Label className="font-semibold text-gray-700">{question.text}</Label>
    <RadioGroup className="flex flex-wrap gap-4 mt-2">
      {question.options.map(option => (
        <Label key={option} className="flex items-center space-x-2 cursor-pointer bg-white p-3 rounded-lg border-2 border-transparent has-[:checked]:border-green-300">
          <RadioGroupItem value={option.toLowerCase()} id={`${question.id}-${option}`} />
          <span>{option}</span>
        </Label>
      ))}
    </RadioGroup>
  </motion.div>
);

const PsychomotricityForm = () => {
  return (
    <div className="space-y-6">
      <h3 className="text-lg font-bold text-gray-800 flex items-center gap-2">
        <ToyBrick className="h-5 w-5 text-green-600" />
        Registro de Psicomotricidade
      </h3>
      {questions.map((q, index) => <FormRow key={q.id} question={q} index={index} />)}
      <div>
        <Label htmlFor="psico-complementary" className="font-semibold text-gray-700">Observação complementar (opcional)</Label>
        <Textarea id="psico-complementary" placeholder="Descreva aqui outros pontos relevantes..." className="mt-2" />
      </div>
    </div>
  );
};

export default PsychomotricityForm;