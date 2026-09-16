import React, { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { apiClient } from '@/lib/apiClient';
import { useAuth } from '@/contexts/AuthContext';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { MessageSquare, CheckCircle } from 'lucide-react';
import { useToast } from '@/components/ui/use-toast';
import { format } from 'date-fns';
import { ptBR } from 'date-fns/locale';
import { safeFormatDate } from '@/lib/dateUtils';

const MessageCard = ({ message, onMarkAsRead }) => {
  return (
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
              {message.titulo && <CardTitle className="text-base font-bold text-roxo-principal">{message.titulo}</CardTitle>}
              <CardDescription className="text-xs text-texto-medio">
                Enviado por {message.remetente} em {safeFormatDate(message.created_at, "dd/MM/yyyy 'às' HH:mm", { locale: ptBR })}
              </CardDescription>
            </div>
            <div className="p-2 bg-white rounded-full">
              <MessageSquare className="h-5 w-5 text-roxo-principal" />
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-texto-escuro mb-4">{message.conteudo}</p>
          <Button 
            onClick={() => onMarkAsRead(message.id)}
            className="w-full bg-roxo-principal hover:bg-roxo-principal/90"
            size="sm"
          >
            <CheckCircle className="mr-2 h-4 w-4" />
            Ok, entendido
          </Button>
        </CardContent>
      </Card>
    </motion.div>
  );
};

const CoordinationMessages = () => {
  const { user } = useAuth();
  const { toast } = useToast();
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchMessages = async () => {
      if (!user) return;

      try {
        setLoading(true);
        
        const { data: readMessages, error: readError } = await apiClient
          .from('mensagens_lidas')
          .select('mensagem_id')
          .eq('usuario_id', user.id);

        if (readError) throw readError;

        const readMessageIds = readMessages.map(m => m.mensagem_id);

        let query = apiClient
          .from('mensagens_coordenacao')
          .select('*');

        if (readMessageIds.length > 0) {
            query = query.not('id', 'in', `(${readMessageIds.join(',')})`);
        }
        
        const { data: unreadMessages, error: unreadError } = await query
          .order('created_at', { ascending: false })
          .limit(3);

        if (unreadError) throw unreadError;

        setMessages(unreadMessages || []);
      } catch (error) {
        toast({
          variant: "destructive",
          title: "Erro ao buscar mensagens",
          description: error.message,
        });
      } finally {
        setLoading(false);
      }
    };

    fetchMessages();
  }, [user, toast]);

  const handleMarkAsRead = async (messageId) => {
    if (!user) return;

    try {
      const { error } = await apiClient
        .from('mensagens_lidas')
        .insert({ mensagem_id: messageId, usuario_id: user.id });

      if (error) throw error;

      setMessages(prevMessages => prevMessages.filter(m => m.id !== messageId));
      toast({
        title: "Mensagem marcada como lida!",
        description: "A mensagem foi arquivada.",
      });
    } catch (error) {
      toast({
        variant: "destructive",
        title: "Erro ao marcar mensagem",
        description: error.message,
      });
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
          {messages.map(message => (
            <MessageCard key={message.id} message={message} onMarkAsRead={handleMarkAsRead} />
          ))}
        </AnimatePresence>
      </ScrollArea>
    </div>
  );
};

export default CoordinationMessages;