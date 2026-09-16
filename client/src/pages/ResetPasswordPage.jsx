import React, { useState } from 'react';
import { Helmet } from 'react-helmet-async';
import { useNavigate, useSearchParams, Link } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useToast } from '@/components/ui/use-toast';
import { authFetch } from '@/services/api';


const ResetPasswordPage = () => {
    const [params] = useSearchParams();
    const navigate = useNavigate();
    const { toast } = useToast();
    const [novaSenha, setNovaSenha] = useState('');
    const [isLoading, setIsLoading] = useState(false);

    const handleSubmit = async (e) => {
        e.preventDefault();
        setIsLoading(true);
        try {
            await authFetch('/api/auth/confirmar-senha/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    uid: params.get('uid'),
                    token: params.get('token'),
                    nova_senha: novaSenha,
                }),
            });
            toast({ title: 'Senha redefinida!', description: 'Faça login com sua nova senha.' });
            navigate('/login');
        } catch (err) {
            toast({ variant: 'destructive', title: 'Link inválido ou expirado.' });
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <>
            <Helmet><title>NARA - Redefinir Senha</title></Helmet>
            <div className="min-h-screen flex items-center justify-center px-4 bg-white">
                <div className="w-full max-w-md space-y-6">
                    <img src="/nara-logo.png" alt="NARA" className="h-20 mx-auto" />
                    <h1 className="text-xl font-bold text-center text-gray-800">Redefinir senha</h1>
                    <form onSubmit={handleSubmit} className="space-y-4">
                        <div>
                            <Label htmlFor="novaSenha">Nova senha</Label>
                            <Input id="novaSenha" type="password" minLength={8} value={novaSenha}
                                onChange={e => setNovaSenha(e.target.value)} required />
                        </div>
                        <Button type="submit" className="w-full" disabled={isLoading}>
                            <span>{isLoading ? 'Salvando...' : 'Salvar nova senha'}</span>
                        </Button>
                    </form>
                    <p className="text-center text-sm">
                        <Link to="/login" className="text-purple-600 hover:underline">Voltar ao login</Link>
                    </p>
                </div>
            </div>
        </>
    );
};

export default ResetPasswordPage;