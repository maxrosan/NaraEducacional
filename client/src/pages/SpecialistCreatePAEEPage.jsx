import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Helmet } from 'react-helmet-async';
import { ArrowLeft, Check, CheckCircle2, Sparkles } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { useEspecialistaLogado } from '@/hooks/useEspecialistaLogado';
import { useAuth } from '@/contexts/AuthContext';
import { capitalizarPalavras } from '@/lib/textFormat';
import SpecialistNavbar from '@/components/specialist/SpecialistNavbar';
// TODO: confirme o nome real do helper de fetch autenticado usado no projeto
import { authFetch } from '@/services/api';

const METAS_SUGERIDAS = [
  {
    id: 'm1',
    categoria: 'Linguagem expressiva',
    categoriaClasses: 'bg-[#EEEDFE] text-[#534AB7]',
    titulo: 'Iniciação verbal em contexto coletivo',
    criterio: 'Verbalizar em dupla 4x/semana',
    justificativa: 'Padrão de hesitação confirmado em 4 contextos — urgente.',
    selecionada: true,
  },
  {
    id: 'm2',
    categoria: 'Linguagem expressiva',
    categoriaClasses: 'bg-[#EEEDFE] text-[#534AB7]',
    titulo: 'Produção de frases com 3+ elementos (SVO)',
    criterio: 'Frase SVO espontânea em 3 sessões consecutivas',
    justificativa: 'Primeiro SVO registrado hoje — consolidar agora.',
    selecionada: true,
  },
  {
    id: 'm3',
    categoria: 'Consciência fonológica',
    categoriaClasses: 'bg-[#E6F1FB] text-[#0C447C]',
    titulo: 'Rimas sem apoio visual',
    criterio: '8/10 sem figuras de referência',
    justificativa: '75% com apoio — retirada gradual é o próximo passo.',
    selecionada: false,
  },
];

/**
 * Wizard de criação de PAEE com IA (4 etapas).
 * Rota: /especialistas/paee/criar
 *
 * O aluno é escolhido dentro da própria etapa 1 (select), não vem mais de
 * um criancaId na URL — mesmo padrão adotado em VoiceRegistrationForm e
 * TextRegistrationForm. Enquanto nenhum aluno é selecionado, a etapa 1
 * fica bloqueada (não dá pra avançar pras metas sugeridas sem saber de
 * quem são).
 *
 * Seleção/edição de metas fica em memória local — sem persistência real.
 */
