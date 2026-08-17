/**
 * <Stat> — apresentação de número em destaque.
 *
 * Padrão: número tabular grande + label maiúsculo pequeno + sub (delta/hint).
 * Ver /app/docs/design-system.md §3, §7.
 *
 * Props:
 *  - value: string | number (obrigatório) — o número principal
 *  - unit: string opcional (ex.: '%', 'min', '/ 100')
 *  - label: string opcional — eyebrow acima do valor
 *  - sub: string opcional — hint abaixo (ex.: 'de 3', 'esta semana')
 *  - tone: 'default' | 'brand' | 'success' | 'attention' | 'care'
 *  - size: 'sm' | 'md' (default) | 'lg' | 'hero'
 */
const TONE = {
  default: 'var(--mf-ink)',
  brand: 'var(--mf-brand)',
  success: 'var(--mf-success)',
  attention: '#B37109',
  care: 'var(--mf-care)',
};

const SIZE_TOKEN = {
  sm:   'var(--text-2xl)',    // 19px
  md:   'var(--text-3xl)',    // 22px
  lg:   'var(--text-4xl)',    // 26px
  hero: 'var(--text-hero)',   // 52px
};

const Stat = ({ value, unit, label, sub, tone = 'default', size = 'md', className = '', ...rest }) => (
  <div className={className} {...rest}>
    {label && (
      <p className="eyebrow"><span>{label}</span></p>
    )}
    <p
      className="tabular font-semibold leading-none"
      style={{
        fontSize: SIZE_TOKEN[size] || SIZE_TOKEN.md,
        color: TONE[tone] || TONE.default,
        letterSpacing: '-0.02em',
        marginTop: label ? 'var(--space-2)' : 0,
      }}
    >
      <span>{value}</span>
      {unit && (
        <span
          className="font-normal"
          style={{ color: 'var(--mf-tertiary)', fontSize: `min(0.5em, 14px)`, marginLeft: '0.25em' }}
        >
          <span>{unit}</span>
        </span>
      )}
    </p>
    {sub && (
      <p
        style={{
          color: 'var(--mf-tertiary)',
          fontSize: 'var(--text-sm)',
          marginTop: 'var(--space-1)',
        }}
      >
        <span>{sub}</span>
      </p>
    )}
  </div>
);

export default Stat;
