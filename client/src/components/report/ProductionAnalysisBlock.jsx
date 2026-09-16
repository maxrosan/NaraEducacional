import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Palette, Lock, FileText, Calendar, Loader2, ChevronRight, Eye, Download, Trash2 } from 'lucide-react';
import EmptyContent from '@/components/reports/EmptyContent';
import ModalDetalhesEscrita from './ModalDetalhesEscrita';
import { buscarRegistrosPorAluno } from '@/services/api';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter, DialogClose } from '@/components/ui/dialog';
import { toast } from '@/components/ui/use-toast';
import { apiClient } from '@/lib/apiClient';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || import.meta.env.VITE_API_URL || '';

const ProductionAnalysisBlock = ({ nomeAluno, periodo, readOnly = false }) => {
  const [registros, setRegistros] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [modalAberto, setModalAberto] = useState(false);
  const [registroSelecionado, setRegistroSelecionado] = useState(null);
  const [modalDesenhoAberto, setModalDesenhoAberto] = useState(false);
  const [desenhoSelecionado, setDesenhoSelecionado] = useState(null);
  const [deletingRegistro, setDeletingRegistro] = useState(null);

  const carregarRegistros = async () => {
    if (!nomeAluno) return;
    
    console.log('🔍 [ProductionAnalysisBlock] Carregando registros para:', nomeAluno);
    
    setLoading(true);
    setError(null);
    
    try {
      const dados = await buscarRegistrosPorAluno(nomeAluno, {
        dataInicio: periodo?.data_inicio,
        dataFim: periodo?.data_fim,
      });
      console.log('✅ [ProductionAnalysisBlock] Dados recebidos:', dados);
      console.log('📊 [ProductionAnalysisBlock] Registros encontrados:', dados.registros?.length || 0);
      setRegistros(dados.registros || []);
    } catch (err) {
      console.error('❌ [ProductionAnalysisBlock] Erro ao carregar registros:', err);
      setError('Erro ao carregar análises de escrita. Tente novamente.');
    } finally {
      setLoading(false);
    }
  };

  const abrirDetalhes = (registro) => {
    if (registro.tipo === 'escrita') {
      setRegistroSelecionado(registro);
      setModalAberto(true);
    } else {
      // Para desenhos, abrir modal específica
      setDesenhoSelecionado(registro);
      setModalDesenhoAberto(true);
    }
  };

  const fecharModal = () => {
    setModalAberto(false);
    setRegistroSelecionado(null);
  };

  const fecharModalDesenho = () => {
    setModalDesenhoAberto(false);
    setDesenhoSelecionado(null);
  };

  const handleDelete = async () => {
    if (!deletingRegistro) return;
    const { tipo, uuid } = deletingRegistro;
    const tabela = tipo === 'escrita' ? 'registros-escrita' : 'registros-desenho';
    const { error } = await apiClient.from(tabela).delete().eq('id', uuid);
    if (error) {
      toast({ variant: 'destructive', title: 'Erro ao excluir', description: error.message });
      return;
    }
    toast({ title: 'Análise excluída com sucesso.' });
    setDeletingRegistro(null);
    carregarRegistros();
  };

  const abrirArquivo = (arquivoHash) => {
    const url = `${API_BASE_URL}/api/arquivo/${arquivoHash}/`;
    window.open(url, '_blank');
  };

  useEffect(() => {
    console.log('🔄 [ProductionAnalysisBlock] useEffect chamado:', { nomeAluno });
    carregarRegistros();
  }, [nomeAluno, periodo]);

  return (
    <>
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.2 }}
        className="bg-white p-6 rounded-2xl shadow-md border border-gray-100"
      >
        <div className="flex items-center gap-3 mb-4">
          <div className="bg-lavanda-claro p-2 rounded-full">
            <Palette className="h-5 w-5 text-roxo-principal" />
          </div>
          <h3 className="text-lg font-bold text-texto-escuro">Análises de Produções</h3>
          {loading && <Loader2 className="h-4 w-4 animate-spin text-roxo-principal ml-2" />}
          <span className="text-xs text-gray-500 ml-2">({registros.length} registros)</span>
        </div>
        
        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 p-3 rounded-lg mb-4">
            {error}
            <Button 
              onClick={carregarRegistros} 
              variant="outline" 
              size="sm" 
              className="ml-2"
            >
              Tentar novamente
            </Button>
          </div>
        )}
        
        {!loading && !error && registros.length === 0 ? (
          <div>
            <EmptyContent />
            {nomeAluno && (
              <div className="mt-4 p-3 bg-orange-50 border border-orange-200 rounded-lg text-sm">
                <p className="text-orange-700">
                  <strong>Verificação:</strong> Buscando análises de escrita e desenho para "<em>{nomeAluno}</em>"
                </p>
                <button 
                  onClick={carregarRegistros}
                  className="mt-2 px-3 py-1 bg-orange-500 text-white rounded text-xs hover:bg-orange-600"
                >
                  Recarregar
                </button>
              </div>
            )}
          </div>
        ) : (
          <div className="space-y-4">
            {registros.map((registro, index) => {
              const isDesenho = registro.tipo === 'desenho';
              const IconeProducao = isDesenho ? Palette : FileText;
              const corGradiente = isDesenho 
                ? 'from-green-500 to-emerald-400' 
                : 'from-roxo-principal to-lavanda';
              
              return (
                <motion.div
                  key={registro.id || index}
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ duration: 0.3, delay: index * 0.1 }}
                  className="flex items-start gap-4 p-4 rounded-lg bg-gray-50 border hover:border-roxo-claro hover:bg-lavanda-claro hover:bg-opacity-30 transition-all duration-200 cursor-pointer"
                  onClick={() => abrirDetalhes(registro)}
                >
                  <div className={`hidden sm:flex flex-shrink-0 w-16 h-16 bg-gradient-to-br ${corGradiente} rounded-lg items-center justify-center`}>
                    <IconeProducao className="h-8 w-8 text-white" />
                  </div>
                  
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-2">
                      <p className="font-bold text-texto-escuro truncate">
                        {isDesenho ? 'Análise de Desenho' : 'Análise de Escrita'}
                      </p>
                      <div className="flex items-center gap-1 text-xs text-texto-medio">
                        <Calendar className="h-3 w-3" />
                        <span>{registro.data_criacao}</span>
                      </div>
                    </div>
                    
                    <p className="text-sm text-texto-medio mb-3 line-clamp-2">
                      {registro.analise_resumida}
                    </p>
                    
                    <div className="flex items-center justify-between">
                      <div className="bg-lavanda-claro p-2 rounded-md text-xs text-roxo-principal flex items-center gap-2">
                        <Lock className="h-3 w-3" />
                        <span className="font-semibold">
                          {isDesenho ? 'Fase:' : 'Etapa IA:'}
                        </span>
                        <span className="italic">{registro.etapa_ia}</span>
                      </div>

                      <div className="flex items-center gap-2">
                        {!readOnly && (
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              const uuid = registro.id.replace(/^(escrita|desenho)_/, '');
                              setDeletingRegistro({ tipo: registro.tipo, uuid });
                            }}
                            className="p-1 rounded hover:bg-red-100 text-gray-400 hover:text-red-600 transition-colors"
                          >
                            <Trash2 className="h-4 w-4" />
                          </button>
                        )}
                        <ChevronRight className="h-4 w-4 text-roxo-principal" />
                      </div>
                    </div>
                  </div>
                </motion.div>
              );
            })}
          </div>
        )}
      </motion.div>

      <Dialog open={!!deletingRegistro} onOpenChange={() => setDeletingRegistro(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Confirmar Exclusão</DialogTitle>
            <DialogDescription>
              Tem certeza que deseja excluir esta análise? Esta ação é irreversível.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <DialogClose asChild>
              <Button variant="outline">Cancelar</Button>
            </DialogClose>
            <Button variant="destructive" onClick={handleDelete}>Excluir</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <ModalDetalhesEscrita
        isOpen={modalAberto}
        onClose={fecharModal}
        registro={registroSelecionado}
      />

      {/* Modal para Análise de Desenho */}
      {modalDesenhoAberto && desenhoSelecionado && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.95 }}
            className="bg-white rounded-xl shadow-2xl max-w-4xl w-full max-h-[90vh] overflow-y-auto"
          >
            <div className="p-6">
              {/* Cabeçalho */}
              <div className="flex items-center justify-between mb-6">
                <div className="flex items-center gap-3">
                  <div className="w-12 h-12 bg-gradient-to-br from-green-500 to-emerald-400 rounded-lg flex items-center justify-center">
                    <Palette className="h-6 w-6 text-white" />
                  </div>
                  <div>
                    <h2 className="text-xl font-bold text-gray-900">Análise de Desenho</h2>
                    <p className="text-sm text-gray-600">{desenhoSelecionado.nome_aluno}</p>
                  </div>
                </div>
                <button
                  onClick={fecharModalDesenho}
                  className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
                >
                  ✕
                </button>
              </div>

              {/* Informações Básicas */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
                <div className="bg-green-50 p-4 rounded-lg">
                  <h3 className="font-semibold text-green-800 mb-1">Fase Detectada</h3>
                  <p className="text-green-700">{desenhoSelecionado.etapa_ia}</p>
                </div>
                <div className="bg-purple-50 p-4 rounded-lg">
                  <h3 className="font-semibold text-purple-800 mb-1">Data</h3>
                  <p className="text-purple-700">{desenhoSelecionado.data_criacao}</p>
                </div>
              </div>

              {/* Botões de Ação */}
              <div className="flex gap-3 mb-6">
                <Button
                  onClick={() => abrirArquivo(desenhoSelecionado.arquivo_hash)}
                  className="flex items-center gap-2 bg-green-600 hover:bg-green-700"
                >
                  <Eye className="h-4 w-4" />
                  Visualizar Desenho
                </Button>
                <Button
                  variant="outline"
                  onClick={() => abrirArquivo(desenhoSelecionado.arquivo_hash)}
                  className="flex items-center gap-2"
                >
                  <Download className="h-4 w-4" />
                  Download
                </Button>
              </div>

              {/* Análise Completa */}
              <div className="bg-gray-50 p-4 rounded-lg">
                <h3 className="font-semibold text-gray-800 mb-3">Análise Detalhada</h3>
                <div className="prose text-sm text-gray-700 whitespace-pre-wrap">
                  {desenhoSelecionado.analise_completa}
                </div>
              </div>

              {/* Informações Adicionais */}
              {(desenhoSelecionado.atividade || desenhoSelecionado.contexto) && (
                <div className="mt-6 grid grid-cols-1 md:grid-cols-2 gap-4">
                  {desenhoSelecionado.atividade && (
                    <div>
                      <h4 className="font-semibold text-gray-800 mb-2">Atividade</h4>
                      <p className="text-gray-600 text-sm">{desenhoSelecionado.atividade}</p>
                    </div>
                  )}
                  {desenhoSelecionado.contexto && (
                    <div>
                      <h4 className="font-semibold text-gray-800 mb-2">Contexto</h4>
                      <p className="text-gray-600 text-sm">{desenhoSelecionado.contexto}</p>
                    </div>
                  )}
                </div>
              )}
            </div>
          </motion.div>
        </div>
      )}
    </>
  );
};

export default ProductionAnalysisBlock;