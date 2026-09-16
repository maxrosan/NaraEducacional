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
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { MessageSquare, Send } from 'lucide-react';
import { useToast } from '@/components/ui/use-toast';

const MessageModal = ({ isOpen, onClose, teacher }) => {
  const { toast } = useToast();
  const [message, setMessage] = useState('');

  if (!teacher) return null;

  const handleSendMessage = () => {
    if (!message.trim()) {
      toast({
        variant: 'destructive',
        title: 'Mensagem vazia',
        description: 'Por favor, escreva uma mensagem antes de enviar.',
      });
      return;
    }
    
    console.log(`Enviando mensagem para ${teacher.email}: "${message}"`);
    
    toast({
      title: 'Mensagem enviada!',
      description: `Sua mensagem para ${teacher.nome} foi enviada com sucesso.`,
      className: 'bg-green-100 text-green-800 border-green-200',
    });
    
    setMessage('');
    onClose();
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-[425px] bg-white/90 backdrop-blur-sm">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-3 text-xl text-roxo-principal">
            <MessageSquare className="h-6 w-6" />
            Enviar Mensagem
          </DialogTitle>
          <DialogDescription>
            Escreva uma mensagem para o professor {teacher.nome}.
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 py-4">
          <div className="grid grid-cols-4 items-center gap-4">
            <Label htmlFor="recipient" className="text-right">
              Para
            </Label>
            <Input id="recipient" value={teacher.nome} disabled className="col-span-3" />
          </div>
          <div className="grid grid-cols-4 items-start gap-4">
            <Label htmlFor="message" className="text-right pt-2">
              Mensagem
            </Label>
            <Textarea
              id="message"
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              placeholder="Digite sua mensagem aqui..."
              className="col-span-3 min-h-[120px]"
            />
          </div>
        </div>
        <DialogFooter>
          <Button onClick={onClose} variant="outline">Cancelar</Button>
          <Button onClick={handleSendMessage}>
            <Send className="h-4 w-4 mr-2" />
            Enviar
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default MessageModal;