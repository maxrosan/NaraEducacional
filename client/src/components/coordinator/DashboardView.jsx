import React from 'react';
import { motion } from 'framer-motion';
import { BarChart, Users, FileText, CalendarCheck, UserX, MessageSquare, Loader2 } from 'lucide-react';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Button } from '@/components/ui/button';

const StatCard = ({ title, value, icon, description, color, delay, onFeedbackClick }) => (
  <motion.div
    initial={{ opacity: 0, y: 20 }}
    animate={{ opacity: 1, y: 0 }}
    transition={{ duration: 0.5, delay }}
  >
    <Card className="shadow-lg border-l-4" style={{ borderLeftColor: color }}>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium">{title}</CardTitle>
        {icon}
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold">{value}</div>
        <p className="text-xs text-muted-foreground">{description}</p>
        {onFeedbackClick && (
          <Button variant="link" size="sm" className="p-0 h-auto mt-2 text-xs" onClick={onFeedbackClick}>
            <MessageSquare className="h-3 w-3 mr-1" />
            Enviar devolutiva
          </Button>
        )}
      </CardContent>
    </Card>
  </motion.div>
);

const ReportStatus = ({ delay, progress, finished, pending }) => (
    <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay }}
    >
        <Card className="shadow-lg">
            <CardHeader>
                <CardTitle>Conclusão dos Relatórios do Bimestre</CardTitle>
                <CardDescription>{finished} de {finished + pending} relatórios foram concluídos.</CardDescription>
            </CardHeader>
            <CardContent>
                <Progress value={progress} className="w-full" indicatorClassName="bg-green-500" />
                 <div className="mt-4 flex justify-between text-sm text-muted-foreground">
                    <span>Concluídos: {finished}</span>
                    <span>Em aberto: {pending}</span>
                </div>
            </CardContent>
        </Card>
    </motion.div>
);


const DashboardView = ({ data, onFeedbackClick }) => {
  if (!data) {
    return (
      <div className="flex justify-center items-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-purple-500" />
      </div>
    );
  }

  const stats = [
    { title: 'Observações na Semana', value: data.weeklyObservations, icon: <BarChart className="h-4 w-4 text-muted-foreground" />, description: 'Registros da equipe', color: '#34D399' },
    { title: 'Planejamentos Finalizados', value: data.planningsFinished, icon: <CalendarCheck className="h-4 w-4 text-muted-foreground" />, description: 'Nesta semana', color: '#60A5FA' },
    { title: 'Crianças que Precisam de Atenção', value: data.studentsWithoutRecords, icon: <Users className="h-4 w-4 text-muted-foreground" />, description: 'Sem registros nos últimos 15 dias', color: '#F87171', onFeedbackClick: () => onFeedbackClick('Professores', 'registro') },
  ];

  return (
    <div className="p-2 sm:p-4 space-y-6">
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {stats.map((stat, index) => (
          <StatCard key={stat.title} {...stat} delay={0.1 * index} onFeedbackClick={stat.onFeedbackClick} />
        ))}
      </div>
      <div className="grid gap-4 md:grid-cols-1">
        <motion.div className="lg:col-span-1" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, delay: 0.5 }}>
          <ReportStatus 
            progress={data.reportProgress}
            finished={data.reportsFinished}
            pending={data.reportsPending}
          />
        </motion.div>
      </div>
    </div>
  );
};

export default DashboardView;
