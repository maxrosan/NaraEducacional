import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { BookOpen, FileText, Calendar, Loader2, Search } from 'lucide-react';
import { format } from 'date-fns';
import { ptBR } from 'date-fns/locale';
import { safeFormatDate } from '@/lib/dateUtils';
import { apiClient } from '@/lib/apiClient';
import { useToast } from '@/components/ui/use-toast';

const ContributionsModal = ({ isOpen, onClose, teacher }) => {
  const { toast } = useToast();
  const [contributions, setContributions] = useState({ planejamentos: [], producoes: [] });
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const fetchContributions = async () => {
      if (!isOpen || !teacher) return;
      setLoading(true);

      try {
        const [
          { data: planejamentos, error: planError },
          { data: producoes, error: prodError }
        ] = await Promise.all([
          apiClient
            .from('planejamentos')
            .select('id, semana_referencia, turmas(nome)')
            .eq('id_professor', teacher.id)
            .order('semana_referencia', { ascending: false }),
          apiClient
            .from('producoes_criancas')
            .select('id, data_registro, tipo_producao, criancas(nome_completo)')
            .eq('professor_id', teacher.id)
            .order('data_registro', { ascending: false })
        ]);

        if (planError || prodError) {
          throw new Error(planError?.message || prodError?.message);
        }

        setContributions({ planejamentos: planejamentos || [], producoes: producoes || [] });
      } catch (error) {
        console.error('Error fetching contributions:', error);
        toast({ variant: 'destructive', title: 'Erro', description: 'Não foi possível buscar as contribuições.' });
        setContributions({ planejamentos: [], producoes: [] }); // Fallback
      } finally {
        setLoading(false);
      }
    };

    fetchContributions();
  }, [isOpen, teacher, toast]);

  const handleViewItem = () => {
    toast({
      title: 'Funcionalidade em desenvolvimento',
      description: 'A visualização detalhada do item estará disponível em breve.',
    });
  };

  if (!teacher) return null;

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-lg bg-white/90 backdrop-blur-sm">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-3 text-xl text-roxo-principal">
            <BookOpen className="h-6 w-6" />
            Contribuições
          </DialogTitle>
          <DialogDescription>
            Registros feitos por {teacher.nome}.
          </DialogDescription>
        </DialogHeader>
        
        <Tabs defaultValue="planejamentos" className="w-full">
          <TabsList>
            <TabsTrigger value="planejamentos">Planejamentos</TabsTrigger>
            <TabsTrigger value="producoes">Produções</TabsTrigger>
          </TabsList>
          <ScrollArea className="h-72 w-full mt-4 pr-4">
            {loading ? (
              <div className="flex justify-center items-center h-full">
                <Loader2 className="h-8 w-8 animate-spin text-roxo-principal" />
              </div>
            ) : (
              <>
                <TabsContent value="planejamentos">
                  {contributions.planejamentos.length > 0 ? (
                    <div className="space-y-3">
                      {contributions.planejamentos.map(item => (
                        <div key={item.id} className="flex justify-between items-center p-3 bg-lavanda-claro rounded-lg">
                          <div>
                            <p className="font-semibold text-texto-escuro">Semana de {safeFormatDate(item.semana_referencia, "dd/MM/yyyy", { locale: ptBR })}</p>
                            <p className="text-sm text-texto-medio">Turma: {item.turmas?.nome || 'N/A'}</p>
                          </div>
                          <Button variant="ghost" size="sm" onClick={handleViewItem}><Search className="h-4 w-4 mr-2" />Ver</Button>
                        </div>
                      ))}
                    </div>
                  ) : <p className="text-center text-texto-medio py-10">Nenhum planejamento encontrado.</p>}
                </TabsContent>
                <TabsContent value="producoes">
                  {contributions.producoes.length > 0 ? (
                    <div className="space-y-3">
                      {contributions.producoes.map(item => (
                        <div key={item.id} className="flex justify-between items-center p-3 bg-lavanda-claro rounded-lg">
                          <div>
                            <p className="font-semibold text-texto-escuro">{item.tipo_producao} - {item.criancas?.nome_completo || 'N/A'}</p>
                            <p className="text-sm text-texto-medio">Registrado em: {safeFormatDate(item.data_registro, "dd/MM/yyyy", { locale: ptBR })}</p>
                          </div>
                          <Button variant="ghost" size="sm" onClick={handleViewItem}><Search className="h-4 w-4 mr-2" />Ver</Button>
                        </div>
                      ))}
                    </div>
                  ) : <p className="text-center text-texto-medio py-10">Nenhuma produção encontrada.</p>}
                </TabsContent>
              </>
            )}
          </ScrollArea>
        </Tabs>

        <DialogFooter>
          <Button onClick={onClose} variant="outline">Fechar</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default ContributionsModal;