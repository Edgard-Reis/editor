# Referência Aprovada — "Virada de Chave"

Versão 0.2 (revisada na Fase 4B.1). Backup da v0.1: `projetos/dr-gestao/motion-system/_backup_pre_fase4b1/REFERENCIA_APROVADA_VIRADA_CHAVE.md`

Papel: **primeira referência de qualidade de motion** do Dr. Gestão. Não é template obrigatório.
Selos de evidência: ver `DESIGN_SYSTEM_MOTION_DR_GESTAO.md`, seção 0.2
([CÓDIGO], [RELATÓRIO], [MARCA], [USUÁRIO], [INTERPRETAÇÃO], [PROPOSTA], [NÃO VALIDADO]).
Os níveis de maturidade V0/V1/V2/NC pertencem ao `CATALOGO_MOTIONS.md` e **não** são usados aqui como evidência.

Convenção de caminhos: todos relativos à raiz do repositório e escritos por extenso, sem abreviações (seções 8 e 9).

---

## 1. Aprovação

| Campo | Valor |
|---|---|
| Data | 04/11/2026 |
| Fonte | **[USUÁRIO]** informada no pedido da Fase 4B.1 |
| Escopo | **somente** a animação "Virada de Chave" (22,50–27,70 s do piloto) |
| SHA-256 do MP4 aprovado | `795E2DB97F1F413A414A49E16F78E605B02BF49344DBA61C2E71E256137A716A` |

Limites da aprovação: não cobre o restante do piloto de 32,5 s, nem componentes isolados, nem 9:16, nem conformidade de loudness.
Como a aprovação é da cena inteira, **não** há aprovação individual de cada técnica (ver `CATALOGO_MOTIONS.md`).

## 2. Conceito narrativo

- **[CÓDIGO]** Trecho falado, segundo o comentário em `build.py`: "...se você que tá notulado... quer virar chave radicalmente..." (22,26–27,70 s).
- **[RELATÓRIO]** Metáfora aprovada no briefing: **bifurcação de trilho**. A estrutura de produção chega a um ponto de decisão, a alavanca redireciona o fluxo e a rota se abre em 4 plataformas. É uma **transformação de rota comercial**, não um toggle.
- **[RELATÓRIO]** Copy: "TRANSFORMAÇÃO", "Virada de Chave", "4 PLATAFORMAS", "ROTA ANTERIOR", "ROTA ATIVA". Sem "Canal único" nem afirmação comercial infundada.
- **[CÓDIGO]** Plataformas: TikTok, Shopee, Mercado Livre, Shein (logos oficiais).

## 3. Solução visual

**[CÓDIGO]** 2.5D vetorial, sem 3D real:
- trilho único com extrusão manual (3 traços SVG por trilho);
- piso em grade com perspectiva CSS, máscara radial e poeira;
- câmera 2D (`x`, `y`, `scale`) sobre o "mundo"; tipografia em camada separada;
- junção física com base, pivô, alavanca e lâmina;
- rota anterior abandonada (trilho cinza, batente, rótulo);
- leque fantasma tracejado (possibilidades);
- pacotes de fluxo: fila na decisão, rajada, regime permanente;
- nós com logos reais; título editorial; âncora "4 PLATAFORMAS"; selo verde "ROTA ATIVA".

**Geometria dos ramos [CÓDIGO]:** leque de quatro retas que parte da junção `(748, 782)` e termina em `(1250,290)`, `(1430,430)`, `(1560,590)`, `(1660,760)`, com inclinações de ≈ 44°, 27°, 13° e 1°. Nós em diagonal descendente da esquerda para a direita (não é um arco).

**Cores:** ver `DESIGN_SYSTEM_MOTION_DR_GESTAO.md`, seção 2. Em resumo **[CÓDIGO]**: a cena usa os oficiais `#2f97d4` e `#8e7de5`, e as cores experimentais `#22d3ee`, `#a78bfa` e `#22c55e`; **não usa** o azul oficial `#004aad`, e a cena **não foi alterada** por isso. Superfícies: gradientes metálicos e radiais; **sem** cards de vidro.

## 4. Técnicas utilizadas

Todas **[CÓDIGO]** em `cena_virada.py` / `virada.css`, exceto onde marcado.

