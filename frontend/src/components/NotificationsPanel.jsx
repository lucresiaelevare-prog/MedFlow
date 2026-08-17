import { useEffect, useState } from 'react';
import { Bell, BellOff, Loader2, CheckCircle2, ArrowRight, TrendingUp } from 'lucide-react';
import api from '@/lib/api';
import {
  isPushSupported, getPermission, enablePush, disablePush,
  currentSubscription, sendTestPush, isPushPromptEnabled,
} from '@/lib/push';

const EVENT_LABELS = [
  { key: 'checkin',       label: 'Lembretes de check-in',           desc: 'Um pequeno lembrete de manhã e à noite, no seu fuso.' },
  { key: 'missions',      label: 'Ação pendente ao fim do dia',     desc: 'Um empurrão suave às 19h, quando sobra tempo curto.' },
  { key: 'exams',         label: 'Prova em 24h e 3 dias',           desc: 'Aviso a tempo de ativar o modo Prova.' },
  { key: 'mental_health', label: 'Aviso de saúde mental',           desc: 'Um toque cuidadoso, sem julgamento, quando pode ajudar.' },
  { key: 'streak',        label: 'Sequência em risco',              desc: 'Só quando fizer sentido. Nunca em excesso.' },
  { key: 'digest',        label: 'Resumo semanal',                  desc: 'Domingo, às 18h. Os padrões da sua semana.' },
];

const HOURS = [5, 6, 7, 8, 9, 10, 11];

