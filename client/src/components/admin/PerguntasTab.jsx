import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiClient } from '@/lib/apiClient';
import { useToast } from '@/components/ui/use-toast';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger, DialogFooter, DialogClose } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Loader2, PlusCircle, Edit, Trash2, ExternalLink, Users, MessageCircle, Shapes, ToyBrick, Palette, BookOpen, Check, ChevronsUpDown } from 'lucide-react';
import IconPicker, { getIconComponent, iconLibrary } from '@/components/ui/icon-picker';

// Mapa de Campos de Experiência da BNCC
const campoExperienciaMap = {
  'O eu, o outro e o nós': { icon: Users, name: 'O eu, o outro e o nós' },
  'Escuta, fala, pensamento e imaginação': { icon: MessageCircle, name: 'Escuta, fala, pensamento e imaginação' },
  'Espaços, tempos, quantidades, relações e transformações': { icon: Shapes, name: 'Espaços, tempos, quantidades...' },
  'Corpo, gestos e movimentos': { icon: ToyBrick, name: 'Corpo, gestos e movimentos' },
  'Traços, sons, cores e formas': { icon: Palette, name: 'Traços, sons, cores e formas' },
};

const baseLevels = ['Nível 1', 'Nível 2', 'Nível 3', 'Nível 4', 'Nível 5'];
const baseLevelOrder = new Map(baseLevels.map((level, index) => [level, index]));

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

const extractAnoFromLabel = (value) => {
  if (!value) return null;
  const match = value.match(/(\d+)\s*º?\s*ANO(?!S)/i);
  if (!match) return null;
  const parsed = Number(match[1]);
  return Number.isNaN(parsed) ? null : parsed;
};

const normalizeLevelFromName = (nome) => {
  if (!nome) return null;
  const anoFromNome = extractAnoFromLabel(nome);
  if (anoFromNome) {
    return `${anoFromNome}º ANO`;
  }
  return null;
};

const normalizeLevelFromFaixaEtaria = (faixaEtaria) => {
  if (!faixaEtaria) return null;
  const nivelMatch = faixaEtaria.match(/nível\s*(\d+)/i);
  if (nivelMatch) {
    return `Nível ${nivelMatch[1]}`;
  }
  const anoFromFaixa = extractAnoFromLabel(faixaEtaria);
  if (anoFromFaixa) {
    return `${anoFromFaixa}º ANO`;
  }
  const ageMatch = faixaEtaria.match(/(\d+)\s*anos?/i);
  if (ageMatch) {
    const age = Number(ageMatch[1]);
    if (!Number.isNaN(age)) {
      if (age >= 1 && age <= 5) {
        return `Nível ${age}`;
      }
      if (age >= 6 && age <= 10) {
        return `${age - 5}º ANO`;
      }
    }
  }
  return null;
};

const normalizeLevelValue = (turma) => {
  const nome = turma?.nome?.trim();
  const faixaEtaria = turma?.faixa_etaria?.trim();

  const levelFromName = normalizeLevelFromName(nome);
  if (levelFromName) return levelFromName;

  const levelFromFaixa = normalizeLevelFromFaixaEtaria(faixaEtaria);
  if (levelFromFaixa) return levelFromFaixa;

  return null;
};

const buildEducationLevels = (turmas = []) => {
  const dynamicLevels = turmas.map(normalizeLevelValue).filter(Boolean);
  const combined = Array.from(new Set([...baseLevels, ...dynamicLevels]));

  combined.sort((a, b) => {
    const aBaseIndex = baseLevelOrder.get(a);
    const bBaseIndex = baseLevelOrder.get(b);
    const aIsBase = aBaseIndex !== undefined;
    const bIsBase = bBaseIndex !== undefined;

    if (aIsBase && bIsBase) {
      return aBaseIndex - bBaseIndex;
    }
    if (aIsBase) return -1;
    if (bIsBase) return 1;

    const aAno = extractAnoFromLabel(a);
    const bAno = extractAnoFromLabel(b);
    if (aAno !== null && bAno !== null) {
      return aAno - bAno;
    }
    if (aAno !== null) return -1;
    if (bAno !== null) return 1;

    return a.localeCompare(b, 'pt-BR', { sensitivity: 'base' });
  });

  return combined;
};

