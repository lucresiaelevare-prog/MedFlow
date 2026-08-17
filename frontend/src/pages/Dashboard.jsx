import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Wind, RefreshCw, Timer, ChevronDown, ChevronUp,
  Bell, BookOpen, HelpCircle, RotateCw, Play,
} from 'lucide-react';
import api from '@/lib/api';
import IDS from '@/constants/testIds';
import { useAuth } from '@/context/AuthContext';
import Shell from '@/components/Shell';
import RecommendationHero from './dashboard/RecommendationHero';
import RhythmStrip from './dashboard/RhythmStrip';
import RecommendationCard from './dashboard/RecommendationCard';
import MentalHealthAlertCard from './dashboard/MentalHealthAlertCard';
import PriorityCard from './dashboard/PriorityCard';
import EffectivenessCard from './dashboard/EffectivenessCard';
import RescheduleCard from './dashboard/RescheduleCard';
import PeerBenchmarkCard from './dashboard/PeerBenchmarkCard';
import TutorIACard from './dashboard/TutorIACard';
import ContextualMessage from './dashboard/ContextualMessage';

/**
 * Painel de Controle — Dashboard reformulado.
 *
 * Filosofia (validada com PO em jan/2026):
 * A tela responde 4 perguntas em ordem, sem competir com a Home Inteligente:
 *  1. Como estou?  → IEA + 5 pilares.
 *  2. O que faço agora?  → 2 CTAs: Atualizar contexto · Foco agora.
 *  3. O que merece atenção?  → 1 card "O que percebi hoje" (dados reais ou learning).
 *  4. Aprofundar? → botão "Ver análise completa" que expande TUDO o resto
 *                   (progresso do dia, meta da semana, priorização, missões, etc.).
 *
 * Regra: nenhuma informação ocupa espaço na tela principal se não responder
 * a uma dessas perguntas. Ver /app/docs/frontend-rules.md #4.
 */

// ─── Anel de progresso (usado só na área expandida)
const ProgressRing = ({ value, max, color, label, sub, testId }) => {
  const pct = max > 0 ? Math.min(1, value / max) : 0;
  const R = 32, C = 2 * Math.PI * R;
  return (
    <div data-testid={testId} className="flex flex-col items-center">
      <div className="relative w-[76px] h-[76px]">
        <svg viewBox="0 0 80 80" className="w-full h-full -rotate-90">
          <circle cx="40" cy="40" r={R} fill="none" stroke="var(--mf-hair)" strokeWidth="6" />
          <circle cx="40" cy="40" r={R} fill="none" stroke={color} strokeWidth="6"
                  strokeDasharray={C} strokeDashoffset={C * (1 - pct)} strokeLinecap="round"
                  style={{ transition: 'stroke-dashoffset 500ms ease-out' }} />
        </svg>
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="mono text-[16px] font-semibold text-zinc-900"><span>{value}</span></span>
        </div>
      </div>
      <p className="mt-2 text-[11.5px] font-semibold text-zinc-900 uppercase tracking-wider"><span>{label}</span></p>
      <p className="text-[11px] text-zinc-500 mono"><span>{sub}</span></p>
    </div>
  );
};

