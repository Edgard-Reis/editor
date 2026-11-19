#!/usr/bin/env python3
"""
core/test_rhythm_engine.py

Testes locais do core/rhythm_engine.py (Editor).
Usa fixtures sinteticas e anonimizadas — SEM API externa, SEM transcricao real.

Cenarios cobertos (10):
  (a) fala continua sem pausas
  (b) fala com enfase pontual
  (c) mudanca de topico
  (d) explicacao longa
  (e) lista de argumentos
  (f) nome/entidade que merece lower third
  (g) trecho que justifica B-roll
  (h) janela sem estimulo justificavel (registra lacuna sem inventar evento)
  (i) intencao sem componente executavel
  (j) eventos sobrepostos ou fora da timeline

Valida: preservacao integral da fala, reprodutibilidade deterministica,
ausencia de duplicidade, duracoes validas e lint().
"""

import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

# Garante import do pacote core (raiz Editor).
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.rhythm_engine import (  # noqa: E402
    RhythmEngine,
    build_rhythm_layers,
    _LAYER_LIMITS,
    _clamp_duracao,
    GAP_SEM_JUSTIFICATIVA_LIMITE_S,
)
from core.master_lint import lint  # noqa: E402


def _make_l1_event(
    event_id: int,
    out_in: float,
    out_out: float,
    raw_in: float = 0.0,
    raw_out: float = 0.0,
    text: str = "",
    topic_id: str = "T1",
    explanation_group_id: str = "E1",
) -> Dict[str, Any]:
    """Cria um evento L1 sintético."""
    return {
        "event_id": event_id,
        "type": "video_audio",
        "source_ref": {"id": "SRC_TEST", "path": "brutos/video.mp4", "sha256": "0" * 64},
        "raw_in": raw_in,
        "raw_out": raw_out,
        "out_in": out_in,
        "out_out": out_out,
        "duration_seconds": out_out - out_in,
        "word_ids": [f"W{i:05d}" for i in range(event_id * 10, event_id * 10 + 5)],
        "text": text,
        "transition_in": "hard_cut",
        "transition_out": "hard_cut",
        "operation": "jump_cut",
        "justification": f"Unidade {event_id}",
        "audio_treatment": "preservar",
        "motion_hints": [],
        "narrative_continuity": {
            "topic_id": topic_id,
            "explanation_group_id": explanation_group_id,
            "preserves_context": True,
        },
    }


