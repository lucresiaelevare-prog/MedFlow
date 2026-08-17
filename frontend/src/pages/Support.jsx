import { useEffect, useState } from 'react';
import {
  Phone, MessageCircle, ExternalLink, ShieldCheck, HeartPulse, Loader2, LifeBuoy, Send,
} from 'lucide-react';
import Shell from '@/components/Shell';
import api from '@/lib/api';
import IDS from '@/constants/testIds';

const KIND_META = {
  prevencao_suicidio:      { label: 'Prevenção do suicídio' },
  emergencia:              { label: 'Emergência médica' },
  saude_mental_publica:    { label: 'Saúde mental pública' },
  saude_mental_gratuita:   { label: 'Atendimento gratuito' },
  estudante_medicina:      { label: 'Estudantes de Medicina' },
  universitario:           { label: 'Sua universidade' },
};

const Support = () => {
  const [contacts, setContacts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [question, setQuestion] = useState('');
  const [allowPublic, setAllowPublic] = useState(false);
  const [questionState, setQuestionState] = useState('');

  useEffect(() => {
    (async () => {
      try {
        const { data } = await api.get('/support-contacts');
        setContacts(data.contacts || []);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const log = async (slug, method) => {
    try {
      await api.post('/support-contacts/log', { contact_slug: slug, method });
    } catch (e) { /* ignore */ }
  };

  const submitQuestion = async (event) => {
    event.preventDefault();
    setQuestionState('');
    try {
      await api.post('/questions', {
        message: question,
        allow_anonymous_publication: allowPublic,
      });
      setQuestion('');
      setAllowPublic(false);
      setQuestionState('Sua dúvida foi enviada ao plantão.');
    } catch (error) {
      setQuestionState('Não foi possível enviar sua dúvida agora.');
    }
  };

  const priority = contacts.filter((c) => c.priority);
  const others = contacts.filter((c) => !c.priority);

  return (
    <Shell>
      <div
        data-testid={IDS.support.root}
        className="max-w-3xl mx-auto px-5 md:px-8 pt-6 md:pt-8 animate-fade-in"
      >
        <header className="mb-6">
          <p className="eyebrow">Você não está sozinho</p>
          <h1 className="mt-1.5 text-[26px] md:text-[30px] font-semibold text-zinc-900 tracking-tight">
            Rede de apoio
          </h1>
          <p className="mt-2 text-[14.5px] text-zinc-600 leading-relaxed max-w-2xl">
            Se hoje está pesado, buscar ajuda é um sinal de força. Estes canais são gratuitos, sigilosos e feitos para receber você.
          </p>
        </header>

        {loading && (
          <div className="mf-card p-10 flex justify-center">
            <Loader2 className="w-5 h-5 text-brand animate-spin" strokeWidth={1.75} />
          </div>
        )}

        {priority.length > 0 && (
          <section className="mb-6">
            <div className="flex items-center gap-2 mb-3">
              <HeartPulse strokeWidth={1.75} className="w-4 h-4 text-care" />
              <p className="eyebrow" style={{ color: 'var(--mf-care)' }}>Se é urgente</p>
            </div>
            <div className="space-y-3">
              {priority.map((c) => (
                <ContactCard key={c.slug} contact={c} priority onAction={log} />
              ))}
            </div>
          </section>
        )}

        {others.length > 0 && (
          <section className="mb-6">
            <div className="flex items-center gap-2 mb-3">
              <LifeBuoy strokeWidth={1.75} className="w-4 h-4 text-brand" />
              <p className="eyebrow" style={{ color: 'var(--mf-brand)' }}>Cuidado contínuo</p>
            </div>
            <div className="space-y-3">
              {others.map((c) => (
                <ContactCard key={c.slug} contact={c} onAction={log} />
              ))}
            </div>
          </section>
        )}

        <section className="mf-card p-5 md:p-6 mb-6" data-testid="student-question-form">
          <div className="flex items-start gap-3">
            <MessageCircle strokeWidth={1.75} className="w-4 h-4 text-brand shrink-0 mt-0.5" />
            <div className="flex-1">
              <p className="eyebrow">Plantão de dúvidas</p>
              <h2 className="mt-1 text-[18px] font-semibold text-zinc-900">Envie sua dúvida</h2>
              <p className="mt-1 text-[13px] text-zinc-600 leading-relaxed">
                A resposta chegará pelo MedFlow. Você decide se ela pode virar uma dúvida pública anônima.
              </p>
              <form onSubmit={submitQuestion} className="mt-4 space-y-3">
                <textarea
                  required
                  value={question}
                  onChange={(event) => setQuestion(event.target.value)}
                  placeholder="Escreva sua dúvida"
                  data-testid="student-question-input"
                  className="w-full min-h-24 border border-zinc-200 bg-white p-3 text-[14px] text-zinc-800 outline-none focus:border-brand"
                />
                <label className="flex items-start gap-2 text-[12px] text-zinc-600">
                  <input
                    type="checkbox"
                    checked={allowPublic}
                    onChange={(event) => setAllowPublic(event.target.checked)}
                    data-testid="student-question-public-consent"
                    className="mt-0.5"
                  />
                  Autorizo publicar esta dúvida de forma anônima, sem meu nome ou e-mail.
                </label>
                <button type="submit" data-testid="student-question-submit" className="btn-primary">
                  <Send strokeWidth={1.75} className="w-4 h-4" />
                  Enviar dúvida
                </button>
                {questionState && <p data-testid="student-question-status" className="text-[12px] text-zinc-600">{questionState}</p>}
              </form>
            </div>
          </div>
        </section>

        <div className="mf-card p-5 flex items-start gap-3 mb-6" style={{ background: 'var(--mf-brand-soft)', borderColor: 'transparent' }}>
          <ShieldCheck strokeWidth={1.75} className="w-4 h-4 text-brand shrink-0 mt-0.5" />
          <div>
            <h3 className="text-[14px] font-semibold text-zinc-900">Confidencial e anônimo</h3>
            <p className="mt-1 text-[13px] text-zinc-600 leading-relaxed">
              O MedFlow não compartilha o que você faz aqui. Registramos apenas um contador anônimo do canal que foi útil, para melhorar a rede. Nada mais.
            </p>
          </div>
        </div>

        <p className="text-center text-[12px] text-zinc-500 pb-6 leading-relaxed">
          Esta página não substitui aconselhamento médico. Em caso de risco imediato, ligue 192 (SAMU).
        </p>
      </div>
    </Shell>
  );
};

const ContactCard = ({ contact, priority, onAction }) => {
  const meta = KIND_META[contact.kind] || { label: contact.kind };
  const accent = priority ? 'var(--mf-care)' : 'var(--mf-brand)';
  const softBg = priority ? 'var(--mf-care-soft)' : 'var(--mf-brand-soft)';

  return (
    <article
      data-testid={IDS.support.item(contact.slug)}
      className="mf-card relative overflow-hidden"
    >
      {priority && (
        <span aria-hidden="true" className="absolute left-0 top-0 bottom-0 w-1" style={{ background: accent }} />
      )}
      <div className={`p-5 md:p-6 ${priority ? 'pl-6 md:pl-7' : ''}`}>
        <div className="flex items-start gap-3">
          <span
            className="w-10 h-10 rounded-lg shrink-0 flex items-center justify-center"
            style={{ background: softBg, color: accent }}
          >
            {contact.phone ? <Phone strokeWidth={1.75} className="w-4 h-4" /> : <HeartPulse strokeWidth={1.75} className="w-4 h-4" />}
          </span>
          <div className="flex-1 min-w-0">
            <p className="eyebrow-mono" style={{ color: accent }}>{meta.label}</p>
            <h3 className="mt-1 text-[17px] font-semibold text-zinc-900 tracking-tight leading-snug">{contact.name}</h3>
            <p className="mt-1.5 text-[13.5px] text-zinc-600 leading-relaxed">{contact.description}</p>
            {contact.hours && (
              <p className="mt-2 text-[12px] text-zinc-500">
                <span className="font-semibold text-zinc-700">Atendimento:</span> {contact.hours}
              </p>
            )}

            <div className="mt-4 flex flex-wrap gap-2">
              {contact.phone && (
                <a
                  data-testid={IDS.support.call(contact.slug)}
                  href={`tel:${contact.phone}`}
                  onClick={() => onAction(contact.slug, 'call')}
                  className="btn-primary"
                  style={priority ? { background: 'var(--mf-care)', borderColor: '#B85539' } : {}}
                >
                  <Phone strokeWidth={1.75} className="w-4 h-4" />
                  Ligar {contact.phone_display || contact.phone}
                </a>
              )}
              {contact.chat_url && (
                <a
                  data-testid={IDS.support.chat(contact.slug)}
                  href={contact.chat_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  onClick={() => onAction(contact.slug, 'chat')}
                  className="btn-secondary"
                >
                  <MessageCircle strokeWidth={1.75} className="w-4 h-4" />
                  Chat online
                </a>
              )}
              {contact.url && (
                <a
                  data-testid={IDS.support.link(contact.slug)}
                  href={contact.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  onClick={() => onAction(contact.slug, 'link')}
                  className="btn-secondary"
                >
                  <ExternalLink strokeWidth={1.75} className="w-4 h-4" />
                  Abrir site
                </a>
              )}
              {contact.email && (
                <a
                  href={`mailto:${contact.email}`}
                  onClick={() => onAction(contact.slug, 'link')}
                  className="btn-secondary"
                >
                  {contact.email}
                </a>
              )}
            </div>
          </div>
        </div>
      </div>
    </article>
  );
};

export default Support;
