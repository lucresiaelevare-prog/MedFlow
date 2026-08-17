import { useEffect, useState } from 'react';
import { Loader2, ArrowUpRight, CheckCircle2, Circle, CalendarDays, Target, Trophy } from 'lucide-react';
import api from '@/lib/api';

const KIND_ICONS = {
  block: CalendarDays,
  mission: Target,
  exam: Trophy,
};

const CATEGORY_COLOR = {
  academic: '#2F6BFF', study: '#7A5CFF', physical: '#22B573',
  leisure: '#F59E0B', social: '#EC4899', family: '#EF4444',
  love: '#F472B6', sleep: '#0F172A', care: '#14B8A6', prova: '#DC6B4C',
};

/**
 * Card de Priorização Inteligente do dia — usado no Dashboard.
 * Mostra top 4 itens ranqueados pelo backend em `/api/priority/today`.
 */
const PriorityCard = () => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const { data } = await api.get('/priority/today');
      setData(data);
    } finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  if (loading) return (
    <div className="mf-card p-5 flex items-center gap-3">
      <Loader2 className="w-4 h-4 text-brand animate-spin" />
      <span className="text-[13px] text-zinc-500">Priorizando seu dia…</span>
    </div>
  );

  const items = (data?.items || []).slice(0, 4);
  if (items.length === 0) return null;

  return (
    <div className="mf-card p-5" data-testid="priority-card">
      <div className="flex items-center justify-between mb-3">
        <p className="eyebrow">Priorização inteligente</p>
        <span className="pill pill-brand mono text-[10.5px]">
          {items.length} · adesão {data.adherence}%
        </span>
      </div>
      <h3 className="text-[15px] font-semibold text-zinc-900 mb-3">O que fazer agora</h3>
      <ul className="space-y-2">
        {items.map((it) => {
          const Icon = KIND_ICONS[it.kind] || Circle;
          const color = CATEGORY_COLOR[it.category] || '#71717A';
          const done = it.done || it.completed;
          return (
            <li
              key={`${it.kind}-${it.id}`}
              data-testid={`priority-item-${it.kind}-${it.id}`}
              className="flex items-start gap-3 p-2.5 rounded-lg hairline"
              style={done ? { opacity: 0.55 } : {}}
            >
              <span
                className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0"
                style={{ background: `${color}22`, color }}
              >
                {done ? <CheckCircle2 className="w-4 h-4" /> : <Icon className="w-4 h-4" strokeWidth={1.75} />}
              </span>
              <div className="flex-1 min-w-0">
                <p className={`text-[13.5px] font-semibold ${done ? 'line-through text-zinc-500' : 'text-zinc-900'} truncate`}>
                  {it.title}
                </p>
                <p className="text-[11px] text-zinc-500 truncate">
                  {it.why} · score {it.score}
                </p>
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
};

export default PriorityCard;
