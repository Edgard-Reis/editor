# Relatório de Correções — Fase 4B.1

Data: 04/11/2026
Escopo: correção **exclusivamente documental** dos três documentos de `projetos/dr-gestao/motion-system/`, com base no parecer da Fase 4B.
Nenhum código, mídia ou ambiente protegido foi alterado. Nenhum build, lint ou renderização foi executado.

## 1. Backups (criados antes de qualquer edição)

Pasta: `projetos/dr-gestao/motion-system/_backup_pre_fase4b1/`

| Arquivo | SHA-256 (idêntico ao original antes da edição) |
|---|---|
| `projetos/dr-gestao/motion-system/_backup_pre_fase4b1/DESIGN_SYSTEM_MOTION_DR_GESTAO.md` | `37F77C4B6A44C7B8C5B14920B80F323F50206368393917044DB87FA6906520B9` |
| `projetos/dr-gestao/motion-system/_backup_pre_fase4b1/REFERENCIA_APROVADA_VIRADA_CHAVE.md` | `C3E8D41B7EA9637BEC81F67A8CF1DE71787C06461DE745E2FFF6E1016D049570` |
| `projetos/dr-gestao/motion-system/_backup_pre_fase4b1/CATALOGO_MOTIONS.md` | `8929286F9E23416F5530221974C5589B6C7B65E977C34614FEE56FFFD53AC33D` |

## 2. Hashes finais dos documentos (v0.2)

| Arquivo | SHA-256 |
|---|---|
| `projetos/dr-gestao/motion-system/DESIGN_SYSTEM_MOTION_DR_GESTAO.md` | `9064609C875A99136F97C0BEC8DAA159CF7F5E6E5B9B5D6330A60AAD55D9D9BB` |
| `projetos/dr-gestao/motion-system/REFERENCIA_APROVADA_VIRADA_CHAVE.md` | `B41F4D4FCBAEC4CEF38D5EB90C3DE1912AB534A40A42F3822C2FA28FFB955D49` |
| `projetos/dr-gestao/motion-system/CATALOGO_MOTIONS.md` | `E1E155CBA7F60D83931981C80BDF8D50BAB4B629A1168C4B78E925C52FAEAD7C` |

Este relatório não tem hash registrado aqui (um arquivo não registra o próprio hash).

## 3. Taxonomia nova (duas dimensões separadas)

### 3.1 Evidência da informação (sete selos)

| Selo | Significado |
|---|---|
| [CÓDIGO] | Confirmado em código-fonte ou arquivo gerado |
| [RELATÓRIO] | Confirmado em relatório ou medição do render |
| [MARCA] | Preferência oficial (`PREFERENCIAS.md`) |
| [USUÁRIO] | Decisão/aprovação explícita do usuário |
| [INTERPRETAÇÃO] | Leitura sobre intenção/efeito; não é fato comprovado |
| [PROPOSTA] | Recomendação não validada |
| [NÃO VALIDADO] | Lacuna conhecida |

Substitui [FATO] / [PREFERÊNCIA] / [PROPOSTA] / [NÃO VALIDADO] da v0.1.

### 3.2 Maturidade do componente

| Nível | Critério |
|---|---|
| V0 | Proposto, sem implementação conhecida |
| V1 | Implementado e renderizado em um único contexto (a cena de referência), acoplado a ela; a aprovação cobre a cena, não cada recurso |
| V2 | Isolado, parametrizável e testado em dois ou mais contextos |
| NC | Não classificado: existe segundo outra fonte; código não revisado |

Progressão V0 → V1 → V2. **Nenhum recurso está em V2.** O antigo "V2 — em uso na biblioteca" foi removido; esses itens passaram a NC.

## 4. Resumo das correções por documento

