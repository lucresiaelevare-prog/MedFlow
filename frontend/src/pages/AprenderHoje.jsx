import { useEffect, useRef, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  Loader2, Sparkles, ArrowRight, Mic, Camera, Paperclip, X,
  Wand2, Compass, BookOpen, Target, Brain, Calendar,
  FileText, Image as ImgIcon, MessagesSquare, Zap,
  Play, Clock, TrendingUp,
} from 'lucide-react';
import Shell from '@/components/Shell';
import api, { streamPost } from '@/lib/api';
import { useAuth } from '@/context/AuthContext';

/**
 * Centro de Aprendizagem Inteligente — entrada universal.
 *
 * "No Med Flow, você não aprende sozinho. O Preceptor IA acompanha cada
 * passo da sua evolução, identifica suas dificuldades, adapta sua
 * estratégia de estudo e conduz você até a aprovação."
 */

const EXAMPLE_PROMPTS = [
  'Revisar Ciclo de Krebs',
  'Explique Choque Séptico',
  'Tenho prova de Farmacologia em 15 dias',
  'Gere questões sobre ECG',
  'Faça um mapa mental de Insuficiência Cardíaca',
  'Transforme este PDF em flashcards',
];

// Sugestões de "próximo passo" mostradas após qualquer atividade —
// linguagem de mentor, não de ferramenta.
const NEXT_STEP_TEMPLATES = [
  { key: 'flash', Icon: Brain,
    label: 'Criar 15 flashcards',
    build: (topic) => `Fazer 15 flashcards sobre ${topic}` },
  { key: 'quiz', Icon: Target,
    label: 'Resolver 10 questões',
    build: (topic) => `Gerar 10 questões sobre ${topic}` },
  { key: 'case', Icon: Compass,
    label: 'Ver um caso clínico',
    build: (topic) => `Caso clínico sobre ${topic}` },
];

const MISSION_ICONS = {
  resolver_duvida: MessagesSquare,
  treinar: Target,
  revisar: Zap,
  memorizar: Brain,
  planejar: Calendar,
  conversar: Compass,
};

function formatDetail(d) {
  if (!d) return null;
  if (typeof d === 'string') return d;
  if (Array.isArray(d)) return d.map((e) => e?.msg || JSON.stringify(e)).join(' ');
  if (typeof d === 'object' && typeof d.message === 'string') return d.message;
  return String(d);
}

// Frases robóticas ou vindas do Cloudflare/servidor não aparecem pro aluno.
// Se o texto do erro parecer técnico, substituímos por uma frase de mentor.
function humanizeError(raw, fallback = 'Nossa conversa tropeçou um pouco. Podemos tentar de novo?') {
  if (!raw) return fallback;
  const s = String(raw);
  const looksTechnical = s.length > 220
    || /cloudflare|origin web server|502|gateway|<html|traceback|exception/i.test(s);
  return looksTechnical ? fallback : s;
}

// ─── Extração leve de texto de arquivos ─────────────────────
async function readFileAsText(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(reader.error);
    reader.readAsText(file);
  });
}

// ─── Memória visível (localStorage) — mentor lembra do aluno ─────
// Schema explícito pra migração ao backend (memória oficial do aluno).
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
    return next;
  } catch { return null; }
}

// ─── Voice input (Web Speech API) ────────────────────────────
function useSpeechRecognition() {
  const [supported, setSupported] = useState(false);
  const [listening, setListening] = useState(false);
  const recognizerRef = useRef(null);

  useEffect(() => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    setSupported(!!SR);
  }, []);

  const start = (onResult, onEnd) => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) return;
    const r = new SR();
    r.lang = 'pt-BR';
    r.interimResults = true;
    r.continuous = false;
    r.onresult = (event) => {
      let transcript = '';
      for (let i = 0; i < event.results.length; i++) {
        transcript += event.results[i][0].transcript;
      }
      onResult(transcript);
    };
    r.onend = () => { setListening(false); onEnd?.(); };
    r.onerror = () => { setListening(false); onEnd?.(); };
    r.start();
    recognizerRef.current = r;
    setListening(true);
  };
  const stop = () => {
    try { recognizerRef.current?.stop(); } catch { /* ignore */ }
    setListening(false);
  };
  return { supported, listening, start, stop };
}

// ─── Conversation Card ─────────────────────────────────────
// PRINCÍPIO 2: o Preceptor NUNCA responde direto com conteúdo.
// Primeiro conversa; depois oferece caminhos de estudo.
// Cada opção é uma "sessão focada" da Revisão Completa.
const STUDY_MODES = [
  { key: 'all',      emoji: '⭐', label: 'Revisão Completa',
    hint: 'tudo de uma vez, no ritmo certo', primary: true },
  { key: 'memorize', emoji: '🧠', label: 'Memorizar em 5–8 min',
    hint: 'consolidação, mnemônicos e recuperação ativa' },
  { key: 'explanation', emoji: '📖', label: 'Explicação detalhada',
    hint: 'entender o mecanismo com calma' },
  { key: 'flashcards',  emoji: '🧠', label: 'Flashcards',
    hint: 'fixar com repetição espaçada' },
  { key: 'questions',   emoji: '❓', label: 'Questões',
    hint: 'testar o que você já sabe' },
  { key: 'case',        emoji: '🩺', label: 'Caso clínico',
    hint: 'raciocinar como na prática' },
  { key: 'plan',        emoji: '📅', label: 'Plano de revisão',
    hint: 'te lembro nos próximos dias' },
];

function buildPreceptorGreeting(interp) {
  // Se o LLM já devolveu uma frase pronta, usamos.
  if (interp?.immediate_response && interp.immediate_response.length > 20) {
    return interp.immediate_response;
  }
  const topic = interp?.topic || 'esse tema';
  const disc  = interp?.discipline;
  if (disc) {
    return `Excelente escolha. ${topic} é um dos temas mais importantes de ${disc} e costuma aparecer com frequência nas provas.`;
  }
  return `Ótima escolha. Vamos estudar ${topic} juntos — esse tema costuma render bem em prova.`;
}

