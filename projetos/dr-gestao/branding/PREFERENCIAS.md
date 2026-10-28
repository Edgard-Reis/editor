# Diretrizes e Preferências de Edição — Dr. Gestão (EP-00 e Próximos)

Este documento registra as preferências e regras de edição aprovadas para os vídeos do **Dr. Gestão (Luiz Roberto Saraiva)**. Todas as edições da série devem seguir rigorosamente estes padrões.

---

## 1. Identidade Visual da Marca
- **Azul Dr. Gestão (Destaque Principal):** `#004aad`
- **Lilás / Roxo (Secundária e Acentos):** `#8e7de5`
- **Azul Ciano (Realces e Detalhes):** `#2f97d4`
- **Fundo dos Cards:** Vidro escuro translúcido com gradiente em azul marinho profundo (`rgba(18,24,42,.88)` a `rgba(8,12,22,.94)`), com borda sutil em lilás (`rgba(142,125,229,.38)`) e glow azul.
- **Tipografia:** Fonte `Inter` (pesos 500, 600, 700, 800).
- **Ícones Animados:** Sempre traçados no tom lilás da marca (`#8e7de5`).

---

## 2. Apresentação e Lower Third (00:02)
- **Nome Oficial:** `Luiz Roberto Saraiva` (nunca abreviar nem cortar o sobrenome).
- **Credencial Oficial:** `Dr. Gestão · Alta Performance em Confecção do Vestuário`.
- **Dimensões e Espaçamento:** Largura máxima de até `1150px` com `width: max-content` e máscara de animação ampla (`x: 1150`) para evitar qualquer corte de texto.
- **Tempo de Entrada:** O card e o nome entram já no início da introdução (`0.2s` a `0.6s`), garantindo que estejam 100% legíveis quando o nome é falado.

---

## 3. Posicionamento de Cards e Motions (Alternância de Lados)
- **Regra Fundamental:** Os cards e pílulas (`il.chip`) **nunca** devem ficar concentrados apenas em um lado do vídeo.
- **Leitura do Enquadramento:** Respeitar o espaço livre e o centro do rosto do Dr. Gestão (`rosto: [980, 420]`):
  - **Lado Esquerdo (`x=100`, `lado="esq"`):** Usado quando o Dr. Gestão estiver mais ao centro/direita.
  - **Lado Direito (`x=1180` a `1240`, `lado="dir"`):** Aproveita a amplitude do espaço da janela do carro, com animação deslizando a partir da direita.
- **Cards Empilhados (ex.: Marketplaces ou Faturamento):** Espaçamento vertical uniforme (`deltaY = 80px a 90px`).

---

## 4. Regras de B-Rolls
- **Zero Obstrução de Rosto:** É terminantemente proibido cards de b-roll sobrepostos cobrirem parcial ou totalmente o rosto do Dr. Gestão.
- **Modo Padrão:** **Tela Cheia** (`cn.broll(..., card=False)`).
- **Animação:** Push-in sutil (*Ken Burns* suave com `kb=1.06`) e corte seco com swish ou whoosh discreto.
- **Identificação:** Acompanhado de chip informativo no rodapé (`y=890`), identificando o tema do b-roll.
- **Coerência Temática:** O conteúdo visual do b-roll deve corresponder à magnitude do discurso:
  - Exemplo: Quando o Dr. Gestão mencionar "estrutura de fábrica muito grande", usar plantas fabris industriais completas em grande escala (`media/fabrica_industrial.jpg`), nunca oficinas ou ateliês pequenos.
- **Download Automatizado de B-Rolls (Pixabay & Pexels):**
  - **Pixabay (Oficial):** `python scripts/broll_pixabay.py "<termo_ingles>" -o media/broll -n 2` (prioriza filmagens industriais, confecção, costura, galpões e logística em Full HD 1080p).
  - **Pexels:** `python scripts/broll_pexels.py "<termo_ingles>" -o media/broll -n 2` como fonte complementar.
  - As chaves de API ficam no `.env` (`PIXABAY_API_KEY` e `PEXELS_API_KEY`).

---