### `DESIGN_SYSTEM_MOTION_DR_GESTAO.md` (v0.1 → v0.2)
- Nova taxonomia e convenção de caminhos (seção 0).
- Seção 1: removida a "estética escura/profissional" como preferência de marca; reclassificada como interpretação desta cena. Tabela "identidade oficial × cena" separando vidro de gradientes metálicos/radiais.
- Seção 2: HEX como identificador canônico; registro de que `#004aad` não aparece na cena (sem alterar a animação); conflitos de nomenclatura; cores oficiais × experimentais; nota sobre `#a78bfa` × `#8e7de5`.
- Seção 3: Inter declarada globalmente em `index.html` + relatório de fontes, sem afirmar mais; selo "ROTA ATIVA" e "ROTA ANTERIOR" descritos conforme o 3A.
- Seção 4: geometria correta dos ramos (leque de retas, não arco); regra de manter opções visíveis.
- Seção 6: amplitudes reais de câmera (0,966–1,05) e piso (1,0–1,10).
- Seção 8.1 (nova): como o título realmente sincroniza.
- Seção 9: loudness pendente; seção 11.1 (nova): marca d'água; seção 12 (nova): contrato HyperFrames; seção 14: backlog; seção 15: registro de aprovação; seção 16: fontes completas.

### `REFERENCIA_APROVADA_VIRADA_CHAVE.md` (v0.1 → v0.2)
- Registro de aprovação (04/11/2026, escopo, SHA-256).
- Ramos terminam em 25,49 s (não 25,3 s); geometria corrigida; nuance de sincronia.
- Pontos de atenção com a avaliação original do 3A (sem exagero).
- Caminhos completos e identificação exata das cópias de `cenas.py`; loudness pendente.

### `CATALOGO_MOTIONS.md` (v0.1 → v0.2)
- Duas dimensões separadas; níveis V0/V1/V2/NC definidos com critérios.
- Seção 6 (nova): tempos absolutos, `de/ate` não parametrizam a cena; seletores CSS globais; uma instância por composição.
- C09 e C11 alinhados ao 3A; T15 limitado à cópia experimental; `cenas.py` por cópia, com caminho completo e SHA-256.
- Backlog P01–P12; "conventional" corrigido (agora o termo "convencional").

## 5. Status O1–O12 e I1–I8

| ID | Item | Status | Onde |
|---|---|---|---|
| O1 | Remover estética escura/profissional como preferência oficial | Corrigido | DS §1 |
| O2 | Vidro oficial × gradientes metálicos/radiais | Corrigido | DS §1.1 |
| O3 | Registrar ausência de `#004aad` sem alterar a cena | Corrigido | DS §2.3; Ref §3, §7 |
| O4 | Conflito de nomes de cor; HEX canônico | Corrigido | DS §2 |
| O5 | Inter: declaração global + relatório, sem afirmar mais | Corrigido | DS §3 |
| O6 | Amplitudes reais câmera/piso | Corrigido | DS §6.1 |
| O7 | Geometria dos ramos | Corrigido | DS §4; Ref §3 |
| O8 | Término do desenho dos ramos ≈ 25,49 s | Corrigido | Ref §5 |
| O9 | Tempos absolutos; `de/ate` não parametrizam | Corrigido | Cat §6.1 |
| O10 | Seletores globais; uma instância por composição | Corrigido | Cat §6.2 |
| O11 | Selos de evidência × maturidade V0/V1/V2 | Corrigido | DS §0; Cat §1 |
| O12 | Interpretações reclassificadas | Corrigido | DS (vários); Ref |
| I1 | Sincronia do título | Corrigido | DS §8.1; Ref §5 |
| I2 | Aprovação 04/11/2026, escopo, SHA-256 | Corrigido | DS §15; Ref §1 |
| I3 | Caminhos completos | Corrigido | DS §16; Ref §8–9; Cat §8 |
| I4 | Cópia exata de `cenas.py` e referências | Corrigido | Ref §8; Cat §8 |
| I5 | Contrato HyperFrames | Corrigido | DS §12 |
| I6 | Marca d'água | Corrigido | DS §11.1 |
| I7 | Selo "ROTA ATIVA" sem exagero | Corrigido | DS §3, §10; Ref §6; Cat C09 |
| I8 | Loudness: −17,7 dB não comprova −14 LUFS; pendente | Corrigido | DS §9.2; Ref §9; Cat §6.5 |

