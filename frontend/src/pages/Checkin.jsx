import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Loader2, ArrowLeft, ArrowRight } from 'lucide-react';
import Shell from '@/components/Shell';
import MentalHealthAlertOverlay from '@/components/MentalHealthAlertOverlay';
import api from '@/lib/api';
import IDS from '@/constants/testIds';

const STEPS = ['welcome', 'sleep', 'energy', 'mood', 'stress', 'exam', 'oncall', 'commitments', 'submit'];

const SCALE_LABELS_ENERGY = ['exausto', 'baixo', 'ok', 'bom', 'ótimo'];
const SCALE_LABELS_MOOD = ['muito baixo', 'baixo', 'neutro', 'bom', 'ótimo'];
const SCALE_LABELS_STRESS = ['calmo', 'tranquilo', 'moderado', 'tenso', 'muito tenso'];

const Bubble = ({ from = 'bot', children }) => (
  <div className={`flex ${from === 'bot' ? 'justify-start' : 'justify-end'} animate-fade-in`}>
    <div
      className={
        from === 'bot'
          ? 'rounded-2xl rounded-tl-md px-4 py-3 max-w-[85%] text-[14px] text-zinc-800'
          : 'rounded-2xl rounded-tr-md px-4 py-3 max-w-[85%] text-[14px] text-white'
      }
      style={{
        background: from === 'bot' ? 'var(--mf-surface-2)' : 'var(--mf-brand)',
      }}
    >
      {children}
    </div>
  </div>
);

