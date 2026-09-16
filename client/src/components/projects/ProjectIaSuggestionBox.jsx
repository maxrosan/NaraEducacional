import React from 'react';
import { motion } from 'framer-motion';
import { Button } from '@/components/ui/button';
import { BrainCircuit, Check, Pencil, X } from 'lucide-react';

export const ProjectIaSuggestionBox = ({ suggestion, onUse, onEdit, onCancel }) => {
  if (!suggestion) return null;

  return (
    <motion.div
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
      transition={{ duration: 0.3 }}
      className="mt-2"
    >
      <div className="bg-lavanda-claro p-4 rounded-lg border border-roxo-principal/30">
        <div className="flex items-start gap-3">
          <BrainCircuit className="h-6 w-6 text-roxo-principal flex-shrink-0 mt-1" />
          <div className="flex-grow">
            <h4 className="font-bold text-texto-escuro">Sugestão da IA:</h4>
            <p className="text-sm text-texto-medio mt-1">{suggestion}</p>
          </div>
        </div>
        <div className="flex justify-end gap-2 mt-4">
          <Button size="sm" variant="ghost" onClick={onCancel} className="text-texto-medio">
            <X className="h-4 w-4 mr-1" />
            Cancelar
          </Button>
          <Button size="sm" variant="outline" onClick={onEdit}>
            <Pencil className="h-3 w-3 mr-1" />
            Editar
          </Button>
          <Button size="sm" className="bg-roxo-principal hover:bg-roxo-principal/90" onClick={onUse}>
            <Check className="h-4 w-4 mr-1" />
            Usar sugestão
          </Button>
        </div>
      </div>
    </motion.div>
  );
};