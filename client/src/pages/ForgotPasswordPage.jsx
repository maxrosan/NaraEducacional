import React, { useState } from 'react';
import { Helmet } from 'react-helmet-async';
import { Link } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useToast } from '@/components/ui/use-toast';
import { authFetch } from '@/services/api';

const ForgotPasswordPage = () => {
    const [email, setEmail] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [sent, setSent] = useState(false);
    const { toast } = useToast();

    const handleSubmit = async (e) => {
        e.preventDefault();
        setIsLoading(true);
        try {
            await authFetch('/api/auth/recuperar-senha/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email }),
            });
            setSent(true);
        } catch {
            toast({ variant: 'destructive', title: 'Erro ao enviar e-mail.' });
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <>
            <Helmet><title>NARA - Recuperar Senha</title></Helmet>
            <div className="min-h-screen flex items-center justify-center px-4 bg-white">
                <div className="w-full max-w-md space-y-6">
                    <img src="/nara-logo.png" alt="NARA" className="h-20 mx-auto" />
                    <h1 className="text-xl font-bold text-center text-gray-800">Recuperar senha</h1>

                    {sent ? (
                        <p className="text-center text-gray-600">
                            Se o e-mail estiver cadastrado, você receberá as instruções em breve.
                        </p>
                    ) : (
                        <form onSubmit={handleSubmit} className="space-y-4">
                            <div>
                                <Label htmlFor="email">E-mail</Label>
                                <Input id="email" type="email" value={email} onChange={e => setEmail(e.target.value)} required />
                            </div>
                            <Button type="submit" className="w-full" disabled={isLoading}>
                                <span>{isLoading ? 'Enviando...' : 'Recuperar senha'}</span>
                            </Button>
                        </form>
                    )}

                    <p className="text-center text-sm">
                        <Link to="/login" className="text-purple-600 hover:underline">Voltar ao login</Link>
                    </p>
                </div>
            </div>
        </>
    );
};

export default ForgotPasswordPage;