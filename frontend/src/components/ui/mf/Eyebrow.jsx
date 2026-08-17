/**
 * <Eyebrow> — rótulo pequeno maiúsculo com espaçamento premium.
 *
 * Ver /app/docs/design-system.md §3 e §7.
 *
 * Variantes de tom:
 *  - default (`--mf-muted`)
 *  - brand   (`--mf-brand`)
 *  - success (`--mf-success`)
 *  - attention (#B37109)
 *  - care    (`--mf-care`)
 */
const TONE = {
  default: 'var(--mf-muted)',
  brand: 'var(--mf-brand)',
  success: 'var(--mf-success)',
  attention: '#B37109',
  care: 'var(--mf-care)',
};

const Eyebrow = ({ tone = 'default', children, className = '', ...rest }) => (
  <p
    className={`eyebrow ${className}`}
    style={{ color: TONE[tone] || TONE.default }}
    {...rest}
  >
    <span>{children}</span>
  </p>
);

export default Eyebrow;