// ─── v2 MissaoDeHoje — real title/subtitle + mock subtasks + real time ────
const MissaoDeHojeV2 = ({ rec, onStart }) => {
  const title = rec?.title || 'Vamos começar quando você estiver pronto';
  const subtitle = rec?.subtitle || null;
  const minutes = rec?.duration_min && rec.duration_min > 1 ? rec.duration_min : 22; // mock fallback
  // Subtarefas — sem endpoint, ficam como pistas visuais fixas do fluxo do MedFlow
  const subtasks = [
    { label: 'Estudo teórico', detail: 'com o Tutor', Icon: BookOpen },
    { label: 'Questões',       detail: '2 blocos',        Icon: HelpCircle },
    { label: 'Revisão',        detail: 'espaçada',        Icon: RotateCw },
  ];
  return (
    <div
      data-testid="dashboard-missao"
      className="rounded-2xl shadow-sm border overflow-hidden"
      style={{
        background: 'linear-gradient(135deg, #f8f6ff 0%, #f3f0ff 40%, #ede9ff 100%)',
        borderColor: '#e4dff5',
      }}
    >
      <div className="p-6 lg:p-8">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            <p className="text-[11px] font-semibold uppercase tracking-widest mb-2" style={{ color: '#6C5CE7' }}>
              Missão de Hoje
            </p>
            <h2 className="text-[22px] lg:text-[28px] font-bold text-slate-900 tracking-tight leading-tight">
              {title}
            </h2>
            {subtitle && (
              <p className="mt-3 text-[13.5px] text-slate-600 leading-relaxed">{subtitle}</p>
            )}
          </div>
        </div>
        <div className="flex flex-wrap gap-6 mt-6 mb-6">
          {subtasks.map((t) => (
            <div key={t.label} className="flex items-center gap-2.5">
              <t.Icon className="w-5 h-5" style={{ color: '#6C5CE7' }} />
              <div>
                <p className="text-[13px] font-medium text-slate-700">{t.label}</p>
                <p className="text-[11px] text-slate-400">{t.detail}</p>
              </div>
            </div>
          ))}
        </div>
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pt-4 border-t"
             style={{ borderColor: '#ddd6f0' }}>
          <div>
            <p className="text-[12px] text-slate-500">Tempo estimado</p>
            <p className="text-[28px] font-bold leading-none mt-1" style={{ color: '#6C5CE7' }}>
              {minutes} minutos
            </p>
          </div>
          <button
            data-testid="dashboard-missao-start"
            onClick={onStart}
            className="inline-flex items-center gap-2.5 text-white font-semibold px-6 py-3 rounded-xl transition-all active:scale-[0.97]"
            style={{
              background: '#6C5CE7',
              boxShadow: '0 10px 25px -8px rgba(108, 92, 231, 0.4)',
            }}
            onMouseEnter={(e) => (e.currentTarget.style.background = '#5B4BD5')}
            onMouseLeave={(e) => (e.currentTarget.style.background = '#6C5CE7')}
          >
            <Play className="w-5 h-5 fill-current" />
            <span>{rec?.action_label || 'Continuar missão'}</span>
          </button>
        </div>
      </div>
    </div>
  );
};

// ─── Footer — orientações de produto sem promessas técnicas ────
const FooterV2 = () => (
  <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 py-4 mt-8 border-t border-slate-100">
    <div className="flex items-center gap-2 text-[11.5px] text-slate-400">
      <RefreshCw className="w-3.5 h-3.5" />
      <span>Seu próximo passo fica organizado aqui.</span>
    </div>
    <div className="flex items-center gap-2 text-[11.5px] text-slate-400">
      <HelpCircle className="w-3.5 h-3.5" />
      <span>Precisa de ajuda?</span>
    </div>
  </div>
);

