import React, { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Upload, Save, Loader2, FileImage, FileText, Mic, Camera, X, Eye, Sparkles } from 'lucide-react';

import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter, DialogTrigger } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import { Progress } from '@/components/ui/progress';

const analysisConfig = {
    drawing: {
        icon: <FileImage className="h-5 w-5 text-[#8A63D2]" />,
        title: "Análise de Desenho",
        description: "Faça upload de uma foto do desenho para análise automática do estágio gráfico.",
        resultText: "Desenho com figura humana completa, uso de cores variadas e organização espacial desenvolvida.",
        accept: "image/jpeg, image/png, image/jpg",
        multiple: false,
    },
    writing: {
        icon: <FileText className="h-5 w-5 text-[#8A63D2]" />,
        title: "Análise de Escrita",
        description: "Envie uma imagem da escrita da criança para identificar a fase de alfabetização.",
        resultText: "Escrita na fase silábico-alfabética, com uso de letras reconhecíveis e tentativa de separar palavras.",
        accept: "image/jpeg, image/png, image/jpg",
        multiple: false,
    },
    reading: {
        icon: <Mic className="h-5 w-5 text-[#8A63D2]" />,
        title: "Análise de Leitura",
        description: "Grave ou envie um áudio da criança lendo para mapear o nível de fluência.",
        resultText: "Leitura com fluência inicial, reconhecendo palavras simples com entonação adequada.",
        accept: "audio/*",
        multiple: false,
    },
    media: {
        icon: <Camera className="h-5 w-5 text-[#8A63D2]" />,
        title: "📸 Upload de Foto ou Vídeo",
        description: "Anexe até 3 mídias (fotos ou vídeos curtos) para documentar momentos importantes.",
        resultText: "Mídia(s) anexada(s).",
        accept: "image/jpeg, image/png, image/jpg, video/mp4, video/quicktime",
        multiple: true,
    }
}

const FilePreview = ({ file, onRemove }) => {
    const isImage = file.type.startsWith('image/');
    const [previewUrl, setPreviewUrl] = useState(null);

    // Um object URL por arquivo, revogado ao desmontar. Antes a URL era criada
    // inline no src e no onClick, então cada re-render do preview criava outra
    // e nenhuma era revogada: o blob (uma foto ou vídeo inteiro) ficava preso
    // na aba até a página ser recarregada.
    useEffect(() => {
        const url = URL.createObjectURL(file);
        setPreviewUrl(url);
        return () => URL.revokeObjectURL(url);
    }, [file]);

    return (
        <motion.div
            layout
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.8 }}
            className="relative w-24 h-24 rounded-lg overflow-hidden border border-gray-200"
        >
            {isImage && previewUrl ? (
                <img  src={previewUrl} alt={file.name} className="w-full h-full object-cover" />
            ) : (
                <div className="w-full h-full bg-gray-100 flex items-center justify-center">
                    <Camera className="h-8 w-8 text-gray-400" />
                </div>
            )}
            <div className="absolute inset-0 bg-black/40 flex items-center justify-center opacity-0 hover:opacity-100 transition-opacity">
                <Button size="icon" variant="ghost" className="h-8 w-8 text-white hover:bg-white/20" disabled={!previewUrl} onClick={() => window.open(previewUrl, '_blank')}>
                    <Eye className="h-4 w-4" />
                </Button>
            </div>
            <Button size="icon" variant="destructive" className="absolute top-1 right-1 h-6 w-6" onClick={onRemove}>
                <X className="h-4 w-4" />
            </Button>
        </motion.div>
    );
};

