"""
core/component_catalog.py

Catalogo central explicito de executabilidade de componentes de motion.
Estados: 'implemented', 'legacy_only', 'planned', 'disabled'.
"""

from __future__ import annotations

from typing import Any, Dict, Set

COMPONENT_CATALOG: Dict[str, Dict[str, Any]] = {
    "titulo_heroi": {
        "component_id": "titulo_heroi",
        "layer": "L2_titulo_heroi_t10",
        "status": "implemented",
        "reason": "Componente T10 V2 (HTML/CSS/GSAP) via HyperFrames nos flancos livres.",
    },
    "micro_zoom_bate": {
        "component_id": "micro_zoom_bate",
        "layer": "L3_micro_zoom_bate",
        "status": "implemented",
        "reason": "cn.bate() + StageStateManager (GSAP scale em #base centrado no rosto).",
    },
    "lower_third": {
        "component_id": "lower_third",
        "layer": "L4_lower_third",
        "status": "implemented",
        "reason": "cn.lower_third() completo em HTML/CSS/GSAP via cenas.py + HyperFrames.",
    },
    "broll_industrial": {
        "component_id": "broll_industrial",
        "layer": "L5_broll_industrial",
        "status": "implemented",
        "reason": "cn.broll() com Ken Burns e contencao de paths via cenas.py + HyperFrames.",
    },
    "fullscreen_motion": {
        "component_id": "fullscreen_motion",
        "layer": "L5_fullscreen_motion",
        "status": "implemented",
        "reason": "Cena de Motion Design inedita em tela cheia (1920x1080 / 1080x1920) via HTML/CSS/GSAP em workspace/motions_custom/<id_cena>.html renderizada pelo HyperFrames.",
    },
    "sound_design_sync": {
        "component_id": "sound_design_sync",
        "layer": "L6_sound_design_sync",
        "status": "implemented",
        "reason": "RobustSoundBus (som.py) + mixagem 48kHz e loudnorm unico.",
    },
    "card_flutuante": {
        "component_id": "card_flutuante",
        "layer": "L4_lower_third",
        "status": "implemented",
        "reason": "cn.card_flutuante() lateral (esq/dir) em cenas.py + HyperFrames.",
    },
    "barra_progresso": {
        "component_id": "barra_progresso",
        "layer": "L4_lower_third",
        "status": "implemented",
        "reason": "cn.barra_progresso() em cenas.py + HyperFrames.",
    },
    "stepper": {
        "component_id": "stepper",
        "layer": "L4_lower_third",
        "status": "implemented",
        "reason": "cn.stepper() em cenas.py + HyperFrames.",
    },
    "pip_stage": {
        "component_id": "pip_stage",
        "layer": "L4_lower_third",
        "status": "implemented",
        "reason": "cn.pip_stage() + StageStateManager em cenas.py/estagio.py + HyperFrames.",
    },
    "split_stage": {
        "component_id": "split_stage",
        "layer": "L4_lower_third",
        "status": "implemented",
        "reason": "cn.split_stage() + CompositionManager em cenas.py/estagio.py + HyperFrames.",
    },
    "transicao_marca": {
        "component_id": "transicao_marca",
        "layer": "L4_lower_third",
        "status": "implemented",
        "reason": "cn.transicao_marca() com overlays/transicoes/ e RobustSoundBus.",
    },
    "hyperframes_cli": {
        "component_id": "hyperframes_cli",
        "layer": "L5_broll_industrial",
        "status": "implemented",
        "reason": "HyperFrames 0.9.5 local + render_rapido.py ativo.",
    },
}

# mapeamento camada -> component_id default
LAYER_DEFAULT_COMPONENT = {
    "L2_titulo_heroi_t10": "titulo_heroi",
    "L3_micro_zoom_bate": "micro_zoom_bate",
    "L4_lower_third": "lower_third",
    "L5_broll_industrial": "broll_industrial",
    "L5_fullscreen_motion": "fullscreen_motion",
    "L6_sound_design_sync": "sound_design_sync",
}


def resolve_component_status(element: Any) -> Dict[str, Any]:
    """Resolve status de um elemento/plano."""
    if isinstance(element, str):
        cid = element
        layer = None
    elif isinstance(element, dict):
        cid = element.get("component_id") or element.get("component") or element.get("id")
        layer = element.get("layer") or element.get("camada")
    else:
        cid = str(element)
        layer = None

    # se layer conhecida e cid ausente, usa default
    if (not cid or cid not in COMPONENT_CATALOG) and layer in LAYER_DEFAULT_COMPONENT:
        cid = LAYER_DEFAULT_COMPONENT[layer]

    entry = COMPONENT_CATALOG.get(cid)
    if entry is None:
        # tenta por layer
        if layer in LAYER_DEFAULT_COMPONENT:
            cid = LAYER_DEFAULT_COMPONENT[layer]
            entry = COMPONENT_CATALOG.get(cid)
    if entry is None:
        return {
            "component_id": cid,
            "status": "planned",
            "executable": False,
            "reason": "Componente nao catalogado; tratado como planned.",
        }
    status = entry["status"]
    executable = status == "implemented"
    return {
        "component_id": entry["component_id"],
        "status": status,
        "executable": executable,
        "reason": entry["reason"],
        "layer": entry.get("layer"),
    }


def is_implemented(element: Any) -> bool:
    return resolve_component_status(element).get("executable", False)
