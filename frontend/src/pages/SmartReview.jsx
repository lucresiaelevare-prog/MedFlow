import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Loader2, ArrowLeft, ArrowRight, CheckCircle2, XCircle, Sparkles,
  Stethoscope, BookMarked, AlertTriangle, HeartPulse, Gem, ListChecks,
  Compass, MessagesSquare, ShieldCheck, Clock, ExternalLink, Zap,
} from 'lucide-react';
import Shell from '@/components/Shell';
import api from '@/lib/api';
import {
  Accordion, AccordionItem, AccordionTrigger, AccordionContent,
} from '@/components/ui/accordion';
import { PreceptorCTA, PreceptorChat } from '@/components/PreceptorChat';
import ConfidencePrompt from './smart-review/ConfidencePrompt';

/**
 * Devolutiva Inteligente Med Flow™
 *
 * O tutor age como tutor: raciocínio clínico + pérola + erro comum +
 * aplicação prática + evidências (PubMed/OpenAlex) + próximos passos +
 * feedback personalizado (Mastery Map).
 */

const input =
  'w-full px-3.5 py-2.5 rounded-lg text-[14px] hairline bg-white focus:outline-none focus:ring-2 focus:ring-brand/40 placeholder:text-zinc-400';

function formatDetail(detail) {
  if (detail == null) return null;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) return detail.map((e) => e?.msg || JSON.stringify(e)).join(' ');
  return String(detail);
}

// ─── Card wrapper para cada seção da devolutiva ───────────────
const SectionCard = ({ Icon, label, tone = 'brand', children, testId }) => (
  <div
    data-testid={testId}
    className="p-4 md:p-5 rounded-xl"
    style={{
      background: tone === 'care' ? 'var(--mf-care-soft)'
        : tone === 'success' ? 'var(--mf-success-soft)'
          : tone === 'neutral' ? 'var(--mf-hair-soft, #FAFAFA)'
            : 'var(--mf-brand-soft)',
    }}
  >
    <div className="flex items-center gap-2 mb-3">
      <Icon
        className="w-4 h-4"
        strokeWidth={2}
        style={{
          color: tone === 'care' ? 'var(--mf-care)'
            : tone === 'success' ? 'var(--mf-success)'
              : tone === 'neutral' ? '#71717A'
                : 'var(--mf-brand)',
        }}
      />
      <p
        className="eyebrow"
        style={{
          color: tone === 'care' ? 'var(--mf-care)'
            : tone === 'success' ? 'var(--mf-success)'
              : tone === 'neutral' ? '#71717A'
                : 'var(--mf-brand)',
        }}
      >
        <span>{label}</span>
      </p>
    </div>
    {children}
  </div>
);

// ─── 1. Resposta Objetiva ──────────────────────────────────
const ObjectiveCard = ({ objective, isCorrect }) => (
  <div
    data-testid="sr-objective"
    className="mf-card p-5 md:p-6 animate-fade-in"
    style={{
      background: isCorrect === false
        ? 'linear-gradient(180deg, var(--mf-care-soft) 0%, #FFF 60%)'
        : 'linear-gradient(180deg, var(--mf-success-soft, #ECFDF5) 0%, #FFF 60%)',
    }}
  >
    <div className="flex items-start gap-3 mb-3">
      <span
        className="w-11 h-11 rounded-xl flex items-center justify-center shrink-0"
        style={{
          background: isCorrect === false ? 'var(--mf-care)' : 'var(--mf-success)',
          color: '#fff',
        }}
      >
        {isCorrect === false
          ? <XCircle strokeWidth={2} className="w-6 h-6" />
          : <CheckCircle2 strokeWidth={2} className="w-6 h-6" />}
      </span>
      <div className="flex-1 min-w-0">
        <p className="eyebrow"><span>alternativa correta</span></p>
        <p
          className="mt-1 font-semibold text-zinc-900 tracking-tight"
          style={{ fontSize: 'clamp(24px, 3vw, 32px)' }}
        >
          <span>{objective?.correct_letter || '—'}</span>
          {isCorrect === false && (
            <span className="ml-2 text-[14px] font-normal text-zinc-500"><span>· você errou</span></span>
          )}
          {isCorrect === true && (
            <span className="ml-2 text-[14px] font-normal" style={{ color: 'var(--mf-success)' }}>
              <span>· você acertou</span>
            </span>
          )}
        </p>
      </div>
    </div>
    <p className="text-[14.5px] text-zinc-700 leading-relaxed">
      <span>{objective?.summary || 'Sem resumo disponível.'}</span>
    </p>
  </div>
);

