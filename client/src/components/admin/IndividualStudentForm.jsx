import React, { useState } from 'react';
import { UserPlus, Calendar as CalendarIcon, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { Calendar } from '@/components/ui/calendar';
import { useToast } from '@/components/ui/use-toast';
import { apiClient } from '@/lib/apiClient';
import { cn } from '@/lib/utils';
import { format } from 'date-fns';
import { ptBR } from 'date-fns/locale';

const IndividualStudentForm = ({ turmas, turmasState, institutionId, onStudentAdded }) => {
  const { toast } = useToast();
  const [isOpen, setIsOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [formData, setFormData] = useState({
    nome_completo: '',
    data_nascimento: null,
    turma_id: '',
    genero: '',
  });

  const handleInputChange = (e) => {
    const { id, value } = e.target;
    setFormData((prev) => ({ ...prev, [id]: value }));
  };

  const handleSelectChange = (name, value) => {
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  const handleDateChange = (date) => {
    setFormData((prev) => ({ ...prev, data_nascimento: date }));
  };

  const resetForm = () => {
    setFormData({
      nome_completo: '',
      data_nascimento: null,
      turma_id: '',
      genero: '',
    });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsLoading(true);

    const { nome_completo, data_nascimento, turma_id } = formData;

    if (!nome_completo || !data_nascimento || !turma_id) {
      toast({ variant: 'destructive', title: 'Erro', description: 'Por favor, preencha todos os campos obrigatórios.' });
      setIsLoading(false);
      return;
    }

    const { data: duplicate, error: duplicateError } = await apiClient
      .from('criancas')
      .select('id')
      .eq('nome_completo', nome_completo)
      .eq('data_nascimento', format(data_nascimento, 'yyyy-MM-dd'))
      .eq('instituicao_id', institutionId)
      .maybeSingle();

    if (duplicateError) {
      toast({ variant: 'destructive', title: 'Erro ao verificar duplicidade', description: duplicateError.message });
      setIsLoading(false);
      return;
    }

    if (duplicate) {
      toast({ variant: 'destructive', title: 'Aluno já existe', description: 'Já existe um aluno com este nome e data de nascimento.' });
      setIsLoading(false);
      return;
    }

    const studentToInsert = {
      instituicao_id: institutionId,
      turma_id: formData.turma_id,
      nome_completo: formData.nome_completo,
      data_nascimento: format(formData.data_nascimento, 'yyyy-MM-dd'),
      genero: formData.genero,
    };

    const { error: insertError } = await apiClient
      .from('criancas')
      .insert(studentToInsert);

    if (insertError) {
      toast({ variant: 'destructive', title: 'Erro ao cadastrar aluno', description: insertError.message });
      setIsLoading(false);
      return;
    }

    const selectedTurma = turmas.find(t => t.id === formData.turma_id);
    toast({ title: 'Sucesso!', description: `Aluno ${formData.nome_completo} cadastrado na turma ${selectedTurma?.nome}.` });
    
    setIsLoading(false);
    setIsOpen(false);
    resetForm();
    if (onStudentAdded) {
      onStudentAdded();
    }
  };

  const renderTurmaSelectContent = () => {
    if (turmasState?.loading) {
        return <SelectItem value="loading" disabled>Carregando...</SelectItem>;
    }
     if (turmasState?.error) {
        return <SelectItem value="error" disabled>Erro ao carregar turmas</SelectItem>;
    }
    if (!turmas || turmas.length === 0) {
        return <SelectItem value="no-turmas" disabled>Nenhuma turma encontrada</SelectItem>;
    }
    return turmas.map((t) => (
        <SelectItem key={t.id} value={t.id}>{t.nome}</SelectItem>
    ));
  };

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" className="bg-lavanda-claro border-lavanda-principal text-lavanda-principal hover:bg-lavanda hover:text-white">
          <UserPlus className="mr-2 h-4 w-4" />
          Cadastrar Aluno Individualmente
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-[425px]">
        <DialogHeader>
          <DialogTitle>Cadastrar Novo Aluno</DialogTitle>
          <DialogDescription>Preencha os dados abaixo para adicionar um novo aluno ao sistema.</DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="grid gap-4 py-4">
          <div className="grid grid-cols-4 items-center gap-4">
            <Label htmlFor="nome_completo" className="text-right">Nome Completo</Label>
            <Input id="nome_completo" value={formData.nome_completo} onChange={handleInputChange} className="col-span-3" required />
          </div>
          <div className="grid grid-cols-4 items-center gap-4">
            <Label htmlFor="data_nascimento" className="text-right">Nascimento</Label>
            <Popover>
              <PopoverTrigger asChild>
                <Button
                  variant={"outline"}
                  className={cn(
                    "col-span-3 justify-start text-left font-normal",
                    !formData.data_nascimento && "text-muted-foreground"
                  )}
                >
                  <CalendarIcon className="mr-2 h-4 w-4" />
                  {formData.data_nascimento ? format(formData.data_nascimento, "PPP", { locale: ptBR }) : <span>Selecione a data</span>}
                </Button>
              </PopoverTrigger>
              <PopoverContent className="w-auto p-0">
                <Calendar
                  mode="single"
                  selected={formData.data_nascimento}
                  onSelect={handleDateChange}
                  initialFocus
                  locale={ptBR}
                  captionLayout="dropdown-buttons"
                  fromYear={2010}
                  toYear={new Date().getFullYear()}
                />
              </PopoverContent>
            </Popover>
          </div>
          <div className="grid grid-cols-4 items-center gap-4">
            <Label htmlFor="turma_id" className="text-right">Turma</Label>
            <Select onValueChange={(v) => handleSelectChange('turma_id', v)} value={formData.turma_id}>
              <SelectTrigger className="col-span-3">
                <SelectValue placeholder="Selecione a turma" />
              </SelectTrigger>
              <SelectContent>
                {renderTurmaSelectContent()}
              </SelectContent>
            </Select>
          </div>
          <div className="grid grid-cols-4 items-center gap-4">
            <Label htmlFor="genero" className="text-right">Gênero</Label>
            <Select onValueChange={(v) => handleSelectChange('genero', v)} value={formData.genero}>
              <SelectTrigger className="col-span-3">
                <SelectValue placeholder="Selecione o gênero" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="Masculino">Masculino</SelectItem>
                <SelectItem value="Feminino">Feminino</SelectItem>
                <SelectItem value="Outro">Outro</SelectItem>
                <SelectItem value="NaoInformado">Prefiro não informar</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <DialogFooter>
            <Button type="submit" disabled={isLoading} className="bg-roxo-principal hover:bg-roxo-principal/90">
              {isLoading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <UserPlus className="mr-2 h-4 w-4" />}
              <span>Salvar Aluno</span>
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
};

export default IndividualStudentForm;