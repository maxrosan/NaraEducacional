import React from 'react';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from '@/components/ui/badge';
import { format } from 'date-fns';
import { ptBR } from 'date-fns/locale';
import { safeFormatDate } from '@/lib/dateUtils';

const ProfessoresTab = ({ professores, loading }) => {
  if (loading) {
    return <p>Carregando professores...</p>;
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Nome</TableHead>
          <TableHead>Email</TableHead>
          <TableHead>Turmas</TableHead>
          <TableHead>Último Acesso</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {professores.length > 0 ? professores.map(prof => (
          <TableRow key={prof.id}>
            <TableCell>{prof.nome}</TableCell>
            <TableCell>{prof.email}</TableCell>
            <TableCell>
              <div className="flex flex-wrap gap-1">
                {prof.turmas && prof.turmas.length > 0 ? prof.turmas.map((turma, index) => (
                  <Badge key={index} variant="secondary">{turma}</Badge>
                )) : <span className="text-xs text-gray-500">Nenhuma</span>}
              </div>
            </TableCell>
            <TableCell>
              {safeFormatDate(prof.ultimo_acesso, "dd/MM/yyyy 'às' HH:mm", { locale: ptBR }, 'Nunca')}
            </TableCell>
          </TableRow>
        )) : (
          <TableRow><TableCell colSpan={4} className="text-center">Nenhum professor encontrado.</TableCell></TableRow>
        )}
      </TableBody>
    </Table>
  );
};

export default ProfessoresTab;