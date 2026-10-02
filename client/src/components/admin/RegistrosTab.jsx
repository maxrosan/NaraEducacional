import React, { useState, useEffect, useCallback, useRef } from 'react';
import { ChevronLeft, ChevronRight, Search, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { toast } from '@/components/ui/use-toast';
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogClose, DialogDescription } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import {
    listarFrequenciasRegistro, atualizarFrequenciaRegistro, listarEscolas,
    FREQUENCIAS_REGISTRO,
} from '@/services/api';

const POR_PAGINA = 10;
const ESPERA_BUSCA_MS = 400;
const TODAS = 'todas';

const ROTULO_FREQUENCIA = Object.fromEntries(FREQUENCIAS_REGISTRO.map((f) => [f.valor, f.rotulo]));
const ROTULO_TURNO = { manha: 'Manhã', tarde: 'Tarde', integral: 'Integral' };
const TOTAIS_VAZIOS = Object.fromEntries(FREQUENCIAS_REGISTRO.map((f) => [f.valor, 0]));

function useValorAtrasado(valor, espera) {
    const [atrasado, setAtrasado] = useState(valor);
    useEffect(() => {
        const t = setTimeout(() => setAtrasado(valor), espera);
        return () => clearTimeout(t);
    }, [valor, espera]);
    return atrasado;
}

function avisarErro(titulo, erro) {
    toast({ variant: 'destructive', title: titulo, description: erro?.message || 'Tente novamente.' });
}

