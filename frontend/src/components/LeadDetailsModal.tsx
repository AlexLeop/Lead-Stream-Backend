import React, { useState } from 'react';
import { 
  X as XIcon, 
  Building2, 
  MapPin, 
  Mail, 
  Phone, 
  Globe, 
  Linkedin, 
  Instagram,
  Facebook,
  Twitter,
  Send, 
  UserCheck, 
  ShieldCheck, 
  ShieldAlert,
  Landmark,
  Scale, 
  Layers, 
  Home, 
  CreditCard, 
  Copy, 
  Check, 
  ExternalLink,
  MessageCircle
} from 'lucide-react';
import { Lead } from '../types';
import { useLeadStream } from '../LeadStreamContext';
import EvidenceBadge from './EvidenceBadge';

interface LeadDetailsModalProps {
  lead: Lead | null;
  onClose: () => void;
  onAddToList?: (lead: Lead) => void;
}

const pixKeyTypeLabel: Record<NonNullable<Lead['pixKeyCandidates']>[number]['keyType'], string> = {
  CNPJ: 'CNPJ',
  CPF: 'CPF',
  EMAIL: 'E-mail',
  PHONE: 'Telefone',
  EVP: 'Chave aleatória (EVP)',
};

function pixEvidenceLabel(status: NonNullable<Lead['pixKeyCandidates']>[number]['evidenceStatus']) {
  if (status === 'VALIDATED') return 'Titular validado';
  if (status === 'OBSERVED') return 'Publicada como Pix';
  if (status === 'REJECTED') return 'Rejeitada';
  return 'Candidata — não consultada';
}

function bankingScopeLabel(scope: NonNullable<Lead['bankRelationships']>[number]['scope']) {
  if (scope === 'COMPANY') return 'Empresa';
  if (scope === 'DECISION_MAKER') return 'Decisor';
  return 'Titular não atribuído';
}

function bankingEvidenceLabel(status: NonNullable<Lead['bankRelationships']>[number]['evidenceStatus']) {
  if (status === 'CONFIRMED') return 'Titularidade confirmada';
  if (status === 'TECHNICALLY_VALIDATED') return 'Chave validada; titular pendente';
  if (status === 'CONFLICTING') return 'Titular divergente';
  return 'Menção pública observada';
}