const Checkin = () => {
  const navigate = useNavigate();
  const [step, setStep] = useState(0);
  const [state, setState] = useState({
    sleep_hours: 7,
    energy: 3,
    mood: 3,
    stress: 3,
    upcoming_exam: false,
    exam_name: '',
    exam_date: '',
    on_call_today: false,
    commitments: '',
    free_text: '',
  });
  const [submitting, setSubmitting] = useState(false);
  const [mhAlert, setMhAlert] = useState(null);
  const scrollRef = useRef(null);

  const stepName = STEPS[step];

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
  }, [step]);

  const set = (patch) => setState((s) => ({ ...s, ...patch }));
  const next = () => setStep((s) => Math.min(s + 1, STEPS.length - 1));
  const back = () => setStep((s) => Math.max(s - 1, 0));

  const submit = async () => {
    setSubmitting(true);
    try {
      const { data } = await api.post('/checkin', state);
      if (data?.mental_health_alert) {
        setMhAlert(data.mental_health_alert);
      } else {
        navigate('/dashboard', { replace: true });
      }
    } catch (e) {
      console.error(e);
      alert('Não consegui salvar. Tente novamente.');
    } finally {
      setSubmitting(false);
    }
  };

  const messages = useMemo(() => {
    const m = [];
    m.push(<Bubble key="w">Oi! Vou te fazer 6 perguntas rápidas. Menos de 30 segundos.</Bubble>);
    if (step >= 1) m.push(<Bubble key="q-sleep">Quantas horas você dormiu na última noite?</Bubble>);
    if (step >= 2) m.push(<Bubble key="a-sleep" from="me">{state.sleep_hours}h de sono</Bubble>);
    if (step >= 2) m.push(<Bubble key="q-energy">E a sua energia agora?</Bubble>);
    if (step >= 3) m.push(<Bubble key="a-energy" from="me">Energia: {SCALE_LABELS_ENERGY[state.energy - 1]}</Bubble>);
    if (step >= 3) m.push(<Bubble key="q-mood">Como está o humor?</Bubble>);
    if (step >= 4) m.push(<Bubble key="a-mood" from="me">Humor: {SCALE_LABELS_MOOD[state.mood - 1]}</Bubble>);
    if (step >= 4) m.push(<Bubble key="q-stress">E o nível de estresse?</Bubble>);
    if (step >= 5) m.push(<Bubble key="a-stress" from="me">Estresse: {SCALE_LABELS_STRESS[state.stress - 1]}</Bubble>);
    if (step >= 5) m.push(<Bubble key="q-exam">Tem prova nos próximos dias?</Bubble>);
    if (step >= 6) m.push(<Bubble key="a-exam" from="me">{state.upcoming_exam ? `Sim, ${state.exam_name || 'sem nome'}${state.exam_date ? ' em ' + state.exam_date : ''}` : 'Sem prova por agora'}</Bubble>);
    if (step >= 6) m.push(<Bubble key="q-oncall">Você está de plantão hoje?</Bubble>);
    if (step >= 7) m.push(<Bubble key="a-oncall" from="me">{state.on_call_today ? 'Sim, plantão' : 'Não, hoje não'}</Bubble>);
    if (step >= 7) m.push(<Bubble key="q-c">Algum compromisso importante hoje? (opcional)</Bubble>);
    if (step >= 8) m.push(<Bubble key="a-c" from="me">{state.commitments || 'Nada específico'}</Bubble>);
    if (step >= 8) m.push(<Bubble key="q-done">Perfeito. Já vou preparar uma ação boa para você agora.</Bubble>);
    return m;
  }, [step, state]);

  return (
    <Shell>
      <div data-testid={IDS.checkin.root} className="max-w-2xl mx-auto px-5 md:px-6 pt-4 md:pt-8">
        {mhAlert && (
          <MentalHealthAlertOverlay
            alert={mhAlert}
            onDismiss={() => { setMhAlert(null); navigate('/dashboard', { replace: true }); }}
          />
        )}
        <button onClick={() => navigate(-1)} className="btn-ghost inline-flex items-center gap-1.5 mb-4">
          <ArrowLeft strokeWidth={1.75} className="w-4 h-4" /> Voltar
        </button>

        <div className="mb-4">
          <p className="eyebrow">Check-in</p>
          <h1 className="mt-1.5 text-[22px] md:text-[26px] font-semibold text-zinc-900 tracking-tight">
            Como está seu dia?
          </h1>
        </div>

        <div ref={scrollRef} className="space-y-2.5 pb-6">
          {messages}
        </div>

        {/* Answer surface */}
        <div className="sticky bottom-24 md:bottom-6 pt-2">
          <div className="mf-card p-5">
            {stepName === 'welcome' && (
              <button
                data-testid={IDS.checkin.next}
                onClick={next}
                className="btn-primary w-full justify-center"
              >
                Começar
                <ArrowRight strokeWidth={1.75} className="w-4 h-4" />
              </button>
            )}

            {stepName === 'sleep' && (
              <div className="space-y-4">
                <div className="flex items-baseline justify-between">
                  <span className="eyebrow">Sono</span>
                  <span className="mono text-[28px] font-semibold text-zinc-900 tabular">{state.sleep_hours}h</span>
                </div>
                <input
                  data-testid={IDS.checkin.sleepInput}
                  type="range" min="0" max="14" step="0.5"
                  value={state.sleep_hours}
                  onChange={(e) => set({ sleep_hours: parseFloat(e.target.value) })}
                  className="w-full accent-brand"
                />
                <button data-testid={IDS.checkin.next} onClick={next} className="btn-primary w-full justify-center">
                  Continuar
                  <ArrowRight strokeWidth={1.75} className="w-4 h-4" />
                </button>
              </div>
            )}

            {['energy', 'mood', 'stress'].includes(stepName) && (
              <ScaleQuestion
                stepName={stepName}
                labels={stepName === 'energy' ? SCALE_LABELS_ENERGY : stepName === 'mood' ? SCALE_LABELS_MOOD : SCALE_LABELS_STRESS}
                value={state[stepName]}
                onChange={(v) => set({ [stepName]: v })}
                onNext={next}
              />
            )}

            {stepName === 'exam' && (
              <div className="space-y-4">
                <p className="eyebrow">Prova próxima</p>
                <div className="grid grid-cols-2 gap-2">
                  <button data-testid={IDS.checkin.upcomingNo} onClick={() => { set({ upcoming_exam: false, exam_name: '', exam_date: '' }); next(); }} className={!state.upcoming_exam ? 'btn-primary justify-center' : 'btn-secondary justify-center'}>Sem prova</button>
                  <button data-testid={IDS.checkin.upcomingYes} onClick={() => set({ upcoming_exam: true })} className={state.upcoming_exam ? 'btn-primary btn-care justify-center' : 'btn-secondary justify-center'} style={state.upcoming_exam ? { background: 'var(--mf-care)', borderColor: '#B85539' } : {}}>Tem prova</button>
                </div>
                {state.upcoming_exam && (
                  <div className="space-y-3 animate-fade-in">
                    <input data-testid={IDS.checkin.examName} value={state.exam_name} onChange={(e) => set({ exam_name: e.target.value })} placeholder="Qual matéria ou prova?" className="w-full bg-white hairline rounded-lg px-3.5 py-2.5 text-[14px] text-zinc-900 placeholder-zinc-400 focus:outline-none focus:ring-2 focus:ring-brand/30" />
                    <input data-testid={IDS.checkin.examDate} type="date" value={state.exam_date} onChange={(e) => set({ exam_date: e.target.value })} className="w-full bg-white hairline rounded-lg px-3.5 py-2.5 text-[14px] text-zinc-900 focus:outline-none focus:ring-2 focus:ring-brand/30" />
                    <button data-testid={IDS.checkin.next} onClick={next} className="btn-primary w-full justify-center">
                      Continuar
                      <ArrowRight strokeWidth={1.75} className="w-4 h-4" />
                    </button>
                  </div>
                )}
              </div>
            )}

            {stepName === 'oncall' && (
              <div className="space-y-3">
                <p className="eyebrow">Plantão hoje?</p>
                <div className="grid grid-cols-2 gap-2">
                  <button data-testid={IDS.checkin.onCallNo} onClick={() => { set({ on_call_today: false }); next(); }} className="btn-secondary justify-center">Não</button>
                  <button data-testid={IDS.checkin.onCallYes} onClick={() => { set({ on_call_today: true }); next(); }} className="btn-primary btn-care justify-center" style={{ background: 'var(--mf-care)', borderColor: '#B85539' }}>Sim</button>
                </div>
              </div>
            )}

            {stepName === 'commitments' && (
              <div className="space-y-3">
                <p className="eyebrow">Compromissos (opcional)</p>
                <textarea data-testid={IDS.checkin.commitments} value={state.commitments} onChange={(e) => set({ commitments: e.target.value })} placeholder="Ex.: aula de anatomia às 14h, revisão em grupo à noite…" className="w-full bg-white hairline rounded-lg px-3.5 py-2.5 text-[14px] text-zinc-900 placeholder-zinc-400 focus:outline-none focus:ring-2 focus:ring-brand/30 min-h-[90px]" />
                <button data-testid={IDS.checkin.next} onClick={next} className="btn-primary w-full justify-center">
                  Continuar
                  <ArrowRight strokeWidth={1.75} className="w-4 h-4" />
                </button>
              </div>
            )}

            {stepName === 'submit' && (
              <div className="space-y-3">
                <p className="eyebrow">Algo mais?</p>
                <textarea data-testid={IDS.checkin.freeText} value={state.free_text} onChange={(e) => set({ free_text: e.target.value })} placeholder="Uma nota curta (opcional)" className="w-full bg-white hairline rounded-lg px-3.5 py-2.5 text-[14px] text-zinc-900 placeholder-zinc-400 focus:outline-none focus:ring-2 focus:ring-brand/30 min-h-[70px]" />
                <button
                  data-testid={IDS.checkin.submit}
                  onClick={submit}
                  disabled={submitting}
                  className="btn-primary w-full justify-center disabled:opacity-60"
                >
                  {submitting && <Loader2 className="w-4 h-4 animate-spin" strokeWidth={1.75} />}
                  {submitting ? 'Preparando sua ação…' : 'Receber minha ação'}
                </button>
              </div>
            )}

            {step > 0 && stepName !== 'submit' && (
              <button data-testid={IDS.checkin.back} onClick={back} className="mt-3 w-full text-zinc-500 text-[12px] hover:text-zinc-800 font-medium">
                ← Voltar
              </button>
            )}
          </div>
        </div>
      </div>
    </Shell>
  );
};

