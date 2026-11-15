# ENGENHARIA DO PIPELINE DE VÍDEO — VIDEO_PIPELINE
## Decupagem, Cortes Inteligentes, Motion Graphics, Composição e Renderização

**Data de Consolidação:** 08 de novembro de 2026  
**Documento Técnico de Referência:** Plano Mestre v0.2, PoC 2 Congelada e Auditoria Técnica  
**Natureza do Documento:** `[FATO VERIFICADO]` / `[DECISÃO]` / `[HIPÓTESE]` / `[PROPOSTA]` / `[PENDÊNCIA]`  
**Estado de Implementação:** `[EXPERIMENTAL]` / `[EM DESENVOLVIMENTO]` / `[PLANEJADO]`  

---

## 1. Especificações Técnicas das Fontes de Entrada `[FATO VERIFICADO]` `[IMPLEMENTADO]`

A auditoria via FFprobe dos arquivos brutos originais (`temp/sources_probe.json`) comprovou as características técnicas reais dos materiais gravados:

| Parâmetro de Mídia | Fonte 1 (`20260823_203211.mp4`) | Fonte 2 (`20260823_203326.mp4`) |
|---|---|---|
| **Duração do Contêiner** | 40,113678 s (~40 s) | **268,685300 s** (~4 min 28 s) |
| **Duração do Áudio (PCM)** | 40,085333 s (1.924.096 amostras) | **268,672000 s** (12.896.256 amostras) |
| **Resolução Nativa** | **3840×2160 (4K UHD)** | **3840×2160 (4K UHD)** |
| **Proporção de Tela (Aspect Ratio)** | 16:9 Widescreen | 16:9 Widescreen |
| **Codec de Vídeo** | HEVC / H.265 (Main Profile, `hvc1`) | HEVC / H.265 (Main Profile, `hvc1`) |
| **Taxa de Quadros (FPS)** | 60000/1001 (~**59,94 fps**) | 60000/1001 (~**59,94 fps**) |
| **Taxa de Bits (Bitrate)** | ~61,1 Mbps | ~61,2 Mbps |
| **Codec de Áudio** | AAC LC (2 canais estéreo, 48 kHz) | AAC LC (2 canais estéreo, 48 kHz) |
| **Dispositivo de Captura** | Samsung Android (tags: `com.android.version: 16`) | Samsung Android (tags: `com.android.version: 16`) |

> **Retificação Documental:** Registros preliminares legados mencionavam erroneamente resolução 1080×1920 a 30 fps. A medição instrumental comprova que a gravação bruta é 4K nativo (3840×2160) a 59,94 fps.
>
> **Nota sobre Durações:** A duração do contêiner MP4 da Parte 2 é 268,685300 s. Ao decodificar o fluxo de áudio AAC para PCM 16-bit a 48.000 Hz, obtêm-se exatamente 12.896.256 amostras, equivalendo a 268,672000 s. A diferença decorre de metadados de priming/encapsulamento do contêiner MP4. Ambas as durações são registradas com precisão e contextualizadas.

---

## 2. Decupagem e Diretrizes de Cortes Editoriais `[DECISÃO]` `[PROPOSTA]`

A política editorial do projeto rejeita expressamente "cortes cegos" baseados unicamente em limiares automáticos de silêncio de áudio (silence removal tradicional). A inteligência de corte é estruturada em diretrizes claras:

1. **Encurtamento de Pausas Longas `[PROPOSTA]` `[EXPERIMENTAL]` `[PENDENTE DE APROVAÇÃO]`:**
   - Proposta em teste: pausas respiratórias ou hesitações superiores a 450 ms são propostas para encurtamento para a faixa de 200–250 ms.
   - *Status de Homologação:* Trata-se de uma proposta experimental pendente de teste sistemático e escuta pelo usuário, não de uma regra definitiva ou universalmente implementada.
2. **Eliminação de Falsos Começos e Reformulações `[DECISÃO]` `[EXPERIMENTAL]`:**
   - Trechos em que o apresentador interrompe uma frase e reinicia a formulação (ex.: trecho em torno de ~00:35 na Parte 2) têm a primeira tentativa eliminada, mantendo o fluxo coeso.
3. **Presença Visual em Silêncios Expressivos `[DECISÃO]` `[PLANEJADO]`:**
   - Momentos em que o orador faz uma pausa deliberada para ênfase dramática, reflexão ou expressão facial não devem ser cortados, preservando a humanidade e o impacto da oratória.
