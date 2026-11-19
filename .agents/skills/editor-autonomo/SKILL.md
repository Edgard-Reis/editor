---
name: editor-autonomo
description: Protocolo obrigatório do Editor Autônomo para ingestão, briefing editorial humano, renderização de vídeo Master (16:9 ou 9:16) com Motion Graphics e extração de cortes virais estilo OpusClip com notas de potencial.
---

# Protocolo do Editor Autônomo (`Editor`)

Este protocolo rege todo fluxo de edição, briefing, renderização e corte de vídeo dentro da sandbox `D:\Drifit\Editor`. Siga as etapas estritamente na ordem abaixo, respeitando os **Portões Humanos** e preservando os módulos existentes em `core/`.

- **Isolamento de Episódio (Proibição de Contaminação Cruzada):** Ao editar qualquer episódio, é terminantemente proibido ler, copiar ou reaproveitar textos, cenas HTML, EDLs ou renders de outros episódios ou pastas de testes antigos (`ep-test-edl`, `ep-01-*`, `teste-piloto-*`, `REFERENCIA_APROVADA_*.md`). Só é permitido ler os arquivos do episódio atual e o kit base da marca (`config.json`, `PREFERENCIAS.md`, `DESIGN_SYSTEM_*`, `sons/`, `logos/`, `overlays/`).

---

## Etapa 1: Ingestão, Transcrição & Roteamento de Modo

1. **Detecção Automática de Orientação:**
   - Analise os metadados do vídeo de entrada via `core/ingest.py` para detectar automaticamente se o material original é **`16:9`** (horizontal) ou **`9:16`** (vertical).
2. **Processamento Inicial:**
   - Execute ingestão + transcrição local com `faster-whisper-large-v3-turbo` (INT8, CPU 8 threads) + tratamento/limpeza de áudio para **`-14 LUFS`**.
   - **Preservação:** Nunca altere o arquivo bruto original (`ΔHash = 0`).
3. **Revisão Rápida de Transcrição (`transcript_review.py`):**
   - Caso existam palavras ou termos próprios com confiança **`< 0.80`**, liste-os rapidamente ao usuário com o trecho ao redor para confirmação ortográfica antes de avançar para decisões editoriais.
4. **Roteamento de Modo (Intenção do Usuário):**
   - **Modo Completo (Vídeo Bruto → Master + Cortes opcionais):** Prossiga normalmente para a **Etapa 2**.
   - **Modo Só Cortes / OpusClip (Vídeo Já Editado → Apenas Cortes `9:16`):** Pule as **Etapas 2 e 3** e vá diretamente para a **Etapa 5**, usando a quantidade de cortes solicitada pelo usuário (ou sugerindo uma quantidade proporcional à duração caso ele não tenha especificado).

---

## Etapa 2: Briefing Editorial do Master — Portão Humano 1

