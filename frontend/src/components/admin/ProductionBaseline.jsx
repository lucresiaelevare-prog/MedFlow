import { CalendarClock, UserCheck, UsersRound } from 'lucide-react';

const formatDate = (value) => {
  if (!value) return 'Sem acesso registrado';
  return new Date(value).toLocaleString('pt-BR', {
    dateStyle: 'short',
    timeStyle: 'short',
  });
};

const BaselineCell = ({ icon: Icon, label, value, detail, testId }) => (
  <div className="border border-slate-200 bg-white p-4" data-testid={testId}>
    <div className="flex items-start justify-between gap-3">
      <p className="text-xs font-medium uppercase tracking-[0.1em] text-slate-500">{label}</p>
      <Icon className="h-4 w-4 text-emerald-700" strokeWidth={1.8} />
    </div>
    <p className="mt-3 text-2xl font-semibold text-slate-900">{value}</p>
    <p className="mt-1 text-xs leading-relaxed text-slate-500">{detail}</p>
  </div>
);

export const ProductionBaseline = ({ growth }) => (
  <section className="border border-emerald-100 bg-emerald-50/40 p-6" data-testid="production-baseline">
    <div>
      <p className="text-xs font-medium uppercase tracking-[0.12em] text-emerald-800">Linha de base</p>
      <h2 className="mt-1 text-lg font-semibold text-slate-900">Comportamento agregado do ambiente</h2>
      <p className="mt-1 text-sm text-slate-600">Sem nomes ou dados individuais. Em produção, estes números refletem a base real.</p>
    </div>
    <div className="mt-5 grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-5">
      <BaselineCell
        icon={UsersRound}
        label="Alunos cadastrados"
        value={growth.total_students}
        detail="Total acumulado de alunos não administrativos."
        testId="baseline-total-students"
      />
      <BaselineCell
        icon={UserCheck}
        label="Ativos em 7 dias"
        value={growth.active_students_7d}
        detail="Com sessão registrada na janela de 7 dias."
        testId="baseline-active-7d"
      />
      <BaselineCell
        icon={UserCheck}
        label="Ativos em 30 dias"
        value={growth.active_students_30d}
        detail="Com sessão registrada na janela de 30 dias."
        testId="baseline-active-30d"
      />
      <BaselineCell
        icon={UsersRound}
        label="Novos cadastros"
        value={`${growth.new_students_7d} / ${growth.new_students_30d}`}
        detail="Últimos 7 dias / últimos 30 dias."
        testId="baseline-new-students"
      />
      <BaselineCell
        icon={CalendarClock}
        label="Último acesso agregado"
        value={formatDate(growth.last_access?.latest_at)}
        detail={`${growth.last_access?.students_with_recorded_access || 0} alunos com acesso registrado.`}
        testId="baseline-last-access"
      />
    </div>
  </section>
);