4. **Alinhamento Temporal de Palavras `[FATO VERIFICADO]` `[IMPLEMENTADO]`:**
   - Todos os pontos de corte e ancoragem de elementos gráficos utilizam **alinhamento temporal de palavras** obtido via Whisper word-level timestamps (`palavras.json`).
   - *Correção Terminológica:* O alinhamento obtido é estritamente temporal no nível de palavras e segmentos, não constituindo alinhamento fonético (que exigiria modelos acústicos baseados em fonemas, como MFA - Montreal Forced Aligner).

---

## 3. Motion Graphics com Timing Controlado (Motion Library) `[DECISÃO]` `[EM DESENVOLVIMENTO]`

Os elementos visuais de apoio não são concebidos como slides estáticos amadores nem utilizam motores de física simulada. A abordagem oficial adota **motion intencional com curvas de aceleração e desaceleração (*easing*) e timing controlado via GSAP (GreenSock Animation Platform 3.14.2)**.

### Classificação e Status dos Componentes da Motion Library:

| Componente | Função Editorial | Status de Catalogação | Status de Implementação | Status de Homologação |
|---|---|---|---|---|
| **T10 — Card Herói / Conceito Principal** | Revelação tipográfica no terço superior/inferior para fixar credenciais e tema. | `[CATALOGADO]` | `[IMPLEMENTADO]` em PoC de teste (`poc_motion_library.py`) | `[NÃO HOMOLOGADO]` no pipeline integrado |
| **D30 — Destaque de Termo / Alerta Têxtil** | Cartela lateral para enfatizar conceitos fabris (*Alta Minutagem*, *Gargalo*, *Custo Minuto*). | `[CATALOGADO]` | `[IMPLEMENTADO]` em PoC de teste; testado em PoC 2 (`render_piloto.js`) | `[PENDENTE DE CORREÇÃO]` (falhas de posicionamento observadas na PoC 2) |
| **M20 — Cartela Métrica / Balanço Numérico** | Contador numérico progressivo animado para cifras financeiras (*R$ 300k a R$ 500k/mês*). | `[CATALOGADO]` | `[IMPLEMENTADO]` em PoC de teste; testado em PoC 2 | `[PENDENTE DE CORREÇÃO]` (necessita revisão de escala e temporalidade) |
| **C40 — Call-to-Action e Contato** | Fechamento visual dinâmico com direcionamento para canais de contato e redes sociais. | `[CATALOGADO]` | `[IMPLEMENTADO]` em PoC de teste | `[NÃO HOMOLOGADO]` no pipeline integrado |

> **Observação de Arquitetura:** Na PoC 2 congelada (`render_piloto.js`), D30 e M20 foram inseridos de forma experimental, revelando artefatos de renderização e problemas de sobreposição temporal. A arquitetura de desacoplamento de estado e barramento sonoro (`StageStateManager` e `RobustSoundBus`) está em desenvolvimento no branch `feature/fase2-nucleo-composicao` e ainda não foi integrada aos scripts de renderização.

---

## 4. B-Roll Contextualizado e Inteligente `[HIPÓTESE]` `[PENDÊNCIA]`

### Diagnóstico Histórico `[FATO VERIFICADO]`
Nos testes preliminares com os scripts experimentais legados `broll_pexels.py` e `broll_pixabay.py`, o motor inseriu zero ou no máximo uma imagem complementar ao longo de mais de 4 minutos de vídeo.

### Investigação da Causa Raiz `[HIPÓTESE]` `[PENDÊNCIA]`
- A baixa utilização de B-roll foi levantada como uma **hipótese técnica a ser investigada**, envolvendo:
  1. A passagem de palavras avulsas ou coloquiais em português para APIs indexadas primordialmente em língua inglesa;
  2. Limiares de pontuação semântica excessivamente restritivos nos scripts de busca;
  3. Lógica de fallback inexistente quando uma busca não retorna resultados de vídeo em alta resolução.
- *Status:* A confirmação definitiva da causa raiz requer testes controlados de consulta às APIs com vocabulário traduzido e balanceado.

### Diretriz Editorial Proposta `[PROPOSTA]` `[EXPERIMENTAL]`
- **Extração Semântica pelo Briefing:** O módulo editorial identifica os blocos conceituais e gera termos de busca industriais padronizados em inglês (ex.: *garment factory*, *sewing machine*, *textile production line*, *industrial clothing workshop*).
- **Duração de Inserção:** A referência de **3 a 5 segundos** por clipe de B-roll é adotada como **parâmetro experimental preliminar**, devendo ser flexibilizada conforme o ritmo da fala e a extensão do raciocínio abordado.

---

