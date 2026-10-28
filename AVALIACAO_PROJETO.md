# 📋 Avaliação do Projeto — Drifit Editor

> **Data:** 28/10/2026 · **Escopo:** leitura e testes de execução (nenhum arquivo alterado)
> **Arquivos verificados:** 57 `.py` compilados · 0 erros de sintaxe
> **Passo seguinte:** [`PLANO_IMPLEMENTACAO.md`](PLANO_IMPLEMENTACAO.md)

---

## Resumo executivo

A arquitetura está bem pensada — isolamento por marca, herança de branding, motor
central, `checa_texto.py` como trava de qualidade. Os problemas estão na
**execução** e na **propagação das correções**: várias correções foram aplicadas
*cópia a cópia* nos episódios, mas nunca voltaram para o `modelo/` (a fonte), que
é exatamente o que `novo_episodio.py` injeta em cada episódio novo.

---

## 🔴 CRÍTICO

### 1. ~~O template `vortex-edicao/modelo/` ficou para trás das correções de encoding~~ ✅ CORRIGIDO (28/10/2026)

As correções de `encoding="utf-8"` existem **nos episódios**, mas não na **fonte**:

| Arquivo | `projetos/.../workspace/` | `vortex-edicao/modelo/` |
|---|---|---|
| `build.py` | 7 ocorrências ✅ | **0** ❌ (linhas 27, 303, 310) |
| `checa_texto.py` | 2 ✅ | **0** ❌ (linha 42) |
| `render_rapido.py` | 2 ✅ | **0** ❌ (linhas 126, 201) |

**Evidência (executado na `.venv` do projeto — Python 3.14, Windows = cp1252):**

```
W("empresa de confeccao")  -> FALHOU   (modelo, encoding padrão)
W("empresa de confeccao")  -> OK       (com encoding="utf-8")
W("menos esforco")         -> FALHOU
W("ponto de interrogacao") -> FALHOU
```

O `index.html` e o `partes.json` do EP-00 atual estão em UTF-8 **porque**
`projetos/EP-00/build.py` e o do workspace foram corrigidos — o `modelo/` não.

> **Por que aplicar:** `novo_episodio.py` copia o `modelo/` para cada episódio
> novo. Hoje um EP-01 criado assim **quebra no build**
> (`SystemExit: palavra não encontrada`) e, se passar, grava `index.html` em
> cp1252 declarando `<meta charset="UTF-8">` → acentos errados no vídeo final.
> Misturar o `build.py` do modelo (cp1252) com o `render_rapido.py` corrigido
> (utf-8) ainda pode gerar `UnicodeDecodeError`. É a própria "Regra de Ouro"
> da skill: *corrija na fonte*.

**Arquivos a corrigir em `vortex-edicao/modelo/`:**

- `build.py` — linhas 27, 29, 53, 208, 259, 269, 270, 303, 310
- `checa_texto.py` — linha 42
- `render_rapido.py` — linhas 126, 201

### 2. ~~`novo_episodio.py` destrói workspaces existentes~~ ✅ CORRIGIDO (28/10/2026)

Linhas 89–92 (cópia do `modelo/`) e 105–132 (herança do `branding/`):
`shutil.copy2(...)` **sem nenhuma guarda** de existência.

> **Por que aplicar:** rodar `python novo_episodio.py dr-gestao EP-00` de novo
> sobrescreve silenciosamente o `build.py` (35 KB de timeline ancorada na fala) e
> o `cenas.py` (38 KB) editados à mão. Uma distração = horas de trabalho perdidas.

### 3. ~~`novo_episodio.py` não copia subdiretórios~~ ✅ CORRIGIDO (28/10/2026)

Blocos 3.2–3.5 usam `if item.is_file()` → **pastas são ignoradas**.
O `branding/overlays/transicoes/` (4 transições `.mov/.webm` da marca) não é
copiado, embora o `SKILL.md` do Dr. Gestão prometa no Passo 3.1:
*"Transições de marca transparentes (`transicoes/`)"*.
No EP-00 atual elas existem porque foram copiadas à mão.

> **Por que aplicar:** o EP-01 nasce sem as transições oficiais e o erro só
> aparece na renderização.

---

## 🟠 ALTO

### 4. Segredos em 3 cópias e sem proteção contra commit

