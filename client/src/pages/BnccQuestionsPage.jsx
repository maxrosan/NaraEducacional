import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Helmet } from 'react-helmet-async';
import { useToast } from '@/components/ui/use-toast';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogFooter, DialogClose } from '@/components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';
import {
  Loader2, PlusCircle, Edit, Power, RotateCcw, FileDown, ArrowLeft, Settings,
  AlertTriangle, ChevronLeft, ChevronRight,
} from 'lucide-react';
import IconPicker from '@/components/ui/icon-picker';
import {
  listarPerguntasBnccGestao, criarPerguntaBncc, atualizarPerguntaBncc,
  listarCamposPedagogicos, criarCampoPedagogico, atualizarCampoPedagogico, desativarCampoPedagogico,
  listarEscolas, listarTurmas,
} from '@/services/api';
import { NIVEIS_BASE, iconeDoCampo, montarNiveis, mensagemDeErro } from '@/lib/perguntasUtils';

/*
 * Gestão das perguntas BNCC (backend: /perguntas/?page=).
 *
 * Perguntas OFICIAIS (sem escola) valem para todas as escolas e só o
 * superadmin cria/edita; o admin vê e usa, e cria as perguntas da(s)
 * escola(s) dele. A resposta paginada diz se quem está logado pode editar
 * oficiais (`pode_editar_oficiais`).
 *
 * Toda pergunta tem Referência BNCC: o código (ex.: EI03EO01) é localizado no
 * catálogo pelo backend; código inexistente volta como erro no formulário.
 *
 * Não há exclusão:
 *   - pergunta: os registros de observação apontam para ela, então é
 *     desativada (aba Inativas) e pode ser reativada;
 *   - campo de experiência: é desativado no "Gerenciar Campos"; se tiver
 *     perguntas, elas são remanejadas antes para outro campo.
 *
 * `embutida`: renderiza só o conteúdo, como aba do painel do admin
 * (/admin/bncc). Sem ela, é a página avulsa antiga (/admin/perguntas-bncc).
 */

const TODOS = 'todos';
const OFICIAL = 'oficial';
const POR_PAGINA = 10;
const BUSCA_DEBOUNCE_MS = 400;
const LISTA_VAZIA = {
  results: [], count: 0, total_paginas: 1, totais: { ativas: 0, inativas: 0 }, pode_editar_oficiais: false,
};

const campoValidoPara = (campo, escolaId) => !campo.escola || String(campo.escola) === escolaId;

