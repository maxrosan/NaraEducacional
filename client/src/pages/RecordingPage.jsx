import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Helmet } from 'react-helmet-async';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { ArrowLeft, Sparkles, Save, Loader2, Square, Trash2, Play, Pause, Users } from 'lucide-react';

import { apiClient } from '@/lib/apiClient';
import { useAuth } from '@/contexts/AuthContext';

import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { useToast } from '@/components/ui/use-toast';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';

import NaraIaIcon from '@/components/NaraIaIcon';
import NoPeriodoModal from '@/components/NoPeriodoModal';
import ProfessorNavbar from '@/components/teacher/ProfessorNavBar';
import { usePeriodoAvaliativo } from '@/hooks/usePeriodoAvaliativo';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || import.meta.env.VITE_API_URL || '';
const getCsrfToken = () => {
  const match = document.cookie.match(/csrftoken=([^;]+)/);
  return match ? match[1] : '';
};

const getAudioFilename = (audioBlob) => {
  const mimeType = audioBlob?.type?.split(';')[0] || '';
  const extensionByType = {
    'audio/webm': 'webm',
    'audio/ogg': 'ogg',
    'audio/mpeg': 'mp3',
    'audio/mp3': 'mp3',
    'audio/mp4': 'm4a',
    'audio/m4a': 'm4a',
    'audio/wav': 'wav',
    'audio/x-wav': 'wav',
  };

  const extension = extensionByType[mimeType] || 'webm';
  return `observacao_professora.${extension}`;
};

// ── Mic icon SVG ──
const MicIcon = ({ size = 28, color = 'currentColor' }) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill="none"
    stroke={color}
    strokeWidth="1.8"
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    <rect x="9" y="1" width="6" height="12" rx="3" />
    <path d="M19 10v1a7 7 0 0 1-14 0v-1" />
    <line x1="12" y1="18" x2="12" y2="22" />
  </svg>
);

// ── Animated dot ring ──
const NUM_DOTS = 24;

const VoiceButton = ({ state, onClick }) => {
  const [levels, setLevels] = useState(Array(NUM_DOTS).fill(0));
  const animRef = useRef(null);
  const timeRef = useRef(0);

  useEffect(() => {
    if (state !== 'listening') {
      setLevels(Array(NUM_DOTS).fill(0));
      return;
    }
    let running = true;
    const animate = () => {
      if (!running) return;
      timeRef.current += 0.06;
      const t = timeRef.current;
      const newLevels = Array.from({ length: NUM_DOTS }, (_, i) => {
        const angle = (i / NUM_DOTS) * Math.PI * 2;
        const wave1 = Math.sin(t * 2.2 + angle * 3) * 0.4;
        const wave2 = Math.sin(t * 3.5 + angle * 1.7) * 0.3;
        const wave3 = Math.sin(t * 1.3 + angle * 5) * 0.2;
        const noise = Math.random() * 0.1;
        return Math.max(0, Math.min(1, 0.35 + wave1 + wave2 + wave3 + noise));
      });
      setLevels(newLevels);
      animRef.current = requestAnimationFrame(animate);
    };
    animRef.current = requestAnimationFrame(animate);
    return () => {
      running = false;
      if (animRef.current) cancelAnimationFrame(animRef.current);
    };
  }, [state]);

  const RADIUS = 72;
  const CENTER = 90;
  const DOT_BASE = 2.2;
  const DOT_MAX = 5.5;

  return (
    <div className="relative flex items-center justify-center">
      <svg
        width={CENTER * 2}
        height={CENTER * 2}
        className="absolute"
        style={{ pointerEvents: 'none' }}
      >
        {levels.map((level, i) => {
          const angle = (i / NUM_DOTS) * Math.PI * 2 - Math.PI / 2;
          const cx = CENTER + Math.cos(angle) * RADIUS;
          const cy = CENTER + Math.sin(angle) * RADIUS;
          const r = state === 'listening' ? DOT_BASE + level * (DOT_MAX - DOT_BASE) : DOT_BASE;
          const opacity = state === 'listening' ? 0.35 + level * 0.65 : 0.22;
          return (
            <circle
              key={i}
              cx={cx}
              cy={cy}
              r={r}
              fill={state === 'listening' ? '#8A63D2' : '#D7CDEB'}
              opacity={opacity}
              style={{
                transition:
                  state === 'idle'
                    ? 'r 0.5s ease, fill 0.4s ease, opacity 0.5s ease'
                    : 'fill 0.15s ease',
              }}
            />
          );
        })}
      </svg>

      <button
        onClick={onClick}
        className="relative z-10 flex items-center justify-center rounded-full transition-all duration-300 focus:outline-none"
        style={{
          width: 96,
          height: 96,
          background:
            state === 'listening'
              ? 'radial-gradient(circle, #F5F3FA 0%, #D7CDEB 100%)'
              : 'radial-gradient(circle, #fafafa 0%, #F5F3FA 100%)',
          boxShadow:
            state === 'listening'
              ? '0 0 0 3px rgba(138,99,210,0.15), 0 4px 20px rgba(138,99,210,0.12)'
              : '0 0 0 1px rgba(0,0,0,0.06), 0 2px 12px rgba(0,0,0,0.04)',
        }}
        aria-label={state === 'listening' ? 'Parar gravação' : 'Iniciar gravação'}
      >
        {state === 'listening' && (
          <>
            <span
              className="absolute inset-0 rounded-full"
              style={{
                border: '2px solid rgba(138,99,210,0.15)',
                animation: 'voicePulse 2s ease-out infinite',
              }}
            />
            <span
              className="absolute inset-0 rounded-full"
              style={{
                border: '2px solid rgba(138,99,210,0.10)',
                animation: 'voicePulse 2s ease-out infinite 0.6s',
              }}
            />
          </>
        )}

        {state === 'listening' ? (
          <Square className="h-7 w-7 text-red-500" />
        ) : (
          <MicIcon size={30} color="#8A63D2" />
        )}
      </button>

      <style>{`
        @keyframes voicePulse {
          0% { transform: scale(1); opacity: 1; }
          100% { transform: scale(1.45); opacity: 0; }
        }
      `}</style>
    </div>
  );
};

