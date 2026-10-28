---
name: dr-gestao
description: Automatiza a edição completa dos episódios do canal Dr. Gestão (Luiz Roberto Saraiva) no formato 16:9 (YouTube) e a extração e renderização dos 7 cortes virais no formato 9:16 (Shorts/Reels/TikTok) com split stage, legendas dinâmicas, sound design e vinhetas. Inclui fluxo contínuo de aprendizado e registro de melhorias e preferências a cada novo episódio. Ative em "edita o ep do dr gestao", "gerar cortes dr gestao", "novo episodio dr gestao", "ajustes dr gestao", "/dr-gestao".
---

# Skill de Edição Automatizada — Dr. Gestão

Esta skill padroniza, automatiza e governa a edição dos vídeos do canal **Dr. Gestão (Luiz Roberto Saraiva)** — especialista com mais de 29 anos de chão de fábrica focado em alta performance e lucro real em confecções do vestuário.

A skill atende aos dois formatos da marca:
1. **Episódio Completo 16:9 (YouTube Principal):** Gancho inicial + fala do carro com áudio tratado + vinheta oficial + vídeo principal com lower third, b-rolls tela cheia e motions laterais alternados.
2. **7 Cortes Virais 9:16 (Shorts / Reels / TikTok):** Formato vertical em Duas Zonas (*Split Stage*), legendas cinéticas palavra por palavra ancoradas no peito, cards animados item por item com sound design sincronizado e vinheta final de fechamento.
3. **Protocolo de Aprendizado Contínuo:** Todas as correções e preferências solicitadas pelo usuário são incorporadas permanentemente ao arquivo mestre `PREFERENCIAS.md` e aos scripts modelo, garantindo evolução contínua da qualidade a cada novo episódio.

---

## 1. Identidade Visual e Padrões da Marca

- **Paleta de Cores Oficial:**
  - **Azul Dr. Gestão (Destaque Primário):** `#004aad`
  - **Lilás / Roxo (Secundária e Acentos):** `#8e7de5`
  - **Azul Ciano (Realces e Detalhes):** `#2f97d4`
  - **Fundo Escuro com Gradiente:** `#0a0e1a` a `#1a2d6e`
  - **Texto Base:** `#ffffff` com sombras suaves `#000000` (alpha 0.85)
- **Tipografia:** Fonte `Segoe UI Bold` / `Inter` (pesos 600, 700, 800).
- **Assinatura e Lower Third Oficial:**
  - Nome: `Luiz Roberto Saraiva` (nunca abreviar).
  - Subtítulo: `Dr. Gestão · Alta Performance em Confecção do Vestuário`.
  - Largura: até `1150px` com `width: max-content` para garantir leitura sem cortes.
- **Áudio:** Masterização final em `-14 LUFS` (True Peak `-1.0 dBFS`). Trilha de fundo musical **desativada por padrão** no render do episódio completo para pós-produção externa.

---

## 2. Estrutura de Diretórios e Herança de Projetos

A estrutura do projeto está organizada em:
```text
d:\Drifit\Editor\
├── novo_episodio.py                          <- Gerenciador multi-projetos
├── projetos\dr-gestao\
│   ├── branding\                             <- Identidade Visual Central Herdada
│   │   ├── PREFERENCIAS.md                   <- DIRETRIZES VIVAS (Atualizado a cada feedback)
│   │   ├── config.json                       <- Paleta e parâmetros da marca
│   │   ├── logos\                            <- Logo-Branco.png, TikTok, Shopee, Mercado Livre, Shein
│   │   ├── overlays\                         <- Vinhetas, transições alpha ProRes/VP9, outro shorts
│   │   ├── sons\                             <- Kit de SFX (whoosh, clique, check, swish, impacto)
│   │   ├── vinhetas\                         <- Intro-Dr-Gestao.mp4
│   │   └── scripts\                          <- Scripts base e templates reutilizáveis
│   └── episodios\
│       ├── EP-00\                            <- Episódio 00 de referência aprovado
│       └── EP-<XX>\                          <- Próximos episódios (EP-01, EP-02...)
│           ├── brutos\                       <- Gravações brutas originais
│           ├── workspace\                    <- Scripts de render, transcrição e assets
│           └── renders\                      <- Renders finais 16:9 e cortes_9_16/
```

---

## 3. Passo a Passo: Criação e Edição do Episódio Completo (16:9)

### Passo 3.1: Criar o Novo Episódio
Para criar a estrutura herdando automaticamente toda a identidade visual e scripts do Dr. Gestão:
```bash
python d:\Drifit\Editor\novo_episodio.py dr-gestao EP-01 "caminho\para\gravacao.mp4"
```
Isso copia automaticamente:
- `PREFERENCIAS.md` atualizado
- Logos oficiais (`Logo-Branco.png`, marketplaces)
- Vinhetas oficiais (`Intro-Dr-Gestao.mp4` e `outro_drgestao_shorts_30fps.mp4`)
- Efeitos sonoros (`whoosh`, `clique`, `check`, `swish`)
- Transições de marca transparentes (`transicoes/`)
- Scripts de renderização (`render_todos_cortes.py`, `clean_car_audio.py`, `build_intro_and_merge.py`)