## 5. Logos de Plataformas e Redes
- **Logos Oficiais:** Utilizar obrigatoriamente os arquivos oficiais em `logos/`:
  - **TikTok Shop:** `logos/tiktok.svg`
  - **Shopee:** `logos/shopee.png`
  - **Mercado Livre:** `logos/mercado-livre.png`
  - **Shein:** `logos/shein.png`
  - **WhatsApp:** `logos/whatsapp.svg`
- **Sincronia:** Quando citadas em grupo, manter todas as opções visíveis em conjunto na tela até a transição para a próxima ideia.

---

## 6. Áudio e Masterização
- **Trilha Sonora de Fundo:** **Desativada** por padrão no render final (`partes.json` e `index.html`), permitindo que a trilha musical definitiva seja aplicada na pós-produção externa. O arquivo `sons/trilha.wav` permanece armazenado para referência.
- **Voz e Efeitos:** Masterização sonora mantida em `-14 LUFS` (padrão YouTube), com efeitos sonoros do kit seco (`sons/`: whoosh, clique, check, impacto).

---

## 7. Estrutura do Início / Gancho & Vinheta (Padrão de Episódio)
- **Gancho Inicial (0:00 - ~0:02.3s)**:
  - Frase de impacto extraída do conteúdo: *"O grande problema de todo mundo é vendas"*.
  - Destaque visual: Palavra-chave **VENDAS** em azul `#58a2eb` com sublinhado branco e sombra suave no lado direito do quadro.
- **Fala de Introdução no Carro (~0:02.3s - ~0:30.5s)**:
  - Contextualização do assunto gravado no carro.
  - Eliminação de erros técnicos / bastidores ao final da gravação.
  - Card explicativo **O PROBLEMA É / VENDAS** posicionado sincronizado à fala.
- **Tratamento de Áudio de Campo (Carro)**:
  - Filtro High-Pass (80 Hz) para remoção de ressonância e ruído do motor/asfalto.
  - Spectral Denoise (gating não destrutivo com perfil acústico do ambiente).
  - EQ paramétrica para redução de ressonância interna de cabine (320 Hz) e ganho de presença vocal (3.0 kHz).
  - Compressão vocal suave e normalização Loudness padrão broadcast (-14 LUFS, Peak -1.0 dBFS).
- **Vinheta Oficial do Canal (~0:30.5s - ~0:38.4s)**:
  - `Intro-Dr-Gestao.mp4` integrada em 1080p 30fps com áudio nivelado em -14 LUFS para não estourar volume.
- **Vídeo Principal (~0:38.4s em diante)**:
  - Entrada contínua com Lower Third completo e B-rolls integrados.

---

## 8. Estratégia de Formatos (16:9 Horizontal vs 9:16 Vertical)

### Formato 16:9 (Horizontal / YouTube Principal):
- **Ritmo:** Dinâmico e moderno, com cortes limpos e micro-zooms suaves nos momentos de ênfase (`bate()`).
- **Cards Flutuantes Laterais (Sidecars):** `cn.card_flutuante(lado='dir'|'esq')` com badge em pílula, título editorial de alto contraste, subtítulo e cantos arredondados (`26px`).
- **Barras de Progresso e Metas:** `cn.barra_progresso(pct, meta)` vertical ou horizontal com gradiente oficial da marca (`#004aad` -> `#8e7de5` -> `#2f97d4`) e linha pontilhada de meta.
- **Steppers Numerados:** `cn.stepper(etapas=5, ativa=1)` com anel pontilhado giratório na etapa ativa.
- **Palco PiP (Picture-in-Picture):** `cn.pip_stage(de, ate, midia)` encolhe a câmera do Dr. Gestão para um card flutuante com borda branca e cantos arredondados, enquanto o centro da tela exibe o canvas visual de demonstração.
- **Transição de Marca:** `cn.transicao_marca(t)` insere a transição diagonal com áudio *whoosh* sincronizado.

### Formato 9:16 (Vertical / Shorts, Reels e TikTok):
- **Volume:** Extração de **7 cortes de alto impacto** (< 60 segundos) por episódio.
- **Padrão Obrigatório de Nomenclatura:** `EP<XX>_corte_<YY>_<tema>.mp4`.
- **Layout de Duas Zonas (Split Stage):**
  - **Metade Superior (~50% do topo):** Palco exclusivo de cards de motion graphics, telas, mockups e b-rolls.
  - **Metade Inferior (~50% da base):** Dr. Gestão centralizado do peito para cima (`cx=980, cy=420`).
