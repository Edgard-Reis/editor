# REGISTRO DE TESTES E EVIDÊNCIAS EMPÍRICAS (TESTS_AND_EVIDENCE.md)
## Protocolo de Fixtures, Telemetria de Desempenho e Histórico de Validações

---

> **Status:** DOCUMENTAÇÃO OPERACIONAL INSTANCIADA — REGISTRO FACTUAL DE TESTES E EVIDÊNCIAS.

---

| Metadado | Especificação |
| :--- | :--- |
| **Documento** | `TESTS_AND_EVIDENCE.md` |
| **Versão** | 1.0.0-alpha.1 |
| **Data de Atualização** | 11/11/2026 |
| **Responsável Técnico** | Axiom (Instrumentação e Testes) / Forge (Execução) |
| **Ambiente de Testes** | Sandbox Isolado no PC Principal (Windows, GPU AMD RX 6600M) |
| **Diretório Canônico** | `D:\Drifit\Experimentos_Sandbox\PLANEJAMENTO_REORGANIZACAO_ESTRATEGICA_2026-11-11\documentacao_operacional\` |

---

# 1. FINALIDADE DESTE DOCUMENTO

Substituir relatórios cartoriais repetitivos por um **registro objetivo, factual e reproduzível** de todos os testes executados nos módulos do Editor.

Toda afirmação técnica de que uma funcionalidade "está pronta" ou "funciona" deve ser obrigatoriamente fundamentada em dados deste documento: comando executado, fixture utilizada, métricas medidas e resultado verificado.

---

# 2. ACERVO HISTÓRICO DE EVIDÊNCIAS PRÉVIAS (ETAPA 2B)

Os ensaios em laboratório executados em 08/11/2026 comprovaram as seguintes capacidades reais no ambiente do Proprietário:

| Ensaio / Etapa | Mídia e Parâmetros | Hardware | Resultado Comprovado |
| :--- | :--- | :--- | :--- |
| **Etapa 2B.1** | Manipulação básica de vídeo via Python | CPU local | Comprovada interoperabilidade Python + FFmpeg para leitura de contêineres e transcodificação. |
| **Etapa 2B.2** | Estruturação de faixas e projeto | CPU local | Validação do modelo de dados inicial em JSON e controle de faixas de mídia. |
| **Etapa 2B.3** | Render sintético 1080p30 H.264 (6s) | GPU / CPU | Comprovada a geração de vídeo final MP4 funcional e reproduzível. |
| **Etapa 2B.4** | Motion Library (componente `titulo_heroi` T10) | CPU local | Validação de queima de títulos dinâmicos e overlays gráficos em vídeo. |
| **Etapa 2B.5** | Transcrição de áudio real do Dr. Gestão | CPU (int8) | Whisper local operou com alta fidelidade semântica em áudio extraído de gravação real. |

---

# 3. PROTOCOLO PADRONIZADO DE FIXTURES DE TESTE (SANDBOX)

Todos os módulos são testados contra uma bateria padronizada de fixtures sintéticas e controladas:

| Identificador | Descrição da Fixture | Propósito Técnico do Teste |
| :--- | :--- | :--- |
| **`fix_valid_15s.mp4`** | Vídeo 1080p a 30 fps (15s) com áudio senoidal estéreo 48 kHz. | Validação do caminho feliz padrão de ponta a ponta. |
| **`fix_no_audio_5s.mp4`** | Vídeo 1080p (5s) sem nenhuma stream de áudio. | Validação de tratamento gracioso (módulo não deve travar). |
| **`fix_multi_audio_10s.mp4`**| Vídeo (10s) contendo 2 faixas de áudio independentes (48 kHz). | Validação de inspeção e seleção correta de faixa pelo FFprobe. |
| **`fix_silent_audio_10s.mp4`**| Vídeo (10s) com áudio de amplitude zero (silêncio legítimo). | Validação de que áudio silencioso **não** é classificado como erro ou corrupção. |
| **`fix_corrupt.mp4`** | Arquivo com cabeçalho MP4 truncado ou bytes aleatórios. | Validação de captura limpa de erro de contêiner ilegível. |
| **Cenário de Caminho** | Pasta com espaços e acentos (`D:\...\Testes Gravações Estúdio\`). | Validação de compatibilidade de caminhos complexos no Windows. |

---

# 4. REGISTROS REAIS DE EXECUÇÃO E TELEMETRIA DOS MÓDULOS

### Registro de Execução — Módulo: MOD-01-INGEST-AUDIO — Data: 2026-11-11
- **Localização do Sandbox:** `D:\Drifit\Experimentos_Sandbox\EXP-MOD01-INGEST-AUDIO\`
- **Comando de Teste:** `python test_ingest.py`
- **Ambiente:** PC Principal Windows, Python 3.10+, FFmpeg 7.1 Essentials.
- **Resultados dos 6 Cenários de Teste:**
  1. **Fixture Válida Padrão (`fix_valid_15s.mp4`, 1080p30 H.264):**
     - Hash SHA-256 verificado antes e após a ingestão: $\Delta\text{Hash} = 0$ (**AC-02 APROVADO**).
     - Parâmetros do WAV extraído: 16.000 Hz, 16-bit PCM s16le, 1 canal mono (**AC-03 APROVADO**).
     - Duração: 15.02s (desvio em relação à stream original: 0.019s, dentro da tolerância de $\pm 0.15$s) (**AC-04 APROVADO**).
     - Telemetria de relógio: Hash = 0.005s, FFprobe = 0.779s, Extração FFmpeg = 0.100s, Total = 0.929s (**AC-06 APROVADO**).
  2. **Fixture Sem Áudio (`fix_no_audio_5s.mp4`):**
     - Tratamento gracioso confirmado: 0 streams de áudio registradas, sem geração indevida de WAV, código de retorno 0.
  3. **Fixture Multi-Áudio (`fix_multi_audio_10s.mp4`):**
     - Ambas as faixas inspecionadas no `project.json`; derivado extraído com sucesso da stream 0 padrão.
  4. **Fixture Áudio Silencioso (`fix_silent_audio_10s.mp4`):**
     - Detecção de silêncio acústico (RMS < 10) com flag `is_silent_detected: true`, sem falha de processo e sem classificação de corrupção.
  5. **Caminho com Espaços e Acentos (`Testes Gravações Estúdio\episódio_01 teste bruto.mp4`):**
     - Execução perfeita no Windows, gerando o projeto e WAV sem erros de encoding de caracteres.
  6. **Injeção de Falhas (`fix_corrupt.mp4` e arquivo inexistente):**
     - Arquivo corrompido encerrou com código 2 e mensagem clara de FFprobe; arquivo inexistente encerrou com código 1 (**AC-05 APROVADO**).
- **Veredito do Revisor Independente (Axiom / Sentry):** **APROVADO (100% dos testes concluídos com sucesso).**
- **Declaração Oficial:**
  > `MÓDULO CONCLUÍDO PELOS AGENTES — TESTADO E REVISADO EM SANDBOX — HOMOLOGADO EM ARQUIVO REAL.`

---

### Registro de Homologação em Arquivo Real — Módulo: MOD-01-INGEST-AUDIO — Data: 2026-11-11
- **Arquivo de Teste Real:** `D:\Drifit\Editor\20260823_203211.mp4`
- **Diretório de Saída:** `D:\Drifit\Experimentos_Sandbox\EXP-MOD01-INGEST-AUDIO\homologacao_real_20260823\`
- **Tamanho do Arquivo:** 308.052.637 bytes (~308 MB)
- **Hash SHA-256 Pré-Ingestão:** `772fc29b30012bf0ae2fb9263fa5a119ef4f6ef043d610553848d31cd7cc873e`
- **Hash SHA-256 Pós-Ingestão:** `772fc29b30012bf0ae2fb9263fa5a119ef4f6ef043d610553848d31cd7cc873e` ($\Delta\text{Hash} = 0$, integridade do original intocada)
- **Mídia Detectada:**
  - Contêiner: MP4/MOV
  - Vídeo: 3840x2160 (4K UHD) @ 59.94 fps, Codec: HEVC (H.265)
  - Áudio: AAC Stereo 48.000 Hz, 40.11s
- **Derivado Gerado:**
  - Arquivo: `derivatives/audio_speech_16k_mono.wav` (1.283.492 bytes)
  - Parâmetros: 16.000 Hz, 1 canal mono, PCM 16-bit
  - Duração: 40.107s (desvio absoluto de apenas 0.006s)
  - Silêncio detectado: `false` (áudio com fala legítima)
- **Telemetria de Execução:**
  - Cálculo Hash SHA-256 (308 MB): 1.196s
  - Inspeção FFprobe: 0.101s
  - Extração de Áudio FFmpeg: 0.148s
  - Tempo Total Wall-Clock: 2.51s
- **Status do Projeto:** `INGEST_COMPLETED` (Registrado em `project.json`)

---

### Registro de Execução e Homologação — Módulo: MOD-02-WHISPER-LOCAL — Data: 2026-11-11
- **Localização do Sandbox:** `D:\Drifit\Experimentos_Sandbox\EXP-MOD02-WHISPER-LOCAL\`
- **Script:** `transcribe.py` | **Suíte de Testes:** `test_transcribe.py`
- **Ambiente:** Intel Xeon E5-2680 v4 (14 cores / 28 threads), 32 GB RAM, Python 3.11, Faster-Whisper 1.2.1 (CTranslate2 INT8).
- **Mídia Avaliada:** Derivado `audio_speech_16k_mono.wav` do vídeo real `20260823_203211.mp4` (40.11s).
- **Resultados da Transcrição:**
  - **Idioma Detectado:** Português (`pt`), com 100% de confiança.
  - **Segmentos:** 7 segmentos de fala gerados com coerência contextual completa.
  - **Palavras:** 97 palavras com timestamps individuais de início, fim e probabilidade.
  - **Artefatos:** `transcript.json` (word timestamps), `transcript.srt` (legendas) e `transcript.txt` (texto corrido).
  - **Integração:** `project.json` atualizado com metadados de transcrição e status `COMPLETED`.
- **Telemetria de Desempenho:**
  - Carga do Modelo (`base` INT8): 4.59s (apenas na 1ª inicialização)
  - Tempo de Inferência Acústica: **5.30s** para 40.11s de áudio.
  - Fator Tempo Real (RTF): **0.132x** (**7.6x mais rápido que tempo real** em CPU multi-threading).
- **Resultados dos Testes Automatizados (`test_transcribe.py`):**
  - `test_01_transcribe_project_mode`: APROVADO (validação completa de artefatos, palavras e timestamps).
  - `test_02_missing_input_error_handling`: APROVADO (tratamento de erro limpo).
  - Total: 2 de 2 testes aprovados (100% de sucesso).
- **Declaração Oficial:**
  > `MÓDULO CONCLUÍDO PELOS AGENTES — TESTADO E REVISADO EM SANDBOX — HOMOLOGADO EM ÁUDIO REAL.`

---

### Registro de Execução e Homologação — Módulo: MOD-03-TIMESTAMP-ALIGN — Data: 2026-11-11
- **Localização do Sandbox:** `D:\Drifit\Experimentos_Sandbox\EXP-MOD03-TIMESTAMP-ALIGN\`
- **Script:** `aligner.py` | **Suíte de Testes:** `test_aligner.py`
- **Ambiente:** Intel Xeon E5-2680 v4 (14 cores / 28 threads), 32 GB RAM, Python 3.11, NumPy.
- **Dados Avaliados:** Transcrição `transcript.json` e WAV do projeto real `homologacao_real_20260823` (40.11s).
- **Resultados do Alinhamento e Detecção de Pausas:**
  - **Palavras Analisadas:** 97 palavras com timestamps individuais.
  - **Pausas Detectadas:** 20 pausas categorizadas (4 micro-pausas, 8 pausas naturais de respiração, 8 pausas de término de sentença/silêncio).
  - **Unidades Editoriais Estruturadas:** 15 blocos coerentes de oração/frase com margens seguras de corte acústico (`padded_in_point` pré-roll 100ms e `padded_out_point` pós-roll 200ms).
  - **Inspeção de Energia RMS:** Cálculo dos vales de transição acústica para corte sem estalos nem cliques.
  - **Artefato Gerado:** `alignment/alignment.json` e atualização do `project.json` com o bloco `"alignment"`.
- **Telemetria:** Execução concluída em **0.01s** (processamento algorítmico quase instantâneo).
- **Resultados dos Testes Automatizados (`test_aligner.py`):**
  - `test_01_alignment_project_mode`: APROVADO (validação de unidades editoriais, integridade de timestamps e project.json).
  - `test_02_missing_input_error_handling`: APROVADO (tratamento de erro).
  - Total: 2 de 2 testes aprovados (100% de sucesso).
- **Declaração Oficial:**
  > `MÓDULO CONCLUÍDO PELOS AGENTES — TESTADO E REVISADO EM SANDBOX — HOMOLOGADO EM PROJETO REAL.`

---

### Registro de Execução e Homologação — Módulo: MOD-06-VIDEO-CUT-RENDER (Walking Skeleton) — Data: 2026-11-11
- **Responsável pela Implementação:** Agente **Forge** (Engenharia de Pipeline)
- **Responsável pela Auditoria Instrumental:** Agente **Axiom** (Auditoria Técnica Instrumental)
- **Orquestração Geral:** Agente **Maestro**
- **Localização do Sandbox:** `D:\Drifit\Experimentos_Sandbox\EXP-MOD06-VIDEO-CUT-RENDER\`
- **Arquivo de Saída Gerado:** `D:\Drifit\Experimentos_Sandbox\EXP-MOD01-INGEST-AUDIO\homologacao_real_20260823\renders\short_vendas_9x16.mp4`
- **Mídia de Entrada:** `20260823_203211.mp4` (4K HEVC original preservado intacto)
- **Metadados Instrumentais Validados (FFprobe):**
  - **Resolução de Vídeo:** 1080x1920 (Aspect Ratio 9:16 vertical nativo).
  - **Codec de Vídeo:** H.264 (libx264, profile High, yuv420p) @ 59.94 fps, taxa de bits ~12.2 Mbps.
  - **Áudio:** AAC Stereo (2 canais), 48.000 Hz, taxa de bits 192 kbps.
  - **Intervalo de Corte:** In-Point = 7.40s / Out-Point = 24.70s (Gancho de vendas identificado no alinhamento).
  - **Duração do Corte:** 17.32 segundos.
  - **Tamanho do Arquivo:** 26.755.469 bytes (~26.7 MB).
  - **Integridade do Arquivo Original:** $\Delta\text{Hash} = 0$ (`772fc29b30012bf0ae2fb9263fa5a119ef4f6ef043d610553848d31cd7cc873e`), arquivo fonte 100% inalterado.
- **Evidências Visuais:** Frame de controle extraído em `evidence/frame_9x16_t6s.png`.
- **Declaração Oficial:**
  > `WALKING SKELETON CONCLUÍDO COM SUCESSO — CICLO PONTA A PONTA COMPROVADO (INGESTÃO -> TRANSCRIÇÃO -> ALINHAMENTO -> CORTE VERTICAL 9:16).`

---

### Registro de Execução e Homologação — Módulo: MOD-07-DYNAMIC-SUBTITLES — Data: 2026-11-11
- **Responsável pela Execução:** Agente **Maestro** & Equipe de Pipeline
- **Localização do Sandbox:** `D:\Drifit\Experimentos_Sandbox\EXP-MOD07-DYNAMIC-SUBTITLES\`
- **Script:** `subtitles.py` | **Suíte de Testes:** `test_subtitles.py`
- **Vídeo de Entrada:** `short_vendas_9x16.mp4` (1080x1920 @ 60fps)
- **Arquivo de Saída Gerado:** `D:\Drifit\Experimentos_Sandbox\EXP-MOD01-INGEST-AUDIO\homologacao_real_20260823\renders\short_vendas_legendado_9x16.mp4`
- **Metadados Instrumentais Validados (FFprobe):**
  - **Resolução:** 1080x1920 (Display Aspect Ratio 9:16).
  - **Taxa de Quadros:** 59.94 fps constante (1.031 frames).
  - **Codec de Vídeo:** H.264 (Lavc libx264, profile High) @ 11.5 Mbps.
  - **Áudio:** AAC Stereo 48.000 Hz, 192 kbps (preservação idêntica da stream de corte).
  - **Duração:** 17.32 segundos.
  - **Tamanho do Arquivo:** 25.380.060 bytes (~25.3 MB).
- **Legendas Dinâmicas (ASS Karaokê):**
  - 51 palavras sincronizadas com destaque em tempo real em Amarelo/Dourado (`#FFD700`) e base em Branco com contorno de 6px.
  - Posicionamento em Safe Zone vertical (Margem inferior 420px).
