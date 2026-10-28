# 🛠️ Plano de Implementação — Drifit Editor

> Origem: [`AVALIACAO_PROJETO.md`](AVALIACAO_PROJETO.md) (28/10/2026)
> Regra: **um bloco por vez** → executar o *Check* → só então seguir adiante.
> Nada de "melhorias" antes de fechar os itens 🔴 e 🟠.

---

## ✅ Progresso

### Fase 1 (Crítico) — CONCLUÍDA em 28/10/2026

| Tarefa | Status | Evidência |
|---|---|---|
| **1.1** `encoding="utf-8"` na fonte | ✅ | `modelo/`: `build.py` 10×, `checa_texto.py` 2×, `render_rapido.py` 2×. Varredura global: **0 suspeitas reais** (as4 restantes são falso-positivo — `encoding` está na linha seguinte). |
| **1.1** teste funcional | ✅ | `W()` com `encoding="utf-8"` → 6/6 frases OK; controle **sem** encoding → `empresa de confeccao`, `menos esforco`, `ponto de interrogacao` **FALHAM** (reproduz o defeito). |
| **1.2** não sobrescreve workspace | ✅ |2ª execução no EP-TESTE: `0 nova(s), 67 já existente(s) mantida(s)` + hash de `build.py` idêntico. Flag `--forcar` criada. |
| **1.3** copia subpastas | ✅ | `workspace/overlays/transicoes/transicao_wipe_drgestao_16x9.mov` → `True` |
| Compilação | ✅ | todos os `.py` (exceto `.venv`) compilam sem erro |

**Escopo que cresceu durante a Fase 1 (mesma classe de defeito):**
- `encoding="utf-8"` também aplicado em `transcrever.py` (3), `broll_pexels.py` (3),
  `criar_vinheta.py` (4), `projetos/EP-00/build.py` (3) e
  `workspace/build.py` (3) — estes estavam *parcialmente* corrigidos.
- **Novo defeito descoberto pelo teste** → `UnicodeEncodeError` ao imprimir
  `⚠`/`✗`/`→` quando `stdout` vai para um pipe com locale cp1252 (o próprio
  check 1.2 quebrou na metade). Aplicada **trava de saída UTF-8 em 18 arquivos**
  (todos os pontos de entrada: `novo_episodio`, `criar_projeto`, `transcrever`,
  `cortar`, `build`, `checa_texto`, `render_rapido`, `broll_*`, `criar_vinheta`,
  nas 3 cópias existentes).
- `novo_episodio.py` ganhou `argparse` + resumo de cópias + aviso de proteção.

**Artefatos de teste usados:** `projetos/dr-gestao/episodios/EP-TESTE/`
(criado e **removido** ao final — só `EP-00` permanece).

**⚠ Pendência da Fase 1:** `novo_episodio.py` e `criar_projeto.py` continuam
duplicados em2 lugares (raiz e `vortex-edicao/`) — alterados em conjunto e
**verificados byte a byte idênticos**, mas a sincronização é manual até a Tarefa 3.1.

### Fase 2 (Alto) — PARCIALMENTE CONCLUÍDA em 28/10/2026

