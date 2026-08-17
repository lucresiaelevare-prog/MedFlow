import { useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  Loader2, GraduationCap, BookOpen, Target, Timer, Compass, ClipboardList,
  ArrowRight, ArrowLeft, CheckCircle2, XCircle, Sparkles, RefreshCw,
  ChevronRight, BarChart3, Zap, Clock, AlertCircle, Stethoscope,
  MessagesSquare, Brain, Calendar, Paperclip, Camera, Mic, Wand2,
  Play, TrendingUp, Battery, Send,
} from 'lucide-react';
import Shell from '@/components/Shell';
import api, { streamPost } from '@/lib/api';
import { useAuth } from '@/context/AuthContext';
import { saveCheckpoint } from '@/lib/resume';

/**
 * Meu Tutor — Centro de Aprendizagem Inteligente (P0.2.3).
 *
 * 5 modos de entrada + Mapa de Domínio pessoal. A IA deixa de ser "chat"
 * e vira mentor adaptativo. Cada slot do plano bate em /api/learning/request,
 * que reutiliza conteúdo existente quando possível (memória-antes-de-IA).
 */

// ─── Memória visível do Preceptor (localStorage) ──────────────
// Schema pensado desde já para migração ao backend (memória oficial do aluno).
// A troca do storage é mecânica — o formato do estado permanece.
//
// {
//   last_topic, last_subject, last_activity,
//   last_interaction (ISO),
//   study_minutes_today, study_minutes_today_date,
//   next_recommendation,
//   last_open_day, streak, days_started, updated_at
// }
const MENTOR_STATE_KEY = 'medflow.mentor.state';
const DAY_MS = 86400000;
const MENTOR_STATE_DEFAULT = {
  last_topic: null,
  last_subject: null,
  last_activity: null,
  last_interaction: null,
  study_minutes_today: 0,
  study_minutes_today_date: null,
  next_recommendation: null,
  last_open_day: null,
  streak: 0,
  days_started: 0,
  updated_at: null,
};

function readMentorState() {
  try {
    const raw = localStorage.getItem(MENTOR_STATE_KEY);
    return raw ? { ...MENTOR_STATE_DEFAULT, ...JSON.parse(raw) } : null;
  } catch { return null; }
}

function writeMentorState(patch) {
  try {
    const prev = readMentorState() || MENTOR_STATE_DEFAULT;
    const now = new Date().toISOString();
    // Reseta o contador diário se virou o dia
    const today = now.slice(0, 10);
    const dailyReset = prev.study_minutes_today_date !== today
      ? { study_minutes_today: 0, study_minutes_today_date: today }
      : {};
    const next = {
      ...prev,
      ...dailyReset,
      ...patch,
      updated_at: now,
      last_interaction: patch.last_interaction || now,
    };
    localStorage.setItem(MENTOR_STATE_KEY, JSON.stringify(next));

    // ─── Resume checkpoint: só se houver contexto real (matéria/tópico/atividade) ──
    const subj = next.last_subject;
    const topic = next.last_topic;
    const act = next.last_activity;
    if (subj || topic || act) {
      const parts = [];
      if (act) parts.push(act);
      const focus = topic || subj;
      const title = focus
        ? `Continuar ${act ? act.toLowerCase() : 'estudo'} de ${focus}`
        : `Continuar no Tutor${parts.length ? ' — ' + parts.join(' · ') : ''}`;
      saveCheckpoint('tutor', {
        title,
        subtitle: subj && topic && subj !== topic ? `${subj} · ${topic}` : (subj || topic || undefined),
        route: '/tutor',
        meta: { last_subject: subj, last_topic: topic, last_activity: act },
      });
    }

    return next;
  } catch { return null; }
}

// Marca "hoje" na sequência do aluno (streak + dia da preparação).
// Idempotente — só age uma vez por dia.
function touchMentorDay() {
  const s = readMentorState() || {};
  const today = new Date().toISOString().slice(0, 10);
  if (s.last_open_day === today) return s;
  const yesterday = new Date(Date.now() - DAY_MS).toISOString().slice(0, 10);
  const streak = s.last_open_day === yesterday ? (s.streak || 0) + 1 : 1;
  const days_started = (s.days_started || 0) + 1;
  return writeMentorState({ last_open_day: today, streak, days_started });
}

function isSameDay(iso) {
  if (!iso) return false;
  return new Date(iso).toISOString().slice(0, 10)
       === new Date().toISOString().slice(0, 10);
}

function isYesterday(iso) {
  if (!iso) return false;
  return new Date(iso).toISOString().slice(0, 10)
       === new Date(Date.now() - DAY_MS).toISOString().slice(0, 10);
}

// ─── Missões de aprendizagem — objetivos, não ferramentas ────
// Cada missão apenas orienta a intenção. O Preceptor identifica
// o tema, a disciplina e a melhor estratégia via /tutor/preceptor/interpret.
const MISSIONS = [
  {
    key: 'doubt', Icon: MessagesSquare, tone: 'brand',
    title: 'Tenho uma dúvida',
    subtitle: 'Entenda um tema ou uma questão passo a passo.',
    prompt: 'Explique ',
  },
  {
    key: 'review', Icon: BookOpen, tone: 'brand',
    title: 'Quero revisar um assunto',
    subtitle: 'Resumos inteligentes, mapas mentais e pontos-chave.',
    prompt: 'Revisar ',
  },
  {
    key: 'memorize', Icon: Brain, tone: 'brand',
    title: 'Quero memorizar',
    subtitle: 'Flashcards com repetição espaçada.',
    prompt: 'Fazer flashcards sobre ',
  },
  {
    key: 'train', Icon: Target, tone: 'brand',
    title: 'Quero treinar',
    subtitle: 'Questões inéditas, casos clínicos e simulados.',
    prompt: 'Gerar questões sobre ',
  },
  {
    key: 'exam', Icon: Calendar, tone: 'care',
    title: 'Tenho prova em breve',
    subtitle: 'Plano inteligente de estudos.',
    prompt: null,   // abre wizard de plano de prova
  },
];

// Modos legados usados internamente pelos wizards (post_exam, plan builder).
// Mantidos por retro-compatibilidade da arquitetura.
const MODES = [
  {
    key: 'exam_tomorrow', Icon: Target, tone: 'brand',
    title: 'Tenho prova amanhã',
    subtitle: 'Vou montar um treino focado no que vai cair.',
  },
  {
    key: 'quick_review', Icon: Timer, tone: 'brand',
    title: 'Quero revisar rapidamente',
    subtitle: 'Você escolhe o tempo. Eu monto o combo.',
  },
  {
    key: 'diagnostic', Icon: Compass, tone: 'brand',
    title: 'Quero descobrir meus pontos fracos',
    subtitle: 'Um exame inteligente pra mapear seu domínio.',
  },
  {
    key: 'post_exam', Icon: ClipboardList, tone: 'brand',
    title: 'Acabei de fazer uma prova',
    subtitle: 'Envie a devolutiva. Eu crio a revisão.',
  },
  {
    key: 'clinical_case', Icon: Stethoscope, tone: 'brand',
    title: 'Praticar um caso clínico',
    subtitle: 'Vinheta · decisão · feedback. 3 minutos.',
  },
  {
    key: 'guide_me', Icon: Sparkles, tone: 'care',
    title: 'Não sei por onde começar',
    subtitle: 'Deixe comigo. Hoje eu faria isto.',
  },
];

// ─── Helpers ────────────────────────────────────────────────
const input =
  'w-full px-3.5 py-2.5 rounded-lg text-[14px] hairline bg-white focus:outline-none focus:ring-2 focus:ring-brand/40 placeholder:text-zinc-400';

function formatDetail(detail) {
  if (detail == null) return null;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) return detail.map((e) => e?.msg || JSON.stringify(e)).join(' ');
  return String(detail);
}

// ─── Mission chips (Princípio 1: missões viram atalhos discretos) ────
// A caixa universal continua sendo a protagonista. As missões são chips
// pequenos, na altura de "sugestões", pra quem prefere clicar.
const MissionChips = ({ onSelect }) => (
  <div className="flex flex-wrap gap-2" data-testid="tutor-mission-grid">
    {MISSIONS.map((m) => (
      <button
        key={m.key}
        type="button"
        data-testid={`tutor-mission-${m.key}`}
        onClick={() => onSelect(m)}
        className="inline-flex items-center gap-1.5 px-3 py-2 rounded-full text-[12.5px] text-zinc-700 bg-white hairline hover:bg-zinc-50 transition-colors focus:outline-none focus:ring-2 focus:ring-brand/40"
      >
        <m.Icon
          strokeWidth={1.75}
          className="w-3.5 h-3.5"
          style={{ color: m.tone === 'care' ? 'var(--mf-care)' : 'var(--mf-brand)' }}
        />
        <span>{m.title}</span>
      </button>
    ))}
  </div>
);

// ─── "Hoje para você" — bilhete curto (Princípio 3) ─────────
// NÃO é dashboard. Uma linha só: último tema + progresso + recomendação.
// Se não há sinal, não aparece. Se há, é enxuto.
const TodayForYouPanel = ({ state, onContinueLast }) => {
  if (!state) return null;
  const days   = state.days_started || 0;
  const streak = state.streak || 0;
  const last   = state.last_topic;
  const hasSignal = days > 1 || streak > 1 || !!last;
  if (!hasSignal) return null;

  // Uma linha de progresso, factual — sem elogios genéricos.
  const progressLine =
      days >= 2 && streak >= 2 ? `Dia ${days} · ${streak} dias seguidos.`
    : days >= 2                ? `Dia ${days} da sua preparação.`
    : null;

  return (
    <section
      className="mb-5"
      data-testid="today-for-you"
      aria-label="Hoje para você"
    >
      <p className="text-[13.5px] text-zinc-600 leading-relaxed">
        {progressLine && <span>{progressLine} </span>}
        {last && (
          <>
            <span>Da última vez conversamos sobre </span>
            <strong className="text-zinc-900 font-medium">{last}</strong>
            <span> — </span>
            <button
              type="button"
              data-testid="today-continue-last"
              onClick={onContinueLast}
              className="underline underline-offset-2 font-medium"
              style={{ color: 'var(--mf-brand)' }}
            >
              <span>continuar de onde paramos?</span>
            </button>
          </>
        )}
      </p>
    </section>
  );
};

// ─── Mode landing (cards) ───────────────────────────────────
const ModeGrid = ({ onSelect }) => (
  <div data-testid="tutor-mode-grid" className="grid grid-cols-1 md:grid-cols-2 gap-3">
    {MODES.map((m) => (
      <button
        key={m.key}
        data-testid={`tutor-mode-${m.key}`}
        onClick={() => onSelect(m.key)}
        className="mf-card p-5 text-left transition-colors hover:bg-zinc-50 focus:outline-none focus:ring-2 focus:ring-brand/40"
      >
        <div className="flex items-start gap-3">
          <span
            className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0"
            style={{
              background: m.tone === 'care' ? 'var(--mf-care-soft)' : 'var(--mf-brand-soft)',
              color: m.tone === 'care' ? 'var(--mf-care)' : 'var(--mf-brand)',
            }}
          >
            <m.Icon strokeWidth={1.75} className="w-5 h-5" />
          </span>
          <div className="flex-1 min-w-0">
            <p className="text-[15px] font-semibold text-zinc-900 leading-tight"><span>{m.title}</span></p>
            <p className="mt-1 text-[13px] text-zinc-500 leading-relaxed"><span>{m.subtitle}</span></p>
          </div>
          <ChevronRight strokeWidth={1.75} className="w-4 h-4 text-zinc-300 mt-1.5 shrink-0" />
        </div>
      </button>
    ))}
  </div>
);

