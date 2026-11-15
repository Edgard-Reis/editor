# HISTÓRICO DE MUDANÇAS E RELEASES (CHANGELOG.md)
## Registro Oficial de Evolução do Software Editor

---

> **Status:** DOCUMENTAÇÃO OPERACIONAL INSTANCIADA — REGISTRO VIVO DE RELEASES.

---

O formato deste documento é baseado no [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/), e adota o [Versionamento Semântico](https://semver.org/lang/pt-BR/).

---

## [1.0.0-rc.2] — 11/11/2026
### Homologação do Motion Graphics 9:16, Verificação Fonética Regional e Desobstrução Facial

#### Adicionado
- **Módulo MOD-09-MOTION-GRAPHICS:** Integração do sistema oficial de Motion Graphics do Dr. Gestão utilizando a toolchain local **HyperFrames 0.9.5** com aceleração Chrome Headless.
  - **Título Herói (T10):** Animação revelada letra a letra com desfoque e stagger (`power3.out`), perfil *Alta Minutagem* (72px, peso 900, sombra azul/preto `#004aad`) posicionado na Safe Zone superior ($Y = 240 - 340\text{px}$).
  - **Lower Third Dr. Gestão:** Card sólido ardósia (`#10182a` $\to$ `#080d16` com 100% de opacidade e borda `rgba(142, 125, 229, 0.65)`), revelação por máscara do nome *"Luiz Roberto Saraiva"*, linha gradiente tricolor animada e credencial *"Dr. Gestão · Especialista em Confecção"*.
  - **Badge Superior Direito:** Pílula marca d'água cilíndrica translúcida com ponto gradiente ciano/secundária.
  - **Renderização com Alfa:** Overlay exportado em WebM VP9 com `ALPHA_MODE: 1` a 60 fps e multiplexado via FFmpeg sobre o vídeo base sem recodificação de áudio (`-c:a copy`).
- **Agente Verificador Fonético (`phonetic_verifier.py`):** Criada camada de pós-processamento de transcrição ASR no MOD-02 com regras de reconstituição para sotaque fluminense/carioca (recomposição de fatiamentos fonéticos como *"que é pra palha"* $\to$ *"que atrapalha"*, aglutinações de *"demais"*, elisões e concordâncias plurais com perda de /s/ final). Preserva intervalos temporais milimétricos para karaokê.
- **Suíte de Testes Automatizados:**
  - `test_phonetic_verifier.py`: 5 testes aprovados (100% PASS em 0,002s).
  - `test_motion_graphics.py`: 4 testes aprovados (100% PASS em 0,030s).

#### Modificado / Corrigido
- **Eliminação de Alucinações na Queima:** Sincronizado o `MOD-03` (`aligner.py`) e `MOD-07` (`subtitles.py`) com a transcrição do modelo `faster-whisper-large-v3-turbo`. O termo errôneo *"TIPO DE BISA DE VENDA"* foi definitivamente substituído por *"DE BUSINESS, DE VENDA"*, além de *"É VENDAS, NÉ?"* e *"EU ESTOU FAZENDO"*.
- **Desobstrução do Rosto do Apresentador:** Identificado que a cabeça de Luiz Roberto Saraiva ocupa a faixa vertical de $Y = 400\text{px}$ a $980\text{px}$. A legenda foi deslocada de $Y = 1060\text{px}$ para a faixa do peito/tronco em **$Y = 1226 - 1274\text{px}$** (`margin_v = 640`), garantindo **246px de margem livre** abaixo do queixo. Rosto 100% desobstruído.
- **Resolução de Conflito Espacial (Legenda vs Lower Third):** O Lower Third foi posicionado em $Y = 1480\text{px}$, mantendo **206px de separação livre** em relação à legenda. Eliminado o vidro translúcido difuso em favor de fundo sólido opaco.
- **Master Final Homologado:** Gerado `short_vendas_motion_master_9x16.mp4` (SHA-256 `F7E79C2FF4B8C18CF339C746744C03FC192EC1A43DDF6BC17275F6F0F6032710`), com áudio EBU R128 $I = -14,5\text{ LUFS}$ e $TP = -6,4\text{ dBTP}$.

---

## [1.0.0-rc.1] — 11/11/2026
### Master Broadcast 9:16 Auditado e Homologado (REAUDITORIA-03)

#### Adicionado
- **Master Broadcast (Receita D):** Renderização canônica do master broadcast vertical 9:16 (`short_vendas_master_broadcast_9x16.mp4`) com ganho estático calibrado (-5,31 dB), reamostragem a 48 kHz stereo, corte com clamp de tempo exato (`-t 17.316933`), micro-fade terminal de 20 ms (eliminação total de estalo/clique, último sample a -74,75 dBFS) e `-movflags +faststart` (átomo `moov` no offset 36 bytes para streaming instantâneo).
- **Log de Custódia e Rastreabilidade:** Criação de [`broadcast.log`](file:///D:/Drifit/Experimentos_Sandbox/EXP-MOD01-INGEST-AUDIO/homologacao_real_20260823/renders/logs/broadcast.log) documentando o processo completo de conformidade.
- **Aprovação Integral REAUDITORIA-03:** Auditoria instrumental independente pelo auditor Axiom e gatekeeping por Zenith aprovando a totalidade dos 18 critérios (18/18 PASS, zero fail material).
  - Áudio: EBU R128 $I = -13,9\text{ LUFS}$, $TP = -5,5\text{ dBTP}$ ($\le -1,0\text{ dBTP}$, folga de 4,5 dB).
  - Perda audível: **0,000 ms** em relação à fonte.
  - Reprodutibilidade bit-a-bit comprovada com N1 de máxima força (SHA-256 `83EE4B74F4A6AC1E86A5A0F0E1A58A386191B48F58B3A5802D10F0C114060149`).
  - Blindagem de Produção: Diretório oficial mantido 100% íntegro.

---

## [1.0.0-alpha.5] — 11/11/2026
### Sound Design Automatizado e Masterização de Áudio Sincronizado

#### Adicionado
- **Módulo MOD-08-SOUND-DESIGN:** Implementado motor de sound design automatizado para Shorts com mixagem em ponto flutuante (NumPy 48kHz float32).
- **Camada de Efeitos Sonoros do Kit Dr. Gestão:**
  - Impacto grave calibrado aos 80ms (`impacto_grave.wav`) para impacto instantâneo no gancho (hook) inicial.
  - Cliques sutis (`clique.wav` a -20 dB) e transições suaves (`whoosh_curto.wav` a -14 dB) sincronizados com as quebras e trocas de legendas.
  - Controle de dinâmica com teto de pico a -0,44 dBFS, garantindo áudio limpo, inteligível e sem clipping.
- **Vídeo Master Gerado:** Renderizado o arquivo final `short_vendas_master_sound_9x16.mp4` (1080x1920 @ 60fps, 17.32s, 25.37 MB), combinando corte vertical 9:16, legendas animadas karaokê e sound design imersivo.
- **Suíte de Testes Automatizados:** `test_sound_design.py` implementada com 100% de aprovação.

---

## [1.0.0-alpha.4] — 11/11/2026
### Legendas Dinâmicas Animadas (Karaokê 9:16) e Sincronização de Documentação Oficial

#### Adicionado
- **Módulo MOD-07-DYNAMIC-SUBTITLES:** Implementado gerador de legendas dinâmicas no formato ASS (Advanced SubStation Alpha) com queima via FFmpeg no vídeo vertical 9:16.
- **Destaque de Palavras em Tempo Real (Karaokê):** Efeito de karaokê sincronizado baseado nos *word timestamps* do Whisper, destacando em amarelo/ouro (`#FFD700`) a palavra pronunciada, com base branca e contorno de 6px em safe zone vertical (margem de 420px).
- **Vídeo Legendado Produzido:** Renderizado o arquivo `short_vendas_legendado_9x16.mp4` (1080x1920 @ 60fps, 17.32s, 25.3 MB), pronto para publicação direta.
- **Integração de Documentação no Repositório Oficial:** Cópia e organização da documentação de referência (`docs/`), do acervo completo de PRDs (`docs/prd/`) e da documentação operacional viva (`docs/operacional/`) diretamente na pasta oficial do produto `D:\Drifit\Editor\docs\`.
- **Suíte de Testes Automatizados:** `test_subtitles.py` implementada com 100% de aprovação (2 de 2 testes).

---

## [1.0.0-alpha.3] — 11/11/2026
### Conclusão do Walking Skeleton (Ciclo Ponta a Ponta 9:16) com Equipe Distribuída

#### Adicionado
- **Módulo MOD-06-VIDEO-CUT-RENDER:** Implementado pelo agente **Forge** e auditado instrumentalmente pelo agente **Axiom**.
- **Primeiro Vídeo Vertical 9:16 Produzido:** Renderizado o arquivo `short_vendas_9x16.mp4` (1080x1920 @ 60fps, 17.32s, 26.7 MB) a partir do vídeo real 4K HEVC, com áudio estéreo cristalino preservado.
- **Ciclo Ponta a Ponta Demonstrado:** O pipeline completo foi executado em sucessão funcional:
  1. Ingestão e extração de áudio 16kHz WAV (`MOD-01`)
  2. Transcrição local Whisper com word timestamps (`MOD-02`)
  3. Alinhamento de pausas e cálculo de margens seguras (`MOD-03`)
  4. Corte frame-accurate e reenquadramento vertical 9:16 via FFmpeg (`MOD-06`)
- **Delegação Operacional Interagentes:** Ativação prática da equipe especializada no canvas do Maestri (Maestro, Forge, Axiom, Sentry, Zenith e Conselheiro).

---

## [1.0.0-alpha.2] — 11/11/2026
### Homologação do MOD-01 e Conclusão do MOD-02 (Whisper) e MOD-03 (Alinhamento & Pausas)

#### Adicionado
- **Módulo MOD-01-INGEST-AUDIO:** Implementado e validado em sandbox com 6 cenários sintéticos e homologado em arquivo real de vídeo 4K HEVC (`20260823_203211.mp4`, 308 MB). Tempo total de execução: 2.51s, com integridade do original intocada ($\Delta\text{Hash} = 0$).
- **Módulo MOD-02-WHISPER-LOCAL:** Implementado e validado em sandbox com Faster-Whisper (CTranslate2 INT8). Transcreveu 40.11s de áudio em 5.30s (7.6x mais rápido que tempo real) no processador Intel Xeon multi-core (14 cores / 28 threads).
- **Módulo MOD-03-TIMESTAMP-ALIGN:** Implementado e validado em sandbox. Detectou 20 pausas e estruturou 15 unidades editoriais com pré-roll (100ms) e pós-roll (200ms) acústicos seguros para cortes sem cliques ou corte de fonemas. Execução em 0.01s.
- **Word-Level Timestamps:** Extração automatizada de início, fim e probabilidade para cada palavra individual, gerando `transcript.json`, `transcript.srt` e atualizando o `project.json`.
- **Suítes de Testes Automatizados:** `test_ingest.py` (6 testes), `test_transcribe.py` (2 testes) e `test_aligner.py` (2 testes), todos com 100% de aprovação.
- **Integração do Conselheiro Independente:** Configurado terminal no Maestri rodando Antigravity CLI com modelo `Claude Sonnet 5.5 (Medium)` para consultorias técnicas de alto nível.

---

## [1.0.0-alpha.1] — 11/11/2026
### Reorganização Estratégica e Instanciação Operacional

#### Adicionado
- **Nova Filosofia de Engenharia:** Instituição do modelo de Engenharia Enxuta, Arquitetura Sólida e Desenvolvimento Modular por Fatias Verticais (*Vertical Slices*) em Sandbox.
- **Documentação Operacional Simplificada:** Instanciação dos 7 documentos canônicos (`PRD_MASTER.md`, `ARCHITECTURE.md`, `DECISIONS.md`, `ROADMAP.md`, `TESTS_AND_EVIDENCE.md`, `CHANGELOG.md`, `AGENT_GUIDELINES.md`).
- **Especificação Técnica do MOD-01:** Conclusão da especificação harmonizada do `MOD-01-INGEST-AUDIO`, unificando ingestão, inspeção FFprobe, hash SHA-256, proteção do original e extração de WAV 16kHz mono.
- **Roadmap do Walking Skeleton:** Mapeamento de 5 etapas práticas para alcançar um vídeo 9:16 exportado com o mínimo de código viável.
- **Diretriz de Autonomia Técnica:** Formalização da autonomia de planejamento para Maestro e Zenith em detalhes reversíveis, mantendo aprovação humana obrigatória para escopo, arquitetura, homologação e promoção ao legado.

#### Modificado
- **Harmonização do MOD-01 e Roadmap:** Removida a divisão artificial entre ingestão e extração de áudio; o WAV 16 kHz mono passa a ser um derivado direto da ingestão, preservando o áudio original contido no vídeo para a renderização final.
- **Critérios de Aceitação do MOD-01:** Refinados AC-04 (tolerância considerando streams reais) e AC-06 (medição experimental de telemetria em vez de corte rígido arbitrário).
- **Tratamento de Áudio Silencioso:** Definido formalmente que áudio silencioso legítimo não constitui erro ou arquivo corrompido.
- **Reclassificação de Desempenho em GPU:** Aceleração por GPU AMD Radeon RX 6600M formalizada como objetivo experimental de otimização, com fallback garantido para CPU.

#### Arquivado / Preservado
- **Acervo Histórico das Versões v0.1 a v0.5.6:** Todo o acervo das 11 ordens conceituais prévias (`PRD-EDITOR-001` a `PRD-EDITOR-011`) foi preservado intacto em modo somente leitura no diretório `PRD_EDITOR_2026-11-11_REV05_CORRECAO_06/`.

---

## [Histórico Preliminar — Ciclo Cartorial v0.1 a v0.5.6] (09/11/2026 – 11/11/2026)
- **v0.1 a v0.4:** Definição da visão de produto e primeiras especificações conceituais do Editor para YouTube e Shorts.
- **v0.5 a v0.5.6:** Ciclo de auditorias documentais cruzadas (ordens PRD-005 a PRD-011), refinando as 13 decisões pendentes, as 6 dimensões analíticas e a rastreabilidade histórica dos 44 requisitos originais. Todo o conhecimento técnico acumulado desse ciclo foi sintetizado e aproveitado na versão 1.0.0-alpha.1.
