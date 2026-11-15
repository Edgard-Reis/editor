# Referência Aprovada — "Alta Minutagem"

Versão: 0.3 (criada na Fase 4C.1).
Papel: **segunda referência de qualidade de motion** do Dr. Gestão. Não é template obrigatório.
Selos de evidência: ver `DESIGN_SYSTEM_MOTION_DR_GESTAO.md`, seção 0.2
([CÓDIGO], [RELATÓRIO], [MARCA], [USUÁRIO], [INTERPRETAÇÃO], [PROPOSTA], [NÃO VALIDADO]).
Os níveis de maturidade V0/V1/V2/NC pertencem ao `CATALOGO_MOTIONS.md` e **não** são usados aqui como evidência.

Convenção de caminhos: todos relativos à raiz do repositório (`d:\Drifit\Editor`), com `/` como separador.

---

## 1. Identificação e aprovação visual

| Campo | Valor |
|---|---|
| Data de Aprovação | 04/11/2026 |
| Fonte | **[USUÁRIO]** decisão registrada nas instruções da Fase 4C.0 / 4C.1 |
| Escopo Aprovado | **somente** a animação da cena "Alta Minutagem" (janela de execução: 23,28s a 30,65s do episódio Parte 02) |
| Janela do Arquivo Renderizado | 22,50s a 31,50s (render convencional de recorte de 9,00 segundos) |
| Arquivo MP4 de Referência | `projetos/dr-gestao/episodios/teste-piloto-parte-02/workspace_experimental_minutagem/_experimento/renders_passo3b/alta_minutagem_convencional_2250_3150.mp4` |
| SHA-256 Verificado Fisicamente | `49FC299ECE61E56CA4DF9184A7E26A3D2CE81DEC5F92B56F1F970CD834FDB16B` |

**Limites da aprovação visual [USUÁRIO]:**
- A aprovação visual cobre a cena **como renderizada**.
- Não cobre homologação de componentes isolados reutilizáveis (V2).
- Não valida uso em formato vertical 9:16.
- Não atesta conformidade formal de loudness integrado (LUFS) nem True Peak; meta de áudio ainda não estabelecida.
- A aprovação da composição cênica não transforma cada elemento gráfico ou técnica em padrão universal do canal.

---

## 2. Contexto narrativo e metáfora industrial

- **[CÓDIGO]** Trecho da fala correspondente (`build.py` e `cena_minutagem.py`):
  *"[E] quando vem os produtos que se trabalha, tem uma alta minutagem, que atrapalha demais as vendas, entendeu?"* (janela 23,28s a 30,65s).
- **[RELATÓRIO]** A expressão "atrapalha demais as vendas" foi auditada e confirmada no áudio original (WAV), corrigindo o erro da transcrição automática bruta ("que é pra palha de mais as vendas").
- **[CÓDIGO]** Metáfora cênica: **Linha Produtiva Industrial 2.5D com Fluxo de Saída Restrito**.
  - A produção percorre três etapas operacionais ilustrativas: **Preparação**, **Montagem** e **Acabamento**.
  - O produto consome tempo operacional elevado no ciclo interno (metáfora de "Alta Minutagem").
  - O escoamento para o mercado consumidor enfrenta um funil físico de estrangulamento ("Válvula de Vazão Restrita").
  - A saída comercial recebe fluxo afunilado e restrito, ilustrando o impacto direto no escoamento das vendas.
- **[CÓDIGO]** **Natureza estritamente conceitual:** Conforme ajustado no Passo 2.1, a cena não utiliza percentuais (como 32%, 64%, 94%), proporções de pacotes (ex.: 4 retidos de 6) ou escalas calibradas. Todos os medidores gráficos e etapas são representações conceituais idênticas e abstratas, sem afirmar que uma operação consome mais tempo que outra na realidade fabril.
- **[CÓDIGO]** Copy visual: "DR. GESTÃO · DIAGNÓSTICO OPERACIONAL", "Alta Minutagem", "Retenção de tempo operacional interno no ciclo da peça", "PERMANÊNCIA NO CICLO", "ESTREITAMENTO DE VAZÃO", "Fluxo de Saída / Escoamento para Vendas", "MINUTAGEM ELEVADA · FLUXO DE SAÍDA RESTRITO", "ESCOAMENTO LIMITADO".

