import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Calendar, ChevronDown, ChevronRight, Clock, Book } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Badge } from '@/components/ui/badge';
import { useToast } from '@/components/ui/use-toast';
import { apiService } from '@/services/api';
import { getSemesterDateRange, safeFormatDate } from '@/lib/dateUtils';
import { format, parseISO } from 'date-fns';
import { ptBR } from 'date-fns/locale';

const DailyPlanModal = ({ isOpen, onClose, dailyPlan }) => {
  if (!dailyPlan) return null;

  const getDayName = (dayCode) => {
    const dayNames = {
      'segunda': 'Segunda-feira',
      'terca': 'Terça-feira',
      'quarta': 'Quarta-feira',
      'quinta': 'Quinta-feira',
      'sexta': 'Sexta-feira'
    };
    return dayNames[dayCode] || dayCode;
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-4xl max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Calendar className="h-5 w-5" />
            {getDayName(dailyPlan.dia_semana)}
          </DialogTitle>
        </DialogHeader>
        
        <div className="space-y-6">
          {/* Atividades Propostas */}
          {dailyPlan.atividades_propostas && (
            <div>
              <h4 className="font-semibold flex items-center gap-2 mb-2">
                <Book className="h-4 w-4" />
                Atividades Propostas
              </h4>
              <p className="text-gray-700 bg-gray-50 p-3 rounded-md whitespace-pre-wrap">
                {dailyPlan.atividades_propostas}
              </p>
            </div>
          )}

          {/* Habilidades BNCC */}
          {dailyPlan.habilidades && dailyPlan.habilidades.length > 0 && (
            <div>
              <h4 className="font-semibold mb-3">Habilidades da BNCC</h4>
              <div className="space-y-2">
                {dailyPlan.habilidades.map((habilidade) => (
                  <div key={habilidade.id} className="border rounded-md p-3">
                    <Badge variant="secondary" className="mb-2">
                      {habilidade.codigo}
                    </Badge>
                    <p className="text-sm text-gray-700">
                      {habilidade.descricao}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
};

function WeeklyPlanningsBlock({ turmaId, periodo }) {
  const [plannings, setPlannings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [expandedPlannings, setExpandedPlannings] = useState(new Set());
  const [selectedDailyPlan, setSelectedDailyPlan] = useState(null);
  const [modalOpen, setModalOpen] = useState(false);
  const { toast } = useToast();

  useEffect(() => {
    const fetchPlannings = async () => {
      if (!turmaId) return;
      
      setLoading(true);
      try {
        // Usar período selecionado ou fallback para semestre
        const inicio = periodo?.data_inicio || getSemesterDateRange().inicio;
        const fim = periodo?.data_fim || getSemesterDateRange().fim;
        const response = await apiService.listarPlanejamentosTurma(
          turmaId,
          inicio,
          fim
        );
        
        setPlannings(response.planejamentos || []);
      } catch (error) {
        console.error('Erro ao carregar planejamentos:', error);
        toast({
          variant: 'destructive',
          title: 'Erro ao carregar planejamentos',
          description: 'Não foi possível carregar os planejamentos da turma.'
        });
      } finally {
        setLoading(false);
      }
    };

    fetchPlannings();
  }, [turmaId, periodo, toast]);

  const togglePlanningExpansion = (planningId) => {
    const newExpanded = new Set(expandedPlannings);
    if (newExpanded.has(planningId)) {
      newExpanded.delete(planningId);
    } else {
      newExpanded.add(planningId);
    }
    setExpandedPlannings(newExpanded);
  };

  const openDailyPlanModal = (dailyPlan) => {
    setSelectedDailyPlan(dailyPlan);
    setModalOpen(true);
  };

  const getDayName = (dayCode) => {
    const dayNames = {
      'segunda': 'Segunda',
      'terca': 'Terça',
      'quarta': 'Quarta',
      'quinta': 'Quinta',
      'sexta': 'Sexta'
    };
    return dayNames[dayCode] || dayCode;
  };

  if (loading) {
    return (
      <Card className="bg-white">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Book className="h-5 w-5 text-roxo-principal" />
            O que vivemos juntos neste bimestre
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-roxo-principal"></div>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <>
      <Card className="bg-white">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Book className="h-5 w-5 text-roxo-principal" />
            O que vivemos juntos neste bimestre
          </CardTitle>
        </CardHeader>
        <CardContent>
          {plannings.length === 0 ? (
            <p className="text-gray-500 text-center py-8">
              Nenhum planejamento encontrado para este período.
            </p>
          ) : (
            <div className="space-y-4">
              {plannings.map((planning) => (
                <motion.div
                  key={planning.id}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="border border-gray-200 rounded-lg overflow-hidden"
                >
                  <div
                    className="p-4 cursor-pointer hover:bg-gray-50 transition-colors"
                    onClick={() => togglePlanningExpansion(planning.id)}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        {expandedPlannings.has(planning.id) ? (
                          <ChevronDown className="h-5 w-5 text-gray-500" />
                        ) : (
                          <ChevronRight className="h-5 w-5 text-gray-500" />
                        )}
                        <div>
                          <h3 className="font-medium">
                            Semana de {safeFormatDate(planning.semana_inicio, 'dd/MM', { locale: ptBR })} a{' '}
                            {safeFormatDate(planning.semana_fim, 'dd/MM/yyyy', { locale: ptBR })}
                          </h3>
                          <p className="text-sm text-gray-500 flex items-center gap-1">
                            <Clock className="h-3 w-3" />
                            {planning.dias.length} dias planejados
                          </p>
                        </div>
                      </div>
                    </div>
                  </div>

                  <AnimatePresence>
                    {expandedPlannings.has(planning.id) && (
                      <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: 'auto', opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        transition={{ duration: 0.2 }}
                        className="border-t bg-gray-50"
                      >
                        <div className="p-4">
                          <div className="grid grid-cols-1 md:grid-cols-5 gap-2">
                            {['segunda', 'terca', 'quarta', 'quinta', 'sexta'].map(dayKey => {
                              const dailyPlan = planning.dias.find(dia => dia.dia_semana === dayKey);
                              if (!dailyPlan) return null;
                              
                              return (
                                <button
                                  key={dailyPlan.id}
                                  onClick={() => openDailyPlanModal(dailyPlan)}
                                  className="p-3 bg-white rounded-md border border-gray-200 hover:border-roxo-principal hover:bg-roxo-claro/10 transition-colors text-left"
                                >
                                  <div className="font-medium text-sm mb-1">
                                    {getDayName(dailyPlan.dia_semana)}
                                  </div>
                                  <div className="text-xs text-gray-500">
                                    {dailyPlan.habilidades.length} habilidades
                                  </div>
                                  {dailyPlan.atividades_propostas && (
                                    <div className="text-xs text-gray-600 mt-1 overflow-hidden" style={{
                                      display: '-webkit-box',
                                      WebkitLineClamp: 2,
                                      WebkitBoxOrient: 'vertical',
                                      textOverflow: 'ellipsis'
                                    }}>
                                      {dailyPlan.atividades_propostas.substring(0, 50)}...
                                    </div>
                                  )}
                                </button>
                              );
                            })}
                          </div>
                        </div>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </motion.div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <DailyPlanModal
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        dailyPlan={selectedDailyPlan}
      />
    </>
  );
}

export default WeeklyPlanningsBlock;