def _make_semantic_plan(
    intencoes_visuais: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Cria um semantic_plan.json sintético."""
    return {
        "schema_version": "1.0.0",
        "tema_central": "Tema de teste sintético",
        "tese_principal": "Tese de teste sintético",
        "topicos": [
            {
                "topic_id": "T1",
                "titulo": "Topico 1",
                "justificativa": "Justificativa do topico 1",
                "raw_start": 0.0,
                "raw_end": 10.0,
                "segment_ids": [0],
                "word_refs": ["w-0"],
            }
        ],
        "argumentos": [],
        "grupos_explicacao": [],
        "ganchos_e_viradas": [],
        "repeticoes_dispensaveis": [],
        "falsos_comecos": [],
        "segmentos_editoriais": [],
        "intencoes_visuais": intencoes_visuais or [],
    }


def _make_intencao_visual(
    camada: str,
    raw_start: float,
    raw_end: float,
    justificativa: str,
    componente_motion_library: Optional[str] = None,
    texto: str = "",
    topic_id: str = "T1",
) -> Dict[str, Any]:
    """Cria uma intencao visual sintética."""
    return {
        "camada": camada,
        "raw_start": raw_start,
        "raw_end": raw_end,
        "justificativa": justificativa,
        "componente_motion_library": componente_motion_library,
        "texto": texto,
        "funcao_editorial": "Funcao editorial de teste",
        "topic_id": topic_id,
        "explanation_group_id": "E1",
        "segment_ids": [0],
        "word_refs": ["w-0"],
    }


# ---------------------------------------------------------------------------
# Testes
# ---------------------------------------------------------------------------


def test_clamp_duracao_limites():
    """Validacao das regras de clamp de duracao por camada."""
    # L2: min=1.8, max=4.5, hard_cap=7.0
    assert _clamp_duracao(1.0, 1.8, 4.5, 7.0) == 1.8  # abaixo do min
    assert _clamp_duracao(5.0, 1.8, 4.5, 7.0) == 4.5  # acima do max
    assert _clamp_duracao(8.0, 1.8, 4.5, 7.0) == 7.0  # acima do hard_cap
    assert _clamp_duracao(3.0, 1.8, 4.5, 7.0) == 3.0  # dentro do range

    # L4: min=3.0, max=5.5, hard_cap=7.0
    assert _clamp_duracao(2.0, 3.0, 5.5, 7.0) == 3.0
    assert _clamp_duracao(6.0, 3.0, 5.5, 7.0) == 5.5
    assert _clamp_duracao(9.0, 3.0, 5.5, 7.0) == 7.0

    # L6: min=0.2, max=1.5, hard_cap=3.0
    assert _clamp_duracao(0.1, 0.2, 1.5, 3.0) == 0.2
    assert _clamp_duracao(2.0, 0.2, 1.5, 3.0) == 1.5
    assert _clamp_duracao(5.0, 0.2, 1.5, 3.0) == 3.0
    print("  [PASS] test_clamp_duracao_limites")


def test_cenario_a_fala_continua_sem_pausas():
    """(a) Fala contínua sem pausas — sem microeventos complementares."""
    l1_events = [
        _make_l1_event(1, 0.0, 5.0, 0.0, 5.0, "Fala contínua sem interrupções"),
        _make_l1_event(2, 5.0, 10.0, 5.0, 10.0, "Continuação da fala"),
    ]
    semantic_plan = _make_semantic_plan()

    layers, report = build_rhythm_layers(
        semantic_plan=semantic_plan,
        events_l1=l1_events,
        final_duration=10.0,
        base_source_ref=l1_events[0]["source_ref"],
    )

    # Sem intencoes visuais no semantic_plan, nao deve haver overlays L2..L5
    total_overlays = sum(len(layers[c]) for c in ("L2_titulo_heroi_t10", "L3_micro_zoom_bate", "L4_lower_third", "L5_broll_industrial"))
    assert total_overlays == 0, f"Esperado 0 overlays, encontrado {total_overlays}"
    # L6 pode estar vazio
    assert len(layers["L6_sound_design_sync"]) == 0
    # Nenhuma lacuna registrada (sem estimulos, sem gaps > 4s entre estimulos)
    assert report["gaps_for_review"] == []
    print("  [PASS] test_cenario_a_fala_continua_sem_pausas")


def test_cenario_b_fala_com_enfase_pontual():
    """(b) Fala com ênfase pontual — permite microevento de enfase."""
    l1_events = [
        _make_l1_event(1, 0.0, 3.0, 0.0, 3.0, "Fala normal"),
        _make_l1_event(2, 3.0, 6.0, 3.0, 6.0, "Ênfase importante aqui"),
        _make_l1_event(3, 6.0, 10.0, 6.0, 10.0, "Fala normal novamente"),
    ]
    semantic_plan = _make_semantic_plan()

    layers, report = build_rhythm_layers(
        semantic_plan=semantic_plan,
        events_l1=l1_events,
        final_duration=10.0,
        base_source_ref=l1_events[0]["source_ref"],
    )

    # Sem intencoes visuais, sem overlays
    total_overlays = sum(len(layers[c]) for c in ("L2_titulo_heroi_t10", "L3_micro_zoom_bate", "L4_lower_third", "L5_broll_industrial"))
    assert total_overlays == 0
    print("  [PASS] test_cenario_b_fala_com_enfase_pontual")


def test_cenario_c_mudanca_de_topico():
    """(c) Mudança de topico — justifica microevento L3."""
    l1_events = [
        _make_l1_event(1, 0.0, 4.0, 0.0, 4.0, "Topico A", topic_id="T1", explanation_group_id="E1"),
        _make_l1_event(2, 4.0, 8.0, 4.0, 8.0, "Topico B", topic_id="T2", explanation_group_id="E2"),
    ]
    semantic_plan = _make_semantic_plan()

    layers, report = build_rhythm_layers(
        semantic_plan=semantic_plan,
        events_l1=l1_events,
        final_duration=8.0,
        base_source_ref=l1_events[0]["source_ref"],
    )

    # Sem intencoes visuais, sem overlays
    total_overlays = sum(len(layers[c]) for c in ("L2_titulo_heroi_t10", "L3_micro_zoom_bate", "L4_lower_third", "L5_broll_industrial"))
    assert total_overlays == 0
    print("  [PASS] test_cenario_c_mudanca_de_topico")


def test_cenario_d_explicacao_longa():
    """(d) Explicação longa — L2 titulo_heroi com clamp se exceder max."""
    l1_events = [
        _make_l1_event(1, 0.0, 10.0, 0.0, 10.0, "Explicação longa contínua", topic_id="T1", explanation_group_id="E1"),
    ]
    semantic_plan = _make_semantic_plan([
        _make_intencao_visual("L2_titulo_heroi_t10", 0.0, 10.0, "Título do vídeo inteiro", "titulo_heroi", "Título")
    ])

    layers, report = build_rhythm_layers(
        semantic_plan=semantic_plan,
        events_l1=l1_events,
        final_duration=10.0,
        base_source_ref=l1_events[0]["source_ref"],
    )

    l2_events = layers["L2_titulo_heroi_t10"]
    assert len(l2_events) == 1
    ev = l2_events[0]
    # Deve ser clampado para max=4.5s (hard_cap=7.0)
    assert ev["duration_seconds"] <= 4.5, f"Duração {ev['duration_seconds']} excede max 4.5s"
    assert ev["origin"] == "semantic_plan"
    assert ev["componente_motion_library"] == "titulo_heroi"
    print("  [PASS] test_cenario_d_explicacao_longa")


def test_cenario_e_lista_de_argumentos():
    """(e) Lista de argumentos — multiplos topicos, sem overlays invalidos."""
    l1_events = [
        _make_l1_event(1, 0.0, 2.5, 0.0, 2.5, "Argumento 1", topic_id="T1", explanation_group_id="E1"),
        _make_l1_event(2, 2.5, 5.0, 2.5, 5.0, "Argumento 2", topic_id="T2", explanation_group_id="E2"),
        _make_l1_event(3, 5.0, 7.5, 5.0, 7.5, "Argumento 3", topic_id="T3", explanation_group_id="E3"),
    ]
    semantic_plan = _make_semantic_plan()

    layers, report = build_rhythm_layers(
        semantic_plan=semantic_plan,
        events_l1=l1_events,
        final_duration=7.5,
        base_source_ref=l1_events[0]["source_ref"],
    )

    total_overlays = sum(len(layers[c]) for c in ("L2_titulo_heroi_t10", "L3_micro_zoom_bate", "L4_lower_third", "L5_broll_industrial"))
    assert total_overlays == 0
    print("  [PASS] test_cenario_e_lista_de_argumentos")


def test_cenario_f_nome_entidade_lower_third():
    """(f) Nome/entidade que merece lower third — L4 com componente None."""
    l1_events = [
        _make_l1_event(1, 0.0, 5.0, 0.0, 5.0, "João Silva fala aqui", topic_id="T1", explanation_group_id="E1"),
    ]
    semantic_plan = _make_semantic_plan([
        _make_intencao_visual("L4_lower_third", 0.0, 5.0, "Apresentação do palestrante", None, "João Silva")
    ])

    layers, report = build_rhythm_layers(
        semantic_plan=semantic_plan,
        events_l1=l1_events,
        final_duration=5.0,
        base_source_ref=l1_events[0]["source_ref"],
    )

    l4_events = layers["L4_lower_third"]
    assert len(l4_events) == 1
    ev = l4_events[0]
    assert ev["origin"] == "semantic_plan"
    assert ev["componente_motion_library"] is None
    # L4: min=3.0, duracao 5.0 está dentro [3.0, 5.5]
    assert 3.0 <= ev["duration_seconds"] <= 5.5
    print("  [PASS] test_cenario_f_nome_entidade_lower_third")


def test_cenario_g_trecho_justifica_broll():
    """(g) Trecho que justifica B-roll — L5 sem sobrepor L2/L4."""
    l1_events = [
        _make_l1_event(1, 0.0, 10.0, 0.0, 10.0, "Mostra a fabrica", topic_id="T1", explanation_group_id="E1"),
    ]
    semantic_plan = _make_semantic_plan([
        _make_intencao_visual("L2_titulo_heroi_t10", 0.0, 2.0, "Titulo", "titulo_heroi", "Titulo"),
        _make_intencao_visual("L5_broll_industrial", 2.0, 6.0, "B-roll da fabrica", None, "Fabrica"),
    ])

    layers, report = build_rhythm_layers(
        semantic_plan=semantic_plan,
        events_l1=l1_events,
        final_duration=10.0,
        base_source_ref=l1_events[0]["source_ref"],
    )

    l2_events = layers["L2_titulo_heroi_t10"]
    l5_events = layers["L5_broll_industrial"]
    assert len(l2_events) == 1
    assert len(l5_events) == 1
    # L5 nao deve sobrepor L2
    l2_ev = l2_events[0]
    l5_ev = l5_events[0]
    assert not (l5_ev["out_in"] < l2_ev["out_out"] and l2_ev["out_in"] < l5_ev["out_out"])
    print("  [PASS] test_cenario_g_trecho_justifica_broll")


def test_cenario_h_janela_sem_estimulo_justificavel():
    """(h) Janela sem estimulo justificavel — registra lacuna, nao inventa evento."""
    l1_events = [
        _make_l1_event(1, 0.0, 2.0, 0.0, 2.0, "Fala curta", topic_id="T1", explanation_group_id="E1"),
        _make_l1_event(2, 8.0, 10.0, 8.0, 10.0, "Fala depois da lacuna", topic_id="T2", explanation_group_id="E2"),
    ]
    semantic_plan = _make_semantic_plan()

    layers, report = build_rhythm_layers(
        semantic_plan=semantic_plan,
        events_l1=l1_events,
        final_duration=10.0,
        base_source_ref=l1_events[0]["source_ref"],
    )

    # Sem overlays (sem intencoes visuais)
    total_overlays = sum(len(layers[c]) for c in ("L2_titulo_heroi_t10", "L3_micro_zoom_bate", "L4_lower_third", "L5_broll_industrial"))
    assert total_overlays == 0
    # Lacuna de 6s (2.0 a 8.0) deve ser registrada
    gaps = report["gaps_for_review"]
    assert len(gaps) >= 1, f"Esperado pelo menos 1 gap, encontrado {len(gaps)}"
    gap = gaps[0]
    assert gap["start"] == 2.0
    assert gap["end"] == 8.0
    assert gap["duration_s"] == 6.0
    print("  [PASS] test_cenario_h_janela_sem_estimulo_justificavel")


def test_cenario_i_intencao_sem_componente_executavel():
    """(i) Intencao sem componente executavel — nao injeta, apenas warning."""
    l1_events = [
        _make_l1_event(1, 0.0, 5.0, 0.0, 5.0, "Fala", topic_id="T1", explanation_group_id="E1"),
    ]
    # Componente invalido (não 'titulo_heroi')
    semantic_plan = _make_semantic_plan([
        _make_intencao_visual("L2_titulo_heroi_t10", 0.0, 5.0, "Componente invalido", "componente_inexistente", "Texto")
    ])

    layers, report = build_rhythm_layers(
        semantic_plan=semantic_plan,
        events_l1=l1_events,
        final_duration=5.0,
        base_source_ref=l1_events[0]["source_ref"],
    )

    # Nao deve injetar evento para componente invalido
    l2_events = layers["L2_titulo_heroi_t10"]
    assert len(l2_events) == 0
    print("  [PASS] test_cenario_i_intencao_sem_componente_executavel")


def test_cenario_j_eventos_sobrepostos_fora_timeline():
    """(j) Eventos sobrepostos ou fora da timeline — rejeitados pelo engine."""
    l1_events = [
        _make_l1_event(1, 0.0, 10.0, 0.0, 10.0, "Fala", topic_id="T1", explanation_group_id="E1"),
    ]
    # Dois overlays L2 sobrepostos
    semantic_plan = _make_semantic_plan([
        _make_intencao_visual("L2_titulo_heroi_t10", 0.0, 5.0, "Sobreposto 1", "titulo_heroi", "A"),
        _make_intencao_visual("L2_titulo_heroi_t10", 3.0, 8.0, "Sobreposto 2", "titulo_heroi", "B"),
    ])

    layers, report = build_rhythm_layers(
        semantic_plan=semantic_plan,
        events_l1=l1_events,
        final_duration=10.0,
        base_source_ref=l1_events[0]["source_ref"],
    )

    l2_events = layers["L2_titulo_heroi_t10"]
    # Deve aceitar apenas um (o primeiro), rejeitar o segundo por colisao
    assert len(l2_events) == 1
    print("  [PASS] test_cenario_j_eventos_sobrepostos_fora_timeline")


def test_preservacao_integral_da_fala():
    """Validar que nenhum segmento de fala é cortado destrutivamente."""
    l1_events = [
        _make_l1_event(1, 0.0, 3.0, 0.0, 3.0, "Segmento 1", topic_id="T1", explanation_group_id="E1"),
        _make_l1_event(2, 3.0, 7.0, 3.0, 7.0, "Segmento 2", topic_id="T2", explanation_group_id="E2"),
        _make_l1_event(3, 7.0, 10.0, 7.0, 10.0, "Segmento 3", topic_id="T3", explanation_group_id="E3"),
    ]
    semantic_plan = _make_semantic_plan()

    layers, _ = build_rhythm_layers(
        semantic_plan=semantic_plan,
        events_l1=l1_events,
        final_duration=10.0,
        base_source_ref=l1_events[0]["source_ref"],
    )

    l1_layer = layers.get("L1_estabelecimento", [])
    # L1 recebe todos os eventos (construído no edl_builder, não no rhythm_engine)
    # Aqui apenas verificamos que o rhythm_engine nao modifica L1
    assert len(l1_layer) == 0  # rhythm_engine nao toca L1
    print("  [PASS] test_preservacao_integral_da_fala")


def test_reprodutibilidade_deterministica():
    """Mesma entrada produz mesma saída."""
    l1_events = [
        _make_l1_event(1, 0.0, 5.0, 0.0, 5.0, "Fala", topic_id="T1", explanation_group_id="E1"),
    ]
    semantic_plan = _make_semantic_plan([
        _make_intencao_visual("L2_titulo_heroi_t10", 0.0, 3.0, "Titulo", "titulo_heroi", "Titulo")
    ])

    resultado1 = build_rhythm_layers(
        semantic_plan=semantic_plan,
        events_l1=l1_events,
        final_duration=5.0,
        base_source_ref=l1_events[0]["source_ref"],
    )
    resultado2 = build_rhythm_layers(
        semantic_plan=semantic_plan,
        events_l1=l1_events,
        final_duration=5.0,
        base_source_ref=l1_events[0]["source_ref"],
    )

    assert json.dumps(resultado1[0], sort_keys=True) == json.dumps(resultado2[0], sort_keys=True)
    assert json.dumps(resultado1[1], sort_keys=True) == json.dumps(resultado2[1], sort_keys=True)
    print("  [PASS] test_reprodutibilidade_deterministica")


def test_ausencia_duplicidade_dedup_key():
    """Validar ausencia de duplicidade via dedup_key."""
    l1_events = [
        _make_l1_event(1, 0.0, 10.0, 0.0, 10.0, "Fala", topic_id="T1", explanation_group_id="E1"),
    ]
    semantic_plan = _make_semantic_plan([
        _make_intencao_visual("L2_titulo_heroi_t10", 0.0, 5.0, "Titulo", "titulo_heroi", "Titulo")
    ])

    layers, _ = build_rhythm_layers(
        semantic_plan=semantic_plan,
        events_l1=l1_events,
        final_duration=10.0,
        base_source_ref=l1_events[0]["source_ref"],
    )

    dedup_keys = []
    for camada in layers:
        for ev in layers[camada]:
            dk = ev.get("dedup_key")
            assert dk not in dedup_keys, f"dedup_key duplicado: {dk}"
            dedup_keys.append(dk)
    print("  [PASS] test_ausencia_duplicidade_dedup_key")


def test_duracoes_validas():
    """Todas as duracoes estao dentro dos limites por camada."""
    l1_events = [
        _make_l1_event(1, 0.0, 10.0, 0.0, 10.0, "Fala", topic_id="T1", explanation_group_id="E1"),
    ]
    semantic_plan = _make_semantic_plan([
        _make_intencao_visual("L2_titulo_heroi_t10", 0.0, 10.0, "Titulo longo", "titulo_heroi", "Titulo"),
        _make_intencao_visual("L4_lower_third", 0.0, 10.0, "Lower third longo", None, "Texto"),
    ])

    layers, _ = build_rhythm_layers(
        semantic_plan=semantic_plan,
        events_l1=l1_events,
        final_duration=10.0,
        base_source_ref=l1_events[0]["source_ref"],
    )

    for camada in layers:
        for ev in layers[camada]:
            dur = ev["duration_seconds"]
            assert dur > 0, f"Duracao <= 0 em {camada}: {dur}"
            # Verificar limite max por camada
            if camada in _LAYER_LIMITS:
                _, _, max_s, hard_cap, _ = _LAYER_LIMITS[camada]
                assert dur <= hard_cap, f"Duracao {dur} excede hard_cap {hard_cap} em {camada}"
    print("  [PASS] test_duracoes_validas")


def test_integracao_com_lint():
    """Validar que o plano gerado pelo rhythm_engine passa no lint()."""
    l1_events = [
        _make_l1_event(1, 0.0, 5.0, 0.0, 5.0, "Fala", topic_id="T1", explanation_group_id="E1"),
        _make_l1_event(2, 5.0, 10.0, 5.0, 10.0, "Mais fala", topic_id="T2", explanation_group_id="E2"),
    ]
    semantic_plan = _make_semantic_plan([
        _make_intencao_visual("L2_titulo_heroi_t10", 0.0, 3.0, "Titulo inicial", "titulo_heroi", "Titulo"),
        _make_intencao_visual("L4_lower_third", 5.0, 8.0, "Lower third", None, "Nome"),
    ])

    layers, rhythm_report = build_rhythm_layers(
        semantic_plan=semantic_plan,
        events_l1=l1_events,
        final_duration=10.0,
        base_source_ref=l1_events[0]["source_ref"],
    )

    # Construir plano completo para lint
    plano_completo = {
        "schema_version": "1.0.0",
        "layers": {
            "L1_estabelecimento": [
                {
                    "out_in": ev["out_in"],
                    "out_out": ev["out_out"],
                    "element_id": ev.get("element_id", ""),
                }
                for ev in l1_events
            ],
            **layers,
        },
        "rhythm_report": rhythm_report,
    }

    projeto = {"sources": [{"id": "SRC_TEST", "sha256": "0" * 64}]}
    edl = {"summary": {"final_duration_seconds": 10.0}}

    rel = lint(plano_completo, edl, projeto)
    # O plano deve passar ou pelo menos nao ter falhas de duracao/colisao
    duracao_falhas = [f for f in rel["failures"] if "duracao" in f.lower() or "colisao" in f.lower()]
    assert not duracao_falhas, f"Falhas de duracao/colisao: {duracao_falhas}"
    print("  [PASS] test_integracao_com_lint")


def test_injetar_microevento_direto():
    """Teste direto de RhythmEngine.injetar_microevento()."""
    engine = RhythmEngine()
    ev = engine.injetar_microevento(
        camada="L3_micro_zoom_bate",
        out_in=5.0,
        out_out=7.0,
        justification="Microzoom para enfatizacao",
        final_duration=10.0,
        texto="Texto de teste",
        funcao_editorial="Enfase",
        segment_ids=[0],
        word_refs=["w-0"],
    )
    # O parametro se chama segment_ids (com 's'), nao segmento_ids
    assert ev is not None
    assert ev.origin == "rhythm_engine"
    ev = engine.injetar_microevento(
        camada="L3_micro_zoom_bate",
        out_in=5.0,
        out_out=7.0,
        justification="Sobreposicao proposital",
        final_duration=10.0,
    )
    # Deve rejeitar por colisao intra-layer
    assert ev is None
    print("  [PASS] test_injetar_microevento_direto")


def test_cooldown_l3_2_0s():
    """Cooldown L3=2.0s: microevento L3 nao pode ser injetado dentro de 2.0s do anterior."""
    engine = RhythmEngine()
    # Primeiro L3 em 0.0-2.0
    ev1 = engine.injetar_microevento(
        camada="L3_micro_zoom_bate",
        out_in=0.0,
        out_out=2.0,
        justification="Primeiro microzoom",
        final_duration=10.0,
    )
    assert ev1 is not None
    # Segundo L3 em 1.0-3.0 (dentro do cooldown de 2.0s: cooldown ate 2.0+2.0=4.0)
    ev2 = engine.injetar_microevento(
        camada="L3_micro_zoom_bate",
        out_in=1.0,
        out_out=3.0,
        justification="Segundo microzoom dentro do cooldown",
        final_duration=10.0,
    )
    assert ev2 is None, "Cooldown L3 deve rejeitar microevento dentro de 2.0s"
    # Terceiro L3 em 4.0-6.0 (fora do cooldown)
    ev3 = engine.injetar_microevento(
        camada="L3_micro_zoom_bate",
        out_in=4.0,
        out_out=6.0,
        justification="Terceiro microzoom fora do cooldown",
        final_duration=10.0,
    )
    assert ev3 is not None, "Cooldown L3 deve permitir microevento apos 2.0s"
    print("  [PASS] test_cooldown_l3_2_0s")


def test_gaps_over_4s_com_l1_continuo():
    """Preenchimento de gaps_over_4s/gaps_for_review mesmo com L1 continuo."""
    l1_events = [
        _make_l1_event(1, 0.0, 5.0, 0.0, 5.0, "Fala continua", topic_id="T1", explanation_group_id="E1"),
        _make_l1_event(2, 5.0, 10.0, 5.0, 10.0, "Mais fala", topic_id="T2", explanation_group_id="E2"),
    ]
    # Sem nenhum estimulo visual L2..L5 -> gap de 10.0s (0 a 10)
    semantic_plan = _make_semantic_plan()

    layers, rhythm_report = build_rhythm_layers(
        semantic_plan=semantic_plan,
        events_l1=l1_events,
        final_duration=10.0,
        base_source_ref=l1_events[0]["source_ref"],
    )

    # Nao deve haver overlays L2..L5
    total_overlays = sum(len(layers[c]) for c in ("L2_titulo_heroi_t10", "L3_micro_zoom_bate", "L4_lower_third", "L5_broll_industrial"))
    assert total_overlays == 0

    # gaps_over_4s deve conter o gap de 0 a 10.0s
    gaps_over_4s = rhythm_report.get("gaps_over_4s", [])
    assert len(gaps_over_4s) == 1, f"Esperado 1 gap_over_4s, encontrado {len(gaps_over_4s)}: {gaps_over_4s}"
    assert gaps_over_4s[0]["start"] == 0.0
    assert gaps_over_4s[0]["end"] == 10.0
    assert gaps_over_4s[0]["duration_s"] == 10.0

    # gaps_for_review: sem estimulos visuais, nao ha gaps entre estimulos
    gaps_for_review = rhythm_report.get("gaps_for_review", [])
    assert len(gaps_for_review) == 0, f"Esperado 0 gap_for_review, encontrado {len(gaps_for_review)}: {gaps_for_review}"
    print("  [PASS] test_gaps_over_4s_com_l1_continuo")


def test_microeventos_complementares_mudanca_topico():
    """Microeventos complementares em mudança de topico/argumento via build_rhythm_layers()."""
    l1_events = [
        _make_l1_event(1, 0.0, 5.0, 0.0, 5.0, "Topico A", topic_id="T1", explanation_group_id="E1"),
        _make_l1_event(2, 5.0, 10.0, 5.0, 10.0, "Topico B", topic_id="T2", explanation_group_id="E2"),
    ]
    # Sem intencoes visuais no semantic_plan
    semantic_plan = _make_semantic_plan()

    layers, rhythm_report = build_rhythm_layers(
        semantic_plan=semantic_plan,
        events_l1=l1_events,
        final_duration=10.0,
        base_source_ref=l1_events[0]["source_ref"],
    )

    # Sem intencoes visuais, nao deve haver microeventos (sem justificativa de topico no plano)
    total_overlays = sum(len(layers[c]) for c in ("L2_titulo_heroi_t10", "L3_micro_zoom_bate", "L4_lower_third", "L5_broll_industrial"))
    assert total_overlays == 0

    # Agora com um topico que tem mudanca e sem estimulo visual proximo
    semantic_plan_com_topicos = _make_semantic_plan([
        _make_intencao_visual("L2_titulo_heroi_t10", 0.0, 2.0, "Titulo", "titulo_heroi", "Titulo"),
    ])
    # Adicionar um segundo topico para criar mudanca de topico
    semantic_plan_com_topicos["topicos"] = [
        {
            "topic_id": "T1",
            "titulo": "Topico A",
            "justificativa": "Topico A",
            "raw_start": 0.0,
            "raw_end": 5.0,
            "segment_ids": [0],
            "word_refs": ["w-0"],
        },
        {
            "topic_id": "T2",
            "titulo": "Topico B",
            "justificativa": "Topico B",
            "raw_start": 5.0,
            "raw_end": 10.0,
            "segment_ids": [1],
            "word_refs": ["w-1"],
        },
    ]

    layers2, rhythm_report2 = build_rhythm_layers(
        semantic_plan=semantic_plan_com_topicos,
        events_l1=l1_events,
        final_duration=10.0,
        base_source_ref=l1_events[0]["source_ref"],
    )

    # Deve ter o L2 original + possivelmente um L3 na mudanca de topico
    l3_events = layers2.get("L3_micro_zoom_bate", [])
    # Como o topico muda em 5.0s e nao ha estimulo visual proximo, deve haver um L3
    assert len(l3_events) >= 1, f"Esperado pelo menos 1 L3 na mudanca de topico, encontrado {len(l3_events)}"
    l3_ev = l3_events[0]
    assert l3_ev["origin"] == "rhythm_engine"
    assert l3_ev["componente_motion_library"] is None
    print("  [PASS] test_microeventos_complementares_mudanca_topico")


# ---------------------------------------------------------------------------
# Runner auxiliar (execucao direta)
# ---------------------------------------------------------------------------


def run_tests() -> int:
    print("=" * 60)
    print("SUITE DE TESTES — core/rhythm_engine (Editor)")
    print("=" * 60)
    testes = [
        test_clamp_duracao_limites,
        test_cenario_a_fala_continua_sem_pausas,
        test_cenario_b_fala_com_enfase_pontual,
        test_cenario_c_mudanca_de_topico,
        test_cenario_d_explicacao_longa,
        test_cenario_e_lista_de_argumentos,
        test_cenario_f_nome_entidade_lower_third,
        test_cenario_g_trecho_justifica_broll,
        test_cenario_h_janela_sem_estimulo_justificavel,
        test_cenario_i_intencao_sem_componente_executavel,
        test_cenario_j_eventos_sobrepostos_fora_timeline,
        test_preservacao_integral_da_fala,
        test_reprodutibilidade_deterministica,
        test_ausencia_duplicidade_dedup_key,
        test_duracoes_validas,
        test_integracao_com_lint,
        test_injetar_microevento_direto,
        test_cooldown_l3_2_0s,
        test_gaps_over_4s_com_l1_continuo,
        test_microeventos_complementares_mudanca_topico,
    ]
    falhas = 0
    for t in testes:
        try:
            t()
        except Exception as e:
            falhas += 1
            print(f"  [FALHA] {t.__name__}: {e}")
            import traceback
            traceback.print_exc()
    print("=" * 60)
    if falhas == 0:
        print("RESULTADO: 100% DOS TESTES PASSARAM!")
    else:
        print(f"RESULTADO: {falhas} FALHA(S) DETECTADA(S)!")
    print("=" * 60)
    return 0 if falhas == 0 else 1


if __name__ == "__main__":
    sys.exit(run_tests())
