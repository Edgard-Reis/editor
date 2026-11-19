"""core/brand_bumpers.py

Motor compartilhado multi-marca para resolucao, geracao via HyperFrames/GSAP
e aplicacao de vinhetas de Introducao (Intro) e Fechamento (Outro) com
hierarquia segura de 3 niveis (asset pronto -> geracao automatica -> fade-out limpo).
"""

from __future__ import annotations

import base64
import html as _html
import json
import mimetypes
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple


_REPO_ROOT = Path(__file__).resolve().parent.parent
_VIDEO_EXTS = (".mp4", ".mov", ".webm", ".mkv")
_LOGO_EXTS = (".png", ".svg", ".jpg", ".jpeg", ".webp")
_EXCLUDED_THIRD_PARTY_LOGOS = {
    "shopee.png",
    "mercado-livre.png",
    "shein.png",
    "tiktok.svg",
    "whatsapp.svg",
    "youtube.svg",
    "instagram.svg",
    "claude.svg",
}


class BrandBumperError(Exception):
    """Erro critico ao resolver ou aplicar vinheta de marca."""


def _normalize_aspect_key(aspect_ratio: Optional[str]) -> str:
    txt = str(aspect_ratio or "16:9").strip().lower().replace(":", "x").replace("/", "x")
    if txt in ("9x16", "vertical", "shorts", "reels", "portrait") or txt.startswith("9"):
        return "9x16"
    return "16x9"


def _dimensions_for_aspect(ar_key: str) -> Tuple[int, int]:
    if ar_key == "9x16":
        return 1080, 1920
    return 1920, 1080


def _resolve_config_dir(raw_path: Optional[str], workspace_root: Optional[Path], repo_root: Path) -> Optional[Path]:
    if not raw_path or not isinstance(raw_path, str):
        return None
    p = Path(raw_path.strip())
    if p.is_absolute():
        return p if p.exists() else None
    cands: List[Path] = []
    if workspace_root is not None:
        cands.append(Path(workspace_root).resolve() / p)
    cands.append(repo_root / p)
    for c in cands:
        if c.exists():
            return c.resolve()
    return None


def _dedupe_paths(paths: Sequence[Optional[Path]]) -> List[Path]:
    out: List[Path] = []
    seen = set()
    for p in paths:
        if p is None:
            continue
        rp = p.resolve()
        key = str(rp).lower()
        if key not in seen:
            seen.add(key)
            out.append(rp)
    return out


def resolve_brand_asset_dirs(
    workspace_root: Optional[str | Path] = None,
    marca_id: Optional[str] = None,
    brand_profile: Optional[Dict[str, Any]] = None,
    *,
    repo_root: Optional[str | Path] = None,
) -> Dict[str, Any]:
    """Resolve diretorios de branding da marca ativa com isolamento multi-marca.

    Honra explicitamente `assets_base_dir` e `assets.*_dir` do `config.json`.
    Nunca vaza `logos/`, `overlays/` ou `vinhetas/` de outra marca se a marca
    ativa nao os configurar. Apenas `sons/` e `scripts/` admitem fallback generico
    do motor quando a marca nao tem pasta propria.
    """
    repo = Path(repo_root).resolve() if repo_root else _REPO_ROOT
    ws_path = Path(workspace_root).resolve() if workspace_root else None
    cfg = (
        (brand_profile or {}).get("config_json")
        if isinstance((brand_profile or {}).get("config_json"), dict)
        else (brand_profile or {})
    )
    if not isinstance(cfg, dict):
        cfg = {}
    assets_cfg = cfg.get("assets") if isinstance(cfg.get("assets"), dict) else {}

    m_id = str(marca_id or (brand_profile or {}).get("marca_id") or cfg.get("brand_id") or "").strip()

    ws_brand = (ws_path / "projetos" / m_id / "branding") if (ws_path and m_id) else None
    repo_brand = (repo / "projetos" / m_id / "branding") if m_id else None
    base_dir_raw = cfg.get("assets_base_dir") or assets_cfg.get("base_dir")
    explicit_base = _resolve_config_dir(base_dir_raw, ws_path, repo)

    brand_roots = _dedupe_paths([
        ws_brand if ws_brand and ws_brand.is_dir() else None,
        repo_brand if repo_brand and repo_brand.is_dir() else None,
        explicit_base,
    ])

    primary_branding_dir: Optional[Path] = None
    if ws_brand is not None and ws_brand.is_dir():
        primary_branding_dir = ws_brand.resolve()
    elif repo_brand is not None and repo_brand.is_dir():
        primary_branding_dir = repo_brand.resolve()
    elif explicit_base is not None:
        primary_branding_dir = explicit_base.resolve()
    elif ws_brand is not None:
        primary_branding_dir = ws_brand.resolve()
    elif repo_brand is not None:
        primary_branding_dir = repo_brand.resolve()

    def _collect_sub(sub: str, override_key: str, *, allow_engine_fallback: bool) -> List[Path]:
        cands: List[Optional[Path]] = []
        ov = _resolve_config_dir(assets_cfg.get(override_key) or cfg.get(override_key), ws_path, repo)
        if ov is not None and ov.is_dir():
            cands.append(ov)
        for br in brand_roots:
            sub_dir = br / sub
            if sub_dir.is_dir():
                cands.append(sub_dir)
        if allow_engine_fallback:
            fb_dir = repo / "projetos" / "dr-gestao" / "branding" / sub
            if fb_dir.is_dir():
                cands.append(fb_dir)
        return _dedupe_paths(cands)

    logos_dirs = _collect_sub("logos", "logos_dir", allow_engine_fallback=False)
    overlays_dirs = _collect_sub("overlays", "overlays_dir", allow_engine_fallback=False)
    vinhetas_dirs = _collect_sub("vinhetas", "vinhetas_dir", allow_engine_fallback=False)
    sons_dirs = _collect_sub("sons", "sons_dir", allow_engine_fallback=True)
    scripts_dirs = _collect_sub("scripts", "scripts_dir", allow_engine_fallback=True)

    overlays_write_dir = (
        (primary_branding_dir / "overlays")
        if primary_branding_dir is not None
        else (overlays_dirs[0] if overlays_dirs else None)
    )

    return {
        "marca_id": m_id,
        "brand_roots": brand_roots,
        "primary_branding_dir": primary_branding_dir,
        "overlays_write_dir": overlays_write_dir,
        "logos_dirs": logos_dirs,
        "overlays_dirs": overlays_dirs,
        "vinhetas_dirs": vinhetas_dirs,
        "sons_dirs": sons_dirs,
        "scripts_dirs": scripts_dirs,
    }


