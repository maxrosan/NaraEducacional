import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import {
    PlusCircle, Edit, Power, RotateCcw, ChevronLeft, ChevronRight, Loader2, Check,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { toast } from '@/components/ui/use-toast';
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogClose, DialogDescription } from "@/components/ui/dialog";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import IconPicker from '@/components/ui/icon-picker';
import { NIVEIS_BASE, iconeDoCampo, montarNiveis, mensagemDeErro } from '@/lib/perguntasUtils';
import {
    listarPerguntasEspecialistasPaginado, criarPerguntaEspecialista, atualizarPerguntaEspecialista,
    listarCamposPedagogicos, criarCampoPedagogico, listarEscolas, listarTurmas,
} from '@/services/api';

/*
 * Perguntas dos especialistas (backend: /perguntas-especialistas/?page=).
 * As perguntas BNCC oficiais têm página própria (/admin/perguntas-bncc),
 * acessada pelo submenu Perguntas → BNCC.
 *
 * Toda pergunta tem uma Referência BNCC: o usuário digita o código (ex.:
 * EI03EO01) e o backend localiza a habilidade no catálogo; código
 * inexistente volta como erro no formulário.
 *
 * Carregamento leve: lista paginada (10 por página), filtrada no servidor
 * pela aba (ativas/inativas), escola, nível, campo e busca (texto ou código
 * BNCC). Escolas, campos e turmas (para os níveis) são buscados uma vez.
 *
 * Não existe exclusão: os registros de observação apontam para a pergunta,
 * então ela é desativada e pode ser reativada na aba Inativas.
 */

const TODOS = 'todos';
const POR_PAGINA = 10;
const BUSCA_DEBOUNCE_MS = 400;
const ABA_ATIVAS = 'ativa';
const ABA_INATIVAS = 'inativa';
const LISTA_VAZIA = { results: [], count: 0, total_paginas: 1, totais: { ativas: 0, inativas: 0 } };

