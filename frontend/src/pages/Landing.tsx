import React, { useState } from 'react';
import { Sparkles, PlayCircle, Target, ArrowRightLeft, CheckCircle2, ShieldCheck, ChevronRight, ArrowRight } from 'lucide-react';
import InteractiveDemoModal from '../components/InteractiveDemoModal';
import { useLeadStream } from '../LeadStreamContext';

interface LandingProps {
  onNavigate: (route: string) => void;
}

export default function Landing({ onNavigate }: LandingProps) {
  const { workspace } = useLeadStream();
  const [isDemoOpen, setIsDemoOpen] = useState(false);

  return (
    <div className="min-h-screen bg-[#FAFAFA] font-sans selection:bg-blue-100 selection:text-blue-900 text-slate-900">
      <InteractiveDemoModal 
        isOpen={isDemoOpen} 
        onClose={() => setIsDemoOpen(false)} 
        onGoToApp={() => onNavigate('dashboard')} 
      />

      {/* Header / Navbar */}
      <nav className="fixed top-0 left-0 right-0 bg-white/90 backdrop-blur-md z-40 border-b border-slate-200/80">
        <div className="max-w-7xl mx-auto px-6 h-18 flex items-center justify-between">
          <div className="flex items-center gap-10">
            <div className="flex items-center gap-2.5 cursor-pointer" onClick={() => onNavigate('landing')}>
              <div className="w-9 h-9 bg-blue-600 rounded-xl flex items-center justify-center font-bold text-white shadow-xs">
                L
              </div>
              <div className="flex flex-col">
                <span className="text-xl font-bold tracking-tight text-slate-900">LeadStream</span>
                <span className="text-[10px] font-semibold text-blue-600 -mt-1 tracking-wider uppercase">Inteligência B2B</span>
              </div>
            </div>
            <div className="hidden lg:flex items-center gap-8 text-sm font-medium text-slate-600">
              <a href="#plataforma" className="text-blue-600 font-semibold py-2">Plataforma</a>
              <a href="#solucoes" className="hover:text-slate-900 transition-colors py-2">Soluções</a>
              <a href="#capacidades" className="hover:text-slate-900 transition-colors py-2">Capacidades</a>
              <a href="#roadmap" className="hover:text-slate-900 transition-colors py-2">Para sua equipe</a>
            </div>
          </div>
          <div className="flex items-center gap-4">
            <button 
              onClick={() => onNavigate('dashboard')} 
              className="text-sm font-semibold text-slate-700 hover:text-slate-900 px-3 py-2 rounded-lg hover:bg-slate-100 transition-colors"
            >
              Minha conta
            </button>
            <button 
              onClick={() => onNavigate('dashboard')} 
              className="text-sm font-semibold bg-blue-600 hover:bg-blue-700 text-white px-5 py-2.5 rounded-lg shadow-xs transition-all flex items-center gap-1.5"
            >
              Começar agora
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="pt-36 pb-20 px-6 relative overflow-hidden bg-white border-b border-slate-100">
        <div className="absolute top-0 right-1/4 w-96 h-96 bg-blue-50/50 rounded-full blur-3xl -z-10 pointer-events-none"></div>

        <div className="max-w-7xl mx-auto relative z-10 grid lg:grid-cols-12 gap-12 items-center">
          <div className="lg:col-span-7 max-w-2xl">
            <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-blue-50 text-blue-700 text-xs font-bold mb-6 border border-blue-200 shadow-2xs">
              <Sparkles className="w-3.5 h-3.5 text-blue-600" />
              Dados melhores. Mais oportunidades.
            </div>
            
            <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold text-slate-900 leading-[1.12] tracking-tight mb-6">
              Transforme sua base B2B em oportunidades reais
            </h1>
            
            <p className="text-lg text-slate-600 mb-8 max-w-xl leading-relaxed font-normal">
              Descubra lacunas, complete perfis empresariais e crie listas prontas para o seu time comercial agir.
            </p>
            
            <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-4">
              <button 
                onClick={() => onNavigate('dashboard')} 
                className="px-7 py-3.5 bg-blue-600 hover:bg-blue-700 text-white font-semibold text-base rounded-xl shadow-md shadow-blue-500/10 transition-all flex items-center justify-center gap-2"
              >
                Analisar minha base
                <ArrowRight className="w-4 h-4" />
              </button>
              <button 
                onClick={() => setIsDemoOpen(true)}
                className="px-6 py-3.5 bg-white text-slate-700 border border-slate-300 font-semibold text-base rounded-xl hover:bg-slate-50 transition-all flex items-center justify-center gap-2 shadow-xs"
              >
                <PlayCircle className="w-5 h-5 text-blue-600" />
                Ver Demonstração
              </button>
            </div>

            <div className="mt-10 flex items-center gap-6 text-xs text-slate-500 font-medium">
              <div className="flex items-center gap-1.5">
                <CheckCircle2 className="w-4 h-4 text-emerald-600" /> Diagnóstico de qualidade
              </div>
              <div className="flex items-center gap-1.5">
                <CheckCircle2 className="w-4 h-4 text-emerald-600" /> Enriquecimento por CNPJ
              </div>
              <div className="flex items-center gap-1.5">
                <ShieldCheck className="w-4 h-4 text-blue-600" /> Listas prontas para ativação
              </div>
            </div>
          </div>
          
          {/* Hero Live Preview Widget (matching Image 1 exactly) */}
          <div className="lg:col-span-5 relative">
            <div className="relative mx-auto max-w-md w-full">
              {/* Main Card */}
              <div className="bg-white rounded-2xl border border-slate-200/90 p-5 relative z-10">
                <div className="bg-slate-50 rounded-xl border border-slate-200/70 p-3.5 mb-4 flex justify-between items-center">
                  <div className="flex items-center gap-2 text-sm font-bold text-slate-800">
                    <Target className="w-4 h-4 text-blue-600" /> Da base à oportunidade
                  </div>
                  <div className="flex items-center gap-1.5 text-[11px] font-bold bg-blue-100/70 text-blue-700 px-2.5 py-0.5 rounded-full">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-600"></span>
                    Em poucos passos
                  </div>
                </div>
                
                <div className="space-y-3">
                  {[
                    { 
                      name: 'Adicione sua base', 
                      role: 'Importe empresas e contatos', 
                      company: 'CSV ou TXT', 
                      intent: 'Tudo organizado automaticamente', 
                      tag: 'Começo',
                      badge: 'bg-emerald-50 text-emerald-700 border-emerald-200'
                    },
                    { 
                      name: 'Complete e priorize', 
                      role: 'Encontre lacunas e adicione dados', 
                      company: 'CNPJ ou domínio', 
                      intent: 'Foco nas contas com maior potencial', 
                      tag: 'Inteligência',
                      badge: 'bg-blue-50 text-blue-700 border-blue-200'
                    },
                    { 
                      name: 'Ative seu time', 
                      role: 'Crie listas e campanhas segmentadas', 
                      company: 'Marketing + vendas', 
                      intent: 'Contatos prontos para abordagem', 
                      tag: 'Resultado',
                      badge: 'bg-indigo-50 text-indigo-700 border-indigo-200'
                    }
                  ].map((item, i) => (
                    <div 
                      key={i} 
                      className="p-3.5 rounded-xl border border-slate-200/80 bg-white transition-all duration-200 flex items-center justify-between"
                    >
                      <div className="pr-3">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-bold text-slate-900">{item.name}</span>
                          <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-md border ${item.badge}`}>
                            {item.tag}
                          </span>
                        </div>
                        <div className="text-xs text-slate-600 font-medium mt-0.5">{item.role} • {item.company}</div>
                        <div className="text-[11px] text-blue-600 font-semibold mt-1 flex items-center gap-1">
                          <Sparkles className="w-3 h-3" /> {item.intent}
                        </div>
                      </div>
                      <CheckCircle2 className="h-5 w-5 shrink-0 text-emerald-600" />
                    </div>
                  ))}
                </div>

                <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between text-xs text-slate-500">
                  <span>Resultados baseados nos dados da sua operação</span>
                  <button 
                    onClick={() => onNavigate('search')} 
                    className="text-blue-600 font-bold hover:underline flex items-center gap-1"
                  >
                    Explorar contatos →
                  </button>
                </div>
              </div>
              
              {/* Floating Metric Pill (Matching Image 1) */}
              <div className="absolute -top-6 -right-4 bg-white rounded-xl shadow-lg border border-slate-200 p-4 z-20 w-48">
                <div className="text-xs text-slate-500 font-semibold">Empresas e contatos analisados</div>
                <div className="text-2xl font-black text-blue-600 tracking-tight mt-0.5">{workspace.contacts + workspace.companies}</div>
                <div className="h-1.5 bg-slate-100 mt-2 rounded-full overflow-hidden">
                  <div className="h-full bg-blue-600 rounded-full" style={{ width: workspace.contacts + workspace.companies > 0 ? '100%' : '0%' }}></div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section id="capacidades" className="py-14 border-b border-slate-200 bg-white">
        <div className="max-w-7xl mx-auto px-6">
          <p className="text-xs font-bold text-slate-400 tracking-widest uppercase mb-8 text-center">
            Resultados para sua operação
          </p>
          <div className="grid md:grid-cols-3 gap-5">
            {[
              ['Qualidade em segundos', 'Identifique campos ausentes, duplicidades e dados que precisam de atenção.'],
              ['Perfis empresariais completos', 'Adicione porte, setor, localização, presença digital e dados societários.'],
              ['Ativação comercial', 'Crie segmentos e listas prontas para marketing e vendas trabalharem.'],
            ].map(([title, description]) => (
              <div key={title} className="rounded-2xl border border-slate-200 bg-slate-50 p-6">
                <CheckCircle2 className="h-5 w-5 text-emerald-600 mb-4" />
                <h3 className="font-bold text-slate-900">{title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-slate-600">{description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* 3-Step Feature Showcase Section (Matching Image 1) */}
      <section id="plataforma" className="py-24 bg-[#FAFAFA]">
        <div className="max-w-7xl mx-auto px-6 text-center">
          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-slate-200/70 text-slate-700 text-xs font-bold mb-4 uppercase tracking-wider">
            Da análise à ativação
          </div>
          <h2 className="text-3xl md:text-5xl font-bold text-slate-900 mb-4 tracking-tight">
            Tudo o que seu time precisa para transformar dados em receita.
          </h2>
          <p className="text-slate-600 max-w-2xl mx-auto mb-16 text-lg leading-relaxed">
            Entenda a qualidade da sua base, complete informações importantes e entregue oportunidades mais qualificadas ao time comercial.
          </p>
          
          <div className="grid md:grid-cols-3 gap-8 text-left">
            <div className="bg-white p-8 rounded-2xl border border-slate-200 shadow-xs hover:shadow-md transition-shadow">
              <div className="w-12 h-12 bg-blue-50 text-blue-600 rounded-xl flex items-center justify-center mb-6 border border-blue-100">
                <Target className="w-6 h-6" />
              </div>
              <h3 className="text-xl font-bold text-slate-900 mb-3">1. Definição do ICP</h3>
              <p className="text-slate-600 leading-relaxed text-sm">
                Encontre as empresas com melhor aderência ao seu mercado usando porte, setor, localização e outros critérios relevantes.
              </p>
            </div>
            
            <div className="bg-white p-8 rounded-2xl border border-slate-200 shadow-xs hover:shadow-md transition-shadow">
              <div className="w-12 h-12 bg-indigo-50 text-indigo-600 rounded-xl flex items-center justify-center mb-6 border border-indigo-100">
                <Sparkles className="w-6 h-6" />
              </div>
              <h3 className="text-xl font-bold text-slate-900 mb-3">2. Extração & Enriquecimento</h3>
              <p className="text-slate-600 leading-relaxed text-sm">
                Complete perfis por CNPJ ou domínio e obtenha as informações necessárias para qualificar cada conta.
              </p>
            </div>
            
            <div className="bg-white p-8 rounded-2xl border border-slate-200 shadow-xs hover:shadow-md transition-shadow">
              <div className="w-12 h-12 bg-emerald-50 text-emerald-600 rounded-xl flex items-center justify-center mb-6 border border-emerald-100">
                <ArrowRightLeft className="w-6 h-6" />
              </div>
              <h3 className="text-xl font-bold text-slate-900 mb-3">3. Ativação comercial</h3>
              <p className="text-slate-600 leading-relaxed text-sm">
                Organize contatos em listas segmentadas, exporte resultados e entregue ao time comercial uma próxima ação clara.
              </p>
            </div>
          </div>
        </div>
      </section>

      <section id="roadmap" className="py-20 bg-white border-y border-slate-200">
        <div className="max-w-7xl mx-auto px-6">
          <div className="grid lg:grid-cols-12 gap-8 items-start max-w-5xl mx-auto">
            <div className="lg:col-span-5">
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-blue-50 text-blue-700 text-xs font-bold uppercase tracking-wider">
                Valor para toda a equipe
              </div>
              <h2 className="mt-4 text-3xl sm:text-4xl font-bold text-slate-900 tracking-tight">
                Marketing, vendas e RevOps trabalhando com os mesmos dados.
              </h2>
              <p className="text-slate-600 mt-4 leading-relaxed">
                Uma visão compartilhada da qualidade e do potencial de cada conta reduz retrabalho e acelera a geração de pipeline.
              </p>
            </div>
            <div className="lg:col-span-7 grid gap-4">
              {[
                ['Marketing', 'Segmentos melhores para campanhas mais relevantes e eficientes.'],
                ['Vendas', 'Contatos e empresas mais completos antes da primeira abordagem.'],
                ['RevOps', 'Qualidade mensurável, menos duplicidade e prioridades claras para a operação.'],
              ].map(([title, description], index) => (
                <div key={title} className="flex gap-4 rounded-2xl border border-slate-200 bg-slate-50 p-5">
                  <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-slate-900 text-sm font-bold text-white">{index + 1}</div>
                  <div>
                    <h3 className="font-bold text-slate-900">{title}</h3>
                    <p className="mt-1 text-sm leading-relaxed text-slate-600">{description}</p>
                  </div>
                </div>
              ))}
              <button
                onClick={() => onNavigate('dashboard')}
                className="mt-2 w-full py-3 bg-blue-600 hover:bg-blue-700 text-white font-bold text-sm rounded-xl transition-colors"
              >
                Conhecer a plataforma →
              </button>
            </div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-white border-t border-slate-200 py-12">
        <div className="max-w-7xl mx-auto px-6">
          <div className="flex flex-col md:flex-row items-center justify-between gap-6 pb-8 border-b border-slate-100">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center font-bold text-white text-sm">
                L
              </div>
              <div>
                <span className="text-base font-bold text-slate-900">LeadStream</span>
                <p className="text-xs text-slate-500">Inteligência B2B para empresas brasileiras</p>
              </div>
            </div>
            <button onClick={() => onNavigate('dashboard')} className="text-xs font-semibold text-blue-600 hover:text-blue-700">
              Começar agora →
            </button>
          </div>
          <div className="pt-6 flex flex-col md:flex-row items-center justify-between text-xs text-slate-400 gap-4">
            <p>LeadStream · Qualidade, enriquecimento e ativação de dados B2B</p>
            <p>Mais qualidade para decisões comerciais mais rápidas.</p>
          </div>
        </div>
      </footer>
    </div>
  );
}
