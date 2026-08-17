import { Loader2, Sparkles, Clock, Target, ArrowRight, RotateCw } from 'lucide-react';
import { composeLetter } from './helpers';
import WhyThisCard from './WhyThisCard';

/**
 * RecommendationCard — clinical AI recommendation card.
 * Kills previous "editorial letter" styling. Now: card with header badge,
 * clear title, body, meta chips, primary CTA, secondary/tertiary text links.
 */
const RecommendationCard = ({ mission, iea, loading, onComplete, onSkip, onRegenerate }) => {
  if (loading && !mission) {
    return (
      <section data-testid="recommendation-card" className="mf-card p-8 flex items-center justify-center text-zinc-400 animate-fade-in">
        <Loader2 className="w-4 h-4 animate-spin mr-2" strokeWidth={1.75} />
        <span className="text-[13px]">Preparando sua próxima ação…</span>
      </section>
    );
  }

  if (!mission) {
    return (
      <section data-testid="recommendation-card" className="mf-card p-6 md:p-8 animate-fade-in">
        <div className="flex items-center gap-2 mb-3">
          <span className="pill pill-success">Encerrado por hoje</span>
        </div>
        <h2 className="text-[22px] font-semibold text-zinc-900 tracking-tight">
          Você fechou o dia.
        </h2>
        <p className="mt-2 text-[15px] text-zinc-600 leading-relaxed max-w-xl">
          Descansar bem agora é parte do plano de estudo.
        </p>
        <button
          data-testid="missions-regenerate-btn"
          onClick={onRegenerate}
          className="mt-6 btn-secondary"
        >
          <RotateCw strokeWidth={1.75} className="w-3.5 h-3.5" />
          Regenerar
        </button>
      </section>
    );
  }

  const letter = composeLetter(mission, iea);
  const durMin = mission.minutes || 0;

  return (
    <article data-testid="recommendation-card" className="mf-card p-6 md:p-8 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <span className="pill pill-brand">
          <Sparkles strokeWidth={1.75} className="w-3 h-3" />
          Recomendação de hoje
        </span>
        <button
          data-testid="missions-regenerate-btn"
          onClick={onRegenerate}
          className="btn-ghost inline-flex items-center gap-1.5"
          aria-label="Regenerar recomendação"
        >
          <RotateCw strokeWidth={1.75} className="w-3.5 h-3.5" />
          Regenerar
        </button>
      </div>

      {/* Title */}
      <h2
        data-testid="recommendation-title"
        className="mt-4 text-[24px] md:text-[28px] font-semibold text-zinc-900 tracking-tight leading-[1.15]"
      >
        {letter.primary}.
      </h2>

      {/* Follow-up */}
      {letter.followup.length > 0 && (
        <p className="mt-2 text-[15px] text-zinc-600 leading-relaxed">
          {letter.followup.join(' ')}
        </p>
      )}

      {/* Rationale */}
      {letter.rationale.length > 0 && (
        <div className="mt-5 rounded-xl p-4" style={{ background: 'var(--mf-surface)' }}>
          <p className="eyebrow-mono mb-2">Por quê</p>
          <ul className="space-y-1.5">
            {letter.rationale.map((r, i) => (
              <li key={i} className="text-[13.5px] text-zinc-700 leading-relaxed flex items-start gap-2">
                <span className="text-zinc-400 mt-0.5">·</span>
                <span>{r}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* iter14 — Motor visível: expõe os sinais crus que geraram esta decisão */}
      <WhyThisCard
        signals={mission.why_signals || []}
        whyNow={mission.why_now}
        testId="why-this-dashboard"
      />

      {/* Meta chips */}
      <div className="mt-5 flex flex-wrap items-center gap-2">
        <span className="pill">
          <Clock strokeWidth={1.75} className="w-3 h-3" />
          <span className="mono text-zinc-700">{durMin}</span> min
        </span>
        <span className="pill capitalize">
          <Target strokeWidth={1.75} className="w-3 h-3" />
          {mission.category}
        </span>
        {iea?.weakest_pillar && (
          <span className="pill">
            Pilar em atenção: <span className="text-zinc-800 capitalize ml-1">{iea.weakest_pillar.replace('_', ' ')}</span>
          </span>
        )}
      </div>

      {/* Actions */}
      <div className="mt-6 flex flex-wrap items-center gap-3">
        <button
          data-testid={`mission-complete-${mission.id}`}
          onClick={onComplete}
          className="btn-primary"
        >
          Começar
          <ArrowRight strokeWidth={1.75} className="w-4 h-4" />
        </button>
        <button
          data-testid={`mission-skip-${mission.id}`}
          onClick={onSkip}
          className="btn-secondary"
        >
          Ver outra
        </button>
      </div>
    </article>
  );
};

export const AlternateRow = () => null;
export default RecommendationCard;
