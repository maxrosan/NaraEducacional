/**
 * client/src/components/auth/AppLockScreen.jsx
 * ------------------------------------------------
 * Bloqueia a tela quando o app volta de segundo plano após um tempo
 * (LOCK_THRESHOLD_MS, hoje 5 min), exigindo desbloqueio com digital/Face ID
 * antes de mostrar o conteúdo de novo. Só se aplica a quem já ativou a
 * biometria via BiometricSetupPrompt — quem nunca ativou não é afetado.
 *
 * A sessão Django continua válida por trás disso (até 90 dias) — este
 * bloqueio é só uma camada extra local de privacidade/segurança, não uma
 * re-autenticação real contra o servidor.
 *
 * Fallback: se a pessoa não conseguir/quiser usar a digital (cancelou,
 * trocou de aparelho, etc.), pode optar por sair e logar de novo com senha.
 */
import { useEffect, useState } from 'react';
import { Fingerprint } from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';
import {
  hasUnlockCredential,
  markBackgrounded,
  clearBackgroundedAt,
  shouldRequireUnlock,
  verifyUnlock,
} from '@/lib/webauthnUnlock';

export default function AppLockScreen() {
  const { user, signOut } = useAuth();
  const [locked, setLocked] = useState(false);
  const [verifying, setVerifying] = useState(false);
  const [failed, setFailed] = useState(false);

  // Avalia, ao montar (app recém-aberto/recarregado), se ficou tempo
  // suficiente em segundo plano desde a última vez que foi escondido.
  useEffect(() => {
    if (!user) return;
    if (hasUnlockCredential(user.id) && shouldRequireUnlock()) {
      setLocked(true);
    }
  }, [user]);

  // Observa esconder/mostrar a partir de agora, durante a sessão atual.
  useEffect(() => {
    if (!user) return;

    function handleVisibilityChange() {
      if (document.hidden) {
        markBackgrounded();
        return;
      }

      // Voltou a ficar visível — decide se precisa bloquear.
      if (hasUnlockCredential(user.id) && shouldRequireUnlock()) {
        setLocked(true);
      } else {
        clearBackgroundedAt();
      }
    }

    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => document.removeEventListener('visibilitychange', handleVisibilityChange);
  }, [user]);

  async function handleUnlock() {
    if (!user) return;
    setVerifying(true);
    setFailed(false);
    const success = await verifyUnlock(user.id);
    setVerifying(false);

    if (success) {
      clearBackgroundedAt();
      setLocked(false);
    } else {
      setFailed(true);
    }
  }

  if (!locked) return null;

  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center bg-white px-4">
      <div className="w-full max-w-sm flex flex-col items-center text-center gap-5">
        <img src="/pwa-192x192.png" alt="NARA" className="h-16 w-16" />
        <div className="space-y-1.5">
          <h2 className="text-lg font-semibold text-slate-900">App bloqueado</h2>
          <p className="text-sm text-slate-600 leading-snug">
            Use sua digital ou Face ID para continuar de onde parou.
          </p>
        </div>

        <button
          onClick={handleUnlock}
          disabled={verifying}
          className="h-16 w-16 rounded-full bg-roxo-principal text-white flex items-center justify-center hover:opacity-90 active:opacity-80 transition-opacity disabled:opacity-60"
          aria-label="Desbloquear"
        >
          <Fingerprint className="h-7 w-7" />
        </button>

        {failed && (
          <p className="text-sm text-red-600">
            Não foi possível verificar. Tente novamente.
          </p>
        )}

        <button
          onClick={() => signOut()}
          className="text-sm text-slate-400 hover:text-slate-600 transition-colors mt-2"
        >
          Sair e entrar com senha
        </button>
      </div>
    </div>
  );
}