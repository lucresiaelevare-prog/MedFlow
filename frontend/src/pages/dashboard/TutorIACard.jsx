import { Sparkles, ArrowRight, MessagesSquare, Compass } from 'lucide-react';

/**
 * TutorIACard — bloco visual definitivo da Dashboard.
 *
 * Camada de apresentação apenas. Sem fetch, sem state, sem hook próprio.
 * O comportamento (para onde vai) é responsabilidade do pai (Dashboard.jsx),
 * que injeta `onOpen`. Mantém a identidade do Tutor IA e a linguagem
 * de mentor do MedFlow — não é placeholder, é o card final.
 */
const TutorIACard = ({ onOpen }) => (
  <section
    data-testid="dashboard-tutor-ia-card"
    className="mf-card p-6 md:p-7 animate-fade-in"
  >
    <div className="flex flex-col md:flex-row md:items-start gap-5 md:gap-6">
      {/* Ícone identidade */}
      <div
        className="w-11 h-11 rounded-xl flex items-center justify-center shrink-0"
        style={{ background: 'var(--mf-brand-soft)', color: 'var(--mf-brand)' }}
        aria-hidden
      >
        <Compass strokeWidth={1.75} className="w-5 h-5" />
      </div>

      {/* Corpo */}
      <div className="flex-1 min-w-0">
        <p className="eyebrow" style={{ color: 'var(--mf-brand)' }}>
          <span>Tutor IA</span>
        </p>
        <h2 className="mt-1 text-[18px] md:text-[20px] font-semibold text-zinc-900 tracking-tight leading-snug">
          <span>Um mentor pra guiar sua próxima decisão de estudo.</span>
        </h2>
        <p className="mt-2 text-[13.5px] text-zinc-600 leading-relaxed max-w-xl">
          <span>
            Diga o tema, envie um PDF, cole uma questão ou faça uma pergunta.
            Eu identifico sua intenção e conduzo a melhor estratégia — resumo,
            flashcards, questões ou revisão completa — a partir daí.
          </span>
        </p>

        {/* Indicadores discretos do que o Tutor faz — sem números fictícios */}
        <div className="mt-4 flex flex-wrap items-center gap-2">
          <span className="pill">
            <MessagesSquare strokeWidth={1.75} className="w-3 h-3" />
            <span>Conversa contextual</span>
          </span>
          <span className="pill">
            <Sparkles strokeWidth={1.75} className="w-3 h-3" />
            <span>Revisão completa</span>
          </span>
          <span className="pill">
            <span>Memória do que você já viu</span>
          </span>
        </div>

        {/* CTA */}
        <div className="mt-5">
          <button
            type="button"
            data-testid="dashboard-tutor-ia-open"
            onClick={onOpen}
            className="btn-primary"
          >
            <Sparkles strokeWidth={1.75} className="w-4 h-4" />
            <span>Conversar com o Tutor</span>
            <ArrowRight strokeWidth={1.75} className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  </section>
);

export default TutorIACard;
