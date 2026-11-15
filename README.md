# Editor — Pós-Produção Audiovisual Assistida por IA

Ferramenta local de pós-produção audiovisual assistida por inteligência artificial, projetada para transformar gravações brutas em vídeos editados profissionalmente com controle editorial do usuário.

> **Perfil piloto inicial:** **Dr. Gestão** (`projetos/dr-gestao/`). O núcleo do produto é concebido para suportar múltiplas marcas e perfis de forma isolada, sem acoplamento permanente a um único cliente.

---

## Fluxo Principal do Produto

```text
Gravação original completa
  → Análise e planejamento editorial
  → Master completo 16:9 (com Motion Graphics e acabamento audiovisual)
  → Revisão e aprovação do usuário
  → Derivados verticais 9:16
```

- **Inteligência editorial:** analisa a gravação completa para compreender temas e narrativa, estruturar a edição, remover erros/repetições e selecionar cortes coerentes e contextualizados (sem prometer viralização automática nem substituir a aprovação humana).
- **Acabamento audiovisual e Motion Graphics no MVP:** tratamento acústico (`-14 LUFS`, True Peak `-1.0 dBFS`), ritmo visual, títulos animados, legendas dinâmicas, destaques de palavras, *lower thirds*, *callouts*, elementos explicativos, zooms, transições, vinheta e encerramento.
- **Derivados 9:16 pós-aprovação:** cortes verticais (`1080×1920`) gerados somente após a aprovação do Master 16:9, reaproveitando a estrutura editorial com reenquadramento próprio para o formato vertical.

---

## Arquitetura e Filosofia

- **Separação de domínios:**
  - **Workspace:** configurações de hardware, caminhos e políticas locais de custódia.
  - **Brand Profile:** identidade visual, paleta, tipografia, léxico, regras de áudio e assets de uma marca (ex.: `projetos/dr-gestao/branding/`).
  - **Editing Project:** gravação individual, transcrição, plano de edição e artefatos isolados por episódio.
- **Planejamento separado da execução:** a inteligência editorial gera representações estruturadas e não destrutivas da edição; o motor local (Python + FFmpeg + HyperFrames/GSAP) executa cortes, áudio e renderização preservando os arquivos originais intactos (somente leitura).
- **IA agnóstica sem chaves comerciais obrigatórias:** o Editor foi projetado para operar com ambientes e agentes de IA autenticados pelo próprio usuário, sem exigir chaves de APIs comerciais pagas como condição de funcionamento.
- **Privacidade local:** vídeos e áudios originais locais **não** são enviados automaticamente para serviços externos.

---

## Estrutura do Repositório

```text
D:\Drifit\Editor\
├── README.md                     # Apresentação principal do projeto
├── GEMINI.md                     # Regras operacionais e governança de agentes
├── criar_projeto.py              # Atalho -> vortex-edicao/criar_projeto.py (cria marca)
├── novo_episodio.py              # Atalho -> vortex-edicao/novo_episodio.py (cria episódio)
│
├── vortex-edicao/                # Motor audiovisual local (transcrição, corte, build, render)
│   ├── transcrever.py            # Transcrição local (Faster-Whisper / Whisper)
│   ├── cortar.py                 # Remoção de erros e pausas
│   ├── modelo/                   # build.py, cenas.py, ilustra.py, render_rapido.py
│   ├── tests/                    # Suíte base (run_all.py)
│   ├── requirements.txt          # Dependências Python
│   └── .env.exemplo              # Modelo opcional de variáveis de ambiente
│
├── motion_library/               # Biblioteca reutilizável de Motion Graphics (ex.: titulo_heroi T10)
├── tools/
│   ├── COMPATIBILITY_MATRIX.md   # Matriz de versões homologadas da toolchain
│   └── hyperframes/              # Manifestos HyperFrames 0.9.5, GSAP 3.14.2 e toolchain local
│
├── projetos/                     # Brand Profiles e episódios isolados por marca
│   ├── dr-gestao/                # Perfil piloto (branding/, motion-system/, episodios/)
│   └── ozon-tech/                # Exemplo de isolamento multi-marca
│
└── docs/
    ├── PLANO_MESTRE_EDITOR.md    # Diretrizes técnicas e restrições de hardware
    ├── AUDIO_PIPELINE.md         # Especificação técnica de áudio
    ├── VIDEO_PIPELINE.md         # Especificação técnica de vídeo
    ├── VISUAL_IDENTITY.md        # Identidade visual e motion
    └── operacional/              # Documentação operacional vigente (PRD, Arquitetura, Roadmap, Decisões)
```

---

## Pré-requisitos e Configuração

### Pré-requisitos de ambiente
- **Python:** 3.11+ (referência: `3.11.15`)
- **Node.js:** v20+ (homologado: `v22.18.0`) para execução local do HyperFrames CLI
- **FFmpeg e FFprobe:** `9.0.2-essentials`
  > **Nota importante:** ainda **não existe script de bootstrap automatizado** para baixar os binários `ffmpeg.exe` e `ffprobe.exe` em um clone novo. Como os executáveis ultrapassam o limite de 100 MB do GitHub, eles ficam fora do Git e devem ser obtidos manualmente (ex.: build `9.0.2-essentials` de `gyan.dev`) e colocados em `tools/hyperframes/bin/windows-x64/` (conforme hashes registrados em [TOOLCHAIN_MANIFEST.json](tools/hyperframes/TOOLCHAIN_MANIFEST.json)) ou disponíveis no `PATH` do sistema.

