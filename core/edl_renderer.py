"""
core/edl_renderer.py

Executor local desacoplado de marca que transforma EDL + editorial_plan em
video MP4 local (1920x1080, 30fps, H.264 + AAC 48kHz).

Gate previo: master_lint.lint() deve retornar ok=True.
"""

from __future__ import annotations

import hashlib
import html as _html
import importlib.util
import json
import math
import re
import shutil
import subprocess
import sys
import unicodedata
import wave
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Sequence, Tuple

_REPO_ROOT = Path(__file__).resolve().parent.parent

try:
    from .master_lint import lint as lint_plan
except Exception:  # pragma: no cover
    sys.path.insert(0, str(_REPO_ROOT))
    from core.master_lint import lint as lint_plan  # type: ignore

try:
    from .component_catalog import resolve_component_status
except Exception:  # pragma: no cover
    sys.path.insert(0, str(_REPO_ROOT))
    from core.component_catalog import resolve_component_status  # type: ignore

try:
    from .brand_bumpers import (
        resolve_brand_asset_dirs,
        resolve_brand_bumper,
        ensure_bumper_mp4,
        apply_intro_outro_to_video,
    )
except Exception:  # pragma: no cover
    sys.path.insert(0, str(_REPO_ROOT))
    from core.brand_bumpers import (  # type: ignore
        resolve_brand_asset_dirs,
        resolve_brand_bumper,
        ensure_bumper_mp4,
        apply_intro_outro_to_video,
    )

# motion_library components homologados (HTML/CSS/GSAP + asset resolvers)
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

try:
    from motion_library.components.titulo_heroi.titulo_heroi import (
        animar_titulo as _animar_titulo_heroi,
        gerar_html_titulo as _gerar_html_titulo_heroi,
    )
except Exception:  # pragma: no cover
    _animar_titulo_heroi = None
    _gerar_html_titulo_heroi = None

try:
    sys.path.insert(0, str(_REPO_ROOT / "motion_library" / "components" / "broll_industrial"))
    from broll_industrial import resolve_broll_asset as _resolve_broll_asset
except Exception:  # pragma: no cover
    _resolve_broll_asset = None

try:
    sys.path.insert(0, str(_REPO_ROOT / "motion_library" / "components" / "sound_design_sync"))
    from sound_design_sync import resolve_sound_asset as _resolve_sound_asset
    from sound_design_sync import deduplicate_and_schedule_sfx as _dedup_sfx
except Exception:  # pragma: no cover
    _resolve_sound_asset = None
    _dedup_sfx = None

TARGET_W, TARGET_H, TARGET_FPS = 1920, 1080, 30
AUDIO_SR = 48000
MICRO_FADE_S = 0.006


class EdlRenderError(Exception):
    """Erro de render da EDL."""


def _event_times(ev: Dict[str, Any]) -> Tuple[float, float, float, float]:
    raw_in = ev.get("raw_in", ev.get("src_in", ev.get("out_in", 0.0)))
    raw_out = ev.get("raw_out", ev.get("src_out", ev.get("out_out", 0.0)))
    out_in = ev.get("out_in", 0.0)
    out_out = ev.get("out_out", 0.0)
    return float(raw_in), float(raw_out), float(out_in), float(out_out)


def _layer_of_element(el: Dict[str, Any]) -> Optional[str]:
    return el.get("layer") or el.get("camada")


def _component_of_element(el: Dict[str, Any]) -> Optional[str]:
    return el.get("component_id") or el.get("component") or el.get("motion_type") or el.get("tipo")


try:
    from .video_verify import verify_master_basic as _verify_master_basic
except Exception:  # pragma: no cover
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from core.video_verify import verify_master_basic as _verify_master_basic  # type: ignore


def verify_rendered_video(
    video_path: str | Path,
    expected_duration_s: float,
    tolerance_s: float = 0.08,
    expected_width: Optional[int] = None,
    expected_height: Optional[int] = None,
) -> Dict[str, Any]:
    """Compatibilidade: delega a verificacao AV ao core/video_verify.py.

    Mantem o contrato historico (ok/problems/path/duration/video/audio) sem
    executar QA caro (ebur128/blackdetect) a cada render.
    """
    try:
        rep = _verify_master_basic(
            video_path,
            expected_duration_s,
            tolerance_s,
            expected_width=expected_width,
            expected_height=expected_height,
        )
    except Exception as exc:  # pragma: no cover - defensivo
        return {"ok": False, "problems": [f"verificacao AV falhou: {exc}"], "path": str(video_path)}
    return {
        "ok": bool(rep.get("ok")),
        "problems": list(rep.get("problems", [])),
        "path": rep.get("path", str(video_path)),
        "duration": rep.get("duration", 0.0),
        "video": rep.get("video"),
        "audio": rep.get("audio"),
    }


def _clean_plain_text(text: Any, default: str = "Destaque") -> str:
    txt = re.sub(r"<[^>]+>", " ", str(text or ""))
    txt = re.sub(r"\s+", " ", _html.unescape(txt)).strip()
    return txt or default


def _load_workspace_module(mod_name: str, file_path: Path):
    spec = importlib.util.spec_from_file_location(f"_edl_ws_{mod_name}", str(file_path))
    if spec is None or spec.loader is None:
        raise EdlRenderError(f"Falha ao carregar modulo do workspace: {file_path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _copy_if_stale(src: Path, dst: Path) -> None:
    if not src.is_file():
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        st_s, st_d = src.stat(), dst.stat()
        if st_s.st_size == st_d.st_size and abs(st_s.st_mtime - st_d.st_mtime) <= 1.0:
            return
    shutil.copy2(src, dst)


def _infer_workspace_and_brand(wd: Path, source_path: Optional[Path] = None, brand_profile: Optional[Dict[str, Any]] = None) -> Tuple[Optional[Path], str]:
    marca_id = str((brand_profile or {}).get("marca_id") or "").strip()
    ws_root: Optional[Path] = None
    for probe in (wd, source_path):
        if probe is None:
            continue
        p = Path(probe).resolve()
        for parent in [p] + list(p.parents):
            if parent.name == "projetos" and parent.parent.is_dir():
                ws_root = parent.parent
                break
        if ws_root is not None:
            break
    return ws_root, marca_id


def _provision_workspace(wd: Path, brand_profile: Dict[str, Any]) -> Dict[str, Any]:
    """Provisiona scripts/assets homologados (HTML/CSS/GSAP/cenas/estagio/som) no workspace."""
    fallback_brand = _REPO_ROOT / "projetos" / "dr-gestao" / "branding"
    template_ws = _REPO_ROOT / "vortex-edicao" / "modelo"
    if not (template_ws / "render_rapido.py").is_file():
        template_ws = _REPO_ROOT / "projetos" / "dr-gestao" / "episodios" / "ep-test-edl" / "workspace"
    ws_root, marca_id = _infer_workspace_and_brand(wd, None, brand_profile)
    asset_dirs = resolve_brand_asset_dirs(
        ws_root, marca_id, brand_profile=brand_profile, repo_root=_REPO_ROOT
    )

    script_roots: List[Path] = list(asset_dirs.get("brand_roots", []))
    ws_brand = wd.parent.parent / "branding"
    if ws_brand.is_dir() and ws_brand not in script_roots:
        script_roots.append(ws_brand)
    if fallback_brand not in script_roots:
        script_roots.append(fallback_brand)

    for fname in ("cenas.py", "cenas.css", "estagio.py", "som.py"):
        for br in script_roots:
            src_f = br / "scripts" / fname
            if src_f.is_file():
                _copy_if_stale(src_f, wd / fname)
                break

    for fname in ("estilo.css", "ilustra.py", "ilustra.css", "checa_texto.py", "render_rapido.py"):
        src_f = template_ws / fname
        if src_f.is_file():
            _copy_if_stale(src_f, wd / fname)

    gsap_src = _REPO_ROOT / "tools" / "hyperframes" / "assets" / "gsap" / "3.14.2" / "gsap.min.js"
    if not gsap_src.is_file():
        gsap_src = template_ws / "assets" / "vendor" / "gsap.min.js"
    if gsap_src.is_file():
        _copy_if_stale(gsap_src, wd / "assets" / "vendor" / "gsap.min.js")

    sub_sources = {
        "sons": list(reversed(asset_dirs.get("sons_dirs", []))),
        "logos": list(reversed(asset_dirs.get("logos_dirs", []))),
        "overlays": list(reversed(asset_dirs.get("overlays_dirs", []))),
    }
    if not sub_sources["sons"] and (fallback_brand / "sons").is_dir():
        sub_sources["sons"] = [fallback_brand / "sons"]

    for sub, dirs in sub_sources.items():
        (wd / sub).mkdir(parents=True, exist_ok=True)
        for src_tree in dirs:
            if not src_tree.is_dir():
                continue
            for item in src_tree.rglob("*"):
                if not item.is_file():
                    continue
                if any(part in ("__pycache__", ".trechos") for part in item.parts):
                    continue
                rel = item.relative_to(src_tree)
                _copy_if_stale(item, wd / sub / rel)

    primary_dir = asset_dirs.get("primary_branding_dir") or fallback_brand
    return {"branding_dir": primary_dir, "template_ws": template_ws, "asset_dirs": asset_dirs}


def _stage_audio_to_wav(src_path: Path, dst_wav: Path) -> None:
    dst_wav.parent.mkdir(parents=True, exist_ok=True)
    if src_path.suffix.lower() == ".wav":
        _copy_if_stale(src_path, dst_wav)
        return
    res = subprocess.run(
        ["ffmpeg", "-y", "-nostdin", "-loglevel", "error", "-i", str(src_path),
         "-ar", str(AUDIO_SR), "-ac", "2", "-c:a", "pcm_s16le", str(dst_wav)],
        capture_output=True, text=True,
    )
    if res.returncode != 0:
        raise EdlRenderError(f"Falha ao converter SFX para WAV ({src_path}): {res.stderr[-300:]}")


def _wav_duration(path: Path) -> float:
    if path.is_file() and path.suffix.lower() == ".wav":
        try:
            with wave.open(str(path), "rb") as w:
                fr = w.getframerate() or AUDIO_SR
                return w.getnframes() / float(fr)
        except Exception:
            pass
    pr = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True,
    )
    try:
        return max(0.05, float((pr.stdout or "1.0").strip()))
    except ValueError:
        return 1.0


def _collect_raw_words(edl: Dict[str, Any], wd: Path) -> List[Dict[str, Any]]:
    raw_words: List[Dict[str, Any]] = []
    for ev in edl.get("timeline_events", []):
        for w in (ev.get("words") or []):
            txt = str(w.get("word") or w.get("w") or "").strip()
            if txt and "start" in w and "end" in w:
                raw_words.append({"w": txt, "s": float(w["start"]), "e": float(w["end"])})
    if raw_words:
        return raw_words
    for cand in (wd / "alignment.json", wd / "fonte" / "alignment.json"):
        if cand.is_file():
            try:
                data = json.loads(cand.read_text(encoding="utf-8"))
                for u in (data.get("editorial_units") or []):
                    for w in (u.get("words") or []):
                        txt = str(w.get("word") or w.get("w") or "").strip()
                        if txt and "start" in w and "end" in w:
                            raw_words.append({"w": txt, "s": float(w["start"]), "e": float(w["end"])})
                if raw_words:
                    return raw_words
            except Exception:
                pass
    for cand in (wd / "transcript.json", wd / "fonte" / "transcript.json"):
        if cand.is_file():
            try:
                data = json.loads(cand.read_text(encoding="utf-8"))
                for seg in (data.get("segments") or []):
                    for w in (seg.get("words") or []):
                        txt = str(w.get("word") or w.get("w") or "").strip()
                        if txt and "start" in w and "end" in w:
                            raw_words.append({"w": txt, "s": float(w["start"]), "e": float(w["end"])})
                if raw_words:
                    return raw_words
            except Exception:
                pass
    return raw_words


