# -*- coding: utf-8 -*-
"""
core/video_verify.py

QA audiovisual automatizado, local e deterministico, do master 16:9
(1920x1080, 30fps, H.264/yuv420p + AAC 48kHz estéreo).

Nao depende de marca, rede, IA ou arquivos fora do workspace. Todas as
medidas são feitas via ffprobe/ffmpeg (astats, ebur128, blackdetect).

API principal:
    verify_video_av(video_path, expected_duration_s, qa_windows=..., ...)
        -> relatorio dict {ok, problems, warnings, video, audio, ...}

`qa_windows` aceita itens no formato:
    {"layer": "L6_sound_design_sync", "kind": "audio", "start": 0.5, "end": 0.9}
    {"layer": "L4_lower_third", "kind": "visual", "start": 1.0, "end": 2.5}
"""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

TARGET_W, TARGET_H = 1920, 1080
TARGET_FPS = 30.0
AUDIO_SR = 48000
AUDIO_CHANNELS = 2

FPS_TOLERANCE = 0.05
DURATION_TOLERANCE_S = 0.08
DEFAULT_TARGET_LUFS = -14.0
DEFAULT_LUFS_TOLERANCE = 1.5
DEFAULT_MAX_TRUE_PEAK_DBTP = -0.8
CLIPPING_PEAK_DBFS = -0.1
SILENCE_RMS_DBFS = -60.0


class VideoVerifyError(Exception):
    """Erro de verificacao audiovisual."""


# ---------------------------------------------------------------------------
# Helpers de execucao
# ---------------------------------------------------------------------------


