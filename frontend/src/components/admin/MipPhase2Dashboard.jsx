import { useEffect, useMemo, useState } from 'react';
import {
  Activity,
  AlertTriangle,
  BarChart3,
  Database,
  Gauge,
  Loader2,
  LockKeyhole,
  RefreshCw,
  ShieldCheck,
  Timer,
} from 'lucide-react';
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import api from '@/lib/api';

const displayNumber = (value, digits = 0) => {
  if (value === null || value === undefined) {
    return '—';
  }
  return Number(value).toLocaleString('pt-BR', {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  });
};

const displayPercent = (value) => `${displayNumber((value || 0) * 100, 1)}%`;

const displayUsd = (value) => `US$ ${displayNumber(value || 0, 4)}`;

const MetricCell = ({
  icon: Icon,
  label,
  value,
  detail,
  tone = 'zinc',
  testId,
}) => {
  const tones = {
    zinc: 'border-zinc-800 bg-zinc-900/70 text-zinc-100',
    cyan: 'border-cyan-400/30 bg-cyan-400/10 text-cyan-100',
    emerald: 'border-emerald-400/30 bg-emerald-400/10 text-emerald-100',
    amber: 'border-amber-400/30 bg-amber-400/10 text-amber-100',
    rose: 'border-rose-400/30 bg-rose-400/10 text-rose-100',
  };
  return (
    <div
      className={`border p-5 transition-colors duration-200 ${tones[tone]}`}
      data-testid={testId}
    >
      <div className="flex items-start justify-between gap-3">
        <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-zinc-400">
          {label}
        </p>
        <Icon className="h-4 w-4 shrink-0" strokeWidth={1.75} />
      </div>
      <p className="mt-5 font-mono text-[28px] font-medium leading-none text-white">
        {value}
      </p>
      <p className="mt-3 text-[11px] leading-relaxed text-zinc-400">
        {detail}
      </p>
    </div>
  );
};

const ChartTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) {
    return null;
  }
  return (
    <div
      className="border border-zinc-700 bg-zinc-950 px-3 py-2 font-mono text-[11px] text-zinc-200"
    >
      <p className="mb-1 text-zinc-400">{label}</p>
      {payload.map((entry) => (
        <p key={entry.name} style={{ color: entry.color }}>
          {entry.name}: {entry.value}
        </p>
      ))}
    </div>
  );
};

const EmptyChart = ({ label, testId }) => (
  <div
    className="flex h-[230px] items-center justify-center border border-dashed border-zinc-800"
    data-testid={testId}
  >
    <p className="max-w-xs text-center text-[12px] leading-relaxed text-zinc-500">
      {label}
    </p>
  </div>
);

