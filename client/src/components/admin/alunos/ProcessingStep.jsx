import React from 'react';
import { Progress } from '@/components/ui/progress';
import { Loader2 } from 'lucide-react';

const ProcessingStep = ({ current, total, currentName }) => {
    const percent = total > 0 ? Math.round((current / total) * 100) : 0;

    return (
        <div className="flex flex-col items-center justify-center space-y-6 p-8">
            <Loader2 className="h-12 w-12 text-[var(--roxo-principal)] animate-spin" />
            <div className="space-y-2 text-center">
                <h2 className="text-lg font-semibold text-gray-800">
                    Cadastrando aluno {current} de {total}
                </h2>
                {currentName && (
                    <p className="text-sm text-gray-500">{currentName}</p>
                )}
            </div>
            <div className="w-full max-w-md space-y-1">
                <Progress value={percent} className="h-3" />
                <p className="text-xs text-gray-400 text-right">{percent}%</p>
            </div>
        </div>
    );
};

export default ProcessingStep;
