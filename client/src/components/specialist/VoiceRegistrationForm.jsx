import React, { useEffect, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Mic, Square, Loader2, Star, ArrowUp, CircleDot, Pencil, Check } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { useAuth } from '@/contexts/AuthContext';
// TODO: confirme o nome real do helper de fetch autenticado usado no projeto
import { authFetch } from '@/services/api';

/**
 * Passo "registro por voz" dentro do SpecialistRegistrationPage.
 *
 * Puramente visual: reproduz a simulação de gravação → transcrição →
 * interpretação da IA (setTimeout em cascata), sem gravação real nem
 * chamada de API. Quando a lógica de verdade for conectada, troque o
 * simulador por integração com /api/upload-audio/.
 *
 * @param {() => void} onSalvar - chamado quando o especialista confirma
 *   o registro; o pai decide o que fazer a seguir (ex: mostrar ligações).
 * @param {(aluno: {id: string, nome_completo: string} | null) => void} [onAlunoSelecionado]
 *   Chamado sempre que o aluno escolhido no select mudar, para que a página
 *   pai (que controla o cabeçalho "Registro por voz · Nome · hoje") possa
 *   exibir o nome do aluno realmente selecionado aqui, em vez do
 *   criancaId genérico da URL.
 */
const TRANSCRICAO =
  '"Trabalhamos nomeação de objetos com apoio de figuras temáticas. Vini acertou 9 de 10 — melhor resultado até agora, e ficou visivelmente animado. No final produziu uma frase espontânea completa com sujeito, verbo e objeto — inédito. Ainda hesita em dígrafos mas está tentando se autocorrigir. Atenção sustentada por 22 minutos — recorde."';

const NARRATIVA =
  'A sessão de hoje marcou um ponto de virada no desenvolvimento de Vini. A produção da primeira frase com sujeito, verbo e objeto de forma espontânea indica que a base lexical construída nas últimas sessões está começando a sustentar a estrutura sintática. O acerto de 9/10 na nomeação, acima de todas as sessões anteriores, reforça que o vocabulário funcional está consolidado. A atenção sustentada de 22 minutos é o maior tempo registrado.';

const LOADING_STEPS = [
  'Transcrevendo a gravação...',
  'Interpretando os dados clínicos...',
  'Gerando resumo da sessão...',
  'Atualizando metas do PAEE...',
];

