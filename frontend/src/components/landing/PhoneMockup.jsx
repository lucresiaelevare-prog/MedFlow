import { CalendarDays, MoonStar, Sparkles, Zap } from 'lucide-react';

/**
 * PhoneMockup — painel diário na seção Sinais.
 * Apresenta sinais essenciais em uma composição compacta e moderna.
 */
export const PhoneMockup = () => {
  return (
    <div className="phone" data-testid="landing-phone-mockup">
      <div className="phone-screen">
        <div className="flex h-full w-full flex-col" style={{ padding: 16, paddingTop: 28 }}>
          <div className="flex items-center justify-between" data-testid="mockup-day-header">
            <p className="inst-readout" style={{ fontSize: 8 }}>
              <span>hoje · 07:15</span>
            </p>
            <span
              className="flex h-5 w-5 items-center justify-center rounded-md"
              style={{ background: 'var(--mf-brand-soft)', color: 'var(--mf-brand)' }}
            >
              <Sparkles aria-hidden="true" size={11} strokeWidth={2} />
            </span>
          </div>
          <p
            className="mt-3 font-semibold leading-[0.95] tracking-tight"
            data-testid="mockup-daily-title"
            style={{ fontSize: 21, letterSpacing: '-0.02em', color: 'var(--mf-inst-ink)' }}
          >
            <span>Um passo</span>
            <br />
            <span style={{ color: 'var(--mf-brand)' }}>por vez.</span>
          </p>

          <div className="mt-4 grid grid-cols-2 gap-2" data-testid="mockup-daily-stats">
            <div
              className="reasoning-step rounded-lg border p-2.5"
              data-testid="mockup-sleep-stat"
              style={{
                background: '#EEF2FF',
                borderColor: '#DDE5FF',
                animationDelay: '120ms',
              }}
            >
              <MoonStar aria-hidden="true" size={13} strokeWidth={2} style={{ color: '#4F46E5' }} />
              <p className="mt-2 text-[8px] font-medium uppercase tracking-wide text-slate-500">Sono</p>
              <p className="mt-0.5 text-[14px] font-semibold tracking-tight text-slate-900">5h48</p>
            </div>
            <div
              className="reasoning-step rounded-lg border p-2.5"
              data-testid="mockup-energy-stat"
              style={{
                background: '#FFF7E7',
                borderColor: '#F9DF9F',
                animationDelay: '220ms',
              }}
            >
              <Zap aria-hidden="true" size={13} strokeWidth={2} style={{ color: '#B45309' }} />
              <p className="mt-2 text-[8px] font-medium uppercase tracking-wide text-amber-700">Energia</p>
              <p className="mt-0.5 text-[14px] font-semibold tracking-tight text-amber-950">Baixa</p>
            </div>
          </div>

          <div
            className="reasoning-step mt-2.5 rounded-lg border p-3"
            data-testid="mockup-exam-stat"
            style={{
              background: 'var(--mf-inst-navy)',
              borderColor: 'rgba(255,255,255,0.12)',
              animationDelay: '320ms',
            }}
          >
            <div className="flex items-center justify-between">
              <span className="text-[8px] font-medium uppercase tracking-wide text-white/55">Próxima prova</span>
              <CalendarDays aria-hidden="true" size={13} strokeWidth={2} className="text-white/70" />
            </div>
            <p className="mt-1 text-[15px] font-semibold leading-tight tracking-tight text-white">Em 6 dias</p>
            <p className="mt-1 text-[9px] text-white/60">Priorize revisão curta hoje.</p>
          </div>
        </div>
      </div>
    </div>
  );
};