// Componente Creatable Select para Campo de Experiência com suporte a ícones
const CreatableCampoSelect = ({ value, onChange, existingCampos, customCampos = [], onCampoCreated }) => {
  const [inputValue, setInputValue] = useState('');
  const [isOpen, setIsOpen] = useState(false);
  const [showIconPicker, setShowIconPicker] = useState(false);
  const [newCampoName, setNewCampoName] = useState('');
  const [selectedIcon, setSelectedIcon] = useState('BookOpen');
  const [savingCampo, setSavingCampo] = useState(false);
  const { toast } = useToast();

  const allCampos = useMemo(() => {
    const standardCampos = Object.keys(campoExperienciaMap);
    const customNames = (customCampos || []).map(c => c.nome);
    const combined = new Set([...standardCampos, ...(existingCampos || []), ...customNames]);
    return Array.from(combined).sort();
  }, [existingCampos, customCampos]);

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

      if (onCampoCreated) {
        onCampoCreated(novoCampo);
      }

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
    if (campoExperienciaMap[campo]) {
      return campoExperienciaMap[campo].icon;
    }
    if (customIconMap[campo]) {
      return getIconComponent(customIconMap[campo]);
    }
    return BookOpen;
  };

  return (
    <>
      <div className="relative col-span-3">
        <div
          className="flex items-center justify-between w-full h-10 px-3 py-2 text-sm bg-white border rounded-md cursor-pointer border-input hover:bg-accent"
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
                  <span>Criar novo: "<strong>{inputValue}</strong>"</span>
                </div>
              )}
            </div>
          </div>
        )}

        {isOpen && (
          <div className="fixed inset-0 z-40" onClick={() => { setIsOpen(false); setInputValue(''); }} />
        )}
      </div>

      {/* Modal de seleção de ícone */}
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
            <DialogClose asChild>
              <Button variant="ghost">Cancelar</Button>
            </DialogClose>
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

