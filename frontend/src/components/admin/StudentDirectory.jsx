import { useEffect, useState } from 'react';
import { Eye, Loader2, Search, UsersRound } from 'lucide-react';
import api from '@/lib/api';

const label = (value) => value || '—';

export const StudentDirectory = () => {
  const [data, setData] = useState({ students: [], filters: { universities: [] } });
  const [filters, setFilters] = useState({ search: '', university: '', plan: '', status: '' });
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState(null);
  const [detail, setDetail] = useState(null);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      const params = Object.fromEntries(Object.entries(filters).filter(([, value]) => value));
      try {
        const response = await api.get('/admin/business/students', { params });
        setData(response.data);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [filters]);

  const openStudent = async (student) => {
    setSelected(student);
    setDetail(null);
    const response = await api.get(`/admin/business/students/${student.user_id}`);
    setDetail(response.data);
  };

  const updateStudent = async (changes) => {
    if (!selected) return;
    const response = await api.patch(`/admin/business/students/${selected.user_id}`, changes);
    setDetail({ ...detail, student: response.data.student });
    setSelected({ ...selected, ...response.data.student });
    const refreshed = await api.get('/admin/business/students');
    setData(refreshed.data);
  };

  return (
    <div className="space-y-5" data-testid="business-students-page">
      <header>
        <p className="text-xs font-medium uppercase tracking-[0.12em] text-slate-500">Alunos</p>
        <h2 className="mt-2 text-2xl font-semibold text-slate-900">Acompanhe quem está aprendendo</h2>
      </header>
      <div className="grid grid-cols-1 gap-3 border border-slate-200 bg-white p-4 md:grid-cols-4">
        <label className="relative md:col-span-2">
          <Search className="absolute left-3 top-3 h-4 w-4 text-slate-400" />
          <input
            value={filters.search}
            onChange={(event) => setFilters({ ...filters, search: event.target.value })}
            placeholder="Buscar nome ou e-mail"
            data-testid="business-student-search"
            className="w-full border border-slate-200 py-2 pl-9 pr-3 text-sm text-slate-800 outline-none focus:border-emerald-500"
          />
        </label>
        <select
          value={filters.university}
          onChange={(event) => setFilters({ ...filters, university: event.target.value })}
          data-testid="business-student-university-filter"
          className="border border-slate-200 px-3 py-2 text-sm text-slate-700"
        >
          <option value="">Todas as faculdades</option>
          {data.filters.universities.map((university) => <option key={university}>{university}</option>)}
        </select>
        <select
          value={filters.status}
          onChange={(event) => setFilters({ ...filters, status: event.target.value })}
          data-testid="business-student-status-filter"
          className="border border-slate-200 px-3 py-2 text-sm text-slate-700"
        >
          <option value="">Todas as situações</option>
          <option value="Ativo">Ativo</option>
          <option value="Inativo">Inativo</option>
        </select>
      </div>
      <div className="grid grid-cols-1 gap-5 xl:grid-cols-12">
        <div className="overflow-x-auto border border-slate-200 bg-white xl:col-span-8" data-testid="business-student-table">
          {loading ? (
            <div className="flex min-h-48 items-center justify-center"><Loader2 className="h-5 w-5 animate-spin text-emerald-600" /></div>
          ) : (
            <table className="w-full min-w-[720px] text-left text-sm">
              <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase tracking-[0.08em] text-slate-500">
                <tr><th className="px-4 py-3">Aluno</th><th className="px-4 py-3">Faculdade</th><th className="px-4 py-3">Período</th><th className="px-4 py-3">Plano</th><th className="px-4 py-3">Situação</th><th className="px-4 py-3" /></tr>
              </thead>
              <tbody>
                {data.students.map((student) => (
                  <tr key={student.user_id} className="border-b border-slate-100 last:border-0 hover:bg-emerald-50/30">
                    <td className="px-4 py-3"><p className="font-medium text-slate-900">{student.name}</p><p className="text-xs text-slate-500">{student.email}</p></td>
                    <td className="px-4 py-3 text-slate-700">{student.university}</td>
                    <td className="px-4 py-3 text-slate-700">{label(student.period)}</td>
                    <td className="px-4 py-3 capitalize text-slate-700">{student.plan}</td>
                    <td className="px-4 py-3"><span className={student.access_blocked ? 'text-rose-700' : student.status === 'Ativo' ? 'text-emerald-700' : 'text-slate-500'}>{student.access_blocked ? 'Bloqueado' : student.status}</span></td>
                    <td className="px-4 py-3 text-right"><button type="button" onClick={() => openStudent(student)} data-testid={`business-student-open-${student.user_id}`} className="p-2 text-emerald-700 hover:bg-emerald-100"><Eye className="h-4 w-4" /></button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {!loading && data.students.length === 0 && <p className="p-8 text-center text-sm text-slate-500">Nenhum aluno encontrado com estes filtros.</p>}
        </div>
        <aside className="border border-slate-200 bg-white p-5 xl:col-span-4" data-testid="business-student-detail">
          {!selected && <p className="text-sm text-slate-500">Selecione um aluno para ver o histórico e o progresso.</p>}
          {selected && !detail && <Loader2 className="h-5 w-5 animate-spin text-emerald-600" />}
          {detail && <><div className="flex items-center gap-2"><UsersRound className="h-4 w-4 text-emerald-600" /><h3 className="font-semibold text-slate-900">{detail.student.name}</h3></div><p className="mt-1 text-sm text-slate-500">{detail.student.email}</p><dl className="mt-5 space-y-3 text-sm"><div className="flex justify-between"><dt className="text-slate-500">Check-ins</dt><dd className="font-medium">{detail.progress.checkins}</dd></div><div className="flex justify-between"><dt className="text-slate-500">Ações de estudo</dt><dd className="font-medium">{detail.progress.study_actions}</dd></div><div className="flex justify-between"><dt className="text-slate-500">Missões concluídas</dt><dd className="font-medium">{detail.progress.missions_completed}</dd></div><div className="flex justify-between"><dt className="text-slate-500">Uso da IA</dt><dd className="font-medium">{detail.progress.ai_requests}</dd></div></dl><div className="mt-5 space-y-3 border-t border-slate-100 pt-4"><label className="block text-xs font-medium uppercase tracking-[0.08em] text-slate-500">Plano<select value={detail.student.subscription_plan || 'free'} onChange={(event) => updateStudent({ subscription_plan: event.target.value })} data-testid="student-plan-select" className="mt-2 w-full border border-slate-200 px-3 py-2 text-sm text-slate-700"><option value="free">Free</option><option value="premium">Premium</option></select></label><button type="button" onClick={() => updateStudent({ access_blocked: !detail.student.access_blocked })} data-testid="student-access-toggle" className={detail.student.access_blocked ? 'w-full bg-emerald-700 px-3 py-2 text-sm font-medium text-white' : 'w-full bg-rose-700 px-3 py-2 text-sm font-medium text-white'}>{detail.student.access_blocked ? 'Desbloquear acesso' : 'Bloquear acesso'}</button><p className="text-xs text-slate-500">O bloqueio encerra as sessões atuais e preserva todo o histórico.</p></div></>}
        </aside>
      </div>
    </div>
  );
};