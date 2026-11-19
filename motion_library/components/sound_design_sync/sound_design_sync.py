# -*- coding: utf-8 -*-
"""Componente Sound Design Sync (desacoplado, sem rede)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

ALLOWED_EXT = {".wav", ".mp3", ".flac", ".aac", ".m4a", ".ogg"}


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def resolve_safe_sound_path(sound_ref: str, authorized_roots: Sequence[Path]) -> Path:
    if not isinstance(sound_ref, str) or not sound_ref.strip():
        raise ValueError("sound_ref vazio.")
    if ".." in Path(sound_ref).parts:
        raise ValueError("path traversal detectado.")
    p = Path(sound_ref)
    if p.suffix.lower() not in ALLOWED_EXT:
        raise ValueError("extensao nao permitida.")
    if p.is_absolute():
        for root in authorized_roots:
            if _is_within(p, root) and p.is_file() and p.stat().st_size > 0:
                return p.resolve()
        raise ValueError("caminho absoluto fora das raizes autorizadas.")
    for root in authorized_roots:
        cand = (root / sound_ref).resolve()
        if _is_within(cand, root) and cand.is_file() and cand.stat().st_size > 0:
            return cand
    raise ValueError("arquivo nao encontrado nas raizes autorizadas.")


def probe_sound_asset(sound_path: Path, ffprobe_path: Optional[str] = None) -> Dict[str, Any]:
    p = Path(sound_path)
    if not p.is_file() or p.stat().st_size <= 0:
        raise ValueError("arquivo inexistente ou vazio.")
    ffprobe = ffprobe_path or "ffprobe"
    try:
        res = subprocess.run([ffprobe, "-v", "error", "-print_format", "json", "-show_streams", "-show_format", str(p)],
                             capture_output=True, text=True, timeout=30)
        info = json.loads(res.stdout)
        a = next((s for s in info.get("streams", []) if s.get("codec_type") == "audio"), None)
        if not a:
            raise ValueError("sem stream de audio.")
        sr = int(a.get("sample_rate", 0))
        if sr <= 0:
            raise ValueError("sample_rate invalido.")
        dur = float(info.get("format", {}).get("duration", 0.0))
        if dur <= 0:
            raise ValueError("duracao invalida.")
        return {"sample_rate": sr, "duration_s": dur, "path": str(p)}
    except Exception as e:
        raise ValueError(f"midia de audio invalida: {e}")


def resolve_sound_asset(element: Dict[str, Any], authorized_roots: Sequence[Path], brand_profile: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    sound_ref = element.get("sound_ref") or element.get("sample") or element.get("arquivo") or element.get("path")
    # try brand_profile sfx_map
    if not sound_ref and brand_profile:
        sfx_map = (brand_profile.get("assets", {}) or {}).get("sfx_map", {}) or {}
        sample = element.get("sample")
        if sample in sfx_map:
            sound_ref = sfx_map[sample].get("path")
    if not sound_ref:
        return {"resolved": False, "reason": "sem sound_ref"}
    # volume
    vol = element.get("volume", element.get("gain_db", 1.0))
    try:
        vol = float(vol)
    except (TypeError, ValueError):
        return {"resolved": False, "reason": "volume invalido"}
    if vol < 0.0 or vol > 1.0:
        # if gain_db provided, convert but still validate [0,1]
        if "gain_db" in element:
            try:
                vol = 10 ** (float(element["gain_db"]) / 20.0)
            except (TypeError, ValueError):
                return {"resolved": False, "reason": "volume fora de [0,1]"}
            if vol < 0.0 or vol > 1.0:
                return {"resolved": False, "reason": "volume fora de [0,1]"}
        else:
            return {"resolved": False, "reason": "volume fora de [0,1]"}
    try:
        p = resolve_safe_sound_path(str(sound_ref), authorized_roots)
        probe = probe_sound_asset(p)
    except Exception as e:
        return {"resolved": False, "reason": str(e)}
    return {"resolved": True, "path": str(p), "sample_rate": probe["sample_rate"],
            "duration_s": probe["duration_s"], "volume": vol}


def deduplicate_and_schedule_sfx(elements: Sequence[Dict[str, Any]], final_duration: float, *, cooldown_s: float = 0.5, proximity_s: float = 0.10) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    accepted: List[Dict[str, Any]] = []
    rejected: List[Dict[str, Any]] = []
    seen_keys = set()
    seen_times = []
    # precedence: semantic_plan first
    def origin_rank(e):
        o = str(e.get("origin", "")).lower()
        if "semantic" in o:
            return 0
        if "rhythm" in o:
            return 1
        return 2
    sorted_elems = sorted(elements, key=lambda e: (origin_rank(e), float(e.get("out_in", 0.0))))
    for el in sorted_elems:
        out_in = float(el.get("out_in", 0.0))
        out_out = float(el.get("out_out", 0.0))
        if out_in < 0 or out_out > final_duration + 1e-9 or out_out <= out_in:
            rejected.append({**el, "reason": "fora da timeline"})
            continue
        # cooldown check (any accepted within cooldown)
        if any(abs(out_in - t) < cooldown_s for t in seen_times):
            rejected.append({**el, "reason": "cooldown"})
            continue
        # proximity: block ANY second SFX within proximity_s
        if any(abs(out_in - t) <= proximity_s for t in seen_times):
            rejected.append({**el, "reason": "proximidade duplicada"})
            continue
        dk = el.get("dedup_key") or el.get("dedup") or f"{el.get('sound_ref')}|{round(out_in,3)}|{round(out_out,3)}"
        if dk in seen_keys:
            rejected.append({**el, "reason": "dedup_key duplicado"})
            continue
        # timestamp dedup: same (out_in_r3, sound_ref)
        ts_key = (round(out_in, 3), el.get("sound_ref"))
        if ts_key in [(round(float(a.get("out_in",0)),3), a.get("sound_ref")) for a in accepted]:
            rejected.append({**el, "reason": "timestamp duplicado"})
            continue
        seen_keys.add(dk)
        seen_times.append(out_in)
        accepted.append(dict(el))
    return accepted, rejected


def build_sound_mix_ffmpeg_filter(
    base_audio_label: str,
    sfx_items: Sequence[Dict[str, Any]],
    out_label: str,
    *,
    final_duration: float,
    target_lufs: float = -14.0,
    max_tp_db: float = -1.0,
    apply_loudnorm: bool = True,
) -> Dict[str, Any]:
    # build filter string
    sfx_labels = []
    steps = []
    for i, sfx in enumerate(sfx_items):
        at_ms = int(round(float(sfx.get("out_in", 0.0)) * 1000))
        dur = float(sfx.get("duration_s", sfx.get("dur_s", 1.0)))
        vol = float(sfx.get("volume", 0.5))
        idx = int(sfx.get("input_idx", i + 1))
        steps.append(f"[{idx}:a]atrim=duration={dur:.3f},asetpts=PTS-STARTPTS,aresample=48000,"
                     f"aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo,"
                     f"volume={vol:.3f},afade=t=in:st=0:d=0.015,afade=t=out:st={max(0.0,dur-0.020):.3f}:d=0.020,"
                     f"adelay={at_ms}|{at_ms}[s{i}]")
        sfx_labels.append(f"[s{i}]")
    if sfx_items:
        steps.append(f"{''.join(sfx_labels)}amix=inputs={len(sfx_items)}:duration=first:dropout_transition=0:normalize=0[sfxmix]")
        steps.append(f"[{base_audio_label}][sfxmix]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[mixed]")
    else:
        steps.append(f"[{base_audio_label}]anull[mixed]")
    lim = f"alimiter=limit=0.891:attack=5:release=50"
    if apply_loudnorm:
        steps.append(f"[mixed]{lim},loudnorm=I={target_lufs}:TP={max_tp_db}:LRA=11[{out_label}]")
    else:
        steps.append(f"[mixed]{lim}[{out_label}]")
    return {"filter_steps": steps, "output_label": out_label, "input_args": []}
