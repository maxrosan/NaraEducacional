import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Helmet } from 'react-helmet-async';
import { Loader2, Mic, PenLine, ClipboardList, Volume2 } from 'lucide-react';
import { motion } from 'framer-motion';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { useEspecialistaLogado } from '@/hooks/useEspecialistaLogado';
import { useAuth } from '@/contexts/AuthContext';
import { capitalizarPalavras } from '@/lib/textFormat';
import ContribuicaoRelatorioCard from '@/components/specialist/ContribuicaoRelatorioCard';
import SpecialistNavbar from '@/components/specialist/SpecialistNavbar';
// TODO: confirme o nome real do helper de fetch autenticado usado no projeto
// (authFetch aparece em vários pontos do apiService — ajuste o import se o
// nome/local for diferente).
import { authFetch } from '@/services/api';

/**
 * Home da especialista.
 * Rota: /especialistas
 *
 * Usa o mesmo navbar padrão do sistema (SpecialistNavbar, espelhado do
 * ProfessorNavbar) em vez de um cabeçalho próprio — consistente com as
 * demais páginas de destino (dashboards) do app.
 *
 * "Suas crianças" agora vem da API real (GET /api/especialistas/minhas-criancas/),
 * que lista as crianças vinculadas ao especialista através da tabela SessaoEspecialista,
 * filtradas também pela turma selecionada na navbar (turmaAtiva do AuthContext
 * — mesmo estado que SpecialistNavbar usa no seletor de turma). Sem turma
 * selecionada, mostra todas as crianças do especialista.
 *
 * O bloco "Ligações da IA" ainda é estático — não existe endpoint para isso
 * hoje. Mantido como exemplo até a lógica ser implementada (ver // TODO).
 */

const AV_CLASSES = [
  'bg-[#E1F5EE] text-[#085041]',
  'bg-[#EEEDFE] text-[#534AB7]',
  'bg-[#E6F1FB] text-[#0C447C]',
];

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

function diasDesde(dataIso) {
  if (!dataIso) return null;
  const diffMs = Date.now() - new Date(dataIso).getTime();
  return Math.max(0, Math.floor(diffMs / 86400000));
}

function mapearCriancaParaCard(crianca, index) {
  const dias = diasDesde(crianca.ultima_sessao_em);
  const recente = dias !== null && dias <= 2;

  let info;
  if (dias === null) {
    info = `${crianca.sessoes_realizadas} sessão(ões) registrada(s) · nenhum atendimento ainda`;
  } else {
    info = `Última sessão: ${dias === 0 ? 'hoje' : `há ${dias} dia(s)`} · ${crianca.sessoes_realizadas} sessão(ões)`;
  }

  return {
    id: crianca.id,
    nome: crianca.nome_completo,
    iniciais: iniciaisDe(crianca.nome_completo),
    avClasses: AV_CLASSES[index % AV_CLASSES.length],
    info,
    badgeClasses: recente ? 'bg-[#E1F5EE] text-[#085041]' : 'bg-[#FCEBEB] text-[#791F1F]',
    badge: dias === null ? '—' : dias === 0 ? 'Hoje' : `${dias} dias`,
    novidade: recente,
  };
}

