# T10 — Título Herói por Letra (Motion Library)

- **Identificador Canônico**: `T10 — Título herói por letra`
- **Classificação de Maturidade**: **V2 (Reutilizável)**
- **Módulo**: `motion_library.components.titulo_heroi`
- **Data de Homologação**: 2026-11-04 (Fase 5.4 do Motion System Dr. Gestão)

---

## 1. Objetivo e Responsabilidades

O componente **T10** implementa a animação tipográfica atômica de títulos em destaque ("palavra de virada" ou "título herói"), decompondo o texto em palavras (`.th-w`) e letras individualizadas (`.th-l`) animadas com deslocamento vertical progressivo, desfoque decrescente e opacidade coordenada.

### Responsabilidade Exclusiva do Componente:
- Normalização Unicode e divisão estruturada de palavras e letras em elementos HTML `<span>`.
- Escapamento defensivo contra quebras de árvore DOM ou injeção.
- Geração da instrução GSAP `tl.fromTo(...)` com seletor estritamente escopado por ID de instância.
- Fornecimento do CSS estrutural mínimo (`display: inline-block`, `white-space: nowrap`, `opacity: 0`, `will-change`).

### Responsabilidade da Cena Hospedeira:
- Posicionamento cênico (`top`, `left`, `width`, alinhamento).
- Tipografia da cena (`font-size`, `font-weight`, `line-height`, `letter-spacing`).
- Paleta e estilização visual (`color`, `text-shadow`, brilhos e gradientes).
- Animação de saída (o componente T10 gerencia exclusivamente a entrada).

---

## 2. Funções Públicas e Interface

```python
from motion_library.components.titulo_heroi import (
    animar_titulo,
    gerar_html_titulo,
)
```

### 2.1 `gerar_html_titulo`
Gera a estrutura HTML de palavras e letras encapsuladas.

```python
def gerar_html_titulo(
    texto: str,
    *,
    clip_id: str,
    elemento_id: str = "t2",
    classe_container: str = "",
) -> str
```

- **`texto`** (`str`): Texto a ser exibido.
- **`clip_id`** (`str`, obrigatório, keyword-only): Identificador único da cena/clip (validação: `^[a-zA-Z0-9_-]+$`).
- **`elemento_id`** (`str`, padrão `"t2"`): Identificador do elemento na cena (gera container com `id="{clip_id}-{elemento_id}"`).
- **`classe_container`** (`str`, opcional): Classe CSS local da cena aplicada ao container (ex.: `"vc-t2"` ou `"cm-t2"`).

### 2.2 `animar_titulo`
Gera a instrução GSAP `tl.fromTo(...)` para animar as letras da instância.

```python
def animar_titulo(
    *,
    clip_id: str,
    elemento_id: str = "t2",
    t_inicio: float,
    duration: float = 0.36,
    stagger: float = 0.035,
    y: float = 32.0,
    blur: float = 10.0,
    ease: str = "power3.out",
) -> str
```

- **`clip_id`** (`str`, obrigatório): Identificador do clip para escopo do seletor GSAP (`#{clip_id}-{elemento_id} .th-l`).
- **`elemento_id`** (`str`, padrão `"t2"`): Identificador do elemento.
- **`t_inicio`** (`float`, obrigatório): Instante de início da animação na timeline (em segundos, $\ge 0$).
- **`duration`** (`float`, padrão `0.36`): Duração da animação individual de cada letra ($\ge 0.01\text{ s}$).
- **`stagger`** (`float`, padrão `0.035`): Intervalo entre a entrada de letras sucessivas ($\ge 0\text{ s}$).
- **`y`** (`float`, padrão `32.0`): Deslocamento vertical inicial em pixels ($y \rightarrow 0$).
- **`blur`** (`float`, padrão `10.0`): Desfoque gaussiano inicial em pixels (`blur(Npx)` $\rightarrow$ `blur(0px)`).
- **`ease`** (`str`, padrão `"power3.out"`): Função de atenuação GSAP permitida.

---

## 3. Exemplo de Utilização em Cena

