# Design System de Motion — Dr. Gestão

Versão: 0.3 (revisado na Fase 4C.1; consolida os aprendizados das cenas Virada de Chave e Alta Minutagem).  
Escopo: motion graphics 16:9 e (futuramente) 9:16 do canal Dr. Gestão.  
Independente de ferramenta: não pressupõe nenhum agente de IA, harness ou modelo.  
Backups anteriores: versões 0.1 e 0.2 arquivadas em locais seguros de histórico.

---

## 0. Como ler este documento

### 0.1 Convenção de caminhos

Todos os caminhos são relativos à raiz do repositório (`d:\Drifit\Editor`), com `/` como separador.  
Os caminhos completos estão na seção 16.  
Quando o texto cita nomes de arquivos sem pasta (ex.: `cena_virada.py` ou `cena_minutagem.py`), ele se refere às cópias dos workspaces experimentais correspondentes:
- `projetos/dr-gestao/episodios/teste-piloto-parte-02/workspace_experimental_virada/`
- `projetos/dr-gestao/episodios/teste-piloto-parte-02/workspace_experimental_minutagem/`  
O arquivo `cenas.py` existe em múltiplas versões; ele é citado sempre com caminho completo.

### 0.2 Dimensão 1 — Evidência da informação

Todo enunciado relevante recebe **um** selo que diz *de onde vem a informação*. O selo atesta a origem do dado, não sua maturidade de reutilização.

| Selo | Significado |
|---|---|
| **[CÓDIGO]** | Confirmado diretamente em código-fonte ou arquivo gerado (`cena_virada.py`, `cena_minutagem.py`, `build.py`, `index.html`, etc.). |
| **[RELATÓRIO]** | Confirmado em relatório formal de execução ou medição do render (`RELATORIO_PASSO3A/3B.md`, `README_EXPERIMENTO.md`). |
| **[MARCA]** | Preferência oficial registrada em `projetos/dr-gestao/branding/PREFERENCIAS.md`. |
| **[USUÁRIO]** | Decisão ou aprovação explícita do usuário, registrada na seção 15. |
| **[INTERPRETAÇÃO]** | Leitura analítica sobre o que o código/relatório demonstra. Não é fato comprovado. |
| **[PROPOSTA]** | Recomendação técnica nova. Não validada; não é decisão aprovada. |
| **[NÃO VALIDADO]** | Lacuna conhecida; nenhuma evidência disponível no momento. |

### 0.3 Dimensão 2 — Maturidade do componente (usada em `CATALOGO_MOTIONS.md`)

A maturidade é independente da evidência. Critérios canônicos:

| Nível | Significado |
|---|---|
| **V0** | Proposto: ideia sem implementação conhecida. |
| **V1** | Implementado e aprovado em **um único contexto** (cena de referência), acoplado a ela. |
| **V2** | Isolado da cena, parametrizável e testado em **dois ou mais contextos** (outra cena ou outro formato). |
| **NC** | Não classificado: existe segundo outra fonte, mas não foi revisado nesta documentação. |

**Estado atual na v0.3:** Todos os recursos implementados permanecem em **V1**. Nenhuma técnica foi promovida a V2, pois não há biblioteca compartilhada homologada.

### 0.4 Base empírica consolidada

O Motion System fundamenta-se nas evidências técnicas e aprovações visuais de duas referências experimentais aprovadas:

1. **Virada de Chave (Referência 1) [USUÁRIO]:**
   - Janela de execução da cena: **22,50s a 27,70s** (duração: 5,20s).
   - Formato: 16:9 (1920×1080), sem apresentador.
   - SHA-256 do MP4 renderizado: `795E2DB97F1F413A414A49E16F78E605B02BF49344DBA61C2E71E256137A716A`.
   - Detalhamento: `REFERENCIA_APROVADA_VIRADA_CHAVE.md`.
2. **Alta Minutagem (Referência 2) [USUÁRIO]:**
   - Janela de execução da cena: **23,28s a 30,65s** (duração: 7,37s).
   - Janela do render convencional de recorte: **22,50s a 31,50s** (duração: 9,00s).
   - Formato: 16:9 (1920×1080), sem apresentador.
   - SHA-256 do MP4 verificado fisicamente: `49FC299ECE61E56CA4DF9184A7E26A3D2CE81DEC5F92B56F1F970CD834FDB16B`.
   - Detalhamento: `REFERENCIA_APROVADA_ALTA_MINUTAGEM.md`.

