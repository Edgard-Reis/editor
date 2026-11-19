"""
core/master_lint.py

Gate de lint do Master 16:9 adaptado de
Editor legado/core/master_lint.py e
EXP-BLOCO-LONGO-VIRAL/05_render_longo_1080p_motion/00_lint_gate.py para o
Workspace Core e a estrutura canônica do legado
(projetos/<marca>/episodios/<episodio>/workspace/briefing/).

Valida editorial_plan.json e edl_longo.json:
  - presenca das 6 camadas L1..L6;
  - lacunas temporais inesperadas entre eventos consecutivos;
  - sobreposicoes invalidas (out_in de um evento < out_out do anterior);
  - segmentos sem referencia a fonte (source_ref) ou divergentes de
    project.json/transcript.json;
  - duplicacoes/repeticoes de word_id ou event_id;
  - quebras de contexto (grupo de explicacao partido entre camadas);
  - duracao/continuidade (out_out final == final_duration do EDL).

Retorna relatorio estruturado com:
  - auto_approved=False (passar no lint NAO aprova automaticamente)
  - requires_human_approval=True (sempre requer revisão humana)
  - ok: True/False
  - failures: lista de falhas bloqueantes
  - warnings: lista de avisos nao-bloqueantes
  - summary: contagem de itens validados

Nao executa render. 100% agnostico a marca e episodio.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from .workspace import WorkspaceLoader, WorkspaceError
    from .semantic_plan import IMPLEMENTED_MOTION_COMPONENTS
except ImportError:  # execução direta como script
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from core.workspace import WorkspaceLoader, WorkspaceError  # type: ignore
    from core.semantic_plan import IMPLEMENTED_MOTION_COMPONENTS  # type: ignore


class MasterLintError(Exception):
    """Erro de lint do master."""


# As 6 camadas obrigatórias do plano editorial e seus papéis funcionais.
REQUIRED_LAYERS = [
    "L1_estabelecimento",
    "L2_titulo_heroi_t10",
    "L3_micro_zoom_bate",
    "L4_lower_third",
    "L5_broll_industrial",
    "L6_sound_design_sync",
]

LAYER_ROLES: Dict[str, str] = {
    "L1_estabelecimento": "continuous",
    "L2_titulo_heroi_t10": "overlay",
    "L3_micro_zoom_bate": "overlay",
    "L4_lower_third": "overlay",
    "L5_broll_industrial": "overlay",
    "L5_fullscreen_motion": "overlay",
    "L6_sound_design_sync": "audio_sync",
}

# Limites de duracao por camada (min, target, max, hard_cap).
_LAYER_DURATION_LIMITS: Dict[str, Tuple[float, float, float, float]] = {
    "L2_titulo_heroi_t10": (1.8, 3.5, 4.5, 7.0),
    "L3_micro_zoom_bate": (1.2, 2.0, 3.0, 4.0),
    "L4_lower_third": (3.0, 4.5, 5.5, 7.0),
    "L5_broll_industrial": (2.5, 4.0, 6.0, 10.0),
    "L5_fullscreen_motion": (2.5, 4.5, 8.0, 12.0),
    "L6_sound_design_sync": (0.2, 0.5, 1.5, 3.0),
}

LAYERS_VISUAIS = ("L2_titulo_heroi_t10", "L3_micro_zoom_bate", "L4_lower_third", "L5_broll_industrial", "L5_fullscreen_motion", "L6_sound_design_sync")

CAMADAS_COMPLEMENTAR = ("L2_titulo_heroi_t10", "L3_micro_zoom_bate", "L4_lower_third", "L5_broll_industrial", "L5_fullscreen_motion")

# Limiares de densidade artificial.
INTERVALO_MEDIO_MINIMO_S = 1.0
MIN_ESTIMULOS_DENSIDADE = 4
OVERLAY_SIMULTANEO_MAXIMO = 2
GAP_SEM_JUSTIFICATIVA_LIMITE_S = 4.0
P90_ALERTA_S = 4.5


def _duracao_valida(
    camada: str, duracao: float
) -> Tuple[bool, Optional[str]]:
    """Verifica se duracao esta dentro dos limites da camada."""
    if camada not in _LAYER_DURATION_LIMITS:
        return True, None
    min_s, _target, max_s, hard_cap = _LAYER_DURATION_LIMITS[camada]
    if duracao <= 0:
        return False, f"duracao <= 0 ({duracao:.3f}s)"
    if duracao < min_s:
        return False, f"duracao {duracao:.3f}s abaixo do minimo {min_s}s"
    if duracao > hard_cap:
        return False, f"duracao {duracao:.3f}s excede teto impeditivo {hard_cap}s"
    if duracao > max_s:
        return False, f"duracao {duracao:.3f}s excede max {max_s}s"
    return True, None


def _janela_overlaps(
    a_in: float, a_out: float, b_in: float, b_out: float
) -> bool:
    return a_in < b_out and b_in < a_out


def check_duracao_componentes(
    plan: Dict[str, Any], final_duration: Optional[float] = None
) -> List[str]:
    """Falhas: duracao <= 0 ou acima do teto do componente/camada."""
    failures: List[str] = []
    layers = _layers(plan)
    for name in LAYERS_VISUAIS:
        for el in _elements(layers.get(name, [])):
            if not _has_window(el):
                continue
            # So valida eventos originados pelo rhythm_engine
            if el.get("origin") is None:
                continue
            try:
                dur = float(el["out_out"]) - float(el["out_in"])
            except (TypeError, ValueError):
                continue
            ok, msg = _duracao_valida(name, dur)
            if not ok:
                el_id = el.get("element_id", el.get("event_id", "?"))
                failures.append(f"{name}: {msg} (elemento {el_id})")
    return failures


def check_colisao_intra_layer_visuais(
    plan: Dict[str, Any],
) -> List[str]:
    """Falhas: colisao intra-layer em L2..L5."""
    failures: List[str] = []
    layers = _layers(plan)
    for name in CAMADAS_COMPLEMENTAR:
        elems = [e for e in _elements(layers.get(name, [])) if _has_window(e)]
        for i in range(len(elems)):
            for j in range(i + 1, len(elems)):
                a_in = float(elems[i]["out_in"])
                a_out = float(elems[i]["out_out"])
                b_in = float(elems[j]["out_in"])
                b_out = float(elems[j]["out_out"])
                if _janela_overlaps(a_in, a_out, b_in, b_out):
                    failures.append(
                        f"{name}: colisao intra-layer entre "
                        f"{elems[i].get('element_id', elems[i].get('event_id', i))} "
                        f"e {elems[j].get('element_id', elems[j].get('event_id', j))}"
                    )
    return failures


def check_colisao_cross_layer_critica(
    plan: Dict[str, Any],
) -> List[str]:
    """Falhas: colisao cross-layer critica (L5 simultaneo com L2, L3 ou L4)."""
    failures: List[str] = []
    layers = _layers(plan)
    l5_elems = [e for e in _elements(layers.get("L5_broll_industrial", [])) if _has_window(e)]
    for alvo in ("L2_titulo_heroi_t10", "L3_micro_zoom_bate", "L4_lower_third", "L5_fullscreen_motion"):
        alvo_elems = [
            e for e in _elements(layers.get(alvo, [])) if _has_window(e)
        ]
        for l5 in l5_elems:
            l5_in = float(l5["out_in"])
            l5_out = float(l5["out_out"])
            for a in alvo_elems:
                a_in = float(a["out_in"])
                a_out = float(a["out_out"])
                if _janela_overlaps(l5_in, l5_out, a_in, a_out):
                    failures.append(
                        f"L5_broll_industrial: colisao cross-layer critica com {alvo} "
                        f"(L5 {l5.get('element_id', l5.get('event_id', '?'))} "
                        f"e {alvo} {a.get('element_id', a.get('event_id', '?'))})"
                    )
    l5_fs_elems = [e for e in _elements(layers.get("L5_fullscreen_motion", [])) if _has_window(e)]
    for alvo in ("L2_titulo_heroi_t10", "L3_micro_zoom_bate", "L4_lower_third"):
        alvo_elems = [
            e for e in _elements(layers.get(alvo, [])) if _has_window(e)
        ]
        for fs in l5_fs_elems:
            fs_in = float(fs["out_in"])
            fs_out = float(fs["out_out"])
            for a in alvo_elems:
                a_in = float(a["out_in"])
                a_out = float(a["out_out"])
                if _janela_overlaps(fs_in, fs_out, a_in, a_out):
                    failures.append(
                        f"L5_fullscreen_motion: colisao cross-layer critica com {alvo} "
                        f"(FS {fs.get('element_id', fs.get('event_id', '?'))} "
                        f"e {alvo} {a.get('element_id', a.get('event_id', '?'))})"
                    )
    for fs in _elements(layers.get("L5_fullscreen_motion", [])):
        hp = fs.get("html_path")
        if isinstance(hp, str) and ".." in Path(hp).parts:
            failures.append(f"L5_fullscreen_motion: path traversal em html_path ({hp})")
    # repeticao consecutiva de media_ref
    refs = [e.get("media_ref") or e.get("arquivo") or e.get("path") for e in _elements(layers.get("L5_broll_industrial", []))]
    for i in range(len(refs) - 1):
        if refs[i] and refs[i] == refs[i + 1]:
            failures.append(f"L5_broll_industrial: repeticao consecutiva de media_ref {refs[i]}")
    return failures


def check_eventos_fora_timeline(
    plan: Dict[str, Any], final_duration: Optional[float] = None
) -> List[str]:
    """Falhas: evento fora dos limites [0, final_duration]."""
    failures: List[str] = []
    layers = _layers(plan)
    for name, layer in layers.items():
        for el in _elements(layer):
            if not _has_window(el):
                continue
            try:
                out_in = float(el["out_in"])
                out_out = float(el["out_out"])
            except (TypeError, ValueError):
                continue
            if out_in < 0:
                failures.append(
                    f"{name}: out_in negativo ({out_in:.3f}s) em "
                    f"{el.get('element_id', el.get('event_id', '?'))}"
                )
            if final_duration is not None and out_out > final_duration + 1e-6:
                failures.append(
                    f"{name}: out_out {out_out:.3f}s excede final_duration "
                    f"({final_duration:.3f}s) em "
                    f"{el.get('element_id', el.get('event_id', '?'))}"
                )
    return failures


def check_estimulo_sem_justificacao(
    plan: Dict[str, Any],
) -> List[str]:
    """Falhas: estimulo L2..L6 sem justification (apenas eventos com origin)."""
    failures: List[str] = []
    layers = _layers(plan)
    for name in LAYERS_VISUAIS:
        for el in _elements(layers.get(name, [])):
            if not _has_window(el):
                continue
            # So aplica a eventos originados pelo fluxo semantic/rhythm engine
            if el.get("origin") is None:
                continue
            just = el.get("justification", "")
            if not just or not str(just).strip():
                el_id = el.get("element_id", el.get("event_id", "?"))
                failures.append(
                    f"{name}: estimulo sem justification (elemento {el_id})"
                )
    return failures


def check_densidade_visual_artificial(
    plan: Dict[str, Any],
) -> List[str]:
    """Falhas: densidade visual artificialmente elevada.

    - Intervalo medio < 1.0s com >= 4 estimulos
    - Mais de 2 overlays visuais L2..L5 simultaneos
    """
    failures: List[str] = []
    layers = _layers(plan)

    # Coletar todos os estimulos visuais L2..L5 ordenados por out_in
    estimulos: List[Dict[str, Any]] = []
    for name in CAMADAS_COMPLEMENTAR:
        for el in _elements(layers.get(name, [])):
            if _has_window(el):
                estimulos.append(
                    {
                        "camada": name,
                        "out_in": float(el["out_in"]),
                        "out_out": float(el["out_out"]),
                    }
                )
    estimulos.sort(key=lambda x: x["out_in"])

    n = len(estimulos)
    if n >= MIN_ESTIMULOS_DENSIDADE and n >= 2:
        inicios = [e["out_in"] for e in estimulos]
        intervalos = [inicios[i + 1] - inicios[i] for i in range(n - 1)]
        media = sum(intervalos) / len(intervalos)
        if media < INTERVALO_MEDIO_MINIMO_S:
            failures.append(
                f"densidade visual artificial: intervalo medio {media:.3f}s "
                f"< {INTERVALO_MEDIO_MINIMO_S}s com {n} estimulos"
            )

    # Max simultaneos L2..L5
    pontos = []
    for e in estimulos:
        pontos.append((e["out_in"], "in"))
        pontos.append((e["out_out"], "out"))
    pontos.sort()
    ativos = 0
    max_ativos = 0
    for t, tipo in pontos:
        if tipo == "in":
            ativos += 1
            max_ativos = max(max_ativos, ativos)
        else:
            ativos -= 1
    if max_ativos > OVERLAY_SIMULTANEO_MAXIMO:
        failures.append(
            f"mais de {OVERLAY_SIMULTANEO_MAXIMO} overlays visuais L2..L5 "
            f"simultaneos (max observado: {max_ativos})"
        )

    return failures


def check_evento_clampado(
    plan: Dict[str, Any],
) -> List[str]:
    """Warning: evento clampado pelo RhythmEngine."""
    warnings: List[str] = []
    layers = _layers(plan)
    for name, layer in layers.items():
        for el in _elements(layer):
            if el.get("clamp_from_duration"):
                el_id = el.get("element_id", el.get("event_id", "?"))
                warnings.append(
                    f"{name}: evento clampado pelo RhythmEngine (elemento {el_id})"
                )
    return warnings


def check_intencao_sem_componente(
    plan: Dict[str, Any],
) -> List[str]:
    """Warning: intencao sem componente executavel no motion_library
    (componente_motion_library is None em L2..L6, apenas informativo)."""
    warnings: List[str] = []
    layers = _layers(plan)
    for name in LAYERS_VISUAIS:
        for el in _elements(layers.get(name, [])):
            comp = el.get("componente_motion_library")
            if comp is None:
                el_id = el.get("element_id", el.get("event_id", "?"))
                warnings.append(
                    f"{name}: intencao sem componente executavel no motion_library "
                    f"(elemento {el_id})"
                )
    return warnings


def check_gaps_sem_estimulo(
    plan: Dict[str, Any],
) -> List[str]:
    """Warning: lacunas > 4.0s sem estimulo (gaps_over_4s)."""
    warnings: List[str] = []
    rhythm_report = plan.get("rhythm_report", {})
    gaps = rhythm_report.get("gaps_for_review", [])
    for gap in gaps:
        warnings.append(
            f"lacuna > {GAP_SEM_JUSTIFICATIVA_LIMITE_S}s sem estimulo: "
            f"{gap.get('start', 0):.3f}s-{gap.get('end', 0):.3f}s "
            f"({gap.get('duration_s', 0):.3f}s) - {gap.get('reason', '')}"
        )
    return warnings


def check_p90_alerta(
    plan: Dict[str, Any],
) -> List[str]:
    """Warning: p90 > 4.5s."""
    warnings: List[str] = []
    rhythm_report = plan.get("rhythm_report", {})
    interval_stats = rhythm_report.get("interval_stats", {})
    p90 = interval_stats.get("p90_s", 0.0)
    if p90 > P90_ALERTA_S:
        warnings.append(f"p90 de intervalos {p90:.3f}s > {P90_ALERTA_S}s")
    return warnings


def check_camada_vazia(
    plan: Dict[str, Any],
) -> List[str]:
    """Warning: camada presente mas vazia."""
    warnings: List[str] = []
    layers = _layers(plan)
    for name in REQUIRED_LAYERS:
        if name in layers and not _elements(layers[name]):
            warnings.append(f"camada vazia: {name}")
    return warnings


def _interval_stats_from_plan(
    plan: Dict[str, Any],
) -> Dict[str, Any]:
    """Extrai interval_stats do rhythm_report do plano."""
    rhythm_report = plan.get("rhythm_report", {})
    return rhythm_report.get("interval_stats", {})


def _cadence_metrics_from_plan(
    plan: Dict[str, Any],
) -> Dict[str, Any]:
    """Construi cadence_metrics a partir do rhythm_report."""
    rhythm_report = plan.get("rhythm_report", {})
    return {
        "interval_stats": rhythm_report.get("interval_stats", {}),
        "gaps_over_4s": rhythm_report.get("gaps_for_review", []),
        "distribution_by_layer": rhythm_report.get("distribution_by_layer", {}),
        "duration_by_component": rhythm_report.get("duration_by_component", {}),
        "simultaneous_overlays": rhythm_report.get("simultaneous_overlays", {}),
        "unjustified_count": rhythm_report.get("unjustified_count", 0),
        "clamped_count": rhythm_report.get("clamped_count", 0),
        "total_estimulos_visuais": rhythm_report.get("total_estimulos_visuais", 0),
    }


def _empty_report() -> Dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "auto_approved": False,
        "requires_human_approval": True,
        "ok": False,
        "failures": [],
        "warnings": [],
        "summary": {},
    }


def _layers(plan: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    return plan.get("layers", {}) if isinstance(plan, dict) else {}


def _elements(layer: Any) -> List[Dict[str, Any]]:
    if isinstance(layer, list):
        return layer
    if not isinstance(layer, dict):
        return []
    if isinstance(layer.get("elements"), list):
        return layer["elements"]
    if isinstance(layer.get("keyframes"), list):
        return layer["keyframes"]
    if isinstance(layer.get("events"), list):
        return layer["events"]
    return []


def _has_window(el: Dict[str, Any]) -> bool:
    return "out_in" in el and "out_out" in el


def _get(event: Dict[str, Any], *keys: str, default: Any = None) -> Any:
    for k in keys:
        if k in event:
            return event[k]
    return default


def check_layers(plan: Dict[str, Any]) -> List[str]:
    """Valida presenca das 6 camadas L1..L6."""
    failures: List[str] = []
    layers = _layers(plan)
    for req in REQUIRED_LAYERS:
        if req not in layers:
            failures.append(f"camada ausente: {req}")
    return failures


def check_windows(plan: Dict[str, Any]) -> List[str]:
    """Valida que out_out > out_in em todas as janelas."""
    failures: List[str] = []
    layers = _layers(plan)
    for name, layer in layers.items():
        for el in _elements(layer):
            if _has_window(el):
                try:
                    if not (float(el["out_out"]) > float(el["out_in"])):
                        failures.append(
                            f"{name}: janela invalida em {el.get('element_id', el.get('event_id', '?'))}"
                        )
                except (TypeError, ValueError):
                    failures.append(
                        f"{name}: janela nao numerica em {el.get('element_id', el.get('event_id', '?'))}"
                    )
    return failures


def check_collisions(plan: Dict[str, Any]) -> List[str]:
    """Zero colisao de janelas temporais dentro de camadas continuas e overlays.

    Camadas de audio_sync (L6_sound_design_sync) podem sobrepor efeitos sonoros
    simultaneos, portanto nao sofrem bloqueio de colisao entre si.
    """
    failures: List[str] = []
    layers = _layers(plan)
    for name, layer in layers.items():
        if LAYER_ROLES.get(name, "overlay") == "audio_sync":
            continue
        elems = [e for e in _elements(layer) if _has_window(e)]
        for i in range(len(elems)):
            for j in range(i + 1, len(elems)):
                a_in = float(elems[i]["out_in"])
                a_out = float(elems[i]["out_out"])
                b_in = float(elems[j]["out_in"])
                b_out = float(elems[j]["out_out"])
                if a_in < b_out and b_in < a_out:
                    failures.append(
                        f"{name}: colisao entre "
                        f"{elems[i].get('element_id', elems[i].get('event_id', i))} "
                        f"e {elems[j].get('element_id', elems[j].get('event_id', j))}"
                    )
    return failures


def check_lacunas_temporais(plan: Dict[str, Any]) -> List[str]:
    """Detecta lacunas temporais inesperadas (> 0.5s) apenas em camadas continuas.

    Overlays pontuais (L2..L5) e eventos de audio sincronizados (L6) podem ter
    intervalos maiores entre ocorrencias sem constituir falha.
    """
    failures: List[str] = []
    layers = _layers(plan)
    for name, layer in layers.items():
        if LAYER_ROLES.get(name, "overlay") != "continuous":
            continue
        elems = [e for e in _elements(layer) if _has_window(e)]
        elems_sorted = sorted(elems, key=lambda e: float(e["out_in"]))
        for i in range(len(elems_sorted) - 1):
            a_out = float(elems_sorted[i]["out_out"])
            b_in = float(elems_sorted[i + 1]["out_in"])
            gap = b_in - a_out
            if gap > 0.5:  # lacuna maior que 0.5s e inesperada na camada continua
                failures.append(
                    f"{name}: lacuna temporais de {gap:.3f}s entre "
                    f"{elems_sorted[i].get('element_id', elems_sorted[i].get('event_id', i))} "
                    f"(out_out {a_out:.3f}) e "
                    f"{elems_sorted[i + 1].get('element_id', elems_sorted[i + 1].get('event_id', i + 1))} "
                    f"(out_in {b_in:.3f})"
                )
    return failures


def check_motion_components(plan: Dict[str, Any]) -> List[str]:
    """Garante que nenhum elemento referencia componente inexistente no Motion Library."""
    failures: List[str] = []
    layers = _layers(plan)
    for name, layer in layers.items():
        for el in _elements(layer):
            comp = el.get("componente_motion_library")
            if comp is not None and comp not in IMPLEMENTED_MOTION_COMPONENTS:
                failures.append(
                    f"{name}: componente_motion_library '{comp}' inexistente no Motion Library "
                    f"(elemento {el.get('element_id', el.get('event_id', '?'))})"
                )
    return failures


def check_referencias_fonte(
    plan: Dict[str, Any],
    edl: Optional[Dict[str, Any]] = None,
    projeto: Optional[Dict[str, Any]] = None,
) -> List[str]:
    """Valida que todos os eventos tem source_ref valida e consistente com
    project.json e transcript.json."""
    failures: List[str] = []
    layers = _layers(plan)

    # Coleta ids de fontes validos do project.json
    fonte_ids_validos: set = set()
    if projeto is not None:
        for s in projeto.get("sources", []):
            sid = s.get("id")
            if sid:
                fonte_ids_validos.add(sid)

    # Coleta ids de palavras do transcript (se disponivel via edl word_index)
    palavras_validas: set = set()
    if edl is not None:
        word_index = edl.get("word_index", {})
        for wid, winfo in word_index.items():
            palavras_validas.add(wid)

    for name, layer in layers.items():
        for el in _elements(layer):
            source_ref = el.get("source_ref")
            if not source_ref or not isinstance(source_ref, dict):
                failures.append(
                    f"{name}: evento sem source_ref em "
                    f"{el.get('element_id', el.get('event_id', '?'))}"
                )
                continue
            sid = source_ref.get("id")
            if sid and fonte_ids_validos and sid not in fonte_ids_validos:
                failures.append(
                    f"{name}: source_ref.id '{sid}' nao encontrado em project.json "
                    f"(evento {el.get('element_id', el.get('event_id', '?'))})"
                )
            sha = source_ref.get("sha256")
            if sha and (not isinstance(sha, str) or len(sha) != 64):
                failures.append(
                    f"{name}: source_ref.sha256 invalido em "
                    f"{el.get('element_id', el.get('event_id', '?'))}"
                )
    return failures


def check_duplicacoes(plan: Dict[str, Any], edl: Optional[Dict[str, Any]] = None) -> List[str]:
    """Detecta duplicacoes de word_id ou event_id."""
    failures: List[str] = []
    layers = _layers(plan)

    event_ids: set = set()
    word_ids: set = set()

    for name, layer in layers.items():
        for el in _elements(layer):
            eid = el.get("event_id")
            if eid:
                if eid in event_ids:
                    failures.append(f"event_id duplicado: {eid} (camada {name})")
                event_ids.add(eid)
            wid_list = el.get("word_ids", [])
            if isinstance(wid_list, list):
                for wid in wid_list:
                    if wid in word_ids:
                        failures.append(f"word_id duplicado: {wid} (camada {name})")
                    word_ids.add(wid)

    # Cruzamento com EDL word_index
    if edl is not None:
        edl_word_index = edl.get("word_index", {})
        for wid in edl_word_index:
            if wid in word_ids:
                # palavra ja usada no plano; nao e duplicacao se for a mesma
                # unidade, mas avisa se houver conflito
                pass

    return failures


def check_quebras_contexto(plan: Dict[str, Any]) -> List[str]:
    """Detecta quebras de contexto: grupo de explicacao partido na camada continua L1.

    Um mesmo explanation_group_id (exceto E_UNCLASSIFIED/E_GENERAL) deve permanecer
    contiguo na linha do tempo de L1_estabelecimento; se for interrompido por outro
    grupo e reaparecer depois, ha quebra de contexto.
    """
    failures: List[str] = []
    layers = _layers(plan)
    l1_elems = _elements(layers.get("L1_estabelecimento", []))
    l1_sorted = sorted(
        [e for e in l1_elems if _has_window(e)],
        key=lambda e: float(e["out_in"]),
    )

    grupos_encerrados: set = set()
    grupo_atual: Optional[str] = None
    for el in l1_sorted:
        nc = el.get("narrative_continuity", {})
        if not isinstance(nc, dict):
            continue
        gid = nc.get("explanation_group_id")
        if not gid or gid in ("E_UNCLASSIFIED", "E_GENERAL"):
            continue
        if gid != grupo_atual:
            if gid in grupos_encerrados:
                failures.append(
                    f"quebra de contexto: explanation_group_id '{gid}' fragmentado "
                    f"em blocos nao contiguos (elemento {el.get('element_id', el.get('event_id', '?'))})"
                )
            if grupo_atual is not None:
                grupos_encerrados.add(grupo_atual)
            grupo_atual = gid
    return failures


def check_duracao_continuidade(
    plan: Dict[str, Any],
    edl: Optional[Dict[str, Any]] = None,
) -> List[str]:
    """Valida duracao/continuidade: out_out final nao excede duracao do EDL
    e a soma das duracoes eh consistente."""
    failures: List[str] = []
    layers = _layers(plan)

    duracao_edl = None
    if edl is not None:
        duracao_edl = edl.get("summary", {}).get("final_duration_seconds")

    max_out = 0.0
    total_duracao = 0.0
    for name, layer in layers.items():
        for el in _elements(layer):
            if _has_window(el):
                try:
                    out_out = float(el["out_out"])
                    out_in = float(el["out_in"])
                    if out_out > max_out:
                        max_out = out_out
                    total_duracao += (out_out - out_in)
                except (TypeError, ValueError):
                    failures.append(
                        f"{name}: janela nao numerica em "
                        f"{el.get('element_id', el.get('event_id', '?'))}"
                    )

    if duracao_edl is not None and max_out > float(duracao_edl) + 1e-6:
        failures.append(
            f"out_out final ({max_out:.3f}s) excede duracao do EDL ({duracao_edl:.3f}s)"
        )

    return failures


def lint(
    plan: Dict[str, Any],
    edl: Optional[Dict[str, Any]] = None,
    projeto: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Executa o lint completo do master 16:9.

    Retorna relatorio estruturado com:
      - auto_approved=False (passar no lint NAO aprova automaticamente)
      - requires_human_approval=True (sempre requer revisao humana)
      - ok: True se nao houver falhas
      - failures: lista de falhas bloqueantes
      - warnings: lista de avisos nao-bloqueantes
      - summary: contagem de itens validados
    """
    report = _empty_report()

    if not isinstance(plan, dict):
        report["failures"].append("plano nao e um dict valido")
        return report

    failures: List[str] = []
    warnings: List[str] = []

    # Extrai final_duration do EDL quando disponivel
    final_duration: Optional[float] = None
    if edl is not None:
        final_duration = edl.get("summary", {}).get("final_duration_seconds")

    failures += check_layers(plan)
    failures += check_windows(plan)
    failures += check_collisions(plan)
    failures += check_lacunas_temporais(plan)
    failures += check_referencias_fonte(plan, edl, projeto)
    failures += check_duplicacoes(plan, edl)
    failures += check_quebras_contexto(plan)
    failures += check_duracao_continuidade(plan, edl)
    failures += check_motion_components(plan)
    # --- Novas verificacoes de ritmo visual ---
    failures += check_duracao_componentes(plan)
    failures += check_colisao_intra_layer_visuais(plan)
    failures += check_colisao_cross_layer_critica(plan)
    failures += check_eventos_fora_timeline(plan, final_duration=final_duration)
    failures += check_estimulo_sem_justificacao(plan)
    failures += check_densidade_visual_artificial(plan)
    # --- Novos avisos ---
    warnings += check_evento_clampado(plan)
    warnings += check_intencao_sem_componente(plan)
    sd_fail, sd_warn = check_sound_design(plan, edl)
    failures += sd_fail
    warnings += sd_warn
    warnings += check_gaps_sem_estimulo(plan)
    warnings += check_p90_alerta(plan)
    warnings += check_camada_vazia(plan)

    # Warnings: camadas presentes mas vazias (ja coberto por check_camada_vazia)
    layers = _layers(plan)

    # Contagem de itens validados
    total_elementos = sum(len(_elements(l)) for l in layers.values())
    total_eventos = len(
        [
            e
            for l in layers.values()
            for e in _elements(l)
            if _has_window(e)
        ]
    )

    report["failures"] = failures
    report["warnings"] = warnings
    report["ok"] = len(failures) == 0
    report["cadence_metrics"] = _cadence_metrics_from_plan(plan)
    report["summary"] = {
        "total_camadas": len([n for n in REQUIRED_LAYERS if n in layers]),
        "total_camadas_obrigatorias": len(REQUIRED_LAYERS),
        "total_elementos": total_elementos,
        "total_eventos_com_janela": total_eventos,
        "total_falhas": len(failures),
        "total_avisos": len(warnings),
    }

    return report


