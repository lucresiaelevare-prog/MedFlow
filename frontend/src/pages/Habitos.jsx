import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Loader2, Bell, Calendar as CalendarIcon, Zap, Moon, Footprints, Brain, Sparkles,
  RefreshCw, Timer, ArrowRight, BookOpen, Activity, Users,
  HelpCircle as HelpCircleIcon,
} from 'lucide-react';
import api from '@/lib/api';
import { useAuth } from '@/context/AuthContext';
import Shell from '@/components/Shell';

/**
 * Hábitos — Layout v2 (Clinical Minimalism · dashboard shell).
 *
 * Sidebar compartilhada com /dashboard (SidebarV2). Shell global das
 * demais rotas fica INTACTO. Conteúdo montado 1:1 com o mockup:
 *  - Header (título + subtitle + date pill + notification bell)
 *  - Panorama de Hoje  (sinais reais do IEA, sem tendência simulada)
 *  - Próxima ação de maior impacto (recomendação REAL do home/today)
 *  - Seu maior aliado / limitador / análise MedFlow  (derivados dos pilares reais)
 *  - Seus pilares  (arcs reais + AÇÃO RÁPIDA)
 *  - Bottom banner learning (real, quando ainda não há sinal suficiente)
 *
 * A tela exibe somente sinais disponíveis no backend. Não simula tendências ou impactos.
 */

// ─── utilidades visuais ────────────────────────────────────────────────
const PILLAR_META = {
  estudos:      { label: 'Estudos',      Icon: BookOpen,  sublabel: 'Estudo e aprendizado'    },
  sono:         { label: 'Sono',         Icon: Moon,      sublabel: 'Descanso e recuperação'  },
  saude_fisica: { label: 'Saúde Física', Icon: Activity,  sublabel: 'Corpo e disposição'      },
  bem_estar:    { label: 'Bem-estar',    Icon: Sparkles,  sublabel: 'Mente e equilíbrio'      },
  social:       { label: 'Social',       Icon: Users,     sublabel: 'Relações e suporte'      },
};
const PILLAR_ORDER = ['estudos', 'sono', 'saude_fisica', 'bem_estar', 'social'];
// Superfície de edição já existente no MedFlow para cada pilar.
// O quadro de edição (Perfil do estudante / check-in) já funciona bem —
// o botão abaixo apenas leva o aluno até a tela correspondente.
const PILLAR_EDIT_ROUTE = {
  estudos:      '/perfil-estudante',
  sono:         '/checkin',
  saude_fisica: '/perfil-estudante',
  bem_estar:    '/checkin',
  social:       '/perfil-estudante',
};

const toneOf = (score) => {
  if (score == null)  return { color: '#94a3b8', word: '—' };
  if (score >= 68)    return { color: '#059669', word: 'Estável' };
  if (score >= 52)    return { color: '#6C5CE7', word: 'Consistente' };
  if (score >= 36)    return { color: '#F59E0B', word: 'Atenção' };
  return                     { color: '#DC6B4C', word: 'Em cuidado' };
};

const todayLabelPt = () => {
  const d = new Date();
  const months = ['jan','fev','mar','abr','mai','jun','jul','ago','set','out','nov','dez'];
  return `Hoje, ${d.getDate()} de ${months[d.getMonth()]}`;
};

// ─── arco circular (para "seus pilares") ────────────────────────────────
const PillarArc = ({ score, color }) => {
  const R = 34;
  const C = 2 * Math.PI * R;
  const pct = Math.max(0, Math.min(1, (score || 0) / 100));
  const offset = C - pct * C;
  return (
    <svg viewBox="0 0 80 80" className="w-20 h-20 -rotate-90" aria-hidden="true">
      <circle cx="40" cy="40" r={R} fill="none" stroke="#EEF2F7" strokeWidth="6" />
      <circle
        cx="40" cy="40" r={R}
        fill="none"
        stroke={color}
        strokeWidth="6"
        strokeLinecap="round"
        strokeDasharray={C}
        strokeDashoffset={offset}
        style={{ transition: 'stroke-dashoffset 900ms cubic-bezier(0.23, 1, 0.32, 1)' }}
      />
    </svg>
  );
};

