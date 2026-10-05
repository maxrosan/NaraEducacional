import React, { useState, useEffect, useMemo, useRef, useCallback } from 'react';
import {
    FileText, Mic, Pencil, CalendarDays, Copy, Check, Loader2,
    ChevronLeft, ChevronRight, ChevronDown, ChevronUp, RotateCcw,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { toast } from '@/components/ui/use-toast';
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from '@/components/ui/dialog';
import { Badge } from '@/components/ui/badge';
import {
    listarPromptsRede, listarPromptsDaEscola,
    salvarPromptPersonalizado, salvarPromptGlobal,
} from '@/services/api';

const ICONE_CATEGORIA = {
    'Relatórios': FileText,
    'Voz': Mic,
    'Desenho': Pencil,
    'Planejamento': CalendarDays,
};

const ESCOLAS_POR_PAGINA = 10;
const FILTROS = [
    { valor: 'todas', rotulo: 'Todas' },
    { valor: 'personalizadas', rotulo: 'Personalizadas' },
    { valor: 'global', rotulo: 'Usando o global' },
];

function formatarData(iso) {
    if (!iso) return '—';
    return new Date(iso).toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit', year: 'numeric' });
}

function avisarErro(titulo, erro) {
    toast({ variant: 'destructive', title: titulo, description: erro?.message || 'Tente novamente.' });
}

function BotaoCopiar({ texto, rotulo = 'Copiar' }) {
    const [copiado, setCopiado] = useState(false);
    const copiar = async () => {
        try {
            await navigator.clipboard.writeText(texto || '');
            setCopiado(true);
            setTimeout(() => setCopiado(false), 2000);
        } catch {
            avisarErro('Não foi possível copiar', null);
        }
    };
    return (
        <Button type="button" size="sm" variant="outline" onClick={copiar} disabled={!texto}>
            {copiado ? <Check className="mr-2 h-4 w-4" /> : <Copy className="mr-2 h-4 w-4" />}
            {copiado ? 'Copiado' : rotulo}
        </Button>
    );
}

function TextoPrompt({ texto, vazio }) {
    const [expandido, setExpandido] = useState(false);
    if (!texto) {
        return <p className="rounded-md border border-dashed p-4 text-sm text-muted-foreground">{vazio}</p>;
    }
    const longo = texto.length > 600 || texto.split('\n').length > 8;
    return (
        <div className="space-y-2">
            <pre
                className={`whitespace-pre-wrap break-words rounded-md border bg-muted/40 p-4 font-sans text-sm leading-relaxed ${
                    longo && !expandido ? 'max-h-48 overflow-hidden' : ''
                }`}
            >
                {texto}
            </pre>
            {longo && (
                <Button type="button" size="sm" variant="ghost" onClick={() => setExpandido((v) => !v)}>
                    {expandido ? <ChevronUp className="mr-2 h-4 w-4" /> : <ChevronDown className="mr-2 h-4 w-4" />}
                    {expandido ? 'Recolher' : 'Ver completo'}
                </Button>
            )}
        </div>
    );
}

function EditorPrompt({ alvo, textoGlobal, carregando, textoInicial, onCancelar, onSalvar, salvando }) {
    const [texto, setTexto] = useState(textoInicial);
    const [confirmarGlobal, setConfirmarGlobal] = useState(false);

    useEffect(() => {
        setTexto(textoInicial);
        setConfirmarGlobal(false);
    }, [textoInicial, alvo]);

    const ehGlobal = alvo?.tipo === 'global';
    const alterado = texto !== textoInicial;
    const personalizadoAtual = !ehGlobal && textoInicial.trim() !== '';

    const fechar = () => {
        if (alterado && !salvando && !window.confirm('Descartar as alterações deste prompt?')) return;
        onCancelar();
    };

    return (
        <Dialog open={!!alvo} onOpenChange={(aberto) => !aberto && fechar()}>
            <DialogContent className="max-w-5xl">
                <DialogHeader>
                    <DialogTitle>
                        {ehGlobal ? `Prompt global de ${alvo?.categoria.titulo}` : `${alvo?.categoria.titulo} · ${alvo?.escola.nome}`}
                    </DialogTitle>
                    <DialogDescription>
                        {ehGlobal
                            ? 'Vale para todas as escolas que não personalizaram esta categoria.'
                            : 'Com o personalizado preenchido, esta escola deixa de usar o prompt global nesta categoria. Em branco, volta a usar o global.'}
                    </DialogDescription>
                </DialogHeader>

                {carregando ? (
                    <div className="flex items-center justify-center py-16">
                        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                    </div>
                ) : (
                    <div className={`grid gap-4 ${ehGlobal ? '' : 'md:grid-cols-2'}`}>
                        {!ehGlobal && (
                            <div className="flex min-w-0 flex-col gap-2">
                                <div className="flex items-center justify-between gap-2">
                                    <span className="text-sm font-medium">Global</span>
                                    <Button
                                        type="button" size="sm" variant="outline"
                                        onClick={() => setTexto(textoGlobal)}
                                        disabled={!textoGlobal || salvando}
                                    >
                                        <Copy className="mr-2 h-4 w-4" />
                                        Usar como base
                                    </Button>
                                </div>
                                <pre className="h-80 overflow-auto whitespace-pre-wrap break-words rounded-md border bg-muted/40 p-3 font-sans text-sm leading-relaxed text-muted-foreground">
                                    {textoGlobal || 'Esta categoria ainda não tem prompt global.'}
                                </pre>
                            </div>
                        )}
                        <div className="flex min-w-0 flex-col gap-2">
                            <div className="flex h-9 items-center justify-between gap-2">
                                <label htmlFor="texto-prompt" className="text-sm font-medium">
                                    {ehGlobal ? 'Texto do prompt global' : 'Personalizado da escola'}
                                </label>
                                <span className="text-xs text-muted-foreground">{texto.length} caracteres</span>
                            </div>
                            <textarea
                                id="texto-prompt"
                                value={texto}
                                onChange={(e) => setTexto(e.target.value)}
                                disabled={salvando}
                                placeholder={ehGlobal ? 'Descreva o comportamento esperado da IA…' : 'Em branco: a escola usa o prompt global.'}
                                className="h-80 w-full resize-none rounded-md border bg-background p-3 text-sm leading-relaxed outline-none focus-visible:ring-2 focus-visible:ring-ring"
                            />
                        </div>
                    </div>
                )}

                <DialogFooter className="flex-col-reverse gap-2 sm:flex-row sm:justify-between">
                    <div>
                        {personalizadoAtual && (
                            confirmarGlobal ? (
                                <div className="flex flex-wrap items-center gap-2 text-sm">
                                    <span>Apagar o personalizado e voltar ao global?</span>
                                    <Button type="button" size="sm" variant="destructive" onClick={() => onSalvar('')} disabled={salvando}>
                                        Confirmar
                                    </Button>
                                    <Button type="button" size="sm" variant="ghost" onClick={() => setConfirmarGlobal(false)} disabled={salvando}>
                                        Não
                                    </Button>
                                </div>
                            ) : (
                                <Button type="button" variant="ghost" onClick={() => setConfirmarGlobal(true)} disabled={salvando || carregando}>
                                    <RotateCcw className="mr-2 h-4 w-4" />
                                    Voltar a usar o global
                                </Button>
                            )
                        )}
                    </div>
                    <div className="flex gap-2">
                        <Button type="button" variant="outline" onClick={fechar} disabled={salvando}>Cancelar</Button>
                        <Button type="button" onClick={() => onSalvar(texto)} disabled={salvando || carregando || !alterado}>
                            {salvando && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                            Salvar
                        </Button>
                    </div>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}

export default function PromptsTab() {
    const [rede, setRede] = useState(null);
    const [carregando, setCarregando] = useState(true);
    const [erro, setErro] = useState(null);

    const [categoriaId, setCategoriaId] = useState(null);
    const [filtro, setFiltro] = useState('todas');
    const [pagina, setPagina] = useState(1);

    const [alvo, setAlvo] = useState(null);
    const [textoInicial, setTextoInicial] = useState('');
    const [carregandoTexto, setCarregandoTexto] = useState(false);
    const [salvando, setSalvando] = useState(false);

    const textosPorEscola = useRef(new Map());
    const aberturaAtual = useRef(0);

    const carregar = useCallback(async () => {
        setCarregando(true);
        setErro(null);
        try {
            const dados = await listarPromptsRede();
            setRede(dados);
            setCategoriaId((atual) => (
                dados.categorias.some((c) => c.id === atual) ? atual : dados.categorias[0]?.id ?? null
            ));
        } catch (e) {
            setErro(e);
        } finally {
            setCarregando(false);
        }
    }, []);

    useEffect(() => { carregar(); }, [carregar]);

    useEffect(() => { setPagina(1); }, [categoriaId, filtro]);

    const categoria = rede?.categorias.find((c) => c.id === categoriaId) ?? null;
    const multiRede = useMemo(
        () => new Set((rede?.escolas ?? []).map((e) => e.instituicao_nome)).size > 1,
        [rede],
    );

    const linhas = useMemo(() => {
        if (!rede || !categoria) return [];
        const personalizadas = new Map(categoria.personalizadas.map((p) => [p.escola, p.atualizado_em]));
        return rede.escolas
            .map((escola) => ({
                escola,
                personalizada: personalizadas.has(escola.id),
                atualizadoEm: personalizadas.get(escola.id) ?? null,
            }))
            .filter((l) => (
                filtro === 'todas' || (filtro === 'personalizadas' ? l.personalizada : !l.personalizada)
            ));
    }, [rede, categoria, filtro]);

    const totalPaginas = Math.max(1, Math.ceil(linhas.length / ESCOLAS_POR_PAGINA));
    const paginaAtual = Math.min(pagina, totalPaginas);
    const linhasDaPagina = linhas.slice((paginaAtual - 1) * ESCOLAS_POR_PAGINA, paginaAtual * ESCOLAS_POR_PAGINA);

    const abrirEscola = async (escola) => {
        const id = ++aberturaAtual.current;
        setAlvo({ tipo: 'escola', categoria, escola });
        const emCache = textosPorEscola.current.get(escola.id);
        if (emCache) {
            setTextoInicial(emCache.get(categoria.id) ?? '');
            return;
        }
        setTextoInicial('');
        setCarregandoTexto(true);
        try {
            const categorias = await listarPromptsDaEscola(escola.id);
            const textos = new Map(categorias.map((c) => [
                c.id, c.template_resolvido?.origem === 'personalizado' ? c.template_resolvido.texto : '',
            ]));
            textosPorEscola.current.set(escola.id, textos);
            if (id === aberturaAtual.current) setTextoInicial(textos.get(categoria.id) ?? '');
        } catch (e) {
            if (id === aberturaAtual.current) {
                avisarErro('Não foi possível abrir o prompt da escola', e);
                setAlvo(null);
            }
        } finally {
            if (id === aberturaAtual.current) setCarregandoTexto(false);
        }
    };

    const abrirGlobal = () => {
        aberturaAtual.current += 1;
        setCarregandoTexto(false);
        setAlvo({ tipo: 'global', categoria });
        setTextoInicial(categoria.global.texto || '');
    };

    const fecharEditor = () => {
        aberturaAtual.current += 1;
        setAlvo(null);
        setCarregandoTexto(false);
    };

    const atualizarCategoria = (id, alterar) => setRede((r) => ({
        ...r,
        categorias: r.categorias.map((c) => (c.id === id ? alterar(c) : c)),
    }));

    const salvar = async (texto) => {
        if (!alvo) return;
        setSalvando(true);
        try {
            if (alvo.tipo === 'global') {
                const resp = await salvarPromptGlobal(alvo.categoria.id, texto);
                atualizarCategoria(alvo.categoria.id, (c) => ({
                    ...c, global: { texto: resp.prompt_global ?? texto, atualizado_em: resp.atualizado_em },
                }));
                toast({ title: 'Prompt global salvo', description: `${alvo.categoria.titulo}: vale para todas as escolas sem personalização.` });
            } else {
                const resp = await salvarPromptPersonalizado(alvo.categoria.id, alvo.escola.id, texto);
                const personalizado = texto.trim() !== '';
                textosPorEscola.current.get(alvo.escola.id)?.set(alvo.categoria.id, texto);
                atualizarCategoria(alvo.categoria.id, (c) => {
                    const outras = c.personalizadas.filter((p) => p.escola !== alvo.escola.id);
                    return {
                        ...c,
                        personalizadas: personalizado
                            ? [...outras, { escola: alvo.escola.id, atualizado_em: resp.atualizado_em }]
                            : outras,
                    };
                });
                toast({
                    title: personalizado ? 'Prompt personalizado salvo' : 'Escola voltou ao prompt global',
                    description: `${alvo.categoria.titulo} · ${alvo.escola.nome}`,
                });
            }
            fecharEditor();
        } catch (e) {
            avisarErro('Não foi possível salvar o prompt', e);
        } finally {
            setSalvando(false);
        }
    };

    if (carregando) {
        return (
            <div className="flex items-center justify-center py-16">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
        );
    }

    if (erro) {
        return (
            <Card>
                <CardContent className="flex flex-col items-center gap-3 py-12 text-center">
                    <p className="font-medium text-destructive">Erro ao carregar os prompts</p>
                    <p className="text-sm text-muted-foreground">{erro.message}</p>
                    <Button onClick={carregar}>Tentar novamente</Button>
                </CardContent>
            </Card>
        );
    }

    const totalEscolas = rede.escolas.length;

    return (
        <Card>
            <CardHeader>
                <CardTitle>Prompts</CardTitle>
                <CardDescription>
                    Todas as escolas usam o prompt global de cada módulo. Uma escola com prompt
                    personalizado passa a usar o dela naquele módulo; as alterações valem nas próximas
                    chamadas da IA.
                </CardDescription>
            </CardHeader>

            <CardContent className="space-y-6">
                {rede.categorias.length === 0 ? (
                    <p className="py-8 text-center text-sm text-muted-foreground">
                        Nenhuma categoria de prompt ativa.
                    </p>
                ) : (
                    <>
                        <div className="flex flex-wrap gap-2" role="tablist" aria-label="Categorias de prompt">
                            {rede.categorias.map((c) => {
                                const Icone = ICONE_CATEGORIA[c.titulo] ?? FileText;
                                const ativa = c.id === categoriaId;
                                return (
                                    <Button
                                        key={c.id}
                                        role="tab"
                                        aria-selected={ativa}
                                        variant={ativa ? 'default' : 'outline'}
                                        onClick={() => setCategoriaId(c.id)}
                                    >
                                        <Icone className="mr-2 h-4 w-4" />
                                        {c.titulo}
                                        {c.personalizadas.length > 0 && (
                                            <Badge variant="secondary" className="ml-2" title="Escolas com prompt personalizado">
                                                {c.personalizadas.length}/{totalEscolas}
                                            </Badge>
                                        )}
                                    </Button>
                                );
                            })}
                        </div>

                        {categoria && (
                            <>
                                <section className="space-y-3" aria-labelledby="titulo-global">
                                    <div className="flex flex-wrap items-center justify-between gap-2">
                                        <div>
                                            <h3 id="titulo-global" className="font-medium">Prompt global</h3>
                                            <p className="text-xs text-muted-foreground">
                                                {rede.pode_editar_global
                                                    ? `Atualizado em ${formatarData(categoria.global.atualizado_em)}`
                                                    : 'Definido pela plataforma. Para mudar o texto de uma escola, personalize abaixo.'}
                                            </p>
                                        </div>
                                        <div className="flex gap-2">
                                            <BotaoCopiar texto={categoria.global.texto} />
                                            {rede.pode_editar_global && (
                                                <Button size="sm" onClick={abrirGlobal}>
                                                    <Pencil className="mr-2 h-4 w-4" />
                                                    Editar global
                                                </Button>
                                            )}
                                        </div>
                                    </div>
                                    <TextoPrompt
                                        key={categoria.id}
                                        texto={categoria.global.texto}
                                        vazio="Esta categoria ainda não tem prompt global."
                                    />
                                </section>

                                <section className="space-y-3" aria-labelledby="titulo-escolas">
                                    <div className="flex flex-wrap items-center justify-between gap-2">
                                        <h3 id="titulo-escolas" className="font-medium">Escolas</h3>
                                        <div className="flex flex-wrap gap-2" role="group" aria-label="Filtrar escolas">
                                            {FILTROS.map((f) => (
                                                <Button
                                                    key={f.valor}
                                                    size="sm"
                                                    variant={filtro === f.valor ? 'default' : 'outline'}
                                                    onClick={() => setFiltro(f.valor)}
                                                >
                                                    {f.rotulo}
                                                </Button>
                                            ))}
                                        </div>
                                    </div>

                                    <div className="overflow-x-auto">
                                        <Table>
                                            <TableHeader>
                                                <TableRow>
                                                    <TableHead>Escola</TableHead>
                                                    {multiRede && <TableHead>Rede</TableHead>}
                                                    <TableHead>Prompt em uso</TableHead>
                                                    <TableHead>Personalizado em</TableHead>
                                                    <TableHead className="w-36 text-right">Ação</TableHead>
                                                </TableRow>
                                            </TableHeader>
                                            <TableBody>
                                                {linhasDaPagina.length === 0 ? (
                                                    <TableRow>
                                                        <TableCell colSpan={multiRede ? 5 : 4} className="py-8 text-center text-muted-foreground">
                                                            {totalEscolas === 0 ? 'Nenhuma escola ativa.' : 'Nenhuma escola neste filtro.'}
                                                        </TableCell>
                                                    </TableRow>
                                                ) : (
                                                    linhasDaPagina.map(({ escola, personalizada, atualizadoEm }) => (
                                                        <TableRow key={escola.id}>
                                                            <TableCell className="font-medium">{escola.nome}</TableCell>
                                                            {multiRede && <TableCell>{escola.instituicao_nome}</TableCell>}
                                                            <TableCell>
                                                                {personalizada
                                                                    ? <Badge>Personalizado</Badge>
                                                                    : <Badge variant="outline">Global</Badge>}
                                                            </TableCell>
                                                            <TableCell className="text-muted-foreground">
                                                                {personalizada ? formatarData(atualizadoEm) : '—'}
                                                            </TableCell>
                                                            <TableCell className="text-right">
                                                                <Button
                                                                    size="sm"
                                                                    variant={personalizada ? 'outline' : 'secondary'}
                                                                    onClick={() => abrirEscola(escola)}
                                                                >
                                                                    {personalizada ? 'Editar' : 'Personalizar'}
                                                                </Button>
                                                            </TableCell>
                                                        </TableRow>
                                                    ))
                                                )}
                                            </TableBody>
                                        </Table>
                                    </div>

                                    {totalPaginas > 1 && (
                                        <div className="flex items-center justify-between text-sm text-muted-foreground">
                                            <span>{linhas.length} escola(s)</span>
                                            <div className="flex items-center gap-2">
                                                <Button
                                                    size="icon" variant="outline"
                                                    onClick={() => setPagina(paginaAtual - 1)}
                                                    disabled={paginaAtual <= 1}
                                                    aria-label="Página anterior"
                                                >
                                                    <ChevronLeft className="h-4 w-4" />
                                                </Button>
                                                <span>Página {paginaAtual} de {totalPaginas}</span>
                                                <Button
                                                    size="icon" variant="outline"
                                                    onClick={() => setPagina(paginaAtual + 1)}
                                                    disabled={paginaAtual >= totalPaginas}
                                                    aria-label="Próxima página"
                                                >
                                                    <ChevronRight className="h-4 w-4" />
                                                </Button>
                                            </div>
                                        </div>
                                    )}
                                </section>
                            </>
                        )}
                    </>
                )}
            </CardContent>

            <EditorPrompt
                alvo={alvo}
                textoGlobal={alvo?.categoria.global.texto ?? ''}
                carregando={carregandoTexto}
                textoInicial={textoInicial}
                salvando={salvando}
                onCancelar={fecharEditor}
                onSalvar={salvar}
            />
        </Card>
    );
}