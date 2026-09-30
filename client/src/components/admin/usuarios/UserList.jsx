import React from 'react';
import { Edit, Power, RotateCcw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";

export const NIVEL_LABELS = {
    superadmin: 'Super Administrador',
    admin: 'Administrador',
    coordenador: 'Coordenador',
    professor_infantil: 'Professor Educação Infantil',
    professor_fundamental: 'Professor Ensino Fundamental',
    professor_especialista: 'Professor Especialista',
    especialista: 'Especialista',
    vendedor: 'Vendedor',
    suporte: 'Suporte',
};

export const TIPO_ESPECIALISTA_LABELS = {
    psicopedagogo: 'Psicopedagogo',
    psicologo: 'Psicólogo',
    fonoaudiologo: 'Fonoaudiólogo',
    terapeuta_ocupacional: 'Terapeuta Ocupacional',
    outro: 'Outro',
};

function resumoVinculos(u) {
    const partes = [];
    if (u.tipo_especialista) partes.push(TIPO_ESPECIALISTA_LABELS[u.tipo_especialista] || u.tipo_especialista);
    if (u.turmas?.length) partes.push(u.turmas.map((t) => t.turma_nome).join(', '));
    if (u.disciplinas?.length) partes.push(u.disciplinas.map((d) => d.disciplina_nome).join(', '));
    return partes.join(' · ');
}

/**
 * Tabela de usuários de uma página. O status já é dado pela aba (Ativos/
 * Inativos). O próprio usuário logado não recebe a ação de desativar.
 */
const UserList = ({ usuarios, variasEscolas, usuarioAtual, mensagemVazia, onEdit, onDesativar, onReativar }) => {
    const colunas = variasEscolas ? 6 : 5;

    const acao = (rotulo, onClick, icone) => (
        <Tooltip>
            <TooltipTrigger asChild>
                <Button variant="ghost" size="icon" onClick={onClick} aria-label={rotulo}>{icone}</Button>
            </TooltipTrigger>
            <TooltipContent><p>{rotulo}</p></TooltipContent>
        </Tooltip>
    );

    return (
        <TooltipProvider>
            <Table>
                <TableHeader>
                    <TableRow>
                        <TableHead>Nome</TableHead>
                        <TableHead>Email</TableHead>
                        <TableHead>Perfil</TableHead>
                        {variasEscolas && <TableHead>Escola</TableHead>}
                        <TableHead>Turmas / Disciplinas / Especialidade</TableHead>
                        <TableHead className="text-right">Ações</TableHead>
                    </TableRow>
                </TableHeader>
                <TableBody>
                    {usuarios.length > 0 ? usuarios.map((u) => {
                        const eu = String(u.id) === String(usuarioAtual);
                        const vinculos = resumoVinculos(u);
                        return (
                            <TableRow key={u.id} className={u.is_active ? undefined : 'opacity-60'}>
                                <TableCell className="font-medium">
                                    {u.nome}{eu && <span className="ml-2 text-xs text-gray-400">(você)</span>}
                                </TableCell>
                                <TableCell>{u.email}</TableCell>
                                <TableCell>{NIVEL_LABELS[u.nivel] || u.nivel}</TableCell>
                                {variasEscolas && <TableCell>{u.escola_nome || '—'}</TableCell>}
                                <TableCell className="max-w-xs truncate" title={vinculos}>{vinculos || '—'}</TableCell>
                                <TableCell className="text-right space-x-2 whitespace-nowrap">
                                    {acao('Editar usuário', () => onEdit(u), <Edit className="h-4 w-4" />)}
                                    {!eu && (u.is_active
                                        ? acao('Desativar usuário', () => onDesativar(u), <Power className="h-4 w-4 text-red-500" />)
                                        : acao('Reativar usuário', () => onReativar(u), <RotateCcw className="h-4 w-4 text-green-600" />))}
                                </TableCell>
                            </TableRow>
                        );
                    }) : (
                        <TableRow>
                            <TableCell colSpan={colunas} className="text-center text-gray-500">{mensagemVazia}</TableCell>
                        </TableRow>
                    )}
                </TableBody>
            </Table>
        </TooltipProvider>
    );
};

export default UserList;