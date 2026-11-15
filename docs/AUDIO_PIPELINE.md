# ENGENHARIA DO PIPELINE DE ÁUDIO — AUDIO_PIPELINE
## Arquitetura de Restauração Acústica, Modelos Neurais e Governança de Picos

**Classificação do Documento:** `[DECISÃO]` / `[FATO VERIFICADO]` / `[HIPÓTESE]`  
**Data de Emissão:** 08 de novembro de 2026 (Revisão v1.5.2 — Complementação Técnica Final)  
**Status Técnico:** `[EXPERIMENTAL]` / `[EM CALIBRAÇÃO]` (Sem Homologação para Produção)  

---

## 1. Rigor Conceitual: Taxonomia de Processamento de Sinal `[DECISÃO]`

Para evitar imprecisões metodológicas, o pipeline de áudio distingue rigorosamente quatro categorias de intervenção:

1. **Redução de Ruído Estacionário / Subtração Espectral:** Algoritmos determinísticos tradicionais (ex.: `noisereduce`) que calculam a média espectral de um perfil de ruído fixo e o subtraem linearmente do sinal.
2. **Aprimoramento de Fala (*Speech Enhancement*):** Modelos estatísticos ou redes neurais (ex.: DeepFilterNet3) que estimam máscaras espectrais complexas em tempo real, suprimindo componentes não-estacionários e ruídos transitórios.
3. **Separação de Fontes (*Source Separation*):** Redes neurais estruturadas para desmembrar misturas complexas em hastes (*stems*) independentes (ex.: voz versus música).
4. **Normalização de Sonoridade (*Loudness Normalization*):** Ajuste determinístico de ganho e dinâmica para conformidade perceptual com normas e práticas recomendadas (ITU-R BS.1770-5 / EBU R128 / AES71-2018), sem alteração do conteúdo espectral subjacente.

---

## 2. Diferenciação Estrita de Picos, Clipping e Saturação `[FATO VERIFICADO]` `[HIPÓTESE]`

O diagnóstico de artefatos na gravação bruta exige a diferenciação formal de quatro fenômenos físicos e digitais distintos:

1. **Sample Peak (Pico de Amostra, em dBFS):** Mede o valor absoluto mais elevado entre as amostras digitais discretas quantizadas no arquivo PCM. O teto máximo teórico em representação de números inteiros é `0,0 dBFS`.
2. **True Peak Inter-Amostra (em dBTP):** Mede a crista contínua da forma de onda analógica estimada por sobre-amostragem (oversampling de 4× conforme a norma ITU-R BS.1770-5). Picos inter-amostra (*overs*) podem exceder 0,0 dBFS quando amostras discretas adjacentes produzem uma crista analógica interpolada que ultrapassa o limite numérico discreto.
3. **Ausência de Clipping Digital em Full Scale no Arquivo Analisado:** Constatação técnica de que nenhuma amostra digital do arquivo avaliado atingiu o teto numérico de 0,0 dBFS de forma contínua em bloco.
4. **Possibilidade de Clipping ou Saturação em Etapas Anteriores:** Fenômeno em que o sinal foi ceifado digitalmente ou saturado antes de sua codificação em AAC ou antes da extração em PCM.
5. **Saturação Analógica:** Deformação harmônica não-linear ocorrida na cadeia física de captura (cápsula do microfone de lapela, pré-amplificador analógico ou conversor A/D) por sobrecarga de pressão sonora ou ganho excessivo antes da quantização.

### 2.1 Análise Instrumental da Medição de +0,53 dBTP:
- O valor de **+0,53 dBTP** foi registrado na análise integrada de `audio_bruto_parte2.wav` (`input_tp: 0.53 dBTP` em `METRICAS_AUDIOS_BRUTOS.json`) e no segmento bruto da **Amostra A** (`00:00 - 00:20`). As amostras B, C e D brutas registraram picos inter-amostra de +0,25 dBTP, +0,38 dBTP e +0,50 dBTP, respectivamente.
- **Ressalva Metodológica Epistemológica:** A medição posterior à decodificação do sinal comprimido AAC para PCM comprova a existência de *overs* inter-amostra na reconstrução contínua, **mas não identifica, isoladamente, a origem física do pico e não pode ser utilizada como prova de que não ocorreu saturação analógica ou clipping em etapas anteriores da cadeia de gravação/transmissão**. A origem primária do fenômeno (se overshoot de decodificação AAC, se ganho excessivo no transmissor de lapela ou se saturação analógica prévia no conversor A/D) permanece classificada estritamente como `[HIPÓTESE]`.

