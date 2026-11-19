"""
core/edl_builder.py

Construtor de EDL (Edit Decision List) longa 16:9 adaptado de
Editor legado/core/edl_builder.py para o Workspace Core e a estrutura
canônica do legado (projetos/<marca>/episodios/<episodio>/workspace/briefing/).

Constrói workspace/briefing/edl_longo.json (EDL não destrutiva do master 16:9)
com:
  - source_ref {id, path, sha256} referenciando o arquivo em brutos/
  - raw_in/raw_out (pontos na fonte original)
  - out_in/out_out (eixo da linha de tempo montada)
  - operation, justification
  - audio_treatment
  - motion_hints
  - narrative_continuity {topic_id, explanation_group_id, preserves_context}

E workspace/briefing/editorial_plan.json (6 camadas L1..L6 coerentes com o EDL),
atualizando project.json (artifacts['03_briefing'],
current_stage='03_BRIEFING_COMPLETED', sem aprovar automaticamente).

Não destrutivo: apenas metadados de edição. Não modifica o arquivo de origem.
Agnóstico a marca e episódio.
"""

from __future__ import annotations

import json
import logging
import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from .workspace import WorkspaceLoader, WorkspaceError
    from .semantic_plan import (
        IMPLEMENTED_MOTION_COMPONENTS,
        SemanticPlanError,
        load_semantic_plan,
    )
    from .semantic_planner import FILLER_WORDS
    from .transcript_review import resolve_editorial_transcript, TranscriptReviewError
    from .rhythm_engine import build_rhythm_layers, _elements, LAYERS_VISUAIS
    from .brand_bumpers import resolve_brand_asset_dirs, resolve_brand_bumper
except ImportError:  # execução direta como script
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from core.workspace import WorkspaceLoader, WorkspaceError  # type: ignore
    from core.semantic_plan import (  # type: ignore
        IMPLEMENTED_MOTION_COMPONENTS,
        SemanticPlanError,
        load_semantic_plan,
    )
    from core.semantic_planner import FILLER_WORDS  # type: ignore
    from core.transcript_review import resolve_editorial_transcript, TranscriptReviewError  # type: ignore
    from core.rhythm_engine import build_rhythm_layers, _elements, LAYERS_VISUAIS  # type: ignore
    from core.brand_bumpers import resolve_brand_asset_dirs, resolve_brand_bumper  # type: ignore

VOCAL_HESITATIONS = frozenset({"ééé", "éé", "eee", "ahn", "hum", "hã"})
CUT_ANTES_S = 0.08
CUT_DEPOIS_S = 0.20
CUT_FPS = 30


class EdlBuilderError(Exception):
    """Erro de construção da EDL."""


def r3(value: float) -> float:
    """Arredonda para milissegundos, evitando -0.0."""
    rounded = round(float(value) + 0.0, 3)
    return 0.0 if rounded == 0 else rounded


def _brand_get(profile: Dict[str, Any], *keys: str, default: Any = None) -> Any:
    """Busca uma seção no brand_profile.

    O perfil normalizado do WorkspaceLoader deixa a maioria dos dados dentro
    de ``config_json``.  Procura primeiro no nível superior e, não encontrando,
    tenta caminhos aninhados dentro de ``config_json`` (suportando notação com
    ponto, ex: "preferencias_edicao.audio").
    """
    for k in keys:
        if k in profile:
            return profile[k]
    config_json = profile.get("config_json", {})
    if isinstance(config_json, dict):
        for k in keys:
            partes = k.split(".")
            valor: Any = config_json
            encontrado = True
            for p in partes:
                if isinstance(valor, dict) and p in valor:
                    valor = valor[p]
                else:
                    encontrado = False
                    break
            if encontrado:
                return valor
    return default


def setup_logger(log_file: Path = None) -> logging.Logger:
    logger = logging.getLogger("CORE-EDL-BUILDER")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setFormatter(formatter)
        logger.addHandler(fh)
    return logger


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


# As 6 camadas do plano editorial (L1..L6), coerentes com o EDL.
CAMADAS_EDITORIAL = [
    "L1_estabelecimento",
    "L2_titulo_heroi_t10",
    "L3_micro_zoom_bate",
    "L4_lower_third",
    "L5_broll_industrial",
    "L5_fullscreen_motion",
    "L6_sound_design_sync",
]


def _empty_layers() -> Dict[str, List[Dict[str, Any]]]:
    return {camada: [] for camada in CAMADAS_EDITORIAL}


def _interval_overlap(a0: float, a1: float, b0: float, b1: float) -> float:
    return max(0.0, min(a1, b1) - max(a0, b0))


def _resolve_unit_decision(
    raw_start: float,
    raw_end: float,
    semantic_plan: Optional[Dict[str, Any]],
) -> Tuple[bool, str, str, str, str]:
    """Determina (preservar, operation, justification, topic_id, explanation_group_id)."""
    if semantic_plan is None:
        return (
            True,
            "jump_cut",
            "Fallback determinístico: unidade de fala preservada (aguardando análise semântica).",
            "T_UNCLASSIFIED",
            "E_UNCLASSIFIED",
        )

    unit_dur = max(0.001, raw_end - raw_start)

    # 1. Verifica decisoes explicitas em segmentos_editoriais
    for seg in semantic_plan.get("segmentos_editoriais", []):
        ov = _interval_overlap(raw_start, raw_end, float(seg["raw_start"]), float(seg["raw_end"]))
        if ov > 0.05 or (raw_start >= float(seg["raw_start"]) and raw_end <= float(seg["raw_end"])):
            dec = seg["decision"]
            if dec in ("remover_repeticao", "remover_falso_comeco", "remover_pausa", "candidato_remocao"):
                return (
                    False,
                    dec,
                    seg["justificativa"],
                    seg.get("topic_id") or "T_REMOVED",
                    seg.get("explanation_group_id") or "E_REMOVED",
                )

    # 1b. Verifica repeticoes_dispensaveis e falsos_comecos que cubram integralmente a unidade
    for list_key, op_name in (
        ("repeticoes_dispensaveis", "remover_repeticao"),
        ("falsos_comecos", "remover_falso_comeco"),
    ):
        for item in semantic_plan.get(list_key, []):
            i_start = float(item.get("raw_start", 0.0))
            i_end = float(item.get("raw_end", 0.0))
            ov = _interval_overlap(raw_start, raw_end, i_start, i_end)
            if (raw_start >= i_start - 0.05 and raw_end <= i_end + 0.05) or (ov >= 0.8 * unit_dur):
                return (
                    False,
                    op_name,
                    str(item.get("justificativa") or f"Removido ({op_name}) pelo plano semântico."),
                    "T_REMOVED",
                    "E_REMOVED",
                )

    # 2. Encontra grupo de explicacao que contenha ou sobreponha a unidade
    group_id = "E_GENERAL"
    topic_id = "T_GENERAL"
    best_grp_ov = 0.0
    for grp in semantic_plan.get("grupos_explicacao", []):
        ov = _interval_overlap(raw_start, raw_end, float(grp["raw_start"]), float(grp["raw_end"]))
        if ov > best_grp_ov:
            best_grp_ov = ov
            group_id = grp["explanation_group_id"]
            topic_id = grp["topic_id"]

    # 3. Se nao achou grupo, encontra topico correspondente (sem mudar de topico a cada pausa)
    if best_grp_ov == 0.0:
        best_top_ov = 0.0
        for top in semantic_plan.get("topicos", []):
            ov = _interval_overlap(raw_start, raw_end, float(top["raw_start"]), float(top["raw_end"]))
            if ov > best_top_ov:
                best_top_ov = ov
                topic_id = top["topic_id"]
                group_id = f"E_{topic_id}"

    return (
        True,
        "jump_cut",
        f"Preservado conforme plano semântico ({topic_id}/{group_id}).",
        topic_id,
        group_id,
    )