| Tarefa | Status | Evidência |
|---|---|---|
| **2.1** `.env` único + `.gitignore` raiz | ✅ | `vortex-edicao/.env` e `projetos/dr-gestao/.env` (idênticos, SHA256 conferido) **removidos** — backup em `Temp\opencode\backup_env_20261028\`. Resolvers de `transcrever.py`/`broll_pexels.py`/`broll_pixabay.py` agora sobem a árvore de pastas → testados de `EP-00/workspace/` (subpasta funda): **3/3 leem o `.env` da raiz**. Raiz ganhou `.gitignore` agressivo (segredos, mídia, `EP-00/`, `arquivo/`, workspaces, `settings.local.json`). |
| **2.2** `.claude/settings.local.json` | ✅ | `"defaultMode": "bypassPermissions"` **removido**; allowlist enxugada de ~90 → **13** entradas (só leitura: ffprobe/grep/sed/head/tail/python -c + o pipeline build/checa_texto/render_rapido). JSON válido. Efeito em sessão nova. |
| **2.4** dependências declaradas | ✅ | `vortex-edicao/requirements.txt` criado (7 pacotes, versões da .venv validada, todos parseiam como PEP 508). `instalar.sh` → `pip install -r requirements.txt` + aponta `.env` para a raiz. `novo_projeto.sh` → caminho `D:/Drifit/Editor/projetos` hardcoded removido (usa `VORTEX_PROJETOS` ou `<raiz>/projetos`). `transcrever.py`: fallback do Whisper agora acha `whisper.exe` da `.venv` (antes `shutil.which` → `None`); `except ImportError` → `except Exception` para também cair no fallback se o *download* do modelo falhar. |
| **2.3** versionamento | ✅ | **`vortex-edicao`** commitado (`b0c81d9`, 20 arquivos: encoding, multi-projeto, desacoplamento, requirements). **Raiz** `git init` + commit (`77cfff1`, 199 arquivos: gitignore, docs, wrappers). Verificado: **0** `.env` rastreado em ambos, **0** `settings.local.json`, nenhum segredo no histórico. Mídia/legados (.mp4/.wav/EP-00/arquivo) fora do repositório. |

### Fase 3 (Médio) — EM ANDAMENTO (28/10/2026)

| Tarefa | Status | Evidência |
|---|---|---|
| **3.1** eliminar duplicação + destino dos EP-00 legados | ✅ | **EP-00 legados movidos** para `arquivo/` (sem apagar): `Editor\EP-00` → `arquivo/EP-00-raiz/` (50 arq., 3.467 MB) e `projetos\EP-00` → `arquivo/EP-00-projetos/` (108 arq., 4.935 MB) — contagens/tamanhos conferidos intactos; `arquivo/README.md` documenta o que é cada um. **Duplicação eliminada:** `novo_episodio.py` e `criar_projeto.py` da raiz viraram *wrappers* de 13 linhas que delegam para as implementações canônicas em `vortex-edicao/` (padrão já usado por `novo_projeto.py`). `projetos/` agora contém só `dr-gestao/` e `ozon-tech/`. |
| **3.2** unificar `media/`/`midia/` | ✅ | **Regra segura:** substituída só a string `midia/` (com barra) → `media/`; nomes de variável/parâmetro (`pip_stage(de, ate, midia)`, `elem_midia`, `card_midia`, `class="midia"`, `midia.lower()`) **intactos** (29 ocorrências preservadas). **63 substituições em código/docs** (modelo/cenas.py, broll_*.py, criar_vinheta.py, branding/*, workspace/*, SKILL.md, README, PREFERENCIAS.md) + 2 especiais sem barra (`novo_episodio.py` mkdir, `novo_projeto.sh`). **Move físico:** 28 arquivos de `workspace/midia/` → `workspace/media/` (sem colisão), `midia/` removida. **Regenerado** `index.html`/`partes.json` via `build.py` (exit 0, `checa_texto: 0 problema(s)`, 70 clips) → 0 `midia/` restante, 14 refs `media/` resolvem. |
| **3.3** desacoplar marca do motor | ✅ | `transcrever.py`: `PROMPT_CONTEXTO` hardcoded virou `prompt_contexto(dir_projeto)` que lê `config.json → preferencias_edicao.lexicon_transcricao` (fallback genérico). Testado 5 casos (workspace real → lexicon; sem config / lexicon vazio / sem seção / JSON quebrado → genérico, sem crash). Lexicon do Dr. Gestão movido para `branding/config.json` + workspace. `build.py`: cabeçalho `LINHA DO TEMPO — DR. GESTÃO` → `— EPISÓDIO ATUAL`. `cenas.py` (motor): `pip_stage(badge="DR. GESTÃO")` → `badge=""` + render condicional; branding/workspace mantêm `"DR. GESTÃO"` (camadas corretas); EP-00 usa 27 badges explícitos. |
| **3.4** `criar_projeto.py` | ✅ | Slug validado por regex `^[a-z0-9]+(-[a-z0-9]+)*$` (rejeita `..`, `/`, acentos, hífen nas bordas → `exit 2`). Projeto já existe → `exit 1` (não `0`). Paleta **neutra** (`#e5e7eb`/`#9ca3af`/`#6b7280`) em vez da Ozon Tech; `PREFERENCIAS.md` template com cores `TODO`; cria `referencias/` e `scripts/`; adiciona `lexicon_transcricao` placeholder. Testado (slugs inválidos, dr-gestao existente → exit 1, projeto novo → paleta neutra + 6 pastas). Artefatos de teste removidos. |
| **3.5** robustez | ✅ | `cortar.py`: guarda para `palavras.json` vazio/inexistente (evita `IndexError` em `w[0]`/`w[-1]`) + validação de cada `--remover` (`inicio < fim`, formato). `render_rapido.py`: ffprobe sem stream de áudio → mensagem clara (evita `IndexError` em `.split()[0]`). `build.py` `W()`: no `SystemExit` agora sugere as 3 frases mais próximas por distância de edição. Todos testados (casos 1–5 passam, sem `IndexError`). Nota: os `sys.exit` do cortar.py usam `_stdout_sys` (o arquivo só importa `sys as _stdout_sys`) — corrigido. |

