import React, { useState, useEffect, useCallback } from 'react';
import { PlusCircle, Edit, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useToast } from '@/components/ui/use-toast';
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogClose, DialogDescription } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { apiClient } from '@/lib/apiClient';
import { format } from 'date-fns';
import { safeFormatDate } from '@/lib/dateUtils';

const PeriodosTab = () => {
    const [periodos, setPeriodos] = useState([]);
    const [loading, setLoading] = useState(true);
    const [isFormOpen, setIsFormOpen] = useState(false);
    const [editingPeriodo, setEditingPeriodo] = useState(null);
    const [deletingPeriodo, setDeletingPeriodo] = useState(null);
    const [institutionId, setInstitutionId] = useState(null);
    const { toast } = useToast();

    const fetchInstitution = useCallback(async () => {
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

    const fetchPeriodos = useCallback(async (id) => {
        if (!id) return;
        setLoading(true);
        const { data, error } = await apiClient.from('periodos_avaliativos').select('*').eq('instituicao_id', id).order('data_inicio');
        if (error) {
            toast({ variant: "destructive", title: "Erro ao buscar períodos", description: error.message });
        } else {
            setPeriodos(data);
        }
        setLoading(false);
    }, [toast]);

    useEffect(() => {
        fetchInstitution().then(id => {
            if (id) fetchPeriodos(id);
            else setLoading(false);
        });
    }, [fetchInstitution, fetchPeriodos]);

    const handleFormSubmit = async (periodoData) => {
        let error;
        if (editingPeriodo) {
            ({ error } = await apiClient.from('periodos_avaliativos').update(periodoData).eq('id', editingPeriodo.id));
        } else {
            ({ error } = await apiClient.from('periodos_avaliativos').insert({ ...periodoData, instituicao_id: institutionId }));
        }

        if (error) {
            toast({ variant: "destructive", title: "Erro ao salvar período", description: error.message });
        } else {
            toast({ title: `Período ${editingPeriodo ? 'atualizado' : 'criado'} com sucesso!` });
            setIsFormOpen(false);
            setEditingPeriodo(null);
            fetchPeriodos(institutionId);
        }
    };

    const handleDeletePeriodo = async () => {
        if (!deletingPeriodo) return;
        const { error } = await apiClient.from('periodos_avaliativos').delete().eq('id', deletingPeriodo.id);
        if (error) {
            toast({ variant: "destructive", title: "Erro ao excluir período", description: error.message });
        } else {
            toast({ title: "Período excluído com sucesso!" });
            setDeletingPeriodo(null);
            fetchPeriodos(institutionId);
        }
    };

    const openFormForNew = () => {
        if (!institutionId) {
            toast({ variant: "destructive", title: "Cadastro de Instituição Necessário", description: "Por favor, cadastre primeiro os dados da instituição." });
            return;
        }
        setEditingPeriodo(null);
        setIsFormOpen(true);
    };

    return (
        <Card>
            <CardHeader className="flex-row items-center justify-between">
                <div>
                    <CardTitle>Períodos Avaliativos</CardTitle>
                    <CardDescription>Defina os ciclos avaliativos da sua escola.</CardDescription>
                </div>
                <Button onClick={openFormForNew}><PlusCircle className="mr-2 h-4 w-4" /> Novo Período</Button>
            </CardHeader>
            <CardContent>
                {loading ? <p>Carregando períodos...</p> : (
                    <Table>
                        <TableHeader>
                            <TableRow>
                                <TableHead>Descrição</TableHead>
                                <TableHead>Tipo</TableHead>
                                <TableHead>Data de Início</TableHead>
                                <TableHead>Data de Fim</TableHead>
                                <TableHead className="text-right">Ações</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {periodos.length > 0 ? periodos.map(periodo => (
                                <TableRow key={periodo.id}>
                                    <TableCell>{periodo.descricao}</TableCell>
                                    <TableCell className="capitalize">{periodo.tipo_periodo}</TableCell>
                                    <TableCell>{safeFormatDate(periodo.data_inicio, 'dd/MM/yyyy')}</TableCell>
                                    <TableCell>{safeFormatDate(periodo.data_fim, 'dd/MM/yyyy')}</TableCell>
                                    <TableCell className="text-right space-x-2">
                                        <Button variant="ghost" size="icon" onClick={() => { setEditingPeriodo(periodo); setIsFormOpen(true); }}>
                                            <Edit className="h-4 w-4" />
                                        </Button>
                                        <Button variant="ghost" size="icon" onClick={() => setDeletingPeriodo(periodo)}>
                                            <Trash2 className="h-4 w-4 text-red-500" />
                                        </Button>
                                    </TableCell>
                                </TableRow>
                            )) : (
                                <TableRow><TableCell colSpan={5} className="text-center">Nenhum período cadastrado.</TableCell></TableRow>
                            )}
                        </TableBody>
                    </Table>
                )}
            </CardContent>

            <PeriodoFormDialog
                isOpen={isFormOpen}
                setIsOpen={setIsFormOpen}
                periodo={editingPeriodo}
                onSubmit={handleFormSubmit}
            />

            <Dialog open={!!deletingPeriodo} onOpenChange={() => setDeletingPeriodo(null)}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Confirmar Exclusão</DialogTitle>
                        <DialogDescription>
                            Tem certeza que deseja excluir o período "{deletingPeriodo?.descricao}"? Esta ação não pode ser desfeita.
                        </DialogDescription>
                    </DialogHeader>
                    <DialogFooter>
                        <DialogClose asChild><Button variant="outline">Cancelar</Button></DialogClose>
                        <Button variant="destructive" onClick={handleDeletePeriodo}>Excluir</Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </Card>
    );
};

const PeriodoFormDialog = ({ isOpen, setIsOpen, periodo, onSubmit }) => {
    const [formData, setFormData] = useState({
        descricao: '',
        tipo_periodo: '',
        data_inicio: '',
        data_fim: '',
    });

    useEffect(() => {
        if (periodo) {
            setFormData({
                descricao: periodo.descricao || '',
                tipo_periodo: periodo.tipo_periodo || '',
                data_inicio: periodo.data_inicio || '',
                data_fim: periodo.data_fim || '',
            });
        } else {
            setFormData({
                descricao: '',
                tipo_periodo: '',
                data_inicio: '',
                data_fim: '',
            });
        }
    }, [periodo, isOpen]);
    
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
                    <DialogTitle>{periodo ? 'Editar Período' : 'Novo Período'}</DialogTitle>
                </DialogHeader>
                <form onSubmit={handleSubmit} className="space-y-4 pt-4">
                    <div>
                        <Label htmlFor="descricao">Descrição</Label>
                        <Input id="descricao" name="descricao" value={formData.descricao} onChange={handleChange} required placeholder="Ex: 1º Bimestre" />
                    </div>
                    <div>
                        <Label htmlFor="tipo_periodo">Tipo</Label>
                        <Select name="tipo_periodo" required value={formData.tipo_periodo} onValueChange={(v) => handleSelectChange('tipo_periodo', v)}>
                            <SelectTrigger id="tipo_periodo"><SelectValue placeholder="Selecione o tipo" /></SelectTrigger>
                            <SelectContent>
                                <SelectItem value="bimestral">Bimestral</SelectItem>
                                <SelectItem value="trimestral">Trimestral</SelectItem>
                                <SelectItem value="semestral">Semestral</SelectItem>
                                <SelectItem value="anual">Anual</SelectItem>
                            </SelectContent>
                        </Select>
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                        <div>
                            <Label htmlFor="data_inicio">Data de Início</Label>
                            <Input id="data_inicio" name="data_inicio" type="date" value={formData.data_inicio} onChange={handleChange} required />
                        </div>
                        <div>
                            <Label htmlFor="data_fim">Data de Fim</Label>
                            <Input id="data_fim" name="data_fim" type="date" value={formData.data_fim} onChange={handleChange} required />
                        </div>
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

export default PeriodosTab;