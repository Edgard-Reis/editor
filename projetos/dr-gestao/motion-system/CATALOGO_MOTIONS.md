# Catálogo de Motions — Dr. Gestão

Versão 0.4 (homologada na Fase 5.4 em 2026-11-04 com a promoção formal da técnica T10 para V2).  
Backup da v0.3: `CATALOGO_MOTIONS.md.bak_pre_fase5_4` (SHA-256 `77931A71ABEC71EA424085941C849EEE5144B6BCFF688BC4EC9B7A483DE267A6`).  
Somente catálogo: **documentação canônica do Motion System do canal Dr. Gestão.**

---

## 1. Duas dimensões, nunca misturadas

### 1.1 Evidência da informação (selos)
Definidos em `DESIGN_SYSTEM_MOTION_DR_GESTAO.md`, seção 0.2:
**[CÓDIGO]**, **[RELATÓRIO]**, **[MARCA]**, **[USUÁRIO]**, **[INTERPRETAÇÃO]**, **[PROPOSTA]**, **[NÃO VALIDADO]**.
Dizem *de onde vem* a informação.

### 1.2 Maturidade do componente (níveis)
Dizem *quão pronto está o recurso para reutilização*. Não indicam certeza da informação.

| Nível | Nome | Critério |
|---|---|---|
| **V0** | Proposto | Ideia sem implementação conhecida. |
| **V1** | Implementado em contexto único | Existe e foi renderizado em uma cena de referência aprovada; está **acoplado** a ela (coordenadas, tempos ou seletores fixos). A aprovação do usuário cobre a cena, **não** cada recurso individualmente. |
| **V2** | Reutilizável | Isolado da cena, parametrizável (sem coordenadas/tempos/seletores fixos) e testado em **dois ou mais contextos** (outra cena ou outro formato). |
| **NC** | Não classificado | Existe segundo outra fonte, mas esta documentação não revisou o código nem o comportamento. |

Progressão: V0 → V1 → V2. Para promover V1 → V2 é obrigatório refatorar em pacote compartilhado independente e validar em um segundo contexto real.  
**Estado atual na v0.4:** A técnica **T10 — Título herói por letra** foi promovida a **V2 (Reutilizável)** em 2026-11-04 após isolamento em módulo compartilhado (`titulo_heroi.py`/`titulo_heroi.css`), cobertura por 16 testes unitários automatizados, validação de build/lint e renderização convencional em dois contextos independentes (Virada de Chave e Alta Minutagem) expressamente aprovados pelo usuário. Todos os demais recursos e componentes permanecem em V1 ou NC.

Dependências comuns: GSAP 3.14.2 (CDN), HyperFrames 0.9.5, canvas 1920×1080, 30 fps.

## 2. Convenção de caminhos

Caminhos relativos à raiz do repositório (`d:\Drifit\Editor`), com `/` como separador.  
Nome de arquivo sem diretório refere-se aos workspaces experimentais documentados na seção 8 (`workspace_experimental_virada/` ou `workspace_experimental_minutagem/`).  
`cenas.py` aparece sempre com caminho completo.

---

## 3. Técnicas reutilizáveis

Evidência de implementação: **[CÓDIGO]** em `cena_virada.py` / `virada.css` e/ou `cena_minutagem.py` / `minutagem.css`, salvo indicação.  
Maturidade: **V1** salvo indicação expressa (T10 homologada como **V2** na Fase 5.4). A taxonomia de IDs e nomes T01 a T19 é fixa e canônica.