| # | Técnica | Onde |
|---|---|---|
| 1 | Extrusão 2.5D por traços SVG concêntricos | `_rail()`, `.vc-r-*` |
| 2 | Desenho de trilho com `pathLength=1` + `strokeDashoffset` | trechos "desenho dos trilhos" |
| 3 | Piso em perspectiva CSS + máscara radial | `.vc-floor__grid` |
| 4 | Câmera 2D com arco tensão/recuo | `.vc-cam` |
| 5 | Paralaxe entre fundo, mundo e tipografia | `.vc-floor`, `.vc-cam`, `.vc-ui` |
| 6 | Gesto físico (alavanca/lâmina com `back.out`) | `.vc-lever`, `.vc-blade` |
| 7 | Halo pulsante no ponto de decisão | `.vc-halo` |
| 8 | Fila → rajada de pacotes, com passagem obrigatória pela junção | `_pacote()` |
| 9 | Leque fantasma tracejado | `.vc-ghost` |
| 10 | Título por letra com blur → nítido e `stagger` | `.vc-t2 .vc-l` |
| 11 | Filetes e âncora numérica com `scaleX` | `.vc-crule`, `.vc-krule` |
| 12 | Sons por evento no kit existente | `sound_bus.registrar_automatico` |
| 13 | Abertura com opacidade-base 0,25 do piso | ajuste A da Passo 3B (**[RELATÓRIO]**) |
| 14 | Entrada do B-roll seguinte a 38% de opacidade | ajuste D (**[RELATÓRIO]**; implementação em `cenas.py` da cópia experimental) |
| 15 | Logos via `background-image` (evita duplicidade de mídia) | ajuste C (**[RELATÓRIO]**) |
| 16 | Módulo que devolve `(html, js)` | `montar_virada()` |

## 5. Sequência temporal

| Tempo (s) | Fala | Eventos **[CÓDIGO]** |
|---|---|---|
| 22,50 | — | fade-in 0,20 s; piso 0,25 → 1; câmera `1,05 → 1` |
| 22,62 | — | SFX `whoosh_curto` |
| 22,72–23,55 | "...se você que tá notulado" | trilho desenha (0,83 s) |
| 23,30–24,65 | | pacotes; 2 escoam pela rota anterior, 4 entram na fila |
| 23,55–24,15 | | rota anterior desenha; rótulo "ROTA ANTERIOR" em 23,90 |
| 23,60 | | halo nasce |
| 24,34–24,84 | "quer" | halo; leque fantasma (24,36); câmera aproxima; SFX `whoosh` |
| 24,84 | "virar" | alavanca gira −130° → −44° (0,46 s); SFX `swish` |
| 25,02 | | lâmina comuta 27,7° → −26°; SFX `clique2`; rota anterior pisca e apaga |
| 25,03–**25,49** | | os 4 ramos desenham (início 25,03 + i·0,04, duração 0,34 s; o último termina em 25,49) |
| 25,16–25,28 | | rajada dos pacotes da fila |
| 25,28 | | batente da rota anterior |
| 25,56–25,70 | | filete, kicker e "Virada de" |
| 25,94 | "chave" | "Chave" (stagger 0,04); nós das 4 plataformas (stagger 0,09); SFX `impacto_grave` |
| 26,46 | "radicalmente" | câmera recua; paralaxe do piso e da UI |
| 26,58–26,66 | | filete e "4 PLATAFORMAS" |
| 26,86 | | selo "ROTA ATIVA"; SFX `check` |
| 27,42–27,70 | | fade-out 0,28 s |
| 27,70 | | B-roll entra a 38% por 0,16 s |

Ápices da fala **[CÓDIGO]** (`FALA`): quer 24,58 · virar 24,84 · chave 25,94 · radicalmente 26,46.

**Sincronia — nuance [CÓDIGO]:** o título se completa na palavra-chave ("Chave" em 25,94), mas nem todos os elementos nascem no momento da fala. O leque fantasma começa ≈ 0,22 s antes de "quer"; "Virada de" entra 0,86 s depois de "virar"; "4 PLATAFORMAS" e o selo entram depois do início de "radicalmente". Detalhe em `DESIGN_SYSTEM_MOTION_DR_GESTAO.md`, seção 8.1.

