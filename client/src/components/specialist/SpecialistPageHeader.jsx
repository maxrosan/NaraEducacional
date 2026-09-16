import React from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import { Button } from '@/components/ui/button';

/**
 * Header padrão das telas do especialista — mesmo padrão visual usado em
 * SpecialistObservationPage / SpecialistReportPage (botão voltar + título
 * + logo da NARA), para manter consistência de navegação em todo o app.
 *
 * @param {string} title
 * @param {string} [subtitle]
 * @param {string} [to] - se informado, navega para essa rota; caso contrário navigate(-1)
 * @param {() => void} [onBack] - se informado, tem prioridade sobre `to` (ex: voltar etapa de um wizard)
 * @param {React.ReactNode} [action] - slot opcional à direita (ex: botão "+")
 */
export default function SpecialistPageHeader({ title, subtitle, to, onBack, action }) {
  const navigate = useNavigate();

  function handleBack() {
    if (onBack) return onBack();
    if (to) return navigate(to);
    return navigate(-1);
  }

  return (
    <header className="sticky top-0 bg-white/80 backdrop-blur-sm z-10 shadow-sm">
      <div className="container mx-auto px-4 sm:px-6 lg:px-8 py-4 flex items-center justify-between">
        <div className="flex items-center gap-4 min-w-0">
          <Button variant="ghost" size="icon" onClick={handleBack}>
            <ArrowLeft className="h-6 w-6 text-gray-600" />
          </Button>
          <div className="min-w-0">
            <h1 className="text-xl font-bold text-gray-800 truncate">{title}</h1>
            {subtitle && <p className="text-xs sm:text-sm text-gray-500 truncate">{subtitle}</p>}
          </div>
        </div>
        <div className="flex items-center gap-3 flex-shrink-0">
          {action}
          <img alt="NARA icon logo" className="h-12 w-auto sm:h-14" src="/nara-logo.png" />
        </div>
      </div>
    </header>
  );
}