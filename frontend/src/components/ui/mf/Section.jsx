/**
 * <Section> — bloco vertical com espaçamento padrão do MedFlow.
 *
 * Uso: envolver blocos principais dentro do container de tela.
 * Aplica gap vertical padrão entre filhos (`var(--space-4)` mobile,
 * `var(--space-5)` desktop).
 *
 * Ver /app/docs/design-system.md §1 e §7.
 */
const Section = ({ as: As = 'section', children, className = '', spacing = 'md', ...rest }) => {
  const gaps = {
    tight: 'space-y-3',        // 12px
    md:    'space-y-4 md:space-y-5', // 16-20px
    loose: 'space-y-6 md:space-y-8', // 24-32px
  };
  return (
    <As className={`${gaps[spacing] || gaps.md} ${className}`} {...rest}>
      {children}
    </As>
  );
};

export default Section;
