import React from 'react';
import { motion } from 'framer-motion';
import { Brain } from 'lucide-react';
import { Label } from '@/components/ui/label';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { Textarea } from '@/components/ui/textarea';
import { Input } from '@/components/ui/input';

const questions = [
  { id: 'q1', text: 'Estado emocional predominante:', options: ['Alegre', 'Ansioso', 'Agressivo', 'Triste', 'Neutro'] },
  { id: 'q2', text: 'Houve conflitos ou isolamento?', options: ['Sim', 'Não', 'Não observado'] },
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
        <Label key={option} className="flex items-center space-x-2 cursor-pointer bg-white p-3 rounded-lg border-2 border-transparent has-[:checked]:border-red-300">
          <RadioGroupItem value={option.toLowerCase()} id={`${question.id}-${option}`} />
          <span>{option}</span>
        </Label>
      ))}
    </RadioGroup>
  </motion.div>
);

const PsychologyForm = () => {
  return (
    <div className="space-y-6">
      <h3 className="text-lg font-bold text-gray-800 flex items-center gap-2">
        <Brain className="h-5 w-5 text-red-600" />
        Registro de Psicologia
      </h3>
      {questions.map((q, index) => <FormRow key={q.id} question={q} index={index} />)}
      <div>
        <Label htmlFor="psycho-behaviors" className="font-semibold text-gray-700">Comportamentos a acompanhar:</Label>
        <Input id="psycho-behaviors" placeholder="Ex: Dificuldade em esperar a vez, morde objetos..." className="mt-2 bg-white" />
      </div>
      <div>
        <Label htmlFor="psycho-complementary" className="font-semibold text-gray-700">Observação complementar:</Label>
        <Textarea id="psycho-complementary" placeholder="Descreva aqui outros pontos relevantes..." className="mt-2" />
      </div>
    </div>
  );
};

export default PsychologyForm;