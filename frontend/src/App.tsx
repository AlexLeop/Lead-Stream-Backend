import { useEffect, useState } from 'react';
import AppShell from './pages/AppShell';
import { LeadStreamProvider } from './LeadStreamContext';
import { useLeadStream } from './LeadStreamContext';
import { Login } from './pages/Login';

function routeFromLocation(): string {
  const route = window.location.pathname.replace(/^\/+|\/+$/g, '');
  return route && route !== 'login' ? route : 'dashboard';
}

function Application() {
  const { isAuthenticated, loading } = useLeadStream();
  const [route, setRoute] = useState(routeFromLocation);

  useEffect(() => {
    const handleHistory = () => setRoute(routeFromLocation());
    window.addEventListener('popstate', handleHistory);
    return () => window.removeEventListener('popstate', handleHistory);
  }, []);

  const navigate = (nextRoute: string, replace = false) => {
    const path = `/${nextRoute}`;
    if (replace) window.history.replaceState({}, '', path);
    else window.history.pushState({}, '', path);
    setRoute(nextRoute);
  };

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[var(--ls-bg)]" role="status">
        <div className="text-center">
          <div className="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-slate-200 border-t-blue-600" />
          <p className="mt-4 text-sm font-medium text-slate-600">Preparando seu workspace…</p>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    if (window.location.pathname !== '/login') window.history.replaceState({}, '', '/login');
    return <Login onLoginSuccess={() => navigate('dashboard', true)} />;
  }

  if (window.location.pathname === '/login') window.history.replaceState({}, '', `/${route}`);
  return <AppShell currentRoute={route} onNavigate={navigate} />;
}

export default function App() {
  return (
    <LeadStreamProvider>
      <Application />
    </LeadStreamProvider>
  );
}
