import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { PlusCircle, Edit, Power, RotateCcw, UserPlus } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { toast } from '@/components/ui/use-toast';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogClose, DialogDescription } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import {
    listarTurmas, listarEscolas, listarUsuarios,
    criarTurma, atualizarTurma,
    listarProfessoresTurma, vincularProfessorTurma, desvincularProfessorTurma,
} from '@/services/api';

/*
 * Cadastro de turmas (backend: /turmas/).
 *
 * No banco multi-tenant não existe cadastro de séries: etapa, faixa etária,
 * idades e ordem são campos da própria turma e são editados aqui.
 *
 * O backend já devolve só as turmas do escopo do usuário: o admin vê as de
 * todas as escolas da rede; o coordenador, só as da escola dele. Por isso não
 * há mais busca de "instituição" nem filtro por instituicao_id.
 *
 * Não existe exclusão de turma: ela é desativada (ativa=false) e pode ser
 * reativada, preservando alunos e registros vinculados.
 */

const ETAPA_LABELS = {
    educacao_infantil: 'Educação Infantil',
    ensino_fundamental: 'Ensino Fundamental',
};

const TURNO_LABELS = { manha: 'Manhã', tarde: 'Tarde', integral: 'Integral' };

// Quem pode ser vinculado a uma turma nesta tela. O front antigo também
// aceitava coordenador como responsável; mantido para não mudar a regra.
const NIVEIS_VINCULAVEIS = {
    professor_infantil: 'Prof. Educação Infantil',
    professor_fundamental: 'Prof. Ensino Fundamental',
    professor_especialista: 'Prof. Especialista',
    coordenador: 'Coordenador',
};

const TODAS = 'todas';
const anoAtual = () => new Date().getFullYear().toString();

/** `{ error }` (permissão/escopo) ou `{ campo: [mensagens] }` (validação). */
function mensagemDeErro(err) {
    const payload = err?.payload;
    if (payload && typeof payload === 'object' && !payload.error && !payload.detail) {
        const mensagens = Object.values(payload).flat().filter(Boolean);
        if (mensagens.length) return mensagens.join(' ');
    }
    return err?.message || 'Erro inesperado.';
}

function textoFaixa(turma) {
    if (turma.faixa_etaria) return turma.faixa_etaria;
    const { idade_min: min, idade_max: max } = turma;
    if (min == null && max == null) return '—';
    if (min != null && max != null) return min === max ? `${min} anos` : `${min}–${max} anos`;
    return min != null ? `a partir de ${min} anos` : `até ${max} anos`;
}

function compararTurmas(a, b) {
    return (a.escola_nome || '').localeCompare(b.escola_nome || '')
        || (a.ordem ?? 999) - (b.ordem ?? 999)
        || (a.nome || '').localeCompare(b.nome || '', 'pt-BR', { numeric: true });
}