export const MipPhase2Dashboard = () => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [refreshedAt, setRefreshedAt] = useState(null);

  const load = async () => {
    setLoading(true);
    setError('');
    try {
      const response = await api.get('/mip/phase2/metrics');
      setData(response.data);
      setRefreshedAt(new Date());
    } catch (requestError) {
      setError('Não foi possível carregar as métricas observacionais agora.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const divergenceData = useMemo(() => {
    if (!data?.comparisons) {
      return [];
    }
    return [
      { name: 'Alinhadas', value: data.comparisons.match || 0 },
      { name: 'Divergentes', value: data.comparisons.divergent || 0 },
      { name: 'Sem comparação', value: data.comparisons.not_compared || 0 },
    ];
  }, [data]);

  if (loading) {
    return (
      <div
        className="flex min-h-[420px] items-center justify-center bg-zinc-950"
        data-testid="mip-dashboard-loading"
      >
        <Loader2 className="h-6 w-6 animate-spin text-cyan-300" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div
        className="border border-rose-400/30 bg-zinc-950 p-6 text-rose-100"
        data-testid="mip-dashboard-error"
      >
        <div className="flex items-start gap-3">
          <AlertTriangle className="h-5 w-5 shrink-0 text-rose-300" />
          <div>
            <p className="font-mono text-xs uppercase tracking-[0.14em]">
              Métricas indisponíveis
            </p>
            <p className="mt-2 text-sm text-zinc-300">{error}</p>
            <button
              type="button"
              onClick={load}
              className={[
                'mt-4 inline-flex items-center gap-2 border border-zinc-600 px-3 py-2',
                'text-xs text-white transition-colors duration-200 hover:border-zinc-300',
              ].join(' ')}
              data-testid="mip-dashboard-retry-button"
            >
              <RefreshCw className="h-3.5 w-3.5" />
              Tentar novamente
            </button>
          </div>
        </div>
      </div>
    );
  }

  const operations = data.operations || {};
  const cost = data.cost_estimates || {};
  const idempotency = data.idempotency || {};
  const isolation = data.isolation || {};
  const anomalies = data.anomalies || [];
  const hasTimeline = (data.timeline || []).length > 0;

  return (
    <section
      className="min-h-[680px] bg-zinc-950 px-4 py-6 text-white md:px-7 md:py-8"
      data-testid="mip-phase2-dashboard"
    >
      <header className="border-b border-zinc-800 pb-6">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <div
              className={[
                'flex items-center gap-2 font-mono text-[10px] uppercase',
                'tracking-[0.18em] text-cyan-300',
              ].join(' ')}
            >
              <span className="h-2 w-2 animate-pulse bg-cyan-300" />
              Shadow mode ativo
            </div>
            <h2 className="mt-3 text-2xl font-semibold tracking-normal text-white md:text-3xl">
              Observatório MIP/PIE
            </h2>
            <p className="mt-2 max-w-2xl text-sm leading-relaxed text-zinc-400">
              Leitura agregada da Fase 2. Nenhuma decisão, conteúdo ou trilha do estudante é
              alterada.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <p
              className="font-mono text-[10px] uppercase tracking-[0.12em] text-zinc-500"
              data-testid="mip-dashboard-refreshed-at"
            >
              Atualizado {refreshedAt ? refreshedAt.toLocaleTimeString('pt-BR') : 'agora'}
            </p>
            <button
              type="button"
              onClick={load}
              className={[
                'inline-flex items-center gap-2 border border-zinc-600 px-3 py-2',
                'font-mono text-[11px] uppercase tracking-[0.1em] text-white',
                'transition-colors duration-200 hover:border-cyan-300 hover:text-cyan-100',
              ].join(' ')}
              data-testid="mip-dashboard-refresh-button"
            >
              <RefreshCw className="h-3.5 w-3.5" />
              Atualizar
            </button>
          </div>
        </div>
      </header>

      <div
        className={[
          'mt-6 grid grid-cols-1 gap-px border border-zinc-800 bg-zinc-800',
          'sm:grid-cols-2 xl:grid-cols-4',
        ].join(' ')}
        data-testid="mip-dashboard-kpis"
      >
        <MetricCell
          icon={Gauge}
          label="Cache hit"
          value={displayPercent(data.cache_hit_rate)}
          detail={`${displayNumber(data.cache_hits)} hits em ${displayNumber(
            data.cache_lookups,
          )} observações`}
          tone="cyan"
          testId="mip-metric-cache-hit-rate"
        />
        <MetricCell
          icon={Database}
          label="Geração potencial evitável"
          value={displayNumber(data.estimated_generations_avoidable)}
          detail="Estimativa observacional; gerações efetivamente evitadas: 0"
          tone="emerald"
          testId="mip-metric-generations-avoidable"
        />
        <MetricCell
          icon={Timer}
          label="Latência hit / miss"
          value={`${displayNumber(operations.cache_hit_p50_ms, 1)} / ${displayNumber(
            operations.cache_miss_p50_ms,
            1,
          )} ms`}
          detail="P50 de observações com candidato de cache / primeira observação"
          tone="zinc"
          testId="mip-metric-latency"
        />
        <MetricCell
          icon={ShieldCheck}
          label="Disponibilidade observada"
          value={`${displayNumber(operations.availability_pct, 1)}%`}
          detail={`Taxa de erro: ${displayPercent(operations.error_rate)}`}
          tone={operations.error_rate > 0 ? 'amber' : 'emerald'}
          testId="mip-metric-availability"
        />
      </div>

      <div className="mt-6 grid grid-cols-1 gap-6 xl:grid-cols-12">
        <div
          className="border border-zinc-800 bg-zinc-900/50 p-5 xl:col-span-8"
          data-testid="mip-cache-timeline"
        >
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-zinc-500">
                Cache observado
              </p>
              <h3 className="mt-2 text-base font-medium text-white">
                Candidatos hit e primeira observação
              </h3>
            </div>
            <Activity className="h-5 w-5 text-cyan-300" />
          </div>
          <div className="mt-5">
            {hasTimeline ? (
              <ResponsiveContainer width="100%" height={230}>
                <AreaChart
                  data={data.timeline}
                  margin={{ top: 8, right: 8, left: -24, bottom: 0 }}
                >
                  <defs>
                    <linearGradient id="mipHitFill" x1="0" x2="0" y1="0" y2="1">
                      <stop offset="0%" stopColor="#22d3ee" stopOpacity={0.35} />
                      <stop offset="100%" stopColor="#22d3ee" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid stroke="#27272a" strokeDasharray="3 3" vertical={false} />
                  <XAxis
                    dataKey="date"
                    tick={{ fill: '#71717a', fontSize: 10 }}
                    tickLine={false}
                    axisLine={false}
                  />
                  <YAxis
                    allowDecimals={false}
                    tick={{ fill: '#71717a', fontSize: 10 }}
                    tickLine={false}
                    axisLine={false}
                  />
                  <Tooltip content={<ChartTooltip />} />
                  <Area
                    type="monotone"
                    dataKey="hits"
                    name="hits"
                    stroke="#22d3ee"
                    fill="url(#mipHitFill)"
                    strokeWidth={2}
                  />
                  <Area
                    type="monotone"
                    dataKey="misses"
                    name="primeiras observações"
                    stroke="#a1a1aa"
                    fill="transparent"
                    strokeWidth={2}
                  />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <EmptyChart
                label="Ainda não há eventos agregados para desenhar a série temporal."
                testId="mip-cache-timeline-empty"
              />
            )}
          </div>
        </div>

        <div
          className="border border-zinc-800 bg-zinc-900/50 p-5 xl:col-span-4"
          data-testid="mip-comparisons-chart"
        >
          <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-zinc-500">
            Comparação shadow
          </p>
          <h3 className="mt-2 text-base font-medium text-white">Adaptativa × legado</h3>
          <div className="mt-5">
            <ResponsiveContainer width="100%" height={230}>
              <BarChart
                data={divergenceData}
                layout="vertical"
                margin={{ top: 0, right: 8, left: 8, bottom: 0 }}
              >
                <CartesianGrid stroke="#27272a" strokeDasharray="3 3" horizontal={false} />
                <XAxis
                  type="number"
                  allowDecimals={false}
                  tick={{ fill: '#71717a', fontSize: 10 }}
                  tickLine={false}
                  axisLine={false}
                />
                <YAxis
                  type="category"
                  dataKey="name"
                  width={95}
                  tick={{ fill: '#a1a1aa', fontSize: 10 }}
                  tickLine={false}
                  axisLine={false}
                />
                <Tooltip content={<ChartTooltip />} />
                <Bar dataKey="value" name="eventos" fill="#a78bfa" radius={0} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <div className="mt-6 grid grid-cols-1 gap-6 xl:grid-cols-3">
        <div
          className="border border-zinc-800 bg-zinc-900/50 p-5"
          data-testid="mip-cost-card"
        >
          <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-zinc-500">
            Custo potencial
          </p>
          <p className="mt-3 font-mono text-2xl text-emerald-200">
            {displayUsd(data.estimated_cost_avoidable_usd)}
          </p>
          <dl className="mt-5 space-y-3 border-t border-zinc-800 pt-4 text-xs">
            <div className="flex justify-between gap-3">
              <dt className="text-zinc-500">por material-base</dt>
              <dd className="font-mono text-zinc-200">
                {displayUsd(cost.per_material_base_usd)}
              </dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt className="text-zinc-500">por aluno observado</dt>
              <dd className="font-mono text-zinc-200">
                {displayUsd(cost.per_observed_student_usd)}
              </dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt className="text-zinc-500">bases observadas</dt>
              <dd className="font-mono text-zinc-200">
                {displayNumber(cost.material_bases_observed)}
              </dd>
            </div>
          </dl>
        </div>

        <div
          className="border border-zinc-800 bg-zinc-900/50 p-5"
          data-testid="mip-idempotency-card"
        >
          <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-zinc-500">
            Event Store
          </p>
          <p className="mt-3 font-mono text-2xl text-cyan-100">
            {displayNumber(data.events_persisted)}
          </p>
          <p className="mt-1 text-xs text-zinc-500">eventos persistidos e pseudonimizados</p>
          <dl className="mt-5 space-y-3 border-t border-zinc-800 pt-4 text-xs">
            <div className="flex justify-between gap-3">
              <dt className="text-zinc-500">duplicações bloqueadas</dt>
              <dd className="font-mono text-zinc-200">
                {displayNumber(idempotency.blocks)}
              </dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt className="text-zinc-500">taxa de bloqueio</dt>
              <dd className="font-mono text-zinc-200">
                {displayPercent(idempotency.block_rate)}
              </dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt className="text-zinc-500">tentativas observadas</dt>
              <dd className="font-mono text-zinc-200">
                {displayNumber(idempotency.attempts)}
              </dd>
            </div>
          </dl>
        </div>

        <div
          className="border border-zinc-800 bg-zinc-900/50 p-5"
          data-testid="mip-isolation-card"
        >
          <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-zinc-500">
            Isolamento
          </p>
          <p className="mt-3 font-mono text-2xl text-white">
            {displayNumber(isolation.curriculum_namespaces)}
          </p>
          <p className="mt-1 text-xs text-zinc-500">namespaces curriculares separados</p>
          <dl className="mt-5 space-y-3 border-t border-zinc-800 pt-4 text-xs">
            <div className="flex justify-between gap-3">
              <dt className="text-zinc-500">colisões curriculares</dt>
              <dd className="font-mono text-zinc-200">
                {displayNumber(isolation.cross_profile_cache_collisions)}
              </dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt className="text-zinc-500">violações entre alunos</dt>
              <dd className="font-mono text-zinc-200">
                {displayNumber(isolation.student_isolation_violations)}
              </dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt className="text-zinc-500">dados individuais</dt>
              <dd className="font-mono text-emerald-200">não expostos</dd>
            </div>
          </dl>
        </div>
      </div>

      <div className="mt-6 grid grid-cols-1 gap-6 xl:grid-cols-12">
        <div
          className="border border-zinc-800 bg-zinc-900/50 p-5 xl:col-span-7"
          data-testid="mip-recent-events"
        >
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-zinc-500">
                Feed agregado
              </p>
              <h3 className="mt-2 text-base font-medium text-white">
                Eventos recentes sem identificadores pessoais
              </h3>
            </div>
            <LockKeyhole className="h-4 w-4 text-emerald-300" />
          </div>
          <div className="mt-5 overflow-x-auto">
            <table className="w-full min-w-[580px] text-left text-[11px]">
              <thead
                className={[
                  'border-y border-zinc-800 font-mono uppercase',
                  'tracking-[0.1em] text-zinc-500',
                ].join(' ')}
              >
                <tr>
                  <th className="px-2 py-2">momento</th>
                  <th className="px-2 py-2">evento</th>
                  <th className="px-2 py-2">cache</th>
                  <th className="px-2 py-2">hipótese</th>
                  <th className="px-2 py-2">comparação</th>
                </tr>
              </thead>
              <tbody>
                {data.recent_events.length === 0 ? (
                  <tr>
                    <td colSpan="5" className="px-2 py-7 text-center text-zinc-500">
                      Sem eventos observacionais no período.
                    </td>
                  </tr>
                ) : data.recent_events.map((event, index) => (
                  <tr
                    key={`${event.created_at}-${index}`}
                    className={[
                      'border-b border-zinc-800/80 text-zinc-300',
                      'transition-colors duration-150 hover:bg-zinc-900',
                    ].join(' ')}
                  >
                    <td className="px-2 py-2.5 font-mono text-zinc-500">
                      {event.created_at?.slice(0, 19).replace('T', ' ')}
                    </td>
                    <td className="px-2 py-2.5">{event.event_type}</td>
                    <td className="px-2 py-2.5">{event.cache_status}</td>
                    <td className="px-2 py-2.5">{event.shadow_recommendation_code}</td>
                    <td className="px-2 py-2.5">{event.comparison_status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div
          className="border border-zinc-800 bg-zinc-900/50 p-5 xl:col-span-5"
          data-testid="mip-anomalies-panel"
        >
          <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-zinc-500">
            Guardrails
          </p>
          <h3 className="mt-2 text-base font-medium text-white">
            Falhas, quarentenas e inconsistências
          </h3>
          <div className="mt-5 space-y-2">
            {anomalies.map((item) => {
              const alerting = item.count > 0 && item.status !== 'not_applicable';
              return (
                <div
                  key={item.kind}
                  className="flex items-center justify-between border border-zinc-800 px-3 py-3"
                >
                  <span className="text-xs capitalize text-zinc-400">{item.kind}</span>
                  <span
                    className={`font-mono text-xs ${
                      alerting ? 'text-amber-200' : 'text-emerald-200'
                    }`}
                  >
                    {displayNumber(item.count)} · {item.status}
                  </span>
                </div>
              );
            })}
          </div>
          <p
            className={[
              'mt-5 border-t border-zinc-800 pt-4 text-[11px]',
              'leading-relaxed text-zinc-500',
            ].join(' ')}
          >
            Quarentena não se aplica porque a Fase 2 não publica nem reutiliza conteúdo.
            Ações pedagógicas continuam fora deste painel.
          </p>
        </div>
      </div>
    </section>
  );
};