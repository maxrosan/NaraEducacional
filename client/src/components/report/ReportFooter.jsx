import React from 'react';
import { ArrowLeft, Save, BrainCircuit, Check } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useNavigate } from 'react-router-dom';

const ReportFooter = () => {
  const navigate = useNavigate();
  return (
    <footer className="fixed bottom-0 left-0 right-0 bg-white/90 backdrop-blur-sm border-t z-10">
      <div className="container mx-auto px-4 sm:px-6 lg:px-8 py-2 sm:py-3 flex flex-nowrap items-center justify-between gap-1.5 sm:gap-2">
        <Button variant="ghost" size="sm" className="text-xs sm:text-sm" onClick={() => navigate('/relatorios')}>
          <ArrowLeft className="h-4 w-4 mr-1 sm:mr-2" />
        </Button>
        <div className="flex flex-nowrap items-center gap-1.5 sm:gap-2">
          <Button variant="outline" size="sm" className="text-xs sm:text-sm" disabled>
            <BrainCircuit className="h-4 w-4 mr-1 sm:mr-2" />
          </Button>
          <Button variant="outline" size="sm" className="text-xs sm:text-sm">
            <Save className="h-4 w-4 mr-1 sm:mr-2" /> <span>Salvar</span>
          </Button>
          <Button size="sm" className="bg-verde-menta hover:bg-verde-menta/80 text-texto-escuro text-xs sm:text-sm">
            <Check className="h-4 w-4 mr-1 sm:mr-2" /> <span>Aprovar</span>
          </Button>
        </div>
      </div>
    </footer>
  );
};

export default ReportFooter;