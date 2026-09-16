/**
 * client/src/components/auth/BiometricSetupPrompt.jsx
 * ------------------------------------------------
 * Modal que oferece ativar a digital/Face ID logo após o primeiro login.
 *
 * Gatilho: o LoginForm marca `sessionStorage['nara_just_logged_in']` no
 * momento em que o login é bem-sucedido. Este componente, montado uma vez
 * em App.jsx, checa essa marca ao montar — se presente, e se o navegador
 * suporta biometria, e se o usuário ainda não tem credencial nem já viu
 * esse prompt antes, mostra o modal. Depois de mostrado (aceito ou não),
 * nunca mais aparece automaticamente para esse usuário.
 */
import { useEffect, useState } from 'react';
import { Fingerprint } from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';
import { useToast } from '@/components/ui/use-toast';
import {
  isBiometricAvailable,
  hasUnlockCredential,
  wasPromptShown,
  markPromptShown,
  registerUnlockCredential,
} from '@/lib/webauthnUnlock';
import { isMobileDevice } from '@/lib/pwaInstallPrompt';

const JUST_LOGGED_IN_KEY = 'nara_just_logged_in';

export default function BiometricSetupPrompt() {
  const { user } = useAuth();
  const { toast } = useToast();
  const [visible, setVisible] = useState(false);
  const [registering, setRegistering] = useState(false);

  useEffect(() => {
    if (!user) return;

    const justLoggedIn = sessionStorage.getItem(JUST_LOGGED_IN_KEY) === '1';
    if (!justLoggedIn) return;

    // Consome a marca imediatamente — só queremos avaliar isso uma vez,
    // logo após o login que a gerou.
    sessionStorage.removeItem(JUST_LOGGED_IN_KEY);

    if (hasUnlockCredential(user.id) || wasPromptShown(user.id)) return;

    // Biometria é exclusiva para mobile — mesma restrição já aplicada ao
    // botão de instalação do PWA. Em desktop, mesmo com autenticador de
    // plataforma disponível (Windows Hello, etc.), não oferecemos.
    if (!isMobileDevice()) {
      markPromptShown(user.id);
      return;
    }

    let cancelled = false;
    isBiometricAvailable().then((available) => {
      if (!cancelled && available) {
        setVisible(true);
      } else if (!cancelled) {
        // Aparelho não suporta — marca como "visto" para nunca mais checar
        // à toa nesse dispositivo.
        markPromptShown(user.id);
      }
    });

    return () => {
      cancelled = true;
    };
  }, [user]);

  async function handleActivate() {
    if (!user) return;
    setRegistering(true);
    const result = await registerUnlockCredential(user.id, user.email);
    setRegistering(false);
    markPromptShown(user.id);
    setVisible(false);

    if (result.success) {
      toast({ title: 'Digital ativada! Você poderá usá-la nos próximos acessos.' });
    } else if (result.reason !== 'NotAllowedError') {
      // Erro cancelado pelo usuário (NotAllowedError) não precisa de aviso.
      toast({
        variant: 'destructive',
        title: 'Não foi possível ativar a digital',
        description: 'Você pode tentar novamente depois nas configurações.',
      });
    }
  }

  function handleDismiss() {
    if (user) markPromptShown(user.id);
    setVisible(false);
  }

  if (!visible) return null;

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/40 px-4">
      <div className="w-full max-w-sm rounded-3xl bg-white p-6 shadow-2xl">
        <div className="flex flex-col items-center text-center gap-4">
          <div className="h-14 w-14 rounded-2xl bg-roxo-principal/10 flex items-center justify-center">
            <Fingerprint className="h-7 w-7 text-roxo-principal" />
          </div>
          <div className="space-y-1.5">
            <h2 className="text-lg font-semibold text-slate-900">Usar digital para acessar?</h2>
            <p className="text-sm text-slate-600 leading-snug">
              Na próxima vez, você pode entrar no NARA com sua digital ou Face ID,
              sem precisar digitar a senha de novo neste aparelho.
            </p>
          </div>
          <div className="w-full flex flex-col gap-2 mt-1">
            <button
              onClick={handleActivate}
              disabled={registering}
              className="w-full rounded-xl bg-roxo-principal text-white text-sm font-semibold py-2.5 hover:opacity-90 active:opacity-80 transition-opacity disabled:opacity-60"
            >
              {registering ? 'Ativando...' : 'Ativar'}
            </button>
            <button
              onClick={handleDismiss}
              disabled={registering}
              className="w-full rounded-xl text-slate-500 text-sm font-medium py-2.5 hover:bg-slate-50 transition-colors"
            >
              Agora não
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}