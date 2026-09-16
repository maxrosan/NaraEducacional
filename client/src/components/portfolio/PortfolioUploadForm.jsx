import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { apiClient } from '@/lib/apiClient';
import { useToast } from '@/components/ui/use-toast';
import imageCompression from 'browser-image-compression';

import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Checkbox } from '@/components/ui/checkbox';
import { UploadCloud, Video, X, Loader2, Save, CheckCircle, AlertTriangle } from 'lucide-react';
import { Progress } from '@/components/ui/progress';

// URL base da API Django (usa proxy em desenvolvimento)
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';


// Alguns navegadores/SOs (Chrome no Windows/Android, por exemplo) não reconhecem
// o mime type de .heic/.heif e retornam file.type vazio. Por isso validamos também
// pela extensão do nome do arquivo, não só pelo `type`.
const HEIC_EXTENSIONS = ['.heic', '.heif'];
const HEIC_MIME_TYPES = ['image/heic', 'image/heif', 'image/heic-sequence', 'image/heif-sequence'];

const isHeicFile = (file) => {
  const type = (file.type || '').toLowerCase();
  const name = (file.name || '').toLowerCase();
  return HEIC_MIME_TYPES.includes(type) || HEIC_EXTENSIONS.some((ext) => name.endsWith(ext));
};

const isImageFile = (file) => {
  const type = (file.type || '').toLowerCase();
  return type.startsWith('image') || isHeicFile(file);
};

const isVideoFile = (file) => (file.type || '').toLowerCase().startsWith('video');