def _probe_media_meta(video_path: Path) -> Dict[str, Any]:
    cmd = [
        "ffprobe",
        "-v", "error",
        "-print_format", "json",
        "-show_streams",
        "-show_format",
        str(video_path),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0 or not res.stdout.strip():
        return {"duration_s": 0.0, "width": 0, "height": 0, "has_audio": False}
    try:
        info = json.loads(res.stdout)
    except json.JSONDecodeError:
        return {"duration_s": 0.0, "width": 0, "height": 0, "has_audio": False}
    streams = info.get("streams", []) or []
    v0 = next((s for s in streams if s.get("codec_type") == "video"), None)
    a0 = next((s for s in streams if s.get("codec_type") == "audio"), None)
    dur = float((info.get("format") or {}).get("duration") or 0.0)
    return {
        "duration_s": max(0.0, dur),
        "width": int((v0 or {}).get("width") or 0),
        "height": int((v0 or {}).get("height") or 0),
        "has_audio": a0 is not None,
    }


def _resolve_relative_asset(raw_ref: str, asset_dirs: Dict[str, Any], ws_path: Optional[Path], repo: Path) -> Optional[Path]:
    p = Path(str(raw_ref).strip())
    if p.is_absolute():
        return p.resolve() if p.is_file() and p.stat().st_size > 0 else None
    cands: List[Path] = []
    for br in asset_dirs.get("brand_roots", []):
        cands.append(br / p)
    for d in asset_dirs.get("overlays_dirs", []):
        cands.append(d / p)
    for d in asset_dirs.get("vinhetas_dirs", []):
        cands.append(d / p)
    if ws_path is not None:
        cands.append(ws_path / p)
    cands.append(repo / p)
    for c in cands:
        if c.is_file() and c.stat().st_size > 0:
            return c.resolve()
    return None


def _matches_orientation_name(name_low: str, ar_key: str) -> bool:
    is_vert_name = any(tok in name_low for tok in ("9x16", "vertical", "shorts", "reels", "portrait"))
    is_horiz_name = any(tok in name_low for tok in ("16x9", "horizontal", "landscape"))
    if ar_key == "9x16":
        return is_vert_name or not is_horiz_name
    return is_horiz_name or not is_vert_name


def _scan_ready_bumper_file(kind: str, ar_key: str, asset_dirs: Dict[str, Any]) -> Optional[Path]:
    search_dirs: List[Path] = list(asset_dirs.get("overlays_dirs", [])) + list(asset_dirs.get("vinhetas_dirs", []))
    exact_names = [
        f"{kind}_{ar_key}",
        f"{kind}-{ar_key}",
        f"{kind}_vertical" if ar_key == "9x16" else f"{kind}_horizontal",
        f"{kind}_shorts" if ar_key == "9x16" else f"{kind}_master",
        kind,
    ]
    # 1) Exact standard filenames first
    for d in search_dirs:
        for stem in exact_names:
            for ext in _VIDEO_EXTS:
                cand = d / f"{stem}{ext}"
                if cand.is_file() and cand.stat().st_size > 0:
                    return cand.resolve()

    # 2) Heuristic keyword scan in overlays/vinhetas
    keywords = ("intro", "abertura") if kind == "intro" else ("outro", "fechamento", "encerramento", "logo-animada", "logo_animada")
    candidates: List[Path] = []
    for d in search_dirs:
        if not d.is_dir():
            continue
        for item in sorted(d.iterdir()):
            if not item.is_file() or item.suffix.lower() not in _VIDEO_EXTS or item.stat().st_size <= 0:
                continue
            low = item.name.lower()
            if "transicao" in low or "wipe" in low:
                continue
            if any(kw in low for kw in keywords) and _matches_orientation_name(low, ar_key):
                candidates.append(item.resolve())

    if not candidates:
        return None
    for cand in candidates:
        meta = _probe_media_meta(cand)
        w, h = meta.get("width", 0), meta.get("height", 0)
        if w > 0 and h > 0:
            if ar_key == "9x16" and h >= w:
                return cand
            if ar_key == "16x9" and w >= h:
                return cand
    return candidates[0] if ar_key == "16x9" else None


def _pick_brand_logo(asset_dirs: Dict[str, Any]) -> Optional[Path]:
    logos_dirs = asset_dirs.get("logos_dirs", [])
    preferred_stems = ("logo-branco-crop", "logo-branco", "logo-texto-branco", "logo-imagem", "logo-texto", "logo")
    for d in logos_dirs:
        if not d.is_dir():
            continue
        files = [
            f for f in sorted(d.iterdir())
            if f.is_file() and f.suffix.lower() in _LOGO_EXTS and f.stat().st_size > 0
            and f.name.lower() not in _EXCLUDED_THIRD_PARTY_LOGOS
        ]
        for pref in preferred_stems:
            for f in files:
                if f.stem.lower() == pref:
                    return f.resolve()
        if files:
            return files[0].resolve()
    return None


def _extract_brand_identity(brand_profile: Optional[Dict[str, Any]], asset_dirs: Dict[str, Any]) -> Dict[str, Any]:
    cfg = (
        (brand_profile or {}).get("config_json")
        if isinstance((brand_profile or {}).get("config_json"), dict)
        else (brand_profile or {})
    )
    if not isinstance(cfg, dict):
        cfg = {}
    marca_cfg = cfg.get("marca") if isinstance(cfg.get("marca"), dict) else {}
    prefs_cfg = cfg.get("preferencias_edicao") if isinstance(cfg.get("preferencias_edicao"), dict) else {}
    visual_cfg = cfg.get("visual") if isinstance(cfg.get("visual"), dict) else {}
    palette_cfg = visual_cfg.get("palette") if isinstance(visual_cfg.get("palette"), dict) else {}

    primary = str(palette_cfg.get("primary") or marca_cfg.get("destaque") or "").strip()
    secondary = str(palette_cfg.get("secondary") or marca_cfg.get("secundaria") or "").strip()
    accent = str(palette_cfg.get("accent") or marca_cfg.get("ciano") or "").strip()
    font_family = str(visual_cfg.get("font_family") or marca_cfg.get("fonte") or "Inter").strip()
    canal = str(prefs_cfg.get("canal") or (brand_profile or {}).get("display_name") or cfg.get("nome") or "").strip()
    credencial = str(prefs_cfg.get("credencial_oficial") or (brand_profile or {}).get("credencial") or "").strip()
    logo_path = _pick_brand_logo(asset_dirs)

    has_palette_and_name = bool(primary and canal)
    has_identity = bool(logo_path is not None or has_palette_and_name)
    return {
        "has_identity": has_identity,
        "logo_path": logo_path,
        "primary": primary or "#004aad",
        "secondary": secondary or "#8e7de5",
        "accent": accent or "#22d3ee",
        "font_family": font_family or "Inter",
        "canal": canal or str(asset_dirs.get("marca_id") or "Canal"),
        "credencial": credencial,
    }


def resolve_brand_bumper(
    kind: str,
    aspect_ratio: str = "16:9",
    *,
    workspace_root: Optional[str | Path] = None,
    marca_id: Optional[str] = None,
    brand_profile: Optional[Dict[str, Any]] = None,
    enabled: Optional[bool] = None,
    repo_root: Optional[str | Path] = None,
) -> Dict[str, Any]:
    """Resolve estrategia de Intro/Outro em 3 niveis para qualquer marca.

    Niveis:
      - 1 (`ready_asset`): video pronto na pasta `overlays/` ou `vinhetas/` da marca.
      - 2 (`generate_hyperframes`): logo ou paleta+nome configurados no `config.json`,
        sem video pronto; gera via HyperFrames/GSAP + SFX e salva em `overlays/`.
      - 3 (`clean_fade_out` / `skip_with_warning`): marca nova sem assets; aplica
        fade-out limpo (0.5s) e registra aviso amigavel sem quebrar o render.
    """
    norm_kind = "intro" if str(kind).strip().lower() == "intro" else "outro"
    ar_key = _normalize_aspect_key(aspect_ratio)
    repo = Path(repo_root).resolve() if repo_root else _REPO_ROOT
    ws_path = Path(workspace_root).resolve() if workspace_root else None

    asset_dirs = resolve_brand_asset_dirs(
        ws_path, marca_id, brand_profile=brand_profile, repo_root=repo
    )
    m_id = asset_dirs["marca_id"] or str(marca_id or "")

    cfg = (
        (brand_profile or {}).get("config_json")
        if isinstance((brand_profile or {}).get("config_json"), dict)
        else (brand_profile or {})
    )
    if not isinstance(cfg, dict):
        cfg = {}
    prefs_cfg = cfg.get("preferencias_edicao") if isinstance(cfg.get("preferencias_edicao"), dict) else {}
    vinhetas_cfg = cfg.get("vinhetas") or prefs_cfg.get("vinhetas") or {}
    if not isinstance(vinhetas_cfg, dict):
        vinhetas_cfg = {}

    if enabled is None:
        if norm_kind == "outro":
            is_enabled = bool(vinhetas_cfg.get("auto_outro", True))
        else:
            is_enabled = bool(vinhetas_cfg.get("auto_intro", False))
    else:
        is_enabled = bool(enabled)

    if not is_enabled:
        return {
            "kind": norm_kind,
            "aspect_ratio": "9:16" if ar_key == "9x16" else "16:9",
            "aspect_key": ar_key,
            "marca_id": m_id,
            "enabled": False,
            "level": 0,
            "strategy": "disabled",
            "path": None,
            "save_to_overlays": False,
            "duration_s": 0.0,
            "fade_duration_s": 0.0,
            "warning": None,
        }

    # Nivel 1: referencia explicita em config.json -> overlays/ ou vinhetas/
    explicit_ref = vinhetas_cfg.get(f"{norm_kind}_{ar_key}") or vinhetas_cfg.get(norm_kind)
    ready_path: Optional[Path] = None
    if explicit_ref:
        ready_path = _resolve_relative_asset(str(explicit_ref), asset_dirs, ws_path, repo)
    if ready_path is None:
        ready_path = _scan_ready_bumper_file(norm_kind, ar_key, asset_dirs)

    if ready_path is not None and ready_path.is_file():
        meta = _probe_media_meta(ready_path)
        return {
            "kind": norm_kind,
            "aspect_ratio": "9:16" if ar_key == "9x16" else "16:9",
            "aspect_key": ar_key,
            "marca_id": m_id,
            "enabled": True,
            "level": 1,
            "strategy": "ready_asset",
            "path": str(ready_path),
            "save_to_overlays": False,
            "duration_s": round(float(meta.get("duration_s") or 0.0), 3),
            "fade_duration_s": 0.0,
            "warning": None,
        }

    # Nivel 2: sem video pronto, mas ha logo ou paleta + nome no config.json
    identity = _extract_brand_identity(brand_profile, asset_dirs)
    if identity["has_identity"]:
        ov_write = asset_dirs.get("overlays_write_dir")
        target_path = str((ov_write / f"{norm_kind}_{ar_key}.mp4").resolve()) if ov_write is not None else None
        return {
            "kind": norm_kind,
            "aspect_ratio": "9:16" if ar_key == "9x16" else "16:9",
            "aspect_key": ar_key,
            "marca_id": m_id,
            "enabled": True,
            "level": 2,
            "strategy": "generate_hyperframes",
            "path": target_path,
            "logo_path": str(identity["logo_path"]) if identity["logo_path"] else None,
            "save_to_overlays": bool(target_path),
            "duration_s": 2.8,
            "fade_duration_s": 0.0,
            "sfx_name": "whoosh_curto.wav" if norm_kind == "intro" else "impacto_grave.wav",
            "warning": None,
        }

    # Nivel 3: marca nova sem assets ou identidade visual cadastrada
    if norm_kind == "outro":
        return {
            "kind": "outro",
            "aspect_ratio": "9:16" if ar_key == "9x16" else "16:9",
            "aspect_key": ar_key,
            "marca_id": m_id,
            "enabled": True,
            "level": 3,
            "strategy": "clean_fade_out",
            "path": None,
            "save_to_overlays": False,
            "duration_s": 0.0,
            "fade_duration_s": 0.5,
            "warning": (
                f"Marca '{m_id or 'atual'}' ainda nao possui logo ou vinheta cadastrada em "
                "branding/; aplicado fade-out limpo de 0.5s no encerramento."
            ),
        }

    return {
        "kind": "intro",
        "aspect_ratio": "9:16" if ar_key == "9x16" else "16:9",
        "aspect_key": ar_key,
        "marca_id": m_id,
        "enabled": True,
        "level": 3,
        "strategy": "skip_with_warning",
        "path": None,
        "save_to_overlays": False,
        "duration_s": 0.0,
        "fade_duration_s": 0.0,
        "warning": (
            f"Marca '{m_id or 'atual'}' ainda nao possui logo ou vinheta de abertura "
            "cadastrada em branding/; iniciando diretamente no gancho do video."
        ),
    }


def _logo_data_uri(logo_path: Optional[Path]) -> Optional[str]:
    if logo_path is None or not logo_path.is_file():
        return None
    mime, _ = mimetypes.guess_type(str(logo_path))
    if not mime:
        mime = "image/svg+xml" if logo_path.suffix.lower() == ".svg" else "image/png"
    raw = logo_path.read_bytes()
    b64 = base64.b64encode(raw).decode("ascii")
    return f"data:{mime};base64,{b64}"


def build_brand_bumper_html(
    kind: str,
    aspect_ratio: str,
    *,
    brand_profile: Optional[Dict[str, Any]],
    logo_path: Optional[Path] = None,
    duration_s: float = 2.8,
) -> str:
    """Constroi cena HTML/CSS/GSAP cinética multi-marca para Intro/Outro HyperFrames."""
    norm_kind = "intro" if str(kind).strip().lower() == "intro" else "outro"
    ar_key = _normalize_aspect_key(aspect_ratio)
    w, h = _dimensions_for_aspect(ar_key)
    dur = max(2.0, min(4.0, float(duration_s)))

    cfg = (
        (brand_profile or {}).get("config_json")
        if isinstance((brand_profile or {}).get("config_json"), dict)
        else (brand_profile or {})
    )
    if not isinstance(cfg, dict):
        cfg = {}
    marca_cfg = cfg.get("marca") if isinstance(cfg.get("marca"), dict) else {}
    prefs_cfg = cfg.get("preferencias_edicao") if isinstance(cfg.get("preferencias_edicao"), dict) else {}
    visual_cfg = cfg.get("visual") if isinstance(cfg.get("visual"), dict) else {}
    palette_cfg = visual_cfg.get("palette") if isinstance(visual_cfg.get("palette"), dict) else {}

    primary = str(palette_cfg.get("primary") or marca_cfg.get("destaque") or "#004aad").strip()
    secondary = str(palette_cfg.get("secondary") or marca_cfg.get("secundaria") or "#8e7de5").strip()
    accent = str(palette_cfg.get("accent") or marca_cfg.get("ciano") or "#22d3ee").strip()
    font_family = str(visual_cfg.get("font_family") or marca_cfg.get("fonte") or "Inter").strip()
    canal = str(
        prefs_cfg.get("canal") or (brand_profile or {}).get("display_name") or cfg.get("nome") or "MARCA"
    ).strip()
    credencial = str(
        prefs_cfg.get("credencial_oficial") or (brand_profile or {}).get("credencial") or ""
    ).strip()
    if not credencial:
        credencial = "Conteúdo Oficial · Inscreva-se" if norm_kind == "outro" else "Apresenta"

    logo_uri = _logo_data_uri(logo_path)
    logo_markup = (
        f'<img class="brand-logo" id="brand-logo" src="{logo_uri}" alt="{_html.escape(canal)}" />'
        if logo_uri
        else f'<div class="brand-monogram" id="brand-logo">{_html.escape(canal[:2].upper())}</div>'
    )
    kicker_txt = "APRESENTA" if norm_kind == "intro" else "ACOMPANHE OS PRÓXIMOS EPISÓDIOS"
    title_sz = "78px" if ar_key == "16x9" else "64px"
    cred_sz = "26px" if ar_key == "16x9" else "24px"
    cx, cy = w // 2, h // 2
    ring_r1 = 270 if ar_key == "16x9" else 240
    ring_r2 = 220 if ar_key == "16x9" else 192

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width={w}, height={h}, initial-scale=1.0">
<title>{_html.escape(canal)} · {norm_kind.upper()}</title>
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  html, body {{
    width: {w}px;
    height: {h}px;
    overflow: hidden;
    background: transparent;
    font-family: "{_html.escape(font_family)}", "Inter", "Segoe UI", "Bahnschrift", system-ui, sans-serif;
    color: #f8fafc;
    -webkit-font-smoothing: antialiased;
  }}
  #root {{
    position: relative;
    width: {w}px;
    height: {h}px;
    overflow: hidden;
    background: transparent;
  }}
  #stage {{
    position: absolute;
    inset: 0;
    opacity: 1;
    background:
      radial-gradient(circle at 50% 46%, rgba(16, 28, 60, 0.96) 0%, rgba(8, 12, 24, 0.99) 64%, rgba(4, 6, 14, 1) 100%);
  }}
  .grid-bg {{
    position: absolute;
    inset: -80px;
    background-image:
      linear-gradient(to right, rgba(255, 255, 255, 0.04) 1px, transparent 1px),
      linear-gradient(to bottom, rgba(255, 255, 255, 0.04) 1px, transparent 1px);
    background-size: 64px 64px;
  }}
  .glow {{
    position: absolute;
    left: {cx - 380}px;
    top: {cy - 380}px;
    width: 760px;
    height: 760px;
    border-radius: 50%;
    background: radial-gradient(circle, {primary}55 0%, {secondary}28 45%, transparent 72%);
    filter: blur(26px);
  }}
  #camera {{
    position: absolute;
    inset: 0;
    transform-origin: {cx}px {cy}px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 64px;
    text-align: center;
  }}
  svg.vectors {{
    position: absolute;
    inset: 0;
    width: {w}px;
    height: {h}px;
    pointer-events: none;
  }}
  .content-wrap {{
    position: relative;
    z-index: 4;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 20px;
    max-width: {w - 140}px;
  }}
  .brand-logo {{
    max-width: 340px;
    max-height: 150px;
    object-fit: contain;
    opacity: 0;
  }}
  .brand-monogram {{
    width: 148px;
    height: 148px;
    border-radius: 36px;
    background: linear-gradient(135deg, {primary}, {secondary});
    border: 2px solid {accent};
    box-shadow: 0 20px 60px {primary}88;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 56px;
    font-weight: 950;
    color: #ffffff;
    opacity: 0;
  }}
  .kicker-pill {{
    padding: 9px 24px;
    border-radius: 999px;
    background: rgba(15, 23, 42, 0.88);
    border: 1px solid {accent}88;
    font-size: 17px;
    font-weight: 800;
    letter-spacing: 0.20em;
    color: {accent};
    text-transform: uppercase;
    opacity: 0;
  }}
  .brand-title {{
    font-size: {title_sz};
    font-weight: 950;
    letter-spacing: -0.025em;
    line-height: 1.04;
    color: #ffffff;
    opacity: 0;
  }}
  .brand-line {{
    width: 240px;
    height: 4px;
    border-radius: 999px;
    background: linear-gradient(90deg, {primary}, {secondary}, {accent});
    transform-origin: center center;
    transform: scaleX(0);
  }}
  .brand-cred {{
    font-size: {cred_sz};
    font-weight: 600;
    color: #cbd5e1;
    line-height: 1.3;
    opacity: 0;
  }}
