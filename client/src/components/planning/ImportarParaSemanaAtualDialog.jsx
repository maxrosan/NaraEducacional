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
 * Diálogo de fallback exibido depois que a professora escolhe "Manter semana
 * selecionada" no DataDivergenteDialog. Permite reaproveitar o conteúdo do
 * arquivo importando para a semana atual — mapeia segunda→segunda,
 * terça→terça, etc., trocando apenas a data.
 *
 * Props:
 *  - open: boolean
 *  - semanaSelecionadaInicio: Date
 *  - semanasDoArquivo: Date[] (segundas-feiras detectadas no arquivo)
 *  - onImportar()
 *  - onDescartar()
 */
function ImportarParaSemanaAtualDialog({
  open,
  semanaSelecionadaInicio,
  semanasDoArquivo = [],
  onImportar,
  onDescartar,
}) {
  const semanasOrdenadas = [...semanasDoArquivo].sort(
    (a, b) => a.getTime() - b.getTime()
  );
  const primeiraSemana = semanasOrdenadas[0];

  // Tanto AlertDialogAction quanto AlertDialogCancel fecham o diálogo, o que
  // dispara onOpenChange(false). Sem distinguir a intenção, clicar em "Importar"
  // também acionava onDescartar — o toast de descarte sobrescrevia o de sucesso
  // e dava a impressão de que o arquivo tinha sido descartado. Guardamos a
  // intenção no clique do botão (que roda antes do onOpenChange) e só tratamos
  // como descarte o que NÃO foi uma importação explícita (inclui dismiss por
  // Esc/clique fora, onde a intenção fica nula).
  const intencaoRef = React.useRef(null);

  const handleOpenChange = (value) => {
    if (value) return;
    const intencao = intencaoRef.current;
    intencaoRef.current = null;
    if (intencao === 'importar') {
      onImportar?.();
    } else {
      onDescartar?.();
    }
  };

  return (
    <AlertDialog open={open} onOpenChange={handleOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>
            Importar atividades para a semana atual?
          </AlertDialogTitle>
          <AlertDialogDescription asChild>
            <div className="space-y-3 text-sm text-gray-700">
              <p>
                O arquivo enviado se refere{' '}
                {semanasOrdenadas.length > 1
                  ? 'a outras semanas, diferentes da selecionada.'
                  : 'a outra semana, diferente da selecionada.'}
              </p>
              <p>
                Deseja importar essas atividades para a semana atual{' '}
                <strong>
                  {formatRange(
                    semanaSelecionadaInicio,
                    semanaSelecionadaInicio
                      ? addDays(semanaSelecionadaInicio, 4)
                      : null
                  )}
                </strong>
                ? A NARA usa o conteúdo da{' '}
                {semanasOrdenadas.length > 1 ? 'primeira semana detectada (' : ''}
                {primeiraSemana
                  ? formatRange(primeiraSemana, addDays(primeiraSemana, 4))
                  : ''}
                {semanasOrdenadas.length > 1 ? ')' : ''} e mapeia cada dia da
                semana — segunda→segunda, terça→terça, e assim por diante.
              </p>
              <p className="text-gray-500 italic">
                Atenção: o conteúdo dos dias da semana atual será sobrescrito.
              </p>
            </div>
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel
            onClick={() => {
              intencaoRef.current = 'descartar';
            }}
          >
            Descartar arquivo
          </AlertDialogCancel>
          <AlertDialogAction
            onClick={() => {
              intencaoRef.current = 'importar';
            }}
          >
            Importar para a semana atual
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}

export default ImportarParaSemanaAtualDialog;