export default function SpecialistCreatePAEEPage() {
  const navigate = useNavigate();
  const { especialista } = useEspecialistaLogado();
  const { turmaAtiva } = useAuth();
  const [etapa, setEtapa] = useState(1);
  const [metas, setMetas] = useState(METAS_SUGERIDAS);

  // --- Alunos da turma ativa, para o select da etapa 1 ---
  const [alunos, setAlunos] = useState([]);
  const [alunoId, setAlunoId] = useState('');
  const [carregandoAlunos, setCarregandoAlunos] = useState(true);
  const [erroAlunos, setErroAlunos] = useState(null);

  useEffect(() => {
    if (!turmaAtiva?.id) {
      setCarregandoAlunos(false);
      return;
    }

    let cancelado = false;
    setCarregandoAlunos(true);
    setErroAlunos(null);

    authFetch(`/api/criancas/?turma_id=${turmaAtiva.id}`)
      .then((res) => {
        if (!res.ok) throw new Error('Falha ao buscar alunos da turma');
        return res.json();
      })
      .then((data) => {
        if (cancelado) return;
        const lista = Array.isArray(data) ? data : data.results || [];
        setAlunos(lista);
      })
      .catch((err) => {
        if (cancelado) return;
        console.error(err);
        setErroAlunos('Não foi possível carregar os alunos da turma.');
      })
      .finally(() => {
        if (!cancelado) setCarregandoAlunos(false);
      });

    return () => {
      cancelado = true;
    };
  }, [turmaAtiva?.id]);

  const alunoSelecionado = alunos.find((a) => a.id === alunoId) || null;
  const nomeAluno = alunoSelecionado?.nome_completo || 'Selecione o aluno';

  const especialidade = especialista?.tipo_especialista ? capitalizarPalavras(especialista.tipo_especialista) : 'Fonoaudiologia';

  function toggleMeta(id) {
    setMetas((prev) => prev.map((m) => (m.id === id ? { ...m, selecionada: !m.selecionada } : m)));
  }

  function voltar() {
    if (etapa > 1) return setEtapa(etapa - 1);
    // Etapa 1 volta pra página anterior de verdade (histórico do navegador) —
    // pode ter vindo do perfil da criança, do fluxo de registro ou da home.
    navigate(-1);
  }

  const metasSelecionadas = metas.filter((m) => m.selecionada);

  return (
    <>
      <Helmet><title>NARA - Criar PAEE</title></Helmet>
      <div className="bg-[#F5F3FA] min-h-screen">
        <SpecialistNavbar />

        <main className="container mx-auto px-4 sm:px-6 lg:px-8 py-6">
          {/* Voltar + título — sempre na largura total do container */}
          <div className="flex items-center gap-3 mb-5">
            <Button variant="ghost" size="icon" onClick={voltar}>
              <ArrowLeft className="h-5 w-5 text-gray-600" />
            </Button>
            <div className="min-w-0">
              <h1 className="text-lg font-semibold text-gray-800 truncate">Criar PAEE{alunoSelecionado ? ` — ${alunoSelecionado.nome_completo}` : ''}</h1>
              <p className="text-xs text-gray-500 truncate">Plano de Atendimento Educacional Especializado · {especialidade}</p>
            </div>
          </div>

          {/* Conteúdo do wizard — largura própria, não afeta a posição do voltar acima */}
          <div className="max-w-2xl mx-auto">
          <div className="flex justify-center gap-1.5 mb-6">
            {[1, 2, 3, 4].map((n) => (
              <div
                key={n}
                className={`h-2 rounded-full transition-all ${
                  n === etapa ? 'w-5 bg-roxo-principal' : n < etapa ? 'w-2 bg-[#1D9E75]' : 'w-2 bg-gray-200'
                }`}
              />
            ))}
          </div>

          {/* ETAPA 1 */}
          {etapa === 1 && (
            <div className="space-y-4">
              <Card className="rounded-xl">
                <CardContent className="p-4">
                  <Label className="text-[11px] font-medium text-gray-500 uppercase tracking-wide">Aluno</Label>
                  <Select onValueChange={setAlunoId} value={alunoId} disabled={carregandoAlunos || !turmaAtiva?.id}>
                    <SelectTrigger className="mt-1.5 w-full bg-[#F8F7FF] text-sm">
                      <SelectValue
                        placeholder={
                          !turmaAtiva?.id
                            ? 'Selecione uma turma na navbar'
                            : carregandoAlunos
                            ? 'Carregando alunos…'
                            : erroAlunos
                            ? 'Erro ao carregar alunos'
                            : 'Selecione o aluno'
                        }
                      />
                    </SelectTrigger>
                    <SelectContent>
                      {alunos.map((aluno) => (
                        <SelectItem key={aluno.id} value={aluno.id}>
                          {aluno.nome_completo}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </CardContent>
              </Card>

              <div className="rounded-xl border border-[#AFA9EC] bg-[#EEEDFE] p-3.5">
                <div className="flex items-center gap-1.5 text-[11px] font-medium text-[#534AB7] uppercase tracking-wide mb-2.5">
                  <Sparkles className="h-3.5 w-3.5" /> NARA analisou — fontes usadas
                </div>
                <FonteItem cor="bg-roxo-principal" label="8 observações da professora:" texto="hesitação verbal em 4 contextos, dificuldade de pinça, interesse tátil" />
                <FonteItem cor="bg-[#1D9E75]" label="3 registros seus:" texto="evolução em rimas e nomeação, dificuldade de iniciação em grupo" />
                <FonteItem cor="bg-[#BA7517]" label="Análise de escrita:" texto="hipótese pré-silábica com grafismos intencionais" ultimo />
              </div>

              <Card className="rounded-xl">
                <CardContent className="p-4">
                  <div className="text-sm font-medium text-gray-800 mb-1.5">Perfil aprendente detectado</div>
                  <p className="text-xs text-gray-600 leading-relaxed">
                    Preferência tátil marcada, comunicação verbal funcional em contextos 1-a-1, hesitação em ambientes não estruturados com mais de 4 pessoas, interesse em categorização e padrões de cores.
                  </p>
                </CardContent>
              </Card>

              <Button
                className="w-full bg-roxo-principal hover:bg-[#6B4EA8] rounded-xl"
                onClick={() => setEtapa(2)}
                disabled={!alunoSelecionado}
              >
                Ver metas sugeridas →
              </Button>
            </div>
          )}

          {/* ETAPA 2 */}
          {etapa === 2 && (
            <div className="space-y-3">
              <p className="text-xs text-gray-500">Selecione as metas que fazem sentido — você edita depois.</p>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5">
                {metas.map((m) => (
                  <button
                    key={m.id}
                    onClick={() => toggleMeta(m.id)}
                    className={`text-left rounded-xl border-2 p-3.5 transition-colors relative ${
                      m.selecionada ? 'border-roxo-principal bg-[#f8f7ff]' : 'border-gray-200 bg-white'
                    }`}
                  >
                    <span
                      className={`absolute top-3.5 right-3.5 w-5 h-5 rounded-full border flex items-center justify-center ${
                        m.selecionada ? 'bg-roxo-principal border-transparent text-white' : 'border-gray-200'
                      }`}
                    >
                      {m.selecionada && <Check className="h-3 w-3" />}
                    </span>
                    <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded-full inline-block mb-1.5 ${m.categoriaClasses}`}>{m.categoria}</span>
                    <div className="text-sm font-medium text-gray-800 mb-1 pr-6">{m.titulo}</div>
                    <div className="text-[11px] text-gray-500 mb-1">Critério: {m.criterio}</div>
                    <div className="text-[11px] text-gray-400 italic">{m.justificativa}</div>
                  </button>
                ))}
              </div>

              <div className="flex gap-2 pt-2">
                <Button variant="outline" className="flex-1 rounded-xl" onClick={() => setEtapa(1)}>← Voltar</Button>
                <Button className="flex-[2] bg-roxo-principal hover:bg-[#6B4EA8] rounded-xl" onClick={() => setEtapa(3)}>Revisar metas →</Button>
              </div>
            </div>
          )}

          {/* ETAPA 3 */}
          {etapa === 3 && (
            <div className="space-y-3">
              <p className="text-xs text-gray-500">Edite se precisar — o que a IA sugeriu é um ponto de partida.</p>

              {metasSelecionadas.map((m) => (
                <Card className="rounded-xl" key={m.id}>
                  <CardContent className="p-4 space-y-3">
                    <span className={`text-[10px] font-medium px-2 py-0.5 rounded-full inline-block ${m.categoriaClasses}`}>{m.categoria}</span>
                    <div>
                      <Label className="text-[11px] font-medium text-gray-500 uppercase tracking-wide">Objetivo</Label>
                      <Textarea rows={2} defaultValue={m.titulo} className="mt-1 text-sm" />
                    </div>
                    <div>
                      <Label className="text-[11px] font-medium text-gray-500 uppercase tracking-wide">Critério de sucesso</Label>
                      <Textarea rows={2} defaultValue={m.criterio} className="mt-1 text-sm" />
                    </div>
                    <div>
                      <Label className="text-[11px] font-medium text-gray-500 uppercase tracking-wide">Estratégia principal</Label>
                      <Textarea rows={2} defaultValue="Definir estratégia com base na avaliação clínica" className="mt-1 text-sm" />
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <Label className="text-[11px] font-medium text-gray-500 uppercase tracking-wide">Prazo</Label>
                        <input defaultValue="Fim do 2º bimestre" className="mt-1 w-full rounded-lg border border-gray-200 bg-[#F8F7FF] px-2.5 py-1.5 text-xs" />
                      </div>
                      <div>
                        <Label className="text-[11px] font-medium text-gray-500 uppercase tracking-wide">Progresso inicial</Label>
                        <input defaultValue="0%" className="mt-1 w-full rounded-lg border border-gray-200 bg-[#F8F7FF] px-2.5 py-1.5 text-xs" />
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}

              <div className="flex gap-2">
                <Button variant="outline" className="flex-1 rounded-xl" onClick={() => setEtapa(2)}>← Voltar</Button>
                <Button className="flex-[2] bg-roxo-principal hover:bg-[#6B4EA8] rounded-xl" onClick={() => setEtapa(4)}>Salvar PAEE →</Button>
              </div>
            </div>
          )}

          {/* ETAPA 4 */}
          {etapa === 4 && (
            <div className="text-center py-8">
              <div className="w-16 h-16 rounded-full bg-[#E1F5EE] flex items-center justify-center mx-auto mb-4">
                <CheckCircle2 className="h-7 w-7 text-[#1D9E75]" />
              </div>
              <div className="text-lg font-medium text-gray-800 mb-1">PAEE criado com sucesso</div>
              <p className="text-sm text-gray-500 mb-1">{metasSelecionadas.length} metas ativas · {nomeAluno}</p>
              <p className="text-xs text-gray-500 mb-6">{especialidade} · 1º Bimestre 2026</p>

              <div className="rounded-lg border border-[#AFA9EC] bg-[#EEEDFE] p-3.5 text-left mb-5">
                <div className="text-xs font-medium text-[#534AB7] mb-1">Próximo passo</div>
                <p className="text-xs text-[#3C3489] leading-relaxed">Registre a primeira sessão para iniciar o acompanhamento do progresso das metas criadas.</p>
              </div>

              <div className="flex flex-col sm:flex-row sm:justify-center gap-2">
                <Button asChild className="w-full sm:w-auto sm:px-8 bg-roxo-principal hover:bg-[#6B4EA8] rounded-xl">
                  <Link to="/especialistas/registrar" state={{ step: 'voz' }}>Registrar primeira sessão</Link>
                </Button>
                {alunoSelecionado && (
                  <Button asChild variant="outline" className="w-full sm:w-auto sm:px-8 rounded-xl">
                    <Link to={`/especialistas/crianca/${alunoSelecionado.id}`}>Ver perfil completo</Link>
                  </Button>
                )}
              </div>
            </div>
          )}
          </div>
        </main>
      </div>
    </>
  );
}

function FonteItem({ cor, label, texto, ultimo }) {
  return (
    <div className={`bg-white rounded-lg px-3 py-2 flex gap-2 text-xs ${ultimo ? '' : 'mb-1.5'}`}>
      <div className={`w-1.5 h-1.5 rounded-full flex-shrink-0 mt-1 ${cor}`} />
      <div className="text-gray-600"><strong className="font-medium text-gray-800">{label}</strong> {texto}</div>
    </div>
  );
}