def _build_palavras_saida(edl: Dict[str, Any], wd: Path) -> List[Dict[str, Any]]:
    raw_words = _collect_raw_words(edl, wd)
    out_words: List[Dict[str, Any]] = []
    for ev in edl.get("timeline_events", []):
        raw_in, raw_out, out_in, out_out = _event_times(ev)
        if raw_out <= raw_in:
            continue
        matched = [
            w for w in raw_words
            if raw_in - 0.02 <= 0.5 * (w["s"] + w["e"]) <= raw_out + 0.02
        ]
        if matched:
            for w in matched:
                t0 = max(out_in, out_in + (w["s"] - raw_in))
                t1 = min(out_out, max(t0 + 0.01, out_in + (w["e"] - raw_in)))
                out_words.append({"w": w["w"], "t": round(t0, 3), "f": round(t1, 3)})
        else:
            tokens = str(ev.get("text") or "").split()
            if tokens:
                step = (out_out - out_in) / len(tokens)
                for idx, tok in enumerate(tokens):
                    t0 = out_in + idx * step
                    t1 = t0 + step
                    out_words.append({"w": tok, "t": round(t0, 3), "f": round(t1, 3)})
    media_dir = wd / "media"
    media_dir.mkdir(parents=True, exist_ok=True)
    (media_dir / "palavras_saida.json").write_text(
        json.dumps(out_words, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return out_words


def _build_base_media_and_words(
    edl: Dict[str, Any],
    src: Path,
    wd: Path,
    target_w: int,
    target_h: int,
    target_fps: int,
    exact_duration: float,
) -> List[Dict[str, Any]]:
    media_dir = wd / "media"
    media_dir.mkdir(parents=True, exist_ok=True)
    base_mp4 = media_dir / "base.mp4"
    voz_wav = media_dir / "voz.wav"

    events = edl.get("timeline_events", [])
    pr_a = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index", "-of", "csv=p=0", str(src)],
        capture_output=True, text=True,
    )
    has_audio = bool((pr_a.stdout or "").strip())

    f: List[str] = []
    v_labels: List[str] = []
    a_labels: List[str] = []
    for i, ev in enumerate(events):
        raw_in, raw_out, _, _ = _event_times(ev)
        dur = max(0.001, raw_out - raw_in)
        f.append(
            f"[0:v]trim=start={raw_in:.6f}:end={raw_out:.6f},setpts=PTS-STARTPTS,"
            f"fps={target_fps},scale={target_w}:{target_h}:flags=lanczos,setsar=1,format=yuv420p[v{i}]"
        )
        v_labels.append(f"[v{i}]")
        if has_audio:
            fade_d = min(MICRO_FADE_S, dur * 0.25)
            f.append(
                f"[0:a]atrim=start={raw_in:.6f}:end={raw_out:.6f},asetpts=PTS-STARTPTS,"
                f"aresample={AUDIO_SR},aformat=sample_fmts=fltp:sample_rates={AUDIO_SR}:channel_layouts=stereo,"
                f"afade=t=in:st=0:d={fade_d:.6f},afade=t=out:st={max(0.0, dur - fade_d):.6f}:d={fade_d:.6f}[a{i}]"
            )
            a_labels.append(f"[a{i}]")

    if not v_labels:
        f.append(
            f"[0:v]trim=start=0:end={exact_duration:.6f},setpts=PTS-STARTPTS,"
            f"fps={target_fps},scale={target_w}:{target_h}:flags=lanczos,setsar=1,format=yuv420p,"
            f"tpad=stop_mode=clone:stop_duration=1.0,trim=start=0:end={exact_duration:.6f},setpts=PTS-STARTPTS[vbase]"
        )
    else:
        f.append(
            f"{''.join(v_labels)}concat=n={len(v_labels)}:v=1:a=0,fps={target_fps},"
            f"tpad=stop_mode=clone:stop_duration=1.0,trim=start=0:end={exact_duration:.6f},"
            f"setpts=PTS-STARTPTS[vbase]"
        )

    if has_audio and a_labels:
        f.append(
            f"{''.join(a_labels)}concat=n={len(a_labels)}:v=0:a=1,"
            f"apad=pad_dur=1.0,atrim=start=0:end={exact_duration:.6f},asetpts=PTS-STARTPTS[abase]"
        )
    elif has_audio:
        f.append(
            f"[0:a]atrim=start=0:end={exact_duration:.6f},asetpts=PTS-STARTPTS,"
            f"aresample={AUDIO_SR},aformat=sample_fmts=fltp:sample_rates={AUDIO_SR}:channel_layouts=stereo,"
            f"apad=pad_dur=1.0,atrim=start=0:end={exact_duration:.6f},asetpts=PTS-STARTPTS[abase]"
        )
    else:
        f.append(f"anullsrc=r={AUDIO_SR}:cl=stereo,atrim=start=0:end={exact_duration:.6f},asetpts=PTS-STARTPTS[abase]")

    base_filter = wd / "_edl_base_filter.txt"
    base_filter.write_text(";\n".join(f) + ";", encoding="utf-8")

    cmd = [
        "ffmpeg", "-y", "-nostdin", "-hide_banner", "-loglevel", "error",
        "-i", str(src),
        "-filter_complex_script", str(base_filter),
        "-map", "[vbase]", "-c:v", "libx264", "-preset", "fast", "-crf", "16",
        "-g", "15", "-profile:v", "high", "-pix_fmt", "yuv420p", "-r", str(target_fps),
        "-t", f"{exact_duration:.6f}", str(base_mp4),
        "-map", "[abase]", "-c:a", "pcm_s16le", "-ar", str(AUDIO_SR), "-ac", "2",
        "-t", f"{exact_duration:.6f}", str(voz_wav),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0 or not base_mp4.is_file() or not voz_wav.is_file():
        raise EdlRenderError(f"FFmpeg falhou ao preparar base.mp4/voz.wav: {res.stderr[-500:]}")

    return _build_palavras_saida(edl, wd)


def _resolve_fullscreen_motion_html(el: Dict[str, Any], roots: Sequence[Path]) -> Dict[str, Any]:
    """Resolve com seguranca o caminho HTML de uma cena `fullscreen_motion` dentro das raizes autorizadas."""
    raw_ref = str(el.get("html_path") or "").strip()
    if not raw_ref:
        sid = str(el.get("scene_id") or el.get("id_cena") or "").strip()
        if sid:
            raw_ref = f"workspace/motions_custom/{sid}.html"
    if not raw_ref:
        return {"resolved": False, "reason": "html_path ausente em fullscreen_motion"}

    norm_ref = raw_ref.replace("\\", "/")
    p = Path(norm_ref)
    if ".." in p.parts:
        return {"resolved": False, "reason": f"path traversal bloqueado: {raw_ref}"}

    resolved_roots: List[Path] = []
    for r in roots:
        try:
            rr = Path(r).resolve()
        except Exception:
            continue
        if rr not in resolved_roots:
            resolved_roots.append(rr)

    if p.is_absolute():
        cand = p.resolve()
        for rr in resolved_roots:
            try:
                cand.relative_to(rr)
                if cand.is_file():
                    return {"resolved": True, "path": str(cand), "html_path": norm_ref}
            except ValueError:
                continue
        return {"resolved": False, "reason": f"html_path absoluto fora das raizes autorizadas ou ausente: {raw_ref}"}

    rel_candidates = [p]
    if p.parts and p.parts[0] == "workspace" and len(p.parts) > 1:
        rel_candidates.append(Path(*p.parts[1:]))

    for rr in resolved_roots:
        for rel in rel_candidates:
            cand = (rr / rel).resolve()
            try:
                cand.relative_to(rr)
            except ValueError:
                continue
            if cand.is_file():
                return {"resolved": True, "path": str(cand), "html_path": norm_ref}

    return {"resolved": False, "reason": f"arquivo HTML nao encontrado para fullscreen_motion: {raw_ref}"}


def _ensure_fullscreen_stage_assets(stage_dir: Path, src_dir: Path, editor_root: Path) -> None:
    """Provisiona gsap.min.js local e assets de apoio no diretorio de staging sem rede externa."""
    stage_dir.mkdir(parents=True, exist_ok=True)
    gsap_candidates = [
        src_dir / "assets" / "vendor" / "gsap.min.js",
        stage_dir / "assets" / "vendor" / "gsap.min.js",
        editor_root / "tools" / "hyperframes" / "assets" / "gsap" / "3.14.2" / "gsap.min.js",
        editor_root / "projetos" / "dr-gestao" / "episodios" / "ep-test-edl" / "workspace" / "assets" / "vendor" / "gsap.min.js",
    ]
    gsap_dst = stage_dir / "assets" / "vendor" / "gsap.min.js"
    for g_src in gsap_candidates:
        if g_src.is_file():
            if g_src.resolve() != gsap_dst.resolve():
                _copy_if_stale(g_src, gsap_dst)
            break

    for sub in ("fonts", "logos"):
        for cand_root in (src_dir, src_dir.parent):
            sub_src = cand_root / sub
            if sub_src.is_dir():
                for item in sub_src.rglob("*"):
                    if item.is_file():
                        _copy_if_stale(item, stage_dir / sub / item.relative_to(sub_src))


def _rewrite_root_attr(html_text: str, attr: str, value: str) -> str:
    pattern = re.compile(rf'(<div\b[^>]*\bid=["\']root["\'][^>]*\b{re.escape(attr)}=["\'])([^"\']*)(["\'])', re.IGNORECASE)
    if pattern.search(html_text):
        return pattern.sub(rf'\g<1>{value}\g<3>', html_text, count=1)
    root_pat = re.compile(r'(<div\b[^>]*\bid=["\']root["\'])', re.IGNORECASE)
    return root_pat.sub(rf'\1 {attr}="{value}"', html_text, count=1)


def _resolve_som_bus_class(editor_root: Path, work_dir: Optional[Path] = None):
    """Carrega RobustSoundBus a partir de som.py local ou branding oficial."""
    cands: List[Path] = []
    if work_dir is not None:
        cands.append(Path(work_dir) / "som.py")
    cands.append(editor_root / "projetos" / "dr-gestao" / "branding" / "scripts" / "som.py")
    for cand in cands:
        if cand.is_file():
            mod = _load_workspace_module("som_fs_bus", cand)
            bus_cls = getattr(mod, "RobustSoundBus", None)
            if bus_cls is not None:
                return bus_cls
    return None


def _resolve_branding_sons_dir(
    editor_root: Path,
    work_dir: Optional[Path] = None,
    branding_sons_dir: Optional[str | Path] = None,
) -> Optional[Path]:
    cands: List[Path] = []
    if branding_sons_dir is not None:
        cands.append(Path(branding_sons_dir))
    if work_dir is not None:
        wd_p = Path(work_dir).resolve()
        cands.extend([wd_p / "sons", wd_p.parent / "sons", wd_p.parent.parent / "branding" / "sons"])
    cands.append(editor_root / "projetos" / "dr-gestao" / "branding" / "sons")
    for cand in cands:
        if cand.is_dir():
            return cand.resolve()
    return None


def build_fullscreen_motion_sfx_events(
    scene_id: str,
    start_s: float,
    duration_s: float,
    explicit_sfx_events: Optional[Sequence[Dict[str, Any]]] = None,
    *,
    include_entry_whoosh: bool = True,
    include_exit_swish: bool = True,
    conclusion_sfx: str = "check",
) -> List[Dict[str, Any]]:
    """Constroi lista deterministica de gatilhos SFX para uma cena `fullscreen_motion`.

    Garante entrada (`whoosh_curto`), marcos internos (`clique2` / `swish`),
    conclusao (`check` ou `impacto_grave`) e saida (`swish`) com volume
    seguro (<= 0.45) para mixagem limpa junto a voz em -14 LUFS.
    """
    dur = max(0.2, float(duration_s))
    t0 = max(0.0, float(start_s))
    safe_sid = re.sub(r"[^a-zA-Z0-9_-]+", "_", str(scene_id or "fs")).strip("_") or "fs"
    events: List[Dict[str, Any]] = []

    parsed_explicit: List[Tuple[str, float, float]] = []
    for item in (explicit_sfx_events or []):
        if not isinstance(item, dict):
            continue
        s_ref = str(item.get("sound_ref") or item.get("sound") or item.get("som") or "").strip()
        if not s_ref:
            continue
        s_name = Path(s_ref).stem
        off = float(item.get("offset_s", item.get("t", 0.0)))
        vol = max(0.05, min(0.45, float(item.get("volume", 0.36))))
        parsed_explicit.append((s_name, off, vol))

    has_explicit_entry = any(off <= 0.15 for _, off, _ in parsed_explicit)
    has_explicit_internal = any(0.15 < off <= dur * 0.65 for _, off, _ in parsed_explicit)
    has_explicit_conclusion = any(
        s_name in ("check", "impacto_grave") and off >= dur * 0.55
        for s_name, off, _ in parsed_explicit
    )
    has_explicit_exit = any(
        s_name == "swish" and off >= max(0.5, dur - 0.45)
        for s_name, off, _ in parsed_explicit
    )

    if include_entry_whoosh and not has_explicit_entry:
        events.append({
            "event_id": f"{safe_sid}_entry",
            "som": "whoosh_curto",
            "t": round(max(0.0, t0 - 0.04), 3),
            "volume": 0.38,
            "modo": "auto",
        })

    for idx_ex, (s_name, off, vol) in enumerate(parsed_explicit):
        if off > dur:
            continue
        events.append({
            "event_id": f"{safe_sid}_exp_{idx_ex}",
            "som": s_name,
            "t": round(max(0.0, t0 + off), 3),
            "volume": round(vol, 3),
            "modo": "explicit",
        })

    if not has_explicit_internal:
        if dur >= 2.0:
            events.append({
                "event_id": f"{safe_sid}_beat_1",
                "som": "clique2",
                "t": round(t0 + dur * 0.24, 3),
                "volume": 0.34,
                "modo": "auto",
            })
        if dur >= 3.2:
            events.append({
                "event_id": f"{safe_sid}_beat_2",
                "som": "swish",
                "t": round(t0 + dur * 0.50, 3),
                "volume": 0.30,
                "modo": "auto",
            })
        if dur >= 4.4:
            events.append({
                "event_id": f"{safe_sid}_beat_3",
                "som": "clique2",
                "t": round(t0 + dur * 0.68, 3),
                "volume": 0.32,
                "modo": "auto",
            })

    conc_stem = Path(str(conclusion_sfx or "check")).stem
    if conc_stem not in ("check", "impacto_grave"):
        conc_stem = "check"
    if dur >= 1.8 and not has_explicit_conclusion:
        t_conc = min(max(0.0, dur - 0.28), round(dur * 0.78, 3))
        events.append({
            "event_id": f"{safe_sid}_conclusion",
            "som": conc_stem,
            "t": round(t0 + t_conc, 3),
            "volume": 0.34 if conc_stem == "impacto_grave" else 0.38,
            "modo": "auto",
        })

    if include_exit_swish and dur >= 1.2 and not has_explicit_exit:
        events.append({
            "event_id": f"{safe_sid}_exit",
            "som": "swish",
            "t": round(max(t0, t0 + dur - 0.24), 3),
            "volume": 0.28,
            "modo": "auto",
        })

    events.sort(key=lambda ev: (ev["t"], ev["event_id"]))
    return events


def _mux_fullscreen_motion_sfx(
    video_mp4: Path,
    duration_s: float,
    sfx_events: Sequence[Dict[str, Any]],
    sons_dir: Path,
    ffmpeg_bin: Path,
    editor_root: Path,
    work_dir: Optional[Path] = None,
) -> None:
    """Compila SFX via RobustSoundBus e realiza mux em -14 LUFS no MP4 da cena."""
    bus_cls = _resolve_som_bus_class(editor_root, work_dir=work_dir)
    if bus_cls is None:
        return
    bus = bus_cls(track_base=20)
    for idx, ev in enumerate(sfx_events):
        som_name = str(ev.get("som") or "").strip()
        if not som_name or not (sons_dir / f"{som_name}.wav").is_file():
            continue
        t_ev = max(0.0, min(max(0.0, duration_s - 0.05), float(ev.get("t", 0.0))))
        vol_ev = max(0.05, min(0.45, float(ev.get("volume", 0.35))))
        eid = str(ev.get("event_id") or f"fs_{idx}")
        if str(ev.get("modo", "auto")).lower() == "explicit":
            bus.registrar_explicito(eid, som_name, t_ev, volume=vol_ev, origem="fullscreen_motion")
        else:
            bus.registrar_automatico(eid, som_name, t_ev, volume=vol_ev, origem="fullscreen_motion")

    compiled = bus.compilar(duracao_cache_fn=lambda name: _wav_duration(sons_dir / f"{name}.wav"))
    if not compiled:
        return

    cmd = [str(ffmpeg_bin), "-y", "-nostdin", "-loglevel", "error", "-i", str(video_mp4)]
    fil: List[str] = []
    mix_lbls: List[str] = []
    for k, c in enumerate(compiled, start=1):
        wav_p = sons_dir / f"{c['som']}.wav"
        cmd += ["-i", str(wav_p)]
        ms = max(0, int(round(float(c["t"]) * 1000)))
        dur_c = max(0.04, min(float(c["dur"]), max(0.05, duration_s - float(c["t"]))))
        vol_c = float(c["volume"])
        fil.append(
            f"[{k}:a]aresample={AUDIO_SR},aformat=channel_layouts=stereo,"
            f"atrim=0:{dur_c:.6f},volume={vol_c:.3f},adelay={ms}|{ms},apad,"
            f"atrim=0:{duration_s:.6f},asetpts=PTS-STARTPTS[as{k}]"
        )
        mix_lbls.append(f"[as{k}]")

    n_mix = len(mix_lbls)
    if n_mix == 1:
        fil.append(f"{mix_lbls[0]}alimiter=limit=0.891:attack=5:release=50,loudnorm=I=-14.0:TP=-1.0:LRA=11[aout]")
    else:
        fil.append(
            "".join(mix_lbls)
            + f"amix=inputs={n_mix}:duration=longest:dropout_transition=0,volume={n_mix},"
            + "alimiter=limit=0.891:attack=5:release=50,loudnorm=I=-14.0:TP=-1.0:LRA=11[aout]"
        )

    mux_tmp = video_mp4.with_suffix(".sfx.mp4")
    cmd += [
        "-filter_complex", ";".join(fil),
        "-map", "0:v", "-map", "[aout]",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", str(AUDIO_SR), "-ac", "2",
        "-t", f"{duration_s:.6f}", "-movflags", "+faststart", str(mux_tmp),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0 or not mux_tmp.is_file():
        mux_tmp.unlink(missing_ok=True)
        raise EdlRenderError(f"FFmpeg falhou no mux SFX da cena fullscreen_motion: {res.stderr[-400:]}")
    mux_tmp.replace(video_mp4)


def render_fullscreen_motion_scene(
    html_path: str | Path,
    output_mp4: str | Path,
    *,
    width: int = TARGET_W,
    height: int = TARGET_H,
    fps: int = TARGET_FPS,
    duration: Optional[float] = None,
    work_dir: Optional[str | Path] = None,
    workers: int = 2,
    editor_root: Optional[str | Path] = None,
    strict_text_check: bool = False,
    palavras_saida: Optional[Sequence[Dict[str, Any]]] = None,
    force: bool = False,
    embed_sfx: bool = False,
    sfx_events: Optional[Sequence[Dict[str, Any]]] = None,
    branding_sons_dir: Optional[str | Path] = None,
    conclusion_sfx: str = "check",
) -> Dict[str, Any]:
    """Renderiza uma cena isolada de Motion Design em tela cheia (HTML/CSS/GSAP) via HyperFrames."""
    import glob as _glob
    import tempfile as _tempfile

    src_html = Path(html_path).resolve()
    if not src_html.is_file():
        raise EdlRenderError(f"Arquivo HTML fullscreen_motion nao encontrado: {src_html}")

    out_mp4 = Path(output_mp4).resolve()
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    root_repo = Path(editor_root).resolve() if editor_root else _REPO_ROOT

    raw_html = src_html.read_text(encoding="utf-8")
    if duration is None:
        m_dur = re.search(r'\bdata-duration=["\']([\d.]+)["\']', raw_html)
        dur_val = float(m_dur.group(1)) if m_dur else 4.0
    else:
        dur_val = max(0.2, float(duration))

    fps_i = max(1, int(fps))
    w_i = max(16, int(width))
    h_i = max(16, int(height))
    frames = max(1, int(round(dur_val * fps_i)))
    exact_dur = round(frames / float(fps_i), 4)

    staged_html = _rewrite_root_attr(raw_html, "data-duration", str(exact_dur))
    staged_html = _rewrite_root_attr(staged_html, "data-width", str(w_i))
    staged_html = _rewrite_root_attr(staged_html, "data-height", str(h_i))
    staged_html = re.sub(
        r'(<meta\s+name=["\']viewport["\']\s+content=["\'])[^"\']*(["\'])',
        rf'\g<1>width={w_i}, height={h_i}\g<2>',
        staged_html,
        count=1,
        flags=re.IGNORECASE,
    )

    if strict_text_check:
        checa_cand = (
            (Path(work_dir) / "checa_texto.py")
            if work_dir and (Path(work_dir) / "checa_texto.py").is_file()
            else (root_repo / "projetos" / "dr-gestao" / "episodios" / "ep-test-edl" / "workspace" / "checa_texto.py")
        )
        if checa_cand.is_file():
            checa_mod = _load_workspace_module("checa_texto_fs", checa_cand)
            ruins = checa_mod.problemas(staged_html, list(palavras_saida or []))
            if ruins:
                raise EdlRenderError(f"checa_texto bloqueou cena fullscreen_motion ({src_html.name}): {ruins}")

    stage_dir = (Path(work_dir).resolve() if work_dir else (src_html.parent / "_hf_stage"))
    _ensure_fullscreen_stage_assets(stage_dir, src_html.parent, root_repo)

    gsap_local = stage_dir / "assets" / "vendor" / "gsap.min.js"
    gsap_sig = str(gsap_local.stat().st_mtime) if gsap_local.is_file() else "no_gsap"
    sfx_sig = json.dumps(
        {
            "embed_sfx": bool(embed_sfx),
            "sfx_events": list(sfx_events or []),
            "conclusion_sfx": str(conclusion_sfx or "check"),
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    digest = hashlib.sha1(f"{staged_html}|{w_i}x{h_i}@{fps_i}|{frames}|{gsap_sig}|{sfx_sig}".encode("utf-8")).hexdigest()[:16]
    sha_sidecar = out_mp4.with_suffix(".sha1")

    rr_path = (
        (Path(work_dir) / "render_rapido.py")
        if work_dir and (Path(work_dir) / "render_rapido.py").is_file()
        else (root_repo / "projetos" / "dr-gestao" / "episodios" / "ep-test-edl" / "workspace" / "render_rapido.py")
    )
    render_rapido_mod = _load_workspace_module("render_rapido_fs", rr_path)
    tc = render_rapido_mod.get_toolchain(stage_dir, editor_root=root_repo)

    if not force and out_mp4.is_file() and sha_sidecar.is_file() and sha_sidecar.read_text(encoding="utf-8").strip() == digest:
        pr_cached = subprocess.run(
            [str(tc["ffprobe"]), "-v", "error", "-count_packets", "-select_streams", "v",
             "-show_entries", "stream=nb_read_packets", "-of", "csv=p=0", str(out_mp4)],
            capture_output=True, text=True,
        )
        try:
            if int((pr_cached.stdout or "0").strip()) == frames:
                return {
                    "ok": True,
                    "output_path": str(out_mp4),
                    "frames": frames,
                    "duration_s": round(frames / float(fps_i), 3),
                    "width": w_i,
                    "height": h_i,
                    "fps": fps_i,
                    "cached": True,
                }
        except ValueError:
            pass

    staged_file = stage_dir / f"_fs_scene_{digest}.html"
    staged_file.write_text(staged_html, encoding="utf-8")
    try:
        cmd_hf = [
            tc["node"], str(tc["hf_mjs"]), "render",
            "-c", staged_file.name,
            "-o", str(out_mp4),
            "-w", str(max(1, int(workers))),
            "-f", str(fps_i),
            "--crf", "8",
            "--quiet",
        ]
        res = subprocess.run(cmd_hf, cwd=stage_dir, env=tc["env"], capture_output=True, text=True)
        for cache_tmp in _glob.glob(str(Path(_tempfile.gettempdir()) / "hyperframes-extract-cache-*")):
            shutil.rmtree(cache_tmp, ignore_errors=True)
        if res.returncode != 0 or not out_mp4.is_file():
            raise EdlRenderError(
                f"HyperFrames falhou ao renderizar fullscreen_motion ({src_html.name}): "
                f"{(res.stdout or '')[-1500:]}\n{(res.stderr or '')[-1500:]}"
            )
    finally:
        staged_file.unlink(missing_ok=True)

    pr_out = subprocess.run(
        [str(tc["ffprobe"]), "-v", "error", "-count_packets", "-select_streams", "v",
         "-show_entries", "stream=nb_read_packets", "-of", "csv=p=0", str(out_mp4)],
        capture_output=True, text=True,
    )
    try:
        n_frames = int((pr_out.stdout or "0").strip())
    except ValueError:
        n_frames = 0

    if n_frames == frames + 1:
        trimmed = out_mp4.with_suffix(".trim.mp4")
        subprocess.run(
            [str(tc["ffmpeg"]), "-y", "-loglevel", "error", "-i", str(out_mp4),
             "-map", "0", "-frames:v", str(frames), "-c", "copy", str(trimmed)],
            check=True,
        )
        trimmed.replace(out_mp4)
        n_frames = frames

    if n_frames != frames:
        out_mp4.unlink(missing_ok=True)
        raise EdlRenderError(
            f"fullscreen_motion ({src_html.name}) gerou {n_frames} quadros, esperado {frames}."
        )

    sfx_applied: List[Dict[str, Any]] = []
    if embed_sfx:
        sons_resolved = _resolve_branding_sons_dir(
            root_repo,
            work_dir=Path(work_dir) if work_dir else src_html.parent,
            branding_sons_dir=branding_sons_dir,
        )
        if sons_resolved is not None:
            sfx_plan = build_fullscreen_motion_sfx_events(
                src_html.stem,
                0.0,
                frames / float(fps_i),
                explicit_sfx_events=sfx_events,
                conclusion_sfx=conclusion_sfx,
            )
            _mux_fullscreen_motion_sfx(
                out_mp4,
                frames / float(fps_i),
                sfx_plan,
                sons_resolved,
                Path(tc["ffmpeg"]),
                root_repo,
                work_dir=Path(work_dir) if work_dir else None,
            )
            sfx_applied = [ev for ev in sfx_plan if (sons_resolved / f"{ev['som']}.wav").is_file()]

    sha_sidecar.write_text(digest, encoding="utf-8")
    return {
        "ok": True,
        "output_path": str(out_mp4),
        "frames": n_frames,
        "duration_s": round(n_frames / float(fps_i), 3),
        "width": w_i,
        "height": h_i,
        "fps": fps_i,
        "cached": False,
        "sfx_events": sfx_applied,
    }


def render_edl_to_video(
    edl: Dict[str, Any],
    editorial_plan: Dict[str, Any],
    source_video_path: str | Path,
    brand_profile: Dict[str, Any],
    output_path: str | Path,
    work_dir: Optional[str | Path] = None,
    strict: bool = True,
    authorized_roots: Optional[Sequence[str | Path]] = None,
    apply_loudnorm: bool = True,
    apply_brand_bumpers: bool = True,
) -> Dict[str, Any]:
    # gate lint
    rep = lint_plan(editorial_plan, edl, None)
    ok = rep.get("ok", False)
    failures = rep.get("failures", [])
    if not ok or failures:
        raise EdlRenderError(f"Lint falhou: {failures}")

    src = Path(source_video_path)
    if not src.exists():
        raise EdlRenderError(f"Source video ausente: {src}")

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    wd = (Path(work_dir) if work_dir else out.parent).resolve()
    wd.mkdir(parents=True, exist_ok=True)
    out = out.resolve()

    # Raizes autorizadas para resolution de assets (b-roll/SFX). Inclui o
    # diretorio de trabalho, o diretorio da fonte, raizes da marca configuradas
    # (incluindo assets_base_dir) e raizes extras fornecidas pelo chamador.
    ws_root_inferred, marca_inferred = _infer_workspace_and_brand(wd, src, brand_profile)
    marca_eff = str(edl.get("marca_id") or marca_inferred or "").strip()
    asset_dirs_eff = resolve_brand_asset_dirs(
        ws_root_inferred, marca_eff, brand_profile=brand_profile, repo_root=_REPO_ROOT
    )

    extra_roots: List[Path] = []
    for p in list(authorized_roots or []) + list(asset_dirs_eff.get("brand_roots", [])):
        try:
            rp = Path(p).resolve()
        except (TypeError, ValueError):  # pragma: no cover - defensivo
            continue
        if rp not in extra_roots:
            extra_roots.append(rp)
    auth_roots: List[Path] = [wd, Path(source_video_path).resolve().parent] + extra_roots

    events = edl.get("timeline_events", [])
    target_fmt = edl.get("target_format") or {}
    res_cfg = target_fmt.get("resolution") or [TARGET_W, TARGET_H]
    target_w = int(res_cfg[0]) if len(res_cfg) >= 2 else TARGET_W
    target_h = int(res_cfg[1]) if len(res_cfg) >= 2 else TARGET_H
    target_fps = int(target_fmt.get("fps") or TARGET_FPS)

    # duracao renderizada = soma dos segmentos raw (base continua), alinhada ao frame exato
    raw_sum = sum(max(0.0, _event_times(e)[1] - _event_times(e)[0]) for e in events)
    expected_duration = round(raw_sum, 3)
    if expected_duration <= 0:
        expected_duration = float(edl.get("summary", {}).get("final_duration_seconds", 0.0))
    total_frames = max(1, int(round(expected_duration * target_fps)))
    exact_duration = total_frames / float(target_fps)

    # coleta elementos L2..L6 e camadas extras homologadas do plano
    layers = editorial_plan.get("layers", {}) or {}
    canonical_layers = (
        "L2_titulo_heroi_t10",
        "L3_micro_zoom_bate",
        "L4_lower_third",
        "L5_broll_industrial",
        "L5_fullscreen_motion",
        "L6_sound_design_sync",
    )
    ordered_layer_names = list(canonical_layers) + [
        k for k in layers.keys()
        if k not in canonical_layers and k != "L1_estabelecimento"
    ]
    elements_by_layer: List[Tuple[str, Dict[str, Any]]] = []
    for layer_name in ordered_layer_names:
        layer = layers.get(layer_name, [])
        if isinstance(layer, dict):
            elems = layer.get("elements", []) or layer.get("events", []) or layer.get("keyframes", []) or []
        elif isinstance(layer, list):
            elems = layer
        else:
            elems = []
        if layer_name == "L5_fullscreen_motion" and not elems and isinstance(edl.get("fullscreen_motions"), list):
            elems = edl["fullscreen_motions"]
        for el in elems:
            if isinstance(el, dict):
                elements_by_layer.append((layer_name, el))

    raw_l6_elements = [el for ln, el in elements_by_layer if ln == "L6_sound_design_sync"]

    executed: List[Dict[str, Any]] = []
    isolated: List[Dict[str, Any]] = []
    raw_by_ex_id: Dict[int, Dict[str, Any]] = {}

    # classifica
    for layer_name, el in elements_by_layer:
        cid = _component_of_element(el) or {
            "L2_titulo_heroi_t10": "titulo_heroi",
            "L3_micro_zoom_bate": "micro_zoom_bate",
            "L4_lower_third": "lower_third",
            "L5_broll_industrial": "broll_industrial",
            "L5_fullscreen_motion": "fullscreen_motion",
            "L6_sound_design_sync": "sound_design_sync",
        }.get(layer_name)
        st = resolve_component_status({"component_id": cid, "layer": layer_name})
        if not st.get("executable"):
            isolated.append({
                "element_id": el.get("id") or el.get("element_id"),
                "layer": layer_name,
                "component_id": st.get("component_id"),
                "status": st.get("status"),
                "reason": st.get("reason"),
            })
        else:
            el_in = float(el.get("out_in", el.get("raw_start", 0.0)))
            el_out = float(el.get("out_out", el.get("raw_end", 0.0)))
            if el_in >= expected_duration:
                isolated.append({
                    "element_id": el.get("id") or el.get("element_id"),
                    "layer": layer_name,
                    "component_id": st.get("component_id"),
                    "status": "out_of_bounds",
                    "reason": "elemento inicia apos duracao renderizada",
                })
                continue
            el_out = min(el_out, expected_duration)
            if el_out <= el_in:
                continue
            ex_item = {
                "element_id": el.get("id") or el.get("element_id"),
                "layer": layer_name,
                "component_id": st.get("component_id"),
                "out_in": round(el_in, 3),
                "out_out": round(el_out, 3),
            }
            raw_by_ex_id[id(ex_item)] = el
            executed.append(ex_item)

    # Resolve b-roll assets e mantem contrato de isolamento/seguranca
    broll_resolved: List[Tuple[Dict[str, Any], Dict[str, Any]]] = []
    for ex in list(executed):
        if ex["component_id"] != "broll_industrial":
            continue
        el = raw_by_ex_id.get(id(ex), {})
        if _resolve_broll_asset is None:
            isolated.append({"element_id": ex["element_id"], "layer": ex["layer"], "component_id": "broll_industrial", "status": "legacy_only", "reason": "resolver indisponivel"})
            executed[:] = [e for e in executed if e is not ex]
            continue
        res = _resolve_broll_asset(el or {}, auth_roots)
        if not res.get("resolved"):
            isolated.append({"element_id": ex["element_id"], "layer": ex["layer"], "component_id": "broll_industrial", "status": "legacy_only", "reason": res.get("reason", "nao resolvido")})
            executed[:] = [e for e in executed if e is not ex]
            continue
        broll_resolved.append((ex, res))

    # Resolve fullscreen_motion HTMLs (L5_fullscreen_motion)
    fs_roots: List[Path] = [wd, wd.parent, wd.parent.parent, wd.parent.parent.parent] + auth_roots
    fs_resolved: List[Tuple[Dict[str, Any], Dict[str, Any]]] = []
    for ex in list(executed):
        if ex["component_id"] != "fullscreen_motion":
            continue
        el = raw_by_ex_id.get(id(ex), {})
        res = _resolve_fullscreen_motion_html(el or {}, fs_roots)
        if not res.get("resolved"):
            isolated.append({
                "element_id": ex["element_id"],
                "layer": ex["layer"],
                "component_id": "fullscreen_motion",
                "status": "legacy_only",
                "reason": res.get("reason", "html nao resolvido"),
            })
            executed[:] = [e for e in executed if e is not ex]
            continue
        fs_resolved.append((ex, res))

    # Resolve sound_design_sync items + deduplicacao/cooldown
    sfx_candidates = []
    for ex in list(executed):
        if ex["component_id"] != "sound_design_sync":
            continue
        el = raw_by_ex_id.get(id(ex), {})
        if _resolve_sound_asset is None:
            isolated.append({"element_id": ex["element_id"], "layer": ex["layer"], "component_id": "sound_design_sync", "status": "legacy_only", "reason": "resolver indisponivel"})
            executed[:] = [e for e in executed if e is not ex]
            continue
        res = _resolve_sound_asset(el or {}, auth_roots, brand_profile)
        if not res.get("resolved"):
            isolated.append({"element_id": ex["element_id"], "layer": ex["layer"], "component_id": "sound_design_sync", "status": "legacy_only", "reason": res.get("reason", "nao resolvido")})
            executed[:] = [e for e in executed if e is not ex]
            continue
        cand = {
            "element_id": ex["element_id"],
            "layer": ex["layer"],
            "out_in": ex["out_in"],
            "out_out": ex["out_out"],
            "path": res["path"],
            "sound_ref": el.get("sound_ref"),
            "origin": el.get("origin"),
            "dedup_key": el.get("dedup_key"),
            "volume": res.get("volume", 0.5),
            "duration_s": res.get("duration_s", 1.0),
            "_ex": ex,
        }
        sfx_candidates.append(cand)

    out_dur = float(edl.get("summary", {}).get("final_duration_seconds", 0.0)) or sum(_event_times(e)[3] - _event_times(e)[2] for e in events)
    if _dedup_sfx is not None and sfx_candidates:
        scheduled, dropped = _dedup_sfx(sfx_candidates, out_dur, cooldown_s=0.5, proximity_s=0.10)
    else:
        scheduled, dropped = sfx_candidates, []
    for item in dropped:
        ex = item.get("_ex")
        if ex is not None:
            executed[:] = [e for e in executed if e is not ex]
        isolated.append({
            "element_id": item.get("element_id"),
            "layer": item.get("layer"),
            "component_id": "sound_design_sync",
            "status": "legacy_only",
            "reason": item.get("reason", "deduplicado/cooldown"),
        })
    sound_items: List[Dict[str, Any]] = []
    for item in scheduled:
        item.pop("_ex", None)
        sound_items.append(item)

    # Provisiona motor HTML/CSS/GSAP homologado e corta base continua (6 ms micro-fade)
    _provision_workspace(wd, brand_profile)
    palavras_saida = _build_base_media_and_words(
        edl, src, wd, target_w, target_h, target_fps, exact_duration
    )

    # Stageia b-rolls, cenas fullscreen_motion e SFX resolvidos dentro de wd/media e wd/sons (src permanece imutavel)
    broll_rel_by_ex: Dict[int, str] = {}
    for bi, (ex, res) in enumerate(broll_resolved):
        b_src = Path(res["path"])
        ext = b_src.suffix.lower() or ".png"
        dst = wd / "media" / f"_edl_broll_{bi}{ext}"
        _copy_if_stale(b_src, dst)
        broll_rel_by_ex[id(ex)] = f"media/_edl_broll_{bi}{ext}"

    fs_rel_by_ex: Dict[int, str] = {}
    for fi, (ex, res) in enumerate(fs_resolved):
        fs_dur = max(0.2, float(ex["out_out"]) - float(ex["out_in"]))
        fs_dst = wd / "media" / f"_edl_fs_{fi}.mp4"
        render_fullscreen_motion_scene(
            res["path"],
            fs_dst,
            width=target_w,
            height=target_h,
            fps=target_fps,
            duration=fs_dur,
            work_dir=wd,
            workers=2,
            editor_root=_REPO_ROOT,
            strict_text_check=strict,
            palavras_saida=palavras_saida,
        )
        fs_rel_by_ex[id(ex)] = f"media/_edl_fs_{fi}.mp4"

    sfx_key_by_id: Dict[int, str] = {}
    for si, sfx_item in enumerate(sound_items):
        s_src = Path(sfx_item["path"])
        som_key = f"_edl_sfx_{si}"
        dst_wav = wd / "sons" / f"{som_key}.wav"
        _stage_audio_to_wav(s_src, dst_wav)
        sfx_item["som_key"] = som_key
        # associa pelo element_id + janela temporal
        for ex in executed:
            if ex["component_id"] == "sound_design_sync" and ex["element_id"] == sfx_item["element_id"] and abs(ex["out_in"] - sfx_item["out_in"]) <= 0.02:
                sfx_key_by_id[id(ex)] = som_key

    # Prepara contexto isolado para cenas.py + estagio.py + som.py + titulo_heroi
    estagio_mod = _load_workspace_module("estagio", wd / "estagio.py")
    som_mod = _load_workspace_module("som", wd / "som.py")
    ilustra_mod = _load_workspace_module("ilustra", wd / "ilustra.py")

    visual = (brand_profile or {}).get("visual", {}) or {}
    palette = visual.get("palette", {}) or {}
    prefs = (
        (brand_profile or {}).get("preferencias_edicao")
        or ((brand_profile or {}).get("config_json") or {}).get("preferencias_edicao")
        or {}
    )
    presenter_info = (brand_profile or {}).get("presenter") or {}
    canal_brand = str(prefs.get("canal") or (brand_profile or {}).get("display_name") or "DR. GESTÃO")
    apresentador_brand = str(
        presenter_info.get("name")
        or (brand_profile or {}).get("apresentador")
        or prefs.get("apresentador")
        or "Apresentador"
    )
    cred_brand = str(
        presenter_info.get("credential")
        or (brand_profile or {}).get("credencial")
        or prefs.get("credencial_oficial")
        or ""
    )
    accent_hex = str(palette.get("accent_cyan") or palette.get("primary") or "#2f97d4")
    font_family = str(visual.get("font_family") or "Inter")
    face = presenter_info.get("face_anchor_1080p", [980, 420])
    fx_raw = int(face[0]) if isinstance(face, (list, tuple)) and len(face) >= 1 else 980
    fy_raw = int(face[1]) if isinstance(face, (list, tuple)) and len(face) >= 2 else 420
    fx = int(fx_raw * target_w / float(TARGET_W)) if target_w != TARGET_W else fx_raw
    fy = int(fy_raw * target_h / float(TARGET_H)) if target_h != TARGET_H else fy_raw

    stage_mgr = estagio_mod.StageStateManager(exact_duration, id_viewport="palco")
    comp_mgr = estagio_mod.CompositionManager(stage_mgr)
    sound_bus = som_mod.RobustSoundBus(track_base=20)

    HTML: List[str] = []
    JS: List[str] = []
    AUD: List[str] = []
    ZOOMS: List[Tuple[float, float]] = []
    CAMZ: List[Tuple[float, float]] = []
    PALCO: List[str] = []
    MISS: List[str] = []
    BATES: List[float] = []
    CENAS: List[Tuple[float, float]] = []
    CENAS_B: List[Tuple[float, float]] = []

    def _norm_tok(s: str) -> str:
        s_nfd = unicodedata.normalize("NFD", s.lower())
        return re.sub(r"[^a-z0-9]", "", "".join(c for c in s_nfd if unicodedata.category(c) != "Mn"))

    TOK = [_norm_tok(str(p.get("w", ""))) for p in palavras_saida]
    _id_cnt = [0]

    def nid(p: str) -> str:
        _id_cnt[0] += 1
        return f"{p}{_id_cnt[0]}"

    def r3(x: float) -> float:
        return round(float(x), 3)

    def clip(de: float, ate: float, conteudo: str, cls: str = "ov", estilo: str = "", track: int = 5) -> str:
        cid_loc = nid("c")
        HTML.append(
            f'<div class="clip {cls}" data-start="{r3(de)}" data-duration="{r3(ate - de)}" '
            f'data-track-index="{track}" style="{estilo}"><div class="in" id="{cid_loc}">{conteudo}</div></div>'
        )
        return cid_loc

    def entra(sel: str, t: float, tipo: str = "vidro", d: float = 0.55) -> None:
        if tipo == "vidro":
            JS.append(f'tl.fromTo("#{sel}",{{opacity:0,y:34,scale:.92,rotationX:14,filter:"blur(14px)"}},{{opacity:1,y:0,scale:1,rotationX:0,filter:"blur(0px)",duration:{d},ease:"power3.out"}},{r3(t)});')
        else:
            JS.append(f'tl.fromTo("#{sel}",{{opacity:0,filter:"blur(10px)"}},{{opacity:1,filter:"blur(0px)",duration:{d},ease:"power2.out"}},{r3(t)});')

    def sai(sel: str, ate: float, n: float = 0.28) -> None:
        t_exit = max(0.0, ate - n)
        JS.append(f'tl.to("#{sel}",{{opacity:0,scale:1.05,filter:"blur(14px)",duration:{n},ease:"power2.in"}},{r3(t_exit)});')

    def aparece(sel: str, t: float, d: float = 0.45, y: int = 24, blur: int = 10, sc: float = 0.94) -> None:
        JS.append(f'tl.fromTo("{sel}",{{opacity:0,y:{y},scale:{sc},filter:"blur({blur}px)"}},{{opacity:1,y:0,scale:1,filter:"blur(0px)",duration:{d},ease:"power3.out"}},{r3(t)});')

    def conta(sel: str, t0: float, t1: float, a: float, b: float, prefixo: str = "", sufixo: str = "", casas: int = 0) -> None:
        JS.append(
            f'(function(){{const o={{v:{a}}},el=document.querySelector("{sel}");'
            f'tl.to(o,{{v:{b},duration:{r3(max(0.3, t1 - t0))},ease:"power2.out",onUpdate:()=>{{el.textContent="{prefixo}"+o.v.toLocaleString("pt-BR",{{minimumFractionDigits:{casas},maximumFractionDigits:{casas}}})+"{sufixo}"}}}},{r3(t0)});'
            f'tl.set(el,{{textContent:"{prefixo}{a:,}{sufixo}".replace(/,/g,".")}},0);}})();'
        )

    def _durwav_safe(nome: str) -> float:
        return _wav_duration(wd / "sons" / f"{nome}.wav")

    def sfx(nome: str, t: float, vol: float = 0.5, dur: Optional[float] = None) -> None:
        if not (wd / "sons" / f"{nome}.wav").is_file():
            return
        i = nid("s")
        d = min(dur or 99.0, _durwav_safe(nome))
        AUD.append(f'<audio id="{i}" src="sons/{nome}.wav" data-start="{r3(max(0.0, t))}" data-duration="{r3(d)}" data-track-index="{20 + len(AUD)}" data-volume="{vol}"></audio>')

    def contador_som(t0: float, t1: float, vol: float = 1.0) -> None:
        d = t1 - t0
        arq = "contador_1_5s" if d <= 1.5 else "contador_2_5s" if d <= 2.5 else "contador_3_5s"
        sfx(arq, t0, vol, dur=min(d + 0.05, 3.5))

    def svgpath(nome: str) -> str:
        svg_file = wd / "logos" / f"{nome}.svg"
        if not svg_file.is_file():
            return ""
        m = re.search(r'd="([^"]+)"', svg_file.read_text(encoding="utf-8"))
        return m.group(1) if m else ""

    def tile(nome: str, px: int = 84) -> str:
        r = int(px * 0.24)
        base = f'class="tile" style="width:{px}px;height:{px}px;border-radius:{r}px;'
        g = int(px * 0.58)
        if nome == "claude" and (wd / "logos/claude.svg").is_file():
            return f'<div {base}background:#D97757"><svg width="{g}" height="{g}" viewBox="0 0 24 24"><path fill="#fff" d="{svgpath("claude")}"/></svg></div>'
        if nome == "codex" and (wd / "logos/codex.png").is_file():
            return f'<div {base}background:#fff;overflow:hidden"><img src="logos/codex.png" style="width:100%;height:100%"/></div>'
        if nome == "instagram" and (wd / "logos/instagram.svg").is_file():
            return (
                f'<div {base}background:radial-gradient(circle at 30% 107%,#fdf497 0%,#fdf497 5%,#fd5949 45%,#d6249f 60%,#285AEB 90%)">'
                f'<svg width="{g}" height="{g}" viewBox="0 0 24 24"><path fill="#fff" d="{svgpath("instagram")}"/></svg></div>'
            )
        if nome == "youtube" and (wd / "logos/youtube.svg").is_file():
            return f'<div {base}background:#fff"><svg width="{int(px * .66)}" height="{int(px * .66)}" viewBox="0 0 24 24"><path fill="#FF0000" d="{svgpath("youtube")}"/></svg></div>'
        if nome == "tiktok" and (wd / "logos/tiktok.svg").is_file():
            p_tk = svgpath("tiktok")
            return (
                f'<div {base}background:#000"><svg width="{g}" height="{g}" viewBox="-1 -1 26 26">'
                f'<path fill="#25F4EE" transform="translate(-0.7,-0.5)" d="{p_tk}"/><path fill="#FE2C55" transform="translate(0.7,0.5)" d="{p_tk}"/>'
                f'<path fill="#fff" d="{p_tk}"/></svg></div>'
            )
        if nome == "whatsapp" and (wd / "logos/whatsapp.svg").is_file():
            return f'<div {base}background:#25D366"><svg width="{g}" height="{g}" viewBox="0 0 24 24"><path fill="#fff" d="{svgpath("whatsapp")}"/></svg></div>'
        return f'<div {base}background:#2f97d4;color:#fff;display:grid;place-items:center;font-weight:800;font-size:{int(px * 0.45)}px">★</div>'

    IC_SVG = {
        "check": '<path d="M5 12.5l4.2 4.2L19 7"/>',
        "raio": '<path d="M13 2.5L5 13.5h6.2L10.5 21.5l8-11h-6.2z"/>',
        "alvo": '<circle cx="12" cy="12" r="8.5"/><circle cx="12" cy="12" r="4.5"/><circle cx="12" cy="12" r="1"/>',
    }

    def ic(nome: str, px: int = 40, cor: str = "currentColor", sw: float = 1.8) -> str:
        return f'<svg class="ic" width="{px}" height="{px}" viewBox="0 0 24 24" fill="none" stroke="{cor}" stroke-width="{sw}" stroke-linecap="round" stroke-linejoin="round">{IC_SVG.get(nome, IC_SVG["raio"])}</svg>'

    env_ctx: Dict[str, Any] = {
        "AQUI": wd,
        "ROOT_EDITOR": _REPO_ROOT,
        "PAL": palavras_saida,
        "CFG": {"rosto": [fx_raw, fy_raw], "marca": {"destaque": accent_hex, "fonte": font_family}},
        "TOK": TOK,
        "HTML": HTML,
        "JS": JS,
        "AUD": AUD,
        "ZOOMS": ZOOMS,
        "CAMZ": CAMZ,
        "PALCO": PALCO,
        "MISS": MISS,
        "BATES": BATES,
        "CENAS": CENAS,
        "CENAS_B": CENAS_B,
        "DUR": exact_duration,
        "FPS": target_fps,
        "nid": nid,
        "r3": r3,
        "clip": clip,
        "entra": entra,
        "aparece": aparece,
        "sai": sai,
        "sfx": sfx,
        "conta": conta,
        "contador_som": contador_som,
        "tile": tile,
        "ic": ic,
        "svgpath": svgpath,
        "_durwav": _durwav_safe,
        "STAGE_MGR": stage_mgr,
        "COMP_MGR": comp_mgr,
        "SOUND_BUS": sound_bus,
    }

    old_sys_path = list(sys.path)
    old_estagio_mod = sys.modules.get("estagio")
    sys.path.insert(0, str(wd))
    sys.modules["estagio"] = estagio_mod
    try:
        cenas_ns = dict(env_ctx)
        exec(compile((wd / "cenas.py").read_text(encoding="utf-8"), str(wd / "cenas.py"), "exec"), cenas_ns)
        cn = SimpleNamespace(**{k: v for k, v in cenas_ns.items() if not k.startswith("__")})
        cn.conecta_nucleo(stage_mgr, comp_mgr, sound_bus)

        def _adapt_dims(start_idx: int) -> None:
            if (target_w, target_h) == (TARGET_W, TARGET_H):
                return
            for hi in range(start_idx, len(HTML)):
                HTML[hi] = HTML[hi].replace("width:1920px;height:1080px", f"width:{target_w}px;height:{target_h}px")

        def _overlaps(ranges: List[Tuple[float, float]], s: float, e: float) -> bool:
            return any(not (e <= rs + 0.05 or s >= re_ - 0.05) for rs, re_ in ranges)

        th_idx = 0
        card_idx = 0
        last_bate_end = -1.0
        palco_busy: List[Tuple[float, float]] = []
        fs_sfx_records: List[Dict[str, Any]] = []
        lt_uses_portrait_scale = target_w < 1200

        ordered_exec = sorted(executed, key=lambda x: (float(x["out_in"]), float(x["out_out"])))
        for ex in ordered_exec:
            cid = ex["component_id"]
            oi = float(ex["out_in"])
            oo = float(ex["out_out"])
            el = raw_by_ex_id.get(id(ex), {})
            dur_el = max(0.2, oo - oi)

            if cid == "titulo_heroi":
                txt = _clean_plain_text(el.get("text") or el.get("titulo") or el.get("texto"), default="Destaque")
                lado_pref = str(el.get("lado") or ("esq" if th_idx % 2 == 0 else "dir")).lower()
                if lado_pref not in ("esq", "dir"):
                    lado_pref = "esq" if th_idx % 2 == 0 else "dir"
                th_idx += 1

                if target_h > target_w:
                    card_w = min(860, target_w - 144)
                    px_x = (target_w - card_w) // 2
                    px_y = 140 if fy > 380 else max(120, target_h - 460)
                else:
                    card_w = min(640, int(target_w * 0.34))
                    px_x = 72 if lado_pref == "esq" else (target_w - 72 - card_w)
                    # Garante desobstrucao do rosto caso ancora configurada esteja no mesmo flanco
                    if abs((px_x + card_w / 2.0) - fx) < (card_w / 2.0 + 180):
                        px_x = (target_w - 72 - card_w) if fx < (target_w / 2.0) else 72
                    px_y = 148 if fy > 260 else max(80, target_h - 360)

                perf = str(el.get("profile") or el.get("perfil") or "destaque-ciano").strip()
                perf_cls = {
                    "alta-minutagem": "th-heroi-alta-minutagem",
                    "virada-chave": "th-heroi-virada-chave",
                    "destaque-ciano": "th-heroi-destaque-ciano",
                }.get(perf, "th-heroi-destaque-ciano")

                th_id = nid("th")
                if _gerar_html_titulo_heroi is not None and _animar_titulo_heroi is not None:
                    th_inner = _gerar_html_titulo_heroi(
                        txt,
                        clip_id=th_id,
                        elemento_id="t2",
                        classe_container=f"cn-t10-heroi {perf_cls}",
                    )
                    card_html = (
                        f'<div class="cn-sidecar escuro cn-t10-card" style="width:{card_w}px">'
                        f'<div class="cn-badge azul escuro"><span class="cn-badge-dot"></span>'
                        f'<span>{_html.escape(canal_brand.upper())}</span></div>'
                        f'{th_inner}</div>'
                    )
                    c_id = clip(oi, oo, card_html, cls="ov cn-t10-clip", estilo=f"left:{px_x}px;top:{px_y}px", track=8)
                    d_ent = min(0.45, max(0.18, dur_el * 0.35))
                    d_sai = min(0.28, max(0.12, dur_el * 0.22))
                    entra(c_id, oi, tipo="vidro", d=d_ent)
                    t_anim = round(min(oo - 0.15, oi + 0.08), 3)
                    js_th = _animar_titulo_heroi(
                        clip_id=th_id,
                        elemento_id="t2",
                        t_inicio=t_anim,
                        duration=min(0.32, max(0.14, dur_el * 0.28)),
                    )
                    for line in js_th.splitlines():
                        if line.strip():
                            JS.append(line.strip())
                    sai(c_id, oo, n=d_sai)
                else:  # pragma: no cover - fallback caso titulo_heroi indisponivel
                    cn.card_flutuante(oi, oo, titulo=_html.escape(txt), lado=lado_pref, x=px_x, y=px_y, w=card_w, escuro=True)
                cn._som("whoosh_curto", max(0.0, oi - 0.06), 0.35)
                cn._som("swish", max(0.0, oo - 0.28), 0.25)

            elif cid == "lower_third":
                raw_lt = _clean_plain_text(
                    el.get("nome") or el.get("text") or el.get("titulo") or el.get("texto") or "",
                    default="",
                )
                cred_explicit = _clean_plain_text(el.get("credencial") or el.get("subtitle") or "", default="")
                onde_explicit = _clean_plain_text(el.get("onde") or "", default="")
                if " · " in raw_lt and not cred_explicit:
                    p1, p2 = [s.strip() for s in raw_lt.split(" · ", 1)]
                    nome = p1 or apresentador_brand
                    cred = p2
                    canal = onde_explicit or (
                        cred_brand.split("·")[-1].strip()
                        if "dr. gestão" in p1.lower() and "·" in cred_brand
                        else canal_brand
                    )
                else:
                    nome = raw_lt or apresentador_brand
                    cred = cred_explicit or cred_brand
                    canal = onde_explicit or canal_brand
                if cred == canal:
                    canal = canal_brand if cred != canal_brand else "Destaque Editorial"
                lt_x = 48 if target_w < 1200 else 80
                lt_y = max(200, target_h - 360) if target_h > target_w else 748
                t_nome = round(min(oo - 0.35, max(oi + 0.06, oi + dur_el * 0.12)), 3)
                t_cred = round(min(oo - 0.55, max(t_nome + 0.18, oi + dur_el * 0.35)), 3)
                creds: List[Tuple[float, str, str, str]] = []
                if dur_el >= 1.2 and (cred or canal):
                    logo_name = str(el.get("logo") or "youtube")
                    creds = [(t_cred, tile(logo_name, 44), cred or "Canal", canal or cred)]
                cn.lower_third(oi, oo, t_nome=t_nome, nome=_html.escape(nome), credenciais=tuple(creds), x=lt_x, y=lt_y)

            elif cid == "micro_zoom_bate":
                t_bate = max(0.06, oi)
                if t_bate - 0.05 <= last_bate_end + 0.01:
                    t_bate = round(last_bate_end + 0.06, 3)
                if t_bate + 0.25 <= exact_duration:
                    segura = max(0.18, min(0.90, oo - t_bate - 0.18))
                    s_val = float(el.get("scale", 1.08))
                    cn.bate(t_bate, s=s_val, segura=segura)
                    last_bate_end = t_bate + segura + 0.55

            elif cid == "broll_industrial":
                rel_path = broll_rel_by_ex.get(id(ex))
                if not rel_path:
                    continue
                is_card = bool(el.get("card", False))
                estilo_br = str(el.get("estilo", "cheia"))
                pip_apr = bool(el.get("pip_apresentador", False))
                if pip_apr and _overlaps(palco_busy, oi, oo):
                    pip_apr = False
                if pip_apr:
                    palco_busy.append((oi, oo))
                bw = int(el.get("w", min(1400, target_w - 120) if target_h > target_w else 1400))
                bx = int(el.get("x", (target_w - bw) // 2))
                by = int(el.get("y", 150))
                n_before = len(HTML)
                cn.broll(
                    oi,
                    oo,
                    rel_path,
                    card=is_card,
                    estilo=estilo_br,
                    x=bx,
                    y=by,
                    w=bw,
                    kb=float(el.get("kb", 1.06)),
                    media_start=float(el.get("media_start", 0.0)),
                    pip_apresentador=pip_apr,
                    pip_pos=str(el.get("pip_pos", "inf-dir")),
                )
                _adapt_dims(n_before)

            elif cid in ("card_flutuante", "barra_progresso", "stepper"):
                lado_pref = str(el.get("lado") or ("dir" if card_idx % 2 == 0 else "esq")).lower()
                if lado_pref not in ("esq", "dir"):
                    lado_pref = "dir"
                card_idx += 1
                cw = min(int(el.get("w", 480)), target_w - 120)
                cx = el.get("x")
                if cx is None:
                    cx = ((target_w - cw) // 2) if target_h > target_w else ((target_w - 72 - cw) if lado_pref == "dir" else 72)
                cy = int(el.get("y", 180 if target_h > target_w else 260))
                tit_cf = _clean_plain_text(el.get("titulo") or el.get("text") or el.get("texto"), default="Ponto-chave")
                cn.card_flutuante(
                    oi,
                    oo,
                    titulo=_html.escape(tit_cf),
                    badge=_html.escape(_clean_plain_text(el.get("badge") or "", default="")),
                    badge_tipo=str(el.get("badge_tipo") or "azul"),
                    valor=_html.escape(_clean_plain_text(el.get("valor") or "", default="")),
                    sub=_html.escape(_clean_plain_text(el.get("sub") or el.get("subtitle") or "", default="")),
                    lado=lado_pref,
                    x=int(cx),
                    y=cy,
                    w=cw,
                    escuro=bool(el.get("escuro", True)),
                    progresso=el.get("progresso", 75 if cid == "barra_progresso" else None),
                    meta=el.get("meta"),
                    etapas=el.get("etapas", 3 if cid == "stepper" else None),
                    etapa_ativa=int(el.get("etapa_ativa", 1)),
                )

            elif cid == "pip_stage":
                if dur_el >= 1.2 and not _overlaps(palco_busy, oi, oo):
                    palco_busy.append((oi, oo))
                    n_before = len(HTML)
                    cn.pip_stage(
                        oi,
                        oo,
                        midia="",
                        badge=_html.escape(_clean_plain_text(el.get("badge") or canal_brand or "DESTAQUE")),
                        titulo=_html.escape(_clean_plain_text(el.get("titulo") or el.get("text") or el.get("texto"), default="Resumo")),
                        sub=_html.escape(_clean_plain_text(el.get("sub") or "", default="")),
                        etapas=int(el.get("etapas", 4)),
                        etapa_ativa=int(el.get("etapa_ativa", 1)),
                        w=min(1120, target_w - 160),
                        h=min(630, int(target_h * 0.55)),
                        x=80,
                        y=140,
                    )
                    _adapt_dims(n_before)

            elif cid == "split_stage":
                if dur_el >= 1.2 and not _overlaps(palco_busy, oi, oo):
                    palco_busy.append((oi, oo))
                    n_before = len(HTML)
                    cn.split_stage(
                        oi,
                        oo,
                        proporcao=str(el.get("proporcao") or "33/67"),
                        lado=str(el.get("lado") or "esq"),
                        badge=_html.escape(_clean_plain_text(el.get("badge") or canal_brand or "DESTAQUE")),
                        titulo=_html.escape(_clean_plain_text(el.get("titulo") or el.get("text") or el.get("texto"), default="Tese")),
                        sub=_html.escape(_clean_plain_text(el.get("sub") or "", default="")),
                    )
                    _adapt_dims(n_before)

            elif cid == "fullscreen_motion":
                rel_path = fs_rel_by_ex.get(id(ex))
                if not rel_path:
                    continue
                CENAS_B.append((oi, oo))
                fs_vid = nid("fsm")
                z_idx = int(el.get("z_index") or 18)
                HTML.append(
                    f'<video id="{fs_vid}" class="clip cn-fullscreen-motion" src="{rel_path}" muted playsinline '
                    f'data-start="{r3(oi)}" data-duration="{r3(dur_el)}" data-media-start="0.000" '
                    f'data-track-index="18" style="position:absolute;left:0;top:0;width:{target_w}px;height:{target_h}px;'
                    f'object-fit:cover;z-index:{z_idx};pointer-events:none"></video>'
                )
                tr_in = str(el.get("transition_in") or "clean_fade").lower()
                tr_out = str(el.get("transition_out") or "clean_fade").lower()
                wipe_rel = (
                    "overlays/transicoes/transicao_wipe_drgestao_9x16.webm"
                    if target_h > target_w
                    else "overlays/transicoes/transicao_wipe_drgestao_16x9.webm"
                )
                has_wipe = (wd / wipe_rel).is_file()
                if tr_in == "transicao_marca" and has_wipe:
                    n_before = len(HTML)
                    cn.transicao_marca(oi, dur=min(0.85, max(0.4, dur_el * 0.3)), arquivo=wipe_rel)
                    _adapt_dims(n_before)
                    JS.append(f'tl.fromTo("#{fs_vid}",{{opacity:0}},{{opacity:1,duration:0.15,ease:"power1.out"}},{r3(oi)});')
                else:
                    JS.append(f'tl.fromTo("#{fs_vid}",{{opacity:0,scale:1.02}},{{opacity:1,scale:1,duration:0.28,ease:"power2.out"}},{r3(oi)});')
                if tr_out == "transicao_marca" and has_wipe:
                    n_before = len(HTML)
                    cn.transicao_marca(oo, dur=min(0.85, max(0.4, dur_el * 0.3)), arquivo=wipe_rel)
                    _adapt_dims(n_before)
                    JS.append(f'tl.to("#{fs_vid}",{{opacity:0,duration:0.15,ease:"power1.in"}},{r3(max(oi, oo - 0.15))});')
                else:
                    JS.append(f'tl.to("#{fs_vid}",{{opacity:0,duration:0.26,ease:"power2.in"}},{r3(max(oi, oo - 0.26))});')

                fs_scene_id = str(el.get("scene_id") or el.get("id_cena") or fs_vid)
                auto_sfx_list = build_fullscreen_motion_sfx_events(
                    fs_scene_id,
                    oi,
                    dur_el,
                    explicit_sfx_events=el.get("sfx_events"),
                    include_entry_whoosh=(not (tr_in == "transicao_marca" and has_wipe)),
                    include_exit_swish=(not (tr_out == "transicao_marca" and has_wipe)),
                    conclusion_sfx=str(el.get("conclusion_sfx") or "check"),
                )
                for sfx_ev in auto_sfx_list:
                    s_name = str(sfx_ev["som"])
                    if not (wd / "sons" / f"{s_name}.wav").is_file():
                        continue
                    t_ev = float(sfx_ev["t"])
                    v_ev = float(sfx_ev["volume"])
                    eid_ev = str(sfx_ev["event_id"])
                    if sfx_ev.get("modo") == "explicit":
                        sound_bus.registrar_explicito(eid_ev, s_name, t_ev, volume=v_ev, origem="fullscreen_motion")
                    else:
                        sound_bus.registrar_automatico(eid_ev, s_name, t_ev, volume=v_ev, origem="fullscreen_motion")
                    fs_sfx_records.append(dict(sfx_ev))

            elif cid == "transicao_marca":
                rel_tr = str(el.get("arquivo") or "overlays/transicoes/transicao_wipe_drgestao_16x9.webm")
                if (wd / rel_tr).is_file():
                    n_before = len(HTML)
                    cn.transicao_marca(oi, dur=min(1.2, max(0.4, dur_el)), arquivo=rel_tr)
                    _adapt_dims(n_before)

            elif cid == "sound_design_sync":
                pass  # explicitamente registrado abaixo a partir de sound_items dedup/validados

        # Registra L6 validado/deduplicado no SOUND_BUS
        for si, sfx_item in enumerate(sound_items):
            sound_bus.registrar_explicito(
                event_id=f"edl_{si}_{sfx_item['element_id']}",
                som=sfx_item["som_key"],
                t=float(sfx_item["out_in"]),
                volume=float(sfx_item.get("volume", 0.5)),
                dur=max(0.05, float(sfx_item["out_out"]) - float(sfx_item["out_in"])),
                origem="editorial",
            )

        stage_js, camz_stage, _ = stage_mgr.compilar()
        if (target_w, target_h) != (TARGET_W, TARGET_H):
            stage_js = [
                s.replace("width:1920,height:1080", f"width:{target_w},height:{target_h}")
                 .replace("width: 1920, height: 1080", f"width:{target_w},height:{target_h}")
                for s in stage_js
            ]
        comp_js = comp_mgr.compilar()
    finally:
        sys.path[:] = old_sys_path
        if old_estagio_mod is not None:
            sys.modules["estagio"] = old_estagio_mod
        else:
            sys.modules.pop("estagio", None)

    for cz in camz_stage:
        if cz not in CAMZ:
            CAMZ.append(cz)

    full_js: List[str] = []
    for chunk in (stage_js + comp_js + JS):
        for line in str(chunk).splitlines():
            st_line = line.strip()
            if st_line:
                full_js.append(st_line)

    voz_tag = f'<audio id="voz" src="media/voz.wav" data-start="0" data-duration="{exact_duration}" data-track-index="10" data-volume="1"></audio>'
    if raw_l6_elements:
        # Quando L6 esta presente no plano (incluindo testes de isolamento/RMS), emite apenas SFX explicitos validados
        # e os SFX sincronizados das cenas fullscreen_motion
        explicit_bus = som_mod.RobustSoundBus(track_base=20)
        for si, sfx_item in enumerate(sound_items):
            explicit_bus.registrar_explicito(
                event_id=f"edl_{si}_{sfx_item['element_id']}",
                som=sfx_item["som_key"],
                t=float(sfx_item["out_in"]),
                volume=float(sfx_item.get("volume", 0.5)),
                dur=max(0.05, float(sfx_item["out_out"]) - float(sfx_item["out_in"])),
                origem="editorial",
            )
        for fsi, rec in enumerate(fs_sfx_records):
            s_name = str(rec.get("som") or "").strip()
            if not s_name or not (wd / "sons" / f"{s_name}.wav").is_file():
                continue
            eid_fs = str(rec.get("event_id") or f"fs_{fsi}")
            t_fs = float(rec.get("t", 0.0))
            v_fs = float(rec.get("volume", 0.35))
            if rec.get("modo") == "explicit":
                explicit_bus.registrar_explicito(eid_fs, s_name, t_fs, volume=v_fs, origem="fullscreen_motion")
            else:
                explicit_bus.registrar_automatico(eid_fs, s_name, t_fs, volume=v_fs, origem="fullscreen_motion")
        sfx_tags = explicit_bus.gerar_tags_html(duracao_cache_fn=_durwav_safe)
    else:
        sfx_tags = [
            t for t in sound_bus.gerar_tags_html(duracao_cache_fn=_durwav_safe)
            if (m_src := re.search(r'src="([^"]+)"', t)) and (wd / m_src.group(1)).is_file()
        ]
    audio_tags = [voz_tag] + sfx_tags

    # CSS oficial (estilo + ilustra + cenas + titulo_heroi + overrides responsivos)
    css_blocks: List[str] = []
    for css_file in (
        wd / "estilo.css",
        wd / "ilustra.css",
        wd / "cenas.css",
        _REPO_ROOT / "motion_library" / "components" / "titulo_heroi" / "titulo_heroi.css",
    ):
        if css_file.is_file():
            css_blocks.append(css_file.read_text(encoding="utf-8"))

    # @font-face apenas para .woff2 que realmente existam em wd/fonts (zero 404)
    fontes_css = ""
    if (wd / "fonts").is_dir():
        fontes_css = "".join(
            f'@font-face{{font-family:"Inter";src:url("fonts/inter-{w}.woff2") format("woff2");font-weight:{w};font-style:normal}}'
            for w in (400, 500, 600, 700, 800)
            if (wd / "fonts" / f"inter-{w}.woff2").is_file()
        )

    fx_pct = (fx / float(max(1, target_w))) * 100.0
    fy_pct = (fy / float(max(1, target_h))) * 100.0
    t10_clamp = "clamp(34px, 4.4vw, 52px)" if target_h > target_w else "clamp(34px, 2.5vw, 48px)"
    portrait_lt_css = (
        f".cn-nm{{max-width:{max(320, target_w - 96)}px;transform:scale(0.88);transform-origin:top left}}"
        if lt_uses_portrait_scale
        else ""
    )
    overrides_css = (
        f':root{{--destaque:{accent_hex};}}'
        f'#root{{font-family:"{font_family}","Inter",system-ui,sans-serif;}}'
        f'html,body,#root,#palco{{width:{target_w}px !important;height:{target_h}px !important;margin:0;padding:0;overflow:hidden;}}'
        f'#base{{width:{target_w}px !important;height:{target_h}px !important;object-fit:cover;transform-origin:{fx_pct:.2f}% {fy_pct:.2f}% !important;}}'
        f'.cn-t10-card{{padding:24px 30px;border-radius:22px;}}'
        f'.cn-t10-card .cn-t10-heroi,.cn-t10-card .th-heroi-wrap{{max-width:100%;white-space:normal !important;font-size:{t10_clamp} !important;line-height:1.14 !important;overflow-wrap:break-word;margin-top:6px;}}'
        f'{portrait_lt_css}'
    )
    full_css = fontes_css + "\n".join(css_blocks) + "\n" + overrides_css

    res_mode = "portrait" if target_h > target_w else "landscape"
    gsap_src = "assets/vendor/gsap.min.js" if (wd / "assets" / "vendor" / "gsap.min.js").is_file() else "https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"
    html_doc = f'''<!doctype html>
<html lang="pt-BR" data-resolution="{res_mode}">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width={target_w}, height={target_h}" />
<script src="{gsap_src}"></script>
<style>{full_css}</style>
</head>
<body>
<div id="root" data-composition-id="main" data-start="0" data-duration="{exact_duration}" data-width="{target_w}" data-height="{target_h}">
  <div id="palco"><video id="base" class="clip" src="media/base.mp4" muted playsinline data-start="0" data-duration="{exact_duration}" data-track-index="0"></video>{chr(10).join(PALCO)}</div>
  {chr(10).join(HTML)}
  {chr(10).join(audio_tags)}
</div>
<script>
const tl = gsap.timeline({{ paused: true }});
tl.set({{}}, {{}}, {exact_duration});
tl.set("#palco", {{scale:1,x:0,y:0}}, 0);
{chr(10).join(full_js)}
window.__timelines["main"] = tl;
tl.seek(0);
</script>
</body>
</html>'''
    (wd / "index.html").write_text(html_doc, encoding="utf-8")

    partes = {
        "dur": exact_duration,
        "fps": target_fps,
        "width": target_w,
        "height": target_h,
        "estilo": full_css,
        "palco": PALCO,
        "html": HTML,
        "js": full_js,
        "audio": audio_tags,
        "zooms_camera": CAMZ,
    }
    (wd / "partes.json").write_text(json.dumps(partes, ensure_ascii=False), encoding="utf-8")

    # Valida anti-transcricao literal e palavras vazias via checa_texto.py
    checa_mod = _load_workspace_module("checa_texto", wd / "checa_texto.py")
    ruins = checa_mod.problemas(html_doc, palavras_saida)
    if ruins and strict:
        raise EdlRenderError(f"checa_texto bloqueou motion com transcricao literal/vazia: {ruins}")

    # Renderiza trechos via HyperFrames + composicao rapida e masteriza em -14 LUFS / -1 dBTP
    render_rapido_mod = _load_workspace_module("render_rapido", wd / "render_rapido.py")
    try:
        render_res = render_rapido_mod.executar_render(
            wd,
            out,
            workers=4,
            junta_gap=2.0,
            margem=0.2,
            so_trechos=False,
            apply_loudnorm=apply_loudnorm,
            editor_root=_REPO_ROOT,
        )
    except Exception as exc:
        raise EdlRenderError(f"Render HyperFrames falhou: {exc}") from exc

    (wd / "_edl_filter.txt").write_text(render_res.get("master_filter") or "", encoding="utf-8")

    # Vinhetas inteligentes multi-marca (Niveis 1/2/3 para Intro e Outro)
    final_expected_duration = exact_duration
    final_total_frames = total_frames
    bumper_report: Dict[str, Any] = {}
    warnings_out: List[str] = []
    if apply_brand_bumpers:
        ar_str = str(target_fmt.get("aspect_ratio") or ("9:16" if target_h > target_w else "16:9"))
        planned_bumpers = edl.get("brand_bumpers") if isinstance(edl.get("brand_bumpers"), dict) else {}
        intro_plan = (
            dict(planned_bumpers["intro"])
            if isinstance(planned_bumpers.get("intro"), dict)
            else resolve_brand_bumper(
                "intro", ar_str, workspace_root=ws_root_inferred, marca_id=marca_eff, brand_profile=brand_profile, repo_root=_REPO_ROOT
            )
        )
        outro_plan = (
            dict(planned_bumpers["outro"])
            if isinstance(planned_bumpers.get("outro"), dict)
            else resolve_brand_bumper(
                "outro", ar_str, workspace_root=ws_root_inferred, marca_id=marca_eff, brand_profile=brand_profile, repo_root=_REPO_ROOT
            )
        )
        intro_ready = ensure_bumper_mp4(
            intro_plan,
            brand_profile=brand_profile,
            asset_dirs=asset_dirs_eff,
            work_dir=wd / "_bumpers",
            repo_root=_REPO_ROOT,
        )
        outro_ready = ensure_bumper_mp4(
            outro_plan,
            brand_profile=brand_profile,
            asset_dirs=asset_dirs_eff,
            work_dir=wd / "_bumpers",
            repo_root=_REPO_ROOT,
        )
        bumper_apply = apply_intro_outro_to_video(
            out,
            out,
            intro_plan=intro_ready,
            outro_plan=outro_ready,
            width=target_w,
            height=target_h,
            fps=target_fps,
            apply_loudnorm=apply_loudnorm,
        )
        final_expected_duration = float(bumper_apply.get("final_duration_seconds") or exact_duration)
        final_total_frames = max(1, int(round(final_expected_duration * target_fps)))
        warnings_out.extend(list(bumper_apply.get("warnings") or []))
        bumper_report = {
            "intro": intro_ready,
            "outro": outro_ready,
            "applied": {
                "intro_applied": bumper_apply.get("intro_applied", False),
                "outro_applied": bumper_apply.get("outro_applied", False),
                "fade_out_applied": bumper_apply.get("fade_out_applied", False),
            },
        }

    report = {
        "executed_events": executed,
        "isolated_events": isolated,
        "output_path": str(out),
        "warnings": warnings_out,
        "brand_bumpers": bumper_report,
        "target_format": {
            "width": target_w,
            "height": target_h,
            "fps": target_fps,
            "total_frames": final_total_frames,
            "expected_duration_seconds": round(final_expected_duration, 6),
        },
        "verification": verify_rendered_video(
            out,
            final_expected_duration,
            expected_width=target_w,
            expected_height=target_h,
        ),
    }
    return report
