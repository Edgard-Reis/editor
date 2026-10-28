# 🎬 Central de Edição Multi-Projetos — Drifit Editor

Estrutura profissional de edição automatizada e assistida por IA, desenhada para gerenciar múltiplos canais, marcas e clientes de forma totalmente isolada e modular.

- **`vortex-edicao/`** — o motor central (transcrição, corte, edição, render). Compartilhado por todos os projetos.
- **`projetos/`** — uma pasta por marca/cliente (`dr-gestao`, `ozon-tech`, ...), cada uma com sua identidade isolada.
- **`arquivo/`** — episódios e artefatos legados (EP-00), fora do caminho do pipeline.

---

## 🏗️ Estrutura de Pastas

```text
D:\Drifit\Editor\
├── criar_projeto.py            # atalho → vortex-edicao/criar_projeto.py (cria uma marca)
├── novo_episodio.py            # atalho → vortex-edicao/novo_episodio.py (cria um episódio)
├── .env                        # ÚNICO arquivo de chaves (raiz; ver "Configuração")
├── .gitignore                  # cobre .env, .venv, media/, renders, caches
├── AVALIACAO_PROJETO.md        # relatório de avaliação do projeto
├── PLANO_IMPLEMENTACAO.md      # plano de correções por fases (com progresso)
│
├── vortex-edicao/              # 🔧 MOTOR CENTRAL (repo próprio, versionado à parte)
│   ├── .venv/                  # ambiente Python isolado (Whisper, Noisereduce, FFmpeg)
│   ├── transcrever.py          # 1) prepara a gravação e transcreve palavra a palavra
│   ├── cortar.py               # 2) corta erros e respiros
│   ├── modelo/
│   │   ├── build.py            # 3) a edição: ferramentas + LINHA DO TEMPO
│   │   ├── ilustra.py          # motions ilustrados
│   │   ├── cenas.py            # kit opcional de cenas e demonstrações (+ cenas.css)
│   │   ├── checa_texto.py      # trava contra motion que transcreve a fala
│   │   ├── webcam_fixa.py      # zoom de câmera dentro da tela sem ampliar a webcam
│   │   └── render_rapido.py    # 4) render rápido com cache + master
│   ├── scripts/                # b-roll (Pexels, Pixabay), áudio, corte
│   ├── captura/                # print e gravação de tela de páginas públicas (Chrome isolado)
│   ├── sons/                   # kit de efeitos e trilha, sintetizados (gerar_sons.py)
│   ├── guia/                   # ESTILO.md, MOTIONS.md, GRAVACAO.md, MELHORIA.md
│   ├── tests/                  # testes (rodam com python puro, sem pytest)
│   │   ├── run_all.py          #   roda todos os testes
│   │   ├── test_encoding.py    #   travas UTF-8 e round-trip de acentos
│   │   └── test_build_w.py     #   W() e sugestão por distância de edição
│   ├── instalar.sh             # instala tudo (uma vez)
│   ├── requirements.txt        # dependências Python (PEP 508)
│   ├── novo_projeto.py|.sh     # cria a pasta de um vídeo (single-project)
│   ├── criar_projeto.py        # cria uma marca/projeto em projetos/
│   ├── novo_episodio.py        # cria um episódio herdando o branding da marca
│   ├── SKILL.md                # instruções pro Claude Code
│   └── .env.exemplo            # modelo de chaves (a real fica na raiz)
│
├── projetos/                   # 📁 Marcas e Clientes (isoladas entre si)
│   ├── dr-gestao/              # 🔵 Dr. Gestão (Alta Performance em Confecção)
│   │   ├── branding/           #   identidade (config.json, PREFERENCIAS.md, logos, vinhetas, sons, overlays)
│   │   └── episodios/EP-00/    #   brutos/ · workspace/ · renders/
│   └── ozon-tech/              # 🟢 Ozon Tech (Inovação e Tecnologia)
│       ├── branding/
│       └── episodios/
│
├── arquivo/                    # 📦 legado fora do pipeline
│   ├── EP-00-raiz/             #   artefatos antigos na raiz
│   ├── EP-00-projetos/         #   snapshots antigos por projeto
│   └── README.md
│
└── Identidade visual/          # material de referência de marca (fora do versionamento de mídia)
```

