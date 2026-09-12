import React, { useEffect, useState } from 'react';
import { api } from '../api';
import type { DjangoCreditTransaction, DjangoCreditWallet, PaginatedResponse } from '../types';
import { Wallet as WalletIcon, ArrowUpRight, ArrowDownLeft, ShieldCheck, RefreshCw, CheckCircle2 } from 'lucide-react';

export const Wallet: React.FC = () => {
  const [wallet, setWallet] = useState<DjangoCreditWallet | null>(null);
  const [transactions, setTransactions] = useState<DjangoCreditTransaction[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [refreshing, setRefreshing] = useState(false);

  const loadData = async (targetPage = 1) => {
    try {
      setRefreshing(true);
      const [walletData, txData] = await Promise.all([
        api.wallet().catch(() => null),
        api.transactions(targetPage).catch(() => ({ count: 0, next: null, previous: null, results: [] } as PaginatedResponse<DjangoCreditTransaction>)),
      ]);

      if (walletData) setWallet(walletData);
      setTransactions(txData.results || []);
      setTotalPages(Math.ceil((txData.count || 0) / 20) || 1);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    loadData(page);
  }, [page]);

  const formatCredits = (val?: number) => {
    if (val === undefined || val === null) return '0';
    return new Intl.NumberFormat('pt-BR').format(val);
  };

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleString('pt-BR', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const getTxBadge = (type: string) => {
    switch (type) {
      case 'DEPOSIT':
        return <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-mono bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">DEPÓSITO</span>;
      case 'RELEASE':
        return <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-mono bg-emerald-500/10 text-emerald-300 border border-emerald-500/30">ESTORNO (PAY-PER-VALUE)</span>;
      case 'HOLD':
        return <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-mono bg-amber-500/10 text-amber-400 border border-amber-500/20">RESERVA EM CUSTÓDIA</span>;
      case 'CAPTURE':
        return <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-mono bg-slate-500/10 text-slate-300 border border-slate-500/20">LIQUIDAÇÃO DE LOTE</span>;
      default:
        return <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-mono bg-slate-800 text-slate-400">{type}</span>;
    }
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white tracking-tight">
            Carteira & Ledger Contábil
          </h1>
          <p className="text-xs text-slate-400 mt-0.5">
            Custódia preventiva com garantia de Pay-per-Value (estorno automático de linhas sem dados úteis).
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => loadData(page)}
            disabled={refreshing}
            className="px-3 py-2 text-xs font-medium text-slate-300 bg-[#12141C] hover:bg-[#1A1D27] border border-white/10 rounded-lg flex items-center gap-1.5 transition-colors cursor-pointer"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin' : ''}`} />
            <span>Atualizar</span>
          </button>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Saldo Disponível */}
        <div className="bg-[#12141C] border border-white/10 rounded-xl p-5 relative overflow-hidden">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-medium text-slate-400 tracking-wider uppercase">
              Saldo Disponível
            </span>
            <span className="p-2 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              <WalletIcon className="w-4 h-4" />
            </span>
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-bold font-mono text-white tracking-tight">
              {loading ? '---' : formatCredits(wallet?.available_balance ?? wallet?.balance)}
            </span>
            <span className="text-xs text-slate-500 font-mono">créditos</span>
          </div>
          <div className="mt-3 pt-3 border-t border-white/5 flex items-center gap-2 text-[11px] text-emerald-400 font-sans">
            <CheckCircle2 className="w-3.5 h-3.5" />
            <span>Pronto para novos lotes e validações</span>
          </div>
        </div>

        {/* Em Custódia / Reserva */}
        <div className="bg-[#12141C] border border-white/10 rounded-xl p-5 relative overflow-hidden">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-medium text-slate-400 tracking-wider uppercase">
              Em Custódia Preventiva (Hold)
            </span>
            <span className="p-2 rounded-lg bg-amber-500/10 text-amber-400 border border-amber-500/20">
              <ArrowDownLeft className="w-4 h-4" />
            </span>
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-bold font-mono text-amber-400 tracking-tight">
              {loading ? '---' : formatCredits(wallet?.reserved_balance)}
            </span>
            <span className="text-xs text-slate-500 font-mono">créditos</span>
          </div>
          <div className="mt-3 pt-3 border-t border-white/5 text-[11px] text-slate-400 font-sans">
            Reservados para lotes atualmente em processamento assíncrono.
          </div>
        </div>

        {/* Modalidade da Conta */}
        <div className="bg-[#12141C] border border-white/10 rounded-xl p-5 relative overflow-hidden">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-medium text-slate-400 tracking-wider uppercase">
              Modalidade de Faturamento
            </span>
            <span className="p-2 rounded-lg bg-blue-500/10 text-blue-400 border border-blue-500/20">
              <ShieldCheck className="w-4 h-4" />
            </span>
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-bold text-white tracking-tight">
              {wallet?.is_unlimited ? 'Ilimitado (SaaS Core)' : 'Pré-pago (Pay-per-Value)'}
            </span>
          </div>
          <div className="mt-3 pt-3 border-t border-white/5 text-[11px] text-slate-400 font-sans">
            Isolamento contábil estrito por Workspace.
          </div>
        </div>
      </div>

      {/* Ledger Table */}
      <div className="bg-[#12141C] border border-white/10 rounded-xl overflow-hidden shadow-xl">
        <div className="px-5 py-4 border-b border-white/10 flex items-center justify-between">
          <div>
            <h2 className="text-sm font-semibold text-white tracking-tight">
              Extrato Contábil Imutável (Ledger)
            </h2>
            <p className="text-xs text-slate-400 mt-0.5 font-sans">
              Registro append-only de dupla entrada. Cada débito, hold e estorno possui trilha auditável.
            </p>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-white/5 bg-[#090A0F]/50 text-[11px] font-medium text-slate-400 uppercase tracking-wider font-mono">
                <th className="py-3 px-4">Data/Hora (UTC)</th>
                <th className="py-3 px-4">Operação</th>
                <th className="py-3 px-4">Referência / Lote</th>
                <th className="py-3 px-4 text-right">Variação</th>
                <th className="py-3 px-4 text-right">Saldo Resultante</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5 text-xs font-sans">
              {loading ? (
                <tr>
                  <td colSpan={5} className="py-8 text-center text-slate-500">
                    Carregando extrato contábil...
                  </td>
                </tr>
              ) : transactions.length === 0 ? (
                <tr>
                  <td colSpan={5} className="py-12 text-center text-slate-500">
                    Nenhuma transação registrada nesta carteira até o momento.
                  </td>
                </tr>
              ) : (
                transactions.map((tx) => {
                  const isPositive = tx.amount > 0;
                  return (
                    <tr key={tx.id} className="hover:bg-white/[0.02] transition-colors">
                      <td className="py-3.5 px-4 text-slate-400 font-mono text-[11px] whitespace-nowrap">
                        {formatDate(tx.created_at)}
                      </td>
                      <td className="py-3.5 px-4 whitespace-nowrap">
                        {getTxBadge(tx.transaction_type)}
                      </td>
                      <td className="py-3.5 px-4 text-slate-300 font-mono text-[11px]">
                        {tx.reference_id || '---'}
                      </td>
                      <td className={`py-3.5 px-4 text-right font-mono font-medium whitespace-nowrap ${
                        isPositive ? 'text-emerald-400' : 'text-slate-300'
                      }`}>
                        {isPositive ? `+${formatCredits(tx.amount)}` : formatCredits(tx.amount)}
                      </td>
                      <td className="py-3.5 px-4 text-right font-mono text-slate-200 whitespace-nowrap">
                        {formatCredits(tx.balance_after)}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination Footer */}
        {totalPages > 1 && (
          <div className="px-5 py-3 border-t border-white/5 flex items-center justify-between text-xs text-slate-400 font-mono">
            <span>Página {page} de {totalPages}</span>
            <div className="flex gap-2">
              <button
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                className="px-2.5 py-1 rounded bg-white/5 hover:bg-white/10 disabled:opacity-30 cursor-pointer"
              >
                Anterior
              </button>
              <button
                disabled={page >= totalPages}
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                className="px-2.5 py-1 rounded bg-white/5 hover:bg-white/10 disabled:opacity-30 cursor-pointer"
              >
                Próxima
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
