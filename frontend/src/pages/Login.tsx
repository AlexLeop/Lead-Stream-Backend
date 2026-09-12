import React, { useState } from 'react';
import { useLeadStream } from '../LeadStreamContext';
import { Lock, User, ArrowRight, ShieldCheck, AlertCircle } from 'lucide-react';

interface LoginProps {
  onLoginSuccess: () => void;
}

export const Login: React.FC<LoginProps> = ({ onLoginSuccess }) => {
  const { login } = useLeadStream();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username.trim() || !password) {
      setError('Informe o usuário e a senha corporativa.');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      await login(username.trim(), password);
      onLoginSuccess();
    } catch (err: any) {
      setError(err?.message || 'Falha na autenticação. Verifique as credenciais.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen w-full bg-[#090A0F] flex items-center justify-center p-4 selection:bg-emerald-500/20 selection:text-emerald-400">
      {/* Background subtle radial gradient */}
      <div className="fixed inset-0 pointer-events-none bg-[radial-gradient(circle_at_top,_rgba(16,185,129,0.05)_0%,_transparent_50%)]" />

      <div className="w-full max-w-md relative z-10">
        {/* Header Branding */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-emerald-500/20 bg-emerald-500/5 text-emerald-400 text-xs font-mono mb-4 tracking-wider uppercase">
            <ShieldCheck className="w-3.5 h-3.5" />
            Zero-Bounce & Ledger Multi-Tenant
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-white">
            LeadStream
          </h1>
          <p className="text-xs text-slate-400 mt-1 font-sans">
            Enterprise Data Intelligence & Enrichment Platform
          </p>
        </div>

        {/* Card Box */}
        <div className="bg-[#12141C] border border-white/10 rounded-xl p-8 shadow-2xl backdrop-blur-sm">
          <h2 className="text-sm font-semibold text-slate-200 uppercase tracking-wider text-center mb-6">
            Acesso Restrito ao Painel
          </h2>

          {error && (
            <div className="mb-6 p-3.5 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs flex items-start gap-2.5">
              <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5 text-rose-400" />
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-slate-400 mb-1.5 font-sans">
                Usuário do Administrador
              </label>
              <div className="relative">
                <span className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-500">
                  <User className="w-4 h-4" />
                </span>
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="admin"
                  autoComplete="username"
                  required
                  className="w-full pl-10 pr-4 py-2.5 bg-[#090A0F] border border-white/10 rounded-lg text-sm text-white placeholder:text-slate-600 focus:outline-none focus:border-emerald-500/60 focus:ring-1 focus:ring-emerald-500/60 transition-colors"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-400 mb-1.5 font-sans">
                Senha de Acesso
              </label>
              <div className="relative">
                <span className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-500">
                  <Lock className="w-4 h-4" />
                </span>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••••••"
                  autoComplete="current-password"
                  required
                  className="w-full pl-10 pr-4 py-2.5 bg-[#090A0F] border border-white/10 rounded-lg text-sm text-white placeholder:text-slate-600 focus:outline-none focus:border-emerald-500/60 focus:ring-1 focus:ring-emerald-500/60 transition-colors font-mono"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full mt-2 py-2.5 px-4 bg-emerald-600 hover:bg-emerald-500 active:bg-emerald-700 disabled:opacity-50 text-white font-medium text-sm rounded-lg flex items-center justify-center gap-2 transition-all cursor-pointer disabled:cursor-not-allowed shadow-lg shadow-emerald-950/40"
            >
              {loading ? (
                <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              ) : (
                <>
                  <span>Entrar no Sistema</span>
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </form>

          <div className="mt-6 pt-6 border-t border-white/5 text-center">
            <p className="text-[11px] text-slate-500">
              Conexão protegida por criptografia TLS e tokens de dupla camada (RFC 7519).
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};
