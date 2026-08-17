import { useEffect, useState } from 'react';
import { Loader2, Sparkles, Flame, Trophy, Target, BookOpen, Moon, Activity, Wind, Shield, Lock } from 'lucide-react';
import Shell from '@/components/Shell';
import api from '@/lib/api';
import IDS from '@/constants/testIds';

const ICON_MAP = {
  sparkles: Sparkles, flame: Flame, trophy: Trophy, target: Target,
  'book-open': BookOpen, moon: Moon, activity: Activity, wind: Wind, shield: Shield,
};

const Badges = () => {
  const [items, setItems] = useState([]);
  const [count, setCount] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      const { data } = await api.get('/badges');
      setItems(data.badges || []);
      setCount(data.earned_count || 0);
      setLoading(false);
    })();
  }, []);

  return (
    <Shell>
      <div data-testid={IDS.badges.root} className="max-w-md md:max-w-3xl mx-auto px-5 md:px-6 pt-6 md:pt-10 space-y-6 animate-fade-in">
        <div>
          <p className="text-xs uppercase tracking-widest text-sage-700 font-semibold">Conquistas</p>
          <h1 className="mt-1 font-display text-3xl md:text-4xl font-semibold text-stone-900">Sua trajetória</h1>
          <p className="mt-2 text-stone-600 text-sm">{count} de {items.length} conquistadas · o foco é criar hábito, não competir.</p>
        </div>

        {loading ? (
          <div className="rounded-3xl bg-white border border-stone-100 p-10 flex justify-center">
            <Loader2 className="w-6 h-6 text-sage-600 animate-spin" />
          </div>
        ) : (
          <ul className="grid grid-cols-2 md:grid-cols-3 gap-3">
            {items.map((b) => {
              const Icon = ICON_MAP[b.icon] || Sparkles;
              const earned = b.earned;
              const accent = b.color === 'terracotta' ? 'terracotta' : 'sage';
              return (
                <li
                  key={b.slug}
                  data-testid={IDS.badges.item(b.slug)}
                  className={`rounded-3xl border p-5 text-center transition-all ${
                    earned
                      ? `bg-white border-${accent}-200 shadow-[0_8px_30px_rgba(74,107,83,0.08)]`
                      : 'bg-stone-50 border-stone-100 opacity-60'
                  }`}
                >
                  <div className={`w-14 h-14 mx-auto rounded-2xl flex items-center justify-center ${
                    earned ? `bg-${accent}-100 text-${accent}-700` : 'bg-stone-200 text-stone-400'
                  }`}>
                    {earned ? <Icon className="w-6 h-6" /> : <Lock className="w-5 h-5" />}
                  </div>
                  <h3 className={`mt-3 font-display text-sm ${earned ? 'text-stone-900' : 'text-stone-500'}`}>
                    {b.title}
                  </h3>
                  <p className="mt-1 text-[11px] text-stone-500 leading-snug">{b.description}</p>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </Shell>
  );
};

export default Badges;
