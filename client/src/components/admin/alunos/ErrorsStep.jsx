import React from 'react';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { AlertTriangle, CheckCircle, Download } from 'lucide-react';

const ErrorsStep = ({ successCount, errors, onFinish }) => {
    const handleDownloadErrors = () => {
        const lines = errors.map(
            (e, i) => `${i + 1}. ${e.nome} — ${e.message}`
        );
        const content = `Erros na importação de alunos\n${'='.repeat(40)}\n\n${lines.join('\n')}`;
        const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = 'erros_importacao_alunos.txt';
        link.click();
        URL.revokeObjectURL(url);
    };

    return (
        <div className="flex flex-col items-center space-y-6 p-6">
            <AlertTriangle className="h-16 w-16 text-amber-500" />
            <div className="space-y-1 text-center">
                <h2 className="text-xl font-bold text-gray-800">Importação concluída com erros</h2>
                <p className="text-sm text-gray-600">
                    <span className="font-semibold text-green-600">{successCount}</span>{' '}
                    {successCount === 1 ? 'aluno cadastrado' : 'alunos cadastrados'} com sucesso,{' '}
                    <span className="font-semibold text-red-600">{errors.length}</span>{' '}
                    {errors.length === 1 ? 'falha' : 'falhas'}.
                </p>
            </div>

            <ScrollArea className="w-full max-h-60 rounded-md border p-3">
                <ul className="space-y-2">
                    {errors.map((e, i) => (
                        <li key={i} className="text-sm text-red-700 flex items-start gap-2">
                            <span className="font-medium shrink-0">{e.nome}:</span>
                            <span className="text-gray-600">{e.message}</span>
                        </li>
                    ))}
                </ul>
            </ScrollArea>

            <div className="flex gap-3">
                <Button variant="outline" onClick={handleDownloadErrors}>
                    <Download className="mr-2 h-4 w-4" />
                    Baixar erros (.txt)
                </Button>
                <Button onClick={onFinish}>
                    <CheckCircle className="mr-2 h-4 w-4" />
                    Finalizar
                </Button>
            </div>
        </div>
    );
};

export default ErrorsStep;
