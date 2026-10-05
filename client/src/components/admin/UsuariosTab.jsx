import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { PlusCircle, ChevronLeft, ChevronRight } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { toast } from '@/components/ui/use-toast';
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from "@/components/ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogClose, DialogDescription } from "@/components/ui/dialog";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
    listarUsuariosPaginado, listarEscolas, listarTurmas, listarDisciplinas,
    criarUsuario, atualizarUsuario,
} from '@/services/api';
import UserList, { NIVEL_LABELS } from './usuarios/UserList';
import UserFormDialog from './usuarios/UserFormDialog';

/*
 * Gestão de usuários (backend: /usuarios/?page=).
 *
 * O backend já devolve só os usuários do escopo: o admin vê os da rede; o
 * coordenador, os da própria escola. Quem pode criar/editar quem, e quais
 * perfis cada um pode atribuir, é regra do backend: a resposta traz
 * `niveis_permitidos` e o formulário só oferece esses.
 *
 * Carregamento leve:
 *   - lista paginada (10 por página), filtrada no servidor pela aba
 *     (ativos/inativos), escola, perfil e busca por nome/e-mail;
 *   - cada usuário já traz turmas e disciplinas (a edição abre preenchida);
 *   - turmas e disciplinas (catálogos do formulário) são buscadas na primeira
 *     vez que o formulário abre.
 *
 * Salvar é UMA requisição: turmas, disciplinas e tipo de especialista vão no
 * payload e o backend grava tudo na mesma transação.
 *
 * Não existe exclusão: o usuário é desativado (perde o acesso) e pode ser
 * reativado na aba Inativos, mantendo o histórico. Ninguém desativa a si mesmo.
 */

const TODOS = 'todos';
const POR_PAGINA = 10;
const BUSCA_DEBOUNCE_MS = 400;
const ABA_ATIVOS = 'ativos';
const ABA_INATIVOS = 'inativos';
const LISTA_VAZIA = {
    results: [], count: 0, total_paginas: 1, totais: { ativos: 0, inativos: 0 },
    niveis_permitidos: [], usuario_atual: null,
};

/** `{ error }` (permissão/escopo) ou `{ campo: [mensagens] }` (validação). */
function mensagemDeErro(err) {
    const payload = err?.payload;
    if (payload && typeof payload === 'object' && !payload.error && !payload.detail) {
        const mensagens = Object.values(payload).flat().filter(Boolean);
        if (mensagens.length) return mensagens.join(' ');
    }
    return err?.message || 'Erro inesperado.';
}

