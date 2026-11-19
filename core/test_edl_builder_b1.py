# -*- coding: utf-8 -*-
"""core/test_edl_builder_b1.py

Testes da correcao B1 (origem da timeline EDL):

Verifica que o primeiro evento retido pelo `build_edl_from_alignment` sempre
começa em `out_in = 0.0` no eixo final, mesmo quando a gravação tem silêncio
inicial (`raw_start > 0`), preservando continuidade do eixo `out_*` e os
timestamps originais `raw_in`/`raw_out` do alignment.

Mantido em arquivo separado para não poluir `core/test_editorial.py` (que
possui 15 testes preexistentes que devem ser preservados).
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List

import pytest

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from core.edl_builder import build_edl_from_alignment, EdlBuilderError  # noqa: E402
from core.workspace import WorkspaceLoader, init_workspace, load_brand_profile  # noqa: E402

MARCA = "marca-editorial"
EPISODIO = "ep-editorial"


# ---------------------------------------------------------------------------
# Helpers de montagem do workspace minimo
# ---------------------------------------------------------------------------


def _montar_workspace(tmp: Path) -> Dict[str, Any]:
    init_workspace(tmp)
    loader = WorkspaceLoader(tmp)
    loader.load_workspace()

    # Escreve branding/config.json diretamente (sem depender de
    # vortex-edicao/criar_projeto.py, que nao esta dentro do workspace tmp).
    marca_dir = tmp / "projetos" / MARCA / "branding"
    marca_dir.mkdir(parents=True, exist_ok=True)
    config = {
        "schema_version": "1.0.0",
        "brand_id": MARCA,
        "display_name": f"Marca {MARCA}",
        "marca": {"destaque": "#004aad", "fonte": "Inter"},
        "preferencias_edicao": {
            "canal": "Canal Editorial",
            "audio": {
                "silence_guard_ms": [180, 220],
                "jumpcut_gap_threshold_ms": 450,
                "jumpcut_target_gap_ms": [200, 250],
            },
        },
    }
    (marca_dir / "config.json").write_text(
        json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    marca_profile = load_brand_profile(tmp, MARCA)
    return marca_profile


def _gravar_json(path: Path, dados: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(dados, f, indent=2, ensure_ascii=False)


def _criar_episodio(tmp: Path, unidades: List[Dict[str, Any]]) -> None:
    """Cria marca/episodio/project.json + alignment.json (minimo para edl_builder)."""
    loader = WorkspaceLoader(tmp)
    loader.load_workspace()
    fonte_dir = loader.resolve_episodio_asset(MARCA, EPISODIO, "workspace/fonte")
    fonte_dir.mkdir(parents=True, exist_ok=True)

    projeto = {
        "schema_version": "1.0.0",
        "marca_id": MARCA,
        "episodio_id": EPISODIO,
        "nome": EPISODIO,
        "current_stage": "01_GRAVACAO_ORIGINAL",
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
        "sources": [
            {
                "id": f"SRC_{MARCA.upper()}_{EPISODIO.upper()}",
                "path": str(tmp / "brutos" / "video.mp4"),
                "sha256": "abc" * 20 + "def" * 6,
            }
        ],
        "artifacts": {},
        "approvals": {"master_16x9_approved": False},
    }
    _gravar_json(loader.project_file(MARCA, EPISODIO), projeto)

    alinhamento = {
        "schema_version": "1.0.0",
        "status": "COMPLETED",
        "editorial_units": unidades,
    }
    _gravar_json(fonte_dir / "alignment.json", alinhamento)


def _unidade(raw_start: float, raw_end: float, palavras: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "raw_start": raw_start,
        "raw_end": raw_end,
        "words": [
            {
                "word": p["w"],
                "start": p["t"],
                "end": p["f"],
                "probability": p.get("probability", 0.98),
            }
            for p in palavras
        ],
        "text": " ".join(p["w"] for p in palavras),
        "silence_removed_before": 0.0,
    }


def _run_edl(tmp: Path, marca_profile: Dict[str, Any] | None = None):
    loader = WorkspaceLoader(tmp)
    loader.load_workspace()
    if marca_profile is None:
        marca_profile = loader.load_brand_profile(MARCA)["config_json"]
    return build_edl_from_alignment(
        alignment_path=loader.resolve_episodio_asset(
            MARCA, EPISODIO, "workspace/fonte/alignment.json"
        ),
        workspace_root=tmp,
        marca_id=MARCA,
        episodio_id=EPISODIO,
        brand_profile=marca_profile,
    )


# ---------------------------------------------------------------------------
# Testes B1
# ---------------------------------------------------------------------------


def test_b1_silencio_inicial_primeiro_evento_em_zero():
    """raw_start = 1.77s (> pad_s): primeiro evento inicia em out_in=0.0."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        _montar_workspace(tmp)
        _criar_episodio(
            tmp,
            [
                _unidade(1.77, 2.5, [{"w": "ola", "t": 1.77, "f": 2.0}]),
                _unidade(3.0, 4.0, [{"w": "mundo", "t": 3.0, "f": 3.5}]),
            ],
        )
        edl, _ = _run_edl(tmp)
        eventos = edl["timeline_events"]
        assert len(eventos) >= 2
        assert abs(eventos[0]["out_in"] - 0.0) <= 1e-6, eventos[0]
        assert abs(eventos[0]["raw_in"] - 1.77) <= 1e-6
        assert abs(eventos[0]["raw_out"] - 2.5) <= 1e-6
        for i in range(1, len(eventos)):
            assert abs(eventos[i]["out_in"] - eventos[i - 1]["out_out"]) <= 1e-6, (
                f"descontinuidade evento {i}: {eventos[i-1]} -> {eventos[i]}"
            )


