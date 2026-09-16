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
import { BarChart3, Calendar, Clock, Smartphone, Monitor, Loader2 } from 'lucide-react';
import { format, isValid } from 'date-fns';
import { ptBR } from 'date-fns/locale';
import { apiClient } from '@/lib/apiClient';
import { safeFormatDate } from '@/lib/dateUtils';

const LoginHistoryModal = ({ isOpen, onClose, teacher }) => {
  const [loginHistory, setLoginHistory] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const fetchLoginHistory = async () => {
      if (!isOpen || !teacher) return;
      setLoading(true);
      
      try {
        // We will call the get_audit_logs function which is more secure and is designed for this.
        const { data, error } = await apiClient.rpc('get_audit_logs');
        if (error) throw error;
        
        const teacherLogs = data
          .filter(log => log.user_email === teacher.email)
          .map(log => ({
            timestamp: new Date(log.timestamp),
            // Device detection would require more info from logs (e.g., user agent in payload)
            // For now, we'll keep it as a placeholder.
            device: 'desktop'
          }))
          .filter(entry => isValid(entry.timestamp))
          .sort((a, b) => b.timestamp - a.timestamp);

        setLoginHistory(teacherLogs);
      } catch (error) {
        console.error('Error fetching login history:', error);
        // Fallback to empty array on error
        setLoginHistory([]);
      } finally {
        setLoading(false);
      }
    };

    fetchLoginHistory();
  }, [isOpen, teacher]);

  if (!teacher) return null;

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-md bg-white/90 backdrop-blur-sm">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-3 text-xl text-roxo-principal">
            <BarChart3 className="h-6 w-6" />
            Histórico de Login
          </DialogTitle>
          <DialogDescription>
            Registros de acesso para {teacher.nome}.
          </DialogDescription>
        </DialogHeader>
        <ScrollArea className="h-72 w-full pr-4">
          {loading ? (
            <div className="flex justify-center items-center h-full">
              <Loader2 className="h-8 w-8 animate-spin text-roxo-principal" />
            </div>
          ) : loginHistory.length > 0 ? (
            <div className="space-y-4">
              {loginHistory.map((entry, index) => (
                <div key={index} className="flex items-center gap-4 p-3 bg-lavanda-claro rounded-lg">
                  {entry.device === 'mobile' ? (
                    <Smartphone className="h-6 w-6 text-roxo-principal" />
                  ) : (
                    <Monitor className="h-6 w-6 text-roxo-principal" />
                  )}
                  <div>
                    <p className="font-semibold text-texto-escuro flex items-center gap-2">
                      <Calendar className="h-4 w-4" />
                      {safeFormatDate(entry.timestamp, "dd 'de' MMMM 'de' yyyy", { locale: ptBR })}
                    </p>
                    <p className="text-sm text-texto-medio flex items-center gap-2">
                      <Clock className="h-4 w-4" />
                      às {safeFormatDate(entry.timestamp, "HH:mm", { locale: ptBR })}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center text-texto-medio py-10">
              Nenhum histórico de login encontrado.
            </div>
          )}
        </ScrollArea>
        <DialogFooter>
          <Button onClick={onClose} variant="outline">Fechar</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default LoginHistoryModal;