---

## 3. Estado dos Métodos Tradicionais (`clean_car_audio.py`) `[FATO VERIFICADO]`

### 3.1 Histórico e Reprodutibilidade
- O script original de referência (`clean_car_audio.py`) foi reproduzido de forma determinística na sandbox `EP-TESTE-001`, gerando `audio_baseline_parte1.wav` com hash idêntico ao histórico auditado.
- **Falha Restrita na Parte 2:** A aplicação da janela fixa de ruído `[0.05s - 0.55s]` na Parte 2 comprovou-se inviável porque esse trecho contém fala ativa aos ~0,32s com pico em 0,0 dBFS.

### 3.2 Avaliação das Variantes Tradicionais na Parte 2:
- **Variante A (Perfil Local):** Perfil extraído da pausa veicular límpida em `[187.9s - 188.9s]` (1,0s, RMS -23,86 dBFS).
- **Variante B (Perfil Cruzado):** Perfil extraído da Parte 1 em `[0.05s - 0.55s]` (0,5s, RMS -19,41 dBFS).
- **Variante C (Janela Inicial de 0,25s):** Perfil extraído dos primeiros 250 ms da Parte 2 (`0.00s - 0.25s`, RMS -40,56 dBFS). Por possuir energia muito baixa, não reduziu o ruído de fundo de forma perceptível na audição do usuário.
- **Avaliação do Usuário:** O usuário considerou as variantes tradicionais semelhantes entre si e eficazes na preservação da naturalidade tímbrica da voz, servindo como baseline de referência.

---

## 4. Estado da Restauração Neural com DeepFilterNet3 `[RESULTADO EXPERIMENTAL]`

### 4.1 Comportamento do Modelo e Degradação Vocal
O DeepFilterNet3 (checkpoint `model_120.ckpt.best`, versão 0.5.6) demonstrou alta capacidade de eliminação de ruídos transitórios e ruído de rolamento veicular. Contudo, em seu modo padrão sem limitação de atenuação (`atten_lim_db = None`), o algoritmo introduziu uma pequena alteração tímbrica perceptível na fala, particularmente na Amostra A.

### 4.2 Mecanismo Técnico do Parâmetro `atten_lim_db`:
- No DeepFilterNet, o parâmetro `atten_lim_db` impõe um **teto máximo em decibéis para a atenuação do ganho da máscara espectral complexa**.
- Trata-se de um limitador de ganho na filtragem no domínio da frequência, impedindo que bandas contendo ruído sofram supressão mais profunda que o valor estabelecido.
- **Esclarecimento:** Não se trata de um controle linear de mistura *dry/wet* percentual.

### 4.3 Experimento de Calibração da Fase 2D:
- Foram geradas variantes com limites de atenuação de **6 dB**, **12 dB** e **18 dB** para as quatro amostras.
- **Retorno Auditivo do Usuário:**
  - *Amostras B, C e D:* O usuário avaliou o **DFN3 original (sem limite)** como superior às calibrações de 6, 12 e 18 dB e superior às variantes tradicionais.
  - *Amostra A:* O DFN3 agressivo foi reprovado por degradação perceptível da voz, sendo preferidas as versões moderadas e tradicionais.
- **Conclusão:** O DeepFilterNet3 **não está homologado universalmente**, dependendo de calibração específica ou de segmentação por trecho.

---

## 5. Auditoria de Métricas Objetivas e Esclarecimento de SNR `[FATO VERIFICADO]`

- **Inexistência de Cálculo Formal de SNR:** Esclarece-se formalmente que **não foram calculados valores matemáticos de SNR (Signal-to-Noise Ratio)** nos relatórios das Fases 2C ou 2D. Qualquer citação preexistente a "ganhos de SNR de -13,01 dB, -9,51 dB, etc." é espúria e decorreu de anotações descontextualizadas. O cálculo formal de SNR exigiria um sinal limpo isolado de voz (*clean speech ground-truth*), o que não existe para as gravações veiculares brutas do canal.
- **Métricas Reais Rastreáveis:** Os dados objetivos auditados em `BENCHMARK_DFN3.json`, `RESULTADOS_MODELOS.json` e `MATRIZ_CALIBRACAO_DFN3.csv` restringem-se a:
  - Sonoridade integrada (LUFS via filtro de loudness baseado no algoritmo ITU-R BS.1770; a versão de implementação exata utilizada no filtro FFmpeg do teste histórico é classificada formalmente como `[NÃO VERIFICADO]`, mantendo-se a referência normativa atualizada para ITU-R BS.1770-5);
  - True Peak máximo medido no arquivo inteiro (dBTP via filtro `ebur128`);
  - Loudness Range (LRA, em LU);
  - Peak Level e RMS Level (dBFS via `astats`);
  - Fator de Tempo Real (RTF) e tempo de execução.