def _detect_target_format(
    projeto: Dict[str, Any],
    fonte_dir: Path,
) -> Dict[str, Any]:
    """Detecta resolucao e aspect ratio nativo a partir de project.json ou media_info.json."""
    vw, vh, fps_val = 0, 0, 30
    vid = ((projeto.get("media_info") or {}).get("video") or {})
    if isinstance(vid, dict):
        try:
            vw = int(vid.get("width") or 0)
            vh = int(vid.get("height") or 0)
            if vid.get("fps"):
                fps_val = max(1, int(round(float(vid["fps"]))))
        except (TypeError, ValueError):
            pass

    if vw <= 0 or vh <= 0:
        mi_path = fonte_dir / "media_info.json"
        if mi_path.is_file():
            try:
                mi = json.loads(mi_path.read_text(encoding="utf-8", errors="replace"))
                if isinstance(mi, dict):
                    if isinstance(mi.get("video"), dict):
                        vw = int(mi["video"].get("width") or 0)
                        vh = int(mi["video"].get("height") or 0)
                    elif isinstance(mi.get("streams"), list):
                        v0 = next((s for s in mi["streams"] if s.get("codec_type") == "video"), None)
                        if v0:
                            vw = int(v0.get("width") or 0)
                            vh = int(v0.get("height") or 0)
            except (json.JSONDecodeError, TypeError, ValueError):
                pass

    if vh > vw > 0:
        return {
            "resolution": [1080, 1920],
            "aspect_ratio": "9:16",
            "fps": fps_val,
            "audio_sample_rate": 48000,
            "audio_channels": 2,
        }
    return {
        "resolution": [1920, 1080],
        "aspect_ratio": "16:9",
        "fps": fps_val,
        "audio_sample_rate": 48000,
        "audio_channels": 2,
    }


def _collect_removal_windows(semantic_plan: Optional[Dict[str, Any]]) -> List[Tuple[float, float, str, str]]:
    """Coleta janelas intra-unidade a remover de repeticoes, falsos comecos e segmentos."""
    windows: List[Tuple[float, float, str, str]] = []
    if not semantic_plan:
        return windows
    for item in semantic_plan.get("repeticoes_dispensaveis", []):
        windows.append((
            float(item.get("raw_start", 0.0)),
            float(item.get("raw_end", 0.0)),
            "remover_repeticao",
            str(item.get("justificativa") or "Repeticao removida"),
        ))
    for item in semantic_plan.get("falsos_comecos", []):
        windows.append((
            float(item.get("raw_start", 0.0)),
            float(item.get("raw_end", 0.0)),
            "remover_falso_comeco",
            str(item.get("justificativa") or "Falso comeco / vicio removido"),
        ))
    for seg in semantic_plan.get("segmentos_editoriais", []):
        dec = seg.get("decision")
        if dec in ("remover_repeticao", "remover_falso_comeco", "remover_pausa", "candidato_remocao"):
            windows.append((
                float(seg.get("raw_start", 0.0)),
                float(seg.get("raw_end", 0.0)),
                str(dec),
                str(seg.get("justificativa") or f"Decisao {dec}"),
            ))
    return windows