`.env` **byte a byte idêntico** em:
- `D:\Drifit\Editor\.env`
- `D:\Drifit\Editor\vortex-edicao\.env`
- `D:\Drifit\Editor\projetos\dr-gestao\.env`

Chaves: `ELEVENLABS_API_KEY`, `PEXELS_API_KEY`, `PIXABAY_API_KEY`.
Só `vortex-edicao/.gitignore` contém `.env` — **a raiz e `projetos/` não têm
`.gitignore` algum**.

> **Por que aplicar:** um `git init` na raiz (ou cópia da pasta para
> GitHub/Drive) vaza as três chaves.

### 5. `.claude/settings.local.json` em `bypassPermissions`

`"defaultMode": "bypassPermissions"` (linha 90) + ~90 permissões granulares
(inclui `Bash(python -c ' *)`).

> **Por que aplicar:** qualquer comando roda sem confirmação num projeto com
> chaves de API e scripts que baixam conteúdo da internet.

### 6. Nada está versionado onde importa

- `vortex-edicao` = repo git com **14 modificados + 4 não rastreados** sem commit
  desde out/2026 — inclui `modelo/*.py`, `transcrever.py`, `SKILL.md`,
  `novo_episodio.py`, `criar_projeto.py`, `scripts/broll_pixabay.py`.
- `projetos/**` (código dos episódios, ~19 GB) **sem versionamento algum**.

> **Por que aplicar:** sem commit não há como reverter regressão nem sincronizar
> a skill com o repositório da equipe (passo 6 do `guia/MELHORIA.md`).

### 7. Bootstrap documentado não instala o que o pipeline precisa

`instalar.sh` instala **só** `numpy scipy soundfile pillow`. O pipeline real
precisa de `faster-whisper` e `noisereduce` (a `.venv` real tem ainda `torch`,
`openai-whisper`, `onnxruntime`, `matplotlib`). **Não existe
`requirements.txt`/`pyproject.toml` em lugar nenhum.**

Contradições de plataforma:

| Arquivo | Alega | Usa |
|---|---|---|
| `instalar.sh` | macOS/Linux | `.venv/bin/pip`, `npx` |
| `novo_projeto.sh` | — | `.venv/Scripts/python.exe`, `D:/Drifit/Editor/projetos` hardcoded |
| `render_rapido.py` | — | `npx.cmd` |

E: `whisper.exe` existe em `vortex-edicao/.venv/Scripts/` mas **não está no
PATH** → `shutil.which("whisper")` retorna `None` → mensagem final
"Nenhum motor de transcrição encontrado" (causa errada).

---

## 🟡 MÉDIO

### 8. Duplicação e legados ocupando ~8 GB

- `criar_projeto.py` e `novo_episodio.py` **idênticos** em dois lugares
  (raiz e `vortex-edicao/`) → vão divergir.
- `EP-00` existe em **3 lugares**:
  - `D:\Drifit\Editor\EP-00` → **3.306 MB** (gravações brutas + finais soltos)
  - `D:\Drifit\Editor\projetos\EP-00` → **4.706 MB** (nível errado: sem
    `branding/`, o `listar_projetos()` o ignora — por sorte)
  - `D:\Drifit\Editor\projetos\dr-gestao\episodios\EP-00` → projeto todo **11.600 MB**
- `branding/scripts/*.py` ≡ `workspace/scripts/*.py` ≡ `workspace/*.py`
  (verificados: idênticos hoje), **sem mecanismo de sincronia** — só instrução
  textual no `SKILL.md`.

### 9. `media/` vs `midia/`

Duas pastas homógrafas na mesma workspace: `cortar.py`/`build.py` usam `media/`
(pipeline); b-roll usa `midia/` (assets). `novo_projeto.sh` cria só `midia`.

### 10. Regra de marca embutida no "motor central"

- `transcrever.py:23` → `PROMPT_CONTEXTO` com o lexicon literal do Dr. Gestão
  (*"confecção, DRE, lucratividade, pacientes, clínica"*).
- `build.py:222` → cabeçalho `LINHA DO TEMPO — DR. GESTÃO` hardcoded.

