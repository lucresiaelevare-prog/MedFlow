/**
 * Telemetria de erros do frontend — cliente unificado.
 *
 * Ver /app/docs/frontend-rules.md #7.
 *
 * - `sendTelemetry(payload)` — fire-and-forget para /api/telemetry/error.
 * - `installGlobalErrorHandlers()` — captura promises rejeitadas e erros
 *   soltos de window (script errors, throws em event handlers).
 *
 * Design:
 * - Uso de `fetch(..., { keepalive: true })` garante que o request
 *   sobreviva à navegação/close da aba.
 * - Deduplicação leve por (component + message + route) num intervalo curto
 *   pra evitar spam quando um mesmo erro dispara N vezes.
 * - Nunca lança. Nunca bloqueia a UI.
 */

import React from 'react';

const REACT_VERSION = React.version;
const DEDUP_WINDOW_MS = 5000;
const _recent = new Map(); // key -> timestamp

const _shouldSend = (key) => {
  const now = Date.now();
  const last = _recent.get(key);
  if (last && now - last < DEDUP_WINDOW_MS) return false;
  _recent.set(key, now);
  // cleanup ocasional
  if (_recent.size > 100) {
    for (const [k, t] of _recent) {
      if (now - t > DEDUP_WINDOW_MS * 4) _recent.delete(k);
    }
  }
  return true;
};

export const sendTelemetry = (payload) => {
  try {
    const key = `${payload.component}|${payload.message || ''}|${payload.route || ''}`;
    if (!_shouldSend(key)) return;

    const url = (process.env.REACT_APP_BACKEND_URL || '') + '/api/telemetry/error';
    fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      credentials: 'include',
      keepalive: true,
    }).catch(() => { /* silencioso */ });
  } catch { /* silencioso */ }
};

const _base = (component) => ({
  component,
  route: (typeof window !== 'undefined' && window.location) ? window.location.pathname : '',
  user_agent: (typeof navigator !== 'undefined') ? navigator.userAgent : '',
  react_version: REACT_VERSION,
  timestamp: new Date().toISOString(),
});

let _installed = false;

export const installGlobalErrorHandlers = () => {
  if (_installed || typeof window === 'undefined') return;
  _installed = true;

  // Promises rejeitadas sem catch — SafeRender não pega isso.
  window.addEventListener('unhandledrejection', (event) => {
    const reason = event?.reason;
    const message = String(
      (reason && (reason.message || reason.toString())) || 'unhandled rejection'
    ).slice(0, 1000);
    const stack = String((reason && reason.stack) || '').slice(0, 4000);
    sendTelemetry({
      ..._base('promise-rejection'),
      message,
      stack,
      component_stack: '',
    });
  });

  // Erros de script soltos (throws em event handlers, sync errors fora do React).
  window.addEventListener('error', (event) => {
    // Filtra erros de resource loading (imagens 404 etc.) que não são interessantes.
    if (event && event.target && event.target !== window) return;
    const err = event?.error;
    const message = String(
      (err && (err.message || err.toString())) || event?.message || 'window error'
    ).slice(0, 1000);
    const stack = String((err && err.stack) || '').slice(0, 4000);
    sendTelemetry({
      ..._base('window-error'),
      message,
      stack,
      component_stack: '',
    });
  });
};