const UsuariosTab = () => {
    const [aba, setAba] = useState(ABA_ATIVOS);
    const [pagina, setPagina] = useState(1);
    const [filtroEscola, setFiltroEscola] = useState(TODOS);
    const [filtroNivel, setFiltroNivel] = useState(TODOS);
    const [busca, setBusca] = useState('');
    const [buscaAplicada, setBuscaAplicada] = useState('');
    const [lista, setLista] = useState(LISTA_VAZIA);
    const [loading, setLoading] = useState(true);
    const [carregouUmaVez, setCarregouUmaVez] = useState(false);
    const [escolas, setEscolas] = useState([]);
    const [catalogos, setCatalogos] = useState(null); // { turmas, disciplinas } | null = não buscados
    const [isFormOpen, setIsFormOpen] = useState(false);
    const [editando, setEditando] = useState(null);
    const [desativando, setDesativando] = useState(null);
    // Descarta respostas atrasadas quando o usuário troca de aba/página rápido.
    const ultimaRequisicao = useRef(0);

    // Só consulta o backend quando o usuário para de digitar.
    useEffect(() => {
        const termo = busca.trim();
        if (termo === buscaAplicada) return undefined;
        const id = setTimeout(() => {
            setBuscaAplicada(termo);
            setPagina(1);
        }, BUSCA_DEBOUNCE_MS);
        return () => clearTimeout(id);
    }, [busca, buscaAplicada]);

    const carregar = useCallback(async () => {
        const id = ++ultimaRequisicao.current;
        setLoading(true);
        try {
            const dados = await listarUsuariosPaginado({
                ativo: aba === ABA_ATIVOS,
                escola: filtroEscola === TODOS ? undefined : filtroEscola,
                nivel: filtroNivel === TODOS ? undefined : filtroNivel,
                busca: buscaAplicada || undefined,
                page: pagina,
                pageSize: POR_PAGINA,
            });
            if (id !== ultimaRequisicao.current) return;
            setLista(dados);
            // Ex.: desativou o único usuário da última página → o backend devolve a anterior.
            if (dados.pagina && dados.pagina !== pagina) setPagina(dados.pagina);
        } catch (err) {
            if (id !== ultimaRequisicao.current) return;
            toast({ variant: "destructive", title: "Erro ao carregar usuários", description: mensagemDeErro(err) });
        } finally {
            if (id === ultimaRequisicao.current) {
                setLoading(false);
                setCarregouUmaVez(true);
            }
        }
    }, [aba, pagina, filtroEscola, filtroNivel, buscaAplicada]);

    useEffect(() => { carregar(); }, [carregar]);

    // Escolas: lista curta, usada no filtro e no formulário. Busca uma vez só.
    useEffect(() => {
        listarEscolas()
            .then(setEscolas)
            .catch((err) => toast({ variant: "destructive", title: "Erro ao carregar escolas", description: mensagemDeErro(err) }));
    }, []);

    // Turmas e disciplinas: só o formulário precisa. Busca na 1ª abertura e reaproveita.
    const garantirCatalogos = useCallback(() => {
        if (catalogos !== null) return;
        Promise.all([listarTurmas(), listarDisciplinas()])
            .then(([turmas, disciplinas]) => setCatalogos({ turmas: turmas || [], disciplinas: disciplinas || [] }))
            .catch((err) => {
                setCatalogos({ turmas: [], disciplinas: [] });
                toast({ variant: "destructive", title: "Erro ao carregar turmas e disciplinas", description: mensagemDeErro(err) });
            });
    }, [catalogos]);

    const variasEscolas = escolas.length > 1;
    const escolasAtivas = useMemo(() => escolas.filter((e) => e.ativa !== false), [escolas]);
    const { niveis_permitidos: niveisPermitidos, usuario_atual: usuarioAtual } = lista;

    // Todo filtro novo volta para a página 1 (no mesmo render, sem requisição extra).
    const trocarAba = (valor) => { setAba(valor); setPagina(1); };
    const trocarEscola = (valor) => { setFiltroEscola(valor); setPagina(1); };
    const trocarNivel = (valor) => { setFiltroNivel(valor); setPagina(1); };

    const abrirFormulario = (usuario) => {
        garantirCatalogos();
        setEditando(usuario);
        setIsFormOpen(true);
    };

    const handleSalvar = async (dados) => {
        const editandoAgora = !!editando;
        try {
            if (editandoAgora) await atualizarUsuario(editando.id, dados);
            else await criarUsuario(dados);
        } catch (err) {
            toast({ variant: "destructive", title: `Erro ao ${editandoAgora ? 'atualizar' : 'criar'} usuário`, description: mensagemDeErro(err) });
            return;
        }

        toast({ title: `Usuário ${editandoAgora ? 'atualizado' : 'criado'} com sucesso!` });
        setIsFormOpen(false);
        setEditando(null);

        // Usuário novo nasce ativo: leva até onde ele aparece.
        if (!editandoAgora && (aba !== ABA_ATIVOS || pagina !== 1)) {
            setAba(ABA_ATIVOS);
            setPagina(1); // o efeito de `carregar` recarrega sozinho
        } else {
            carregar();
        }
    };

    const alterarAtivo = async (usuario, ativo) => {
        try {
            await atualizarUsuario(usuario.id, { is_active: ativo });
        } catch (err) {
            toast({ variant: "destructive", title: `Erro ao ${ativo ? 'reativar' : 'desativar'} usuário`, description: mensagemDeErro(err) });
            return;
        }
        toast({ title: `Usuário ${ativo ? 'reativado' : 'desativado'} com sucesso!` });
        setDesativando(null);
        carregar(); // ele sai desta aba e os contadores se atualizam
    };

    const { results: usuarios, count, total_paginas: totalPaginas, totais } = lista;
    const primeiro = count ? (pagina - 1) * POR_PAGINA + 1 : 0;
    const ultimo = Math.min(pagina * POR_PAGINA, count);
    let mensagemVazia = aba === ABA_ATIVOS ? 'Nenhum usuário ativo.' : 'Nenhum usuário inativo.';
    if (buscaAplicada) mensagemVazia = `Nenhum usuário encontrado para "${buscaAplicada}".`;

    return (
        <Card>
            <CardHeader className="flex-row items-center justify-between gap-4">
                <div>
                    <CardTitle>Gerenciamento de Usuários</CardTitle>
                    <CardDescription>
                        {variasEscolas
                            ? 'Adicione, edite ou desative os usuários das escolas da rede.'
                            : 'Adicione, edite ou desative os usuários da sua escola.'}
                    </CardDescription>
                </div>
                <Button onClick={() => abrirFormulario(null)}><PlusCircle className="mr-2 h-4 w-4" /> Novo Usuário</Button>
            </CardHeader>
            <CardContent>
                <div className="mb-4 flex flex-wrap items-center justify-between gap-4">
                    <Tabs value={aba} onValueChange={trocarAba}>
                        <TabsList>
                            <TabsTrigger value={ABA_ATIVOS}>
                                Ativos <Badge variant="secondary" className="ml-2">{totais.ativos}</Badge>
                            </TabsTrigger>
                            <TabsTrigger value={ABA_INATIVOS}>
                                Inativos <Badge variant="secondary" className="ml-2">{totais.inativos}</Badge>
                            </TabsTrigger>
                        </TabsList>
                    </Tabs>
                    <div className="flex flex-wrap items-center gap-2">
                        {variasEscolas && (
                            <div className="w-48">
                                <Select value={filtroEscola} onValueChange={trocarEscola}>
                                    <SelectTrigger aria-label="Filtrar por escola"><SelectValue /></SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value={TODOS}>Todas as escolas</SelectItem>
                                        {escolas.map((e) => <SelectItem key={e.id} value={String(e.id)}>{e.nome}</SelectItem>)}
                                    </SelectContent>
                                </Select>
                            </div>
                        )}
                        <div className="w-56">
                            <Select value={filtroNivel} onValueChange={trocarNivel}>
                                <SelectTrigger aria-label="Filtrar por perfil"><SelectValue /></SelectTrigger>
                                <SelectContent>
                                    <SelectItem value={TODOS}>Todos os perfis</SelectItem>
                                    {Object.entries(NIVEL_LABELS)
                                        .filter(([valor]) => !['superadmin', 'vendedor', 'suporte'].includes(valor))
                                        .map(([valor, label]) => <SelectItem key={valor} value={valor}>{label}</SelectItem>)}
                                </SelectContent>
                            </Select>
                        </div>
                        <Input
                            className="w-56"
                            placeholder="Buscar por nome ou e-mail..."
                            aria-label="Buscar usuário por nome ou e-mail"
                            value={busca}
                            onChange={(e) => setBusca(e.target.value)}
                        />
                    </div>
                </div>

                {!carregouUmaVez ? <p>Carregando usuários...</p> : (
                    <>
                        {/* Mantém a tabela na tela ao trocar de página/aba, só esmaecida. */}
                        <div className={loading ? 'pointer-events-none opacity-50 transition-opacity' : 'transition-opacity'} aria-busy={loading}>
                            <UserList
                                usuarios={usuarios}
                                variasEscolas={variasEscolas}
                                usuarioAtual={usuarioAtual}
                                mensagemVazia={mensagemVazia}
                                onEdit={abrirFormulario}
                                onDesativar={setDesativando}
                                onReativar={(u) => alterarAtivo(u, true)}
                            />
                        </div>

                        {totalPaginas > 1 && (
                            <div className="mt-4 flex flex-wrap items-center justify-between gap-2 text-sm text-gray-600">
                                <span>Mostrando {primeiro}–{ultimo} de {count} usuários</span>
                                <div className="flex items-center gap-2">
                                    <Button variant="outline" size="sm" disabled={loading || pagina <= 1} onClick={() => setPagina((p) => p - 1)}>
                                        <ChevronLeft className="mr-1 h-4 w-4" /> Anterior
                                    </Button>
                                    <span className="px-2">Página {pagina} de {totalPaginas}</span>
                                    <Button variant="outline" size="sm" disabled={loading || pagina >= totalPaginas} onClick={() => setPagina((p) => p + 1)}>
                                        Próxima <ChevronRight className="ml-1 h-4 w-4" />
                                    </Button>
                                </div>
                            </div>
                        )}
                    </>
                )}
            </CardContent>

            <UserFormDialog
                isOpen={isFormOpen}
                setIsOpen={setIsFormOpen}
                user={editando}
                escolas={escolasAtivas}
                turmas={catalogos?.turmas ?? []}
                disciplinas={catalogos?.disciplinas ?? []}
                carregandoCatalogos={catalogos === null}
                niveisPermitidos={niveisPermitidos}
                usuarioAtual={usuarioAtual}
                onSubmit={handleSalvar}
            />

            <Dialog open={!!desativando} onOpenChange={() => setDesativando(null)}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Desativar usuário</DialogTitle>
                        <DialogDescription>
                            "{desativando?.nome}" perde o acesso ao sistema e passa para a aba Inativos.
                            Os registros e vínculos dele são mantidos, e você pode reativá-lo depois por essa aba.
                        </DialogDescription>
                    </DialogHeader>
                    <DialogFooter>
                        <DialogClose asChild><Button variant="outline">Cancelar</Button></DialogClose>
                        <Button variant="destructive" onClick={() => alterarAtivo(desativando, false)}>Desativar</Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </Card>
    );
};

export default UsuariosTab;