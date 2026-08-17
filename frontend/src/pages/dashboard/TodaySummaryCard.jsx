import { ArrowRight, CheckCircle2, Clock3, ListTodo } from 'lucide-react';

const TodaySummaryCard = ({ greeting, summary, onStart }) => {
  const actions = summary?.actions || [];
  if (!actions.length) return null;
  return (
    <section
      className="mb-6 rounded-2xl border border-emerald-100 bg-white p-5 shadow-sm md:p-6"
      data-testid="dashboard-today-summary"
    >
      <div className="flex items-start gap-3">
        <span className="rounded-xl bg-emerald-50 p-2.5 text-emerald-700"><ListTodo className="h-5 w-5" /></span>
        <div><p className="text-sm font-semibold text-slate-900">{greeting}, seu foco de hoje</p><p className="mt-1 text-xs text-slate-500">Uma leitura simples do plano que já está definido para você.</p></div>
      </div>
      <ul className="mt-5 space-y-3">
        {actions.map((action, index) => <li key={`${action.id || action.title}-${index}`} className="flex items-center justify-between gap-4"><div className="flex min-w-0 items-center gap-2.5"><CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-600" /><span className="truncate text-sm text-slate-700">{action.title}</span></div><span className="shrink-0 text-xs font-medium text-slate-500">{action.duration_min} min</span></li>)}
      </ul>
      <div className="mt-5 flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 pt-4"><span className="inline-flex items-center gap-1.5 text-xs text-slate-500"><Clock3 className="h-3.5 w-3.5" />Tempo estimado: <strong className="text-slate-700">{summary.estimated_minutes} min</strong></span><button type="button" onClick={() => onStart(actions[0])} data-testid="dashboard-today-summary-start" className="inline-flex items-center gap-1.5 text-sm font-semibold text-emerald-700 hover:text-emerald-800">Começar pelo foco <ArrowRight className="h-4 w-4" /></button></div>
    </section>
  );
};

export default TodaySummaryCard;