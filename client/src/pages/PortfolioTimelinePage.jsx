import React, { useState } from 'react';
import { Helmet } from 'react-helmet-async';
import { useNavigate, useParams } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  ArrowLeft, FileText, Search, Calendar, Filter, BrainCircuit, Mic, FileImage, Type, Video, Edit, Recycle, CheckCircle, LayoutGrid
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useToast } from '@/components/ui/use-toast';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';

const studentData = {
  '1': {
    name: 'Júlia',
    turma: 'Maternal II - A',
    age: '3 anos e 2 meses',
    records: [
      {
        id: 'rec1',
        date: '2025-07-10',
        type: 'writing',
        title: 'Primeiras letras',
        content: 'Escrita na fase silábico-alfabética, com uso de letras reconhecíveis e tentativa de separar palavras.',
        mediaUrl: 'https://storage.googleapis.com/hostinger-horizons-assets-prod/images_for_nara/writing_sample.png',
        inReport: true,
      },
      {
        id: 'rec2',
        date: '2025-07-09',
        type: 'drawing',
        title: 'Desenho da família',
        content: 'Desenho com figura humana completa, uso de cores variadas e organização espacial desenvolvida.',
        mediaUrl: 'https://storage.googleapis.com/hostinger-horizons-assets-prod/images_for_nara/drawing_sample.png',
        inReport: false,
      },
      {
        id: 'rec3',
        date: '2025-07-08',
        type: 'audio',
        title: 'Observação livre',
        content: 'Júlia participou ativamente da contação de história, recontando um trecho para os colegas.',
        inReport: true,
      },
      {
        id: 'rec4',
        date: '2025-07-07',
        type: 'guided',
        title: 'Interação com colegas',
        content: 'Demonstrou iniciativa para brincar com os colegas durante a atividade no parque.',
        inReport: false,
      },
       {
        id: 'rec5',
        date: '2025-07-06',
        type: 'video',
        title: 'Roda de conversa',
        content: 'Vídeo da roda de conversa sobre os animais da fazenda.',
        inReport: false,
      },
    ],
  },
};

const recordIcons = {
  writing: <Type className="h-5 w-5 text-white" />,
  drawing: <FileImage className="h-5 w-5 text-white" />,
  audio: <Mic className="h-5 w-5 text-white" />,
  guided: <FileText className="h-5 w-5 text-white" />,
  video: <Video className="h-5 w-5 text-white" />,
};

const recordColors = {
  writing: 'bg-blue-400',
  drawing: 'bg-orange-400',
  audio: 'bg-purple-500',
  guided: 'bg-green-500',
  video: 'bg-red-500',
};

const RecordCard = ({ record, onAction }) => (
  <motion.div 
    layout
    initial={{ opacity: 0, y: 20 }}
    animate={{ opacity: 1, y: 0 }}
    exit={{ opacity: 0, y: -10 }}
    transition={{ duration: 0.3 }}
    className="bg-white rounded-2xl shadow-md border border-gray-100 overflow-hidden"
  >
    <div className="p-4">
      <div className="flex justify-between items-start mb-3">
        <div className="flex items-center gap-3">
           <div className={`p-2 rounded-full ${recordColors[record.type]}`}>
            {recordIcons[record.type]}
          </div>
          <div>
            <p className="font-bold text-gray-800">{record.title}</p>
            <p className="text-xs text-gray-500">{new Date(record.date).toLocaleDateString('pt-BR', { day: '2-digit', month: 'long', year: 'numeric' })}</p>
          </div>
        </div>
        {record.inReport && <div className="flex items-center gap-1 text-xs text-green-600 bg-green-100 px-2 py-1 rounded-full">
            <CheckCircle className="h-3 w-3" />
            <span>No relatório</span>
        </div>}
      </div>
      {record.mediaUrl && <img  class="rounded-lg w-full h-auto mb-3" alt={record.title} src="https://images.unsplash.com/photo-1673872094188-fd5b921cd0fb" />}
      <p className="text-sm text-gray-600 flex items-start gap-2">
        <BrainCircuit className="h-4 w-4 text-[#8A63D2] mt-0.5 shrink-0" />
        <span>{record.content}</span>
      </p>
    </div>
    <div className="bg-gray-50 px-4 py-2 flex justify-end gap-2">
      <Button variant="ghost" size="sm" onClick={() => onAction('edit')}>
        <Edit className="h-4 w-4 mr-1" /> Editar
      </Button>
      <Button variant="ghost" size="sm" onClick={() => onAction('reuse')}>
        <Recycle className="h-4 w-4 mr-1" /> Reutilizar
      </Button>
    </div>
  </motion.div>
);

