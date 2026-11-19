# -*- coding: utf-8 -*-
"""core/shorts_renderer.py

Derivados verticais 9:16 (Shorts) a partir do master 16:9 aprovado.

Nenhuma descoberta automatica de Shorts, selecao por viralizacao ou
inteligencia editorial de recortes: os clips sao fornecidos explicitamente pelo
chamador. O master 16:9 nunca e modificado (Delta-Hash = 0).
"""

from __future__ import annotations

import json
import math
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_REPO_ROOT = Path(__file__).resolve().parent.parent

try:
    from .workspace import (  # noqa: F401
        WorkspaceLoader,
        RENDER_DEFAULTS_9X16,
        SAFE_ZONES_9X16,
        init_workspace,
        load_brand_profile,
    )
    from .pipeline import (  # noqa: F401
        MasterApprovalError,
        approve_master_16x9,
        sha256_file,
        verify_master_16x9_approval,
    )
    from .video_verify import probe_media  # noqa: F401
    from .semantic_planner import load_user_brief  # noqa: F401
    from .transcript_review import resolve_editorial_transcript, TranscriptReviewError  # noqa: F401
    from .ingest import verify_source_integrity, IngestError  # noqa: F401
    from .edl_renderer import (  # noqa: F401
        build_fullscreen_motion_sfx_events,
        render_fullscreen_motion_scene,
        _resolve_fullscreen_motion_html,
        _wav_duration,
    )
    from .brand_bumpers import (  # noqa: F401
        resolve_brand_asset_dirs,
        resolve_brand_bumper,
        ensure_bumper_mp4,
        apply_intro_outro_to_video,
    )
except ImportError:  # execucao direta como script
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from core.workspace import (  # type: ignore
        WorkspaceLoader,
        RENDER_DEFAULTS_9X16,
        SAFE_ZONES_9X16,
        init_workspace,
        load_brand_profile,
    )
    from core.pipeline import (  # type: ignore
        MasterApprovalError,
        approve_master_16x9,
        sha256_file,
        verify_master_16x9_approval,
    )
    from core.video_verify import probe_media  # type: ignore
    from core.semantic_planner import load_user_brief  # type: ignore
    from core.transcript_review import resolve_editorial_transcript, TranscriptReviewError  # type: ignore
    from core.ingest import verify_source_integrity, IngestError  # type: ignore
    from core.edl_renderer import (  # type: ignore
        build_fullscreen_motion_sfx_events,
        render_fullscreen_motion_scene,
        _resolve_fullscreen_motion_html,
        _wav_duration,
    )
    from core.brand_bumpers import (  # type: ignore
        resolve_brand_asset_dirs,
        resolve_brand_bumper,
        ensure_bumper_mp4,
        apply_intro_outro_to_video,
    )


class ShortsRenderError(Exception):
    """Erro na geracao/aprovacao de derivados verticais 9:16 (Shorts)."""


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------


_SLUG_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def _iso_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def _validate_short_id(short_id: Any) -> str:
    if not isinstance(short_id, str) or not short_id:
        raise ShortsRenderError("short_id nao pode ser vazio.")
    if not _SLUG_RE.match(short_id):
        raise ShortsRenderError(
            f"short_id invalido '{short_id}': use apenas [a-z0-9]+(-[a-z0-9]+)*."
        )
    return short_id


def _validate_clips(clips: List[Dict[str, Any]], master_duration: float) -> None:
    if not isinstance(clips, list) or len(clips) == 0:
        raise ShortsRenderError("clips deve ser uma lista nao vazia.")
    for idx, clip in enumerate(clips):
        if not isinstance(clip, dict):
            raise ShortsRenderError(f"clips[{idx}] nao eh um objeto.")
        short_id = clip.get("short_id")
        start = clip.get("start")
        end = clip.get("end")
        _validate_short_id(short_id)
        if not isinstance(start, (int, float)) or isinstance(start, bool):
            raise ShortsRenderError(f"clips[{idx}].start invalido: {start!r}.")
        if not isinstance(end, (int, float)) or isinstance(end, bool):
            raise ShortsRenderError(f"clips[{idx}].end invalido: {end!r}.")
        start = float(start)
        end = float(end)
        if start < 0:
            raise ShortsRenderError(
                f"clips[{idx}].start negativo ({start:.3f}s) para '{short_id}'."
            )
        if end <= start:
            raise ShortsRenderError(
                f"clips[{idx}].end ({end:.3f}s) <= start ({start:.3f}s) para '{short_id}'."
            )
        if end > master_duration + 0.05:
            raise ShortsRenderError(
                f"clips[{idx}].end ({end:.3f}s) excede duracao do master "
                f"({master_duration:.3f}s) para '{short_id}'."
            )


