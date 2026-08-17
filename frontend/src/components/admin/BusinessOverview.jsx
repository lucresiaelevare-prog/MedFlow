import { useCallback, useEffect, useState } from 'react';
import {
  Activity,
  AlertTriangle,
  Bot,
  BookOpenCheck,
  Loader2,
  Sparkles,
  RefreshCw,
  UsersRound,
} from 'lucide-react';
import api from '@/lib/api';
import { BusinessMetricCard } from './BusinessMetricCard';
import { BetaIntelligenceReport } from './BetaIntelligenceReport';
import { ProductionBaseline } from './ProductionBaseline';

const number = (value) => Number(value || 0).toLocaleString('pt-BR');

const HealthBadge = ({ health }) => {
  const copy = health === 'healthy' ? 'Saudável' : 'Atenção';
  const color = health === 'healthy' ? 'bg-emerald-500' : 'bg-amber-400';
  return (
    <span className="inline-flex items-center gap-2 text-sm font-medium text-slate-700">
      <span className={`h-2.5 w-2.5 rounded-full ${color}`} />
      {copy}
    </span>
  );
};

export const BusinessOverview = () => {
  const [data, setData] = useState(null);
  const [intelligence, setIntelligence] = useState(null);
  const [error, setError] = useState('');
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async (manual = false) => {
      if (manual) setRefreshing(true);
      try {
        const [overview, report] = await Promise.all([
          api.get('/admin/business/overview'),
          api.get('/admin/business/beta-intelligence'),
        ]);
        setData(overview.data);
        setIntelligence(report.data);
        setError('');
      } catch (requestError) {
        setError('Não foi possível carregar a visão geral agora.');
      } finally {
        setRefreshing(false);
      }
    }, []);

  useEffect(() => {
    load();
    const timer = window.setInterval(() => load(), 60_000);
    return () => window.clearInterval(timer);
  }, [load]);

  if (!data && !error) {
    return (
      <div className="flex min-h-[360px] items-center justify-center" data-testid="business-overview-loading">
        <Loader2 className="h-6 w-6 animate-spin text-emerald-600" />
      </div>
    );
  }

  if (error) {
    return <p className="p-6 text-sm text-rose-700" data-testid="business-overview-error">{error}</p>;
  }

  const hasAlerts = data.alerts.length > 0;
  return (
    <div className="space-y-8" data-testid="business-overview">
      <div className="flex justify-end"><button type="button" onClick={() => load(true)} data-testid="business-overview-refresh" className="inline-flex items-center gap-2 border border-slate-200 bg-white px-3 py-2 text-xs font-medium text-slate-700 hover:bg-slate-50"><RefreshCw className={`h-3.5 w-3.5 ${refreshing ? 'animate-spin' : ''}`} />Atualizar dados</button></div>
      <section className="grid grid-cols-1 gap-px border border-slate-200 bg-slate-200 sm:grid-cols-2 xl:grid-cols-4">
        <BusinessMetricCard
          icon={UsersRound}
          label="Total de alunos"
          value={number(data.growth.total_students)}
          detail="Cadastros ativos no MedFlow Beta."
          tone="slate"
          testId="business-total-students-card"
        />
        <BusinessMetricCard
          icon={UsersRound}
          label="Alunos ativos"
          value={number(data.growth.active_students)}
          detail="Com sessão registrada nos últimos 30 dias."
          tone="green"
          testId="business-growth-card"
        />
        <BusinessMetricCard
          icon={BookOpenCheck}
          label="Novos cadastros"
          value={number(data.growth.new_students_30d)}
          detail={`${number(data.growth.new_students_today)} registrados hoje.`}
          tone="slate"
          testId="business-new-students-card"
        />
        <BusinessMetricCard
          icon={UsersRound}
          label="Plano Free"
          value={number(data.growth.plans.free)}
          detail="Alunos no plano gratuito."
          tone="slate"
          testId="business-free-students-card"
        />
        <BusinessMetricCard
          icon={UsersRound}
          label="Plano Premium"
          value={number(data.growth.plans.premium)}
          detail="Alunos marcados no plano Premium."
          tone="green"
          testId="business-premium-students-card"
        />
        <BusinessMetricCard
          icon={BookOpenCheck}
          label="Conclusão de aulas"
          value={number(data.learning.completed_study_actions)}
          detail={`${number(data.learning.learning_interactions)} interações de estudo.`}
          tone="slate"
          testId="business-learning-card"
        />
        <BusinessMetricCard
          icon={Bot}
          label="A IA está saudável?"
          value={<HealthBadge health={data.ai.health} />}
          detail={`${number(data.ai.questions_today)} perguntas respondidas hoje`}
          tone={data.ai.health === 'healthy' ? 'green' : 'amber'}
          testId="business-ai-health-card"
        />
        <BusinessMetricCard
          icon={AlertTriangle}
          label="Problemas urgentes"
          value={number(data.alerts.length)}
          detail={hasAlerts ? 'Há itens que pedem atenção.' : 'Nenhum alerta urgente agora.'}
          tone={hasAlerts ? 'coral' : 'green'}
          testId="business-alerts-card"
        />
      </section>

      <ProductionBaseline growth={data.growth} />

      <section className="grid grid-cols-1 gap-6 xl:grid-cols-12">
        <div className="border border-slate-200 bg-white p-6 shadow-sm xl:col-span-8" data-testid="business-growth-summary">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-xs font-medium uppercase tracking-[0.12em] text-slate-500">Crescimento</p>
              <h2 className="mt-2 text-lg font-semibold text-slate-900">Novos alunos registrados</h2>
            </div>
            <Sparkles className="h-5 w-5 text-emerald-600" strokeWidth={1.8} />
          </div>
          {data.growth.timeline.length ? (
            <ul className="mt-5 divide-y divide-slate-100">
              {data.growth.timeline.map((item) => (
                <li key={item.date} className="flex items-center justify-between py-3 text-sm">
                  <span className="text-slate-600">{item.date}</span>
                  <span className="font-semibold text-emerald-700">
                    {number(item.new_students)} novos alunos
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-10 text-sm text-slate-500">Ainda não há novos registros no período.</p>
          )}
        </div>

        <div className="border border-slate-200 bg-white p-6 shadow-sm xl:col-span-4" data-testid="business-ai-summary">
          <div className="flex items-center gap-2">
            <Activity className="h-4 w-4 text-emerald-600" strokeWidth={1.8} />
            <p className="text-xs font-medium uppercase tracking-[0.12em] text-slate-500">IA hoje</p>
          </div>
          <dl className="mt-5 space-y-4 text-sm">
            <div className="flex items-center justify-between gap-4">
              <dt className="text-slate-500">Perguntas respondidas</dt>
              <dd className="font-semibold text-slate-900">{number(data.ai.questions_today)}</dd>
            </div>
            <div className="flex items-center justify-between gap-4">
              <dt className="text-slate-500">Planos e feedbacks</dt>
              <dd className="font-semibold text-slate-900">{number(data.ai.plans_today)}</dd>
            </div>
            <div className="flex items-center justify-between gap-4">
              <dt className="text-slate-500">Reuso de conteúdo</dt>
              <dd className="font-semibold text-slate-900">{number(data.ai.cache_reuse_ratio * 100)}%</dd>
            </div>
          </dl>
        </div>
      </section>

      <section className="border border-slate-200 bg-white p-6 shadow-sm" data-testid="business-alerts-list">
        <div className="flex items-center gap-2">
          <AlertTriangle className="h-4 w-4 text-rose-600" strokeWidth={1.8} />
          <h2 className="text-lg font-semibold text-slate-900">Alertas</h2>
        </div>
        {hasAlerts ? (
          <div className="mt-4 divide-y divide-slate-100">
            {data.alerts.map((alert, index) => (
              <div key={`${alert.title}-${index}`} className="py-4 first:pt-0 last:pb-0">
                <p className="font-medium text-slate-900">{alert.title}</p>
                <p className="mt-1 text-sm text-slate-600">{alert.detail}</p>
              </div>
            ))}
          </div>
        ) : (
          <p className="mt-4 text-sm text-slate-600">Tudo está sob controle no momento.</p>
        )}
      </section>
      <BetaIntelligenceReport data={intelligence} loading={refreshing} onRefresh={() => load(true)} />
    </div>
  );
};