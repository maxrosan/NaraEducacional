import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import { listarEscolas, listarTurmas, listarAlunosPaginado } from '@/services/api';
import { useToast } from '@/components/ui/use-toast';
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import AlunosList from './alunos/AlunosList';
import StudentFormDialog from './alunos/StudentFormDialog';
import { Button } from '@/components/ui/button';
import { UserPlus, ChevronLeft, ChevronRight } from 'lucide-react';
import BulkUploadDialog from './alunos/BulkUploadDialog';

/*
 * Gestão de alunos (backend: /alunos/?page=).
 *
 * Carregamento leve:
 *   - a lista vem paginada (10 por página) e já filtrada no servidor por
 *     status (abas), escola, turma e busca por nome;
 *   - cada aluno já traz turma_nome/escola_nome (select_related no backend);
 *   - escolas e turmas são buscadas uma vez, em paralelo.
 *
 * A tela de turmas abre esta com ?turma_id=<uuid> para já filtrar a turma.
 *
 * Não existe exclusão de aluno: "excluir" muda o status para inativo e o
 * aluno passa para a aba Inativos. A aba Inativos também mostra os
 * transferidos (status_vinculo = 'transferido').
 */

const POR_PAGINA = 10;
const BUSCA_DEBOUNCE_MS = 400;
const TODAS = 'todas';
// `status`: valor(es) de status_vinculo que cada aba pede ao backend.
const ABAS = [
    { valor: 'ativos', rotulo: 'Ativos', status: ['ativo'] },
    { valor: 'inativos', rotulo: 'Inativos', status: ['inativo', 'transferido'] },
];
const abaPorValor = (valor) => ABAS.find((a) => a.valor === valor) ?? ABAS[0];
const LISTA_VAZIA = {
    results: [], count: 0, total_paginas: 1,
    totais: { ativo: 0, inativo: 0, transferido: 0 },
};

