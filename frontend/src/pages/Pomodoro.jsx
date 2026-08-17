import { useEffect, useMemo, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Loader2, Timer, Play, Pause, SkipForward, RotateCcw, Check, Coffee, Brain, Flame, AlertTriangle, BarChart3 } from 'lucide-react';
import Shell from '@/components/Shell';
import api from '@/lib/api';
import { saveCheckpoint, clearCheckpoint } from '@/lib/resume';

const useQuery = () => {
  const { search } = useLocation();
  return useMemo(() => Object.fromEntries(new URLSearchParams(search)), [search]);
};

const fmtClock = (secs) => {
  const s = Math.max(0, Math.floor(secs));
  const m = Math.floor(s / 60).toString().padStart(2, '0');
  const r = (s % 60).toString().padStart(2, '0');
  return `${m}:${r}`;
};

const Pomodoro = () => {
  const q = useQuery();
  const navigate = useNavigate();
  const audioBeepRef = useRef(null);
  const tickRef = useRef(null);

  const [loading, setLoading] = useState(true);
  const [config, setConfig] = useState(null);
  const [today, setToday] = useState({ sessions: [], totals: { completed_sessions: 0, focused_minutes: 0, cycles: 0 } });
  const [blockMeta, setBlockMeta] = useState(null);
  const [subjects, setSubjects] = useState([]);
  const [bySubject, setBySubject] = useState([]);

  const [session, setSession] = useState(null);        // sessão persistida
  const [subjectId, setSubjectId] = useState('');
  const [subject, setSubject] = useState('');
  const [note, setNote] = useState('');
  const [error, setError] = useState(null);

  // timer local
  const [phase, setPhase] = useState('focus');         // focus | break | done
  const [cycle, setCycle] = useState(1);
  const [remaining, setRemaining] = useState(0);        // segundos
  const [running, setRunning] = useState(false);
  const [focusedMinutes, setFocusedMinutes] = useState(0); // acumulado real (min)

  // ─── Load config + today + subjects + stats + optional block ───
  const loadAll = async () => {
    setLoading(true);
    try {
      const [{ data: cfg }, { data: t }, { data: sj }, { data: bs }] = await Promise.all([
        api.get('/pomodoro/config'),
        api.get('/pomodoro/today'),
        api.get('/subjects'),
        api.get('/pomodoro/by-subject'),
      ]);
      setConfig(cfg.config);
      setToday(t);
      setSubjects(sj.subjects || []);
      setBySubject(bs.items || []);
      if (q.block_id) {
        try {
          const { data } = await api.get('/agenda/blocks');
          const b = (data.blocks || []).find((x) => x.id === q.block_id);
          if (b) {
            setBlockMeta(b);
            setSubject(b.title);
          }
        } catch (e) { /* noop */ }
      }
      setRemaining((cfg.config.block_minutes || 25) * 60);
    } finally { setLoading(false); }
  };

  useEffect(() => { loadAll(); /* eslint-disable-next-line */ }, [q.block_id]);

  // ─── Timer loop ────────────────────────────────────────────
  useEffect(() => {
    if (!running) return;
    tickRef.current = setInterval(() => {
      setRemaining((r) => {
        if (r <= 1) {
          onPhaseEnd();
          return 0;
        }
        return r - 1;
      });
      if (phase === 'focus') {
        // acumula minutos parciais a cada segundo
        setFocusedMinutes((m) => m + (1 / 60));
      }
    }, 1000);
    return () => clearInterval(tickRef.current);
    // eslint-disable-next-line
  }, [running, phase]);

  // ─── Resume checkpoint: enquanto rodando, salva a cada 15s ───
  useEffect(() => {
    if (!running || phase !== 'focus') return;
    const remainingMin = () => Math.max(1, Math.round(remaining / 60));
    const push = () => saveCheckpoint('pomodoro', {
      title: `Retomar Pomodoro (${remainingMin()} min restantes)`,
      subtitle: subject ? `Foco: ${subject}` : undefined,
      route: '/pomodoro',
      meta: { remaining_sec: remaining, phase, cycle, session_id: session?.id },
    });
    push();
    const id = setInterval(push, 15000);
    return () => clearInterval(id);
    // eslint-disable-next-line
  }, [running, phase, subject, session?.id]);

  const beep = () => {
    try {
      if (!audioBeepRef.current) {
        const ctx = new (window.AudioContext || window.webkitAudioContext)();
        audioBeepRef.current = ctx;
      }
      const ctx = audioBeepRef.current;
      const o = ctx.createOscillator();
      const g = ctx.createGain();
      o.type = 'sine'; o.frequency.value = 720;
      o.connect(g); g.connect(ctx.destination);
      g.gain.setValueAtTime(0.001, ctx.currentTime);
      g.gain.exponentialRampToValueAtTime(0.25, ctx.currentTime + 0.05);
      g.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.6);
      o.start(); o.stop(ctx.currentTime + 0.6);
    } catch (e) { /* noop */ }
  };

  const onPhaseEnd = () => {
    beep();
    if (phase === 'focus') {
      if (cycle >= (config?.cycles || 4)) {
        // Finalizado — completar sessão automaticamente
        setPhase('done');
        setRunning(false);
        completeSession();
        return;
      }
      setPhase('break');
      setRemaining((config?.break_minutes || 5) * 60);
    } else if (phase === 'break') {
      setCycle((c) => c + 1);
      setPhase('focus');
      setRemaining((config?.block_minutes || 25) * 60);
    }
  };

  // ─── Actions ───────────────────────────────────────────────
  const start = async () => {
    setError(null);
    if (!session) {
      // Só envia block_id/subject_id se realmente resolvemos o objeto no cliente
      const validBlockId = blockMeta?.id || null;
      const validSubjectId = subjectId && subjects.find((s) => s.id === subjectId) ? subjectId : null;
      try {
        const { data } = await api.post('/pomodoro/start', {
          block_id: validBlockId,
          subject_id: validSubjectId,
          subject: subject || null,
          note: note || null,
        });
        setSession(data.session);
      } catch (e) {
        if (e?.response?.status === 404) {
          // Bloco/matéria stale — reset local e tenta de novo sem eles
          setBlockMeta(null);
          setSubjectId('');
          try {
            const { data } = await api.post('/pomodoro/start', {
              subject: subject || null,
              note: note || null,
            });
            setSession(data.session);
          } catch (err2) {
            setError('Não consegui iniciar a sessão. Tente novamente em instantes.');
            return;
          }
        } else {
          setError('Não consegui iniciar a sessão. Tente novamente em instantes.');
          return;
        }
      }
    }
    setRunning(true);
  };

  const pause = () => setRunning(false);

  const skipPhase = () => {
    if (phase === 'focus') {
      setPhase('break');
      setRemaining((config?.break_minutes || 5) * 60);
    } else {
      setCycle((c) => c + 1);
      setPhase('focus');
      setRemaining((config?.block_minutes || 25) * 60);
    }
  };

  const reset = () => {
    setRunning(false);
    setPhase('focus');
    setCycle(1);
    setRemaining((config?.block_minutes || 25) * 60);
    setFocusedMinutes(0);
    clearCheckpoint();
  };

  const completeSession = async (interrupted = false) => {
    if (!session) return;
    try {
      const cycles = Math.max(0, phase === 'focus' ? cycle - 1 : cycle);
      const { data } = await api.post(`/pomodoro/${session.id}/complete`, {
        focused_minutes: Math.round(focusedMinutes),
        completed_cycles: cycles,
        interrupted,
      });
      setSession(null);
      setRunning(false);
      setPhase('done');
      clearCheckpoint();
      await loadAll();
    } catch (e) { /* noop */ }
  };

  const skipSession = async () => {
    if (!session) return;
    try { await api.post(`/pomodoro/${session.id}/skip`); }
    catch (e) { /* noop */ }
    setSession(null);
    setRunning(false);
    reset();
    await loadAll();
  };

  if (loading || !config) {
    return (
      <Shell>
        <div className="max-w-3xl mx-auto px-5 md:px-8 pt-10 flex justify-center">
          <Loader2 className="w-5 h-5 text-brand animate-spin" />
        </div>
      </Shell>
    );
  }

  const totalPhaseSeconds = (phase === 'focus' ? config.block_minutes : config.break_minutes) * 60;
  const progress = 1 - (remaining / (totalPhaseSeconds || 1));
  const dash = 283; // 2*PI*r (r=45)

  return (
    <Shell>
      <div className="max-w-3xl mx-auto px-5 md:px-8 pt-6 md:pt-8 animate-fade-in" data-testid="pomodoro-root">
        <header className="mb-6">
          <div className="flex items-center gap-2 mb-1">
            <Timer strokeWidth={1.75} className="w-5 h-5 text-brand" />
            <p className="eyebrow">Foco adaptativo</p>
          </div>
          <h1 className="mt-1.5 text-[26px] md:text-[30px] font-semibold text-zinc-900 tracking-tight">
            Pomodoro do seu jeito
          </h1>
          <p className="mt-2 text-[14px] text-zinc-500 max-w-2xl">
            {config.reason} · Ciclo <span className="mono">{config.block_minutes}/{config.break_minutes}</span> · <span className="mono">{config.cycles}</span> ciclos por sessão.
          </p>
          <p className="mt-1.5 text-[13px] text-zinc-400 max-w-2xl">
            Pomodoro Timer: técnica de gerenciamento de foco e estudo em blocos curtos (por exemplo, 25 minutos de foco seguidos de 5 minutos de pausa), que ajuda a manter a atenção e a evitar fadiga durante a preparação para as provas.
          </p>
          {blockMeta && (
            <div className="mt-3 inline-flex items-center gap-2 rounded-lg hairline px-3 py-1.5 bg-white">
              <span className="w-2 h-2 rounded-full" style={{ background: blockMeta.color || 'var(--mf-brand)' }} />
              <span className="text-[12.5px] text-zinc-700 font-medium">
                {blockMeta.title} · {blockMeta.start_time}–{blockMeta.end_time}
              </span>
            </div>
          )}
        </header>

        {/* ─── Timer principal ─── */}
        <section className="mf-card p-6 md:p-8 mb-5 flex flex-col items-center">
          <div className="relative w-56 h-56 md:w-64 md:h-64">
            <svg viewBox="0 0 100 100" className="w-full h-full -rotate-90">
              <circle cx="50" cy="50" r="45" fill="none" stroke="var(--mf-hair)" strokeWidth="6" />
              <circle
                cx="50" cy="50" r="45" fill="none"
                stroke={phase === 'focus' ? 'var(--mf-brand)' : phase === 'break' ? 'var(--mf-success)' : 'var(--mf-attention)'}
                strokeWidth="6"
                strokeDasharray={dash}
                strokeDashoffset={dash * (1 - progress)}
                strokeLinecap="round"
                style={{ transition: 'stroke-dashoffset 1s linear' }}
              />
            </svg>
            <div className="absolute inset-0 flex flex-col items-center justify-center">
              <span className="mono text-[44px] md:text-[52px] font-semibold text-zinc-900 tracking-tight"
                    data-testid="pomodoro-clock">
                {fmtClock(remaining)}
              </span>
              <span className="mt-1 text-[11px] uppercase tracking-widest text-zinc-500 font-semibold flex items-center gap-1">
                {phase === 'focus' ? <><Brain className="w-3 h-3" />Foco</>
                 : phase === 'break' ? <><Coffee className="w-3 h-3" />Pausa</>
                 : <><Check className="w-3 h-3" />Concluído</>}
              </span>
              <span className="mt-0.5 text-[12px] text-zinc-500">
                Ciclo <span className="mono">{Math.min(cycle, config.cycles)}</span> / <span className="mono">{config.cycles}</span>
              </span>
            </div>
          </div>

          {error && (
            <p className="mt-4 text-[13px] text-red-600" data-testid="pomodoro-error">{error}</p>
          )}
          <div className="mt-6 flex flex-wrap gap-2 justify-center">
            {!running ? (
              <button
                onClick={start}
                data-testid="pomodoro-start"
                className="mf-btn-primary flex items-center gap-2"
              >
                <Play className="w-4 h-4" /> {session ? 'Retomar' : 'Iniciar sessão'}
              </button>
            ) : (
              <button
                onClick={pause}
                data-testid="pomodoro-pause"
                className="mf-btn-primary flex items-center gap-2"
                style={{ background: 'var(--mf-attention)' }}
              >
                <Pause className="w-4 h-4" /> Pausar
              </button>
            )}
            {session && (
              <>
                <button onClick={skipPhase} className="btn-ghost flex items-center gap-1.5" data-testid="pomodoro-skip-phase">
                  <SkipForward className="w-4 h-4" /> Pular {phase === 'focus' ? 'foco' : 'pausa'}
                </button>
                <button onClick={() => completeSession(true)} className="btn-ghost flex items-center gap-1.5" data-testid="pomodoro-complete">
                  <Check className="w-4 h-4" /> Encerrar sessão
                </button>
                <button onClick={skipSession} className="btn-ghost flex items-center gap-1.5 text-red-500" data-testid="pomodoro-abandon">
                  <RotateCcw className="w-4 h-4" /> Descartar
                </button>
              </>
            )}
          </div>

          {/* Input de matéria/nota, só quando ainda não tem sessão iniciada */}
          {!session && (
            <div className="mt-6 w-full max-w-sm space-y-3">
              {subjects.length > 0 ? (
                <div>
                  <label className="text-[12px] font-medium text-zinc-600">Matéria da grade</label>
                  <select
                    data-testid="pomodoro-subject-select"
                    value={subjectId}
                    onChange={(e) => {
                      setSubjectId(e.target.value);
                      const s = subjects.find((x) => x.id === e.target.value);
                      if (s) setSubject(s.name);
                    }}
                    className="mt-1 w-full rounded-lg hairline px-3 py-2 text-[14px] bg-white"
                  >
                    <option value="">— Livre / sem matéria</option>
                    {subjects.map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.is_critical ? '⚠️ ' : ''}{s.name}
                      </option>
                    ))}
                  </select>
                  {subjectId && subjects.find((s) => s.id === subjectId)?.is_critical && (
                    <p className="mt-1.5 text-[11.5px] text-red-600 flex items-center gap-1">
                      <AlertTriangle className="w-3 h-3" /> Matéria crítica — foco extra recomendado.
                    </p>
                  )}
                </div>
              ) : (
                <div>
                  <label className="text-[12px] font-medium text-zinc-600">Matéria / assunto</label>
                  <input
                    data-testid="pomodoro-subject"
                    value={subject}
                    onChange={(e) => setSubject(e.target.value)}
                    placeholder="Ex: Anatomia — plexo braquial"
                    className="mt-1 w-full rounded-lg hairline px-3 py-2 text-[14px] bg-white"
                  />
                  <p className="mt-1.5 text-[11.5px] text-zinc-400">
                    Dica: importe a grade da sua faculdade no <b>Perfil do estudante</b> para escolher direto da lista.
                  </p>
                </div>
              )}
              <div>
                <label className="text-[12px] font-medium text-zinc-600">Nota (opcional)</label>
                <input
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  placeholder="Ex: capítulos 4 e 5, Netter"
                  className="mt-1 w-full rounded-lg hairline px-3 py-2 text-[14px] bg-white"
                />
              </div>
            </div>
          )}
        </section>

        {/* ─── Minutos por matéria (30 dias) ─── */}
        {bySubject.length > 0 && (
          <section className="mf-card p-5 md:p-6 mb-5" data-testid="pomodoro-by-subject">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-[14px] font-semibold text-zinc-900 flex items-center gap-2">
                <BarChart3 className="w-4 h-4 text-brand" /> Minutos por matéria · 30 dias
              </h3>
              <p className="text-[11px] text-zinc-400 uppercase tracking-wider">Foco distribuído</p>
            </div>
            <ul className="space-y-2">
              {bySubject.slice(0, 6).map((r) => {
                const max = bySubject[0]?.focused_minutes || 1;
                const pct = Math.max(4, Math.round((r.focused_minutes / max) * 100));
                return (
                  <li key={r.subject_id || r.subject} className="text-[13px]">
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-medium text-zinc-900 truncate max-w-[70%]">
                        {r.is_critical && <span title="Matéria crítica" className="mr-1">⚠️</span>}
                        {r.subject}
                      </span>
                      <span className="mono text-zinc-500">{r.focused_minutes} min · {r.sessions}s</span>
                    </div>
                    <div className="w-full h-1.5 rounded-full overflow-hidden" style={{ background: 'var(--mf-hair)' }}>
                      <div
                        className="h-full rounded-full"
                        style={{
                          width: `${pct}%`,
                          background: r.is_critical ? 'var(--mf-care)' : 'var(--mf-brand)',
                          transition: 'width 300ms ease-out',
                        }}
                      />
                    </div>
                  </li>
                );
              })}
            </ul>
          </section>
        )}

        {/* ─── Resumo do dia ─── */}
        <section className="mf-card p-5 md:p-6 mb-5">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-[14px] font-semibold text-zinc-900 flex items-center gap-2">
              <Flame className="w-4 h-4 text-brand" /> Hoje
            </h3>
            <p className="text-[12px] text-zinc-500 mono">
              {today.totals.completed_sessions} sessões · {today.totals.focused_minutes} min · {today.totals.cycles} ciclos
            </p>
          </div>
          {(today.sessions || []).length === 0 ? (
            <p className="text-[13px] text-zinc-500 italic">Nenhuma sessão iniciada hoje.</p>
          ) : (
            <ul className="space-y-2">
              {today.sessions.map((s) => (
                <li key={s.id} className="rounded-lg hairline p-3 flex items-center gap-3 bg-white">
                  <span className="w-8 h-8 rounded-lg flex items-center justify-center text-white"
                        style={{ background: s.status === 'completed' ? 'var(--mf-success)' :
                                            s.status === 'skipped' ? 'var(--mf-tertiary)' : 'var(--mf-brand)' }}>
                    {s.status === 'completed' ? <Check className="w-4 h-4" /> :
                     s.status === 'skipped' ? <RotateCcw className="w-4 h-4" /> :
                     <Play className="w-4 h-4" />}
                  </span>
                  <div className="flex-1 min-w-0">
                    <p className="text-[13px] font-semibold text-zinc-900 truncate">
                      {s.subject || 'Sessão'}
                    </p>
                    <p className="text-[11.5px] text-zinc-500 mono">
                      {s.focused_minutes || 0} min · {s.completed_cycles || 0} ciclos
                      {s.block?.title ? ` · ${s.block.title}` : ''}
                    </p>
                  </div>
                  <span className="text-[11px] uppercase tracking-wider text-zinc-400">{s.status}</span>
                </li>
              ))}
            </ul>
          )}
        </section>

        <button
          onClick={() => navigate('/dashboard')}
          className="btn-ghost text-[13px] mx-auto block"
        >
          Voltar ao painel
        </button>
      </div>
    </Shell>
  );
};

export default Pomodoro;
