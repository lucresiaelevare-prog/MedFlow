import { useState } from 'react';
import {
  ChevronDown, ChevronUp, Brain, Moon, Heart, Activity, Sun, Clock,
  AlertTriangle, TrendingUp, Wand2, CalendarDays, BookOpen,
} from 'lucide-react';

/**
 * WhyThisCard — Motor visível (iter14).
 *
 * Expande sob demanda um bloco "Como o MedFlow percebeu isso?" listando
 * os sinais crus + a frase de decisão. NÃO inventa nada — só traduz
 * o que o backend já devolveu em recommendation.why_signals + why_now.
 *
 * Filosofia: o cérebro do produto vira vidro. O aluno vê a máquina pensar.
 */

const ICON_MAP = {
  moon: Moon, heart: Heart, activity: Activity, sun: Sun, clock: Clock,
  alert: AlertTriangle, brain: Brain, chart: TrendingUp, wand: Wand2,
  calendar: CalendarDays, book: BookOpen,
};

const WhyThisCard = ({ signals = [], whyNow, testId = 'why-this', onExpanded }) => {
  const [open, setOpen] = useState(false);
  const hasContent = whyNow || signals.length > 0;
  if (!hasContent) return null;

  return (
    <div
      className="mt-5 rounded-xl p-4 hairline"
      style={{ background: 'var(--mf-surface)' }}
      data-testid={testId}
    >
      <button
        type="button"
        onClick={() => setOpen((v) => {
          if (!v) onExpanded?.();
          return !v;
        })}
        className="w-full flex items-center justify-between gap-3 text-left"
        data-testid={`${testId}-toggle`}
        aria-expanded={open}
      >
        <div className="flex items-start gap-2.5 min-w-0">
          <Brain
            strokeWidth={1.75}
            className="w-4 h-4 mt-0.5 shrink-0"
            style={{ color: 'var(--mf-brand)' }}
          />
          <div className="min-w-0">
            <p className="eyebrow-mono"><span>como percebi isso</span></p>
            {whyNow && (
              <p className="mt-1 text-[13.5px] text-zinc-800 leading-relaxed line-clamp-2">
                <span>{whyNow}</span>
              </p>
            )}
          </div>
        </div>
        {open ? (
          <ChevronUp strokeWidth={1.75} className="w-4 h-4 text-zinc-400 shrink-0" />
        ) : (
          <ChevronDown strokeWidth={1.75} className="w-4 h-4 text-zinc-400 shrink-0" />
        )}
      </button>

      {open && signals.length > 0 && (
        <ul
          className="mt-4 pt-4 hairline-t space-y-2.5"
          data-testid={`${testId}-signals`}
        >
          {signals.map((s, i) => {
            const Icon = ICON_MAP[s.icon] || Brain;
            return (
              <li
                key={i}
                className="flex items-center justify-between gap-3 text-[12.5px]"
                data-testid={`${testId}-signal-${s.kind}`}
              >
                <span className="flex items-center gap-2 text-zinc-600 min-w-0">
                  <Icon strokeWidth={1.75} className="w-3.5 h-3.5 shrink-0 text-zinc-400" />
                  <span className="truncate"><span>{s.label}</span></span>
                </span>
                <span className="mono text-zinc-900 shrink-0"><span>{s.value}</span></span>
              </li>
            );
          })}
        </ul>
      )}

      {open && (
        <p className="mt-3 text-[11px] text-zinc-400 leading-relaxed">
          <span>
            Nada disso é opinião. Cada linha vem de um sinal que você registrou
            ou de um comportamento que o motor observou. Se algum não fizer
            sentido, ajuste seu perfil ou registre um check-in.
          </span>
        </p>
      )}
    </div>
  );
};

export default WhyThisCard;
