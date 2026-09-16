import React, { useState, useEffect, useRef } from 'react';
import { UserPlus, Edit, Calendar as CalendarIcon, Loader2, Camera, User } from 'lucide-react';
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
import { criarCrianca, atualizarCrianca, uploadFotoCrianca } from '@/services/api';
import { cn } from '@/lib/utils';
import { format, parseISO } from 'date-fns';
import { ptBR } from 'date-fns/locale';
import { IMaskInput } from 'react-imask';

const MAX_FOTO_SIZE_BYTES = 10 * 1024 * 1024; // 10MB, mesmo limite do backend
const ALLOWED_FOTO_TYPES = ['image/jpeg', 'image/png', 'image/webp', 'image/heic', 'image/heif'];

const StudentFormDialog = ({ children, studentData, turmas, institutionId, onStudentUpdated }) => {
    const { toast } = useToast();
    const [isOpen, setIsOpen] = useState(false);
    const [isCalendarOpen, setIsCalendarOpen] = useState(false);
    const [isLoading, setIsLoading] = useState(false);
    const fileInputRef = useRef(null);

    const isEditing = Boolean(studentData);

    const initialFormData = {
        nome_completo: '',
        data_nascimento: null,
        turma_id: '',
        nome_responsavel: '',
        telefone_responsavel: '',
    };
    
    const [formData, setFormData] = useState(initialFormData);
    const [phoneValue, setPhoneValue] = useState('');

    // Arquivo selecionado localmente (ainda não enviado) e URL de preview.
    const [fotoFile, setFotoFile] = useState(null);
    const [fotoPreview, setFotoPreview] = useState(null);

    useEffect(() => {
        if (isEditing && studentData) {
            setFormData({
                nome_completo: studentData.nome_completo || '',
                data_nascimento: studentData.data_nascimento ? parseISO(studentData.data_nascimento) : null,
                turma_id: studentData.turma_id || '',
                nome_responsavel: studentData.nome_responsavel || '',
                telefone_responsavel: studentData.telefone_responsavel || '',
            });
            setPhoneValue(studentData.telefone_responsavel || '');
            setFotoFile(null);
            setFotoPreview(studentData.foto_url || null);
        } else {
            setFormData(initialFormData);
            setPhoneValue('');
            setFotoFile(null);
            setFotoPreview(null);
        }
    }, [isEditing, studentData, isOpen]);

    // Libera a URL de preview criada localmente quando o componente desmonta
    // ou quando o arquivo muda, evitando vazamento de memória.
    useEffect(() => {
        return () => {
            if (fotoPreview && fotoPreview.startsWith('blob:')) {
                URL.revokeObjectURL(fotoPreview);
            }
        };
    }, [fotoPreview]);

    const handleInputChange = (e) => {
        const { id, value } = e.target;
        setFormData((prev) => ({ ...prev, [id]: value }));
    };

    const handleSelectChange = (name, value) => {
        setFormData((prev) => ({ ...prev, [name]: value }));
    };

    const handleDateChange = (date) => {
        setFormData((prev) => ({ ...prev, data_nascimento: date }));
        setIsCalendarOpen(false);
    };

    const handleFotoClick = () => {
        fileInputRef.current?.click();
    };

    const handleFotoChange = (e) => {
        const file = e.target.files?.[0];
        if (!file) return;

        if (!ALLOWED_FOTO_TYPES.includes(file.type)) {
            toast({
                variant: 'destructive',
                title: 'Formato inválido',
                description: 'Envie uma imagem JPG, PNG, WEBP ou HEIC.',
            });
            return;
        }

        if (file.size > MAX_FOTO_SIZE_BYTES) {
            toast({
                variant: 'destructive',
                title: 'Arquivo muito grande',
                description: 'A imagem deve ter no máximo 10MB.',
            });
            return;
        }

        if (fotoPreview && fotoPreview.startsWith('blob:')) {
            URL.revokeObjectURL(fotoPreview);
        }

        setFotoFile(file);
        setFotoPreview(URL.createObjectURL(file));
    };

    const resetForm = () => {
        setFormData(initialFormData);
        setPhoneValue('');
        setFotoFile(null);
        setFotoPreview(null);
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setIsLoading(true);

        const { nome_completo, data_nascimento, turma_id, nome_responsavel } = formData;
        const telefone_responsavel = phoneValue;

        if (!nome_completo || !data_nascimento || !turma_id || !nome_responsavel || !telefone_responsavel) {
            toast({ variant: 'destructive', title: 'Erro', description: 'Por favor, preencha todos os campos obrigatórios.' });
            setIsLoading(false);
            return;
        }

        const studentToSave = {
            instituicao_id: institutionId,
            nome_completo,
            data_nascimento: format(data_nascimento, 'yyyy-MM-dd'),
            turma_id,
            nome_responsavel,
            telefone_responsavel
        };

        try {
            let criancaId = studentData?.id;

            if (isEditing) {
                await atualizarCrianca(criancaId, studentToSave);
            } else {
                const criada = await criarCrianca(studentToSave);
                criancaId = criada?.id;
            }

            // Upload da foto é uma etapa separada, só possível depois que a
            // criança já existe (o endpoint precisa do id). Se falhar, o
            // aluno já foi salvo mesmo assim — avisamos sem bloquear o fluxo.
            if (fotoFile && criancaId) {
                try {
                    await uploadFotoCrianca(criancaId, fotoFile);
                } catch (fotoError) {
                    toast({
                        variant: 'destructive',
                        title: 'Aluno salvo, mas a foto falhou',
                        description: fotoError.message,
                    });
                }
            }

            toast({ title: 'Sucesso!', description: `Aluno ${isEditing ? 'atualizado' : 'cadastrado'} com sucesso.` });

            onStudentUpdated();
            setIsOpen(false);
            resetForm();
        } catch (error) {
            toast({ variant: 'destructive', title: `Erro ao ${isEditing ? 'atualizar' : 'cadastrar'} aluno`, description: error.message });
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <Dialog open={isOpen} onOpenChange={setIsOpen}>
            <DialogTrigger asChild>
                {children || <Button variant="outline"><Edit className="mr-2 h-4 w-4" /> Editar Aluno</Button>}
            </DialogTrigger>
            <DialogContent className="sm:max-w-md">
                <DialogHeader>
                    <DialogTitle>{isEditing ? 'Editar Aluno' : 'Cadastrar Novo Aluno'}</DialogTitle>
                    <DialogDescription>
                        {isEditing ? 'Atualize os dados do aluno abaixo.' : 'Preencha os dados para adicionar um novo aluno.'}
                    </DialogDescription>
                </DialogHeader>
                <form onSubmit={handleSubmit} noValidate className="grid gap-4 py-4">
                    <div className="flex flex-col items-center gap-2">
                        <input
                            type="file"
                            ref={fileInputRef}
                            onChange={handleFotoChange}
                            accept="image/jpeg,image/png,image/webp,image/heic,image/heif"
                            className="hidden"
                        />
                        <button
                            type="button"
                            onClick={handleFotoClick}
                            className="relative h-24 w-24 rounded-full border-2 border-dashed border-gray-300 hover:border-purple-400 transition-colors overflow-hidden flex items-center justify-center bg-gray-50 group"
                        >
                            {fotoPreview ? (
                                <img src={fotoPreview} alt="Foto do aluno" className="h-full w-full object-cover" />
                            ) : (
                                <User className="h-10 w-10 text-gray-300" />
                            )}
                            <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                                <Camera className="h-6 w-6 text-white" />
                            </div>
                        </button>
                        <span className="text-xs text-gray-500">Foto do aluno (opcional)</span>
                    </div>
                    <div className="space-y-2">
                        <Label htmlFor="nome_completo">Nome Completo</Label>
                        <Input id="nome_completo" value={formData.nome_completo} onChange={handleInputChange} required />
                    </div>
                    <div className="space-y-2">
                        <Label htmlFor="data_nascimento">Data de Nascimento</Label>
                        <Popover open={isCalendarOpen} onOpenChange={setIsCalendarOpen}>
                            <PopoverTrigger asChild>
                                <Button
                                    variant={"outline"}
                                    className={cn(
                                        "w-full justify-start text-left font-normal",
                                        !formData.data_nascimento && "text-muted-foreground"
                                    )}
                                >
                                    <CalendarIcon className="mr-2 h-4 w-4" />
                                    {formData.data_nascimento ? format(formData.data_nascimento, "dd/MM/yyyy") : <span>Selecione a data</span>}
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
                                    fromYear={new Date().getFullYear() - 20}
                                    toYear={new Date().getFullYear()}
                                />
                            </PopoverContent>
                        </Popover>
                    </div>
                    <div className="space-y-2">
                        <Label htmlFor="nome_responsavel">Nome do Responsável</Label>
                        <Input id="nome_responsavel" value={formData.nome_responsavel} onChange={handleInputChange} required />
                    </div>
                    <div className="space-y-2">
                        <Label htmlFor="telefone_responsavel">Telefone do Responsável</Label>
                        <IMaskInput
                            mask="(00) 00000-0000"
                            id="telefone_responsavel"
                            value={phoneValue}
                            onAccept={(value) => setPhoneValue(value)}
                            className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                            required
                        />
                    </div>
                    <div className="space-y-2">
                        <Label htmlFor="turma_id">Turma</Label>
                        <Select onValueChange={(v) => handleSelectChange('turma_id', v)} value={formData.turma_id}>
                            <SelectTrigger>
                                <SelectValue placeholder="Selecione a turma" />
                            </SelectTrigger>
                            <SelectContent>
                                {turmas.map((t) => (
                                    <SelectItem key={t.id} value={t.id}>{t.nome}</SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>
                    <DialogFooter>
                        <Button type="submit" disabled={isLoading} className="w-full">
                            {isLoading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : (isEditing ? <Edit className="mr-2 h-4 w-4" /> : <UserPlus className="mr-2 h-4 w-4" />)}
                            <span>{isEditing ? 'Salvar Alterações' : 'Cadastrar Aluno'}</span>
                        </Button>
                    </DialogFooter>
                </form>
            </DialogContent>
        </Dialog>
    );
};

export default StudentFormDialog;