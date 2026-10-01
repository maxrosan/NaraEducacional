import React from 'react';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Users, Edit, Trash2, RotateCcw } from 'lucide-react';
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
import { safeFormatDate } from '@/lib/dateUtils';
import StudentFormDialog from './StudentFormDialog';

const STATUS_INATIVOS = { inativo: 'Inativo', transferido: 'Transferido' };

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
                loading="lazy"
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

/**
 * Tabela de alunos de UMA página (a paginação é do AlunosTab). Desativar e
 * reativar mudam o `status_vinculo`; o aluno sai da aba atual e o pai recarrega.
 */
const AlunosList = ({ alunos, onStudentUpdated, onStudentDeleted, turmas, mensagemVazia, mostrarEscola }) => {
    const { toast } = useToast();

    const handleDelete = async (aluno) => {
        try {
            await deletarCrianca(aluno.id);
            toast({ title: "Sucesso!", description: `${aluno.nome_completo} foi desativado(a).` });
            onStudentDeleted(aluno.id);
        } catch (error) {
            toast({ variant: "destructive", title: "Erro ao desativar", description: error.message });
        }
    };

    const handleReactivate = async (aluno) => {
        try {
            await atualizarCrianca(aluno.id, { status_vinculo: 'ativo' });
            toast({ title: "Sucesso!", description: `${aluno.nome_completo} foi reativado(a).` });
            onStudentUpdated();
        } catch (error) {
            toast({ variant: "destructive", title: "Erro ao reativar", description: error.message });
        }
    };

    if (alunos.length === 0) {
        return (
            <div className="flex flex-col items-center justify-center h-64 text-center border-2 border-dashed rounded-lg">
                <Users className="h-12 w-12 text-gray-400 mb-4" />
                <p className="font-semibold text-lg">Nenhum aluno encontrado</p>
                <p className="text-sm text-gray-500">{mensagemVazia || 'Cadastre um novo aluno para começar.'}</p>
            </div>
        );
    }

    return (
        <div className="w-full overflow-x-auto rounded-md border">
            <Table>
                <TableHeader className="bg-gray-50">
                    <TableRow>
                        <TableHead>Nome Completo</TableHead>
                        <TableHead>Data de Nasc.</TableHead>
                        <TableHead>Turma</TableHead>
                        {mostrarEscola && <TableHead>Escola</TableHead>}
                        <TableHead>Responsável</TableHead>
                        <TableHead>Telefone</TableHead>
                        <TableHead className="text-right">Ações</TableHead>
                    </TableRow>
                </TableHeader>
                <TableBody>
                    {alunos.map((aluno) => {
                        const statusInativo = STATUS_INATIVOS[aluno.status_vinculo];
                        return (
                            <TableRow key={aluno.id}>
                                <TableCell className="font-medium">
                                    <div className="flex items-center gap-3">
                                        <AlunoAvatar aluno={aluno} />
                                        <div>
                                            <span className={statusInativo ? 'text-gray-400' : ''}>{aluno.nome_completo}</span>
                                            {statusInativo && (
                                                <Badge variant="secondary" className="ml-2 text-gray-500">{statusInativo}</Badge>
                                            )}
                                        </div>
                                    </div>
                                </TableCell>
                                <TableCell>{safeFormatDate(aluno.data_nascimento, 'dd/MM/yyyy', undefined, 'N/A')}</TableCell>
                                <TableCell>{aluno.turma_nome || 'Sem turma'}</TableCell>
                                {mostrarEscola && <TableCell>{aluno.escola_nome}</TableCell>}
                                <TableCell>{aluno.nome_responsavel || 'N/A'}</TableCell>
                                <TableCell className="whitespace-nowrap">{aluno.telefone_responsavel || 'N/A'}</TableCell>
                                <TableCell className="text-right">
                                    <div className="flex items-center justify-end gap-2">
                                        <StudentFormDialog
                                            studentData={aluno}
                                            turmas={turmas}
                                            onStudentUpdated={onStudentUpdated}
                                        >
                                            <Button variant="ghost" size="icon" title="Editar aluno" aria-label="Editar aluno">
                                                <Edit className="h-4 w-4" />
                                            </Button>
                                        </StudentFormDialog>
                                        {statusInativo ? (
                                            <Button variant="ghost" size="icon" onClick={() => handleReactivate(aluno)} title="Reativar aluno" aria-label="Reativar aluno">
                                                <RotateCcw className="h-4 w-4 text-green-600" />
                                            </Button>
                                        ) : (
                                            <AlertDialog>
                                                <AlertDialogTrigger asChild>
                                                    <Button variant="ghost" size="icon" title="Desativar aluno" aria-label="Desativar aluno">
                                                        <Trash2 className="h-4 w-4 text-red-500" />
                                                    </Button>
                                                </AlertDialogTrigger>
                                                <AlertDialogContent>
                                                    <AlertDialogHeader>
                                                        <AlertDialogTitle>Você tem certeza?</AlertDialogTitle>
                                                        <AlertDialogDescription>
                                                            Isso desativará o aluno
                                                            <span className="font-bold"> {aluno.nome_completo} </span>
                                                            e ele passará para a aba Inativos. Os registros e relatórios são mantidos, e você pode reativá-lo depois por essa aba.
                                                        </AlertDialogDescription>
                                                    </AlertDialogHeader>
                                                    <AlertDialogFooter>
                                                        <AlertDialogCancel>Cancelar</AlertDialogCancel>
                                                        <AlertDialogAction onClick={() => handleDelete(aluno)} className="bg-red-600 hover:bg-red-700">
                                                            Sim, desativar
                                                        </AlertDialogAction>
                                                    </AlertDialogFooter>
                                                </AlertDialogContent>
                                            </AlertDialog>
                                        )}
                                    </div>
                                </TableCell>
                            </TableRow>
                        );
                    })}
                </TableBody>
            </Table>
        </div>
    );
};

export default AlunosList;