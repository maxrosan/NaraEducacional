import React, { useState, useEffect, useCallback } from 'react';
import { PlusCircle, ChevronLeft, ChevronRight } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { toast } from '@/components/ui/use-toast';
import { Card, CardHeader, CardTitle, CardContent, CardDescription, CardFooter } from "@/components/ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogClose, DialogDescription } from "@/components/ui/dialog";
import { apiClient } from '@/lib/apiClient';
import UserList from '@/components/admin/usuarios/UserList';
import UserFormDialog from '@/components/admin/usuarios/UserFormDialog';

const PROFESSOR_FUNDAMENTAL = 'professor_fundamental';
const PAGE_SIZE = 15;

const UsuariosTab = () => {
    const [usuarios, setUsuarios] = useState([]);
    const [totalUsuarios, setTotalUsuarios] = useState(0);
    const [currentPage, setCurrentPage] = useState(1);
    const [turmas, setTurmas] = useState([]);
    const [disciplinas, setDisciplinas] = useState([]);
    const [loading, setLoading] = useState(true);
    const [isFormOpen, setIsFormOpen] = useState(false);
    const [editingUser, setEditingUser] = useState(null);
    const [deletingUser, setDeletingUser] = useState(null);
    const [institutionId, setInstitutionId] = useState(null);

    const totalPages = Math.max(1, Math.ceil(totalUsuarios / PAGE_SIZE));

    // Usuários vêm paginados (15 por página, mais recentes primeiro). Turmas e
    // disciplinas continuam sendo buscadas por inteiro — são catálogos
    // pequenos, usados só pra popular os checkboxes do formulário.
    const fetchUsuarios = useCallback(async (currentInstitutionId, page) => {
        const { data, count, error } = await apiClient
            .from('usuarios')
            .select('id, nome, email, perfil, tipo_especialista, ativo, usuario_turmas!left(turma_id), permissoes_esp', { count: 'exact' })
            .eq('instituicao_id', currentInstitutionId)
            .order('created_at', { ascending: false })
            .limit(PAGE_SIZE)
            .page(page);
        if (error) throw error;
        const usuariosList = Array.isArray(data) ? data : [];
        setUsuarios(usuariosList.map(u => ({
            ...u,
            turmas: (u.usuario_turmas ?? []).map(ut => ut.turma_id),
        })));
        setTotalUsuarios(count ?? usuariosList.length);
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

            await fetchUsuarios(currentInstitutionId, page);

            const { data: turmasData, error: turmasError } = await apiClient.from('turmas').select('*').eq('instituicao_id', currentInstitutionId);
            if (turmasError) throw turmasError;
            setTurmas(Array.isArray(turmasData) ? turmasData : []);

            // .limit(100) garante a lista completa numa página só — disciplinas
            // é um catálogo curricular pequeno e limitado por natureza, então
            // não vale a pena implementar UI de paginação pra isso.
            const { data: disciplinasData, error: disciplinasError } = await apiClient.from('disciplinas').select('*').eq('instituicao_id', currentInstitutionId).limit(100);
            if (disciplinasError) throw disciplinasError;
            setDisciplinas(Array.isArray(disciplinasData) ? disciplinasData : []);

        } catch (error) {
            toast({ variant: "destructive", title: "Erro ao carregar dados", description: error.message });
        } finally {
            setLoading(false);
        }
    }, [institutionId, currentPage, fetchUsuarios]);

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
            await fetchUsuarios(institutionId, page);
        } catch (error) {
            toast({ variant: "destructive", title: "Erro ao carregar usuários", description: error.message });
        } finally {
            setLoading(false);
        }
    };

    const handleFormSubmit = async (userData) => {
        const { turmas: newTurmasIds, disciplinas: newDisciplinasIds, password, tipo_especialista_outro, ...userFields } = userData;
        let savedUser;
        const isCreating = !editingUser;

        const isSpecialistProfile = ['especialista', 'professor_especialista'].includes(userFields.perfil);
        const finalTipoEspecialista = userFields.tipo_especialista === 'outro'
            ? 'outro'
            : userFields.tipo_especialista;

        const userPayload = {
            nome: userFields.nome,
            perfil: userFields.perfil,
            ativo: userFields.ativo,
            permissoes_esp: userFields.permissoes_esp,
            tipo_especialista: isSpecialistProfile ? finalTipoEspecialista : null,
        };

        if (password) userPayload.password = password;

        try {
            if (editingUser) {
                const { data, error } = await apiClient.from('usuarios').update(userPayload).eq('id', editingUser.id).select().single();
                if (error) throw error;
                savedUser = data;
            } else {
                const createPayload = {
                    ...userPayload,
                    email: userFields.email,
                    password: password,
                    instituicao_id: institutionId,
                };
                const { data, error } = await apiClient.from('usuarios').insert(createPayload).select().single();
                if (error) throw error;
                savedUser = data;
            }

            const currentTurmasIds = editingUser?.turmas || [];
            const turmasToAdd = newTurmasIds.filter(tId => !currentTurmasIds.includes(tId));
            const turmasToRemove = currentTurmasIds.filter(tId => !newTurmasIds.includes(tId));

            if (turmasToRemove.length > 0) {
                 const { error: removeError } = await apiClient.from('usuario_turmas').delete().eq('usuario_id', savedUser.id).in('turma_id', turmasToRemove);
                if (removeError) throw new Error(`Falha ao remover turmas: ${removeError.message}`);
            }

            if (turmasToAdd.length > 0) {
                const links = turmasToAdd.map(turma_id => ({ usuario_id: savedUser.id, turma_id }));
                const { error: insertError } = await apiClient.from('usuario_turmas').insert(links);
                if (insertError) throw new Error(`Falha ao adicionar turmas: ${insertError.message}`);
            }

            const currentVinculos = editingUser?.usuario_disciplinas || [];
            const wantedDisciplinaIds = userFields.perfil === PROFESSOR_FUNDAMENTAL ? (newDisciplinasIds || []) : [];

            const vinculosToRemove = currentVinculos.filter(v => !wantedDisciplinaIds.includes(v.disciplina));
            const disciplinasToAdd = wantedDisciplinaIds.filter(
                dId => !currentVinculos.some(v => v.disciplina === dId)
            );

            if (vinculosToRemove.length > 0) {
                const results = await Promise.all(
                    vinculosToRemove.map(v => apiClient.from('usuario_disciplinas').delete().eq('id', v.id))
                );
                const failed = results.find(r => r.error);
                if (failed) throw new Error(`Falha ao remover disciplina: ${failed.error.message}`);
            }

            if (disciplinasToAdd.length > 0) {
                const results = await Promise.all(
                    disciplinasToAdd.map(disciplina_id => apiClient.from('usuario_disciplinas').insert({
                        usuario: savedUser.id,
                        disciplina: disciplina_id,
                        instituicao: institutionId,
                    }))
                );
                const failed = results.find(r => r.error);
                if (failed) throw new Error(`Falha ao vincular disciplina: ${failed.error.message}`);
            }

            toast({ title: `Usuário ${editingUser ? 'atualizado' : 'criado'} com sucesso!` });
            setIsFormOpen(false);
            setEditingUser(null);

            // Criação: como a ordenação padrão é "mais recente primeiro", ir
            // pra página 1 já mostra o usuário recém-criado no topo.
            // Edição: mantém a página atual, pra não perder o contexto.
            const targetPage = isCreating ? 1 : currentPage;
            setCurrentPage(targetPage);
            await fetchUsuarios(institutionId, targetPage);

        } catch (error) {
            toast({ variant: "destructive", title: `Erro ao ${editingUser ? 'atualizar' : 'criar'} usuário`, description: error.message });
        }
    };

    const handleDeleteUser = async () => {
        if (!deletingUser) return;
        try {
            const { error } = await apiClient.from('usuarios').delete().eq('id', deletingUser.id);
            if (error) throw error;

            toast({ title: "Usuário excluído com sucesso!" });
            setDeletingUser(null);

            // Se essa era a última linha da página (e não é a página 1), volta
            // uma página pra não ficar numa página vazia.
            const targetPage = (usuarios.length === 1 && currentPage > 1) ? currentPage - 1 : currentPage;
            setCurrentPage(targetPage);
            await fetchUsuarios(institutionId, targetPage);
        } catch (error) {
            toast({ variant: "destructive", title: "Erro ao excluir usuário", description: error.message });
        }
    };

    const openFormForNew = () => {
        if (!institutionId) {
            toast({ variant: "destructive", title: "Cadastro de Instituição Necessário", description: "Por favor, cadastre primeiro os dados da instituição." });
            return;
        }
        setEditingUser(null);
        setIsFormOpen(true);
    };

    const handleEdit = async (user) => {
        let usuarioDisciplinas = [];

        if (user.perfil === PROFESSOR_FUNDAMENTAL) {
            const { data, error } = await apiClient.from('usuario_disciplinas').select('*').eq('usuario_id', user.id).limit(100);
            if (error) {
                toast({ variant: "destructive", title: "Erro ao carregar disciplinas do professor", description: error.message });
            } else {
                usuarioDisciplinas = Array.isArray(data) ? data : [];
            }
        }

        setEditingUser({ ...user, usuario_disciplinas: usuarioDisciplinas });
        setIsFormOpen(true);
    };

    const handleDelete = (user) => {
        setDeletingUser(user);
    };

    return (
        <Card>
            <CardHeader className="flex-row items-center justify-between">
                <div>
                    <CardTitle>Gerenciamento de Usuários</CardTitle>
                    <CardDescription>Adicione, edite ou remova os usuários da sua escola.</CardDescription>
                </div>
                <Button onClick={openFormForNew}><PlusCircle className="mr-2 h-4 w-4" /> Novo Usuário</Button>
            </CardHeader>
            <CardContent>
                <UserList
                    loading={loading}
                    usuarios={usuarios}
                    onEdit={handleEdit}
                    onDelete={handleDelete}
                />
            </CardContent>
            <CardFooter className="flex items-center justify-between">
                <p className="text-sm text-gray-500">
                    {totalUsuarios > 0
                        ? `${totalUsuarios} usuário${totalUsuarios !== 1 ? 's' : ''} — página ${currentPage} de ${totalPages}`
                        : 'Nenhum usuário cadastrado.'}
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

            <UserFormDialog
                isOpen={isFormOpen}
                setIsOpen={setIsFormOpen}
                user={editingUser}
                turmas={turmas}
                disciplinas={disciplinas}
                onSubmit={handleFormSubmit}
            />

            <Dialog open={!!deletingUser} onOpenChange={() => setDeletingUser(null)}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Confirmar Exclusão</DialogTitle>
                        <DialogDescription>
                            Tem certeza que deseja excluir o usuário "{deletingUser?.nome}"? Esta ação é irreversível e removerá o acesso do usuário.
                        </DialogDescription>
                    </DialogHeader>
                    <DialogFooter>
                        <DialogClose asChild><Button variant="outline">Cancelar</Button></DialogClose>
                        <Button variant="destructive" onClick={handleDeleteUser}>Excluir</Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </Card>
    );
};

export default UsuariosTab;