// ─── Wizards por modo ───────────────────────────────────────
const ExamTomorrowWizard = ({ onCreate, onBack, loading }) => {
  const [discipline, setDiscipline] = useState('');
  const [topicsRaw, setTopicsRaw] = useState('');
  const [timeMin, setTimeMin] = useState(40);
  const [energy, setEnergy] = useState('medium');
  const disabled = !discipline.trim() || !topicsRaw.trim() || loading;
  return (
    <div className="mf-card p-5 md:p-6 space-y-4 animate-fade-in" data-testid="tutor-wizard-exam_tomorrow">
      <div>
        <p className="eyebrow"><span>disciplina</span></p>
        <input
          data-testid="tutor-input-discipline"
          className={`${input} mt-2`}
          placeholder="ex.: Anatomia"
          value={discipline}
          onChange={(e) => setDiscipline(e.target.value)}
        />
      </div>
      <div>
        <p className="eyebrow"><span>quais assuntos vão cair? (separe por vírgula)</span></p>
        <textarea
          data-testid="tutor-input-topics"
          rows={2}
          className={`${input} mt-2`}
          placeholder="ex.: Face, Membro Superior, Plexo Braquial"
          value={topicsRaw}
          onChange={(e) => setTopicsRaw(e.target.value)}
        />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <p className="eyebrow"><span>quanto tempo você tem?</span></p>
          <select
            data-testid="tutor-input-time"
            className={`${input} mt-2`}
            value={timeMin}
            onChange={(e) => setTimeMin(parseInt(e.target.value))}
          >
            <option value={20}>20 min</option>
            <option value={40}>40 min</option>
            <option value={60}>1 hora</option>
            <option value={90}>1h30</option>
            <option value={120}>2 horas</option>
          </select>
        </div>
        <div>
          <p className="eyebrow"><span>como está sua energia?</span></p>
          <select
            data-testid="tutor-input-energy"
            className={`${input} mt-2`}
            value={energy}
            onChange={(e) => setEnergy(e.target.value)}
          >
            <option value="low">Baixa</option>
            <option value="medium">Média</option>
            <option value="high">Alta</option>
          </select>
        </div>
      </div>
      <div className="flex items-center justify-between pt-2">
        <button onClick={onBack} className="btn-ghost inline-flex items-center gap-1.5">
          <ArrowLeft className="w-4 h-4" /> <span>Voltar</span>
        </button>
        <button
          data-testid="tutor-wizard-submit"
          disabled={disabled}
          onClick={() => onCreate({
            mode: 'exam_tomorrow',
            discipline: discipline.trim(),
            topics: topicsRaw.split(',').map((t) => t.trim()).filter(Boolean),
            time_min: timeMin,
            energy,
          })}
          className="btn-primary"
        >
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <ArrowRight className="w-4 h-4" />}
          <span>{loading ? 'Montando…' : 'Montar treino'}</span>
        </button>
      </div>
    </div>
  );
};

const QuickReviewWizard = ({ onCreate, onBack, loading }) => {
  const [timeMin, setTimeMin] = useState(10);
  const [discipline, setDiscipline] = useState('');
  return (
    <div className="mf-card p-5 md:p-6 space-y-4 animate-fade-in" data-testid="tutor-wizard-quick_review">
      <p className="text-[14px] text-zinc-600 leading-relaxed">
        <span>Vou focar no que você mais precisa agora. Quanto tempo você tem?</span>
      </p>
      <div className="grid grid-cols-4 gap-2">
        {[5, 10, 20, 40].map((t) => (
          <button
            key={t}
            data-testid={`tutor-time-${t}`}
            onClick={() => setTimeMin(t)}
            className={`px-3 py-3 rounded-lg text-[14px] font-medium transition-colors hairline ${
              timeMin === t ? 'text-white' : 'bg-white text-zinc-700 hover:bg-zinc-50'
            }`}
            style={timeMin === t ? { background: 'var(--mf-brand)', borderColor: 'var(--mf-brand)' } : {}}
          >
            <span>{t} min</span>
          </button>
        ))}
      </div>
      <div>
        <p className="eyebrow"><span>disciplina (opcional — deixe em branco pra eu escolher)</span></p>
        <input
          data-testid="tutor-input-discipline"
          className={`${input} mt-2`}
          placeholder="ex.: Farmacologia"
          value={discipline}
          onChange={(e) => setDiscipline(e.target.value)}
        />
      </div>
      <div className="flex items-center justify-between pt-2">
        <button onClick={onBack} className="btn-ghost inline-flex items-center gap-1.5">
          <ArrowLeft className="w-4 h-4" /> <span>Voltar</span>
        </button>
        <button
          data-testid="tutor-wizard-submit"
          disabled={loading}
          onClick={() => onCreate({
            mode: 'quick_review',
            time_min: timeMin,
            discipline: discipline.trim() || null,
          })}
          className="btn-primary"
        >
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <ArrowRight className="w-4 h-4" />}
          <span>{loading ? 'Montando…' : 'Começar revisão'}</span>
        </button>
      </div>
    </div>
  );
};

const ClinicalCaseWizard = ({ onCreate, onBack, loading }) => {
  const [discipline, setDiscipline] = useState('');
  const [topic, setTopic] = useState('');
  const disabled = !discipline.trim() || !topic.trim() || loading;
  return (
    <div className="mf-card p-5 md:p-6 space-y-4 animate-fade-in" data-testid="tutor-wizard-clinical_case">
      <p className="text-[14px] text-zinc-600 leading-relaxed">
        <span>
          Vou montar 1 vinheta clínica realista, com 4 alternativas de conduta. Você decide, eu explico.
        </span>
      </p>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div>
          <p className="eyebrow"><span>disciplina</span></p>
          <input
            data-testid="tutor-clinical-discipline"
            className={`${input} mt-2`}
            placeholder="ex.: Cardiologia"
            value={discipline}
            onChange={(e) => setDiscipline(e.target.value)}
          />
        </div>
        <div>
          <p className="eyebrow"><span>tema</span></p>
          <input
            data-testid="tutor-clinical-topic"
            className={`${input} mt-2`}
            placeholder="ex.: Insuficiência Cardíaca"
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
          />
        </div>
      </div>
      <div className="flex items-center justify-between pt-2">
        <button onClick={onBack} className="btn-ghost inline-flex items-center gap-1.5">
          <ArrowLeft className="w-4 h-4" /> <span>Voltar</span>
        </button>
        <button
          data-testid="tutor-wizard-submit"
          disabled={disabled}
          onClick={() => onCreate({
            mode: 'clinical_case',
            discipline: discipline.trim(),
            topic: topic.trim(),
          })}
          className="btn-primary"
        >
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <ArrowRight className="w-4 h-4" />}
          <span>{loading ? 'Preparando…' : 'Ver caso'}</span>
        </button>
      </div>
    </div>
  );
};

const DiagnosticWizard = ({ onCreate, onBack, loading }) => {  const [discipline, setDiscipline] = useState('');
  return (
    <div className="mf-card p-5 md:p-6 space-y-4 animate-fade-in" data-testid="tutor-wizard-diagnostic">
      <p className="text-[14px] text-zinc-600 leading-relaxed">
        <span>
          Não é uma prova — é um exame inteligente. 6 questões pra eu mapear o que você já domina
          e onde ainda tem dificuldade.
        </span>
      </p>
      <div>
        <p className="eyebrow"><span>em qual disciplina?</span></p>
        <input
          data-testid="tutor-input-discipline"
          className={`${input} mt-2`}
          placeholder="ex.: Fisiologia"
          value={discipline}
          onChange={(e) => setDiscipline(e.target.value)}
        />
      </div>
      <div className="flex items-center justify-between pt-2">
        <button onClick={onBack} className="btn-ghost inline-flex items-center gap-1.5">
          <ArrowLeft className="w-4 h-4" /> <span>Voltar</span>
        </button>
        <button
          data-testid="tutor-wizard-submit"
          disabled={!discipline.trim() || loading}
          onClick={() => onCreate({ mode: 'diagnostic', discipline: discipline.trim() })}
          className="btn-primary"
        >
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <ArrowRight className="w-4 h-4" />}
          <span>{loading ? 'Preparando…' : 'Começar diagnóstico'}</span>
        </button>
      </div>
    </div>
  );
};

// ─── Content renderers ────────────────────────────────────────
const QuestionCard = ({ payload, onAnswered }) => {
  const [choice, setChoice] = useState(null);
  const [submitted, setSubmitted] = useState(false);
  const opts = payload?.options || [];
  const correct = payload?.correct_index;
  const explain = payload?.explanation;

  const handleSubmit = () => {
    if (choice == null) return;
    setSubmitted(true);
    onAnswered?.(choice === correct);
  };
  return (
    <div className="animate-fade-in">
      <p className="text-[14.5px] font-medium text-zinc-900 leading-relaxed">
        <span>{payload?.stem || 'Questão sem enunciado.'}</span>
      </p>
      <ul className="mt-4 space-y-2">
        {opts.map((o, i) => {
          const isChosen = choice === i;
          const isRight = submitted && i === correct;
          const isWrong = submitted && isChosen && i !== correct;
          return (
            <li key={i}>
              <button
                data-testid={`tutor-option-${i}`}
                disabled={submitted}
                onClick={() => setChoice(i)}
                className={`w-full text-left px-3.5 py-2.5 rounded-lg text-[13.5px] hairline transition-colors ${
                  isRight ? 'text-white' : isWrong ? 'text-white' :
                  isChosen ? 'text-white' : 'bg-white hover:bg-zinc-50 text-zinc-800'
                }`}
                style={
                  isRight ? { background: 'var(--mf-success)', borderColor: 'var(--mf-success)' } :
                  isWrong ? { background: 'var(--mf-care)', borderColor: 'var(--mf-care)' } :
                  isChosen ? { background: 'var(--mf-brand)', borderColor: 'var(--mf-brand)' } : {}
                }
              >
                <span className="mono mr-2 opacity-70">{String.fromCharCode(65 + i)}.</span>
                <span>{o}</span>
              </button>
            </li>
          );
        })}
      </ul>
      {!submitted && (
        <button
          data-testid="tutor-submit-answer"
          onClick={handleSubmit}
          disabled={choice == null}
          className="mt-4 btn-primary"
        >
          <span>Responder</span> <ArrowRight className="w-4 h-4" />
        </button>
      )}
      {submitted && explain && (
        <div
          className="mt-4 p-3.5 rounded-lg text-[13px] leading-relaxed"
          style={{ background: 'var(--mf-brand-soft)', color: 'var(--mf-ink-2)' }}
          data-testid="tutor-explanation"
        >
          <p className="font-semibold" style={{ color: 'var(--mf-brand)' }}>
            {choice === correct ? (
              <><CheckCircle2 className="inline w-3.5 h-3.5 mr-1" /><span>Correto.</span></>
            ) : (
              <><XCircle className="inline w-3.5 h-3.5 mr-1" /><span>Gabarito: {String.fromCharCode(65 + (correct ?? 0))}</span></>
            )}
          </p>
          <p className="mt-1"><span>{explain}</span></p>
        </div>
      )}
    </div>
  );
};

const FlashcardCard = ({ payload, onAnswered }) => {
  const [flipped, setFlipped] = useState(false);
  return (
    <div className="animate-fade-in text-center">
      <button
        data-testid="tutor-flashcard-flip"
        onClick={() => setFlipped((v) => !v)}
        className="w-full py-10 md:py-14 rounded-xl hairline hover:bg-zinc-50 transition-colors"
      >
        <p className="text-[11px] uppercase tracking-wider text-zinc-400 mb-3">
          <span>{flipped ? 'resposta' : 'pergunta'}</span>
        </p>
        <p className="text-[16px] md:text-[18px] font-medium text-zinc-900 leading-relaxed px-5">
          <span>{flipped ? payload?.back : payload?.front}</span>
        </p>
        <p className="mt-4 text-[11.5px] text-zinc-400">
          <span>Clique pra {flipped ? 'ver a pergunta' : 'ver a resposta'}</span>
        </p>
      </button>
      {flipped && (
        <div className="mt-4 flex items-center justify-center gap-2">
          <button
            data-testid="tutor-flash-wrong"
            onClick={() => onAnswered?.(false)}
            className="btn-secondary"
          >
            <XCircle className="w-4 h-4" style={{ color: 'var(--mf-care)' }} /> <span>Errei</span>
          </button>
          <button
            data-testid="tutor-flash-right"
            onClick={() => onAnswered?.(true)}
            className="btn-secondary"
          >
            <CheckCircle2 className="w-4 h-4" style={{ color: 'var(--mf-success)' }} /> <span>Acertei</span>
          </button>
        </div>
      )}
    </div>
  );
};

const SummaryCard = ({ payload }) => (
  <div className="animate-fade-in">
    <ul className="space-y-2.5">
      {(payload?.bullets || []).map((b, i) => (
        <li key={i} className="flex items-start gap-3">
          <span className="mono text-[11px] mt-1" style={{ color: 'var(--mf-brand)' }}><span>{String(i + 1).padStart(2, '0')}</span></span>
          <span className="text-[14px] text-zinc-800 leading-relaxed"><span>{b}</span></span>
        </li>
      ))}
    </ul>
  </div>
);

const ExplanationCard = ({ payload }) => (
  <div className="animate-fade-in space-y-3">
    {(payload?.paragraphs || []).map((p, i) => (
      <p key={i} className="text-[14px] text-zinc-800 leading-relaxed"><span>{p}</span></p>
    ))}
  </div>
);

