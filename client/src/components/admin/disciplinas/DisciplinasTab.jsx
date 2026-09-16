import React, { useState, useEffect, useCallback } from 'react';
import { PlusCircle, ChevronLeft, ChevronRight } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { toast } from '@/components/ui/use-toast';
import { Card, CardHeader, CardTitle, CardContent, CardDescription, CardFooter } from "@/components/ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogClose, DialogDescription } from "@/components/ui/dialog";
import { apiClient } from '@/lib/apiClient';
import DisciplinaList from '@/components/admin/disciplinas/DisciplinaList';
import DisciplinaFormDialog from '@/components/admin/disciplinas/DisciplinaFormDialog';

const PAGE_SIZE = 15;

const DisciplinasTab = () => {
    const [disciplinas, setDisciplinas] = useState([]);
    const [totalDisciplinas, setTotalDisciplinas] = useState(0);
    const [currentPage, setCurrentPage] = useState(1);
    const [loading, setLoading] = useState(true);
    const [isFormOpen, setIsFormOpen] = useState(false);
    const [editingDisciplina, setEditingDisciplina] = useState(null);
    const [deletingDisciplina, setDeletingDisciplina] = useState(null);
    const [institutionId, setInstitutionId] = useState(null);

    const totalPages = Math.max(1, Math.ceil(totalDisciplinas / PAGE_SIZE));

    const fetchDisciplinas = useCallback(async (currentInstitutionId, page) => {
        const { data, count, error } = await apiClient
            .from('disciplinas')
            .select('*', { count: 'exact' })
            .eq('instituicao_id', currentInstitutionId)
            .order('nome')
            .limit(PAGE_SIZE)
            .page(page);
        if (error) throw error;
        setDisciplinas(Array.isArray(data) ? data : []);
        setTotalDisciplinas(count ?? (Array.isArray(data) ? data.length : 0));
    }, []);

    const fetchInstitutionAndData = useCallback(async (forceRefetch = false, page = currentPage) => {
        setLoading(true);
        try {
            let currentInstitutionId = institutionId;
            if (!currentInstitutionId || forceRefetch) {
                const { data: instData, error: instError } = await apiClient.from('instituicoes').select('id').limit(1).single();
                if (instError && instError.code !== 'PGRST116') throw instError;
                if (!instData) {
                    setLoading(false);
                    return;
                }
                setInstitutionId(instData.id);
                currentInstitutionId = instData.id;
            }

            await fetchDisciplinas(currentInstitutionId, page);

        } catch (error) {
            toast({ variant: "destructive", title: "Erro ao carregar disciplinas", description: error.message });
        } finally {
            setLoading(false);
        }
    }, [institutionId, currentPage, fetchDisciplinas]);

    useEffect(() => {
        fetchInstitutionAndData(true, 1);
        setCurrentPage(1);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const goToPage = async (page) => {
        if (page < 1 || page > totalPages || !institutionId) return;
        setCurrentPage(page);
        setLoading(true);
        try {
            await fetchDisciplinas(institutionId, page);
        } catch (error) {
            toast({ variant: "destructive", title: "Erro ao carregar disciplinas", description: error.message });
        } finally {
            setLoading(false);
        }
    };

    const handleFormSubmit = async (disciplinaData) => {
        const isCreating = !editingDisciplina;
        try {
            if (editingDisciplina) {
                const { error } = await apiClient
                    .from('disciplinas')
                    .update({ nome: disciplinaData.nome, ativo: disciplinaData.ativo })
                    .eq('id', editingDisciplina.id)
                    .select()
                    .single();
                if (error) throw error;
            } else {
                const { error } = await apiClient
                    .from('disciplinas')
                    .insert({
                        nome: disciplinaData.nome,
                        ativo: disciplinaData.ativo,
                        instituicao: institutionId,
                    })
                    .select()
                    .single();
                if (error) throw error;
            }

            toast({ title: `Disciplina ${editingDisciplina ? 'atualizada' : 'criada'} com sucesso!` });
            setIsFormOpen(false);
            setEditingDisciplina(null);

            // Criação: como a lista é ordenada por nome (não por criação), a nova
            // disciplina pode cair em qualquer página — volta pra página 1 é a
            // opção mais previsível. Edição: mantém a página atual.
            const targetPage = isCreating ? 1 : currentPage;
            setCurrentPage(targetPage);
            await fetchDisciplinas(institutionId, targetPage);

        } catch (error) {
            toast({ variant: "destructive", title: `Erro ao ${editingDisciplina ? 'atualizar' : 'criar'} disciplina`, description: error.message });
        }
    };

    const handleDeleteDisciplina = async () => {
        if (!deletingDisciplina) return;
        try {
            const { error } = await apiClient.from('disciplinas').delete().eq('id', deletingDisciplina.id);
            if (error) throw error;

            toast({ title: "Disciplina excluída com sucesso!" });
            setDeletingDisciplina(null);

            // Se essa era a última linha da página (e não é a página 1), volta
            // uma página pra não ficar numa página vazia.
            const targetPage = (disciplinas.length === 1 && currentPage > 1) ? currentPage - 1 : currentPage;
            setCurrentPage(targetPage);
            await fetchDisciplinas(institutionId, targetPage);
        } catch (error) {
            toast({ variant: "destructive", title: "Erro ao excluir disciplina", description: error.message });
        }
    };

    const openFormForNew = () => {
        if (!institutionId) {
            toast({ variant: "destructive", title: "Cadastro de Instituição Necessário", description: "Por favor, cadastre primeiro os dados da instituição." });
            return;
        }
        setEditingDisciplina(null);
        setIsFormOpen(true);
    };

    const handleEdit = (disciplina) => {
        setEditingDisciplina(disciplina);
        setIsFormOpen(true);
    };

    const handleDelete = (disciplina) => {
        setDeletingDisciplina(disciplina);
    };

    return (
        <Card>
            <CardHeader className="flex-row items-center justify-between">
                <div>
                    <CardTitle>Gerenciamento de Disciplinas</CardTitle>
                    <CardDescription>Catálogo de disciplinas disponíveis para vincular a professores do Ensino Fundamental.</CardDescription>
                </div>
                <Button onClick={openFormForNew}><PlusCircle className="mr-2 h-4 w-4" /> Nova Disciplina</Button>
            </CardHeader>
            <CardContent>
                <DisciplinaList
                    loading={loading}
                    disciplinas={disciplinas}
                    onEdit={handleEdit}
                    onDelete={handleDelete}
                />
            </CardContent>
            <CardFooter className="flex items-center justify-between">
                <p className="text-sm text-gray-500">
                    {totalDisciplinas > 0
                        ? `${totalDisciplinas} disciplina${totalDisciplinas !== 1 ? 's' : ''} — página ${currentPage} de ${totalPages}`
                        : 'Nenhuma disciplina cadastrada.'}
                </p>
                <div className="flex items-center gap-2">
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={() => goToPage(currentPage - 1)}
                        disabled={currentPage <= 1 || loading}
                    >
                        <ChevronLeft className="h-4 w-4 mr-1" /> Anterior
                    </Button>
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={() => goToPage(currentPage + 1)}
                        disabled={currentPage >= totalPages || loading}
                    >
                        Próxima <ChevronRight className="h-4 w-4 ml-1" />
                    </Button>
                </div>
            </CardFooter>

            <DisciplinaFormDialog
                isOpen={isFormOpen}
                setIsOpen={setIsFormOpen}
                disciplina={editingDisciplina}
                onSubmit={handleFormSubmit}
            />

            <Dialog open={!!deletingDisciplina} onOpenChange={() => setDeletingDisciplina(null)}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Confirmar Exclusão</DialogTitle>
                        <DialogDescription>
                            Tem certeza que deseja excluir a disciplina "{deletingDisciplina?.nome}"? Isso também removerá o vínculo dela com qualquer professor que a esteja lecionando. Considere apenas desativá-la (editar → desmarcar "Ativa") se preferir manter o histórico.
                        </DialogDescription>
                    </DialogHeader>
                    <DialogFooter>
                        <DialogClose asChild><Button variant="outline">Cancelar</Button></DialogClose>
                        <Button variant="destructive" onClick={handleDeleteDisciplina}>Excluir</Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </Card>
    );
};

export default DisciplinasTab;