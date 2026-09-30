import React, { useState, useEffect, useMemo } from 'react';
import { RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogClose, DialogDescription } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { toast } from '@/components/ui/use-toast';
import { NIVEL_LABELS, TIPO_ESPECIALISTA_LABELS } from './UserList';

// Espelham as regras do backend (api/escopo.py e UsuarioWriteSerializer).
const NIVEIS_COM_TURMA = ['professor_infantil', 'professor_fundamental', 'professor_especialista', 'coordenador'];
const NIVEIS_COM_DISCIPLINA = ['professor_fundamental'];
const NIVEIS_COM_TIPO_ESPECIALISTA = ['especialista', 'professor_especialista'];
const NIVEIS_SEM_ESCOLA = ['admin'];

const FORM_VAZIO = {
    nome: '', email: '', password: '', nivel: '', escola: '',
    tipo_especialista: '', turmas: [], disciplinas: [],
};

/** Senha aleatória com gerador criptográfico (Math.random não é seguro para senhas). */
function gerarSenha(tamanho = 12) {
    const caracteres = 'abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789!@#$%&*';
    const valores = new Uint32Array(tamanho);
    crypto.getRandomValues(valores);
    return Array.from(valores, (v) => caracteres[v % caracteres.length]).join('');
}

/**
 * Cria/edita usuário. Ativar e desativar ficam nas ações da lista (abas
 * Ativos/Inativos), não aqui.
 *
 * Props:
 *   user                 usuário em edição (da listagem: já traz turmas/disciplinas) ou null
 *   escolas              escolas ATIVAS do escopo
 *   turmas, disciplinas  catálogos do escopo (carregados na 1ª abertura)
 *   carregandoCatalogos  true enquanto turmas/disciplinas não chegaram
 *   niveisPermitidos     níveis que QUEM ESTÁ LOGADO pode atribuir (vem do backend)
 *   usuarioAtual         id de quem está logado (autoedição só muda dados pessoais)
 *   onSubmit(dados)      async; o pai fecha o diálogo se salvar
 */