| ID | Técnica | Descrição | Dependências | Limitações | Maturidade |
|---|---|---|---|---|---|
| T01 | Traçado de caminho | `pathLength=1` + `strokeDashoffset 1→0` | SVG, GSAP | exige `stroke-dasharray:1`; só segmentos retos usados na Virada | V1 |
| T02 | Extrusão 2.5D | 3 traços SVG (sombra, corpo, luz) + `drop-shadow` | SVG/CSS | linhas/trilhos; sem rotação 3D | V1 |
| T03 | Plano de fuga | grade CSS `perspective + rotateX(64°)` com máscara radial | CSS | custo de render **não medido** | V1 |
| T04 | Câmera 2D | `x/y/scale` em um wrapper | GSAP | wrapper `.vc-cam` global na Virada; texto fora do wrapper | V1 |
| T05 | Paralaxe por camadas | fundo, mundo e tipografia com deslocamentos diferentes | GSAP | amplitudes pequenas | V1 |
| T06 | Gesto físico com overshoot | `back.out` em alavanca/lâmina/nós/selo | GSAP | objetos "mecânicos" | V1 |
| T07 | Halo de decisão | gradiente radial pulsante | CSS/GSAP | usa cores experimentais | V1 |
| T08 | Fila → rajada | pacotes que travam na decisão e saem pelos ramos | GSAP | trajeto manual; 14 pacotes fixos | V1 |
| T09 | Leque fantasma | tracejado com `strokeDashoffset` negativo | SVG/GSAP | específico de "possibilidades"; cor `#a78bfa` | V1 |
| T10 | Título herói por letra | Animação tipográfica com individualização de palavras (`.th-w`) e letras (`.th-l`), stagger progressivo, deslocamento vertical e blur decrescente. Módulo Python e CSS estrutural compartilhados em `fase5_experimento_t10/shared/`. | GSAP, CSS filter, Python standard library (`unicodedata`, `html`) | Validado em 16:9 nas duas cenas; formato 9:16 não validado; animação de saída sob responsabilidade da cena; localização atual em área experimental. | **V2** |
| T11 | Filete de entrada | `scaleX 0→1` | CSS/GSAP | — | V1 |
| T12 | Revelação sincronizada à fala | tempos absolutos por ápice | `media/palavras_saida.json` (referência) | tempos escritos à mão; sem tolerância medida | V1 |
| T13 | Sound design por evento | `registrar_automatico` com SFX do kit | `SoundBus` ou `sfx_fn`, `sons/*.wav` | volumes relativos; LUFS e True Peak ainda não medidos; meta não definida | V1 |
| T14 | Abertura com base de opacidade | piso em 25% no primeiro frame | GSAP | cena continua escura (luma ≈ 8) — **[RELATÓRIO]** | V1 |
| T15 | Entrada suave de B-roll | `entrada_de`, `entrada_dur` em `broll()` | `cenas.py` **da cópia experimental** | só nesta cópia; um B-roll testado | V1 |
| T16 | Anti-sobreposição de tweens | encurtar duração para terminar antes do próximo | GSAP, lint | manual; sem `overwrite:"auto"` — **[RELATÓRIO]** | V1 |
| T17 | Logos por `background-image` | evita `duplicate_media_discovery_risk` | CSS | testado em tiles de 78 px — **[RELATÓRIO]** | V1 |
| T18 | Poeira de profundidade | 9 partículas com deriva linear | CSS/GSAP | seletor `.vc-dust` global na Virada | V1 |
| T19 | Vinheta atrás do mundo | escurece só o fundo | CSS | — | V1 |

---

## 4. Componentes candidatos a reutilização

Candidatos apenas. Nenhum está isolado em biblioteca compartilhada; todos dependem de arquivos específicos das cenas experimentais.

### 4.1 Candidatos da cena Virada de Chave

