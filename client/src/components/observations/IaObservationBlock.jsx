import React, { useState, useRef, useEffect, useCallback } from 'react';
import { Mic, Square, Send, BookOpen, Pencil, Palette, Loader2, Save } from 'lucide-react';

import { apiService } from '@/services/api';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Card, CardContent } from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useToast } from '@/components/ui/use-toast';
import { AnalysisCard } from '@/components/observations/AnalysisCard';

const POLL_INTERVAL_MS = 2500;
const POLL_TIMEOUT_MS = 5 * 60 * 1000;

const CLASS_LABELS = {
  'pre-silabico': 'Pré-silábico',
  'silabico': 'Silábico',
  'transicao': 'Transição',
  'leitura-fluente': 'Leitura fluente',
  'alfabetico': 'Alfabético',
};

const CLASS_ID_TO_NAME = {
  1: 'transicao',
  2: 'leitura-fluente',
  3: 'pre-silabico',
  4: 'silabico',
  5: 'alfabetico',
};

const formatLabel = (className) => CLASS_LABELS[className] || className;

const buildClassesFromProbabilidades = (probabilidades, classePredita) => {
  if (!probabilidades) return [];
  // Meta-chaves do backend (`__predita__`, `__model_kind__`, …) não são classes
  // — guardam dados auxiliares no mesmo JSON pra evitar migrations.
  const entries = Object.entries(probabilidades).filter(([k]) => !/^__.+__$/.test(k));
  const items = entries
    .map(([id, prob]) => {
      const className = CLASS_ID_TO_NAME[Number(id)] || `classe_${id}`;
      return {
        id: String(id),
        className,
        label: formatLabel(className),
        probability: typeof prob === 'number' ? prob : Number(prob) || 0,
      };
    })
    .sort((a, b) => b.probability - a.probability);

  if (!items.length && classePredita) {
    items.push({
      id: classePredita,
      className: classePredita,
      label: formatLabel(classePredita),
      probability: 1,
    });
  }
  return items;
};

const formatProbability = (p) => `${Math.round(p * 100)}%`;

