import React, { createContext, useContext, useEffect, useState, useCallback, useMemo } from 'react';

import * as Sentry from '@sentry/react';
import {
  API_BASE_URL,
  HEADERS_PADRAO,
  EVENTO_SESSAO_EXPIRADA,
  authFetch,
  getAccessToken,
  getRefreshToken,
  salvarTokens,
  limparTokens,
  normalizarUsuario,
} from '@/services/api';
import { useToast } from '@/components/ui/use-toast';
import { PERFIS_PROFESSOR } from '@/constants/perfis';

/*
 * ALTERADO: autenticação por JWT (auth/login/ + me/), sem sessão Django e sem o
 * `apiClient` estilo Supabase. O tenant (instituição/escola) é definido pelo
 * backend a partir do token — o front só guarda o usuário para exibir e decidir telas.
 */

const AuthContext = createContext(undefined);

async function lerErro(response, padrao) {
  try {
    const data = await response.json();
    return data.detail || data.error || padrao;
  } catch (_) {
    return padrao;
  }
}

export const AuthProvider = ({ children }) => {
  const { toast } = useToast();

  const [user, setUser] = useState(null);
  const [session, setSession] = useState(null);
  const [loading, setLoading] = useState(true);
  const [turmas, setTurmas] = useState([]);
  const [turmaAtiva, setTurmaAtiva] = useState(null);

  /**
   * ALTERADO: não existe mais consulta genérica à tabela `usuario_turmas`.
   * GET /turmas/ já devolve só as turmas da escola do professor; daqui
   * mantemos apenas aquelas em que ele está vinculado (turmas/<id>/professores/).
   * Uma chamada por turma — ver nota sobre `me/turmas/` na conversa.
   */
  const carregarTurmasProfessor = useCallback(async (userId) => {
    try {
      const resp = await authFetch(`${API_BASE_URL}/turmas/`);
      if (!resp.ok) return;
      const turmasEscola = await resp.json();

      const vinculadas = await Promise.all(
        turmasEscola.map(async (turma) => {
          const r = await authFetch(`${API_BASE_URL}/turmas/${turma.id}/professores/`);
          if (!r.ok) return null;
          const vinculos = await r.json();
          return vinculos.some((v) => String(v.usuario) === String(userId)) ? turma : null;
        }),
      );

      const minhas = vinculadas.filter(Boolean);
      setTurmas(minhas);
      setTurmaAtiva(minhas[0] ?? null);
    } catch (err) {
      console.error('[Auth] Erro ao carregar turmas do professor:', err);
    }
  }, []);

  const handleSession = useCallback((usuarioApi) => {
    const u = normalizarUsuario(usuarioApi);
    setUser(u);
    setSession(u ? { user: u, access_token: getAccessToken() } : null);

    if (u) {
      Sentry.setUser({ id: u.id, email: u.email, username: u.nome || u.email });
      if (PERFIS_PROFESSOR.includes((u.nivel || '').toLowerCase())) {
        carregarTurmasProfessor(u.id);
      } else {
        setTurmas([]);
        setTurmaAtiva(null);
      }
    } else {
      Sentry.setUser(null);
      setTurmas([]);
      setTurmaAtiva(null);
    }
    setLoading(false);
  }, [carregarTurmasProfessor]);

  // Restaura a sessão ao abrir/recarregar a página.
  useEffect(() => {
    let mounted = true;

    const restaurar = async () => {
      if (!getAccessToken()) {
        if (mounted) handleSession(null);
        return;
      }
      try {
        // authFetch renova o access token sozinho se ele tiver expirado.
        const resp = await authFetch(`${API_BASE_URL}/me/`);
        if (!mounted) return;
        if (resp.ok) {
          handleSession(await resp.json());
        } else {
          limparTokens();
          handleSession(null);
        }
      } catch (error) {
        console.error('[Auth] Erro ao restaurar sessão:', error);
        if (mounted) handleSession(null);
      }
    };

    restaurar();
    return () => { mounted = false; };
  }, [handleSession]);

  // Sessão expirada: o authFetch dispara este evento quando o refresh token
  // também não vale mais (expirou em 7 dias ou foi invalidado).
  // ALTERADO: substitui o polling de 5 em 5 minutos — com JWT a validade é
  // verificada em cada requisição.
  useEffect(() => {
    const aoExpirar = () => {
      handleSession(null);
      toast({
        variant: 'destructive',
        title: 'Sessão expirada',
        description: 'Sua sessão expirou. Faça login novamente.',
      });
      setTimeout(() => { window.location.href = '/'; }, 1500);
    };
    window.addEventListener(EVENTO_SESSAO_EXPIRADA, aoExpirar);
    return () => window.removeEventListener(EVENTO_SESSAO_EXPIRADA, aoExpirar);
  }, [handleSession, toast]);

  /** REMOVIDO: o backend não tem auto-cadastro. Usuários são criados pela gestão. */
  const signUp = useCallback(async () => {
    const error = new Error('Cadastro público não está disponível. Solicite acesso à coordenação.');
    toast({ variant: 'destructive', title: 'Cadastro indisponível', description: error.message });
    return { error };
  }, [toast]);

  /**
   * ALTERADO: POST auth/login/ com { email, password }. A resposta traz
   * access, refresh e `usuario` (não precisa chamar /me/ depois).
   * `remember_me` não tem mais efeito: a duração é a do refresh token (7 dias,
   * renovados a cada uso). Mantido na assinatura só para não quebrar chamadas.
   */
  // eslint-disable-next-line no-unused-vars
  const signIn = useCallback(async (email, password, remember_me = true) => {
    try {
      const resp = await fetch(`${API_BASE_URL}/auth/login/`, {
        method: 'POST',
        headers: { ...HEADERS_PADRAO, 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });

      if (!resp.ok) {
        const mensagem = resp.status === 401
          ? 'E-mail ou senha inválidos.'
          : await lerErro(resp, 'Não foi possível entrar.');
        throw new Error(mensagem);
      }

      const data = await resp.json();
      salvarTokens(data);
      const u = normalizarUsuario(data.usuario);
      handleSession(data.usuario);
      return { error: null, data: { user: u, session: { user: u, access_token: data.access } } };
    } catch (error) {
      toast({
        variant: 'destructive',
        title: 'Falha no login',
        description: error.message || 'Credenciais inválidas',
      });
      return { error, data: null };
    }
  }, [toast, handleSession]);

  /**
   * ALTERADO: POST auth/logout/ coloca o refresh token na blacklist no backend
   * e depois os tokens são apagados do navegador.
   * Usa fetch puro (não authFetch): se o access token tiver vencido, o authFetch
   * tentaria renovar — e a renovação invalidaria justamente o refresh que
   * estamos enviando. O endpoint não exige access token.
   * Se a chamada falhar (rede fora, servidor caído), sai assim mesmo: o usuário
   * pediu para sair, e o token expira sozinho em até 7 dias.
   */
  const signOut = useCallback(async () => {
    const refresh = getRefreshToken();
    if (refresh) {
      try {
        await fetch(`${API_BASE_URL}/auth/logout/`, {
          method: 'POST',
          headers: { ...HEADERS_PADRAO, 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh }),
        });
      } catch (err) {
        console.warn('[Auth] Logout no servidor falhou; encerrando só no navegador.', err);
      }
    }

    limparTokens();
    setUser(null);
    setSession(null);
    setTurmas([]);
    setTurmaAtiva(null);
    Sentry.setUser(null);
    window.location.href = '/';
    return { error: null };
  }, []);

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