| ID | Candidato | Origem | Dependências | Limitações | Maturidade |
|---|---|---|---|---|---|
| C01 | Trilho extrudado | `_rail()` em `cena_virada.py` | T01, T02, `.vc-r*` | Coordenadas fixas; IDs de gradiente `vcG1/vcG2` fixos | V1 |
| C02 | Piso em perspectiva | `.vc-floor` | T03 | Tweens com tempo absoluto fixo na timeline | V1 |
| C03 | Arco de câmera | Trechos `.vc-cam` | T04 | Tempos absolutos amarrados à fala de 5,20s | V1 |
| C04 | Junção + alavanca + lâmina | `.vc-junc*` | T06, T07 | Metáfora de rota comercial; posição `(748, 782)` fixa | V1 |
| C05 | Fluxo de pacotes | `_pacote()` | T08 | Trajeto retilíneo; 14 pacotes e tempos fixos | V1 |
| C06 | Nó de plataforma | `.vc-node*` | `logos/*`, T06 | 4 plataformas e coordenadas fixas | V1 |
| C07 | Título herói (kicker + título + herói) | `.vc-kicker/.vc-t1/.vc-t2` | T10, T11 | Texto fixo ("Chave"); 152 px | V1 |
| C08 | Âncora "N + RÓTULO" | `.vc-count*` | T11 | Rótulo pequeno (22 px); texto fixo | V1 |
| C09 | Selo de status verde | `.vc-status` | — | Relatório 3A: 12 px, discreto; cor experimental `#22c55e` | V1 (com ressalva) |
| C10 | Contrato de módulo `(html, js)` | `montar_virada()` | `build.py` | Acoplado ao `build.py`; ver seção 6 | V1 |
| C11 | Rota anterior (cinza, batente, rótulo) | `.vc-r-old`, `.vc-bufstop`, `.vc-oldlbl` | T01 | Rótulo de 12 px (informativo no 3A) | V1 (com ressalva) |

### 4.2 Candidatos da cena Alta Minutagem (Adicionados na v0.3)

Todos os itens abaixo são classificados estritamente como **V1 (Acoplados à Alta Minutagem)**.

| ID | Candidato | Origem / Arquivos | Descrição Funcional | Dependências | Limitações | Maturidade | Testes Necessários para V2 |
|---|---|---|---|---|---|---|---|
| **C12** | Cards Industriais 2.5D com Medidor Conceitual Uniforme | `cena_minutagem.py` (`ESTACOES`, `_html`), `minutagem.css` (`.cm-mod*`) | Módulo retangular 2.5D com perspectiva, borda luminosa, ícone vetorial, tag superior e medidor gráfico conceitual progressivo. | T02, T03, GSAP `back.out` | Geometria, textos e 3 estações fixas no código; requer CSS `.cm-mod*`. | **V1** | Parametrizar quantidade de cards (N itens), títulos, ícones e ângulos Y em função utilitária independente. |
| **C13** | Cronômetro Vetorial 2.5D | `cena_minutagem.py` (`chrono_html`), `minutagem.css` (`.cm-chrono*`) | Relógio/indicador vetorial circular com anel em gradiente, arco progressivo e ponteiro rotativo mecânico. | T01, T06, gradiente SVG | Coordenadas fixas; tempos amarrados à minutagem da cena. | **V1** | Extrair para widget visual isolado aceitando raio, posição (x,y) e duração de rotação do ponteiro. |
| **C14** | Válvula de Estreitamento | `cena_minutagem.py` (`choke_html`, `_rail_svg`), `minutagem.css` (`.cm-choke*`) | Conjunto mecânico composto por halo de atenção, alojamento industrial e mandíbulas que se aproximam para estreitar visualmente o conduto. | T01, T02, T06, T07 | Coordenadas físicas fixas (`x=1368, y=642`); dimensões de mandíbula estáticas. | **V1** | Generalizar geração de trajetórias e parâmetros de afunilamento em função matemática reutilizável. |
| **C15** | Pulsos Luminosos Conduzidos | `cena_minutagem.py` (`_animar_pulsos_continuos`), `minutagem.css` (`.cm-pulse`) | Partículas luminosas que percorrem o conduto SVG amplo e sofrem afilamento visual e atenuação de opacidade ao cruzar o afunilamento. | T01, T10, GSAP `tl` | Caminho fixo ancorado na linha Y=642; offsets temporais manuais. | **V1** | Criar gerador de pulsos acoplável a qualquer `path` SVG via GSAP MotionPathPlugin ou função paramétrica. |
| **C16** | Assinatura Conceitual Inferior com Selo de Status | `cena_minutagem.py` (`_html`), `minutagem.css` (`.cm-footer`, `.cm-sig`, `.cm-status`) | Barra de rodapé composta por linha separadora, texto institucional de diagnóstico (20 px) e chip/selo de status de estado. | T11, T06, tipografia monoespacada | Classes e posições ancoradas na camada `.cm-ui`; layout fixo para tela cheia. | **V1** | Módulo de rodapé padronizado aceitando lista de strings de status e cores de estado semântico. |