export const IaObservationBlock = ({ students, turmaId }) => {
  const { toast } = useToast();
  const [isRecording, setIsRecording] = useState(false);
  const [audioBlob, setAudioBlob] = useState(null);
  const [audioUrl, setAudioUrl] = useState(null);
  const [timer, setTimer] = useState('00:00');
  const [selectedStudent, setSelectedStudent] = useState('');

  const [modalOpen, setModalOpen] = useState(false);
  const [modalState, setModalState] = useState('analyzing');
  const [registroId, setRegistroId] = useState(null);
  const [classes, setClasses] = useState([]);
  const [selectedClass, setSelectedClass] = useState('');
  const [anotacoes, setAnotacoes] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');

  const mediaRecorderRef = useRef(null);
  const chunksRef = useRef([]);
  const recordingMimeTypeRef = useRef('');
  const timerIntervalRef = useRef(null);
  const pollTimeoutRef = useRef(null);
  const pollDeadlineRef = useRef(0);
  const cancelOnUnmountRef = useRef(null);

  const maxAudioBytes = 50 * 1024 * 1024;
  const allowedAudioTypes = [
    'audio/wav',
    'audio/x-wav',
    'audio/webm',
    'audio/ogg',
    'audio/mpeg',
    'audio/mp3',
    'audio/mp4',
    'audio/m4a',
  ];

  // O MediaRecorder padrão depende do navegador (Chrome/Firefox: webm/opus,
  // Safari: mp4/aac). Forçar 'audio/wav' no Blob causa NotSupportedError ao
  // tocar no <audio>, então selecionamos um tipo realmente suportado.
  const pickSupportedMimeType = () => {
    const candidates = [
      'audio/webm;codecs=opus',
      'audio/webm',
      'audio/mp4',
      'audio/ogg;codecs=opus',
      'audio/wav',
    ];
    for (const type of candidates) {
      if (typeof MediaRecorder !== 'undefined' && MediaRecorder.isTypeSupported(type)) {
        return type;
      }
    }
    return '';
  };

  const filenameForMimeType = (mimeType) => {
    const base = (mimeType || '').split(';')[0];
    switch (base) {
      case 'audio/webm':
        return 'leitura.webm';
      case 'audio/mp4':
        return 'leitura.m4a';
      case 'audio/ogg':
        return 'leitura.ogg';
      case 'audio/mpeg':
      case 'audio/mp3':
        return 'leitura.mp3';
      case 'audio/wav':
      default:
        return 'leitura.wav';
    }
  };

  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  useEffect(() => () => {
    if (audioUrl) URL.revokeObjectURL(audioUrl);
    if (pollTimeoutRef.current) clearTimeout(pollTimeoutRef.current);
    if (timerIntervalRef.current) clearInterval(timerIntervalRef.current);
    if (cancelOnUnmountRef.current) {
      apiService.cancelarAnaliseLeitura(cancelOnUnmountRef.current).catch(() => {});
    }
  }, [audioUrl]);

  const resetRecording = () => {
    if (audioUrl) {
      URL.revokeObjectURL(audioUrl);
      setAudioUrl(null);
    }
    setAudioBlob(null);
    setTimer('00:00');
  };

  const startRecording = async () => {
    resetRecording();
    try {
      // mono 48 kHz, AGC ligado (precisamos do ganho automático para vozes
      // infantis baixinhas), mas desabilitamos echoCancellation e
      // noiseSuppression — eles alteram a textura do sinal e o NaraNN, que
      // foi treinado em áudios do WhatsApp + tem seu próprio DeepFilterNet,
      // espera um perfil diferente. Denoise duplo distorce features de
      // hesitação/prolongamento.
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          sampleRate: 48000,
          echoCancellation: false,
          noiseSuppression: false,
          autoGainControl: true,
        },
      });
      const mimeType = pickSupportedMimeType();
      recordingMimeTypeRef.current = mimeType;
      mediaRecorderRef.current = mimeType
        ? new MediaRecorder(stream, { mimeType })
        : new MediaRecorder(stream);

      mediaRecorderRef.current.ondataavailable = (event) => {
        if (event.data.size > 0) chunksRef.current.push(event.data);
      };

      mediaRecorderRef.current.onstop = () => {
        const effectiveType =
          mediaRecorderRef.current?.mimeType ||
          recordingMimeTypeRef.current ||
          chunksRef.current[0]?.type ||
          '';
        const blob = new Blob(chunksRef.current, effectiveType ? { type: effectiveType } : {});
        setAudioBlob(blob);
        setAudioUrl(URL.createObjectURL(blob));
        chunksRef.current = [];
      };

      mediaRecorderRef.current.start();
      setIsRecording(true);

      let seconds = 0;
      timerIntervalRef.current = setInterval(() => {
        seconds += 1;
        setTimer(formatTime(seconds));
      }, 1000);

      toast({
        title: 'Gravação iniciada',
        description: 'Peça para a criança ler. Clique em "Parar" quando terminar.',
      });
    } catch (error) {
      console.error('Erro ao iniciar gravação:', error);
      toast({
        title: 'Erro ao iniciar gravação',
        description: 'Verifique se o microfone está conectado e permitido.',
        variant: 'destructive',
      });
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      mediaRecorderRef.current.stream.getTracks().forEach((track) => track.stop());
      clearInterval(timerIntervalRef.current);
      setIsRecording(false);
      toast({
        title: 'Gravação finalizada',
        description: 'Clique em "Enviar para IA" para analisar a leitura.',
      });
    }
  };

  const stopPolling = () => {
    if (pollTimeoutRef.current) {
      clearTimeout(pollTimeoutRef.current);
      pollTimeoutRef.current = null;
    }
  };

  const applyServerSnapshot = useCallback((snapshot) => {
    const itens = buildClassesFromProbabilidades(
      snapshot.probabilidades,
      snapshot.classe_predita,
    );
    setClasses(itens);
    if (itens.length > 0) {
      setSelectedClass(itens[0].className);
    } else if (snapshot.classe_predita) {
      setSelectedClass(snapshot.classe_predita);
    }
  }, []);

  const pollOnce = useCallback(async (id) => {
    try {
      const snapshot = await apiService.consultarAnaliseLeitura(id);
      if (snapshot.status === 'pendente') {
        if (Date.now() > pollDeadlineRef.current) {
          setModalState('failed');
          setErrorMsg('A análise demorou mais que o esperado. Tente novamente.');
          return;
        }
        pollTimeoutRef.current = setTimeout(() => pollOnce(id), POLL_INTERVAL_MS);
        return;
      }
      if (snapshot.status === 'falhou') {
        setModalState('failed');
        setErrorMsg('A análise falhou. Tente gravar novamente.');
        return;
      }
      // status confirmado/cancelado também caem aqui mas, se houver probabilidades, mostra
      applyServerSnapshot(snapshot);
      setModalState('ready');
    } catch (error) {
      if (error.status === 503) {
        // serviço caiu, retry
        if (Date.now() < pollDeadlineRef.current) {
          pollTimeoutRef.current = setTimeout(() => pollOnce(id), POLL_INTERVAL_MS);
          return;
        }
      }
      console.error('Erro ao consultar análise de leitura:', error);
      setModalState('failed');
      setErrorMsg(error.message || 'Não foi possível consultar a análise.');
    }
  }, [applyServerSnapshot]);

  const handleAnalyze = async () => {
    if (!selectedStudent) {
      toast({
        title: 'Selecione a criança',
        description: 'Escolha a criança antes de enviar o áudio.',
        variant: 'destructive',
      });
      return;
    }
    if (!audioBlob) {
      toast({
        title: 'Nenhum áudio gravado',
        description: 'Grave um áudio antes de enviar para análise.',
        variant: 'destructive',
      });
      return;
    }
    if (audioBlob.size > maxAudioBytes) {
      toast({
        title: 'Arquivo acima do limite',
        description: 'O áudio precisa ter até 50MB. Grave novamente com duração menor.',
        variant: 'destructive',
      });
      return;
    }
    const baseAudioType = (audioBlob.type || '').split(';')[0].trim().toLowerCase();
    if (baseAudioType && !allowedAudioTypes.includes(baseAudioType)) {
      toast({
        title: 'Formato não suportado',
        description: 'Envie um áudio nos formatos WAV, WEBM, OGG, MP3 ou M4A.',
        variant: 'destructive',
      });
      return;
    }

    setModalOpen(true);
    setModalState('analyzing');
    setErrorMsg('');
    setClasses([]);
    setSelectedClass('');
    setAnotacoes('');

    const formData = new FormData();
    const audioFilename = filenameForMimeType(audioBlob.type || recordingMimeTypeRef.current);
    formData.append('audio', audioBlob, audioFilename);
    formData.append('crianca_id', selectedStudent);
    if (turmaId) formData.append('turma_id', turmaId);

    try {
      const snapshot = await apiService.iniciarAnaliseLeitura(formData);
      setRegistroId(snapshot.id);
      cancelOnUnmountRef.current = snapshot.id;
      pollDeadlineRef.current = Date.now() + POLL_TIMEOUT_MS;
      pollOnce(snapshot.id);
    } catch (error) {
      console.error('Erro ao iniciar análise de leitura:', error);
      setModalState('failed');
      setErrorMsg(error.message || 'Não foi possível enviar o áudio.');
    }
  };

  const handleConfirm = async () => {
    if (!registroId || !selectedClass) return;
    setIsSaving(true);
    try {
      await apiService.confirmarAnaliseLeitura(registroId, {
        classe_escolhida: selectedClass,
        anotacoes_professora: anotacoes,
      });
      cancelOnUnmountRef.current = null;
      toast({
        title: 'Análise salva!',
        description: 'O áudio foi armazenado e a classificação registrada.',
      });
      setModalOpen(false);
      setRegistroId(null);
      resetRecording();
    } catch (error) {
      console.error('Erro ao confirmar análise de leitura:', error);
      toast({
        title: 'Erro ao salvar',
        description: error.message || 'Tente novamente.',
        variant: 'destructive',
      });
    } finally {
      setIsSaving(false);
    }
  };

  const handleCancel = async () => {
    stopPolling();
    if (registroId) {
      try {
        await apiService.cancelarAnaliseLeitura(registroId);
      } catch (error) {
        console.warn('Falha ao cancelar análise (ignorado):', error);
      }
    }
    cancelOnUnmountRef.current = null;
    setRegistroId(null);
    setModalOpen(false);
    setModalState('analyzing');
    setErrorMsg('');
    setClasses([]);
    setSelectedClass('');
    setAnotacoes('');
  };

  return (
    <div className="pt-8">
      <h2 className="text-xl font-bold text-center text-texto-escuro mb-2">Registros de Produções</h2>
      <p className="text-center text-texto-medio mb-6">
        Adicione registros individuais de desenhos, escritas e outras produções.
      </p>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <AnalysisCard
          icon={<Pencil className="h-6 w-6 text-roxo-principal" />}
          title="Análise da Escrita"
          type="escrita"
          students={students}
          turmaId={turmaId}
        />
        <AnalysisCard
          icon={<Palette className="h-6 w-6 text-roxo-principal" />}
          title="Análise do Desenho"
          type="desenho"
          students={students}
          turmaId={turmaId}
        />
        <Card>
          <CardContent className="p-6">
            <div className="flex items-center gap-3 mb-4">
              <BookOpen className="h-6 w-6 text-roxo-principal" />
              <h3 className="text-lg font-semibold text-texto-escuro">Análise da Leitura</h3>
            </div>

            <div className="space-y-4">
              <div>
                <Label className="font-semibold">Criança</Label>
                <Select onValueChange={setSelectedStudent} value={selectedStudent}>
                  <SelectTrigger className="mt-1 bg-white">
                    <SelectValue placeholder="Selecione a criança" />
                  </SelectTrigger>
                  <SelectContent>
                    {students.map((student) => (
                      <SelectItem key={student.id} value={student.id}>
                        {student.nome_completo}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="w-full p-6 border-2 border-dashed border-roxo-claro rounded-lg flex flex-col items-center justify-center gap-4 bg-white/50">
                {!isRecording && !audioBlob ? (
                  <Button
                    onClick={startRecording}
                    className="bg-[#8B5CF6] hover:bg-[#7C3AED] text-white"
                  >
                    <Mic className="mr-2 h-4 w-4" />
                    Iniciar Gravação
                  </Button>
                ) : isRecording ? (
                  <>
                    <div className="text-2xl font-bold text-[#8B5CF6] mb-2">{timer}</div>
                    <Button
                      onClick={stopRecording}
                      className="bg-red-500 hover:bg-red-600 text-white"
                    >
                      <Square className="mr-2 h-4 w-4" />
                      Parar Gravação
                    </Button>
                  </>
                ) : (
                  <div className="flex flex-col items-center gap-4 w-full max-w-[400px]">
                    {audioUrl && (
                      <div className="w-full space-y-2">
                        <p className="text-sm font-medium text-texto-medio text-center mb-3">
                          Áudio gravado:
                        </p>
                        <audio
                          controls
                          src={audioUrl}
                          className="w-full"
                          onError={() => {
                            console.warn('Não foi possível reproduzir o áudio gravado neste navegador.');
                          }}
                        >
                          Seu navegador não suporta a reprodução do áudio.
                        </audio>
                      </div>
                    )}
                    <div className="flex flex-col sm:flex-row gap-2 w-full">
                      <Button
                        onClick={startRecording}
                        variant="outline"
                        className="border-[#8B5CF6] text-[#8B5CF6] hover:bg-[#8B5CF6] hover:text-white w-full sm:flex-1"
                      >
                        <Mic className="mr-2 h-4 w-4" />
                        Gravar Novamente
                      </Button>
                      <Button
                        onClick={handleAnalyze}
                        className="bg-[#8B5CF6] hover:bg-[#7C3AED] text-white w-full sm:flex-1"
                      >
                        <Send className="mr-2 h-4 w-4" />
                        Enviar para IA
                      </Button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      <Dialog
        open={modalOpen}
        onOpenChange={(open) => {
          if (!open && !isSaving) handleCancel();
        }}
      >
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Análise da Leitura</DialogTitle>
            <DialogDescription>
              {modalState === 'analyzing' && 'Analisando o áudio. Isso pode levar até 1 minuto.'}
              {modalState === 'ready' && 'Confirme a classificação detectada pela IA. Você pode alterar antes de salvar.'}
              {modalState === 'failed' && 'Não foi possível concluir a análise.'}
            </DialogDescription>
          </DialogHeader>

          {modalState === 'analyzing' && (
            <div className="flex flex-col items-center justify-center py-8 gap-3 text-texto-medio">
              <Loader2 className="h-8 w-8 animate-spin text-roxo-principal" />
              <p className="text-sm">Aguarde enquanto a IA processa a leitura…</p>
            </div>
          )}

          {modalState === 'failed' && (
            <div className="py-4 text-sm text-red-600 text-center">{errorMsg || 'Erro inesperado.'}</div>
          )}

          {modalState === 'ready' && (
            <div className="space-y-4">
              <div>
                <Label className="font-semibold">Classificação</Label>
                <RadioGroup
                  value={selectedClass}
                  onValueChange={setSelectedClass}
                  className="mt-2 space-y-2"
                >
                  {classes.map((opt, idx) => (
                    <label
                      key={opt.id}
                      htmlFor={`leitura-classe-${opt.id}`}
                      className="flex items-center justify-between gap-3 p-3 rounded-md border bg-white hover:bg-roxo-claro/5 cursor-pointer"
                    >
                      <div className="flex items-center gap-3">
                        <RadioGroupItem id={`leitura-classe-${opt.id}`} value={opt.className} />
                        <span className="font-medium text-texto-escuro">
                          {opt.label}
                          {idx === 0 && (
                            <span className="ml-2 text-xs text-roxo-principal">(sugerida pela IA)</span>
                          )}
                        </span>
                      </div>
                      <span className="text-sm text-texto-medio tabular-nums">
                        {formatProbability(opt.probability)}
                      </span>
                    </label>
                  ))}
                </RadioGroup>
              </div>

              <div>
                <Label className="font-semibold">Anotações adicionais (opcional)</Label>
                <Textarea
                  className="mt-1 bg-white"
                  value={anotacoes}
                  onChange={(e) => setAnotacoes(e.target.value)}
                  placeholder="Observações complementares sobre a leitura da criança…"
                />
              </div>
            </div>
          )}

          <DialogFooter className="gap-2">
            {modalState === 'ready' ? (
              <>
                <Button variant="outline" onClick={handleCancel} disabled={isSaving}>
                  Cancelar
                </Button>
                <Button
                  onClick={handleConfirm}
                  disabled={!selectedClass || isSaving}
                  className="bg-[#8B5CF6] hover:bg-[#7C3AED] text-white"
                >
                  {isSaving ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Salvando…
                    </>
                  ) : (
                    <>
                      <Save className="mr-2 h-4 w-4" />
                      Salvar Registro
                    </>
                  )}
                </Button>
              </>
            ) : (
              <Button variant="outline" onClick={handleCancel}>
                Fechar
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};