# -*- coding: utf-8 -*-
"""core/test_master_approval.py

Testes do gate de aprovacao do master 16:9 (Lote 2 - fechamento V1).

Cobre:
  - Positivo: render valido -> approve_master_16x9 grava SHA-256/by/at e
    verify_master_16x9_approval confirma valido.
  - Negativo 1: tentar aprovar sem master existente -> MasterApprovalError.
  - Negativo 2: tentar aprovar com QA reprovado (video sem audio / qa.ok=False)
    -> MasterApprovalError.
  - Negativo 3: tentar aprovar com approved_by vazio -> MasterApprovalError.
  - Invalidacao 1: alterar bytes do master apos aprovacao ->
    verify_master_16x9_approval detecta divergencia de SHA-256 e invalida
    (master_16x9_approved volta para False).
  - Invalidacao 2: novo render no pipeline reseta master_16x9_approved para
    False.

Tudo roda em tmp_path, sem tocar arquivos do repositorio.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

import pytest

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from core.pipeline import (  # noqa: E402
    MasterApprovalError,
    PipelineError,
    approve_master_16x9,
    render_existing_episode,
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
    _make_background,
    _make_wav,
    _sha256,
)

MASTER_APPROVED_BY = "proprietario"


# ---------------------------------------------------------------------------
# Fixture: workspace renderizado com master valido (Modalidade A, injetada)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="function")
def rendered_env(tmp_path_factory) -> Dict[str, Any]:
    """Construi workspace, roda o pipeline e devolve caminhos do master."""
    root = tmp_path_factory.mktemp("master_approval")
    source = _build_workspace(root)

    loader = WorkspaceLoader(root)
    loader.load_workspace()
    loader.load_brand_profile(MARCA)

    consent = SemanticConsent(
        destination="mock_local",
        shared_data=["transcript.json", "alignment.json"],
        authorized=True,
        notes="Teste de aprovacao do master 16:9.",
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

    return {
        "root": root,
        "source": source,
        "master_path": Path(result["master_path"]),
        "traceability_path": Path(result["traceability_path"]),
        "project_path": loader.project_file(MARCA, EPISODIO),
        "result": result,
        "loader": loader,
    }


# ---------------------------------------------------------------------------
# Positivo
# ---------------------------------------------------------------------------


def test_aprove_master_valido_e_verifica_ok(rendered_env):
    """Render valido -> aprova e verify confirma."""
    env = rendered_env
    master_path = env["master_path"]
    assert master_path.is_file() and master_path.stat().st_size > 0

    aprovacao = approve_master_16x9(
        env["root"], MARCA, EPISODIO, approved_by=MASTER_APPROVED_BY
    )
    assert aprovacao["approved"] is True
    assert aprovacao["master_16x9_approved"] is True
    assert aprovacao["approved_by"] == MASTER_APPROVED_BY
    assert aprovacao["master_sha256"]
    assert aprovacao["master_sha256"] == _sha256(master_path)
    assert aprovacao["approved_at"]

    verificacao = verify_master_16x9_approval(
        env["root"], MARCA, EPISODIO
    )
    assert verificacao["approved"] is True
    assert verificacao["master_16x9_approved"] is True
    assert verificacao["current_sha256"] == aprovacao["master_sha256"]
    assert verificacao["reason"] is None

    # project.json gravado com os campos de aprovacao.
    projeto = json.loads(
        env["project_path"].read_text(encoding="utf-8")
    )
    aprova = projeto["approvals"]
    assert aprova["master_16x9_approved"] is True
    assert aprova["master_16x9_sha256"] == aprovacao["master_sha256"]
    assert aprova["master_16x9_approved_by"] == MASTER_APPROVED_BY
    assert aprova["master_16x9_approved_at"]


# ---------------------------------------------------------------------------
# Negativo 1: master inexistente
# ---------------------------------------------------------------------------


def test_aprove_master_inexistente_erro(rendered_env):
    """Tentar aprovar master nao existente -> MasterApprovalError."""
    env = rendered_env
    inexistente = env["root"] / "nao_existe" / "master.mp4"
    with pytest.raises(MasterApprovalError) as exc:
        approve_master_16x9(
            env["root"], MARCA, EPISODIO,
            approved_by=MASTER_APPROVED_BY, master_path=inexistente,
        )
    assert "inexistente ou vazio" in str(exc.value).lower()


# ---------------------------------------------------------------------------
# Negativo 2: QA reprovado (video sem audio / qa.ok=False)
# ---------------------------------------------------------------------------


def test_aprove_qa_reprovado_erro(tmp_path):
    """Master sem audio + traceability qa.ok=False -> MasterApprovalError."""
    root = tmp_path / "qa_reprovado"
    init_workspace(root)
    loader = WorkspaceLoader(root)
    loader.load_workspace()
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
    episodio_dir = loader.resolve_episodio_asset(MARCA, EPISODIO, "")
    episodio_dir.mkdir(parents=True, exist_ok=True)
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
    loader.project_file(MARCA, EPISODIO).parent.mkdir(
        parents=True, exist_ok=True
    )
    loader.project_file(MARCA, EPISODIO).write_text(
        json.dumps(projeto, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # Master sem audio.
    master = root / "projetos" / MARCA / "episodios" / EPISODIO / "workspace" / "renders" / "master_16x9.mp4"
    master.parent.mkdir(parents=True, exist_ok=True)
    _ffmpeg(
        [
            "ffmpeg", "-y", "-f", "lavfi", "-i",
            "color=c=black:s=1920x1080:r=30:d=1",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-t", "1", str(master),
        ]
    )

    # traceability_report.json com qa.ok=False.
    renders_dir = master.parent
    trace = {
        "schema_version": "1.0.0",
        "identification": {
            "master_path": str(master),
            "master_sha256": _sha256(master),
        },
        "qa": {"ok": False, "problems": ["sem stream de audio"]},
    }
    (renders_dir / "traceability_report.json").write_text(
        json.dumps(trace, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    with pytest.raises(MasterApprovalError) as exc:
        approve_master_16x9(
            root, MARCA, EPISODIO, approved_by=MASTER_APPROVED_BY
        )
    assert "QA nao aprovado" in str(exc.value)


# ---------------------------------------------------------------------------
# Negativo 3: approved_by vazio
# ---------------------------------------------------------------------------


def test_aprove_approved_by_vazio_erro(rendered_env):
    """approved_by vazio -> MasterApprovalError."""
    env = rendered_env
    for vazio in ("", "   ", None):
        with pytest.raises(MasterApprovalError) as exc:
            approve_master_16x9(
                env["root"], MARCA, EPISODIO, approved_by=vazio,
            )
        assert "nao pode ser vazio" in str(exc.value).lower()


# ---------------------------------------------------------------------------
# Invalidacao 1: master alterado apos aprovacao
# ---------------------------------------------------------------------------


def test_invalidacao_master_alterado(rendered_env):
    """Alterar bytes do master apos aprovacao invalida a aprovacao."""
    env = rendered_env
    master_path = env["master_path"]
    sha_antes = _sha256(master_path)

    # Aprova.
    approve_master_16x9(
        env["root"], MARCA, EPISODIO, approved_by=MASTER_APPROVED_BY
    )
    projeto_antes = json.loads(
        env["project_path"].read_text(encoding="utf-8")
    )
    assert projeto_antes["approvals"]["master_16x9_approved"] is True

    # Altera bytes do master.
    master_path.write_bytes(master_path.read_bytes() + b"\x00padding")

    # Verify detecta divergencia e invalida.
    verificacao = verify_master_16x9_approval(
        env["root"], MARCA, EPISODIO
    )
    assert verificacao["approved"] is False
    assert verificacao["master_16x9_approved"] is False
    assert verificacao["reason"] is not None
    assert "SHA-256" in verificacao["reason"]

    # project.json refletiu a invalidez.
    projeto_depois = json.loads(
        env["project_path"].read_text(encoding="utf-8")
    )
    assert projeto_depois["approvals"]["master_16x9_approved"] is False
    assert projeto_depois["approvals"]["master_16x9_sha256"] is None

    # require_valid=True levanta MasterApprovalError.
    with pytest.raises(MasterApprovalError):
        verify_master_16x9_approval(
            env["root"], MARCA, EPISODIO, require_valid=True
        )


# ---------------------------------------------------------------------------
# Invalidacao 2: novo render reseta aprovacao
# ---------------------------------------------------------------------------


def test_invalidacao_novo_render_reseta(rendered_env, tmp_path):
    """Novo render no pipeline reseta master_16x9_approved para False."""
    env = rendered_env

    # Aprova.
    approve_master_16x9(
        env["root"], MARCA, EPISODIO, approved_by=MASTER_APPROVED_BY
    )
    projeto_antes = json.loads(
        env["project_path"].read_text(encoding="utf-8")
    )
    assert projeto_antes["approvals"]["master_16x9_approved"] is True

    # Novo render (re-renderiza o mesmo episodio).
    # O ingest deixa brutos/source.mp4 apenas-leitura; torna gravavel para
    # permitir o re-render no mesmo workspace.
    brutos_path = (
        env["root"]
        / "projetos"
        / MARCA
        / "episodios"
        / EPISODIO
        / "brutos"
        / "source.mp4"
    )
    if brutos_path.exists():
        brutos_path.chmod(0o644)

    result2 = run_episode_pipeline(
        env["root"],
        MARCA,
        EPISODIO,
        source_video=env["source"],
        transcricao_injetada=_build_transcription(),
        semantic_provider=CallableMockProvider(_build_semantic_plan),
        consent=SemanticConsent(
            destination="mock_local",
            shared_data=["transcript.json", "alignment.json"],
            authorized=True,
            notes="Re-render para invalidacao de aprovacao.",
        ),
        strict=True,
    )

    projeto_depois = json.loads(
        env["project_path"].read_text(encoding="utf-8")
    )
    assert projeto_depois["approvals"]["master_16x9_approved"] is False
    assert projeto_depois["approvals"]["master_16x9_sha256"] is None
    assert projeto_depois["approvals"]["master_16x9_approved_by"] is None
    assert projeto_depois["approvals"]["master_16x9_approved_at"] is None

    # O novo master existe e tem um SHA (possivelmente diferente).
    novo_master = Path(result2["master_path"])
    assert novo_master.is_file()

    # Verify agora deve reportar nao aprovado (resetado pelo render).
    verificacao = verify_master_16x9_approval(
        env["root"], MARCA, EPISODIO
    )
    assert verificacao["approved"] is False
    assert verificacao["master_16x9_approved"] is False


# ---------------------------------------------------------------------------
# render_existing_episode
# ---------------------------------------------------------------------------


def test_render_existing_episode_positivo(rendered_env, tmp_path):
    """Re-render de episodio existente sem reexecutar pipeline completo."""
    env = rendered_env

    # Aprova o master primeiro.
    approve_master_16x9(
        env["root"], MARCA, EPISODIO, approved_by=MASTER_APPROVED_BY
    )
    projeto_antes = json.loads(
        env["project_path"].read_text(encoding="utf-8")
    )
    assert projeto_antes["approvals"]["master_16x9_approved"] is True

    # Re-render usando render_existing_episode (nao reexecuta ingest/analise/etc).
    # O brutos e apenas-leitura; torna gravavel.
    brutos_path = (
        env["root"]
        / "projetos"
        / MARCA
        / "episodios"
        / EPISODIO
        / "brutos"
        / "source.mp4"
    )
    if brutos_path.exists():
        brutos_path.chmod(0o644)

    resultado = render_existing_episode(
        env["root"], MARCA, EPISODIO, strict=True
    )

    assert resultado["ok"] is True
    assert resultado["master_path"]
    assert Path(resultado["master_path"]).is_file()
    assert resultado["master_sha256"]
    assert resultado["integrity_delta_hash_zero"] is True

    # Master approval foi resetado pelo re-render.
    projeto_depois = json.loads(
        env["project_path"].read_text(encoding="utf-8")
    )
    assert projeto_depois["approvals"]["master_16x9_approved"] is False
    assert projeto_depois["approvals"]["master_16x9_sha256"] is None

    # O novo master existe.
    novo_master = Path(resultado["master_path"])
    assert novo_master.is_file() and novo_master.stat().st_size > 0


def test_render_existing_episode_sem_edl_erro(rendered_env):
    """Sem edl_longo.json -> PipelineError."""
    env = rendered_env

    # Remove o EDL existente para simular episodio sem EDL.
    edl_path = (
        env["root"]
        / "projetos"
        / MARCA
        / "episodios"
        / EPISODIO
        / "workspace"
        / "briefing"
        / "edl_longo.json"
    )
    if edl_path.exists():
        edl_path.unlink()

    with pytest.raises(PipelineError) as exc:
        render_existing_episode(env["root"], MARCA, EPISODIO)
    assert "edl_longo.json" in str(exc.value)


def test_render_existing_episode_sem_brutos_erro(rendered_env):
    """Sem arquivo de brutos -> PipelineError."""
    env = rendered_env

    # Remove o arquivo de brutos.
    brutos_path = (
        env["root"]
        / "projetos"
        / MARCA
        / "episodios"
        / EPISODIO
        / "brutos"
        / "source.mp4"
    )
    if brutos_path.exists():
        brutos_path.chmod(0o644)
        brutos_path.unlink()

    with pytest.raises(PipelineError) as exc:
        render_existing_episode(env["root"], MARCA, EPISODIO)
    assert "brutos" in str(exc.value).lower() or "nao encontrado" in str(
        exc.value
    ).lower()