*Distinção Obrigatória:* A janela de execução da cena marca o tempo útil em que a composição atua na timeline do vídeo. A janela do render MP4 refere-se ao intervalo do arquivo de vídeo exportado para homologação (que inclui margens de segurança).

As duas cenas são **referências de qualidade**, não templates obrigatórios. Suas características específicas não constituem regras rígidas para todas as produções futuras.

---

## 1. Linguagem visual e princípios demonstrados

Nas duas cenas aprovadas, foram consolidados os seguintes princípios visuais:

- **Composição 2.5D Vetorial [CÓDIGO]:** Construção de profundidade espacial sem uso de engines 3D pesadas, combinando perspectiva CSS, sombras projetadas, extrusões concêntricas e planos sobrepostos.
- **Profundidade por Camadas [CÓDIGO]:** Estruturação clara em três planos: fundo/grade em perspectiva, mundo vetorial sob ação de câmera e interface editorial (UI) estática e nítida.
- **Câmera 2D como Recurso Narrativo [CÓDIGO]:** A movimentação da câmera (`scale`, `x`, `y`) atua estritamente para conduzir a atenção do espectador: aproximação nos momentos de tensão argumentativa, recuo na revelação e estabilização completa antes de perguntas de fechamento ("entendeu?").
- **Tipografia Cinética Hierárquica [CÓDIGO]:** Textos revelados em sincronia deliberada com os ápices da fala, utilizando desfasamento (`stagger`) e transição de desfoque para nitidez na palavra de maior ênfase.
- **Trilhos e Condutos SVG [CÓDIGO]:** Uso de vetores dinâmicos com `pathLength="1"` e manipulação de `strokeDashoffset` para ilustrar fluxos contínuos e conexões.
- **Metáforas Visuais Integradas à Fala [INTERPRETAÇÃO]:**
  - *Metáfora Comercial (Virada de Chave):* Bifurcação de trilhos com alavanca mecânica para expressar transformação de rota comercial e múltiplos canais de venda.
  - *Metáfora Industrial (Alta Minutagem):* Linha de produção modular, cronômetro de retenção e válvula de afunilamento para ilustrar retenção operacional interna e dificuldade de escoamento para o mercado.
- **Natureza Conceitual das Representações [CÓDIGO]:** Os elementos industriais da Alta Minutagem foram construídos como representações conceituais e pedagógicas, livres de dados estatísticos fictícios, percentuais infundados ou métricas reais de fábrica.

*Diretriz de Design:* Esses princípios servem de orientação para novos experimentos, mas não transformam as implementações atuais em componentes universais V2.

---

## 2. Identidade visual e paleta de cores

**Convenção:** O **código HEX é o identificador canônico** de cada cor.

### 2.1 Cores oficiais da marca — **[MARCA]** (`PREFERENCIAS.md`)

| HEX | Nome em `PREFERENCIAS.md` | Uso Institucional Oficial |
|---|---|---|
| `#004aad` | Azul Dr. Gestão | Destaque principal da marca e identidade do canal. |
| `#8e7de5` | Lilás / Roxo | Cor secundária e de acentos; ícones animados sempre em lilás. |
| `#2f97d4` | Azul Ciano | Realces, detalhes e iluminação de fluxo. |
| `#004aad` → `#8e7de5` → `#2f97d4` | Gradiente oficial | Barras de progresso e elementos centrais da marca. |
| `rgba(18,24,42,.88)` → `rgba(8,12,22,.94)` | Superfície oficial | Cards de vidro escuro translúcido (borda `rgba(142,125,229,.38)`). |

### 2.2 Cores funcionais e de experimentação cênica — **[CÓDIGO]**

As duas cenas aprovadas adotaram tons adicionais para finalidades estritamente cênicas e semânticas:

- **Na Virada de Chave:**
  - `#22d3ee` (ciano experimental): utilizado no final do gradiente de trilho, pacotes e número "4".
  - `#a78bfa` (lilás experimental): leque fantasma de possibilidades.
  - `#22c55e` / `#86efac` (verde): selo de status "ROTA ATIVA".
  - *Nota:* `#004aad` não foi utilizado na Virada de Chave.