def _run(cmd: Sequence[str], *, timeout: float = 240.0) -> subprocess.CompletedProcess:
    return subprocess.run(
        list(cmd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )


def probe_media(path: str | Path) -> Dict[str, Any]:
    """Executa ffprobe e retorna o JSON completo (format + streams)."""
    p = Path(path)
    if not p.is_file() or p.stat().st_size <= 0:
        raise VideoVerifyError(f"arquivo inexistente ou vazio: {p}")
    res = _run([
        "ffprobe", "-v", "error", "-print_format", "json",
        "-show_format", "-show_streams", str(p),
    ])
    if res.returncode != 0:
        raise VideoVerifyError(f"ffprobe falhou: {res.stderr.strip()[:400]}")
    try:
        return json.loads(res.stdout)
    except json.JSONDecodeError as exc:  # pragma: no cover - defensivo
        raise VideoVerifyError(f"ffprobe retornou JSON invalido: {exc}") from exc


def _parse_rate(rate: Any) -> Optional[float]:
    if not isinstance(rate, str) or "/" not in rate:
        return None
    try:
        num, den = (float(x) for x in rate.split("/", 1))
    except (TypeError, ValueError):
        return None
    if den <= 0:
        return None
    return num / den


def _normalize_sar(sar: Any) -> Optional[float]:
    if not isinstance(sar, str) or ":" not in sar:
        return None
    try:
        num, den = (float(x) for x in sar.split(":", 1))
    except (TypeError, ValueError):
        return None
    if den <= 0:
        return None
    return num / den


def count_loudnorm(filtergraph_text: Optional[str]) -> int:
    """Conta ocorrencias do filtro loudnorm em um filtergraph."""
    if not filtergraph_text:
        return 0
    return len(re.findall(r"\bloudnorm\b", filtergraph_text))


# ---------------------------------------------------------------------------
# Medicoes de audio
# ---------------------------------------------------------------------------


def parse_astats(stderr: str) -> Dict[str, Optional[float]]:
    """Extrai RMS/Peak level (dBFS) da saida textual do filtro astats."""
    def _last(pattern: str) -> Optional[float]:
        found = re.findall(pattern, stderr)
        return float(found[-1]) if found else None

    peak_raw = re.findall(r"Peak level dB:\s*(-?[\d.]+|-inf)", stderr)
    peak: Optional[float]
    if not peak_raw:
        peak = None
    elif peak_raw[-1] == "-inf":
        peak = float("-inf")
    else:
        peak = float(peak_raw[-1])

    return {
        "rms_db": _last(r"RMS level dB:\s*(-?[\d.]+)"),
        "peak_db": peak,
        "flat_factor": _last(r"Flat factor:\s*([\d.]+)"),
        "noise_floor_db": _last(r"Noise floor dB:\s*(-?[\d.]+)"),
    }


def measure_astats(
    video_path: str | Path,
    *,
    start: Optional[float] = None,
    duration: Optional[float] = None,
) -> Dict[str, Optional[float]]:
    """Mede RMS/peek via astats (opcionalmente em uma janela temporal)."""
    cmd: List[str] = ["ffmpeg", "-hide_banner", "-nostats"]
    if start is not None:
        cmd += ["-ss", f"{max(0.0, float(start)):.6f}"]
    if duration is not None:
        cmd += ["-t", f"{max(0.001, float(duration)):.6f}"]
    cmd += ["-i", str(video_path), "-af", "astats=metadata=0", "-f", "null", "-"]
    res = _run(cmd)
    if res.returncode != 0:
        raise VideoVerifyError(f"astats falhou: {res.stderr.strip()[:400]}")
    return parse_astats(res.stderr)


def measure_ebur128(video_path: str | Path) -> Dict[str, Optional[float]]:
    """Mede Integrated Loudness (LUFS), LRA e True Peak (dBTP) via ebur128."""
    res = _run([
        "ffmpeg", "-hide_banner", "-nostats", "-i", str(video_path),
        "-af", "ebur128=peak=true", "-f", "null", "-",
    ])
    if res.returncode != 0:
        raise VideoVerifyError(f"ebur128 falhou: {res.stderr.strip()[:400]}")

    def _last(pattern: str) -> Optional[float]:
        found = re.findall(pattern, res.stderr)
        return float(found[-1]) if found else None

    return {
        "integrated_lufs": _last(r"\bI:\s+(-?[\d.]+)\s+LUFS"),
        "lra_lu": _last(r"\bLRA:\s+(-?[\d.]+)\s+LU"),
        "true_peak_dbtp": _last(r"\bPeak:\s+(-?[\d.]+)\s+dBFS"),
    }


def detect_black(video_path: str | Path, min_duration_s: float = 0.10) -> List[Dict[str, float]]:
    """Detecta trechos pretos nao intencionais via blackdetect."""
    res = _run([
        "ffmpeg", "-hide_banner", "-nostats", "-i", str(video_path),
        "-vf", f"blackdetect=d={min_duration_s:.3f}:pix_th=0.10",
        "-an", "-f", "null", "-",
    ])
    if res.returncode != 0:
        raise VideoVerifyError(f"blackdetect falhou: {res.stderr.strip()[:400]}")
    segments: List[Dict[str, float]] = []
    for m in re.finditer(
        r"black_start:([\d.]+)\s+black_end:([\d.]+)\s+black_duration:([\d.]+)",
        res.stderr,
    ):
        segments.append({
            "start": float(m.group(1)),
            "end": float(m.group(2)),
            "duration": float(m.group(3)),
        })
    return segments


# ---------------------------------------------------------------------------
# Medicoes de video (pixels)
# ---------------------------------------------------------------------------

_FRAME_SIZE = (160, 90)


def _extract_frame_rgb(video_path: str | Path, t: float, out_png: Path) -> List[Tuple[int, int, int]]:
    res = _run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-ss", f"{max(0.0, float(t)):.3f}", "-i", str(video_path),
        "-frames:v", "1", str(out_png),
    ])
    if res.returncode != 0 or not out_png.is_file():
        raise VideoVerifyError(f"nao foi possivel extrair frame em {t:.3f}s: {res.stderr.strip()[:300]}")

    from PIL import Image

    with Image.open(out_png) as im:
        small = im.convert("RGB").resize(_FRAME_SIZE)
        raw = (
            list(small.get_flattened_data())
            if hasattr(small, "get_flattened_data")
            else list(small.getdata())
        )
    if raw and isinstance(raw[0], (int, float)):
        flat = list(raw)
        return [
            (int(flat[i]), int(flat[i + 1]), int(flat[i + 2]))
            for i in range(0, len(flat) - 2, 3)
        ]
    return [(int(px[0]), int(px[1]), int(px[2])) for px in raw]


def _mean_abs_diff(a: Sequence[Tuple[int, int, int]], b: Sequence[Tuple[int, int, int]]) -> float:
    if not a or len(a) != len(b):
        return 0.0
    total = 0
    for pa, pb in zip(a, b):
        total += abs(pa[0] - pb[0]) + abs(pa[1] - pb[1]) + abs(pa[2] - pb[2])
    return total / (len(a) * 3.0)


def _outside_times(
    windows: Sequence[Dict[str, Any]],
    duration: float,
    *,
    n: int = 2,
    step: float = 0.25,
    margin: float = 0.05,
) -> List[float]:
    """Retorna ate `n` instantes fora de todas as janelas informadas."""
    spans = []
    for w in windows:
        try:
            s = float(w.get("start", 0.0))
            e = float(w.get("end", 0.0))
        except (TypeError, ValueError):
            continue
        spans.append((s - margin, e + margin))

    def _inside(t: float) -> bool:
        return any(a <= t <= b for a, b in spans)

    found: List[float] = []
    t = 0.05
    while t < duration - 0.05 and len(found) < n:
        if not _inside(t):
            if not found or abs(t - found[-1]) >= 0.30:
                found.append(round(t, 3))
        t += step
    return found