```python
from motion_library.components.titulo_heroi import (
    animar_titulo,
    gerar_html_titulo,
)

# 1. Geração do HTML no script da cena
clip_id = "cena_intro"
html_titulo = gerar_html_titulo(
    "Resultado",
    clip_id=clip_id,
    elemento_id="t2",
    classe_container="intro-t2",
)

# 2. Inserção do comando GSAP na timeline da cena
cmd_gsap = animar_titulo(
    clip_id=clip_id,
    elemento_id="t2",
    t_inicio=14.20,
    duration=0.38,
    stagger=0.04,
    y=40.0,
    blur=12.0,
    ease="power3.out",
)
timeline_js.append(cmd_gsap)
```

---

## 4. Inclusão do CSS no Build

No script de compilação da cena (`build.py`), o CSS estrutural do componente deve ser concatenado **antes** das regras específicas de cena para respeitar a ordem natural da cascata:

```python
from pathlib import Path

# Localização do CSS canônico a partir da raiz do Editor
caminho_css_t10 = (
    Path(__file__).resolve().parent / "motion_library" / "components" / "titulo_heroi" / "titulo_heroi.css"
)
CSS_SHARED_T10 = caminho_css_t10.read_text(encoding="utf-8")

CSS = (
    CSS_SHARED_T10
    + (AQUI / "estilo.css").read_text(encoding="utf-8")
    + (AQUI / "cenas.css").read_text(encoding="utf-8")
)
```

---

## 5. Contextos Homologados (Evidências Físicas)

O componente foi validado e homologado em dois episódios 16:9 independentes com aprovação visual expressa do usuário:

1. **Virada de Chave** (`workspace_teste_virada`):
   - Render: `_render_teste/virada_teste_t10.mp4` (SHA-256: `5C7256313722E9ACC770709EACBA7342C35056975725E131D87D3C725658CBB6`)
   - Parâmetros: Palavra `"Chave"`, 152 px, $t = 25.94\text{ s}$, `duration = 0.38`, `stagger = 0.04`, $y = 44\text{ px}$, $\text{blur} = 14\text{ px}$, `power3.out`.
2. **Alta Minutagem** (`workspace_teste_minutagem`):
   - Render: `_render_teste/minutagem_teste_t10.mp4` (SHA-256: `C7ADF06A510395AC78E948E83D4F226DE2ADCD7B5A447E51E1B8BC9AA1DB5499`)
   - Parâmetros: Palavra `"Minutagem"`, 76 px, $t = 26.90\text{ s}$, `duration = 0.36`, `stagger = 0.032`, $y = 32\text{ px}$, $\text{blur} = 10\text{ px}$, `power3.out`.

**Origem Experimental**:
Os arquivos canônicos foram extraídos do workspace de validação da Fase 5:
`projetos/dr-gestao/episodios/teste-piloto-parte-02/fase5_experimento_t10/shared/`

---

## 6. Hashes Criptográficos Canônicos

| Arquivo | Hash SHA-256 Homologado |
| :--- | :--- |
| `titulo_heroi.py` | `E79205B8B6BE4D7C9D3B868072403D91407FAFCD9AB24293E64E098AD333669C` |
| `titulo_heroi.css` | `FE926A6CF0329A900AE99B43ED455BEC0D1DDBCD0ED8D02BBE348EFD2B9E86B2` |
| `test_titulo_heroi.py` | `2DC5A181D0DB3C766B5D922A562EC32B020BEF2BA40EA91121E7BDE95361B06C` |

---

## 7. Limitações Conhecidas

- **Formato 9:16**: Validado exclusivamente no formato 16:9 (horizontal). O comportamento responsivo para cortes verticais de redes sociais (Shorts/Reels/TikTok) ainda não foi homologado.
- **Normalização Unicode**: Aplica `unicodedata.normalize("NFC", texto)` para garantir a integridade de acentos da língua portuguesa (`ç`, `ã`, `é`, etc.). Não há garantia de compatibilidade com todos os grafemas complexos ou emojis do padrão Unicode.
- **Animação de Saída**: O componente não implementa transição de saída; o elemento deve ter sua saída controlada pela cena hospedeira.

---

## 8. Execução da Suíte de Testes Automatizados

A suíte contém 16 testes unitários em Python puro (`unittest`), sem dependências externas.

Para executar os testes a partir da pasta do componente:
```bash
python -m unittest test_titulo_heroi -v
```

Para executar a partir da raiz do repositório (`d:\Drifit\Editor`):
```bash
python -m unittest discover -s motion_library/components/titulo_heroi -p "test_*.py" -v
```
