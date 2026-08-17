import { useEffect, useState } from 'react';
import {
  Loader2, ExternalLink, FileText, Video, Headphones, Music,
  BookOpen, Moon, Activity, Sparkles, Users, LayoutGrid,
} from 'lucide-react';
import Shell from '@/components/Shell';
import api from '@/lib/api';
import IDS from '@/constants/testIds';

const TYPE_ICONS = { artigo: FileText, video: Video, podcast: Headphones, audio: Music };

const PILLAR_TABS = [
  { key: 'all',          label: 'Todos',        Icon: LayoutGrid },
  { key: 'estudos',      label: 'Estudos',      Icon: BookOpen },
  { key: 'sono',         label: 'Sono',         Icon: Moon },
  { key: 'saude_fisica', label: 'Saúde física', Icon: Activity },
  { key: 'bem_estar',    label: 'Bem-estar',    Icon: Sparkles },
  { key: 'social',       label: 'Social',       Icon: Users },
];

const Resources = () => {
  const [tab, setTab] = useState('all');
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = async (t) => {
    setLoading(true);
    const params = t === 'all' ? '' : `?pillar=${t}`;
    const { data } = await api.get(`/resources${params}`);
    setItems(data.resources || []);
    setLoading(false);
  };

  useEffect(() => { load(tab); }, [tab]);

  return (
    <Shell>
      <div
        data-testid={IDS.resources.root}
        className="max-w-4xl mx-auto px-5 md:px-8 pt-6 md:pt-8 animate-fade-in"
      >
        <header className="mb-6">
          <p className="eyebrow">Biblioteca</p>
          <h1 className="mt-1.5 text-[26px] md:text-[30px] font-semibold text-zinc-900 tracking-tight">
            Leituras e escutas
          </h1>
          <p className="mt-2 text-[14px] text-zinc-500 max-w-xl">
            Uma seleção curta que complementa seus pilares. Nada obrigatório, escolha o que faz sentido para hoje.
          </p>
        </header>

        <div className="flex gap-2 overflow-x-auto no-scrollbar -mx-5 px-5 md:mx-0 md:px-0 mb-5">
          {PILLAR_TABS.map((t) => {
            const active = tab === t.key;
            return (
              <button
                key={t.key}
                onClick={() => setTab(t.key)}
                className={`shrink-0 inline-flex items-center gap-1.5 rounded-full px-3.5 py-2 text-[13px] font-medium transition-colors ${
                  active
                    ? 'text-white'
                    : 'bg-white hairline text-zinc-700 hover:bg-zinc-50'
                }`}
                style={active ? { background: 'var(--mf-brand)', border: '1px solid var(--mf-brand-hov)' } : {}}
              >
                <t.Icon strokeWidth={1.75} className="w-3.5 h-3.5" />
                {t.label}
              </button>
            );
          })}
        </div>

        {loading ? (
          <div className="mf-card p-10 flex justify-center">
            <Loader2 className="w-5 h-5 text-brand animate-spin" strokeWidth={1.75} />
          </div>
        ) : items.length === 0 ? (
          <div className="mf-card p-8 text-center">
            <p className="text-[15px] font-medium text-zinc-800">Sem recursos por aqui, no momento.</p>
            <p className="mt-2 text-[13px] text-zinc-500">Novos conteúdos entram toda semana.</p>
          </div>
        ) : (
          <ul className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {items.map((r) => {
              const Icon = TYPE_ICONS[r.type] || FileText;
              return (
                <li key={r.slug} data-testid={IDS.resources.item(r.slug)}>
                  <a
                    href={r.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="group block mf-card p-5 hover:border-brand transition-colors h-full"
                  >
                    <div className="flex items-start gap-3">
                      <span
                        className="w-9 h-9 rounded-lg shrink-0 flex items-center justify-center"
                        style={{ background: 'var(--mf-brand-soft)', color: 'var(--mf-brand)' }}
                      >
                        <Icon strokeWidth={1.75} className="w-4 h-4" />
                      </span>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="eyebrow-mono capitalize">{r.type}</span>
                          <span className="text-zinc-300">·</span>
                          <span className="mono text-[11px] text-zinc-500">{r.duration_min} min</span>
                        </div>
                        <h3 className="mt-1.5 text-[15px] font-semibold text-zinc-900 tracking-tight leading-snug">
                          {r.title}
                        </h3>
                        <p className="mt-1.5 text-[13px] text-zinc-500 leading-relaxed line-clamp-3">
                          {r.excerpt}
                        </p>
                      </div>
                      <ExternalLink strokeWidth={1.75} className="w-4 h-4 text-zinc-400 shrink-0 mt-1 group-hover:text-brand transition-colors" />
                    </div>
                  </a>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </Shell>
  );
};

export default Resources;
