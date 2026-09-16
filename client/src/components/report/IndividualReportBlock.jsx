import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Check, Pencil, RotateCw, FileText, Mic, Clock, ChevronDown, ChevronUp, Trash2 } from 'lucide-react';
import { format } from 'date-fns';
import { ptBR } from 'date-fns/locale';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/accordion';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import EmptyContent from '@/components/reports/EmptyContent';
import { authFetch } from '@/services/api';
import { useAuth } from '@/contexts/AuthContext';
import { useToast } from '@/components/ui/use-toast';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || import.meta.env.VITE_API_URL || '';

const PERFIS_COORDENACAO = ['coordenador', 'admin'];

const formatarDataObservacao = (dateString) => {
  try {
    return format(new Date(dateString), "dd/MM/yyyy 'às' HH:mm", { locale: ptBR });
  } catch {
    return dateString;
  }
};

/**
 * Lista de relatos individuais vindos da transcrição de áudio.
 * Extraída porque o bloco a renderiza em duas situações (com e sem relato
 * já escrito) e a exclusão precisa se comportar igual nas duas.
 */
const ObservacoesTranscricaoList = ({ observacoes, mostrar, onToggle, onExcluir, podeExcluir, excluindoId }) => {
  const [confirmando, setConfirmando] = useState(null);

  if (observacoes.length === 0) return null;

  return (
    <div className="mb-6">
      <div className="flex items-center gap-2 mb-3">
        <Mic className="h-4 w-4 text-blue-600" />
        <h4 className="text-sm font-semibold text-blue-700">Observações da Professora (IA)</h4>
        <span className="bg-blue-100 text-blue-600 text-xs px-2 py-1 rounded-full whitespace-nowrap">
          <span className="sm:hidden">{observacoes.length} Obs.</span>
          <span className="hidden sm:inline">{observacoes.length} observação{observacoes.length > 1 ? 'ões' : ''}</span>
        </span>
        <button
          onClick={onToggle}
          className="ml-auto text-blue-600 hover:text-blue-800 p-1"
        >
          {mostrar ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
        </button>
      </div>

      {mostrar && (
        <div className="space-y-3 mb-4 max-h-96 overflow-y-auto pr-1">
          {observacoes.map((obs, index) => (
            <motion.div
              key={obs.id || index}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3, delay: index * 0.1 }}
              className="bg-blue-50 p-4 rounded-lg border border-blue-200"
            >
              <div className="flex items-start gap-3">
                <div className="bg-blue-600 p-2 rounded-full flex-shrink-0">
                  <Mic className="h-3 w-3 text-white" />
                </div>
                <div className="flex-1">
                  <p className="text-sm text-gray-800 mb-2">{obs.texto}</p>
                  <div className="flex items-center gap-4 text-xs text-gray-600">
                    <div className="flex items-center gap-1">
                      <Clock className="h-3 w-3" />
                      <span>{formatarDataObservacao(obs.data)}</span>
                    </div>
                    <span>Por: {obs.professora}</span>
                    {obs.metadados?.confianca && (
                      <span className="bg-green-100 text-green-700 px-2 py-1 rounded">
                        Confiança: {Math.round(obs.metadados.confianca * 100)}%
                      </span>
                    )}
                  </div>
                </div>
                {podeExcluir(obs) && (
                  <button
                    type="button"
                    onClick={() => setConfirmando(obs)}
                    disabled={excluindoId === obs.id}
                    aria-label="Excluir este relato"
                    title="Excluir este relato"
                    className="text-gray-400 hover:text-red-600 disabled:opacity-40 p-1 flex-shrink-0"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                )}
              </div>
            </motion.div>
          ))}
        </div>
      )}

      <AlertDialog open={!!confirmando} onOpenChange={(aberto) => !aberto && setConfirmando(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Excluir este relato?</AlertDialogTitle>
            <AlertDialogDescription>
              O relato será apagado definitivamente e não poderá ser recuperado.
              Ele deixará de ser usado na geração dos próximos relatórios.
              Relatórios já gerados não mudam.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction
              className="bg-red-600 hover:bg-red-700"
              onClick={() => {
                const alvo = confirmando;
                setConfirmando(null);
                onExcluir(alvo);
              }}
            >
              Excluir
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
};

/*
 * `readOnly`: usado na visão da coordenação (CriancaPage), onde os relatos são
 * consulta — sem botão de excluir, como os demais blocos daquela tela.
 * Combinado com `isPlaceholder`, rende só a lista, sem o editor de texto.
 */
const IndividualReportBlock = ({ content, onContentChange, sources, isPlaceholder, nomeAluno, criancaId, periodo, readOnly = false }) => {
  const { user } = useAuth();
  const { toast } = useToast();

  const [observacoesTranscricao, setObservacoesTranscricao] = useState([]);
  const [loadingObservacoes, setLoadingObservacoes] = useState(false);
  const [mostrarObservacoes, setMostrarObservacoes] = useState(true);
  const [excluindoId, setExcluindoId] = useState(null);

  // Buscar observações de transcrição para o aluno
  const buscarObservacoesTranscricao = async () => {
    if (!nomeAluno && !criancaId) return;

    setLoadingObservacoes(true);
    try {
      const params = new URLSearchParams();
      // `crianca_id` é o vínculo confiável; o nome vai junto como fallback
      // para os relatos antigos que ficaram sem id da criança.
      if (criancaId) params.set('crianca_id', criancaId);
      if (nomeAluno) params.set('nome_aluno', nomeAluno);
      if (periodo?.data_inicio) params.set('data_inicio', periodo.data_inicio);
      if (periodo?.data_fim) params.set('data_fim', periodo.data_fim);

      const response = await authFetch(`${API_BASE_URL}/api/buscar-observacoes-transcricao/?${params.toString()}`);
      if (response.ok) {
        const data = await response.json();
        setObservacoesTranscricao(data.observacoes || []);
      } else {
        console.error('[IndividualReportBlock] Erro HTTP ao buscar observações:', response.status);
      }
    } catch (error) {
      console.error('[IndividualReportBlock] Erro ao buscar observações de transcrição:', error);
    } finally {
      setLoadingObservacoes(false);
    }
  };

  useEffect(() => {
    if (nomeAluno || criancaId) {
      buscarObservacoesTranscricao();
    }
  }, [nomeAluno, criancaId, isPlaceholder, periodo]);

  // Autora do relato ou coordenação.
  const podeExcluir = (obs) => {
    if (readOnly || !user) return false;
    const perfil = (user.perfil || '').toLowerCase();
    if (PERFIS_COORDENACAO.includes(perfil)) return true;
    return !!obs.professora_id && String(obs.professora_id) === String(user.id);
  };

  const excluirObservacao = async (obs) => {
    if (!obs?.id) return;
    setExcluindoId(obs.id);
    try {
      const response = await authFetch(
        `${API_BASE_URL}/api/observacoes-transcricao/${obs.id}/deletar/`,
        { method: 'DELETE' }
      );

      if (response.ok) {
        setObservacoesTranscricao(prev => prev.filter(o => o.id !== obs.id));
        toast({ title: 'Relato excluído' });
      } else {
        const erro = await response.json().catch(() => ({}));
        toast({
          title: 'Não foi possível excluir',
          description: erro.error || `Erro ${response.status}`,
          variant: 'destructive',
        });
      }
    } catch (error) {
      toast({
        title: 'Não foi possível excluir',
        description: error.message,
        variant: 'destructive',
      });
    } finally {
      setExcluindoId(null);
    }
  };
  if (isPlaceholder) {
     return (
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.1 }}
        className="bg-white p-6 rounded-2xl shadow-md border border-gray-100"
      >
         <div className="flex items-center gap-3 mb-4">
          <div className="bg-lavanda-claro p-2 rounded-full"><FileText className="h-5 w-5 text-roxo-principal" /></div>
          <h3 className="text-lg font-bold text-texto-escuro">Relato Individual</h3>
        </div>
        
        {/* Observações de Transcrição mesmo no placeholder */}
        <ObservacoesTranscricaoList
          observacoes={observacoesTranscricao}
          mostrar={mostrarObservacoes}
          onToggle={() => setMostrarObservacoes(!mostrarObservacoes)}
          onExcluir={excluirObservacao}
          podeExcluir={podeExcluir}
          excluindoId={excluindoId}
        />

        {observacoesTranscricao.length === 0 && <EmptyContent />}
      </motion.div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.1 }}
      className="bg-white p-6 rounded-2xl shadow-md border border-gray-100"
    >
      <div className="flex items-center gap-3 mb-4">
        <div className="bg-lavanda-claro p-2 rounded-full"><FileText className="h-5 w-5 text-roxo-principal" /></div>
        <h3 className="text-lg font-bold text-texto-escuro">Relato Individual</h3>
      </div>

      {/* Observações de Transcrição */}
      <ObservacoesTranscricaoList
        observacoes={observacoesTranscricao}
        mostrar={mostrarObservacoes}
        onToggle={() => setMostrarObservacoes(!mostrarObservacoes)}
        onExcluir={excluirObservacao}
        podeExcluir={podeExcluir}
        excluindoId={excluindoId}
      />


      {/* Textarea para edição do relato */}
      <div className="bg-lavanda-claro/50 p-4 rounded-lg border border-lavanda">
        <Textarea 
          value={content} 
          onChange={(e) => onContentChange(e.target.value)} 
          className="min-h-[150px] bg-white" 
          placeholder="Digite o relato individualou use as observações da IA como base..."
        />
        <div className="flex justify-between items-center mt-3">
          <p className="text-xs text-texto-medio italic">Texto com apoio da IA NARA</p>
          <div className="flex gap-2">
            <Button size="sm" className="bg-verde-menta/80 hover:bg-verde-menta text-texto-escuro">
              <Check className="h-4 w-4 mr-1" /> Aprovar
            </Button>
            <Button size="sm" variant="outline">
              <Pencil className="h-3 w-3 mr-1" /> Editar
            </Button>
            <Button size="sm" variant="ghost" disabled>
              <RotateCw className="h-3 w-3 mr-1" /> Regerar
            </Button>
          </div>
        </div>
      </div>

      <Accordion type="single" collapsible className="w-full mt-4">
        <AccordionItem value="item-1" className="border-b-0">
          <AccordionTrigger className="text-sm font-semibold text-roxo-principal hover:no-underline">
            Ver fontes que geraram esse texto
          </AccordionTrigger>
          <AccordionContent>
            <ul className="list-disc list-inside text-sm text-texto-medio space-y-1">
              {sources?.map((s, i) => <li key={i}>{s}</li>) || <li>Nenhuma fonte disponível.</li>}
              {observacoesTranscricao.length > 0 && (
                <li>Observações da professora via transcrição de áudio (IA)</li>
              )}
            </ul>
          </AccordionContent>
        </AccordionItem>
      </Accordion>
    </motion.div>
  );
};

export default IndividualReportBlock;