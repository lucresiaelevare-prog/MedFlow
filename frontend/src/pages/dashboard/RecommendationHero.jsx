import { useMemo } from 'react';
import {
  ArrowRight, Clock, Sparkles,
  Brain, HeartPulse, Stethoscope, Microscope, Dna,
  BookOpenText, Target,
} from 'lucide-react';
import WhyThisCard from './WhyThisCard';

/**
 * RecommendationHero — Hero card "RECOMENDAÇÃO DO DIA" (versão compacta).
 *
 * Objetivo: fazer o aluno entender EM 3 SEGUNDOS qual é a missão do dia.
 * Sem redundância (removida a duplicação de descrição/métricas do sub-card).
 * Sem "Confiança da IA" (ruído em relação à ação).
 *
 * Ilustração: ícone lucide-react temático dentro de uma moldura circular
 * com halo em gradiente. O ícone MUDA A CADA DIA (rotaciona por day-of-year),
 * mantendo consistência com o design system (mesmos ícones do MedFlow).
 *
 * Dados:
 *  - REAIS: title, subtitle, duration_min, priority, action_route, action_label
 *  - MOCK:  nenhum
 */

// Temas diários — ícone + subtitle micro + cor de acento (adequadas a fundo claro)
const DAILY_THEMES = [
  { key: 'brain',       Icon: Brain,        accent: '#7c3aed', label: 'Neuroplasticidade' },
  { key: 'heart',       Icon: HeartPulse,   accent: '#e11d48', label: 'Cardiologia'      },
  { key: 'stetho',      Icon: Stethoscope,  accent: '#2563eb', label: 'Semiologia'       },
  { key: 'micro',       Icon: Microscope,   accent: '#059669', label: 'Investigação'     },
  { key: 'dna',         Icon: Dna,          accent: '#c026d3', label: 'Fisiopatologia'   },
  { key: 'book',        Icon: BookOpenText, accent: '#d97706', label: 'Estudo dirigido'  },
  { key: 'target',      Icon: Target,       accent: '#0891b2', label: 'Foco de prova' },
];

const dayOfYear = (d = new Date()) => {
  const start = Date.UTC(d.getUTCFullYear(), 0, 0);
  const now = Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate());
  return Math.floor((now - start) / 86_400_000);
};

const priorityBadge = (priority) => {
  if (priority === 1) return { label: 'PRIORIDADE ALTA',  bg: '#FEE4E2', color: '#B42318' };
  if (priority === 2) return { label: 'PRIORIDADE MÉDIA', bg: '#FEF0C7', color: '#B54708' };
  if (priority === 3) return { label: 'PRIORIDADE BAIXA', bg: '#D1FADF', color: '#027A48' };
  return null; // sem RECOMENDADO — se não vier prioridade real, não mostra badge
};

const DailyIllustration = ({ theme }) => {
  const { Icon, accent, label } = theme;
  return (
    <div className="relative w-full h-full flex items-center justify-center" data-testid="dashboard-recommendation-illustration" data-theme={theme.key}>
      {/* halo em anel — 3 camadas concêntricas para dar profundidade */}
      <div
        aria-hidden
        className="absolute rounded-full"
        style={{
          width: '86%',
          height: '86%',
          background: `radial-gradient(circle, ${accent}55 0%, ${accent}18 45%, transparent 75%)`,
          filter: 'blur(2px)',
        }}
      />
      <div
        aria-hidden
        className="absolute rounded-full border"
        style={{
          width: '72%',
          height: '72%',
          borderColor: `${accent}44`,
        }}
      />
      <div
        aria-hidden
        className="absolute rounded-full border"
        style={{
          width: '58%',
          height: '58%',
          borderColor: `${accent}22`,
        }}
      />
      {/* pontinhos orbitais */}
      <svg
        aria-hidden
        viewBox="0 0 200 200"
        className="absolute inset-0 w-full h-full"
      >
        <g fill={accent}>
          <circle cx="100" cy="28" r="2.5">
            <animate attributeName="opacity" values="0.3;1;0.3" dur="2.6s" repeatCount="indefinite" />
          </circle>
          <circle cx="172" cy="100" r="2">
            <animate attributeName="opacity" values="0.5;1;0.5" dur="2.2s" repeatCount="indefinite" />
          </circle>
          <circle cx="100" cy="172" r="2.2">
            <animate attributeName="opacity" values="0.4;0.9;0.4" dur="3s" repeatCount="indefinite" />
          </circle>
          <circle cx="28" cy="100" r="1.8">
            <animate attributeName="opacity" values="0.3;0.8;0.3" dur="2.4s" repeatCount="indefinite" />
          </circle>
          <circle cx="52" cy="48" r="1.5" opacity="0.6" />
          <circle cx="148" cy="52" r="1.5" opacity="0.5" />
          <circle cx="152" cy="150" r="1.6" opacity="0.5" />
          <circle cx="50" cy="152" r="1.4" opacity="0.4" />
        </g>
      </svg>
      {/* ícone central */}
      <div
        className="relative w-24 h-24 md:w-28 md:h-28 rounded-full flex items-center justify-center"
        style={{
          background: `linear-gradient(135deg, ${accent}33 0%, ${accent}11 100%)`,
          boxShadow: `inset 0 0 30px ${accent}22`,
        }}
      >
        <Icon
          className="w-10 h-10 md:w-12 md:h-12"
          strokeWidth={1.4}
          style={{ color: accent, filter: `drop-shadow(0 0 8px ${accent}55)` }}
        />
      </div>
      {/* micro-label */}
      <span
        className="absolute bottom-1 md:bottom-2 text-[10px] font-semibold uppercase tracking-widest"
        style={{ color: `${accent}bb` }}
      >
        {label}
      </span>
    </div>
  );
};

