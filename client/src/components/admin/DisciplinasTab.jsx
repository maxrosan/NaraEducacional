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
    listarDisciplinasPaginado, listarEscolas, listarUsuarios,
    criarDisciplina, atualizarDisciplina,
} from '@/services/api';
import DisciplinaList from './disciplinas/DisciplinaList';
import DisciplinaFormDialog from './disciplinas/DisciplinaFormDialog';

/*
 * Catálogo de disciplinas (backend: /disciplinas/?page=).
 *
 * O backend já devolve só as disciplinas do escopo do usuário: o admin vê as
 * de todas as escolas da rede; o coordenador, só as da escola dele.
 *
 * Carregamento leve:
 *   - lista paginada (10 por página), filtrada no servidor pela aba
 *     (ativas/inativas), pela escola e pela busca por nome;
 *   - cada disciplina já traz `professores`;
 *   - os usuários (só usados no formulário) são buscados na primeira vez que
 *     o formulário abre.
 *
 * Salvar é UMA requisição: os professores vão no payload e o backend grava
 * disciplina e vínculos na mesma transação. Só professor_fundamental pode ser
 * vinculado (regra do backend). Nome repetido na escola, sem diferenciar
 * maiúsculas, volta como erro no campo `nome`.
 *
 * Não existe exclusão: a disciplina é desativada e pode ser reativada na aba
 * Inativas, mantendo os vínculos e o histórico.
 */

const TODAS = 'todas';
const POR_PAGINA = 10;
const BUSCA_DEBOUNCE_MS = 400;
const ABA_ATIVAS = 'ativas';
const ABA_INATIVAS = 'inativas';
const NIVEL_VINCULAVEL = 'professor_fundamental';
const LISTA_VAZIA = { results: [], count: 0, total_paginas: 1, totais: { ativas: 0, inativas: 0 } };

/** `{ error }` (permissão/escopo) ou `{ campo: [mensagens] }` (validação). */
function mensagemDeErro(err) {
    const payload = err?.payload;
    if (payload && typeof payload === 'object' && !payload.error && !payload.detail) {
        const mensagens = Object.values(payload).flat().filter(Boolean);
        if (mensagens.length) return mensagens.join(' ');
    }
    return err?.message || 'Erro inesperado.';
}

