import { useEffect, useState } from 'react';
import { Users, Info } from 'lucide-react';
import api from '@/lib/api';

/**
 * PeerBenchmarkCard — comparação anônima com alunos do mesmo período.
 *
 * Filosofia (P0.2):
 *   Sem ranking. Sem competição. Apenas contexto.
 *
 * Consome GET /api/insights/peer-benchmark.
 * Só renderiza se available=true. Fica silencioso nos outros casos
 * (sem período declarado ou peers insuficientes).
 */

const Row = ({ label, you, peer, testId }) => (
  <div
    data-testid={testId}
    className="flex items-baseline justify-between py-2.5 border-b last:border-0"
    style={{ borderColor: 'var(--mf-hair, #E5E5E5)' }}
  >
    <p className="text-[13px] text-zinc-500"><span>{label}</span></p>
    <div className="flex items-baseline gap-4">
      <span
        data-testid={`${testId}-you`}
        className="mono text-[15px] font-semibold text-zinc-900 tabular"
      >
        <span>{you}</span>
      </span>
      <span className="text-[11px] text-zinc-400"><span>vs</span></span>
      <span
        data-testid={`${testId}-peer`}
        className="mono text-[14px] text-zinc-500 tabular"
      >
        <span>{peer}</span>
      </span>
    </div>
  </div>
);

const PeerBenchmarkCard = () => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const { data } = await api.get('/insights/peer-benchmark');
        if (alive) setData(data);
      } catch {
        if (alive) setData(null);
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => { alive = false; };
  }, []);

  if (loading) return null;
  if (!data || !data.available) return null;

  return (
    <section
      data-testid="dashboard-peer-benchmark"
      data-bucket={data.bucket}
      className="mf-card p-5 md:p-6"
      translate="no"
    >
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="flex items-center gap-2.5">
          <div
            className="w-9 h-9 rounded-lg flex items-center justify-center shrink-0"
            style={{ background: 'var(--mf-brand-soft, #FFF7ED)', color: 'var(--mf-brand, #DC6B4C)' }}
          >
            <Users strokeWidth={1.75} className="w-4.5 h-4.5" />
          </div>
          <div>
            <p className="eyebrow"><span>contexto anônimo</span></p>
            <p className="mt-0.5 text-[15px] font-semibold text-zinc-900 leading-tight">
              <span>Você e alunos do mesmo período</span>
            </p>
          </div>
        </div>
        <span
          data-testid="peer-benchmark-sample"
          className="pill mono text-[11px] text-zinc-500 shrink-0"
        >
          <span>n={data.sample_size}</span>
        </span>
      </div>

      <div className="mt-2 space-y-0">
        <div className="flex items-baseline justify-between py-1">
          <div className="flex items-baseline gap-2">
            <span
              data-testid="peer-benchmark-legend-you"
              className="text-[11px] uppercase tracking-wider font-semibold"
              style={{ color: 'var(--mf-brand, #DC6B4C)' }}
            >
              <span>Você</span>
            </span>
            <span className="text-[11px] text-zinc-400"><span>vs</span></span>
            <span
              data-testid="peer-benchmark-legend-peer"
              className="text-[11px] uppercase tracking-wider text-zinc-500"
            >
              <span>Peers (mediana)</span>
            </span>
          </div>
        </div>

        <Row
          label="Hoje"
          you={data.today.you_fmt}
          peer={data.today.peer_median_fmt}
          testId="peer-benchmark-today"
        />
        <Row
          label="Média/dia (7 dias)"
          you={data.week.you_avg_fmt}
          peer={data.week.peer_median_avg_fmt}
          testId="peer-benchmark-week"
        />
      </div>

      <div className="mt-4 pt-3 flex items-start gap-2 border-t" style={{ borderColor: 'var(--mf-hair, #E5E5E5)' }}>
        <Info strokeWidth={1.75} className="w-3.5 h-3.5 mt-0.5 shrink-0 text-zinc-400" />
        <p
          data-testid="peer-benchmark-footer"
          className="text-[11.5px] text-zinc-500 leading-relaxed"
        >
          <span>
            Comparação anônima com {data.sample_size} alunos do{' '}
            <span className="font-medium text-zinc-700">{data.bucket_label}</span>.
            {' '}Sem ranking. Só contexto.
          </span>
        </p>
      </div>
    </section>
  );
};

export default PeerBenchmarkCard;
