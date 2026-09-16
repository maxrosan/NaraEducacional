import React, { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogClose } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";

const DisciplinaFormDialog = ({ isOpen, setIsOpen, disciplina, onSubmit }) => {
    const [formData, setFormData] = useState({});

    useEffect(() => {
        setFormData({
            nome: disciplina?.nome || '',
            ativo: disciplina?.ativo ?? true,
        });
    }, [disciplina, isOpen]);

    const handleChange = (e) => {
        const { name, value } = e.target;
        setFormData(prev => ({ ...prev, [name]: value }));
    };

    const handleSubmit = (e) => {
        e.preventDefault();
        onSubmit(formData);
    };

    return (
        <Dialog open={isOpen} onOpenChange={setIsOpen}>
            <DialogContent>
                <DialogHeader>
                    <DialogTitle>{disciplina ? 'Editar Disciplina' : 'Nova Disciplina'}</DialogTitle>
                </DialogHeader>
                <form onSubmit={handleSubmit} className="space-y-4 pt-4">
                    <div>
                        <Label htmlFor="nome">Nome</Label>
                        <Input
                            id="nome"
                            name="nome"
                            value={formData.nome || ''}
                            onChange={handleChange}
                            placeholder="Ex: Matemática"
                            required
                        />
                    </div>
                    <div className="flex items-center space-x-2">
                        <Checkbox
                            id="ativo"
                            name="ativo"
                            checked={formData.ativo}
                            onCheckedChange={(checked) => setFormData(p => ({ ...p, ativo: checked }))}
                        />
                        <Label htmlFor="ativo">Ativa</Label>
                    </div>
                    <DialogFooter>
                        <DialogClose asChild><Button type="button" variant="outline">Cancelar</Button></DialogClose>
                        <Button type="submit">Salvar</Button>
                    </DialogFooter>
                </form>
            </DialogContent>
        </Dialog>
    );
};

export default DisciplinaFormDialog;