> **`media/` unificado:** todo o pipeline usa `media/` (não existe mais `midia/`). Cada episódio/workspace tem sua `media/` com `base.mp4`, `palavras_saida.json`, b-roll, etc. `renders/` guarda os MP4 finais.

---

## ⚙️ Configuração (`.env`)

Existe **um único `.env`, na raiz** (`D:\Drifit\Editor\.env`). Os resolvers sobem a árvore a partir de qualquer subpasta, então `transcrever.py`, `broll_*.py` etc. encontram a mesma cópia.

```bash
ELEVENLABS_API_KEY=          # opcional; vazio → Whisper local (grátis)
PEXELS_API_KEY=              # opcional; b-roll grátis
PIXABAY_API_KEY=             # opcional; b-roll grátis
```

Copie de `vortex-edicao/.env.exemplo` e preencha as chaves que quiser. **Nunca** commite o `.env` (já está no `.gitignore`).

---

## 🚀 Pipeline (um episódio, do bruto ao MP4)

```bash
# 0) criar o episódio (herda o branding da marca automaticamente)
python novo_episodio.py dr-gestao EP-01 "D:\Gravacoes\gravacao.mp4"

# 1) transcrever (prepara media/ e gera roteiro palavra a palavra)
python vortex-edicao/transcrever.py projetos/dr-gestao/episodios/EP-01

# 2) cortar erros e respiros (anote os trechos no roteiro e passe --remover)
python vortex-edicao/cortar.py projetos/dr-gestao/episodios/EP-01 --remover 12.3-15.8

# 3) editar: escreva a LINHA DO TEMPO no workspace/build.py e rode
cd projetos/dr-gestao/episodios/EP-01/workspace
python build.py

# 4) renderizar rápido (cache + master)
python render_rapido.py -o ../renders/v1.mp4
```

### Criar uma nova marca

```bash
python criar_projeto.py novo-parceiro "Nome da Empresa"
# gera projetos/novo-parceiro/branding/ com config.json, PREFERENCIAS.md,
# referencias/ e scripts/ prontos
```

### Cortes verticais 9:16 (Shorts / Reels / TikTok)

- Saída em `renders/cortes_9_16/`.
- Nomenclatura obrigatória: `EP<XX>_corte_<YY>_<tema>.mp4` (ex.: `EP00_corte_01_problema_vendas.mp4`).

---

## 🧪 Testes

Sem dependências (não usa pytest). Roda com o Python da `.venv`:

```bash
# todos
python vortex-edicao/tests/run_all.py

# ou individualmente
python vortex-edicao/tests/test_encoding.py
python vortex-edicao/tests/test_build_w.py
```

- **`test_encoding.py`** — round-trip de acentos (ção, ç, ★) em JSON/texto e presença da trava UTF-8 nos scripts.
- **`test_build_w.py`** — `W("frase")`, `fim=True`, `apos=` e as sugestões por distância de edição no erro.

Sai com código 0 se tudo passar, 1 se algo falhar (pronto pra CI).

---

## 🎯 Vantagens da Estrutura

- **Isolamento total:** a identidade do Dr. Gestão nunca se mistura com a da Ozon Tech ou de outros clientes.
- **Zero repetição:** identidade, logos, vinhetas e regras ficam uma única vez no `branding/`; todos os episódios herdam.
- **Rastreabilidade e segurança:** os brutos originais ficam preservados em `brutos/`, sem risco de sobrescrita.
- **Motor centralizado:** o núcleo (`vortex-edicao`) evolui globalmente e beneficia todos os projetos.
- **Legado isolado:** o EP-00 e artefatos antigos ficam em `arquivo/`, fora do caminho do pipeline.

---

## 📚 Documentação

- `AVALIACAO_PROJETO.md` — avaliação completa do estado do projeto (itens, riscos, status).
- `PLANO_IMPLEMENTACAO.md` — plano de correções por fases, com checklist de progresso.
- `vortex-edicao/guia/` — ESTILO.md (regras de estilo), MOTIONS.md (princípios de motion), GRAVACAO.md (como gravar), MELHORIA.md (melhoria contínua).
- `vortex-edicao/SKILL.md` — instruções pro Claude Code.
