/**
 * Resume checkpoints — helper de UX para "Continuar de onde você parou".
 * Todas as chamadas são silenciosas (falha não afeta a atividade em curso).
 */
import api from '@/lib/api';

/**
 * Salva/atualiza o checkpoint ativo do aluno.
 * @param {'pomodoro'|'tutor'|'flashcards'|'questions'|'simulado'|'resumo'|'revisao'} kind
 * @param {{ title: string, subtitle?: string, route: string, meta?: object }} data
 */
export async function saveCheckpoint(kind, { title, subtitle, route, meta } = {}) {
  if (!kind || !title || !route) return;
  try {
    await api.post('/resume/save', { kind, title, subtitle, route, meta });
  } catch (_e) { /* silencioso */ }
}

export async function clearCheckpoint() {
  try { await api.post('/resume/clear'); } catch (_e) { /* silencioso */ }
}

export async function getCheckpoint() {
  try {
    const { data } = await api.get('/resume/state');
    return data?.resume || null;
  } catch (_e) { return null; }
}