---

## 6. Reconciliação Técnica do Flat Factor no `astats` e Proveniência de -3,14 dBTP `[FATO VERIFICADO]`

- **Proveniência Exata do True Peak de -3,14 dBTP:**
  - *Arquivo de Medição:* `tradicional_varC_janela0_25_amostra_B.wav`
  - *Amostra de Origem:* Amostra B (`00m34s_00m55s.wav`, trecho extraído da Parte 2 bruta `20260823_203326.mp4`)
  - *Abordagem e Variante:* Tratamento Tradicional — Variante C (perfil de ruído extraído da janela inicial de 250 ms: `0.00s a 0.25s`, RMS -40,56 dBFS)
  - *Condição do Áudio:* **Arquivo tratado** (o áudio bruto original da Amostra B registrou True Peak de **+0,25 dBTP** em `METRICAS_AUDIOS_BRUTOS.json`)
  - *Relatório de Sustentação:* `RESULTADOS_MODELOS.json` (`metrics_raw.ebur128.input_tp = -3.14 dBTP`) e `MATRIZ_COMPARATIVA_PARTE2.csv`.
- **Definição e Limitações do Flat Factor:** O filtro `astats` do FFmpeg analisa sequências de valores repetidos nos níveis mínimo e máximo do sinal dentro de cada quadro (*frame*). **A métrica de Flat Factor não constitui, isoladamente, um detector ou prova de clipping**.
- **Comportamento do Parâmetro `reset=1`:** O parâmetro `reset=1` reinicia as estatísticas a cada quadro de áudio (*frame*), mas **não determina diretamente a quantidade de amostras por quadro**. A leitura da última linha impressa no stderr pelo script `compute_all_benchmark_metrics.py` capturou as estatísticas do último quadro processado.
- **Evidência Amostral do Quadro Final:** No arquivo tratado `tradicional_varC_janela0_25_amostra_B.wav`, o último quadro avaliado registrou Peak Level de **-47,83 dBFS**, RMS Level de **-55,14 dBFS** e `Flat factor = 4.436975`. A afirmação de que esse quadro final continha exatamente 2.048 amostras (~42 ms a 48 kHz), embora observada em análises de outros arquivos com o mesmo filtro, é classificada formalmente como `[NÃO VERIFICADO]` para este arquivo específico, uma vez que o campo `Number of samples` não foi registrado no objeto `astats` de `RESULTADOS_MODELOS.json`.
- **Versão do FFmpeg no Experimento:** A versão exata do binário FFmpeg executado durante as medições de `EP-TESTE-001` não foi capturada nos relatórios JSON gerados, sendo classificada formalmente como `[NÃO VERIFICADO]` (sem reconstrução por re-execução).
- **Conclusão:** O True Peak máximo medido no arquivo inteiro tratado foi de **-3,14 dBTP** e o Peak Level foi de **-47,83 dBFS**. Constata-se a **ausência de clipping digital em full scale (0,0 dBFS) no arquivo analisado**, corroborando a percepção auditiva limpa do usuário, sem que isso sirva de prova absoluta sobre ausência de saturação em etapas anteriores de captura física.

---

## 7. Governança de Loudness: Padrões Normativos, Plataformas e Perfis `[DECISÃO]` `[PROPOSTO]`

A sonoridade integrada e o True Peak devem ser parametrizados por perfil de distribuição, diferenciando rigorosamente o contexto audiovisual (*sound-with-picture*) do contexto de áudio isolado (*audio-only*), além de distinguir especificações oficiais, recomendações normativas e estimativas empíricas de mercado:

