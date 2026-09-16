import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Progress } from '@/components/ui/progress';
import { Clock, Loader2, CheckCircle2, AlertCircle, Download, X } from 'lucide-react';
import { useToast } from '@/components/ui/use-toast';
import { bulkPdfRelatoriosStream } from '@/services/api';

const STATUS = {
  PENDING: 'pending',
  GENERATING: 'generating',
  READY: 'ready',
  ERROR: 'error',
};

function StatusIcon({ status }) {
  if (status === STATUS.GENERATING) {
    return <Loader2 className="h-4 w-4 text-purple-600 animate-spin" />;
  }
  if (status === STATUS.READY) {
    return <CheckCircle2 className="h-4 w-4 text-green-600" />;
  }
  if (status === STATUS.ERROR) {
    return <AlertCircle className="h-4 w-4 text-red-600" />;
  }
  return <Clock className="h-4 w-4 text-gray-400" />;
}

function statusLabel(status) {
  switch (status) {
    case STATUS.GENERATING:
      return 'Gerando...';
    case STATUS.READY:
      return 'Pronto';
    case STATUS.ERROR:
      return 'Falhou';
    default:
      return 'Aguardando';
  }
}

function triggerBrowserDownload(url, suggestedName) {
  const link = document.createElement('a');
  link.href = url;
  if (suggestedName) link.download = suggestedName;
  link.rel = 'noopener';
  document.body.appendChild(link);
  link.click();
  link.remove();
}

/**
 * Modal que acompanha a geração em lote dos PDFs de relatórios.
 * Props:
 *   - isOpen: boolean
 *   - onClose: () => void
 *   - reports: Array<{ id, nome, turma?, periodo? }>
 */