---

## 5. Análise de Candidatos que Surgiram nas Duas Cenas

As duas cenas aprovadas (*Virada de Chave* e *Alta Minutagem*) implementaram soluções visuais correlatas para resolver desafios narrativos distintos. A tabela abaixo documenta a convergência técnica:

| Técnica | Implementação na Virada de Chave | Implementação na Alta Minutagem | Status de Maturidade | Observação Arquitetural |
|---|---|---|---|---|
| **Extrusão 2.5D (T02)** | Trilhos bifurcados (`_rail` com 3 paths concêntricos) | Condutos industriais (`_rail_svg` com conectores e funil bézier) | **V1** | Código duplicado e adaptado ad-hoc em cada arquivo Python. Não há módulo compartilhado. |
| **Plano de Fuga (T03)** | Grade `.vc-floor__grid` (`rotateX(64deg)`) | Grade `.cm-floor__grid` (`rotateX(62deg)`) | **V1** | Classes e seletores locais independentes. Não há folha de estilo global compartilhada. |
| **Câmera 2D (T04)** | Wrapper `.vc-cam` com recuo final | Wrapper `.cm-cam` com aproximação e pan | **V1** | Tweens GSAP gerados diretamente nas timelines locais de cada cena. |
| **Poeira de Profundidade (T18)** | 9 partículas `.vc-dust` com deriva linear | 8 partículas `.cm-dust` com deriva determinística | **V1** | Parâmetros de coordenadas e diâmetros declarados em tuplas locais em cada script. |
| **Título Herói com Blur (T10)** | "Chave" (152 px, stagger 0.04s, blur 14px) | "Minutagem" (76 px, stagger 0.032s, blur 10px) | **V2** | Promovido formalmente na Fase 5.4 após isolamento em módulo compartilhado (`titulo_heroi.py`/`titulo_heroi.css`), 16 testes unitários e dois MP4s aprovados. |

**Diretriz Arquitetural:** A existência de soluções semelhantes nas duas cenas não comprova, por si só, reutilização de componentes. A técnica **T10** constitui o primeiro componente do projeto a cumprir todos os requisitos para promoção formal a **V2** (criação de módulo compartilhado independente, testes unitários automatizados, validação de build/lint, renderização convencional em dois contextos distintos e aprovação visual expressa do usuário). Os demais candidatos (T02, T03, T04, T18, C01–C16) permanecem em **V1**.

### 5.1 Registro da Homologação da Técnica T10 como V2 (Fase 5.4 — 2026-11-04)

- **Identificador canônico**: T10 — Título herói por letra
- **Status de maturidade**: **V2 (Reutilizável)** — Aprovado expressamente pelo usuário após validação audiovisual completa.

#### Componente compartilhado
- **Localização**: `fase5_experimento_t10/shared/`
- **Arquivos e Hashes SHA-256**:
  - Python: `titulo_heroi.py` (`E79205B8B6BE4D7C9D3B868072403D91407FAFCD9AB24293E64E098AD333669C`)
  - CSS: `titulo_heroi.css` (`FE926A6CF0329A900AE99B43ED455BEC0D1DDBCD0ED8D02BBE348EFD2B9E86B2`)
  - Testes: `test_titulo_heroi.py` (`2DC5A181D0DB3C766B5D922A562EC32B020BEF2BA40EA91121E7BDE95361B06C`)
- **Suíte de testes automatizados**: 16 testes unitários cobrindo normalização NFC, acentuação em português, escape HTML, preservação de quebras de linha e espaços, validação defensiva de IDs, parâmetros numéricos finitos, easing GSAP, correspondência ID/seletor e determinismo. Resultado: **16 testes aprovados, zero falhas, zero erros**.