function PortfolioTimelinePage() {
  const { studentId } = useParams();
  const navigate = useNavigate();
  const { toast } = useToast();
  
  const student = studentData[studentId];
  
  const [filterType, setFilterType] = useState('all');
  const [searchTerm, setSearchTerm] = useState('');

  const handleAction = (action) => {
    toast({
      title: '🚧 Em breve!',
      description: `A funcionalidade de "${action}" ainda não foi implementada.`,
    });
  };

  const handleGenerateReport = () => {
    navigate(`/relatorios/${studentId}`);
  };
  
  if (!student) {
    return <div>Criança não encontrada.</div>;
  }
  
  const filteredRecords = student.records.filter(record => {
    const typeMatch = filterType === 'all' || record.type === filterType;
    const searchMatch = searchTerm === '' || record.title.toLowerCase().includes(searchTerm.toLowerCase()) || record.content.toLowerCase().includes(searchTerm.toLowerCase());
    return typeMatch && searchMatch;
  });

  return (
    <>
      <Helmet>
        <title>NARA - Linha do Tempo de {student.name}</title>
        <meta name="description" content={`Acompanhe a jornada de aprendizagem de ${student.name}.`} />
      </Helmet>

      <div className="bg-[#F5F3FA] min-h-screen">
        <header className="sticky top-0 bg-white/80 backdrop-blur-sm z-20 shadow-sm">
          <div className="container mx-auto px-4 sm:px-6 lg:px-8 py-4 flex items-center justify-between">
            <div className="flex items-center gap-2 sm:gap-4">
              <Button variant="ghost" size="icon" onClick={() => navigate(-1)}>
                <ArrowLeft className="h-6 w-6 text-gray-600" />
              </Button>
              <div>
                 <h1 className="text-lg sm:text-xl font-bold text-gray-800">{student.name}</h1>
                 <p className="text-xs sm:text-sm text-gray-500">{student.turma}</p>
              </div>
            </div>
             <div className="flex items-center gap-2">
              <Button variant="ghost" size="icon" onClick={() => navigate(`/portfolio/${studentId}`)} title="Ver galeria de mídias">
                <LayoutGrid className="h-5 w-5 text-gray-600" />
              </Button>
              <Button className="nara-gradient text-white btn-hover" onClick={handleGenerateReport}>
                <FileText className="h-4 w-4 mr-0 sm:mr-2" />
                <span className="hidden sm:inline">Gerar Relatório</span>
              </Button>
              <img  alt="NARA icon logo" className="h-12 w-auto hidden sm:block sm:h-14" src="/nara-logo.png" />
            </div>
          </div>
        </header>

        <main className="container mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <motion.div 
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-white p-6 rounded-2xl shadow-lg border border-gray-100 mb-8 grid grid-cols-2 md:grid-cols-4 gap-4 text-center"
          >
            <div>
              <p className="text-sm text-gray-500">Idade</p>
              <p className="font-bold text-gray-800">{student.age}</p>
            </div>
            <div>
              <p className="text-sm text-gray-500">Período</p>
              <p className="font-bold text-gray-800">Bimestre 2</p>
            </div>
            <div>
              <p className="text-sm text-gray-500">Último Registro</p>
              <p className="font-bold text-gray-800">{new Date(student.records[0].date).toLocaleDateString('pt-BR')}</p>
            </div>
            <div>
              <p className="text-sm text-gray-500">Total de Registros</p>
              <p className="font-bold text-gray-800">{student.records.length} observações</p>
            </div>
          </motion.div>

          <div className="bg-white p-4 rounded-2xl shadow-lg border border-gray-100 mb-8 sticky top-[80px] z-10">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="relative">
                <Input placeholder="Buscar por palavra-chave..." className="pl-10" onChange={(e) => setSearchTerm(e.target.value)} />
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-gray-400" />
              </div>
              <Select onValueChange={setFilterType} defaultValue="all">
                  <SelectTrigger>
                      <Filter className="h-4 w-4 mr-2 text-gray-400"/>
                      <SelectValue placeholder="Filtrar por tipo"/>
                  </SelectTrigger>
                  <SelectContent>
                      <SelectItem value="all">Todos os tipos</SelectItem>
                      <SelectItem value="writing">Escrita</SelectItem>
                      <SelectItem value="drawing">Desenho</SelectItem>
                      <SelectItem value="audio">Observação (Áudio)</SelectItem>
                      <SelectItem value="guided">Observação (Guiada)</SelectItem>
                      <SelectItem value="video">Vídeo</SelectItem>
                  </SelectContent>
              </Select>
              <Button variant="outline" onClick={() => handleAction('filtrar por período')}>
                <Calendar className="h-4 w-4 mr-2" />
                Filtrar por período
              </Button>
            </div>
          </div>
          
          <div className="relative">
            <div className="absolute left-4 h-full w-0.5 bg-gray-200"></div>
            <div className="space-y-8 pl-10">
              <AnimatePresence>
                {filteredRecords.map(record => (
                  <RecordCard key={record.id} record={record} onAction={handleAction}/>
                ))}
              </AnimatePresence>
              {filteredRecords.length === 0 && (
                 <motion.div initial={{opacity: 0}} animate={{opacity: 1}} className="text-center py-10">
                    <p className="font-semibold text-gray-600">Nenhum registro encontrado.</p>
                    <p className="text-sm text-gray-500">Tente ajustar seus filtros.</p>
                 </motion.div>
              )}
            </div>
          </div>
        </main>
      </div>
    </>
  );
}

export default PortfolioTimelinePage;
