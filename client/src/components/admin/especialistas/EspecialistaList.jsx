import React from 'react';
import { Edit, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

const EspecialistaList = ({ loading, especialistas, onEdit, onDelete }) => {
    if (loading) return <p>Carregando especialistas...</p>;

    return (
        <Table>
            <TableHeader>
                <TableRow>
                    <TableHead>Nome</TableHead>
                    <TableHead>Email</TableHead>
                    <TableHead>Tipo</TableHead>
                    <TableHead>Ativo</TableHead>
                    <TableHead className="text-right">Ações</TableHead>
                </TableRow>
            </TableHeader>
            <TableBody>
                {especialistas.length > 0 ? especialistas.map(user => (
                    <TableRow key={user.id}>
                        <TableCell>{user.nome}</TableCell>
                        <TableCell>{user.email}</TableCell>
                        <TableCell>{user.tipo_especialista}</TableCell>
                        <TableCell>{user.ativo ? 'Sim' : 'Não'}</TableCell>
                        <TableCell className="text-right space-x-2">
                            <Button variant="ghost" size="icon" onClick={() => onEdit(user)}><Edit className="h-4 w-4" /></Button>
                            <Button variant="ghost" size="icon" onClick={() => onDelete(user)}><Trash2 className="h-4 w-4 text-red-500" /></Button>
                        </TableCell>
                    </TableRow>
                )) : (
                    <TableRow><TableCell colSpan={5} className="text-center">Nenhum especialista cadastrado.</TableCell></TableRow>
                )}
            </TableBody>
        </Table>
    );
};

export default EspecialistaList;