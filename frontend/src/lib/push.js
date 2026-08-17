/* Web Push helpers for MedFlow.
 * Handles: SW registration, permission, subscribe/unsubscribe against /api/push/*.
 *
 * Beta 1 gate: `REACT_APP_ENABLE_PUSH_PROMPT` must be "true" for the browser
 * permission prompt to fire. Backend infra (jobs, endpoints) stays live regardless.
 */
import api from '@/lib/api';

export const isPushPromptEnabled = () =>
  String(process.env.REACT_APP_ENABLE_PUSH_PROMPT || '').toLowerCase() === 'true';

const urlBase64ToUint8Array = (base64String) => {
  const padding = '='.repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
  const raw = atob(base64);
  const output = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i++) output[i] = raw.charCodeAt(i);
  return output;
};

export const isPushSupported = () =>
  typeof window !== 'undefined' &&
  'serviceWorker' in navigator &&
  'PushManager' in window &&
  'Notification' in window;

export const getPermission = () => {
  if (!('Notification' in window)) return 'unsupported';
  return Notification.permission; // 'default' | 'granted' | 'denied'
};

export const registerServiceWorker = async () => {
  if (!isPushSupported()) return null;
  try {
    const reg = await navigator.serviceWorker.register('/sw.js', { scope: '/' });
    await navigator.serviceWorker.ready;
    return reg;
  } catch (e) {
    console.error('SW register failed', e);
    return null;
  }
};

export const enablePush = async () => {
  if (!isPushPromptEnabled()) throw new Error('push_prompt_disabled');
  if (!isPushSupported()) throw new Error('Este navegador não suporta Web Push.');
  const permission = await Notification.requestPermission();
  if (permission !== 'granted') throw new Error('Permissão de notificação negada.');

  const reg = await registerServiceWorker();
  if (!reg) throw new Error('Falha ao registrar o service worker.');

  const { data: cfg } = await api.get('/push/config');
  const existing = await reg.pushManager.getSubscription();
  const sub = existing || await reg.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: urlBase64ToUint8Array(cfg.vapid_public_key),
  });

  const payload = sub.toJSON();
  await api.post('/push/subscribe', {
    endpoint: payload.endpoint,
    expirationTime: payload.expirationTime || null,
    keys: payload.keys,
    user_agent: navigator.userAgent,
    tz: Intl.DateTimeFormat().resolvedOptions().timeZone || 'America/Sao_Paulo',
  });
  return { ok: true, endpoint: payload.endpoint };
};

export const disablePush = async () => {
  if (!isPushSupported()) return { ok: true };
  const reg = await navigator.serviceWorker.getRegistration('/');
  if (!reg) return { ok: true };
  const sub = await reg.pushManager.getSubscription();
  if (sub) {
    try { await api.delete(`/push/subscribe?endpoint=${encodeURIComponent(sub.endpoint)}`); } catch (e) { /* ignore */ }
    try { await sub.unsubscribe(); } catch (e) { /* ignore */ }
  }
  return { ok: true };
};

export const currentSubscription = async () => {
  if (!isPushSupported()) return null;
  const reg = await navigator.serviceWorker.getRegistration('/');
  if (!reg) return null;
  const sub = await reg.pushManager.getSubscription();
  return sub ? sub.toJSON() : null;
};

export const sendTestPush = async () => {
  const { data } = await api.post('/push/test', {});
  return data;
};
