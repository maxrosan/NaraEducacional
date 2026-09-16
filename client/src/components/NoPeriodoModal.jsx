import React from 'react';
import { useNavigate } from 'react-router-dom';
import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogAction,
} from '@/components/ui/alert-dialog';

const TITLE = 'Fora do Per\u00edodo Avaliativo';
const DESCRIPTION =
  'N\u00e3o \u00e9 poss\u00edvel enviar registros no momento. Nenhum per\u00edodo avaliativo ' +
  'est\u00e1 ativo para a sua institui\u00e7\u00e3o. Entre em contato com a coordena\u00e7\u00e3o ' +
  'para verificar os per\u00edodos configurados.';

const NoPeriodoModal = ({ open }) => {
  const navigate = useNavigate();

  return (
    <AlertDialog open={open}>
      <AlertDialogContent onEscapeKeyDown={(e) => e.preventDefault()}>
        <AlertDialogHeader>
          <AlertDialogTitle>{TITLE}</AlertDialogTitle>
          <AlertDialogDescription>{DESCRIPTION}</AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogAction onClick={() => navigate('/home-professor')}>
            Voltar
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
};

export default NoPeriodoModal;
