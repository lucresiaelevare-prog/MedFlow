import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Flame, Target, BookOpen, Clock, Sparkles, Heart, Award, Trophy, Medal, Star, Lock,
  Calendar, TrendingUp, User, ChevronRight, Route as RouteIcon, BarChart3, FileText,
  Wind, LifeBuoy, Bell, BellRing, Settings2, ShieldCheck, GraduationCap, LogOut,
  Pencil, Camera,
} from 'lucide-react';
import Shell from '@/components/Shell';
import api from '@/lib/api';
import { useAuth } from '@/context/AuthContext';

// ── Menus (mantém as rotas existentes que já funcionam) ─────────
const JOURNEY_LINKS = [
  { key: 'plan',    to: '/perfil-estudante', icon: RouteIcon, label: 'Meu plano de estudos', desc: 'Ajuste sua meta, tempo e rotina' },
  { key: 'stats',   to: '/dashboard',        icon: BarChart3, label: 'Estatísticas detalhadas', desc: 'Acompanhe seu desempenho' },
  { key: 'badges',  to: '/dashboard',        icon: Trophy,    label: 'Minhas conquistas', desc: 'Veja todas as suas badges' },
  { key: 'reports', to: '/history',          icon: FileText,  label: 'Relatórios e evolução', desc: 'Gráficos e análises completas' },
];

const WELLBEING_LINKS = [
  { key: 'mindfulness', to: '/mindfulness', icon: Wind,     label: 'Pausas guiadas',      desc: 'Respiração, foco e descanso' },
  { key: 'support',     to: '/support',     icon: LifeBuoy, label: 'Rede de apoio',       desc: 'CVV, CAPS e outros canais' },
  { key: 'notify',      to: '/settings',    icon: Bell,     label: 'Notificações',        desc: 'Gerencie seus alertas' },
  { key: 'reminders',   to: '/settings',    icon: BellRing, label: 'Lembretes inteligentes', desc: 'Personalize seus lembretes' },
];

const ACCOUNT_LINKS = [
  { key: 'data',     to: '/perfil-estudante', icon: User,        label: 'Meus dados',            desc: 'Dados pessoais e de contato' },
  { key: 'subjects', to: '/subjects',         icon: GraduationCap, label: 'Matérias e preferências', desc: 'Organize suas matérias' },
  { key: 'settings', to: '/settings',         icon: Settings2,   label: 'Ajustes do app',        desc: 'Modo, IA, aparência e mais' },
  { key: 'privacy',  to: '/settings',         icon: ShieldCheck, label: 'Privacidade e segurança', desc: 'Gerencie sua privacidade' },
];

// ── Utils ─────────────────────────────────────────────────────────
const num = (n, fallback = '—') => (typeof n === 'number' ? n.toLocaleString('pt-BR') : fallback);
const CHRONO_LABEL = { matutino: 'Manhã', vespertino: 'Tarde', noturno: 'Noite' };

const initialsOf = (name) => {
  const parts = (name || '').trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return '?';
  if (parts.length === 1) return parts[0].slice(0, 1).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
};

