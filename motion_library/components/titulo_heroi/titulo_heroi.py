# -*- coding: utf-8 -*-
"""Componente T10 — Título Herói por Letra (Implementação Compartilhada).
Drifit Editor — Fase 5.1 (Prova de Reutilização).

Responsabilidade exclusiva:
- Normalização Unicode e divisão estruturada de palavras e letras em spans HTML.
- Geração de comando GSAP fromTo com seletor escopado, deslocamento vertical e desfoque progressivo.
- Sem acoplamento de estilo visual cênico (posição, cor, tamanho, glow pertencem à cena).
"""

import html
import json
import math
import re
import unicodedata
from typing import Optional

# Padrão estrito de identificadores HTML/CSS válidos e seguros
_ID_RE = re.compile(r"^[a-zA-Z0-9_-]+$")

# Easings permitidos para garantir determinismo e segurança de injeção
_EASING_RE = re.compile(r"^[a-zA-Z0-9_().,-]+$")


def _validar_id(nome: str, valor: str) -> str:
    if not valor or not isinstance(valor, str) or not _ID_RE.match(valor):
        raise ValueError(f"Identificador inválido para {nome}: {valor!r}. Esperado padrão [a-zA-Z0-9_-]+.")
    return valor


def _validar_float(nome: str, valor: float, min_val: Optional[float] = None) -> float:
    try:
        v = float(valor)
    except (TypeError, ValueError):
        raise ValueError(f"Valor numérico inválido para {nome}: {valor!r}.")
    if not math.isfinite(v):
        raise ValueError(f"Valor para {nome} deve ser finito: {valor!r}.")
    if min_val is not None and v < min_val:
        raise ValueError(f"Valor para {nome} ({v}) não pode ser inferior a {min_val}.")
    return v


def _r(v: float) -> str:
    """Arredonda com precisão determinística para serialização JavaScript limpa."""
    val = round(float(v), 3)
    if val.is_integer():
        return str(int(val))
    return f"{val:.3f}".rstrip("0").rstrip(".")


def gerar_html_titulo(
    texto: str,
    *,
    clip_id: str,
    elemento_id: str = "t2",
    classe_container: str = "",
) -> str:
    """Gera o HTML do título herói estruturado em palavras e letras individualizadas.

    Garante:
    - Normalização NFC para integridade de acentos da língua portuguesa.
    - Escape seguro contra XSS ou quebras de sintaxe HTML.
    - Wrappers de palavras (.th-w) para quebra de linha natural sem corte silábico indesejado.
    - Preservação de espaços normais entre palavras para evitar colapsos sem depender de &nbsp; forçado.
    """
    _validar_id("clip_id", clip_id)
    _validar_id("elemento_id", elemento_id)

    if not isinstance(texto, str):
        raise TypeError(f"O parâmetro 'texto' deve ser uma string, recebido {type(texto).__name__}.")

    texto_nfc = unicodedata.normalize("NFC", texto)

    # Processamento linha a linha para suportar eventuais quebras explícitas (\n)
    linhas = texto_nfc.split("\n")
    html_linhas = []

    for linha in linhas:
        # Divide por espaços preservando múltiplos espaços intencionais
        partes = linha.split(" ")
        html_palavras = []
        for parte in partes:
            if not parte:
                # Espaço consecutivo preservado como espaçador sem colapso
                html_palavras.append('<span class="th-w">&nbsp;</span>')
                continue
            letras_html = "".join(f'<span class="th-l">{html.escape(c, quote=True)}</span>' for c in parte)
            html_palavras.append(f'<span class="th-w">{letras_html}</span>')

        html_linhas.append(" ".join(html_palavras))

    conteudo_interno = "<br/>".join(html_linhas)

    container_id = f"{clip_id}-{elemento_id}"
    cls_attr = f' class="{html.escape(classe_container, quote=True)}"' if classe_container else ""
    return f'<div class="{html.escape(classe_container, quote=True)}" id="{container_id}">{conteudo_interno}</div>' if classe_container else f'<div id="{container_id}">{conteudo_interno}</div>'


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
) -> str:
    """Gera a instrução GSAP tl.fromTo(...) com seletor estritamente escopado.

    Garante:
    - Isolamento completo por ID de instância: #{clip_id}-{elemento_id} .th-l.
    - Validação de valores numéricos finitos.
    - Interpolação coordenada de opacidade, deslocamento vertical e desfoque.
    """
    _validar_id("clip_id", clip_id)
    _validar_id("elemento_id", elemento_id)

    t_in = _validar_float("t_inicio", t_inicio, min_val=0.0)
    dur = _validar_float("duration", duration, min_val=0.01)
    stag = _validar_float("stagger", stagger, min_val=0.0)
    y_off = _validar_float("y", y)
    blur_px = _validar_float("blur", blur, min_val=0.0)

    if not isinstance(ease, str) or not _EASING_RE.match(ease):
        raise ValueError(f"Easing inválido: {ease!r}.")

    seletor = f"#{clip_id}-{elemento_id} .th-l"

    return (
        f'tl.fromTo("{seletor}",'
        f'{{opacity:0,y:{_r(y_off)},filter:"blur({_r(blur_px)}px)"}},'
        f'{{opacity:1,y:0,filter:"blur(0px)",duration:{_r(dur)},stagger:{_r(stag)},ease:"{ease}"}},'
        f'{_r(t_in)});'
    )
