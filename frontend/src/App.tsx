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
      <div className="min-h-screen w-full bg-[#090A0F] flex items-center justify-center text-slate-400 font-mono text-xs">
        <div className="flex flex-col items-center gap-3">
          <div className="w-5 h-5 border-2 border-emerald-500/30 border-t-emerald-400 rounded-full animate-spin" />
          <span>Autenticando sessão LeadStream...</span>
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