**Observação sobre o `.env` da raiz (informativo):**
`ELEVENLABS_API_KEY` está **vazia** (por design → transcrição cai no Whisper
local), `PEXELS_API_KEY` contém só o placeholder `free` (não é chave real) e
`PIXABAY_API_KEY` tem uma chave de verdade (33 chars). Nada disso foi alterado.

### Fase 4 (Melhorias) — CONCLUÍDA em 28/10/2026

| Tarefa | Status | Evidência |
|---|---|---|
| **4.3** cache do Whisper para fora do projeto | ✅ | `transcrever.py`: `CACHE_HF` fixo em `.cache/huggingface` virou `_cache_huggingface()` platform-aware (respeita `HF_HOME` se definido; senão `%LOCALAPPDATA%\huggingface` no Windows, `~/.cache` no Unix). **Migração física:** 1.546 MB movidos para `C:\Users\Edgard\AppData\Local\huggingface` (o `Move-Item` preservou o layout *flat* antigo e o `snapshot_download` re-baixou no layout `hub/` → **havia 2 cópias, ~3 GB**; removidos os leftovers flat orfãos, restando só o `hub/` íntegro). Teste fim-a-fim: `WhisperModel` **transcreve** do novo local sem re-download. `.cache/` já estava no `.gitignore`; pasta `.cache/` da raiz removida. |
| **4.1** testes automatizados | ✅ | `vortex-edicao/tests/` criado (sem pytest — scripts Python puros): `test_encoding.py` (7 testes: round-trip de acentos em JSON/texto, `ensure_ascii=False`, trava de saída UTF-8, prova de que cp1252 quebraria sem a trava, presença da trava nos scripts) + `test_build_w.py` (7 testes: `_n`, distância de edição, `W()`, `fim=True`, `apos=`, sugestões no erro — extrai as funções reais do `build.py` via AST e roda contra fixture, sem disparar I/O do import) + `run_all.py`. **14/14 passam, exit 0.** Aproveitando: `modelo/ilustra.py` estava **sem** a trava de saída UTF-8 (defensivo adicionado). |
| **4.2** READMEs atualizados | ✅ | `README.md` raiz reescrito: árvore real (`.agents/`, `arquivo/`, `Identidade visual/`, `projetos/` com `dr-gestao`/`ozon-tech`, wrappers), seção de configuração (`.env` único na raiz), **pipeline** `transcrever → cortar → build → render_rapido`, seção de **testes**, nota de `media/` unificado. `vortex-edicao/README.md`: fluxo manual corrigido, árvore com `tests/`/`requirements.txt`/`criar_projeto.py`/`novo_episodio.py`/`broll_pixabay.py`, seção de testes, nota `media/`. |
| **4.4** consolidação de docs | ✅ | **Pare 1** (`vortex-edicao`): `SKILL.md` (109→95 l.) deixou de duplicar o fluxo de melhoria contínua e agora aponta para `guia/MELHORIA.md` (dono canônico do processo, 30 l. intactos). **Pare 2** (Dr. Gestão): `.agents/skills/dr-gestao/SKILL.md` (182→70 l.) deixou de duplicar identidade/paleta/b-roll/split-stage/checklist/histórico e agora manda só no **procedimento**, delegando as **regras** ao único dono `branding/PREFERENCIAS.md` (130 l., que mantém o histórico de melhorias). Checklist (§6 skill) era cópia verbatim de `PREFERENCIAS.md` §10 → virou ponteiro. |
| **4.5** ajustes menores | ✅ | `modelo/build.py`: `_durwav()` ganhou cache `_DURWAV_CACHE` (memoiza; `sfx()` reabria o mesmo `.wav` a cada chamada). `cortar.py` (2×) e `transcrever.py` (1×): `json.dump(..., open(...))` sem `with` → `with open(...) as _f`. Verificado: 0 `json.dump` com `open()` inline restante; os 3 arquivos compilam. |

