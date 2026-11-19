# -*- coding: utf-8 -*-
"""
core/pipeline.py

Orquestrador ponta a ponta (L1..L6) do Editor.

Encadeia, de forma local, deterministica e offline:

    01_INGEST      -> ingest_media (custodia SHA-256, Delta-Hash = 0)
    02_ANALYZE     -> analyze_episodio (transcricao_injetada permitida)
    03_SEMANTIC    -> plan_episodio_semantics (provider injetavel / fallback)
    03_BRIEFING    -> gerar_briefing
    03_EDL         -> build_edl_from_alignment (jump cuts) + RhythmEngine
    03_LINT        -> master_lint.lint (bloqueia em failures)
    04_RENDER      -> render_edl_to_video (L1..L6 + loudnorm unico)
    04_QA          -> video_verify.verify_video_av
    04_TRACE       -> workspace/renders/traceability_report.json

Observacoes de contrato:
  * `transcricao_injetada` e explicito: quando informado, nenhum modelo
    Whisper e executado e a origem registrada e `injected_fixture`. Sem ele,
    o pipeline transcreve com faster-whisper LOCAL offline
    (`local_faster_whisper`) via `whisper_model_path` ou
    EDITOR_WHISPER_MODEL_PATH, com `local_files_only=True` e sem download.
  * `external_provider` e bloqueado nesta fase (modo offline); nao ha fallback
    silencioso para fixture quando a transcricao local falha.
  * Nenhuma chamada externa/IA e feita sem um `SemanticConsent` autorizado.
  * A duracao renderizada e a soma das duracoes raw dos segmentos do EDL
    (o eixo `out_*` do plano inclui padding de seguranca). Ambos os valores
    sao registrados no relatorio.
  * O master recebe exatamente um estagio de loudnorm no filtergraph final
    (alimiter + loudnorm), precedido de medicao em 2 passes; mesmo quando nao
    ha SFX.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set

try:
    from .workspace import WorkspaceLoader, WorkspaceError
    from .ingest import ingest_media, compute_sha256, verify_source_integrity
    from .analyze import analyze_episodio
    from .semantic_planner import (
        SemanticConsent,
        SemanticPlannerError,
        load_user_brief,
        plan_episodio_semantics,
    )
    from .briefing import gerar_briefing
    from .edl_builder import build_edl_from_alignment
    from .master_lint import lint as lint_plan
    from .edl_renderer import render_edl_to_video
    from .video_verify import verify_video_av
    from .component_catalog import LAYER_DEFAULT_COMPONENT
    from .transcript_review import (
        resolve_editorial_transcript,
        review_transcript,
        sync_alignment_with_editorial_transcript,
        TranscriptReviewError,
    )
except Exception:  # pragma: no cover - execucao direta
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from core.workspace import WorkspaceLoader, WorkspaceError  # type: ignore
    from core.ingest import ingest_media, compute_sha256  # type: ignore
    from core.analyze import analyze_episodio  # type: ignore
    from core.semantic_planner import (  # type: ignore
        SemanticConsent,
        SemanticPlannerError,
        load_user_brief,
        plan_episodio_semantics,
    )
    from core.briefing import gerar_briefing  # type: ignore
    from core.edl_builder import build_edl_from_alignment  # type: ignore
    from core.master_lint import lint as lint_plan  # type: ignore
    from core.edl_renderer import render_edl_to_video  # type: ignore
    from core.video_verify import verify_video_av  # type: ignore
    from core.component_catalog import LAYER_DEFAULT_COMPONENT  # type: ignore
    from core.transcript_review import (  # type: ignore
        resolve_editorial_transcript,
        review_transcript,
        sync_alignment_with_editorial_transcript,
        TranscriptReviewError,
    )

PIPELINE_SCHEMA_VERSION = "1.0.0"
PIPELINE_VERSION = "forge-pipeline-1.0.0"

TARGET_W, TARGET_H, TARGET_FPS = 1920, 1080, 30
AUDIO_SR = 48000

MEDIA_EXT = {
    ".mp4", ".mov", ".mkv", ".avi", ".webm",
    ".wav", ".mp3", ".flac", ".aac", ".m4a", ".ogg",
    ".png", ".jpg", ".jpeg", ".webp",
}

VISUAL_LAYERS = (
    "L2_titulo_heroi_t10",
    "L3_micro_zoom_bate",
    "L4_lower_third",
    "L5_broll_industrial",
    "L5_fullscreen_motion",
)
AUDIO_LAYER = "L6_sound_design_sync"


class PipelineError(Exception):
    """Falha bloqueante do pipeline."""


class PipelineQAError(PipelineError):
    """Master renderizado, mas reprovado no QA audiovisual."""

    def __init__(self, message: str, report: Dict[str, Any]) -> None:
        super().__init__(message)
        self.report = report


class MasterApprovalError(PipelineError):
    """Erro na aprovacao ou verificacao do master 16:9."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _iso_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: str | Path) -> str:
    """SHA-256 hex de um arquivo (via ingest.compute_sha256)."""
    digest, _ = compute_sha256(Path(path))
    return digest


def _events(layer: Any) -> List[Dict[str, Any]]:
    if isinstance(layer, list):
        return layer
    if not isinstance(layer, dict):
        return []
    for key in ("elements", "events", "keyframes"):
        if isinstance(layer.get(key), list):
            return layer[key]
    return []


def _timeline_events(edl: Dict[str, Any]) -> List[Dict[str, Any]]:
    events = edl.get("timeline_events")
    if isinstance(events, list):
        return [e for e in events if isinstance(e, dict)]
    return []


def expected_render_duration(edl: Dict[str, Any]) -> float:
    """Duracao efetivamente renderizada: soma das duracoes raw dos segmentos."""
    total = 0.0
    for ev in _timeline_events(edl):
        raw_in = float(ev.get("raw_in", ev.get("src_in", 0.0)))
        raw_out = float(ev.get("raw_out", ev.get("src_out", raw_in)))
        total += max(0.0, raw_out - raw_in)
    if total > 0:
        return round(total, 3)
    return round(float(edl.get("summary", {}).get("final_duration_seconds", 0.0)), 3)


def _resolve_media_ref(ref: str, roots: Sequence[Path]) -> Optional[Path]:
    """Resolve uma referencia relativa de asset contra as raizes autorizadas."""
    if not isinstance(ref, str) or not ref.strip():
        return None
    p = Path(ref)
    if p.is_absolute():
        return p if p.is_file() else None
    if ".." in p.parts:
        return None
    for root in roots:
        cand = (Path(root) / p).resolve()
        try:
            cand.relative_to(Path(root).resolve())
        except ValueError:
            continue
        if cand.is_file():
            return cand
    return None


