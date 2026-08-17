/**
 * <SoftProgress> — barra de progresso fina com cor semântica.
 *
 * Cor semântica automática por percentual (a menos que `tone` seja passado):
 *  - 0–34%  → care (crítico)
 *  - 35–59% → attention (atenção)
 *  - 60–79% → brand (no ritmo)
 *  - 80–100%→ success (excelente)
 *
 * Ver /app/docs/design-system.md §2, §7.
 */
const TONE_BY_PCT = (pct) => {
  if (pct >= 0.8) return 'success';
  if (pct >= 0.6) return 'brand';
  if (pct >= 0.35) return 'attention';
  return 'care';
};

const TONE_COLOR = {
  brand: 'var(--mf-brand)',
  success: 'var(--mf-success)',
  attention: 'var(--mf-attention)',
  care: 'var(--mf-care)',
};

const SoftProgress = ({
  value = 0,
  max = 100,
  tone: forcedTone,
  height = 6,
  className = '',
  'data-testid': testId,
  ...rest
}) => {
  const pct = max > 0 ? Math.max(0, Math.min(1, value / max)) : 0;
  const tone = forcedTone || TONE_BY_PCT(pct);
  return (
    <div
      className={`rounded-full overflow-hidden w-full ${className}`}
      style={{ height, background: 'var(--mf-hair)' }}
      role="progressbar"
      aria-valuenow={Math.round(pct * 100)}
      aria-valuemin={0}
      aria-valuemax={100}
      data-testid={testId}
      {...rest}
    >
      <div
        className="h-full rounded-full"
        style={{
          width: `${pct * 100}%`,
          background: TONE_COLOR[tone] || TONE_COLOR.brand,
          transition: `width var(--motion-slow) var(--ease-out), background-color var(--motion-fast) var(--ease-out)`,
        }}
      />
    </div>
  );
};

export default SoftProgress;
