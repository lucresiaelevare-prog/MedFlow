import { useEffect, useState } from 'react';
import { Loader2, CalendarClock, Stethoscope, Repeat, RotateCcw, Sun, Moon, BookOpen, Bell, Type, Contrast, Sparkles, EyeOff, UserRoundX } from 'lucide-react';
import Shell from '@/components/Shell';
import api from '@/lib/api';
import IDS from '@/constants/testIds';
import { useTheme } from '@/context/ThemeContext';
import { useAccessibility } from '@/context/AccessibilityContext';

const MODES = [
  { key: 'rotina',      label: 'Rotina',            icon: Sun,           desc: 'A organização normal do seu dia.' },
  { key: 'prova',       label: 'Semana de provas',  icon: CalendarClock, desc: 'Prioriza revisão ativa curta, protege o sono e reduz o lazer.' },
  { key: 'plantao',     label: 'Plantão',           icon: Stethoscope,   desc: 'Foco em micro-recuperação: hidratar, alongar, cochilo curto.' },
  { key: 'dependencia', label: 'Dependência',       icon: Repeat,        desc: 'Adiciona pequenas ações extras da disciplina em dependência.' },
  { key: 'recuperacao', label: 'Recuperação',       icon: RotateCcw,     desc: 'Usa os tópicos mais fracos da última prova para reorganizar o estudo.' },
];

const STUDY_TOOLS = [
  { key: 'anki',    label: 'Anki' },
  { key: 'quizlet', label: 'Quizlet' },
  { key: 'remnote', label: 'RemNote' },
  { key: 'caderno', label: 'Caderno' },
  { key: 'outro',   label: 'Outro' },
];