**Total de testes:** 14/14 (`run_all.py` exit 0). **Commits Fase 4:** ver tabela resumo abaixo.

---

## Fase 0 — Estado atual (para reconferir após compactação de contexto)

Reconferir antes de começar:

```powershell
# encoding ausente no modelo (esperado:0,0,0 para os três)
$f=@('vortex-edicao\modelo\build.py','vortex-edicao\modelo\checa_texto.py','vortex-edicao\modelo\render_rapido.py')
foreach($x in $f){ "{0,-45} utf8={1}" -f $x,([regex]::Matches((Get-Content $x -Raw),'encoding="utf-8"')).Count }

# cópias idênticas em dois lugares (esperado: True,True)
(Get-FileHash criar_projeto.py).Hash -eq (Get-FileHash vortex-edicao\criar_projeto.py).Hash
(Get-FileHash novo_episodio.py).Hash  -eq (Get-FileHash vortex-edicao\novo_episodio.py).Hash

# .env duplicado (esperado: True,True)
(Get-FileHash .env).Hash -eq (Get-FileHash vortex-edicao\.env).Hash
(Get-FileHash .env).Hash -eq (Get-FileHash projetos\dr-gestao\.env).Hash

# git da skill (esperado: 14 M + 4 ??)
git -C vortex-edicao status --short
```

Referência de "como ficou certo": `projetos/dr-gestao/episodios/EP-00/workspace/`.

---

## 🔴 Fase 1 — Crítico

### Tarefa 1.1 · `encoding="utf-8"` no `vortex-edicao/modelo/`

**Arquivo:** `vortex-edicao/modelo/build.py`

| Linha | Hoje | Passa a ser |
|---|---|---|
| 27 | `json.load(open(AQUI / "media/palavras_saida.json"))` | `..., encoding="utf-8"))` |
| 29 | `json.load(open(AQUI / "config.json"))` | `..., encoding="utf-8"))` |
| 53 | `(AQUI / f"logos/{nome}.svg").read_text()` | `.read_text(encoding="utf-8")` |
| 208 | `(AQUI / "cenas.py").read_text()` | `.read_text(encoding="utf-8")` |
| 259 | `(AQUI / "webcam_fixa.py").read_text()` | `.read_text(encoding="utf-8")` |
| 269–270 | `estilo.css` / `ilustra.css` / `cenas.css` `.read_text()` | `.read_text(encoding="utf-8")` |
| 303 | `(AQUI / "index.html").write_text(html)` | `.write_text(html, encoding="utf-8")` |
| 310 | `open(AQUI / "partes.json", "w")` | `open(AQUI / "partes.json", "w", encoding="utf-8")` |

