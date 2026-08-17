import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ShieldCheck, ArrowRight, CheckCircle2,
  X, Sparkles, BookMarked, GraduationCap, Repeat, Compass, TrendingUp,
} from 'lucide-react';
import IDS from '@/constants/testIds';
import { useAuth } from '@/context/AuthContext';

/**
 * Landing v6 — Cinematic Institute.
 *
 * Diretrizes (rev. 2026-01):
 *  - Respiro luxo: 120-160px entre seções principais.
 *  - Tipografia cinematográfica: hero title 72-88px.
 *  - Mockups reais do produto (laptop 3D + phone), não cards flutuantes.
 *  - Menos cards, mais editorial: alternância imagem + texto.
 *  - Momento humano: prova institucional, foto real, números.
 *  - Palette única do sistema (violeta brand + navy + off-white quente).
 *  - Copy aprovada permanece intacta.
 */

// ─── Landing components extraídos ──────────────────────────────
import { CATEGORY, CREED, REASONING, FLOW, SIGNALS, DIFF } from '@/components/landing/data';
import { Wordmark, GoogleG } from '@/components/landing/primitives';
import { PhoneMockup } from '@/components/landing/PhoneMockup';
import { ParadeOfScreens } from '@/components/landing/ParadeOfScreens';
import { PreceptorShowcase, PreceptorExperience } from '@/components/landing/PreceptorSections';