export const PortfolioUploadForm = ({ students = [], turmaId, onUploadComplete }) => {
  const { toast } = useToast();

  // ALTERAÇÃO: fileStudentIds agora é string[][] — cada arquivo tem um array de IDs selecionados
  const [fileStudentIds, setFileStudentIds] = useState([]);   // string[][]
  const [fileApplyAll, setFileApplyAll]     = useState([]);   // boolean[]
  const [fileCaptions, setFileCaptions]     = useState([]);   // string[]
  const [files, setFiles]                   = useState([]);
  const [previews, setPreviews]             = useState([]);
  const [fileStatuses, setFileStatuses]     = useState([]);
  const [isUploading, setIsUploading]       = useState(false);
  const [uploadProgress, setUploadProgress] = useState({ current: 0, total: 0 });
  const [uploadStatus, setUploadStatus]     = useState('idle'); // 'idle' | 'uploading' | 'saving' | 'done'
  const [isCompressing, setIsCompressing]   = useState(false);
  const [compressionStats, setCompressionStats] = useState(null);


  const handleFileChange = async (event) => {
    const newFiles = Array.from(event.target.files);

    const maxOriginalSizeBytes = 2 * 1024 * 1024;
    const compressionOptions = {
      maxSizeMB: 0.15,
      maxWidthOrHeight: 1600,
      useWebWorker: true,
      fileType: 'image/jpeg',
    };

    setIsCompressing(true);
    let totalOriginal = 0;
    let totalCompressed = 0;

    try {
      const processedFiles = await Promise.all(
        newFiles.map(async (file) => {
          if (isVideoFile(file)) return file;

          if (isImageFile(file)) {
            // HEIC/HEIF: a maioria dos navegadores (fora Safari) não sabe decodificar
            // esse formato via canvas, então a biblioteca de compressão falharia.
            // Enviamos o arquivo original sem tentar comprimir no cliente.
            if (isHeicFile(file)) {
              totalOriginal += file.size;
              totalCompressed += file.size;
              return file;
            }
            try {
              const originalSize = file.size;
              totalOriginal += originalSize;
              if (originalSize > maxOriginalSizeBytes) {
                const compressedFile = await imageCompression(file, compressionOptions);
                totalCompressed += compressedFile.size;
                return compressedFile;
              }
              totalCompressed += originalSize;
              return file;
            } catch (compError) {
              console.warn(`[Compressão] Erro ao comprimir ${file.name}:`, compError);
              totalCompressed += file.size;
              return file;
            }
          }
          return file;
        })
      );

      if (totalOriginal > 0) {
        const reduction = ((totalOriginal - totalCompressed) / totalOriginal * 100).toFixed(1);
        setCompressionStats({
          original:   (totalOriginal   / 1024 / 1024).toFixed(2),
          compressed: (totalCompressed / 1024 / 1024).toFixed(2),
          reduction,
        });
      }

      setFiles(prev        => [...prev, ...processedFiles]);
      setFileStatuses(prev => [...prev, ...processedFiles.map(() => ({ status: 'pending', error: '' }))]);
      // ALTERAÇÃO: cada arquivo começa com array vazio de IDs selecionados
      setFileStudentIds(prev => [...prev, ...processedFiles.map(() => [])]);
      setFileCaptions(prev   => [...prev, ...processedFiles.map(() => '')]);
      setFileApplyAll(prev   => [...prev, ...processedFiles.map(() => false)]);

      const newPreviews = processedFiles.map(file => ({
        url:  URL.createObjectURL(file),
        type: isVideoFile(file) ? 'video' : 'image',
        name: file.name,
        // HEIC/HEIF não renderiza em <img> fora do Safari — sinaliza pra UI mostrar um placeholder.
        unsupportedPreview: isHeicFile(file),
        size: file.size,
      }));
      setPreviews(prev => [...prev, ...newPreviews]);

    } catch (error) {
      console.error('[Compressão] Erro geral:', error);
      toast({
        variant: 'destructive',
        title: 'Erro ao processar arquivos',
        description: 'Houve um erro ao processar os arquivos. Tente novamente.',
      });
    } finally {
      setIsCompressing(false);
    }
  };

  const removeFile = (index) => {
    setFiles(prev         => prev.filter((_, i) => i !== index));
    setPreviews(prev      => prev.filter((_, i) => i !== index));
    setFileStatuses(prev  => prev.filter((_, i) => i !== index));
    setFileStudentIds(prev => prev.filter((_, i) => i !== index));
    setFileCaptions(prev  => prev.filter((_, i) => i !== index));
    setFileApplyAll(prev  => prev.filter((_, i) => i !== index));
  };

  const resetForm = () => {
    setFiles([]);
    setPreviews([]);
    setFileStatuses([]);
    setFileStudentIds([]);
    setFileCaptions([]);
    setFileApplyAll([]);
  };

  const updateFileStatus = (index, status, error = '') => {
    setFileStatuses(prev => prev.map((item, i) => i === index ? { ...item, status, error } : item));
  };

  const updateFileCaption = (index, value) => {
    setFileCaptions(prev => prev.map((item, i) => i === index ? value : item));
  };

  const updateFileApplyAll = (index, value) => {
    setFileApplyAll(prev => prev.map((item, i) => i === index ? value : item));
  };

  // ALTERAÇÃO: toggle de um ID individual no array de selecionados daquele arquivo
  const toggleStudentForFile = (fileIndex, studentId) => {
    setFileStudentIds(prev => prev.map((selectedIds, i) => {
      if (i !== fileIndex) return selectedIds;
      return selectedIds.includes(studentId)
        ? selectedIds.filter(id => id !== studentId)   // desmarca
        : [...selectedIds, studentId];                  // marca
    }));
  };

  const handleSave = async () => {
    if (files.length === 0) {
      toast({
        variant: 'destructive',
        title: 'Campos obrigatórios',
        description: 'Por favor, adicione pelo menos um arquivo.',
      });
      return;
    }

    // ALTERAÇÃO: valida que cada arquivo tem ao menos uma criança marcada (ou "Selecionar todos")
    const primeiroSemAluno = fileStudentIds.findIndex(
      (ids, index) => !fileApplyAll[index] && ids.length === 0
    );
    if (primeiroSemAluno !== -1) {
      toast({
        variant: 'destructive',
        title: 'Campos obrigatórios',
        description: 'Selecione ao menos uma criança para cada arquivo antes de salvar.',
      });
      return;
    }

    if (fileApplyAll.some(Boolean) && students.length === 0) {
      toast({
        variant: 'destructive',
        title: 'Nenhuma criança disponível',
        description: 'Não há crianças na turma atual para aplicar a seleção em lote.',
      });
      return;
    }

    setIsUploading(true);
    setUploadProgress({ current: 0, total: files.length });
    setUploadStatus('uploading');

    const { data: { user } } = await apiClient.auth.getUser();
    if (!user) {
      toast({
        variant: 'destructive',
        title: 'Sessão expirada',
        description: 'Por favor, faça login novamente.',
      });
      setIsUploading(false);
      setUploadStatus('idle');
      return;
    }

    const professor_id   = user.id;
    const professor_nome = user.user_metadata?.nome || user.user_metadata?.nome_completo || user.email;

    try {
      const uploadTasks = files.map((file, index) => (async () => {
        updateFileStatus(index, 'uploading');

        const applyAll    = fileApplyAll[index];
        const selectedIds = fileStudentIds[index]; // string[]

        // ALTERAÇÃO: monta o payload com todas as crianças selecionadas para este arquivo
        const criancasPayload = applyAll
          ? students.map(item => ({
              crianca_id:   item.id,
              crianca_nome: item.nome_completo,
              legenda:      fileCaptions[index] || '',
            }))
          : selectedIds.map(id => {
              const student = students.find(s => s.id === id);
              return {
                crianca_id:   id,
                crianca_nome: student?.nome_completo || '',
                legenda:      fileCaptions[index] || '',
              };
            });

        if (criancasPayload.length === 0) {
          updateFileStatus(index, 'error', 'Nenhuma criança selecionada para este arquivo.');
          throw new Error('Nenhuma criança selecionada');
        }

        const formData = new FormData();
        formData.append('arquivo',        file);
        formData.append('turma_id',       turmaId);
        formData.append('professora_id',  professor_id);
        formData.append('professora_nome', professor_nome);
        formData.append('tipo_midia',     isVideoFile(file) ? 'video' : 'foto');
        formData.append('data_registro',  new Date().toISOString().split('T')[0]);
        formData.append('criancas',       JSON.stringify(criancasPayload));

        const getCsrfToken = () => {
          const match = document.cookie.match(/csrftoken=([^;]+)/);
          return match ? match[1] : '';
        };

        try {
          const response = await fetch(`${API_BASE_URL}/api/portfolio/upload/`, {
            method: 'POST',
            credentials: 'include',
            headers: { 'X-CSRFToken': getCsrfToken() },
            body: formData,
          });

          if (!response.ok) {
            let message = 'Erro ao enviar arquivo';
            try {
              const errorData = await response.json();
              message = errorData.message || errorData.error || message;
            } catch {
              message = `${message} (${response.status})`;
            }
            updateFileStatus(index, 'error', message);
            throw new Error(message);
          }

          updateFileStatus(index, 'done');
        } finally {
          setUploadProgress(prev => ({ current: prev.current + 1, total: prev.total }));
        }
      })());

      const results = await Promise.allSettled(uploadTasks);
      const failed  = results.filter(r => r.status === 'rejected');

      if (failed.length > 0) {
        const firstMessage = failed[0]?.reason?.message;
        setUploadStatus('idle');
        toast({
          variant: 'destructive',
          title: 'Erro ao salvar',
          description: firstMessage
            ? `${failed.length} arquivo(s) falharam. ${firstMessage}`
            : `${failed.length} arquivo(s) falharam. Verifique os itens marcados e tente novamente.`,
        });
        return;
      }

      setUploadStatus('done');
      toast({
        title: '✅ Sucesso!',
        description: `${files.length} arquivo(s) adicionado(s) ao portfólio.`,
        className: 'bg-green-100 border-green-300 text-green-800',
      });
      if (onUploadComplete) onUploadComplete();

      setTimeout(() => {
        resetForm();
        setUploadStatus('idle');
        setUploadProgress({ current: 0, total: 0 });
      }, 1000);

    } catch (error) {
      setUploadStatus('idle');
      toast({ variant: 'destructive', title: 'Erro ao salvar', description: error.message });
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="space-y-6"
    >
      {/* ── Área de drop ─────────────────────────────────────────── */}
      <div className="space-y-2">
        <Label className="font-semibold">Mídia (fotos ou vídeos)</Label>
        <div className="relative border-2 border-dashed border-gray-300 rounded-lg p-6 text-center cursor-pointer hover:border-roxo-principal transition-colors">
          {isCompressing ? (
            <>
              <Loader2 className="mx-auto h-12 w-12 text-roxo-principal animate-spin" />
              <p className="mt-2 text-sm text-roxo-principal font-medium">Otimizando imagens...</p>
              <p className="text-xs text-gray-500">Aguarde enquanto comprimimos para melhor performance</p>
            </>
          ) : (
            <>
              <UploadCloud className="mx-auto h-12 w-12 text-gray-400" />
              <p className="mt-2 text-sm text-gray-600">Arraste e solte os arquivos ou clique para selecionar</p>
              <p className="text-xs text-gray-500">Você pode enviar múltiplas imagens ou vídeos (compressão automática)</p>
            </>
          )}
          <Input
            id="file-upload"
            type="file"
            multiple
            accept="image/*,video/*,.heic,.heif"
            className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
            onChange={handleFileChange}
            disabled={isCompressing}
          />
        </div>
        {compressionStats && (
          <div className="text-xs text-gray-500 flex items-center gap-2 justify-center">
            <span>Compressão: {compressionStats.original}MB → {compressionStats.compressed}MB</span>
            <Badge variant="secondary" className="text-xs">-{compressionStats.reduction}%</Badge>
          </div>
        )}
      </div>

      {/* ── Lista de arquivos selecionados ────────────────────────── */}
      <AnimatePresence>
        {previews.length > 0 && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4"
          >
            {previews.map((preview, index) => (
              <motion.div
                key={preview.name + index}
                initial={{ opacity: 0, scale: 0.8 }}
                animate={{ opacity: 1, scale: 1 }}
                className="group"
              >
                {/* Thumbnail */}
                <div className="relative">
                  {fileStatuses[index]?.status && fileStatuses[index].status !== 'error' && (
                    <div className="absolute bottom-1 left-1 z-10 rounded-full bg-white/90 p-1 shadow-sm">
                      {fileStatuses[index].status === 'uploading' && (
                        <Loader2 className="h-4 w-4 animate-spin text-roxo-principal" />
                      )}
                      {fileStatuses[index].status === 'done' && (
                        <CheckCircle className="h-4 w-4 text-green-600" />
                      )}
                    </div>
                  )}
                  <div className="absolute top-1 right-1 z-10">
                    <Button
                      size="icon"
                      variant="destructive"
                      className="h-6 w-6 rounded-full"
                      onClick={() => removeFile(index)}
                    >
                      <X className="h-4 w-4" />
                    </Button>
                  </div>
                  {preview.type === 'video' ? (
                    <div className="w-full h-32 bg-black rounded-lg flex items-center justify-center">
                      <Video className="h-10 w-10 text-white" />
                    </div>
                  ) : preview.unsupportedPreview ? (
                    <div className="w-full h-32 bg-gray-100 rounded-lg flex flex-col items-center justify-center text-center px-2">
                      <UploadCloud className="h-8 w-8 text-gray-400" />
                      <span className="text-[10px] text-gray-500 mt-1">Pré-visualização indisponível (HEIC)</span>
                    </div>
                  ) : (
                    <img
                      src={preview.url}
                      alt={preview.name}
                      className="w-full h-32 object-cover rounded-lg"
                    />
                  )}
                </div>

                <p className="text-xs text-gray-500 truncate mt-1">{preview.name}</p>

                {/* ── Seleção de alunos ── */}
                <div className="mt-3 space-y-2">
                  <div className="space-y-1">
                    {/* Cabeçalho: label + "Selecionar todos" */}
                    <div className="flex items-center justify-between">
                      <Label className="text-xs text-gray-600">Aluno</Label>
                      <div className="flex items-center gap-2 text-xs text-gray-600">
                        <Checkbox
                          id={`select-all-${index}`}
                          checked={fileApplyAll[index] || false}
                          onCheckedChange={(checked) => updateFileApplyAll(index, checked === true)}
                          disabled={students.length === 0}
                        />
                        <Label htmlFor={`select-all-${index}`} className="text-xs text-gray-600 cursor-pointer">
                          Selecionar todos
                        </Label>
                      </div>
                    </div>

                    {/* ALTERAÇÃO: lista de checkboxes em vez de Select */}
                    {students.length === 0 ? (
                      <p className="text-xs text-gray-400 italic">Nenhuma criança disponível</p>
                    ) : fileApplyAll[index] ? (
                      <p className="text-xs text-green-700">
                        Todas as crianças da turma serão vinculadas ({students.length}).
                      </p>
                    ) : (
                      <div className="border border-gray-200 rounded-md p-2 space-y-1 max-h-36 overflow-y-auto">
                        {students.map((student) => {
                          const isChecked = (fileStudentIds[index] || []).includes(student.id);
                          return (
                            <label
                              key={student.id}
                              className="flex items-center gap-2 cursor-pointer hover:bg-gray-50 rounded px-1 py-0.5"
                            >
                              <Checkbox
                                checked={isChecked}
                                onCheckedChange={() => toggleStudentForFile(index, student.id)}
                              />
                              <span className="text-xs text-gray-700 leading-tight">
                                {student.nome_completo}
                              </span>
                            </label>
                          );
                        })}
                      </div>
                    )}

                    {/* Contador de selecionados */}
                    {!fileApplyAll[index] && students.length > 0 && (
                      <p className="text-xs text-gray-500">
                        {(fileStudentIds[index] || []).length === 0
                          ? 'Nenhuma criança selecionada'
                          : `${(fileStudentIds[index] || []).length} criança(s) selecionada(s)`}
                      </p>
                    )}
                  </div>

                  {/* Legenda */}
                  <div className="space-y-1">
                    <Label className="text-xs text-gray-600">Legenda (opcional)</Label>
                    <Textarea
                      value={fileCaptions[index] || ''}
                      onChange={(e) => updateFileCaption(index, e.target.value)}
                      rows={2}
                      placeholder="Descreva o momento ou destaque a observação."
                    />
                  </div>

                  {/* Erro */}
                  {fileStatuses[index]?.status === 'error' && fileStatuses[index]?.error && (
                    <div className="flex items-center gap-2 text-xs text-red-600 leading-tight">
                      <AlertTriangle className="h-4 w-4 shrink-0" />
                      <span>{fileStatuses[index].error}</span>
                    </div>
                  )}
                </div>
              </motion.div>
            ))}
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── Barra de progresso ────────────────────────────────────── */}
      <AnimatePresence>
        {uploadStatus !== 'idle' && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="space-y-2 p-4 bg-gray-50 rounded-lg border"
          >
            <div className="flex items-center justify-between text-sm">
              <span className="flex items-center gap-2">
                {uploadStatus === 'uploading' && (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin text-roxo-principal" />
                    <span>Enviando arquivos... ({uploadProgress.current}/{uploadProgress.total})</span>
                  </>
                )}
                {uploadStatus === 'saving' && (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin text-roxo-principal" />
                    <span>Salvando no portfólio...</span>
                  </>
                )}
                {uploadStatus === 'done' && (
                  <>
                    <CheckCircle className="h-4 w-4 text-green-600" />
                    <span className="text-green-600">Upload concluído!</span>
                  </>
                )}
              </span>
              {uploadStatus === 'uploading' && uploadProgress.total > 0 && (
                <span className="text-gray-500">
                  {Math.round((uploadProgress.current / uploadProgress.total) * 100)}%
                </span>
              )}
            </div>
            <Progress
              value={
                uploadStatus === 'done'
                  ? 100
                  : uploadStatus === 'saving'
                  ? 90
                  : uploadProgress.total > 0
                  ? (uploadProgress.current / uploadProgress.total) * 80
                  : 0
              }
              className="h-2"
              indicatorClassName={uploadStatus === 'done' ? 'bg-green-500' : 'bg-roxo-principal'}
            />
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── Botão salvar ──────────────────────────────────────────── */}
      <div className="flex justify-end">
        <Button size="lg" onClick={handleSave} disabled={isUploading}>
          {isUploading ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              <span>Salvando...</span>
            </>
          ) : (
            <>
              <Save className="mr-2 h-4 w-4" />
              <span>Salvar no Portfólio</span>
            </>
          )}
        </Button>
      </div>
    </motion.div>
  );
};