</style>
</head>
<body>
<div id="root" data-composition-id="main" data-start="0" data-duration="{dur:.3f}" data-width="{w}" data-height="{h}">
  <div id="stage">
    <div class="grid-bg" id="grid-bg"></div>
    <div class="glow" id="glow"></div>
    <div id="camera">
      <svg class="vectors" viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <linearGradient id="bumper-ring" x1="{cx - ring_r1}" y1="{cy}" x2="{cx + ring_r1}" y2="{cy}" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stop-color="{accent}"/>
            <stop offset="50%" stop-color="{secondary}"/>
            <stop offset="100%" stop-color="{primary}"/>
          </linearGradient>
        </defs>
        <g id="ring-1">
          <circle cx="{cx}" cy="{cy}" r="{ring_r1}" fill="none" stroke="url(#bumper-ring)" stroke-width="2.5" stroke-dasharray="18 14" opacity="0.45"/>
        </g>
        <g id="ring-2">
          <circle cx="{cx}" cy="{cy}" r="{ring_r2}" fill="none" stroke="{accent}" stroke-width="2" stroke-dasharray="44 18" opacity="0.55"/>
        </g>
        <circle id="pulse-ring" cx="{cx}" cy="{cy}" r="{ring_r2}" fill="none" stroke="{accent}" stroke-width="3" opacity="0"/>
      </svg>

      <div class="content-wrap">
        <div class="kicker-pill" id="kicker-pill">{_html.escape(kicker_txt)}</div>
        {logo_markup}
        <h1 class="brand-title" id="brand-title">{_html.escape(canal)}</h1>
        <div class="brand-line" id="brand-line"></div>
        <div class="brand-cred" id="brand-cred">{_html.escape(credencial)}</div>
      </div>
    </div>
  </div>
