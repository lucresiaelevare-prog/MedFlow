import React from 'react';

/**
 * <IconBubble> — círculo colorido semântico contendo um ícone lucide.
 *
 * Uso padrão em cabeçalhos de card, CTAs e alertas.
 *
 * Props:
 *  - icon: componente lucide-react (obrigatório)
 *  - tone: 'brand' | 'success' | 'attention' | 'care' | 'muted' (default 'brand')
 *  - size: 'sm' (32px) | 'md' (40px, default) | 'lg' (48px)
 *
 * Ver /app/docs/design-system.md §2, §9, §7.
 */
const TONE = {
  brand:     { bg: 'var(--mf-brand-soft)',     fg: 'var(--mf-brand)' },
  success:   { bg: 'var(--mf-success-soft)',   fg: 'var(--mf-success)' },
  attention: { bg: 'var(--mf-attention-soft)', fg: '#B37109' },
  care:      { bg: 'var(--mf-care-soft)',      fg: 'var(--mf-care)' },
  muted:     { bg: 'var(--mf-surface-2)',      fg: 'var(--mf-muted)' },
};

const SIZE = {
  sm: { box: 'w-8 h-8',   icon: 'w-4 h-4' },
  md: { box: 'w-10 h-10', icon: 'w-5 h-5' },
  lg: { box: 'w-12 h-12', icon: 'w-6 h-6' },
};

const IconBubble = ({ icon: Icon, tone = 'brand', size = 'md', className = '', strokeWidth = 1.5, ...rest }) => {
  const t = TONE[tone] || TONE.brand;
  const s = SIZE[size] || SIZE.md;
  return (
    <div
      className={`${s.box} rounded-xl flex items-center justify-center shrink-0 ${className}`}
      style={{ background: t.bg }}
      {...rest}
    >
      {Icon ? <Icon strokeWidth={strokeWidth} className={s.icon} style={{ color: t.fg }} /> : null}
    </div>
  );
};

export default IconBubble;