function formatarDataHora(dataIso) {
  if (!dataIso) return '';
  return new Date(dataIso).toLocaleString('pt-BR', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

const SpecialistHomePage = () => {
  const { especialista, loading } = useEspecialistaLogado();
  const { turmaAtiva } = useAuth();

  const [criancas, setCriancas] = useState([]);
  const [carregandoCriancas, setCarregandoCriancas] = useState(true);
  const [erroCriancas, setErroCriancas] = useState(null);

  useEffect(() => {
    if (!especialista?.id) return;

    let cancelado = false;
    setCarregandoCriancas(true);
    setErroCriancas(null);

    const params = new URLSearchParams({ especialista_id: especialista.id });
    if (turmaAtiva?.id) params.set('turma_id', turmaAtiva.id);

    authFetch(`/api/especialistas/minhas-criancas/?${params.toString()}`)
      .then((res) => {
        if (!res.ok) throw new Error('Falha ao buscar crianças do especialista');
        return res.json();
      })
      .then((data) => {
        if (cancelado) return;
        setCriancas(data.map(mapearCriancaParaCard));
      })
      .catch((err) => {
        if (cancelado) return;
        console.error(err);
        setErroCriancas('Não foi possível carregar suas crianças agora.');
      })
      .finally(() => {
        if (!cancelado) setCarregandoCriancas(false);
      });

    return () => {
      cancelado = true;
    };
  }, [especialista?.id, turmaAtiva?.id]);

  const [registrosVoz, setRegistrosVoz] = useState([]);
  const [carregandoRegistrosVoz, setCarregandoRegistrosVoz] = useState(true);
  const [erroRegistrosVoz, setErroRegistrosVoz] = useState(null);

  useEffect(() => {
    if (!especialista?.id) return;

    let cancelado = false;
    setCarregandoRegistrosVoz(true);
    setErroRegistrosVoz(null);

    const params = new URLSearchParams({ especialista_id: especialista.id, limite: '10' });
    if (turmaAtiva?.id) params.set('turma_id', turmaAtiva.id);

    authFetch(`/api/especialistas/registros-voz/?${params.toString()}`)
      .then((res) => {
        if (!res.ok) throw new Error('Falha ao buscar registros de voz');
        return res.json();
      })
      .then((data) => {
        if (cancelado) return;
        setRegistrosVoz(data.resultados);
      })
      .catch((err) => {
        if (cancelado) return;
        console.error(err);
        setErroRegistrosVoz('Não foi possível carregar os registros de voz agora.');
      })
      .finally(() => {
        if (!cancelado) setCarregandoRegistrosVoz(false);
      });

    return () => {
      cancelado = true;
    };
  }, [especialista?.id, turmaAtiva?.id]);

  if (loading) {
    return (
      <div className="flex justify-center items-center h-screen">
        <Loader2 className="h-8 w-8 animate-spin" />
      </div>
    );
  }

  return (
    <>
      <Helmet><title>NARA - Especialista</title></Helmet>
      <div className="bg-fundo-solido min-h-screen">
        <SpecialistNavbar />
      <main className="container mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
        {/* Saudação */}
        <div>
          <h1 className="text-2xl font-semibold">Bem-vinda de volta!</h1>
          <p className="text-muted-foreground text-sm">
            {especialista?.tipo_especialista ? capitalizarPalavras(especialista.tipo_especialista) : 'Especialista'}
          </p>
        </div>
        {/* Escolha de registro */}
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}>
          <Card className="bg-roxo-principal border-none rounded-2xl overflow-hidden">
            <CardContent className="p-5">
              <p className="text-sm font-medium text-white/80 mb-3">O que quer fazer agora?</p>
              <div className="grid grid-cols-3 gap-2">
                <QuickActionCard
                  to="/especialistas/registrar"
                  state={{ step: 'voz' }}
                  habilitado
                  Icone={Mic}
                  label="Por voz"
                  sublabel="IA transcreve e interpreta"
                />
                <QuickActionCard
                  to="/especialistas/registrar"
                  state={{ step: 'texto' }}
                  habilitado
                  Icone={PenLine}
                  label="Digitando"
                  sublabel="Escreva a observação"
                />
                <QuickActionCard
                  to="/especialistas/paee/criar"
                  habilitado
                  Icone={ClipboardList}
                  label="Criar PAEE"
                  sublabel="IA gera as metas"
                />
              </div>
            </CardContent>
          </Card>
        </motion.div>
        {/* Crianças */}
        <div>
          <p className="text-[11px] font-medium text-gray-500 uppercase tracking-wide mb-2">Suas crianças</p>
          {carregandoCriancas ? (
            <div className="flex items-center gap-2 text-sm text-gray-400 py-4">
              <Loader2 className="h-4 w-4 animate-spin" />
              Carregando crianças…
            </div>
          ) : erroCriancas ? (
            <p className="text-sm text-red-500 py-2">{erroCriancas}</p>
          ) : criancas.length === 0 ? (
            <p className="text-sm text-gray-400 py-2">Nenhuma criança vinculada ainda.</p>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {criancas.map((c) => (
                <Link
                  key={c.id}
                  to={`/especialistas/crianca/${c.id}`}
                  className="flex items-center gap-3 bg-white rounded-xl border border-gray-100 p-3 hover:border-roxo-principal transition-colors"
                >
                  <div className={`w-10 h-10 rounded-full flex items-center justify-center text-xs font-medium flex-shrink-0 ${c.avClasses}`}>
                    {c.iniciais}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1.5 text-sm font-medium text-gray-800">
                      {c.nome}
                      {c.novidade && <span className="w-1.5 h-1.5 rounded-full bg-[#E24B4A] inline-block" />}
                    </div>
                    <div className="text-[11px] text-gray-500 truncate">{c.info}</div>
                  </div>
                  <span className={`text-[11px] font-medium px-2.5 py-0.5 rounded-full flex-shrink-0 ${c.badgeClasses}`}>{c.badge}</span>
                </Link>
              ))}
            </div>
          )}
        </div>
        {/* Últimos registros de voz da professora (alunos acompanhados pelo especialista) */}
        <div>
          <p className="text-[11px] font-medium text-gray-500 uppercase tracking-wide mb-2">
            Últimos registros de voz da professora
          </p>
          <Card className="rounded-2xl border-gray-100 overflow-hidden">
            <CardContent className="p-0 divide-y divide-gray-100">
              {carregandoRegistrosVoz ? (
                <div className="flex items-center gap-2 text-sm text-gray-400 px-4 py-4">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Carregando registros…
                </div>
              ) : erroRegistrosVoz ? (
                <p className="text-sm text-red-500 px-4 py-4">{erroRegistrosVoz}</p>
              ) : registrosVoz.length === 0 ? (
                <p className="text-sm text-gray-400 px-4 py-4">Nenhum registro de voz encontrado ainda.</p>
              ) : (
                registrosVoz.map((r) => (
                  <div key={r.id} className="px-4 py-3 flex gap-3">
                    <Volume2 className="h-4 w-4 text-roxo-principal flex-shrink-0 mt-0.5" />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-xs font-medium text-gray-800">{r.aluno_nome}</span>
                        <span className="text-[10px] text-gray-400 flex-shrink-0">{formatarDataHora(r.data_criacao)}</span>
                      </div>
                      <p className="text-xs text-gray-600 leading-relaxed line-clamp-2 mt-0.5">{r.resumo}</p>
                      <p className="text-[10px] text-gray-400 mt-1">
                        {r.professora_nome} · {r.turma_nome || 'Turma não informada'}
                      </p>
                    </div>
                  </div>
                ))
              )}
            </CardContent>
          </Card>
          <Button
            asChild
            variant="outline"
            className="w-full mt-2 text-sm border-gray-200 text-gray-600 hover:text-roxo-principal hover:border-roxo-principal"
          >
            <Link to="/especialistas/registros-voz">Ver todos os registros</Link>
          </Button>
        </div>
        {/* Contribuição para o relatório bimestral (fluxo existente, mantido) */}
        {/* {especialista && <ContribuicaoRelatorioCard especialista={especialista} />} */}
      </main>
      </div>
    </>
  );
};

/**
 * Card de ação rápida da home. Quando não há uma criança válida ainda
 * (lista carregando ou vazia), renderiza como não-clicável em vez de um
 * <Link>, evitando montar uma URL com o segmento de criancaId vazio
 * (ex: "/especialistas/crianca//registrar", que o router acaba
 * reinterpretando de forma quebrada).
 */
function QuickActionCard({ to, state, habilitado, titulo, Icone, label, sublabel }) {
  const conteudo = (
    <>
      <Icone className="h-6 w-6 mx-auto mb-1 text-white" />
      <div className="text-xs font-medium text-white mb-0.5">{label}</div>
      <div className="text-[10px] text-white/65">{sublabel}</div>
    </>
  );

  if (!habilitado) {
    return (
      <div
        title={titulo}
        aria-disabled="true"
        className="rounded-xl bg-white/15 border border-white/20 p-3 text-center opacity-50 cursor-not-allowed"
      >
        {conteudo}
      </div>
    );
  }

  return (
    <Link
      to={to}
      state={state}
      className="rounded-xl bg-white/15 hover:bg-white/25 border border-white/20 transition-colors p-3 text-center"
    >
      {conteudo}
    </Link>
  );
}

export default SpecialistHomePage;