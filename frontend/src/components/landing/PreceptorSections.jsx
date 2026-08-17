import { useEffect, useState, useRef } from 'react';
import { ArrowRight, Sparkles, Check } from 'lucide-react';
import { PRECEPTOR_CAPS, PRECEPTOR_FLOW, PRECEPTOR_LOADING_STAGES } from './data';

/**
 * Tutor IA — Seção principal + Experiência sequencial.
 * Onda 5 — reposicionamento da landing após ativação do Tutor.
 * Inspiração visual: Apple / Linear / Stripe / Notion / Raycast.
 */

// ─── Browser chrome padrão da landing ──────────────────────────
const Chrome = ({ children, testId, small }) => (
  <div
    data-testid={testId}
    className="w-full"
    style={{
      borderRadius: 14,
      border: '1px solid var(--mf-inst-line-2)',
      background: '#FFFFFF',
      boxShadow: '0 40px 100px -30px rgba(20,20,40,0.28), 0 16px 48px -18px rgba(20,20,40,0.14)',
      overflow: 'hidden',
    }}
  >
    <div
      className="flex items-center gap-1.5 px-3.5 py-2.5"
      style={{ background: '#F6F3ED', borderBottom: '1px solid var(--mf-inst-line)' }}
    >
      <span className="w-2.5 h-2.5 rounded-full" style={{ background: '#E4DFD6' }} />
      <span className="w-2.5 h-2.5 rounded-full" style={{ background: '#E4DFD6' }} />
      <span className="w-2.5 h-2.5 rounded-full" style={{ background: '#E4DFD6' }} />
      <span
        className="ml-3 text-[10.5px]"
        style={{ color: 'var(--mf-inst-muted)', letterSpacing: '0.14em' }}
      >
        MEDFLOW.APP / TUTOR
      </span>
    </div>
    <div className={small ? 'p-4 md:p-5' : 'p-5 md:p-8'}>{children}</div>
  </div>
);