## 5. Reenquadramento, Composição e Áreas de Segurança `[DECISÃO]` `[PLANEJADO]`

### 5.1 Reenquadramento a partir de Fontes 4K UHD
A captura em 3840×2160 oferece margem para recomposição de plano sem qualquer perda de qualidade ou interpolação artificial:
- **Para 16:9 Full HD (1920×1080):** Redução proporcional (*downscale*) de alta fidelidade com filtros Lanczos/Bicubic, permitindo cortes virtuais de câmera (plano médio para primeiro plano / plano fechado) com fator de zoom de até 2x mantendo resolução nativa 1080p.
- **Para 9:16 Full HD Vertical (1080×1920):** Recorte vertical (*crop*) a partir da imagem 4K de 2160 pixels de altura, ancorado nas coordenadas faciais do apresentador (`rosto` em `branding/config.json` ou detecção facial automatizada). O apresentador é mantido centralizado dinamicamente.

### 5.2 Perfis de Entrega e Áreas de Segurança (Safe Areas)

```text
+-----------------------------------------------------------------------------------+
| PERFIL 1: YOUTUBE / WIDESCREEN (16:9 — 1920×1080)                                  |
|                                                                                   |
|  +-----------------------------------------------------------------------------+  |
|  | [Zona Segura Superior - 5% / 54 px]: Evitar elementos críticos nas bordas  |  |
|  |                                                                             |  |
|  |                                                                             |  |
|  |                           APRESENTADOR CENTRAL                              |  |
|  |                       (Cortes T10 / D30 / M20 no terço lateral)             |  |
|  |                                                                             |  |
|  | [Zona Inferior Reservada - 100 px]: Barra de progresso, botões do player    |  |
|  | [Canto Inferior Direito - 120x80 px]: Marca d'água / botão de inscrição    |  |
|  +-----------------------------------------------------------------------------+  |
+-----------------------------------------------------------------------------------+

+-----------------------------------------------------------------------------------+
| PERFIL 2: REDES SOCIAIS VERTICAIS (9:16 — 1080×1920: Shorts / Reels / TikTok)     |
|                                                                                   |
|  +-----------------------------------------------------------------------------+  |
|  | [ZONA PROIBIDA SUPERIOR - 150 px]: Ícones de status, barra de busca, áudio  |  |
|  +-----------------------------------------------------------------------------+  |
|  |                                                                             |  |
|  |                                                                             |  |
|  |                         ZONA VISUAL ÚTIL SUPERIOR                           |  |
|  |                      (Apresentador / Câmera Principal)                      |  |
|  |                                                                             |  |
|  | --------------------------------------------------------------------------- |  |
|  |                                                                             |  |
|  |                          ZONA CENTRAL / SPLIT-STAGE                         |  |
|  |                     (Legendas Dinâmicas / Motion M20/D30)     [ZONA DIREITA |  |
|  |                                                                PROIBIDA     |  |
|  |                                                                120 px:      |  |
|  |  +----------------------------------------------------------+  Curtir,      |  |
|  |  | [ZONA PROIBIDA INFERIOR - 250 px]:                       |  Comentar,    |  |
|  |  | Legenda da plataforma, nome do canal, CTA e faixa de áudio |  Compartilhar] |  |
|  |  +----------------------------------------------------------+               |  |
|  +-----------------------------------------------------------------------------+  |
+-----------------------------------------------------------------------------------+
```

### 5.3 Política de Taxa de Quadros (FPS) `[DECISÃO]`
- **Fonte:** 59,94 fps (60000/1001).
- **Composição Gráfica (HyperFrames/GSAP):** Gera quadros a 60 fps nominais ou cadência sincronizada com timebase de 60000/1001.
- **Política por Perfil de Saída:**
  - *Perfil 16:9 Master YouTube:* Saída em **59,94 fps** idêntica à taxa nativa da câmera, preservando integridade de timecode e evitando quedas de quadro (*frame drops*) ou repetições.
  - *Perfil 9:16 Cortes / Redes:* Saída homologada em **60 fps** ou **59,94 fps** via filtro de conformação temporal do FFmpeg (`fps=fps=60000/1001` ou `fps=fps=60`), garantindo reprodução fluida em telas de alta taxa de atualização sem gaguejos (*judder*).

---

## 6. Mecanismo de Renderização e Áudio `[DECISÃO]` `[IMPLEMENTADO]`

1. **Mecanismo HyperFrames 0.9.5 (`hyperframes.mjs`):**
   - Renderização headless local via Chrome Headless Shell.
   - Extrai frames em imagens estáticas ou buffer compartilhado sem depender de placas gráficas proprietárias de nuvem.
