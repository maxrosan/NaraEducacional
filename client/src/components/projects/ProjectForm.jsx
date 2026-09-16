import React, { useState, useEffect } from 'react';
import { format } from 'date-fns';
import { ptBR } from 'date-fns/locale';
import { motion, AnimatePresence } from 'framer-motion';
import { apiClient } from '@/lib/apiClient';
import { useAuth } from '@/contexts/AuthContext';
import { useToast } from '@/components/ui/use-toast';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardHeader, CardTitle, CardFooter } from '@/components/ui/card';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { Calendar as CalendarPicker } from '@/components/ui/calendar';
import { Checkbox } from '@/components/ui/checkbox';
import { Badge } from '@/components/ui/badge';
import { ProjectIaSuggestionBox } from '@/components/projects/ProjectIaSuggestionBox';
import { Calendar, CheckCircle, Loader2, Sparkles } from 'lucide-react';

const camposExperienciaOptions = [
  'O eu, o outro e o nós',
  'Corpo, gestos e movimentos',
  'Traços, sons, cores e formas',
  'Escuta, fala, pensamento e imaginação',
  'Espaços, tempos, quantidades, relações e transformações'
];

const areasEnvolvidasOptions = ['Linguagem', 'Natureza', 'Arte', 'Matemática', 'Música'];