// ── Main page ──
const RecordingPage = () => {
  const navigate = useNavigate();
  const { toast } = useToast();
  const { user, turmaAtiva } = useAuth();

  // Turma & alunos
  const [turmas, setTurmas] = useState([]);
  const [alunos, setAlunos] = useState([]);
  const [selectedTurmaId, setSelectedTurmaId] = useState('');
  const [institutionId, setInstitutionId] = useState(null);

  // Recording
  const [isRecording, setIsRecording] = useState(false);
  const [audioBlob, setAudioBlob] = useState(null);
  const [recordingTime, setRecordingTime] = useState(0);
  const [mediaRecorder, setMediaRecorder] = useState(null);
  const [saving, setSaving] = useState(false);

  // Transcription result
  const [transcricaoResultado, setTranscricaoResultado] = useState(null);
  const [editandoTranscricao, setEditandoTranscricao] = useState(false);

  // Audio playback
  const [isPlaying, setIsPlaying] = useState(false);
  const [audioElement, setAudioElement] = useState(null);

  const { periodoAtivo, loading: periodoLoading } = usePeriodoAvaliativo(institutionId);

  // Refs
  const intervalRef = useRef(null);
  const chunksRef = useRef([]);
  const startTimeRef = useRef(null);

  // ── Fetch turmas & alunos ──
  const fetchInitialData = useCallback(async () => {
    if (!user) return;
    try {
      const { data: turmasData, error: turmasError } = await apiClient
        .from('turmas')
        .select('id, nome, faixa_etaria, instituicao_id, usuario_turmas!inner(usuario_id)')
        .eq('usuario_turmas.usuario_id', user.id);

      if (turmasError) throw turmasError;
      const formattedTurmas = turmasData.filter(Boolean);

      if (!formattedTurmas || formattedTurmas.length === 0) {
        toast({ title: 'Nenhuma turma encontrada', description: 'Você não está vinculado a nenhuma turma.' });
        setTurmas([]);
        return;
      }

      setTurmas(formattedTurmas);
      if (formattedTurmas.length > 0) setInstitutionId(formattedTurmas[0].instituicao_id);
      // Auto-select: turmaAtiva do contexto ou primeira turma
      const turmaAlvo = formattedTurmas.find(t => t.id === turmaAtiva?.id) || formattedTurmas[0];
      setSelectedTurmaId(turmaAlvo.id);
      const { data: alunosData } = await apiClient.from('criancas').select('id, nome_completo').eq('turma_id', turmaAlvo.id);
      setAlunos(alunosData || []);
    } catch (error) {
    toast({ variant: 'destructive', title: 'Erro ao carregar dados', description: error.message });
  }
}, [user, toast, turmaAtiva]);

useEffect(() => {
  fetchInitialData();
}, [fetchInitialData]);

const handleTurmaChange = async (turmaId) => {
  setSelectedTurmaId(turmaId);
  resetarEstado();
  const { data: alunosData } = await apiClient.from('criancas').select('id, nome_completo').eq('turma_id', turmaId);
  setAlunos(alunosData || []);
};

useEffect(() => {
  if (!turmas.length) return;
  if (turmaAtiva?.id && turmaAtiva.id !== selectedTurmaId) {
    handleTurmaChange(turmaAtiva.id);
  }
}, [turmaAtiva?.id, turmas]);

// ── Format time ──
const formatarTempo = (segundos) => {
  const mins = Math.floor(segundos / 60);
  const secs = segundos % 60;
  return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
};

// ── Auto-detect microphone ──
const detectarMicrofone = async () => {
  try {
    await navigator.mediaDevices.getUserMedia({ audio: true });
    return true;
  } catch {
    return false;
  }
};

// ── Start recording ──
const iniciarGravacao = async () => {
  // Clear previous state
  setAudioBlob(null);
  setRecordingTime(0);
  chunksRef.current = [];
  startTimeRef.current = null;
  if (intervalRef.current) {
    clearInterval(intervalRef.current);
    intervalRef.current = null;
  }

  try {
    const constraints = {
      audio: {
        echoCancellation: true,
        noiseSuppression: true,
        sampleRate: 44100,
      },
    };
    const stream = await navigator.mediaDevices.getUserMedia(constraints);

    let mimeType = 'audio/webm';
    if (MediaRecorder.isTypeSupported('audio/webm;codecs=opus')) {
      mimeType = 'audio/webm;codecs=opus';
    } else if (MediaRecorder.isTypeSupported('audio/mp4')) {
      mimeType = 'audio/mp4';
    } else if (MediaRecorder.isTypeSupported('audio/wav')) {
      mimeType = 'audio/wav';
    }

    const recorder = new MediaRecorder(stream, { mimeType });

    recorder.ondataavailable = (event) => {
      if (event.data.size > 0) {
        chunksRef.current.push(event.data);
      }
    };

    recorder.onstop = () => {
      if (chunksRef.current.length > 0) {
        const blob = new Blob(chunksRef.current, { type: mimeType });
        setAudioBlob(blob);
      } else {
        toast({ title: 'Erro na gravação', description: 'Nenhum áudio foi gravado. Tente novamente.', variant: 'destructive' });
      }
      stream.getTracks().forEach((track) => track.stop());
    };

    recorder.onstart = () => {
      startTimeRef.current = Date.now();
      setIsRecording(true);
      setRecordingTime(0);
      intervalRef.current = setInterval(() => {
        if (startTimeRef.current) {
          const elapsed = Math.floor((Date.now() - startTimeRef.current) / 1000);
          setRecordingTime(elapsed);
        }
      }, 1000);
    };

    recorder.onerror = () => {
      setIsRecording(false);
      toast({ title: 'Erro na gravação', description: 'Erro durante a gravação de áudio.', variant: 'destructive' });
    };

    setMediaRecorder(recorder);
    recorder.start(1000);
  } catch (error) {
    if (error.name === 'NotAllowedError') {
      toast({ title: 'Permissão negada', description: 'Permita o acesso ao microfone e tente novamente.', variant: 'destructive' });
    } else if (error.name === 'NotFoundError') {
      toast({ title: 'Microfone não encontrado', description: 'Verifique se há um microfone conectado.', variant: 'destructive' });
    } else {
      toast({ title: 'Erro no microfone', description: error.message, variant: 'destructive' });
    }
    setIsRecording(false);
    setRecordingTime(0);
  }
};

// ── Stop recording ──
const pararGravacao = () => {
  if (intervalRef.current) {
    clearInterval(intervalRef.current);
    intervalRef.current = null;
  }
  if (mediaRecorder && mediaRecorder.state === 'recording') {
    mediaRecorder.stop();
    setIsRecording(false);
  } else {
    setIsRecording(false);
    setAudioBlob(null);
    setRecordingTime(0);
    setMediaRecorder(null);
    startTimeRef.current = null;
    chunksRef.current = [];
  }
};

// ── Handle voice button click ──
const handleVoiceClick = () => {
  if (isRecording) {
    pararGravacao();
  } else {
    iniciarGravacao();
  }
};

// ── Send audio to AI ──
const enviarAudio = async () => {
  if (!audioBlob || !selectedTurmaId) {
    toast({ title: 'Erro', description: 'Nenhum áudio ou turma selecionada.', variant: 'destructive' });
    return;
  }

  try {
    const formData = new FormData();
    formData.append('audio', audioBlob, getAudioFilename(audioBlob));
    formData.append('turmaId', selectedTurmaId);
    formData.append('professora', user?.name || 'Sistema');
    formData.append('tipo', 'observacao_livre');
    formData.append('alunosTurma', JSON.stringify(alunos));

    setSaving(true);

    const apiUrl = `${API_BASE_URL}/api/upload-audio/`;
    const response = await fetch(apiUrl, {
      method: 'POST',
      body: formData,
      credentials: 'include',
      headers: { 'X-CSRFToken': getCsrfToken() },
    });

    if (response.ok) {
      const resultado = await response.json();

      if (!resultado.success) {
        toast({
          title: 'Não foi possível identificar alunos',
          description: resultado.error || 'Tente gravar novamente falando o nome do aluno de forma clara.',
          variant: 'destructive',
        });
        return;
      }

      setTranscricaoResultado(resultado);
      setEditandoTranscricao(true);

      if (resultado.turma_info?.alunos_disponiveis) {
        setAlunos(resultado.turma_info.alunos_disponiveis);
      }

      if (resultado.parcial && resultado.avisos?.length > 0) {
        toast({
          title: 'Alguns alunos não foram identificados',
          description: resultado.avisos.join('. '),
          className: 'bg-yellow-100 border-yellow-300 text-yellow-800',
        });
      } else {
        toast({
          title: 'Áudio processado com sucesso!',
          description:
            resultado.transcricao.total_alunos > 1
              ? `Observações sobre ${resultado.transcricao.total_alunos} alunos detectadas.`
              : `Observação sobre ${resultado.transcricao.alunos_detectados[0]?.aluno_nome} detectada.`,
          className: 'bg-green-100 border-green-300 text-green-800',
        });
      }

      setAudioBlob(null);
      setRecordingTime(0);
    } else if (response.status === 422) {
      const errorData = await response.json();
      if (errorData.nao_identificados?.length > 0) {
        const resultado = {
          success: true,
          parcial: true,
          transcricao: {
            texto_completo: errorData.transcricao?.texto_completo || '',
            alunos_detectados: [],
            total_alunos: 0,
            status: 'Processado pela IA',
            duracao_audio: '',
            qualidade_audio: 'Boa',
          },
          nao_identificados: errorData.nao_identificados,
          avisos: [errorData.error],
          metadados: { modelo_ia_usado: 'whisper-1 + gpt-4', modo_deteccao: 'multiplos_alunos' },
        };
        setTranscricaoResultado(resultado);
        setEditandoTranscricao(true);
        toast({
          title: 'Nenhum aluno identificado automaticamente',
          description: 'Selecione os alunos manualmente nos campos abaixo.',
          className: 'bg-yellow-100 border-yellow-300 text-yellow-800',
        });
        setAudioBlob(null);
        setRecordingTime(0);
      } else {
        toast({
          title: 'Não foi possível processar o áudio',
          description: errorData.error || 'Tente gravar novamente.',
          variant: 'destructive',
        });
      }
    } else {
      const errorData = await response.json();
      throw new Error(errorData.error || 'Erro ao enviar áudio');
    }
  } catch (error) {
    toast({ title: 'Erro ao enviar', description: error.message, variant: 'destructive' });
  } finally {
    setSaving(false);
  }
};

// ── Cancel recording ──
const cancelarGravacao = () => {
  if (audioElement) {
    audioElement.pause();
    audioElement.currentTime = 0;
    setAudioElement(null);
  }
  setIsPlaying(false);

  if (mediaRecorder && mediaRecorder.state === 'recording') {
    mediaRecorder.stop();
  }

  setAudioBlob(null);
  setRecordingTime(0);
  setIsRecording(false);
  setMediaRecorder(null);
  startTimeRef.current = null;
  setTranscricaoResultado(null);
  setEditandoTranscricao(false);

  if (intervalRef.current) {
    clearInterval(intervalRef.current);
    intervalRef.current = null;
  }
  chunksRef.current = [];
};

// ── Reset state ──
const resetarEstado = () => {
  if (audioElement) {
    audioElement.pause();
    audioElement.currentTime = 0;
    setAudioElement(null);
  }
  setIsPlaying(false);
  if (mediaRecorder && mediaRecorder.state === 'recording') {
    mediaRecorder.stop();
  }
  if (intervalRef.current) {
    clearInterval(intervalRef.current);
    intervalRef.current = null;
  }
  setIsRecording(false);
  setAudioBlob(null);
  setRecordingTime(0);
  setMediaRecorder(null);
  setTranscricaoResultado(null);
  setEditandoTranscricao(false);
  startTimeRef.current = null;
  chunksRef.current = [];
};

// ── Save transcription ──
const salvarTranscricao = async () => {
  if (!transcricaoResultado) return;

  const detectados = transcricaoResultado.transcricao.alunos_detectados?.length || 0;
  const pendentes = transcricaoResultado.nao_identificados?.length || 0;

  if (detectados === 0) {
    toast({
      title: 'Nenhum aluno selecionado',
      description: 'Selecione o aluno correto para pelo menos uma observação antes de salvar.',
      variant: 'destructive',
    });
    return;
  }

  if (pendentes > 0) {
    const nomes = transcricaoResultado.nao_identificados.map((n) => `"${n.nome_original_detectado}"`).join(', ');
    toast({
      title: `${pendentes} observação(ões) não resolvida(s)`,
      description: `As observações de ${nomes} serão descartadas. Clique em salvar novamente para confirmar.`,
      className: 'bg-yellow-100 border-yellow-300 text-yellow-800',
    });
    setTranscricaoResultado((prev) => ({ ...prev, nao_identificados: [] }));
    return;
  }

  try {
    setSaving(true);
    const dadosParaSalvar = {
      turma_id: selectedTurmaId,
      professora_id: user?.id,
      professora_nome: user?.name || 'Sistema',
      transcricao_completa: transcricaoResultado.transcricao.texto_completo,
      alunos_observacoes: transcricaoResultado.transcricao.alunos_detectados.map((alunoObs) => ({
        aluno_nome: alunoObs.aluno_nome,
        observacao: alunoObs.observacao,
        nome_original_detectado: alunoObs.nome_original_detectado,
        metodo_match: alunoObs.metodo_match,
        score_similaridade: alunoObs.score_similaridade,
        timestamp_inicio: alunoObs.timestamp_inicio,
        timestamp_fim: alunoObs.timestamp_fim,
      })),
      metadados: {
        modelo_ia_usado: transcricaoResultado.metadados.modelo_ia_usado,
        duracao_audio: transcricaoResultado.transcricao.duracao_audio,
        qualidade_audio: transcricaoResultado.transcricao.qualidade_audio,
        total_alunos: transcricaoResultado.transcricao.total_alunos,
        modo_deteccao: transcricaoResultado.metadados.modo_deteccao || 'multi-aluno',
      },
    };

    const apiUrl = `${API_BASE_URL}/api/salvar-observacoes-transcricao/`;
    const response = await fetch(apiUrl, {
      method: 'POST',
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCsrfToken(),
      },
      body: JSON.stringify(dadosParaSalvar),
    });

    if (response.ok) {
      const numAlunos = transcricaoResultado.transcricao.alunos_detectados?.length || 0;
      const nomeAlunos =
        transcricaoResultado.transcricao.alunos_detectados?.map((a) => a.aluno_nome.split(' ')[0]).join(', ') || 'alunos';

      toast({
        title: 'Observações salvas!',
        description:
          numAlunos > 1
            ? `Observações sobre ${numAlunos} alunos (${nomeAlunos}) foram registradas.`
            : `Observação sobre ${nomeAlunos} foi registrada.`,
        className: 'bg-green-100 border-green-300 text-green-800',
      });

      setTranscricaoResultado(null);
      setEditandoTranscricao(false);
    } else {
      const errorData = await response.json();
      throw new Error(errorData.error || 'Erro ao salvar observações');
    }
  } catch (error) {
    toast({ title: 'Erro ao salvar', description: error.message, variant: 'destructive' });
  } finally {
    setSaving(false);
  }
};

