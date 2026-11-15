# PRD MESTRE DO EDITOR (PRD_MASTER.md)
## Especificação de Requisitos do Produto — Editor de Vídeo Assistido por IA para Uso Local

---

> **Status:** DOCUMENTAÇÃO OPERACIONAL INSTANCIADA — REQUISITOS DO MVP LOCAL APROVADOS — ENGENHARIA MODULAR EM SANDBOX.

---

| Metadado | Especificação |
| :--- | :--- |
| **Documento** | `PRD_MASTER.md` |
| **Versão** | 1.1.0-alpha |
| **Data de Instanciação** | 11/11/2026 (Alinhado em 15/11/2026) |
| **Proprietário e Usuário Primário** | Proprietário do Projeto (Dr. Gestão como perfil piloto inicial; arquitetura extensível a outros perfis) |
| **Ambiente de Execução** | Local no PC Principal (Windows, GPU AMD Radeon RX 6600M 8 GB) |
| **Diretório Canônico** | `D:\Drifit\Experimentos_Sandbox\PLANEJAMENTO_REORGANIZACAO_ESTRATEGICA_2026-11-11\documentacao_operacional\` |

---

# 1. VISÃO DO PRODUTO E CASO DE USO REAL

O **Editor** é um software autônomo de pós-produção audiovisual assistido por inteligência artificial, projetado para operar em ambiente local no computador pessoal do Proprietário.

### Fluxo Oficial e Problema que o Software Resolve:
O fluxo principal do MVP é:

**Gravação original completa → análise e planejamento editorial → master completo 16:9 → revisão e aprovação do usuário → geração de derivados 9:16.**

No fluxo inicial de produção (tendo o canal **Dr. Gestão** como perfil piloto, sem acoplamento ao núcleo), gravações brutas longas em formato horizontal 16:9 precisam ser transformadas em:
1. **Episódio Master 16:9 completo** com áudio tratado, remoção de erros/repetições, narrativa estruturada e Motion Graphics profissionais;
2. **Cortes verticais 9:16 derivados** (aproximadamente sete cortes coerentes e contextualizados por episódio, gerados apenas após aprovação do Master 16:9).

O Editor elimina o trabalho manual repetitivo de transcrição, limpeza acústica, decupagem, animação gráfica e renderização, mantendo o Proprietário sempre no controle da aprovação editorial final.

---

# 2. ESCOPO DO MVP LOCAL (O QUE ESTÁ INCLUÍDO)

O MVP inicial contempla as capacidades abaixo (distinguindo **requisito aprovado** de **funcionalidade já comprovada em sandbox**):

1. **Ingestão Segura e Preservação de Mídia *(comprovada em sandbox)*:**
   - Ingestão de arquivos de vídeo nos contêineres `.mp4`, `.mkv`, `.mov` e `.avi`.
   - Garantia incondicional de que as gravações brutas originais jamais serão modificadas, truncadas ou sobrescritas (preservação somente leitura e $\Delta\text{Hash} = 0$).
   - Cálculo de hash SHA-256 para comprovação de integridade de dados.
   - Extração do derivado de trabalho de áudio (WAV PCM 16kHz mono) para transcrição, mantendo o áudio original intacto para o master final.
2. **Transcrição Local e Inteligência Editorial *(requisito aprovado; ASR e alinhamento comprovados em sandbox)*:**
   - Reconhecimento de fala via Whisper local (`faster-whisper-large-v3-turbo` INT8 em CPU), alinhamento temporal por frase/palavra e identificação de pausas.
   - **Compreensão integral e estruturação narrativa:** a inteligência editorial deve compreender o conteúdo completo, identificar temas e arcos narrativos, preservar explicações relevantes, remover erros e repetições e selecionar cortes coerentes e contextualizados (sem fabricar ganchos nem prometer viralização).
3. **Montagem e Renderização do Master 16:9 com Motion Graphics *(requisito aprovado; cadeia 16:9 validada em sandbox)*:**
   - Tratamento acústico e normalização broadcast (`-14 LUFS`, True Peak `-1.0 dBFS`).
   - **Motion Graphics no MVP (prioridade obrigatória, não refinamento futuro):** biblioteca reutilizável de títulos animados, legendas dinâmicas, destaques de palavras, *lower thirds*, *callouts*, destaques numéricos, elementos explicativos, setas, ícones, zooms/reenquadramentos e transições modernas, além de vinheta e encerramento.
   - Checkpoint de revisão e aprovação do Master 16:9 pelo usuário.
4. **Derivados Verticais 9:16 Pós-Aprovação *(requisito aprovado; módulos base validados em sandbox)*:**
   - Geração de cortes verticais 9:16 (`1080×1920`) derivados do conteúdo aprovado, com reenquadramento adequado, legendas dinâmicas e Motion Graphics, mantendo o contexto original das falas.
5. **Arquitetura Agnóstica de IA e Privacidade *(requisito aprovado; estudo e adaptador local em evolução)*:**
   - O Editor não deve depender de chaves de APIs comerciais como requisito de funcionamento. Deve operar com ambientes e agentes compatíveis (ex.: Antigravity/Gemini, OpenCode) utilizando a autenticação e as assinaturas já disponíveis ao usuário.
   - Mídias originais locais não podem ser enviadas automaticamente para serviços externos.

---

# 3. ESCOPO EXPLICITAMENTE EXCLUÍDO DO MVP (EVOLUÇÕES FUTURAS)

Para evitar inflação desnecessária de complexidade no MVP local, ficam formalmente alocados como evoluções posteriores (Pós-MVP):
- Arquitetura multi-inquilino (*multi-tenant*) comercial, cobrança SaaS ou painéis corporativos em nuvem;
- Integrações diretas de publicação via API de redes sociais (o Proprietário publica manualmente seus arquivos exportados);
- Exportação avançada de projetos para DaVinci Resolve / Premiere (formato EDL/FCPXML);
- Promessas automáticas de viralização ou análise multimodal pesada em tempo real durante a gravação.

---

# 4. REQUISITOS NÃO-FUNCIONAIS FUNDAMENTAIS

| ID | Requisito | Diretriz de Engenharia |
| :--- | :--- | :--- |
| **NFR-01** | **Segurança de Mídias** | O arquivo original bruto do Proprietário jamais sofre operação de escrita ou deleção pelo software. |
| **NFR-02** | **Operação 100% Local** | O pipeline essencial (ingestão, Whisper, corte FFmpeg e render) opera sem dependência obrigatória de conexão com a internet. |
| **NFR-03** | **Compatibilidade de Hardware** | O software é desenvolvido e validado para o PC Principal do Proprietário (Windows com GPU AMD Radeon RX 6600M 8 GB). |
| **NFR-04** | **Arquitetura Modular** | Módulos desacoplados via contratos de dados JSON simples, permitindo substituir ou melhorar componentes (ex: trocar modelo de transcrição) sem reescrever o sistema. |
| **NFR-05** | **Recuperabilidade** | O estado do projeto é persistido em arquivo local `project.json`, permitindo retomar o trabalho em caso de fechamento do programa. |