**Arquivo:** `vortex-edicao/modelo/checa_texto.py` — linha 42

```python
# antes
ruins = problemas(alvo.read_text(), json.load(open(AQUI / "media/palavras_saida.json")))
# depois
ruins = problemas(alvo.read_text(encoding="utf-8"),
                  json.load(open(AQUI / "media/palavras_saida.json", encoding="utf-8")))
```

**Arquivo:** `vortex-edicao/modelo/render_rapido.py`

- linha 126 → `tmp.write_text(h, encoding="utf-8")`
- linha 201 → `p = json.load(open(AQUI / "partes.json", encoding="utf-8"))`

> Nota: em `render_rapido.py` também há `print(...·...)` (linha 213) — trocar a
> `·` literal por `|` evita `UnicodeEncodeError` em console cp1252 (foi assim na
> versão corrigida do EP-00).

**✅ Check 1.1**

```powershell
& vortex-edicao\.venv\Scripts\python.exe -c "import pathlib,py_compile;[py_compile.compile(str(p),doraise=True,cfile=r'C:\Users\Edgard\AppData\Local\Temp\opencode\_pc.tmp') for p in pathlib.Path('vortex-edicao/modelo').glob('*.py')];print('modelo OK')"
# e o teste que falhava:
& vortex-edicao\.venv\Scripts\python.exe -c "import json,re,unicodedata,pathlib;A=pathlib.Path('projetos/EP-00');PAL=json.load(open(A/'media/palavras_saida.json',encoding='utf-8'));n=lambda s:re.sub(r'[^a-z0-9]','',''.join(c for c in unicodedata.normalize('NFD',s.lower()) if unicodedata.category(c)!='Mn'));T=[n(p['w']) for p in PAL];print('frases OK:',all((' '.join(n(x) for x in f.split())) in ' '.join(T) for f in ['empresa de confeccao','menos esforco','ponto de interrogacao']))"
```

Esperado: `modelo OK` e `frases OK: True`.

---

### Tarefa 1.2 · `novo_episodio.py` não sobrescreve workspace existente

**Arquivo:** `novo_episodio.py` (raiz) **e** `vortex-edicao/novo_episodio.py`
(idênticos — alterar os dois, ou melhor: eliminar a duplicação, ver Tarefa 3.1)

- Bloco 2 (linhas 89–92): só copiar se `not (workspace_dir / arq).exists()`,
  contando pulados e imprimindo aviso.
- Blocos 3.2–3.6 (linhas 105–132): mesma guarda, com contador
  `pulados`/`novos`.
- Aceitar flag `--forcar` para sobrescrever de propósito (e avisar em vermelho).

```python
def copia_se_novo(src, dst, estado):
    if dst.exists():
        estado["pulados"] += 1
        return
    shutil.copy2(src, dst)
    estado["novos"] += 1
```

**✅ Check 1.2** — criar episódio, rodar de novo, conferir que não muda:

```powershell
python novo_episodio.py dr-gestao EP-TESTE
(Get-FileHash projetos\dr-gestao\episodios\EP-TESTE\workspace\build.py).Hash
python novo_episodio.py dr-gestao EP-TESTE
(Get-FileHash projetos\dr-gestao\episodios\EP-TESTE\workspace\build.py).Hash   # igual
Remove-Item -Recurse projetos\dr-gestao\episodios\EP-TESTE                     # limpar teste
```

---

### Tarefa 1.3 · `novo_episodio.py` copia subdiretórios

**Arquivo:** `novo_episodio.py`, blocos 3.2–3.5 (logos, vinhetas, sons, overlays).

Trocar o loop `if item.is_file()` por:

```python
if (branding_dir / "overlays").exists():
    shutil.copytree(branding_dir / "overlays", workspace_dir / "overlays", dirs_exist_ok=True)
```

