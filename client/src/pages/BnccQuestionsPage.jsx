import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Helmet } from 'react-helmet-async';
import { apiClient } from '@/lib/apiClient';
import { useToast } from '@/components/ui/use-toast';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogFooter, DialogClose } from '@/components/ui/dialog';
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/accordion';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import {
  Loader2, PlusCircle, Edit, Trash2, FileUp, FileDown,
  ChevronsUpDown, ChevronsDownUp, Users, MessageCircle,
  Shapes, ToyBrick, Palette, ArrowLeft, BookOpen, Check,
  Settings, AlertTriangle
} from 'lucide-react';
import IconPicker, { getIconComponent } from '@/components/ui/icon-picker';

// Mapa de Campos de Experiência da BNCC
const campoExperienciaMap = {
  'O eu, o outro e o nós': { icon: Users, name: 'O eu, o outro e o nós' },
  'Escuta, fala, pensamento e imaginação': { icon: MessageCircle, name: 'Escuta, fala, pensamento e imaginação' },
  'Espaços, tempos, quantidades, relações e transformações': { icon: Shapes, name: 'Espaços, tempos, quantidades...' },
  'Corpo, gestos e movimentos': { icon: ToyBrick, name: 'Corpo, gestos e movimentos' },
  'Traços, sons, cores e formas': { icon: Palette, name: 'Traços, sons, cores e formas' },
};

// Níveis/faixas etárias padrão
const baseLevels = ['Nível 1', 'Nível 2', 'Nível 3', 'Nível 4', 'Nível 5'];

// Helper para obter CSRF token
const getCsrfToken = () => {
  const match = document.cookie.match(/csrftoken=([^;]+)/);
  return match ? match[1] : '';
};

const ensureCsrfToken = async () => {
  const existingToken = getCsrfToken();
  if (existingToken) return existingToken;

  try {
    await fetch('/api/auth/csrf/', { method: 'GET', credentials: 'include' });
  } catch (error) {
    console.warn('Não foi possível obter CSRF token:', error);
  }
  return getCsrfToken();
};

// Componente Creatable Select para Campo de Experiência com seleção de ícone
const CreatableCampoSelect = ({ value, onChange, existingCampos, customCampos = [], onCampoCreated }) => {
  const [inputValue, setInputValue] = useState('');
  const [isOpen, setIsOpen] = useState(false);
  const [showIconPicker, setShowIconPicker] = useState(false);
  const [newCampoName, setNewCampoName] = useState('');
  const [selectedIcon, setSelectedIcon] = useState('BookOpen');
  const [savingCampo, setSavingCampo] = useState(false);
  const { toast } = useToast();

  // Combinar campos padrão com campos existentes e customizados
  const allCampos = useMemo(() => {
    const customNames = (customCampos || []).map(c => c.nome);
    const usarCamposPadraoFallback = customNames.length === 0;
    const standardCampos = usarCamposPadraoFallback ? Object.keys(campoExperienciaMap) : [];
    const combined = new Set([...standardCampos, ...(existingCampos || []), ...customNames]);
    return Array.from(combined).sort();
  }, [existingCampos, customCampos]);

  // Mapa de ícones customizados
  const customIconMap = useMemo(() => {
    const map = {};
    (customCampos || []).forEach(c => {
      map[c.nome] = c.icone || 'BookOpen';
    });
    return map;
  }, [customCampos]);

  const filteredCampos = useMemo(() => {
    if (!inputValue) return allCampos;
    return allCampos.filter(campo =>
      campo.toLowerCase().includes(inputValue.toLowerCase())
    );
  }, [allCampos, inputValue]);

  const handleSelect = (campo) => {
    onChange(campo);
    setInputValue('');
    setIsOpen(false);
  };

  const handleStartCreateNew = () => {
    if (inputValue.trim()) {
      setNewCampoName(inputValue.trim());
      setSelectedIcon('BookOpen');
      setShowIconPicker(true);
      setIsOpen(false);
    }
  };

  const handleCreateNewCampo = async () => {
    if (!newCampoName.trim()) return;

    setSavingCampo(true);
    try {
      // Garantir que temos o CSRF token
      const csrfToken = await ensureCsrfToken();

      // Salvar o campo customizado na API
      const response = await fetch('/api/campos-experiencia/criar/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken,
        },
        credentials: 'include',
        body: JSON.stringify({
          nome: newCampoName.trim(),
          icone: selectedIcon,
        }),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.error || 'Erro ao criar campo');
      }

      const novoCampo = await response.json();

      toast({
        title: 'Campo criado!',
        description: `"${newCampoName}" foi adicionado com sucesso.`,
        className: 'bg-green-100'
      });

      // Notificar componente pai sobre o novo campo
      if (onCampoCreated) {
        onCampoCreated(novoCampo);
      }

      // Selecionar o novo campo
      onChange(newCampoName.trim());
      setShowIconPicker(false);
      setNewCampoName('');
      setInputValue('');
    } catch (error) {
      toast({
        title: 'Erro ao criar campo',
        description: error.message,
        variant: 'destructive'
      });
    } finally {
      setSavingCampo(false);
    }
  };

  const getIconForCampo = (campo) => {
    if (customIconMap[campo]) {
      return getIconComponent(customIconMap[campo]);
    }
    if (campoExperienciaMap[campo]) {
      return campoExperienciaMap[campo].icon;
    }
    return BookOpen;
  };

  return (
    <>
      <div className="relative">
        <div
          className="flex items-center justify-between w-full h-10 px-3 py-2 text-sm bg-white border rounded-md cursor-pointer border-input hover:bg-accent hover:text-accent-foreground"
          onClick={() => setIsOpen(!isOpen)}
        >
          {value ? (
            <span className="flex items-center gap-2 text-foreground">
              {React.createElement(getIconForCampo(value), { className: "h-4 w-4 text-purple-600" })}
              {value}
            </span>
          ) : (
            <span className="text-muted-foreground">
              Selecione ou digite um Campo de Experiência
            </span>
          )}
          <ChevronsUpDown className="h-4 w-4 opacity-50" />
        </div>

        {isOpen && (
          <div className="absolute z-50 w-full mt-1 bg-white border rounded-md shadow-lg max-h-60 overflow-auto">
            <div className="p-2 border-b">
              <Input
                placeholder="Buscar ou criar novo campo..."
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && inputValue.trim() && !allCampos.includes(inputValue.trim())) {
                    e.preventDefault();
                    handleStartCreateNew();
                  }
                }}
                className="h-8"
                autoFocus
              />
            </div>

            <div className="py-1">
              {filteredCampos.map((campo) => {
                const Icon = getIconForCampo(campo);
                return (
                  <div
                    key={campo}
                    className={`flex items-center gap-2 px-3 py-2 text-sm cursor-pointer hover:bg-purple-50 ${value === campo ? 'bg-purple-100 text-purple-800' : ''}`}
                    onClick={() => handleSelect(campo)}
                  >
                    <Icon className="h-4 w-4 text-purple-600" />
                    <span>{campo}</span>
                  </div>
                );
              })}

              {inputValue && !allCampos.includes(inputValue.trim()) && (
                <div
                  className="flex items-center gap-2 px-3 py-2 text-sm cursor-pointer hover:bg-green-50 border-t text-green-700"
                  onClick={handleStartCreateNew}
                >
                  <PlusCircle className="h-4 w-4" />
                  <span>Criar novo campo: "<strong>{inputValue}</strong>"</span>
                </div>
              )}

              {filteredCampos.length === 0 && !inputValue && (
                <div className="px-3 py-2 text-sm text-gray-500">
                  Nenhum campo encontrado
                </div>
              )}
            </div>
          </div>
        )}

        {isOpen && (
          <div
            className="fixed inset-0 z-40"
            onClick={() => {
              setIsOpen(false);
              setInputValue('');
            }}
          />
        )}
      </div>

      {/* Modal de seleção de ícone para novo campo */}
      <Dialog open={showIconPicker} onOpenChange={setShowIconPicker}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <PlusCircle className="h-5 w-5 text-green-600" />
              Criar novo Campo de Experiência
            </DialogTitle>
            <DialogDescription>
              Defina o nome e escolha um ícone para o novo campo de experiência.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            <div>
              <Label className="font-medium">Nome do campo</Label>
              <Input
                value={newCampoName}
                onChange={(e) => setNewCampoName(e.target.value)}
                className="mt-1"
                placeholder="Nome do campo de experiência"
              />
            </div>

            <div>
              <Label className="font-medium">Escolha um ícone</Label>
              <div className="mt-2">
                <IconPicker
                  selectedIcon={selectedIcon}
                  onSelect={setSelectedIcon}
                />
              </div>
            </div>

            <div className="p-3 bg-gray-50 rounded-lg">
              <p className="text-sm text-gray-600 mb-2">Prévia:</p>
              <div className="flex items-center gap-2">
                {React.createElement(getIconComponent(selectedIcon), { className: "h-5 w-5 text-purple-600" })}
                <span className="font-medium">{newCampoName || 'Nome do campo'}</span>
              </div>
            </div>
          </div>

          <DialogFooter>
            <Button variant="ghost" onClick={() => setShowIconPicker(false)}>
              Cancelar
            </Button>
            <Button onClick={handleCreateNewCampo} disabled={savingCampo || !newCampoName.trim()}>
              {savingCampo ? (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              ) : (
                <Check className="h-4 w-4 mr-2" />
              )}
              <span>Criar Campo</span>
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
};

