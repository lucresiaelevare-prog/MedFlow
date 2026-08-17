import { useEffect, useState } from 'react';
import {
  BookOpen,
  BrainCircuit,
  HeartPulse,
  Loader2,
  MessageSquareText,
  Settings2,
  Wrench,
} from 'lucide-react';
import api from '@/lib/api';

const pageConfig = {
  learning: {
    icon: BrainCircuit,
    title: 'Aprendizagem',
    subtitle: 'Veja os assuntos que mais pedem atenção e os mais estudados.',
    endpoint: '/admin/business/learning',
  },
  content: {
    icon: BookOpen,
    title: 'Conteúdo',
    subtitle: 'Acompanhe a base de materiais e os recursos publicados.',
    endpoint: '/admin/business/content',
  },
  wellness: {
    icon: HeartPulse,
    title: 'Bem-estar',
    subtitle: 'Acompanhe check-ins e conteúdos de apoio disponíveis.',
    endpoint: '/admin/business/wellness',
  },
  feedbacks: {
    icon: MessageSquareText,
    title: 'Feedbacks',
    subtitle: 'Leia o que os alunos enviaram, sem misturar com dados técnicos.',
    endpoint: '/admin/business/feedbacks',
  },
  settings: {
    icon: Settings2,
    title: 'Configurações',
    subtitle: 'Confira a disponibilidade das integrações sem exibir chaves.',
    endpoint: '/admin/business/settings',
  },
};

const EmptyState = ({ children }) => <p className="py-10 text-sm text-slate-500">{children}</p>;

const LearningView = ({ data }) => (
  <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
    <section className="border border-slate-200 bg-white p-6" data-testid="learning-difficult-topics">
      <h3 className="font-semibold text-slate-900">Assuntos com maior dificuldade</h3>
      {data.difficult_topics.length ? <ul className="mt-4 divide-y divide-slate-100">{data.difficult_topics.map((item, index) => <li key={`${item.topic}-${index}`} className="flex justify-between gap-4 py-3 text-sm"><span className="text-slate-700">{item.topic || item.discipline || 'Assunto não informado'}</span><span className="font-medium text-rose-700">{Math.round((item.difficulty || 0) * 100)}%</span></li>)}</ul> : <EmptyState>Ainda não há amostra suficiente para indicar dificuldades coletivas.</EmptyState>}
    </section>
    <section className="border border-slate-200 bg-white p-6" data-testid="learning-studied-topics">
      <h3 className="font-semibold text-slate-900">Assuntos mais estudados</h3>
      {data.studied_topics.length ? <ul className="mt-4 divide-y divide-slate-100">{data.studied_topics.map((item) => <li key={item.topic} className="flex justify-between gap-4 py-3 text-sm"><span className="text-slate-700">{item.topic}</span><span className="font-medium text-emerald-700">{item.count}</span></li>)}</ul> : <EmptyState>Ainda não há temas registrados nas interações de estudo.</EmptyState>}
    </section>
  </div>
);

const ContentView = ({ data }) => (
  <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
    <section className="border border-slate-200 bg-white p-6 xl:col-span-1"><p className="text-xs uppercase tracking-[0.12em] text-slate-500">Biblioteca</p><p className="mt-3 text-3xl font-bold text-slate-900">{data.learning_materials}</p><p className="mt-2 text-sm text-slate-500">materiais de aprendizagem ativos</p><dl className="mt-5 space-y-3 border-t border-slate-100 pt-4 text-sm"><div className="flex justify-between"><dt className="text-slate-500">Recursos</dt><dd>{data.resources}</dd></div><div className="flex justify-between"><dt className="text-slate-500">Bem-estar</dt><dd>{data.wellness_items}</dd></div><div className="flex justify-between"><dt className="text-slate-500">Em revisão</dt><dd>{data.quarantined_materials}</dd></div></dl></section>
    <section className="border border-slate-200 bg-white p-6 xl:col-span-2"><h3 className="font-semibold text-slate-900">Recursos recentes</h3>{data.recent_resources.length ? <ul className="mt-4 divide-y divide-slate-100">{data.recent_resources.map((item) => <li key={item.id} className="py-3"><p className="font-medium text-slate-800">{item.title}</p><p className="mt-1 text-xs text-slate-500">{item.type || 'recurso'} · {item.category || 'sem categoria'}</p></li>)}</ul> : <EmptyState>Nenhum recurso foi publicado ainda.</EmptyState>}</section>
  </div>
);

const WellnessView = ({ data }) => (
  <div className="grid grid-cols-1 gap-6 md:grid-cols-3"><section className="border border-slate-200 bg-white p-6"><p className="text-xs uppercase tracking-[0.12em] text-slate-500">Check-ins</p><p className="mt-3 text-3xl font-bold text-slate-900">{data.checkins}</p></section><section className="border border-slate-200 bg-white p-6"><p className="text-xs uppercase tracking-[0.12em] text-slate-500">Humor médio</p><p className="mt-3 text-3xl font-bold text-slate-900">{data.average_mood ?? '—'}</p></section><section className="border border-slate-200 bg-white p-6"><p className="text-xs uppercase tracking-[0.12em] text-slate-500">Conteúdos de apoio</p><p className="mt-3 text-3xl font-bold text-slate-900">{data.wellness_items}</p></section></div>
);

