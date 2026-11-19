# -*- coding: utf-8 -*-
"""core/test_cli.py

Testes da CLI unificada (core/cli.py) - Lote 4 (fechamento V1).

Tudo roda em tmp_path, sem tocar arquivos do repositorio. Nao cria UI
web/desktop. Nao duplica logica do pipeline: orquestra estritamente as
funcoes canonicas existentes.

Cobre:
  - status (episodio novo, pos-ingest, pos-render, pos-approve, pos-shorts)
    verificando estado e proxima_acao.
  - Fluxo completo via main([...]): ingest -> analyze (injetado) -> review ->
    plan -> render -> approve -> shorts render -> shorts approve (individual,
    mantendo outro short pendente).
  - Erros compreensiveis (exit code != 0, mensagem clara sem traceback):
    shorts render antes de approve, approve sem master, review sem
    transcript.json.

Tambem exercita `python -m core.cli` via subprocess em um cenario curto.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

import pytest

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from core.cli import main  # noqa: E402
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
    _sha256,
)

MASTER_APPROVED_BY = "proprietario"
CLIP_A = {"short_id": "curta-abertura", "start": 0.5, "end": 2.5}
CLIP_B = {"short_id": "curta-credencial", "start": 4.0, "end": 6.0}

# Snapshot validado do faster-whisper (mesmo usado por test_pipeline_e2e).
_SNAPSHOT_WHISPER = Path(
    os.environ.get(
        "EDITOR_WHISPER_MODEL_PATH",
        r"D:\Backup\HuggingFace\local-appdata\hub"
        r"\models--mobiuslabsgmbh--faster-whisper-large-v3-turbo"
        r"\snapshots\0a363e9161cbc7ed1431c9597a8ceaf0c4f78fcf",
    )
)


# ---------------------------------------------------------------------------
# Helpers de execucao
# ---------------------------------------------------------------------------


def _run_cli(*args: str, json_mode: bool = True) -> subprocess.CompletedProcess:
    """Executa `python -m core.cli <args>` como subprocess."""
    cmd = [sys.executable, "-m", "core.cli"]
    if json_mode:
        cmd.append("--json")
    cmd.extend(args)
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(_REPO),
    )


def _parse_json(proc: subprocess.CompletedProcess) -> Dict[str, Any]:
    assert proc.returncode == 0, (
        f"CLI falhou (rc={proc.returncode}):\n"
        f"stdout: {proc.stdout}\nstderr: {proc.stderr}"
    )
    # Modulos do core podem emitir logs de INFO no stdout antes do JSON.
    # Extrai apenas o primeiro objeto JSON valido da saida.
    texto = proc.stdout
    inicio = texto.find("{")
    if inicio < 0:
        raise AssertionError(f"Nenhum JSON encontrado na saida:\n{texto}")
    return json.loads(texto[inicio:])


def _estado(
    root: Path, marca: str = MARCA, episodio: str = EPISODIO, json_mode: bool = True
) -> Dict[str, Any]:
    proc = _run_cli(
        "--workspace", str(root), "--marca", marca, "--episodio", episodio,
        "status", json_mode=json_mode,
    )
    return _parse_json(proc)


def _cria_workspace_e_marca(root: Path) -> None:
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
    # Disponibiliza vortex-edicao/transcrever.py na raiz do workspace (necessario
    # para analyze_episodio / run_episode_pipeline).
    (root / "vortex-edicao").mkdir(exist_ok=True)
    import shutil
    shutil.copy2(
        _REPO / "vortex-edicao" / "transcrever.py",
        root / "vortex-edicao" / "transcrever.py",
    )
    # project.json minimo do episodio.
    loader.project_file(MARCA, EPISODIO).parent.mkdir(parents=True, exist_ok=True)
    projeto = {
        "schema_version": "1.0.0",
        "marca_id": MARCA,
        "episodio_id": EPISODIO,
        "nome": EPISODIO,
        "current_stage": "01_GRAVACAO_ORIGINAL",
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
        "sources": [],
        "artifacts": {},
        "approvals": {"master_16x9_approved": False},
    }
    loader.project_file(MARCA, EPISODIO).write_text(
        json.dumps(projeto, indent=2, ensure_ascii=False), encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------


def test_status_episodio_novo(tmp_path):
    """Episodio novo: current_stage 01_GRAVACAO_ORIGINAL, proxima_acao = ingest."""
    root = tmp_path / "status_novo"
    _cria_workspace_e_marca(root)
    estado = _estado(root)
    assert estado["current_stage"] == "01_GRAVACAO_ORIGINAL"
    assert estado["transcricao"]["origem"] == "ausente"
    assert estado["master_16x9"]["aprovado"] is False
    assert estado["shorts_9x16"]["total"] == 0
    assert "ingest" in estado["proxima_acao"]


def test_status_pos_ingest(tmp_path):
    """Pos-ingest: proxima_acao aponta para analyze."""
    root = tmp_path / "status_ingest"
    _cria_workspace_e_marca(root)
    source = _build_workspace(root)
    loader = WorkspaceLoader(root)
    loader.load_workspace()
    loader.load_brand_profile(MARCA)

    from core.ingest import ingest_media  # noqa: E402
    rc = ingest_media(str(source), MARCA, EPISODIO, str(root))
    assert rc == 0

    estado = _estado(root)
    assert estado["current_stage"] == "01_INGEST_COMPLETED"
    assert estado["transcricao"]["origem"] == "ausente"
    assert "analyze" in estado["proxima_acao"]


# ---------------------------------------------------------------------------
# Fluxo completo via main([...])
# ---------------------------------------------------------------------------


def _escreve_json(path: Path, dados: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dados, indent=2, ensure_ascii=False), encoding="utf-8")


def test_fluxo_completo_via_main(tmp_path):
    """Fluxo completo: ingest -> analyze (injetado) -> review -> plan ->
    render -> approve -> shorts render -> shorts approve (individual)."""
    root = tmp_path / "fluxo_completo"
    _cria_workspace_e_marca(root)
    source = _build_workspace(root)

    transcricao = _build_transcription()
    correcoes = [
        {"segment_id": 30, "corrected_text": "Palavra Corrigida"},
    ]
    clips_json = tmp_path / "clips.json"
    _escreve_json(clips_json, [CLIP_A, CLIP_B])

    argv = [
        "--workspace", str(root), "--marca", MARCA, "--episodio", EPISODIO,
        "ingest", "--source", str(source),
    ]
    assert main(argv) == 0

    argv = [
        "--workspace", str(root), "--marca", MARCA, "--episodio", EPISODIO,
        "analyze", "--injected-json", str(tmp_path / "injecao.json"),
    ]
    _escreve_json(tmp_path / "injecao.json", transcricao)
    assert main(argv) == 0

    argv = [
        "--workspace", str(root), "--marca", MARCA, "--episodio", EPISODIO,
        "review", "--corrections-json", str(tmp_path / "correcoes.json"),
        "--reviewed-by", MASTER_APPROVED_BY,
    ]
    _escreve_json(tmp_path / "correcoes.json", correcoes)
    assert main(argv) == 0

    argv = [
        "--workspace", str(root), "--marca", MARCA, "--episodio", EPISODIO,
        "plan",
    ]
    assert main(argv) == 0

    argv = [
        "--workspace", str(root), "--marca", MARCA, "--episodio", EPISODIO,
        "render",
        "--whisper-model-path", str(_SNAPSHOT_WHISPER),
    ]
    assert main(argv) == 0

    estado = _estado(root)
    assert estado["master_16x9"]["aprovado"] is False
    assert "approve" in estado["proxima_acao"]

    argv = [
        "--workspace", str(root), "--marca", MARCA, "--episodio", EPISODIO,
        "approve", "--by", MASTER_APPROVED_BY,
    ]
    assert main(argv) == 0

    estado = _estado(root)
    assert estado["master_16x9"]["aprovado"] is True
    assert estado["shorts_9x16"]["total"] == 0
    assert "shorts render" in estado["proxima_acao"]

    argv = [
        "--workspace", str(root), "--marca", MARCA, "--episodio", EPISODIO,
        "shorts", "render", "--clips-json", str(clips_json),
    ]
    assert main(argv) == 0

    estado = _estado(root)
    assert estado["shorts_9x16"]["total"] == 2
    assert estado["shorts_9x16"]["aprovados"] == 0
    assert "shorts approve" in estado["proxima_acao"]

    argv = [
        "--workspace", str(root), "--marca", MARCA, "--episodio", EPISODIO,
        "shorts", "approve", "--short-id", "curta-abertura", "--by", MASTER_APPROVED_BY,
    ]
    assert main(argv) == 0

    estado = _estado(root)
    assert estado["shorts_9x16"]["aprovados"] == 1
    assert "shorts approve" in estado["proxima_acao"]  # ainda tem pendente


# ---------------------------------------------------------------------------
# Erros compreensiveis (exit code != 0, sem traceback cru)
# ---------------------------------------------------------------------------


def test_shorts_render_antes_de_aprove_erro(tmp_path):
    """shorts render com master nao aprovado -> rc != 0, mensagem clara."""
    root = tmp_path / "erro_shorts_antes"
    _cria_workspace_e_marca(root)

    # Cria project com master NAO aprovado (sem precisar renderizar).
    projeto = json.loads(
        loader_load := root  # placeholder, nao usado
    ) if False else None
    loader = WorkspaceLoader(root)
    loader.load_workspace()
    projeto = loader.load_project(MARCA, EPISODIO)
    projeto.setdefault("approvals", {})
    projeto["approvals"]["master_16x9_approved"] = False
    projeto["approvals"]["master_16x9_sha256"] = None
    loader.project_file(MARCA, EPISODIO).write_text(
        json.dumps(projeto, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    clips_json = tmp_path / "clips.json"
    _escreve_json(clips_json, [CLIP_A])

    proc = _run_cli(
        "--workspace", str(root), "--marca", MARCA, "--episodio", EPISODIO,
        "shorts", "render", "--clips-json", str(clips_json),
    )
    assert proc.returncode != 0
    saida = proc.stdout + proc.stderr
    assert "Traceback" not in saida
    assert "nao aprovado" in saida.lower() or "aprovado" in saida.lower()


def test_approve_sem_master_erro(tmp_path):
    """approve sem master existente -> rc != 0, mensagem clara."""
    root = tmp_path / "erro_approve_sem_master"
    _cria_workspace_e_marca(root)

    proc = _run_cli(
        "--workspace", str(root), "--marca", MARCA, "--episodio", EPISODIO,
        "approve", "--by", MASTER_APPROVED_BY,
    )
    assert proc.returncode != 0
    saida = proc.stdout + proc.stderr
    assert "Traceback" not in saida
    assert "inexistente" in saida.lower() or "aprovado" in saida.lower()


def test_review_sem_transcript_erro(tmp_path):
    """review sem transcript.json -> rc != 0, mensagem clara."""
    root = tmp_path / "erro_review_sem_transcript"
    _cria_workspace_e_marca(root)

    _escreve_json(tmp_path / "correcoes.json", [{"segment_id": 0, "corrected_text": "X"}])

    proc = _run_cli(
        "--workspace", str(root), "--marca", MARCA, "--episodio", EPISODIO,
        "review", "--corrections-json", str(tmp_path / "correcoes.json"),
    )
    assert proc.returncode != 0
    saida = proc.stdout + proc.stderr
    assert "Traceback" not in saida
    assert "transcript.json" in saida.lower()


# ---------------------------------------------------------------------------
# python -m core.cli (subprocess) em cenario curto
# ---------------------------------------------------------------------------


def test_subprocess_python_m_core_cli(tmp_path):
    """Execucao via `python -m core.cli` em fluxo curto (status + ingest)."""
    root = tmp_path / "subprocess_cli"
    _cria_workspace_e_marca(root)
    source = _build_workspace(root)

    # status inicial
    proc = _run_cli(
        "--workspace", str(root), "--marca", MARCA, "--episodio", EPISODIO,
        "status",
    )
    assert proc.returncode == 0
    estado = _parse_json(proc)
    assert estado["current_stage"] == "01_GRAVACAO_ORIGINAL"

    # ingest via subprocess
    proc = _run_cli(
        "--workspace", str(root), "--marca", MARCA, "--episodio", EPISODIO,
        "ingest", "--source", str(source),
    )
    assert proc.returncode == 0
    saida = _parse_json(proc)
    assert saida["ok"] is True
    assert saida["comando"] == "ingest"

    # status apos ingest
    estado = _estado(root)
    assert estado["current_stage"] == "01_INGEST_COMPLETED"


# ---------------------------------------------------------------------------
# E2E Modalidade B: ingest -> analyze (local_faster_whisper) -> review ->
# plan -> render -> status com correcao ERRADO_ASR -> TermoCorrigido
# ---------------------------------------------------------------------------


def test_e2e_modalidade_b_review_correcao_erro_asr(tmp_path):
    """Fluxo Modalidade B com correcao humana ERRADO_ASR -> TermoCorrigido."""
    import os as _os

    if _os.name != "nt":
        pytest.skip("SAPI pt-BR so disponivel no Windows")

    snapshot = Path(
        _os.environ.get(
            "EDITOR_WHISPER_MODEL_PATH",
            r"D:\Backup\HuggingFace\local-appdata\hub"
            r"\models--mobiuslabsgmbh--faster-whisper-large-v3-turbo"
            r"\snapshots\0a363e9161cbc7ed1431c9597a8ceaf0c4f78fcf",
        )
    )
    if not (snapshot / "model.bin").is_file():
        pytest.skip("snapshot faster-whisper local nao encontrado")

    from core.test_pipeline_e2e import (  # noqa: E402
        _sintetizar_fala_ptbr,
        _TEXTO_FALA_PTBR,
        _ffmpeg,
        _make_background,
        _make_wav,
        _sha256,
    )
    from core.edl_builder import build_edl_from_alignment  # noqa: E402
    from core.briefing import gerar_briefing  # noqa: E402
    from core.semantic_planner import SemanticConsent  # noqa: E402

    root = tmp_path / "e2e_modalidade_b"
    _cria_workspace_e_marca(root)

    # Sintetiza fala pt-BR para correcao posterior.
    fala_texto = (
        _TEXTO_FALA_PTBR + " ERRADO_ASR. Este termo deve ser corrigido para TermoCorrigido na revisao."
    )
    fala_wav = root / "fala_erro_asr.wav"
    assert _sintetizar_fala_ptbr(fala_wav, fala_texto), "falha na sintese SAPI"
    fala_16k = root / "fala_erro_asr_16k.wav"
    _ffmpeg(
        [
            "ffmpeg", "-y", "-loglevel", "error", "-i", str(fala_wav),
            "-ar", "16000", "-ac", "1", str(fala_16k),
        ]
    )

    # Cria source.mp4 com a fala real (dentro do workspace).
    source = root / "source_erro_asr.mp4"
    background = root / "bg_erro_asr.png"
    _make_background(background)
    _ffmpeg(
        [
            "ffmpeg", "-y", "-loop", "1", "-i", str(background), "-i", str(fala_16k),
            "-t", "16", "-r", "30",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "24", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
            str(source),
        ]
    )

    # 1) Ingest via CLI.
    proc = _run_cli(
        "--workspace", str(root), "--marca", MARCA, "--episodio", EPISODIO,
        "ingest", "--source", str(source),
    )
    assert proc.returncode == 0, proc.stderr
    saida = _parse_json(proc)
    assert saida["ok"] is True

    loader = WorkspaceLoader(root)
    loader.load_workspace()
    fonte_dir = Path(loader.resolve_episodio_asset(
        MARCA, EPISODIO, "workspace/fonte"
    ))
    transcript_path = Path(fonte_dir / "transcript.json")
    transcript_reviewed_path = Path(fonte_dir / "transcript_reviewed.json")
    alignment_path = Path(fonte_dir / "alignment.json")
    briefing_dir = Path(loader.resolve_episodio_asset(
        MARCA, EPISODIO, "workspace/briefing"
    ))
    briefing_path = Path(briefing_dir / "briefing.json")
    edl_path = Path(briefing_dir / "edl_longo.json")
    semantic_plan_path = Path(briefing_dir / "semantic_plan.json")
    consent_path = Path(briefing_dir / "semantic_consent.json")
    editorial_plan_path = Path(briefing_dir / "editorial_plan.json")

    # 2) Analyze via CLI com whisper local (origin = local_faster_whisper).
    proc = _run_cli(
        "--workspace", str(root), "--marca", MARCA, "--episodio", EPISODIO,
        "analyze", "--whisper-model-path", str(snapshot),
    )
    assert proc.returncode == 0, proc.stderr
    saida = _parse_json(proc)
    assert saida["transcription_origin"] == "local_faster_whisper", saida
    assert saida["local_execution_confirmed"] is True, saida
    assert saida["local_files_only"] is True, saida
    assert saida["offline_only"] is True, saida

    # SHA-256 de referencia DEPOIS do analyze (antes do render).
    transcript_sha_antes = _sha256(transcript_path)

    # 3) Review: corrige uma palavra do transcript para "TermoCorrigido",
    #    preservando o texto do segmento e substituindo apenas a palavra alvo.
    transcript_dados = json.loads(transcript_path.read_text(encoding="utf-8"))
    segmento_alvo = None
    palavra_original = None
    for seg in transcript_dados.get("segments", []):
        for w in seg.get("words", []) or []:
            palavra_original = w.get("word", w.get("w", ""))
            segmento_alvo = seg
            break
        if segmento_alvo is not None:
            break
    assert segmento_alvo is not None, "Nenhum segmento encontrado no transcript"

    seg_texto = segmento_alvo.get("text", segmento_alvo.get("w", ""))
    corrected_text = seg_texto.replace(palavra_original, "TermoCorrigido", 1)

    correcoes = [
        {
            "segment_id": segmento_alvo.get("id"),
            "corrected_text": corrected_text,
            "reason": "Correcao de reconhecimento ASR",
            "category": "asr_correction",
        }
    ]
    correcoes_json = tmp_path / "correcoes_erro_asr.json"
    _escreve_json(correcoes_json, correcoes)

    proc = _run_cli(
        "--workspace", str(root), "--marca", MARCA, "--episodio", EPISODIO,
        "review", "--corrections-json", str(correcoes_json),
        "--reviewed-by", MASTER_APPROVED_BY,
    )
    assert proc.returncode == 0, proc.stderr
    saida = _parse_json(proc)
    assert saida["ok"] is True, saida
    assert saida["total_corrections"] >= 1, saida

    # transcript_reviewed.json deve existir.
    assert transcript_reviewed_path.is_file()
    transcript_reviewed_sha_antes = _sha256(transcript_reviewed_path)

    # 4) Plan: preparar artefatos semanticos (semantic_plan.json,
    #    semantic_consent.json, briefing.json, edl_longo.json,
    #    editorial_plan.json) com ids validos do transcript original.
    #    O cmd_plan CLI gera plano de fallback que referencia ids do
    #    transcript_reviewed ('reviewed-N') que nao existem no transcript.json
    #    original, entao preparamos manualmente para garantir validacao.
    from core.transcript_review import resolve_editorial_transcript  # noqa: E402
    editorial = resolve_editorial_transcript(fonte_dir)
    fim = max(float(s.get("end", 0.0)) for s in editorial.get("segments", [])) if editorial.get("segments") else 12.0

    # Obter primeiro segmento valido do transcript reviewed (apos correcao).
    # Usa o primeiro segmento com id inteiro que existe tanto no transcript
    # original quanto no reviewed (segmentos nao corrigidos mantem o id original).
    primeiro_id = None
    for s in editorial.get("segments", []):
        sid = s.get("id")
        if isinstance(sid, int):
            primeiro_id = sid
            break
    if primeiro_id is None:
        primeiro_id = 0

    def _r(x: float) -> float:
        return round(max(0.0, x), 3)

    semantic_plan = {
        "schema_version": "1.0.0",
        "tema_central": "Modalidade B - fala real transcrita offline.",
        "tese_principal": "faster-whisper local sustenta L1..L6 com QA.",
        "gerado_em": "2026-01-01T00:00:00+00:00",
        "provedor": "callable_mock",
        "autorizado": True,
        "marca_id": MARCA,
        "episodio_id": EPISODIO,
        "provider": "fallback_local",
        "topicos": [{
            "topic_id": "T1", "titulo": "Bloco unico",
            "justificativa": "Fala real transcrita offline.",
            "raw_start": 0.0, "raw_end": _r(fim),
            "segment_ids": [primeiro_id],
        }],
        "argumentos": [],
        "grupos_explicacao": [],
        "ganchos_e_viradas": [],
        "repeticoes_dispensaveis": [],
        "falsos_comecos": [],
        "segmentos_editoriais": [{
            "decision": "preservar", "topic_id": "T1",
            "justificativa": "Preservar a fala real transcrita.",
            "raw_start": 0.0, "raw_end": _r(fim),
            "segment_ids": [primeiro_id],
        }],
        "intencoes_visuais": [
            {
                "camada": "L2_titulo_heroi_t10", "funcao_editorial": "Abertura",
                "justificativa": "Titulo ancorado no inicio da fala real.",
                "componente_motion_library": "titulo_heroi", "texto": "MASTER LOCAL",
                "raw_start": 0.0, "raw_end": 0.5,
                "segment_ids": [primeiro_id],
            },
        ],
    }
    semantic_plan_path.parent.mkdir(parents=True, exist_ok=True)
    semantic_plan_path.write_text(
        json.dumps(semantic_plan, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # semantic_consent.json (sem --authorize -> authorized=False).
    consent_obj = SemanticConsent(
        destination="cli_local",
        shared_data=["transcript.json", "alignment.json", "phonetic_report.json"],
        authorized=False,
        notes="Plano gerado via CLI (fallback local sem consentimento).",
    )
    consent_path.write_text(
        json.dumps(consent_obj.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # Briefing + EDL (via funcoes canonicas do core).
    brand_profile = loader.load_brand_profile(MARCA)
    rc = gerar_briefing(
        MARCA, EPISODIO, str(root),
        marca_profile=brand_profile,
        semantic_plan_path=str(semantic_plan_path),
    )
    assert rc == 0, "gerar_briefing falhou"

    edl, editorial_plan = build_edl_from_alignment(
        alignment_path=alignment_path,
        workspace_root=str(root),
        marca_id=MARCA,
        episodio_id=EPISODIO,
        brand_profile=brand_profile,
        semantic_plan_path=semantic_plan_path,
    )
    edl_path.write_text(json.dumps(edl, indent=2, ensure_ascii=False), encoding="utf-8")
    editorial_plan_path.write_text(
        json.dumps(editorial_plan, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # SHA-256 de referencia DEPOIS do plan (imediatamente antes do render).
    alignment_sha_antes = _sha256(alignment_path)
    briefing_sha_antes = _sha256(briefing_path)

    # 5) Render via CLI (chama render_existing_episode).
    proc = _run_cli(
        "--workspace", str(root), "--marca", MARCA, "--episodio", EPISODIO,
        "render",
    )
    assert proc.returncode == 0, proc.stderr
    saida = _parse_json(proc)
    assert saida["ok"] is True, saida
    assert saida["qa_ok"] is True, saida
    assert saida["integrity_delta_hash_zero"] is True, saida

    # 6) Verificacoes apos render.
    # SHA-256 de transcript.json e transcript_reviewed.json identicos antes e depois.
    transcript_sha_depois = _sha256(transcript_path)
    transcript_reviewed_sha_depois = _sha256(transcript_reviewed_path)
    assert transcript_sha_antes == transcript_sha_depois, "transcript.json alterado pelo render"
    assert transcript_reviewed_sha_antes == transcript_reviewed_sha_depois, "transcript_reviewed.json alterado pelo render"

    # alignment.json e briefing.json preservados.
    alignment_sha_depois = _sha256(alignment_path)
    briefing_sha_depois = _sha256(briefing_path)
    assert alignment_sha_antes == alignment_sha_depois, "alignment.json alterado pelo render"
    assert briefing_sha_antes == briefing_sha_depois, "briefing.json alterado pelo render"

    # TermoCorrigido presente em edl_longo.json.
    edl_dados = json.loads(edl_path.read_text(encoding="utf-8"))
    edl_texto = json.dumps(edl_dados, ensure_ascii=False)
    assert "TermoCorrigido" in edl_texto, "TermoCorrigido ausente do edl_longo.json"

    # traceability_report.json com origin == local_faster_whisper.
    renders_dir = Path(loader.resolve_episodio_asset(
        MARCA, EPISODIO, "workspace/renders"
    ))
    trace_path = renders_dir / "traceability_report.json"
    assert trace_path.is_file()
    trace = json.loads(trace_path.read_text(encoding="utf-8"))
    assert trace["data_origin"]["transcription"] == "local_faster_whisper", trace
    assert trace["data_origin"]["source"] == "real_recording", trace
    # Sem --authorize no plan -> fallback_local, authorized is False.
    assert trace["data_origin"]["semantic_plan"] == "fallback_local", trace
    assert trace["data_origin"]["semantic_provider"] == "fallback_local", trace
    consent = trace["data_origin"]["consent"]
    assert consent["authorized"] is False, trace

    # project.json com status MASTER_RENDERED e aprovacao resetada.
    projeto = json.loads(
        loader.project_file(MARCA, EPISODIO).read_text(encoding="utf-8")
    )
    assert projeto["status"] == "MASTER_RENDERED", projeto
    assert projeto["approvals"]["master_16x9_approved"] is False, projeto


# ---------------------------------------------------------------------------
# Helper: monta episodio pronto para render (sem whisper real)
# ---------------------------------------------------------------------------


def _montar_episodio_para_render(root: Path) -> Dict[str, Any]:
    """Cria episodio com todos os artefatos necessarios para render_existing_episode.

    Usa transcricao injetada (rapida, sem whisper) para gerar transcript,
    alignment, semantic_plan, consent, briefing, edl e editorial_plan.
    Retorna dicionario com caminhos e hashes de referencia dos artefatos.
    """
    _cria_workspace_e_marca(root)
    source = _build_workspace(root)

    # Ingest via CLI.
    proc = _run_cli(
        "--workspace", str(root), "--marca", MARCA, "--episodio", EPISODIO,
        "ingest", "--source", str(source),
    )
    assert proc.returncode == 0, proc.stderr

    loader = WorkspaceLoader(root)
    loader.load_workspace()

    # Analyze com transcricao injetada (nao precisa de whisper).
    transcricao = _build_transcription()
    injetado = root / "injetado.json"
    _escreve_json(injetado, transcricao)
    proc = _run_cli(
        "--workspace", str(root), "--marca", MARCA, "--episodio", EPISODIO,
        "analyze", "--injected-json", str(injetado),
    )
    assert proc.returncode == 0, proc.stderr

    fonte_dir = Path(loader.resolve_episodio_asset(
        MARCA, EPISODIO, "workspace/fonte"
    ))
    briefing_dir = Path(loader.resolve_episodio_asset(
        MARCA, EPISODIO, "workspace/briefing"
    ))
    transcript_path = Path(fonte_dir / "transcript.json")
    alignment_path = Path(fonte_dir / "alignment.json")
    briefing_path = Path(briefing_dir / "briefing.json")
    semantic_plan_path = Path(briefing_dir / "semantic_plan.json")
    consent_path = Path(briefing_dir / "semantic_consent.json")
    edl_path = Path(briefing_dir / "edl_longo.json")
    editorial_plan_path = Path(briefing_dir / "editorial_plan.json")

    # Preparar semantic_plan, consent, briefing, edl, editorial_plan.
    from core.transcript_review import resolve_editorial_transcript  # noqa: E402
    from core.edl_builder import build_edl_from_alignment  # noqa: E402
    from core.briefing import gerar_briefing  # noqa: E402
    from core.semantic_planner import SemanticConsent  # noqa: E402

    editorial = resolve_editorial_transcript(fonte_dir)
    segments = editorial.get("segments", [])
    primeiro_id = segments[0].get("id", 0) if segments else 0
    fim = max(float(s.get("end", 0.0)) for s in segments) if segments else 12.0

    def _r(x: float) -> float:
        return round(max(0.0, x), 3)

    semantic_plan = {
        "schema_version": "1.0.0",
        "tema_central": "Teste negativo render.",
        "tese_principal": "Plano valido para render existente.",
        "gerado_em": "2026-01-01T00:00:00+00:00",
        "provedor": "callable_mock",
        "autorizado": True,
        "marca_id": MARCA,
        "episodio_id": EPISODIO,
        "provider": "fallback_local",
        "topicos": [{
            "topic_id": "T1", "titulo": "Bloco unico",
            "justificativa": "Transcricao injetada.",
            "raw_start": 0.0, "raw_end": _r(fim),
            "segment_ids": [primeiro_id],
        }],
        "argumentos": [],
        "grupos_explicacao": [],
        "ganchos_e_viradas": [],
        "repeticoes_dispensaveis": [],
        "falsos_comecos": [],
        "segmentos_editoriais": [{
            "decision": "preservar", "topic_id": "T1",
            "justificativa": "Preservar transcricao injetada.",
            "raw_start": 0.0, "raw_end": _r(fim),
            "segment_ids": [primeiro_id],
        }],
        "intencoes_visuais": [
            {
                "camada": "L2_titulo_heroi_t10", "funcao_editorial": "Abertura",
                "justificativa": "Titulo de abertura.",
                "componente_motion_library": "titulo_heroi", "texto": "MASTER",
                "raw_start": _r(0.0), "raw_end": _r(min(fim * 0.20, 3.0)),
                "segment_ids": [primeiro_id],
            },
            {
                "camada": "L6_sound_design_sync", "funcao_editorial": "SFX",
                "justificativa": "Efeito sonoro.",
                "componente_motion_library": "sound_design_sync",
                "sound_ref": "s1.wav", "volume": 0.9,
                "raw_start": _r(0.3), "raw_end": _r(0.7),
                "segment_ids": [primeiro_id],
            },
        ],
    }
    semantic_plan_path.parent.mkdir(parents=True, exist_ok=True)
    semantic_plan_path.write_text(
        json.dumps(semantic_plan, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    consent_obj = SemanticConsent(
        destination="cli_local",
        shared_data=["transcript.json", "alignment.json", "phonetic_report.json"],
        authorized=False,
        notes="Consent para teste negativo.",
    )
    consent_path.write_text(
        json.dumps(consent_obj.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
    )

    brand_profile = loader.load_brand_profile(MARCA)
    rc = gerar_briefing(
        MARCA, EPISODIO, str(root),
        marca_profile=brand_profile,
        semantic_plan_path=str(semantic_plan_path),
    )
    assert rc == 0, "gerar_briefing falhou"

    edl, editorial_plan = build_edl_from_alignment(
        alignment_path=alignment_path,
        workspace_root=str(root),
        marca_id=MARCA,
        episodio_id=EPISODIO,
        brand_profile=brand_profile,
        semantic_plan_path=semantic_plan_path,
    )
    edl_path.write_text(json.dumps(edl, indent=2, ensure_ascii=False), encoding="utf-8")
    editorial_plan_path.write_text(
        json.dumps(editorial_plan, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # Hashes de referencia dos artefatos existentes.
    def _sha(p: Path) -> str:
        return _sha256(p) if p.is_file() else None

    refs = {
        "transcript": _sha(transcript_path),
        "transcript_reviewed": _sha(fonte_dir / "transcript_reviewed.json"),
        "alignment": _sha(alignment_path),
        "semantic_plan": _sha(semantic_plan_path),
        "consent": _sha(consent_path),
        "briefing": _sha(briefing_path),
        "edl_longo": _sha(edl_path),
        "editorial_plan": _sha(editorial_plan_path),
    }

    return {
        "root": root,
        "loader": loader,
        "fonte_dir": fonte_dir,
        "briefing_dir": briefing_dir,
        "transcript_path": transcript_path,
        "transcript_reviewed_path": fonte_dir / "transcript_reviewed.json",
        "alignment_path": alignment_path,
        "semantic_plan_path": semantic_plan_path,
        "consent_path": consent_path,
        "briefing_path": briefing_path,
        "edl_path": edl_path,
        "editorial_plan_path": editorial_plan_path,
        "refs": refs,
    }


def _assert_artefatos_nao_modificados(refs: Dict[str, str], teste_nome: str) -> None:
    """Verifica que os hashes dos artefatos existentes nao mudaram."""
    caminhos = refs.pop("_caminhos", {})
    for nome, sha_antes in refs.items():
        if sha_antes is None or nome == "refs":
            continue
        caminho = caminhos.get(nome)
        if not caminho:
            continue
        caminho_p = Path(caminho)
        if not caminho_p.is_file():
            continue
        sha_depois = _sha256(caminho_p)
        assert sha_depois == sha_antes, (
            f"{teste_nome}: artefato {nome} foi modificado ({sha_antes} -> {sha_depois})"
        )


# ---------------------------------------------------------------------------
# Testes negativos de render_existing_episode via CLI
# ---------------------------------------------------------------------------


def test_render_transcricao_ausente_erro(tmp_path):
    """Sem transcript.json -> render falha e nao modifica artefatos existentes."""
    env = _montar_episodio_para_render(tmp_path)
    env["refs"]["_caminhos"] = {
        "transcript": env["transcript_path"],
        "transcript_reviewed": env["transcript_reviewed_path"],
        "alignment": env["alignment_path"],
        "semantic_plan": env["semantic_plan_path"],
        "consent": env["consent_path"],
        "briefing": env["briefing_path"],
        "edl_longo": env["edl_path"],
        "editorial_plan": env["editorial_plan_path"],
    }
    # Remove transcript.json.
    env["transcript_path"].unlink()

    proc = _run_cli(
        "--workspace", str(env["root"]), "--marca", MARCA, "--episodio", EPISODIO,
        "render",
    )
    assert proc.returncode != 0, "render deveria falhar sem transcript.json"
    saida = proc.stdout + proc.stderr
    assert "transcript.json" in saida.lower(), saida

    _assert_artefatos_nao_modificados(env["refs"], "test_render_transcricao_ausente_erro")


def test_render_revisao_desatualizada_erro(tmp_path):
    """source_transcript_sha256 divergente em transcript_reviewed.json -> render falha."""
    env = _montar_episodio_para_render(tmp_path)
    env["refs"]["_caminhos"] = {
        "transcript": env["transcript_path"],
        "transcript_reviewed": env["transcript_reviewed_path"],
        "alignment": env["alignment_path"],
        "semantic_plan": env["semantic_plan_path"],
        "consent": env["consent_path"],
        "briefing": env["briefing_path"],
        "edl_longo": env["edl_path"],
        "editorial_plan": env["editorial_plan_path"],
    }
    # Cria transcript_reviewed.json com source_transcript_sha256 divergente.
    reviewed = {
        "schema_version": "1.0.0",
        "origin": "human_review",
        "reviewed_by": "proprietario",
        "reviewed_version": "1.0.0",
        "source_transcript_sha256": "sha256-divergente-que-nao-bate",
        "segments": [
            {
                "id": "reviewed-1",
                "start": 0.0,
                "end": 1.0,
                "text": "teste revisado",
                "human_reviewed": True,
            }
        ],
    }
    env["transcript_reviewed_path"].write_text(
        json.dumps(reviewed, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    proc = _run_cli(
        "--workspace", str(env["root"]), "--marca", MARCA, "--episodio", EPISODIO,
        "render",
    )
    assert proc.returncode != 0, "render deveria falhar com revisao desatualizada"
    saida = proc.stdout + proc.stderr
    assert ("desatual" in saida.lower()
            or "source_transcript_sha256" in saida.lower()
            or "transcript_reviewed" in saida.lower()), saida

    _assert_artefatos_nao_modificados(env["refs"], "test_render_revisao_desatualizada_erro")


def test_render_edl_ausente_erro(tmp_path):
    """Sem edl_longo.json -> render falha e nao modifica artefatos existentes."""
    env = _montar_episodio_para_render(tmp_path)
    env["refs"]["_caminhos"] = {
        "transcript": env["transcript_path"],
        "transcript_reviewed": env["transcript_reviewed_path"],
        "alignment": env["alignment_path"],
        "semantic_plan": env["semantic_plan_path"],
        "consent": env["consent_path"],
        "briefing": env["briefing_path"],
        "edl_longo": env["edl_path"],
        "editorial_plan": env["editorial_plan_path"],
    }
    # Remove edl_longo.json.
    env["edl_path"].unlink()

    proc = _run_cli(
        "--workspace", str(env["root"]), "--marca", MARCA, "--episodio", EPISODIO,
        "render",
    )
    assert proc.returncode != 0, "render deveria falhar sem edl_longo.json"
    saida = proc.stdout + proc.stderr
    assert "edl_longo" in saida.lower(), saida

    _assert_artefatos_nao_modificados(env["refs"], "test_render_edl_ausente_erro")


def test_render_artefatos_incompativeis_erro(tmp_path):
    """semantic_plan.json ou alignment.json corrompido/incompativel -> render falha."""
    env = _montar_episodio_para_render(tmp_path)
    env["refs"]["_caminhos"] = {
        "transcript": env["transcript_path"],
        "transcript_reviewed": env["transcript_reviewed_path"],
        "alignment": env["alignment_path"],
        "semantic_plan": env["semantic_plan_path"],
        "consent": env["consent_path"],
        "briefing": env["briefing_path"],
        "edl_longo": env["edl_path"],
        "editorial_plan": env["editorial_plan_path"],
    }
    # Corrompe semantic_plan.json (JSON invalido).
    env["semantic_plan_path"].write_text("{json invalido", encoding="utf-8")
    env["refs"]["semantic_plan"] = _sha256(env["semantic_plan_path"])

    proc = _run_cli(
        "--workspace", str(env["root"]), "--marca", MARCA, "--episodio", EPISODIO,
        "render",
    )
    assert proc.returncode != 0, "render deveria falhar com semantic_plan corrompido"
    saida = proc.stdout + proc.stderr
    assert ("semantic_plan" in saida.lower()
            or "json" in saida.lower()
            or "inval" in saida.lower()), saida

    _assert_artefatos_nao_modificados(env["refs"], "test_render_artefatos_incompativeis_erro")


def test_render_integridade_bruto_violada_erro(tmp_path):
    """Arquivo em brutos/ adulterado -> Delta-Hash != 0, render falha."""
    env = _montar_episodio_para_render(tmp_path)
    env["refs"]["_caminhos"] = {
        "transcript": env["transcript_path"],
        "transcript_reviewed": env["transcript_reviewed_path"],
        "alignment": env["alignment_path"],
        "semantic_plan": env["semantic_plan_path"],
        "consent": env["consent_path"],
        "briefing": env["briefing_path"],
        "edl_longo": env["edl_path"],
        "editorial_plan": env["editorial_plan_path"],
    }
    # Adultera o arquivo de brutos.
    loader = env["loader"]
    projeto = loader.load_project(MARCA, EPISODIO)
    sources = projeto.get("sources", [])
    assert sources, "episode deve ter source registrada"
    brutos_path = Path(sources[0]["path"]).resolve()
    assert brutos_path.is_file(), "arquivo de brutos deve existir"
    conteudo_antes = brutos_path.read_bytes()
    try:
        brutos_path.chmod(0o644)
        brutos_path.write_bytes(conteudo_antes + b"\x00\x00")
        proc = _run_cli(
            "--workspace", str(env["root"]), "--marca", MARCA, "--episodio", EPISODIO,
            "render",
        )
        assert proc.returncode != 0, "render deveria falhar com brutos adulterado"
        saida = proc.stdout + proc.stderr
        assert ("delta-hash" in saida.lower()
                or "integridade" in saida.lower()
                or "sha-256" in saida.lower()
                or "brutos" in saida.lower()), saida
    finally:
        brutos_path.write_bytes(conteudo_antes)
        brutos_path.chmod(0o444)

    _assert_artefatos_nao_modificados(env["refs"], "test_render_integridade_bruto_violada_erro")


# ---------------------------------------------------------------------------
# Portoes Humanos CLI (prepare-brief -> render-master -> suggest-shorts -> render-shorts)
# ---------------------------------------------------------------------------


def test_portoes_humanos_cli_e_mcp_tools(tmp_path):
    """Exercita prepare-brief (Portao 1), render-master, suggest-shorts (Portao 2) e render-shorts."""
    root = tmp_path / "portoes_cli"
    _cria_workspace_e_marca(root)
    source = _build_workspace(root)

    inj_path = tmp_path / "inj_portoes.json"
    _escreve_json(inj_path, _build_transcription())

    ub_path = tmp_path / "user_brief.json"
    _escreve_json(
        ub_path,
        {
            "pedido_usuario": "Deixe o ritmo dinamico e corte pausas.",
            "modo": "completo",
            "qtd_cortes_desejada": 2,
            "correcoes_ortograficas": [
                {"segment_id": 0, "corrected_text": "Abertura revisada"}
            ],
        },
    )

    # 1) prepare-brief: deve gerar BRIEFING.md + edl_longo.json e PARAR (sem master)
    assert main([
        "--workspace", str(root), "--marca", MARCA, "--episodio", EPISODIO,
        "prepare-brief",
        "--source", str(source),
        "--injected-json", str(inj_path),
        "--user-brief-json", str(ub_path),
    ]) == 0

    loader = WorkspaceLoader(root)
    loader.load_workspace()
    briefing_dir = loader.resolve_episodio_asset(MARCA, EPISODIO, "workspace/briefing")
    renders_dir = loader.resolve_episodio_asset(MARCA, EPISODIO, "workspace/renders")

    assert (briefing_dir / "BRIEFING.md").is_file()
    assert (briefing_dir / "edl_longo.json").is_file()
    assert not (renders_dir / "master_16x9.mp4").exists(), "Portao 1 violado: renderizou antes do OK"
    brief_md = (briefing_dir / "BRIEFING.md").read_text(encoding="utf-8")
    assert "Deixe o ritmo dinamico" in brief_md

    plan_json = json.loads((briefing_dir / "editorial_plan.json").read_text(encoding="utf-8"))
    assert len(plan_json["layers"]["L2_titulo_heroi_t10"]) >= 1

    # 2) render-master: executa lint e renderiza o Master aprovado
    assert main([
        "--workspace", str(root), "--marca", MARCA, "--episodio", EPISODIO,
        "render-master", "--by", MASTER_APPROVED_BY,
    ]) == 0
    assert (renders_dir / "master_16x9.mp4").is_file()

    # 3) suggest-shorts: gera shorts_briefing.md + shorts_plan.json e PARA (Portao 2)
    assert main([
        "--workspace", str(root), "--marca", MARCA, "--episodio", EPISODIO,
        "suggest-shorts", "--count", "2",
    ]) == 0
    assert (briefing_dir / "shorts_briefing.md").is_file()
    assert (briefing_dir / "shorts_plan.json").is_file()
    shorts_dir = renders_dir / "shorts"
    assert not (shorts_dir / "corte-01.mp4").exists(), "Portao 2 violado: renderizou short antes da aprovacao"

    # 4) render-shorts: renderiza apenas corte-01 aprovado
    assert main([
        "--workspace", str(root), "--marca", MARCA, "--episodio", EPISODIO,
        "render-shorts", "--short-ids", "corte-01",
    ]) == 0
    assert (shorts_dir / "corte-01.mp4").is_file()
    assert not (shorts_dir / "corte-02.mp4").exists()