## 6. Decisões aprovadas e pontos de atenção

Decisões registradas **[RELATÓRIO]** (`README_EXPERIMENTO.md` e relatórios 3A/3B):
- metáfora de bifurcação/alavanca de trilho;
- título com revelação tardia, sincronizado à fala;
- "4 PLATAFORMAS" no lugar de "4 CANAIS";
- azul, lilás e ciano para a transformação; verde apenas para status;
- iniciar em 2.5D; órbita 3D só como experimento futuro;
- cobertura ≥80% e hold ≤0,35 s como diagnóstico, não requisito;
- SSIM/PSNR só entre render convencional e rápido da **mesma** implementação;
- prefixo `.vc-` em todas as classes;
- quatro ajustes da Passo 3B (A–D).

**[USUÁRIO]** A aprovação visual de 04/11/2026 cobre a cena como renderizada, com os defeitos abaixo.

Pontos de atenção **[RELATÓRIO]** (3A) registrados e **não corrigidos**:
- metade superior vazia até ≈ 25,7 s (severidade: atenção);
- rótulo "ROTA ANTERIOR": 12 px, opacidade final ≈ 0,28 (informativo);
- selo "ROTA ATIVA": 190×34 px, em (606, 848), 12 px, fundo verde a 10%, sobre área de glow — classificado como "discreto" (atenção); o relatório pede reavaliação, não afirma que a posição esteja errada;
- colisão preexistente na track 30 (marca d'água + `sfx_11`).

## 7. Pontos que não devem ser generalizados

1. A metáfora de trilho/alavanca serve para "decisão/mudança de rota"; não para outros assuntos.
2. A janela de 5,2 s e os tempos absolutos são específicos desta fala.
3. O layout (tipografia à esquerda, rede à direita) pressupõe cena de tela cheia sem apresentador; não foi testado com rosto.
4. O leque com 4 destinos é específico de "4 plataformas".
5. `#22d3ee`, `#a78bfa` e `#22c55e` são experimentais, não tokens da marca; `#004aad` não foi usado.
6. Rótulos de 12–13 px não são padrão de legibilidade.
7. Os pontos de atenção da seção 6 não devem ser copiados.
8. A abordagem tem alto custo de produção (sincronização manual).
9. Não há versão vertical (9:16).
10. Nada indica que todos os vídeos precisem desse acabamento.
11. A cena aprovada **não** usa cards de vidro nem o azul `#004aad`; isso **não** a torna modelo para a identidade de cards.

## 8. Caminhos dos arquivos de referência (raiz do repositório)

| Arquivo (caminho completo) | Papel |
|---|---|
| `projetos/dr-gestao/episodios/teste-piloto-parte-02/workspace_experimental_virada/cena_virada.py` | geração de HTML + timeline (fonte) |
| `projetos/dr-gestao/episodios/teste-piloto-parte-02/workspace_experimental_virada/virada.css` | estilos `.vc-*` (fonte) |
| `projetos/dr-gestao/episodios/teste-piloto-parte-02/workspace_experimental_virada/build.py` | integra a cena (`montar_virada`) e gera a composição |
| `projetos/dr-gestao/episodios/teste-piloto-parte-02/workspace_experimental_virada/cenas.py` | **cópia experimental**; única com `entrada_de`/`entrada_dur` em `broll()` |
| `projetos/dr-gestao/episodios/teste-piloto-parte-02/workspace_experimental_virada/index.html` | artefato gerado |
| `projetos/dr-gestao/episodios/teste-piloto-parte-02/workspace_experimental_virada/partes.json` | artefato gerado |
| `projetos/dr-gestao/episodios/teste-piloto-parte-02/workspace_experimental_virada/README_EXPERIMENTO.md` | briefing, ferramentas, guardrails |
| `projetos/dr-gestao/episodios/teste-piloto-parte-02/workspace_experimental_virada/_experimento/RELATORIO_PASSO3A.md` | relatório da Passo 3A |
| `projetos/dr-gestao/episodios/teste-piloto-parte-02/workspace_experimental_virada/_experimento/RELATORIO_PASSO3B.md` | relatório da Passo 3B |
| `projetos/dr-gestao/episodios/teste-piloto-parte-02/workspace_experimental_virada/_experimento/renders_passo3b/virada_passo3b_convencional.mp4` | render aprovado |
| `projetos/dr-gestao/episodios/teste-piloto-parte-02/workspace_experimental_virada/_experimento/renders_passo3b/CONTATO_AVALIACAO.png` | contato visual |
| `projetos/dr-gestao/episodios/teste-piloto-parte-02/workspace_experimental_virada/_experimento/renders_passo3b/snapshots/` | 13 quadros (22,55–27,766 s) |
| `projetos/dr-gestao/episodios/teste-piloto-parte-02/workspace_experimental_virada/_experimento/MANIFESTO_POS_PASSO3B_SHA256.tsv` | manifesto de integridade |
| `projetos/dr-gestao/branding/PREFERENCIAS.md` | regras de marca |

Outras cópias de `cenas.py` **não** são a referência (nenhuma tem `entrada_de`):
`projetos/dr-gestao/branding/scripts/cenas.py` (biblioteca compartilhada),
`projetos/dr-gestao/episodios/EP-00/workspace/cenas.py`,
`projetos/dr-gestao/episodios/teste-piloto/workspace/cenas.py`,
`projetos/dr-gestao/episodios/teste-piloto-parte-02/workspace/cenas.py` (primeiro piloto),
`projetos/dr-gestao/episodios/teste-piloto-parte-02/workspace_validacao_fase2/cenas.py`.

(O caminho `workspace_experimental_virada/renders_passo3b/...` citado na Fase 4A não existe; o correto está na tabela acima.)

## 9. Versão renderizada e integridade

| Propriedade | Valor |
|---|---|
| Arquivo | `projetos/dr-gestao/episodios/teste-piloto-parte-02/workspace_experimental_virada/_experimento/renders_passo3b/virada_passo3b_convencional.mp4` |
| SHA-256 | `795E2DB97F1F413A414A49E16F78E605B02BF49344DBA61C2E71E256137A716A` |
| Verificação | hash recalculado nas Fases 4A e 4B.1; idêntico ao de `RELATORIO_PASSO3B.md` e ao da aprovação (seção 1) |
| Tamanho | 35.173.860 bytes |
| Vídeo | 1920×1080, H.264/yuv420p, 30 fps, 975 frames, 32,500 s |
| Áudio | AAC 48 kHz estéreo; volume médio −17,7 dB, pico −2,7 dB |
| Render | HyperFrames 0.9.5, convencional, qualidade `standard` |

- O vídeo contém o piloto inteiro; a Virada de Chave corresponde a 22,50–27,70 s.
- **Loudness:** a medição de −17,7 dB **não comprova** −14 LUFS integrado. **Conformidade de loudness: PENDENTE de medição apropriada** (LUFS integrado e True Peak).

Hashes das fontes (verificados na Fase 4A):

| Arquivo | SHA-256 |
|---|---|
| `projetos/dr-gestao/episodios/teste-piloto-parte-02/workspace_experimental_virada/cena_virada.py` | `8F40A8F7408927CD03B986E0B7163E59281519B208AE9C0F9B60B6DEDF1DBBBF` |
| `projetos/dr-gestao/episodios/teste-piloto-parte-02/workspace_experimental_virada/virada.css` | `8CE681EDB24E095DCB266727B65EC2BD49C28CB430B56410C60D41BC121DE4FC` |
| `projetos/dr-gestao/episodios/teste-piloto-parte-02/workspace_experimental_virada/cenas.py` | `6CA271017B234C332F3F3863021B694885C3C5908EDFDDD19AE941A903E0C14A` |

Reprodutibilidade **[RELATÓRIO]**: HyperFrames resolvido pelo cache do `npx`; GSAP por CDN. Ambos podem mudar sem alteração do workspace.

## 10. Medições do relatório (Passo 3B) — **[RELATÓRIO]**

- Lint HyperFrames 0.9.5: 0 erros, 6 avisos (5 preexistentes + 1 arquitetural `vc5`).
- Referências locais: 15, nenhuma faltando. Seletores GSAP únicos: 73.
- Track 12: `vc5` 22,500–27,700 e `br6` 27,700–31,650, adjacentes.
- Luminância: 22,55 s → 8,3; último frame da cena → 5,4; primeiro do B-roll → 33,7.
