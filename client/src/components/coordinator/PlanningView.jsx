import React, { useState, useMemo } from 'react';
import { motion } from 'framer-motion';
import { CalendarDays, Filter, Download, Loader2, UserX } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/accordion';
import { useToast } from '@/components/ui/use-toast';
import { format, parseISO, startOfWeek, endOfWeek } from 'date-fns';
import { ptBR } from 'date-fns/locale';
import { generatePlanningPdf } from '@/lib/pdfGenerator';

const PlanningDetail = ({ day, content }) => {
  if (!content) return null;

  const fields = [
    { label: 'Atividades Propostas', value: content.atividades_propostas },
  ];

  return (
    <div className="py-2 px-4 bg-gray-50 rounded-lg mb-2">
      <h4 className="font-bold text-gray-700">{day}</h4>
      <div className="mt-2 space-y-2 text-sm">
        {fields.map(field => field.value && (
          <div key={field.label}>
            <p className="font-semibold text-gray-600">{field.label}:</p>
            <p className="text-gray-800 whitespace-pre-wrap">{field.value}</p>
          </div>
        ))}
      </div>
    </div>
  );
};

const PlanningView = ({ data, turmas, professores }) => {
  const { toast } = useToast();
  const [filters, setFilters] = useState({ turma: 'all', professor: 'all', semana: 'all' });
  const [expandedItem, setExpandedItem] = useState(null);

  const handleFilterChange = (type, value) => {
    setFilters(prev => ({ ...prev, [type]: value }));
  };

  const getWeekOptions = useMemo(() => {
    if (!data) return [];
    const weekStarts = [...new Set(data.map(p => format(startOfWeek(parseISO(p.semana_referencia), { weekStartsOn: 1 }), 'yyyy-MM-dd')))];
    return weekStarts.map(weekStart => {
      const start = parseISO(weekStart);
      const end = endOfWeek(start, { weekStartsOn: 1 });
      return {
        value: weekStart,
        label: `${format(start, 'dd/MM')} a ${format(end, 'dd/MM/yyyy')}`
      };
    });
  }, [data]);

  const filteredData = useMemo(() => {
    if (!data) return [];
    return data.filter(p => {
      const turmaMatch = filters.turma === 'all' || p.turma_id === filters.turma;
      const professorMatch = filters.professor === 'all' || p.id_professor === filters.professor;
      const semanaMatch = filters.semana === 'all' || format(startOfWeek(parseISO(p.semana_referencia), { weekStartsOn: 1 }), 'yyyy-MM-dd') === filters.semana;
      return turmaMatch && professorMatch && semanaMatch;
    });
  }, [data, filters]);

  const missingProfessors = useMemo(() => {
    if (!professores || !data) return [];
    const semanaKey = filters.semana;
    const dataToCheck = semanaKey === 'all' ? data : data.filter(p =>
      format(startOfWeek(parseISO(p.semana_referencia), { weekStartsOn: 1 }), 'yyyy-MM-dd') === semanaKey
    );
    const professoresComPlanejamento = new Set(dataToCheck.map(p => String(p.id_professor || p.professora_id)));
    const seenIds = new Set();
    const seenNames = new Set();
    return professores.filter(p => {
      const id = String(p.id);
      const name = (p.nome || '').trim().toLowerCase();
      if (seenIds.has(id) || seenNames.has(name) || professoresComPlanejamento.has(id)) return false;
      seenIds.add(id);
      seenNames.add(name);
      return true;
    });
  }, [data, professores, filters.semana]);

  const handleExportPDF = async (planning) => {
    toast({ title: 'Gerando PDF...', description: 'Aguarde um momento.' });
    try {
        const dailyPlans = (planning.dias || []).map(dayPlan => ({
            day: dayPlan.dia_semana || dayPlan.dia,
            atividades_propostas: dayPlan.atividades_propostas || '',
            skills: (dayPlan.habilidades || []).map(h => ({ codigo: h.codigo, descricao: h.descricao || '' })),
        }));

        const reportData = {
            turmaName: planning.turmas?.nome || 'N/A',
            weekPeriod: `${format(startOfWeek(parseISO(planning.semana_referencia), { weekStartsOn: 1 }), 'dd/MM/yyyy', { locale: ptBR })} a ${format(endOfWeek(parseISO(planning.semana_referencia), { weekStartsOn: 1 }), 'dd/MM/yyyy', { locale: ptBR })}`,
            dailyPlans
        };
        await generatePlanningPdf(reportData);
    } catch (error) {
        console.error("Error generating PDF:", error);
        toast({ variant: 'destructive', title: 'Erro ao gerar PDF', description: 'Não foi possível exportar o planejamento.' });
    }
  };

  if (!data || !turmas || !professores) {
    return (
      <div className="flex justify-center items-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-purple-500" />
      </div>
    );
  }

  const weekDays = [
    { key: 'segunda', label: 'Segunda-feira', abbr: 'S' },
    { key: 'terca', label: 'Terça-feira', abbr: 'T' },
    { key: 'quarta', label: 'Quarta-feira', abbr: 'Q' },
    { key: 'quinta', label: 'Quinta-feira', abbr: 'Q' },
    { key: 'sexta', label: 'Sexta-feira', abbr: 'S' },
  ];

  return (
    <Card className="bg-white/50">
      <CardHeader>
        <CardTitle className="flex items-center gap-3 text-xl">
          <CalendarDays className="h-6 w-6 text-blue-500" />
          Acompanhamento de Planejamentos
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex flex-col sm:flex-row gap-4 mb-6">
          <Select value={filters.turma} onValueChange={(value) => handleFilterChange('turma', value)}>
            <SelectTrigger className="w-full sm:w-[200px]">
              <Filter className="h-4 w-4 mr-2 text-gray-400" />
              <SelectValue placeholder="Filtrar por Turma" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Todas as Turmas</SelectItem>
              {turmas.map(t => <SelectItem key={t.id} value={t.id}>{t.nome}</SelectItem>)}
            </SelectContent>
          </Select>
          <Select value={filters.professor} onValueChange={(value) => handleFilterChange('professor', value)}>
            <SelectTrigger className="w-full sm:w-[200px]">
              <Filter className="h-4 w-4 mr-2 text-gray-400" />
              <SelectValue placeholder="Filtrar por Professor" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Todos os Professores</SelectItem>
              {professores.map(p => <SelectItem key={p.id} value={p.id}>{p.nome}</SelectItem>)}
            </SelectContent>
          </Select>
          <Select value={filters.semana} onValueChange={(value) => handleFilterChange('semana', value)}>
            <SelectTrigger className="w-full sm:w-[200px]">
              <Filter className="h-4 w-4 mr-2 text-gray-400" />
              <SelectValue placeholder="Filtrar por Semana" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Todas as Semanas</SelectItem>
              {getWeekOptions.map(w => <SelectItem key={w.value} value={w.value}>{w.label}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>

        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
          {missingProfessors.length > 0 && (
            <div className="mb-6">
              <h3 className="text-sm font-semibold text-red-600 flex items-center gap-2 mb-2">
                <UserX className="h-4 w-4" /> Professoras sem planejamento enviado
              </h3>
              <div className="flex flex-wrap gap-2">
                {missingProfessors.map(p => (
                  <span key={p.id} className="px-3 py-1 rounded-full text-xs font-medium bg-red-100 text-red-700">
                    {p.nome}
                  </span>
                ))}
              </div>
            </div>
          )}
          {filteredData.length > 0 ? (
            <Accordion type="single" collapsible className="w-full" value={expandedItem} onValueChange={setExpandedItem}>
              {filteredData.map(planning => (
                <AccordionItem value={planning.id} key={planning.id} className="border-b-0 mb-2">
                  <Card className="overflow-hidden">
                    <AccordionTrigger className="p-4 hover:no-underline hover:bg-gray-50/80">
                      <div className="flex justify-between items-center w-full">
                        <div className="text-left">
                          <div className="flex items-center gap-2">
                            <p className="font-bold text-base text-gray-800">{planning.turmas?.nome || 'Turma não encontrada'}</p>
                            <div className="flex gap-1">
                              {weekDays.map(day => {
                                const has = planning.dias?.some(d => d.dia_semana === day.key);
                                return (
                                  <span key={day.key} className={`text-xs font-bold ${has ? 'text-green-600' : 'text-red-500'}`}>
                                    {day.abbr}
                                  </span>
                                );
                              })}
                            </div>
                          </div>
                          <p className="text-sm text-gray-600">{planning.usuarios?.nome || 'Professor não encontrado'}</p>
                        </div>
                        <div className="flex items-center gap-4">
                          <span className={`px-2 py-1 rounded-full text-xs font-semibold ${planning.status === 'Finalizado' ? 'bg-green-100 text-green-800' : 'bg-yellow-100 text-yellow-800'}`}>
                            {planning.status}
                          </span>
                          <div
                            role="button"
                            tabIndex={0}
                            className="p-1 rounded hover:bg-gray-100 cursor-pointer"
                            onClick={(e) => { e.stopPropagation(); handleExportPDF(planning); }}
                            onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.stopPropagation(); handleExportPDF(planning); } }}
                          >
                            <Download className="h-4 w-4" />
                          </div>
                        </div>
                      </div>
                    </AccordionTrigger>
                    <AccordionContent className="p-4 bg-white">
                      {weekDays.map(day => (
                        <PlanningDetail key={day.key} day={day.label} content={planning.dias?.find(d => d.dia_semana === day.key)} />
                      ))}
                    </AccordionContent>
                  </Card>
                </AccordionItem>
              ))}
            </Accordion>
          ) : (
            <p className="text-center text-gray-500 py-8">Nenhum planejamento encontrado com os filtros selecionados.</p>
          )}
        </motion.div>
      </CardContent>
    </Card>
  );
};

export default PlanningView;