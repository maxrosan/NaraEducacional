import React from 'react';
import { Edit, Power, RotateCcw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";

/**
 * Tabela de disciplinas de uma página. O status já é dado pela aba em que a
 * lista aparece, por isso não há coluna de status.
 */
const DisciplinaList = ({ disciplinas, variasEscolas, mensagemVazia, onEdit, onDesativar, onReativar }) => {
    const colunas = variasEscolas ? 4 : 3;

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
                        {variasEscolas && <TableHead>Escola</TableHead>}
                        <TableHead>Professores</TableHead>
                        <TableHead className="text-right">Ações</TableHead>
                    </TableRow>
                </TableHeader>
                <TableBody>
                    {disciplinas.length > 0 ? disciplinas.map((d) => {
                        const nomes = (d.professores ?? []).map((v) => v.usuario_nome);
                        return (
                            <TableRow key={d.id} className={d.ativo ? undefined : 'opacity-60'}>
                                <TableCell className="font-medium">{d.nome}</TableCell>
                                {variasEscolas && <TableCell>{d.escola_nome}</TableCell>}
                                <TableCell>
                                    {nomes.length
                                        ? nomes.join(', ')
                                        : <span className="text-amber-600">Nenhum vinculado</span>}
                                </TableCell>
                                <TableCell className="text-right space-x-2 whitespace-nowrap">
                                    {acao('Editar disciplina', () => onEdit(d), <Edit className="h-4 w-4" />)}
                                    {d.ativo
                                        ? acao('Desativar disciplina', () => onDesativar(d), <Power className="h-4 w-4 text-red-500" />)
                                        : acao('Reativar disciplina', () => onReativar(d), <RotateCcw className="h-4 w-4 text-green-600" />)}
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

export default DisciplinaList;