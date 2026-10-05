import React, { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { listarNotificacoes, marcarNotificacaoLida } from '@/services/api';
import { useAuth } from '@/contexts/AuthContext';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { MessageSquare, CheckCircle, Loader2 } from 'lucide-react';
import { useToast } from '@/components/ui/use-toast';
import { ptBR } from 'date-fns/locale';
import { safeFormatDate } from '@/lib/dateUtils';

/*
 * ALTERADO: lê as notificações do usuário logado (GET notificacoes/?lidas=false)
 * em vez de mensagens_coordenacao + mensagens_lidas. Mostra só as enviadas por
 * uma pessoa (com remetente); avisos automáticos do sistema ficam no
 * AlertsAndMessagesCenter. "Ok, entendido" chama notificacoes/<id>/marcar-lida/.
 */

const LIMITE = 3;

const MessageCard = ({ message, onMarkAsRead, marking }) => (
  <motion.div
    layout
    initial={{ opacity: 0, y: 20, scale: 0.95 }}
    animate={{ opacity: 1, y: 0, scale: 1 }}
    exit={{ opacity: 0, y: -20, scale: 0.95 }}
    transition={{ duration: 0.3, ease: 'easeInOut' }}
    className="mb-4"
  >
    <Card className="bg-lavanda-claro border-lavanda shadow-sm overflow-hidden">
      <CardHeader className="pb-3">
        <div className="flex justify-between items-start">
          <div>
            {message.titulo && (
              <CardTitle className="text-base font-bold text-roxo-principal">{message.titulo}</CardTitle>
            )}
            <CardDescription className="text-xs text-texto-medio">
              Enviado por {message.remetente_nome} em{' '}
              {safeFormatDate(message.criado_em, "dd/MM/yyyy 'às' HH:mm", { locale: ptBR })}
            </CardDescription>
          </div>
          <div className="p-2 bg-white rounded-full">
            <MessageSquare className="h-5 w-5 text-roxo-principal" />
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <p className="text-sm text-texto-escuro mb-4 whitespace-pre-line">{message.conteudo}</p>
        <Button
          onClick={() => onMarkAsRead(message.id)}
          disabled={marking}
          className="w-full bg-roxo-principal hover:bg-roxo-principal/90"
          size="sm"
        >
          {marking
            ? <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            : <CheckCircle className="mr-2 h-4 w-4" />}
          Ok, entendido
        </Button>
      </CardContent>
    </Card>
  </motion.div>
);

const CoordinationMessages = () => {
  const { user } = useAuth();
  const { toast } = useToast();
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [markingId, setMarkingId] = useState(null);

  useEffect(() => {
    const fetchMessages = async () => {
      if (!user) {
        setLoading(false);
        return;
      }
      try {
        setLoading(true);
        const notificacoes = await listarNotificacoes({ apenasNaoLidas: true });
        // O backend já devolve da mais recente para a mais antiga.
        setMessages((notificacoes || []).filter((n) => n.remetente).slice(0, LIMITE));
      } catch (error) {
        toast({ variant: 'destructive', title: 'Erro ao buscar mensagens', description: error.message });
      } finally {
        setLoading(false);
      }
    };
    fetchMessages();
  }, [user, toast]);

  const handleMarkAsRead = async (messageId) => {
    if (!user) return;
    setMarkingId(messageId);
    try {
      await marcarNotificacaoLida(messageId);
      setMessages((prev) => prev.filter((m) => m.id !== messageId));
      toast({ title: 'Mensagem marcada como lida!', description: 'A mensagem foi arquivada.' });
    } catch (error) {
      toast({ variant: 'destructive', title: 'Erro ao marcar mensagem', description: error.message });
    } finally {
      setMarkingId(null);
    }
  };

  if (loading) {
    return (
      <div className="mt-10 text-center">
        <p className="text-texto-medio">Carregando mensagens...</p>
      </div>
    );
  }

  if (messages.length === 0) {
    return (
      <div className="mt-10 text-center p-6 bg-white rounded-2xl shadow-sm border border-gray-100">
        <CheckCircle className="h-12 w-12 text-green-500 mx-auto mb-4" />
        <h3 className="text-lg font-semibold text-gray-800">Tudo em dia!</h3>
        <p className="text-texto-medio mt-1">Você não tem novas mensagens da coordenação.</p>
      </div>
    );
  }

  return (
    <div className="mt-10">
      <h2 className="text-xl font-bold text-gray-800 mb-4">💬 Mensagens da Coordenação</h2>
      <ScrollArea className="h-auto max-h-[450px] pr-4">
        <AnimatePresence>
          {messages.map((message) => (
            <MessageCard
              key={message.id}
              message={message}
              onMarkAsRead={handleMarkAsRead}
              marking={markingId === message.id}
            />
          ))}
        </AnimatePresence>
      </ScrollArea>
    </div>
  );
};

export default CoordinationMessages;