import { useEffect, useState } from 'react';
import { Eye, EyeOff, Loader2, Save, Send, ShieldAlert } from 'lucide-react';
import api from '@/lib/api';

const contentTypes = [
  ['course', 'Curso'],
  ['module', 'Módulo'],
  ['lesson', 'Aula'],
  ['simulation', 'Simulado'],
  ['pdf', 'PDF'],
];

export const ContentManager = () => {
  const [data, setData] = useState(null);
  const [form, setForm] = useState({ title: '', content_type: 'lesson', url: '', parent_title: '' });

  const load = async () => setData((await api.get('/admin/business/content')).data);
  useEffect(() => { load(); }, []);

  const create = async (event) => {
    event.preventDefault();
    await api.post('/admin/business/content', { ...form, published: true });
    setForm({ title: '', content_type: 'lesson', url: '', parent_title: '' });
    load();
  };

  const visibility = async (item) => {
    await api.patch(`/admin/business/content/${item.id}/visibility`, { published: !item.published });
    load();
  };

  if (!data) return <div className="flex min-h-64 items-center justify-center"><Loader2 className="h-6 w-6 animate-spin text-emerald-600" /></div>;
  return <div className="space-y-6" data-testid="beta-content-manager"><header><p className="text-xs font-medium uppercase tracking-[0.12em] text-slate-500">Conteúdo</p><h2 className="mt-2 text-2xl font-semibold text-slate-900">Cursos e materiais</h2></header><form onSubmit={create} className="grid grid-cols-1 gap-3 border border-slate-200 bg-white p-5 md:grid-cols-5"><input required value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} placeholder="Título" data-testid="content-title-input" className="border border-slate-200 px-3 py-2 text-sm md:col-span-2" /><select value={form.content_type} onChange={(event) => setForm({ ...form, content_type: event.target.value })} data-testid="content-type-select" className="border border-slate-200 px-3 py-2 text-sm">{contentTypes.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select><input value={form.url} onChange={(event) => setForm({ ...form, url: event.target.value })} placeholder="Link opcional" className="border border-slate-200 px-3 py-2 text-sm" /><button type="submit" data-testid="content-create-button" className="inline-flex items-center justify-center gap-2 bg-emerald-700 px-3 py-2 text-sm font-medium text-white hover:bg-emerald-800"><Save className="h-4 w-4" />Adicionar</button></form><section className="overflow-x-auto border border-slate-200 bg-white"><table className="w-full min-w-[620px] text-left text-sm"><thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase tracking-[0.08em] text-slate-500"><tr><th className="px-4 py-3">Conteúdo</th><th className="px-4 py-3">Tipo</th><th className="px-4 py-3">Estado</th><th className="px-4 py-3" /></tr></thead><tbody>{data.items.map((item) => <tr key={item.id} className="border-b border-slate-100 last:border-0"><td className="px-4 py-3 font-medium text-slate-900">{item.title}</td><td className="px-4 py-3 capitalize text-slate-600">{item.content_type}</td><td className="px-4 py-3"><span className={item.published ? 'text-emerald-700' : 'text-slate-500'}>{item.published ? 'Publicado' : 'Oculto'}</span></td><td className="px-4 py-3 text-right"><button type="button" onClick={() => visibility(item)} data-testid={`content-visibility-${item.id}`} className="inline-flex items-center gap-2 px-2 py-1 text-xs text-slate-700 hover:bg-slate-100">{item.published ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}{item.published ? 'Ocultar' : 'Publicar'}</button></td></tr>)}</tbody></table>{data.items.length === 0 && <p className="p-8 text-center text-sm text-slate-500">Nenhum conteúdo cadastrado ainda.</p>}</section></div>;
};

