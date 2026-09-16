import React, { useEffect, useState } from 'react';
import { Bell, Loader2 } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { apiService } from '@/services/api';
import { apiClient } from '@/lib/apiClient';
import { useAuth } from '@/contexts/AuthContext';
import { useToast } from '@/components/ui/use-toast';

const truncateText = (text, maxLength) => {
  if (!text) return '';
  if (text.length <= maxLength) return text;
  return `${text.substring(0, maxLength - 1)}…`;
};

const NotificationsBell = () => {
  const { user } = useAuth();
  const { toast } = useToast();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(false);

  // Fetch alert count on mount so the red dot renders immediately
  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    apiService.listarAlertas()
      .then((data) => { if (!cancelled) setAlerts(Array.isArray(data) ? data : []); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [user]);

  // Re-fetch when the popover opens for fresh data
  useEffect(() => {
    if (!open || !user) return;

    const fetchAlerts = async () => {
      setLoading(true);
      try {
        const data = await apiService.listarAlertas();
        setAlerts(Array.isArray(data) ? data : []);
      } catch (error) {
        toast({
          variant: 'destructive',
          title: 'Erro ao carregar alertas',
          description: 'N\u00e3o foi poss\u00edvel buscar as notifica\u00e7\u00f5es.',
        });
      } finally {
        setLoading(false);
      }
    };

    fetchAlerts();
  }, [open, user, toast]);

  const handleOpenDetail = async (alert) => {
    if (!user) return;

    try {
      await apiClient.from('alertas_lidos').insert({
        usuario_id: user.id,
        alerta_tipo: alert.tipo,
        alerta_chave: alert.id,
      });
      setAlerts((prev) => prev.filter((item) => item.id !== alert.id));
    } catch (error) {
      toast({
        variant: 'destructive',
        title: 'Erro ao marcar alerta',
        description: 'Não foi possível marcar o alerta como lido.',
      });
    } finally {
      const params = new URLSearchParams({
        tipo: alert.tipo,
        chave: alert.id,
      });
      navigate(`/notificacoes?${params.toString()}`);
      setOpen(false);
    }
  };

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button variant="ghost" size="icon" className="relative">
          <Bell className="h-6 w-6 text-gray-600" />
          {alerts.length > 0 && (
            <span className="absolute right-2 top-2 flex h-2.5 w-2.5 rounded-full bg-red-500" />
          )}
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-80" alignOffset={-35}>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-gray-800">Notificações</h3>
          {alerts.length > 0 && (
            <span className="text-xs text-gray-500">{alerts.length} não lida(s)</span>
          )}
        </div>

        {loading ? (
          <div className="flex items-center gap-2 text-gray-500 text-sm">
            <Loader2 className="h-4 w-4 animate-spin" />
            <span>Carregando alertas...</span>
          </div>
        ) : alerts.length === 0 ? (
          <p className="text-sm text-gray-500">Nenhum alerta pendente no momento.</p>
        ) : (
          <div className="space-y-3 max-h-72 overflow-auto">
            {alerts.map((alert) => (
              <button
                key={`${alert.tipo}-${alert.id}`}
                type="button"
                onClick={() => handleOpenDetail(alert)}
                className="w-full text-left border border-gray-200 rounded-lg p-3 hover:bg-gray-50 transition-colors"
              >
                <p className="text-sm font-semibold text-gray-800">{truncateText(alert.titulo, 60)}</p>
                <p className="text-xs text-gray-500 mt-1">{truncateText(alert.resumo, 120)}</p>
              </button>
            ))}
          </div>
        )}
      </PopoverContent>
    </Popover>
  );
};

export default NotificationsBell;
