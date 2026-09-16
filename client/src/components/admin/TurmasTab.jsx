import React, { useState, useEffect, useCallback } from 'react';
import { PlusCircle, Edit, Trash2, UserPlus } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { toast } from '@/components/ui/use-toast';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogClose, DialogDescription } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { apiClient } from '@/lib/apiClient';
import { PERFIS_PROFESSOR } from '@/constants/perfis';

const TurmasTab = () => {
    const navigate = useNavigate();
    const [turmas, setTurmas] = useState([]);
    const [professores, setProfessores] = useState([]);
    const [seriesConfig, setSeriesConfig] = useState([]);
    const [loading, setLoading] = useState(true);
    const [isFormOpen, setIsFormOpen] = useState(false);
    const [editingTurma, setEditingTurma] = useState(null);
    const [deletingTurma, setDeletingTurma] = useState(null);
    const [institutionId, setInstitutionId] = useState(null);

    const fetchSeriesConfig = useCallback(async () => {
        const { data, error } = await apiClient
            .from('series_config')
            .select('*')
            .eq('ativa', true)
            .order('ordem');

        if (!error && data) {
            setSeriesConfig(Array.isArray(data) ? data : []);
        }
    }, []);

    const fetchCommonData = useCallback(async (id) => {
        if (!id) return;

        const { data: profData, error: profError } = await apiClient
            .from('usuarios')
            .select('id, nome')
            .eq('instituicao_id', id)
            .in('perfil', ['professor', 'professor_especialista', 'coordenador']);

        if (profError) {
            toast({ variant: "destructive", title: "Erro ao buscar professores", description: profError.message });
        } else {
            setProfessores(Array.isArray(profData) ? profData : []);
        }
    }, []);

    const fetchTurmas = useCallback(async (id) => {
        if (!id) return;
        setLoading(true);
        const { data, error } = await apiClient
            .from('turmas')
            .select('*, usuario_turmas(usuarios(id, nome, perfil))')
            .eq('instituicao_id', id)
            .order('created_at');
        
        if (error) {
            toast({ variant: "destructive", title: "Erro ao buscar turmas", description: error.message });
        } else {
            const turmasList = Array.isArray(data) ? data : [];
            const turmasComProfessor = turmasList.map(turma => {
                const professorLink = (turma.usuario_turmas ?? []).find(ut => ut.usuarios && (
                    PERFIS_PROFESSOR.includes(ut.usuarios.perfil)
                    || ut.usuarios.perfil === 'coordenador'
                ));
                return {
                    ...turma,
                    professor_nome: professorLink ? professorLink.usuarios.nome : 'Não associado',
                    professor_id: professorLink ? professorLink.usuarios.id : null,
                };
            });
            setTurmas(turmasComProfessor);
        }
        setLoading(false);
    }, []);

    const fetchInstitutionAndData = useCallback(async () => {
        setLoading(true);
        const { data, error } = await apiClient.from('instituicoes').select('id').limit(1).single();
        if (error && error.code !== 'PGRST116') {
            toast({ variant: "destructive", title: "Erro ao buscar instituição", description: error.message });
            setLoading(false);
            return;
        }

        if (data) {
            setInstitutionId(data.id);
            await Promise.all([
                fetchTurmas(data.id),
                fetchCommonData(data.id),
                fetchSeriesConfig(),
            ]);
        } else {
            setLoading(false);
        }
    }, [fetchTurmas, fetchCommonData, fetchSeriesConfig]);

    useEffect(() => {
        fetchInstitutionAndData();
    }, [fetchInstitutionAndData]);

    const handleFormSubmit = async ({ professor_id, ...turmaData }) => {
        let savedTurma;
        let error;

        const { id, created_at, professor_nome, ...cleanTurmaData } = turmaData;

        if (editingTurma) {
            ({ data: savedTurma, error } = await apiClient.from('turmas').update(cleanTurmaData).eq('id', editingTurma.id).select().single());
        } else {
            ({ data: savedTurma, error } = await apiClient.from('turmas').insert({ ...cleanTurmaData, instituicao_id: institutionId }).select().single());
        }

        if (error) {
            toast({ variant: "destructive", title: "Erro ao salvar turma", description: error.message });
            return;
        }
        
        const currentProfessorId = editingTurma?.professor_id;
        
        if (currentProfessorId !== professor_id) {
            if (currentProfessorId) {
                const { error: deleteError } = await apiClient.from('usuario_turmas').delete().match({ turma_id: savedTurma.id, usuario_id: currentProfessorId });
                if (deleteError) {
                    toast({ variant: "destructive", title: "Erro ao desvincular professor antigo", description: deleteError.message });
                    return;
                }
            }
            if (professor_id && professor_id !== 'nenhum') {
                const { error: linkError } = await apiClient.from('usuario_turmas').insert({ turma_id: savedTurma.id, usuario_id: professor_id });
                if (linkError && linkError.code !== '23505') { // Ignore duplicate key error
                    toast({ variant: "destructive", title: "Erro ao vincular novo professor", description: linkError.message });
                    return;
                }
            }
        }

        toast({ title: `Turma ${editingTurma ? 'atualizada' : 'criada'} com sucesso!` });
        setIsFormOpen(false);
        setEditingTurma(null);
        fetchTurmas(institutionId);
    };

    const handleDeleteTurma = async () => {
        if (!deletingTurma) return;
        
        await apiClient.from('usuario_turmas').delete().eq('turma_id', deletingTurma.id);
        const { error } = await apiClient.from('turmas').delete().eq('id', deletingTurma.id);

        if (error) {
            toast({ variant: "destructive", title: "Erro ao excluir turma", description: error.message });
        } else {
            toast({ title: "Turma excluída com sucesso!" });
            setDeletingTurma(null);
            fetchTurmas(institutionId);
        }
    };
    
    const openFormForNew = () => {
        if (!institutionId) {
            toast({ variant: "destructive", title: "Cadastro de Instituição Necessário", description: "Por favor, cadastre primeiro os dados da instituição." });
            return;
        }
        setEditingTurma(null);
        setIsFormOpen(true);
    };

    const handleAddStudents = (turmaId) => {
        navigate(`/admin/alunos?turma_id=${turmaId}`);
    };

    return (
        <Card>
            <CardHeader className="flex-row items-center justify-between">
                <div>
                    <CardTitle>Gerenciamento de Turmas</CardTitle>
                    <CardDescription>Adicione, edite ou remova as turmas da sua escola.</CardDescription>
                </div>
                <Button onClick={openFormForNew}><PlusCircle className="mr-2 h-4 w-4" /> Nova Turma</Button>
            </CardHeader>
            <CardContent>
                {loading ? <p>Carregando turmas...</p> : (
                    <TooltipProvider>
                        <Table>
                            <TableHeader>
                                <TableRow>
                                    <TableHead>Nome</TableHead>
                                    <TableHead>Faixa Etária</TableHead>
                                    <TableHead>Turno</TableHead>
                                    <TableHead>Professor(a)</TableHead>
                                    <TableHead>Ano Letivo</TableHead>
                                    <TableHead className="text-right">Ações</TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {turmas.length > 0 ? turmas.map(turma => (
                                    <TableRow key={turma.id}>
                                        <TableCell>{turma.nome}</TableCell>
                                        <TableCell>{turma.faixa_etaria}</TableCell>
                                        <TableCell className="capitalize">{turma.turno}</TableCell>
                                        <TableCell>{turma.professor_nome}</TableCell>
                                        <TableCell>{turma.ano_letivo}</TableCell>
                                        <TableCell className="text-right space-x-2">
                                            <Tooltip>
                                                <TooltipTrigger asChild>
                                                    <Button variant="ghost" size="icon" onClick={() => handleAddStudents(turma.id)} aria-label="Cadastrar alunos para esta turma">
                                                        <UserPlus className="h-4 w-4 text-blue-500" />
                                                    </Button>
                                                </TooltipTrigger>
                                                <TooltipContent><p>Cadastrar Alunos</p></TooltipContent>
                                            </Tooltip>
                                            <Tooltip>
                                                <TooltipTrigger asChild>
                                                    <Button variant="ghost" size="icon" onClick={() => { setEditingTurma(turma); setIsFormOpen(true); }} aria-label="Editar turma">
                                                        <Edit className="h-4 w-4" />
                                                    </Button>
                                                </TooltipTrigger>
                                                <TooltipContent><p>Editar Turma</p></TooltipContent>
                                            </Tooltip>
                                            <Tooltip>
                                                <TooltipTrigger asChild>
                                                     <Button variant="ghost" size="icon" onClick={() => setDeletingTurma(turma)} aria-label="Excluir turma">
                                                        <Trash2 className="h-4 w-4 text-red-500" />
                                                    </Button>
                                                </TooltipTrigger>
                                                <TooltipContent><p>Excluir Turma</p></TooltipContent>
                                            </Tooltip>
                                        </TableCell>
                                    </TableRow>
                                )) : (
                                    <TableRow><TableCell colSpan={6} className="text-center">Nenhuma turma cadastrada.</TableCell></TableRow>
                                )}
                            </TableBody>
                        </Table>
                    </TooltipProvider>
                )}
            </CardContent>

            <TurmaFormDialog
                isOpen={isFormOpen}
                setIsOpen={setIsFormOpen}
                turma={editingTurma}
                professores={professores}
                seriesConfig={seriesConfig}
                onSubmit={handleFormSubmit}
            />

            <Dialog open={!!deletingTurma} onOpenChange={() => setDeletingTurma(null)}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Confirmar Exclusão</DialogTitle>
                        <DialogDescription>
                            Tem certeza que deseja excluir a turma "{deletingTurma?.nome}"? Esta ação não pode ser desfeita.
                        </DialogDescription>
                    </DialogHeader>
                    <DialogFooter>
                        <DialogClose asChild><Button variant="outline">Cancelar</Button></DialogClose>
                        <Button variant="destructive" onClick={handleDeleteTurma}>Excluir</Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </Card>
    );
};

