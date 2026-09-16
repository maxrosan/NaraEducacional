import React, { useState, useEffect, useCallback } from 'react';
import { KeyRound, Edit, Ban, RotateCcw, Radio, Copy, Check } from 'lucide-react';
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
import { Checkbox } from "@/components/ui/checkbox";
import { apiClient } from '@/lib/apiClient';
import { apiService } from '@/services/api';

/** Lista de turmas com checkbox — a professora pode atender mais de uma. */
const TurmasCheckList = ({ turmas, selecionadas, onChange }) => {
    const alternar = (id) => {
        onChange(selecionadas.includes(id)
            ? selecionadas.filter(t => t !== id)
            : [...selecionadas, id]);
    };

    return (
        <div className="mt-1 max-h-44 overflow-y-auto rounded-md border border-gray-200 p-2 space-y-1">
            {turmas.length === 0 && (
                <p className="text-sm text-gray-500 px-1">Nenhuma turma ativa cadastrada.</p>
            )}
            {turmas.map(t => (
                <label key={t.id} className="flex items-center gap-2 px-1 py-1 rounded hover:bg-gray-50 cursor-pointer">
                    <Checkbox
                        checked={selecionadas.includes(t.id)}
                        onCheckedChange={() => alternar(t.id)}
                    />
                    <span className="text-sm">{t.nome}</span>
                </label>
            ))}
        </div>
    );
};

const formatarDataHora = (iso) => {
    if (!iso) return '—';
    try {
        return new Date(iso).toLocaleString('pt-BR', {
            day: '2-digit', month: '2-digit', year: 'numeric',
            hour: '2-digit', minute: '2-digit',
        });
    } catch {
        return iso;
    }
};