const TurmasTab = () => {
    const navigate = useNavigate();
    const [turmas, setTurmas] = useState([]);
    const [escolas, setEscolas] = useState([]);
    const [usuarios, setUsuarios] = useState([]);
    const [vinculos, setVinculos] = useState({}); // turmaId → [{ usuario, usuario_nome, usuario_nivel }]
    const [loading, setLoading] = useState(true);
    const [filtroEscola, setFiltroEscola] = useState(TODAS);
    const [mostrarInativas, setMostrarInativas] = useState(false);
    const [isFormOpen, setIsFormOpen] = useState(false);
    const [editingTurma, setEditingTurma] = useState(null);
    const [desativandoTurma, setDesativandoTurma] = useState(null);

    const carregar = useCallback(async () => {
        setLoading(true);
        try {
            const [listaTurmas, listaEscolas, listaUsuarios] = await Promise.all([
                listarTurmas(), listarEscolas(), listarUsuarios(),
            ]);
            // Uma chamada por turma: o TurmaSerializer não traz os professores.
            let falhas = 0;
            const professores = await Promise.all(
                listaTurmas.map((t) => listarProfessoresTurma(t.id).catch(() => { falhas += 1; return []; })),
            );
            setTurmas(listaTurmas);
            setEscolas(listaEscolas);
            setUsuarios(listaUsuarios);
            setVinculos(Object.fromEntries(listaTurmas.map((t, i) => [t.id, professores[i]])));
            if (falhas) {
                toast({ variant: "destructive", title: "Professores incompletos", description: `Não foi possível carregar os professores de ${falhas} turma(s).` });
            }
        } catch (err) {
            toast({ variant: "destructive", title: "Erro ao carregar turmas", description: mensagemDeErro(err) });
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => { carregar(); }, [carregar]);

    const variasEscolas = escolas.length > 1;
    const escolasAtivas = useMemo(() => escolas.filter((e) => e.ativa !== false), [escolas]);
    const vinculaveis = useMemo(
        () => usuarios.filter((u) => u.is_active !== false && NIVEIS_VINCULAVEIS[u.nivel]),
        [usuarios],
    );

    const turmasVisiveis = useMemo(() => turmas
        .filter((t) => mostrarInativas || t.ativa !== false)
        .filter((t) => filtroEscola === TODAS || String(t.escola) === filtroEscola)
        .sort(compararTurmas), [turmas, mostrarInativas, filtroEscola]);

    const handleSalvar = async (dados, professoresSelecionados) => {
        let turma;
        try {
            turma = editingTurma
                ? await atualizarTurma(editingTurma.id, dados)
                : await criarTurma(dados);
        } catch (err) {
            toast({ variant: "destructive", title: "Erro ao salvar turma", description: mensagemDeErro(err) });
            return;
        }

        // Sincroniza os vínculos: vincula os marcados e desvincula os desmarcados.
        const atuais = new Set((vinculos[turma.id] ?? []).map((v) => String(v.usuario)));
        const desejados = new Set(professoresSelecionados.map(String));
        const falhas = [];
        for (const id of desejados) {
            if (atuais.has(id)) continue;
            try { await vincularProfessorTurma(turma.id, id); } catch (err) { falhas.push(mensagemDeErro(err)); }
        }
        for (const id of atuais) {
            if (desejados.has(id)) continue;
            try { await desvincularProfessorTurma(turma.id, id); } catch (err) { falhas.push(mensagemDeErro(err)); }
        }

        if (falhas.length) {
            toast({ variant: "destructive", title: "Turma salva, mas alguns vínculos falharam", description: falhas.join(' ') });
        } else {
            toast({ title: `Turma ${editingTurma ? 'atualizada' : 'criada'} com sucesso!` });
        }
        setIsFormOpen(false);
        setEditingTurma(null);
        carregar();
    };

    const alterarAtiva = async (turma, ativa) => {
        try {
            await atualizarTurma(turma.id, { ativa });
        } catch (err) {
            toast({ variant: "destructive", title: `Erro ao ${ativa ? 'reativar' : 'desativar'} turma`, description: mensagemDeErro(err) });
            return;
        }
        toast({ title: `Turma ${ativa ? 'reativada' : 'desativada'} com sucesso!` });
        setDesativandoTurma(null);
        carregar();
    };

    const openFormForNew = () => {
        if (!escolasAtivas.length) {
            toast({ variant: "destructive", title: "Nenhuma escola ativa", description: "Cadastre ou reative uma escola antes de criar turmas." });
            return;
        }
        setEditingTurma(null);
        setIsFormOpen(true);
    };

    const colunas = variasEscolas ? 8 : 7;

    return (
        <Card>
            <CardHeader className="flex-row items-center justify-between gap-4">
                <div>
                    <CardTitle>Gerenciamento de Turmas</CardTitle>
                    <CardDescription>
                        {variasEscolas
                            ? 'Adicione, edite ou desative as turmas das escolas da rede.'
                            : 'Adicione, edite ou desative as turmas da sua escola.'}
                    </CardDescription>
                </div>
                <Button onClick={openFormForNew}><PlusCircle className="mr-2 h-4 w-4" /> Nova Turma</Button>
            </CardHeader>
            <CardContent>
                <div className="mb-4 flex flex-wrap items-center gap-4">
                    {variasEscolas && (
                        <div className="w-64">
                            <Select value={filtroEscola} onValueChange={setFiltroEscola}>
                                <SelectTrigger aria-label="Filtrar por escola"><SelectValue /></SelectTrigger>
                                <SelectContent>
                                    <SelectItem value={TODAS}>Todas as escolas</SelectItem>
                                    {escolas.map((e) => <SelectItem key={e.id} value={String(e.id)}>{e.nome}</SelectItem>)}
                                </SelectContent>
                            </Select>
                        </div>
                    )}
                    <label className="flex items-center gap-2 text-sm text-gray-600">
                        <input type="checkbox" checked={mostrarInativas} onChange={(e) => setMostrarInativas(e.target.checked)} />
                        Mostrar turmas desativadas
                    </label>
                </div>

                {loading ? <p>Carregando turmas...</p> : (
                    <TooltipProvider>
                        <Table>
                            <TableHeader>
                                <TableRow>
                                    <TableHead>Nome</TableHead>
                                    {variasEscolas && <TableHead>Escola</TableHead>}
                                    <TableHead>Etapa</TableHead>
                                    <TableHead>Faixa Etária</TableHead>
                                    <TableHead>Turno</TableHead>
                                    <TableHead>Professores</TableHead>
                                    <TableHead>Ano Letivo</TableHead>
                                    <TableHead className="text-right">Ações</TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {turmasVisiveis.length > 0 ? turmasVisiveis.map((turma) => {
                                    const nomes = (vinculos[turma.id] ?? []).map((v) => v.usuario_nome);
                                    const inativa = turma.ativa === false;
                                    return (
                                        <TableRow key={turma.id} className={inativa ? 'opacity-60' : undefined}>
                                            <TableCell className="font-medium">
                                                {turma.nome}
                                                {inativa && <Badge variant="outline" className="ml-2">Desativada</Badge>}
                                            </TableCell>
                                            {variasEscolas && <TableCell>{turma.escola_nome}</TableCell>}
                                            <TableCell>{ETAPA_LABELS[turma.etapa] || '—'}</TableCell>
                                            <TableCell>{textoFaixa(turma)}</TableCell>
                                            <TableCell>{TURNO_LABELS[turma.turno] || turma.turno}</TableCell>
                                            <TableCell>
                                                {nomes.length
                                                    ? nomes.join(', ')
                                                    : <span className="text-amber-600">Nenhum vinculado</span>}
                                            </TableCell>
                                            <TableCell>{turma.ano_letivo}</TableCell>
                                            <TableCell className="text-right space-x-2 whitespace-nowrap">
                                                {!inativa && (
                                                    <Tooltip>
                                                        <TooltipTrigger asChild>
                                                            <Button variant="ghost" size="icon" onClick={() => navigate(`/admin/alunos?turma_id=${turma.id}`)} aria-label="Cadastrar alunos para esta turma">
                                                                <UserPlus className="h-4 w-4 text-blue-500" />
                                                            </Button>
                                                        </TooltipTrigger>
                                                        <TooltipContent><p>Cadastrar Alunos</p></TooltipContent>
                                                    </Tooltip>
                                                )}
                                                <Tooltip>
                                                    <TooltipTrigger asChild>
                                                        <Button variant="ghost" size="icon" onClick={() => { setEditingTurma(turma); setIsFormOpen(true); }} aria-label="Editar turma">
                                                            <Edit className="h-4 w-4" />
                                                        </Button>
                                                    </TooltipTrigger>
                                                    <TooltipContent><p>Editar Turma</p></TooltipContent>
                                                </Tooltip>
                                                {inativa ? (
                                                    <Tooltip>
                                                        <TooltipTrigger asChild>
                                                            <Button variant="ghost" size="icon" onClick={() => alterarAtiva(turma, true)} aria-label="Reativar turma">
                                                                <RotateCcw className="h-4 w-4 text-green-600" />
                                                            </Button>
                                                        </TooltipTrigger>
                                                        <TooltipContent><p>Reativar Turma</p></TooltipContent>
                                                    </Tooltip>
                                                ) : (
                                                    <Tooltip>
                                                        <TooltipTrigger asChild>
                                                            <Button variant="ghost" size="icon" onClick={() => setDesativandoTurma(turma)} aria-label="Desativar turma">
                                                                <Power className="h-4 w-4 text-red-500" />
                                                            </Button>
                                                        </TooltipTrigger>
                                                        <TooltipContent><p>Desativar Turma</p></TooltipContent>
                                                    </Tooltip>
                                                )}
                                            </TableCell>
                                        </TableRow>
                                    );
                                }) : (
                                    <TableRow>
                                        <TableCell colSpan={colunas} className="text-center">
                                            {turmas.length ? 'Nenhuma turma com esses filtros.' : 'Nenhuma turma cadastrada.'}
                                        </TableCell>
                                    </TableRow>
                                )}
                            </TableBody>
                        </Table>
                    </TooltipProvider>
                )}
            </CardContent>

            <TurmaFormDialog
                isOpen={isFormOpen}
                setIsOpen={setIsFormOpen}
                turma={editingTurma}
                escolas={escolasAtivas}
                vinculaveis={vinculaveis}
                vinculosAtuais={editingTurma ? (vinculos[editingTurma.id] ?? []) : []}
                onSubmit={handleSalvar}
            />

            <Dialog open={!!desativandoTurma} onOpenChange={() => setDesativandoTurma(null)}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Desativar turma</DialogTitle>
                        <DialogDescription>
                            A turma "{desativandoTurma?.nome}" deixa de aparecer entre as turmas ativas.
                            Alunos, registros e relatórios dela são mantidos, e você pode reativá-la depois
                            marcando "Mostrar turmas desativadas".
                        </DialogDescription>
                    </DialogHeader>
                    <DialogFooter>
                        <DialogClose asChild><Button variant="outline">Cancelar</Button></DialogClose>
                        <Button variant="destructive" onClick={() => alterarAtiva(desativandoTurma, false)}>Desativar</Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </Card>
    );
};

const FORM_VAZIO = {
    escola: '', nome: '', etapa: '', faixa_etaria: '', idade_min: '', idade_max: '',
    ordem: '', turno: '', ano_letivo: anoAtual(), professores: [],
};

const inteiroOuNulo = (v) => (v === '' || v == null ? null : parseInt(v, 10));

const TurmaFormDialog = ({ isOpen, setIsOpen, turma, escolas, vinculaveis, vinculosAtuais, onSubmit }) => {
    const [formData, setFormData] = useState(FORM_VAZIO);
    const [salvando, setSalvando] = useState(false);

    useEffect(() => {
        if (!isOpen) return;
        setFormData(turma ? {
            escola: String(turma.escola ?? ''),
            nome: turma.nome || '',
            etapa: turma.etapa || '',
            faixa_etaria: turma.faixa_etaria || '',
            idade_min: turma.idade_min ?? '',
            idade_max: turma.idade_max ?? '',
            ordem: turma.ordem ?? '',
            turno: turma.turno || '',
            ano_letivo: turma.ano_letivo?.toString() || anoAtual(),
            professores: vinculosAtuais.map((v) => String(v.usuario)),
        } : {
            ...FORM_VAZIO,
            ano_letivo: anoAtual(),
            escola: escolas.length === 1 ? String(escolas[0].id) : '',
        });
    // vinculosAtuais muda de referência a cada render; só reinicia ao abrir.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [turma, isOpen]);

    // Opções: professores ativos da escola da turma + quem já está vinculado
    // (mesmo que inativo), para que salvar não desfaça esse vínculo sem querer.
    const opcoesProfessores = useMemo(() => {
        const daEscola = vinculaveis
            .filter((u) => String(u.escola) === formData.escola)
            .map((u) => ({ id: String(u.id), nome: u.nome, nivel: u.nivel }));
        const ids = new Set(daEscola.map((u) => u.id));
        const extras = vinculosAtuais
            .filter((v) => !ids.has(String(v.usuario)))
            .map((v) => ({ id: String(v.usuario), nome: v.usuario_nome, nivel: v.usuario_nivel, fora: true }));
        return [...daEscola, ...extras].sort((a, b) => a.nome.localeCompare(b.nome, 'pt-BR'));
    }, [vinculaveis, vinculosAtuais, formData.escola]);

    const set = (campo, valor) => setFormData((prev) => ({ ...prev, [campo]: valor }));
    const handleChange = (e) => set(e.target.name, e.target.value);

    const alternarProfessor = (id) => setFormData((prev) => ({
        ...prev,
        professores: prev.professores.includes(id)
            ? prev.professores.filter((p) => p !== id)
            : [...prev.professores, id],
    }));

    const handleSubmit = async (e) => {
        e.preventDefault();
        // Os Selects do Radix não participam da validação nativa do form.
        const faltando = [
            !turma && !formData.escola && 'escola',
            !formData.etapa && 'etapa',
            !formData.turno && 'turno',
        ].filter(Boolean);
        if (faltando.length) {
            toast({ variant: "destructive", title: "Campos obrigatórios", description: `Selecione: ${faltando.join(', ')}.` });
            return;
        }
        const idadeMin = inteiroOuNulo(formData.idade_min);
        const idadeMax = inteiroOuNulo(formData.idade_max);
        if (idadeMin != null && idadeMax != null && idadeMin > idadeMax) {
            toast({ variant: "destructive", title: "Idades inválidas", description: "A idade máxima não pode ser menor que a mínima." });
            return;
        }

        const dados = {
            nome: formData.nome.trim(),
            etapa: formData.etapa,
            faixa_etaria: formData.faixa_etaria.trim(),
            idade_min: idadeMin,
            idade_max: idadeMax,
            ordem: inteiroOuNulo(formData.ordem),
            turno: formData.turno,
            ano_letivo: String(formData.ano_letivo).trim(),
        };
        if (!turma) dados.escola = formData.escola; // a escola da turma não muda depois de criada

        setSalvando(true);
        try {
            await onSubmit(dados, formData.professores);
        } finally {
            setSalvando(false);
        }
    };

    return (
        <Dialog open={isOpen} onOpenChange={setIsOpen}>
            <DialogContent className="max-h-[90vh] overflow-y-auto">
                <DialogHeader>
                    <DialogTitle>{turma ? 'Editar Turma' : 'Nova Turma'}</DialogTitle>
                </DialogHeader>
                <form onSubmit={handleSubmit} className="space-y-4 pt-4">
                    {(escolas.length > 1 || turma) && (
                        <div>
                            <Label htmlFor="escola">Escola</Label>
                            {turma ? (
                                <Input id="escola" value={turma.escola_nome || ''} disabled />
                            ) : (
                                <Select value={formData.escola} onValueChange={(v) => setFormData((prev) => ({ ...prev, escola: v, professores: [] }))}>
                                    <SelectTrigger id="escola"><SelectValue placeholder="Selecione a escola" /></SelectTrigger>
                                    <SelectContent>
                                        {escolas.map((e) => <SelectItem key={e.id} value={String(e.id)}>{e.nome}</SelectItem>)}
                                    </SelectContent>
                                </Select>
                            )}
                        </div>
                    )}
                    <div>
                        <Label htmlFor="nome">Nome da Turma</Label>
                        <Input id="nome" name="nome" value={formData.nome} onChange={handleChange} placeholder="Ex: Nível 3A, 1º Ano B" required />
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                        <div>
                            <Label htmlFor="etapa">Etapa de Ensino</Label>
                            <Select value={formData.etapa} onValueChange={(v) => set('etapa', v)}>
                                <SelectTrigger id="etapa"><SelectValue placeholder="Selecione a etapa" /></SelectTrigger>
                                <SelectContent>
                                    {Object.entries(ETAPA_LABELS).map(([valor, label]) => <SelectItem key={valor} value={valor}>{label}</SelectItem>)}
                                </SelectContent>
                            </Select>
                        </div>
                        <div>
                            <Label htmlFor="faixa_etaria">Faixa Etária</Label>
                            <Input id="faixa_etaria" name="faixa_etaria" value={formData.faixa_etaria} onChange={handleChange} placeholder="Ex: 3 anos" maxLength={50} />
                        </div>
                    </div>
                    <div className="grid grid-cols-3 gap-4">
                        <div>
                            <Label htmlFor="idade_min">Idade mínima</Label>
                            <Input id="idade_min" name="idade_min" type="number" min="0" max="18" value={formData.idade_min} onChange={handleChange} />
                        </div>
                        <div>
                            <Label htmlFor="idade_max">Idade máxima</Label>
                            <Input id="idade_max" name="idade_max" type="number" min="0" max="18" value={formData.idade_max} onChange={handleChange} />
                        </div>
                        <div>
                            <Label htmlFor="ordem">Ordem</Label>
                            <Input id="ordem" name="ordem" type="number" min="0" value={formData.ordem} onChange={handleChange} title="Posição da turma nas listagens" />
                        </div>
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                        <div>
                            <Label htmlFor="turno">Turno</Label>
                            <Select value={formData.turno} onValueChange={(v) => set('turno', v)}>
                                <SelectTrigger id="turno"><SelectValue placeholder="Selecione o turno" /></SelectTrigger>
                                <SelectContent>
                                    {Object.entries(TURNO_LABELS).map(([valor, label]) => <SelectItem key={valor} value={valor}>{label}</SelectItem>)}
                                </SelectContent>
                            </Select>
                        </div>
                        <div>
                            <Label htmlFor="ano_letivo">Ano Letivo</Label>
                            <Input id="ano_letivo" name="ano_letivo" type="number" min="2000" max="2100" value={formData.ano_letivo} onChange={handleChange} required />
                        </div>
                    </div>
                    <div>
                        <Label>Professores</Label>
                        <div className="mt-1 max-h-44 space-y-1 overflow-y-auto rounded-md border p-2">
                            {opcoesProfessores.length ? opcoesProfessores.map((p) => (
                                <label key={p.id} className="flex cursor-pointer items-center gap-2 rounded px-1 py-1 text-sm hover:bg-gray-50">
                                    <input type="checkbox" checked={formData.professores.includes(p.id)} onChange={() => alternarProfessor(p.id)} />
                                    <span>{p.nome}</span>
                                    <span className="text-xs text-gray-400">
                                        {NIVEIS_VINCULAVEIS[p.nivel] || p.nivel}{p.fora ? ' · inativo ou de outra escola' : ''}
                                    </span>
                                </label>
                            )) : (
                                <p className="px-1 py-1 text-sm text-gray-500">
                                    {formData.escola ? 'Nenhum professor ativo nesta escola.' : 'Selecione a escola para ver os professores.'}
                                </p>
                            )}
                        </div>
                    </div>
                    <DialogFooter>
                        <DialogClose asChild><Button type="button" variant="outline">Cancelar</Button></DialogClose>
                        <Button type="submit" disabled={salvando}>{salvando ? 'Salvando...' : 'Salvar'}</Button>
                    </DialogFooter>
                </form>
            </DialogContent>
        </Dialog>
    );
};

export default TurmasTab;