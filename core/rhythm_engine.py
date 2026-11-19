"""
core/rhythm_engine.py

Motor de ritmo visual editorial (deterministico, local) para o Editor.
Complementa o semantic_plan.json sem altera-lo nem substitui-lo.

Regras de duracao por camada/componente:
  * L2_titulo_heroi_t10 (componente_motion_library='titulo_heroi'):
      min=1.8s, target=3.5s, max=4.5s (teto impeditivo=7.0s).
      Janela longa ancora no gatilho inicial [out_in, min(out_out, out_in+3.5s)].
  * L4_lower_third (componente_motion_library=None): min=3.0s, target=4.5s,
      max=5.5s (teto=7.0s). Max 1 na abertura, sem colidir com L2/L5.
  * L3_micro_zoom_bate (componente_motion_library=None): min=1.2s, target=2.0s,
      max=3.0s (teto=4.0s), cooldown=2.0s.
  * L5_broll_industrial (componente_motion_library=None): min=2.5s, target=4.0s,
      max=6.0s (teto=10.0s), proibido sobrepor L2 ou L4.
  * L6_sound_design_sync (componente_motion_library=None): min=0.2s, target=0.5s,
      max=1.5s, pareado a entradas L2/L4/L5, sem duplicar timestamp+som.

Precedencia e deduplicacao:
  * Semantic-first: preserva todas as intencoes do semantic_plan
    (origin='semantic_plan'), aplicando clamp por componente.
  * Microeventos complementares (origin='rhythm_engine') so quando houver
    justificativa deterministica clara (mudanca de topico/argumento/
    grupo_explicacao, pausa/fronteira de unidade > 0.35s no alignment,
    ou enfase explicita) respeitando cooldown e ausencia de colisao.
  * Lacuna > 4.0s sem justificativa editorial: nao inventar evento
    artificial; registrar em gaps_for_review.
  * Todo elemento L2..L6 recebe origin ('semantic_plan' | 'rhythm_engine')
    e dedup_key deterministico.

Nao modifica core/semantic_plan.py, core/briefing.py, core/edl_builder.py,
core/master_lint.py. Nao executa render. Nao depende de API comercial externa.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

try:
    from .semantic_plan import IMPLEMENTED_MOTION_COMPONENTS as _IMPLEMENTED_COMPONENTS
except Exception:
    _IMPLEMENTED_COMPONENTS = {"titulo_heroi", "lower_third"}

# Limites por camada (L2..L6) e componentes.
# Cada entrada: (min_s, target_s, max_s, hard_cap_s, cooldown_s)
_LAYER_LIMITS: Dict[str, Tuple[float, float, float, float, float]] = {
    "L2_titulo_heroi_t10": (1.8, 3.5, 4.5, 7.0, 0.0),
    "L3_micro_zoom_bate": (1.2, 2.0, 3.0, 4.0, 2.0),
    "L4_lower_third": (3.0, 4.5, 5.5, 7.0, 0.0),
    "L5_broll_industrial": (2.5, 4.0, 6.0, 10.0, 8.0),
    "L5_fullscreen_motion": (2.5, 4.5, 8.0, 12.0, 2.0),
    "L6_sound_design_sync": (0.2, 0.5, 1.5, 3.0, 0.5),
}

LAYERS_VISUAIS = ("L2_titulo_heroi_t10", "L3_micro_zoom_bate", "L4_lower_third", "L5_broll_industrial", "L5_fullscreen_motion", "L6_sound_design_sync")

CAMADAS_COMPLEMENTAR = ("L2_titulo_heroi_t10", "L3_micro_zoom_bate", "L4_lower_third", "L5_broll_industrial", "L5_fullscreen_motion")

# Lacuna acima da qual nao se inventa evento artificial.
GAP_SEM_JUSTIFICATIVA_LIMITE_S = 4.0

# Limiar de pausa/fronteira no alignment para justificar microevento.
PAUSA_FRONTEIRA_LIMITE_S = 0.35

# Intervalor medio abaixo do qual a densidade e considerada artificial.
INTERVALO_MEDIO_MINIMO_S = 1.0
MIN_ESTIMULOS_DENSIDADE = 4
OVERLAY_SIMULTANEO_MAXIMO = 2


def r3(value: float) -> float:
    """Arredonda para milissegundos, evitando -0.0."""
    rounded = round(float(value) + 0.0, 3)
    return 0.0 if rounded == 0 else rounded


def _clamp_duracao(
    duracao: float,
    min_s: float,
    max_s: float,
    hard_cap_s: float,
) -> float:
    """Aplica clamp de duracao respeitando min, max e hard_cap.

    Ordem: hard_cap primeiro (teto absoluto e impedindo), depois max
    (recomendado), depois min (piso). Se duracao excede hard_cap, nao
    aplica max apos.
    """
    if duracao < min_s:
        duracao = min_s
    if duracao > hard_cap_s:
        duracao = hard_cap_s
    elif duracao > max_s:
        duracao = max_s
    return r3(max(duracao, 0.0))


def _janela_overlaps(
    a_in: float, a_out: float, b_in: float, b_out: float
) -> bool:
    """True se duas janelas se sobrepoem (intersecao de abertura > 0)."""
    return a_in < b_out and b_in < a_out


def _tem_colisao_cross_layer_critica(
    camada: str,
    out_in: float,
    out_out: float,
    elementos_por_camada: Dict[str, List[Dict[str, Any]]],
) -> bool:
    """Verifica colisao cross-layer critica:
    - L5 (b-roll e fullscreen_motion) nao sobrepoe L2, L3, L4 nem outro L5.
    - L4 nao sobrepoe L2 nem L5.
    """
    if camada == "L5_broll_industrial":
        for alvo in ("L2_titulo_heroi_t10", "L3_micro_zoom_bate", "L4_lower_third", "L5_fullscreen_motion"):
            for el in elementos_por_camada.get(alvo, []):
                if _janela_overlaps(out_in, out_out, float(el["out_in"]), float(el["out_out"])):
                    return True
    if camada == "L5_fullscreen_motion":
        for alvo in ("L2_titulo_heroi_t10", "L3_micro_zoom_bate", "L4_lower_third", "L5_broll_industrial"):
            for el in elementos_por_camada.get(alvo, []):
                if _janela_overlaps(out_in, out_out, float(el["out_in"]), float(el["out_out"])):
                    return True
    if camada == "L4_lower_third":
        for alvo in ("L2_titulo_heroi_t10", "L5_broll_industrial", "L5_fullscreen_motion"):
            for el in elementos_por_camada.get(alvo, []):
                if _janela_overlaps(out_in, out_out, float(el["out_in"]), float(el["out_out"])):
                    return True
    return False


def _tem_colisao_intra_layer(
    out_in: float,
    out_out: float,
    elementos: List[Dict[str, Any]],
) -> bool:
    """Verifica colisao intra-layer (mesma camada)."""
    for el in elementos:
        if _janela_overlaps(out_in, out_out, float(el["out_in"]), float(el["out_out"])):
            return True
    return False


def _dedup_key(origin: str, camada: str, out_in: float, out_out: float) -> str:
    """Gera chave de deduplicacao deterministica."""
    return f"{origin}|{camada}|{r3(out_in)}|{r3(out_out)}"


@dataclass
class RhythmEvent:
    """Representa um evento de ritmo visual."""
    camada: str
    out_in: float
    out_out: float
    duration_seconds: float
    origin: str  # 'semantic_plan' | 'rhythm_engine'
    dedup_key: str
    justification: str
    componente_motion_library: Optional[str] = None
    texto: str = ""
    funcao_editorial: str = ""
    element_id: str = ""
    event_id: Optional[int] = None
    raw_in: Optional[float] = None
    raw_out: Optional[float] = None
    segment_ids: List[Any] = field(default_factory=list)
    word_refs: List[str] = field(default_factory=list)
    motion_type: str = ""
    audio_treatment: str = "preservar"
    clamp_from_duration: bool = False
    original_out_out: Optional[float] = None
    source_ref: Dict[str, Any] = field(default_factory=dict)
    media_ref: Optional[str] = None
    sound_ref: Optional[str] = None
    sample: Optional[str] = None
    sfx_type: Optional[str] = None
    volume: Optional[float] = None
    tags: List[str] = field(default_factory=list)
    scene_id: Optional[str] = None
    html_path: Optional[str] = None
    transition_in: Optional[str] = None
    transition_out: Optional[str] = None
    conceito_visual: Optional[str] = None
    elementos_graficos: List[str] = field(default_factory=list)
    sfx_events: List[Dict[str, Any]] = field(default_factory=list)
    z_index: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        ev_type = (
            "fullscreen_motion"
            if self.camada == "L5_fullscreen_motion"
            else ("visual_overlay" if self.origin == "rhythm_engine" else "semantic_injection")
        )
        d: Dict[str, Any] = {
            "element_id": self.element_id,
            "event_id": self.event_id,
            "type": ev_type,
            "source_ref": dict(self.source_ref),
            "raw_in": r3(self.raw_in) if self.raw_in is not None else None,
            "raw_out": r3(self.raw_out) if self.raw_out is not None else None,
            "out_in": r3(self.out_in),
            "out_out": r3(self.out_out),
            "duration_seconds": self.duration_seconds,
            "origin": self.origin,
            "dedup_key": self.dedup_key,
            "justification": self.justification,
            "componente_motion_library": self.componente_motion_library,
            "texto": self.texto,
            "funcao_editorial": self.funcao_editorial,
            "motion_type": self.motion_type,
            "audio_treatment": self.audio_treatment,
            "segment_ids": list(self.segment_ids),
            "word_refs": list(self.word_refs),
        }
        if self.camada == "L5_fullscreen_motion":
            d["narration_continuous"] = True
        if self.scene_id is not None:
            d["scene_id"] = self.scene_id
        if self.html_path is not None:
            d["html_path"] = self.html_path
        if self.transition_in is not None:
            d["transition_in"] = self.transition_in
        if self.transition_out is not None:
            d["transition_out"] = self.transition_out
        if self.conceito_visual is not None:
            d["conceito_visual"] = self.conceito_visual
        if self.elementos_graficos:
            d["elementos_graficos"] = list(self.elementos_graficos)
        if self.sfx_events:
            d["sfx_events"] = list(self.sfx_events)
        if self.z_index is not None:
            d["z_index"] = self.z_index
        if self.media_ref is not None:
            d["media_ref"] = self.media_ref
        if self.sound_ref is not None:
            d["sound_ref"] = self.sound_ref
        if self.sample is not None:
            d["sample"] = self.sample
        if self.sfx_type is not None:
            d["sfx_type"] = self.sfx_type
        if self.volume is not None:
            d["volume"] = self.volume
        if self.tags:
            d["tags"] = list(self.tags)
        if self.clamp_from_duration:
            d["clamp_from_duration"] = True
            d["original_out_out"] = r3(self.original_out_out) if self.original_out_out is not None else None
        return d


class RhythmEngine:
    """
    Motor de ritmo visual editorial deterministico.

    Recebe um semantic_plan (opcional) e eventos de alinhamento, e produz
    camadas L2..L6 com regras de duracao, cooldown, precedencia semantica
    e deteccao de lacunas sem justificativa.
    """

    def __init__(self) -> None:
        self.eventos: List[RhythmEvent] = []
        self.gaps_for_review: List[Dict[str, Any]] = []
        self.clamped_count = 0
        self.unjustified_count = 0
        self._ultimo_out_por_camada: Dict[str, float] = {camada: 0.0 for camada in LAYERS_VISUAIS}
        self._ultimo_out_geral = 0.0
        self._cooldown_por_camada: Dict[str, float] = {camada: 0.0 for camada in LAYERS_VISUAIS}
        self._elementos_por_camada: Dict[str, List[Dict[str, Any]]] = {camada: [] for camada in LAYERS_VISUAIS}
        self._contador_elemento = 1

    # ------------------------------------------------------------------
    # Injecao de intencoes semanticas (semantic-first)
    # ------------------------------------------------------------------
    def injetar_intencao_semantica(
        self,
        iv: Dict[str, Any],
        events_l1: List[Dict[str, Any]],
        final_duration: float,
        mapeamento_raw_para_out,
    ) -> Optional[RhythmEvent]:
        """
        Injeta uma intencao visual do semantic_plan como evento origin='semantic_plan'.
        Aplica clamp de duracao por componente. Retorna None se invalido.
        """
        camada = iv.get("camada")
        if camada not in LAYERS_VISUAIS:
            return None

        comp_ml = iv.get("componente_motion_library")
        if comp_ml is not None and comp_ml not in _IMPLEMENTED_COMPONENTS:
            # Componente nao executavel: apenas warning informativo, nao injeta evento visual
            return None

        raw_in = float(iv["raw_start"])
        raw_out = float(iv["raw_end"])
        out_in = mapeamento_raw_para_out(raw_in, events_l1)
        out_out = mapeamento_raw_para_out(raw_out, events_l1)

        if out_out <= out_in:
            dur_raw = max(0.25, raw_out - raw_in)
            out_out = r3(min(final_duration, out_in + dur_raw))
        if out_out <= out_in:
            return None

        # Aplica limites por camada
        min_s, target_s, max_s, hard_cap_s, cooldown_s = _LAYER_LIMITS[camada]
        duracao_raw = out_out - out_in

        # Para janelas longas (ex: 8-15s), ancora no gatilho inicial
        # e usa target_s como duracao, em vez de clampar para max_s.
        if duracao_raw > max_s:
            out_out = r3(min(out_out, out_in + target_s))
            duracao_clampada = out_out - out_in
            clamp_from_duration = abs(duracao_clampada - duracao_raw) > 1e-6
        else:
            duracao_clampada = _clamp_duracao(duracao_raw, min_s, max_s, hard_cap_s)
            clamp_from_duration = abs(duracao_clampada - duracao_raw) > 1e-6
            out_out = r3(out_in + duracao_clampada)

        if out_out > final_duration:
            out_out = r3(final_duration)
            if out_out - out_in < min_s:
                cand_in = r3(max(0.0, out_out - duracao_clampada))
                if (out_out - cand_in) < min_s and cand_in >= 0.001:
                    cand_in = r3(cand_in - 0.001)
                if (
                    cand_in < out_in
                    and cand_in >= self._cooldown_por_camada[camada] - 1e-6
                    and not _tem_colisao_intra_layer(cand_in, out_out, self._elementos_por_camada[camada])
                    and not _tem_colisao_cross_layer_critica(camada, cand_in, out_out, self._elementos_por_camada)
                ):
                    out_in = cand_in
        elif (out_out - out_in) < min_s and (out_out + 0.001) <= final_duration:
            out_out = r3(out_out + 0.001)
        if out_out <= out_in:
            return None

        # Verifica cooldown
        if out_in < self._cooldown_por_camada[camada] - 1e-6:
            return None

        # Verifica colisoes
        if _tem_colisao_intra_layer(out_in, out_out, self._elementos_por_camada[camada]):
            return None
        if _tem_colisao_cross_layer_critica(camada, out_in, out_out, self._elementos_por_camada):
            return None

        movimento = {
            "L2_titulo_heroi_t10": "T10",
            "L3_micro_zoom_bate": "MicroZoom",
            "L4_lower_third": "LowerThird",
            "L5_broll_industrial": "B-roll",
            "L5_fullscreen_motion": "FullscreenMotion",
            "L6_sound_design_sync": "SoundDesign",
        }.get(camada, camada)

        evento = RhythmEvent(
            camada=camada,
            out_in=out_in,
            out_out=out_out,
            duration_seconds=r3(out_out - out_in),
            origin="semantic_plan",
            dedup_key=_dedup_key("semantic_plan", camada, out_in, out_out),
            justification=iv.get("justificativa", ""),
            componente_motion_library=comp_ml,
            texto=iv.get("texto", ""),
            funcao_editorial=iv.get("funcao_editorial", ""),
            element_id=f"V{self._contador_elemento:05d}",
            event_id=None,
            raw_in=raw_in,
            raw_out=raw_out,
            segment_ids=list(iv.get("segment_ids", [])),
            word_refs=list(iv.get("word_refs", [])),
            motion_type=movimento,
            clamp_from_duration=clamp_from_duration,
            original_out_out=r3(raw_out) if clamp_from_duration else None,
            media_ref=iv.get("media_ref"),
            sound_ref=iv.get("sound_ref"),
            sample=iv.get("sample"),
            sfx_type=iv.get("sfx_type"),
            volume=iv.get("volume"),
            tags=list(iv.get("tags", []) or []),
            scene_id=iv.get("scene_id") or iv.get("id_cena"),
            html_path=iv.get("html_path"),
            transition_in=iv.get("transition_in"),
            transition_out=iv.get("transition_out"),
            conceito_visual=iv.get("conceito_visual"),
            elementos_graficos=list(iv.get("elementos_graficos", []) or []),
            sfx_events=list(iv.get("sfx_events", []) or []),
            z_index=iv.get("z_index"),
        )
        self._contador_elemento += 1

        self.eventos.append(evento)
        self._elementos_por_camada[camada].append(
            {"out_in": out_in, "out_out": out_out, "element_id": evento.element_id}
        )
        self._ultimo_out_por_camada[camada] = out_out
        self._cooldown_por_camada[camada] = out_out + cooldown_s
        self._ultimo_out_geral = max(self._ultimo_out_geral, out_out)

        if clamp_from_duration:
            self.clamped_count += 1

        return evento

    # ------------------------------------------------------------------
    # Injecao de microeventos complementares (rhythm_engine)
    # ------------------------------------------------------------------
    def injetar_microevento(
        self,
        camada: str,
        out_in: float,
        out_out: float,
        justification: str,
        final_duration: float,
        texto: str = "",
        funcao_editorial: str = "",
        componente_motion_library: Optional[str] = None,
        segment_ids: Optional[List[Any]] = None,
        word_refs: Optional[List[str]] = None,
        source_ref: Optional[Dict[str, Any]] = None,
    ) -> Optional[RhythmEvent]:
        """
        Injeta um microevento complementar origin='rhythm_engine'.
        So e aceito se houver justificativa, respeitar cooldown e nao colidir.
        """
        if camada not in CAMADAS_COMPLEMENTAR:
            return None

        min_s, target_s, max_s, hard_cap_s, cooldown_s = _LAYER_LIMITS[camada]
        duracao = _clamp_duracao(out_out - out_in, min_s, max_s, hard_cap_s)
        out_out = r3(out_in + duracao)
        if out_out > final_duration:
            out_out = r3(final_duration)
        if out_out <= out_in:
            return None

        # Cooldown
        if out_in < self._cooldown_por_camada[camada] - 1e-6:
            return None

        # Colisoes
        if _tem_colisao_intra_layer(out_in, out_out, self._elementos_por_camada[camada]):
            return None
        if _tem_colisao_cross_layer_critica(camada, out_in, out_out, self._elementos_por_camada):
            return None

        movimento = {
            "L2_titulo_heroi_t10": "T10",
            "L3_micro_zoom_bate": "MicroZoom",
            "L4_lower_third": "LowerThird",
            "L5_broll_industrial": "B-roll",
        }.get(camada, camada)

        evento = RhythmEvent(
            camada=camada,
            out_in=out_in,
            out_out=out_out,
            duration_seconds=r3(out_out - out_in),
            origin="rhythm_engine",
            dedup_key=_dedup_key("rhythm_engine", camada, out_in, out_out),
            justification=justification,
            componente_motion_library=componente_motion_library,
            texto=texto,
            funcao_editorial=funcao_editorial,
            element_id=f"V{self._contador_elemento:05d}",
            event_id=None,
            raw_in=None,
            raw_out=None,
            segment_ids=list(segment_ids or []),
            word_refs=list(word_refs or []),
            motion_type=movimento,
            source_ref=dict(source_ref) if source_ref else {},
        )
        self._contador_elemento += 1

        self.eventos.append(evento)
        self._elementos_por_camada[camada].append(
            {"out_in": out_in, "out_out": out_out, "element_id": evento.element_id}
        )
        self._ultimo_out_por_camada[camada] = out_out
        self._cooldown_por_camada[camada] = out_out + cooldown_s
        self._ultimo_out_geral = max(self._ultimo_out_geral, out_out)

        return evento

    # ------------------------------------------------------------------
    # Proposicao de microeventos complementares (rhythm_engine)
    # ------------------------------------------------------------------
    def propor_microeventos_complementares(
        self,
        semantic_plan: Optional[Dict[str, Any]],
        events_l1: List[Dict[str, Any]],
        final_duration: float,
        mapeamento_raw_para_out,
        base_source_ref: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Propoe microeventos deterministicos complementares
        (origin='rhythm_engine', componente_motion_library=None) apenas quando
        houver justificativa editorial clara em janelas descobertas
        (> 4.0s entre estímulos visuais L2..L5).

        - Mudancas de topico/ganchos/argumentos sem estimulo visual proximo
          -> propõe L3_micro_zoom_bate (2.0s) com justification e segment_ids.
        - Entradas L2/L4/L5 -> acopla L6_sound_design_sync (0.5s) se nao houver
          outro L6 no mesmo timestamp.
        """
        if semantic_plan is None:
            return

        # Coleta eventos visuais L2..L5 ja injetados, ordenados por out_in
        visuais: List[Dict[str, Any]] = []
        for ev in self.eventos:
            if ev.camada in CAMADAS_COMPLEMENTAR:
                visuais.append(
                    {
                        "out_in": ev.out_in,
                        "out_out": ev.out_out,
                        "camada": ev.camada,
                    }
                )
        visuais.sort(key=lambda x: x["out_in"])

        def tem_estimulo_proximo(t: float, tolerancia: float = 1.0) -> bool:
            for v in visuais:
                if v["out_in"] <= t <= v["out_out"]:
                    return True
                if abs(v["out_in"] - t) <= tolerancia or abs(v["out_out"] - t) <= tolerancia:
                    return True
            return False

        # 1. Pontos de justificativa editorial: mudanca de topico,
        #    ganchos/viradas, argumentos
        pontos_just: List[Tuple[float, str, List[Any], List[str]]] = []

        topicos = semantic_plan.get("topicos", [])
        for i in range(1, len(topicos)):
            prev_out = float(topicos[i - 1].get("raw_end", 0.0))
            curr_in = float(topicos[i].get("raw_start", 0.0))
            # Mudanca de topico: fronteira entre topicos consecutivos
            # (mesmo que toquem, ha uma fronteira editorial)
            pontos_just.append(
                (
                    curr_in,
                    "mudanca_topico",
                    list(topicos[i].get("segment_ids", [])),
                    list(topicos[i].get("word_refs", [])),
                )
            )

        for gv in semantic_plan.get("ganchos_e_viradas", []):
            t = float(gv.get("raw_start", 0.0))
            pontos_just.append(
                (t, "gancho_virada", list(gv.get("segment_ids", [])), list(gv.get("word_refs", [])))
            )

        for arg in semantic_plan.get("argumentos", []):
            t = float(arg.get("raw_start", 0.0))
            pontos_just.append(
                (t, "argumento", list(arg.get("segment_ids", [])), list(arg.get("word_refs", [])))
            )

        # Para cada ponto, verificar se esta em janela descoberta (> 4.0s)
        # sem estimulo visual proximo
        l3_events_a_adicionar: List[Dict[str, Any]] = []
        for t_raw, tipo, seg_ids, word_refs in pontos_just:
            t_out = mapeamento_raw_para_out(t_raw, events_l1)

            if tem_estimulo_proximo(t_out, tolerancia=1.0):
                continue

            # Encontrar estimulo visual anterior e seguinte
            anterior_out = 0.0
            seguinte_in = final_duration
            for v in visuais:
                if v["out_out"] <= t_out:
                    anterior_out = max(anterior_out, v["out_out"])
                if v["out_in"] >= t_out:
                    seguinte_in = min(seguinte_in, v["out_in"])

            janela_descoberta = (seguinte_in - anterior_out) > GAP_SEM_JUSTIFICATIVA_LIMITE_S

            if janela_descoberta:
                out_in_l3 = t_out
                out_out_l3 = r3(min(final_duration, out_in_l3 + 2.0))
                l3_events_a_adicionar.append(
                    {
                        "out_in": out_in_l3,
                        "out_out": out_out_l3,
                        "justification": f"{tipo}: {t_raw:.3f}s — microzoom para enfatizar transicao editorial",
                        "texto": "",
                        "funcao_editorial": "Enfase na transicao editorial",
                        "segment_ids": seg_ids,
                        "word_refs": word_refs,
                    }
                )

        # Injetar L3 microeventos
        for ev_data in l3_events_a_adicionar:
            self.injetar_microevento(
                camada="L3_micro_zoom_bate",
                out_in=ev_data["out_in"],
                out_out=ev_data["out_out"],
                justification=ev_data["justification"],
                final_duration=final_duration,
                texto=ev_data["texto"],
                funcao_editorial=ev_data["funcao_editorial"],
                componente_motion_library=None,
                segment_ids=ev_data["segment_ids"],
                word_refs=ev_data["word_refs"],
                source_ref=base_source_ref,
            )

        # 2. Acoplar L6_sound_design_sync (0.5s) a entradas L2/L4/L5
        l6_events_a_adicionar: List[Dict[str, Any]] = []
        for ev in self.eventos:
            if ev.camada in ("L2_titulo_heroi_t10", "L4_lower_third", "L5_broll_industrial", "L5_fullscreen_motion"):
                tem_l6_proximo = False
                for ev2 in self.eventos:
                    if ev2.camada == "L6_sound_design_sync":
                        if abs(ev2.out_in - ev.out_in) <= 0.1:
                            tem_l6_proximo = True
                            break
                if not tem_l6_proximo:
                    out_in_l6 = ev.out_in
                    out_out_l6 = r3(min(final_duration, out_in_l6 + 0.5))
                    l6_events_a_adicionar.append(
                        {
                            "out_in": out_in_l6,
                            "out_out": out_out_l6,
                            "justification": f"Acoplamento sonoro a {ev.camada} em {ev.out_in:.3f}s",
                            "texto": "",
                            "funcao_editorial": "Sincronizacao de som",
                            "segment_ids": [],
                            "word_refs": [],
                        }
                    )

        for ev_data in l6_events_a_adicionar:
            self.injetar_microevento(
                camada="L6_sound_design_sync",
                out_in=ev_data["out_in"],
                out_out=ev_data["out_out"],
                justification=ev_data["justification"],
                final_duration=final_duration,
                texto=ev_data["texto"],
                funcao_editorial=ev_data["funcao_editorial"],
                componente_motion_library=None,
                segment_ids=ev_data["segment_ids"],
                word_refs=ev_data["word_refs"],
                source_ref=base_source_ref,
            )

    # ------------------------------------------------------------------
    # Deteccao de lacunas visuais (somente L2..L5)
    # ------------------------------------------------------------------
    def detectar_gaps_visuais(
        self,
        final_duration: float,
        alinhamento_unidades: Optional[List[Dict[str, Any]]] = None,
        l1_events: Optional[List[Dict[str, Any]]] = None,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Detecta lacunas de ritmo visual.

        Retorna (todos_os_gaps, gaps_sem_justificativa).

        Regras:
        - Se houver estímulos visuais L2..L5: mede lacunas > 4.0s entre eles
          (incluindo 0 ate o primeiro e o ultimo ate final_duration).
        - Se NAO houver estímulos visuais L2..L5:
          * todos_os_gaps = [0.0, final_duration] (timeline inteira sem visual)
          * gaps_sem_justificativa = gaps > 4.0s na cobertura de fala (L1),
            ou seja, regiões onde nem fala nem visual cobrem o tempo.
        """
        # Somente eventos visuais L2..L5 quebram lacunas de ritmo
        visuais: List[Dict[str, Any]] = []
        for ev in self.eventos:
            if ev.camada in CAMADAS_COMPLEMENTAR:
                visuais.append(
                    {
                        "out_in": ev.out_in,
                        "out_out": ev.out_out,
                        "justification": ev.justification,
                        "origin": ev.origin,
                        "camada": ev.camada,
                    }
                )
        visuais.sort(key=lambda x: x["out_in"])

        # Caso A: ha estímulos visuais L2..L5 — mede lacunas entre eles
        if visuais:
            todos_gaps: List[Dict[str, Any]] = []
            gaps_sem_just: List[Dict[str, Any]] = []
            prev_out = 0.0
            for ev in visuais:
                gap = ev["out_in"] - prev_out
                if gap > GAP_SEM_JUSTIFICATIVA_LIMITE_S:
                    gap_entry = {
                        "start": r3(prev_out),
                        "end": r3(ev["out_in"]),
                        "duration_s": r3(gap),
                        "reason": "lacuna_sem_estimulo_justificado",
                    }
                    todos_gaps.append(gap_entry)
                    justificada = self._lacuna_tem_justificativa(
                        prev_out, ev["out_in"], alinhamento_unidades
                    )
                    if not justificada:
                        gaps_sem_just.append(gap_entry)
                prev_out = max(prev_out, ev["out_out"])
            # Lacuna apos o ultimo estimulo ate o final
            gap_final = final_duration - prev_out
            if gap_final > GAP_SEM_JUSTIFICATIVA_LIMITE_S:
                gap_entry = {
                    "start": r3(prev_out),
                    "end": r3(final_duration),
                    "duration_s": r3(gap_final),
                    "reason": "lacuna_final_sem_estimulo_justificado",
                }
                todos_gaps.append(gap_entry)
                justificada = self._lacuna_tem_justificativa(
                    prev_out, final_duration, alinhamento_unidades
                )
                if not justificada:
                    gaps_sem_just.append(gap_entry)

        # Caso B: nao ha estímulos visuais L2..L5
        else:
            # todos_os_gaps: timeline inteira (sem nenhum visual)
            todos_gaps = []
            if final_duration > GAP_SEM_JUSTIFICATIVA_LIMITE_S:
                todos_gaps.append(
                    {
                        "start": r3(0.0),
                        "end": r3(final_duration),
                        "duration_s": r3(final_duration),
                        "reason": "lacuna_total_sem_estimulo_visual",
                    }
                )

            # gaps_sem_justificativa: usa cobertura de fala (L1) para delimitar
            # lacunas onde nem fala nem visual cobrem o tempo
            cobertura: List[Dict[str, float]] = []
            if l1_events:
                for ev in l1_events:
                    if _has_window(ev):
                        cobertura.append(
                            {
                                "out_in": float(ev["out_in"]),
                                "out_out": float(ev["out_out"]),
                            }
                        )
            cobertura.sort(key=lambda x: x["out_in"])

            gaps_sem_just: List[Dict[str, Any]] = []
            prev_out = 0.0
            for cov in cobertura:
                gap = cov["out_in"] - prev_out
                if gap > GAP_SEM_JUSTIFICATIVA_LIMITE_S:
                    gaps_sem_just.append(
                        {
                            "start": r3(prev_out),
                            "end": r3(cov["out_in"]),
                            "duration_s": r3(gap),
                            "reason": "lacuna_sem_cobertura_fala_ou_visual",
                        }
                    )
                prev_out = max(prev_out, cov["out_out"])
            gap_final = final_duration - prev_out
            if gap_final > GAP_SEM_JUSTIFICATIVA_LIMITE_S:
                gaps_sem_just.append(
                    {
                        "start": r3(prev_out),
                        "end": r3(final_duration),
                        "duration_s": r3(gap_final),
                        "reason": "lacuna_final_sem_cobertura_fala_ou_visual",
                    }
                )

        self.todos_gaps = todos_gaps
        self.gaps_for_review = gaps_sem_just
        return todos_gaps, gaps_sem_just

    def _lacuna_tem_justificativa(
        self,
        inicio: float,
        fim: float,
        alinhamento_unidades: Optional[List[Dict[str, Any]]],
    ) -> bool:
        """Verifica se uma lacuna tem justificativa no alignment."""
        if not alinhamento_unidades:
            return False
        for unidade in alinhamento_unidades:
            us = float(unidade.get("raw_start", 0.0))
            ue = float(unidade.get("raw_end", 0.0))
            # Sobreposicao parcial com a lacuna
            if us < fim and ue > inicio:
                texto = unidade.get("text", "")
                # Pausa longa dentro da unidade
                if ue - us > PAUSA_FRONTEIRA_LIMITE_S:
                    return True
                # Palavras de enfase
                if any(
                    termo in texto.lower()
                    for termo in ("importante", "essencial", "chave", "destaque", "principal")
                ):
                    return True
        return False

    # ------------------------------------------------------------------
    # Metricas
    # ------------------------------------------------------------------
    def compute_rhythm_metrics(
        self, plan: Dict[str, Any], final_duration: float
    ) -> Dict[str, Any]:
        """
        Computa metricas de ritmo a partir do plano editorial.
        """
        layers = plan.get("layers", {})

        # Coletar estimulos visuais L2..L5 com janela
        estimulos: List[Dict[str, Any]] = []
        for camada in CAMADAS_COMPLEMENTAR:
            for el in _elements(layers.get(camada, [])):
                if _has_window(el):
                    estimulos.append(
                        {
                            "camada": camada,
                            "out_in": float(el["out_in"]),
                            "out_out": float(el["out_out"]),
                            "justification": el.get("justification", ""),
                            "origin": el.get("origin", ""),
                        }
                    )
        estimulos.sort(key=lambda x: x["out_in"])

        # interval_stats entre inicios
        inicios = [e["out_in"] for e in estimulos]
        interval_stats = self._interval_stats(inicios)

        # gaps_over_4s (do plano, se houver rhythm_report)
        gaps_over_4s = []
        rhythm_report = plan.get("rhythm_report", {})
        if rhythm_report:
            gaps_over_4s = rhythm_report.get("gaps_for_review", [])

        # distribution_by_layer
        distribution_by_layer: Dict[str, Dict[str, Any]] = {}
        for camada in ("L1_estabelecimento",) + LAYERS_VISUAIS:
            elems = [e for e in _elements(layers.get(camada, [])) if _has_window(e)]
            contagem = len(elems)
            duracao_total = r3(sum(float(e["out_out"]) - float(e["out_in"]) for e in elems))
            distribution_by_layer[camada] = {
                "contagem": contagem,
                "duracao_total_s": duracao_total,
            }

        # duration_by_component
        duration_by_component: Dict[str, Dict[str, float]] = {}
        for camada in CAMADAS_COMPLEMENTAR:
            elems = [
                e
                for e in _elements(layers.get(camada, []))
                if _has_window(e)
            ]
            if elems:
                duracoes = [float(e["out_out"]) - float(e["out_in"]) for e in elems]
                duration_by_component[camada] = {
                    "min_s": r3(min(duracoes)),
                    "mean_s": r3(sum(duracoes) / len(duracoes)),
                    "max_s": r3(max(duracoes)),
                }

        # simultaneous_overlays (max simultaneos L2..L5)
        max_simultaneous = 0
        simultaneous_windows: List[Dict[str, Any]] = []
        pontos = []
        for e in estimulos:
            pontos.append((e["out_in"], "in", e))
            pontos.append((e["out_out"], "out", e))
        pontos.sort(key=lambda x: (x[0], x[1]))
        ativos: List[Dict[str, Any]] = []
        for t, tipo, e in pontos:
            if tipo == "in":
                ativos.append(e)
                if len(ativos) > max_simultaneous:
                    max_simultaneous = len(ativos)
                    simultaneous_windows = [
                        {
                            "camada": a["camada"],
                            "out_in": r3(a["out_in"]),
                            "out_out": r3(a["out_out"]),
                        }
                        for a in ativos
                    ]
            else:
                ativos = [a for a in ativos if a is not e]

        # unjustified_count
        unjustified_count = sum(
            1 for e in estimulos if not e.get("justification")
        )

        # clamped_count
        clamped_count = self.clamped_count

        return {
            "interval_stats": interval_stats,
            "gaps_over_4s": gaps_over_4s,
            "distribution_by_layer": distribution_by_layer,
            "duration_by_component": duration_by_component,
            "simultaneous_overlays": {
                "max_simultaneous_overlays": max_simultaneous,
                "janelas_simultaneas": simultaneous_windows,
            },
            "unjustified_count": unjustified_count,
            "clamped_count": clamped_count,
            "total_estimulos_visuais": len(estimulos),
        }

    def _interval_stats(
        self, inicios: List[float]
    ) -> Dict[str, Any]:
        if len(inicios) < 2:
            return {
                "count": len(inicios),
                "mean_s": 0.0,
                "median_s": 0.0,
                "p90_s": 0.0,
                "min_s": 0.0,
                "max_gap_s": 0.0,
            }
        intervalos = [inicios[i + 1] - inicios[i] for i in range(len(inicios) - 1)]
        intervalos_ordenados = sorted(intervalos)
        n = len(intervalos_ordenados)
        mean_s = r3(sum(intervalos_ordenados) / n)
        median_s = (
            intervalos_ordenados[n // 2]
            if n % 2 == 1
            else r3((intervalos_ordenados[n // 2 - 1] + intervalos_ordenados[n // 2]) / 2.0)
        )
        p90_idx = max(0, min(n - 1, int(n * 0.90)))
        p90_s = r3(intervalos_ordenados[p90_idx])
        return {
            "count": n,
            "mean_s": mean_s,
            "median_s": median_s,
            "p90_s": p90_s,
            "min_s": r3(min(intervalos_ordenados)),
            "max_gap_s": r3(max(intervalos_ordenados)),
        }


# -----------------------------------------------------------------------------
# Funcao de conveniencia para construcao completa
# -----------------------------------------------------------------------------


def build_rhythm_layers(
    semantic_plan: Optional[Dict[str, Any]],
    events_l1: List[Dict[str, Any]],
    final_duration: float,
    alinhamento_unidades: Optional[List[Dict[str, Any]]] = None,
    mapeamento_raw_para_out=None,
    base_source_ref: Optional[Dict[str, Any]] = None,
) -> Tuple[Dict[str, List[Dict[str, Any]]], Dict[str, Any]]:
    """
    Construi as camadas L2..L6 a partir do semantic_plan e eventos L1.
    Retorna (layers, rhythm_report).
    """
    engine = RhythmEngine()

    if mapeamento_raw_para_out is None:
        def _mapeamento_default(raw: float, events: List[Dict[str, Any]]) -> float:
            # Mapeamento identidade: out ~= raw (ajustado aos eventos L1)
            for ev in events:
                if ev["raw_in"] <= raw <= ev["raw_out"]:
                    return float(ev["out_in"]) + (raw - ev["raw_in"])
            return raw

        mapeamento_raw_para_out = _mapeamento_default

    if base_source_ref is None:
        base_source_ref = {}

    # 1. Injetar intencoes semanticas (semantic-first)
    if semantic_plan is not None:
        for iv in semantic_plan.get("intencoes_visuais", []):
            evento = engine.injetar_intencao_semantica(
                iv, events_l1, final_duration, mapeamento_raw_para_out
            )
            if evento is not None:
                evento.source_ref = dict(base_source_ref)

    # 2. Detectar todos os gaps visuais (somente L2..L5; usa L1 como
    #    cobertura de fala quando nao ha estímulos visuais)
    todos_gaps, gaps_sem_just = engine.detectar_gaps_visuais(
        final_duration, alinhamento_unidades, l1_events=events_l1
    )

    # 3. Propor microeventos complementares (rhythm_engine) em janelas
    #    descobertas (> 4.0s) com justificativa editorial clara.
    engine.propor_microeventos_complementares(
        semantic_plan,
        events_l1,
        final_duration,
        mapeamento_raw_para_out,
        base_source_ref=base_source_ref,
    )

    # 4. Construir layers
    layers: Dict[str, List[Dict[str, Any]]] = {camada: [] for camada in LAYERS_VISUAIS}
    for ev in engine.eventos:
        layers[ev.camada].append(ev.to_dict())

    # 4. Metricas
    plano_sintetico: Dict[str, Any] = {"layers": layers}
    # Adicionar elementos L1 para metricas de distribuicao
    layers_com_l1: Dict[str, List[Dict[str, Any]]] = dict(layers)
    layers_com_l1["L1_estabelecimento"] = [
        {
            "out_in": float(ev["out_in"]),
            "out_out": float(ev["out_out"]),
            "element_id": ev.get("element_id", ""),
        }
        for ev in events_l1
        if "out_in" in ev and "out_out" in ev
    ]
    plano_sintetico["layers"] = layers_com_l1

    rhythm_report = engine.compute_rhythm_metrics(plano_sintetico, final_duration)
    rhythm_report["gaps_over_4s"] = engine.todos_gaps
    rhythm_report["gaps_for_review"] = engine.gaps_for_review
    rhythm_report["clamped_count"] = engine.clamped_count
    rhythm_report["unjustified_count"] = engine.unjustified_count

    return layers, rhythm_report


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