---

## 3. Janela da cena vs. Janela do render de referência

É fundamental não confundir as duas janelas temporais:

1. **Janela de Execução da Cena na Timeline do Episódio [CÓDIGO]:**
   - Início (`de`): **23,28s** (em "quando vem").
   - Fim (`ate`): **30,65s** (fade-out completo antes de "Então", que começa em 30,82s).
   - Duração da cena: **7,37s**.
2. **Janela de Recorte do Render de Referência MP4 [RELATÓRIO]:**
   - Início do render: **22,50s**.
   - Fim do render: **31,50s**.
   - Duração total do vídeo gerado: **9,00s** (270 quadros a 30 fps).
   - O arquivo MP4 inclui uma margem anterior e posterior de segurança para avaliação contextual da entrada e saída da cena.

---

## 4. Descrição da composição visual

A composição industrial é estruturada em camadas 2.5D no canvas 1920×1080:

1. **Plano de Fundo e Piso em Perspectiva [CÓDIGO]:**
   - Fundo radial profundo em três paradas: `#0e1628` → `#080c18` → `#03050a`.
   - Piso em perspectiva CSS (`perspective(1050px) rotateX(62deg)`) com grade de 96×96 px e máscara elíptica de desvanecimento radial.
   - Vinheta periférica suave para concentração visual no plano de ação.
   - 8 partículas de poeira industrial com posições determinísticas e deriva vertical contínua.
2. **Mundo 2.5D (sob ação de Câmera 2D) [CÓDIGO]:**
   - **Conduto SVG Extrudado:** Conectores tubulares amplos conectando a entrada às três estações produtivas e conduzindo ao ponto de estrangulamento.
   - **Três Estações Operacionais (Cards 2.5D):** Módulos em `x=272` (Preparação), `x=652` (Montagem) e `x=1032` (Acabamento) na linha vertical `y=642`, contendo ícone vetorial, tag "ETAPA ILUSTRATIVA", subtítulo funcional e medidor de fluxo interno idêntico.
   - **Cronômetro Vetorial 2.5D:** Localizado acima do fluxo central (`y≈440`), com anel circular em gradiente, ponteiro indicador e etiqueta "PERMANÊNCIA NO CICLO", simbolizando a minutagem elevada acumulada.
   - **Válvula de Afunilamento Mecânico:** Localizada em `x=1368, y=642`, composta por alojamento industrial, halo de atenção e mandíbulas que se aproximam fisicamente para estreitar o conduto de passagem.
   - **Módulo de Saída Comercial:** Card receptor em `x=1664, y=642` com badge "SAÍDA COMERCIAL", título "Fluxo de Saída" e tarja de advertência "VAZÃO RESTRITA PELA MINUTAGEM".
   - **Pulsos Luminosos Contínuos:** 5 pulsos luminescentes (`.cm-pulse`) que percorrem a linha de montagem e sofrem afilamento visual ao atravessar o conduto estreitado.
3. **Camada Editorial de Interface (UI) [CÓDIGO]:**
   - Kicker editorial superior com traço horizontal e texto "DR. GESTÃO · DIAGNÓSTICO OPERACIONAL".
   - Bloco de título: Kicker "Alta" (34 px) e título herói cinético "Minutagem" (76 px) com revelação letra por letra.
   - Subtítulo editorial explicativo: "Retenção de tempo operacional interno no ciclo da peça" (20 px).
   - Rodapé com separador e barra de diagnóstico: assinatura "MINUTAGEM ELEVADA · FLUXO DE SAÍDA RESTRITO" (20 px) e selo de status âmbar "ESCOAMENTO LIMITADO" (13 px).

---

## 5. Sequência temporal da cena

A sincronização temporal da cena é ancorada aos marcos auditados da fala:

| Offset Local (s) | Timestamp Global (s) | Fala / Marco Auditado | Eventos Visuais [CÓDIGO] |
|---|---|---|---|
| **0,00s** | 23,28s | "[E] quando vem os..." | Fade-in do clip (0,24s); piso surge (0,22 → 1) e câmera acomoda (`scale 1.04 → 1.0`); poeira inicia deriva. SFX `whoosh_curto`. |
| **0,72s** | 24,00s | Estação Preparação | Traçado do conector inicial; card "Preparação" surge com overshoot (`back.out`); traçado do ícone e medidor. SFX `clique2`. |
| **1,66s** | 24,94s | "...produtos que se..." | Traçado do conector intermediário 1; card "Montagem" surge com overshoot; cronômetro vetorial inicia rotação e arco. SFX `clique2`. |
| **2,46s** | 25,74s | "...trabalha," | Traçado do conector intermediário 2; card "Acabamento" surge com overshoot; medidor operacional. SFX `clique2`. |
| **3,32s** | 26,60s | "...tem uma alta..." | Entrada da palavra "Alta" (34 px); leve aproximação de câmera (`scale 1.024`). |
| **3,62s** | 26,90s | "...minutagem," | Título "Minutagem" (76 px) revela letra a letra com `stagger 0.032` e blur decrescente; subtítulo editorial entra. SFX `impacto_grave`. |
| **4,88s** | 28,16s | "...que atrapalha..." | Conector atinge a válvula; caixa de estrangulamento surge; mandíbulas mecânicas aproximam-se estreitando visualmente o conduto. SFX `swish`. |
| **5,44s** | 28,72s | "...demais..." | Conduto estreitado e etiqueta "ESTREITAMENTO DE VAZÃO"; entrada da linha separadora e assinatura de rodapé. |
| **5,92s** | 29,20s | "...as vendas," | Card "Fluxo de Saída" entra em `x=1664`; selo "ESCOAMENTO LIMITADO" assenta; câmera acomoda (`scale 0.994`). SFX `clique`. |
| **6,72s** | 30,00s | "entendeu?" | **Hold estável integral:** câmera perfeitamente estática, sem movimentos ou entradas bruscas, permitindo absorção do diagnóstico completo. |
| **7,02s** | 30,30s | Pausa pré-"Então" | Início do fade-out suave da composição (duração 0,35s). |
| **7,37s** | 30,65s | Encerramento | Opacidade atinge zero; liberação completa da tela antes da fala "Então" em 30,82s. |

---

## 6. Tipografia e cores utilizadas

### 6.1 Tipografia — **[CÓDIGO]** (`minutagem.css`, canvas 1920×1080)
A cena herda `font-family: "Inter", sans-serif` do layout raiz:

| Classe / Elemento | Texto Aplicado | Tamanho / Peso | Cor Aplicada |
|---|---|---|---|
| `.cm-ktxt` | DR. GESTÃO · DIAGNÓSTICO OPERACIONAL | 13 px / 700 / tracking .32em | `rgba(203, 213, 225, 0.70)` |
| `.cm-t1` | Alta | 34 px / 600 / lh 1.0 | `#cbd5e1` |
| `.cm-t2` | Minutagem | 76 px / 800 / tracking -.035em / lh .92 | `#ffffff` |
| `.cm-tsub` | Retenção de tempo operacional interno... | 20 px / 500 / lh 1.35 | `#94a3b8` |
| `.cm-mod__tag` | ETAPA ILUSTRATIVA | 11 px / 700 / tracking .20em | `#2f97d4` |
| `.cm-mod__title` | Preparação / Montagem / Acabamento | 30 px / 700 / lh 1.05 | `#ffffff` |
| `.cm-mod__sub` | Subtítulos das estações | 14 px / 400 | `#94a3b8` |
| `.cm-mod__mlbl` | FLUXO INTERNO | 11 px / 600 / tracking .16em | `rgba(203, 213, 225, 0.65)` |
| `.cm-chrono__lbl` | PERMANÊNCIA NO CICLO | 12 px / 700 / tracking .18em | `rgba(203, 213, 225, 0.75)` |
| `.cm-choke__lbl` | ESTREITAMENTO DE VAZÃO | 12 px / 700 / tracking .18em | `#f59e0b` |
| `.cm-out__title` | Fluxo de Saída | 28 px / 700 / lh 1.05 | `#ffffff` |
| `.cm-out__sub` | Escoamento para Vendas | 15 px / 400 | `#cbd5e1` |
| `.cm-out__restriction` | VAZÃO RESTRITA PELA MINUTAGEM | 12 px / 700 / tracking .18em | `#ef4444` |
| `.cm-sig` | MINUTAGEM ELEVADA · FLUXO DE SAÍDA RESTRITO | 20 px / 700 / tracking .22em | `#e2e8f0` |
| `.cm-status` | ESCOAMENTO LIMITADO | 13 px / 700 / tracking .16em | `#f59e0b` |

