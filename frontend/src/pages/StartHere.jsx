import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowRight } from 'lucide-react';
import api from '@/lib/api';
import Shell from '@/components/Shell';

/**
 * Minimal onboarding — 3 telas.
 * Período · Faculdade · Tempo típico de estudo.
 * Rodapé enxuto: "É só isso." (sem promessa temporal ansiosa).
 */
const StartHere = () => {
  const [step, setStep] = useState(0);
  const [period, setPeriod] = useState(null);
  const [faculty, setFaculty] = useState('');
  const [studyMin, setStudyMin] = useState(null);
  const [saving, setSaving] = useState(false);
  const navigate = useNavigate();

  const finish = async () => {
    setSaving(true);
    try {
      await api.post('/experience/onboarding-minimal', {
        period_number: period,
        faculty: faculty.trim(),
        typical_study_min: studyMin,
      });
      navigate('/hoje', { replace: true });
    } finally {
      setSaving(false);
    }
  };

  return (
    <Shell>
      <div
        data-testid="start-here-root"
        className="flex items-center justify-center bg-canvas px-5 py-12 md:py-20 min-h-[calc(100vh-8rem)]"
      >
      <div className="w-full max-w-md animate-fade-in">
        {/* progress dots */}
        <div className="flex items-center justify-center gap-1.5 mb-8">
          {[0, 1, 2].map((i) => (
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

        <div className="mf-card p-8 md:p-10">
          {step === 0 && (
            <div data-testid="start-here-step-period" className="animate-fade-in">
              <p className="eyebrow" style={{ color: 'var(--mf-brand)' }}>1 de 3</p>
              <h2 className="mt-2 text-[22px] md:text-[24px] font-semibold text-zinc-900 tracking-tight">
                Em qual período você está?
              </h2>
              <div className="mt-6 grid grid-cols-3 gap-2">
                {Array.from({ length: 12 }, (_, i) => i + 1).map((p) => (
                  <button
                    key={p}
                    data-testid={`start-here-period-${p}`}
                    onClick={() => setPeriod(p)}
                    className={`h-14 rounded-xl text-[15px] font-semibold transition-all hairline ${
                      period === p ? 'text-white' : 'text-zinc-800 hover:bg-zinc-50'
                    }`}
                    style={{
                      background: period === p ? 'var(--mf-brand, #DC6B4C)' : 'transparent',
                    }}
                  >
                    {p}º
                  </button>
                ))}
              </div>
              <div className="mt-8 flex justify-end">
                <button
                  data-testid="start-here-next-1"
                  disabled={!period}
                  onClick={() => setStep(1)}
                  className="btn-primary rounded-full px-5 py-2.5 text-[14px] inline-flex items-center gap-2 disabled:opacity-40"
                >
                  Próximo <ArrowRight strokeWidth={2} className="w-4 h-4" />
                </button>
              </div>
            </div>
          )}

          {step === 1 && (
            <div data-testid="start-here-step-faculty" className="animate-fade-in">
              <p className="eyebrow" style={{ color: 'var(--mf-brand)' }}>2 de 3</p>
              <h2 className="mt-2 text-[22px] md:text-[24px] font-semibold text-zinc-900 tracking-tight">
                Qual faculdade?
              </h2>
              <input
                autoFocus
                data-testid="start-here-faculty-input"
                value={faculty}
                onChange={(e) => setFaculty(e.target.value)}
                placeholder="Ex.: FCMMG, FAMINAS-BH, UFMG…"
                maxLength={120}
                className="mt-5 w-full text-[16px] px-4 py-3 rounded-xl hairline bg-white focus:outline-none focus:ring-2 focus:ring-brand/30"
              />
              <p className="mt-2 text-[12px] text-zinc-400">Pode digitar como quiser — só serve pra personalizar.</p>
              <div className="mt-8 flex items-center justify-between">
                <button
                  data-testid="start-here-back-1"
                  onClick={() => setStep(0)}
                  className="text-[13px] text-zinc-500 hover:text-zinc-800"
                >
                  Voltar
                </button>
                <button
                  data-testid="start-here-next-2"
                  disabled={!faculty.trim()}
                  onClick={() => setStep(2)}
                  className="btn-primary rounded-full px-5 py-2.5 text-[14px] inline-flex items-center gap-2 disabled:opacity-40"
                >
                  Próximo <ArrowRight strokeWidth={2} className="w-4 h-4" />
                </button>
              </div>
            </div>
          )}

          {step === 2 && (
            <div data-testid="start-here-step-time" className="animate-fade-in">
              <p className="eyebrow" style={{ color: 'var(--mf-brand)' }}>3 de 3</p>
              <h2 className="mt-2 text-[22px] md:text-[24px] font-semibold text-zinc-900 tracking-tight">
                Quanto tempo você costuma conseguir estudar por sessão?
              </h2>
              <div className="mt-6 grid grid-cols-2 gap-2">
                {[
                  { v: 15, label: '15 min', hint: 'blocos curtos' },
                  { v: 30, label: '30 min', hint: 'padrão' },
                  { v: 60, label: '1 hora', hint: 'foco profundo' },
                  { v: 120, label: '2h+', hint: 'sessões longas' },
                ].map((o) => (
                  <button
                    key={o.v}
                    data-testid={`start-here-time-${o.v}`}
                    onClick={() => setStudyMin(o.v)}
                    className={`p-4 rounded-xl text-left transition-all hairline ${
                      studyMin === o.v ? 'text-white' : 'text-zinc-800 hover:bg-zinc-50'
                    }`}
                    style={{
                      background: studyMin === o.v ? 'var(--mf-brand, #DC6B4C)' : 'transparent',
                    }}
                  >
                    <p className="text-[16px] font-semibold">{o.label}</p>
                    <p className={`mt-1 text-[12px] ${studyMin === o.v ? 'text-white/80' : 'text-zinc-500'}`}>
                      {o.hint}
                    </p>
                  </button>
                ))}
              </div>
              <div className="mt-8 flex items-center justify-between">
                <button
                  data-testid="start-here-back-2"
                  onClick={() => setStep(1)}
                  className="text-[13px] text-zinc-500 hover:text-zinc-800"
                >
                  Voltar
                </button>
                <button
                  data-testid="start-here-finish"
                  disabled={!studyMin || saving}
                  onClick={finish}
                  className="btn-primary rounded-full px-5 py-2.5 text-[14px] inline-flex items-center gap-2 disabled:opacity-40"
                >
                  Pronto <ArrowRight strokeWidth={2} className="w-4 h-4" />
                </button>
              </div>
            </div>
          )}
        </div>

        <p className="mt-6 text-center text-[12px] text-zinc-400">
          É só isso.
        </p>
      </div>
      </div>
    </Shell>
  );
};

export default StartHere;
