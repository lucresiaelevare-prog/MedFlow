import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API_BASE = `${BACKEND_URL}/api`;

const api = axios.create({
  baseURL: API_BASE,
  withCredentials: true,
});

/**
 * POST + Server-Sent Events. Usa fetch (streaming) para consumir gerações
 * longas sem estourar o timeout do ingress. Chama onDone(payload) no evento
 * `done`, onError({status,detail}) no evento `error`, onProgress(payload) em
 * eventos `progress`. Resolve quando o stream termina.
 */
export async function streamPost(path, body, { onDone, onError, onProgress } = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

  if (!res.ok || !res.body) {
    let detail = `HTTP ${res.status}`;
    try {
      const j = await res.json();
      detail = j.detail || detail;
    } catch (_) { /* ignore */ }
    onError && onError({ status: res.status, detail });
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let settled = false;

  const handleFrame = (frame) => {
    let event = 'message';
    let data = '';
    for (const line of frame.split('\n')) {
      if (line.startsWith('event:')) event = line.slice(6).trim();
      else if (line.startsWith('data:')) data += line.slice(5).trim();
      // linhas iniciadas por ':' são comentários (keep-alive) e são ignoradas
    }
    if (!data) return;
    let payload;
    try { payload = JSON.parse(data); } catch (_) { return; }
    if (event === 'done') { settled = true; onDone && onDone(payload); }
    else if (event === 'error') { settled = true; onError && onError(payload); }
    else if (event === 'progress') { onProgress && onProgress(payload); }
  };

  // eslint-disable-next-line no-constant-condition
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const frames = buffer.split('\n\n');
    buffer = frames.pop();
    for (const frame of frames) handleFrame(frame);
  }
  if (buffer.trim()) handleFrame(buffer);
  if (!settled) onError && onError({ status: 0, detail: 'Conexão encerrada antes de concluir a geração.' });
}

export default api;
