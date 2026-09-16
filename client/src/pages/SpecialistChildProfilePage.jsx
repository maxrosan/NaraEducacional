import React, { useState, useEffect, useCallback } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { Helmet } from 'react-helmet-async';
import { motion, AnimatePresence } from 'framer-motion';
import { ArrowLeft, Plus, ChevronDown, Loader2 } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { useEspecialistaLogado } from '@/hooks/useEspecialistaLogado';
import { capitalizarPalavras } from '@/lib/textFormat';
import SpecialistNavbar from '@/components/specialist/SpecialistNavbar';
import RecadoForm from '@/components/specialist/RecadoForm';
// TODO: confirme o nome real do helper de fetch autenticado usado no projeto
// (mesmo usado em SpecialistHomePage.jsx — ajuste o import se o nome/local
// for diferente).
import { authFetch } from '@/services/api';

const REGISTROS_POR_PAGINA = 10;

function iniciaisDe(nomeCompleto) {
  if (!nomeCompleto) return '?';
  return nomeCompleto
    .split(' ')
    .filter(Boolean)
    .slice(0, 2)
    .map((parte) => parte[0])
    .join('')
    .toUpperCase();
}

function calcularIdade(dataNascimentoIso) {
  if (!dataNascimentoIso) return null;
  const nascimento = new Date(dataNascimentoIso);
  const hoje = new Date();

  let anos = hoje.getFullYear() - nascimento.getFullYear();
  let meses = hoje.getMonth() - nascimento.getMonth();
  if (hoje.getDate() < nascimento.getDate()) meses -= 1;
  if (meses < 0) {
    anos -= 1;
    meses += 12;
  }
  return `${anos}a ${meses}m`;
}

function formatarDataCurta(dataIso) {
  if (!dataIso) return '';
  return new Date(dataIso).toLocaleDateString('pt-BR', { day: '2-digit', month: 'short' });
}

const STATUS_META_CLASSES = {
  ativa: 'bg-[#EEEDFE] text-[#534AB7]',
  alcancada: 'bg-[#E1F5EE] text-[#085041]',
  encerrada: 'bg-gray-100 text-gray-600',
  revisada: 'bg-[#FAEEDA] text-[#633806]',
};

/**
 * Perfil da criança na visão do especialista.
 * Rota: /especialistas/crianca/:criancaId
 *
 * Usa o SpecialistNavbar padrão (fixo, igual todas as outras telas do
 * especialista) — a navegação de "voltar" e o título vivem dentro do
 * próprio conteúdo da página, não num header compartilhado à parte.
 *
 * Cabeçalho (nome, idade, turma) carrega dados reais via
 * GET /api/criancas/{id}/ e GET /api/turmas/{turma_id}/.
 *
 * Aba "Da escola" > "Observações da professora" carrega os registros de
 * voz reais (ObservacaoTranscricao) via
 * GET /api/criancas/{id}/registros-voz/?limite=10&offset=N, com paginação
 * incremental por "Carregar mais".
 *
 * Restante (padrão identificado pela IA, abas Registros/PAEE/Resumo) ainda
 * é visual — dados de exemplo. Trocar pelos blocos // TODO quando as APIs
 * correspondentes existirem.
 */
