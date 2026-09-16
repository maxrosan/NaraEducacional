import React from 'react';
import { ScrollArea } from "@/components/ui/scroll-area";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Loader2, Users, Edit, Trash2, RotateCcw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { useToast } from '@/components/ui/use-toast';
import { deletarCrianca, atualizarCrianca } from '@/services/api';
import { format, parseISO } from 'date-fns';
import { safeFormatDate } from '@/lib/dateUtils';
import StudentFormDialog from './StudentFormDialog';

const getIniciais = (nome) => {
    if (!nome) return '?';
    const partes = nome.trim().split(/\s+/);
    const primeira = partes[0]?.[0] || '';
    const ultima = partes.length > 1 ? partes[partes.length - 1][0] : '';
    return (primeira + ultima).toUpperCase();
};

const AlunoAvatar = ({ aluno }) => {
    if (aluno.foto_url) {
        return (
            <img
                src={aluno.foto_url}
                alt={aluno.nome_completo}
                className="h-9 w-9 rounded-full object-cover flex-shrink-0"
            />
        );
    }
    return (
        <div className="h-9 w-9 rounded-full bg-purple-100 text-purple-700 flex items-center justify-center text-xs font-semibold flex-shrink-0">
            {getIniciais(aluno.nome_completo)}
        </div>
    );
};

const AlunosList = ({ alunos, loading, onStudentUpdated, onStudentDeleted, turmas, institutionId }) => {
    const { toast } = useToast();

    const handleDelete = async (alunoId) => {
        try {
            await deletarCrianca(alunoId);
            toast({ title: "Sucesso!", description: "Aluno desativado com sucesso." });
            onStudentDeleted(alunoId);
        } catch (error) {
            toast({ variant: "destructive", title: "Erro ao excluir", description: error.message });
        }
    };

    const handleReactivate = async (alunoId) => {
        try {
            await atualizarCrianca(alunoId, { status_vinculo: 'ativo' });
            toast({ title: "Sucesso!", description: "Aluno reativado com sucesso." });
            onStudentUpdated();
        } catch (error) {
            toast({ variant: "destructive", title: "Erro ao reativar", description: error.message });
        }
    };
  
    if (loading) {
        return (
            <div className="flex items-center justify-center h-64">
                <Loader2 className="h-8 w-8 animate-spin text-roxo-principal" />
            </div>
        );
    }

    if (alunos.length === 0) {
        return (
            <div className="flex flex-col items-center justify-center h-64 text-center border-2 border-dashed rounded-lg">
                <Users className="h-12 w-12 text-gray-400 mb-4" />
                <p className="font-semibold text-lg">Nenhum aluno encontrado</p>
                <p className="text-sm text-gray-500">Cadastre um novo aluno para começar.</p>
            </div>
        );
    }

    return (
        <ScrollArea className="h-[500px] w-full rounded-md border">
            <Table>
                <TableHeader className="sticky top-0 bg-gray-50 z-10">
                    <TableRow>
                        <TableHead>Nome Completo</TableHead>
                        <TableHead>Data de Nasc.</TableHead>
                        <TableHead>Turma</TableHead>
                        <TableHead>Responsável</TableHead>
                        <TableHead>Telefone</TableHead>
                        <TableHead className="text-right">Ações</TableHead>
                    </TableRow>
                </TableHeader>
                <TableBody>
                    {alunos.map(aluno => (
                        <TableRow key={aluno.id}>
                            <TableCell className="font-medium">
                                <div className="flex items-center gap-3">
                                    <AlunoAvatar aluno={aluno} />
                                    <div>
                                        <span className={aluno.status_vinculo === 'inativo' ? 'text-gray-400' : ''}>{aluno.nome_completo}</span>
                                        {aluno.status_vinculo === 'inativo' && (
                                            <Badge variant="secondary" className="ml-2 text-gray-500">Inativo</Badge>
                                        )}
                                    </div>
                                </div>
                            </TableCell>
                            <TableCell>{safeFormatDate(aluno.data_nascimento, 'dd/MM/yyyy', undefined, 'N/A')}</TableCell>
                            <TableCell>{aluno.turma_nome || aluno.turmas?.nome || 'Sem turma'}</TableCell>
                            <TableCell>{aluno.nome_responsavel || 'N/A'}</TableCell>
                            <TableCell>{aluno.telefone_responsavel || 'N/A'}</TableCell>
                            <TableCell className="text-right">
                                <div className="flex items-center justify-end gap-2">
                                    <StudentFormDialog
                                        studentData={aluno}
                                        turmas={turmas}
                                        institutionId={institutionId}
                                        onStudentUpdated={onStudentUpdated}
                                    >
                                        <Button variant="ghost" size="icon">
                                            <Edit className="h-4 w-4" />
                                        </Button>
                                    </StudentFormDialog>
                                    {aluno.status_vinculo === 'inativo' ? (
                                        <Button variant="ghost" size="icon" onClick={() => handleReactivate(aluno.id)} title="Reativar aluno">
                                            <RotateCcw className="h-4 w-4 text-green-600" />
                                        </Button>
                                    ) : (
                                        <AlertDialog>
                                            <AlertDialogTrigger asChild>
                                                <Button variant="ghost" size="icon">
                                                    <Trash2 className="h-4 w-4 text-red-500" />
                                                </Button>
                                            </AlertDialogTrigger>
                                            <AlertDialogContent>
                                                <AlertDialogHeader>
                                                    <AlertDialogTitle>Você tem certeza?</AlertDialogTitle>
                                                    <AlertDialogDescription>
                                                        Isso desativará o aluno
                                                        <span className="font-bold"> {aluno.nome_completo} </span>
                                                        — ele deixará de aparecer para professores e coordenação. Os registros e relatórios são mantidos, e você pode reativá-lo depois aqui na gestão de alunos.
                                                    </AlertDialogDescription>
                                                </AlertDialogHeader>
                                                <AlertDialogFooter>
                                                    <AlertDialogCancel>Cancelar</AlertDialogCancel>
                                                    <AlertDialogAction onClick={() => handleDelete(aluno.id)} className="bg-red-600 hover:bg-red-700">
                                                        Sim, desativar
                                                    </AlertDialogAction>
                                                </AlertDialogFooter>
                                            </AlertDialogContent>
                                        </AlertDialog>
                                    )}
                                </div>
                            </TableCell>
                        </TableRow>
                    ))}
                </TableBody>
            </Table>
        </ScrollArea>
    );
};

export default AlunosList;