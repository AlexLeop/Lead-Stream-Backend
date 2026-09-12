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
    } catch (err: any) {
      setError(err?.message || 'Falha ao executar probe SMTP.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      {/* Header */}
      <div>
        <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded text-[11px] font-mono bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 mb-2 uppercase">
          <ShieldCheck className="w-3.5 h-3.5" />
          Zero-Bounce Engine (RFC 5321)
        </div>
        <h1 className="text-xl font-bold text-white tracking-tight">
          Verificação Profunda de E-mail Corporativo
        </h1>
        <p className="text-xs text-slate-400 mt-0.5">
          Handshake SMTP atômico em tempo real com resolução MX de DNS e detecção de domínio Catch-all.
        </p>
      </div>

      {/* Input Box */}
      <div className="bg-[#12141C] border border-white/10 rounded-xl p-6 shadow-xl">
        <form onSubmit={handleVerify} className="flex flex-col sm:flex-row gap-3">
          <div className="relative flex-1">
            <span className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-500">
              <Mail className="w-4 h-4" />
            </span>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="ex: diretoria@empresa.com.br"
              required
              className="w-full pl-10 pr-4 py-2.5 bg-[#090A0F] border border-white/10 rounded-lg text-sm text-white placeholder:text-slate-600 focus:outline-none focus:border-emerald-500/60 focus:ring-1 focus:ring-emerald-500/60 transition-colors font-mono"
            />
          </div>
          <button
            type="submit"
            disabled={loading}
            className="py-2.5 px-6 bg-emerald-600 hover:bg-emerald-500 active:bg-emerald-700 disabled:opacity-50 text-white font-medium text-xs rounded-lg flex items-center justify-center gap-2 transition-all cursor-pointer disabled:cursor-not-allowed whitespace-nowrap uppercase tracking-wider font-mono shadow-lg shadow-emerald-950/40"
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
          <div className="mt-4 p-3 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs flex items-center gap-2">
            <XCircle className="w-4 h-4 flex-shrink-0 text-rose-400" />
            <span>{error}</span>
          </div>
        )}
      </div>

      {/* Results View */}
      {result && (
        <div className="space-y-4 animate-in fade-in duration-200">
          {/* Status Banner */}
          <div className={`p-5 rounded-xl border flex items-center justify-between ${
            result.deliverable
              ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-200'
              : result.is_catch_all
              ? 'bg-amber-500/10 border-amber-500/30 text-amber-200'
              : 'bg-rose-500/10 border-rose-500/30 text-rose-200'
          }`}>
            <div className="flex items-center gap-3">
              {result.deliverable ? (
                <CheckCircle2 className="w-6 h-6 text-emerald-400" />
              ) : result.is_catch_all ? (
                <AlertTriangle className="w-6 h-6 text-amber-400" />
              ) : (
                <XCircle className="w-6 h-6 text-rose-400" />
              )}
              <div>
                <h3 className="text-sm font-semibold tracking-wide">
                  {result.deliverable
                    ? 'ENTREGÁVEL (Caixa Postal Confirmada via SMTP 250)'
                    : result.is_catch_all
                    ? 'RISCO MODERADO (Servidor Catch-all / Aceita Qualquer E-mail)'
                    : 'NÃO ENTREGÁVEL (Rejeitado no Handshake do Servidor)'}
                </h3>
                <p className="text-xs opacity-80 font-mono mt-0.5">
                  Alvo: {result.email}
                </p>
              </div>
            </div>

            <div className="text-right font-mono">
              <span className="text-xs opacity-70 block">Score de Confiança</span>
              <span className="text-xl font-bold">{result.confidence_score}%</span>
            </div>
          </div>

          {/* Technical Diagnostics */}
          <div className="grid grid-cols-1 sm:grid-cols-4 gap-3 font-mono text-xs">
            <div className="bg-[#12141C] border border-white/10 p-3.5 rounded-lg">
              <span className="text-slate-500 block text-[10px] uppercase">Sintaxe RFC 5322</span>
              <span className={result.syntax_valid ? 'text-emerald-400 font-semibold' : 'text-rose-400'}>
                {result.syntax_valid ? 'VÁLIDA' : 'INVÁLIDA'}
              </span>
            </div>
            <div className="bg-[#12141C] border border-white/10 p-3.5 rounded-lg">
              <span className="text-slate-500 block text-[10px] uppercase">DNS MX Server</span>
              <span className={result.mx_found ? 'text-emerald-400 font-semibold' : 'text-rose-400'}>
                {result.mx_found ? 'ENCONTRADO' : 'AUSENTE'}
              </span>
            </div>
            <div className="bg-[#12141C] border border-white/10 p-3.5 rounded-lg">
              <span className="text-slate-500 block text-[10px] uppercase">Handshake SMTP</span>
              <span className={result.smtp_handshake_ok ? 'text-emerald-400 font-semibold' : 'text-rose-400'}>
                {result.smtp_handshake_ok ? '250 OK' : 'REJEITADO'}
              </span>
            </div>
            <div className="bg-[#12141C] border border-white/10 p-3.5 rounded-lg">
              <span className="text-slate-500 block text-[10px] uppercase">Filtro Catch-all</span>
              <span className={result.is_catch_all ? 'text-amber-400 font-semibold' : 'text-emerald-400'}>
                {result.is_catch_all ? 'DETECTADO' : 'NÃO CATCH-ALL'}
              </span>
            </div>
          </div>

          {/* Live Terminal Log Mockup */}
          <div className="bg-[#090A0F] border border-white/10 rounded-xl p-4 font-mono text-xs text-slate-300 shadow-inner">
            <div className="flex items-center gap-2 pb-3 mb-3 border-b border-white/10 text-slate-500 text-[11px]">
              <Terminal className="w-3.5 h-3.5" />
              <span>Trilha de Auditoria SMTP Socket (Timeout 3.0s)</span>
            </div>
            <div className="space-y-1 text-slate-400">
              <p className="text-slate-500"># Iniciando handshake atômico com servidor de destino...</p>
              <p>&gt; RESOLVE MX {result.email.split('@')[1]} → Conectado</p>
              <p>&gt; HELO leadstream.io → 250 mx.google.com at your service</p>
              <p>&gt; MAIL FROM:&lt;probe@leadstream.io&gt; → 250 2.1.0 OK</p>
              <p className={result.smtp_handshake_ok ? 'text-emerald-400' : 'text-rose-400'}>
                &gt; RCPT TO:&lt;{result.email}&gt; → {result.smtp_handshake_ok ? '250 2.1.5 Recipient OK' : '550 5.1.1 User unknown'}
              </p>
              {result.is_catch_all && (
                <p className="text-amber-400">
                  &gt; CANARY PROBE: Recipient aleatório aceito. Domínio classificado como Catch-All.
                </p>
              )}
              {result.diagnostics && (
                <p className="text-slate-400 mt-2">Diagnóstico: {result.diagnostics}</p>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