// ── Edit transcription ──
const editarTranscricao = (campo, valor, alunoIndex = null) => {
  setTranscricaoResultado((prev) => {
    if (alunoIndex !== null) {
      const novosAlunos = [...prev.transcricao.alunos_detectados];
      novosAlunos[alunoIndex] = { ...novosAlunos[alunoIndex], [campo]: valor };
      return { ...prev, transcricao: { ...prev.transcricao, alunos_detectados: novosAlunos } };
    }
    return { ...prev, transcricao: { ...prev.transcricao, [campo]: valor } };
  });
};

const descartarAlunoObservacao = (alunoIndex) => {
  const totalObservacoes =
    (transcricaoResultado.transcricao.alunos_detectados?.length || 0) + (transcricaoResultado.nao_identificados?.length || 0);
  if (totalObservacoes <= 1) {
    toast({
      title: 'Não é possível descartar',
      description: 'Deve haver pelo menos uma observação. Use "Descartar" para remover tudo.',
      variant: 'destructive',
    });
    return;
  }

  const nomeAluno = transcricaoResultado.transcricao.alunos_detectados[alunoIndex]?.aluno_nome || 'Aluno';
  setTranscricaoResultado((prev) => {
    const novosAlunos = prev.transcricao.alunos_detectados.filter((_, index) => index !== alunoIndex);
    return { ...prev, transcricao: { ...prev.transcricao, alunos_detectados: novosAlunos, total_alunos: novosAlunos.length } };
  });
  toast({
    title: 'Observação descartada',
    description: `A observação sobre ${nomeAluno.split(' ')[0]} foi removida.`,
    className: 'bg-yellow-100 border-yellow-300 text-yellow-800',
  });
};