export default function LeadDetailsModal({ lead, onClose, onAddToList }: LeadDetailsModalProps) {
  const { leads } = useLeadStream();
  const [copiedField, setCopiedField] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'VISAO_GERAL' | 'DECISORES' | 'REDES_SOCIAIS' | 'RISCO_LGPD'>('VISAO_GERAL');

  if (!lead) return null;

  const copyToClipboard = (text: string, field: string) => {
    navigator.clipboard.writeText(text);
    setCopiedField(field);
    setTimeout(() => setCopiedField(null), 2000);
  };

  const cleanPhone = (lead.phone || '').replace(/[^0-9]/g, '');
  const nationalDigits = cleanPhone.startsWith('55') ? cleanPhone.slice(2) : cleanPhone;
  
  // Heurística de formato: 11 dígitos nacionais com o nono dígito de celular.
  const isMobile = (nationalDigits.length === 11 && nationalDigits[2] === '9') || (nationalDigits.length === 9 && nationalDigits[0] === '9');
  const isPJ = lead.leadType === 'PJ';

  // Busca todos os decisores e sócios da mesma empresa no contexto de leads
  const companyDecisors = leads.filter(
    (l) => l.cnpj
      && lead.cnpj
      && l.cnpj.toUpperCase().replace(/[^A-Z0-9]/g, '') === lead.cnpj.toUpperCase().replace(/[^A-Z0-9]/g, ''),
  );
  const displayDecisors = companyDecisors.length > 0 ? companyDecisors : [lead];

  return (
    <div className="fixed inset-0 z-50 overflow-hidden bg-slate-950/60 backdrop-blur-xs flex justify-end animate-in fade-in duration-200">
      <div 
        className="w-full max-w-2xl bg-white h-full shadow-2xl flex flex-col border-l border-slate-200 overflow-hidden animate-in slide-in-from-right duration-300"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="p-6 border-b border-slate-200 flex items-start justify-between bg-slate-50">
          <div className="flex items-start gap-4">
            <div className="w-14 h-14 rounded-2xl bg-blue-600 text-white font-bold text-lg flex items-center justify-center shrink-0 shadow-md">
              {lead.avatar ? (
                <img src={lead.avatar} alt={lead.name} className="w-full h-full object-cover rounded-2xl" />
              ) : (
                lead.initials || lead.name.slice(0, 2).toUpperCase()
              )}
            </div>
            <div>
              <div className="flex items-center gap-2 flex-wrap">
                <h2 className="text-xl font-bold text-slate-900 tracking-tight">{lead.name}</h2>
                <span className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-bold tracking-wide uppercase ${
                  isPJ 
                    ? 'bg-blue-100 text-blue-800 border border-blue-200' 
                    : 'bg-emerald-100 text-emerald-800 border border-emerald-200'
                }`}>
                  {isPJ ? <Building2 className="w-3 h-3" /> : <UserCheck className="w-3 h-3" />}
                  {isPJ ? 'Pessoa Jurídica (PJ)' : 'Decisor / Pessoa Física'}
                </span>
              </div>

              <p className="text-sm font-medium text-slate-600 mt-0.5">{lead.title}</p>
              
              <div className="flex items-center gap-2 mt-2 flex-wrap text-xs">
                <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-md font-semibold bg-slate-200 text-slate-800">
                  <Building2 className="w-3 h-3 text-slate-500" /> {lead.company}
                </span>
                <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-md font-medium bg-slate-100 text-slate-700">
                  <MapPin className="w-3 h-3 text-slate-400" /> {lead.location || 'Localização não informada'}
                </span>
                <span className="inline-flex items-center px-2 py-0.5 rounded-md font-bold bg-slate-900 text-white">
                  {lead.seniority || 'Senioridade não informada'}
                </span>
              </div>
            </div>
          </div>
          <button 
            onClick={onClose}
            className="p-2 text-slate-400 hover:text-slate-700 hover:bg-slate-200 rounded-xl transition-colors cursor-pointer"
          >
            <XIcon className="w-5 h-5" />
          </button>
        </div>

        {/* Abas de Navegação */}
        <div className="flex border-b border-slate-200 bg-white px-6">
          <button
            onClick={() => setActiveTab('VISAO_GERAL')}
            className={`py-3 px-3 text-xs font-bold border-b-2 transition-all cursor-pointer ${
              activeTab === 'VISAO_GERAL'
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-slate-500 hover:text-slate-900'
            }`}
          >
            Visão Geral & Contatos
          </button>
          <button
            onClick={() => setActiveTab('DECISORES')}
            className={`py-3 px-3 text-xs font-bold border-b-2 transition-all cursor-pointer ${
              activeTab === 'DECISORES'
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-slate-500 hover:text-slate-900'
            }`}
          >
            Sócios & Decisores (QSA) ({(lead.sociosDetails && lead.sociosDetails.length > 0) ? lead.sociosDetails.length : displayDecisors.length})
          </button>
          <button
            onClick={() => setActiveTab('REDES_SOCIAIS')}
            className={`py-3 px-3 text-xs font-bold border-b-2 transition-all cursor-pointer ${
              activeTab === 'REDES_SOCIAIS'
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-slate-500 hover:text-slate-900'
            }`}
          >
            Redes Sociais OSINT
          </button>
          <button
            onClick={() => setActiveTab('RISCO_LGPD')}
            className={`py-3 px-3 text-xs font-bold border-b-2 transition-all cursor-pointer ${
              activeTab === 'RISCO_LGPD'
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-slate-500 hover:text-slate-900'
            }`}
          >
            Bancário, Risco & LGPD
          </button>
        </div>

        {/* Conteúdo Dinâmico por Aba */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6 bg-slate-50/50">
          {/* ABA 1: VISÃO GERAL & CONTATOS */}
          {activeTab === 'VISAO_GERAL' && (
            <div className="space-y-5">
              {/* Card de Contatos Diretos Validados */}
              <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm space-y-3.5">
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center gap-2">
                  <Mail className="w-4 h-4 text-blue-600" /> Canais observados e estado da evidência
                </h3>

                {/* E-mail Corporativo */}
                <div className="flex items-center justify-between p-3.5 rounded-xl border border-slate-200 bg-slate-50/80">
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="w-9 h-9 rounded-lg bg-blue-100 text-blue-700 flex items-center justify-center shrink-0 font-bold">
                      @
                    </div>
                    <div className="min-w-0">
                      <div className="text-[11px] text-slate-500 font-medium">E-mail Cadastral / Corporativo</div>
                      <div className="text-xs font-bold text-slate-900 truncate flex items-center gap-2">
                        {lead.email || 'Não informado no cadastro da Receita'}
                        <EvidenceBadge status={lead.emailEvidenceStatus} compact />
                      </div>
                    </div>
                  </div>
                  {lead.email && (
                    <button
                      onClick={() => copyToClipboard(lead.email, 'email')}
                      className="p-2 text-slate-400 hover:text-slate-700 rounded-lg hover:bg-slate-200 cursor-pointer shrink-0"
                    >
                      {copiedField === 'email' ? <Check className="w-4 h-4 text-emerald-600" /> : <Copy className="w-4 h-4" />}
                    </button>
                  )}
                </div>

                {/* Telefone 1 - Canal Principal */}
                <div className="flex items-center justify-between p-3.5 rounded-xl border border-slate-200 bg-slate-50/80">
                  <div className="flex items-center gap-3 min-w-0">
                    <div className={`w-9 h-9 rounded-lg flex items-center justify-center shrink-0 ${
                      isMobile ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-200 text-slate-700'
                    }`}>
                      <Phone className="w-4 h-4" />
                    </div>
                    <div className="min-w-0">
                      <div className="text-[11px] text-slate-500 font-medium">
                        Telefone 1 · {isMobile ? 'Celular provável' : 'Fixo ou formato não móvel'}
                      </div>
                      <div className="text-xs font-bold text-slate-900 truncate flex items-center gap-2">
                        {lead.phone || 'Não informado'}
                        {lead.phone && <EvidenceBadge status={lead.phoneEvidenceStatus} compact />}
                      </div>
                    </div>
                  </div>
                  
                  <div className="flex items-center gap-2 shrink-0">
                    {lead.phone && (
                      <button
                        onClick={() => copyToClipboard(lead.phone, 'phone')}
                        className="p-2 text-slate-400 hover:text-slate-700 rounded-lg hover:bg-slate-200 cursor-pointer"
                        title="Copiar número"
                      >
                        {copiedField === 'phone' ? <Check className="w-4 h-4 text-emerald-600" /> : <Copy className="w-4 h-4" />}
                      </button>
                    )}
                    {isMobile && nationalDigits ? (
                      <a
                        href={`https://wa.me/55${nationalDigits}`}
                        target="_blank"
                        rel="noreferrer"
                        className="flex items-center gap-1 px-3 py-1.5 bg-emerald-600 text-white rounded-lg text-xs font-bold hover:bg-emerald-700 transition-colors shadow-sm cursor-pointer"
                      >
                        <MessageCircle className="w-3 h-3" /> WhatsApp (por formato)
                      </a>
                    ) : null}
                  </div>
                </div>

                {/* Telefone 2 - Secundário / Comercial */}
                {(() => {
                  const phone2 = lead.commercialPhoneSecondary;
                  if (!phone2) return null;
                  const clean = phone2.replace(/[^0-9]/g, '');
                  const national = clean.startsWith('55') ? clean.slice(2) : clean;
                  const isMobile2 = (national.length === 11 && national[2] === '9') || (national.length === 9 && national[0] === '9');
                  return (
                    <div className="flex items-center justify-between p-3.5 rounded-xl border border-indigo-200 bg-indigo-50/40">
                      <div className="flex items-center gap-3 min-w-0">
                        <div className={`w-9 h-9 rounded-lg flex items-center justify-center shrink-0 ${isMobile2 ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-200 text-slate-700'}`}>
                          <Phone className="w-4 h-4" />
                        </div>
                        <div className="min-w-0">
                          <div className="text-[11px] text-indigo-700 font-medium">
                            Telefone 2 · Comercial Secundário
                          </div>
                          <div className="text-xs font-bold text-slate-900 truncate">{phone2}</div>
                        </div>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        <button
                          onClick={() => copyToClipboard(phone2, 'phone2')}
                          className="p-2 text-slate-400 hover:text-slate-700 rounded-lg hover:bg-white cursor-pointer"
                        >
                          {copiedField === 'phone2' ? <Check className="w-4 h-4 text-emerald-600" /> : <Copy className="w-4 h-4" />}
                        </button>
                        {isMobile2 && national ? (
                          <a
                            href={`https://wa.me/55${national}`}
                            target="_blank"
                            rel="noreferrer"
                            className="flex items-center gap-1 px-3 py-1.5 bg-emerald-600 text-white rounded-lg text-xs font-bold hover:bg-emerald-700 cursor-pointer"
                          >
                            <MessageCircle className="w-3 h-3" /> Tentar no WhatsApp
                          </a>
                        ) : null}
                      </div>
                    </div>
                  );
                })()}
              </div>

              {/* Candidatos e relações bancárias preservam escopo e força da evidência. */}
              {(lead.instituicaoBancaria || lead.chavePix || (lead.pixKeyCandidates?.length ?? 0) > 0 || (lead.bankRelationships?.length ?? 0) > 0) && (
              <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm space-y-3">
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center gap-2">
                  <CreditCard className="w-4 h-4 text-emerald-600" /> Chaves Pix e vínculos bancários
                </h3>
                <p className="text-[11px] leading-5 text-slate-500">
                  Valores sempre mascarados. Um candidato não é testado no DICT sem publicação explícita e autorização operacional.
                </p>

                {(lead.bankRelationships?.length ?? 0) > 0 ? (
                  <div className="space-y-2">
                    {lead.bankRelationships?.slice(0, 6).map((relationship) => (
                      <div key={relationship.id} className={`rounded-xl border p-3 text-xs ${relationship.evidenceStatus === 'CONFLICTING' ? 'border-amber-200 bg-amber-50' : 'border-emerald-200 bg-emerald-50/50'}`}>
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <span className="font-bold text-slate-900">
                              {relationship.institutionName || (relationship.ispb ? `Instituição ISPB ${relationship.ispb}` : 'Instituição não identificada')}
                            </span>
                            <span className="mt-0.5 block text-[10px] text-slate-600">
                              {bankingScopeLabel(relationship.scope)} · {bankingEvidenceLabel(relationship.evidenceStatus)}
                            </span>
                          </div>
                          <span className="rounded-full bg-white px-2 py-1 text-[10px] font-bold text-slate-600 border border-slate-200">
                            {relationship.confidence}%
                          </span>
                        </div>
                        {(relationship.ownerName || relationship.ownerDocumentMasked) && (
                          <div className="mt-2 text-[10px] text-slate-600">
                            Titular: {relationship.ownerName || 'nome não retornado'} {relationship.ownerDocumentMasked ? `· ${relationship.ownerDocumentMasked}` : ''}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                ) : lead.instituicaoBancaria ? (
                  <div className="p-3 bg-emerald-50/50 rounded-xl border border-emerald-200 text-xs">
                    <span className="text-emerald-800 font-medium block text-[11px]">Instituição observada em fonte pública</span>
                    <span className="font-semibold text-slate-900 block mt-0.5">{lead.instituicaoBancaria}</span>
                  </div>
                ) : null}

                {(lead.pixKeyCandidates?.length ?? 0) > 0 ? (
                  <div className="grid gap-2 sm:grid-cols-2">
                    {lead.pixKeyCandidates?.slice(0, 8).map((candidate) => (
                      <div key={candidate.id} className="p-3 bg-slate-50 rounded-xl border border-slate-200 text-xs">
                        <div className="flex items-center justify-between gap-2">
                          <span className="font-semibold text-slate-700">{pixKeyTypeLabel[candidate.keyType]}</span>
                          <span className={`text-[9px] font-bold ${candidate.evidenceStatus === 'VALIDATED' ? 'text-emerald-700' : candidate.evidenceStatus === 'OBSERVED' ? 'text-blue-700' : 'text-slate-500'}`}>
                            {pixEvidenceLabel(candidate.evidenceStatus)}
                          </span>
                        </div>
                        <span className="font-mono font-bold text-slate-900 block mt-1 break-all">{candidate.maskedValue}</span>
                        <span className="text-[9px] text-slate-500 block mt-1">
                          {candidate.subjectScope === 'COMPANY' ? 'Empresa' : 'Decisor'} · {candidate.sourceProvider}
                        </span>
                      </div>
                    ))}
                  </div>
                ) : lead.chavePix ? (
                  <div className="p-3 bg-slate-50 rounded-xl border border-slate-200 text-xs">
                    <span className="text-slate-500 font-medium block text-[11px]">Chave Pix observada</span>
                    <span className="font-mono font-bold text-slate-900 block mt-0.5">{lead.chavePix}</span>
                  </div>
                ) : null}
              </div>
              )}

              {(lead.governmentRisk?.status || lead.publicSectorProfile) && (
                <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm space-y-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center gap-2">
                        <ShieldAlert className="w-4 h-4 text-amber-600" /> Inteligência governamental
                      </h3>
                      <p className="mt-1 text-[11px] leading-5 text-slate-500">
                        Consulta oficial por CNPJ. Ausência significa somente que não houve correspondência nas fontes e no momento indicados.
                      </p>
                    </div>
                    {lead.governmentRisk?.status && (
                      <span className={`shrink-0 rounded-full border px-2.5 py-1 text-[10px] font-bold ${lead.governmentRisk.has_matches ? 'border-red-200 bg-red-50 text-red-700' : 'border-emerald-200 bg-emerald-50 text-emerald-700'}`}>
                        {lead.governmentRisk.has_matches ? `${lead.governmentRisk.match_count ?? 0} ocorrência(s)` : 'Sem correspondência'}
                      </span>
                    )}
                  </div>

                  {lead.governmentRisk?.checked_sources?.length ? (
                    <div className="flex flex-wrap gap-1.5">
                      {lead.governmentRisk.checked_sources.map((source) => (
                        <span key={source} className="rounded-md border border-slate-200 bg-slate-50 px-2 py-1 text-[10px] font-semibold text-slate-600">
                          {source.replaceAll('_', ' ')}
                        </span>
                      ))}
                    </div>
                  ) : null}

                  {(lead.governmentRisk?.records?.length ?? 0) > 0 && (
                    <div className="space-y-2">
                      {lead.governmentRisk?.records?.slice(0, 6).map((record, index) => (
                        <div key={`${record.source}-${record.record_id ?? index}`} className="rounded-xl border border-red-100 bg-red-50/40 p-3 text-xs">
                          <div className="flex items-start justify-between gap-3">
                            <div>
                              <span className="font-bold text-slate-900">{record.sanction_type || record.reason || record.status || 'Registro governamental'}</span>
                              <span className="mt-0.5 block text-[10px] text-slate-600">
                                {record.source.replaceAll('_', ' ')}{record.sanctioning_organ || record.responsible_organ ? ` · ${record.sanctioning_organ || record.responsible_organ}` : ''}
                              </span>
                            </div>
                            {record.publication_url ? (
                              <a href={record.publication_url} target="_blank" rel="noreferrer" aria-label="Abrir publicação oficial" className="rounded-lg p-1.5 text-slate-500 hover:bg-white hover:text-indigo-700">
                                <ExternalLink className="h-3.5 w-3.5" />
                              </a>
                            ) : null}
                          </div>
                          {(record.starts_on || record.ends_on || record.process_number) && (
                            <span className="mt-2 block text-[10px] text-slate-500">
                              {[record.starts_on && `Início: ${record.starts_on}`, record.ends_on && `Fim: ${record.ends_on}`, record.process_number && `Processo: ${record.process_number}`].filter(Boolean).join(' · ')}
                            </span>
                          )}
                        </div>
                      ))}
                    </div>
                  )}

                  {lead.publicSectorProfile && (
                    <div className="border-t border-slate-100 pt-4">
                      <div className="flex items-center justify-between gap-3">
                        <span className="flex items-center gap-2 text-xs font-bold text-slate-800">
                          <Landmark className="h-4 w-4 text-indigo-600" /> Contratos federais
                        </span>
                        <span className="text-[10px] font-semibold text-slate-500">
                          {lead.publicSectorProfile.contract_count ?? 0} na página consultada
                        </span>
                      </div>
                      {(lead.publicSectorProfile.contracts?.length ?? 0) > 0 ? (
                        <div className="mt-2 space-y-2">
                          {lead.publicSectorProfile.contracts?.slice(0, 5).map((contract, index) => (
                            <div key={`${contract.record_id ?? contract.number ?? index}`} className="rounded-xl border border-indigo-100 bg-indigo-50/40 p-3 text-xs">
                              <span className="font-bold text-slate-900">{contract.number ? `Contrato ${contract.number}` : 'Contrato federal'}</span>
                              <span className="mt-0.5 block text-[11px] leading-5 text-slate-700">{contract.object || 'Objeto não informado'}</span>
                              <span className="mt-1 block text-[10px] text-slate-500">
                                {[contract.managing_unit, contract.status, contract.final_value != null && `R$ ${Number(contract.final_value).toLocaleString('pt-BR', { minimumFractionDigits: 2 })}`].filter(Boolean).join(' · ')}
                              </span>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <p className="mt-2 text-[11px] text-slate-500">Nenhum contrato federal localizado na página consultada.</p>
                      )}
                    </div>
                  )}

                  <div className="text-[10px] text-slate-500">
                    Atualizado em {lead.governmentRiskObservedAt || lead.publicSectorObservedAt ? new Date(lead.governmentRiskObservedAt || lead.publicSectorObservedAt || '').toLocaleString('pt-BR') : 'data não informada'} · Fonte: Portal da Transparência / CGU
                  </div>
                </div>
              )}

              {/* Dados Cadastrais e Fiscais da Empresa */}
              <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm space-y-4">
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center gap-2">
                  <Building2 className="w-4 h-4 text-indigo-600" /> Dados Fiscais e Cadastrais (RFB)
                </h3>

                <div className="grid grid-cols-2 gap-3 text-xs">
                  <div className="p-3 bg-slate-50 rounded-xl border border-slate-200">
                    <span className="text-slate-500 font-medium block text-[11px]">CNPJ</span>
                    <span className="font-mono font-bold text-slate-900 block mt-0.5">{lead.cnpj || 'Não informado'}</span>
                  </div>

                  <div className="p-3 bg-slate-50 rounded-xl border border-slate-200">
                    <span className="text-slate-500 font-medium block text-[11px]">Situação Cadastral</span>
                    <span className="font-bold text-slate-900 block mt-0.5">{lead.situacaoCadastral || 'Não informada'}</span>
                  </div>

                  {lead.nomeFantasia && (
                    <div className="p-3 bg-indigo-50/60 rounded-xl border border-indigo-200 col-span-2">
                      <span className="text-indigo-800 font-semibold block text-[11px]">Nome Fantasia</span>
                      <span className="font-extrabold text-indigo-950 block mt-0.5 text-sm">{lead.nomeFantasia}</span>
                    </div>
                  )}

                  <div className="p-3 bg-slate-50 rounded-xl border border-slate-200 col-span-2">
                    <span className="text-slate-500 font-medium block text-[11px]">Razão social cadastrada</span>
                    <span className="font-bold text-slate-900 block mt-0.5">{lead.razaoSocial || 'Não informada'}</span>
                  </div>

                  <div className="p-3 bg-slate-50 rounded-xl border border-slate-200 col-span-2">
                    <span className="text-slate-500 font-medium block text-[11px]">Atividade Econômica Principal (CNAE)</span>
                    <span className="font-bold text-slate-800 block mt-0.5 text-xs">{lead.cnae || 'Não informado'}</span>
                  </div>

                  <div className="p-3 bg-slate-50 rounded-xl border border-slate-200">
                    <span className="text-slate-500 font-medium block text-[11px]">Porte da Empresa</span>
                    <span className="font-bold text-slate-900 block mt-0.5">{lead.companySize || 'Não informado'}</span>
                  </div>

                  <div className="p-3 bg-slate-50 rounded-xl border border-slate-200">
                    <span className="text-slate-500 font-medium block text-[11px]">Capital Social</span>
                    <span className="font-bold text-slate-900 block mt-0.5">{lead.capitalSocial || 'Não informado'}</span>
                  </div>

                  <div className="p-3 bg-slate-50 rounded-xl border border-slate-200">
                    <span className="text-slate-500 font-medium block text-[11px]">Simples Nacional</span>
                    <span className={`font-bold block mt-0.5 ${lead.opcaoSimples === 'SIM' ? 'text-emerald-700' : 'text-slate-800'}`}>
                      {lead.opcaoSimples === 'SIM' ? 'Optante pelo Simples' : lead.opcaoSimples === 'NÃO' ? 'Não optante' : 'Não informado'}
                    </span>
                  </div>

                  <div className="p-3 bg-slate-50 rounded-xl border border-slate-200">
                    <span className="text-slate-500 font-medium block text-[11px]">MEI (Microempreendedor)</span>
                    <span className="font-bold text-slate-800 block mt-0.5">
                      {lead.opcaoMei === 'SIM' ? 'Optante pelo MEI' : lead.opcaoMei === 'NÃO' ? 'Não optante' : 'Não informado'}
                    </span>
                  </div>

                  {/* Endereço Cadastral */}
                  {(lead.logradouro || lead.bairro || lead.municipio) && (
                    <div className="p-3 bg-slate-50 rounded-xl border border-slate-200 col-span-2">
                      <span className="text-slate-500 font-medium block text-[11px] flex items-center gap-1">
                        <Home className="w-3 h-3 text-slate-400" /> Endereço Cadastral
                      </span>
                      <span className="font-semibold text-slate-800 block mt-0.5 text-xs">
                        {[lead.logradouro, lead.numero, lead.bairro, lead.cep, lead.municipio, lead.uf].filter(Boolean).join(', ')}
                      </span>
                    </div>
                  )}
                </div>

                {/* CNAEs Secundários */}
                {lead.cnaesSecundarios && lead.cnaesSecundarios.length > 0 && (
                  <div className="pt-3 border-t border-slate-100 space-y-2">
                    <span className="text-xs font-bold text-slate-700 flex items-center gap-1.5">
                      <Layers className="w-3.5 h-3.5 text-blue-600" /> Atividades Econômicas Secundárias ({lead.cnaesSecundarios.length})
                    </span>
                    <div className="flex flex-wrap gap-1.5 max-h-48 overflow-y-auto">
                      {lead.cnaesSecundarios.map((sec: any, idx: number) => {
                        const codigo = typeof sec === 'string' ? sec : sec?.codigo || '';
                        const desc = typeof sec === 'object' ? sec?.descricao : '';
                        return (
                          <span key={idx} className="px-2.5 py-1 bg-slate-100 border border-slate-200 text-slate-700 rounded-lg text-[11px] font-medium">
                            <strong>{codigo}</strong> {desc && `- ${desc}`}
                          </span>
                        );
                      })}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* ABA 2: SÓCIOS & DECISORES (QSA) */}
          {activeTab === 'DECISORES' && (
            <div className="space-y-4">
              <div className="bg-blue-50/80 p-4 rounded-2xl border border-blue-200 text-xs text-blue-900 flex items-start gap-2.5">
                <ShieldCheck className="w-5 h-5 text-blue-600 shrink-0 mt-0.5" />
                <div>
                  <span className="font-bold block">Quadro de Sócios e Administradores (QSA)</span>
                  A identidade e a qualificação vêm da fonte cadastrada. O papel de compra é uma classificação inferida e deve ser revisado.
                </div>
              </div>

              {/* 1) Decisores vindos do enriquecimento 360 via sociosDetails */}
              {lead.sociosDetails && lead.sociosDetails.length > 0 ? (
                lead.sociosDetails.map((socio, idx) => {
                  const initials = (socio.nome || '').split(/\s+/).slice(0, 2).map(p => p[0] || '').join('').toUpperCase() || 'NA';
                  const phone1Clean = (socio.telefone || '').replace(/[^0-9]/g, '');
                  const phone1National = phone1Clean.startsWith('55') ? phone1Clean.slice(2) : phone1Clean;
                  const isMobile1 = (phone1National.length === 11 && phone1National[2] === '9') || (phone1National.length === 9 && phone1National[0] === '9');
                  const phone2Clean = (socio.telefoneSecundario || '').replace(/[^0-9]/g, '');
                  const phone2National = phone2Clean.startsWith('55') ? phone2Clean.slice(2) : phone2Clean;
                  const isMobile2 = (phone2National.length === 11 && phone2National[2] === '9') || (phone2National.length === 9 && phone2National[0] === '9');

                  return (
                    <div key={`socio-${idx}`} className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm space-y-4">
                      {/* Header */}
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <div className="w-12 h-12 rounded-2xl bg-blue-100 text-blue-700 flex items-center justify-center font-bold text-base shrink-0">
                            {initials}
                          </div>
                          <div className="min-w-0">
                            <h4 className="text-sm font-bold text-slate-950 truncate">{socio.nome}</h4>
                            <p className="text-xs text-slate-500 font-medium truncate">
                              {socio.cargo || socio.qualificacao || 'Cargo / qualificação não informada'}
                            </p>
                          </div>
                        </div>
                        <span className="px-3 py-1 rounded-full text-xs font-bold bg-blue-100 text-blue-800 border border-blue-200 shrink-0">
                          {socio.papelCompra || 'Não classificado'}
                        </span>
                      </div>

                      {/* Dados cadastrais + Região */}
                      <div className="grid grid-cols-2 gap-2 text-xs border-t border-slate-100 pt-3">
                        <div className="p-2.5 bg-slate-50 rounded-xl border border-slate-200">
                          <span className="text-slate-400 block text-[10px] uppercase font-bold">Qualificação RFB</span>
                          <span className="font-semibold text-slate-900 mt-0.5 block">
                            {socio.qualificacao || 'Não informada'}
                          </span>
                        </div>
                        <div className="p-2.5 bg-slate-50 rounded-xl border border-slate-200">
                          <span className="text-slate-400 block text-[10px] uppercase font-bold">Papel Compra</span>
                          <span className="font-semibold text-blue-700 mt-0.5 block">
                            {socio.papelCompra || 'Não classificado'}
                          </span>
                        </div>
                        <div className="p-2.5 bg-slate-50 rounded-xl border border-slate-200">
                          <span className="text-slate-400 block text-[10px] uppercase font-bold">Faixa Etária</span>
                          <span className="font-semibold text-slate-900 mt-0.5 block">{socio.faixaEtaria || '—'}</span>
                        </div>
                        <div className="p-2.5 bg-slate-50 rounded-xl border border-slate-200">
                          <span className="text-slate-400 block text-[10px] uppercase font-bold">Entrada Sociedade</span>
                          <span className="font-semibold text-slate-900 mt-0.5 block">{socio.dataEntrada || '—'}</span>
                        </div>
                        <div className="p-2.5 bg-slate-50 rounded-xl border border-slate-200 col-span-2">
                          <span className="text-slate-400 block text-[10px] uppercase font-bold">CPF Mascarado • Região Fiscal</span>
                          <span className="font-mono font-semibold text-slate-900 mt-0.5 block">
                            {socio.cpfMascarado || 'CPF não informado'} • {socio.regiaoFiscal || '—'}
                          </span>
                        </div>
                      </div>

                      {/* Email + 2 Telefones + WhatsApp */}
                      <div className="space-y-2 pt-1">
                        <h5 className="text-[10px] font-bold uppercase tracking-wider text-slate-500 flex items-center gap-1">
                          <Mail className="w-3.5 h-3.5" /> Contatos do Decisor
                          {socio.whatsappAtivo && (
                            <span className="ml-2 px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 text-[9px] font-extrabold border border-emerald-200">
                              WhatsApp informado na fonte
                            </span>
                          )}
                        </h5>

                        {socio.email ? (
                          <div className="flex items-center justify-between p-2.5 rounded-xl border border-slate-200 bg-blue-50/40">
                            <div className="flex items-center gap-2 min-w-0">
                              <div className="w-7 h-7 rounded-lg bg-blue-100 text-blue-700 flex items-center justify-center shrink-0 font-bold text-[11px]">@</div>
                              <div className="min-w-0">
                                <div className="text-[10px] text-blue-700 font-medium">E-mail (corporativo / atribuído)</div>
                                <div className="text-xs font-bold text-slate-900 truncate">{socio.email}</div>
                              </div>
                            </div>
                            <button
                              onClick={() => copyToClipboard(socio.email!, `socio-email-${idx}`)}
                              className="p-1.5 text-slate-400 hover:text-slate-700 rounded-lg hover:bg-white cursor-pointer shrink-0"
                            >
                              {copiedField === `socio-email-${idx}` ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
                            </button>
                          </div>
                        ) : (
                          <div className="p-2.5 rounded-xl border border-slate-200 bg-slate-50 text-[11px] text-slate-500 font-medium flex items-center gap-2">
                            <Mail className="w-3.5 h-3.5 text-slate-400" /> E-mail do decisor: não atribuído nesta execução.
                          </div>
                        )}

                        {/* Telefone 1 do decisor */}
                        {socio.telefone ? (
                          <div className="flex items-center justify-between p-2.5 rounded-xl border border-slate-200 bg-slate-50">
                            <div className="flex items-center gap-2 min-w-0">
                              <div className={`w-7 h-7 rounded-lg flex items-center justify-center shrink-0 ${isMobile1 ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-200 text-slate-700'}`}>
                                <Phone className="w-3.5 h-3.5" />
                              </div>
                              <div className="min-w-0">
                                <div className="text-[10px] text-slate-500 font-medium">Telefone 1 · {isMobile1 ? 'Celular' : 'Fixo'}</div>
                                <div className="text-xs font-bold text-slate-900 truncate">{socio.telefone}</div>
                              </div>
                            </div>
                            <div className="flex items-center gap-1.5 shrink-0">
                              <button
                                onClick={() => copyToClipboard(socio.telefone!, `socio-tel1-${idx}`)}
                                className="p-1.5 text-slate-400 hover:text-slate-700 rounded-lg hover:bg-white cursor-pointer"
                              >
                                {copiedField === `socio-tel1-${idx}` ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
                              </button>
                              {(socio.whatsappLink || isMobile1) && (
                                <a
                                  href={socio.whatsappLink || `https://wa.me/55${phone1National}`}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="flex items-center gap-1 px-2.5 py-1 bg-emerald-600 text-white rounded-lg text-[10px] font-bold hover:bg-emerald-700 cursor-pointer"
                                >
                                  <MessageCircle className="w-3 h-3" /> Tentar no WhatsApp
                                </a>
                              )}
                            </div>
                          </div>
                        ) : null}

                        {/* Telefone 2 do decisor */}
                        {socio.telefoneSecundario ? (
                          <div className="flex items-center justify-between p-2.5 rounded-xl border border-indigo-200 bg-indigo-50/40">
                            <div className="flex items-center gap-2 min-w-0">
                              <div className={`w-7 h-7 rounded-lg flex items-center justify-center shrink-0 ${isMobile2 ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-200 text-slate-700'}`}>
                                <Phone className="w-3.5 h-3.5" />
                              </div>
                              <div className="min-w-0">
                                <div className="text-[10px] text-indigo-700 font-medium">Telefone 2 · Secundário</div>
                                <div className="text-xs font-bold text-slate-900 truncate">{socio.telefoneSecundario}</div>
                              </div>
                            </div>
                            <div className="flex items-center gap-1.5 shrink-0">
                              <button
                                onClick={() => copyToClipboard(socio.telefoneSecundario!, `socio-tel2-${idx}`)}
                                className="p-1.5 text-slate-400 hover:text-slate-700 rounded-lg hover:bg-white cursor-pointer"
                              >
                                {copiedField === `socio-tel2-${idx}` ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
                              </button>
                              {isMobile2 && phone2National ? (
                                <a
                                  href={`https://wa.me/55${phone2National}`}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="flex items-center gap-1 px-2.5 py-1 bg-emerald-600 text-white rounded-lg text-[10px] font-bold hover:bg-emerald-700 cursor-pointer"
                                >
                                  <MessageCircle className="w-3 h-3" /> Tentar no WhatsApp
                                </a>
                              ) : null}
                            </div>
                          </div>
                        ) : null}

                        {!socio.telefone && !socio.telefoneSecundario && (
                          <div className="p-2.5 rounded-xl border border-slate-200 bg-slate-50 text-[11px] text-slate-500 font-medium flex items-center gap-2">
                            <Phone className="w-3.5 h-3.5 text-slate-400" /> Nenhum telefone atribuído ao decisor nesta execução.
                          </div>
                        )}
                      </div>

                      {/* Redes Sociais do Decisor (4) */}
                      <div className="space-y-2 pt-1">
                        <h5 className="text-[10px] font-bold uppercase tracking-wider text-slate-500 flex items-center gap-1">
                          <Globe className="w-3.5 h-3.5" /> Redes Sociais · OSINT atribuídas ao decisor
                        </h5>
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                          {/* LinkedIn Decisor */}
                          {socio.linkedinUrl ? (
                            <a
                              href={socio.linkedinUrl}
                              target="_blank"
                              rel="noreferrer"
                              className="flex items-center gap-2 p-2.5 rounded-xl border border-blue-200 bg-blue-50/40 hover:bg-blue-50 transition-colors min-w-0"
                            >
                              <Linkedin className="w-4 h-4 text-[#0A66C2] fill-current shrink-0" />
                              <div className="min-w-0">
                                <div className="text-[10px] text-blue-700 font-bold">LinkedIn</div>
                                <div className="text-[11px] text-slate-800 font-semibold truncate">{socio.linkedinUrl.replace(/^https?:\/\/(www\.)?linkedin\.com\/in\//, '/in/').slice(0, 32)}</div>
                              </div>
                              <ExternalLink className="w-3 h-3 text-slate-400 ml-auto shrink-0" />
                            </a>
                          ) : (
                            <div className="flex items-center gap-2 p-2.5 rounded-xl border border-slate-200 bg-slate-50 text-[11px] text-slate-500">
                              <Linkedin className="w-4 h-4 text-slate-400 shrink-0" />
                              <span>LinkedIn: não encontrado</span>
                            </div>
                          )}

                          {/* Instagram Decisor */}
                          {socio.instagramUrl ? (
                            <a
                              href={socio.instagramUrl}
                              target="_blank"
                              rel="noreferrer"
                              className="flex items-center gap-2 p-2.5 rounded-xl border border-pink-200 bg-pink-50/40 hover:bg-pink-50 transition-colors min-w-0"
                            >
                              <Instagram className="w-4 h-4 text-pink-600 shrink-0" />
                              <div className="min-w-0">
                                <div className="text-[10px] text-pink-700 font-bold">Instagram</div>
                                <div className="text-[11px] text-slate-800 font-semibold truncate">@{(socio.instagramUrl.match(/\/([^\/?#]+)[^\/]*$/) || [])[1] || socio.instagramUrl.slice(-28)}</div>
                              </div>
                              <ExternalLink className="w-3 h-3 text-slate-400 ml-auto shrink-0" />
                            </a>
                          ) : (
                            <div className="flex items-center gap-2 p-2.5 rounded-xl border border-slate-200 bg-slate-50 text-[11px] text-slate-500">
                              <Instagram className="w-4 h-4 text-slate-400 shrink-0" />
                              <span>Instagram: não encontrado</span>
                            </div>
                          )}

                          {/* Facebook Decisor */}
                          {socio.facebookUrl ? (
                            <a
                              href={socio.facebookUrl}
                              target="_blank"
                              rel="noreferrer"
                              className="flex items-center gap-2 p-2.5 rounded-xl border border-blue-200 bg-blue-50/40 hover:bg-blue-50 transition-colors min-w-0"
                            >
                              <Facebook className="w-4 h-4 text-[#1877F2] fill-current shrink-0" />
                              <div className="min-w-0">
                                <div className="text-[10px] text-blue-700 font-bold">Facebook</div>
                                <div className="text-[11px] text-slate-800 font-semibold truncate">{(socio.facebookUrl.match(/(?:facebook\.com|fb\.com)\/([^/?#]+)/i) || [])[1] || socio.facebookUrl.slice(-28)}</div>
                              </div>
                              <ExternalLink className="w-3 h-3 text-slate-400 ml-auto shrink-0" />
                            </a>
                          ) : (
                            <div className="flex items-center gap-2 p-2.5 rounded-xl border border-slate-200 bg-slate-50 text-[11px] text-slate-500">
                              <Facebook className="w-4 h-4 text-slate-400 shrink-0" />
                              <span>Facebook: não encontrado</span>
                            </div>
                          )}

                          {/* X / Twitter Decisor */}
                          {socio.twitterUrl ? (
                            <a
                              href={socio.twitterUrl}
                              target="_blank"
                              rel="noreferrer"
                              className="flex items-center gap-2 p-2.5 rounded-xl border border-slate-900/20 bg-slate-900/5 hover:bg-slate-900/10 transition-colors min-w-0"
                            >
                              <Twitter className="w-4 h-4 text-slate-900 fill-current shrink-0" />
                              <div className="min-w-0">
                                <div className="text-[10px] text-slate-700 font-bold">X / Twitter</div>
                                <div className="text-[11px] text-slate-900 font-semibold truncate">@{(socio.twitterUrl.match(/\/([^\/?#]+)[^\/]*$/) || [])[1] || socio.twitterUrl.slice(-28)}</div>
                              </div>
                              <ExternalLink className="w-3 h-3 text-slate-400 ml-auto shrink-0" />
                            </a>
                          ) : (
                            <div className="flex items-center gap-2 p-2.5 rounded-xl border border-slate-200 bg-slate-50 text-[11px] text-slate-500">
                              <Twitter className="w-4 h-4 text-slate-400 shrink-0" />
                              <span>X / Twitter: não encontrado</span>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })
              ) : (
                /* 2) Fallback: decisores buscados em outros leads PF do mesmo CNPJ (legado) */
                displayDecisors.map((decisor, idx) => (
                  <div key={decisor.id || idx} className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm space-y-4">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div className="w-12 h-12 rounded-2xl bg-blue-100 text-blue-700 flex items-center justify-center font-bold text-base">
                          {decisor.initials || decisor.name.slice(0, 2).toUpperCase()}
                        </div>
                        <div>
                          <h4 className="text-sm font-bold text-slate-950">{decisor.name}</h4>
                          <p className="text-xs text-slate-500 font-medium">
                            {decisor.qualificacaoRfb || decisor.title || 'Qualificação não informada'}
                          </p>
                        </div>
                      </div>
                      <span className="px-3 py-1 rounded-full text-xs font-bold bg-blue-100 text-blue-800 border border-blue-200">
                        {decisor.papelCompra || 'Papel não classificado'}
                      </span>
                    </div>

                    <div className="grid grid-cols-2 gap-2 text-xs pt-3 border-t border-slate-100 text-slate-700">
                      <div className="p-2.5 bg-slate-50 rounded-xl border border-slate-200">
                        <span className="text-slate-400 block text-[10px] uppercase font-bold">Qualificação RFB</span>
                        <span className="font-semibold text-slate-900 mt-0.5 block">
                          {decisor.qualificacaoRfb || 'Não informada'}
                        </span>
                      </div>
                      <div className="p-2.5 bg-slate-50 rounded-xl border border-slate-200">
                        <span className="text-slate-400 block text-[10px] uppercase font-bold">Papel de compra inferido</span>
                        <span className="font-semibold text-blue-700 mt-0.5 block">
                          {decisor.papelCompra || 'Não classificado'}
                        </span>
                      </div>
                      <div className="p-2.5 bg-slate-50 rounded-xl border border-slate-200">
                        <span className="text-slate-400 block text-[10px] uppercase font-bold">Faixa etária cadastrada</span>
                        <span className="font-semibold text-slate-900 mt-0.5 block">{decisor.faixaEtaria || '—'}</span>
                      </div>
                      <div className="p-2.5 bg-slate-50 rounded-xl border border-slate-200">
                        <span className="text-slate-400 block text-[10px] uppercase font-bold">Entrada na Sociedade</span>
                        <span className="font-semibold text-slate-900 mt-0.5 block">{decisor.dataEntradaSociedade || '—'}</span>
                      </div>
                      <div className="p-2.5 bg-slate-50 rounded-xl border border-slate-200 col-span-2">
                        <span className="text-slate-400 block text-[10px] uppercase font-bold">CPF Mascarado & Região Fiscal</span>
                        <span className="font-mono font-semibold text-slate-900 mt-0.5 block">
                          {decisor.cpf || 'CPF não informado'} • {decisor.regiaoFiscal || '—'}
                        </span>
                      </div>
                      {(decisor.email || decisor.phone) && (
                        <div className="p-2.5 bg-slate-50 rounded-xl border border-slate-200 col-span-2 flex items-center justify-between">
                          <div className="space-y-0.5">
                            <span className="text-slate-400 block text-[10px] uppercase font-bold">Meios de Contato</span>
                            <span className="font-medium text-slate-800 block text-xs">
                              {decisor.email && (
                                <span className="inline-flex items-center gap-1 mr-3">
                                  <Mail className="h-3 w-3 text-slate-400" />
                                  {decisor.email}
                                </span>
                              )}
                              {decisor.phone && (
                                <span className="inline-flex items-center gap-1">
                                  <Phone className="h-3 w-3 text-slate-400" />
                                  {decisor.phone}
                                </span>
                              )}
                            </span>
                          </div>
                          {decisor.phone && (
                            <a
                              href={`https://wa.me/${decisor.phone.replace(/\D/g, '').startsWith('55') ? decisor.phone.replace(/\D/g, '') : `55${decisor.phone.replace(/\D/g, '')}`}`}
                              target="_blank"
                              rel="noreferrer"
                              className="px-2.5 py-1 bg-emerald-600 text-white rounded-lg text-[11px] font-bold hover:bg-emerald-700 flex items-center gap-1 cursor-pointer"
                            >
                              <Send className="w-3 h-3" /> Tentar no WhatsApp
                            </a>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                ))
              )}
            </div>
          )}

          {/* ABA 3: REDES SOCIAIS OSINT */}
          {activeTab === 'REDES_SOCIAIS' && (
            <div className="space-y-4">
              <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-xs leading-relaxed text-amber-900">
                Os perfis abaixo são candidatos observados em busca pública e vinculados por nome, empresa e localização. Revise o perfil antes de utilizá-lo como contato confirmado.
              </div>
              <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm space-y-4">
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center gap-2">
                  <Globe className="w-4 h-4 text-blue-600" /> Presença Digital & Perfis Comerciais
                </h3>

                {/* LinkedIn Decisor */}
                {lead.linkedinUrl ? (
                  <a
                    href={lead.linkedinUrl}
                    target="_blank"
                    rel="noreferrer"
                    className="flex items-center justify-between p-3.5 rounded-xl border border-blue-200 bg-blue-50/50 hover:bg-blue-50 transition-colors"
                  >
                    <div className="flex items-center gap-3">
                      <Linkedin className="w-5 h-5 text-[#0A66C2] fill-current" />
                      <div>
                        <p className="text-xs font-bold text-slate-900">LinkedIn candidato do decisor</p>
                        <p className="text-[11px] text-blue-600 truncate">{lead.linkedinUrl}</p>
                      </div>
                    </div>
                    <ExternalLink className="w-4 h-4 text-slate-400" />
                  </a>
                ) : (
                  <div className="p-3.5 rounded-xl border border-slate-200 bg-slate-50 text-xs text-slate-500 flex items-center gap-3">
                    <Linkedin className="w-5 h-5 text-slate-400" />
                    <span>Nenhum candidato de LinkedIn suficientemente corroborado foi encontrado.</span>
                  </div>
                )}

                {/* Instagram Decisor */}
                {lead.instagramDecisorUrl ? (
                  <a
                    href={lead.instagramDecisorUrl}
                    target="_blank"
                    rel="noreferrer"
                    className="flex items-center justify-between p-3.5 rounded-xl border border-pink-200 bg-pink-50/50 hover:bg-pink-50 transition-colors"
                  >
                    <div className="flex items-center gap-3">
                      <Instagram className="w-5 h-5 text-pink-600" />
                      <div>
                        <p className="text-xs font-bold text-slate-900">Instagram candidato do decisor</p>
                        <p className="text-[11px] text-pink-600 truncate">{lead.instagramDecisorUrl}</p>
                      </div>
                    </div>
                    <ExternalLink className="w-4 h-4 text-slate-400" />
                  </a>
                ) : (
                  <div className="p-3.5 rounded-xl border border-slate-200 bg-slate-50 text-xs text-slate-500 flex items-center gap-3">
                    <Instagram className="w-5 h-5 text-slate-400" />
                    <span>Nenhum candidato de Instagram suficientemente corroborado foi encontrado.</span>
                  </div>
                )}

                {/* Facebook Decisor */}
                {lead.facebookUrl ? (
                  <a
                    href={lead.facebookUrl}
                    target="_blank"
                    rel="noreferrer"
                    className="flex items-center justify-between p-3.5 rounded-xl border border-blue-200 bg-blue-50/50 hover:bg-blue-50 transition-colors"
                  >
                    <div className="flex items-center gap-3">
                      <Facebook className="w-5 h-5 text-[#1877F2] fill-current" />
                      <div>
                        <p className="text-xs font-bold text-slate-900">Facebook candidato do decisor</p>
                        <p className="text-[11px] text-blue-600 truncate">{lead.facebookUrl}</p>
                      </div>
                    </div>
                    <ExternalLink className="w-4 h-4 text-slate-400" />
                  </a>
                ) : null}

                {/* LinkedIn da Empresa */}
                {lead.companyLinkedinUrl ? (
                  <a
                    href={lead.companyLinkedinUrl}
                    target="_blank"
                    rel="noreferrer"
                    className="flex items-center justify-between p-3.5 rounded-xl border border-blue-200 bg-blue-50/50 hover:bg-blue-50 transition-colors"
                  >
                    <div className="flex items-center gap-3">
                      <Linkedin className="w-5 h-5 text-[#0A66C2] fill-current" />
                      <div>
                        <p className="text-xs font-bold text-slate-900">LinkedIn candidato da empresa</p>
                        <p className="text-[11px] text-blue-600 truncate">{lead.companyLinkedinUrl}</p>
                      </div>
                    </div>
                    <ExternalLink className="w-4 h-4 text-slate-400" />
                  </a>
                ) : (
                  <div className="p-3.5 rounded-xl border border-slate-200 bg-slate-50 text-xs text-slate-500 flex items-center gap-3">
                    <Linkedin className="w-5 h-5 text-slate-400" />
                    <span>Nenhum candidato de LinkedIn suficientemente corroborado foi encontrado.</span>
                  </div>
                )}

                {/* Instagram Comercial */}
                {lead.companyInstagramUrl ? (
                  <a
                    href={lead.companyInstagramUrl}
                    target="_blank"
                    rel="noreferrer"
                    className="flex items-center justify-between p-3.5 rounded-xl border border-pink-200 bg-pink-50/50 hover:bg-pink-50 transition-colors"
                  >
                    <div className="flex items-center gap-3">
                      <Instagram className="w-5 h-5 text-pink-600" />
                      <div>
                        <p className="text-xs font-bold text-slate-900">Instagram candidato da empresa</p>
                        <p className="text-[11px] text-pink-600 truncate">{lead.companyInstagramUrl}</p>
                      </div>
                    </div>
                    <ExternalLink className="w-4 h-4 text-slate-400" />
                  </a>
                ) : (
                  <div className="p-3.5 rounded-xl border border-slate-200 bg-slate-50 text-xs text-slate-500 flex items-center gap-3">
                    <Instagram className="w-5 h-5 text-slate-400" />
                    <span>Nenhum candidato de Instagram suficientemente corroborado foi encontrado.</span>
                  </div>
                )}

                {/* Facebook da Empresa */}
                {lead.companyFacebookUrl ? (
                  <a
                    href={lead.companyFacebookUrl}
                    target="_blank"
                    rel="noreferrer"
                    className="flex items-center justify-between p-3.5 rounded-xl border border-blue-200 bg-blue-50/50 hover:bg-blue-50 transition-colors"
                  >
                    <div className="flex items-center gap-3">
                      <Facebook className="w-5 h-5 text-[#1877F2] fill-current" />
                      <div>
                        <p className="text-xs font-bold text-slate-900">Facebook candidato da empresa</p>
                        <p className="text-[11px] text-blue-600 truncate">{lead.companyFacebookUrl}</p>
                      </div>
                    </div>
                    <ExternalLink className="w-4 h-4 text-slate-400" />
                  </a>
                ) : (
                  <div className="p-3.5 rounded-xl border border-slate-200 bg-slate-50 text-xs text-slate-500 flex items-center gap-3">
                    <Facebook className="w-5 h-5 text-slate-400" />
                    <span>Nenhum candidato de Facebook suficientemente corroborado foi encontrado.</span>
                  </div>
                )}

                {/* X / Twitter da Empresa */}
                {lead.companyTwitterUrl ? (
                  <a
                    href={lead.companyTwitterUrl}
                    target="_blank"
                    rel="noreferrer"
                    className="flex items-center justify-between p-3.5 rounded-xl border border-slate-900/20 bg-slate-900/5 hover:bg-slate-900/10 transition-colors"
                  >
                    <div className="flex items-center gap-3">
                      <Twitter className="w-5 h-5 text-slate-900 fill-current" />
                      <div>
                        <p className="text-xs font-bold text-slate-900">X / Twitter candidato da empresa</p>
                        <p className="text-[11px] text-slate-700 truncate">{lead.companyTwitterUrl}</p>
                      </div>
                    </div>
                    <ExternalLink className="w-4 h-4 text-slate-400" />
                  </a>
                ) : (
                  <div className="p-3.5 rounded-xl border border-slate-200 bg-slate-50 text-xs text-slate-500 flex items-center gap-3">
                    <Twitter className="w-5 h-5 text-slate-400" />
                    <span>Nenhum candidato de X / Twitter suficientemente corroborado foi encontrado.</span>
                  </div>
                )}

                {/* Website Institucional */}
                {lead.domain ? (
                  <a
                    href={`https://${lead.domain}`}
                    target="_blank"
                    rel="noreferrer"
                    className="flex items-center justify-between p-3.5 rounded-xl border border-slate-200 bg-slate-50/80 hover:bg-slate-100 transition-colors"
                  >
                    <div className="flex items-center gap-3">
                      <Globe className="w-5 h-5 text-indigo-600" />
                      <div>
                        <p className="text-xs font-bold text-slate-900">Website informado</p>
                        <p className="text-[11px] text-slate-600">{lead.domain}</p>
                      </div>
                    </div>
                    <ExternalLink className="w-4 h-4 text-slate-400" />
                  </a>
                ) : (
                  <div className="p-3.5 rounded-xl border border-slate-200 bg-slate-50 text-xs text-slate-500 flex items-center gap-3">
                    <Globe className="w-5 h-5 text-slate-400" />
                    <span>Website da empresa não informado.</span>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* ABA 4: RISCO & LGPD */}
          {activeTab === 'RISCO_LGPD' && (
            <div className="space-y-4">
              <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm space-y-4">
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center gap-2">
                  <Scale className="w-4 h-4 text-indigo-600" /> Governança, risco e dados restritos
                </h3>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                  <div className="p-3.5 bg-slate-50 rounded-xl border border-slate-200">
                    <span className="text-slate-500 font-medium block text-[11px]">Dívida Ativa PGFN / FGTS</span>
                    <span className="font-bold text-slate-900 block mt-0.5 flex items-center gap-1">
                      {lead.pgfnStatus || 'Não consultado'}
                    </span>
                  </div>

                  <div className="p-3.5 bg-slate-50 rounded-xl border border-slate-200">
                    <span className="text-slate-500 font-medium block text-[11px]">Hipótese de base legal</span>
                    <span className="font-bold text-slate-900 block mt-0.5">
                      Legítimo interesse em avaliação; exige finalidade, balanceamento e salvaguardas documentadas.
                    </span>
                  </div>

                  <div className="p-3.5 bg-emerald-50/50 rounded-xl border border-emerald-200">
                    <span className="text-emerald-800 font-medium block text-[11px]">Instituição bancária da empresa</span>
                    <span className="font-bold text-slate-900 block mt-0.5">
                      {lead.instituicaoBancaria || 'Não observada'}
                    </span>
                    <span className="text-[10px] text-emerald-800/80 block mt-1">
                      Exibida como vínculo empresarial somente com menção pública explícita ou titularidade CNPJ confirmada.
                    </span>
                  </div>

                  <div className="p-3.5 bg-emerald-50/50 rounded-xl border border-emerald-200">
                    <span className="text-emerald-800 font-medium block text-[11px]">Chave Pix confirmada da empresa</span>
                    <span className="font-mono font-bold text-slate-900 block mt-0.5">
                      {lead.chavePix || 'Não observada'}
                    </span>
                    <span className="text-[10px] text-emerald-800/80 block mt-1">
                      Contas de pessoa física permanecem separadas e nunca são promovidas a conta da empresa.
                    </span>
                  </div>

                  <div className="p-3.5 bg-slate-50 rounded-xl border border-slate-200 col-span-2">
                    <span className="text-slate-500 font-medium block text-[11px]">Finalidade do Tratamento</span>
                    <span className="text-slate-700 block mt-0.5 leading-relaxed">
                      Prospecção comercial B2B entre pessoas jurídicas com contatos corporativos e registros públicos da Receita Federal.
                    </span>
                  </div>
                </div>

                <div className="pt-2 border-t border-slate-100 flex items-center justify-between">
                  <span className="text-xs text-slate-500">Direito do Titular (Art. 18 LGPD):</span>
                  <span className="text-xs font-semibold text-slate-600">Registro de supressão ainda não disponível neste fluxo.</span>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-5 border-t border-slate-200 bg-slate-50 flex items-center justify-between">
          <div className="text-xs text-slate-500 font-medium">
            Confiança registrada: <strong className="text-slate-900">{lead.dataConfidenceScore}%</strong>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={onClose}
              className="px-4 py-2 text-xs font-bold text-slate-600 hover:bg-slate-200 rounded-xl transition-colors cursor-pointer"
            >
              Fechar
            </button>
            {onAddToList && (
              <button
                onClick={() => onAddToList(lead)}
                className="px-4 py-2 bg-blue-600 text-white text-xs font-bold rounded-xl hover:bg-blue-700 transition-colors shadow-sm cursor-pointer"
              >
                Adicionar à Lista de Campanha
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
