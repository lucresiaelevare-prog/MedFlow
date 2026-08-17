import { NavLink, useNavigate, useLocation } from 'react-router-dom';
import {
  Home, Calendar, Heart, Bot, User, BookMarked, LogOut, Moon, Sun, Shield, Target,
} from 'lucide-react';
import { useAuth } from '@/context/AuthContext';
import { useTheme } from '@/context/ThemeContext';
import { useFocus } from '@/context/FocusContext';
import { useEffect, useState } from 'react';
import api from '@/lib/api';
import IDS from '@/constants/testIds';

// ─── nav items (uma única fonte de verdade — igual em todas as páginas) ──
const NAV_ITEMS = [
  { to: '/hoje',      label: 'Hoje',      Icon: Calendar,   testId: 'nav-hoje' },
  { to: '/dashboard', label: 'Início',    Icon: Home,       testId: 'nav-dashboard' },
  { to: '/habitos',   label: 'Hábitos',   Icon: Heart,      testId: 'nav-habitos' },
  { to: '/tutor',     label: 'Tutor',     Icon: Bot,        testId: 'nav-tutor' },
  { to: '/resources', label: 'Biblioteca',Icon: BookMarked, testId: 'nav-resources' },
  { to: '/profile',   label: 'Perfil',    Icon: User,       testId: 'nav-profile' },
];

const MOBILE_NAV = [
  { to: '/hoje',      label: 'Hoje',    Icon: Calendar, testId: 'nav-hoje' },
  { to: '/dashboard', label: 'Início',  Icon: Home,     testId: 'nav-dashboard' },
  { to: '/tutor',     label: 'Tutor',   Icon: Bot,      testId: 'nav-tutor' },
  { to: '/profile',   label: 'Perfil',  Icon: User,     testId: 'nav-profile' },
];

// ─── paleta do sidebar (SidebarV2 original — navy + purple accent) ───────
const SB = {
  bg:        '#1a1a3e',
  activeBg:  '#2d2b6b',
  hoverBg:   'rgba(255,255,255,.05)',
  accent:    '#6C5CE7',
  textIdle:  '#94a3b8',
  textActive:'#ffffff',
  divider:   'rgba(255,255,255,.08)',
  chip:      'rgba(255,255,255,.05)',
  avatarBg:  '#475569',
};

const SidebarNavItem = ({ to, label, Icon, testId, currentPath }) => {
  const navigate = useNavigate();
  const active = currentPath === to;
  return (
    <button
      key={to}
      data-testid={testId}
      onClick={() => navigate(to)}
      className="w-full flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium transition-all duration-200"
      style={{
        background: active ? SB.activeBg : 'transparent',
        color: active ? SB.textActive : SB.textIdle,
        borderLeft: active ? `3px solid ${SB.accent}` : '3px solid transparent',
      }}
      onMouseEnter={(e) => {
        if (!active) {
          e.currentTarget.style.background = SB.hoverBg;
          e.currentTarget.style.color = SB.textActive;
        }
      }}
      onMouseLeave={(e) => {
        if (!active) {
          e.currentTarget.style.background = 'transparent';
          e.currentTarget.style.color = SB.textIdle;
        }
      }}
    >
      <Icon className="w-5 h-5" style={{ color: active ? SB.accent : undefined }} />
      <span>{label}</span>
    </button>
  );
};

const MobileNavItem = ({ to, label, Icon, testId }) => (
  <NavLink
    to={to}
    data-testid={`${testId}-m`}
    className={({ isActive }) =>
      `flex-1 flex flex-col items-center gap-1 py-2 text-[11px] font-medium transition-colors ${
        isActive ? 'text-brand' : 'text-zinc-500'
      }`
    }
  >
    <Icon strokeWidth={1.75} className="w-5 h-5" />
    <span>{label}</span>
  </NavLink>
);

