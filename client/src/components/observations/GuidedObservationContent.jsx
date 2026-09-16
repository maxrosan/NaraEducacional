import React, { useMemo } from 'react';
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/accordion';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Step } from '@/components/observations/Step';
import { Loader2, BookOpen, Users, MessageCircle, ToyBrick, Palette, Shapes, Info } from 'lucide-react';

const iconsMap = { Users, MessageCircle, ToyBrick, Palette, Shapes, BookOpen };
const campoExperienciaMap = {
  'O eu, o outro e o nós': { icon: 'Users', name: 'O eu, o outro e o nós' },
  'Escuta, fala, pensamento e imaginação': { icon: 'MessageCircle', name: 'Escuta, fala, pensamento e imaginação' },
  'Corpo, gestos e movimentos': { icon: 'ToyBrick', name: 'Corpo, gestos e movimentos' },
  'Traços, sons, cores e formas': { icon: 'Palette', name: 'Traços, sons, cores e formas' },
  'Espaços, tempos, quantidades, relações e transformações': { icon: 'Shapes', name: 'Espaços, tempos, quantidades...' },
};

const MAX_MARCACOES = 3;

//INICIO - essa função não está mais sendo utilizada
const getShortName = (fullName) => {
  if (!fullName) return '';
  const names = fullName.split(' ');
  return names.slice(0, 2).join(' ');
};
//FIM - essa função não está mais sendo utilizada

const StudentCountChip = ({ count, name, onCycle }) => {
  const marked = count > 0;
  return (
    <button
      type="button"
      onClick={onCycle}
      aria-label={
        marked
          ? `${name}, ${count} marcação${count > 1 ? 'es' : ''}. Toque para adicionar mais uma (volta a zero após ${MAX_MARCACOES}).`
          : `${name}. Toque para marcar.`
      }
      className={`flex items-center w-full text-left rounded-md px-2 py-1.5 transition-colors focus:outline-none focus:ring-2 focus:ring-roxo-principal/40 ${
        marked ? 'bg-roxo-principal/10' : 'hover:bg-white/60'
      }`}
    >
      <span
        aria-hidden="true"
        className={`flex items-center justify-center shrink-0 h-5 w-5 rounded-full border-2 text-[10px] font-bold transition-colors ${
          marked
            ? 'bg-roxo-principal border-roxo-principal text-white'
            : 'border-roxo-principal/60 text-transparent'
        }`}
      >
        {marked ? `${count}x` : ''}
      </span>
      <span className="ml-2 text-sm text-texto-medio">{name}</span>
    </button>
  );
};

export const GuidedObservationContent = ({ loading, questions, alunos, selections, setSelections, initialCounts = {}, comments, setComments, generalComment, setGeneralComment }) => {
  const groupedQuestions = useMemo(() => {
    if (!questions) return {};
    return questions.reduce((acc, q) => {
      const campo = q.campo_experiencia;
      if (!acc[campo]) acc[campo] = [];
      acc[campo].push(q);
      return acc;
    }, {});
  }, [questions]);

  const handleCycleStudent = (questionId, studentId) => {
    setSelections(prev => {
      const currentCounts = { ...(prev[questionId] || {}) };
      const current = currentCounts[studentId] || 0;
      const floor = initialCounts?.[questionId]?.[studentId] || 0;
      const next = current < MAX_MARCACOES ? current + 1 : floor;
      if (next === current) return prev;
      if (next === 0) delete currentCounts[studentId];
      else currentCounts[studentId] = next;
      return { ...prev, [questionId]: currentCounts };
    });
  };

  const handleCommentChange = (field, value) => {
    setComments(prev => ({ ...prev, [field]: value }));
  };

  return (
    <>
      <div
        role="note"
        className="mb-6 flex items-start gap-3 rounded-xl border border-roxo-principal/20 bg-lavanda-claro p-4 text-sm text-texto-escuro"
      >
        <Info className="h-5 w-5 shrink-0 text-roxo-principal mt-0.5" aria-hidden="true" />
        <div>
          <p className="font-semibold text-roxo-principal">Como marcar várias vezes</p>
          <p className="mt-1 text-texto-medio">
            O número ao lado da criança mostra quantas vezes você já a marcou nesta pergunta
            no período avaliativo atual. Toque para adicionar uma marcação
            (<span className="font-semibold">1x → 2x → 3x</span>) até o limite de{' '}
            <span className="font-semibold">{MAX_MARCACOES}x</span>. Marcações já salvas em
            envios anteriores não podem ser desfeitas por aqui — o contador volta no mínimo
            ao valor já registrado. Não precisa salvar várias vezes: tudo o que for novo é
            enviado em uma única submissão.
          </p>
        </div>
      </div>
      <Step title="Registro por pergunta" icon={<BookOpen className="h-5 w-5" />}>
        {loading ? (
          <div className="flex justify-center items-center p-8"><Loader2 className="h-8 w-8 animate-spin text-roxo-principal" /></div>
        ) : Object.keys(groupedQuestions).length > 0 ? (
          <Accordion type="multiple" defaultValue={[]} className="w-full">
            {Object.entries(groupedQuestions).map(([campo, qs]) => {
              const IconComponent = iconsMap[campoExperienciaMap[campo]?.icon] || BookOpen;
              return (
                <AccordionItem key={campo} value={campo}>
                  <AccordionTrigger className="text-lg font-bold text-roxo-principal hover:no-underline">
                    <div className="flex items-center gap-3"><IconComponent className="h-6 w-6" /> {campoExperienciaMap[campo]?.name || campo}</div>
                  </AccordionTrigger>
                  <AccordionContent>
                    <div className="space-y-4 pl-2">
                      {qs.map(q => (
                        <div key={q.id} className="bg-lavanda-claro p-4 rounded-lg">
                          <p className="font-semibold text-texto-escuro mb-3">{q.pergunta}</p>
                          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                            {alunos.map(aluno => (
                              <StudentCountChip
                                key={aluno.id}
                                name={aluno.nome_completo}
                                count={selections[q.id]?.[aluno.id] || 0}
                                onCycle={() => handleCycleStudent(q.id, aluno.id)}
                              />
                            ))}
                          </div>
                        </div>
                      ))}
                      {/* <div className="mt-4">
                        <Label className="font-semibold text-gray-600">Comentário sobre este campo (opcional)</Label>
                        <Textarea
                          className="mt-2 bg-white"
                          placeholder={`Adicione uma anotação sobre "${campoExperienciaMap[campo]?.name || campo}"...`}
                          value={comments[campo] || ''}
                          onChange={(e) => handleCommentChange(campo, e.target.value)}
                        />
                      </div> */}
                    </div>
                  </AccordionContent>
                </AccordionItem>
              );
            })}
          </Accordion>
        ) : (
            <div className="text-center text-gray-500 p-8">
                <p>Nenhuma pergunta da BNCC encontrada para a faixa etária desta turma.</p>
                <p className="text-sm mt-2">Verifique se a faixa etária da turma está correta e se existem perguntas cadastradas para ela.</p>
            </div>
        )}
      </Step>
      {/* <Step title="Observações Gerais" icon={<BookOpen className="h-5 w-5" />}>
        <Label className="font-semibold text-gray-600">Observações gerais da semana (opcional)</Label>
        <Textarea
            className="mt-2 bg-white"
            placeholder="Anote aqui qualquer evento, avanço ou ponto de atenção geral sobre a turma nesta semana..."
            value={generalComment}
            onChange={(e) => setGeneralComment(e.target.value)}
        />
      </Step> */}
    </>
  );
};