const ProjectForm = ({ project, onSave, onCancel }) => {
  const { toast } = useToast();
  const { user } = useAuth();
  const [formData, setFormData] = useState({
    nome_projeto: project?.nome_projeto || '',
    turmas: project?.turmas || [],
    data_inicio: project?.data_inicio ? new Date(project.data_inicio) : new Date(),
    data_fim: project?.data_fim ? new Date(project.data_fim) : new Date(),
    objetivo_pedagogico: project?.objetivo_pedagogico || '',
    campos_experiencia: project?.campos_experiencia || [],
    areas_envolvidas: project?.areas_envolvidas || [],
    status: project?.status || 'Em andamento'
  });
  const [saving, setSaving] = useState(false);
  const [showIaSuggestion, setShowIaSuggestion] = useState(false);
  const [iaSuggestion, setIaSuggestion] = useState('');
  const [userTurmas, setUserTurmas] = useState([]);
  const [loadingTurmas, setLoadingTurmas] = useState(true);

  useEffect(() => {
    const fetchUserTurmas = async () => {
      if (!user) return;
      setLoadingTurmas(true);
      try {
        const { data: userTurmasData, error: userTurmasError } = await apiClient
          .from('usuario_turmas')
          .select('turma_id')
          .eq('usuario_id', user.id);

        if (userTurmasError) throw userTurmasError;

        const turmaIds = userTurmasData.map(ut => ut.turma_id);
        const { data: turmasData, error: turmasError } = await apiClient
          .from('turmas')
          .select('id, nome')
          .in('id', turmaIds);

        if (turmasError) throw turmasError;

        setUserTurmas(turmasData);

        if (turmasData.length === 1 && !project?.id) {
          setFormData(prev => ({ ...prev, turmas: [turmasData[0].id] }));
        }
      } catch (error) {
        toast({
          variant: 'destructive',
          title: 'Erro ao buscar turmas',
          description: error.message,
        });
      } finally {
        setLoadingTurmas(false);
      }
    };

    fetchUserTurmas();
  }, [user, toast, project?.id]);

  const handleChange = (field, value) => {
    setFormData(prev => ({ ...prev, [field]: value }));
  };

  const handleMultiSelectChange = (field, value) => {
    const currentValues = formData[field];
    const newValues = currentValues.includes(value)
      ? currentValues.filter(item => item !== value)
      : [...currentValues, value];
    handleChange(field, newValues);
  };

  const handleRequestIaSuggestion = () => {
    const { nome_projeto, campos_experiencia, areas_envolvidas } = formData;
    if (!nome_projeto) {
      toast({
        variant: 'destructive',
        title: 'Ops!',
        description: 'Preencha o nome do projeto para a IA gerar uma sugestão.',
      });
      return;
    }
    const suggestion = `Este projeto, "${nome_projeto}", tem como objetivo ampliar a capacidade de observação e escuta das crianças, promovendo interações significativas que envolvam ${areas_envolvidas.join(', ') || 'diversas áreas'}, em contextos lúdicos e investigativos, alinhado aos campos de experiência: ${campos_experiencia.join(', ') || 'BNCC'}.`;
    setIaSuggestion(suggestion);
    setShowIaSuggestion(true);
  };

  const useIaSuggestion = () => {
    handleChange('objetivo_pedagogico', iaSuggestion);
    setShowIaSuggestion(false);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);
    
    const professor_id = user.id;
    const instituicao_id = user.user_metadata.instituicao_id;

    const projectData = {
      nome_projeto: formData.nome_projeto,
      data_inicio: format(formData.data_inicio, 'yyyy-MM-dd'),
      data_fim: format(formData.data_fim, 'yyyy-MM-dd'),
      objetivo_pedagogico: formData.objetivo_pedagogico,
      campos_experiencia: formData.campos_experiencia,
      areas_envolvidas: formData.areas_envolvidas,
      status: formData.status,
      professor_id,
      instituicao_id,
    };
    
    const turmasToLink = formData.turmas;

    try {
      let savedProject;
      if (project?.id) {
        const { data, error } = await apiClient.from('projetos').update(projectData).eq('id', project.id).select().single();
        if (error) throw error;
        savedProject = data;
      } else {
        const { data, error } = await apiClient.from('projetos').insert(projectData).select().single();
        if (error) throw error;
        savedProject = data;
      }

      await apiClient.from('projeto_turmas').delete().eq('projeto_id', savedProject.id);

      if (turmasToLink.length > 0) {
        const links = turmasToLink.map(turma_id => ({ projeto_id: savedProject.id, turma_id }));
        const { error: linkError } = await apiClient.from('projeto_turmas').insert(links);
        if (linkError) throw linkError;
      }

      toast({
        title: '✅ Projeto salvo!',
        description: 'Seu projeto foi salvo com sucesso.',
        className: 'bg-green-100 border-green-300 text-green-800',
      });
      onSave();
    } catch (error) {
      toast({
        variant: 'destructive',
        title: 'Erro ao salvar projeto',
        description: error.message,
      });
    } finally {
      setSaving(false);
    }
  };

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
      <form onSubmit={handleSubmit} className="space-y-6">
        <Card>
          <CardHeader>
            <CardTitle>{project?.id ? 'Editar Projeto' : 'Cadastrar Novo Projeto'}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <Label htmlFor="nome_projeto">Nome do Projeto</Label>
              <Input id="nome_projeto" value={formData.nome_projeto} onChange={(e) => handleChange('nome_projeto', e.target.value)} required />
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <Label>Período de Realização</Label>
                <div className="flex items-center gap-2">
                  <Popover>
                    <PopoverTrigger asChild>
                      <Button variant="outline" className="w-full justify-start text-left font-normal">
                        <Calendar className="mr-2 h-4 w-4" />
                        {format(formData.data_inicio, 'PPP', { locale: ptBR })}
                      </Button>
                    </PopoverTrigger>
                    <PopoverContent className="w-auto p-0">
                      <CalendarPicker mode="single" selected={formData.data_inicio} onSelect={(date) => handleChange('data_inicio', date)} initialFocus locale={ptBR} />
                    </PopoverContent>
                  </Popover>
                  <span>até</span>
                  <Popover>
                    <PopoverTrigger asChild>
                      <Button variant="outline" className="w-full justify-start text-left font-normal">
                        <Calendar className="mr-2 h-4 w-4" />
                        {format(formData.data_fim, 'PPP', { locale: ptBR })}
                      </Button>
                    </PopoverTrigger>
                    <PopoverContent className="w-auto p-0">
                      <CalendarPicker mode="single" selected={formData.data_fim} onSelect={(date) => handleChange('data_fim', date)} initialFocus locale={ptBR} />
                    </PopoverContent>
                  </Popover>
                </div>
              </div>
              <div>
                <Label>Turma(s) Envolvida(s)</Label>
                <div className="flex flex-wrap gap-4 p-2 border rounded-md min-h-[40px]">
                  {loadingTurmas ? (
                    <div className="flex items-center text-sm text-gray-500">
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Carregando turmas...
                    </div>
                  ) : userTurmas.length > 0 ? (
                    userTurmas.map(turma => (
                      <div key={turma.id} className="flex items-center space-x-2">
                        <Checkbox id={`turma-${turma.id}`} checked={formData.turmas.includes(turma.id)} onCheckedChange={() => handleMultiSelectChange('turmas', turma.id)} />
                        <Label htmlFor={`turma-${turma.id}`}>{turma.nome}</Label>
                      </div>
                    ))
                  ) : (
                    <p className="text-sm text-gray-500">Nenhuma turma vinculada.</p>
                  )}
                </div>
              </div>
            </div>
            <div>
              <Label htmlFor="objetivo_pedagogico">Objetivo Pedagógico</Label>
              <Textarea id="objetivo_pedagogico" value={formData.objetivo_pedagogico} onChange={(e) => handleChange('objetivo_pedagogico', e.target.value)} />
              <div className="mt-2">
                {!showIaSuggestion ? (
                  <Button type="button" variant="ghost" size="sm" onClick={handleRequestIaSuggestion} className="text-roxo-principal hover:bg-lavanda-light">
                    <Sparkles className="h-4 w-4 mr-2" />
                    Pedir ajuda à IA para escrever o objetivo
                  </Button>
                ) : (
                  <AnimatePresence>
                    <ProjectIaSuggestionBox
                        suggestion={iaSuggestion}
                        onUse={useIaSuggestion}
                        onEdit={() => setShowIaSuggestion(false)}
                        onCancel={() => setShowIaSuggestion(false)}
                    />
                  </AnimatePresence>
                )}
              </div>
            </div>
            <div>
              <Label>Campos de Experiência (BNCC)</Label>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2 mt-2">
                {camposExperienciaOptions.map(campo => (
                  <div key={campo} className="flex items-center space-x-2">
                    <Checkbox id={`campo-${campo}`} checked={formData.campos_experiencia.includes(campo)} onCheckedChange={() => handleMultiSelectChange('campos_experiencia', campo)} />
                    <Label htmlFor={`campo-${campo}`}>{campo}</Label>
                  </div>
                ))}
              </div>
            </div>
            <div>
              <Label>Área(s) Envolvida(s)</Label>
              <div className="flex flex-wrap gap-2 mt-2">
                {areasEnvolvidasOptions.map(area => (
                  <Badge key={area} variant={formData.areas_envolvidas.includes(area) ? 'default' : 'secondary'} onClick={() => handleMultiSelectChange('areas_envolvidas', area)} className="cursor-pointer">{area}</Badge>
                ))}
              </div>
            </div>
          </CardContent>
          <CardFooter className="flex justify-end gap-2">
            <Button type="button" variant="ghost" onClick={onCancel}>Cancelar</Button>
            <Button type="submit" disabled={saving || loadingTurmas}>
              {saving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <CheckCircle className="mr-2 h-4 w-4" />}
              <span>{project?.id ? 'Salvar Alterações' : 'Salvar Projeto'}</span>
            </Button>
          </CardFooter>
        </Card>
      </form>
    </motion.div>
  );
};

export default ProjectForm;