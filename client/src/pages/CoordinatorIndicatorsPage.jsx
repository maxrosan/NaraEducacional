import React, { useState, useEffect, useMemo } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Helmet } from 'react-helmet-async';
import { ArrowLeft, Loader2, Target, Users, Lightbulb, TrendingUp, BarChart3, AlertTriangle, CheckCircle2, Filter, BookOpen, School, Download, FileText } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, Legend } from 'recharts';
import BnccUsageMap from '@/components/coordinator/BnccUsageMap';
import ParticipacaoDocenteCard from '@/components/indicators/ParticipacaoDocenteCard';
import { useToast } from '@/components/ui/use-toast';
import { apiClient } from '@/lib/apiClient';
import { useAuth } from '@/contexts/AuthContext';
import { campoExperienciaMap } from '@/lib/observationUtils';
import { startOfWeek, endOfWeek, subWeeks, format, parseISO, isWithinInterval } from 'date-fns';
import { ptBR } from 'date-fns/locale';
import { generateBnccCoveragePdf, generateClassReportPdf } from '@/lib/pdfGenerator';
import { apiService } from '@/services/api';
import NotificationsBell from '@/components/notifications/NotificationsBell';

const COLORS = ['#8A63D2', '#60A5FA', '#34D399', '#FBBF24', '#F87171', '#A488E1'];

// C14 - Função para determinar nível e cor baseado na porcentagem
const getNivelInfo = (percent) => {
  if (percent >= 80) return { nivel: 'Excelente', cor: 'bg-green-100 text-green-800 border-green-300', corBarra: 'bg-green-500', icon: '🟢' };
  if (percent >= 50) return { nivel: 'Atenção', cor: 'bg-yellow-100 text-yellow-800 border-yellow-300', corBarra: 'bg-yellow-500', icon: '🟡' };
  return { nivel: 'Crítico', cor: 'bg-red-100 text-red-800 border-red-300', corBarra: 'bg-red-500', icon: '🔴' };
};

// Card de Cobertura BNCC Média da Escola (C14 - com níveis e cores)
const BnccCoverageCard = ({ totalHabilidades, habilidadesUsadas, camposAtivos, totalCampos, onOpenDetails }) => {
  const coveragePercent = totalHabilidades > 0 ? Math.round((habilidadesUsadas / totalHabilidades) * 100) : 0;
  const camposPercent = totalCampos > 0 ? Math.round((camposAtivos / totalCampos) * 100) : 0;
  const nivelInfo = getNivelInfo(coveragePercent);

  return (
    <Card className="shadow-lg">
      <CardHeader>
        <CardTitle className="flex items-center justify-between gap-3">
          <span className="flex items-center gap-2">
            <Target className="h-5 w-5 text-purple-600" />
            Cobertura BNCC - Média da Escola
          </span>
          <div className="flex items-center gap-2">
            <Badge className={`${nivelInfo.cor} border`}>
              {nivelInfo.icon} {nivelInfo.nivel}
            </Badge>
            {onOpenDetails && (
              <Button variant="outline" size="sm" onClick={onOpenDetails}>
                <Download className="h-4 w-4 mr-1" />
                Ver detalhes
              </Button>
            )}
          </div>
        </CardTitle>
        <CardDescription>Proporção de habilidades da BNCC utilizadas nos registros.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <div>
          <div className="flex justify-between text-sm mb-2">
            <span className="text-gray-600">Habilidades registradas</span>
            <span className="font-bold text-purple-700">{habilidadesUsadas} de {totalHabilidades}</span>
          </div>
          <Progress value={coveragePercent} className="h-3" indicatorClassName={nivelInfo.corBarra} />
          <p className="text-xs text-gray-500 mt-1">{coveragePercent}% de cobertura</p>
        </div>
        <div>
          <div className="flex justify-between text-sm mb-2">
            <span className="text-gray-600">Campos de experiência ativos</span>
            <span className="font-bold text-green-700">{camposAtivos} de {totalCampos}</span>
          </div>
          <Progress value={camposPercent} className="h-3" indicatorClassName="bg-green-500" />
          <p className="text-xs text-gray-500 mt-1">{camposPercent}% dos campos utilizados</p>
        </div>
      </CardContent>
    </Card>
  );
};

