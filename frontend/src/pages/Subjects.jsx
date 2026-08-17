import { useEffect, useState } from 'react';
import { Loader2, Plus, Trash2, GraduationCap, ClipboardList, Check } from 'lucide-react';
import Shell from '@/components/Shell';
import api from '@/lib/api';
import IDS from '@/constants/testIds';

const Subjects = () => {
  const [subjects, setSubjects] = useState([]);
  const [exams, setExams] = useState([]);
  const [loading, setLoading] = useState(true);
  const [subjName, setSubjName] = useState('');
  const [subjDep, setSubjDep] = useState(false);
  const [examName, setExamName] = useState('');
  const [examDate, setExamDate] = useState('');
  const [examSubjId, setExamSubjId] = useState('');
  const [gradeInputs, setGradeInputs] = useState({});
  const [weakInputs, setWeakInputs] = useState({});

  const load = async () => {
    setLoading(true);
    const [s, e] = await Promise.all([api.get('/subjects'), api.get('/exams')]);
    setSubjects(s.data.subjects || []);
    setExams(e.data.exams || []);
    if (s.data.subjects?.length && !examSubjId) {
      setExamSubjId(s.data.subjects[0].id);
    }
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  const addSubject = async () => {
    if (!subjName.trim()) return;
    await api.post('/subjects', { name: subjName.trim(), is_dependency: subjDep });
    setSubjName(''); setSubjDep(false);
    await load();
  };

  const removeSubject = async (id) => {
    await api.delete(`/subjects/${id}`);
    await load();
  };

  const addExam = async () => {
    if (!examName.trim() || !examDate || !examSubjId) return;
    await api.post('/exams', { subject_id: examSubjId, name: examName.trim(), exam_date: examDate });
    setExamName(''); setExamDate('');
    await load();
  };

  const saveGrade = async (exam) => {
    const g = parseFloat(gradeInputs[exam.id]);
    if (Number.isNaN(g)) return;
    await api.patch(`/exams/${exam.id}`, { grade: g, weak_topics: weakInputs[exam.id] || null });
    await load();
  };

  const removeExam = async (id) => {
    await api.delete(`/exams/${id}`);
    await load();
  };

  const today = new Date().toISOString().slice(0, 10);
  const upcoming = exams.filter((e) => (e.grade == null) && e.exam_date >= today);
  const past = exams.filter((e) => e.grade != null || e.exam_date < today);

  return (
    <Shell>
      <div data-testid={IDS.subjects.root} className="max-w-md md:max-w-3xl mx-auto px-5 md:px-6 pt-6 md:pt-10 space-y-6 animate-fade-in">
        <div>
          <p className="text-xs uppercase tracking-widest text-sage-700 font-semibold">Acompanhamento acadêmico</p>
          <h1 className="mt-1 font-display text-3xl md:text-4xl font-semibold text-stone-900">Matérias & Provas</h1>
          <p className="mt-2 text-stone-600 text-sm">O motor usa essas informações para adaptar suas missões.</p>
        </div>

        {loading ? (
          <div className="rounded-3xl bg-white border border-stone-100 p-10 flex justify-center">
            <Loader2 className="w-6 h-6 text-sage-600 animate-spin" />
          </div>
        ) : (
          <>
            {/* Add subject */}
            <section className="rounded-3xl bg-white border border-stone-100 p-6">
              <div className="flex items-center gap-2 mb-4">
                <GraduationCap className="w-5 h-5 text-sage-700" />
                <h3 className="font-display text-lg text-stone-800">Disciplina</h3>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-[1fr_auto_auto] gap-2">
                <input
                  data-testid={IDS.subjects.name}
                  value={subjName}
                  onChange={(e) => setSubjName(e.target.value)}
                  placeholder="Ex.: Cardiologia"
                  className="bg-stone-50 border border-stone-200 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-sage-500/40"
                />
                <label className="flex items-center gap-2 text-sm text-stone-600 px-2">
                  <input
                    data-testid={IDS.subjects.depToggle}
                    type="checkbox"
                    checked={subjDep}
                    onChange={(e) => setSubjDep(e.target.checked)}
                    className="w-4 h-4 accent-terracotta-500"
                  />
                  Dependência
                </label>
                <button
                  data-testid={IDS.subjects.save}
                  onClick={addSubject}
                  disabled={!subjName.trim()}
                  className="bg-sage-600 hover:bg-sage-700 disabled:bg-stone-200 disabled:text-stone-400 text-white rounded-full px-5 py-3 font-medium flex items-center gap-2"
                >
                  <Plus className="w-4 h-4" /> Adicionar
                </button>
              </div>

              {subjects.length > 0 && (
                <ul className="mt-4 space-y-2">
                  {subjects.map((s) => (
                    <li key={s.id} className="flex items-center justify-between bg-stone-50 rounded-2xl px-4 py-3">
                      <div className="flex items-center gap-2">
                        <span className="text-stone-800 font-medium">{s.name}</span>
                        {s.is_dependency && (
                          <span className="text-[10px] uppercase tracking-widest bg-terracotta-100 text-terracotta-700 px-2 py-0.5 rounded-full">dep</span>
                        )}
                      </div>
                      <button
                        data-testid={IDS.subjects.remove(s.id)}
                        onClick={() => removeSubject(s.id)}
                        className="text-stone-400 hover:text-terracotta-600 transition-colors"
                        aria-label={`Remover ${s.name}`}
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </section>

            {/* Add exam */}
            <section className="rounded-3xl bg-white border border-stone-100 p-6">
              <div className="flex items-center gap-2 mb-4">
                <ClipboardList className="w-5 h-5 text-terracotta-600" />
                <h3 className="font-display text-lg text-stone-800">Prova</h3>
              </div>
              {subjects.length === 0 ? (
                <p className="text-sm text-stone-500">Adicione uma disciplina primeiro.</p>
              ) : (
                <div className="grid grid-cols-1 sm:grid-cols-4 gap-2">
                  <select
                    data-testid={IDS.subjects.examSubject}
                    value={examSubjId}
                    onChange={(e) => setExamSubjId(e.target.value)}
                    className="bg-stone-50 border border-stone-200 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-sage-500/40"
                  >
                    {subjects.map((s) => (
                      <option key={s.id} value={s.id}>{s.name}</option>
                    ))}
                  </select>
                  <input
                    data-testid={IDS.subjects.examName}
                    value={examName}
                    onChange={(e) => setExamName(e.target.value)}
                    placeholder="Ex.: P1 Anatomia"
                    className="bg-stone-50 border border-stone-200 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-sage-500/40"
                  />
                  <input
                    data-testid={IDS.subjects.examDate}
                    type="date"
                    value={examDate}
                    onChange={(e) => setExamDate(e.target.value)}
                    className="bg-stone-50 border border-stone-200 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-sage-500/40"
                  />
                  <button
                    data-testid={IDS.subjects.examSave}
                    onClick={addExam}
                    disabled={!examName.trim() || !examDate}
                    className="bg-sage-600 hover:bg-sage-700 disabled:bg-stone-200 disabled:text-stone-400 text-white rounded-full px-5 py-3 font-medium flex items-center justify-center gap-2"
                  >
                    <Plus className="w-4 h-4" /> Adicionar
                  </button>
                </div>
              )}
            </section>

            {/* Upcoming exams */}
            {upcoming.length > 0 && (
              <section className="rounded-3xl bg-white border border-stone-100 p-6">
                <h3 className="font-display text-lg text-stone-800 mb-4">Próximas provas</h3>
                <ul className="space-y-3">
                  {upcoming.map((e) => (
                    <li key={e.id} className="flex items-center justify-between bg-terracotta-50/60 rounded-2xl px-4 py-3">
                      <div>
                        <p className="text-stone-800 font-medium">{e.name} <span className="text-stone-500 font-normal">· {e.subject_name}</span></p>
                        <p className="text-xs text-stone-600">{new Date(e.exam_date).toLocaleDateString('pt-BR')}</p>
                      </div>
                      <button
                        data-testid={IDS.subjects.examRemove(e.id)}
                        onClick={() => removeExam(e.id)}
                        className="text-stone-400 hover:text-terracotta-600"
                        aria-label={`Remover ${e.name}`}
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </li>
                  ))}
                </ul>
              </section>
            )}

            {/* Past exams / grading */}
            {past.length > 0 && (
              <section className="rounded-3xl bg-white border border-stone-100 p-6">
                <h3 className="font-display text-lg text-stone-800 mb-4">Provas realizadas</h3>
                <ul className="space-y-3">
                  {past.map((e) => (
                    <li key={e.id} className="bg-stone-50 rounded-2xl px-4 py-3 space-y-3">
                      <div className="flex items-center justify-between">
                        <div>
                          <p className="text-stone-800 font-medium">{e.name} <span className="text-stone-500 font-normal">· {e.subject_name}</span></p>
                          <p className="text-xs text-stone-600">{new Date(e.exam_date).toLocaleDateString('pt-BR')}</p>
                        </div>
                        {e.grade != null && (
                          <div className="flex items-center gap-2 text-sage-700">
                            <Check className="w-4 h-4" />
                            <span className="font-display text-xl tabular-nums">{e.grade}</span>
                          </div>
                        )}
                      </div>
                      {e.grade == null && (
                        <div className="grid grid-cols-1 sm:grid-cols-[auto_1fr_auto] gap-2">
                          <input
                            data-testid={IDS.subjects.gradeInput(e.id)}
                            type="number" step="0.1" min="0" max="10"
                            placeholder="Nota"
                            value={gradeInputs[e.id] || ''}
                            onChange={(ev) => setGradeInputs({ ...gradeInputs, [e.id]: ev.target.value })}
                            className="bg-white border border-stone-200 rounded-xl px-3 py-2 w-full sm:w-24 focus:outline-none focus:ring-2 focus:ring-sage-500/40"
                          />
                          <input
                            placeholder="Tópicos fracos (opcional)"
                            value={weakInputs[e.id] || ''}
                            onChange={(ev) => setWeakInputs({ ...weakInputs, [e.id]: ev.target.value })}
                            className="bg-white border border-stone-200 rounded-xl px-3 py-2 focus:outline-none focus:ring-2 focus:ring-sage-500/40"
                          />
                          <button
                            data-testid={IDS.subjects.gradeSave(e.id)}
                            onClick={() => saveGrade(e)}
                            className="bg-sage-600 hover:bg-sage-700 text-white rounded-full px-4 py-2 text-sm font-medium"
                          >
                            Salvar nota
                          </button>
                        </div>
                      )}
                      {e.weak_topics && <p className="text-xs text-stone-500 italic">Tópicos fracos: {e.weak_topics}</p>}
                    </li>
                  ))}
                </ul>
              </section>
            )}
          </>
        )}
      </div>
    </Shell>
  );
};

export default Subjects;