### Instalação das dependências

1. **Ambiente Python** (a partir da raiz do repositório):
   ```powershell
   python -m venv vortex-edicao\.venv
   vortex-edicao\.venv\Scripts\pip install -r vortex-edicao\requirements.txt
   ```
2. **Toolchain Node.js (HyperFrames):**
   ```powershell
   cd tools\hyperframes
   npm ci
   ```
3. **Variáveis de ambiente opcionais (`.env`):**
   ```powershell
   copy vortex-edicao\.env.exemplo .env
   ```
   Sem chaves preenchidas, a transcrição utiliza o Whisper local. Nunca versione o arquivo `.env`.

---

## Como Executar e Testar o que Já Funciona

### Pipeline atual por episódio (`vortex-edicao/`)
```powershell
# 1) Criar episódio herdando o branding da marca
python novo_episodio.py dr-gestao EP-01 "D:\Gravacoes\gravacao.mp4"

# 2) Transcrever áudio localmente
python vortex-edicao\transcrever.py projetos\dr-gestao\episodios\EP-01

# 3) Cortar trechos com erro
python vortex-edicao\cortar.py projetos\dr-gestao\episodios\EP-01 --remover 12.3-15.8

# 4) Compilar e renderizar a partir do workspace do episódio
cd projetos\dr-gestao\episodios\EP-01\workspace
python build.py
python render_rapido.py -o ..\renders\v1.mp4
```

### Testes unitários disponíveis
```powershell
# Suíte base do motor (encoding e utilitário de busca W)
python vortex-edicao\tests\run_all.py

# Testes do componente Motion Library T10 (com pytest)
$env:PYTHONPATH = "motion_library\components\titulo_heroi"
python -m pytest -v motion_library\components\titulo_heroi\test_titulo_heroi.py

# Testes do núcleo de composição e som (branding Dr. Gestão)
python -m pytest -v projetos\dr-gestao\branding\scripts\test_nucleo.py
```

> **Pendência conhecida:** em `projetos/dr-gestao/branding/scripts/test_integracao_cenas.py`, o teste `test_04_som_roteia_para_robust_sound_bus` falha quando executado diretamente de `branding/scripts/` porque `cenas.py` procura `sons/whoosh_curto.wav` relativo ao diretório do script antes de recorrer ao som reserva (`clique2`).

---

## Estado Atual do Desenvolvimento e Próximas Etapas

| Frente | Estado | Observação |
|---|---|---|
| Motor base (`vortex-edicao/`) e presets Dr. Gestão | **Implementado** | Scripts de ingestão, transcrição, corte, `cenas.py`, `estagio.py`, `som.py` e renderização local ativos. |
| Biblioteca de Motion Graphics (`motion_library/`) | **Parcial** | Componente `titulo_heroi` (`T10`) implementado e testado (`16/16`); demais componentes em consolidação. |
| Fluxo unificado Master 16:9 → Aprovação → 9:16 e adaptador de IA agnóstico | **Em desenvolvimento (Sandbox)** | Arquitetura modular (`Workspace` / `Brand Profile` / `Editing Project`) e adaptador local CLI/MCP em evolução em sandbox antes de promoção para este repositório. |
| Bootstrap automatizado de FFmpeg/FFprobe | **Planejado** | Binários documentados no manifesto, sem instalador automático ainda. |

### Próximas etapas
1. Corrigir a resolução de caminhos de áudio em `test_integracao_cenas.py` / `cenas.py` e adicionar script de bootstrap/verificação da toolchain FFmpeg.
2. Promover para o repositório principal, após homologação, a arquitetura modular unificada (`Workspace`, `Brand Profile`, `Editing Project`), o fluxo ponta a ponta `Master 16:9 → Aprovação → Derivados 9:16` e o adaptador local de IA agnóstico.

---

## Documentação de Referência

- **Operacional vigente:**
  - [PRD_MASTER.md](docs/operacional/PRD_MASTER.md) — Escopo oficial do produto e requisitos do MVP
  - [ARCHITECTURE.md](docs/operacional/ARCHITECTURE.md) — Arquitetura, separação de domínios e privacidade
  - [ROADMAP.md](docs/operacional/ROADMAP.md) — Sequenciamento das etapas do MVP
  - [DECISIONS.md](docs/operacional/DECISIONS.md) — Decisões arquiteturais (ADRs)
  - [AGENT_GUIDELINES.md](docs/operacional/AGENT_GUIDELINES.md) — Diretrizes de atuação e segurança
  - [TESTS_AND_EVIDENCE.md](docs/operacional/TESTS_AND_EVIDENCE.md) — Registro de testes e evidências
- **Técnica e Governança:**
  - [GEMINI.md](GEMINI.md) · [PLANO_MESTRE_EDITOR.md](docs/PLANO_MESTRE_EDITOR.md) · [AUDIO_PIPELINE.md](docs/AUDIO_PIPELINE.md) · [VIDEO_PIPELINE.md](docs/VIDEO_PIPELINE.md) · [VISUAL_IDENTITY.md](docs/VISUAL_IDENTITY.md) · [COMPATIBILITY_MATRIX.md](tools/COMPATIBILITY_MATRIX.md)
