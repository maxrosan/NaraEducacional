/**
 * client/src/components/pwa/InstallPWAButton.jsx
 * ------------------------------------------------
 * Visual: cartão branco ocupando a largura da tela (com padding lateral),
 * ícone do app à esquerda, texto explicativo no meio, botão quadrado à
 * direita com o mesmo ícone usado no item "Instalar app" do menu do usuário
 * (Download, do lucide-react), e o × de fechar dentro do card, na mesma
 * linha do conteúdo.
 *
 * Comportamento:
 *  - Chrome/Edge/Android: consome @/lib/pwaInstallPrompt (captura o evento
 *    beforeinstallprompt cedo, mesmo se este componente montar depois). O
 *    botão dispara o prompt nativo de instalação.
 *  - iOS/Safari: sem evento nativo — o botão revela as instruções manuais
 *    (Compartilhar > Adicionar à Tela de Início).
 *  - Mobile only: não aparece em desktop, mesmo quando o Chrome considera
 *    o app instalável.
 *  - Se o app já estiver rodando instalado, não mostra nada.
 *
 * Uso: importar e renderizar uma vez, condicionado a usuário logado
 * (ver App.jsx).
 */
import { useEffect, useState } from 'react';
import { Download } from 'lucide-react';
import {
  getDeferredPrompt,
  onPromptChange,
  clearDeferredPrompt,
  isMobileDevice,
} from '@/lib/pwaInstallPrompt';

const DISMISSED_KEY = 'nara_pwa_install_dismissed_at';
const DISMISS_COOLDOWN_MS = 1000 * 60 * 60 * 24 * 7; // não insiste por 7 dias após "fechar"

function isStandalone() {
  return (
    window.matchMedia?.('(display-mode: standalone)').matches ||
    window.navigator.standalone === true
  );
}

function isIOS() {
  return /iphone|ipad|ipod/i.test(window.navigator.userAgent);
}

function wasRecentlyDismissed() {
  const raw = localStorage.getItem(DISMISSED_KEY);
  if (!raw) return false;
  const dismissedAt = Number(raw);
  if (Number.isNaN(dismissedAt)) return false;
  return Date.now() - dismissedAt < DISMISS_COOLDOWN_MS;
}

function markDismissed() {
  localStorage.setItem(DISMISSED_KEY, String(Date.now()));
}

function AppIcon() {
  return (
    <img
      src="/pwa-192x192.png"
      alt=""
      aria-hidden="true"
      className="h-10 w-10 rounded-xl shadow-sm shrink-0 bg-roxo-principal/5 object-contain p-1"
    />
  );
}

function CloseButton({ onClick }) {
  return (
    <button
      onClick={onClick}
      aria-label="Fechar"
      className="self-start shrink-0 h-7 w-7 flex items-center justify-center rounded-full text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors"
    >
      <span className="text-lg leading-none">×</span>
    </button>
  );
}

export default function InstallPWAButton() {
  const [showAndroidButton, setShowAndroidButton] = useState(false);
  const [showIOSBanner, setShowIOSBanner] = useState(false);
  const [showIOSInstructions, setShowIOSInstructions] = useState(false);

  useEffect(() => {
    if (!isMobileDevice() || isStandalone() || wasRecentlyDismissed()) return;

    if (getDeferredPrompt()) {
      setShowAndroidButton(true);
    }

    const unsubscribe = onPromptChange((prompt) => {
      setShowAndroidButton(Boolean(prompt));
    });

    if (isIOS()) {
      setShowIOSBanner(true);
    }

    return unsubscribe;
  }, []);

  async function handleInstallClick() {
    const deferredPrompt = getDeferredPrompt();
    if (!deferredPrompt) return;
    deferredPrompt.prompt();
    await deferredPrompt.userChoice;
    clearDeferredPrompt();
    setShowAndroidButton(false);
  }

  function handleDismiss(setter) {
    markDismissed();
    setter(false);
  }

  if (showAndroidButton) {
    return (
      <div className="fixed z-50 bottom-4 inset-x-4">
        <div className="rounded-[28px] bg-white shadow-[0_8px_30px_rgba(0,0,0,0.15)] border border-slate-200 p-3">
          <div className="flex items-center gap-3">
            <AppIcon />
            <p className="flex-1 text-sm text-slate-800 leading-snug">
              Adicione o NARA à tela inicial do seu smartphone
            </p>
            <button
              onClick={handleInstallClick}
              aria-label="Instalar"
              className="shrink-0 h-11 w-11 rounded-2xl bg-roxo-principal text-white flex items-center justify-center hover:opacity-90 active:opacity-80 transition-opacity"
            >
              <Download className="h-5 w-5" />
            </button>
            <CloseButton onClick={() => handleDismiss(setShowAndroidButton)} />
          </div>
        </div>
      </div>
    );
  }

  if (showIOSBanner) {
    return (
      <div className="fixed z-50 bottom-4 inset-x-4">
        <div className="rounded-[28px] bg-white shadow-[0_8px_30px_rgba(0,0,0,0.15)] border border-slate-200 p-3">
          <div className="flex items-center gap-3">
            <AppIcon />
            <p className="flex-1 text-sm text-slate-800 leading-snug">
              Adicione o NARA à tela inicial do seu smartphone
            </p>
            <button
              onClick={() => setShowIOSInstructions((v) => !v)}
              aria-label="Como instalar"
              className="shrink-0 h-11 w-11 rounded-2xl bg-roxo-principal text-white flex items-center justify-center hover:opacity-90 active:opacity-80 transition-opacity"
            >
              <Download className="h-5 w-5" />
            </button>
            <CloseButton onClick={() => handleDismiss(setShowIOSBanner)} />
          </div>
          {showIOSInstructions && (
            <p className="mt-3 text-xs text-slate-600 leading-snug border-t border-slate-100 pt-3">
              Toque em <span className="font-semibold text-slate-900">Compartilhar</span> ↑ e depois em{' '}
              <span className="font-semibold text-slate-900">"Adicionar à Tela de Início"</span>.
            </p>
          )}
        </div>
      </div>
    );
  }

  return null;
}