// Formulário de Nova Pergunta BNCC
const NovaPerguntaForm = ({ isOpen, onClose, onSave, existingCampos, customCampos, onCampoCreated, educationLevels }) => {
  const [formData, setFormData] = useState({
    campo_experiencia: '',
    faixa_etaria: '',
    pergunta: '',
    pergunta_norma: '',
    habilidade_bncc: '',
    area_conhecimento: '',
  });
  const [saving, setSaving] = useState(false);
  const { toast } = useToast();

  const handleChange = (field, value) => {
    setFormData(prev => ({ ...prev, [field]: value }));
  };

  const handleSubmit = async () => {
    if (!formData.campo_experiencia || !formData.faixa_etaria || !formData.pergunta) {
      toast({
        title: 'Campos obrigatórios',
        description: 'Campo de Experiência, Nível e Pergunta são necessários.',
        variant: 'destructive'
      });
      return;
    }

    setSaving(true);
    try {
      const { data, error } = await apiClient
        .from('perguntas_bncc')
        .insert({
          campo_experiencia: formData.campo_experiencia,
          faixa_etaria: formData.faixa_etaria,
          pergunta: formData.pergunta.trim(),
          pergunta_norma: formData.pergunta_norma?.trim() || null,
          habilidade_bncc: formData.habilidade_bncc?.trim() || null,
          area_conhecimento: formData.area_conhecimento?.trim() || null,
        })
        .select()
        .single();

      if (error) throw error;

      toast({
        title: 'Pergunta criada com sucesso!',
        description: `A pergunta foi adicionada ao campo "${formData.campo_experiencia}".`,
        className: 'bg-green-100'
      });

      onSave(data);
      setFormData({
        campo_experiencia: '',
        faixa_etaria: '',
        pergunta: '',
        pergunta_norma: '',
        habilidade_bncc: '',
        area_conhecimento: '',
      });
      onClose();
    } catch (error) {
      toast({
        title: 'Erro ao criar pergunta',
        description: error.message,
        variant: 'destructive'
      });
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <PlusCircle className="h-5 w-5 text-purple-600" />
            Nova Pergunta BNCC
          </DialogTitle>
        </DialogHeader>

        <div className="grid gap-4 py-4">
          <div className="grid grid-cols-4 items-center gap-4">
            <Label htmlFor="campo_experiencia" className="text-right font-medium">
              Campo de Experiência *
            </Label>
            <div className="col-span-3">
              <CreatableCampoSelect
                value={formData.campo_experiencia}
                onChange={(value) => handleChange('campo_experiencia', value)}
                existingCampos={existingCampos}
                customCampos={customCampos}
                onCampoCreated={onCampoCreated}
              />
              <p className="text-xs text-gray-500 mt-1">
                Selecione um campo existente ou digite para criar um novo com ícone personalizado.
              </p>
            </div>
          </div>

          <div className="grid grid-cols-4 items-center gap-4">
            <Label htmlFor="faixa_etaria" className="text-right font-medium">
              Nível/Faixa Etária *
            </Label>
            <Select
              value={formData.faixa_etaria}
              onValueChange={(value) => handleChange('faixa_etaria', value)}
            >
              <SelectTrigger className="col-span-3">
                <SelectValue placeholder="Selecione o nível" />
              </SelectTrigger>
              <SelectContent>
                {educationLevels.map(level => (
                  <SelectItem key={level} value={level}>{level}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="grid grid-cols-4 items-start gap-4">
            <Label htmlFor="pergunta" className="text-right font-medium pt-2">
              Pergunta Facilitadora *
            </Label>
            <Textarea
              id="pergunta"
              value={formData.pergunta}
              onChange={(e) => handleChange('pergunta', e.target.value)}
              className="col-span-3"
              placeholder="Digite a pergunta facilitadora para observação pedagógica"
              rows={3}
            />
          </div>

          <div className="grid grid-cols-4 items-start gap-4">
            <Label htmlFor="pergunta_norma" className="text-right font-medium pt-2">
              Referência da Norma BNCC
            </Label>
            <Textarea
              id="pergunta_norma"
              value={formData.pergunta_norma}
              onChange={(e) => handleChange('pergunta_norma', e.target.value)}
              className="col-span-3"
              placeholder="Texto original da norma BNCC (opcional)"
              rows={2}
            />
          </div>

          <div className="grid grid-cols-4 items-center gap-4">
            <Label htmlFor="habilidade_bncc" className="text-right font-medium">
              Código Habilidade
            </Label>
            <Input
              id="habilidade_bncc"
              value={formData.habilidade_bncc}
              onChange={(e) => handleChange('habilidade_bncc', e.target.value)}
              className="col-span-3"
              placeholder="Ex: EI03EO01"
            />
          </div>

          <div className="grid grid-cols-4 items-center gap-4">
            <Label htmlFor="area_conhecimento" className="text-right font-medium">
              Área do Conhecimento
            </Label>
            <Input
              id="area_conhecimento"
              value={formData.area_conhecimento}
              onChange={(e) => handleChange('area_conhecimento', e.target.value)}
              className="col-span-3"
              placeholder="Ex: Linguagens, Matemática..."
            />
          </div>
        </div>

        <DialogFooter>
          <DialogClose asChild>
            <Button variant="ghost">Cancelar</Button>
          </DialogClose>
          <Button onClick={handleSubmit} disabled={saving}>
            {saving && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
            Salvar Pergunta
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

// Formulário de Edição de Pergunta BNCC
const EditarPerguntaForm = ({ isOpen, onClose, pergunta, onSave, existingCampos, customCampos, onCampoCreated, educationLevels }) => {
  const [formData, setFormData] = useState({});
  const [saving, setSaving] = useState(false);
  const { toast } = useToast();

  useEffect(() => {
    if (pergunta) {
      setFormData({
        campo_experiencia: pergunta.campo_experiencia || '',
        faixa_etaria: pergunta.faixa_etaria || '',
        pergunta: pergunta.pergunta || '',
        pergunta_norma: pergunta.pergunta_norma || '',
        habilidade_bncc: pergunta.habilidade_bncc || '',
        area_conhecimento: pergunta.area_conhecimento || '',
      });
    }
  }, [pergunta]);

  const handleChange = (field, value) => {
    setFormData(prev => ({ ...prev, [field]: value }));
  };

  const handleSubmit = async () => {
    if (!formData.campo_experiencia || !formData.faixa_etaria || !formData.pergunta) {
      toast({
        title: 'Campos obrigatórios',
        description: 'Campo de Experiência, Nível e Pergunta são necessários.',
        variant: 'destructive'
      });
      return;
    }

    setSaving(true);
    try {
      const { data, error } = await apiClient
        .from('perguntas_bncc')
        .update({
          campo_experiencia: formData.campo_experiencia,
          faixa_etaria: formData.faixa_etaria,
          pergunta: formData.pergunta.trim(),
          pergunta_norma: formData.pergunta_norma?.trim() || null,
          habilidade_bncc: formData.habilidade_bncc?.trim() || null,
          area_conhecimento: formData.area_conhecimento?.trim() || null,
        })
        .eq('id', pergunta.id)
        .select()
        .single();

      if (error) throw error;

      toast({
        title: 'Pergunta atualizada!',
        className: 'bg-green-100'
      });

      onSave(data);
      onClose();
    } catch (error) {
      toast({
        title: 'Erro ao atualizar pergunta',
        description: error.message,
        variant: 'destructive'
      });
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Edit className="h-5 w-5 text-purple-600" />
            Editar Pergunta BNCC
          </DialogTitle>
        </DialogHeader>

        <div className="grid gap-4 py-4">
          <div className="grid grid-cols-4 items-center gap-4">
            <Label className="text-right font-medium">Campo de Experiência *</Label>
            <div className="col-span-3">
              <CreatableCampoSelect
                value={formData.campo_experiencia}
                onChange={(value) => handleChange('campo_experiencia', value)}
                existingCampos={existingCampos}
                customCampos={customCampos}
                onCampoCreated={onCampoCreated}
              />
            </div>
          </div>

          <div className="grid grid-cols-4 items-center gap-4">
            <Label className="text-right font-medium">Nível/Faixa Etária *</Label>
            <Select
              value={formData.faixa_etaria}
              onValueChange={(value) => handleChange('faixa_etaria', value)}
            >
              <SelectTrigger className="col-span-3">
                <SelectValue placeholder="Selecione o nível" />
              </SelectTrigger>
              <SelectContent>
                {educationLevels.map(level => (
                  <SelectItem key={level} value={level}>{level}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="grid grid-cols-4 items-start gap-4">
            <Label className="text-right font-medium pt-2">Pergunta Facilitadora *</Label>
            <Textarea
              value={formData.pergunta}
              onChange={(e) => handleChange('pergunta', e.target.value)}
              className="col-span-3"
              rows={3}
            />
          </div>

          <div className="grid grid-cols-4 items-start gap-4">
            <Label className="text-right font-medium pt-2">Referência da Norma</Label>
            <Textarea
              value={formData.pergunta_norma}
              onChange={(e) => handleChange('pergunta_norma', e.target.value)}
              className="col-span-3"
              rows={2}
            />
          </div>

          <div className="grid grid-cols-4 items-center gap-4">
            <Label className="text-right font-medium">Código Habilidade</Label>
            <Input
              value={formData.habilidade_bncc}
              onChange={(e) => handleChange('habilidade_bncc', e.target.value)}
              className="col-span-3"
            />
          </div>

          <div className="grid grid-cols-4 items-center gap-4">
            <Label className="text-right font-medium">Área do Conhecimento</Label>
            <Input
              value={formData.area_conhecimento}
              onChange={(e) => handleChange('area_conhecimento', e.target.value)}
              className="col-span-3"
            />
          </div>
        </div>

        <DialogFooter>
          <DialogClose asChild>
            <Button variant="ghost">Cancelar</Button>
          </DialogClose>
          <Button onClick={handleSubmit} disabled={saving}>
            {saving && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
            Salvar Alterações
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

const BnccQuestionsPage = () => {
  const navigate = useNavigate();
  const { toast } = useToast();

  const [perguntas, setPerguntas] = useState([]);
  const [customCampos, setCustomCampos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [nivelFilter, setNivelFilter] = useState('');
  const [campoFilter, setCampoFilter] = useState('');
  const [expanded, setExpanded] = useState([]);

  const [isNewModalOpen, setIsNewModalOpen] = useState(false);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [editingPergunta, setEditingPergunta] = useState(null);
  const [deleteConfirmId, setDeleteConfirmId] = useState(null);
  const [isCampoManagerOpen, setIsCampoManagerOpen] = useState(false);
  const [isCampoCreateOpen, setIsCampoCreateOpen] = useState(false);
  const [campoCreateForm, setCampoCreateForm] = useState({ nome: '', icone: 'BookOpen' });
  const [creatingCampo, setCreatingCampo] = useState(false);
  const [isCampoEditOpen, setIsCampoEditOpen] = useState(false);
  const [editingCampo, setEditingCampo] = useState(null);
  const [campoForm, setCampoForm] = useState({ nome: '', icone: 'BookOpen' });
  const [savingCampo, setSavingCampo] = useState(false);
  const [isCampoDeleteOpen, setIsCampoDeleteOpen] = useState(false);
  const [deletingCampo, setDeletingCampo] = useState(null);
  const [remapTarget, setRemapTarget] = useState('');
  const [deletingCampoLoading, setDeletingCampoLoading] = useState(false);
  const [seriesConfig, setSeriesConfig] = useState([]);

  useEffect(() => {
    apiClient.from('series_config').select('*').eq('ativa', true).then(({ data, error }) => {
      if (error) {
        console.error('Erro ao carregar configurações de séries:', error);
      } else {
        setSeriesConfig(data?.length ? data : []);
      }
    });
  }, []);

  // Carregar campos de experiência customizados
  const fetchCamposCustomizados = useCallback(async () => {
    try {
      const response = await fetch('/api/campos-experiencia/?ativo=true', {
        credentials: 'include',
      });
      if (response.ok) {
        const data = await response.json();
        setCustomCampos(data);
      }
    } catch (error) {
      console.error('Erro ao carregar campos customizados:', error);
    }
  }, []);

  const handleCampoCreated = useCallback((novoCampo) => {
    setCustomCampos(prev => [...prev, novoCampo]);
  }, []);

  const fetchPerguntas = useCallback(async () => {
    setLoading(true);
    const { data, error } = await apiClient
      .from('perguntas_bncc')
      .select('*')
      .order('campo_experiencia', { ascending: true })
      .order('faixa_etaria', { ascending: true });

    if (error) {
      toast({ title: 'Erro ao buscar perguntas', description: error.message, variant: 'destructive' });
    } else {
      setPerguntas(data || []);
      const allCampos = [...new Set((data || []).map(p => p.campo_experiencia))];
      setExpanded(allCampos);
    }
    setLoading(false);
  }, [toast]);

  useEffect(() => {
    fetchPerguntas();
    fetchCamposCustomizados();
  }, [fetchPerguntas, fetchCamposCustomizados]);

  // Campos de experiência existentes (incluindo novos criados)
  const existingCampos = useMemo(() => {
    return [...new Set(perguntas.map(p => p.campo_experiencia).filter(Boolean))];
  }, [perguntas]);

  // Níveis de educação existentes
  const educationLevels = useMemo(() => {
    if (seriesConfig.length > 0) {
      // Ordena pelo campo `ordem` do backend e extrai os nomes
      const ordenados = [...seriesConfig].sort((a, b) => (a.ordem ?? 999) - (b.ordem ?? 999));
      const nomesOrdenados = ordenados.map(s => s.nome);
      // Adiciona ao final quaisquer faixas usadas em perguntas mas não cadastradas em series_config
      const nomeSet = new Set(nomesOrdenados);
      const fromPerguntas = [...new Set(perguntas.map(p => p.faixa_etaria).filter(Boolean))];
      fromPerguntas.forEach(n => { if (!nomeSet.has(n)) nomesOrdenados.push(n); });
      return nomesOrdenados;
    }
    // Fallback: hardcoded + valores das perguntas, ordenados por número
    const fromPerguntas = [...new Set(perguntas.map(p => p.faixa_etaria).filter(Boolean))];
    const combined = new Set([...baseLevels, ...fromPerguntas]);
    return Array.from(combined).sort((a, b) => {
      const aNum = parseInt(a.match(/\d+/)?.[0] || '99');
      const bNum = parseInt(b.match(/\d+/)?.[0] || '99');
      return aNum - bNum;
    });
  }, [perguntas, seriesConfig]);

  const filteredPerguntas = useMemo(() => {
    return perguntas.filter(p => {
      const nivelMatch = !nivelFilter || nivelFilter === 'all-levels' || p.faixa_etaria.includes(nivelFilter.replace('Nível ', ''));
      const campoMatch = !campoFilter || campoFilter === 'all-fields' || p.campo_experiencia === campoFilter;
      return nivelMatch && campoMatch;
    });
  }, [perguntas, nivelFilter, campoFilter]);

  const groupedPerguntas = useMemo(() => {
    return filteredPerguntas.reduce((acc, p) => {
      const campo = p.campo_experiencia;
      if (!acc[campo]) acc[campo] = [];
      acc[campo].push(p);
      return acc;
    }, {});
  }, [filteredPerguntas]);

  const customCamposWithUsage = useMemo(() => {
    const usageMap = perguntas.reduce((acc, p) => {
      const campo = p.campo_experiencia;
      if (!campo) return acc;
      acc[campo] = (acc[campo] || 0) + 1;
      return acc;
    }, {});

    return (customCampos || [])
      .map(campo => ({
        ...campo,
        total_perguntas: usageMap[campo.nome] || 0,
      }))
      .sort((a, b) => a.nome.localeCompare(b.nome, 'pt-BR', { sensitivity: 'base' }));
  }, [customCampos, perguntas]);

  const customIconMap = useMemo(() => {
    const map = {};
    (customCampos || []).forEach(campo => {
      if (!campo?.nome) return;
      map[campo.nome] = campo.icone || 'BookOpen';
    });
    return map;
  }, [customCampos]);

  const remapCampoOptions = useMemo(() => {
    const customNomes = (customCampos || []).map(campo => campo.nome);
    const usarCamposPadraoFallback = customNomes.length === 0;
    const nomes = new Set([
      ...existingCampos,
      ...customNomes,
      ...(usarCamposPadraoFallback ? Object.keys(campoExperienciaMap) : []),
    ]);
    if (deletingCampo?.nome) {
      nomes.delete(deletingCampo.nome);
    }
    return Array.from(nomes).sort((a, b) => a.localeCompare(b, 'pt-BR', { sensitivity: 'base' }));
  }, [existingCampos, customCampos, deletingCampo]);

  const resolveCampoIcon = (campoNome, iconePersonalizado) => {
    if (iconePersonalizado) {
      return getIconComponent(iconePersonalizado);
    }
    if (campoExperienciaMap[campoNome]) {
      return campoExperienciaMap[campoNome].icon;
    }
    return BookOpen;
  };

  const handleExpandAll = () => {
    setExpanded(Object.keys(groupedPerguntas));
  };

  const handleCollapseAll = () => {
    setExpanded([]);
  };

  const resetCampoCreate = () => {
    setCampoCreateForm({ nome: '', icone: 'BookOpen' });
    setIsCampoCreateOpen(false);
    setCreatingCampo(false);
  };

  const handleCreateCampo = async () => {
    const nome = campoCreateForm.nome?.trim();
    if (!nome) {
      toast({
        title: 'Nome obrigatório',
        description: 'Informe o nome do campo de experiência.',
        variant: 'destructive',
      });
      return;
    }

    setCreatingCampo(true);
    try {
      const csrfToken = await ensureCsrfToken();
      const response = await fetch('/api/campos-experiencia/criar/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken,
        },
        credentials: 'include',
        body: JSON.stringify({
          nome,
          icone: campoCreateForm.icone || 'BookOpen',
        }),
      });

      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload?.error || 'Erro ao criar campo');
      }

      toast({
        title: 'Campo criado!',
        description: `"${nome}" foi adicionado com sucesso.`,
        className: 'bg-green-100',
      });

      resetCampoCreate();
      fetchCamposCustomizados();
      fetchPerguntas();
    } catch (error) {
      toast({
        title: 'Erro ao criar campo',
        description: error.message,
        variant: 'destructive',
      });
    } finally {
      setCreatingCampo(false);
    }
  };

  const openCampoEdit = (campo) => {
    if (!campo) return;
    setEditingCampo(campo);
    setCampoForm({
      nome: campo.nome || '',
      icone: campo.icone || 'BookOpen',
    });
    setIsCampoEditOpen(true);
  };

  const handleSaveCampo = async () => {
    if (!editingCampo) return;
    const nome = campoForm.nome?.trim();
    if (!nome) {
      toast({
        title: 'Nome obrigatório',
        description: 'Informe o nome do campo de experiência.',
        variant: 'destructive'
      });
      return;
    }

    setSavingCampo(true);
    try {
      const csrfToken = await ensureCsrfToken();
      const response = await fetch(`/api/campos-experiencia/${editingCampo.id}/atualizar/`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken,
        },
        credentials: 'include',
        body: JSON.stringify({
          nome,
          icone: campoForm.icone || 'BookOpen',
        }),
      });

      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload?.error || 'Erro ao atualizar campo');
      }

      const totalAtualizadas = payload?.perguntas_atualizadas || 0;
      toast({
        title: 'Campo atualizado!',
        description: totalAtualizadas > 0
          ? `${totalAtualizadas} pergunta(s) atualizada(s).`
          : 'Alterações salvas com sucesso.',
        className: 'bg-green-100',
      });

      setIsCampoEditOpen(false);
      setEditingCampo(null);
      fetchCamposCustomizados();
      fetchPerguntas();
    } catch (error) {
      toast({
        title: 'Erro ao atualizar campo',
        description: error.message,
        variant: 'destructive',
      });
    } finally {
      setSavingCampo(false);
    }
  };

  const openCampoDelete = (campo) => {
    if (!campo) return;
    setDeletingCampo(campo);
    setRemapTarget('');
    setIsCampoDeleteOpen(true);
  };

  const handleDeleteCampo = async () => {
    if (!deletingCampo) return;
    const precisaRemapeamento = (deletingCampo.total_perguntas || 0) > 0;
    if (precisaRemapeamento && !remapTarget) {
      toast({
        title: 'Remanejamento necessário',
        description: 'Selecione o campo de destino para remanejar as perguntas vinculadas.',
        variant: 'destructive',
      });
      return;
    }

    setDeletingCampoLoading(true);
    try {
      const csrfToken = await ensureCsrfToken();
      const response = await fetch(`/api/campos-experiencia/${deletingCampo.id}/deletar/`, {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken,
        },
        credentials: 'include',
        body: JSON.stringify({
          remanejar_para: remapTarget || null,
        }),
      });

      const payload = await response.json();
      if (!response.ok) {
        if (response.status === 409 && payload?.total_vinculos) {
          toast({
            title: 'Campo com perguntas vinculadas',
            description: `Existem ${payload.total_vinculos} pergunta(s) vinculada(s). Selecione um campo de destino para remanejar.`,
            variant: 'destructive',
          });
          return;
        }
        throw new Error(payload?.error || 'Erro ao excluir campo');
      }

      const totalRemanejadas = payload?.perguntas_remanejadas || 0;
      toast({
        title: 'Campo desativado',
        description: totalRemanejadas > 0
          ? `${totalRemanejadas} pergunta(s) remanejada(s).`
          : 'Campo removido com sucesso.',
      });

      setIsCampoDeleteOpen(false);
      setDeletingCampo(null);
      setRemapTarget('');
      fetchCamposCustomizados();
      fetchPerguntas();
    } catch (error) {
      toast({
        title: 'Erro ao excluir campo',
        description: error.message,
        variant: 'destructive',
      });
    } finally {
      setDeletingCampoLoading(false);
    }
  };

  const handleExportCSV = () => {
    if (filteredPerguntas.length === 0) {
      toast({ title: 'Nenhuma pergunta para exportar', description: 'Altere os filtros para selecionar perguntas.', variant: 'destructive' });
      return;
    }
    const headers = ['faixa_etaria', 'campo_experiencia', 'area_conhecimento', 'pergunta', 'pergunta_norma', 'habilidade_bncc'];
    const csvContent = [
      headers.join(','),
      ...filteredPerguntas.map(p => headers.map(header => `"${(p[header] || '').replace(/"/g, '""')}"`).join(','))
    ].join('\n');

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);
    link.setAttribute('href', url);
    link.setAttribute('download', 'perguntas_bncc.csv');
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    toast({ title: 'Exportação concluída!', description: `${filteredPerguntas.length} perguntas exportadas.` });
  };

  const handleDeletePergunta = async (id) => {
    const { error } = await apiClient
      .from('perguntas_bncc')
      .delete()
      .eq('id', id);

    if (error) {
      toast({ title: 'Erro ao excluir', description: error.message, variant: 'destructive' });
    } else {
      toast({ title: 'Pergunta excluída com sucesso!' });
      fetchPerguntas();
    }
    setDeleteConfirmId(null);
  };

  const handleEditClick = (pergunta) => {
    setEditingPergunta(pergunta);
    setIsEditModalOpen(true);
  };

  const handleSaveNew = () => {
    fetchPerguntas();
  };

  const handleSaveEdit = () => {
    fetchPerguntas();
    setEditingPergunta(null);
  };

  return (
    <>
      <Helmet>
        <title>NARA - Gestão de Perguntas BNCC</title>
        <meta name="description" content="Gerencie as perguntas pedagógicas baseadas na BNCC." />
      </Helmet>

      <div className="bg-[#F5F3FA] min-h-screen">
        <header className="bg-white/80 backdrop-blur-sm shadow-sm sticky top-0 z-10">
          <div className="container mx-auto px-4 sm:px-6 lg:px-8 py-4 flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Button variant="ghost" size="icon" onClick={() => navigate('/admin/perguntas')}>
                <ArrowLeft className="h-6 w-6" />
              </Button>
              <div>
                <h1 className="text-xl font-bold text-gray-800">Gestão de Perguntas BNCC</h1>
                <p className="text-sm text-gray-500">Administre as perguntas pedagógicas por Campo de Experiência</p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Button variant="outline" onClick={() => setIsCampoManagerOpen(true)}>
                <Settings className="h-4 w-4 mr-2" />
                Gerenciar Campos
              </Button>
              <Button onClick={() => setIsNewModalOpen(true)}>
                <PlusCircle className="h-4 w-4 mr-2" />
                Nova Pergunta
              </Button>
            </div>
          </div>
        </header>

        <main className="container mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <Card className="shadow-lg">
            <CardHeader>
              <CardTitle>Perguntas da BNCC</CardTitle>
              <CardDescription>
                <span>{filteredPerguntas.length} pergunta(s) encontrada(s)</span>
                {(nivelFilter || campoFilter) && <span> com os filtros aplicados</span>}
              </CardDescription>
            </CardHeader>
            <CardContent>
              {/* Filtros e Ações */}
              <div className="space-y-4 mb-6">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <Select value={nivelFilter} onValueChange={(value) => setNivelFilter(value === 'all-levels' ? '' : value)}>
                    <SelectTrigger>
                      <SelectValue placeholder="Filtrar por Nível/Faixa Etária" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all-levels">Todos os Níveis</SelectItem>
                      {educationLevels.map(n => <SelectItem key={n} value={n}>{n}</SelectItem>)}
                    </SelectContent>
                  </Select>

                  <Select value={campoFilter} onValueChange={(value) => setCampoFilter(value === 'all-fields' ? '' : value)}>
                    <SelectTrigger>
                      <SelectValue placeholder="Filtrar por Campo de Experiência" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all-fields">Todos os Campos</SelectItem>
                      {existingCampos.map(campo => (
                        <SelectItem key={campo} value={campo}>
                          {campoExperienciaMap[campo]?.name || campo}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="flex flex-wrap items-center gap-2">
                  <Button variant="outline" size="sm" onClick={handleExpandAll}>
                    <ChevronsUpDown className="h-4 w-4 mr-2" />Expandir Tudo
                  </Button>
                  <Button variant="outline" size="sm" onClick={handleCollapseAll}>
                    <ChevronsDownUp className="h-4 w-4 mr-2" />Recolher Tudo
                  </Button>
                  <Button variant="outline" size="sm" onClick={() => toast({ title: 'Funcionalidade em breve!' })}>
                    <FileUp className="h-4 w-4 mr-2" />Importar CSV
                  </Button>
                  <Button variant="outline" size="sm" onClick={handleExportCSV}>
                    <FileDown className="h-4 w-4 mr-2" />Exportar CSV
                  </Button>
                </div>
              </div>

              {/* Lista de Perguntas */}
              {loading ? (
                <div className="flex justify-center items-center h-64">
                  <Loader2 className="h-8 w-8 animate-spin text-purple-500" />
                </div>
              ) : Object.keys(groupedPerguntas).length === 0 ? (
                <div className="text-center py-12 text-gray-500">
                  <BookOpen className="h-12 w-12 mx-auto mb-4 text-gray-300" />
                  <p>Nenhuma pergunta encontrada.</p>
                  <Button className="mt-4" onClick={() => setIsNewModalOpen(true)}>
                    <PlusCircle className="h-4 w-4 mr-2" />
                    Criar primeira pergunta
                  </Button>
                </div>
              ) : (
                <Accordion type="multiple" value={expanded} onValueChange={setExpanded}>
                  {Object.entries(groupedPerguntas).map(([campo, perguntasDoCampo]) => {
                    const Icon = resolveCampoIcon(campo, customIconMap[campo]);
                    return (
                      <AccordionItem key={campo} value={campo}>
                        <AccordionTrigger className="text-lg font-bold text-purple-700 hover:no-underline">
                          <div className="flex items-center gap-3">
                            <Icon className="h-6 w-6" />
                            <span>{campoExperienciaMap[campo]?.name || campo}</span>
                            <span className="text-sm font-normal text-gray-500">
                              ({perguntasDoCampo.length} pergunta{perguntasDoCampo.length !== 1 ? 's' : ''})
                            </span>
                          </div>
                        </AccordionTrigger>
                        <AccordionContent>
                          <div className="space-y-3 pl-9">
                            {perguntasDoCampo.map(p => (
                              <div key={p.id} className="p-4 bg-gray-50 rounded-lg border hover:border-purple-200 transition-colors">
                                <div className="flex items-start justify-between gap-4">
                                  <div className="flex-1">
                                    <p className="font-semibold text-gray-800">{p.pergunta}</p>
                                    {p.pergunta_norma && (
                                      <div className="mt-2 p-2 bg-blue-50 border-l-2 border-blue-400 rounded">
                                        <p className="text-xs text-blue-600 font-medium">Referência na Norma BNCC:</p>
                                        <p className="text-sm text-blue-800">{p.pergunta_norma}</p>
                                      </div>
                                    )}
                                    <div className="flex flex-wrap items-center gap-2 text-xs text-gray-500 mt-2">
                                      <span className="font-medium bg-purple-100 text-purple-800 px-2 py-0.5 rounded">
                                        {p.faixa_etaria}
                                      </span>
                                      {p.habilidade_bncc && (
                                        <span className="font-mono bg-green-100 text-green-800 px-2 py-0.5 rounded">
                                          {p.habilidade_bncc}
                                        </span>
                                      )}
                                      {p.area_conhecimento && (
                                        <span className="bg-gray-100 text-gray-700 px-2 py-0.5 rounded">
                                          {p.area_conhecimento}
                                        </span>
                                      )}
                                    </div>
                                  </div>
                                  <div className="flex items-center gap-1">
                                    <Button
                                      variant="ghost"
                                      size="icon"
                                      onClick={() => handleEditClick(p)}
                                      title="Editar"
                                    >
                                      <Edit className="h-4 w-4 text-gray-500 hover:text-purple-600" />
                                    </Button>
                                    <Button
                                      variant="ghost"
                                      size="icon"
                                      onClick={() => setDeleteConfirmId(p.id)}
                                      title="Excluir"
                                    >
                                      <Trash2 className="h-4 w-4 text-gray-500 hover:text-red-600" />
                                    </Button>
                                  </div>
                                </div>
                              </div>
                            ))}
                          </div>
                        </AccordionContent>
                      </AccordionItem>
                    );
                  })}
                </Accordion>
              )}
            </CardContent>
          </Card>
        </main>
      </div>

      {/* Modal de Gerenciamento de Campos */}
      <Dialog
        open={isCampoManagerOpen}
        onOpenChange={(open) => {
          setIsCampoManagerOpen(open);
          if (!open) {
            resetCampoCreate();
          }
        }}
      >
        <DialogContent className="max-w-3xl">
          <DialogHeader>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <DialogTitle className="flex items-center gap-2">
                <Settings className="h-5 w-5 text-purple-600" />
                Gerenciar Campos de Experiência
              </DialogTitle>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setIsCampoCreateOpen(prev => !prev)}
              >
                <PlusCircle className="h-4 w-4 mr-2" />
                {isCampoCreateOpen ? 'Ocultar' : 'Novo Campo'}
              </Button>
            </div>
            <DialogDescription>
              Crie, edite ou desative campos de experiência disponíveis para as perguntas.
            </DialogDescription>
          </DialogHeader>
          {isCampoCreateOpen && (
            <div className="p-4 border rounded-lg bg-white">
              <div className="grid gap-4">
                <div>
                  <Label className="font-medium">Nome do campo</Label>
                  <Input
                    value={campoCreateForm.nome}
                    onChange={(e) => setCampoCreateForm(prev => ({ ...prev, nome: e.target.value }))}
                    className="mt-1"
                    placeholder="Nome do campo de experiência"
                  />
                </div>

                <div>
                  <Label className="font-medium">Escolha um ícone</Label>
                  <div className="mt-2">
                    <IconPicker
                      selectedIcon={campoCreateForm.icone}
                      onSelect={(value) => setCampoCreateForm(prev => ({ ...prev, icone: value }))}
                    />
                  </div>
                </div>

                <div className="p-3 bg-gray-50 rounded-lg">
                  <p className="text-sm text-gray-600 mb-2">Prévia:</p>
                  <div className="flex items-center gap-2">
                    {React.createElement(getIconComponent(campoCreateForm.icone), { className: "h-5 w-5 text-purple-600" })}
                    <span className="font-medium">{campoCreateForm.nome || 'Nome do campo'}</span>
                  </div>
                </div>

                <div className="flex items-center justify-end gap-2">
                  <Button variant="ghost" onClick={resetCampoCreate}>
                    Cancelar
                  </Button>
                  <Button onClick={handleCreateCampo} disabled={creatingCampo || !campoCreateForm.nome.trim()}>
                    {creatingCampo ? (
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    ) : (
                      <Check className="h-4 w-4 mr-2" />
                    )}
                    Criar Campo
                  </Button>
                </div>
              </div>
            </div>
          )}
          {customCamposWithUsage.length === 0 ? (
            <div className="text-sm text-gray-600 py-6 text-center">
              Nenhum campo ativo encontrado. Crie um novo campo para disponibilizar nas perguntas.
            </div>
          ) : (
            <div className="space-y-3 max-h-[60vh] overflow-auto pr-1">
              {customCamposWithUsage.map((campo) => {
                const Icon = resolveCampoIcon(campo.nome, campo.icone);
                return (
                  <div key={campo.id} className="flex items-center justify-between gap-4 p-3 border rounded-lg bg-gray-50">
                    <div className="flex items-center gap-3">
                      {React.createElement(Icon, { className: "h-5 w-5 text-purple-600" })}
                      <div>
                        <p className="font-medium text-gray-800">{campo.nome}</p>
                        <p className="text-xs text-gray-500">
                          {campo.total_perguntas} pergunta(s) vinculada(s)
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-1">
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => openCampoEdit(campo)}
                        title="Editar campo"
                      >
                        <Edit className="h-4 w-4 text-gray-600" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => openCampoDelete(campo)}
                        title="Excluir campo"
                      >
                        <Trash2 className="h-4 w-4 text-gray-600 hover:text-red-600" />
                      </Button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
          <DialogFooter>
            <DialogClose asChild>
              <Button variant="outline">Fechar</Button>
            </DialogClose>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Modal de Edição de Campo */}
      <Dialog
        open={isCampoEditOpen}
        onOpenChange={(open) => {
          setIsCampoEditOpen(open);
          if (!open) {
            setEditingCampo(null);
            setCampoForm({ nome: '', icone: 'BookOpen' });
          }
        }}
      >
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Edit className="h-5 w-5 text-purple-600" />
              Editar Campo de Experiência
            </DialogTitle>
            <DialogDescription>
              Atualize o nome e o ícone do campo. As perguntas vinculadas serão ajustadas automaticamente.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            <div>
              <Label className="font-medium">Nome do campo</Label>
              <Input
                value={campoForm.nome}
                onChange={(e) => setCampoForm(prev => ({ ...prev, nome: e.target.value }))}
                className="mt-1"
                placeholder="Nome do campo de experiência"
              />
            </div>

            <div>
              <Label className="font-medium">Escolha um ícone</Label>
              <div className="mt-2">
                <IconPicker
                  selectedIcon={campoForm.icone}
                  onSelect={(value) => setCampoForm(prev => ({ ...prev, icone: value }))}
                />
              </div>
            </div>

            <div className="p-3 bg-gray-50 rounded-lg">
              <p className="text-sm text-gray-600 mb-2">Prévia:</p>
              <div className="flex items-center gap-2">
                {React.createElement(getIconComponent(campoForm.icone), { className: "h-5 w-5 text-purple-600" })}
                <span className="font-medium">{campoForm.nome || 'Nome do campo'}</span>
              </div>
            </div>

            {editingCampo?.total_perguntas > 0 && (
              <div className="text-xs text-gray-500">
                Esta alteração atualizará {editingCampo.total_perguntas} pergunta(s) vinculada(s).
              </div>
            )}
          </div>

          <DialogFooter>
            <Button variant="ghost" onClick={() => setIsCampoEditOpen(false)}>
              Cancelar
            </Button>
            <Button onClick={handleSaveCampo} disabled={savingCampo}>
              {savingCampo ? (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              ) : (
                <Check className="h-4 w-4 mr-2" />
              )}
              <span>Salvar Alterações</span>
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Dialog de Exclusão de Campo */}
      <Dialog
        open={isCampoDeleteOpen}
        onOpenChange={(open) => {
          setIsCampoDeleteOpen(open);
          if (!open) {
            setDeletingCampo(null);
            setRemapTarget('');
          }
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Trash2 className="h-5 w-5 text-red-600" />
              Excluir Campo de Experiência
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <p className="text-gray-600">
              Tem certeza que deseja desativar o campo <strong>{deletingCampo?.nome}</strong>?
            </p>
            {deletingCampo?.total_perguntas > 0 && (
              <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg text-sm text-amber-800 flex items-start gap-2">
                <AlertTriangle className="h-4 w-4 mt-0.5" />
                <span>
                  Existem {deletingCampo.total_perguntas} pergunta(s) vinculada(s). Selecione um campo de destino para remanejamento.
                </span>
              </div>
            )}
            {deletingCampo?.total_perguntas > 0 && (
              <div className="space-y-2">
                <Label className="font-medium">Remanejar perguntas para</Label>
                <Select value={remapTarget} onValueChange={setRemapTarget}>
                  <SelectTrigger>
                    <SelectValue placeholder="Selecione o campo de destino" />
                  </SelectTrigger>
                  <SelectContent>
                    {remapCampoOptions.map((nome) => (
                      <SelectItem key={nome} value={nome}>{nome}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsCampoDeleteOpen(false)}>
              Cancelar
            </Button>
            <Button
              variant="destructive"
              onClick={handleDeleteCampo}
              disabled={deletingCampoLoading || (deletingCampo?.total_perguntas > 0 && !remapTarget)}
            >
              {deletingCampoLoading && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
              Excluir
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Modal de Nova Pergunta */}
      <NovaPerguntaForm
        isOpen={isNewModalOpen}
        onClose={() => setIsNewModalOpen(false)}
        onSave={handleSaveNew}
        existingCampos={existingCampos}
        customCampos={customCampos}
        onCampoCreated={handleCampoCreated}
        educationLevels={educationLevels}
      />

      {/* Modal de Edição */}
      <EditarPerguntaForm
        isOpen={isEditModalOpen}
        onClose={() => {
          setIsEditModalOpen(false);
          setEditingPergunta(null);
        }}
        pergunta={editingPergunta}
        onSave={handleSaveEdit}
        existingCampos={existingCampos}
        customCampos={customCampos}
        onCampoCreated={handleCampoCreated}
        educationLevels={educationLevels}
      />

      {/* Dialog de Confirmação de Exclusão */}
      <Dialog open={!!deleteConfirmId} onOpenChange={() => setDeleteConfirmId(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Confirmar Exclusão</DialogTitle>
          </DialogHeader>
          <p className="text-gray-600">
            Tem certeza que deseja excluir esta pergunta? Esta ação não pode ser desfeita.
          </p>
          <DialogFooter>
            <DialogClose asChild>
              <Button variant="outline">Cancelar</Button>
            </DialogClose>
            <Button variant="destructive" onClick={() => handleDeletePergunta(deleteConfirmId)}>
              Excluir
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
};

export default BnccQuestionsPage;
