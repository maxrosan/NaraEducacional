import React, { useState, useEffect } from 'react';
import { RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogClose } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { toast } from '@/components/ui/use-toast';

const PROFESSOR_FUNDAMENTAL = 'professor_fundamental';

const UserFormDialog = ({ isOpen, setIsOpen, user, turmas, disciplinas, onSubmit }) => {
    const tiposEspecialistaPadrao = [
        { value: 'psicologo', label: 'Psicólogo' },
        { value: 'psicopedagogo', label: 'Psicopedagogo' },
        { value: 'fonoaudiologo', label: 'Fonoaudiólogo' },
        { value: 'terapeuta_ocupacional', label: 'Terapeuta Ocupacional' },
    ];
    const tipoEspecialistaOutro = 'outro';
    const specialistProfiles = ['especialista', 'professor_especialista'];
    const [formData, setFormData] = useState({});

    const generatePassword = () => {
        const length = 10;
        const charset = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*()";
        let retVal = "";
        for (let i = 0, n = charset.length; i < length; ++i) {
            retVal += charset.charAt(Math.floor(Math.random() * n));
        }
        return retVal;
    };

    useEffect(() => {
        const tiposEspecialistaValores = tiposEspecialistaPadrao.map(tipo => tipo.value);
        const isTipoPadrao = user?.tipo_especialista && tiposEspecialistaValores.includes(user.tipo_especialista);
        const isSpecialistProfile = specialistProfiles.includes(user?.perfil);
        const initialData = {
            nome: user?.nome || '',
            email: user?.email || '',
            perfil: user?.perfil || '',
            ativo: user?.ativo ?? true,
            turmas: user?.turmas || [],
            disciplinas: user?.usuario_disciplinas?.map(v => v.disciplina) || [],
            password: '',
            tipo_especialista: isSpecialistProfile ? (isTipoPadrao ? user.tipo_especialista : tipoEspecialistaOutro) : '',
            tipo_especialista_outro: isSpecialistProfile && !isTipoPadrao ? user.tipo_especialista : '',
            permissoes_esp: user?.permissoes_esp || {},
        };
        if (!user) {
            initialData.password = generatePassword();
        }
        setFormData(initialData);

    }, [user, isOpen]);

    const handleChange = (e) => {
        const { name, value, type, checked } = e.target;
        setFormData(prev => ({ ...prev, [name]: type === 'checkbox' ? checked : value }));
    };

    const handleSelectChange = (name, value) => {
        setFormData(prev => ({...prev, [name]: value}));
    };

    const handleTurmaChange = (turmaId, checked) => {
        setFormData(prev => {
            const currentTurmas = prev.turmas || [];
            if (checked) {
                return { ...prev, turmas: [...currentTurmas, turmaId] };
            } else {
                return { ...prev, turmas: currentTurmas.filter(id => id !== turmaId) };
            }
        });
    };

    const handleSelectAllTurmas = (checked) => {
        if (checked) {
            setFormData(prev => ({ ...prev, turmas: turmas.map(t => t.id) }));
        } else {
            setFormData(prev => ({ ...prev, turmas: [] }));
        }
    };

    const handleDisciplinaChange = (disciplinaId, checked) => {
        setFormData(prev => {
            const currentDisciplinas = prev.disciplinas || [];
            if (checked) {
                return { ...prev, disciplinas: [...currentDisciplinas, disciplinaId] };
            } else {
                return { ...prev, disciplinas: currentDisciplinas.filter(id => id !== disciplinaId) };
            }
        });
    };

    const handleSelectAllDisciplinas = (checked) => {
        if (checked) {
            setFormData(prev => ({ ...prev, disciplinas: disciplinas.map(d => d.id) }));
        } else {
            setFormData(prev => ({ ...prev, disciplinas: [] }));
        }
    };

    const handleSubmit = (e) => {
        e.preventDefault();
        let finalData = { ...formData };
        if (!specialistProfiles.includes(formData.perfil)) {
            finalData.tipo_especialista = null;
            finalData.tipo_especialista_outro = null;
        }
        // Always clear permissions for specialists, as it's no longer configured here
        if (specialistProfiles.includes(formData.perfil)) {
            finalData.permissoes_esp = {};
        }
        // Disciplinas só se aplicam a professor_fundamental — limpa o resto
        // pra não deixar vínculo órfão se o perfil mudar antes de salvar.
        if (formData.perfil !== PROFESSOR_FUNDAMENTAL) {
            finalData.disciplinas = [];
        }
        onSubmit(finalData);
    };

    const handleGenerateAndCopyPassword = () => {
        const newPassword = generatePassword();
        setFormData(prev => ({ ...prev, password: newPassword }));
        navigator.clipboard.writeText(newPassword);
        toast({ title: "Senha gerada e copiada!" });
    };

    return (
        <Dialog open={isOpen} onOpenChange={setIsOpen}>
            <DialogContent className="max-h-[90vh] overflow-y-auto">
                <DialogHeader>
                    <DialogTitle>{user ? 'Editar Usuário' : 'Novo Usuário'}</DialogTitle>
                </DialogHeader>
                <form onSubmit={handleSubmit} className="space-y-4 pt-4">
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        <div>
                            <Label htmlFor="nome">Nome</Label>
                            <Input id="nome" name="nome" value={formData.nome || ''} onChange={handleChange} required />
                        </div>
                        <div>
                            <Label htmlFor="email">Email</Label>
                            <Input id="email" name="email" type="email" value={formData.email || ''} onChange={handleChange} required disabled={!!user} />
                        </div>
                    </div>


                    { user ? (
  <div>
    <Label htmlFor="password">Nova Senha <span className="text-xs text-gray-400">(deixe em branco para não alterar)</span></Label>
    <div className="flex items-center gap-2">
      <Input id="password" name="password" type="text" value={formData.password || ''} onChange={handleChange} placeholder="Digite para redefinir..." />
      <Button type="button" variant="ghost" size="icon" onClick={handleGenerateAndCopyPassword} title="Gerar e copiar nova senha">
        <RefreshCw className="h-4 w-4" />
      </Button>
    </div>
  </div>
                    ) : (
  <div>
    <Label htmlFor="password">Senha</Label>
    <div className="flex items-center gap-2">
      <Input id="password" name="password" type="text" value={formData.password || ''} onChange={handleChange} required />
      <Button type="button" variant="ghost" size="icon" onClick={handleGenerateAndCopyPassword} title="Gerar e copiar nova senha">
        <RefreshCw className="h-4 w-4" />
      </Button>
    </div>
  </div>
                    )
                    }

                    <div>
                        <Label htmlFor="perfil">Perfil</Label>
                        <Select name="perfil" required value={formData.perfil || ''} onValueChange={(v) => handleSelectChange('perfil', v)}>
                            <SelectTrigger id="perfil"><SelectValue placeholder="Selecione o perfil" /></SelectTrigger>
                            <SelectContent>
                                <SelectItem value="professor_infantil">Professor Educação Infantil</SelectItem>
                                <SelectItem value="professor_fundamental">Professor Ensino Fundamental</SelectItem>
                                <SelectItem value="professor_especialista">Professor Especialista</SelectItem>
                                <SelectItem value="coordenador">Coordenador</SelectItem>
                                <SelectItem value="especialista">Especialista</SelectItem>
                                <SelectItem value="admin">Administrador</SelectItem>
                                {/* 'professor' é perfil legado — não oferecido em novos cadastros,
                                    mas precisa continuar selecionável aqui pra exibir corretamente
                                    o valor de usuários antigos que ainda o possuem. */}
                                {formData.perfil === 'professor' && (
                                    <SelectItem value="professor">Professor (legado)</SelectItem>
                                )}
                            </SelectContent>
                        </Select>
                    </div>
                    {specialistProfiles.includes(formData.perfil) && (
                        <>
                            <div className="space-y-2">
                                <Label htmlFor="tipo_especialista">Tipo de Especialista</Label>
                                <Select
                                    name="tipo_especialista"
                                    required
                                    value={formData.tipo_especialista || ''}
                                    onValueChange={(v) => handleSelectChange('tipo_especialista', v)}
                                >
                                    <SelectTrigger id="tipo_especialista">
                                        <SelectValue placeholder="Selecione o tipo" />
                                    </SelectTrigger>
                                <SelectContent>
                                        {tiposEspecialistaPadrao.map(tipo => (
                                            <SelectItem key={tipo.value} value={tipo.value}>{tipo.label}</SelectItem>
                                        ))}
                                        <SelectItem value={tipoEspecialistaOutro}>Outro</SelectItem>
                                    </SelectContent>
                                </Select>
                            </div>
                            {formData.tipo_especialista === tipoEspecialistaOutro && (
                                <div>
                                    <Label htmlFor="tipo_especialista_outro">Especifique o tipo</Label>
                                    <Input
                                        id="tipo_especialista_outro"
                                        name="tipo_especialista_outro"
                                        value={formData.tipo_especialista_outro || ''}
                                        onChange={handleChange}
                                        placeholder="Digite o tipo de especialista"
                                        required
                                    />
                                </div>
                            )}
                        </>
                    )}
                    {formData.perfil === PROFESSOR_FUNDAMENTAL && (
                        <div>
                            <Label>Disciplinas</Label>
                            <div className="space-y-2 rounded-md border p-4">
                                {disciplinas.length > 0 && (
                                    <div className="flex items-center space-x-2 pb-2 border-b">
                                        <Checkbox
                                            id="select-all-disciplinas"
                                            checked={disciplinas.length > 0 && formData.disciplinas?.length === disciplinas.length}
                                            onCheckedChange={handleSelectAllDisciplinas}
                                        />
                                        <Label htmlFor="select-all-disciplinas" className="font-semibold">Selecionar Todas as Disciplinas</Label>
                                    </div>
                                )}
                                <div className="max-h-32 overflow-y-auto pt-2">
                                    {disciplinas.length > 0 ? disciplinas.map(disciplina => (
                                        <div key={disciplina.id} className="flex items-center space-x-2">
                                            <Checkbox
                                                id={`disciplina-${disciplina.id}`}
                                                checked={formData.disciplinas?.includes(disciplina.id)}
                                                onCheckedChange={(checked) => handleDisciplinaChange(disciplina.id, checked)}
                                            />
                                            <Label htmlFor={`disciplina-${disciplina.id}`}>{disciplina.nome}</Label>
                                        </div>
                                    )) : <p className="text-sm text-gray-500">Nenhuma disciplina cadastrada.</p>}
                                </div>
                            </div>
                        </div>
                    )}
                    <div>
                        <Label>Turmas Vinculadas</Label>
                        <div className="space-y-2 rounded-md border p-4">
                            {turmas.length > 0 && (
                                <div className="flex items-center space-x-2 pb-2 border-b">
                                    <Checkbox
                                        id="select-all-turmas"
                                        checked={turmas.length > 0 && formData.turmas?.length === turmas.length}
                                        onCheckedChange={handleSelectAllTurmas}
                                    />
                                    <Label htmlFor="select-all-turmas" className="font-semibold">Selecionar Todas as Turmas</Label>
                                </div>
                            )}
                            <div className="max-h-32 overflow-y-auto pt-2">
                                {turmas.length > 0 ? turmas.map(turma => (
                                    <div key={turma.id} className="flex items-center space-x-2">
                                        <Checkbox
                                            id={`turma-${turma.id}`}
                                            checked={formData.turmas?.includes(turma.id)}
                                            onCheckedChange={(checked) => handleTurmaChange(turma.id, checked)}
                                        />
                                        <Label htmlFor={`turma-${turma.id}`}>{turma.nome}</Label>
                                    </div>
                                )) : <p className="text-sm text-gray-500">Nenhuma turma disponível.</p>}
                            </div>
                        </div>
                    </div>
                    <div className="flex items-center space-x-2">
                        <Checkbox id="ativo" name="ativo" checked={formData.ativo} onCheckedChange={(checked) => setFormData(p => ({...p, ativo: checked}))} />
                        <Label htmlFor="ativo">Usuário Ativo</Label>
                    </div>
                    <DialogFooter>
                        <DialogClose asChild><Button type="button" variant="outline">Cancelar</Button></DialogClose>
                        <Button type="submit">Salvar</Button>
                    </DialogFooter>
                </form>
            </DialogContent>
        </Dialog>
    );
};

export default UserFormDialog;