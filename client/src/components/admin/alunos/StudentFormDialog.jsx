import React, { useState, useEffect, useMemo, useRef } from 'react';
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

// Fixo (10 dígitos) ou celular (11): o IMask escolhe a máscara pelo que foi digitado.
const MASCARA_TELEFONE = [{ mask: '(00) 0000-0000' }, { mask: '(00) 00000-0000' }];

const STATUS_LABELS = { ativo: 'Ativo', inativo: 'Inativo', transferido: 'Transferido' };

const FORM_VAZIO = {
    nome_completo: '',
    data_nascimento: null,
    turma: '',
    nome_responsavel: '',
    status_vinculo: 'ativo',
};

/**
 * Cadastro/edição de aluno. `turmas`: turmas ATIVAS do escopo (o backend
 * recusa turma desativada). Na edição, só as turmas da escola do aluno (ele
 * não muda de escola), mais a turma atual, mesmo que desativada.
 */
const StudentFormDialog = ({ children, studentData, turmas, onStudentUpdated }) => {
    const { toast } = useToast();
    const [isOpen, setIsOpen] = useState(false);
    const [isCalendarOpen, setIsCalendarOpen] = useState(false);
    const [isLoading, setIsLoading] = useState(false);
    const fileInputRef = useRef(null);

    const isEditing = Boolean(studentData);

    const [formData, setFormData] = useState(FORM_VAZIO);
    const [phoneValue, setPhoneValue] = useState('');

    // Arquivo selecionado localmente (ainda não enviado) e URL de preview.
    const [fotoFile, setFotoFile] = useState(null);
    const [fotoPreview, setFotoPreview] = useState(null);

    useEffect(() => {
        if (!isOpen) return;
        if (isEditing) {
            setFormData({
                nome_completo: studentData.nome_completo || '',
                data_nascimento: studentData.data_nascimento ? parseISO(studentData.data_nascimento) : null,
                turma: studentData.turma ? String(studentData.turma) : '',
                nome_responsavel: studentData.nome_responsavel || '',
                status_vinculo: studentData.status_vinculo || 'ativo',
            });
            setPhoneValue(studentData.telefone_responsavel || '');
            setFotoFile(null);
            setFotoPreview(studentData.foto_url || null);
        } else {
            setFormData(FORM_VAZIO);
            setPhoneValue('');
            setFotoFile(null);
            setFotoPreview(null);
        }
    }, [isEditing, studentData, isOpen]);

    // Libera a URL de preview criada localmente quando o arquivo muda ou o
    // componente desmonta, evitando vazamento de memória.
    useEffect(() => {
        return () => {
            if (fotoPreview && fotoPreview.startsWith('blob:')) {
                URL.revokeObjectURL(fotoPreview);
            }
        };
    }, [fotoPreview]);

    const variasEscolas = useMemo(() => new Set(turmas.map((t) => String(t.escola))).size > 1, [turmas]);

    const opcoesTurma = useMemo(() => {
        let lista = isEditing
            ? turmas.filter((t) => String(t.escola) === String(studentData.escola))
            : turmas;
        // Turma atual desativada: continua aparecendo para o select não ficar vazio.
        if (isEditing && studentData.turma && !lista.some((t) => String(t.id) === String(studentData.turma))) {
            lista = [...lista, { id: studentData.turma, nome: `${studentData.turma_nome} (desativada)`, escola: studentData.escola }];
        }
        return lista;
    }, [turmas, isEditing, studentData]);

    const rotuloTurma = (t) => (variasEscolas && !isEditing && t.escola_nome ? `${t.nome} — ${t.escola_nome}` : t.nome);

    const set = (campo, valor) => setFormData((prev) => ({ ...prev, [campo]: valor }));

    const handleDateChange = (date) => {
        set('data_nascimento', date);
        setIsCalendarOpen(false);
    };

    const handleFotoChange = (e) => {
        const file = e.target.files?.[0];
        e.target.value = ''; // permite escolher o mesmo arquivo de novo depois
        if (!file) return;

        if (!ALLOWED_FOTO_TYPES.includes(file.type)) {
            toast({ variant: 'destructive', title: 'Formato inválido', description: 'Envie uma imagem JPG, PNG, WEBP ou HEIC.' });
            return;
        }
        if (file.size > MAX_FOTO_SIZE_BYTES) {
            toast({ variant: 'destructive', title: 'Arquivo muito grande', description: 'A imagem deve ter no máximo 10MB.' });
            return;
        }

        setFotoFile(file);
        setFotoPreview(URL.createObjectURL(file));
    };

    const handleSubmit = async (e) => {
        e.preventDefault();

        const nome_completo = formData.nome_completo.trim();
        const nome_responsavel = formData.nome_responsavel.trim();
        if (!nome_completo || !formData.data_nascimento || !formData.turma || !nome_responsavel || !phoneValue) {
            toast({ variant: 'destructive', title: 'Erro', description: 'Por favor, preencha todos os campos obrigatórios.' });
            return;
        }

        const studentToSave = {
            nome_completo,
            data_nascimento: format(formData.data_nascimento, 'yyyy-MM-dd'),
            turma: formData.turma,
            nome_responsavel,
            telefone_responsavel: phoneValue,
        };
        if (isEditing) studentToSave.status_vinculo = formData.status_vinculo;

        setIsLoading(true);
        try {
            let alunoId = studentData?.id;
            if (isEditing) {
                await atualizarCrianca(alunoId, studentToSave);
            } else {
                alunoId = (await criarCrianca(studentToSave))?.id;
            }

            // A foto é uma etapa separada (o endpoint precisa do aluno já salvo).
            // Se falhar, o aluno já foi salvo mesmo assim: avisa sem bloquear.
            if (fotoFile && alunoId) {
                try {
                    await uploadFotoCrianca(alunoId, fotoFile);
                } catch (fotoError) {
                    toast({ variant: 'destructive', title: 'Aluno salvo, mas a foto falhou', description: fotoError.message });
                }
            }

            toast({ title: 'Sucesso!', description: `Aluno ${isEditing ? 'atualizado' : 'cadastrado'} com sucesso.` });
            onStudentUpdated();
            setIsOpen(false);
        } catch (error) {
            // Erros por campo (aluno duplicado, telefone, turma) já vêm na mensagem.
            toast({ variant: 'destructive', title: `Erro ao ${isEditing ? 'atualizar' : 'cadastrar'} aluno`, description: error.message });
        } finally {
            setIsLoading(false);
        }
    };

    return (
        // Não fecha no meio do salvamento (Esc/clique fora).
        <Dialog open={isOpen} onOpenChange={(aberto) => { if (!isLoading) setIsOpen(aberto); }}>
            <DialogTrigger asChild>
                {children || <Button variant="outline"><Edit className="mr-2 h-4 w-4" /> Editar Aluno</Button>}
            </DialogTrigger>
            <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-md">
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
                            onClick={() => fileInputRef.current?.click()}
                            aria-label="Escolher foto do aluno"
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
                        <Input id="nome_completo" value={formData.nome_completo} onChange={(e) => set('nome_completo', e.target.value)} maxLength={200} required />
                    </div>
                    <div className="space-y-2">
                        <Label htmlFor="data_nascimento">Data de Nascimento</Label>
                        <Popover open={isCalendarOpen} onOpenChange={setIsCalendarOpen}>
                            <PopoverTrigger asChild>
                                <Button
                                    id="data_nascimento"
                                    variant="outline"
                                    className={cn('w-full justify-start text-left font-normal', !formData.data_nascimento && 'text-muted-foreground')}
                                >
                                    <CalendarIcon className="mr-2 h-4 w-4" />
                                    {formData.data_nascimento ? format(formData.data_nascimento, 'dd/MM/yyyy') : <span>Selecione a data</span>}
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
                                    disabled={{ after: new Date() }}
                                />
                            </PopoverContent>
                        </Popover>
                    </div>
                    <div className="space-y-2">
                        <Label htmlFor="nome_responsavel">Nome do Responsável</Label>
                        <Input id="nome_responsavel" value={formData.nome_responsavel} onChange={(e) => set('nome_responsavel', e.target.value)} maxLength={200} required />
                    </div>
                    <div className="space-y-2">
                        <Label htmlFor="telefone_responsavel">Telefone do Responsável</Label>
                        <IMaskInput
                            mask={MASCARA_TELEFONE}
                            id="telefone_responsavel"
                            value={phoneValue}
                            onAccept={(value) => setPhoneValue(value)}
                            placeholder="(84) 99999-9999"
                            className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                            required
                        />
                    </div>
                    <div className="space-y-2">
                        <Label htmlFor="turma">Turma</Label>
                        <Select onValueChange={(v) => set('turma', v)} value={formData.turma}>
                            <SelectTrigger id="turma">
                                <SelectValue placeholder="Selecione a turma" />
                            </SelectTrigger>
                            <SelectContent>
                                {opcoesTurma.map((t) => (
                                    <SelectItem key={t.id} value={String(t.id)}>{rotuloTurma(t)}</SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                        {isEditing && variasEscolas && studentData.escola_nome && (
                            <p className="text-xs text-gray-500">Escola: {studentData.escola_nome} (o aluno não muda de escola).</p>
                        )}
                    </div>
                    {isEditing && (
                        <div className="space-y-2">
                            <Label htmlFor="status_vinculo">Situação</Label>
                            <Select onValueChange={(v) => set('status_vinculo', v)} value={formData.status_vinculo}>
                                <SelectTrigger id="status_vinculo"><SelectValue /></SelectTrigger>
                                <SelectContent>
                                    {Object.entries(STATUS_LABELS).map(([valor, label]) => (
                                        <SelectItem key={valor} value={valor}>{label}</SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </div>
                    )}
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