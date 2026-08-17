import { useEffect, useState } from 'react';
import { Loader2, Save, User, GraduationCap, Sparkles, AlertTriangle } from 'lucide-react';
import Shell from '@/components/Shell';
import api from '@/lib/api';

const CHRONOTYPES = [
  { key: 'matutino', label: 'Matutino — desperto cedo' },
  { key: 'vespertino', label: 'Vespertino — pico à tarde' },
  { key: 'noturno', label: 'Noturno — energia à noite' },
];

const ENERGY_PEAKS = [
  { key: 'manha', label: 'Manhã' },
  { key: 'tarde', label: 'Tarde' },
  { key: 'noite', label: 'Noite' },
];

const FOCUS_TECHNIQUES = [
  { key: 'pomodoro', label: 'Pomodoro (25×5)' },
  { key: 'ultradian', label: 'Ultradian (90×20)' },
  { key: 'flow', label: 'Flow (60×15)' },
  { key: 'livre', label: 'Livre' },
];

const HOBBIES = [
  'musica', 'leitura', 'cinema', 'games', 'esporte', 'arte',
  'culinaria', 'amigos', 'familia', 'natureza', 'meditacao', 'escrita',
];

const SOCIAL_LEVELS = [
  { key: 'baixa', label: 'Baixa' },
  { key: 'media', label: 'Média' },
  { key: 'alta', label: 'Alta' },
];

const FAMILY_FREQ = [
  { key: 'diaria', label: 'Diária' },
  { key: 'semanal', label: 'Semanal' },
  { key: 'quinzenal', label: 'Quinzenal' },
  { key: 'mensal', label: 'Mensal' },
];

const ND_TYPES = [
  { key: '', label: '—' },
  { key: 'tdah', label: 'TDAH' },
  { key: 'tea', label: 'TEA (autismo)' },
  { key: 'outro', label: 'Outro' },
];

const emptyProfile = {
  course: 'Medicina',
  university: '',
  semester: 1,
  living_alone: false,
  has_dependencies: false,
  is_neurodivergent: false,
  neurodivergence_type: '',
  chronotype: 'matutino',
  wake_time: '07:00',
  sleep_time: '23:00',
  target_sleep_hours: 8,
  energy_peak: 'manha',
  focus_technique: 'pomodoro',
  hobbies: [],
  interests: [],
  family_pref: 'semanal',
  social_pref: 'media',
  physical_activity: 'leve',
  physical_days_per_week: 3,
  notify_channel: 'push',
  dark_mode: false,
  reduce_motion: false,
};