def derive_qa_windows(
    editorial_plan: Dict[str, Any],
    expected_duration_s: float,
    *,
    max_visual: int = 8,
    max_audio: int = 6,
    executed_element_ids: Optional[Set[str]] = None,
) -> List[Dict[str, Any]]:
    """Deriva janelas de QA a partir do plano editorial.

    - L2..L5: janelas visuais (pixels dentro vs fora).
    - L6: janelas de audio apenas quando ha `sound_ref`/`media_ref` executavel.
    Janelas sao recortadas ao intervalo [0, expected_duration_s] do master.
    """
    windows: List[Dict[str, Any]] = []
    layers = editorial_plan.get("layers", {}) or {}
    duration = max(0.0, float(expected_duration_s))

    visual_count = 0
    for layer_name in VISUAL_LAYERS:
        for el in _events(layers.get(layer_name, [])):
            if visual_count >= max_visual:
                break
            el_id = el.get("element_id") or el.get("id")
            if executed_element_ids is not None and el_id not in executed_element_ids:
                continue
            if "out_in" not in el or "out_out" not in el:
                continue
            start = max(0.0, float(el["out_in"]))
            end = min(duration, float(el["out_out"]))
            if end - start < 0.20:
                continue
            windows.append(
                {
                    "layer": layer_name,
                    "kind": "visual",
                    "start": round(start, 3),
                    "end": round(end, 3),
                    "element_id": el_id,
                }
            )
            visual_count += 1

    audio_count = 0
    for el in _events(layers.get(AUDIO_LAYER, [])):
        if audio_count >= max_audio:
            break
        el_id = el.get("element_id") or el.get("id")
        if executed_element_ids is not None and el_id not in executed_element_ids:
            continue
        if not (el.get("sound_ref") or el.get("media_ref")):
            continue
        if "out_in" not in el or "out_out" not in el:
            continue
        start = max(0.0, float(el["out_in"]))
        end = min(duration, float(el["out_out"]))
        if end - start < 0.10:
            continue
        windows.append(
            {
                "layer": AUDIO_LAYER,
                "kind": "audio",
                "start": round(start, 3),
                "end": round(end, 3),
                "element_id": el_id,
            }
        )
        audio_count += 1

    return windows


