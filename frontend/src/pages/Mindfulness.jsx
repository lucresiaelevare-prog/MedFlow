import { useEffect, useRef, useState } from 'react';
import { Loader2, Play, Pause, Check } from 'lucide-react';
import Shell from '@/components/Shell';
import api from '@/lib/api';
import IDS from '@/constants/testIds';

const Mindfulness = () => {
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [active, setActive] = useState(null); // slug
  const [remaining, setRemaining] = useState(0);
  const timerRef = useRef(null);
  const [completed, setCompleted] = useState(null);

  useEffect(() => {
    (async () => {
      const { data } = await api.get('/mindfulness/sessions');
      setSessions(data.sessions);
      setLoading(false);
    })();
    return () => clearInterval(timerRef.current);
  }, []);

  const start = (s) => {
    setActive(s.slug);
    setRemaining(s.duration_seconds);
    setCompleted(null);
    clearInterval(timerRef.current);
    timerRef.current = setInterval(() => {
      setRemaining((r) => {
        if (r <= 1) {
          clearInterval(timerRef.current);
          completeSession(s);
          return 0;
        }
        return r - 1;
      });
    }, 1000);
  };

  const stop = () => {
    clearInterval(timerRef.current);
    setActive(null);
    setRemaining(0);
  };

  const completeSession = async (s) => {
    setActive(null);
    setCompleted(s.slug);
    try {
      await api.post('/mindfulness/log', { session_slug: s.slug, duration_seconds: s.duration_seconds });
    } catch (e) { /* ignore */ }
  };

  const fmt = (sec) => {
    const m = Math.floor(sec / 60).toString().padStart(1, '0');
    const s = (sec % 60).toString().padStart(2, '0');
    return `${m}:${s}`;
  };

  return (
    <Shell>
      <div data-testid={IDS.mindfulness.root} className="max-w-md md:max-w-3xl mx-auto px-5 md:px-6 pt-6 md:pt-10 space-y-6 animate-fade-in">
        <div>
          <p className="text-xs uppercase tracking-widest text-sage-700 font-semibold">Pausas guiadas</p>
          <h1 className="mt-1 font-display text-3xl md:text-4xl font-semibold text-stone-900">Respire por 3 minutos.</h1>
          <p className="mt-2 text-stone-600 text-sm">Sessões curtas para plantão, pré-prova ou quando o dia pesa demais.</p>
        </div>

        {loading ? (
          <div className="rounded-3xl bg-white border border-stone-100 p-10 flex justify-center">
            <Loader2 className="w-6 h-6 text-sage-600 animate-spin" />
          </div>
        ) : (
          <div className="space-y-4">
            {sessions.map((s) => {
              const isActive = active === s.slug;
              const isDone = completed === s.slug;
              return (
                <div
                  key={s.slug}
                  className={`rounded-3xl bg-white border p-6 transition-all ${
                    isActive ? 'border-sage-300 shadow-[0_12px_40px_rgba(74,107,83,0.15)]' : 'border-stone-100'
                  }`}
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1">
                      <h3 className="font-display text-xl text-stone-900">{s.title}</h3>
                      <p className="mt-1 text-sm text-stone-600">{s.description}</p>
                      <ul className="mt-3 space-y-1">
                        {s.instructions.map((step, i) => (
                          <li key={i} className="text-sm text-stone-600 flex gap-2">
                            <span className="text-sage-600 font-semibold w-4 shrink-0">{i + 1}.</span>
                            <span>{step}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                    <div className="text-right shrink-0">
                      <p className="text-xs text-stone-500 uppercase tracking-wider">
                        {isActive ? 'Restam' : `${Math.round(s.duration_seconds / 60)} min`}
                      </p>
                      {isActive && (
                        <p className="font-display text-2xl text-sage-700 tabular-nums">{fmt(remaining)}</p>
                      )}
                      {isDone && (
                        <p className="mt-1 text-sage-700 text-xs flex items-center gap-1 justify-end">
                          <Check className="w-3.5 h-3.5" /> feito
                        </p>
                      )}
                    </div>
                  </div>

                  <div className="mt-5 flex gap-2">
                    {!isActive ? (
                      <button
                        data-testid={IDS.mindfulness.play(s.slug)}
                        onClick={() => start(s)}
                        className="bg-sage-600 hover:bg-sage-700 text-white rounded-full px-5 py-2.5 text-sm font-medium flex items-center gap-2"
                      >
                        <Play className="w-4 h-4" /> Começar
                      </button>
                    ) : (
                      <button
                        onClick={stop}
                        className="bg-stone-100 hover:bg-stone-200 text-stone-800 rounded-full px-5 py-2.5 text-sm font-medium flex items-center gap-2"
                      >
                        <Pause className="w-4 h-4" /> Pausar
                      </button>
                    )}
                    {isActive && (
                      <button
                        data-testid={IDS.mindfulness.complete}
                        onClick={() => completeSession(s)}
                        className="bg-stone-100 hover:bg-stone-200 text-stone-800 rounded-full px-5 py-2.5 text-sm font-medium"
                      >
                        Concluir agora
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </Shell>
  );
};

export default Mindfulness;