### Passo 3.2: Tratamento de Áudio de Campo (Voz do Carro / Ambiente)
Gravações externas ou na cabine do carro sofrem com ressonância e ruído de asfalto. Execute o script de limpeza acústica:
```bash
python clean_car_audio.py
```
**Cadeia acústica obrigatória aplicada:**
1. Extração WAV 48kHz stereo.
2. High-Pass Filter em `80 Hz` para eliminar sub-graves e trepidação mecânica.
3. *Spectral Denoise* com gating suave (`prop_decrease=0.82`) preservando harmônicos vocais.
4. EQ Paramétrica: atenuação de ressonância de cabine em `320 Hz` (`-2.5 dB, Q=1.2`) e reforço de inteligibilidade em `3000 Hz` (`+2.0 dB, Q=1.0`).
5. Compressão vocal suave (`threshold=-18dB, ratio=2.5`) e normalização para `-14 LUFS`.

### Passo 3.3: Estrutura da Linha do Tempo do Episódio 16:9
O episódio completo do Dr. Gestão é estruturado obrigatoriamente em 4 blocos sequenciais:

1. **Gancho Inicial (~0:00 - ~0:02.3s):**
   - Frase curta e incisiva pinçada do meio do vídeo (ex.: *"O grande problema de todo mundo é vendas"*).
   - Lettering do gancho com a palavra-chave em azul ciano `#58a2eb` e sublinhado branco no terço direito.
2. **Fala Introdutória no Carro (~0:02.3s - ~0:30.5s):**
   - Apresentação contextualizada do tema gravada no carro.
   - Eliminação de respiros longos e hesitações finais.
   - Card explicativo sincronizado no canto inferior.
3. **Vinheta Oficial do Canal (~0:30.5s - ~0:38.4s):**
   - `Intro-Dr-Gestao.mp4` em 1080p 30fps nivelada em -14 LUFS.
4. **Conteúdo Principal (~0:38.4s em diante):**
   - **Lower Third:** Entrada em `0.4s` com `Luiz Roberto Saraiva / Dr. Gestão · Alta Performance em Confecção do Vestuário`.
   - **Posicionamento de Cards:** Alternância balanceada entre lado esquerdo (`x=100`) e lado direito (`x=1180` a `1240`), respeitando o espaço do apresentador (`rosto: [980, 420]`).
   - **B-Rolls:** Obrigatoriamente em **tela cheia** (`card=False`), com *Ken Burns* suave (`kb=1.06`) e chip temático no rodapé. Nunca usar imagens modestas quando o discurso citar indústrias grandes.
     - **Busca e Download Automático de B-Rolls:**
       ```bash
       # Pixabay (Oficial - busca em inglês ou termos em português auto-traduzidos):
       python scripts/broll_pixabay.py "garment factory" -o media/broll -n 2
       python scripts/broll_pixabay.py "sewing machine" --dry-run
       # Pexels (Alternativo):
       python scripts/broll_pexels.py "textile manufacturing" -o media/broll
       ```
   - **Transições:** Transição diagonal transparente da marca (`transicao_wipe_drgestao_16x9.mov`) nos cortes temáticos principais.

### Passo 3.4: Renderização e Concatenação Final (16:9)
Execute:
```bash
python build_intro_and_merge.py
```
O script gera o arquivo final completo e consolidado: `renders/EP<XX>_final_completo.mp4`.

---

## 4. Passo a Passo: Extração e Renderização dos 7 Cortes (9:16)

Cada episódio alimenta 7 cortes de alto impacto para Shorts, Reels e TikTok (< 60 segundos cada).

### Passo 4.1: Seleção dos 7 Ganchos Estratégicos
Mapeie na transcrição (`media/palavras_saida.json`) 7 trechos de alta retenção que cubram os pilares do Dr. Gestão:
1. **Corte 01 · Diagnóstico / Problema de Vendas & Minutagem:** O gargalo das confecções tradicionais.
2. **Corte 02 · Oportunidade / Dinheiro na Mesa:** Os 3 passos (Minerar, Validar, Vender).
3. **Corte 03 · Escala / Virada nos Marketplaces:** TikTok Shop, Shopee, Mercado Livre e Shein.
4. **Corte 04 · Realismo / A Ilusão do Milhão Fácil:** Gestão responsável e estrutura enxuta.
5. **Corte 05 · Casos Reais / Faturamento 300k a 500k Enxuto:** Alerta sobre a reforma tributária 2026/2027.
6. **Corte 06 · Ponto Crítico / Faturamento vs Lucro Real:** Ter vendas sem ter caixa no bolso.
7. **Corte 07 · Autoridade / Bastidores & 29 Anos de Prática:** Apresentação e chamada oficial.

