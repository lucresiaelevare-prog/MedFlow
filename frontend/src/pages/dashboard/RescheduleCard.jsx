import { useState } from 'react';
import {
  Wand2, Coffee, Clock, ArrowRight, ChevronDown, ChevronUp,
  Check, X, Undo2, Loader2,
} from 'lucide-react';
import api from '@/lib/api';

/**
 * RescheduleCard — "Eu reorganizei sua tarde."
 *
 * Consome home.today.reschedule (proposta pendente ou aplicada).
 * Salto de produto: o motor detecta fadiga/saturação E ATUA.
 *
 * Estados possíveis:
 *   pending   → apresenta ações + CTAs "Aplicar" | "Manter como estava"
 *   accepted  → apresenta o que foi aplicado + CTA "Desfazer"
 */

const REASON_TAG = {
  saturation: 'sobrecarga detectada',
  fatigue: 'sinais de cansaço',
};

const actionIcon = (type) => {
  if (type === 'insert') return Coffee;
  if (type === 'shorten') return Clock;
  return ArrowRight;
};

const actionLabel = (a) => {
  if (a.type === 'insert') {
    const b = a.block || {};
    return {
      title: b.title || 'Pausa restauradora',
      detail: `${b.start_time}–${b.end_time} · nova`,
    };
  }
  if (a.type === 'shorten') {
    return {
      title: a.title,
      detail: `${a.from_start}–${a.from_end}  →  ${a.to_start}–${a.to_end} · encurtado`,
    };
  }
  return {
    title: a.title,
    detail: `${a.from_start}–${a.from_end}  →  ${a.to_start}–${a.to_end} · adiado`,
  };
};

const RescheduleCard = ({ reschedule, onChanged }) => {
  const [expanded, setExpanded] = useState(false);
  const [busy, setBusy] = useState(null); // 'apply' | 'dismiss' | 'undo' | null

  if (!reschedule || !reschedule.actions?.length) return null;

  const isPending = reschedule.status === 'pending';
  const isAccepted = reschedule.status === 'accepted';

  const call = async (action) => {
    setBusy(action);
    try {
      await api.post(`/agenda/reschedule/${reschedule.id}/${action}`);
      if (onChanged) await onChanged();
    } finally {
      setBusy(null);
    }
  };

  return (
    <section
      data-testid="dashboard-reschedule"
      data-status={reschedule.status}
      data-reason={reschedule.reason}
      className="mt-4 md:mt-5 mf-card p-5 md:p-6"
      style={{
        borderLeft: '4px solid var(--mf-care, #F59E0B)',
        background: 'linear-gradient(0deg, var(--mf-care-soft, #FEF3C7) 0%, transparent 60%)',
      }}
      translate="no"
    >
      <div className="flex items-start gap-3">
        <div
          className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0"
          style={{ background: 'var(--mf-care-soft, #FEF3C7)', color: 'var(--mf-care, #B15437)' }}
        >
          <Wand2 strokeWidth={1.75} className="w-5 h-5" />
        </div>
        <div className="flex-1 min-w-0">
          <p
            data-testid="reschedule-tag"
            className="text-[11px] uppercase tracking-wider font-semibold"
            style={{ color: 'var(--mf-care, #B15437)' }}
          >
            <span>{REASON_TAG[reschedule.reason] || 'ajuste inteligente'}</span>
          </p>
          <p
            data-testid="reschedule-headline"
            className="mt-1 text-[17px] md:text-[19px] font-semibold text-zinc-900 leading-tight tracking-tight"
          >
            <span>{reschedule.headline}</span>
          </p>
          <p
            data-testid="reschedule-subline"
            className="mt-1.5 text-[13.5px] text-zinc-600 leading-relaxed"
          >
            <span>{reschedule.subline}</span>
          </p>
          <p
            data-testid="reschedule-summary"
            className="mt-2 text-[13px] text-zinc-500 leading-relaxed"
          >
            <span>{reschedule.summary}</span>
          </p>
        </div>
      </div>

      {/* Expand — ações detalhadas */}
      <button
        data-testid="reschedule-toggle"
        onClick={() => setExpanded((v) => !v)}
        className="mt-4 w-full flex items-center justify-center gap-1.5 py-2 text-[12.5px] text-zinc-500 hover:text-zinc-800 transition-colors"
        aria-expanded={expanded}
      >
        <span>{expanded ? 'Ocultar mudanças' : 'Ver mudanças'}</span>
        {expanded
          ? <ChevronUp strokeWidth={1.75} className="w-3.5 h-3.5" />
          : <ChevronDown strokeWidth={1.75} className="w-3.5 h-3.5" />}
      </button>

      <div
        data-testid="reschedule-actions"
        data-expanded={expanded}
        className="overflow-hidden transition-all duration-300"
        style={{ maxHeight: expanded ? '2000px' : '0', opacity: expanded ? 1 : 0 }}
        aria-hidden={!expanded}
      >
        <ul className="pt-2 space-y-2">
          {reschedule.actions.map((a, i) => {
            const Icon = actionIcon(a.type);
            const { title, detail } = actionLabel(a);
            return (
              <li
                key={i}
                data-testid={`reschedule-action-${i}`}
                data-type={a.type}
                className="flex items-start gap-2.5 p-2.5 rounded-lg bg-white/60 hairline"
              >
                <Icon
                  strokeWidth={1.75}
                  className="w-4 h-4 mt-0.5 shrink-0"
                  style={{ color: 'var(--mf-care, #B15437)' }}
                />
                <div className="flex-1 min-w-0">
                  <p className="text-[13px] font-medium text-zinc-900 truncate">
                    <span>{title}</span>
                  </p>
                  <p className="mt-0.5 text-[11.5px] text-zinc-500 mono">
                    <span>{detail}</span>
                  </p>
                </div>
              </li>
            );
          })}
        </ul>
      </div>

      {/* CTAs */}
      <div className="mt-4 flex items-center gap-2">
        {isPending && (
          <>
            <button
              data-testid="reschedule-apply"
              onClick={() => call('apply')}
              disabled={busy !== null}
              className="btn-primary text-[13px] inline-flex items-center gap-1.5"
            >
              {busy === 'apply'
                ? <Loader2 className="w-4 h-4 animate-spin" />
                : <Check className="w-4 h-4" />}
              <span>Aplicar</span>
            </button>
            <button
              data-testid="reschedule-dismiss"
              onClick={() => call('dismiss')}
              disabled={busy !== null}
              className="btn-ghost text-[13px] inline-flex items-center gap-1.5"
            >
              {busy === 'dismiss'
                ? <Loader2 className="w-4 h-4 animate-spin" />
                : <X className="w-4 h-4" />}
              <span>Manter como estava</span>
            </button>
          </>
        )}

        {isAccepted && (
          <div className="w-full flex items-center justify-between">
            <p
              data-testid="reschedule-applied-hint"
              className="text-[12.5px] text-zinc-500"
            >
              <Check
                strokeWidth={2}
                className="inline w-3.5 h-3.5 mr-1"
                style={{ color: 'var(--mf-success, #10B981)' }}
              />
              <span>Aplicado. Sua agenda de hoje foi ajustada.</span>
            </p>
            <button
              data-testid="reschedule-undo"
              onClick={() => call('undo')}
              disabled={busy !== null}
              className="btn-ghost text-[12.5px] inline-flex items-center gap-1.5"
            >
              {busy === 'undo'
                ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
                : <Undo2 className="w-3.5 h-3.5" />}
              <span>Desfazer</span>
            </button>
          </div>
        )}
      </div>
    </section>
  );
};

export default RescheduleCard;
