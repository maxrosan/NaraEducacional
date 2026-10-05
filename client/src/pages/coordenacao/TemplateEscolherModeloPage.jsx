import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import '@/styles/relatorio-editor.css';

import {
  MODELOS,
  SECOES_PADRAO,
  renderCapa,
  fetchInstituicao,
  apiGet,
  apiPost,
  useEscolaTemplate,
  useRotasTemplate,
  templatePadraoDoModelo,
} from '@/lib/templateRelatorioShared';

function usePreviewScale(larguraBase = 794) {
  const [node, setNode] = useState(null);
  const [escala, setEscala] = useState(0.5);

  const containerRef = (el) => {
    setNode(el);
  };

  useEffect(() => {
    if (!node) return undefined;

    const atualizar = () => {
      const largura = node.getBoundingClientRect().width;

      if (largura > 0) {
        setEscala(largura / larguraBase);
      }
    };

    const raf = requestAnimationFrame(atualizar);

    const observer = new ResizeObserver(atualizar);
    observer.observe(node);

    return () => {
      cancelAnimationFrame(raf);
      observer.disconnect();
    };
  }, [node, larguraBase]);

  return [containerRef, escala];
}


// ---------------------------------------------------------
// Miniatura da capa
// ---------------------------------------------------------

function ModeloThumbnail({ modeloId, instituicao }) {
  const [previewRef, escala] = usePreviewScale(794);

  return (
    <div
      ref={previewRef}
      className="rounded-xl overflow-hidden border border-gray-100 bg-white"
      style={{
        height: escala * 1123,
        position: 'relative',
      }}
    >
      <div
        className="ProseMirror"
        style={{
          width: 794,
          height: 1123,
          transform: `scale(${escala})`,
          transformOrigin: 'top left',
          pointerEvents: 'none',
        }}
        dangerouslySetInnerHTML={{
          __html: renderCapa(modeloId, {
            escolaNome: instituicao.nome,
            escolaCnpj: instituicao.cnpj,
            escolaContato: instituicao.contato,
            logoUrl: instituicao.logoUrl,

            itemsSumario: SECOES_PADRAO,

            imagemPrincipal: ['mascote', 'essencial'].includes(modeloId)
              ? 'mascote'
              : 'nenhuma',

            elementos: {
              mascot: true,
            },
          }),
        }}
      />
    </div>
  );
}


// ---------------------------------------------------------
// Página
// ---------------------------------------------------------

