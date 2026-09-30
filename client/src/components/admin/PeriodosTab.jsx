import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { PlusCircle, Edit, Trash2, ChevronLeft, ChevronRight } from 'lucide-react';
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
import { safeFormatDate } from '@/lib/dateUtils';
import {
    listarPeriodosPaginado, listarEscolas,
    criarPeriodoAvaliativo, atualizarPeriodoAvaliativo, excluirPeriodoAvaliativo,
} from '@/services/api';

/*
 * Períodos avaliativos (backend: /periodos-avaliativos/?page=).
 *
 * Cada período pertence a uma escola. O admin vê os de todas as escolas da
 * rede (com a coluna Escola e o filtro); o coordenador, só os da escola dele.
 *
 * Abas: "Vigentes" (em andamento ou futuros, fim >= hoje) e "Encerrados".
 * Lista paginada (10 por página), filtrada no servidor.
 *
 * Regras do backend: fim não pode ser antes do início, e dois períodos do
 * MESMO tipo na mesma escola não podem ter datas em comum (um anual pode
 * conviver com os bimestres dentro dele). O ano, se não informado, vem da
 * data de início.
 *
 * Excluir é definitivo, mas nenhum outro cadastro depende do período
 * (relatórios guardam o período como texto).
 */

const TODAS = 'todas';
const POR_PAGINA = 10;
const ABA_VIGENTES = 'vigentes';
const ABA_ENCERRADOS = 'encerrados';
const LISTA_VAZIA = { results: [], count: 0, total_paginas: 1, totais: { vigentes: 0, encerrados: 0 } };

const TIPO_LABELS = {
    bimestral: 'Bimestral',
    trimestral: 'Trimestral',
    semestral: 'Semestral',
    anual: 'Anual',
};

const FORM_VAZIO = { escola: '', descricao: '', tipo_periodo: '', data_inicio: '', data_fim: '' };

/** `{ error }` (permissão/escopo) ou `{ campo: [mensagens] }` (validação). */
function mensagemDeErro(err) {
    const payload = err?.payload;
    if (payload && typeof payload === 'object' && !payload.error && !payload.detail) {
        const mensagens = Object.values(payload).flat().filter(Boolean);
        if (mensagens.length) return mensagens.join(' ');
    }
    return err?.message || 'Erro inesperado.';
}

