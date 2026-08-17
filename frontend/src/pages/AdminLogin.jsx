import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Shield, ArrowRight, Loader2, AlertCircle } from 'lucide-react';
import api from '@/lib/api';

const AdminLogin = () => {
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const onSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await api.post('/auth/admin-login', { email: email.trim().toLowerCase(), password });
      window.location.href = '/admin';
    } catch (ex) {
      setError('Credenciais inválidas. Confira e tente novamente.');
    } finally {
      setLoading(false);
    }
  };

  const input =
    'w-full px-3.5 py-2.5 rounded-lg text-[14px] hairline bg-white focus:outline-none focus:ring-2 focus:ring-brand/40 placeholder:text-zinc-400';

  return (
    <div className="min-h-screen bg-white flex flex-col" translate="no">
      <header className="hairline-b">
        <div className="max-w-6xl mx-auto px-5 md:px-8 h-14 md:h-16 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2" data-testid="admin-login-back">
            <span
              aria-hidden="true"
              className="w-8 h-8 rounded-[9px] flex items-center justify-center text-white text-[14px] font-semibold tracking-tight"
              style={{ background: 'var(--mf-brand)' }}
            >
              <span>M</span>
            </span>
            <span className="font-semibold text-[17px] tracking-tight text-zinc-900">
              <span>MedFlow</span>
            </span>
          </Link>
          <span className="pill"><span>Painel administrativo</span></span>
        </div>
      </header>

      <main className="flex-1 flex items-center justify-center px-5 py-10">
        <div className="w-full max-w-md" data-testid="admin-login-root">
          <div className="text-center mb-8">
            <span
              className="inline-flex w-12 h-12 rounded-xl items-center justify-center mb-4"
              style={{ background: 'var(--mf-brand-soft)', color: 'var(--mf-brand)' }}
            >
              <Shield strokeWidth={1.75} className="w-6 h-6" />
            </span>
            <h1
              className="font-semibold text-zinc-900 tracking-tight"
              style={{ fontSize: 'clamp(26px, 3.4vw, 34px)', letterSpacing: '-0.02em' }}
            >
              <span>Painel administrativo</span>
            </h1>
            <p className="mt-2 text-[14.5px] text-zinc-500 max-w-sm mx-auto leading-relaxed">
              <span>
                Acesso restrito. Este painel abriga o banco de dados anonimizado de padrões de
                aprendizagem — MedFlow Research.
              </span>
            </p>
          </div>

          <form onSubmit={onSubmit} className="mf-card p-5 md:p-6 space-y-4" data-testid="admin-login-form">
            <label className="block">
              <span className="eyebrow"><span>email</span></span>
              <input
                data-testid="admin-login-email"
                type="email"
                required
                autoComplete="username"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className={`${input} mt-2`}
                placeholder="admin@medflow.app"
              />
            </label>

            <label className="block">
              <span className="eyebrow"><span>senha</span></span>
              <input
                data-testid="admin-login-password"
                type="password"
                required
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className={`${input} mt-2`}
                placeholder="••••••••"
              />
            </label>

            {error && (
              <div
                data-testid="admin-login-error"
                className="flex items-start gap-2 px-3 py-2.5 rounded-lg text-[13px]"
                style={{ background: 'var(--mf-care-soft)', color: '#B15437' }}
              >
                <AlertCircle strokeWidth={1.75} className="w-4 h-4 shrink-0 mt-0.5" />
                <span>{error}</span>
              </div>
            )}

            <button
              data-testid="admin-login-submit"
              type="submit"
              disabled={loading || !email || !password}
              className="btn-primary w-full"
            >
              {loading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Entrando…</span>
                </>
              ) : (
                <>
                  <span>Entrar no painel</span>
                  <ArrowRight strokeWidth={2} className="w-4 h-4" />
                </>
              )}
            </button>
          </form>

          <p className="mt-6 text-center text-[12px] text-zinc-400">
            <button
              type="button"
              onClick={() => navigate('/')}
              className="hover:text-zinc-700 transition-colors"
              data-testid="admin-login-home-link"
            >
              <span>← Voltar para a página inicial</span>
            </button>
          </p>
        </div>
      </main>
    </div>
  );
};

export default AdminLogin;