// ─── Footer v2 ─────────────────────────────────────────────────────────
const FooterV2 = () => (
  <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 py-4 mt-8 border-t border-slate-100">
    <div className="flex items-center gap-2 text-[11.5px] text-slate-400">
      <Activity className="w-3.5 h-3.5" />
      <span>Use estes sinais para acompanhar sua rotina, não para prever resultados.</span>
    </div>
    <div className="flex items-center gap-2 text-[11.5px] text-slate-400">
      <HelpCircleIcon className="w-3.5 h-3.5" />
      <span>Precisa de ajuda?</span>
    </div>
  </div>
);

// ─── Página ────────────────────────────────────────────────────────────
const Habitos = () => {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [loading, setLoading] = useState(true);
  const [iea, setIea] = useState(null);
  const [home, setHome] = useState(null);
  const [care, setCare] = useState(null);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    (async () => {
      setLoading(true);
      try {
        const [i, h, c] = await Promise.all([
          api.get('/iea'),
          api.get('/home/today').catch(() => ({ data: {} })),
          api.get('/care/today').catch(() => ({ data: { tasks: [] } })),
        ]);
        setIea(i.data);
        setHome(h.data);
        setCare(c.data);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  // ── Dados REAIS derivados ────────────────────────────────────────────
  const pillars = useMemo(() => {
    const src = iea?.pillars || [];
    return PILLAR_ORDER.map((k) => src.find((p) => p.key === k) || { key: k, score: null });
  }, [iea]);

  // Índice real do IEA, comunicado como sinal de contexto e não como resultado acadêmico.
  const performance = iea?.iea ?? null;
  const performanceTone = toneOf(performance);
  // P0: só apresentamos aliado/limitador/análise quando há dado REAL do aluno.
  const hasData = iea?.has_data === true;

  // Maior aliado / limitador — REAL a partir dos pilares (apenas com dados)
  const withData = pillars.filter((p) => typeof p.score === 'number');
  const sorted = [...withData].sort((a, b) => (b.score || 0) - (a.score || 0));
  const strongest = hasData ? sorted[0] : null;
  const weakest = hasData ? sorted[sorted.length - 1] : null;
  const strongestMeta = strongest ? PILLAR_META[strongest.key] : null;
  const weakestMeta   = weakest ? PILLAR_META[weakest.key] : null;

  // Frases observacionais para os cards laterais — derivadas do pilar, sem estimar impacto.
  const strongestNote = {
    estudos: {
      line: 'Padrão mais consistente',
      hint: 'Seus registros recentes sustentam a rotina de estudos.',
    },
    sono: {
      line: 'Padrão mais estável',
      hint: 'Seus registros de descanso ajudam a compor o contexto do dia.',
    },
    saude_fisica: {
      line: 'Sinal favorável recente',
      hint: 'Seu contexto físico aparece mais estável nos registros.',
    },
    bem_estar: {
      line: 'Sinal favorável recente',
      hint: 'Seu bem-estar aparece como um apoio na rotina recente.',
    },
    social: {
      line: 'Rede de apoio presente',
      hint: 'O suporte social aparece como parte do seu contexto.',
    },
  }[strongest?.key] || {
    line: 'Sinal em acompanhamento',
    hint: 'Continue registrando sua rotina.',
  };

  const weakestNote = {
    estudos: {
      line: 'Sinal que pede atenção',
      hint: 'Seus registros sugerem revisar como o estudo cabe na rotina.',
    },
    sono: {
      line: 'Sinal que pede atenção',
      hint: 'O descanso merece acompanhamento nos próximos registros.',
    },
    saude_fisica: {
      line: 'Sinal que pede atenção',
      hint: 'Seu contexto físico merece um olhar cuidadoso hoje.',
    },
    bem_estar: {
      line: 'Sinal que pede atenção',
      hint: 'Seu bem-estar merece espaço no planejamento do dia.',
    },
    social: {
      line: 'Sinal que pede atenção',
      hint: 'Seu suporte social pode ser acompanhado ao longo da rotina.',
    },
  }[weakest?.key] || {
    line: 'Sinal em acompanhamento',
    hint: 'Observe como esse pilar evolui.',
  };

  // Próxima ação de maior impacto — REAL de home/today
  const rec = home?.recommendation;
  // "O que percebi" / learning banner — REAL de home/today.noticed
  const noticed = home?.noticed;
  const showLearning = noticed?.mode === 'learning' && !dismissed;

  const displayName = ((user?.name || '') + '').trim();
  const initial = displayName.charAt(0).toUpperCase() || 'U';

  return (
    <Shell>
      <div
        data-testid="habitos-root"
        className="p-5 md:p-7 lg:p-10"
        style={{ background: '#f8f7fc' }}
      >
        <div className="max-w-6xl mx-auto">
          {/* ─── Header ─── */}
          <header className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-4 mb-8">
            <div className="min-w-0">
              <h1
                data-testid="habitos-title"
                className="text-[26px] md:text-[30px] font-bold text-slate-900 tracking-tight leading-tight"
              >
                Hábitos
              </h1>
              <p className="mt-2 text-[13.5px] md:text-[14px] text-slate-500 leading-relaxed max-w-2xl">
                Acompanhe os sinais da sua rotina que ajudam a sustentar seus estudos.
              </p>
            </div>
            <div className="flex items-center gap-3 shrink-0">
              <div
                className="flex items-center gap-2 bg-white rounded-xl px-4 py-2.5 shadow-sm border border-slate-100"
                data-testid="habitos-date-pill"
              >
                <CalendarIcon className="w-4 h-4 text-slate-500" />
                <span className="text-[13px] font-medium text-slate-700">{todayLabelPt()}</span>
              </div>
              <button
                data-testid="habitos-notif-btn"
                className="relative w-11 h-11 bg-white rounded-xl shadow-sm border border-slate-100 flex items-center justify-center hover:bg-slate-50 transition-colors"
                aria-label="Notificações"
              >
                <Bell className="w-5 h-5 text-slate-500" />
                <span className="absolute top-2.5 right-2.5 w-2 h-2 rounded-full" style={{ background: '#6C5CE7' }} />
              </button>
            </div>
          </header>

          {/* ─── Panorama de hoje (esq) + Próxima ação (dir) ─── */}
          <div className="grid grid-cols-1 lg:grid-cols-[1fr_360px] gap-5 mb-6">
            <section
              data-testid="habitos-performance"
              className="bg-white rounded-2xl shadow-sm border border-slate-100 p-6 md:p-7"
            >
              <p className="text-[11px] font-semibold uppercase tracking-widest text-slate-500">
                Panorama de hoje
              </p>
              <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-5 mt-2">
                <div className="min-w-0">
                  <div className="flex items-center gap-3">
                    <span
                      className="w-11 h-11 rounded-xl flex items-center justify-center"
                      style={{ background: '#F4F2FF', color: performanceTone.color }}
                    >
                      <Activity className="w-5 h-5" strokeWidth={1.75} />
                    </span>
                    <span
                      data-testid="habitos-performance-score"
                      className="text-[22px] font-bold leading-none"
                      style={{ color: performanceTone.color }}
                    >
                      {loading && performance == null
                        ? 'Acompanhando'
                        : performance == null ? 'Sem check-in' : performanceTone.word}
                    </span>
                  </div>
                  <p className="mt-2 text-[14px] text-slate-600 max-w-sm">
                    {performance == null
                      ? 'Faça um check-in para registrar como seu dia está agora.'
                      : 'Este panorama organiza sinais do seu contexto para orientar o próximo passo.'}
                  </p>
                </div>
                <div className="flex-1 max-w-[360px] rounded-xl border border-slate-100 bg-slate-50 p-4">
                  <p className="text-[11px] font-semibold uppercase tracking-widest text-slate-500">
                    Leitura honesta
                  </p>
                  <p className="mt-2 text-[13px] leading-relaxed text-slate-600">
                    Ainda não exibimos tendência ou previsão sem histórico real suficiente.
                  </p>
                </div>
              </div>
            </section>

            <section
              data-testid="habitos-next-action"
              className="rounded-2xl border p-6 flex flex-col"
              style={{
                background: 'linear-gradient(135deg, #f8f6ff 0%, #f3f0ff 40%, #ede9ff 100%)',
                borderColor: '#e4dff5',
              }}
            >
              <div className="flex items-center gap-2 mb-2">
                <div
                  className="w-8 h-8 rounded-lg flex items-center justify-center"
                  style={{ background: '#6C5CE7' }}
                >
                  <Zap className="w-4 h-4 text-white" />
                </div>
                <p className="text-[11px] font-semibold uppercase tracking-widest" style={{ color: '#6C5CE7' }}>
                  Sua ação de agora
                </p>
              </div>
              <h3 className="text-[22px] font-bold text-slate-900 tracking-tight leading-snug mt-1">
                {rec?.title || 'Fazer o check-in de hoje'}
              </h3>
              <div className="mt-4">
                <p className="text-[13px] leading-relaxed text-slate-600">
                  Uma única ação sugerida a partir do seu contexto e plano atual.
                </p>
              </div>
              <button
                data-testid="habitos-next-action-cta"
                onClick={() => navigate(rec?.action_route || '/checkin')}
                className="mt-auto pt-5 inline-flex items-center justify-center gap-2 text-white font-semibold px-6 py-3 rounded-xl transition-all active:scale-[0.97] w-full"
                style={{
                  background: '#6C5CE7',
                  boxShadow: '0 10px 25px -8px rgba(108, 92, 231, 0.4)',
                }}
                onMouseEnter={(e) => (e.currentTarget.style.background = '#5B4BD5')}
                onMouseLeave={(e) => (e.currentTarget.style.background = '#6C5CE7')}
              >
                <span>{rec?.action_label || 'Fazer agora'}</span>
                <ArrowRight className="w-4 h-4" />
              </button>
            </section>
          </div>

          {/* ─── Aliado / Limitador / Análise MedFlow ─── */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
            {/* Maior aliado */}
            <section
              data-testid="habitos-strongest"
              className="bg-white rounded-2xl shadow-sm border border-slate-100 p-5"
            >
              <p className="text-[11px] font-semibold uppercase tracking-widest text-slate-500 mb-3">
                Seu maior aliado
              </p>
              <div className="flex items-start gap-3">
                <div
                  className="w-12 h-12 rounded-xl flex items-center justify-center shrink-0"
                  style={{ background: '#ECFDF5' }}
                >
                  {strongestMeta && <strongestMeta.Icon className="w-6 h-6" style={{ color: '#059669' }} strokeWidth={1.75} />}
                </div>
                <div className="min-w-0">
                  <p className="text-[16px] font-bold text-slate-900">
                    {strongestMeta?.label || '—'}
                  </p>
                  <p className="mt-0.5 text-[13px] font-semibold" style={{ color: '#059669' }}>
                    {strongestNote.line}
                  </p>
                </div>
              </div>
              <p className="mt-4 text-[13px] text-slate-500 leading-relaxed">
                {strongestNote.hint}
              </p>
            </section>

            {/* Principal limitador */}
            <section
              data-testid="habitos-weakest"
              className="bg-white rounded-2xl shadow-sm border border-slate-100 p-5"
            >
              <p className="text-[11px] font-semibold uppercase tracking-widest text-slate-500 mb-3">
                Seu principal limitador
              </p>
              <div className="flex items-start gap-3">
                <div
                  className="w-12 h-12 rounded-xl flex items-center justify-center shrink-0"
                  style={{ background: '#FDE7DE' }}
                >
                  {weakestMeta && <weakestMeta.Icon className="w-6 h-6" style={{ color: '#DC6B4C' }} strokeWidth={1.75} />}
                </div>
                <div className="min-w-0">
                  <p className="text-[16px] font-bold text-slate-900">
                    {weakestMeta?.label || '—'}
                  </p>
                  <p className="mt-0.5 text-[13px] font-semibold" style={{ color: '#DC6B4C' }}>
                    {weakestNote.line}
                  </p>
                </div>
              </div>
              <p className="mt-4 text-[13px] text-slate-500 leading-relaxed">
                {weakestNote.hint}
              </p>
            </section>

            {/* Análise MedFlow */}
            <section
              data-testid="habitos-analysis"
              className="bg-white rounded-2xl shadow-sm border border-slate-100 p-5 flex flex-col"
            >
              <div className="flex items-center gap-2 mb-3">
                <Brain className="w-4 h-4" style={{ color: '#6C5CE7' }} />
                <p className="text-[11px] font-semibold uppercase tracking-widest text-slate-500">
                  Análise MedFlow
                </p>
              </div>
              <p className="text-[13px] text-slate-700 leading-relaxed">
                {weakestMeta && strongestMeta
                  ? `Seu pilar ${strongestMeta.label} sustenta sua rotina, enquanto ${weakestMeta.label} pede mais atenção. A sugestão de hoje considera esse contexto.`
                  : 'Ainda estou aprendendo sua rotina. Faça alguns check-ins para eu montar sua análise.'}
              </p>
              <div className="mt-4 flex items-center gap-3 p-3 rounded-xl" style={{ background: '#f4f2ff', border: '1px solid #EDE9FF' }}>
                <div className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0" style={{ background: '#EDE9FF' }}>
                  {weakestMeta && <weakestMeta.Icon className="w-4 h-4" style={{ color: '#6C5CE7' }} />}
                </div>
                <div className="min-w-0">
                  <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">Prioridade da semana</p>
                  <p className="text-[14px] font-bold" style={{ color: '#6C5CE7' }}>
                    {weakestMeta ? `Recuperação de ${weakestMeta.label.toLowerCase()}` : 'A definir'}
                  </p>
                </div>
              </div>
              <button
                data-testid="habitos-analysis-cta"
                onClick={() => navigate('/dashboard')}
                className="mt-4 inline-flex items-center gap-1.5 text-[13px] font-semibold self-start transition-colors"
                style={{ color: '#6C5CE7' }}
                onMouseEnter={(e) => (e.currentTarget.style.color = '#5B4BD5')}
                onMouseLeave={(e) => (e.currentTarget.style.color = '#6C5CE7')}
              >
                Ver análise completa
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            </section>
          </div>

          {/* ─── Seus pilares (esq) + Ação rápida (dir) ─── */}
          <div className="grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-4 mb-6">
            <section
              data-testid="habitos-pillars"
              className="bg-white rounded-2xl shadow-sm border border-slate-100 p-6"
            >
              <p className="text-[11px] font-semibold uppercase tracking-widest text-slate-500 mb-4">
                Seus pilares
              </p>
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
                {pillars.map((p) => {
                  const meta = PILLAR_META[p.key];
                  const tone = toneOf(p.score);
                  const Icon = meta?.Icon;
                  return (
                    <div
                      key={p.key}
                      data-testid={`habitos-pillar-${p.key}`}
                      className="flex flex-col items-center text-center"
                    >
                      <div className="relative w-20 h-20 mb-2">
                        <PillarArc score={p.score} color={tone.color} />
                        <div className="absolute inset-0 flex items-center justify-center">
                          {Icon && <Icon className="w-5 h-5 text-slate-400" strokeWidth={1.75} />}
                        </div>
                      </div>
                      <p className="text-[22px] font-bold text-slate-900 tabular leading-none">
                        {p.score ?? '—'}
                      </p>
                      <p className="mt-1 text-[12px] font-semibold text-slate-700">
                        {meta?.label}
                      </p>
                      <p className="text-[11px] font-medium mt-0.5" style={{ color: tone.color }}>
                        {tone.word}
                      </p>
                      <button
                        data-testid={`habitos-pillar-edit-${p.key}`}
                        onClick={() => navigate(PILLAR_EDIT_ROUTE[p.key] || '/checkin')}
                        className="mt-2 text-[11.5px] font-semibold px-3 py-1.5 rounded-lg border transition-colors"
                        style={{
                          color: tone.color,
                          borderColor: tone.color,
                          background: '#ffffff',
                        }}
                      >
                        Ajustar
                      </button>
                    </div>
                  );
                })}
              </div>
            </section>

            <section
              data-testid="habitos-quick-actions"
              className="bg-white rounded-2xl shadow-sm border border-slate-100 p-5 flex flex-col"
            >
              <p className="text-[11px] font-semibold uppercase tracking-widest text-slate-500 mb-3">
                Ação rápida
              </p>
              <button
                data-testid="habitos-cta-checkin"
                onClick={() => navigate('/checkin')}
                className="flex items-center gap-3 p-3 rounded-xl hover:bg-slate-50 transition-colors border border-transparent hover:border-slate-100 text-left"
              >
                <div className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0" style={{ background: '#EDE9FF' }}>
                  <RefreshCw className="w-5 h-5" style={{ color: '#6C5CE7' }} strokeWidth={1.75} />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-[14px] font-semibold text-slate-900">Atualizar contexto</p>
                  <p className="text-[12px] text-slate-500">Como você está agora?</p>
                </div>
                <ArrowRight className="w-4 h-4 text-slate-400" />
              </button>

              <button
                data-testid="habitos-cta-focus"
                onClick={() => navigate('/pomodoro')}
                className="mt-2 flex items-center gap-3 p-3 rounded-xl hover:bg-slate-50 transition-colors border border-transparent hover:border-slate-100 text-left"
              >
                <div className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0" style={{ background: '#EDE9FF' }}>
                  <Timer className="w-5 h-5" style={{ color: '#6C5CE7' }} strokeWidth={1.75} />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-[14px] font-semibold text-slate-900">Foco agora</p>
                  <p className="text-[12px] text-slate-500">Pomodoro adaptativo</p>
                </div>
                <ArrowRight className="w-4 h-4 text-slate-400" />
              </button>
            </section>
          </div>

          {/* ─── Banner learning (real) ─── */}
          {showLearning && (
            <section
              data-testid="habitos-learning"
              className="rounded-2xl border p-5 flex items-start gap-3"
              style={{ background: '#f4f2ff', borderColor: '#EDE9FF' }}
            >
              <div className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0" style={{ background: '#EDE9FF' }}>
                <Sparkles className="w-4 h-4" style={{ color: '#6C5CE7' }} />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-[14px] font-semibold text-slate-900">
                  {noticed?.text || 'Ainda estou aprendendo sobre sua rotina.'}
                </p>
                <p className="mt-1 text-[13px] text-slate-500">
                  {noticed?.hint || 'Continue registrando seus dias para receber análises cada vez mais personalizadas.'}
                </p>
              </div>
              <button
                data-testid="habitos-learning-dismiss"
                onClick={() => setDismissed(true)}
                className="text-[13px] font-semibold px-4 py-2 rounded-xl border transition-colors shrink-0"
                style={{ color: '#6C5CE7', borderColor: '#DDD6F0' }}
                onMouseEnter={(e) => (e.currentTarget.style.background = '#EDE9FF')}
                onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
              >
                Entendi
              </button>
            </section>
          )}

          {/* ─── Autocuidado essencial (mantém o valor real do backend) ─── */}
          {care?.tasks?.length > 0 && (
            <section
              data-testid="habitos-care"
              className="mt-6 bg-white rounded-2xl shadow-sm border border-slate-100 p-5 md:p-6"
            >
              <div className="flex items-center justify-between mb-4">
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-widest text-slate-500">
                    Autocuidado essencial
                  </p>
                  <p className="mt-1 text-[14px] text-slate-600">
                    Pequenos gestos ao longo do dia — clique para registrar.
                  </p>
                </div>
                <p className="text-[13px] font-semibold text-slate-700 mono tabular">
                  {care.tasks.reduce((n, t) => n + t.done_today, 0)}
                  <span className="text-slate-400"> / {care.tasks.reduce((n, t) => n + t.target, 0)}</span>
                  <span className="ml-2 text-[11px] text-slate-500 font-normal uppercase tracking-wider">de hoje</span>
                </p>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                {care.tasks.map((t) => {
                  const complete = t.done_today >= t.target;
                  const percent = Math.round((t.progress || 0) * 100);
                  return (
                    <button
                      key={t.slug}
                      data-testid={`care-btn-${t.slug}`}
                      onClick={async () => {
                        try {
                          await api.post('/care/log', { slug: t.slug });
                          const { data } = await api.get('/care/today');
                          setCare(data);
                        } catch { /* noop */ }
                      }}
                      className="text-left border border-slate-100 rounded-xl p-4 hover:bg-slate-50 transition-colors"
                    >
                      <div className="flex items-center justify-between mb-2">
                        <span
                          className="w-9 h-9 rounded-lg flex items-center justify-center"
                          style={{ background: complete ? '#ECFDF5' : '#EDE9FF', color: complete ? '#059669' : '#6C5CE7' }}
                        >
                          <Footprints className="w-4 h-4" strokeWidth={1.75} />
                        </span>
                        <span className="mono text-[12.5px] font-semibold text-slate-900">
                          {t.done_today}/{t.target}
                        </span>
                      </div>
                      <p className="text-[13.5px] font-semibold text-slate-900 leading-tight">{t.title}</p>
                      <div className="mt-2 h-1.5 bg-slate-100 rounded-full overflow-hidden">
                        <div
                          className="h-full rounded-full transition-all"
                          style={{
                            width: `${percent}%`,
                            background: complete ? '#059669' : '#6C5CE7',
                          }}
                        />
                      </div>
                    </button>
                  );
                })}
              </div>
            </section>
          )}

          <FooterV2 />

          <div className="mt-2 mb-4 flex items-center justify-center">
            <p className="text-[11px] tracking-wider uppercase text-slate-400 font-medium">
              Protegido conforme a LGPD
            </p>
          </div>
        </div>
      </div>

      {loading && (
        <div className="fixed top-4 right-4 z-40 bg-white rounded-lg px-3 py-2 shadow-md border border-slate-100 flex items-center gap-2">
          <Loader2 className="w-4 h-4 animate-spin" style={{ color: '#6C5CE7' }} />
          <span className="text-[12px] text-slate-600">Carregando…</span>
        </div>
      )}
    </Shell>
  );
};

export default Habitos;
