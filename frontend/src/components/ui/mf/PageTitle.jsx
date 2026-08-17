/**
 * <PageTitle> — cabeçalho padrão de tela.
 *
 * Composição: eyebrow (opcional) + título grande + descrição (opcional)
 * + slot de ação (botão/CTA no canto direito, opcional).
 *
 * Segue a hierarquia de leitura em <5s:
 *  1. Eyebrow contextual
 *  2. Título grande (peso 600, tracking -0.02em)
 *  3. Descrição em cinza para respiro
 *
 * Ver /app/docs/design-system.md §3, §7.
 */
const PageTitle = ({ eyebrow, title, description, action, className = '' }) => (
  <header className={`animate-fade-in ${className}`}>
    <div className="flex items-start justify-between gap-4">
      <div className="flex-1 min-w-0">
        {eyebrow && (
          <p className="eyebrow"><span>{eyebrow}</span></p>
        )}
        {title && (
          <h1
            className="font-semibold text-zinc-900 tracking-tight leading-[1.15]"
            style={{
              fontSize: 'var(--text-4xl)',
              marginTop: eyebrow ? 'var(--space-2)' : 0,
              letterSpacing: '-0.02em',
            }}
          >
            <span>{title}</span>
          </h1>
        )}
        {description && (
          <p
            className="text-zinc-500 leading-relaxed"
            style={{
              fontSize: 'var(--text-lg)',
              marginTop: 'var(--space-3)',
              maxWidth: '52ch',
            }}
          >
            <span>{description}</span>
          </p>
        )}
      </div>
      {action && (
        <div className="shrink-0">{action}</div>
      )}
    </div>
  </header>
);

export default PageTitle;
