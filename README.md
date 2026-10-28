# 🎬 Central de Edição Multi-Projetos — Drifit Editor

Estrutura profissional de edição automatizada e assistida por IA, desenhada para gerenciar múltiplos canais, marcas e clientes de forma totalmente isolada e modular.

---

## 🏗️ Estrutura de Pastas

```text
D:\Drifit\Editor\
├── criar_projeto.py            # Cria uma nova marca/projeto com estrutura completa
├── novo_episodio.py            # Cria um episódio herdando automaticamente a identidade da marca
│
├── vortex-edicao\              # Motor central de edição compartilhado (ferramentas e IA)
│   ├── .venv\                  # Ambiente Python isolado (Whisper, Noisereduce, FFmpeg)
│   ├── modelo\                 # Modelos base de código e design system
│   ├── scripts\                # Ferramentas auxiliares (b-rolls, áudio, corte)
│   └── transcrever.py          # Transcrição palavra a palavra
│
└── projetos\                   # Diretório de Marcas e Clientes
    │
    ├── dr-gestao\              # 🔵 PROJETO: Dr. Gestão (Alta Performance em Confecção)
    │   ├── branding\           # Identidade Visual e Regras Centrais (Configurado 1 única vez)
    │   │   ├── config.json     # Cores (#004aad, #8e7de5, #2f97d4), fontes, nomes
    │   │   ├── PREFERENCIAS.md # Manual editorial: Lower Thirds, B-Rolls tela cheia, áudio
    │   │   ├── logos\          # Logos Dr. Gestão, Shopee, Mercado Livre, Shein, TikTok
    │   │   ├── vinhetas\       # Intro-Dr-Gestao.mp4, Logo-Animada.mp4
    │   │   ├── sons\           # Trilha sonora e kit de efeitos
    │   │   └── overlays\       # Cards gráficos e destaques do gancho (VENDAS)
    │   └── episodios\          # Episódios do Dr. Gestão
    │       └── EP-00\
    │           ├── brutos\     # Gravações brutas (carro, estúdio, referências)
    │           ├── workspace\  # Ambiente de montagem (build.py, cenas.py, estilo.css)
    │           └── renders\    # Vídeos finais prontos (EP00_final_completo.mp4)
    │
    └── ozon-tech\              # 🟢 PROJETO: Ozon Tech (Inovação e Tecnologia)
        ├── branding\           # Identidade Visual Central da Ozon Tech
        │   ├── config.json     # Cores Tech (#00d2ff, #3a86ff, #00f0ff), fontes, apresentador
        │   ├── PREFERENCIAS.md # Manual de edição e estética Ozon Tech
        │   ├── logos\          # Logos da Ozon Tech
        │   ├── vinhetas\       # Vinhetas da Ozon Tech
        │   └── sons\           # Efeitos sonoros tech
        └── episodios\          # Episódios da Ozon Tech
```

---

## 🚀 Como Usar no Dia a Dia

### 1. Criar um Novo Episódio para um Projeto Existente

Para iniciar a edição de um novo vídeo sem precisar reconfigurar cores, logos ou vinhetas:

```bash
# Sintaxe:
python novo_episodio.py <projeto> <episodio> [caminho_da_gravacao.mp4]

# Exemplos:
python novo_episodio.py dr-gestao EP-01
python novo_episodio.py dr-gestao EP-01 "D:\Gravacoes\gravacao_estudio.mp4"
python novo_episodio.py ozon-tech EP-01 "D:\Gravacoes\video_ozon.mp4"
```

**O que o comando faz automaticamente:**
1. Cria as pastas `brutos/`, `workspace/` e `renders/` para o episódio.
2. Copia a gravação original para a pasta `brutos/`.
3. Herda diretamente da pasta `branding/` do projeto:
   - Cores e configurações (`config.json`);
   - Diretrizes e manual de edição (`PREFERENCIAS.md`);
   - Todos os logos oficiais (`logos/`);
   - Vinhetas de abertura e encerramento (`vinhetas/`);
   - Efeitos sonoros e trilhas (`sons/`);
   - Overlays e cards gráficos (`overlays/`).
4. Inicia a transcrição com IA e prepara a linha do tempo pronta para edição.

---

### 2. Criar uma Nova Marca / Projeto

Para cadastrar um novo cliente, canal ou parceiro:

```bash
# Sintaxe:
python criar_projeto.py <slug-do-projeto> "Nome de Exibição"

# Exemplo:
python criar_projeto.py novo-parceiro "Nome da Empresa"
```

Isso gera a pasta `projetos/novo-parceiro/branding/` com todos os arquivos de configuração pré-formatados prontos para receber os logos e vinhetas da nova marca.

### 3. Geração de Cortes Verticais 9:16 (Shorts / Reels / TikTok)

Para gerar os 7 cortes verticais de alto impacto de cada episódio com legendas dinâmicas:
- Os arquivos finais são salvos na pasta `renders/cortes_9_16/`.
- **Padrão Obrigatório de Nomenclatura:**
  ```text
  EP<XX>_corte_<YY>_<tema>.mp4
  ```
  *Exemplos:*
  - `EP00_corte_01_problema_vendas.mp4`
  - `EP00_corte_02_estrutura_fabrica.mp4`
  - `EP00_corte_03_troca_canal_venda.mp4`
- Permite rastreabilidade imediata ao baixar, organizar em nuvem (Drive/Notion) ou agendar postagens.

---

## 🎯 Vantagens da Nova Estrutura

- **Isolamento Total:** A identidade e os arquivos do Dr. Gestão nunca se misturam com os da Ozon Tech ou outros clientes.
- **Zero Repetição:** Você define a identidade visual, vinheta e regras de corte apenas uma vez na pasta `branding/`. Todos os episódios futuros daquele canal herdam tudo automaticamente.
- **Rastreabilidade e Segurança:** Arquivos brutos originais ficam sempre preservados na subpasta `brutos/`, sem risco de sobrescrita.
- **Motor Centralizado:** O núcleo técnico (`vortex-edicao`) evolui de forma global, beneficiando todos os projetos simultaneamente.
