import {
  BookOpen,
  LayoutDashboard,
  MessageSquareText,
  Settings2,
  UsersRound,
  Wrench,
} from 'lucide-react';

const primaryItems = [
  { key: 'dashboard', label: 'Visão geral', Icon: LayoutDashboard },
  { key: 'students', label: 'Alunos', Icon: UsersRound },
  { key: 'content', label: 'Conteúdo', Icon: BookOpen },
  { key: 'questions', label: 'Plantão de dúvidas', Icon: MessageSquareText },
  { key: 'settings', label: 'Configurações', Icon: Settings2 },
];

export const BusinessAdminNav = ({ active, onChange, technicalAccess }) => (
  <nav className="border-b border-slate-200 bg-white" data-testid="business-admin-navigation">
    <div className="mx-auto max-w-7xl overflow-x-auto px-4 sm:px-6 lg:px-8">
      <div className="flex min-w-max items-center gap-1 py-2">
        {primaryItems.map(({ key, label, Icon }) => (
          <button
            key={key}
            type="button"
            onClick={() => onChange(key)}
            data-testid={`business-nav-${key}`}
            className={`inline-flex items-center gap-2 px-3 py-2 text-sm font-medium transition-colors duration-150 ${
              active === key
                ? 'bg-emerald-50 text-emerald-800'
                : 'text-slate-600 hover:bg-slate-50 hover:text-slate-950'
            }`}
          >
            <Icon className="h-4 w-4" strokeWidth={1.8} />
            {label}
          </button>
        ))}
        {technicalAccess && (
          <>
            <span className="mx-2 h-6 w-px bg-slate-200" />
            <button
              type="button"
              onClick={() => onChange('developer')}
              data-testid="business-nav-developer"
              className={`inline-flex items-center gap-2 px-3 py-2 text-sm font-medium transition-colors duration-150 ${
                active === 'developer'
                  ? 'bg-slate-900 text-white'
                  : 'text-slate-600 hover:bg-slate-100 hover:text-slate-950'
              }`}
            >
              <Wrench className="h-4 w-4" strokeWidth={1.8} />
              Modo desenvolvedor
            </button>
          </>
        )}
      </div>
    </div>
  </nav>
);