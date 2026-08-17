import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Play, CheckCircle2, Circle, Loader2, ArrowRight, LineChart, RefreshCw, BookOpen, Heart,
  RotateCcw, Sparkles,
} from 'lucide-react';
import Shell from '@/components/Shell';
import api from '@/lib/api';
import { useAuth } from '@/context/AuthContext';
import { getCheckpoint, clearCheckpoint } from '@/lib/resume';

/**
 * /hoje — Centro de execução ("o volante").
 *
 * Responde apenas: "O que eu faço agora?"
 * Prioridades do card principal:
 *   1) Checkpoint ativo   → "Continuar de onde você parou"
 *   2) Check-in pendente  → recommendation do backend
 *   3) Próxima missão     → primeira missão não concluída
 *
 * Sem ECG, sem pilares, sem análise pesada — tudo isso vive em /dashboard.
 */

// ─── Rotas por categoria (para o botão → das missões) ─────────────
const CATEGORY_ROUTE = {
  aula:        '/subjects',
  estudo:      '/tutor',
  prova:       '/subjects',
  movimento:   '/checkin',
  descanso:    '/pomodoro',
  alimentacao: '/checkin',
  bemestar:    '/mindfulness',
  social:      '/community',
  admin:       '/settings',
};

// ─── Buckets visuais (Estudos vs Hábitos) ─────────────────────────
const STUDY_CATS = new Set(['aula', 'estudo', 'prova']);
const HABIT_CATS = new Set(['movimento', 'descanso', 'alimentacao', 'bemestar', 'social']);

const bucketOf = (m) => {
  if (STUDY_CATS.has(m.category)) return 'estudos';
  if (HABIT_CATS.has(m.category)) return 'habitos';
  // Fallback por título (missões geradas por LLM podem vir sem categoria clara)
  const t = (m.title || '').toLowerCase();
  if (/(quest|flashcard|revis|simulad|resumo|estud|aula|caso cl|prova)/.test(t)) return 'estudos';
  if (/(água|agua|caminh|sono|dorm|along|pausa|respir|hidrat|movimente|movimento)/.test(t)) return 'habitos';
  return 'estudos';
};

const routeForMission = (m) => {
  if (m.kind === 'exam')  return '/subjects';
  if (m.kind === 'block') return '/dashboard';
  return CATEGORY_ROUTE[m.category] || '/pomodoro';
};

// ─── Preceptor hint (regra determinística, sem LLM) ──────────────
// Só aparece se o check-in de hoje já foi feito. Máx. 2 linhas, sem CTA.
const preceptorHint = (home) => {
  if (!home?.has_checkin_today) return null;
  const rec = home?.recommendation;

  // 1) Se a recomendação já traz uma matéria/tópico, orienta com ele.
  const title = rec?.title || '';
  const subj = extractSubject(title);
  if (subj) {
    return `Agora que entendi como você está hoje, recomendo começar por ${subj}.`;
  }

  // 2) Fallback por horário (Brasil UTC-3 aproximado — usa hora local do navegador).
  const h = new Date().getHours();
  if (h >= 5 && h < 12) {
    return 'Manhãs costumam ser seu momento de maior clareza. Comece por uma tarefa curta.';
  }
  if (h >= 12 && h < 18) {
    return 'Hoje seu melhor rendimento deve acontecer nas próximas duas horas. Vamos aproveitar.';
  }
  return 'À noite, uma revisão leve consolida mais que estudar assunto novo. Fica tranquilo.';
};

// Extrai possível matéria da frase da recomendação.
// Exemplos: "Revisar Cardiologia agora" → "Cardiologia"
//           "Estudar Farmacologia por 30 min" → "Farmacologia"
function extractSubject(title) {
  if (!title) return null;
  const m = title.match(/(?:revisar|estudar|começar|revisão de|questões de|flashcards de|resumo de|aula de)\s+([A-ZÀ-Ú][\wÀ-ÿ\s]{2,30}?)(?:\s+(?:agora|por|de|para|em)|$)/i);
  return m ? m[1].trim().replace(/\s+/g, ' ') : null;
}

// ─── Ícones/labels dos checkpoints ────────────────────────────────
const CHECKPOINT_LABEL = {
  pomodoro:   { label: 'Retomar Pomodoro',    Icon: RotateCcw },
  tutor:      { label: 'Continuar no Tutor',   Icon: RotateCcw },
  flashcards: { label: 'Finalizar Flashcards', Icon: RotateCcw },
  questions:  { label: 'Continuar Questões',   Icon: RotateCcw },
  simulado:   { label: 'Continuar Simulado',   Icon: RotateCcw },
  resumo:     { label: 'Continuar Resumo',     Icon: RotateCcw },
  revisao:    { label: 'Continuar Revisão',    Icon: RotateCcw },
};

