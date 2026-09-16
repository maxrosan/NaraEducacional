import React, { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { AlertTriangle, Send, Loader2 } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { useToast } from '@/components/ui/use-toast';
import { useAuth } from '@/contexts/AuthContext';
import apiClient from '@/lib/apiClient';
import { apiService } from '@/services/api';

const AlertItem = ({ alert, onActionClick, delay, disabled }) => {
    const icon = <AlertTriangle className="h-5 w-5 text-red-500" />;

    return (
        <motion.div
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.5, delay }}
        >
            <Card className="hover:shadow-md transition-shadow">
                <CardContent className="p-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
                    <div className="flex items-start gap-4">
                        <div className="mt-1">{icon}</div>
                        <div>
                            <p className="font-bold text-gray-800">{alert.titulo}</p>
                            <p className="text-sm text-gray-600">{alert.resumo}</p>
                        </div>
                    </div>
                    <Button
                      size="sm"
                      variant="ghost"
                      className="text-purple-600 hover:bg-purple-50 self-end sm:self-center"
                      onClick={() => onActionClick(alert)}
                      disabled={disabled}
                    >
                        <Send className="h-4 w-4 mr-2" />
                        <span className="whitespace-nowrap">Ver detalhes</span>
                    </Button>
                </CardContent>
            </Card>
        </motion.div>
    );
};

const AlertsView = () => {
  const { toast } = useToast();
  const { user } = useAuth();
  const navigate = useNavigate();
  const [alerts, setAlerts] = useState([]);
  const [loadingRead, setLoadingRead] = useState(true);
  const [markingKey, setMarkingKey] = useState(null);

  useEffect(() => {
    const fetchAlerts = async () => {
      if (!user) {
        setLoadingRead(false);
        return;
      }
      try {
        const data = await apiService.listarAlertas();
        setAlerts(Array.isArray(data) ? data : []);
      } catch (error) {
        console.error('Erro ao buscar alertas:', error);
        toast({ title: 'Erro ao carregar alertas', description: 'Não foi possível buscar as notificações.', variant: 'destructive' });
      } finally {
        setLoadingRead(false);
      }
    };

    fetchAlerts();
  }, [user]);

  const handleActionClick = async (alert) => {
    if (!user) {
      toast({ title: 'Sessão inválida', description: 'Faça login novamente para gerenciar alertas.', variant: 'destructive' });
      return;
    }

    const key = `${alert.tipo}:${alert.id}`;
    setMarkingKey(key);
    try {
      const payload = {
        usuario_id: user.id,
        alerta_tipo: alert.tipo || 'registro-semanal',
        alerta_chave: alert.id,
      };

      const { error } = await apiClient.from('alertas_lidos').insert(payload);
      if (error) {
        throw new Error(error.message || 'Erro ao marcar alerta como lido');
      }

      setAlerts((prev) => prev.filter((item) => item.id !== alert.id));
      const params = new URLSearchParams({ tipo: alert.tipo, chave: alert.id });
      navigate(`/notificacoes?${params.toString()}`);
    } catch (error) {
      console.error('Erro ao marcar alerta como lido:', error);
      toast({ title: 'Erro', description: error.message, variant: 'destructive' });
    } finally {
      setMarkingKey(null);
    }
  };

  if (!alerts) {
    return (
      <div className="flex justify-center items-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-purple-500" />
      </div>
    );
  }

  return (
    <Card className="bg-white/50">
      <CardHeader>
        <CardTitle className="flex items-center gap-3 text-xl">
          <AlertTriangle className="h-6 w-6 text-red-500" />
          Central de Alertas
        </CardTitle>
      </CardHeader>
      <CardContent>
        {loadingRead ? (
          <div className="flex items-center justify-center py-10 text-gray-500 gap-2">
            <Loader2 className="h-5 w-5 animate-spin" />
            <span>Carregando alertas...</span>
          </div>
        ) : (
          <div className="space-y-4">
            {alerts.length === 0 ? (
              <p className="text-center text-gray-500 py-8">Nenhum alerta no momento. Bom trabalho!</p>
            ) : (
              alerts.map((alert, index) => (
                <AlertItem
                  key={alert.id}
                  alert={alert}
                  onActionClick={handleActionClick}
                  delay={index * 0.1}
                  disabled={markingKey === `${alert.tipo}:${alert.id}`}
                />
              ))
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default AlertsView;
