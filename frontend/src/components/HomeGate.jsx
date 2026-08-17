import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '@/context/AuthContext';
import api from '@/lib/api';

/**
 * Roteia a landing autenticada:
 *   - novo usuário sem onboarding minimal → /comecar
 *   - existente com tour pendente        → /bem-vindo
 *   - home_layout === "smart"            → /hoje
 *   - home_layout === "control_center"   → /dashboard
 */
const HomeGate = ({ fallback = null }) => {
  const { isAuthenticated } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (isAuthenticated !== true) return;
    let cancelled = false;
    (async () => {
      try {
        const { data } = await api.get('/experience/state');
        if (cancelled) return;
        const anyHistory =
          (data.stats?.days_active || 0) > 0 ||
          (data.stats?.checkins_total || 0) > 0 ||
          (data.stats?.pomodoros_completed || 0) > 0;
        if (!data.minimal_onboarding_done && !anyHistory) {
          navigate('/comecar', { replace: true });
        } else if (data.tour_pending) {
          navigate('/bem-vindo', { replace: true });
        } else {
          // Nova arquitetura: sempre cai em /hoje (executar).
          // /dashboard fica como painel completo (Início) acessível pelo menu.
          navigate('/hoje', { replace: true });
        }
      } catch {
        navigate('/hoje', { replace: true });
      }
    })();
    return () => { cancelled = true; };
  }, [isAuthenticated, navigate]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-canvas">
      {fallback || <div className="w-8 h-8 rounded-full border-2 border-zinc-200 border-t-zinc-600 animate-spin" />}
    </div>
  );
};

export default HomeGate;
