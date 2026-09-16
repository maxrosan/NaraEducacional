import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { BookOpen, MessageCircle, ChevronDown, ChevronRight, Calendar, Eye } from 'lucide-react';
import { format } from 'date-fns';
import { ptBR } from 'date-fns/locale';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import EmptyContent from '@/components/reports/EmptyContent';
import { listarObservacoes, listarPerguntasBncc } from '@/services/api';
import { fetchPeriodosAvaliativos, findPeriodoForDate, safeFormatDate } from '@/lib/dateUtils';

const SkillsMatrixBlock = ({ criancaId, turmaId, instituicaoId, selectedPeriodo, readOnly = false }) => {
  console.log('SkillsMatrixBlock Props recebidas:', { criancaId, turmaId, instituicaoId });
  
  const [bimestresDisponiveis, setBimestresDisponiveis] = useState([]);
  const [loading, setLoading] = useState(true);
  const [modalData, setModalData] = useState(null);
  const [loadingModal, setLoadingModal] = useState(false);
  const [expandedSkills, setExpandedSkills] = useState(new Set());
  const [debugInfo, setDebugInfo] = useState({});

  // Função para determinar o status baseado na frequência
  const getStatusFromFrequency = (frequency) => {
    if (frequency >= 3) return { status: 'green', label: 'Desenvolvido', icon: '🟢' };
    if (frequency === 2) return { status: 'yellow', label: 'Em desenvolvimento', icon: '🟡' };
    if (frequency === 1) return { status: 'orange', label: 'Às vezes', icon: '🟠' };
    return { status: 'default', label: 'Não observado', icon: '⚪️' };
  };

  // Buscar períodos disponíveis
  useEffect(() => {
    const fetchPeriodosDisponiveis = async () => {
      if (!criancaId || !turmaId || !instituicaoId) {
        setLoading(false);
        return;
      }

      try {
        setLoading(true);

        // Buscar períodos avaliativos da instituição
        const periodos = await fetchPeriodosAvaliativos(instituicaoId);

        // Buscar todos os registros da criança
        const registros = await listarObservacoes({ crianca_id: criancaId, turma_id: turmaId });
        const registrosFiltrados = (registros || []).filter((registro) => {
          const resposta = (registro.resposta || '').toString().toLowerCase();
          return resposta === 'sim';
        });

        // Agrupar por período avaliativo
        const periodosInfo = {};

        registrosFiltrados.forEach(registro => {
          const periodo = findPeriodoForDate(registro.data_observacao, periodos);
          if (!periodo) return;

          const key = periodo.id;
          if (!periodosInfo[key]) {
            periodosInfo[key] = {
              id: periodo.id,
              descricao: periodo.descricao,
              data_inicio: periodo.data_inicio,
              data_fim: periodo.data_fim,
              count: 0,
              dates: []
            };
          }
          periodosInfo[key].count++;
          periodosInfo[key].dates.push(registro.data_observacao);
        });

        const periodosArray = Object.values(periodosInfo)
          .sort((a, b) => a.data_inicio.localeCompare(b.data_inicio))
          .map(p => ({
            id: p.id,
            label: p.descricao,
            data_inicio: p.data_inicio,
            data_fim: p.data_fim,
            totalObservacoes: p.count,
            ultimaObservacao: p.dates.sort().pop()
          }));

        setBimestresDisponiveis(periodosArray);
        setDebugInfo({
          totalRegistros: registrosFiltrados.length,
          bimestresEncontrados: periodosArray.length
        });

      } catch (error) {
        console.error('Erro ao buscar períodos:', error);
        setDebugInfo({ error: error.message });
      } finally {
        setLoading(false);
      }
    };

    fetchPeriodosDisponiveis();
  }, [criancaId, turmaId, instituicaoId]);

  // Função para carregar dados detalhados de um período
  const loadPeriodoDetails = async (periodo) => {
    try {
      setLoadingModal(true);

      // Buscar registros do período específico
      const registros = await listarObservacoes({ crianca_id: criancaId, turma_id: turmaId });
      const registrosValidos = (registros || []).filter((registro) => {
        const resposta = (registro.resposta || '').toString().toLowerCase();
        return resposta === 'sim';
      });

      // Filtrar pelo intervalo de datas do período
      const registrosBimestre = registrosValidos.filter(registro => {
        const data = registro.data_observacao?.split('T')[0];
        return data >= periodo.data_inicio && data <= periodo.data_fim;
      });

      // Buscar perguntas BNCC
      const perguntasIds = [...new Set(registrosBimestre.map(r => r.pergunta_id))];
      
      if (perguntasIds.length === 0) {
        setModalData({
          periodo: periodo.label,
          campos: [],
          totalObservacoes: 0
        });
        return;
      }

      const perguntas = await listarPerguntasBncc({ ids: perguntasIds });

      // Criar mapa de perguntas
      const perguntasMap = {};
      perguntas?.forEach(p => {
        perguntasMap[p.id] = p;
      });

      // Agrupar por campo de experiência
      const camposMap = {};
      
      registrosBimestre.forEach(registro => {
        const pergunta = perguntasMap[registro.pergunta_id];
        if (!pergunta) return;

        const campo = pergunta.campo_experiencia;
        const perguntaId = registro.pergunta_id;
        
        if (!camposMap[campo]) {
          camposMap[campo] = {
            nome: campo,
            perguntas: {},
            totalObservacoes: 0
          };
        }

        if (!camposMap[campo].perguntas[perguntaId]) {
          camposMap[campo].perguntas[perguntaId] = {
            pergunta: pergunta.pergunta,
            habilidade_bncc: pergunta.habilidade_bncc,
            frequencia: 0,
            comentarios: []
          };
        }

        camposMap[campo].perguntas[perguntaId].frequencia++;
        camposMap[campo].totalObservacoes++;
        
        if (registro.observacao && registro.observacao.trim()) {
          camposMap[campo].perguntas[perguntaId].comentarios.push({
            comentario: registro.observacao,
            data: registro.data_observacao
          });
        }
      });

      // Converter para array e adicionar status
      const camposArray = Object.values(camposMap).map(campo => {
        const perguntasArray = Object.values(campo.perguntas).map(pergunta => ({
          ...pergunta,
          ...getStatusFromFrequency(pergunta.frequencia)
        }));

        return {
          ...campo,
          perguntas: perguntasArray.sort((a, b) => a.pergunta.localeCompare(b.pergunta))
        };
      }).sort((a, b) => a.nome.localeCompare(b.nome));

      setModalData({
        periodo: periodo.label,
        campos: camposArray,
        totalObservacoes: registrosBimestre.length
      });

    } catch (error) {
      console.error('Erro ao carregar detalhes do período:', error);
    } finally {
      setLoadingModal(false);
    }
  };

  const toggleSkillExpansion = (skillId) => {
    setExpandedSkills(prev => {
      const newSet = new Set(prev);
      if (newSet.has(skillId)) {
        newSet.delete(skillId);
      } else {
        newSet.add(skillId);
      }
      return newSet;
    });
  };
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.5 }}
      className="bg-white p-6 rounded-2xl shadow-md border border-gray-100"
    >
      <div className="flex items-center gap-3 mb-4">
        <div className="bg-lavanda-claro p-2 rounded-full">
          <BookOpen className="h-5 w-5 text-roxo-principal" />
        </div>
        <h3 className="text-lg font-bold text-texto-escuro">
          Acompanhamento por Habilidades da BNCC
        </h3>
      </div>

      {/* Debug Info (temporário) — oculto na visão somente-leitura da coordenação */}
      {!readOnly && debugInfo && Object.keys(debugInfo).length > 0 && (
        <div className="mb-4 p-3 bg-yellow-50 border border-yellow-200 rounded-lg text-xs">
          <h4 className="font-semibold text-yellow-800 mb-2">Debug Info:</h4>
          <div className="space-y-1 text-yellow-700">
            <p>Total de registros: {debugInfo.totalRegistros}</p>
            <p>Bimestres encontrados: {debugInfo.bimestresEncontrados}</p>
            {debugInfo.error && <p className="text-red-600">Erro: {debugInfo.error}</p>}
          </div>
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center py-8">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-roxo-principal"></div>
          <span className="ml-2 text-gray-600">Carregando dados...</span>
        </div>
      ) : bimestresDisponiveis.length === 0 ? (
        <EmptyContent message="Nenhuma observação BNCC encontrada para esta criança." />
      ) : (
        <div>
          <div className="mb-4 p-3 bg-blue-50 rounded-lg">
            <h4 className="font-semibold text-sm text-blue-800 mb-2">Legenda de Status:</h4>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-2 text-xs">
              <div className="flex items-center gap-1">
                <span>🟢</span> <span>Desenvolvido (3+ obs.)</span>
              </div>
              <div className="flex items-center gap-1">
                <span>🟡</span> <span>Em desenvolvimento (2 obs.)</span>
              </div>
              <div className="flex items-center gap-1">
                <span>🟠</span> <span>Às vezes (1 obs.)</span>
              </div>
              <div className="flex items-center gap-1">
                <span>⚪️</span> <span>Não observado</span>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {bimestresDisponiveis.map((bimestre) => (
              <Dialog key={bimestre.id}>
                <DialogTrigger asChild>
                  <div
                    className="p-4 border border-gray-200 rounded-lg hover:shadow-md transition-shadow cursor-pointer bg-gradient-to-br from-lavanda-claro to-white"
                    onClick={() => loadPeriodoDetails(bimestre)}
                  >
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <Calendar className="h-4 w-4 text-roxo-principal" />
                        <span className="font-semibold text-sm">{bimestre.label}</span>
                      </div>
                      <Eye className="h-4 w-4 text-gray-400" />
                    </div>
                    <div className="space-y-1 text-xs text-gray-600">
                      <p>{bimestre.totalObservacoes} observações</p>
                      <p>Última: {safeFormatDate(bimestre.ultimaObservacao, 'dd/MM/yyyy', { locale: ptBR })}</p>
                    </div>
                  </div>
                </DialogTrigger>
                
                <DialogContent className="max-w-4xl max-h-[80vh] overflow-y-auto">
                  <DialogHeader>
                    <DialogTitle className="flex items-center gap-2">
                      <BookOpen className="h-5 w-5 text-roxo-principal" />
                      Habilidades BNCC - {bimestre.label}
                    </DialogTitle>
                  </DialogHeader>

                  {loadingModal ? (
                    <div className="flex items-center justify-center py-8">
                      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-roxo-principal"></div>
                      <span className="ml-2 text-gray-600">Carregando detalhes...</span>
                    </div>
                  ) : modalData ? (
                    <div className="space-y-6">
                      <div className="text-sm text-gray-600 bg-gray-50 p-3 rounded-lg">
                        Total de observações neste bimestre: <strong>{modalData.totalObservacoes}</strong>
                      </div>

                      {modalData.campos.length === 0 ? (
                        <EmptyContent message="Nenhuma habilidade BNCC observada neste bimestre." />
                      ) : (
                        <div className="space-y-4">
                          {modalData.campos.map((campo, campoIndex) => (
                            <div key={campoIndex} className="border border-gray-200 rounded-lg overflow-hidden">
                              <div 
                                className="bg-lavanda-claro p-4 cursor-pointer hover:bg-opacity-80"
                                onClick={() => toggleSkillExpansion(`${bimestre.id}-${campoIndex}`)}
                              >
                                <div className="flex items-center justify-between">
                                  <h4 className="font-semibold text-roxo-principal">{campo.nome}</h4>
                                  <div className="flex items-center gap-2">
                                    <Badge variant="outline" className="whitespace-nowrap">
                                      <span className="sm:hidden">{campo.perguntas.length} perg.</span>
                                      <span className="hidden sm:inline">{campo.perguntas.length} perguntas</span>
                                    </Badge>
                                    {expandedSkills.has(`${bimestre.id}-${campoIndex}`) ? 
                                      <ChevronDown className="h-4 w-4" /> : 
                                      <ChevronRight className="h-4 w-4" />
                                    }
                                  </div>
                                </div>
                              </div>

                              {expandedSkills.has(`${bimestre.id}-${campoIndex}`) && (
                                <div className="p-4 space-y-4">
                                  {campo.perguntas.map((pergunta, perguntaIndex) => (
                                    <div key={perguntaIndex} className="border border-gray-100 rounded-lg p-3">
                                      <div className="flex items-start justify-between gap-3 mb-2">
                                        <div className="flex-1">
                                          <p className="text-sm font-medium text-gray-800">
                                            {pergunta.pergunta}
                                          </p>
                                          {pergunta.habilidade_bncc && (
                                            <p className="text-xs text-gray-600 mt-1">
                                              <strong>Habilidade BNCC:</strong> {pergunta.habilidade_bncc}
                                            </p>
                                          )}
                                        </div>
                                        <div className="flex items-center gap-2">
                                          <TooltipProvider>
                                            <Tooltip>
                                              <TooltipTrigger>
                                                <span className="text-xl">{pergunta.icon}</span>
                                              </TooltipTrigger>
                                              <TooltipContent>
                                                <p>{pergunta.label} ({pergunta.frequencia} observação{pergunta.frequencia !== 1 ? 'ões' : ''})</p>
                                              </TooltipContent>
                                            </Tooltip>
                                          </TooltipProvider>
                                          <Badge variant="secondary" className="text-xs">
                                            {pergunta.frequencia}x
                                          </Badge>
                                        </div>
                                      </div>

                                      {pergunta.comentarios.length > 0 && (
                                        <div className="mt-3 pt-3 border-t border-gray-200">
                                          <div className="flex items-center gap-1 mb-2">
                                            <MessageCircle className="h-3 w-3 text-gray-500" />
                                            <span className="text-xs font-medium text-gray-600">
                                              Comentários ({pergunta.comentarios.length}):
                                            </span>
                                          </div>
                                          <div className="space-y-2">
                                            {pergunta.comentarios.map((comment, commentIndex) => (
                                              <div key={commentIndex} className="bg-blue-50 p-2 rounded border-l-2 border-blue-300">
                                                <p className="text-xs text-gray-700">{comment.comentario}</p>
                                                <p className="text-xs text-gray-500 mt-1">
                                                  {safeFormatDate(comment.data, 'dd/MM/yyyy', { locale: ptBR })}
                                                </p>
                                              </div>
                                            ))}
                                          </div>
                                        </div>
                                      )}
                                    </div>
                                  ))}
                                </div>
                              )}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  ) : null}
                </DialogContent>
              </Dialog>
            ))}
          </div>
        </div>
      )}
    </motion.div>
  );
};

export default SkillsMatrixBlock;