const AlunosTab = () => {
    const { toast } = useToast();
    const [searchParams] = useSearchParams();

    const [aba, setAba] = useState('ativos');
    const [pagina, setPagina] = useState(1);
    const [filtroEscola, setFiltroEscola] = useState(TODAS);
    const [filtroTurma, setFiltroTurma] = useState(() => searchParams.get('turma_id') || TODAS);
    const [busca, setBusca] = useState('');
    const [buscaAplicada, setBuscaAplicada] = useState('');

    const [lista, setLista] = useState(LISTA_VAZIA);
    const [loading, setLoading] = useState(true);
    const [carregouUmaVez, setCarregouUmaVez] = useState(false);
    const [escolas, setEscolas] = useState([]);
    const [turmas, setTurmas] = useState([]);
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

    // Dados de apoio (filtros e formulários): uma vez, em paralelo e sem
    // bloquear a lista.
    useEffect(() => {
        const erro = (titulo) => (err) => toast({ variant: "destructive", title: titulo, description: err.message });
        listarEscolas().then(setEscolas).catch(erro("Erro ao carregar escolas"));
        listarTurmas()
            .then((dados) => setTurmas((dados || []).slice().sort((a, b) =>
                (a.escola_nome || '').localeCompare(b.escola_nome || '')
                || (a.nome || '').localeCompare(b.nome || '', 'pt-BR', { numeric: true }))))
            .catch(erro("Erro ao carregar turmas"));
    }, [toast]);

    const carregar = useCallback(async () => {
        const id = ++ultimaRequisicao.current;
        setLoading(true);
        try {
            const dados = await listarAlunosPaginado({
                status: abaPorValor(aba).status.join(','),
                escola: filtroEscola === TODAS ? undefined : filtroEscola,
                turma: filtroTurma === TODAS ? undefined : filtroTurma,
                busca: buscaAplicada || undefined,
                page: pagina,
                pageSize: POR_PAGINA,
            });
            if (id !== ultimaRequisicao.current) return; // resposta atrasada
            setLista(dados);
            // Ex.: inativou o único aluno da última página → o backend devolve a anterior.
            if (dados.pagina && dados.pagina !== pagina) setPagina(dados.pagina);
        } catch (err) {
            if (id !== ultimaRequisicao.current) return;
            toast({ variant: "destructive", title: "Erro ao carregar alunos", description: err.message });
        } finally {
            if (id === ultimaRequisicao.current) {
                setLoading(false);
                setCarregouUmaVez(true);
            }
        }
    }, [aba, pagina, filtroEscola, filtroTurma, buscaAplicada, toast]);

    useEffect(() => { carregar(); }, [carregar]);

    const variasEscolas = escolas.length > 1;
    const turmasDoFiltro = useMemo(
        () => (filtroEscola === TODAS ? turmas : turmas.filter((t) => String(t.escola) === filtroEscola)),
        [turmas, filtroEscola],
    );
    // Formulários só oferecem turmas ativas (o backend recusa as desativadas).
    const turmasAtivas = useMemo(() => turmas.filter((t) => t.ativa !== false), [turmas]);
    const escolasAtivas = useMemo(() => escolas.filter((e) => e.ativa !== false), [escolas]);

    // Todo filtro novo volta para a página 1 (no mesmo render, sem requisição extra).
    const trocarAba = (valor) => { setAba(valor); setPagina(1); };
    const trocarTurma = (valor) => { setFiltroTurma(valor); setPagina(1); };
    const trocarEscola = (valor) => {
        setFiltroEscola(valor);
        setPagina(1);
        // A turma escolhida pode não ser da escola nova.
        if (valor !== TODAS && filtroTurma !== TODAS) {
            const turma = turmas.find((t) => String(t.id) === filtroTurma);
            if (turma && String(turma.escola) !== valor) setFiltroTurma(TODAS);
        }
    };

    const rotuloTurma = (t) => {
        const partes = [t.nome];
        if (variasEscolas && filtroEscola === TODAS && t.escola_nome) partes.push(`— ${t.escola_nome}`);
        if (t.ativa === false) partes.push('(desativada)');
        return partes.join(' ');
    };

    const { results: alunos, count, total_paginas: totalPaginas, totais } = lista;
    let mensagemVazia = aba === 'ativos' ? 'Cadastre um novo aluno para começar.' : 'Nenhum aluno inativo ou transferido.';
    if (buscaAplicada) mensagemVazia = `Nenhum aluno encontrado para "${buscaAplicada}".`;
    else if (filtroTurma !== TODAS || filtroEscola !== TODAS) mensagemVazia = 'Nenhum aluno com os filtros escolhidos.';
    const primeiro = count ? (pagina - 1) * POR_PAGINA + 1 : 0;
    const ultimo = Math.min(pagina * POR_PAGINA, count);

    return (
        <div className="grid grid-cols-1 gap-6">
            <Card>
                <CardHeader>
                    <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
                        <div>
                            <CardTitle>Gestão de Alunos</CardTitle>
                            <CardDescription>
                                {variasEscolas
                                    ? 'Cadastre, edite e visualize os alunos das escolas da rede.'
                                    : 'Cadastre, edite e visualize os alunos da escola.'}
                            </CardDescription>
                        </div>
                        <div className="flex items-center gap-2">
                            <BulkUploadDialog
                                turmas={turmasAtivas}
                                escolas={escolasAtivas}
                                onUploadComplete={carregar}
                            />
                            <StudentFormDialog
                                turmas={turmasAtivas}
                                onStudentUpdated={carregar}
                            >
                                <Button>
                                    <UserPlus className="mr-2 h-4 w-4" />
                                    Cadastrar Novo Aluno
                                </Button>
                            </StudentFormDialog>
                        </div>
                    </div>
                </CardHeader>
                <CardContent>
                    <div className="mb-4">
                        <Tabs value={aba} onValueChange={trocarAba}>
                            <TabsList>
                                {ABAS.map(({ valor, rotulo, status }) => (
                                    <TabsTrigger key={valor} value={valor}>
                                        {rotulo}{' '}
                                        <Badge variant="secondary" className="ml-2">
                                            {status.reduce((soma, s) => soma + (totais[s] ?? 0), 0)}
                                        </Badge>
                                    </TabsTrigger>
                                ))}
                            </TabsList>
                        </Tabs>
                    </div>

                    <div className={`grid grid-cols-1 gap-4 mb-6 ${variasEscolas ? 'md:grid-cols-3' : 'md:grid-cols-2 max-w-3xl'}`}>
                        {variasEscolas && (
                            <div>
                                <Label htmlFor="escola-filter">Escola</Label>
                                <Select value={filtroEscola} onValueChange={trocarEscola}>
                                    <SelectTrigger id="escola-filter"><SelectValue /></SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value={TODAS}>Todas as escolas</SelectItem>
                                        {escolas.map((e) => <SelectItem key={e.id} value={String(e.id)}>{e.nome}</SelectItem>)}
                                    </SelectContent>
                                </Select>
                            </div>
                        )}
                        <div>
                            <Label htmlFor="turma-filter">Turma</Label>
                            <Select value={filtroTurma} onValueChange={trocarTurma}>
                                <SelectTrigger id="turma-filter"><SelectValue placeholder="Todas as turmas" /></SelectTrigger>
                                <SelectContent>
                                    <SelectItem value={TODAS}>Todas as turmas</SelectItem>
                                    {turmasDoFiltro.map((t) => (
                                        <SelectItem key={t.id} value={String(t.id)}>{rotuloTurma(t)}</SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </div>
                        <div>
                            <Label htmlFor="aluno-search">Buscar por nome do aluno</Label>
                            <Input
                                id="aluno-search"
                                placeholder="Digite o nome do aluno..."
                                value={busca}
                                onChange={(e) => setBusca(e.target.value)}
                            />
                        </div>
                    </div>

                    {!carregouUmaVez ? <p>Carregando alunos...</p> : (
                        <>
                            {/* Mantém a lista na tela ao trocar de página/filtro, só esmaecida. */}
                            <div className={loading ? 'pointer-events-none opacity-50 transition-opacity' : 'transition-opacity'} aria-busy={loading}>
                                <AlunosList
                                    alunos={alunos}
                                    onStudentUpdated={carregar}
                                    onStudentDeleted={carregar}
                                    turmas={turmasAtivas}
                                    mostrarEscola={variasEscolas && filtroEscola === TODAS}
                                    mensagemVazia={mensagemVazia}
                                />
                            </div>

                            {totalPaginas > 1 && (
                                <div className="mt-4 flex flex-wrap items-center justify-between gap-2 text-sm text-gray-600">
                                    <span>Mostrando {primeiro}–{ultimo} de {count} alunos</span>
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
            </Card>
        </div>
    );
};

export default AlunosTab;