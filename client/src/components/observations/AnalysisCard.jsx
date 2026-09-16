import React, { useState, useRef, useEffect } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { useToast } from '@/components/ui/use-toast';
import { apiService, uploadProducaoCrianca } from '@/services/api';

import { Card, CardContent, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/components/ui/dialog';
import { Upload, FileImage, X, Loader2, Save, Lock } from 'lucide-react';
import NaraIaIcon from '@/components/NaraIaIcon';

// Fallback caso o backend não envie `fases_validas` na resposta do upload
// (fonte canônica: server/api/services/fases_producao.py).
const FASES_PADRAO = {
    escrita: ['Pré-silábica', 'Silábica sem valor sonoro', 'Silábica com valor sonoro', 'Silábico-alfabética', 'Alfabética', 'Não classificável'],
    desenho: ['Garatuja desordenada', 'Garatuja controlada', 'Pré-esquemático', 'Esquemático', 'Realismo nascente', 'Não classificável'],
};

const FilePreview = ({ file, onRemove }) => {
    const [imageError, setImageError] = useState(false);
    const isImage = file.type.startsWith('image/') && !imageError;
    const url = URL.createObjectURL(file);
    
    // Formatar tamanho do arquivo
    const formatFileSize = (bytes) => {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    };
    
    return (
        <div className="relative w-24 h-24 rounded-lg overflow-hidden border-2 border-lavanda bg-white shadow-sm">
            {isImage ? (
                <img 
                    src={url} 
                    alt={file.name} 
                    className="w-full h-full object-cover"
                    onLoad={() => URL.revokeObjectURL(url)}
                    onError={() => {
                        setImageError(true);
                        URL.revokeObjectURL(url);
                    }}
                />
            ) : (
                <div className="w-full h-full bg-gray-100 flex flex-col items-center justify-center p-2">
                    <FileImage className="h-6 w-6 text-gray-400 mb-1" />
                    <span className="text-xs text-gray-500 text-center truncate w-full">
                        {file.type.startsWith('image/') ? 'IMG' : file.name.split('.').pop()?.toUpperCase() || 'FILE'}
                    </span>
                </div>
            )}
            <Button 
                size="icon" 
                variant="destructive" 
                className="absolute -top-2 -right-2 h-5 w-5 rounded-full shadow-md hover:scale-110 transition-transform" 
                onClick={onRemove}
                title="Remover arquivo"
            >
                <X className="h-3 w-3" />
            </Button>
            
            {/* Informações do arquivo na parte inferior */}
            <div className="absolute bottom-0 left-0 right-0 bg-black bg-opacity-70 text-white text-xs p-1">
                <div className="truncate" title={file.name}>{file.name}</div>
                <div className="text-gray-300">{formatFileSize(file.size)}</div>
            </div>
        </div>
    );
};

const buildAnalysisKey = (analysisType, file, studentId) => {
    if (!file || !studentId) {
        return '';
    }
    return `${analysisType}:${studentId}:${file.name}:${file.size}:${file.lastModified}`;
};

export const AnalysisCard = ({ icon, title, type, students, turmaId }) => {
    const { toast } = useToast();
    const { user } = useAuth();
    const fileInputRef = useRef(null);
    const lastAnalysisKeyRef = useRef('');
    const [selectedStudent, setSelectedStudent] = useState('');
    const [uploadedFile, setUploadedFile] = useState(null);
    const [description, setDescription] = useState('');
    const [aiAnalysis, setAiAnalysis] = useState(''); // Nova state para análise da IA
    const [aiPhase, setAiPhase] = useState(''); // Nova state para a fase sugerida
    const [fileHash, setFileHash] = useState(''); // Nova state para o hash do arquivo
    // Estados específicos para desenho
    const [drawingPhase, setDrawingPhase] = useState('');
    const [detectedElements, setDetectedElements] = useState([]);
    const [drawingAnalysis, setDrawingAnalysis] = useState('');
    const [tag, setTag] = useState('');
    const [isSaving, setIsSaving] = useState(false);
    const [isUploading, setIsUploading] = useState(false);
    const [isAnalyzing, setIsAnalyzing] = useState(false);
    // Modal de confirmação da classificação antes de salvar
    const [confirmOpen, setConfirmOpen] = useState(false);
    const [discordou, setDiscordou] = useState(false);
    const [overridePhase, setOverridePhase] = useState('');
    const [fasesValidas, setFasesValidas] = useState([]);

    const isMediaCard = type === 'media';
    const allowedImageTypes = ['image/jpeg', 'image/png', 'image/webp', 'image/jpg', 'image/heic', 'image/heif'];
    const allowedImageExtensions = ['jpg', 'jpeg', 'png', 'webp', 'heic', 'heif'];
    const maxImageBytes = 10 * 1024 * 1024; // 10MB
    const footerText = isMediaCard
        ? "🧺 Este registro será armazenado no portfólio."
        : "📝 Este registro será integrado ao relatório final.";

    const resetFileInput = () => {
        if (fileInputRef.current) {
            fileInputRef.current.value = '';
        }
    };

    const resetAnalysisData = () => {
        setAiAnalysis('');
        setAiPhase('');
        setDrawingPhase('');
        setDetectedElements([]);
        setDrawingAnalysis('');
        setFileHash('');
        setConfirmOpen(false);
        setDiscordou(false);
        setOverridePhase('');
        setFasesValidas([]);
    };

    const validateFileBeforeUpload = (file) => {
        if (!file || (type !== 'escrita' && type !== 'desenho')) {
            return true;
        }

        const fileExtension = file.name.split('.').pop()?.toLowerCase() || '';
        const isAllowedType = allowedImageTypes.includes(file.type) || allowedImageExtensions.includes(fileExtension);

        if (!isAllowedType) {
            toast({
                title: 'Formato não suportado',
                description: 'Envie imagens nos formatos JPG, PNG, WEBP ou HEIC.',
                variant: 'destructive',
            });
            resetFileInput();
            return false;
        }

        if (file.size > maxImageBytes) {
            toast({
                title: 'Arquivo muito grande',
                description: 'O limite é de 10MB por imagem. Comprima o arquivo antes de enviar.',
                variant: 'destructive',
            });
            resetFileInput();
            return false;
        }

        return true;
    };

    const processAnaliseEscrita = async (file) => {
        if (type !== 'escrita' || !selectedStudent) {
            return;
        }

        if (!validateFileBeforeUpload(file)) {
            return;
        }

        setIsUploading(true);
        setIsAnalyzing(true);
        
        try {
            const selectedStudentData = students.find(s => s.id === selectedStudent);
            
            // Determinar o nome do aluno usando várias possibilidades
            let nomeAluno = 'Aluno não identificado';
            if (selectedStudentData) {
                nomeAluno = selectedStudentData.nome_completo || 
                           selectedStudentData.nome || 
                           selectedStudentData.name || 
                           `Aluno ID: ${selectedStudentData.id}`;
            }
            
            const dadosAnalise = {
                nomeAluno: nomeAluno,
                serieAluno: selectedStudentData?.serie || selectedStudentData?.grade || 'Educação Infantil',
                turmaId: turmaId
            };

            // Fazer upload do arquivo e análise no backend
            const resultadoAnalise = await apiService.uploadEAnaliseEscrita(dadosAnalise, file);
            setAiPhase(resultadoAnalise.analise.fase_escrita);
            setAiAnalysis(resultadoAnalise.analise.descricao);
            setFileHash(resultadoAnalise.arquivo_hash);
            setFasesValidas(resultadoAnalise.analise.fases_validas || FASES_PADRAO.escrita);
            
            console.log('Upload realizado:', {
                arquivo_hash: resultadoAnalise.arquivo_hash,
                arquivo_nome: resultadoAnalise.arquivo_nome,
                arquivo_original: resultadoAnalise.arquivo_original,
                fase_escrita: resultadoAnalise.analise.fase_escrita
            });
            
            toast({
                title: '🤖 Upload e Análise concluídos!',
                description: `Arquivo enviado (ID: ${resultadoAnalise.arquivo_hash}) e análise de ${dadosAnalise.nomeAluno} realizada com sucesso.`,
                className: 'bg-blue-100 border-blue-300 text-blue-800',
            });
        } catch (apiError) {
            console.error('Erro no upload e análise:', apiError);
            setAiPhase('Análise indisponível');
            setAiAnalysis('A análise automática falhou. Você pode adicionar uma descrição manual e salvar o registro.');
            toast({
                title: '⚠️ Erro no upload',
                description: 'O upload do arquivo falhou. Você pode adicionar a descrição manualmente.',
                className: 'bg-yellow-100 border-yellow-300 text-yellow-800',
            });
        } finally {
            setIsUploading(false);
            setIsAnalyzing(false);
        }
    };

    const processAnaliseDesenho = async (file) => {
        if (type !== 'desenho' || !selectedStudent) {
            return;
        }

        if (!validateFileBeforeUpload(file)) {
            return;
        }

        setIsUploading(true);
        setIsAnalyzing(true);
        
        try {
            const selectedStudentData = students.find(s => s.id === selectedStudent);
            
            // Determinar o nome do aluno
            let nomeAluno = 'Aluno não identificado';
            if (selectedStudentData) {
                nomeAluno = selectedStudentData.nome_completo || 
                           selectedStudentData.nome || 
                           selectedStudentData.name || 
                           `Aluno ID: ${selectedStudentData.id}`;
            }
            
            // Preparar FormData para upload
            const formData = new FormData();
            formData.append('arquivo', file);
            formData.append('nomeAluno', nomeAluno);
            formData.append('serieAluno', selectedStudentData?.serie || 'Educação Infantil');
            formData.append('turmaId', turmaId || '1');
            formData.append('professora', user?.email || 'Professor');
            formData.append('atividade', 'Análise de Desenho');
            formData.append('contexto', description || 'Desenho livre');

            // Fazer upload do arquivo e análise no backend
            const resultadoAnalise = await apiService.uploadEAnaliseDesenho(formData);
            
            setDrawingPhase(resultadoAnalise.analise.fase_desenho || 'Não detectada');
            setDetectedElements(resultadoAnalise.analise.elementos || []);
            setDrawingAnalysis(resultadoAnalise.analise.descricao || 'Análise não disponível');
            setFileHash(resultadoAnalise.arquivo_hash);
            setFasesValidas(resultadoAnalise.analise.fases_validas || FASES_PADRAO.desenho);
            
            console.log('Upload de desenho realizado:', {
                arquivo_hash: resultadoAnalise.arquivo_hash,
                fase_desenho: resultadoAnalise.analise.fase_desenho,
                elementos: resultadoAnalise.analise.elementos
            });
            
            toast({
                title: '🎨 Análise de Desenho concluída!',
                description: `Desenho de ${nomeAluno} analisado com sucesso. Fase: ${resultadoAnalise.analise.fase_desenho}`,
                className: 'bg-green-100 border-green-300 text-green-800',
            });
        } catch (apiError) {
            console.error('Erro no upload e análise de desenho:', apiError);
            setDrawingPhase('Análise indisponível');
            setDrawingAnalysis('A análise automática falhou. Você pode adicionar uma descrição manual e salvar o registro.');
            setDetectedElements([]);
            toast({
                title: '⚠️ Erro na análise do desenho',
                description: 'O upload do desenho falhou. Você pode adicionar a descrição manualmente.',
                className: 'bg-yellow-100 border-yellow-300 text-yellow-800',
            });
        } finally {
            setIsUploading(false);
            setIsAnalyzing(false);
        }
    };

    const handleFileChange = (event) => {
        if (event.target.files && event.target.files.length > 0) {
            const file = event.target.files[0];

            if (!validateFileBeforeUpload(file)) {
                return;
            }

            setUploadedFile(file);
            resetAnalysisData();
            lastAnalysisKeyRef.current = '';
            
            // Processar análise automaticamente baseado no tipo
            if (type === 'escrita') {
                if (!selectedStudent) {
                    toast({
                        title: 'Selecione a criança',
                        description: 'Escolha a criança antes de enviar o arquivo para análise.',
                        variant: 'destructive',
                    });
                    return;
                }
                lastAnalysisKeyRef.current = buildAnalysisKey(type, file, selectedStudent);
                processAnaliseEscrita(file);
            } else if (type === 'desenho') {
                if (!selectedStudent) {
                    toast({
                        title: 'Selecione a criança',
                        description: 'Escolha a criança antes de enviar o arquivo para análise.',
                        variant: 'destructive',
                    });
                    return;
                }
                lastAnalysisKeyRef.current = buildAnalysisKey(type, file, selectedStudent);
                processAnaliseDesenho(file);
            }
        }
    };

    useEffect(() => {
        if (!uploadedFile || !selectedStudent) {
            return;
        }
        if (type !== 'escrita' && type !== 'desenho') {
            return;
        }
        if (isUploading || isAnalyzing) {
            return;
        }
        if (type === 'escrita' && aiPhase) {
            return;
        }
        if (type === 'desenho' && drawingPhase) {
            return;
        }

        const analysisKey = buildAnalysisKey(type, uploadedFile, selectedStudent);
        if (!analysisKey || lastAnalysisKeyRef.current === analysisKey) {
            return;
        }

        lastAnalysisKeyRef.current = analysisKey;

        if (type === 'escrita') {
            processAnaliseEscrita(uploadedFile);
        } else {
            processAnaliseDesenho(uploadedFile);
        }
    }, [uploadedFile, selectedStudent, type, isUploading, isAnalyzing, aiPhase, drawingPhase]);

    const handleRemoveFile = () => {
        setUploadedFile(null);
        resetAnalysisData();
        lastAnalysisKeyRef.current = '';
        resetFileInput();
    };

    const resetForm = () => {
        setSelectedStudent('');
        setUploadedFile(null);
        setDescription('');
        resetAnalysisData();
        setTag('');
        lastAnalysisKeyRef.current = '';
        resetFileInput();
    };

    const handleSave = async () => {
        // Verificar se há upload em andamento para análise de escrita ou desenho
        if ((type === 'escrita' || type === 'desenho') && (isUploading || isAnalyzing)) {
            toast({
                title: '⏳ Upload em andamento',
                description: 'Aguarde o upload e análise serem concluídos antes de salvar.',
                className: 'bg-yellow-100 border-yellow-300 text-yellow-800',
            });
            return;
        }

        if (!selectedStudent || !uploadedFile) {
            toast({
                title: 'Campos obrigatórios',
                description: 'Por favor, selecione uma criança e anexe um arquivo.',
                variant: 'destructive',
            });
            return;
        }

        // Para análise de escrita, verificar se a IA já processou
        if (type === 'escrita' && !aiPhase) {
            toast({
                title: 'Análise pendente',
                description: 'Aguarde a IA processar a análise da escrita antes de salvar.',
                variant: 'destructive',
            });
            return;
        }

        // Para análise de desenho, verificar se a IA já processou
        if (type === 'desenho' && !drawingPhase) {
            toast({
                title: 'Análise pendente',
                description: 'Aguarde a IA processar a análise do desenho antes de salvar.',
                variant: 'destructive',
            });
            return;
        }

        // Escrita/desenho: antes de persistir, pedir a confirmação da
        // classificação sugerida pela IA no modal (concordar ou corrigir).
        if ((type === 'escrita' || type === 'desenho') && fileHash) {
            setDiscordou(false);
            setOverridePhase('');
            setConfirmOpen(true);
            return;
        }

        setIsSaving(true);

        try {
            // Para outros tipos (mídia), enviar para o backend
            await uploadProducaoCrianca({
                arquivo: uploadedFile,
                crianca_id: selectedStudent,
                turma_id: turmaId,
                professor_id: user.id,
                instituicao_id: user.user_metadata.instituicao_id,
                tipo: type,
                descricao: description,
                titulo: isMediaCard ? tag : '',
            });

            toast({
                title: '✅ Registro salvo!',
                description: 'A produção foi salva com sucesso.',
                className: 'bg-green-100 border-green-300 text-green-800',
            });
            resetForm();

        } catch (error) {
            toast({
                title: 'Erro ao salvar',
                description: error.message,
                variant: 'destructive',
            });
        } finally {
            setIsSaving(false);
        }
    };

    /**
     * Chamado pelo modal de confirmação. `classificacaoEscolhida` é null quando
     * a professora concorda com a sugestão da IA; caso contrário, é a fase
     * escolhida no select — atualizada no backend antes de concluir o salvamento.
     */
    const confirmarESalvar = async (classificacaoEscolhida) => {
        setConfirmOpen(false);
        setIsSaving(true);

        try {
            const sugerida = type === 'escrita' ? aiPhase : drawingPhase;
            let classificacaoFinal = sugerida;

            if (classificacaoEscolhida && classificacaoEscolhida !== sugerida) {
                await apiService.atualizarClassificacaoRegistro(type, fileHash, classificacaoEscolhida);
                classificacaoFinal = classificacaoEscolhida;
                if (type === 'escrita') {
                    setAiPhase(classificacaoEscolhida);
                } else {
                    setDrawingPhase(classificacaoEscolhida);
                }
            }

            // Anotações da professora (a análise em si já foi salva no upload)
            if (type === 'escrita') {
                await apiService.salvarAnotacoesProfessora(fileHash, description || '', user?.email || 'Professora');
            }

            toast({
                title: type === 'escrita' ? '✅ Registro de escrita salvo!' : '✅ Registro de desenho salvo!',
                description: classificacaoEscolhida && classificacaoEscolhida !== sugerida
                    ? `Classificação ajustada pela professora para "${classificacaoFinal}" e registro salvo.`
                    : `Classificação "${classificacaoFinal}" confirmada e registro salvo.`,
                className: 'bg-green-100 border-green-300 text-green-800',
            });

            resetForm();
        } catch (error) {
            toast({
                title: 'Erro ao salvar',
                description: error.message,
                variant: 'destructive',
            });
        } finally {
            setIsSaving(false);
        }
    };

    const faseSugerida = type === 'escrita' ? aiPhase : drawingPhase;
    const opcoesFases = (fasesValidas.length > 0 ? fasesValidas : (FASES_PADRAO[type] || []))
        .filter((f) => f !== faseSugerida);

    return (
        <Card className="bg-white/70 border-lavanda shadow-sm overflow-hidden">
            <CardHeader className="bg-lavanda-claro p-4">
                <CardTitle className="flex items-center gap-3 text-base font-bold text-texto-escuro">
                    {icon}
                    {title}
                </CardTitle>
            </CardHeader>
            <CardContent className="p-4 space-y-4">
                <div>
                    <Label className="font-semibold">Criança</Label>
                    <Select onValueChange={setSelectedStudent} value={selectedStudent}>
                        <SelectTrigger className="mt-1 bg-white"><SelectValue placeholder="Selecione a criança" /></SelectTrigger>
                        <SelectContent>
                            {students.map(student => (
                                <SelectItem key={student.id} value={student.id}>{student.nome_completo}</SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                </div>

                <div>
                    <Label className="font-semibold">Anexar produção</Label>
                    <div
                        className="mt-1 flex justify-center items-center w-full h-28 border-2 border-dashed border-gray-300 rounded-lg cursor-pointer hover:bg-gray-50 transition-colors"
                        onClick={() => fileInputRef.current?.click()}
                    >
                        {uploadedFile ? (
                            <div className="flex items-center space-x-4">
                                <FilePreview file={uploadedFile} onRemove={handleRemoveFile} />
                                {(isUploading || isAnalyzing) && type === 'escrita' && (
                                    <div className="flex flex-col items-center text-blue-600">
                                        <Loader2 className="h-6 w-6 animate-spin" />
                                        <p className="text-xs mt-1">
                                            {isUploading ? 'Enviando arquivo...' : 'Analisando escrita...'}
                                        </p>
                                    </div>
                                )}
                            </div>
                        ) : (
                            <div className="text-center text-gray-500">
                                <Upload className="mx-auto h-8 w-8" />
                                <p className="text-sm">Clique para fazer upload</p>
                            </div>
                        )}
                    </div>
                    <input type="file" ref={fileInputRef} onChange={handleFileChange} className="hidden" accept={isMediaCard ? "image/*,video/*" : "image/*"} />
                </div>

                {!isMediaCard && (
                    <div className="bg-lavanda-claro p-4 rounded-lg border border-lavanda">
                        <div className="flex items-start gap-3">
                            <NaraIaIcon className="h-6 w-6 text-roxo-principal flex-shrink-0" />
                            <div className="flex-grow">
                                <h4 className="font-bold text-texto-escuro">Análise Automática por IA</h4>
                                <p className="text-xs text-texto-medio mt-1">
                                    <Lock className="h-3 w-3 inline-block mr-1" />
                                    {type === 'escrita' ? 
                                        'A interpretação é gerada pela IA do NARA com base na imagem enviada, seguindo a teoria da psicogênese da escrita.' :
                                        'A interpretação é gerada pela IA do NARA com base na imagem enviada, analisando o desenvolvimento gráfico e criativo.'
                                    }
                                </p>
                                <div className="mt-3">
                                    {type === 'escrita' && (
                                        <>
                                            <div className="mb-3">
                                                <span className="font-semibold text-sm">Etapa sugerida pela IA:</span>
                                                <div className="mt-1 p-2 bg-white rounded border">
                                                    {(isUploading || isAnalyzing) ? (
                                                        <span className="text-gray-500 italic flex items-center">
                                                            <Loader2 className="h-3 w-3 animate-spin mr-1" />
                                                            Analisando...
                                                        </span>
                                                    ) : aiPhase ? (
                                                        <span className="text-texto-escuro font-medium">{aiPhase}</span>
                                                    ) : (
                                                        <span className="text-gray-500 italic">Aguardando upload de imagem...</span>
                                                    )}
                                                </div>
                                            </div>
                                            {aiAnalysis && (
                                                <div>
                                                    <span className="font-semibold text-sm">Análise detalhada:</span>
                                                    <div className="mt-1 p-3 bg-white rounded border max-h-40 overflow-y-auto">
                                                        <div className="text-sm text-texto-escuro whitespace-pre-wrap">
                                                            {aiAnalysis}
                                                        </div>
                                                    </div>
                                                </div>
                                            )}
                                        </>
                                    )}
                                    
                                    {type === 'desenho' && (
                                        <>
                                            <div className="mb-3">
                                                <span className="font-semibold text-sm">Fase do desenho:</span>
                                                <div className="mt-1 p-2 bg-white rounded border">
                                                    {(isUploading || isAnalyzing) ? (
                                                        <span className="text-gray-500 italic flex items-center">
                                                            <Loader2 className="h-3 w-3 animate-spin mr-1" />
                                                            Analisando desenho...
                                                        </span>
                                                    ) : drawingPhase ? (
                                                        <span className="text-texto-escuro font-medium">{drawingPhase}</span>
                                                    ) : (
                                                        <span className="text-gray-500 italic">Aguardando upload de imagem...</span>
                                                    )}
                                                </div>
                                            </div>
                                            
                                            {detectedElements.length > 0 && (
                                                <div className="mb-3">
                                                    <span className="font-semibold text-sm">Elementos detectados:</span>
                                                    <div className="mt-1 flex flex-wrap gap-1">
                                                        {detectedElements.map((elemento, index) => (
                                                            <span 
                                                                key={index}
                                                                className="inline-block bg-roxo-claro/20 text-roxo-principal text-xs px-2 py-1 rounded-full border border-roxo-claro"
                                                            >
                                                                {elemento}
                                                            </span>
                                                        ))}
                                                    </div>
                                                </div>
                                            )}
                                            
                                            {drawingAnalysis && (
                                                <div>
                                                    <span className="font-semibold text-sm">Análise detalhada:</span>
                                                    <div className="mt-1 p-3 bg-white rounded border max-h-40 overflow-y-auto">
                                                        <div className="text-sm text-texto-escuro whitespace-pre-wrap">
                                                            {drawingAnalysis}
                                                        </div>
                                                    </div>
                                                </div>
                                            )}
                                        </>
                                    )}
                                </div>
                            </div>
                        </div>
                    </div>
                )}

                <div>
                    <Label className="font-semibold">
                        {isMediaCard ? 'Descrição da atividade/contexto' : 'Anotações adicionais da professora (opcional)'}
                    </Label>
                    <Textarea 
                        className="mt-1 bg-white" 
                        value={description} 
                        onChange={(e) => setDescription(e.target.value)}
                        placeholder={
                            isMediaCard ? "Descreva a atividade ou contexto..." :
                            "Adicione observações complementares sobre a produção da criança..."
                        }
                        disabled={false}
                    />
                </div>
                
                {isMediaCard && (
                    <div>
                        <Label className="font-semibold">Tag (opcional)</Label>
                        <Input className="mt-1 bg-white" placeholder="Ex: projeto, rotina, momento especial" value={tag} onChange={(e) => setTag(e.target.value)} />
                    </div>
                )}
            </CardContent>
            <CardFooter className="bg-lavanda-claro p-4 flex flex-col items-start gap-4">
                <p className="text-xs text-texto-medio italic">{footerText}</p>
                <Button 
                    onClick={handleSave} 
                    disabled={
                        isSaving || 
                        (type === 'escrita' && (isUploading || isAnalyzing || !aiPhase)) ||
                        (type === 'desenho' && (isUploading || isAnalyzing || !drawingPhase)) ||
                        (type !== 'escrita' && type !== 'desenho' && (!selectedStudent || !uploadedFile))
                    } 
                    className="w-full bg-verde-menta hover:bg-opacity-80 text-texto-escuro disabled:opacity-50 disabled:cursor-not-allowed"
                >
                    {isSaving ? (
                        <>
                            <Loader2 className="h-4 w-4 animate-spin mr-2" />
                            <span>Salvando...</span>
                        </>
                    ) : isUploading ? (
                        <>
                            <Loader2 className="h-4 w-4 animate-spin mr-2" />
                            <span>Enviando arquivo...</span>
                        </>
                    ) : isAnalyzing ? (
                        <>
                            <Loader2 className="h-4 w-4 animate-spin mr-2" />
                            <span>{type === 'escrita' ? 'Analisando escrita...' : 'Analisando desenho...'}</span>
                        </>
                    ) : (
                        <>
                            <Save className="h-4 w-4 mr-2" />
                            <span>Salvar Registro</span>
                        </>
                    )}
                </Button>
            </CardFooter>

            {/* Modal de confirmação da classificação sugerida pela IA */}
            <Dialog open={confirmOpen} onOpenChange={(open) => { if (!open) setConfirmOpen(false); }}>
                <DialogContent className="sm:max-w-md">
                    <DialogHeader>
                        <DialogTitle>
                            {type === 'escrita' ? 'Confirmar etapa da escrita' : 'Confirmar fase do desenho'}
                        </DialogTitle>
                        <DialogDescription>
                            A IA do NARA sugeriu a classificação abaixo. Você concorda?
                        </DialogDescription>
                    </DialogHeader>

                    <div className="p-3 bg-lavanda-claro border border-lavanda rounded-lg text-center">
                        <span className="text-xs text-texto-medio block mb-1">
                            {type === 'escrita' ? 'Etapa sugerida pela IA' : 'Fase sugerida pela IA'}
                        </span>
                        <span className="font-bold text-texto-escuro">{faseSugerida}</span>
                    </div>

                    {discordou && (
                        <div>
                            <Label className="font-semibold text-sm">Qual classificação você considera correta?</Label>
                            <Select onValueChange={setOverridePhase} value={overridePhase}>
                                <SelectTrigger className="mt-1 bg-white">
                                    <SelectValue placeholder="Selecione a classificação" />
                                </SelectTrigger>
                                <SelectContent>
                                    {opcoesFases.map((fase) => (
                                        <SelectItem key={fase} value={fase}>{fase}</SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </div>
                    )}

                    <DialogFooter className="gap-2 sm:gap-2">
                        {!discordou ? (
                            <>
                                <Button
                                    variant="outline"
                                    onClick={() => setDiscordou(true)}
                                >
                                    Não concordo
                                </Button>
                                <Button
                                    className="bg-verde-menta hover:bg-opacity-80 text-texto-escuro"
                                    onClick={() => confirmarESalvar(null)}
                                >
                                    Concordo, salvar
                                </Button>
                            </>
                        ) : (
                            <>
                                <Button
                                    variant="outline"
                                    onClick={() => { setDiscordou(false); setOverridePhase(''); }}
                                >
                                    Voltar
                                </Button>
                                <Button
                                    className="bg-verde-menta hover:bg-opacity-80 text-texto-escuro"
                                    disabled={!overridePhase}
                                    onClick={() => confirmarESalvar(overridePhase)}
                                >
                                    Salvar com esta classificação
                                </Button>
                            </>
                        )}
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </Card>
    );
};
