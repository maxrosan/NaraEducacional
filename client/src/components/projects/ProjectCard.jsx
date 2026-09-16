import React from 'react';
import { format } from 'date-fns';
import { safeFormatDate } from '@/lib/dateUtils';
import { Card, CardContent, CardHeader, CardTitle, CardDescription, CardFooter } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { MoreHorizontal, Edit, Trash2, CheckCircle, Calendar, Target } from 'lucide-react';

const ProjectCard = ({ project, onEdit, onDelete, onFinish }) => {
  const statusColor = project.status === 'Finalizado' ? 'bg-green-100 text-green-800' : 'bg-blue-100 text-blue-800';
  return (
    <Card className="flex flex-col">
      <CardHeader>
        <div className="flex justify-between items-start">
          <CardTitle className="text-lg">{project.nome_projeto}</CardTitle>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon"><MoreHorizontal className="h-4 w-4" /></Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={() => onEdit(project)}><Edit className="mr-2 h-4 w-4" /> Editar</DropdownMenuItem>
              {project.status !== 'Finalizado' && <DropdownMenuItem onClick={() => onFinish(project.id)}><CheckCircle className="mr-2 h-4 w-4" /> Finalizar</DropdownMenuItem>}
              <DropdownMenuItem onClick={() => onDelete(project.id)} className="text-red-600 focus:text-red-600 focus:bg-red-50"><Trash2 className="mr-2 h-4 w-4" /> Excluir</DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
        <CardDescription>
          <Badge variant="outline" className={statusColor}>{project.status}</Badge>
        </CardDescription>
      </CardHeader>
      <CardContent className="flex-grow space-y-2">
        <p className="text-sm text-gray-600 flex items-center gap-2"><Calendar className="h-4 w-4" /> {safeFormatDate(project.data_inicio, 'dd/MM/yy')} a {safeFormatDate(project.data_fim, 'dd/MM/yy')}</p>
        <p className="text-sm text-gray-600 flex items-start gap-2"><Target className="h-4 w-4 mt-1 flex-shrink-0" /> {project.objetivo_pedagogico?.substring(0, 80) || 'Sem objetivo definido'}...</p>
        <div className="flex flex-wrap gap-1 pt-2">
          {project.areas_envolvidas?.map(area => <Badge key={area} variant="secondary">{area}</Badge>)}
        </div>
      </CardContent>
      <CardFooter>
        <p className="text-xs text-gray-500">Registros vinculados: 0</p>
      </CardFooter>
    </Card>
  );
};

export default ProjectCard;