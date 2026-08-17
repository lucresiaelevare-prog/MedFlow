import { useEffect, useMemo, useState } from 'react';
import { Bell, Sunrise, Calendar, Sparkles, ArrowRight, Loader2, X } from 'lucide-react';
import api from '@/lib/api';
import { enablePush, isPushSupported, getPermission, isPushPromptEnabled } from '@/lib/push';

const HOURS = [5, 6, 7, 8, 9, 10, 11];

const OnboardingWizard = ({ onDone }) => {
  const [step, setStep] = useState(0);
  const [wakeHour, setWakeHour] = useState(7);
  const [examLead, setExamLead] = useState(3);
  const [digest, setDigest] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [skipping, setSkipping] = useState(false);

  const tz = useMemo(
    () => Intl.DateTimeFormat().resolvedOptions().timeZone || 'America/Sao_Paulo',
    []
  );

  useEffect(() => {
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => { document.body.style.overflow = prev; };
  }, []);

  const skip = async () => {
    setSkipping(true);
    setError('');
    try {
      await api.post('/push/onboarding', {
        wake_hour: wakeHour,
        exam_alert_lead_days: examLead,
        digest_sunday: digest,
        tz,
      });
      await api.patch('/push/preferences', { notifications_enabled: false });
      onDone?.({ enabled: false });
    } catch (e) {
      setError('Não foi possível salvar suas preferências. Tente novamente.');
    } finally {
      setSkipping(false);
    }
  };

  const finish = async () => {
    setBusy(true);
    setError('');
    try {
      await api.post('/push/onboarding', {
        wake_hour: wakeHour,
        exam_alert_lead_days: examLead,
        digest_sunday: digest,
        tz,
      });
      if (isPushPromptEnabled() && isPushSupported() && getPermission() !== 'denied') {
        try {
          await enablePush();
        } catch (pushErr) {
          await api.patch('/push/preferences', { notifications_enabled: false });
          onDone?.({ enabled: false, reason: pushErr?.message });
          return;
        }
      }
      onDone?.({ enabled: isPushPromptEnabled() });
    } catch (e) {
      setError('Algo falhou ao salvar. Tente novamente em instantes.');
    } finally {
      setBusy(false);
    }
  };

  const next = () => setStep((s) => Math.min(s + 1, 2));
  const back = () => setStep((s) => Math.max(s - 1, 0));

  return (
    <div
      data-testid="onboarding-wizard"
      className="fixed inset-0 z-[100] flex items-center justify-center px-4 py-6 animate-fade-in"
      style={{ background: 'rgba(9, 9, 11, 0.55)', backdropFilter: 'blur(8px)' }}
    >
      <div className="w-full max-w-md mf-card overflow-hidden">
        {/* Header */}
        <div className="px-6 pt-6 pb-4 flex items-start gap-3">
          <span
            className="w-10 h-10 rounded-lg flex items-center justify-center shrink-0"
            style={{ background: 'var(--mf-brand-soft)', color: 'var(--mf-brand)' }}
          >
            <Sparkles strokeWidth={1.75} className="w-4 h-4" />
          </span>
          <div className="flex-1 min-w-0">
            <p className="eyebrow">3 perguntas rápidas</p>
            <h2 className="mt-1 text-[18px] font-semibold text-zinc-900 tracking-tight leading-tight">
              Deixe o copiloto no seu ritmo
            </h2>
            <p className="mt-1 text-[13px] text-zinc-500 leading-relaxed">
              Ajustamos os lembretes ao seu fuso e evitamos excessos. Você pode mudar tudo depois.
            </p>
          </div>
          <button
            data-testid="onboarding-close"
            onClick={skip}
            disabled={skipping || busy}
            aria-label="Pular"
            className="text-zinc-400 hover:text-zinc-700 p-1 -mr-2 -mt-1 shrink-0"
          >
            <X strokeWidth={1.75} className="w-5 h-5" />
          </button>
        </div>

        {/* Progress dots */}
        <div className="px-6 pb-3 flex items-center gap-1.5">
          {[0, 1, 2].map((i) => (
            <div
              key={i}
              className={`h-1 flex-1 rounded-full transition-colors ${
                i <= step ? 'bg-brand' : 'bg-zinc-200'
              }`}
            />
          ))}
        </div>

        {/* Steps */}
        <div className="px-6 pb-5 min-h-[220px]">
          {step === 0 && (
            <div data-testid="onboarding-step-wake" className="space-y-4 animate-fade-in">
              <div className="flex items-center gap-2 text-zinc-800">
                <Sunrise strokeWidth={1.75} className="w-4 h-4 text-brand" />
                <span className="text-[14px] font-semibold">Que horas você costuma acordar?</span>
              </div>
              <p className="text-[12.5px] text-zinc-500">
                O lembrete de check-in da manhã sai nesse horário, no seu fuso.
              </p>
              <div className="grid grid-cols-4 gap-2">
                {HOURS.map((h) => (
                  <button
                    key={h}
                    data-testid={`onboarding-wake-${h}`}
                    onClick={() => setWakeHour(h)}
                    className={`py-2.5 rounded-lg text-[14px] font-semibold hairline transition-colors ${
                      wakeHour === h ? 'text-white' : 'text-zinc-800 hover:bg-zinc-50'
                    }`}
                    style={wakeHour === h
                      ? { background: 'var(--mf-brand)', borderColor: 'var(--mf-brand-hov)' }
                      : { background: 'var(--mf-canvas)' }}
                  >
                    {h}h
                  </button>
                ))}
              </div>
              <p className="text-[11px] text-zinc-400">
                Fuso detectado: <span className="text-zinc-700 font-medium">{tz}</span>
              </p>
            </div>
          )}

          {step === 1 && (
            <div data-testid="onboarding-step-exam" className="space-y-4 animate-fade-in">
              <div className="flex items-center gap-2 text-zinc-800">
                <Calendar strokeWidth={1.75} className="w-4 h-4 text-brand" />
                <span className="text-[14px] font-semibold">Antecedência dos avisos de prova</span>
              </div>
              <p className="text-[12.5px] text-zinc-500">
                Você sempre recebe o aviso de 24 horas. Escolha se quer também um de 3 dias antes.
              </p>
              <div className="grid grid-cols-2 gap-2.5">
                <button
                  data-testid="onboarding-exam-3d"
                  onClick={() => setExamLead(3)}
                  className={`p-4 text-left rounded-xl hairline transition-colors ${
                    examLead === 3 ? '' : 'hover:bg-zinc-50'
                  }`}
                  style={examLead === 3
                    ? { background: 'var(--mf-brand-soft)', borderColor: 'var(--mf-brand)' }
                    : { background: 'var(--mf-canvas)' }}
                >
                  <div className={`text-[14.5px] font-semibold ${examLead === 3 ? 'text-brand' : 'text-zinc-900'}`}>3 dias antes</div>
                  <div className="mt-1 text-[12px] text-zinc-500">Dá tempo de ativar o modo Prova.</div>
                </button>
                <button
                  data-testid="onboarding-exam-1d"
                  onClick={() => setExamLead(1)}
                  className={`p-4 text-left rounded-xl hairline transition-colors ${
                    examLead === 1 ? '' : 'hover:bg-zinc-50'
                  }`}
                  style={examLead === 1
                    ? { background: 'var(--mf-brand-soft)', borderColor: 'var(--mf-brand)' }
                    : { background: 'var(--mf-canvas)' }}
                >
                  <div className={`text-[14.5px] font-semibold ${examLead === 1 ? 'text-brand' : 'text-zinc-900'}`}>Só na véspera</div>
                  <div className="mt-1 text-[12px] text-zinc-500">Um único aviso, na hora certa.</div>
                </button>
              </div>
            </div>
          )}

          {step === 2 && (
            <div data-testid="onboarding-step-digest" className="space-y-4 animate-fade-in">
              <div className="flex items-center gap-2 text-zinc-800">
                <Sparkles strokeWidth={1.75} className="w-4 h-4 text-brand" />
                <span className="text-[14px] font-semibold">Resumo semanal</span>
              </div>
              <p className="text-[12.5px] text-zinc-500">
                Um card curto no domingo, às 18h, com os padrões da sua semana.
              </p>
              <div className="grid grid-cols-2 gap-2.5">
                <button
                  data-testid="onboarding-digest-yes"
                  onClick={() => setDigest(true)}
                  className={`p-4 text-left rounded-xl hairline transition-colors ${
                    digest ? '' : 'hover:bg-zinc-50'
                  }`}
                  style={digest
                    ? { background: 'var(--mf-brand-soft)', borderColor: 'var(--mf-brand)' }
                    : { background: 'var(--mf-canvas)' }}
                >
                  <div className={`text-[14.5px] font-semibold ${digest ? 'text-brand' : 'text-zinc-900'}`}>Pode mandar</div>
                  <div className="mt-1 text-[12px] text-zinc-500">Leitura de 1 minuto, no domingo.</div>
                </button>
                <button
                  data-testid="onboarding-digest-no"
                  onClick={() => setDigest(false)}
                  className={`p-4 text-left rounded-xl hairline transition-colors ${
                    !digest ? '' : 'hover:bg-zinc-50'
                  }`}
                  style={!digest
                    ? { background: 'var(--mf-brand-soft)', borderColor: 'var(--mf-brand)' }
                    : { background: 'var(--mf-canvas)' }}
                >
                  <div className={`text-[14.5px] font-semibold ${!digest ? 'text-brand' : 'text-zinc-900'}`}>Prefiro não</div>
                  <div className="mt-1 text-[12px] text-zinc-500">Sem resumo semanal.</div>
                </button>
              </div>
              {isPushPromptEnabled() && isPushSupported() && (
                <div className="hairline-t pt-4 flex items-start gap-2 text-[12px] text-zinc-500">
                  <Bell strokeWidth={1.75} className="w-4 h-4 text-brand mt-0.5 shrink-0" />
                  <span>
                    Ao concluir, o navegador vai pedir permissão para enviar notificações. Você pode negar sem perder acesso ao painel.
                  </span>
                </div>
              )}
            </div>
          )}
        </div>

        {error && (
          <div className="px-6 pb-2 text-[12.5px] text-care">{error}</div>
        )}

        {/* Footer */}
        <div className="px-6 pb-6 pt-2 flex items-center justify-between gap-3">
          <button
            data-testid="onboarding-skip"
            onClick={skip}
            disabled={busy || skipping}
            className="btn-ghost"
          >
            {skipping ? 'Salvando…' : 'Pular por agora'}
          </button>
          <div className="flex items-center gap-2">
            {step > 0 && (
              <button
                data-testid="onboarding-back"
                onClick={back}
                disabled={busy || skipping}
                className="btn-ghost"
              >
                Voltar
              </button>
            )}
            {step < 2 ? (
              <button
                data-testid="onboarding-next"
                onClick={next}
                disabled={busy || skipping}
                className="btn-primary"
              >
                Próxima
                <ArrowRight strokeWidth={1.75} className="w-4 h-4" />
              </button>
            ) : (
              <button
                data-testid="onboarding-finish"
                onClick={finish}
                disabled={busy || skipping}
                className="btn-primary disabled:opacity-60"
              >
                {busy ? <Loader2 className="w-4 h-4 animate-spin" strokeWidth={1.75} /> : <Bell strokeWidth={1.75} className="w-4 h-4" />}
                Ativar copiloto
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default OnboardingWizard;
