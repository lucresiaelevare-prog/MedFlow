import { HeartPulse, Phone, LifeBuoy, X, AlertTriangle } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import api from '@/lib/api';
import IDS from '@/constants/testIds';

/**
 * Empathetic overlay shown after a check-in whenever the backend returned a
 * mental_health_alert. High severity gets terracotta + CVV/SAMU. Medium gets
 * sage + CVV/CAPS/mapa. Never blocks the user — dismiss goes to /dashboard.
 */
const MentalHealthAlertOverlay = ({ alert, onDismiss }) => {
  const navigate = useNavigate();
  if (!alert) return null;
  const high = alert.level === 'high';
  const accent = high ? 'terracotta' : 'sage';

  const logAndClose = async (method, contactSlug, target) => {
    try {
      if (contactSlug && method) {
        await api.post('/support-contacts/log', { contact_slug: contactSlug, method });
      }
    } catch (e) { /* non-blocking */ }
    if (target === 'call-cvv') window.location.href = 'tel:188';
    else if (target === 'call-samu') window.location.href = 'tel:192';
    else if (target === 'support') navigate('/support');
    else if (target === 'dismiss') onDismiss?.();
  };

  return (
    <div
      data-testid={IDS.mentalHealth.overlay}
      className="fixed inset-0 z-50 flex items-center justify-center px-4 py-6 bg-stone-900/50 backdrop-blur-sm animate-fade-in"
      role="dialog"
      aria-modal="true"
    >
      <div className={`relative w-full max-w-md bg-white rounded-3xl p-6 md:p-8 shadow-[0_20px_60px_rgba(28,33,31,0.3)] border ${
        high ? 'border-terracotta-200' : 'border-sage-200'
      }`}>
        <button
          data-testid={IDS.mentalHealth.overlayDismiss}
          onClick={() => logAndClose(null, null, 'dismiss')}
          className="absolute top-4 right-4 w-8 h-8 rounded-full bg-stone-100 hover:bg-stone-200 flex items-center justify-center text-stone-500"
          aria-label="Fechar"
        >
          <X className="w-4 h-4" />
        </button>

        <div className={`w-14 h-14 rounded-2xl flex items-center justify-center ${
          high ? 'bg-terracotta-500 text-white' : 'bg-sage-600 text-white'
        }`}>
          {high ? <AlertTriangle className="w-7 h-7" /> : <HeartPulse className="w-7 h-7" />}
        </div>

        <p className={`mt-5 text-xs uppercase tracking-widest font-semibold text-${accent}-700`}>
          {high ? 'Você não precisa segurar isso sozinho' : 'Um sinal que merece cuidado'}
        </p>
        <h2 className="mt-1 font-display text-2xl md:text-3xl text-stone-900 leading-tight">
          A gente pode dar uma pausa aqui?
        </h2>
        <p className="mt-3 text-stone-600 leading-relaxed">
          {alert.message}
        </p>

        <div className="mt-6 space-y-2.5">
          {high && (
            <button
              data-testid={IDS.mentalHealth.overlayCallCvv}
              onClick={() => logAndClose('call', 'cvv', 'call-cvv')}
              className="w-full bg-terracotta-600 hover:bg-terracotta-700 text-white rounded-full py-3.5 font-medium flex items-center justify-center gap-2"
            >
              <Phone className="w-4 h-4" /> Ligar CVV 188 (24h, sigiloso)
            </button>
          )}
          {high && (
            <button
              data-testid={IDS.mentalHealth.overlayCallSamu}
              onClick={() => logAndClose('call', 'samu', 'call-samu')}
              className="w-full bg-white border-2 border-terracotta-300 hover:bg-terracotta-50 text-terracotta-700 rounded-full py-3 font-medium flex items-center justify-center gap-2"
            >
              <Phone className="w-4 h-4" /> Emergência médica — SAMU 192
            </button>
          )}
          {!high && (
            <button
              data-testid={IDS.mentalHealth.overlayCallCvv}
              onClick={() => logAndClose('call', 'cvv', 'call-cvv')}
              className="w-full bg-sage-600 hover:bg-sage-700 text-white rounded-full py-3.5 font-medium flex items-center justify-center gap-2"
            >
              <Phone className="w-4 h-4" /> Ligar CVV 188
            </button>
          )}
          <button
            data-testid={IDS.mentalHealth.overlaySeeSupport}
            onClick={() => logAndClose(null, null, 'support')}
            className="w-full bg-stone-100 hover:bg-stone-200 text-stone-800 rounded-full py-3 font-medium flex items-center justify-center gap-2"
          >
            <LifeBuoy className="w-4 h-4" /> Ver toda a Rede de Apoio
          </button>
          <button
            onClick={() => logAndClose(null, null, 'dismiss')}
            className="w-full text-stone-500 hover:text-stone-800 text-sm py-2"
          >
            Agora só quero continuar
          </button>
        </div>

        <p className="mt-5 text-[11px] text-stone-500 leading-relaxed">
          O MedFlow não é diagnóstico. Estes canais são gratuitos, anônimos e feitos para receber você. Seus dados ficam seguros · LGPD.
        </p>
      </div>
    </div>
  );
};

export default MentalHealthAlertOverlay;
