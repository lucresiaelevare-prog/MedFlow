import { useEffect, useState } from 'react';
import { Loader2, TrendingUp, Calendar, Timer, Sparkles, Droplet } from 'lucide-react';
import {
  LineChart, Line, ResponsiveContainer, XAxis, YAxis, Tooltip, CartesianGrid,
  BarChart, Bar,
} from 'recharts';
import Shell from '@/components/Shell';
import api from '@/lib/api';
import IDS from '@/constants/testIds';

const MOOD_TONES = [
  '#FEE2E2',  // 1 — muito baixo
  '#FED7AA',  // 2 — baixo
  '#FEF3C7',  // 3 — neutro
  '#BBF7D0',  // 4 — bom
  '#86EFAC',  // 5 — ótimo
];

const shortDate = (iso) => {
  const d = new Date(iso + 'T00:00:00');
  return d.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' });
};

const History = () => {
  const [data, setData] = useState(null);
  const [weekly, setWeekly] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const [h, w] = await Promise.all([
          api.get('/history?days=30'),
          api.get('/insights/weekly-report?days=7'),
        ]);
        setData(h.data);
        setWeekly(w.data);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const rows = (data?.checkins || []).map((c) => ({
    ts: c.created_at,
    date: new Date(c.created_at).toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' }),
    sleep: c.sleep_hours,
    energy: c.energy,
    mood: c.mood,
  }));

  // Constrói o heatmap: últimos 30 dias, index 0 = mais antigo, 29 = hoje
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const moodByDay = {};
  rows.forEach((r) => {
    const d = new Date(r.ts); d.setHours(0, 0, 0, 0);
    moodByDay[d.toISOString().slice(0, 10)] = r.mood;
  });
  const heatCells = Array.from({ length: 30 }, (_, i) => {
    const d = new Date(today);
    d.setDate(d.getDate() - (29 - i));
    const key = d.toISOString().slice(0, 10);
    const mood = moodByDay[key];
    return {
      key,
      day: d.getDate(),
      label: d.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' }),
      mood,
    };
  });

  const focusRows = (weekly?.focus_series || []).map((r) => ({ date: shortDate(r.date), minutes: r.minutes }));
  const habitRows = (weekly?.habits_series || []).map((r) => ({ date: shortDate(r.date), actions: r.actions }));
  const moodRows = (weekly?.mood_series || []).map((r) => ({ date: shortDate(r.date), mood: r.mood ?? 0 }));

  return (
    <Shell>
      <div
        data-testid={IDS.history.root}
        className="max-w-5xl mx-auto px-5 md:px-8 pt-6 md:pt-8 animate-fade-in"
      >
        <header className="mb-6">
          <p className="eyebrow">Últimos 30 dias</p>
          <h1 className="mt-1.5 text-[26px] md:text-[30px] font-semibold text-zinc-900 tracking-tight">
            Padrões
          </h1>
          <p className="mt-2 text-[14px] text-zinc-500 max-w-xl">
            Como sono, energia e humor têm se comportado. Sem julgamento, só padrões para você observar.
          </p>
        </header>

        {loading ? (
          <div className="mf-card p-10 flex justify-center">
            <Loader2 className="w-5 h-5 text-brand animate-spin" strokeWidth={1.75} />
          </div>
        ) : (
          <>
            {/* ── Frase de coaching (IA) ─────────────── */}
            {weekly?.coaching?.text && (
              <section
                data-testid="history-coaching"
                className="mf-card p-5 md:p-6 mb-4 md:mb-5"
                style={{
                  background: 'var(--mf-brand-soft, #FFF7ED)',
                  borderLeft: '3px solid var(--mf-brand, #DC6B4C)',
                }}
              >
                <div className="flex items-start gap-3">
                  <div
                    className="w-9 h-9 rounded-lg flex items-center justify-center text-white shrink-0"
                    style={{ background: 'var(--mf-brand, #DC6B4C)' }}
                  >
                    <Sparkles strokeWidth={1.75} className="w-4 h-4" />
                  </div>
                  <div className="flex-1">
                    <p className="eyebrow" style={{ color: 'var(--mf-brand, #DC6B4C)' }}>
                      Coaching da semana
                    </p>
                    <p className="mt-1 text-[14.5px] text-zinc-800 leading-relaxed">
                      {weekly.coaching.text}
                    </p>
                  </div>
                </div>
              </section>
            )}

            {/* ── Cards Foco / Hábitos / Humor (7 dias) ─── */}
            {weekly && (
              <div
                data-testid="history-weekly-cards"
                className="grid grid-cols-1 md:grid-cols-3 gap-4 md:gap-5 mb-4 md:mb-5"
              >
                <MiniCard
                  testId="history-focus-card"
                  icon={<Timer strokeWidth={1.75} className="w-4 h-4" style={{ color: '#059669' }} />}
                  title="Foco"
                  bigValue={weekly.totals.focus_minutes}
                  bigUnit="min"
                  subtitle={`${weekly.totals.days_focused} dia(s) com sessões`}
                >
                  <div className="h-24 min-h-[96px]">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={focusRows} margin={{ top: 4, right: 4, left: -28, bottom: 0 }}>
                        <XAxis dataKey="date" tick={{ fill: '#A1A1AA', fontSize: 10 }} axisLine={false} tickLine={false} />
                        <YAxis hide />
                        <Tooltip contentStyle={{ borderRadius: 10, border: '1px solid #E5E5E7', fontSize: 12 }} />
                        <Bar dataKey="minutes" fill="#059669" radius={[3, 3, 0, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </MiniCard>

                <MiniCard
                  testId="history-habits-card"
                  icon={<Droplet strokeWidth={1.75} className="w-4 h-4" style={{ color: '#6C5CE7' }} />}
                  title="Hábitos"
                  bigValue={weekly.totals.care_actions}
                  bigUnit="ações"
                  subtitle={`${weekly.totals.days_care} dia(s) com autocuidado`}
                >
                  <div className="h-24 min-h-[96px]">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={habitRows} margin={{ top: 4, right: 4, left: -28, bottom: 0 }}>
                        <XAxis dataKey="date" tick={{ fill: '#A1A1AA', fontSize: 10 }} axisLine={false} tickLine={false} />
                        <YAxis hide />
                        <Tooltip contentStyle={{ borderRadius: 10, border: '1px solid #E5E5E7', fontSize: 12 }} />
                        <Bar dataKey="actions" fill="#6C5CE7" radius={[3, 3, 0, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </MiniCard>

                <MiniCard
                  testId="history-mood-card"
                  icon={<TrendingUp strokeWidth={1.75} className="w-4 h-4" style={{ color: '#DC6B4C' }} />}
                  title="Humor 7d"
                  bigValue={weekly.totals.avg_mood ?? '—'}
                  bigUnit="/5"
                  subtitle={`${weekly.totals.checkins} check-in(s)`}
                >
                  <div className="h-24 min-h-[96px]">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={moodRows} margin={{ top: 6, right: 4, left: -28, bottom: 0 }}>
                        <XAxis dataKey="date" tick={{ fill: '#A1A1AA', fontSize: 10 }} axisLine={false} tickLine={false} />
                        <YAxis hide domain={[0, 5]} />
                        <Tooltip contentStyle={{ borderRadius: 10, border: '1px solid #E5E5E7', fontSize: 12 }} />
                        <Line type="monotone" dataKey="mood" stroke="#DC6B4C" strokeWidth={1.75} dot={{ r: 2.5, fill: '#DC6B4C' }} />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </MiniCard>
              </div>
            )}

            <div className="grid grid-cols-3 gap-3 md:gap-4">
              <Stat label="Check-ins" value={rows.length} unit="" />
              <Stat
                label="Sono médio"
                value={rows.length ? (rows.reduce((s, r) => s + r.sleep, 0) / rows.length).toFixed(1) : '—'}
                unit={rows.length ? 'h' : ''}
              />
              <Stat label="Adesão" value={data?.adherence_pct ?? 0} unit="%" />
            </div>

            {/* Heatmap 30 dias — Diário de humor visual */}
            <section data-testid="history-mood-heatmap" className="mf-card p-5 md:p-6 mt-4 md:mt-5">
              <div className="flex items-center gap-2 mb-1">
                <Calendar strokeWidth={1.75} className="w-4 h-4 text-brand" />
                <h3 className="text-[15px] font-semibold text-zinc-900 tracking-tight">Meu humor · 30 dias</h3>
              </div>
              <p className="text-[12.5px] text-zinc-500 mb-4">
                Cada quadrado é um dia. Cor mais viva = melhor humor. Vazio = sem check-in.
              </p>
              <div className="grid grid-cols-6 sm:grid-cols-10 gap-1.5">
                {heatCells.map((c) => (
                  <div
                    key={c.key}
                    title={c.mood ? `${c.label} · humor ${c.mood}/5` : `${c.label} · sem registro`}
                    className="aspect-square rounded-md hairline flex items-center justify-center text-[10.5px] font-medium"
                    style={{
                      background: c.mood ? MOOD_TONES[Math.max(0, Math.min(4, c.mood - 1))] : 'var(--mf-canvas)',
                      color: c.mood ? '#3F3F46' : '#A1A1AA',
                    }}
                  >
                    {c.day}
                  </div>
                ))}
              </div>
              <div className="mt-4 flex items-center justify-between text-[11px] text-zinc-500">
                <span className="uppercase tracking-wider font-medium">Escala</span>
                <div className="flex items-center gap-1">
                  {MOOD_TONES.map((c, i) => (
                    <span key={i} className="inline-flex items-center gap-1">
                      <span className="w-3 h-3 rounded-sm hairline" style={{ background: c }} />
                      {i === 0 ? '1' : i === 4 ? '5' : ''}
                    </span>
                  ))}
                </div>
              </div>
            </section>

            {rows.length > 0 && (
              <div className="mt-4 md:mt-5 grid grid-cols-1 md:grid-cols-3 gap-4 md:gap-5">
                <ChartCard title="Sono" subtitle="horas por noite" dataKey="sleep" rows={rows} color="#6C5CE7" domain={[0, 12]} />
                <ChartCard title="Energia" subtitle="1 (exausto) a 5 (ótimo)" dataKey="energy" rows={rows} color="#059669" domain={[0, 5]} />
                <ChartCard title="Humor" subtitle="1 (muito baixo) a 5 (ótimo)" dataKey="mood" rows={rows} color="#DC6B4C" domain={[0, 5]} />
              </div>
            )}
          </>
        )}
      </div>
    </Shell>
  );
};

const Stat = ({ label, value, unit }) => (
  <div className="mf-card p-4 md:p-5">
    <p className="eyebrow">{label}</p>
    <p className="mt-1.5 mono text-[26px] font-semibold text-zinc-900 tabular leading-none">
      {value}<span className="text-[14px] text-zinc-400 font-medium ml-0.5">{unit}</span>
    </p>
  </div>
);

const MiniCard = ({ testId, icon, title, bigValue, bigUnit, subtitle, children }) => (
  <div data-testid={testId} className="mf-card p-5">
    <div className="flex items-center gap-2 mb-1">
      {icon}
      <h3 className="text-[14px] font-semibold text-zinc-900 tracking-tight">{title}</h3>
    </div>
    <p className="mono text-[26px] font-semibold text-zinc-900 leading-none tabular">
      {bigValue}
      <span className="text-[13px] text-zinc-400 font-medium ml-0.5">{bigUnit}</span>
    </p>
    <p className="mt-1 text-[12px] text-zinc-500">{subtitle}</p>
    <div className="mt-3">{children}</div>
  </div>
);

const ChartCard = ({ title, subtitle, dataKey, rows, color, domain }) => (
  <div className="mf-card p-5">
    <div className="flex items-center gap-2 mb-1">
      <TrendingUp strokeWidth={1.75} className="w-4 h-4" style={{ color }} />
      <h3 className="text-[15px] font-semibold text-zinc-900 tracking-tight">{title}</h3>
    </div>
    <p className="text-[12px] text-zinc-500 mb-3">{subtitle}</p>
    <div className="h-36">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={rows} margin={{ top: 6, right: 8, left: -22, bottom: 0 }}>
          <CartesianGrid stroke="#F4F4F5" strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="date" tick={{ fill: '#A1A1AA', fontSize: 11 }} axisLine={false} tickLine={false} />
          <YAxis domain={domain} tick={{ fill: '#A1A1AA', fontSize: 11 }} axisLine={false} tickLine={false} />
          <Tooltip contentStyle={{ borderRadius: 10, border: '1px solid #E5E5E7', fontSize: 12 }} />
          <Line type="monotone" dataKey={dataKey} stroke={color} strokeWidth={1.75} dot={{ r: 2.5, fill: color }} activeDot={{ r: 4 }} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  </div>
);

export default History;