- **Legendas Dinâmicas Palavra por Palavra:** Ancoradas na linha de corte divisória (`y=1020`), com destaque na cor da marca para a palavra falada.
- **Padrão Obrigatório de Motion Graphics & Sound Design (Shorts):**
  - **Entrada e Saída Item por Item:** Animações fluidas (*staggered ease-out*) revelando badge, título, subtítulo e lista de tópicos progressivamente, com *slide-out* e *fade-out* ao término.
  - **Sound Design Sincronizado:** Trilha sutil de efeitos sonoros (`whoosh_curto.wav` na entrada do card, `clique2.wav` no badge, `check.wav` a cada novo item/bullet revelado, e `swish.wav` na saída).
  - **Logo Oficial Branca:** Rasterizada em alta definição a partir de `Logo-Branco.svg` e fixada no canto superior direito como marca d'água.
  - **Fechamento Oficial:** Vinheta animada final (Avatar Dr. Gestão + círculo lilás + chamada para redes) concatenada ao final com áudio normalizado a `-14 LUFS` (True Peak `-1.0 dBFS`).
- **Cortes do EP-00 Renderizados e Padronizados:**
  1. `EP00_corte_01_problema_vendas_minutagem.mp4` (36.2s total) · *Vendas travadas, alta minutagem e estrutura enxuta.*
  2. `EP00_corte_02_dinheiro_na_mesa.mp4` (28.5s total) · *Quem já tem confecção está deixando dinheiro na mesa (Minerar, Validar, Vender).*
  3. `EP00_corte_03_virada_marketplaces.mp4` (29.6s total) · *Virada de chave no TikTok Shop, Shopee, Mercado Livre e Shein.*
  4. `EP00_corte_04_ilusao_do_milhao.mp4` (25.6s total) · *Sem ilusão de milhão fácil: o segredo da estrutura enxuta.*
  5. `EP00_corte_05_faturamento_400k_enxuto.mp4` (27.2s total) · *Faturando R$ 300k a R$ 500k e o alerta da tributação 2026/27.*
  6. `EP00_corte_06_lucro_vs_faturamento.mp4` (25.6s total) · *Trabalhando pra caramba, faturamento alto, mas cadê o lucro real?*
  7. `EP00_corte_07_bastidores_campo_batalha.mp4` (28.1s total) · *29 anos no campo de batalha gravando domingo à noite.*

---

## 9. Ciclo de Feedback Contínuo & Aprendizado a Cada Novo EP (Protocolo Vivo)

Para garantir que a qualidade da série evolua constantemente e nenhum erro ou preferência seja esquecido:

1. **Regra de Ouro da Memória Central:**
   - Toda solicitação de ajuste, correção ou preferência feita pelo usuário em qualquer episódio (EP-00, EP-01, EP-02...) deve ser **imediatamente documentada neste arquivo (`PREFERENCIAS.md`)**.
   - O ajuste não deve ficar restrito ao script local do episódio; deve ser promovido a regra permanente para todos os episódios futuros.

2. **Fluxo de Aplicação de Correções:**
   - **Passo 1 (Diagnóstico):** Identificar se a correção é de texto, enquadramento, áudio, timing ou elemento gráfico.
   - **Passo 2 (Correção Local):** Aplicar o ajuste no workspace do episódio em edição e renderizar novamente.
   - **Passo 3 (Promoção para Branding):** Atualizar `PREFERENCIAS.md` e os templates em `branding/scripts/` para que o próximo episódio já nasça com a correção incorporada.
   - **Passo 4 (Registro no Log):** Adicionar uma entrada na tabela de melhorias abaixo.

### Registro Histórico de Melhorias e Ajustes

