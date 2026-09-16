import React, { useState, useEffect, useCallback } from 'react';
import { PlusCircle, Edit, Trash2, GraduationCap } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { toast } from '@/components/ui/use-toast';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogClose, DialogDescription } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { apiClient } from '@/lib/apiClient';

const ETAPA_LABELS = {
    educacao_infantil: 'Educação Infantil',
    ensino_fundamental: 'Ensino Fundamental',
};

const SeriesTab = () => {
    const [series, setSeries] = useState([]);
    const [loading, setLoading] = useState(true);
    const [isFormOpen, setIsFormOpen] = useState(false);
    const [editingSerie, setEditingSerie] = useState(null);
    const [deletingSerie, setDeletingSerie] = useState(null);

    const fetchSeries = useCallback(async () => {
        setLoading(true);
        const { data, error } = await apiClient
            .from('series_config')
            .select('*')
            .eq('ativa', true)
            .order('ordem');

        if (error) {
            toast({ variant: "destructive", title: "Erro ao buscar séries", description: error.message });
        } else {
            setSeries(Array.isArray(data) ? data : []);
        }
        setLoading(false);
    }, []);

    useEffect(() => {
        fetchSeries();
    }, [fetchSeries]);

    const handleFormSubmit = async (formData) => {
        let error;

        if (editingSerie) {
            ({ error } = await apiClient
                .from('series_config')
                .update(formData)
                .eq('id', editingSerie.id));
        } else {
            ({ error } = await apiClient
                .from('series_config')
                .insert(formData));
        }

        if (error) {
            toast({ variant: "destructive", title: "Erro ao salvar série", description: error.message });
            return;
        }

        toast({ title: `Série ${editingSerie ? 'atualizada' : 'criada'} com sucesso!` });
        setIsFormOpen(false);
        setEditingSerie(null);
        fetchSeries();
    };

    const handleDeleteSerie = async () => {
        if (!deletingSerie) return;

        const { error } = await apiClient
            .from('series_config')
            .delete()
            .eq('id', deletingSerie.id);

        if (error) {
            toast({ variant: "destructive", title: "Erro ao desativar série", description: error.message });
        } else {
            toast({ title: "Série desativada com sucesso!" });
            setDeletingSerie(null);
            fetchSeries();
        }
    };

    return (
        <Card>
            <CardHeader className="flex-row items-center justify-between">
                <div>
                    <CardTitle>Gerenciamento de Séries</CardTitle>
                    <CardDescription>Configure as séries/faixas etárias disponíveis para as turmas.</CardDescription>
                </div>
                <Button onClick={() => { setEditingSerie(null); setIsFormOpen(true); }}>
                    <PlusCircle className="mr-2 h-4 w-4" /> Nova Série
                </Button>
            </CardHeader>
            <CardContent>
                {loading ? <p>Carregando séries...</p> : (
                    <TooltipProvider>
                        <Table>
                            <TableHeader>
                                <TableRow>
                                    <TableHead>Nome</TableHead>
                                    <TableHead>Etapa</TableHead>
                                    <TableHead>Faixa Etária</TableHead>
                                    <TableHead>Ordem</TableHead>
                                    <TableHead className="text-right">Ações</TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {series.length > 0 ? series.map(serie => (
                                    <TableRow key={serie.id}>
                                        <TableCell className="font-medium">
                                            <div className="flex items-center gap-2">
                                                <GraduationCap className="h-4 w-4 text-purple-500" />
                                                {serie.nome}
                                            </div>
                                        </TableCell>
                                        <TableCell>
                                            <Badge variant={serie.etapa === 'educacao_infantil' ? 'default' : 'secondary'}>
                                                {ETAPA_LABELS[serie.etapa] || serie.etapa}
                                            </Badge>
                                        </TableCell>
                                        <TableCell>
                                            {serie.idade_min != null && serie.idade_max != null
                                                ? `${serie.idade_min}–${serie.idade_max} anos`
                                                : '—'}
                                        </TableCell>
                                        <TableCell>{serie.ordem}</TableCell>
                                        <TableCell className="text-right space-x-2">
                                            <Tooltip>
                                                <TooltipTrigger asChild>
                                                    <Button variant="ghost" size="icon" onClick={() => { setEditingSerie(serie); setIsFormOpen(true); }}>
                                                        <Edit className="h-4 w-4" />
                                                    </Button>
                                                </TooltipTrigger>
                                                <TooltipContent><p>Editar Série</p></TooltipContent>
                                            </Tooltip>
                                            <Tooltip>
                                                <TooltipTrigger asChild>
                                                    <Button variant="ghost" size="icon" onClick={() => setDeletingSerie(serie)}>
                                                        <Trash2 className="h-4 w-4 text-red-500" />
                                                    </Button>
                                                </TooltipTrigger>
                                                <TooltipContent><p>Desativar Série</p></TooltipContent>
                                            </Tooltip>
                                        </TableCell>
                                    </TableRow>
                                )) : (
                                    <TableRow>
                                        <TableCell colSpan={5} className="text-center">Nenhuma série cadastrada.</TableCell>
                                    </TableRow>
                                )}
                            </TableBody>
                        </Table>
                    </TooltipProvider>
                )}
            </CardContent>

            <SerieFormDialog
                isOpen={isFormOpen}
                setIsOpen={setIsFormOpen}
                serie={editingSerie}
                onSubmit={handleFormSubmit}
            />

            <Dialog open={!!deletingSerie} onOpenChange={() => setDeletingSerie(null)}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Confirmar Desativação</DialogTitle>
                        <DialogDescription>
                            Tem certeza que deseja desativar a série "{deletingSerie?.nome}"? Turmas existentes com esta série não serão afetadas.
                        </DialogDescription>
                    </DialogHeader>
                    <DialogFooter>
                        <DialogClose asChild><Button variant="outline">Cancelar</Button></DialogClose>
                        <Button variant="destructive" onClick={handleDeleteSerie}>Desativar</Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </Card>
    );
};

