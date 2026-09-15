---
name: LeadStream
description: Sala de operações para dados B2B brasileiros confiáveis e auditáveis.
colors:
  action-blue: "oklch(0.56 0.21 260)"
  focus-blue: "oklch(0.68 0.16 255)"
  workspace: "oklch(0.975 0.006 255)"
  surface: "oklch(1 0 0)"
  ink: "oklch(0.19 0.025 258)"
  muted: "oklch(0.48 0.025 258)"
  divider: "oklch(0.9 0.012 255)"
typography:
  title:
    fontFamily: "Plus Jakarta Sans, Inter, ui-sans-serif, system-ui, sans-serif"
    fontSize: "1.25rem"
    fontWeight: 700
    lineHeight: 1.35
  body:
    fontFamily: "Plus Jakarta Sans, Inter, ui-sans-serif, system-ui, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 400
    lineHeight: 1.55
  label:
    fontFamily: "Plus Jakarta Sans, Inter, ui-sans-serif, system-ui, sans-serif"
    fontSize: "0.8125rem"
    fontWeight: 600
    lineHeight: 1.35
rounded:
  control: "8px"
  surface: "12px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "16px"
  lg: "24px"
  xl: "32px"
components:
  button-primary:
    backgroundColor: "{colors.action-blue}"
    textColor: "{colors.surface}"
    rounded: "{rounded.control}"
    padding: "10px 16px"
  input:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    padding: "10px 12px"
---

# Design System: LeadStream

## Overview

**Creative North Star: "Sala de Operações de Evidências"**

A LeadStream deve parecer um ambiente de trabalho calmo, preciso e auditável, utilizado durante horas por operadores de dados e vendas. A densidade é profissional, mas a hierarquia deixa claro o que é fato, o que está pendente e qual ação vem a seguir.

O sistema evita o painel genérico de SaaS. Valor percebido vem da qualidade dos dados, da proveniência visível e de controles previsíveis — nunca de decoração, números inflados ou cartões repetitivos.

**Key Characteristics:**

- Superfícies claras e estáveis para uso prolongado.
- Uma única cor de ação, reservada a seleção, foco e ações primárias.
- Tabelas e filas de trabalho como estruturas principais.
- Estados ausente, observado, validado e confirmado sempre explícitos.
- PJ e PF são trilhas distintas dentro do mesmo fluxo operacional.

## Colors

A paleta usa neutros levemente azulados e um único azul de ação, com cores semânticas apenas quando existe um estado real a comunicar.

### Primary

- **Azul de Ação:** usado em ação primária, seleção atual, links e progresso confirmado.
- **Azul de Foco:** reservado ao contorno de teclado e estados de foco visível.

### Neutral

- **Área de Trabalho:** plano de fundo geral que separa a aplicação das superfícies de conteúdo.
- **Superfície:** tabelas, barras de ferramentas e painéis ativos.
- **Tinta:** texto principal e valores de alta importância.
- **Texto Secundário:** descrições e metadados, sempre com contraste AA.
- **Divisor:** separação estrutural de linhas e regiões.

**The One Voice Rule.** O azul de ação ocupa no máximo 10% de uma tela e nunca é decoração.

## Typography

**Display Font:** Plus Jakarta Sans (com Inter e system-ui como fallback)  
**Body Font:** Plus Jakarta Sans (com Inter e system-ui como fallback)

**Character:** Uma única família humanista mantém leitura confortável e consistência entre dados, rótulos e controles.

### Hierarchy

- **Title** (700, 1.25rem, 1.35): título de página e de região principal.
- **Body** (400, 0.875rem, 1.55): texto operacional, mensagens e células com conteúdo extenso.
- **Label** (600, 0.8125rem, 1.35): rótulos de campo, cabeçalhos de tabela e controles.

**The Readable Floor Rule.** Nenhum texto funcional usa tamanho inferior a 13px; corpo e célula preferem 14px.

## Elevation

O sistema é plano por padrão. Profundidade vem de contraste tonal e divisores; sombras aparecem somente em elementos que realmente flutuam, como menus e diálogos.

### Shadow Vocabulary

- **Flutuação controlada** (`0 4px 8px rgba(15, 23, 42, 0.10)`): menus, popovers e diálogos.

**The Flat-by-Default Rule.** Um contêiner em repouso usa borda ou mudança tonal, nunca borda acompanhada de sombra larga.

## Components

### Buttons

- **Shape:** cantos discretamente arredondados (8px).
- **Primary:** azul de ação, texto branco e área mínima de toque de 40px.
- **Hover / Focus:** escurecimento moderado no hover e contorno de foco sempre visível.
- **Secondary / Ghost:** superfície branca ou transparente, tinta escura e divisor estrutural.

### Chips

- **Style:** compactos, com fundo tonal e texto de alto contraste; não são botões decorativos.
- **State:** seleção combina cor, ícone e texto, sem depender apenas da cor.

### Cards / Containers

- **Corner Style:** 12px no máximo.
- **Background:** superfície branca sobre a área de trabalho.
- **Shadow Strategy:** nenhuma sombra em repouso.
- **Border:** divisor de 1px quando a separação for necessária.
- **Internal Padding:** 16px a 24px conforme densidade.

### Inputs / Fields

- **Style:** superfície branca, contorno estrutural e cantos de 8px.
- **Focus:** contorno azul visível sem alterar o layout.
- **Error / Disabled:** mensagem específica junto ao campo; estado desabilitado preserva legibilidade.

### Navigation

Navegação usa rótulos diretos, ícones Lucide consistentes e seleção atual inequívoca. Em telas estreitas, ações secundárias recolhem antes de dados essenciais.

### Evidence Status

O estado de evidência combina texto, ícone e tratamento tonal. “Ausente”, “observado”, “validado” e “confirmado” nunca são substituídos por um score genérico.

## Do's and Don'ts

### Do:

- **Do** manter filtros ativos na URL e resultados paginados no servidor.
- **Do** mostrar fonte, data e nível de evidência próximo ao dado acionável.
- **Do** usar tabelas para comparação e painéis laterais para inspeção detalhada.
- **Do** oferecer estados de carregamento, vazio, erro e recuperação em português do Brasil.
- **Do** preservar contraste WCAG 2.2 AA e foco visível em todos os controles.

### Don't:

- **Don't** criar painéis genéricos de SaaS compostos por grades repetitivas de cartões e métricas decorativas.
- **Don't** esconder ausência, inferência ou falha atrás de scores sem explicação.
- **Don't** usar linguagem excessivamente técnica em fluxos de negócio.
- **Don't** usar tipografia pequena, baixo contraste ou densidade sem hierarquia.
- **Don't** misturar telas administrativas à operação cotidiana do cliente.
- **Don't** usar faixas coloridas laterais, glassmorphism, texto em gradiente ou cartões com raio acima de 16px.
