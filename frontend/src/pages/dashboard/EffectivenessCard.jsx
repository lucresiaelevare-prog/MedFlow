import { useEffect, useState } from 'react';
import { Loader2, TrendingUp, TrendingDown, Minus } from 'lucide-react';
import api from '@/lib/api';

/**
 * Tendências da sua rotina — cartão neutro no Dashboard.
 * Consome /api/insights/effectiveness-report. Sem gamificação, sem badges.
 * Se estiver vazio (semana sem dados), o cartão simplesmente não aparece.
 */
const arrow = (v) => {
  if (v == null) return <Minus strokeWidth={1.75} className="w-3.5 h-3.5" />;
  if (v > 0) return <TrendingUp strokeWidth={1.75} className="w-3.5 h-3.5" style={{ color: 'var(--mf-success)' }} />;
  if (v < 0) return <TrendingDown strokeWidth={1.75} className="w-3.5 h-3.5" style={{ color: 'var(--mf-care)' }} />;
  return <Minus strokeWidth={1.75} className="w-3.5 h-3.5 text-zinc-400" />;
};

const EffectivenessCard = () => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const { data } = await api.get('/insights/effectiveness-report');
        setData(data);
      } finally { setLoading(false); }
    })();
  }, []);

  if (loading) {
    return (
      <div className="mf-card p-4 flex items-center justify-center py-6">
        <Loader2 className="w-4 h-4 animate-spin" style={{ color: 'var(--mf-brand)' }} />
      </div>
    );
  }
  if (!data || data.empty) return null;

  return (
    <section className="mf-card p-5 md:p-6" data-testid="dashboard-effectiveness">
      <div className="flex items-center justify-between mb-3">
        <div>
          <p className="eyebrow"><span>tendências da sua rotina</span></p>
          <h3 className="mt-1 text-[15.5px] font-semibold text-zinc-900 tracking-tight">
            <span>Semana atual vs anterior</span>
          </h3>
        </div>
      </div>

      {data.trends.length > 0 && (
        <ul className="space-y-2" data-testid="effectiveness-trends">
          {data.trends.map((t, i) => (
            <li key={i} className="flex items-center gap-2 text-[13.5px] text-zinc-800">
              {arrow(t.delta_pct)}
              <span>{t.text}</span>
            </li>
          ))}
        </ul>
      )}

      {(data.best_disciplines.length > 0 || data.worst_disciplines.length > 0) && (
        <div className="mt-4 pt-4 hairline-t grid grid-cols-1 md:grid-cols-2 gap-3">
          {data.best_disciplines.length > 0 && (
            <div data-testid="effectiveness-best">
              <p className="eyebrow"><span>maior evolução</span></p>
              <ul className="mt-1.5 space-y-1">
                {data.best_disciplines.map((d) => (
                  <li key={d.discipline} className="flex items-center justify-between text-[12.5px]">
                    <span className="text-zinc-700 capitalize"><span>{d.discipline}</span></span>
                    <span className="mono" style={{ color: 'var(--mf-success)' }}>
                      <span>+{d.delta_points} pts</span>
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {data.worst_disciplines.length > 0 && (
            <div data-testid="effectiveness-worst">
              <p className="eyebrow"><span>menor evolução</span></p>
              <ul className="mt-1.5 space-y-1">
                {data.worst_disciplines.map((d) => (
                  <li key={d.discipline} className="flex items-center justify-between text-[12.5px]">
                    <span className="text-zinc-700 capitalize"><span>{d.discipline}</span></span>
                    <span className="mono" style={{ color: 'var(--mf-care)' }}>
                      <span>{d.delta_points} pts</span>
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      <p className="mt-4 text-[11px] text-zinc-400">
        <span>Dados observados esta semana. Sem metas, sem ranking — só sinais reais.</span>
      </p>
    </section>
  );
};

export default EffectivenessCard;
