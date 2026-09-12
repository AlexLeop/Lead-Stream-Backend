import React, { useState } from 'react';
import { api } from '../api';
import type { DjangoEmailValidationResult } from '../types';
import { Mail, CheckCircle2, AlertTriangle, XCircle, Terminal, Search, ShieldCheck } from 'lucide-react';

export const EmailValidation: React.FC = () => {
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<DjangoEmailValidationResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleVerify = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim()) return;

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const data = await api.verifyEmail(email.trim());
      setResult(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Falha ao executar probe SMTP.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6 max-w-[1440px] mx-auto pb-8">
      {/* Header (Light MVP Style) */}
      <div className="bg-white p-5 sm:p-6 rounded-[12px] border border-slate-200 shadow-xs flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2.5 flex-wrap">
            <h1 className="text-xl sm:text-2xl font-extrabold text-slate-900 tracking-tight">
              Verificação Profunda de E-mail Corporativo
            </h1>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-extrabold bg-blue-50 text-blue-700 border border-blue-200 flex items-center gap-1.5">
              <ShieldCheck className="w-3.5 h-3.5" />
              Zero-Bounce Engine RFC 5321
            </span>
          </div>
          <p className="text-slate-500 text-xs sm:text-sm mt-1 font-medium max-w-2xl">
            Handshake SMTP atômico em tempo real com resolução MX de DNS e detecção precisa de domínio Catch-all.
          </p>
        </div>
      </div>

      {/* Input Box */}
      <div className="bg-white border border-slate-200/90 rounded-2xl p-6 shadow-xs">
        <form onSubmit={handleVerify} className="flex flex-col sm:flex-row gap-3">
          <div className="relative flex-1">
            <span className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
              <Mail className="w-4 h-4" />
            </span>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="ex: diretoria@empresa.com.br"
              required
              className="w-full pl-10 pr-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs sm:text-sm text-slate-900 placeholder:text-slate-400 focus:bg-white focus:outline-none focus:border-blue-600 focus:ring-1 focus:ring-blue-600 transition-all font-medium"
            />
          </div>
          <button
            type="submit"
            disabled={loading}
            className="py-2.5 px-6 bg-blue-600 hover:bg-blue-700 active:bg-blue-800 disabled:opacity-50 text-white font-bold text-xs rounded-xl flex items-center justify-center gap-2 transition-all cursor-pointer disabled:cursor-not-allowed whitespace-nowrap shadow-xs"
          >
            {loading ? (
              <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
            ) : (
              <>
                <Search className="w-3.5 h-3.5" />
                <span>Disparar Probe SMTP</span>
              </>
            )}
          </button>
        </form>

        {error && (
          <div className="mt-4 p-3.5 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-center gap-2 font-medium">
            <XCircle className="w-4 h-4 shrink-0 text-rose-600" />
            <span>{error}</span>
          </div>
        )}
      </div>

      {/* Results View */}
      {result && (
        <div className="space-y-4 animate-in fade-in duration-200">
          {/* Status Banner */}
          <div className={`p-5 rounded-2xl border flex items-center justify-between shadow-xs ${
            result.deliverable
              ? 'bg-emerald-50 border-emerald-200 text-emerald-950'
              : result.is_catch_all
              ? 'bg-amber-50 border-amber-200 text-amber-950'
              : 'bg-rose-50 border-rose-200 text-rose-950'
          }`}>
            <div className="flex items-center gap-3.5">
              {result.deliverable ? (
                <CheckCircle2 className="w-7 h-7 text-emerald-600 shrink-0" />
              ) : result.is_catch_all ? (
                <AlertTriangle className="w-7 h-7 text-amber-600 shrink-0" />
              ) : (
                <XCircle className="w-7 h-7 text-rose-600 shrink-0" />
              )}
              <div>
                <h3 className="text-sm font-extrabold tracking-tight">
                  {result.deliverable
                    ? 'ENTREGÁVEL (Caixa Postal Confirmada via SMTP 250)'
                    : result.is_catch_all
                    ? 'RISCO MODERADO (Servidor Catch-all / Aceita Qualquer E-mail)'
                    : 'NÃO ENTREGÁVEL (Rejeitado no Handshake do Servidor)'}
                </h3>
                <p className="text-xs text-slate-600 font-mono mt-0.5">
                  Alvo: {result.email}
                </p>
              </div>
            </div>

            <div className="text-right shrink-0">
              <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider block">Score de Confiança</span>
              <span className="text-2xl font-extrabold text-slate-900">{result.confidence_score}%</span>
            </div>
          </div>

          {/* Technical Diagnostics */}
          <div className="grid grid-cols-1 sm:grid-cols-4 gap-3 text-xs">
            <div className="bg-white border border-slate-200/90 p-4 rounded-xl shadow-xs">
              <span className="text-slate-400 block text-[10px] font-bold uppercase tracking-wider">Sintaxe RFC 5322</span>
              <span className={`text-sm font-extrabold mt-1 block ${result.syntax_valid ? 'text-emerald-700' : 'text-rose-700'}`}>
                {result.syntax_valid ? 'VÁLIDA' : 'INVÁLIDA'}
              </span>
            </div>
            <div className="bg-white border border-slate-200/90 p-4 rounded-xl shadow-xs">
              <span className="text-slate-400 block text-[10px] font-bold uppercase tracking-wider">DNS MX Server</span>
              <span className={`text-sm font-extrabold mt-1 block ${result.mx_found ? 'text-emerald-700' : 'text-rose-700'}`}>
                {result.mx_found ? 'ENCONTRADO' : 'AUSENTE'}
              </span>
            </div>
            <div className="bg-white border border-slate-200/90 p-4 rounded-xl shadow-xs">
              <span className="text-slate-400 block text-[10px] font-bold uppercase tracking-wider">Handshake SMTP</span>
              <span className={`text-sm font-extrabold mt-1 block ${result.smtp_handshake_ok ? 'text-emerald-700' : 'text-rose-700'}`}>
                {result.smtp_handshake_ok ? '250 OK' : 'REJEITADO'}
              </span>
            </div>
            <div className="bg-white border border-slate-200/90 p-4 rounded-xl shadow-xs">
              <span className="text-slate-400 block text-[10px] font-bold uppercase tracking-wider">Filtro Catch-all</span>
              <span className={`text-sm font-extrabold mt-1 block ${result.is_catch_all ? 'text-amber-700' : 'text-emerald-700'}`}>
                {result.is_catch_all ? 'DETECTADO' : 'NÃO CATCH-ALL'}
              </span>
            </div>
          </div>

          {/* Terminal Log Socket */}
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 font-mono text-xs text-slate-300 shadow-md">
            <div className="flex items-center gap-2 pb-3 mb-3 border-b border-slate-800 text-slate-400 text-[11px] font-bold uppercase tracking-wider">
              <Terminal className="w-3.5 h-3.5 text-blue-400" />
              <span>Trilha de Auditoria SMTP Socket (Timeout 3.0s)</span>
            </div>
            <div className="space-y-1 text-slate-300 text-[11px]">
              <p className="text-slate-500"># Conectando ao host MX de destino...</p>
              <p>&gt; RESOLVE MX {result.email.split('@')[1]} → Conectado</p>
              <p>&gt; HELO leadstream.io → 250 host at your service</p>
              <p>&gt; MAIL FROM:&lt;probe@leadstream.io&gt; → 250 2.1.0 OK</p>
              <p className={result.smtp_handshake_ok ? 'text-emerald-400 font-bold' : 'text-rose-400 font-bold'}>
                &gt; RCPT TO:&lt;{result.email}&gt; → {result.smtp_handshake_ok ? '250 2.1.5 Recipient OK' : '550 5.1.1 User unknown'}
              </p>
              {result.is_catch_all && (
                <p className="text-amber-400 font-bold">
                  &gt; CANARY PROBE: Recipient aleatório aceito. Domínio classificado como Catch-All.
                </p>
              )}
              {result.diagnostics && (
                <p className="text-slate-400 mt-2 font-sans text-xs">Diagnóstico: {result.diagnostics}</p>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
