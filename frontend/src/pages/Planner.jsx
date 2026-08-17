import { useEffect, useState } from 'react';
import { Loader2, Sparkles, Plus, Trash2, CheckCircle2, Circle, Coffee, Moon, Brain, CalendarDays, Timer } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import Shell from '@/components/Shell';
import api from '@/lib/api';

const CATEGORIES = [
  { key: 'academic', label: 'Acadêmico', color: '#2F6BFF' },
  { key: 'study',    label: 'Estudo',     color: '#7A5CFF' },
  { key: 'physical', label: 'Físico',     color: '#22B573' },
  { key: 'leisure',  label: 'Ócio',       color: '#F59E0B' },
  { key: 'social',   label: 'Social',     color: '#EC4899' },
  { key: 'family',   label: 'Família',    color: '#EF4444' },
  { key: 'love',     label: 'Afetivo',    color: '#F472B6' },
  { key: 'sleep',    label: 'Sono',       color: '#0F172A' },
  { key: 'care',     label: 'Autocuidado', color: '#14B8A6' },
];

const DAYS = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom'];
const CAT_MAP = Object.fromEntries(CATEGORIES.map((c) => [c.key, c]));

const TABS = [
  { key: 'agenda', label: 'Agenda',    Icon: CalendarDays },
  { key: 'study',  label: 'Estudo',    Icon: Brain },
  { key: 'sleep',  label: 'Sono',      Icon: Moon },
  { key: 'leisure', label: 'Ócio',     Icon: Coffee },
];

