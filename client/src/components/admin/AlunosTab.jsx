import React, { useState, useEffect, useCallback, useRef } from 'react';
import { listarInstituicoes, listarTurmas, listarCriancas } from '@/services/api';
import { useToast } from '@/components/ui/use-toast';
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import AlunosList from './alunos/AlunosList';
import StudentFormDialog from './alunos/StudentFormDialog';
import { Button } from '@/components/ui/button';
import { UserPlus, Download, ChevronLeft, ChevronRight } from 'lucide-react';
import BulkUploadDialog from './alunos/BulkUploadDialog';

const PAGE_SIZE = 20;
const SEARCH_DEBOUNCE_MS = 400;

const AlunosTab = () => {
    const { toast } = useToast();
    const [turmas, setTurmas] = useState([]);
    const [alunos, setAlunos] = useState([]);
    const [loading, setLoading] = useState(true);
    const [selectedTurma, setSelectedTurma] = useState('');
    const [searchTerm, setSearchTerm] = useState('');
    const [debouncedSearchTerm, setDebouncedSearchTerm] = useState('');
    const [institutionId, setInstitutionId] = useState(null);
    const [page, setPage] = useState(1);
    const [totalPages, setTotalPages] = useState(1);
    const [totalCount, setTotalCount] = useState(0);

    // Evita disparar uma busca no backend a cada tecla digitada — espera
    // o usuário parar de digitar antes de consultar a API.
    const debounceRef = useRef(null);
    useEffect(() => {
        if (debounceRef.current) clearTimeout(debounceRef.current);
        debounceRef.current = setTimeout(() => {
            setDebouncedSearchTerm(searchTerm);
        }, SEARCH_DEBOUNCE_MS);
        return () => clearTimeout(debounceRef.current);
    }, [searchTerm]);

    // Volta para a primeira página sempre que um filtro muda, para não
    // ficar "presa" numa página que deixou de existir no resultado novo.
    useEffect(() => {
        setPage(1);
    }, [selectedTurma, debouncedSearchTerm]);

    const fetchTurmasEInstituicao = useCallback(async () => {
        try {
            const instituicoes = await listarInstituicoes();
            const currentInstitutionId = instituicoes?.[0]?.id;
            setInstitutionId(currentInstitutionId);

            if (currentInstitutionId) {
                const turmasData = await listarTurmas({ instituicao_id: currentInstitutionId });
                const sortedTurmas = (turmasData || []).sort((a, b) =>
                    (a.nome || '').localeCompare(b.nome || '')
                );
                setTurmas(sortedTurmas);
            }
            return currentInstitutionId;
        } catch (error) {
            toast({ variant: "destructive", title: "Erro ao carregar turmas", description: error.message });
            return null;
        }
    }, [toast]);

    const fetchAlunos = useCallback(async (currentInstitutionId) => {
        if (!currentInstitutionId) return;
        setLoading(true);
        try {
            const filtros = {
                instituicao_id: currentInstitutionId,
                status_vinculo: 'all',
                page,
                page_size: PAGE_SIZE,
            };
            if (selectedTurma && selectedTurma !== 'all') {
                filtros.turma_id = selectedTurma;
            }
            if (debouncedSearchTerm.trim()) {
                filtros.nome = debouncedSearchTerm.trim();
            }

            const response = await listarCriancas(filtros);
            setAlunos(response.results || []);
            setTotalPages(response.total_pages || 1);
            setTotalCount(response.count ?? (response.results || []).length);
        } catch (error) {
            toast({ variant: "destructive", title: "Erro ao carregar alunos", description: error.message });
        } finally {
            setLoading(false);
        }
    }, [toast, page, selectedTurma, debouncedSearchTerm]);

    // Carrega instituição/turmas uma vez ao montar.
    useEffect(() => {
        fetchTurmasEInstituicao().then((currentInstitutionId) => {
            if (currentInstitutionId) {
                fetchAlunos(currentInstitutionId);
            }
        });
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    // Recarrega alunos sempre que página, turma ou busca mudam — mas só
    // depois que já temos institutionId (evita chamada duplicada no mount).
    useEffect(() => {
        if (institutionId) {
            fetchAlunos(institutionId);
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [page, selectedTurma, debouncedSearchTerm, institutionId]);

    const handleFilterByTurma = (turmaId) => {
        setSelectedTurma(turmaId);
    };

    const handleStudentUpdated = () => {
        fetchAlunos(institutionId);
    };

    const handleStudentDeleted = () => {
        // Recarrega para o aluno reaparecer marcado como inativo (admin continua vendo).
        fetchAlunos(institutionId);
    };

    const handlePreviousPage = () => {
        setPage((p) => Math.max(1, p - 1));
    };

    const handleNextPage = () => {
        setPage((p) => Math.min(totalPages, p + 1));
    };

    return (
        <div className="grid grid-cols-1 gap-6">
            <Card>
                <CardHeader>
                    <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
                        <div>
                            <CardTitle>Gestão de Alunos</CardTitle>
                            <CardDescription>Cadastre, edite e visualize os alunos da instituição.</CardDescription>
                        </div>
                        <div className="flex items-center gap-2">
                             <BulkUploadDialog 
                                turmas={turmas}
                                institutionId={institutionId}
                                onUploadComplete={handleStudentUpdated}
                             />
                            <StudentFormDialog 
                                turmas={turmas}
                                institutionId={institutionId}
                                onStudentUpdated={handleStudentUpdated}
                            >
                                <Button>
                                    <UserPlus className="mr-2 h-4 w-4" />
                                    Cadastrar Novo Aluno
                                </Button>
                            </StudentFormDialog>
                        </div>
                    </div>
                </CardHeader>
                <CardContent>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6 max-w-3xl">
                        <div>
                            <Label htmlFor="turma-filter">Filtrar por Turma</Label>
                            <Select onValueChange={handleFilterByTurma} value={selectedTurma}>
                                <SelectTrigger id="turma-filter">
                                    <SelectValue placeholder="Todas as turmas" />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="all">Todas as turmas</SelectItem>
                                    {turmas.map(turma => (
                                        <SelectItem key={turma.id} value={turma.id}>{turma.nome}</SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </div>
                        <div>
                            <Label htmlFor="aluno-search">Buscar por nome do aluno</Label>
                            <Input
                                id="aluno-search"
                                placeholder="Digite o nome do aluno..."
                                value={searchTerm}
                                onChange={(e) => setSearchTerm(e.target.value)}
                            />
                        </div>
                    </div>

                    <AlunosList 
                        alunos={alunos} 
                        loading={loading}
                        onStudentUpdated={handleStudentUpdated}
                        onStudentDeleted={handleStudentDeleted}
                        turmas={turmas}
                        institutionId={institutionId}
                    />

                    {!loading && totalCount > 0 && (
                        <div className="flex items-center justify-between mt-4">
                            <span className="text-sm text-gray-500">
                                {totalCount} aluno{totalCount !== 1 ? 's' : ''} · Página {page} de {totalPages}
                            </span>
                            <div className="flex gap-2">
                                <Button
                                    variant="outline"
                                    size="sm"
                                    disabled={page <= 1}
                                    onClick={handlePreviousPage}
                                >
                                    <ChevronLeft className="h-4 w-4 mr-1" />
                                    Anterior
                                </Button>
                                <Button
                                    variant="outline"
                                    size="sm"
                                    disabled={page >= totalPages}
                                    onClick={handleNextPage}
                                >
                                    Próxima
                                    <ChevronRight className="h-4 w-4 ml-1" />
                                </Button>
                            </div>
                        </div>
                    )}
                </CardContent>
            </Card>
        </div>
    );
};

export default AlunosTab;