0. **Padrão Autônomo Obrigatório (Usuário Leigo / Pedidos Simples):**
   - Mesmo que o usuário peça apenas *"edita esse vídeo para mim"* em linguagem natural simples — sem citar termos técnicos como `fullscreen_motion`, `SFX`, `GSAP` ou `LUFS` — o editor **DEVE aplicar automaticamente por padrão**:
     - **a) Limpeza acústica e ritmo seguro:** remover pausas longas, vícios de linguagem e repetições/falsos começos preservando respiro de **`70–100 ms` pré-palavra** e **`180–220 ms` (`~200 ms`) pós-palavra**, micro-fade de no máximo **`6 ms`** nos cortes de áudio e normalização **`-14 LUFS` / `-1.0 dBTP`**.
     - **b) 2 a 3 Cenas Inéditas de Motion Graphics Full-Screen (`fullscreen_motion`):** projetar, detalhar no `BRIEFING.md` (Portão 1) e criar sob medida em `workspace/motions_custom/<id_cena>.html` **2 a 3 cenas inéditas em tela cheia** nos conceitos-chave, métodos, listas ou viradas narrativas do vídeo — **proibindo balões/cards laterais repetitivos**.
     - **c) Sound Design (`SFX`) 100% Automático e Sincronizado:** acionar automaticamente efeitos sonoros reais de `branding/sons/` via `RobustSoundBus` (`som.py`) — `whoosh_curto.wav` na entrada da cena, `clique2.wav`/`swish.wav` nos marcos internos da animação e `check.wav`/`impacto_grave.wav` na conclusão — mixados sem distorção junto à voz no master `-14 LUFS`.
     - **d) Vinhetas Inteligentes Multi-Marca (`brand_bumpers.py` — Master `16:9` e Cortes `9:16`):** incluir automaticamente vinheta de fechamento (*Outro*) seguindo a hierarquia segura em 3 níveis:
       - *Nível 1 (`ready_asset`):* usar o arquivo de vinheta final em `projetos/<marca>/branding/overlays/` ou `vinhetas/` (honrando `assets_base_dir`/`vinhetas` no `config.json`) com áudio normalizado em `-14 LUFS`.
       - *Nível 2 (`generate_hyperframes`):* se houver logo ou paleta+nome no `config.json` sem vídeo pronto, gerar automaticamente vinheta animada via HyperFrames/GSAP (`2,5s`–`3,0s`) + SFX (`impacto_grave.wav`/`check.wav`) e salvar em `projetos/<marca>/branding/overlays/` para reuso futuro.
       - *Nível 3 (`clean_fade_out`):* se a marca nova não tiver nenhum asset nem identidade cadastrada, nunca quebrar o render — aplicar *fade-out* limpo (`0,5s` vídeo+áudio) e registrar aviso amigável.
       - *Intro sob demanda ou configurada:* quando `auto_intro` estiver ativo no `config.json` ou o usuário solicitar criação de vinheta de introdução/fechamento, gerar via HyperFrames/GSAP + SFX e salvar os `.mp4` (`16:9` e `9:16`) em `projetos/<marca>/branding/overlays/`.
   - **Proibição de Slides Estáticos (Master 16:9 e Cortes 9:16):** Tanto no Master `16:9` (`1920x1080`) quanto na janela superior (`1080x960`) ou tela cheia (`1080x1920`) dos cortes `9:16`, **é terminantemente proibido gerar quadros/cards estáticos estilo "slide de PowerPoint"** (incluindo cartões estáticos desenhados via Pillow). Toda cena gráfica deve ter movimento contínuo real em HTML/CSS/GSAP/HyperFrames (stagger de elementos, traçados SVG animados com `pathLength` + `strokeDashoffset`, entrada/saída fluida e SFX automático via `RobustSoundBus`).

1. **Leitura Obrigatória Pré-Briefing (Bloqueante):**
   - Antes de gerar `semantic_plan.json`, `BRIEFING.md` ou `edl_longo.json`, o agente **DEVE** carregar e obedecer estritamente:
     - `projetos/<marca>/branding/PREFERENCIAS.md` (ou o equivalente da marca ativa; para `dr-gestao` / derivados, todas as regras de marca vivem aqui);
     - `projetos/<marca>/motion-system/DESIGN_SYSTEM_MOTION_DR_GESTAO.md`;
     - `projetos/<marca>/motion-system/CATALOGO_MOTIONS.md`;
     - `vortex-edicao/guia/MOTIONS.md`.