Resultado: `overlays/transicoes/*` passa a ir junto (prometido no
`SKILL.md` do Dr. Gestão, Passo 3.1).

**✅ Check 1.3**

```powershell
python novo_episodio.py dr-gestao EP-TESTE
Test-Path projetos\dr-gestao\episodios\EP-TESTE\workspace\overlays\transicoes\transicao_wipe_drgestao_16x9.mov   # True
Remove-Item -Recurse projetos\dr-gestao\episodios\EP-TESTE
```

---

## 🟠 Fase 2 — Alto

### Tarefa 2.1 · Um único `.env` + `.gitignore` na raiz

1. Manter `D:\Drifit\Editor\.env` como fonte única (já contém as 3 chaves).
2. Criar `D:\Drifit\Editor\.gitignore`:

```gitignore
.env
.cache/
.venv/
__pycache__/
*.pyc
*.mp4
*.mov
*.wav
projetos/*/episodios/*/workspace/media/
projetos/*/episodios/*/workspace/renders/
EP-00/
projetos/EP-00/
.claude/settings.local.json
```

3. Fazer os leitores de `.env` procurarem **subindo a árvore** (hoje cada
   script olha só na sua pasta):
   - `vortex-edicao/transcrever.py:31-38` (`chave_elevenlabs`)
   - `vortex-edicao/scripts/broll_pexels.py:22-29` (`chave`)
   - `vortex-edicao/scripts/broll_pixabay.py` (mesmo padrão)

```python
def acha_env(chave):
    for base in (Path(__file__).resolve().parent, *Path(__file__).resolve().parents):
        env = base / ".env"
        if env.exists():
            for l in env.read_text(encoding="utf-8").splitlines():
                if l.startswith(chave + "="):
                    return l.split("=", 1)[1].strip().strip('"')
    return os.environ.get(chave)
```

4. Depois: apagar `vortex-edicao/.env` e `projetos/dr-gestao/.env` (ou deixar
   um aviso `.env.mover-para-a-raiz.txt`) — **decisão do usuário**.

**✅ Check 2.1** — `python -c` imprimindo `len(chave)>0` para as 3 chaves a partir
de qualquer subpasta; e `git -C vortex-edicao check-ignore -v .env` não reclamando.

> ⚠ **Decisão necessária:** apagar os `.env` duplicados ou manter por segurança?

---

### Tarefa 2.2 · `.claude/settings.local.json`

1. Trocar `"defaultMode": "bypassPermissions"` pelo modo padrão
   (`"default"` ou remover a chave).
2. Enxugar a lista `allow` (as ~90 entradas são histórico de uma sessão).
3. Adicionar `.claude/settings.local.json` ao `.gitignore` da raiz (já previsto
   na Tarefa 2.1).

**✅ Check 2.2** — abrir uma sessão nova e confirmar que pede permissão antes de
rodar comandos destrutivos.

> ⚠ **Decisão necessária:** o usuário aceita voltar a confirmar comandos?

---

### Tarefa 2.3 · Versionamento

1. **`vortex-edicao`** (repo existente):

```powershell
git -C vortex-edicao add -A
git -C vortex-edicao commit -m "Correções de encoding no modelo, novo_episodio multi-projeto e b-roll Pixabay"
git -C vortex-edicao status --short   # esperado: vazio
```

2. **Código dos episódios** (sem mídia): opcional — como `projetos/**` tem
   ~19 GB, o caminho é um `.gitignore` agressivo (já previsto na Tarefa 2.1)
   + `git init` na raiz **só depois** da Tarefa 2.1.

> ⚠ **Decisão necessária:** `git init` na raiz sim/não?

---

### Tarefa 2.4 · Dependências declaradas

1. Criar `vortex-edicao/requirements.txt` a partir da `.venv` real:

```text
faster-whisper>=1.2
openai-whisper
noisereduce>=3.0
soundfile>=0.14
numpy>=2.5
scipy>=1.18
pillow>=13
```

