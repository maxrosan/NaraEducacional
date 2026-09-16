import React, { useState, useCallback } from 'react';
import * as XLSX from 'xlsx';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogTrigger,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Upload, Download, ArrowRight, ArrowLeft } from 'lucide-react';
import { useToast } from '@/components/ui/use-toast';
import { criarCriancasLote } from '@/services/api';
import { formatDateForApi } from '@/lib/dateUtils';
import UploadStep from './UploadStep';
import ConfirmationStep from './ConfirmationStep';
import ProcessingStep from './ProcessingStep';
import SuccessStep from './SuccessStep';
import ErrorsStep from './ErrorsStep';

const BulkUploadDialog = ({ turmas, institutionId, onUploadComplete }) => {
    const [isOpen, setIsOpen] = useState(false);
    const [step, setStep] = useState('upload'); // upload, confirmation, processing, success, errors
    const [studentsToConfirm, setStudentsToConfirm] = useState([]);
    const [processing, setProcessing] = useState(false);
    const [progress, setProgress] = useState({ current: 0, total: 0, currentName: '' });
    const [uploadResult, setUploadResult] = useState({ successCount: 0, errors: [] });
    const { toast } = useToast();

    const turmasMap = turmas.reduce((acc, turma) => {
        acc[turma.nome.toLowerCase().trim()] = turma.id;
        return acc;
    }, {});
    
    const handleDownloadTemplate = () => {
        const link = document.createElement('a');
        link.href = `${import.meta.env.BASE_URL}modelo_alunos.xlsx`;
        link.download = 'modelo_alunos.xlsx';
        link.click();
    };

    const processFile = useCallback((file) => {
        if (!file) {
            toast({ variant: 'destructive', title: 'Nenhum arquivo selecionado' });
            return;
        }
        setProcessing(true);
        const reader = new FileReader();
        reader.onload = (e) => {
            try {
                const data = new Uint8Array(e.target.result);
                const workbook = XLSX.read(data, { type: 'array' });
                const firstSheetName = workbook.SheetNames[0];
                const worksheet = workbook.Sheets[firstSheetName];
                const jsonData = XLSX.utils.sheet_to_json(worksheet);

                if (jsonData.length === 0) {
                    throw new Error("A planilha está vazia.");
                }

                const COLUMN_ALIASES = {
                    nome_completo: ['Nome do aluno', 'Nome Completo', 'Nome', 'Aluno', 'nome'],
                    data_nascimento: ['Data de nascimento', 'Data de Nasc.', 'Data Nasc', 'Nascimento', 'data_nasc'],
                    nome_responsavel: ['Nome do responsável', 'Responsável', 'Responsavel', 'Nome Responsável', 'Nome Responsavel'],
                    telefone: ['Telefone', 'Tel', 'Celular', 'Contato', 'telefone_responsavel'],
                    turma: ['Turma', 'Classe', 'Sala'],
                };

                const col = (key, row) => {
                    if (row[key] !== undefined) return row[key];
                    const aliases = COLUMN_ALIASES[key] || [];
                    for (const alias of aliases) {
                        if (row[alias] !== undefined) return row[alias];
                    }
                    return undefined;
                };

                const processedStudents = jsonData.map((row, index) => {

                    const nome_completo = String(col('nome_completo', row) ?? '').trim() || undefined;
                    const data_nascimento_raw = col('data_nascimento', row);
                    const nome_responsavel = String(col('nome_responsavel', row) ?? '').trim() || undefined;
                    const telefone = String(col('telefone', row) ?? '').trim();
                    const turma_nome = String(col('turma', row) ?? '').toLowerCase().trim() || undefined;

                    const errors = [];
                    if (!nome_completo) errors.push('Nome do aluno é obrigatório.');
                    if (!data_nascimento_raw) errors.push('Data de nascimento é obrigatória.');
                    if (!nome_responsavel) errors.push('Nome do responsável é obrigatório.');
                    if (!telefone) errors.push('Telefone é obrigatório.');
                    if (!turma_nome) errors.push('Turma é obrigatória.');
                    
                    const data_nascimento = formatDateForApi(data_nascimento_raw);
                    if (!data_nascimento) errors.push('Formato de data inválido. Use dd/mm/aaaa.');
                    
                    const turma_raw = String(col('turma', row) ?? '').trim();
                    const turma_id = turmasMap[turma_nome];
                    if (!turma_id) errors.push(`Turma "${turma_raw}" não encontrada.`);

                    return {
                        id: index,
                        nome_completo,
                        data_nascimento,
                        nome_responsavel,
                        telefone_responsavel: telefone,
                        turma_id,
                        turma_nome: turma_raw,
                        errors,
                    };
                });
                
                const studentsWithErrors = processedStudents.filter(s => s.errors.length > 0);
                if (studentsWithErrors.length > 0) {
                    studentsWithErrors.forEach(student => {
                        toast({
                            variant: 'destructive',
                            title: `Erro na linha de ${student.nome_completo || 'aluno desconhecido'}`,
                            description: student.errors.join(' '),
                        });
                    });
                    setProcessing(false);
                    return;
                }

                setStudentsToConfirm(processedStudents);
                setStep('confirmation');

            } catch (error) {
                 toast({ variant: 'destructive', title: 'Erro ao processar arquivo', description: error.message });
            } finally {
                setProcessing(false);
            }
        };
        reader.readAsArrayBuffer(file);
    }, [toast, turmasMap]);

    const handleFinalUpload = async () => {
        setProcessing(true);
        setStep('processing');
        setProgress({ current: 0, total: studentsToConfirm.length, currentName: '' });

        const studentsToInsert = studentsToConfirm.map(s => ({
            instituicao_id: institutionId,
            nome_completo: s.nome_completo,
            data_nascimento: s.data_nascimento,
            nome_responsavel: s.nome_responsavel,
            telefone_responsavel: s.telefone_responsavel,
            turma_id: s.turma_id,
        }));

        const { successCount, errors } = await criarCriancasLote(
            studentsToInsert,
            (current, total, nome) => setProgress({ current, total, currentName: nome })
        );

        setUploadResult({ successCount, errors });
        setProcessing(false);
        onUploadComplete();

        if (errors.length > 0) {
            setStep('errors');
        } else {
            setStep('success');
        }
    };
    
    const reset = () => {
        setStep('upload');
        setStudentsToConfirm([]);
        setProcessing(false);
        setProgress({ current: 0, total: 0, currentName: '' });
        setUploadResult({ successCount: 0, errors: [] });
    }
    
    const handleOpenChange = (open) => {
        if (!open && step === 'processing') return;
        setIsOpen(open);
        if (!open) {
            reset();
        }
    }

    return (
        <Dialog open={isOpen} onOpenChange={handleOpenChange}>
            <DialogTrigger asChild>
                <Button variant="outline">
                    <Download className="mr-2 h-4 w-4" />
                    Importar em Massa
                </Button>
            </DialogTrigger>
            <DialogContent className="sm:max-w-3xl">
                <DialogHeader>
                    <DialogTitle>Importação de Alunos em Massa</DialogTitle>
                    <DialogDescription>
                        {step === 'upload' && 'Faça o upload de um arquivo .xlsx para cadastrar múltiplos alunos.'}
                        {step === 'confirmation' && 'Revise os dados antes de confirmar a importação.'}
                        {step === 'processing' && 'Aguarde enquanto os alunos são cadastrados...'}
                        {step === 'success' && 'A importação foi concluída com sucesso.'}
                        {step === 'errors' && 'A importação foi concluída com alguns erros.'}
                    </DialogDescription>
                </DialogHeader>

                {step === 'upload' && (
                    <UploadStep onProcessFile={processFile} onDownloadTemplate={handleDownloadTemplate} processing={processing} />
                )}

                {step === 'confirmation' && (
                    <ConfirmationStep
                        students={studentsToConfirm}
                        onConfirm={handleFinalUpload}
                        onBack={() => setStep('upload')}
                        processing={processing}
                        turmas={turmas}
                    />
                )}

                {step === 'processing' && (
                    <ProcessingStep
                        current={progress.current}
                        total={progress.total}
                        currentName={progress.currentName}
                    />
                )}

                {step === 'success' && (
                    <SuccessStep studentCount={uploadResult.successCount} onFinish={reset} />
                )}

                {step === 'errors' && (
                    <ErrorsStep
                        successCount={uploadResult.successCount}
                        errors={uploadResult.errors}
                        onFinish={reset}
                    />
                )}
            </DialogContent>
        </Dialog>
    );
};

export default BulkUploadDialog;