const UserFormDialog = ({
    isOpen, setIsOpen, user, escolas, turmas, disciplinas, carregandoCatalogos,
    niveisPermitidos, usuarioAtual, onSubmit,
}) => {
    const [formData, setFormData] = useState(FORM_VAZIO);
    const [salvando, setSalvando] = useState(false);
    const editandoASiMesmo = !!user && String(user.id) === String(usuarioAtual);

    useEffect(() => {
        if (!isOpen) return;
        setFormData(user ? {
            nome: user.nome || '',
            email: user.email || '',
            password: '',
            nivel: user.nivel || '',
            escola: user.escola ? String(user.escola) : '',
            tipo_especialista: user.tipo_especialista || '',
            turmas: (user.turmas ?? []).map((t) => String(t.turma)),
            disciplinas: (user.disciplinas ?? []).map((d) => String(d.disciplina)),
        } : {
            ...FORM_VAZIO,
            password: gerarSenha(),
            escola: escolas.length === 1 ? String(escolas[0].id) : '',
        });
    // escolas pode chegar depois; só reinicia ao abrir ou trocar o usuário.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [user, isOpen]);

    const precisaEscola = formData.nivel && !NIVEIS_SEM_ESCOLA.includes(formData.nivel);
    const temTurmas = NIVEIS_COM_TURMA.includes(formData.nivel);
    const temDisciplinas = NIVEIS_COM_DISCIPLINA.includes(formData.nivel);
    const temTipo = NIVEIS_COM_TIPO_ESPECIALISTA.includes(formData.nivel);

    // O perfil atual de quem está sendo editado sempre aparece, mesmo que quem
    // edita não possa atribuí-lo (só para exibição).
    const opcoesNivel = useMemo(() => {
        const lista = [...(niveisPermitidos ?? [])];
        if (user?.nivel && !lista.includes(user.nivel)) lista.push(user.nivel);
        return lista;
    }, [niveisPermitidos, user]);

    // Turmas: ativas da escola + as já vinculadas (mesmo desativadas), para
    // salvar não desfazer um vínculo sem querer.
    const turmasDaEscola = useMemo(() => {
        const vinculadas = new Set(formData.turmas);
        return turmas
            .filter((t) => String(t.escola) === formData.escola && (t.ativa !== false || vinculadas.has(String(t.id))))
            .sort((a, b) => (a.nome || '').localeCompare(b.nome || '', 'pt-BR', { numeric: true }));
    // formData.turmas fora das deps de propósito: a lista não deve "piscar" ao marcar.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [turmas, formData.escola]);

    const disciplinasDaEscola = useMemo(() => {
        const vinculadas = new Set(formData.disciplinas);
        return disciplinas
            .filter((d) => String(d.escola) === formData.escola && (d.ativo !== false || vinculadas.has(String(d.id))))
            .sort((a, b) => (a.nome || '').localeCompare(b.nome || '', 'pt-BR'));
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [disciplinas, formData.escola]);

    const set = (campo, valor) => setFormData((prev) => ({ ...prev, [campo]: valor }));
    // Trocar de escola invalida as turmas/disciplinas marcadas (são de outra escola).
    const trocarEscola = (escola) => setFormData((prev) => ({ ...prev, escola, turmas: [], disciplinas: [] }));

    const alternar = (campo, id, marcado) => setFormData((prev) => ({
        ...prev,
        [campo]: marcado ? [...prev[campo], id] : prev[campo].filter((x) => x !== id),
    }));
    const marcarTodas = (campo, lista, marcado) => set(campo, marcado ? lista.map((x) => String(x.id)) : []);

    const handleGerarSenha = () => {
        const senha = gerarSenha();
        set('password', senha);
        navigator.clipboard?.writeText(senha)
            .then(() => toast({ title: 'Senha gerada e copiada!' }))
            .catch(() => toast({ title: 'Senha gerada.', description: 'Copie-a manualmente antes de salvar.' }));
    };

    const handleSubmit = async (e) => {
        e.preventDefault();

        let dados;
        if (editandoASiMesmo) {
            // O backend ignora perfil, escola e vínculos na autoedição.
            dados = { nome: formData.nome.trim() };
        } else {
            // Os Selects do Radix não participam da validação nativa do form.
            const faltando = [
                !formData.nivel && 'perfil',
                precisaEscola && !formData.escola && 'escola',
                temTipo && !formData.tipo_especialista && 'tipo de especialista',
            ].filter(Boolean);
            if (faltando.length) {
                toast({ variant: "destructive", title: "Campos obrigatórios", description: `Selecione: ${faltando.join(', ')}.` });
                return;
            }
            dados = {
                nome: formData.nome.trim(),
                nivel: formData.nivel,
                escola: precisaEscola ? formData.escola : null,
                turmas: temTurmas ? formData.turmas : [],
                disciplinas: temDisciplinas ? formData.disciplinas : [],
            };
            if (temTipo) dados.tipo_especialista = formData.tipo_especialista;
        }
        if (!user) dados.email = formData.email.trim();
        if (formData.password) dados.password = formData.password;

        setSalvando(true);
        try {
            await onSubmit(dados);
        } finally {
            setSalvando(false);
        }
    };

    const listaDeMarcar = (campo, lista, vazio, idTodas) => (
        <div className="space-y-2 rounded-md border p-3">
            {carregandoCatalogos ? (
                <p className="text-sm text-gray-500">Carregando...</p>
            ) : !formData.escola ? (
                <p className="text-sm text-gray-500">Selecione a escola primeiro.</p>
            ) : lista.length === 0 ? (
                <p className="text-sm text-gray-500">{vazio}</p>
            ) : (
                <>
                    <div className="flex items-center space-x-2 border-b pb-2">
                        <Checkbox
                            id={idTodas}
                            checked={formData[campo].length === lista.length}
                            onCheckedChange={(v) => marcarTodas(campo, lista, !!v)}
                        />
                        <Label htmlFor={idTodas} className="font-semibold">Selecionar todas</Label>
                    </div>
                    <div className="max-h-32 space-y-1 overflow-y-auto pt-1">
                        {lista.map((item) => (
                            <div key={item.id} className="flex items-center space-x-2">
                                <Checkbox
                                    id={`${campo}-${item.id}`}
                                    checked={formData[campo].includes(String(item.id))}
                                    onCheckedChange={(v) => alternar(campo, String(item.id), !!v)}
                                />
                                <Label htmlFor={`${campo}-${item.id}`}>{item.nome}</Label>
                            </div>
                        ))}
                    </div>
                </>
            )}
        </div>
    );

    return (
        // Não fecha no meio do salvamento (Esc/clique fora).
        <Dialog open={isOpen} onOpenChange={(aberto) => { if (!salvando) setIsOpen(aberto); }}>
            <DialogContent className="max-h-[90vh] overflow-y-auto">
                <DialogHeader>
                    <DialogTitle>{user ? 'Editar Usuário' : 'Novo Usuário'}</DialogTitle>
                    {editandoASiMesmo && (
                        <DialogDescription>
                            Você está editando o próprio cadastro: perfil, escola e vínculos só podem
                            ser alterados por outro gestor.
                        </DialogDescription>
                    )}
                </DialogHeader>
                <form onSubmit={handleSubmit} className="space-y-4 pt-2">
                    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                        <div>
                            <Label htmlFor="nome">Nome</Label>
                            <Input id="nome" value={formData.nome} onChange={(e) => set('nome', e.target.value)} maxLength={200} required />
                        </div>
                        <div>
                            <Label htmlFor="email">Email</Label>
                            <Input id="email" type="email" value={formData.email} onChange={(e) => set('email', e.target.value)} required disabled={!!user} />
                        </div>
                    </div>

                    <div>
                        <Label htmlFor="password">
                            {user ? <>Nova Senha <span className="text-xs text-gray-400">(deixe em branco para não alterar)</span></> : 'Senha'}
                        </Label>
                        <div className="flex items-center gap-2">
                            <Input
                                id="password" type="text" value={formData.password}
                                onChange={(e) => set('password', e.target.value)}
                                minLength={8} required={!user}
                                placeholder={user ? 'Digite para redefinir...' : undefined}
                            />
                            <Button type="button" variant="ghost" size="icon" onClick={handleGerarSenha} title="Gerar e copiar nova senha">
                                <RefreshCw className="h-4 w-4" />
                            </Button>
                        </div>
                    </div>

                    {!editandoASiMesmo && (
                        <>
                            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                                <div>
                                    <Label htmlFor="nivel">Perfil</Label>
                                    <Select value={formData.nivel} onValueChange={(v) => set('nivel', v)}>
                                        <SelectTrigger id="nivel"><SelectValue placeholder="Selecione o perfil" /></SelectTrigger>
                                        <SelectContent>
                                            {opcoesNivel.map((n) => <SelectItem key={n} value={n}>{NIVEL_LABELS[n] || n}</SelectItem>)}
                                        </SelectContent>
                                    </Select>
                                </div>
                                {precisaEscola && escolas.length > 1 && (
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
                            </div>

                            {temTipo && (
                                <div>
                                    <Label htmlFor="tipo_especialista">Tipo de Especialista</Label>
                                    <Select value={formData.tipo_especialista} onValueChange={(v) => set('tipo_especialista', v)}>
                                        <SelectTrigger id="tipo_especialista"><SelectValue placeholder="Selecione o tipo" /></SelectTrigger>
                                        <SelectContent>
                                            {Object.entries(TIPO_ESPECIALISTA_LABELS).map(([valor, label]) => (
                                                <SelectItem key={valor} value={valor}>{label}</SelectItem>
                                            ))}
                                        </SelectContent>
                                    </Select>
                                </div>
                            )}

                            {temDisciplinas && (
                                <div>
                                    <Label>Disciplinas</Label>
                                    {listaDeMarcar('disciplinas', disciplinasDaEscola, 'Nenhuma disciplina ativa nesta escola.', 'todas-disciplinas')}
                                </div>
                            )}

                            {temTurmas && (
                                <div>
                                    <Label>Turmas Vinculadas</Label>
                                    {listaDeMarcar('turmas', turmasDaEscola, 'Nenhuma turma ativa nesta escola.', 'todas-turmas')}
                                </div>
                            )}
                        </>
                    )}

                    <DialogFooter>
                        <DialogClose asChild><Button type="button" variant="outline" disabled={salvando}>Cancelar</Button></DialogClose>
                        <Button type="submit" disabled={salvando || (carregandoCatalogos && !editandoASiMesmo)}>
                            {salvando ? 'Salvando...' : 'Salvar'}
                        </Button>
                    </DialogFooter>
                </form>
            </DialogContent>
        </Dialog>
    );
};

export default UserFormDialog;