// ─── 2. Raciocínio Clínico ──────────────────────────────────
const ReasoningCard = ({ paragraphs }) => (
  <div className="space-y-3">
    {(paragraphs || []).map((p, i) => (
      <p key={i} className="text-[14px] text-zinc-800 leading-relaxed"><span>{p}</span></p>
    ))}
  </div>
);

// ─── 3. Análise das Alternativas ────────────────────────────
const AlternativesCard = ({ items }) => (
  <ul className="space-y-2.5">
    {(items || []).map((alt, i) => (
      <li key={i} className="flex items-start gap-3 p-3 rounded-lg bg-white hairline">
        <span
          className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0 font-semibold text-[13px]"
          style={{
            background: alt.is_correct ? 'var(--mf-success)' : 'var(--mf-care)',
            color: '#fff',
          }}
        >
          {alt.is_correct
            ? <CheckCircle2 className="w-4 h-4" strokeWidth={2.2} />
            : <XCircle className="w-4 h-4" strokeWidth={2.2} />}
        </span>
        <div className="flex-1 min-w-0">
          <p className="text-[13.5px] font-semibold text-zinc-900">
            <span className="mono mr-1">{alt.letter}.</span>
            <span className={alt.is_correct ? '' : 'text-zinc-500 line-through decoration-1'}>
              {alt.is_correct ? 'correta' : 'incorreta'}
            </span>
          </p>
          <p className="mt-1 text-[13px] text-zinc-700 leading-relaxed">
            <span>{alt.explanation}</span>
          </p>
        </div>
      </li>
    ))}
  </ul>
);

// ─── 6. Aplicação na Prática ─────────────────────────────────
const RealWorldCard = ({ rw }) => (
  <div className="space-y-3">
    {rw?.arrival && (
      <div>
        <p className="text-[11.5px] uppercase tracking-wider text-zinc-500 mb-1"><span>como chega</span></p>
        <p className="text-[13.5px] text-zinc-800 leading-relaxed"><span>{rw.arrival}</span></p>
      </div>
    )}
    {rw?.physician_thinking && (
      <div>
        <p className="text-[11.5px] uppercase tracking-wider text-zinc-500 mb-1"><span>o médico pensa</span></p>
        <p className="text-[13.5px] text-zinc-800 leading-relaxed"><span>{rw.physician_thinking}</span></p>
      </div>
    )}
    {rw?.priority && (
      <div>
        <p className="text-[11.5px] uppercase tracking-wider text-zinc-500 mb-1"><span>prioridade imediata</span></p>
        <p className="text-[13.5px] font-semibold text-zinc-900 leading-relaxed"><span>{rw.priority}</span></p>
      </div>
    )}
  </div>
);