- **Suíte de Testes Automatizados (`test_subtitles.py`):**
  - `test_01_ass_and_video_generation`: APROVADO (validação estrutural de ASS, PlayResX/Y e integridade de MP4).
  - `test_02_missing_input_error_handling`: APROVADO (tratamento gracioso de erro).
  - Total: 2 de 2 testes aprovados (100% de sucesso).
- **Declaração Oficial:**
  > `MÓDULO CONCLUÍDO COM SUCESSO — PRIMEIRO SHORT 9:16 COM LEGENDAS DINÂMICAS RENDERIZADO COM SUCESSO.`

---

### Registro de Execução e Homologação — Módulo: MOD-08-SOUND-DESIGN — Data: 2026-11-11
- **Responsável pela Execução:** Agente **Maestro** & Equipe de Pipeline
- **Localização do Sandbox:** `D:\Drifit\Experimentos_Sandbox\EXP-MOD08-SOUND-DESIGN\`
- **Script:** `sound_design.py` | **Suíte de Testes:** `test_sound_design.py`
- **Vídeo de Entrada:** `short_vendas_legendado_9x16.mp4`
- **Arquivo de Saída Gerado:** `D:\Drifit\Experimentos_Sandbox\EXP-MOD01-INGEST-AUDIO\homologacao_real_20260823\renders\short_vendas_master_sound_9x16.mp4`
- **Metadados Instrumentais Validados (FFprobe):**
  - **Resolução e Taxa de Quadros:** 1080x1920 (9:16) @ 59.94 fps constante.
  - **Áudio:** AAC Stereo 48.000 Hz, 192 kbps.
  - **Duração:** 17.32 segundos.
  - **Tamanho do Arquivo:** 25.379.192 bytes (~25.3 MB).
  - **Efeitos Sonoros Mixados (12 SFX):**
    - 1 impacto grave no gancho inicial aos 0.08s (`impacto_grave.wav` a -12 dB).
    - 11 transições acústicas suaves de legenda (`clique.wav` a -20 dB e `whoosh_curto.wav` a -14 dB).
    - Teto de pico seguro calibrado em 0.950 (-0.44 dBFS) com zero distorção.
- **Telemetria:** Processamento e mixagem concluídos em **1.23 segundos**.
- **Suíte de Testes Automatizados (`test_sound_design.py`):**
  - `test_01_sound_mix_and_video_generation`: APROVADO.
  - `test_02_missing_sfx_error_handling`: APROVADO.
  - Total: 2 de 2 testes aprovados (100% de sucesso).
- **Declaração Oficial:**
  > `MÓDULO CONCLUÍDO COM SUCESSO — VÍDEO VERTICAL MASTER COM LEGENDAS E SOUND DESIGN FINALIZADO.`

---

### Registro de Auditoria Técnica Instrumental Independente — Agente: Axiom — Data: 2026-11-11
- **Alvo Principal Auditado:** `short_vendas_9x16.mp4` (26.755.469 bytes)
- **Fonte Original Auditada:** `D:\Drifit\Editor\20260823_203211.mp4` (308.052.637 bytes)
- **Métodos e Ferramentas:** FFprobe 8.1.2-essentials, FFmpeg 7.1-essentials, ebur128, astats, SHA-256 e correlação cruzada PCM.
- **Resultados da Auditoria Instrumental:**
  1. **Integridade da Fonte Original:** SHA-256 idêntico (`772fc29b...873e`), tamanho inalterado, `LastWriteTime` de 22/10/2026 preservado anterior a qualquer ingestão/render. Veredito: `ORIGINAL_UNTOUCHED_CONFIRMED`.
  2. **Cadeia de Custódia do Render:** SHA-256 medido = `D5045BA6ECD3DF9C73B64952A53858842FE227FA2C5FF02D8FB0F70EC611F2B5`, tamanho = 26.755.469 bytes. Confere 100% com o bloco `renders[0]` de `project.json`. Veredito: `PASS`.
  3. **Stream de Vídeo e Exatidão de Corte:** H.264 High Profile level 42, Lavc61.19.100 libx264, resolução 1080x1920 (SAR 1:1, DAR 9:16) confirmada, yuv420p progressivo, bt709 tv range. No original, o intervalo de 7,4s a 24,7s contém exatamente 1.031 frames (primeiro em 7,409900s, último em 24,683256s); o render entrega exatamente 1.031 frames decodificados ($\Delta\text{Frames} = 0$, corte frame-accurate perfeito, sem frames ocultos ou duplicados). Veredito: `PASS`.
  4. **Correlação Temporal e Acústica:** Análise de PSNR ancorada a partir de $t=7.400s$ da fonte; defasagem acústica de lag = 21,31 ms (341 amostras a 16 kHz), correspondente exatamente à fronteira do pacote de 1.024 amostras AAC a 48 kHz. Correlação cruzada normalizada de **0,992640** (99,26% de fidelidade de sinal entre corte e fonte original), com offset A/V interno imperceptível de 11,4 ms.
  5. **Métricas de Áudio (EBU R128 / ITU-R BS.1770-5 e astats):**
     - Render `short_vendas_9x16.mp4`: $I = -7,9\text{ LUFS}$, $LRA = 2,2\text{ LU}$, $TP = +0,2\text{ dBTP}$, Pico $= +0,1681\text{ dBFS}$, $RMS = -11,0363\text{ dBFS}$, Crest $= 3,6326$, Noise floor $= -47,21\text{ dB}$, DC offset $= 0,000012$.
     - Comparação com o trecho fonte original: $I = -7,6\text{ LUFS}$, $LRA = 2,3\text{ LU}$, $TP = +0,3\text{ dBTP}$, $RMS = -10,7254\text{ dBFS}$ ($\Delta I = -0,3\text{ LU}$ e $\Delta RMS = -0,312\text{ dB}$).
     - Demonstração: O corte preservou a dinâmica original da fonte sem ganho indevido. Em conformidade com o postulado da Seção 5 de `AUDIO_PIPELINE.md`, **nenhuma razão de SNR foi calculada** dada a inexistência de voz limpa isolada de referência (*clean speech ground-truth*).
- **Ressalvas Apontadas:**
  - **F1 (True Peak +0,2 dBTP):** Constatado no corte bruto; sanado na versão `short_vendas_master_broadcast_9x16.mp4` com teto a -5.6 dBTP e -14.0 LUFS.
  - **F5 (Proteção SO):** Sugestão de ativação do atributo Read-Only nativo no Windows para defesa em profundidade.
  - **F6 (Rótulos de Idioma):** Streams marcadas com `por` para conformidade de distribuição.
- **Veredito Oficial do Axiom:** `APROVADO PARA HOMOLOGAÇÃO INTERNA COM RESSALVAS`.

---

### Aditivo de Auditoria Instrumental — Agente: Axiom — Data: 2026-11-11
- **Alvos Auditados no Aditivo:**
  - `short_vendas_9x16.mp4` (SHA-256: `D5045BA6...F2B5` — Alvo permanece imutável e intacto)
  - `short_vendas_legendado_9x16.mp4` (SHA-256: `3F5A4EAB...7353`)
  - `short_vendas_master_sound_9x16.mp4` (SHA-256: `0CFE9AF2...78EC37`)
  - `short_vendas_master_broadcast_9x16.mp4` (SHA-256: `4247B433...7AB8`)

- **Análise Instrumental do Master Broadcast (`short_vendas_master_broadcast_9x16.mp4`):**
  - **Loudness EBU R128:** $I = -14,0\text{ LUFS}$ e $TP = -5,6\text{ dBTP}$ (Conforme a norma broadcast / YouTube Shorts).
  - **Anomalia de Reamostragem (Taxa de Amostragem):** Áudio reamostrado indevidamente para **96.000 Hz** (o padrão técnico de produção e masterização do projeto é estritamente **48.000 Hz**). Causa raiz: filtro `loudnorm` do FFmpeg operando sem parâmetro explícito `-ar 48000`.
  - **Anomalia de Truncamento / Defasagem de Cauda:** Duração de áudio = 17,400 s vs Duração de vídeo = 17,284 s ($\Delta = +116\text{ ms}$). O filtro de áudio introduziu cauda excedente não truncada por ausência de flag `-shortest` ou `atrim`.

- **Inconsistência de Métrica de Telemetria (RTF — Real Time Factor):**
  - **Diagnóstico:** No `project.json`, `transcription.real_time_factor` registrou `0.119` seguindo o RTF padrão ($\frac{T_{\text{processamento}}}{T_{\text{mídia}}} = \frac{4.77}{40.11} = 0,119$). Por outro lado, `telemetry.realtime_factor` no render registrou `0.331`, correspondendo à razão inversa de velocidade de reprodução ($\frac{T_{\text{mídia}}}{T_{\text{render}}} = \frac{17.3}{52.264} = 0,331$).
  - **RTF Padrão do Render:** $\frac{52,264}{17,3} = \mathbf{3,021}$.
  - **Correção Mandatória no Código/Schema:** Unificar e explicitar ambos os campos: `real_time_factor` ($T_{\text{proc}} / T_{\text{mídia}}$) e `speed_factor` ($T_{\text{mídia}} / T_{\text{proc}}$).

- **Tabela Consolidada de Achados (Axiom):**
  - **F1 (MÉDIA — Bloqueio de Distribuição):** True Peak inicial em +0.2 dBTP sanado no master broadcast (-5.6 dBTP), porém pendente de refiltragem a 48 kHz e truncamento de 116 ms.
  - **F2 (MÉDIA — Registro de Evidências):** Exclusão definitiva de entradas superdeclaradas/fantasmas (`_test_short_9x16`) em `project.json`.
  - **F3 (BAIXA — Cadência de Quadros):** CFR 59.94 nominal apresentando 5 slots vazios (média real 59.65 fps).
  - **F4 (BAIXA — Priming A/V):** Deslocamento inicial de 11,4 ms (vídeo em 0,038s, áudio em 0,000s) decorrente do priming intrínseco do codec AAC.
  - **F5 (BAIXA — Proteção de SO):** Atributo nativo *Read-Only* do Windows no arquivo fonte para mitigação em profundidade além do hash.
  - **F6 (BAIXA — Metadados e Duração):** Inclusão de tags de idioma explícitas (`-metadata:s:v:0 language=por -metadata:s:a:0 language=por`) e distinção entre duração nominal (17.3s) e duração exata de container (17.322s).

- **Parecer Final Consolidado (Axiom):**
  > **STATUS: APROVADO COM RESSALVAS.**  
  > **GOVERNANÇA: BLOQUEIO DE PROMOÇÃO ATIVO.**  
  > Nenhuma promoção autônoma para a pasta oficial será realizada até o saneamento completo de F1 (refiltro 48 kHz / 0 ms delta) e registro auditado de F2 a F6.  
  > **Produção e Sandbox permanecem rigorosamente intocadas.**

---

### Laudo da Re-auditoria Instrumental REAUDITORIA-02 (Axiom) — Data: 2026-11-11
- **Veredito Inicial:** `NÃO APROVADO PARA PROMOÇÃO` (11 PASS, 2 FAIL, 1 FAIL parcial).
- **Achado Crítico C2:** Truncamento de 85,333 ms de áudio de programa no master broadcast causado pelo lookahead do filtro `loudnorm` com `-shortest`.
- **Achado C13:** Faststart ausente (`moov` no final do arquivo).
- **Achado C10:** Ausência de `playback_speed_factor` na telemetria de transcrição.
- **Divergências Documentais Identificadas (D1 a D5):**
  - D1: Desvio real de áudio audível vs metadado de edit list.
  - D2: RTF real do Whisper medido em 0,124 (4,973s / 40,107s).
  - D3: Distinção entre contagem estática de 22 testes e histórico de reexecução instrumental.
  - D4: Distinção explícita entre estado pré e pós-ingestão do atributo Read-Only.
  - D5: Registro formal do log de execução da normalização (`broadcast.log`).

---

### Execução da Remediação Definitiva Autorizada (Receita D + R1 a R8) — Data: 2026-11-11
Sob autorização expressa do Proprietário de 11/11/2026 16:05, a engenharia aplicou as seguintes correções instrumentais:

1. **Master Broadcast com Receita D (Zero Perda + Faststart + Anti-Clique):**
   - **Comando Executado e Registrado em Log:**
     ```powershell
     ffmpeg -y -i short_vendas_master_sound_9x16.mp4 `
       -af "volume=-5.31dB,aresample=48000,atrim=0:17.316933,asetpts=PTS-STARTPTS,afade=t=out:st=17.296933:d=0.020" `
       -c:v copy -c:a aac -b:a 192k -ar 48000 -t 17.316933 -movflags +faststart `
       -metadata:s:v:0 language=por -metadata:s:a:0 language=por `
       short_vendas_master_broadcast_9x16.mp4
     ```
   - **Log de Execução Registrado na Cadeia de Custódia:** [`homologacao_real_20260823/renders/logs/broadcast.log`](file:///D:/Drifit/Experimentos_Sandbox/EXP-MOD01-INGEST-AUDIO/homologacao_real_20260823/renders/logs/broadcast.log) (D5 saneado).
   - **Auditoria Instrumental FFprobe & ebur128:**
     - **Resolução e Vídeo:** 1080x1920 (9:16) H.264 High Profile, 1031 frames exatos, duração 17,283933 s, tag `language=por`.
     - **Áudio Reamostrado e Sincronizado:** AAC Estéreo **48.000 Hz**, 813 pacotes (idêntico à fonte `master_sound`), duração de áudio 17,317000 s, tag `language=por`.
     - **Perda de Conteúdo Audível vs Master:** **0,000 ms** (C2 saneado integralmente).
     - **Descontinuidade de Borda:** $-80,8\text{ dB}$ (fade out de 20 ms elimina cliques acústicos).
     - **Posicionamento Faststart:** Átomo `moov` no início em `offset: 36 bytes` (`faststart: True`, C13 saneado).
     - **Loudness EBU R128:** $I = -13,9\text{ LUFS}$, $TP = -5,5\text{ dBTP}$ ($\le -1,0\text{ dBTP}$ conforme, folga de 4,5 dB), $LRA = 2,2\text{ LU}$.
     - **Cadeia de Custódia:** Tamanho = **25.381.286 bytes** | SHA-256 = `83EE4B74F4A6AC1E86A5A0F0E1A58A386191B48F58B3A5802D10F0C114060149`.

2. **Padronização Canônica ADR-05 em Transcrição e Pipeline:**
   - [`transcribe.py`](file:///D:/Drifit/Experimentos_Sandbox/EXP-MOD02-WHISPER-LOCAL/transcribe.py), [`transcript.json`](file:///D:/Drifit/Experimentos_Sandbox/EXP-MOD01-INGEST-AUDIO/homologacao_real_20260823/transcription/transcript.json) e [`project.json`](file:///D:/Drifit/Experimentos_Sandbox/EXP-MOD01-INGEST-AUDIO/homologacao_real_20260823/project.json):
     - Telemetria viva do Whisper: `real_time_factor`: $\mathbf{0,121}$ (inferência 4,843s / áudio 40,107s) e `playback_speed_factor`: $\mathbf{8,282}$ (40,107s / 4,843s).
     - Telemetria de Render: `real_time_factor`: $\mathbf{3,021}$ (52,264s / 17,3s) e `playback_speed_factor`: $\mathbf{0,331}$ (17,3s / 52,264s).
     - C10 saneado integralmente e sincronizado com a telemetria viva (resolvendo R12).

3. **Governança de Proteção de SO (R5 / Achado F5):**
   - [`ingest.py`](file:///D:/Drifit/Experimentos_Sandbox/EXP-MOD01-INGEST-AUDIO/ingest.py) e [`project.json`](file:///D:/Drifit/Experimentos_Sandbox/EXP-MOD01-INGEST-AUDIO/homologacao_real_20260823/project.json) atualizados para distinguir:
     - `pre_ingest_readonly`: false (estado original antes da ingestão).
     - `post_ingest_readonly`: true (estado assegurado via `os.chmod` como defesa em profundidade).
     - `os_write_permission`: false (escrita travada no sistema operacional).

4. **Emenda Regulatória ADR-05 em `DECISIONS.md`:**
   - Flag `-shortest` revogada formalmente para cadeias com normalização temporal.
   - Padrão estabelecido: `-t [duracao_video]` + `atrim/asetpts` + `afade=20ms` + `-movflags +faststart`.

5. **Blindagem e Segregação:**
   - Produção [`D:/Drifit/Editor/renders/`](file:///D:/Drifit/Editor/renders/) preservada 100% vazia até a conclusão da Re-auditoria 03.

---

### Laudo Definitivo da Re-auditoria Instrumental REAUDITORIA-03 (Axiom) — Data: 2026-11-11
- **Alvo Auditado:** [`short_vendas_master_broadcast_9x16.mp4`](file:///D:/Drifit/Experimentos_Sandbox/EXP-MOD01-INGEST-AUDIO/homologacao_real_20260823/renders/short_vendas_master_broadcast_9x16.mp4) (Versão 3)
- **Auditor Instrumental:** Axiom (Níveis 1 e 2 de Evidência Instrumental)
- **Homologador & Gatekeeper:** Zenith (Gatekeeper de Produção & Homologador de Qualidade)
- **Veredito Instrumental:** `APROVADO TECNICAMENTE` — **18/18 CRITÉRIOS PASS (ZERO FAIL MATERIAL)**.

#### Matriz Consolidada de Critérios (C1 a C18):
| Critério | Descrição | Exigência | Medição Instrumental Real | Veredito |
| :--- | :--- | :--- | :--- | :---: |
| **C1** | Taxa de Amostragem Áudio | 48.000 Hz | AAC LC 48.000 Hz stereo, 813 pacotes | **PASS** |
| **C2** | Perda de Conteúdo Audível | 0,000 ms vs master | 0,000 ms (831.488 amostras idênticas à fonte, fade 20ms) | **PASS** |
| **C3** | Sincronia Temporal A/V | Desvio $\le 30\text{ ms}$ | Áudio encerra a 0,121 ms do fim do vídeo (cauda 5,7 ms) | **PASS** |
| **C4** | Faststart (Web Streaming) | `moov` at byte offset 36 | `moov` no offset 36 (segundo passe confirmado em log) | **PASS** |
| **C5** | Loudness Integrado (EBU R128) | $-14,0 \pm 0,5\text{ LUFS}$ | $I = -13,9\text{ LUFS}$ (LRA: 2,2 LU) | **PASS** |
| **C6** | True Peak Inter-amostra | $\le -1,0\text{ dBTP}$ | $TP = -5,5\text{ dBTP}$ (folga de 4,5 dB contra ceifamento) | **PASS** |
| **C7** | Segurança de Sinal | 0 ceifamento, 0 NaN/Inf | 0 amostras $\ge 1,0$, 0 NaN, 0 Inf, noise floor $-52,3\text{ dBFS}$ | **PASS** |
| **C8** | Integridade do Vídeo | Sem recodificação | MD5 dos pacotes de vídeo: `36A7FEC845F76A2A8C7A8A1CC845E1DF` | **PASS** |
| **C9** | Descontinuidade Acústica | Sem estalo na borda | Fade de 20 ms suave, último sample a $-74,75\text{ dBFS}$ | **PASS** |
| **C10** | Telemetria ADR-05 Whisper | PSF e RTF em código e JSON | `transcribe.py`, `transcript.json` e `project.json` conformes | **PASS** |
| **C11** | Governança ReadOnly (R5) | Pré e pós separados | `ingest.py` e `project.json` conformes | **PASS** |
| **C12** | Hash e Tamanho do Master | Conformidade bit-a-bit | SHA-256 `83EE4B74...0149`, tamanho `25.381.286 bytes` | **PASS** |
| **C13** | Rastreabilidade do Broadcast | Log de execução | [`broadcast.log`](file:///D:/Drifit/Experimentos_Sandbox/EXP-MOD01-INGEST-AUDIO/homologacao_real_20260823/renders/logs/broadcast.log) presente (3.888 bytes) | **PASS** |
| **C14** | Reprodutibilidade N1 | Determinismo absoluto | Reexecução isolada reproduziu hash idêntico bit-a-bit | **PASS** |
| **C15** | Conformidade Regulatória | DECISIONS.md e TESTS | ADR-05 emendada e D1-D5 documentados formalmente | **PASS** |
| **C16** | Blindagem da Produção | Renders oficiais vazios | `D:\Drifit\Editor\renders\` 100% vazia (0 arquivos) | **PASS** |
| **C17** | Integridade da Custódia | 4 renders válidos | 4/4 renders conferidos sem órfãos de teste | **PASS** |
| **C18** | Proteção da Mídia Original | $\Delta\text{Hash} = 0$ | Original preservado intocado (`772FC29B...873E`), ReadOnly ativo | **PASS** |

#### Parecer de Gatekeeping e Homologação (Zenith):
> **STATUS: HOMOLOGAÇÃO TÉCNICA DEFERIDA COM SUCESSO.**  
> Todos os 18 critérios instrumentais (C1 a C18) foram aprovados com louvor técnico.  
> **DIRETRIZ DE PROMOÇÃO:** O master broadcast [`short_vendas_master_broadcast_9x16.mp4`](file:///D:/Drifit/Experimentos_Sandbox/EXP-MOD01-INGEST-AUDIO/homologacao_real_20260823/renders/short_vendas_master_broadcast_9x16.mp4) está qualificado e autorizado para promoção física à pasta oficial [`D:\Drifit\Editor\renders\`](file:///D:/Drifit/Editor/renders/).

---

### Laudo de Auditoria Instrumental — MASTER LONGO 16:9 1080p30 com Motion Graphics (Axiom) — Data: 2026-11-12

- **Ordem de Serviço:** Forge → Axiom, 11/11/2026 (auditoria instrumental independente do master longo 16:9 1080p30).
- **Alvo Auditado:** [`master_longo_16x9_1080p30_motion.mp4`](file:///D:/Drifit/Experimentos_Sandbox/EXP-BLOCO-LONGO-VIRAL/05_render_longo_1080p_motion/renders/master_longo_16x9_1080p30_motion.mp4) — **441.331.240 bytes**, `mtime` 11/11/2026 23:14:53, **SHA-256 `788BB5B85B5882A13F4D61FB8F609DE9F03E8A5BF1A16C3755F9AF29D22D4683`**.
- **Auditor Instrumental:** Axiom (Níveis 1 e 2 de Evidência Instrumental) | **Homologador / Gatekeeper:** Zenith | **Solicitante:** Forge.
- **Confrontado:** `RELATORIO_RENDER_1080P30.md` (6.897 B, 23:16:29) e `CONTRATO_DADOS_EDL_E_CLIPS.md` (normativa).

#### 1. Veredito

> **APROVADO COM RESSALVAS (mérito técnico) — BLOQUEIO DE PROMOÇÃO ATIVO (achado D1).**
>
> - **Mérito técnico do artefato: 18/18 CRITÉRIOS PASS (ZERO FAIL MATERIAL).** O defeito alegado de **165 s de tela preta está REFUTADO** por varredura exaustiva de 8.782 frames.
> - **Governança: D1 (drift da EDL / não-reprodutibilidade) BLOQUEIA a promoção.** O master materializa uma EDL de **31 eventos / 292,732 s** que **deixou de ser a fonte normativa vigente**; a EDL vigente foi regenerada em **12/11/2026 00:07:24** com **30 eventos / 288,842 s**. O artefato **não é reprodutível** a partir da fonte normativa atual.
> - **Nenhuma promoção autônoma** para `D:\Drifit\Editor\renders\` será executada. Sanear D1 (e D2, D4) e reemitir o laudo antes de qualquer promoção.

#### 2. Hierarquia de fontes de evidência aplicada

- **Nível 1 (código e testes reexecutáveis):** FFmpeg/FFprobe 7.1 (gyan.dev), Python 3.11 + numpy/scipy/PIL; scripts de auditoria executados sobre o artefato e sobre as fontes; leitura do código do render (`03_render_master_1080p30.py`, L89-96, L363-423, L426-432, L520-582) e dos logs reais de execução.
- **Nível 2 (metadados instrumentais):** FFprobe (streams/packets/frames/PTS), `ebur128`, `loudnorm` (JSON), `astats`, `signalstats` (YAVG por frame), `blackdetect`, PCM `f32le` a 192 kHz, correlação cruzada e correlação de envelope, SHA-256.
- **Nenhum achado deste laudo se apoia em documento sem evidência executável.** Score paramétrico/perceptual não foi usado como critério de qualidade acústica. **SNR não foi calculado** — inexiste voz limpa isolada de referência (o bruto é ambiente + fala sobrepostos; qualquer ganho de SNR seria espúrio).

#### 3. Custódia e integridade de identidade

| Alvo | Bytes | `mtime` | SHA-256 | Estado |
| :--- | ---: | :--- | :--- | :--- |
| Master 1080p30 (alvo) | 441.331.240 | 11/11 23:14:53 | `788BB5B8…D4683` (2 leituras + re-hash final, estável) | **ÍNTEGRO — MATCH exato do esperado** |
| Bruto `20260823_203211.mp4` | 308.052.637 | 22/10 08:34 | `772FC29B…873E` | **ÍNTEGRO** (hash do contrato) |
| Bruto `20260823_203326.mp4` | 2.065.006.193 | 20/10 23:10 | `ECB30903…E7127` | **ÍNTEGRO** (hash do contrato) |
| Vinheta `Intro-Dr-Gestao.mp4` | 3.154.271 | 23/10 00:07 | `47884F4C…4939` | **ÍNTEGRO** |
| **EDL `edl_longo.json` (normativa)** | 253.821 | **12/11 00:07:24** | `2942010BAACA2B71A67B4BB9E11CC92B9CF00F18E2DFDF534615E4EDE315A682` | **REGENERADA DURANTE A AUDITORIA — ver D1** |

- Container: **`ftyp`@4, `moov`@36, `mdat`@371.111** → **faststart confirmado** (o `mdat` @371.111 declarado no relatório do Forge foi confirmado byte a byte).
- Integridade do bloco: **zero arquivos de 0 bytes** em `EXP-BLOCO-LONGO-VIRAL` (os artefatos residuais do blackout foram sanados); `render_master_1080p30.log` saiu de 0 para **3.480 B**; `render_manifest.json` reescrito às **23:15:21**, coerente com o master (hash, tamanho, loudness, `events: 31`).

#### 4. Matriz consolidada de conformidade (18/18 PASS)

| ID | Critério | Exigência | Medição Instrumental Real | Veredito |
| :--- | :--- | :--- | :--- | :---: |
| **F1** | Hash e tamanho | `788bb5b8…d4683` / 441.331.240 B | SHA-256 idêntico em 3 leituras; tamanho exato | **PASS** |
| **F2** | Integridade do container / faststart | `moov` no início | `ftyp`@4, `moov`@36, `mdat`@371.111 | **PASS** |
| **F3** | Resolução e formato | 1920×1080, `yuv420p` | 1920×1080, `yuv420p` | **PASS** |
| **F4** | Perfil de cor / entrelaçamento | bt709, progressivo | primaries/transfer/space = bt709; `field_order=progressive` | **PASS** |
| **F5** | CFR real | 30/1 constante | **8.781/8.781 deltas de PTS = 1/30 s exatos**; sem salto, sem duplicata | **PASS** |
| **F6** | Contagem de frames e duração | 8.782 frames / 292,733 s | `nb_read_frames=8782`; `duration=292,733000`; 13 mil e 722 quadros AAC × 1024 amostras = 292,736 s | **PASS** |
| **F7** | Decodificação integral | zero erro | **0 linhas de warning/error** na decodificação completa de ambos os streams | **PASS** |
| **F8** | Áudio | AAC LC 2ch 48 kHz 251 kbps | `aac` LC, 2 canais, 48.000 Hz, **251.352 bps** | **PASS** |
| **F9** | Loudness integrado | −14,1 LUFS | `ebur128`: **I = −14,1 LUFS** (thr −24,4); `loudnorm`: `input_i = −14,08` | **PASS** |
| **F10** | True Peak real | ≤ −1,0 dBTP | **PCM 192 kHz: −1,0200 dBTP**; `ebur128` −1,0; `loudnorm input_tp = −1,02` | **PASS** (ressalva D6) |
| **F11** | LRA | 2,1 LU | `ebur128`: **LRA = 2,1 LU**; `loudnorm input_lra = 2,10` | **PASS** |
| **F12** | Integridade do sinal | sem NaN/Inf/clipping | `astats`: **0 NaN, 0 Inf, 0 denormais, 0 amostras ≥0,99, Peak count 2**; PCM: 0 NaN/Inf; **RMS −17,6909 dBFS** | **PASS** |
| **F13** | Ausência de tela preta | nenhum segmento preto | `blackdetect d=0,2s`: **0 segmentos**; varredura `signalstats` YAVG de **8.782 frames**: **mínimo 62,713** (t=283,000 s), **0 frames <48**; janela 127–292 s: 4.951 frames, YAVG mín 62,713 | **PASS — REFUTA o defeito de 165 s** |
| **F14** | Sincronia A/V | sem desvio acumulado | Varredura exaustiva **31/31 eventos, 62 sondas** (Aditivo 1): lag medido master-vs-fonte **+0,000 ms** em todas as sondas, correlação **≥ 0,9996**; desvio frente ao eixo exato da EDL na faixa **−12,000 a +16,667 ms**, **zero** sondas acima de meio frame. Nos 4 eventos da tabela do Forge: **+14,667 / −12,000 / −5,333 / −2,000 ms** = `round(out_in×30)/30 − out_in`, erro 0,000 ms | **PASS** |
| **F15** | Motion graphics — overlays de fala | 4,95–9,75 s e 15,70–18,25 s | Correspondência pixel-a-pixel sob máscara alfa: `speech_vendas` **MAE 2,82** dentro vs **104,55** fora (37,1×, 124/124 frames, opaco 5,25–9,45 s); `hook_vendas` **MAE 2,71** vs **90,63** (33,4×, 56/56, opaco 16,00–17,95 s) | **PASS** |
| **F16** | Motion graphics — logos | 117,927–127,30 s | MAE na caixa 96×96 durante a presença: **1 / 3 / 5 / 0** (tiktok/shopee/mercado-livre/shein) vs **229 / 77 / 127 / 78** no fundo; revelação na ordem declarada; todos encerram em **127,30 s** | **PASS** |
| **F17** | Motion graphics — wipes | 28,35–29,25 s e 36,25–37,15 s | Os **3 maiores picos** de delta frame-a-frame do programa inteiro estão nas janelas de wipe: 28,600 s (**9,2×** mediana), 29,167 s (**33,7×**), 36,467 s (**19,7×**); **nenhum coincide com fronteira de evento** | **PASS** |
| **F18** | Ganho da vinheta e alinhamento das fontes limpas | −4,5 dB; lag ≈0 | Ganho da vinheta **−4,527 dB** (mediana −4,523, σ 0,023) vs −4,5 declarado, alinhamento −0,021 ms, janela 28,8667 s; `intro_cleaned` **−14,4 LUFS** (TP −1,8 / LRA 2,3) e `body_cleaned` **−14,0 LUFS** (TP −1,0 / LRA 1,9); alinhamento aos brutos por envelope 10 ms: **lag 0,000 ms**, correlação **0,9522 / 0,9411** | **PASS** |

#### 5. Ressalvas e achados (D1 a D10)

**D1 — Drift da EDL / não-reprodutibilidade do artefato. SEVERIDADE ALTA. BLOQUEIO DE PROMOÇÃO.**
- A EDL normativa foi **regenerada em 12/11/2026 00:07:24**, **durante a janela de auditoria**: SHA-256 `2942010BAACA2B71A67B4BB9E11CC92B9CF00F18E2DFDF534615E4EDE315A682`, **30 eventos**, `final_duration = 288,842 s`. O master (23:14:53) materializa a **EDL anterior: 31 eventos / 292,732 s** (o `render_manifest.json` ainda declara `events: 31`).
- **Prova empírica (N1/N2)** — correlação do áudio do master contra `body_cleaned.wav`, âncoras por `src_in`:

  | `src_in` | `out_in` EDL antiga | correlação | `out_in` EDL vigente | correlação |
  | ---: | ---: | ---: | ---: | ---: |
  | 8,945 s | 45,152 s | **0,9996 (±0 ms)** | 41,262 s | 0,0402 |
  | 50,205 s | 85,612 s | **1,0000 (±0 ms)** | 81,722 s | 0,0631 |
  | 101,585 s | 135,272 s | **0,9996 (±0 ms)** | 131,382 s | ~0,05 |
  | 252,935 s | 279,202 s | **1,0000 (±0 ms)** | 275,312 s | ~0,07 |

- Consequência corroborada: o evento da vinheta migrou de `out 28,850→36,717` (EDL antiga, **materializada pelo master**) para `out 24,960→32,827` (EDL vigente) — coerente com a posição dos wipes medida no master.
- **Ação exigida:** re-renderizar a partir da EDL vigente **ou** restaurar/pinizar a EDL de 31 eventos com hash no manifesto; registrar no manifesto o SHA-256 da EDL e dos insumos.

**D2 — Sobrescrita in-place do master durante a janela de auditoria. SEVERIDADE MÉDIA.**
- O mesmo caminho foi gravado por **3 gerações**: 22:53:33 (181.659.336 B, `2dab0c98…`, **defeituosa com 165 s de preto**), 23:00:19–23:14:53 (441.331.240 B, `788bb5b8…`, auditada) e a posterior regeneração da EDL. A geração defeituosa foi **destruída** — não há registro imutável de gerações.
- **Ação exigida:** versionar saídas com sufixo de geração + hash no nome, ou manter registro de artefatos; nunca sobrescrever o mesmo caminho de entrega.

**D3 — Campo `realtime_factor` com semântica invertida (violação da ADR-05). SEVERIDADE MÉDIA.**
- **Código (N1):** `03_render_master_1080p30.py` L563 → `"realtime_factor": round(built["duration"] / elapsed, 3)` = 292,733 / 874,074 = **0,335**, que é `playback_speed_factor`. A ADR-05 fixa `real_time_factor = T_processamento / T_mídia`.
- **RTF real = 874,074 / 292,733 = 2,986** (≈ **2,99× mais lento que o tempo real**). O valor 0,335 no manifesto será lido como render 3× mais rápido que o tempo real — leitura invertida.
- **Ação exigida:** renomear para `playback_speed_factor` e adicionar `real_time_factor: 2.986`.

**D4 — Ausência de hash-pinning das entradas no manifesto. SEVERIDADE MÉDIA.**
- `render_manifest.json` fixa **apenas a saída** (SHA-256, tamanho). EDL, WAVs limpos, brutos, overlays, logos e wipe **não são pinados** — exatamente por isso o drift de D1 é invisível ao manifesto.
- **Ação exigida:** bloco `inputs` no manifesto com `path`, `sha256` e `bytes` de cada insumo, incluindo `source_edl_sha256`.

**D5 — Entrega 1080p30 ≠ `target_format` do contrato. SEVERIDADE BAIXA-MÉDIA (qualificação).**
- O contrato (`CONTRATO_DADOS_EDL_E_CLIPS.md` L25-27) fixa `target_format` **3840×2160 @ 60000/1001**. A ordem de serviço pediu 1080p30, logo há conformidade com o pedido, mas o artefato é **derivado/proxy** (Lanczos 4K→1080p), **não master 4K**. Deve ser rotulado como derivado no manifesto e no registro de promoção (coerente com R23).

**D6 — Margem de True Peak de apenas 0,02 dB. SEVERIDADE BAIXA (técnica) / ALTA (operação).**
- Medido **−1,0200 dBTP** contra o teto de **−1,0 dBTP** → folga de **0,0200 dB**. Qualquer reprocessamento, re-mux ou mudança de encoder pode violar o teto; um alvo de entrega com 0,02 dB de folga não é seguro em produção. **Ação:** re-render com alvo de −1,5 dBTP ou limite de TP no pipeline.

**D7 — Telemetria materializada só ao fim do processo e `verify()` não barra loudness fora da spec. SEVERIDADE MÉDIA.**
- **Código (N1):** o log do FFmpeg é escrito nas **L523-524**, *depois* do retorno do subprocesso; `log()` (**L89-96**) apenas imprime em `stdout`. Em execução interrompida, `render_master_1080p30.log` fica vazio e o `.ffmpeg.log` nem existe.
- `verify()` (**L363-423**) valida geometria/codecs/duração/decodificação e o guard de luma, mas **não** valida loudness: `loudness()` (**L540**) é informativo e não impede o `return 0` (**L578**). **Um master fora da spec de LUFS/TP/LRA é entregue como sucesso.**
- **Ação exigida:** tee do stderr do FFmpeg para disco em tempo real; `verify()` deve reprovar (exit ≠ 0) quando `ebur128` I/TP/LRA saírem da tolerância.

**D8 — Guard anti-tela-preta com amostragem insuficiente. SEVERIDADE MÉDIA.**
- **Código (N1):** `verify()` **L404** amostra **5 pontos** (2 %, 25 %, 50 %, 75 %, 97 %) e **L413** só reprova com **YAVG < 10**. Uma cauda preta de 165 s **pode não ser amostrada** — foi exatamente assim que a geração defeituosa passou.
- **Instrumento correto (N2):** varredura de **todos os 8.782 frames** com `signalstats` + `blackdetect d=0,2s` + critério de maior sequência contígua escura. Medido: YAVG mín 62,713, 0 frames abaixo de 48, 0 segmentos pretos.
- **Ação exigida:** substituir as 5 amostras por varredura completa + limite de sequência escura contígua (ex.: > 0,5 s).

**D9 — Granularidade intrínseca do AAC LC (informativo).**
- O stream de áudio carrega **13.722 quadros de 1024 amostras = 21,333 ms cada** (13.722 × 1024 / 48.000 = 292,736 s ≈ duração do master). A resolução de qualquer análise por pacote de áudio é, portanto, **21,333 ms**; medições de deslocamento abaixo disso exigem o domínio PCM — como foi feito nesta auditoria (PCM a 192 kHz e correlação sobre janelas de 2,5 a 5 s).

**D10 — Reprodutibilidade condicionada ao ambiente de encode (informativo).**
- A re-renderização **não foi reexecutada** pelo auditor (o render sobrescreve o alvo in-place — vedado em auditoria somente-leitura). A bit-exatidão do x264 depende do **número de threads** e da build; o FFmpeg disponível (7.1 gyan.dev) **não possui `soxr`** (o resampler `soxr` é indisponível nesta build), logo o caminho de reamostragem é o `swr` padrão e **não é bit-reprodutível** contra builds com `soxr`. Qualquer afirmação de reprodutibilidade deve registrar build, threads e motor de resampler.

#### 6. Observação residual sobre telemetria do FFmpeg

O log real (`logs/master_longo_16x9_1080p30_motion.ffmpeg.log`) encerra em `frame= 8782 … Lsize= 430988KiB … dup=0 drop=28 speed=0.335x` (430988 KiB = 441.331.712 B; os 472 B de diferença são os átomos de container fora do payload muxido — coerente). O campo `drop=28` **não indica lacuna na saída**, provado pela varredura independente de PTS (8.781 deltas uniformes de 1/30 s, F5); o significado exato do campo não foi isolado por reexecução. `speed=0.335x` é o mesmo valor de semântica invertida de D3.

#### 7. Conclusão e condições de liberação

> **Laudo: APROVADO COM RESSALVAS.**
> **1)** O artefato de 441.331.240 B / `788BB5B8…D4683` cumpre integralmente a especificação contratada da ordem de serviço (18/18 critérios), tem decodificação limpa, CFR exato, loudness e True Peak conformes, **não contém os 165 s de preto alegados** e apresenta motion graphics presentes nas janelas declaradas.
> **2)** **Ressalvas bloqueantes para promoção: D1** (EDL regenerada — artefato não reprodutível a partir da fonte normativa vigente), **D2** (sobrescrita in-place, geração defeituosa destruída) e **D4** (entradas não pinadas no manifesto). Saneamento obrigatório e reemissão do laudo antes de qualquer promoção.
> **3)** Ressalvas não bloqueantes a sanear: **D3** (nomenclatura de RTF conforme ADR-05), **D5** (rotular como derivado/proxy 1080p30), **D6** (margem de TP de 0,02 dB), **D7** (telemetria tardia + `verify()` sem gate de loudness), **D8** (guard de preto amostral).
> **4)** **Produção e Sandbox permanecem intocadas.** Nenhuma promoção autônoma foi executada; os brutos (`772FC29B…873E`, `ECB30903…E7127`) e a vinheta (`47884F4C…4939`) foram verificados **íntegros** ao final da auditoria.

---

### Aditivo 1 ao Laudo — Cobertura Exaustiva de Sincronia e Respostas às Pendências do Gatekeeper (Axiom) — Data: 2026-11-12

**Origem:** Zenith, parecer de gatekeeping do master longo 1080p30 (12/11/2026 07:00:15), que ratificou o mérito técnico, **negou a homologação para promoção** e abriu 3 pendências de retorno: (1) concatenação do SHA-256; (2) cobertura de sincronia — se os 27 eventos restantes foram **medidos** ou apenas inferidos pela regra de quantização; (3) confirmação do teto de True Peak contratado.

**Resposta 1 — SHA-256.** Os dois grupos separados por espaço no Bloco 1 concatenam no hash de 64 caracteres `788BB5B85B5882A13F4D61FB8F609DE9F03E8A5BF1A16C3755F9AF29D22D4683`, **idêntico ao hash esperado pelo Forge**. A separação foi exclusivamente uma proteção do canal IPC (padrão numérico que trunca o transporte); **neste registro canônico o hash está escrito de forma contígua e integral**, ver seção 3.

**Resposta 2 — Cobertura de sincronia: MEDIDA, não inferida.**
- **Fonte N1 recuperada:** [`logs/_filter_graph_tmp.txt`](file:///D:/Drifit/Experimentos_Sandbox/EXP-BLOCO-LONGO-VIRAL/05_render_longo_1080p_motion/logs/_filter_graph_tmp.txt) (`mtime` **11/11/2026 23:00:19**, 16.969 B) — o filtergraph exato do render auditado, que materializa os **31 segmentos** com `trim`/`atrim` de origem e duração quantizada. A linha do tempo materializada foi reconstruída a partir dele, sem depender da EDL regenerada.
- **Medição N2:** correlação cruzada do áudio do master contra a fonte de cada segmento (2 sondas por evento, janela de 3,0 s, busca de ±50 ms), com `intro_cleaned.wav`, `body_cleaned.wav` e o áudio da vinheta.

| Métrica da varredura exaustiva | Resultado |
| :--- | :--- |
| Eventos cobertos | **31 de 31** (62 sondas) |
| Lag medido master-vs-fonte | **+0,000 ms** em todas as sondas (máx. \|0,000\| ms) |
| Correlação | mínima **0,9996**, média **1,0000** |
| Desvio do conteúdo frente ao eixo **exato** da EDL | média **+2,011 ms**, faixa **−12,000 a +16,667 ms** |
| Sondas acima de meio frame (16,667 ms) | **0 de 62** |
| Soma das durações quantizadas | **292,733334 s = 8.782 frames exatos** (EDL exata: 292,732 s; diferença total +0,001334 s) |

- **Correção factual (qualifica a tabela do Forge):** o pior desvio real do programa **não é 14,67 ms**, e sim **+16,667 ms** (evento 8 — vinheta; evento 9 com +16,334 ms). O valor de 14,67 ms declarado pelo Forge é correto, porém foi apurado apenas nos 4 eventos da tabela dele. O valor maior permanece **dentro** do limite de meio frame que o próprio Forge declarou aceitar, portanto **não altera o veredito** — apenas qualifica a afirmação de pior desvio.

**Resposta 3 — Teto de True Peak.** O contrato de dados ([`CONTRATO_DADOS_EDL_E_CLIPS.md`](file:///D:/Drifit/Experimentos_Sandbox/EXP-BLOCO-LONGO-VIRAL/00_docs/CONTRATO_DADOS_EDL_E_CLIPS.md), L25-29) **não fixa teto de True Peak**: define apenas `target_format` 3840×2160 @ 60000/1001, `audio_sample_rate` 48000 e `audio_channels` 2. O teto de **−1,0 dBTP** provém de duas referências: (a) **ADR-05 / REAUDITORIA-03, critério C6** (TP ≤ −1,0 dBTP) e (b) a **ordem de serviço do Forge**, que declara TP −1,0 dBFS como valor de especificação. Medido: **−1,0200 dBTP** sobre PCM a 192 kHz — **conforme frente às duas referências**, com folga de **0,0200 dB**, que é exatamente a ressalva **D6**.

**Efeito sobre o laudo:** **nenhum**. Veredito mantido — **APROVADO COM RESSALVAS** no mérito técnico; **promoção NEGADA** pelo gatekeeper, com bloqueio por **D1, D2 e D4**; sanear D3, D5, D6, D7 e D8.

---

### Aditivo 2 ao Laudo — Registro do Gatekeeper e Encerramento do Ciclo de Auditoria (Axiom) — Data: 2026-11-12

**Gatekeeper:** Zenith (Homologação & Gatekeeper) | **Protocolo:** Master longo 16x9 1080p30 (Axiom → Zenith), blocos 1 a 3 + resposta às pendências.

#### Registro final do gate (Zenith, 12/11/2026 07:22:38)
> **MÉRITO TÉCNICO: APROVADO COM RESSALVAS.**
> **PROMOÇÃO: NEGADA. BLOQUEIOS D1, D2 e D4 ATIVOS.**
> **RESSALVAS A SANEAR: D3, D5, D6, D7 e D8.**
> *Nenhuma promoção a `D:\Drifit\Editor\` foi executada ou está autorizada; a promoção depende de aprovação soberana do Proprietário.*

- **Pendências encerradas com evidência N1/N2 de Axiom:** (1) concatenação do SHA-256 — **fechada**; (2) cobertura de sincronia — **fechada**, 31/31 eventos medidos; (3) teto de True Peak — **fechada**, PASS formal com D6 mantida; (4) critério de meio frame — **fechada**, inclusivo `|desvio| ≤ 16,667 ms`.
- **Correção factual averbada pelo gate:** o pior desvio do programa é **+16,667 ms** (evento 8 — vinheta; evento 9 com +16,334 ms), e não os 14,67 ms da tabela do Forge, que cobria apenas 4 eventos. O valor permanece dentro do limite de meio frame, de modo que **o veredito não muda**.
- **Distinção averbada:** o desvio de até 16,667 ms é o **snap do ponto de corte à grade de frames** (escolha de montagem declarada pelo Forge); o **desincronismo A/V real medido no master é 0,000 ms** nas 62 sondas dos 31 eventos.

#### Lacuna documental apontada pelo gate (encaminhada à deliberação soberana)
O contrato de dados ([`CONTRATO_DADOS_EDL_E_CLIPS.md`](file:///D:/Drifit/Experimentos_Sandbox/EXP-BLOCO-LONGO-VIRAL/00_docs/CONTRATO_DADOS_EDL_E_CLIPS.md), L25-29) **não define loudness, True Peak nem LRA** — fixa apenas `target_format`, `audio_sample_rate` e `audio_channels`. O teto de −1,0 dBTP e a faixa de −14 LUFS existem hoje apenas na ADR-05/REAUDITORIA-03 (critério C6) e na ordem de serviço. **Recomendação do gate:** incorporar esses limites ao contrato. Registrada como item de saneamento documental no Aditivo 1, sob deliberação do Proprietário.

#### Encerramento do ciclo de auditoria
- **Veredito de Axiom:** `APROVADO COM RESSALVAS` (mérito técnico) — **18/18 critérios PASS**, defeito de 165 s de tela preta **refutado**, cobertura de sincronia **31/31 eventos medidos**.
- **Veredito de Zenith:** mérito **aprovado com ressalvas**, **promoção negada**, bloqueios **D1, D2 e D4** ativos.
- **Pendência soberana remanescente:** decisão do **Maestro/Proprietário** sobre o re-render — opção (a) re-render a partir da EDL vigente, ou opção (b) restaurar e pinar a EDL antiga de 31 eventos — sempre com **saída versionada por hash** e **manifesto com inputs pinados**.
- **Custódia ao encerrar:** master e os três brutos **íntegros** (hashes conferidos); **produção e sandbox intocadas**; **nenhuma promoção executada**.
- **Estado factual da pasta oficial no encerramento (correção do registro):** `D:\Drifit\Editor\renders\` **não está mais vazia** — contém **2 arquivos**, ambos de módulos **anteriores** a esta auditoria e **promovidos antes da janela de auditoria** (início em 11/11 23:17): `short_vendas_master_broadcast_9x16.mp4` (25.381.286 B, `mtime` 11/11 16:06:15, SHA-256 `83EE4B74…0149` — versão 3 homologada na REAUDITORIA-03, autorizada pelo Proprietário às 16:05) e `short_vendas_motion_master_9x16.mp4` (24.742.469 B, `mtime` 11/11 18:15:32, SHA-256 `F7E79C2F…2710` — artefato MOD-09). **O master longo 16:9 1080p30 auditado NÃO foi promovido**, coerente com a negação de promoção do gate. A afirmação de C16 no item 7.2 anterior deste documento (`renders` oficiais vazios, 0 arquivos) refere-se ao marco temporal da REAUDITORIA-03 e **não reflete o estado atual da pasta**.

---

### Aditivo 3 ao Laudo — Disposição dos Achados pelo Forge e Reconstrução do Eixo Temporal da EDL v1.0 (Axiom) — Data: 2026-11-13

#### 1. Disposição dos achados (Forge, 13/11/2026)
| Achado | Responsável | Destinação declarada pelo Forge |
| :--- | :--- | :--- |
| **D3, D4, D6, D7, D8** | Forge | Próximo render do piloto: `real_time_factor` = `elapsed/duration` separado de `playback_speed_factor`; bloco `inputs` com `sha256`+`bytes` (EDL, fontes, assets); TP alvo −1,5 dBTP; tee de stderr e gate de loudness com saída ≠ 0; varredura integral de luma/`blackdetect` como gate. |
| **D1, D2** | Maestro/Proprietário | Decisão de re-render do master longo (EDL vigente ou EDL antiga pinada). |
| **D5** | Forge | Rótulo de derivado/proxy 1080p30. |
| **D9, D10** | Informativos | Registrados, sem ação. |

> **Nota de auditoria sobre o alcance das correções:** D3, D4, D7 e D8 são **defeitos do renderizador compartilhado**, não do piloto isolado. Para que o re-render do master longo (decisão soberana de D1) **não reproduza os mesmos achados**, as correções precisam ser aplicadas no **módulo de render comum** — e não apenas no caminho do piloto. Esta é a condição para que a re-homologação do master longo seja proponível.

#### 2. Reconstrução do eixo temporal da EDL v1.0 (31 eventos) — desbloqueio da opção (b)
O JSON original da EDL de 31 eventos foi destruído pela regeneração de 12/11 00:07:24 (achado D1). O **eixo temporal** foi reconstruído a partir do **artefato N1 do próprio render auditado** — o filtergraph [`logs/_filter_graph_tmp.txt`](file:///D:/Drifit/Experimentos_Sandbox/EXP-BLOCO-LONGO-VIRAL/05_render_longo_1080p_motion/logs/_filter_graph_tmp.txt) (`mtime` 11/11 23:00:19, SHA-256 `C336BF35414A0038CA8478BBDB7EFB353D2427011D1738FABA7323A2C83D6D0B`), que preserva os 31 segmentos com `atrim` de origem e duração quantizada.

- **Artefatos entregues** (pasta nova, **sem tocar** na EDL normativa `edl_longo.json`):
  - [`edl_v1_0_31eventos_eixo_temporal_reconstruido.json`](file:///D:/Drifit/Experimentos_Sandbox/EXP-BLOCO-LONGO-VIRAL/02_decupagem_edl/_reconstrucao_auditoria_axiom/edl_v1_0_31eventos_eixo_temporal_reconstruido.json) — SHA-256 `35D9E8D22E5FB11D083D80C1D27F5A88BCA6191F8202627821820C3555418324`
  - [`PROVENIENCIA_E_METODO.md`](file:///D:/Drifit/Experimentos_Sandbox/EXP-BLOCO-LONGO-VIRAL/02_decupagem_edl/_reconstrucao_auditoria_axiom/PROVENIENCIA_E_METODO.md) — SHA-256 `B99B7C75726D655C9CA676D0592CACFA3803B8F5779B9F2DCC46CA0E1D2FA80D`
  - [`sha256sums.txt`](file:///D:/Drifit/Experimentos_Sandbox/EXP-BLOCO-LONGO-VIRAL/02_decupagem_edl/_reconstrucao_auditoria_axiom/sha256sums.txt) — SHA-256 `0E98672A89666311A89AAC603C92ED6D3C5676DF53CD8FEAF62BA60F20413A94`
- **Estrutura reconstruída:** 31 eventos, duração final **292,732000 s**, eixo de origem **292,732000 s** (INTRO 28,850 s + VINHETA 7,867 s + CORPO 256,015 s); soma das durações quantizadas **292,733334 s = 8.782 frames exatos**.
- **Validação empírica (N2):**

  | Teste | Posição do master | Resultado |
  | :--- | :--- | :--- |
  | **A — materializada** | grade de frames do render | correlação mín. **0,9994**, média **1,0000**; lag residual **0,000 ms** em **31/31** eventos |
  | **B — eixo exato da EDL** | `out_in` reconstruído | lags de **−12,000 a +16,667 ms**, correlação média **0,9924** — coincidem com os offsets de quantização `round(t*30)` |

  **Conclusão: o eixo temporal reconstruído é o mesmo que o master materializa.** A opção (b) — *"EDL antiga restaurada e pinada"* — deixa de estar bloqueada pela perda do JSON.
- **Limitação material declarada:** a reconstrução restaura o **eixo temporal** (`event_id`, `type`, `source_id`, `src_in`, `src_out`, `out_in`, `out_out`, `duration_seconds`, `summary`). **Não** restaura `word_ids`, `word_count`, `text`, `notes`, `silence_removed_before`, `removed_silences`, `word_index`, `sources` e `telemetry` — esses campos não existem no filtergraph. As **âncoras lexicais** (contrato: ancoragem por `word_id`) devem ser **re-derivadas pela etapa 02** a partir de [`clips.json`](file:///D:/Drifit/Experimentos_Sandbox/EXP-BLOCO-LONGO-VIRAL/03_analisador_viral/clips.json) (`mtime` 20/10 20:54:36, SHA-256 `9CF9DA3E57D2A169F9B909C912F345C3F1BDCE77E893B95C2F81533FDC1A819F`).
- **Natureza do artefato:** **reconstrução derivada**, não o arquivo original. Uso restrito a insumo de referência da opção (b), submetido à validação da etapa 02 e do Forge.

#### 3. Protocolo de aceitação N1 para o re-render do master longo (proposto para o re-homologação)
| ID | Critério de aceitação | Verificação instrumental |
| :--- | :--- | :--- |
| **A1** | Custódia de entradas | `render_manifest.json` com `source_edl_sha256` + bloco `inputs` (path, sha256, bytes) de EDL, WAVs limpos, brutos e assets |
| **A2** | D1 encerrado | SHA-256 da EDL vigente no momento da auditoria **idêntico** ao declarado no manifesto |
| **A3** | Linha do tempo correta | Correlação do áudio do master contra `body_cleaned.wav` nos `out_in` da EDL vigente **≥ 0,99** em todos os eventos; e **zero** correspondência na EDL não declarada |
| **A4** | Contagem e duração | `events` do manifesto = contagem da EDL (30 na v1.1.0, 31 na v1.0 pinada); duração final = EDL ± 1 frame |
| **A5** | D8 encerrado | Varredura integral de luma (todos os frames) + `blackdetect`: **zero** segmentos pretos; YAVG mínimo > 48 |
| **A6** | D6 encerrado | `I` = −14,1 ± 0,5 LUFS; **TP ≤ −1,5 dBTP** (novo alvo); LRA ≤ 3 LU |
| **A7** | D3 encerrado | `real_time_factor` = `elapsed/duration` e `playback_speed_factor` = `duration/elapsed`, sem inversão |
| **A8** | D2 encerrado | Saída versionada com hash no nome; **nenhum** caminho de entrega sobrescrito in-place |
| **A9** | D7 encerrado | Log de execução do encoder em disco, persistido **durante** a execução; gate de loudness com saída ≠ 0 |

---

### Aditivo 5 ao Laudo — Auditoria Técnica Instrumental do Entregável Final Multicamada (Axiom) — Data: 2026-11-14

**Auditor:** Axiom (Auditor Técnico Instrumental) · **Alvo:** `master_longo_16x9_1080p30_multicamada.mp4`
**SHA-256 do alvo:** `783D182D8FFC98DCA891D3E84E9A7B928981F1E25DC026F6FB8EFD25CB420D8A` (443.815.722 B)
**Confrontos:** `edl_longo.json` v1.0.0 (30 eventos, 288,842 s) · `editorial_plan.json` v2.0.0 · `logs/master_longo_16x9_1080p30_multicamada.manifest.json`
**Instrumentos (N1):** `verificar_A1_A9.py` (v3) · `auditar_AV.py` · **Metadados (N2):** FFmpeg/FFprobe 7.1, PCM 48 kHz e PCM 192 kHz, `ebur128=peak=true`, `signalstats`, `blackdetect`, SHA-256
**Hierarquia de evidência:** N1 + N2. Nenhuma afirmação deste aditivo se apoia em documento sem evidência executável.
**Sequência:** este é o Aditivo **5**; não há Aditivo 4 neste registro canônico.

> **Parecer-resumo: REPROVADO — 2 bloqueios (A1, A4).** PASS = 6 · PASS COM RESSALVA = 2 · FAIL = 2. Identidade de timeline, sincronia A/V e ausência de frames pretos **comprovadas**; a entrega, porém, **não é reconstituível** a partir do manifesto e está **3 frames curta** em relação à EDL vigente.

#### 1. Custódia do alvo e meios do stream

| Item | Valor medido |
| :--- | :--- |
| Master (canônico) | 443.815.722 B · mtime 14/11/2026 02:39:10 · SHA-256 `783D182D…CB420D8A` — **confere com o hash declarado** |
| Cópia pinada | `renders/_versions/master_longo_16x9_1080p30_multicamada__783d182d8ffc.mp4` (443.815.722 B, hash idêntico) |
| Gerações anteriores preservadas | `__b95e724dd7ba` (443.815.939 B, 02:23:37) · `__abc77846067e` (443.286.735 B, 12/11 01:29:27) |
| Manifesto | 10.709 B · mtime 02:39:56 · SHA-256 `4EE672146112FC3B360EE5F94EB8C8BD…` |
| EDL vigente | 253.821 B · mtime 12/11 00:07:24 · SHA-256 `2942010BAACA2B71…315A682` |
| Plano editorial v2.0.0 | 80.846 B · mtime 14/11 00:13:02 · SHA-256 `9FDCE7D3D9FD6FC7…83C366D` |

**Meios (ffprobe):** H.264 High 1920×1080 `yuv420p`, `color_range=tv`, bt709, 30/1 fps, **8.662 frames**, 288,733333 s · áudio AAC 2ch 48 kHz · **0 erros de decodificação** (`ffmpeg -v error … -f null -`: rc=0, 0 linhas de erro).

> **Nota de janela móvel:** o manifesto foi reescrito durante a janela de auditoria (02:28:40 → 02:39:56) e o master teve o mtime atualizado **com conteúdo idêntico** (hash estável `783D182D…`). Este aditivo refere-se ao hash acima; qualquer re-render posterior exige re-hash.

#### 2. Parecer objetivo por critério (protocolo N1 A1–A9)

| ID | Critério | Veredito | Evência (N2) |
| :--- | :--- | :--- | :--- |
| **A1** | Custódia de entradas pinadas por SHA-256 + bytes | **FAIL** | 24 entradas pinadas, **todas conferem**; porém **5 insumos que carregam o programa não estão pinados**: bruto `20260823_203211.mp4`, bruto `20260823_203326.mp4`, vinheta `Intro-Dr-Gestao.mp4`, `intro_cleaned.wav`, `body_cleaned.wav`. O áudio master da mixagem (`_mix_master.wav`, 110.912.092 B) também não é fixado. |
| **A2** | D1 encerrado — EDL vigente = declarada no manifesto | **PASS** | SHA-256 da EDL vigente `2942010B…` = `source_edl_sha256` do manifesto; `source_plan_sha256` `9FDCE7D3…` = plano v2.0.0. |
| **A3** | Master materializa a EDL declarada e **não** a outra | **PASS COM RESSALVA** | **A3-r (identidade de timeline) ATENDIDO:** Pearson em janela cheia, eixo declarado, 30/30 eventos, desvio de materialização **−14,67 a +15,33 ms** (≤ 1 frame); EDL não declarada (31 eventos reconstruída) **média 0,2394** → não casa. **A3-t (pureza da mixagem) NÃO ATENDIDO:** 24/30 eventos com corr ≥ 0,99; 6 eventos em 0,9351–0,9895 — **atribuídos** (ver §3). |
| **A4** | Contagem de eventos e duração coerentes com a EDL | **FAIL** | Master **8.662 frames / 288,733333 s**; EDL 288,842 s = 8.665,26 frames. Diferença **3 frames (0,108667 s)** — excede a tolerância de 1 frame. O próprio `staged_run_v3.log` registra "Passe 1/3: medindo loudness do mix completo (**8665 frames**)": o pipeline planejou 8.665 e entregou 8.662. Manifesto internamente inconsistente (`slice` = [0.0, 288,842] × `duration_seconds` = 288,733333 × `staged.frames_totais` = 8.662). `_mix_master.wav` tem 288,833 s (8.665 frames) → o truncamento ocorreu na fase concat/mux. **Efeito:** a cena 2.5D de encerramento (plano: 284,000–288,842 s) é cortada 3 frames antes do fim. |
| **A5** | D8 encerrado — varredura integral de luma, **zero frames pretos** | **PASS** | Varredura de **todos os 8.662 frames** em faixa plena (`scale=480:270:in_range=tv:out_range=pc`): YAVG mín **5,289**; **0 frames abaixo do piso 3,0**; maior sequência abaixo do piso **0,000 s**. Faixa de revisão (< 25,5): 476 frames, maior sequência **7,100 s em 56,600–63,667 s**, dentro da cena 2.5D homologada "alta_minutagem" (55,7–64,7 s, fundo marinho legítimo). `blackdetect`: 1 segmento (56,666667–57,400 s, 0,733333 s) — **mesma cena legítima**. Controles validados na mesma execução: preto 3 s → 0,000 / 3,000 s (**reprova**); cinza 27 → 27,000 / 0,000 s (aprova); marinho 13 → 13,000 / 0,000 s (aprova) e `blackdetect` **acusa** 1 segmento → divergência demonstrada. |
| **A6** | D6 encerrado — loudness e True Peak | **PASS** | `ebur128=peak=true`: **I = −14,0 LUFS**, **TP = −1,9 dBTP**, **LRA = 2,1 LU**. PCM independente a 192 kHz: **TP = −1,8859 dBTP**. Faixas: −14,1 ±0,5 LUFS · teto −1,5 dBTP · LRA ≤ 3. |
| **A7** | D3 encerrado — `real_time_factor` = elapsed/duration, sem inversão | **PASS COM RESSALVA** | Fórmula correta: `real_time_factor` 0,153 = 44,19 / 288,733 ✓; `playback_speed_factor` 6,536 = 288,733 / 44,19 ✓; recíprocos. **Ressalva:** a base `elapsed` cobre **apenas a etapa concat/mux** (segmentos 1–3 reaproveitados; 4º re-encodeu em janela própria). Janela de parede dos logs do encoder (seg_00 01:27:24 → mux 02:27:56) = **4.305,7 s → RTF observado 14,912**: o RTF declarado superestima o desempenho do pipeline em ~97×. |
| **A8** | D2 encerrado — saída versionada, nada sobrescrito in-place | **PASS** | `__783d182d8ffc.mp4` presente em `_versions` com os mesmos 443.815.722 B; `sha256` do manifesto = hash do master; 3 gerações anteriores preservadas. |
| **A9** | D7 encerrado — telemetria do encoder em disco, persistida na execução | **PASS** | Log do concat/mux em disco (6.262 B, mtime 02:27:56 = mtime do master) contendo `frame=` e `Lsize= 433414KiB`; os 4 logs de segmento também em disco com telemetria. |

**Contagem:** PASS = 6 · PASS COM RESSALVA = 2 · FAIL = 2 → **VEREDITO DA ACEITAÇÃO N1: REPROVADO — BLOQUEIO DE HOMOLOGAÇÃO.**

#### 3. Sincronia A/V e materialização

| Medida | Resultado | Critério |
| :--- | :--- | :--- |
| Desvio de materialização do **áudio** (30 eventos, Pearson em janela cheia, eixo declarado) | **−14,67 a +15,33 ms** — ≤ 1 frame em 30/30 | PASS |
| **Não materialização** da EDL não declarada (31 eventos) | média **0,2394** (min 0,0766) | PASS |
| Integridade do **mux** (áudio do master vs `_mix_master.wav`) | Pearson **0,999987**, lag **0,000 ms** (t=100–110 s) e **0,995722**, lag 0,000 ms (cauda) | PASS |
| **Camada gráfica 2,5D** — 9/9 sondas de NCC contra as cenas-fonte | NCC **0,999–1,000**, pico dentro de **±1 frame** (0,0 a +33,3 ms) da janela planejada | PASS |
| Estrutura de cortes do vídeo (YAVG da diferença de quadros) | 23/29 limites de evento com pico dentro de ±0,5 s (desvios −26,7 a +271,3 ms); 268 picos no master | RESSALVA DE MÉTODO |
| Comparação quadro-a-quadro master × fonte bruta (NCC ±0,75 s) | NCC 0,02–0,75, **sem pico estável** | MÉTODO INADEQUADO (zoom + overlays deformam a base; não é evidência de defeito) |

**Atribuição das 6 correlações < 0,99 (perfil de sub-janelas):** o perfil mostra **lag constante** por evento e degradação **localizada** em janelas curtas (0,7678–0,9814), assinatura de transiente somado — não de erro de timeline. **6 das 11 sub-janelas degradadas coincidem com hits da camada 6 (sound design):**

| Evento | Sub-janela degradada | SFX | Alvo |
| :--- | :--- | :--- | :--- |
| 5 | 16,393–16,689 s | `sfx_00g` whoosh_transicao (16,500 s, −5 dB) | `broll_00b_outro_business` |
| 8 | 32,827–33,881 s | `sfx_01` whoosh_abertura (32,910 s, −6 dB) | `lt_oficial_luiz_roberto` |
| 8 | 35,990–37,044 s | `sfx_02` hit_impacto_medio (36,910 s, −4 dB) | `t10_01_29_anos` |
| 18 | 172,519–173,113 s | `sfx_30` hit_impacto_pesado (172,600 s, −3 dB) | `t10_11_vai_ter_taxas` |
| 23 | 212,785–214,646 s | `sfx_40` hit_impacto_medio (214,000 s, −4 dB) | `t10_14_compartilhar` |
| 24 | 229,378–231,187 s | `sfx_43` hit_impacto_medio (230,000 s, −4 dB) | `t10_15_ponto_interrogacao` |

As 5 sub-janelas restantes coincidem com as bordas dos eventos, onde há cross-fade de b-roll/cena. **Conclusão:** a identidade de timeline está comprovada; o limiar estrito de 0,99 pressupõe entrega de camada única e deve ser emendado para entrega multicamada (A3-t).

#### 4. Achados

**Bloqueios**

- **B1 (A1) — Custódia incompleta.** As fontes primárias (brutos 203211/203326), a vinheta e os dois WAVs limpos **não** constam do bloco `inputs` do manifesto, que fixa 24 entradas (todas verificáveis) mas não cobre o material que carrega o programa. O entregável **não é reconstituível** a partir do manifesto. *Correção:* incluir no `inputs` os 3 vídeos-fonte, os 2 WAVs limpos e o áudio master da mixagem, com `path`, `bytes` e `sha256`.
- **B2 (A4) — Entrega 3 frames curta e manifesto inconsistente.** O master entrega 8.662 frames contra os 8.665 da EDL vigente (288,842 s). O truncamento ocorreu na fase concat/mux (o `_mix_master.wav` tem 8.665 frames). O manifesto declara `slice` [0,0; 288,842] e `duration_seconds` 288,733333 na mesma estrutura. *Efeito:* o logo animado de encerramento (cena 2.5D 284,0–288,842 s) não completa. *Correção:* alinhar a grade do mux à EDL (8.665 frames) e fazer o manifesto declarar uma única duração coerente.

**Ressalvas**

- **R1 (A7) — Base do `elapsed` parcial.** `render_seconds` mede apenas concat/mux; o RTF declarado (0,153) e o `playback_speed_factor` (6,536) descrevem essa etapa, não o pipeline (RTF observado pela janela de logs: 14,912). *Correção:* declarar `elapsed_render_seconds` e `elapsed_stage` por etapa, ou medir o wall-clock do processo completo.
- **R2 (A3-t) — Emenda de critério.** O limiar "corr ≥ 0,99 em todos os eventos" foi escrito para render de camada única; em entrega multicamada ele reprova o SFX legítimo. *Correção:* manter o gate de identidade de timeline (≤ 1 frame em 100% dos eventos + não correspondência da EDL não declarada) e tratar a pureza da mixagem como ressalva, com a lista de eventos.
- **R3 — Artefato em escrita durante a auditoria.** Manifesto reescrito às 02:39:56 durante a janela de auditoria; master regravado com conteúdo idêntico. Re-hash final registrado em §6.
- **R4 — Resolução do detector de cortes.** A camada gráfica gera 268 picos de diferença de quadros no master, o que impede resolução de 1 frame na estrutura de cortes do vídeo. A sincronia foi aferida pelo áudio (≤ 1 frame) e pela camada 2,5D (≤ 1 frame), não pelos picos isolados.

#### 5. Correções aplicadas ao instrumento durante esta auditoria (N1)

1. **A3** — a versão anterior media a posição *materializada* pela soma de durações arredondadas (`round(dur·30)/30`), que diverge da grade real do render em ±1 frame (desvio acumulado de 33,3 ms) e produzia correlações de 0,08–0,99. O renderer **quantiza o início acumulado** (`round(out_in·30)/30`); o instrumento passou a sondar o **eixo declarado** com Pearson em janela cheia (sem perda de sobreposição), busca de ±50 ms e inset de 1 frame + 1 ms. Verificado por equivalência contra a força bruta.
2. **A5** — a varredura era feita em faixa **limitada** (preto = 16), onde o piso 10 nunca disparava: o gate **não reprovava preto nenhum**. Passou a medir em faixa plena (`tv→pc`), piso 3,0, sequência tolerada 0,20 s, com controles positivo e negativos executados a cada rodada.
3. **A7** — a premissa "RTF ≥ 1,0" foi removida: render estagiado com encoder AMF pode ser mais rápido que o tempo real; o critério passa a verificar fórmula, reciprocidade e a base do `elapsed` contra os logs em disco.
4. **A8** — comparação do hash passou a ser *case-insensitive* (o nome do arquivo pinado é minúsculo; o hash é maiúsculo) — a versão anterior reportava falsamente ausência de cópia pinada.
5. **A1** — passa a exigir que cada insumo obrigatório (EDL, WAVs limpos, brutos, assets) esteja **de fato** no bloco `inputs`, e não apenas que as entradas listadas conferem.
6. **A6** — True Peak PCM exibido arredondado (4 casas).

#### 6. Re-hash final de custódia (14/11/2026, encerramento da auditoria)

| Arquivo | Bytes | mtime | SHA-256 |
| :--- | ---: | :--- | :--- |
| `renders/master_longo_16x9_1080p30_multicamada.mp4` | 443.815.722 | 14/11 02:39:10 | `783D182D8FFC98DCA891D3E84E9A7B928981F1E25DC026F6FB8EFD25CB420D8A` |
| `renders/_versions/…__783d182d8ffc.mp4` | 443.815.722 | 14/11 02:27:56 | `783D182D8FFC98DCA891D3E84E9A7B928981F1E25DC026F6FB8EFD25CB420D8A` |
| `logs/master_longo_16x9_1080p30_multicamada.manifest.json` | 10.709 | 14/11 02:39:56 | `4EE672146112FC3B360EE5F94EB8C8BD76CA75FA79CC71DF82AAB388CE443B50` |
| `02_decupagem_edl/edl_longo.json` | 253.821 | 12/11 00:07:24 | `2942010BAACA2B71A67B4BB9E11CC92B9CF00F18E2DFDF534615E4EDE315A682` |
| `05_render_longo_1080p_motion/editorial_plan.json` | 80.846 | 14/11 00:13:02 | `9FDCE7D3D9FD6FC79E2DA771ED2CC2ECE945D35EA358DD0261A04D4DD83C366D` |
| `D:\Drifit\Editor\20260823_203211.mp4` (bruto SRC_INTRO) | 308.052.637 | 22/10 08:34:00 | `772FC29B30012BF0AE2FB9263FA5A119EF4F6EF043D610553848D31CD7CC873E` |
| `D:\Drifit\Editor\20260823_203326.mp4` (bruto SRC_CORPO) | 2.065.006.193 | 20/10 23:10:55 | `ECB30903F72F38B06C55407DB784E27937C83B9F004D3D5A7F7CAFFD0DEE7127` |
| `…\vinhetas\Intro-Dr-Gestao.mp4` (SRC_VINHETA) | 3.154.271 | 23/10 00:07:58 | `47884F4CB657EB686945EDC0401FB7A98F5031D8CFC172E7FD620186FA264939` |
| `05_render_longo_1080p_motion/audio/intro_cleaned.wav` | 7.700.558 | 11/11 22:09:04 | `893132AE5937D9A3CF899330FBE8A9FAD4F65663748AA3B7BC6E087349C4B325` |
| `05_render_longo_1080p_motion/audio/body_cleaned.wav` | 51.585.102 | 11/11 22:09:20 | `29C325A063AFA3CC192FB467B21A6130402B26DD51F7E96A9AFD92319978BE29` |
| `05_render_longo_1080p_motion/logs/_mix_master.wav` | 110.912.092 | 14/11 02:38:50 | `D5CB026300838EED101C4A1C1DE6EAB6D06C5ECA36390869EDEE304D75379225` |

**Artefatos de auditoria (N1):** `verificar_A1_A9.py` 29.947 B `1BDB88C42C3EBA8983ED473CCA078E501CF2983D2CE64BD8881B04B0E6998FCF` · `auditar_AV.py` 10.845 B `A0340067A9CA17F21E1F30DBBF53430FF0922D7253E597A15245A5E7F986915D` · `A1_A9_RESULTADO.json` 7.235 B `7BF12CB48B63ED2AD1E9DAA9C3598E0A34E965F6853BB5BE3FA519E3A0C7ABC7` · `AUDITORIA_AV.json` 14.427 B `2CC7644EF75EE9AEA717EF5AAB43E92D945D80F192CCD4CDA71DA795172FD251` · `PARECER_MASTER_MULTICAMADA_783d182d.md` 13.763 B `A2E32CEB62CFDDBECD716D41E0F049EE8994629F096972ADD3DACB2C23516211`.

**Conclusão de custódia:** as três fontes primárias e a vinheta seguem **íntegras** (hashes idênticos aos do fechamento do ciclo anterior); o master e sua cópia pinada são **bit a bit idênticos**. **Produção e Sandbox permanecem intocadas; nenhuma promoção foi executada.**

#### 7. Conclusão

O entregável final multicamada **supera** o master motion auditado em todos os achados que lhe eram aplicáveis: D1 (A2), D3 (A7, com ressalva de base), D6 (A6), D7 (A9) e D8 (A5) estão encerrados com evidência instrumental; a **identidade de timeline está comprovada** (áudio ≤ 1 frame em 30/30 eventos, mux com Pearson 0,999987, camada 2,5D com NCC ≈ 1,000 dentro de ±1 frame) e **não há um único frame preto** no master (0 frames abaixo de YAVG 3,0; a faixa escura de 7,1 s é a cena 2,5D homologada, e o `blackdetect` acusa justamente essa cena legítima — divergência confirmada empiricamente no master, não só no piloto).

**Pendências objetivas para a re-homologação: B1 (custódia) e B2 (3 frames + manifesto inconsistente).** Nenhuma promoção foi executada; produção intocada.

---

# 7. HOMOLOGAÇÃO DO MOTION GRAPHICS 9:16 E VERIFICAÇÃO FONÉTICA (ADR-06)

Data: 11/11/2026  
Módulos: `EXP-MOD02-WHISPER-LOCAL`, `EXP-MOD07-DYNAMIC-SUBTITLES`, `EXP-MOD09-MOTION-GRAPHICS`

### 7.1 Suíte de Testes Automatizados Unitários
| Módulo | Arquivo de Teste | Quantidade | Duração | Veredito |
| :--- | :--- | :--- | :--- | :---: |
| **MOD-02-VERIFIER** | `test_phonetic_verifier.py` | 5 testes | 0,002s | **100% PASS** |
| **MOD-07-SUBTITLES** | `test_subtitles.py` | 2 testes | 0,258s | **100% PASS** |
| **MOD-09-MOTION** | `test_motion_graphics.py` | 4 testes | 0,030s | **100% PASS** |

### 7.2 Medição Instrumental do Master Final (`short_vendas_motion_master_9x16.mp4`)
- **Hash SHA-256:** `F7E79C2FF4B8C18CF339C746744C03FC192EC1A43DDF6BC17275F6F0F6032710`
- **Tamanho:** `24.742.469 bytes`
- **Resolução / FPS:** `1080x1920 (9:16)` @ `59,94 fps CFR` (1031 quadros)
- **Integrated Loudness (EBU R128):** **-14,5 LUFS** (Conforme, faixa $-14 \pm 1\text{ LUFS}$)
- **True Peak:** **-6,4 dBTP** (Conforme, teto $\le -1,0\text{ dBTP}$)
- **Loudness Range:** **2,2 LU**
- **Áudio Stream:** AAC LC 48.000 Hz estéreo 192 kbps, multiplexado com cópia direta de áudio (`-c:a copy`).

### 7.3 Verificação Factual de Desobstrução Facial e Separação Espacial (1080x1920)
- **Face de Luiz Roberto Saraiva:** Ocupa $Y = 400\text{px}$ a $980\text{px}$.
- **Legendas Dinâmicas:** Centralizadas na faixa do peito em $Y = 1226\text{px}$ a $1274\text{px}$ (margem de respiro facial de **246px livres** abaixo do queixo).
- **Lower Third Dr. Gestão:** Posicionado em $Y = 1480\text{px}$ a $1610\text{px}$ (margem de separação de **206px livres** abaixo da legenda).
- **Fundo do Card:** Sólido opaco (`#10182a` $\to$ `#080d16`), eliminando artefatos de transparência difusa.