export default function VoiceRegistrationForm({ onSalvar, onAlunoSelecionado }) {
  const { turmaAtiva } = useAuth();

  // --- Alunos da turma ativa, para o select antes de gravar ---
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

  // Avisa a página pai qual aluno está selecionado (para o cabeçalho refletir
  // o aluno real, não o criancaId genérico da URL).
  useEffect(() => {
    if (!onAlunoSelecionado) return;
    const aluno = alunos.find((a) => a.id === alunoId) || null;
    onAlunoSelecionado(aluno);
  }, [alunoId, alunos, onAlunoSelecionado]);

  // 'idle' | 'gravando' | 'processando' | 'pronto'
  const [estado, setEstado] = useState('idle');
  const [segundos, setSegundos] = useState(0);
  const [stepAtivo, setStepAtivo] = useState(-1);
  const [editandoTranscricao, setEditandoTranscricao] = useState(false);
  const [editandoResumo, setEditandoResumo] = useState(false);
  const [transcricao, setTranscricao] = useState(TRANSCRICAO);
  const [narrativa, setNarrativa] = useState(NARRATIVA);
  const [metas, setMetas] = useState({ p1: 90, p2: 45, p3: 80 });

  const intervalRef = useRef(null);
  const autoStopRef = useRef(null);

  useEffect(() => () => {
    clearInterval(intervalRef.current);
    clearTimeout(autoStopRef.current);
  }, []);

  function iniciarGravacao() {
    setEstado('gravando');
    setSegundos(0);
    intervalRef.current = setInterval(() => setSegundos((s) => s + 1), 1000);
    autoStopRef.current = setTimeout(pararGravacao, 6000); // demo: para sozinho
  }

  function pararGravacao() {
    clearInterval(intervalRef.current);
    clearTimeout(autoStopRef.current);
    setEstado('processando');
    setStepAtivo(0);
  }

  useEffect(() => {
    if (estado !== 'processando' || stepAtivo < 0) return;
    if (stepAtivo >= LOADING_STEPS.length) {
      const t = setTimeout(() => setEstado('pronto'), 400);
      return () => clearTimeout(t);
    }
    const t = setTimeout(() => setStepAtivo((s) => s + 1), 900);
    return () => clearTimeout(t);
  }, [estado, stepAtivo]);

  function regravar() {
    setEstado('idle');
    setStepAtivo(-1);
    setSegundos(0);
  }

  const min = Math.floor(segundos / 60);
  const seg = segundos % 60;
  const timerTexto = `${min}:${seg < 10 ? '0' : ''}${seg}`;

  return (
    <div className={estado === 'pronto' ? 'grid grid-cols-1 lg:grid-cols-2 gap-4 items-start' : 'max-w-xl mx-auto'}>
      <div className="space-y-4">
        {estado === 'idle' && (
          <Card className="rounded-2xl">
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
        )}

        <Card className="rounded-2xl">
          <CardContent className="p-6 text-center">
            <motion.button
              onClick={() => (estado === 'gravando' ? pararGravacao() : (estado === 'idle' || estado === 'pronto') && iniciarGravacao())}
              animate={estado === 'gravando' ? { boxShadow: ['0 0 0 0 rgba(226,75,74,.3)', '0 0 0 14px rgba(226,75,74,0)'] } : {}}
              transition={estado === 'gravando' ? { duration: 1.2, repeat: Infinity } : {}}
              className={`w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-3 ${
                estado === 'gravando' ? 'bg-[#E24B4A]' : estado === 'processando' ? 'bg-gray-100' : 'bg-[#EEEDFE]'
              }`}
            >
              {estado === 'gravando' && <Square className="h-6 w-6 text-white" />}
              {estado === 'processando' && <Loader2 className="h-6 w-6 text-gray-500 animate-spin" />}
              {(estado === 'idle' || estado === 'pronto') && <Mic className="h-7 w-7 text-roxo-principal" />}
            </motion.button>

            {estado === 'gravando' && (
              <div className="flex items-center justify-center gap-1 h-7 mb-1">
                {[0, 1, 2, 3, 4, 5].map((i) => (
                  <motion.span
                    key={i}
                    className="w-1 bg-[#E24B4A] rounded-full"
                    animate={{ height: [6, 22, 6] }}
                    transition={{ duration: 0.8, repeat: Infinity, delay: i * 0.08 }}
                  />
                ))}
              </div>
            )}

            <div className="text-base font-medium text-gray-800 mb-1">
              {estado === 'idle' && 'Toque para gravar'}
              {estado === 'gravando' && 'Gravando...'}
              {estado === 'processando' && 'Analisando a sessão...'}
              {estado === 'pronto' && 'Toque para regravar'}
            </div>
            {estado === 'idle' && <p className="text-xs text-gray-500">Fale como num prontuário oral — descreva a sessão com detalhes</p>}
            {estado === 'gravando' && <p className="text-xs text-gray-500">Fale com detalhes sobre o que aconteceu</p>}
            {estado === 'gravando' && <p className="text-sm font-medium text-[#E24B4A] mt-1.5">{timerTexto}</p>}
            {estado === 'gravando' && (
              <Button size="sm" className="mt-3 bg-[#E24B4A] hover:bg-[#c53f3e] rounded-full text-xs" onClick={pararGravacao}>
                Parar
              </Button>
            )}
          </CardContent>
        </Card>

        {estado === 'processando' && (
          <Card className="rounded-xl">
            <CardContent className="p-4 space-y-2">
              {LOADING_STEPS.map((label, i) => (
                <div key={label} className={`flex items-center gap-2.5 text-sm ${i < stepAtivo ? 'text-gray-800' : i === stepAtivo ? 'text-roxo-principal' : 'text-gray-300'}`}>
                  <span className={`w-2 h-2 rounded-full ${i < stepAtivo ? 'bg-[#1D9E75]' : i === stepAtivo ? 'bg-roxo-principal animate-pulse' : 'bg-gray-200'}`} />
                  {label}
                </div>
              ))}
            </CardContent>
          </Card>
        )}

        {estado === 'idle' && (
          <Card className="rounded-xl border-gray-100">
            <CardContent className="p-4">
              <p className="text-xs font-medium text-gray-800 mb-1">Fale com detalhes — a IA interpreta melhor</p>
              <p className="text-xs text-gray-500 leading-relaxed">
                "Trabalhamos rimas hoje, ela acertou 6 de 8. Ficou mais tranquila que na semana passada — fez contato visual comigo durante toda a atividade, o que é novo."
              </p>
            </CardContent>
          </Card>
        )}
      </div>

      <AnimatePresence>
        {estado === 'pronto' && (
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="space-y-4">
            <Card className="rounded-xl overflow-hidden">
              <div className="px-4 py-2.5 border-b border-gray-100 flex items-center justify-between">
                <span className="text-[11px] font-medium text-gray-500 uppercase tracking-wide">O que você disse</span>
                <button className="text-xs text-roxo-principal flex items-center gap-1" onClick={() => setEditandoTranscricao((v) => !v)}>
                  {editandoTranscricao ? <><Check className="h-3 w-3" /> Concluir</> : <><Pencil className="h-3 w-3" /> Editar</>}
                </button>
              </div>
              <CardContent className="p-4">
                {editandoTranscricao ? (
                  <Textarea rows={5} value={transcricao} onChange={(e) => setTranscricao(e.target.value)} className="text-sm italic" />
                ) : (
                  <p className="text-sm text-gray-600 leading-relaxed italic">{transcricao}</p>
                )}
              </CardContent>
            </Card>

            <Card className="rounded-2xl border-[#AFA9EC] overflow-hidden">
              <div className="bg-[#EEEDFE] px-4 py-3 flex items-center gap-2">
                <Star className="h-4 w-4 text-[#534AB7]" />
                <span className="text-sm font-medium text-[#534AB7] flex-1">Resumo interpretado pela NARA</span>
                <span className="text-[10px] font-medium bg-roxo-principal text-white px-2 py-0.5 rounded-full">IA</span>
              </div>
              <CardContent className="p-4">
                {editandoResumo ? (
                  <Textarea rows={7} value={narrativa} onChange={(e) => setNarrativa(e.target.value)} className="text-sm mb-3" />
                ) : (
                  <p className="text-sm text-gray-800 leading-relaxed mb-3.5">{narrativa}</p>
                )}

                <Insight tipo="mrc" icon={<Star className="h-4 w-4" />} label="Marco de desenvolvimento" texto="Primeira frase SVO espontânea registrada. Indica transição do estágio de nomeação para elaboração sintática." />
                <Insight tipo="pos" icon={<ArrowUp className="h-4 w-4" />} label="Avanço interpretado" texto="Autocorreção espontânea em dígrafos sugere que a consciência fonológica está começando a aparecer na fala espontânea." />
                <Insight tipo="atc" icon={<CircleDot className="h-4 w-4" />} label="Ponto de atenção" texto="Hesitação em dígrafos persiste em nomeação rápida. Próxima sessão: explorar dígrafos com apoio tátil." />

                <button
                  className="w-full mt-1.5 py-2 rounded-lg border border-[#AFA9EC] text-xs font-medium text-[#534AB7] flex items-center justify-center gap-1"
                  onClick={() => setEditandoResumo((v) => !v)}
                >
                  {editandoResumo ? <><Check className="h-3 w-3" /> Confirmar edição</> : <><Pencil className="h-3 w-3" /> Editar interpretação</>}
                </button>
              </CardContent>
            </Card>

            <Card className="rounded-2xl border-[#AFA9EC] bg-[#EEEDFE]">
              <CardContent className="p-4">
                <div className="flex items-center mb-2.5">
                  <span className="text-xs font-medium text-[#534AB7] flex-1">Atualização sugerida das metas</span>
                  <span className="text-[10px] text-roxo-principal font-medium">Calculado pela IA</span>
                </div>
                <MetaComparativo label="Nomeação de vocabulário" anterior={80} valor={metas.p1} onChange={(v) => setMetas((m) => ({ ...m, p1: v }))} />
                <MetaComparativo label="Linguagem expressiva (SVO)" anterior={20} valor={metas.p2} onChange={(v) => setMetas((m) => ({ ...m, p2: v }))} />
                <MetaComparativo label="Atenção sustentada" anterior={65} valor={metas.p3} onChange={(v) => setMetas((m) => ({ ...m, p3: v }))} semBorda />
                <p className="text-[11px] text-[#534AB7] mt-1">A IA calculou com base na sua fala · ajuste se precisar</p>
              </CardContent>
            </Card>

            <div className="flex flex-col sm:flex-row sm:justify-end gap-2">
              <Button variant="outline" className="order-2 sm:order-1 w-full sm:w-auto sm:px-8 rounded-xl" onClick={regravar}>Regravar</Button>
              <Button className="order-1 sm:order-2 w-full sm:w-auto sm:px-8 bg-roxo-principal hover:bg-[#6B4EA8] rounded-xl" onClick={onSalvar}>
                Salvar e ver ligações da IA
              </Button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function Insight({ tipo, icon, label, texto }) {
  const cores = {
    pos: { bg: 'bg-[#E1F5EE] border-[#9FE1CB]', label: 'text-[#085041]', texto: 'text-[#0F6E56]' },
    atc: { bg: 'bg-[#FAEEDA] border-[#EF9F27]', label: 'text-[#633806]', texto: 'text-[#854F0B]' },
    mrc: { bg: 'bg-[#EEEDFE] border-[#AFA9EC]', label: 'text-[#534AB7]', texto: 'text-[#3C3489]' },
  }[tipo];

  return (
    <div className={`rounded-lg p-3 flex gap-2.5 mb-2 border ${cores.bg}`}>
      <div className="flex-shrink-0">{icon}</div>
      <div>
        <div className={`text-[10px] font-medium uppercase tracking-wide mb-0.5 ${cores.label}`}>{label}</div>
        <div className={`text-xs leading-relaxed ${cores.texto}`}>{texto}</div>
      </div>
    </div>
  );
}

function MetaComparativo({ label, anterior, valor, onChange, semBorda }) {
  return (
    <div className={`py-2 ${semBorda ? '' : 'border-b border-[#534AB7]/15'}`}>
      <div className="flex justify-between items-center mb-1.5">
        <span className="text-xs font-medium text-[#3C3489]">{label}</span>
        <div className="flex items-center gap-1.5 text-xs">
          <span className="text-[#AFA9EC] line-through">{anterior}%</span>
          <span className="text-gray-500">→</span>
          <span className="font-medium text-roxo-principal">{valor}%</span>
        </div>
      </div>
      <input type="range" min={0} max={100} step={5} value={valor} onChange={(e) => onChange(Number(e.target.value))} className="w-full accent-[#7C5CBF]" />
    </div>
  );
}