export default function TemplateEscolherModeloPage() {
  const navigate = useNavigate();
  // escolaUuid: URL e GET; escolaId (int): body do POST de criação.
  const { escolaUuid, escolaId, escolas, trocarEscola, comEscola, pronto } = useEscolaTemplate();
  const rotas = useRotasTemplate();

  const [instituicao, setInstituicao] = useState({
    nome: 'Sua Escola',
    cnpj: '',
    contato: '',
    logoUrl: null,
  });

  // ID do template atualmente ativo
  const [templateAtivoId, setTemplateAtivoId] = useState(null);

  // Todos os templates da instituição
  const [templates, setTemplates] = useState([]);

  const [carregando, setCarregando] = useState(true);
  const [selecionandoId, setSelecionandoId] = useState(null);
  const [erro, setErro] = useState(null);


  // -------------------------------------------------------
  // Carregar instituição + template ativo + templates
  // -------------------------------------------------------

  useEffect(() => {
    if (!pronto) return undefined;
    let cancelado = false;

    async function carregarDados() {
      try {
        setCarregando(true);
        setErro(null);

        // Só os templates DA ESCOLA em configuração (o admin enxerga os da
        // rede inteira; sem o filtro, modelos de escolas diferentes se
        // misturavam na tela).
        const [instituicaoData, templatesData] = await Promise.all([
          fetchInstituicao(escolaUuid),
          apiGet(comEscola('/relatorio-templates/')),
        ]);
        if (cancelado) return;

        if (instituicaoData) setInstituicao(instituicaoData);

        const listaTemplates = Array.isArray(templatesData)
          ? templatesData
          : (Array.isArray(templatesData?.results) ? templatesData.results : []);
        setTemplates(listaTemplates);
        // O ativo vem da própria lista (antes usava fetchModeloAtivo, que
        // devolvia o nome do MODELO e era comparado com o id do template).
        setTemplateAtivoId(listaTemplates.find((t) => t.ativo)?.id ?? null);
      } catch (e) {
        if (cancelado) return;
        console.error('Erro ao carregar templates:', e);
        setErro(e.message || 'Não foi possível carregar os templates.');
      } finally {
        if (!cancelado) setCarregando(false);
      }
    }

    carregarDados();
    return () => { cancelado = true; };
  }, [pronto, escolaUuid, comEscola]);


  // -------------------------------------------------------
  // Encontrar template de determinado modelo
  // -------------------------------------------------------

  function encontrarTemplateDoModelo(modeloId) {
    return templates.find(
      (template) => template.modelo === modeloId
    );
  }


  // -------------------------------------------------------
  // Criar template
  // -------------------------------------------------------

  // "Selecionar" um modelo que a escola ainda não tem: cria o template com a
  // configuração padrão JÁ ATIVO (o backend desativa os outros da escola) e
  // fica na tela — para personalizar, o botão "Editar" aparece em seguida.
  // Antes abria o editor e a capa só passava a valer depois de salvar lá.
  async function criar(modeloId) {
    try {
      setSelecionandoId(modeloId);
      setErro(null);

      const ativoAtual = templates.find((t) => t.ativo);
      const payload = {
        ...templatePadraoDoModelo(modeloId, instituicao?.nome, ativoAtual?.items_sumario),
        ativo: true,
        ...(escolaId ? { escola: escolaId } : {}),
      };
      const novo = await apiPost('/relatorio-templates/criar/', payload);

      setTemplates((anteriores) => [
        ...anteriores.map((item) => ({ ...item, ativo: false })),
        novo,
      ]);
      setTemplateAtivoId(novo.id);
    } catch (e) {
      console.error('Erro ao selecionar modelo:', e);
      setErro(e.message || 'Não foi possível selecionar este modelo.');
    } finally {
      setSelecionandoId(null);
    }
  }


  // -------------------------------------------------------
  // Editar template
  // -------------------------------------------------------

  // Recebe o UUID do template (vai na URL do editor).
  function editar(templateUuid) {
    navigate(
      comEscola(rotas.editar(templateUuid))
    );
  }


  // -------------------------------------------------------
  // Selecionar/ativar template
  // -------------------------------------------------------

  async function selecionar(template) {
    if (!template?.id) {
      return;
    }

    // Já está selecionado
    if (
      template.ativo === true ||
      template.id === templateAtivoId
    ) {
      return;
    }

    try {
      setSelecionandoId(template.id);
      setErro(null);

      await apiPost(
        `/api/templates-relatorio/${template.uuid}/ativar/`,
        {}
      );

      // Atualiza imediatamente a interface
      setTemplateAtivoId(template.id);

      // Atualiza também a lista local dos templates
      setTemplates((anteriores) =>
        anteriores.map((item) => ({
          ...item,
          ativo: item.id === template.id,
        }))
      );

    } catch (e) {
      console.error('Erro ao selecionar template:', e);

      setErro(
        e.message ||
        'Não foi possível selecionar este modelo.'
      );
    } finally {
      setSelecionandoId(null);
    }
  }


  // -------------------------------------------------------
  // Loading
  // -------------------------------------------------------

  if (carregando) {
    return (
      <div className="max-w-6xl mx-auto px-6 py-10">
        <div className="text-gray-400 text-sm">
          Carregando modelos...
        </div>
      </div>
    );
  }


  // -------------------------------------------------------
  // Render
  // -------------------------------------------------------


  return (
    <div className="content">

      {/* -------------------------------------------------
        Cabeçalho
       ------------------------------------------------- */}

      <div className="page-header">
        <div>
          <h1 className="page-title">
            Escolha a capa do relatório
          </h1>
          <p className="page-subtitle">
            Escolha um modelo e personalize com as informações e a
            identidade visual da sua escola.
          </p>
        </div>
      </div>


      {/* Escola em configuração — só para quem enxerga mais de uma. */}
      {escolas.length > 1 && (
        <div className="mt-4 max-w-sm">
          <label htmlFor="escola-capa" className="block text-sm font-medium text-gray-700 mb-1">
            Escola
          </label>
          <select
            id="escola-capa"
            value={escolaUuid || ''}
            onChange={(e) => trocarEscola(e.target.value)}
            className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm"
          >
            {escolas.map((e) => <option key={e.uuid} value={e.uuid}>{e.nome}</option>)}
          </select>
        </div>
      )}

      {/* -------------------------------------------------
          Erro
         ------------------------------------------------- */}

      {erro && (
        <div className="mt-4 text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-4 py-3">
          {erro}
        </div>
      )}


      {/* -------------------------------------------------
          Modelos
         ------------------------------------------------- */}

      <div className="mt-8 grid grid-cols-[repeat(auto-fill,minmax(280px,1fr))] gap-6">

        {MODELOS.map((modelo) => {

          // Template salvo para este modelo
          const templateExistente =
            encontrarTemplateDoModelo(modelo.id);


          // -------------------------------------------------
          // Verifica se é o template atualmente ativo
          //
          // Mantemos as duas verificações:
          //
          // 1. template.ativo
          // 2. templateAtivoId (o ativo da lista desta escola)
          //
          // Assim a UI continua funcionando mesmo se o endpoint
          // retornar o ID separado.
          // -------------------------------------------------

          const selecionado =
            Boolean(
              templateExistente &&
              (
                templateExistente.ativo === true ||
                templateExistente.id === templateAtivoId
              )
            );


          const estaSelecionando =
            selecionandoId === templateExistente?.id;


          return (
            <div
              key={modelo.id}
              className={`
                relative
                bg-white
                rounded-2xl
                p-3
                shadow-sm
                transition
                border
                ${selecionado
                  ? 'border-violet-400 ring-2 ring-violet-300'
                  : 'border-gray-200'
                }
              `}
            >

              {/* -------------------------------------------------
                  Badge "SELECIONADO"
                 ------------------------------------------------- */}

              {selecionado && (
                <span
                  className="
                    absolute
                    -top-3
                    left-1/2
                    -translate-x-1/2
                    z-10
                    bg-violet-600
                    text-white
                    text-xs
                    font-bold
                    px-4
                    py-1
                    rounded-full
                    shadow-sm
                    whitespace-nowrap
                  "
                >
                  SELECIONADO
                </span>
              )}


              {/* -------------------------------------------------
                  Pré-visualização
                 ------------------------------------------------- */}

              <ModeloThumbnail
                modeloId={modelo.id}
                instituicao={instituicao}
              />


              {/* -------------------------------------------------
                  Informações
                 ------------------------------------------------- */}

              <div className="pt-3 px-1">

                <h3 className="font-bold text-gray-900">
                  {modelo.nome}
                </h3>

                <p className="text-sm text-gray-500 mt-1">
                  {modelo.desc}
                </p>


                {/* -------------------------------------------------
                    Status
                   ------------------------------------------------- */}

                {templateExistente && (
                  <p
                    className={`
                      text-xs
                      font-medium
                      mt-2
                      ${selecionado
                        ? 'text-violet-600'
                        : 'text-gray-500'
                      }
                    `}
                  >
                    {selecionado
                      ? '✓ Modelo atualmente em uso'
                      : '✓ Modelo configurado'}
                  </p>
                )}


                {/* -------------------------------------------------
                    Botões
                   ------------------------------------------------- */}

                <div className="mt-4 flex gap-2">

                  {/* -----------------------------------------------
                      NÃO EXISTE TEMPLATE
                     ----------------------------------------------- */}

                  {!templateExistente && (
                    <button
                      type="button"
                      disabled={selecionandoId === modelo.id}
                      onClick={() => criar(modelo.id)}
                      className="
                        w-full
                        text-sm
                        font-semibold
                        text-white
                        bg-violet-600
                        hover:bg-violet-700
                        rounded-lg
                        px-4
                        py-2.5
                        transition
                        disabled:opacity-60
                      "
                    >
                      {selecionandoId === modelo.id ? 'Selecionando...' : 'Selecionar'}
                    </button>
                  )}


                  {/* -----------------------------------------------
                      JÁ EXISTE TEMPLATE
                     ----------------------------------------------- */}

                  {templateExistente && (
                    <>
                      {/* -----------------------------------------
                          Editar
                         ----------------------------------------- */}

                      <button
                        type="button"
                        onClick={() =>
                          editar(templateExistente.uuid)
                        }
                        className="
                          flex-1
                          text-sm
                          font-semibold
                          text-violet-700
                          bg-violet-50
                          hover:bg-violet-100
                          border
                          border-violet-200
                          rounded-lg
                          px-4
                          py-2.5
                          transition
                        "
                      >
                        Editar
                      </button>


                      {/* -----------------------------------------
                          Selecionar
                         ----------------------------------------- */}

                      <button
                        type="button"
                        disabled={
                          selecionado ||
                          estaSelecionando
                        }
                        onClick={() =>
                          selecionar(templateExistente)
                        }
                        className={`
                          flex-1
                          text-sm
                          font-semibold
                          rounded-lg
                          px-4
                          py-2.5
                          transition

                          ${selecionado
                            ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
                            : 'bg-violet-600 text-white hover:bg-violet-700'
                          }

                          ${estaSelecionando
                            ? 'opacity-60 cursor-wait'
                            : ''
                          }
                        `}
                      >
                        {estaSelecionando
                          ? 'Selecionando...'
                          : selecionado
                            ? 'Selecionado'
                            : 'Selecionar'}
                      </button>
                    </>
                  )}

                </div>

              </div>

            </div>
          );
        })}

      </div>

    </div>
  );
}