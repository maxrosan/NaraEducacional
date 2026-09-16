import React, { useState, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Backpack, Filter, PlayCircle, Loader2, Download, FileText } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Input } from '@/components/ui/input';
import { MediaViewerModal } from '@/components/portfolio/MediaViewerModal';
import { useToast } from '@/components/ui/use-toast';
import { jsPDF } from 'jspdf';
import 'jspdf-autotable';
import * as XLSX from 'xlsx';
import { addNaraHeader } from '@/lib/pdfGenerator';

const MediaCard = ({ media, onClick }) => (
  <motion.div
    layout
    initial={{ opacity: 0, scale: 0.9 }}
    animate={{ opacity: 1, scale: 1 }}
    exit={{ opacity: 0, scale: 0.9 }}
    className="bg-white rounded-2xl shadow-md border border-gray-100 overflow-hidden cursor-pointer card-hover"
    onClick={onClick}
  >
    <div className="relative">
      <img  src={media.type === 'video' ? 'https://images.unsplash.com/photo-1505102942944-6b7f2b4a7284?q=80&w=800' : media.url} alt={media.caption} className="w-full h-48 object-cover" />
      {media.type === 'video' && (
        <div className="absolute inset-0 bg-black/30 flex items-center justify-center">
          <PlayCircle className="h-12 w-12 text-white/80" />
        </div>
      )}
      <div className="absolute top-2 left-2 bg-black/50 text-white text-xs px-2 py-1 rounded-full font-bold">
        {media.student}
      </div>
    </div>
    <div className="p-3">
      <p className="text-sm text-gray-600 truncate">{media.caption}</p>
      <p className="text-xs text-gray-400">{media.turma}</p>
    </div>
  </motion.div>
);

const PortfoliosView = ({ data, turmas }) => {
  const { toast } = useToast();
  const [selectedMedia, setSelectedMedia] = useState(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [turmaFilter, setTurmaFilter] = useState('all');
  const [studentFilter, setStudentFilter] = useState('');

  const filteredData = useMemo(() => {
    if (!data) return [];
    return data.filter(item => {
      const turmaMatch = turmaFilter === 'all' || item.turma === turmaFilter;
      const studentMatch = studentFilter === '' || item.student.toLowerCase().includes(studentFilter.toLowerCase());
      return turmaMatch && studentMatch;
    });
  }, [data, turmaFilter, studentFilter]);

  const handleViewMedia = (media) => {
    setSelectedMedia(media);
    setIsModalOpen(true);
  };

  const handleRemoveMedia = () => {
    toast({
      title: '🗑️ Mídia removida!',
      description: 'O item foi removido do portfólio com sucesso. (Simulado)',
    });
    setIsModalOpen(false);
  };

  const exportToPDF = async () => {
    try {
      const doc = new jsPDF();
      await addNaraHeader(doc, 'Relatório de Portfólios');
      doc.autoTable({
        head: [['Criança', 'Turma', 'Data', 'Tipo', 'Descrição']],
        body: filteredData.map(item => [item.student, item.turma, item.date, item.type, item.caption]),
        startY: 50,
      });
      doc.save('relatorio_portfolios.pdf');
    } catch (error) {
      toast({
        variant: 'destructive',
        title: 'Erro ao exportar PDF',
        description: 'Não foi possível gerar o relatório de portfólios.',
      });
    }
  };

  const exportToExcel = () => {
    const worksheet = XLSX.utils.json_to_sheet(filteredData.map(item => ({
      Criança: item.student,
      Turma: item.turma,
      Data: item.date,
      Tipo: item.type,
      Descrição: item.caption,
      URL: item.url,
    })));
    const workbook = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(workbook, worksheet, "Portfólios");
    XLSX.writeFile(workbook, "relatorio_portfolios.xlsx");
  };

  if (!data) {
    return (
      <div className="flex justify-center items-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-purple-500" />
      </div>
    );
  }

  return (
    <>
      <MediaViewerModal
        isOpen={isModalOpen}
        onOpenChange={setIsModalOpen}
        media={selectedMedia}
        onRemove={handleRemoveMedia}
      />
      <Card className="bg-white/50">
        <CardHeader>
          <CardTitle className="flex items-center justify-between text-xl">
            <div className="flex items-center gap-3">
              <Backpack className="h-6 w-6 text-yellow-500" />
              Consulta de Portfólios
            </div>
            <div className="flex items-center gap-2">
              <Button variant="outline" size="sm" onClick={exportToPDF}>
                <Download className="h-4 w-4 mr-2" />
                PDF
              </Button>
              <Button variant="outline" size="sm" onClick={exportToExcel}>
                <FileText className="h-4 w-4 mr-2" />
                Excel
              </Button>
            </div>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col sm:flex-row gap-4 mb-6">
            <Select value={turmaFilter} onValueChange={setTurmaFilter}>
              <SelectTrigger className="w-full sm:w-[200px]">
                <Filter className="h-4 w-4 mr-2 text-gray-400" />
                <SelectValue placeholder="Filtrar por Turma" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Todas as Turmas</SelectItem>
                {turmas?.map(turma => (
                  <SelectItem key={turma.id} value={turma.nome}>{turma.nome}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Input 
              placeholder="Buscar por nome da criança..." 
              className="w-full sm:w-[240px]" 
              value={studentFilter}
              onChange={(e) => setStudentFilter(e.target.value)}
            />
          </div>

          <AnimatePresence>
            <motion.div
              layout
              className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6"
            >
              {filteredData.map(media => (
                <MediaCard key={media.id} media={media} onClick={() => handleViewMedia(media)} />
              ))}
            </motion.div>
          </AnimatePresence>
          {filteredData.length === 0 && (
            <div className="text-center py-12 text-gray-500">
              <p>Nenhum registro encontrado para os filtros selecionados.</p>
            </div>
          )}
        </CardContent>
      </Card>
    </>
  );
};

export default PortfoliosView;
