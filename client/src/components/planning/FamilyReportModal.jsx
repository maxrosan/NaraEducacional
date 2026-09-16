import React from 'react';
import { motion } from 'framer-motion';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Download, Calendar, Sun, Paintbrush, Music, ToyBrick, BookOpenCheck } from 'lucide-react';
import { useToast } from '@/components/ui/use-toast';
import { generateFamilyPlanningPdf } from '@/lib/pdfGenerator';
import { NARA_LOGO_URL } from '@/lib/branding';

const dayIcons = {
  segunda: <Sun className="h-5 w-5 text-yellow-500" />,
  terça: <Paintbrush className="h-5 w-5 text-blue-500" />,
  quarta: <Music className="h-5 w-5 text-red-500" />,
  quinta: <ToyBrick className="h-5 w-5 text-green-500" />,
  sexta: <BookOpenCheck className="h-5 w-5 text-purple-500" />,
};

const FamilyReportModal = ({ isOpen, onClose, reportData }) => {
  const { toast } = useToast();

  const handleDownload = async () => {
    if (!reportData) return;
    toast({
      title: '📥 PDF sendo gerado...',
      description: 'O download do seu arquivo começará em breve.',
      className: 'bg-green-100 border-green-300 text-green-800',
    });
    await generateFamilyPlanningPdf(reportData);
    onClose();
  };

  if (!reportData) return null;

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-3xl p-0 bg-[#F5F3FA] rounded-2xl overflow-hidden">
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}>
          <DialogHeader className="p-6 bg-white">
            <div className="flex items-center justify-between">
              <div>
                <DialogTitle className="text-2xl font-extrabold text-gray-800">Cronograma Semanal</DialogTitle>
                <DialogDescription className="flex items-center gap-4 mt-2 text-gray-500">
                  <span className="flex items-center gap-1.5"><Calendar className="h-4 w-4" /> {reportData.weekPeriod}</span>
                  <span>{reportData.turmaName}</span>
                </DialogDescription>
              </div>
              <img
                src={NARA_LOGO_URL}
                alt="Logo NARA"
                className="h-12 w-auto"
              />
            </div>
          </DialogHeader>
          
          <div className="p-6">
            <div className="bg-white p-4 rounded-xl border border-gray-100 overflow-x-auto">
              <table className="w-full text-sm text-left text-gray-600">
                <thead className="text-xs text-gray-700 uppercase bg-gray-50 rounded-t-lg">
                  <tr>
                    <th scope="col" className="px-4 py-3 w-1/4">Habilidades</th>
                    <th scope="col" className="px-4 py-3 w-1/3">Atividade Proposta</th>
                    <th scope="col" className="px-4 py-3 w-1/5">Atividade de Casa</th>
                    <th scope="col" className="px-4 py-3 w-1/5">Observações</th>
                  </tr>
                </thead>
                <tbody>
                  {reportData.dailyPlans.map((dayPlan, index) => (
                    <tr key={index} className="bg-white border-b last:border-b-0">
                      <td className="px-4 py-4 align-top">
                        <div className="flex items-center gap-2 font-semibold text-gray-800 mb-2">
                          {dayIcons[dayPlan.day.toLowerCase()]}
                          <span className="capitalize">{dayPlan.day}</span>
                        </div>
                        <div className="text-xs text-gray-600 whitespace-pre-wrap">
                          {(dayPlan.skills || [])
                            .map(skill => `${skill.codigo} - ${skill.descricao}`)
                            .join('\n') || '—'}
                        </div>
                      </td>
                      <td className="px-4 py-4 align-top whitespace-pre-wrap">{dayPlan.activities || '—'}</td>
                      <td className="px-4 py-4 align-top whitespace-pre-wrap">{dayPlan.homework || '—'}</td>
                      <td className="px-4 py-4 align-top whitespace-pre-wrap">{dayPlan.observations || '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <DialogFooter className="p-6 bg-white/50">
            <div className="w-full text-center">
              <p className="text-sm text-gray-500 mb-4">Agradecemos pela parceria! Qualquer dúvida, estamos à disposição.</p>
              <Button size="lg" className="nara-gradient text-white btn-hover w-full sm:w-auto" onClick={handleDownload}>
                <Download className="h-5 w-5 mr-2" /> Baixar PDF
              </Button>
            </div>
          </DialogFooter>
        </motion.div>
      </DialogContent>
    </Dialog>
  );
};

export default FamilyReportModal;