const FeedbackView = ({ data }) => (
  <section className="border border-slate-200 bg-white p-6" data-testid="business-feedback-list"><h3 className="font-semibold text-slate-900">Feedbacks recebidos</h3>{data.feedbacks.length ? <ul className="mt-4 divide-y divide-slate-100">{data.feedbacks.map((item, index) => <li key={item.id || index} className="py-4"><p className="text-sm text-slate-700">{item.message || 'Feedback sem mensagem'}</p><p className="mt-2 text-xs text-slate-500">{item.rating ? `Nota: ${item.rating}` : 'Sem nota'} · {item.created_at?.slice(0, 10) || 'sem data'}</p></li>)}</ul> : <EmptyState>Nenhum feedback foi enviado ainda.</EmptyState>}</section>
);

const SettingsView = ({ data }) => (
  <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
    <section className="border border-slate-200 bg-white p-6">
      <h3 className="font-semibold text-slate-900">Pagamentos</h3>
      <p className="mt-3 text-sm text-slate-600">
        {data.payments_connected ? 'Conectados' : 'Ainda não conectados'}
      </p>
    </section>
    <section className="border border-slate-200 bg-white p-6">
      <h3 className="font-semibold text-slate-900">Serviços disponíveis</h3>
      {data.technical_access ? (
        <dl className="mt-4 space-y-3 text-sm">
          {Object.entries(data.providers).map(([name, available]) => (
            <div key={name} className="flex justify-between">
              <dt className="text-slate-600">{name}</dt>
              <dd className={available ? 'text-emerald-700' : 'text-slate-500'}>
                {available ? 'Disponível' : 'Não configurado'}
              </dd>
            </div>
          ))}
        </dl>
      ) : (
        <p className="mt-3 text-sm text-slate-600">{data.message}</p>
      )}
    </section>
  </div>
);

const PreparedView = ({ section }) => <section className="border border-slate-200 bg-white p-8" data-testid={`prepared-${section}`}><p className="text-xs uppercase tracking-[0.12em] text-slate-500">{section}</p><h2 className="mt-3 text-xl font-semibold text-slate-900">Nenhum dado disponível ainda</h2><p className="mt-2 max-w-xl text-sm leading-relaxed text-slate-600">Esta área está pronta para receber dados reais quando a operação correspondente for conectada. Nada é estimado ou simulado aqui.</p></section>;

export const BusinessOperations = ({ section }) => {
  const config = pageConfig[section];
  const [data, setData] = useState(null);

  useEffect(() => {
    if (!config) return;
    api.get(config.endpoint).then((response) => setData(response.data));
  }, [config]);

  if (!config) return <PreparedView section={section} />;
  if (!data) return <div className="flex min-h-[240px] items-center justify-center"><Loader2 className="h-6 w-6 animate-spin text-emerald-600" /></div>;
  const Icon = config.icon;
  return <div className="space-y-6" data-testid={`business-${section}-page`}><header className="flex items-start gap-3"><span className="border border-emerald-100 bg-emerald-50 p-3 text-emerald-700"><Icon className="h-5 w-5" /></span><div><p className="text-xs font-medium uppercase tracking-[0.12em] text-slate-500">Gestão</p><h2 className="mt-1 text-2xl font-semibold text-slate-900">{config.title}</h2><p className="mt-2 text-sm text-slate-600">{config.subtitle}</p></div></header>{section === 'learning' && <LearningView data={data} />}{section === 'content' && <ContentView data={data} />}{section === 'wellness' && <WellnessView data={data} />}{section === 'feedbacks' && <FeedbackView data={data} />}{section === 'settings' && <SettingsView data={data} />}</div>;
};

export const DeveloperView = () => {
  const [data, setData] = useState(null);
  useEffect(() => { api.get('/admin/business/developer/overview').then((response) => setData(response.data)); }, []);
  if (!data) return <div className="flex min-h-[240px] items-center justify-center"><Loader2 className="h-6 w-6 animate-spin text-slate-700" /></div>;
  const shadowActive = data.shadow_mode?.shadow_mode ?? false;
  return (
    <section className="border border-slate-300 bg-slate-950 p-6 text-white" data-testid="developer-overview">
      <div className="flex items-center gap-2"><Wrench className="h-4 w-4 text-emerald-300" /><h2 className="font-semibold">Modo desenvolvedor</h2></div>
      <p className="mt-2 text-sm text-slate-400">Observabilidade técnica restrita a administradores técnicos.</p>
      <dl className="mt-6 grid grid-cols-1 gap-px bg-slate-700 sm:grid-cols-3">
        <div className="bg-slate-900 p-4"><dt className="text-xs text-slate-400">Shadow mode</dt><dd className="mt-2 text-lg" data-testid="developer-shadow-status">{shadowActive ? 'Ativo' : 'Inativo'}</dd></div>
        <div className="bg-slate-900 p-4"><dt className="text-xs text-slate-400">Cache hit</dt><dd className="mt-2 text-lg">{Math.round((data.content_memory.reuse_ratio || 0) * 100)}%</dd></div>
        <div className="bg-slate-900 p-4"><dt className="text-xs text-slate-400">Circuito IA</dt><dd className="mt-2 text-lg">{data.engine.circuit_breaker.state}</dd></div>
      </dl>
    </section>
  );
};