### 7.1 Recomendações Normativas e Práticas Recomendadas
1. **Recomendação AES71-2018 (reafirmada em 2023):** *Recommended Practice for audio loudness of OTT television and online video distribution*. Trata-se da **prática recomendada mais diretamente aplicável ao escopo audiovisual do Projeto Editor**, especificando práticas de gerenciamento de sonoridade para conteúdos audiovisuais (*sound-with-picture*) veiculados pela internet. Constitui prática recomendada (RP), e não um requisito mandatório universal de plataformas.
2. **Recomendação Técnica AES TD1008 e Recomendação AES77-2023:** 
   - **AESTD1008:** *Recommendations for Loudness of Internet Audio Streaming*. Documento Técnico (TD) voltado especificamente para distribuição e streaming de **áudio isolado sem imagem (*audio-only*)**. Serviu de base técnica para a AES77-2023, excluindo expressamente produções audiovisuais (*sound-with-picture*) de seu escopo primário e remetendo esse contexto diretamente à **AES71-2018**.
   - **AES77-2023:** *Recommended Practice for Internet Audio Distribution*. Prática recomendada baseada no AESTD1008 para arquivos de áudio sob demanda e streaming de áudio isolado (*audio-only*, música e podcasts), não substituindo a AES71-2018 para distribuição de vídeos online.
3. **Recomendações EBU (União Europeia de Radiodifusão):**
   - **EBU R128 v5.0:** Recomendação principal de normalização de sonoridade de programas (*program loudness*) para radiodifusão, estabelecendo alvo integrado em **-23,0 LUFS** (±0,5 LU) com True Peak máximo de -1,0 dBTP para televisão e rádio.
   - **EBU R128 S1:** Complemento específico para conteúdo de curta duração (*short-form content*), incluindo anúncios, publicidade, patrocínios, chamadas promocionais (*promos*), vinhetas e peças semelhantes.
   - **EBU R128 S2:** Complemento específico para sonoridade em distribuição via streaming.
   - *Nota:* As recomendações EBU atuam como padrões de excelência técnica para radiodifusão e streaming, sem constituir requisitos universais mandatórios para plataformas de vídeo online.
4. **Norma ITU-R BS.1770-5 (11/2023):** Versão normativa vigente do algoritmo padrão de medição de sonoridade de programas integrada com ponderação K (*K-weighting*) e medição de True Peak com sobreamostragem mínima de 4×. A especificação exata da implementação interna nos filtros FFmpeg utilizados durante os testes históricos de `EP-TESTE-001` permanece classificada formalmente como `[NÃO VERIFICADO]`, preservando-se rigorosamente os valores numéricos apurados nos relatórios experimentais originais sem reprocessamento de áudios.

### 7.2 Especificações de Plataformas Online
1. **Spotify (Especificação Oficial):** Adota **-14,0 LUFS** como nível padrão de reprodução normalizada para a maioria dos ouvintes. Usuários do plano Premium podem selecionar em suas preferências os níveis alternativos de reprodução **Alto (-11,0 LUFS)** e **Baixo (-19,0 LUFS)**.
2. **YouTube (Recursos e Estimativas de Mercado):** A plataforma **não publica especificação técnica oficial com alvo fixo mandatório em -14,0 LUFS**. O YouTube implementa normalização de reprodução para atenuar volumes excessivos, além do recurso nativo **Volume Estável (*Stable Volume*)**. O valor de -14,0 LUFS constitui uma **estimativa e referência empírica de terceiros**, amplamente observada na indústria, decorrente da atenuação aplicada pela plataforma em conteúdos com sonoridade integrada superior a esse patamar.
3. **Apple Music (Referência de Mercado):** O patamar de **-16,0 LUFS** é amplamente adotado como **referência de mercado e estimativa da indústria** associada ao recurso *Sound Check*, e **não como especificação oficial publicada pela Apple**.

### 7.3 Nivelamento Experimental vs. Arquitetura do Produto
- **Nivelamento na Sandbox:** O valor de **-14,0 LUFS** utilizado nas Fases 2C e 2D constituiu exclusivamente um **nivelamento experimental preliminar** para permitir comparação auditiva equilibrada das amostras sem viés de volume na escuta do usuário.
- **Diretriz de Arquitetura:** O pipeline do Editor não deve hardcodar -14,0 LUFS nem associá-lo como norma compulsória. Os parâmetros de sonoridade (`target_lufs`, `max_true_peak`) devem permanecer configuráveis por perfil de distribuição em `config.json` para atender a cada canal ou destino específico.
