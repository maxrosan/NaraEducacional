import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import '@/styles/relatorio-editor.css';
import {
  MODELOS,
  PALETAS,
  SECOES_PADRAO,
  DADOS_PREVIA,
  ELEMENTOS_VISIVEIS_PADRAO,
  CAPACIDADES_ELEMENTOS,
  MODELOS_COM_IMAGEM_PRINCIPAL,
  MODELOS_COM_ALINHAMENTO,
  FONTES,
  CORES_TEXTO,
  TIPOGRAFIA_PADRAO,
  cssVarsTipografia,
  renderCapa,
  cssVarsPaleta,
  montarPaletaPersonalizada,
  sortearCoresQueCombinam,
  fetchInstituicao,
  useEscolaTemplate,
  useRotasTemplate,
} from '@/lib/templateRelatorioShared';
import {
  buscarRelatorioTemplate,
  criarRelatorioTemplate,
  atualizarRelatorioTemplate,
} from '@/services/api';

// Modelos que usam foto da criança na capa (bate com RelatorioTemplate.suporta_foto()).
// Apenas 'memorias' — 'natureza' mantém só o círculo pontilhado decorativo,
// sem foto real, por decisão de produto.
const MODELOS_COM_FOTO = ['memorias'];

// Indicador visual usado só nesta tela de preview quando "usar foto da
// criança" está ativado — não é uma foto real (esta tela não representa
// nenhuma criança específica). Serve para o switch ter efeito visível no
// preview; a foto de verdade é resolvida no backend ao gerar cada relatório.
const FOTO_PREVIEW_ATIVA_HTML = `
  <div style="width:100%;height:100%;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:6px;background:#EDE7F6;color:#6D4AAE;text-align:center;padding:12px;box-sizing:border-box;">
    <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 8h3l2-2h6l2 2h3v11H4z"/><circle cx="12" cy="13" r="3.4"/></svg>
    <span style="font-size:11px;font-weight:600;line-height:1.3;">Foto real do aluno aparece aqui</span>
  </div>`;

const CAPACIDADES_INFO_RELATORIO = {
  classico: { tipo: true, titulo: false, frase: false },
  memorias: { tipo: true, titulo: false, frase: false },
  mascote: { tipo: false, titulo: true, frase: true },
  natureza: { tipo: false, titulo: true, frase: true },
  essencial: { tipo: true, titulo: true, frase: false },
};
const ELEMENTOS_LISTA = [
  { key: 'photo', label: 'Foto da criança' },
  { key: 'age', label: 'Idade' },
  { key: 'teacher', label: 'Nome da professora' },
  { key: 'date', label: 'Data de geração' },
  { key: 'cnpj', label: 'CNPJ da escola' },
  { key: 'contact', label: 'Endereço e telefone' },
  // { key: 'naraLogo', label: 'Logomarca NARA' },
  { key: 'mascot', label: 'Mascote Nara' },
  { key: 'content', label: 'Conteúdo do relatório' },
  // { key: 'footerPhrase', label: 'Frase do rodapé' },
];

// Largura/altura de referência do card (folha A4 em px a 96dpi, aprox.).
const LARGURA_BASE = 794;
const ALTURA_BASE = 1123;

function AccordionSection({ icone, titulo, isOpen, onToggle, children }) {
  return (
    <div className="border border-gray-200 rounded-xl overflow-hidden">
      <button
        type="button"
        onClick={onToggle}
        className="w-full flex items-center gap-3 px-4 py-3 cursor-pointer select-none bg-white hover:bg-gray-50 text-left"
      >
        <span className="text-lg leading-none">{icone}</span>
        <span className="flex-1 font-semibold text-gray-800 text-sm">{titulo}</span>
        <span className={`text-gray-400 text-xs transition ${isOpen ? 'rotate-180' : ''}`}>▾</span>
      </button>
      {isOpen && (
        <div className="px-4 py-4 border-t border-gray-100 space-y-4">{children}</div>
      )}
    </div>
  );
}

function ToggleRow({ label, value, disabled, reason, onChange }) {
  return (
    <div className="flex items-center justify-between gap-3 py-1.5">
      <span className={`text-sm ${disabled ? 'text-gray-300' : 'text-gray-700'}`}>
        {label}
        {disabled && reason && <span className="text-xs text-gray-300"> — {reason}</span>}
      </span>
      <button
        type="button"
        disabled={disabled}
        onClick={onChange}
        className="flex-none w-10 h-[22px] rounded-full relative transition disabled:cursor-not-allowed"
        style={{ background: disabled ? '#e5e7eb' : value ? '#9b87d4' : '#e2dcf5' }}
      >
        <span
          className="absolute top-0.5 w-[18px] h-[18px] rounded-full bg-white shadow transition"
          style={{ left: value ? 20 : 2 }}
        />
      </button>
    </div>
  );
}