def _verify_visual_windows(
    video_path: Path,
    windows: Sequence[Dict[str, Any]],
    duration: float,
    work_dir: Path,
    *,
    min_visual_diff: float = 0.25,
    max_control_diff: float = 2.0,
) -> Tuple[List[Dict[str, Any]], List[str], List[str]]:
    results: List[Dict[str, Any]] = []
    problems: List[str] = []
    warnings: List[str] = []

    if not windows:
        return results, problems, warnings

    outside = _outside_times(windows, duration, n=2)
    if not outside:
        warnings.append("sem instante fora das janelas visuais para referencia")
        return results, problems, warnings

    ref_t = outside[0]
    ref_frame = _extract_frame_rgb(video_path, ref_t, work_dir / "_qa_ref.png")
    control_diff = 0.0
    if len(outside) > 1:
        ctrl_frame = _extract_frame_rgb(video_path, outside[1], work_dir / "_qa_control.png")
        control_diff = _mean_abs_diff(ctrl_frame, ref_frame)
        if control_diff > max_control_diff:
            warnings.append(
                f"movimento natural de camera fora das janelas visuais (diff={control_diff:.3f} > {max_control_diff})"
            )

    for idx, w in enumerate(windows):
        try:
            start = float(w.get("start", 0.0))
            end = float(w.get("end", 0.0))
        except (TypeError, ValueError):
            problems.append(f"janela visual invalida: {w}")
            continue
        mid = max(0.0, min(duration - 0.02, (start + end) / 2.0))
        frame = _extract_frame_rgb(video_path, mid, work_dir / f"_qa_in_{idx}.png")
        diff = _mean_abs_diff(frame, ref_frame)
        results.append({
            "layer": w.get("layer", "?"),
            "start": start,
            "end": end,
            "inside_time": round(mid, 3),
            "reference_time": ref_t,
            "inside_diff": round(diff, 4),
            "control_diff": round(control_diff, 4),
        })
        if diff < min_visual_diff:
            problems.append(
                f"{w.get('layer', '?')}: sem alteracao visual mensuravel na janela "
                f"[{start:.3f}, {end:.3f}] (diff={diff:.3f} < {min_visual_diff})"
            )
        elif control_diff <= max_control_diff and diff <= control_diff + 0.05:
            problems.append(
                f"{w.get('layer', '?')}: alteracao visual na janela nao se distingue "
                f"do fora (inside={diff:.3f}, control={control_diff:.3f})"
            )
    return results, problems, warnings


def _verify_audio_windows(
    video_path: Path,
    windows: Sequence[Dict[str, Any]],
    *,
    min_rms_delta_db: float = 1.0,
) -> Tuple[List[Dict[str, Any]], List[str], List[str]]:
    results: List[Dict[str, Any]] = []
    problems: List[str] = []
    warnings: List[str] = []

    if not windows:
        return results, problems, warnings

    duration_fmt = float(probe_media(video_path).get("format", {}).get("duration", 0.0) or 0.0)
    outside = _outside_times(windows, max(0.5, duration_fmt), n=1)
    if not outside:
        warnings.append("sem instante fora das janelas L6 para referencia de audio")
        return results, problems, warnings

    ref_t = outside[0]
    outside_stats = measure_astats(video_path, start=ref_t, duration=0.25)
    outside_rms = outside_stats.get("rms_db")
    if outside_rms is None:
        problems.append("nao foi possivel medir RMS fora das janelas L6")
        return results, problems, warnings

    for w in windows:
        try:
            start = float(w.get("start", 0.0))
            end = float(w.get("end", 0.0))
        except (TypeError, ValueError):
            problems.append(f"janela de audio invalida: {w}")
            continue
        span = max(0.05, min(0.25, end - start))
        stats = measure_astats(video_path, start=start, duration=span)
        inside_rms = stats.get("rms_db")
        delta = None if inside_rms is None else inside_rms - outside_rms
        results.append({
            "layer": w.get("layer", "?"),
            "start": start,
            "end": end,
            "inside_rms_db": inside_rms,
            "outside_rms_db": outside_rms,
            "rms_delta_db": None if delta is None else round(delta, 3),
            "reference_time": ref_t,
        })
        if inside_rms is None:
            problems.append(f"{w.get('layer', '?')}: sem RMS mensuravel na janela L6")
        elif delta is not None and delta < min_rms_delta_db:
            problems.append(
                f"{w.get('layer', '?')}: SFX nao detectavel na janela "
                f"[{start:.3f}, {end:.3f}] (delta RMS={delta:.2f} dB < {min_rms_delta_db} dB)"
            )
    return results, problems, warnings


