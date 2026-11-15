# REGISTRO DE DECISÕES DE ARQUITETURA E CATÁLOGO DE DECISÕES (DECISIONS.md)
## Histórico Consolidado de Decisões, Orientações Estabelecidas e Pendências

---

> **Status:** DOCUMENTAÇÃO OPERACIONAL INSTANCIADA — DECISÕES HISTÓRICAS PRESERVADAS — PADRÃO ADR.

---

| Metadado | Especificação |
| :--- | :--- |
| **Documento** | `DECISIONS.md` |
| **Versão** | 1.0.0-alpha |
| **Data de Instanciação** | 11/11/2026 |
| **Classificação Canônica** | Aprovada / Orientação Estabelecida / Pendente do Proprietário / Dependente de Validação Experimental |
| **Diretório Canônico** | `D:\Drifit\Experimentos_Sandbox\PLANEJAMENTO_REORGANIZACAO_ESTRATEGICA_2026-11-11\documentacao_operacional\` |

---

# 1. TAXONOMIA E ESTADOS DE DECISÃO

Em cumprimento estrito à Seção 2.5 da Ordem Complementar de 11/11/2026, todas as decisões e pendências históricas são registradas preservando suas distinções de governança:

- **`APROVADA`:** Decisão deliberada e formalmente autorizada pelo Proprietário do Projeto.
- **`ORIENTACAO_ESTABELECIDA`:** Consenso técnico adotado como diretriz de projeto, aguardando formalização definitiva pelo Proprietário.
- **`PENDENTE_DE_DELIBERACAO`:** Matéria de impacto estratégico, de negócio ou de escopo que depende exclusivamente de decisão soberana do Proprietário.
- **`DEPENDENTE_DE_EVIDENCIA_EXPERIMENTAL`:** Questão técnica que necessita de ensaios laboratoriais e medições em sandbox para ser decidida.
- **`PROPOSTA`:** Recomendação técnica dos agentes submetida à avaliação.

---

# 2. DECISÕES ESTRUTURAIS APROVADAS NA REORGANIZAÇÃO

### ADR-01 — Adoção da Filosofia de Engenharia Enxuta e Desenvolvimento Modular em Sandbox
- **Estado:** `APROVADA` (Ordem de Reorganização Estratégica, 11/11/2026).
- **Contexto:** O projeto encontrava-se paralisado em um ciclo hiper-burocrático de revisões de PRD (11 ordens conceituais sem avanço de código).
- **Decisão:** Reorientar o projeto para software local, engenharia enxuta, arquitetura sólida e desenvolvimento modular por fatias verticais (*Vertical Slices*) dentro de sandboxes isolados, mantendo o projeto legado protegido.
- **Consequência:** Encerramento do ciclo cartorial e foco em entregar código testado e demonstrável ao Proprietário.

### ADR-02 — Consolidação Documental em Sete Documentos Operacionais
- **Estado:** `APROVADA` (Ordem de Reorganização Estratégica, 11/11/2026).
- **Contexto:** Havia sobrecarga documental com dezenas de arquivos, matrizes de 264 células e relatórios repetitivos.
- **Decisão:** Substituir o acervo de trabalho por 7 documentos operacionais simples e vivos (`PRD_MASTER`, `ARCHITECTURE`, `DECISIONS`, `ROADMAP`, `TESTS_AND_EVIDENCE`, `CHANGELOG`, `AGENT_GUIDELINES`), preservando todo o histórico v0.5.6 em arquivo passivo.
- **Consequência:** Clareza absoluta de referência para a equipe técnica e fim das divergências taxonômicas.

### ADR-03 — Autonomia Técnica dos Agentes para Especificações Reversíveis
- **Estado:** `APROVADA` (Ordem Complementar, 11/11/2026).
- **Contexto:** Agentes solicitavam aval para detalhes triviais de código, travando o ritmo de trabalho.
- **Decisão:** Maestro e Zenith possuem autonomia para planejar e especificar detalhes técnicos reversíveis no escopo aprovado. A aprovação humana do Proprietário é restrita a: (1) mudanças relevantes de escopo/arquitetura/privacidade/custos, (2) homologação de módulos concluídos e (3) promoção ao legado.
- **Consequência:** Agilidade no sandbox com preservação total da soberania do Proprietário nos pontos críticos.

### ADR-04 — Regra de Ouro da Promoção: Segregação Estrita na Sandbox
- **Estado:** `APROVADA` (Diretriz Soberana do Proprietário, 11/11/2026).
- **Contexto:** Risco de contaminação prematura da pasta oficial do produto (`D:\Drifit\Editor\`) com arquivos intermediários, experimentais ou renders preliminares.
- **Decisão:** Toda e qualquer modificação, desenvolvimento de código, geração de teste, experimento ou renderização multimídia deve ocorrer OBRIGATORIAMENTE dentro da Sandbox (`D:\Drifit\Experimentos_Sandbox\`). A promoção para a pasta oficial (`D:\Drifit\Editor\`) ocorre estritamente após a conclusão do tripé: (1) **Testado** com 100% de aprovação e telemetria, (2) **Auditado** instrumentalmente por Axiom/Sentry, e (3) **Homologado** com autorização expressa do Proprietário.
- **Consequência:** Blindagem absoluta da pasta oficial contra código experimental, garantindo que o repositório principal do produto contenha apenas artefatos finais homologados.

### ADR-05 — Padronização Canônica de RTF e Parâmetros Estritos de Broadcast Audio
- **Estado:** `APROVADA COM EMENDA REAUDITORIA-02` (Laudos Instrumentais Axiom / Autorização Soberana do Proprietário, 11/11/2026).
- **Contexto:** Identificou-se inconsistência métrica em `project.json` (razão inversa chamada de `realtime_factor` no render vs RTF canônico no Whisper) e distorção técnica na reamostragem (96 kHz involuntário e cauda de 116 ms). Na primeira correção, a flag `-shortest` truncou indevidamente 85,333 ms de áudio de programa devido ao lookahead do filtro `loudnorm`.
- **Decisão:**
  1. **Métricas Canônicas:** Fixar `real_time_factor` como $\frac{T_{\text{processamento}}}{T_{\text{mídia}}}$ (onde $<1.0$ representa mais rápido que tempo real e $>1.0$ mais lento). Para a velocidade relativa de playback, utilizar explicitamente `playback_speed_factor` ($\frac{T_{\text{mídia}}}{T_{\text{processamento}}}$), aplicando a regra a todos os módulos (Render e Transcrição).
  2. **Encoding de Broadcast Audio (Emenda Reauditoria-02 / Receita D):**
     - Revogar expressamente a flag `-shortest` para cadeias com normalização temporal.
     - Forçar resample travado em **48.000 Hz** (`-ar 48000`).
     - Alinhar a cauda temporal com a duração exata do vídeo via duração explícita (`-t [duracao_video]`) combinada com corte fino (`atrim=0:[duracao_video],asetpts=PTS-STARTPTS`) e rampa suave de término de 20 ms (`afade=t=out:st=[fim-20ms]:d=0.020`) para eliminar cliques na fronteira.
     - Garantir que todo muxing MP4 incorpore `-movflags +faststart` para posicionar o átomo `moov` no início do container.
- **Consequência:** Zero perda de programa audível ($\Delta_{\text{perda}} = 0,000\text{ ms}$), conformidade EBU R128 ($I = -13,9\text{ LUFS}$, $TP = -5,5\text{ dBTP}$), streaming web instantâneo e ausência total de cliques acústicos.

### ADR-06 — Padrão de Excelência ASR (Large-v3-Turbo), Revisão Fonética Regional e Motion Graphics Mandatório
- **Estado:** `APROVADA COM RESSALVAS DO PROPRIETÁRIO` (Homologação com Diretrizes Soberanas, 11/11/2026).
- **Contexto:** Na homologação da Walking Skeleton, o Proprietário autorizou o marco registrando três ressalvas técnicas essenciais para a qualidade do produto final:
  1. *Modelo ASR:* Uso indevido de modelo inferior (`base`) em vez do padrão de excelência estabelecido `faster-whisper-large-v3-turbo`.
  2. *Revisão Fonética / Textual:* Ausência de verificação de erros de ASR decorrentes de sotaques regionais (especificamente a fala fluminense/carioca de Luiz Roberto Saraiva, onde "que atrapalha demais as vendas" foi fatiado grotescamente em "que é pra palha de mais as vendas").
  3. *Motion Graphics:* Ausência de elementos gráficos de identidade visual (títulos herói, lower thirds, vinhetas e animações do catálogo Dr. Gestão).
- **Decisão:**
  1. **Motor ASR:** Travar o modelo padrão do `EXP-MOD02-WHISPER-LOCAL` em `faster-whisper-large-v3-turbo` (com fallback somente sob restrição explícita de hardware).
  2. **Camada de Revisão Fonética:** Implementar módulo de pós-processamento de transcrição treinado/instruído para as particularidades da prosódia e sotaque fluminense (redução de sibilantes finais, ligaduras fonéticas) antes da injeção no alinhador e gerador de legendas.
  3. **Integração de Motion Graphics:** Adotar o Motion System Dr. Gestão (`CATALOGO_MOTIONS.md` V2 / T10 Título Herói) como camada mandatória na composição final dos cortes de vídeo.
- **Consequência:** Elevação imediata da fidelidade semântica das legendas, eliminação de erros bizarros de ASR na tela e entrega de produto audiovisual com acabamento profissional completo.

---

# 3. ORIENTAÇÕES HISTÓRICAS ESTABELECIDAS (AGUARDANDO FORMALIZAÇÃO DEFINITIVA)

Estas matérias foram consensuadas tecnicamente e guiam o desenvolvimento, mas permanecem registradas com sua distinção canônica:

### DEC-PEND-001 — Nomenclatura Neutra e Independência do Núcleo
- **Estado:** `ORIENTACAO_ESTABELECIDA`
- **Diretriz:** O núcleo do software é mantido com nomenclatura neutra e independente em relação a marcas ou clientes específicos, permitindo atender ao estúdio Dr. Gestão sem acoplamento rígido de código.

### DEC-PEND-005 — Preservação de Originais e Procedimento Formal de Expurgo
- **Estado:** `ORIENTACAO_ESTABELECIDA`
- **Diretriz:** Arquivos de vídeo brutos gravados são estritamente imutáveis durante a edição. Expurgo físico de mídias só pode ocorrer por solicitação expressa do Proprietário através de procedimento seguro de 4 etapas com confirmação consciente.

### DEC-PEND-006 — Escopo Operacional do Estúdio Interno
- **Estado:** `ORIENTACAO_ESTABELECIDA`
- **Diretriz:** O produto é dimensionado para o estúdio de produção do canal Dr. Gestão e associados autorizados, sem antecipar desnecessariamente requisitos comerciais de multi-inquilino.

### DEC-PEND-007 — Encurtamento Algorítmico Desativado por Padrão
- **Estado:** `ORIENTACAO_ESTABELECIDA`
- **Diretriz:** O corte algorítmico agressivo de pausas é mantido desativado por padrão no fluxo principal, evitando que pausas reflexivas naturais da fala sejam cortadas indevidamente.

### DEC-PEND-008 — Ambiente-Alvo de Desenvolvimento e Validação
- **Estado:** `ORIENTACAO_ESTABELECIDA`
- **Diretriz:** A plataforma de referência oficial é o computador PC Principal do Proprietário com Windows e GPU dedicada AMD Radeon RX 6600M 8 GB.

---

# 4. PENDÊNCIAS DE DELIBERAÇÃO SOBERANA DO PROPRIETÁRIO

Matérias de negócio e escopo reservadas exclusivamente à decisão do Proprietário:

### DEC-PEND-002 — Escopo MVP-A / MVP-B e Dependência Multimodal
- **Estado:** `PENDENTE_DE_DELIBERACAO`
- **Contexto:** Deliberar sobre a alocação da proteção preliminar de continuidade de silêncios (FR-005B) no MVP-A (amostragem visual mínima) ou em etapa posterior (MVP-B), mantendo o MVP inicial estritamente focado em fala/semântica.

### DEC-PEND-003 — Estratégia de Inferência de IA e Limites de Nuvem
- **Estado:** `PENDENTE_DE_DELIBERACAO`
- **Contexto:** Deliberar sobre a política de modelos: priorizar 100% execução local gratuita ou permitir chamadas pontuais e controladas a APIs de nuvem caso necessário.

### DEC-PEND-010 — Autonomia Editorial e Calibração de Propostas
- **Estado:** `PENDENTE_DE_DELIBERACAO`
- **Contexto:** Calibrar o nível de agressividade com que a IA sugere cortes de vídeo e o grau de detalhe exigido no checkpoint de aprovação humana.

### DEC-PEND-011 — Diretrizes de Privacidade e Transmissão de Conteúdos
- **Estado:** `PENDENTE_DE_DELIBERACAO`
- **Contexto:** Formalizar a política de tratamento de mídias inéditas (conteúdos antes da publicação aberta na internet).

### DEC-PEND-012 — Interface de Interação Prevista para o MVP
- **Estado:** `PENDENTE_DE_DELIBERACAO`
- **Contexto:** Definir a evolução da interface: se a CLI automatizada atende à fase inicial ou se deve ser acoplado um dashboard local simples (web local) para visualização dos cortes.

---

### DEC-PEND-014 — Imutabilidade e Pinning Hash de Artefatos de Render
- **Estado:** `PENDENTE_DE_DELIBERACAO` (submetido pela auditoria instrumental Axiom, 12/11/2026 — achados D1, D2, D4 e D7 do laudo do master longo 1080p30).
- **Contexto:** No pipeline de render do episódio longo o master foi sobrescrito in-place por gerações sucessivas no mesmo caminho (a geração defeituosa com 165 s de tela preta foi destruída sem registro) e a EDL normativa foi regenerada durante a janela de auditoria, deixando de ser a fonte da verdade do artefato já entregue. O manifesto fixa apenas a saída e não as entradas, de modo que o drift normativo permaneceu invisível à verificação automática. Soma-se a isso um verificador de pré-entrega amostral (5 pontos de luma) que não barra loudness fora de especificação.
- **Diretriz Proposta:** (1) toda saída de render deve ser versionada com sufixo de geração e hash no nome, vedada a sobrescrita in-place do caminho de entrega; (2) o manifesto deve fixar por SHA-256 e tamanho todas as entradas (EDL, WAVs limpos, brutos, overlays, logos e transições), incluindo `source_edl_sha256`; (3) um verificador de custódia deve comparar o hash da EDL vigente com o declarado no manifesto e reprovar o artefato quando divergirem; (4) a verificação de pré-entrega deve varrer todos os frames para ausência de tela preta (em vez de amostrar pontos) e reprovar loudness fora da especificação, com telemetria do encoder persistida em disco durante a execução.
- **Consequência (se aprovada):** tornaria a auditoria instrumental reprodutível e fecharia a classe de defeitos detectada no laudo de 12/11/2026, sem prejudicar o direito soberano do Proprietário sobre a promoção (ADR-04).

# 5. PENDÊNCIAS DE VALIDAÇÃO EXPERIMENTAL EM SANDBOX

Questões técnicas que serão medidas e respondidas na prática durante a execução dos módulos:

### DEC-PEND-004 — Homologação da Cadeia Acústica Veicular
- **Estado:** `DEPENDENTE_DE_EVIDENCIA_EXPERIMENTAL`
- **Contexto:** Ensaiar em sandbox a combinação ideal de filtros para áudios gravados em ambiente automotivo (ruído de rodagem, motor e reverberação).

### DEC-PEND-009 — Requisitos de Hardware Mínimos e Recomendados
- **Estado:** `DEPENDENTE_DE_EVIDENCIA_EXPERIMENTAL`
- **Contexto:** Registrar métricas empíricas de uso de VRAM, memória RAM e consumo térmico durante o processamento no PC Principal.

### DEC-PEND-013 — Formatos, Codecs e Perfis de Entrada e Saída
- **Estado:** `DEPENDENTE_DE_EVIDENCIA_EXPERIMENTAL`
- **Contexto:** Medir o desempenho de decodificação de 4K 59.94 fps HEVC e comparar a renderização acelerada por GPU AMD (`h264_amf`) com CPU (`libx264`).