2. **Análise Editorial & Blindagem Acústica de Cortes (`analyze.py`, `semantic_planner.py`, `edl_builder.py`):**
   - Leia o pedido natural do usuário (`user_brief.json` e instruções da conversa).
   - **Trava Anti-Corte de Fala:**
     - É **proibido** quebrar unidades ou frases por pontos de abreviações (`"Dr."`, `"Dra."`, `"Sr."`, `"Sra."`, etc.) ou pontuação sem pausa respiratória real.
     - É **proibido** cortar palavras soltas (incluindo muletas lexicais) no meio de frases contínuas sem silêncio adjacente.
     - Todo corte DEVE usar subtração segura de silêncios/intervalos (`vortex-edicao/cortar.py`), preservando margem acústica de **`70–100 ms` pré-palavra** e **`180–220 ms` pós-palavra** (além de `150 ms` na entrada e `350 ms` no fim do vídeo, alinhados em múltiplos de `1/30s`) diretamente em `raw_in`/`raw_out`, mantendo **`out_out - out_in == raw_out - raw_in`**.
   - **Proibição de Legendas no Master 16:9 & Regra Anti-Transcrição:**
     - É **terminantemente proibido** incluir legendas dinâmicas (`dynamic_captions`) no Master `16:9` (legendas palavra por palavra são exclusivas dos cortes verticais `9:16` ancoradas em `y=1020`, salvo solicitação explícita do usuário).
     - O motion **não transcreve a fala** e não usa palavras vazias soltas: valide obrigatoriamente com `checa_texto.py` (`0` erros).
   - **Regra de Ouro Visual — Proibição de "Chuva de Cards/Balões" & Obrigatoriedade de Motion Graphics Full-Screen (`fullscreen_motion`):**
     - **Proibição de "chuva de cards/balões":** É **terminantemente proibido** poluir o vídeo com balões laterais ou cards de texto repetitivos (`card_flutuante`, cascata de `titulo_heroi` lateral). Cards laterais só devem ser usados se o usuário solicitar explicitamente e de forma pontual.
     - **Obrigatoriedade de Motion Graphics Full-Screen (`1920x1080` ou `1080x1920`):** Sempre que o usuário solicitar motion graphics ou houver explicação de conceitos, métodos, listas, processos ou viradas narrativas, o agente **DEVE** projetar **cenas inéditas em tela cheia** (`fullscreen_motion`, camada `L5_fullscreen_motion`, ocupando `100%` do viewport acima do vídeo base enquanto a narração continua), criadas sob medida em `workspace/motions_custom/<id_cena>.html` com diagramas vetoriais SVG animados, fluxogramas, etapas conectadas, tipografia cinética em tela inteira, ícones animados em GSAP (`gsap.min.js` local + fontes locais) e SFX sincronizado. **Nunca copie layouts ou textos prontos de episódios ou testes anteriores.**
   - **Oportunidades de Motion Graphics Homologados** (`cenas.py`, `cenas.css`, `ilustra.py`, `estagio.py`, `som.py`, `motion_library/components/titulo_heroi` T10 V2):
     - `fullscreen_motion` (`L5_fullscreen_motion` em `1920x1080` / `1080x1920` via `workspace/motions_custom/<id_cena>.html` com transição limpa ou `transicao_marca` enquanto a narração segue contínua)
     - `titulo_heroi` T10 V2 (pontual nos marcos principais; perfis `.th-heroi-destaque-ciano`, `.th-heroi-virada-chave`, `.th-heroi-alta-minutagem` alternando nos flancos livres `esq`/`dir` sem cruzar o rosto)
     - `lower_third` (`cn.lower_third` completo com vidro escuro, máscara e credenciais)
     - `barra_progresso`, `stepper`, `pip_stage`, `split_stage`, `transicao_marca` (e `card_flutuante` apenas sob solicitação explícita do usuário)
     - `broll_industrial` (`cn.broll` com Ken Burns sem obstruir o rosto)
     - `sound_design_sync` (`RobustSoundBus` de `som.py` com SFX de `branding/sons/`) e micro-zooms (`cn.bate`) ancorados no rosto (`rosto: [980, 420]`).
3. **Geração do `BRIEFING.md` (Detalhamento Obrigatório das Cenas Full-Screen):**
   - Escreva `BRIEFING.md` no diretório do episódio em **linguagem clara de editor humano** (evite jargão técnico de código, hashes ou parâmetros internos de FFmpeg). Explique o que será cortado, o ritmo da edição e onde cada elemento visual entrará e por quê.
   - **Detalhamento explícito de cada Cena Full-Screen (`fullscreen_motion`):** Para cada cena em tela cheia planejada, o `BRIEFING.md` deve listar explicitamente: ID da cena, minutagem (início → fim), gatilho falado, conceito visual animado inédito, elementos gráficos (diagramas SVG, fluxogramas, etapas, ícones, tipografia cinética), transição de entrada/saída e arquivo dedicado (`workspace/motions_custom/<id_cena>.html`), para aprovação humana no Portão 1.
4. **PORTÃO HUMANO 1 (PARADA OBRIGATÓRIA):**
   - Apresente o resumo do `BRIEFING.md` ao usuário e **PARE**.
   - **É TERMINANTEMENTE PROIBIDO renderizar o Master antes do "OK" explícito ou aprovação após ajustes do usuário.**

---

## Etapa 3: Render do Master

1. **Montagem da EDL (`edl_builder.py`):**
   - Somente após o "OK" do usuário no Portão Humano 1, gere ou atualize `edl_longo.json` refletindo todos os cortes seguros (margem pré `70–100 ms` e pós `180–220 ms` diretamente em `raw_in`/`raw_out`, zero corte intra-frase) e camadas de Motion Graphics aprovadas, sem `dynamic_captions` em `16:9` (salvo pedido explícito).
2. **Motor Visual Obrigatório HTML/CSS/GSAP/HyperFrames (`edl_renderer.py` + `cenas.py` + `render_rapido.py`):**
   - É **TERMINANTEMENTE PROIBIDO** gerar PNGs estáticos via Pillow (`_make_title_png`, retângulos estáticos) ou quadros estáticos estilo "slide de PowerPoint" para títulos, lower thirds, cards ou cenas de apoio (tanto no Master `16:9` quanto nos cortes `9:16`).
   - Todo elemento visual (incluindo cenas inéditas `fullscreen_motion` em `workspace/motions_custom/<id_cena>.html` e overlays aprovados) deve ser renderizado pelo motor HTML/CSS/GSAP/HyperFrames com movimento contínuo real (stagger de elementos, traçados SVG animados, entrada/saída fluida) e SFX automático sincronizado via `RobustSoundBus` (`som.py` + `branding/sons/`), utilizando exclusivamente fontes locais, `gsap.min.js` local e templates/estilos/componentes aprovados (`cenas.py`, `cenas.css`, `ilustra.py`, `estagio.py`, `som.py`, `titulo_heroi` T10 V2, `branding/sons/`, `branding/overlays/transicoes/`), executando obrigatoriamente a trava `checa_texto.py` antes do render.
   - Renderize o vídeo Master **preservando a orientação original** detectada na Etapa 1 (`16:9` ou `9:16`), com micro-fade nos cortes de áudio de no máximo **`6 ms` (`0.006s`)**, aplicação automática da vinheta final da marca (Níveis 1/2/3 via `core/brand_bumpers.py`) e normalização `-14 LUFS` / `-1.0 dBTP`.