// ─── Mockup: interface real do Tutor com múltiplas superfícies ──
const PreceptorInterface = () => (
  <Chrome testId="preceptor-mockup">
    {/* Bubble: pergunta do aluno */}
    <div className="mb-4 flex justify-end">
      <div
        className="max-w-[85%] rounded-2xl rounded-tr-sm px-3.5 py-2.5 text-[13.5px]"
        style={{
          background: 'var(--mf-brand)',
          color: '#FFFFFF',
          lineHeight: 1.45,
        }}
      >
        Explique-me o Ciclo de Krebs. Prova amanhã.
      </div>
    </div>

    {/* Bubble: Tutor + tópico identificado */}
    <div className="mb-5">
      <div className="flex items-start gap-2.5">
        <span
          className="mt-0.5 w-6 h-6 rounded-md shrink-0 inline-flex items-center justify-center"
          style={{ background: 'var(--mf-brand-soft)' }}
        >
          <Sparkles strokeWidth={2} className="w-3 h-3" style={{ color: 'var(--mf-brand)' }} />
        </span>
        <div className="flex-1">
          <p className="text-[11px] font-semibold uppercase tracking-widest" style={{ color: 'var(--mf-inst-muted)' }}>
            Tutor
          </p>
          <p className="mt-1 text-[13.5px] leading-[1.55]" style={{ color: 'var(--mf-inst-ink)' }}>
            Entendi. Vou preparar a Revisão Completa: explicação, mapa mental, flashcards, questões e caso clínico.
          </p>
          <p className="mt-1.5 inline-flex items-center gap-1.5 text-[11.5px]" style={{ color: 'var(--mf-inst-muted)' }}>
            <span
              className="inline-block w-1.5 h-1.5 rounded-full"
              style={{ background: 'var(--mf-brand)' }}
              aria-hidden="true"
            />
            <span>Ciclo de Krebs · Bioquímica</span>
          </p>
        </div>
      </div>
    </div>

    {/* Divisor sutil */}
    <div className="h-px w-full my-4" style={{ background: 'var(--mf-inst-line)' }} />

    {/* Content grid: mapa mental + flashcard + questão */}
    <div className="grid grid-cols-2 gap-3">
      {/* Mapa mental */}
      <div
        className="col-span-2 md:col-span-1 rounded-lg p-3.5"
        style={{ background: '#FAF8F4', border: '1px solid var(--mf-inst-line)' }}
      >
        <p className="text-[10.5px] font-semibold uppercase tracking-widest" style={{ color: 'var(--mf-inst-muted)' }}>
          Mapa mental
        </p>
        <div
          className="mt-2 text-[11.5px] leading-[1.65] font-mono"
          style={{ color: 'var(--mf-inst-ink)' }}
        >
          <div>- Ciclo de Krebs</div>
          <div className="pl-3">- Local: matriz mitocondrial</div>
          <div className="pl-3">- Entrada: acetil-CoA</div>
          <div className="pl-3">- 8 reações</div>
          <div className="pl-6" style={{ color: 'var(--mf-brand)' }}>
            - Citrato sintase
          </div>
          <div className="pl-6">- Isocitrato DH · α-KG DH</div>
          <div className="pl-3">- Rendimento: 3 NADH · 1 FADH₂ · 1 GTP</div>
        </div>
      </div>

      {/* Flashcard */}
      <div className="rounded-lg p-3.5" style={{ background: '#FFFFFF', border: '1px solid var(--mf-inst-line-2)' }}>
        <div className="flex items-center justify-between">
          <p className="text-[10.5px] font-semibold uppercase tracking-widest" style={{ color: 'var(--mf-inst-muted)' }}>
            Flashcard · 03 / 06
          </p>
          <span className="text-[10.5px]" style={{ color: 'var(--mf-brand)' }}>frente</span>
        </div>
        <p className="mt-2.5 text-[13px] font-medium leading-snug" style={{ color: 'var(--mf-inst-ink)' }}>
          Qual enzima liga o Ciclo de Krebs à cadeia respiratória?
        </p>
        <div className="mt-3 pt-2 flex items-center gap-2 text-[11px]" style={{ color: 'var(--mf-inst-muted)', borderTop: '1px dashed var(--mf-inst-line)' }}>
          <span>tocar para virar</span>
        </div>
      </div>

      {/* Questão inédita */}
      <div className="rounded-lg p-3.5" style={{ background: '#FFFFFF', border: '1px solid var(--mf-inst-line-2)' }}>
        <p className="text-[10.5px] font-semibold uppercase tracking-widest" style={{ color: 'var(--mf-inst-muted)' }}>
          Questão · inédita
        </p>
        <p className="mt-2 text-[12px] leading-snug" style={{ color: 'var(--mf-inst-ink)' }}>
          Paciente alcoolista, confusão + ataxia. Piruvato e α-KG elevados. Qual deficiência?
        </p>
        <div className="mt-2.5 space-y-1 text-[11.5px]" style={{ color: 'var(--mf-inst-ink-2)' }}>
          <div className="flex items-center gap-2">
            <span
              className="w-4 h-4 rounded-full inline-flex items-center justify-center text-[9px] font-semibold"
              style={{ background: 'var(--mf-brand)', color: '#FFFFFF' }}
            >
              A
            </span>
            <span style={{ color: 'var(--mf-brand)', fontWeight: 500 }}>Tiamina (B1)</span>
          </div>
          <div className="flex items-center gap-2 opacity-55">
            <span
              className="w-4 h-4 rounded-full inline-flex items-center justify-center text-[9px] font-semibold"
              style={{ background: '#EDE9E1', color: 'var(--mf-inst-muted)' }}
            >
              B
            </span>
            <span>Riboflavina (B2)</span>
          </div>
        </div>
      </div>
    </div>

    {/* Rodapé: opções de aprofundamento */}
    <div className="mt-4 flex flex-wrap gap-1.5">
      {[
        'Revisão Completa',
        'Explicação',
        'Flashcards',
        'Questões',
        'Caso clínico',
      ].map((label, i) => (
        <span
          key={label}
          className="inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[11px]"
          style={{
            background: i === 0 ? 'var(--mf-brand-soft)' : '#F6F3ED',
            color: i === 0 ? 'var(--mf-brand)' : 'var(--mf-inst-ink-2)',
            border: i === 0 ? '1px solid var(--mf-brand)' : '1px solid var(--mf-inst-line-2)',
            fontWeight: i === 0 ? 600 : 500,
          }}
        >
          {i === 0 && <Sparkles strokeWidth={2.5} className="w-2.5 h-2.5" />}
          {label}
        </span>
      ))}
    </div>
  </Chrome>
);