export default function TemplateEditorPage() {
  const navigate = useNavigate();
  const { templateId: templateIdDaRota } = useParams();
  const [searchParams] = useSearchParams();
  // Coordenação: /coordenacao/templates/<uuid>. Painel admin: /admin/capa?template=<uuid>.
  // É o UUID do template (vai nas URLs da API), não o id.
  const templateId = templateIdDaRota || searchParams.get('template');
  const rotas = useRotasTemplate();
  const modeloDaUrl = searchParams.get('modelo');
  const modoEdicao = Boolean(templateId);
  const { escolaUuid: escolaUuidDaUrl, escolaId: escolaIdDaUrl, comEscola, pronto } = useEscolaTemplate();
  // Editando: a escola é a do template (não muda). Criando: a da URL.
  // escolaAlvo é o UUID (links e prévia); no body de criação vai escolaIdDaUrl.
  const [escolaDoTemplate, setEscolaDoTemplate] = useState(null);
  const escolaAlvo = modoEdicao ? escolaDoTemplate : escolaUuidDaUrl;
  const rotaModelos = comEscola(rotas.modelos, escolaAlvo);

  const [carregando, setCarregando] = useState(modoEdicao);
  const [modeloId, setModeloId] = useState(modeloDaUrl || 'classico');
  const [templateAtivoId, setTemplateAtivoId] = useState(null);

  const [paletaId, setPaletaId] = useState('padrao');
  const [corPrincipal, setCorPrincipal] = useState('#9b87d4');
  const [corSecundaria, setCorSecundaria] = useState('#8bc4a0');

  const [itemsSumario, setItemsSumario] = useState(SECOES_PADRAO);

  const [secaoAberta, setSecaoAberta] = useState('sistema');

  function alternarSecao(id) {
    setSecaoAberta((atual) => (atual === id ? null : id));
  }

  const [tipoRelatorio, setTipoRelatorio] = useState('Relatório Individual');
  const [tituloRelatorio, setTituloRelatorio] = useState('Relatório de Acompanhamento da Aprendizagem');
  const [fraseDestaque, setFraseDestaque] = useState('');

  const [usaFotoCrianca, setUsaFotoCrianca] = useState(false);
  const [elementos, setElementos] = useState(() => ({
    ...ELEMENTOS_VISIVEIS_PADRAO,
    // "Com a Nara" e "Essencial" têm slot de mascote — nasce ligada por
    // padrão pra um template NOVO nesses dois modelos. No modo edição, o
    // useEffect de carga (abaixo) sobrescreve com o que já foi salvo, então
    // isso não afeta templates existentes.
    mascot: ['mascote', 'essencial'].includes(modeloDaUrl || 'classico'),
  }));
  const [imagemPrincipal, setImagemPrincipal] = useState(() =>
    ['mascote', 'essencial'].includes(modeloDaUrl || 'classico') ? 'mascote' : 'nenhuma'
  );

  const [fonteCombo, setFonteCombo] = useState(TIPOGRAFIA_PADRAO.fonteCombo);
  const [corTexto, setCorTexto] = useState(TIPOGRAFIA_PADRAO.corTexto);
  const [nomeTamanho, setNomeTamanho] = useState(TIPOGRAFIA_PADRAO.nomeTamanho);
  const [tituloTamanho, setTituloTamanho] = useState(TIPOGRAFIA_PADRAO.tituloTamanho);
  const [alinhamento, setAlinhamento] = useState(null); // null = usa o default do próprio modelo

  const [instituicao, setInstituicao] = useState({ nome: 'Sua Escola', cnpj: '', contato: '', logoUrl: null });
  const [salvando, setSalvando] = useState(false);
  const [erro, setErro] = useState(null);
  const [sucesso, setSucesso] = useState(false);

  // Prévia com os dados da escola do template (como o gerador faz).
  useEffect(() => {
    if (modoEdicao ? !escolaDoTemplate : !pronto) return;
    fetchInstituicao(escolaAlvo).then(setInstituicao);
  }, [modoEdicao, escolaDoTemplate, pronto, escolaAlvo]);

  useEffect(() => {
    if (!modoEdicao) return;
    (async () => {
      try {
        const t = await buscarRelatorioTemplate(templateId);
        setModeloId(t.modelo);
        setEscolaDoTemplate(t.escola_uuid ? String(t.escola_uuid) : null);
        setItemsSumario(Array.isArray(t.items_sumario) && t.items_sumario.length ? t.items_sumario : SECOES_PADRAO);
        setTemplateAtivoId(t.ativo ? t.id : null);
        // O campo do model é usa_foto_aluno (usa_foto_crianca era do legado).
        setUsaFotoCrianca(Boolean(t.usa_foto_aluno ?? t.usa_foto_crianca));
        setTipoRelatorio(t.config?.tipoRelatorio || 'Relatório Individual');
        setTituloRelatorio(t.config?.tituloRelatorio || 'Relatório de Acompanhamento da Aprendizagem');
        setFraseDestaque(t.config?.fraseDestaque || '');
        setElementos({ ...ELEMENTOS_VISIVEIS_PADRAO, ...(t.config?.elementos || {}) });
        setImagemPrincipal(t.config?.imagemPrincipal || 'nenhuma');
        setFonteCombo(t.config?.fonteCombo || TIPOGRAFIA_PADRAO.fonteCombo);
        setCorTexto(t.config?.corTexto || TIPOGRAFIA_PADRAO.corTexto);
        setNomeTamanho(t.config?.nomeTamanho || TIPOGRAFIA_PADRAO.nomeTamanho);
        setTituloTamanho(t.config?.tituloTamanho || TIPOGRAFIA_PADRAO.tituloTamanho);
        setAlinhamento(t.config?.alinhamento || null);

        const paletaSalva = t.config?.paleta;
        if (!paletaSalva || Object.keys(paletaSalva).length === 0) {
          setPaletaId('padrao');
        } else {
          const match = Object.entries(PALETAS).find(
            ([id, p]) => id !== 'padrao' && p.cores.roxo?.base?.toLowerCase() === paletaSalva.roxo?.base?.toLowerCase()
          );
          if (match) {
            setPaletaId(match[0]);
          } else {
            setPaletaId('personalizada');
            if (paletaSalva.roxo?.base) setCorPrincipal(paletaSalva.roxo.base);
            if (paletaSalva.verde?.base) setCorSecundaria(paletaSalva.verde.base);
          }
        }
      } catch (e) {
        setErro(e.message);
      } finally {
        setCarregando(false);
      }
    })();
  }, [modoEdicao, templateId]);

  const paletaAtual = useMemo(
    () => (paletaId === 'personalizada' ? montarPaletaPersonalizada(corPrincipal, corSecundaria) : PALETAS[paletaId] || PALETAS.padrao),
    [paletaId, corPrincipal, corSecundaria]
  );

  const modeloAtual = MODELOS.find((m) => m.id === modeloId);
  const suportaFoto = MODELOS_COM_FOTO.includes(modeloId);
  const cap = CAPACIDADES_INFO_RELATORIO[modeloId] || CAPACIDADES_INFO_RELATORIO.classico;
  const capElementos = CAPACIDADES_ELEMENTOS[modeloId] || CAPACIDADES_ELEMENTOS.classico;
  const suportaImagemPrincipal = MODELOS_COM_IMAGEM_PRINCIPAL.includes(modeloId);
  const suportaAlinhamento = MODELOS_COM_ALINHAMENTO.includes(modeloId);
  const alinhamentoEfetivo = alinhamento || (modeloId === 'natureza' ? 'center' : 'left');
  const suportaConteudoCapa = capElementos.content;

  // Nome do template é decidido pelo sistema, não pelo coordenador —
  // "{Nome do modelo} — {Nome da instituição}".
  const nomeTemplateGerado = `${modeloAtual?.nome || 'Template'} — ${instituicao.nome}`;

  const capaHtml = useMemo(
    () =>
      renderCapa(modeloId, {
        escolaNome: instituicao.nome,
        escolaCnpj: instituicao.cnpj,
        escolaContato: instituicao.contato,
        logoUrl: instituicao.logoUrl,
        itemsSumario,
        tipoRelatorio,
        tituloRelatorio,
        fraseDestaque,
        elementos,
        imagemPrincipal,
        alinhamento,
        // Preview não tem uma criança real associada (é tela de configuração
        // do template, não de geração de relatório). Quando a opção está
        // ativada, mostra um indicador visual — não uma foto real — só para
        // confirmar que o switch tem efeito na composição da capa. A foto
        // de verdade é resolvida no backend na hora de gerar cada relatório.
        fotoCriancaHtml: suportaFoto && usaFotoCrianca ? FOTO_PREVIEW_ATIVA_HTML : undefined,
      }),
    [modeloId, instituicao, itemsSumario, tipoRelatorio, tituloRelatorio, fraseDestaque, elementos, imagemPrincipal, alinhamento, suportaFoto, usaFotoCrianca]
  );

  const estiloPreview = useMemo(
    () => ({
      ...cssVarsPaleta(paletaAtual),
      ...cssVarsTipografia({ fonteCombo, corTexto, nomeTamanho, tituloTamanho }),
    }),
    [paletaAtual, fonteCombo, corTexto, nomeTamanho, tituloTamanho]
  );

  function moverSecao(index, direcao) {
    const novo = [...itemsSumario];
    const alvo = index + direcao;
    if (alvo < 0 || alvo >= novo.length) return;
    [novo[index], novo[alvo]] = [novo[alvo], novo[index]];
    setItemsSumario(novo);
  }

  function renomearSecao(index, titulo) {
    const novo = [...itemsSumario];
    novo[index] = { ...novo[index], titulo };
    setItemsSumario(novo);
  }

  function alternarElemento(key) {
    setElementos((prev) => ({ ...prev, [key]: !prev[key] }));
  }

  // Configuração de cada linha do dropdown "Textos e elementos visíveis" —
  // espelha a função mascotDisabled/sw(...) do protótipo.
  function configDoElemento(key) {
    if (key === 'photo') {
      return { value: usaFotoCrianca, disabled: !suportaFoto, reason: 'este modelo não usa foto', onChange: () => setUsaFotoCrianca((v) => !v) };
    }
    if (key === 'mascot') {
      const disponivel = capElementos.mascot && imagemPrincipal === 'mascote';
      return { value: elementos.mascot, disabled: !disponivel, reason: 'escolha a mascote em Imagem principal', onChange: () => alternarElemento('mascot') };
    }
    if (key === 'content') {
      return { value: elementos.content, disabled: !capElementos.content, reason: 'exclusivo do Clássico NARA', onChange: () => alternarElemento('content') };
    }
    const disponivel = capElementos[key] !== false;
    return { value: elementos[key], disabled: !disponivel, reason: 'não aparece neste modelo', onChange: () => alternarElemento(key) };
  }

  async function salvar() {
    setErro(null);
    setSalvando(true);
    try {
      const payload = {
        nome: nomeTemplateGerado,
        modelo: modeloId,
        usa_foto_aluno: suportaFoto ? usaFotoCrianca : false,
        config: {
          paleta: paletaAtual.cores,
          tipoRelatorio,
          tituloRelatorio,
          fraseDestaque,
          elementos,
          imagemPrincipal,
          fonteCombo,
          corTexto,
          nomeTamanho,
          tituloTamanho,
          alinhamento,
        },
        // Preserva o "ocultar" configurado em Admin → Relatórios (antes
        // forçava visivel: true e desfazia essa configuração a cada salvar).
        items_sumario: itemsSumario.map((i) => ({ ...i, visivel: i.visivel !== false })),
      };
      if (!modoEdicao) {
        // Criar = "Selecionar" um modelo que a escola ainda não tinha: o novo
        // template passa a valer (o backend desativa os outros da escola).
        // Antes nascia inativo e a capa escolhida não era usada. Na edição,
        // `ativo` não é enviado: editar não troca a capa em uso.
        payload.ativo = true;
        // Escola do template (admin/superadmin precisam; para o coordenador
        // o backend usa sempre a escola dele).
        if (escolaIdDaUrl) payload.escola = escolaIdDaUrl;
      }
      if (modoEdicao) {
        await atualizarRelatorioTemplate(templateId, payload);
      } else {
        await criarRelatorioTemplate(payload);
      }
      setSucesso(true);
      setTimeout(() => navigate(rotaModelos), 1200);
    } catch (e) {
      setErro(e.message);
    } finally {
      setSalvando(false);
    }
  }

  if (carregando) {
    return <div className="max-w-7xl mx-auto px-6 py-8 text-gray-400">Carregando template...</div>;
  }

  return (
    // No painel admin a tela fica abaixo da navbar e do título do painel:
    // altura da janela menos esse espaço (no layout do coordenador, a tela inteira).
    <div className={`max-w-[1600px] mx-auto lg:flex lg:flex-col ${rotas.noAdmin ? 'py-2 lg:h-[calc(100vh-11rem)]' : 'px-6 py-8 lg:h-screen lg:py-6'}`}>
      <div className="flex items-center gap-3 mb-6 flex-none">
        <button
          onClick={() => navigate(rotaModelos)}
          className="text-sm text-gray-500 hover:text-violet-400 border border-gray-500 hover:border-violet-500 rounded-xl px-4 py-2 transition-colors"
        >
          ← Voltar aos modelos
        </button>
        <div className="ml-2">
          <span className="block text-[11px] uppercase tracking-wide text-gray-400 font-bold">
            {modoEdicao ? 'Editar template' : 'Novo template'}
          </span>
          <strong className="text-lg text-gray-700">{modeloAtual?.nome}</strong>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[420px_minmax(0,1fr)] gap-6 items-start lg:flex-1 lg:min-h-0">
        {/* Painel de controles — acordeão, nas mesmas seções do protótipo.
        Em telas grandes, rola dentro de si mesmo (altura travada pelo grid
        pai via lg:min-h-0 + lg:h-full), então a prévia ao lado nunca precisa
        de sticky nem de "corredor" pra acompanhar o scroll. */}
        <div className="space-y-3 lg:h-full lg:overflow-y-auto lg:pr-1">
          <AccordionSection icone="🔄" titulo="Dados que vêm do sistema" isOpen={secaoAberta === 'sistema'} onToggle={() => alternarSecao('sistema')}>
            <p className="text-xs text-gray-500 leading-relaxed bg-gray-50 border border-gray-200 rounded-lg p-3">
              🔒 Os dados da <b>escola</b> e da <b>criança</b> são preenchidos automaticamente pelo sistema na hora
              de gerar o relatório. Aqui aparecem só como exemplo, para você ver como a capa fica.
            </p>
            <div className="text-sm divide-y divide-gray-100 border border-gray-100 rounded-lg overflow-hidden">
              <div className="flex justify-between px-3 py-2"><span className="text-gray-400">Escola</span><b className="text-gray-700">{instituicao.nome}</b></div>
              <div className="flex justify-between px-3 py-2"><span className="text-gray-400">CNPJ</span><b className="text-gray-700 text-right">{instituicao.cnpj || '—'}</b></div>
              <div className="flex justify-between px-3 py-2"><span className="text-gray-400">Contato</span><b className="text-gray-700 text-right">{instituicao.contato || '—'}</b></div>
            </div>

            <div>
              <label className="block text-xs font-bold text-gray-500 mb-2">Logotipo da escola</label>
              <div className="flex items-center gap-3 border border-gray-200 rounded-lg p-3">
                <div className="w-10 h-10 rounded bg-gray-100 flex items-center justify-center overflow-hidden flex-none">
                  {instituicao.logoUrl ? (
                    <img src={instituicao.logoUrl} alt="" className="w-full h-full object-contain" />
                  ) : (
                    <span className="text-gray-300">🖼️</span>
                  )}
                </div>
                <p className="text-xs text-gray-500 flex-1">
                  Vem do cadastro da escola. Envio de um logotipo exclusivo para a capa ainda não está disponível.
                </p>
                <button type="button" disabled className="text-xs font-semibold px-3 py-1.5 rounded-lg border border-gray-200 text-gray-300 cursor-not-allowed">
                  Em breve
                </button>
              </div>
            </div>
          </AccordionSection>

          <AccordionSection icone="📋" titulo="Informações do relatório" isOpen={secaoAberta === 'info'} onToggle={() => alternarSecao('info')}>
            {cap.titulo && (
              <div>
                <label className="block text-xs font-bold text-gray-500 mb-1">Título do relatório</label>
                <input
                  type="text"
                  value={tituloRelatorio}
                  onChange={(e) => setTituloRelatorio(e.target.value)}
                  maxLength={62}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:border-violet-500 focus:outline-none"
                />
              </div>
            )}

            {cap.tipo && (
              <div>
                <label className="block text-xs font-bold text-gray-500 mb-1">Tipo de relatório</label>
                <input
                  type="text"
                  value={tipoRelatorio}
                  onChange={(e) => setTipoRelatorio(e.target.value)}
                  maxLength={40}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:border-violet-500 focus:outline-none"
                />
              </div>
            )}

            {cap.frase && (
              <div>
                <label className="block text-xs font-bold text-gray-500 mb-1">Frase de destaque da capa</label>
                <input
                  type="text"
                  value={fraseDestaque}
                  onChange={(e) => setFraseDestaque(e.target.value)}
                  placeholder={
                    modeloId === 'mascote' ? 'Meu caminho de aprendizagens' : 'Pequenas descobertas, grandes aprendizagens'
                  }
                  maxLength={52}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:border-violet-500 focus:outline-none"
                />
              </div>
            )}

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-bold text-gray-500 mb-1">Período / bimestre / semestre</label>
                <input type="text" value={DADOS_PREVIA.periodo} disabled className="w-full border border-gray-200 bg-gray-50 text-gray-400 rounded-lg px-3 py-2 text-sm cursor-not-allowed" />
              </div>
              <div>
                <label className="block text-xs font-bold text-gray-500 mb-1">Ano letivo</label>
                <input type="text" value={DADOS_PREVIA.anoLetivo} disabled className="w-full border border-gray-200 bg-gray-50 text-gray-400 rounded-lg px-3 py-2 text-sm cursor-not-allowed" />
              </div>
            </div>
            <div>
              <label className="block text-xs font-bold text-gray-500 mb-1">Data de geração</label>
              <input type="text" value={DADOS_PREVIA.dataGeracao} disabled className="w-full border border-gray-200 bg-gray-50 text-gray-400 rounded-lg px-3 py-2 text-sm cursor-not-allowed" />
            </div>
            <p className="text-xs text-gray-500 leading-relaxed bg-gray-50 border border-gray-200 rounded-lg p-3">
              🔒 Esses três campos são preenchidos automaticamente pelo sistema na hora de gerar cada relatório —
              aqui aparecem só como exemplo.
            </p>
          </AccordionSection>

          {suportaFoto && (
            <AccordionSection icone="📷" titulo="Foto da criança" isOpen={secaoAberta === 'foto'} onToggle={() => alternarSecao('foto')}>
              <label className="flex items-center justify-between gap-3 text-sm text-gray-700">
                Usar a foto da criança nesta capa
                <button
                  type="button"
                  onClick={() => setUsaFotoCrianca((v) => !v)}
                  className="flex-none w-10 h-[22px] rounded-full relative transition"
                  style={{ background: usaFotoCrianca ? '#9b87d4' : '#e2dcf5' }}
                >
                  <span className="absolute top-0.5 w-[18px] h-[18px] rounded-full bg-white shadow transition" style={{ left: usaFotoCrianca ? 20 : 2 }} />
                </button>
              </label>
              <p className="text-xs text-gray-500 leading-relaxed bg-gray-50 border border-gray-200 rounded-lg p-3">
                📸 A foto é cadastrada em Gestão de Alunos, no perfil de cada criança. Quando ativado, o relatório
                usa a foto salva da criança; se ela ainda não tiver foto cadastrada, a capa mantém a composição
                decorativa padrão deste modelo.
              </p>
            </AccordionSection>
          )}

          <AccordionSection icone="🌈" titulo="Cores" isOpen={secaoAberta === 'cores'} onToggle={() => alternarSecao('cores')}>
            <div className="space-y-2">
              {Object.entries(PALETAS).map(([id, p]) => (
                <button
                  key={id}
                  onClick={() => setPaletaId(id)}
                  className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl border text-left transition ${paletaId === id ? 'border-violet-400 bg-violet-50' : 'border-gray-200 hover:border-violet-300'
                    }`}
                >
                  <span className="flex -space-x-2 flex-none">
                    {p.amostra.map((cor, i) => (
                      <span key={i} className="w-6 h-6 rounded-full border-2 border-white shadow-sm" style={{ background: cor }} />
                    ))}
                  </span>
                  <span className="flex-1">
                    <span className="block text-sm font-semibold text-gray-800">{p.nome}</span>
                    <span className="block text-xs text-gray-400">{p.desc}</span>
                  </span>
                  {paletaId === id && <span className="flex-none text-violet-600">✓</span>}
                </button>
              ))}
            </div>

            <div className="border border-gray-200 rounded-xl p-4 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm font-semibold text-gray-800">Escolher as cores da escola</span>
                {paletaId === 'personalizada' && (
                  <span className="text-[10px] font-bold uppercase tracking-wide bg-violet-600 text-white rounded-full px-2 py-0.5">Em uso</span>
                )}
              </div>
              <div className="grid grid-cols-2 gap-3">
                <label className="flex items-center gap-2 border border-gray-200 rounded-lg px-2 py-2 cursor-pointer">
                  <input type="color" value={corPrincipal} onChange={(e) => { setCorPrincipal(e.target.value); setPaletaId('personalizada'); }} className="w-8 h-8 rounded border-0 cursor-pointer flex-none" />
                  <span>
                    <span className="block text-xs font-semibold text-gray-700">Cor principal</span>
                    <span className="block text-[11px] text-gray-400 uppercase">{corPrincipal}</span>
                  </span>
                </label>
                <label className="flex items-center gap-2 border border-gray-200 rounded-lg px-2 py-2 cursor-pointer">
                  <input type="color" value={corSecundaria} onChange={(e) => { setCorSecundaria(e.target.value); setPaletaId('personalizada'); }} className="w-8 h-8 rounded border-0 cursor-pointer flex-none" />
                  <span>
                    <span className="block text-xs font-semibold text-gray-700">Cor secundária</span>
                    <span className="block text-[11px] text-gray-400 uppercase">{corSecundaria}</span>
                  </span>
                </label>
              </div>
              <button
                type="button"
                onClick={() => {
                  const sorteio = sortearCoresQueCombinam();
                  setCorPrincipal(sorteio.principal);
                  setCorSecundaria(sorteio.secundaria);
                  setPaletaId('personalizada');
                }}
                className="w-full text-sm font-semibold border border-gray-200 rounded-lg py-2 hover:border-violet-300 hover:bg-violet-50 transition"
              >
                🎲 Sortear cores que combinam
              </button>
              <p className="text-xs text-gray-400 leading-relaxed">
                A cor principal vai na capa e nos títulos; a secundária, nos detalhes. As seções do corpo do
                relatório (Atividades, Relato, Portfólio, BNCC) mantêm suas cores próprias.
              </p>
            </div>

            <button type="button" onClick={() => setPaletaId('padrao')} className="w-full text-sm font-semibold text-gray-500 border border-gray-200 rounded-xl py-2.5 hover:border-gray-300 hover:text-gray-700 transition">
              Voltar às cores originais do modelo
            </button>
          </AccordionSection>

          <AccordionSection icone="👁️" titulo="Textos e elementos visíveis" isOpen={secaoAberta === 'elementos'} onToggle={() => alternarSecao('elementos')}>
            {suportaImagemPrincipal && (
              <div>
                <label className="block text-xs font-bold text-gray-500 mb-2">Imagem principal</label>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => setImagemPrincipal('mascote')}
                    className={`flex-1 text-xs font-semibold rounded-lg py-2 border transition ${imagemPrincipal === 'mascote' ? 'border-violet-400 bg-violet-50 text-violet-700' : 'border-gray-200 text-gray-500 hover:border-violet-300'
                      }`}
                  >
                    Mascote Nara
                  </button>
                  <button
                    type="button"
                    onClick={() => setImagemPrincipal('nenhuma')}
                    className={`flex-1 text-xs font-semibold rounded-lg py-2 border transition ${imagemPrincipal === 'nenhuma' ? 'border-violet-400 bg-violet-50 text-violet-700' : 'border-gray-200 text-gray-500 hover:border-violet-300'
                      }`}
                  >
                    Nenhuma
                  </button>
                </div>
              </div>
            )}

            <div className="divide-y divide-gray-50">
              {ELEMENTOS_LISTA.map((item) => (
                <ToggleRow key={item.key} label={item.label} {...configDoElemento(item.key)} />
              ))}
            </div>
          </AccordionSection>

          {suportaConteudoCapa && (
            <AccordionSection icone="📝" titulo="Conteúdo do relatório" isOpen={secaoAberta === 'conteudo'} onToggle={() => alternarSecao('conteudo')}>
              <p className="text-xs text-gray-400">
                As 6 seções do relatório são sempre exibidas. Você pode renomear e reordenar como preferir — isso
                edita o bloco &ldquo;Conteúdo do Relatório&rdquo; da capa e a ordem das páginas do corpo.
              </p>
              <div className="space-y-2">
                {itemsSumario.map((item, i) => (
                  <div key={item.chave} className="flex items-center gap-2 border border-gray-200 rounded-lg px-2 py-2 bg-white">
                    <span className="flex flex-col flex-none">
                      <button onClick={() => moverSecao(i, -1)} disabled={i === 0} className="text-gray-400 hover:text-violet-600 disabled:opacity-20 leading-none text-xs" title="Mover para cima">▲</button>
                      <button onClick={() => moverSecao(i, 1)} disabled={i === itemsSumario.length - 1} className="text-gray-400 hover:text-violet-600 disabled:opacity-20 leading-none text-xs" title="Mover para baixo">▼</button>
                    </span>
                    <input
                      type="text"
                      value={item.titulo}
                      onChange={(e) => renomearSecao(i, e.target.value)}
                      className="flex-1 min-w-0 text-sm border border-transparent hover:border-gray-200 focus:border-violet-400 rounded px-2 py-1 focus:outline-none"
                    />
                  </div>
                ))}
              </div>
            </AccordionSection>
          )}

          <AccordionSection icone="✒️" titulo="Tipografia" isOpen={secaoAberta === 'tipografia'} onToggle={() => alternarSecao('tipografia')}>
            <div>
              <label className="block text-xs font-bold text-gray-500 mb-2">Combinação de fontes</label>
              <div className="flex flex-wrap gap-2">
                {Object.entries(FONTES).map(([id, f]) => (
                  <button
                    key={id}
                    type="button"
                    onClick={() => setFonteCombo(id)}
                    className={`text-xs font-semibold rounded-lg px-3 py-2 border transition ${fonteCombo === id ? 'border-violet-400 bg-violet-50 text-violet-700' : 'border-gray-200 text-gray-600 hover:border-violet-300'
                      }`}
                  >
                    {f.nome}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label className="block text-xs font-bold text-gray-500 mb-2">Cor dos textos</label>
              <div className="flex flex-wrap gap-2">
                {CORES_TEXTO.map((c) => (
                  <button
                    key={c.id}
                    type="button"
                    onClick={() => setCorTexto(c.id)}
                    className={`flex items-center gap-1.5 text-xs font-semibold rounded-lg px-3 py-2 border transition ${corTexto === c.id ? 'border-violet-400 bg-violet-50 text-violet-700' : 'border-gray-200 text-gray-600 hover:border-violet-300'
                      }`}
                  >
                    {c.valor && <span className="w-2.5 h-2.5 rounded-full flex-none" style={{ background: c.valor }} />}
                    {c.nome}
                  </button>
                ))}
              </div>
            </div>

            {/* <div>
              <div className="flex items-center justify-between mb-1">
                <label className="text-xs font-bold text-gray-500">Tamanho do nome da criança</label>
                <span className="text-xs text-gray-400">{nomeTamanho}%</span>
              </div>
              <input
                type="range"
                min={80}
                max={120}
                step={1}
                value={nomeTamanho}
                onChange={(e) => setNomeTamanho(Number(e.target.value))}
                className="w-full accent-violet-600"
              />
            </div>

            <div>
              <div className="flex items-center justify-between mb-1">
                <label className="text-xs font-bold text-gray-500">Tamanho do título</label>
                <span className="text-xs text-gray-400">{tituloTamanho}%</span>
              </div>
              <input
                type="range"
                min={80}
                max={120}
                step={1}
                value={tituloTamanho}
                onChange={(e) => setTituloTamanho(Number(e.target.value))}
                className="w-full accent-violet-600"
              />
            </div> */}

            {suportaAlinhamento && (
              <div>
                <label className="block text-xs font-bold text-gray-500 mb-2">Alinhamento</label>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => setAlinhamento('left')}
                    className={`flex-1 text-xs font-semibold rounded-lg py-2 border transition ${alinhamentoEfetivo === 'left' ? 'border-violet-400 bg-violet-50 text-violet-700' : 'border-gray-200 text-gray-500 hover:border-violet-300'
                      }`}
                  >
                    À esquerda
                  </button>
                  <button
                    type="button"
                    onClick={() => setAlinhamento('center')}
                    className={`flex-1 text-xs font-semibold rounded-lg py-2 border transition ${alinhamentoEfetivo === 'center' ? 'border-violet-400 bg-violet-50 text-violet-700' : 'border-gray-200 text-gray-500 hover:border-violet-300'
                      }`}
                  >
                    Centralizado
                  </button>
                </div>
              </div>
            )}

            {/* <p className="text-xs text-gray-500 leading-relaxed bg-gray-50 border border-gray-200 rounded-lg p-3">
              🔒 Os tamanhos têm limite entre 80% e 120%, para manter a legibilidade e o texto não estourar a
              página.
            </p> */}
          </AccordionSection>

          {erro && <p className="text-sm text-red-600">{erro}</p>}
          {sucesso && (
            <p className="text-sm text-green-700 bg-green-50 border border-green-200 rounded-lg px-3 py-2">Template salvo!</p>
          )}

          <button
            onClick={salvar}
            disabled={salvando}
            className="w-full bg-violet-600 hover:bg-violet-700 disabled:opacity-50 text-white font-semibold rounded-xl py-2.5 transition"
          >
            {salvando ? 'Salvando...' : modoEdicao ? 'Salvar alterações' : 'Criar e usar esta capa'}
          </button>
        </div>

        {/* Prévia — o painel esquerdo agora rola dentro de si mesmo (veja
        lg:overflow-y-auto acima), então a prévia não precisa mais de sticky:
        fica só centralizada nesta coluna, sempre visível por inteiro.

        O escalonamento é feito via <svg viewBox>, não mais com
        `transform: scale()` calculado em JS — ver comentário acima de
        LARGURA_BASE/ALTURA_BASE sobre por que isso elimina o corte da capa
        ao dar zoom no navegador. */}
        <div className="lg:h-full lg:overflow-y-auto flex flex-col items-center">
          <div className="bg-gray-50 border border-gray-200 rounded-2xl overflow-hidden" style={{ width: '100%', maxWidth: 580 }}>
            <svg
              viewBox={`0 0 ${LARGURA_BASE} ${ALTURA_BASE}`}
              width="100%"
              height="100%"
              preserveAspectRatio="xMidYMin meet"
              style={{
                display: 'block',
                width: '100%',
                aspectRatio: `${LARGURA_BASE} / ${ALTURA_BASE}`,
                boxShadow: '0 8px 24px rgba(44,39,64,.12)',
              }}
            >
              <foreignObject x="0" y="0" width={LARGURA_BASE} height={ALTURA_BASE}>
                <div
                  className="ProseMirror"
                  style={{
                    ...estiloPreview,
                    width: LARGURA_BASE,
                    height: ALTURA_BASE,
                  }}
                  dangerouslySetInnerHTML={{ __html: capaHtml }}
                />
              </foreignObject>
            </svg>
          </div>
          <p className="text-xs text-gray-400 mt-3">
            Prévia em tamanho real · folha A4 (21 × 29,7 cm) · dados fictícios para ilustração
          </p>
        </div>
      </div>
    </div>
  );
}