export const QuestionsDesk = () => {
  const [data, setData] = useState(null);
  const [reply, setReply] = useState({});
  const [error, setError] = useState('');
  const load = async () => setData((await api.get('/admin/business/questions')).data);
  useEffect(() => { load(); }, []);
  const update = async (question, changes) => {
    setError('');
    try { await api.patch(`/admin/business/questions/${question.id}`, changes); await load(); } catch (requestError) { setError(requestError.response?.data?.detail || 'Não foi possível atualizar a dúvida.'); }
  };
  if (!data) return <div className="flex min-h-64 items-center justify-center"><Loader2 className="h-6 w-6 animate-spin text-emerald-600" /></div>;
  return <div className="space-y-5" data-testid="beta-questions-desk"><header><p className="text-xs font-medium uppercase tracking-[0.12em] text-slate-500">Plantão de dúvidas</p><h2 className="mt-2 text-2xl font-semibold text-slate-900">Responder e acompanhar</h2></header>{error && <p className="border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700" data-testid="question-error">{error}</p>}<section className="space-y-4">{data.questions.map((question) => <article key={question.id} className="border border-slate-200 bg-white p-5"><div className="flex flex-wrap items-start justify-between gap-3"><div><p className="text-sm font-medium text-slate-900">{question.message}</p><p className="mt-2 text-xs text-slate-500">{question.category} · {question.resolved ? 'Resolvida' : 'Em aberto'}</p></div>{question.allow_anonymous_publication && <span className="text-xs text-emerald-700">Publicação anônima autorizada</span>}</div>{question.admin_reply && <p className="mt-4 border-l-2 border-emerald-500 pl-3 text-sm text-slate-700">{question.admin_reply}</p>}<div className="mt-4 flex flex-col gap-3"><textarea value={reply[question.id] ?? question.admin_reply ?? ''} onChange={(event) => setReply({ ...reply, [question.id]: event.target.value })} placeholder="Resposta para o aluno" data-testid={`question-reply-${question.id}`} className="min-h-20 border border-slate-200 p-3 text-sm" /><div className="flex flex-wrap gap-2"><button type="button" onClick={() => update(question, { reply: reply[question.id] || '' })} data-testid={`question-send-${question.id}`} className="inline-flex items-center gap-2 bg-emerald-700 px-3 py-2 text-xs font-medium text-white"><Send className="h-3.5 w-3.5" />Responder</button><button type="button" onClick={() => update(question, { resolved: !question.resolved })} data-testid={`question-resolve-${question.id}`} className="border border-slate-300 px-3 py-2 text-xs text-slate-700">{question.resolved ? 'Reabrir' : 'Marcar resolvida'}</button>{question.allow_anonymous_publication && <button type="button" onClick={() => update(question, { published_anonymously: !question.published_anonymously })} data-testid={`question-publish-${question.id}`} className="border border-slate-300 px-3 py-2 text-xs text-slate-700">{question.published_anonymously ? 'Ocultar pública' : 'Publicar anônima'}</button>}</div></div></article>)}{data.questions.length === 0 && <p className="border border-slate-200 bg-white p-8 text-center text-sm text-slate-500">Nenhuma dúvida enviada ainda.</p>}</section></div>;
};

export const BetaSettings = () => {
  const [data, setData] = useState(null);
  useEffect(() => { api.get('/admin/business/settings').then((response) => setData(response.data)); }, []);
  if (!data) return <div className="flex min-h-64 items-center justify-center"><Loader2 className="h-6 w-6 animate-spin text-emerald-600" /></div>;
  return <div className="space-y-6" data-testid="beta-settings"><header><p className="text-xs font-medium uppercase tracking-[0.12em] text-slate-500">Configurações</p><h2 className="mt-2 text-2xl font-semibold text-slate-900">Base da plataforma</h2></header><div className="grid grid-cols-1 gap-5 md:grid-cols-2"><section className="border border-slate-200 bg-white p-5"><h3 className="font-semibold text-slate-900">Plataforma</h3><p className="mt-3 text-sm text-slate-600">{data.platform.name} · Beta ativo</p></section><section className="border border-slate-200 bg-white p-5"><h3 className="font-semibold text-slate-900">IA</h3><p className="mt-3 text-sm text-slate-600">{data.ai.enabled ? 'Ativa para os fluxos configurados' : 'Indisponível'}</p></section><section className="border border-slate-200 bg-white p-5"><h3 className="font-semibold text-slate-900">E-mails do sistema</h3><p className="mt-3 text-sm text-slate-600">{data.emails.sender_configured ? 'Remetente configurado' : 'Remetente ainda não configurado'}</p></section><section className="border border-slate-200 bg-white p-5"><h3 className="font-semibold text-slate-900">Logs básicos</h3><p className="mt-3 text-sm text-slate-600">{data.logs.sessions_last_24h} sessões iniciadas nas últimas 24 horas</p><p className="mt-2 text-xs text-slate-500">{data.logs.note}</p></section></div></div>;
};