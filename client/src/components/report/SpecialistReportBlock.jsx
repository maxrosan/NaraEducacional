import React, { useMemo } from 'react';
import { motion } from 'framer-motion';
import { BrainCircuit, Music, ToyBrick, Languages } from 'lucide-react';
import { Textarea } from '@/components/ui/textarea';
import EmptyContent from '@/components/reports/EmptyContent';

const SpecialistReportBlock = ({ reports, onReportChange }) => {
  const icons = { 'Música': <Music />, 'Psicomotricidade': <ToyBrick />, 'Inglês': <Languages /> };
  const hasReports = useMemo(() => Object.values(reports).some(r => r.trim() !== ''), [reports]);
  
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.4 }}
      className="bg-white p-6 rounded-2xl shadow-md border border-gray-100"
    >
      <div className="flex items-center gap-3 mb-4">
        <div className="bg-lavanda-claro p-2 rounded-full"><BrainCircuit className="h-5 w-5 text-roxo-principal" /></div>
        <h3 className="text-lg font-bold text-texto-escuro">Registros dos Especialistas</h3>
      </div>
      {!hasReports ? <EmptyContent /> : (
        <div className="space-y-4">
          {Object.entries(reports).map(([specialist, text]) => (
            <div key={specialist}>
              <label className="font-semibold text-sm flex items-center gap-2 mb-1">{icons[specialist]} {specialist}</label>
              <Textarea value={text} onChange={(e) => onReportChange(specialist, e.target.value)} placeholder={`Cole ou digite o relato de ${specialist}...`} className="bg-gray-50" />
            </div>
          ))}
        </div>
      )}
    </motion.div>
  );
};

export default SpecialistReportBlock;