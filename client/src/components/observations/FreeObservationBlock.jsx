import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Mic, Loader2, BrainCircuit, Pencil, Trash2, FileImage, FileText, Camera } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { useToast } from '@/components/ui/use-toast';
import { MediaAnalysisModal } from '@/components/observations/MediaAnalysisModal';

export const FreeObservationBlock = ({ students }) => {
  const { toast } = useToast();
  const [isRecording, setIsRecording] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [analysisResult, setAnalysisResult] = useState(null);

  const handleRecord = () => {
    setIsRecording(true);
    toast({
      title: '🎙️ Gravando...',
      description: 'Fale livremente sobre o dia da turma.',
    });

    setTimeout(() => {
      setIsRecording(false);
      setIsLoading(true);
      toast({
        title: '🤖 Processando áudio com IA...',
        description: 'Aguarde um momento.',
      });

      setTimeout(() => {
        setAnalysisResult({
          'Júlia': 'Participou ativamente da contação de história.',
          'Davi': 'Apresentou dificuldade inicial de interação, mas se engajou posteriormente na roda.',
        });
        setIsLoading(false);
        toast({
          title: '✨ Análise concluída!',
          description: 'Os registros por criança estão prontos para revisão.',
          className: 'bg-green-100 border-green-300 text-green-800',
        });
      }, 3000);
    }, 4000);
  };
  
  const handleEditResult = (student, newText) => {
    setAnalysisResult(prev => ({...prev, [student]: newText}));
  };
  
  const mediaTypes = [
      { type: 'drawing', icon: FileImage, label: 'Análise de Desenho'},
      { type: 'writing', icon: FileText, label: 'Análise de Escrita'},
      { type: 'reading', icon: Mic, label: 'Análise de Leitura'},
      { type: 'media', icon: Camera, label: 'Foto ou Vídeo'},
  ];

  return (
    <div className="space-y-6">
      <Button 
        className="w-full h-16 text-lg font-bold nara-gradient text-white btn-hover flex items-center gap-3"
        onClick={handleRecord}
        disabled={isRecording || isLoading}
      >
        {isRecording ? (
          <><Mic className="h-6 w-6 animate-pulse" /> <span>Gravando...</span></>
        ) : isLoading ? (
          <><Loader2 className="h-6 w-6 animate-spin" /> <span>Analisando...</span></>
        ) : (
          <><Mic className="h-6 w-6" /> <span>Gravar Observação por Áudio</span></>
        )}
      </Button>

      <AnimatePresence>
        {analysisResult && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-purple-50 p-4 rounded-xl border border-purple-200"
          >
            <h3 className="text-lg font-bold text-[#8A63D2] flex items-center gap-2 mb-4">
              <BrainCircuit className="h-5 w-5"/>
              Resultados da Análise de IA
            </h3>
            <div className="space-y-4">
            {Object.entries(analysisResult).map(([student, text]) => (
              <div key={student}>
                <Label className="font-bold text-gray-700">{student}</Label>
                <div className="flex gap-2 mt-1">
                  <Textarea 
                    value={text} 
                    onChange={(e) => handleEditResult(student, e.target.value)}
                    className="bg-white"
                  />
                  <Button variant="ghost" size="icon" onClick={() => toast({title: "Texto editado!"})}>
                    <Pencil className="h-4 w-4 text-gray-500"/>
                  </Button>
                </div>
              </div>
            ))}
            </div>
            <Button variant="link" className="text-red-500 mt-4" onClick={() => setAnalysisResult(null)}>
              <Trash2 className="h-4 w-4 mr-2"/>
              Descartar Análise
            </Button>
          </motion.div>
        )}
      </AnimatePresence>
      
      <div>
        <Label className="font-semibold text-gray-700">Ou adicione mídias individuais:</Label>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-2">
            {mediaTypes.map(({type, icon: Icon, label}) => (
                 <MediaAnalysisModal
                    key={type}
                    students={students}
                    analysisType={type}
                    onSave={toast}
                    triggerButton={
                        <Button variant="outline" className="flex-col h-24 gap-1 text-center bg-white">
                            <Icon className="h-6 w-6 text-[#8A63D2]" /> 
                            <span className="text-xs font-normal">{label}</span>
                        </Button>
                    }
                />
            ))}
        </div>
        <p className="text-xs text-gray-500 mt-2 text-center">
            Adicione registros visuais da criança para compor o portfólio (fotos ou vídeos curtos).
        </p>
      </div>
    </div>
  )
}