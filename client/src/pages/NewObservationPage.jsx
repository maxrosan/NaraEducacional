import React, { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { Helmet } from 'react-helmet-async';
import { useNavigate, useParams } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { ArrowLeft, Check, Edit, Sparkles, Save, Loader2, BookOpen, Camera, Mic, MicOff, Square, Trash2, Play, Pause } from 'lucide-react';

import { apiClient } from '@/lib/apiClient';
import { useAuth } from '@/contexts/AuthContext';
import { fetchQuestionsByFaixaEtaria, resolverCampoExperiencia } from '@/lib/observationUtils';

import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { useToast } from '@/components/ui/use-toast';
import { Textarea } from '@/components/ui/textarea';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';

import { Step } from '@/components/observations/Step';
import { IaObservationBlock } from '@/components/observations/IaObservationBlock';
import { PortfolioUploadForm } from '@/components/portfolio/PortfolioUploadForm';
import { GuidedObservationContent } from '@/components/observations/GuidedObservationContent';
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

const NewObservationPage = () => {
  const navigate = useNavigate();
  const { turmaId: turmaIdFromUrl } = useParams();
  const { toast } = useToast();
  const { user, turmaAtiva } = useAuth();

  const [turmas, setTurmas] = useState([]);
  const [alunos, setAlunos] = useState([]);
  const [selectedTurmaId, setSelectedTurmaId] = useState(turmaIdFromUrl || '');
  const [observationType, setObservationType] = useState('guiado');
  const [questions, setQuestions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selections, setSelections] = useState({});
  const [initialCounts, setInitialCounts] = useState({});
  const [comments, setComments] = useState({});
  const [generalComment, setGeneralComment] = useState('');
  const [saving, setSaving] = useState(false);
  const [institutionId, setInstitutionId] = useState(null);
  const [showTurmaSelection, setShowTurmaSelection] = useState(false);

  // Disciplinas vinculadas ao professor logado (só se aplica a professor_fundamental).
  // null = ainda não carregado / não se aplica; [] = carregado, sem vínculos;
  // [...] = nomes das disciplinas (Disciplina.nome) que o professor pode ver.
  const [disciplinasPermitidas, setDisciplinasPermitidas] = useState(null);

  const { periodoAtivo, loading: periodoLoading } = usePeriodoAvaliativo(institutionId);

  // Estados para gravação de áudio
  const [isRecording, setIsRecording] = useState(false);
  const [audioBlob, setAudioBlob] = useState(null);
  const [recordingTime, setRecordingTime] = useState(0);
  const [mediaRecorder, setMediaRecorder] = useState(null);
  const [transcricaoResultado, setTranscricaoResultado] = useState(null);
  const [editandoTranscricao, setEditandoTranscricao] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const [audioElement, setAudioElement] = useState(null);
  const [audioDevices, setAudioDevices] = useState([]);
  const [selectedMicrophoneId, setSelectedMicrophoneId] = useState('');
  const [showMicrophoneSelector, setShowMicrophoneSelector] = useState(false);
  const intervalRef = useRef(null);
  const chunksRef = useRef([]);
  const startTimeRef = useRef(null);

  const loadQuestions = useCallback(async (currentTurmas, turmaId) => {
    const selectedTurma = currentTurmas.find(t => t.id === turmaId);
    if (!selectedTurma || !selectedTurma.faixa_etaria) {
      toast({ title: 'Turma sem faixa etária', description: 'A turma selecionada não possui uma faixa etária definida.', variant: 'destructive' });
      setQuestions([]);
      return;
    }

    const { data, error } = await fetchQuestionsByFaixaEtaria(selectedTurma.faixa_etaria);
    if (error) {
      toast({ title: 'Erro ao buscar perguntas', description: error.message, variant: 'destructive' });
      setQuestions([]);
    } else {
      setQuestions(data || []);
    }
  }, [toast]);

  const handleTurmaChange = useCallback(async (turmaId) => {
    if (!turmaId) return;
    navigate(`/registro/${turmaId}`);
  }, [navigate]);

  const fetchInitialData = useCallback(async () => {
    if (!user) return;
    setLoading(true);

    try {
      const { data: turmasData, error: turmasError } = await apiClient
        .from('turmas')
        .select('id, nome, faixa_etaria, instituicao_id, usuario_turmas!inner(usuario_id)')
        .eq('usuario_turmas.usuario_id', user.id);

      if (turmasError) throw turmasError;

      const formattedTurmas = turmasData.filter(Boolean);

      if (!formattedTurmas || formattedTurmas.length === 0) {
        toast({ title: "Nenhuma turma encontrada", description: "Você não está vinculado a nenhuma turma. Fale com a coordenação." });
        setTurmas([]);
        setLoading(false);
        return;
      }

      setTurmas(formattedTurmas);
      if (formattedTurmas.length > 0) setInstitutionId(formattedTurmas[0].instituicao_id);

      if (!turmaIdFromUrl) {
        // Se só tem uma turma, vai direto pra ela
        // Se tem mais de uma, usa a turmaAtiva do contexto (escolhida no home)
        const turmaAlvo = formattedTurmas.length === 1
          ? formattedTurmas[0]
          : formattedTurmas.find(t => t.id === turmaAtiva?.id) || formattedTurmas[0];

        navigate(`/registro/${turmaAlvo.id}`, { replace: true });
        return;
      }

      setShowTurmaSelection(formattedTurmas.length > 1);

      if (turmaIdFromUrl) {
        setSelectedTurmaId(turmaIdFromUrl);
        const { data: alunosData, error: alunosError } = await apiClient.from('criancas').select('id, nome_completo').eq('turma_id', turmaIdFromUrl);
        if (alunosError) throw alunosError;
        setAlunos(alunosData || []);
        await loadQuestions(formattedTurmas, turmaIdFromUrl);
      }
    } catch (error) {
      toast({ variant: "destructive", title: "Erro ao carregar dados", description: error.message });
    } finally {
      setLoading(false);
    }
  }, [user, toast, navigate, turmaIdFromUrl, loadQuestions, turmaAtiva]);

  useEffect(() => {
    fetchInitialData();
  }, [fetchInitialData, turmaIdFromUrl]);

  useEffect(() => {
    if (!turmaIdFromUrl || turmas.length === 0) return;
    if (turmaAtiva?.id && turmaAtiva.id !== turmaIdFromUrl) {
      handleTurmaChange(turmaAtiva.id);
    }
  }, [turmaAtiva?.id, turmaIdFromUrl, turmas, handleTurmaChange]);

  // Busca as disciplinas que o professor do fundamental está vinculado, para
  // filtrar as matérias exibidas em "Registro por pergunta". Não afeta o
  // dropdown de disciplinas (cadastro) nem o fluxo de professor de infantil.
  useEffect(() => {
    if (!user || user.perfil !== 'professor_fundamental' || !institutionId) {
      setDisciplinasPermitidas(null);
      return;
    }

    let cancelled = false;
    (async () => {
      try {
        const apiUrl = `${API_BASE_URL}/api/usuario-disciplinas/?usuario_id=${user.id}&instituicao_id=${institutionId}`;
        const response = await fetch(apiUrl, {
          credentials: 'include',
          headers: { 'X-CSRFToken': getCsrfToken() },
        });
        if (!response.ok) throw new Error('Erro ao buscar disciplinas do professor');
        const resultado = await response.json();
        const vinculos = resultado.results ?? resultado; // suporta resposta paginada ou lista simples
        if (!cancelled) {
          setDisciplinasPermitidas((vinculos || []).map(v => resolverCampoExperiencia(v.disciplina_nome)));
        }
      } catch (error) {
        if (!cancelled) {
          toast({
            title: 'Erro ao carregar disciplinas do professor',
            description: error.message,
            variant: 'destructive',
          });
          // fail-safe: em caso de erro, não mostra nenhuma matéria em vez de vazar todas
          setDisciplinasPermitidas([]);
        }
      }
    })();

    return () => { cancelled = true; };
  }, [user, institutionId, toast]);

  // Perguntas efetivamente exibidas no "Registro por pergunta". Para
  // professor_fundamental, restringe aos componentes curriculares vinculados
  // via UsuarioDisciplina; para os demais perfis, mantém o comportamento atual.
  const visibleQuestions = useMemo(() => {
    if (user?.perfil !== 'professor_fundamental' || disciplinasPermitidas === null) {
      return questions;
    }
    return questions.filter(q => disciplinasPermitidas.includes(q.campo_experiencia));
  }, [questions, user, disciplinasPermitidas]);

  useEffect(() => {
    if (!user || !periodoAtivo || !questions?.length || !alunos?.length) {
      setInitialCounts({});
      setSelections(prev => (Object.keys(prev).length === 0 ? prev : {}));
      return;
    }

    let cancelled = false;
    (async () => {
      const { data, error } = await apiClient
        .from('registros_observacao')
        .select('pergunta_id, crianca_id')
        .eq('professor_id', user.id)
        .gte('data_observacao', periodoAtivo.data_inicio)
        .lte('data_observacao', periodoAtivo.data_fim)
        .in('pergunta_id', questions.map(q => q.id))
        .in('crianca_id', alunos.map(a => a.id));

      if (cancelled) return;
      if (error) {
        toast({ title: 'Erro ao carregar marcações anteriores', description: error.message, variant: 'destructive' });
        return;
      }

      const counts = {};
      (data || []).forEach(({ pergunta_id, crianca_id }) => {
        if (!pergunta_id || !crianca_id) return;
        if (!counts[pergunta_id]) counts[pergunta_id] = {};
        counts[pergunta_id][crianca_id] = (counts[pergunta_id][crianca_id] || 0) + 1;
      });

      setInitialCounts(counts);
      setSelections(counts);
    })();

    return () => { cancelled = true; };
  }, [user, periodoAtivo, questions, alunos, toast]);

  // Função para listar dispositivos de áudio
  const listarDispositivosAudio = async () => {
    try {
      // Primeiro solicitar permissão para acessar dispositivos
      await navigator.mediaDevices.getUserMedia({ audio: true });

      // Listar todos os dispositivos
      const devices = await navigator.mediaDevices.enumerateDevices();

      // Filtrar apenas dispositivos de entrada de áudio
      const audioInputDevices = devices.filter(device => device.kind === 'audioinput');

      console.log('📱 Dispositivos de áudio encontrados:', audioInputDevices);

      setAudioDevices(audioInputDevices);

      // Se há mais de um dispositivo, mostrar seletor
      if (audioInputDevices.length > 1) {
        setShowMicrophoneSelector(true);
        // Selecionar o primeiro dispositivo por padrão se nenhum estiver selecionado
        if (!selectedMicrophoneId && audioInputDevices.length > 0) {
          setSelectedMicrophoneId(audioInputDevices[0].deviceId);
        }
      } else if (audioInputDevices.length === 1) {
        // Se há apenas um, selecionar automaticamente
        setSelectedMicrophoneId(audioInputDevices[0].deviceId);
        setShowMicrophoneSelector(false);
      }

      return audioInputDevices;
    } catch (error) {
      console.error('❌ Erro ao listar dispositivos de áudio:', error);
      toast({
        title: 'Erro ao acessar microfones',
        description: 'Não foi possível listar os dispositivos de áudio disponíveis.',
        variant: 'destructive'
      });
      return [];
    }
  };

  // Auto-detectar microfone ao entrar na aba "livre"
  useEffect(() => {
    if (observationType === 'livre' && !selectedMicrophoneId) {
      listarDispositivosAudio();
    }
  }, [observationType]);

  // Funções para gravação de áudio
  const iniciarGravacao = async () => {
    try {
      console.log('🎤 Iniciando processo de gravação...');

      // Verificar se há microfone selecionado ou listar dispositivos
      if (!selectedMicrophoneId) {
        console.log('🔍 Nenhum microfone selecionado, listando dispositivos...');
        const devices = await listarDispositivosAudio();
        if (devices.length === 0) {
          toast({ title: 'Nenhum microfone encontrado', description: 'Não foi possível encontrar dispositivos de áudio.', variant: 'destructive' });
          return;
        }
      }

      // Limpar estado anterior PRIMEIRO
      setAudioBlob(null);
      setRecordingTime(0);
      chunksRef.current = [];
      startTimeRef.current = null;

      // Limpar interval anterior se existir
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }

      console.log('🎤 Solicitando permissão do microfone selecionado:', selectedMicrophoneId);

      // Configurar constraints com microfone específico
      const constraints = {
        audio: {
          deviceId: selectedMicrophoneId ? { exact: selectedMicrophoneId } : undefined,
          echoCancellation: true,
          noiseSuppression: true,
          sampleRate: 44100
        }
      };

      const stream = await navigator.mediaDevices.getUserMedia(constraints);

      console.log('✅ Permissão concedida! Stream ativo:', stream.active);
      console.log('🎵 Tracks de áudio:', stream.getAudioTracks().length);

      // Detectar melhor MIME type
      let mimeType = 'audio/webm';
      if (MediaRecorder.isTypeSupported('audio/webm;codecs=opus')) {
        mimeType = 'audio/webm;codecs=opus';
      } else if (MediaRecorder.isTypeSupported('audio/mp4')) {
        mimeType = 'audio/mp4';
      } else if (MediaRecorder.isTypeSupported('audio/wav')) {
        mimeType = 'audio/wav';
      }

      console.log('🎵 MIME type selecionado:', mimeType);

      const recorder = new MediaRecorder(stream, { mimeType });

      recorder.ondataavailable = (event) => {
        console.log('📦 Dados disponíveis:', event.data.size, 'bytes');
        if (event.data.size > 0) {
          chunksRef.current.push(event.data);
          console.log('📦 Total de chunks:', chunksRef.current.length);
        }
      };

      recorder.onstop = () => {
        console.log('⏹️ Gravação parada. Chunks coletados:', chunksRef.current.length);

        if (chunksRef.current.length > 0) {
          const audioBlob = new Blob(chunksRef.current, { type: mimeType });
          console.log('✅ Blob criado:', audioBlob.size, 'bytes');
          setAudioBlob(audioBlob);
        } else {
          console.warn('⚠️ Nenhum chunk de áudio foi coletado');
          toast({ title: 'Erro na gravação', description: 'Nenhum áudio foi gravado. Tente novamente.', variant: 'destructive' });
        }

        // Parar todas as faixas de mídia
        stream.getTracks().forEach(track => {
          track.stop();
          console.log('🔇 Track parada:', track.kind, track.label);
        });
      };

      recorder.onstart = () => {
        console.log('▶️ MediaRecorder iniciado com sucesso');

        // Definir timestamp de início
        startTimeRef.current = Date.now();
        console.log('⏰ Timestamp de início:', startTimeRef.current);

        // Definir estado como gravando APÓS confirmação
        setIsRecording(true);
        setRecordingTime(0); // Garantir que começa em 0

        // Iniciar contador baseado em timestamp real
        console.log('⏰ Iniciando contador de tempo baseado em timestamp...');
        intervalRef.current = setInterval(() => {
          if (startTimeRef.current) {
            const elapsed = Math.floor((Date.now() - startTimeRef.current) / 1000);
            console.log('⏰ Tempo calculado:', elapsed, 'segundos');
            setRecordingTime(elapsed);
          }
        }, 1000);
      };

      recorder.onerror = (event) => {
        console.error('❌ Erro no MediaRecorder:', event.error);
        setIsRecording(false);
        toast({ title: 'Erro na gravação', description: 'Erro durante a gravação: ' + event.error, variant: 'destructive' });
      };

      setMediaRecorder(recorder);

      console.log('🚀 Iniciando gravação...');
      recorder.start(1000); // Capturar dados a cada 1 segundo

    } catch (error) {
      console.error('❌ Erro ao acessar microfone:', error);

      if (error.name === 'NotAllowedError') {
        toast({ title: 'Permissão negada', description: 'Permissão para usar o microfone foi negada. Por favor, permita o acesso ao microfone e tente novamente.', variant: 'destructive' });
      } else if (error.name === 'NotFoundError') {
        toast({ title: 'Microfone não encontrado', description: 'Nenhum microfone foi encontrado. Verifique se há um microfone conectado.', variant: 'destructive' });
      } else {
        toast({ title: 'Erro no microfone', description: 'Erro ao acessar o microfone: ' + error.message, variant: 'destructive' });
      }

      setIsRecording(false);
      setRecordingTime(0);
    }
  };

  const pararGravacao = () => {
    console.log('⏹️ Iniciando processo de parada...');
    console.log('📊 Estado atual - MediaRecorder:', mediaRecorder?.state);
    console.log('📊 Estado atual - isRecording:', isRecording);
    console.log('📊 Estado atual - recordingTime:', recordingTime);
    console.log('📊 Estado atual - startTime:', startTimeRef.current);

    // Parar o contador primeiro
    if (intervalRef.current) {
      console.log('⏰ Parando contador de tempo...');
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }

    // Parar a gravação
    if (mediaRecorder && mediaRecorder.state === 'recording') {
      console.log('🛑 Parando MediaRecorder...');
      mediaRecorder.stop();
      setIsRecording(false);
    } else {
      console.warn('⚠️ MediaRecorder não está gravando ou não existe');
      console.log('🔍 Estado do MediaRecorder:', mediaRecorder?.state);
      setIsRecording(false);

      // Se não há gravação ativa, limpar tudo
      if (!mediaRecorder || mediaRecorder.state === 'inactive') {
        console.log('🧹 Limpando estado...');
        setAudioBlob(null);
        setRecordingTime(0);
        setMediaRecorder(null);
        startTimeRef.current = null;
        chunksRef.current = [];
      }
    }
  };

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

      // Enviar lista de alunos da turma para o backend
      formData.append('alunosTurma', JSON.stringify(alunos));

      setSaving(true);

      const apiUrl = `${API_BASE_URL}/api/upload-audio/`;
      const response = await fetch(apiUrl, {
        method: 'POST',
        body: formData,
        credentials: 'include',
        headers: {
          'X-CSRFToken': getCsrfToken(),
        },
      });

      if (response.ok) {
        const resultado = await response.json();
        console.log('Transcrição recebida:', resultado);

        if (!resultado.success) {
          toast({
            title: 'Não foi possível identificar alunos',
            description: resultado.error || 'Tente gravar novamente falando o nome do aluno de forma clara.',
            variant: 'destructive',
          });
          return;
        }

        // Armazenar resultado da transcrição
        setTranscricaoResultado(resultado);
        setEditandoTranscricao(true);

        // Atualizar lista de alunos se fornecida pelo backend
        if (resultado.turma_info?.alunos_disponiveis) {
          console.log('Atualizando lista de alunos da turma:', resultado.turma_info.alunos_disponiveis);
          setAlunos(resultado.turma_info.alunos_disponiveis);
        }

        // Avisar sobre alunos não identificados (sucesso parcial)
        if (resultado.parcial && resultado.avisos?.length > 0) {
          toast({
            title: 'Alguns alunos não foram identificados',
            description: resultado.avisos.join('. '),
            className: 'bg-yellow-100 border-yellow-300 text-yellow-800',
          });
        } else {
          toast({
            title: 'Áudio processado com sucesso!',
            description: resultado.transcricao.total_alunos > 1
              ? `IA detectou observações sobre ${resultado.transcricao.total_alunos} alunos: ${resultado.transcricao.alunos_detectados.map(a => a.aluno_nome.split(' ')[0]).join(', ')}`
              : `IA detectou observação sobre ${resultado.transcricao.alunos_detectados[0]?.aluno_nome}`,
            className: 'bg-green-100 border-green-300 text-green-800',
          });
        }

        // Limpar estado da gravação de áudio
        setAudioBlob(null);
        setRecordingTime(0);

      } else if (response.status === 422) {
        // Legacy 422 handling — try to recover nao_identificados if present
        const errorData = await response.json();
        if (errorData.nao_identificados?.length > 0) {
          const resultado = {
            success: true,
            parcial: true,
            transcricao: {
              texto_completo: errorData.transcricao?.texto_completo || '',
              alunos_detectados: [],
              total_alunos: 0,
              confianca_geral: 0,
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
            description: errorData.error || 'Tente gravar novamente falando o nome do aluno de forma clara.',
            variant: 'destructive',
          });
        }
      } else {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Erro ao enviar áudio');
      }
    } catch (error) {
      console.error('Erro ao enviar áudio:', error);
      toast({ title: 'Erro ao enviar', description: error.message, variant: 'destructive' });
    } finally {
      setSaving(false);
    }
  };

  const cancelarGravacao = () => {
    console.log('🗑️ Cancelando gravação...');

    // Parar áudio se estiver reproduzindo
    if (audioElement) {
      audioElement.pause();
      audioElement.currentTime = 0;
      setAudioElement(null);
    }
    setIsPlaying(false);

    // Parar MediaRecorder se estiver ativo
    if (mediaRecorder && mediaRecorder.state === 'recording') {
      console.log('🛑 Parando MediaRecorder...');
      mediaRecorder.stop();
    }

    // Limpar estados de gravação
    setAudioBlob(null);
    setRecordingTime(0);
    setIsRecording(false);
    setMediaRecorder(null);
    startTimeRef.current = null;

    // Limpar estados de transcrição
    setTranscricaoResultado(null);
    setEditandoTranscricao(false);

    // Limpar interval se estiver ativo
    if (intervalRef.current) {
      console.log('⏰ Limpando interval...');
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }

    // Limpar chunks
    chunksRef.current = [];

    console.log('✅ Gravação cancelada com sucesso');
  };

  const resetarEstado = () => {
    console.log('🔄 Resetando estado completo...');

    // Parar áudio se estiver reproduzindo
    if (audioElement) {
      audioElement.pause();
      audioElement.currentTime = 0;
      setAudioElement(null);
    }
    setIsPlaying(false);

    // Parar qualquer gravação ativa
    if (mediaRecorder && mediaRecorder.state === 'recording') {
      mediaRecorder.stop();
    }

    // Limpar interval
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }

    // Resetar todos os estados
    setIsRecording(false);
    setAudioBlob(null);
    setRecordingTime(0);
    setMediaRecorder(null);
    setTranscricaoResultado(null);
    setEditandoTranscricao(false);
    startTimeRef.current = null;
    chunksRef.current = [];

    console.log('✅ Estado resetado completamente');
  };

  const testarSuporteAudio = async () => {
    console.log('🔍 === DIAGNÓSTICO COMPLETO DE ÁUDIO ===');

    // Teste básico de APIs
    console.log('📱 navigator.mediaDevices:', !!navigator.mediaDevices);
    console.log('🎤 getUserMedia:', !!navigator.mediaDevices?.getUserMedia);
    console.log('🎵 MediaRecorder:', !!window.MediaRecorder);
    console.log('📱 enumerateDevices:', !!navigator.mediaDevices?.enumerateDevices);

    // Teste de tipos MIME suportados
    if (MediaRecorder) {
      console.log('🎵 Tipos de MIME suportados:');
      const tipos = [
        'audio/webm',
        'audio/webm;codecs=opus',
        'audio/mp4',
        'audio/wav',
        'audio/ogg',
        'audio/mpeg'
      ];
      tipos.forEach(tipo => {
        console.log(`- ${tipo}: ${MediaRecorder.isTypeSupported(tipo)}`);
      });
    }

    // Listar dispositivos de áudio
    try {
      console.log('📱 Listando dispositivos de áudio...');
      const devices = await listarDispositivosAudio();
      console.log(`✅ Encontrados ${devices.length} dispositivos de entrada de áudio`);
      devices.forEach((device, index) => {
        console.log(`${index + 1}. ${device.label || `Dispositivo ${index + 1}`} (ID: ${device.deviceId})`);
      });
    } catch (deviceError) {
      console.error('❌ Erro ao listar dispositivos:', deviceError);
    }

    // Teste de acesso ao microfone
    try {
      console.log('🎤 Testando acesso ao microfone...');
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      console.log('✅ Microfone acessível!');
      console.log('🎵 Tracks de áudio:', stream.getAudioTracks().length);

      // Informações do track de áudio
      if (stream.getAudioTracks().length > 0) {
        const audioTrack = stream.getAudioTracks()[0];
        console.log('🎵 Label do dispositivo:', audioTrack.label);
        console.log('🎵 ID do dispositivo:', audioTrack.getSettings().deviceId);
      }

      // Testar criação do MediaRecorder
      try {
        const testRecorder = new MediaRecorder(stream);
        console.log('✅ MediaRecorder criado com sucesso');
        console.log('🎵 Estado inicial:', testRecorder.state);

        // Testar start/stop rápido
        testRecorder.start();
        console.log('✅ MediaRecorder.start() funcionou');
        setTimeout(() => {
          testRecorder.stop();
          console.log('✅ MediaRecorder.stop() funcionou');
        }, 100);

      } catch (recorderError) {
        console.error('❌ Erro ao criar MediaRecorder:', recorderError);
      }

      // Parar stream de teste
      stream.getTracks().forEach(track => track.stop());

    } catch (micError) {
      console.error('❌ Erro ao acessar microfone:', micError);
    }

    // Informações do navegador
    console.log('🌐 Navegador:', navigator.userAgent);
    console.log('🔒 Protocolo:', location.protocol);
    console.log('🌍 Host:', location.host);

    toast({ title: 'Diagnóstico concluído', description: 'Verifique o console para detalhes.', });
  };

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
      const nomes = transcricaoResultado.nao_identificados
        .map(n => `"${n.nome_original_detectado}"`)
        .join(', ');
      toast({
        title: `${pendentes} observação(ões) não resolvida(s)`,
        description: `As observações de ${nomes} serão descartadas. Clique em salvar novamente para confirmar.`,
        className: 'bg-yellow-100 border-yellow-300 text-yellow-800',
      });
      // Clear nao_identificados so next click saves without warning
      setTranscricaoResultado(prev => ({ ...prev, nao_identificados: [] }));
      return;
    }

    try {
      setSaving(true);

      // Preparar dados para envio ao backend
      const dadosParaSalvar = {
        turma_id: selectedTurmaId,
        professora_id: user?.id,
        professora_nome: user?.name || 'Sistema',
        transcricao_completa: transcricaoResultado.transcricao.texto_completo,
        alunos_observacoes: transcricaoResultado.transcricao.alunos_detectados.map(alunoObs => ({
          aluno_nome: alunoObs.aluno_nome,
          observacao: alunoObs.observacao,
          confianca: alunoObs.confianca,
          nome_original_detectado: alunoObs.nome_original_detectado,
          metodo_match: alunoObs.metodo_match,
          score_similaridade: alunoObs.score_similaridade,
          timestamp_inicio: alunoObs.timestamp_inicio,
          timestamp_fim: alunoObs.timestamp_fim
        })),
        metadados: {
          modelo_ia_usado: transcricaoResultado.metadados.modelo_ia_usado,
          duracao_audio: transcricaoResultado.transcricao.duracao_audio,
          qualidade_audio: transcricaoResultado.transcricao.qualidade_audio,
          confianca_geral: transcricaoResultado.transcricao.confianca_geral,
          total_alunos: transcricaoResultado.transcricao.total_alunos,
          modo_deteccao: transcricaoResultado.metadados.modo_deteccao || 'multi-aluno'
        }
      };

      console.log('📤 Enviando dados da transcrição para salvamento:', dadosParaSalvar);

      // Enviar para o backend
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
        const resultado = await response.json();
        console.log('✅ Observações salvas no banco:', resultado);

        const numAlunos = transcricaoResultado.transcricao.alunos_detectados?.length || 0;
        const nomeAlunos = transcricaoResultado.transcricao.alunos_detectados
          ?.map(a => a.aluno_nome.split(' ')[0])
          .join(', ') || 'alunos';

        toast({
          title: '✅ Observações salvas no banco!',
          description: numAlunos > 1
            ? `Observações sobre ${numAlunos} alunos (${nomeAlunos}) foram registradas no banco de dados.`
            : `Observação sobre ${nomeAlunos} foi registrada no banco de dados.`,
          className: 'bg-green-100 border-green-300 text-green-800',
        });

        // Limpar estados após salvar com sucesso
        setTranscricaoResultado(null);
        setEditandoTranscricao(false);

      } else {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Erro ao salvar observações no banco');
      }

    } catch (error) {
      console.error('❌ Erro ao salvar observação:', error);
      toast({
        title: 'Erro ao salvar no banco',
        description: `Erro ao salvar observações: ${error.message}`,
        variant: 'destructive'
      });
    } finally {
      setSaving(false);
    }
  };

  const editarTranscricao = (campo, valor, alunoIndex = null) => {
    setTranscricaoResultado(prev => {
      if (alunoIndex !== null) {
        // Editando observação de um aluno específico
        const novosAlunos = [...prev.transcricao.alunos_detectados];
        novosAlunos[alunoIndex] = { ...novosAlunos[alunoIndex], [campo]: valor };
        return {
          ...prev,
          transcricao: {
            ...prev.transcricao,
            alunos_detectados: novosAlunos
          }
        };
      } else {
        // Editando campo geral
        return {
          ...prev,
          transcricao: {
            ...prev.transcricao,
            [campo]: valor
          }
        };
      }
    });
  };

  const descartarAlunoObservacao = (alunoIndex) => {
    // Verificar se há mais de uma observação (detectados + não identificados) antes de descartar
    const totalObservacoes = (transcricaoResultado.transcricao.alunos_detectados?.length || 0)
      + (transcricaoResultado.nao_identificados?.length || 0);
    if (totalObservacoes <= 1) {
      toast({
        title: 'Não é possível descartar',
        description: 'Deve haver pelo menos uma observação de aluno. Para remover todas, use "Descartar" ou "Nova Gravação".',
        variant: 'destructive',
      });
      return;
    }

    const nomeAluno = transcricaoResultado.transcricao.alunos_detectados[alunoIndex]?.aluno_nome || 'Aluno';

    setTranscricaoResultado(prev => {
      const novosAlunos = prev.transcricao.alunos_detectados.filter((_, index) => index !== alunoIndex);
      return {
        ...prev,
        transcricao: {
          ...prev.transcricao,
          alunos_detectados: novosAlunos,
          total_alunos: novosAlunos.length
        }
      };
    });

    toast({
      title: 'Observação descartada',
      description: `A observação sobre ${nomeAluno.split(' ')[0]} foi removida.`,
      className: 'bg-yellow-100 border-yellow-300 text-yellow-800',
    });
  };

  const resolverAlunoNaoIdentificado = (naoIdIndex, alunoNomeEscolhido) => {
    setTranscricaoResultado(prev => {
      const naoId = prev.nao_identificados[naoIdIndex];
      const novosNaoIdentificados = prev.nao_identificados.filter((_, i) => i !== naoIdIndex);
      const novoAluno = {
        aluno_nome: alunoNomeEscolhido,
        observacao: naoId.observacao,
        confianca: 0,
        nome_original_detectado: naoId.nome_original_detectado,
        score_similaridade: 0,
        metodo_match: 'manual',
      };
      const novosDetectados = [...prev.transcricao.alunos_detectados, novoAluno];
      return {
        ...prev,
        nao_identificados: novosNaoIdentificados,
        transcricao: {
          ...prev.transcricao,
          alunos_detectados: novosDetectados,
          total_alunos: novosDetectados.length,
        },
      };
    });
  };

  const editarObservacaoNaoIdentificado = (naoIdIndex, novaObservacao) => {
    setTranscricaoResultado(prev => {
      const novos = [...prev.nao_identificados];
      novos[naoIdIndex] = { ...novos[naoIdIndex], observacao: novaObservacao };
      return { ...prev, nao_identificados: novos };
    });
  };

  const descartarAlunoNaoIdentificado = (naoIdIndex) => {
    const totalObservacoes = (transcricaoResultado.transcricao.alunos_detectados?.length || 0)
      + (transcricaoResultado.nao_identificados?.length || 0);
    if (totalObservacoes <= 1) {
      toast({
        title: 'Não é possível descartar',
        description: 'Deve haver pelo menos uma observação de aluno. Para remover todas, use "Descartar" ou "Nova Gravação".',
        variant: 'destructive',
      });
      return;
    }

    const nome = transcricaoResultado.nao_identificados[naoIdIndex]?.nome_original_detectado || 'Aluno';
    setTranscricaoResultado(prev => ({
      ...prev,
      nao_identificados: prev.nao_identificados.filter((_, i) => i !== naoIdIndex),
    }));
    toast({
      title: 'Observação descartada',
      description: `A observação sobre "${nome}" foi removida.`,
      className: 'bg-yellow-100 border-yellow-300 text-yellow-800',
    });
  };

  const formatarTempo = (segundos) => {
    const mins = Math.floor(segundos / 60);
    const secs = segundos % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  // Funções para reprodução do áudio
  const reproduzirAudio = () => {
    if (!audioBlob) return;

    try {
      // Parar áudio anterior se estiver tocando
      if (audioElement) {
        audioElement.pause();
        audioElement.currentTime = 0;
      }

      // Criar URL do blob e elemento de áudio
      const audioUrl = URL.createObjectURL(audioBlob);
      const audio = new Audio(audioUrl);

      audio.onplay = () => {
        setIsPlaying(true);
      };

      audio.onpause = () => {
        setIsPlaying(false);
      };

      audio.onended = () => {
        setIsPlaying(false);
        URL.revokeObjectURL(audioUrl); // Limpar URL do blob
      };

      audio.onerror = (error) => {
        console.error('Erro ao reproduzir áudio:', error);
        setIsPlaying(false);
        toast({ title: 'Erro na reprodução', description: 'Não foi possível reproduzir o áudio.', variant: 'destructive' });
      };

      setAudioElement(audio);
      audio.play();

    } catch (error) {
      console.error('Erro ao criar áudio:', error);
      toast({ title: 'Erro na reprodução', description: 'Erro ao preparar áudio para reprodução.', variant: 'destructive' });
    }
  };

  const pararAudio = () => {
    if (audioElement) {
      audioElement.pause();
      audioElement.currentTime = 0;
      setIsPlaying(false);
    }
  };

  // Cleanup effect para limpar interval quando componente é desmontado
  useEffect(() => {
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
      // Limpar áudio se estiver reproduzindo
      if (audioElement) {
        audioElement.pause();
        audioElement.currentTime = 0;
      }
    };
  }, [audioElement]);

  const handleSave = async () => {
    setSaving(true);
    const teacherId = user.id;

    const observationsToInsert = Object.entries(selections).flatMap(([pergunta_id, counts]) =>
      Object.entries(counts).flatMap(([crianca_id, n]) => {
        const previous = initialCounts[pergunta_id]?.[crianca_id] || 0;
        const delta = n - previous;
        if (delta <= 0) return [];
        return Array.from({ length: delta }, () => ({
          crianca_id,
          pergunta_id,
          resposta: 'Sim',
          observacao: comments[questions.find(q => q.id === pergunta_id)?.campo_experiencia] || null,
          data_observacao: new Date().toISOString().split('T')[0],
          professor_id: teacherId,
        }));
      })
    );

    if (observationsToInsert.length > 0) {
      const { error } = await apiClient.from('registros_observacao').insert(observationsToInsert);
      if (error) {
        toast({ title: 'Erro ao salvar observações', description: error.message, variant: 'destructive' });
        setSaving(false);
        return;
      }
    }

    if (generalComment) {
      const { error } = await apiClient.from('observacoes_comentarios').insert({
        instituicao_id: institutionId,
        turma_id: selectedTurmaId,
        professor_id: teacherId,
        data_observacao: new Date().toISOString(),
        observacao_geral: generalComment,
      });
      if (error) {
        toast({ title: 'Erro ao salvar observação geral', description: error.message, variant: 'destructive' });
      }
    }

    toast({
      title: '✅ Registro salvo com sucesso!',
      description: 'Ele já está sendo incluído na trajetória da criança.',
      className: 'bg-green-100 border-green-300 text-green-800',
    });
    setSaving(false);
    setTimeout(() => navigate('/home-professor'), 2000);
  };

  return (
    <>
      <NoPeriodoModal open={!periodoLoading && !periodoAtivo && !!institutionId} />
      <Helmet>
        <title>NARA - Nova Observação</title>
      </Helmet>
      <div className="bg-[#F5F3FA] min-h-screen">
        <ProfessorNavbar />

        <div className="bg-white border-b shadow-sm">
          <div className="container mx-auto px-4 sm:px-6 lg:px-8 py-4 flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Button variant="ghost" size="icon" onClick={() => navigate(-1)}><ArrowLeft className="h-6 w-6 text-gray-600" /></Button>
            </div>
            <h1 className="text-md font-bold text-gray-800">Nova Observação</h1>
            {/* <NaraIaIcon isLogo={true} /> */}
          </div>
        </div>

        <main className="container mx-auto px-4 sm:px-6 lg:px-8 py-8">
          {loading && !selectedTurmaId && <div className="flex justify-center p-8"><Loader2 className="h-8 w-8 animate-spin text-roxo-principal" /></div>}

          <AnimatePresence>
            {selectedTurmaId && (
              <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                <Step title="Tipo de registro" icon={<Edit className="h-5 w-5" />}>
                  <Tabs defaultValue="guiado" onValueChange={setObservationType} className="w-full">
                    <TabsList className="grid w-full grid-cols-3">
                      <TabsTrigger value="guiado">⇡ Guiado</TabsTrigger>
                      <TabsTrigger value="livre">👧 Análise</TabsTrigger>
                      <TabsTrigger value="portfolio">📸 Portfólio</TabsTrigger>
                    </TabsList>
                    <AnimatePresence mode="wait">
                      <motion.div key={observationType} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -10 }} transition={{ duration: 0.2 }} className="mt-6">
                        <TabsContent value="guiado">
                          <GuidedObservationContent
                            loading={loading || (user?.perfil === 'professor_fundamental' && disciplinasPermitidas === null)}
                            questions={visibleQuestions}
                            alunos={alunos}
                            selections={selections}
                            setSelections={setSelections}
                            initialCounts={initialCounts}
                            comments={comments}
                            setComments={setComments}
                            generalComment={generalComment}
                            setGeneralComment={setGeneralComment}
                          />
                        </TabsContent>
                        <TabsContent value="livre">
                          <IaObservationBlock students={alunos} turmaId={selectedTurmaId} />
                        </TabsContent>
                        <TabsContent value="portfolio">
                          <Step title="Adicionar ao Portfólio" icon={<Camera className="h-5 w-5" />}>
                            <PortfolioUploadForm students={alunos} turmaId={selectedTurmaId} />
                          </Step>
                        </TabsContent>
                      </motion.div>
                    </AnimatePresence>
                  </Tabs>
                </Step>
                {observationType === 'guiado' && (
                  <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, delay: 0.2 }} className="mt-8 flex justify-center">
                    <Button size="lg" className="bg-verde-menta hover:bg-opacity-80 text-texto-escuro font-bold rounded-full w-full max-w-md btn-hover" onClick={handleSave} disabled={saving || loading}>
                      {saving ? <Loader2 className="h-5 w-5 mr-2 animate-spin" /> : <Save className="h-5 w-5 mr-2" />}
                      <span>{saving ? 'Salvando...' : 'Salvar Observação'}</span>
                    </Button>
                  </motion.div>
                )}
              </motion.div>
            )}
          </AnimatePresence>
        </main>
      </div>
    </>
  );
};

export default NewObservationPage;