const ScaleQuestion = ({ stepName, labels, value, onChange, onNext }) => {
  const testId = stepName === 'energy' ? IDS.checkin.energy : stepName === 'mood' ? IDS.checkin.mood : IDS.checkin.stress;
  const title = stepName === 'energy' ? 'Energia' : stepName === 'mood' ? 'Humor' : 'Estresse';
  return (
    <div className="space-y-4">
      <div className="flex items-baseline justify-between">
        <span className="eyebrow">{title}</span>
        <span className="text-[13px] text-zinc-500">{labels[value - 1]}</span>
      </div>
      <div className="grid grid-cols-5 gap-1.5">
        {[1, 2, 3, 4, 5].map((v) => (
          <button
            key={v}
            data-testid={testId(v)}
            onClick={() => onChange(v)}
            className={`py-3 rounded-lg font-semibold text-[14px] tabular transition-colors ${
              value === v ? 'text-white' : 'text-zinc-700 hover:bg-zinc-100'
            }`}
            style={value === v
              ? { background: 'var(--mf-brand)', border: '1px solid var(--mf-brand-hov)' }
              : { background: 'var(--mf-surface)', border: '1px solid var(--mf-hair)' }}
          >
            {v}
          </button>
        ))}
      </div>
      <button data-testid={IDS.checkin.next} onClick={onNext} className="btn-primary w-full justify-center">
        Continuar
        <ArrowRight strokeWidth={1.75} className="w-4 h-4" />
      </button>
    </div>
  );
};

export default Checkin;
