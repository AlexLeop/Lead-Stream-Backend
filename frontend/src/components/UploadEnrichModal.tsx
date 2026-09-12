import { useMemo, useRef, useState } from 'react';
import {
  AlertCircle,
  ArrowRight,
  CheckCircle2,
  FileSpreadsheet,
  FolderKanban,
  FolderPlus,
  LoaderCircle,
  Upload,
  X,
} from 'lucide-react';
import { useLeadStream } from '../LeadStreamContext';
import { leadSetCategories } from '../config';
import type { ImportResult, LeadSet } from '../types';

interface UploadEnrichModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (result: ImportResult) => void;
  existingSets?: LeadSet[];
}

const headerAliases: Record<string, string> = {
  nome: 'name',
  nome_contato: 'name',
  contato: 'name',
  name: 'name',
  cargo: 'title',
  title: 'title',
  senioridade: 'seniority',
  seniority: 'seniority',
  email: 'email',
  e_mail: 'email',
  telefone: 'phone',
  celular: 'phone',
  whatsapp: 'phone',
  phone: 'phone',
  empresa: 'company',
  nome_empresa: 'company',
  company: 'company',
  razao_social: 'legalName',
  dominio: 'domain',
  domain: 'domain',
  site: 'domain',
  website: 'domain',
  cnpj: 'cnpj',
  setor: 'industry',
  industria: 'industry',
  industry: 'industry',
  cnae: 'cnae',
  porte: 'companySize',
  faixa_funcionarios: 'companySize',
  funcionarios: 'employeeCount',
  employee_count: 'employeeCount',
  faturamento: 'annualRevenue',
  cidade: 'city',
  city: 'city',
  estado: 'state',
  uf: 'state',
  state: 'state',
  pais: 'country',
  country: 'country',
  localizacao: 'location',
  location: 'location',
  linkedin: 'linkedinUrl',
  linkedin_url: 'linkedinUrl',
  status_email: 'status',
};

function normalizeHeader(header: string) {
  const normalized = header
    .trim()
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_|_$/g, '');
  return headerAliases[normalized] ?? normalized;
}

function detectDelimiter(firstLine: string) {
  const candidates = [',', ';', '\t'];
  return candidates.sort((left, right) => firstLine.split(right).length - firstLine.split(left).length)[0];
}

function parseDelimited(text: string) {
  const normalizedText = text.replace(/^\uFEFF/, '').replace(/\r\n/g, '\n').replace(/\r/g, '\n');
  const delimiter = detectDelimiter(normalizedText.split('\n', 1)[0] ?? '');
  const rows: string[][] = [];
  let row: string[] = [];
  let field = '';
  let quoted = false;

  for (let index = 0; index < normalizedText.length; index += 1) {
    const character = normalizedText[index];
    const next = normalizedText[index + 1];
    if (character === '"' && quoted && next === '"') {
      field += '"';
      index += 1;
    } else if (character === '"') {
      quoted = !quoted;
    } else if (character === delimiter && !quoted) {
      row.push(field.trim());
      field = '';
    } else if (character === '\n' && !quoted) {
      row.push(field.trim());
      if (row.some(Boolean)) rows.push(row);
      row = [];
      field = '';
    } else {
      field += character;
    }
  }
  row.push(field.trim());
  if (row.some(Boolean)) rows.push(row);
  if (rows.length < 2) throw new Error('O CSV precisa conter cabeçalho e ao menos uma linha de dados.');

  const headers = rows[0].map(normalizeHeader);
  const records = rows.slice(1).map((values) =>
    Object.fromEntries(headers.map((header, index) => [header, values[index] ?? ''])),
  );
  return { headers, records };
}