### 6.2 Paleta de Cores — **[CÓDIGO]** (`minutagem.css`)
- **Cores Oficiais da Marca [MARCA]:**
  - Azul Institucional: `#004aad` (presente nos gradientes SVG `cmGFlow` e `cmGChrono`).
  - Azul Ciano: `#2f97d4` (presente em gradientes de trilho, partículas de poeira e badges).
  - Roxo / Lilás: `#8e7de5` (presente no gradiente do conduto e acentos luminosos).
- **Cores Funcionais e Experimentais de Cena [CÓDIGO]:**
  - Âmbar (`#f59e0b`): Utilizado no funil de estreitamento, rótulo de atenção e selo de status de escoamento limitado.
  - Vermelho (`#ef4444`): Utilizado na parede convergente do afunilamento e na etiqueta de restrição severa de vazão comercial.
  - *Essas cores atendem à semântica de estrangulamento da cena e não constituem expansão da paleta institucional da marca.*

---

## 7. Elementos SVG e animações GSAP

- **Conduto Tubular Extrudado [CÓDIGO]:** Traçado em três vias concêntricas com `stroke-dasharray: 1` e interpolação de `strokeDashoffset` de 1 para 0.
- **Funil de Afunilamento em Curvas Bézier [CÓDIGO]:** Paredes superior e inferior descritas por curvas cúbicas (`C 1272 y_wide, 1310 y_slim, ...`) que convergem visualmente de 56 px de largura total para 10 px na passagem da válvula.
- **Pulsos Luminosos Conduzidos [CÓDIGO]:** 5 elementos com gradiente radial e desfasamento temporal que percorrem a linha até a válvula e sofrem redução de escala (`scaleX: 0.52`, `scaleY: 0.34`) e atenuação de opacidade ao adentrar o trecho restrito de saída.
- **Camadas e Contexto de Empilhamento [CÓDIGO]:** O container SVG do palco possui `z-index: 1` e `pointer-events: none`. Os cards operacionais possuem `z-index: 10`, garantindo que os pulsos luminosos transitem visualmente por trás dos blocos opacos de texto, aparecendo apenas nos vãos entre os módulos.

---

## 8. Sound design (comprovado em código)

