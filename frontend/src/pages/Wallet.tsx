import React, { useEffect, useState } from 'react';
import { api } from '../api';
import { ensureArray, type DjangoCreditTransaction, type DjangoCreditWallet, type PaginatedResponse } from '../types';
import { Wallet as WalletIcon, ArrowDownLeft, ShieldCheck, RefreshCw, CheckCircle2 } from 'lucide-react';

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
      setTransactions(ensureArray<DjangoCreditTransaction>(txData));
      setTotalPages(Math.ceil(((txData as PaginatedResponse<DjangoCreditTransaction>)?.count || 0) / 20) || 1);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    loadData(page);
  }, [page]);

  const formatBRL = (val?: number) => {
    const num = Number(val || 0);
    return num.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
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
        return <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">Depósito</span>;
      case 'RELEASE':
        return <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-50 text-emerald-800 border border-emerald-300">Estorno (Pay-per-Value)</span>;
      case 'HOLD':
        return <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold bg-amber-50 text-amber-700 border border-amber-200">Reserva em Custódia</span>;
      case 'CAPTURE':
        return <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold bg-blue-50 text-blue-700 border border-blue-200">Liquidação</span>;
      default:
        return <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium bg-slate-100 text-slate-700">{type}</span>;
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h2 className="text-base font-bold text-slate-950 tracking-tight">
            Carteira & Ledger Contábil
          </h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Registro contábil de dupla entrada em Reais (BRL) com garantia de estorno de dados ausentes (Pay-per-Value).
          </p>
        </div>
        <button
          onClick={() => loadData(page)}
          disabled={refreshing}
          className="px-3 py-1.5 text-xs font-semibold text-slate-700 bg-white hover:bg-slate-50 border border-slate-200 rounded-[10px] flex items-center gap-1.5 transition-colors cursor-pointer shadow-2xs w-fit"
        >
          <RefreshCw className={`w-3.5 h-3.5 text-slate-400 ${refreshing ? 'animate-spin' : ''}`} />
          <span>Atualizar</span>
        </button>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Saldo Disponível */}
        <div className="p-5 bg-white rounded-[12px] border border-slate-200 shadow-2xs flex flex-col justify-between space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-500">
              Saldo Disponível
            </span>
            <div className="w-8 h-8 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center font-bold">
              <WalletIcon className="w-4 h-4" />
            </div>
          </div>
          <div>
            <div className="text-2xl font-bold tracking-tight text-slate-950">
              {loading ? '—' : formatBRL(wallet?.available_balance ?? wallet?.balance)}
            </div>
            <div className="mt-2 pt-2 border-t border-slate-100 flex items-center gap-1.5 text-xs text-emerald-600 font-medium">
              <CheckCircle2 className="w-3.5 h-3.5" />
              <span>Pronto para novos lotes e validações</span>
            </div>
          </div>
        </div>

        {/* Em Custódia / Reserva */}
        <div className="p-5 bg-white rounded-[12px] border border-slate-200 shadow-2xs flex flex-col justify-between space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-500">
              Em Custódia Preventiva (Hold)
            </span>
            <div className="w-8 h-8 rounded-lg bg-amber-50 text-amber-600 flex items-center justify-center font-bold">
              <ArrowDownLeft className="w-4 h-4" />
            </div>
          </div>
          <div>
            <div className="text-2xl font-bold tracking-tight text-amber-700">
              {loading ? '—' : formatBRL(wallet?.reserved_balance)}
            </div>
            <div className="mt-2 pt-2 border-t border-slate-100 text-xs text-slate-500">
              Reservados para lotes atualmente em processamento assíncrono.
            </div>
          </div>
        </div>

        {/* Modalidade da Conta */}
        <div className="p-5 bg-white rounded-[12px] border border-slate-200 shadow-2xs flex flex-col justify-between space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-500">
              Modalidade de Cobrança
            </span>
            <div className="w-8 h-8 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center font-bold">
              <ShieldCheck className="w-4 h-4" />
            </div>
          </div>
          <div>
            <div className="text-2xl font-bold tracking-tight text-slate-950">
              Pay-per-Value BRL
            </div>
            <div className="mt-2 pt-2 border-t border-slate-100 text-xs text-slate-500">
              Cobrança exclusivamente por dados efetivamente entregues.
            </div>
          </div>
        </div>
      </div>

      {/* Ledger Table */}
      <div className="bg-white border border-slate-200 rounded-[12px] overflow-hidden shadow-2xs">
        <div className="p-5 border-b border-slate-200">
          <h3 className="text-sm font-bold text-slate-950">
            Extrato Contábil Imutável (Ledger)
          </h3>
          <p className="text-xs text-slate-500 mt-0.5">
            Registro append-only de dupla entrada em Reais. Cada débito, retenção e estorno possui proveniência e trilha auditável.
          </p>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50 text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
                <th className="py-3 px-4">Data / Hora</th>
                <th className="py-3 px-4">Operação</th>
                <th className="py-3 px-4">Referência / Lote</th>
                <th className="py-3 px-4 text-right">Variação</th>
                <th className="py-3 px-4 text-right">Saldo Resultante</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-xs">
              {loading ? (
                <tr>
                  <td colSpan={5} className="py-8 text-center text-slate-400">
                    Carregando extrato contábil…
                  </td>
                </tr>
              ) : transactions.length === 0 ? (
                <tr>
                  <td colSpan={5} className="py-12 text-center text-slate-400">
                    Nenhuma transação registrada nesta carteira até o momento.
                  </td>
                </tr>
              ) : (
                transactions.map((tx) => {
                  const isPositive = tx.amount > 0;
                  return (
                    <tr key={tx.id} className="hover:bg-slate-50/70 transition-colors">
                      <td className="py-3 px-4 text-slate-500 font-medium text-[11px] whitespace-nowrap">
                        {formatDate(tx.created_at)}
                      </td>
                      <td className="py-3 px-4 whitespace-nowrap">
                        {getTxBadge(tx.transaction_type)}
                      </td>
                      <td className="py-3 px-4 text-slate-700 font-medium text-[11px]">
                        {tx.reference_id || '—'}
                      </td>
                      <td className={`py-3 px-4 text-right font-bold whitespace-nowrap ${
                        isPositive ? 'text-emerald-700' : 'text-slate-800'
                      }`}>
                        {isPositive ? `+${formatBRL(tx.amount)}` : formatBRL(tx.amount)}
                      </td>
                      <td className="py-3 px-4 text-right font-bold text-slate-900 whitespace-nowrap">
                        {formatBRL(tx.balance_after)}
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
          <div className="p-4 border-t border-slate-100 flex items-center justify-between text-xs text-slate-600 font-medium">
            <span>Página {page} de {totalPages}</span>
            <div className="flex gap-2">
              <button
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                className="px-3 py-1.5 rounded-[8px] border border-slate-200 bg-white hover:bg-slate-50 disabled:opacity-40 cursor-pointer shadow-2xs"
              >
                Anterior
              </button>
              <button
                disabled={page >= totalPages}
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                className="px-3 py-1.5 rounded-[8px] border border-slate-200 bg-white hover:bg-slate-50 disabled:opacity-40 cursor-pointer shadow-2xs"
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
