import React, { useState, useEffect } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';

const EditPortfolioItemModal = ({ item, isOpen, onClose, onSave }) => {
  const [descricao, setDescricao] = useState('');
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    if (item) {
      setDescricao(item.descricao || '');
    }
  }, [item]);

  const handleSave = async () => {
    setIsSaving(true);
    await onSave({ ...item, descricao });
    setIsSaving(false);
    onClose();
  };

  if (!item) return null;

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Editar Registro do Portfólio</DialogTitle>
          <DialogDescription>
            Ajuste a legenda deste registro.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4 py-4">
          <div className="space-y-2">
            <Label htmlFor="descricao">Legenda</Label>
            <Textarea
              id="descricao"
              value={descricao}
              onChange={(e) => setDescricao(e.target.value)}
              rows={4}
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>Cancelar</Button>
          <Button onClick={handleSave} disabled={isSaving}>
            <span>{isSaving ? 'Salvando...' : 'Salvar Alterações'}</span>
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default EditPortfolioItemModal;
