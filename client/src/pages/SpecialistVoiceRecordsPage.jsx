import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Helmet } from 'react-helmet-async';
import { ArrowLeft, Loader2, Search, RotateCcw, Volume2 } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useEspecialistaLogado } from '@/hooks/useEspecialistaLogado';
import { useAuth } from '@/contexts/AuthContext';
import SpecialistNavbar from '@/components/specialist/SpecialistNavbar';
// TODO: confirme o nome real do helper de fetch autenticado usado no projeto
import { authFetch } from '@/services/api';

const REGISTROS_POR_PAGINA = 20;

function formatarDataHora(dataIso) {
  if (!dataIso) return '';
  return new Date(dataIso).toLocaleString('pt-BR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

/**
 * Listagem completa dos registros de voz da professora (ObservacaoTranscricao),
 * restrita aos alunos acompanhados pelo especialista logado.
 * Rota sugerida: /especialistas/registros-voz
 *
 * Suporta busca textual (aluno, professora ou trecho do resumo), filtro por
 * intervalo de datas e paginação incremental ("Carregar mais").
 */
export default function SpecialistVoiceRecordsPage() {
  const navigate = useNavigate();
  const { especialista } = useEspecialistaLogado();
  const { turmaAtiva } = useAuth();

  const [busca, setBusca] = useState('');
  const [buscaAplicada, setBuscaAplicada] = useState('');
  const [dataInicio, setDataInicio] = useState('');
  const [dataFim, setDataFim] = useState('');

  const [registros, setRegistros] = useState([]);
  const [temMais, setTemMais] = useState(false);
  const [carregando, setCarregando] = useState(true);
  const [carregandoMais, setCarregandoMais] = useState(false);
  const [erro, setErro] = useState(null);

  const buscarRegistros = useCallback((offset, { isLoadMore = false } = {}) => {
    if (!especialista?.id) return;

    if (isLoadMore) setCarregandoMais(true);
    else setCarregando(true);
    setErro(null);

    const params = new URLSearchParams({
      especialista_id: especialista.id,
      limite: String(REGISTROS_POR_PAGINA),
      offset: String(offset),
    });
    if (turmaAtiva?.id) params.set('turma_id', turmaAtiva.id);
    if (buscaAplicada) params.set('busca', buscaAplicada);
    if (dataInicio) params.set('data_inicio', dataInicio);
    if (dataFim) params.set('data_fim', dataFim);

    authFetch(`/api/especialistas/registros-voz/?${params.toString()}`)
      .then((res) => {
        if (!res.ok) throw new Error('Falha ao buscar registros de voz');
        return res.json();
      })
      .then((data) => {
        setRegistros((anteriores) => (isLoadMore ? [...anteriores, ...data.resultados] : data.resultados));
        setTemMais(Boolean(data.tem_mais));
      })
      .catch((err) => {
        console.error(err);
        setErro('Não foi possível carregar os registros agora.');
      })
      .finally(() => {
        if (isLoadMore) setCarregandoMais(false);
        else setCarregando(false);
      });
  }, [especialista?.id, turmaAtiva?.id, buscaAplicada, dataInicio, dataFim]);

  // Refaz a busca do zero sempre que filtros aplicados ou turma mudarem
  useEffect(() => {
    buscarRegistros(0);
  }, [buscarRegistros]);

  // Busca reativa: aplica o texto digitado automaticamente após uma pequena
  // pausa (evita disparar uma requisição a cada tecla).
  useEffect(() => {
    const timeout = setTimeout(() => {
      setBuscaAplicada(busca.trim());
    }, 400);
    return () => clearTimeout(timeout);
  }, [busca]);

  const handleSubmitBusca = (e) => {
    e.preventDefault();
    // Aplica imediatamente, sem esperar o debounce (Enter ou clique na lupa).
    setBuscaAplicada(busca.trim());
  };

  const handleLimparFiltros = () => {
    setBusca('');
    setBuscaAplicada('');
    setDataInicio('');
    setDataFim('');
  };

  const filtrosAtivos = Boolean(buscaAplicada || dataInicio || dataFim);

  const handleCarregarMais = () => {
    buscarRegistros(registros.length, { isLoadMore: true });
  };

  return (
    <>
      <Helmet><title>NARA - Registros de voz</title></Helmet>
      <div className="bg-fundo-solido min-h-screen">
        <SpecialistNavbar />

        <main className="container mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="flex items-center gap-3 mb-4">
            <Button variant="ghost" size="icon" onClick={() => navigate(-1)}>
              <ArrowLeft className="h-5 w-5 text-gray-600" />
            </Button>
            <div className="flex-1 min-w-0">
              <h1 className="text-lg font-semibold text-gray-800 truncate">Registros de voz da professora</h1>
              <p className="text-xs text-gray-500 truncate">Alunos acompanhados por você</p>
            </div>
          </div>

          <div className="max-w-4xl mx-auto space-y-4">
            {/* Filtros */}
            <Card className="rounded-2xl">
              <CardContent className="p-3">
                <form onSubmit={handleSubmitBusca} className="flex items-center gap-2">
                  <div className="relative flex-1 min-w-0">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
                    <Input
                      value={busca}
                      onChange={(e) => setBusca(e.target.value)}
                      placeholder="Buscar por aluno, professora ou trecho do resumo…"
                      className="pl-9"
                    />
                  </div>
                  <Input
                    type="date"
                    value={dataInicio}
                    onChange={(e) => setDataInicio(e.target.value)}
                    aria-label="Data início"
                    className="w-[130px] sm:w-[150px] flex-shrink-0 text-xs sm:text-sm"
                  />
                  <Input
                    type="date"
                    value={dataFim}
                    onChange={(e) => setDataFim(e.target.value)}
                    aria-label="Data fim"
                    className="w-[130px] sm:w-[150px] flex-shrink-0 text-xs sm:text-sm"
                  />
                  <Button
                    type="button"
                    variant="outline"
                    size="icon"
                    onClick={handleLimparFiltros}
                    disabled={!filtrosAtivos && !busca}
                    className="flex-shrink-0"
                    title="Limpar filtros"
                  >
                    <RotateCcw className="h-4 w-4" />
                  </Button>
                </form>
              </CardContent>
            </Card>

            {/* Tabela */}
            <Card className="rounded-2xl overflow-hidden">
              {carregando ? (
                <div className="flex items-center gap-2 text-sm text-gray-400 px-4 py-8 justify-center">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Carregando registros…
                </div>
              ) : erro ? (
                <p className="text-sm text-red-500 px-4 py-8 text-center">{erro}</p>
              ) : registros.length === 0 ? (
                <p className="text-sm text-gray-400 px-4 py-8 text-center">
                  {filtrosAtivos ? 'Nenhum registro encontrado para esses filtros.' : 'Nenhum registro de voz encontrado ainda.'}
                </p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-gray-100 text-left">
                        <th className="px-4 py-2.5 text-[11px] font-medium text-gray-500 uppercase tracking-wide whitespace-nowrap">Data</th>
                        <th className="px-4 py-2.5 text-[11px] font-medium text-gray-500 uppercase tracking-wide whitespace-nowrap">Aluno</th>
                        <th className="px-4 py-2.5 text-[11px] font-medium text-gray-500 uppercase tracking-wide">Resumo</th>
                        <th className="px-4 py-2.5 text-[11px] font-medium text-gray-500 uppercase tracking-wide whitespace-nowrap">Professora</th>
                        <th className="px-4 py-2.5 text-[11px] font-medium text-gray-500 uppercase tracking-wide whitespace-nowrap">Turma</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {registros.map((r) => (
                        <tr key={r.id} className="align-top">
                          <td className="px-4 py-3 text-xs text-gray-500 whitespace-nowrap">
                            {formatarDataHora(r.data_criacao)}
                          </td>
                          <td className="px-4 py-3 text-xs font-medium text-gray-800 whitespace-nowrap">
                            <span className="flex items-center gap-1.5">
                              <Volume2 className="h-3.5 w-3.5 text-roxo-principal flex-shrink-0" />
                              {r.aluno_nome}
                            </span>
                          </td>
                          <td className="px-4 py-3 text-xs text-gray-600 leading-relaxed min-w-[280px]">{r.resumo}</td>
                          <td className="px-4 py-3 text-xs text-gray-500 whitespace-nowrap">{r.professora_nome}</td>
                          <td className="px-4 py-3 text-xs text-gray-500 whitespace-nowrap">{r.turma_nome || '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              {!carregando && !erro && temMais && (
                <div className="px-4 py-3 border-t border-gray-100">
                  <Button
                    variant="outline"
                    size="sm"
                    className="w-full text-xs"
                    onClick={handleCarregarMais}
                    disabled={carregandoMais}
                  >
                    {carregandoMais ? (
                      <span className="flex items-center gap-1.5">
                        <Loader2 className="h-3.5 w-3.5 animate-spin" /> Carregando…
                      </span>
                    ) : (
                      'Carregar mais'
                    )}
                  </Button>
                </div>
              )}
            </Card>
          </div>
        </main>
      </div>
    </>
  );
}