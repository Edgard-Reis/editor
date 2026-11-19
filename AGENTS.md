# REGRAS DE GOVERNANÇA — DRIFIT EDITOR (PRODUÇÃO)

## 1. Ambiente Oficial e Proteção de Mídias
- **Ambiente Oficial:** Toda execução de produção, testes e renders ocorre em `D:\Drifit\Editor`.
- **Imutabilidade de Mídias:** Arquivos brutos originais em `brutos/` são estritamente somente-leitura (`ΔHash = 0`). Nunca sobrescrever ou mover mídias originais.
- **Isolamento de Episódio (Proibição de Contaminação Cruzada):** Ao editar qualquer episódio, é terminantemente proibido ler, copiar ou reaproveitar textos, cenas HTML, EDLs ou renders de outros episódios ou pastas de testes antigos (`ep-test-edl`, `ep-01-*`, `teste-piloto-*`, `REFERENCIA_APROVADA_*.md`). Só é permitido ler os arquivos do episódio atual e o kit base da marca (`config.json`, `PREFERENCIAS.md`, `DESIGN_SYSTEM_*`, `sons/`, `logos/`, `overlays/`, `vinhetas/`).

## 2. Preservação do Motor (`core/`)
- Nunca apagar ou reescrever do zero os módulos já testados em `core/`:
  - `ingest.py`
  - `analyze.py`
  - `transcript_review.py`
  - `semantic_planner.py`
  - `edl_builder.py`
  - `edl_renderer.py`
  - `shorts_renderer.py`
  - `brand_bumpers.py`
  - `master_lint.py`
  - `video_verify.py`
- Atue apenas conectando fluxos, corrigindo pontas soltas e ajustando integrações incrementais.

## 3. Proporcionalidade e Higiene de Contexto
- **Execução Direta e Enxuta:** Tarefas simples e lineares devem ser executadas diretamente, sem sobrecarga cerimonial.
- **Delegação Seletiva:** Delegar subtarefas apenas quando houver paralelismo real e independente que justifique o custo.
- **Higiene de Contexto:** É proibido ler pastas de `docs/historico/` ou `docs/prd/historico_*` sem solicitação explícita do usuário.

## 4. Ativação Obrigatória de Skill
- Para **qualquer** pedido envolvendo edição de vídeo, briefing editorial, cortes (Master ou Shorts/Reels) ou revisão de render, você DEVE carregar e seguir estritamente:
  - `.agents/skills/editor-autonomo/SKILL.md`

## 5. Diretrizes Técnicas Essenciais (Hardware & Qualidade)
- **Hardware:** GPU AMD Radeon RX 6600M (**sem CUDA**). Renderização de vídeo via `h264_amf` ou `libx264` (CPU).
- **Transcrição Local:** `faster-whisper-large-v3-turbo` em **CPU com 8 threads e quantização INT8**.
- **Áudio & Cortes:** Áudio tratado para `-14 LUFS` (limpeza acústica aplicada) e respiro pós-palavra de **180 ms a 220 ms** para preservar fonemas finais e respirações.
- **Linguagem Visual & Vinhetas:** Prioridade absoluta para **Motion Graphics cinéticos em tela cheia (`fullscreen_motion`)** + `RobustSoundBus` SFX + vinhetas finais multi-marca em 3 níveis (`core/brand_bumpers.py`).
- **Portões Humanos:** Nunca iniciar renderização final do Master (`Portão 1`) ou dos cortes curtos (`Portão 2`) sem aprovação explícita do usuário conforme a skill `editor-autonomo`.
