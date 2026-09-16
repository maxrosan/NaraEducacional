import React, { useState } from 'react';
import { Helmet } from 'react-helmet-async';
import { useNavigate, useParams } from 'react-router-dom';
import { motion } from 'framer-motion';
import { ArrowLeft, Save, Users, Check, MessageSquare } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useToast } from '@/components/ui/use-toast';
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/accordion';
import { Checkbox } from '@/components/ui/checkbox';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

const turmasData = {
  'turma-a': {
    name: 'Nível 2 - Manhã',
    students: [
      { id: '1', name: 'Júlia Almeida' },
      { id: '2', name: 'Beatriz Souza' },
      { id: '3', name: 'Emanuel Costa' },
      { id: '4', name: 'Ana Clara Dias' },
      { id: '5', name: 'Lucas Martins' },
      { id: '6', name: 'Mariana Pereira' },
    ],
  },
  'turma-b': {
    name: 'Nível 2 - Tarde',
    students: [
      { id: '7', name: 'Pedro Lima' },
      { id: '8', name: 'Davi Santos' },
      { id: '9', name: 'Laura Oliveira' },
      { id: '10', name: 'Sofia Rodrigues' },
      { id: '11', name: 'Miguel Ferreira' },
      { id: '12', name: 'Heitor Gonçalves' },
    ],
  },
};

const observationData = {
  'O eu, o outro e o nós': {
    color: 'bg-purple-100 text-purple-800',
    questions: [
      { id: 'eo01', text: 'Demonstrou iniciativa para brincar com os colegas?' },
      { id: 'eo02', text: 'Identificou seus pertences (mochila, lancheira, copo...) sem ajuda?' },
      { id: 'eo03', text: 'Expressou suas vontades com clareza?' },
      { id: 'eo04', text: 'Participou de atividades coletivas com cooperação?' },
      { id: 'eo05', text: 'Conseguiu esperar sua vez em situações de grupo?' },
    ],
  },
  'Escuta, fala, pensamento e imaginação': {
    color: 'bg-yellow-100 text-yellow-800',
    questions: [
      { id: 'ef01', text: 'Participou de uma conversa, ouviu e respondeu de forma significativa?' },
      { id: 'ef02', text: 'Fez perguntas ou comentou sobre o que ouviu?' },
      { id: 'ef03', text: 'Nomeou objetos, pessoas ou sentimentos espontaneamente?' },
      { id: 'ef04', text: 'Compreendeu instruções simples do dia a dia?' },
      { id: 'ef05', text: 'Narrou algo que viveu ou imaginou?' },
    ],
  },
  'Corpo, gestos e movimentos': {
    color: 'bg-green-100 text-green-800',
    questions: [
      { id: 'cg01', text: 'Movimentou-se com autonomia em uma atividade física ou lúdica?' },
      { id: 'cg02', text: 'Pulou, correu ou se equilibrou com segurança?' },
      { id: 'cg03', text: 'Explorou diferentes formas de se movimentar (rolar, engatinhar, subir...)?' },
      { id: 'cg04', text: 'Participou com interesse de jogos corporais ou circuitos?' },
      { id: 'cg05', text: 'Demonstrou coordenação ao empilhar, encaixar ou montar?' },
    ],
  },
  'Traços, sons, cores e formas': {
    color: 'bg-blue-100 text-blue-800',
    questions: [
      { id: 'ts01', text: 'Explorou tintas, lápis, giz ou outros materiais gráficos com intenção?' },
      { id: 'ts02', text: 'Participou de uma atividade de música com gestos ou cantando?' },
      { id: 'ts03', text: 'Construiu ou modelou com massinha, areia ou argila?' },
      { id: 'ts04', text: 'Demonstrou preferência por cores, formas ou materiais específicos?' },
      { id: 'ts05', text: 'Participou de encenações, dramatizações ou brincadeiras simbólicas?' },
    ],
  },
  'Espaços, tempos, quantidades, relações e transformações': {
    color: 'bg-orange-100 text-orange-800',
    questions: [
      { id: 'et01', text: 'Identificou cores, formas ou tamanhos durante as atividades?' },
      { id: 'et02', text: 'Usou expressões como “mais”, “grande”, “pequeno”, “acabou”, “tem dois”...?' },
      { id: 'et03', text: 'Reconheceu partes do corpo, objetos da rotina ou animais?' },
      { id: 'et04', text: 'Demonstrou noção de antes/depois, perto/longe, dentro/fora...?' },
      { id: 'et05', text: 'Explorou o espaço escolar com curiosidade e segurança?' },
    ],
  },
};

