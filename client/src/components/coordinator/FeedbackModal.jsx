import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Label } from '@/components/ui/label';
import { MessageSquare, Sparkles, Send, Edit, X } from 'lucide-react';
import { useToast } from '@/components/ui/use-toast';

const iaSuggestions = {
  planejamento: "Observei que o campo ‘Traços, sons, cores e formas’ não foi abordado esta semana. Sugerimos incluir uma proposta artística sensorial.",
  relatorio: "O relatório da criança está afetivo e fluido, mas a parte de Psicomotricidade ainda não foi registrada. Que tal solicitar ao especialista?",
  portfolio: "Seu planejamento está sensível e completo. Parabéns pela intencionalidade nas atividades propostas!",
  registro: "O registro de observação está muito rico em detalhes. Excelente trabalho!"
};

const FeedbackModal = ({ isOpen, onClose, teacherName, feedbackType }) => {
  const { toast } = useToast();
  const [comment, setComment] = useState('');
  const [type, setType] = useState(feedbackType || 'planejamento');

  const handleSend = () => {
    if (comment.trim() === '') {
      toast({
        title: 'Campo vazio',
        description: 'Por favor, escreva um comentário antes de enviar.',
        variant: 'destructive',
      });
      return;
    }
    toast({
      title: '✅ Devolutiva enviada!',
      description: `Sua mensagem foi enviada com sucesso para ${teacherName}.`,
      className: 'bg-green-100 border-green-300 text-green-800',
    });
    onClose();
    setComment('');
  };

  const handleIaSuggestion = () => {
    setComment(iaSuggestions[type] || "Excelente trabalho, continue assim!");
     toast({
      title: '✨ Sugestão da IA aplicada!',
      description: 'Um texto foi gerado para você. Sinta-se à vontade para editar.',
      className: 'bg-purple-100 border-purple-300 text-purple-800',
    });
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-2xl bg-[#F5F3FA] rounded-2xl p-0">
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}>
          <DialogHeader className="p-6 bg-white">
            <div className="flex items-center gap-3">
              <div className="bg-[#D7CDEB] p-3 rounded-full">
                <MessageSquare className="h-6 w-6 text-[#8A63D2]" />
              </div>
              <div>
                <DialogTitle className="text-2xl font-extrabold text-gray-800">Nova Devolutiva Pedagógica</DialogTitle>
                <DialogDescription>Para: {teacherName}</DialogDescription>
              </div>
            </div>
          </DialogHeader>
          
          <div className="p-6 space-y-4">
            <div>
              <Label htmlFor="feedback-type" className="font-semibold text-gray-700">Tipo de Devolutiva</Label>
              <Select value={type} onValueChange={setType}>
                <SelectTrigger id="feedback-type">
                  <SelectValue placeholder="Selecione o tipo" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="planejamento">Planejamento</SelectItem>
                  <SelectItem value="registro">Registro de Observação</SelectItem>
                  <SelectItem value="portfolio">Portfólio</SelectItem>
                  <SelectItem value="relatorio">Relatório</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label htmlFor="comment" className="font-semibold text-gray-700">Comentário</Label>
              <div className="relative">
                <Textarea
                  id="comment"
                  value={comment}
                  onChange={(e) => setComment(e.target.value)}
                  placeholder="Escreva sua devolutiva aqui..."
                  className="min-h-[150px]"
                  maxLength={800}
                />
                <Button
                  variant="ghost"
                  size="icon"
                  className="absolute bottom-2 right-2 text-yellow-500 hover:bg-yellow-100"
                  onClick={handleIaSuggestion}
                >
                  <Sparkles className="h-5 w-5" />
                </Button>
              </div>
              <p className="text-xs text-right text-gray-500 mt-1">{comment.length}/800</p>
            </div>
          </div>

          <DialogFooter className="p-6 bg-white/50 flex-col sm:flex-row gap-2">
            <Button variant="outline" className="w-full sm:w-auto" onClick={onClose}>
              <X className="h-4 w-4 mr-2" /> Cancelar
            </Button>
            <Button variant="secondary" className="w-full sm:w-auto" onClick={() => toast({ title: '🚧 Em breve!', description: 'Funcionalidade de salvar para editar depois será implementada.' })}>
              <Edit className="h-4 w-4 mr-2" /> Editar Depois
            </Button>
            <Button className="nara-gradient text-white btn-hover w-full sm:w-auto" onClick={handleSend}>
              <Send className="h-4 w-4 mr-2" /> Enviar Devolutiva
            </Button>
          </DialogFooter>
        </motion.div>
      </DialogContent>
    </Dialog>
  );
};

export default FeedbackModal;