const ConversationCard = ({ result, onPickMode, onChat }) => {
  const { interpretation: interp } = result;
  const topic = interp?.topic || '';
  const disc  = interp?.discipline;
  const greeting = buildPreceptorGreeting(interp);

  return (
    <div className="mf-card p-5 md:p-6 space-y-5 animate-fade-in" data-testid="mission-result">
      {/* Fala do Preceptor — cabeça humana, tom acolhedor */}
      <div className="flex items-start gap-3">
        <span
          className="w-9 h-9 rounded-full flex items-center justify-center shrink-0 text-[15px]"
          style={{ background: 'var(--mf-brand-soft)', color: 'var(--mf-brand)' }}
          aria-hidden
        >
          <Compass strokeWidth={1.8} className="w-4.5 h-4.5" />
        </span>
        <div className="flex-1 min-w-0">
          <p className="text-[11px] uppercase tracking-widest text-zinc-400 font-medium">
            <span>Preceptor</span>
          </p>
          <p
            data-testid="preceptor-greeting"
            className="mt-0.5 text-[15px] text-zinc-800 leading-relaxed"
          >
            <span>{greeting}</span>
          </p>
          {topic && topic.length > 3 && (
            <p className="mt-1.5 text-[11.5px] text-zinc-400">
              <span>{topic}{disc ? ` · ${disc}` : ''}</span>
            </p>
          )}
        </div>
      </div>

      <div>
        <p className="text-[13.5px] text-zinc-600 leading-relaxed">
          <span>Como você prefere estudar esse tema?</span>
        </p>

        <div className="mt-3 space-y-2" data-testid="study-modes">
          {STUDY_MODES.map((m) => (
            <button
              key={m.key}
              type="button"
              data-testid={`study-mode-${m.key}`}
              onClick={() => onPickMode(m.key)}
              className={
                m.primary
                  ? 'w-full text-left rounded-xl p-3.5 transition-transform hover:scale-[1.005] focus:outline-none flex items-center gap-3'
                  : 'w-full text-left rounded-xl p-3 hairline bg-white hover:bg-zinc-50 transition-colors focus:outline-none flex items-center gap-3'
              }
              style={m.primary ? {
                background: 'linear-gradient(135deg, var(--mf-brand) 0%, #B15437 100%)',
                color: '#fff',
                boxShadow: '0 6px 20px -10px rgba(220,107,76,.45)',
              } : {}}
            >
              <span className="text-[18px] shrink-0" aria-hidden>{m.emoji}</span>
              <span className="flex-1 min-w-0">
                <span className="block text-[14px] font-semibold leading-tight">
                  <span>{m.label}{m.primary ? ' · Recomendado' : ''}</span>
                </span>
                <span className={`block mt-0.5 text-[12px] leading-relaxed ${m.primary ? 'opacity-90' : 'text-zinc-500'}`}>
                  <span>{m.hint}</span>
                </span>
              </span>
              <ArrowRight className={`w-4 h-4 shrink-0 ${m.primary ? 'opacity-80' : 'text-zinc-300'}`} />
            </button>
          ))}
        </div>
      </div>

      {/* Continuar conversando — porta discreta pro chat */}
      <button
        type="button"
        data-testid="mission-talk"
        onClick={onChat}
        className="w-full text-[12.5px] text-zinc-500 hover:text-zinc-700 inline-flex items-center gap-1.5 justify-center py-1"
      >
        <MessagesSquare className="w-3.5 h-3.5" />
        <span>ou continue conversando comigo</span>
      </button>
    </div>
  );
};

// ─── Full Review result view ────────────────────────────────
// PRINCÍPIO 7: nunca termina em uma única resposta. Ao final,
// o Preceptor sempre conduz o aluno pro próximo passo natural.
const FOCUS_LABELS = {
  all:         'Revisão completa',
  memorize:    'Consolidação inteligente',
  explanation: 'Explicação detalhada',
  flashcards:  'Flashcards',
  questions:   'Questões',
  case:        'Caso clínico',
  plan:        'Plano de revisão',
};

// Define quais seções aparecem para cada modo de estudo escolhido.
// Ordem importa — a seção "principal" sempre vem primeiro.
const FOCUS_SECTIONS = {
  all:         ['summary', 'why', 'explanation', 'bullets', 'high_yield', 'mind_map', 'memory', 'flashcards', 'questions', 'case', 'mistakes', 'exam', 'spaced'],
  memorize:    ['summary', 'why', 'explanation', 'high_yield', 'memory', 'flashcards', 'questions', 'mistakes'],
  explanation: ['summary', 'explanation', 'bullets', 'high_yield'],
  flashcards:  ['summary', 'flashcards'],
  questions:   ['summary', 'questions', 'high_yield'],
  case:        ['summary', 'case', 'mistakes'],
  plan:        ['summary', 'spaced', 'bullets'],
};

