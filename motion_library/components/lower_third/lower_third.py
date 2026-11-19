# -*- coding: utf-8 -*-
"""Componente Lower Third.

Desacoplado de cenas.py/globals. Normalizacao NFC, validacao de IDs,
HTML seguro, funcao pura de layout/geometria e renderizacao Pillow RGBA.
"""

from __future__ import annotations

import html
import math
import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_ID_RE = re.compile(r"^[a-zA-Z0-9_-]+$")

_DEFAULT_PALETTE = {
    "primary": "#004aad",
    "secondary": "#8e7de5",
    "accent_cyan": "#2f97d4",
    "bg_dark": "#0a0a0a",
    "text_primary": "#ffffff",
}


def _validar_id(nome: str, valor: str) -> str:
    if not valor or not isinstance(valor, str) or not _ID_RE.match(valor):
        raise ValueError(f"Identificador invalido para {nome}: {valor!r}.")
    return valor


def _nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s) if isinstance(s, str) else s


def _hex_to_rgb(hx: str, default=(255, 255, 255)):
    if not isinstance(hx, str):
        return default
    hx = hx.strip().lstrip("#")
    if len(hx) == 3:
        hx = "".join(c * 2 for c in hx)
    if len(hx) != 6:
        return default
    try:
        return (int(hx[0:2], 16), int(hx[2:4], 16), int(hx[4:6], 16))
    except ValueError:
        return default


def _brand_tokens(brand_profile: Optional[Dict[str, Any]]):
    bp = brand_profile or {}
    presenter = bp.get("presenter", {}) or {}
    visual = bp.get("visual", {}) or {}
    palette = visual.get("palette", {}) or {}
    merged = dict(_DEFAULT_PALETTE)
    for k in ("primary", "secondary", "accent_cyan", "bg_dark", "text_primary", "subtitle_highlight"):
        if k in palette and palette[k]:
            merged[k if k != "subtitle_highlight" else "text_primary"] = palette[k]
    # map subtitle_highlight to accent if present? keep simple
    font_family = visual.get("font_family", "Inter")
    safe = (visual.get("safe_zones", {}) or {}).get("master_16x9", {}) or {}
    max_w = safe.get("lower_third_max_w", 1150)
    face = presenter.get("face_anchor_1080p", [980, 420])
    name = presenter.get("name", "")
    cred = presenter.get("credential", "")
    return {
        "name": name,
        "credential": cred,
        "face_anchor": (int(face[0]), int(face[1])) if isinstance(face, (list, tuple)) and len(face) >= 2 else (980, 420),
        "palette": merged,
        "font_family": font_family,
        "max_width": int(max_w) if max_w else 1150,
    }


def gerar_html_lower_third(
    nome: str,
    credencial: str = "",
    *,
    clip_id: str,
    sub_itens: Optional[List[str]] = None,
    brand_profile: Optional[Dict[str, Any]] = None,
    x: Optional[int] = None,
    y: Optional[int] = None,
    max_width: Optional[int] = None,
    entry_duration_s: float = 0.35,
    exit_duration_s: float = 0.35,
    duration_seconds: Optional[float] = None,
) -> str:
    _validar_id("clip_id", clip_id)
    tokens = _brand_tokens(brand_profile)
    visual = (brand_profile or {}).get("visual", {}) or {}
    safe = (visual.get("safe_zones", {}) or {}).get("master_16x9", {}) or {}
    if x is None:
        x = safe.get("lower_third_x", 80)
    if y is None:
        y = safe.get("lower_third_y", 760)
    if max_width is None:
        max_width = safe.get("lower_third_max_w", tokens["max_width"])
    nome = _nfc(str(nome or ""))
    credencial = _nfc(str(credencial or ""))
    sub_itens = [_nfc(str(s)) for s in (sub_itens or [])]

    tokens = _brand_tokens(brand_profile)
    if max_width is None:
        max_width = tokens["max_width"]

    primary = tokens["palette"]["primary"]
    secondary = tokens["palette"]["secondary"]
    bg = tokens["palette"]["bg_dark"]
    text_color = tokens["palette"].get("text_primary", "#ffffff")

    # escape
    nome_e = html.escape(nome, quote=True)
    cred_e = html.escape(credencial, quote=True)
    sub_html = "".join(f"<li>{html.escape(s, quote=True)}</li>" for s in sub_itens)

    dur_total = duration_seconds if duration_seconds is not None else (entry_duration_s + exit_duration_s + 1.0)

    return (
        f'<div class="lower-third" id="{clip_id}-lt" '
        f'style="--lt-primary:{primary};--lt-secondary:{secondary};--lt-bg:{bg};--lt-text:{text_color};'
        f'--lt-font:{tokens["font_family"]};left:{x}px;top:{y}px;max-width:{max_width}px;" '
        f'data-entry="{entry_duration_s}" data-exit="{exit_duration_s}" data-duration="{dur_total}">'
        f'<div class="lt-name">{nome_e}</div>'
        f'<div class="lt-cred">{cred_e}</div>'
        f'<ul class="lt-subs">{sub_html}</ul>'
        f'</div>'
    )