2. **Encapsulamento Final com FFmpeg 9.0.2:**
   - Codificação de vídeo H.264/H.265 via FFmpeg com perfil de alta compatibilidade (`pix_fmt yuv420p`).
   - Muxing do fluxo de áudio final tratado.
3. **Nível de Sonoridade (Loudness) por Perfil de Distribuição Audiovisual:**
   - **Recomendação AES71-2018 (reafirmada em 2023):** *Recommended Practice for audio loudness of OTT television and online video distribution*. Prática recomendada da Audio Engineering Society para produções de vídeo online (*sound-with-picture*), aplicável diretamente ao motor do Editor (não constitui requisito mandatório universal).
   - **Normas e Práticas de Áudio Isolado (AESTD1008 e AES77-2023):** Diretrizes voltadas especificamente para distribuição e streaming de áudio sem imagem (*audio-only*). O Documento Técnico AESTD1008 serviu de base à prática recomendada AES77-2023, excluindo conteúdos de vídeo de seu escopo primário e remetendo produções audiovisuais diretamente à AES71-2018.
   - **Recomendações EBU R128 (v5.0), R128 S1 e R128 S2:** 
     - *EBU R128 v5.0:* Recomendação principal de normalização de sonoridade de programas para radiodifusão (-23,0 LUFS ±0,5 LU, True Peak máximo de -1,0 dBTP).
     - *EBU R128 S1:* Complemento específico para conteúdo de curta duração (anúncios publicitários, chamadas promocionais e vinhetas).
     - *EBU R128 S2:* Complemento específico para sonoridade em streaming.
   - **Norma ITU-R BS.1770-5 (11/2023):** Algoritmo padrão de medição de sonoridade integrada e True Peak (ressalvada a versão exata do filtro nos experimentos históricos como `[NÃO VERIFICADO]`, sem reprocessamento).
   - **Perfis de Plataformas Online:**
     - *Spotify (Oficial):* Reprodução normalizada padrão em **-14,0 LUFS** (com opções Alto a -11 LUFS e Baixo a -19 LUFS para usuários Premium).
     - *YouTube (Referência Empírica):* Não publica meta oficial mandatória fixa em -14 LUFS; aplica normalização contra picos e recurso *Stable Volume* (Volume Estável); -14,0 LUFS é estimativa de mercado decorrente da atenuação de materiais acima deste patamar.
     - *Apple Music (Referência de Mercado):* Estimativa da indústria em **-16,0 LUFS** (associada ao Sound Check), sem especificação oficial publicada pela Apple.
   - **Diretriz do Pipeline:** Parâmetros de alvo (`target_lufs`, `true_peak_limit`) estritamente configuráveis por perfil de distribuição em `config.json`.

---

## 7. Controle de Qualidade Visual e QA de Renderização `[DECISÃO]` `[PLANEJADO]`

Para assegurar confiabilidade industrial antes da entrega, o pipeline incorpora duas etapas de controle de qualidade:

### 7.1 Verificações Automatizadas de Integridade (QA Técnico)
- **Verificação de Descarte de Quadros (*Frame Drop*):** Análise do log do FFmpeg e contagem total de frames renderizados contra a duração esperada da timeline (`fps * duration`).
- **Sincronismo Áudio/Vídeo (Lip-Sync):** Validação instrumental de ausência de deriva temporal (*drift*) entre o início e o fim do arquivo renderizado (desvio máximo tolerado: ±1 quadro / ~16 ms).
- **Detecção de Quadros Negros / Congelados:** Execução automatizada de filtros FFmpeg (`blackdetect`, `freezedetect`) para alertar sobre eventuais falhas do Chrome Headless Shell ou da renderização de templates.
- **Conformidade de Áudio:** Análise do arquivo final via `ebur128` garantindo sonoridade integrada em -14,0 LUFS (±0,5 LU) e True Peak <= -1,0 dBTP.

### 7.2 Avaliação Audiovisual Pós-Render (QA Editorial e Perceptual)
- **Inspeção de Legibilidade:** Garantia de que legendas e cartelas D30/M20 não conflitam com as zonas proibidas das plataformas e mantêm contraste e legibilidade mesmo em telas móveis pequenas.
- **Fluidez de Transições:** Verificação visual de ausência de piscamentos (*flicker*) na entrada/saída de cartelas e B-rolls.
- **Naturalidade de Cortes:** Validação de que cortes editoriais de hesitações e falsos começos preservam a linha de raciocínio e a cadência oratória do apresentador.