// ─── Seção 1: "Conheça o Tutor IA" ──────────────────────────
export const PreceptorShowcase = ({ onCta }) => (
  <section
    data-testid="landing-preceptor-showcase"
    className="py-28 md:py-44 relative overflow-hidden"
    style={{
      background: 'var(--mf-inst-bg)',
      borderTop: '1px solid var(--mf-inst-line)',
    }}
  >
    {/* Glow discreto de fundo */}
    <span
      aria-hidden="true"
      className="hidden md:block absolute -z-10 rounded-full blur-3xl"
      style={{
        top: '10%',
        left: '55%',
        width: 620,
        height: 620,
        background: 'radial-gradient(closest-side, rgba(108,92,231,0.14), transparent 72%)',
      }}
    />

    <div className="max-w-[1240px] mx-auto px-6 md:px-10">
      <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,0.95fr)] gap-14 lg:gap-20 items-center">
        {/* Coluna esquerda — mockup gigante do Tutor */}
        <div className="order-2 lg:order-1">
          <PreceptorInterface />
        </div>

        {/* Coluna direita — headline + capacidades + CTA */}
        <div className="order-1 lg:order-2">
          <p
            className="text-[11.5px] font-semibold uppercase tracking-widest"
            style={{ color: 'var(--mf-brand)', letterSpacing: '0.22em' }}
          >
            <span>Conheça o Tutor IA</span>
          </p>

          <h2
            className="mt-5 font-semibold tracking-tight leading-[1.03]"
            style={{
              fontSize: 'clamp(34px, 4.6vw, 60px)',
              letterSpacing: '-0.035em',
              color: 'var(--mf-inst-ink)',
            }}
          >
            <span>O MedFlow não responde</span>
            <br />
            <span>apenas perguntas. </span>
            <span style={{ color: 'var(--mf-brand)' }}>
              Ele ensina até você entender.
            </span>
          </h2>

          <p
            className="mt-7 text-[16.5px] leading-[1.7] max-w-lg"
            style={{ color: 'var(--mf-inst-ink-2)' }}
          >
            <span>
              Um mentor calibrado para Medicina brasileira. Traz explicação, resumo, mapa
              mental, flashcards, questões inéditas e casos clínicos — em uma única
              solicitação, do fundamento ao raciocínio da prova.
            </span>
          </p>

          {/* Capacidades — grid 2 x 3 */}
          <ul
            className="mt-10 pt-8 grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-4"
            style={{ borderTop: '1px solid var(--mf-inst-line)' }}
          >
            {PRECEPTOR_CAPS.map((c) => (
              <li key={c.k} className="flex items-start gap-3">
                <span
                  className="mt-0.5 w-5 h-5 rounded-full inline-flex items-center justify-center shrink-0"
                  style={{ background: 'var(--mf-brand)' }}
                >
                  <Check strokeWidth={3} className="w-3 h-3 text-white" />
                </span>
                <div>
                  <p
                    className="text-[14.5px] font-semibold tracking-tight leading-tight"
                    style={{ color: 'var(--mf-inst-ink)', letterSpacing: '-0.005em' }}
                  >
                    <span>{c.label}</span>
                  </p>
                  <p className="mt-0.5 text-[12.5px]" style={{ color: 'var(--mf-inst-muted)' }}>
                    <span>{c.hint}</span>
                  </p>
                </div>
              </li>
            ))}
          </ul>

          <div className="mt-10">
            <button
              data-testid="landing-preceptor-cta"
              onClick={onCta}
              className="inline-flex items-center gap-2 px-5 py-3 text-[14px] font-medium text-white"
              style={{ background: 'var(--mf-brand)', borderRadius: 6 }}
            >
              <span>Conversar com o Tutor</span>
              <ArrowRight strokeWidth={2} className="w-4 h-4" />
            </button>
            <p className="mt-3 text-[12px]" style={{ color: 'var(--mf-inst-muted)' }}>
              <span>Grátis para começar · Powered by Claude Sonnet 4.5</span>
            </p>
          </div>
        </div>
      </div>
    </div>
  </section>
);