const PerguntasTab = () => {
    const [aba, setAba] = useState(ABA_ATIVAS);
    const [pagina, setPagina] = useState(1);
    const [filtroEscola, setFiltroEscola] = useState(TODOS);
    const [filtroNivel, setFiltroNivel] = useState(TODOS);
    const [filtroCampo, setFiltroCampo] = useState(TODOS);
    const [busca, setBusca] = useState('');
    const [buscaAplicada, setBuscaAplicada] = useState('');
    const [lista, setLista] = useState(LISTA_VAZIA);
    const [loading, setLoading] = useState(true);
    const [carregouUmaVez, setCarregouUmaVez] = useState(false);
    const [escolas, setEscolas] = useState([]);
    const [campos, setCampos] = useState([]);
    const [niveis, setNiveis] = useState(NIVEIS_BASE);
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
            const dados = await listarPerguntasEspecialistasPaginado({
                status: aba,
                escola: filtroEscola === TODOS ? undefined : filtroEscola,
                nivel: filtroNivel === TODOS ? undefined : filtroNivel,
                campo: filtroCampo === TODOS ? undefined : filtroCampo,
                busca: buscaAplicada || undefined,
                page: pagina,
                pageSize: POR_PAGINA,
            });
            if (id !== ultimaRequisicao.current) return;
            setLista(dados);
            if (dados.pagina && dados.pagina !== pagina) setPagina(dados.pagina);
        } catch (err) {
            if (id !== ultimaRequisicao.current) return;
            toast({ variant: "destructive", title: "Erro ao carregar perguntas", description: mensagemDeErro(err) });
        } finally {
            if (id === ultimaRequisicao.current) {
                setLoading(false);
                setCarregouUmaVez(true);
            }
        }
    }, [aba, pagina, filtroEscola, filtroNivel, filtroCampo, buscaAplicada]);

    useEffect(() => { carregar(); }, [carregar]);

    // Dados de apoio (filtros e formulário): uma vez, em paralelo.
    useEffect(() => {
        const erro = (titulo) => (err) => toast({ variant: "destructive", title: titulo, description: mensagemDeErro(err) });
        listarEscolas().then(setEscolas).catch(erro("Erro ao carregar escolas"));
        listarCamposPedagogicos().then((c) => setCampos(c || [])).catch(erro("Erro ao carregar campos de experiência"));
        listarTurmas()
            .then((t) => setNiveis(montarNiveis((t || []).filter((x) => x.ativa !== false))))
            .catch(() => setNiveis(NIVEIS_BASE));
    }, []);

    const variasEscolas = escolas.length > 1;
    const escolasAtivas = useMemo(() => escolas.filter((e) => e.ativa !== false), [escolas]);
    const camposAtivos = useMemo(
        () => campos.filter((c) => c.ativo !== false).sort((a, b) => a.nome.localeCompare(b.nome, 'pt-BR')),
        [campos],
    );

    // Todo filtro novo volta para a página 1 (no mesmo render, sem requisição extra).
    const trocar = (setter) => (valor) => { setter(valor); setPagina(1); };

    const abrirFormulario = (pergunta) => {
        if (!pergunta && !escolasAtivas.length) {
            toast({ variant: "destructive", title: "Nenhuma escola ativa", description: "Cadastre ou reative uma escola antes de criar perguntas." });
            return;
        }
        setEditando(pergunta);
        setIsFormOpen(true);
    };

    const handleSalvar = async (dados) => {
        const editandoAgora = !!editando;
        try {
            if (editandoAgora) await atualizarPerguntaEspecialista(editando.id, dados);
            else await criarPerguntaEspecialista(dados);
        } catch (err) {
            toast({ variant: "destructive", title: "Erro ao salvar pergunta", description: mensagemDeErro(err) });
            return;
        }
        toast({ title: `Pergunta ${editandoAgora ? 'atualizada' : 'criada'} com sucesso!` });
        setIsFormOpen(false);
        setEditando(null);
        if (!editandoAgora && (aba !== ABA_ATIVAS || pagina !== 1)) {
            setAba(ABA_ATIVAS);
            setPagina(1);
        } else {
            carregar();
        }
    };

    const alterarStatus = async (pergunta, status) => {
        try {
            await atualizarPerguntaEspecialista(pergunta.id, { status });
        } catch (err) {
            toast({ variant: "destructive", title: `Erro ao ${status === 'ativa' ? 'reativar' : 'desativar'} pergunta`, description: mensagemDeErro(err) });
            return;
        }
        toast({ title: `Pergunta ${status === 'ativa' ? 'reativada' : 'desativada'} com sucesso!` });
        setDesativando(null);
        carregar();
    };

    const { results: perguntas, count, total_paginas: totalPaginas, totais } = lista;
    const primeira = count ? (pagina - 1) * POR_PAGINA + 1 : 0;
    const ultima = Math.min(pagina * POR_PAGINA, count);
    const colunas = variasEscolas ? 6 : 5;
    let mensagemVazia = aba === ABA_ATIVAS ? 'Nenhuma pergunta ativa.' : 'Nenhuma pergunta inativa.';
    if (buscaAplicada) mensagemVazia = `Nenhuma pergunta encontrada para "${buscaAplicada}".`;

    const acao = (rotulo, onClick, icone) => (
        <Tooltip>
            <TooltipTrigger asChild>
                <Button variant="ghost" size="icon" onClick={onClick} aria-label={rotulo}>{icone}</Button>
            </TooltipTrigger>
            <TooltipContent><p>{rotulo}</p></TooltipContent>
        </Tooltip>
    );

    return (
        <div className="grid grid-cols-1 gap-6">
            <Card>
                <CardHeader className="flex-row items-center justify-between gap-4">
                    <div>
                        <CardTitle>Perguntas dos Especialistas</CardTitle>
                        <CardDescription>
                            Perguntas livres, agrupadas por Campo de Experiência no formulário de observação.
                            Toda pergunta tem uma Referência BNCC.
                        </CardDescription>
                    </div>
                    <Button onClick={() => abrirFormulario(null)}><PlusCircle className="mr-2 h-4 w-4" /> Nova Pergunta</Button>
                </CardHeader>
                <CardContent>
                    <div className="mb-4 flex flex-wrap items-center justify-between gap-4">
                        <Tabs value={aba} onValueChange={trocar(setAba)}>
                            <TabsList>
                                <TabsTrigger value={ABA_ATIVAS}>
                                    Ativas <Badge variant="secondary" className="ml-2">{totais.ativas}</Badge>
                                </TabsTrigger>
                                <TabsTrigger value={ABA_INATIVAS}>
                                    Inativas <Badge variant="secondary" className="ml-2">{totais.inativas}</Badge>
                                </TabsTrigger>
                            </TabsList>
                        </Tabs>
                        <Input
                            className="w-64"
                            placeholder="Buscar por texto ou código BNCC..."
                            aria-label="Buscar pergunta por texto ou código BNCC"
                            value={busca}
                            onChange={(e) => setBusca(e.target.value)}
                        />
                    </div>
                    <div className={`mb-4 grid grid-cols-1 gap-2 ${variasEscolas ? 'md:grid-cols-3' : 'md:grid-cols-2'}`}>
                        {variasEscolas && (
                            <Select value={filtroEscola} onValueChange={trocar(setFiltroEscola)}>
                                <SelectTrigger aria-label="Filtrar por escola"><SelectValue /></SelectTrigger>
                                <SelectContent>
                                    <SelectItem value={TODOS}>Todas as escolas</SelectItem>
                                    {escolas.map((e) => <SelectItem key={e.id} value={String(e.id)}>{e.nome}</SelectItem>)}
                                </SelectContent>
                            </Select>
                        )}
                        <Select value={filtroNivel} onValueChange={trocar(setFiltroNivel)}>
                            <SelectTrigger aria-label="Filtrar por nível"><SelectValue /></SelectTrigger>
                            <SelectContent>
                                <SelectItem value={TODOS}>Todos os níveis</SelectItem>
                                {niveis.map((n) => <SelectItem key={n} value={n}>{n}</SelectItem>)}
                            </SelectContent>
                        </Select>
                        <Select value={filtroCampo} onValueChange={trocar(setFiltroCampo)}>
                            <SelectTrigger aria-label="Filtrar por campo de experiência"><SelectValue /></SelectTrigger>
                            <SelectContent>
                                <SelectItem value={TODOS}>Todos os campos de experiência</SelectItem>
                                {camposAtivos.map((c) => <SelectItem key={c.id} value={String(c.id)}>{c.nome}</SelectItem>)}
                            </SelectContent>
                        </Select>
                    </div>

                    {!carregouUmaVez ? <p>Carregando perguntas...</p> : (
                        <TooltipProvider>
                            {/* Mantém a tabela na tela ao trocar de página/aba, só esmaecida. */}
                            <div className={loading ? 'pointer-events-none opacity-50 transition-opacity' : 'transition-opacity'} aria-busy={loading}>
                                <Table>
                                    <TableHeader>
                                        <TableRow>
                                            <TableHead>Pergunta Facilitadora</TableHead>
                                            <TableHead>Campo de Experiência</TableHead>
                                            <TableHead>Nível</TableHead>
                                            <TableHead>Referência (BNCC)</TableHead>
                                            {variasEscolas && <TableHead>Escola</TableHead>}
                                            <TableHead className="text-right">Ações</TableHead>
                                        </TableRow>
                                    </TableHeader>
                                    <TableBody>
                                        {perguntas.length > 0 ? perguntas.map((p) => {
                                            const Icone = iconeDoCampo(p.campo_experiencia_nome, p.campo_experiencia_icone);
                                            return (
                                                <TableRow key={p.id}>
                                                    <TableCell className="max-w-md font-medium">{p.pergunta_facilitadora || p.pergunta}</TableCell>
                                                    <TableCell>
                                                        {p.campo_experiencia_nome ? (
                                                            <span className="flex items-center gap-2">
                                                                <Icone className="h-4 w-4 shrink-0 text-purple-600" />
                                                                {p.campo_experiencia_nome}
                                                            </span>
                                                        ) : '—'}
                                                    </TableCell>
                                                    <TableCell>{p.nivel || '—'}</TableCell>
                                                    <TableCell>
                                                        {p.habilidade_bncc_codigo ? (
                                                            <Tooltip>
                                                                <TooltipTrigger asChild>
                                                                    <span className="cursor-help font-mono text-sm underline decoration-dotted">{p.habilidade_bncc_codigo}</span>
                                                                </TooltipTrigger>
                                                                <TooltipContent className="max-w-sm"><p>{p.habilidade_bncc_descricao}</p></TooltipContent>
                                                            </Tooltip>
                                                        ) : <span className="text-amber-600">Sem referência</span>}
                                                    </TableCell>
                                                    {variasEscolas && <TableCell>{p.escola_nome}</TableCell>}
                                                    <TableCell className="text-right space-x-2 whitespace-nowrap">
                                                        {acao('Editar pergunta', () => abrirFormulario(p), <Edit className="h-4 w-4" />)}
                                                        {p.status === 'ativa'
                                                            ? acao('Desativar pergunta', () => setDesativando(p), <Power className="h-4 w-4 text-red-500" />)
                                                            : acao('Reativar pergunta', () => alterarStatus(p, 'ativa'), <RotateCcw className="h-4 w-4 text-green-600" />)}
                                                    </TableCell>
                                                </TableRow>
                                            );
                                        }) : (
                                            <TableRow>
                                                <TableCell colSpan={colunas} className="text-center text-gray-500">{mensagemVazia}</TableCell>
                                            </TableRow>
                                        )}
                                    </TableBody>
                                </Table>
                            </div>

                            {totalPaginas > 1 && (
                                <div className="mt-4 flex flex-wrap items-center justify-between gap-2 text-sm text-gray-600">
                                    <span>Mostrando {primeira}–{ultima} de {count} perguntas</span>
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
                        </TooltipProvider>
                    )}
                </CardContent>
            </Card>

            <PerguntaFormDialog
                isOpen={isFormOpen}
                setIsOpen={setIsFormOpen}
                pergunta={editando}
                escolas={escolasAtivas}
                campos={camposAtivos}
                niveis={niveis}
                onCampoCriado={(c) => setCampos((prev) => [...prev, c])}
                onSubmit={handleSalvar}
            />

            <Dialog open={!!desativando} onOpenChange={() => setDesativando(null)}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Desativar pergunta</DialogTitle>
                        <DialogDescription>
                            A pergunta deixa de aparecer na aba Ativas. As observações já registradas com ela
                            são mantidas, e você pode reativá-la depois pela aba Inativas.
                        </DialogDescription>
                    </DialogHeader>
                    <DialogFooter>
                        <DialogClose asChild><Button variant="outline">Cancelar</Button></DialogClose>
                        <Button variant="destructive" onClick={() => alterarStatus(desativando, 'inativa')}>Desativar</Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    );
};

const FORM_VAZIO = { escola: '', campo_experiencia: '', nivel: '', pergunta: '', referencia_bncc: '' };

const PerguntaFormDialog = ({ isOpen, setIsOpen, pergunta, escolas, campos, niveis, onCampoCriado, onSubmit }) => {
    const [formData, setFormData] = useState(FORM_VAZIO);
    const [salvando, setSalvando] = useState(false);
    const [novoCampo, setNovoCampo] = useState(null); // { nome, icone } enquanto o diálogo de criação está aberto
    const [criandoCampo, setCriandoCampo] = useState(false);

    useEffect(() => {
        if (!isOpen) return;
        setFormData(pergunta ? {
            escola: String(pergunta.escola ?? ''),
            campo_experiencia: pergunta.campo_experiencia ? String(pergunta.campo_experiencia) : '',
            nivel: pergunta.nivel || '',
            pergunta: pergunta.pergunta_facilitadora || pergunta.pergunta || '',
            referencia_bncc: pergunta.habilidade_bncc_codigo || '',
        } : {
            ...FORM_VAZIO,
            escola: escolas.length === 1 ? String(escolas[0].id) : '',
        });
    // escolas pode chegar depois; só reinicia ao abrir ou trocar a pergunta.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [pergunta, isOpen]);

    const set = (campo, valor) => setFormData((prev) => ({ ...prev, [campo]: valor }));

    // Campos oficiais (sem escola) + os da escola da pergunta.
    const camposDaEscola = useMemo(
        () => campos.filter((c) => !c.escola || String(c.escola) === formData.escola),
        [campos, formData.escola],
    );
    // Campo da escola anterior deixa de valer ao trocar de escola.
    const trocarEscola = (escola) => setFormData((prev) => {
        const campo = campos.find((c) => String(c.id) === prev.campo_experiencia);
        const aindaVale = !campo || !campo.escola || String(campo.escola) === escola;
        return { ...prev, escola, campo_experiencia: aindaVale ? prev.campo_experiencia : '' };
    });

    const handleCriarCampo = async () => {
        if (!novoCampo?.nome.trim()) return;
        setCriandoCampo(true);
        try {
            const criado = await criarCampoPedagogico({
                nome: novoCampo.nome.trim(), icone: novoCampo.icone, escola: formData.escola,
            });
            onCampoCriado(criado);
            set('campo_experiencia', String(criado.id));
            setNovoCampo(null);
            toast({ title: 'Campo de experiência criado!' });
        } catch (err) {
            toast({ variant: "destructive", title: "Erro ao criar campo", description: mensagemDeErro(err) });
        } finally {
            setCriandoCampo(false);
        }
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        // Os Selects do Radix não participam da validação nativa do form.
        const faltando = [
            !pergunta && !formData.escola && 'escola',
            !formData.campo_experiencia && 'campo de experiência',
            !formData.nivel && 'nível',
        ].filter(Boolean);
        if (faltando.length) {
            toast({ variant: "destructive", title: "Campos obrigatórios", description: `Selecione: ${faltando.join(', ')}.` });
            return;
        }
        const texto = formData.pergunta.trim();
        const dados = {
            campo_experiencia: formData.campo_experiencia,
            nivel: formData.nivel,
            pergunta: texto,
            pergunta_facilitadora: texto,
            referencia_bncc: formData.referencia_bncc.trim().toUpperCase(),
        };
        if (!pergunta) dados.escola = formData.escola; // na edição a escola não muda

        setSalvando(true);
        try {
            await onSubmit(dados);
        } finally {
            setSalvando(false);
        }
    };

    const escolaDaPergunta = pergunta
        ? (escolas.find((e) => String(e.id) === formData.escola)?.nome || pergunta.escola_nome)
        : null;

    return (
        <>
            {/* Não fecha no meio do salvamento (Esc/clique fora). */}
            <Dialog open={isOpen} onOpenChange={(aberto) => { if (!salvando) setIsOpen(aberto); }}>
                <DialogContent className="max-h-[90vh] max-w-lg overflow-y-auto">
                    <DialogHeader>
                        <DialogTitle>{pergunta ? 'Editar' : 'Nova'} Pergunta de Especialista</DialogTitle>
                        <DialogDescription>
                            O Campo de Experiência define como a pergunta é agrupada no formulário de observação.
                        </DialogDescription>
                    </DialogHeader>
                    <form onSubmit={handleSubmit} className="space-y-4 pt-2">
                        {pergunta ? (
                            escolas.length > 1 && (
                                <div>
                                    <Label>Escola</Label>
                                    <p className="mt-1 text-sm text-gray-600">{escolaDaPergunta}</p>
                                </div>
                            )
                        ) : escolas.length > 1 && (
                            <div>
                                <Label htmlFor="escola">Escola</Label>
                                <Select value={formData.escola} onValueChange={trocarEscola}>
                                    <SelectTrigger id="escola"><SelectValue placeholder="Selecione a escola" /></SelectTrigger>
                                    <SelectContent>
                                        {escolas.map((e) => <SelectItem key={e.id} value={String(e.id)}>{e.nome}</SelectItem>)}
                                    </SelectContent>
                                </Select>
                            </div>
                        )}

                        <div>
                            <Label htmlFor="campo_experiencia">Campo de Experiência</Label>
                            <div className="flex items-center gap-2">
                                <Select value={formData.campo_experiencia} onValueChange={(v) => set('campo_experiencia', v)}>
                                    <SelectTrigger id="campo_experiencia"><SelectValue placeholder="Selecione o campo" /></SelectTrigger>
                                    <SelectContent>
                                        {camposDaEscola.map((c) => {
                                            const Icone = iconeDoCampo(c.nome, c.icone);
                                            return (
                                                <SelectItem key={c.id} value={String(c.id)}>
                                                    <span className="flex items-center gap-2"><Icone className="h-4 w-4 text-purple-600" />{c.nome}</span>
                                                </SelectItem>
                                            );
                                        })}
                                    </SelectContent>
                                </Select>
                                <Button
                                    type="button" variant="outline" size="icon" title="Criar novo campo de experiência"
                                    disabled={!formData.escola}
                                    onClick={() => setNovoCampo({ nome: '', icone: 'BookOpen' })}
                                >
                                    <PlusCircle className="h-4 w-4" />
                                </Button>
                            </div>
                        </div>

                        <div>
                            <Label htmlFor="nivel">Nível</Label>
                            <Select value={formData.nivel} onValueChange={(v) => set('nivel', v)}>
                                <SelectTrigger id="nivel"><SelectValue placeholder="Selecione o nível" /></SelectTrigger>
                                <SelectContent>
                                    {/* Nível antigo que não bate com as turmas atuais continua visível. */}
                                    {[...new Set([...niveis, formData.nivel].filter(Boolean))].map((n) => (
                                        <SelectItem key={n} value={n}>{n}</SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </div>

                        <div>
                            <Label htmlFor="pergunta">Pergunta Facilitadora</Label>
                            <textarea
                                id="pergunta" rows={3} required
                                className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                                value={formData.pergunta}
                                onChange={(e) => set('pergunta', e.target.value)}
                                placeholder="Digite o texto da pergunta facilitadora"
                            />
                        </div>

                        <div>
                            <Label htmlFor="referencia_bncc">Referência (BNCC)</Label>
                            <Input
                                id="referencia_bncc" required maxLength={20}
                                className="font-mono uppercase"
                                value={formData.referencia_bncc}
                                onChange={(e) => set('referencia_bncc', e.target.value)}
                                placeholder="Ex: EI03EO01"
                            />
                            {pergunta?.habilidade_bncc_descricao && formData.referencia_bncc.trim().toUpperCase() === pergunta.habilidade_bncc_codigo && (
                                <p className="mt-1 text-xs text-gray-500">{pergunta.habilidade_bncc_descricao}</p>
                            )}
                        </div>

                        <DialogFooter>
                            <DialogClose asChild><Button type="button" variant="outline" disabled={salvando}>Cancelar</Button></DialogClose>
                            <Button type="submit" disabled={salvando}>{salvando ? 'Salvando...' : 'Salvar'}</Button>
                        </DialogFooter>
                    </form>
                </DialogContent>
            </Dialog>

            <Dialog open={!!novoCampo} onOpenChange={(aberto) => { if (!aberto && !criandoCampo) setNovoCampo(null); }}>
                <DialogContent className="max-w-md">
                    <DialogHeader>
                        <DialogTitle>Novo Campo de Experiência</DialogTitle>
                        <DialogDescription>O campo fica disponível para as perguntas desta escola.</DialogDescription>
                    </DialogHeader>
                    <div className="space-y-4 py-2">
                        <div>
                            <Label htmlFor="novo-campo-nome">Nome do campo</Label>
                            <Input
                                id="novo-campo-nome" maxLength={200}
                                value={novoCampo?.nome || ''}
                                onChange={(e) => setNovoCampo((c) => ({ ...c, nome: e.target.value }))}
                            />
                        </div>
                        <div>
                            <Label>Ícone</Label>
                            <div className="mt-2">
                                <IconPicker
                                    selectedIcon={novoCampo?.icone || 'BookOpen'}
                                    onSelect={(icone) => setNovoCampo((c) => ({ ...c, icone }))}
                                />
                            </div>
                        </div>
                    </div>
                    <DialogFooter>
                        <DialogClose asChild><Button variant="ghost" disabled={criandoCampo}>Cancelar</Button></DialogClose>
                        <Button onClick={handleCriarCampo} disabled={criandoCampo || !novoCampo?.nome.trim()}>
                            {criandoCampo ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Check className="mr-2 h-4 w-4" />}
                            Criar Campo
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </>
    );
};

export default PerguntasTab;