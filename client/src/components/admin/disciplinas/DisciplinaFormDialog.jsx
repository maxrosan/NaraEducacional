import React, { useState, useEffect, useMemo } from 'react';
import { Button } from '@/components/ui/button';
import { toast } from '@/components/ui/use-toast';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogClose, DialogDescription } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

/**
 * Cria/edita disciplina. Ativar e desativar ficam nas ações da lista (abas
 * Ativas/Inativas), não aqui.
 *
 * Props:
 *   escolas               escolas ATIVAS do escopo (o backend recusa escola desativada)
 *   vinculaveis           usuários ativos com nível professor_fundamental
 *   carregandoProfessores true enquanto a lista de usuários não chegou
 *   onSubmit(dados)       async; retorna true se salvou (o diálogo é fechado pelo pai)
 */
const DisciplinaFormDialog = ({ isOpen, setIsOpen, disciplina, escolas, vinculaveis, carregandoProfessores, onSubmit }) => {
    const [formData, setFormData] = useState({ escola: '', nome: '', professores: [] });
    const [salvando, setSalvando] = useState(false);
    const vinculosAtuais = disciplina?.professores ?? [];

    useEffect(() => {
        if (!isOpen) return;
        setFormData(disciplina ? {
            escola: String(disciplina.escola ?? ''),
            nome: disciplina.nome || '',
            professores: (disciplina.professores ?? []).map((v) => String(v.usuario)),
        } : {
            escola: escolas.length === 1 ? String(escolas[0].id) : '',
            nome: '',
            professores: [],
        });
    // escolas pode chegar depois; só reinicia ao abrir ou trocar a disciplina.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [disciplina, isOpen]);

    // Opções: professores ativos da escola + quem já está vinculado (mesmo que
    // inativo), para que salvar não desfaça esse vínculo sem querer.
    const opcoesProfessores = useMemo(() => {
        const daEscola = vinculaveis
            .filter((u) => String(u.escola) === formData.escola)
            .map((u) => ({ id: String(u.id), nome: u.nome }));
        const ids = new Set(daEscola.map((u) => u.id));
        const extras = vinculosAtuais
            .filter((v) => !ids.has(String(v.usuario)))
            .map((v) => ({ id: String(v.usuario), nome: v.usuario_nome, fora: true }));
        return [...daEscola, ...extras].sort((a, b) => a.nome.localeCompare(b.nome, 'pt-BR'));
    }, [vinculaveis, vinculosAtuais, formData.escola]);

    const trocarEscola = (escola) => setFormData((prev) => ({ ...prev, escola, professores: [] }));

    const alternarProfessor = (id) => setFormData((prev) => ({
        ...prev,
        professores: prev.professores.includes(id)
            ? prev.professores.filter((p) => p !== id)
            : [...prev.professores, id],
    }));

    const handleSubmit = async (e) => {
        e.preventDefault();
        // O Select do Radix não participa da validação nativa do form.
        if (!disciplina && !formData.escola) {
            toast({ variant: "destructive", title: "Campo obrigatório", description: "Selecione a escola." });
            return;
        }
        const dados = { nome: formData.nome.trim(), professores: formData.professores };
        if (!disciplina) dados.escola = formData.escola; // na edição a escola não muda

        setSalvando(true);
        try {
            await onSubmit(dados);
        } finally {
            setSalvando(false);
        }
    };

    const escolaDaDisciplina = disciplina
        ? (escolas.find((e) => String(e.id) === formData.escola)?.nome || disciplina.escola_nome)
        : null;

    return (
        // Não fecha no meio do salvamento (Esc/clique fora).
        <Dialog open={isOpen} onOpenChange={(aberto) => { if (!salvando) setIsOpen(aberto); }}>
            <DialogContent className="max-h-[90vh] overflow-y-auto">
                <DialogHeader>
                    <DialogTitle>{disciplina ? 'Editar Disciplina' : 'Nova Disciplina'}</DialogTitle>
                    <DialogDescription>
                        Só professores do Ensino Fundamental podem ser vinculados a disciplinas.
                    </DialogDescription>
                </DialogHeader>
                <form onSubmit={handleSubmit} className="space-y-4 pt-2">
                    {disciplina ? (
                        escolas.length > 1 && (
                            <div>
                                <Label>Escola</Label>
                                <p className="mt-1 text-sm text-gray-600">{escolaDaDisciplina}</p>
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
                        <Label htmlFor="nome">Nome</Label>
                        <Input
                            id="nome"
                            value={formData.nome}
                            onChange={(e) => setFormData((prev) => ({ ...prev, nome: e.target.value }))}
                            placeholder="Ex: Matemática"
                            maxLength={100}
                            required
                        />
                    </div>
                    <div>
                        <Label>Professores</Label>
                        <div className="mt-1 max-h-44 space-y-1 overflow-y-auto rounded-md border p-2">
                            {carregandoProfessores ? (
                                <p className="px-1 py-1 text-sm text-gray-500">Carregando professores...</p>
                            ) : opcoesProfessores.length ? opcoesProfessores.map((p) => (
                                <label key={p.id} className="flex cursor-pointer items-center gap-2 rounded px-1 py-1 text-sm hover:bg-gray-50">
                                    <input type="checkbox" checked={formData.professores.includes(p.id)} onChange={() => alternarProfessor(p.id)} />
                                    <span>{p.nome}</span>
                                    {p.fora && <span className="text-xs text-gray-400">inativo ou de outra escola</span>}
                                </label>
                            )) : (
                                <p className="px-1 py-1 text-sm text-gray-500">
                                    {formData.escola
                                        ? 'Nenhum professor do Ensino Fundamental ativo nesta escola.'
                                        : 'Selecione a escola para ver os professores.'}
                                </p>
                            )}
                        </div>
                    </div>
                    <DialogFooter>
                        <DialogClose asChild><Button type="button" variant="outline" disabled={salvando}>Cancelar</Button></DialogClose>
                        <Button type="submit" disabled={salvando || carregandoProfessores}>{salvando ? 'Salvando...' : 'Salvar'}</Button>
                    </DialogFooter>
                </form>
            </DialogContent>
        </Dialog>
    );
};

export default DisciplinaFormDialog;