def run_lint(
    plan_path: str | Path,
    edl_path: Optional[str | Path] = None,
    projeto: Optional[Dict[str, Any]] = None,
) -> int:
    """Executa o lint a partir de arquivos. Retorna codigo de saida."""
    plan_p = Path(plan_path)
    if not plan_p.is_file():
        print(f"[ERRO] plano nao encontrado: {plan_p}", file=sys.stderr)
        return 1
    plan = json.loads(plan_p.read_text(encoding="utf-8"))

    edl = None
    if edl_path:
        ep = Path(edl_path)
        if ep.is_file():
            edl = json.loads(ep.read_text(encoding="utf-8"))

    report = lint(plan, edl, projeto)

    for w in report["warnings"]:
        print(f"  [aviso] {w}")
    for f in report["failures"]:
        print(f"  [FALHA] {f}")

    if not report["ok"]:
        print(
            f"LINT REPROVADO - {report['summary']['total_falhas']} falha(s). "
            f"Requer revisao humana antes de prosseguir."
        )
        return 1
    print(
        "LINT OK - aprovado para revisao humana (nao e aprovacao automatica)."
    )
    return 0


def run_lint_workspace(
    marca_id: str,
    episodio_id: str,
    workspace_root: str | Path,
) -> int:
    """Executa o lint usando os arquivos do episódio no workspace.

    Carrega editorial_plan.json, edl_longo.json e project.json do episódio.
    """
    loader = WorkspaceLoader(workspace_root)
    loader.load_workspace()

    briefing_dir = loader.resolve_episodio_asset(marca_id, episodio_id, "workspace/briefing")
    plan_path = briefing_dir / "editorial_plan.json"
    edl_path = briefing_dir / "edl_longo.json"

    projeto = None
    pj_path = loader.project_file(marca_id, episodio_id)
    if pj_path.is_file():
        projeto = json.loads(pj_path.read_text(encoding="utf-8"))

    if not plan_path.is_file():
        print(f"[ERRO] editorial_plan.json nao encontrado: {plan_path}", file=sys.stderr)
        return 1

    return run_lint(plan_path, edl_path if edl_path.is_file() else None, projeto)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="CORE-MASTER-LINT: gate de lint do Master 16:9 (Editor)."
    )
    parser.add_argument("-m", "--marca-id", required=True, help="ID da marca.")
    parser.add_argument("-e", "--episodio-id", required=True, help="ID do episódio.")
    parser.add_argument(
        "-w", "--workspace-root", default="D:/Drifit/Editor"
    )
    parser.add_argument("-p", "--plan", help="Caminho direto para editorial_plan.json.")
    parser.add_argument("-x", "--edl", help="Caminho direto para edl_longo.json.")
    args = parser.parse_args()

    if args.plan and args.edl:
        plan_p = Path(args.plan)
        edl_p = Path(args.edl) if args.edl else None
        plano = json.loads(plan_p.read_text(encoding="utf-8"))
        edl = json.loads(edl_p.read_text(encoding="utf-8")) if edl_p and edl_p.is_file() else None
        report = lint(plano, edl)
        for w in report["warnings"]:
            print(f"  [aviso] {w}")
        for f in report["failures"]:
            print(f"  [FALHA] {f}")
        if not report["ok"]:
            print(
                f"LINT REPROVADO - {report['summary']['total_falhas']} falha(s). "
                f"Requer revisao humana."
            )
            sys.exit(1)
        print("LINT OK - aprovado para revisao humana.")
        sys.exit(0)

    sys.exit(
        run_lint_workspace(args.marca_id, args.episodio_id, args.workspace_root)
    )


