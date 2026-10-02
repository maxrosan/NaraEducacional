import React, { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import {
  DndContext, closestCenter, KeyboardSensor, PointerSensor, useSensor, useSensors,
} from '@dnd-kit/core';
import {
  arrayMove, SortableContext, sortableKeyboardCoordinates, useSortable, verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { GripVertical, RotateCcw, Save } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { useToast } from '@/components/ui/use-toast';
import { useAuth } from '@/contexts/AuthContext';
import {
  listarEscolas, listarRelatorioTemplates, criarRelatorioTemplate, atualizarRelatorioTemplate,
} from '@/services/api';

/*
 * Ordem, título e visibilidade das seções do relatório — POR ESCOLA.
 *
 * Grava em `relatorio_templates.items_sumario` do template ATIVO da escola
 * (o mesmo que o gerador usa). Sem template ativo:
 *   - se a escola tem algum template, o mais recente é ativado ao salvar;
 *   - se não tem nenhum, cria um "Clássico" ativo.
 * A capa (cores, textos, modelo) continua no editor da coordenação.
 *
 * As chaves espelham _SECOES_PADRAO de api/services/relatorio.py — o backend
 * recusa qualquer outra.
 */
const SECOES_PADRAO = [
  { chave: 'atividades', titulo: 'O que vivemos juntos neste período', visivel: true },
  { chave: 'relato', titulo: 'Relato Individual', visivel: true },
  { chave: 'producoes', titulo: 'Análise das Produções', visivel: true },
  { chave: 'portfolio', titulo: 'Portfólio da Criança', visivel: true },
  { chave: 'bncc', titulo: 'Acompanhamento por Habilidades da BNCC', visivel: true },
  { chave: 'conclusao', titulo: 'Conclusão da Professora', visivel: true },
];
const TITULO_PADRAO = Object.fromEntries(SECOES_PADRAO.map((s) => [s.chave, s.titulo]));
const DESCRICAO = {
  atividades: 'Narrativa da turma a partir dos planejamentos (IA).',
  relato: 'Texto individual a partir das observações da professora (IA).',
  producoes: 'Análises de escrita e desenho, com a imagem da produção (IA).',
  portfolio: 'Fotos das produções da criança no período.',
  bncc: 'Quadro das habilidades observadas, com a frequência.',
  conclusao: 'Carta à família, com a assinatura da professora (IA).',
};

/** Mesma regra do backend (_normalizar_items_sumario): ignora chave
 * desconhecida/repetida e acrescenta no fim a seção que faltar. */
function normalizar(itens) {
  const lista = Array.isArray(itens) ? itens : [];
  const vistas = new Set();
  const resultado = [];
  lista.forEach((item) => {
    if (!item || !TITULO_PADRAO[item.chave] || vistas.has(item.chave)) return;
    vistas.add(item.chave);
    resultado.push({
      chave: item.chave,
      titulo: (item.titulo || '').trim() || TITULO_PADRAO[item.chave],
      visivel: item.visivel !== false,
    });
  });
  SECOES_PADRAO.forEach((s) => { if (!vistas.has(s.chave)) resultado.push({ ...s }); });
  return resultado;
}

function LinhaSecao({ item, posicao, onToggle, onTitulo }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: item.chave });
  const estilo = { transform: CSS.Transform.toString(transform), transition, zIndex: isDragging ? 10 : undefined };

  return (
    <div
      ref={setNodeRef}
      style={estilo}
      className={`flex items-center gap-3 rounded-lg border bg-white p-3 shadow-sm ${isDragging ? 'ring-2 ring-purple-300' : ''} ${item.visivel ? '' : 'opacity-60'}`}
    >
      <button
        type="button"
        {...attributes}
        {...listeners}
        className="cursor-grab touch-none p-1 text-gray-400 hover:text-gray-600"
        aria-label={`Arrastar ${item.titulo}`}
      >
        <GripVertical className="h-5 w-5" />
      </button>
      <span className="w-6 text-center text-sm font-semibold text-gray-400">{posicao}</span>
      <div className="min-w-0 flex-1">
        <Input
          value={item.titulo}
          maxLength={120}
          onChange={(e) => onTitulo(item.chave, e.target.value)}
          onBlur={(e) => { if (!e.target.value.trim()) onTitulo(item.chave, TITULO_PADRAO[item.chave]); }}
          aria-label="Título da seção"
          className="h-9 font-medium"
        />
        <p className="mt-1 truncate text-xs text-gray-500">{DESCRICAO[item.chave]}</p>
      </div>
      <div className="flex items-center gap-2">
        <Label htmlFor={`vis-${item.chave}`} className="hidden text-xs text-gray-500 sm:inline">
          {item.visivel ? 'Visível' : 'Oculta'}
        </Label>
        <Switch id={`vis-${item.chave}`} checked={item.visivel} onCheckedChange={(v) => onToggle(item.chave, v)} />
      </div>
    </div>
  );
}

