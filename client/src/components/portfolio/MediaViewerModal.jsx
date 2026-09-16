import React from 'react';
import { motion } from 'framer-motion';
import { format } from 'date-fns';
import { ptBR } from 'date-fns/locale';
import { safeFormatDate } from '@/lib/dateUtils';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Calendar, Tag, Trash2 } from 'lucide-react';

export const MediaViewerModal = ({ isOpen, onOpenChange, media, onRemove }) => {
  if (!media) return null;

  const isVideo = media.type === 'video';

  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogContent className="bg-[#F5F3FA] max-w-3xl p-0">
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.3 }}
        >
          <div className="relative">
            {isVideo ? (
              <video controls autoPlay className="w-full h-auto max-h-[70vh] rounded-t-2xl bg-black">
                <source src={media.url} type="video/mp4" />
                Seu navegador não suporta o player de vídeo.
              </video>
            ) : (
              <img  src={media.url} alt={media.caption} className="w-full h-auto max-h-[70vh] object-contain rounded-t-2xl bg-black" />
            )}
          </div>
          <div className="p-6">
            <DialogHeader>
              <DialogDescription className="text-base text-gray-700">{media.caption}</DialogDescription>
            </DialogHeader>
            <div className="flex flex-wrap gap-4 text-sm text-gray-500 mt-4">
              <div className="flex items-center gap-2">
                <Calendar className="h-4 w-4" />
                <span>{safeFormatDate(media.date, "dd 'de' MMMM 'de' yyyy", { locale: ptBR })}</span>
              </div>
              {media.project && (
                <div className="flex items-center gap-2">
                  <Tag className="h-4 w-4" />
                  <span>{media.project}</span>
                </div>
              )}
            </div>
            <DialogFooter className="mt-6">
              <Button variant="destructive" onClick={() => onRemove(media.id)}>
                <Trash2 className="h-4 w-4 mr-2" />
                Remover do Portfólio
              </Button>
            </DialogFooter>
          </div>
        </motion.div>
      </DialogContent>
    </Dialog>
  );
};