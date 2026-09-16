/**
 * client/src/hooks/usePwaInstall.js
 * ------------------------------------------------
 * Hook fino sobre @/lib/pwaInstallPrompt, para ser reutilizado em qualquer
 * lugar que precise oferecer instalação do PWA (banner flutuante, item de
 * menu fixo, etc.) sem duplicar a lógica de captura do evento.
 *
 * Retorna:
 *  - canInstall: true se o Chrome/Edge já capturou o beforeinstallprompt
 *    (ainda não usado/dispensado nesta sessão)
 *  - isIOS: true se estiver no Safari/iOS (sem evento nativo)
 *  - isStandalone: true se o app já estiver rodando instalado agora
 *  - alreadyInstalled: true se já sabemos (via evento ou marcação manual,
 *    persistido em localStorage) que o app foi instalado em algum momento —
 *    cobre o caso do iOS, onde abrir numa aba comum do Safari depois de já
 *    ter instalado não teria outra forma de ser detectado.
 *  - shouldOfferInstall: combinação pronta pra decidir se mostra UI de
 *    instalação (nem standalone, nem já instalado, e há algo a oferecer).
 *  - install(): dispara o prompt nativo do Chrome (só funciona se canInstall)
 *  - markInstalledManually(): usar no fluxo iOS, ao mostrar as instruções.
 */
import { useEffect, useState } from 'react';
import {
  getDeferredPrompt,
  onPromptChange,
  clearDeferredPrompt,
  wasInstalled,
  markInstalledManually,
  isMobileDevice,
} from '@/lib/pwaInstallPrompt';

function isStandaloneNow() {
  return (
    window.matchMedia?.('(display-mode: standalone)').matches ||
    window.navigator.standalone === true
  );
}

function isIOSDevice() {
  return /iphone|ipad|ipod/i.test(window.navigator.userAgent);
}

export function usePwaInstall() {
  const [canInstall, setCanInstall] = useState(Boolean(getDeferredPrompt()));
  const [alreadyInstalled, setAlreadyInstalled] = useState(wasInstalled());

  useEffect(() => {
    const unsubscribe = onPromptChange((prompt) => {
      setCanInstall(Boolean(prompt));
      setAlreadyInstalled(wasInstalled());
    });
    return unsubscribe;
  }, []);

  async function install() {
    const deferredPrompt = getDeferredPrompt();
    if (!deferredPrompt) return { outcome: 'unavailable' };
    deferredPrompt.prompt();
    const choice = await deferredPrompt.userChoice;
    clearDeferredPrompt();
    setCanInstall(false);
    return choice; // { outcome: 'accepted' | 'dismissed' }
  }

  const isStandalone = isStandaloneNow();
  const isIOS = isIOSDevice();
  const isMobile = isMobileDevice();

  return {
    canInstall,
    isIOS,
    isMobile,
    isStandalone,
    alreadyInstalled,
    // mobile-only: em desktop não oferecemos o botão
    shouldOfferInstall: isMobile && !isStandalone && !alreadyInstalled && (canInstall || isIOS),
    install,
    markInstalledManually: () => {
      markInstalledManually();
      setAlreadyInstalled(true);
    },
  };
}