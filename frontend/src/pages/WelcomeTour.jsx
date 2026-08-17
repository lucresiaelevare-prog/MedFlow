import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowRight, CheckCircle2, Sparkles, Compass } from 'lucide-react';
import api from '@/lib/api';
import Shell from '@/components/Shell';

/**
 * Tour da nova experiência — 3 telas (era 4).
 * Fusão de "A nova home" + "Nada foi perdido" numa única tela.
 * Última tela abre com uma observação REAL do usuário (aha moment).
 */
const WelcomeTour = () => {
  const [step, setStep] = useState(0);
  const [saving, setSaving] = useState(false);
  const [preview, setPreview] = useState(null); // { mode, text, stats }
  const navigate = useNavigate();

  useEffect(() => {
    let mounted = true;
    api.get('/experience/tour-preview')
      .then((r) => { if (mounted) setPreview(r.data); })
      .catch(() => { if (mounted) setPreview({ mode: 'learning', text: 'Ainda estou aprendendo como você estuda.', stats: {} }); });
    return () => { mounted = false; };
  }, []);

  const commit = async (home_layout) => {
    setSaving(true);
    try {
      await api.post('/experience/tour-complete', { home_layout });
      navigate(home_layout === 'smart' ? '/hoje' : '/dashboard', { replace: true });
    } finally {
      setSaving(false);
    }
  };

  const steps = [
    {
      icon: <Sparkles strokeWidth={1.5} className="w-6 h-6" style={{ color: 'var(--mf-brand)' }} />,
      eyebrow: 'novidade',
      title: 'Bem-vindo ao novo MedFlow.',
      body: 'Reorganizamos tudo. Agora o aplicativo cresce junto com você, em vez de despejar tudo na primeira tela.',
    },
    {
      icon: <Compass strokeWidth={1.5} className="w-6 h-6" style={{ color: 'var(--mf-brand)' }} />,
      eyebrow: 'a nova home',
      title: 'Um passo por dia. Nada foi perdido.',
      body: 'A Home Inteligente mostra apenas o próximo passo — o mais importante para hoje. Todo o resto (histórico, análises, pomodoro, agenda, hábitos, comunidade) continua aqui, a um clique.',
    },
    {
      icon: <CheckCircle2 strokeWidth={1.5} className="w-6 h-6" style={{ color: 'var(--mf-brand)' }} />,
      eyebrow: 'sua escolha',
      title: 'Como você quer começar?',
      body: 'Você pode trocar essa preferência a qualquer momento nas Configurações.',
    },
  ];

  const s = steps[step];
  const isLast = step === steps.length - 1;

  // Chip de dados reais no último passo — só aparece se houver stats significativos
  const st = preview?.stats || {};
  const chips = [];
  if (st.pomodoros_completed >= 1) chips.push(`${st.pomodoros_completed} sessão${st.pomodoros_completed > 1 ? 'ões' : ''} de foco`);
  if (st.checkins_total >= 1) chips.push(`${st.checkins_total} check-in${st.checkins_total > 1 ? 's' : ''}`);
  if (st.avg_mood != null) chips.push(`humor médio ${String(st.avg_mood).replace('.', ',')}`);

  return (
    <Shell>
      <div
        data-testid="welcome-tour-root"
        className="flex items-center justify-center bg-canvas px-5 py-12 md:py-20 min-h-[calc(100vh-8rem)]"
      >
      <div className="w-full max-w-lg animate-fade-in">
        {/* Dots */}
        <div className="flex items-center justify-center gap-1.5 mb-8">
          {steps.map((_, i) => (
            <span
              key={i}
              className="h-1 rounded-full transition-all duration-300"
              style={{
                width: i === step ? 22 : 8,
                background: i === step ? 'var(--mf-brand)' : 'var(--mf-hair)',
              }}
            />
          ))}
        </div>

        <div data-testid={`welcome-tour-step-${step}`} className="mf-card p-8 md:p-10 text-left">
          <div
            className="w-12 h-12 rounded-xl flex items-center justify-center mb-6"
            style={{ background: 'var(--mf-brand-soft, #FFF7ED)' }}
          >
            {s.icon}
          </div>
          <p className="eyebrow" style={{ color: 'var(--mf-brand)' }}>{s.eyebrow}</p>
          <h1 className="mt-2 text-[24px] md:text-[28px] font-semibold text-zinc-900 tracking-tight leading-tight">
            {s.title}
          </h1>
          <p className="mt-4 text-[14.5px] text-zinc-500 leading-relaxed">{s.body}</p>

          {/* Observação real no último passo — aha moment */}
          {isLast && preview && (
            <div
              data-testid="welcome-tour-observation"
              className="mt-6 rounded-xl p-4 hairline"
              style={{ background: 'var(--mf-canvas-soft, #FAFAF9)' }}
            >
              <p className="text-[11px] uppercase tracking-wider text-zinc-400 font-medium">
                O que já percebi de você
              </p>
              <p
                data-testid="welcome-tour-observation-text"
                className={`mt-1.5 text-[14px] leading-relaxed ${
                  preview.mode === 'observed' ? 'text-zinc-800' : 'text-zinc-500'
                }`}
              >
                {preview.text}
              </p>
              {chips.length > 0 && (
                <div className="mt-3 flex flex-wrap gap-1.5">
                  {chips.map((c, i) => (
                    <span
                      key={i}
                      data-testid={`welcome-tour-chip-${i}`}
                      className="pill text-[11px]"
                    >
                      {c}
                    </span>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* CTA — container estável, só conteúdo varia por passo.
              Ver /app/docs/frontend-rules.md #1 (não trocar elemento-raiz). */}
          <div className="mt-8" data-mode={isLast ? 'choose' : 'progress'}>
            {!isLast ? (
              <div className="flex items-center justify-between">
                <button
                  data-testid="welcome-tour-skip"
                  onClick={() => commit('control_center')}
                  className="text-[13px] text-zinc-500 hover:text-zinc-800 transition-colors"
                >
                  <span>Pular</span>
                </button>
                <button
                  data-testid="welcome-tour-next"
                  onClick={() => setStep((s) => Math.min(s + 1, steps.length - 1))}
                  className="btn-primary rounded-full px-5 py-2.5 text-[14px] inline-flex items-center gap-2"
                >
                  <span>Próximo</span>
                  <ArrowRight strokeWidth={2} className="w-4 h-4" />
                </button>
              </div>
            ) : (
              <div className="grid gap-3">
                <button
                  data-testid="welcome-tour-choose-smart"
                  disabled={saving}
                  onClick={() => commit('smart')}
                  className="btn-primary rounded-xl px-5 py-4 text-[14.5px] inline-flex items-center justify-between w-full disabled:opacity-60"
                >
                  <span className="text-left">
                    <span className="block font-semibold">Usar Home Inteligente</span>
                    <span className="block text-[12.5px] opacity-80 mt-0.5">Um passo por dia</span>
                  </span>
                  <ArrowRight strokeWidth={2} className="w-4 h-4 shrink-0" />
                </button>
                <button
                  data-testid="welcome-tour-choose-control"
                  disabled={saving}
                  onClick={() => commit('control_center')}
                  className="rounded-xl px-5 py-4 text-[14.5px] w-full text-left hairline hover:bg-zinc-50 transition-colors disabled:opacity-60"
                >
                  <span className="block font-semibold text-zinc-900">Continuar com Painel Completo</span>
                  <span className="block text-[12.5px] text-zinc-500 mt-0.5">
                    Tudo como estava antes
                  </span>
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
      </div>
    </Shell>
  );
};

export default WelcomeTour;
