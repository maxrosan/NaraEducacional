import React, { useState, useEffect, useCallback } from 'react';
import { Helmet } from 'react-helmet-async';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { apiClient } from '@/lib/apiClient';
import { useAuth } from '@/contexts/AuthContext';
import { useToast } from '@/components/ui/use-toast';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogClose } from '@/components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { ArrowLeft, Image, UploadCloud, Loader2 } from 'lucide-react';
import PortfolioItemCard from '@/components/portfolio/PortfolioItemCard';
import EditPortfolioItemModal from '@/components/portfolio/EditPortfolioItemModal';
import { PortfolioUploadForm } from '@/components/portfolio/PortfolioUploadForm';
import ProfessorNavbar from '@/components/teacher/ProfessorNavBar';

const STORAGE_KEY_TURMA = 'nara_portfolio_selected_turma';
const STORAGE_KEY_CRIANCA = 'nara_portfolio_selected_crianca';
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

const getCsrfToken = () => {
  const match = document.cookie.match(/csrftoken=([^;]+)/);
  return match ? match[1] : '';
};

const PortfoliosPage = () => {
  const navigate = useNavigate();
  const { toast } = useToast();
  const { user, turmaAtiva } = useAuth();
  const [turmas, setTurmas] = useState([]);
  const [criancas, setCriancas] = useState([]);
  const [selectedTurma, setSelectedTurma] = useState(() => {
    return localStorage.getItem(STORAGE_KEY_TURMA) || '';
  });
  const [selectedCrianca, setSelectedCrianca] = useState(() => {
    return localStorage.getItem(STORAGE_KEY_CRIANCA) || '';
  });
  const [portfolioItems, setPortfolioItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadingCriancas, setLoadingCriancas] = useState(false);
  const [editingItem, setEditingItem] = useState(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isUploadOpen, setIsUploadOpen] = useState(false);
  const [showTurmaSelect, setShowTurmaSelect] = useState(false);
  const [initialLoadComplete, setInitialLoadComplete] = useState(false);
  const [bulkUpdating, setBulkUpdating] = useState(false);

  const fetchCriancas = useCallback(async (turmaId) => {
    if (!turmaId) {
      setCriancas([]);
      return;
    }
    setLoadingCriancas(true);
    try {
      const { data, error } = await apiClient
        .from('criancas')
        .select('id, nome_completo')
        .eq('turma_id', turmaId)
        .order('nome_completo');
      if (error) throw error;
      setCriancas(data);
    } catch (error) {
      toast({ variant: 'destructive', title: 'Erro ao buscar crianças', description: error.message });
    } finally {
      setLoadingCriancas(false);
    }
  }, [toast]);

  const handleTurmaChange = useCallback((turmaId) => {
    setSelectedTurma(turmaId);
    setSelectedCrianca('');
    setPortfolioItems([]);
    localStorage.setItem(STORAGE_KEY_TURMA, turmaId);
    localStorage.removeItem(STORAGE_KEY_CRIANCA);
    fetchCriancas(turmaId);
  }, [fetchCriancas]);

  const fetchTurmas = useCallback(async () => {
    if (!user) return;
    setLoading(true);
    try {
      const { data: userTurmasData, error: userTurmasError } = await apiClient
        .from('usuario_turmas')
        .select('turma_id')
        .eq('usuario_id', user.id);

      if (userTurmasError) throw userTurmasError;

      const turmaIds = userTurmasData.map(ut => ut.turma_id);
      if (turmaIds.length === 0) {
        setTurmas([]);
        setShowTurmaSelect(false);
        setLoading(false);
        setInitialLoadComplete(true);
        return;
      }

      const { data: turmasData, error: turmasError } = await apiClient
        .from('turmas')
        .select('id, nome')
        .in('id', turmaIds);

      if (turmasError) throw turmasError;

      setTurmas(turmasData);

      const savedTurma = localStorage.getItem(STORAGE_KEY_TURMA);
      const savedCrianca = localStorage.getItem(STORAGE_KEY_CRIANCA);

      // Prioridade: turmaAtiva do contexto > localStorage > primeira turma
      const turmaToUsePadrao =
        turmasData.find(t => t.id === turmaAtiva?.id)?.id ||
        (savedTurma && turmasData.some(t => t.id === savedTurma) ? savedTurma : null) ||
        turmasData[0].id;

      if (turmasData.length === 1) {
        setShowTurmaSelect(false);
        const turmaToUse = turmaToUsePadrao;
        setSelectedTurma(turmaToUse);
        localStorage.setItem(STORAGE_KEY_TURMA, turmaToUse);
        await fetchCriancas(turmaToUse);
        if (savedCrianca) {
          setSelectedCrianca(savedCrianca);
        }
      } else {
        setShowTurmaSelect(true);
        // Pré-selecionar turmaAtiva do contexto (ou fallback)
        handleTurmaChange(turmaToUsePadrao);
      }

      setInitialLoadComplete(true);
    } catch (error) {
      toast({ variant: 'destructive', title: 'Erro ao buscar turmas', description: error.message });
    } finally {
      setLoading(false);
    }
  }, [user, toast, fetchCriancas, handleTurmaChange, turmaAtiva]);

  const fetchPortfolioItems = useCallback(async () => {
    if (!selectedCrianca || !selectedTurma) {
      setPortfolioItems([]);
      return;
    }
    setLoading(true);
    try {
      const params = new URLSearchParams({
        turma_id: selectedTurma,
        crianca_id: selectedCrianca,
      });
      const response = await fetch(`${API_BASE_URL}/api/portfolio/listar/?${params}`, {
        credentials: 'include',
      });
      const payload = await response.json();

      if (!response.ok || !payload?.success) {
        throw new Error(payload?.error || 'Erro ao buscar portfólio');
      }

      const producoes = payload.producoes || [];
      const itens = producoes.flatMap((producao) => {
        const vinculo = (producao.criancas || []).find(
          (crianca) => crianca.crianca_id === selectedCrianca
        );
        if (!vinculo) return [];
        return [{
          id: vinculo.id,
          producao_id: producao.id,
          data_registro: producao.data_registro,
          projeto: producao.projeto,
          descricao: vinculo.legenda,
          legenda_ia: vinculo.legenda_ia,
          para_relatorio: vinculo.incluir_relatorio,
          media_urls: [producao.arquivo_url],
          arquivo_nome: producao.arquivo_nome,
          tipo_midia: producao.tipo_midia,
        }];
      });

      setPortfolioItems(itens);
    } catch (error) {
      toast({ variant: 'destructive', title: 'Erro ao buscar portfólio', description: error.message });
    } finally {
      setLoading(false);
    }
  }, [selectedCrianca, selectedTurma, toast]);

  useEffect(() => {
    fetchTurmas();
  }, [fetchTurmas]);

  useEffect(() => {
    if (!initialLoadComplete) return;
    if (turmaAtiva?.id && turmaAtiva.id !== selectedTurma) {
      handleTurmaChange(turmaAtiva.id);
    }
  }, [turmaAtiva?.id, initialLoadComplete, selectedTurma, handleTurmaChange]);

  useEffect(() => {
    fetchPortfolioItems();
  }, [fetchPortfolioItems]);

  const handleCriancaChange = (criancaId) => {
    setSelectedCrianca(criancaId);
    localStorage.setItem(STORAGE_KEY_CRIANCA, criancaId);
  };

  const handleSelectItem = async (itemId, checked) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/portfolio/vinculo/${itemId}/`, {
        method: 'PATCH',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCsrfToken(),
        },
        body: JSON.stringify({ incluir_relatorio: checked }),
      });
      if (!response.ok) {
        throw new Error('Erro ao selecionar item');
      }
      fetchPortfolioItems();
    } catch (error) {
      toast({ variant: 'destructive', title: 'Erro ao selecionar item', description: error.message });
    }
  };

  const handleEditItem = (item) => {
    setEditingItem(item);
    setIsModalOpen(true);
  };

  const handleDeleteItem = async (producaoId) => {
    if (window.confirm('Tem certeza que deseja excluir este registro?')) {
      try {
        const response = await fetch(`${API_BASE_URL}/api/portfolio/excluir/${producaoId}/`, {
          method: 'DELETE',
          credentials: 'include',
          headers: {
            'X-CSRFToken': getCsrfToken(),
          },
        });
        if (!response.ok) {
          throw new Error('Erro ao excluir');
        }
        toast({ title: 'Registro excluído com sucesso!' });
        fetchPortfolioItems();
      } catch (error) {
        toast({ variant: 'destructive', title: 'Erro ao excluir', description: error.message });
      }
    }
  };

  const handleSaveItem = async (updatedItem) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/portfolio/vinculo/${updatedItem.id}/`, {
        method: 'PATCH',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCsrfToken(),
        },
        body: JSON.stringify({ legenda: updatedItem.descricao }),
      });
      if (!response.ok) {
        throw new Error('Erro ao salvar');
      }
      toast({ title: 'Registro atualizado!' });
      fetchPortfolioItems();
    } catch (error) {
      toast({ variant: 'destructive', title: 'Erro ao salvar', description: error.message });
    }
  };

  const handleUploadComplete = useCallback(() => {
    fetchPortfolioItems();
    setIsUploadOpen(false);
  }, [fetchPortfolioItems]);

  const handleBulkToggle = async (incluirRelatorio) => {
    if (!portfolioItems.length) return;

    const idsToUpdate = portfolioItems
      .filter(item => item.para_relatorio !== incluirRelatorio)
      .map(item => item.id);

    if (idsToUpdate.length === 0) {
      toast({
        title: 'Nenhuma alteração necessária',
        description: 'Todos os registros já estão com o status desejado.',
      });
      return;
    }

    setBulkUpdating(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/portfolio/vinculos/lote/`, {
        method: 'PATCH',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCsrfToken(),
        },
        body: JSON.stringify({ vinculo_ids: idsToUpdate, incluir_relatorio: incluirRelatorio }),
      });

      const payload = await response.json();
      if (!response.ok || !payload?.success) {
        throw new Error(payload?.error || 'Erro ao atualizar portfólio');
      }

      toast({
        title: 'Atualização em massa concluída',
        description: `${payload.total_atualizados || idsToUpdate.length} registros atualizados.`,
      });
      fetchPortfolioItems();
    } catch (error) {
      toast({ variant: 'destructive', title: 'Erro ao atualizar em massa', description: error.message });
    } finally {
      setBulkUpdating(false);
    }
  };

  return (
    <>
      <Helmet>
        <title>NARA - Portfólios</title>
        <meta name="description" content="Gerencie os portfólios das crianças." />
      </Helmet>
      <div className="bg-[#F5F3FA] min-h-screen">
        <ProfessorNavbar />

        <div className="bg-white border-b shadow-sm">
          <div className="container mx-auto px-4 sm:px-6 lg:px-8 py-4 flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Button variant="ghost" size="icon" onClick={() => navigate(-1)}>
                <ArrowLeft className="h-6 w-6 text-gray-600" />
              </Button>
            </div>
            <div className="flex items-center gap-4"><h1 className="text-md font-bold text-gray-800 flex items-center gap-2"> Portfólios</h1>
              <Button
                onClick={() => setIsUploadOpen(true)}
                disabled={!selectedTurma}
                title={!selectedTurma ? 'Selecione uma turma para iniciar o upload' : undefined}
              >
                <UploadCloud className="h-4 w-4 mr-2" />
                <span className="sm:hidden">Upload</span>
                <span className="hidden sm:inline">Novo Upload</span>
              </Button>
            </div>
          </div>
        </div>

        <main className="container mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}>
            <div className="bg-white p-4 rounded-lg shadow-sm mb-8">
              <p className="text-gray-600 text-center">Aqui você encontra todos os registros da criança. Edite e selecione aqueles que representam melhor sua jornada para compor o relatório final.</p>
              <div className="grid grid-cols-1 gap-4 mt-4">
                <Select onValueChange={handleCriancaChange} value={selectedCrianca} disabled={!selectedTurma || loadingCriancas}>
                  <SelectTrigger>
                    <SelectValue placeholder={loadingCriancas ? "Carregando crianças..." : "Selecione a criança"} />
                  </SelectTrigger>
                  <SelectContent>
                    {criancas.map(crianca => <SelectItem key={crianca.id} value={crianca.id}>{crianca.nome_completo}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              {portfolioItems.length > 0 && (
                <div className="flex flex-wrap gap-2 justify-center mt-4">
                  <Button
                    variant="secondary"
                    onClick={() => handleBulkToggle(true)}
                    disabled={bulkUpdating}
                  >
                    Marcar todos para relatório
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => handleBulkToggle(false)}
                    disabled={bulkUpdating}
                  >
                    Remover todos do relatório
                  </Button>
                </div>
              )}
            </div>

            {loading ? (
              <div className="flex justify-center items-center p-8"><Loader2 className="h-8 w-8 animate-spin text-roxo-principal" /></div>
            ) : portfolioItems.length > 0 ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
                {portfolioItems.map(item => (
                  <PortfolioItemCard
                    key={item.id}
                    item={item}
                    onSelect={handleSelectItem}
                    onEdit={handleEditItem}
                    onDelete={handleDeleteItem}
                  />
                ))}
              </div>
            ) : (
              <div className="text-center py-16 border-2 border-dashed rounded-lg">
                <h3 className="text-lg font-semibold text-gray-700">Nenhum registro encontrado.</h3>
                <p className="text-gray-500 mt-2">Selecione uma turma e uma criança para visualizar o portfólio.</p>
              </div>
            )}
          </motion.div>
        </main>
      </div>
      <Dialog open={isUploadOpen} onOpenChange={setIsUploadOpen}>
        <DialogContent className="max-w-5xl max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <UploadCloud className="h-5 w-5 text-roxo-principal" />
              Novo Upload para o Portfólio
            </DialogTitle>
            <DialogDescription>
              Envie novas mídias e vincule as crianças da turma selecionada.
            </DialogDescription>
          </DialogHeader>
          {selectedTurma ? (
            <PortfolioUploadForm
              students={criancas}
              turmaId={selectedTurma}
              onUploadComplete={handleUploadComplete}
            />
          ) : (
            <div className="text-sm text-gray-600 py-6 text-center">
              Selecione uma turma para iniciar o upload.
            </div>
          )}
          <DialogFooter>
            <DialogClose asChild>
              <Button variant="outline">Fechar</Button>
            </DialogClose>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      <EditPortfolioItemModal
        item={editingItem}
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onSave={handleSaveItem}
      />
    </>
  );
};

export default PortfoliosPage;