// ─── Landing ───────────────────────────────────────────────────
const Landing = () => {
  const navigate = useNavigate();
  const { isAuthenticated } = useAuth();
  const [showPrivacy, setShowPrivacy] = useState(false);
  useEffect(() => {
    if (isAuthenticated) navigate('/dashboard', { replace: true });
  }, [isAuthenticated, navigate]);

  const handleLogin = () => {
    // REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
    const redirectUrl = window.location.origin + '/dashboard';
    window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
  };

  return (
    <div
      className="min-h-screen"
      style={{ background: 'var(--mf-inst-bg)', color: 'var(--mf-inst-ink)' }}
      translate="no"
    >
      {/* ─── Header ─── */}
      <header
        className="sticky top-0 z-30 backdrop-blur-sm"
        style={{
          background: 'rgba(250,248,244,0.88)',
          borderBottom: '1px solid var(--mf-inst-line)',
        }}
      >
        <div className="mx-auto flex h-16 max-w-[1240px] items-center justify-between px-4 sm:px-6 md:px-10">
          <Wordmark />
          <div className="flex items-center gap-4">
            <button
              data-testid={IDS.landing.googleLogin}
              onClick={() => navigate('/entrar')}
              className="inline-flex min-h-11 items-center gap-2 px-4 py-2 text-[14px] font-medium"
              style={{
                background: 'var(--mf-inst-surface)',
                border: '1px solid var(--mf-inst-line-2)',
                borderRadius: 6,
                color: 'var(--mf-inst-ink)',
              }}
            >
              <GoogleG /> <span>Entrar</span>
            </button>
          </div>
        </div>
      </header>

      {/* ═══════════════════════════════════════════════════════ */}
      {/* 01. HERO CINEMATOGRÁFICO — texto + browser lateral      */}
      {/* ═══════════════════════════════════════════════════════ */}
      <section className="pb-16 pt-10 md:pb-24 md:pt-20">
        <div className="mx-auto max-w-[1320px] px-4 sm:px-6 md:px-10">
          <div className="grid grid-cols-1 items-center gap-10 lg:grid-cols-[minmax(0,1.15fr)_minmax(0,0.95fr)] lg:gap-16">
            {/* Coluna esquerda — texto */}
            <div className="min-w-0">
              {/* Kicker — positioning line acima da headline */}
              <p
                className="reveal reveal-1 text-[14px] font-medium tracking-tight"
                style={{ color: 'var(--mf-inst-ink-2)', letterSpacing: '-0.005em' }}
                data-testid="landing-kicker"
              >
                <span>Feito para quem quer aprovar.</span>{' '}
                <span style={{ color: 'var(--mf-inst-muted)' }}>Não apenas estudar.</span>
              </p>

              <h1
                data-testid={IDS.landing.heroTitle}
                className="headline-xl reveal reveal-3 mt-4"
                style={{
                  fontSize: 'clamp(38px, 10vw, 84px)',
                  color: 'var(--mf-inst-ink)',
                }}
              >
                <span>Aprenda a estudar.</span>
                <br />
                <span style={{ color: 'var(--mf-brand)' }}>
                  <span>com esta nova ferramenta!</span>
                </span>
              </h1>

              <p
                className="reveal reveal-4 mt-7 max-w-xl leading-relaxed"
                style={{ fontSize: 'clamp(16px, 1.25vw, 19px)', color: 'var(--mf-inst-ink-2)' }}
              >
                <span>
                  O MedFlow interpreta seu contexto, sono, energia, provas, plantões e
                  tempo disponível, e responde uma única pergunta:{' '}
                </span>
                <span style={{ color: 'var(--mf-inst-ink)', fontWeight: 500 }}>
                  <span>o que faz mais sentido fazer agora?</span>
                </span>
              </p>

              <div className="reveal reveal-5 mt-8 flex flex-col items-stretch gap-3 sm:flex-row sm:items-center">
                <button
                  data-testid={IDS.landing.getStarted}
                  onClick={handleLogin}
                  className="inline-flex min-h-12 items-center justify-center gap-2 px-5 py-3 text-[16px] font-medium text-white sm:w-auto sm:text-[14px]"
                  style={{ background: 'var(--mf-brand)', borderRadius: 6 }}
                >
                  <span>Começar gratuitamente</span>
                  <ArrowRight strokeWidth={2} className="w-4 h-4" />
                </button>
                <button
                  data-testid={IDS.landing.googleLogin + '-hero'}
                  onClick={handleLogin}
                  className="inline-flex min-h-12 items-center justify-center gap-2 px-5 py-3 text-[16px] font-medium sm:w-auto sm:text-[14px]"
                  style={{
                    background: 'var(--mf-inst-surface)',
                    border: '1px solid var(--mf-inst-line-2)',
                    borderRadius: 6,
                    color: 'var(--mf-inst-ink)',
                  }}
                >
                  <GoogleG /> <span>Entrar com Google</span>
                </button>
              </div>
            </div>

            {/* Coluna direita — composição editorial: estudante + laptop do Preceptor */}
            <div className="reveal reveal-3 relative min-w-0">
              {/* Glow discreto atrás */}
              <span
                aria-hidden="true"
                className="hidden lg:block absolute -inset-8 -z-10 rounded-3xl"
                style={{
                  background:
                    'radial-gradient(50% 50% at 60% 40%, rgba(108,92,231,0.14), transparent 70%)',
                  filter: 'blur(24px)',
                }}
              />

              <div className="relative">
                {/* Foto editorial da estudante — background */}
                <div
                  className="photo-frame w-full mx-auto"
                  style={{ maxWidth: 560, aspectRatio: '5 / 4' }}
                  data-testid="landing-hero-portrait"
                >
                  <img
                    src="/brand/hero-student.png"
                    alt="Estudante de Medicina usando o MedFlow"
                    loading="eager"
                    style={{ objectPosition: 'center 40%' }}
                  />
                </div>

              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ═══════════════════════════════════════════════════════ */}
      {/* VALUE STRIP — benefícios de aprovação                    */}
      {/* ═══════════════════════════════════════════════════════ */}
      <section
        data-testid="landing-benefits"
        className="py-16 md:py-20"
        style={{ borderTop: '1px solid var(--mf-inst-line)', borderBottom: '1px solid var(--mf-inst-line)' }}
      >
        <div className="max-w-[1120px] mx-auto px-6 md:px-10">
          <div style={{ borderTop: '1px solid var(--mf-inst-line)' }}>
            {[
              [
                { text: 'Saiba exatamente o que estudar hoje',   Icon: Compass },
                { text: 'Aprenda com um Preceptor IA',            Icon: GraduationCap },
                { text: 'Nunca perca uma revisão',                Icon: Repeat },
              ],
              [
                { text: 'Questões com explicações inteligentes', Icon: Sparkles },
                { text: 'Evolua todos os dias',                   Icon: TrendingUp },
                { text: 'Estude com direção — não com esforço',   Icon: BookMarked },
              ],
            ].map((row, rowIdx) => (
              <div
                key={rowIdx}
                className="grid grid-cols-1 md:grid-cols-3 py-8 md:py-9"
                style={{ borderBottom: '1px solid var(--mf-inst-line)' }}
              >
                {row.map(({ text, Icon }) => (
                  <div
                    key={text}
                    className="flex items-center gap-3.5 px-2 md:px-6 py-2"
                  >
                    <span
                      className="w-8 h-8 rounded-md flex items-center justify-center shrink-0"
                      style={{ background: 'var(--mf-brand-soft)' }}
                    >
                      <Icon
                        strokeWidth={1.75}
                        className="w-4 h-4"
                        style={{ color: 'var(--mf-brand)' }}
                      />
                    </span>
                    <span
                      className="text-[15px] leading-snug"
                      style={{ color: 'var(--mf-inst-ink)', letterSpacing: '-0.005em' }}
                    >
                      {text}
                    </span>
                  </div>
                ))}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ═══════════════════════════════════════════════════════ */}
      {/* 02. MOMENTO HUMANO — "Feito para quem"                  */}
      {/* ═══════════════════════════════════════════════════════ */}
      <section
        data-testid="landing-audience"
        className="py-24 md:py-40"
        style={{ background: '#FFFFFF', borderBottom: '1px solid var(--mf-inst-line)' }}
      >
        <div className="max-w-[1240px] mx-auto px-6 md:px-10">
          <div className="grid grid-cols-1 md:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)] gap-14 md:gap-24 items-center">
            {/* Coluna imagem — foto Imagem 1 (comunidade médica com estetoscópio roxo) */}
            <div className="relative">
              <div className="photo-frame w-full aspect-[4/5]">
                <img
                  src="/brand/community-circle.png"
                  alt="Estudantes de Medicina reunidos com seus estetoscópios"
                  loading="lazy"
                  onError={(e) => { e.currentTarget.style.display = 'none'; }}
                />
              </div>

              <p className="mt-5 inst-readout text-center md:text-left">
                <span>uma jornada acompanhada · não uma promessa</span>
              </p>
            </div>

            {/* Coluna texto */}
            <div>
              <h2
                className="mt-6 font-semibold tracking-tight leading-[1.05]"
                style={{ fontSize: 'clamp(30px, 4.2vw, 52px)', letterSpacing: '-0.035em', color: 'var(--mf-inst-ink)' }}
              >
                <span>Um copiloto que te ajuda</span><br/>
                <span>a guiar seu caminho.</span>
              </h2>

              <div className="mt-8 space-y-6 max-w-xl">
                <p className="text-[16px] leading-[1.7]" style={{ color: 'var(--mf-inst-ink-2)' }}>
                  <span>
                    Aulas na parte da manhã. Plantão à noite. Provas espaçadas por semanas.
                    Cada dia acontece diferente. E a maior parte da sua energia se perde
                    tentando descobrir por onde começar.
                  </span>
                </p>
                <p className="text-[16px] leading-[1.7]" style={{ color: 'var(--mf-inst-ink-2)' }}>
                  <span>
                    O MedFlow foi construído para reduzir essa fricção. Ele não tenta te
                    convencer de nada.{' '}
                  </span>
                  <span style={{ color: 'var(--mf-inst-ink)', fontWeight: 500 }}>
                    <span>Apenas interpreta e recomenda a melhor estratégia para tornar
                    seu esforço diário mais eficiente.</span>
                  </span>
                </p>
              </div>

              <div
                className="mt-10 pt-8 grid grid-cols-3 gap-6"
                style={{ borderTop: '1px solid var(--mf-inst-line)' }}
              >
                {[
                  { k: 'Feito para', v: 'Medicina', sub: 'exclusivamente' },
                  { k: 'Sinais', v: '6', sub: 'analisados' },
                  { k: 'Sessão', v: '< 1min', sub: 'para começar' },
                ].map((m) => (
                  <div key={m.k}>
                    <p className="inst-readout"><span>{m.k}</span></p>
                    <p
                      className="mt-1.5 font-semibold tracking-tight"
                      style={{ fontSize: 26, letterSpacing: '-0.03em', color: 'var(--mf-inst-ink)' }}
                    >
                      <span>{m.v}</span>
                    </p>
                    <p className="text-[11.5px]" style={{ color: 'var(--mf-inst-muted)' }}>
                      <span>{m.sub}</span>
                    </p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ═══════════════════════════════════════════════════════ */}
      {/* 03. MÉTODO — editorial, não card                        */}
      {/* ═══════════════════════════════════════════════════════ */}
      <section
        data-testid="landing-method"
        className="py-24 md:py-40 relative overflow-hidden"
      >
        <span
          className="editorial-numeral absolute top-8 right-4 md:right-16"
          aria-hidden="true"
        >
          03
        </span>

        <div className="max-w-[1240px] mx-auto px-6 md:px-10 relative">
          <div className="grid grid-cols-1 md:grid-cols-[minmax(0,1fr)_minmax(0,340px)] gap-10 md:gap-14 items-end">
            <div>
              <h2
                className="font-semibold tracking-tight leading-[1.05] max-w-3xl"
                style={{ fontSize: 'clamp(32px, 4.6vw, 58px)', letterSpacing: '-0.035em', color: 'var(--mf-inst-ink)' }}
              >
                <span>Do contexto</span><br/>
                <span style={{ color: 'var(--mf-brand)' }}>à próxima ação.</span>
              </h2>
              <p className="mt-6 text-[16.5px] leading-relaxed max-w-2xl" style={{ color: 'var(--mf-inst-ink-2)' }}>
                <span>
                  Cada recomendação percorre o mesmo caminho, na mesma ordem. Sem
                  improviso, sem opinião, sem viés de humor.
                </span>
              </p>
            </div>

            {/* Foto lateral discreta — Método aplicado em ambiente acadêmico */}
            <div className="photo-frame w-full" style={{ aspectRatio: '4 / 5', maxHeight: 400 }}>
              <img
                src="/brand/anatomy-room.jpg"
                alt="Ambiente acadêmico de estudo, anatomia"
                loading="lazy"
              />
            </div>
          </div>

          {/* Timeline editorial — grande, sem cards */}
          <ol className="mt-16 md:mt-20 space-y-8 md:space-y-10 max-w-4xl">
            {FLOW.map((f, i) => (
              <li
                key={f.k}
                className="grid grid-cols-[auto_1fr] gap-6 md:gap-10 items-baseline"
              >
                <span
                  className="display-num"
                  style={{
                    fontSize: 'clamp(42px, 5vw, 68px)',
                    color: i === 2 ? 'var(--mf-brand)' : 'var(--mf-inst-muted)',
                    minWidth: 90,
                  }}
                >
                  {String(i + 1).padStart(2, '0')}
                </span>
                <div style={{ borderBottom: '1px solid var(--mf-inst-line)', paddingBottom: 24 }}>
                  <p
                    className="font-semibold tracking-tight"
                    style={{ fontSize: 'clamp(20px, 2.4vw, 28px)', letterSpacing: '-0.02em', color: 'var(--mf-inst-ink)' }}
                  >
                    <span>{f.label}</span>
                  </p>
                  <p className="mt-2 text-[15px] leading-relaxed max-w-xl" style={{ color: 'var(--mf-inst-muted)' }}>
                    <span>{f.hint}</span>
                  </p>
                </div>
              </li>
            ))}
          </ol>
        </div>
      </section>

      {/* ═══════════════════════════════════════════════════════ */}
      {/* 04. SINAIS — spec sheet + phone mockup                  */}
      {/* ═══════════════════════════════════════════════════════ */}
      <section
        data-testid="landing-signals"
        className="py-24 md:py-40"
        style={{ background: 'var(--mf-inst-navy)', color: '#FFFFFF' }}
      >
        <div className="max-w-[1240px] mx-auto px-6 md:px-10">
          <div className="grid grid-cols-1 md:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)] gap-14 md:gap-20 items-start">
            <div>
              <h2
                className="font-semibold tracking-tight leading-[1.05]"
                style={{ fontSize: 'clamp(32px, 4.6vw, 58px)', letterSpacing: '-0.035em' }}
              >
                <span>Seis sinais.</span>
                <br />
                <span style={{ color: '#A28CF5' }}>Um único mecanismo.</span>
              </h2>
              <p className="mt-6 text-[16px] leading-relaxed max-w-xl" style={{ color: 'rgba(255,255,255,0.7)' }}>
                <span>
                  Os sinais não são analisados isoladamente. São componentes de um
                  mesmo mecanismo. Combinam-se em tempo real para produzir um único
                  passo claro.
                </span>
              </p>

              {/* Spec sheet — cada sinal como linha, não card */}
              <ul
                className="mt-12 md:mt-16"
                style={{ borderTop: '1px solid rgba(255,255,255,0.08)' }}
              >
                {SIGNALS.map((s, i) => (
                  <li
                    key={s.k}
                    className="py-4 md:py-5 grid grid-cols-[auto_1fr_auto] gap-4 md:gap-6 items-center"
                    style={{ borderBottom: '1px solid rgba(255,255,255,0.08)' }}
                    data-testid={`landing-signal-${s.k}`}
                  >
                    <span
                      className="display-num text-white/40"
                      style={{ fontSize: 16, minWidth: 32 }}
                    >
                      {String(i + 1).padStart(2, '0')}
                    </span>
                    <div>
                      <p className="text-[16px] font-semibold tracking-tight">
                        <span>{s.label}</span>
                      </p>
                      <p className="text-[13px] mt-0.5" style={{ color: 'rgba(255,255,255,0.55)' }}>
                        <span>{s.hint}</span>
                      </p>
                    </div>
                    <span
                      className="inst-readout"
                      style={{ color: 'rgba(255,255,255,0.4)' }}
                    >
                      <span>{s.unit}</span>
                    </span>
                  </li>
                ))}
              </ul>
            </div>

            {/* Phone mockup */}
            <div className="flex justify-center md:justify-end">
              <div className="relative">
                <PhoneMockup />
                {/* Halo */}
                <span
                  aria-hidden="true"
                  className="absolute inset-0 -z-10 rounded-full blur-3xl"
                  style={{
                    background: 'radial-gradient(closest-side, rgba(108,92,231,0.32), transparent 70%)',
                    transform: 'scale(1.4)',
                  }}
                />
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ═══════════════════════════════════════════════════════ */}
      {/* BLOCO EMOCIONAL — transformação, entre Sinais e Diff    */}
      {/* ═══════════════════════════════════════════════════════ */}
      <section
        data-testid="landing-emotional"
        className="py-20 md:py-32"
        style={{ background: '#FFFFFF' }}
      >
        <div className="max-w-[1240px] mx-auto px-6 md:px-10">
          <div className="grid grid-cols-1 md:grid-cols-[minmax(0,1.05fr)_minmax(0,1fr)] gap-12 md:gap-20 items-center">
            {/* Foto — momento íntimo de estudo */}
            <div className="photo-frame w-full" style={{ aspectRatio: '4 / 3' }}>
              <img
                src="/brand/intimate-study.jpg"
                alt="Momento de estudo, presença e clareza"
                loading="lazy"
              />
            </div>

            {/* Texto — transformação */}
            <div>
              <h2
                className="font-semibold tracking-tight leading-[1.05]"
                style={{ fontSize: 'clamp(28px, 4vw, 48px)', letterSpacing: '-0.035em', color: 'var(--mf-inst-ink)' }}
              >
                <span>A aprovação começa</span><br />
                <span style={{ color: 'var(--mf-brand)' }}>muito antes da prova.</span>
              </h2>
              <p className="mt-6 text-[16.5px] leading-[1.7] max-w-lg" style={{ color: 'var(--mf-inst-ink-2)' }}>
                <span>
                  Ela começa quando você finalmente sabe qual é o próximo passo. O
                  MedFlow elimina a dúvida sobre o que estudar para que cada hora de
                  estudo tenha um propósito.
                </span>
              </p>

              <button
                data-testid="landing-emotional-cta"
                onClick={handleLogin}
                className="mt-8 inline-flex items-center gap-2 px-5 py-3 text-[14px] font-medium text-white"
                style={{ background: 'var(--mf-brand)', borderRadius: 6 }}
              >
                <span>Começar agora</span>
                <ArrowRight strokeWidth={2} className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      </section>

      {/* ═══════════════════════════════════════════════════════ */}
      {/* 04B. PARADE OF SCREENS — Onda 4                          */}
      {/* Cinco superfícies reais do produto, editorial            */}
      {/* ═══════════════════════════════════════════════════════ */}
      <ParadeOfScreens />

      {/* ═══════════════════════════════════════════════════════ */}
      {/* 05. DIFERENCIAIS                                        */}
      {/* ═══════════════════════════════════════════════════════ */}
      <section
        data-testid="landing-diff"
        className="py-24 md:py-40"
      >
        <div className="max-w-[1240px] mx-auto px-6 md:px-10">
          <div className="max-w-3xl">
            <h2
              className="font-semibold tracking-tight leading-[1.05]"
              style={{ fontSize: 'clamp(30px, 4.2vw, 52px)', letterSpacing: '-0.035em', color: 'var(--mf-inst-ink)' }}
            >
              <span>O que torna o MedFlow diferente.</span>
            </h2>
            <p className="mt-6 text-[16px] leading-relaxed max-w-2xl" style={{ color: 'var(--mf-inst-ink-2)' }}>
              <span>
                O MedFlow não pertence à categoria de aplicativos de organização de
                estudos. Pertence a uma categoria própria, orientada ao aprendizado.
              </span>
            </p>
          </div>

          <div className="mt-14 md:mt-16 grid grid-cols-1 md:grid-cols-2 gap-10 md:gap-16">
            {/* Coluna legado */}
            <div>
              <p className="inst-readout"><span>Ferramentas tradicionais</span></p>
              <ul className="mt-6 space-y-4">
                {DIFF.map((row, i) => (
                  <li
                    key={i}
                    className="flex items-center gap-3 pb-4"
                    style={{ borderBottom: '1px solid var(--mf-inst-line)' }}
                  >
                    <span
                      className="w-5 h-5 rounded-full flex items-center justify-center shrink-0"
                      style={{ background: 'var(--mf-inst-tint)' }}
                    >
                      <X strokeWidth={2.5} className="w-3 h-3" style={{ color: 'var(--mf-inst-muted)' }} />
                    </span>
                    <span className="text-[16px] leading-snug" style={{ color: 'var(--mf-inst-muted)' }}>
                      <span>{row.legacy}</span>
                    </span>
                  </li>
                ))}
              </ul>
            </div>

            {/* Coluna MedFlow */}
            <div
              className="p-8 md:p-10"
              style={{ background: '#FFFFFF', border: '1px solid var(--mf-inst-line)', borderRadius: 6 }}
            >
              <p className="inst-readout" style={{ color: 'var(--mf-brand)' }}><span>MedFlow</span></p>
              <ul className="mt-6 space-y-4">
                {DIFF.map((row, i) => (
                  <li
                    key={i}
                    className="flex items-center gap-3 pb-4"
                    style={{ borderBottom: i === DIFF.length - 1 ? 'none' : '1px solid var(--mf-inst-line)' }}
                  >
                    <span
                      className="w-5 h-5 rounded-full flex items-center justify-center shrink-0"
                      style={{ background: 'var(--mf-brand)' }}
                    >
                      <CheckCircle2 strokeWidth={2.5} className="w-3 h-3 text-white" />
                    </span>
                    <span className="text-[16px] font-medium leading-snug" style={{ color: 'var(--mf-inst-ink)' }}>
                      <span>{row.medflow}</span>
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      </section>

      {/* ═══════════════════════════════════════════════════════ */}
      {/* CTA CINEMATOGRÁFICO — Apple-style, entre Diff e Sust    */}
      {/* ═══════════════════════════════════════════════════════ */}
      <section
        data-testid="landing-cta-anchor"
        className="py-40 md:py-56"
        style={{ background: 'var(--mf-inst-bg)' }}
      >
        <div className="max-w-[1240px] mx-auto px-6 md:px-10 text-center">
          <p
            className="headline-xl mx-auto max-w-4xl"
            style={{
              fontSize: 'clamp(40px, 6vw, 88px)',
              color: 'var(--mf-inst-ink)',
            }}
          >
            <span>Aprenda a estudar</span>
            <br />
            <span style={{ color: 'var(--mf-brand)' }}>com esta nova ferramenta!</span>
          </p>

          <div className="mt-12 md:mt-16 flex justify-center">
            <button
              data-testid="landing-cta-anchor-btn"
              onClick={handleLogin}
              className="inline-flex items-center gap-2 px-7 py-4 text-[15px] font-medium text-white"
              style={{ background: 'var(--mf-brand)', borderRadius: 8 }}
            >
              <span>Começar gratuitamente</span>
              <ArrowRight strokeWidth={2} className="w-4 h-4" />
            </button>
          </div>
        </div>
      </section>

      {/* ═══════════════════════════════════════════════════════ */}
      {/* 06. PERFORMANCE SEM ESGOTAMENTO                         */}
      {/* ═══════════════════════════════════════════════════════ */}
      <section
        data-testid="landing-sustainable"
        className="py-20 md:py-32"
        style={{ background: '#FFFFFF', borderTop: '1px solid var(--mf-inst-line)', borderBottom: '1px solid var(--mf-inst-line)' }}
      >
        <div className="max-w-[1240px] mx-auto px-6 md:px-10">
          <div className="grid grid-cols-1 md:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)] gap-12 md:gap-24">
            <div>
              <h2
                className="font-semibold tracking-tight leading-[1.05]"
                style={{ fontSize: 'clamp(28px, 3.8vw, 46px)', letterSpacing: '-0.03em', color: 'var(--mf-inst-ink)' }}
              >
                <span>Performance sem esgotamento.</span>
              </h2>

              {/* Foto lateral — o cansaço da força de vontade sem sistema */}
              <div
                className="photo-frame w-full mt-8"
                style={{ aspectRatio: '4 / 3', maxWidth: 380 }}
              >
                <img
                  src="/brand/chaos-notes.jpg"
                  alt="Anotações espalhadas em rotina de estudo"
                  loading="lazy"
                />
              </div>
            </div>
            <div className="max-w-xl">
              <p className="text-[17px] leading-[1.7]" style={{ color: 'var(--mf-inst-ink-2)' }}>
                <span>
                  O MedFlow considera sono, energia, carga cognitiva, plantões e contexto
                  para ajudar você a evoluir de forma consistente.
                </span>
              </p>
              <p className="mt-5 text-[17px] leading-[1.7]" style={{ color: 'var(--mf-inst-muted)' }}>
                <span>Porque aprender melhor é mais importante do que estudar mais.</span>
              </p>

              <ul
                className="mt-10 pt-7 flex flex-wrap items-center gap-x-6 gap-y-2 text-[13px]"
                style={{ borderTop: '1px solid var(--mf-inst-line)', color: 'var(--mf-inst-muted)' }}
              >
                {['Sem cronogramas rígidos', 'Sem culpa', 'Sem romantizar esforço'].map((t) => (
                  <li key={t} className="inline-flex items-center gap-1.5">
                    <span
                      className="w-1 h-1 rounded-full"
                      style={{ background: 'var(--mf-inst-clinical)' }}
                      aria-hidden="true"
                    />
                    <span>{t}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      </section>

      {/* ═══════════════════════════════════════════════════════ */}
      {/* 08. MANIFESTO — cinematográfico                          */}
      {/* ═══════════════════════════════════════════════════════ */}
      <section
        data-testid="landing-manifesto"
        className="py-32 md:py-52"
        style={{ background: 'var(--mf-inst-navy)', color: '#FFFFFF' }}
      >
        <div className="max-w-[1240px] mx-auto px-6 md:px-10">
          <div className="max-w-3xl">
            <p
              className="font-semibold tracking-tight leading-[1.05]"
              style={{ fontSize: 'clamp(36px, 5.4vw, 72px)', letterSpacing: '-0.04em' }}
            >
              <span>Estudar Medicina</span><br/>
              <span>nunca foi apenas memorizar.</span>
              <br />
              <span style={{ color: '#A28CF5' }}><span>É aprender a estudar.</span></span>
            </p>

            <div className="mt-12 md:mt-16 space-y-2.5 text-[17px] md:text-[19px] leading-[1.8]" style={{ color: 'rgba(255,255,255,0.75)' }}>
              <p><span>Todos os dias.</span></p>
              <p><span>O que revisar.</span></p>
              <p><span>Quando descansar.</span></p>
              <p><span>Quando insistir.</span></p>
              <p><span>Quando desacelerar.</span></p>
            </div>

            <p className="mt-16 text-[16.5px] leading-relaxed max-w-2xl" style={{ color: 'rgba(255,255,255,0.55)' }}>
              <span>
                Nós acreditamos que nada disso deveria depender apenas da força de vontade.
              </span>
            </p>
            <p
              className="mt-4 text-[17px] font-medium leading-relaxed max-w-2xl"
              style={{ color: '#FFFFFF' }}
            >
              <span>Por isso criamos o MedFlow.</span>
            </p>

            <p
              data-testid="landing-creed-manifesto"
              className="mt-14 italic text-[14.5px]"
              style={{ color: 'rgba(255,255,255,0.5)', borderLeft: '2px solid #A28CF5', paddingLeft: 14 }}
            >
              <span>{CREED}</span>
            </p>
          </div>
        </div>
      </section>

      {/* ═══════════════════════════════════════════════════════ */}
      {/* Footer                                                  */}
      {/* ═══════════════════════════════════════════════════════ */}
      <footer
        data-testid="landing-footer"
        className="py-12"
        style={{ borderTop: '1px solid var(--mf-inst-line)' }}
      >
        <div className="max-w-[1240px] mx-auto px-6 md:px-10">
          <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
            <div className="flex items-center gap-6">
              <Wordmark />
              <span className="inst-readout"><span>MF · 2026</span></span>
            </div>
            <div className="flex items-center gap-5 text-[12px]" style={{ color: 'var(--mf-inst-muted)' }}>
              <button
                type="button"
                onClick={() => setShowPrivacy(true)}
                className="hover:opacity-70 text-left"
              >
                <span>Privacidade</span>
              </button>
              <button
                type="button"
                onClick={() => setShowPrivacy(true)}
                className="hover:opacity-70 text-left"
              >
                <span>LGPD</span>
              </button>
              <a href="mailto:contato@medflow.app" className="hover:opacity-70"><span>Contato</span></a>
              <a
                href="/admin-login"
                className="hover:opacity-70"
                title="Acesso do painel administrativo"
              >
                <span>Admin</span>
              </a>
            </div>
          </div>

          {/* Segunda linha do rodapé */}
          <div
            className="mt-8 pt-6 flex flex-wrap items-center gap-x-5 gap-y-2 text-[11.5px]"
            style={{ borderTop: '1px solid var(--mf-inst-line)', color: 'var(--mf-inst-muted)' }}
          >
            <span className="inline-flex items-center gap-1.5">
              <ShieldCheck strokeWidth={1.75} className="w-3.5 h-3.5" style={{ color: 'var(--mf-brand)' }} />
              <span>Protegido pela LGPD</span>
            </span>

            {/* Modal de privacidade — abre quando "Privacidade" ou "LGPD" é clicado */}
            {showPrivacy && (
              <div
                role="dialog"
                aria-modal="true"
                aria-labelledby="privacy-modal-title"
                className="fixed inset-0 z-50 flex items-center justify-center p-4"
                style={{ background: 'rgba(15,15,20,0.55)' }}
                onClick={() => setShowPrivacy(false)}
              >
                <div
                  className="max-w-lg w-full rounded-xl p-6 md:p-7"
                  style={{ background: 'var(--mf-inst-surface)', border: '1px solid var(--mf-inst-line)' }}
                  onClick={(e) => e.stopPropagation()}
                >
                  <h3 id="privacy-modal-title" className="text-[17px] font-semibold" style={{ color: 'var(--mf-inst-ink)' }}>Privacidade e LGPD</h3>
                  <div className="mt-3 space-y-3 text-[13.5px] leading-relaxed" style={{ color: 'var(--mf-inst-ink-2)' }}>
                    <p>
                      O MedFlow coleta apenas dados necessários ao funcionamento do produto:
                      informações da conta, dados de estudo, check-ins de rotina e preferências
                      de perfil. Nenhum conteúdo médico sensível é compartilhado com terceiros.
                    </p>
                    <p>
                      Seus dados são tratados em conformidade com a Lei Geral de Proteção de
                      Dados (Lei nº 13.709/2018). Você pode solicitar acesso, correção ou
                      exclusão dos seus dados a qualquer momento.
                    </p>
                    <p>
                      Para solicitações relacionadas a privacidade, entre em contato pelo e-mail
                      <a href="mailto:contato@medflow.app" className="underline" style={{ color: 'var(--mf-brand)' }}> contato@medflow.app</a>.
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => setShowPrivacy(false)}
                    className="mt-5 px-4 py-2 text-[13.5px] font-medium text-white rounded-lg"
                    style={{ background: 'var(--mf-brand)' }}
                  >
                    Fechar
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </footer>
    </div>
  );
};

export default Landing;
