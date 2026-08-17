import { useEffect, useState } from 'react';
import {
  Loader2,
  Shield,
  Users,
  BarChart3,
  ClipboardList,
  BookMarked,
  Plus,
  Trash2,
  AlertTriangle,
  FlaskConical,
  Lightbulb,
  GraduationCap,
  Building2,
  Microscope,
  Radar,
} from 'lucide-react';
import Shell from '@/components/Shell';
import { MipPhase2Dashboard } from '@/components/admin/MipPhase2Dashboard';
import api from '@/lib/api';

const TABS = [
  { key: 'stats',      label: 'Estatísticas', Icon: BarChart3 },
  { key: 'research',   label: 'Pesquisa',     Icon: FlaskConical },
  { key: 'mip',        label: 'MIP/PIE',      Icon: Radar },
  { key: 'users',      label: 'Usuários',     Icon: Users },
  { key: 'leisure',    label: 'CMS · Ócio',   Icon: ClipboardList },
  { key: 'resources',  label: 'CMS · Recursos', Icon: BookMarked },
];

const Metric = ({ label, value, hint, testId }) => (
  <div className="mf-card p-4" data-testid={testId}>
    <p className="eyebrow">{label}</p>
    <p className="mt-1.5 mono text-[24px] font-semibold text-zinc-900">{value}</p>
    {hint && <p className="mt-1 text-[11.5px] text-zinc-500">{hint}</p>}
  </div>
);

