import { useEffect, useRef, useState } from 'react';
import {
  MessagesSquare, Send, Sparkles, Loader2, Zap, User2, Stethoscope, X,
} from 'lucide-react';
import api from '@/lib/api';

/**
 * Preceptor IA — chat contextualizado da Devolutiva Inteligente Med Flow™.
 *
 * O contexto (enunciado, alternativas, gabarito, devolutiva completa,
 * evidências, perfil do aluno) já vai automaticamente no system prompt
 * do backend. O aluno nunca precisa repetir.
 */

const SUGGESTIONS = [
  'Por que minha resposta estava errada?',
  'Explique isso de forma mais simples.',
  'Como diferenciar esse diagnóstico de outros parecidos?',
  'O que mudaria se o paciente apresentasse outro sintoma?',
  'Como esse tema costuma ser cobrado nas provas?',
  'Como esse caso acontece na prática clínica?',
  'Existe algum macete para nunca mais errar isso?',
  'Mostre um caso clínico semelhante.',
  'Faça um resumo em 30 segundos.',
  'Crie um mapa mental desse assunto.',
  'Faça um fluxograma da conduta.',
  'Compare essa doença com a principal diferencial.',
  'Quais exames confirmam esse diagnóstico?',
  'Qual seria a conduta segundo as diretrizes mais atuais?',
  'Quais são os principais erros dos candidatos?',
  'Me faça três perguntas para verificar se realmente aprendi.',
  'Gere uma questão semelhante com dificuldade maior.',
  'Gere uma questão mais fácil para fixação.',
  'Quais medicamentos costumam aparecer nesse tema?',
  'Quais palavras-chave deveriam ter chamado minha atenção?',
];

/**
 * Renderer simples de markdown "leve":
 * - **negrito**
 * - listas com "- " ou "• "
 * - parágrafos separados por linha em branco
 */
function renderRich(text) {
  if (!text) return null;
  const paragraphs = text.split(/\n{2,}/);
  return paragraphs.map((para, pi) => {
    const lines = para.split('\n');
    const isList = lines.every((l) => /^\s*(?:[-•*]|\d+\.)\s+/.test(l));
    if (isList && lines.length > 1) {
      return (
        <ul key={pi} className="list-disc pl-5 space-y-1.5 mb-3">
          {lines.map((l, i) => (
            <li key={i} className="text-[13.5px] leading-relaxed text-zinc-800">
              <span dangerouslySetInnerHTML={{
                __html: l.replace(/^\s*(?:[-•*]|\d+\.)\s+/, '')
                  .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>'),
              }} />
            </li>
          ))}
        </ul>
      );
    }
    return (
      <p key={pi} className="text-[13.5px] leading-relaxed text-zinc-800 mb-3 whitespace-pre-line">
        <span dangerouslySetInnerHTML={{
          __html: para.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>'),
        }} />
      </p>
    );
  });
}

// ─── CTA card (fica no fim da devolutiva) ─────────────────────
export const PreceptorCTA = ({ onOpen }) => (
  <button
    type="button"
    data-testid="preceptor-cta"
    onClick={onOpen}
    className="w-full text-left rounded-2xl p-5 md:p-6 transition-transform hover:-translate-y-0.5
      focus:outline-none focus:ring-2 focus:ring-brand/40 relative overflow-hidden"
    style={{
      background: '#1E3B32',
      color: '#fff',
      boxShadow: '0 12px 32px -12px rgba(30, 59, 50, 0.42)',
    }}
  >
    <div className="flex items-start gap-4 relative z-10">
      <span
        className="w-11 h-11 rounded-xl flex items-center justify-center shrink-0"
        style={{ background: '#39574D' }}
      >
        <Stethoscope strokeWidth={1.8} className="w-6 h-6" />
      </span>
      <div className="flex-1 min-w-0">
        <p className="text-[11.5px] uppercase tracking-widest opacity-80 font-semibold">
          <span>Análise contextual da questão</span>
        </p>
        <p className="mt-1 text-[16px] md:text-[18px] font-semibold leading-tight">
          <span>Transforme a resposta em raciocínio clínico.</span>
        </p>
        <p className="mt-1.5 text-[13.5px] leading-relaxed opacity-90 max-w-lg">
          <span>
            O Preceptor parte da questão, das alternativas e da sua devolutiva para aprofundar
            o erro, comparar hipóteses e orientar a próxima revisão.
          </span>
        </p>
        <span
          className="inline-flex items-center gap-1.5 mt-3.5 px-3 py-1.5 rounded-lg
            text-[12.5px] font-semibold"
          style={{ background: '#39574D' }}
        >
          <Sparkles className="w-3.5 h-3.5" /> <span>Abrir análise com o Preceptor</span>
        </span>
      </div>
    </div>
    <div
      className="absolute -right-10 -bottom-14 w-48 h-48 rounded-full opacity-15"
      style={{ background: 'radial-gradient(circle, rgba(255,255,255,0.3), transparent 60%)' }}
    />
  </button>
);