Em [cena_minutagem.py](file:///d:/Drifit/Editor/projetos/dr-gestao/episodios/teste-piloto-parte-02/workspace_experimental_minutagem/cena_minutagem.py#L490-L510), a função `montar_minutagem` registra 7 eventos sonoros discretos via kit nativo:

| Identificador do Evento | Efeito Sonoro | Timestamp de Disparo | Volume Relativo | Duração Nominal |
|---|---|---:|---:|---:|
| `{clip_id}_entrada` | `whoosh_curto` | `de + 0,04s` (23,32s) | 0.34 | — |
| `{clip_id}_etapa1` | `clique2` | `m["preparacao"]` (24,00s) | 0.30 | — |
| `{clip_id}_etapa2` | `clique2` | `m["produtos"]` (24,94s) | 0.32 | — |
| `{clip_id}_etapa3` | `clique2` | `m["trabalha"]` (25,74s) | 0.34 | — |
| `{clip_id}_minutagem` | `impacto_grave` | `m["minutagem"]` (26,90s) | 0.32 | 0.85s |
| `{clip_id}_restricao` | `swish` | `m["atrapalha"]` (28,16s) | 0.36 | — |
| `{clip_id}_assinatura` | `clique` | `m["vendas"]` (29,20s) | 0.30 | — |

*Nota:* Os volumes registrados são coeficientes relativos da timeline de áudio. LUFS integrado e True Peak ainda não foram medidos formalmente, a meta de loudness e pico ainda não foi definida para o projeto, e medições em `volumedetect` não equivalem a LUFS integrado.

---

## 9. Arquitetura e dependências

- **Parametrização por `clip_id` [CÓDIGO]:** A função `montar_minutagem(*, de, ate, clip_id, ...)` gera tags HTML, referências CSS e gradientes dinamicamente prefixados por `{clip_id}` (ex.: `id="{clip_id}-chrono"`).
- **Offsets Locais Relativos [CÓDIGO]:** Os instantes dos marcos da fala são calculados por offsets relativos a partir de `de`, escalados pela duração real da janela (`ate - de`).
- **Isolamento de Estilos [CÓDIGO]:** Todas as classes CSS utilizam o namespace temático `.cm-*`.
- **Dependências de Execução:** GSAP 3.14.2 (carregado via CDN em `index.html`), HyperFrames 0.9.5, Python 3.11+.

---

## 10. Resultado do build e lint

No Passo 3A / 3A.1 do workspace experimental:
- **Build:** `python -B build.py` executado com sucesso gerando `index.html` e `partes.json`.
- **Lint de Texto (`checa_texto.py`):** 0 erros.
- **Lint GSAP:** 0 erros de sintaxe. No Passo 3A.1, o desfasamento dos intervalos de fade-out dos pulsos eliminou as sobreposições de opacidade registradas no Passo 3A. O único aviso remanescente (`nested_structure_needs_subcomposition` para o clip `cm9`) é uma limitação arquitetural estrutural do compilador HyperFrames idêntica à observada na Virada de Chave.

---

## 11. Dados técnicos do arquivo MP4

Dados do arquivo renderizado no Passo 3B:
- **Caminho:** `projetos/dr-gestao/episodios/teste-piloto-parte-02/workspace_experimental_minutagem/_experimento/renders_passo3b/alta_minutagem_convencional_2250_3150.mp4`
- **Resolução:** 1920×1080 (16:9)
- **Taxa de Quadros:** 30 fps progressivo (270 frames exatos)
- **Duração do Arquivo:** 9,000 segundos (recorte temporal 22,50s a 31,50s)
- **Formato / Codecs:** MP4 (H.264 High / yuv420p), áudio AAC estéreo 48 kHz
- **SHA-256 Confirmado Fisicamente:** `49FC299ECE61E56CA4DF9184A7E26A3D2CE81DEC5F92B56F1F970CD834FDB16B`

---

## 12. Pendências e limitações conhecidas

1. **Natureza Conceitual:** Os cards e módulos não representam dados estatísticos, tempos cronometrados ou métricas reais de fábrica. São representações gráficas pedagógicas para ancorar a fala do apresentador.
2. **Formato 9:16 Não Validado:** Não foi produzido nem testado corte vertical para esta composição.
3. **Múltiplas Instâncias Não Testadas:** Embora o código utilize `clip_id`, a convivência de duas ou mais instâncias de `montar_minutagem` na mesma timeline do episódio ainda precisa de teste empírico formal.
4. **Fontes Inter WOFF2 Ausentes:** Durante o render, o compilador emitiu requisições 404 para `/fonts/inter-*.woff2`. O render prosseguiu com fallback de sistema; a resolução de empacotamento local de fontes permanece pendente.
5. **Medição de Loudness Integrado e True Peak:** Os dados de volume médio informados na fase experimental via `volumedetect` não equivalem a medição em LUFS integrado. LUFS integrado e True Peak ainda não foram medidos formalmente, e a meta de loudness e pico ainda não foi estabelecida para o projeto.
