import React, { useEffect, useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { apiClient } from '@/lib/apiClient';
import { apiService } from '@/services/api';
import { useAuth } from '@/contexts/AuthContext';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { MessageSquare, CheckCircle, AlertTriangle, AlertCircle, Loader2 } from 'lucide-react';
import { useToast } from '@/components/ui/use-toast';

const AlertCard = ({ alert, onDismiss }) => {
  const icons = {
    'no-record': <AlertTriangle className="h-5 w-5 text-red-500" />,
    message: <MessageSquare className="h-5 w-5 text-roxo-principal" />,
    default: <AlertCircle className="h-5 w-5 text-yellow-500" />,
  };
  const colors = {
    'no-record': 'border-red-200 bg-red-50',
    message: 'border-lavanda bg-lavanda-claro',
    default: 'border-yellow-200 bg-yellow-50',
  }

  const icon = icons[alert.type] || icons.default;
  const cardClass = colors[alert.type] || colors.default;

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 20, scale: 0.95 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: -20, scale: 0.95 }}
      transition={{ duration: 0.3, ease: 'easeInOut' }}
      className="mb-4"
    >
      <Card className={`${cardClass} shadow-sm overflow-hidde mb-4`}>
        <CardHeader className="pb-3">
          <div className="flex justify-between items-start">
            <div className="flex items-center gap-3">
               <div className="p-2 bg-white rounded-full">{icon}</div>
               <div>
                <p className="text-sm font-semibold text-texto-escuro">{alert.title}</p>
                <p className="text-xs text-texto-medio">{alert.subtitle}</p>
               </div>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-texto-escuro mb-4">{alert.content}</p>
          <Button
            onClick={() => onDismiss(alert)}
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

const AlertsAndMessagesCenter = () => {
  const { user } = useAuth();
  const { toast } = useToast();
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchAlertsAndMessages = useCallback(async () => {
    if (!user) {
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      const allAlerts = [];

      // 1. Fetch Coordination Messages
      const { data: readMessages, error: readError } = await apiClient
        .from('mensagens_lidas').select('mensagem_id').eq('usuario_id', user.id);
      if (readError) throw readError;
      const readMessageIds = readMessages.map(m => m.mensagem_id);

      let query = apiClient.from('mensagens_coordenacao').select('*');
      if (readMessageIds.length > 0) {
        query = query.not('id', 'in', `(${readMessageIds.join(',')})`);
      }
      query = query.order('created_at', { ascending: false });

      const { data: unreadMessages, error: msgError } = await query;
      if (msgError) throw msgError;

      if (unreadMessages) {
        allAlerts.push(...unreadMessages.map(msg => ({
          id: `msg-${msg.id}`,
          type: 'message',
          title: msg.titulo || "Mensagem da Coordena\u00e7\u00e3o",
          subtitle: `Enviado por ${msg.remetente}`,
          content: msg.conteudo,
          createdAt: msg.created_at,
          originalId: msg.id,
        })));
      }

      // 2. Fetch system alerts from backend (frequency-based per-child alerts)
      try {
        const backendAlerts = await apiService.listarAlertas();
        if (Array.isArray(backendAlerts)) {
          allAlerts.push(...backendAlerts.map(alert => ({
            id: alert.id,
            type: 'no-record',
            title: alert.titulo,
            subtitle: alert.resumo,
            content: alert.conteudo,
            createdAt: alert.criado_em,
            originalId: alert.id,
            alertType: alert.tipo,
          })));
        }
      } catch (alertErr) {
        console.error('Erro ao buscar alertas do sistema:', alertErr);
      }

      allAlerts.sort((a, b) => new Date(b.createdAt) - new Date(a.createdAt));
      setAlerts(allAlerts);

    } catch (error) {
      toast({ variant: "destructive", title: "Erro ao buscar alertas", description: error.message });
    } finally {
      setLoading(false);
    }
  }, [user, toast]);

  useEffect(() => {
    fetchAlertsAndMessages();
  }, [fetchAlertsAndMessages]);

  const handleDismiss = async (alert) => {
    if (!user) return;
    try {
      if (alert.type === 'message') {
        const { error } = await apiClient.from('mensagens_lidas').insert({ mensagem_id: alert.originalId, usuario_id: user.id });
        if (error) throw error;
      } else {
        const { error } = await apiClient.from('alertas_lidos').insert({
            usuario_id: user.id,
            alerta_tipo: alert.alertType || alert.type,
            alerta_chave: alert.originalId
        });
        if (error) throw error;
      }
      setAlerts(prevAlerts => prevAlerts.filter(a => a.id !== alert.id));
      toast({ title: "Notifica\u00e7\u00e3o marcada como lida!" });
    } catch (error) {
      toast({ variant: "destructive", title: "Erro ao marcar como lido", description: error.message });
    }
  };

  if (loading) {
    return (
      <div className="mt-10 flex justify-center items-center h-40">
        <Loader2 className="h-8 w-8 text-roxo-principal animate-spin" />
      </div>
    );
  }

  if (!alerts || alerts.length === 0) {
    return (
      <div className="mt-10 text-center p-6 bg-white rounded-2xl shadow-sm border border-gray-100">
        <CheckCircle className="h-12 w-12 text-green-500 mx-auto mb-4" />
        <h3 className="text-lg font-semibold text-gray-800">Nenhum alerta no momento.</h3>
        <p className="text-texto-medio mt-1">Tudo em dia por aqui!</p>
      </div>
    );
  }

  return (
    <div className="mt-10">
      <h2 className="text-xl font-bold text-gray-800 mb-4">Alertas e Mensagens</h2>
      <div className="space-y-0">
        <AnimatePresence>
          {alerts.map(alert => (
            <AlertCard key={alert.id} alert={alert} onDismiss={handleDismiss} />
          ))}
        </AnimatePresence>
      </div>
    </div>
  );
};

export default AlertsAndMessagesCenter;