// ─── Loading intelligent-processing (usado no Experience) ──────
const LoadingCard = () => {
  const [stageIdx, setStageIdx] = useState(0);
  const [done, setDone] = useState(false);
  const ref = useRef(null);
  const startedRef = useRef(false);

  useEffect(() => {
    // Só inicia quando entra na viewport
    const el = ref.current;
    if (!el) return;
    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (e.isIntersecting && !startedRef.current) {
            startedRef.current = true;
          }
        });
      },
      { threshold: 0.35 }
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);

  useEffect(() => {
    let cancelled = false;
    const tick = async () => {
      // aguarda entrar na viewport
      while (!startedRef.current && !cancelled) {
        await new Promise((r) => setTimeout(r, 200));
      }
      if (cancelled) return;
      for (let i = 0; i < PRECEPTOR_LOADING_STAGES.length; i++) {
        if (cancelled) return;
        setStageIdx(i);
        await new Promise((r) => setTimeout(r, 1250));
      }
      if (!cancelled) {
        setDone(true);
        // Reinicia após 4s
        setTimeout(() => {
          if (!cancelled) {
            setDone(false);
            setStageIdx(0);
            startedRef.current = true;
            tick();
          }
        }, 4200);
      }
    };
    tick();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div
      ref={ref}
      className="w-full max-w-md"
      data-testid="preceptor-loading"
      style={{
        background: '#FFFFFF',
        border: '1px solid var(--mf-inst-line-2)',
        borderRadius: 12,
        padding: 24,
        boxShadow: '0 20px 60px -20px rgba(20,20,40,0.16)',
      }}
    >
      <div className="flex items-center gap-2.5">
        <span
          className="w-7 h-7 rounded-md inline-flex items-center justify-center"
          style={{ background: 'var(--mf-brand-soft)' }}
        >
          <Sparkles strokeWidth={2} className="w-3.5 h-3.5" style={{ color: 'var(--mf-brand)' }} />
        </span>
        <p
          className="text-[11.5px] font-semibold uppercase tracking-widest"
          style={{ color: 'var(--mf-inst-muted)', letterSpacing: '0.16em' }}
        >
          <span>{done ? 'Revisão concluída' : 'Tutor trabalhando'}</span>
        </p>
      </div>

      <ol className="mt-5 space-y-2.5">
        {PRECEPTOR_LOADING_STAGES.map((label, i) => {
          const isDone = done || i < stageIdx;
          const isActive = !done && i === stageIdx;
          return (
            <li
              key={label}
              className="flex items-center gap-3 text-[13.5px] transition-opacity duration-500"
              style={{
                opacity: isDone || isActive ? 1 : 0.35,
                color: isDone
                  ? 'var(--mf-inst-ink)'
                  : isActive
                  ? 'var(--mf-inst-ink)'
                  : 'var(--mf-inst-muted)',
              }}
              data-testid={`preceptor-stage-${i}`}
            >
              <span
                className="w-5 h-5 rounded-full inline-flex items-center justify-center shrink-0 transition-colors"
                style={{
                  background: isDone
                    ? 'var(--mf-brand)'
                    : isActive
                    ? 'var(--mf-brand-soft)'
                    : '#EDE9E1',
                }}
              >
                {isDone ? (
                  <Check strokeWidth={3} className="w-3 h-3 text-white" />
                ) : isActive ? (
                  <span
                    className="w-2 h-2 rounded-full"
                    style={{
                      background: 'var(--mf-brand)',
                      animation: 'pulse-soft 1.2s ease-in-out infinite',
                    }}
                  />
                ) : (
                  <span
                    className="w-1.5 h-1.5 rounded-full"
                    style={{ background: 'var(--mf-inst-muted)', opacity: 0.4 }}
                  />
                )}
              </span>
              <span style={{ fontWeight: isActive ? 500 : 400 }}>{label}</span>
            </li>
          );
        })}
      </ol>

      {done && (
        <div
          className="mt-6 pt-4 flex items-center justify-between"
          style={{ borderTop: '1px solid var(--mf-inst-line)' }}
        >
          <p className="text-[12px]" style={{ color: 'var(--mf-inst-muted)' }}>
            <span>Explicação · Resumo · Mapa · Flashcards · Questões · Caso</span>
          </p>
          <span
            className="inline-flex items-center gap-1 text-[11.5px]"
            style={{ color: 'var(--mf-brand)', fontWeight: 600 }}
          >
            <Check strokeWidth={3} className="w-3 h-3" />
            <span>pronto</span>
          </span>
        </div>
      )}

      <style>{`
        @keyframes pulse-soft {
          0%, 100% { transform: scale(1); opacity: 0.9; }
          50% { transform: scale(1.35); opacity: 0.4; }
        }
      `}</style>
    </div>
  );
};