- **Na Alta Minutagem:**
  - `#004aad`: utilizado nos gradientes SVG do conduto e cronômetro.
  - `#f59e0b` (âmbar funcional): funil de estrangulamento mecânico, aviso de atenção e selo de status "ESCOAMENTO LIMITADO".
  - `#ef4444` (vermelho funcional): parede convergente da válvula e etiqueta "VAZÃO RESTRITA PELA MINUTAGEM".
  - `#cbd5e1`, `#94a3b8`, `#e2e8f0`: tons neutros editoriais de texto técnico.

**Restrição de Marca [PROPOSTA]:** Tons como âmbar (`#f59e0b`), vermelho (`#ef4444`) e ciano experimental (`#22d3ee`) atuam **exclusivamente como cores funcionais de estado cênico** (alerta, estrangulamento, fluxo). **Não são e não devem ser registrados como novas cores oficiais da marca Dr. Gestão.**

---

## 3. Arquitetura, isolamento e limitações

A evolução técnica entre os dois experimentos estabeleceu uma progressão arquitetural clara:

1. **Virada de Chave (Implementação Monolítica) [CÓDIGO]:**
   - Dependência estrita de tempos absolutos da timeline geral do episódio.
   - Classes com prefixo temático `.vc-*`.
   - Seletores e IDs de gradiente fixos (`vcG1`, `vcG2`), impedindo mais de uma instância na mesma composição.
2. **Alta Minutagem (Parametrização por clip_id) [CÓDIGO]:**
   - Sincronização calculada a partir de offsets locais relativos ao início da cena (`de`), escalados pela duração (`ate - de`).
   - Namespace temático nas classes CSS (`.cm-*`).
   - Identificadores HTML e gradientes SVG dinamicamente prefixados por `{clip_id}-` (ex.: `id="{clip_id}-chrono"`).
   - Comandos GSAP estritamente escopados pela raiz do clip (`#{clip_id}`).
3. **Limitação Crítica de Concorrência [NÃO VALIDADO]:**
   - O suporte da Alta Minutagem a múltiplas instâncias simultâneas é um padrão de projeto promissor, mas **permanece não testado empiricamente**. No build do episódio, apenas uma instância foi executada. Conflitos de GPU em filtros SVG idênticos ou sobreposição de z-index precisam de validação em teste futuro.
   - A Alta Minutagem é uma referência de qualidade arquitetural, **não uma biblioteca compartilhada homologada**.

---

## 4. Tipografia, escala e protocolo mobile

### 4.1 Medidas tipográficas comprovadas em código — **[CÓDIGO]**

No canvas desktop 1920×1080:
- **Virada de Chave:** Título herói `.vc-t2` ("Chave") = **152 px**; título secundário `.vc-t1` = 56 px; número `.vc-count__num` = 62 px; rótulo `.vc-count__lbl` = 22 px; nós de plataforma = 21 px; rótulos de apoio técnicos = 12–13 px.
- **Alta Minutagem:** Kicker `.cm-t1` ("Alta") = **34 px**; título principal `.cm-t2` ("Minutagem") = **76 px**; subtítulo editorial `.cm-tsub` = 20 px; assinatura de rodapé `.cm-sig` = 20 px; títulos das estações `.cm-mod__title` = 30 px; subtítulos de apoio = 14–15 px; tags e badges = 11–13 px.

*Observação:* Não existe texto de 152 px na Alta Minutagem. A disparidade de escala foi uma decisão cênica específica de cada composição.

### 4.2 Fatores matemáticos de redução proporcional

Ao exibir composições digitais em telas de smartphones (larguras físicas de 360 px e 390 px), ocorrem reduções geométricas proporcionais:

**Vídeo Horizontal 16:9 (Canvas 1920×1080):**
- Exibição em tela de 360 px: fator **0,1875** ($\frac{360}{1920}$)
- Exibição em tela de 390 px: fator **0,203125** ($\frac{390}{1920}$)