def _split_unit_by_removals_and_pauses(
    unit: Dict[str, Any],
    unit_idx: int,
    removal_windows: List[Tuple[float, float, str, str]],
    min_silence_s: float,
    removed_segments: List[Dict[str, Any]],
    *,
    antes: float = CUT_ANTES_S,
    depois: float = CUT_DEPOIS_S,
    fps: int = CUT_FPS,
    is_first_unit: bool = False,
    is_last_unit: bool = False,
    audio_duration_s: Optional[float] = None,
    prev_raw_out: float = 0.0,
) -> List[Dict[str, Any]]:
    """Remove palavras marcadas com margem segura e divide pausas pela lógica do cortar.py."""
    words = unit.get("words", []) or []
    if not words:
        return [unit]

    kept_flags: List[bool] = []
    kept_words: List[Dict[str, Any]] = []
    removed_any = False

    for idx, w in enumerate(words):
        w_text = str(w.get("word", w.get("w", ""))).strip()
        w_start = float(w.get("start", w.get("t", unit["raw_start"])))
        w_end = float(w.get("end", w.get("f", w_start)))
        w_dur = max(0.001, w_end - w_start)
        norm = "".join(ch for ch in w_text.lower() if ch.isalnum())
        clean_low = w_text.lower().strip(".,!?;:")

        cut_reason: Optional[Tuple[str, str]] = None
        for r_in, r_out, op, just in removal_windows:
            ov = _interval_overlap(w_start, w_end, r_in, r_out)
            if (w_start >= r_in - 0.03 and w_end <= r_out + 0.03) or (ov >= 0.5 * w_dur):
                cut_reason = (op, just)
                break

        if cut_reason is None:
            if norm in VOCAL_HESITATIONS or clean_low in VOCAL_HESITATIONS:
                cut_reason = ("remover_vicio_linguagem", f"Vicio de linguagem '{w_text}' removido")
            elif norm in FILLER_WORDS or clean_low in FILLER_WORDS:
                prev_end_w = float(words[idx - 1].get("end", words[idx - 1].get("f", w_start))) if idx > 0 else 0.0
                next_start_w = float(words[idx + 1].get("start", words[idx + 1].get("t", w_end))) if idx + 1 < len(words) else (w_end + min_silence_s)
                gap_before_w = (w_start - prev_end_w) if idx > 0 else min_silence_s
                gap_after_w = (next_start_w - w_end) if idx + 1 < len(words) else min_silence_s
                if gap_before_w >= min_silence_s and gap_after_w >= min_silence_s:
                    cut_reason = ("remover_vicio_linguagem", f"Muleta isolada '{w_text}' removida")

        if cut_reason is not None:
            removed_any = True
            kept_flags.append(False)
            removed_segments.append(
                {
                    "unit_index": unit_idx,
                    "raw_in": r3(w_start),
                    "raw_out": r3(w_end),
                    "operation": cut_reason[0],
                    "justification": cut_reason[1],
                    "text": w_text,
                }
            )
        else:
            kept_flags.append(True)
            kept_words.append(w)

    if not kept_words:
        return []

    has_unit_padding = ("padded_in_point" in unit and "padded_out_point" in unit)

    has_internal_long_pause = False
    for i in range(len(kept_words) - 1):
        w0_end = float(kept_words[i].get("end", kept_words[i].get("f", 0.0)))
        w1_start = float(kept_words[i + 1].get("start", kept_words[i + 1].get("t", 0.0)))
        if (w1_start - w0_end) >= min_silence_s:
            has_internal_long_pause = True
            break

    if not removed_any and not has_internal_long_pause and not has_unit_padding:
        return [unit]

    first_w_start = float(words[0].get("start", words[0].get("t", unit["raw_start"])))
    last_w_end = float(words[-1].get("end", words[-1].get("f", unit["raw_end"])))
    if has_unit_padding:
        outer_start = float(unit["padded_in_point"])
        outer_end = float(unit["padded_out_point"])
        if is_first_unit:
            outer_start = min(outer_start, max(0.0, first_w_start - 0.15))
        if is_last_unit:
            target_end = last_w_end + 0.35
            if audio_duration_s is not None and audio_duration_s > 0:
                target_end = min(float(audio_duration_s), target_end)
            outer_end = max(outer_end, target_end)
    else:
        outer_start = float(unit.get("raw_start", first_w_start))
        outer_end = float(unit.get("raw_end", last_w_end))

    outer_start = max(prev_raw_out, outer_start)
    outer_end = max(outer_start, outer_end)

    # Subtracao de intervalos `fora` conforme vortex-edicao/cortar.py
    fora: List[Tuple[float, float]] = []

    rem_blocks: List[Tuple[Optional[int], int, int, Optional[int]]] = []
    i = 0
    while i < len(words):
        if not kept_flags[i]:
            left_kept = i - 1
            while left_kept >= 0 and not kept_flags[left_kept]:
                left_kept -= 1
            j = i
            while j + 1 < len(words) and not kept_flags[j + 1]:
                j += 1
            right_kept = j + 1 if j + 1 < len(words) else None
            rem_blocks.append((left_kept if left_kept >= 0 else None, i, j, right_kept))
            i = j + 1
        else:
            i += 1

    for left_k, rem_i, rem_j, right_k in rem_blocks:
        rem_s = float(words[rem_i].get("start", words[rem_i].get("t", outer_start)))
        rem_e = float(words[rem_j].get("end", words[rem_j].get("f", rem_s)))
        if left_k is not None:
            p_end = float(words[left_k].get("end", words[left_k].get("f", outer_start)))
            x = max(p_end, min(rem_s, p_end + depois))
        else:
            x = outer_start
        if right_k is not None:
            q_start = float(words[right_k].get("start", words[right_k].get("t", outer_end)))
            y = min(q_start, max(rem_e, q_start - antes))
        else:
            y = outer_end
        if y > x:
            fora.append((x, y))

    kept_indices = [idx for idx, flag in enumerate(kept_flags) if flag]
    for pos in range(len(kept_indices) - 1):
        idx_a = kept_indices[pos]
        idx_b = kept_indices[pos + 1]
        if idx_b - idx_a == 1:
            p_end = float(words[idx_a].get("end", words[idx_a].get("f", outer_start)))
            q_start = float(words[idx_b].get("start", words[idx_b].get("t", outer_end)))
            if (q_start - p_end) >= min_silence_s:
                cut_s = p_end + depois
                cut_e = q_start - antes
                if cut_e > cut_s:
                    fora.append((cut_s, cut_e))

    fora.sort()
    merged: List[Tuple[float, float]] = []
    for x, y in fora:
        if merged and x <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], y))
        else:
            merged.append((x, y))

    cursor = outer_start
    spans: List[Tuple[float, float]] = []
    for x, y in merged:
        if x > cursor:
            spans.append((cursor, min(x, outer_end)))
        cursor = max(cursor, y)
    if cursor < outer_end:
        spans.append((cursor, outer_end))

    sub_units: List[Dict[str, Any]] = []
    prev_span_end = prev_raw_out
    for span_idx, (raw_a, raw_b) in enumerate(spans):
        a = max(prev_span_end, r3(round(raw_a * fps) / fps))
        b = max(a, r3(round(raw_b * fps) / fps))
        if b - a <= 0.05:
            continue
        span_words: List[Dict[str, Any]] = []
        for kw in kept_words:
            ks = float(kw.get("start", kw.get("t", a)))
            ke = float(kw.get("end", kw.get("f", ks)))
            kmid = (ks + ke) / 2.0
            if (raw_a - 0.02) <= kmid <= (raw_b + 0.02):
                span_words.append(kw)
        if not span_words:
            continue
        prev_span_end = b
        sil_before = (
            unit.get("silence_removed_before", 0.0)
            if not sub_units
            else round(max(0.0, raw_a - spans[span_idx - 1][1]), 3)
        )
        sub_units.append(
            {
                "raw_start": a,
                "raw_end": b,
                "words": span_words,
                "text": " ".join(str(x.get("word", x.get("w", ""))).strip() for x in span_words),
                "silence_removed_before": sil_before,
            }
        )
    return sub_units


def _map_raw_to_out(raw_t: float, events: List[Dict[str, Any]]) -> float:
    """Mapeia um timestamp do eixo bruto (raw_*) para o eixo montado (out_*)."""
    if not events:
        return 0.0
    for ev in events:
        if ev["raw_in"] <= raw_t <= ev["raw_out"]:
            offset = raw_t - ev["raw_in"]
            return r3(min(ev["out_out"], ev["out_in"] + offset))
    # Se estiver em pausa entre eventos, ancora no evento mais proximo
    for ev in events:
        if raw_t < ev["raw_in"]:
            return r3(ev["out_in"])
    return r3(events[-1]["out_out"])


