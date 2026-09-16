import React, { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { BookOpen, Loader2, Calendar, Lock, Trash2 } from 'lucide-react';

import EmptyContent from '@/components/reports/EmptyContent';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter, DialogClose } from '@/components/ui/dialog';
import { toast } from '@/components/ui/use-toast';
import { apiService } from '@/services/api';
import { formatLeituraLabel as formatLabel } from '@/lib/observationUtils';

const formatDate = (iso) => {
  if (!iso) return '';
  try {
    return new Date(iso).toLocaleDateString('pt-BR', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
    });
  } catch {
    return iso;
  }
};

const formatDuration = (seconds) => {
  if (seconds == null) return null;
  const total = Math.round(Number(seconds));
  if (Number.isNaN(total) || total <= 0) return null;
  const mins = Math.floor(total / 60);
  const secs = total % 60;
  return mins > 0 ? `${mins}m${String(secs).padStart(2, '0')}s` : `${secs}s`;
};

const ReadingAnalysisBlock = ({ criancaId, periodo, readOnly = false }) => {
  const [registros, setRegistros] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [deletingRegistro, setDeletingRegistro] = useState(null);

  const carregar = async () => {
    if (!criancaId) return;
    setLoading(true);
    setError(null);
    try {
      const data = await apiService.listarAnalisesLeitura({
        criancaId,
        dataInicio: periodo?.data_inicio,
        dataFim: periodo?.data_fim,
      });
      setRegistros(data.registros || []);
    } catch (err) {
      console.error('[ReadingAnalysisBlock] erro ao carregar:', err);
      setError('Não foi possível carregar as análises de leitura.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    carregar();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [criancaId, periodo?.data_inicio, periodo?.data_fim]);

  const handleDelete = async () => {
    if (!deletingRegistro) return;
    try {
      await apiService.deletarAnaliseLeitura(deletingRegistro.id);
      toast({ title: 'Análise de leitura excluída com sucesso.' });
      setDeletingRegistro(null);
      carregar();
    } catch (err) {
      console.error('[ReadingAnalysisBlock] erro ao excluir:', err);
      toast({ variant: 'destructive', title: 'Erro ao excluir', description: err.message });
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.2 }}
      className="bg-white p-6 rounded-2xl shadow-md border border-gray-100"
    >
      <div className="flex items-center gap-3 mb-4">
        <div className="bg-lavanda-claro p-2 rounded-full">
          <BookOpen className="h-5 w-5 text-roxo-principal" />
        </div>
        <h3 className="text-lg font-bold text-texto-escuro">Análises de Leitura</h3>
        {loading && <Loader2 className="h-4 w-4 animate-spin text-roxo-principal ml-2" />}
        <span className="text-xs text-gray-500 ml-2">({registros.length} registros)</span>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 p-3 rounded-lg mb-4 flex items-center gap-3">
          <span className="flex-1">{error}</span>
          <Button onClick={carregar} variant="outline" size="sm">
            Tentar novamente
          </Button>
        </div>
      )}

      {!loading && !error && registros.length === 0 ? (
        <EmptyContent />
      ) : (
        <div className="space-y-4">
          {registros.map((registro, index) => {
            const duracao = formatDuration(registro.duracao_seg);
            return (
              <motion.div
                key={registro.id}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.3, delay: index * 0.05 }}
                className="p-4 rounded-lg bg-gray-50 border border-gray-200 hover:border-roxo-claro transition-colors"
              >
                <div className="flex flex-wrap items-center gap-3 mb-3">
                  <div className="bg-lavanda-claro p-2 rounded-md text-xs text-roxo-principal flex items-center gap-2">
                    <Lock className="h-3 w-3" />
                    <span className="font-semibold">Classificação:</span>
                    <span className="italic">{formatLabel(registro.classe_escolhida)}</span>
                  </div>
                  <div className="flex items-center gap-1 text-xs text-texto-medio">
                    <Calendar className="h-3 w-3" />
                    <span>{formatDate(registro.data_criacao)}</span>
                  </div>
                  {duracao && (
                    <span className="text-xs text-texto-medio">Duração: {duracao}</span>
                  )}
                  {!readOnly && (
                    <Button
                      variant="ghost"
                      size="icon"
                      className="ml-auto h-8 w-8 text-red-500 hover:text-red-700 hover:bg-red-50"
                      title="Excluir análise de leitura"
                      onClick={() => setDeletingRegistro(registro)}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  )}
                </div>

                {registro.audio_url ? (
                  <audio
                    controls
                    preload="none"
                    src={registro.audio_url}
                    className="w-full"
                    onError={() => {
                      console.warn('Não foi possível carregar o áudio:', registro.audio_url);
                    }}
                  >
                    Seu navegador não suporta a reprodução do áudio.
                  </audio>
                ) : (
                  <div className="text-xs text-texto-medio italic">
                    Áudio indisponível no momento.
                  </div>
                )}

                {registro.anotacoes_professora && (
                  <p className="mt-3 text-sm text-texto-medio whitespace-pre-wrap">
                    {registro.anotacoes_professora}
                  </p>
                )}
              </motion.div>
            );
          })}
        </div>
      )}

      <Dialog open={!!deletingRegistro} onOpenChange={() => setDeletingRegistro(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Confirmar Exclusão</DialogTitle>
            <DialogDescription>
              Tem certeza que deseja excluir esta análise de leitura? Esta ação é irreversível
              e o áudio gravado também será removido.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <DialogClose asChild>
              <Button variant="outline">Cancelar</Button>
            </DialogClose>
            <Button variant="destructive" onClick={handleDelete}>Excluir</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </motion.div>
  );
};

export default ReadingAnalysisBlock;