*Escala aparente resultante:*
- 152 px (Virada): $152 \times 0{,}1875 = \mathbf{28{,}5\text{ px}}$ (em 360 px) / $\mathbf{30{,}87\text{ px}}$ (em 390 px)
- 76 px (Minutagem): $76 \times 0{,}1875 = \mathbf{14{,}25\text{ px}}$ (em 360 px) / $\mathbf{15{,}44\text{ px}}$ (em 390 px)
- 34 px (Minutagem): $34 \times 0{,}1875 = \mathbf{6{,}375\text{ px}}$ (em 360 px) / $\mathbf{6{,}91\text{ px}}$ (em 390 px)
- 11–13 px (Rótulos técnicos): $11 \times 0{,}1875 \approx \mathbf{2{,}06\text{ px}}$ / $13 \times 0{,}1875 \approx \mathbf{2{,}44\text{ px}}$

**Vídeo Vertical 9:16 Nativo (Canvas 1080×1920):**
- Exibição em tela de 360 px: fator **0,3333** ($\frac{360}{1080}$)
- Exibição em tela de 390 px: fator **0,3611** ($\frac{390}{1080}$)

*Escala aparente em 9:16 nativo:*
- O vídeo vertical em smartphone também sofre redução (aproximadamente 3×). Textos de 76 px no canvas vertical resultam em $\approx 25{,}3\text{ px}$ aparentes; textos de 20 px resultam em $\approx 6{,}7\text{ px}$ aparentes.

### 4.3 Diretrizes metodológicas para mobile

- **Redução Geométrica vs. Legibilidade:** Os fatores acima são cálculos matemáticos exatos de escala, **não garantias de legibilidade visual**.
- **Sem Limites Mínimos Universais:** É vedado estabelecer tamanhos mínimos obrigatórios no Design System sem a realização de testes empíricos com usuários em dispositivos reais.
- **Distinção de Contextos de Exibição:**
  1. *Feed Vertical (16:9 embutido):* Textos de apoio abaixo de 20 px no canvas 1920 perdem legibilidade e assumem função puramente decorativa/textural.
  2. *Tela Cheia Horizontal (Smartphone rotacionado):* Aproveita a largura quase total do aparelho (fator $\approx 0{,}45$), tornando legíveis textos a partir de 16 px.
  3. *Cortes 9:16 Nativos:* Exigem recomposição específica (split stage), não sendo viável a transposição direta do layout horizontal.
- **Safe Zones:** As indicações de margens de safe zone para plataformas móveis (YouTube Shorts, Reels, TikTok) permanecem como pendência de homologação e **não devem ser fixadas como normas definitivas** sem validação visual cruzada em cada rede.

---

## 5. Profundidade, iluminação e câmera 2D

- **Extrusão 2.5D [CÓDIGO]:** Criada a partir de três vias SVG sobrepostas (sombra inferior, corpo em gradiente, aresta clara) complementadas por `drop-shadow`.
- **Iluminação e Luz Funcional [CÓDIGO]:** Halos radiais para destacar pontos de decisão e atenções visuais; pulsos luminosos com desfoque e gradiente para indicar matérias em trânsito; iluminação de acento em bordas.
- **Câmera 2D [CÓDIGO]:** Manipulação de `scale` (faixa 0,96 a 1,05), `x` e `y` em wrapper dedicado. Movimentos sincronizados aos blocos de raciocínio da fala, mantendo a camada de texto (UI) fora do wrapper para preservar estabilidade e nitidez.

---

## 6. Sincronização com a fala e sound design

- **Sincronia Fina [CÓDIGO]:** Ações visuais principais vinculadas aos ápices das palavras transcritas em `media/palavras_saida.json`. A regra observada consiste em: preparar o elemento visual antes, acionar o movimento mecânico no verbo de ação e completar a revelação do texto na palavra-chave.
- **Hold Estável Obrigatório [RELATÓRIO]:** Nos momentos de conclusão ou questionamento retórico (ex.: "entendeu?"), a composição deve suspender movimentações bruscas e estabilizar câmera e elementos por pelo menos 0,3s a 0,5s antes do encerramento.
- **Sound Design Integrado [CÓDIGO]:** Os efeitos sonoros nativos (`whoosh_curto`, `clique2`, `impacto_grave`, `swish`, `clique`) acompanham exclusivamente os marcos visuais fundamentais, sem pontuar microanimações decorativas.

---

## 7. Pendências técnicas explícitas e limitações

As seguintes pendências técnicas foram confirmadas na auditoria e permanecem em aberto:

1. **Empacotamento Local de Fontes Inter [RELATÓRIO]:**
   - O arquivo `index.html` declara `@font-face` referenciando `fonts/inter-*.woff2`. A ausência física desses arquivos na pasta local do workspace gera requisições `404 Not Found` no log do compilador HyperFrames. A decisão sobre a política de vendor local e distribuição de assets permanece pendente.
2. **Normalização de Áudio e Loudness Formal [RELATÓRIO]:**
   - *Virada de Chave:* volume médio −17,7 dB e pico −2,7 dB (medidos via `volumedetect` no Passo 3B).
   - *Alta Minutagem:* volume médio −17,3 dB e pico −3,8 dB foram valores informados no histórico de testes, porém a auditoria da Fase 4C.0 confirmou que **não há relatório autônomo persistido no workspace** atestando essa medição.
   - *Limitação:* Medições em dB via `volumedetect` representam volume médio RMS e pico amostral simples e **não equivalem a LUFS integrado**. LUFS integrado e True Peak ainda não foram medidos formalmente, e a meta de loudness e pico ainda não foi definida para o projeto.
3. **Versão e Avisos do HyperFrames [RELATÓRIO]:**
   - Os testes foram executados na CLI 0.9.5. O aviso estrutural `nested_structure_needs_subcomposition` emitido pelo compilador para clips em tela cheia permanece como limitação documentada, sem que seu impacto deva ser generalizado para versões futuras.

---

## 8. Registro de aprovação das referências

| Campo | Referência 1: Virada de Chave | Referência 2: Alta Minutagem |
|---|---|---|
| **Data de Aprovação** | 04/11/2026 | 04/11/2026 |
| **Responsável** | **[USUÁRIO]** do projeto | **[USUÁRIO]** do projeto |
| **Janela da Cena** | 22,50s a 27,70s (5,20s) | 23,28s a 30,65s (7,37s) |
| **Janela do Render** | 0,00s a 32,50s (piloto completo) | 22,50s a 31,50s (recorte de 9,00s) |
| **Arquivo MP4** | `workspace_experimental_virada/_experimento/renders_passo3b/virada_passo3b_convencional.mp4` | `workspace_experimental_minutagem/_experimento/renders_passo3b/alta_minutagem_convencional_2250_3150.mp4` |
| **SHA-256 Confirmado** | `795E2DB97F1F413A414A49E16F78E605B02BF49344DBA61C2E71E256137A716A` | `49FC299ECE61E56CA4DF9184A7E26A3D2CE81DEC5F92B56F1F970CD834FDB16B` |

*Limites Formais:* As aprovações cobrem a composição visual e o sincronismo das cenas renderizadas. Não constituem homologação técnica de componentes V2, nem validação de vertical 9:16 ou conformidade de áudio broadcast.

---

## 9. Fontes de referência documental (caminhos completos)

1. `projetos/dr-gestao/motion-system/REFERENCIA_APROVADA_VIRADA_CHAVE.md`
2. `projetos/dr-gestao/motion-system/REFERENCIA_APROVADA_ALTA_MINUTAGEM.md`
3. `projetos/dr-gestao/motion-system/CATALOGO_MOTIONS.md`
4. `projetos/dr-gestao/branding/PREFERENCIAS.md`
5. `projetos/dr-gestao/episodios/teste-piloto-parte-02/workspace_experimental_virada/cena_virada.py`
6. `projetos/dr-gestao/episodios/teste-piloto-parte-02/workspace_experimental_virada/virada.css`
7. `projetos/dr-gestao/episodios/teste-piloto-parte-02/workspace_experimental_virada/build.py`
8. `projetos/dr-gestao/episodios/teste-piloto-parte-02/workspace_experimental_minutagem/cena_minutagem.py`
9. `projetos/dr-gestao/episodios/teste-piloto-parte-02/workspace_experimental_minutagem/minutagem.css`
10. `projetos/dr-gestao/episodios/teste-piloto-parte-02/workspace_experimental_minutagem/build.py`
11. `projetos/dr-gestao/episodios/teste-piloto-parte-02/workspace_experimental_virada/_experimento/renders_passo3b/virada_passo3b_convencional.mp4`
12. `projetos/dr-gestao/episodios/teste-piloto-parte-02/workspace_experimental_minutagem/_experimento/renders_passo3b/alta_minutagem_convencional_2250_3150.mp4`
