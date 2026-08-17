import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import "@/index.css";
import App from "@/App";
import { installGlobalErrorHandlers } from "@/lib/telemetry";
import { Sentry, sentryEnabled } from "@/lib/sentry";

// Captura global de erros — promises rejeitadas + throws de window.
// Complementa <SafeRender> (que só pega erros de render).
installGlobalErrorHandlers();

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 60_000,
      refetchOnWindowFocus: false,
    },
  },
});

const rootOptions = sentryEnabled
  ? {
      onCaughtError: Sentry.reactErrorHandler(),
      onRecoverableError: Sentry.reactErrorHandler(),
      onUncaughtError: Sentry.reactErrorHandler(),
    }
  : undefined;

const root = ReactDOM.createRoot(document.getElementById("root"), rootOptions);
root.render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      {sentryEnabled ? (
        <Sentry.ErrorBoundary
          fallback={
            <main
              className="flex min-h-screen items-center justify-center p-6 text-center"
              data-testid="sentry-error-fallback"
            >
              <div>
                <h1 className="text-xl font-semibold">Não foi possível carregar esta tela.</h1>
                <p className="mt-2 text-sm text-zinc-600">Atualize a página e tente novamente.</p>
              </div>
            </main>
          }
        >
          <App />
        </Sentry.ErrorBoundary>
      ) : (
        <App />
      )}
    </QueryClientProvider>
  </React.StrictMode>,
);

// Registro discreto do Service Worker para cache offline (também usado para push).
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js', { scope: '/' }).catch(() => { /* silent */ });
  });
}