// ── Sparkline SVG (chart de 30 dias) ────────────────────────────
const EvolutionChart = ({ points = [] }) => {
  const w = 620;
  const h = 200;
  const pad = { l: 32, r: 12, t: 14, b: 26 };
  const iw = w - pad.l - pad.r;
  const ih = h - pad.t - pad.b;
  const values = points.map((p) => p.value ?? 0);
  const yMax = 100;
  const yMin = 0;
  const n = Math.max(1, points.length);
  const xAt = (i) => pad.l + (n === 1 ? iw / 2 : (i * iw) / (n - 1));
  const yAt = (v) => pad.t + ih - ((v - yMin) / (yMax - yMin)) * ih;

  const linePath = points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${xAt(i)} ${yAt(p.value ?? 0)}`).join(' ');
  const areaPath = points.length
    ? `${linePath} L ${xAt(points.length - 1)} ${pad.t + ih} L ${xAt(0)} ${pad.t + ih} Z`
    : '';

  const ticks = [0, 25, 50, 75, 100];
  const dateLabelIdx = points.length ? [0, Math.floor(points.length * 0.25), Math.floor(points.length * 0.5), Math.floor(points.length * 0.75), points.length - 1] : [];

  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-full h-auto" data-testid="profile-evolution-chart">
      <defs>
        <linearGradient id="areaFill" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor="#6C5CE7" stopOpacity="0.28" />
          <stop offset="100%" stopColor="#6C5CE7" stopOpacity="0.02" />
        </linearGradient>
      </defs>
      {ticks.map((t) => (
        <g key={t}>
          <line x1={pad.l} x2={w - pad.r} y1={yAt(t)} y2={yAt(t)} stroke="#EEF2F7" strokeWidth={1} />
          <text x={pad.l - 8} y={yAt(t) + 3} fontSize={10} textAnchor="end" fill="#94A3B8">{t}</text>
        </g>
      ))}
      {points.length > 1 && (
        <>
          <path d={areaPath} fill="url(#areaFill)" />
          <path d={linePath} fill="none" stroke="#6C5CE7" strokeWidth={2.2} strokeLinejoin="round" strokeLinecap="round" />
          {points.map((p, i) => (
            <circle key={i} cx={xAt(i)} cy={yAt(p.value ?? 0)} r={2.5} fill="#6C5CE7" />
          ))}
        </>
      )}
      {dateLabelIdx.map((i) => (
        <text key={i} x={xAt(i)} y={h - 6} fontSize={10} textAnchor="middle" fill="#94A3B8">
          {points[i]?.label ?? ''}
        </text>
      ))}
    </svg>
  );
};

// ── Badge hexagonal (conquistas) ────────────────────────────────
const HexBadge = ({ icon: Icon, label, sub, tone = 'brand', locked = false }) => {
  const toneMap = {
    brand:   { bg: '#EDE9FF', fg: '#6C5CE7', border: '#DDD3FF' },
    success: { bg: '#D1FAE5', fg: '#059669', border: '#BBF7D0' },
    attention:{ bg: '#FEF3C7', fg: '#B45309', border: '#FDE68A' },
    care:    { bg: '#FDE7DE', fg: '#DC6B4C', border: '#FBCBB6' },
    gray:    { bg: '#F1F5F9', fg: '#94A3B8', border: '#E2E8F0' },
  };
  const t = locked ? toneMap.gray : (toneMap[tone] || toneMap.brand);
  return (
    <div className="flex flex-col items-center text-center gap-1.5 min-w-0">
      <div
        className="relative w-16 h-[72px] flex items-center justify-center"
        style={{
          background: t.bg,
          clipPath: 'polygon(50% 0%, 100% 25%, 100% 75%, 50% 100%, 0% 75%, 0% 25%)',
        }}
      >
        {locked ? (
          <Lock className="w-6 h-6" style={{ color: t.fg }} strokeWidth={2} />
        ) : (
          <Icon className="w-6 h-6" style={{ color: t.fg }} strokeWidth={2} />
        )}
      </div>
      <p className="text-[12.5px] font-semibold text-slate-900 truncate max-w-[96px]">
        <span>{label}</span>
      </p>
      {sub && (
        <p className="text-[10.5px] text-slate-500 max-w-[104px] leading-tight">
          <span>{sub}</span>
        </p>
      )}
    </div>
  );
};

// ── Card genérico de estatística ─────────────────────────────────
const StatCard = ({ icon: Icon, tone, label, value, unit, sub, testId }) => {
  const map = {
    care:      { bg: '#FDE7DE', fg: '#DC6B4C' },
    brand:     { bg: '#EDE9FF', fg: '#6C5CE7' },
    success:   { bg: '#D1FAE5', fg: '#059669' },
    attention: { bg: '#FEF3C7', fg: '#B45309' },
  };
  const t = map[tone] || map.brand;
  return (
    <div className="flex-1 min-w-0" data-testid={testId}>
      <div className="flex items-center gap-2 mb-1.5">
        <span className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0" style={{ background: t.bg, color: t.fg }}>
          <Icon className="w-4 h-4" strokeWidth={2} />
        </span>
        <p className="text-[13px] text-slate-500 font-medium truncate"><span>{label}</span></p>
      </div>
      <p className="tabular-nums leading-none">
        <span className="text-[26px] md:text-[28px] font-bold text-slate-900">{value}</span>
        {unit && <span className="ml-1 text-[13px] text-slate-400 font-medium">{unit}</span>}
      </p>
      {sub && <p className="mt-1.5 text-[11.5px] text-slate-500 leading-snug"><span>{sub}</span></p>}
    </div>
  );
};

// ── Link item das seções finais ─────────────────────────────────
const LinkRow = ({ icon: Icon, label, desc, onClick, testId }) => (
  <button
    type="button"
    onClick={onClick}
    data-testid={testId}
    className="w-full flex items-center gap-3 py-3 px-1 text-left group focus:outline-none"
  >
    <span
      className="w-9 h-9 rounded-lg flex items-center justify-center shrink-0"
      style={{ background: 'var(--mf-brand-soft)', color: 'var(--mf-brand)' }}
    >
      <Icon className="w-4 h-4" strokeWidth={1.9} />
    </span>
    <div className="flex-1 min-w-0">
      <p className="text-[13.5px] font-semibold text-slate-900 leading-tight truncate">
        <span>{label}</span>
      </p>
      <p className="mt-0.5 text-[12px] text-slate-500 truncate"><span>{desc}</span></p>
    </div>
    <ChevronRight className="w-4 h-4 text-slate-300 shrink-0 group-hover:text-slate-500 transition-colors" strokeWidth={2} />
  </button>
);

// ═══════════════════════════════════════════════════════════════
const Profile = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const [streak, setStreak] = useState({ streak: 0, best: 0 });
  const [iea, setIea] = useState(null);
  const [profile, setProfile] = useState(null);
  const [home, setHome] = useState(null);
  const [pomodoroToday, setPomodoroToday] = useState(null);
  const [history, setHistory] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const [s, i, p, h, pt, hist] = await Promise.allSettled([
          api.get('/streak'),
          api.get('/iea'),
          api.get('/profile'),
          api.get('/home/today'),
          api.get('/pomodoro/today'),
          api.get('/history?days=30'),
        ]);
        if (s.status === 'fulfilled') setStreak(s.value.data);
        if (i.status === 'fulfilled') setIea(i.value.data);
        if (p.status === 'fulfilled') setProfile(p.value.data?.profile || null);
        if (h.status === 'fulfilled') setHome(h.value.data);
        if (pt.status === 'fulfilled') setPomodoroToday(pt.value.data);
        if (hist.status === 'fulfilled') setHistory(hist.value.data);
      } finally { setLoading(false); }
    })();
  }, []);

  const handleLogout = async () => { await logout(); navigate('/', { replace: true }); };

  const firstName = (user?.name || '').split(' ')[0] || 'Você';
  const stats = home?.stats || {};

  // ─── Meta diária (Pomodoro) ────
  const dailyGoalMin = profile?.target_focus_minutes_per_day || 90;
  const todayMin = Math.round((pomodoroToday?.focused_minutes ?? pomodoroToday?.minutes ?? 0));
  const dailyPct = Math.min(100, Math.round((todayMin / Math.max(1, dailyGoalMin)) * 100));

  // ─── Sequência atual + melhor ────
  const streakDays = streak?.streak ?? 0;
  const bestStreak = streak?.best ?? streak?.longest ?? streakDays;

  // ─── Índice hoje (IEA) ────
  const ieaValue = iea?.iea != null ? Math.round(iea.iea) : null;

  // ─── Questões resolvidas / Horas estudadas ────
  const questoesTotal = stats?.questions_answered ?? stats?.content_events_total ?? null;
  const questoesHoje = stats?.questions_answered_today ?? null;
  const totalMin = stats?.focus_minutes_total ?? stats?.pomodoros_completed_minutes ?? null;
  const totalHoras = totalMin != null ? Math.floor(totalMin / 60) : null;
  const totalMinsRest = totalMin != null ? (totalMin % 60) : null;
  const hojeHorasMin = todayMin || null;

  // ─── Chart 30 dias ────
  const chartPoints = useMemo(() => {
    const checks = history?.checkins || [];
    if (!checks.length) return [];
    // Agrupa por dia (média do IEA/score do checkin quando disponível)
    const byDay = new Map();
    checks.forEach((c) => {
      const day = (c.created_at || '').slice(0, 10);
      if (!day) return;
      const score = typeof c.iea === 'number' ? c.iea
                 : typeof c.energy === 'number' ? c.energy * 20
                 : null;
      if (score == null) return;
      const arr = byDay.get(day) || [];
      arr.push(score);
      byDay.set(day, arr);
    });
    const days = Array.from(byDay.entries()).sort(([a], [b]) => a.localeCompare(b));
    return days.map(([day, arr]) => {
      const val = arr.reduce((s, x) => s + x, 0) / arr.length;
      const [_y, m, d] = day.split('-');
      return { label: `${d}/${m}`, value: Math.round(val) };
    });
  }, [history]);

  const mediaPeriodo = chartPoints.length
    ? Math.round(chartPoints.reduce((s, p) => s + (p.value || 0), 0) / chartPoints.length)
    : null;

  // ─── Conquistas (derivadas de dados reais) ────
  const badges = [
    { key: '7d',    tone: 'brand',     icon: Flame,    label: 'Consistência', sub: '7 dias seguidos', locked: streakDays < 7 },
    { key: '100q',  tone: 'success',   icon: Award,    label: 'Centenário',   sub: '100 questões',    locked: (questoesTotal ?? 0) < 100 },
    { key: '1000q', tone: 'brand',     icon: Medal,    label: 'Mil questões', sub: '1.000 resolvidas', locked: (questoesTotal ?? 0) < 1000 },
    { key: '10h',   tone: 'attention', icon: Clock,    label: 'Dedicação',    sub: '10 horas de estudo', locked: (totalMin ?? 0) < 600 },
    { key: '30d',   tone: 'gray',      icon: Star,     label: 'Próxima meta', sub: 'Estude por 30 dias', locked: true },
  ];

  if (loading) {
    return (
      <Shell>
        <div className="max-w-6xl mx-auto pt-10 flex justify-center">
          <div className="w-8 h-8 rounded-full border-2 border-slate-200 border-t-brand animate-spin" style={{ borderTopColor: 'var(--mf-brand)' }} />
        </div>
      </Shell>
    );
  }

  return (
    <Shell>
      <div
        data-testid="profile-root"
        className="max-w-6xl mx-auto px-5 md:px-8 pt-6 md:pt-8 pb-16 animate-fade-in"
      >
        {/* ─── Header ─── */}
        <header className="mb-6 md:mb-7" data-testid="profile-header">
          <div className="flex items-center gap-2">
            <h1
              className="font-bold text-slate-900 tracking-tight leading-none"
              style={{ fontSize: 'clamp(30px, 3.8vw, 40px)', letterSpacing: '-0.025em' }}
            >
              <span>Perfil</span>
            </h1>
            <Sparkles className="w-6 h-6" style={{ color: 'var(--mf-brand)' }} strokeWidth={1.8} />
          </div>
          <p className="mt-2 text-[14.5px] text-slate-600 max-w-2xl leading-relaxed">
            <span>Este é o seu espaço. Acompanhe sua jornada e evolua todos os dias.</span>
          </p>
        </header>

        {/* ─── Hero: identidade + meta diária ─── */}
        <section className="mf-card p-5 md:p-6 mb-4" data-testid="profile-identity-card">
          <div className="flex flex-col md:flex-row md:items-center gap-6">
            {/* Avatar + camera */}
            <div className="flex items-center gap-5 flex-1 min-w-0">
              <div className="relative shrink-0">
                {user?.picture ? (
                  <img
                    src={user.picture}
                    alt={user.name || firstName}
                    className="w-20 h-20 md:w-24 md:h-24 rounded-full object-cover ring-2 ring-white shadow-md"
                  />
                ) : (
                  <div
                    className="w-20 h-20 md:w-24 md:h-24 rounded-full flex items-center justify-center text-[26px] font-bold text-white shadow-md"
                    style={{ background: 'linear-gradient(135deg, #F87171 0%, #EC4899 100%)' }}
                  >
                    {initialsOf(user?.name)}
                  </div>
                )}
                <button
                  type="button"
                  onClick={() => navigate('/perfil-estudante')}
                  data-testid="profile-avatar-camera"
                  className="absolute -bottom-1 -right-1 w-8 h-8 rounded-full bg-white flex items-center justify-center shadow-md ring-1 ring-slate-200 hover:bg-slate-50 transition-colors"
                  title="Editar foto"
                >
                  <Camera className="w-4 h-4 text-slate-600" strokeWidth={1.8} />
                </button>
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <h2 className="text-[24px] md:text-[26px] font-bold text-slate-900 tracking-tight truncate">
                    <span>{firstName}</span>
                  </h2>
                  <button
                    type="button"
                    onClick={() => navigate('/perfil-estudante')}
                    data-testid="profile-edit-name"
                    className="p-1 rounded-md text-slate-400 hover:text-slate-700 hover:bg-slate-50 transition-colors"
                    title="Editar dados"
                  >
                    <Pencil className="w-4 h-4" strokeWidth={1.8} />
                  </button>
                </div>

                {(profile?.university || profile?.course) && (
                  <p className="mt-1 text-[13.5px] text-slate-600 flex items-center gap-1.5 flex-wrap">
                    <GraduationCap className="w-3.5 h-3.5 shrink-0" style={{ color: 'var(--mf-brand)' }} />
                    <span className="truncate">{profile?.university || '—'}</span>
                    {profile?.course && <span className="text-slate-400">·</span>}
                    {profile?.course && <span className="truncate">{profile.course}</span>}
                  </p>
                )}

                <div className="mt-3 flex flex-wrap gap-2">
                  {profile?.chronotype && (
                    <span
                      className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[12px] font-medium"
                      style={{ background: 'var(--mf-attention-soft)', color: '#78350F' }}
                    >
                      <Sparkles className="w-3 h-3" strokeWidth={2.2} />
                      <span>Cronotipo: {CHRONO_LABEL[profile.chronotype] || profile.chronotype}</span>
                    </span>
                  )}
                  <span
                    className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[12px] font-medium"
                    style={{ background: 'var(--mf-brand-soft)', color: 'var(--mf-brand)' }}
                  >
                    <Trophy className="w-3 h-3" strokeWidth={2.2} />
                    <span>Plano: Beta</span>
                  </span>
                </div>

                <div className="mt-3 flex items-start gap-1.5">
                  <Heart className="w-3.5 h-3.5 shrink-0 mt-1" style={{ color: '#EC4899', fill: '#EC4899' }} strokeWidth={1.5} />
                  <p className="text-[13px] text-slate-600 italic leading-snug">
                    <span>Você está construindo sua aprovação um dia por vez.</span>
                  </p>
                </div>
              </div>
            </div>

            {/* Meta diária */}
            <div
              className="md:min-w-[260px] rounded-2xl p-4 md:p-5"
              style={{ background: 'var(--mf-canvas)', border: '1px solid var(--mf-hair)' }}
              data-testid="profile-daily-goal"
            >
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-1.5">
                  <Clock className="w-4 h-4" style={{ color: 'var(--mf-brand)' }} strokeWidth={2} />
                  <p className="text-[12px] font-semibold uppercase tracking-wider text-slate-500">
                    <span>Meta diária</span>
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => navigate('/perfil-estudante')}
                  data-testid="profile-daily-goal-edit"
                  className="text-[12px] font-semibold hover:underline"
                  style={{ color: 'var(--mf-brand)' }}
                >
                  Editar
                </button>
              </div>
              <p className="tabular-nums leading-none">
                <span className="text-[32px] font-bold text-slate-900">{dailyGoalMin}</span>
                <span className="ml-1 text-[14px] text-slate-400 font-medium">min</span>
              </p>
              <div className="mt-3 h-2 rounded-full bg-slate-200 overflow-hidden">
                <div
                  className="h-full rounded-full transition-all duration-500"
                  style={{ width: `${dailyPct}%`, background: 'linear-gradient(90deg, #6C5CE7 0%, #A78BFA 100%)' }}
                />
              </div>
              <p className="mt-2 text-[12px] text-slate-500">
                <span>{todayMin} min concluídos hoje</span>
              </p>
            </div>
          </div>
        </section>

        {/* ─── Stats row (4 cards horizontal) ─── */}
        <section
          className="mf-card p-5 md:p-6 mb-4 grid grid-cols-2 md:grid-cols-4 gap-5 md:gap-4"
          data-testid="profile-stats-row"
        >
          <StatCard
            icon={Flame}
            tone="care"
            label="Sequência atual"
            value={num(streakDays)}
            unit="dias"
            sub={`Maior sequência: ${bestStreak || 0} dias`}
            testId="stat-streak"
          />
          <StatCard
            icon={Target}
            tone="brand"
            label="Índice hoje"
            value={ieaValue != null ? ieaValue : '—'}
            unit={ieaValue != null ? '/100' : ''}
            sub={ieaValue == null ? 'Faça o check-in de hoje' :
                 ieaValue >= 60 ? 'Bom progresso 💪' :
                 ieaValue >= 40 ? 'Continue firme' : 'Recupere seu ritmo'}
            testId="stat-iea"
          />
          <StatCard
            icon={BookOpen}
            tone="success"
            label="Questões resolvidas"
            value={num(questoesTotal, '—')}
            sub={questoesHoje != null ? `+${questoesHoje} hoje` : 'Comece agora'}
            testId="stat-questoes"
          />
          <StatCard
            icon={Clock}
            tone="attention"
            label="Horas estudadas"
            value={totalHoras != null ? `${totalHoras}h ${String(totalMinsRest || 0).padStart(2, '0')}m` : '—'}
            sub={hojeHorasMin != null ? `+${hojeHorasMin}m hoje` : 'Sem sessões ainda'}
            testId="stat-horas"
          />
        </section>

        {/* ─── Grid principal: chart+minis (esquerda) + plano+desempenho (direita) ─── */}
        <section className="grid grid-cols-1 lg:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)] gap-4 mb-4">
          {/* ── Esquerda: Evolução ── */}
          <div className="space-y-4 min-w-0">
            <div className="mf-card p-5 md:p-6" data-testid="profile-evolution-card">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-[16px] font-bold text-slate-900 tracking-tight">
                  <span>Evolução nos últimos 30 dias</span>
                </h3>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-[minmax(0,2.4fr)_minmax(0,1fr)] gap-4 items-center">
                <div className="min-w-0">
                  {chartPoints.length > 1 ? (
                    <EvolutionChart points={chartPoints} />
                  ) : (
                    <div className="h-40 flex flex-col items-center justify-center text-center px-3">
                      <BarChart3 className="w-8 h-8 text-slate-300 mb-2" strokeWidth={1.5} />
                      <p className="text-[13px] font-semibold text-slate-700">
                        <span>Aguardando dados suficientes</span>
                      </p>
                      <p className="mt-1 text-[12px] text-slate-500 max-w-xs">
                        <span>Faça check-ins diários para construir sua linha de evolução.</span>
                      </p>
                    </div>
                  )}
                </div>
                <div
                  className="rounded-2xl p-4"
                  style={{ background: 'var(--mf-canvas)', border: '1px solid var(--mf-hair)' }}
                >
                  <p className="text-[11.5px] font-semibold uppercase tracking-wider text-slate-500">
                    <span>Média do período</span>
                  </p>
                  <p className="mt-1.5 tabular-nums leading-none">
                    <span className="text-[28px] font-bold text-slate-900">{mediaPeriodo != null ? mediaPeriodo : '—'}</span>
                    {mediaPeriodo != null && <span className="ml-1 text-[13px] text-slate-400 font-medium">/100</span>}
                  </p>
                  {mediaPeriodo != null && (
                    <p className="mt-3 text-[11.5px]" style={{ color: 'var(--mf-success)' }}>
                      <span className="font-semibold">Base para próxima janela</span>
                    </p>
                  )}
                </div>
              </div>
            </div>

            {/* Mini stats horizontal */}
            <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
              {[
                { label: 'Questões', value: num(questoesTotal, '—'), testId: 'mini-questoes' },
                { label: 'Revisões', value: num(stats?.reviews_total, '—'), testId: 'mini-revisoes' },
                { label: 'Flashcards', value: num(stats?.flashcards_total, '—'), testId: 'mini-flashcards' },
                { label: 'Simulados', value: num(stats?.simulados_total, '—'), testId: 'mini-simulados' },
                { label: 'Precisão média', value: stats?.accuracy_pct != null ? `${Math.round(stats.accuracy_pct)}%` : '—', testId: 'mini-precisao' },
              ].map((m) => (
                <div key={m.label} className="mf-card p-4 text-center" data-testid={m.testId}>
                  <p className="text-[12px] text-slate-500 font-medium mb-1"><span>{m.label}</span></p>
                  <p className="tabular-nums text-[20px] md:text-[22px] font-bold text-slate-900 leading-none">
                    <span>{m.value}</span>
                  </p>
                </div>
              ))}
            </div>

            {/* Conquistas */}
            <div className="mf-card p-5 md:p-6" data-testid="profile-conquistas-card">
              <div className="flex items-center justify-between mb-5">
                <h3 className="text-[16px] font-bold text-slate-900 tracking-tight">
                  <span>Conquistas</span>
                </h3>
                <button
                  type="button"
                  onClick={() => navigate('/dashboard')}
                  data-testid="profile-conquistas-all"
                  className="text-[12.5px] font-semibold hover:underline"
                  style={{ color: 'var(--mf-brand)' }}
                >
                  Ver todas
                </button>
              </div>
              <div className="flex items-start justify-between gap-3 flex-wrap">
                {badges.map((b) => (
                  <HexBadge
                    key={b.key}
                    icon={b.icon}
                    label={b.label}
                    sub={b.sub}
                    tone={b.tone}
                    locked={b.locked}
                  />
                ))}
              </div>
            </div>
          </div>

          {/* ── Direita: Meu plano + Meu desempenho ── */}
          <div className="space-y-4 min-w-0">
            <div className="mf-card p-5 md:p-6" data-testid="profile-plan-card">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <Calendar className="w-4 h-4" style={{ color: 'var(--mf-brand)' }} strokeWidth={2} />
                  <h3 className="text-[15.5px] font-bold text-slate-900 tracking-tight">
                    <span>Meu plano</span>
                  </h3>
                </div>
                <button
                  type="button"
                  onClick={() => navigate('/perfil-estudante')}
                  data-testid="profile-plan-edit"
                  className="text-[12.5px] font-semibold hover:underline"
                  style={{ color: 'var(--mf-brand)' }}
                >
                  Editar
                </button>
              </div>
              <p className="text-[13.5px] text-slate-700 leading-relaxed">
                {profile?.university || '—'}
                {profile?.course && <span className="text-slate-400"> · </span>}
                {profile?.course && <span>{profile.course}</span>}
              </p>
              <dl className="mt-4 space-y-2.5 text-[13px]">
                {profile?.exam_name && (
                  <div className="flex items-center justify-between gap-2">
                    <dt className="text-slate-500 flex items-center gap-1.5">
                      <Sparkles className="w-3.5 h-3.5" strokeWidth={1.9} />
                      <span>Prova:</span>
                    </dt>
                    <dd className="font-semibold text-slate-900 truncate max-w-[60%] text-right">{profile.exam_name}</dd>
                  </div>
                )}
                {profile?.exam_date && (
                  <div className="flex items-center justify-between gap-2">
                    <dt className="text-slate-500 flex items-center gap-1.5">
                      <Calendar className="w-3.5 h-3.5" strokeWidth={1.9} />
                      <span>Data da prova:</span>
                    </dt>
                    <dd className="font-semibold text-slate-900">{profile.exam_date}</dd>
                  </div>
                )}
                {profile?.study_days_per_week && (
                  <div className="flex items-center justify-between gap-2">
                    <dt className="text-slate-500 flex items-center gap-1.5">
                      <RouteIcon className="w-3.5 h-3.5" strokeWidth={1.9} />
                      <span>Dias de estudo:</span>
                    </dt>
                    <dd className="font-semibold text-slate-900">{profile.study_days_per_week} dias/semana</dd>
                  </div>
                )}
                <div className="flex items-center justify-between gap-2">
                  <dt className="text-slate-500 flex items-center gap-1.5">
                    <Clock className="w-3.5 h-3.5" strokeWidth={1.9} />
                    <span>Meta diária:</span>
                  </dt>
                  <dd className="font-semibold text-slate-900">{dailyGoalMin} minutos</dd>
                </div>
              </dl>
              <button
                type="button"
                onClick={() => navigate('/dashboard')}
                data-testid="profile-plan-view"
                className="mt-5 w-full inline-flex items-center justify-center gap-2 py-2.5 rounded-xl text-[13.5px] font-semibold text-white transition-all hover:-translate-y-0.5"
                style={{
                  background: 'linear-gradient(135deg, #6C5CE7 0%, #A78BFA 100%)',
                  boxShadow: '0 6px 20px -6px rgba(108,92,231,0.55)',
                }}
              >
                <span>Ver meu plano de estudos</span>
              </button>
            </div>

            <div className="mf-card p-5 md:p-6" data-testid="profile-performance-card">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <TrendingUp className="w-4 h-4" style={{ color: 'var(--mf-brand)' }} strokeWidth={2} />
                  <h3 className="text-[15.5px] font-bold text-slate-900 tracking-tight">
                    <span>Meu desempenho</span>
                  </h3>
                </div>
                <button
                  type="button"
                  onClick={() => navigate('/dashboard')}
                  data-testid="profile-performance-details"
                  className="text-[12.5px] font-semibold hover:underline"
                  style={{ color: 'var(--mf-brand)' }}
                >
                  Ver detalhes
                </button>
              </div>
              <ul className="space-y-3 text-[13px]">
                <li className="flex items-center justify-between gap-2">
                  <span className="text-slate-500 flex items-center gap-1.5">
                    <Trophy className="w-3.5 h-3.5" strokeWidth={1.9} />
                    <span>Ranking geral</span>
                  </span>
                  <span className="font-bold" style={{ color: 'var(--mf-brand)' }}>
                    {home?.rank?.percentile ? `Top ${home.rank.percentile}%` : '—'}
                  </span>
                </li>
                <li className="flex items-center justify-between gap-2">
                  <span className="text-slate-500 flex items-center gap-1.5">
                    <TrendingUp className="w-3.5 h-3.5" strokeWidth={1.9} />
                    <span>Desempenho semanal</span>
                  </span>
                  <span className="font-bold" style={{ color: 'var(--mf-success)' }}>
                    {home?.week_delta_pct != null ? `▲ ${home.week_delta_pct}%` : '—'}
                  </span>
                </li>
                <li className="flex items-center justify-between gap-2">
                  <span className="text-slate-500 flex items-center gap-1.5">
                    <Star className="w-3.5 h-3.5" strokeWidth={1.9} />
                    <span>Pontos acumulados</span>
                  </span>
                  <span className="font-bold text-slate-900">{num(home?.points_total, '—')}</span>
                </li>
                <li className="flex items-center justify-between gap-2">
                  <span className="text-slate-500 flex items-center gap-1.5">
                    <Sparkles className="w-3.5 h-3.5" strokeWidth={1.9} />
                    <span>Matéria forte</span>
                  </span>
                  <span className="font-semibold text-slate-900 truncate max-w-[55%] text-right capitalize">
                    {home?.strong_subject || '—'}
                  </span>
                </li>
                <li className="flex items-center justify-between gap-2">
                  <span className="text-slate-500 flex items-center gap-1.5">
                    <Target className="w-3.5 h-3.5" strokeWidth={1.9} />
                    <span>Matéria a melhorar</span>
                  </span>
                  <span className="font-semibold truncate max-w-[55%] text-right capitalize" style={{ color: 'var(--mf-care)' }}>
                    {home?.weak_subject || '—'}
                  </span>
                </li>
              </ul>
            </div>
          </div>
        </section>

        {/* ─── 3 colunas de menus (Minha jornada / Bem-estar / Minha conta) ─── */}
        <section className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4" data-testid="profile-menus">
          <div className="mf-card p-5">
            <div className="flex items-center gap-2 mb-3">
              <RouteIcon className="w-4 h-4" style={{ color: 'var(--mf-brand)' }} strokeWidth={2} />
              <h3 className="text-[15.5px] font-bold text-slate-900 tracking-tight">
                <span>Minha jornada</span>
              </h3>
            </div>
            <div className="divide-y" style={{ borderColor: 'var(--mf-hair)' }}>
              {JOURNEY_LINKS.map((l) => (
                <LinkRow
                  key={l.key}
                  icon={l.icon}
                  label={l.label}
                  desc={l.desc}
                  onClick={() => navigate(l.to)}
                  testId={`link-journey-${l.key}`}
                />
              ))}
            </div>
          </div>

          <div className="mf-card p-5">
            <div className="flex items-center gap-2 mb-3">
              <Heart className="w-4 h-4" style={{ color: '#EC4899' }} strokeWidth={2} />
              <h3 className="text-[15.5px] font-bold text-slate-900 tracking-tight">
                <span>Bem-estar</span>
              </h3>
            </div>
            <div className="divide-y" style={{ borderColor: 'var(--mf-hair)' }}>
              {WELLBEING_LINKS.map((l) => (
                <LinkRow
                  key={l.key}
                  icon={l.icon}
                  label={l.label}
                  desc={l.desc}
                  onClick={() => navigate(l.to)}
                  testId={`link-wellbeing-${l.key}`}
                />
              ))}
            </div>
          </div>

          <div className="mf-card p-5">
            <div className="flex items-center gap-2 mb-3">
              <User className="w-4 h-4" style={{ color: 'var(--mf-brand)' }} strokeWidth={2} />
              <h3 className="text-[15.5px] font-bold text-slate-900 tracking-tight">
                <span>Minha conta</span>
              </h3>
            </div>
            <div className="divide-y" style={{ borderColor: 'var(--mf-hair)' }}>
              {ACCOUNT_LINKS.map((l) => (
                <LinkRow
                  key={l.key}
                  icon={l.icon}
                  label={l.label}
                  desc={l.desc}
                  onClick={() => navigate(l.to)}
                  testId={`link-account-${l.key}`}
                />
              ))}
            </div>
          </div>
        </section>

        {/* ─── Sair da conta ─── */}
        <button
          type="button"
          data-testid="profile-logout"
          onClick={handleLogout}
          className="mf-card w-full p-4 md:p-5 flex items-center gap-3 text-left transition-colors hover:bg-slate-50"
        >
          <span
            className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0"
            style={{ background: 'var(--mf-care-soft)', color: 'var(--mf-care)' }}
          >
            <LogOut className="w-4 h-4" strokeWidth={2} />
          </span>
          <div className="flex-1 min-w-0">
            <p className="text-[14px] font-semibold text-slate-900"><span>Sair da conta</span></p>
            <p className="mt-0.5 text-[12px] text-slate-500"><span>Até logo! 👋</span></p>
          </div>
          <ChevronRight className="w-4 h-4 text-slate-400" strokeWidth={2} />
        </button>

        <p className="mt-6 text-center text-[11px] text-slate-400 tracking-wider uppercase font-medium">
          <span>Seus dados ficam seguros e anônimos · LGPD</span>
        </p>
      </div>
    </Shell>
  );
};

export default Profile;