const NotificationsPanel = () => {
  const [supported, setSupported] = useState(true);
  const [permission, setPermission] = useState('default');
  const [subscribed, setSubscribed] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [prefs, setPrefs] = useState({});
  const [enabled, setEnabled] = useState(false);
  const [wakeHour, setWakeHour] = useState(8);
  const [examLead, setExamLead] = useState(3);
  const [stats, setStats] = useState(null);
  const [status, setStatus] = useState('');
  const [error, setError] = useState('');

  const refresh = async () => {
    setLoading(true);
    setError('');
    try {
      const sup = isPushSupported();
      setSupported(sup);
      setPermission(getPermission());
      const sub = sup ? await currentSubscription() : null;
      setSubscribed(!!sub);
      const [{ data }, { data: st }] = await Promise.all([
        api.get('/push/preferences'),
        api.get('/push/stats').catch(() => ({ data: null })),
      ]);
      setPrefs(data.preferences || {});
      setEnabled(!!data.notifications_enabled);
      setWakeHour(data.wake_hour ?? 8);
      setExamLead(data.exam_alert_lead_days ?? 3);
      setStats(st);
    } catch (e) {
      setError('Não foi possível carregar as preferências.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { refresh(); }, []);

  const handleEnable = async () => {
    setBusy(true); setError(''); setStatus('');
    try {
      await enablePush();
      await api.patch('/push/preferences', { notifications_enabled: true });
      setStatus('Notificações ativadas.');
      await refresh();
    } catch (e) {
      setError(e?.message || 'Não foi possível ativar as notificações.');
    } finally { setBusy(false); }
  };

  const handleDisable = async () => {
    setBusy(true); setError(''); setStatus('');
    try {
      await disablePush();
      await api.patch('/push/preferences', { notifications_enabled: false });
      setStatus('Notificações desativadas.');
      await refresh();
    } catch (e) {
      setError('Não foi possível desativar.');
    } finally { setBusy(false); }
  };

  const togglePref = async (key, value) => {
    setPrefs((p) => ({ ...p, [key]: value }));
    try {
      const { data } = await api.patch('/push/preferences', { [key]: value });
      setPrefs(data.preferences || {});
    } catch (e) {
      setError('Não consegui salvar essa preferência.');
      refresh();
    }
  };

  const patchScalar = async (payload, rollback) => {
    try {
      const { data } = await api.patch('/push/preferences', payload);
      setWakeHour(data.wake_hour ?? wakeHour);
      setExamLead(data.exam_alert_lead_days ?? examLead);
    } catch (e) {
      setError('Não consegui salvar.');
      rollback?.();
    }
  };

  const handleTest = async () => {
    setBusy(true); setError(''); setStatus('');
    try {
      const r = await sendTestPush();
      setStatus(r.sent > 0 ? `Aviso enviado (${r.sent}).` : 'Sem inscrições ativas para receber o teste.');
      try {
        const { data: st } = await api.get('/push/stats');
        setStats(st);
      } catch (_) { /* ignore */ }
    } catch (e) {
      setError('Não consegui disparar o teste.');
    } finally { setBusy(false); }
  };

  if (loading) {
    return (
      <section className="mf-card p-5 flex items-center gap-3 text-zinc-500">
        <Loader2 className="w-4 h-4 animate-spin" strokeWidth={1.75} />
        <span className="text-[13.5px]">Carregando notificações…</span>
      </section>
    );
  }

  const active = enabled && subscribed && permission === 'granted';
  const promptEnabled = isPushPromptEnabled();

  return (
    <section data-testid="notif-panel" className="mf-card p-5 md:p-6">
      <header className="flex items-start gap-3">
        <span
          className={`w-10 h-10 rounded-lg flex items-center justify-center shrink-0`}
          style={{
            background: active ? 'var(--mf-brand-soft)' : 'var(--mf-surface)',
            color: active ? 'var(--mf-brand)' : 'var(--mf-muted)',
          }}
        >
          {active
            ? <Bell strokeWidth={1.75} className="w-4 h-4" />
            : <BellOff strokeWidth={1.75} className="w-4 h-4" />}
        </span>
        <div className="flex-1 min-w-0">
          <p className="eyebrow">Notificações</p>
          <h3 className="mt-1 text-[16px] font-semibold text-zinc-900 tracking-tight">
            {active ? 'Ativadas' : 'Desativadas'}
          </h3>
          <p className="mt-1 text-[13px] text-zinc-500 leading-relaxed">
            {!promptEnabled
              ? 'Seu Mentor Inteligente está a caminho. Em breve, o MedFlow poderá te avisar quando chegar a hora da revisão, quando houver risco de esquecimento e quando seu plano mudar automaticamente.'
              : supported
              ? 'Lembretes suaves nos momentos que importam, respeitando seu fuso e evitando excessos.'
              : 'Seu navegador não suporta notificações web. Continue usando pelo app.'}
          </p>
        </div>
        {promptEnabled && supported && !active && (
          <button
            data-testid="notif-enable-btn"
            onClick={handleEnable}
            disabled={busy || permission === 'denied'}
            className="btn-primary disabled:opacity-60"
          >
            {busy ? <Loader2 className="w-4 h-4 animate-spin" strokeWidth={1.75} /> : <ArrowRight strokeWidth={1.75} className="w-4 h-4" />}
            {permission === 'denied' ? 'Bloqueado' : 'Ativar'}
          </button>
        )}
        {promptEnabled && supported && active && (
          <button
            data-testid="notif-disable-btn"
            onClick={handleDisable}
            disabled={busy}
            className="btn-ghost"
          >
            Desativar
          </button>
        )}
      </header>

      {(stats?.delivered_total > 0 || active) && (
        <div
          data-testid="notif-stats"
          className="mt-4 hairline rounded-lg px-4 py-3 flex items-center gap-3"
          style={{ background: 'var(--mf-surface)' }}
        >
          <TrendingUp strokeWidth={1.75} className="w-4 h-4 text-brand shrink-0" />
          <div className="flex-1 min-w-0">
            <div className="text-[13px] text-zinc-800 font-medium">
              <span data-testid="notif-delivered-count" className="mono text-zinc-900 font-semibold">
                {stats?.delivered_total ?? 0}
              </span>{' '}
              {(stats?.delivered_total ?? 0) === 1 ? 'notificação entregue' : 'notificações entregues'}
            </div>
            {stats?.last_delivered?.title && (
              <div className="text-[11px] text-zinc-500 truncate mt-0.5">
                Última: {stats.last_delivered.title}
              </div>
            )}
          </div>
        </div>
      )}

      {promptEnabled && permission === 'denied' && (
        <p className="mt-4 text-[12.5px] text-care rounded-lg px-4 py-3" style={{ background: 'var(--mf-care-soft)' }}>
          O navegador bloqueou notificações. Ajuste no cadeado da URL para reativar.
        </p>
      )}
      {error && <p className="mt-4 text-[12.5px] text-care">{error}</p>}
      {status && (
        <p className="mt-4 text-[12.5px] text-success flex items-center gap-1.5">
          <CheckCircle2 strokeWidth={1.75} className="w-4 h-4" /> {status}
        </p>
      )}

      {active && (
        <>
          <div className="mt-5 pt-5 hairline-t space-y-3">
            {EVENT_LABELS.map((row) => (
              <label
                key={row.key}
                data-testid={`notif-pref-${row.key}`}
                className="flex items-start gap-3 py-1.5 cursor-pointer"
              >
                <input
                  type="checkbox"
                  className="mt-1 w-4 h-4 cursor-pointer"
                  style={{ accentColor: 'var(--mf-brand)' }}
                  checked={prefs[row.key] !== false}
                  onChange={(e) => togglePref(row.key, e.target.checked)}
                />
                <div className="flex-1 min-w-0">
                  <div className="text-[13.5px] font-semibold text-zinc-900">{row.label}</div>
                  <div className="text-[12px] text-zinc-500 leading-snug">{row.desc}</div>
                </div>
              </label>
            ))}
          </div>

          <div className="mt-4 pt-4 hairline-t space-y-2.5">
            <div className="flex items-center justify-between">
              <span className="text-[13px] font-semibold text-zinc-800">Horário de acordar</span>
              <span data-testid="notif-wake-hour" className="text-[12px] text-zinc-500">
                <span className="mono text-zinc-700">{wakeHour}h</span> no seu fuso
              </span>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {HOURS.map((h) => (
                <button
                  key={h}
                  data-testid={`notif-wake-${h}`}
                  onClick={() => {
                    const prev = wakeHour;
                    setWakeHour(h);
                    patchScalar({ wake_hour: h }, () => setWakeHour(prev));
                  }}
                  className={`min-w-[42px] py-1.5 rounded-lg text-[12px] font-semibold hairline transition-colors ${
                    wakeHour === h ? 'text-white' : 'text-zinc-700 hover:bg-zinc-50'
                  }`}
                  style={wakeHour === h
                    ? { background: 'var(--mf-brand)', borderColor: 'var(--mf-brand-hov)' }
                    : { background: 'var(--mf-canvas)' }}
                >
                  {h}h
                </button>
              ))}
            </div>
          </div>

          <div className="mt-4 pt-4 hairline-t space-y-2.5">
            <span className="text-[13px] font-semibold text-zinc-800">Antecedência dos avisos de prova</span>
            <div className="grid grid-cols-2 gap-2">
              <button
                data-testid="notif-exam-3d"
                onClick={() => {
                  const prev = examLead;
                  setExamLead(3);
                  patchScalar({ exam_alert_lead_days: 3 }, () => setExamLead(prev));
                }}
                className={`py-2 rounded-lg text-[13px] font-semibold hairline transition-colors ${
                  examLead === 3 ? 'text-white' : 'text-zinc-700 hover:bg-zinc-50'
                }`}
                style={examLead === 3
                  ? { background: 'var(--mf-brand)', borderColor: 'var(--mf-brand-hov)' }
                  : { background: 'var(--mf-canvas)' }}
              >
                3 dias + 24h
              </button>
              <button
                data-testid="notif-exam-1d"
                onClick={() => {
                  const prev = examLead;
                  setExamLead(1);
                  patchScalar({ exam_alert_lead_days: 1 }, () => setExamLead(prev));
                }}
                className={`py-2 rounded-lg text-[13px] font-semibold hairline transition-colors ${
                  examLead === 1 ? 'text-white' : 'text-zinc-700 hover:bg-zinc-50'
                }`}
                style={examLead === 1
                  ? { background: 'var(--mf-brand)', borderColor: 'var(--mf-brand-hov)' }
                  : { background: 'var(--mf-canvas)' }}
              >
                Só na véspera
              </button>
            </div>
          </div>

          <div className="mt-4 pt-4 hairline-t flex items-center justify-between">
            <p className="text-[12px] text-zinc-500">
              Fuso detectado: <span className="text-zinc-800 font-medium">{Intl.DateTimeFormat().resolvedOptions().timeZone}</span>
            </p>
            <button
              data-testid="notif-test-btn"
              onClick={handleTest}
              disabled={busy}
              className="btn-ghost"
            >
              Enviar teste
            </button>
          </div>
        </>
      )}
    </section>
  );
};

export default NotificationsPanel;
