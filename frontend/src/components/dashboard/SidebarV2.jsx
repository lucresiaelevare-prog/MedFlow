import { useLocation, useNavigate } from 'react-router-dom';
import { Home, Calendar, Heart, Bot, User } from 'lucide-react';

/**
 * SidebarV2 — Clinical Minimalism (dark navy).
 *
 * Uso: apenas nas rotas que adotarem o novo Shell v2
 * (por enquanto /dashboard e /habitos). Shell global segue intacto.
 *
 * activePath: força qual item aparece como ativo (útil quando a rota
 * tem sub-rotas ou alias). Se ausente, usa location.pathname.
 */
const NAV_ITEMS = [
  { label: 'Início',  Icon: Home,     path: '/hoje' },
  { label: 'Hoje',    Icon: Calendar, path: '/dashboard' },
  { label: 'Hábitos', Icon: Heart,    path: '/habitos' },
  { label: 'Tutor',   Icon: Bot,      path: '/tutor' },
  { label: 'Perfil',  Icon: User,     path: '/profile' },
];

const SidebarV2 = ({ userName, activePath }) => {
  const location = useLocation();
  const navigate = useNavigate();
  const current = activePath || location.pathname;
  const initial = (userName || 'U').trim().charAt(0).toUpperCase();
  return (
    <aside
      data-testid="dashboard-sidebar"
      className="fixed left-0 top-0 bottom-0 w-60 flex-col z-50 hidden lg:flex"
      style={{ background: '#1a1a3e' }}
    >
      <div className="px-6 py-6">
        <div className="flex items-center gap-3">
          <div
            className="w-8 h-8 rounded-lg flex items-center justify-center"
            style={{ background: '#6C5CE7', color: '#fff', fontWeight: 700 }}
          >
            M
          </div>
          <span className="text-white font-bold text-lg tracking-tight">MedFlow</span>
        </div>
        <p className="text-slate-400 text-xs mt-1.5">Seu ritmo. Sua aprovação.</p>
      </div>
      <nav className="flex-1 px-3 py-4 space-y-1">
        {NAV_ITEMS.map((item) => {
          const active = current === item.path;
          return (
            <button
              key={item.label}
              data-testid={`dashboard-sidebar-${item.label.toLowerCase()}`}
              onClick={() => navigate(item.path)}
              className="w-full flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium transition-all duration-200"
              style={{
                background: active ? '#2d2b6b' : 'transparent',
                color: active ? '#fff' : '#94a3b8',
                borderLeft: active ? '3px solid #6C5CE7' : '3px solid transparent',
              }}
              onMouseEnter={(e) => {
                if (!active) {
                  e.currentTarget.style.background = 'rgba(255,255,255,.05)';
                  e.currentTarget.style.color = '#fff';
                }
              }}
              onMouseLeave={(e) => {
                if (!active) {
                  e.currentTarget.style.background = 'transparent';
                  e.currentTarget.style.color = '#94a3b8';
                }
              }}
            >
              <item.Icon className="w-5 h-5" style={{ color: active ? '#6C5CE7' : undefined }} />
              <span>{item.label}</span>
            </button>
          );
        })}
      </nav>
      <div className="px-4 pb-6">
        <div
          className="flex items-center gap-3 p-3 rounded-lg"
          style={{ background: 'rgba(255,255,255,.05)' }}
        >
          <div
            className="w-9 h-9 rounded-full flex items-center justify-center text-white font-semibold text-sm"
            style={{ background: '#475569' }}
          >
            {initial}
          </div>
          <div className="min-w-0">
            <p className="text-white text-sm font-medium truncate">{userName || 'Usuário'}</p>
            <p className="text-slate-500 text-xs truncate">MedFlow</p>
          </div>
        </div>
      </div>
    </aside>
  );
};

export default SidebarV2;