const PerguntasTab = () => {
  const navigate = useNavigate();
  const { toast } = useToast();
  const [perguntas, setPerguntas] = useState([]);
  const [loading, setLoading] = useState(true);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [currentPergunta, setCurrentPergunta] = useState(null);
  const [institutionId, setInstitutionId] = useState(null);
  const [nivelFilterEspecialista, setNivelFilterEspecialista] = useState('');
  const [educationLevels, setEducationLevels] = useState(baseLevels);
  const [existingCampos, setExistingCampos] = useState([]);
  const [customCampos, setCustomCampos] = useState([]);

  const fetchInstitution = useCallback(async () => {
      const { data: authData } = await apiClient.auth.getUser();
      const userInstitutionId = authData?.user?.instituicao_id || authData?.user?.user_metadata?.instituicao_id;
      if (userInstitutionId) {
          setInstitutionId(userInstitutionId);
          return userInstitutionId;
      }

      const { data, error } = await apiClient.from('instituicoes').select('id').limit(1).single();
      if (error && error.code !== 'PGRST116') {
          toast({ variant: "destructive", title: "Erro ao buscar instituição", description: error.message });
          return null;
      }
      if (data) {
          setInstitutionId(data.id);
          return data.id;
      }
      return null;
  }, [toast]);

  const fetchPerguntas = useCallback(async (id) => {
    if (!id) return;
    setLoading(true);
    const { data, error } = await apiClient
      .from('perguntas_especialistas')
      .select('*')
      .eq('instituicao_id', id)
      .order('created_at', { ascending: false });

    if (error) {
      toast({ title: 'Erro ao buscar perguntas', description: error.message, variant: 'destructive' });
    } else {
      setPerguntas(Array.isArray(data) ? data : []);
    }
    setLoading(false);
  }, [toast]);

  const fetchEducationLevels = useCallback(async (id) => {
    if (!id) return;

    const { data, error } = await apiClient
      .from('turmas')
      .select('id, nome, faixa_etaria, ativa')
      .eq('instituicao_id', id)
      .eq('ativa', true);

    if (error) {
      toast({
        title: 'Erro ao buscar níveis das turmas',
        description: error.message,
        variant: 'destructive',
      });
      setEducationLevels(baseLevels);
      return;
    }

    const levels = buildEducationLevels(Array.isArray(data) ? data : []);
    setEducationLevels(levels);
  }, [toast]);

  const fetchExistingCampos = useCallback(async () => {
    const { data } = await apiClient
      .from('perguntas_bncc')
      .select('campo_experiencia');

    if (data) {
      const campos = [...new Set(data.map(p => p.campo_experiencia).filter(Boolean))];
      setExistingCampos(campos);
    }
  }, []);

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

  useEffect(() => {
    fetchInstitution().then(id => {
      if (id) {
        fetchPerguntas(id);
        fetchEducationLevels(id);
        fetchExistingCampos();
        fetchCamposCustomizados();
      } else {
        setLoading(false);
      }
    });
  }, [fetchInstitution, fetchPerguntas, fetchEducationLevels, fetchExistingCampos, fetchCamposCustomizados]);


  const handleSave = async () => {
    if (!currentPergunta || !currentPergunta.campo_experiencia || !currentPergunta.nivel || !currentPergunta.pergunta_facilitadora || !currentPergunta.referencia_norma) {
      toast({ title: 'Campos obrigatórios', description: 'Campo de Experiência, Nível, Pergunta Facilitadora e Referência da Norma são necessários.', variant: 'destructive' });
      return;
    }

    const payload = {
      ...currentPergunta,
      pergunta_facilitadora: currentPergunta.pergunta_facilitadora?.trim(),
      referencia_norma: currentPergunta.referencia_norma?.trim(),
      pergunta: (currentPergunta.pergunta || currentPergunta.pergunta_facilitadora || '').trim(),
      instituicao_id: institutionId,
    };

    const { data, error } = await apiClient
      .from('perguntas_especialistas')
      .upsert(payload)
      .select();

    if (error) {
      toast({ title: 'Erro ao salvar pergunta', description: error.message, variant: 'destructive' });
    } else {
      toast({ title: 'Pergunta salva com sucesso!', className: 'bg-green-100' });
      setIsModalOpen(false);
      fetchPerguntas(institutionId);
    }
  };

  const openModal = (pergunta = null) => {
    if (!institutionId) {
        toast({ variant: "destructive", title: "Cadastro de Instituição Necessário", description: "Por favor, cadastre primeiro os dados da instituição." });
        return;
    }
    const perguntaBase = pergunta?.pergunta_facilitadora || pergunta?.pergunta || '';
    if (pergunta) {
      setCurrentPergunta({
        ...pergunta,
        pergunta: pergunta.pergunta || perguntaBase,
        pergunta_facilitadora: perguntaBase,
        referencia_norma: pergunta.referencia_norma || '',
        campo_experiencia: pergunta.campo_experiencia || pergunta.especialidade || '',
      });
    } else {
      setCurrentPergunta({ campo_experiencia: '', pergunta: perguntaBase, pergunta_facilitadora: perguntaBase, referencia_norma: '', status: 'ativa', nivel: '' });
    }
    setIsModalOpen(true);
  };

  const handleDelete = async (id) => {
    const { error } = await apiClient.from('perguntas_especialistas').delete().match({ id });
    if (error) {
      toast({ title: 'Erro ao deletar pergunta', description: error.message, variant: 'destructive' });
    } else {
      toast({ title: 'Pergunta deletada com sucesso!' });
      fetchPerguntas(institutionId);
    }
  };

  return (
    <div className="p-6 bg-white rounded-lg shadow-md">
      <div className="mb-8 p-4 border rounded-lg bg-gray-50">
        <h3 className="text-lg font-bold mb-2 text-gray-700">Perguntas da BNCC</h3>
        <p className="text-sm text-gray-600 mb-4">
          Gerencie as perguntas pedagógicas baseadas na BNCC. Você pode criar novos Campos de Experiência
          que serão exibidos automaticamente no formulário de observação dos professores.
        </p>
        <Button variant="outline" onClick={() => navigate('/admin/perguntas-bncc')}>
          <ExternalLink className="mr-2 h-4 w-4" />
          Gerenciar Perguntas BNCC
        </Button>
      </div>

      <div>
        <div className="flex flex-col gap-4 mb-4">
          <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
            <h3 className="text-lg font-bold text-gray-700">Perguntas dos Especialistas (Livres)</h3>
            <Dialog open={isModalOpen} onOpenChange={setIsModalOpen}>
              <DialogTrigger asChild>
                <Button onClick={() => openModal()}>
                  <PlusCircle className="mr-2 h-4 w-4" /> Nova Pergunta
                </Button>
              </DialogTrigger>
              <DialogContent className="max-w-lg">
                <DialogHeader>
                  <DialogTitle>{currentPergunta?.id ? 'Editar' : 'Nova'} Pergunta de Especialista</DialogTitle>
                </DialogHeader>
                <div className="grid gap-4 py-4">
                  <div className="grid grid-cols-4 items-center gap-4">
                    <Label htmlFor="campo_experiencia" className="text-right">Campo de Experiência</Label>
                    <CreatableCampoSelect
                      value={currentPergunta?.campo_experiencia || ''}
                      onChange={(value) => setCurrentPergunta(p => ({ ...p, campo_experiencia: value }))}
                      existingCampos={existingCampos}
                      customCampos={customCampos}
                      onCampoCreated={handleCampoCreated}
                    />
                  </div>
                  <div className="grid grid-cols-4 items-center gap-4">
                    <Label htmlFor="nivel" className="text-right">Nível</Label>
                    <Select value={currentPergunta?.nivel || ''} onValueChange={(value) => setCurrentPergunta(p => ({ ...p, nivel: value }))}>
                      <SelectTrigger className="col-span-3">
                        <SelectValue placeholder="Selecione o nível" />
                      </SelectTrigger>
                      <SelectContent>
                        {educationLevels.map(n => <SelectItem key={n} value={n}>{n}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="grid grid-cols-4 items-center gap-4">
                    <Label htmlFor="pergunta_facilitadora" className="text-right">Pergunta Facilitadora</Label>
                    <Input id="pergunta_facilitadora" value={currentPergunta?.pergunta_facilitadora || currentPergunta?.pergunta || ''} onChange={(e) => setCurrentPergunta(p => ({ ...p, pergunta_facilitadora: e.target.value, pergunta: e.target.value }))} className="col-span-3" placeholder="Digite o texto da pergunta facilitadora" />
                  </div>
                  <div className="grid grid-cols-4 items-center gap-4">
                    <Label htmlFor="referencia_norma" className="text-right">Referência (BNCC)</Label>
                    <Input id="referencia_norma" value={currentPergunta?.referencia_norma || ''} onChange={(e) => setCurrentPergunta(p => ({ ...p, referencia_norma: e.target.value }))} className="col-span-3" placeholder="Ex: EI03EO01" />
                  </div>
                  <div className="grid grid-cols-4 items-center gap-4">
                    <Label htmlFor="status" className="text-right">Status</Label>
                    <Select value={currentPergunta?.status || 'ativa'} onValueChange={(value) => setCurrentPergunta(p => ({ ...p, status: value }))}>
                      <SelectTrigger className="col-span-3">
                        <SelectValue placeholder="Selecione o status" />
                      </SelectTrigger>
                      <SelectContent>
                          <SelectItem value="ativa">Ativa</SelectItem>
                          <SelectItem value="inativa">Inativa</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                <p className="text-xs text-gray-500 -mt-2 mb-2">
                  O Campo de Experiência define como a pergunta será agrupada no formulário de observação.
                  Você pode criar novos campos digitando no seletor acima.
                </p>
                <DialogFooter>
                  <DialogClose asChild><Button variant="ghost">Cancelar</Button></DialogClose>
                  <Button onClick={handleSave}>Salvar</Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </div>
          <div className="max-w-xs">
            <Select value={nivelFilterEspecialista} onValueChange={(value) => setNivelFilterEspecialista(value === 'all-levels' ? '' : value)}>
              <SelectTrigger>
                <SelectValue placeholder="Filtrar por Nível" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all-levels">Todos os Níveis</SelectItem>
                {educationLevels.map(n => <SelectItem key={n} value={n}>{n}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
        </div>
        {loading ? (
          <div className="flex justify-center items-center h-32"><Loader2 className="h-8 w-8 animate-spin text-purple-500" /></div>
        ) : (
          <div className="border rounded-lg overflow-hidden">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Campo de Experiência</TableHead>
                  <TableHead>Nível</TableHead>
                  <TableHead>Pergunta Facilitadora</TableHead>
                  <TableHead>Referência (BNCC)</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Ações</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {perguntas.filter(p => !nivelFilterEspecialista || p.nivel === nivelFilterEspecialista).map((p) => (
                  <TableRow key={p.id}>
                    <TableCell className="font-medium">{p.campo_experiencia || p.especialidade}</TableCell>
                    <TableCell>{p.nivel}</TableCell>
                    <TableCell>{p.pergunta_facilitadora || p.pergunta}</TableCell>
                    <TableCell>{p.referencia_norma}</TableCell>
                    <TableCell>
                      <span className={`px-2 py-1 rounded-full text-xs font-semibold ${p.status === 'ativa' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
                        {p.status === 'ativa' ? 'Ativa' : 'Inativa'}
                      </span>
                    </TableCell>
                    <TableCell className="text-right">
                      <Button variant="ghost" size="icon" onClick={() => openModal(p)}><Edit className="h-4 w-4" /></Button>
                      <Dialog>
                        <DialogTrigger asChild>
                          <Button variant="ghost" size="icon"><Trash2 className="h-4 w-4 text-red-500" /></Button>
                        </DialogTrigger>
                        <DialogContent>
                          <DialogHeader>
                            <DialogTitle>Confirmar Exclusão</DialogTitle>
                            <DialogClose/>
                          </DialogHeader>
                          <p>Tem certeza que deseja excluir esta pergunta?</p>
                          <DialogFooter>
                            <DialogClose asChild><Button variant="outline">Cancelar</Button></DialogClose>
                            <Button variant="destructive" onClick={() => handleDelete(p.id)}>Excluir</Button>
                          </DialogFooter>
                        </DialogContent>
                      </Dialog>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </div>
    </div>
  );
};

export default PerguntasTab;
