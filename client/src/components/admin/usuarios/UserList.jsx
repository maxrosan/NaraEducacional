import React from 'react';
import { Edit, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

const profileLabels = {
    admin: 'Administrador',
    coordenador: 'Coordenador',
    professor: 'Professor',
    professor_infantil: 'Professor Educação Infantil',
    professor_fundamental: 'Professor Ensino Fundamental',
    professor_especialista: 'Professor Especialista',
    especialista: 'Especialista',
};

const UserList = ({ loading, usuarios, onEdit, onDelete }) => {
    if (loading) {
        return <p>Carregando usuários...</p>;
    }

    return (
        <Table>
            <TableHeader>
                <TableRow>
                    <TableHead>Nome</TableHead>
                    <TableHead>Email</TableHead>
                    <TableHead>Perfil</TableHead>
                    <TableHead>Tipo/Especialidade</TableHead>
                    <TableHead>Ativo</TableHead>
                    <TableHead className="text-right">Ações</TableHead>
                </TableRow>
            </TableHeader>
            <TableBody>
                {usuarios.length > 0 ? usuarios.map(user => (
                    <TableRow key={user.id}>
                        <TableCell>{user.nome}</TableCell>
                        <TableCell>{user.email}</TableCell>
                        <TableCell>{profileLabels[user.perfil] || user.perfil}</TableCell>
                        <TableCell>{user.tipo_especialista || 'N/A'}</TableCell>
                        <TableCell>{user.ativo ? 'Sim' : 'Não'}</TableCell>
                        <TableCell className="text-right space-x-2">
                            <Button variant="ghost" size="icon" onClick={() => onEdit(user)}>
                                <Edit className="h-4 w-4" />
                            </Button>
                            <Button variant="ghost" size="icon" onClick={() => onDelete(user)}>
                                <Trash2 className="h-4 w-4 text-red-500" />
                            </Button>
                        </TableCell>
                    </TableRow>
                )) : (
                    <TableRow><TableCell colSpan={6} className="text-center">Nenhum usuário cadastrado.</TableCell></TableRow>
                )}
            </TableBody>
        </Table>
    );
};

export default UserList;