export default function RegistrosTab() {
    const [escolas, setEscolas] = useState([]);

    // filtros.escola guarda o UUID da escola: vai na query string do GET.
    // No body do PATCH em lote vai o id (escolaFiltrada.id).
    const [filtros, setFiltros] = useState({ escola: TODAS, frequencia: TODAS, busca: '', pagina: 1 });
    const { escola, frequencia, pagina } = filtros;
    const [busca, setBusca] = useState('');
    const buscaAtrasada = useValorAtrasado(busca.trim(), ESPERA_BUSCA_MS);

    const [dados, setDados] = useState({ results: [], count: 0, total_paginas: 1, totais: TOTAIS_VAZIOS });
    const [carregando, setCarregando] = useState(true);
    const [salvandoIds, setSalvandoIds] = useState(() => new Set());
    const [selecionadas, setSelecionadas] = useState(() => new Set());

    const [lote, setLote] = useState(null);
    const [aplicandoLote, setAplicandoLote] = useState(false);

    const requisicaoAtual = useRef(0);

    const mudarFiltro = (campo, valor) => {
        setFiltros((f) => (f[campo] === valor ? f : { ...f, [campo]: valor, pagina: 1 }));
        setSelecionadas(new Set());
    };
    const setEscola = (v) => mudarFiltro('escola', v);
    const setFrequencia = (v) => mudarFiltro('frequencia', v);
    const setPagina = (fn) => setFiltros((f) => ({ ...f, pagina: typeof fn === 'function' ? fn(f.pagina) : fn }));

    useEffect(() => {
        setFiltros((f) => (f.busca === buscaAtrasada ? f : { ...f, busca: buscaAtrasada, pagina: 1 }));
        setSelecionadas(new Set());
    }, [buscaAtrasada]);

    useEffect(() => {
        listarEscolas()
            .then((lista) => setEscolas((lista || []).filter((e) => e.ativa !== false)))
            .catch(() => setEscolas([]));
    }, []);

    const carregar = useCallback(async ({ silencioso = false } = {}) => {
        const id = ++requisicaoAtual.current;
        if (!silencioso) setCarregando(true);
        try {
            const resp = await listarFrequenciasRegistro({
                escola: escola === TODAS ? undefined : escola,
                frequencia: frequencia === TODAS ? undefined : frequencia,
                busca: filtros.busca || undefined,
                page: pagina,
                pageSize: POR_PAGINA,
            });
            if (id !== requisicaoAtual.current) return;
            setDados({ ...resp, totais: { ...TOTAIS_VAZIOS, ...resp.totais } });
            if (resp.pagina !== pagina) setPagina(resp.pagina);
        } catch (erro) {
            if (id === requisicaoAtual.current) avisarErro('Erro ao carregar as turmas', erro);
        } finally {
            if (id === requisicaoAtual.current) setCarregando(false);
        }
    }, [escola, frequencia, filtros.busca, pagina]);

    useEffect(() => { carregar(); }, [carregar]);

    const alterarFrequencia = async (turma, nova) => {
        if (nova === turma.frequencia_registro) return;
        const anterior = turma.frequencia_registro;

        const aplicar = (de, para) => setDados((d) => ({
            ...d,
            results: d.results.map((t) => (t.id === turma.id ? { ...t, frequencia_registro: para } : t)),
            totais: { ...d.totais, [de]: Math.max(0, d.totais[de] - 1), [para]: d.totais[para] + 1 },
        }));

        aplicar(anterior, nova);
        setSalvandoIds((s) => new Set(s).add(turma.id));
        try {
            await atualizarFrequenciaRegistro(nova, { turmas: [turma.id] });
            toast({ title: 'Frequência atualizada', description: `${turma.nome}: ${ROTULO_FREQUENCIA[nova].toLowerCase()}.` });
        } catch (erro) {
            aplicar(nova, anterior);
            avisarErro('Não foi possível alterar a frequência', erro);
        } finally {
            setSalvandoIds((s) => { const n = new Set(s); n.delete(turma.id); return n; });
        }
    };

    const escolaFiltrada = escolas.find((e) => String(e.uuid) === escola) || null;

    const aplicarLote = async () => {
        if (!lote) return;
        setAplicandoLote(true);
        try {
            const alvo = lote.tipo === 'escola' ? { escola: escolaFiltrada?.id } : { turmas: [...selecionadas] };
            const { atualizadas } = await atualizarFrequenciaRegistro(lote.frequencia, alvo);
            toast({
                title: 'Frequência atualizada',
                description: `${atualizadas} turma(s) agora ${ROTULO_FREQUENCIA[lote.frequencia].toLowerCase()}.`,
            });
            setLote(null);
            setSelecionadas(new Set());
            await carregar({ silencioso: true });
        } catch (erro) {
            avisarErro('Não foi possível aplicar a frequência', erro);
        } finally {
            setAplicandoLote(false);
        }
    };

    const idsDaPagina = dados.results.map((t) => t.id);
    const todasDaPaginaMarcadas = idsDaPagina.length > 0 && idsDaPagina.every((id) => selecionadas.has(id));

    const marcarPagina = () => setSelecionadas((s) => {
        const n = new Set(s);
        idsDaPagina.forEach((id) => (todasDaPaginaMarcadas ? n.delete(id) : n.add(id)));
        return n;
    });

    const marcar = (id) => setSelecionadas((s) => {
        const n = new Set(s);
        if (n.has(id)) n.delete(id); else n.add(id);
        return n;
    });

    const nomeEscolaFiltrada = escolaFiltrada?.nome;
    const totalGeral = Object.values(dados.totais).reduce((a, b) => a + b, 0);
    const mostrarFiltroEscola = escolas.length > 1;

    return (
        <Card>
            <CardHeader>
                <CardTitle>Frequência de registro</CardTitle>
                <CardDescription>
                    Defina de quanto em quanto tempo cada turma deve ser registrada pelas professoras.
                    Turmas novas começam como semanais.
                </CardDescription>
            </CardHeader>

            <CardContent className="space-y-4">

                <div className="flex flex-wrap gap-2" role="group" aria-label="Filtrar por frequência">
                    <Button
                        size="sm"
                        variant={frequencia === TODAS ? 'default' : 'outline'}
                        onClick={() => setFrequencia(TODAS)}
                    >
                        Todas <Badge variant="secondary" className="ml-2">{totalGeral}</Badge>
                    </Button>
                    {FREQUENCIAS_REGISTRO.map((f) => (
                        <Button
                            key={f.valor}
                            size="sm"
                            variant={frequencia === f.valor ? 'default' : 'outline'}
                            onClick={() => setFrequencia(f.valor)}
                        >
                            {f.rotulo} <Badge variant="secondary" className="ml-2">{dados.totais[f.valor]}</Badge>
                        </Button>
                    ))}
                </div>

                <div className="flex flex-col gap-2 sm:flex-row">
                    <div className="relative flex-1">
                        <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                        <Input
                            value={busca}
                            onChange={(e) => setBusca(e.target.value)}
                            placeholder="Buscar turma pelo nome"
                            className="pl-8"
                            aria-label="Buscar turma pelo nome"
                        />
                    </div>
                    {mostrarFiltroEscola && (
                        <Select value={escola} onValueChange={setEscola}>
                            <SelectTrigger className="sm:w-64" aria-label="Filtrar por escola">
                                <SelectValue placeholder="Escola" />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value={TODAS}>Todas as escolas</SelectItem>
                                {escolas.map((e) => <SelectItem key={e.uuid} value={String(e.uuid)}>{e.nome}</SelectItem>)}
                            </SelectContent>
                        </Select>
                    )}
                </div>

                {(selecionadas.size > 0 || escola !== TODAS) && (
                    <div className="flex flex-wrap items-center gap-2 rounded-md border bg-muted/40 p-2 text-sm">
                        {selecionadas.size > 0 ? (
                            <>
                                <span>{selecionadas.size} turma(s) selecionada(s):</span>
                                <SeletorLote onEscolher={(f) => setLote({ tipo: 'selecionadas', frequencia: f })} />
                                <Button size="sm" variant="ghost" onClick={() => setSelecionadas(new Set())}>
                                    Limpar seleção
                                </Button>
                            </>
                        ) : (
                            <>
                                <span>Todas as turmas ativas de {nomeEscolaFiltrada}:</span>
                                <SeletorLote onEscolher={(f) => setLote({ tipo: 'escola', frequencia: f })} />
                            </>
                        )}
                    </div>
                )}

                <div className="overflow-x-auto">
                    <Table>
                        <TableHeader>
                            <TableRow>
                                <TableHead className="w-10">
                                    <input
                                        type="checkbox"
                                        className="h-4 w-4 cursor-pointer accent-primary"
                                        checked={todasDaPaginaMarcadas}
                                        onChange={marcarPagina}
                                        disabled={carregando || idsDaPagina.length === 0}
                                        aria-label="Selecionar as turmas desta página"
                                    />
                                </TableHead>
                                <TableHead>Turma</TableHead>
                                {mostrarFiltroEscola && <TableHead>Escola</TableHead>}
                                <TableHead>Turno</TableHead>
                                <TableHead className="w-48">Frequência</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {carregando ? (
                                Array.from({ length: 5 }).map((_, i) => (
                                    <TableRow key={`esqueleto-${i}`}>
                                        <TableCell colSpan={mostrarFiltroEscola ? 5 : 4}>
                                            <div className="h-5 animate-pulse rounded bg-muted" />
                                        </TableCell>
                                    </TableRow>
                                ))
                            ) : dados.results.length === 0 ? (
                                <TableRow>
                                    <TableCell colSpan={mostrarFiltroEscola ? 5 : 4} className="py-8 text-center text-muted-foreground">
                                        Nenhuma turma ativa encontrada com esses filtros.
                                    </TableCell>
                                </TableRow>
                            ) : (
                                dados.results.map((turma) => (
                                    <TableRow key={turma.id} data-state={selecionadas.has(turma.id) ? 'selected' : undefined}>
                                        <TableCell>
                                            <input
                                                type="checkbox"
                                                className="h-4 w-4 cursor-pointer accent-primary"
                                                checked={selecionadas.has(turma.id)}
                                                onChange={() => marcar(turma.id)}
                                                aria-label={`Selecionar ${turma.nome}`}
                                            />
                                        </TableCell>
                                        <TableCell className="font-medium">
                                            {turma.nome}
                                            {turma.ano_letivo && <span className="ml-2 text-xs text-muted-foreground">{turma.ano_letivo}</span>}
                                        </TableCell>
                                        {mostrarFiltroEscola && <TableCell>{turma.escola_nome}</TableCell>}
                                        <TableCell>{ROTULO_TURNO[turma.turno] || turma.turno}</TableCell>
                                        <TableCell>
                                            <div className="flex items-center gap-2">
                                                <Select
                                                    value={turma.frequencia_registro}
                                                    onValueChange={(v) => alterarFrequencia(turma, v)}
                                                    disabled={salvandoIds.has(turma.id)}
                                                >
                                                    <SelectTrigger className="h-8" aria-label={`Frequência de ${turma.nome}`}>
                                                        <SelectValue />
                                                    </SelectTrigger>
                                                    <SelectContent>
                                                        {FREQUENCIAS_REGISTRO.map((f) => (
                                                            <SelectItem key={f.valor} value={f.valor}>{f.rotulo}</SelectItem>
                                                        ))}
                                                    </SelectContent>
                                                </Select>
                                                {salvandoIds.has(turma.id) && <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />}
                                            </div>
                                        </TableCell>
                                    </TableRow>
                                ))
                            )}
                        </TableBody>
                    </Table>
                </div>

                <div className="flex items-center justify-between text-sm text-muted-foreground">
                    <span>{dados.count} turma(s)</span>
                    <div className="flex items-center gap-2">
                        <Button
                            size="icon" variant="outline"
                            onClick={() => setPagina((p) => p - 1)}
                            disabled={carregando || pagina <= 1}
                            aria-label="Página anterior"
                        >
                            <ChevronLeft className="h-4 w-4" />
                        </Button>
                        <span>Página {pagina} de {Math.max(1, dados.total_paginas)}</span>
                        <Button
                            size="icon" variant="outline"
                            onClick={() => setPagina((p) => p + 1)}
                            disabled={carregando || pagina >= dados.total_paginas}
                            aria-label="Próxima página"
                        >
                            <ChevronRight className="h-4 w-4" />
                        </Button>
                    </div>
                </div>
            </CardContent>

            <Dialog open={!!lote} onOpenChange={(aberto) => !aberto && !aplicandoLote && setLote(null)}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Alterar frequência em lote</DialogTitle>
                        <DialogDescription>
                            {lote?.tipo === 'escola'
                                ? `Todas as turmas ativas de ${nomeEscolaFiltrada} passarão a ter registro ${ROTULO_FREQUENCIA[lote?.frequencia]?.toLowerCase()}.`
                                : `${selecionadas.size} turma(s) passarão a ter registro ${ROTULO_FREQUENCIA[lote?.frequencia]?.toLowerCase()}.`}
                        </DialogDescription>
                    </DialogHeader>
                    <DialogFooter>
                        <DialogClose asChild>
                            <Button variant="outline" disabled={aplicandoLote}>Cancelar</Button>
                        </DialogClose>
                        <Button onClick={aplicarLote} disabled={aplicandoLote}>
                            {aplicandoLote && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                            Aplicar
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </Card>
    );
}

function SeletorLote({ onEscolher }) {
    return (
        <Select value="" onValueChange={onEscolher}>
            <SelectTrigger className="h-8 w-44" aria-label="Escolher frequência para aplicar">
                <SelectValue placeholder="Definir frequência…" />
            </SelectTrigger>
            <SelectContent>
                {FREQUENCIAS_REGISTRO.map((f) => (
                    <SelectItem key={f.valor} value={f.valor}>{f.rotulo}</SelectItem>
                ))}
            </SelectContent>
        </Select>
    );
}