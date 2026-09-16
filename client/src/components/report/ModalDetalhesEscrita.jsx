import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, Calendar, User, Brain, FileText, BookOpen, Hash, Clock, Eye, ExternalLink } from 'lucide-react';
import { Button } from '@/components/ui/button';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || import.meta.env.VITE_API_URL || '';

const ModalDetalhesEscrita = ({ isOpen, onClose, registro }) => {
  if (!registro) return null;

  const formatarTamanho = (bytes) => {
    if (!bytes) return 'N/A';
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const abrirArquivo = () => {
    if (registro.arquivo_hash) {
      const urlArquivo = `${API_BASE_URL}/api/arquivo/${registro.arquivo_hash}/`;
      window.open(urlArquivo, '_blank');
    }
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="absolute inset-0 bg-black bg-opacity-50"
            onClick={onClose}
          />
          
          {/* Modal */}
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 20 }}
            className="relative bg-white rounded-2xl shadow-2xl w-full max-w-3xl max-h-[90vh] overflow-hidden"
          >
            {/* Header */}
            <div className="bg-gradient-to-r from-roxo-principal to-lavanda p-6 text-white">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-xl font-bold">Análise de Escrita Detalhada</h2>
                  <p className="text-roxo-claro opacity-90">{registro.nome_aluno}</p>
                </div>
                <div className="flex items-center gap-2">
                  <Button
                    onClick={abrirArquivo}
                    size="sm"
                    variant="ghost"
                    className="text-white hover:bg-white hover:bg-opacity-20 flex items-center gap-2"
                  >
                    <Eye className="h-4 w-4" />
                    Ver Arquivo
                  </Button>
                  <Button
                    onClick={onClose}
                    size="icon"
                    variant="ghost"
                    className="text-white hover:bg-white hover:bg-opacity-20"
                  >
                    <X className="h-5 w-5" />
                  </Button>
                </div>
              </div>
            </div>

            {/* Content */}
            <div className="p-6 overflow-y-auto max-h-[calc(90vh-180px)]">
              <div className="space-y-6">
                {/* Informações básicas */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
                    <Calendar className="h-5 w-5 text-roxo-principal" />
                    <div>
                      <p className="text-xs text-gray-500">Data da Análise</p>
                      <p className="font-semibold text-sm">{registro.data_criacao}</p>
                    </div>
                  </div>

                  <div className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
                    <Hash className="h-5 w-5 text-roxo-principal" />
                    <div>
                      <p className="text-xs text-gray-500">Arquivo</p>
                      <p className="font-semibold text-sm">{formatarTamanho(registro.tamanho_arquivo)}</p>
                    </div>
                  </div>
                </div>

                {/* Etapa da IA */}
                <div className="bg-lavanda-claro p-4 rounded-lg border-l-4 border-roxo-principal">
                  <div className="flex items-center gap-2 mb-2">
                    <Brain className="h-5 w-5 text-roxo-principal" />
                    <h3 className="font-bold text-roxo-principal">Etapa Sugerida pela IA</h3>
                  </div>
                  <p className="text-xl font-semibold text-texto-escuro">{registro.etapa_ia}</p>
                </div>

                {/* Análise detalhada */}
                <div>
                  <div className="flex items-center gap-2 mb-3">
                    <FileText className="h-5 w-5 text-roxo-principal" />
                    <h3 className="font-bold text-texto-escuro">Análise Detalhada da IA</h3>
                  </div>
                  <div className="bg-gray-50 p-4 rounded-lg max-h-64 overflow-y-auto">
                    <pre className="whitespace-pre-wrap text-sm text-texto-medio font-sans leading-relaxed">
                      {registro.analise_completa}
                    </pre>
                  </div>
                </div>

                {/* Anotações da professora */}
                {registro.anotacoes_professora && registro.anotacoes_professora.trim() && (
                  <div>
                    <div className="flex items-center gap-2 mb-3">
                      <BookOpen className="h-5 w-5 text-verde-escuro" />
                      <h3 className="font-bold text-texto-escuro">Anotações da Professora</h3>
                    </div>
                    <div className="bg-verde-menta bg-opacity-20 p-4 rounded-lg border border-verde-menta">
                      <p className="text-texto-escuro">{registro.anotacoes_professora}</p>
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Footer */}
            <div className="bg-gray-50 px-6 py-4 flex justify-between items-center border-t">
              <Button 
                onClick={abrirArquivo}
                variant="outline"
                className="border-roxo-principal text-roxo-principal hover:bg-roxo-principal hover:text-white flex items-center gap-2"
              >
                <ExternalLink className="h-4 w-4" />
                Abrir Arquivo Original
              </Button>
              
              <Button 
                onClick={onClose} 
                className="bg-roxo-principal hover:bg-roxo-escuro text-white"
              >
                Fechar
              </Button>
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
};

export default ModalDetalhesEscrita;