export const MediaAnalysisModal = ({ students, analysisType, onSave, triggerButton }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [selectedStudent, setSelectedStudent] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [analysisResult, setAnalysisResult] = useState('');
  const [uploadedFiles, setUploadedFiles] = useState([]);
  const [addToPortfolio, setAddToPortfolio] = useState(true);
  const [project, setProject] = useState('');
  const [analysisProgress, setAnalysisProgress] = useState(0);
  const [analysisStep, setAnalysisStep] = useState(''); // 'uploading' | 'processing' | 'analyzing' | ''
  const fileInputRef = useRef(null);

  const config = analysisConfig[analysisType];

  const handleUpload = () => {
    if (!selectedStudent) {
      onSave({
        title: '⚠️ Atenção!',
        description: 'Por favor, selecione uma criança primeiro.',
        className: 'bg-yellow-100 border-yellow-300 text-yellow-800',
      });
      return;
    }
    fileInputRef.current.click();
  };

  const handleFileChange = (event) => {
    if (event.target.files && event.target.files.length > 0) {
        const newFiles = Array.from(event.target.files);
        const totalFiles = uploadedFiles.length + newFiles.length;

        if (config.multiple && totalFiles > 3) {
            onSave({
                title: 'Limite de arquivos excedido!',
                description: 'Você pode anexar no máximo 3 mídias.',
                variant: 'destructive'
            });
            return;
        }

        const filesToAdd = config.multiple ? [...uploadedFiles, ...newFiles].slice(0, 3) : newFiles.slice(0, 1);
        setUploadedFiles(filesToAdd);

        if (analysisType !== 'media') {
            setIsLoading(true);
            setAnalysisProgress(0);
            setAnalysisStep('uploading');

            // Simulate upload progress
            const uploadInterval = setInterval(() => {
                setAnalysisProgress(prev => {
                    if (prev >= 30) {
                        clearInterval(uploadInterval);
                        return prev;
                    }
                    return prev + 10;
                });
            }, 200);

            // Simulate processing step
            setTimeout(() => {
                setAnalysisStep('processing');
                setAnalysisProgress(40);

                const processInterval = setInterval(() => {
                    setAnalysisProgress(prev => {
                        if (prev >= 60) {
                            clearInterval(processInterval);
                            return prev;
                        }
                        return prev + 5;
                    });
                }, 150);
            }, 800);

            // Simulate AI analysis step
            setTimeout(() => {
                setAnalysisStep('analyzing');
                setAnalysisProgress(70);

                const analyzeInterval = setInterval(() => {
                    setAnalysisProgress(prev => {
                        if (prev >= 95) {
                            clearInterval(analyzeInterval);
                            return prev;
                        }
                        return prev + 5;
                    });
                }, 100);
            }, 1500);

            // Complete analysis
            setTimeout(() => {
                setAnalysisProgress(100);
                setAnalysisResult(config.resultText);
                setIsLoading(false);
                setAnalysisStep('');
                onSave({
                    title: '✨ Análise concluída!',
                    description: 'O resultado está pronto para revisão.',
                    className: 'bg-green-100 border-green-300 text-green-800',
                });
            }, 2500);
        } else {
            setAnalysisResult("Legenda gerada pela IA com base no contexto da atividade...");
        }
    }
  };

  const handleRemoveFile = (index) => {
    const newFiles = [...uploadedFiles];
    newFiles.splice(index, 1);
    setUploadedFiles(newFiles);
    if (newFiles.length === 0) {
        setAnalysisResult('');
    }
  };

  const handleSaveAnalysis = () => {
    onSave({
      title: '✅ Mídia salva!',
      description: `O registro foi adicionado com sucesso. ${addToPortfolio ? 'Visível no portfólio.' : ''}`,
      className: 'bg-green-100 border-green-300 text-green-800',
    });
    setIsOpen(false);
    setSelectedStudent('');
    setUploadedFiles([]);
    setAnalysisResult('');
    setAddToPortfolio(true);
    setProject('');
  };

  const handleGenerateCaption = () => {
    onSave({
        title: '✨ Legenda gerada!',
        description: 'A IA criou uma sugestão de legenda para você.',
        className: 'bg-purple-100 border-purple-300 text-purple-800',
    });
    setAnalysisResult("A IA sugere: Criança explorando texturas e cores com alegria e concentração durante a atividade de artes.");
  }

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DialogTrigger asChild>{triggerButton}</DialogTrigger>
      <DialogContent className="bg-[#F5F3FA]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">{config.icon} {config.title}</DialogTitle>
          <DialogDescription>{config.description}</DialogDescription>
        </DialogHeader>
        <div className="space-y-4 py-2 max-h-[60vh] overflow-y-auto pr-2">
          <div>
            <Label htmlFor={`student-select-${analysisType}`} className="font-semibold text-gray-700">Criança</Label>
            <Select onValueChange={setSelectedStudent} value={selectedStudent}>
              <SelectTrigger id={`student-select-${analysisType}`} className="mt-1 bg-white">
                <SelectValue placeholder="Selecione a criança" />
              </SelectTrigger>
              <SelectContent>
                {students.map(student => (
                  <SelectItem key={student.id} value={student.id}>{student.name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          
          <input type="file" ref={fileInputRef} onChange={handleFileChange} className="hidden" accept={config.accept} multiple={config.multiple} />

          <AnimatePresence>
            {selectedStudent && (
              <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }}>
                 <Button onClick={handleUpload} className="w-full mt-4 bg-white text-gray-800 border-gray-300" variant="outline" disabled={!selectedStudent || (config.multiple && uploadedFiles.length >= 3)}>
                  <Upload className="mr-2 h-4 w-4" />
                  {uploadedFiles.length > 0 ? 'Adicionar mais' : 'Fazer Upload'}
                </Button>
              </motion.div>
            )}
          </AnimatePresence>

          <AnimatePresence>
            {uploadedFiles.length > 0 && (
                <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="pt-2 space-y-4">
                    <div>
                        <Label className="font-semibold text-gray-700">Mídias Anexadas</Label>
                        <div className="flex flex-wrap gap-2 mt-2">
                            {uploadedFiles.map((file, index) => (
                                <FilePreview key={index} file={file} onRemove={() => handleRemoveFile(index)} />
                            ))}
                        </div>
                    </div>
                    {analysisType === 'media' && (
                        <div className="items-center flex space-x-2">
                            <Checkbox id={`portfolio-check-${analysisType}`} checked={addToPortfolio} onCheckedChange={setAddToPortfolio} />
                            <Label htmlFor={`portfolio-check-${analysisType}`} className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">
                                Adicionar ao portfólio
                            </Label>
                        </div>
                    )}
                </motion.div>
            )}
          </AnimatePresence>

          <AnimatePresence>
            {isLoading && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="p-4 space-y-3 bg-purple-50 rounded-lg border border-purple-200"
              >
                <div className="flex items-center gap-2 text-[#8A63D2]">
                  <Loader2 className="h-5 w-5 animate-spin" />
                  <span className="font-medium">
                    {analysisStep === 'uploading' && 'Enviando imagem...'}
                    {analysisStep === 'processing' && 'Processando arquivo...'}
                    {analysisStep === 'analyzing' && '🤖 Analisando com a Nara...'}
                  </span>
                </div>
                <Progress value={analysisProgress} className="h-2" indicatorClassName="bg-[#8A63D2]" />
                <p className="text-xs text-gray-500">
                  {analysisStep === 'uploading' && 'Preparando arquivo para análise'}
                  {analysisStep === 'processing' && 'Otimizando imagem para processamento'}
                  {analysisStep === 'analyzing' && 'A IA está identificando padrões e características'}
                </p>
              </motion.div>
            )}
            {analysisResult && !isLoading && (
              <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-2 pt-2">
                <div className="flex justify-between items-center">
                    <Label htmlFor={`analysis-result-${analysisType}`} className="font-semibold text-gray-700">Legenda (editável)</Label>
                    <Button variant="ghost" size="sm" onClick={handleGenerateCaption}>
                        <Sparkles className="h-4 w-4 mr-1 text-yellow-500" /> Gerar com IA
                    </Button>
                </div>
                <Textarea
                  id={`analysis-result-${analysisType}`}
                  value={analysisResult}
                  onChange={(e) => setAnalysisResult(e.target.value)}
                  rows={3}
                  maxLength={200}
                  className="bg-white"
                  placeholder="Descreva o que a mídia representa..."
                />
                <div className="pt-2">
                    <Label htmlFor={`project-${analysisType}`} className="font-semibold text-gray-700">Projeto vinculado (opcional)</Label>
                    <Input 
                        id={`project-${analysisType}`}
                        value={project}
                        onChange={(e) => setProject(e.target.value)}
                        className="bg-white mt-1"
                        placeholder="Ex: Projeto Animais da Fazenda"
                    />
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={() => setIsOpen(false)}>Cancelar</Button>
          <Button onClick={handleSaveAnalysis} disabled={uploadedFiles.length === 0 || isLoading} className="bg-[#C3ECD4] hover:bg-[#B0E4C1] text-gray-800">
            <Save className="mr-2 h-4 w-4" />
            Salvar Registro
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};