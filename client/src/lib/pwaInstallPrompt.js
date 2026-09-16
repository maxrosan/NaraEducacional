/**
 * client/src/lib/pwaInstallPrompt.js
 * ------------------------------------------------
 * O evento `beforeinstallprompt` dispara assim que o browser decide que a
 * página é instalável — geralmente logo no carregamento. Se o listener só é
 * registrado depois (ex: dentro de um componente React que só monta após o
 * login), o evento já passou e nunca mais dispara de novo nessa sessão.
 *
 * Este módulo registra o listener no nível mais alto possível (assim que o
 * arquivo é importado, idealmente logo no main.jsx, antes do React montar),
 * guarda o evento capturado em uma variável de módulo, e expõe funções pra
 * qualquer componente consultar/depois assinar mudanças — mesmo que monte
 * bem depois do evento já ter disparado.
 *
 * Também persiste em localStorage a confirmação de instalação (evento
 * `appinstalled` no Chrome/Edge, ou marcação manual no fluxo iOS), pra que
 * o item "Instalar app" não reapareça em visitas futuras numa aba comum do
 * navegador — cenário em que o Safari não expõe nenhum evento nativo pra
 * detectar que o app já foi adicionado à Tela de Início.
 */

const INSTALLED_STORAGE_KEY = 'nara_pwa_installed';

let deferredPrompt = null;
const listeners = new Set();

function readInstalledFromStorage() {
  try {
    return localStorage.getItem(INSTALLED_STORAGE_KEY) === '1';
  } catch (_) {
    return false;
  }
}

function writeInstalledToStorage(value) {
  try {
    if (value) {
      localStorage.setItem(INSTALLED_STORAGE_KEY, '1');
    } else {
      localStorage.removeItem(INSTALLED_STORAGE_KEY);
    }
  } catch (_) {
    // localStorage indisponível (modo privado etc.) — segue sem persistir
  }
}

let installedFlag = typeof window !== 'undefined' ? readInstalledFromStorage() : false;

if (typeof window !== 'undefined') {
  window.addEventListener('beforeinstallprompt', (event) => {
    event.preventDefault(); // bloqueia o mini-infobar automático do Chrome
    deferredPrompt = event;
    listeners.forEach((cb) => cb(deferredPrompt));
  });

  window.addEventListener('appinstalled', () => {
    installedFlag = true;
    writeInstalledToStorage(true);
    deferredPrompt = null;
    listeners.forEach((cb) => cb(null));
  });
}

export function getDeferredPrompt() {
  return deferredPrompt;
}

export function wasInstalled() {
  return installedFlag;
}

/**
 * Marca manualmente como "instalado" — usado no fluxo iOS, onde não existe
 * confirmação nativa: assumimos que, ao clicar em "Instalar app" e ver as
 * instruções, o usuário seguiu o passo a passo.
 */
export function markInstalledManually() {
  installedFlag = true;
  writeInstalledToStorage(true);
  listeners.forEach((cb) => cb(null));
}

/** Assina mudanças (evento capturado ou app instalado). Retorna função de unsubscribe. */
export function onPromptChange(callback) {
  listeners.add(callback);
  return () => listeners.delete(callback);
}

export function clearDeferredPrompt() {
  deferredPrompt = null;
}

/**
 * Detecta se o dispositivo é mobile (Android/iOS/etc), para restringir a
 * oferta de instalação apenas a celulares — em desktop, mesmo quando o
 * Chrome considera o app "instalável", não queremos mostrar o banner/item
 * de menu, já que é mobile-only.
 *
 * Usa `userAgentData.mobile` quando disponível (mais confiável, Chromium),
 * com fallback por regex de user-agent para os demais navegadores.
 */
export function isMobileDevice() {
  if (typeof navigator === 'undefined') return false;

  if (navigator.userAgentData && typeof navigator.userAgentData.mobile === 'boolean') {
    return navigator.userAgentData.mobile;
  }

  return /android|iphone|ipad|ipod|mobile/i.test(navigator.userAgent);
}