// ─── Agenda tab ────────────────────────────────────────────────
const AgendaTab = () => {
  const navigate = useNavigate();
  const [week, setWeek] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({
    title: '', category: 'study', day_of_week: 0, start_time: '08:00', end_time: '09:00',
  });

  const load = async () => {
    setLoading(true);
    try {
      const { data } = await api.get('/agenda/week');
      setWeek(data.days);
    } finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  const propose = async () => {
    setBusy(true);
    try {
      await api.post('/agenda/proposal?replace=true');
      await load();
    } finally { setBusy(false); }
  };

  const addBlock = async () => {
    if (!form.title.trim()) return;
    setBusy(true);
    try {
      await api.post('/agenda/blocks', form);
      setForm({ ...form, title: '' });
      await load();
    } finally { setBusy(false); }
  };

  const toggleDone = async (b) => {
    setBusy(true);
    try {
      await api.patch(`/agenda/blocks/${b.id}`, { done: !b.done });
      await load();
    } catch (e) {
      // Bloco pode ter sido excluído em outra aba/sessão — recarrega silenciosamente
      if (e?.response?.status !== 404) console.warn(e);
      await load();
    } finally { setBusy(false); }
  };

  const removeBlock = async (id) => {
    setBusy(true);
    try {
      await api.delete(`/agenda/blocks/${id}`);
      await load();
    } catch (e) {
      if (e?.response?.status !== 404) console.warn(e);
      await load();
    } finally { setBusy(false); }
  };

  if (loading) return <div className="py-8 flex justify-center"><Loader2 className="w-5 h-5 text-brand animate-spin" /></div>;

  const totalBlocks = Object.values(week || {}).reduce((n, arr) => n + arr.length, 0);
  const input = 'w-full px-3 py-2 rounded-lg text-[13.5px] hairline bg-white focus:outline-none focus:ring-2 focus:ring-brand/40';

  return (
    <div className="animate-fade-in">
      {/* Ações */}
      <div className="mf-card p-4 md:p-5 mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="eyebrow">Etapa 2 · Agenda</p>
          <p className="mt-1 text-[13.5px] text-zinc-600">
            {totalBlocks > 0 ? `${totalBlocks} blocos na sua semana.` : 'Comece gerando uma proposta a partir do seu perfil.'}
          </p>
        </div>
        <button
          data-testid="agenda-propose-btn"
          onClick={propose}
          disabled={busy}
          className="btn-primary"
        >
          <Sparkles className="w-4 h-4" strokeWidth={1.75} />
          Gerar agenda proposta
        </button>
      </div>

      {/* Form novo bloco */}
      <div className="mf-card p-4 md:p-5 mb-5">
        <p className="text-[13.5px] font-semibold text-zinc-900 mb-3">Adicionar bloco manual</p>
        <div className="grid grid-cols-1 md:grid-cols-6 gap-2.5">
          <input
            data-testid="agenda-title-input"
            placeholder="Ex.: Anatomia — músculos"
            className={`${input} md:col-span-2`}
            value={form.title}
            onChange={(e) => setForm({ ...form, title: e.target.value })}
          />
          <select data-testid="agenda-category" className={input} value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}>
            {CATEGORIES.map((c) => <option key={c.key} value={c.key}>{c.label}</option>)}
          </select>
          <select data-testid="agenda-day" className={input} value={form.day_of_week} onChange={(e) => setForm({ ...form, day_of_week: parseInt(e.target.value) })}>
            {DAYS.map((d, i) => <option key={d} value={i}>{d}</option>)}
          </select>
          <input data-testid="agenda-start" type="time" className={input} value={form.start_time} onChange={(e) => setForm({ ...form, start_time: e.target.value })} />
          <input data-testid="agenda-end" type="time" className={input} value={form.end_time} onChange={(e) => setForm({ ...form, end_time: e.target.value })} />
        </div>
        <div className="mt-3 flex justify-end">
          <button data-testid="agenda-add-btn" onClick={addBlock} disabled={busy} className="btn-secondary">
            <Plus className="w-4 h-4" strokeWidth={1.75} /> Adicionar
          </button>
        </div>
      </div>

      {/* Weekly grid */}
      <div data-testid="agenda-week-grid" className="grid grid-cols-1 md:grid-cols-7 gap-2.5">
        {DAYS.map((d, dow) => (
          <div key={d} className="mf-card p-3 min-h-[180px]" data-testid={`agenda-day-${dow}`}>
            <div className="flex items-center justify-between mb-2">
              <p className="text-[12px] font-semibold text-zinc-900 tracking-tight uppercase">{d}</p>
              <span className="text-[11px] text-zinc-400">{(week?.[dow] || []).length}</span>
            </div>
            <div className="space-y-1.5">
              {(week?.[dow] || []).map((b) => {
                const cat = CAT_MAP[b.category] || { color: '#6B8E76', label: b.category };
                return (
                  <div
                    key={b.id}
                    data-testid={`agenda-block-${b.id}`}
                    className="rounded-lg p-2 hairline group relative"
                    style={{ borderLeft: `3px solid ${b.color || cat.color}`, background: 'var(--mf-canvas)' }}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <p className="text-[12.5px] font-semibold text-zinc-900 leading-tight truncate">{b.title}</p>
                        <p className="text-[10.5px] text-zinc-500 mono mt-0.5">
                          {b.start_time}–{b.end_time} · {cat.label}
                        </p>
                      </div>
                      <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                        {(b.category === 'study' || b.category === 'academic') && (
                          <button
                            onClick={() => navigate(`/pomodoro?block_id=${b.id}`)}
                            title="Iniciar Pomodoro nesse bloco"
                            className="text-brand hover:opacity-75"
                            data-testid={`agenda-block-focus-${b.id}`}
                          >
                            <Timer className="w-4 h-4" />
                          </button>
                        )}
                        <button onClick={() => toggleDone(b)} title="Marcar" className="text-zinc-500 hover:text-brand">
                          {b.done ? <CheckCircle2 className="w-4 h-4 text-success" /> : <Circle className="w-4 h-4" />}
                        </button>
                        <button onClick={() => removeBlock(b.id)} title="Excluir" className="text-zinc-400 hover:text-care">
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>
                  </div>
                );
              })}
              {(week?.[dow] || []).length === 0 && (
                <p className="text-[11px] text-zinc-400 italic">Vazio</p>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Legenda */}
      <div className="mt-6 flex flex-wrap gap-2">
        {CATEGORIES.map((c) => (
          <span key={c.key} className="inline-flex items-center gap-1.5 text-[11.5px] text-zinc-600">
            <span className="w-2.5 h-2.5 rounded-sm" style={{ background: c.color }} />
            {c.label}
          </span>
        ))}
      </div>
    </div>
  );
};

// ─── Estudo tab ────────────────────────────────────────────────
const StudyTab = () => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    (async () => {
      try {
        const { data } = await api.get('/study/strategies');
        setData(data.strategies);
      } finally { setLoading(false); }
    })();
  }, []);
  if (loading) return <div className="py-8 flex justify-center"><Loader2 className="w-5 h-5 text-brand animate-spin" /></div>;
  if (!data) return <p className="text-zinc-500 text-center py-8">Preencha seu perfil para receber estratégias.</p>;

  return (
    <div className="animate-fade-in space-y-4">
      <div className="mf-card p-5">
        <p className="eyebrow">Etapa 3 · Estratégias de estudo</p>
        <h3 className="mt-1 text-[20px] font-semibold text-zinc-900">Sua sessão ideal</h3>
        <div className="mt-4 grid grid-cols-2 md:grid-cols-4 gap-3">
          <Metric label="Bloco de foco" value={`${data.session.block_minutes} min`} />
          <Metric label="Pausa" value={`${data.session.break_minutes} min`} />
          <Metric label="Blocos por sessão" value={data.session.blocks_per_session} />
          <Metric label="Melhor janela" value={data.best_window} />
        </div>
        <p className="mt-4 text-[13px] text-zinc-600"><b>Técnica:</b> {data.session.technique} · <b>Frequência semanal:</b> {data.weekly_frequency}</p>
      </div>

      <div className="mf-card p-5" data-testid="study-techniques">
        <p className="text-[15px] font-semibold text-zinc-900 mb-3">Técnicas recomendadas</p>
        <ul className="space-y-2.5">
          {data.techniques.map((t) => (
            <li key={t.name} className="p-3 rounded-lg hairline">
              <p className="text-[13.5px] font-semibold text-zinc-900">{t.name}</p>
              <p className="mt-0.5 text-[12.5px] text-zinc-600 leading-relaxed">{t.detail}</p>
            </li>
          ))}
        </ul>
      </div>

      {data.priority_exams?.length > 0 && (
        <div className="mf-card p-5" data-testid="study-priorities">
          <p className="text-[15px] font-semibold text-zinc-900 mb-3">Provas priorizadas</p>
          <ul className="space-y-2">
            {data.priority_exams.map((e) => (
              <li key={e.exam_id} className="flex items-center justify-between p-3 rounded-lg hairline">
                <div>
                  <p className="text-[13.5px] font-semibold text-zinc-900">{e.subject_name} — {e.name}</p>
                  <p className="text-[11.5px] text-zinc-500 mono">{e.exam_date}</p>
                </div>
                <span className={`mono text-[12px] font-semibold ${e.days_left <= 3 ? 'text-care' : 'text-brand'}`}>
                  {e.days_left != null ? `${e.days_left}d` : '—'}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {data.tips?.length > 0 && (
        <div className="mf-card p-5">
          <p className="text-[15px] font-semibold text-zinc-900 mb-3">Dicas para o seu perfil</p>
          <ul className="space-y-2 text-[13.5px] text-zinc-700 list-disc pl-5">
            {data.tips.map((t, i) => <li key={i}>{t}</li>)}
          </ul>
        </div>
      )}
    </div>
  );
};

const Metric = ({ label, value }) => (
  <div className="p-3 rounded-lg hairline" style={{ background: 'var(--mf-canvas)' }}>
    <p className="text-[11px] text-zinc-500 uppercase tracking-wider">{label}</p>
    <p className="mt-1 mono text-[18px] font-semibold text-zinc-900">{value}</p>
  </div>
);

// ─── Sono tab ────────────────────────────────────────────────
const SleepTab = () => {
  const [plan, setPlan] = useState(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    (async () => {
      try {
        const { data } = await api.get('/sleep/plan');
        setPlan(data.plan);
      } finally { setLoading(false); }
    })();
  }, []);
  if (loading) return <div className="py-8 flex justify-center"><Loader2 className="w-5 h-5 text-brand animate-spin" /></div>;
  if (!plan) return null;

  return (
    <div className="animate-fade-in space-y-4">
      <div className="mf-card p-5">
        <p className="eyebrow">Etapa 4 · Dieta de sono</p>
        <h3 className="mt-1 text-[20px] font-semibold text-zinc-900">Sua rotina de sono</h3>
        <div className="mt-4 grid grid-cols-2 md:grid-cols-4 gap-3">
          <Metric label="Meta" value={`${plan.target_hours} h`} />
          <Metric label="Dormir" value={plan.sleep_time} />
          <Metric label="Acordar" value={plan.wake_time} />
          <Metric label="Cronotipo" value={plan.chronotype} />
        </div>
      </div>

      <div className="mf-card p-5" data-testid="sleep-checklist">
        <p className="text-[15px] font-semibold text-zinc-900 mb-3">Checklist do fim de dia</p>
        <ul className="space-y-2">
          {plan.checklist.map((c, i) => (
            <li key={i} className="flex items-center gap-3 p-3 rounded-lg hairline">
              <span className="mono text-[12.5px] font-semibold text-brand w-14">{c.time}</span>
              <span className="text-[13.5px] text-zinc-800">{c.label}</span>
            </li>
          ))}
        </ul>
      </div>

      <div className="mf-card p-5">
        <p className="text-[15px] font-semibold text-zinc-900 mb-3">Dicas de higiene do sono</p>
        <ul className="space-y-2 text-[13.5px] text-zinc-700 list-disc pl-5">
          {plan.tips.map((t, i) => <li key={i}>{t}</li>)}
        </ul>
        <p className="mt-4 text-[12.5px] text-zinc-500">Cochilo estratégico: <span className="mono font-semibold">{plan.nap_window}</span></p>
      </div>
    </div>
  );
};

// ─── Ócio tab ────────────────────────────────────────────────
const LeisureTab = () => {
  const [items, setItems] = useState([]);
  const [hobbies, setHobbies] = useState([]);
  const [loading, setLoading] = useState(true);
  const [maxMin, setMaxMin] = useState(45);
  const [energy, setEnergy] = useState('');

  const load = async () => {
    setLoading(true);
    try {
      const qs = new URLSearchParams();
      if (maxMin) qs.set('max_minutes', String(maxMin));
      if (energy) qs.set('energy', energy);
      const { data } = await api.get(`/leisure/suggestions?${qs}`);
      setItems(data.suggestions);
      setHobbies(data.hobbies || []);
    } finally { setLoading(false); }
  };
  useEffect(() => { load(); /* eslint-disable-next-line */ }, []);

  const input = 'px-3 py-2 rounded-lg text-[13px] hairline bg-white focus:outline-none focus:ring-2 focus:ring-brand/40';

  return (
    <div className="animate-fade-in space-y-4">
      <div className="mf-card p-5">
        <p className="eyebrow">Etapa 5 · Propostas de ócio</p>
        <h3 className="mt-1 text-[20px] font-semibold text-zinc-900">Ideias para descansar</h3>
        <p className="mt-2 text-[13px] text-zinc-500">
          Personalizado com seus hobbies: {hobbies.length ? hobbies.join(', ') : 'preencha em Perfil.'}
        </p>
        <div className="mt-4 flex flex-wrap items-center gap-2.5">
          <label className="text-[12.5px] text-zinc-600">Tempo disponível:
            <input data-testid="leisure-max-min" type="number" min="5" step="5" className={`${input} ml-2 w-24`} value={maxMin} onChange={(e) => setMaxMin(parseInt(e.target.value || '0'))} />
          </label>
          <label className="text-[12.5px] text-zinc-600">Energia:
            <select data-testid="leisure-energy" className={`${input} ml-2`} value={energy} onChange={(e) => setEnergy(e.target.value)}>
              <option value="">qualquer</option>
              <option value="baixa">baixa</option>
              <option value="media">média</option>
              <option value="alta">alta</option>
            </select>
          </label>
          <button data-testid="leisure-apply-btn" onClick={load} className="btn-secondary">Atualizar</button>
        </div>
      </div>

      {loading ? (
        <div className="py-8 flex justify-center"><Loader2 className="w-5 h-5 text-brand animate-spin" /></div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3" data-testid="leisure-list">
          {items.map((it) => (
            <div key={it.slug} data-testid={`leisure-item-${it.slug}`} className="mf-card p-4 flex items-start gap-3">
              <span className="w-10 h-10 rounded-lg flex items-center justify-center shrink-0" style={{ background: 'var(--mf-brand-soft)', color: 'var(--mf-brand)' }}>
                <Coffee className="w-4 h-4" strokeWidth={1.75} />
              </span>
              <div className="flex-1 min-w-0">
                <p className="text-[14px] font-semibold text-zinc-900">{it.title}</p>
                <p className="text-[12px] text-zinc-500 mt-0.5">
                  {it.duration_min} min · energia {it.energy}
                </p>
                <div className="mt-1.5 flex flex-wrap gap-1.5">
                  {it.tags.map((tag) => (
                    <span key={tag} className="text-[10.5px] text-zinc-600 bg-zinc-100 px-1.5 py-0.5 rounded">{tag}</span>
                  ))}
                </div>
              </div>
            </div>
          ))}
          {items.length === 0 && <p className="text-zinc-500 text-center py-8 md:col-span-2">Sem sugestões para esse filtro.</p>}
        </div>
      )}
    </div>
  );
};

// ─── Página principal ─────────────────────────────────────────
const Planner = () => {
  const [tab, setTab] = useState('agenda');

  return (
    <Shell>
      <div data-testid="planner-root" className="max-w-6xl mx-auto px-5 md:px-8 pt-6 md:pt-8">
        <header className="mb-6">
          <p className="eyebrow">Copiloto de rotina</p>
          <h1 className="mt-1.5 text-[26px] md:text-[32px] font-semibold text-zinc-900 tracking-tight">
            Planejamento por etapas
          </h1>
          <p className="mt-2 text-[14px] text-zinc-500 max-w-2xl">
            Agenda, estratégias de estudo, sono e ócio — tudo baseado no seu perfil.
          </p>
        </header>

        {/* Tabs */}
        <div role="tablist" className="mf-card p-1.5 flex gap-1 mb-5 overflow-x-auto">
          {TABS.map((t) => (
            <button
              key={t.key}
              data-testid={`planner-tab-${t.key}`}
              role="tab"
              aria-selected={tab === t.key}
              onClick={() => setTab(t.key)}
              className={`flex-1 min-w-[110px] flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg text-[13.5px] font-medium transition-colors ${
                tab === t.key ? 'text-white' : 'text-zinc-700 hover:bg-zinc-50'
              }`}
              style={tab === t.key ? { background: 'var(--mf-brand)' } : {}}
            >
              <t.Icon className="w-4 h-4" strokeWidth={1.75} />
              {t.label}
            </button>
          ))}
        </div>

        {tab === 'agenda'  && <AgendaTab />}
        {tab === 'study'   && <StudyTab />}
        {tab === 'sleep'   && <SleepTab />}
        {tab === 'leisure' && <LeisureTab />}
      </div>
    </Shell>
  );
};

export default Planner;