</div>

<script src="assets/vendor/gsap.min.js"></script>
<script>
(function () {{
  const rootEl = document.getElementById("root");
  const DUR = parseFloat(rootEl.dataset.duration || "{dur:.3f}") || {dur:.3f};
  const k = (f) => DUR * f;

  const tl = gsap.timeline({{ defaults: {{ ease: "power3.out" }} }});
  tl.fromTo("#camera", {{ scale: 0.94 }}, {{ scale: 1.03, duration: DUR, ease: "sine.inOut" }}, 0);
  tl.to("#grid-bg", {{ x: -32, y: -20, duration: DUR, ease: "none" }}, 0);
  tl.to("#ring-1", {{ rotation: 60, svgOrigin: "{cx} {cy}", duration: DUR, ease: "none" }}, 0);
  tl.to("#ring-2", {{ rotation: -90, svgOrigin: "{cx} {cy}", duration: DUR, ease: "none" }}, 0);

  tl.fromTo("#kicker-pill", {{ opacity: 0, y: -14 }}, {{ opacity: 1, y: 0, duration: k(0.16) }}, k(0.04));
  tl.fromTo("#brand-logo", {{ opacity: 0, scale: 0.78 }}, {{ opacity: 1, scale: 1, duration: k(0.22), ease: "back.out(1.5)" }}, k(0.08));
  tl.fromTo("#brand-title", {{ opacity: 0, y: 20 }}, {{ opacity: 1, y: 0, duration: k(0.22) }}, k(0.18));
  tl.to("#brand-line", {{ scaleX: 1, duration: k(0.24), ease: "power2.out" }}, k(0.28));
  tl.fromTo("#brand-cred", {{ opacity: 0, y: 14 }}, {{ opacity: 1, y: 0, duration: k(0.22) }}, k(0.34));
  tl.fromTo("#pulse-ring", {{ opacity: 0.85, scale: 0.9, svgOrigin: "{cx} {cy}" }}, {{ opacity: 0, scale: 1.38, svgOrigin: "{cx} {cy}", duration: k(0.32), ease: "power2.out" }}, k(0.22));
  tl.set({{}}, {{}}, DUR);

  window.__timelines = window.__timelines || {{}};
  window.__timelines["main"] = tl;
}})();
</script>
</body>
</html>
"""


def _find_sfx_wav(name: str, sons_dirs: Sequence[Path], repo: Path) -> Optional[Path]:
    stem = Path(name).stem
    for d in list(sons_dirs) + [repo / "projetos" / "dr-gestao" / "branding" / "sons"]:
        cand = Path(d) / f"{stem}.wav"
        if cand.is_file() and cand.stat().st_size > 0:
            return cand.resolve()
    return None


def generate_brand_bumper_mp4(
    kind: str,
    aspect_ratio: str,
    *,
    brand_profile: Optional[Dict[str, Any]],
    asset_dirs: Dict[str, Any],
    output_path: Optional[str | Path] = None,
    save_to_overlays: bool = True,
    duration_s: float = 2.8,
    work_dir: Optional[str | Path] = None,
    sfx_name: Optional[str] = None,
    repo_root: Optional[str | Path] = None,
) -> Dict[str, Any]:
    """Gera vinheta `.mp4` (16:9 ou 9:16) via HyperFrames/GSAP + SFX e salva em `overlays/`."""
    from .edl_renderer import render_fullscreen_motion_scene

    repo = Path(repo_root).resolve() if repo_root else _REPO_ROOT
    norm_kind = "intro" if str(kind).strip().lower() == "intro" else "outro"
    ar_key = _normalize_aspect_key(aspect_ratio)
    w, h = _dimensions_for_aspect(ar_key)
    dur = max(2.0, min(4.0, float(duration_s)))

    identity = _extract_brand_identity(brand_profile, asset_dirs)
    ov_dir = asset_dirs.get("overlays_write_dir")
    if output_path is not None:
        out_mp4 = Path(output_path).resolve()
    elif save_to_overlays and ov_dir is not None:
        out_mp4 = (Path(ov_dir) / f"{norm_kind}_{ar_key}.mp4").resolve()
    else:
        base_wd = Path(work_dir).resolve() if work_dir else (repo / "tmp_bumpers").resolve()
        out_mp4 = base_wd / f"{norm_kind}_{ar_key}.mp4"
    out_mp4.parent.mkdir(parents=True, exist_ok=True)

    wd = Path(work_dir).resolve() if work_dir else out_mp4.parent / "_bumper_work"
    wd.mkdir(parents=True, exist_ok=True)

    gsap_dst = wd / "assets" / "vendor" / "gsap.min.js"
    gsap_src = repo / "tools" / "hyperframes" / "assets" / "gsap" / "3.14.2" / "gsap.min.js"
    if gsap_src.is_file() and not gsap_dst.is_file():
        gsap_dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(gsap_src, gsap_dst)

    html_path = wd / f"{norm_kind}_{ar_key}.html"
    html_content = build_brand_bumper_html(
        norm_kind,
        ar_key,
        brand_profile=brand_profile,
        logo_path=identity.get("logo_path"),
        duration_s=dur,
    )
    html_path.write_text(html_content, encoding="utf-8")

    silent_mp4 = wd / f"{norm_kind}_{ar_key}_video.mp4"
    render_fullscreen_motion_scene(
        html_path,
        silent_mp4,
        width=w,
        height=h,
        fps=30,
        duration=dur,
        work_dir=wd,
        workers=2,
        editor_root=repo,
        strict_text_check=False,
        embed_sfx=False,
    )

    sons_dirs = asset_dirs.get("sons_dirs", [])
    primary_sfx = _find_sfx_wav(
        sfx_name or ("whoosh_curto.wav" if norm_kind == "intro" else "impacto_grave.wav"),
        sons_dirs,
        repo,
    )
    accent_sfx = _find_sfx_wav("check.wav" if norm_kind == "outro" else "clique2.wav", sons_dirs, repo)

    cmd = ["ffmpeg", "-y", "-nostdin", "-loglevel", "error", "-i", str(silent_mp4)]
    filter_parts: List[str] = []
    audio_map = "1:a"
    if primary_sfx is not None:
        cmd += ["-i", str(primary_sfx)]
        mix_inputs = ["[a_p]"]
        filter_parts.append(
            f"[1:a]aresample=48000,aformat=channel_layouts=stereo,volume=0.45,adelay=60|60,apad,atrim=0:{dur:.3f},asetpts=PTS-STARTPTS[a_p]"
        )
        if accent_sfx is not None:
            cmd += ["-i", str(accent_sfx)]
            delay_ms = int(round((dur * 0.42) * 1000))
            filter_parts.append(
                f"[2:a]aresample=48000,aformat=channel_layouts=stereo,volume=0.35,adelay={delay_ms}|{delay_ms},apad,atrim=0:{dur:.3f},asetpts=PTS-STARTPTS[a_c]"
            )
            mix_inputs.append("[a_c]")
        if len(mix_inputs) > 1:
            filter_parts.append(
                "".join(mix_inputs)
                + f"amix=inputs={len(mix_inputs)}:duration=first:dropout_transition=0,loudnorm=I=-14.0:TP=-1.0:LRA=7,atrim=0:{dur:.3f}[aout]"
            )
        else:
            filter_parts.append(f"[a_p]loudnorm=I=-14.0:TP=-1.0:LRA=7,atrim=0:{dur:.3f}[aout]")
        audio_map = "[aout]"
    else:
        cmd += ["-f", "lavfi", "-t", f"{dur:.3f}", "-i", "anullsrc=r=48000:cl=stereo"]
        filter_parts.append("[1:a]anull[aout]")
        audio_map = "[aout]"

    if filter_parts:
        cmd += ["-filter_complex", ";".join(filter_parts), "-map", "0:v", "-map", audio_map]
    cmd += [
        "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p", "-r", "30",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
        "-t", f"{dur:.3f}", "-movflags", "+faststart", str(out_mp4),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise BrandBumperError(f"FFmpeg falhou ao gerar vinheta {norm_kind} ({ar_key}): {res.stderr[-400:]}")

    meta = _probe_media_meta(out_mp4)
    return {
        "kind": norm_kind,
        "aspect_key": ar_key,
        "path": str(out_mp4),
        "saved_to_overlays": bool(save_to_overlays and ov_dir is not None),
        "duration_s": round(float(meta.get("duration_s") or dur), 3),
        "sfx_used": primary_sfx.name if primary_sfx else None,
    }


def ensure_bumper_mp4(
    plan: Dict[str, Any],
    *,
    brand_profile: Optional[Dict[str, Any]],
    asset_dirs: Dict[str, Any],
    work_dir: Path,
    repo_root: Optional[str | Path] = None,
) -> Dict[str, Any]:
    """Executa a estrategia planejada (Nivel 1 pronto, Nivel 2 gera/salva, Nivel 3 fallback)."""
    updated = dict(plan or {})
    if not updated.get("enabled"):
        return updated

    strategy = updated.get("strategy")
    if strategy == "ready_asset" and updated.get("path") and Path(updated["path"]).is_file():
        return updated

    if strategy == "generate_hyperframes":
        gen = generate_brand_bumper_mp4(
            str(updated.get("kind") or "outro"),
            str(updated.get("aspect_key") or updated.get("aspect_ratio") or "16:9"),
            brand_profile=brand_profile,
            asset_dirs=asset_dirs,
            output_path=updated.get("path"),
            save_to_overlays=bool(updated.get("save_to_overlays", True)),
            duration_s=float(updated.get("duration_s") or 2.8),
            work_dir=work_dir / f"_gen_{updated.get('kind')}_{updated.get('aspect_key')}",
            sfx_name=updated.get("sfx_name"),
            repo_root=repo_root,
        )
        updated["path"] = gen["path"]
        updated["duration_s"] = gen["duration_s"]
        updated["generated"] = True
        return updated

    return updated


def apply_intro_outro_to_video(
    main_video_path: str | Path,
    output_path: str | Path,
    *,
    intro_plan: Optional[Dict[str, Any]] = None,
    outro_plan: Optional[Dict[str, Any]] = None,
    width: int = 1920,
    height: int = 1080,
    fps: int = 30,
    apply_loudnorm: bool = True,
) -> Dict[str, Any]:
    """Aplica Intro e Outro (Niveis 1/2 via concat normalizada, ou Nivel 3 via fade-out limpo 0.5s)."""
    main_p = Path(main_video_path).resolve()
    out_p = Path(output_path).resolve()
    out_p.parent.mkdir(parents=True, exist_ok=True)
    main_meta = _probe_media_meta(main_p)
    main_dur_frames = max(1, int(round(float(main_meta.get("duration_s") or 0.1) * fps)))
    main_dur = main_dur_frames / float(fps)

    warnings: List[str] = []
    if intro_plan and intro_plan.get("warning"):
        warnings.append(str(intro_plan["warning"]))
    if outro_plan and outro_plan.get("warning"):
        warnings.append(str(outro_plan["warning"]))

    segments: List[Tuple[str, Path, float, bool]] = []
    intro_applied = False
    outro_applied = False
    fade_out_applied = False

    if intro_plan and intro_plan.get("enabled") and intro_plan.get("path") and Path(intro_plan["path"]).is_file():
        ip = Path(intro_plan["path"]).resolve()
        im = _probe_media_meta(ip)
        i_frames = max(1, int(round(float(im.get("duration_s") or 2.5) * fps)))
        segments.append(("intro", ip, i_frames / float(fps), bool(im.get("has_audio"))))
        intro_applied = True

    segments.append(("main", main_p, main_dur, bool(main_meta.get("has_audio"))))

    if outro_plan and outro_plan.get("enabled") and outro_plan.get("path") and Path(outro_plan["path"]).is_file():
        op = Path(outro_plan["path"]).resolve()
        om = _probe_media_meta(op)
        o_frames = max(1, int(round(float(om.get("duration_s") or 2.8) * fps)))
        segments.append(("outro", op, o_frames / float(fps), bool(om.get("has_audio"))))
        outro_applied = True

    total_dur = round(sum(seg[2] for seg in segments), 6)

    # Nivel 3 sem concat de outro/intro: aplica fade-out limpo (0.5s) ou copia direto
    if len(segments) == 1:
        need_fade_out = bool(
            outro_plan
            and outro_plan.get("enabled")
            and outro_plan.get("strategy") == "clean_fade_out"
        )
        fade_d = min(float((outro_plan or {}).get("fade_duration_s") or 0.5), max(0.05, main_dur * 0.4))
        if need_fade_out and main_dur > 0.2:
            st = max(0.0, main_dur - fade_d)
            tmp_out = out_p.with_name(f".{out_p.stem}_bumper_tmp{out_p.suffix}")
            cmd = [
                "ffmpeg", "-y", "-nostdin", "-loglevel", "error",
                "-i", str(main_p),
                "-vf", f"fade=t=out:st={st:.3f}:d={fade_d:.3f}",
            ]
            if main_meta.get("has_audio"):
                af = f"afade=t=out:st={st:.3f}:d={fade_d:.3f}"
                if apply_loudnorm:
                    af += ",alimiter=limit=0.891:attack=5:release=50,loudnorm=I=-14.0:TP=-1.0:LRA=7"
                cmd += ["-af", af, "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2"]
            else:
                cmd += ["-an"]
            cmd += [
                "-c:v", "libx264", "-preset", "fast", "-crf", "17",
                "-color_range", "tv", "-pix_fmt", "yuv420p", "-r", str(fps),
                "-t", f"{main_dur:.6f}", "-movflags", "+faststart", str(tmp_out),
            ]
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode != 0:
                raise BrandBumperError(f"FFmpeg falhou ao aplicar fade-out limpo: {res.stderr[-400:]}")
            shutil.move(str(tmp_out), str(out_p))
            fade_out_applied = True
        elif main_p != out_p:
            shutil.copy2(main_p, out_p)

        return {
            "output_path": str(out_p),
            "final_duration_seconds": round(main_dur, 6),
            "intro_applied": False,
            "outro_applied": False,
            "fade_out_applied": fade_out_applied,
            "warnings": warnings,
        }

    # Concatena Intro/Main/Outro normalizando streams para compatibilidade 100%
    tmp_out = out_p.with_name(f".{out_p.stem}_bumper_tmp{out_p.suffix}")
    cmd = ["ffmpeg", "-y", "-nostdin", "-loglevel", "error"]
    for _, seg_p, _, _ in segments:
        cmd += ["-i", str(seg_p)]

    f_parts: List[str] = []
    cat_inputs: List[str] = []
    for idx, (_, _, seg_dur, has_a) in enumerate(segments):
        f_parts.append(
            f"[{idx}:v]scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,fps={fps},setsar=1,format=yuv420p,"
            f"tpad=stop_mode=clone:stop_duration=0.2,trim=0:{seg_dur:.6f},setpts=PTS-STARTPTS[v{idx}]"
        )
        if has_a:
            f_parts.append(
                f"[{idx}:a]aresample=48000,aformat=channel_layouts=stereo,"
                f"apad=pad_dur=0.2,atrim=0:{seg_dur:.6f},asetpts=PTS-STARTPTS[a{idx}]"
            )
        else:
            f_parts.append(f"anullsrc=r=48000:cl=stereo:d={seg_dur:.6f}[a{idx}]")
        cat_inputs.append(f"[v{idx}][a{idx}]")

    f_parts.append(f"{''.join(cat_inputs)}concat=n={len(segments)}:v=1:a=1[vcat][acat]")
    if apply_loudnorm:
        f_parts.append(
            f"[acat]alimiter=limit=0.891:attack=5:release=50,loudnorm=I=-14.0:TP=-1.0:LRA=7,"
            f"atrim=0:{total_dur:.6f},asetpts=PTS-STARTPTS[aout]"
        )
    else:
        f_parts.append(f"[acat]atrim=0:{total_dur:.6f},asetpts=PTS-STARTPTS[aout]")

    cmd += [
        "-filter_complex", ";".join(f_parts),
        "-map", "[vcat]", "-map", "[aout]",
        "-c:v", "libx264", "-preset", "fast", "-crf", "17",
        "-color_range", "tv", "-pix_fmt", "yuv420p", "-r", str(fps),
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
        "-t", f"{total_dur:.6f}", "-movflags", "+faststart", str(tmp_out),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise BrandBumperError(f"FFmpeg falhou ao concatenar vinhetas: {res.stderr[-500:]}")
    shutil.move(str(tmp_out), str(out_p))

    return {
        "output_path": str(out_p),
        "final_duration_seconds": round(total_dur, 6),
        "intro_applied": intro_applied,
        "outro_applied": outro_applied,
        "fade_out_applied": fade_out_applied,
        "warnings": warnings,
    }