const resolverAlunoNaoIdentificado = (naoIdIndex, alunoNomeEscolhido) => {
  setTranscricaoResultado((prev) => {
    const naoId = prev.nao_identificados[naoIdIndex];
    const novosNaoIdentificados = prev.nao_identificados.filter((_, i) => i !== naoIdIndex);
    const novoAluno = {
      aluno_nome: alunoNomeEscolhido,
      observacao: naoId.observacao,
      nome_original_detectado: naoId.nome_original_detectado,
      score_similaridade: 0,
      metodo_match: 'manual',
    };
    const novosDetectados = [...prev.transcricao.alunos_detectados, novoAluno];
    return {
      ...prev,
      nao_identificados: novosNaoIdentificados,
      transcricao: { ...prev.transcricao, alunos_detectados: novosDetectados, total_alunos: novosDetectados.length },
    };
  });
};

const editarObservacaoNaoIdentificado = (naoIdIndex, novaObservacao) => {
  setTranscricaoResultado((prev) => {
    const novos = [...prev.nao_identificados];
    novos[naoIdIndex] = { ...novos[naoIdIndex], observacao: novaObservacao };
    return { ...prev, nao_identificados: novos };
  });
};

const descartarAlunoNaoIdentificado = (naoIdIndex) => {
  const totalObservacoes =
    (transcricaoResultado.transcricao.alunos_detectados?.length || 0) + (transcricaoResultado.nao_identificados?.length || 0);
  if (totalObservacoes <= 1) {
    toast({
      title: 'Não é possível descartar',
      description: 'Deve haver pelo menos uma observação. Use "Descartar" para remover tudo.',
      variant: 'destructive',
    });
    return;
  }

  const nome = transcricaoResultado.nao_identificados[naoIdIndex]?.nome_original_detectado || 'Aluno';
  setTranscricaoResultado((prev) => ({
    ...prev,
    nao_identificados: prev.nao_identificados.filter((_, i) => i !== naoIdIndex),
  }));
  toast({
    title: 'Observação descartada',
    description: `A observação sobre "${nome}" foi removida.`,
    className: 'bg-yellow-100 border-yellow-300 text-yellow-800',
  });
};

