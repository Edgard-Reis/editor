# ROADMAP OPERACIONAL DO MVP (ROADMAP.md)
## Planejamento de Módulos, Fatias Verticais e Sequenciamento de Entregas

---

> **Status:** DOCUMENTAÇÃO OPERACIONAL INSTANCIADA — ROADMAP HARMONIZADO APROVADO.

---

| Metadado | Especificação |
| :--- | :--- |
| **Documento** | `ROADMAP.md` |
| **Versão** | 1.1.0-alpha |
| **Data de Instanciação** | 11/11/2026 (Alinhado em 15/11/2026) |
| **Abordagem** | Fatias Verticais (*Vertical Slicing*) orientadas ao Master 16:9 no MVP |
| **Diretório Canônico** | `D:\Drifit\Experimentos_Sandbox\PLANEJAMENTO_REORGANIZACAO_ESTRATEGICA_2026-11-11\documentacao_operacional\` |

---

# 1. VISÃO DO PRIMEIRO PRODUTO FUNCIONAL (MASTER 16:9)

O desenvolvimento prioriza a entrega completa e revisável do episódio horizontal **Master 16:9**, com Motion Graphics e acabamento profissional integrados ao MVP:

$$\text{\bf Ingestão Segura} \longrightarrow \text{\bf Análise \& Briefing} \longrightarrow \text{\bf Master 16:9 + Motion} \longrightarrow \text{\bf Aprovação} \longrightarrow \text{\bf Derivados 9:16}$$

Os cortes verticais 9:16 são gerados **após a aprovação do Master 16:9**, reaproveitando a estrutura editorial já validada e aplicando reenquadramento próprio para o formato vertical.

---

# 2. SEQUÊNCIA DE ETAPAS OPERACIONAIS DO MVP

### ETAPA 1 — Fundação Técnica e Ingestão de Mídia *(validada em sandbox)*
- **`MOD-01-INGEST-AUDIO`:** Ingestão somente leitura (`.mp4`, `.mkv`, `.mov`, `.avi`), inspeção FFprobe, cálculo SHA-256, extração `audio_speech_16k_mono.wav` (Whisper) e preservação do áudio original para o master.

### ETAPA 2 — Transcrição Local, Alinhamento e Inteligência Editorial *(em consolidação em sandbox)*
- **`MOD-02-WHISPER-LOCAL`:** Transcrição local (`faster-whisper-large-v3-turbo` INT8 em CPU) com verificação fonética parametrizada por `Brand Profile`.
- **`MOD-03-TIMESTAMP-ALIGN`:** Alinhamento temporal por frase e palavra, respeitando margem de silêncio segura (`180–220 ms`).
- **Briefing e Planejamento Editorial:** Compreensão do conteúdo integral, remoção de erros/repetições, estruturação narrativa em `briefing.json` / `edl_longo.json` / `editorial_plan.json`.

### ETAPA 3 — Montagem Master 16:9, Motion Graphics e Acabamento *(no escopo do MVP)*
- **Tratamento Acústico e Masterização:** Cadeia de limpeza vocal (`-14 LUFS`, True Peak `-1.0 dBFS`).
- **Motion Graphics no MVP (obrigatório):** Biblioteca reutilizável de títulos animados (`T10`), legendas dinâmicas, destaques de palavras, *lower thirds*, *callouts*, destaques numéricos, elementos explicativos, setas, ícones, zooms (`bate()`), B-rolls (Ken Burns), transições, sound design sincronizado, vinheta e encerramento.
- **Renderização e Auditoria Master 16:9:** Renderização `1920×1080` a `30 fps` (validação prévia por fatia-piloto antes do episódio completo).
- **`MOD-05-HUMAN-CHECKPOINT`:** Revisão e aprovação do Master 16:9 pelo Proprietário.

### ETAPA 4 — Cortes Verticais 9:16 Derivados *(pós-aprovação do Master)*
- **Seleção e Reenquadramento 9:16:** Reaproveita a estrutura editorial aprovada para extrair cortes coerentes (sem promessas de viralização e preservando o contexto original) em `1080×1920`, com reenquadramento dedicado, legendas dinâmicas e Motion Graphics verticais.

### ETAPA 5 — Integração Agnóstica de IA e Exportação Final
- **Adaptador Local (CLI/MCP):** Exposição das ferramentas locais para ambientes autenticados do usuário, sem chaves comerciais e sem envio automático de mídia.
- **Empacotamento e Controle de Qualidade:** Exportação somente leitura com manifestos SHA-256 e laudos instrumentais.

---

# 3. CRITÉRIO DE AVANÇO ENTRE ETAPAS

1. Cada módulo é desenvolvido isoladamente em sandbox, testado, revisado e corrigido pela equipe de agentes.
2. O módulo concluído é submetido à homologação do Proprietário (Fase 7 do modelo).
3. A etapa seguinte só é iniciada após aprovação expressa do módulo anterior.
