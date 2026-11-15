# ARQUITETURA DO EDITOR (ARCHITECTURE.md)
## Design de Sistemas, Fluxo de Dados e Integrações Técnicas

---

> **Status:** DOCUMENTAÇÃO OPERACIONAL INSTANCIADA — ARQUITETURA MODULAR ENXUTA APROVADA.

---

| Metadado | Especificação |
| :--- | :--- |
| **Documento** | `ARCHITECTURE.md` |
| **Versão** | 1.1.0-alpha |
| **Data de Instanciação** | 11/11/2026 (Alinhado em 15/11/2026) |
| **Stack Principal** | Python 3.11+, FFmpeg 6+, Faster-Whisper Local (CPU INT8), HyperFrames/GSAP, Contratos JSON |
| **Hardware de Referência** | PC Principal Windows com GPU dedicada AMD Radeon RX 6600M 8 GB |
| **Diretório Canônico** | `D:\Drifit\Experimentos_Sandbox\PLANEJAMENTO_REORGANIZACAO_ESTRATEGICA_2026-11-11\documentacao_operacional\` |

---

# 1. VISÃO GERAL DA ARQUITETURA E FLUXO OFICIAL

O Editor é projetado com separação estrita entre a **camada de inteligência editorial** (que analisa e planeja a edição por meio de uma representação estruturada e não destrutiva: `briefing.json`, `edl_longo.json`, `editorial_plan.json`) e o **motor audiovisual local** (que executa corte, áudio, Motion Graphics e renderização determinística sem modificar os originais).

```text
 [ Gravação Original Bruta ] (Somente Leitura — ΔHash = 0)
             │
             ▼
 ┌────────────────────────────────────────────────────────┐
 │ 01_ingest: Ingestão Segura & Inspeção FFprobe          │
 │ - SHA-256 original, WAV 16kHz (ASR) e WAV 48kHz        │
 └────────────────────────────────────────────────────────┘
             │
             ▼
 ┌────────────────────────────────────────────────────────┐
 │ 02_analyze & 03_briefing: Inteligência Editorial       │
 │ - Transcrição local + alinhamento + análise integral   │
 │ - Briefing, EDL não destrutiva e Plano de 6 Camadas    │
 │   (inclui Motion Graphics como parte do MVP)           │
 └────────────────────────────────────────────────────────┘
             │
             ▼
 ┌────────────────────────────────────────────────────────┐
 │ 04_master_16x9: Motor Local — Master 16:9 (Principal)  │
 │ - Limpeza acústica (-14 LUFS), Motion Graphics,        │
 │   B-Rolls, Lower Third e SFX -> Master 1920x1080       │
 └────────────────────────────────────────────────────────┘
             │
             ▼
 ┌────────────────────────────────────────────────────────┐
 │ 05_approval: Revisão e Aprovação Humana                │
 └────────────────────────────────────────────────────────┘
             │ (somente após aprovação do Master 16:9)
             ▼
 ┌────────────────────────────────────────────────────────┐
 │ 06_cortes_9x16 & 07_export: Derivados Verticais 9:16   │
 │ - Reaproveita estrutura editorial aprovada             │
 │ - Reenquadramento 1080x1920, legendas e Motion 9:16    │
 └────────────────────────────────────────────────────────┘
```

---

# 2. SEPARAÇÃO DE DOMÍNIOS NO DISCO (WORKSPACE / BRAND PROFILE / EDITING PROJECT)

Para evitar acoplamento permanente a uma única marca (como o piloto **Dr. Gestão**), a arquitetura planejada separa três domínios independentes:

- **Workspace (`workspace.json`):** configurações de ambiente, hardware (`faster-whisper-large-v3-turbo`, `h264_amf`/`libx264`), política de custódia e caminhos.
- **Brand Profile (`brands/<brand_id>/brand_profile.json` + `assets/`):** identidade visual, paleta, tipografia, zonas seguras, regras fonéticas e kit sonoro/vinhetas de uma pessoa ou empresa (ex.: `dr-gestao` como piloto, sem hardcode no núcleo `core/`).
- **Editing Project (`projects/<project_id>/`):** gravação individual, estado (`project.json`) e artefatos isolados por etapa:

```text
<workspace_root>/
├── workspace.json
├── core/                         # Motor local agnóstico a marca e a modelo de IA
├── ai_adapter/                   # Exposição local (CLI/MCP) para agentes autenticados
├── brands/<brand_id>/            # Brand Profile desacoplado (ex.: dr-gestao)
└── projects/<project_id>/        # Editing Project isolado
    ├── project.json
    ├── 01_ingest/
    ├── 02_analyze/
    ├── 03_briefing/              # Representação não destrutiva (briefing, EDL, plano)
    ├── 04_master_16x9/           # Produto principal 1920x1080
    ├── 05_approval/              # Gate de aprovação do usuário
    ├── 06_cortes_9x16/           # Derivados verticais 1080x1920
    └── 07_export/                # Pacote final + manifestos e laudos
```

---

# 3. CONTRATOS DE DADOS E PRIVACIDADE

### 3.1. Estado Central do Projeto (`project.json`)
Armazena referências imutáveis aos arquivos originais (`sources`: caminho, `sha256`, `bytes`, verificação somente leitura) e ponteiros relativos para os artefatos de cada etapa.

### 3.2. Representação Estruturada da Edição (`edl_longo.json` / `editorial_plan.json`)
Separa a decisão editorial da execução de mídia:
- O plano do **Master 16:9** (`1920×1080`) define cortes, faixas de áudio e camadas de Motion Graphics antes da renderização.
- Os planos de **Cortes 9:16** (`1080×1920`) derivam da edição aprovada, aplicando reenquadramento próprio para o formato vertical.

### 3.3. Limites de Privacidade e IA Agnóstica *(requisito arquitetural)*
- Vídeos e áudios originais locais **não podem ser enviados automaticamente** para serviços externos.
- Qualquer compartilhamento de conteúdo (como transcrições em texto) com serviços ou agentes externos depende de **autorização explícita do usuário**.
- O núcleo não exige chaves de API comerciais; integra-se localmente (via CLI/MCP) aos ambientes autenticados do próprio usuário.

---

# 4. DIRETRIZES DE HARDWARE E ACELERAÇÃO (PC PRINCIPAL)

- **CPU:** Processamento multithread nativo para orquestração, leitura de contêineres e decodificação de áudio.
- **GPU AMD Radeon RX 6600M (8 GB VRAM):**
  - **Objetivo Experimental:** Avaliação empírica do encoder de vídeo acelerado por hardware via FFmpeg (`h264_amf` ou Vulkan), comparando tempo de renderização e qualidade visual com o encoder de CPU (`libx264`).
  - O pipeline sempre possui modo de contingência automático (*fallback*) para CPU caso o encoder de GPU não esteja disponível.
- **Memória RAM:** Gerenciamento com leitura de arquivos em blocos de 64 KB para garantir consumo inferior a 2 GB durante a operação do Editor.