> **Por que aplicar:** contradiz o README ("Motor Centralizado... beneficiando
> todos os projetos"). Episódio da Ozon Tech transcreveria com vocabulário de
> clínica/confecção.

### 11. `criar_projeto.py` nasce com a identidade da Ozon Tech

Linhas 59–63 geram `destaque: #00d2ff / secundaria: #3a86ff / ciano: #00f0ff`, e o
`PREFERENCIAS.md` template já escreve *"Paleta de Cores Oficial: #00d2ff"*.
Não valida o slug (só troca espaços por `-`) e usa `sys.exit(0)` quando o projeto
já existe (mesmo código de "sucesso").

### 12. Robustez pontual (erros opacos)

- `cortar.py:23` → `w[0]`/`w[-1]` explodem se `palavras.json` vier vazio;
  `--remover` sem validar `início <= fim` quebra o ffmpeg com erro incompreensível.
- `transcrever.py:160` → `except ImportError` só pega o *import*: falha ao baixar
  o modelo não aciona fallback.
- `render_rapido.py:158` → `.stdout.split()[0]` vira `IndexError` se o ffprobe não
  achar stream de áudio.
- `build.py:50` → `W()` morre com `SystemExit` sem sugerir a frase mais próxima.
- ~~**`UnicodeEncodeError` em impressões**~~ → **CORRIGIDO em 28/10/2026**:
  `⚠` (U+26A0), `✗` (U+2717) e `→` (U+2192) não existem no cp1252; quando a saída
  ia para um pipe (redirecionamento, `| Out-String`), o script quebrava no meio.
  Descoberto pelo próprio teste de validação da Fase 1. Trava
  `sys.stdout.reconfigure(encoding="utf-8", errors="replace")` aplicada em
  **18 arquivos** (todos os pontos de entrada, nas3 cópias existentes).

---

## 🔵 MELHORIAS — ✅ RESOLVIDAS (Fase 4, 28/10/2026)

13. **Zero testes automatizados.** ✅ `vortex-edicao/tests/` criado (sem pytest):
    `test_encoding.py` + `test_build_w.py` (extrai `W()` via AST) + `run_all.py`. 14/14, exit 0.
14. **README desatualizado.** ✅ `README.md` raiz e `vortex-edicao/README.md` reescritos:
    árvore real, pipeline `transcrever → cortar → build → render_rapido`, `media/` unificado, testes.
15. **`.cache/huggingface` dentro do projeto.** ✅ Movido (1.5 GB) para
    `%LOCALAPPDATA%\huggingface`; `CACHE_HF` platform-aware (respeita `HF_HOME`); testado sem re-download.
16. **Docs duplicados.** ✅ `vortex-edicao/SKILL.md` ↔ `guia/MELHORIA.md` e
    `dr-gestao/SKILL.md` ↔ `branding/PREFERENCIAS.md` consolidados (skill manda no procedimento,
    regras só no dono canônico).
17. **Menores.** ✅ `_durwav()` com cache; `json.dump(open(...))` → `with open(...)` (cortar.py 2×,
    transcrever.py 1×); `criar_projeto.py` já cria `referencias/` e `scripts/` (Fase 3).

---

## Referência rápida — caminhos citados

```
D:\Drifit\Editor\
├── .env                                  # ⚠ duplicado (raiz / vortex-edicao / dr-gestao)
├── .claude\settings.local.json           # ⚠ bypassPermissions
├── criar_projeto.py                      # idêntico ao de vortex-edicao\
├── novo_episodio.py                      # idêntico ao de vortex-edicao\
├── EP-00\                                # 3,3 GB legado
├── projetos\EP-00\                       # 4,7 GB no nível errado
├── vortex-edicao\                        # git repo, 14 M + 4 ?? sem commit
│   ├── .env / .env.exemplo / .gitignore
│   ├── instalar.sh                       # ⚠ só numpy/scipy/soundfile/pillow
│   ├── transcrever.py                    # ⚠ PROMPT_CONTEXTO (linha 23)
│   ├── cortar.py
│   └── modelo\                           # ⚠ FONTE SEM encoding="utf-8"
│       ├── build.py                      #    linhas 27,29,53,208,259,269,270,303,310
│       ├── checa_texto.py                #    linha 42
│       └── render_rapido.py              #    linhas 126,201
└── projetos\dr-gestao\episodios\EP-00\workspace\   # ✅ já corrigido (referência)
```
