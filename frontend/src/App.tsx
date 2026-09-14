import { useState } from 'react';
import AppShell from './pages/AppShell';
import { LeadStreamProvider } from './LeadStreamContext';

export default function App() {
  const [route, setRoute] = useState('dashboard');

  return (
    <LeadStreamProvider>
      <AppShell currentRoute={route} onNavigate={setRoute} />
    </LeadStreamProvider>
  );
}