export default function UploadEnrichModal({
  isOpen,
  onClose,
  onSuccess,
  existingSets = [],
}: UploadEnrichModalProps) {
  const { importRecords } = useLeadStream();
  const inputRef = useRef<HTMLInputElement>(null);
  const [step, setStep] = useState<'upload' | 'configure' | 'processing' | 'done'>('upload');
  const [dragActive, setDragActive] = useState(false);
  const [fileName, setFileName] = useState('');
  const [fileSize, setFileSize] = useState('');
  const [headers, setHeaders] = useState<string[]>([]);
  const [records, setRecords] = useState<Array<Record<string, string>>>([]);
  const [setMode, setSetMode] = useState<'new' | 'existing'>(existingSets.length ? 'existing' : 'new');
  const [selectedExistingSetId, setSelectedExistingSetId] = useState(existingSets[0]?.id ?? '');
  const [newSetName, setNewSetName] = useState('');
  const [category, setCategory] = useState('Prospecção Outbound');
  const [leadType, setLeadType] = useState<'PJ' | 'PF' | 'MISTO'>('MISTO');
  const [result, setResult] = useState<ImportResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const recognizedHeaders = useMemo(
    () => headers.filter((header) => Object.values(headerAliases).includes(header)),
    [headers],
  );

  if (!isOpen) return null;

  const reset = () => {
    setStep('upload');
    setFileName('');
    setFileSize('');
    setHeaders([]);
    setRecords([]);
    setResult(null);
    setError(null);
  };

  const close = () => {
    reset();
    onClose();
  };

  const processFile = async (file: File) => {
    setError(null);
    if (!/\.(csv|txt)$/i.test(file.name)) {
      setError('Use um arquivo CSV. XLSX será adicionado quando o importador tabular estiver integrado.');
      return;
    }
    if (file.size > 8 * 1024 * 1024) {
      setError('O arquivo excede o limite inicial de 8 MB.');
      return;
    }
    try {
      const parsed = parseDelimited(await file.text());
      if (parsed.records.length > 10_000) throw new Error('O limite inicial é de 10.000 linhas por importação.');
      setFileName(file.name);
      setFileSize(`${Math.max(1, Math.round(file.size / 1024))} KB`);
      setHeaders(parsed.headers);
      setRecords(parsed.records);
      setNewSetName(file.name.replace(/\.[^.]+$/, '').replace(/[_-]+/g, ' '));
      setStep('configure');
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Não foi possível ler o arquivo.');
    }
  };

  const submit = async () => {
    if (setMode === 'new' && !newSetName.trim()) {
      setError('Informe um nome para o novo dataset.');
      return;
    }
    if (setMode === 'existing' && !selectedExistingSetId) {
      setError('Selecione o dataset de destino.');
      return;
    }

    setError(null);
    setStep('processing');
    try {
      const imported = await importRecords({
        sourceFileName: fileName,
        records,
        ...(setMode === 'existing'
          ? { datasetId: selectedExistingSetId }
          : {
              dataset: {
                name: newSetName.trim(),
                category,
                leadType,
                description: `Importado de ${fileName}`,
                tags: ['Importação CSV'],
              },
            }),
      });
      setResult(imported);
      setStep('done');
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'A importação falhou.');
      setStep('configure');
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto bg-slate-950/60 p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="import-title"
    >
      <div className="flex max-h-[92vh] w-full max-w-2xl flex-col overflow-hidden rounded-2xl bg-white shadow-2xl">
        <div className="flex items-center justify-between border-b border-slate-200 bg-slate-50 px-6 py-5">
          <div>
            <h2 id="import-title" className="text-lg font-extrabold text-slate-900">
              Importar dados reais
            </h2>
            <p className="mt-1 text-xs font-medium text-slate-600">
              O arquivo é normalizado e salvo com segurança, sem gerar ou completar valores fictícios.
            </p>
          </div>
          <button onClick={close} className="rounded-lg p-2 text-slate-500 hover:bg-slate-200" aria-label="Fechar">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="overflow-y-auto p-6">
          {error && (
            <div className="mb-5 flex items-start gap-3 rounded-xl bg-red-50 p-4 text-sm text-red-800" role="alert">
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {step === 'upload' && (
            <div>
              <button
                type="button"
                onClick={() => inputRef.current?.click()}
                onDragEnter={(event) => {
                  event.preventDefault();
                  setDragActive(true);
                }}
                onDragOver={(event) => event.preventDefault()}
                onDragLeave={() => setDragActive(false)}
                onDrop={(event) => {
                  event.preventDefault();
                  setDragActive(false);
                  const file = event.dataTransfer.files[0];
                  if (file) void processFile(file);
                }}
                className={`flex min-h-72 w-full flex-col items-center justify-center rounded-2xl border-2 border-dashed p-8 text-center transition-colors ${
                  dragActive ? 'border-blue-500 bg-blue-50' : 'border-slate-300 bg-slate-50 hover:border-blue-400'
                }`}
              >
                <span className="mb-4 flex h-14 w-14 items-center justify-center rounded-xl bg-blue-600 text-white">
                  <Upload className="h-6 w-6" />
                </span>
                <span className="text-base font-bold text-slate-900">Selecione ou arraste um CSV</span>
                <span className="mt-2 max-w-md text-sm text-slate-600">
                  Cabeçalhos como nome, empresa, e-mail, telefone, domínio, CNPJ, cargo, cidade e setor são reconhecidos automaticamente.
                </span>
                <span className="mt-4 text-xs font-semibold text-slate-500">Até 10.000 linhas e 8 MB</span>
              </button>
              <input
                ref={inputRef}
                type="file"
                accept=".csv,.txt,text/csv,text/plain"
                className="hidden"
                onChange={(event) => {
                  const file = event.target.files?.[0];
                  if (file) void processFile(file);
                }}
              />
            </div>
          )}

          {step === 'configure' && (
            <div className="space-y-6">
              <div className="flex items-center justify-between rounded-xl bg-slate-100 p-4">
                <div className="flex items-center gap-3">
                  <FileSpreadsheet className="h-5 w-5 text-emerald-600" />
                  <div>
                    <div className="text-sm font-bold text-slate-900">{fileName}</div>
                    <div className="text-xs text-slate-600">{records.length} linhas · {fileSize}</div>
                  </div>
                </div>
                <button onClick={reset} className="text-xs font-bold text-blue-700 hover:underline">Trocar arquivo</button>
              </div>

              <div>
                <div className="mb-2 text-xs font-bold text-slate-700">Colunas reconhecidas</div>
                <div className="flex flex-wrap gap-2">
                  {recognizedHeaders.length ? (
                    recognizedHeaders.map((header) => (
                      <span key={header} className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-800">
                        {header}
                      </span>
                    ))
                  ) : (
                    <span className="text-sm text-amber-700">Nenhuma coluna padrão foi reconhecida; revise o cabeçalho.</span>
                  )}
                </div>
              </div>

              <div>
                <div className="mb-2 text-xs font-bold text-slate-700">Destino</div>
                <div className="grid grid-cols-2 gap-2 rounded-xl bg-slate-100 p-1">
                  <button
                    onClick={() => setSetMode('new')}
                    className={`flex items-center justify-center gap-2 rounded-lg px-3 py-2 text-xs font-bold ${
                      setMode === 'new' ? 'bg-white text-blue-700 shadow-sm' : 'text-slate-600'
                    }`}
                  >
                    <FolderPlus className="h-4 w-4" /> Novo dataset
                  </button>
                  <button
                    onClick={() => setSetMode('existing')}
                    disabled={!existingSets.length}
                    className={`flex items-center justify-center gap-2 rounded-lg px-3 py-2 text-xs font-bold disabled:opacity-40 ${
                      setMode === 'existing' ? 'bg-white text-blue-700 shadow-sm' : 'text-slate-600'
                    }`}
                  >
                    <FolderKanban className="h-4 w-4" /> Dataset existente
                  </button>
                </div>
              </div>

              {setMode === 'existing' ? (
                <select
                  value={selectedExistingSetId}
                  onChange={(event) => setSelectedExistingSetId(event.target.value)}
                  className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm text-slate-900"
                >
                  {existingSets.map((dataset) => <option key={dataset.id} value={dataset.id}>{dataset.name}</option>)}
                </select>
              ) : (
                <div className="grid gap-4 sm:grid-cols-2">
                  <label className="sm:col-span-2">
                    <span className="mb-1.5 block text-xs font-bold text-slate-700">Nome do dataset</span>
                    <input
                      value={newSetName}
                      onChange={(event) => setNewSetName(event.target.value)}
                      className="w-full rounded-xl border border-slate-300 px-3 py-2.5 text-sm"
                    />
                  </label>
                  <label>
                    <span className="mb-1.5 block text-xs font-bold text-slate-700">Categoria</span>
                    <select value={category} onChange={(event) => setCategory(event.target.value)} className="w-full rounded-xl border border-slate-300 px-3 py-2.5 text-sm">
                      {leadSetCategories.map((item) => <option key={item}>{item}</option>)}
                    </select>
                  </label>
                  <label>
                    <span className="mb-1.5 block text-xs font-bold text-slate-700">Conteúdo predominante</span>
                    <select value={leadType} onChange={(event) => setLeadType(event.target.value as typeof leadType)} className="w-full rounded-xl border border-slate-300 px-3 py-2.5 text-sm">
                      <option value="PJ">Empresas</option>
                      <option value="PF">Contatos profissionais</option>
                      <option value="MISTO">Empresas e contatos</option>
                    </select>
                  </label>
                </div>
              )}

              <div className="flex items-center justify-end gap-3 border-t border-slate-200 pt-5">
                <button onClick={close} className="rounded-xl bg-slate-100 px-4 py-2.5 text-xs font-bold text-slate-700">Cancelar</button>
                <button
                  onClick={() => void submit()}
                  disabled={!records.length || recognizedHeaders.length === 0}
                  className="flex items-center gap-2 rounded-xl bg-blue-600 px-5 py-2.5 text-xs font-bold text-white disabled:opacity-50"
                >
                  Adicionar à minha base <ArrowRight className="h-4 w-4" />
                </button>
              </div>
            </div>
          )}

          {step === 'processing' && (
            <div className="flex min-h-72 flex-col items-center justify-center text-center" aria-live="polite">
              <LoaderCircle className="h-10 w-10 animate-spin text-blue-600" />
              <h3 className="mt-5 text-lg font-bold text-slate-900">Organizando registros</h3>
              <p className="mt-2 max-w-md text-sm text-slate-600">
                Empresas e contatos estão sendo conciliados por CNPJ, domínio e e-mail em uma operação segura.
              </p>
            </div>
          )}

          {step === 'done' && result && (
            <div className="flex min-h-72 flex-col items-center justify-center text-center">
              <CheckCircle2 className="h-12 w-12 text-emerald-600" />
              <h3 className="mt-4 text-xl font-extrabold text-slate-900">Importação concluída</h3>
              <p className="mt-2 text-sm text-slate-600">Dataset “{result.dataset.name}” atualizado com dados do arquivo.</p>
              <div className="mt-6 flex flex-wrap justify-center gap-3">
                <span className="rounded-full bg-slate-100 px-4 py-2 text-sm font-bold text-slate-800">{result.companies} {result.companies === 1 ? 'empresa' : 'empresas'}</span>
                <span className="rounded-full bg-slate-100 px-4 py-2 text-sm font-bold text-slate-800">{result.contacts} {result.contacts === 1 ? 'contato' : 'contatos'}</span>
                <span className="rounded-full bg-slate-100 px-4 py-2 text-sm font-bold text-slate-800">{result.skipped} {result.skipped === 1 ? 'ignorado' : 'ignorados'}</span>
              </div>
              <button
                onClick={() => {
                  onSuccess(result);
                  close();
                }}
                className="mt-7 rounded-xl bg-blue-600 px-6 py-3 text-sm font-bold text-white"
              >
                Concluir
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
