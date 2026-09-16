import React, { useState, useEffect } from 'react';
import { PlusCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useToast } from '@/components/ui/use-toast';
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from "@/components/ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogClose, DialogDescription } from "@/components/ui/dialog";
import { apiClient } from '@/lib/apiClient';
import { useEspecialistas } from '@/hooks/useEspecialistas';
import EspecialistaList from '@/components/admin/especialistas/EspecialistaList';
import EspecialistaFormDialog from '@/components/admin/especialistas/EspecialistaFormDialog';

const EspecialistasTab = () => {
    const { toast } = useToast();
    const {
        especialistas,
        loading,
        institutionId,
        fetchInstitutionAndData,
        tiposEspecialistaPadrao
    } = useEspecialistas();

    const [isFormOpen, setIsFormOpen] = useState(false);
    const [editingEspecialista, setEditingEspecialista] = useState(null);
    const [deletingEspecialista, setDeletingEspecialista] = useState(null);

    useEffect(() => {
        fetchInstitutionAndData(true);
    }, [fetchInstitutionAndData]);

    const handleFormSubmit = async (formData) => {
        const { password, tipo_especialista_outro, ...userFields } = formData;
        
        const finalTipoEspecialista = userFields.tipo_especialista === 'Outros' 
            ? tipo_especialista_outro.trim() 
            : userFields.tipo_especialista;

        try {
            if (editingEspecialista) {
                const { data, error } = await apiClient.from('usuarios').update({
                    nome: userFields.nome,
                    tipo_especialista: finalTipoEspecialista,
                    ativo: userFields.ativo,
                }).eq('id', editingEspecialista.id).select().single();
                if (error) throw error;
            } else {
                const createPayload = {
                    email: userFields.email,
                    password: password,
                    nome: userFields.nome,
                    perfil: 'especialista',
                    instituicao_id: institutionId,
                    tipo_especialista: finalTipoEspecialista,
                    ativo: userFields.ativo,
                };
                const { error } = await apiClient.from('usuarios').insert(createPayload);
                if (error) throw error;
            }
            
            toast({ title: `Especialista ${editingEspecialista ? 'atualizado' : 'criado'} com sucesso!` });
            setIsFormOpen(false);
            setEditingEspecialista(null);
            await fetchInstitutionAndData(true);

        } catch (error) {
            toast({ variant: "destructive", title: `Erro ao ${editingEspecialista ? 'atualizar' : 'criar'} especialista`, description: error.message });
        }
    };

    const handleDeleteEspecialista = async () => {
        if (!deletingEspecialista) return;
        
        try {
            const especialistaId = deletingEspecialista.id;
            
            await apiClient.from('especialista_funcoes').delete().eq('especialista_id', especialistaId);
            await apiClient.from('atendimentos_especialistas').delete().eq('especialista_id', especialistaId);
            
            const { error: deleteError } = await apiClient.from('usuarios').delete().eq('id', especialistaId);
            if (deleteError) throw deleteError;
            
            toast({ title: "Especialista excluído com sucesso!" });
            await fetchInstitutionAndData(true);
        } catch (error) {
            toast({ variant: "destructive", title: "Erro ao excluir especialista", description: error.message });
        } finally {
            setDeletingEspecialista(null);
        }
    };

    const openFormForNew = () => {
        if (!institutionId) {
            toast({ variant: "destructive", title: "Cadastro de Instituição Necessário", description: "Por favor, cadastre primeiro os dados da instituição." });
            return;
        }
        setEditingEspecialista(null);
        setIsFormOpen(true);
    };

    const handleEdit = (especialista) => {
        setEditingEspecialista(especialista);
        setIsFormOpen(true);
    };

    const handleDelete = (especialista) => {
        setDeletingEspecialista(especialista);
    };

    return (
        <Card>
            <CardHeader className="flex-row items-center justify-between">
                <div>
                    <CardTitle>Gestão de Especialistas</CardTitle>
                    <CardDescription>Adicione, edite e gerencie os especialistas da sua escola.</CardDescription>
                </div>
                <Button onClick={openFormForNew}><PlusCircle className="mr-2 h-4 w-4" /> Novo Especialista</Button>
            </CardHeader>
            <CardContent>
                <EspecialistaList
                    loading={loading}
                    especialistas={especialistas}
                    onEdit={handleEdit}
                    onDelete={handleDelete}
                />
            </CardContent>

            <EspecialistaFormDialog
                isOpen={isFormOpen}
                setIsOpen={setIsFormOpen}
                especialista={editingEspecialista}
                onSubmit={handleFormSubmit}
                tiposEspecialistaPadrao={tiposEspecialistaPadrao}
            />

            <Dialog open={!!deletingEspecialista} onOpenChange={() => setDeletingEspecialista(null)}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Confirmar Exclusão</DialogTitle>
                        <DialogDescription>
                            Tem certeza que deseja excluir o especialista "{deletingEspecialista?.nome}"? Esta ação é irreversível e removerá todos os dados associados.
                        </DialogDescription>
                    </DialogHeader>
                    <DialogFooter>
                        <DialogClose asChild><Button variant="outline">Cancelar</Button></DialogClose>
                        <Button variant="destructive" onClick={handleDeleteEspecialista}>Excluir</Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </Card>
    );
};

export default EspecialistasTab;