const QuestionItem = ({ question, students, selections, onToggleStudent }) => {
  const { toast } = useToast();
  const handleComment = () => {
    toast({
      title: "🚧 Funcionalidade em desenvolvimento",
      description: "A opção de adicionar comentários individuais estará disponível em breve.",
    });
  };

  return (
    <div className="bg-white p-4 rounded-xl border border-gray-100 mb-3">
      <p className="font-semibold text-gray-700 mb-4">{question.text}</p>
      <div className="space-y-3">
        {students.map(student => (
          <div key={student.id} className="flex items-center justify-between">
            <Label htmlFor={`${question.id}-${student.id}`} className="flex items-center cursor-pointer">
              <Checkbox
                id={`${question.id}-${student.id}`}
                checked={selections.includes(student.id)}
                onCheckedChange={() => onToggleStudent(question.id, student.id)}
                className="h-5 w-5"
              />
              <span className="ml-3 text-gray-600">{student.name}</span>
            </Label>
            <Button variant="ghost" size="icon" className="h-8 w-8" onClick={handleComment}>
              <MessageSquare className="h-4 w-4 text-gray-400" />
            </Button>
          </div>
        ))}
      </div>
    </div>
  );
};

function GuidedObservationPage() {
  const navigate = useNavigate();
  const { turmaId } = useParams();
  const { toast } = useToast();
  const [selections, setSelections] = useState({});

  const turma = turmasData[turmaId];

  if (!turma) {
    return <div>Turma não encontrada.</div>;
  }

  const handleToggleStudent = (questionId, studentId) => {
    setSelections(prev => {
      const currentQuestionSelections = prev[questionId] || [];
      const newSelections = currentQuestionSelections.includes(studentId)
        ? currentQuestionSelections.filter(id => id !== studentId)
        : [...currentQuestionSelections, studentId];
      return { ...prev, [questionId]: newSelections };
    });
  };

  const handleSave = () => {
    toast({
      title: '✅ Registro salvo com sucesso!',
      description: 'As observações já estão sendo processadas na trajetória das crianças.',
      className: 'bg-green-100 border-green-300 text-green-800',
    });
    setTimeout(() => navigate('/home-professor'), 2000);
  };

  return (
    <>
      <Helmet>
        <title>NARA - Registro Guiado</title>
        <meta name="description" content="Realize o registro de observação guiado por perguntas." />
      </Helmet>

      <div className="bg-[#F5F3FA] min-h-screen">
        <header className="sticky top-0 bg-white/80 backdrop-blur-sm z-10 shadow-sm">
          <div className="container mx-auto px-4 sm:px-6 lg:px-8 py-4 flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Button variant="ghost" size="icon" onClick={() => navigate(-1)}>
                <ArrowLeft className="h-6 w-6 text-gray-600" />
              </Button>
              <h1 className="text-xl font-bold text-gray-800">Registro Guiado</h1>
            </div>
            <img alt="NARA icon logo" className="h-12 w-auto sm:h-14" src="/nara-logo.png" />
          </div>
        </header>

        <main className="container mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
          >
            <Card className="mb-6">
              <CardHeader>
                <CardTitle className="flex items-center gap-3">
                  <Users className="h-6 w-6 text-purple-600" />
                  <span>{turma.name}</span>
                </CardTitle>
              </CardHeader>
            </Card>

            <Accordion type="multiple" defaultValue={Object.keys(observationData)} className="w-full space-y-4">
              {Object.entries(observationData).map(([field, data]) => (
                <AccordionItem key={field} value={field} className="bg-white p-4 rounded-2xl shadow-md border border-gray-100">
                  <AccordionTrigger>
                    <span className={`px-3 py-1 rounded-full text-sm font-semibold ${data.color}`}>{field}</span>
                  </AccordionTrigger>
                  <AccordionContent className="pt-4">
                    {data.questions.map(q => (
                      <QuestionItem
                        key={q.id}
                        question={q}
                        students={turma.students}
                        selections={selections[q.id] || []}
                        onToggleStudent={handleToggleStudent}
                      />
                    ))}
                  </AccordionContent>
                </AccordionItem>
              ))}
            </Accordion>

            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.2 }}
              className="mt-8 flex justify-center"
            >
              <Button
                size="lg"
                className="bg-[#8A63D2] hover:bg-[#7755b5] text-white font-bold rounded-full w-full max-w-md btn-hover shadow-lg"
                onClick={handleSave}
              >
                <Save className="h-5 w-5 mr-2" />
                Finalizar e Salvar Registro
              </Button>
            </motion.div>
          </motion.div>
        </main>
      </div>
    </>
  );
}

export default GuidedObservationPage;