const PerfilExtendido = () => {
  const [form, setForm] = useState(emptyProfile);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [savedAt, setSavedAt] = useState(null);
  const [universities, setUniversities] = useState([]);
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState(null);

  useEffect(() => {
    (async () => {
      try {
        const [{ data: p }, { data: t }] = await Promise.all([
          api.get('/profile'),
          api.get('/academic/curriculum-templates'),
        ]);
        setForm({ ...emptyProfile, ...(p.profile || {}) });
        setUniversities(t.universities || []);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const update = (patch) => setForm((prev) => ({ ...prev, ...patch }));

  const toggleHobby = (h) => {
    const set = new Set(form.hobbies || []);
    if (set.has(h)) set.delete(h); else set.add(h);
    update({ hobbies: Array.from(set) });
  };

  const save = async () => {
    setSaving(true);
    try {
      const payload = { ...form };
      delete payload.user_id;
      delete payload.updated_at;
      delete payload.mode;
      const { data } = await api.patch('/profile', payload);
      setForm({ ...emptyProfile, ...(data.profile || {}) });
      setSavedAt(new Date());
    } finally {
      setSaving(false);
    }
  };

  const importCurriculum = async (replace = false) => {
    const uniSlug = universities.find(
      (u) => u.label.toLowerCase() === (form.university || '').toLowerCase()
        || u.slug === (form.university_slug || '')
    )?.slug;
    if (!uniSlug) return;
    setImporting(true);
    setImportResult(null);
    try {
      const { data } = await api.post('/academic/import-curriculum', {
        university: uniSlug,
        semester: form.semester || 1,
        replace,
      });
      setImportResult(data);
    } catch (e) {
      setImportResult({ error: e?.response?.data?.detail || 'Falha ao importar' });
    } finally { setImporting(false); }
  };

  const currentUniversitySlug = universities.find(
    (u) => u.label.toLowerCase() === (form.university || '').toLowerCase()
      || u.slug === (form.university_slug || '')
  )?.slug;
  const canImport = !!currentUniversitySlug && (form.semester >= 1 && form.semester <= 3);

  if (loading) {
    return (
      <Shell>
        <div className="max-w-3xl mx-auto pt-10 flex justify-center">
          <Loader2 className="w-5 h-5 text-brand animate-spin" strokeWidth={1.75} />
        </div>
      </Shell>
    );
  }

  const Field = ({ label, children, hint }) => (
    <label className="block">
      <span className="block text-[12px] font-medium text-zinc-500 uppercase tracking-wider mb-1.5">{label}</span>
      {children}
      {hint && <span className="mt-1 block text-[11.5px] text-zinc-400">{hint}</span>}
    </label>
  );

  const input = 'w-full px-3 py-2 rounded-lg text-[14px] hairline bg-white focus:outline-none focus:ring-2 focus:ring-brand/40';

  return (
    <Shell>
      <div data-testid="perfil-extendido-root" className="max-w-3xl mx-auto px-5 md:px-8 pt-6 md:pt-8 animate-fade-in pb-24">
        <header className="mb-6">
          <p className="eyebrow">Etapa 1 · Persistência</p>
          <h1 className="mt-1.5 text-[26px] md:text-[30px] font-semibold text-zinc-900 tracking-tight flex items-center gap-2">
            <User strokeWidth={1.75} className="w-6 h-6 text-brand" /> Perfil do estudante
          </h1>
          <p className="mt-2 text-[14px] text-zinc-500 max-w-xl">
            Suas informações ficam guardadas com segurança e alimentam a agenda, o estudo, o sono e o ócio.
          </p>
        </header>

        {/* Bloco Acadêmico */}
        <section className="mf-card p-5 md:p-6 mb-4">
          <h3 className="text-[15px] font-semibold text-zinc-900 mb-4">Vida acadêmica</h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Field label="Curso">
              <input data-testid="pe-course" className={input} value={form.course || ''} onChange={(e) => update({ course: e.target.value })} />
            </Field>
            <Field label="Faculdade">
              <select
                data-testid="pe-university"
                className={input}
                value={form.university || ''}
                onChange={(e) => update({ university: e.target.value })}
              >
                <option value="">— Selecione</option>
                {universities.map((u) => (
                  <option key={u.slug} value={u.label}>{u.label}</option>
                ))}
                <option value="__other__">Outra (digite abaixo)</option>
              </select>
              {form.university === '__other__' && (
                <input
                  className={`${input} mt-2`}
                  placeholder="Nome da sua faculdade"
                  onChange={(e) => update({ university: e.target.value })}
                />
              )}
            </Field>
            <Field label="Semestre">
              <input data-testid="pe-semester" type="number" min="1" max="14" className={input} value={form.semester || 1} onChange={(e) => update({ semester: parseInt(e.target.value || '1') })} />
            </Field>
            <Field label="Ferramenta de estudo">
              <select data-testid="pe-study-tool" className={input} value={form.study_tool || 'anki'} onChange={(e) => update({ study_tool: e.target.value })}>
                <option value="anki">Anki</option>
                <option value="quizlet">Quizlet</option>
                <option value="remnote">RemNote</option>
                <option value="caderno">Caderno</option>
                <option value="outro">Outro</option>
              </select>
            </Field>
            <label className="flex items-center gap-2 text-[13.5px] text-zinc-700">
              <input data-testid="pe-living-alone" type="checkbox" checked={!!form.living_alone} onChange={(e) => update({ living_alone: e.target.checked })} />
              Moro sozinho ou em república
            </label>
            <label className="flex items-center gap-2 text-[13.5px] text-zinc-700">
              <input data-testid="pe-has-deps" type="checkbox" checked={!!form.has_dependencies} onChange={(e) => update({ has_dependencies: e.target.checked })} />
              Tenho disciplina(s) em dependência
            </label>
          </div>
        </section>

        {/* Import grade oficial */}
        <section
          data-testid="curriculum-import-card"
          className="mf-card p-5 md:p-6 mb-4"
          style={{ borderLeft: '3px solid var(--mf-brand)', background: 'var(--mf-brand-soft)' }}
        >
          <div className="flex items-start gap-3">
            <div className="w-9 h-9 rounded-lg flex items-center justify-center text-white shrink-0"
                 style={{ background: 'var(--mf-brand)' }}>
              <GraduationCap strokeWidth={1.75} className="w-5 h-5" />
            </div>
            <div className="flex-1">
              <h3 className="text-[15px] font-semibold text-zinc-900">Importar grade oficial</h3>
              <p className="text-[13px] text-zinc-600 mt-1 max-w-xl">
                {canImport
                  ? <>Vamos carregar as disciplinas do <b>{form.semester}º período</b> da <b>{form.university}</b> automaticamente. Matérias com histórico de dependência ficam sinalizadas como críticas.</>
                  : <>Selecione uma das faculdades suportadas <span className="mono">(FAMINAS-BH ou FCMMG)</span> e um período entre 1 e 3 para carregar a grade oficial.</>
                }
              </p>
              {importResult?.imported >= 0 && (
                <div className="mt-3 rounded-lg p-3 hairline bg-white flex items-center gap-2">
                  <Sparkles className="w-4 h-4 text-brand" />
                  <p className="text-[13px] text-zinc-800">
                    <b>{importResult.imported}</b> disciplina(s) importada(s)
                    {importResult.skipped > 0 && <> · {importResult.skipped} já existentes ignoradas</>}.
                    Confira em <b>Perfil › Matérias</b>.
                  </p>
                </div>
              )}
              {importResult?.error && (
                <div className="mt-3 rounded-lg p-3 hairline bg-white flex items-center gap-2 border-red-300">
                  <AlertTriangle className="w-4 h-4 text-red-500" />
                  <p className="text-[13px] text-red-700">{importResult.error}</p>
                </div>
              )}
              <div className="mt-4 flex gap-2 flex-wrap">
                <button
                  data-testid="curriculum-import-btn"
                  onClick={() => importCurriculum(false)}
                  disabled={!canImport || importing}
                  className="mf-btn-primary flex items-center gap-2 disabled:opacity-40"
                >
                  {importing ? <Loader2 className="w-4 h-4 animate-spin" /> : <GraduationCap className="w-4 h-4" />}
                  {importing ? 'Importando…' : 'Importar grade oficial'}
                </button>
                {canImport && (
                  <button
                    data-testid="curriculum-import-replace"
                    onClick={() => importCurriculum(true)}
                    disabled={importing}
                    className="btn-ghost text-[13px]"
                    title="Remove disciplinas da grade oficial antes de reimportar"
                  >
                    Reimportar (substituir)
                  </button>
                )}
              </div>
            </div>
          </div>
        </section>

        {/* Bloco Neurodivergência */}
        <section className="mf-card p-5 md:p-6 mb-4">
          <h3 className="text-[15px] font-semibold text-zinc-900 mb-4">Neurodivergência</h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <label className="flex items-center gap-2 text-[13.5px] text-zinc-700">
              <input data-testid="pe-nd" type="checkbox" checked={!!form.is_neurodivergent} onChange={(e) => update({ is_neurodivergent: e.target.checked })} />
              Sou neurodivergente
            </label>
            <Field label="Tipo">
              <select data-testid="pe-nd-type" className={input} value={form.neurodivergence_type || ''} onChange={(e) => update({ neurodivergence_type: e.target.value })}>
                {ND_TYPES.map((t) => <option key={t.key} value={t.key}>{t.label}</option>)}
              </select>
            </Field>
          </div>
        </section>

        {/* Bloco Cronotipo / Sono */}
        <section className="mf-card p-5 md:p-6 mb-4">
          <h3 className="text-[15px] font-semibold text-zinc-900 mb-4">Ritmo biológico</h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Field label="Cronotipo">
              <select data-testid="pe-chronotype" className={input} value={form.chronotype} onChange={(e) => update({ chronotype: e.target.value })}>
                {CHRONOTYPES.map((c) => <option key={c.key} value={c.key}>{c.label}</option>)}
              </select>
            </Field>
            <Field label="Pico de energia">
              <select data-testid="pe-energy-peak" className={input} value={form.energy_peak} onChange={(e) => update({ energy_peak: e.target.value })}>
                {ENERGY_PEAKS.map((c) => <option key={c.key} value={c.key}>{c.label}</option>)}
              </select>
            </Field>
            <Field label="Acordar às">
              <input data-testid="pe-wake" type="time" className={input} value={form.wake_time} onChange={(e) => update({ wake_time: e.target.value })} />
            </Field>
            <Field label="Dormir às">
              <input data-testid="pe-sleep" type="time" className={input} value={form.sleep_time} onChange={(e) => update({ sleep_time: e.target.value })} />
            </Field>
            <Field label="Meta de sono (horas)">
              <input data-testid="pe-target-sleep" type="number" step="0.5" min="5" max="10" className={input} value={form.target_sleep_hours} onChange={(e) => update({ target_sleep_hours: parseFloat(e.target.value || '8') })} />
            </Field>
            <Field label="Técnica de foco">
              <select data-testid="pe-focus-technique" className={input} value={form.focus_technique} onChange={(e) => update({ focus_technique: e.target.value })}>
                {FOCUS_TECHNIQUES.map((c) => <option key={c.key} value={c.key}>{c.label}</option>)}
              </select>
            </Field>
          </div>
        </section>

        {/* Bloco Vida pessoal */}
        <section className="mf-card p-5 md:p-6 mb-4">
          <h3 className="text-[15px] font-semibold text-zinc-900 mb-4">Vida pessoal</h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Field label="Vida social">
              <select data-testid="pe-social" className={input} value={form.social_pref} onChange={(e) => update({ social_pref: e.target.value })}>
                {SOCIAL_LEVELS.map((c) => <option key={c.key} value={c.key}>{c.label}</option>)}
              </select>
            </Field>
            <Field label="Contato com família">
              <select data-testid="pe-family" className={input} value={form.family_pref} onChange={(e) => update({ family_pref: e.target.value })}>
                {FAMILY_FREQ.map((c) => <option key={c.key} value={c.key}>{c.label}</option>)}
              </select>
            </Field>
            <Field label="Atividade física semanal (dias)">
              <input data-testid="pe-phys-days" type="number" min="0" max="7" className={input} value={form.physical_days_per_week} onChange={(e) => update({ physical_days_per_week: parseInt(e.target.value || '0') })} />
            </Field>
            <Field label="Canal de notificação preferido">
              <select data-testid="pe-notify" className={input} value={form.notify_channel} onChange={(e) => update({ notify_channel: e.target.value })}>
                <option value="push">Push</option>
                <option value="whatsapp">WhatsApp</option>
                <option value="email">E-mail</option>
              </select>
            </Field>
          </div>

          <div className="mt-5">
            <p className="text-[12px] font-medium text-zinc-500 uppercase tracking-wider mb-2">Hobbies e interesses</p>
            <div className="flex flex-wrap gap-2">
              {HOBBIES.map((h) => {
                const active = (form.hobbies || []).includes(h);
                return (
                  <button
                    key={h}
                    data-testid={`pe-hobby-${h}`}
                    onClick={() => toggleHobby(h)}
                    className={`rounded-full px-3.5 py-1.5 text-[12.5px] font-medium transition-colors hairline ${
                      active ? 'text-white' : 'text-zinc-700 hover:bg-zinc-50'
                    }`}
                    style={active ? { background: 'var(--mf-brand)', borderColor: 'var(--mf-brand-hov)' } : { background: 'var(--mf-canvas)' }}
                  >
                    {h}
                  </button>
                );
              })}
            </div>
          </div>
        </section>

        <div className="sticky bottom-4 z-20 flex items-center justify-end gap-3">
          {savedAt && <span className="text-[12px] text-zinc-500">Salvo às {savedAt.toLocaleTimeString()}</span>}
          <button
            data-testid="pe-save-btn"
            onClick={save}
            disabled={saving}
            className="btn-primary shadow-lg"
          >
            {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" strokeWidth={1.75} />}
            Salvar perfil
          </button>
        </div>
      </div>
    </Shell>
  );
};

export default PerfilExtendido;
