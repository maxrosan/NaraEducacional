import React, { useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { ArrowLeft, BookOpen, ChevronRight, Loader2, User, Users } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';

const ProductionStudentsList = ({ teacher, allTurmas = [], students, loading, onBack }) => {
  const navigate = useNavigate();

  const turmaIdToNome = useMemo(() => {
    const map = new Map();
    (allTurmas || []).forEach(turma => {
      if (turma?.id != null) map.set(String(turma.id), turma.nome);
    });
    return map;
  }, [allTurmas]);

  const grupos = useMemo(() => {
    if (!students || students.length === 0) return [];
    const porTurma = new Map();
    students.forEach(student => {
      const turmaId = student.turma_id != null ? String(student.turma_id) : 'sem-turma';
      if (!porTurma.has(turmaId)) {
        porTurma.set(turmaId, {
          turmaId,
          turmaNome: turmaIdToNome.get(turmaId) || student.turma_nome || 'Sem turma',
          alunos: [],
        });
      }
      porTurma.get(turmaId).alunos.push(student);
    });
    return Array.from(porTurma.values()).map(grupo => ({
      ...grupo,
      alunos: [...grupo.alunos].sort((a, b) =>
        (a.nome_completo || '').localeCompare(b.nome_completo || '')
      ),
    })).sort((a, b) => a.turmaNome.localeCompare(b.turmaNome));
  }, [students, turmaIdToNome]);

  const totalAlunos = students?.length || 0;

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.2 }}>
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-6">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon" onClick={onBack} aria-label="Voltar para professores">
            <ArrowLeft className="h-5 w-5" />
          </Button>
          <div>
            <p className="text-sm text-gray-500 flex items-center gap-2">
              <BookOpen className="h-4 w-4 text-purple-500" />
              Produção do(a) professor(a)
            </p>
            <h3 className="text-lg font-bold text-gray-800">{teacher?.nome}</h3>
          </div>
        </div>
        <div className="flex flex-wrap gap-2 items-center">
          {(teacher?.turmas || []).filter(Boolean).map(t => (
            <Badge key={t} className="bg-purple-100 text-purple-800 hover:bg-purple-200">{t}</Badge>
          ))}
          <Badge variant="secondary" className="ml-1">
            <Users className="h-3 w-3 mr-1" />
            {totalAlunos} aluno{totalAlunos === 1 ? '' : 's'}
          </Badge>
        </div>
      </div>

      {loading ? (
        <div className="flex justify-center items-center py-16">
          <Loader2 className="h-8 w-8 animate-spin text-purple-500" />
        </div>
      ) : totalAlunos === 0 ? (
        <div className="text-center py-12 text-gray-500 border-2 border-dashed rounded-lg">
          <Users className="mx-auto h-12 w-12 text-gray-400" />
          <p className="mt-4">Nenhum aluno encontrado nas turmas deste professor.</p>
        </div>
      ) : (
        <div className="space-y-6">
          {grupos.map(grupo => (
            <div key={grupo.turmaId}>
              <h4 className="text-sm font-semibold text-gray-600 uppercase tracking-wide mb-2">
                {grupo.turmaNome}
              </h4>
              <ul className="border rounded-md divide-y bg-white">
                {grupo.alunos.map(aluno => (
                  <li key={aluno.id}>
                    <Button
                      variant="ghost"
                      className="w-full justify-between h-12 px-4"
                      onClick={() => navigate(`/relatorios/${aluno.id}`)}
                    >
                      <div className="flex items-center gap-3">
                        <User className="h-5 w-5 text-gray-500" />
                        <span>{aluno.nome_completo}</span>
                      </div>
                      <ChevronRight className="h-5 w-5 text-gray-400" />
                    </Button>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}
    </motion.div>
  );
};

export default ProductionStudentsList;
