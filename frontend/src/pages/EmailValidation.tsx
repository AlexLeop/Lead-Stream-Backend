import React, { useState } from 'react';
import { api } from '../api';
import type { DjangoEmailValidationResult } from '../types';
import { Mail, CheckCircle2, AlertTriangle, XCircle, Search, ShieldCheck } from 'lucide-react';

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
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-white p-5 rounded-[12px] border border-slate-200 shadow-2xs flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2.5 flex-wrap">
            <h2 className="text-base font-bold text-slate-950 tracking-tight">
              Validação Profunda de E-mail Corporativo
            </h2>
            <span className="px-2.5 py-0.5 rounded-full text-[10px] font-semibold bg-blue-50 text-blue-700 border border-blue-200 flex items-center gap-1.5">
              <ShieldCheck className="w-3.5 h-3.5" />
              Zero-Bounce RFC 5321
            </span>
          </div>
          <p className="text-slate-500 text-xs mt-1 font-normal max-w-2xl">
            Handshake SMTP atômico em tempo real com resolução MX de DNS e detecção precisa de domínio Catch-all.
          </p>
        </div>
      </div>

      {/* Input Box */}
      <div className="bg-white border border-slate-200 rounded-[12px] p-5 shadow-2xs">
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
              className="w-full pl-10 pr-4 py-2 bg-white border border-slate-200 rounded-[10px] text-xs text-slate-900 placeholder:text-slate-400 focus:outline-none focus:border-blue-600 focus:ring-1 focus:ring-blue-600 transition-all font-medium"
            />
          </div>
          <button
            type="submit"
            disabled={loading}
            className="py-2 px-5 bg-blue-600 hover:bg-blue-700 active:bg-blue-800 disabled:opacity-50 text-white font-bold text-xs rounded-[10px] flex items-center justify-center gap-2 transition-all cursor-pointer disabled:cursor-not-allowed whitespace-nowrap shadow-2xs"
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
          <div className="mt-4 p-3 rounded-[10px] bg-red-50 border border-red-200 text-red-800 text-xs flex items-center gap-2">
            <XCircle className="w-4 h-4 shrink-0 text-red-600" />
            <span>{error}</span>
          </div>
        )}
      </div>

      {/* Results View */}
      {result && (
        <div className="space-y-4">
          {/* Status Banner */}
          <div className={`p-4 rounded-[12px] border flex items-center justify-between shadow-2xs ${
            result.deliverable
              ? 'bg-emerald-50/60 border-emerald-200 text-emerald-950'
              : result.is_catch_all
              ? 'bg-amber-50/60 border-amber-200 text-amber-950'
              : 'bg-red-50/60 border-red-200 text-red-950'
          }`}>
            <div className="flex items-center gap-3">
              {result.deliverable ? (
                <CheckCircle2 className="w-6 h-6 text-emerald-600 shrink-0" />
              ) : result.is_catch_all ? (
                <AlertTriangle className="w-6 h-6 text-amber-600 shrink-0" />
              ) : (
                <XCircle className="w-6 h-6 text-red-600 shrink-0" />
              )}
              <div>
                <h3 className="text-xs font-bold tracking-tight">
                  {result.deliverable
                    ? 'ENTREGÁVEL — Caixa postal confirmada via SMTP 250'
                    : result.is_catch_all
                    ? 'RISCO MODERADO — Servidor Catch-all configurado'
                    : 'NÃO ENTREGÁVEL — Rejeitado no handshake do servidor'}
                </h3>
                <p className="text-[11px] text-slate-500 font-mono mt-0.5">
                  Endereço: {result.email}
                </p>
              </div>
            </div>

            <div className="text-right shrink-0">
              <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider block">Score</span>
              <span className="text-xl font-bold text-slate-900">{result.confidence_score}%</span>
            </div>
          </div>

          {/* Technical Diagnostics */}
          <div className="grid grid-cols-1 sm:grid-cols-4 gap-3 text-xs">
            <div className="bg-white border border-slate-200 p-3.5 rounded-[10px] shadow-2xs">
              <span className="text-slate-400 block text-[10px] font-semibold uppercase tracking-wider">Sintaxe RFC 5322</span>
              <span className={`text-xs font-bold mt-1 block ${result.syntax_valid ? 'text-emerald-700' : 'text-red-700'}`}>
                {result.syntax_valid ? 'VÁLIDA' : 'INVÁLIDA'}
              </span>
            </div>
            <div className="bg-white border border-slate-200 p-3.5 rounded-[10px] shadow-2xs">
              <span className="text-slate-400 block text-[10px] font-semibold uppercase tracking-wider">Servidor DNS MX</span>
              <span className={`text-xs font-bold mt-1 block ${result.mx_found ? 'text-emerald-700' : 'text-red-700'}`}>
                {result.mx_found ? 'ENCONTRADO' : 'AUSENTE'}
              </span>
            </div>
            <div className="bg-white border border-slate-200 p-3.5 rounded-[10px] shadow-2xs">
              <span className="text-slate-400 block text-[10px] font-semibold uppercase tracking-wider">Handshake SMTP</span>
              <span className={`text-xs font-bold mt-1 block ${result.smtp_handshake_ok ? 'text-emerald-700' : 'text-red-700'}`}>
                {result.smtp_handshake_ok ? '250 OK' : 'REJEITADO'}
              </span>
            </div>
            <div className="bg-white border border-slate-200 p-3.5 rounded-[10px] shadow-2xs">
              <span className="text-slate-400 block text-[10px] font-semibold uppercase tracking-wider">Catch-All</span>
              <span className={`text-xs font-bold mt-1 block ${result.is_catch_all ? 'text-amber-700' : 'text-slate-700'}`}>
                {result.is_catch_all ? 'SIM (Aceita tudo)' : 'NÃO (Específico)'}
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