def _run(cmd: List[str], *, timeout: float = 240.0) -> subprocess.CompletedProcess:
    return subprocess.run(
        list(cmd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )


def _probe_duration(path: Path) -> float:
    info = probe_media(path)
    try:
        return float(info.get("format", {}).get("duration", 0.0) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _stream_info(path: Path) -> Dict[str, Any]:
    info = probe_media(path)
    streams = info.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    return {"video": video, "audio": audio}


def _measure_peak_rms(path: Path) -> Dict[str, Optional[float]]:
    """Mede pico (dBFS) e RMS (dBFS) via filtro volumedetect."""
    res = _run(
        [
            "ffmpeg", "-v", "error", "-i", str(path),
            "-af", "volumedetect", "-f", "null", "-",
        ],
    )
    text = res.stderr or ""
    peak: Optional[float] = None
    rms: Optional[float] = None
    for line in text.splitlines():
        line = line.strip()
        if "max_volume:" in line:
            try:
                peak = float(line.split("max_volume:")[1].split("dB")[0].strip())
            except (ValueError, IndexError):
                pass
        elif "mean_volume:" in line:
            try:
                rms = float(line.split("mean_volume:")[1].split("dB")[0].strip())
            except (ValueError, IndexError):
                pass
    return {"peak": peak, "rms": rms}


def _qa_short(output_path: Path, expected_duration: float) -> Dict[str, Any]:
    """QA automatizado de um derivado 9:16.

    Verifica resolucao, FPS, SAR, codec/pix_fmt, audio, duracao, pico/RMS.
    Retorna dict com `ok`, `problems`, `warnings` e metricas.
    """
    problems: List[str] = []
    warnings: List[str] = []
    vp = Path(output_path)

    if not vp.is_file() or vp.stat().st_size <= 0:
        return {
            "ok": False,
            "problems": ["arquivo inexistente ou vazio"],
            "warnings": [],
            "duration": 0.0,
        }

    streams = _stream_info(vp)
    video = streams["video"]
    audio = streams["audio"]

    duration = _probe_duration(vp)

    # Video
    if video is None:
        problems.append("sem stream de video")
    else:
        if video.get("codec_name") != "h264":
            problems.append(f"codec de video {video.get('codec_name')} (esperado h264)")
        if video.get("pix_fmt") != "yuv420p":
            problems.append(f"pix_fmt {video.get('pix_fmt')} (esperado yuv420p)")
        if (video.get("width"), video.get("height")) != (1080, 1920):
            problems.append(
                f"resolucao {video.get('width')}x{video.get('height')} "
                f"(esperado 1080x1920)"
            )
        from core.video_verify import _parse_rate  # type: ignore

        fps = _parse_rate(video.get("avg_frame_rate")) or _parse_rate(
            video.get("r_frame_rate")
        )
        if fps is None or abs(fps - 30.0) > 0.05:
            problems.append(
                f"fps {video.get('avg_frame_rate') or video.get('r_frame_rate')} "
                f"(esperado 30)"
            )
        sar = video.get("sample_aspect_ratio")
        if sar not in ("1:1", None):
            problems.append(f"SAR {sar} (esperado 1:1)")

    # Audio
    if audio is None:
        problems.append("sem stream de audio")
    else:
        if audio.get("codec_name") != "aac":
            problems.append(f"codec de audio {audio.get('codec_name')} (esperado aac)")
        try:
            sr = int(audio.get("sample_rate", 0))
        except (TypeError, ValueError):
            sr = 0
        if sr != 48000:
            problems.append(f"sample_rate {sr} (esperado 48000)")
        try:
            ch = int(audio.get("channels", 0))
        except (TypeError, ValueError):
            ch = 0
        if ch != 2:
            problems.append(f"canais {ch} (esperado 2)")

    # Duracao
    if abs(duration - expected_duration) > 0.10:
        problems.append(
            f"duracao {duration:.3f}s (esperado {expected_duration:.3f}s +-0.10s)"
        )

    # Pico / RMS
    levels = _measure_peak_rms(vp)
    peak = levels["peak"]
    rms = levels["rms"]
    if peak is not None and peak > -0.1:
        problems.append(f"pico {peak:.2f} dBFS (maximo -0.1 dBFS)")
    if rms is not None and rms <= -60.0:
        problems.append(f"RMS {rms:.2f} dBFS (minimo -60 dBFS)")

    return {
        "ok": len(problems) == 0,
        "problems": problems,
        "warnings": warnings,
        "duration": duration,
        "peak_db": peak,
        "rms_db": rms,
    }


def _shorts_dir(root: Path, marca_id: str, episodio_id: str) -> Path:
    loader = WorkspaceLoader(root)
    loader.load_workspace()
    return loader.resolve_episodio_asset(
        marca_id, episodio_id, "workspace/renders/shorts"
    )


def _manifest_path(shorts_dir: Path) -> Path:
    return shorts_dir / "shorts_manifest.json"


def _load_manifest(shorts_dir: Path) -> Dict[str, Any]:
    mp = _manifest_path(shorts_dir)
    if not mp.is_file():
        return {}
    try:
        return json.loads(mp.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _save_manifest(shorts_dir: Path, manifest: Dict[str, Any]) -> None:
    shorts_dir.mkdir(parents=True, exist_ok=True)
    _manifest_path(shorts_dir).write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def _update_project_shorts(
    root: Path,
    loader: WorkspaceLoader,
    marca_id: str,
    episodio_id: str,
    shorts_entries: Dict[str, Any],
) -> None:
    """Atualiza project.json (derivatives.shorts_9x16) com os derivados."""
    projeto = loader.load_project(marca_id, episodio_id)
    projeto.setdefault("derivatives", {})
    projeto["derivatives"]["shorts_9x16"] = shorts_entries
    projeto["updated_at"] = _iso_now()
    projeto_path = loader.project_file(marca_id, episodio_id)
    with open(projeto_path, "w", encoding="utf-8") as f:
        json.dump(projeto, f, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Curadoria OpusClip (suggest_shorts_opusclip - Portao Humano 2)
# ---------------------------------------------------------------------------


def _fmt_mmss(sec: float) -> str:
    sec_i = max(0, int(round(sec)))
    return f"{sec_i // 60:02d}:{sec_i % 60:02d}"


def _score_narrative_arc(
    text: str,
    dur: float,
    has_hook: bool = False,
    ideal_min: float = 15.0,
    ideal_max: float = 55.0,
) -> Tuple[float, str]:
    """Pontua um arco narrativo (0 a 10) e gera justificativa editorial."""
    words = [w for w in text.strip().split() if w]
    score = 6.2
    reasons: List[str] = []

    if has_hook:
        score += 1.6
        reasons.append("abre com gancho ou virada marcada no roteiro")

    if "?" in text or any(k in text.lower() for k in ("como", "por que", "erro", "segredo", "nunca", "sempre", "resultado", "lucro", "produ")):
        score += 0.9
        reasons.append("contem pergunta, contraste ou promessa direta de valor")

    if any(ch.isdigit() for ch in text):
        score += 0.6
        reasons.append("apresenta dado numerico concreto")

    if ideal_min <= dur <= ideal_max:
        score += 0.5
        reasons.append("duracao ideal para retencao em Reels/Shorts")
    elif dur >= 2.0:
        score += 0.2

    if len(words) >= 12:
        score += 0.4

    score = round(min(9.9, max(5.0, score)), 1)
    just = "; ".join(reasons).capitalize() + "." if reasons else "Bloco narrativo completo com inicio, desenvolvimento e fechamento."
    return score, just


def _map_raw_interval_to_master(
    raw_start: float,
    raw_end: float,
    edl: Optional[Dict[str, Any]],
    max_duration: float,
) -> Tuple[float, float]:
    """Converte timestamps raw para o eixo montado do Master quando houver EDL."""
    if not edl or not edl.get("timeline_events"):
        s = max(0.0, min(max_duration - 0.5, raw_start))
        e = max(s + 0.5, min(max_duration, raw_end))
        return round(s, 3), round(e, 3)

    events = edl["timeline_events"]
    out_cursor = 0.0
    mapped_starts: List[float] = []
    mapped_ends: List[float] = []
    for ev in events:
        ev_in = float(ev.get("raw_in", ev.get("src_in", 0.0)))
        ev_out = float(ev.get("raw_out", ev.get("src_out", ev_in)))
        ev_dur = max(0.0, ev_out - ev_in)
        if ev_out >= raw_start and ev_in <= raw_end:
            local_s = max(0.0, raw_start - ev_in)
            local_e = min(ev_dur, raw_end - ev_in)
            mapped_starts.append(out_cursor + local_s)
            mapped_ends.append(out_cursor + local_e)
        out_cursor += ev_dur

    if mapped_starts and mapped_ends:
        s = max(0.0, min(max_duration - 0.5, min(mapped_starts)))
        e = max(s + 0.5, min(max_duration, max(mapped_ends)))
        return round(s, 3), round(e, 3)

    s = max(0.0, min(max_duration - 0.5, raw_start))
    e = max(s + 0.5, min(max_duration, raw_end))
    return round(s, 3), round(e, 3)


def suggest_shorts_opusclip(
    workspace_root: str | Path,
    marca_id: str,
    episodio_id: str,
    *,
    count: Optional[int] = None,
    modo: Optional[str] = None,
) -> Dict[str, Any]:
    """Analisa arcos narrativos e gera briefing estilo OpusClip (Portao Humano 2).

    Funciona tanto apos a entrega do Master (`modo="completo"`) quanto direto
    sobre o video original em `brutos/` (`modo="so_cortes"`).
    Grava `workspace/briefing/shorts_plan.json` e `workspace/briefing/shorts_briefing.md`
    e PARA aguardando aprovacao humana antes de renderizar qualquer corte.
    """
    root = Path(workspace_root).resolve()
    loader = WorkspaceLoader(root)
    loader.load_workspace()

    projeto = loader.load_project(marca_id, episodio_id)
    fonte_dir = loader.resolve_episodio_asset(marca_id, episodio_id, "workspace/fonte")
    briefing_dir = loader.resolve_episodio_asset(marca_id, episodio_id, "workspace/briefing")
    briefing_dir.mkdir(parents=True, exist_ok=True)

    user_brief = load_user_brief(briefing_dir)
    effective_modo = (modo or user_brief.get("modo") or "completo").strip().lower()

    master_path = Path(
        loader.resolve_episodio_asset(
            marca_id, episodio_id, "workspace/renders/master_16x9.mp4"
        )
    ).resolve()

    source_kind = "master"
    source_path: Optional[Path] = None
    if effective_modo == "so_cortes" or not master_path.is_file():
        if effective_modo != "so_cortes" and not master_path.is_file():
            raise ShortsRenderError(
                f"Master nao encontrado em {master_path}. Renderize o Master antes ou use modo 'so_cortes'."
            )
        sources = projeto.get("sources", []) or []
        if not sources or not sources[0].get("path"):
            raise ShortsRenderError(
                f"Nenhuma fonte em brutos/ registrada para {marca_id}/{episodio_id}."
            )
        source_path = Path(sources[0]["path"]).resolve()
        if not source_path.is_file():
            raise ShortsRenderError(f"Arquivo bruto nao encontrado: {source_path}")
        if sources[0].get("sha256"):
            try:
                verify_source_integrity(source_path, sources[0]["sha256"], source_path.name)
            except IngestError as exc:
                raise ShortsRenderError(str(exc)) from exc
        source_kind = "brutos"
    else:
        source_path = master_path
        source_kind = "master"

    source_duration = _probe_duration(source_path)
    if source_duration <= 0.5:
        raise ShortsRenderError(f"Duracao da midia fonte insuficiente ({source_duration:.2f}s).")

    # Quantidade de cortes
    target_count = count if count is not None else user_brief.get("qtd_cortes_desejada")
    if target_count is None:
        if source_duration >= 600:
            target_count = min(7, max(3, int(round(source_duration / 180.0))))
        elif source_duration >= 120:
            target_count = 3
        else:
            target_count = 2 if source_duration >= 6.0 else 1
    target_count = max(1, int(target_count))

    # Carrega transcricao / alignment / semantic_plan / edl
    try:
        editorial = resolve_editorial_transcript(fonte_dir)
        segments = editorial.get("segments", [])
    except TranscriptReviewError:
        segments = []

    alignment_path = fonte_dir / "alignment.json"
    units: List[Dict[str, Any]] = []
    if alignment_path.is_file():
        try:
            al_data = json.loads(alignment_path.read_text(encoding="utf-8", errors="replace"))
            units = al_data.get("editorial_units", []) or []
        except json.JSONDecodeError:
            units = []

    semantic_plan: Optional[Dict[str, Any]] = None
    sem_path = briefing_dir / "semantic_plan.json"
    if sem_path.is_file():
        try:
            semantic_plan = json.loads(sem_path.read_text(encoding="utf-8", errors="replace"))
        except json.JSONDecodeError:
            semantic_plan = None

    edl_data: Optional[Dict[str, Any]] = None
    edl_path = briefing_dir / "edl_longo.json"
    if source_kind == "master" and edl_path.is_file():
        try:
            edl_data = json.loads(edl_path.read_text(encoding="utf-8", errors="replace"))
        except json.JSONDecodeError:
            edl_data = None

    # Constroi arcos candidatos
    raw_candidates: List[Dict[str, Any]] = []
    if semantic_plan:
        for gv in semantic_plan.get("ganchos_e_viradas", []):
            raw_candidates.append({
                "raw_start": float(gv.get("raw_start", 0.0)),
                "raw_end": float(gv.get("raw_end", 0.0)),
                "text": str(gv.get("descricao") or ""),
                "titulo": str(gv.get("descricao") or "Momento de Impacto")[:60],
                "has_hook": True,
            })
        for arg in semantic_plan.get("argumentos", []):
            raw_candidates.append({
                "raw_start": float(arg.get("raw_start", 0.0)),
                "raw_end": float(arg.get("raw_end", 0.0)),
                "text": str(arg.get("resumo") or ""),
                "titulo": str(arg.get("resumo") or "Argumento Central")[:60],
                "has_hook": arg.get("tipo") in ("gancho", "virada", "tese"),
            })
        for top in semantic_plan.get("topicos", []):
            raw_candidates.append({
                "raw_start": float(top.get("raw_start", 0.0)),
                "raw_end": float(top.get("raw_end", 0.0)),
                "text": str(top.get("justificativa") or top.get("titulo") or ""),
                "titulo": str(top.get("titulo") or "Destaque do Episodio")[:60],
                "has_hook": False,
            })

    # Unidades de alinhamento / segmentos para completar arcos
    blocks = units if units else [
        {
            "raw_start": float(s.get("start", 0.0)),
            "raw_end": float(s.get("end", 0.0)),
            "text": str(s.get("text", "")),
        }
        for s in segments
    ]
    if blocks:
        ideal_win = min(45.0, max(2.0, (source_duration * 0.85) / target_count))
        cur_start = float(blocks[0].get("raw_start", 0.0))
        cur_end = float(blocks[0].get("raw_end", cur_start + 1.0))
        cur_texts: List[str] = [str(blocks[0].get("text", "")).strip()]
        for blk in blocks[1:]:
            b_start = float(blk.get("raw_start", cur_end))
            b_end = float(blk.get("raw_end", b_start + 1.0))
            b_txt = str(blk.get("text", "")).strip()
            if (b_end - cur_start) <= ideal_win or (cur_end - cur_start) < max(1.5, ideal_win * 0.5):
                cur_end = max(cur_end, b_end)
                if b_txt:
                    cur_texts.append(b_txt)
            else:
                raw_candidates.append({
                    "raw_start": cur_start,
                    "raw_end": cur_end,
                    "text": " ".join(cur_texts),
                    "titulo": "",
                    "has_hook": len(raw_candidates) == 0,
                })
                cur_start = b_start
                cur_end = b_end
                cur_texts = [b_txt] if b_txt else []
        raw_candidates.append({
            "raw_start": cur_start,
            "raw_end": cur_end,
            "text": " ".join(cur_texts),
            "titulo": "",
            "has_hook": False,
        })

    # Converte candidatos para o eixo da fonte (master ou bruto) e pontua
    scored: List[Dict[str, Any]] = []
    for cand in raw_candidates:
        if source_kind == "master":
            s_out, e_out = _map_raw_interval_to_master(
                cand["raw_start"], cand["raw_end"], edl_data, source_duration
            )
        else:
            s_out = max(0.0, min(source_duration - 0.5, cand["raw_start"]))
            e_out = max(s_out + 0.5, min(source_duration, cand["raw_end"]))
        dur = round(e_out - s_out, 3)
        if dur < 1.0:
            continue
        # Limita corte individual a no maximo 60s (Shorts/Reels)
        if dur > 58.0:
            e_out = round(s_out + 55.0, 3)
            dur = round(e_out - s_out, 3)
        txt = cand.get("text", "").strip()
        if not txt and segments:
            txt = " ".join(
                str(seg.get("text", "")).strip()
                for seg in segments
                if float(seg.get("end", 0.0)) >= cand["raw_start"]
                and float(seg.get("start", 0.0)) <= cand["raw_end"]
            ).strip()
        nota, just = _score_narrative_arc(txt, dur, has_hook=bool(cand.get("has_hook")))
        words_txt = [w for w in txt.split() if w]
        hook = " ".join(words_txt[:10]) + ("..." if len(words_txt) > 10 else "")
        titulo = cand.get("titulo") or (" ".join(words_txt[:6]).strip(".,;:!?") or f"Corte de Destaque")
        scored.append({
            "start": round(s_out, 3),
            "end": round(e_out, 3),
            "duracao_s": dur,
            "nota_potencial": nota,
            "justificativa_editorial": just,
            "gancho_abertura": hook or "(Abertura visual imediata)",
            "titulo": titulo[:72],
        })

    # Seleciona top `target_count` sem sobreposicao excessiva; fallback por fatiamento se faltar
    scored.sort(key=lambda c: (-c["nota_potencial"], c["start"]))
    selected: List[Dict[str, Any]] = []
    for cand in scored:
        if len(selected) >= target_count:
            break
        overlaps = any(
            min(cand["end"], sel["end"]) - max(cand["start"], sel["start"]) > 0.35
            for sel in selected
        )
        if not overlaps:
            selected.append(cand)

    if len(selected) < target_count:
        slice_dur = max(1.5, min(55.0, source_duration / target_count))
        for idx in range(target_count):
            if len(selected) >= target_count:
                break
            s_i = round(idx * slice_dur, 3)
            e_i = round(min(source_duration, s_i + max(1.5, slice_dur - 0.15)), 3)
            if e_i - s_i < 1.0:
                continue
            if any(min(e_i, sel["end"]) - max(s_i, sel["start"]) > 0.35 for sel in selected):
                continue
            seg_txt = " ".join(
                str(seg.get("text", "")).strip()
                for seg in segments
                if float(seg.get("end", 0.0)) >= s_i and float(seg.get("start", 0.0)) <= e_i
            ).strip()
            nota, just = _score_narrative_arc(seg_txt, e_i - s_i, has_hook=(idx == 0))
            words_txt = [w for w in seg_txt.split() if w]
            selected.append({
                "start": s_i,
                "end": e_i,
                "duracao_s": round(e_i - s_i, 3),
                "nota_potencial": nota,
                "justificativa_editorial": just,
                "gancho_abertura": (" ".join(words_txt[:10]) or f"Trecho {idx + 1}"),
                "titulo": (" ".join(words_txt[:6]).strip(".,;:!?") or f"Corte {idx + 1}")[:72],
            })

    selected.sort(key=lambda c: c["start"])
    suggestions: List[Dict[str, Any]] = []
    for idx, item in enumerate(selected, start=1):
        sid = f"corte-{idx:02d}"
        suggestions.append({
            "short_id": sid,
            "titulo": item["titulo"],
            "nota_potencial": item["nota_potencial"],
            "justificativa_editorial": item["justificativa_editorial"],
            "gancho_abertura": item["gancho_abertura"],
            "start": item["start"],
            "end": item["end"],
            "duracao_s": item["duracao_s"],
            "minutagem": f"{_fmt_mmss(item['start'])} - {_fmt_mmss(item['end'])} ({item['duracao_s']:.1f}s)",
            "approved": False,
        })

    plan_payload: Dict[str, Any] = {
        "schema_version": "1.0.0",
        "generated_at": _iso_now(),
        "marca_id": marca_id,
        "episodio_id": episodio_id,
        "modo": effective_modo,
        "source_kind": source_kind,
        "source_path": str(source_path),
        "source_duration_seconds": round(source_duration, 3),
        "requested_count": target_count,
        "requires_human_approval": True,
        "suggestions": suggestions,
    }
    shorts_plan_path = briefing_dir / "shorts_plan.json"
    shorts_plan_path.write_text(
        json.dumps(plan_payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    md_lines: List[str] = [
        f"# BRIEFING DE CORTES VIRAIS (OPUSCLIP) — {marca_id} / {episodio_id}",
        "",
        f"**Modo:** {effective_modo} | **Fonte:** {source_kind} ({source_duration:.1f}s)",
        f"**Cortes Sugeridos:** {len(suggestions)} (Portao Humano 2 — aguardando aprovacao)",
        "",
    ]
    for s in suggestions:
        md_lines.extend([
            f"## {s['short_id']} — {s['titulo']}",
            f"- **Nota de Potencial:** {s['nota_potencial']:.1f}/10",
            f"- **Minutagem Exata:** {s['minutagem']} (`{s['start']:.3f}s` -> `{s['end']:.3f}s`)",
            f"- **Gancho (Hook) de Abertura:** \"{s['gancho_abertura']}\"",
            f"- **Justificativa Editorial:** {s['justificativa_editorial']}",
            "",
        ])
    md_lines.append("⚠️ **PARADA OBRIGATORIA (Portao Humano 2):** aprove os cortes desejados antes de rodar `render-shorts`.")

    shorts_briefing_path = briefing_dir / "shorts_briefing.md"
    shorts_briefing_path.write_text("\n".join(md_lines), encoding="utf-8")

    return {
        "ok": True,
        "modo": effective_modo,
        "source_kind": source_kind,
        "source_path": str(source_path),
        "source_duration_seconds": round(source_duration, 3),
        "count": len(suggestions),
        "shorts_plan_path": str(shorts_plan_path),
        "shorts_briefing_path": str(shorts_briefing_path),
        "suggestions": suggestions,
        "requires_human_approval": True,
        "stopped_at_gate": True,
    }


def _load_ttf(candidates: Tuple[str, ...], size: int):
    from PIL import ImageFont

    for cand in candidates:
        try:
            return ImageFont.truetype(cand, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _wrap_text_lines(draw: Any, text: str, font: Any, max_width: int) -> List[str]:
    words = [w for w in str(text or "").split() if w]
    if not words:
        return []
    lines: List[str] = []
    cur = words[0]
    for w in words[1:]:
        cand = f"{cur} {w}"
        if draw.textlength(cand, font=font) <= max_width:
            cur = cand
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    return lines


def _calc_item_anim(t_rel: float, t_appear: float, dur: float = 0.35, slide_dx: int = -25, slide_dy: int = 0) -> Tuple[float, int, int]:
    if t_rel < t_appear:
        return 0.0, slide_dx, slide_dy
    p = min(1.0, (t_rel - t_appear) / max(0.01, dur))
    ease = 1.0 - (1.0 - p) ** 3
    return ease, int(slide_dx * (1.0 - ease)), int(slide_dy * (1.0 - ease))


def _resolve_branding_assets(
    workspace_root: Optional[Path] = None,
    marca_id: Optional[str] = None,
    brand_profile: Optional[Dict[str, Any]] = None,
) -> Tuple[Path, Path]:
    """Resolve diretorios de branding e sons respeitando isolamento multi-marca."""
    fallback_sons = _REPO_ROOT / "projetos" / "dr-gestao" / "branding" / "sons"
    asset_dirs = resolve_brand_asset_dirs(
        workspace_root, marca_id, brand_profile=brand_profile, repo_root=_REPO_ROOT
    )
    branding_dir = asset_dirs.get("primary_branding_dir") or (
        (_REPO_ROOT / "projetos" / str(marca_id) / "branding")
        if marca_id
        else (_REPO_ROOT / "projetos" / "dr-gestao" / "branding")
    )
    sons_dirs = [d for d in asset_dirs.get("sons_dirs", []) if d.is_dir() and any(d.glob("*.wav"))]
    sons_dir = sons_dirs[0] if sons_dirs else fallback_sons
    return Path(branding_dir), Path(sons_dir)


def _norm_hook_token(word: str) -> str:
    import unicodedata

    nfd = unicodedata.normalize("NFD", str(word or "").strip().lower())
    clean = "".join(ch for ch in nfd if unicodedata.category(ch) != "Mn")
    return re.sub(r"[^a-z0-9]", "", clean)


def sanitize_short_start_and_words(
    t_ini: float,
    t_fim: float,
    todas_palavras: List[Dict[str, Any]],
    *,
    hook_text: Optional[str] = None,
    max_residual_window_s: float = 0.45,
) -> Tuple[float, List[Dict[str, Any]], Dict[str, Any]]:
    """Remove residuos de frase anterior na abertura de cortes 9:16.

    Garante que o corte comece na frase-gancho escolhida, descartando restos
    de palavras da frase anterior (antes de t_ini ou dentro dos primeiros ~0.4s)
    e evitando vazamento da primeira palavra da frase seguinte no fim do corte.
    """
    t0 = float(t_ini)
    t1 = float(t_fim)
    sorted_words = sorted(
        [p for p in (todas_palavras or []) if str(p.get("w") or "").strip()],
        key=lambda p: (float(p.get("t", 0.0)), float(p.get("f", 0.0))),
    )
    candidates = [
        p
        for p in sorted_words
        if float(p.get("f", 0.0)) > t0 + 0.005 and float(p.get("t", 0.0)) < t1 - 0.02
    ]

    discarded: List[Dict[str, Any]] = []
    t_ini_clean = t0

    # 1) Descarta palavra iniciada antes do corte (rabo da frase anterior)
    if len(candidates) >= 2:
        w0 = candidates[0]
        w0_t = float(w0.get("t", 0.0))
        w0_f = float(w0.get("f", 0.0))
        w1_t = float(candidates[1].get("t", 0.0))
        if w0_t < t0 - 0.03 and (w0_f - t0) <= max_residual_window_s and w1_t <= t1 - 0.35:
            discarded.append(w0)
            candidates = candidates[1:]
            t_ini_clean = max(t_ini_clean, w0_f, w1_t - 0.06)

    # 2) Descarta palavra isolada terminal de frase anterior nos primeiros 0.45s
    while len(candidates) >= 2:
        w0 = candidates[0]
        w0_txt = str(w0.get("w") or "").strip()
        w0_f = float(w0.get("f", 0.0))
        w1_t = float(candidates[1].get("t", 0.0))
        if not w0_txt.endswith((".", "!", "?")) or (w0_f - t0) > max_residual_window_s or w1_t > t1 - 0.35:
            break
        hook_first = ""
        if hook_text:
            parts = [tok for tok in re.split(r"\s+", str(hook_text).strip()) if tok]
            if parts:
                hook_first = _norm_hook_token(parts[0])
        if hook_first and _norm_hook_token(w0_txt) == hook_first:
            break
        discarded.append(w0)
        candidates = candidates[1:]
        t_ini_clean = max(t_ini_clean, w0_f, w1_t - 0.06)

    # 3) Se o texto do gancho foi informado, alinha se houver residuo inicial < 0.60s
    if hook_text and len(candidates) >= 2:
        parts = [tok for tok in re.split(r"\s+", str(hook_text).strip()) if tok]
        hook_first = _norm_hook_token(parts[0]) if parts else ""
        if hook_first and _norm_hook_token(str(candidates[0].get("w") or "")) != hook_first:
            for idx_k in range(1, len(candidates)):
                wk = candidates[idx_k]
                wk_t = float(wk.get("t", 0.0))
                if wk_t - t_ini_clean > 0.60:
                    break
                if _norm_hook_token(str(wk.get("w") or "")) == hook_first:
                    prev_f = float(candidates[idx_k - 1].get("f", wk_t))
                    discarded.extend(candidates[:idx_k])
                    candidates = candidates[idx_k:]
                    t_ini_clean = max(t_ini_clean, prev_f, wk_t - 0.06)
                    break

    t_ini_clean = round(min(max(t0, t_ini_clean), max(t0, t1 - 0.25)), 3)
    kept_words = [
        p
        for p in candidates
        if float(p.get("f", 0.0)) > t_ini_clean + 0.005 and float(p.get("t", 0.0)) < t1 - 0.02
    ]
    info = {
        "original_start": round(t0, 3),
        "sanitized_start": t_ini_clean,
        "trimmed_s": round(max(0.0, t_ini_clean - t0), 3),
        "discarded_leading": [str(p.get("w") or "") for p in discarded],
    }
    return t_ini_clean, kept_words, info


def _shift_relative_clip_events(clip: Dict[str, Any], shift_s: float, new_dur: float) -> Dict[str, Any]:
    """Desloca tempos relativos internos do corte se o inicio foi sanitizado."""
    if shift_s <= 0.001:
        return clip
    shifted = dict(clip)
    if clip.get("fullscreen_motions"):
        new_fs: List[Dict[str, Any]] = []
        for fs in clip["fullscreen_motions"]:
            if not isinstance(fs, dict):
                continue
            item = dict(fs)
            fs_in = float(item.get("t_ini", item.get("start_rel", 0.0)))
            fs_out = float(item.get("t_fim", item.get("end_rel", new_dur)))
            item["t_ini"] = round(max(0.0, fs_in - shift_s), 3)
            item["t_fim"] = round(min(new_dur, max(item["t_ini"], fs_out - shift_s)), 3)
            if item["t_fim"] - item["t_ini"] >= 0.25:
                new_fs.append(item)
        shifted["fullscreen_motions"] = new_fs
    if clip.get("cards"):
        new_cards: List[Dict[str, Any]] = []
        for c in clip["cards"]:
            if not isinstance(c, dict):
                continue
            item = dict(c)
            c_in = float(item.get("t_ini", 0.0))
            c_out = float(item.get("t_fim", new_dur))
            item["t_ini"] = round(max(0.0, c_in - shift_s), 3)
            item["t_fim"] = round(min(new_dur, max(item["t_ini"], c_out - shift_s)), 3)
            if item["t_fim"] - item["t_ini"] >= 0.25:
                new_cards.append(item)
        shifted["cards"] = new_cards
    return shifted


def _extract_short_fullscreen_motions(clip: Dict[str, Any], dur_aligned: float) -> List[Dict[str, Any]]:
    """Normaliza definicoes de cenas `fullscreen_motion` (9:16 ou split_top) de um short."""
    raw_items: List[Dict[str, Any]] = []
    for item in (clip.get("fullscreen_motions") or []):
        if isinstance(item, dict):
            raw_items.append(dict(item))
    if not raw_items and clip.get("top_motion_html"):
        raw_items.append({
            "scene_id": str(clip.get("short_id") or "short_top"),
            "html_path": str(clip["top_motion_html"]),
            "t_ini": 0.0,
            "t_fim": dur_aligned,
            "mode": "split_top",
            "conclusion_sfx": clip.get("conclusion_sfx") or "check",
            "sfx_events": clip.get("top_motion_sfx_events") or [],
        })
    elif not raw_items and clip.get("motion_html"):
        raw_items.append({
            "scene_id": str(clip.get("short_id") or "short_full"),
            "html_path": str(clip["motion_html"]),
            "t_ini": 0.0,
            "t_fim": dur_aligned,
            "mode": "fullscreen",
            "conclusion_sfx": clip.get("conclusion_sfx") or "check",
            "sfx_events": clip.get("motion_sfx_events") or [],
        })

    normalized: List[Dict[str, Any]] = []
    for idx, item in enumerate(raw_items):
        t_ini = max(0.0, float(item.get("t_ini", item.get("start_rel", 0.0))))
        t_fim = min(dur_aligned, float(item.get("t_fim", item.get("end_rel", dur_aligned))))
        if t_fim - t_ini < 0.25:
            continue
        mode = str(item.get("mode") or "split_top").strip().lower()
        if mode not in ("split_top", "fullscreen"):
            mode = "split_top"
        normalized.append({
            **item,
            "scene_id": str(item.get("scene_id") or item.get("id_cena") or f"short_fs_{idx}"),
            "t_ini": round(t_ini, 3),
            "t_fim": round(t_fim, 3),
            "mode": mode,
        })
    return normalized


def _load_robust_sound_bus(branding_dir: Path):
    import importlib.util

    cands = [
        branding_dir / "scripts" / "som.py",
        _REPO_ROOT / "projetos" / "dr-gestao" / "branding" / "scripts" / "som.py",
    ]
    for cand in cands:
        if cand.is_file():
            spec = importlib.util.spec_from_file_location("_shorts_som_bus", str(cand))
            if spec and spec.loader:
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                bus_cls = getattr(mod, "RobustSoundBus", None)
                if bus_cls is not None:
                    return bus_cls
    return None


def _compile_short_sfx_with_sound_bus(
    clip: Dict[str, Any],
    dur_aligned: float,
    sons_dir: Path,
    branding_dir: Path,
) -> List[Tuple[Path, float, float]]:
    """Compila SFX automaticos (fullscreen_motion + cards) e explicitos via RobustSoundBus."""
    bus_cls = _load_robust_sound_bus(branding_dir)
    if bus_cls is None:
        raw_sfx = []
        for item in (clip.get("sfx_triggers") or []):
            if isinstance(item, (list, tuple)) and len(item) >= 3:
                p = sons_dir / str(item[0])
                t_s = float(item[1])
                vol = max(0.05, min(0.45, float(item[2])))
                if p.is_file() and 0.0 <= t_s < dur_aligned - 0.04:
                    raw_sfx.append((p, t_s, vol))
        return raw_sfx

    bus = bus_cls(track_base=20)
    for idx_ex, item in enumerate(clip.get("sfx_triggers") or []):
        if isinstance(item, (list, tuple)) and len(item) >= 3:
            s_name = Path(str(item[0])).stem
            t_s = float(item[1])
            vol = max(0.05, min(0.45, float(item[2])))
        elif isinstance(item, dict):
            s_ref = str(item.get("sound_ref") or item.get("sound") or item.get("som") or "").strip()
            if not s_ref:
                continue
            s_name = Path(s_ref).stem
            t_s = float(item.get("t", item.get("offset_s", 0.0)))
            vol = max(0.05, min(0.45, float(item.get("volume", 0.36))))
        else:
            continue
        if (sons_dir / f"{s_name}.wav").is_file() and 0.0 <= t_s < dur_aligned - 0.04:
            bus.registrar_explicito(f"short_exp_{idx_ex}", s_name, t_s, volume=vol, origem="shorts")

    fs_motions = _extract_short_fullscreen_motions(clip, dur_aligned)
    for idx_fs, fs_cfg in enumerate(fs_motions):
        fs_ini = float(fs_cfg["t_ini"])
        fs_dur = float(fs_cfg["t_fim"]) - fs_ini
        triggers = build_fullscreen_motion_sfx_events(
            f"{fs_cfg['scene_id']}_{idx_fs}",
            fs_ini,
            fs_dur,
            explicit_sfx_events=fs_cfg.get("sfx_events"),
            include_entry_whoosh=True,
            include_exit_swish=True,
            conclusion_sfx=str(fs_cfg.get("conclusion_sfx") or "check"),
        )
        for ev in triggers:
            s_name = str(ev["som"])
            t_s = float(ev["t"])
            vol = max(0.05, min(0.45, float(ev["volume"])))
            if not (sons_dir / f"{s_name}.wav").is_file() or not (0.0 <= t_s < dur_aligned - 0.04):
                continue
            if ev.get("modo") == "explicit":
                bus.registrar_explicito(str(ev["event_id"]), s_name, t_s, volume=vol, origem="shorts_fs")
            else:
                bus.registrar_automatico(str(ev["event_id"]), s_name, t_s, volume=vol, origem="shorts_fs")

    for idx_c, card in enumerate(clip.get("cards") or []):
        c_in = max(0.0, float(card.get("t_ini", 0.0)))
        c_out = min(dur_aligned, float(card.get("t_fim", dur_aligned)))
        c_dur = c_out - c_in
        if c_dur < 0.4:
            continue
        if any(float(fs["t_ini"]) <= c_in < float(fs["t_fim"]) for fs in fs_motions):
            continue
        if (sons_dir / "whoosh_curto.wav").is_file():
            bus.registrar_automatico(f"card_{idx_c}_in", "whoosh_curto", max(0.0, c_in - 0.02), volume=0.36, origem="shorts_card")
        if c_dur >= 1.5 and (sons_dir / "clique2.wav").is_file():
            bus.registrar_automatico(f"card_{idx_c}_beat", "clique2", round(c_in + min(0.45, c_dur * 0.30), 3), volume=0.32, origem="shorts_card")
        out_stem = "check" if card.get("checks") else "swish"
        if c_dur >= 1.0 and (sons_dir / f"{out_stem}.wav").is_file():
            bus.registrar_automatico(f"card_{idx_c}_out", out_stem, round(max(c_in, c_out - 0.25), 3), volume=0.30, origem="shorts_card")

    compiled = bus.compilar(duracao_cache_fn=lambda name: _wav_duration(sons_dir / f"{name}.wav"))
    valid: List[Tuple[Path, float, float]] = []
    for c in compiled:
        wav_p = sons_dir / f"{c['som']}.wav"
        t_c = float(c["t"])
        v_c = max(0.05, min(0.45, float(c["volume"])))
        if wav_p.is_file() and 0.0 <= t_c < dur_aligned - 0.04:
            valid.append((wav_p, t_c, v_c))
    return valid


def _render_split_stage_short(
    clip: Dict[str, Any],
    *,
    base_video_path: Path,
    voz_wav_path: Path,
    palavras_path: Path,
    brand_profile: Dict[str, Any],
    output_path: Path,
    workspace_root: Optional[Path] = None,
    marca_id: Optional[str] = None,
    episodio_id: Optional[str] = None,
    render_meta: Optional[Dict[str, Any]] = None,
) -> float:
    """Renderiza Short 9:16 (1080x1920, 30fps) com Split Stage, cards animados,
    legendas dinamicas palavra por palavra em y=1020, sound design e vinhetas multi-marca.
    Retorna a duracao total esperada (segundos) do arquivo final gerado.
    """
    import numpy as np
    from PIL import Image, ImageDraw

    short_id = _validate_short_id(clip["short_id"])
    t_ini_orig = float(clip["start"])
    t_fim = float(clip["end"])
    todas_palavras = json.loads(palavras_path.read_text(encoding="utf-8"))
    hook_txt = clip.get("gancho") or clip.get("hook")
    t_ini, palavras, sanitize_info = sanitize_short_start_and_words(
        t_ini_orig, t_fim, todas_palavras, hook_text=str(hook_txt) if hook_txt else None
    )
    shift_s = max(0.0, t_ini - t_ini_orig)
    dur = max(0.2, t_fim - t_ini)
    fps = 30
    W, H = 1080, 1920
    total_frames = max(1, int(round(dur * fps)))
    dur_aligned = total_frames / float(fps)
    clip_work = _shift_relative_clip_events(clip, shift_s, dur_aligned)

    asset_dirs = resolve_brand_asset_dirs(
        workspace_root, marca_id, brand_profile=brand_profile, repo_root=_REPO_ROOT
    )
    branding_dir, sons_dir = _resolve_branding_assets(
        workspace_root, marca_id, brand_profile=brand_profile
    )
    logos_dirs = list(asset_dirs.get("logos_dirs") or [])

    bold_cands = ("C:\\Windows\\Fonts\\segoeuib.ttf", "segoeuib.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf")
    reg_cands = ("C:\\Windows\\Fonts\\segoeui.ttf", "segoeui.ttf", "arial.ttf", "DejaVuSans.ttf")
    font_badge = _load_ttf(bold_cands, 24)
    font_card_tit = _load_ttf(bold_cands, 44)
    font_card_sub = _load_ttf(reg_cands, 27)
    font_card_lead = _load_ttf(bold_cands, 28)
    font_card_item = _load_ttf(reg_cands, 29)
    font_card_item_b = _load_ttf(bold_cands, 29)
    font_caption = _load_ttf(bold_cands, 44)
    font_caption_hl = _load_ttf(bold_cands, 48)
    font_meta = _load_ttf(bold_cands, 22)
    font_counter = _load_ttf(bold_cands, 54)

    # Logo oficial branco da marca ativa (zero vazamento de outra marca)
    logo_img = None
    logo_cand = None
    for ld in logos_dirs:
        for nm in ("Logo-Branco-Crop.png", "Logo-Branco.png"):
            cand_l = Path(ld) / nm
            if cand_l.is_file():
                logo_cand = cand_l
                break
        if logo_cand is not None:
            break
    if logo_cand is not None and logo_cand.is_file():
        lg = Image.open(logo_cand).convert("RGBA")
        bbox = lg.getbbox()
        if bbox:
            lg = lg.crop(bbox)
        _, _, _, alpha_ch = lg.split()
        white_lg = Image.new("RGBA", lg.size, (255, 255, 255, 0))
        white_lg.putalpha(alpha_ch)
        lw = 180
        lh = max(1, int(white_lg.height * (lw / white_lg.width)))
        logo_img = white_lg.resize((lw, lh), Image.Resampling.LANCZOS)

    # Centro horizontal do rosto na camera 16:9 (sem cortar ou distorcer)
    face = ((brand_profile or {}).get("presenter") or {}).get("face_anchor_1080p", [980, 420])
    face_cx = int(clip.get("face_cx") or (face[0] if isinstance(face, (list, tuple)) and len(face) >= 1 else 980))

    # Fundo topo gradiente escuro oficial da marca
    bg_topo = np.zeros((H, W, 4), dtype=np.uint8)
    bg_topo[:, :] = [10, 14, 26, 255]
    Y_grid, X_grid = np.ogrid[:980, :W]
    dist_topo = np.sqrt((X_grid - 540) ** 2 + (Y_grid - 300) ** 2)
    bg_topo[:980, :, 0] = np.clip(16 + (30 - dist_topo * 0.03), 10, 40).astype(np.uint8)
    bg_topo[:980, :, 1] = np.clip(24 + (45 - dist_topo * 0.04), 14, 60).astype(np.uint8)
    bg_topo[:980, :, 2] = np.clip(45 + (85 - dist_topo * 0.07), 26, 110).astype(np.uint8)
    bg_topo_img = Image.fromarray(bg_topo, mode="RGBA")

    mask_cam = Image.new("L", (1080, 940), 0)
    mask_draw = ImageDraw.Draw(mask_cam)
    mask_draw.rounded_rectangle([0, 0, 1080, 940], radius=36, fill=255)

    def _draw_vector_check(draw_ctx: Any, x: int, y: int, anim_val: float) -> None:
        a = int(255 * anim_val)
        draw_ctx.ellipse([x, y + 4, x + 28, y + 32], fill=(16, 185, 129, a))
        draw_ctx.line([x + 8, y + 18, x + 13, y + 24], fill=(255, 255, 255, a), width=3)
        draw_ctx.line([x + 13, y + 24, x + 22, y + 12], fill=(255, 255, 255, a), width=3)

    # Agrupar palavras sanitizadas em frases curtas para legenda dinamica (<= 900px de largura)
    frases: List[List[Dict[str, Any]]] = []
    cur_frase: List[Dict[str, Any]] = []
    dummy_draw = ImageDraw.Draw(Image.new("RGB", (W, 120)))
    cur_w = 0.0
    for p in palavras:
        w_txt = str(p.get("w") or "").strip()
        if not w_txt:
            continue
        w_px = float(dummy_draw.textlength(w_txt.upper(), font=font_caption_hl)) + 18.0
        if cur_frase and (cur_w + w_px > 780 or len(cur_frase) >= 3):
            frases.append(cur_frase)
            cur_frase = []
            cur_w = 0.0
        cur_frase.append(p)
        cur_w += w_px
        if w_txt.endswith((".", ",", "?", "!")):
            frases.append(cur_frase)
            cur_frase = []
            cur_w = 0.0
    if cur_frase:
        frases.append(cur_frase)

    cards = list(clip_work.get("cards") or [])
    steppers = list(clip_work.get("steppers") or [])
    canal_lbl = str((brand_profile or {}).get("display_name") or marca_id or "DESTAQUE").upper()
    badge_topo = str(clip_work.get("badge_topo") or canal_lbl)
    include_outro = bool(clip_work.get("include_outro", True))
    include_intro = clip_work.get("include_intro")
    outro_plan = resolve_brand_bumper(
        "outro",
        "9:16",
        workspace_root=workspace_root,
        marca_id=marca_id,
        brand_profile=brand_profile,
        enabled=include_outro,
        repo_root=_REPO_ROOT,
    )
    intro_plan = resolve_brand_bumper(
        "intro",
        "9:16",
        workspace_root=workspace_root,
        marca_id=marca_id,
        brand_profile=brand_profile,
        enabled=include_intro,
        repo_root=_REPO_ROOT,
    )
    fs_motions = _extract_short_fullscreen_motions(clip_work, dur_aligned)

    auth_fs_roots: List[Path] = [
        base_video_path.parent,
        base_video_path.parent.parent,
        base_video_path.parent.parent.parent,
        base_video_path.parent.parent.parent.parent,
        branding_dir,
        _REPO_ROOT,
    ]
    if workspace_root is not None and marca_id and episodio_id:
        ep_root = Path(workspace_root).resolve() / "projetos" / marca_id / "episodios" / episodio_id
        auth_fs_roots = [ep_root, ep_root / "workspace"] + auth_fs_roots

    with tempfile.TemporaryDirectory(prefix=f"short_{short_id}_") as td_str:
        td = Path(td_str)
        temp_base = td / "base_frames"
        temp_out = td / "out_frames"
        temp_base.mkdir(parents=True, exist_ok=True)
        temp_out.mkdir(parents=True, exist_ok=True)

        # 0. Pre-renderizar cenas fullscreen_motion via HyperFrames (GSAP continuo, nunca slide estatico)
        rendered_fs_scenes: List[Dict[str, Any]] = []
        for idx_fs, fs_cfg in enumerate(fs_motions):
            res_html = _resolve_fullscreen_motion_html(fs_cfg, auth_fs_roots)
            if not res_html.get("resolved"):
                raise ShortsRenderError(
                    f"HTML fullscreen_motion nao resolvido no short '{short_id}': {res_html.get('reason')}"
                )
            fs_ini = float(fs_cfg["t_ini"])
            fs_fim = float(fs_cfg["t_fim"])
            fs_dur = max(0.25, fs_fim - fs_ini)
            fs_h = 1920 if fs_cfg["mode"] == "fullscreen" else 960
            fs_mp4 = td / f"fs_{idx_fs}.mp4"
            fs_work = Path(res_html["path"]).parent
            render_fullscreen_motion_scene(
                res_html["path"],
                fs_mp4,
                width=1080,
                height=fs_h,
                fps=fps,
                duration=fs_dur,
                work_dir=fs_work,
                workers=2,
                editor_root=_REPO_ROOT,
                embed_sfx=False,
            )
            fs_frames_dir = td / f"fs_frames_{idx_fs}"
            fs_frames_dir.mkdir(parents=True, exist_ok=True)
            fs_n_frames = max(1, int(round(fs_dur * fps)))
            res_fext = _run([
                "ffmpeg", "-y", "-nostdin", "-loglevel", "error",
                "-i", str(fs_mp4),
                "-vf", f"fps={fps}", "-frames:v", str(fs_n_frames), "-q:v", "2",
                str(fs_frames_dir / "fs_%05d.jpg"),
            ])
            if res_fext.returncode != 0:
                raise ShortsRenderError(f"Falha ao extrair quadros da cena fullscreen_motion no short '{short_id}': {res_fext.stderr[-300:]}")
            rendered_fs_scenes.append({
                "t_ini": fs_ini,
                "t_fim": fs_fim,
                "mode": fs_cfg["mode"],
                "frames_dir": fs_frames_dir,
                "total_frames": fs_n_frames,
            })

        # 1. Extrair quadros da camera base exatos a 30fps
        res_ext = _run([
            "ffmpeg", "-y", "-nostdin", "-loglevel", "error",
            "-ss", f"{t_ini:.3f}", "-t", f"{dur_aligned:.3f}",
            "-i", str(base_video_path),
            "-vf", "fps=30", "-frames:v", str(total_frames), "-q:v", "2",
            str(temp_base / "f_%05d.jpg"),
        ])
        if res_ext.returncode != 0:
            raise ShortsRenderError(f"Falha ao extrair quadros do short '{short_id}': {res_ext.stderr[-400:]}")

        card_x0, card_y0, card_x1, card_y1 = 60, 170, 1020, 870
        last_base_cam: Optional[Any] = None

        for f_idx in range(total_frames):
            t_atual = t_ini + (f_idx / float(fps))
            t_rel = f_idx / float(fps)

            frame_img = bg_topo_img.copy()
            draw = ImageDraw.Draw(frame_img)

            base_frame_path = temp_base / f"f_{f_idx + 1:05d}.jpg"
            if base_frame_path.is_file():
                cam_raw = Image.open(base_frame_path).convert("RGBA")
                cw_src, ch_src = cam_raw.size
                target_ratio = 1080.0 / 940.0
                crop_h = ch_src
                crop_w = min(cw_src, int(round(crop_h * target_ratio)))
                x0 = max(0, min(cw_src - crop_w, face_cx - crop_w // 2))
                last_base_cam = cam_raw.crop((x0, 0, x0 + crop_w, crop_h)).resize((1080, 940), Image.Resampling.BILINEAR)
            if last_base_cam is not None:
                frame_img.paste(last_base_cam, (0, 980), mask_cam)
                draw.arc([0, 980, 72, 1052], start=180, end=270, fill=(142, 125, 229, 180), width=3)
                draw.line([36, 980, 1044, 980], fill=(142, 125, 229, 180), width=3)
                draw.arc([1008, 980, 1080, 1052], start=270, end=360, fill=(142, 125, 229, 180), width=3)

            # Top Bar (Pill Badge + Logo Branca)
            bw = int(draw.textlength(badge_topo, font=font_badge)) + 70
            draw.rounded_rectangle([60, 68, 60 + bw, 122], radius=27, fill=(142, 125, 229, 45), outline=(142, 125, 229, 120), width=2)
            draw.ellipse([84, 90, 100, 106], fill=(142, 125, 229, 255))
            draw.text((116, 80), badge_topo, fill=(210, 200, 255, 255), font=font_badge)
            if logo_img is not None:
                frame_img.paste(logo_img, (W - logo_img.width - 60, int(95 - logo_img.height / 2)), logo_img)

            # Cena HyperFrames fullscreen_motion ativa (split_top 1080x960 ou fullscreen 1080x1920)
            active_fs = None
            for fs_item in rendered_fs_scenes:
                if fs_item["t_ini"] <= t_rel < fs_item["t_fim"]:
                    active_fs = fs_item
                    break

            if active_fs is not None:
                local_idx = min(
                    active_fs["total_frames"],
                    max(1, int(round((t_rel - active_fs["t_ini"]) * fps)) + 1),
                )
                fs_frame_p = active_fs["frames_dir"] / f"fs_{local_idx:05d}.jpg"
                if fs_frame_p.is_file():
                    fs_img = Image.open(fs_frame_p).convert("RGBA")
                    dt_in = t_rel - active_fs["t_ini"]
                    dt_out = active_fs["t_fim"] - t_rel
                    fs_alpha = 1.0
                    if dt_in < 0.20:
                        fs_alpha = max(0.0, dt_in / 0.20)
                    elif dt_out < 0.20:
                        fs_alpha = max(0.0, dt_out / 0.20)
                    if fs_alpha < 0.999:
                        _, _, _, a_fs = fs_img.split()
                        fs_img.putalpha(a_fs.point(lambda p: int(p * fs_alpha)))
                    frame_img.paste(fs_img, (0, 0), fs_img)

            # Card ativo (apenas quando nao ha cena fullscreen_motion ativa no mesmo instante)
            card_ativo = None
            if active_fs is None:
                for c in cards:
                    if float(c["t_ini"]) <= t_rel < float(c["t_fim"]):
                        card_ativo = c
                        break

            if card_ativo is not None:
                card_img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
                cdraw = ImageDraw.Draw(card_img)
                c_t_start = float(card_ativo["t_ini"])
                c_t_end = float(card_ativo["t_fim"])
                c_dt_in = t_rel - c_t_start
                c_dt_out = c_t_end - t_rel

                if c_dt_in < 0.35:
                    p_c = max(0.0, c_dt_in / 0.35)
                    c_ease = 1.0 - (1.0 - p_c) ** 3
                    card_dy = int(30 * (1.0 - c_ease))
                    card_alpha = c_ease
                elif c_dt_out < 0.35:
                    p_c = max(0.0, c_dt_out / 0.35)
                    c_ease = p_c ** 2
                    card_dy = int(30 * (1.0 - c_ease))
                    card_alpha = c_ease
                else:
                    card_dy = 0
                    card_alpha = 1.0

                cdraw.rounded_rectangle([card_x0 + 8, card_y0 + 16, card_x1 + 8, card_y1 + 16], radius=32, fill=(0, 0, 0, int(90 * card_alpha)))
                cdraw.rounded_rectangle([card_x0, card_y0, card_x1, card_y1], radius=32, fill=(18, 26, 46, int(242 * card_alpha)), outline=(142, 125, 229, int(110 * card_alpha)), width=2)

                e_pill, _, dy_pill = _calc_item_anim(t_rel, c_t_start + 0.15, dur=0.30, slide_dx=0, slide_dy=-15)
                if e_pill > 0:
                    p_txt = str(card_ativo.get("badge") or "DESTAQUE")
                    p_w = int(cdraw.textlength(p_txt, font=font_badge)) + 50
                    cdraw.rounded_rectangle([card_x0 + 40, card_y0 + 40 + dy_pill, card_x0 + 40 + p_w, card_y0 + 88 + dy_pill], radius=24, fill=(0, 74, 173, int(80 * e_pill)), outline=(47, 151, 212, int(140 * e_pill)), width=1)
                    cdraw.text((card_x0 + 60, card_y0 + 49 + dy_pill), p_txt, fill=(47, 210, 255, int(255 * e_pill)), font=font_badge)

                e_tit, _, dy_tit = _calc_item_anim(t_rel, c_t_start + 0.30, dur=0.35, slide_dx=0, slide_dy=15)
                if e_tit > 0:
                    cdraw.text((card_x0 + 40, card_y0 + 112 + dy_tit), str(card_ativo.get("tit") or ""), fill=(255, 255, 255, int(255 * e_tit)), font=font_card_tit)

                e_sub, dx_sub, _ = _calc_item_anim(t_rel, c_t_start + 0.50, dur=0.35, slide_dx=-15)
                if e_sub > 0:
                    sub_lines = _wrap_text_lines(cdraw, str(card_ativo.get("sub") or ""), font_card_sub, 860)
                    for si_l, s_line in enumerate(sub_lines[:2]):
                        cdraw.text((card_x0 + 40 + dx_sub, card_y0 + 178 + si_l * 34), s_line, fill=(180, 190, 215, int(255 * e_sub)), font=font_card_sub)

                if card_ativo.get("lead"):
                    e_lead, dx_lead, _ = _calc_item_anim(t_rel, c_t_start + 0.75, dur=0.30)
                    if e_lead > 0:
                        cdraw.text((card_x0 + 40 + dx_lead, card_y0 + 266), str(card_ativo["lead"]), fill=(255, 255, 255, int(255 * e_lead)), font=font_card_lead)

                if card_ativo.get("bullets"):
                    base_y = 330
                    for b_i, b_txt in enumerate(card_ativo["bullets"]):
                        e_b, dx_b, _ = _calc_item_anim(t_rel, c_t_start + 1.00 + b_i * 0.55, dur=0.35)
                        if e_b > 0:
                            y_pos = base_y + b_i * 60
                            cdraw.ellipse([card_x0 + 40 + dx_b, card_y0 + y_pos + 11, card_x0 + 56 + dx_b, card_y0 + y_pos + 27], fill=(239, 68, 68, int(255 * e_b)))
                            cdraw.text((card_x0 + 68 + dx_b, card_y0 + y_pos), str(b_txt), fill=(255, 130, 130, int(255 * e_b)), font=font_card_item)

                if card_ativo.get("checks"):
                    base_y = 330
                    for c_i, c_txt in enumerate(card_ativo["checks"]):
                        e_c, dx_c, _ = _calc_item_anim(t_rel, c_t_start + 1.00 + c_i * 0.65, dur=0.35)
                        if e_c > 0:
                            y_pos = base_y + c_i * 60
                            _draw_vector_check(cdraw, card_x0 + 40 + dx_c, card_y0 + y_pos, e_c)
                            cdraw.text((card_x0 + 80 + dx_c, card_y0 + y_pos), str(c_txt), fill=(110, 255, 175, int(255 * e_c)), font=font_card_item_b)

                if card_ativo.get("tipo_especial") == "marketplaces" and card_ativo.get("highlights"):
                    mkts = list(card_ativo["highlights"])
                    for m_i, (m_nome, m_desc, m_cor) in enumerate(mkts[:4]):
                        e_m, dx_m, _ = _calc_item_anim(t_rel, c_t_start + 0.85 + m_i * 0.50, dur=0.35)
                        if e_m > 0:
                            mx = card_x0 + 40 + (m_i % 2) * 460 + dx_m
                            my = card_y0 + 260 + (m_i // 2) * 135
                            cdraw.rounded_rectangle([mx, my, mx + 430, my + 115], radius=20, fill=(255, 255, 255, int(15 * e_m)), outline=(142, 125, 229, int(100 * e_m)), width=1)
                            cdraw.rounded_rectangle([mx + 20, my + 20, mx + 235, my + 60], radius=12, fill=(0, 0, 0, int(180 * e_m)), outline=(m_cor[0], m_cor[1], m_cor[2], int(160 * e_m)), width=1)
                            cdraw.text((mx + 32, my + 27), str(m_nome), fill=(255, 255, 255, int(255 * e_m)), font=font_meta)
                            cdraw.text((mx + 20, my + 74), str(m_desc), fill=(180, 190, 215, int(255 * e_m)), font=font_meta)

                if card_ativo.get("tipo_especial") == "contador_mvp":
                    e_cnt, _, _ = _calc_item_anim(t_rel, c_t_start + 0.75, dur=0.30)
                    if e_cnt > 0:
                        cdraw.rounded_rectangle([card_x0 + 40, card_y0 + 265, card_x1 - 40, card_y0 + 410], radius=24, fill=(10, 14, 24, int(210 * e_cnt)), outline=(0, 210, 255, int(120 * e_cnt)), width=2)
                        cdraw.text((card_x0 + 76, card_y0 + 286), "MÉTODO VALIDADO:", fill=(0, 210, 255, int(255 * e_cnt)), font=font_badge)
                        cdraw.text((card_x0 + 76, card_y0 + 328), "MINERAR · VALIDAR · PRODUZIR", fill=(255, 255, 255, int(255 * e_cnt)), font=font_counter if cdraw.textlength("MINERAR · VALIDAR · PRODUZIR", font=font_counter) <= 800 else font_card_tit)

                if steppers:
                    s_idx = int(card_ativo.get("stepper_idx", 0))
                    step_w = 260
                    for idx_s, lbl_s in enumerate(steppers[:3]):
                        sx = card_x0 + 40 + idx_s * (step_w + 30)
                        sy = card_y0 + 570
                        is_active = idx_s == s_idx
                        bg_c = (0, 74, 173, int(255 * card_alpha)) if is_active else (255, 255, 255, int(20 * card_alpha))
                        txt_c = (255, 255, 255, int(255 * card_alpha)) if is_active else (160, 168, 190, int(255 * card_alpha))
                        cdraw.rounded_rectangle([sx, sy, sx + step_w, sy + 64], radius=32, fill=bg_c, outline=(142, 125, 229, int(120 * card_alpha)) if is_active else None, width=2)
                        cdraw.text((sx + 28, sy + 18), str(lbl_s), fill=txt_c, font=font_meta)

                if card_alpha < 0.999:
                    _, _, _, a_c = card_img.split()
                    a_c = a_c.point(lambda p: int(p * card_alpha))
                    card_img.putalpha(a_c)
                frame_img.paste(card_img, (0, card_dy), card_img)

            # Legenda dinamica palavra por palavra ancorada na linha divisoria (~y=1020)
            frase_ativa = None
            for fr in frases:
                if float(fr[0]["t"]) - 0.15 <= t_atual <= float(fr[-1]["f"]) + 0.25:
                    frase_ativa = fr
                    break

            if frase_ativa:
                active_idx = -1
                for idx_p, p in enumerate(frase_ativa):
                    if float(p["t"]) - 0.03 <= t_atual <= float(p["f"]) + 0.06:
                        active_idx = idx_p
                if active_idx < 0:
                    for idx_p, p in enumerate(frase_ativa):
                        if float(p["t"]) <= t_atual:
                            active_idx = idx_p
                space_w = 18
                partes_w = []
                for idx_p, p in enumerate(frase_ativa):
                    w_txt = str(p["w"]).upper()
                    eh_ativa = idx_p == active_idx
                    fnt = font_caption_hl if eh_ativa else font_caption
                    w_word = float(draw.textlength(w_txt, font=fnt))
                    partes_w.append((w_txt, fnt, w_word, eh_ativa))
                total_w = sum(w for _, _, w, _ in partes_w) + space_w * max(0, len(partes_w) - 1)
                box_x0 = max(36, int(540 - total_w / 2 - 28))
                box_x1 = min(W - 36, int(540 + total_w / 2 + 28))
                draw.rounded_rectangle([box_x0, 960, box_x1, 1034], radius=24, fill=(8, 12, 24, 215), outline=(142, 125, 229, 110), width=2)
                cur_x = box_x0 + 28
                for w_txt, fnt, w_word, eh_ativa in partes_w:
                    cor = (0, 210, 255, 255) if eh_ativa else (255, 255, 255, 255)
                    draw.text((cur_x + 2, 972 + 2), w_txt, fill=(0, 0, 0, 235), font=fnt)
                    draw.text((cur_x, 972), w_txt, fill=cor, font=fnt)
                    cur_x += int(round(w_word)) + space_w

            frame_img.convert("RGB").save(temp_out / f"f_{f_idx + 1:05d}.jpg", quality=94)

        # 2. Mixar audio (voz limpa + triggers de SFX via RobustSoundBus / FFmpeg)
        base_mp4 = td / f"{short_id}_base.mp4"
        sfx_valid = _compile_short_sfx_with_sound_bus(clip_work, dur_aligned, sons_dir, branding_dir)
        cmd_p1 = [
            "ffmpeg", "-y", "-nostdin", "-loglevel", "error",
            "-framerate", str(fps), "-i", str(temp_out / "f_%05d.jpg"),
            "-ss", f"{t_ini:.3f}", "-t", f"{dur_aligned:.3f}", "-i", str(voz_wav_path),
        ]
        for s_path, _, _ in sfx_valid:
            cmd_p1 += ["-i", str(s_path)]
        v_stage = "[0:v]scale=1080:1920:in_range=full:out_range=tv,format=yuv420p,setsar=1[v0]"
        if sfx_valid:
            fil_a = [f"[1:a]aresample=48000,aformat=channel_layouts=stereo,atrim=0:{dur_aligned:.6f},asetpts=PTS-STARTPTS[av0]"]
            mix_lbls = ["[av0]"]
            for idx_s, (_, s_t, s_gain) in enumerate(sfx_valid, start=1):
                in_idx = 1 + idx_s
                ms = round(s_t * 1000)
                fil_a.append(
                    f"[{in_idx}:a]aresample=48000,aformat=channel_layouts=stereo,volume={s_gain:.3f},"
                    f"adelay={ms}|{ms},apad,atrim=0:{dur_aligned:.6f},asetpts=PTS-STARTPTS[as{idx_s}]"
                )
                mix_lbls.append(f"[as{idx_s}]")
            n_mix = len(mix_lbls)
            fil_a.append("".join(mix_lbls) + f"amix=inputs={n_mix}:duration=first:dropout_transition=0,volume={n_mix}[aout]")
            filter_p1 = v_stage + ";" + ";".join(fil_a)
            cmd_p1 += ["-filter_complex", filter_p1, "-map", "[v0]", "-map", "[aout]"]
        else:
            cmd_p1 += ["-filter_complex", v_stage, "-map", "[v0]", "-map", "1:a"]

        cmd_p1 += [
            "-c:v", "libx264", "-preset", "fast", "-crf", "17", "-color_range", "tv", "-pix_fmt", "yuv420p", "-r", str(fps),
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2", "-t", f"{dur_aligned:.6f}",
            str(base_mp4),
        ]
        res_p1 = _run(cmd_p1)
        if res_p1.returncode != 0:
            raise ShortsRenderError(f"FFmpeg falhou na composicao do short '{short_id}': {res_p1.stderr[-500:]}")

        # 3. Aplicar vinhetas multi-marca (Nivel 1 pronto, Nivel 2 gerado, Nivel 3 fade-out 0.5s) e -14 LUFS
        intro_ready = ensure_bumper_mp4(
            intro_plan,
            brand_profile=brand_profile,
            asset_dirs=asset_dirs,
            work_dir=td / "_bumpers",
            repo_root=_REPO_ROOT,
        )
        outro_ready = ensure_bumper_mp4(
            outro_plan,
            brand_profile=brand_profile,
            asset_dirs=asset_dirs,
            work_dir=td / "_bumpers",
            repo_root=_REPO_ROOT,
        )
        bumper_apply = apply_intro_outro_to_video(
            base_mp4,
            output_path,
            intro_plan=intro_ready,
            outro_plan=outro_ready,
            width=W,
            height=H,
            fps=fps,
            apply_loudnorm=True,
        )
        total_expected = float(bumper_apply.get("final_duration_seconds") or dur_aligned)
        if isinstance(render_meta, dict):
            render_meta["sanitize_start"] = sanitize_info
            render_meta["brand_bumpers"] = {
                "intro": intro_ready,
                "outro": outro_ready,
                "applied": {
                    "intro_applied": bumper_apply.get("intro_applied", False),
                    "outro_applied": bumper_apply.get("outro_applied", False),
                    "fade_out_applied": bumper_apply.get("fade_out_applied", False),
                },
            }
            render_meta["warnings"] = list(bumper_apply.get("warnings") or [])

    return round(total_expected, 3)


# ---------------------------------------------------------------------------
# render_shorts_from_master
# ---------------------------------------------------------------------------


def render_shorts_from_master(
    workspace_root: str | Path,
    marca_id: str,
    episodio_id: str,
    clips: List[Dict[str, Any]],
    *,
    output_dir: Optional[str | Path] = None,
    use_raw_source_if_so_cortes: bool = False,
) -> Dict[str, Any]:
    """Renderiza derivados verticais 9:16 (Shorts) a partir do master aprovado
    (ou direto de brutos/ no modo 'so_cortes' quando nao houver master).

    Parametros
    ----------
    workspace_root:
        Raiz do workspace.
    marca_id, episodio_id:
        Slugs validados pelo WorkspaceLoader.
    clips:
        Lista nao vazia de dicts: {short_id, start, end}.
    output_dir:
        Diretorio de saida dos derivados. Default:
        workspace/renders/shorts/<marca>/<episodio>.

    Retorna dicionario com:
      master_path, master_sha256, master_duration, output_dir,
      shorts (lista de resultados por derivado), manifest_path.
    """
    root = Path(workspace_root).resolve()
    loader = WorkspaceLoader(root)
    loader.load_workspace()

    master_candidate = Path(
        loader.resolve_episodio_asset(
            marca_id, episodio_id, "workspace/renders/master_16x9.mp4"
        )
    ).resolve()
    briefing_dir = loader.resolve_episodio_asset(marca_id, episodio_id, "workspace/briefing")
    user_brief = load_user_brief(briefing_dir)

    so_cortes_mode = (
        use_raw_source_if_so_cortes
        or (user_brief.get("modo") == "so_cortes" and not master_candidate.is_file())
    )

    if so_cortes_mode and not master_candidate.is_file():
        projeto = loader.load_project(marca_id, episodio_id)
        sources = projeto.get("sources", []) or []
        if not sources or not sources[0].get("path"):
            raise ShortsRenderError(
                f"Nenhuma fonte em brutos/ registrada para {marca_id}/{episodio_id}."
            )
        master = Path(sources[0]["path"]).resolve()
        if not master.is_file() or master.stat().st_size <= 0:
            raise ShortsRenderError(f"Arquivo bruto inexistente ou vazio: {master}")
        if sources[0].get("sha256"):
            try:
                verify_source_integrity(master, sources[0]["sha256"], master.name)
            except IngestError as exc:
                raise ShortsRenderError(str(exc)) from exc
        master_sha = sha256_file(master)
        master_duration = _probe_duration(master)
        needs_loudnorm = True
    else:
        # 1) Master deve estar aprovado e valido (nao adulterado).
        try:
            verify_master_16x9_approval(root, marca_id, episodio_id, require_valid=True)
        except MasterApprovalError as exc:
            raise ShortsRenderError(str(exc)) from exc

        master = master_candidate
        if not master.is_file() or master.stat().st_size <= 0:
            raise ShortsRenderError(f"master 16:9 inexistente ou vazio: {master}")
        master_sha = sha256_file(master)
        master_duration = _probe_duration(master)
        needs_loudnorm = False

    # 2) Validar clips.
    _validate_clips(clips, master_duration)

    # Diretorio de saida.
    if output_dir is not None:
        out_dir = Path(output_dir).resolve()
    else:
        out_dir = _shorts_dir(root, marca_id, episodio_id)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Filtro de enquadramento 9:16 adaptativo (suporta entrada 16:9 ou 9:16).
    crop_filter = (
        "crop='min(iw,ih*9/16)':'min(ih,iw*16/9)':"
        "'(iw-min(iw,ih*9/16))/2':'(ih-min(ih,iw*16/9))/2',"
        "scale=1080:1920:flags=lanczos,setsar=1,fps=30"
    )

    shorts_results: List[Dict[str, Any]] = []
    manifest = _load_manifest(out_dir)

    brand_profile = load_brand_profile(root, marca_id)
    work_media_dir = loader.resolve_episodio_asset(marca_id, episodio_id, "workspace/renders/_work/media")
    split_base = work_media_dir / "base.mp4"
    split_voz = work_media_dir / "voz.wav"
    split_palavras = work_media_dir / "palavras_saida.json"

    for clip in clips:
        short_id = _validate_short_id(clip["short_id"])
        start = float(clip["start"])
        end = float(clip["end"])
        duration = end - start

        output_path = out_dir / f"{short_id}.mp4"
        clip_render_meta: Dict[str, Any] = {}

        has_split_motion = bool(
            clip.get("cards")
            or clip.get("fullscreen_motions")
            or clip.get("top_motion_html")
            or clip.get("motion_html")
        )
        if has_split_motion and split_base.is_file() and split_voz.is_file() and split_palavras.is_file():
            expected_qa_duration = _render_split_stage_short(
                clip,
                base_video_path=split_base,
                voz_wav_path=split_voz,
                palavras_path=split_palavras,
                brand_profile=brand_profile,
                output_path=output_path,
                workspace_root=root,
                marca_id=marca_id,
                episodio_id=episodio_id,
                render_meta=clip_render_meta,
            )
            eff_start = float((clip_render_meta.get("sanitize_start") or {}).get("sanitized_start", start))
        else:
            # Render do derivado simples: sanitiza abertura (quando houver palavras),
            # aplica enquadramento 9:16 e anexa vinhetas multi-marca (Niveis 1/2/3).
            eff_start = start
            if split_palavras.is_file() and not so_cortes_mode:
                try:
                    todas_p = json.loads(split_palavras.read_text(encoding="utf-8"))
                    eff_start, _, san_inf = sanitize_short_start_and_words(
                        start, end, todas_p, hook_text=clip.get("gancho") or clip.get("hook")
                    )
                    clip_render_meta["sanitize_start"] = san_inf
                except Exception:
                    eff_start = start
            eff_dur = max(0.2, end - eff_start)

            with tempfile.TemporaryDirectory(prefix=f"short_crop_{short_id}_") as td_crop_str:
                td_crop = Path(td_crop_str)
                crop_tmp = td_crop / f"{short_id}_rawcrop.mp4"
                cmd = [
                    "ffmpeg", "-y", "-v", "error",
                    "-ss", f"{eff_start:.3f}",
                    "-i", str(master),
                    "-t", f"{eff_dur:.3f}",
                    "-vf", crop_filter,
                ]
                if needs_loudnorm:
                    cmd += ["-af", "loudnorm=I=-14.0:TP=-1.0:LRA=11"]
                cmd += [
                    "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-ar", "48000", "-ac", "2",
                    "-movflags", "+faststart",
                    str(crop_tmp),
                ]
                res = _run(cmd)
                if res.returncode != 0:
                    raise ShortsRenderError(
                        f"ffmpeg falhou ao renderizar '{short_id}': "
                        f"{res.stderr.strip()[-800:]}"
                    )

                asset_dirs_s = resolve_brand_asset_dirs(
                    root, marca_id, brand_profile=brand_profile, repo_root=_REPO_ROOT
                )
                outro_p = resolve_brand_bumper(
                    "outro",
                    "9:16",
                    workspace_root=root,
                    marca_id=marca_id,
                    brand_profile=brand_profile,
                    enabled=bool(clip.get("include_outro", True)),
                    repo_root=_REPO_ROOT,
                )
                intro_p = resolve_brand_bumper(
                    "intro",
                    "9:16",
                    workspace_root=root,
                    marca_id=marca_id,
                    brand_profile=brand_profile,
                    enabled=clip.get("include_intro"),
                    repo_root=_REPO_ROOT,
                )
                intro_r = ensure_bumper_mp4(
                    intro_p, brand_profile=brand_profile, asset_dirs=asset_dirs_s, work_dir=td_crop / "_b_in", repo_root=_REPO_ROOT
                )
                outro_r = ensure_bumper_mp4(
                    outro_p, brand_profile=brand_profile, asset_dirs=asset_dirs_s, work_dir=td_crop / "_b_out", repo_root=_REPO_ROOT
                )
                b_app = apply_intro_outro_to_video(
                    crop_tmp,
                    output_path,
                    intro_plan=intro_r,
                    outro_plan=outro_r,
                    width=1080,
                    height=1920,
                    fps=30,
                    apply_loudnorm=True,
                )
                expected_qa_duration = float(b_app.get("final_duration_seconds") or eff_dur)
                clip_render_meta["brand_bumpers"] = {
                    "intro": intro_r,
                    "outro": outro_r,
                    "applied": {
                        "intro_applied": b_app.get("intro_applied", False),
                        "outro_applied": b_app.get("outro_applied", False),
                        "fade_out_applied": b_app.get("fade_out_applied", False),
                    },
                }
                clip_render_meta["warnings"] = list(b_app.get("warnings") or [])

        # QA automatizado do derivado.
        qa = _qa_short(output_path, expected_qa_duration)

        output_sha = sha256_file(output_path)

        entry: Dict[str, Any] = {
            "short_id": short_id,
            "source_master_path": str(master),
            "source_master_sha256": master_sha,
            "start": round(eff_start, 3),
            "end": round(end, 3),
            "duration_seconds": round(expected_qa_duration, 3),
            "output_path": str(output_path),
            "output_sha256": output_sha,
            "safe_zones_9x16": dict(SAFE_ZONES_9X16),
            "qa": qa,
            "approved": False,
            "approved_by": None,
            "approved_at": None,
        }
        if clip_render_meta.get("sanitize_start"):
            entry["sanitize_start"] = clip_render_meta["sanitize_start"]
        if clip_render_meta.get("brand_bumpers"):
            entry["brand_bumpers"] = clip_render_meta["brand_bumpers"]
        if clip_render_meta.get("warnings"):
            entry["warnings"] = clip_render_meta["warnings"]
        shorts_results.append(entry)
        manifest[short_id] = entry

    # Grava manifest e project.json.
    _save_manifest(out_dir, manifest)
    _update_project_shorts(root, loader, marca_id, episodio_id, manifest)

    return {
        "master_path": str(master),
        "master_sha256": master_sha,
        "master_duration": round(master_duration, 3),
        "output_dir": str(out_dir),
        "shorts": shorts_results,
        "manifest_path": str(_manifest_path(out_dir)),
    }


def render_approved_shorts(
    workspace_root: str | Path,
    marca_id: str,
    episodio_id: str,
    *,
    approved_short_ids: Optional[List[str]] = None,
    clips: Optional[List[Dict[str, Any]]] = None,
    approved_by: Optional[str] = None,
    output_dir: Optional[str | Path] = None,
) -> Dict[str, Any]:
    """Renderiza apenas os cortes aprovados no Portao Humano 2 (shorts_plan.json)."""
    root = Path(workspace_root).resolve()
    loader = WorkspaceLoader(root)
    loader.load_workspace()
    briefing_dir = loader.resolve_episodio_asset(marca_id, episodio_id, "workspace/briefing")
    user_brief = load_user_brief(briefing_dir)

    shorts_plan_path = briefing_dir / "shorts_plan.json"
    plan_modo = user_brief.get("modo", "completo")

    if clips is None:
        if not shorts_plan_path.is_file():
            raise ShortsRenderError(
                f"shorts_plan.json nao encontrado: {shorts_plan_path}. Execute suggest-shorts primeiro."
            )
        plan_data = json.loads(shorts_plan_path.read_text(encoding="utf-8"))
        plan_modo = plan_data.get("modo") or plan_modo
        suggestions = plan_data.get("suggestions", []) or []

        if approved_short_ids is not None:
            norm_ids = [s.strip() for s in approved_short_ids if s and s.strip()]
            approve_all = "all" in [x.lower() for x in norm_ids]
            for s in suggestions:
                s["approved"] = bool(approve_all or s.get("short_id") in norm_ids)
            plan_data["suggestions"] = suggestions
            shorts_plan_path.write_text(
                json.dumps(plan_data, indent=2, ensure_ascii=False), encoding="utf-8"
            )

        selected = [s for s in suggestions if s.get("approved") is True]
        if not selected:
            raise ShortsRenderError(
                "Nenhum corte aprovado no Portao Humano 2. Informe os IDs aprovados ou marque approved=true em shorts_plan.json."
            )
        _optional_clip_keys = (
            "cards",
            "fullscreen_motions",
            "top_motion_html",
            "motion_html",
            "steppers",
            "badge_topo",
            "sfx_triggers",
            "include_outro",
            "include_intro",
            "gancho",
            "hook",
            "face_cx",
        )
        clips = []
        for s in selected:
            c_item: Dict[str, Any] = {
                "short_id": s["short_id"],
                "start": float(s["start"]),
                "end": float(s["end"]),
            }
            for opt_k in _optional_clip_keys:
                if opt_k in s and s[opt_k] is not None:
                    c_item[opt_k] = s[opt_k]
            clips.append(c_item)

    master_candidate = Path(
        loader.resolve_episodio_asset(
            marca_id, episodio_id, "workspace/renders/master_16x9.mp4"
        )
    ).resolve()
    use_raw = (plan_modo == "so_cortes") and (not master_candidate.is_file())

    if not use_raw and master_candidate.is_file() and approved_by:
        verif = verify_master_16x9_approval(root, marca_id, episodio_id, require_valid=False)
        if not verif.get("approved"):
            approve_master_16x9(root, marca_id, episodio_id, approved_by=approved_by)

    return render_shorts_from_master(
        root,
        marca_id,
        episodio_id,
        clips,
        output_dir=output_dir,
        use_raw_source_if_so_cortes=use_raw,
    )


# ---------------------------------------------------------------------------
# approve_short_9x16
# ---------------------------------------------------------------------------


def approve_short_9x16(
    workspace_root: str | Path,
    marca_id: str,
    episodio_id: str,
    short_id: str,
    *,
    approved_by: str,
) -> Dict[str, Any]:
    """Aprova individualmente um derivado 9:16.

    Exige approved_by nao vazio, derivado existente, QA ok is True e
    SHA-256 atual == output_sha256 (nao adulterado). Gravacao apenas para
    aquele short_id em project.json e shorts_manifest.json.
    """
    root = Path(workspace_root).resolve()
    loader = WorkspaceLoader(root)
    loader.load_workspace()

    short_id = _validate_short_id(short_id)
    if not approved_by or not str(approved_by).strip():
        raise ShortsRenderError("approved_by nao pode ser vazio.")
    approved_by = str(approved_by).strip()

    shorts_dir = _shorts_dir(root, marca_id, episodio_id)
    manifest = _load_manifest(shorts_dir)

    if short_id not in manifest:
        raise ShortsRenderError(
            f"derivado '{short_id}' nao encontrado no manifest de shorts."
        )

    entry = manifest[short_id]
    output_path = Path(entry["output_path"])
    registered_sha = entry.get("output_sha256")

    # Derivado deve existir e nao estar vazio.
    if not output_path.is_file() or output_path.stat().st_size <= 0:
        raise ShortsRenderError(
            f"arquivo do derivado '{short_id}' inexistente ou vazio: {output_path}"
        )

    # QA deve estar ok.
    qa = entry.get("qa", {}) or {}
    if qa.get("ok") is not True:
        raise ShortsRenderError(
            f"derivado '{short_id}' sem QA aprovado (qa.ok={qa.get('ok')})."
        )

    # SHA-256 atual deve bater com o registrado (nao adulterado).
    current_sha = sha256_file(output_path)
    if registered_sha is None or current_sha != str(registered_sha):
        # Invalida aprovacao se existisse.
        entry["approved"] = False
        entry["approved_by"] = None
        entry["approved_at"] = None
        entry["approval_invalidated_reason"] = (
            f"SHA-256 divergente (registrado={registered_sha}, atual={current_sha})"
        )
        manifest[short_id] = entry
        _save_manifest(shorts_dir, manifest)
        _update_project_shorts(root, loader, marca_id, episodio_id, manifest)
        raise ShortsRenderError(
            f"derivado '{short_id}' adulterado: SHA-256 divergente "
            f"(registrado={registered_sha}, atual={current_sha})."
        )

    # Aprova.
    entry["approved"] = True
    entry["approved_by"] = approved_by
    entry["approved_at"] = _iso_now()
    manifest[short_id] = entry
    _save_manifest(shorts_dir, manifest)
    _update_project_shorts(root, loader, marca_id, episodio_id, manifest)

    return {
        "approved": True,
        "short_id": short_id,
        "output_path": str(output_path),
        "output_sha256": current_sha,
        "approved_by": approved_by,
        "approved_at": entry["approved_at"],
        "qa_ok": True,
    }
