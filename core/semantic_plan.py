"""
core/semantic_plan.py

Contrato versionado e validador de planejamento editorial semantico
(workspace/briefing/semantic_plan.json) para o Editor.

Caracteristicas:
- Agnóstico a modelo/provedor de IA (sem chaves de API comerciais).
- Permite que um agente externo (ou revisao humana) gere semantic_plan.json
  a partir de transcript.json, roteiro.txt e metadados textuais autorizados.
- Valida estrutura, versionamento, consistencia temporal (sem inventar
  timestamps), referencias a segmentos/palavras da transcricao e whitelist de
  componentes efetivamente implementados no Motion Library.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


SEMANTIC_PLAN_SCHEMA_VERSION = "1.0.0"

# Componentes efetivamente implementados na Motion Library + motor HTML/GSAP/HyperFrames
IMPLEMENTED_MOTION_COMPONENTS: Set[str] = {
    "titulo_heroi",
    "micro_zoom_bate",
    "lower_third",
    "broll_industrial",
    "sound_design_sync",
    "card_flutuante",
    "barra_progresso",
    "stepper",
    "pip_stage",
    "split_stage",
    "transicao_marca",
    "fullscreen_motion",
    "hyperframes_cli",
}

VALID_DECISIONS: Set[str] = {
    "preservar",
    "remover_repeticao",
    "remover_falso_comeco",
    "remover_pausa",
    "candidato_remocao",
}

VALID_ARGUMENT_TYPES: Set[str] = {
    "tese",
    "argumento",
    "evidencia",
    "exemplo",
    "gancho",
    "virada",
    "conclusao",
}

VALID_EDITORIAL_LAYERS: Set[str] = {
    "L1_estabelecimento",
    "L2_titulo_heroi_t10",
    "L3_micro_zoom_bate",
    "L4_lower_third",
    "L5_broll_industrial",
    "L5_fullscreen_motion",
    "L6_sound_design_sync",
}


class SemanticPlanError(Exception):
    """Erro de validacao ou carregamento de semantic_plan.json."""


def _require_str(obj: Dict[str, Any], key: str, ctx: str) -> str:
    val = obj.get(key)
    if not isinstance(val, str) or not val.strip():
        raise SemanticPlanError(f"{ctx}: campo obrigatorio '{key}' ausente ou vazio.")
    return val.strip()


def _validate_time_window(
    obj: Dict[str, Any],
    ctx: str,
    max_duration_s: Optional[float] = None,
    allow_zero_length: bool = False,
) -> Tuple[float, float]:
    if "raw_start" not in obj or "raw_end" not in obj:
        raise SemanticPlanError(f"{ctx}: 'raw_start' e 'raw_end' sao obrigatorios.")
    try:
        raw_start = float(obj["raw_start"])
        raw_end = float(obj["raw_end"])
    except (TypeError, ValueError) as exc:
        raise SemanticPlanError(f"{ctx}: timestamps nao numericos.") from exc

    if raw_start < 0:
        raise SemanticPlanError(f"{ctx}: raw_start negativo ({raw_start}).")
    if allow_zero_length:
        if raw_end < raw_start:
            raise SemanticPlanError(f"{ctx}: raw_end ({raw_end}) < raw_start ({raw_start}).")
    else:
        if raw_end <= raw_start:
            raise SemanticPlanError(f"{ctx}: raw_end ({raw_end}) <= raw_start ({raw_start}).")

    if max_duration_s is not None and raw_end > max_duration_s + 0.25:
        raise SemanticPlanError(
            f"{ctx}: raw_end ({raw_end:.3f}s) excede a duracao da transcricao "
            f"({max_duration_s:.3f}s) — timestamp possivelmente inventado."
        )
    return raw_start, raw_end


def _validate_grounding_refs(
    obj: Dict[str, Any],
    ctx: str,
    valid_segment_ids: Optional[Set[Any]] = None,
    valid_word_ids: Optional[Set[str]] = None,
) -> None:
    seg_ids = obj.get("segment_ids")
    word_refs = obj.get("word_refs")
    has_seg = isinstance(seg_ids, list) and len(seg_ids) > 0
    has_word = isinstance(word_refs, list) and len(word_refs) > 0
    if not has_seg and not has_word:
        raise SemanticPlanError(
            f"{ctx}: toda decisao deve referenciar 'segment_ids' ou 'word_refs' da transcricao."
        )
    if valid_segment_ids is not None and has_seg:
        for sid in seg_ids:
            if sid not in valid_segment_ids:
                raise SemanticPlanError(
                    f"{ctx}: segment_id '{sid}' inexistente na transcricao."
                )
    if valid_word_ids is not None and has_word:
        for wid in word_refs:
            if wid not in valid_word_ids:
                raise SemanticPlanError(
                    f"{ctx}: word_ref '{wid}' inexistente na transcricao."
                )


def _extract_transcript_bounds(
    transcript_data: Optional[Dict[str, Any]],
) -> Tuple[Optional[float], Optional[Set[Any]], Optional[Set[str]]]:
    if not isinstance(transcript_data, dict):
        return None, None, None

    max_end = 0.0
    seg_ids: Set[Any] = set()
    word_ids: Set[str] = set()

    for seg in transcript_data.get("segments", []):
        if "id" in seg:
            seg_ids.add(seg["id"])
        if "segment_id" in seg:
            seg_ids.add(seg["segment_id"])
        try:
            max_end = max(max_end, float(seg.get("end", 0.0)))
        except (TypeError, ValueError):
            pass
        for w in seg.get("words", []):
            wid = w.get("word_id")
            if wid:
                word_ids.add(str(wid))
            try:
                max_end = max(max_end, float(w.get("end", w.get("f", 0.0))))
            except (TypeError, ValueError):
                pass

    dur = transcript_data.get("audio_duration_seconds") or transcript_data.get("duration_seconds")
    if dur is not None:
        try:
            max_end = max(max_end, float(dur))
        except (TypeError, ValueError):
            pass

    return (
        max_end if max_end > 0 else None,
        seg_ids if seg_ids else None,
        word_ids if word_ids else None,
    )


def validate_semantic_plan(
    plan: Dict[str, Any],
    transcript_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Valida contrato, temporalidade e referencias de um semantic_plan.json."""
    if not isinstance(plan, dict):
        raise SemanticPlanError("semantic_plan deve ser um objeto JSON (dict).")

    version = plan.get("schema_version")
    if version != SEMANTIC_PLAN_SCHEMA_VERSION:
        raise SemanticPlanError(
            f"schema_version invalida: {version!r} (esperado {SEMANTIC_PLAN_SCHEMA_VERSION!r})."
        )

    _require_str(plan, "tema_central", "semantic_plan")
    _require_str(plan, "tese_principal", "semantic_plan")

    max_dur, valid_seg_ids, valid_word_ids = _extract_transcript_bounds(transcript_data)

    topicos = plan.get("topicos")
    if not isinstance(topicos, list) or not topicos:
        raise SemanticPlanError("semantic_plan: 'topicos' deve ser uma lista nao vazia.")

    topic_ids: Set[str] = set()
    for idx, top in enumerate(topicos):
        ctx = f"topicos[{idx}]"
        if not isinstance(top, dict):
            raise SemanticPlanError(f"{ctx}: item invalido.")
        tid = _require_str(top, "topic_id", ctx)
        _require_str(top, "titulo", ctx)
        _require_str(top, "justificativa", ctx)
        _validate_time_window(top, ctx, max_dur)
        _validate_grounding_refs(top, ctx, valid_seg_ids, valid_word_ids)
        topic_ids.add(tid)

    for idx, arg in enumerate(plan.get("argumentos", [])):
        ctx = f"argumentos[{idx}]"
        if not isinstance(arg, dict):
            raise SemanticPlanError(f"{ctx}: item invalido.")
        _require_str(arg, "id", ctx)
        tid = _require_str(arg, "topic_id", ctx)
        if tid not in topic_ids:
            raise SemanticPlanError(f"{ctx}: topic_id '{tid}' nao declarado em topicos.")
        tipo = _require_str(arg, "tipo", ctx)
        if tipo not in VALID_ARGUMENT_TYPES:
            raise SemanticPlanError(f"{ctx}: tipo '{tipo}' invalido.")
        _require_str(arg, "resumo", ctx)
        _require_str(arg, "justificativa", ctx)
        _validate_time_window(arg, ctx, max_dur)
        _validate_grounding_refs(arg, ctx, valid_seg_ids, valid_word_ids)

    group_ids: Set[str] = set()
    for idx, grp in enumerate(plan.get("grupos_explicacao", [])):
        ctx = f"grupos_explicacao[{idx}]"
        if not isinstance(grp, dict):
            raise SemanticPlanError(f"{ctx}: item invalido.")
        gid = _require_str(grp, "explanation_group_id", ctx)
        tid = _require_str(grp, "topic_id", ctx)
        if tid not in topic_ids:
            raise SemanticPlanError(f"{ctx}: topic_id '{tid}' nao declarado em topicos.")
        _require_str(grp, "justificativa", ctx)
        _validate_time_window(grp, ctx, max_dur)
        _validate_grounding_refs(grp, ctx, valid_seg_ids, valid_word_ids)
        group_ids.add(gid)

    for idx, gv in enumerate(plan.get("ganchos_e_viradas", [])):
        ctx = f"ganchos_e_viradas[{idx}]"
        if not isinstance(gv, dict):
            raise SemanticPlanError(f"{ctx}: item invalido.")
        tipo = _require_str(gv, "tipo", ctx)
        if tipo not in {"gancho", "virada"}:
            raise SemanticPlanError(f"{ctx}: tipo '{tipo}' deve ser 'gancho' ou 'virada'.")
        _require_str(gv, "descricao", ctx)
        _require_str(gv, "justificativa", ctx)
        _validate_time_window(gv, ctx, max_dur)
        _validate_grounding_refs(gv, ctx, valid_seg_ids, valid_word_ids)

    for list_name in ("repeticoes_dispensaveis", "falsos_comecos"):
        for idx, item in enumerate(plan.get(list_name, [])):
            ctx = f"{list_name}[{idx}]"
            if not isinstance(item, dict):
                raise SemanticPlanError(f"{ctx}: item invalido.")
            _require_str(item, "texto", ctx)
            _require_str(item, "justificativa", ctx)
            _validate_time_window(item, ctx, max_dur, allow_zero_length=True)
            _validate_grounding_refs(item, ctx, valid_seg_ids, valid_word_ids)

    for idx, seg_dec in enumerate(plan.get("segmentos_editoriais", [])):
        ctx = f"segmentos_editoriais[{idx}]"
        if not isinstance(seg_dec, dict):
            raise SemanticPlanError(f"{ctx}: item invalido.")
        dec = _require_str(seg_dec, "decision", ctx)
        if dec not in VALID_DECISIONS:
            raise SemanticPlanError(f"{ctx}: decision '{dec}' invalida.")
        tid = seg_dec.get("topic_id")
        if tid and tid not in topic_ids:
            raise SemanticPlanError(f"{ctx}: topic_id '{tid}' nao declarado em topicos.")
        gid = seg_dec.get("explanation_group_id")
        if gid and group_ids and gid not in group_ids:
            raise SemanticPlanError(
                f"{ctx}: explanation_group_id '{gid}' nao declarado em grupos_explicacao."
            )
        _require_str(seg_dec, "justificativa", ctx)
        _validate_time_window(seg_dec, ctx, max_dur)
        _validate_grounding_refs(seg_dec, ctx, valid_seg_ids, valid_word_ids)

    for idx, iv in enumerate(plan.get("intencoes_visuais", [])):
        ctx = f"intencoes_visuais[{idx}]"
        if not isinstance(iv, dict):
            raise SemanticPlanError(f"{ctx}: item invalido.")
        camada = _require_str(iv, "camada", ctx)
        if camada not in VALID_EDITORIAL_LAYERS:
            raise SemanticPlanError(f"{ctx}: camada '{camada}' invalida.")
        _require_str(iv, "funcao_editorial", ctx)
        _require_str(iv, "justificativa", ctx)
        comp = iv.get("componente_motion_library")
        if comp is not None:
            if not isinstance(comp, str) or comp not in IMPLEMENTED_MOTION_COMPONENTS:
                raise SemanticPlanError(
                    f"{ctx}: componente_motion_library '{comp}' nao existe no Motion Library "
                    f"(implementados: {sorted(IMPLEMENTED_MOTION_COMPONENTS)})."
                )
        _validate_time_window(iv, ctx, max_dur, allow_zero_length=(camada == "L6_sound_design_sync"))
        _validate_grounding_refs(iv, ctx, valid_seg_ids, valid_word_ids)

    return plan


def load_semantic_plan(
    plan_path: Path,
    transcript_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Carrega e valida um semantic_plan.json."""
    if not plan_path.is_file():
        raise SemanticPlanError(f"semantic_plan.json nao encontrado: {plan_path}")
    try:
        data = json.loads(plan_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SemanticPlanError(f"JSON invalido em {plan_path}: {exc}") from exc
    return validate_semantic_plan(data, transcript_data=transcript_data)
