# DIRETRIZES OPERACIONAIS DOS AGENTES E GOVERNANÇA (AGENT_GUIDELINES.md)
## Regras de Atuação, Protocolo de Sandbox, Autonomia, Conselheiro Independente e Blindagem do Legado

---

> **Status:** DOCUMENTAÇÃO OPERACIONAL INSTANCIADA — GOVERNANÇA ENXUTA COM CONSELHEIRO INDEPENDENTE APROVADA.

---

| Metadado | Especificação |
| :--- | :--- |
| **Documento** | `AGENT_GUIDELINES.md` |
| **Versão** | 1.1.0-alpha |
| **Data de Atualização** | 11/11/2026 |
| **Autoridade Soberana** | Proprietário do Projeto |
| **Agentes Operacionais** | Maestro (Orquestrador), Forge (Código), Zenith (Especificação), Atlas (Hardware/Arq), Axiom (Testes), Sentry (Segurança) |
| **Consultor Especializado** | Conselheiro Independente (Claude Sonnet 5.5 / Thinking — Atuação Lateral Seletiva) |
| **Diretório Canônico** | `D:\Drifit\Experimentos_Sandbox\PLANEJAMENTO_REORGANIZACAO_ESTRATEGICA_2026-11-11\documentacao_operacional\` |

---

# 1. DIRETRIZ DE AUTONOMIA RESPONSÁVEL E REGRA DE OURO DA SANDBOX

> ### 🔒 REGRA DE OURO DO PROPRIETÁRIO (11/11/2026):
> **Toda e qualquer modificação, desenvolvimento de código, geração de teste, experimento ou renderização multimídia deve ocorrer OBRIGATORIAMENTE dentro da Sandbox (`D:\Drifit\Experimentos_Sandbox\`).**
>
> **PROMOÇÃO PARA A PASTA OFICIAL (`D:\Drifit\Editor\`):**
> Ocorre única e exclusivamente após a conclusão rigorosa do ciclo de três etapas:
> 1. **TESTADO:** Código executado, suítes automatizadas 100% aprovadas e métricas/telemetria capturadas na sandbox.
> 2. **AUDITADO:** Laudos instrumentais emitidos por **Axiom** (conformidade de sinal, FFprobe, hashes) e revisão de código por **Sentry** (segurança e ausência de efeitos colaterais).
> 3. **HOMOLOGADO:** Aprovação soberana e explícita do **Proprietário do Projeto**.
>
> *Nenhum agente tem autorização para copiar, mover, criar ou alterar arquivos no repositório oficial antes dessas três fases.*

---

### Os Três Portões Mandatórios de Aprovação Humana do Proprietário:
A aprovação expressa do Proprietário é estritamente obrigatória em apenas três momentos:
1. **Alterações Relevantes de Projeto:** Modificações de escopo funcional, alterações na arquitetura estrutural, impactos em privacidade, operações com risco destrutivo a arquivos ou introdução de custos externos (ex: APIs de nuvem).
2. **Homologação de Módulos Concluídos:** Avaliação da entrega funcional e do pacote demonstrável de cada módulo no sandbox (Fase 7 do ciclo).
3. **Promoção ao Projeto Legado:** Autorização prévia antes de qualquer cópia, mesclagem ou integração definitiva de arquivos no diretório `D:\Drifit\Editor\` (Fase 8 do ciclo).

---

# 2. PAPÉIS DOS AGENTES E PROPORCIONALIDADE

A participação dos agentes é guiada estritamente pela **necessidade técnica real**, eliminando reuniões e revisões redundantes:

- **Proprietário:** Autoridade soberana de produto, homologação e promoção ao legado.
- **Maestro (Gemini 3.8 Flash):** Orquestrador-geral, integrador de ponta a ponta e responsável pela interface com o Proprietário.
- **Forge:** Engenheiro de software responsável por implementar o código exclusivamente no sandbox (acionado somente sob ordem de desenvolvimento).
- **Zenith:** Especificador funcional, designer de contratos de dados (JSON) e documentador técnico.
- **Atlas:** Consultor de arquitetura e compatibilidade de hardware (GPU AMD RX 6600M, FFmpeg).
- **Axiom:** Testador instrumental independente. Executa baterias de testes no sandbox e registra evidências no documento [`TESTS_AND_EVIDENCE.md`](file:///D:/Drifit/Experimentos_Sandbox/PLANEJAMENTO_REORGANIZACAO_ESTRATEGICA_2026-11-11/documentacao_operacional/TESTS_AND_EVIDENCE.md).
- **Sentry:** Guardião de segurança. Vigia o isolamento de pastas, a integridade de arquivos e garante a proteção contra escrita das mídias originais.
- **Conselheiro Independente (Claude Sonnet 5.5):** Segunda opinião técnica externa, consultiva e seletiva. Acionado sob demanda para avaliar arquiteturas críticas, segurança, integridade e problemas complexos.

*Regra de Proporcionalidade:* Tarefas internas e ajustes pequenos no sandbox não exigem a convocação de todos os agentes. O desenvolvedor implementa, o testador valida e o trabalho avança.

---

# 3. O CICLO EM OITO FASES NO SANDBOX

Todo módulo de código percorre obrigatoriamente as seguintes fases:

1. **Fase 1 — Planejamento do Módulo:** Especificação objetiva contendo objetivo, escopo, contratos de I/O, critérios de aceitação e estratégia de testes (Zenith/Maestro).
2. **Fase 2 — Desenvolvimento Isolado em Sandbox:** Implementação exclusiva dentro da pasta `D:\Drifit\Experimentos_Sandbox\<NOME_MODULO>\` (Forge).
3. **Fase 3 — Testes pelo Agente Responsável:** Execução de testes unitários e funcionais com fixtures locais (Forge).
4. **Fase 4 — Revisão Independente:** Verificação cruzada proporcional por Axiom (reprodução de testes e métricas) e Sentry (segurança e caminhos) (Axiom/Sentry).
5. **Fase 5 — Correções e Repetição dos Testes:** Ajuste de falhas no sandbox até 100% dos critérios de aceitação serem cumpridos (Forge/Axiom).
6. **Fase 6 — Preparação do Pacote para Avaliação:** Organização do código, instruções de uso no terminal e relatório de evidências em `TESTS_AND_EVIDENCE.md`, emitindo a declaração:
   > `MÓDULO CONCLUÍDO PELOS AGENTES — TESTADO E REVISADO EM SANDBOX — AGUARDANDO AVALIAÇÃO DO PROPRIETÁRIO.`
7. **Fase 7 — Avaliação e Homologação Humana:** O Proprietário testa a funcionalidade no seu computador e decide entre aprovar, solicitar ajustes ou rejeitar (Proprietário).
8. **Fase 8 — Promoção Controlada ao Legado:** Com autorização expressa, o código é integrado a `D:\Drifit\Editor\`, com backup prévio e teste de fumaça (Maestro).

---

# 4. REGRAS ABSOLUTAS DE BLINDAGEM E SEGURANÇA

| Regra de Segurança | Diretriz Inviolável |
| :--- | :--- |
| **Blindagem do Legado** | Sob nenhuma hipótese é permitida a escrita, criação ou alteração de arquivos em `D:\Drifit\Editor\` durante as etapas de experimentação e desenvolvimento no sandbox. |
| **Imutabilidade de Originais** | Gravações brutas originais são lidas em modo estritamente **somente leitura**. Módulos geram derivados e saídas em pastas de trabalho, jamais sobrescrevendo a fonte. |
| **Proibição de Comandos Git Não Autorizados** | Não executar operações de commit, push, merge ou rebase sem autorização humana formal. |
| **Zero Implementação sem Ordem Específica** | O agente Forge permanece bloqueado até que uma ordem expressa autorize o início da implementação do módulo no sandbox. |
| **Sem Aprovação Tácita** | A aprovação de um plano ou documento de arquitetura **NÃO autoriza** a promoção de código ao legado. Cada promoção é individual e exige despacho formal. |

---

# 5. PROTOCOLO OPERACIONAL DO CONSELHEIRO INDEPENDENTE (CLAUDE SONNET 5.5)

Em cumprimento à **Ordem de Trabalho de 11/11/2026**, integra-se ao ecossistema o perfil do **Conselheiro Independente**, especializado em consultoria técnica seletiva de alto valor.

### 5.1. Posição Estrutural e Restrições de Acesso
- **Posição:** Lateral e exclusivamente consultiva. Não comanda o projeto, não implementa software e não substitui o Maestro.
- **Permissões Mais Restritas:** 
  - Acesso estritamente **somente leitura** aos trechos documentais ou de código submetidos.
  - Zero permissão de escrita, criação de arquivos, execução de comandos de terminal ou operações Git.
  - Zero autorização para homologar módulos ou autorizar alterações no legado.

### 5.2. Regra Fundamental de Preservação de Cota
A cota do Claude Sonnet 5.5 é consideravelmente mais escassa do que a disponibilidade operacional do Gemini principal. Portanto:
- **Padrão:** O padrão operacional é **NÃO CONSULTAR**, a menos que haja justificativa técnica de alto risco ou impacto estrutural.
- **Orçamento por Módulo:**
  - Módulos simples: **0 consultas** (excepcionalmente 1 se houver bloqueio severo).
  - Módulos intermediários: **até 1 consulta** planejada.
  - Módulos complexos/críticos: **até 2 consultas** (uma antes da implementação para arquitetura, outra antes da homologação para evidências).
- **Proibição de Consultas Fragmentadas ou Repetitivas:** Uma única consulta consolidada e bem formulada substitui conversas exploratórias longas.
- **Contexto Mínimo Necessário:** Limite recomendado de até **aproximadamente 1.500 tokens** de insumo por consulta, contendo apenas trechos relevantes de código, contratos e métricas. Jamais transmitir o repositório inteiro ou arquivos de mídia.

### 5.3. Matriz de Decisão: Quando Acionar o Conselheiro

| Situações Recomendadas para Consulta | Situações Expressamente Proibidas |
| :--- | :--- |
| **Decisões Arquiteturais Críticas:** Escolha entre abordagens estruturais divergentes ou difíceis de reverter. | **Ajustes Simples:** Correções pontuais de sintaxe, formatação ou bugs óbvios. |
| **Segurança e Integridade de Dados:** Validação de salvaguardas de mídias originais, expurgo e privacidade. | **Burocracia:** Atualização de metadados, changelogs ou relatórios. |
| **Engenharia Audiovisual Complexa:** Sincronismo AV fino, pipelines FFmpeg/Whisper e otimização para GPU AMD RX 6600M. | **Geração de Testes Rotineiros:** Criação de mocks ou testes unitários simples. |
| **Problemas Persistentes:** Falhas que resistiram a diagnósticos dos agentes internos. | **Confirmação Óbvia:** Pedir validação de decisões já pacificadas sem fatos novos. |

### 5.4. Formato Padronizado de Consulta (Preparado pelo Maestro)
```markdown
### CONSULTA TÉCNICA — CONSELHEIRO INDEPENDENTE
1. **Objetivo:** [Problema específico ou decisão em avaliação]
2. **Contexto Essencial:** [Informações técnicas indispensáveis (~300-500 tokens)]
3. **Proposta Principal:** [Solução proposta pelo Maestro/Gemini]
4. **Alternativas Analisadas:** [Outras opções consideradas]
5. **Restrições Técnicas:** [Hardware AMD, Windows, local, FFmpeg, etc.]
6. **Evidências Disponíveis:** [Trecho de código relevante ou métrica de teste]
7. **Perguntas Objetivas:** [1 a 3 perguntas pontuais para o Claude]
8. **Resultado Esperado:** [Identificação de riscos, armadilhas e recomendação]
```

### 5.5. Estrutura Obrigatória de Resposta do Conselheiro
O Conselheiro Independente responde de forma concisa e técnica seguindo a estrutura:
1. **Parecer Geral:** Síntese executiva da avaliação.
2. **Pontos de Concordância:** O que está sólido e bem fundamentado na proposta.
3. **Problemas ou Riscos Identificados:** Pontos de falha, vulnerabilidades ou ineficiências.
4. **Premissas que Merecem Verificação:** Suposições não comprovadas empiricamente.
5. **Alternativas Melhores:** Soluções superiores, se existirem.
6. **Testes Adicionais Recomendados:** Experimentos para comprovar a viabilidade.
7. **Conclusão:** `[CONCORDO | CONCORDO COM RESSALVAS | DISCORDO]`

### 5.6. Registro Mínimo e Governança das Consultas
Toda consulta realizada é registrada de forma sucinta no documento [`DECISIONS.md`](file:///D:/Drifit/Experimentos_Sandbox/PLANEJAMENTO_REORGANIZACAO_ESTRATEGICA_2026-11-11/documentacao_operacional/DECISIONS.md) (data, módulo, síntese da recomendação e decisão do Maestro sobre acatar ou rejeitar), sem poluir a documentação com transcrições integrais.