const Settings = () => {
  const [loading, setLoading] = useState(true);
  const [profile, setProfile] = useState(null);
  const [saving, setSaving] = useState(false);
  const { theme, setTheme } = useTheme();
  const { prefs: a11y, update: updateA11y } = useAccessibility();

  const load = async () => {
    setLoading(true);
    const { data } = await api.get('/profile');
    setProfile(data.profile);
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  const setMode = async (mode) => {
    setSaving(true);
    try {
      await api.post('/mode', { mode });
      setProfile({ ...profile, mode });
    } finally { setSaving(false); }
  };

  const setStudyTool = async (tool) => {
    setSaving(true);
    try {
      const { data } = await api.patch('/profile', { study_tool: tool });
      setProfile(data.profile);
    } finally { setSaving(false); }
  };

  const setNotifyChannel = async (channel) => {
    setSaving(true);
    try {
      const { data } = await api.patch('/profile', { notify_channel: channel });
      setProfile(data.profile);
    } finally { setSaving(false); }
  };

  const setDarkMode = async (dark) => {
    setTheme(dark ? 'dark' : 'light');
    try {
      const { data } = await api.patch('/profile', { dark_mode: dark });
      setProfile(data.profile);
    } catch (e) { /* ignore */ }
  };

  const patchA11y = async (patch) => {
    await updateA11y(patch);
    setProfile((p) => ({ ...(p || {}), ...patch }));
  };

  const toggleAnonymous = async (v) => {
    setSaving(true);
    try {
      const { data } = await api.patch('/profile', { anonymous_community: v });
      setProfile(data.profile);
    } finally { setSaving(false); }
  };

  if (loading) {
    return (
      <Shell>
        <div className="max-w-3xl mx-auto px-5 md:px-8 pt-10 flex justify-center">
          <Loader2 className="w-5 h-5 text-brand animate-spin" strokeWidth={1.75} />
        </div>
      </Shell>
    );
  }

  return (
    <Shell>
      <div
        data-testid={IDS.settings.root}
        className="max-w-3xl mx-auto px-5 md:px-8 pt-6 md:pt-8 animate-fade-in"
      >
        <header className="mb-6">
          <p className="eyebrow">Ajustes</p>
          <h1 className="mt-1.5 text-[26px] md:text-[30px] font-semibold text-zinc-900 tracking-tight">
            Personalize seu copiloto
          </h1>
          <p className="mt-2 text-[14px] text-zinc-500 max-w-xl">
            Suas preferências ajustam como as recomendações são priorizadas ao longo da semana.
          </p>
        </header>

        {/* Modes */}
        <section className="mf-card p-5 md:p-6 mb-5">
          <h3 className="text-[16px] font-semibold text-zinc-900 tracking-tight">Modo atual</h3>
          <p className="mt-1 text-[13px] text-zinc-500">
            O modo muda como as ações são priorizadas ao longo do dia.
          </p>
          <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-2.5">
            {MODES.map((m) => {
              const Icon = m.icon;
              const active = profile?.mode === m.key;
              return (
                <button
                  key={m.key}
                  data-testid={IDS.settings.mode(m.key)}
                  onClick={() => setMode(m.key)}
                  disabled={saving}
                  className={`text-left rounded-xl p-4 transition-colors hairline ${
                    active ? '' : 'hover:bg-zinc-50'
                  }`}
                  style={active
                    ? { background: 'var(--mf-brand-soft)', borderColor: 'var(--mf-brand)' }
                    : { background: 'var(--mf-canvas)' }}
                >
                  <div className="flex items-center gap-2">
                    <span
                      className="w-8 h-8 rounded-lg flex items-center justify-center"
                      style={active
                        ? { background: 'var(--mf-brand)', color: '#FFF' }
                        : { background: 'var(--mf-surface)', color: 'var(--mf-ink-2)' }}
                    >
                      <Icon strokeWidth={1.75} className="w-4 h-4" />
                    </span>
                    <span className={`text-[14px] font-semibold ${active ? 'text-brand' : 'text-zinc-900'}`}>
                      {m.label}
                    </span>
                  </div>
                  <p className="mt-2.5 text-[12.5px] text-zinc-600 leading-relaxed">{m.desc}</p>
                </button>
              );
            })}
          </div>
        </section>

        {/* Study tool preference */}
        <section className="mf-card p-5 md:p-6 mb-6">
          <div className="flex items-center gap-2 mb-1">
            <BookOpen strokeWidth={1.75} className="w-4 h-4 text-brand" />
            <h3 className="text-[16px] font-semibold text-zinc-900 tracking-tight">Ferramenta de estudo</h3>
          </div>
          <p className="text-[13px] text-zinc-500 mb-4">
            O copiloto usa essa informação para escrever ações que combinam com seu jeito de estudar.
          </p>
          <div className="flex flex-wrap gap-2">
            {STUDY_TOOLS.map((t) => {
              const active = profile?.study_tool === t.key;
              return (
                <button
                  key={t.key}
                  data-testid={IDS.settings.studyTool(t.key)}
                  onClick={() => setStudyTool(t.key)}
                  disabled={saving}
                  className={`rounded-full px-4 py-2 text-[13px] font-medium transition-colors hairline ${
                    active ? 'text-white' : 'text-zinc-700 hover:bg-zinc-50'
                  }`}
                  style={active
                    ? { background: 'var(--mf-brand)', borderColor: 'var(--mf-brand-hov)' }
                    : { background: 'var(--mf-canvas)' }}
                >
                  {t.label}
                </button>
              );
            })}
          </div>
        </section>

        {/* Notificações personalizadas */}
        <section className="mf-card p-5 md:p-6 mb-5">
          <div className="flex items-center gap-2 mb-1">
            <Bell strokeWidth={1.75} className="w-4 h-4 text-brand" />
            <h3 className="text-[16px] font-semibold text-zinc-900 tracking-tight">Notificações</h3>
          </div>
          <p className="text-[13px] text-zinc-500 mb-4">
            Escolha como você prefere receber lembretes de check-in, agenda e priorização.
          </p>
          <div className="flex flex-wrap gap-2">
            {[
              { key: 'push', label: 'Notificações push' },
              { key: 'whatsapp', label: 'WhatsApp' },
              { key: 'email', label: 'E-mail' },
              { key: 'nenhum', label: 'Sem notificações' },
            ].map((c) => {
              const active = (profile?.notify_channel || 'push') === c.key;
              return (
                <button
                  key={c.key}
                  data-testid={`notify-${c.key}`}
                  onClick={() => setNotifyChannel(c.key)}
                  disabled={saving}
                  className={`rounded-full px-4 py-2 text-[13px] font-medium transition-colors hairline ${
                    active ? 'text-white' : 'text-zinc-700 hover:bg-zinc-50'
                  }`}
                  style={active
                    ? { background: 'var(--mf-brand)', borderColor: 'var(--mf-brand-hov)' }
                    : { background: 'var(--mf-canvas)' }}
                >
                  {c.label}
                </button>
              );
            })}
          </div>

          {/* Lembretes de autocuidado */}
          <div className="mt-5 pt-5 hairline-t">
            <p className="text-[13px] font-semibold text-zinc-900 mb-1">Lembretes de autocuidado</p>
            <p className="text-[12.5px] text-zinc-500 mb-3">
              Micro-alertas suaves durante o dia. Podem desligar quando quiser.
            </p>
            {[
              { key: 'remind_water', label: 'Beber água', desc: 'A cada ~3h, entre acordar e 22h.' },
              { key: 'remind_stretch', label: 'Alongar', desc: '10h, 14h e 17h — pausa de 2 min.' },
            ].map(({ key, label, desc }) => (
              <label
                key={key}
                data-testid={`selfcare-${key}`}
                className="flex items-center justify-between py-2 cursor-pointer"
              >
                <div>
                  <p className="text-[13.5px] font-medium text-zinc-900">{label}</p>
                  <p className="text-[12px] text-zinc-500">{desc}</p>
                </div>
                <input
                  type="checkbox"
                  checked={!!profile?.[key]}
                  onChange={async (e) => {
                    setSaving(true);
                    try {
                      const { data } = await api.patch('/profile', { [key]: e.target.checked });
                      setProfile(data.profile);
                    } finally { setSaving(false); }
                  }}
                  className="w-4 h-4 accent-current text-brand"
                />
              </label>
            ))}
          </div>
        </section>

        {/* Tema */}
        <section className="mf-card p-5 md:p-6 mb-6">
          <div className="flex items-center gap-2 mb-1">
            {theme === 'dark' ? <Moon strokeWidth={1.75} className="w-4 h-4 text-brand" /> : <Sun strokeWidth={1.75} className="w-4 h-4 text-brand" />}
            <h3 className="text-[16px] font-semibold text-zinc-900 tracking-tight">Tema</h3>
          </div>
          <p className="text-[13px] text-zinc-500 mb-4">
            Alterne entre claro e escuro para reduzir a fadiga ocular.
          </p>
          <div className="flex flex-wrap gap-2">
            {['light', 'dark'].map((t) => {
              const active = theme === t;
              const label = t === 'light' ? 'Claro' : 'Escuro';
              return (
                <button
                  key={t}
                  data-testid={`theme-${t}`}
                  onClick={() => setDarkMode(t === 'dark')}
                  className={`rounded-full px-4 py-2 text-[13px] font-medium transition-colors hairline ${
                    active ? 'text-white' : 'text-zinc-700 hover:bg-zinc-50'
                  }`}
                  style={active
                    ? { background: 'var(--mf-brand)', borderColor: 'var(--mf-brand-hov)' }
                    : { background: 'var(--mf-canvas)' }}
                >
                  {label}
                </button>
              );
            })}
          </div>
        </section>

        {/* Acessibilidade — Neurodivergência Nível 2 */}
        <section className="mf-card p-5 md:p-6 mb-5">
          <div className="flex items-center gap-2 mb-1">
            <Sparkles strokeWidth={1.75} className="w-4 h-4 text-brand" />
            <h3 className="text-[16px] font-semibold text-zinc-900 tracking-tight">Acessibilidade</h3>
          </div>
          <p className="text-[13px] text-zinc-500 mb-4">
            Ajustes pensados para diferentes formas de atenção e leitura. Aplicados no aparelho e salvos no perfil.
          </p>

          {/* Font size */}
          <div className="mb-4">
            <p className="text-[12.5px] font-medium text-zinc-700 mb-2 flex items-center gap-1.5">
              <Type className="w-3.5 h-3.5" /> Tamanho do texto
            </p>
            <div className="flex flex-wrap gap-2">
              {[
                { key: 'sm', label: 'Pequeno' },
                { key: 'md', label: 'Padrão' },
                { key: 'lg', label: 'Grande' },
                { key: 'xl', label: 'Extra grande' },
              ].map((f) => {
                const active = (a11y.font_size || 'md') === f.key;
                return (
                  <button
                    key={f.key}
                    data-testid={`a11y-font-${f.key}`}
                    onClick={() => patchA11y({ font_size: f.key })}
                    className={`rounded-full px-4 py-2 text-[13px] font-medium transition-colors hairline ${
                      active ? 'text-white' : 'text-zinc-700 hover:bg-zinc-50'
                    }`}
                    style={active
                      ? { background: 'var(--mf-brand)', borderColor: 'var(--mf-brand-hov)' }
                      : { background: 'var(--mf-canvas)' }}
                  >{f.label}</button>
                );
              })}
            </div>
          </div>

          {/* Toggles */}
          {[
            { key: 'high_contrast', label: 'Alto contraste', desc: 'Reforça bordas e cor da fonte para leitura difícil.', Icon: Contrast },
            { key: 'simplified_ui', label: 'Interface simplificada', desc: 'Esconde animações e cards secundários para reduzir estímulos.', Icon: EyeOff },
            { key: 'dyslexia_font', label: 'Fonte para dislexia', desc: 'Aplica família de fonte mais legível para leitura contínua.', Icon: Type },
            { key: 'reduce_motion', label: 'Reduzir movimento', desc: 'Desativa transições e animações do sistema.', Icon: Sparkles },
          ].map(({ key, label, desc, Icon }) => {
            const active = !!a11y[key];
            return (
              <label
                key={key}
                data-testid={`a11y-toggle-${key}`}
                className="flex items-start gap-3 py-2.5 cursor-pointer"
              >
                <Icon className="w-4 h-4 mt-0.5 text-zinc-500" strokeWidth={1.75} />
                <div className="flex-1">
                  <p className="text-[13.5px] font-medium text-zinc-900">{label}</p>
                  <p className="text-[12.5px] text-zinc-500">{desc}</p>
                </div>
                <input
                  type="checkbox"
                  checked={active}
                  onChange={(e) => patchA11y({ [key]: e.target.checked })}
                  className="mt-1 w-4 h-4 accent-current text-brand"
                />
              </label>
            );
          })}
        </section>

        {/* Comunidade — anonimato */}
        <section className="mf-card p-5 md:p-6 mb-6">
          <div className="flex items-center gap-2 mb-1">
            <UserRoundX strokeWidth={1.75} className="w-4 h-4 text-brand" />
            <h3 className="text-[16px] font-semibold text-zinc-900 tracking-tight">Comunidade</h3>
          </div>
          <p className="text-[13px] text-zinc-500 mb-4">
            Quando ativo, seus posts e comentários aparecem como <span className="font-medium">Estudante anônimo</span>.
          </p>
          <label className="flex items-center justify-between cursor-pointer" data-testid="anon-community-toggle">
            <span className="text-[13.5px] font-medium text-zinc-900">Publicar como anônimo</span>
            <input
              type="checkbox"
              checked={!!profile?.anonymous_community}
              onChange={(e) => toggleAnonymous(e.target.checked)}
              className="w-4 h-4 accent-current text-brand"
            />
          </label>
        </section>

        <p className="text-center text-[11px] text-zinc-400 pb-6 tracking-wider uppercase font-medium">
          Seus dados ficam seguros e anônimos · LGPD
        </p>
      </div>
    </Shell>
  );
};

export default Settings;