Itens do §5 do pedido também atendidos: não adicionei `#004aad`; cores oficiais × experimentais diferenciadas; `#a78bfa` × `#8e7de5` registrado sem presumir mesma aplicação; regra de manter opções visíveis registrada (DS §4); "conventional" corrigido.

**Observações:**
- A afirmação de determinismo (DS §12, item 7) foi registrada como **[INTERPRETAÇÃO]**: não há texto explícito nas fontes, só a ausência de `Math.random` no `index.html`.
- A verificação visual da marca d'água sobre a Virada continua **[NÃO VALIDADO]**.
- Correção de uma afirmação do parecer 4B: ele sugeria que a marca d'água diferia de `PREFERENCIAS.md`. Verifiquei que `right:48px` com 175 px de largura equivale a `x=1697`; a documentação registra compatibilidade.

## 6. Evidências e caminhos consultados (somente leitura)

- `projetos/dr-gestao/episodios/teste-piloto-parte-02/workspace_experimental_virada/cena_virada.py`
- `projetos/dr-gestao/episodios/teste-piloto-parte-02/workspace_experimental_virada/virada.css`
- `projetos/dr-gestao/episodios/teste-piloto-parte-02/workspace_experimental_virada/build.py` (trechos de integração e geração do HTML)
- `projetos/dr-gestao/episodios/teste-piloto-parte-02/workspace_experimental_virada/index.html` (cabeçalho, trechos finais, clips `vc5` e `br6`, marca d'água, fonte)
- `projetos/dr-gestao/episodios/teste-piloto-parte-02/workspace_experimental_virada/_experimento/RELATORIO_PASSO3A.md`
- `projetos/dr-gestao/episodios/teste-piloto-parte-02/workspace_experimental_virada/_experimento/RELATORIO_PASSO3B.md`
- `projetos/dr-gestao/episodios/teste-piloto-parte-02/workspace_experimental_virada/README_EXPERIMENTO.md`
- `projetos/dr-gestao/branding/PREFERENCIAS.md`
- seis cópias de `cenas.py` (busca por `entrada_de` e SHA-256)
- `projetos/dr-gestao/episodios/teste-piloto-parte-02/workspace_experimental_virada/_experimento/MANIFESTO_POS_PASSO3B_SHA256.tsv` (conferência de integridade)

## 7. Confirmação de integridade

- **Manifesto pós-3B:** 62 de 62 arquivos do workspace experimental conferem (SHA-256), incluindo `cena_virada.py`, `virada.css`, `build.py`, `cenas.py`, `index.html` e `partes.json`.
- **Arquivos gravados nos últimos 30 minutos** em `projetos/` e `vortex-edicao/`: apenas os três documentos de `motion-system/` (os backups foram excluídos da busca por serem cópias novas).
- **Ações executadas:** criação da pasta de backup, cópia dos três documentos, reescrita/edição dos três documentos e criação deste relatório. Comandos executados: `Copy-Item`, `Get-FileHash`, `Get-ChildItem`, `Select-String`, `Get-Content` e `git status` (leitura).
- **Não executados:** build, lint, renderização, qualquer alteração de código.
- **Observação sobre o repositório:** `git status` mostra modificações **preexistentes** não relacionadas a esta fase (por exemplo, `projetos/dr-gestao/branding/scripts/cenas.py`, com última gravação em 01/11/2026, e arquivos em `Identidade visual/`). Não foram tocadas nesta etapa. A origem delas não foi investigada. A pasta `motion-system/` não estava versionada antes das Fases 4A/4B.1.

## 8. Pendente

Aguardando aprovação do usuário para a Fase 4C. Nenhum experimento de desenvolvimento foi iniciado.