#### Evidências nos dois contextos 16:9 testados
1. **Primeiro contexto — Virada de Chave**:
   - Workspace: `fase5_experimento_t10/workspace_teste_virada/`
   - Render convencional: `_render_teste/virada_teste_t10.mp4`
   - SHA-256: `5C7256313722E9ACC770709EACBA7342C35056975725E131D87D3C725658CBB6`
   - Características preservadas: Texto "Chave", tipografia 152 px, entrada em 25,94 s, duration 0,38 s, stagger 0,04 s, deslocamento Y 44 px, blur progressivo 14 px, easing `power3.out`.
2. **Segundo contexto — Alta Minutagem**:
   - Workspace: `fase5_experimento_t10/workspace_teste_minutagem/`
   - Render convencional: `_render_teste/minutagem_teste_t10.mp4`
   - SHA-256: `C7ADF06A510395AC78E948E83D4F226DE2ADCD7B5A447E51E1B8BC9AA1DB5499`
   - Características preservadas: Texto "Minutagem", tipografia 76 px, entrada em 26,90 s, duration 0,36 s, stagger 0,032 s, deslocamento Y 32 px, blur progressivo 10 px, easing `power3.out`.

#### Características arquiteturais consolidadas
- Módulo Python isolado e compartilhado (`gerar_html_titulo`, `animar_titulo`).
- CSS estrutural compartilhado restrito a `.th-w` e `.th-l`.
- Parâmetros configuráveis por cena sem acoplamento de estilo visual cênico (posicionamento, tipografia e cores continuam declarados na cena).
- Seletores GSAP escopados por instância (`#{clip_id}-{elemento_id} .th-l`).
- Testes automatizados persistentes executáveis independentemente de browsers ou do HyperFrames.
- Validação em dois contextos 16:9 independentes sem regressão visual.
- Aprovação visual expressa dos renders convencionais em MP4 pelo usuário.

#### Limitações que permanecem expressamente documentadas
- **Escopo de formato**: Validação realizada estritamente nas duas cenas em formato 16:9. O comportamento no formato **9:16 (Shorts/Reels/TikTok)** ainda não foi testado nem validado.
- **Animação de saída**: O componente T10 cobre exclusivamente a animação de entrada (in-animation). A animação de saída (exit/outro) permanece sob responsabilidade da timeline da cena hospedeira.
- **Localização dos artefatos**: O componente reside atualmente no diretório experimental da Fase 5 (`fase5_experimento_t10/shared/`). Sua futura transposição para uma biblioteca de componentes de produção dependerá de uma etapa arquitetural dedicada.
- **Suporte a caracteres**: A normalização Unicode NFC garante a integridade de acentos da língua portuguesa (`ç`, `ã`, `é`, etc.), mas não constitui garantia de compatibilidade universal com todos os grafemas complexos ou emojis do padrão Unicode.

---

## 6. Recursos da biblioteca existentes (citados em `PREFERENCIAS.md`)

Evidência: **[MARCA]** apenas. Maturidade: **NC** (código não revisado formalmente nesta documentação).

| Recurso | Uso | Formato |
|---|---|---|
| `cn.card_flutuante(lado)` | sidecar lateral | 16:9 |
| `cn.barra_progresso(pct, meta)` | barra com gradiente da marca | 16:9 |
| `cn.stepper(etapas, ativa)` | etapas numeradas | 16:9 |
| `cn.pip_stage(de, ate, midia)` | PiP do apresentador | 16:9 |
| `cn.transicao_marca(t)` | transição diagonal com whoosh | 16:9 |
| `cn.broll(..., card=False)` | B-roll em tela cheia com Ken Burns | 16:9 |
| `bate()` | micro-zoom de ênfase | 16:9 |
| Split stage + legendas dinâmicas | cortes verticais | 9:16 |
| Entrada/saída item por item (stagger ease-out) | cards de Shorts | 9:16 |

---

## 7. Limitações de reutilização e isolamento

