import React, { useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useToast } from '@/components/ui/use-toast';
import { authFetch } from '@/services/api';

const ChangePasswordModal = ({ open, onOpenChange }) => {
  const { toast } = useToast();
  const [senhaAtual, setSenhaAtual] = useState('');
  const [novaSenha, setNovaSenha] = useState('');
  const [confirmarSenha, setConfirmarSenha] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const resetForm = () => {
    setSenhaAtual('');
    setNovaSenha('');
    setConfirmarSenha('');
  };

  const handleOpenChange = (nextOpen) => {
    if (!nextOpen) {
      resetForm();
    }
    onOpenChange(nextOpen);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (novaSenha !== confirmarSenha) {
      toast({
        variant: 'destructive',
        title: 'Confirmação inválida',
        description: 'A nova senha e a confirmação devem ser iguais.',
      });
      return;
    }

    setIsLoading(true);
    try {
      const response = await authFetch('/api/auth/alterar-senha/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          senha_atual: senhaAtual,
          nova_senha: novaSenha,
          confirmar_senha: confirmarSenha,
        }),
      });

      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        toast({
          variant: 'destructive',
          title: 'Não foi possível alterar a senha',
          description: data.error || 'Verifique os dados e tente novamente.',
        });
        return;
      }

      toast({
        title: 'Senha alterada!',
        description: data.message || 'Sua nova senha já está ativa.',
      });
      handleOpenChange(false);
    } catch {
      toast({
        variant: 'destructive',
        title: 'Erro de conexão',
        description: 'Não foi possível conectar ao servidor. Tente novamente.',
      });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Trocar senha</DialogTitle>
          <DialogDescription>
            Informe sua senha atual e escolha uma nova senha com pelo menos 8 caracteres.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <fieldset className="space-y-4">
            <legend className="sr-only">Dados da nova senha</legend>
            <p className="space-y-2">
              <Label htmlFor="senhaAtual">Senha atual</Label>
              <Input
                id="senhaAtual"
                type="password"
                autoComplete="current-password"
                value={senhaAtual}
                onChange={(e) => setSenhaAtual(e.target.value)}
                required
              />
            </p>
            <p className="space-y-2">
              <Label htmlFor="novaSenha">Nova senha</Label>
              <Input
                id="novaSenha"
                type="password"
                autoComplete="new-password"
                minLength={8}
                value={novaSenha}
                onChange={(e) => setNovaSenha(e.target.value)}
                required
              />
            </p>
            <p className="space-y-2">
              <Label htmlFor="confirmarSenha">Confirmar nova senha</Label>
              <Input
                id="confirmarSenha"
                type="password"
                autoComplete="new-password"
                minLength={8}
                value={confirmarSenha}
                onChange={(e) => setConfirmarSenha(e.target.value)}
                required
              />
            </p>
          </fieldset>
          <DialogFooter className="gap-2 sm:gap-0">
            <Button
              type="button"
              variant="outline"
              onClick={() => handleOpenChange(false)}
              disabled={isLoading}
            >
              Cancelar
            </Button>
            <Button type="submit" disabled={isLoading}>
              {isLoading ? 'Salvando...' : 'Salvar nova senha'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
};

export default ChangePasswordModal;
