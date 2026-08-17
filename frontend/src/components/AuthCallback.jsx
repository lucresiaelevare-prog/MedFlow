import { useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '@/lib/api';
import { useAuth } from '@/context/AuthContext';

const AuthCallback = () => {
  const navigate = useNavigate();
  const { setUser, setIsAuthenticated } = useAuth();
  const hasProcessed = useRef(false);

  useEffect(() => {
    if (hasProcessed.current) return;
    hasProcessed.current = true;

    const run = async () => {
      try {
        const hash = window.location.hash || '';
        const params = new URLSearchParams(hash.startsWith('#') ? hash.slice(1) : hash);
        const sessionId = params.get('session_id');
        if (!sessionId) {
          navigate('/', { replace: true });
          return;
        }
        const { data } = await api.post('/auth/session', { session_id: sessionId });
        setUser(data.user);
        setIsAuthenticated(true);
        // Clear the hash and go to dashboard
        window.history.replaceState(null, '', '/dashboard');
        navigate('/dashboard', { replace: true, state: { user: data.user } });
      } catch (e) {
        console.error('Auth callback failed', e);
        navigate('/', { replace: true });
      }
    };
    run();
  }, [navigate, setUser, setIsAuthenticated]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-stone-50">
      <div className="flex flex-col items-center gap-4 text-stone-600">
        <div className="w-10 h-10 rounded-full border-2 border-sage-200 border-t-sage-600 animate-spin" />
        <p className="text-sm">Entrando com segurança…</p>
      </div>
    </div>
  );
};

export default AuthCallback;