const FullReviewView = ({ data, focus = 'all', onBack, onPickAnother, onNextStep }) => {
  const c = data.content || data.review || {};
  const sections = FOCUS_SECTIONS[focus] || FOCUS_SECTIONS.all;
  const has = (k) => sections.includes(k);
  const isFocused = focus !== 'all';

  // Próximos passos automáticos (Princípio 7).
  // Sempre sugere 2 caminhos diferentes do modo atual, na ordem certa.
  const nextOrder = ['explanation', 'flashcards', 'questions', 'case', 'plan'];
  const nextSuggestions = nextOrder.filter((k) => k !== focus).slice(0, 3);
  const pointText = (point) => {
    if (typeof point === 'string') return point;
    return [point?.point, point?.why, point?.trap, point?.memory].filter(Boolean).join(' · ');
  };

  return (
    <div className="mf-card p-5 md:p-6 space-y-6 animate-fade-in" data-testid="full-review-view">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="eyebrow"><span>{FOCUS_LABELS[focus] || 'revisão completa'}</span></p>
          <h2 className="mt-1 text-[22px] font-semibold text-zinc-900 tracking-tight">
            <span>{c.topic || data.topic}</span>
          </h2>
          {c.discipline && (
            <p className="mt-1 text-[12.5px] text-zinc-500 capitalize"><span>{c.discipline}</span></p>
          )}
        </div>
        <button onClick={onBack} className="btn-ghost text-[12px]" data-testid="full-review-back">
          <span>Nova conversa</span>
        </button>
      </div>

      {has('summary') && c.smart_summary?.one_line && (
        <div className="p-4 rounded-xl" style={{ background: 'var(--mf-brand-soft)' }}>
          <p className="eyebrow" style={{ color: 'var(--mf-brand)' }}><span>em uma linha</span></p>
          <p className="mt-1 text-[15px] font-semibold text-zinc-900 leading-snug">
            <span>{c.smart_summary.one_line}</span>
          </p>
        </div>
      )}

      {has('why') && c.why_it_matters && (
        <section data-testid="review-why-it-matters">
          <h3 className="mb-2 text-[14.5px] font-semibold text-zinc-900">Por que importa</h3>
          <p className="text-[13.5px] leading-relaxed text-zinc-800">
            <span>{Array.isArray(c.why_it_matters) ? c.why_it_matters.join(' ') : c.why_it_matters}</span>
          </p>
        </section>
      )}

      {has('explanation') && c.detailed_explanation?.paragraphs?.length > 0 && (
        <section>
          <h3 className="text-[14.5px] font-semibold text-zinc-900 mb-2"><span>Explicação detalhada</span></h3>
          <div className="space-y-3">
            {c.detailed_explanation.paragraphs.map((p, i) => (
              <p key={i} className="text-[13.5px] text-zinc-800 leading-relaxed"><span>{p}</span></p>
            ))}
          </div>
        </section>
      )}

      {has('bullets') && c.smart_summary?.bullets?.length > 0 && (
        <section>
          <h3 className="text-[14.5px] font-semibold text-zinc-900 mb-2"><span>Pontos-chave</span></h3>
          <ul className="space-y-2">
            {c.smart_summary.bullets.map((b, i) => (
              <li key={i} className="flex items-start gap-2 text-[13.5px] text-zinc-800">
                <span className="mono text-[11px] mt-0.5 shrink-0" style={{ color: 'var(--mf-brand)' }}>
                  {String(i + 1).padStart(2, '0')}
                </span>
                <span>{b}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {has('high_yield') && c.high_yield_points?.length > 0 && (
        <section>
          <h3 className="text-[14.5px] font-semibold text-zinc-900 mb-2"><span>🎯 Mais cobrados em prova</span></h3>
          <ul className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {c.high_yield_points.map((h, i) => (
              <li key={i} className="p-3 rounded-lg bg-white hairline text-[12.5px] text-zinc-800">
                <span>{pointText(h)}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {has('mind_map') && c.mind_map && (
        <section>
          <h3 className="text-[14.5px] font-semibold text-zinc-900 mb-2"><span>🧠 Mapa mental</span></h3>
          <pre className="p-4 rounded-lg overflow-x-auto text-[12.5px] leading-relaxed whitespace-pre-wrap"
            style={{ background: 'var(--mf-hair-soft, #FAFAFA)', color: 'var(--mf-ink-2)' }}>
            {c.mind_map}
          </pre>
        </section>
      )}

      {has('flashcards') && c.flashcards?.length > 0 && (
        <section>
          <h3 className="text-[14.5px] font-semibold text-zinc-900 mb-2"><span>Flashcards ({c.flashcards.length})</span></h3>
          <ul className="space-y-2">
            {c.flashcards.map((f, i) => (
              <li key={i} className="p-3 rounded-lg bg-white hairline">
                <p className="text-[12.5px] font-semibold text-zinc-900"><span>{f.front}</span></p>
                <p className="mt-1 text-[12.5px] text-zinc-600"><span>→ {f.back}</span></p>
              </li>
            ))}
          </ul>
        </section>
      )}

      {has('memory') && c.memory_technique && (
        <section data-testid="review-memory-technique">
          <h3 className="mb-2 text-[14.5px] font-semibold text-zinc-900">Como memorizar</h3>
          <div className="rounded-lg border border-amber-100 bg-amber-50 p-4 text-[13px] leading-relaxed text-amber-950">
            <span>{c.memory_technique}</span>
          </div>
        </section>
      )}

      {has('questions') && c.practice_questions?.length > 0 && (
        <section>
          <h3 className="text-[14.5px] font-semibold text-zinc-900 mb-2"><span>Questões inéditas ({c.practice_questions.length})</span></h3>
          <ol className="space-y-3">
            {c.practice_questions.map((q, i) => (
              <li key={i} className="p-3 rounded-lg bg-white hairline text-[12.5px] text-zinc-800">
                <p className="font-semibold text-zinc-900"><span>{i + 1}. {q.stem}</span></p>
                <ul className="mt-2 space-y-1">
                  {(q.options || []).map((o, j) => (
                    <li key={j} className="text-zinc-700"><span>{o}</span></li>
                  ))}
                </ul>
                <p className="mt-2 text-zinc-500">
                  <span><strong style={{ color: 'var(--mf-success)' }}>Gabarito: {q.answer}</strong> · {q.explanation}</span>
                </p>
                {q.option_analysis && (
                  <p className="mt-2 text-[12px] leading-relaxed text-zinc-600">
                    <span>{Array.isArray(q.option_analysis) ? q.option_analysis.join(' ') : q.option_analysis}</span>
                  </p>
                )}
              </li>
            ))}
          </ol>
        </section>
      )}

      {has('case') && c.clinical_case?.vignette && (
        <section>
          <h3 className="text-[14.5px] font-semibold text-zinc-900 mb-2"><span>🏥 Caso clínico</span></h3>
          <div className="p-4 rounded-lg bg-white hairline space-y-2">
            <p className="text-[13px] text-zinc-800 leading-relaxed whitespace-pre-line">
              <span>{c.clinical_case.vignette}</span>
            </p>
            {c.clinical_case.question && (
              <p className="text-[13px] font-semibold text-zinc-900"><span>{c.clinical_case.question}</span></p>
            )}
            {c.clinical_case.answer && (
              <p className="text-[12.5px]" style={{ color: 'var(--mf-brand)' }}>
                <span><strong>Conduta:</strong> {c.clinical_case.answer}</span>
              </p>
            )}
          </div>
        </section>
      )}

      {has('mistakes') && c.common_mistakes?.length > 0 && (
        <section>
          <h3 className="text-[14.5px] font-semibold text-zinc-900 mb-2"><span>⚠️ Erros mais frequentes</span></h3>
          <ul className="space-y-1.5">
            {c.common_mistakes.map((m, i) => (
              <li key={i} className="text-[13px] text-zinc-700"><span>• {pointText(m)}</span></li>
            ))}
          </ul>
        </section>
      )}

      {has('exam') && c.exam_strategy && (
        <section data-testid="review-exam-strategy">
          <h3 className="mb-2 text-[14.5px] font-semibold text-zinc-900">Como isso cai na prova</h3>
          <p className="text-[13px] leading-relaxed text-zinc-700"><span>{c.exam_strategy}</span></p>
        </section>
      )}

      {has('spaced') && c.spaced_review_days?.length > 0 && (
        <div className="p-4 rounded-lg text-[12.5px] text-zinc-600"
          style={{ background: 'var(--mf-hair-soft, #FAFAFA)' }}>
          <p className="eyebrow"><span>vou te lembrar</span></p>
          <p className="mt-1">
            <span>Você verá esse tema de novo em: {c.spaced_review_days.join(' · ')} dias — no ritmo certo pro cérebro consolidar.</span>
          </p>
        </div>
      )}

      {/* Próximo passo — Princípio 7 */}
      <div
        className="pt-5 border-t"
        style={{ borderColor: 'var(--mf-hair, #EEE)' }}
        data-testid="full-review-next"
      >
        <p className="text-[13px] text-zinc-600 leading-relaxed">
          <span>Você concluiu {FOCUS_LABELS[focus].toLowerCase()} sobre <strong>{c.topic || data.topic}</strong>. Ótimo trabalho.</span>
        </p>
        <p className="mt-1 text-[13.5px] font-semibold text-zinc-900">
          <span>{isFocused ? 'Que tal seguir com:' : 'Para consolidar, podemos ainda:'}</span>
        </p>
        <div className="mt-3 flex flex-wrap gap-2">
          {(isFocused ? nextSuggestions : ['flashcards', 'questions', 'case']).map((k) => {
            const mode = STUDY_MODES.find((m) => m.key === k);
            if (!mode) return null;
            return (
              <button
                key={k}
                type="button"
                data-testid={`review-next-${k}`}
                onClick={() => onNextStep?.(k)}
                className="inline-flex items-center gap-1.5 px-3 py-2 rounded-full text-[12.5px] text-zinc-700 bg-white hairline hover:bg-zinc-50 transition-colors"
              >
                <span>{mode.emoji}</span>
                <span>{mode.label}</span>
              </button>
            );
          })}
          {isFocused && (
            <button
              type="button"
              data-testid="review-see-all"
              onClick={() => onNextStep?.('all')}
              className="inline-flex items-center gap-1.5 px-3 py-2 rounded-full text-[12.5px] text-white transition-transform hover:scale-[1.02]"
              style={{ background: 'var(--mf-brand)' }}
            >
              <span>⭐ Ver revisão completa</span>
            </button>
          )}
          <button
            type="button"
            data-testid="review-back-conv"
            onClick={onPickAnother}
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-full text-[12.5px] text-zinc-500 hover:text-zinc-800 transition-colors"
          >
            <span>← voltar às opções</span>
          </button>
        </div>
      </div>
    </div>
  );
};

// ─── Hero do Preceptor (mentor, não pergunta) ─────────────
// Quando existe recomendação real vinda de /api/home/today, o hero
// se comporta como um mentor: "Analisei sua evolução. Hoje o melhor
// uso do seu tempo é ...". Sem dados, cai num fallback humilde.
const PreceptorHero = ({ firstName, home, loading, onGo }) => {
  const rec = home?.recommendation;
  const durationMin = rec?.duration_min || rec?.duration_actual_min || null;
  const noticedText = home?.noticed?.mode === 'observed' ? home.noticed.text : null;

  return (
    <header
      className="mb-6 md:mb-8 rounded-2xl overflow-hidden border relative"
      style={{
        background: 'linear-gradient(135deg, #FBFAFF 0%, #F5F3FF 55%, #FEF3E9 100%)',
        borderColor: '#EDE9FE',
      }}
      data-testid="aprender-hero"
    >
      <div className="p-6 md:p-8">
        <p className="text-[11px] font-semibold uppercase tracking-widest" style={{ color: 'var(--mf-brand)' }}>
          <span>Preceptor IA · Particular</span>
        </p>

        <p className="mt-3 text-[15.5px] text-slate-700 leading-relaxed">
          <span>{firstName ? `${firstName}, ` : ''}analisei sua evolução recente.</span>
        </p>

        {loading ? (
          <div className="mt-4 flex items-center gap-2 text-slate-500 text-[13px]">
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
            <span>Compondo a melhor próxima ação para você…</span>
          </div>
        ) : rec ? (
          <>
            <p className="mt-4 text-[13px] text-slate-500">
              <span>Hoje o melhor uso do seu tempo é:</span>
            </p>
            <h1
              className="mt-1 font-bold text-slate-900 tracking-tight leading-[1.1]"
              style={{ fontSize: 'clamp(24px, 3.4vw, 34px)', letterSpacing: '-0.02em' }}
              data-testid="aprender-hero-title"
            >
              <span>{rec.title || rec.action_label || 'Sessão guiada com o Preceptor'}</span>
            </h1>
            {(rec.why_now || rec.subtitle) && (
              <p className="mt-2.5 text-[13.5px] text-slate-600 leading-relaxed max-w-xl">
                <span>{rec.why_now || rec.subtitle}</span>
              </p>
            )}

            <div className="mt-5 flex items-center gap-5 flex-wrap">
              {durationMin && (
                <div className="flex items-center gap-2 text-[13px] text-slate-700">
                  <Clock className="w-3.5 h-3.5" strokeWidth={2} style={{ color: 'var(--mf-brand)' }} />
                  <span><strong className="font-semibold">{durationMin} min</strong> · tempo estimado</span>
                </div>
              )}
              {noticedText && (
                <div className="flex items-center gap-2 text-[12.5px] text-slate-500 max-w-md">
                  <Wand2 className="w-3.5 h-3.5 shrink-0" strokeWidth={2} style={{ color: 'var(--mf-brand)' }} />
                  <span className="line-clamp-2">{noticedText}</span>
                </div>
              )}
            </div>

            <div className="mt-6">
              <button
                type="button"
                onClick={onGo}
                data-testid="aprender-hero-go"
                className="inline-flex items-center gap-2 text-white text-[14px] font-semibold px-5 py-2.5 rounded-xl transition-all hover:opacity-95 hover:-translate-y-px"
                style={{ background: 'var(--mf-brand)', boxShadow: '0 8px 20px -6px rgba(108,92,231,.55)' }}
              >
                <Play className="w-4 h-4" fill="currentColor" />
                <span>Ir com o Preceptor</span>
              </button>
            </div>
          </>
        ) : (
          <>
            <h1
              className="mt-3 font-bold text-slate-900 tracking-tight leading-[1.1]"
              style={{ fontSize: 'clamp(22px, 3vw, 30px)', letterSpacing: '-0.02em' }}
              data-testid="aprender-hero-title"
            >
              <span>Ainda estou aprendendo sua rotina.</span>
            </h1>
            <p className="mt-2.5 text-[13.5px] text-slate-600 leading-relaxed max-w-xl">
              <span>Escolha um caminho abaixo ou envie um tema — a partir daí eu conduzo.</span>
            </p>
          </>
        )}
      </div>
    </header>
  );
};


// Mesmo vocabulário orientado a resultado do Tutor home.
const APRENDER_ACTIONS = [
  { key: 'review',   Icon: Target,       label: 'Melhorar meu pior tema',        prompt: 'Melhorar meu pior tema' },
  { key: 'exam',     Icon: BookOpen,     label: 'Tenho prova em breve',          prompt: 'Tenho prova em breve — preciso de plano' },
  { key: 'memorize', Icon: Brain,        label: 'Memorizar um assunto',          prompt: 'Quero memorizar um assunto: ' },
  { key: 'quick',    Icon: Zap,          label: 'Estudo rápido',                 prompt: 'Estudo rápido de 15 minutos' },
  { key: 'perf',     Icon: TrendingUp,   label: 'Entender meus erros',           route: '/dashboard' },
];

const PERIOD_OPTIONS = [
  <option key="1" value="1">1º período</option>,
  <option key="2" value="2">2º período</option>,
  <option key="3" value="3">3º período</option>,
  <option key="4" value="4">4º período</option>,
  <option key="5" value="5">5º período</option>,
  <option key="6" value="6">6º período</option>,
  <option key="7" value="7">7º período</option>,
  <option key="8" value="8">8º período</option>,
  <option key="9" value="9">9º período</option>,
  <option key="10" value="10">10º período</option>,
  <option key="11" value="11">11º período</option>,
  <option key="12" value="12">12º período</option>,
];


// ─── Root ────────────────────────────────────────────────
const AprenderHoje = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { user } = useAuth();
  const firstName = (user?.name || '').trim().split(' ')[0] || '';
  const [text, setText] = useState('');
  const [source, setSource] = useState('typed');
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);   // interpretation
  const [fullReview, setFullReview] = useState(null);
  const [focus, setFocus] = useState('all');    // qual modo de estudo o aluno escolheu
  const [error, setError] = useState(null);
  const [resumeMode, setResumeMode] = useState(false); // vindo do "Retomar estudo"
  const [home, setHome] = useState(null);
  const [homeLoading, setHomeLoading] = useState(true);
  const [curriculum, setCurriculum] = useState(() => (
    localStorage.getItem('medflow-curriculum') || 'faminas_bh'
  ));
  const [period, setPeriod] = useState(() => (
    Number(localStorage.getItem('medflow-period') || 1)
  ));

  const updateCurriculum = (value) => {
    setCurriculum(value);
    localStorage.setItem('medflow-curriculum', value);
  };

  const updatePeriod = (value) => {
    const nextPeriod = Number(value);
    setPeriod(nextPeriod);
    localStorage.setItem('medflow-period', String(nextPeriod));
  };

  // Carrega a leitura do Preceptor pra usar no hero (recomendação + noticed)
  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const { data } = await api.get('/home/today');
        if (alive) setHome(data);
      } catch { /* silent */ }
      finally { if (alive) setHomeLoading(false); }
    })();
    return () => { alive = false; };
  }, []);

  const fileInputRef = useRef(null);
  const cameraInputRef = useRef(null);

  const { supported: voiceSupported, listening, start: startVoice, stop: stopVoice } =
    useSpeechRecognition();

  // Suporte a deep-link vindo da tela do Preceptor (missões / envie tudo aqui)
  //   ?q=<texto>         → auto-interpreta imediatamente
  //   ?prompt=<prefixo>  → só pré-preenche o campo (aluno completa)
  //   ?resume=1          → "Retomar estudo": pula o menu, vai direto pra Revisão Completa
  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const q = params.get('q');
    const prompt = params.get('prompt');
    const resume = params.get('resume') === '1';
    if (resume) setResumeMode(true);
    if (q && q.trim()) {
      setText(q);
      setSource('typed');
      // dispara em seguida — o handler usa o valor recebido, não o state
      handleInterpret(q, 'typed');
      return;
    }
    if (prompt && prompt.trim()) {
      setText(prompt);
      setSource('typed');
    }
  }, [location.search]);

  // Se veio de "Retomar estudo", pula o menu automaticamente
  // e vai direto pra Revisão Completa. Consumimos a intenção quando
  // o full-review chega (não antes) pra manter o rótulo visível.
  useEffect(() => {
    if (resumeMode && result && !fullReview && !loading) {
      onPickStudyMode('all');
    }
  }, [resumeMode, result, fullReview, loading]);

  useEffect(() => {
    if (resumeMode && fullReview) {
      setResumeMode(false);
    }
  }, [resumeMode, fullReview]);

  // ─── Executar ação rápida (chips) — igual ao Tutor home ──
  const pickAction = (a) => {
    if (a.route) { navigate(a.route); return; }
    if (a.prompt) {
      setText(a.prompt);
      setSource('typed');
      // Para prompts prontos ("Melhorar meu pior tema", "Estudo rápido"),
      // dispara imediatamente. Para os com placeholder (":"), deixa aluno completar.
      if (!a.prompt.endsWith(':') && !a.prompt.endsWith(': ')) {
        handleInterpret(a.prompt, 'typed');
      }
    }
  };

  // ─── "Ir com o Preceptor" — leva o aluno para a recomendação do dia ──
  const goWithPreceptor = () => {
    const rec = home?.recommendation;
    if (!rec) return;
    if (rec.action_route) { navigate(rec.action_route); return; }
    if (rec.action === 'checkin') { navigate('/checkin'); return; }
    // Se a recomendação tem tópico/título, usa como prompt inteligente
    const topic = rec.topic || rec.subject || rec.title || '';
    if (topic) {
      setText(topic);
      setSource('preceptor');
      handleInterpret(topic, 'preceptor');
      return;
    }
    handleInterpret('Sessão guiada pelo Preceptor', 'preceptor');
  };

  const handleInterpret = async (rawText, srcType = source) => {
    const finalText = (rawText ?? text).trim();
    if (!finalText) return;
    setLoading(true);
    setError(null);
    setResult(null);
    setFullReview(null);
    try {
      const payload = {
        text: finalText,
        source: srcType,
        file_name: file?.name || null,
        file_type: file
          ? (file.type.startsWith('image/') ? 'image'
            : file.type === 'application/pdf' ? 'pdf'
            : file.type.startsWith('audio/') ? 'audio' : 'other')
          : null,
      };
      const { data } = await api.post('/tutor/preceptor/interpret', payload,
        { timeout: 30_000 });
      setResult(data);
      // Memória visível: guardamos contexto rico pra próxima visita
      // (também facilita a migração pra memória oficial no backend).
      const topic = data?.interpretation?.topic;
      const disc  = data?.interpretation?.discipline;
      const next  = data?.interpretation?.next_topic
                 || data?.interpretation?.suggested_next
                 || null;
      if (topic && topic.length > 3) {
        writeMentorState({
          last_topic: topic,
          last_subject: disc || null,
          next_recommendation: next,
        });
      }
    } catch (e) {
      const raw = formatDetail(e?.response?.data?.detail || e?.response?.data);
      setError(humanizeError(raw, 'Deu um probleminha pra entender agora. Tenta reformular?'));
    } finally {
      setLoading(false);
    }
  };

  const handleFile = async (f) => {
    if (!f) return;
    setFile(f);
    setSource(f.type.startsWith('image/') ? 'camera' : 'file');
    // Tenta extrair texto (para PDFs simples ou .txt)
    if (f.type === 'text/plain' || f.name?.endsWith('.txt')) {
      const content = await readFileAsText(f);
      setText(content.slice(0, 6000));
    } else {
      // Para PDF/imagem: usamos apenas o nome como pista e o texto que o aluno digitar
      setText((prev) => prev || `Analise este ${f.type.startsWith('image/') ? 'material da foto' : 'arquivo'}: ${f.name}`);
    }
  };

  // ─── Modo de estudo escolhido pelo aluno ───
  // Princípio 2: só nesse momento entregamos conteúdo.
  const onPickStudyMode = async (mode) => {
    if (!result) return;
    // "plan" navega direto pro fluxo de plano de prova (que já existe no Tutor)
    if (mode === 'plan') {
      const topic = result.interpretation?.topic || '';
      const disc  = result.interpretation?.discipline || '';
      // Vamos deixar o wizard já semi-preenchido via query string
      const params = new URLSearchParams();
      if (topic) params.set('topic', topic);
      if (disc)  params.set('discipline', disc);
      navigate(`/tutor?planFor=${encodeURIComponent(topic || 'este tema')}`);
      return;
    }
    setFocus(mode);
    setLoading(true);
    setError(null);
    // Memória contextual: registra a atividade escolhida.
    const modeLabels = {
      all: 'Revisão Completa', explanation: 'Explicação',
      flashcards: 'Flashcards', questions: 'Questões',
      case: 'Caso clínico', plan: 'Plano de revisão', memorize: 'Consolidação inteligente',
    };
    writeMentorState({ last_activity: modeLabels[mode] || mode });
    try {
      const topic = result.interpretation.topic || text.trim();
      const discipline = result.interpretation.discipline || null;
      const learningMode = mode === 'memorize'
        ? 'memorize'
        : mode === 'all' ? 'premium_review' : 'focused';
      await streamPost('/tutor/preceptor/full-review/stream', {
        topic,
        discipline,
        mode: learningMode,
        focus: learningMode === 'focused' ? mode : null,
        curriculum,
        period,
      }, {
        onDone: (data) => setFullReview(data),
        onError: (err) => setError(humanizeError(formatDetail(err?.detail), 'Não deu certo agora. Podemos tentar de novo?')),
      });
    } catch (e) {
      setError(humanizeError(null, 'Não deu certo agora. Podemos tentar de novo?'));
    } finally {
      setLoading(false);
    }
  };

  // Continuar aprofundando: aluno já viu uma sessão focada e clicou num "próximo passo".
  // Se o full-review já foi gerado, só trocamos o foco (sem nova chamada).
  const onNextStep = (mode) => {
    if (mode === 'plan') return onPickStudyMode('plan');
    setFocus(mode);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const backToConversation = () => {
    // Volta para o menu de opções (ConversationCard) mantendo a interpretação.
    setFullReview(null);
    setFocus('all');
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const reset = () => {
    setText(''); setResult(null); setFullReview(null); setFile(null);
    setError(null); setFocus('all');
  };

  return (
    <Shell>
      <div className="max-w-3xl mx-auto px-5 md:px-8 pt-6 md:pt-8 pb-16" data-testid="aprender-root">
        {/* ─── Hero: Preceptor-first (mentor, não pergunta) ─── */}
        {resumeMode ? (
          <header className="mb-6 text-center" data-testid="aprender-hero">
            <p className="text-[11px] font-semibold uppercase tracking-widest text-slate-500">
              <span>retomar estudo</span>
            </p>
            <h1
              className="mt-1.5 font-bold text-slate-900 tracking-tight"
              style={{ fontSize: 'clamp(24px, 3.6vw, 34px)', letterSpacing: '-0.02em' }}
            >
              <span>Retomando de onde paramos…</span>
            </h1>
            <p className="mt-3 text-[14px] text-slate-500 max-w-2xl mx-auto leading-relaxed">
              <span>Vou preparar a Revisão Completa do último tema. Um instante.</span>
            </p>
          </header>
        ) : result || fullReview ? (
          /* Após interpretação, o card de resultado toma o palco.
             Um cabeçalho enxuto basta pra manter contexto. */
          <header className="mb-5" data-testid="aprender-hero">
            <p className="text-[11px] font-semibold uppercase tracking-widest" style={{ color: 'var(--mf-brand)' }}>
              <span>preceptor ia · particular</span>
            </p>
          </header>
        ) : (
          <PreceptorHero
            firstName={firstName}
            home={home}
            loading={homeLoading}
            onGo={goWithPreceptor}
          />
        )}

        {!fullReview && (
          <>
            <section
              className="mb-5 flex flex-wrap items-end gap-3 rounded-xl border border-slate-200 bg-white p-4"
              data-testid="curriculum-context"
            >
              <div className="min-w-[190px] flex-1">
                <label className="mb-1 block text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                  Matriz curricular
                </label>
                <select
                  data-testid="curriculum-select"
                  value={curriculum}
                  onChange={(event) => updateCurriculum(event.target.value)}
                  className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-[13px] text-slate-800"
                >
                  <option value="faminas_bh">FAMINAS-BH · currículo integrado</option>
                  <option value="fcmmg">FCMMG · matriz por disciplinas</option>
                </select>
              </div>
              <div className="w-[132px]">
                <label className="mb-1 block text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                  Período
                </label>
                <select
                  data-testid="curriculum-period-select"
                  value={period}
                  onChange={(event) => updatePeriod(event.target.value)}
                  className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-[13px] text-slate-800"
                >
                  {PERIOD_OPTIONS}
                </select>
              </div>
              <p className="max-w-sm text-[12px] leading-relaxed text-slate-500">
                O Preceptor integra automaticamente módulos, sistema corporal e profundidade da aula.
              </p>
            </section>
            {/* Ações rápidas — mentor: "Ou escolha outro caminho" */}
            {!result && !resumeMode && (
              <section
                className="mb-6"
                data-testid="aprender-actions"
                aria-label="Ações rápidas do Preceptor"
              >
                <p className="text-[11px] font-semibold uppercase tracking-widest text-slate-500 mb-3">
                  <span>Ou escolha outro caminho</span>
                </p>
                <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
                  {APRENDER_ACTIONS.map((a) => (
                    <button
                      key={a.key}
                      type="button"
                      data-testid={`aprender-action-${a.key}`}
                      onClick={() => pickAction(a)}
                      disabled={loading}
                      className="group mf-card p-3 md:p-3.5 text-left transition-all hover:-translate-y-0.5 hover:shadow-md disabled:opacity-60 disabled:pointer-events-none"
                    >
                      <div
                        className="w-8 h-8 rounded-lg flex items-center justify-center mb-2"
                        style={{ background: 'var(--mf-brand-soft)', color: 'var(--mf-brand)' }}
                      >
                        <a.Icon strokeWidth={2} className="w-4 h-4" />
                      </div>
                      <p className="text-[12.5px] font-semibold text-slate-900 leading-snug">
                        <span>{a.label}</span>
                      </p>
                    </button>
                  ))}
                </div>
              </section>
            )}

            {/* Chat livre — secundário: "Ou converse livremente" */}
            {!resumeMode && !result && (
            <section data-testid="aprender-free-chat">
              <p className="text-[11px] font-semibold uppercase tracking-widest text-slate-500 mb-3">
                <span>Ou converse livremente</span>
              </p>
              <div className="mf-card p-4 md:p-5 space-y-3" data-testid="universal-input">
              <textarea
                data-testid="aprender-input"
                rows={3}
                value={text}
                onChange={(e) => setText(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) handleInterpret();
                }}
                placeholder="Digite um tema, envie um PDF, imagem ou faça uma pergunta."
                className="w-full resize-none px-3.5 py-2.5 rounded-lg text-[14.5px] bg-white hairline focus:outline-none focus:ring-2 focus:ring-brand/40 placeholder:text-slate-400"
              />

              {file && (
                <div className="flex items-center gap-2 p-2 rounded-lg text-[12px]"
                  style={{ background: 'var(--mf-hair-soft, #FAFAFA)' }}
                  data-testid="aprender-file-chip">
                  {file.type.startsWith('image/')
                    ? <ImgIcon className="w-3.5 h-3.5 text-slate-500" />
                    : <FileText className="w-3.5 h-3.5 text-slate-500" />}
                  <span className="flex-1 truncate text-slate-700">{file.name}</span>
                  <button type="button" onClick={() => setFile(null)}
                    className="p-1 rounded hover:bg-slate-100">
                    <X className="w-3 h-3" />
                  </button>
                </div>
              )}

              <div className="flex items-center justify-between flex-wrap gap-2">
                <div className="flex items-center gap-1">
                  {/* File picker nativo (documento) */}
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".pdf,.txt,.doc,.docx,image/*"
                    onChange={(e) => handleFile(e.target.files?.[0])}
                    className="hidden"
                    data-testid="aprender-file-input"
                  />
                  <button
                    type="button"
                    data-testid="aprender-attach"
                    onClick={() => fileInputRef.current?.click()}
                    className="p-2 rounded-lg text-slate-500 hover:bg-slate-100 transition-colors"
                    title="Anexar arquivo"
                  >
                    <Paperclip className="w-4 h-4" />
                  </button>

                  {/* Câmera nativa */}
                  <input
                    ref={cameraInputRef}
                    type="file"
                    accept="image/*"
                    capture="environment"
                    onChange={(e) => handleFile(e.target.files?.[0])}
                    className="hidden"
                    data-testid="aprender-camera-input"
                  />
                  <button
                    type="button"
                    data-testid="aprender-camera"
                    onClick={() => cameraInputRef.current?.click()}
                    className="p-2 rounded-lg text-slate-500 hover:bg-slate-100 transition-colors"
                    title="Fotografar página"
                  >
                    <Camera className="w-4 h-4" />
                  </button>

                  {/* Voz (Web Speech API) */}
                  {voiceSupported && (
                    <button
                      type="button"
                      data-testid="aprender-voice"
                      onClick={() => {
                        if (listening) stopVoice();
                        else startVoice(
                          (t) => setText(t),
                          () => setSource('voice'),
                        );
                      }}
                      className="p-2 rounded-lg transition-colors"
                      style={listening
                        ? { background: 'var(--mf-care-soft)', color: 'var(--mf-care)' }
                        : {}}
                      title={listening ? 'Parar gravação' : 'Falar por voz'}
                    >
                      <Mic className={`w-4 h-4 ${listening ? 'animate-pulse' : ''}`} />
                    </button>
                  )}
                </div>

                <button
                  type="button"
                  data-testid="aprender-submit"
                  onClick={() => handleInterpret()}
                  disabled={loading || !text.trim()}
                  className="btn-primary"
                >
                  {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
                  <span>{loading ? 'Estou pensando…' : 'Enviar ao Preceptor'}</span>
                </button>
              </div>
              </div>
            </section>
            )}

            {/* Examples — "Sugestões para começar" (só quando não há resultado) */}
            {!result && !resumeMode && (
              <div className="mt-6" data-testid="aprender-examples">
                <p className="text-[11px] font-semibold uppercase tracking-widest text-slate-500 mb-2">
                  <span>Sugestões para começar</span>
                </p>
                <div className="flex flex-wrap gap-2">
                  {EXAMPLE_PROMPTS.map((ex, i) => (
                    <button
                      key={i}
                      type="button"
                      data-testid={`aprender-example-${i}`}
                      onClick={() => { setText(ex); setSource('typed'); handleInterpret(ex, 'typed'); }}
                      disabled={loading}
                      className="px-3 py-1.5 rounded-full text-[12.5px] text-slate-700 bg-white hairline hover:bg-slate-50 transition-colors"
                    >
                      <span>{ex}</span>
                    </button>
                  ))}
                </div>
              </div>
            )}

            {error && (
              <div
                data-testid="aprender-error"
                className="mt-4 p-3 rounded-lg flex items-start gap-2 text-[13px]"
                style={{ background: 'var(--mf-care-soft)', color: '#B15437' }}
              >
                <X className="w-4 h-4 mt-0.5 shrink-0" />
                <span>{error}</span>
              </div>
            )}

            {result && !fullReview && !resumeMode && (
              <div className="mt-6" data-testid="mission-result-wrap">
                <ConversationCard
                  result={result}
                  onPickMode={onPickStudyMode}
                  onChat={() => navigate('/tutor')}
                />
                {loading && (
                  <p className="mt-4 text-center text-[12.5px] text-zinc-500 inline-flex items-center gap-1.5 justify-center w-full">
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    <span>Preparando o material com carinho…</span>
                  </p>
                )}
                <div className="mt-4 text-center">
                  <button
                    type="button"
                    onClick={reset}
                    className="btn-ghost text-[12px]"
                    data-testid="aprender-reset"
                  >
                    <span>← começar uma nova conversa</span>
                  </button>
                </div>
              </div>
            )}

            {/* Modo Retomar estudo: sem menu, sem ruído. Só o preparo. */}
            {resumeMode && !fullReview && (
              <div className="mt-6 text-center" data-testid="resume-preparing">
                <Loader2 className="w-6 h-6 animate-spin mx-auto"
                  style={{ color: 'var(--mf-brand)' }} />
                <p className="mt-3 text-[13.5px] text-zinc-600">
                  <span>{loading ? 'Estou pensando…' : 'Preparando o material com carinho…'}</span>
                </p>
              </div>
            )}
          </>
        )}

        {fullReview && (
          <FullReviewView
            data={fullReview}
            focus={focus}
            onBack={reset}
            onPickAnother={backToConversation}
            onNextStep={onNextStep}
          />
        )}
      </div>
    </Shell>
  );
};

export default AprenderHoje;