// ─── Caso clínico (3 passos: caso → decisão → feedback) ───────
const ClinicalCaseCard = ({ payload, onAnswered, onCompleted }) => {
  const [choice, setChoice] = useState(null);
  const [submitted, setSubmitted] = useState(false);

  const opts = payload?.options || [];
  const chosen = opts.find((o) => o.letter === choice) || null;
  const isCorrect = submitted && chosen?.correct === true;

  const handleSubmit = () => {
    if (!chosen) return;
    setSubmitted(true);
    onAnswered?.(!!chosen.correct);
  };

  // Passo 1+2: vinheta sempre visível, decisão embaixo
  return (
    <div className="animate-fade-in space-y-5" data-testid="tutor-clinical-case">
      {/* Passo 1: vinheta clínica */}
      <div
        data-testid="clinical-case-stem"
        className="p-4 rounded-lg text-[13.5px] leading-relaxed text-zinc-800"
        style={{ background: 'var(--mf-brand-soft, #FFF7ED)' }}
      >
        <p className="eyebrow mb-2" style={{ color: 'var(--mf-brand, #DC6B4C)' }}>
          <span>caso clínico</span>
        </p>
        <p className="whitespace-pre-line"><span>{payload?.stem}</span></p>
      </div>

      {/* Passo 2: decisão */}
      <div data-testid="clinical-case-decision">
        <p className="text-[14.5px] font-semibold text-zinc-900 leading-snug">
          <span>{payload?.question || 'Qual sua conduta?'}</span>
        </p>
        <ul className="mt-3 space-y-2">
          {opts.map((o) => {
            const active = choice === o.letter;
            const showRight = submitted && o.correct === true;
            const showWrong = submitted && active && !o.correct;
            return (
              <li key={o.letter}>
                <button
                  data-testid={`clinical-option-${o.letter}`}
                  disabled={submitted}
                  onClick={() => setChoice(o.letter)}
                  className={`w-full text-left px-3.5 py-3 rounded-lg text-[13.5px] hairline transition-colors ${
                    showRight ? 'text-white' :
                    showWrong ? 'text-white' :
                    active ? 'text-white' :
                    'bg-white hover:bg-zinc-50 text-zinc-800'
                  }`}
                  style={
                    showRight ? { background: 'var(--mf-success)', borderColor: 'var(--mf-success)' } :
                    showWrong ? { background: 'var(--mf-care)', borderColor: 'var(--mf-care)' } :
                    active ? { background: 'var(--mf-brand)', borderColor: 'var(--mf-brand)' } : {}
                  }
                >
                  <span className="mono mr-2 opacity-70">{o.letter}.</span>
                  <span>{o.text}</span>
                </button>
              </li>
            );
          })}
        </ul>

        {!submitted && (
          <button
            data-testid="clinical-submit"
            onClick={handleSubmit}
            disabled={!chosen}
            className="mt-4 btn-primary"
          >
            <span>Ver feedback</span> <ArrowRight className="w-4 h-4" />
          </button>
        )}
      </div>

      {/* Passo 3: feedback */}
      {submitted && chosen && (
        <div
          data-testid="clinical-feedback"
          data-correct={isCorrect ? 'true' : 'false'}
          className="animate-fade-in space-y-3"
        >
          <div
            className="p-4 rounded-lg text-[13.5px] leading-relaxed"
            style={{
              background: isCorrect ? 'var(--mf-success-soft, #ECFDF5)' : 'var(--mf-care-soft, #FEF3C7)',
              color: isCorrect ? 'var(--mf-success, #10B981)' : '#B15437',
            }}
          >
            <p className="font-semibold flex items-center gap-1.5">
              {isCorrect
                ? <><CheckCircle2 className="w-4 h-4" /><span>Correto — {chosen.letter}</span></>
                : <><XCircle className="w-4 h-4" /><span>Não é a melhor opção — {chosen.letter}</span></>}
            </p>
            <p className="mt-1.5 text-zinc-800"><span>{chosen.feedback}</span></p>
          </div>

          {/* Se errou, mostra o feedback da correta também */}
          {!isCorrect && opts.filter((o) => o.correct).map((o) => (
            <div
              key={o.letter}
              data-testid="clinical-correct-explain"
              className="p-4 rounded-lg text-[13.5px] leading-relaxed"
              style={{ background: 'var(--mf-success-soft, #ECFDF5)', color: 'var(--mf-ink-2)' }}
            >
              <p className="font-semibold" style={{ color: 'var(--mf-success)' }}>
                <CheckCircle2 className="inline w-3.5 h-3.5 mr-1" />
                <span>Alternativa correta: {o.letter}</span>
              </p>
              <p className="mt-1.5 text-zinc-800"><span>{o.feedback}</span></p>
            </div>
          ))}

          {/* Teaching point */}
          {payload?.teaching_point && (
            <div
              data-testid="clinical-teaching-point"
              className="p-4 rounded-lg hairline"
              style={{ background: 'var(--mf-hair-soft, #FAFAFA)' }}
            >
              <p className="eyebrow mb-1"><span>ponto-chave</span></p>
              <p className="text-[13px] text-zinc-800 leading-relaxed">
                <span>{payload.teaching_point}</span>
              </p>
            </div>
          )}

          <button
            data-testid="clinical-complete"
            onClick={onCompleted}
            className="btn-secondary"
          >
            <CheckCircle2 className="w-4 h-4" /> <span>Concluir caso</span>
          </button>
        </div>
      )}
    </div>
  );
};

const ContentRenderer = ({ slot, content, onAnswered, onCompleted }) => {
  if (!content) return null;
  const kind = content.kind || slot.kind;
  const payload = content.payload || {};

  if ((payload?.raw && !payload?.stem && !payload?.front && !payload?.bullets)) {
    return <p className="text-[13px] text-zinc-500 italic"><span>{payload.raw}</span></p>;
  }

  if (kind === 'question') return <QuestionCard payload={payload} onAnswered={onAnswered} />;
  if (kind === 'flashcard') return <FlashcardCard payload={payload} onAnswered={onAnswered} />;
  if (kind === 'clinical_case') {
    return (
      <ClinicalCaseCard
        payload={payload}
        onAnswered={onAnswered}
        onCompleted={onCompleted}
      />
    );
  }
  if (kind === 'summary') {
    return (
      <>
        <SummaryCard payload={payload} />
        <button onClick={onCompleted} className="mt-4 btn-secondary">
          <CheckCircle2 className="w-4 h-4" /> <span>Marcar como revisado</span>
        </button>
      </>
    );
  }
  if (kind === 'explanation') {
    return (
      <>
        <ExplanationCard payload={payload} />
        <button onClick={onCompleted} className="mt-4 btn-secondary">
          <CheckCircle2 className="w-4 h-4" /> <span>Concluir leitura</span>
        </button>
      </>
    );
  }
  return <pre className="text-[12px] text-zinc-500 whitespace-pre-wrap"><span>{JSON.stringify(payload, null, 2)}</span></pre>;
};

// ─── Plan runner ─────────────────────────────────────────────
const PlanRunner = ({ plan, onExit }) => {
  const [idx, setIdx] = useState(0);
  const [contentMap, setContentMap] = useState({}); // slot.id -> {content, event_id, source}
  const [loadingSlot, setLoadingSlot] = useState(false);
  const [error, setError] = useState(null);
  const [done, setDone] = useState(false);
  const [fatigue, setFatigue] = useState(null);

  const slot = plan.slots[idx];
  const total = plan.slots.length;
  const loaded = contentMap[slot?.id];
  const reusedCount = Object.values(contentMap).filter((v) => v.source === 'reused').length;
  const generatedCount = Object.values(contentMap).filter((v) => v.source === 'generated').length;

  // Lazy load do conteúdo ao entrar num slot
  useEffect(() => {
    if (!slot || contentMap[slot.id]) return;
    let alive = true;
    setLoadingSlot(true);
    setError(null);
    (async () => {
      try {
        const { data } = await api.post('/learning/request', {
          kind: slot.kind,
          discipline: slot.discipline,
          topic: slot.topic,
          subtopic: slot.subtopic || null,
          period: slot.period || null,
          variant: slot.variant || 'default',
        }, { timeout: 60_000 });
        if (!alive) return;
        setContentMap((m) => ({ ...m, [slot.id]: data }));
      } catch (e) {
        if (!alive) return;
        setError(formatDetail(e?.response?.data?.detail) || 'Falha ao carregar conteúdo. Tente de novo.');
      } finally { if (alive) setLoadingSlot(false); }
    })();
    return () => { alive = false; };
  }, [slot?.id]);

  const handleAnswered = async (correct) => {
    const c = contentMap[slot.id]?.content;
    if (!c?.id) return;
    try {
      const { data } = await api.post(`/learning/content/${c.id}/answered`, { correct });
      if (data?.fatigue?.fatigued) {
        setFatigue(data.fatigue);
      }
    } catch { /* silent */ }
  };

  const handleCompleted = async () => {
    const c = contentMap[slot.id]?.content;
    if (!c?.id) return;
    try {
      await api.post(`/learning/content/${c.id}/completed`);
    } catch { /* silent */ }
  };

  const next = () => {
    if (idx + 1 >= total) setDone(true);
    else setIdx(idx + 1);
  };

  if (done) {
    return (
      <div className="mf-card p-6 md:p-8 text-center animate-fade-in" data-testid="tutor-plan-done">
        <span
          className="inline-flex w-12 h-12 rounded-xl items-center justify-center mb-4"
          style={{ background: 'var(--mf-success-soft)', color: 'var(--mf-success)' }}
        >
          <CheckCircle2 strokeWidth={1.75} className="w-6 h-6" />
        </span>
        <h2 className="text-[22px] font-semibold text-zinc-900 tracking-tight">
          <span>Sessão concluída</span>
        </h2>
        <p className="mt-2 text-[14px] text-zinc-600 max-w-md mx-auto">
          <span>{total} atividades completadas. Seu mapa de domínio já foi atualizado.</span>
        </p>
        {reusedCount > 0 && (
          <p className="mt-3 text-[12.5px] text-zinc-400">
            <span>💡 {reusedCount} de {total} atividades vieram do que já preparei com outros alunos — economizando o seu tempo.</span>
          </p>
        )}
        <button data-testid="tutor-plan-done-back" onClick={onExit} className="mt-6 btn-primary">
          <span>Voltar ao início</span> <ArrowRight className="w-4 h-4" />
        </button>
      </div>
    );
  }

  return (
    <div className="animate-fade-in" data-testid="tutor-plan-runner">
      <div className="flex items-center justify-between mb-4">
        <button onClick={onExit} className="btn-ghost inline-flex items-center gap-1.5">
          <ArrowLeft className="w-4 h-4" /> <span>Sair da sessão</span>
        </button>
        <span className="mono text-[12px] text-zinc-500">
          <span>{idx + 1} / {total}</span>
        </span>
      </div>

      <div className="h-1.5 rounded-full bg-zinc-100 overflow-hidden mb-6">
        <div
          className="h-full transition-all duration-500"
          style={{ width: `${((idx + 1) / total) * 100}%`, background: 'var(--mf-brand)' }}
        />
      </div>

      <div className="mf-card p-5 md:p-6" data-testid="tutor-slot-card">
        {fatigue?.fatigued && (
          <div
            data-testid="tutor-fatigue-banner"
            className="mb-4 p-3.5 rounded-lg flex items-start gap-3"
            style={{ background: 'var(--mf-care-soft)', color: '#B15437' }}
          >
            <AlertCircle className="w-5 h-5 shrink-0 mt-0.5" />
            <div className="flex-1">
              <p className="text-[13.5px] font-semibold"><span>{fatigue.reason}</span></p>
              <div className="mt-2 flex gap-2">
                <button
                  data-testid="tutor-fatigue-pause"
                  onClick={onExit}
                  className="btn-secondary text-[12.5px]"
                >
                  <span>Pausar sessão</span>
                </button>
                <button
                  onClick={() => setFatigue(null)}
                  className="btn-ghost text-[12.5px]"
                >
                  <span>Ignorar</span>
                </button>
              </div>
            </div>
          </div>
        )}
        <div className="flex items-center justify-between mb-4">
          <div>
            <p className="eyebrow"><span>{slot.phase || slot.kind}</span></p>
            <p className="mt-1 text-[13.5px] font-semibold text-zinc-900"><span>{slot.label}</span></p>
          </div>
          {loaded?.source === 'reused' && (
            <span className="pill inline-flex items-center gap-1 opacity-70">
              <RefreshCw className="w-3 h-3" /> <span>consolidação</span>
            </span>
          )}
          {loaded?.source === 'generated' && (
            <span className="pill pill-brand inline-flex items-center gap-1">
              <Sparkles className="w-3 h-3" /> <span>preparado agora</span>
            </span>
          )}
        </div>

        {loadingSlot && (
          <div className="py-10 flex flex-col items-center gap-3">
            <Loader2 className="w-6 h-6 text-brand animate-spin" style={{ color: 'var(--mf-brand)' }} />
            <p className="text-[12.5px] text-zinc-500"><span>Preparando o próximo passo com carinho…</span></p>
          </div>
        )}

        {error && (
          <div
            className="p-3 rounded-lg text-[13px] flex items-start gap-2"
            style={{ background: 'var(--mf-care-soft)', color: '#B15437' }}
          >
            <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
            <span>{error}</span>
          </div>
        )}

        {loaded && (
          <ContentRenderer
            slot={slot}
            content={loaded.content}
            onAnswered={handleAnswered}
            onCompleted={handleCompleted}
          />
        )}
      </div>

      {loaded && (
        <div className="mt-4 flex justify-end">
          <button data-testid="tutor-slot-next" onClick={next} className="btn-primary">
            <span>{idx + 1 === total ? 'Finalizar sessão' : 'Próximo'}</span>
            <ArrowRight className="w-4 h-4" />
          </button>
        </div>
      )}
    </div>
  );
};

