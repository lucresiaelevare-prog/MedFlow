import { Sparkles } from 'lucide-react';

const ContextualMessage = ({ weekGoals, noticed }) => {
  let message = noticed?.text || 'Seu plano de hoje está pronto.';
  let source = 'Hoje';
  if (weekGoals?.total > 0) {
    const percentage = Math.round((weekGoals.achieved / weekGoals.total) * 100);
    message = percentage >= 100
      ? 'Você concluiu as metas planejadas para esta semana. Mantenha esse ritmo com leveza.'
      : `Você concluiu ${weekGoals.achieved} de ${weekGoals.total} metas desta semana (${percentage}%).`;
    source = 'Sua semana';
  }
  return <section className="mb-6 flex items-start gap-3 rounded-2xl border border-slate-100 bg-white p-5 shadow-sm" data-testid="dashboard-contextual-message"><Sparkles className="mt-0.5 h-4 w-4 shrink-0 text-violet-600" /><div><p className="text-[11px] font-semibold uppercase tracking-widest text-slate-500">{source}</p><p className="mt-1 text-sm leading-relaxed text-slate-700">{message}</p></div></section>;
};

export default ContextualMessage;