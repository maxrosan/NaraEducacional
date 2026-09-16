import React, { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogClose } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";

const EspecialistaFormDialog = ({ isOpen, setIsOpen, especialista, onSubmit, tiposEspecialistaPadrao }) => {
    const [formData, setFormData] = useState({});

    useEffect(() => {
        if (isOpen) {
            const isTipoPadrao = especialista?.tipo_especialista && tiposEspecialistaPadrao.includes(especialista.tipo_especialista);
            const initialData = {
                nome: especialista?.nome || '',
                email: especialista?.email || '',
                tipo_especialista: especialista ? (isTipoPadrao ? especialista.tipo_especialista : 'Outros') : '',
                tipo_especialista_outro: especialista && !isTipoPadrao ? especialista.tipo_especialista : '',
                ativo: especialista?.ativo ?? true,
                password: '',
            };
            if (!especialista) {
                initialData.password = Math.random().toString(36).slice(-8);
            }
            setFormData(initialData);
        }
    }, [especialista, isOpen, tiposEspecialistaPadrao]);

    const handleChange = (e) => {
        const { name, value, type, checked } = e.target;
        setFormData(prev => ({ ...prev, [name]: type === 'checkbox' ? checked : value }));
    };

    const handleSelectChange = (name, value) => {
        setFormData(prev => ({...prev, [name]: value}));
    };

    const handleSubmit = (e) => {
        e.preventDefault();
        onSubmit(formData);
    };

    return (
        <Dialog open={isOpen} onOpenChange={setIsOpen}>
            <DialogContent className="max-h-[90vh] overflow-y-auto">
                <DialogHeader>
                    <DialogTitle>{especialista ? 'Editar Especialista' : 'Novo Especialista'}</DialogTitle>
                </DialogHeader>
                <form onSubmit={handleSubmit} className="space-y-4 pt-4">
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        <div>
                            <Label htmlFor="nome">Nome Completo</Label>
                            <Input id="nome" name="nome" value={formData.nome || ''} onChange={handleChange} required />
                        </div>
                        <div>
                            <Label htmlFor="email">Email</Label>
                            <Input id="email" name="email" type="email" value={formData.email || ''} onChange={handleChange} required disabled={!!especialista} />
                        </div>
                    </div>
                    {!especialista && (
                        <div>
                            <Label htmlFor="password">Senha Provisória</Label>
                            <Input id="password" name="password" type="text" value={formData.password || ''} onChange={handleChange} required />
                        </div>
                    )}
                    <div className="space-y-2">
                        <Label htmlFor="tipo_especialista">Tipo de Especialista</Label>
                        <Select
                            name="tipo_especialista"
                            required
                            value={formData.tipo_especialista || ''}
                            onValueChange={(v) => handleSelectChange('tipo_especialista', v)}
                        >
                            <SelectTrigger id="tipo_especialista">
                                <SelectValue placeholder="Selecione o tipo" />
                            </SelectTrigger>
                            <SelectContent>
                                {tiposEspecialistaPadrao.map(tipo => (
                                    <SelectItem key={tipo} value={tipo}>{tipo}</SelectItem>
                                ))}
                                <SelectItem value="Outros">Outros</SelectItem>
                            </SelectContent>
                        </Select>
                    </div>

                    {formData.tipo_especialista === 'Outros' && (
                         <div>
                            <Label htmlFor="tipo_especialista_outro">Especifique o tipo</Label>
                            <Input 
                                id="tipo_especialista_outro"
                                name="tipo_especialista_outro"
                                value={formData.tipo_especialista_outro || ''}
                                onChange={handleChange}
                                placeholder="Digite o tipo de especialista"
                                required
                            />
                        </div>
                    )}

                    <div className="flex items-center space-x-2">
                        <Checkbox id="ativo" name="ativo" checked={formData.ativo} onCheckedChange={(checked) => setFormData(p => ({ ...p, ativo: checked }))} />
                        <Label htmlFor="ativo">Usuário Ativo</Label>
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

export default EspecialistaFormDialog;