const RelatoriosConfigTab = () => {
  const { toast } = useToast();
  const { user } = useAuth();

  const [escolas, setEscolas] = useState([]);
  const [escolaId, setEscolaId] = useState('');
  const [templates, setTemplates] = useState([]);
  const [itens, setItens] = useState(SECOES_PADRAO);
  const [salvos, setSalvos] = useState(SECOES_PADRAO);
  const [carregando, setCarregando] = useState(true);
  const [salvando, setSalvando] = useState(false);
  const ultimaCarga = useRef(0);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  // Escolas do escopo (o backend já recorta). Padrão: a escola do usuário.
  useEffect(() => {
    listarEscolas()
      .then((dados) => {
        const ativas = (dados || []).filter((e) => e.ativa !== false);
        setEscolas(ativas);
        const propria = String(user?.escola_id ?? user?.escola ?? '');
        const inicial = ativas.find((e) => String(e.id) === propria) || ativas[0];
        if (inicial) setEscolaId(String(inicial.id));
        else setCarregando(false);
      })
      .catch((err) => {
        toast({ variant: 'destructive', title: 'Erro ao carregar escolas', description: err.message });
        setCarregando(false);
      });
  }, [toast, user]);

  const carregarTemplates = useCallback(async (id) => {
    const carga = ++ultimaCarga.current;
    setCarregando(true);
    try {
      const lista = await listarRelatorioTemplates({ escola: id });
      if (carga !== ultimaCarga.current) return; // troca rápida de escola
      setTemplates(lista || []);
      const ativo = (lista || []).find((t) => t.ativo);
      const normalizados = normalizar(ativo?.items_sumario);
      setItens(normalizados);
      setSalvos(normalizados);
    } catch (err) {
      if (carga === ultimaCarga.current) {
        toast({ variant: 'destructive', title: 'Erro ao carregar a configuração', description: err.message });
      }
    } finally {
      if (carga === ultimaCarga.current) setCarregando(false);
    }
  }, [toast]);

  useEffect(() => { if (escolaId) carregarTemplates(escolaId); }, [escolaId, carregarTemplates]);

  const templateAtivo = templates.find((t) => t.ativo) || null;
  // Lista vem com o ativo primeiro e depois o mais recente.
  const templateParaAtivar = templateAtivo ? null : templates[0] || null;
  const escolaAtual = escolas.find((e) => String(e.id) === escolaId);
  const alterado = useMemo(() => JSON.stringify(itens) !== JSON.stringify(salvos), [itens, salvos]);
  const ehPadrao = useMemo(() => JSON.stringify(itens) === JSON.stringify(SECOES_PADRAO), [itens]);
  const nenhumaVisivel = itens.every((i) => !i.visivel);

  function trocarEscola(id) {
    if (alterado && !window.confirm('Há alterações não salvas nesta escola. Descartar?')) return;
    setEscolaId(id);
  }

  function aoSoltar({ active, over }) {
    if (!over || active.id === over.id) return;
    setItens((atual) => {
      const de = atual.findIndex((i) => i.chave === active.id);
      const para = atual.findIndex((i) => i.chave === over.id);
      return arrayMove(atual, de, para);
    });
  }

  const alternar = (chave, visivel) => setItens((atual) => atual.map((i) => (i.chave === chave ? { ...i, visivel } : i)));
  const renomear = (chave, titulo) => setItens((atual) => atual.map((i) => (i.chave === chave ? { ...i, titulo } : i)));

  async function salvar() {
    const items_sumario = itens.map((i) => ({ ...i, titulo: i.titulo.trim() || TITULO_PADRAO[i.chave] }));
    setSalvando(true);
    try {
      if (templateAtivo) {
        await atualizarRelatorioTemplate(templateAtivo.id, { items_sumario });
      } else if (templateParaAtivar) {
        await atualizarRelatorioTemplate(templateParaAtivar.id, { items_sumario, ativo: true });
      } else {
        await criarRelatorioTemplate({
          escola: escolaId,
          nome: `Clássico — ${escolaAtual?.nome || 'Escola'}`,
          modelo: 'classico',
          ativo: true,
          items_sumario,
        });
      }
      toast({ title: 'Configuração salva!', description: `Vale para os próximos relatórios de ${escolaAtual?.nome || 'a escola'}.` });
      await carregarTemplates(escolaId);
    } catch (err) {
      toast({ variant: 'destructive', title: 'Erro ao salvar', description: err.message });
    } finally {
      setSalvando(false);
    }
  }

  let aviso = null;
  if (!carregando && escolaId && !templateAtivo) {
    aviso = templateParaAtivar
      ? `Esta escola não tem template ativo. Ao salvar, o template "${templateParaAtivar.nome}" será ativado.`
      : 'Esta escola ainda não tem template de relatório. Ao salvar, será criado um template com a capa Clássica.';
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Configuração da Geração de Relatórios</CardTitle>
        <CardDescription>
          Arraste para reordenar, renomeie os títulos e escolha quais seções aparecem no relatório.
          A configuração é por escola e vale para os próximos relatórios gerados.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        {escolas.length > 1 && (
          <div className="max-w-sm">
            <Label htmlFor="escola-relatorio">Escola</Label>
            <Select value={escolaId} onValueChange={trocarEscola}>
              <SelectTrigger id="escola-relatorio"><SelectValue placeholder="Selecione a escola" /></SelectTrigger>
              <SelectContent>
                {escolas.map((e) => <SelectItem key={e.id} value={String(e.id)}>{e.nome}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
        )}

        {!escolaId && !carregando && (
          <p className="py-8 text-center text-sm text-gray-500">Nenhuma escola ativa disponível para configurar.</p>
        )}

        {escolaId && (carregando ? (
          <p className="py-8 text-center text-sm text-gray-500">Carregando configuração...</p>
        ) : (
          <>
            {templateAtivo && (
              <p className="text-sm text-gray-500">
                Template ativo: <span className="font-medium text-gray-700">{templateAtivo.nome}</span>
              </p>
            )}
            {aviso && (
              <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">{aviso}</div>
            )}

            <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={aoSoltar}>
              <SortableContext items={itens.map((i) => i.chave)} strategy={verticalListSortingStrategy}>
                <div className="space-y-3">
                  {itens.map((item, i) => (
                    <LinhaSecao key={item.chave} item={item} posicao={i + 1} onToggle={alternar} onTitulo={renomear} />
                  ))}
                </div>
              </SortableContext>
            </DndContext>

            {nenhumaVisivel && (
              <p className="text-sm text-red-600">Deixe pelo menos uma seção visível.</p>
            )}

            <div className="flex flex-wrap items-center justify-end gap-2 border-t pt-4">
              <Button variant="ghost" onClick={() => setItens(SECOES_PADRAO.map((s) => ({ ...s })))} disabled={salvando || ehPadrao}>
                <RotateCcw className="mr-2 h-4 w-4" /> Restaurar padrão
              </Button>
              <Button variant="outline" onClick={() => setItens(salvos)} disabled={salvando || !alterado}>
                Descartar alterações
              </Button>
              <Button onClick={salvar} disabled={salvando || nenhumaVisivel || (!alterado && !!templateAtivo)}>
                <Save className="mr-2 h-4 w-4" /> {salvando ? 'Salvando...' : 'Salvar'}
              </Button>
            </div>
          </>
        ))}
      </CardContent>
    </Card>
  );
};

export default RelatoriosConfigTab;