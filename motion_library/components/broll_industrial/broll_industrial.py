# -*- coding: utf-8 -*-
"""Componente B-Roll Industrial (desacoplado, sem rede/IA)."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from PIL import Image


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def resolve_safe_media_path(media_ref: str, authorized_roots: Sequence[Path]) -> Path:
    if not isinstance(media_ref, str) or not media_ref.strip():
        raise ValueError("media_ref vazio.")
    # reject traversal and absolute outside roots
    if ".." in Path(media_ref).parts:
        raise ValueError("path traversal detectado.")
    p = Path(media_ref)
    if p.is_absolute():
        # only allowed if within an authorized root
        for root in authorized_roots:
            if _is_within(p, root):
                if not p.is_file() or p.stat().st_size <= 0:
                    raise ValueError("arquivo inexistente ou vazio.")
                return p.resolve()
        raise ValueError("caminho absoluto fora das raizes autorizadas.")
    # relative: resolve against each root
    for root in authorized_roots:
        cand = (root / media_ref).resolve()
        if _is_within(cand, root) and cand.is_file() and cand.stat().st_size > 0:
            return cand
    raise ValueError("arquivo nao encontrado nas raizes autorizadas.")


def probe_broll_media(media_path: Path, ffprobe_path: Optional[str] = None) -> Dict[str, Any]:
    p = Path(media_path)
    if not p.is_file() or p.stat().st_size <= 0:
        raise ValueError("arquivo inexistente ou vazio.")
    # image
    try:
        with Image.open(p) as im:
            im.verify()
        with Image.open(p) as im2:
            w, h = im2.size
        return {"media_type": "image", "width": w, "height": h, "duration_s": 0.0, "path": str(p)}
    except Exception:
        pass
    # video via ffprobe
    ffprobe = ffprobe_path or "ffprobe"
    try:
        res = subprocess.run([ffprobe, "-v", "error", "-print_format", "json", "-show_streams", "-show_format", str(p)],
                             capture_output=True, text=True, timeout=30)
        info = json.loads(res.stdout)
        v = next((s for s in info.get("streams", []) if s.get("codec_type") == "video"), None)
        if not v:
            raise ValueError("sem stream de video.")
        w = int(v.get("width", 0)); h = int(v.get("height", 0))
        if w <= 0 or h <= 0:
            raise ValueError("video invalido: dimensoes zero.")
        dur = float(info.get("format", {}).get("duration", 0.0))
        return {"media_type": "video", "width": w, "height": h,
                "duration_s": dur, "path": str(p)}
    except Exception as e:
        raise ValueError(f"midia invalida/corrompida: {e}")


def resolve_broll_asset(element: Dict[str, Any], authorized_roots: Sequence[Path], local_catalog: Optional[Sequence[Dict[str, Any]]] = None) -> Dict[str, Any]:
    # level 1: media_ref explicito
    media_ref = element.get("media_ref") or element.get("arquivo") or element.get("path")
    if media_ref:
        try:
            p = resolve_safe_media_path(str(media_ref), authorized_roots)
            probe = probe_broll_media(p)
            return {"resolved": True, "level": 1, "path": str(p), "media_type": probe["media_type"],
                    "width": probe["width"], "height": probe["height"], "duration_s": probe["duration_s"]}
        except Exception as e:
            # fall through to catalog
            level1_error = str(e)
    else:
        level1_error = "sem media_ref"
    # level 2: local_catalog deterministic match by tags
    tags = set(element.get("tags", []) or [])
    if local_catalog:
        for cat in local_catalog:
            cat_ref = cat.get("media_ref") or cat.get("path")
            if not cat_ref:
                continue
            cat_tags = set(cat.get("tags", []) or [])
            if tags and tags.issubset(cat_tags):
                try:
                    p = resolve_safe_media_path(str(cat_ref), authorized_roots)
                    probe = probe_broll_media(p)
                    return {"resolved": True, "level": 2, "path": str(p), "media_type": probe["media_type"],
                            "width": probe["width"], "height": probe["height"], "duration_s": probe["duration_s"]}
                except Exception:
                    continue
    return {"resolved": False, "reason": f"nao resolvido: {level1_error}"}


def build_broll_ffmpeg_filter(
    input_idx: int,
    base_label: str,
    out_label: str,
    *,
    out_in: float,
    out_out: float,
    media_type: str,
    media_duration_s: Optional[float] = None,
    media_start: float = 0.0,
    ken_burns: float = 1.06,
    mode: str = "fullscreen",
    brand_profile: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if not (out_out > out_in):
        raise ValueError("out_out deve ser > out_in.")
    if ken_burns < 1.0:
        raise ValueError("ken_burns deve ser >= 1.0.")
    if mode not in ("fullscreen", "card"):
        raise ValueError("mode invalido.")
    dur = out_out - out_in
    if media_type == "image":
        media_dur = dur
        input_args = ["-loop", "1"]
    else:
        media_dur = min(dur, media_duration_s or dur)
        if (media_duration_s or 0) < dur:
            input_args = ["-stream_loop", "-1"]
        else:
            input_args = []
    zoom = f"1+({ken_burns}-1)*(on/{max(1,int(round(dur*30))-1)})"
    entry = 0.3
    exitd = 0.3
    st_out = max(0.0, dur - exitd)
    if mode == "fullscreen":
        vf = (f"[{input_idx}:v]trim=start={media_start:.3f}:duration={media_dur:.3f},setpts=PTS-STARTPTS,"
              f"fps=30,scale=1920:1080:force_original_aspect_ratio=increase:flags=lanczos,"
              f"crop=1920:1080,zoompan=z='{zoom}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s=1920x1080:fps=30,"
              f"setsar=1,format=yuva420p,"
              f"fade=t=in:st=0:d={entry}:alpha=1,fade=t=out:st={st_out:.3f}:d={exitd}:alpha=1,"
              f"setpts=PTS-STARTPTS+{out_in:.3f}/TB[broll{input_idx}]")
        overlay_xy = "0:0"
    else:
        face = (brand_profile or {}).get("presenter", {}).get("face_anchor_1080p", [980, 420])
        fx, fy = (int(face[0]), int(face[1])) if isinstance(face, (list, tuple)) and len(face) >= 2 else (980, 420)
        safe = ((brand_profile or {}).get("visual", {}) or {}).get("safe_zones", {}).get("master_16x9", {}) or {}
        if "card_left" in safe and "card_right" in safe:
            left = safe["card_left"]; right = safe["card_right"]
            # choose side opposite to face
            if fx < 960 and "card_right" in safe:
                cx = int(right[0]); cy = int(right[1])
            else:
                cx = int(left[0]); cy = int(left[1])
            cw = int(abs(right[0] - left[0]))
        else:
            cx, cy, cw = 100, 320, 580
        ch = 420
        vf = (f"[{input_idx}:v]trim=start={media_start:.3f}:duration={media_dur:.3f},setpts=PTS-STARTPTS,"
              f"fps=30,scale={cw}:{ch}:force_original_aspect_ratio=increase:flags=lanczos,"
              f"crop={cw}:{ch},setsar=1,format=yuva420p,"
              f"fade=t=in:st=0:d={entry}:alpha=1,fade=t=out:st={st_out:.3f}:d={exitd}:alpha=1,"
              f"setpts=PTS-STARTPTS+{out_in:.3f}/TB[broll{input_idx}]")
        overlay_xy = f"{cx}:{cy}"
    filter_steps = [vf, f"[{base_label}][broll{input_idx}]overlay={overlay_xy}:enable='between(t,{out_in:.3f},{out_out:.3f})':eof_action=pass:shortest=0[{out_label}]"]
    return {
        "filter_steps": filter_steps,
        "audio_discarded": True,
        "output_label": out_label,
        "duration": dur,
        "input_args": input_args,
    }
