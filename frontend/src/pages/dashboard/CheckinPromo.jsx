import { ClipboardEdit, ArrowRight } from 'lucide-react';

/**
 * CheckinPromo — clinical CTA card.
 */
const CheckinPromo = ({ onClick }) => (
  <button
    data-testid="start-checkin-btn"
    onClick={onClick}
    className="group w-full mf-card p-4 md:p-5 flex items-center justify-between text-left hover:border-brand transition-colors"
  >
    <div className="flex items-center gap-3">
      <span className="w-9 h-9 rounded-lg flex items-center justify-center" style={{ background: 'var(--mf-brand-soft)', color: 'var(--mf-brand)' }}>
        <ClipboardEdit strokeWidth={1.75} className="w-4 h-4" />
      </span>
      <div className="min-w-0">
        <p className="text-[13.5px] font-semibold text-zinc-900">Atualizar o contexto de hoje</p>
        <p className="text-[12px] text-zinc-500">Sono, humor, energia e demandas em 30 segundos.</p>
      </div>
    </div>
    <ArrowRight strokeWidth={1.75} className="w-4 h-4 text-zinc-400 group-hover:text-brand group-hover:translate-x-0.5 transition-transform" />
  </button>
);

export default CheckinPromo;