3. **Validação Automática de QA e Conferência Visual de Quadros:**
   - Execute `video_verify.py` e `master_lint.py` para garantir integridade de áudio (`-14 LUFS`), ausência de frames pretos/travados e conformidade técnica.
   - Inspecione visualmente frames/snapshots extraídos das janelas com motion para validar o checklist de `PREFERENCIAS.md` §10: **rosto 100% desobstruído** (`rosto: [980, 420]`), alternância real de lados (`esq`/`dir`) e lower third legível sem corte de texto.
4. **Entrega e Ciclo de Ajustes:**
   - Entregue o Master renderizado para revisão humana.
   - Se o usuário solicitar ajustes em linguagem natural (ex.: "tira aquela frase aos 2:15", "aumenta o zoom ali", "muda o título"), **altere apenas a EDL (`edl_longo.json`) e re-renderize via `render_existing_episode()`** sem refazer transcrição ou ingestão.

---

## Etapa 4: Oferta Opcional de Cortes — Nunca Automático

- Somente **após** o Master ser aprovado pelo usuário (ou ao encerrar o fluxo do Master), **pergunte** ao usuário se ele deseja que você gere sugestões de cortes curtos verticais (`9:16` para Shorts/Reels/TikTok).
- Caso positivo, pergunte quantos cortes ele quer — sugerindo uma quantidade proporcional à duração do vídeo (por exemplo, ~3 a 5 cortes para vídeos de 10 min; ~5 a 8 para vídeos de 20+ min).
- **Nunca gere ou renderize cortes curtos automaticamente sem perguntar.**

---

## Etapa 5: Briefing Estilo OpusClip com Notas — Portão Humano 2

1. **Curadoria Narrativa:**
   - Caso o usuário aceite a oferta da Etapa 4 ou tenha entrado pelo **Modo Só Cortes / OpusClip** na Etapa 1, analise os arcos narrativos completos (início com gancho forte, desenvolvimento coeso e fechamento claro).
2. **Briefing de Cortes Sugeridos:**
   - Apresente um Briefing de Cortes estruturado contendo, para **cada** corte sugerido:
     - **Nota de Potencial (0 a 10)**
     - **Justificativa Editorial** (por que esse trecho retém atenção e funciona isolado)
     - **Gancho (Hook) de Abertura** (frase ou ideia nos primeiros 3 segundos)
     - **Minutagem Exata** (início → fim e duração estimada)
     - **Título Sugerido** (forte e chamativo para retenção)
3. **PORTÃO HUMANO 2 (PARADA OBRIGATÓRIA):**
   - **PARE** e aguarde a aprovação, seleção ou ajustes do usuário (ex.: aprovar apenas os cortes 1, 3 e 4, ou ajustar minutagem/título).
   - **Proibição de Slides Estáticos nos Cortes `9:16`:** Na janela superior (`1080x960`) ou tela cheia (`1080x1920`) dos cortes verticais, é proibido gerar cards estáticos tipo slide; utilize cenas HTML/CSS/GSAP/HyperFrames (`fullscreen_motion`) com movimento contínuo e disparo automático de SFX via `RobustSoundBus` (`whoosh_curto.wav`, `clique2.wav`/`swish.wav`, `check.wav`/`impacto_grave.wav`) normalizados em `-14 LUFS`.
   - **Limpeza de Abertura & Vinheta Final Automática (`9:16`):** Todo corte `9:16` deve sanitizar automaticamente o ponto de entrada (`sanitize_short_start_and_words` em `core/shorts_renderer.py`), descartando restos de palavras da frase anterior nos primeiros `0,4s` e vazamento da frase seguinte no fim, além de aplicar por padrão a vinheta final da marca em `9:16` conforme os Níveis 1/2/3 (`core/brand_bumpers.py`).
   - **Só renderize os cortes aprovados** após a confirmação humana, utilizando `core/shorts_renderer.py`.
