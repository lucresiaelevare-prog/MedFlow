import { useEffect, useState } from 'react';
import { Loader2, MessageCircle, Heart, Send, Trash2, Users, ChevronDown, ChevronUp } from 'lucide-react';
import Shell from '@/components/Shell';
import api from '@/lib/api';

const CATEGORIES = [
  { key: 'all',           label: 'Todos' },
  { key: 'geral',         label: 'Geral' },
  { key: 'rotina',        label: 'Rotina' },
  { key: 'estudo',        label: 'Estudo' },
  { key: 'saude-mental',  label: 'Saúde mental' },
  { key: 'plantao',       label: 'Plantão' },
  { key: 'dependencia',   label: 'Dependência' },
  { key: 'ocio',          label: 'Ócio' },
];

const humanDate = (iso) => {
  try {
    const d = new Date(iso);
    return d.toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });
  } catch (e) { return ''; }
};

const CommentList = ({ postId }) => {
  const [comments, setComments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [body, setBody] = useState('');
  const [sending, setSending] = useState(false);

  const load = async () => {
    setLoading(true);
    const { data } = await api.get(`/community/posts/${postId}/comments`);
    setComments(data.comments || []);
    setLoading(false);
  };

  useEffect(() => { load(); }, [postId]);

  const send = async () => {
    if (!body.trim()) return;
    setSending(true);
    try {
      await api.post(`/community/posts/${postId}/comments`, { body });
      setBody('');
      await load();
    } finally { setSending(false); }
  };

  const remove = async (id) => {
    if (!window.confirm('Excluir comentário?')) return;
    await api.delete(`/community/comments/${id}`);
    await load();
  };

  return (
    <div className="mt-4 pt-4 hairline-t">
      {loading ? (
        <div className="flex justify-center py-2"><Loader2 className="w-4 h-4 text-brand animate-spin" /></div>
      ) : (
        <div className="space-y-2.5">
          {comments.map((c) => (
            <div key={c.id} className="flex items-start gap-2">
              <div className="w-7 h-7 rounded-full flex items-center justify-center text-[10px] font-semibold text-zinc-700 shrink-0"
                   style={{ background: 'var(--mf-surface-2)' }}>
                {(c.author?.name || 'A').split(' ').map((s) => s[0]).slice(0, 2).join('').toUpperCase()}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-baseline gap-2">
                  <p className="text-[12.5px] font-semibold text-zinc-900">{c.author?.name || 'Estudante'}</p>
                  <p className="text-[11px] text-zinc-400">{humanDate(c.created_at)}</p>
                </div>
                <p className="text-[13px] text-zinc-700 leading-snug whitespace-pre-wrap">{c.body}</p>
              </div>
              <button onClick={() => remove(c.id)} className="btn-ghost text-red-500 opacity-60 hover:opacity-100">
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </div>
          ))}
          {!comments.length && <p className="text-[12.5px] text-zinc-400 italic">Ainda sem comentários.</p>}
        </div>
      )}
      <div className="mt-3 flex gap-2">
        <input
          value={body}
          onChange={(e) => setBody(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') send(); }}
          placeholder="Escreva um comentário…"
          className="flex-1 rounded-lg hairline px-3 py-2 text-[13px] bg-white"
          data-testid={`comment-input-${postId}`}
        />
        <button onClick={send} disabled={sending || !body.trim()}
                className="mf-btn-primary px-3"
                data-testid={`comment-send-${postId}`}>
          {sending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
        </button>
      </div>
    </div>
  );
};

const Community = () => {
  const [posts, setPosts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState('all');
  const [body, setBody] = useState('');
  const [category, setCategory] = useState('geral');
  const [posting, setPosting] = useState(false);
  const [openComments, setOpenComments] = useState({});

  const load = async () => {
    setLoading(true);
    try {
      const params = tab === 'all' ? '' : `?category=${tab}`;
      const { data } = await api.get(`/community/posts${params}`);
      setPosts(data.posts || []);
    } finally { setLoading(false); }
  };

  useEffect(() => { load(); }, [tab]);

  const submit = async () => {
    if (!body.trim() || body.trim().length < 3) return;
    setPosting(true);
    try {
      await api.post('/community/posts', { body, category });
      setBody('');
      await load();
    } finally { setPosting(false); }
  };

  const toggleLike = async (post) => {
    // optimistic
    setPosts((prev) => prev.map((p) => p.id === post.id
      ? { ...p, liked_by_me: !p.liked_by_me, like_count: p.like_count + (p.liked_by_me ? -1 : 1) }
      : p));
    try { await api.post(`/community/posts/${post.id}/like`); }
    catch (e) { await load(); }
  };

  const removePost = async (id) => {
    if (!window.confirm('Excluir seu post?')) return;
    await api.delete(`/community/posts/${id}`);
    await load();
  };

  return (
    <Shell>
      <div className="max-w-3xl mx-auto px-5 md:px-8 pt-6 md:pt-8 animate-fade-in" data-testid="community-root">
        <header className="mb-6">
          <div className="flex items-center gap-2 mb-1">
            <Users strokeWidth={1.75} className="w-5 h-5 text-brand" />
            <p className="eyebrow">Comunidade</p>
          </div>
          <h1 className="mt-1.5 text-[26px] md:text-[30px] font-semibold text-zinc-900 tracking-tight">
            Troca de vivências
          </h1>
          <p className="mt-2 text-[14px] text-zinc-500 max-w-2xl">
            Um espaço para compartilhar experiências e apoio entre estudantes. Aqui não é sobre tirar dúvidas
            acadêmicas — é sobre vida universitária, rotina e como ninguém está sozinho nisso.
          </p>
        </header>

        {/* Compose */}
        <section className="mf-card p-4 md:p-5 mb-5">
          <textarea
            value={body}
            onChange={(e) => setBody(e.target.value)}
            rows={3}
            maxLength={2000}
            placeholder="Compartilhe algo com a turma — uma vitória, um desabafo, uma dica de rotina…"
            className="w-full rounded-lg hairline px-3 py-2 text-[14px] bg-white resize-none"
            data-testid="community-compose-body"
          />
          <div className="mt-2 flex items-center justify-between gap-2 flex-wrap">
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              className="rounded-lg hairline px-3 py-1.5 text-[13px] bg-white"
              data-testid="community-compose-category"
            >
              {CATEGORIES.filter((c) => c.key !== 'all').map((c) =>
                <option key={c.key} value={c.key}>{c.label}</option>
              )}
            </select>
            <div className="flex items-center gap-2">
              <p className="text-[11px] text-zinc-400">{body.length}/2000</p>
              <button
                onClick={submit}
                disabled={posting || body.trim().length < 3}
                data-testid="community-compose-submit"
                className="mf-btn-primary flex items-center gap-1.5"
              >
                {posting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                Publicar
              </button>
            </div>
          </div>
        </section>

        {/* Tabs */}
        <div className="mb-4 flex gap-2 overflow-x-auto pb-1">
          {CATEGORIES.map((c) => (
            <button
              key={c.key}
              onClick={() => setTab(c.key)}
              className={`px-3 py-1.5 rounded-full text-[12.5px] font-medium whitespace-nowrap transition-colors hairline ${
                tab === c.key ? 'text-white' : 'text-zinc-700 hover:bg-zinc-50 bg-white'
              }`}
              style={tab === c.key ? { background: 'var(--mf-brand)', borderColor: 'var(--mf-brand-hov)' } : {}}
              data-testid={`community-tab-${c.key}`}
            >{c.label}</button>
          ))}
        </div>

        {/* Feed */}
        {loading ? (
          <div className="flex justify-center py-10"><Loader2 className="w-5 h-5 text-brand animate-spin" /></div>
        ) : posts.length === 0 ? (
          <div className="mf-card p-8 text-center">
            <p className="text-[14px] text-zinc-500">Nenhuma publicação por aqui ainda. Seja a primeira.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {posts.map((p) => (
              <article key={p.id} className="mf-card p-4 md:p-5" data-testid={`community-post-${p.id}`}>
                <header className="flex items-center gap-3">
                  <div className="w-9 h-9 rounded-full flex items-center justify-center text-[12px] font-semibold text-zinc-700"
                       style={{ background: 'var(--mf-surface-2)' }}>
                    {(p.author?.name || 'A').split(' ').map((s) => s[0]).slice(0, 2).join('').toUpperCase()}
                  </div>
                  <div className="flex-1">
                    <p className="text-[13.5px] font-semibold text-zinc-900">{p.author?.name || 'Estudante'}</p>
                    <p className="text-[11.5px] text-zinc-500">
                      <span className="uppercase tracking-wider">{p.category}</span> · {humanDate(p.created_at)}
                    </p>
                  </div>
                  {p.is_mine && (
                    <button onClick={() => removePost(p.id)} className="btn-ghost text-red-500 opacity-70 hover:opacity-100">
                      <Trash2 className="w-4 h-4" />
                    </button>
                  )}
                </header>
                <p className="mt-3 text-[14px] text-zinc-800 leading-relaxed whitespace-pre-wrap">{p.body}</p>
                <div className="mt-3 flex items-center gap-4">
                  <button
                    onClick={() => toggleLike(p)}
                    className={`flex items-center gap-1.5 text-[13px] ${p.liked_by_me ? 'text-red-500' : 'text-zinc-500 hover:text-red-500'}`}
                    data-testid={`community-like-${p.id}`}
                  >
                    <Heart className={`w-4 h-4 ${p.liked_by_me ? 'fill-red-500' : ''}`} strokeWidth={1.75} />
                    {p.like_count || 0}
                  </button>
                  <button
                    onClick={() => setOpenComments({ ...openComments, [p.id]: !openComments[p.id] })}
                    className="flex items-center gap-1.5 text-[13px] text-zinc-500 hover:text-brand"
                    data-testid={`community-comments-toggle-${p.id}`}
                  >
                    <MessageCircle className="w-4 h-4" strokeWidth={1.75} />
                    {p.comments_count || 0}
                    {openComments[p.id] ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                  </button>
                </div>
                {openComments[p.id] && <CommentList postId={p.id} />}
              </article>
            ))}
          </div>
        )}

        <p className="text-center text-[11px] text-zinc-400 py-10 tracking-wider uppercase font-medium">
          Regras · respeito, escuta e sem substituir profissionais de saúde
        </p>
      </div>
    </Shell>
  );
};

export default Community;