// ─── 7. Evidências ───────────────────────────────────────────
const EvidenceCard = ({ guideline, pubmed, openalex }) => {
  const hasGuideline = guideline && guideline.society && guideline.society !== 'não citada';
  const items = [...(pubmed || []), ...(openalex || [])].slice(0, 3);
  if (!hasGuideline && items.length === 0) {
    return <p className="text-[13px] text-zinc-500 italic"><span>Sem referências indexadas para esta questão.</span></p>;
  }
  return (
    <div className="space-y-3">
      {hasGuideline && (
        <div className="p-3 rounded-lg bg-white hairline">
          <p className="text-[11.5px] uppercase tracking-wider text-zinc-500"><span>diretriz</span></p>
          <p className="mt-1 text-[13.5px] font-semibold text-zinc-900">
            <span>{guideline.note || 'não citada'}</span>
          </p>
          <p className="mt-0.5 text-[12.5px] text-zinc-600">
            <span>{guideline.society}{guideline.year ? ` · ${guideline.year}` : ''}</span>
          </p>
        </div>
      )}
      {items.length > 0 && (
        <ul className="space-y-2">
          {items.map((it, i) => (
            <li key={i} className="p-3 rounded-lg bg-white hairline">
              <a
                href={it.url || it.open_access_url || it.id}
                target="_blank"
                rel="noopener noreferrer"
                className="group"
                data-testid={`sr-evidence-${i}`}
              >
                <p className="text-[13px] font-medium text-zinc-900 leading-snug group-hover:underline">
                  <span>{it.title}</span>
                  <ExternalLink className="inline w-3 h-3 ml-1 text-zinc-400" />
                </p>
                <p className="mt-1 text-[11.5px] text-zinc-500">
                  <span>
                    {it.journal || it.venue || 'Fonte'}
                    {it.pubdate ? ` · ${it.pubdate}` : (it.year ? ` · ${it.year}` : '')}
                    {it.pmid ? ` · PMID ${it.pmid}` : ''}
                  </span>
                </p>
              </a>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};

// ─── 8. O que revisar agora ─────────────────────────────────
const ReviewTopicsCard = ({ topics, discipline }) => {
  const navigate = useNavigate();
  return (
    <ul className="grid grid-cols-1 sm:grid-cols-2 gap-2">
      {(topics || []).slice(0, 5).map((t, i) => (
        <li key={i}>
          <button
            data-testid={`sr-topic-${i}`}
            onClick={() =>
              navigate(`/tutor?discipline=${encodeURIComponent(discipline || '')}&topic=${encodeURIComponent(t)}`)
            }
            className="w-full text-left p-3 rounded-lg bg-white hairline hover:bg-zinc-50 transition-colors flex items-center gap-2 group"
          >
            <span
              className="w-6 h-6 rounded-md flex items-center justify-center shrink-0 mono text-[11px]"
              style={{ background: 'var(--mf-brand-soft)', color: 'var(--mf-brand)' }}
            >
              {i + 1}
            </span>
            <span className="text-[13.5px] text-zinc-800 flex-1 truncate"><span>{t}</span></span>
            <ArrowRight className="w-3.5 h-3.5 text-zinc-300 group-hover:text-zinc-500 shrink-0" strokeWidth={2} />
          </button>
        </li>
      ))}
    </ul>
  );
};

// ─── 11. Confiança ──────────────────────────────────────────
const ConfidenceBadge = ({ level }) => {
  const map = {
    alta: { bg: 'var(--mf-success-soft, #ECFDF5)', color: 'var(--mf-success)', label: 'Estimativa alta' },
    moderada: { bg: 'var(--mf-brand-soft)', color: 'var(--mf-brand)', label: 'Estimativa moderada' },
    baixa: { bg: 'var(--mf-care-soft)', color: 'var(--mf-care)', label: 'Estimativa baixa' },
  };
  const c = map[(level || '').toLowerCase()] || map.moderada;
  return (
    <span
      className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11.5px] font-semibold"
      style={{ background: c.bg, color: c.color }}
    >
      <ShieldCheck className="w-3 h-3" strokeWidth={2.2} />
      <span>{c.label}</span>
    </span>
  );
};

// ─── Full result view ──────────────────────────────────────────
const SmartReviewResult = ({ review, onBack }) => {
  const [chatOpen, setChatOpen] = useState(false);

  const llm = review.llm_output || {};
  const alts = llm.alternatives_analysis || [];
  const pubmed = review.evidence?.pubmed || [];
  const openalex = review.evidence?.openalex || [];
  const readingSec = llm.reading_time_sec || 120;
  const readingLabel = readingSec < 60
    ? `${readingSec}s`
    : readingSec < 180 ? `${Math.round(readingSec / 60)} min` : `${Math.round(readingSec / 60)} min`;

  return (
    <div className="space-y-4 animate-fade-in" data-testid="sr-result">
      {/* Header com meta info */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <button onClick={onBack} className="btn-ghost inline-flex items-center gap-1.5" data-testid="sr-back">
          <ArrowLeft className="w-4 h-4" /> <span>Nova devolutiva</span>
        </button>
        <div className="flex items-center gap-2 text-[11.5px] text-zinc-500">
          <span className="inline-flex items-center gap-1">
            <Clock className="w-3.5 h-3.5" /> <span>{readingLabel} de leitura</span>
          </span>
          <span>·</span>
          <ConfidenceBadge level={llm.confidence?.level} />
          {review.llm_provider && (
            <>
              <span>·</span>
              <span className="inline-flex items-center gap-1">
                <Zap className="w-3.5 h-3.5" />
                <span>{review.llm_provider}</span>
              </span>
            </>
          )}
        </div>
      </div>

      {/* 1. Resposta objetiva */}
      <ObjectiveCard objective={llm.objective} isCorrect={review.is_correct} />

      {/* 10. Feedback personalizado — banner alto */}
      {review.personalized?.message && (
        <div
          data-testid="sr-personalized"
          className="p-4 md:p-5 rounded-xl flex items-start gap-3"
          style={{
            background: 'var(--mf-brand-soft)',
            borderLeft: '3px solid var(--mf-brand)',
          }}
        >
          <MessagesSquare
            className="w-5 h-5 shrink-0 mt-0.5"
            strokeWidth={1.8}
            style={{ color: 'var(--mf-brand)' }}
          />
          <div>
            <p className="text-[11.5px] uppercase tracking-wider font-semibold" style={{ color: 'var(--mf-brand)' }}>
              <span>seu tutor observa</span>
            </p>
            <p className="mt-1 text-[14px] text-zinc-800 leading-relaxed">
              <span>{review.personalized.message}</span>
            </p>
          </div>
        </div>
      )}

      {/* Accordion com todas as demais seções */}
      <Accordion
        type="multiple"
        defaultValue={['reasoning', 'alternatives']}
        className="space-y-3"
        data-testid="sr-accordion"
      >
        {/* 2. Raciocínio clínico */}
        <AccordionItem value="reasoning" className="mf-card border-0 px-4 md:px-5" data-testid="sr-section-reasoning">
          <AccordionTrigger className="py-4">
            <div className="flex items-center gap-2.5">
              <Stethoscope className="w-4 h-4" style={{ color: 'var(--mf-brand)' }} strokeWidth={2} />
              <span className="text-[14.5px] font-semibold text-zinc-900">Raciocínio clínico</span>
            </div>
          </AccordionTrigger>
          <AccordionContent>
            <ReasoningCard paragraphs={llm.clinical_reasoning?.paragraphs} />
          </AccordionContent>
        </AccordionItem>

        {/* 3. Análise das alternativas */}
        <AccordionItem value="alternatives" className="mf-card border-0 px-4 md:px-5" data-testid="sr-section-alternatives">
          <AccordionTrigger className="py-4">
            <div className="flex items-center gap-2.5">
              <ListChecks className="w-4 h-4" style={{ color: 'var(--mf-brand)' }} strokeWidth={2} />
              <span className="text-[14.5px] font-semibold text-zinc-900">Análise das alternativas</span>
            </div>
          </AccordionTrigger>
          <AccordionContent>
            <AlternativesCard items={alts} />
          </AccordionContent>
        </AccordionItem>

        {/* 4. Pérola clínica */}
        {llm.clinical_pearl?.content && (
          <AccordionItem value="pearl" className="mf-card border-0 px-4 md:px-5" data-testid="sr-section-pearl">
            <AccordionTrigger className="py-4">
              <div className="flex items-center gap-2.5">
                <Gem className="w-4 h-4" style={{ color: 'var(--mf-brand)' }} strokeWidth={2} />
                <span className="text-[14.5px] font-semibold text-zinc-900">Pérola clínica</span>
              </div>
            </AccordionTrigger>
            <AccordionContent>
              <SectionCard Icon={Gem} label={llm.clinical_pearl.title || 'perla'} tone="brand" testId="sr-pearl">
                <p className="text-[14px] text-zinc-800 leading-relaxed font-medium italic">
                  <span>“{llm.clinical_pearl.content}”</span>
                </p>
              </SectionCard>
            </AccordionContent>
          </AccordionItem>
        )}

        {/* 5. Erro mais comum */}
        {llm.common_mistake?.content && (
          <AccordionItem value="mistake" className="mf-card border-0 px-4 md:px-5" data-testid="sr-section-mistake">
            <AccordionTrigger className="py-4">
              <div className="flex items-center gap-2.5">
                <AlertTriangle className="w-4 h-4" style={{ color: 'var(--mf-care)' }} strokeWidth={2} />
                <span className="text-[14.5px] font-semibold text-zinc-900">Onde os candidatos mais erram</span>
              </div>
            </AccordionTrigger>
            <AccordionContent>
              <SectionCard Icon={AlertTriangle} label={llm.common_mistake.title || 'atenção'} tone="care" testId="sr-mistake">
                <p className="text-[13.5px] text-zinc-800 leading-relaxed"><span>{llm.common_mistake.content}</span></p>
              </SectionCard>
            </AccordionContent>
          </AccordionItem>
        )}

        {/* 6. Na vida real */}
        {llm.real_world && (llm.real_world.arrival || llm.real_world.priority) && (
          <AccordionItem value="real" className="mf-card border-0 px-4 md:px-5" data-testid="sr-section-realworld">
            <AccordionTrigger className="py-4">
              <div className="flex items-center gap-2.5">
                <HeartPulse className="w-4 h-4" style={{ color: 'var(--mf-brand)' }} strokeWidth={2} />
                <span className="text-[14.5px] font-semibold text-zinc-900">Na vida real</span>
              </div>
            </AccordionTrigger>
            <AccordionContent>
              <RealWorldCard rw={llm.real_world} />
            </AccordionContent>
          </AccordionItem>
        )}

        {/* 7. Evidências */}
        <AccordionItem value="evidence" className="mf-card border-0 px-4 md:px-5" data-testid="sr-section-evidence">
          <AccordionTrigger className="py-4">
            <div className="flex items-center gap-2.5">
              <BookMarked className="w-4 h-4" style={{ color: 'var(--mf-brand)' }} strokeWidth={2} />
              <span className="text-[14.5px] font-semibold text-zinc-900">Evidências científicas</span>
              {(pubmed.length + openalex.length) > 0 && (
                <span className="mono text-[11px] text-zinc-400 ml-1">
                  <span>{pubmed.length + openalex.length} refs</span>
                </span>
              )}
            </div>
          </AccordionTrigger>
          <AccordionContent>
            <EvidenceCard guideline={llm.guideline} pubmed={pubmed} openalex={openalex} />
          </AccordionContent>
        </AccordionItem>

        {/* 8. Próximos tópicos */}
        {(llm.review_topics || []).length > 0 && (
          <AccordionItem value="topics" className="mf-card border-0 px-4 md:px-5" data-testid="sr-section-topics">
            <AccordionTrigger className="py-4">
              <div className="flex items-center gap-2.5">
                <Compass className="w-4 h-4" style={{ color: 'var(--mf-brand)' }} strokeWidth={2} />
                <span className="text-[14.5px] font-semibold text-zinc-900">O que revisar agora</span>
              </div>
            </AccordionTrigger>
            <AccordionContent>
              <ReviewTopicsCard topics={llm.review_topics} discipline={review.discipline} />
            </AccordionContent>
          </AccordionItem>
        )}

        {/* 11. Confiança — detalhes */}
        {llm.confidence?.explanation && (
          <AccordionItem value="confidence" className="mf-card border-0 px-4 md:px-5" data-testid="sr-section-confidence">
            <AccordionTrigger className="py-4">
              <div className="flex items-center gap-2.5">
                <ShieldCheck className="w-4 h-4" style={{ color: 'var(--mf-brand)' }} strokeWidth={2} />
                <span className="text-[14.5px] font-semibold text-zinc-900">Estimativa da resposta</span>
                <span className="ml-1"><ConfidenceBadge level={llm.confidence?.level} /></span>
              </div>
            </AccordionTrigger>
            <AccordionContent>
              <p className="text-[13.5px] text-zinc-700 leading-relaxed"><span>{llm.confidence.explanation}</span></p>
            </AccordionContent>
          </AccordionItem>
        )}
      </Accordion>

      {/* CTA + Chat contextualizado com o Tutor IA */}
      {!chatOpen && (
        <div className="pt-2">
          <PreceptorCTA onOpen={() => setChatOpen(true)} />
        </div>
      )}
      {chatOpen && (
        <PreceptorChat reviewId={review.id} onClose={() => setChatOpen(false)} />
      )}
      <ConfidencePrompt reviewId={review.id} />
    </div>
  );
};

// ─── Form ────────────────────────────────────────────────────
const SmartReviewForm = ({ onSubmit, loading }) => {
  const [stem, setStem] = useState('');
  const [options, setOptions] = useState(['', '', '', '']);
  const [correctLetter, setCorrectLetter] = useState('A');
  const [studentLetter, setStudentLetter] = useState('');
  const [discipline, setDiscipline] = useState('');
  const [topic, setTopic] = useState('');

  const setOpt = (i, val) => setOptions((prev) => prev.map((o, j) => (j === i ? val : o)));
  const addOpt = () => setOptions((prev) => (prev.length < 6 ? [...prev, ''] : prev));
  const removeOpt = () => setOptions((prev) => (prev.length > 2 ? prev.slice(0, -1) : prev));

  const letters = options.map((_, i) => String.fromCharCode(65 + i));
  const disabled =
    loading ||
    stem.trim().length < 10 ||
    options.filter((o) => o.trim()).length < 2 ||
    !correctLetter;

  const submit = () => {
    onSubmit({
      question_stem: stem.trim(),
      options: options.map((o) => o.trim()).filter(Boolean),
      correct_letter: correctLetter,
      student_letter: studentLetter || null,
      discipline: discipline.trim() || null,
      topic: topic.trim() || null,
    });
  };

  return (
    <div className="mf-card p-5 md:p-6 space-y-4 animate-fade-in" data-testid="sr-form">
      <div>
        <p className="eyebrow"><span>enunciado da questão *</span></p>
        <textarea
          data-testid="sr-input-stem"
          rows={5}
          className={`${input} mt-2`}
          placeholder="Cole aqui o enunciado completo da questão…"
          value={stem}
          onChange={(e) => setStem(e.target.value)}
        />
      </div>

      <div>
        <div className="flex items-center justify-between mb-2">
          <p className="eyebrow"><span>alternativas ({options.length}) *</span></p>
          <div className="flex gap-1.5">
            <button type="button" onClick={removeOpt} disabled={options.length <= 2}
              className="btn-ghost text-[11.5px] px-2 py-1" data-testid="sr-opt-remove">
              <span>-</span>
            </button>
            <button type="button" onClick={addOpt} disabled={options.length >= 6}
              className="btn-ghost text-[11.5px] px-2 py-1" data-testid="sr-opt-add">
              <span>+</span>
            </button>
          </div>
        </div>
        <ul className="space-y-2">
          {options.map((opt, i) => (
            <li key={i} className="flex items-center gap-2">
              <span className="mono text-[13px] w-6 text-center shrink-0"
                style={{ color: 'var(--mf-brand)' }}>{letters[i]}.</span>
              <input
                data-testid={`sr-input-opt-${i}`}
                className={input}
                placeholder={`Alternativa ${letters[i]}`}
                value={opt}
                onChange={(e) => setOpt(i, e.target.value)}
              />
            </li>
          ))}
        </ul>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <p className="eyebrow"><span>gabarito oficial *</span></p>
          <select
            data-testid="sr-input-correct"
            className={`${input} mt-2`}
            value={correctLetter}
            onChange={(e) => setCorrectLetter(e.target.value)}
          >
            {letters.map((l) => <option key={l} value={l}>{l}</option>)}
          </select>
        </div>
        <div>
          <p className="eyebrow"><span>sua resposta (opcional)</span></p>
          <select
            data-testid="sr-input-student"
            className={`${input} mt-2`}
            value={studentLetter}
            onChange={(e) => setStudentLetter(e.target.value)}
          >
            <option value="">— não respondi —</option>
            {letters.map((l) => <option key={l} value={l}>{l}</option>)}
          </select>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <p className="eyebrow"><span>disciplina (opcional)</span></p>
          <input
            data-testid="sr-input-discipline"
            className={`${input} mt-2`}
            placeholder="ex.: Cardiologia"
            value={discipline}
            onChange={(e) => setDiscipline(e.target.value)}
          />
        </div>
        <div>
          <p className="eyebrow"><span>tema (opcional)</span></p>
          <input
            data-testid="sr-input-topic"
            className={`${input} mt-2`}
            placeholder="ex.: Tamponamento Cardíaco"
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
          />
        </div>
      </div>

      <div className="flex justify-end pt-2">
        <button
          data-testid="sr-submit"
          disabled={disabled}
          onClick={submit}
          className="btn-primary"
        >
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
          <span>{loading ? 'Analisando…' : 'Gerar devolutiva inteligente'}</span>
        </button>
      </div>
    </div>
  );
};

// ─── Root ────────────────────────────────────────────────────
const SmartReview = () => {
  const [review, setReview] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const submit = async (payload) => {
    setLoading(true); setError(null);
    try {
      const { data } = await api.post('/tutor/smart-review', payload, { timeout: 90_000 });
      setReview(data.review);
    } catch (e) {
      setError(formatDetail(e?.response?.data?.detail) || 'Não foi possível gerar a devolutiva.');
    } finally {
      setLoading(false);
    }
  };

  const reset = () => { setReview(null); setError(null); };

  return (
    <Shell>
      <div className="max-w-3xl mx-auto px-5 md:px-8 pt-6 md:pt-8 pb-16" data-testid="sr-root">
        <header className="mb-6">
          <p className="eyebrow"><span>tutor · devolutiva inteligente</span></p>
          <h1
            className="mt-1.5 font-semibold text-zinc-900 tracking-tight"
            style={{ fontSize: 'clamp(26px, 3.4vw, 34px)', letterSpacing: '-0.02em' }}
          >
            <span>Devolutiva Inteligente Med Flow™</span>
          </h1>
          <p className="mt-2 text-[14.5px] text-zinc-500 max-w-2xl leading-relaxed">
            <span>Não é só a resposta certa. É um tutor experiente ensinando raciocínio clínico, mostrando onde os candidatos erram e conectando teoria à prática.</span>
          </p>
        </header>

        {error && (
          <div
            data-testid="sr-error"
            className="mb-4 p-3 rounded-lg flex items-start gap-2 text-[13px]"
            style={{ background: 'var(--mf-care-soft)', color: '#B15437' }}
          >
            <XCircle className="w-4 h-4 mt-0.5 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {!review && <SmartReviewForm onSubmit={submit} loading={loading} />}
        {review && <SmartReviewResult review={review} onBack={reset} />}
      </div>
    </Shell>
  );
};

export default SmartReview;