# ---------------------------------------------------------------------------
# API principal
# ---------------------------------------------------------------------------


def verify_video_av(
    video_path: str | Path,
    expected_duration_s: Optional[float] = None,
    *,
    qa_windows: Optional[Sequence[Dict[str, Any]]] = None,
    tolerance_s: float = DURATION_TOLERANCE_S,
    expected_width: Optional[int] = None,
    expected_height: Optional[int] = None,
    expected_lufs: float = DEFAULT_TARGET_LUFS,
    lufs_tolerance: float = DEFAULT_LUFS_TOLERANCE,
    max_true_peak_db: float = DEFAULT_MAX_TRUE_PEAK_DBTP,
    require_audio: bool = True,
    check_black: bool = True,
    check_loudness: bool = True,
    check_windows: bool = True,
    filtergraph_text: Optional[str] = None,
    min_visual_diff: float = 0.25,
    max_control_diff: float = 2.0,
    min_audio_rms_delta_db: float = 1.0,
    work_dir: Optional[str | Path] = None,
) -> Dict[str, Any]:
    """Verifica o master audiovisual e retorna relatorio estruturado."""
    vp = Path(video_path)
    problems: List[str] = []
    warnings: List[str] = []

    if not vp.is_file() or vp.stat().st_size <= 0:
        return {
            "ok": False,
            "problems": ["arquivo inexistente ou vazio"],
            "warnings": [],
            "path": str(vp),
            "duration": 0.0,
            "video": None,
            "audio": None,
        }

    info = probe_media(vp)
    streams = info.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)

    duration = 0.0
    try:
        duration = float(info.get("format", {}).get("duration", 0.0) or 0.0)
    except (TypeError, ValueError):
        problems.append("duracao do container invalida")

    # --- Video ---
    if video is None:
        problems.append("sem stream de video")
    else:
        if video.get("codec_name") != "h264":
            problems.append(f"codec de video {video.get('codec_name')} (esperado h264)")
        if video.get("pix_fmt") != "yuv420p":
            problems.append(f"pix_fmt {video.get('pix_fmt')} (esperado yuv420p)")
        if expected_width is not None and expected_height is not None:
            if (video.get("width"), video.get("height")) != (expected_width, expected_height):
                problems.append(
                    f"resolucao {video.get('width')}x{video.get('height')} "
                    f"(esperado {expected_width}x{expected_height})"
                )
        elif (video.get("width"), video.get("height")) not in ((TARGET_W, TARGET_H), (TARGET_H, TARGET_W)):
            problems.append(
                f"resolucao {video.get('width')}x{video.get('height')} "
                f"(esperado {TARGET_W}x{TARGET_H} ou {TARGET_H}x{TARGET_W})"
            )
        fps = _parse_rate(video.get("avg_frame_rate")) or _parse_rate(video.get("r_frame_rate"))
        if fps is None or abs(fps - TARGET_FPS) > FPS_TOLERANCE:
            problems.append(f"fps {video.get('avg_frame_rate') or video.get('r_frame_rate')} (esperado {TARGET_FPS})")
        sar = _normalize_sar(video.get("sample_aspect_ratio"))
        if sar is None:
            warnings.append(f"SAR desconhecido: {video.get('sample_aspect_ratio')!r}")
        elif abs(sar - 1.0) > 1e-6:
            problems.append(f"SAR {video.get('sample_aspect_ratio')} (esperado 1:1)")

    if expected_duration_s is not None and abs(duration - float(expected_duration_s)) > tolerance_s:
        problems.append(
            f"duracao {duration:.3f}s (esperado {float(expected_duration_s):.3f}s "
            f"+-{tolerance_s}s)"
        )

    # --- Audio ---
    if audio is None:
        if require_audio:
            problems.append("sem stream de audio")
    else:
        if audio.get("codec_name") != "aac":
            problems.append(f"codec de audio {audio.get('codec_name')} (esperado aac)")
        try:
            sr = int(audio.get("sample_rate", 0))
        except (TypeError, ValueError):
            sr = 0
        if sr != AUDIO_SR:
            problems.append(f"sample_rate {audio.get('sample_rate')} (esperado {AUDIO_SR})")
        try:
            ch = int(audio.get("channels", 0))
        except (TypeError, ValueError):
            ch = 0
        if ch != AUDIO_CHANNELS:
            problems.append(f"canais {audio.get('channels')} (esperado {AUDIO_CHANNELS})")

    loudnorm_count = None
    if filtergraph_text is not None:
        loudnorm_count = count_loudnorm(filtergraph_text)
        if loudnorm_count != 1:
            problems.append(f"loudnorm ocorrencias={loudnorm_count} (esperado exatamente 1)")

    # --- blackdetect ---
    black_segments: List[Dict[str, float]] = []
    if check_black and video is not None:
        try:
            black_segments = detect_black(vp)
        except VideoVerifyError as exc:
            warnings.append(str(exc))
        if black_segments:
            problems.append(
                f"{len(black_segments)} trecho(s) preto(s) nao intencional(is) detectado(s)"
            )

    # --- Loudness / clipping / silencio ---
    loudness: Dict[str, Optional[float]] = {}
    astats_full: Dict[str, Optional[float]] = {}
    if check_loudness and audio is not None:
        try:
            loudness = measure_ebur128(vp)
        except VideoVerifyError as exc:
            problems.append(str(exc))
        if loudness:
            i_lufs = loudness.get("integrated_lufs")
            if i_lufs is None:
                problems.append("nao foi possivel medir Integrated Loudness (ebur128)")
            elif abs(i_lufs - expected_lufs) > lufs_tolerance:
                problems.append(
                    f"Integrated Loudness {i_lufs:.2f} LUFS fora de "
                    f"{expected_lufs:+.1f}+-{lufs_tolerance} LU"
                )
            tp = loudness.get("true_peak_dbtp")
            if tp is None:
                problems.append("nao foi possivel medir True Peak (ebur128)")
            elif tp > max_true_peak_db:
                problems.append(f"True Peak {tp:.2f} dBTP > {max_true_peak_db} dBTP")
        try:
            astats_full = measure_astats(vp)
        except VideoVerifyError as exc:
            problems.append(str(exc))
        if astats_full:
            peak_db = astats_full.get("peak_db")
            if peak_db is not None and peak_db > CLIPPING_PEAK_DBFS:
                problems.append(f"pico {peak_db:.2f} dBFS indica clipping (>{CLIPPING_PEAK_DBFS})")
            rms_db = astats_full.get("rms_db")
            if rms_db is None:
                problems.append("nao foi possivel medir RMS do master")
            elif rms_db <= SILENCE_RMS_DBFS:
                problems.append(f"audio mudo (RMS {rms_db:.2f} dBFS <= {SILENCE_RMS_DBFS})")

    # --- Janelas QA ---
    visual_results: List[Dict[str, Any]] = []
    audio_results: List[Dict[str, Any]] = []
    if check_windows and qa_windows:
        visual_windows = [w for w in qa_windows if w.get("kind", "visual") == "visual"]
        audio_windows = [w for w in qa_windows if w.get("kind") == "audio"]
        tmp = Path(work_dir) if work_dir else Path(tempfile.mkdtemp(prefix="qa_frames_"))
        tmp.mkdir(parents=True, exist_ok=True)
        if visual_windows:
            visual_results, vp_problems, vp_warnings = _verify_visual_windows(
                vp, visual_windows, duration, tmp,
                min_visual_diff=min_visual_diff, max_control_diff=max_control_diff,
            )
            problems.extend(vp_problems)
            warnings.extend(vp_warnings)
        if audio_windows:
            audio_results, ap_problems, ap_warnings = _verify_audio_windows(
                vp, audio_windows, min_rms_delta_db=min_audio_rms_delta_db,
            )
            problems.extend(ap_problems)
            warnings.extend(ap_warnings)

    return {
        "ok": len(problems) == 0,
        "problems": problems,
        "warnings": warnings,
        "path": str(vp),
        "duration": duration,
        "video": video,
        "audio": audio,
        "loudness": loudness,
        "astats": astats_full,
        "black_segments": black_segments,
        "loudnorm_count": loudnorm_count,
        "visual_windows": visual_results,
        "audio_windows": audio_results,
    }


def verify_master_basic(
    video_path: str | Path,
    expected_duration_s: Optional[float] = None,
    tolerance_s: float = DURATION_TOLERANCE_S,
    expected_width: Optional[int] = None,
    expected_height: Optional[int] = None,
) -> Dict[str, Any]:
    """Verificacao rapida de container/streams/duracao (sem QA de loudness)."""
    return verify_video_av(
        video_path,
        expected_duration_s,
        tolerance_s=tolerance_s,
        expected_width=expected_width,
        expected_height=expected_height,
        check_black=False,
        check_loudness=False,
        check_windows=False,
    )