### 7.1 Acoplamento temporal
- Na **Virada de Chave**, a maioria dos tempos é absoluta (segundos fixos da timeline geral).
- Na **Alta Minutagem**, foi introduzido o cálculo por offsets locais relativos a `de` escalados pela duração da janela. No entanto, a sincronia fina ainda exige casamento direto com a velocidade da fala do apresentador.

### 7.2 Isolamento de namespace e teste de múltiplas instâncias
- A **Virada de Chave** utiliza seletores com prefixo `.vc-*` e alguns IDs fixos de gradiente (`vcG1`, `vcG2`), inviabilizando múltiplas instâncias simultâneas.
- A **Alta Minutagem** avançou arquiteturalmente ao utilizar classes de cena `.cm-*`, IDs de tags e gradientes prefixados dinamicamente por `{clip_id}-` e seletores GSAP restritos ao escopo `#{clip_id}`.
- **Limitação Crítica:** O suporte da Alta Minutagem a múltiplas instâncias simultâneas na mesma composição **permanece como hipótese arquitetural não testada empiricamente**, visto que no build do episódio foi instanciada apenas uma cena (`nid("cm")`).

---

## 8. Arquivos de referência exatos (cópias identificadas)

| Arquivo | Caminho completo | Papel e Observações |
|---|---|---|
| `cena_virada.py` | `projetos/dr-gestao/episodios/teste-piloto-parte-02/workspace_experimental_virada/cena_virada.py` | Fonte da cena Virada de Chave (referência 1) |
| `virada.css` | `projetos/dr-gestao/episodios/teste-piloto-parte-02/workspace_experimental_virada/virada.css` | Estilos locais da Virada de Chave |
| `cena_minutagem.py` | `projetos/dr-gestao/episodios/teste-piloto-parte-02/workspace_experimental_minutagem/cena_minutagem.py` | Fonte da cena Alta Minutagem (referência 2) |
| `minutagem.css` | `projetos/dr-gestao/episodios/teste-piloto-parte-02/workspace_experimental_minutagem/minutagem.css` | Estilos locais da Alta Minutagem |
| `build.py` (virada) | `projetos/dr-gestao/episodios/teste-piloto-parte-02/workspace_experimental_virada/build.py` | Script de build com montagem da Virada de Chave |
| `build.py` (minutagem) | `projetos/dr-gestao/episodios/teste-piloto-parte-02/workspace_experimental_minutagem/build.py` | Script de build com montagem da Alta Minutagem |
| `cenas.py` **(referência)** | `projetos/dr-gestao/episodios/teste-piloto-parte-02/workspace_experimental_virada/cenas.py` | SHA-256 `6CA271017B234C332F3F3863021B694885C3C5908EDFDDD19AE941A903E0C14A`; única com `entrada_de` |

---

## 9. Backlog (melhorias futuras; nada aqui é decisão aprovada)

| ID | Ideia | Maturidade |
|---|---|---|
| P01 | Biblioteca de metáforas físicas para outros conceitos de gestão | V0 |
| P02 | Versão 9:16 recomposta das cenas de tela cheia | V0 |
| P03 | Extração de componentes comuns (cards, poeira, pulsos) em pacote compartilhado | V0 |
| P04 | Teste empírico de múltiplas instâncias simultâneas na mesma timeline | V0 |
| P05 | Medição formal de dessincronia fala/ação (ms) e tolerância humana | V0 |
| P06 | Teste visual e validação empírica de legibilidade mobile em dispositivos reais | V0 |
| P07 | Vendor local do GSAP e empacotamento local de fontes Inter WOFF2 | V0 |
| P08 | Modelos de duração e easing padronizados para o canal | V0 |
| P09 | Orçamento de renderização e análise de custo de filtros CSS complexos | V0 |
| P10 | Paridade entre render convencional e render rápido do Vortex | V0 |
| P11 | Regras de convivência com o apresentador em tela cheia | V0 |
| P12 | Medição formal de loudness integrado (LUFS) e True Peak e definição das metas de áudio | V0 |
