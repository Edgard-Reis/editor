# Preferências de Edição — Ozon Tech

Este documento reúne todas as decisões estéticas, diretrizes de edição e padrões visuais específicos da **Ozon Tech**. Todos os episódios criados para este projeto herdam essas definições por padrão.

---

## 1. Identidade Visual da Marca
- **Canal / Projeto:** Ozon Tech
- **Proposta Visual:** Estética tecnológica, moderna, limpa e profissional (Dark Tech / Glassmorphism).
- **Paleta de Cores Oficial:**
  - **Destaque Primário (Cyan Tech):** `#00d2ff` (ponto focal, palavras de impacto e bordas ativas)
  - **Secundária (Eletric Blue):** `#3a86ff` (gradientes e destaques complementares)
  - **Ciano Brilhante:** `#00f0ff` (detalhes finos e ícones luminosos)
  - **Fundo dos Cards:** `rgba(15, 23, 42, 0.85)` (azul petróleo escuro translúcido com `backdrop-filter: blur(16px)`)
  - **Texto Principal:** `#ffffff` (alto contraste)
  - **Texto de Apoio / Subtítulo:** `#94a3b8` (cinza azulado suave)
- **Tipografia:**
  - Família: **Inter** / **Roboto** (sans-serif moderna com pesos 400, 600, 800)

---

## 2. Regras de Lower Thirds & Apresentador
- **Posição:** Canto inferior esquerdo (`x=100`, `y=780` a `820`).
- **Composição:**
  - **Linha 1:** Nome do Especialista / Apresentador (em branco, negrito, tamanho 44px).
  - **Linha 2:** Ícone Ozon Tech + Credencial Oficial (*Ozon Tech · Inovação & Tecnologia*).
- **Largura Dinâmica:** Auto-ajuste para evitar cortes de texto (`max-width: 1150px`).

---

## 3. Posicionamento de Cards e Motions
- **Alternância Dinâmica:**
  - Lado esquerdo padrão: `x=100`, `y=320`
  - Lado direito padrão: `x=1220`, `y=320`
- **Zero Obstrução:** Nunca posicionar cards ou b-rolls sobrepondo o rosto do apresentador.
- **Ritmo e Animação:** Entradas suaves com blur e escala (`scale: 0.95 -> 1.0`), saídas rápidas e fluidas.

---

## 4. Regras de B-Rolls
- **Modo Padrão:** **Tela Cheia** (`cn.broll(..., card=False)`).
- **Animação:** Push-in sutil (*Ken Burns* suave com `kb=1.05`).
- **Identificação:** Chip informativo discreto no rodapé identificando o conceito abordado.
- **Coerência Temática:** Imagens em alta resolução de servidores, código, telas de software, circuitos e tecnologia real.

---

## 5. Áudio e Masterização
- **Loudness Padrão:** `-14 LUFS` (padrão YouTube / Web) com True Peak máximo em `-1.0 dBFS`.
- **Trilha Sonora:** Controlada por projeto (geralmente desativada ou aplicada na pós-produção externa).
- **Sound Effects:** Kit de sons secos (whoosh sutil, click tech, swoosh).

---

## 6. Recursos da Marca
- Coloque os arquivos de logo (vetores SVG e PNGs transparentes) em `branding/logos/`.
- Coloque a vinheta de introdução/encerramento em `branding/vinhetas/`.
- Coloque vinhetas de transição ou áudios exclusivos em `branding/sons/`.

---

## 7. Cortes Verticais 9:16 (Shorts / Reels / TikTok)
- **Volume:** 7 cortes de alto impacto (< 60s) por episódio.
- **Padrão Obrigatório de Nomenclatura:**
  - `EP<XX>_corte_<YY>_<tema>.mp4` (ex.: `EP01_corte_01_ia_codigo.mp4`).
- **Legendas Dinâmicas:** Centralizadas na Safe Zone do rodapé com palavra ativa destacada em Cyan Tech (`#00d2ff`).