const RecommendationHero = ({ rec, onStart, onWhyExpanded }) => {
  const theme = useMemo(() => DAILY_THEMES[dayOfYear() % DAILY_THEMES.length], []);
  const badge = priorityBadge(rec?.priority);
  const durationMin = rec?.duration_min && rec.duration_min > 1 ? rec.duration_min : null;
  const title = rec?.title || 'Fazer o check-in de hoje';
  const subtitle = rec?.subtitle || rec?.reasoning || 'Sua próxima melhor decisão de estudo.';
  const actionLabel = rec?.action_label || 'Iniciar agora';

  return (
    <section
      data-testid="dashboard-recommendation-hero"
      className="relative rounded-2xl overflow-hidden border shadow-sm"
      style={{
        // versão CLEAN clara — casa com o fundo do dashboard (#f8f7fc)
        background:
          'linear-gradient(135deg, #ffffff 0%, #f8f6ff 35%, #ede9ff 100%)',
        borderColor: '#e4dff5',
      }}
    >
      {/* Halo suave no canto superior direito */}
      <div
        aria-hidden
        className="absolute -top-24 -right-16 w-80 h-80 rounded-full opacity-60"
        style={{
          background: 'radial-gradient(circle, rgba(139,92,246,0.18) 0%, transparent 70%)',
          filter: 'blur(10px)',
        }}
      />

      <div className="relative grid grid-cols-[1fr_auto] gap-4 md:gap-6 items-center p-5 md:p-6">
        {/* ─── Coluna esquerda: missão do dia ─── */}
        <div className="min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span
              className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-semibold uppercase tracking-widest"
              style={{
                background: 'rgba(108,92,231,0.10)',
                color: '#5B4BD5',
                border: '1px solid rgba(108,92,231,0.20)',
              }}
            >
              <Sparkles className="w-3 h-3" />
              Missão do dia
            </span>
            {badge && (
              <span
                data-testid="dashboard-recommendation-priority"
                className="px-2.5 py-1 rounded-full text-[9.5px] font-bold uppercase tracking-widest"
                style={{ background: badge.bg, color: badge.color }}
              >
                {badge.label}
              </span>
            )}
          </div>

          <h2
            data-testid="dashboard-recommendation-hero-title"
            className="mt-3 text-[22px] md:text-[26px] font-bold text-slate-900 tracking-tight leading-[1.15]"
          >
            {title}
          </h2>

          <p
            data-testid="dashboard-recommendation-hero-subtitle"
            className="mt-2 text-[13.5px] leading-relaxed max-w-lg text-slate-600"
          >
            {subtitle}
          </p>
          <p
            data-testid="dashboard-mission-context"
            className="mt-2 text-[12.5px] leading-relaxed max-w-lg text-slate-500"
          >
            Comece por esta missão. O restante do plano pode esperar.
          </p>

          <div className="mt-4 flex items-center gap-4 flex-wrap">
            {durationMin && (
              <div className="flex items-center gap-1.5 text-slate-500">
                <Clock className="w-3.5 h-3.5" strokeWidth={1.75} />
                <span className="text-[12.5px]">
                  <span className="text-slate-800 font-semibold">{durationMin} min</span>
                  <span> estimados</span>
                </span>
              </div>
            )}
            <button
              type="button"
              data-testid="dashboard-recommendation-hero-cta"
              onClick={onStart}
              className="inline-flex items-center gap-2 font-semibold px-5 py-2.5 rounded-xl text-white transition-all active:scale-[0.97]"
              style={{
                background: 'linear-gradient(90deg, #6C5CE7 0%, #8b5cf6 100%)',
                boxShadow: '0 8px 22px -6px rgba(108, 92, 231, 0.35)',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = 'linear-gradient(90deg, #5B4BD5 0%, #7c3aed 100%)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'linear-gradient(90deg, #6C5CE7 0%, #8b5cf6 100%)';
              }}
            >
              <span>{actionLabel}</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>
          <WhyThisCard
            signals={rec?.why_signals || []}
            whyNow={rec?.why_now}
            testId="dashboard-why-now"
            onExpanded={onWhyExpanded}
          />
        </div>

        {/* ─── Coluna direita: ilustração diária (auto-rotate) ─── */}
        <div className="hidden sm:flex w-[160px] md:w-[200px] aspect-square shrink-0">
          <DailyIllustration theme={theme} />
        </div>
      </div>
    </section>
  );
};

export default RecommendationHero;
