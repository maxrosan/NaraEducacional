import React, { useState, useEffect } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { useToast } from '@/components/ui/use-toast';
import { useAuth } from '@/contexts/AuthContext';
// TODO: confirme o nome real do helper de fetch autenticado usado no projeto
import { authFetch } from '@/services/api';

/**
 * Passo "registro por texto" dentro do SpecialistRegistrationPage.
 * Ao contrário do registro por voz, aqui "salvar" volta direto para o
 * perfil da criança (sem passar pela tela de ligações) — mesmo
 * comportamento do protótipo original.
 *
 * @param {() => void} onSalvar
 * @param {() => void} onCancelar
 * @param {(aluno: {id: string, nome_completo: string} | null) => void} [onAlunoSelecionado]
 *   Chamado sempre que o aluno escolhido no select mudar, para que a página
 *   pai (que controla o cabeçalho "Registro da sessão · Nome · hoje") possa
 *   exibir o nome do aluno realmente selecionado aqui, em vez do
 *   criancaId genérico da URL.
 */
export default function TextRegistrationForm({ onSalvar, onCancelar, onAlunoSelecionado }) {
  const { toast } = useToast();
  const { turmaAtiva } = useAuth();
  const [data, setData] = useState(() => new Date().toISOString().split('T')[0]);
  const [observacao, setObservacao] = useState('');

  // --- Alunos da turma ativa, para o select ao lado da data ---
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

  function handleSalvar() {
    toast({
      title: '🚧 Funcionalidade em construção!',
      description: 'A lógica para salvar os dados do formulário ainda será implementada.',
    });
    onSalvar();
  }

  return (
    <div className="space-y-4">
      <Card className="rounded-2xl">
        <CardContent className="p-4 space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label className="text-[11px] font-medium text-gray-500 uppercase tracking-wide">Data do atendimento</Label>
              <input
                type="date"
                value={data}
                onChange={(e) => setData(e.target.value)}
                className="mt-1.5 w-full rounded-lg border border-gray-200 bg-[#F8F7FF] px-3 py-2 text-sm text-gray-800"
              />
            </div>

            <div>
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
            </div>
          </div>

          <div>
            <Label className="text-[11px] font-medium text-gray-500 uppercase tracking-wide">O que foi observado</Label>
            <Textarea
              rows={10}
              placeholder="Descreva o que aconteceu na sessão, o que a criança demonstrou, avanços e pontos de atenção..."
              value={observacao}
              onChange={(e) => setObservacao(e.target.value)}
              className="mt-1.5 text-sm bg-[#F8F7FF]"
            />
          </div>
        </CardContent>
      </Card>

      <div className="flex flex-col sm:flex-row sm:justify-end gap-2">
        <Button variant="outline" className="order-2 sm:order-1 w-full sm:w-auto sm:px-8 rounded-xl" onClick={onCancelar}>
          Cancelar
        </Button>
        <Button className="order-1 sm:order-2 w-full sm:w-auto sm:px-8 bg-roxo-principal hover:bg-[#6B4EA8] rounded-xl" onClick={handleSalvar}>
          Salvar registro
        </Button>
      </div>
    </div>
  );
}