const SerieFormDialog = ({ isOpen, setIsOpen, serie, onSubmit }) => {
    const [formData, setFormData] = useState({
        nome: '',
        etapa: '',
        ordem: 0,
        idade_min: '',
        idade_max: '',
    });

    useEffect(() => {
        if (serie) {
            setFormData({
                nome: serie.nome || '',
                etapa: serie.etapa || '',
                ordem: serie.ordem ?? 0,
                idade_min: serie.idade_min ?? '',
                idade_max: serie.idade_max ?? '',
            });
        } else {
            setFormData({
                nome: '',
                etapa: '',
                ordem: 0,
                idade_min: '',
                idade_max: '',
            });
        }
    }, [serie, isOpen]);

    const handleChange = (e) => {
        const { name, value } = e.target;
        setFormData(prev => ({ ...prev, [name]: value }));
    };

    const handleSubmit = (e) => {
        e.preventDefault();
        onSubmit({
            ...formData,
            ordem: parseInt(formData.ordem, 10) || 0,
            idade_min: formData.idade_min !== '' ? parseInt(formData.idade_min, 10) : null,
            idade_max: formData.idade_max !== '' ? parseInt(formData.idade_max, 10) : null,
        });
    };

    return (
        <Dialog open={isOpen} onOpenChange={setIsOpen}>
            <DialogContent>
                <DialogHeader>
                    <DialogTitle>{serie ? 'Editar Série' : 'Nova Série'}</DialogTitle>
                </DialogHeader>
                <form onSubmit={handleSubmit} className="space-y-4 pt-4">
                    <div>
                        <Label htmlFor="nome">Nome da Série</Label>
                        <Input id="nome" name="nome" value={formData.nome} onChange={handleChange} placeholder="Ex: Nível 1, 1º ANO" required />
                    </div>
                    <div>
                        <Label htmlFor="etapa">Etapa de Ensino</Label>
                        <Select name="etapa" required value={formData.etapa} onValueChange={(v) => setFormData(prev => ({ ...prev, etapa: v }))}>
                            <SelectTrigger id="etapa"><SelectValue placeholder="Selecione a etapa" /></SelectTrigger>
                            <SelectContent>
                                <SelectItem value="educacao_infantil">Educação Infantil</SelectItem>
                                <SelectItem value="ensino_fundamental">Ensino Fundamental</SelectItem>
                            </SelectContent>
                        </Select>
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                        <div>
                            <Label htmlFor="idade_min">Idade Mínima (anos)</Label>
                            <Input id="idade_min" name="idade_min" type="number" min="0" max="18" value={formData.idade_min} onChange={handleChange} />
                        </div>
                        <div>
                            <Label htmlFor="idade_max">Idade Máxima (anos)</Label>
                            <Input id="idade_max" name="idade_max" type="number" min="0" max="18" value={formData.idade_max} onChange={handleChange} />
                        </div>
                    </div>
                    <div>
                        <Label htmlFor="ordem">Ordem de Exibição</Label>
                        <Input id="ordem" name="ordem" type="number" value={formData.ordem} onChange={handleChange} required />
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

export default SeriesTab;