export default function SpecialistChildProfilePage() {
  const { criancaId } = useParams();
  const navigate = useNavigate();
  const { especialista } = useEspecialistaLogado();
  const [metaAberta, setMetaAberta] = useState(null);
  const [mostrandoRecado, setMostrandoRecado] = useState(false);
  const [resumoTexto, setResumoTexto] = useState(
    'Vini Natan foi acompanhado em sessões regulares de fonoaudiologia ao longo do 1º bimestre. Observou-se evolução consistente na consciência fonológica, com identificação de rimas atingindo 75% de acerto. O foco terapêutico permanece na iniciação verbal em contextos coletivos. A preferência tátil foi identificada como facilitador terapêutico promissor para as próximas sessões.'
  );

  const especialidade = especialista?.tipo_especialista ? capitalizarPalavras(especialista.tipo_especialista) : 'Fonoaudiologia';

  // --- Dados reais da criança ---
  const [crianca, setCrianca] = useState(null);
  const [turma, setTurma] = useState(null);
  const [carregandoCrianca, setCarregandoCrianca] = useState(true);
  const [erroCrianca, setErroCrianca] = useState(null);

  useEffect(() => {
    if (!criancaId) return;

    let cancelado = false;
    setCarregandoCrianca(true);
    setErroCrianca(null);

    authFetch(`/api/criancas/${criancaId}/`)
      .then((res) => {
        if (!res.ok) throw new Error('Falha ao buscar dados da criança');
        return res.json();
      })
      .then((dataCrianca) => {
        if (cancelado) return;
        setCrianca(dataCrianca);
        if (dataCrianca.turma_id) {
          return authFetch(`/api/turmas/${dataCrianca.turma_id}/`)
            .then((res) => (res.ok ? res.json() : null))
            .then((dataTurma) => {
              if (!cancelado) setTurma(dataTurma);
            });
        }
      })
      .catch((err) => {
        if (cancelado) return;
        console.error(err);
        setErroCrianca('Não foi possível carregar os dados da criança.');
      })
      .finally(() => {
        if (!cancelado) setCarregandoCrianca(false);
      });

    return () => {
      cancelado = true;
    };
  }, [criancaId]);

  const nomeExibido = crianca?.nome_completo || 'Carregando…';
  const idadeExibida = calcularIdade(crianca?.data_nascimento);

  // --- Registros de voz (aba "Da escola"), paginados ---
  const [registrosVoz, setRegistrosVoz] = useState([]);
  const [temMaisRegistros, setTemMaisRegistros] = useState(false);
  const [carregandoRegistrosVoz, setCarregandoRegistrosVoz] = useState(true);
  const [carregandoMaisRegistros, setCarregandoMaisRegistros] = useState(false);
  const [erroRegistrosVoz, setErroRegistrosVoz] = useState(null);

  const buscarRegistrosVoz = useCallback((offset, { isLoadMore = false } = {}) => {
    if (!criancaId) return;

    if (isLoadMore) setCarregandoMaisRegistros(true);
    else setCarregandoRegistrosVoz(true);
    setErroRegistrosVoz(null);

    authFetch(`/api/criancas/${criancaId}/registros-voz/?limite=${REGISTROS_POR_PAGINA}&offset=${offset}`)
      .then((res) => {
        if (!res.ok) throw new Error('Falha ao buscar registros de voz');
        return res.json();
      })
      .then((data) => {
        setRegistrosVoz((anteriores) => (isLoadMore ? [...anteriores, ...data.resultados] : data.resultados));
        setTemMaisRegistros(Boolean(data.tem_mais));
      })
      .catch((err) => {
        console.error(err);
        setErroRegistrosVoz('Não foi possível carregar as observações da professora.');
      })
      .finally(() => {
        if (isLoadMore) setCarregandoMaisRegistros(false);
        else setCarregandoRegistrosVoz(false);
      });
  }, [criancaId]);

  useEffect(() => {
    buscarRegistrosVoz(0);
  }, [buscarRegistrosVoz]);

  const handleCarregarMais = () => {
    buscarRegistrosVoz(registrosVoz.length, { isLoadMore: true });
  };

  // --- Metas do PAEE (aba "PAEE"), dados reais de MetaPAEE ---
  const [metasPaee, setMetasPaee] = useState([]);
  const [carregandoMetasPaee, setCarregandoMetasPaee] = useState(true);
  const [erroMetasPaee, setErroMetasPaee] = useState(null);

  useEffect(() => {
    if (!criancaId) return;

    let cancelado = false;
    setCarregandoMetasPaee(true);
    setErroMetasPaee(null);

    authFetch(`/api/criancas/${criancaId}/metas-paee/`)
      .then((res) => {
        if (!res.ok) throw new Error('Falha ao buscar metas do PAEE');
        return res.json();
      })
      .then((data) => {
        if (cancelado) return;
        setMetasPaee(data);
      })
      .catch((err) => {
        if (cancelado) return;
        console.error(err);
        setErroMetasPaee('Não foi possível carregar as metas do PAEE agora.');
      })
      .finally(() => {
        if (!cancelado) setCarregandoMetasPaee(false);
      });

    return () => {
      cancelado = true;
    };
  }, [criancaId]);

  return (
    <>
      <Helmet><title>NARA - {crianca?.nome_completo || 'Especialista'}</title></Helmet>
      <div className="bg-[#F5F3FA] min-h-screen">
        <SpecialistNavbar />

        <main className="container mx-auto px-4 sm:px-6 lg:px-8 py-6">
          {/* Voltar + título — sempre na largura total do container, mesma posição do logo do navbar */}
          <div className="flex items-start gap-3 mb-4">
            <Button variant="ghost" size="icon" className="flex-shrink-0" onClick={() => navigate(-1)}>
              <ArrowLeft className="h-5 w-5 text-gray-600" />
            </Button>
            <div className="flex-1 min-w-0">
              <h1 className="text-lg font-semibold text-gray-800 leading-snug line-clamp-2">{nomeExibido}</h1>
              <p className="text-xs text-gray-500 truncate">{especialidade}</p>
            </div>
            <Button asChild size="icon" className="bg-roxo-principal hover:bg-[#6B4EA8] rounded-xl flex-shrink-0">
              <Link to={`/especialistas/crianca/${criancaId}/registrar`}><Plus className="h-5 w-5" /></Link>
            </Button>
          </div>

          {/* Conteúdo com sua própria largura — não afeta a posição do voltar acima */}
          <div className="max-w-3xl mx-auto space-y-4">
          <Card className="rounded-2xl">
            <CardContent className="p-4 flex items-center gap-3">
              {carregandoCrianca ? (
                <div className="flex items-center gap-2 text-sm text-gray-400">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Carregando dados da criança…
                </div>
              ) : erroCrianca ? (
                <p className="text-sm text-red-500">{erroCrianca}</p>
              ) : (
                <>
                  <div className="w-12 h-12 rounded-full bg-[#E1F5EE] text-[#085041] flex items-center justify-center text-sm font-medium flex-shrink-0">
                    {iniciaisDe(crianca?.nome_completo)}
                  </div>
                  <div>
                    <div className="text-base font-medium text-gray-800">
                      {crianca?.nome_completo}{idadeExibida ? ` · ${idadeExibida}` : ''}
                    </div>
                    <div className="text-xs text-gray-500 mb-1.5">
                      {turma?.nome || 'Turma não informada'}{turma?.ano_letivo ? ` · ${turma.ano_letivo}` : ''}
                    </div>
                    {/* TODO: badges "PAEE ativo"/"Padrão novo" ainda estáticas — sem endpoint definido */}
                    <div className="flex gap-1.5 flex-wrap">
                      <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-[#EEEDFE] text-[#534AB7]">PAEE ativo</span>
                      <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-[#FAEEDA] text-[#633806]">Padrão novo</span>
                    </div>
                  </div>
                </>
              )}
            </CardContent>
          </Card>

          <Tabs defaultValue="escola" className="w-full">
            <TabsList className="w-full grid grid-cols-4 bg-white border border-gray-100 rounded-xl h-auto p-1">
              <TabsTrigger value="escola" className="text-xs data-[state=active]:bg-roxo-principal data-[state=active]:text-white rounded-lg">Da escola</TabsTrigger>
              <TabsTrigger value="registros" className="text-xs data-[state=active]:bg-roxo-principal data-[state=active]:text-white rounded-lg">Registros</TabsTrigger>
              <TabsTrigger value="paee" className="text-xs data-[state=active]:bg-roxo-principal data-[state=active]:text-white rounded-lg">PAEE</TabsTrigger>
              <TabsTrigger value="resumo" className="text-xs data-[state=active]:bg-roxo-principal data-[state=active]:text-white rounded-lg">Resumo</TabsTrigger>
            </TabsList>

            {/* ABA DA ESCOLA */}
            <TabsContent value="escola" className="space-y-3 mt-4">
              <AnimatePresence mode="wait">
                {mostrandoRecado ? (
                  <motion.div key="recado" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                    <RecadoForm onEnviado={() => setMostrandoRecado(false)} onCancelar={() => setMostrandoRecado(false)} />
                  </motion.div>
                ) : (
                  <motion.div key="conteudo" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="space-y-3">
                    <button
                      onClick={() => setMostrandoRecado(true)}
                      className="block w-full text-center text-xs font-medium text-[#534AB7] bg-white border border-[#AFA9EC] rounded-lg py-2 hover:bg-[#EEEDFE] transition-colors"
                    >
                      Enviar estratégia para a professora →
                    </button>

                    <Card className="rounded-xl overflow-hidden">
                      <div className="px-4 py-2.5 border-b border-gray-100 flex items-center justify-between">
                        <span className="text-xs font-medium text-gray-500">Observações da professora</span>
                        <span className="text-[10px] text-gray-400">só leitura</span>
                      </div>
                      <CardContent className="p-0 divide-y divide-gray-100">
                        {carregandoRegistrosVoz ? (
                          <div className="flex items-center gap-2 text-xs text-gray-400 px-4 py-4">
                            <Loader2 className="h-3.5 w-3.5 animate-spin" />
                            Carregando observações…
                          </div>
                        ) : erroRegistrosVoz ? (
                          <p className="text-xs text-red-500 px-4 py-4">{erroRegistrosVoz}</p>
                        ) : registrosVoz.length === 0 ? (
                          <p className="text-xs text-gray-400 px-4 py-4">Nenhuma observação da professora ainda.</p>
                        ) : (
                          registrosVoz.map((o) => (
                            <div key={o.id} className="px-4 py-2.5 flex gap-2.5">
                              <div className="text-[10px] text-gray-400 w-12 flex-shrink-0 pt-0.5">
                                {formatarDataCurta(o.data_observacao || o.data_criacao)}
                              </div>
                              <div className="text-xs text-gray-600 leading-snug">{o.resumo}</div>
                            </div>
                          ))
                        )}
                      </CardContent>
                      {!carregandoRegistrosVoz && !erroRegistrosVoz && temMaisRegistros && (
                        <div className="px-4 py-3 border-t border-gray-100">
                          <Button
                            variant="outline"
                            size="sm"
                            className="w-full text-xs"
                            onClick={handleCarregarMais}
                            disabled={carregandoMaisRegistros}
                          >
                            {carregandoMaisRegistros ? (
                              <span className="flex items-center gap-1.5">
                                <Loader2 className="h-3.5 w-3.5 animate-spin" /> Carregando…
                              </span>
                            ) : (
                              'Ver Mais'
                            )}
                          </Button>
                        </div>
                      )}
                    </Card>
                  </motion.div>
                )}
              </AnimatePresence>
            </TabsContent>

            {/* ABA REGISTROS */}
            <TabsContent value="registros" className="space-y-3 mt-4">
              <p className="text-[11px] font-medium text-gray-500 uppercase tracking-wide">Histórico de atendimentos</p>
              <Card className="rounded-xl">
                <CardContent className="p-4">
                  <div className="text-[11px] text-gray-400 mb-1">01 de abril · Linguagem expressiva</div>
                  <p className="text-sm text-gray-600 leading-relaxed mb-2">
                    Nomeação: 9/10. <strong className="text-gray-800 font-medium">Primeira frase SVO espontânea</strong> registrada ao final da sessão.
                  </p>
                </CardContent>
              </Card>
              <Card className="rounded-xl">
                <CardContent className="p-4">
                  <div className="text-[11px] text-gray-400 mb-1">25 de março · Consciência fonológica</div>
                  <p className="text-sm text-gray-600 leading-relaxed">Rimas: 6/8 com apoio. Atenção: 20 min — melhor resultado.</p>
                </CardContent>
              </Card>
              <Button asChild className="w-full bg-roxo-principal hover:bg-[#6B4EA8] rounded-xl">
                <Link to={`/especialistas/crianca/${criancaId}/registrar`}>+ Novo registro</Link>
              </Button>
            </TabsContent>

            {/* ABA PAEE */}
            <TabsContent value="paee" className="space-y-2 mt-4">
              <p className="text-[11px] font-medium text-gray-500 uppercase tracking-wide mb-1">Metas do PAEE</p>

              {carregandoMetasPaee ? (
                <div className="flex items-center gap-2 text-sm text-gray-400 py-4">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Carregando metas…
                </div>
              ) : erroMetasPaee ? (
                <p className="text-sm text-red-500 py-2">{erroMetasPaee}</p>
              ) : metasPaee.length === 0 ? (
                <p className="text-sm text-gray-400 py-2">Nenhuma meta de PAEE cadastrada ainda.</p>
              ) : (
                metasPaee.map((m) => (
                  <MetaAccordion
                    key={m.id}
                    aberta={metaAberta === m.id}
                    onToggle={() => setMetaAberta(metaAberta === m.id ? null : m.id)}
                    titulo={m.objetivo}
                    statusLabel={m.status_label}
                    statusClasses={STATUS_META_CLASSES[m.status] || 'bg-gray-100 text-gray-600'}
                  >
                    <span className="text-[10px] font-medium px-2 py-0.5 rounded-full inline-block mb-2.5 bg-[#E6F1FB] text-[#0C447C]">
                      {m.categoria_label}
                    </span>
                    <div className="grid grid-cols-2 gap-1.5 mb-2.5">
                      <DetalheMeta label="Critério de sucesso" valor={m.criterio} />
                      <DetalheMeta label="Estratégia" valor={m.estrategia} />
                      <DetalheMeta label="Início" valor={formatarDataCurta(m.inicio)} />
                      <DetalheMeta label="Fim previsto" valor={formatarDataCurta(m.fim)} />
                      <DetalheMeta label="Status" valor={m.status_label} />
                      <DetalheMeta label="Atualizado" valor={formatarDataCurta(m.data_atualizacao)} />
                    </div>
                    <Button variant="outline" size="sm" className="w-full text-xs">
                      Ver metas
                    </Button>
                  </MetaAccordion>
                ))
              )}

              <Link
                to={`/especialistas/crianca/${criancaId}/paee/criar`}
                className="block text-center text-sm font-medium text-roxo-principal border-2 border-dashed border-gray-300 rounded-xl py-2.5 hover:border-roxo-principal transition-colors"
              >
                + Nova meta com IA
              </Link>
            </TabsContent>

            {/* ABA RESUMO */}
            <TabsContent value="resumo" className="space-y-3 mt-4">
              <Card className="rounded-xl overflow-hidden">
                <div className="bg-[#E1F5EE] border-b border-[#9FE1CB] px-4 py-2.5 flex items-center gap-2">
                  <span className="text-xs font-medium text-[#085041] flex-1">Resumo bimestral — seção 6 do relatório</span>
                  <span className="text-[10px] font-medium bg-[#1D9E75] text-white px-2 py-0.5 rounded-full">IA gerou</span>
                </div>
                <CardContent className="p-4">
                  <Textarea rows={6} value={resumoTexto} onChange={(e) => setResumoTexto(e.target.value)} className="text-sm" />
                  <p className="text-[11px] text-[#1D9E75] mt-1.5">✎ Edite livremente antes de ir para o relatório</p>
                </CardContent>
              </Card>
              <div className="bg-[#EEEDFE] border border-[#AFA9EC] rounded-lg p-3 text-xs text-[#3C3489] leading-relaxed">
                Este texto vai automaticamente para a <strong className="font-medium">seção 6</strong> do relatório de {crianca?.nome_completo || 'quando a professora gerar o relatório do bimestre'}.
              </div>
            </TabsContent>
          </Tabs>
          </div>
        </main>
      </div>
    </>
  );
}

function DetalheMeta({ label, valor }) {
  return (
    <div className="bg-[#F8F7FF] rounded-lg px-2.5 py-1.5">
      <div className="text-[10px] text-gray-500 font-medium mb-0.5">{label}</div>
      <div className="text-[11px] text-gray-800">{valor}</div>
    </div>
  );
}

function MetaAccordion({ aberta, onToggle, titulo, statusLabel, statusClasses, children }) {
  return (
    <Card className="rounded-xl overflow-hidden">
      <button onClick={onToggle} className="w-full bg-[#EEEDFE] px-4 py-3 flex items-center gap-2 text-left">
        <span className="text-xs font-medium text-[#534AB7] flex-1 truncate">{titulo}</span>
        {statusLabel && (
          <span className={`text-[10px] font-medium px-2 py-0.5 rounded-full flex-shrink-0 ${statusClasses}`}>{statusLabel}</span>
        )}
        <ChevronDown className={`h-4 w-4 text-[#AFA9EC] transition-transform flex-shrink-0 ${aberta ? 'rotate-180' : ''}`} />
      </button>
      {aberta && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="p-4">
          {children}
        </motion.div>
      )}
    </Card>
  );
}