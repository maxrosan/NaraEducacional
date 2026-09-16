import React from 'react';
import { addDays, format } from 'date-fns';
import { ptBR } from 'date-fns/locale';
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

function formatRange(inicio, fim) {
  if (!inicio || !fim) return '';
  return `${format(inicio, 'dd/MM/yyyy', { locale: ptBR })} a ${format(fim, 'dd/MM/yyyy', {
    locale: ptBR,
  })}`;
}

/**
 * Diálogo exibido quando NENHUMA das semanas detectadas pela NARA bate com a
 * semana selecionada na tela. A professora pode aplicar nas semanas detectadas
 * (a tela navega para a primeira) ou descartar (a interpretação pode estar
 * errada).
 *
 * Props:
 *  - semanaSelecionadaInicio: Date
 *  - semanasDetectadasInicio: Date[] (uma ou mais segundas-feiras)
 *  - evidencia: string
 *  - onManter, onAjustar
 */
function DataDivergenteDialog({
  open,
  semanaSelecionadaInicio,
  semanasDetectadasInicio = [],
  evidencia,
  onManter,
  onAjustar,
}) {
  const semanasOrdenadas = [...semanasDetectadasInicio].sort(
    (a, b) => a.getTime() - b.getTime()
  );

  const titulo =
    semanasOrdenadas.length > 1
      ? 'O arquivo cobre semanas diferentes da selecionada'
      : 'A semana do arquivo é diferente da selecionada';

  const labelAjustar =
    semanasOrdenadas.length > 1
      ? 'Aplicar nas semanas detectadas'
      : 'Ajustar para a semana detectada';

  return (
    <AlertDialog
      open={open}
      onOpenChange={(value) => {
        if (!value) onManter?.();
      }}
    >
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{titulo}</AlertDialogTitle>
          <AlertDialogDescription asChild>
            <div className="space-y-3 text-sm text-gray-700">
              <p>
                A NARA leu o arquivo enviado e identificou que ele se refere{' '}
                {semanasOrdenadas.length > 1
                  ? 'às semanas:'
                  : 'à semana:'}
              </p>
              <ul className="list-disc pl-5 space-y-1">
                {semanasOrdenadas.map((inicio) => (
                  <li key={inicio.toISOString()}>
                    <strong>{formatRange(inicio, addDays(inicio, 4))}</strong>
                  </li>
                ))}
              </ul>
              <p>
                A semana selecionada na tela é{' '}
                <strong>
                  {formatRange(
                    semanaSelecionadaInicio,
                    semanaSelecionadaInicio
                      ? addDays(semanaSelecionadaInicio, 4)
                      : null
                  )}
                </strong>
                .
              </p>
              {evidencia && (
                <p className="text-gray-500 italic">
                  Trecho identificado no arquivo: “{evidencia}”
                </p>
              )}
              <p>
                A informação interpretada pela NARA está correta? Se sim, aplique
                nas semanas detectadas. Se não, mantenha a semana selecionada
                (o arquivo será descartado).
              </p>
            </div>
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel onClick={onManter}>
            Manter semana selecionada
          </AlertDialogCancel>
          <AlertDialogAction onClick={onAjustar}>
            {labelAjustar}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}

export default DataDivergenteDialog;