| Data | Episódio | Elemento | Motivo / Ajuste Solicitado | Regra Estabelecida |
| :--- | :--- | :--- | :--- | :--- |
| **2026-10-27** | EP-00 | Lower Third | Nome do Dr. Gestão cortando na borda direita | Definir `width: max-content`, `max-width: 1150px` e máscara ampla de animação `x: 1150`. |
| **2026-10-27** | EP-00 | B-Rolls | B-Roll sobrepondo o rosto do apresentador | B-Rolls sempre em tela cheia (`card=False`) ou em flanco livre com Ken Burns suave. |
| **2026-10-27** | EP-00 | B-Rolls | Imagem de fábrica modesta não compatível com discurso de "grande fábrica" | Usar apenas plantas fabris industriais modernas de grande escala. |
| **2026-10-27** | EP-00 | Áudio | Ruído e ressonância da cabine do carro na gravação externa | Cadeia de tratamento acústico: High-Pass 80Hz, Spectral Denoise, EQ 320Hz/3kHz, compressão e -14 LUFS. |
| **2026-10-27** | EP-00 | Áudio Trilha | Trilha de fundo conflitando com a edição externa | Deixar a trilha musical desativada por padrão no render final (`partes.json`), pronta para pós externa. |
| **2026-10-27** | EP-00 | Cortes 9:16 | Legendas cobrindo botões do TikTok/Instagram | Ancorar legendas palavra por palavra estritamente em `y=1020` (linha divisória segura). |
| **2026-10-27** | EP-00 | Cortes 9:16 | Cards estáticos sem dinamismo visual nos Shorts | Implementar animação item por item (*staggered ease-out*) com sound design sincronizado (`whoosh`, `clique`, `check`). |
| **2026-10-27** | EP-00 | Cortes 9:16 | Falta de CTA e identidade no fim do corte vertical | Concatenar vinheta animada oficial final (`outro_drgestao_shorts_30fps.mp4`) com áudio a -14 LUFS. |
| **2026-10-27** | EP-00/EP-01 | B-Rolls | Integração da API Pixabay para acervo têxtil e industrial em Full HD | Usar `scripts/broll_pixabay.py` com busca em inglês (ou termos PT auto-traduzidos) e filtro live-action (`video_type=film`). |
| **2026-10-27** | Geral | B-Rolls | B-Rolls genéricos de indústrias pesadas não relacionados ao vestuário | B-Rolls devem retratar estritamente confecção do vestuário (costura, enfesto, corte de tecidos, araras, linhas de confecção, estamparia e modelagem). |
| **2026-10-27** | Geral | Marca d'Água | Falta de assinatura visual contínua do canal no vídeo horizontal | Marca d'água oficial branca (`Logo-Branco-Crop.png`) fixada permanentemente no canto inferior direito (`x=1697`, `y=1016`, `w=175px`, `opacity=0.92`). |
| **2026-10-27** | Geral | Estilo Visual | Dinamismo entre b-rolls e motion graphics baseado nas referências | Alternância rítmica entre estilo `moldura` (card 4px branco sobre fundo gradiente da marca), `letterbox` (barras com degradê azul/lilás), palco PiP e sidecars flutuantes. |

---

## 10. Checklist de Qualidade Pré-Renderização (Obrigatório para Todos os EPs)

Antes de aprovar e entregar qualquer episódio ou corte, verificar rigorosamente os itens abaixo:

- [ ] **Rosto Desobstruído:** O apresentador está 100% visível, sem cards, legendas ou B-rolls sobrepondo seus olhos, boca ou tronco.
- [ ] **Lower Third Perfeito:** `Luiz Roberto Saraiva` completo, sem quebras indesejadas de linha e sem cortes de texto na máscara.
- [ ] **Loudness Padrão Broadcast:** Áudio principal e vinhetas nivelados em `-14 LUFS` com True Peak em `-1.0 dBFS`.
- [ ] **Safe Zone 9:16 Respeitada:** Nenhuma informação relevante abaixo de `y=1550` ou acima de `y=220`, legendas fixadas em `y=1020`.
- [ ] **Identidade Visual Dr. Gestão:** Paleta oficial (`#004aad`, `#8e7de5`, `#2f97d4`), fonte Segoe UI Bold / Inter e Logo Branca no canto superior direito nos cortes verticais.
- [ ] **7 Cortes Extraídos e Nivelados:** Cada corte com gancho forte nos primeiros 3 segundos, duração inferior a 60s, tópicos animados e vinheta final de fechamento.