const DispositivosTab = () => {
    const [dispositivos, setDispositivos] = useState([]);
    const [professores, setProfessores] = useState([]);
    const [turmas, setTurmas] = useState([]);
    const [loading, setLoading] = useState(true);
    const [isCodigoOpen, setIsCodigoOpen] = useState(false);
    const [editando, setEditando] = useState(null);
    const [revogando, setRevogando] = useState(null);

    const fetchDispositivos = useCallback(async () => {
        setLoading(true);
        try {
            const data = await apiService.listarDispositivos();
            setDispositivos(Array.isArray(data?.dispositivos) ? data.dispositivos : []);
        } catch (err) {
            toast({ variant: "destructive", title: "Erro ao buscar dispositivos", description: err.message });
        } finally {
            setLoading(false);
        }
    }, []);

    const fetchVinculos = useCallback(async () => {
        const { data: profData, error: profError } = await apiClient
            .from('usuarios')
            .select('id, nome, perfil')
            .in('perfil', ['professor', 'professor_especialista']);
        if (profError) {
            toast({ variant: "destructive", title: "Erro ao buscar professores", description: profError.message });
        } else {
            setProfessores(Array.isArray(profData) ? profData : []);
        }

        const { data: turmaData, error: turmaError } = await apiClient
            .from('turmas')
            .select('id, nome')
            .eq('ativa', true);
        if (turmaError) {
            toast({ variant: "destructive", title: "Erro ao buscar turmas", description: turmaError.message });
        } else {
            setTurmas(Array.isArray(turmaData) ? turmaData : []);
        }
    }, []);

    useEffect(() => {
        fetchDispositivos();
        fetchVinculos();
    }, [fetchDispositivos, fetchVinculos]);

    const handleSalvarVinculo = async (formData) => {
        try {
            await apiService.atualizarDispositivo(editando.id, {
                nome: formData.nome,
                professora_id: formData.professora_id,
                turma_ids: formData.turma_ids,
            });
            toast({ title: "Dispositivo atualizado com sucesso." });
            setEditando(null);
            fetchDispositivos();
        } catch (err) {
            toast({ variant: "destructive", title: "Erro ao atualizar dispositivo", description: err.message });
        }
    };

    const handleRevogar = async () => {
        try {
            await apiService.revogarDispositivo(revogando.id);
            toast({ title: "Dispositivo revogado. O token não funciona mais." });
            setRevogando(null);
            fetchDispositivos();
        } catch (err) {
            toast({ variant: "destructive", title: "Erro ao revogar dispositivo", description: err.message });
        }
    };

    const handleReativar = async (dispositivo) => {
        try {
            await apiService.reativarDispositivo(dispositivo.id);
            toast({ title: "Dispositivo reativado.", description: "É preciso parear o aparelho novamente." });
            fetchDispositivos();
        } catch (err) {
            toast({ variant: "destructive", title: "Erro ao reativar dispositivo", description: err.message });
        }
    };

    return (
        <Card>
            <CardHeader className="flex-row items-center justify-between">
                <div>
                    <CardTitle>Dispositivos de Gravação</CardTitle>
                    <CardDescription>
                        Gravadores vinculados a uma professora e turma. O aparelho envia apenas o áudio —
                        a identidade vem deste cadastro.
                    </CardDescription>
                </div>
                <Button onClick={() => setIsCodigoOpen(true)}>
                    <KeyRound className="mr-2 h-4 w-4" /> Gerar código de pareamento
                </Button>
            </CardHeader>
            <CardContent>
                {loading ? <p>Carregando dispositivos...</p> : (
                    <TooltipProvider>
                        <Table>
                            <TableHeader>
                                <TableRow>
                                    <TableHead>Dispositivo</TableHead>
                                    <TableHead>Professora</TableHead>
                                    <TableHead>Turmas</TableHead>
                                    <TableHead>Status</TableHead>
                                    <TableHead>Último contato</TableHead>
                                    <TableHead>Áudios</TableHead>
                                    <TableHead className="text-right">Ações</TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {dispositivos.length > 0 ? dispositivos.map(d => (
                                    <TableRow key={d.id}>
                                        <TableCell className="font-medium">
                                            <div className="flex items-center gap-2">
                                                <Radio className="h-4 w-4 text-purple-500" />
                                                <div>
                                                    <div>{d.nome || 'Sem nome'}</div>
                                                    <div className="text-xs text-gray-500">{d.device_id}</div>
                                                </div>
                                            </div>
                                        </TableCell>
                                        <TableCell>{d.professora_nome || '—'}</TableCell>
                                        <TableCell>
                                            {d.turmas?.length ? (
                                                <div className="flex flex-wrap gap-1">
                                                    {d.turmas.map(t => (
                                                        <Badge
                                                            key={t.id}
                                                            variant={t.id === d.turma_ativa_id ? 'default' : 'secondary'}
                                                            title={t.id === d.turma_ativa_id ? 'Turma ativa (definida por voz)' : undefined}
                                                        >
                                                            {t.nome}
                                                        </Badge>
                                                    ))}
                                                </div>
                                            ) : '—'}
                                        </TableCell>
                                        <TableCell>
                                            <Badge variant={d.ativo ? 'default' : 'secondary'}>
                                                {d.ativo ? 'Ativo' : 'Revogado'}
                                            </Badge>
                                        </TableCell>
                                        <TableCell className="text-sm">{formatarDataHora(d.last_seen)}</TableCell>
                                        <TableCell>{d.total_audios ?? 0}</TableCell>
                                        <TableCell className="text-right space-x-2">
                                            <Tooltip>
                                                <TooltipTrigger asChild>
                                                    <Button variant="ghost" size="icon" onClick={() => setEditando(d)}>
                                                        <Edit className="h-4 w-4" />
                                                    </Button>
                                                </TooltipTrigger>
                                                <TooltipContent><p>Editar nome e vínculo</p></TooltipContent>
                                            </Tooltip>
                                            {d.ativo ? (
                                                <Tooltip>
                                                    <TooltipTrigger asChild>
                                                        <Button variant="ghost" size="icon" onClick={() => setRevogando(d)}>
                                                            <Ban className="h-4 w-4 text-red-500" />
                                                        </Button>
                                                    </TooltipTrigger>
                                                    <TooltipContent><p>Revogar acesso</p></TooltipContent>
                                                </Tooltip>
                                            ) : (
                                                <Tooltip>
                                                    <TooltipTrigger asChild>
                                                        <Button variant="ghost" size="icon" onClick={() => handleReativar(d)}>
                                                            <RotateCcw className="h-4 w-4 text-green-600" />
                                                        </Button>
                                                    </TooltipTrigger>
                                                    <TooltipContent><p>Reativar dispositivo</p></TooltipContent>
                                                </Tooltip>
                                            )}
                                        </TableCell>
                                    </TableRow>
                                )) : (
                                    <TableRow>
                                        <TableCell colSpan={7} className="text-center">
                                            Nenhum dispositivo pareado. Gere um código para vincular o primeiro gravador.
                                        </TableCell>
                                    </TableRow>
                                )}
                            </TableBody>
                        </Table>
                    </TooltipProvider>
                )}
            </CardContent>

            <CodigoPareamentoDialog
                isOpen={isCodigoOpen}
                setIsOpen={setIsCodigoOpen}
                professores={professores}
                turmas={turmas}
                onFechar={fetchDispositivos}
            />

            <DispositivoFormDialog
                dispositivo={editando}
                setDispositivo={setEditando}
                professores={professores}
                turmas={turmas}
                onSubmit={handleSalvarVinculo}
            />

            <Dialog open={!!revogando} onOpenChange={() => setRevogando(null)}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Confirmar Revogação</DialogTitle>
                        <DialogDescription>
                            Revogar "{revogando?.nome || revogando?.device_id}"? O token deixa de funcionar
                            imediatamente e o aparelho precisará ser pareado de novo. Os áudios já enviados
                            são preservados.
                        </DialogDescription>
                    </DialogHeader>
                    <DialogFooter>
                        <DialogClose asChild><Button variant="outline">Cancelar</Button></DialogClose>
                        <Button variant="destructive" onClick={handleRevogar}>Revogar</Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </Card>
    );
};

