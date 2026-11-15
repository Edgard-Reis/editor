# IDENTIDADE VISUAL E DESIGN SYSTEM — VISUAL_IDENTITY
## Diretrizes de Estilo, Configuração por Marca e Casos de Uso

**Data de Consolidação:** 08 de novembro de 2026  
**Documento Técnico de Referência:** `projetos/dr-gestao/branding/` e `DESIGN_SYSTEM_MOTION_DR_GESTAO.md`  
**Natureza do Documento:** `[FATO VERIFICADO]` / `[DECISÃO]` / `[PROPOSTA]` / `[PENDÊNCIA]`  
**Estado de Implementação:** `[IMPLEMENTADO]` / `[EXPERIMENTAL]` / `[PLANEJADO]`  

---

## 1. Princípio de Separação Estrita entre Motor e Marca `[DECISÃO]` `[IMPLEMENTADO]`

O núcleo do Editor audiovisual é concebido de maneira 100% agnóstica em relação a qualquer cliente, canal ou marca comercial:
- O motor de renderização desconhece paletas cromáticas, fontes tipográficas, nomes ou regras de negócios de qualquer criador específico.
- Toda personalização estética, tipográfica, sonora e editorial é externalizada e injetada em tempo de execução a partir do diretório do projeto:
  `D:\Drifit\Editor\projetos\<slug_da_marca>\branding\`

### 1.1 Estrutura Padrão de uma Marca:
```text
projetos/<slug_da_marca>/branding/
├── config.json         # Paleta de cores, tipografia, parâmetros de enquadramento facial
├── PREFERENCIAS.md     # Diretrizes de estilo, tom editorial, ritmo e regras de negócio
├── fontes/             # Arquivos de fontes locais (.ttf / .woff2) para independência de rede
├── logos/              # Ativos vetoriais e bitmaps em alta resolução (.svg / .png)
├── vinhetas/           # Vídeos institucionais de abertura, transição e encerramento
├── sons/               # Elementos sonoros de assinatura (whooshes, dings, pops, swooshes)
├── overlays/           # Máscaras de terço inferior, molduras e split-stages
└── scripts/            # Templates específicos de motion graphics e sobrescritas de estilo
```

---

## 2. Caso Piloto: Dr. Gestão `[FATO VERIFICADO]` `[IMPLEMENTADO]`

### 2.1 Papel Semântico das Cores da Paleta `[DECISÃO]` `[IMPLEMENTADO]`
As cores corporativas do canal Dr. Gestão possuem funções semânticas específicas no sistema de motion graphics:

| Cor / Código Hexadecimal | Papel Semântico no Design System | Aplicação Prática |
|---|---|---|
| **Azul Primário (`#1d7cf2`)** | **Destaque de Marca e Ênfase Visual** | Bordas ativas de cartelas, botões de ação, realce de palavras-chave nas legendas dinâmicas (*karaoke*). |
| **Azul Corporativo Profundo (`#0d3b66`)** | **Suporte Institucional e Fundo Primário** | Fundo dos cards informativos (T10, D30, M20), barras de identificação e terços inferiores sóbrios. |
| **Amarelo / Laranja de Alerta (`#f39c12`)** | **Alerta Crítico, Gargalo e Desperdício** | Sinalização visual de termos críticos de fábrica (*Gargalo*, *Custo Minuto Elevado*, *Prejuízo*, *Retrabalho*). |
| **Branco Neutro (`#ffffff`)** | **Contraste Tipográfico de Leitura** | Textos principais sobre fundos azuis profundos, ícones explicativos e contadores numéricos. |
| **Cinza Escuro / Texto Base (`#1a1a1a`)** | **Texto Secundário e Delimitação** | Legendas sobre fundos neutros claros, contornos e sombras para separação de planos visuais. |

### 2.2 Tipografia Oficial e Governança de Licenciamento `[DECISÃO]` `[PLANEJADO]`
- **Família Tipográfica Principal:** `Inter` (pesos 400 Regular, 600 Semi-Bold, 800 Bold) — utilizada para legendas dinâmicas, textos de corpo de cartelas e informações institucionais.
- **Família Tipográfica de Apoio:** `Montserrat` (pesos 700 Bold, 900 Black) — utilizada para títulos herói de alto impacto (T10) e contadores numéricos de cifras (M20).
- **Repositório Local das Fontes:** Os arquivos das fontes (`.ttf` e `.woff2`) residem localmente em `projetos/dr-gestao/branding/fontes/` e em `assets/fonts/` na toolchain do editor. Isso garante que a renderização via Chrome Headless ocorra sem conexões externas à web.
- **Verificação de Licenciamento:** Ambas as fontes são distribuídas sob a licença de código aberto *SIL Open Font License (OFL v1.1)*. Caso o sistema Editor seja empacotado para distribuição comercial independente, os arquivos de licença originais e os créditos deverão acompanhar os binários distribuídos.

### 2.3 Tradução do Vocabulário Técnico em Elementos Audiovisuais Concretos `[DECISÃO]` `[EXPERIMENTAL]`
O conteúdo do apresentador Luiz Roberto Saraiva é fortemente ancorado no chão de fábrica da indústria de confecção do vestuário. O sistema traduz automaticamente esse vocabulário em componentes gráficos da Motion Library:

- **Termos Fabris Especializados:** Termos como *Alta Minutagem*, *Gargalo*, *PPCP*, *Balanceamento de Célula*, *Facção de Costura* disparam a inserção de cartelas laterais **D30 (Destaque de Termo)** com borda de alerta em `#f39c12` e texto explicativo conciso.
- **Cifras Financeiras e Métricas Operacionais:** Menções a valores financeiros (ex.: *R$ 300.000 a R$ 500.000 por mês*, *prejuízo de 20%*, *12 minutos por peça*) disparam cartelas **M20 (Cartela Métrica)** com animação progressiva de contagem de números via GSAP.
- **Conceitos de Abertura:** A introdução do tema ou tese central do episódio ativa o card **T10 (Card Herói)** no terço da tela, reforçando o título e a credencial do consultor.
- **Chamada Final:** A menção de canais de atendimento e assessoria aciona o card final **C40 (Call-to-Action)** com QR code, logotipo e contatos estruturados.

### 2.4 Preferências de Estilo do Canal Dr. Gestão `[DECISÃO]` `[IMPLEMENTADO]`
Conforme documentado em `projetos/dr-gestao/branding/PREFERENCIAS.md`:
- **Ritmo de Edição:** Enérgico, direto e sem rodeios. Cortes eliminam hesitações e falsos começos, mas respeitam pausas dramáticas intencionais de reflexão do apresentador.
- **Estilo de Motion:** Profissional e minimalista. Animações utilizam aceleração e desaceleração (*easing* suave do GSAP), sem rotações excessivas ou transições amadoras.
- **Legendas Dinâmicas:** Sincronizadas no nível de palavra com realce de estilo *karaoke* em azul primário (`#1d7cf2`), exibindo blocos curtos de 2 a 3 palavras por linha para facilitar a leitura rápida em dispositivos móveis.
- **Uso de B-Roll:** Clipes cinematográficos de linhas industriais de confecção, tecidos, máquinas de costura e operárias em atividade, funcionando como suporte semântico em durações preliminares de 3 a 5 segundos por inserção.
- **Sound Design:** Extremamente sóbrio. Efeitos sonoros discretos (*whoosh* suave em entradas, *click/tap* mecânico sutil em contadores numéricos), calibrados entre -18 dB e -24 dB em relação à voz do apresentador.
- **Enquadramento Facial:** Recomposição digital a partir da fonte 4K mantendo o rosto do apresentador enquadrado confortavelmente no terço superior, com base nas coordenadas de ancoragem configuradas em `config.json`.

---

## 3. Perfis Detalhados de Áreas de Segurança (Safe Areas) `[DECISÃO]` `[PLANEJADO]`

Para evitar a sobreposição de textos e elementos gráficos pelas interfaces dos reprodutores de vídeo, são definidos dois perfis geométricos estritos:

### 3.1 Perfil 16:9 — YouTube / Desktop / Smart TV (1920×1080)
- **Margem de Segurança Perimetral:** 5% nas quatro bordas (54 px superior/inferior, 96 px laterais).
- **Zona Proibida Inferior:** Faixa de **100 px** a partir da borda inferior (área reservada para barra de progresso, botões de controle e legendas nativas do player).
- **Zona Proibida Canto Inferior Direito:** Área de **120×80 px** (botão de inscrição e marca d'água de canal do YouTube).
- **Zona Proibida Canto Superior Direito:** Área de **150×80 px** (cartões de recomendação e links informativos).

### 3.2 Perfil 9:16 — Plataformas Verticais (1080×1920: Shorts / Reels / TikTok)
- **Zona Proibida Superior:** Faixa de **150 px** no topo da tela (reservada para nome de áudio, botões de busca, câmera e indicadores de sistema do smartphone).
- **Zona Proibida Inferior:** Faixa de **250 px** na base da tela (reservada para nome do perfil, descrição do vídeo, legendas geradas pelo app e botão de CTA da plataforma).
- **Zona Proibida Lateral Direita:** Coluna de **120 px** ao longo de toda a borda direita (reservada para botões de interação: Curtir, Comentários, Compartilhar, Remixar e Som original).
- **Zona Segura Central Útil (Área Efetiva):** Retângulo delimitado entre os pixels verticais `Y = 150` e `Y = 1670`, e horizontais `X = 50` e `X = 960`. Todos os elementos críticos de motion graphics, rostos e legendas dinâmicas devem residir estritamente dentro desta área.

---

## 4. Projetos Adicionais e Extensibilidade `[PROPOSTA]` `[PENDÊNCIA]`

### 4.1 Caso Equipe Ozon (`projetos/ozon-tech/`) `[PROPOSTA]` `[PENDÊNCIA] [PENDENTE DE APROVAÇÃO]`
- **Contexto:** Projeto voltado para engenharia de purificação de ar e água via tecnologia de ozônio.
- **Status Documental:** A identidade visual preliminar (tons de azul ciano, prata e branco) consiste em uma **proposta conceitual preliminar pendente de validação com o cliente**. Não há ativos formalizados nem homologação de diretrizes para este canal.

### 4.2 Produções de Conteúdo Técnico / Pessoal `[PROPOSTA]` `[PLANEJADO]`
- Identidade visual minimalista e funcional focada em tutoriais de programação, arquitetura de software e engenharia audiovisual.
- Layouts de tela dividida (*split-screen*) com código fonte, visualizadores de áudio e captura de tela de alta resolução.
