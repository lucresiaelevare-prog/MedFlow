import { useNavigate } from 'react-router-dom';
import { HeartPulse, Phone, Users } from 'lucide-react';
import IDS from '@/constants/testIds';
import api from '@/lib/api';

/**
 * MentalHealthAlertCard — clinical, sensitive, warm. Never alarmist.
 * Left rail 4px care color. Clear title + body + 3 CTAs.
 */
const MentalHealthAlertCard = ({ alert, onAck }) => {
  const navigate = useNavigate();
  const high = alert.level === 'high';

  return (
    <article
      data-testid={IDS.mentalHealth.dashboardCard}
      className="relative mf-card overflow-hidden animate-fade-in"
    >
      <span
        aria-hidden="true"
        className="absolute left-0 top-0 bottom-0 w-1"
        style={{ background: 'var(--mf-care)' }}
      />
      <div className="p-5 md:p-6 pl-6 md:pl-7">
        <div className="flex items-start gap-3">
          <span
            className="w-9 h-9 rounded-lg shrink-0 flex items-center justify-center"
            style={{ background: 'var(--mf-care-soft)', color: 'var(--mf-care)' }}
          >
            <HeartPulse strokeWidth={1.75} className="w-4 h-4" />
          </span>
          <div className="flex-1 min-w-0">
            <span className="pill pill-care">
              {high ? 'Cuidado prioritário' : 'Sinal a considerar hoje'}
            </span>
            <h3 className="mt-2 text-[18px] font-semibold text-zinc-900 tracking-tight">
              {high ? 'Você merece falar com alguém agora.' : 'Os últimos dias estão pesando.'}
            </h3>
            <p className="mt-2 text-[14px] text-zinc-600 leading-relaxed">
              {alert.message}
            </p>

            <div className="mt-4 flex flex-wrap items-center gap-2">
              <a
                href="tel:188"
                onClick={() => api.post('/support-contacts/log', { contact_slug: 'cvv', method: 'call' }).catch(() => {})}
                className="btn-primary btn-care"
                style={{ background: 'var(--mf-care)', borderColor: '#B85539' }}
              >
                <Phone strokeWidth={1.75} className="w-4 h-4" />
                Ligar CVV — 188
              </a>
              <button
                onClick={() => navigate('/support')}
                className="btn-secondary"
              >
                <Users strokeWidth={1.75} className="w-4 h-4" />
                Rede de Apoio
              </button>
              <button
                data-testid={IDS.mentalHealth.dashboardCardAck}
                onClick={onAck}
                className="btn-ghost"
              >
                Dispensar por hoje
              </button>
            </div>
          </div>
        </div>
      </div>
    </article>
  );
};

export default MentalHealthAlertCard;
