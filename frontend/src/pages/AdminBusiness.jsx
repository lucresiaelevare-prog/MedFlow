import { useEffect, useState } from 'react';
import { Loader2, ShieldCheck } from 'lucide-react';
import { useSearchParams } from 'react-router-dom';
import Shell from '@/components/Shell';
import api from '@/lib/api';
import { BusinessAdminNav } from '@/components/admin/BusinessAdminNav';
import { BusinessOverview } from '@/components/admin/BusinessOverview';
import { StudentDirectory } from '@/components/admin/StudentDirectory';
import { DeveloperView } from '@/components/admin/BusinessOperations';
import { BetaSettings, ContentManager, QuestionsDesk } from '@/components/admin/BetaAdminViews';

export default function AdminBusiness() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [access, setAccess] = useState(null);
  const section = searchParams.get('area') || 'dashboard';

  useEffect(() => {
    api.get('/admin/whoami').then((response) => setAccess(response.data)).catch(() => setAccess(false));
  }, []);

  const changeSection = (next) => setSearchParams(next === 'dashboard' ? {} : { area: next });

  if (access === null) {
    return <Shell><div className="flex min-h-[360px] items-center justify-center"><Loader2 className="h-6 w-6 animate-spin text-emerald-600" /></div></Shell>;
  }
  if (!access || !access.is_admin) {
    return <Shell><div className="p-12 text-center text-slate-600" data-testid="business-admin-forbidden">Acesso restrito a administradores.</div></Shell>;
  }

  let screen = <BusinessOverview />;
  if (section === 'dashboard') screen = <BusinessOverview />;
  if (section === 'students') screen = <StudentDirectory />;
  if (section === 'content') screen = <ContentManager />;
  if (section === 'questions') screen = <QuestionsDesk />;
  if (section === 'settings') screen = <BetaSettings />;
  if (section === 'developer' && access.is_technical_admin) screen = <DeveloperView />;
  if (section === 'developer' && !access.is_technical_admin) screen = <div className="p-8 text-slate-600">Acesso técnico restrito.</div>;
  return (
    <Shell>
      <div className="min-h-screen bg-[#fafbfd]" data-testid="business-admin-root">
        <header className="border-b border-slate-200 bg-white">
          <div className="mx-auto flex max-w-7xl items-center gap-3 px-4 py-6 sm:px-6 lg:px-8">
            <span className="border border-emerald-100 bg-emerald-50 p-3 text-emerald-700"><ShieldCheck className="h-5 w-5" strokeWidth={1.8} /></span>
            <div><p className="text-xs font-medium uppercase tracking-[0.12em] text-slate-500">Painel administrativo</p><h1 className="mt-1 text-2xl font-semibold text-slate-900">MedFlow em 30 segundos</h1></div>
          </div>
        </header>
        <BusinessAdminNav active={section} onChange={changeSection} technicalAccess={access.is_technical_admin} />
        <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">{screen}</main>
      </div>
    </Shell>
  );
}