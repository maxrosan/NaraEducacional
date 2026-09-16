import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { Eye, EyeOff, Mail, Lock } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useToast } from '@/components/ui/use-toast';
import { useAuth } from '@/contexts/AuthContext';
import { apiClient } from '@/lib/apiClient';
import { PERFIS_PROFESSOR } from '@/constants/perfis';
const LoginForm = () => {
  const [showPassword, setShowPassword] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const { toast } = useToast();
  const navigate = useNavigate();
  const { signIn } = useAuth();
  const [rememberMe, setRememberMe] = useState(false);
  const handleLogin = async (e) => {
    e.preventDefault();
    setIsLoading(true);
    try {
      const { error, data } = await signIn(email, password, rememberMe);
      if (error) {
        setIsLoading(false);
        return;
      }
      // O signIn já retorna os dados completos do usuário (perfil, id, etc.)
      const user = data?.user;
      if (!user) {
        throw new Error('Dados do usuário não retornados pelo login');
      }
      // Sinaliza para o BiometricSetupPrompt (montado em App.jsx) que este
      // é o momento imediatamente após um login bem-sucedido — só nesse
      // instante o modal de ativação de digital pode aparecer.
      sessionStorage.setItem('nara_just_logged_in', '1');
      toast({
        title: "Login realizado com sucesso!",
        description: "Bem-vindo(a) de volta!",
        className: 'bg-green-100 border-green-300 text-green-800',
      });
      const userProfile = (user.perfil || 'professor').toLowerCase();
      // Redireciona com base no perfil
      switch (userProfile) {
        case 'admin':
          navigate('/admin');
          break;
        case 'professor':
        case 'professor_infantil':
        case 'professor_fundamental':
        case 'professor_especialista':
          navigate('/home-professor');
          break;
        case 'coordenador':
          navigate('/coordenacao');
          break;
        case 'especialista':
          navigate('/especialistas');
          break;
        default:
          navigate('/');
          break;
      }
    } catch (err) {
      console.error('Erro no login:', err);
      toast({
        variant: "destructive",
        title: "Erro ao fazer login",
        description: "Não foi possível fazer login. Tente novamente.",
      });
    } finally {
      setIsLoading(false);
    }
  };
  const handleForgotPassword = () => {
    toast({
      title: "🚧 Esta funcionalidade ainda não foi implementada—mas não se preocupe! Você pode solicitar na sua próxima mensagem! 🚀",
      description: "Recuperação de senha em desenvolvimento.",
    });
  };
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.6, delay: 0.3 }}
      className="w-full max-w-md mx-auto"
    >
      <form onSubmit={handleLogin} className="space-y-6">
        <div className="space-y-2">
          <Label htmlFor="email" className="text-gray-700 font-medium">
            E-mail institucional
          </Label>
          <div className="relative">
            <Mail className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 h-5 w-5" />
            <Input
              id="email"
              type="email"
              placeholder="seu.email@instituicao.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="pl-11"
              required
            />
          </div>
        </div>
        <div className="space-y-2">
          <Label htmlFor="password" className="text-gray-700 font-medium">
            Senha
          </Label>
          <div className="relative">
            <Lock className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 h-5 w-5" />
            <Input
              id="password"
              type={showPassword ? 'text' : 'password'}
              placeholder="Sua senha"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="pl-11 pr-11"
              required
            />
            <button
              type="button"
              onClick={() => setShowPassword(!showPassword)}
              className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-400 hover:text-gray-600 transition-colors"
            >
              {showPassword ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
            </button>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <input
            id="remember_me"
            type="checkbox"
            checked={rememberMe}
            onChange={(e) => setRememberMe(e.target.checked)}
            className="h-4 w-4 rounded border-gray-300"
          />
          <Label htmlFor="remember_me" className="text-gray-600 font-normal cursor-pointer">
            Lembrar de mim
          </Label>
        </div>
        <Button
          type="submit"
          disabled={isLoading}
          className="w-full h-12 bg-[#C3ECD4] hover:bg-[#B0E4C1] text-gray-800 font-semibold rounded-xl btn-hover border-0 text-base"
        >
          {isLoading ? (
            <motion.div
              animate={{ rotate: 360 }}
              transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
              className="w-5 h-5 border-2 border-gray-600 border-t-transparent rounded-full"
            />
          ) : (
            <span>Conversar com NARA</span>
          )}
        </Button>
      </form>
    </motion.div>
  );
};
export default LoginForm;