// ── Audio playback ──
const reproduzirAudio = () => {
  if (!audioBlob) return;
  try {
    if (audioElement) {
      audioElement.pause();
      audioElement.currentTime = 0;
    }
    const audioUrl = URL.createObjectURL(audioBlob);
    const audio = new Audio(audioUrl);
    audio.onplay = () => setIsPlaying(true);
    audio.onpause = () => setIsPlaying(false);
    audio.onended = () => {
      setIsPlaying(false);
      URL.revokeObjectURL(audioUrl);
    };
    audio.onerror = () => {
      setIsPlaying(false);
      toast({ title: 'Erro na reprodução', description: 'Não foi possível reproduzir o áudio.', variant: 'destructive' });
    };
    setAudioElement(audio);
    audio.play();
  } catch {
    toast({ title: 'Erro na reprodução', description: 'Erro ao preparar áudio.', variant: 'destructive' });
  }
};

const pararAudio = () => {
  if (audioElement) {
    audioElement.pause();
    audioElement.currentTime = 0;
    setIsPlaying(false);
  }
};

// ── Cleanup ──
useEffect(() => {
  return () => {
    if (intervalRef.current) clearInterval(intervalRef.current);
    if (audioElement) {
      audioElement.pause();
      audioElement.currentTime = 0;
    }
  };
}, [audioElement]);