const Shell = ({ children }) => {
  const { user, logout } = useAuth();
  const { theme, toggle } = useTheme();
  const { focus, toggle: toggleFocus } = useFocus();
  const navigate = useNavigate();
  const location = useLocation();
  const [isAdmin, setIsAdmin] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const { data } = await api.get('/admin/whoami');
        setIsAdmin(!!data.is_admin);
      } catch (e) {
        setIsAdmin(false);
      }
    })();
  }, [user?.user_id]);

  const handleLogout = async () => {
    await logout();
    navigate('/', { replace: true });
  };

  const displayName = (user?.name || 'Usuário').trim();
  const initial = displayName.charAt(0).toUpperCase();

  return (
    <div className="relative min-h-screen" style={{ background: '#f8f7fc' }}>
      {/* ─── Desktop sidebar (fixed left · navy · matches SidebarV2) ─── */}
      <aside
        data-testid="dashboard-sidebar"
        className="hidden lg:flex fixed left-0 top-0 bottom-0 w-60 flex-col z-40"
        style={{ background: SB.bg }}
        aria-label="Menu principal"
      >
        <div className="px-6 py-6">
          <button
            onClick={() => navigate('/hoje')}
            className="flex items-center gap-3 text-left w-full"
            aria-label="MedFlow"
            data-testid="sidebar-logo"
          >
            <img
              src="/brand/medflow-dark.png"
              alt="MedFlow"
              className="w-11 h-11 rounded-lg object-cover shrink-0"
              style={{ background: SB.bg }}
            />
            <span className="text-white font-bold text-lg tracking-tight">MedFlow</span>
          </button>
          <p className="text-slate-400 text-xs mt-2 pl-[3px]">Seu ritmo. Sua aprovação.</p>
        </div>

        <nav className="flex-1 px-3 py-2 space-y-1 overflow-y-auto">
          {NAV_ITEMS.map((n) => (
            <SidebarNavItem key={n.to} {...n} currentPath={location.pathname} />
          ))}
          {isAdmin && (
            <SidebarNavItem
              to="/admin"
              label="Admin"
              Icon={Shield}
              testId="nav-admin"
              currentPath={location.pathname}
            />
          )}
        </nav>

        {/* Footer — toggles + user card + logout */}
        <div className="px-3 py-3" style={{ borderTop: `1px solid ${SB.divider}` }}>
          <div className="flex items-center gap-1 mb-2">
            <button
              data-testid="focus-toggle"
              onClick={toggleFocus}
              className="flex-1 flex items-center justify-center gap-1.5 px-2 py-2 rounded-lg text-[12px] font-medium transition-colors"
              style={{
                background: focus ? SB.activeBg : 'transparent',
                color: focus ? SB.accent : SB.textIdle,
              }}
              aria-label={focus ? 'Sair do modo foco' : 'Ativar modo foco'}
              title={focus ? 'Modo foco ativo' : 'Modo foco'}
            >
              <Target strokeWidth={1.75} className="w-4 h-4" />
              <span>{focus ? 'Foco on' : 'Foco'}</span>
            </button>
            <button
              data-testid="theme-toggle"
              onClick={toggle}
              className="flex items-center justify-center px-3 py-2 rounded-lg transition-colors"
              style={{ background: 'transparent', color: SB.textIdle }}
              onMouseEnter={(e) => { e.currentTarget.style.background = SB.hoverBg; e.currentTarget.style.color = SB.textActive; }}
              onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = SB.textIdle; }}
              aria-label={theme === 'dark' ? 'Ativar tema claro' : 'Ativar tema escuro'}
              title={theme === 'dark' ? 'Tema claro' : 'Tema escuro'}
            >
              {theme === 'dark'
                ? <Sun strokeWidth={1.75} className="w-4 h-4" />
                : <Moon strokeWidth={1.75} className="w-4 h-4" />}
            </button>
          </div>

          <div
            className="flex items-center gap-3 p-3 rounded-lg"
            style={{ background: SB.chip }}
          >
            {user?.picture ? (
              <img
                src={user.picture}
                alt={displayName}
                className="w-9 h-9 rounded-full shrink-0"
                style={{ boxShadow: '0 0 0 1px rgba(255,255,255,.1)' }}
              />
            ) : (
              <div
                className="w-9 h-9 rounded-full flex items-center justify-center text-white font-semibold text-sm shrink-0"
                style={{ background: SB.avatarBg }}
              >
                {initial}
              </div>
            )}
            <div className="min-w-0 flex-1">
              <p className="text-white text-sm font-medium truncate">{displayName}</p>
              <p className="text-slate-500 text-xs truncate">MedFlow</p>
            </div>
            <button
              onClick={handleLogout}
              data-testid={IDS.dashboard.logout}
              className="shrink-0 p-1.5 rounded-md transition-colors"
              style={{ color: SB.textIdle }}
              onMouseEnter={(e) => { e.currentTarget.style.background = SB.hoverBg; e.currentTarget.style.color = SB.textActive; }}
              onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = SB.textIdle; }}
              aria-label="Sair"
              title="Sair"
            >
              <LogOut strokeWidth={1.75} className="w-4 h-4" />
            </button>
          </div>
        </div>
      </aside>

      {/* ─── Mobile top bar (visible < lg) ─── */}
      <header
        className="lg:hidden sticky top-0 z-30 backdrop-blur-sm"
        style={{ background: 'rgba(26, 26, 62, 0.96)', borderBottom: `1px solid ${SB.divider}` }}
      >
        <div className="flex h-16 items-center justify-between px-4 sm:px-5">
          <button
            onClick={() => navigate('/hoje')}
            className="flex min-h-11 items-center gap-2"
            aria-label="MedFlow"
            data-testid="mobile-topbar-logo"
          >
            <img
              src="/brand/medflow-dark.png"
              alt="MedFlow"
              className="w-8 h-8 rounded-lg object-cover"
              style={{ background: SB.bg }}
            />
            <span className="text-white font-semibold text-[15px] tracking-tight">MedFlow</span>
          </button>
          <div className="flex items-center gap-2">
            <button
              data-testid="theme-toggle-m"
              onClick={toggle}
              className="flex h-11 w-11 items-center justify-center rounded-lg text-slate-300 transition-colors hover:bg-white/5 hover:text-white"
              aria-label={theme === 'dark' ? 'Tema claro' : 'Tema escuro'}
            >
              {theme === 'dark'
                ? <Sun strokeWidth={1.75} className="w-4 h-4" />
                : <Moon strokeWidth={1.75} className="w-4 h-4" />}
            </button>
            <button
              onClick={handleLogout}
              data-testid={`${IDS.dashboard.logout}-m`}
              className="flex h-11 w-11 items-center justify-center rounded-lg text-slate-300 transition-colors hover:bg-white/5 hover:text-white"
              aria-label="Sair"
            >
              <LogOut strokeWidth={1.75} className="w-4 h-4" />
            </button>
            {user?.picture ? (
              <img src={user.picture} alt={displayName} className="w-8 h-8 rounded-full ring-1 ring-white/10" />
            ) : (
              <div
                className="w-8 h-8 rounded-full flex items-center justify-center text-white font-semibold text-[12px]"
                style={{ background: SB.avatarBg }}
              >{initial}</div>
            )}
          </div>
        </div>
      </header>

      {/* ─── Main content (offset by sidebar on lg+) ─── */}
      <main className="relative z-10 min-h-screen pb-24 lg:ml-60 lg:pb-0">
        {children}
      </main>

      {/* ─── Mobile bottom tab bar ─── */}
      <nav
        className="lg:hidden fixed bottom-0 inset-x-0 z-30 bg-white"
        style={{ borderTop: '1px solid var(--mf-hair)' }}
        aria-label="Navegação principal"
      >
        <div className="flex min-h-16 items-stretch justify-between px-2 pb-1.5 pt-1">
          {MOBILE_NAV.map((n) => <MobileNavItem key={n.to} {...n} />)}
          {isAdmin && (
            <MobileNavItem
              to="/admin"
              label="Admin"
              Icon={Shield}
              testId="nav-admin"
            />
          )}
        </div>
      </nav>
    </div>
  );
};

export default Shell;