def _nearest_edl_event(
    element: Dict[str, Any],
    edl_events: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    raw_in = element.get("raw_in")
    out_in = element.get("out_in")
    if raw_in is not None:
        try:
            raw_in_f = float(raw_in)
            for ev in edl_events:
                if float(ev.get("raw_in", 0)) <= raw_in_f <= float(ev.get("raw_out", 0)):
                    return ev
        except (TypeError, ValueError):
            pass
    if out_in is not None:
        try:
            out_in_f = float(out_in)
            for ev in edl_events:
                if float(ev.get("out_in", 0)) <= out_in_f <= float(ev.get("out_out", 0)):
                    return ev
        except (TypeError, ValueError):
            pass
    # fallback: evento de menor distancia no eixo out
    best = None
    best_d = float("inf")
    for ev in edl_events:
        try:
            d = abs(float(ev.get("out_in", 0)) - float(out_in or 0))
        except (TypeError, ValueError):
            continue
        if d < best_d:
            best_d = d
            best = ev
    return best


def build_trace_paths(
    editorial_plan: Dict[str, Any],
    edl: Dict[str, Any],
    expected_duration_s: float,
) -> List[Dict[str, Any]]:
    """Trilha: segmento -> decisao editorial -> evento EDL -> componente -> master."""
    edl_events = _timeline_events(edl)
    layers = editorial_plan.get("layers", {}) or {}
    paths: List[Dict[str, Any]] = []

    for layer_name, layer in layers.items():
        for el in _events(layer):
            event = _nearest_edl_event(el, edl_events)
            comp = (
                el.get("componente_motion_library")
                or el.get("component_id")
                or LAYER_DEFAULT_COMPONENT.get(layer_name)
            )
            out_in = el.get("out_in")
            out_out = el.get("out_out")
            try:
                win_in = round(max(0.0, float(out_in)), 3) if out_in is not None else None
                win_out = (
                    round(min(float(expected_duration_s), float(out_out)), 3)
                    if out_out is not None
                    else None
                )
            except (TypeError, ValueError):
                win_in = win_out = None
            paths.append(
                {
                    "layer": layer_name,
                    "element_id": el.get("element_id") or el.get("id"),
                    "origin": el.get("origin"),
                    "segment_ids": list(el.get("segment_ids", []) or []),
                    "word_ids": list(el.get("word_ids", []) or el.get("word_refs", []) or []),
                    "editorial_decision": el.get("operation")
                    or el.get("justification")
                    or el.get("justificativa"),
                    "edl_event_id": event.get("event_id") if event else None,
                    "edl_raw_window": (
                        {
                            "in": event.get("raw_in"),
                            "out": event.get("raw_out"),
                        }
                        if event
                        else None
                    ),
                    "component": comp,
                    "master_window": {"in": win_in, "out": win_out},
                    "media_ref": el.get("media_ref"),
                    "sound_ref": el.get("sound_ref"),
                }
            )
    return paths


# ---------------------------------------------------------------------------
# Pipeline principal
# ---------------------------------------------------------------------------


def _collect_asset_hashes(roots: Sequence[Path]) -> Dict[str, str]:
    """Hash de todos os assets de midia encontrados nas raizes indicadas."""
    hashes: Dict[str, str] = {}
    for root in roots:
        root_p = Path(root)
        if not root_p.is_dir():
            continue
        for p in sorted(root_p.rglob("*")):
            if "renders" in p.parts:
                continue
            if p.is_file() and p.suffix.lower() in MEDIA_EXT:
                try:
                    hashes[str(p.resolve())] = sha256_file(p)
                except Exception:  # pragma: no cover - defensivo
                    continue
    return hashes


# ---------------------------------------------------------------------------
# Aprovacao do master 16:9
# ---------------------------------------------------------------------------


def _resolve_master_path(
    root: Path,
    loader: WorkspaceLoader,
    marca_id: str,
    episodio_id: str,
    master_path: Optional[str | Path] = None,
) -> Path:
    """Resolve o caminho do master 16:9.

    Prioridade:
      1. `master_path` informado explicitamente;
      2. `traceability_report.json` -> identification.master_path;
      3. `project.json` -> approvals.master_16x9_path ou artifacts.04_render.master_16x9;
      4. Padrao: workspace/renders/master_16x9.mp4 do episodio.
    """
    if master_path is not None:
        return Path(master_path).resolve()

    # 2) traceability_report.json
    trace_path = loader.resolve_episodio_asset(
        marca_id, episodio_id, "workspace/renders/traceability_report.json"
    )
    if trace_path.is_file():
        try:
            trace = json.loads(trace_path.read_text(encoding="utf-8"))
            mp = trace.get("identification", {}).get("master_path")
            if mp and Path(mp).is_file():
                return Path(mp).resolve()
        except Exception:  # pragma: no cover - defensivo
            pass

    # 3) project.json
    projeto = loader.load_project(marca_id, episodio_id)
    aprova = projeto.get("approvals", {}) or {}
    mp = aprova.get("master_16x9_path")
    if mp and Path(mp).is_file():
        return Path(mp).resolve()
    render_ref = (
        (projeto.get("artifacts", {}) or {}).get("04_render", {}) or {}
    ).get("master_16x9")
    if render_ref:
        cand = (loader.resolve_episodio_asset(marca_id, episodio_id, "") / render_ref)
        if cand.is_file():
            return cand.resolve()

    # 4) Padrao
    return (
        loader.resolve_episodio_asset(marca_id, episodio_id, "workspace/renders")
        / "master_16x9.mp4"
    ).resolve()


def _qa_ok_for_master(
    root: Path,
    loader: WorkspaceLoader,
    marca_id: str,
    episodio_id: str,
    master: Path,
) -> bool:
    """Verifica se o master tem QA aprovado.

    Confere traceability_report.json (qa.ok is True e master_sha256 bate com
    o arquivo atual). Se nao houver QA valido, executa verify_video_av como
    fallback.
    """
    trace_path = loader.resolve_episodio_asset(
        marca_id, episodio_id, "workspace/renders/traceability_report.json"
    )
    if trace_path.is_file():
        try:
            trace = json.loads(trace_path.read_text(encoding="utf-8"))
            qa = trace.get("qa", {}) or {}
            if qa.get("ok") is True:
                trace_sha = trace.get("identification", {}).get("master_sha256")
                if trace_sha:
                    return sha256_file(master) == str(trace_sha)
                return True
        except Exception:  # pragma: no cover - defensivo
            pass

    # Fallback: executa verify_video_av direto no master.
    try:
        from .video_verify import verify_video_av  # type: ignore

        rep = verify_video_av(
            master,
            None,
            check_black=False,
            check_windows=False,
            require_audio=True,
        )
        return bool(rep.get("ok"))
    except Exception:  # pragma: no cover - defensivo
        return False


def _rel_within_workspace(root: Path, path: Path) -> str:
    """Retorna caminho relativo ao workspace quando possivel, senao absoluto."""
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:  # pragma: no cover - defensivo
        return str(path.resolve())


def approve_master_16x9(
    workspace_root: str | Path,
    marca_id: str,
    episodio_id: str,
    *,
    approved_by: str,
    master_path: Optional[str | Path] = None,
) -> Dict[str, Any]:
    """Aprova o master 16:9 de um episodio.

    Grava em project.json (approvals):
      master_16x9_approved, master_16x9_sha256, master_16x9_path,
      master_16x9_approved_by, master_16x9_approved_at.

    Levanta MasterApprovalError se approved_by vazio, master inexistente/vazio
    ou QA nao aprovado.
    """
    root = Path(workspace_root).resolve()
    loader = WorkspaceLoader(root)
    loader.load_workspace()

    if not approved_by or not str(approved_by).strip():
        raise MasterApprovalError("approved_by nao pode ser vazio.")
    approved_by = str(approved_by).strip()

    master = _resolve_master_path(root, loader, marca_id, episodio_id, master_path)
    if not master.is_file() or master.stat().st_size <= 0:
        raise MasterApprovalError(
            f"master 16:9 inexistente ou vazio: {master}"
        )

    if not _qa_ok_for_master(root, loader, marca_id, episodio_id, master):
        raise MasterApprovalError(
            f"QA nao aprovado para o master: {master}"
        )

    sha = sha256_file(master)

    projeto = loader.load_project(marca_id, episodio_id)
    projeto.setdefault("approvals", {})
    aprova = projeto["approvals"]
    aprova["master_16x9_approved"] = True
    aprova["master_16x9_sha256"] = sha
    aprova["master_16x9_path"] = _rel_within_workspace(root, master)
    aprova["master_16x9_approved_by"] = approved_by
    aprova["master_16x9_approved_at"] = _iso_now()
    projeto["updated_at"] = _iso_now()

    projeto_path = loader.project_file(marca_id, episodio_id)
    with open(projeto_path, "w", encoding="utf-8") as f:
        json.dump(projeto, f, indent=2, ensure_ascii=False)

    return {
        "approved": True,
        "master_16x9_approved": True,
        "master_path": str(master.resolve()),
        "master_16x9_path": aprova["master_16x9_path"],
        "master_sha256": sha,
        "approved_by": approved_by,
        "approved_at": aprova["master_16x9_approved_at"],
        "project_path": str(projeto_path),
    }


def verify_master_16x9_approval(
    workspace_root: str | Path,
    marca_id: str,
    episodio_id: str,
    *,
    require_valid: bool = False,
) -> Dict[str, Any]:
    """Verifica se a aprovacao do master 16:9 esta valida.

    Confere master_16x9_approved is True, arquivo existe e SHA-256 atual bate
    com o registrado. Se o arquivo mudou ou sumiu, invalida a aprovacao em
    project.json (master_16x9_approved = False com motivo).

    Retorna dicionario com approved, master_16x9_approved, master_path,
    master_sha256, current_sha256, qa_ok, reason, approved_by, approved_at.
    Levanta MasterApprovalError quando require_valid=True e nao estiver valido.
    """
    root = Path(workspace_root).resolve()
    loader = WorkspaceLoader(root)
    loader.load_workspace()

    projeto = loader.load_project(marca_id, episodio_id)
    aprova = projeto.get("approvals", {}) or {}

    approved = bool(aprova.get("master_16x9_approved"))
    registered_sha = aprova.get("master_16x9_sha256")
    registered_path = aprova.get("master_16x9_path")
    approved_by = aprova.get("master_16x9_approved_by")
    approved_at = aprova.get("master_16x9_approved_at")

    resultado: Dict[str, Any] = {
        "approved": False,
        "master_16x9_approved": False,
        "master_path": registered_path,
        "master_sha256": registered_sha,
        "current_sha256": None,
        "qa_ok": None,
        "reason": None,
        "approved_by": approved_by,
        "approved_at": approved_at,
    }

    if not approved:
        resultado["reason"] = "master nao aprovado"
        if require_valid:
            raise MasterApprovalError("master 16:9 nao aprovado.")
        return resultado

    # Resolve caminho do master.
    master = None
    if registered_path:
        cand = Path(registered_path)
        if not cand.is_absolute():
            cand = (root / cand).resolve()
        else:
            cand = cand.resolve()
        if cand.is_file():
            master = cand
    if master is None:
        master = _resolve_master_path(root, loader, marca_id, episodio_id)

    current_sha = None
    if master is not None and master.is_file() and master.stat().st_size > 0:
        current_sha = sha256_file(master)
        resultado["current_sha256"] = current_sha
        resultado["master_path"] = str(master)
    else:
        # Arquivo sumiu ou vazio -> invalida.
        aprova["master_16x9_approved"] = False
        aprova["master_16x9_sha256"] = None
        aprova["master_16x9_approved_by"] = None
        aprova["master_16x9_approved_at"] = None
        aprova["master_16x9_approval_invalidated_reason"] = (
            "master arquivo ausente ou vazio"
        )
        projeto["updated_at"] = _iso_now()
        _gravar_projeto(loader, marca_id, episodio_id, projeto)
        resultado["master_16x9_approved"] = False
        resultado["reason"] = "master arquivo ausente ou vazio"
        if require_valid:
            raise MasterApprovalError(resultado["reason"])
        return resultado

    # Compara SHA-256.
    if registered_sha is None or current_sha != str(registered_sha):
        aprova["master_16x9_approved"] = False
        aprova["master_16x9_sha256"] = None
        aprova["master_16x9_approved_by"] = None
        aprova["master_16x9_approved_at"] = None
        aprova["master_16x9_approval_invalidated_reason"] = (
            f"SHA-256 divergente (registrado={registered_sha}, "
            f"atual={current_sha})"
        )
        projeto["updated_at"] = _iso_now()
        _gravar_projeto(loader, marca_id, episodio_id, projeto)
        resultado["master_16x9_approved"] = False
        resultado["reason"] = (
            f"SHA-256 divergente: registrado={registered_sha}, atual={current_sha}"
        )
        if require_valid:
            raise MasterApprovalError(resultado["reason"])
        return resultado

    # QA do traceability.
    trace_path = loader.resolve_episodio_asset(
        marca_id, episodio_id, "workspace/renders/traceability_report.json"
    )
    qa_ok = None
    if trace_path.is_file():
        try:
            trace = json.loads(trace_path.read_text(encoding="utf-8"))
            qa = trace.get("qa", {}) or {}
            qa_ok = bool(qa.get("ok"))
        except Exception:  # pragma: no cover - defensivo
            qa_ok = None
    resultado["qa_ok"] = qa_ok

    resultado["approved"] = True
    resultado["master_16x9_approved"] = True
    resultado["master_sha256"] = registered_sha
    resultado["reason"] = None
    if require_valid and qa_ok is False:
        raise MasterApprovalError("QA do master nao aprovado.")
    return resultado


def _gravar_projeto(
    loader: WorkspaceLoader, marca_id: str, episodio_id: str, projeto: Dict[str, Any]
) -> None:
    """Grava project.json do episodio."""
    projeto_path = loader.project_file(marca_id, episodio_id)
    with open(projeto_path, "w", encoding="utf-8") as f:
        json.dump(projeto, f, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Helper compartilhado: render/QA/trace (etapas 04)
# Usado tanto por run_episode_pipeline quanto por render_existing_episode.
# ---------------------------------------------------------------------------


def _executar_render_qa_trace(
    *,
    root: Path,
    loader: WorkspaceLoader,
    marca_id: str,
    episodio_id: str,
    edl: Dict[str, Any],
    editorial_plan: Dict[str, Any],
    brand_profile: Dict[str, Any],
    brutos_path: Path,
    fonte_dir: Path,
    branding_dir: Path,
    ep_dir: Path,
    renders_dir: Path,
    wd: Path,
    qa_dir: Path,
    render_duration: float,
    edl_final_duration: float,
    qa_windows: Optional[Sequence[Dict[str, Any]]],
    strict: bool,
    stages: List[Dict[str, Any]],
    transcription_info: Dict[str, Any],
    transcription_origin: str,
    analysis: Dict[str, Any],
    semantic_result: Dict[str, Any],
    consent_obj: SemanticConsent,
    semantic_plan: Dict[str, Any],
    hashes_before: Dict[str, str],
    src: Path,
    brutos_sha: str,
    lint_report: Dict[str, Any],
    transcricao_injetada: Optional[List[Dict[str, Any]]],
    user_brief: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Executa as etapas 04_RENDER, 04_QA e 04_TRACE.

    Recebe todos os dados necessários (EDL, plano editorial, profile da marca,
    caminhos, hashes pré-pipeline, metadados de transcrição/semântica) e
    devolve o dicionário de resultado completo. Não modifica transcript.json,
    alignment.json, semantic_plan.json ou briefing.
    """
    t_start_render = time.perf_counter()
    target_fmt = edl.get("target_format") or {}
    res_cfg = target_fmt.get("resolution") or [TARGET_W, TARGET_H]
    target_w = int(res_cfg[0]) if len(res_cfg) >= 2 else TARGET_W
    target_h = int(res_cfg[1]) if len(res_cfg) >= 2 else TARGET_H
    target_fps = int(target_fmt.get("fps") or TARGET_FPS)
    aspect_ratio = target_fmt.get("aspect_ratio") or ("9:16" if target_h > target_w else "16:9")

    # ------------------------------------------------------------------
    # 04_RENDER (L1..L6 + loudnorm unico)
    # ------------------------------------------------------------------
    t = time.perf_counter()
    master_path = renders_dir / "master_16x9.mp4"
    authorized_roots = [fonte_dir, branding_dir, ep_dir, wd]
    render_report = render_edl_to_video(
        edl,
        editorial_plan,
        brutos_path,
        brand_profile,
        master_path,
        work_dir=wd,
        strict=True,
        authorized_roots=authorized_roots,
        apply_loudnorm=True,
    )
    if not master_path.is_file() or master_path.stat().st_size <= 0:
        raise PipelineError(f"master nao gerado: {master_path}")

    render_duration_exact = float(
        (render_report.get("target_format") or {}).get("expected_duration_seconds")
        or render_duration
    )

    filter_path = wd / "_edl_filter.txt"
    filtergraph_text = (
        filter_path.read_text(encoding="utf-8", errors="replace")
        if filter_path.is_file()
        else None
    )
    stages.append(
        {
            "stage": "04_RENDER",
            "status": "completed",
            "duration_seconds": round(time.perf_counter() - t, 3),
            "artifacts": [str(master_path)],
            "executed_events": len(render_report.get("executed_events", [])),
            "isolated_events": len(render_report.get("isolated_events", [])),
            "render_expected_duration_seconds": render_duration_exact,
            "loudnorm_stage": True,
        }
    )

    # ------------------------------------------------------------------
    # 04_QA (video_verify)
    # ------------------------------------------------------------------
    t = time.perf_counter()
    if qa_windows is None:
        executed_ids = {
            str(e.get("element_id"))
            for e in render_report.get("executed_events", [])
            if e.get("element_id")
        }
        windows = derive_qa_windows(
            editorial_plan,
            render_duration_exact,
            executed_element_ids=executed_ids if executed_ids else None,
        )
    else:
        windows = [dict(w) for w in qa_windows]
    qa_report = verify_video_av(
        master_path,
        render_duration_exact,
        qa_windows=windows,
        expected_width=target_w,
        expected_height=target_h,
        filtergraph_text=filtergraph_text,
        work_dir=qa_dir,
    )
    stages.append(
        {
            "stage": "04_QA",
            "status": "completed",
            "duration_seconds": round(time.perf_counter() - t, 3),
            "artifacts": [],
            "ok": bool(qa_report.get("ok")),
            "problems": len(qa_report.get("problems", [])),
            "qa_windows": len(windows),
        }
    )

    # ------------------------------------------------------------------
    # Integridade pos-pipeline (Delta-Hash = 0)
    # ------------------------------------------------------------------
    integrity: List[Dict[str, Any]] = []
    hashes_after = _collect_asset_hashes([fonte_dir, branding_dir, ep_dir])
    tracked = set(hashes_before.keys()) | set(hashes_after.keys())
    src_resolved = str(src.resolve())
    brutos_resolved = str(brutos_path.resolve())
    if src_resolved not in tracked:
        tracked.add(src_resolved)
    if brutos_resolved not in tracked:
        tracked.add(brutos_resolved)
    for path_str in sorted(tracked):
        before = hashes_before.get(path_str)
        after = hashes_after.get(path_str)
        if after is None and Path(path_str).is_file():
            after = sha256_file(path_str)
        if before is None and Path(path_str).is_file():
            before = sha256_file(path_str)
        p = Path(path_str)
        if path_str == brutos_resolved:
            role = "brutos_copy"
            before = before or brutos_sha
        elif path_str == src_resolved:
            role = "source_input"
        elif p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
            role = "broll_or_image"
        elif p.suffix.lower() in {".wav", ".mp3", ".flac", ".aac", ".m4a", ".ogg"}:
            role = "sfx_or_audio"
        else:
            role = "media"
        integrity.append(
            {
                "role": role,
                "path": path_str,
                "sha256_before": before,
                "sha256_after": after,
                "delta_hash": 0 if before == after else 1,
            }
        )
    delta_hash_zero = all(item["delta_hash"] == 0 for item in integrity)

    # ------------------------------------------------------------------
    # Traceability report
    # ------------------------------------------------------------------
    trace = {
        "schema_version": PIPELINE_SCHEMA_VERSION,
        "pipeline_version": PIPELINE_VERSION,
        "generated_at": _iso_now(),
        "identification": {
            "marca_id": marca_id,
            "episodio_id": episodio_id,
            "workspace_root": str(root),
            "master_path": str(master_path),
            "master_sha256": sha256_file(master_path),
            "target_format": {
                "width": target_w,
                "height": target_h,
                "aspect_ratio": aspect_ratio,
                "fps": target_fps,
                "audio_sample_rate": AUDIO_SR,
            },
            "render_expected_duration_seconds": render_duration_exact,
            "edl_final_duration_seconds": edl_final_duration,
            "duration_note": (
                "O master cobre a soma das duracoes raw dos segmentos; o eixo "
                "out_* do plano inclui padding de seguranca e pode ser maior."
            ),
        },
        "user_brief": user_brief or {},
        "stages": stages,
        "transcription": {
            "origin": transcription_origin,
            "engine": transcription_info.get("engine"),
            "model_identifier": transcription_info.get("model_identifier"),
            "model_revision": transcription_info.get("model_revision"),
            "model_path_kind": transcription_info.get("model_path_kind"),
            "local_execution_confirmed": bool(
                transcription_info.get("local_execution_confirmed")
            ),
            "local_files_only": bool(transcription_info.get("local_files_only")),
            "offline_only": bool(transcription_info.get("offline_only")),
            "language": transcription_info.get("language")
            or analysis.get("language"),
            "duration_seconds": transcription_info.get("duration_seconds"),
            "total_words": transcription_info.get("total_words"),
            "analysis_state": transcription_info.get(
                "analysis_state", "02_ANALYZE_COMPLETED"
            ),
            "external_calls": False,
            "editorial_transcript_source": analysis.get(
                "editorial_transcript_source"
            ),
            "editorial_transcript_sha256": analysis.get(
                "editorial_transcript_sha256"
            ),
            "editorial_base_transcript_sha256": analysis.get(
                "editorial_base_transcript_sha256"
            ),
        },
        "data_origin": {
            "source": (
                "synthetic_fixture"
                if transcricao_injetada is not None
                or transcription_origin == "injected_fixture"
                else "real_recording"
            ),
            "transcription": transcription_origin,
            "origins": {
                "transcription": transcription_origin,
                "semantic_plan": (
                    "fallback_local" if semantic_result.get("fallback")
                    else "provider"
                ),
                "external_provider": "blocked_offline",
            },
            "semantic_plan": (
                "fallback_local" if semantic_result.get("fallback")
                else "provider"
            ),
            "semantic_provider": semantic_result.get("provider"),
            "consent": consent_obj.to_dict(),
            "external_calls": False,
            "deterministic_offline": True,
        },
        "integrity": {
            "delta_hash_zero": delta_hash_zero,
            "media": integrity,
        },
        "edl": {
            "schema_version": edl.get("schema_version"),
            "planning_mode": edl.get("planning_mode"),
            "summary": edl.get("summary", {}),
            "parameters": edl.get("parameters", {}),
            "events": _timeline_events(edl),
            "removed_segments": edl.get("removed_segments", []),
        },
        "execution": {
            "executed_events": render_report.get("executed_events", []),
            "isolated_events": render_report.get("isolated_events", []),
            "executed_count": len(render_report.get("executed_events", [])),
            "isolated_count": len(render_report.get("isolated_events", [])),
        },
        "trace_paths": build_trace_paths(editorial_plan, edl, render_duration),
        "cadence_metrics": lint_report.get("cadence_metrics", {}),
        "lint": {
            "ok": bool(lint_report.get("ok")),
            "failures": lint_report.get("failures", []),
            "warnings": lint_report.get("warnings", []),
            "auto_approved": lint_report.get("auto_approved"),
            "requires_human_approval": lint_report.get(
                "requires_human_approval"
            ),
        },
        "qa": {
            "ok": bool(qa_report.get("ok")),
            "windows": windows,
            **qa_report,
        },
        "limitations": [
            "Loudness do master: medicao em 2 passes + exatamente 1 filtro "
            "loudnorm no filtergraph final (alimiter antes, linear=true).",
            "Sem transcricao_injetada, a transcricao e local/offline "
            "(local_faster_whisper, local_files_only=True). Downloads e "
            "provedores externos de transcricao ficam bloqueados.",
            "B-roll e SFX sao resolvidos apenas dentro das raizes autorizadas; "
            "referencias invalidas sao isoladas, nunca carregadas.",
            "O master renderizado usa a soma das duracoes raw; o eixo out_* do "
            "plano inclui padding de seguranca.",
            "Aprovacao humana continua obrigatoria: o pipeline nao aprova "
            "automaticamente o master.",
        ],
    }

    traceability_path = renders_dir / "traceability_report.json"
    with open(traceability_path, "w", encoding="utf-8") as f:
        json.dump(trace, f, indent=2, ensure_ascii=False)

    # ------------------------------------------------------------------
    # project.json
    # ------------------------------------------------------------------
    projeto = loader.load_project(marca_id, episodio_id)
    projeto["current_stage"] = "04_RENDER_COMPLETED"
    projeto["status"] = (
        "MASTER_RENDERED" if qa_report.get("ok") else "MASTER_QA_FAILED"
    )
    projeto["updated_at"] = _iso_now()
    projeto.setdefault("artifacts", {})
    projeto["artifacts"]["04_render"] = {
        "master_16x9": "workspace/renders/master_16x9.mp4",
        "traceability_report": "workspace/renders/traceability_report.json",
    }
    projeto.setdefault("approvals", {})
    # Re-render invalida qualquer aprovacao anterior do master 16:9.
    projeto["approvals"]["master_16x9_approved"] = False
    projeto["approvals"]["master_16x9_sha256"] = None
    projeto["approvals"]["master_16x9_path"] = None
    projeto["approvals"]["master_16x9_approved_by"] = None
    projeto["approvals"]["master_16x9_approved_at"] = None
    projeto["approvals"].pop(
        "master_16x9_approval_invalidated_reason", None
    )
    projeto["telemetry"] = {
        **(projeto.get("telemetry") or {}),
        "pipeline_total_wallclock_seconds": round(
            time.perf_counter() - t_start_render, 3
        ),
    }
    _gravar_projeto(loader, marca_id, episodio_id, projeto)

    result: Dict[str, Any] = {
        "ok": bool(qa_report.get("ok")) and delta_hash_zero,
        "marca_id": marca_id,
        "episodio_id": episodio_id,
        "workspace_root": str(root),
        "master_path": str(master_path),
        "master_sha256": trace["identification"]["master_sha256"],
        "traceability_path": str(traceability_path),
        "render_expected_duration_seconds": render_duration_exact,
        "edl_final_duration_seconds": edl_final_duration,
        "target_format": trace["identification"]["target_format"],
        "user_brief": user_brief or {},
        "stages": stages,
        "analysis": analysis,
        "transcription": transcription_info,
        "semantic_plan": semantic_plan,
        "semantic_result": {
            "provider": semantic_result.get("provider"),
            "fallback": bool(semantic_result.get("fallback")),
            "validated": bool(semantic_result.get("validated")),
        },
        "edl": edl,
        "editorial_plan": editorial_plan,
        "lint": lint_report,
        "render": render_report,
        "qa": qa_report,
        "traceability": trace,
        "integrity_delta_hash_zero": delta_hash_zero,
        "qa_windows": windows,
        "total_wallclock_seconds": round(time.perf_counter() - t_start_render, 3),
    }

    if strict and not qa_report.get("ok"):
        raise PipelineQAError(
            "QA audiovisual reprovou o master: "
            + "; ".join(qa_report.get("problems", [])[:6]),
            result,
        )
    if not delta_hash_zero:
        raise PipelineError(
            "Delta-Hash != 0 em midias originais apos o pipeline."
        )

    return result


# ---------------------------------------------------------------------------
# Pipeline principal
# ---------------------------------------------------------------------------


def run_episode_pipeline(
    workspace_root: str | Path,
    marca_id: str,
    episodio_id: str,
    *,
    source_video: Optional[str | Path] = None,
    transcricao_injetada: Optional[List[Dict[str, Any]]] = None,
    semantic_provider: Optional[Any] = None,
    consent: Optional[SemanticConsent] = None,
    strict: bool = True,
    work_dir: Optional[str | Path] = None,
    qa_windows: Optional[Sequence[Dict[str, Any]]] = None,
    whisper_model_path: Optional[str | Path] = None,
    offline_only: bool = True,
    ensure_motion_layers: bool = False,
) -> Dict[str, Any]:
    """Executa o pipeline completo L1..L6 de um episodio.

    Parameters
    ----------
    workspace_root:
        Raiz do workspace (contem `workspace.json` e `projetos/`).
    marca_id, episodio_id:
        Slugs validados pelo WorkspaceLoader (path traversal -> WorkspaceError).
    source_video:
        Arquivo original a ingerir. Quando omitido, usa a source registrada no
        `project.json` (ou o primeiro arquivo de midia em `brutos/`).
    transcricao_injetada:
        Lista explicita de palavras ({w,t,f,probability}). Quando informada,
        nenhum modelo Whisper e executado (origem `injected_fixture`).
        Quando omitida, a transcricao real e feita localmente, offline, com
        faster-whisper (`local_faster_whisper`).
    whisper_model_path:
        Diretorio do snapshot local do faster-whisper. Se omitido, usa
        EDITOR_WHISPER_MODEL_PATH. Obrigatorio quando nao ha transcricao
        injetada (modo offline; sem download).
    offline_only:
        Default True: proibe download de modelo e provedores externos de
        transcricao. `external_provider` fica bloqueado nesta fase.
    semantic_provider:
        Provedor de semantic_plan (ex.: CallableMockProvider).
    consent:
        SemanticConsent. Sem consentimento autorizado, o plano e fallback local
        e o provedor NAO e chamado.
    strict:
        Quando True, QA reprovado levanta PipelineQAError apos gravar o
        relatorio de rastreabilidade. Falhas de lint sempre bloqueiam o render.
    work_dir:
        Diretorio de trabalho do render/QA (default: workspace/renders/_work).
    qa_windows:
        Janelas de QA explicitas. Quando omitidas, sao derivadas do plano.
    """
    t_start = time.perf_counter()
    root = Path(workspace_root).resolve()

    loader = WorkspaceLoader(root)
    loader.load_workspace()

    # Slugs e marca (path traversal -> WorkspaceError).
    brand_profile = loader.load_brand_profile(marca_id)
    ep_dir = loader.episodio_dir(marca_id, episodio_id)

    fonte_dir = loader.resolve_episodio_asset(marca_id, episodio_id, "workspace/fonte")
    briefing_dir = loader.resolve_episodio_asset(marca_id, episodio_id, "workspace/briefing")
    renders_dir = loader.resolve_episodio_asset(marca_id, episodio_id, "workspace/renders")
    branding_dir = loader.branding_dir(marca_id)

    fonte_dir.mkdir(parents=True, exist_ok=True)
    briefing_dir.mkdir(parents=True, exist_ok=True)
    renders_dir.mkdir(parents=True, exist_ok=True)
    wd = Path(work_dir).resolve() if work_dir else (renders_dir / "_work")
    wd.mkdir(parents=True, exist_ok=True)
    qa_dir = renders_dir / "_qa"
    qa_dir.mkdir(parents=True, exist_ok=True)

    stages: List[Dict[str, Any]] = []

    def _record(stage: str, started: float, artifacts: Optional[List[str]] = None, **extra: Any) -> None:
        entry: Dict[str, Any] = {
            "stage": stage,
            "status": "completed",
            "duration_seconds": round(time.perf_counter() - started, 3),
            "artifacts": artifacts or [],
        }
        entry.update(extra)
        stages.append(entry)

    # ------------------------------------------------------------------
    # Determinacao da fonte
    # ------------------------------------------------------------------
    project_path = loader.project_file(marca_id, episodio_id)
    existing_project: Optional[Dict[str, Any]] = None
    if project_path.is_file():
        existing_project = loader.load_project(marca_id, episodio_id)

    if source_video is not None:
        src = Path(source_video).resolve()
    else:
        src = None
        if existing_project:
            sources = existing_project.get("sources", []) or []
            if sources and sources[0].get("path"):
                cand = Path(sources[0]["path"])
                if cand.is_file():
                    src = cand.resolve()
        if src is None:
            brutos_dir = loader.resolve_episodio_asset(marca_id, episodio_id, "brutos")
            if brutos_dir.is_dir():
                for p in sorted(brutos_dir.iterdir()):
                    if p.is_file() and p.suffix.lower() in MEDIA_EXT:
                        src = p.resolve()
                        break
        if src is None:
            raise PipelineError(
                "source_video nao informado e nenhuma source valida encontrada "
                f"em brutos/ para {marca_id}/{episodio_id}."
            )

    if not src.is_file() or src.stat().st_size <= 0:
        raise PipelineError(f"source_video inexistente ou vazio: {src}")

    # Hashes ANTES do pipeline (video de entrada + assets de midia do episodio).
    hashes_before: Dict[str, str] = {str(src): sha256_file(src)}
    hashes_before.update(_collect_asset_hashes([fonte_dir, branding_dir, ep_dir]))

    # ------------------------------------------------------------------
    # 01_INGEST
    # ------------------------------------------------------------------
    t = time.perf_counter()
    rc = ingest_media(str(src), marca_id, episodio_id, root)
    if rc != 0:
        raise PipelineError(f"ingest_media falhou (rc={rc}) para {src}")
    project = loader.load_project(marca_id, episodio_id)
    sources = project.get("sources", []) or []
    if not sources or not sources[0].get("path"):
        raise PipelineError("project.json sem source registrada apos ingestao.")
    brutos_path = Path(sources[0]["path"])
    brutos_sha = sha256_file(brutos_path)
    source_sha = hashes_before[str(src)]
    if brutos_sha != source_sha:
        raise PipelineError(
            "Delta-Hash != 0 na ingestao: "
            f"origem={source_sha} brutos={brutos_sha}"
        )
    _record(
        "01_INGEST",
        t,
        artifacts=[str(brutos_path), str(fonte_dir / "audio_speech_16k_mono.wav")],
        source_sha256=source_sha,
        brutos_sha256=brutos_sha,
        delta_hash=0,
    )

    # ------------------------------------------------------------------
    # 02_ANALYZE
    # ------------------------------------------------------------------
    t = time.perf_counter()
    analysis = analyze_episodio(
        marca_id,
        episodio_id,
        root,
        transcricao_injetada=transcricao_injetada,
        whisper_model_path=whisper_model_path,
        offline_only=offline_only,
    )
    transcription_info = analysis.get("transcription") or {}
    transcription_origin = transcription_info.get(
        "origin",
        "injected_fixture" if transcricao_injetada is not None else "local_faster_whisper",
    )
    alignment_path = fonte_dir / "alignment.json"
    if not alignment_path.is_file():
        raise PipelineError(f"alignment.json nao gerado: {alignment_path}")
    _record(
        "02_ANALYZE",
        t,
        artifacts=[
            str(fonte_dir / "transcript.json"),
            str(alignment_path),
            str(fonte_dir / "phonetic_report.json"),
        ],
        transcription_origin=transcription_origin,
        local_execution_confirmed=bool(transcription_info.get("local_execution_confirmed")),
        local_files_only=bool(transcription_info.get("local_files_only")),
        offline_only=bool(transcription_info.get("offline_only", offline_only)),
        editorial_transcript_source=analysis.get("editorial_transcript_source"),
        editorial_transcript_sha256=analysis.get("editorial_transcript_sha256"),
        editorial_base_transcript_sha256=analysis.get("editorial_base_transcript_sha256"),
    )

    # Carrega user_brief.json se existir e aplica correcoes ortograficas iniciais
    user_brief = load_user_brief(briefing_dir)
    if user_brief.get("correcoes_ortograficas") and not (fonte_dir / "transcript_reviewed.json").is_file():
        review_transcript(
            fonte_dir / "transcript.json",
            user_brief["correcoes_ortograficas"],
            reviewed_by="user_brief",
            reviewed_version="1.0.0",
        )
        sync_res = sync_alignment_with_editorial_transcript(fonte_dir)
        analysis["editorial_transcript_source"] = sync_res.get("source_kind")
        analysis["editorial_transcript_sha256"] = sync_res.get("transcript_sha256")
        analysis["editorial_base_transcript_sha256"] = sync_res.get("base_transcript_sha256")

    # ------------------------------------------------------------------
    # 03_SEMANTIC
    # ------------------------------------------------------------------
    t = time.perf_counter()
    consent_obj = consent or SemanticConsent(
        destination="local_semantic_planner",
        shared_data=["transcript.json", "alignment.json", "phonetic_report.json"],
        authorized=False,
        notes="Sem consentimento explicito: fallback local.",
    )
    try:
        semantic_result = plan_episodio_semantics(
            marca_id=marca_id,
            episodio_id=episodio_id,
            workspace_root=root,
            provider=semantic_provider,
            authorized=bool(consent_obj.authorized),
            destination=consent_obj.destination,
            shared_data=list(consent_obj.shared_data),
            consent_notes=consent_obj.notes,
        )
    except SemanticPlannerError as exc:
        raise PipelineError(f"semantic_planner falhou: {exc}") from exc

    if not semantic_result.get("validated") or not semantic_result.get("plan"):
        raise PipelineError(
            "semantic_plan invalido: "
            f"{semantic_result.get('validation_error') or semantic_result.get('error')}"
        )
    semantic_plan = semantic_result["plan"]
    semantic_plan_path = briefing_dir / "semantic_plan.json"
    _record(
        "03_SEMANTIC",
        t,
        artifacts=[str(semantic_plan_path), str(briefing_dir / "semantic_consent.json")],
        provider=semantic_result.get("provider"),
        fallback=bool(semantic_result.get("fallback")),
        authorized=bool(consent_obj.authorized),
        consent=consent_obj.to_dict(),
    )

    # ------------------------------------------------------------------
    # 03_BRIEFING
    # ------------------------------------------------------------------
    t = time.perf_counter()
    rc = gerar_briefing(
        marca_id,
        episodio_id,
        root,
        marca_profile=brand_profile,
        semantic_plan_path=semantic_plan_path,
    )
    if rc != 0:
        raise PipelineError(f"gerar_briefing falhou (rc={rc})")
    _record(
        "03_BRIEFING",
        t,
        artifacts=[
            str(briefing_dir / "briefing.json"),
            str(briefing_dir / "BRIEFING.md"),
        ],
    )

    # ------------------------------------------------------------------
    # 03_EDL (jump cuts) + RhythmEngine
    # ------------------------------------------------------------------
    t = time.perf_counter()
    should_ensure_motion = ensure_motion_layers or bool(user_brief.get("pedido_usuario"))
    edl, editorial_plan = build_edl_from_alignment(
        alignment_path=alignment_path,
        workspace_root=root,
        marca_id=marca_id,
        episodio_id=episodio_id,
        brand_profile=brand_profile,
        semantic_plan_path=semantic_plan_path,
        ensure_motion_layers=should_ensure_motion,
    )
    edl_final_duration = float(
        edl.get("summary", {}).get("final_duration_seconds", 0.0)
    )
    render_duration = expected_render_duration(edl)
    _record(
        "03_EDL",
        t,
        artifacts=[
            str(briefing_dir / "edl_longo.json"),
            str(briefing_dir / "editorial_plan.json"),
        ],
        timeline_events=len(_timeline_events(edl)),
        edl_final_duration_seconds=edl_final_duration,
        render_expected_duration_seconds=render_duration,
    )

    # ------------------------------------------------------------------
    # 03_LINT (gate bloqueante)
    # ------------------------------------------------------------------
    t = time.perf_counter()
    lint_report = lint_plan(editorial_plan, edl, project)
    if not lint_report.get("ok"):
        raise PipelineError(
            "MasterLint bloqueou o render: " + "; ".join(lint_report.get("failures", [])[:8])
        )
    _record(
        "03_LINT",
        t,
        artifacts=[],
        failures=[],
        warnings=len(lint_report.get("warnings", [])),
    )

    # ------------------------------------------------------------------
    # 04_RENDER / 04_QA / 04_TRACE (helper compartilhado)
    # ------------------------------------------------------------------
    return _executar_render_qa_trace(
        root=root,
        loader=loader,
        marca_id=marca_id,
        episodio_id=episodio_id,
        edl=edl,
        editorial_plan=editorial_plan,
        brand_profile=brand_profile,
        brutos_path=brutos_path,
        fonte_dir=fonte_dir,
        branding_dir=branding_dir,
        ep_dir=ep_dir,
        renders_dir=renders_dir,
        wd=wd,
        qa_dir=qa_dir,
        render_duration=render_duration,
        edl_final_duration=edl_final_duration,
        qa_windows=qa_windows,
        strict=strict,
        stages=stages,
        transcription_info=transcription_info,
        transcription_origin=transcription_origin,
        analysis=analysis,
        semantic_result=semantic_result,
        consent_obj=consent_obj,
        semantic_plan=semantic_plan,
        hashes_before=hashes_before,
        src=src,
        brutos_sha=brutos_sha,
        lint_report=lint_report,
        transcricao_injetada=transcricao_injetada,
        user_brief=user_brief,
    )


# ---------------------------------------------------------------------------
# render_existing_episode
# Re-rende um episodio ja processado (que ja possui EDL/editorial_plan/
# alignment gerados), repetindo apenas as etapas 04_RENDER/04_QA/04_TRACE.
# Nao reexecuta ingestao, analise, planejamento semantico, briefing ou EDL.
# ---------------------------------------------------------------------------


def render_existing_episode(
    workspace_root: str | Path,
    marca_id: str,
    episodio_id: str,
    *,
    qa_windows: Optional[Sequence[Dict[str, Any]]] = None,
    strict: bool = True,
) -> Dict[str, Any]:
    """Re-rende o master 16:9 de um episodio ja processado.

    Nao reexecuta ingestao, analise, planejamento semantico, briefing nem
    EDL: utiliza os artefatos existentes em workspace/fonte/ e
    workspace/briefing/. Repete apenas as etapas 04_RENDER, 04_QA e 04_TRACE.

    Levanta PipelineError se nao houver EDL/editorial_plan existentes.
    """
    root = Path(workspace_root).resolve()
    loader = WorkspaceLoader(root)
    loader.load_workspace()

    # Valida marca/episodio (path traversal -> WorkspaceError).
    brand_profile = loader.load_brand_profile(marca_id)
    ep_dir = loader.episodio_dir(marca_id, episodio_id)

    fonte_dir = loader.resolve_episodio_asset(marca_id, episodio_id, "workspace/fonte")
    briefing_dir = loader.resolve_episodio_asset(
        marca_id, episodio_id, "workspace/briefing"
    )
    renders_dir = loader.resolve_episodio_asset(
        marca_id, episodio_id, "workspace/renders"
    )
    branding_dir = loader.branding_dir(marca_id)

    fonte_dir.mkdir(parents=True, exist_ok=True)
    briefing_dir.mkdir(parents=True, exist_ok=True)
    renders_dir.mkdir(parents=True, exist_ok=True)

    # Carrega project.json existente para obter source/brutos.
    projeto = loader.load_project(marca_id, episodio_id)
    sources = projeto.get("sources", []) or []
    if not sources or not sources[0].get("path"):
        raise PipelineError(
            "project.json sem source registrada para "
            f"{marca_id}/{episodio_id}. Rode a ingestao primeiro."
        )
    brutos_path = Path(sources[0]["path"]).resolve()
    if not brutos_path.is_file():
        raise PipelineError(f"Arquivo em brutos nao encontrado: {brutos_path}")
    brutos_sha = sha256_file(brutos_path)

    # ---- (a) Validar integridade do bruto sem reingerir (Delta-Hash == 0) ----
    expected_sha = sources[0].get("sha256")
    verify_source_integrity(brutos_path, expected_sha, brutos_path.name)

    # Carrega EDL e editorial_plan existentes.
    edl_path = briefing_dir / "edl_longo.json"
    editorial_plan_path = briefing_dir / "editorial_plan.json"
    if not edl_path.is_file():
        raise PipelineError(f"edl_longo.json nao encontrado: {edl_path}. Rode o pipeline primeiro.")
    if not editorial_plan_path.is_file():
        raise PipelineError(f"editorial_plan.json nao encontrado: {editorial_plan_path}. Rode o pipeline primeiro.")

    # ---- (c) Exigir que todos os artefatos JSON existam e sejam validos ----
    obrigatorios = {
        "transcript.json": fonte_dir / "transcript.json",
        "alignment.json": fonte_dir / "alignment.json",
        "semantic_plan.json": briefing_dir / "semantic_plan.json",
        "semantic_consent.json": briefing_dir / "semantic_consent.json",
        "briefing.json": briefing_dir / "briefing.json",
        "edl_longo.json": edl_path,
        "editorial_plan.json": editorial_plan_path,
    }
    artefatos: Dict[str, Any] = {}
    for nome, caminho in obrigatorios.items():
        if not caminho.is_file():
            raise PipelineError(
                f"Arquivo obrigatorio ausente para re-render: {nome} ({caminho})"
            )
        try:
            artefatos[nome] = json.loads(caminho.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise PipelineError(
                f"JSON invalido no arquivo obrigatorio {nome} ({caminho}): {exc}"
            ) from exc

    # Verifica compatibilidade marca_id/episodio_id nos artefatos-chave.
    projeto_id = artefatos.get("project.json") if "project.json" in artefatos else None
    semantic_plan = artefatos["semantic_plan.json"]
    if isinstance(semantic_plan, dict):
        if semantic_plan.get("marca_id") not in (None, marca_id):
            raise PipelineError(
                f"semantic_plan.json incompatível com marca_id: "
                f"{semantic_plan.get('marca_id')} != {marca_id}"
            )
        if semantic_plan.get("episodio_id") not in (None, episodio_id):
            raise PipelineError(
                f"semantic_plan.json incompatível com episodio_id: "
                f"{semantic_plan.get('episodio_id')} != {episodio_id}"
            )

    with open(edl_path, "r", encoding="utf-8") as f:
        edl = json.load(f)
    with open(editorial_plan_path, "r", encoding="utf-8") as f:
        editorial_plan = json.load(f)

    # Carrega alignment existente (para referencia na trace/analise).
    alignment_path = fonte_dir / "alignment.json"
    analysis: Dict[str, Any] = {}
    analysis = json.loads(alignment_path.read_text(encoding="utf-8"))

    # Carrega transcript existente para metadados de transcricao.
    transcript_path = fonte_dir / "transcript.json"
    transcription_info: Dict[str, Any] = {}
    transcription_origin = "raw_transcript"
    transcript_data = json.loads(
        transcript_path.read_text(encoding="utf-8", errors="replace")
    )
    transcription_info = transcript_data.get("transcription", {}) or {}
    transcription_origin = transcription_info.get(
        "origin", "raw_transcript"
    )
    analysis["language"] = transcript_data.get("language")

    # ---- (b) Validar revisao editorial via resolve_editorial_transcript ----
    editorial = resolve_editorial_transcript(fonte_dir)
    analysis["editorial_transcript_source"] = editorial["source_kind"]
    analysis["editorial_transcript_sha256"] = editorial["transcript_sha256"]
    analysis["editorial_base_transcript_sha256"] = editorial.get(
        "base_transcript_sha256"
    )

    # ---- (d) Preservar semantic_provider e fallback a partir dos arquivos ----
    semantic_plan_path = briefing_dir / "semantic_plan.json"
    semantic_result: Dict[str, Any] = {
        "provider": "existing",
        "fallback": False,
        "validated": True,
    }
    if semantic_plan_path.is_file():
        try:
            semantic_plan = json.loads(
                semantic_plan_path.read_text(encoding="utf-8")
            )
            semantic_result["validated"] = True
        except json.JSONDecodeError:
            semantic_plan = {}

    provider = semantic_plan.get("provider") or "fallback_local"
    fallback = bool(
        semantic_plan.get("fallback", provider == "fallback_local")
    )
    semantic_result["provider"] = provider
    semantic_result["fallback"] = fallback

    # Carrega consent de semantic_consent.json.
    consent_obj = SemanticConsent(
        destination="local_semantic_planner",
        shared_data=["transcript.json", "alignment.json", "phonetic_report.json"],
        authorized=False,
        notes="Re-render de episodio existente (sem provedor externo).",
    )
    consent_path = briefing_dir / "semantic_consent.json"
    if consent_path.is_file():
        try:
            consent_data = json.loads(consent_path.read_text(encoding="utf-8"))
            if isinstance(consent_data, dict):
                consent_obj = SemanticConsent(
                    destination=consent_data.get(
                        "destination", "local_semantic_planner"
                    ),
                    shared_data=list(consent_data.get("shared_data", [])),
                    authorized=bool(consent_data.get("authorized", False)),
                    notes=consent_data.get(
                        "notes", "Consent carregado de semantic_consent.json."
                    ),
                )
        except json.JSONDecodeError:
            pass

    # Executa lint no plano existente para validacao antes do render.
    from .master_lint import lint as lint_plan  # type: ignore

    lint_report = lint_plan(editorial_plan, edl, projeto)
    if not lint_report.get("ok"):
        raise PipelineError(
            "MasterLint bloqueou o render: "
            + "; ".join(lint_report.get("failures", [])[:8])
        )

    # Hashes antes (para Delta-Hash = 0).
    hashes_before: Dict[str, str] = {str(brutos_path): brutos_sha}
    hashes_before.update(
        _collect_asset_hashes([fonte_dir, branding_dir, ep_dir])
    )

    # Diretorios de trabalho.
    wd = renders_dir / "_work"
    wd.mkdir(parents=True, exist_ok=True)
    qa_dir = renders_dir / "_qa"
    qa_dir.mkdir(parents=True, exist_ok=True)

    stages: List[Dict[str, Any]] = []

    # Duracoes.
    user_brief = load_user_brief(briefing_dir)
    render_duration = expected_render_duration(edl)
    edl_final_duration = float(
        edl.get("summary", {}).get("final_duration_seconds", 0.0)
    )

    return _executar_render_qa_trace(
        root=root,
        loader=loader,
        marca_id=marca_id,
        episodio_id=episodio_id,
        edl=edl,
        editorial_plan=editorial_plan,
        brand_profile=brand_profile,
        brutos_path=brutos_path,
        fonte_dir=fonte_dir,
        branding_dir=branding_dir,
        ep_dir=ep_dir,
        renders_dir=renders_dir,
        wd=wd,
        qa_dir=qa_dir,
        render_duration=render_duration,
        edl_final_duration=edl_final_duration,
        qa_windows=qa_windows,
        strict=strict,
        stages=stages,
        transcription_info=transcription_info,
        transcription_origin=transcription_origin,
        analysis=analysis,
        semantic_result=semantic_result,
        consent_obj=consent_obj,
        semantic_plan=semantic_plan,
        hashes_before=hashes_before,
        src=brutos_path,
        brutos_sha=brutos_sha,
        lint_report=lint_report,
        transcricao_injetada=None,
        user_brief=user_brief,
    )