/** Data de hoje no fuso do navegador, como YYYY-MM-DD (mesmo formato da API). */
function hojeISO() {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

const PeriodosTab = () => {
    const [aba, setAba] = useState(ABA_VIGENTES);
    const [pagina, setPagina] = useState(1);
    const [filtroEscola, setFiltroEscola] = useState(TODAS);
    const [lista, setLista] = useState(LISTA_VAZIA);
    const [loading, setLoading] = useState(true);
    const [carregouUmaVez, setCarregouUmaVez] = useState(false);
    const [escolas, setEscolas] = useState([]);
    const [isFormOpen, setIsFormOpen] = useState(false);
    const [editando, setEditando] = useState(null);
    const [excluindo, setExcluindo] = useState(null);
    // Descarta respostas atrasadas quando o usuário troca de aba/página rápido.
    const ultimaRequisicao = useRef(0);

    const carregar = useCallback(async () => {
        const id = ++ultimaRequisicao.current;
        setLoading(true);
        try {
            const dados = await listarPeriodosPaginado({
                situacao: aba,
                escola: filtroEscola === TODAS ? undefined : filtroEscola,
                page: pagina,
                pageSize: POR_PAGINA,
            });
            if (id !== ultimaRequisicao.current) return;
            setLista(dados);
            // Ex.: excluiu o único período da última página → o backend devolve a anterior.
            if (dados.pagina && dados.pagina !== pagina) setPagina(dados.pagina);
        } catch (err) {
            if (id !== ultimaRequisicao.current) return;
            toast({ variant: "destructive", title: "Erro ao carregar períodos", description: mensagemDeErro(err) });
        } finally {
            if (id === ultimaRequisicao.current) {
                setLoading(false);
                setCarregouUmaVez(true);
            }
        }
    }, [aba, pagina, filtroEscola]);

    useEffect(() => { carregar(); }, [carregar]);

    // Escolas: lista curta, usada no filtro e no formulário. Busca uma vez só.
    useEffect(() => {
        listarEscolas()
            .then(setEscolas)
            .catch((err) => toast({ variant: "destructive", title: "Erro ao carregar escolas", description: mensagemDeErro(err) }));
    }, []);

    const variasEscolas = escolas.length > 1;
    const escolasAtivas = useMemo(() => escolas.filter((e) => e.ativa !== false), [escolas]);

    // Todo filtro novo volta para a página 1 (no mesmo render, sem requisição extra).
    const trocarAba = (valor) => { setAba(valor); setPagina(1); };
    const trocarEscola = (valor) => { setFiltroEscola(valor); setPagina(1); };

    const abrirFormulario = (periodo) => {
        if (!periodo && !escolasAtivas.length) {
            toast({ variant: "destructive", title: "Nenhuma escola ativa", description: "Cadastre ou reative uma escola antes de criar períodos." });
            return;
        }
        setEditando(periodo);
        setIsFormOpen(true);
    };

    /** Retorna true se salvou (o formulário fecha); false mantém aberto para correção. */
    const handleSalvar = async (dados) => {
        const editandoAgora = !!editando;
        let salvo;
        try {
            salvo = editandoAgora
                ? await atualizarPeriodoAvaliativo(editando.id, dados)
                : await criarPeriodoAvaliativo(dados);
        } catch (err) {
            toast({ variant: "destructive", title: "Erro ao salvar período", description: mensagemDeErro(err) });
            return false;
        }

        toast({ title: `Período ${editandoAgora ? 'atualizado' : 'criado'} com sucesso!` });
        setIsFormOpen(false);
        setEditando(null);

        // Leva o usuário até a aba onde o período salvo aparece.
        const abaDoSalvo = salvo?.data_fim && salvo.data_fim < hojeISO() ? ABA_ENCERRADOS : ABA_VIGENTES;
        if (abaDoSalvo !== aba || (!editandoAgora && pagina !== 1)) {
            setAba(abaDoSalvo);
            setPagina(1); // o efeito de `carregar` recarrega sozinho
        } else {
            carregar();
        }
        return true;
    };

    const handleExcluir = async () => {
        if (!excluindo) return;
        try {
            await excluirPeriodoAvaliativo(excluindo.id);
        } catch (err) {
            toast({ variant: "destructive", title: "Erro ao excluir período", description: mensagemDeErro(err) });
            return;
        }
        toast({ title: "Período excluído com sucesso!" });
        setExcluindo(null);
        carregar();
    };

    const { results: periodos, count, total_paginas: totalPaginas, totais } = lista;
    const primeiro = count ? (pagina - 1) * POR_PAGINA + 1 : 0;
    const ultimo = Math.min(pagina * POR_PAGINA, count);
    const colunas = variasEscolas ? 6 : 5;
    const hoje = hojeISO();

    return (
        <Card>
            <CardHeader className="flex-row items-center justify-between gap-4">
                <div>
                    <CardTitle>Períodos Avaliativos</CardTitle>
                    <CardDescription>
                        {variasEscolas
                            ? 'Defina os ciclos avaliativos das escolas da rede.'
                            : 'Defina os ciclos avaliativos da sua escola.'}
                    </CardDescription>
                </div>
                <Button onClick={() => abrirFormulario(null)}><PlusCircle className="mr-2 h-4 w-4" /> Novo Período</Button>
            </CardHeader>
            <CardContent>
                <div className="mb-4 flex flex-wrap items-center justify-between gap-4">
                    <Tabs value={aba} onValueChange={trocarAba}>
                        <TabsList>
                            <TabsTrigger value={ABA_VIGENTES}>
                                Vigentes <Badge variant="secondary" className="ml-2">{totais.vigentes}</Badge>
                            </TabsTrigger>
                            <TabsTrigger value={ABA_ENCERRADOS}>
                                Encerrados <Badge variant="secondary" className="ml-2">{totais.encerrados}</Badge>
                            </TabsTrigger>
                        </TabsList>
                    </Tabs>
                    {variasEscolas && (
                        <div className="w-64">
                            <Select value={filtroEscola} onValueChange={trocarEscola}>
                                <SelectTrigger aria-label="Filtrar por escola"><SelectValue /></SelectTrigger>
                                <SelectContent>
                                    <SelectItem value={TODAS}>Todas as escolas</SelectItem>
                                    {escolas.map((e) => <SelectItem key={e.id} value={String(e.id)}>{e.nome}</SelectItem>)}
                                </SelectContent>
                            </Select>
                        </div>
                    )}
                </div>

                {!carregouUmaVez ? <p>Carregando períodos...</p> : (
                    <TooltipProvider>
                        {/* Mantém a tabela na tela ao trocar de página/aba, só esmaecida. */}
                        <div className={loading ? 'pointer-events-none opacity-50 transition-opacity' : 'transition-opacity'} aria-busy={loading}>
                            <Table>
                                <TableHeader>
                                    <TableRow>
                                        <TableHead>Descrição</TableHead>
                                        {variasEscolas && <TableHead>Escola</TableHead>}
                                        <TableHead>Tipo</TableHead>
                                        <TableHead>Data de Início</TableHead>
                                        <TableHead>Data de Fim</TableHead>
                                        <TableHead className="text-right">Ações</TableHead>
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    {periodos.length > 0 ? periodos.map((periodo) => {
                                        const emAndamento = periodo.data_inicio <= hoje && periodo.data_fim >= hoje;
                                        return (
                                            <TableRow key={periodo.id}>
                                                <TableCell className="font-medium">
                                                    {periodo.descricao}
                                                    {emAndamento && <Badge className="ml-2">Em andamento</Badge>}
                                                </TableCell>
                                                {variasEscolas && <TableCell>{periodo.escola_nome}</TableCell>}
                                                <TableCell>{TIPO_LABELS[periodo.tipo_periodo] || periodo.tipo_periodo}</TableCell>
                                                <TableCell>{safeFormatDate(periodo.data_inicio, 'dd/MM/yyyy')}</TableCell>
                                                <TableCell>{safeFormatDate(periodo.data_fim, 'dd/MM/yyyy')}</TableCell>
                                                <TableCell className="text-right space-x-2 whitespace-nowrap">
                                                    <Tooltip>
                                                        <TooltipTrigger asChild>
                                                            <Button variant="ghost" size="icon" onClick={() => abrirFormulario(periodo)} aria-label="Editar período">
                                                                <Edit className="h-4 w-4" />
                                                            </Button>
                                                        </TooltipTrigger>
                                                        <TooltipContent><p>Editar Período</p></TooltipContent>
                                                    </Tooltip>
                                                    <Tooltip>
                                                        <TooltipTrigger asChild>
                                                            <Button variant="ghost" size="icon" onClick={() => setExcluindo(periodo)} aria-label="Excluir período">
                                                                <Trash2 className="h-4 w-4 text-red-500" />
                                                            </Button>
                                                        </TooltipTrigger>
                                                        <TooltipContent><p>Excluir Período</p></TooltipContent>
                                                    </Tooltip>
                                                </TableCell>
                                            </TableRow>
                                        );
                                    }) : (
                                        <TableRow>
                                            <TableCell colSpan={colunas} className="text-center text-gray-500">
                                                {aba === ABA_VIGENTES ? 'Nenhum período vigente ou futuro.' : 'Nenhum período encerrado.'}
                                                {filtroEscola !== TODAS && ' (nesta escola)'}
                                            </TableCell>
                                        </TableRow>
                                    )}
                                </TableBody>
                            </Table>
                        </div>

                        {totalPaginas > 1 && (
                            <div className="mt-4 flex flex-wrap items-center justify-between gap-2 text-sm text-gray-600">
                                <span>Mostrando {primeiro}–{ultimo} de {count} períodos</span>
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

            <PeriodoFormDialog
                isOpen={isFormOpen}
                setIsOpen={setIsFormOpen}
                periodo={editando}
                escolas={escolasAtivas}
                onSubmit={handleSalvar}
            />

            <Dialog open={!!excluindo} onOpenChange={() => setExcluindo(null)}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Excluir período</DialogTitle>
                        <DialogDescription>
                            Tem certeza que deseja excluir o período "{excluindo?.descricao}"
                            {variasEscolas && excluindo?.escola_nome ? ` da escola ${excluindo.escola_nome}` : ''}?
                            Esta ação não pode ser desfeita. Relatórios já gerados não são afetados.
                        </DialogDescription>
                    </DialogHeader>
                    <DialogFooter>
                        <DialogClose asChild><Button variant="outline">Cancelar</Button></DialogClose>
                        <Button variant="destructive" onClick={handleExcluir}>Excluir</Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </Card>
    );
};

const PeriodoFormDialog = ({ isOpen, setIsOpen, periodo, escolas, onSubmit }) => {
    const [formData, setFormData] = useState(FORM_VAZIO);
    const [salvando, setSalvando] = useState(false);

    useEffect(() => {
        if (!isOpen) return;
        setFormData(periodo ? {
            escola: String(periodo.escola ?? ''),
            descricao: periodo.descricao || '',
            tipo_periodo: periodo.tipo_periodo || '',
            data_inicio: periodo.data_inicio || '',
            data_fim: periodo.data_fim || '',
        } : {
            ...FORM_VAZIO,
            escola: escolas.length === 1 ? String(escolas[0].id) : '',
        });
    // escolas pode chegar depois; só reinicia ao abrir ou trocar o período.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [periodo, isOpen]);

    const set = (campo, valor) => setFormData((prev) => ({ ...prev, [campo]: valor }));
    const handleChange = (e) => set(e.target.name, e.target.value);

    const handleSubmit = async (e) => {
        e.preventDefault();
        // Os Selects do Radix não participam da validação nativa do form.
        const faltando = [
            !periodo && !formData.escola && 'escola',
            !formData.tipo_periodo && 'tipo',
        ].filter(Boolean);
        if (faltando.length) {
            toast({ variant: "destructive", title: "Campos obrigatórios", description: `Selecione: ${faltando.join(', ')}.` });
            return;
        }
        if (formData.data_fim < formData.data_inicio) {
            toast({ variant: "destructive", title: "Datas inválidas", description: "A data de fim não pode ser anterior à data de início." });
            return;
        }

        const dados = {
            descricao: formData.descricao.trim(),
            tipo_periodo: formData.tipo_periodo,
            data_inicio: formData.data_inicio,
            data_fim: formData.data_fim,
        };
        if (!periodo) dados.escola = formData.escola; // na edição a escola não muda

        setSalvando(true);
        try {
            await onSubmit(dados);
        } finally {
            setSalvando(false);
        }
    };

    const escolaDoPeriodo = periodo
        ? (escolas.find((e) => String(e.id) === formData.escola)?.nome || periodo.escola_nome)
        : null;

    return (
        // Não fecha no meio do salvamento (Esc/clique fora).
        <Dialog open={isOpen} onOpenChange={(aberto) => { if (!salvando) setIsOpen(aberto); }}>
            <DialogContent>
                <DialogHeader>
                    <DialogTitle>{periodo ? 'Editar Período' : 'Novo Período'}</DialogTitle>
                </DialogHeader>
                <form onSubmit={handleSubmit} className="space-y-4 pt-4">
                    {periodo ? (
                        escolas.length > 1 && (
                            <div>
                                <Label>Escola</Label>
                                <p className="mt-1 text-sm text-gray-600">{escolaDoPeriodo}</p>
                            </div>
                        )
                    ) : escolas.length > 1 && (
                        <div>
                            <Label htmlFor="escola">Escola</Label>
                            <Select value={formData.escola} onValueChange={(v) => set('escola', v)}>
                                <SelectTrigger id="escola"><SelectValue placeholder="Selecione a escola" /></SelectTrigger>
                                <SelectContent>
                                    {escolas.map((e) => <SelectItem key={e.id} value={String(e.id)}>{e.nome}</SelectItem>)}
                                </SelectContent>
                            </Select>
                        </div>
                    )}
                    <div>
                        <Label htmlFor="descricao">Descrição</Label>
                        <Input id="descricao" name="descricao" value={formData.descricao} onChange={handleChange} maxLength={200} required placeholder="Ex: 1º Bimestre" />
                    </div>
                    <div>
                        <Label htmlFor="tipo_periodo">Tipo</Label>
                        <Select value={formData.tipo_periodo} onValueChange={(v) => set('tipo_periodo', v)}>
                            <SelectTrigger id="tipo_periodo"><SelectValue placeholder="Selecione o tipo" /></SelectTrigger>
                            <SelectContent>
                                {Object.entries(TIPO_LABELS).map(([valor, label]) => <SelectItem key={valor} value={valor}>{label}</SelectItem>)}
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
                            <Input id="data_fim" name="data_fim" type="date" min={formData.data_inicio || undefined} value={formData.data_fim} onChange={handleChange} required />
                        </div>
                    </div>
                    <DialogFooter>
                        <DialogClose asChild><Button type="button" variant="outline" disabled={salvando}>Cancelar</Button></DialogClose>
                        <Button type="submit" disabled={salvando}>{salvando ? 'Salvando...' : 'Salvar'}</Button>
                    </DialogFooter>
                </form>
            </DialogContent>
        </Dialog>
    );
};

export default PeriodosTab;