const StatsTab = () => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    (async () => {
      try {
        const { data } = await api.get('/admin/stats');
        setData(data);
      } finally { setLoading(false); }
    })();
  }, []);
  if (loading) return <div className="py-8 flex justify-center"><Loader2 className="w-5 h-5 text-brand animate-spin" /></div>;
  if (!data) return null;
  return (
    <div className="animate-fade-in space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3" data-testid="admin-stats-grid">
        <Metric label="Usuários" value={data.users.total} hint={`+${data.users.last_7d} nos últimos 7d`} />
        <Metric label="Perfis salvos" value={data.profiles} />
        <Metric label="Check-ins" value={data.checkins.total} hint={`+${data.checkins.last_7d} nos últimos 7d`} />
        <Metric label="Blocos de agenda" value={data.agenda_blocks} />
        <Metric label="Missões geradas" value={data.missions.bundles} />
        <Metric label="Missões concluídas" value={data.missions.completed_events} />
        <Metric
          label="Tutor IA hoje"
          value={`${data.ai_usage.tutor_messages}/${data.ai_usage.tutor_limit}`}
          hint="total da beta"
          testId="admin-tutor-usage"
        />
        <Metric
          label="Planos IA hoje"
          value={`${data.ai_usage.feedback_generations}/${data.ai_usage.feedback_limit}`}
          hint="total da beta"
          testId="admin-feedback-usage"
        />
      </div>
      <div className="mf-card p-5">
        <p className="text-[15px] font-semibold text-zinc-900 mb-3">Distribuição por modo</p>
        <ul className="space-y-2">
          {Object.entries(data.modes).map(([k, v]) => (
            <li key={k} className="flex items-center justify-between">
              <span className="text-[13.5px] capitalize text-zinc-700">{k}</span>
              <span className="mono text-[13.5px] font-semibold text-zinc-900">{v}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
};

const UsersTab = () => {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [changingUser, setChangingUser] = useState(null);
  useEffect(() => {
    (async () => {
      try {
        const { data } = await api.get('/admin/users');
        setUsers(data.users);
      } finally { setLoading(false); }
    })();
  }, []);
  const changePlan = async (userId, subscriptionPlan) => {
    setChangingUser(userId);
    try {
      await api.patch(`/admin/users/${userId}/subscription-plan`, {
        subscription_plan: subscriptionPlan,
      });
      setUsers((current) => current.map((user) => (
        user.user_id === userId ? { ...user, subscription_plan: subscriptionPlan } : user
      )));
    } finally {
      setChangingUser(null);
    }
  };
  if (loading) return <div className="py-8 flex justify-center"><Loader2 className="w-5 h-5 text-brand animate-spin" /></div>;
  return (
    <div className="mf-card overflow-hidden animate-fade-in" data-testid="admin-users-list">
      <table className="w-full text-[13px]">
        <thead className="bg-zinc-50">
          <tr>
            <th className="text-left py-2.5 px-4 font-medium text-zinc-500">Email</th>
            <th className="text-left py-2.5 px-4 font-medium text-zinc-500">Nome</th>
            <th className="text-left py-2.5 px-4 font-medium text-zinc-500">Admin</th>
            <th className="text-left py-2.5 px-4 font-medium text-zinc-500">Plano</th>
            <th className="text-left py-2.5 px-4 font-medium text-zinc-500">Criado em</th>
          </tr>
        </thead>
        <tbody>
          {users.map((u) => (
            <tr key={u.user_id} className="hairline-t">
              <td className="py-2.5 px-4 text-zinc-800">{u.email}</td>
              <td className="py-2.5 px-4 text-zinc-700">{u.name}</td>
              <td className="py-2.5 px-4 mono text-[12px]">{u.is_admin ? '✓' : '—'}</td>
              <td className="py-2.5 px-4">
                <select
                  data-testid={`admin-user-plan-${u.user_id}`}
                  value={u.subscription_plan || 'free'}
                  disabled={changingUser === u.user_id}
                  onChange={(event) => changePlan(u.user_id, event.target.value)}
                  className="rounded border border-zinc-200 bg-white px-2 py-1 text-[12px] text-zinc-700"
                >
                  <option value="free">Free</option>
                  <option value="premium">Premium</option>
                </select>
              </td>
              <td className="py-2.5 px-4 mono text-[11.5px] text-zinc-500">{u.created_at?.slice(0, 10)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

const LeisureTab = () => {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({ title: '', duration_min: 20, energy: 'baixa', tags: '' });

  const load = async () => {
    setLoading(true);
    try {
      const { data } = await api.get('/admin/cms/leisure');
      setItems(data.items);
    } finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  const add = async () => {
    if (!form.title.trim()) return;
    setSaving(true);
    try {
      await api.post('/admin/cms/leisure', {
        title: form.title, duration_min: parseInt(form.duration_min) || 20,
        energy: form.energy,
        tags: form.tags.split(',').map((t) => t.trim()).filter(Boolean),
      });
      setForm({ title: '', duration_min: 20, energy: 'baixa', tags: '' });
      await load();
    } finally { setSaving(false); }
  };

  const remove = async (id) => {
    await api.delete(`/admin/cms/leisure/${id}`);
    await load();
  };

  const input = 'px-3 py-2 rounded-lg text-[13.5px] hairline bg-white focus:outline-none focus:ring-2 focus:ring-brand/40';
  return (
    <div className="animate-fade-in space-y-4">
      <div className="mf-card p-4 md:p-5">
        <p className="text-[13.5px] font-semibold text-zinc-900 mb-3">Nova sugestão de ócio</p>
        <div className="grid grid-cols-1 md:grid-cols-5 gap-2.5">
          <input data-testid="cms-lz-title" className={`${input} md:col-span-2`} placeholder="Título" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
          <input data-testid="cms-lz-duration" className={input} type="number" min="5" placeholder="min" value={form.duration_min} onChange={(e) => setForm({ ...form, duration_min: e.target.value })} />
          <select data-testid="cms-lz-energy" className={input} value={form.energy} onChange={(e) => setForm({ ...form, energy: e.target.value })}>
            <option value="baixa">baixa</option>
            <option value="media">média</option>
            <option value="alta">alta</option>
          </select>
          <input data-testid="cms-lz-tags" className={input} placeholder="tags separadas por vírgula" value={form.tags} onChange={(e) => setForm({ ...form, tags: e.target.value })} />
        </div>
        <div className="mt-3 flex justify-end">
          <button data-testid="cms-lz-add-btn" onClick={add} disabled={saving} className="btn-primary">
            <Plus className="w-4 h-4" /> Adicionar
          </button>
        </div>
      </div>

      {loading ? (
        <div className="py-8 flex justify-center"><Loader2 className="w-5 h-5 text-brand animate-spin" /></div>
      ) : (
        <div className="mf-card overflow-hidden" data-testid="cms-lz-list">
          {items.length === 0 && <p className="text-zinc-500 text-center py-8">Nenhuma sugestão no CMS ainda.</p>}
          {items.map((it) => (
            <div key={it.id} className="flex items-center justify-between px-4 py-3 hairline-t">
              <div>
                <p className="text-[13.5px] font-semibold text-zinc-900">{it.title}</p>
                <p className="text-[11.5px] text-zinc-500">
                  {it.duration_min} min · {it.energy} · {(it.tags || []).join(', ')}
                </p>
              </div>
              <button onClick={() => remove(it.id)} className="text-zinc-400 hover:text-care">
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

const ResourcesTab = () => {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({
    title: '', type: 'artigo', duration_min: 5, category: 'estudo',
    pillar: 'estudos', excerpt: '', url: '',
  });

  const load = async () => {
    setLoading(true);
    try {
      const { data } = await api.get('/admin/cms/resources');
      setItems(data.items);
    } finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  const add = async () => {
    if (!form.title.trim() || !form.url.trim()) return;
    setSaving(true);
    try {
      await api.post('/admin/cms/resources', { ...form, duration_min: parseInt(form.duration_min) || 5 });
      setForm({ ...form, title: '', excerpt: '', url: '' });
      await load();
    } finally { setSaving(false); }
  };

  const remove = async (id) => {
    await api.delete(`/admin/cms/resources/${id}`);
    await load();
  };

  const input = 'px-3 py-2 rounded-lg text-[13.5px] hairline bg-white focus:outline-none focus:ring-2 focus:ring-brand/40';
  return (
    <div className="animate-fade-in space-y-4">
      <div className="mf-card p-4 md:p-5">
        <p className="text-[13.5px] font-semibold text-zinc-900 mb-3">Novo recurso</p>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-2.5">
          <input data-testid="cms-rs-title" className={input} placeholder="Título" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
          <select data-testid="cms-rs-type" className={input} value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value })}>
            <option value="artigo">artigo</option>
            <option value="video">video</option>
            <option value="podcast">podcast</option>
            <option value="audio">audio</option>
          </select>
          <input data-testid="cms-rs-duration" className={input} type="number" min="1" placeholder="minutos" value={form.duration_min} onChange={(e) => setForm({ ...form, duration_min: e.target.value })} />
          <input data-testid="cms-rs-category" className={input} placeholder="categoria (estudo|sono|...)" value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} />
          <input data-testid="cms-rs-pillar" className={input} placeholder="pilar (estudos|sono|bem_estar|...)" value={form.pillar} onChange={(e) => setForm({ ...form, pillar: e.target.value })} />
          <input data-testid="cms-rs-url" className={input} placeholder="URL" value={form.url} onChange={(e) => setForm({ ...form, url: e.target.value })} />
        </div>
        <input data-testid="cms-rs-excerpt" className={`${input} w-full mt-2.5`} placeholder="Resumo" value={form.excerpt} onChange={(e) => setForm({ ...form, excerpt: e.target.value })} />
        <div className="mt-3 flex justify-end">
          <button data-testid="cms-rs-add-btn" onClick={add} disabled={saving} className="btn-primary">
            <Plus className="w-4 h-4" /> Adicionar
          </button>
        </div>
      </div>

      {loading ? (
        <div className="py-8 flex justify-center"><Loader2 className="w-5 h-5 text-brand animate-spin" /></div>
      ) : (
        <div className="mf-card overflow-hidden" data-testid="cms-rs-list">
          {items.length === 0 && <p className="text-zinc-500 text-center py-8">Nenhum recurso no CMS ainda.</p>}
          {items.map((it) => (
            <div key={it.id} className="flex items-center justify-between px-4 py-3 hairline-t">
              <div>
                <p className="text-[13.5px] font-semibold text-zinc-900">{it.title}</p>
                <p className="text-[11.5px] text-zinc-500">
                  {it.type} · {it.duration_min} min · {it.category} · {it.pillar}
                </p>
                <a href={it.url} target="_blank" rel="noreferrer" className="text-[11.5px] text-brand break-all">{it.url}</a>
              </div>
              <button onClick={() => remove(it.id)} className="text-zinc-400 hover:text-care">
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

const DistBar = ({ dist }) => {
  const total = Object.values(dist || {}).reduce((a, b) => a + b, 0);
  if (!total) return <p className="text-[12px] text-zinc-400">sem dados</p>;
  return (
    <div className="space-y-1.5">
      {Object.entries(dist).map(([k, v]) => {
        const pct = Math.round((v / total) * 100);
        return (
          <div key={k}>
            <div className="flex items-center justify-between text-[12px] mb-0.5">
              <span className="text-zinc-700 capitalize"><span>{k}</span></span>
              <span className="mono text-zinc-500"><span>{v} · {pct}%</span></span>
            </div>
            <div className="h-1.5 rounded-full bg-zinc-100 overflow-hidden">
              <div className="h-full" style={{ width: `${pct}%`, background: 'var(--mf-brand)' }} />
            </div>
          </div>
        );
      })}
    </div>
  );
};

const HypothesisCard = ({ h }) => {
  const tone =
    h.confidence_level === 'consistente' ? 'success' :
    h.confidence_level === 'sugestiva' ? 'brand' :
    'attention';
  return (
    <li className="mf-card p-4 md:p-5" data-testid={`research-hypothesis-${h.id}`}>
      <div className="flex items-start gap-3">
        <span
          className="w-9 h-9 rounded-lg flex items-center justify-center shrink-0 mt-0.5"
          style={{ background: 'var(--mf-brand-soft)', color: 'var(--mf-brand)' }}
        >
          <Lightbulb strokeWidth={1.75} className="w-4 h-4" />
        </span>
        <div className="flex-1 min-w-0">
          <p className="eyebrow"><span>{h.prompt}</span></p>
          <h4 className="mt-1.5 text-[15px] font-semibold text-zinc-900 leading-snug">
            <span>{h.title}</span>
          </h4>
          <p className="mt-2 text-[13.5px] text-zinc-700 leading-relaxed">
            <span>{h.statement}</span>
          </p>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <span className={`pill pill-${tone}`}>
              <span>confiança: {h.confidence_level}</span>
            </span>
            <span className="pill">
              <span>Δ = {h.delta_pct > 0 ? '+' : ''}{h.delta_pct}%</span>
            </span>
            <span className="pill">
              <span>n = {Object.values(h.sample || {}).filter((v) => typeof v === 'number').join(' / ')}</span>
            </span>
          </div>
          <p className="mt-3 text-[11.5px] text-zinc-500 italic">
            <span>⚠ {h.warning}</span>
          </p>
        </div>
      </div>
    </li>
  );
};

const ResearchTab = () => {
  const [cohort, setCohort] = useState(null);
  const [hyp, setHyp] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const [c, h] = await Promise.all([
          api.get('/admin/research/cohort'),
          api.get('/admin/research/hypotheses'),
        ]);
        setCohort(c.data);
        setHyp(h.data);
      } finally { setLoading(false); }
    })();
  }, []);

  if (loading) return <div className="py-8 flex justify-center"><Loader2 className="w-5 h-5 text-brand animate-spin" /></div>;
  if (!cohort || !hyp) return null;

  return (
    <div className="animate-fade-in space-y-6" data-testid="admin-research-root">
      {/* Banner LGPD/anonimização */}
      <div
        className="mf-card p-4 md:p-5 flex items-start gap-3"
        style={{ background: 'var(--mf-brand-soft)', borderColor: 'transparent' }}
      >
        <FlaskConical strokeWidth={1.75} className="w-5 h-5 shrink-0 mt-0.5" style={{ color: 'var(--mf-brand)' }} />
        <div>
          <p className="text-[13.5px] font-semibold" style={{ color: 'var(--mf-brand)' }}>
            <span>Banco anonimizado — MedFlow Research</span>
          </p>
          <p className="mt-1 text-[12.5px] text-zinc-700 leading-relaxed">
            <span>{cohort.notice}</span>
          </p>
        </div>
      </div>

      {/* Coorte agregada */}
      <div>
        <p className="eyebrow"><span>coorte anonimizada</span></p>
        <h2 className="mt-1 text-[19px] font-semibold text-zinc-900 tracking-tight">
          <span>População observada</span>
        </h2>
        <div className="mt-4 grid grid-cols-2 md:grid-cols-4 gap-3" data-testid="research-cohort-grid">
          <Metric label="Usuários (total)" value={cohort.population.total_users} />
          <Metric label="Perfis registrados" value={cohort.population.total_profiles} />
          <Metric label="Neurodivergentes" value={`${Math.round(cohort.population.neurodivergent_share * 100)}%`} />
          <Metric label="Mora sozinho" value={`${Math.round(cohort.population.living_alone_share * 100)}%`} />
          <Metric label="Check-ins totais" value={cohort.checkins.total} />
          <Metric label="Humor médio" value={cohort.checkins.avg_mood ?? '—'} />
          <Metric label="Estresse médio" value={cohort.checkins.avg_stress ?? '—'} />
          <Metric label="Taxa de conclusão" value={`${Math.round(cohort.recommendations.completion_rate * 100)}%`} hint={`${cohort.recommendations.completed}/${cohort.recommendations.total} recomendações`} />
        </div>

        <div className="mt-4 grid grid-cols-1 md:grid-cols-3 gap-3">
          <div className="mf-card p-4">
            <p className="text-[13px] font-semibold text-zinc-900 mb-3"><span>Período (faixa)</span></p>
            <DistBar dist={cohort.period_distribution} />
          </div>
          <div className="mf-card p-4">
            <p className="text-[13px] font-semibold text-zinc-900 mb-3"><span>Cronotipo</span></p>
            <DistBar dist={cohort.chronotype_distribution} />
          </div>
          <div className="mf-card p-4">
            <p className="text-[13px] font-semibold text-zinc-900 mb-3"><span>Técnica de foco</span></p>
            <DistBar dist={cohort.focus_technique_distribution} />
          </div>
        </div>
      </div>

      {/* Hipóteses */}
      <div>
        <p className="eyebrow"><span>hipóteses para investigação</span></p>
        <h2 className="mt-1 text-[19px] font-semibold text-zinc-900 tracking-tight">
          <span>Padrões observados</span>
        </h2>
        <p className="mt-2 text-[13.5px] text-zinc-600 max-w-2xl leading-relaxed">
          <span>{hyp.notice}</span>
        </p>

        {hyp.count === 0 ? (
          <div className="mt-4 mf-card p-6 text-center" data-testid="research-no-hypotheses">
            <p className="text-[13.5px] text-zinc-500">
              <span>Ainda não há dados suficientes para gerar hipóteses. Cada padrão precisa de pelo menos 3 observações. Continue coletando check-ins e recomendações.</span>
            </p>
          </div>
        ) : (
          <ul className="mt-4 space-y-3" data-testid="research-hypotheses-list">
            {hyp.hypotheses.map((h) => <HypothesisCard key={h.id} h={h} />)}
          </ul>
        )}
      </div>

      {/* Visão de três produtos */}
      <div className="mt-2" data-testid="research-vision">
        <p className="eyebrow"><span>visão a longo prazo</span></p>
        <h2 className="mt-1 text-[19px] font-semibold text-zinc-900 tracking-tight">
          <span>Três produtos, um ativo estratégico</span>
        </h2>
        <p className="mt-2 text-[13.5px] text-zinc-600 max-w-2xl leading-relaxed">
          <span>Empresas de educação têm conteúdo. Poucas têm dados de como humanos aprendem.</span>
        </p>
        <div className="mt-4 grid grid-cols-1 md:grid-cols-3 gap-3">
          {[
            { Icon: GraduationCap, k: 'student',     name: hyp.vision.student },
            { Icon: Building2,     k: 'institution', name: hyp.vision.institution },
            { Icon: Microscope,    k: 'research',    name: hyp.vision.research },
          ].map((v) => (
            <div key={v.k} className="mf-card p-4 md:p-5" data-testid={`research-vision-${v.k}`}>
              <span
                className="w-10 h-10 rounded-lg flex items-center justify-center"
                style={{ background: 'var(--mf-brand-soft)', color: 'var(--mf-brand)' }}
              >
                <v.Icon strokeWidth={1.75} className="w-5 h-5" />
              </span>
              <p className="mt-3 text-[13.5px] text-zinc-800 leading-relaxed"><span>{v.name}</span></p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

const Admin = () => {
  const [tab, setTab] = useState('stats');
  const [checked, setChecked] = useState(null);

  useEffect(() => {
    (async () => {
      try {
        const { data } = await api.get('/admin/whoami');
        setChecked(!!data.is_admin);
      } catch (e) { setChecked(false); }
    })();
  }, []);

  if (checked === null) {
    return <Shell><div className="pt-10 flex justify-center"><Loader2 className="w-5 h-5 animate-spin text-brand" /></div></Shell>;
  }
  if (checked === false) {
    return (
      <Shell>
        <div className="max-w-xl mx-auto pt-16 text-center animate-fade-in" data-testid="admin-forbidden">
          <AlertTriangle className="w-8 h-8 text-care mx-auto mb-3" strokeWidth={1.75} />
          <h2 className="text-[20px] font-semibold text-zinc-900">Acesso restrito</h2>
          <p className="mt-2 text-[13.5px] text-zinc-500">Apenas administradores podem ver o painel.</p>
        </div>
      </Shell>
    );
  }

  return (
    <Shell>
      <div data-testid="admin-root" className="max-w-6xl mx-auto px-5 md:px-8 pt-6 md:pt-8">
        <header className="mb-6 flex items-center gap-3">
          <span className="w-11 h-11 rounded-xl flex items-center justify-center" style={{ background: 'var(--mf-brand-soft)', color: 'var(--mf-brand)' }}>
            <Shield strokeWidth={1.75} className="w-5 h-5" />
          </span>
          <div>
            <p className="eyebrow">Painel administrativo</p>
            <h1 className="text-[24px] md:text-[28px] font-semibold text-zinc-900 tracking-tight">
              Coleta de dados & CMS
            </h1>
          </div>
        </header>

        <div role="tablist" className="mf-card p-1.5 flex gap-1 mb-5 overflow-x-auto">
          {TABS.map((t) => (
            <button
              key={t.key}
              data-testid={`admin-tab-${t.key}`}
              onClick={() => setTab(t.key)}
              className={`flex-1 min-w-[140px] flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg text-[13.5px] font-medium transition-colors ${
                tab === t.key ? 'text-white' : 'text-zinc-700 hover:bg-zinc-50'
              }`}
              style={tab === t.key ? { background: 'var(--mf-brand)' } : {}}
            >
              <t.Icon className="w-4 h-4" strokeWidth={1.75} />
              {t.label}
            </button>
          ))}
        </div>

        {tab === 'stats'     && <StatsTab />}
        {tab === 'research'  && <ResearchTab />}
        {tab === 'mip'       && <MipPhase2Dashboard />}
        {tab === 'users'     && <UsersTab />}
        {tab === 'leisure'   && <LeisureTab />}
        {tab === 'resources' && <ResourcesTab />}
      </div>
    </Shell>
  );
};

export default Admin;