def test_b1_sem_silencio_inicial_primeiro_evento_em_zero():
    """raw_start = 0.0: primeiro evento inicia em out_in=0.0 (compatibilidade)."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        _montar_workspace(tmp)
        _criar_episodio(
            tmp,
            [
                _unidade(0.0, 2.0, [{"w": "inicio", "t": 0.0, "f": 1.0}]),
                _unidade(2.5, 3.5, [{"w": "fim", "t": 2.5, "f": 3.0}]),
            ],
        )
        edl, _ = _run_edl(tmp)
        eventos = edl["timeline_events"]
        assert len(eventos) >= 1
        assert abs(eventos[0]["out_in"] - 0.0) <= 1e-6
        for i in range(1, len(eventos)):
            assert abs(eventos[i]["out_in"] - eventos[i - 1]["out_out"]) <= 1e-6


def test_b1_varias_unidades_e_pausas_continuidade():
    """Varias unidades com pausas mantem continuidade do eixo out_* e raw inalterado."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        _montar_workspace(tmp)
        unidades = [
            _unidade(1.0, 1.8, [{"w": "a", "t": 1.0, "f": 1.3}]),
            _unidade(2.6, 3.4, [{"w": "b", "t": 2.6, "f": 3.0}]),
            _unidade(4.2, 5.1, [{"w": "c", "t": 4.2, "f": 4.7}]),
        ]
        _criar_episodio(tmp, unidades)
        edl, _ = _run_edl(tmp)
        eventos = edl["timeline_events"]
        assert len(eventos) == 3
        assert abs(eventos[0]["out_in"] - 0.0) <= 1e-6
        for i in range(1, len(eventos)):
            assert abs(eventos[i]["out_in"] - eventos[i - 1]["out_out"]) <= 1e-6
        assert abs(eventos[0]["raw_in"] - 1.0) <= 1e-6
        assert abs(eventos[0]["raw_out"] - 1.8) <= 1e-6
        assert abs(eventos[2]["raw_in"] - 4.2) <= 1e-6
        assert abs(eventos[2]["raw_out"] - 5.1) <= 1e-6


def test_b1_duracao_positiva_e_final_coerente():
    """Nenhum evento duracao <= 0 e out_out final == final_duration."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        _montar_workspace(tmp)
        _criar_episodio(
            tmp,
            [_unidade(1.77, 2.5, [{"w": "ola", "t": 1.77, "f": 2.0}])],
        )
        edl, _ = _run_edl(tmp)
        eventos = edl["timeline_events"]
        for ev in eventos:
            assert ev["out_out"] > ev["out_in"]
            assert ev["duration_seconds"] > 0
        assert abs(eventos[-1]["out_out"] - edl["summary"]["final_duration_seconds"]) <= 1e-6


def test_b1_nao_levanta_descontinuidade_com_silencio_inicial():
    """Antes da correcao levantava EdlBuilderError 'Descontinuidade no eixo out_*'."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        _montar_workspace(tmp)
        _criar_episodio(
            tmp, [_unidade(1.77, 2.5, [{"w": "ola", "t": 1.77, "f": 2.0}])]
        )
        edl, _ = _run_edl(tmp)
        assert edl["timeline_events"][0]["out_in"] == 0.0
