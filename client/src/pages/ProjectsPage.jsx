import React, { useState, useEffect, useCallback } from 'react';
import { Helmet } from 'react-helmet-async';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { ArrowLeft, Plus, BookCopy, Loader2 } from 'lucide-react';
import { apiClient } from '@/lib/apiClient';
import { useToast } from '@/components/ui/use-toast';
import { Button } from '@/components/ui/button';
import ProjectForm from '@/components/projects/ProjectForm';
import ProjectCard from '@/components/projects/ProjectCard';

function ProjectsPage() {
  const navigate = useNavigate();
  const { toast } = useToast();
  const [showForm, setShowForm] = useState(false);
  const [projects, setProjects] = useState([]);
  const [editingProject, setEditingProject] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchProjects = useCallback(async () => {
    setLoading(true);
    const { data, error } = await apiClient
      .from('projetos')
      .select(`
        *,
        projeto_turmas (
          turma_id
        )
      `)
      .order('created_at', { ascending: false });

    if (error) {
      toast({ variant: 'destructive', title: 'Erro ao buscar projetos', description: error.message });
    } else {
      const formattedProjects = data.map(p => ({
        ...p,
        turmas: p.projeto_turmas.map(pt => pt.turma_id)
      }));
      setProjects(formattedProjects);
    }
    setLoading(false);
  }, [toast]);

  useEffect(() => {
    fetchProjects();
  }, [fetchProjects]);

  const handleAddNew = () => {
    setEditingProject(null);
    setShowForm(true);
  };

  const handleEdit = (project) => {
    setEditingProject(project);
    setShowForm(true);
  };

  const handleCancel = () => {
    setShowForm(false);
    setEditingProject(null);
  };

  const handleSave = () => {
    setShowForm(false);
    setEditingProject(null);
    fetchProjects();
  };

  const handleDelete = async (id) => {
    if (window.confirm('Tem certeza que deseja excluir este projeto?')) {
      const { error: turmaError } = await apiClient.from('projeto_turmas').delete().eq('projeto_id', id);
      if (turmaError) {
        toast({ variant: 'destructive', title: 'Erro ao desvincular turmas', description: turmaError.message });
        return;
      }
      const { error } = await apiClient.from('projetos').delete().eq('id', id);
      if (error) {
        toast({ variant: 'destructive', title: 'Erro ao excluir', description: error.message });
      } else {
        toast({ title: 'Projeto excluído com sucesso.' });
        fetchProjects();
      }
    }
  };

  const handleFinish = async (id) => {
    const { error } = await apiClient.from('projetos').update({ status: 'Finalizado' }).eq('id', id);
    if (error) {
      toast({ variant: 'destructive', title: 'Erro ao finalizar', description: error.message });
    } else {
      toast({ title: 'Projeto finalizado com sucesso.' });
      fetchProjects();
    }
  };

  return (
    <>
      <Helmet>
        <title>NARA - Meus Projetos</title>
        <meta name="description" content="Cadastre e gerencie os projetos pedagógicos." />
      </Helmet>
      <div className="bg-[#F5F3FA] min-h-screen">
        <header className="sticky top-0 bg-white/80 backdrop-blur-sm z-10 shadow-sm">
          <div className="container mx-auto px-4 sm:px-6 lg:px-8 py-4 flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Button variant="ghost" size="icon" onClick={() => navigate(-1)}>
                <ArrowLeft className="h-6 w-6 text-gray-600" />
              </Button>
              <h1 className="text-xl font-bold text-gray-800 flex items-center gap-2"><BookCopy /> Meus Projetos</h1>
            </div>
            <Button onClick={handleAddNew} disabled={showForm}>
              <Plus className="mr-2 h-4 w-4" /> Novo Projeto
            </Button>
          </div>
        </header>

        <main className="container mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <AnimatePresence mode="wait">
            {showForm ? (
              <ProjectForm project={editingProject} onSave={handleSave} onCancel={handleCancel} />
            ) : (
              <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                <div className="text-center mb-8">
                  <p className="text-gray-600">Cadastre aqui os projetos que sua turma está vivenciando. Eles poderão ser vinculados a registros, portfólios e relatórios.</p>
                </div>
                {loading ? (
                  <div className="flex justify-center items-center p-8"><Loader2 className="h-8 w-8 animate-spin text-purple-500" /></div>
                ) : projects.length > 0 ? (
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {projects.map(project => (
                      <ProjectCard key={project.id} project={project} onEdit={handleEdit} onDelete={handleDelete} onFinish={handleFinish} />
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-16 border-2 border-dashed rounded-lg">
                    <h3 className="text-lg font-semibold text-gray-700">Nenhum projeto cadastrado ainda.</h3>
                    <p className="text-gray-500 mt-2">Clique em "Novo Projeto" para começar.</p>
                  </div>
                )}
              </motion.div>
            )}
          </AnimatePresence>
        </main>
      </div>
    </>
  );
}

export default ProjectsPage;