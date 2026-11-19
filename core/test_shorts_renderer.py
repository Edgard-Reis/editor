# -*- coding: utf-8 -*-
"""core/test_shorts_renderer.py

Testes dos derivados verticais 9:16 (Shorts) - Lote 3 (fechamento V1).

Tudo roda em tmp_path, sem tocar arquivos do repositorio.
Nenhuma descoberta automatica de Shorts, selecao por viralizacao ou
inteligencia editorial de recortes: os clips sao fornecidos explicitamente.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

import pytest

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from core.shorts_renderer import (  # noqa: E402
    ShortsRenderError,
    approve_short_9x16,
    render_shorts_from_master,
)
from core.pipeline import (  # noqa: E402
    MasterApprovalError,
    approve_master_16x9,
    run_episode_pipeline,
    verify_master_16x9_approval,
)
from core.semantic_planner import (  # noqa: E402
    CallableMockProvider,
    SemanticConsent,
)
from core.workspace import (  # noqa: E402
    WorkspaceLoader,
    init_workspace,
    load_brand_profile,
)

# Helpers da suíte existente (reuso, sem duplicar).
from core.test_pipeline_e2e import (  # noqa: E402
    MARCA,
    EPISODIO,
    _build_semantic_plan,
    _build_transcription,
    _build_workspace,
    _ffmpeg,
    _sha256,
)

MASTER_APPROVED_BY = "proprietario"

CLIP_A = {"short_id": "curta-abertura", "start": 0.5, "end": 2.5}
CLIP_B = {"short_id": "curta-credencial", "start": 4.0, "end": 6.0}


# ---------------------------------------------------------------------------
# Fixture: workspace com master 16:9 aprovado (Modalidade A, injetada)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="function")
def approved_master_env(tmp_path_factory) -> Dict[str, Any]:
    """Construi workspace, roda o pipeline e aprova o master 16:9."""
    root = tmp_path_factory.mktemp("shorts_master")
    source = _build_workspace(root)

    loader = WorkspaceLoader(root)
    loader.load_workspace()
    loader.load_brand_profile(MARCA)

    consent = SemanticConsent(
        destination="mock_local",
        shared_data=["transcript.json", "alignment.json"],
        authorized=True,
        notes="Teste de derivados 9:16.",
    )
    result = run_episode_pipeline(
        root,
        MARCA,
        EPISODIO,
        source_video=source,
        transcricao_injetada=_build_transcription(),
        semantic_provider=CallableMockProvider(_build_semantic_plan),
        consent=consent,
        strict=True,
    )

    master_path = Path(result["master_path"])
    assert master_path.is_file() and master_path.stat().st_size > 0

    # Aprova o master 16:9 (pre-condicao para renderizar shorts).
    aprovacao = approve_master_16x9(
        root, MARCA, EPISODIO, approved_by=MASTER_APPROVED_BY
    )
    assert aprovacao["approved"] is True

    verificacao = verify_master_16x9_approval(root, MARCA, EPISODIO)
    assert verificacao["approved"] is True

    return {
        "root": root,
        "source": source,
        "master_path": master_path,
        "master_sha256": aprovacao["master_sha256"],
        "master_duration": result["render_expected_duration_seconds"],
        "project_path": loader.project_file(MARCA, EPISODIO),
        "loader": loader,
    }


# ---------------------------------------------------------------------------
# Positivo
# ---------------------------------------------------------------------------


def test_render_shorts_positivo_e_aprovacao_individual(approved_master_env):
    """Master aprovado -> gera 2 derivados 9:16 validos; aprova apenas um."""
    env = approved_master_env
    master_path = env["master_path"]
    sha_antes = _sha256(master_path)

    resultado = render_shorts_from_master(
        env["root"], MARCA, EPISODIO, [CLIP_A, CLIP_B]
    )
    assert resultado["master_sha256"] == env["master_sha256"]
    assert len(resultado["shorts"]) == 2

    shorts_por_id = {s["short_id"]: s for s in resultado["shorts"]}
    assert set(shorts_por_id) == {"curta-abertura", "curta-credencial"}

    for short in resultado["shorts"]:
        out = Path(short["output_path"])
        assert out.is_file() and out.stat().st_size > 0
        assert short["source_master_sha256"] == env["master_sha256"]
        assert short["qa"]["ok"] is True, short["qa"]["problems"]
        assert short["safe_zones_9x16"] is not None
        # Delta-Hash = 0 no master (nao modificado).
        assert _sha256(master_path) == sha_antes

        # QA: 1080x1920, 30fps, 48kHz, 2ch, duracao coerente.
        qa = short["qa"]
        dur_esperada = short["end"] - short["start"]
        assert abs(qa["duration"] - dur_esperada) <= 0.10, qa

    # Aprova apenas curta-abertura; curta-credencial permanece nao aprovada.
    aprov = approve_short_9x16(
        env["root"], MARCA, EPISODIO, "curta-abertura",
        approved_by=MASTER_APPROVED_BY,
    )
    assert aprov["approved"] is True
    assert aprov["short_id"] == "curta-abertura"
    assert aprov["approved_by"] == MASTER_APPROVED_BY
    assert aprov["qa_ok"] is True

    # Manifest reflete aprovacao apenas de curta-abertura.
    manifest_path = Path(resultado["manifest_path"])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["curta-abertura"]["approved"] is True
    assert manifest["curta-abertura"]["approved_by"] == MASTER_APPROVED_BY
    assert manifest["curta-credencial"]["approved"] is False
    assert manifest["curta-credencial"]["approved_by"] is None

    # project.json reflete aprovacao apenas de curta-abertura.
    projeto = json.loads(env["project_path"].read_text(encoding="utf-8"))
    derivs = projeto["derivatives"]["shorts_9x16"]
    assert derivs["curta-abertura"]["approved"] is True
    assert derivs["curta-credencial"]["approved"] is False

    # Re-verificacao do derivado aprovado continua valida.
    verif_a = verify_short_approval_state(
        env["root"], MARCA, EPISODIO, "curta-abertura"
    )
    assert verif_a["approved"] is True


def verify_short_approval_state(
    root: Path, marca_id: str, episodio_id: str, short_id: str
) -> Dict[str, Any]:
    """Lê o estado de aprovacao de um short do manifest/project.json."""
    loader = WorkspaceLoader(root)
    loader.load_workspace()
    from core.shorts_renderer import _shorts_dir, _load_manifest  # noqa: F401

    shorts_dir = _shorts_dir(root, marca_id, episodio_id)
    manifest = _load_manifest(shorts_dir)
    entry = manifest.get(short_id, {})
    return {
        "approved": bool(entry.get("approved")),
        "approved_by": entry.get("approved_by"),
        "approved_at": entry.get("approved_at"),
        "qa_ok": bool((entry.get("qa") or {}).get("ok")),
        "output_sha256": entry.get("output_sha256"),
    }


# ---------------------------------------------------------------------------
# Negativo 1: master nao aprovado
# ---------------------------------------------------------------------------


def test_render_sem_master_aprovado_erro(tmp_path):
    """Master nao aprovado -> ShortsRenderError."""
    root = tmp_path / "sem_aprovacao"
    init_workspace(root)
    loader = WorkspaceLoader(root)
    loader.load_workspace()

    # Cria a marca (exigida por load_brand_profile / resolve_episodio_asset).
    marca_dir = root / "projetos" / MARCA / "branding"
    marca_dir.mkdir(parents=True, exist_ok=True)
    (marca_dir / "config.json").write_text(
        json.dumps(
            {
                "schema_version": "1.0.0",
                "brand_id": MARCA,
                "display_name": "Marca",
                "marca": {"destaque": "#004aad", "fonte": "Inter"},
                "preferencias_edicao": {},
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    # Cria project.json do episodio (master nao aprovado).
    loader.project_file(MARCA, EPISODIO).parent.mkdir(
        parents=True, exist_ok=True
    )
    projeto = {
        "schema_version": "1.0.0",
        "marca_id": MARCA,
        "episodio_id": EPISODIO,
        "nome": EPISODIO,
        "current_stage": "04_RENDER_COMPLETED",
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
        "sources": [],
        "artifacts": {},
        "approvals": {"master_16x9_approved": False},
    }
    loader.project_file(MARCA, EPISODIO).write_text(
        json.dumps(projeto, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # Cria master mas NAO o aprova.
    master_dir = loader.resolve_episodio_asset(
        MARCA, EPISODIO, "workspace/renders"
    )
    master_dir.mkdir(parents=True, exist_ok=True)
    master = master_dir / "master_16x9.mp4"
    _ffmpeg(
        [
            "ffmpeg", "-y", "-f", "lavfi", "-i",
            "color=c=black:s=1920x1080:r=30:d=1",
            "-f", "lavfi", "-i",
            "sine=frequency=440:sample_rate=48000:duration=10",
            "-t", "10", "-r", "30",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-ar", "48000", "-ac", "2", "-shortest",
            str(master),
        ]
    )

    with pytest.raises(ShortsRenderError) as exc:
        render_shorts_from_master(root, MARCA, EPISODIO, [CLIP_A])
    assert "nao aprovado" in str(exc.value).lower() or "aprovado" in str(
        exc.value
    ).lower()


# ---------------------------------------------------------------------------
# Negativo 2: master adulterado apos aprovacao
# ---------------------------------------------------------------------------


def test_render_master_adulterado_apos_aprovacao_erro(approved_master_env):
    """Master adulterado apos aprovacao -> ShortsRenderError."""
    env = approved_master_env
    master_path = env["master_path"]

    # Adiciona bytes ao master (adulteracao).
    master_path.write_bytes(master_path.read_bytes() + b"\x00padding")

    with pytest.raises(ShortsRenderError) as exc:
        render_shorts_from_master(env["root"], MARCA, EPISODIO, [CLIP_A])
    assert "nao aprovado" in str(exc.value).lower() or "aprovado" in str(
        exc.value
    ).lower() or "divergente" in str(exc.value).lower()


# ---------------------------------------------------------------------------
# Negativo 3: intervalo invalido
# ---------------------------------------------------------------------------


def test_render_intervalo_invalido_erro(approved_master_env):
    """Intervalos invalidos -> ShortsRenderError."""
    env = approved_master_env
    dur = env["master_duration"]

    casos_invalidos: List[Dict[str, Any]] = [
        {"short_id": "c1", "start": 2.0, "end": 1.0},  # end <= start
        {"short_id": "c2", "start": -0.5, "end": 1.0},  # start < 0
        {"short_id": "c3", "start": 0.0, "end": dur + 1.0},  # end > duracao
    ]
    for clip in casos_invalidos:
        with pytest.raises(ShortsRenderError):
            render_shorts_from_master(env["root"], MARCA, EPISODIO, [clip])


def test_render_clips_vazio_erro(approved_master_env):
    """clips vazio -> ShortsRenderError."""
    env = approved_master_env
    with pytest.raises(ShortsRenderError):
        render_shorts_from_master(env["root"], MARCA, EPISODIO, [])


# ---------------------------------------------------------------------------
# Negativo 4: derivado alterado apos geracao
# ---------------------------------------------------------------------------


def test_derivado_alterado_apos_geracao_erro(approved_master_env):
    """Derivado alterado apos geracao -> erro na aprovacao/verificacao."""
    env = approved_master_env

    render_shorts_from_master(env["root"], MARCA, EPISODIO, [CLIP_A])

    # Localiza o arquivo do derivado.
    loader = WorkspaceLoader(env["root"])
    loader.load_workspace()
    from core.shorts_renderer import _shorts_dir, _load_manifest  # noqa: F401

    shorts_dir = _shorts_dir(env["root"], MARCA, EPISODIO)
    manifest = _load_manifest(shorts_dir)
    entry = manifest["curta-abertura"]
    out_path = Path(entry["output_path"])
    sha_antes = _sha256(out_path)

    # Adultera o derivado.
    out_path.write_bytes(out_path.read_bytes() + b"\x00padding")

    # Aprovacao deve rejeitar (SHA-256 divergente).
    with pytest.raises(ShortsRenderError) as exc:
        approve_short_9x16(
            env["root"], MARCA, EPISODIO, "curta-abertura",
            approved_by=MASTER_APPROVED_BY,
        )
    assert "adulterado" in str(exc.value).lower() or "divergente" in str(
        exc.value
    ).lower()

    # O derivado permaneceu nao aprovado.
    pos = _load_manifest(shorts_dir)
    assert pos["curta-abertura"]["approved"] is False
    # SHA do arquivo voltou ao original (test so adicionou bytes; nao restaura,
    # mas o estado de aprovacao e o que importa).
    assert _sha256(out_path) != sha_antes


def test_suggest_shorts_opusclip_e_render_aprovados_so_cortes(tmp_path):
    """Modo 'so_cortes': suggest_shorts_opusclip para no Portao 2 e render_approved_shorts corta apenas aprovados."""
    from core.ingest import ingest_media
    from core.analyze import analyze_episodio
    from core.shorts_renderer import suggest_shorts_opusclip, render_approved_shorts

    root = tmp_path / "ws_so_cortes"
    source = _build_workspace(root)
    assert ingest_media(str(source), MARCA, EPISODIO, str(root)) == 0
    analyze_episodio(MARCA, EPISODIO, str(root), transcricao_injetada=_build_transcription())

    briefing_dir = root / "projetos" / MARCA / "episodios" / EPISODIO / "workspace" / "briefing"
    briefing_dir.mkdir(parents=True, exist_ok=True)
    (briefing_dir / "user_brief.json").write_text(
        json.dumps({"modo": "so_cortes", "qtd_cortes_desejada": 2}), encoding="utf-8"
    )

    sug = suggest_shorts_opusclip(root, MARCA, EPISODIO)
    assert sug["ok"] is True
    assert sug["modo"] == "so_cortes"
    assert sug["source_kind"] == "brutos"
    assert sug["stopped_at_gate"] is True
    assert sug["count"] == 2
    assert Path(sug["shorts_briefing_path"]).is_file()
    assert Path(sug["shorts_plan_path"]).is_file()

    for s in sug["suggestions"]:
        assert 0.0 <= s["nota_potencial"] <= 10.0
        assert s["justificativa_editorial"]
        assert s["gancho_abertura"]
        assert s["minutagem"]
        assert s["titulo"]
        assert s["approved"] is False

    # Portao 2: sem aprovar nenhum corte, deve recusar render
    with pytest.raises(ShortsRenderError):
        render_approved_shorts(root, MARCA, EPISODIO)

    # Aprova apenas corte-01
    res = render_approved_shorts(root, MARCA, EPISODIO, approved_short_ids=["corte-01"])
    assert len(res["shorts"]) == 1
    assert res["shorts"][0]["short_id"] == "corte-01"
    assert res["shorts"][0]["qa"]["ok"] is True
    assert Path(res["shorts"][0]["output_path"]).is_file()