const BnccQuestionsPage = ({ embutida = false }) => {
  const navigate = useNavigate();
  const { toast } = useToast();
  const avisarErro = useCallback(
    (titulo, err) => toast({ variant: 'destructive', title: titulo, description: mensagemDeErro(err) }),
    [toast],
  );

  const [aba, setAba] = useState('true'); // ativa=true|false
  const [pagina, setPagina] = useState(1);
  const [filtroOrigem, setFiltroOrigem] = useState(TODOS);
  const [filtroEscola, setFiltroEscola] = useState(TODOS);
  const [filtroCampo, setFiltroCampo] = useState(TODOS);
  const [filtroNivel, setFiltroNivel] = useState(TODOS);
  const [busca, setBusca] = useState('');
  const [buscaAplicada, setBuscaAplicada] = useState('');
  const [lista, setLista] = useState(LISTA_VAZIA);
  const [loading, setLoading] = useState(true);
  const [carregouUmaVez, setCarregouUmaVez] = useState(false);
  const [exportando, setExportando] = useState(false);

  const [escolas, setEscolas] = useState([]);
  const [campos, setCampos] = useState([]);
  const [niveis, setNiveis] = useState(NIVEIS_BASE);

  const [isFormOpen, setIsFormOpen] = useState(false);
  const [editando, setEditando] = useState(null);
  const [desativando, setDesativando] = useState(null);
  const [isCampoManagerOpen, setIsCampoManagerOpen] = useState(false);
  const ultimaRequisicao = useRef(0);

  // Só consulta o backend quando o usuário para de digitar.
  useEffect(() => {
    const termo = busca.trim();
    if (termo === buscaAplicada) return undefined;
    const id = setTimeout(() => { setBuscaAplicada(termo); setPagina(1); }, BUSCA_DEBOUNCE_MS);
    return () => clearTimeout(id);
  }, [busca, buscaAplicada]);

  const filtrosAtuais = useCallback(() => ({
    ativa: aba,
    origem: filtroOrigem === TODOS ? undefined : filtroOrigem,
    escola: filtroEscola === TODOS ? undefined : filtroEscola,
    campo: filtroCampo === TODOS ? undefined : filtroCampo,
    faixa_etaria: filtroNivel === TODOS ? undefined : filtroNivel,
    busca: buscaAplicada || undefined,
  }), [aba, filtroOrigem, filtroEscola, filtroCampo, filtroNivel, buscaAplicada]);

  const carregar = useCallback(async () => {
    const id = ++ultimaRequisicao.current;
    setLoading(true);
    try {
      const dados = await listarPerguntasBnccGestao({ ...filtrosAtuais(), page: pagina, pageSize: POR_PAGINA });
      if (id !== ultimaRequisicao.current) return; // resposta atrasada
      setLista(dados);
      if (dados.pagina && dados.pagina !== pagina) setPagina(dados.pagina);
    } catch (err) {
      if (id === ultimaRequisicao.current) avisarErro('Erro ao buscar perguntas', err);
    } finally {
      if (id === ultimaRequisicao.current) { setLoading(false); setCarregouUmaVez(true); }
    }
  }, [filtrosAtuais, pagina, avisarErro]);

  useEffect(() => { carregar(); }, [carregar]);

  const carregarCampos = useCallback(() => (
    listarCamposPedagogicos({ comUso: true })
      .then((c) => setCampos(c || []))
      .catch((err) => avisarErro('Erro ao carregar campos de experiência', err))
  ), [avisarErro]);

  // Dados de apoio: uma vez, em paralelo.
  useEffect(() => {
    listarEscolas().then(setEscolas).catch((err) => avisarErro('Erro ao carregar escolas', err));
    carregarCampos();
    listarTurmas()
      .then((t) => setNiveis(montarNiveis((t || []).filter((x) => x.ativa !== false))))
      .catch(() => setNiveis(NIVEIS_BASE));
  }, [avisarErro, carregarCampos]);

  const podeEditarOficiais = !!lista.pode_editar_oficiais;
  const variasEscolas = escolas.length > 1;
  const escolasAtivas = useMemo(() => escolas.filter((e) => e.ativa !== false), [escolas]);
  const camposAtivos = useMemo(() => campos.filter((c) => c.ativo !== false), [campos]);

  const trocar = (setter) => (valor) => { setter(valor); setPagina(1); };

  const abrirFormulario = (pergunta) => { setEditando(pergunta); setIsFormOpen(true); };

  const handleSalvar = async (dados) => {
    const editandoAgora = !!editando;
    try {
      if (editandoAgora) await atualizarPerguntaBncc(editando.id, dados);
      else await criarPerguntaBncc(dados);
    } catch (err) {
      avisarErro('Erro ao salvar pergunta', err);
      return;
    }
    toast({ title: `Pergunta ${editandoAgora ? 'atualizada' : 'criada'} com sucesso!` });
    setIsFormOpen(false);
    setEditando(null);
    carregarCampos(); // contagem de uso dos campos
    if (!editandoAgora && (aba !== 'true' || pagina !== 1)) { setAba('true'); setPagina(1); } else carregar();
  };

  const alterarAtiva = async (pergunta, ativa) => {
    try {
      await atualizarPerguntaBncc(pergunta.id, { ativa });
    } catch (err) {
      avisarErro(`Erro ao ${ativa ? 'reativar' : 'desativar'} pergunta`, err);
      return;
    }
    toast({ title: `Pergunta ${ativa ? 'reativada' : 'desativada'} com sucesso!` });
    setDesativando(null);
    carregar();
  };

  // Exporta TODAS as perguntas com os filtros atuais (não só a página).
  const handleExportCSV = async () => {
    setExportando(true);
    try {
      const perguntas = await listarPerguntasBnccGestao(filtrosAtuais());
      if (!perguntas.length) {
        toast({ title: 'Nenhuma pergunta para exportar', description: 'Altere os filtros para selecionar perguntas.', variant: 'destructive' });
        return;
      }
      const colunas = [
        ['faixa_etaria', (p) => p.faixa_etaria],
        ['campo_experiencia', (p) => p.campo_experiencia_nome],
        ['area_conhecimento', (p) => p.area_conhecimento],
        ['pergunta', (p) => p.pergunta],
        ['pergunta_norma', (p) => p.pergunta_norma],
        ['habilidade_bncc', (p) => p.habilidade_bncc_codigo],
        ['origem', (p) => (p.escola ? p.escola_nome : 'Oficial')],
        ['ativa', (p) => (p.ativa ? 'sim' : 'não')],
      ];
      const celula = (v) => `"${String(v ?? '').replace(/"/g, '""')}"`;
      const csv = [colunas.map(([nome]) => nome).join(','),
        ...perguntas.map((p) => colunas.map(([, valor]) => celula(valor(p))).join(','))].join('\n');
      // BOM: o Excel abre o CSV com os acentos certos.
      const url = URL.createObjectURL(new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8;' }));
      const link = document.createElement('a');
      link.href = url;
      link.download = 'perguntas_bncc.csv';
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
      toast({ title: 'Exportação concluída!', description: `${perguntas.length} perguntas exportadas.` });
    } catch (err) {
      avisarErro('Erro ao exportar', err);
    } finally {
      setExportando(false);
    }
  };

  const { results: perguntas, count, total_paginas: totalPaginas, totais } = lista;
  const primeira = count ? (pagina - 1) * POR_PAGINA + 1 : 0;
  const ultima = Math.min(pagina * POR_PAGINA, count);
  let mensagemVazia = aba === 'true' ? 'Nenhuma pergunta ativa.' : 'Nenhuma pergunta inativa.';
  if (buscaAplicada) mensagemVazia = `Nenhuma pergunta encontrada para "${buscaAplicada}".`;

  const acao = (rotulo, onClick, icone) => (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button variant="ghost" size="icon" onClick={onClick} aria-label={rotulo}>{icone}</Button>
      </TooltipTrigger>
      <TooltipContent><p>{rotulo}</p></TooltipContent>
    </Tooltip>
  );

  const acoesCabecalho = (
    <div className="flex flex-wrap items-center gap-2">
      <Button variant="outline" onClick={() => setIsCampoManagerOpen(true)}>
        <Settings className="mr-2 h-4 w-4" /> Gerenciar Campos
      </Button>
      <Button variant="outline" onClick={handleExportCSV} disabled={exportando}>
        {exportando ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <FileDown className="mr-2 h-4 w-4" />}
        Exportar CSV
      </Button>
      <Button onClick={() => abrirFormulario(null)}><PlusCircle className="mr-2 h-4 w-4" /> Nova Pergunta</Button>
    </div>
  );

  const cartaoPerguntas = (
    <Card>
      <CardHeader>
        <CardTitle>Perguntas da BNCC</CardTitle>
        <CardDescription>
          Perguntas oficiais valem para todas as escolas{podeEditarOficiais ? '' : ' e só podem ser alteradas pelo suporte NARA'}.
          Cada escola pode ter perguntas próprias.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="mb-4 flex flex-wrap items-center justify-between gap-4">
          <Tabs value={aba} onValueChange={trocar(setAba)}>
            <TabsList>
              <TabsTrigger value="true">Ativas <Badge variant="secondary" className="ml-2">{totais.ativas}</Badge></TabsTrigger>
              <TabsTrigger value="false">Inativas <Badge variant="secondary" className="ml-2">{totais.inativas}</Badge></TabsTrigger>
            </TabsList>
          </Tabs>
          <Input
            className="w-64" placeholder="Buscar por texto ou código BNCC..."
            aria-label="Buscar pergunta por texto ou código BNCC"
            value={busca} onChange={(e) => setBusca(e.target.value)}
          />
        </div>
        <div className={`mb-4 grid grid-cols-1 gap-2 ${variasEscolas ? 'md:grid-cols-4' : 'md:grid-cols-3'}`}>
          <Select value={filtroOrigem} onValueChange={trocar(setFiltroOrigem)}>
            <SelectTrigger aria-label="Filtrar por origem"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value={TODOS}>Oficiais e das escolas</SelectItem>
              <SelectItem value="oficial">Só oficiais</SelectItem>
              <SelectItem value="escola">Só das escolas</SelectItem>
            </SelectContent>
          </Select>
          {variasEscolas && (
            <Select value={filtroEscola} onValueChange={trocar(setFiltroEscola)}>
              <SelectTrigger aria-label="Filtrar por escola"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value={TODOS}>Todas as escolas</SelectItem>
                {escolas.map((e) => <SelectItem key={e.id} value={String(e.id)}>{e.nome}</SelectItem>)}
              </SelectContent>
            </Select>
          )}
          <Select value={filtroCampo} onValueChange={trocar(setFiltroCampo)}>
            <SelectTrigger aria-label="Filtrar por campo de experiência"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value={TODOS}>Todos os campos</SelectItem>
              {campos.map((c) => (
                <SelectItem key={c.id} value={String(c.id)}>{c.nome}{c.ativo === false ? ' (desativado)' : ''}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select value={filtroNivel} onValueChange={trocar(setFiltroNivel)}>
            <SelectTrigger aria-label="Filtrar por nível"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value={TODOS}>Todos os níveis</SelectItem>
              {niveis.map((n) => <SelectItem key={n} value={n}>{n}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>

        {!carregouUmaVez ? (
          <div className="flex h-40 items-center justify-center"><Loader2 className="h-8 w-8 animate-spin text-purple-500" /></div>
        ) : (
          <TooltipProvider>
            {/* Mantém a tabela na tela ao trocar de página/aba, só esmaecida. */}
            <div className={`overflow-x-auto ${loading ? 'pointer-events-none opacity-50 transition-opacity' : 'transition-opacity'}`} aria-busy={loading}>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Pergunta Facilitadora</TableHead>
                    <TableHead>Campo de Experiência</TableHead>
                    <TableHead>Nível</TableHead>
                    <TableHead>Referência (BNCC)</TableHead>
                    <TableHead>Origem</TableHead>
                    <TableHead className="text-right">Ações</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {perguntas.length > 0 ? perguntas.map((p) => {
                    const Icone = iconeDoCampo(p.campo_experiencia_nome, p.campo_experiencia_icone);
                    const oficial = !p.escola;
                    const editavel = !oficial || podeEditarOficiais;
                    return (
                      <TableRow key={p.id}>
                        <TableCell className="max-w-md">
                          <p className="font-medium">{p.pergunta}</p>
                          {p.area_conhecimento && <p className="text-xs text-gray-500">{p.area_conhecimento}</p>}
                        </TableCell>
                        <TableCell>
                          {p.campo_experiencia_nome ? (
                            <span className="flex items-center gap-2">
                              <Icone className="h-4 w-4 shrink-0 text-purple-600" />{p.campo_experiencia_nome}
                            </span>
                          ) : '—'}
                        </TableCell>
                        <TableCell className="whitespace-nowrap">{p.faixa_etaria || '—'}</TableCell>
                        <TableCell>
                          {p.habilidade_bncc_codigo ? (
                            <Tooltip>
                              <TooltipTrigger asChild>
                                <span className="cursor-help font-mono text-sm underline decoration-dotted">{p.habilidade_bncc_codigo}</span>
                              </TooltipTrigger>
                              <TooltipContent className="max-w-sm">
                                <p>{p.habilidade_bncc_descricao}</p>
                                {p.pergunta_norma && <p className="mt-2 text-xs opacity-80">{p.pergunta_norma}</p>}
                              </TooltipContent>
                            </Tooltip>
                          ) : <span className="text-amber-600">Sem referência</span>}
                        </TableCell>
                        <TableCell>{oficial ? <Badge variant="outline">Oficial</Badge> : p.escola_nome}</TableCell>
                        <TableCell className="space-x-2 whitespace-nowrap text-right">
                          {editavel ? (
                            <>
                              {acao('Editar pergunta', () => abrirFormulario(p), <Edit className="h-4 w-4" />)}
                              {p.ativa
                                ? acao('Desativar pergunta', () => setDesativando(p), <Power className="h-4 w-4 text-red-500" />)
                                : acao('Reativar pergunta', () => alterarAtiva(p, true), <RotateCcw className="h-4 w-4 text-green-600" />)}
                            </>
                          ) : <span className="text-xs text-gray-400">Somente leitura</span>}
                        </TableCell>
                      </TableRow>
                    );
                  }) : (
                    <TableRow><TableCell colSpan={6} className="text-center text-gray-500">{mensagemVazia}</TableCell></TableRow>
                  )}
                </TableBody>
              </Table>
            </div>

            {totalPaginas > 1 && (
              <div className="mt-4 flex flex-wrap items-center justify-between gap-2 text-sm text-gray-600">
                <span>Mostrando {primeira}–{ultima} de {count} perguntas</span>
                <div className="flex items-center gap-2">
                  <Button variant="outline" size="sm" disabled={loading || pagina <= 1} onClick={() => setPagina((n) => n - 1)}>
                    <ChevronLeft className="mr-1 h-4 w-4" /> Anterior
                  </Button>
                  <span className="px-2">Página {pagina} de {totalPaginas}</span>
                  <Button variant="outline" size="sm" disabled={loading || pagina >= totalPaginas} onClick={() => setPagina((n) => n + 1)}>
                    Próxima <ChevronRight className="ml-1 h-4 w-4" />
                  </Button>
                </div>
              </div>
            )}
          </TooltipProvider>
        )}
      </CardContent>
    </Card>
  );

  const dialogos = (
    <>
      <PerguntaBnccForm
        isOpen={isFormOpen}
        setIsOpen={setIsFormOpen}
        pergunta={editando}
        escolas={escolasAtivas}
        campos={camposAtivos}
        niveis={niveis}
        podeCriarOficial={podeEditarOficiais}
        onSubmit={handleSalvar}
      />

      <Dialog open={!!desativando} onOpenChange={() => setDesativando(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Desativar pergunta</DialogTitle>
            <DialogDescription>
              A pergunta deixa de aparecer na aba Ativas. As observações já registradas com ela são
              mantidas, e você pode reativá-la depois pela aba Inativas.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <DialogClose asChild><Button variant="outline">Cancelar</Button></DialogClose>
            <Button variant="destructive" onClick={() => alterarAtiva(desativando, false)}>Desativar</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <GerenciadorCampos
        isOpen={isCampoManagerOpen}
        setIsOpen={setIsCampoManagerOpen}
        campos={campos}
        escolas={escolasAtivas}
        podeEditarOficiais={podeEditarOficiais}
        onAlterado={() => { carregarCampos(); carregar(); }}
      />
    </>
  );

  if (embutida) {
    return (
      <div className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h3 className="text-xl font-bold text-gray-800">Gestão de Perguntas BNCC</h3>
            <p className="text-sm text-gray-500">Administre as perguntas pedagógicas por Campo de Experiência</p>
          </div>
          {acoesCabecalho}
        </div>
        {cartaoPerguntas}
        {dialogos}
      </div>
    );
  }

  return (
    <>
      <Helmet>
        <title>NARA - Gestão de Perguntas BNCC</title>
        <meta name="description" content="Gerencie as perguntas pedagógicas baseadas na BNCC." />
      </Helmet>
      <div className="min-h-screen bg-[#F5F3FA]">
        <header className="sticky top-0 z-10 bg-white/80 shadow-sm backdrop-blur-sm">
          <div className="container mx-auto flex flex-wrap items-center justify-between gap-4 px-4 py-4 sm:px-6 lg:px-8">
            <div className="flex items-center gap-4">
              <Button variant="ghost" size="icon" onClick={() => navigate('/admin/dashboard')} aria-label="Voltar ao painel">
                <ArrowLeft className="h-6 w-6" />
              </Button>
              <div>
                <h1 className="text-xl font-bold text-gray-800">Gestão de Perguntas BNCC</h1>
                <p className="text-sm text-gray-500">Administre as perguntas pedagógicas por Campo de Experiência</p>
              </div>
            </div>
            {acoesCabecalho}
          </div>
        </header>
        <main className="container mx-auto px-4 py-8 sm:px-6 lg:px-8">{cartaoPerguntas}</main>
      </div>
      {dialogos}
    </>
  );
};

// ─── Formulário de pergunta ───────────────────────────────────────────────────

const FORM_VAZIO = {
  escola: '', campo_experiencia: '', faixa_etaria: '', pergunta: '',
  referencia_bncc: '', pergunta_norma: '', area_conhecimento: '',
};

const textareaClasses = 'flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2';

const PerguntaBnccForm = ({ isOpen, setIsOpen, pergunta, escolas, campos, niveis, podeCriarOficial, onSubmit }) => {
  const { toast } = useToast();
  const [formData, setFormData] = useState(FORM_VAZIO);
  const [salvando, setSalvando] = useState(false);

  useEffect(() => {
    if (!isOpen) return;
    setFormData(pergunta ? {
      escola: pergunta.escola ? String(pergunta.escola) : OFICIAL,
      campo_experiencia: pergunta.campo_experiencia ? String(pergunta.campo_experiencia) : '',
      faixa_etaria: pergunta.faixa_etaria || '',
      pergunta: pergunta.pergunta || '',
      referencia_bncc: pergunta.habilidade_bncc_codigo || '',
      pergunta_norma: pergunta.pergunta_norma || '',
      area_conhecimento: pergunta.area_conhecimento || '',
    } : { ...FORM_VAZIO, escola: !podeCriarOficial && escolas.length === 1 ? String(escolas[0].id) : '' });
  // escolas pode chegar depois; só reinicia ao abrir ou trocar a pergunta.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pergunta, isOpen]);

  const set = (campo, valor) => setFormData((prev) => ({ ...prev, [campo]: valor }));
  const escolaDaPergunta = formData.escola === OFICIAL ? null : formData.escola;

  // Oficial → só campos oficiais; da escola → oficiais + os da escola.
  // O campo atual sempre aparece (mesmo se desativado depois).
  const opcoesCampo = useMemo(() => {
    const lista = campos.filter((c) => (escolaDaPergunta ? campoValidoPara(c, escolaDaPergunta) : !c.escola));
    if (pergunta?.campo_experiencia && !lista.some((c) => String(c.id) === String(pergunta.campo_experiencia))) {
      lista.push({ id: pergunta.campo_experiencia, nome: `${pergunta.campo_experiencia_nome} (desativado)`, icone: pergunta.campo_experiencia_icone });
    }
    return lista.sort((a, b) => a.nome.localeCompare(b.nome, 'pt-BR'));
  }, [campos, escolaDaPergunta, pergunta]);

  const trocarEscola = (escola) => setFormData((prev) => {
    const campo = campos.find((c) => String(c.id) === prev.campo_experiencia);
    const novaEscola = escola === OFICIAL ? null : escola;
    const aindaVale = !campo || (novaEscola ? campoValidoPara(campo, novaEscola) : !campo.escola);
    return { ...prev, escola, campo_experiencia: aindaVale ? prev.campo_experiencia : '' };
  });

  const handleSubmit = async (e) => {
    e.preventDefault();
    // Os Selects do Radix não participam da validação nativa do form.
    const faltando = [
      !pergunta && !formData.escola && 'escola',
      !formData.campo_experiencia && 'campo de experiência',
      !formData.faixa_etaria && 'nível',
    ].filter(Boolean);
    if (faltando.length) {
      toast({ variant: 'destructive', title: 'Campos obrigatórios', description: `Selecione: ${faltando.join(', ')}.` });
      return;
    }
    const dados = {
      campo_experiencia: formData.campo_experiencia,
      faixa_etaria: formData.faixa_etaria,
      pergunta: formData.pergunta.trim(),
      referencia_bncc: formData.referencia_bncc.trim().toUpperCase(),
      pergunta_norma: formData.pergunta_norma.trim(),
      area_conhecimento: formData.area_conhecimento.trim(),
    };
    // Na edição a escola não muda. Oficial = sem escola (só superadmin).
    if (!pergunta && formData.escola !== OFICIAL) dados.escola = formData.escola;

    setSalvando(true);
    try {
      await onSubmit(dados);
    } finally {
      setSalvando(false);
    }
  };

  const mostrarEscola = !pergunta && (podeCriarOficial || escolas.length > 1);
  const rotuloOrigem = pergunta ? (pergunta.escola ? pergunta.escola_nome : 'Oficial (todas as escolas)') : null;

  return (
    // Não fecha no meio do salvamento (Esc/clique fora).
    <Dialog open={isOpen} onOpenChange={(aberto) => { if (!salvando) setIsOpen(aberto); }}>
      <DialogContent className="max-h-[90vh] max-w-2xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            {pergunta ? <Edit className="h-5 w-5 text-purple-600" /> : <PlusCircle className="h-5 w-5 text-purple-600" />}
            {pergunta ? 'Editar' : 'Nova'} Pergunta BNCC
          </DialogTitle>
          {rotuloOrigem && <DialogDescription>Origem: {rotuloOrigem}</DialogDescription>}
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4 pt-2">
          {mostrarEscola && (
            <div>
              <Label htmlFor="bncc-escola">Escola</Label>
              <Select value={formData.escola} onValueChange={trocarEscola}>
                <SelectTrigger id="bncc-escola"><SelectValue placeholder="Selecione a escola" /></SelectTrigger>
                <SelectContent>
                  {podeCriarOficial && <SelectItem value={OFICIAL}>Oficial (todas as escolas)</SelectItem>}
                  {escolas.map((e) => <SelectItem key={e.id} value={String(e.id)}>{e.nome}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
          )}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <Label htmlFor="bncc-campo">Campo de Experiência</Label>
              <Select value={formData.campo_experiencia} onValueChange={(v) => set('campo_experiencia', v)}>
                <SelectTrigger id="bncc-campo"><SelectValue placeholder="Selecione o campo" /></SelectTrigger>
                <SelectContent>
                  {opcoesCampo.map((c) => {
                    const Icone = iconeDoCampo(c.nome, c.icone);
                    return (
                      <SelectItem key={c.id} value={String(c.id)}>
                        <span className="flex items-center gap-2"><Icone className="h-4 w-4 text-purple-600" />{c.nome}</span>
                      </SelectItem>
                    );
                  })}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label htmlFor="bncc-nivel">Nível/Faixa Etária</Label>
              <Select value={formData.faixa_etaria} onValueChange={(v) => set('faixa_etaria', v)}>
                <SelectTrigger id="bncc-nivel"><SelectValue placeholder="Selecione o nível" /></SelectTrigger>
                <SelectContent>
                  {[...new Set([...niveis, formData.faixa_etaria].filter(Boolean))].map((n) => (
                    <SelectItem key={n} value={n}>{n}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <div>
            <Label htmlFor="bncc-pergunta">Pergunta Facilitadora</Label>
            <textarea
              id="bncc-pergunta" rows={3} required className={textareaClasses}
              value={formData.pergunta} onChange={(e) => set('pergunta', e.target.value)}
              placeholder="Digite a pergunta facilitadora para observação pedagógica"
            />
          </div>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <Label htmlFor="bncc-referencia">Referência (BNCC)</Label>
              <Input
                id="bncc-referencia" required maxLength={20} className="font-mono uppercase"
                value={formData.referencia_bncc} onChange={(e) => set('referencia_bncc', e.target.value)}
                placeholder="Ex: EI03EO01"
              />
              {pergunta?.habilidade_bncc_descricao && formData.referencia_bncc.trim().toUpperCase() === pergunta.habilidade_bncc_codigo && (
                <p className="mt-1 text-xs text-gray-500">{pergunta.habilidade_bncc_descricao}</p>
              )}
            </div>
            <div>
              <Label htmlFor="bncc-area">Área do Conhecimento <span className="text-xs text-gray-400">(opcional)</span></Label>
              <Input
                id="bncc-area" maxLength={200}
                value={formData.area_conhecimento} onChange={(e) => set('area_conhecimento', e.target.value)}
                placeholder="Ex: Linguagens, Matemática..."
              />
            </div>
          </div>
          <div>
            <Label htmlFor="bncc-norma">Texto da Norma BNCC <span className="text-xs text-gray-400">(opcional)</span></Label>
            <textarea
              id="bncc-norma" rows={2} className={textareaClasses}
              value={formData.pergunta_norma} onChange={(e) => set('pergunta_norma', e.target.value)}
              placeholder="Texto original da norma BNCC"
            />
          </div>
          <DialogFooter>
            <DialogClose asChild><Button type="button" variant="ghost" disabled={salvando}>Cancelar</Button></DialogClose>
            <Button type="submit" disabled={salvando}>
              {salvando && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Salvar Pergunta
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
};

// ─── Gerenciador de campos de experiência ─────────────────────────────────────

const CAMPO_VAZIO = { nome: '', icone: 'BookOpen', escola: '' };

const GerenciadorCampos = ({ isOpen, setIsOpen, campos, escolas, podeEditarOficiais, onAlterado }) => {
  const { toast } = useToast();
  const avisarErro = (titulo, err) => toast({ variant: 'destructive', title: titulo, description: mensagemDeErro(err) });

  const [formCampo, setFormCampo] = useState(null);      // { ...CAMPO_VAZIO, id? } aberto para criar/editar
  const [salvandoCampo, setSalvandoCampo] = useState(false);
  const [desativando, setDesativando] = useState(null);  // campo sendo desativado
  const [destino, setDestino] = useState('');
  const [processando, setProcessando] = useState(false);

  const editavel = (c) => !!c.escola || podeEditarOficiais;
  const ordenados = useMemo(
    () => [...campos].sort((a, b) => (a.ativo === b.ativo ? a.nome.localeCompare(b.nome, 'pt-BR') : a.ativo ? -1 : 1)),
    [campos],
  );

  // Destinos válidos: ativos, diferentes do campo; origem oficial → só oficiais
  // (as perguntas são de várias escolas); origem da escola → oficiais + da mesma escola.
  const destinos = useMemo(() => {
    if (!desativando) return [];
    return campos.filter((c) => c.ativo !== false && c.id !== desativando.id
      && (desativando.escola ? campoValidoPara(c, String(desativando.escola)) : !c.escola));
  }, [campos, desativando]);

  const abrirNovo = () => setFormCampo({
    ...CAMPO_VAZIO, escola: escolas.length === 1 && !podeEditarOficiais ? String(escolas[0].id) : '',
  });

  const salvarCampo = async () => {
    const nome = formCampo.nome.trim();
    if (!nome) return;
    if (!formCampo.id && !formCampo.escola) {
      toast({ variant: 'destructive', title: 'Selecione a escola do campo.' });
      return;
    }
    setSalvandoCampo(true);
    try {
      if (formCampo.id) {
        await atualizarCampoPedagogico(formCampo.id, { nome, icone: formCampo.icone });
      } else {
        const dados = { nome, icone: formCampo.icone };
        if (formCampo.escola !== OFICIAL) dados.escola = formCampo.escola;
        await criarCampoPedagogico(dados);
      }
      toast({ title: `Campo ${formCampo.id ? 'atualizado' : 'criado'} com sucesso!` });
      setFormCampo(null);
      onAlterado();
    } catch (err) {
      avisarErro('Erro ao salvar campo', err);
    } finally {
      setSalvandoCampo(false);
    }
  };

  const confirmarDesativacao = async () => {
    const total = desativando.total_perguntas || 0;
    if (total > 0 && !destino) {
      toast({ variant: 'destructive', title: 'Remanejamento necessário', description: 'Escolha o campo que vai receber as perguntas.' });
      return;
    }
    setProcessando(true);
    try {
      const r = await desativarCampoPedagogico(desativando.id, destino || null);
      toast({
        title: 'Campo desativado',
        description: r.perguntas_remanejadas ? `${r.perguntas_remanejadas} pergunta(s) remanejada(s).` : undefined,
      });
      setDesativando(null);
      setDestino('');
      onAlterado();
    } catch (err) {
      avisarErro('Erro ao desativar campo', err);
    } finally {
      setProcessando(false);
    }
  };

  const reativar = async (campo) => {
    try {
      await atualizarCampoPedagogico(campo.id, { ativo: true });
      toast({ title: 'Campo reativado!' });
      onAlterado();
    } catch (err) {
      avisarErro('Erro ao reativar campo', err);
    }
  };

  return (
    <>
      <Dialog open={isOpen} onOpenChange={setIsOpen}>
        <DialogContent className="max-h-[90vh] max-w-2xl overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Campos de Experiência</DialogTitle>
            <DialogDescription>
              Campos oficiais valem para todas as escolas. Desativar um campo com perguntas exige escolher
              para qual campo elas vão.
            </DialogDescription>
          </DialogHeader>
          <div className="flex justify-end">
            <Button size="sm" onClick={abrirNovo}><PlusCircle className="mr-2 h-4 w-4" /> Novo Campo</Button>
          </div>
          <div className="divide-y rounded-md border">
            {ordenados.length === 0 && <p className="p-4 text-center text-sm text-gray-500">Nenhum campo cadastrado.</p>}
            {ordenados.map((c) => {
              const Icone = iconeDoCampo(c.nome, c.icone);
              return (
                <div key={c.id} className={`flex items-center justify-between gap-3 px-4 py-3 ${c.ativo === false ? 'opacity-60' : ''}`}>
                  <div className="flex min-w-0 items-center gap-3">
                    <Icone className="h-5 w-5 shrink-0 text-purple-600" />
                    <div className="min-w-0">
                      <p className="truncate font-medium">{c.nome}</p>
                      <p className="text-xs text-gray-500">
                        {c.escola ? c.escola_nome : 'Oficial'} · {c.total_perguntas ?? 0} pergunta(s)
                        {c.ativo === false && ' · desativado'}
                      </p>
                    </div>
                  </div>
                  {editavel(c) ? (
                    <div className="flex shrink-0 items-center gap-1">
                      <Button variant="ghost" size="icon" aria-label="Editar campo"
                        onClick={() => setFormCampo({ id: c.id, nome: c.nome, icone: c.icone || 'BookOpen', escola: c.escola ? String(c.escola) : OFICIAL })}>
                        <Edit className="h-4 w-4" />
                      </Button>
                      {c.ativo === false ? (
                        <Button variant="ghost" size="icon" aria-label="Reativar campo" onClick={() => reativar(c)}>
                          <RotateCcw className="h-4 w-4 text-green-600" />
                        </Button>
                      ) : (
                        <Button variant="ghost" size="icon" aria-label="Desativar campo" onClick={() => { setDestino(''); setDesativando(c); }}>
                          <Power className="h-4 w-4 text-red-500" />
                        </Button>
                      )}
                    </div>
                  ) : <span className="shrink-0 text-xs text-gray-400">Somente leitura</span>}
                </div>
              );
            })}
          </div>
        </DialogContent>
      </Dialog>

      {/* Criar/editar campo */}
      <Dialog open={!!formCampo} onOpenChange={(aberto) => { if (!aberto && !salvandoCampo) setFormCampo(null); }}>
        <DialogContent className="max-w-md">
          <DialogHeader><DialogTitle>{formCampo?.id ? 'Editar' : 'Novo'} Campo de Experiência</DialogTitle></DialogHeader>
          <div className="space-y-4 py-2">
            {!formCampo?.id && (podeEditarOficiais || escolas.length > 1) && (
              <div>
                <Label htmlFor="campo-escola">Escola</Label>
                <Select value={formCampo?.escola || ''} onValueChange={(v) => setFormCampo((f) => ({ ...f, escola: v }))}>
                  <SelectTrigger id="campo-escola"><SelectValue placeholder="Selecione a escola" /></SelectTrigger>
                  <SelectContent>
                    {podeEditarOficiais && <SelectItem value={OFICIAL}>Oficial (todas as escolas)</SelectItem>}
                    {escolas.map((e) => <SelectItem key={e.id} value={String(e.id)}>{e.nome}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
            )}
            <div>
              <Label htmlFor="campo-nome">Nome do campo</Label>
              <Input id="campo-nome" maxLength={200} value={formCampo?.nome || ''}
                onChange={(e) => setFormCampo((f) => ({ ...f, nome: e.target.value }))} />
            </div>
            <div>
              <Label>Ícone</Label>
              <div className="mt-2">
                <IconPicker selectedIcon={formCampo?.icone || 'BookOpen'} onSelect={(icone) => setFormCampo((f) => ({ ...f, icone }))} />
              </div>
            </div>
          </div>
          <DialogFooter>
            <DialogClose asChild><Button variant="ghost" disabled={salvandoCampo}>Cancelar</Button></DialogClose>
            <Button onClick={salvarCampo} disabled={salvandoCampo || !formCampo?.nome.trim()}>
              {salvandoCampo && <Loader2 className="mr-2 h-4 w-4 animate-spin" />} Salvar
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Desativar campo (com remanejamento) */}
      <Dialog open={!!desativando} onOpenChange={(aberto) => { if (!aberto && !processando) setDesativando(null); }}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Desativar campo</DialogTitle>
            <DialogDescription>
              O campo "{desativando?.nome}" deixa de ser oferecido nos cadastros. Você pode reativá-lo depois.
            </DialogDescription>
          </DialogHeader>
          {(desativando?.total_perguntas || 0) > 0 && (
            <div className="space-y-2">
              <div className="flex items-start gap-2 rounded-md bg-amber-50 p-3 text-sm text-amber-800">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                <span>{desativando.total_perguntas} pergunta(s) usam este campo e serão remanejadas.</span>
              </div>
              <Label className="font-medium">Remanejar perguntas para</Label>
              <Select value={destino} onValueChange={setDestino}>
                <SelectTrigger><SelectValue placeholder="Selecione o campo de destino" /></SelectTrigger>
                <SelectContent>
                  {destinos.map((c) => <SelectItem key={c.id} value={String(c.id)}>{c.nome}{c.escola ? '' : ' (oficial)'}</SelectItem>)}
                </SelectContent>
              </Select>
              {destinos.length === 0 && (
                <p className="text-xs text-gray-500">Não há outro campo ativo que possa receber estas perguntas. Crie um antes.</p>
              )}
            </div>
          )}
          <DialogFooter>
            <DialogClose asChild><Button variant="ghost" disabled={processando}>Cancelar</Button></DialogClose>
            <Button variant="destructive" onClick={confirmarDesativacao} disabled={processando}>
              {processando && <Loader2 className="mr-2 h-4 w-4 animate-spin" />} Desativar
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
};

export default BnccQuestionsPage;