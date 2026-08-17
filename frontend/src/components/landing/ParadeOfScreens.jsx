import { SCREENS } from './data';

/**
 * Parade of Screens — Onda 4.
 * Cinco superfícies reais do produto em alternância editorial.
 * Cada slide: número + kicker + headline + prosa curta + micro-benefícios + captura real
 * apresentada dentro de um "browser chrome" institucional.
 * Sem cards flutuantes, sem gradientes. Muito respiro, tipografia cinematográfica.
 */

// ─── Browser chrome (macOS-style, minimalista) ─────────────────
const BrowserChrome = ({ children, testId }) => (
  <div
    data-testid={testId}
    className="w-full"
    style={{
      borderRadius: 12,
      border: '1px solid var(--mf-inst-line-2)',
      background: '#FFFFFF',
      boxShadow: '0 30px 80px -30px rgba(20,20,40,0.22), 0 12px 32px -18px rgba(20,20,40,0.12)',
      overflow: 'hidden',
    }}
  >
    {/* Barra do "browser" */}
    <div
      className="flex items-center gap-1.5 px-3.5 py-2.5"
      style={{
        background: '#F6F3ED',
        borderBottom: '1px solid var(--mf-inst-line)',
      }}
    >
      <span className="w-2.5 h-2.5 rounded-full" style={{ background: '#E4DFD6' }} />
      <span className="w-2.5 h-2.5 rounded-full" style={{ background: '#E4DFD6' }} />
      <span className="w-2.5 h-2.5 rounded-full" style={{ background: '#E4DFD6' }} />
      <span
        className="ml-3 inst-readout"
        style={{ color: 'var(--mf-inst-muted)', fontSize: 10.5 }}
      >
        medflow.app
      </span>
    </div>
    {/* Conteúdo */}
    <div className="relative w-full" style={{ aspectRatio: '16 / 10' }}>
      {children}
    </div>
  </div>
);

// ─── Slide individual ──────────────────────────────────────────
const ScreenSlide = ({ screen, index }) => {
  const reversed = index % 2 === 1;
  const num = String(index + 1).padStart(2, '0');
  return (
    <li
      className="grid grid-cols-1 md:grid-cols-2 gap-12 md:gap-20 items-center"
      data-testid={`landing-screen-${screen.k}`}
    >
      {/* Imagem */}
      <div className={reversed ? 'md:order-2' : ''}>
        <BrowserChrome testId={`landing-screen-${screen.k}-frame`}>
          <img
            src={screen.img}
            alt={screen.alt}
            loading="lazy"
            className="absolute inset-0 w-full h-full"
            style={{ objectFit: 'cover', objectPosition: 'top left' }}
          />
        </BrowserChrome>
      </div>

      {/* Texto */}
      <div className={reversed ? 'md:order-1' : ''}>
        <div className="flex items-baseline gap-4">
          <span
            className="display-num"
            style={{
              fontSize: 'clamp(30px, 3.4vw, 44px)',
              color: 'var(--mf-inst-muted)',
              opacity: 0.55,
              minWidth: 60,
            }}
          >
            {num}
          </span>
          <p className="inst-readout" style={{ color: 'var(--mf-brand)' }}>
            <span>{screen.kicker}</span>
          </p>
        </div>

        <h3
          className="mt-5 font-semibold tracking-tight leading-[1.05] whitespace-pre-line"
          style={{
            fontSize: 'clamp(26px, 3.4vw, 42px)',
            letterSpacing: '-0.03em',
            color: 'var(--mf-inst-ink)',
          }}
        >
          {screen.title}
        </h3>

        <p
          className="mt-5 text-[16px] leading-[1.7] max-w-lg"
          style={{ color: 'var(--mf-inst-ink-2)' }}
        >
          <span>{screen.body}</span>
        </p>

        <ul
          className="mt-8 pt-6 flex flex-wrap items-center gap-x-5 gap-y-2.5 text-[13px]"
          style={{ borderTop: '1px solid var(--mf-inst-line)', color: 'var(--mf-inst-muted)' }}
        >
          {screen.bullets.map((b) => (
            <li key={b} className="inline-flex items-center gap-1.5">
              <span
                className="w-1 h-1 rounded-full"
                style={{ background: 'var(--mf-brand)' }}
                aria-hidden="true"
              />
              <span>{b}</span>
            </li>
          ))}
        </ul>
      </div>
    </li>
  );
};

// ─── Bloco completo ────────────────────────────────────────────
export const ParadeOfScreens = () => (
  <section
    data-testid="landing-parade"
    className="py-24 md:py-40"
    style={{
      background: 'var(--mf-inst-bg)',
      borderTop: '1px solid var(--mf-inst-line)',
      borderBottom: '1px solid var(--mf-inst-line)',
    }}
  >
    <div className="max-w-[1240px] mx-auto px-6 md:px-10">
      {/* Cabeçalho editorial */}
      <div className="max-w-3xl">
        <p className="inst-readout"><span>o produto · por dentro</span></p>
        <h2
          className="mt-5 font-semibold tracking-tight leading-[1.05]"
          style={{
            fontSize: 'clamp(30px, 4.2vw, 52px)',
            letterSpacing: '-0.035em',
            color: 'var(--mf-inst-ink)',
          }}
        >
          <span>Cinco superfícies.</span>
          <br />
          <span style={{ color: 'var(--mf-brand)' }}>Um único ritmo.</span>
        </h2>
        <p
          className="mt-6 text-[16.5px] leading-relaxed max-w-2xl"
          style={{ color: 'var(--mf-inst-ink-2)' }}
        >
          <span>
            Cada tela do MedFlow existe para te mostrar o próximo passo. Nada de dashboards
            saturados, gráficos ornamentais ou menus infinitos. Apenas o que aproxima
            você da próxima ação.
          </span>
        </p>
      </div>

      {/* Parade */}
      <ol className="mt-20 md:mt-28 space-y-24 md:space-y-32">
        {SCREENS.map((s, i) => (
          <ScreenSlide key={s.k} screen={s} index={i} />
        ))}
      </ol>
    </div>
  </section>
);