// ─── Seção 2: Sequência tipo Apple do fluxo do Tutor ──────
export const PreceptorExperience = ({ onCta }) => (
  <section
    data-testid="landing-preceptor-experience"
    className="py-28 md:py-44"
    style={{
      background: '#FFFFFF',
      borderTop: '1px solid var(--mf-inst-line)',
      borderBottom: '1px solid var(--mf-inst-line)',
    }}
  >
    <div className="max-w-[1240px] mx-auto px-6 md:px-10">
      {/* Cabeçalho editorial */}
      <div className="max-w-3xl">
        <p
          className="text-[11.5px] font-semibold uppercase tracking-widest"
          style={{ color: 'var(--mf-brand)', letterSpacing: '0.22em' }}
        >
          <span>a experiência</span>
        </p>
        <h2
          className="mt-5 font-semibold tracking-tight leading-[1.05]"
          style={{
            fontSize: 'clamp(32px, 4.4vw, 56px)',
            letterSpacing: '-0.035em',
            color: 'var(--mf-inst-ink)',
          }}
        >
          <span>Uma pergunta.</span>
          <br />
          <span style={{ color: 'var(--mf-brand)' }}>Oito superfícies de aprendizado.</span>
        </h2>
        <p
          className="mt-6 text-[16.5px] leading-relaxed max-w-2xl"
          style={{ color: 'var(--mf-inst-ink-2)' }}
        >
          <span>
            O Tutor não devolve um bloco de texto. Ele conduz um raciocínio — do
            entendimento ao caso clínico — em segundos, dentro da interface.
          </span>
        </p>
      </div>

      {/* Loading demo cinematográfico */}
      <div className="mt-16 md:mt-24 flex justify-center">
        <LoadingCard />
      </div>

      {/* Sequência de 8 passos — grid editorial */}
      <ol className="mt-20 md:mt-28 grid grid-cols-1 md:grid-cols-2 gap-x-16 gap-y-10">
        {PRECEPTOR_FLOW.map((f, i) => (
          <li
            key={f.k}
            className="grid grid-cols-[auto_1fr] gap-5 items-baseline"
            data-testid={`preceptor-flow-${f.k}`}
          >
            <span
              className="display-num"
              style={{
                fontSize: 'clamp(28px, 3vw, 40px)',
                color: i === PRECEPTOR_FLOW.length - 1 ? 'var(--mf-brand)' : 'var(--mf-inst-muted)',
                opacity: i === PRECEPTOR_FLOW.length - 1 ? 1 : 0.55,
                minWidth: 60,
              }}
            >
              {f.step}
            </span>
            <div
              className="pb-6"
              style={{ borderBottom: '1px solid var(--mf-inst-line)' }}
            >
              <p
                className="font-semibold tracking-tight"
                style={{
                  fontSize: 'clamp(17px, 1.8vw, 22px)',
                  letterSpacing: '-0.02em',
                  color: 'var(--mf-inst-ink)',
                }}
              >
                <span>{f.title}</span>
              </p>
              <p
                className="mt-1.5 text-[14px] leading-relaxed max-w-md"
                style={{ color: 'var(--mf-inst-muted)' }}
              >
                <span>{f.hint}</span>
              </p>
            </div>
          </li>
        ))}
      </ol>

      {/* CTA final da seção */}
      <div className="mt-20 md:mt-24 flex justify-center">
        <button
          data-testid="landing-experience-cta"
          onClick={onCta}
          className="inline-flex items-center gap-2 px-6 py-3.5 text-[14px] font-medium text-white"
          style={{ background: 'var(--mf-brand)', borderRadius: 8 }}
        >
          <span>Experimentar o Tutor</span>
          <ArrowRight strokeWidth={2} className="w-4 h-4" />
        </button>
      </div>
    </div>
  </section>
);