/** Modal de geração do código: escolhe professora + turma e mostra o código. */
const CodigoPareamentoDialog = ({ isOpen, setIsOpen, professores, turmas, onFechar }) => {
    const [professoraId, setProfessoraId] = useState('');
    const [turmaIds, setTurmaIds] = useState([]);
    const [codigo, setCodigo] = useState(null);
    const [gerando, setGerando] = useState(false);
    const [copiado, setCopiado] = useState(false);

    useEffect(() => {
        if (!isOpen) {
            setProfessoraId('');
            setTurmaIds([]);
            setCodigo(null);
            setCopiado(false);
        }
    }, [isOpen]);

    const handleGerar = async () => {
        if (!professoraId) {
            toast({ variant: "destructive", title: "Selecione a professora" });
            return;
        }
        setGerando(true);
        try {
            const data = await apiService.gerarCodigoPareamento({ professoraId, turmaIds });
            setCodigo(data);
        } catch (err) {
            toast({ variant: "destructive", title: "Erro ao gerar código", description: err.message });
        } finally {
            setGerando(false);
        }
    };

    const handleCopiar = async () => {
        try {
            await navigator.clipboard.writeText(codigo.codigo);
            setCopiado(true);
            setTimeout(() => setCopiado(false), 2000);
        } catch {
            toast({ variant: "destructive", title: "Não foi possível copiar" });
        }
    };

    // O dispositivo só existe no banco DEPOIS que o aparelho consome o código,
    // então a lista precisa ser recarregada ao FECHAR o modal (não ao gerar).
    const handleOpenChange = (aberto) => {
        setIsOpen(aberto);
        if (!aberto) onFechar?.();
    };

    return (
        <Dialog open={isOpen} onOpenChange={handleOpenChange}>
            <DialogContent>
                <DialogHeader>
                    <DialogTitle>Parear novo gravador</DialogTitle>
                    <DialogDescription>
                        Escolha a professora e as turmas que ela atende. O código gerado deve ser
                        digitado na tela de configuração do próprio aparelho (WiFi do gravador).
                    </DialogDescription>
                </DialogHeader>

                {!codigo ? (
                    <div className="space-y-4 pt-2">
                        <div>
                            <Label htmlFor="professora">Professora</Label>
                            <Select value={professoraId} onValueChange={setProfessoraId}>
                                <SelectTrigger id="professora"><SelectValue placeholder="Selecione a professora" /></SelectTrigger>
                                <SelectContent>
                                    {professores.map(p => (
                                        <SelectItem key={p.id} value={p.id}>{p.nome}</SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </div>
                        <div>
                            <Label>Turmas atendidas</Label>
                            <TurmasCheckList turmas={turmas} selecionadas={turmaIds} onChange={setTurmaIds} />
                            <p className="mt-1 text-xs text-gray-500">
                                Com mais de uma turma, a professora troca durante a gravação falando
                                no microfone (ex.: "estou na turma Nível 5").
                            </p>
                        </div>
                    </div>
                ) : (
                    <div className="space-y-3 pt-2 text-center">
                        <p className="text-sm text-gray-600">Digite este código no gravador:</p>
                        <div className="flex items-center justify-center gap-3">
                            <span className="text-4xl font-bold tracking-[0.3em] text-purple-700">
                                {codigo.codigo}
                            </span>
                            <Button variant="ghost" size="icon" onClick={handleCopiar} title="Copiar código">
                                {copiado ? <Check className="h-4 w-4 text-green-600" /> : <Copy className="h-4 w-4" />}
                            </Button>
                        </div>
                        <p className="text-xs text-gray-500">
                            Válido por {codigo.validade_minutos} minutos · uso único ·
                            {' '}{codigo.professora_nome}
                        </p>
                    </div>
                )}

                <DialogFooter>
                    {!codigo ? (
                        <>
                            <DialogClose asChild><Button variant="outline">Cancelar</Button></DialogClose>
                            <Button onClick={handleGerar} disabled={gerando}>
                                {gerando ? 'Gerando...' : 'Gerar código'}
                            </Button>
                        </>
                    ) : (
                        <DialogClose asChild><Button>Concluir</Button></DialogClose>
                    )}
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
};

/** Modal de edição: nome + reatribuição de professora/turma (sem tocar no aparelho). */
const DispositivoFormDialog = ({ dispositivo, setDispositivo, professores, turmas, onSubmit }) => {
    const [formData, setFormData] = useState({ nome: '', professora_id: '', turma_ids: [] });

    useEffect(() => {
        if (dispositivo) {
            setFormData({
                nome: dispositivo.nome || '',
                professora_id: dispositivo.professora_id || '',
                turma_ids: (dispositivo.turmas || []).map(t => t.id),
            });
        }
    }, [dispositivo]);

    const handleSubmit = (e) => {
        e.preventDefault();
        if (!formData.professora_id) {
            toast({ variant: "destructive", title: "Selecione a professora" });
            return;
        }
        onSubmit(formData);
    };

    return (
        <Dialog open={!!dispositivo} onOpenChange={() => setDispositivo(null)}>
            <DialogContent>
                <DialogHeader>
                    <DialogTitle>Editar dispositivo</DialogTitle>
                    <DialogDescription>
                        A troca de vínculo vale para os próximos áudios — não é preciso mexer no aparelho.
                        Os áudios já enviados mantêm a professora e a turma da época.
                    </DialogDescription>
                </DialogHeader>
                <form onSubmit={handleSubmit} className="space-y-4 pt-2">
                    <div>
                        <Label htmlFor="nome-dispositivo">Nome</Label>
                        <Input
                            id="nome-dispositivo"
                            value={formData.nome}
                            onChange={(e) => setFormData(prev => ({ ...prev, nome: e.target.value }))}
                            placeholder="Ex: Gravador Sala 5C"
                        />
                    </div>
                    <div>
                        <Label htmlFor="professora-dispositivo">Professora</Label>
                        <Select
                            value={formData.professora_id}
                            onValueChange={(v) => setFormData(prev => ({ ...prev, professora_id: v }))}
                        >
                            <SelectTrigger id="professora-dispositivo"><SelectValue placeholder="Selecione a professora" /></SelectTrigger>
                            <SelectContent>
                                {professores.map(p => (
                                    <SelectItem key={p.id} value={p.id}>{p.nome}</SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>
                    <div>
                        <Label>Turmas atendidas</Label>
                        <TurmasCheckList
                            turmas={turmas}
                            selecionadas={formData.turma_ids}
                            onChange={(ids) => setFormData(prev => ({ ...prev, turma_ids: ids }))}
                        />
                        {dispositivo?.turma_ativa_nome && (
                            <p className="mt-1 text-xs text-gray-500">
                                Turma ativa agora: <strong>{dispositivo.turma_ativa_nome}</strong> (definida por voz).
                            </p>
                        )}
                    </div>
                    <DialogFooter>
                        <DialogClose asChild><Button type="button" variant="outline">Cancelar</Button></DialogClose>
                        <Button type="submit">Salvar</Button>
                    </DialogFooter>
                </form>
            </DialogContent>
        </Dialog>
    );
};

export default DispositivosTab;
