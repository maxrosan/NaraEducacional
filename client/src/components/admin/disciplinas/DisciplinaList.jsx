import React from 'react';
import { Edit, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

const DisciplinaList = ({ loading, disciplinas, onEdit, onDelete }) => {
    if (loading) {
        return <p>Carregando disciplinas...</p>;
    }

    return (
        <Table>
            <TableHeader>
                <TableRow>
                    <TableHead>Nome</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead className="text-right">Ações</TableHead>
                </TableRow>
            </TableHeader>
            <TableBody>
                {disciplinas.length > 0 ? disciplinas.map(disciplina => (
                    <TableRow key={disciplina.id}>
                        <TableCell>{disciplina.nome}</TableCell>
                        <TableCell>
                            <Badge variant={disciplina.ativo ? 'default' : 'secondary'}>
                                {disciplina.ativo ? 'Ativa' : 'Inativa'}
                            </Badge>
                        </TableCell>
                        <TableCell className="text-right space-x-2">
                            <Button variant="ghost" size="icon" onClick={() => onEdit(disciplina)}>
                                <Edit className="h-4 w-4" />
                            </Button>
                            <Button variant="ghost" size="icon" onClick={() => onDelete(disciplina)}>
                                <Trash2 className="h-4 w-4 text-red-500" />
                            </Button>
                        </TableCell>
                    </TableRow>
                )) : (
                    <TableRow><TableCell colSpan={3} className="text-center">Nenhuma disciplina cadastrada.</TableCell></TableRow>
                )}
            </TableBody>
        </Table>
    );
};

export default DisciplinaList;