### Passo 4.2: Padrão Visual em Duas Zonas (Split Stage 9:16)
- **Zona Superior (0 a 960px):**
  - Fundo em gradiente marinho escuro radial (`#0a0e1a` a `#1a2d6e`).
  - Badge em pílula lilás/ciano com o tema editorial no topo esquerdo.
  - Logo oficial branca (`Logo-Branco.png`) fixada no topo direito (`x=790, y=74`).
  - Título em caixa alta branco (`font-size: 46px`).
  - Lista de itens/etapas com animação *staggered ease-out* e slide horizontal.
  - Ícones vetoriais: checkmarks esmeralda (`#10b981`), alertas de exclamação (`#eb1e3c`), contadores de faturamento ou logos oficiais de marketplaces.
  - Stepper inferior da zona superior indicando a etapa do raciocínio (`01. DIAGNÓSTICO`, `02. MINERAR`, etc.).
- **Zona Inferior (960 a 1920px):**
  - Crop centrado no Dr. Gestão peito para cima (`cx=980, cy=420`), redimensionado para `1080x940`.
  - Cantos superiores arredondados (`radius=36px`) com borda lilás translúcida (`rgba(142,125,229, 0.7)`).
- **Legendas Dinâmicas Palavra por Palavra (Kinetic Subtitles):**
  - Ancoradas rigorosamente na linha central `y=1020` (sobre o peito, em safe zone total).
  - Agrupamento de 3 a 5 palavras por frase.
  - A palavra falada no instante exato acende na cor da marca (`#004aad` / `#8e7de5` / `#2f97d4`).
- **Sound Design Sincronizado:**
  - `whoosh_curto.wav` na entrada do card.
  - `clique2.wav` na revelação do badge.
  - `check.wav` a cada bullet/item revelado.
  - `swish.wav` no encerramento e transição do card.
- **Fechamento Oficial:**
  - Concatenação obrigatória com `outro_drgestao_shorts_30fps.mp4` (avatar animado + chamada para ação) com áudio normalizado em `-14 LUFS`.

### Passo 4.3: Renderizar os Cortes
Para renderizar todos os 7 cortes em sequência:
```bash
python render_todos_cortes.py
```
Para renderizar um corte específico para teste rápido:
```bash
python render_todos_cortes.py --cuts 1
python render_todos_cortes.py --cuts 3 5
```
Os vídeos finais são salvos em: `renders/cortes_9_16/EP<XX>_corte_<YY>_<tema>.mp4`.

---

## 5. Protocolo de Aprendizado Contínuo & Feedback a Cada Novo EP

Conforme solicitado, **o sistema deve aprender e incorporar correções a cada novo episódio**.

### A Regra de Ouro da Memória Central:
> **Nenhuma correção pedida pelo usuário fica restrita ao arquivo local do episódio.**
> Sempre que o usuário apontar uma falha, ajuste visual, alteração de copy, timing ou preferência estética:
> 1. O código local do episódio é imediatamente ajustado e validado.
> 2. A nova regra é **documentada imediatamente** em `d:\Drifit\Editor\projetos\dr-gestao\branding\PREFERENCIAS.md`.
> 3. Os scripts modelo em `d:\Drifit\Editor\projetos\dr-gestao\branding\scripts\` são atualizados para que os próximos episódios já nasçam com a correção ativa.
> 4. Uma nova linha é registrada na tabela de histórico de melhorias.

### Fluxo Operacional de Correção:
```text
[Solicitação do Usuário]
         │
         ▼
[1. Ajustar e testar no episódio atual] ────► Gera snapshot/render de validação
         │
         ▼
[2. Promover para PREFERENCIAS.md] ──────────► Atualiza regra na seção correspondente
         │
         ▼
[3. Atualizar branding/scripts/] ────────────► Atualiza templates de cortes e render
         │
         ▼
[4. Registrar no Histórico de Versões] ──────► Documenta data, motivo e regra criada
```

---

## 6. Checklist de Qualidade Pré-Renderização

Antes de dar o episódio ou cortes como concluídos, validar:

- [ ] **Rosto Desobstruído:** O apresentador está 100% visível, sem cards, legendas ou B-rolls sobrepondo seus olhos, boca ou tronco.
- [ ] **Lower Third Perfeito:** `Luiz Roberto Saraiva` completo, sem quebras indesejadas de linha e sem cortes de texto na máscara.
- [ ] **Loudness Padrão Broadcast:** Áudio principal e vinhetas nivelados em `-14 LUFS` com True Peak em `-1.0 dBFS`.
- [ ] **Safe Zone 9:16 Respeitada:** Nenhuma informação relevante abaixo de `y=1550` ou acima de `y=220`, legendas fixadas em `y=1020`.
- [ ] **Identidade Visual Dr. Gestão:** Paleta oficial (`#004aad`, `#8e7de5`, `#2f97d4`), fonte Segoe UI Bold / Inter e Logo Branca no canto superior direito nos cortes verticais.
- [ ] **7 Cortes Extraídos e Nivelados:** Cada corte com gancho forte nos primeiros 3 segundos, duração inferior a 60s, tópicos animados e vinheta final de fechamento.