const DisciplinasTab = () => {
    const [aba, setAba] = useState(ABA_ATIVAS);
    const [pagina, setPagina] = useState(1);
    const [filtroEscola, setFiltroEscola] = useState(TODAS);
    const [busca, setBusca] = useState('');
    const [buscaAplicada, setBuscaAplicada] = useState('');
    const [lista, setLista] = useState(LISTA_VAZIA);
    const [loading, setLoading] = useState(true);
    const [carregouUmaVez, setCarregouUmaVez] = useState(false);
    const [escolas, setEscolas] = useState([]);
    const [usuarios, setUsuarios] = useState(null); // null = ainda não buscados
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
            const dados = await listarDisciplinasPaginado({
                ativo: aba === ABA_ATIVAS,
                escola: filtroEscola === TODAS ? undefined : filtroEscola,
                busca: buscaAplicada || undefined,
                page: pagina,
                pageSize: POR_PAGINA,
            });
            if (id !== ultimaRequisicao.current) return;
            setLista(dados);
            // Ex.: desativou a única disciplina da última página → o backend devolve a anterior.
            if (dados.pagina && dados.pagina !== pagina) setPagina(dados.pagina);
        } catch (err) {
            if (id !== ultimaRequisicao.current) return;
            toast({ variant: "destructive", title: "Erro ao carregar disciplinas", description: mensagemDeErro(err) });
        } finally {
            if (id === ultimaRequisicao.current) {
                setLoading(false);
                setCarregouUmaVez(true);
            }
        }
    }, [aba, pagina, filtroEscola, buscaAplicada]);

    useEffect(() => { carregar(); }, [carregar]);

    // Escolas: lista curta, usada no filtro e no formulário. Busca uma vez só.
    useEffect(() => {
        listarEscolas()
            .then(setEscolas)
            .catch((err) => toast({ variant: "destructive", title: "Erro ao carregar escolas", description: mensagemDeErro(err) }));
    }, []);

    // Usuários: só o formulário precisa. Busca na primeira abertura e reaproveita.
    const garantirUsuarios = useCallback(() => {
        if (usuarios !== null) return;
        listarUsuarios()
            .then(setUsuarios)
            .catch((err) => {
                setUsuarios([]);
                toast({ variant: "destructive", title: "Erro ao carregar professores", description: mensagemDeErro(err) });
            });
    }, [usuarios]);

    const variasEscolas = escolas.length > 1;
    const escolasAtivas = useMemo(() => escolas.filter((e) => e.ativa !== false), [escolas]);
    const vinculaveis = useMemo(
        () => (usuarios ?? []).filter((u) => u.is_active !== false && u.nivel === NIVEL_VINCULAVEL),
        [usuarios],
    );

    // Todo filtro novo volta para a página 1 (no mesmo render, sem requisição extra).
    const trocarAba = (valor) => { setAba(valor); setPagina(1); };
    const trocarEscola = (valor) => { setFiltroEscola(valor); setPagina(1); };

    const abrirFormulario = (disciplina) => {
        if (!disciplina && !escolasAtivas.length) {
            toast({ variant: "destructive", title: "Nenhuma escola ativa", description: "Cadastre ou reative uma escola antes de criar disciplinas." });
            return;
        }
        garantirUsuarios();
        setEditando(disciplina);
        setIsFormOpen(true);
    };

    /** Retorna true se salvou (o formulário fecha); false mantém aberto para correção. */
    const handleSalvar = async (dados) => {
        const editandoAgora = !!editando;
        try {
            if (editandoAgora) await atualizarDisciplina(editando.id, dados);
            else await criarDisciplina(dados);
        } catch (err) {
            toast({ variant: "destructive", title: "Erro ao salvar disciplina", description: mensagemDeErro(err) });
            return false;
        }

        toast({ title: `Disciplina ${editandoAgora ? 'atualizada' : 'criada'} com sucesso!` });
        setIsFormOpen(false);
        setEditando(null);

        // Disciplina nova nasce ativa: leva o usuário até onde ela aparece.
        if (!editandoAgora && (aba !== ABA_ATIVAS || pagina !== 1)) {
            setAba(ABA_ATIVAS);
            setPagina(1); // o efeito de `carregar` recarrega sozinho
        } else {
            carregar();
        }
        return true;
    };

    const alterarAtivo = async (disciplina, ativo) => {
        try {
            await atualizarDisciplina(disciplina.id, { ativo });
        } catch (err) {
            toast({ variant: "destructive", title: `Erro ao ${ativo ? 'reativar' : 'desativar'} disciplina`, description: mensagemDeErro(err) });
            return;
        }
        toast({ title: `Disciplina ${ativo ? 'reativada' : 'desativada'} com sucesso!` });
        setDesativando(null);
        carregar(); // ela sai desta aba e os contadores se atualizam
    };

    const { results: disciplinas, count, total_paginas: totalPaginas, totais } = lista;
    const primeira = count ? (pagina - 1) * POR_PAGINA + 1 : 0;
    const ultima = Math.min(pagina * POR_PAGINA, count);
    const naAbaAtivas = aba === ABA_ATIVAS;
    let mensagemVazia = naAbaAtivas ? 'Nenhuma disciplina ativa.' : 'Nenhuma disciplina inativa.';
    if (buscaAplicada) mensagemVazia = `Nenhuma disciplina encontrada para "${buscaAplicada}".`;

    return (
        <Card>
            <CardHeader className="flex-row items-center justify-between gap-4">
                <div>
                    <CardTitle>Gerenciamento de Disciplinas</CardTitle>
                    <CardDescription>Catálogo de disciplinas disponíveis para vincular a professores do Ensino Fundamental.</CardDescription>
                </div>
                <Button onClick={() => abrirFormulario(null)}><PlusCircle className="mr-2 h-4 w-4" /> Nova Disciplina</Button>
            </CardHeader>
            <CardContent>
                <div className="mb-4 flex flex-wrap items-center justify-between gap-4">
                    <Tabs value={aba} onValueChange={trocarAba}>
                        <TabsList>
                            <TabsTrigger value={ABA_ATIVAS}>
                                Ativas <Badge variant="secondary" className="ml-2">{totais.ativas}</Badge>
                            </TabsTrigger>
                            <TabsTrigger value={ABA_INATIVAS}>
                                Inativas <Badge variant="secondary" className="ml-2">{totais.inativas}</Badge>
                            </TabsTrigger>
                        </TabsList>
                    </Tabs>
                    <div className="flex flex-wrap items-center gap-2">
                        {variasEscolas && (
                            <div className="w-56">
                                <Select value={filtroEscola} onValueChange={trocarEscola}>
                                    <SelectTrigger aria-label="Filtrar por escola"><SelectValue /></SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value={TODAS}>Todas as escolas</SelectItem>
                                        {escolas.map((e) => <SelectItem key={e.id} value={String(e.id)}>{e.nome}</SelectItem>)}
                                    </SelectContent>
                                </Select>
                            </div>
                        )}
                        <Input
                            className="w-56"
                            placeholder="Buscar disciplina..."
                            aria-label="Buscar disciplina pelo nome"
                            value={busca}
                            onChange={(e) => setBusca(e.target.value)}
                        />
                    </div>
                </div>

                {!carregouUmaVez ? <p>Carregando disciplinas...</p> : (
                    <>
                        {/* Mantém a tabela na tela ao trocar de página/aba, só esmaecida. */}
                        <div className={loading ? 'pointer-events-none opacity-50 transition-opacity' : 'transition-opacity'} aria-busy={loading}>
                            <DisciplinaList
                                disciplinas={disciplinas}
                                variasEscolas={variasEscolas}
                                mensagemVazia={mensagemVazia}
                                onEdit={abrirFormulario}
                                onDesativar={setDesativando}
                                onReativar={(d) => alterarAtivo(d, true)}
                            />
                        </div>

                        {totalPaginas > 1 && (
                            <div className="mt-4 flex flex-wrap items-center justify-between gap-2 text-sm text-gray-600">
                                <span>Mostrando {primeira}–{ultima} de {count} disciplinas</span>
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

            <DisciplinaFormDialog
                isOpen={isFormOpen}
                setIsOpen={setIsFormOpen}
                disciplina={editando}
                escolas={escolasAtivas}
                vinculaveis={vinculaveis}
                carregandoProfessores={usuarios === null}
                onSubmit={handleSalvar}
            />

            <Dialog open={!!desativando} onOpenChange={() => setDesativando(null)}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Desativar disciplina</DialogTitle>
                        <DialogDescription>
                            A disciplina "{desativando?.nome}" passa para a aba Inativas. Os vínculos com
                            professores e o histórico são mantidos, e você pode reativá-la depois por essa aba.
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

export default DisciplinasTab;