function BulkReportDownloadModal({ isOpen, onClose, reports }) {
  const { toast } = useToast();
  const [statusById, setStatusById] = useState({});
  const [errorById, setErrorById] = useState({});
  const [phase, setPhase] = useState('idle');
  const [result, setResult] = useState(null);
  const controllerRef = useRef(null);
  const startedRef = useRef(false);

  const reportsById = useMemo(() => {
    const map = new Map();
    (reports || []).forEach((r) => map.set(String(r.id), r));
    return map;
  }, [reports]);

  useEffect(() => {
    if (!isOpen) return;
    if (startedRef.current) return;
    if (!reports || reports.length === 0) return;
    startedRef.current = true;

    const initial = {};
    reports.forEach((r) => { initial[String(r.id)] = STATUS.PENDING; });
    setStatusById(initial);
    setErrorById({});
    setResult(null);
    setPhase('running');

    const controller = new AbortController();
    controllerRef.current = controller;

    bulkPdfRelatoriosStream({
      ids: reports.map((r) => String(r.id)),
      signal: controller.signal,
      onEvent: (evt) => {
        if (evt?.type === 'progress' && evt.id) {
          setStatusById((prev) => ({ ...prev, [evt.id]: evt.status }));
          if (evt.status === STATUS.ERROR && evt.error) {
            setErrorById((prev) => ({ ...prev, [evt.id]: evt.error }));
          }
        } else if (evt?.type === 'zipping') {
          setPhase('zipping');
        } else if (evt?.type === 'uploading') {
          setPhase('uploading');
        }
      },
    })
      .then((doneEvt) => {
        setResult(doneEvt);
        setPhase('done');
        if (doneEvt?.download_url && doneEvt.success_count > 0) {
          triggerBrowserDownload(doneEvt.download_url, doneEvt.zip_filename);
          if (doneEvt.fail_count > 0) {
            toast({
              variant: 'destructive',
              title: `${doneEvt.fail_count} relatório(s) falharam`,
              description: 'O ZIP foi baixado com os que funcionaram.',
            });
          } else {
            toast({
              title: 'Download iniciado',
              description: `${doneEvt.success_count} relatório(s) empacotados em ZIP.`,
            });
          }
        } else {
          toast({
            variant: 'destructive',
            title: 'Nenhum PDF foi gerado',
            description: doneEvt?.error || 'Todos os relatórios selecionados falharam.',
          });
        }
      })
      .catch((err) => {
        if (controller.signal.aborted) {
          setPhase('cancelled');
          return;
        }
        console.error('Erro no download em lote:', err);
        setPhase('error');
        toast({
          variant: 'destructive',
          title: 'Erro ao baixar em lote',
          description: err?.message || 'Tente novamente em instantes.',
        });
      });

    return () => {
      controller.abort();
    };
    // Só inicia quando o modal abre — dependências sob controle via startedRef.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen) {
      controllerRef.current?.abort();
      controllerRef.current = null;
      startedRef.current = false;
      setStatusById({});
      setErrorById({});
      setPhase('idle');
      setResult(null);
    }
  }, [isOpen]);

  const counts = useMemo(() => {
    let pending = 0;
    let generating = 0;
    let ready = 0;
    let error = 0;
    Object.values(statusById).forEach((s) => {
      if (s === STATUS.READY) ready += 1;
      else if (s === STATUS.ERROR) error += 1;
      else if (s === STATUS.GENERATING) generating += 1;
      else pending += 1;
    });
    return { pending, generating, ready, error, total: reports?.length || 0 };
  }, [statusById, reports]);

  const progressPct = counts.total
    ? Math.round(((counts.ready + counts.error) / counts.total) * 100)
    : 0;

  const isRunning = phase === 'running' || phase === 'zipping' || phase === 'uploading';
  const canClose = !isRunning;
  const downloadUrl = result?.download_url;
  const zipFilename = result?.zip_filename;

  const handleCancel = () => {
    controllerRef.current?.abort();
  };

  const handleRedownload = () => {
    if (!downloadUrl) return;
    triggerBrowserDownload(downloadUrl, zipFilename);
  };

  const handleDialogOpenChange = (open) => {
    if (!open && canClose) {
      onClose?.();
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={handleDialogOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Download className="h-5 w-5 text-purple-600" />
            Download de relatórios em lote
          </DialogTitle>
          <DialogDescription>
            {phase === 'zipping'
              ? 'Preparando ZIP…'
              : phase === 'uploading'
                ? 'Enviando ZIP para download…'
                : phase === 'running'
                  ? `Gerando ${counts.ready + counts.error + counts.generating}/${counts.total}…`
                  : phase === 'done'
                    ? `Concluído — ${counts.ready} pronto(s), ${counts.error} falha(s).`
                    : phase === 'cancelled'
                      ? 'Operação cancelada.'
                      : phase === 'error'
                        ? 'Ocorreu um erro ao processar o lote.'
                        : 'Preparando…'}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <Progress value={progressPct} />

          <ScrollArea className="h-72 rounded-md border border-gray-200 bg-gray-50/50 p-2">
            <ul className="space-y-1">
              {(reports || []).map((r) => {
                const s = statusById[String(r.id)] || STATUS.PENDING;
                const errMsg = errorById[String(r.id)];
                return (
                  <li
                    key={r.id}
                    className="flex items-start gap-3 rounded-md bg-white px-3 py-2 border border-gray-100"
                  >
                    <div className="mt-0.5 shrink-0">
                      <StatusIcon status={s} />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="text-sm font-medium text-gray-800 truncate">
                        {r.nome || 'Estudante'}
                      </div>
                      <div className="text-xs text-gray-500 truncate">
                        {[r.turma, r.periodo].filter(Boolean).join(' • ') || '—'}
                      </div>
                      {s === STATUS.ERROR && errMsg && (
                        <div className="text-xs text-red-600 mt-1 truncate" title={errMsg}>
                          {errMsg}
                        </div>
                      )}
                    </div>
                    <span
                      className={`text-xs shrink-0 self-center ${
                        s === STATUS.READY ? 'text-green-700'
                          : s === STATUS.ERROR ? 'text-red-700'
                            : s === STATUS.GENERATING ? 'text-purple-700'
                              : 'text-gray-500'
                      }`}
                    >
                      {statusLabel(s)}
                    </span>
                  </li>
                );
              })}
            </ul>
          </ScrollArea>
        </div>

        <div className="flex justify-end gap-2 pt-2 border-t">
          {isRunning ? (
            <Button variant="outline" onClick={handleCancel}>
              <X className="mr-2 h-4 w-4" />
              Cancelar
            </Button>
          ) : (
            <>
              {downloadUrl && (
                <Button variant="outline" onClick={handleRedownload}>
                  <Download className="mr-2 h-4 w-4" />
                  Baixar novamente
                </Button>
              )}
              <Button onClick={() => onClose?.()}>Fechar</Button>
            </>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}

export default BulkReportDownloadModal;