// Card de Sugestões Automáticas
const SugestoesCard = ({ sugestoes }) => {
  if (!sugestoes || sugestoes.length === 0) {
    return (
      <Card className="shadow-lg">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Lightbulb className="h-5 w-5 text-yellow-500" />
            Sugestões Pedagógicas
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-3 text-green-600">
            <CheckCircle2 className="h-6 w-6" />
            <p>Parabéns! Não há alertas no momento. Continue o bom trabalho!</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="shadow-lg">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Lightbulb className="h-5 w-5 text-yellow-500" />
          Sugestões Pedagógicas
        </CardTitle>
        <CardDescription>Recomendações baseadas nos dados da instituição.</CardDescription>
      </CardHeader>
      <CardContent>
        <ul className="space-y-3">
          {sugestoes.map((sugestao, index) => (
            <li key={index} className="flex items-start gap-3 p-3 bg-yellow-50 rounded-lg border-l-4 border-yellow-400">
              <AlertTriangle className="h-5 w-5 text-yellow-600 flex-shrink-0 mt-0.5" />
              <div>
                <p className="font-medium text-yellow-800">{sugestao.titulo}</p>
                <p className="text-sm text-yellow-700">{sugestao.descricao}</p>
              </div>
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
};

// Card de Análise Comparativa
const AnaliseComparativaCard = ({ dadosTurmas }) => {
  if (!dadosTurmas || dadosTurmas.length === 0) {
    return (
      <Card className="shadow-lg">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <BarChart3 className="h-5 w-5 text-blue-600" />
            Análise Comparativa por Turma
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-gray-500 text-center py-8">Dados insuficientes para análise comparativa.</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="shadow-lg">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <BarChart3 className="h-5 w-5 text-blue-600" />
          Análise Comparativa por Turma
        </CardTitle>
        <CardDescription>Comparação de registros e atividades entre as turmas.</CardDescription>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={dadosTurmas} margin={{ top: 20, right: 30, left: 0, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="turma" fontSize={12} tickLine={false} />
            <YAxis allowDecimals={false} fontSize={12} tickLine={false} />
            <Tooltip
              contentStyle={{ backgroundColor: 'white', border: '1px solid #e5e7eb', borderRadius: '8px' }}
            />
            <Legend />
            <Bar dataKey="registros" name="Registros" fill="#8A63D2" radius={[4, 4, 0, 0]} />
            <Bar dataKey="relatorios" name="Relatórios" fill="#60A5FA" radius={[4, 4, 0, 0]} />
            <Bar dataKey="portfolios" name="Portfólios" fill="#34D399" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
};

// Card de Engajamento Semanal
const EngajamentoSemanalCard = ({ dadosSemanais }) => {
  if (!dadosSemanais || dadosSemanais.length === 0) {
    return null;
  }

  return (
    <Card className="shadow-lg">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <TrendingUp className="h-5 w-5 text-green-600" />
          Engajamento Docente Semanal
        </CardTitle>
        <CardDescription>Evolução de registros nas últimas 4 semanas.</CardDescription>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={250}>
          <BarChart data={dadosSemanais} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="semana" fontSize={12} tickLine={false} />
            <YAxis allowDecimals={false} fontSize={12} tickLine={false} />
            <Tooltip
              contentStyle={{ backgroundColor: 'white', border: '1px solid #e5e7eb', borderRadius: '8px' }}
            />
            <Bar dataKey="registros" name="Registros" fill="#34D399" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
};

// C13 - Cards por Turma com cobertura BNCC individual
const TurmaCard = ({ turma, onClick }) => {
  const nivelInfo = getNivelInfo(turma.cobertura);

  return (
    <Card
      className={`shadow-md border-l-4 cursor-pointer transition-all hover:shadow-lg hover:scale-[1.02] ${turma.cobertura >= 80 ? 'border-l-green-500' : turma.cobertura >= 50 ? 'border-l-yellow-500' : 'border-l-red-500'}`}
      onClick={() => onClick && onClick(turma)}
    >
      <CardContent className="p-4">
        <div className="flex items-center justify-between mb-2">
          <h4 className="font-semibold text-gray-800 truncate" title={turma.nome}>{turma.nome}</h4>
          <Badge className={`${nivelInfo.cor} border text-xs`}>
            {nivelInfo.icon} {nivelInfo.nivel}
          </Badge>
        </div>
        <div className="space-y-2">
          <div>
            <div className="flex justify-between text-xs text-gray-500 mb-1">
              <span>Cobertura BNCC</span>
              <span className="font-medium">{turma.cobertura}%</span>
            </div>
            <Progress value={turma.cobertura} className="h-2" indicatorClassName={nivelInfo.corBarra} />
          </div>
          <div className="flex justify-between text-xs text-gray-600 pt-1">
            <span>{turma.habilidadesUsadas} de {turma.totalHabilidades} habilidades</span>
            <span>{turma.registros} registros</span>
          </div>
          {turma.turno && (
            <div className="text-xs text-gray-400">
              Turno: {turma.turno}
            </div>
          )}
        </div>
        <p className="text-xs text-purple-600 mt-2 text-center font-medium">Clique para ver detalhes</p>
      </CardContent>
    </Card>
  );
};

// C13 - Container de Cards por Turma
const TurmasCardsGrid = ({ turmas, filtroNivel, filtroTurno, onTurmaClick }) => {
  const turmasFiltradas = useMemo(() => {
    return turmas.filter(turma => {
      const nivelMatch = filtroNivel === 'all' || getNivelInfo(turma.cobertura).nivel.toLowerCase() === filtroNivel.toLowerCase();
      const turnoMatch = filtroTurno === 'all' || (turma.turno && turma.turno.toLowerCase() === filtroTurno.toLowerCase());
      return nivelMatch && turnoMatch;
    });
  }, [turmas, filtroNivel, filtroTurno]);

  if (!turmas || turmas.length === 0) {
    return (
      <Card className="shadow-lg">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <School className="h-5 w-5 text-purple-600" />
            Cobertura BNCC por Turma
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-gray-500 text-center py-4">Nenhuma turma encontrada.</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="shadow-lg">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <School className="h-5 w-5 text-purple-600" />
          Cobertura BNCC por Turma
        </CardTitle>
        <CardDescription>
          {turmasFiltradas.length} turma(s) exibida(s) de {turmas.length} total — Clique em uma turma para ver o detalhamento
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {turmasFiltradas.map((turma, index) => (
            <TurmaCard key={turma.id || index} turma={turma} onClick={onTurmaClick} />
          ))}
        </div>
        {turmasFiltradas.length === 0 && (
          <p className="text-gray-500 text-center py-4">Nenhuma turma corresponde aos filtros selecionados.</p>
        )}
      </CardContent>
    </Card>
  );
};

// C22 - Desenvolvimento de Linguagem por Turma
const LanguageDevelopmentCard = ({ turmas, filtroTurno }) => {
  const turmasFiltradas = useMemo(() => {
    if (!turmas || turmas.length === 0) return [];
    return turmas.filter((turma) => {
      if (filtroTurno === 'all') return true;
      return turma.turma_turno && turma.turma_turno.toLowerCase() === filtroTurno.toLowerCase();
    });
  }, [turmas, filtroTurno]);

  return (
    <Card className="shadow-lg">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Target className="h-5 w-5 text-purple-600" />
          Desenvolvimento de Linguagem por Turma
        </CardTitle>
      </CardHeader>
      <CardContent>
        {turmasFiltradas.length === 0 ? (
          <p className="text-gray-500 text-center py-4">Nenhum dado disponível para o período.</p>
        ) : (
          <div className="space-y-4">
            {turmasFiltradas.map((turma) => (
              <div key={turma.turma_id} className="space-y-2">
                <div className="flex items-center justify-between text-sm text-gray-700">
                  <span className="font-medium">{turma.turma_nome}</span>
                  <span>{turma.percentual_final}%</span>
                </div>
                <Progress value={turma.percentual_final} className="h-2" indicatorClassName="bg-purple-500" />
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
};

const ResultadosAnaliseCard = ({ dados, filtroTurno }) => {
  const turmasFiltradas = useMemo(() => {
    if (!dados || dados.length === 0) return [];
    return dados.filter((turma) => {
      if (filtroTurno === 'all') return true;
      return turma.turmaTurno && turma.turmaTurno.toLowerCase() === filtroTurno.toLowerCase();
    });
  }, [dados, filtroTurno]);

  const renderBadges = (items, className) => {
    if (!items || items.length === 0) {
      return <span className="text-xs text-gray-400">Sem dados</span>;
    }
    return items.map((item) => (
      <Badge key={`${item.label}-${item.count}`} className={className}>
        {item.count} {item.label}
      </Badge>
    ));
  };

  return (
    <Card className="shadow-lg">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <FileText className="h-5 w-5 text-indigo-600" />
          Resultados da Análise
        </CardTitle>
        <CardDescription>
          {turmasFiltradas.length} turma(s) listada(s) com os filtros aplicados.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {turmasFiltradas.length === 0 ? (
          <p className="text-gray-500 text-center py-4">Nenhum dado encontrado para os filtros aplicados.</p>
        ) : (
          <div className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-[160px_1fr_1fr_1fr] gap-4 text-xs font-semibold text-gray-500 uppercase">
              <span>Turma</span>
              <span>Escrita</span>
              <span>Leitura</span>
              <span>Desenho</span>
            </div>
            {turmasFiltradas.map((turma) => (
              <div
                key={turma.turmaId}
                className="grid grid-cols-1 md:grid-cols-[160px_1fr_1fr_1fr] gap-4 items-start border-t pt-4"
              >
                <span className="text-sm font-medium text-gray-700">{turma.turmaNome}</span>
                <div className="flex flex-wrap gap-2">
                  {renderBadges(turma.escrita, 'bg-purple-100 text-purple-700 border border-purple-200')}
                </div>
                <div className="flex flex-wrap gap-2">
                  {renderBadges(turma.leitura, 'bg-amber-100 text-amber-700 border border-amber-200')}
                </div>
                <div className="flex flex-wrap gap-2">
                  {renderBadges(turma.desenho, 'bg-green-100 text-green-700 border border-green-200')}
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
};

const ComparativoPeriodosCard = ({ comparativo }) => {
  if (!comparativo?.periodoAtual) {
    return (
      <Card className="shadow-lg">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <BarChart3 className="h-5 w-5 text-emerald-600" />
            Comparativo entre Períodos
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-gray-500 text-center py-4">Nenhum período avaliativo configurado.</p>
        </CardContent>
      </Card>
    );
  }

  const { periodoAtual, periodoAnterior } = comparativo;

  const formatTrend = (current, previous, invert = false) => {
    const diff = current - previous;
    const adjusted = invert ? -diff : diff;
    const positive = adjusted >= 0;
    return {
      label: `${Math.abs(diff)}`,
      icon: positive ? '↑' : '↓',
      className: positive ? 'text-green-600' : 'text-red-600',
    };
  };

  const coberturaTrend = periodoAnterior
    ? formatTrend(periodoAtual.coberturaPercentual, periodoAnterior.coberturaPercentual)
    : null;
  const professoresTrend = periodoAnterior
    ? formatTrend(periodoAtual.professoresAtivos, periodoAnterior.professoresAtivos)
    : null;
  const alertasTrend = periodoAnterior
    ? formatTrend(periodoAtual.criancasEmAlerta, periodoAnterior.criancasEmAlerta, true)
    : null;

  return (
    <Card className="shadow-lg">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <BarChart3 className="h-5 w-5 text-emerald-600" />
          Comparativo entre Períodos
        </CardTitle>
        <CardDescription>
          Período atual: {periodoAtual.descricao}
        </CardDescription>
      </CardHeader>
      <CardContent>
        {!periodoAnterior && (
          <p className="text-xs text-gray-500 mb-4">
            Não há período anterior configurado para comparação.
          </p>
        )}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="rounded-lg border p-4 bg-white">
            <p className="text-xs text-gray-500">Cobertura BNCC</p>
            <p className="text-2xl font-bold text-gray-800">{periodoAtual.coberturaPercentual}%</p>
            {periodoAnterior && (
              <p className={`text-xs mt-1 ${coberturaTrend.className}`}>
                {coberturaTrend.icon} {coberturaTrend.label}% vs período anterior ({periodoAnterior.coberturaPercentual}%)
              </p>
            )}
          </div>
          <div className="rounded-lg border p-4 bg-white">
            <p className="text-xs text-gray-500">Professores Ativos</p>
            <p className="text-2xl font-bold text-gray-800">{periodoAtual.professoresAtivos}</p>
            {periodoAnterior && (
              <p className={`text-xs mt-1 ${professoresTrend.className}`}>
                {professoresTrend.icon} {professoresTrend.label} vs período anterior ({periodoAnterior.professoresAtivos})
              </p>
            )}
          </div>
          <div className="rounded-lg border p-4 bg-white">
            <p className="text-xs text-gray-500">Alerta de Crianças</p>
            <p className="text-2xl font-bold text-gray-800">{periodoAtual.criancasEmAlerta}</p>
            {periodoAnterior && (
              <p className={`text-xs mt-1 ${alertasTrend.className}`}>
                {alertasTrend.icon} {alertasTrend.label} vs período anterior ({periodoAnterior.criancasEmAlerta})
              </p>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

// C17 - Card de Habilidades BNCC Pendentes (não utilizadas)
const HabilidadesPendentesCard = ({ habilidadesPendentes }) => {
  const [expanded, setExpanded] = useState(false);

  if (!habilidadesPendentes || habilidadesPendentes.length === 0) {
    return (
      <Card className="shadow-lg border-l-4 border-l-green-500">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <BookOpen className="h-5 w-5 text-green-600" />
            Habilidades BNCC Pendentes
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-3 text-green-600">
            <CheckCircle2 className="h-6 w-6" />
            <p>Excelente! Todas as habilidades da BNCC já foram trabalhadas.</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  // Agrupar por campo de experiência
  const porCampo = habilidadesPendentes.reduce((acc, hab) => {
    const campo = hab.campo_experiencia || 'Outros';
    if (!acc[campo]) acc[campo] = [];
    acc[campo].push(hab);
    return acc;
  }, {});

  const camposOrdenados = Object.entries(porCampo).sort((a, b) => b[1].length - a[1].length);
  const habsParaMostrar = expanded ? camposOrdenados : camposOrdenados.slice(0, 3);

  return (
    <Card className="shadow-lg border-l-4 border-l-orange-500">
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <span className="flex items-center gap-2">
            <BookOpen className="h-5 w-5 text-orange-600" />
            Habilidades BNCC Pendentes
          </span>
          <Badge className="bg-orange-100 text-orange-800 border border-orange-300">
            {habilidadesPendentes.length} pendente(s)
          </Badge>
        </CardTitle>
        <CardDescription>
          Habilidades da BNCC que ainda não foram trabalhadas nos registros.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {habsParaMostrar.map(([campo, habs]) => (
          <div key={campo} className="bg-gray-50 p-3 rounded-lg">
            <h4 className="font-semibold text-gray-700 text-sm mb-2">{campo} ({habs.length})</h4>
            <ul className="space-y-1">
              {habs.slice(0, expanded ? undefined : 3).map((hab, idx) => (
                <li key={idx} className="text-xs text-gray-600 flex items-start gap-2">
                  <span className="text-orange-500">•</span>
                  <span>
                    {hab.pergunta_norma && <strong className="text-gray-700">{hab.pergunta_norma}: </strong>}
                    {hab.pergunta}
                  </span>
                </li>
              ))}
              {!expanded && habs.length > 3 && (
                <li className="text-xs text-gray-400 italic">
                  ... e mais {habs.length - 3} habilidade(s)
                </li>
              )}
            </ul>
          </div>
        ))}
        {camposOrdenados.length > 3 && (
          <Button
            variant="ghost"
            size="sm"
            className="w-full text-purple-600"
            onClick={() => setExpanded(!expanded)}
          >
            {expanded ? 'Ver menos' : `Ver todos os ${camposOrdenados.length} campos`}
          </Button>
        )}
      </CardContent>
    </Card>
  );
};

const CoverageDetailsModal = ({
  isOpen,
  onClose,
  coverageByField,
  pendingSkills,
  filters,
  onExportPdf,
}) => {
  const filterEntries = Object.entries(filters || {}).filter(([, value]) => value);
  const pendingByField = (pendingSkills || []).reduce((acc, hab) => {
    const campo = hab.campo_experiencia || 'Outros';
    if (!acc[campo]) acc[campo] = [];
    acc[campo].push(hab);
    return acc;
  }, {});

  const orderedPendingFields = Object.entries(pendingByField).sort((a, b) => b[1].length - a[1].length);

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-4xl max-h-[90vh] overflow-hidden flex flex-col">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Target className="h-5 w-5 text-purple-600" />
            Cobertura BNCC
          </DialogTitle>
          <DialogDescription>
            {filterEntries.length > 0
              ? `Filtros aplicados: ${filterEntries.map(([label, value]) => `${label}: ${value}`).join(' | ')}`
              : 'Sem filtros aplicados.'}
          </DialogDescription>
        </DialogHeader>

        <div className="flex-1 overflow-auto space-y-6 pr-2">
          <div className="space-y-3">
            <h3 className="text-sm font-semibold text-gray-700">Cobertura por Campo de Experiência</h3>
            {coverageByField && coverageByField.length > 0 ? (
              <div className="space-y-3">
                {coverageByField.map((item) => (
                  <div key={item.campo} className="space-y-2">
                    <div className="flex items-center justify-between text-sm">
                      <span className="font-medium text-gray-700">{item.campo}</span>
                      <span className="text-gray-600">{item.percent}%</span>
                    </div>
                    <div className="h-2 bg-gray-200 rounded-full">
                      <div
                        className="h-2 bg-roxo-principal rounded-full"
                        style={{ width: `${item.percent}%` }}
                      />
                    </div>
                    <p className="text-xs text-gray-500">
                      {item.usadas} de {item.total} habilidades
                    </p>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-gray-500">Sem dados de cobertura disponíveis.</p>
            )}
          </div>

          <div className="space-y-3">
            <h3 className="text-sm font-semibold text-gray-700">Habilidades Pendentes</h3>
            {orderedPendingFields.length > 0 ? (
              <div className="space-y-3">
                {orderedPendingFields.map(([campo, habs]) => (
                  <div key={campo} className="rounded-lg border border-gray-200 bg-gray-50 p-3">
                    <p className="text-sm font-semibold text-gray-700">
                      {campo} ({habs.length})
                    </p>
                    <ul className="mt-2 space-y-1 text-xs text-gray-600">
                      {habs.map((hab, idx) => (
                        <li key={`${campo}-${idx}`} className="flex items-start gap-2">
                          <span className="text-orange-500">•</span>
                          <span>
                            {hab.pergunta_norma && (
                              <strong className="text-gray-700">{hab.pergunta_norma}: </strong>
                            )}
                            {hab.pergunta}
                          </span>
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-gray-500">Nenhuma habilidade pendente encontrada.</p>
            )}
          </div>
        </div>

        <div className="flex justify-end gap-2 pt-4 border-t">
          <Button variant="outline" onClick={onClose}>
            Fechar
          </Button>
          <Button onClick={onExportPdf}>
            <Download className="h-4 w-4 mr-2" />
            Exportar PDF
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
};

// Modal de Drill-down para Turma específica
const TurmaDrilldownModal = ({ isOpen, onClose, turma, coberturaPorCampoTurma }) => {
  if (!turma) return null;

  const nivelInfo = getNivelInfo(turma.cobertura);

  // Campos de experiência padrão com cores
  const CAMPO_COLORS = {
    'O eu, o outro e o nós': '#8A63D2',
    'Escuta, fala, pensamento e imaginação': '#60A5FA',
    'Corpo, gestos e movimentos': '#34D399',
    'Traços, sons, cores e formas': '#FBBF24',
    'Espaços, tempos, quantidades, relações e transformações': '#F87171',
  };

  // Ordenar por registros (maior para menor)
  const dadosOrdenados = (coberturaPorCampoTurma || []).sort((a, b) => b.registros - a.registros);
  const totalRegistros = dadosOrdenados.reduce((sum, c) => sum + c.registros, 0);
  const maxRegistros = Math.max(...dadosOrdenados.map(c => c.registros), 1);

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-hidden flex flex-col">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <School className="h-5 w-5 text-purple-600" />
            {turma.nome} — Mapa de Utilização BNCC
          </DialogTitle>
          <DialogDescription>
            Visualização detalhada dos Campos de Experiência registrados para esta turma
          </DialogDescription>
        </DialogHeader>

        <div className="flex-1 overflow-auto space-y-6 pr-2 py-4">
          {/* Resumo da Turma */}
          <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
            <div>
              <p className="text-sm text-gray-500">Cobertura BNCC</p>
              <p className="text-3xl font-bold text-gray-800">{turma.cobertura}%</p>
              <p className="text-xs text-gray-500 mt-1">
                {turma.habilidadesUsadas} de {turma.totalHabilidades} habilidades
              </p>
            </div>
            <div className="text-right">
              <Badge className={`${nivelInfo.cor} border text-sm px-3 py-1`}>
                {nivelInfo.icon} {nivelInfo.nivel}
              </Badge>
              <p className="text-sm text-gray-500 mt-2">{turma.registros} registros totais</p>
              {turma.turno && <p className="text-xs text-gray-400">Turno: {turma.turno}</p>}
            </div>
          </div>

          {/* Mapa de Utilização por Campo */}
          <div className="space-y-4">
            <h3 className="text-sm font-semibold text-gray-700 flex items-center gap-2">
              <Target className="h-4 w-4 text-purple-600" />
              Utilização por Campo de Experiência
            </h3>

            {dadosOrdenados.length === 0 ? (
              <div className="text-center py-8 text-gray-500">
                <AlertTriangle className="h-8 w-8 mx-auto mb-2 text-yellow-500" />
                <p>Nenhum registro encontrado para esta turma.</p>
                <p className="text-xs mt-1">Incentive os professores a realizar observações.</p>
              </div>
            ) : (
              <div className="space-y-3">
                {dadosOrdenados.map((campo) => {
                  const percent = totalRegistros > 0 ? Math.round((campo.registros / totalRegistros) * 100) : 0;
                  const barWidth = maxRegistros > 0 ? Math.round((campo.registros / maxRegistros) * 100) : 0;
                  const color = CAMPO_COLORS[campo.campo] || '#A488E1';
                  const Icon = campoExperienciaMap[campo.campo]?.icon || Target;
                  const isNeglected = campo.registros === 0;

                  return (
                    <div
                      key={campo.campo}
                      className={`p-3 rounded-lg border ${isNeglected ? 'bg-red-50 border-red-200' : 'bg-white border-gray-200'}`}
                    >
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                          <Icon className="h-5 w-5" style={{ color }} />
                          <span className="font-medium text-gray-700 text-sm">
                            {campoExperienciaMap[campo.campo]?.name || campo.campo}
                          </span>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-semibold" style={{ color }}>
                            {campo.registros} {campo.registros === 1 ? 'registro' : 'registros'}
                          </span>
                          <span className="text-xs text-gray-500">({percent}%)</span>
                        </div>
                      </div>
                      <div className="h-3 bg-gray-200 rounded-full overflow-hidden">
                        <div
                          className="h-full rounded-full transition-all duration-500"
                          style={{ width: `${barWidth}%`, backgroundColor: color }}
                        />
                      </div>
                      {isNeglected && (
                        <p className="text-xs text-red-600 mt-1 flex items-center gap-1">
                          <AlertTriangle className="h-3 w-3" />
                          Campo não utilizado — requer atenção
                        </p>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Alertas de campos negligenciados */}
          {dadosOrdenados.filter(c => c.registros === 0).length > 0 && (
            <div className="p-4 bg-yellow-50 border-l-4 border-yellow-400 rounded-r-lg">
              <h4 className="font-bold text-yellow-800 flex items-center gap-2 text-sm">
                <AlertTriangle className="h-5 w-5" />
                Campos de Experiência Negligenciados
              </h4>
              <ul className="list-disc list-inside text-xs text-yellow-700 mt-2 space-y-1">
                {dadosOrdenados.filter(c => c.registros === 0).map(c => (
                  <li key={c.campo}>{campoExperienciaMap[c.campo]?.name || c.campo}</li>
                ))}
              </ul>
              <p className="text-xs text-yellow-600 mt-2">
                Considere incentivar observações nestes campos para uma cobertura mais completa da BNCC.
              </p>
            </div>
          )}
        </div>

        <div className="flex justify-end gap-2 pt-4 border-t">
          <Button variant="outline" onClick={onClose}>
            Fechar
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
};

// C15 - Componente de Filtros
const FiltrosIndicadores = ({ filtroNivel, setFiltroNivel, filtroTurno, setFiltroTurno, turnos }) => {
  return (
    <Card className="shadow-md mb-6">
      <CardContent className="p-4">
        <div className="flex flex-wrap items-center gap-4">
          <div className="flex items-center gap-2">
            <Filter className="h-4 w-4 text-gray-500" />
            <span className="text-sm font-medium text-gray-600">Filtros:</span>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-sm text-gray-500">Nível:</span>
            <Select value={filtroNivel} onValueChange={setFiltroNivel}>
              <SelectTrigger className="w-[140px] h-9">
                <SelectValue placeholder="Todos" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Todos</SelectItem>
                <SelectItem value="crítico">🔴 Crítico</SelectItem>
                <SelectItem value="atenção">🟡 Atenção</SelectItem>
                <SelectItem value="excelente">🟢 Excelente</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-sm text-gray-500">Turno:</span>
            <Select value={filtroTurno} onValueChange={setFiltroTurno}>
              <SelectTrigger className="w-[140px] h-9">
                <SelectValue placeholder="Todos" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Todos</SelectItem>
                {turnos.map(turno => (
                  <SelectItem key={turno} value={turno.toLowerCase()}>{turno}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {(filtroNivel !== 'all' || filtroTurno !== 'all') && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => { setFiltroNivel('all'); setFiltroTurno('all'); }}
              className="text-gray-500 hover:text-gray-700"
            >
              Limpar filtros
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
};

const CoordinatorIndicatorsPage = ({ dashboardData: dataFromProps }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const { user } = useAuth();
  const { toast } = useToast();
  const dashboardData = dataFromProps || location.state?.dashboardData;

  const [loading, setLoading] = useState(true);
  // C15 - Estados para filtros
  const [filtroNivel, setFiltroNivel] = useState('all');
  const [filtroTurno, setFiltroTurno] = useState('all');

  const [indicatorData, setIndicatorData] = useState({
    bnccCoverage: { totalHabilidades: 0, habilidadesUsadas: 0, camposAtivos: 0, totalCampos: 6 },
    sugestoes: [],
    dadosTurmas: [],
    dadosSemanais: [],
    coberturaPorCampo: [],
    // C13 - Dados detalhados por turma
    turmasDetalhadas: [],
    // C17 - Habilidades pendentes
    habilidadesPendentes: [],
    // C15 - Lista de turnos disponíveis
    turnos: [],
    // C22 - Desenvolvimento de Linguagem
    linguagemPorTurma: [],
    // Resultados da análise por turma
    analisesPorTurma: [],
    // Comparativo entre períodos
    comparativoPeriodos: null,
    // Cobertura por campo para cada turma (drill-down)
    coberturaPorCampoPorTurma: {},
  });
  const [isCoverageModalOpen, setIsCoverageModalOpen] = useState(false);
  // Estados para modal de drill-down da turma
  const [isDrilldownModalOpen, setIsDrilldownModalOpen] = useState(false);
  const [selectedTurma, setSelectedTurma] = useState(null);

  useEffect(() => {
    const fetchIndicatorData = async () => {
      if (!user?.user_metadata?.instituicao_id && !user?.instituicao_id) {
        setLoading(false);
        return;
      }

      const instituicaoId = user.user_metadata?.instituicao_id || user.instituicao_id;

      try {
        // Buscar dados por turma
        const { data: turmas } = await apiClient
          .from('turmas')
          .select('id, nome, turno')
          .eq('instituicao_id', instituicaoId);

        const turmaIds = (turmas || []).map(turma => turma.id);

        // C15 - Extrair turnos únicos
        const turnosSet = new Set();
        (turmas || []).forEach(t => {
          if (t.turno) turnosSet.add(t.turno);
        });
        const turnos = Array.from(turnosSet).sort();

        // Buscar crianças para mapear registros por turma
        const { data: criancas } = await apiClient
          .from('criancas')
          .select('id, turma_id')
          .eq('instituicao_id', instituicaoId);

        const criancaIds = (criancas || []).map(crianca => crianca.id);
        const criancaTurmaMap = new Map((criancas || []).map(crianca => [crianca.id, crianca.turma_id]));

        // Buscar registros de observação por instituição (evita URL longa com crianca_id__in)
        let registrosObservacao = [];
        if (criancaIds.length > 0) {
          const { data: registrosData } = await apiClient
            .from('registros_observacao')
            .select('id, pergunta_id, tipo_pergunta, crianca_id, data_observacao')
            .eq('instituicao_id', instituicaoId);
          registrosObservacao = registrosData || [];
        }

        // Buscar todas as habilidades BNCC
        const { data: todasHabilidades } = await apiClient
          .from('perguntas_bncc')
          .select('id, pergunta, pergunta_norma, campo_experiencia');

        const totalHabilidades = (todasHabilidades || []).length;
        let analisesPorTurma = [];
        try {
          const [escritaResponse, desenhoResponse] = await Promise.all([
            apiService.listarRegistrosEscrita(),
            apiService.listarRegistrosDesenho(),
          ]);
          const registrosEscrita = escritaResponse?.registros || [];
          const registrosDesenho = desenhoResponse?.registros || [];

          const analisesMap = new Map(
            (turmas || []).map((turma) => [
              String(turma.id),
              {
                turmaId: String(turma.id),
                turmaNome: turma.nome,
                turmaTurno: turma.turno || null,
                escrita: new Map(),
                leitura: new Map(),
                desenho: new Map(),
              },
            ])
          );

          const registrarContagem = (mapa, chave) => {
            if (!chave) return;
            mapa.set(chave, (mapa.get(chave) || 0) + 1);
          };

          registrosEscrita.forEach((registro) => {
            const turmaId = String(registro.turma_id || '');
            const etapa = registro.etapa_ia?.trim();
            const turmaAnalise = analisesMap.get(turmaId);
            if (!turmaAnalise || !etapa) return;
            registrarContagem(turmaAnalise.escrita, etapa);
          });

          registrosDesenho.forEach((registro) => {
            const turmaId = String(registro.turma_id || '');
            const fase = registro.fase_desenho?.trim();
            const turmaAnalise = analisesMap.get(turmaId);
            if (!turmaAnalise || !fase) return;
            registrarContagem(turmaAnalise.desenho, fase);
          });

          const mapToList = (mapa) =>
            Array.from(mapa.entries())
              .map(([label, count]) => ({ label, count }))
              .sort((a, b) => b.count - a.count);

          analisesPorTurma = Array.from(analisesMap.values()).map((item) => ({
            ...item,
            escrita: mapToList(item.escrita),
            leitura: mapToList(item.leitura),
            desenho: mapToList(item.desenho),
          }));
        } catch (error) {
          console.warn('Falha ao carregar análises de escrita e desenho:', error);
        }

        const isBnccRegistro = (registro) => {
          if (registro?.tipo_pergunta) {
            return registro.tipo_pergunta === 'bncc';
          }
          return Boolean(registro?.pergunta_id);
        };

        const habilidadesUsadasIds = new Set(
          (registrosObservacao || [])
            .filter(isBnccRegistro)
            .map(registro => registro.pergunta_id)
            .filter(Boolean)
        );
        const habilidadesUsadas = habilidadesUsadasIds.size;

        const camposAtivos = new Set(
          (todasHabilidades || [])
            .filter(habilidade => habilidadesUsadasIds.has(habilidade.id))
            .map(habilidade => habilidade.campo_experiencia || 'Outros')
        ).size;

        // C17 - Identificar habilidades pendentes (não usadas em nenhum registro)
        const habilidadesPendentes = (todasHabilidades || []).filter(h => !habilidadesUsadasIds.has(h.id));

        // C18 - Cobertura por campo de experiência
        const habilidadesPorId = new Map(
          (todasHabilidades || []).map(hab => [hab.id, hab.campo_experiencia || 'Outros'])
        );
        const totalPorCampo = (todasHabilidades || []).reduce((acc, hab) => {
          const campo = hab.campo_experiencia || 'Outros';
          acc[campo] = (acc[campo] || 0) + 1;
          return acc;
        }, {});
        const usadasPorCampo = {};
        habilidadesUsadasIds.forEach((habId) => {
          const campo = habilidadesPorId.get(habId) || 'Outros';
          usadasPorCampo[campo] = (usadasPorCampo[campo] || 0) + 1;
        });
        const coberturaPorCampo = Object.entries(totalPorCampo).map(([campo, total]) => {
          const usadas = usadasPorCampo[campo] || 0;
          const percent = total > 0 ? Math.round((usadas / total) * 100) : 0;
          return { campo, usadas, total, percent };
        }).sort((a, b) => b.percent - a.percent);

        const registrosPorTurma = new Map();
        const habilidadesPorTurma = new Map();
        // Mapa de cobertura por campo para cada turma (drill-down)
        const coberturaPorCampoPorTurma = {};

        // Criar mapa de pergunta_id para campo_experiencia
        const perguntaCampoMap = new Map(
          (todasHabilidades || []).map(h => [h.id, h.campo_experiencia || 'Outros'])
        );

        (registrosObservacao || []).forEach((registro) => {
          const turmaId = criancaTurmaMap.get(registro.crianca_id);
          if (!turmaId) {
            return;
          }

          registrosPorTurma.set(turmaId, (registrosPorTurma.get(turmaId) || 0) + 1);

          if (isBnccRegistro(registro) && registro.pergunta_id) {
            if (!habilidadesPorTurma.has(turmaId)) {
              habilidadesPorTurma.set(turmaId, new Set());
            }
            habilidadesPorTurma.get(turmaId).add(registro.pergunta_id);

            // Contar registros por campo de experiência para cada turma
            const campo = perguntaCampoMap.get(registro.pergunta_id) || 'Outros';
            if (!coberturaPorCampoPorTurma[turmaId]) {
              coberturaPorCampoPorTurma[turmaId] = {};
            }
            coberturaPorCampoPorTurma[turmaId][campo] = (coberturaPorCampoPorTurma[turmaId][campo] || 0) + 1;
          }
        });

        const { data: relatoriosData } = await apiClient
          .from('relatorios')
          .select('id')
          .eq('instituicao_id', instituicaoId);

        const relatoriosPorTurma = Math.round((relatoriosData?.length || 0) / (turmas?.length || 1));

        let producoesPortfolio = [];
        if (turmaIds.length > 0) {
          const { data: producoesData } = await apiClient
            .from('portfolios')
            .select('id, turma_id')
            .in('turma_id', turmaIds);
          producoesPortfolio = producoesData || [];
        }

        const portfoliosPorTurma = new Map();
        (producoesPortfolio || []).forEach((producao) => {
          if (!producao.turma_id) {
            return;
          }
          portfoliosPorTurma.set(producao.turma_id, (portfoliosPorTurma.get(producao.turma_id) || 0) + 1);
        });

        const dadosTurmas = [];
        const turmasDetalhadas = [];

        for (const turma of (turmas || [])) {
          const registros = registrosPorTurma.get(turma.id) || 0;
          const habilidadesUsadasTurma = habilidadesPorTurma.get(turma.id)?.size || 0;
          const coberturaTurma = totalHabilidades > 0
            ? Math.round((habilidadesUsadasTurma / totalHabilidades) * 100)
            : 0;

          dadosTurmas.push({
            turma: turma.nome.length > 15 ? turma.nome.substring(0, 15) + '...' : turma.nome,
            registros: registros || 0,
            relatorios: relatoriosPorTurma,
            portfolios: portfoliosPorTurma.get(turma.id) || 0,
          });

          // C13 - Dados detalhados para cards individuais
          turmasDetalhadas.push({
            id: turma.id,
            nome: turma.nome,
            turno: turma.turno || null,
            registros: registros,
            habilidadesUsadas: habilidadesUsadasTurma,
            totalHabilidades: totalHabilidades || 0,
            cobertura: coberturaTurma,
          });
        }

        // Buscar dados semanais (últimas 4 semanas)
        const now = new Date();
        const dadosSemanais = [];
        for (let i = 3; i >= 0; i--) {
          const weekStart = startOfWeek(subWeeks(now, i), { weekStartsOn: 1 });
          const weekEnd = endOfWeek(subWeeks(now, i), { weekStartsOn: 1 });
          const count = (registrosObservacao || []).filter((registro) => {
            if (!registro.data_observacao) {
              return false;
            }
            const registroDate = parseISO(registro.data_observacao);
            return registroDate >= weekStart && registroDate <= weekEnd;
          }).length;

          dadosSemanais.push({
            semana: `Semana ${format(weekStart, 'dd/MM', { locale: ptBR })}`,
            registros: count || 0,
          });
        }

        // Gerar sugestões automáticas
        const sugestoes = [];

        const coveragePercent = totalHabilidades > 0 ? (habilidadesUsadas / totalHabilidades) * 100 : 0;
        if (coveragePercent < 30) {
          sugestoes.push({
            titulo: 'Ampliar cobertura BNCC',
            descricao: `Apenas ${coveragePercent.toFixed(0)}% das habilidades estão sendo registradas. Incentive os professores a explorar mais campos de experiência.`,
          });
        }

        if (camposAtivos < 4) {
          sugestoes.push({
            titulo: 'Diversificar campos de experiência',
            descricao: `Apenas ${camposAtivos} de 6 campos estão sendo trabalhados. Sugira atividades que contemplem os campos menos utilizados.`,
          });
        }

        const ultimaSemana = dadosSemanais[dadosSemanais.length - 1]?.registros || 0;
        const semanaAnterior = dadosSemanais[dadosSemanais.length - 2]?.registros || 0;
        if (ultimaSemana < semanaAnterior * 0.5 && semanaAnterior > 0) {
          sugestoes.push({
            titulo: 'Queda no engajamento',
            descricao: `Os registros caíram ${Math.round((1 - ultimaSemana/semanaAnterior) * 100)}% esta semana. Verifique se há obstáculos ou necessidade de apoio à equipe.`,
          });
        }

        const turmasSemRegistro = dadosTurmas.filter(t => t.registros === 0);
        if (turmasSemRegistro.length > 0) {
          sugestoes.push({
            titulo: 'Turmas sem registros',
            descricao: `${turmasSemRegistro.length} turma(s) não possuem registros. Acompanhe de perto: ${turmasSemRegistro.map(t => t.turma).join(', ')}.`,
          });
        }

        let linguagemPorTurma = [];
        try {
          const linguagemData = await apiService.listarIndicadorLinguagem(instituicaoId);
          linguagemPorTurma = linguagemData?.turmas || [];
        } catch (error) {
          console.warn('Falha ao carregar indicador de linguagem:', error);
        }

        let comparativoPeriodos = null;
        try {
          const { data: periodosRaw } = await apiClient
            .from('periodos_avaliativos')
            .select('id, descricao, tipo_periodo, data_inicio, data_fim')
            .eq('instituicao_id', instituicaoId)
            .order('data_inicio', { ascending: true });

          let periodosList = periodosRaw || [];

          const periodosOrdenados = [...periodosList].sort(
            (a, b) => new Date(a.data_inicio) - new Date(b.data_inicio)
          );
          const hoje = new Date();
          const periodoAtual =
            periodosOrdenados.find((periodo) =>
              isWithinInterval(hoje, {
                start: parseISO(periodo.data_inicio),
                end: parseISO(periodo.data_fim),
              })
            ) || periodosOrdenados[periodosOrdenados.length - 1];

          const periodoAnterior = periodoAtual
            ? periodosOrdenados
                .filter((periodo) => new Date(periodo.data_fim) < new Date(periodoAtual.data_inicio))
                .slice(-1)[0]
            : null;

          const calcularResumoPeriodo = (periodo) => {
            if (!periodo) return null;
            const inicio = parseISO(periodo.data_inicio);
            const fim = parseISO(periodo.data_fim);
            const registrosPeriodo = (registrosObservacao || []).filter((registro) => {
              if (!registro?.data_observacao) return false;
              const registroDate = parseISO(registro.data_observacao);
              return registroDate >= inicio && registroDate <= fim;
            });

            const habilidadesPeriodo = new Set(
              registrosPeriodo
                .filter(isBnccRegistro)
                .map((registro) => registro.pergunta_id)
                .filter(Boolean)
            );

            const professoresAtivos = new Set(
              registrosPeriodo.map((registro) => registro.professor_id).filter(Boolean)
            ).size;

            const criancasComRegistro = new Set(
              registrosPeriodo.map((registro) => registro.crianca_id).filter(Boolean)
            ).size;

            return {
              id: periodo.id,
              descricao: periodo.descricao,
              data_inicio: periodo.data_inicio,
              data_fim: periodo.data_fim,
              coberturaPercentual: totalHabilidades > 0
                ? Math.round((habilidadesPeriodo.size / totalHabilidades) * 100)
                : 0,
              professoresAtivos,
              criancasEmAlerta: Math.max(0, (criancas || []).length - criancasComRegistro),
            };
          };

          if (periodoAtual) {
            comparativoPeriodos = {
              periodoAtual: calcularResumoPeriodo(periodoAtual),
              periodoAnterior: calcularResumoPeriodo(periodoAnterior),
            };
          }
        } catch (error) {
          console.warn('Falha ao montar comparativo entre períodos:', error);
        }

        setIndicatorData({
          bnccCoverage: {
            totalHabilidades: totalHabilidades || 0,
            habilidadesUsadas,
            camposAtivos,
            totalCampos: 6
          },
          sugestoes,
          dadosTurmas,
          dadosSemanais,
          coberturaPorCampo,
          // C13 - Dados detalhados por turma
          turmasDetalhadas,
          // C17 - Habilidades pendentes
          habilidadesPendentes,
          // C15 - Lista de turnos
          turnos,
          // C22 - Desenvolvimento de linguagem
          linguagemPorTurma,
          analisesPorTurma,
          comparativoPeriodos,
          // Cobertura por campo para cada turma (drill-down)
          coberturaPorCampoPorTurma,
        });

      } catch (error) {
        console.error('Erro ao buscar dados de indicadores:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchIndicatorData();
  }, [user]);

  const formatFilterLabel = (value) => {
    if (!value || value === 'all') return 'Todos';
    return value.charAt(0).toUpperCase() + value.slice(1);
  };

  const appliedFilters = {
    Nível: formatFilterLabel(filtroNivel),
    Turno: formatFilterLabel(filtroTurno),
  };

  // Handler para abrir o drill-down da turma
  const handleTurmaClick = (turma) => {
    setSelectedTurma(turma);
    setIsDrilldownModalOpen(true);
  };

  // Preparar dados de cobertura por campo para a turma selecionada
  const coberturaPorCampoTurmaSelecionada = useMemo(() => {
    if (!selectedTurma || !indicatorData.coberturaPorCampoPorTurma) return [];

    const turmaId = selectedTurma.id;
    const dadosTurma = indicatorData.coberturaPorCampoPorTurma[turmaId] || {};

    // Campos padrão da BNCC
    const camposPadrao = Object.keys(campoExperienciaMap);

    // Incluir todos os campos padrão, mesmo que não tenham registros
    return camposPadrao.map(campo => ({
      campo,
      registros: dadosTurma[campo] || 0,
    }));
  }, [selectedTurma, indicatorData.coberturaPorCampoPorTurma]);

  const handleExportCoveragePdf = async () => {
    try {
      toast({
        title: 'Gerando PDF de cobertura...',
        description: 'O arquivo será baixado em instantes.',
      });
      await generateBnccCoveragePdf({
        coverageByField: indicatorData.coberturaPorCampo,
        pendingSkills: indicatorData.habilidadesPendentes,
        filters: appliedFilters,
      });
    } catch (error) {
      toast({
        variant: 'destructive',
        title: 'Erro ao gerar PDF',
        description: 'Não foi possível exportar a cobertura BNCC.',
      });
    }
  };

  const handleExportClassReportPdf = async () => {
    try {
      const turmasFiltradas = indicatorData.turmasDetalhadas.filter((turma) => {
        const nivelMatch = filtroNivel === 'all'
          || getNivelInfo(turma.cobertura).nivel.toLowerCase() === filtroNivel.toLowerCase();
        const turnoMatch = filtroTurno === 'all'
          || (turma.turno && turma.turno.toLowerCase() === filtroTurno.toLowerCase());
        return nivelMatch && turnoMatch;
      });
      const turmasFiltradasIds = new Set(turmasFiltradas.map((turma) => turma.id));
      const linguagemFiltrada = indicatorData.linguagemPorTurma.filter((turma) => turmasFiltradasIds.has(turma.turma_id));

      toast({
        title: 'Gerando relatório da turma...',
        description: 'O arquivo será baixado em instantes.',
      });
      await generateClassReportPdf({
        coverageByField: indicatorData.coberturaPorCampo,
        pendingSkills: indicatorData.habilidadesPendentes,
        filters: appliedFilters,
        bnccCoverage: indicatorData.bnccCoverage,
        sugestoes: indicatorData.sugestoes,
        dadosSemanais: indicatorData.dadosSemanais,
        turmas: turmasFiltradas,
        languageDevelopment: linguagemFiltrada,
      });
    } catch (error) {
      toast({
        variant: 'destructive',
        title: 'Erro ao gerar relatório',
        description: 'Não foi possível gerar o relatório da turma.',
      });
    }
  };

  return (
    <>
      <Helmet>
        <title>NARA - Indicadores da Coordenação</title>
        <meta name="description" content="Página de indicadores para a coordenação pedagógica." />
      </Helmet>

      <div className="bg-[#F5F3FA] min-h-screen">
        <header className="bg-white/80 backdrop-blur-sm shadow-sm sticky top-0 z-10">
          <div className="container mx-auto px-4 sm:px-6 lg:px-8 py-4 flex items-center justify-between">
            <div className="flex items-center">
              <Button variant="ghost" size="icon" onClick={() => navigate('/coordenacao')}>
                <ArrowLeft className="h-6 w-6" />
              </Button>
              <h1 className="text-xl font-bold text-gray-800 ml-4">Indicadores Pedagógicos</h1>
            </div>
            <NotificationsBell />
          </div>
        </header>

        <main className="container mx-auto px-4 sm:px-6 lg:px-8 py-8">
          {loading ? (
            <div className="flex justify-center items-center h-64">
              <Loader2 className="h-8 w-8 animate-spin text-purple-500" />
              <p className="ml-4 text-gray-600">Carregando indicadores...</p>
            </div>
          ) : (
            <div className="space-y-6">
              <div className="flex flex-wrap justify-end gap-3">
                <Button variant="outline" onClick={handleExportClassReportPdf}>
                  <FileText className="h-4 w-4 mr-2" />
                  Relatório da Turma
                </Button>
              </div>

              {/* C15 - Filtros por nível e turno */}
              <FiltrosIndicadores
                filtroNivel={filtroNivel}
                setFiltroNivel={setFiltroNivel}
                filtroTurno={filtroTurno}
                setFiltroTurno={setFiltroTurno}
                turnos={indicatorData.turnos}
              />

              {/* Primeira linha: Cobertura BNCC e Sugestões */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <BnccCoverageCard
                  {...indicatorData.bnccCoverage}
                  onOpenDetails={() => setIsCoverageModalOpen(true)}
                />
                <SugestoesCard sugestoes={indicatorData.sugestoes} />
              </div>

              {/* C13 - Cards por Turma com cobertura BNCC */}
              <TurmasCardsGrid
                turmas={indicatorData.turmasDetalhadas}
                filtroNivel={filtroNivel}
                filtroTurno={filtroTurno}
                onTurmaClick={handleTurmaClick}
              />

              <LanguageDevelopmentCard
                turmas={indicatorData.linguagemPorTurma}
                filtroTurno={filtroTurno}
              />

              <ResultadosAnaliseCard
                dados={indicatorData.analisesPorTurma}
                filtroTurno={filtroTurno}
              />

              {/* Segunda linha: Mapa BNCC */}
              {dashboardData?.bnccUsageData && dashboardData.bnccUsageData.length > 0 && (
                <BnccUsageMap data={dashboardData.bnccUsageData} />
              )}

              {/* C17 - Habilidades BNCC Pendentes */}
              <HabilidadesPendentesCard habilidadesPendentes={indicatorData.habilidadesPendentes} />

              {/* Terceira linha: Engajamento Semanal e Participação Docente */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <EngajamentoSemanalCard dadosSemanais={indicatorData.dadosSemanais} />
                <ParticipacaoDocenteCard />
              </div>

              <ComparativoPeriodosCard comparativo={indicatorData.comparativoPeriodos} />

              {/* Quarta linha: Análise Comparativa */}
              <AnaliseComparativaCard dadosTurmas={indicatorData.dadosTurmas} />
            </div>
          )}
        </main>

        <CoverageDetailsModal
          isOpen={isCoverageModalOpen}
          onClose={() => setIsCoverageModalOpen(false)}
          coverageByField={indicatorData.coberturaPorCampo}
          pendingSkills={indicatorData.habilidadesPendentes}
          filters={appliedFilters}
          onExportPdf={handleExportCoveragePdf}
        />

        {/* Modal de Drill-down para Turma específica */}
        <TurmaDrilldownModal
          isOpen={isDrilldownModalOpen}
          onClose={() => {
            setIsDrilldownModalOpen(false);
            setSelectedTurma(null);
          }}
          turma={selectedTurma}
          coberturaPorCampoTurma={coberturaPorCampoTurmaSelecionada}
        />
      </div>
    </>
  );
};

export default CoordinatorIndicatorsPage;
