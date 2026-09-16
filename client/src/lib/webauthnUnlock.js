/**
 * client/src/lib/webauthnUnlock.js
 * ------------------------------------------------
 * Usa a WebAuthn API (Face ID / Touch ID / impressão digital) apenas como
 * um "destravador" local do app — NÃO substitui o login real por
 * email/senha contra o backend Django. A ideia é: a sessão Django já dura
 * até 90 dias (ver AuthContext/remember_me); a biometria só evita ter que
 * digitar a senha de novo no mesmo aparelho enquanto essa sessão for válida.
 *
 * Por isso a credencial nunca é enviada/validada no servidor: o sucesso do
 * desafio (navigator.credentials.get() resolver sem erro) já é prova
 * suficiente de que o sistema operacional confirmou a biometria da pessoa
 * dona do aparelho.
 *
 * Guardamos, por usuário, o ID da credencial no localStorage — isso é só
 * para o navigator.credentials.get() saber qual credencial verificar; não
 * é um segredo (o segredo/chave privada nunca sai do hardware do aparelho).
 */

const CREDENTIAL_STORAGE_PREFIX = 'nara_webauthn_credential_';
const PROMPT_SHOWN_STORAGE_PREFIX = 'nara_webauthn_prompt_shown_';
const BACKGROUNDED_AT_KEY = 'nara_lock_backgrounded_at';

/**
 * Tempo mínimo em segundo plano para exigir desbloqueio biométrico ao
 * voltar. Abaixo disso (ex: trocou de app rapidinho e voltou), não
 * interrompe — só passa a pedir depois de um afastamento real.
 */
export const LOCK_THRESHOLD_MS = 2 * 24 * 60 * 60 * 1000; // 2 dias (48 horas)

function credentialStorageKey(userId) {
  return `${CREDENTIAL_STORAGE_PREFIX}${userId}`;
}

function promptShownStorageKey(userId) {
  return `${PROMPT_SHOWN_STORAGE_PREFIX}${userId}`;
}

function randomChallenge() {
  return crypto.getRandomValues(new Uint8Array(32));
}

function textToBytes(text) {
  return new TextEncoder().encode(text);
}

function bytesToBase64(bytes) {
  let binary = '';
  const arr = new Uint8Array(bytes);
  for (let i = 0; i < arr.byteLength; i++) {
    binary += String.fromCharCode(arr[i]);
  }
  return window.btoa(binary);
}

function base64ToBytes(base64) {
  const binary = window.atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes;
}

/**
 * Verifica se o navegador suporta WebAuthn E se o aparelho tem um
 * autenticador de plataforma disponível (Face ID, Touch ID, leitor de
 * digital) — sem isso, não faz sentido nem oferecer a opção.
 */
export async function isBiometricAvailable() {
  if (typeof window === 'undefined') return false;
  if (!window.PublicKeyCredential) return false;
  if (!window.PublicKeyCredential.isUserVerifyingPlatformAuthenticatorAvailable) return false;

  try {
    return await window.PublicKeyCredential.isUserVerifyingPlatformAuthenticatorAvailable();
  } catch (_) {
    return false;
  }
}

export function hasUnlockCredential(userId) {
  try {
    return Boolean(localStorage.getItem(credentialStorageKey(userId)));
  } catch (_) {
    return false;
  }
}

export function wasPromptShown(userId) {
  try {
    return localStorage.getItem(promptShownStorageKey(userId)) === '1';
  } catch (_) {
    return true; // por segurança, se não conseguir ler, não insiste
  }
}

export function markPromptShown(userId) {
  try {
    localStorage.setItem(promptShownStorageKey(userId), '1');
  } catch (_) {
    // localStorage indisponível — segue sem persistir
  }
}

/**
 * Registra uma credencial biométrica local para o usuário. Dispara o
 * prompt nativo do sistema operacional (Face ID / Touch ID / digital).
 * Retorna { success: true } ou { success: false, reason }.
 */
export async function registerUnlockCredential(userId, userName) {
  try {
    const credential = await navigator.credentials.create({
      publicKey: {
        challenge: randomChallenge(),
        rp: {
          name: 'NARA Educacional',
          id: window.location.hostname,
        },
        user: {
          id: textToBytes(userId),
          name: userName || 'usuario@nara',
          displayName: userName || 'Usuário NARA',
        },
        pubKeyCredParams: [
          { type: 'public-key', alg: -7 },   // ES256
          { type: 'public-key', alg: -257 }, // RS256
        ],
        authenticatorSelection: {
          authenticatorAttachment: 'platform', // só biometria embutida do aparelho, não chaves externas
          userVerification: 'required',
          residentKey: 'preferred',
        },
        timeout: 60000,
        attestation: 'none',
      },
    });

    if (!credential) {
      return { success: false, reason: 'no_credential' };
    }

    const credentialIdB64 = bytesToBase64(credential.rawId);
    localStorage.setItem(credentialStorageKey(userId), credentialIdB64);

    return { success: true };
  } catch (error) {
    // NotAllowedError: usuário cancelou ou negou o prompt do SO
    return { success: false, reason: error?.name || 'unknown_error' };
  }
}

/**
 * Pede a verificação biométrica (usada em telas de "desbloquear com
 * digital" no futuro). Retorna true se o SO confirmou a biometria.
 */
export async function verifyUnlock(userId) {
  const storedId = localStorage.getItem(credentialStorageKey(userId));
  if (!storedId) return false;

  try {
    const assertion = await navigator.credentials.get({
      publicKey: {
        challenge: randomChallenge(),
        allowCredentials: [
          {
            id: base64ToBytes(storedId),
            type: 'public-key',
          },
        ],
        userVerification: 'required',
        timeout: 60000,
      },
    });

    return Boolean(assertion);
  } catch (_) {
    return false;
  }
}

export function removeUnlockCredential(userId) {
  try {
    localStorage.removeItem(credentialStorageKey(userId));
  } catch (_) {
    // ignora
  }
}

/**
 * --- Rastreamento de "app foi para segundo plano" ---
 * Usa localStorage (não sessionStorage) de propósito: em PWA instalado,
 * o sistema operacional pode encerrar o processo ao minimizar (comum no
 * iOS), então uma reabertura é um carregamento de página totalmente novo.
 * localStorage sobrevive a isso; sessionStorage não teria garantia.
 */

export function markBackgrounded() {
  try {
    localStorage.setItem(BACKGROUNDED_AT_KEY, String(Date.now()));
  } catch (_) {
    // ignora
  }
}

export function clearBackgroundedAt() {
  try {
    localStorage.removeItem(BACKGROUNDED_AT_KEY);
  } catch (_) {
    // ignora
  }
}

/**
 * Retorna true se o app ficou em segundo plano por tempo suficiente para
 * exigir desbloqueio biométrico ao voltar.
 */
export function shouldRequireUnlock() {
  try {
    const raw = localStorage.getItem(BACKGROUNDED_AT_KEY);
    if (!raw) return false;
    const backgroundedAt = Number(raw);
    if (Number.isNaN(backgroundedAt)) return false;
    return Date.now() - backgroundedAt > LOCK_THRESHOLD_MS;
  } catch (_) {
    return false;
  }
}