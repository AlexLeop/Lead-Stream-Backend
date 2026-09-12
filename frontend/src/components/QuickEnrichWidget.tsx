import { useState, type FormEvent } from 'react';
import { ArrowRight, Building2, Loader2, Mail, Search, ShieldCheck } from 'lucide-react';
import { api } from '../api';
import type { Lead } from '../types';

export default function QuickEnrichWidget() {
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<Lead | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleLookup = async (event: FormEvent) => {
    event.preventDefault();
    if (!query.trim()) return;
    setLoading(true);
    setResult(null);
    setError(null);
    try {
      setResult(await api.enrichmentLookup(query.trim()));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Não foi possível consultar a base.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col justify-between rounded-2xl border border-slate-200 bg-white p-6 shadow-xs">
      <div>
        <div className="mb-3 flex items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-blue-50 text-blue-600">
              <Search className="h-4 w-4" />
            </div>
            <div>
              <h2 className="text-base font-bold text-slate-900">Consulta rápida da base</h2>
              <p className="text-xs text-slate-500">Localize uma empresa ou um contato por e-mail, domínio ou nome</p>
            </div>
          </div>
          <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-[11px] font-bold text-slate-700">Consulta rápida</span>
        </div>

        <form onSubmit={handleLookup} className="mt-4 flex gap-2">
          <input
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="E-mail, domínio, pessoa ou empresa"
            className="min-w-0 flex-1 rounded-xl border border-slate-300 bg-slate-50 px-3.5 py-2.5 text-xs font-medium text-slate-900 placeholder:text-slate-500 focus:border-blue-500 focus:bg-white focus:outline-none"
          />
          <button
            type="submit"
            disabled={loading || !query.trim()}
            className="flex shrink-0 items-center gap-2 rounded-xl bg-blue-600 px-4 py-2.5 text-xs font-bold text-white disabled:opacity-50"
          >
            {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <ArrowRight className="h-3.5 w-3.5" />}
            Consultar
          </button>
        </form>

        {error && (
          <div className="mt-4 rounded-xl bg-amber-50 px-4 py-3 text-xs font-semibold leading-relaxed text-amber-900" role="alert">
            {error}
          </div>
        )}

        {result && (
          <div className="mt-4 rounded-xl bg-slate-50 p-4">
            <div className="flex items-start justify-between gap-4">
              <div>
                <div className="text-sm font-bold text-slate-900">{result.name}</div>
                <div className="mt-0.5 text-xs text-slate-600">{result.title || 'Cargo não informado'}</div>
              </div>
              <span className="rounded-full bg-emerald-50 px-2.5 py-1 text-[11px] font-bold text-emerald-800">Registro encontrado</span>
            </div>
            <div className="mt-4 grid gap-3 text-xs sm:grid-cols-3">
              <div className="flex items-start gap-2">
                <Building2 className="mt-0.5 h-3.5 w-3.5 text-slate-500" />
                <span><strong className="block text-slate-800">Empresa</strong>{result.company || 'Não informada'}</span>
              </div>
              <div className="flex items-start gap-2">
                <Mail className="mt-0.5 h-3.5 w-3.5 text-slate-500" />
                <span><strong className="block text-slate-800">E-mail</strong>{result.email || 'Não informado'}</span>
              </div>
              <div className="flex items-start gap-2">
                <ShieldCheck className="mt-0.5 h-3.5 w-3.5 text-slate-500" />
                <span><strong className="block text-slate-800">Status</strong>{result.status}</span>
              </div>
            </div>
          </div>
        )}
      </div>

      {!result && !error && (
        <div className="mt-4 flex items-center gap-1.5 border-t border-slate-100 pt-3 text-[11px] text-slate-500">
          <ShieldCheck className="h-3.5 w-3.5 text-blue-600" /> Os resultados refletem as informações disponíveis na sua base.
        </div>
      )}
    </div>
  );
}
