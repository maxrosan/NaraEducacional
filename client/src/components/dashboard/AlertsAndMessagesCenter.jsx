import React, { useEffect, useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { listarNotificacoes, marcarNotificacaoLida } from '@/services/api';
import { useAuth } from '@/contexts/AuthContext';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { MessageSquare, CheckCircle, AlertTriangle, AlertCircle, Loader2 } from 'lucide-react';
import { useToast } from '@/components/ui/use-toast';

/*
 * ALTERADO: mensagens da coordenação e alertas do sistema vêm agora da mesma
 * fonte, a tabela `notificacoes` (GET notificacoes/?lidas=false). Cada usuário
 * tem a própria cópia de cada notificação; "Ok, entendido" preenche `lido_em`
 * (POST notificacoes/<id>/marcar-lida/). As tabelas mensagens_coordenacao,
 * mensagens_lidas e alertas_lidos não existem no backend multi-tenant.
 */

/** Tipos de notificação exibidos como alerta (vermelho). Os demais são mensagem. */
const TIPOS_ALERTA = new Set(['alerta', 'sem_registro', 'no-record']);

function paraCartao(n) {
  const ehAlerta = TIPOS_ALERTA.has((n.tipo || '').toLowerCase());
  return {
    id: n.id,
    type: ehAlerta ? 'no-record' : 'message',
    title: n.titulo || (ehAlerta ? 'Alerta' : 'Mensagem da Coordenação'),
    subtitle: n.remetente_nome ? `Enviado por ${n.remetente_nome}` : 'Aviso do sistema',
    content: n.conteudo,
    createdAt: n.criado_em,
  };
}

const AlertCard = ({ alert, onDismiss, dismissing }) => {
  const icons = {
    'no-record': <AlertTriangle className="h-5 w-5 text-red-500" />,
    message: <MessageSquare className="h-5 w-5 text-roxo-principal" />,
    default: <AlertCircle className="h-5 w-5 text-yellow-500" />,
  };
  const colors = {
    'no-record': 'border-red-200 bg-red-50',
    message: 'border-lavanda bg-lavanda-claro',
    default: 'border-yellow-200 bg-yellow-50',
  };

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
      <Card className={`${cardClass} shadow-sm overflow-hidden mb-4`}>
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
          <p className="text-sm text-texto-escuro mb-4 whitespace-pre-line">{alert.content}</p>
          <Button
            onClick={() => onDismiss(alert)}
            disabled={dismissing}
            className="w-full bg-roxo-principal hover:bg-roxo-principal/90"
            size="sm"
          >
            {dismissing
              ? <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              : <CheckCircle className="mr-2 h-4 w-4" />}
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
  const [dismissingId, setDismissingId] = useState(null);

  const fetchAlertsAndMessages = useCallback(async () => {
    if (!user) {
      setLoading(false);
      return;
    }
    try {
      setLoading(true);
      const notificacoes = await listarNotificacoes({ apenasNaoLidas: true });
      const cartoes = (notificacoes || []).map(paraCartao);
      cartoes.sort((a, b) => new Date(b.createdAt) - new Date(a.createdAt));
      setAlerts(cartoes);
    } catch (error) {
      toast({ variant: 'destructive', title: 'Erro ao buscar alertas', description: error.message });
    } finally {
      setLoading(false);
    }
  }, [user, toast]);

  useEffect(() => {
    fetchAlertsAndMessages();
  }, [fetchAlertsAndMessages]);

  const handleDismiss = async (alert) => {
    if (!user) return;
    setDismissingId(alert.id);
    try {
      await marcarNotificacaoLida(alert.id);
      setAlerts((prev) => prev.filter((a) => a.id !== alert.id));
      toast({ title: 'Notificação marcada como lida!' });
    } catch (error) {
      toast({ variant: 'destructive', title: 'Erro ao marcar como lido', description: error.message });
    } finally {
      setDismissingId(null);
    }
  };

  if (loading) {
    return (
      <div className="mt-10 flex justify-center items-center h-40">
        <Loader2 className="h-8 w-8 text-roxo-principal animate-spin" />
      </div>
    );
  }

  if (alerts.length === 0) {
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
          {alerts.map((alert) => (
            <AlertCard
              key={alert.id}
              alert={alert}
              onDismiss={handleDismiss}
              dismissing={dismissingId === alert.id}
            />
          ))}
        </AnimatePresence>
      </div>
    </div>
  );
};

export default AlertsAndMessagesCenter;