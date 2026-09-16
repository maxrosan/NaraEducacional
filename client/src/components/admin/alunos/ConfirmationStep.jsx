import React from 'react';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ArrowLeft, CheckCircle, Loader2 } from 'lucide-react';
import { format, parseISO } from 'date-fns';
import { safeFormatDate } from '@/lib/dateUtils';

const ConfirmationStep = ({ students, onConfirm, onBack, processing, turmas }) => {
    const turmasMap = turmas.reduce((acc, turma) => {
        acc[turma.id] = turma.nome;
        return acc;
    }, {});

    return (
        <div className="p-4 space-y-4">
            <h3 className="text-lg font-medium">Revise os {students.length} alunos a serem importados:</h3>
            <ScrollArea className="h-[400px] w-full rounded-md border">
                <Table>
                    <TableHeader className="sticky top-0 bg-gray-50 z-10">
                        <TableRow>
                            <TableHead>Nome Completo</TableHead>
                            <TableHead>Nascimento</TableHead>
                            <TableHead>Responsável</TableHead>
                            <TableHead>Telefone</TableHead>
                            <TableHead>Turma</TableHead>
                        </TableRow>
                    </TableHeader>
                    <TableBody>
                        {students.map((student) => (
                            <TableRow key={student.id}>
                                <TableCell>{student.nome_completo}</TableCell>
                                <TableCell>{safeFormatDate(student.data_nascimento, 'dd/MM/yyyy')}</TableCell>
                                <TableCell>{student.nome_responsavel}</TableCell>
                                <TableCell>{student.telefone_responsavel}</TableCell>
                                <TableCell>{turmasMap[student.turma_id]}</TableCell>
                            </TableRow>
                        ))}
                    </TableBody>
                </Table>
            </ScrollArea>
            <div className="flex justify-between items-center pt-4">
                <Button variant="outline" onClick={onBack} disabled={processing}>
                    <ArrowLeft className="mr-2 h-4 w-4" /> Voltar
                </Button>
                <Button onClick={onConfirm} disabled={processing}>
                    {processing ? (
                        <>
                            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                            Salvando...
                        </>
                    ) : (
                        <>
                            <CheckCircle className="mr-2 h-4 w-4" />
                            Confirmar Importação
                        </>
                    )}
                </Button>
            </div>
        </div>
    );
};

export default ConfirmationStep;