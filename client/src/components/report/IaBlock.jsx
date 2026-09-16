import React from 'react';
import { motion } from 'framer-motion';
import { Pencil, RotateCw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import EmptyContent from '@/components/reports/EmptyContent';

const IaBlock = ({ title, content, onContentChange, icon, badgeText, onEdit, onRegenerate, isPlaceholder }) => {
  if (isPlaceholder) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="bg-white p-6 rounded-2xl shadow-md border border-gray-100"
      >
        <div className="flex justify-between items-start mb-4">
          <div className="flex items-center gap-3">
            <div className="bg-lavanda-claro p-2 rounded-full">{icon}</div>
            <h3 className="text-lg font-bold text-texto-escuro">{title}</h3>
          </div>
        </div>
        <EmptyContent />
      </motion.div>
    );
  }
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
      className="bg-white p-6 rounded-2xl shadow-md border border-gray-100"
    >
      <div className="flex justify-between items-start mb-4">
        <div className="flex items-center gap-3">
          <div className="bg-lavanda-claro p-2 rounded-full">{icon}</div>
          <h3 className="text-lg font-bold text-texto-escuro">{title}</h3>
        </div>
        <Badge variant="outline" className="border-lavanda text-roxo-principal bg-lavanda-claro">{badgeText}</Badge>
      </div>
      <Textarea value={content} onChange={(e) => onContentChange(e.target.value)} className="min-h-[100px] bg-gray-50" />
      <div className="flex justify-end gap-2 mt-3">
        <Button variant="ghost" size="sm" onClick={onEdit}><Pencil className="h-3 w-3 mr-2" /> Editar</Button>
        <Button variant="ghost" size="sm" onClick={onRegenerate} disabled><RotateCw className="h-3 w-3 mr-2" /> Regerar com IA</Button>
      </div>
    </motion.div>
  );
};

export default IaBlock;