const SmartHome = () => {
  const navigate = useNavigate();
  const { user } = useAuth();

  const [home, setHome] = useState(null);
  const [bundle, setBundle] = useState(null);
  const [resume, setResume] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState(null);
  const [generating, setGenerating] = useState(false);

  const firstName = (user?.name || '').trim().split(' ')[0] || '';

  const loadAll = async () => {
    setLoading(true);
    try {
      const [h, m, r] = await Promise.all([
        api.get('/home/today').then((res) => res.data).catch(() => null),
        api.get('/missions/today').then((res) => res.data?.bundle || null).catch(() => null),
        getCheckpoint(),
      ]);
      setHome(h);
      setBundle(m);
      setResume(r);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadAll(); }, []);

  const missions = bundle?.missions || [];
  const total = missions.length;
  const done = missions.filter((m) => m.completed).length;
  const pct = total ? Math.round((done / total) * 100) : 0;

  const nextMission = useMemo(
    () => missions.find((m) => !m.completed && !m.skipped) || null,
    [missions]
  );

  // ─── Card principal — resume vence tudo ─────────────────────────
  let primary = null;
  if (resume) {
    const info = CHECKPOINT_LABEL[resume.kind] || CHECKPOINT_LABEL.pomodoro;
    primary = {
      mode: 'resume',
      kicker: 'Continuar de onde você parou',
      title: resume.title,
      subtitle: resume.subtitle,
      route: resume.route,
      buttonLabel: info.label,
      Icon: info.Icon,
    };
  } else if (home?.recommendation?.action_route) {
    const rec = home.recommendation;
    primary = {
      mode: 'recommendation',
      kicker: 'Próxima missão',
      title: rec.title,
      subtitle: rec.duration_min ? `${rec.duration_min} min` : null,
      route: rec.action_route,
      buttonLabel: rec.action_label || 'Começar',
      Icon: Play,
      minutes: rec.duration_min,
    };
  } else if (nextMission) {
    primary = {
      mode: 'mission',
      kicker: 'Próxima missão',
      title: nextMission.title,
      subtitle: nextMission.minutes ? `${nextMission.minutes} min` : null,
      route: routeForMission(nextMission),
      buttonLabel: 'Começar',
      Icon: Play,
      minutes: nextMission.minutes,
    };
  }

  const hint = preceptorHint(home);

  const buckets = useMemo(() => {
    const est = [], hab = [];
    missions.forEach((m) => (bucketOf(m) === 'habitos' ? hab.push(m) : est.push(m)));
    return { est, hab };
  }, [missions]);

  const toggle = async (m) => {
    if (busyId) return;
    setBusyId(m.id);
    setBundle((prev) => prev && ({
      ...prev,
      missions: prev.missions.map((x) =>
        x.id === m.id ? { ...x, completed: !x.completed, skipped: false } : x
      ),
    }));
    try {
      await api.post(`/missions/${m.id}/complete`, { completed: !m.completed });
    } catch {
      setBundle((prev) => prev && ({
        ...prev,
        missions: prev.missions.map((x) =>
          x.id === m.id ? { ...x, completed: m.completed, skipped: m.skipped } : x
        ),
      }));
    } finally {
      setBusyId(null);
    }
  };

  const generateMissions = async () => {
    if (generating) return;
    setGenerating(true);
    try {
      const { data } = await api.post('/missions/generate');
      setBundle(data?.bundle || null);
    } catch (_e) { /* silencioso */ }
    finally { setGenerating(false); }
  };

  const dismissResume = async () => {
    await clearCheckpoint();
    setResume(null);
  };

  return (
    <Shell>
      <div
        data-testid="smart-home-root"
        className="p-5 md:p-7 lg:p-10 min-h-screen"
        style={{ background: '#f8f7fc' }}
      >
        <div className="max-w-3xl mx-auto animate-fade-in">
          {/* ── Saudação ─────────────────────────────────────────── */}
          <header className="mb-6">
            <h1
              data-testid="smart-home-greeting"
              className="text-[26px] md:text-[30px] font-semibold text-slate-900 tracking-tight leading-tight"
            >
              {home?.greeting || 'Olá'}{firstName ? `, ${firstName}` : ''} <span aria-hidden>👋</span>
            </h1>
            {total > 0 && (
              <p className="mt-1.5 text-[14px] text-slate-500">
                Hoje você tem <strong className="text-slate-800">{total}</strong>{' '}
                {total === 1 ? 'missão' : 'missões'}.
              </p>
            )}
          </header>

          {loading ? (
            <div className="h-48 bg-white rounded-2xl border border-slate-100 animate-pulse" />
          ) : (
            <>
              {/* ── Card principal (Resume > Check-in > Missão) ── */}
              {primary && (
                <PrimaryCard
                  primary={primary}
                  onStart={() => navigate(primary.route)}
                  onDismiss={primary.mode === 'resume' ? dismissResume : null}
                />
              )}

              {/* ── Preceptor: 1 linha, sem CTA, só após check-in ── */}
              {hint && (
                <p
                  data-testid="smart-home-preceptor-hint"
                  className="mt-3 mb-6 flex items-start gap-2 text-[13.5px] text-slate-500 leading-relaxed"
                >
                  <Sparkles className="w-4 h-4 shrink-0 mt-0.5" style={{ color: '#6c5ce7' }} />
                  <span>{hint}</span>
                </p>
              )}

              {/* ── Missões, agrupadas por categoria visual ────── */}
              <section
                data-testid="smart-home-missions"
                className="bg-white rounded-2xl border border-slate-100 overflow-hidden mb-6 mt-6"
              >
                <div className="px-5 md:px-6 py-4 border-b border-slate-100 flex items-center justify-between">
                  <h3 className="text-[13px] font-semibold uppercase tracking-wider text-slate-600">
                    Missões de hoje
                  </h3>
                  {total > 0 && (
                    <span
                      data-testid="smart-home-progress-label"
                      className="text-[12px] font-medium text-slate-500"
                    >
                      {done}/{total} · {pct}%
                    </span>
                  )}
                </div>

                {total > 0 && (
                  <div className="px-5 md:px-6 pt-4">
                    <div className="h-2 rounded-full bg-slate-100 overflow-hidden">
                      <div
                        data-testid="smart-home-progress-bar"
                        className="h-full transition-all duration-500 rounded-full"
                        style={{ width: `${pct}%`, background: '#6c5ce7' }}
                      />
                    </div>
                  </div>
                )}

                {missions.length === 0 ? (
                  <div className="px-5 md:px-6 py-8 text-center">
                    <p className="text-[14px] text-slate-500 mb-4">
                      Ainda não tem missões pra hoje.
                    </p>
                    <button
                      data-testid="smart-home-generate-btn"
                      onClick={generateMissions}
                      disabled={generating}
                      className="inline-flex items-center gap-2 text-white font-medium px-5 py-2.5 rounded-xl transition-colors disabled:opacity-70"
                      style={{ background: '#6c5ce7' }}
                    >
                      {generating
                        ? <><Loader2 className="w-4 h-4 animate-spin" /> Gerando…</>
                        : <><RefreshCw className="w-4 h-4" /> Gerar missões do dia</>}
                    </button>
                  </div>
                ) : (
                  <>
                    {buckets.est.length > 0 && (
                      <MissionGroup
                        label="Estudos"
                        Icon={BookOpen}
                        items={buckets.est}
                        busyId={busyId}
                        onToggle={toggle}
                        onGo={(m) => navigate(routeForMission(m))}
                      />
                    )}
                    {buckets.hab.length > 0 && (
                      <MissionGroup
                        label="Hábitos"
                        Icon={Heart}
                        items={buckets.hab}
                        busyId={busyId}
                        onToggle={toggle}
                        onGo={(m) => navigate(routeForMission(m))}
                      />
                    )}
                  </>
                )}
              </section>

              {/* ── Escape para o painel completo (Início) ─────── */}
              <div className="flex items-center justify-center">
                <button
                  data-testid="smart-home-open-dashboard"
                  onClick={() => navigate('/dashboard')}
                  className="inline-flex items-center gap-2 text-[13px] text-slate-500 hover:text-slate-800 transition-colors"
                >
                  <LineChart strokeWidth={1.75} className="w-4 h-4" />
                  <span>ver meu painel de evolução</span>
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </Shell>
  );
};

// ─── PrimaryCard: Resume / Check-in / Missão ─────────────────────
const PrimaryCard = ({ primary, onStart, onDismiss }) => {
  const isResume = primary.mode === 'resume';
  const { Icon } = primary;
  return (
    <section
      data-testid="smart-home-primary"
      data-mode={primary.mode}
      className="rounded-2xl border overflow-hidden"
      style={{
        background: isResume
          ? 'linear-gradient(135deg, #eef7ff 0%, #e7f0ff 45%, #dfe9ff 100%)'
          : 'linear-gradient(135deg, #f8f6ff 0%, #f3f0ff 45%, #ede9ff 100%)',
        borderColor: isResume ? '#c9dbff' : '#e4dff5',
      }}
    >
      <div className="p-6 md:p-8">
        <p
          className="text-[11px] font-semibold uppercase tracking-wider mb-2"
          style={{ color: isResume ? '#2f6bd6' : '#6c5ce7' }}
        >
          {primary.kicker}
        </p>
        <h2
          data-testid="smart-home-primary-title"
          className="text-[22px] md:text-[26px] font-semibold text-slate-900 tracking-tight leading-tight"
        >
          {primary.title}
        </h2>
        {primary.subtitle && (
          <p className="mt-1.5 text-[13.5px] text-slate-500">{primary.subtitle}</p>
        )}

        <div
          className="mt-6 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pt-5 border-t"
          style={{ borderColor: isResume ? '#c9dbff' : '#ddd6f0' }}
        >
          {primary.minutes && primary.minutes > 1 ? (
            <div>
              <p className="text-[12px] text-slate-500">Tempo estimado</p>
              <p className="text-[24px] font-semibold leading-none mt-1" style={{ color: isResume ? '#2f6bd6' : '#6c5ce7' }}>
                {primary.minutes} min
              </p>
            </div>
          ) : <div />}
          <div className="flex items-center gap-3">
            {onDismiss && (
              <button
                data-testid="smart-home-primary-dismiss"
                onClick={onDismiss}
                className="text-[13px] text-slate-500 hover:text-slate-800 transition-colors"
              >
                começar outra coisa
              </button>
            )}
            <button
              data-testid="smart-home-start-btn"
              onClick={onStart}
              className="inline-flex items-center gap-2 text-white font-semibold px-6 py-3 rounded-xl transition-all active:scale-[0.97]"
              style={{
                background: isResume ? '#2f6bd6' : '#6c5ce7',
                boxShadow: isResume
                  ? '0 10px 25px -12px rgba(47, 107, 214, 0.45)'
                  : '0 10px 25px -12px rgba(108, 92, 231, 0.45)',
              }}
            >
              <Icon className="w-4 h-4" />
              <span>{primary.buttonLabel}</span>
            </button>
          </div>
        </div>
      </div>
    </section>
  );
};

// ─── MissionGroup: header + list ───────────────────────────────────
const MissionGroup = ({ label, Icon, items, busyId, onToggle, onGo }) => (
  <div data-testid={`smart-home-group-${label.toLowerCase()}`} className="mt-3">
    <div className="px-5 md:px-6 pt-3 pb-1 flex items-center gap-2">
      <Icon strokeWidth={1.75} className="w-3.5 h-3.5 text-slate-400" />
      <h4 className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
        {label}
      </h4>
      <span className="text-[11px] text-slate-300">·</span>
      <span className="text-[11px] text-slate-400 tabular-nums">
        {items.filter((m) => m.completed).length}/{items.length}
      </span>
    </div>
    <ul className="divide-y divide-slate-100">
      {items.map((m) => (
        <MissionRow
          key={m.id}
          m={m}
          disabled={busyId === m.id}
          onToggle={() => onToggle(m)}
          onGo={() => onGo(m)}
        />
      ))}
    </ul>
  </div>
);

const MissionRow = ({ m, disabled, onToggle, onGo }) => (
  <li
    data-testid={`smart-home-mission-${m.id}`}
    className="px-5 md:px-6 py-3 flex items-center gap-3"
  >
    <button
      data-testid={`smart-home-mission-toggle-${m.id}`}
      onClick={onToggle}
      disabled={disabled}
      className="shrink-0 focus:outline-none focus:ring-2 focus:ring-brand/30 rounded-full"
      aria-label={m.completed ? 'Marcar como não concluída' : 'Marcar como concluída'}
    >
      {disabled ? (
        <Loader2 className="w-5 h-5 animate-spin text-slate-400" />
      ) : m.completed ? (
        <CheckCircle2 className="w-5 h-5" style={{ color: '#6c5ce7' }} />
      ) : (
        <Circle strokeWidth={1.75} className="w-5 h-5 text-slate-300 hover:text-slate-500 transition-colors" />
      )}
    </button>
    <div className="min-w-0 flex-1">
      <p
        className={`text-[14.5px] leading-snug ${
          m.completed ? 'line-through text-slate-400' : 'text-slate-800'
        }`}
      >
        {m.title}
      </p>
    </div>
    {m.minutes ? (
      <span className="shrink-0 text-[12px] text-slate-400 tabular-nums">
        {m.minutes} min
      </span>
    ) : null}
    {!m.completed && (
      <button
        data-testid={`smart-home-mission-go-${m.id}`}
        onClick={onGo}
        className="shrink-0 p-1.5 rounded-lg text-slate-400 hover:text-slate-800 hover:bg-slate-50 transition-colors"
        aria-label={`Ir para ${m.title}`}
        title="Continuar"
      >
        <ArrowRight strokeWidth={1.75} className="w-4 h-4" />
      </button>
    )}
  </li>
);

export default SmartHome;
