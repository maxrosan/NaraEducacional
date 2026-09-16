import React from 'react';
import { motion } from 'framer-motion';
import { Button } from '@/components/ui/button';
import { BrainCircuit, Check, Pencil, X } from 'lucide-react';

export const IaSuggestionBox = ({ suggestion, onUse, onEdit, onClose }) => {
  if (!suggestion) return null;

  return (
    <motion.div
      initial={{ opacity: 0, height: 0 }}
      animate={{ opacity: 1, height: 'auto' }}
      exit={{ opacity: 0, height: 0 }}
      transition={{ duration: 0.3 }}
      className="mt-2 overflow-hidden"
    >
      <div className="bg-lavanda-claro p-4 rounded-lg border border-verde-menta">
        <div className="flex items-start gap-3">
          <BrainCircuit className="h-5 w-5 text-roxo-principal flex-shrink-0 mt-1" />
          <div className="flex-grow">
            <h4 className="font-bold text-texto-escuro">Sugestão da IA:</h4>
            <p className="text-sm text-texto-medio mt-1">{suggestion}</p>
          </div>
        </div>
        <div className="flex justify-end gap-2 mt-3">
          {onClose && (
            <Button size="sm" variant="ghost" onClick={onClose} className="text-texto-medio">
              <X className="h-3 w-3 mr-1" />
              Cancelar
            </Button>
          )}
          <Button size="sm" variant="ghost" onClick={onEdit} className="text-texto-medio">
            <Pencil className="h-3 w-3 mr-1" />
            Editar
          </Button>
          <Button size="sm" className="bg-verde-menta/80 hover:bg-verde-menta text-texto-escuro" onClick={onUse}>
            <Check className="h-4 w-4 mr-1" />
            Usar sugestão
          </Button>
        </div>
      </div>
    </motion.div>
  );
};