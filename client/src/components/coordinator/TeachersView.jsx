import React, { useState, useMemo, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Users, Filter, Search, User, MessageSquare, Loader2, Star, XCircle, BookOpen, ChevronLeft, ChevronRight } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { useToast } from '@/components/ui/use-toast';
import { formatDistanceToNow } from 'date-fns';
import { ptBR } from 'date-fns/locale';
import { toValidDate } from '@/lib/dateUtils';

const formatLastLogin = (value) => {
  const date = toValidDate(value);
  if (!date) return 'Nunca';
  return formatDistanceToNow(date, { addSuffix: true, locale: ptBR });
};
import ProfileModal from '@/components/coordinator/ProfileModal';
import MessageModal from '@/components/coordinator/MessageModal';
import ProductionStudentsList from '@/components/coordinator/ProductionStudentsList';
import { apiClient } from '@/lib/apiClient';

const PAGE_SIZE = 20;

const TeachersView = ({ professores, turmas: allTurmas }) => {
  const { toast } = useToast();
  const [turmaFilter, setTurmaFilter] = useState('all');
  const [searchTerm, setSearchTerm] = useState('');
  const [filteredData, setFilteredData] = useState([]);
  const [selectedTeacher, setSelectedTeacher] = useState(null);
  const [isProfileModalOpen, setProfileModalOpen] = useState(false);
  const [isMessageModalOpen, setMessageModalOpen] = useState(false);
  const [productionTeacher, setProductionTeacher] = useState(null);
  const [studentsCache, setStudentsCache] = useState({});
  const [loadingStudents, setLoadingStudents] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);

  useEffect(() => {
    if (professores) {
      setFilteredData([...professores].sort((a, b) => a.nome.localeCompare(b.nome)));
    }
  }, [professores]);

  useEffect(() => {
    setCurrentPage(1);
  }, [filteredData]);

  const totalPages = Math.max(1, Math.ceil(filteredData.length / PAGE_SIZE));

  useEffect(() => {
    if (currentPage > totalPages) {
      setCurrentPage(totalPages);
    }
  }, [totalPages, currentPage]);

  const pagedData = useMemo(() => {
    const start = (currentPage - 1) * PAGE_SIZE;
    return filteredData.slice(start, start + PAGE_SIZE);
  }, [filteredData, currentPage]);

  const pageStartIndex = filteredData.length === 0 ? 0 : (currentPage - 1) * PAGE_SIZE + 1;
  const pageEndIndex = Math.min(currentPage * PAGE_SIZE, filteredData.length);

  const handleViewProfile = (teacher) => {
    setSelectedTeacher(teacher);
    setProfileModalOpen(true);
  };

  const handleSendMessage = (teacher) => {
    setSelectedTeacher(teacher);
    setMessageModalOpen(true);
  };

  const handleViewProduction = async (teacher) => {
    setProductionTeacher(teacher);

    if (studentsCache[teacher.id]) return;

    const turmaIds = (teacher.usuario_turmas || [])
      .map(ut => ut?.turma_id)
      .filter(Boolean);

    if (turmaIds.length === 0) {
      setStudentsCache(prev => ({ ...prev, [teacher.id]: [] }));
      return;
    }

    setLoadingStudents(true);
    try {
      const { data, error } = await apiClient
        .from('criancas')
        .select('id, nome_completo, turma_id')
        .in('turma_id', turmaIds)
        .order('nome_completo');
      if (error) throw error;
      setStudentsCache(prev => ({ ...prev, [teacher.id]: data || [] }));
    } catch (error) {
      toast({
        variant: 'destructive',
        title: 'Erro ao carregar alunos',
        description: error.message || 'Não foi possível buscar os alunos deste professor.',
      });
      setProductionTeacher(null);
    } finally {
      setLoadingStudents(false);
    }
  };

  const handleBackToTeachers = () => {
    setProductionTeacher(null);
  };

  const applyFilters = () => {
    if (!professores) return;
    const filtered = professores.filter(teacher => {
      const nameMatch = teacher.nome.toLowerCase().includes(searchTerm.toLowerCase());
      const turmas = teacher.turmas || [];
      const turmaMatch = turmaFilter === 'all' || turmas.includes(turmaFilter);
      return nameMatch && turmaMatch;
    });
    setFilteredData(filtered.sort((a, b) => a.nome.localeCompare(b.nome)));
  };

  const clearFilters = () => {
    setSearchTerm('');
    setTurmaFilter('all');
    setFilteredData([...(professores || [])].sort((a, b) => a.nome.localeCompare(b.nome)));
  };

  const getTurmasBadges = (turmas) => {
    if (!turmas || turmas.length === 0 || turmas.every(t => t === null)) {
      return <Badge variant="secondary">Nenhuma turma</Badge>;
    }
    return turmas.filter(Boolean).map(t => <Badge key={t} className="mr-1 mb-1 bg-purple-100 text-purple-800 hover:bg-purple-200">{t}</Badge>);
  };

  if (!professores) {
    return (
      <div className="flex justify-center items-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-purple-500" />
      </div>
    );
  }

  return (
    <>
      <ProfileModal
        isOpen={isProfileModalOpen}
        onClose={() => setProfileModalOpen(false)}
        teacher={selectedTeacher}
      />
      <MessageModal
        isOpen={isMessageModalOpen}
        onClose={() => setMessageModalOpen(false)}
        teacher={selectedTeacher}
      />
      <Card className="bg-white/50 overflow-hidden">
        <CardHeader>
          <CardTitle className="flex items-center gap-3 text-xl">
            <Users className="h-6 w-6 text-indigo-500" />
            Gestão de Professores
          </CardTitle>
        </CardHeader>
        <CardContent>
          {productionTeacher ? (
            <ProductionStudentsList
              teacher={productionTeacher}
              allTurmas={allTurmas}
              students={studentsCache[productionTeacher.id]}
              loading={loadingStudents && !studentsCache[productionTeacher.id]}
              onBack={handleBackToTeachers}
            />
          ) : (
          <>
          <div className="flex flex-col sm:flex-row gap-4 mb-6 items-center">
            <div className="relative w-full sm:w-auto sm:flex-grow">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
              <Input
                placeholder="Buscar por nome..."
                className="pl-10"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
              />
            </div>
            <Select value={turmaFilter} onValueChange={setTurmaFilter}>
              <SelectTrigger className="w-full sm:w-[200px]">
                <Filter className="h-4 w-4 mr-2 text-gray-400" />
                <SelectValue placeholder="Filtrar por Turma" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Todas as Turmas</SelectItem>
                {allTurmas?.map(turma => (
                  <SelectItem key={turma.id} value={turma.nome}>{turma.nome}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button onClick={applyFilters} className="w-full sm:w-auto">
              <Filter className="h-4 w-4 mr-2" />
              Filtrar
            </Button>
            <Button onClick={clearFilters} variant="outline" className="w-full sm:w-auto">
              <XCircle className="h-4 w-4 mr-2" />
              Limpar
            </Button>
          </div>

          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="overflow-x-auto">
            {filteredData.length === 0 ? (
              <div className="text-center py-10 text-gray-500">
                <Users className="mx-auto h-12 w-12 text-gray-400" />
                <p className="mt-4">Nenhum professor encontrado.</p>
                <p className="text-sm text-gray-400 mt-1">Verifique os filtros ou se existem professores cadastrados e ativos.</p>
              </div>
            ) : (
              <>
                <div className="md:hidden space-y-4">
                  {pagedData.map(teacher => (
                    <Card key={teacher.id} className="p-4">
                      <div className="font-bold">{teacher.nome}</div>
                      <div className="text-sm text-gray-500 break-all">{teacher.email}</div>
                      {teacher.especialidade && <div className="text-sm text-amber-600 flex items-center gap-1 mt-1"><Star className="h-3 w-3" />{teacher.especialidade}</div>}
                      <div className="my-2">{getTurmasBadges(teacher.turmas)}</div>
                      <div className="text-sm text-gray-500">
                        Último acesso: {formatLastLogin(teacher.last_login)}
                      </div>
                      <div className="flex flex-wrap justify-end items-center mt-2 gap-2">
                          <Button variant="outline" size="sm" onClick={() => handleViewProfile(teacher)}>
                            <User className="h-4 w-4 mr-2" /> Perfil
                          </Button>
                          <Button variant="outline" size="sm" onClick={() => handleSendMessage(teacher)}>
                            <MessageSquare className="h-4 w-4 mr-2" /> Mensagem
                          </Button>
                          <Button variant="outline" size="sm" onClick={() => handleViewProduction(teacher)}>
                            <BookOpen className="h-4 w-4 mr-2" /> Ver Produção
                          </Button>
                      </div>
                    </Card>
                  ))}
                </div>

                <div className="hidden md:block">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead className="text-center">Nome</TableHead>
                        <TableHead className="text-center">Email</TableHead>
                        <TableHead className="text-center">Especialidade</TableHead>
                        <TableHead className="text-center">Turmas</TableHead>
                        <TableHead className="text-center">Último Acesso</TableHead>
                        <TableHead className="text-center">Ações</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {pagedData.map((teacher) => (
                        <TableRow key={teacher.id}>
                          <TableCell className="font-medium">{teacher.nome}</TableCell>
                          <TableCell>{teacher.email}</TableCell>
                          <TableCell>{teacher.especialidade || 'N/A'}</TableCell>
                          <TableCell className="max-w-[250px]">{getTurmasBadges(teacher.turmas)}</TableCell>
                          <TableCell>{formatLastLogin(teacher.last_login)}</TableCell>
                          <TableCell className="text-right">
                            <Button variant="ghost" title="Ver perfil" size="sm" onClick={() => handleViewProfile(teacher)}>
                              <User className="h-4 w-4 mr-2"  />
                            </Button>
                            <Button variant="ghost" size="sm" title="Enviar Mensagem" onClick={() => handleSendMessage(teacher)}>
                              <MessageSquare className="h-4 w-4 mr-2" /> 
                            </Button>
                            <Button variant="ghost" size="sm" title="Ver Produção" onClick={() => handleViewProduction(teacher)}>
                              <BookOpen className="h-4 w-4 mr-2" />
                            </Button>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>

                {filteredData.length > PAGE_SIZE && (
                  <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mt-4 pt-4 border-t">
                    <span className="text-sm text-gray-600">
                      Exibindo {pageStartIndex}–{pageEndIndex} de {filteredData.length} professor{filteredData.length > 1 ? 'es' : ''}
                    </span>
                    <div className="flex items-center gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                        disabled={currentPage === 1}
                      >
                        <ChevronLeft className="h-4 w-4 mr-1" />
                        Anterior
                      </Button>
                      <span className="text-sm text-gray-700 px-2">
                        Página {currentPage} de {totalPages}
                      </span>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                        disabled={currentPage === totalPages}
                      >
                        Próxima
                        <ChevronRight className="h-4 w-4 ml-1" />
                      </Button>
                    </div>
                  </div>
                )}
              </>
            )}
          </motion.div>
          </>
          )}
        </CardContent>
      </Card>
    </>
  );
};

export default TeachersView;