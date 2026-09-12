import { useState } from 'react';
import AppShell from './pages/AppShell';
import { Login } from './pages/Login';
import { LeadStreamProvider, useLeadStream } from './LeadStreamContext';
import { BrandingProvider } from './components/BrandingProvider';

function AppContent() {
  const [route, setRoute] = useState('dashboard');
  const { isAuthenticated, loading } = useLeadStream();

  if (loading) {
    return (
      <div className="min-h-screen w-full bg-slate-50 flex items-center justify-center text-slate-500 text-xs font-medium">
        <div className="flex flex-col items-center gap-2.5">
          <div className="w-5 h-5 border-2 border-slate-300 border-t-blue-600 rounded-full animate-spin" />
          <span>Carregando LeadStream...</span>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Login onLoginSuccess={() => setRoute('dashboard')} />;
  }

  return <AppShell currentRoute={route} onNavigate={setRoute} />;
}

export default function App() {
  return (
    <BrandingProvider>
      <LeadStreamProvider>
        <AppContent />
      </LeadStreamProvider>
    </BrandingProvider>
  );
}