const ETAPA_LABELS = {
    educacao_infantil: 'Educação Infantil',
    ensino_fundamental: 'Ensino Fundamental',
};

const TurmaFormDialog = ({ isOpen, setIsOpen, turma, professores, seriesConfig = [], onSubmit }) => {
    const [formData, setFormData] = useState({
        nome: '',
        faixa_etaria: '',
        turno: '',
        ano_letivo: new Date().getFullYear().toString(),
        professor_id: '',
    });

    useEffect(() => {
        if (turma) {
            setFormData({
                nome: turma.nome || '',
                faixa_etaria: turma.faixa_etaria || '',
                turno: turma.turno || '',
                ano_letivo: turma.ano_letivo?.toString() || new Date().getFullYear().toString(),
                professor_id: turma.professor_id || '',
            });
        } else {
            setFormData({
                nome: '',
                faixa_etaria: '',
                turno: '',
                ano_letivo: new Date().getFullYear().toString(),
                professor_id: '',
            });
        }
    }, [turma, isOpen]);
    
    const handleChange = (e) => {
        const { name, value } = e.target;
        setFormData(prev => ({ ...prev, [name]: value }));
    };

    const handleSelectChange = (name, value) => {
        setFormData(prev => ({...prev, [name]: value}));
    }

    const handleSubmit = (e) => {
        e.preventDefault();
        onSubmit(formData);
    };

    return (
        <Dialog open={isOpen} onOpenChange={setIsOpen}>
            <DialogContent>
                <DialogHeader>
                    <DialogTitle>{turma ? 'Editar Turma' : 'Nova Turma'}</DialogTitle>
                </DialogHeader>
                <form onSubmit={handleSubmit} className="space-y-4 pt-4">
                    <div>
                        <Label htmlFor="nome">Nome da Turma</Label>
                        <Input id="nome" name="nome" value={formData.nome} onChange={handleChange} required />
                    </div>
                    <div>
                        <Label htmlFor="faixa_etaria">Faixa Etária / Série</Label>
                        <Select name="faixa_etaria" required value={formData.faixa_etaria} onValueChange={(v) => handleSelectChange('faixa_etaria', v)}>
                            <SelectTrigger id="faixa_etaria"><SelectValue placeholder="Selecione a faixa etária" /></SelectTrigger>
                            <SelectContent>
                                {seriesConfig.length > 0 ? (
                                    Object.entries(
                                        seriesConfig.reduce((acc, s) => {
                                            if (!acc[s.etapa]) acc[s.etapa] = [];
                                            acc[s.etapa].push(s);
                                            return acc;
                                        }, {})
                                    ).map(([etapa, items]) => (
                                        <React.Fragment key={etapa}>
                                            <SelectItem value={`__group_${etapa}`} disabled className="text-xs font-semibold text-muted-foreground uppercase">
                                                {ETAPA_LABELS[etapa] || etapa}
                                            </SelectItem>
                                            {items.map(s => (
                                                <SelectItem key={s.id} value={s.nome}>
                                                    {s.nome}{s.idade_min != null && s.idade_max != null ? ` (${s.idade_min}–${s.idade_max} anos)` : ''}
                                                </SelectItem>
                                            ))}
                                        </React.Fragment>
                                    ))
                                ) : (
                                    <>
                                        <SelectItem value="Nível 1">Nível 1</SelectItem>
                                        <SelectItem value="Nível 2">Nível 2</SelectItem>
                                        <SelectItem value="Nível 3">Nível 3</SelectItem>
                                        <SelectItem value="Nível 4">Nível 4</SelectItem>
                                        <SelectItem value="Nível 5">Nível 5</SelectItem>
                                    </>
                                )}
                            </SelectContent>
                        </Select>
                    </div>
                    <div>
                        <Label htmlFor="turno">Turno</Label>
                        <Select name="turno" required value={formData.turno} onValueChange={(v) => handleSelectChange('turno', v)}>
                            <SelectTrigger id="turno"><SelectValue placeholder="Selecione o turno" /></SelectTrigger>
                            <SelectContent>
                                <SelectItem value="manha">Manhã</SelectItem>
                                <SelectItem value="tarde">Tarde</SelectItem>
                                <SelectItem value="integral">Integral</SelectItem>
                            </SelectContent>
                        </Select>
                    </div>
                    <div>
                        <Label htmlFor="professor_id">Professor(a) Responsável</Label>
                        <Select name="professor_id" value={formData.professor_id || 'nenhum'} onValueChange={(v) => handleSelectChange('professor_id', v)}>
                            <SelectTrigger id="professor_id"><SelectValue placeholder="Selecione um professor" /></SelectTrigger>
                            <SelectContent>
                                <SelectItem value="nenhum">Nenhum</SelectItem>
                                {professores.map(p => <SelectItem key={p.id} value={p.id}>{p.nome}</SelectItem>)}
                            </SelectContent>
                        </Select>
                    </div>
                    <div>
                        <Label htmlFor="ano_letivo">Ano Letivo</Label>
                        <Input id="ano_letivo" name="ano_letivo" type="number" value={formData.ano_letivo} onChange={handleChange} required />
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

export default TurmasTab;
