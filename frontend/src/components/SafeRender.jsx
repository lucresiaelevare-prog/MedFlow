import React from 'react';
import { AlertTriangle, RotateCcw, Home, Send } from 'lucide-react';
import { sendTelemetry } from '@/lib/telemetry';

/**
 * SafeRender — ErrorBoundary + telemetria + fallback controlado.
 *
 * Regras (ver /app/docs/frontend-rules.md #6, #7):
 * - Nunca reload automático (evita loop infinito).
 * - Fallback com 3 ações explícitas: Recarregar / Voltar / Reportar.
 * - Telemetria fire-and-forget via lib/telemetry (com deduplicação).
 * - Prop `name` identifica a tela nos logs.
 */

const REACT_VERSION = React.version;

class SafeRender extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, reported: false, sending: false };
  }

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error, info) {
    const payload = {
      component: this.props.name || 'unknown',
      route: (typeof window !== 'undefined' && window.location) ? window.location.pathname : '',
      message: String(error?.message || error || 'unknown error'),
      stack: String(error?.stack || '').slice(0, 4000),
      component_stack: String(info?.componentStack || '').slice(0, 2000),
      user_agent: (typeof navigator !== 'undefined') ? navigator.userAgent : '',
      react_version: REACT_VERSION,
      timestamp: new Date().toISOString(),
    };
    sendTelemetry(payload);
    // eslint-disable-next-line no-console
    console.error(`[SafeRender:${this.props.name || 'unknown'}]`, error);
  }

  handleReport = () => {
    if (this.state.sending || this.state.reported) return;
    this.setState({ sending: true });
    // Segundo envio marcado como user-triggered (útil pra filtrar noise)
    sendTelemetry({
      component: this.props.name || 'unknown',
      route: window.location.pathname,
      user_reported: true,
      timestamp: new Date().toISOString(),
    });
    setTimeout(() => this.setState({ reported: true, sending: false }), 350);
  };

  render() {
    if (!this.state.hasError) return this.props.children;

    const { name = 'esta tela' } = this.props;
    return (
      <div
        data-testid={`safe-render-fallback-${name}`}
        data-component={name}
        className="min-h-screen flex items-center justify-center px-5 py-12"
        style={{ background: 'var(--mf-canvas, #FAFAF9)' }}
        translate="no"
      >
        <div className="w-full max-w-md">
          <div
            className="w-12 h-12 rounded-xl flex items-center justify-center mb-6"
            style={{ background: 'var(--mf-brand-soft, #FFF7ED)' }}
          >
            <AlertTriangle strokeWidth={1.5} className="w-6 h-6" style={{ color: 'var(--mf-brand, #DC6B4C)' }} />
          </div>

          <p className="text-[11px] uppercase tracking-wider text-zinc-400 font-medium">
            <span>algo estranho aconteceu</span>
          </p>
          <h1 className="mt-2 text-[24px] md:text-[26px] font-semibold text-zinc-900 tracking-tight leading-tight">
            <span>Não conseguimos renderizar {name}.</span>
          </h1>
          <p className="mt-3 text-[14px] text-zinc-500 leading-relaxed">
            <span>
              Um erro inesperado apareceu. Já registramos aqui pra investigar. Você pode
              tentar de novo, voltar para o início ou reportar pra gente.
            </span>
          </p>

          <div className="mt-8 grid gap-2.5">
            <button
              data-testid="safe-render-reload"
              onClick={() => window.location.reload()}
              className="btn-primary rounded-xl px-5 py-3 text-[14px] inline-flex items-center justify-center gap-2"
            >
              <RotateCcw strokeWidth={2} className="w-4 h-4" />
              <span>Recarregar</span>
            </button>
            <button
              data-testid="safe-render-home"
              onClick={() => { window.location.href = '/'; }}
              className="rounded-xl px-5 py-3 text-[14px] w-full text-zinc-800 hairline hover:bg-zinc-50 transition-colors inline-flex items-center justify-center gap-2"
            >
              <Home strokeWidth={1.75} className="w-4 h-4" />
              <span>Voltar para o início</span>
            </button>
            <button
              data-testid="safe-render-report"
              onClick={this.handleReport}
              disabled={this.state.sending || this.state.reported}
              className="rounded-xl px-5 py-3 text-[13.5px] w-full text-zinc-500 hover:text-zinc-800 transition-colors inline-flex items-center justify-center gap-2 disabled:opacity-60"
            >
              <Send strokeWidth={1.75} className="w-4 h-4" />
              <span>
                {this.state.reported ? 'Reporte enviado, obrigado.' : this.state.sending ? 'Enviando…' : 'Reportar problema'}
              </span>
            </button>
          </div>
        </div>
      </div>
    );
  }
}

export default SafeRender;