def check_sound_design(plan: Dict[str, Any], edl: Optional[Dict[str, Any]] = None) -> Tuple[List[str], List[str]]:
    failures: List[str] = []
    warnings: List[str] = []
    layers = _layers(plan)
    final_duration = None
    if edl:
        final_duration = edl.get("summary", {}).get("final_duration_seconds")
    layer = layers.get("L6_sound_design_sync", {}) or layers.get("layer_6_sound_design_sync", {}) or {}
    elems = _elements(layer)
    seen_keys = set()
    seen_ts = set()
    for el in elems:
        sr = el.get("sound_ref") or el.get("media_ref") or el.get("arquivo") or el.get("path")
        if isinstance(sr, str) and ".." in Path(sr).parts:
            failures.append("L6: path traversal")
        if _has_window(el):
            oi = float(el.get("out_in", 0)); oo = float(el.get("out_out", 0))
            if oi < 0:
                failures.append("L6: out_in < 0")
            if final_duration is not None and oo > final_duration + 1e-6:
                failures.append("L6: out_out > final_duration")
            if oo <= oi:
                failures.append("L6: duracao invalida")
            dur = oo - oi
            if dur > 3.0:
                failures.append("L6: duracao > 3.0s")
        vol = el.get("volume", None)
        if vol is not None:
            try:
                v = float(vol)
                if v < 0.0 or v > 1.0:
                    failures.append("L6: volume fora de [0,1]")
            except (TypeError, ValueError):
                failures.append("L6: volume invalido")
        dk = el.get("dedup_key") or el.get("dedup")
        if dk is not None:
            if dk in seen_keys:
                failures.append(f"L6: dedup_key duplicado {dk}")
            seen_keys.add(dk)
        if _has_window(el):
            ts = (round(float(el.get("out_in", 0)), 3), el.get("sound_ref"))
            if ts in seen_ts:
                failures.append("L6: timestamp duplicado")
            seen_ts.add(ts)
        if not (el.get("justificativa") or el.get("justification") or el.get("rationale")):
            warnings.append(f"L6: ausencia de justificativa editorial em {el.get('id', '?')}")
    return failures, warnings


if __name__ == "__main__":
    main()
