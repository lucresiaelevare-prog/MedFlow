import { ArrowLeft } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { GoogleG, Wordmark } from '@/components/landing/primitives';

export default function Entrar() {
  const navigate = useNavigate();

  const handleLogin = () => {
    const redirectUrl = `${window.location.origin}/dashboard`;
    const authUrl = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
    window.location.href = authUrl;
  };

  return (
    <div
      className="min-h-screen px-4 py-4 sm:px-6 sm:py-6"
      data-testid="login-page"
      style={{ background: 'var(--mf-inst-bg)', color: 'var(--mf-inst-ink)' }}
    >
      <header className="mx-auto flex max-w-[1240px] items-center justify-between">
        <Wordmark />
        <button
          aria-label="Voltar para a página inicial"
          className="inline-flex min-h-11 min-w-11 items-center justify-center rounded-md"
          data-testid="login-back-button"
          onClick={() => navigate('/')}
          style={{ border: '1px solid var(--mf-inst-line-2)' }}
          type="button"
        >
          <ArrowLeft aria-hidden="true" className="h-4 w-4" />
        </button>
      </header>

      <main className="mx-auto flex min-h-[calc(100vh-96px)] max-w-md items-center py-10 sm:py-16">
        <section className="w-full" data-testid="login-panel">
          <p
            className="text-[14px] font-medium"
            data-testid="login-eyebrow"
            style={{ color: 'var(--mf-inst-muted)' }}
          >
            Acesso MedFlow
          </p>
          <h1
            className="mt-3 text-[clamp(32px,10vw,48px)] font-semibold leading-[1.05]"
            data-testid="login-title"
          >
            Entrar para continuar.
          </h1>
          <p
            className="mt-5 text-[16px] leading-relaxed"
            data-testid="login-description"
            style={{ color: 'var(--mf-inst-ink-2)' }}
          >
            Use sua conta Google para acessar seu plano de estudo.
          </p>
          <button
            className={
              'mt-8 inline-flex min-h-12 w-full items-center justify-center ' +
              'gap-2 px-5 py-3 text-[16px] font-medium'
            }
            data-testid="login-google-button"
            onClick={handleLogin}
            style={{
              background: 'var(--mf-inst-surface)',
              border: '1px solid var(--mf-inst-line-2)',
              borderRadius: 6,
              color: 'var(--mf-inst-ink)',
            }}
            type="button"
          >
            <GoogleG />
            <span>Entrar com Google</span>
          </button>
        </section>
      </main>
    </div>
  );
}