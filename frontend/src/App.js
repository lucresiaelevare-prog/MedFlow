import '@/App.css';
import { BrowserRouter, Routes, Route, useLocation } from 'react-router-dom';
import { AuthProvider } from '@/context/AuthContext';
import { ThemeProvider } from '@/context/ThemeContext';
import { FocusProvider } from '@/context/FocusContext';
import { AccessibilityProvider } from '@/context/AccessibilityContext';
import AuthCallback from '@/components/AuthCallback';
import ProtectedRoute from '@/components/ProtectedRoute';
import Landing from '@/pages/Landing';
import Entrar from '@/pages/Entrar';
import Dashboard from '@/pages/Dashboard';
import Checkin from '@/pages/Checkin';
import History from '@/pages/History';
import Mindfulness from '@/pages/Mindfulness';
import Settings from '@/pages/Settings';
import Subjects from '@/pages/Subjects';
import Resources from '@/pages/Resources';
import Support from '@/pages/Support';
import Profile from '@/pages/Profile';
import PerfilExtendido from '@/pages/PerfilExtendido';
import AdminBusiness from '@/pages/AdminBusiness';
import Habitos from '@/pages/Habitos';
import Tutor from '@/pages/Tutor';
import SmartReview from '@/pages/SmartReview';
import AprenderHoje from '@/pages/AprenderHoje';
import Pomodoro from '@/pages/Pomodoro';
import SmartHome from '@/pages/SmartHome';
import WelcomeTour from '@/pages/WelcomeTour';
import StartHere from '@/pages/StartHere';
import AdminLogin from '@/pages/AdminLogin';
import HomeGate from '@/components/HomeGate';
import SafeRender from '@/components/SafeRender';
import { useAuth } from '@/context/AuthContext';

/** Envolve um element com <SafeRender name="X"> — reduz boilerplate abaixo. */
const safe = (name, element) => <SafeRender name={name}>{element}</SafeRender>;

function AuthedGateOrLanding() {
  const { isAuthenticated } = useAuth();
  if (isAuthenticated === null) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-canvas">
        <div className="w-8 h-8 rounded-full border-2 border-zinc-200 border-t-zinc-600 animate-spin" />
      </div>
    );
  }
  if (isAuthenticated) return <HomeGate />;
  return <Landing />;
}

function AppRouter() {
  const location = useLocation();
  if (location.hash?.includes('session_id=')) return <AuthCallback />;
  return (
    <Routes>
      <Route path="/" element={safe('início', <AuthedGateOrLanding />)} />
      <Route path="/entrar" element={safe('Entrar', <Entrar />)} />
      <Route path="/admin-login" element={safe('Login Admin', <AdminLogin />)} />
      <Route path="/hoje" element={<ProtectedRoute>{safe('Home', <SmartHome />)}</ProtectedRoute>} />
      <Route path="/bem-vindo" element={<ProtectedRoute>{safe('Boas-vindas', <WelcomeTour />)}</ProtectedRoute>} />
      <Route path="/comecar" element={<ProtectedRoute>{safe('Onboarding', <StartHere />)}</ProtectedRoute>} />
      <Route path="/dashboard" element={<ProtectedRoute>{safe('Painel', <Dashboard />)}</ProtectedRoute>} />
      <Route path="/checkin" element={<ProtectedRoute>{safe('Check-in', <Checkin />)}</ProtectedRoute>} />
      <Route path="/history" element={<ProtectedRoute>{safe('Histórico', <History />)}</ProtectedRoute>} />
      <Route path="/mindfulness" element={<ProtectedRoute>{safe('Mindfulness', <Mindfulness />)}</ProtectedRoute>} />
      <Route path="/settings" element={<ProtectedRoute>{safe('Configurações', <Settings />)}</ProtectedRoute>} />
      <Route path="/subjects" element={<ProtectedRoute>{safe('Matérias', <Subjects />)}</ProtectedRoute>} />
      <Route path="/resources" element={<ProtectedRoute>{safe('Recursos', <Resources />)}</ProtectedRoute>} />
      <Route path="/support" element={<ProtectedRoute>{safe('Suporte', <Support />)}</ProtectedRoute>} />
      <Route path="/profile" element={<ProtectedRoute>{safe('Perfil', <Profile />)}</ProtectedRoute>} />
      <Route path="/perfil-estudante" element={<ProtectedRoute>{safe('Perfil de estudo', <PerfilExtendido />)}</ProtectedRoute>} />
      <Route path="/admin" element={<ProtectedRoute>{safe('Admin', <AdminBusiness />)}</ProtectedRoute>} />
      <Route path="/habitos" element={<ProtectedRoute>{safe('Hábitos', <Habitos />)}</ProtectedRoute>} />
      <Route path="/tutor" element={<ProtectedRoute>{safe('Tutor', <Tutor />)}</ProtectedRoute>} />
      <Route path="/tutor/devolutiva" element={<ProtectedRoute>{safe('Devolutiva Inteligente', <SmartReview />)}</ProtectedRoute>} />
      <Route path="/tutor/aprender" element={<ProtectedRoute>{safe('Aprender Hoje', <AprenderHoje />)}</ProtectedRoute>} />
      <Route path="/pomodoro" element={<ProtectedRoute>{safe('Pomodoro', <Pomodoro />)}</ProtectedRoute>} />
      <Route path="*" element={safe('início', <Landing />)} />
    </Routes>
  );
}

function App() {
  return (
    <div className="App">
      <BrowserRouter>
        <ThemeProvider>
          <AuthProvider>
            <AccessibilityProvider>
              <FocusProvider>
                <AppRouter />
              </FocusProvider>
            </AccessibilityProvider>
          </AuthProvider>
        </ThemeProvider>
      </BrowserRouter>
    </div>
  );
}

export default App;
