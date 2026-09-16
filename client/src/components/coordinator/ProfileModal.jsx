import React, { useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { User, Mail, Star, Users, Calendar, BookOpen, BarChart3 } from 'lucide-react';
import { format } from 'date-fns';
import { safeFormatDate } from '@/lib/dateUtils';
import { ptBR } from 'date-fns/locale';
import LoginHistoryModal from '@/components/coordinator/LoginHistoryModal';
import ContributionsModal from '@/components/coordinator/ContributionsModal';

const ProfileModal = ({ isOpen, onClose, teacher }) => {
  const [isLoginHistoryOpen, setLoginHistoryOpen] = useState(false);
  const [isContributionsOpen, setContributionsOpen] = useState(false);

  if (!teacher) return null;

  const getTurmasBadges = (turmas) => {
    if (!turmas || turmas.length === 0 || turmas.every(t => t === null)) {
      return <span className="text-gray-500">Nenhuma turma associada.</span>;
    }
    return turmas.filter(Boolean).map(t => <Badge key={t} className="mr-1 mb-1 bg-purple-100 text-purple-800 hover:bg-purple-200">{t}</Badge>);
  };

  const handleOpenLoginHistory = () => {
    setLoginHistoryOpen(true);
  };

  const handleOpenContributions = () => {
    setContributionsOpen(true);
  };

  return (
    <>
      <Dialog open={isOpen} onOpenChange={onClose}>
        <DialogContent className="sm:max-w-[525px] bg-white/90 backdrop-blur-sm">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-3 text-xl text-roxo-principal">
              <User className="h-6 w-6" />
              Perfil do Professor
            </DialogTitle>
            <DialogDescription>
              Informações detalhadas sobre o professor {teacher.nome}.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="flex items-center gap-4 p-3 bg-lavanda-claro rounded-lg">
              <Mail className="h-5 w-5 text-roxo-principal" />
              <div>
                <p className="font-semibold text-texto-escuro">Email</p>
                <p className="text-sm text-texto-medio">{teacher.email}</p>
              </div>
            </div>
            {teacher.especialidade && (
              <div className="flex items-center gap-4 p-3 bg-lavanda-claro rounded-lg">
                <Star className="h-5 w-5 text-roxo-principal" />
                <div>
                  <p className="font-semibold text-texto-escuro">Especialidade</p>
                  <p className="text-sm text-texto-medio">{teacher.especialidade}</p>
                </div>
              </div>
            )}
            <div className="flex items-start gap-4 p-3 bg-lavanda-claro rounded-lg">
              <Users className="h-5 w-5 text-roxo-principal mt-1" />
              <div>
                <p className="font-semibold text-texto-escuro">Turmas Associadas</p>
                <div className="flex flex-wrap mt-1">
                  {getTurmasBadges(teacher.turmas)}
                </div>
              </div>
            </div>
            <div className="flex items-center gap-4 p-3 bg-lavanda-claro rounded-lg">
              <Calendar className="h-5 w-5 text-roxo-principal" />
              <div>
                <p className="font-semibold text-texto-escuro">Último Acesso</p>
                <p className="text-sm text-texto-medio">
                  {safeFormatDate(teacher.ultimo_acesso, "dd 'de' MMMM 'de' yyyy, 'às' HH:mm", { locale: ptBR }, 'Nunca acessou')}
                </p>
              </div>
            </div>
            <div className="mt-4 border-t pt-4 space-y-2">
              <Button variant="ghost" className="w-full justify-start" onClick={handleOpenLoginHistory}>
                  <BarChart3 className="h-4 w-4 mr-2" /> Ver histórico de login
              </Button>
              <Button variant="ghost" className="w-full justify-start" onClick={handleOpenContributions}>
                  <BookOpen className="h-4 w-4 mr-2" /> Ver contribuições
              </Button>
            </div>
          </div>
          <DialogFooter>
            <Button onClick={onClose} variant="outline">Fechar</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <LoginHistoryModal
        isOpen={isLoginHistoryOpen}
        onClose={() => setLoginHistoryOpen(false)}
        teacher={teacher}
      />

      <ContributionsModal
        isOpen={isContributionsOpen}
        onClose={() => setContributionsOpen(false)}
        teacher={teacher}
      />
    </>
  );
};

export default ProfileModal;