// ─── Mastery Map ─────────────────────────────────────────────
const MasteryBar = ({ score, size = 'md' }) => {
  const pct = score == null ? 0 : Math.round(score * 100);
  const h = size === 'sm' ? 'h-1.5' : 'h-2';
  const color = score == null ? 'var(--mf-hair-2)'
    : score >= 0.75 ? 'var(--mf-success)'
    : score >= 0.5 ? 'var(--mf-brand)'
    : 'var(--mf-care)';
  return (
    <div className={`${h} rounded-full overflow-hidden bg-zinc-100`}>
      <div className="h-full transition-all duration-500" style={{ width: `${pct}%`, background: color }} />
    </div>
  );
};

const MasteryMap = () => {
  const [data, setData] = useState(null);
  const [expanded, setExpanded] = useState({});
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const { data } = await api.get('/tutor/mastery-map');
      setData(data);
    } finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  if (loading) return <div className="py-6 flex justify-center"><Loader2 className="w-5 h-5 animate-spin" style={{ color: 'var(--mf-brand)' }} /></div>;
  if (!data || data.empty) {
    return (
      <div className="mf-card p-5 text-center" data-testid="mastery-empty">
        <BarChart3 className="w-8 h-8 mx-auto text-zinc-300 mb-3" strokeWidth={1.5} />
        <p className="text-[13.5px] font-semibold text-zinc-800"><span>Seu mapa está em branco</span></p>
        <p className="mt-1.5 text-[12.5px] text-zinc-500 max-w-sm mx-auto leading-relaxed">
          <span>Assim que você começar uma sessão aqui em cima, o Meu Tutor passa a mapear o que você domina — por disciplina, tema e subtema.</span>
        </p>
      </div>
    );
  }
  return (
    <div className="mf-card p-5 md:p-6 space-y-4" data-testid="mastery-map">
      {data.disciplines.map((d) => (
        <div key={d.discipline} data-testid={`mastery-disc-${d.discipline}`}>
          <button
            className="w-full flex items-center justify-between gap-3 text-left"
            onClick={() => setExpanded((s) => ({ ...s, [d.discipline]: !s[d.discipline] }))}
          >
            <div className="flex-1 min-w-0">
              <div className="flex items-center justify-between mb-1.5">
                <p className="text-[14px] font-semibold text-zinc-900 capitalize"><span>{d.discipline}</span></p>
                <span className="mono text-[12px] text-zinc-500">
                  <span>{d.score == null ? 'aprendendo' : `${Math.round(d.score * 100)}%`}</span>
                </span>
              </div>
              <MasteryBar score={d.score} />
            </div>
            <ChevronRight
              strokeWidth={1.75}
              className="w-4 h-4 text-zinc-400 transition-transform shrink-0"
              style={{ transform: expanded[d.discipline] ? 'rotate(90deg)' : 'none' }}
            />
          </button>
          {expanded[d.discipline] && (
            <ul className="mt-3 ml-3 space-y-3 pl-3" style={{ borderLeft: '2px solid var(--mf-hair)' }}>
              {d.topics.map((t) => (
                <li key={t.topic}>
                  <div className="flex items-center justify-between mb-1">
                    <p className="text-[13px] text-zinc-700 capitalize"><span>{t.topic}</span></p>
                    <span className="mono text-[11.5px] text-zinc-400">
                      <span>{t.score == null ? '—' : `${Math.round(t.score * 100)}%`}</span>
                    </span>
                  </div>
                  <MasteryBar score={t.score} size="sm" />
                  {t.subtopics?.length > 1 && (
                    <ul className="mt-2 ml-3 space-y-1.5">
                      {t.subtopics.map((st, i) => (
                        <li key={i} className="flex items-center justify-between text-[12px]">
                          <span className="text-zinc-500 truncate"><span>{st.subtopic || '(sem subtópico)'}</span></span>
                          <span className="mono text-[11px] text-zinc-400 ml-2">
                            <span>{st.score == null ? '—' : `${Math.round(st.score * 100)}%`}</span>
                          </span>
                        </li>
                      ))}
                    </ul>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      ))}
    </div>
  );
};

// ─── Post-exam (legacy devolutiva flow) — inline component ────
const PostExamFlow = ({ onBack }) => {
  const [form, setForm] = useState({ subject: '', exam_name: '', grade: '', weak_topics: '', strong_topics: '', notes: '' });
  const [current, setCurrent] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [answers, setAnswers] = useState({});
  const [result, setResult] = useState(null);

  const submit = async () => {
    if (!form.subject.trim() || !form.weak_topics.trim()) {
      setError('Informe pelo menos a matéria e os tópicos onde errou.');
      return;
    }
    setLoading(true); setError(null);
    try {
      const payload = { ...form, grade: form.grade ? parseFloat(form.grade) : null };
      await streamPost('/tutor/exam-feedback/stream', payload, {
        onDone: (data) => setCurrent(data.feedback),
        onError: (err) => setError(formatDetail(err?.detail) || 'Não foi possível gerar a análise.'),
      });
    } catch (e) {
      setError('Não foi possível gerar a análise. Verifique sua conexão e tente novamente.');
    } finally { setLoading(false); }
  };

  const submitAnswers = async () => {
    const { data } = await api.post(`/tutor/exam-feedback/${current.id}/answers`, { answers });
    setResult(data);
  };

  if (current) {
    return (
      <div className="mf-card p-5 md:p-6 animate-fade-in" data-testid="tutor-postexam-result">
        <div className="flex items-center justify-between mb-3">
          <p className="eyebrow"><span>{current.subject}{current.exam_name ? ` · ${current.exam_name}` : ''}</span></p>
          <button onClick={onBack} className="btn-ghost text-[12px]"><span>Voltar</span></button>
        </div>
        <p className="text-[14px] text-zinc-800 leading-relaxed"><span>{current.diagnosis}</span></p>
        <div className="mt-5">
          <h3 className="text-[13.5px] font-semibold text-zinc-900 mb-2"><span>Áreas de foco</span></h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
            {(current.focus_areas || []).map((f, i) => (
              <div key={i} className="mf-card p-3">
                <p className="text-[12.5px] font-semibold" style={{ color: 'var(--mf-brand)' }}><span>{f.topic}</span></p>
                <ul className="mt-2 space-y-1 text-[12px] text-zinc-700">
                  {(f.plan || []).map((p, j) => <li key={j}><span>• {p}</span></li>)}
                </ul>
              </div>
            ))}
          </div>
        </div>
        <div className="mt-6">
          <h3 className="text-[13.5px] font-semibold text-zinc-900 mb-3"><span>10 questões de revisão</span></h3>
          <ol className="space-y-3">
            {(current.questions || []).map((q, i) => {
              const chosen = answers[String(i)];
              const detail = result?.detail?.find((d) => d.index === i);
              return (
                <li key={i} className="rounded-lg hairline p-3 bg-white">
                  <p className="text-[13px] text-zinc-800"><span className="mono mr-1" style={{ color: 'var(--mf-brand)' }}>{i + 1}.</span> <span>{q.stem}</span></p>
                  <div className="mt-2 grid gap-1.5">
                    {(q.options || []).map((opt) => {
                      const letter = opt.trim()[0]?.toUpperCase();
                      const active = chosen === letter;
                      const isRight = detail && detail.expected === letter;
                      const isWrongPick = detail && detail.given === letter && !detail.correct;
                      return (
                        <button key={letter} disabled={!!result}
                          onClick={() => setAnswers({ ...answers, [String(i)]: letter })}
                          className="text-left px-3 py-2 rounded-lg text-[12.5px] hairline transition-colors bg-white hover:bg-zinc-50"
                          style={
                            isRight ? { background: 'var(--mf-success-soft)', color: 'var(--mf-success)', borderColor: 'transparent' } :
                            isWrongPick ? { background: 'var(--mf-care-soft)', color: '#B15437', borderColor: 'transparent' } :
                            active ? { background: 'var(--mf-brand-soft)', color: 'var(--mf-brand)', borderColor: 'transparent' } : {}
                          }
                        >
                          <span>{opt}</span>
                        </button>
                      );
                    })}
                  </div>
                  {detail && (
                    <p className="mt-2 text-[12px] text-zinc-600">
                      {detail.correct ? (
                        <><CheckCircle2 className="inline w-3.5 h-3.5 mr-1" style={{ color: 'var(--mf-success)' }} /><span>Correto.</span></>
                      ) : (
                        <><XCircle className="inline w-3.5 h-3.5 mr-1" style={{ color: 'var(--mf-care)' }} /><span>Gabarito: {detail.expected}. </span></>
                      )}
                      <span>{q.explanation}</span>
                    </p>
                  )}
                </li>
              );
            })}
          </ol>
          {!result && (
            <button data-testid="tutor-postexam-check" onClick={submitAnswers} className="mt-4 btn-primary">
              <GraduationCap className="w-4 h-4" /> <span>Corrigir minhas respostas</span>
            </button>
          )}
          {result && (
            <div className="mt-4 p-3.5 rounded-lg" style={{ background: 'var(--mf-brand-soft)' }}>
              <p className="text-[12.5px] font-semibold" style={{ color: 'var(--mf-brand)' }}><span>Resultado</span></p>
              <p className="mt-1 text-[16px] font-semibold text-zinc-900">
                <span>{result.correct} / {result.total} acertos · nota {result.score}</span>
              </p>
            </div>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="mf-card p-5 md:p-6 space-y-4 animate-fade-in" data-testid="tutor-wizard-post_exam">
      <p className="text-[14px] text-zinc-600 leading-relaxed">
        <span>Envie sua devolutiva. Eu identifico as lacunas, monto 10 questões de revisão e atualizo seu mapa.</span>
      </p>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div>
          <p className="eyebrow"><span>matéria</span></p>
          <input data-testid="tutor-postexam-subject" className={`${input} mt-2`} placeholder="ex.: Anatomia" value={form.subject} onChange={(e) => setForm({ ...form, subject: e.target.value })} />
        </div>
        <div>
          <p className="eyebrow"><span>nome da prova (opcional)</span></p>
          <input className={`${input} mt-2`} value={form.exam_name} onChange={(e) => setForm({ ...form, exam_name: e.target.value })} placeholder="ex.: P1 · Sistema Locomotor" />
        </div>
        <div>
          <p className="eyebrow"><span>nota (0-10, opcional)</span></p>
          <input type="number" step="0.1" min="0" max="10" className={`${input} mt-2`} value={form.grade} onChange={(e) => setForm({ ...form, grade: e.target.value })} placeholder="6.5" />
        </div>
      </div>
      <div>
        <p className="eyebrow"><span>onde você errou *</span></p>
        <textarea rows={2} data-testid="tutor-postexam-weak" className={`${input} mt-2`} placeholder="tópicos onde teve dificuldade" value={form.weak_topics} onChange={(e) => setForm({ ...form, weak_topics: e.target.value })} />
      </div>
      <div>
        <p className="eyebrow"><span>onde você acertou (opcional)</span></p>
        <textarea rows={2} className={`${input} mt-2`} value={form.strong_topics} onChange={(e) => setForm({ ...form, strong_topics: e.target.value })} />
      </div>
      {error && (
        <div className="p-3 rounded-lg flex items-start gap-2 text-[13px]" style={{ background: 'var(--mf-care-soft)', color: '#B15437' }}>
          <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" /> <span>{error}</span>
        </div>
      )}
      <div className="flex items-center justify-between pt-2">
        <button onClick={onBack} className="btn-ghost inline-flex items-center gap-1.5">
          <ArrowLeft className="w-4 h-4" /> <span>Voltar</span>
        </button>
        <button data-testid="tutor-wizard-submit" disabled={loading || !form.subject.trim() || !form.weak_topics.trim()} onClick={submit} className="btn-primary">
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <ArrowRight className="w-4 h-4" />}
          <span>{loading ? 'Analisando…' : 'Gerar análise + 10 questões'}</span>
        </button>
      </div>
    </div>
  );
};

// ─── Due Review Runner (curva de esquecimento) ────────────────
const DueReviewRunner = ({ items, onExit }) => {
  const [idx, setIdx] = useState(0);
  const [done, setDone] = useState(false);
  const total = items.length;
  const it = items[idx];

  const handleAnswered = async (correct) => {
    try {
      await api.post(`/learning/content/${it.content_id}/answered`, {
        correct,
        time_spent_sec: null,
      });
    } catch { /* silent */ }
  };
  const handleReviewed = async () => {
    try {
      await api.post(`/learning/content/${it.content_id}/reviewed`, {});
    } catch { /* silent */ }
  };

  const next = () => {
    if (idx + 1 >= total) setDone(true);
    else setIdx(idx + 1);
  };

  if (done) {
    return (
      <div className="mf-card p-6 md:p-8 text-center animate-fade-in" data-testid="tutor-due-done">
        <span
          className="inline-flex w-12 h-12 rounded-xl items-center justify-center mb-4"
          style={{ background: 'var(--mf-success-soft)', color: 'var(--mf-success)' }}
        >
          <CheckCircle2 strokeWidth={1.75} className="w-6 h-6" />
        </span>
        <h2 className="text-[22px] font-semibold text-zinc-900 tracking-tight">
          <span>Revisões concluídas</span>
        </h2>
        <p className="mt-2 text-[14px] text-zinc-600 max-w-md mx-auto">
          <span>Você acabou de consolidar {total} carta(s). Volto a te lembrar delas na hora certa.</span>
        </p>
        <button onClick={onExit} className="mt-6 btn-primary">
          <span>Voltar</span> <ArrowRight className="w-4 h-4" />
        </button>
      </div>
    );
  }

  const kind = it.kind;
  const payload = it.payload || {};

  return (
    <div className="animate-fade-in" data-testid="tutor-due-runner">
      <div className="flex items-center justify-between mb-4">
        <button onClick={onExit} className="btn-ghost inline-flex items-center gap-1.5">
          <ArrowLeft className="w-4 h-4" /> <span>Sair da revisão</span>
        </button>
        <span className="mono text-[12px] text-zinc-500">
          <span>{idx + 1} / {total}</span>
        </span>
      </div>

      <div className="h-1.5 rounded-full bg-zinc-100 overflow-hidden mb-6">
        <div
          className="h-full transition-all duration-500"
          style={{ width: `${((idx + 1) / total) * 100}%`, background: 'var(--mf-brand)' }}
        />
      </div>

      <div className="mf-card p-5 md:p-6" data-testid="tutor-due-card">
        <div className="flex items-center justify-between mb-4">
          <div>
            <p className="eyebrow"><span>revisão espaçada</span></p>
            <p className="mt-1 text-[13.5px] font-semibold text-zinc-900">
              <span>{it.discipline}{it.topic ? ` · ${it.topic}` : ''}</span>
            </p>
          </div>
          <span className="pill">
            <span>{it.interval_days}d de intervalo</span>
          </span>
        </div>

        {kind === 'question' && <QuestionCard payload={payload} onAnswered={handleAnswered} />}
        {kind === 'flashcard' && <FlashcardCard payload={payload} onAnswered={handleAnswered} />}
        {kind !== 'question' && kind !== 'flashcard' && (
          <>
            <SummaryCard payload={payload} />
            <button onClick={handleReviewed} className="mt-4 btn-secondary">
              <CheckCircle2 className="w-4 h-4" /> <span>Marcar como revisado</span>
            </button>
          </>
        )}
      </div>

      <div className="mt-4 flex justify-end">
        <button data-testid="tutor-due-next" onClick={next} className="btn-primary">
          <span>{idx + 1 === total ? 'Finalizar' : 'Próxima'}</span>
          <ArrowRight className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
};

// ── Insight do Preceptor (padrão observado, não texto genérico) ─
// Usa `home.noticed` do backend: quando o motor identifica um padrão real,
// ele vem com mode='observed'. Se ainda não há sinal (mode='learning'),
// escondemos — não inventamos observação.
const InsightCard = ({ noticed }) => {
  if (!noticed || noticed.mode !== 'observed' || !noticed.text) return null;
  return (
    <div
      className="rounded-2xl overflow-hidden mb-4 md:mb-5 border"
      style={{
        background: 'linear-gradient(135deg, #F5F3FF 0%, #FEF3E9 100%)',
        borderColor: '#EDE9FE',
      }}
      data-testid="tutor-insight-card"
    >
      <div className="p-5 md:p-6 flex items-start gap-3">
        <div
          className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0 shadow-sm"
          style={{ background: '#FFFFFF', color: 'var(--mf-brand)' }}
        >
          <Wand2 className="w-5 h-5" strokeWidth={1.75} />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-[11px] font-semibold uppercase tracking-widest" style={{ color: 'var(--mf-brand)' }}>
            <span>Insight do preceptor</span>
          </p>
          <p
            className="mt-1.5 text-[15px] text-slate-800 leading-relaxed"
            data-testid="tutor-insight-text"
          >
            <span>{noticed.text}</span>
          </p>
          {noticed.hint && (
            <p className="mt-1 text-[12.5px] text-slate-500 leading-relaxed">
              <span>{noticed.hint}</span>
            </p>
          )}
        </div>
      </div>
    </div>
  );
};


// ═══════════════════════════════════════════════════════════════
// Substitui a antiga home cheia de "chat vazio + chips genéricos" por um
// layout de produto premium: contexto primeiro (o Preceptor JÁ analisou),
// recomendação única e específica, momento cognitivo lateral, chat
// discreto com ações orientadas a resultado, e prova de evolução (domínio).
// Toda a lógica de wizards, plano, devolutiva e MasteryMap segue intacta.
// ═══════════════════════════════════════════════════════════════

const HOME_MISSIONS = [
  { key: 'review',   Icon: Target,       title: 'Melhorar meu pior tema',       prompt: 'Melhorar meu pior tema' },
  { key: 'memorize', Icon: Brain,        title: 'Memorizar um assunto',         prompt: 'Quero memorizar um assunto: ' },
  { key: 'exam',     Icon: BookOpen,     title: 'Preparar prova próxima',       prompt: null }, // abre wizard
  { key: 'quick',    Icon: Zap,          title: 'Estudar por 15 minutos',       prompt: 'Estudo rápido de 15 minutos' },
  { key: 'perf',     Icon: TrendingUp,   title: 'Ver onde estou perdendo pontos', route: '/dashboard' },
];

// ── Recomendação principal (esquerda superior) ─────────────
const RecommendationCard = ({ home, loading, error, onStart, onRetry }) => {
  if (loading) {
    return (
      <div className="mf-card p-6 md:p-7 min-h-[220px] flex items-center justify-center" data-testid="tutor-recommendation-card">
        <Loader2 className="w-5 h-5 animate-spin" style={{ color: 'var(--mf-brand)' }} />
      </div>
    );
  }
  if (error) {
    return (
      <div className="mf-card p-6 md:p-7" data-testid="tutor-recommendation-card">
        <p className="eyebrow" style={{ color: 'var(--mf-care)' }}><span>Recomendação do preceptor</span></p>
        <p className="mt-2 text-[15px] text-zinc-800">
          <span>Não consegui carregar a recomendação de hoje.</span>
        </p>
        <button
          type="button"
          onClick={onRetry}
          className="mt-3 inline-flex items-center gap-1.5 text-[13px] font-medium"
          style={{ color: 'var(--mf-brand)' }}
        >
          <RefreshCw className="w-3.5 h-3.5" /> <span>Tentar de novo</span>
        </button>
      </div>
    );
  }
  const rec = home?.recommendation;
  if (!rec) {
    return (
      <div className="mf-card p-6 md:p-7" data-testid="tutor-recommendation-card">
        <p className="text-[11px] font-semibold uppercase tracking-widest text-slate-500">
          <span>Recomendação do preceptor</span>
        </p>
        <p className="mt-2 text-[17px] font-semibold text-slate-900 tracking-tight">
          <span>Ainda estou aprendendo sua rotina.</span>
        </p>
        <p className="mt-2 text-[13.5px] text-slate-600 leading-relaxed max-w-md">
          <span>Faça o primeiro check-in ou uma sessão para eu calibrar a melhor próxima ação para você.</span>
        </p>
      </div>
    );
  }

  const durationMin = rec.duration_min || rec.duration_actual_min || null;
  const reason = rec.why_now || rec.subtitle || rec.reasoning || '';

  return (
    <div
      className="relative overflow-hidden rounded-3xl p-6 md:p-8 text-white"
      data-testid="tutor-recommendation-card"
      style={{
        background: '#1E3B32',
        boxShadow: '0 10px 40px -12px rgba(30,59,50,0.45)',
        minHeight: 260,
      }}
    >
      {/* Halo decorativo à direita */}
      <div
        className="pointer-events-none absolute -right-12 -top-12 w-72 h-72 rounded-full opacity-40"
        style={{ background: 'radial-gradient(circle, rgba(109,154,130,0.5) 0%, transparent 70%)' }}
      />
      <Brain
        className="pointer-events-none absolute right-4 md:right-8 top-1/2 -translate-y-1/2 hidden sm:block text-white/[0.08]"
        style={{ width: 180, height: 180 }}
        strokeWidth={1.2}
      />

      <div className="relative z-10 max-w-lg">
        <div
          className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full mb-4"
          style={{ background: '#39574D', border: '1px solid #55766A' }}
        >
          <Sparkles className="w-3 h-3" style={{ color: '#D5E8DE' }} strokeWidth={2.4} />
          <p
            className="text-[10.5px] font-bold uppercase tracking-[0.14em]"
            style={{ color: '#D5E8DE' }}
          >
            <span>Missão sugerida pelo Preceptor</span>
          </p>
        </div>

        <h2
          className="font-bold tracking-tight leading-[1.08]"
          style={{ fontSize: 'clamp(26px, 3.4vw, 38px)', letterSpacing: '-0.02em' }}
          data-testid="tutor-recommendation-title"
        >
          <span>{rec.title || rec.action_label || 'Sessão guiada'}</span>
        </h2>

        {reason && (
          <p
            className="mt-4 text-[14px] leading-relaxed max-w-md"
            style={{ color: 'rgba(226,232,240,0.78)' }}
            data-testid="tutor-recommendation-reason"
          >
            <span>{reason}</span>
          </p>
        )}

        <div className="mt-6 flex items-center gap-6 flex-wrap">
          {durationMin && (
            <div className="flex items-center gap-2.5">
              <div
                className="w-9 h-9 rounded-lg flex items-center justify-center"
                style={{ background: '#39574D', color: '#D5E8DE' }}
              >
                <Clock className="w-4 h-4" strokeWidth={2} />
              </div>
              <div className="leading-tight">
                <p className="text-[14.5px] font-bold text-white"><span>{durationMin} min</span></p>
                <p className="text-[11px]" style={{ color: 'rgba(148,163,184,0.9)' }}>
                  <span>tempo estimado</span>
                </p>
              </div>
            </div>
          )}
        </div>

        <button
          type="button"
          onClick={() => onStart(rec)}
          data-testid="tutor-recommendation-start"
          className="mt-7 inline-flex items-center gap-2 text-[14.5px] font-bold px-6 py-3 rounded-xl transition-all hover:-translate-y-0.5 hover:brightness-110"
          style={{
            background: '#C45B45',
            color: 'white',
            boxShadow: '0 10px 30px -8px rgba(196,91,69,0.42)',
          }}
        >
          <Play className="w-4 h-4" fill="currentColor" />
          <span>Começar agora</span>
        </button>
      </div>
    </div>
  );
};

// ── Momento cognitivo (direita superior) ──────────────────
// Só mostra métricas quando existe check-in real. Se não, exibe estado
// "Indisponível" com CTA — nunca inventa números para o aluno.
const wordFromScore = (s) => {
  if (s == null) return 'Indisponível';
  if (s >= 70) return 'Alta';
  if (s >= 55) return 'Boa';
  if (s >= 40) return 'Moderada';
  if (s >= 25) return 'Baixa';
  return 'Muito baixa';
};

const MomentMetric = ({ Icon, label, sub, score, sources, tone = 'brand', dim = false }) => {
  const toneMap = {
    success:   { fg: 'var(--mf-success)',   soft: 'var(--mf-success-soft)' },
    attention: { fg: 'var(--mf-attention)', soft: 'var(--mf-attention-soft)' },
    care:      { fg: 'var(--mf-care)',      soft: 'var(--mf-care-soft)' },
    brand:     { fg: 'var(--mf-brand)',     soft: 'var(--mf-brand-soft)' },
  };
  const t = toneMap[tone] || toneMap.brand;
  const pct = typeof score === 'number' ? Math.max(0, Math.min(100, Math.round(score))) : null;
  return (
    <div data-dim={dim ? 'true' : 'false'}>
      <div className="flex items-center gap-3">
        <div
          className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0"
          style={{ background: t.soft, color: t.fg }}
        >
          <Icon className="w-5 h-5" strokeWidth={1.75} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-baseline justify-between gap-2">
            <p className="text-[14px] font-semibold text-slate-900 leading-tight">
              <span>{label}</span>
            </p>
            {pct != null ? (
              <p className="tabular-nums leading-none">
                <span className="text-[15.5px] font-bold text-slate-900">{pct}</span>
                <span className="text-[11.5px] text-slate-400 font-medium">/100</span>
              </p>
            ) : (
              <span className="text-[12px] text-slate-400">—</span>
            )}
          </div>
          <p className="text-[12px] text-slate-500 mt-0.5"><span>{sub}</span></p>
          <div className="mt-2 h-[6px] rounded-full bg-slate-100 overflow-hidden">
            <div
              className="h-full rounded-full transition-all duration-500"
              style={{ width: `${pct ?? 0}%`, background: t.fg }}
            />
          </div>
          {sources && sources.length > 0 && (
            <p className="mt-1.5 text-[10.5px] text-slate-400"><span>{sources.join(' · ')}</span></p>
          )}
        </div>
      </div>
    </div>
  );
};

const MomentCard = ({ home, iea, loading, onCheckin }) => {
  // Fonte de verdade: só considera métricas se houver check-in de fato.
  const stats = home?.stats || {};
  const hasCheckin = (stats.checkins_total ?? 0) > 0;
  const hasSession = (stats.pomodoros_completed ?? 0) > 0;
  const hasRealData = hasCheckin || hasSession;

  if (loading) {
    return (
      <div className="mf-card p-5 md:p-6 min-h-[220px] flex items-center justify-center" data-testid="tutor-moment-card">
        <Loader2 className="w-4 h-4 animate-spin text-slate-400" />
      </div>
    );
  }

  // Sem dados → um estado único, honesto, com CTA
  if (!hasRealData) {
    return (
      <div className="mf-card p-5 md:p-6" data-testid="tutor-moment-card" data-state="empty">
        <p className="text-[11px] font-semibold uppercase tracking-widest text-slate-500">
          <span>Seu momento</span>
        </p>
        <div className="mt-4 flex items-start gap-3">
          <div
            className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0"
            style={{ background: 'var(--mf-brand-soft)', color: 'var(--mf-brand)' }}
          >
            <Sparkles className="w-5 h-5" strokeWidth={1.75} />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-[14px] font-semibold text-slate-900 leading-snug">
              <span>Ainda não tenho leitura sua de hoje</span>
            </p>
            <p className="mt-1.5 text-[12.5px] text-slate-500 leading-relaxed">
              <span>
                Faça um check-in rápido para registrar sua energia e foco antes da próxima sugestão.
              </span>
            </p>
            <button
              type="button"
              data-testid="tutor-moment-checkin-cta"
              onClick={onCheckin}
              className="mt-3 inline-flex items-center gap-1.5 text-[13px] font-semibold"
              style={{ color: 'var(--mf-brand)' }}
            >
              <span>Fazer check-in agora</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Com dados: métricas com palavra + fontes visíveis
  const byKey = Object.fromEntries((iea?.pillars || []).map((p) => [p.key, p.score]));
  const energia = byKey.saude_fisica ?? byKey.bem_estar ?? null;
  const foco    = byKey.estudos ?? null;
  const retencao = iea?.iea ?? null;

  // Cada pilar tem base própria — só marca a fonte se houver dado real dela
  const sonoOk    = hasCheckin;
  const ritmoOk   = hasSession;
  const missoesOk = (stats.days_active ?? 0) > 0;
  const eSources = [sonoOk && '✓ Sono', missoesOk && '✓ Missões'].filter(Boolean);
  const fSources = [ritmoOk && '✓ Pomodoros', missoesOk && '✓ Missões'].filter(Boolean);
  const rSources = [sonoOk && '✓ Check-ins', ritmoOk && '✓ Ritmo recente'].filter(Boolean);

  const readiness = (() => {
    const avg = ((energia ?? 0) + (foco ?? 0) + (retencao ?? 0)) / 3;
    if (avg >= 70) return { text: 'Você está pronto para uma sessão profunda de estudo.', tone: 'success' };
    if (avg >= 45) return { text: 'Bom momento para uma sessão de 25–30 min.', tone: 'brand' };
    if (avg >= 25) return { text: 'Prefira uma sessão curta e leve agora.', tone: 'attention' };
    return { text: 'Priorize descanso — retome depois com energia.', tone: 'care' };
  })();

  return (
    <div className="mf-card p-6" data-testid="tutor-moment-card" data-state="ready">
      <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
        <span>Seu momento</span>
      </p>
      <div className="mt-5 space-y-5">
        <MomentMetric
          Icon={Battery}
          label="Energia"
          sub={wordFromScore(energia)}
          score={energia}
          sources={eSources}
          tone={energia == null ? 'brand' : energia >= 60 ? 'success' : energia >= 40 ? 'brand' : 'attention'}
          dim={energia == null}
        />
        <MomentMetric
          Icon={Target}
          label="Foco"
          sub={wordFromScore(foco)}
          score={foco}
          sources={fSources}
          tone={foco == null ? 'brand' : foco >= 60 ? 'success' : foco >= 40 ? 'attention' : 'attention'}
          dim={foco == null}
        />
        <MomentMetric
          Icon={Brain}
          label="Retenção prevista"
          sub={wordFromScore(retencao)}
          score={retencao}
          sources={rSources}
          tone={retencao == null ? 'brand' : retencao >= 60 ? 'success' : retencao >= 40 ? 'brand' : 'attention'}
          dim={retencao == null}
        />
      </div>
      {readiness && (
        <div
          className="mt-5 p-3.5 rounded-xl flex items-start gap-2"
          style={{
            background:
              readiness.tone === 'success' ? 'var(--mf-success-soft)' :
              readiness.tone === 'attention' ? 'var(--mf-attention-soft)' :
              readiness.tone === 'care' ? 'var(--mf-care-soft)' :
              'var(--mf-brand-soft)',
          }}
        >
          <Sparkles
            className="w-3.5 h-3.5 mt-0.5 shrink-0"
            style={{
              color:
                readiness.tone === 'success' ? 'var(--mf-success)' :
                readiness.tone === 'attention' ? 'var(--mf-attention)' :
                readiness.tone === 'care' ? 'var(--mf-care)' :
                'var(--mf-brand)',
            }}
          />
          <p
            className="text-[12.5px] leading-snug"
            style={{
              color:
                readiness.tone === 'success' ? '#065F46' :
                readiness.tone === 'attention' ? '#78350F' :
                readiness.tone === 'care' ? '#7A2E1B' :
                '#4C3AC2',
            }}
            data-testid="tutor-moment-readiness"
          >
            <span>{readiness.text}</span>
          </p>
        </div>
      )}
    </div>
  );
};

// ── Chat compacto (ferramenta, não protagonista) ─────────
const ConverseCard = ({ text, setText, onSubmit, onMissionSelect, onAttach, onCamera, onVoice }) => {
  return (
    <div className="mf-card p-4 md:p-5" data-testid="tutor-converse-card">
      <div className="flex items-center justify-between gap-3 mb-3">
        <div className="min-w-0">
          <p className="text-[11px] font-semibold uppercase tracking-widest text-slate-500">
            <span>Converse com o preceptor</span>
          </p>
        </div>
        <div className="flex items-center gap-0.5 shrink-0">
          <button
            type="button"
            data-testid="tutor-hero-attach"
            onClick={onAttach}
            className="p-1.5 rounded-md text-slate-400 hover:text-slate-700 hover:bg-slate-50 transition-colors"
            title="Anexar PDF, imagem ou documento"
          >
            <Paperclip className="w-3.5 h-3.5" />
          </button>
          <button
            type="button"
            data-testid="tutor-hero-camera"
            onClick={onCamera}
            className="p-1.5 rounded-md text-slate-400 hover:text-slate-700 hover:bg-slate-50 transition-colors"
            title="Fotografar página"
          >
            <Camera className="w-3.5 h-3.5" />
          </button>
          <button
            type="button"
            data-testid="tutor-hero-voice"
            onClick={onVoice}
            className="p-1.5 rounded-md text-slate-400 hover:text-slate-700 hover:bg-slate-50 transition-colors"
            title="Falar por voz"
          >
            <Mic className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
      <div className="relative">
        <input
          type="text"
          value={text}
          data-testid="tutor-hero-input"
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              onSubmit();
            }
          }}
          placeholder="Digite uma dúvida ou tema…"
          className="w-full pl-3.5 pr-24 py-2.5 rounded-lg text-[14px] bg-white hairline focus:outline-none focus:ring-2 focus:ring-brand/40 placeholder:text-slate-400"
        />
        <button
          type="button"
          data-testid="tutor-hero-submit"
          onClick={onSubmit}
          className="absolute right-1 top-1 bottom-1 px-3 rounded-md text-[13px] font-semibold text-white inline-flex items-center gap-1.5 transition-colors"
          style={{ background: 'var(--mf-brand)' }}
        >
          <Send className="w-3.5 h-3.5" />
          <span>Enviar</span>
        </button>
      </div>
      <div className="mt-3 flex flex-wrap gap-1.5" data-testid="tutor-mission-grid">
        {HOME_MISSIONS.map((m) => (
          <button
            key={m.key}
            type="button"
            data-testid={`tutor-mission-${m.key}`}
            onClick={() => onMissionSelect(m)}
            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[12px] text-slate-700 bg-slate-50 hover:bg-slate-100 border border-transparent hover:border-slate-200 transition-colors focus:outline-none focus:ring-2 focus:ring-brand/40"
          >
            <m.Icon
              strokeWidth={2}
              className="w-3 h-3"
              style={{ color: 'var(--mf-brand)' }}
            />
            <span>{m.title}</span>
          </button>
        ))}
      </div>
    </div>
  );
};

// ── Evolução do Domínio (barras planas com gargalo) ───────
const DomainEvolutionCard = ({ loading }) => {
  const [data, setData] = useState(null);
  const [innerLoading, setInnerLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const { data } = await api.get('/tutor/mastery-map');
        if (alive) setData(data);
      } catch { if (alive) setData({ empty: true }); }
      finally { if (alive) setInnerLoading(false); }
    })();
    return () => { alive = false; };
  }, []);

  const busy = loading || innerLoading;
  const disciplines = (data?.disciplines || []).slice(0, 5);

  // Encontra o principal gargalo (menor score)
  const gargalo = disciplines
    .filter((d) => typeof d.score === 'number')
    .sort((a, b) => a.score - b.score)[0];

  const barColor = (score) => {
    if (score == null) return '#CBD5E1';
    if (score >= 0.70) return 'var(--mf-success)';
    if (score >= 0.50) return 'var(--mf-attention)';
    return 'var(--mf-care)';
  };

  return (
    <div className="mf-card p-5 md:p-6" data-testid="tutor-domain-card">
      <div className="flex items-center gap-1.5 mb-4">
        <p className="text-[11px] font-semibold uppercase tracking-widest text-slate-500">
          <span>Evolução do domínio</span>
        </p>
      </div>

      {busy ? (
        <div className="py-8 flex justify-center">
          <Loader2 className="w-4 h-4 animate-spin text-slate-400" />
        </div>
      ) : data?.empty || disciplines.length === 0 ? (
        <div className="py-8 px-2 text-center">
          <div
            className="w-11 h-11 mx-auto mb-3 rounded-2xl flex items-center justify-center"
            style={{ background: 'var(--mf-brand-soft)', color: 'var(--mf-brand)' }}
          >
            <BarChart3 className="w-5 h-5" strokeWidth={1.75} />
          </div>
          <p className="text-[14px] font-semibold text-slate-900">
            <span>Mapa de domínio em construção</span>
          </p>
          <p className="mt-1.5 text-[12.5px] text-slate-500 max-w-sm mx-auto leading-relaxed">
            <span>Converse com o preceptor ou resolva sua primeira questão para iniciar sua análise personalizada por disciplina.</span>
          </p>
        </div>
      ) : (
        <>
          <div className="space-y-3.5">
            {disciplines.map((d) => {
              const pct = d.score == null ? 0 : Math.round(d.score * 100);
              return (
                <div key={d.discipline} className="flex items-center gap-3" data-testid={`tutor-domain-${d.discipline}`}>
                  <p className="text-[13px] text-slate-700 capitalize w-32 shrink-0 truncate">
                    <span>{d.discipline}</span>
                  </p>
                  <div className="flex-1 h-2 rounded-full bg-slate-100 overflow-hidden">
                    <div
                      className="h-full rounded-full transition-all duration-500"
                      style={{ width: `${pct}%`, background: barColor(d.score) }}
                    />
                  </div>
                  <span className="text-[12.5px] font-bold tabular text-slate-800 w-10 text-right shrink-0">
                    <span>{d.score == null ? '—' : `${pct}%`}</span>
                  </span>
                </div>
              );
            })}
          </div>
          {gargalo && gargalo.score < 0.6 && (
            <div
              className="mt-4 p-3 rounded-lg flex items-start gap-2"
              style={{ background: 'var(--mf-care-soft)' }}
              data-testid="tutor-domain-gargalo"
            >
              <Target
                className="w-3.5 h-3.5 mt-0.5 shrink-0"
                style={{ color: 'var(--mf-care)' }}
                strokeWidth={2.2}
              />
              <p className="text-[12.5px] leading-snug" style={{ color: '#7A2E1B' }}>
                <span>Principal gargalo: </span>
                <strong className="font-semibold capitalize">{gargalo.discipline}</strong>
                <span>. Este é um bom ponto para orientar sua próxima revisão.</span>
              </p>
            </div>
          )}
        </>
      )}
    </div>
  );
};

// ── Hexagon radar (SVG) ───────────────────────────────────
const HexagonRadar = ({ items = [] }) => {
  const size = 260;
  const cx = size / 2;
  const cy = size / 2;
  const radius = 92;
  const source = items.length >= 3 ? items : [
    ...items,
    ...Array.from({ length: Math.max(0, 6 - items.length) }).map(() => ({ discipline: '—', score: null })),
  ];
  const n = Math.min(6, Math.max(3, source.length));
  const points = source.slice(0, n).map((item, i) => {
    const angle = (Math.PI * 2 * i) / n - Math.PI / 2;
    const score = typeof item.score === 'number' ? item.score : 0;
    const r = radius * Math.max(0.08, score);
    return {
      label: item.discipline || '—',
      angle,
      score,
      dx: cx + Math.cos(angle) * r,
      dy: cy + Math.sin(angle) * r,
      px: cx + Math.cos(angle) * radius,
      py: cy + Math.sin(angle) * radius,
      gx: cx + Math.cos(angle) * (radius + 24),
      gy: cy + Math.sin(angle) * (radius + 24),
    };
  });

  const dataPath = points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.dx} ${p.dy}`).join(' ') + ' Z';
  const rings = [0.25, 0.5, 0.75, 1].map((ratio) =>
    points.map((p) => {
      const r = radius * ratio;
      const x = cx + Math.cos(p.angle) * r;
      const y = cy + Math.sin(p.angle) * r;
      return `${x},${y}`;
    }).join(' ')
  );

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="overflow-visible" data-testid="tutor-domain-hexagon">
      {rings.map((r, i) => (
        <polygon key={i} points={r} fill="none" stroke="#E2E8F0" strokeWidth={1} />
      ))}
      {points.map((p, i) => (
        <line key={`ax-${i}`} x1={cx} y1={cy} x2={p.px} y2={p.py} stroke="#E2E8F0" strokeWidth={1} />
      ))}
      <path
        d={dataPath}
        fill="rgba(108,92,231,0.16)"
        stroke="#6C5CE7"
        strokeWidth={2}
        strokeLinejoin="round"
      />
      {points.map((p, i) => (
        <circle key={`d-${i}`} cx={p.dx} cy={p.dy} r={3.5} fill="#6C5CE7" />
      ))}
      {points.map((p, i) => {
        const pct = Math.round(p.score * 100);
        const anchor = Math.abs(p.gx - cx) < 6 ? 'middle' : (p.gx > cx ? 'start' : 'end');
        return (
          <g key={`t-${i}`}>
            <text x={p.gx} y={p.gy - 4} fill="#334155" fontSize={11.5} fontWeight={600}
                  textAnchor={anchor} style={{ textTransform: 'capitalize' }}>
              {p.label}
            </text>
            <text x={p.gx} y={p.gy + 10} fill="#94A3B8" fontSize={11} fontWeight={500} textAnchor={anchor}>
              {p.score ? `${pct}%` : '—'}
            </text>
          </g>
        );
      })}
    </svg>
  );
};

// ── Mapa de domínio unificado (hexágono + lista compacta + insights) ─────
const DomainMapCard = () => {
  const [data, setData] = useState(null);
  const [innerLoading, setInnerLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const { data } = await api.get('/tutor/mastery-map');
        if (alive) setData(data);
      } catch { if (alive) setData({ empty: true }); }
      finally { if (alive) setInnerLoading(false); }
    })();
    return () => { alive = false; };
  }, []);

  if (innerLoading) {
    return (
      <div className="mf-card p-6 flex items-center justify-center min-h-[280px]" data-testid="tutor-domain-map-card">
        <Loader2 className="w-4 h-4 animate-spin text-slate-400" />
      </div>
    );
  }

  const disciplines = (data?.disciplines || []).slice(0, 6);
  const listDisciplines = disciplines.slice(0, 5);
  const withScore = disciplines.filter((d) => typeof d.score === 'number');
  const gargalo = [...withScore].sort((a, b) => a.score - b.score)[0];
  const topper = [...withScore].sort((a, b) => b.score - a.score)[0];

  const barColor = (score) => {
    if (score == null) return '#CBD5E1';
    if (score >= 0.70) return 'var(--mf-success)';
    if (score >= 0.50) return 'var(--mf-attention)';
    return 'var(--mf-care)';
  };

  if (data?.empty || disciplines.length === 0) {
    return (
      <div className="mf-card p-6 md:p-7" data-testid="tutor-domain-map-card">
        <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500 mb-4">
          <span>Seu mapa de domínio</span>
        </p>
        <div className="py-6 text-center">
          <div
            className="w-12 h-12 mx-auto mb-3 rounded-2xl flex items-center justify-center"
            style={{ background: 'var(--mf-brand-soft)', color: 'var(--mf-brand)' }}
          >
            <BarChart3 className="w-5 h-5" strokeWidth={1.75} />
          </div>
          <p className="text-[14px] font-semibold text-slate-900">
            <span>Mapa de domínio em construção</span>
          </p>
          <p className="mt-1.5 text-[12.5px] text-slate-500 max-w-md mx-auto leading-relaxed">
            <span>Converse com o preceptor ou resolva sua primeira questão para iniciar sua análise personalizada por disciplina.</span>
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="mf-card p-6 md:p-7" data-testid="tutor-domain-map-card">
      <div className="flex items-start justify-between gap-3 mb-6">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
            <span>Seu mapa de domínio</span>
          </p>
          <h3 className="mt-1 text-[17px] md:text-[18px] font-bold text-slate-900 tracking-tight">
            <span>Onde você está agora</span>
          </h3>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-[minmax(0,0.95fr)_minmax(0,1.05fr)] gap-6 md:gap-8 items-center">
        <div className="flex items-center justify-center">
          <HexagonRadar items={disciplines.slice(0, 6)} />
        </div>
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500 mb-3">
            <span>Suas disciplinas</span>
          </p>
          <div className="space-y-3.5" data-testid="tutor-domain-list">
            {listDisciplines.map((d) => {
              const pct = d.score == null ? 0 : Math.round(d.score * 100);
              return (
                <div key={d.discipline} className="flex items-center gap-3" data-testid={`tutor-domain-${d.discipline}`}>
                  <p className="text-[13px] text-slate-700 capitalize w-28 shrink-0 truncate">
                    <span>{d.discipline}</span>
                  </p>
                  <div className="flex-1 h-2 rounded-full bg-slate-100 overflow-hidden">
                    <div
                      className="h-full rounded-full transition-all duration-500"
                      style={{ width: `${pct}%`, background: barColor(d.score) }}
                    />
                  </div>
                  <span className="text-[13px] font-bold tabular-nums text-slate-800 w-11 text-right shrink-0">
                    <span>{d.score == null ? '—' : `${pct}%`}</span>
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {(topper || (gargalo && gargalo.score < 0.6)) && (
        <div className="mt-6 grid grid-cols-1 md:grid-cols-2 gap-3">
          {topper && topper.score >= 0.5 && (
            <div
              className="flex items-start gap-2.5 p-3.5 rounded-xl"
              style={{ background: 'var(--mf-success-soft)' }}
              data-testid="tutor-domain-evolucao"
            >
              <TrendingUp
                className="w-4 h-4 mt-0.5 shrink-0"
                style={{ color: 'var(--mf-success)' }}
                strokeWidth={2}
              />
              <div className="min-w-0">
                <p className="text-[11px] font-bold uppercase tracking-wider" style={{ color: '#065F46' }}>
                  <span>Em evolução</span>
                </p>
                <p className="mt-0.5 text-[12.5px] leading-snug" style={{ color: '#065F46' }}>
                  <strong className="font-semibold capitalize">{topper.discipline}</strong>
                  <span> é a sua área mais consolidada — mantenha o ritmo.</span>
                </p>
              </div>
            </div>
          )}
          {gargalo && gargalo.score < 0.6 && (
            <div
              className="flex items-start gap-2.5 p-3.5 rounded-xl"
              style={{ background: 'var(--mf-care-soft)' }}
              data-testid="tutor-domain-gargalo"
            >
              <Target
                className="w-4 h-4 mt-0.5 shrink-0"
                style={{ color: 'var(--mf-care)' }}
                strokeWidth={2.2}
              />
              <div className="min-w-0">
                <p className="text-[11px] font-bold uppercase tracking-wider" style={{ color: '#7A2E1B' }}>
                  <span>Ponto de atenção</span>
                </p>
                <p className="mt-0.5 text-[12.5px] leading-snug" style={{ color: '#7A2E1B' }}>
                  <strong className="font-semibold capitalize">{gargalo.discipline}</strong>
                  <span> pede mais atenção nos próximos estudos.</span>
                </p>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};



// ─── Root ─────────────────────────────────────────────────────
const Tutor = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const { user } = useAuth();
  const firstName = (user?.name || '').trim().split(' ')[0] || '';
  const [step, setStep] = useState('home');   // home | wizard | plan | postexam | due
  const [selectedMode, setSelectedMode] = useState(null);
  const [plan, setPlan] = useState(null);
  const [loadingPlan, setLoadingPlan] = useState(false);
  const [planError, setPlanError] = useState(null);
  const [dueItems, setDueItems] = useState([]);
  const [dueCount, setDueCount] = useState(0);
  const [loadingDue, setLoadingDue] = useState(false);
  const [showMoreModes, setShowMoreModes] = useState(false);
  const [heroText, setHeroText] = useState('');
  const [mentorState, setMentorState] = useState(null);

  // ── Dados do Preceptor (home/today) + Ritmo (iea) para o layout novo ──
  const [homeToday, setHomeToday] = useState(null);
  const [homeLoading, setHomeLoading] = useState(true);
  const [homeError, setHomeError] = useState(null);
  const [ieaData, setIeaData] = useState(null);
  const [ieaLoading, setIeaLoading] = useState(true);

  const loadHome = async () => {
    setHomeLoading(true); setHomeError(null);
    try {
      const { data } = await api.get('/home/today');
      setHomeToday(data);
    } catch (e) {
      setHomeError(formatDetail(e?.response?.data?.detail) || 'Não foi possível carregar.');
    } finally { setHomeLoading(false); }
  };

  useEffect(() => {
    loadHome();
    (async () => {
      try {
        const { data } = await api.get('/iea');
        setIeaData(data);
      } catch { /* silent */ }
      finally { setIeaLoading(false); }
    })();
  }, []);

  // Atualiza o mentor state a cada entrada na Home (streak, dias, memória)
  useEffect(() => {
    const s = touchMentorDay();
    setMentorState(s || readMentorState());
  }, []);

  // Carrega contagem de vencidas ao entrar
  useEffect(() => {
    (async () => {
      try {
        const { data } = await api.get('/learning/me/due?limit=20');
        setDueCount(data.count || 0);
        setDueItems(data.items || []);
      } catch { /* silent */ }
    })();
  }, []);

  // Auto-open modo revisão quando vier com ?mode=due
  useEffect(() => {
    const params = new URLSearchParams(location.search);
    if (params.get('mode') === 'due' && dueItems.length > 0 && step === 'home') {
      setStep('due');
    }
  }, [location.search, dueItems, step]);

  const start = async (payload) => {
    setLoadingPlan(true); setPlanError(null);
    try {
      // Modo clinical_case — plano local (1 slot, sem passar pelo /tutor/plan).
      // Isso deixa o fluxo com apenas 3 passos: caso · decisão · feedback.
      if (payload.mode === 'clinical_case') {
        const localPlan = {
          mode: 'clinical_case',
          title: `Caso clínico — ${payload.discipline}`,
          subtitle: payload.topic,
          total_duration_min: 3,
          slots: [{
            id: `slot_${Date.now()}`,
            kind: 'clinical_case',
            discipline: payload.discipline,
            topic: payload.topic,
            subtopic: null,
            period: null,
            variant: 'default',
            duration_min: 3,
            label: payload.topic,
            phase: 'caso clínico',
          }],
        };
        setPlan(localPlan);
        setStep('plan');
        return;
      }
      const body = payload.mode === 'guide_me' ? { mode: 'guide_me' } : payload;
      const { data } = await api.post('/tutor/plan', body, { timeout: 30_000 });
      setPlan(data);
      setStep('plan');
    } catch (e) {
      setPlanError(formatDetail(e?.response?.data?.detail) || 'Não foi possível montar o plano.');
    } finally { setLoadingPlan(false); }
  };

  const startDueReview = async () => {
    setLoadingDue(true);
    try {
      const { data } = await api.get('/learning/me/due?limit=20');
      setDueItems(data.items || []);
      setDueCount(data.count || 0);
      if ((data.count || 0) > 0) setStep('due');
    } finally { setLoadingDue(false); }
  };

  const selectMode = (mode) => {
    setSelectedMode(mode);
    if (mode === 'guide_me') {
      start({ mode: 'guide_me' });
      return;
    }
    if (mode === 'post_exam') {
      setStep('postexam');
      return;
    }
    setStep('wizard');
  };

  // ─── Seleção de missão (objetivo, não ferramenta) ────
  // O aluno diz o que quer aprender — o Preceptor decide o formato.
  const selectMission = (m) => {
    // Missão com rota fixa (ex.: analisar desempenho → /dashboard)
    if (m.route) {
      navigate(m.route);
      return;
    }
    // "Tenho prova em breve" / "Preparar prova" → abre o plano de prova
    if (m.key === 'exam') {
      setSelectedMode('exam_tomorrow');
      setStep('wizard');
      return;
    }
    // Estudo rápido — abre o wizard de revisão rápida
    if (m.key === 'quick') {
      setSelectedMode('quick_review');
      setStep('wizard');
      return;
    }
    // Demais missões → leva o aluno pra caixa universal já preparada
    const params = new URLSearchParams();
    if (m.prompt) params.set('prompt', m.prompt);
    navigate(`/tutor/aprender${params.toString() ? `?${params.toString()}` : ''}`);
  };

  // Executar a recomendação do Preceptor: se tiver action_route, navega;
  // senão, cai no fluxo "guide_me" (o motor decide).
  const startRecommendation = (rec) => {
    if (!rec) return;
    if (rec.action_route) {
      navigate(rec.action_route);
      return;
    }
    if (rec.action === 'checkin') { navigate('/checkin'); return; }
    if (rec.action === 'pomodoro' || rec.kind === 'study') {
      const t = rec.topic || rec.subject || rec.title || '';
      navigate(t ? `/tutor/aprender?q=${encodeURIComponent(t)}` : '/tutor/aprender');
      return;
    }
    // Fallback: usa o motor de plano
    start({ mode: 'guide_me' });
  };

  const submitHero = (rawText) => {
    const t = (rawText ?? heroText).trim();
    if (!t) {
      navigate('/tutor/aprender');
      return;
    }
    navigate(`/tutor/aprender?q=${encodeURIComponent(t)}`);
  };

  const backToHome = () => {
    setStep('home'); setSelectedMode(null); setPlan(null); setPlanError(null);
  };

  return (
    <Shell>
      <div className={`mx-auto px-5 md:px-8 pt-6 md:pt-8 ${step === 'home' ? 'max-w-6xl' : 'max-w-4xl'}`} data-testid="tutor-root">
        {step === 'home' && (
          <>
            {/* ─── Hero enxuto: contexto primeiro, não pergunta ─── */}
            <header className="mb-6 md:mb-8" data-testid="tutor-hero-header">
              <h1
                className="font-bold text-slate-900 tracking-tight leading-[1.05]"
                style={{ fontSize: 'clamp(30px, 3.8vw, 40px)', letterSpacing: '-0.025em' }}
              >
                <span>Olá{firstName ? `, ${firstName}` : ''} 👋</span>
              </h1>
              <p className="mt-2 text-[14.5px] text-slate-600 max-w-2xl leading-relaxed">
                <span>Seu Preceptor analisou sua evolução de hoje e preparou o melhor plano para você.</span>
              </p>
              {mentorState?.last_topic && (
                <p className="mt-3 text-[13px] text-slate-500">
                  <span>Da última vez você estudou </span>
                  <strong className="text-slate-800 font-medium">{mentorState.last_topic}</strong>
                  <span> — </span>
                  <button
                    type="button"
                    data-testid="today-continue-last"
                    onClick={() => navigate(`/tutor/aprender?q=${encodeURIComponent(mentorState.last_topic)}&resume=1`)}
                    className="underline underline-offset-2 font-medium"
                    style={{ color: 'var(--mf-brand)' }}
                  >
                    <span>continuar de onde paramos?</span>
                  </button>
                </p>
              )}
            </header>

            {/* ─── Grid superior: Recomendação (2/3) + Momento (1/3) ─── */}
            <div className="grid grid-cols-1 lg:grid-cols-[1fr_340px] gap-4 md:gap-5 mb-4 md:mb-5">
              <RecommendationCard
                home={homeToday}
                loading={homeLoading}
                error={homeError}
                onStart={startRecommendation}
                onRetry={loadHome}
              />
              <MomentCard
                home={homeToday}
                iea={ieaData}
                loading={homeLoading || ieaLoading}
                onCheckin={() => navigate('/checkin')}
              />
            </div>

            {/* ─── Insight do Preceptor (só aparece se há padrão real) ─── */}
            <InsightCard noticed={homeToday?.noticed} />

            {/* ─── Chat compacto com missões acionáveis ─── */}
            <div className="mb-4 md:mb-5">
              <ConverseCard
                text={heroText}
                setText={setHeroText}
                onSubmit={() => submitHero()}
                onMissionSelect={selectMission}
                onAttach={() => navigate('/tutor/aprender')}
                onCamera={() => navigate('/tutor/aprender')}
                onVoice={() => navigate('/tutor/aprender')}
              />
              {planError && (
                <p className="mt-3 text-[13px]" style={{ color: 'var(--mf-care)' }}>
                  <span>{planError}</span>
                </p>
              )}
            </div>

            {/* ─── Mapa de domínio unificado (hexágono + lista + insights) ─── */}
            <div className="mb-6">
              <DomainMapCard />
            </div>

            {/* ─── Revisões vencidas (curva de esquecimento) ─── */}
            {dueCount > 0 && (
              <button
                type="button"
                data-testid="tutor-due-badge"
                onClick={startDueReview}
                disabled={loadingDue}
                className="mb-4 w-full mf-card p-4 md:p-5 text-left transition-colors hover:bg-zinc-50 focus:outline-none focus:ring-2 focus:ring-brand/40"
              >
                <div className="flex items-center gap-3">
                  <span
                    className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0"
                    style={{ background: 'var(--mf-care-soft)', color: 'var(--mf-care)' }}
                  >
                    <RefreshCw strokeWidth={1.75} className="w-5 h-5" />
                  </span>
                  <div className="flex-1 min-w-0">
                    <p className="text-[14.5px] font-semibold text-zinc-900 leading-tight">
                      <span>
                        {dueCount === 1
                          ? 'Vamos consolidar 1 tema que você já viu?'
                          : `Vamos consolidar ${dueCount} temas que você já viu?`}
                      </span>
                    </p>
                    <p className="mt-1 text-[12.5px] text-zinc-500 leading-relaxed">
                      <span>É o melhor momento pra fixar o que aprendeu.</span>
                    </p>
                  </div>
                  {loadingDue ? (
                    <Loader2 className="w-4 h-4 animate-spin text-zinc-400 shrink-0" />
                  ) : (
                    <ChevronRight strokeWidth={1.75} className="w-4 h-4 text-zinc-300 shrink-0" />
                  )}
                </div>
              </button>
            )}

            {/* ─── Atalhos secundários ─── */}
            <div className="mb-8 flex flex-wrap items-center gap-x-4 gap-y-2 text-[12.5px]">
              <button
                type="button"
                data-testid="tutor-devolutiva-cta"
                onClick={() => navigate('/tutor/devolutiva')}
                className="text-zinc-500 hover:text-zinc-900 transition-colors underline underline-offset-2"
              >
                <span>Já resolvi uma questão de prova</span>
              </button>
              <span className="text-zinc-300" aria-hidden>·</span>
              <button
                type="button"
                data-testid="tutor-more-modes-toggle"
                onClick={() => setShowMoreModes((v) => !v)}
                className="text-zinc-500 hover:text-zinc-900 transition-colors"
              >
                <span>{showMoreModes ? 'esconder outras formas' : 'ver outras formas de estudar'}</span>
              </button>
            </div>

            {/* Opções avançadas (modos legados) — só pra quem quiser */}
            {showMoreModes && (
              <section className="mb-10">
                <ModeGrid onSelect={selectMode} />
              </section>
            )}
          </>
        )}

        {step === 'wizard' && selectedMode === 'exam_tomorrow' && (
          <ExamTomorrowWizard onCreate={start} onBack={backToHome} loading={loadingPlan} />
        )}
        {step === 'wizard' && selectedMode === 'quick_review' && (
          <QuickReviewWizard onCreate={start} onBack={backToHome} loading={loadingPlan} />
        )}
        {step === 'wizard' && selectedMode === 'diagnostic' && (
          <DiagnosticWizard onCreate={start} onBack={backToHome} loading={loadingPlan} />
        )}
        {step === 'wizard' && selectedMode === 'clinical_case' && (
          <ClinicalCaseWizard onCreate={start} onBack={backToHome} loading={loadingPlan} />
        )}

        {step === 'postexam' && <PostExamFlow onBack={backToHome} />}

        {step === 'due' && dueItems.length > 0 && (
          <DueReviewRunner items={dueItems} onExit={backToHome} />
        )}

        {step === 'plan' && plan && (
          <div>
            <div className="mb-5">
              <p className="eyebrow"><span>{plan.mode.replace('_', ' ')}</span></p>
              <h2 className="mt-1 text-[20px] font-semibold text-zinc-900 tracking-tight"><span>{plan.title}</span></h2>
              <p className="mt-1 text-[13.5px] text-zinc-500"><span>{plan.subtitle}</span></p>
              <div className="mt-3 flex items-center gap-3 text-[12px] text-zinc-500">
                <span className="inline-flex items-center gap-1">
                  <Clock className="w-3.5 h-3.5" /> <span>{plan.total_duration_min} min</span>
                </span>
                <span>·</span>
                <span className="inline-flex items-center gap-1">
                  <Zap className="w-3.5 h-3.5" /> <span>{plan.slots.length} atividades</span>
                </span>
              </div>
            </div>
            <PlanRunner plan={plan} onExit={backToHome} />
          </div>
        )}
      </div>
    </Shell>
  );
};

export default Tutor;
