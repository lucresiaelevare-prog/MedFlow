import { useState } from 'react';
import { Brain, Check } from 'lucide-react';
import api from '@/lib/api';

const levels = [
  ['Muito inseguro', 1],
  ['Inseguro', 2],
  ['Neutro', 3],
  ['Confiante', 4],
  ['Muito confiante', 5],
];

const ConfidencePrompt = ({ reviewId }) => {
  const [selected, setSelected] = useState(null);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState('');
  const submit = async (level) => {
    setSelected(level);
    setError('');
    try {
      await api.post('/learning/confidence', {
        context_id: reviewId,
        context_type: 'smart_review',
        confidence_level: level,
        idempotency_key: `review-${reviewId}-${level}`,
      });
      setSaved(true);
    } catch (requestError) {
      setError('Não foi possível registrar sua percepção agora.');
    }
  };
  return <section className="mt-6 rounded-xl border border-violet-100 bg-violet-50/40 p-4" data-testid="confidence-shadow-prompt"><div className="flex gap-2.5"><Brain className="mt-0.5 h-4 w-4 shrink-0 text-violet-600" /><div><p className="text-sm font-semibold text-slate-900">Como você se sente neste assunto?</p><p className="mt-1 text-xs leading-relaxed text-slate-600">Sua resposta será usada apenas para observação. Ela não altera seu plano nem suas recomendações.</p></div></div>{saved ? <p className="mt-4 inline-flex items-center gap-2 text-sm text-emerald-700"><Check className="h-4 w-4" />Percepção registrada.</p> : <div className="mt-4 flex flex-wrap gap-2">{levels.map(([label, value]) => <button key={value} type="button" onClick={() => submit(value)} data-testid={`confidence-level-${value}`} className={`border px-3 py-2 text-xs transition-colors ${selected === value ? 'border-violet-600 bg-violet-600 text-white' : 'border-violet-200 bg-white text-slate-700 hover:border-violet-400'}`}>{label}</button>)}</div>}{error && <p className="mt-3 text-xs text-rose-700" data-testid="confidence-shadow-error">{error}</p>}</section>;
};

export default ConfidencePrompt;