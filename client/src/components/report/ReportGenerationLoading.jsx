import React from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Loader2, Brain, FileText, Search, Sparkles } from 'lucide-react';

function ReportGenerationLoading({ step = 'collecting', studentName }) {
  const steps = [
    {
      key: 'collecting',
      icon: Search,
      title: 'Coletando Dados',
      description: `Buscando observações e registros de ${studentName}...`,
      duration: '~15 segundos'
    },
    {
      key: 'analyzing',
      icon: Brain,
      title: 'Analisando com a Nara',
      description: 'Processando informações e identificando padrões de desenvolvimento...',
      duration: '~30 segundos'
    },
    {
      key: 'generating',
      icon: Sparkles,
      title: 'Gerando Relatório',
      description: 'Criando narrativa pedagógica personalizada...',
      duration: '~20 segundos'
    },
    {
      key: 'finalizing',
      icon: FileText,
      title: 'Finalizando',
      description: 'Preparando relatório para edição...',
      duration: '~5 segundos'
    }
  ];

  const currentStepIndex = steps.findIndex(s => s.key === step);
  const currentStep = steps[currentStepIndex] || steps[0];
  const CurrentIcon = currentStep.icon;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <Card className="w-full max-w-md">
        <CardContent className="p-6">
          <div className="text-center space-y-6">
            {/* Ícone animado */}
            <div className="flex justify-center">
              <div className="relative">
                <div className="w-16 h-16 rounded-full bg-roxo-principal/10 flex items-center justify-center">
                  <CurrentIcon className="w-8 h-8 text-roxo-principal" />
                </div>
                <div className="absolute inset-0 rounded-full border-2 border-roxo-principal/20 animate-pulse"></div>
              </div>
            </div>

            {/* Título e descrição */}
            <div className="space-y-2">
              <h3 className="text-lg font-semibold text-gray-900">
                {currentStep.title}
              </h3>
              <p className="text-sm text-gray-600">
                {currentStep.description}
              </p>
              <p className="text-xs text-gray-400">
                Tempo estimado: {currentStep.duration}
              </p>
            </div>

            {/* Barra de progresso */}
            <div className="space-y-2">
              <div className="flex justify-between text-xs text-gray-500">
                <span>Progresso</span>
                <span>{currentStepIndex + 1} de {steps.length}</span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div 
                  className="bg-roxo-principal rounded-full h-2 transition-all duration-500"
                  style={{ 
                    width: `${((currentStepIndex + 1) / steps.length) * 100}%` 
                  }}
                ></div>
              </div>
            </div>

            {/* Lista de steps */}
            <div className="space-y-2 text-left">
              {steps.map((stepItem, index) => {
                const StepIcon = stepItem.icon;
                const isCompleted = index < currentStepIndex;
                const isCurrent = index === currentStepIndex;
                const isPending = index > currentStepIndex;

                return (
                  <div 
                    key={stepItem.key}
                    className={`flex items-center gap-3 p-2 rounded ${
                      isCurrent ? 'bg-roxo-principal/5' : ''
                    }`}
                  >
                    <div className={`flex-shrink-0 ${
                      isCompleted ? 'text-green-600' :
                      isCurrent ? 'text-roxo-principal' :
                      'text-gray-400'
                    }`}>
                      {isCompleted ? (
                        <div className="w-4 h-4 rounded-full bg-green-600 flex items-center justify-center">
                          <svg className="w-3 h-3 text-white" fill="currentColor" viewBox="0 0 20 20">
                            <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                          </svg>
                        </div>
                      ) : isCurrent ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : (
                        <StepIcon className="w-4 h-4" />
                      )}
                    </div>
                    <span className={`text-sm ${
                      isCompleted ? 'text-green-600 line-through' :
                      isCurrent ? 'text-gray-900 font-medium' :
                      'text-gray-500'
                    }`}>
                      {stepItem.title}
                    </span>
                  </div>
                );
              })}
            </div>

            {/* Mensagem de rodapé */}
            <div className="text-center">
              <p className="text-xs text-gray-500">
                Por favor, aguarde enquanto processamos as informações...
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

export default ReportGenerationLoading;