// Determine voice button state
const voiceState = isRecording ? 'listening' : 'idle';

// Show voice button area when no transcription result yet
const showVoiceArea = !transcricaoResultado;

return (
  <>
    <NoPeriodoModal open={!periodoLoading && !periodoAtivo && !!institutionId} />
    <Helmet>
      <title>NARA - Gravação</title>
      <meta name="description" content="Grave observações de voz e transcreva com IA." />
    </Helmet>

    <div className="bg-white min-h-screen flex flex-col">
      <ProfessorNavbar />

      <div className="bg-white border-b shadow-sm">
        <div className="container mx-auto px-4 sm:px-6 lg:px-8 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Button variant="ghost" size="icon" onClick={() => navigate('/home-professor')}>
              <ArrowLeft className="h-6 w-6 text-gray-600" />
            </Button>
            <NaraIaIcon isLogo={true} />
          </div>
          <h1 className="text-lg font-bold text-texto-escuro">Gravação</h1>
          {/* <div className="w-10" /> */}
        </div>
      </div>

      <main className="flex-1 container mx-auto px-4 sm:px-6 lg:px-8 py-8 max-w-2xl">
        {selectedTurmaId && showVoiceArea && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex flex-col items-center"
          >
            {/* Voice button */}
            <div className="py-8">
              <VoiceButton state={voiceState} onClick={handleVoiceClick} />
            </div>

            {/* Timer when recording */}
            {isRecording && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="mb-4"
              >
                <div className="flex items-center gap-2">
                  <div className="w-2.5 h-2.5 bg-red-500 rounded-full animate-pulse" />
                  <span className="font-mono text-2xl font-bold text-red-600">
                    {formatarTempo(recordingTime)}
                  </span>
                </div>
              </motion.div>
            )}

            {/* Label */}
            <p className="text-sm tracking-wide text-texto-medio mt-2">
              {isRecording
                ? 'Gravando... Toque para parar.'
                : audioBlob
                  ? 'Gravação concluída!'
                  : 'Toque para começar a gravar'}
            </p>

            {/* Post-recording actions */}
            {audioBlob && !isRecording && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="mt-6 flex flex-col sm:flex-row gap-3 w-full max-w-sm"
              >
                <Button
                  onClick={isPlaying ? pararAudio : reproduzirAudio}
                  variant="outline"
                  className="flex items-center gap-2 flex-1 border-roxo-principal text-roxo-principal hover:bg-lavanda-claro"
                >
                  {isPlaying ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
                  {isPlaying ? 'Pausar' : 'Escutar'}
                </Button>
                <Button
                  onClick={enviarAudio}
                  className="flex items-center gap-2 flex-[3] bg-roxo-principal hover:opacity-90 text-white"
                  disabled={saving}
                >
                  {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
                  {saving ? 'Processando...' : 'Enviar p/ Nara'}
                </Button>
                <Button onClick={cancelarGravacao} variant="outline" className="flex-1 text-texto-medio">
                  Cancelar
                </Button>
              </motion.div>
            )}
          </motion.div>
        )}

        {/* Transcription results */}
        <AnimatePresence>
          {transcricaoResultado && editandoTranscricao && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="mt-8 space-y-6"
            >
              {/* Transcription processed card */}
              <div className="p-6 bg-gradient-to-r from-lavanda-claro to-white rounded-xl border border-lavanda">
                <div className="flex items-center gap-3 mb-4">
                  <Sparkles className="h-5 w-5 text-roxo-principal" />
                  <h3 className="font-semibold text-texto-escuro">Transcrição Processada</h3>
                  <div className="bg-lavanda px-2 py-1 rounded-full text-xs text-roxo-principal">
                    {transcricaoResultado.transcricao.total_alunos > 1
                      ? `${transcricaoResultado.transcricao.total_alunos} alunos detectados`
                      : '1 aluno detectado'}
                  </div>
                </div>

                {/* Full transcription */}
                <div className="bg-white p-4 rounded-lg border border-lavanda">
                  <Label className="text-sm font-medium text-texto-medio">Transcrição completa:</Label>
                  <Textarea
                    value={transcricaoResultado.transcricao.texto_completo}
                    onChange={(e) => editarTranscricao('texto_completo', e.target.value)}
                    className="mt-2 min-h-[100px]"
                    placeholder="Transcrição do áudio..."
                  />
                </div>
              </div>

              {/* Observations per student */}
              <div className="space-y-4">
                <h3 className="font-semibold text-texto-escuro flex items-center gap-2">
                  <Users className="h-4 w-4 text-roxo-principal" />
                  Observações por Aluno
                  <span className="text-sm text-texto-medio">
                    ({transcricaoResultado.transcricao.alunos_detectados?.length || 0}{' '}
                    {transcricaoResultado.transcricao.alunos_detectados?.length === 1 ? 'aluno' : 'alunos'})
                  </span>
                </h3>

                {transcricaoResultado.transcricao.alunos_detectados?.length === 0 ? (
                  <div className="bg-yellow-50 p-4 rounded-lg border border-yellow-200">
                    <div className="flex items-center gap-2 text-yellow-800">
                      <Users className="h-4 w-4" />
                      <span className="font-medium">Nenhuma observação de aluno restante</span>
                    </div>
                    <p className="text-sm text-yellow-700 mt-1">
                      A transcrição completa ainda está disponível acima.
                    </p>
                  </div>
                ) : (
                  transcricaoResultado.transcricao.alunos_detectados?.map((alunoObs, index) => (
                    <div key={index} className="bg-white p-4 rounded-lg border border-lavanda relative">
                      <Button
                        onClick={() => descartarAlunoObservacao(index)}
                        variant="ghost"
                        size="sm"
                        className="absolute top-2 right-2 h-8 w-8 p-0 text-red-500 hover:text-red-700 hover:bg-red-50"
                        title="Descartar observação"
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>

                      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 pr-10">
                        <div>
                          <Label className="text-sm font-medium text-texto-medio flex items-center gap-2">
                            <span className="bg-lavanda text-roxo-principal px-2 py-1 rounded-full text-xs">
                              #{index + 1}
                            </span>
                            Aluno identificado:
                          </Label>
                          <Select
                            value={alunoObs.aluno_nome}
                            onValueChange={(value) => editarTranscricao('aluno_nome', value, index)}
                          >
                            <SelectTrigger className="mt-2">
                              <SelectValue placeholder="Selecione o aluno correto" />
                            </SelectTrigger>
                            <SelectContent>
                              {alunos.map((aluno) => (
                                <SelectItem key={aluno.id} value={aluno.nome_completo}>
                                  {aluno.nome_completo}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </div>

                        <div>
                          <Label className="text-sm font-medium text-texto-medio">Observação:</Label>
                          <Textarea
                            value={alunoObs.observacao}
                            onChange={(e) => editarTranscricao('observacao', e.target.value, index)}
                            className="mt-2 min-h-[100px]"
                            placeholder="O que foi observado sobre este aluno..."
                          />
                        </div>
                      </div>
                    </div>
                  ))
                )}

                {/* Unidentified students */}
                {transcricaoResultado.nao_identificados?.length > 0 && (
                  <>
                    <h4 className="text-sm font-semibold text-orange-700 flex items-center gap-2 mt-4">
                      Alunos não identificados
                      <span className="bg-orange-100 text-orange-700 px-2 py-0.5 rounded-full text-xs">
                        {transcricaoResultado.nao_identificados.length}
                      </span>
                    </h4>
                    {transcricaoResultado.nao_identificados.map((naoId, naoIdIndex) => (
                      <div key={`nao-id-${naoIdIndex}`} className="bg-orange-50 p-4 rounded-lg border border-orange-200 relative">
                        <Button
                          onClick={() => descartarAlunoNaoIdentificado(naoIdIndex)}
                          variant="ghost"
                          size="sm"
                          className="absolute top-2 right-2 h-8 w-8 p-0 text-red-500 hover:text-red-700 hover:bg-red-50"
                          title="Descartar observação"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>

                        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 pr-10">
                          <div>
                            <Label className="text-sm font-medium text-orange-700 flex items-center gap-2">
                              <span className="bg-orange-200 text-orange-800 px-2 py-1 rounded-full text-xs">?</span>
                              Não identificado
                            </Label>
                            <div className="mt-2 text-xs text-orange-600 bg-orange-100 p-2 rounded">
                              <span className="font-medium">Nome detectado:</span> "{naoId.nome_original_detectado}"
                            </div>
                            <Select onValueChange={(value) => resolverAlunoNaoIdentificado(naoIdIndex, value)}>
                              <SelectTrigger className="mt-2">
                                <SelectValue placeholder="Selecione o aluno correto" />
                              </SelectTrigger>
                              <SelectContent>
                                {alunos.map((aluno) => (
                                  <SelectItem key={aluno.id} value={aluno.nome_completo}>
                                    {aluno.nome_completo}
                                  </SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                          </div>

                          <div>
                            <Label className="text-sm font-medium text-texto-medio">Observação:</Label>
                            <Textarea
                              value={naoId.observacao}
                              onChange={(e) => editarObservacaoNaoIdentificado(naoIdIndex, e.target.value)}
                              className="mt-2 min-h-[100px]"
                              placeholder="O que foi observado sobre este aluno..."
                            />
                          </div>
                        </div>
                      </div>
                    ))}
                  </>
                )}
              </div>

              {/* Action buttons */}
              <div className="flex flex-col gap-3 pt-2 sm:flex-row sm:items-center">
                <Button
                  onClick={salvarTranscricao}
                  className="flex items-center gap-2 bg-verde-menta hover:bg-opacity-80 text-texto-escuro w-full sm:w-auto"
                  disabled={saving}
                >
                  {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                  {saving
                    ? 'Salvando...'
                    : `Salvar ${transcricaoResultado.transcricao.total_alunos > 1 ? 'Observações' : 'Observação'}`}
                </Button>
                <div className="flex gap-3 w-full sm:contents">
                  <Button onClick={cancelarGravacao} variant="outline" className="text-texto-medio flex-1 sm:flex-none">
                    Descartar
                  </Button>
                  <Button onClick={resetarEstado} variant="outline" className="text-texto-medio flex-1 sm:flex-none">
                    Nova Gravação
                  </Button>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </main>
    </div>
  </>
);
};

export default RecordingPage;