const Dashboard = () => {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [loading, setLoading] = useState(true);
  const [bundle, setBundle] = useState(null);
  const [iea, setIea] = useState(null);
  const [streak, setStreak] = useState(0);
  const [regenerating, setRegenerating] = useState(false);
  const [mhAlert, setMhAlert] = useState(null);
  const [pomToday, setPomToday] = useState({ totals: { focused_minutes: 0, completed_sessions: 0 } });
  const [latestStress, setLatestStress] = useState(null);
  const [weekGoals, setWeekGoals] = useState(null);
  const [noticed, setNoticed] = useState(null); // {mode: observed|learning, text}
  const [reschedule, setReschedule] = useState(null); // proposta de reordenação (P0.1)
  const [consistency, setConsistency] = useState(null);
  const [expanded, setExpanded] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const [i, s, a, p, h, w, home] = await Promise.all([
        api.get('/iea'),
        api.get('/streak'),
        api.get('/mental-health/alert'),
        api.get('/pomodoro/today'),
        api.get('/history?days=1'),
        api.get('/goals/weekly'),
        api.get('/home/today').catch(() => ({ data: {} })),
      ]);
      setIea(i.data);
      setStreak(s.data.streak || 0);
      setMhAlert(a.data.alert || null);
      setPomToday(p.data || { totals: { focused_minutes: 0, completed_sessions: 0 } });
      const cks = h.data.checkins || [];
      setLatestStress(cks.length ? cks[cks.length - 1].stress : null);
      setWeekGoals(w.data || null);
      setNoticed(home?.data?.noticed || {
        mode: 'learning',
        text: 'Ainda estou aprendendo como você estuda.',
      });
      setReschedule(home?.data?.reschedule || null);
      setConsistency(home?.data?.consistency || null);
      // ITER14 — o card de recomendação agora consome o motor NOVO (/home/today.recommendation),
      // que traz why_signals + why_now. Nada de missions/bundle antigo.
      const rec = home?.data?.recommendation || null;
      if (rec?.id) {
        api.post(`/recommendations/${rec.id}/shown`).catch(() => {});
      }
      setBundle(rec ? {
        recommendation: rec,
        missions: [{
          id: rec.id,
          title: rec.title,
          minutes: rec.duration_min || 0,
          category: rec.kind === 'care' ? 'descanso' : 'estudo',
          why: rec.reasoning,
          why_signals: rec.why_signals || [],
          why_now: rec.why_now,
          action_route: rec.action_route,
          action_label: rec.action_label,
          completed: false,
          skipped: false,
        }],
      } : null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const regenerate = async () => {
    setRegenerating(true);
    try {
      await load();
    } finally {
      setRegenerating(false);
    }
  };

  const startRecommendation = (action = rec) => {
    if (action?.id) api.post(`/recommendations/${action.id}/started`).catch(() => {});
    if (action?.action_route) navigate(action.action_route);
  };

  const trackWhyExpanded = () => {
    if (rec?.id) api.post(`/recommendations/${rec.id}/why-expanded`).catch(() => {});
  };

  const toggleMission = async (mission, completed) => {
    // ITER14 — RecommendationCard usa este handler para "Aceitar decisão".
    // Persistimos como lifecycle event no motor de eficácia.
    if (!mission?.id) return;
    try {
      if (completed) {
        await api.post(`/recommendations/${mission.id}/completed`);
      } else {
        await api.post(`/recommendations/${mission.id}/abandoned`);
      }
    } catch { /* noop */ }
    setBundle((b) => b ? {
      ...b,
      missions: b.missions.map((m) =>
        m.id === mission.id ? { ...m, completed, skipped: !completed } : m,
      ),
    } : b);
    try {
      const i = await api.get('/iea');
      setIea(i.data);
    } catch { /* noop */ }
  };

  const missions = bundle?.missions || [];
  const primary = missions.find((m) => !m.completed && !m.skipped) || null;

  // Saudação humanizada e acionável — mantém identidade do MedFlow
  const bundleGreeting = bundle?.greeting || null;

  // Recomendação principal (mesma fonte que a Home Inteligente usa)
  const rec = bundle?.recommendation || (primary ? {
    title: primary.title,
    subtitle: primary.subtitle || 'Missão do Tutor',
    duration_min: primary.minutes || 0,
    action_route: primary.action_route || '/checkin',
    action_label: primary.action_label || 'Começar',
  } : null);

  // Nome do aluno vindo do AuthContext (real) → fallback para greeting do bundle
  const displayName = ((user?.name || bundle?.user_name || '') + '').trim().split(' ')[0] || '';
  const hour = new Date().getHours();
  const timeOfDay = hour < 12 ? 'Bom dia' : hour < 18 ? 'Boa tarde' : 'Boa noite';
  const greetingLine = bundleGreeting || timeOfDay;

  return (
    <Shell>
      <div
        data-testid={IDS.dashboard.root}
        className="overflow-x-clip p-4 sm:p-5 md:p-7 lg:p-10"
        style={{ background: '#f8f7fc' }}
      >
        <div className="max-w-6xl mx-auto">
          {/* Topo: Saudação (esq) + sino (dir) */}
          <div className="mb-6 flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between md:mb-8">
            <div className="flex-1 min-w-0">
              <h1
                data-testid="dashboard-greeting"
                className="text-[24px] md:text-[30px] font-bold text-slate-900 tracking-tight leading-tight"
              >
                <span>{greetingLine}{displayName ? `, ${displayName}` : ''}! 👋</span>
              </h1>
              <p className="mt-2 text-[13.5px] text-slate-500 leading-relaxed max-w-xl">
                {streak > 0 ? (
                  <>
                    <span>Você mantém sua sequência há </span>
                    <strong className="text-slate-700">{streak}</strong>
                    <span>{streak === 1 ? ' dia. ' : ' dias. '}</span>
                    <span>Hoje, você só precisa seguir o próximo passo.</span>
                  </>
                ) : consistency?.active_days_last5 > 0 ? (
                  <>
                    <span>Você estudou </span>
                    <strong className="text-slate-700">{consistency.active_days_last5} dos últimos 5 dias.</strong>
                    <span> Hoje, você só precisa seguir o próximo passo.</span>
                  </>
                ) : (
                  <span>Seu plano de hoje está pronto. Comece por uma missão de cada vez.</span>
                )}
              </p>
            </div>
            <button
              data-testid="dashboard-notif-btn"
              onClick={() => {}}
              className="relative w-11 h-11 bg-white rounded-xl shadow-sm border border-slate-100 flex items-center justify-center hover:bg-slate-50 transition-colors shrink-0"
              aria-label="Notificações"
            >
              <Bell className="w-5 h-5 text-slate-500" />
            </button>
          </div>

          {/* Faixa de ritmo — card CENTRAL: IEA + ECG por pilar + msg humana */}
          <div className="mb-4">
            <RhythmStrip iea={iea} />
          </div>

          {/* Conector visual ↓ — narrativa de causalidade */}
          <div className="flex items-center justify-center mb-4" aria-hidden="true">
            <div className="w-px h-4 bg-gradient-to-b from-transparent via-slate-300 to-slate-300" />
          </div>

          {/* Missão única do dia — ação principal da jornada */}
          <div className="mb-6">
            <RecommendationHero
              rec={rec}
              onStart={startRecommendation}
              onWhyExpanded={trackWhyExpanded}
            />
          </div>

          {/* Os 5 pilares detalhados — REMOVIDO (v13): redundante com o
              ECG-semáforo do RhythmStrip que já mostra label + score + status
              por pilar, e nomeia o pilar limitante na mensagem humana. */}

          {/* Tutor IA — identidade preservada, visual v2 */}
          <div className="mb-6">
            <TutorIACard onOpen={() => navigate('/tutor')} />
          </div>

          <ContextualMessage weekGoals={weekGoals} noticed={noticed} />

          {/* Atalhos secundários */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-6">
            <button
              data-testid="dashboard-cta-checkin"
              onClick={() => navigate('/checkin')}
              className="min-h-24 rounded-2xl border border-slate-100 bg-white p-5 text-left shadow-sm transition-colors hover:bg-slate-50"
            >
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0"
                     style={{ background: 'var(--mf-brand-soft, #EDE9FF)' }}>
                  <RefreshCw strokeWidth={1.75} className="w-5 h-5" style={{ color: 'var(--mf-brand, #6C5CE7)' }} />
                </div>
                <div>
                  <p className="text-[15px] font-semibold text-slate-900">Atualizar contexto</p>
                  <p className="mt-0.5 text-[12.5px] text-slate-500">Como você está agora</p>
                </div>
              </div>
            </button>
            <button
              data-testid="dashboard-cta-focus"
              onClick={() => navigate('/pomodoro')}
              className="min-h-24 rounded-2xl border border-slate-100 bg-white p-5 text-left shadow-sm transition-colors hover:bg-slate-50"
            >
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0"
                     style={{ background: 'var(--mf-brand-soft, #EDE9FF)' }}>
                  <Timer strokeWidth={1.75} className="w-5 h-5" style={{ color: 'var(--mf-brand, #6C5CE7)' }} />
                </div>
                <div>
                  <p className="text-[15px] font-semibold text-slate-900">Foco agora</p>
                  <p className="mt-0.5 text-[12.5px] text-slate-500">Pomodoro adaptativo</p>
                </div>
              </div>
            </button>
          </div>

          {/* O que percebi hoje */}
          {noticed && (
            <section
              data-testid="dashboard-noticed"
              data-mode={noticed.mode}
              className="mb-6 bg-white rounded-2xl shadow-sm border border-slate-100 p-5 md:p-6"
              translate="no"
            >
              <p className="text-[11px] font-semibold uppercase tracking-widest text-slate-600">O que percebi hoje</p>
              <p
                data-testid="dashboard-noticed-text"
                className={`mt-2 text-[15px] md:text-[16px] leading-relaxed ${
                  noticed.mode === 'observed' ? 'text-slate-800' : 'text-slate-500'
                }`}
              >
                <span>{noticed.text}</span>
              </p>
              {noticed.mode === 'learning' && noticed.hint && (
                <p className="mt-1 text-[13px] text-slate-400 leading-relaxed">{noticed.hint}</p>
              )}
            </section>
          )}

          {/* Coach de stress alto */}
          {latestStress != null && latestStress >= 7 && (
            <button
              data-testid="dashboard-stress-coach"
              onClick={() => navigate('/mindfulness')}
              className="w-full mb-6 rounded-2xl p-5 text-left hover:opacity-95 transition-opacity border"
              style={{ background: 'var(--mf-care-soft)', borderColor: 'var(--mf-care)' }}
            >
              <div className="flex items-start gap-3">
                <div className="w-10 h-10 rounded-lg flex items-center justify-center text-white shrink-0"
                     style={{ background: 'var(--mf-care)' }}>
                  <Wind strokeWidth={1.75} className="w-5 h-5" />
                </div>
                <div className="flex-1">
                  <p className="text-[11px] font-semibold uppercase tracking-widest" style={{ color: 'var(--mf-care)' }}>
                    Seu último check-in indicou stress alto
                  </p>
                  <p className="mt-1 text-[15px] font-semibold text-slate-900">
                    Que tal 3 minutos de respiração agora?
                  </p>
                </div>
              </div>
            </button>
          )}

          {/* Reordenação por fadiga */}
          <RescheduleCard reschedule={reschedule} onChanged={load} />

          {/* Alerta clínico */}
          {mhAlert && !mhAlert.acknowledged && (
            <div className="mt-6">
              <MentalHealthAlertCard
                alert={mhAlert}
                onAck={async () => {
                  try { await api.post('/mental-health/alert/ack', { alert_id: mhAlert.id }); } catch (e) { /* noop */ }
                  setMhAlert({ ...mhAlert, acknowledged: true });
                }}
              />
            </div>
          )}

          {/* Análise completa — colapsável */}
          <div className="mt-8 space-y-5">
            <EffectivenessCard />
            <PeerBenchmarkCard />
          </div>

          <div className="mt-6">
            <button
              data-testid="dashboard-toggle-details"
              onClick={() => setExpanded((v) => !v)}
              aria-expanded={expanded}
              className="w-full flex items-center justify-center gap-2 py-3 text-[13.5px] text-slate-500 hover:text-slate-800 transition-colors"
            >
              <span>{expanded ? 'Fechar análise completa' : 'Ver análise completa'}</span>
              {expanded
                ? <ChevronUp strokeWidth={1.75} className="w-4 h-4" />
                : <ChevronDown strokeWidth={1.75} className="w-4 h-4" />}
            </button>

            <div
              data-testid="dashboard-details"
              data-expanded={expanded}
              className="overflow-hidden transition-all duration-300"
              style={{ maxHeight: expanded ? '4000px' : '0', opacity: expanded ? 1 : 0 }}
              aria-hidden={!expanded}
            >
              <div className="pt-2 space-y-5">
                <section data-testid="dashboard-today-progress" className="bg-white rounded-2xl shadow-sm border border-slate-100 p-5 md:p-6">
                  <div className="flex items-center justify-between mb-4">
                    <p className="text-[11px] font-semibold uppercase tracking-widest text-slate-600">Progresso de hoje</p>
                    <p className="text-[11px] text-slate-400 uppercase tracking-wider">Meta pessoal</p>
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <ProgressRing
                      testId="ring-missions"
                      value={(bundle?.missions || []).filter((m) => m.completed).length}
                      max={(bundle?.missions || []).length || 3}
                      color="var(--mf-brand)"
                      label="Missões"
                      sub={`de ${(bundle?.missions || []).length || 0}`}
                    />
                    <ProgressRing
                      testId="ring-focus"
                      value={pomToday?.totals?.focused_minutes || 0}
                      max={90}
                      color="var(--mf-success)"
                      label="Foco (min)"
                      sub={`${pomToday?.totals?.completed_sessions || 0} sessões`}
                    />
                  </div>
                </section>

                {weekGoals && (
                  <section data-testid="dashboard-week-progress" className="bg-white rounded-2xl shadow-sm border border-slate-100 p-5 md:p-6">
                    <div className="flex items-center justify-between mb-4">
                      <div>
                        <p className="text-[11px] font-semibold uppercase tracking-widest text-slate-600">Meta da semana</p>
                        <p className="mt-1 text-[13px] text-slate-500">
                          {weekGoals.week_start} → {weekGoals.week_end}
                        </p>
                      </div>
                      <p data-testid="week-goals-count" className="mono text-[22px] font-semibold text-slate-900 tabular">
                        <span>{weekGoals.achieved}</span>
                        <span className="text-[14px] text-slate-400 font-medium ml-0.5">/{weekGoals.total}</span>
                      </p>
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2.5">
                      {(weekGoals.goals || []).map((g) => (
                        <div
                          key={g.slug}
                          data-testid={`week-goal-${g.slug}`}
                          className="border border-slate-100 rounded-lg p-3"
                          style={{ background: g.achieved ? 'var(--mf-success-soft, #ECFDF5)' : 'transparent' }}
                        >
                          <div className="flex items-baseline justify-between gap-2">
                            <p className="text-[12.5px] font-medium text-slate-800 truncate">{g.title}</p>
                            <span className="mono text-[12px] font-semibold text-slate-900 shrink-0">
                              {g.current}/{g.target}
                            </span>
                          </div>
                          <div className="mt-2 h-1.5 rounded-full overflow-hidden" style={{ background: 'var(--mf-hair)' }}>
                            <div
                              className="h-full rounded-full transition-all duration-500"
                              style={{
                                width: `${Math.min(100, Math.round((g.progress || 0) * 100))}%`,
                                background: g.achieved ? 'var(--mf-success, #10B981)' : 'var(--mf-brand)',
                              }}
                            />
                          </div>
                        </div>
                      ))}
                    </div>
                  </section>
                )}

                <PriorityCard />

                <RecommendationCard
                  mission={primary}
                  iea={iea}
                  loading={loading || regenerating}
                  onComplete={() => primary && toggleMission(primary, true)}
                  onSkip={() => primary && toggleMission(primary, false)}
                  onRegenerate={regenerate}
                />
              </div>
            </div>
          </div>

          {/* Footer v2 */}
          <FooterV2 />

          <div className="mt-4 mb-2 flex items-center justify-center">
            <p className="text-[11px] tracking-wider uppercase text-slate-400 font-medium">
              Protegido conforme a LGPD
            </p>
          </div>
        </div>
      </div>
    </Shell>
  );
};

export default Dashboard;
