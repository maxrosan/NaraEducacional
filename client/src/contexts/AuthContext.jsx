import React, { createContext, useContext, useEffect, useState, useCallback, useMemo } from 'react';

import * as Sentry from '@sentry/react';
import { apiClient } from '@/lib/apiClient';
import { useToast } from '@/components/ui/use-toast';
import { PERFIS_PROFESSOR } from '@/constants/perfis';

const AuthContext = createContext(undefined);

export const AuthProvider = ({ children }) => {
  const { toast } = useToast();

  const [user, setUser] = useState(null);
  const [session, setSession] = useState(null);
  const [loading, setLoading] = useState(true);
  const [turmas, setTurmas] = useState([]);
  const [turmaAtiva, setTurmaAtiva] = useState(null);

  const carregarTurmasProfessor = useCallback(async (userId) => {
    try {
      const { data } = await apiClient
        .from('usuario_turmas')
        .select('turma_id, turma_nome')
        .eq('usuario_id', userId);

      if (!data || data.length === 0) return;

      // Buscar detalhes das turmas
      const turmaIds = data.map(ut => ut.turma_id).filter(Boolean);
      const { data: turmasData } = await apiClient
        .from('turmas')
        .select('id, nome')
        .in('id', turmaIds);

      if (turmasData && turmasData.length > 0) {
        setTurmas(turmasData);
        // Primeira ocorrência como turma ativa
        setTurmaAtiva(turmasData[0]);
      }
    } catch (err) {
      console.error('[Auth] Erro ao carregar turmas do professor:', err);
    }
  }, []);

  const handleSession = useCallback((session) => {
    setSession(session);
    const u = session?.user ?? null;
    setUser(u);
    if (u) {
      Sentry.setUser({
        id: u.id,
        email: u.email,
        username: u.user_metadata?.full_name || u.email,
      });

      const perfil = (u.perfil || u.user_metadata?.perfil || '').toLowerCase();
      if (PERFIS_PROFESSOR.includes(perfil)) {
        carregarTurmasProfessor(u.id);
      }
    } else {
      Sentry.setUser(null);
      setTurmas([]);
      setTurmaAtiva(null);
    }
    setLoading(false);
  }, [carregarTurmasProfessor]);

  useEffect(() => {
    let mounted = true;

    const getSession = async () => {
      try {
        const { data: { session } } = await apiClient.auth.getSession();
        if (mounted) {
          handleSession(session);
        }
      } catch (error) {
        console.error('[Auth] Erro ao buscar sessão:', error);
        if (mounted) {
          setLoading(false);
        }
      }
    };

    getSession();

    let isLoggedIn = false;

    const { data: { subscription } } = apiClient.auth.onAuthStateChange(
      (event, session) => {
        if (mounted) {
          if (event === 'SIGNED_IN') {
            isLoggedIn = true;
          }

          handleSession(session);

          if (event === 'SESSION_EXPIRED') {
            isLoggedIn = false;
            toast({
              variant: 'destructive',
              title: 'Sessão expirada',
              description: 'Sua sessão expirou. Faça login novamente.',
            });
            setTimeout(() => {
              window.location.href = '/';
            }, 1500);
          }
        }
      }
    );

    // Checa a cada 5 minutos se a sessão ainda é válida no servidor. Esse é
    // o mecanismo correto de expiração — reflete o estado real do backend
    // (SESSION_COOKIE_AGE / set_expiry no login), em vez de um timer de
    // inatividade arbitrário no cliente.
    const SESSION_CHECK_INTERVAL = 5 * 60 * 1000;
    const sessionInterval = setInterval(async () => {
      if (!mounted) return;
      const { data: { session } } = await apiClient.auth.getSession();
      if (mounted && !session && isLoggedIn) {
        apiClient.auth.notifySignedOut();
      }
    }, SESSION_CHECK_INTERVAL);

    return () => {
      mounted = false;
      subscription.unsubscribe();
      clearInterval(sessionInterval);
    };
  }, [handleSession]);

  const signUp = useCallback(async (email, password, options) => {
    const { error } = await apiClient.auth.signUp({ email, password, options });
    if (error) {
      toast({
        variant: "destructive",
        title: "Sign up Failed",
        description: error.message || "Something went wrong",
      });
    }
    return { error };
  }, [toast]);

  // remember_me = true por padrão: sessão longa (ver auth_login no backend,
  // que aplica set_expiry(90 dias) quando remember_me é verdadeiro), sem
  // exigir checkbox — comportamento "fica logado" por padrão.
  const signIn = useCallback(async (email, password, remember_me = true) => {
    const { error, data } = await apiClient.auth.signInWithPassword({
      email,
      password,
      remember_me,
    });

    if (error) {
      toast({
        variant: "destructive",
        title: "Falha no login",
        description: error.message || "Credenciais inválidas",
      });
    } else if (data?.user) {
      handleSession({ user: data.user, access_token: 'django-session' });
    }

    return { error, data };
  }, [toast, handleSession]);

  const signOut = useCallback(async () => {
    const { error } = await apiClient.auth.signOut();

    // O estado local é limpo nos dois casos — `apiClient.signOut` já o fez do
    // seu lado, e deixar o usuário aqui com a sessão "meio encerrada" é pior.
    setUser(null);
    setSession(null);
    setTurmas([]);
    setTurmaAtiva(null);

    if (error) {
      // Servidor recusou: NÃO redireciona. Um `window.location` recarregaria a
      // página, o `/auth/me/` traria o usuário de volta (a sessão do Django
      // segue viva) e o toast se perderia no reload — exatamente o sintoma de
      // "cliquei em sair e continuo logado", só que sem explicação na tela.
      toast({
        variant: 'destructive',
        title: 'Não foi possível sair',
        description: `${error.message} Recarregue a página e tente novamente.`,
      });
      return { error };
    }

    window.location.href = '/';
    return { error: null };
  }, [toast]);

  const value = useMemo(() => ({
    user,
    session,
    loading,
    turmas,
    turmaAtiva,
    setTurmaAtiva,
    signUp,
    signIn,
    signOut,
  }), [user, session, loading, turmas, turmaAtiva, signUp, signIn, signOut]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};