def build_edl_from_alignment(
    alignment_path: Path,
    workspace_root: str | Path,
    marca_id: str,
    episodio_id: str,
    brand_profile: Dict[str, Any],
    output_dir: Path | None = None,
    logger: logging.Logger | None = None,
    semantic_plan_path: Path | None = None,
    ensure_motion_layers: bool = False,
    include_dynamic_captions: bool = False,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Constrói a EDL longa (edl_longo.json) e o editorial_plan.json (6 camadas)
    a partir do alignment.json, aplicando regras de jump-cut (remoção de
    silêncios > threshold, padding de segurança) e parâmetros de áudio da marca.

    Gera events no eixo out_* (linha de tempo montada) com:
      - source_ref {id, path, sha256} referenciando o arquivo em brutos/
      - raw_in/raw_out (pontos na fonte original)
      - out_in/out_out (eixo da linha de tempo montada)
      - operation, justification
      - audio_treatment
      - motion_hints
      - narrative_continuity {topic_id, explanation_group_id, preserves_context}

    Retorna (edl, editorial_plan).
    """
    if logger is None:
        logger = setup_logger()

    loader = WorkspaceLoader(workspace_root)
    loader.load_workspace()

    t_start = time.perf_counter()

    # Parâmetros de áudio da marca
    audio_cfg = _brand_get(brand_profile, "audio", "preferencias_edicao.audio", default={})
    min_silence_s = float(audio_cfg.get("jumpcut_gap_threshold_ms", 450)) / 1000.0
    target_gap_ms = audio_cfg.get("jumpcut_target_gap_ms", [200, 250])
    pad_s = (target_gap_ms[0] + target_gap_ms[1]) / 2 / 1000.0  # ~225ms total

    logger.info("=" * 74)
    logger.info("CONSTRUTOR DE EDL LONGA — CORE-EDL-BUILDER (Editor)")
    logger.info("=" * 74)
    logger.info(f"Alignment: {alignment_path}")
    logger.info(f"Marca: {marca_id} | Episódio: {episodio_id}")
    logger.info(f"jumpcut_gap_threshold_ms: {min_silence_s * 1000:.0f}ms")
    logger.info(f"jumpcut_target_gap_ms: {target_gap_ms} -> pad_s: {pad_s * 1000:.0f}ms")

    if not alignment_path.is_file():
        raise EdlBuilderError(f"alignment.json não encontrado: {alignment_path}")

    with open(alignment_path, "r", encoding="utf-8") as f:
        alignment_data = json.load(f)

    editorial_units = alignment_data.get("editorial_units", [])
    if not editorial_units:
        raise EdlBuilderError("alignment.json sem unidades editoriais.")

    # Caminho do arquivo em brutos (source_ref), a partir de project.json.
    loader.load_workspace()
    projeto = loader.load_project(marca_id, episodio_id)
    sources = projeto.get("sources", [])
    if not sources:
        raise EdlBuilderError(
            f"Nenhuma source registrada em project.json para {marca_id}/{episodio_id}. "
            f"Rode a ingestão primeiro."
        )
    fonte = sources[0]
    source_ref = {
        "id": fonte.get("id", f"SRC_{marca_id.upper()}_{episodio_id.upper()}"),
        "path": fonte.get("path", ""),
        "sha256": fonte.get("sha256", ""),
    }

    proj_path = loader.project_file(marca_id, episodio_id)
    if output_dir is None:
        output_dir = loader.resolve_episodio_asset(marca_id, episodio_id, "workspace/briefing")
    output_dir.mkdir(parents=True, exist_ok=True)
    log_file = output_dir / "logs" / "edl_builder.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    for h in list(logger.handlers):
        logger.removeHandler(h)
    logger = setup_logger(log_file)

    # Carrega semantic_plan.json se existir
    fonte_dir = loader.resolve_episodio_asset(marca_id, episodio_id, "workspace/fonte")
    branding_dir = loader.branding_dir(marca_id)
    target_format = _detect_target_format(projeto, fonte_dir)

    sem_path = semantic_plan_path if semantic_plan_path is not None else (output_dir / "semantic_plan.json")
    semantic_plan: Optional[Dict[str, Any]] = None
    if sem_path.is_file():
        t_path = fonte_dir / "transcript.json"
        t_data = json.loads(t_path.read_text(encoding="utf-8")) if t_path.is_file() else None
        try:
            semantic_plan = load_semantic_plan(sem_path, transcript_data=t_data)
        except SemanticPlanError as exc:
            # Tenta validar contra a transcricao revisada se existir
            if (fonte_dir / "transcript_reviewed.json").is_file():
                try:
                    ed_tr = resolve_editorial_transcript(fonte_dir)
                    semantic_plan = load_semantic_plan(
                        sem_path,
                        transcript_data={"segments": ed_tr.get("segments", [])},
                    )
                except Exception as exc2:
                    raise EdlBuilderError(f"semantic_plan.json inválido: {exc2}") from exc2
            else:
                raise EdlBuilderError(f"semantic_plan.json inválido: {exc}") from exc

    # Constrói eventos da timeline a partir das unidades editoriais,
    # aplicando remoção de silêncios, vícios/repetições, decisões semânticas e padding.
    events: List[Dict[str, Any]] = []
    removed_segments: List[Dict[str, Any]] = []
    event_id = 1
    out_cursor = 0.0
    word_index: Dict[str, Any] = {}
    total_words_preserved = 0
    word_counter = 0

    removal_windows = _collect_removal_windows(semantic_plan)
    audio_duration_s = (alignment_data.get("summary") or {}).get("audio_duration_seconds")
    fps_val = int(target_format.get("fps") or CUT_FPS)
    valid_unit_indices = [idx for idx, u in enumerate(editorial_units, start=1) if u.get("words")]
    first_valid_unit = valid_unit_indices[0] if valid_unit_indices else 1
    last_valid_unit = valid_unit_indices[-1] if valid_unit_indices else len(editorial_units)
    prev_raw_out = 0.0

    for unit_idx, unit in enumerate(editorial_units, start=1):
        words = unit.get("words", [])
        if not words:
            continue

        raw_start = unit["raw_start"]
        raw_end = unit["raw_end"]

        preservar, operation, sem_just, topic_label, explanation_group = _resolve_unit_decision(
            raw_start, raw_end, semantic_plan
        )
        if not preservar:
            removed_segments.append(
                {
                    "unit_index": unit_idx,
                    "raw_in": r3(raw_start),
                    "raw_out": r3(raw_end),
                    "operation": operation,
                    "justification": sem_just,
                    "text": unit.get("text", ""),
                }
            )
            continue

        sub_units = _split_unit_by_removals_and_pauses(
            unit,
            unit_idx,
            removal_windows,
            min_silence_s,
            removed_segments,
            fps=fps_val,
            is_first_unit=(unit_idx == first_valid_unit),
            is_last_unit=(unit_idx == last_valid_unit),
            audio_duration_s=audio_duration_s,
            prev_raw_out=prev_raw_out,
        )
        for sub_unit in sub_units:
            sub_words = sub_unit.get("words", [])
            if not sub_words:
                continue
            sub_raw_start = float(sub_unit["raw_start"])
            sub_raw_end = float(sub_unit["raw_end"])
            if sub_raw_end <= sub_raw_start:
                continue

            # O respiro pre/post-palavra ja vive em raw_in/raw_out; assim out_out - out_in == raw_out - raw_in
            duration = r3(sub_raw_end - sub_raw_start)
            if duration <= 0:
                continue

            out_in_ev = r3(events[-1]["out_out"]) if events else 0.0
            out_out_ev = r3(out_in_ev + duration)
            prev_raw_out = max(prev_raw_out, r3(sub_raw_end))

            # word_ids para as palavras deste segmento
            unit_word_ids = []
            for w in sub_words:
                word_counter += 1
                wid = f"W{word_counter:05d}"
                unit_word_ids.append(wid)
                word_index[wid] = {
                    "event_id": event_id,
                    "position_in_event": len(unit_word_ids),
                    "word": w.get("word", w.get("w", "")),
                    "start": r3(w.get("start", w.get("t", sub_raw_start))),
                    "end": r3(w.get("end", w.get("f", sub_raw_end))),
                    "probability": w.get("probability", 1.0),
                }

            event = {
                "event_id": event_id,
                "type": "video_audio",
                "source_ref": dict(source_ref),  # cópia do source_ref
                "raw_in": r3(sub_raw_start),
                "raw_out": r3(sub_raw_end),
                "out_in": out_in_ev,
                "out_out": out_out_ev,
                "duration_seconds": duration,
                "word_ids": list(unit_word_ids),
                "word_count": len(unit_word_ids),
                "text": sub_unit.get("text", ""),
                "transition_in": "hard_cut",
                "transition_out": "hard_cut",
                "operation": operation,
                "justification": (
                    f"Unidade editorial {unit_idx} — {sem_just} "
                    f"(silêncio removido antes: {sub_unit.get('silence_removed_before', 0.0)}s)"
                ),
                "audio_treatment": "preservar",
                "motion_hints": [],
                "notes": f"Unidade editorial {unit_idx}",
                "silence_removed_before": sub_unit.get("silence_removed_before", 0.0),
                "narrative_continuity": {
                    "topic_id": topic_label,
                    "explanation_group_id": explanation_group,
                    "preserves_context": True,
                },
            }
            events.append(event)
            total_words_preserved += len(unit_word_ids)
            event_id += 1
            out_cursor = event["out_out"]

    # Atualiza out_cursor final e durações finais
    final_duration = r3(events[-1]["out_out"]) if events else 0.0

    # Sumário da EDL
    source_total = r3(sum(e["raw_out"] - e["raw_in"] for e in events))
    silence_removed = r3(source_total - final_duration)

    summary = {
        "source_axis_total_seconds": source_total,
        "out_axis_total_seconds": final_duration,
        "final_duration_seconds": final_duration,
        "silence_removed_seconds": silence_removed,
        "silence_removed_percent_of_source": r3(
            silence_removed / source_total * 100.0
        )
        if source_total > 0
        else 0.0,
        "silences_removed_count": len(editorial_units) - len(events),
        "blocks_preserved_count": len(events),
        "timeline_events_count": len(events),
        "words_preserved": total_words_preserved,
        "jumpcut_gap_threshold_ms": min_silence_s * 1000,
        "jumpcut_target_gap_ms": target_gap_ms,
    }

    edl = {
        "schema_version": "1.0.0",
        "version": "1.0.0",
        "marca_id": marca_id,
        "episodio_id": episodio_id,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
        "generated_by": "CORE-EDL-BUILDER (Editor)",
        "source_ref": source_ref,
        "target_format": dict(target_format),
        "parameters": {
            "min_silence_seconds": r3(min_silence_s),
            "pad_seconds": r3(pad_s),
            "total_safety_padding_seconds": r3(pad_s * 2),
            "jumpcut_gap_threshold_ms": r3(min_silence_s * 1000),
            "jumpcut_target_gap_ms": target_gap_ms,
            "silence_rule": (
                "gap > jumpcut_gap_threshold_ms entre palavras; padding de segurança "
                "conforme jumpcut_target_gap_ms"
            ),
        },
        "planning_mode": "semantic_plan" if semantic_plan is not None else "deterministic_fallback",
        "requires_semantic_review": semantic_plan is None,
        "requires_human_approval": True,
        "timeline_events": events,
        "removed_segments": removed_segments,
        "word_index": word_index,
        "summary": summary,
        "telemetry": {
            "processing_time_seconds": r3(time.perf_counter() - t_start),
        },
    }

    # Validação do contrato (enxuta)
    previous_out = 0.0
    for event in events:
        if abs(event["out_in"] - previous_out) > 1e-6:
            raise EdlBuilderError(
                f"Descontinuidade no eixo out_* antes do evento {event['event_id']}"
            )
        if event["out_out"] <= event["out_in"]:
            raise EdlBuilderError(f"Evento {event['event_id']} com duração não positiva.")
        previous_out = event["out_out"]

    indexed = edl["word_index"]
    emitted = [wid for event in events for wid in event["word_ids"]]
    if len(emitted) != len(set(emitted)):
        raise EdlBuilderError("word_id duplicado entre eventos da timeline.")
    if set(emitted) != set(indexed):
        raise EdlBuilderError("Eventos e word_index divergem no conjunto de palavras.")

    total = r3(sum(event["duration_seconds"] for event in events))
    if abs(total - edl["summary"]["final_duration_seconds"]) > 1e-2:
        raise EdlBuilderError(
            f"Soma dos eventos ({total}) != duração final "
            f"({edl['summary']['final_duration_seconds']})."
        )

    # --- Constroi editorial_plan.json (6 camadas L1..L6) coerente com o EDL ---
    editorial_plan = _build_editorial_plan(
        events,
        brand_profile,
        marca_id,
        episodio_id,
        final_duration,
        semantic_plan=semantic_plan,
        alinhamento_unidades=editorial_units,
        target_format=target_format,
        fonte_dir=fonte_dir,
        branding_dir=branding_dir,
        ensure_motion_layers=ensure_motion_layers,
        source_total=source_total,
    )

    if target_format.get("aspect_ratio") == "9:16" or include_dynamic_captions:
        dynamic_captions = _build_dynamic_captions(events, word_index)
    else:
        dynamic_captions = []
    edl["dynamic_captions"] = dynamic_captions
    editorial_plan["dynamic_captions"] = dynamic_captions

    # Propaga motion_hints da timeline de volta para timeline_events e L1
    layers_map = editorial_plan.get("layers", {})
    for ev_idx, ev in enumerate(events):
        hints: List[str] = []
        ev_in = float(ev["out_in"])
        ev_out = float(ev["out_out"])
        for cname in LAYERS_VISUAIS:
            for mel in layers_map.get(cname, []):
                if _interval_overlap(ev_in, ev_out, float(mel.get("out_in", 0.0)), float(mel.get("out_out", 0.0))) > 0:
                    cid = mel.get("componente_motion_library") or cname
                    if cid not in hints:
                        hints.append(cid)
        ev["motion_hints"] = hints
        if ev_idx < len(layers_map.get("L1_estabelecimento", [])):
            layers_map["L1_estabelecimento"][ev_idx]["motion_hints"] = list(hints)

    # Espelha eventos de Motion Design em tela cheia na raiz da EDL para consumo direto
    edl["fullscreen_motions"] = list(layers_map.get("L5_fullscreen_motion", []))

    # Resolve vinhetas multi-marca (Niveis 1/2/3) para Intro e Outro no formato alvo
    ar_str = str((target_format or {}).get("aspect_ratio") or "16:9")
    brand_bumpers = {
        "intro": resolve_brand_bumper(
            "intro",
            ar_str,
            workspace_root=workspace_root,
            marca_id=marca_id,
            brand_profile=brand_profile,
        ),
        "outro": resolve_brand_bumper(
            "outro",
            ar_str,
            workspace_root=workspace_root,
            marca_id=marca_id,
            brand_profile=brand_profile,
        ),
    }
    edl["brand_bumpers"] = brand_bumpers
    editorial_plan["brand_bumpers"] = brand_bumpers

    edl_path = output_dir / "edl_longo.json"
    with open(edl_path, "w", encoding="utf-8") as f:
        json.dump(edl, f, indent=2, ensure_ascii=False)

    plan_path = output_dir / "editorial_plan.json"
    with open(plan_path, "w", encoding="utf-8") as f:
        json.dump(editorial_plan, f, indent=2, ensure_ascii=False)

    logger.info(f"EDL longa gravada: {edl_path}")
    logger.info(f"Editorial plan gravado: {plan_path}")
    logger.info(
        f"Eventos: {len(events)} | Palavras preservadas: {total_words_preserved}"
    )
    logger.info(
        f"Duração final: {final_duration:.3f}s | Silêncio removido: {silence_removed:.3f}s"
    )

    # Fecha handlers de arquivo para liberar locks (Windows)
    for handler in list(logger.handlers):
        if isinstance(handler, logging.FileHandler):
            handler.close()
            logger.removeHandler(handler)

    return edl, editorial_plan


def _discover_local_assets(
    fonte_dir: Optional[Path],
    branding_dir: Optional[Path],
    *,
    brand_profile: Optional[Dict[str, Any]] = None,
    workspace_root: Optional[Path] = None,
    marca_id: Optional[str] = None,
) -> Tuple[List[str], List[str]]:
    """Descobre assets locais autorizados de B-roll e SFX sem hardcode."""
    brolls: List[str] = []
    sfx_list: List[str] = []
    excluded_audio = {"audio_speech_16k_mono.wav", "audio_program_48k.wav"}

    scan_roots: List[Path] = []
    for r in (fonte_dir, branding_dir):
        if r is not None and r.is_dir() and r not in scan_roots:
            scan_roots.append(r)
    if brand_profile is not None or marca_id:
        try:
            ad = resolve_brand_asset_dirs(
                workspace_root, marca_id, brand_profile=brand_profile
            )
            for br in ad.get("brand_roots", []):
                if br.is_dir() and br not in scan_roots:
                    scan_roots.append(br)
        except Exception:
            pass

    for root in scan_roots:
        if root is None or not root.is_dir():
            continue
        for p in sorted(root.rglob("*")):
            if not p.is_file() or p.stat().st_size <= 0:
                continue
            rel = str(p.relative_to(root)).replace("\\", "/")
            ext = p.suffix.lower()
            name_low = p.name.lower()
            if ext in (".png", ".jpg", ".jpeg", ".webp") and ("broll" in rel.lower() or root == fonte_dir):
                if rel not in brolls:
                    brolls.append(rel)
            elif ext in (".wav", ".mp3", ".ogg", ".flac") and name_low not in excluded_audio:
                if rel not in sfx_list:
                    sfx_list.append(rel)
    return brolls, sfx_list


def _build_dynamic_captions(
    events: List[Dict[str, Any]],
    word_index: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Gera legendas dinamicas sincronizadas no eixo out_* a partir da EDL."""
    captions: List[Dict[str, Any]] = []
    for ev in events:
        raw_in = float(ev["raw_in"])
        out_in = float(ev["out_in"])
        out_out = float(ev["out_out"])
        wids = list(ev.get("word_ids", []))
        if not wids:
            continue
        # Agrupa em blocos de ate 5 palavras para leitura rapida
        chunk_size = 5
        for idx in range(0, len(wids), chunk_size):
            chunk = wids[idx : idx + chunk_size]
            tokens = [word_index[wid] for wid in chunk if wid in word_index]
            if not tokens:
                continue
            c_start = r3(max(out_in, out_in + max(0.0, float(tokens[0]["start"]) - raw_in)))
            c_end = r3(min(out_out, max(c_start + 0.15, out_in + max(0.0, float(tokens[-1]["end"]) - raw_in))))
            captions.append(
                {
                    "event_id": ev["event_id"],
                    "out_in": c_start,
                    "out_out": c_end,
                    "text": " ".join(str(t.get("word", "")).strip() for t in tokens).strip(),
                    "words": [
                        {
                            "word": str(t.get("word", "")).strip(),
                            "out_in": r3(max(out_in, out_in + max(0.0, float(t["start"]) - raw_in))),
                            "out_out": r3(min(out_out, out_in + max(0.0, float(t["end"]) - raw_in))),
                        }
                        for t in tokens
                    ],
                }
            )
    return captions


def _populate_missing_motion_layers(
    layers: Dict[str, List[Dict[str, Any]]],
    *,
    events: List[Dict[str, Any]],
    brand_profile: Dict[str, Any],
    semantic_plan: Optional[Dict[str, Any]],
    base_source_ref: Dict[str, Any],
    final_duration: float,
    raw_total: float,
    fonte_dir: Optional[Path],
    branding_dir: Optional[Path],
) -> None:
    """Garante camadas de Motion Graphics reais quando solicitadas pelo fluxo."""
    effective_dur = min(final_duration, raw_total) if raw_total >= 1.8 else final_duration
    if effective_dur < 1.2 or not events:
        return

    next_id = sum(len(layers.get(c, [])) for c in LAYERS_VISUAIS) + 1

    def _new_el(
        camada: str,
        comp: str,
        out_in: float,
        out_out: float,
        texto: str,
        funcao: str,
        just: str,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        nonlocal next_id
        eid = f"M{next_id:04d}"
        next_id += 1
        el: Dict[str, Any] = {
            "element_id": eid,
            "event_id": None,
            "type": "visual_overlay",
            "source_ref": dict(base_source_ref),
            "raw_in": None,
            "raw_out": None,
            "out_in": r3(out_in),
            "out_out": r3(out_out),
            "duration_seconds": r3(out_out - out_in),
            "origin": "rhythm_engine",
            "dedup_key": f"motion_ensure|{camada}|{r3(out_in)}|{r3(out_out)}",
            "justification": just,
            "componente_motion_library": comp,
            "texto": texto,
            "funcao_editorial": funcao,
            "motion_type": {
                "L2_titulo_heroi_t10": "T10",
                "L3_micro_zoom_bate": "MicroZoom",
                "L4_lower_third": "LowerThird",
                "L5_broll_industrial": "B-roll",
                "L5_fullscreen_motion": "FullscreenMotion",
                "L6_sound_design_sync": "SoundDesign",
            }.get(camada, camada),
            "audio_treatment": "preservar",
            "segment_ids": [],
            "word_refs": [],
        }
        if extra:
            el.update(extra)
        return el

    def _overlaps_any(camadas: Tuple[str, ...], a_in: float, a_out: float) -> bool:
        for cname in camadas:
            for item in layers.get(cname, []):
                if _interval_overlap(a_in, a_out, float(item["out_in"]), float(item["out_out"])) > 0:
                    return True
        return False

    # 1. L2: titulo_heroi na abertura (min 1.8s, max 4.5s)
    if not layers["L2_titulo_heroi_t10"] and effective_dur >= 1.8:
        titulo_txt = ""
        if semantic_plan:
            topicos = semantic_plan.get("topicos") or []
            if topicos and topicos[0].get("titulo") and "abertura" not in str(topicos[0]["titulo"]).lower():
                titulo_txt = str(topicos[0]["titulo"])
        if not titulo_txt:
            titulo_txt = str(
                _brand_get(brand_profile, "preferencias_edicao.canal", "display_name", default="Destaque")
                or "Destaque"
            )
        titulo_txt = titulo_txt[:48]
        l2_out = r3(min(effective_dur, 3.0))
        if l2_out >= 1.8 and not _overlaps_any(("L5_broll_industrial", "L5_fullscreen_motion"), 0.0, l2_out):
            layers["L2_titulo_heroi_t10"].append(
                _new_el(
                    "L2_titulo_heroi_t10",
                    "titulo_heroi",
                    0.0,
                    l2_out,
                    titulo_txt,
                    "Abertura com titulo cinetico",
                    "Ancora o tema principal nos primeiros segundos.",
                )
            )

    # 2. L4: lower_third para credencial do apresentador (min 3.0s, max 5.5s)
    if not layers["L4_lower_third"] and effective_dur >= 6.2:
        l4_in = r3(max((layers["L2_titulo_heroi_t10"][-1]["out_out"] + 0.2) if layers["L2_titulo_heroi_t10"] else 0.5, 0.5))
        l4_out = r3(min(effective_dur, l4_in + 3.5))
        if l4_out - l4_in >= 3.0 and not _overlaps_any(("L2_titulo_heroi_t10", "L5_broll_industrial", "L5_fullscreen_motion"), l4_in, l4_out):
            nome = str(
                _brand_get(brand_profile, "presenter.name", "preferencias_edicao.apresentador", default="Apresentador")
                or "Apresentador"
            )
            cred = str(
                _brand_get(brand_profile, "presenter.credential", "preferencias_edicao.credencial_oficial", default="")
                or ""
            )
            layers["L4_lower_third"].append(
                _new_el(
                    "L4_lower_third",
                    "lower_third",
                    l4_in,
                    l4_out,
                    nome,
                    "Identificacao oficial do apresentador",
                    "Reforca autoridade com lower third cinetico.",
                    {"nome": nome, "credencial": cred},
                )
            )

    # 3. L3: micro_zoom_bate em pontos de transicao ou enfase (min 1.2s, max 3.0s)
    if not layers["L3_micro_zoom_bate"] and effective_dur >= 2.0:
        cand_in = 0.0
        if layers["L2_titulo_heroi_t10"]:
            cand_in = float(layers["L2_titulo_heroi_t10"][-1]["out_out"]) + 0.2
        if cand_in + 1.5 > effective_dur:
            cand_in = max(0.0, effective_dur - 1.6)
        cand_out = r3(min(effective_dur, cand_in + 1.8))
        if cand_out - cand_in >= 1.2 and not _overlaps_any(("L5_broll_industrial", "L5_fullscreen_motion"), cand_in, cand_out):
            layers["L3_micro_zoom_bate"].append(
                _new_el(
                    "L3_micro_zoom_bate",
                    "micro_zoom_bate",
                    cand_in,
                    cand_out,
                    "Micro-zoom de enfase",
                    "Dinamica de camera em ponto de enfase",
                    "Mantem ritmo visual sem cortes bruscos.",
                )
            )

    # 4. L5 e L6: se houver assets locais autorizados
    brolls, sfx_files = _discover_local_assets(
        fonte_dir,
        branding_dir,
        brand_profile=brand_profile,
        marca_id=(brand_profile or {}).get("marca_id"),
    )
    if not layers["L5_broll_industrial"] and brolls and effective_dur >= 9.0:
        ocupado_fim = max(
            [float(el["out_out"]) for c in ("L2_titulo_heroi_t10", "L3_micro_zoom_bate", "L4_lower_third", "L5_fullscreen_motion") for el in layers.get(c, [])]
            or [0.0]
        )
        b_in = r3(ocupado_fim + 0.2)
        b_out = r3(min(effective_dur, b_in + 3.0))
        if b_out - b_in >= 2.5 and not _overlaps_any(("L2_titulo_heroi_t10", "L3_micro_zoom_bate", "L4_lower_third", "L5_fullscreen_motion"), b_in, b_out):
            layers["L5_broll_industrial"].append(
                _new_el(
                    "L5_broll_industrial",
                    "broll_industrial",
                    b_in,
                    b_out,
                    "B-Roll de apoio visual",
                    "Insercao visual contextual com Ken Burns",
                    "Ilustra o argumento sem obstruir o apresentador.",
                    {"media_ref": brolls[0]},
                )
            )

    if not layers["L6_sound_design_sync"] and sfx_files:
        ancoras = [
            float(el["out_in"])
            for c in ("L2_titulo_heroi_t10", "L4_lower_third", "L5_broll_industrial", "L5_fullscreen_motion")
            for el in layers.get(c, [])
        ]
        if ancoras:
            s_in = r3(max(0.0, ancoras[0]))
            s_out = r3(min(effective_dur, s_in + 0.5))
            if s_out - s_in >= 0.2:
                layers["L6_sound_design_sync"].append(
                    _new_el(
                        "L6_sound_design_sync",
                        "sound_design_sync",
                        s_in,
                        s_out,
                        sfx_files[0],
                        "Sincronizacao sonora de entrada",
                        "Sublinha entrada do elemento grafico principal.",
                        {"sound_ref": sfx_files[0], "volume": 0.9},
                    )
                )


def _normalize_fullscreen_motion_elements(
    elements: List[Dict[str, Any]],
    target_format: Optional[Dict[str, Any]] = None,
) -> None:
    """Garante contrato completo de eventos `fullscreen_motion` na camada L5_fullscreen_motion."""
    res = (target_format or {}).get("resolution") or [1920, 1080]
    target_w = int(res[0]) if len(res) >= 2 else 1920
    target_h = int(res[1]) if len(res) >= 2 else 1080
    for idx, el in enumerate(elements, start=1):
        if not isinstance(el, dict):
            continue
        scene_id = str(
            el.get("scene_id")
            or el.get("id_cena")
            or el.get("element_id")
            or f"cena_full_{idx:02d}"
        ).strip()
        safe_scene_id = "".join(c if (c.isalnum() or c in "_-") else "_" for c in scene_id).strip("_") or f"cena_full_{idx:02d}"
        html_path = str(el.get("html_path") or f"workspace/motions_custom/{safe_scene_id}.html").replace("\\", "/")
        z_index = int(el.get("z_index") or 18)
        el["type"] = "fullscreen_motion"
        el["componente_motion_library"] = "fullscreen_motion"
        el["motion_type"] = "FullscreenMotion"
        el["scene_id"] = safe_scene_id
        el["html_path"] = html_path
        el["transition_in"] = str(el.get("transition_in") or "clean_fade")
        el["transition_out"] = str(el.get("transition_out") or "clean_fade")
        el["z_index"] = z_index
        el["narration_continuous"] = True
        el["viewport"] = {
            "width": target_w,
            "height": target_h,
            "coverage": "100%",
            "z_index": z_index,
        }


def _build_editorial_plan(
    events: List[Dict[str, Any]],
    brand_profile: Dict[str, Any],
    marca_id: str,
    episodio_id: str,
    final_duration: float,
    semantic_plan: Optional[Dict[str, Any]] = None,
    alinhamento_unidades: Optional[List[Dict[str, Any]]] = None,
    target_format: Optional[Dict[str, Any]] = None,
    fonte_dir: Optional[Path] = None,
    branding_dir: Optional[Path] = None,
    ensure_motion_layers: bool = False,
    source_total: Optional[float] = None,
) -> Dict[str, Any]:
    """Constrói o editorial_plan.json com 6 camadas coerentes com o EDL.

    - L1_estabelecimento recebe todos os eventos contínuos de fala (video_audio).
    - L2..L6 são construídas pelo RhythmEngine a partir de intencoes_visuais
      do semantic_plan.json (semantic-first, com clamp de duracao) mais
      microeventos complementares quando houver justificativa deterministica.
    """
    layers: Dict[str, List[Dict[str, Any]]] = _empty_layers()
    base_source_ref = dict(events[0]["source_ref"]) if events else {}

    # L1: continuidade audiovisual da fala
    for event in events:
        element = {
            "element_id": f"E{event['event_id']:05d}",
            "event_id": event["event_id"],
            "type": event["type"],
            "source_ref": dict(event["source_ref"]),
            "raw_in": event["raw_in"],
            "raw_out": event["raw_out"],
            "out_in": event["out_in"],
            "out_out": event["out_out"],
            "duration_seconds": event["duration_seconds"],
            "word_ids": list(event["word_ids"]),
            "text": event["text"],
            "transition_in": event["transition_in"],
            "transition_out": event["transition_out"],
            "operation": event["operation"],
            "justification": event["justification"],
            "audio_treatment": event["audio_treatment"],
            "motion_hints": list(event["motion_hints"]),
            "narrative_continuity": dict(event["narrative_continuity"]),
        }
        layers["L1_estabelecimento"].append(element)

    # L2..L6: construídas pelo RhythmEngine (semantic-first + complementares)
    rhythm_layers, rhythm_report = build_rhythm_layers(
        semantic_plan=semantic_plan,
        events_l1=events,
        final_duration=final_duration,
        alinhamento_unidades=alinhamento_unidades,
        base_source_ref=base_source_ref,
    )

    # Mescla camadas do rhythm_engine no plano
    for camada in LAYERS_VISUAIS:
        layers[camada] = rhythm_layers.get(camada, [])

    _normalize_fullscreen_motion_elements(layers.get("L5_fullscreen_motion", []), target_format=target_format)

    if ensure_motion_layers:
        _populate_missing_motion_layers(
            layers,
            events=events,
            brand_profile=brand_profile,
            semantic_plan=semantic_plan,
            base_source_ref=base_source_ref,
            final_duration=final_duration,
            raw_total=float(source_total if source_total is not None else final_duration),
            fonte_dir=fonte_dir,
            branding_dir=branding_dir,
        )
        total_vis = sum(
            len(layers[c])
            for c in ("L2_titulo_heroi_t10", "L3_micro_zoom_bate", "L4_lower_third", "L5_broll_industrial", "L5_fullscreen_motion")
        )
        rhythm_report["total_estimulos_visuais"] = total_vis

    is_semantic = semantic_plan is not None
    plan = {
        "schema_version": "1.0.0",
        "version": "1.0.0",
        "marca_id": marca_id,
        "episodio_id": episodio_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generated_by": "CORE-EDL-BUILDER (Editor)",
        "target_format": dict(target_format) if target_format else {
            "resolution": [1920, 1080],
            "aspect_ratio": "16:9",
            "fps": 30,
        },
        "planning_mode": "semantic_plan" if is_semantic else "deterministic_fallback",
        "requires_semantic_review": not is_semantic,
        "requires_human_approval": True,
        "source_ref": base_source_ref,
        "target_duration_seconds": final_duration,
        "total_events": len(events),
        "total_words": sum(e["word_count"] for e in events),
        "layers": layers,
        "layer_summary": {
            camada: len(elems) for camada, elems in layers.items()
        },
        "rhythm_report": rhythm_report,
        "notes": (
            "Plano editorial com 6 camadas (L1..L6) fundamentado em semantic_plan.json. "
            "Não aprova automaticamente o render — requer revisão humana."
            if is_semantic
            else "Fallback determinístico conservador: L1 preenchida com continuidade de fala; "
                 "L2..L6 vazias aguardando semantic_plan.json e revisão humana."
        ),
    }
    return plan


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="CORE-EDL-BUILDER: Construtor de EDL longa 16:9 (Editor)."
    )
    parser.add_argument("-m", "--marca-id", required=True, help="ID da marca.")
    parser.add_argument("-e", "--episodio-id", required=True, help="ID do episódio.")
    parser.add_argument(
        "-a", "--alignment-json", help="Caminho direto para alignment.json."
    )
    parser.add_argument(
        "-w", "--workspace-root", default="D:/Drifit/Editor"
    )
    parser.add_argument("-o", "--output-dir", help="Diretório de saída customizado.")
    args = parser.parse_args()

    loader = WorkspaceLoader(args.workspace_root)
    loader.load_workspace()
    brand_profile = loader.load_brand_profile(args.marca_id)

    alignment_path = None
    if args.alignment_json:
        alignment_path = Path(args.alignment_json).resolve()
    else:
        # Tenta usar alignment.json salvo na workspace/fonte do episódio.
        ep_dir = loader.episodio_dir(args.marca_id, args.episodio_id)
        candidato = ep_dir / "workspace" / "fonte" / "alignment.json"
        if candidato.is_file():
            alignment_path = candidato

    if alignment_path is None:
        print(
            "[ERRO] alignment.json não encontrado. Informe --alignment-json.",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        edl, plan = build_edl_from_alignment(
            alignment_path=alignment_path,
            workspace_root=args.workspace_root,
            marca_id=args.marca_id,
            episodio_id=args.episodio_id,
            brand_profile=brand_profile,
            output_dir=Path(args.output_dir).resolve() if args.output_dir else None,
        )
        print(
            f"[OK] EDL longa: {len(edl['timeline_events'])} eventos | "
            f"Duração final: {edl['summary']['final_duration_seconds']:.3f}s"
        )
        print(
            f"[OK] Editorial plan: {plan['total_events']} eventos em "
            f"{plan['layer_summary']}"
        )
        sys.exit(0)
    except Exception as e:
        print(f"[ERRO FATAL] EDL Builder falhou: {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