2. Corrigir `instalar.sh`: `pip install -r requirements.txt` (e trocar o nome do
   script para refletir que é macOS/Linux) **ou** criar `instalar.ps1` para
   Windows — a máquina atual é Windows.
3. `novo_projeto.sh`: remover `D:/Drifit/Editor/projetos` hardcoded →
   `${VORTEX_PROJETOS:-$(pwd)/../projetos}`.
4. `transcrever.py:168`: além de `shutil.which("whisper")`, testar
   `vortex-edicao/.venv/Scripts/whisper.exe` — hoje o fallback nunca é achado.

**✅ Check 2.4** — em um venv novo (ou `pip install -r requirements.txt`):
`python transcrever.py --help` roda; `import faster_whisper, noisereduce` OK.

---

## 🟡 Fase 3 — Médio

### Tarefa 3.1 · Eliminar duplicação

- [ ] Apagar `vortex-edicao/criar_projeto.py` e `vortex-edicao/novo_episodio.py`
      (idênticos aos da raiz) **ou** inverter: manter só em `vortex-edicao/` e
      deixar os da raiz como *wrappers* de 3 linhas.
- [ ] `vortex-edicao/novo_projeto.py` já é wrapper — manter.
- [ ] Decidir o destino de `EP-00\` (3,3 GB) e `projetos\EP-00\` (4,7 GB):
      mover para `projetos/dr-gestao/episodios/EP-00/brutos/` ou para um
      `archivo/` fora do fluxo. **Não apagar sem confirmação.**
- [ ] `projetos/EP-00` — confirmar que não há arquivo único ali que não exista
      no workspace do Dr. Gestão antes de mover.

### Tarefa 3.2 · `media/` vs `midia/`

- [ ] Escolher: unificar tudo em `media/` (b-roll em `media/broll/`) **ou**
      documentar a diferença em `README.md` + `SKILL.md`.
- [ ] Se unificar: atualizar `SKILL.md` (`-o midia/broll`), `novo_projeto.sh`
      (`mkdir -p "$P/midia"`) e `broll_*.py` (default `midia/broll`).

### Tarefa 3.3 · Desacoplar marca do motor

- [ ] `transcrever.py:23` → ler `PROMPT_CONTEXTO` de
      `branding/config.json → preferencias_edicao.lexicon_transcricao`
      (fallback para o prompt genérico se ausente).
- [ ] `modelo/build.py:222` → trocar `LINHA DO TEMPO — DR. GESTÃO` por
      `LINHA DO TEMPO — {CFG['preferencias_edicao']['canal']}` (ou comentário neutro).
- [ ] Preencher o lexicon em `projetos/dr-gestao/branding/config.json`.

### Tarefa 3.4 · `criar_projeto.py`

- [ ] Validar slug com regex `^[a-z0-9]+(-[a-z0-9]+)*$` (rejeitar acentos/`..`).
- [ ] Paleta padrão **neutra** (cinza/branco) em vez da Ozon Tech; deixar as
      cores em branco para o usuário preencher.
- [ ] `PREFERENCIAS.md` template → marcar as cores como `TODO: preencher`.
- [ ] Criar também `branding/referencias/` e `branding/scripts/`.
- [ ] `sys.exit(1)` (ou `2`) quando o projeto já existe.

### Tarefa 3.5 · Robustez

- [ ] `cortar.py` — abortar com mensagem clara se `palavras.json` vazio;
      validar `início < fim` em cada `--remover`.
- [ ] `transcrever.py` — ampliar `except ImportError` para `except Exception`
      com aviso e cair no fallback.
- [ ] `render_rapido.py:158` — tratar ffprobe sem stream de áudio.
- [ ] `build.py:50` — no `SystemExit`, imprimir as 3 frases mais próximas
      (distância de edição) para acelerar a correção.

---

## 🔵 Fase 4 — Melhorias — ✅ CONCLUÍDA (28/10/2026)

- [x] **4.1** `vortex-edicao/tests/test_encoding.py` + `test_build_w.py` (scripts puros, sem pytest) — 14/14 passam; `run_all.py` exit 0.
- [x] **4.2** Atualizar `README.md` (raiz + `vortex-edicao/`): árvore real, pipeline `transcrever → cortar → build → render_rapido`, `media/` unificado, seção de testes.
- [x] **4.3** `.cache/huggingface` (1.5 GB) movido para `%LOCALAPPDATA%\huggingface`; `CACHE_HF` platform-aware; testado fim-a-fim sem re-download.
- [x] **4.4** Docs consolidados: `vortex-edicao/SKILL.md` ↔ `guia/MELHORIA.md`; `dr-gestao/SKILL.md` ↔ `branding/PREFERENCIAS.md` (regras só no dono canônico).
- [x] **4.5** `_durwav()` com cache; `with open(...)` nos `json.dump` (cortar.py 2×, transcrever.py 1×).

---

## Ordem resumida — ✅ FASES 1–4 CONCLUÍDAS (28/10/2026)

| # | Tarefa | Status | Commit |
|---|---|---|---|
| 1.1 | encoding no `modelo/` | ✅ | `b0c81d9` |
| 1.2 + 1.3 | guarda de sobrescrita + `copytree` | ✅ | `b0c81d9` |
| 2.1 + 2.2 | `.env` único + `.gitignore` + permissões | ✅ | `b0c81d9` / `77cfff1` |
| 2.4 | `requirements.txt` + instalação | ✅ | `b0c81d9` |
| 2.3 | commits | ✅ | `b0c81d9` (skill) + `77cfff1` (raiz) |
| 3.1–3.5 | limpeza e desacoplamento | ✅ | `b0c81d9` |
| 4.1–4.5 | testes, cache, docs, ajustes | ✅ | (ver abaixo) |

**Commits Fase 4:** `vortex-edicao` (testes, README, SKILL, transcrever/build/cortar/ilustra) + raiz (README, PLANO, SKILL dr-gestao). Árvores limpas após commit; 0 `.env`/segredo rastreado.

---

## ⚠️ Decisões do usuário — TODAS respondidas (28/10/2026)

| # | Decisão | Resposta | O que foi feito |
|---|---|---|---|
| 1 | `.env` duplicado | Só o da raiz | Duplicados apagados (backup em Temp); resolvers sobem a árvore |
| 2 | Permissões `.claude` | Voltar ao modo padrão | `bypassPermissions` removido; allowlist ~90 → 13 |
| 3 | Versionamento raiz | Sim, gitignore agressivo | `git init` + commit `77cfff1` |
| 4 | EP-00 legados | Mover para `arquivo/` | `arquivo/EP-00-raiz/` + `arquivo/EP-00-projetos/` + README |
| 5 | `media` vs `midia` | Unificar em `media/` | 63 subs. código + move físico + build regenerado |

---

## ✅ Fase 4 (melhorias) — CONCLUÍDA em 28/10/2026

- [x] **4.1** Testes automatizados (`test_encoding.py`, `test_build_w.py`, `run_all.py`) — automatizam o check 1.1. 14/14, exit 0.
- [x] **4.2** README da árvore real + pipeline + `media/` unificado (raiz + vortex-edicao).
- [x] **4.3** `.cache/huggingface` movido para `%LOCALAPPDATA%` (cache platform-aware, sem re-download).
- [x] **4.4** Docs duplicados consolidados (`SKILL.md` ↔ `MELHORIA.md`; `dr-gestao/SKILL.md` ↔ `PREFERENCIAS.md`).
- [x] **4.5** Menores: cache `_durwav()`, `with open()` em `json.dump`.

> **Fases 1–4 completas.** Não há pendência aberta no plano. Próximos passos são opcionais
> (ex.: `instalar.ps1` nativo para Windows, já que a máquina é Windows e o `instalar.sh`
> é macOS/Linux — não bloqueia, pois a `.venv` já existe).
