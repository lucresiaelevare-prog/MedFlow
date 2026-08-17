import { useMemo } from 'react';
import { Check, AlertTriangle, AlertOctagon } from 'lucide-react';

/**
 * RhythmStrip — card CENTRAL do /dashboard. Consolida:
 *   1) o Índice de Equilíbrio Acadêmico (rebatizado "Seu Ritmo de Aprovação")
 *   2) o ECG-semáforo: 5 batimentos, um por pilar, com amplitude e cor
 *      derivadas do score REAL de cada pilar → o traço "quebra" no pilar fraco
 *   3) a mensagem humana com o pilar limitante nomeado
 *
 * Substitui o antigo IEAHero (lateral) + a versão anterior compacta do
 * RhythmStrip. Passa a ocupar largura total do dashboard.
 *
 * Fonte dos dados: /api/iea → { iea, weakest_pillar, pillars[] } (todos reais).
 */

const PILLARS = [
  { key: 'estudos',      label: 'Estudos'      },
  { key: 'sono',         label: 'Sono'         },
  { key: 'saude_fisica', label: 'Saúde Física' },
  { key: 'bem_estar',    label: 'Bem-estar'    },
  { key: 'social',       label: 'Social'       },
];

// ── Classificação de estado geral (IEA)
const stateOf = (iea) => {
  if (iea == null) return { key: 'unknown', word: 'Aguardando dados',  color: '#94a3b8', halo: '#e2e8f0' };
  if (iea >= 68)   return { key: 'stable',  word: 'Ritmo estável',     color: '#059669', halo: '#D1FAE5' };
  if (iea >= 40)   return { key: 'weak',    word: 'Ritmo perdeu força', color: '#F59E0B', halo: '#FEF3C7' };
  return                  { key: 'risk',    word: 'Ritmo em risco',     color: '#DC6B4C', halo: '#FDE7DE' };
};

// ── Semáforo por pilar (verde/âmbar/vermelho)
const beatToneOf = (score) => {
  if (score == null)  return { color: '#94a3b8', bg: '#f1f5f9', Icon: AlertTriangle };
  if (score >= 60)    return { color: '#059669', bg: '#D1FAE5', Icon: Check          };
  if (score >= 40)    return { color: '#F59E0B', bg: '#FEF3C7', Icon: AlertTriangle  };
  return                     { color: '#DC6B4C', bg: '#FDE7DE', Icon: AlertOctagon   };
};

const weakestLabelOf = (weakest_pillar) =>
  PILLARS.find((p) => p.key === weakest_pillar)?.label || null;

// ── Coerência: se todos os pilares estão >=60 (verde), o overall NÃO pode
// ser "weak"; se todos <40 (vermelho), overall não pode ser "stable".
// Também detecta empate real entre pilares (gap <=5) para evitar apontar
// um "pilar limitante" quando matematicamente não existe.
const reconcile = (baseState, pillars) => {
  if (!pillars || pillars.length === 0) return { state: baseState, balanced: false, allGreen: false };
  const scores = pillars.map((p) => (typeof p.score === 'number' ? p.score : 0));
  const minS = Math.min(...scores);
  const maxS = Math.max(...scores);
  const gap = maxS - minS;
  const balanced = gap <= 5; // empate visual
  const allGreen = minS >= 60;
  let state = baseState;
  if (allGreen && baseState.key === 'weak') {
    state = { key: 'stable', word: 'Ritmo estável', color: '#059669', halo: '#D1FAE5' };
  } else if (minS < 40 && baseState.key === 'stable') {
    state = { key: 'weak', word: 'Ritmo perdeu força', color: '#F59E0B', halo: '#FEF3C7' };
  }
  return { state, balanced, allGreen };
};

// ── Path de um batimento (QRS) centrado em cx, com amplitude A
// A escala é score/100 → floor 3, teto ~30. Score baixo = traço quase reto.
const beatPath = (cx, A) => {
  return (
    `M ${cx - 45} 45 ` +           // baseline esquerda
    `L ${cx - 15} 45 ` +
    `L ${cx - 10} ${45 - A * 0.22} ` + // pequena onda P
    `L ${cx - 5}  45 ` +
    `L ${cx - 2}  ${45 + A * 0.45} ` + // Q dip (para baixo)
    `L ${cx + 1}  ${45 - A} ` +        // R peak (para cima)
    `L ${cx + 4}  ${45 + A * 0.55} ` + // S dip
    `L ${cx + 7}  45 ` +
    `L ${cx + 14} ${45 - A * 0.18} ` + // T wave
    `L ${cx + 22} 45 ` +
    `L ${cx + 45} 45`                  // baseline direita
  );
};

