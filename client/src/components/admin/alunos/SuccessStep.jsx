import React from 'react';
import { Button } from '@/components/ui/button';
import { CheckCircle, PartyPopper } from 'lucide-react';

const SuccessStep = ({ studentCount, onFinish }) => {
    return (
        <div className="text-center p-8 flex flex-col items-center justify-center space-y-6">
            <PartyPopper className="h-20 w-20 text-green-500" />
            <div className="space-y-2">
                <h2 className="text-2xl font-bold text-gray-800">Importação Concluída!</h2>
                <p className="text-lg text-gray-600">
                    <span className="font-semibold text-green-600">{studentCount}</span> {studentCount === 1 ? 'aluno foi cadastrado' : 'alunos foram cadastrados'} com sucesso.
                </p>
            </div>
            <Button onClick={onFinish}>
                <CheckCircle className="mr-2 h-4 w-4" />
                Finalizar
            </Button>
        </div>
    );
};

export default SuccessStep;