// ─── Painel de chat (expande abaixo da CTA) ─────────────────
export const PreceptorChat = ({ reviewId, onClose }) => {
  const [messages, setMessages] = useState([]);   // [{role, content, latency_ms, provider, cached}]
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [showSuggestions, setShowSuggestions] = useState(true);
  const bottomRef = useRef(null);

  // Carrega conversa existente (se o aluno já conversou antes sobre essa devolutiva)
  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const { data } = await api.get(`/tutor/smart-review/${reviewId}/conversation`);
        if (!alive) return;
        const msgs = (data.messages || []).map((m) => ({
          role: m.role, content: m.content,
          provider: m.provider, latency_ms: m.latency_ms,
          cached: m.cached, intent: m.intent,
        }));
        setMessages(msgs);
        if (msgs.length > 0) setShowSuggestions(false);
      } catch { /* silent */ }
    })();
    return () => { alive = false; };
  }, [reviewId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }, [messages, loading]);

  const send = async (text) => {
    const msg = (text ?? input).trim();
    if (!msg || loading) return;
    setInput('');
    setError(null);
    setShowSuggestions(false);
    const optimistic = { role: 'user', content: msg };
    setMessages((prev) => [...prev, optimistic]);
    setLoading(true);
    try {
      // Baixo consumo de tokens: enviamos APENAS a mensagem.
      // O backend recupera contexto + histórico + summary da session_memory.
      const { data } = await api.post(
        `/tutor/smart-review/${reviewId}/chat`,
        { message: msg },
        { timeout: 60_000 },
      );
      setMessages((prev) => [...prev, {
        role: 'assistant', content: data.reply,
        provider: data.provider, latency_ms: data.latency_ms,
        cached: data.cached, intent: data.intent,
      }]);
    } catch (e) {
      const detail = e?.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Não foi possível enviar a mensagem.');
    } finally {
      setLoading(false);
    }
  };

  const onKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  };

  return (
    <div
      data-testid="preceptor-chat"
      className="mf-card p-0 overflow-hidden animate-fade-in"
      style={{ borderColor: 'var(--mf-hair)' }}
    >
      {/* Header */}
      <div
        className="px-5 py-4 flex items-center justify-between"
        style={{ background: '#1E3B32', color: '#fff' }}
      >
        <div className="flex items-center gap-3">
          <span
            className="w-9 h-9 rounded-lg flex items-center justify-center"
            style={{ background: 'rgba(255,255,255,0.18)' }}
          >
            <Stethoscope strokeWidth={1.8} className="w-5 h-5" />
          </span>
          <div>
            <p className="text-[14px] font-semibold leading-tight"><span>Preceptor IA</span></p>
            <p className="text-[11.5px] opacity-80 leading-tight">
            <span>Questão, alternativas e devolutiva em contexto</span>
            </p>
          </div>
        </div>
        <button
          data-testid="preceptor-close"
          onClick={onClose}
          className="w-8 h-8 rounded-lg flex items-center justify-center transition-colors"
          style={{ background: 'rgba(255,255,255,0.15)' }}
          aria-label="Fechar chat"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Messages */}
      <div
        className="px-4 md:px-5 py-4 space-y-4 max-h-[520px] overflow-y-auto"
        data-testid="preceptor-messages"
      >
        {messages.length === 0 && (
          <div className="py-2">
            <p className="text-[13.5px] text-zinc-700 leading-relaxed">
              <span>
                <strong>Vamos aprofundar.</strong> Eu parto da questão que você trouxe, das
                alternativas e da devolutiva para explorar seu raciocínio clínico.
              </span>
            </p>
          </div>
        )}

        {messages.map((m, i) => (
          <div
            key={i}
            data-testid={`preceptor-msg-${i}`}
            data-role={m.role}
            className={`flex gap-2.5 ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            {m.role === 'assistant' && (
              <span
                className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0 mt-0.5"
                style={{ background: 'var(--mf-brand-soft)', color: 'var(--mf-brand)' }}
              >
                <Stethoscope strokeWidth={1.8} className="w-4 h-4" />
              </span>
            )}
            <div
              className={`max-w-[85%] rounded-2xl px-3.5 py-2.5 ${
                m.role === 'user' ? 'text-white' : 'bg-white hairline'
              }`}
              style={m.role === 'user' ? { background: '#1E3B32' } : {}}
            >
              {m.role === 'user'
                ? <p className="text-[13.5px] leading-relaxed whitespace-pre-line"><span>{m.content}</span></p>
                : renderRich(m.content)}
              {m.role === 'assistant' && m.latency_ms != null && (
                <p className="text-[10.5px] text-zinc-400 mt-1.5 flex items-center gap-1.5">
                  {m.cached ? (
                    <>
                      <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-md text-[9.5px] font-semibold"
                        style={{ background: 'var(--mf-success-soft, #ECFDF5)', color: 'var(--mf-success, #10B981)' }}>
                        ⚡ cache
                      </span>
                      <span>{m.latency_ms}ms</span>
                    </>
                  ) : (
                    <>
                      <Zap className="w-3 h-3" />
                      <span>{m.provider} · {m.latency_ms}ms</span>
                      {m.intent?.label && m.intent.label !== 'general' && (
                        <span className="text-zinc-300">·</span>
                      )}
                      {m.intent?.label && m.intent.label !== 'general' && (
                        <span className="opacity-60">{m.intent.label.replace('_', ' ')}</span>
                      )}
                    </>
                  )}
                </p>
              )}
            </div>
            {m.role === 'user' && (
              <span
                className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0 mt-0.5 bg-zinc-100 text-zinc-500"
              >
                <User2 strokeWidth={1.8} className="w-4 h-4" />
              </span>
            )}
          </div>
        ))}

        {loading && (
          <div className="flex gap-2.5 justify-start" data-testid="preceptor-loading">
            <span
              className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0 mt-0.5"
              style={{ background: 'var(--mf-brand-soft)', color: 'var(--mf-brand)' }}
            >
              <Stethoscope strokeWidth={1.8} className="w-4 h-4" />
            </span>
            <div className="bg-white hairline rounded-2xl px-3.5 py-3 inline-flex items-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-zinc-400 animate-bounce" style={{ animationDelay: '0ms' }} />
              <span className="w-1.5 h-1.5 rounded-full bg-zinc-400 animate-bounce" style={{ animationDelay: '150ms' }} />
              <span className="w-1.5 h-1.5 rounded-full bg-zinc-400 animate-bounce" style={{ animationDelay: '300ms' }} />
            </div>
          </div>
        )}

        {error && (
          <p className="text-[12.5px] text-center" style={{ color: 'var(--mf-care)' }}>
            <span>{error}</span>
          </p>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Suggestions strip */}
      {showSuggestions && (
        <div
          data-testid="preceptor-suggestions"
          className="px-4 md:px-5 py-3 border-t"
          style={{ borderColor: 'var(--mf-hair)', background: 'var(--mf-hair-soft, #FAFAFA)' }}
        >
          <p className="eyebrow mb-2 flex items-center gap-1.5">
            <Sparkles className="w-3 h-3" style={{ color: 'var(--mf-brand)' }} />
            <span>você pode perguntar, por exemplo</span>
          </p>
          <div className="flex gap-2 overflow-x-auto pb-1 -mx-1 px-1">
            {SUGGESTIONS.map((s, i) => (
              <button
                key={i}
                data-testid={`preceptor-suggestion-${i}`}
                type="button"
                onClick={() => send(s)}
                disabled={loading}
                className="shrink-0 px-3 py-1.5 rounded-full text-[12px] text-zinc-700 bg-white hairline hover:bg-zinc-50 transition-colors"
              >
                <span>{s}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Input */}
      <div
        className="p-3 md:p-4 border-t"
        style={{ borderColor: 'var(--mf-hair)' }}
      >
        <div className="flex items-end gap-2">
          <textarea
            data-testid="preceptor-input"
            rows={1}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={onKey}
            placeholder="Pergunte ao Preceptor sobre esta questão…"
            className="flex-1 resize-none px-3.5 py-2.5 rounded-lg text-[13.5px] hairline bg-white focus:outline-none focus:ring-2 focus:ring-brand/40 placeholder:text-zinc-400"
            style={{ maxHeight: '120px', minHeight: '42px' }}
          />
          <button
            data-testid="preceptor-send"
            type="button"
            onClick={() => send()}
            disabled={loading || !input.trim()}
            className="btn-primary shrink-0"
            aria-label="Enviar"
          >
            {loading
              ? <Loader2 className="w-4 h-4 animate-spin" />
              : <Send className="w-4 h-4" />}
          </button>
        </div>
        {!showSuggestions && (
          <button
            type="button"
            onClick={() => setShowSuggestions(true)}
            className="mt-2 text-[11.5px] text-zinc-500 hover:text-zinc-700 inline-flex items-center gap-1"
            data-testid="preceptor-show-suggestions"
          >
            <Sparkles className="w-3 h-3" /> <span>ver sugestões novamente</span>
          </button>
        )}
      </div>
    </div>
  );
};

export default PreceptorChat;
