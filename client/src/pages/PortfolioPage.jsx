import React, { useState } from 'react';
import { Helmet } from 'react-helmet-async';
import { useNavigate, useParams } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { ArrowLeft, FileText, Filter, Calendar, PlayCircle, Trash2, LayoutGrid, List, Download } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useToast } from '@/components/ui/use-toast';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Card, CardContent } from '@/components/ui/card';
import { MediaViewerModal } from '@/components/portfolio/MediaViewerModal';
import { generatePortfolioPdf } from '@/lib/pdfGenerator';

const studentData = {
  '1': {
    name: 'Júlia',
    turma: 'Maternal II - A',
    age: '3 anos e 2 meses',
    portfolioMedia: [
      {
        id: 'med1',
        date: '2025-07-11',
        type: 'image',
        url: 'https://images.unsplash.com/photo-1518895318346-f33b2a11b332?q=80&w=800',
        caption: 'Júlia explorando as cores e texturas na atividade de pintura com os dedos.',
        project: 'Semana das Artes',
      },
      {
        id: 'med2',
        date: '2025-07-10',
        type: 'video',
        url: 'https://storage.googleapis.com/hostinger-horizons-assets-prod/videos_for_nara/sample_video.mp4',
        thumbnail: 'https://images.unsplash.com/photo-1505102942944-6b7f2b4a7284?q=80&w=800',
        caption: 'Momento da roda de música, cantando a canção do "Pintinho Amarelinho".',
        project: 'Músicas e Ritmos',
      },
      {
        id: 'med3',
        date: '2025-07-08',
        type: 'image',
        url: 'https://images.unsplash.com/photo-1509248961158-e54f935324d4?q=80&w=800',
        caption: 'Concentração total na construção de uma torre com blocos de madeira.',
        project: null,
      },
      {
        id: 'med4',
        date: '2025-07-05',
        type: 'image',
        url: 'https://images.unsplash.com/photo-1519340333755-56e9c1d04579?q=80&w=800',
        caption: 'Cuidando da nossa hortinha, aprendendo sobre o crescimento das plantas.',
        project: 'Projeto Meio Ambiente',
      },
    ],
  },
};

const MediaCard = ({ media, onClick }) => (
  <motion.div
    layout
    initial={{ opacity: 0, scale: 0.9 }}
    animate={{ opacity: 1, scale: 1 }}
    exit={{ opacity: 0, scale: 0.9 }}
    transition={{ duration: 0.3 }}
    className="bg-white rounded-2xl shadow-md border border-gray-100 overflow-hidden cursor-pointer card-hover"
    onClick={onClick}
  >
    <div className="relative">
      <img  src={media.type === 'video' ? media.thumbnail : media.url} alt={media.caption} className="w-full h-48 object-cover" />
      {media.type === 'video' && (
        <div className="absolute inset-0 bg-black/30 flex items-center justify-center">
          <PlayCircle className="h-12 w-12 text-white/80" />
        </div>
      )}
      <div className="absolute bottom-2 left-2 bg-black/50 text-white text-xs px-2 py-1 rounded-md">
        {new Date(media.date).toLocaleDateString('pt-BR', { day: '2-digit', month: 'short' })}
      </div>
    </div>
    <div className="p-3">
      <p className="text-sm text-gray-600 truncate">{media.caption}</p>
    </div>
  </motion.div>
);

function PortfolioPage() {
  const { studentId } = useParams();
  const navigate = useNavigate();
  const { toast } = useToast();
  
  const [student, setStudent] = useState(studentData[studentId]);
  const [filterProject, setFilterProject] = useState('all');
  const [selectedMedia, setSelectedMedia] = useState(null);
  const [isModalOpen, setIsModalOpen] = useState(false);

  const handleGenerateReport = () => {
    navigate(`/relatorios/${studentId}`);
  };

  const handleViewMedia = (media) => {
    setSelectedMedia(media);
    setIsModalOpen(true);
  };

  const handleRemoveMedia = (mediaId) => {
    setStudent(prev => ({
      ...prev,
      portfolioMedia: prev.portfolioMedia.filter(m => m.id !== mediaId)
    }));
    setIsModalOpen(false);
    toast({
      title: '🗑️ Mídia removida!',
      description: 'O item foi removido do portfólio com sucesso.',
      className: 'bg-yellow-100 border-yellow-300 text-yellow-800',
    });
  };

  const handleExportPortfolio = async () => {
    toast({
      title: '📥 Gerando PDF do Portfólio...',
      description: 'Aguarde enquanto preparamos o arquivo para download.',
    });
    await generatePortfolioPdf(student);
  };
  
  if (!student) {
    return <div>Criança não encontrada.</div>;
  }

  const projects = ['all', ...new Set(student.portfolioMedia.map(m => m.project).filter(Boolean))];
  
  const filteredMedia = student.portfolioMedia.filter(media => {
    return filterProject === 'all' || media.project === filterProject;
  });

  return (
    <>
      <Helmet>
        <title>NARA - Portfólio de {student.name}</title>
        <meta name="description" content={`Acompanhe a galeria de aprendizagem de ${student.name}.`} />
      </Helmet>

      <MediaViewerModal 
        isOpen={isModalOpen}
        onOpenChange={setIsModalOpen}
        media={selectedMedia}
        onRemove={handleRemoveMedia}
      />

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
              <Button variant="outline" size="sm" onClick={handleExportPortfolio}>
                <Download className="h-4 w-4 mr-0 sm:mr-2" />
                <span className="hidden sm:inline">Exportar</span>
              </Button>
              <Button className="nara-gradient text-white btn-hover" onClick={handleGenerateReport}>
                <FileText className="h-4 w-4 mr-0 sm:mr-2" />
                <span className="hidden sm:inline">Relatório</span>
              </Button>
              <img  alt="NARA icon logo" className="h-12 w-auto hidden sm:block sm:h-14" src="/nara-logo.png" />
            </div>
          </div>
        </header>

        <main className="container mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <Card className="mb-8 bg-white/50">
            <CardContent className="p-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <Select onValueChange={setFilterProject} defaultValue="all">
                    <SelectTrigger>
                        <Filter className="h-4 w-4 mr-2 text-gray-400"/>
                        <SelectValue placeholder="Filtrar por projeto"/>
                    </SelectTrigger>
                    <SelectContent>
                        <SelectItem value="all">Todos os projetos</SelectItem>
                        {projects.slice(1).map(p => <SelectItem key={p} value={p}>{p}</SelectItem>)}
                    </SelectContent>
                </Select>
                <Button variant="outline" onClick={() => toast({ title: '🚧 Em breve!', description: 'Filtro por período será adicionado em breve.' })}>
                  <Calendar className="h-4 w-4 mr-2" />
                  Filtrar por período
                </Button>
              </div>
            </CardContent>
          </Card>
          
          <AnimatePresence>
            <motion.div 
              layout
              className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6"
            >
              {filteredMedia.map(media => (
                <MediaCard key={media.id} media={media} onClick={() => handleViewMedia(media)} />
              ))}
            </motion.div>
          </AnimatePresence>

          {filteredMedia.length === 0 && (
             <motion.div initial={{opacity: 0}} animate={{opacity: 1}} className="text-center py-16 bg-white rounded-2xl">
                <LayoutGrid className="h-12 w-12 mx-auto text-gray-300" />
                <p className="mt-4 font-semibold text-gray-600">Nenhuma mídia encontrada.</p>
                <p className="text-sm text-gray-500">Tente ajustar os filtros ou adicione novas mídias.</p>
             </motion.div>
          )}
        </main>
      </div>
    </>
  );
}

export default PortfolioPage;