def animar_lower_third(
    *,
    clip_id: str,
    t_inicio: float,
    entry_duration_s: float = 0.35,
    exit_duration_s: float = 0.35,
    duration_seconds: Optional[float] = None,
    x: int = 80,
    y: int = 760,
) -> str:
    _validar_id("clip_id", clip_id)
    dur_total = duration_seconds if duration_seconds is not None else (entry_duration_s + exit_duration_s + 1.0)
    t_in = float(t_inicio)
    t_out = t_in + dur_total
    return (
        f"lower_third: clip={clip_id} in={t_in:.3f} out={t_out:.3f} "
        f"entry={entry_duration_s} exit={exit_duration_s} dur={dur_total} pos=({x},{y})"
    )


def render_lower_third_png(
    nome: str,
    credencial: str = "",
    out_path: str | Path = "lower_third.png",
    *,
    brand_profile: Optional[Dict[str, Any]] = None,
    sub_itens: Optional[List[str]] = None,
    x: Optional[int] = None,
    y: Optional[int] = None,
    max_width: Optional[int] = None,
    entry_duration_s: float = 0.35,
    exit_duration_s: float = 0.35,
    duration_seconds: Optional[float] = None,
) -> Dict[str, Any]:
    tokens = _brand_tokens(brand_profile)
    # safe_zones opcionais
    visual = (brand_profile or {}).get("visual", {}) or {}
    safe = (visual.get("safe_zones", {}) or {}).get("master_16x9", {}) or {}
    if x is None:
        x = safe.get("lower_third_x", 80)
    if y is None:
        y = safe.get("lower_third_y", 760)
    if max_width is None:
        max_width = safe.get("lower_third_max_w", tokens["max_width"])
    x = int(x); y = int(y); max_width = int(max_width)

    nome = _nfc(str(nome or tokens["name"] or ""))
    credencial = _nfc(str(credencial or tokens["credential"] or ""))
    sub_itens = [_nfc(str(s)) for s in (sub_itens or [])]
    if max_width is None:
        max_width = tokens["max_width"]

    fx, fy = tokens["face_anchor"]
    # geometry box estimate
    # simple text width estimate: 12px per char approx
    def text_w(s: str, size: int) -> int:
        return int(len(s) * size * 0.55)

    title_size = 40
    cred_size = 22
    w = min(max_width, max(text_w(nome, title_size), text_w(credencial, cred_size)) + 40)
    h = title_size + 12 + cred_size + 12 * len(sub_itens) + 24
    if w < 120:
        w = 120
    if h < 60:
        h = 60

    # anti-face reposition
    face_avoided = False
    face_zone = (fx - 200, fy - 200, fx + 200, fy + 200)
    box = (x, y, x + w, y + h)
    if not (box[2] < face_zone[0] or box[0] > face_zone[2] or box[3] < face_zone[1] or box[1] > face_zone[3]):
        # intersect -> reposition
        y = max(760, fy + 220)
        # clamp within screen with margin
        if y + h > 1080 - 40:
            y = 1080 - 40 - h
        if y < 40:
            y = 40
        face_avoided = True
        box = (x, y, x + w, y + h)

    clipped = not (0 <= x and x + w <= 1920 and 0 <= y and y + h <= 1080)

    # render Pillow RGBA
    from PIL import Image, ImageDraw, ImageFont
    img = Image.new("RGBA", (1920, 1080), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    palette = tokens["palette"]
    primary = _hex_to_rgb(palette.get("primary", "#004aad"))
    secondary = _hex_to_rgb(palette.get("secondary", "#8e7de5"))
    bg = _hex_to_rgb(palette.get("bg_dark", "#0a0a0a"))
    text_color = _hex_to_rgb(palette.get("text_primary", "#ffffff"))
    # card bg
    draw.rounded_rectangle((x, y, x + w, y + h), radius=8, fill=(*bg, 200), outline=(*secondary, 180), width=2)
    # barra primaria esquerda
    draw.rectangle((x, y, x + 6, y + h), fill=(*primary, 255))
    # texto
    try:
        font_title = ImageFont.truetype(tokens["font_family"], title_size)
    except Exception:
        font_title = ImageFont.load_default()
    try:
        font_cred = ImageFont.truetype(tokens["font_family"], cred_size)
    except Exception:
        font_cred = ImageFont.load_default()
    draw.text((x + 16, y + 8), nome, font=font_title, fill=(*text_color, 255))
    draw.text((x + 16, y + 8 + title_size + 4), credencial, font=font_cred, fill=(*secondary, 255))
    yy = y + 8 + title_size + 4 + cred_size + 4
    for s in sub_itens:
        draw.text((x + 16, yy), f"- {s}", font=font_cred, fill=(*text_color, 220))
        yy += cred_size + 2

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)

    dur_total = duration_seconds if duration_seconds is not None else (entry_duration_s + exit_duration_s + 1.0)
    return {
        "bbox": {"x": x, "y": y, "w": w, "h": h},
        "face_avoided": face_avoided,
        "clipped": clipped,
        "entry_duration_s": entry_duration_s,
        "exit_duration_s": exit_duration_s,
        "duration_seconds": dur_total,
        "path": str(out),
    }