// ── Estimativa animada opcional: mesmo score = fase estável.
const RhythmStrip = ({ iea }) => {
  const baseState = stateOf(iea?.iea);
  const { state: overall, balanced, allGreen } = reconcile(baseState, iea?.pillars);
  // Só nomeia "pilar limitante" quando há gap real E ele não está verde.
  const weakestPillarObj = (iea?.pillars || []).find((p) => p.key === iea?.weakest_pillar);
  const weakestScore = weakestPillarObj?.score;
  const canNameWeakest = !balanced && !allGreen && typeof weakestScore === 'number' && weakestScore < 60;
  const weakestLabel = canNameWeakest ? weakestLabelOf(iea?.weakest_pillar) : null;

  // Assemble pillar rows (mantém ordem definida, injeta score do backend)
  const rows = useMemo(() => {
    const byKey = Object.fromEntries((iea?.pillars || []).map((p) => [p.key, p.score]));
    return PILLARS.map((p, i) => {
      const score = byKey[p.key] ?? null;
      const amp   = Math.max(3, Math.round(((score ?? 0) / 100) * 30));
      const tone  = beatToneOf(score);
      return { ...p, score, amp, tone, cx: i * 100 + 50 };
    });
  }, [iea]);

  const humanMessage = useMemo(() => {
    if (iea?.iea == null) {
      return {
        first: 'Ainda estou aprendendo o seu ritmo.',
        second: 'Faça o primeiro check-in para eu calibrar seus 5 pilares.',
      };
    }
    if (weakestLabel) {
      return {
        first: (
          <>
            Seu ritmo está sendo limitado pelo{' '}
            <strong className="text-slate-900">{weakestLabel}</strong>.
          </>
        ),
        second: 'Enquanto esse pilar permanecer baixo, sua evolução fica comprometida.',
      };
    }
    if (balanced && !allGreen) {
      return {
        first: 'Seu ritmo está equilibrado entre os pilares.',
        second: 'O próximo avanço depende de melhorar todos de forma consistente.',
      };
    }
    return {
      first: 'Seu ritmo está equilibrado nos 5 pilares.',
      second: 'Continue no que está funcionando.',
    };
  }, [iea, weakestLabel, balanced, allGreen]);

  return (
    <section
      data-testid="dashboard-rhythm-strip"
      data-state={overall.key}
      className="bg-white rounded-2xl border border-slate-100 shadow-sm overflow-hidden"
    >
      {/* ── Linha 1: Score grande à esquerda + ECG à direita ── */}
      <div className="p-5 md:p-6 grid grid-cols-1 lg:grid-cols-[240px_1fr] gap-4 lg:gap-6 items-center">
        {/* Score */}
        <div className="flex items-center gap-4">
          <div
            className="relative w-[92px] h-[92px] rounded-2xl flex items-center justify-center shrink-0"
            style={{ background: overall.halo }}
          >
            <span
              data-testid="iea-score"
              className="text-[36px] font-bold tabular text-slate-900 leading-none"
              style={{ letterSpacing: '-0.03em' }}
            >
              {iea?.iea ?? '—'}
            </span>
            <span className="absolute -bottom-1.5 right-1.5 text-[11px] text-slate-500 font-medium tabular">/100</span>
          </div>
          <div className="min-w-0">
            <p className="text-[10px] font-semibold uppercase tracking-widest text-slate-500">
              Seu Ritmo de Aprovação
            </p>
            <p
              className="mt-1 text-[15px] font-semibold"
              style={{ color: overall.color }}
              data-testid="dashboard-rhythm-state"
            >
              {overall.word}
            </p>
          </div>
        </div>

        {/* ECG por pilar (5 batimentos) */}
        <div className="relative">
          <svg
            data-testid="dashboard-pillar-ecg"
            viewBox="0 0 500 60"
            className="w-full h-14 md:h-16"
            aria-hidden="true"
          >
            {/* linha guia sutil */}
            <line x1="0" y1="45" x2="500" y2="45" stroke="#E2E8F0" strokeWidth="0.8" strokeDasharray="3 4" />
            {/* separadores por seção */}
            {rows.map((r, i) => (
              i > 0 && (
                <line
                  key={`sep-${i}`}
                  x1={i * 100} y1="12" x2={i * 100} y2="55"
                  stroke="#F1F5F9" strokeWidth="1"
                />
              )
            ))}
            {/* traços base (opacidade baixa) — sempre visíveis */}
            {rows.map((r) => (
              <path
                key={`base-${r.key}`}
                d={beatPath(r.cx, r.amp)}
                fill="none"
                stroke={r.tone.color}
                strokeWidth="1.4"
                strokeLinecap="round"
                strokeLinejoin="round"
                opacity="0.32"
              />
            ))}
            {/* traços em animação sequencial (sweep pilar-por-pilar) */}
            {rows.map((r, i) => {
              // len aproximado do path (visual sweep de ~120 px)
              const len = 120;
              // cada beat começa 0.5s depois do anterior — 5 beats em 3s + pausa 1s → 4s ciclo
              const dur = 4;
              const delay = i * 0.5;
              const keyName = `mf-beat-${r.key}-${i}`;
              return (
                <g key={`ani-${r.key}`}>
                  <path
                    d={beatPath(r.cx, r.amp)}
                    fill="none"
                    stroke={r.tone.color}
                    strokeWidth="2.2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeDasharray={`${len} 900`}
                    strokeDashoffset={len}
                    style={{
                      animation: `${keyName} ${dur}s cubic-bezier(0.4, 0, 0.2, 1) ${delay}s infinite`,
                      filter: `drop-shadow(0 0 3px ${r.tone.color}66)`,
                    }}
                  />
                  <style>{`
                    @keyframes ${keyName} {
                      0%   { stroke-dashoffset: ${len}; }
                      12%  { stroke-dashoffset: 0; }
                      25%  { stroke-dashoffset: 0; opacity: 0.9; }
                      35%  { stroke-dashoffset: 0; opacity: 0.4; }
                      100% { stroke-dashoffset: ${len}; opacity: 0; }
                    }
                  `}</style>
                </g>
              );
            })}
          </svg>

          {/* Rótulos dos pilares (linha semáforo) */}
          <div className="mt-1 grid grid-cols-5 gap-1.5 sm:gap-2">
            {rows.map((r) => {
              const isWeakest = canNameWeakest && r.key === iea?.weakest_pillar;
              const IconEl = r.tone.Icon;
              return (
                <div
                  key={`lbl-${r.key}`}
                  data-testid={`pillar-beat-${r.key}`}
                  data-weakest={isWeakest ? 'true' : 'false'}
                  className="flex min-w-0 flex-col items-center justify-start gap-0.5"
                >
                  <div className="flex items-center gap-1">
                    <IconEl
                      className="h-3 w-3 shrink-0"
                      style={{ color: r.tone.color }}
                      strokeWidth={2.2}
                    />
                    <span
                      className="shrink-0 text-[11px] font-bold tabular"
                      style={{ color: r.tone.color }}
                    >
                      {r.score ?? '—'}
                    </span>
                  </div>
                  <span
                    className="min-h-[2.4em] text-center text-[11px] font-medium leading-[1.2]"
                    style={{ color: isWeakest ? r.tone.color : '#64748b' }}
                  >
                    {r.label}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* ── Linha 2: mensagem humana com o pilar limitante nomeado ── */}
      <div
        data-testid="dashboard-rhythm-message"
        className="px-5 md:px-6 py-4 border-t border-slate-100 flex items-start gap-3"
        style={{ background: '#fafafd' }}
      >
        <span
          className="w-1.5 h-1.5 rounded-full mt-1.5 shrink-0"
          style={{ background: overall.color }}
        />
        <div className="min-w-0">
          <p className="text-[14px] text-slate-700 leading-relaxed">
            {humanMessage.first}
          </p>
          <p className="mt-0.5 text-[13px] text-slate-500 leading-relaxed">
            {humanMessage.second}
          </p>
        </div>
      </div>
    </section>
  );
};

export default RhythmStrip;
