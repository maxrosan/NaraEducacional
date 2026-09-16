import React from 'react';
import { motion } from 'framer-motion';
import { Puzzle } from 'lucide-react';
import { Label } from '@/components/ui/label';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { Textarea } from '@/components/ui/textarea';
import { Checkbox } from '@/components/ui/checkbox';

const difficulties = ['Atenção', 'Memória', 'Linguagem', 'Organização'];
const interventionLevels = ['Alta', 'Média', 'Leve', 'Não interferiu'];

const PsychoPedagogyForm = () => {
  return (
    <div className="space-y-6">
      <h3 className="text-lg font-bold text-gray-800 flex items-center gap-2">
        <Puzzle className="h-5 w-5 text-orange-600" />
        Registro de Psicopedagogia
      </h3>
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0 }}>
        <Label className="font-semibold text-gray-700">Apresentou dificuldade em:</Label>
        <div className="flex flex-wrap gap-4 mt-2">
          {difficulties.map(item => (
            <Label key={item} className="flex items-center space-x-2 cursor-pointer bg-white p-3 rounded-lg border-2 border-gray-200">
              <Checkbox id={`diff-${item}`} />
              <span>{item}</span>
            </Label>
          ))}
        </div>
      </motion.div>
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}>
        <Label htmlFor="pedagogy-observation" className="font-semibold text-gray-700">Observação livre (áudio ou escrita)</Label>
        <Textarea id="pedagogy-observation" placeholder="Descreva aqui as dificuldades e potencialidades observadas..." className="mt-2" />
      </motion.div>
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}>
        <Label className="font-semibold text-gray-700">Nível de interferência pedagógica:</Label>
        <RadioGroup className="flex flex-wrap gap-4 mt-2">
          {interventionLevels.map(option => (
            <Label key={option} className="flex items-center space-x-2 cursor-pointer bg-white p-3 rounded-lg border-2 border-transparent has-[:checked]:border-orange-300">
              <RadioGroupItem value={option.toLowerCase()} id={`int-${option}`} />
              <span>{option}</span>
            </Label>
          ))}
        </RadioGroup>
      </motion.div>
    </div>
  );
};

export default PsychoPedagogyForm;