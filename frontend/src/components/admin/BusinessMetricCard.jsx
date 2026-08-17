export const BusinessMetricCard = ({ icon: Icon, label, value, detail, tone = 'slate', testId }) => {
  const tones = {
    slate: 'border-slate-200 text-slate-900',
    green: 'border-emerald-200 text-emerald-900',
    amber: 'border-amber-200 text-amber-900',
    coral: 'border-rose-200 text-rose-900',
  };
  return (
    <article
      className={`border bg-white p-5 shadow-sm transition-shadow duration-150 hover:shadow-md ${tones[tone]}`}
      data-testid={testId}
    >
      <div className="flex items-start justify-between gap-3">
        <p className="text-xs font-medium uppercase tracking-[0.12em] text-slate-500">{label}</p>
        {Icon && <Icon className="h-4 w-4 text-current" strokeWidth={1.8} />}
      </div>
      <p className="mt-5 text-3xl font-bold tracking-normal text-current">{value}</p>
      <p className="mt-2 text-xs leading-relaxed text-slate-500">{detail}</p>
    </article>
  );
};