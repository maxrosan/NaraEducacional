import React from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from '@/components/ui/button';
import { Bell, CalendarX } from 'lucide-react';

const MissingPlanningCard = ({ turmas, planejamentos, professores, onNotifyClick }) => {
  const turmasComPlanejamento = new Set(planejamentos.map(p => p.turma_id));
  const turmasSemPlanejamento = turmas.filter(t => !turmasComPlanejamento.has(t.id));

  const getProfessorDaTurma = (turmaId) => {
    // This is a simplification. A better approach would be to have a direct link
    // between turma and professor in the fetched data.
    const vinculo = professores.find(p => p.turmas?.some(t => t === turmas.find(tu => tu.id === turmaId)?.nome));
    return vinculo;
  };

  if (turmasSemPlanejamento.length === 0) {
    return null; // Don't render the card if there are no missing plannings
  }

  return (
    <Card className="shadow-lg border-l-4 border-yellow-400">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <CalendarX className="h-5 w-5 text-yellow-600" />
          Turmas com Planejamento Ausente
        </CardTitle>
        <CardDescription>Estas turmas ainda não enviaram o planejamento para a semana atual.</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          {turmasSemPlanejamento.map(turma => {
            const professor = getProfessorDaTurma(turma.id);
            return (
              <div key={turma.id} className="flex items-center justify-between bg-yellow-50 p-2 rounded-lg">
                <div>
                  <p className="font-semibold text-sm text-yellow-800">{turma.nome}</p>
                  <p className="text-xs text-yellow-600">{professor ? professor.nome : 'Professor não encontrado'}</p>
                </div>
                <Button 
                  variant="outline" 
                  size="sm" 
                  className="bg-white text-yellow-700 border-yellow-300 hover:bg-yellow-100"
                  onClick={() => professor && onNotifyClick(professor.nome, 'planejamento')}
                  disabled={!professor}
                >
                  <Bell className="h-3 w-3 mr-1.5" />
                  Notificar
                </Button>
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
};

export default MissingPlanningCard;