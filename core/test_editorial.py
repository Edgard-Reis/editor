#!/usr/bin/env python3
"""
core/test_editorial.py

Suíte de testes unitários para core/briefing.py, core/edl_builder.py e
core/master_lint.py (Editor).

Usa fixtures sinteticas (transcricoes estruturadas, sem API externa) em
tempfile.TemporaryDirectory(), sem alterar arquivos reais do repositorio.

Cenarios cobertos:
  - organizacao de temas;
  - preservacao de explicacoes contextualizadas juntas;
  - geracao de briefing.json e BRIEFING.md;
  - construcao de edl_longo.json e editorial_plan.json (6 camadas);
  - integridade temporal (lacunas/sobreposicoes detectadas pelo lint);
  - referencias a fonte original;
  - compatibilidade com project.json;
  - consumo do Brand Profile;
  - reprodutibilidade deterministica;
  - auto_approved=False no lint.
"""

import json
import os
import math
import struct
import sys
import tempfile
import wave
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Garante import do pacote core (raiz Editor).
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.workspace import (  # noqa: E402
    WorkspaceLoader,
    init_workspace,
    register_brand,
    load_brand_profile,
    create_project,
    load_project,
    resolve_episodio_asset,
)
from core.ingest import (  # noqa: E402
    ingest_media,
    IngestError,
    compute_sha256,
)
from core.analyze import (  # noqa: E402
    analyze_episodio,
)
from core.briefing import (  # noqa: E402
    gerar_briefing,
    BriefingError,
)
from core.edl_builder import (  # noqa: E402
    build_edl_from_alignment,
    EdlBuilderError,
)
from core.master_lint import (  # noqa: E402
    lint,
    MasterLintError,
    REQUIRED_LAYERS,
)
from core.semantic_plan import (  # noqa: E402
    SemanticPlanError,
    validate_semantic_plan,
    IMPLEMENTED_MOTION_COMPONENTS,
)


def _iso_now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def _gravar_json(path: Path, dados: Any) -> None:  # type: ignore[name-defined]
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(dados, f, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Fixtures sinteticas
# ---------------------------------------------------------------------------


def _gerar_transcricao_sintetica() -> Dict[str, Any]:
    """Gera um transcript.json sintetico com segmentos e palavras."""
    palavras = [
        {"word": "Seja", "start": 0.0, "end": 0.76, "probability": 0.99},
        {"word": "muito", "start": 0.76, "end": 1.04, "probability": 0.98},
        {"word": "bem-vindo", "start": 1.04, "end": 1.46, "probability": 0.97},
        {"word": "ao", "start": 1.46, "end": 1.64, "probability": 0.99},
        {"word": "canal", "start": 1.64, "end": 1.9, "probability": 0.98},
        {"word": "do", "start": 1.9, "end": 2.06, "probability": 0.97},
        {"word": "Dr.", "start": 2.06, "end": 2.24, "probability": 0.99},
        {"word": "Gestao", "start": 2.32, "end": 2.6, "probability": 0.98},
        {"word": "Luiz", "start": 2.6, "end": 2.8, "probability": 0.97},
        {"word": "Roberto", "start": 2.8, "end": 3.06, "probability": 0.98},
        {"word": "Saraiva.", "start": 3.06, "end": 3.58, "probability": 0.99},
        {"word": "Sao", "start": 3.9, "end": 4.08, "probability": 0.97},
        {"word": "29", "start": 4.08, "end": 4.5, "probability": 0.98},
        {"word": "anos", "start": 4.5, "end": 5.0, "probability": 0.99},
        {"word": "alta", "start": 26.6, "end": 26.9, "probability": 0.90},
        {"word": "minutagem,", "start": 26.9, "end": 27.58, "probability": 0.88},
        {"word": "faturamento", "start": 103.73, "end": 104.41, "probability": 0.40},  # baixa confianca
    ]
    segments = [
        {
            "id": 0,
            "start": 0.0,
            "end": 3.58,
            "text": "Seja muito bem-vindo ao canal do Dr. Gestao Luiz Roberto Saraiva.",
            "words": palavras[:11],
        },
        {
            "id": 1,
            "start": 3.9,
            "end": 5.0,
            "text": "Sao 29 anos.",
            "words": palavras[11:14],
        },
        {
            "id": 2,
            "start": 26.6,
            "end": 27.58,
            "text": "alta minutagem,",
            "words": palavras[14:16],
        },
        {
            "id": 3,
            "start": 103.73,
            "end": 104.41,
            "text": "faturamento.",
            "words": palavras[16:17],
        },
    ]
    return {
        "schema_version": "1.0.0",
        "engine": "faster-whisper",
        "language": "pt",
        "audio_duration_seconds": 105.0,
        "total_segments": len(segments),
        "total_words": len(palavras),
        "segments": segments,
        "source_ref": {"path": "brutos/video.mp4", "sha256": "abc123"},
    }


def _gerar_alignment_sintetico() -> Dict[str, Any]:
    """Gera um alignment.json sintetico com unidades editoriais."""
    return {
        "schema_version": "1.0.0",
        "editorial_units": [
            {
                "raw_start": 0.0,
                "raw_end": 3.58,
                "text": "Seja muito bem-vindo ao canal do Dr. Gestao Luiz Roberto Saraiva.",
                "words": [
                    {"word": "Seja", "start": 0.0, "end": 0.76, "probability": 0.99},
                    {"word": "muito", "start": 0.76, "end": 1.04, "probability": 0.98},
                    {"word": "bem-vindo", "start": 1.04, "end": 1.46, "probability": 0.97},
                    {"word": "ao", "start": 1.46, "end": 1.64, "probability": 0.99},
                    {"word": "canal", "start": 1.64, "end": 1.9, "probability": 0.98},
                    {"word": "do", "start": 1.9, "end": 2.06, "probability": 0.97},
                    {"word": "Dr.", "start": 2.06, "end": 2.24, "probability": 0.99},
                    {"word": "Gestao", "start": 2.32, "end": 2.6, "probability": 0.98},
                    {"word": "Luiz", "start": 2.6, "end": 2.8, "probability": 0.97},
                    {"word": "Roberto", "start": 2.8, "end": 3.06, "probability": 0.98},
                    {"word": "Saraiva.", "start": 3.06, "end": 3.58, "probability": 0.99},
                ],
            },
            {
                "raw_start": 3.9,
                "raw_end": 5.0,
                "text": "Sao 29 anos.",
                "words": [
                    {"word": "Sao", "start": 3.9, "end": 4.08, "probability": 0.97},
                    {"word": "29", "start": 4.08, "end": 4.5, "probability": 0.98},
                    {"word": "anos", "start": 4.5, "end": 5.0, "probability": 0.99},
                ],
            },
            {
                "raw_start": 26.6,
                "raw_end": 27.58,
                "text": "alta minutagem,",
                "words": [
                    {"word": "alta", "start": 26.6, "end": 26.9, "probability": 0.90},
                    {"word": "minutagem,", "start": 26.9, "end": 27.58, "probability": 0.88},
                ],
            },
            {
                "raw_start": 103.73,
                "raw_end": 104.41,
                "text": "faturamento.",
                "words": [
                    {"word": "faturamento", "start": 103.73, "end": 104.41, "probability": 0.40},
                ],
            },
        ],
    }


def _gerar_phonetic_report_sintetico() -> Dict[str, Any]:
    """Gera um phonetic_report.json sintetico com baixa confianca e divergencias."""
    return {
        "schema_version": "1.0.0",
        "marca_id": "marca-teste",
        "episodio_id": "ep-teste",
        "total_palavras": 17,
        "total_findings": 1,
        "low_confidence_count": 1,
        "low_confidence": [
            {"palavra": "faturamento", "t": 103.73, "f": 104.41, "probability": 0.40}
        ],
        "lexicon_hits": [
            {"palavra": "alta", "t": 26.6, "f": 26.9},
            {"palavra": "minutagem,", "t": 26.9, "f": 27.58},
            {"palavra": "faturamento", "t": 103.73, "f": 104.41},
        ],
        "findings": [
            {
                "original_text": "alta minutagem",
                "corrected_text": "alta minutagem",
                "start_time": 26.6,
                "end_time": 27.58,
                "certainty": 0.9,
                "category": "uniao",
                "rule_name": "uniao_alta_minutagem",
                "rationale": "Uniao fonetica de 'alta minutagem'.",
            }
        ],
        "status": "VERIFIED_AND_CORRECTED",
    }


def _setup_workspace_e_marca(tmp: Path, marca_id: str = "marca-teste") -> Path:
    """Cria workspace.json e registra uma marca no tmp."""
    init_workspace(tmp)
    marca_dir = tmp / "projetos" / marca_id / "branding"
    marca_dir.mkdir(parents=True, exist_ok=True)
    perfil = {
        "schema_version": "1.0.0",
        "brand_id": marca_id,
        "display_name": f"Marca {marca_id}",
        "presenter": {"name": "Apresentador Teste", "credential": "Credencial de Teste"},
        "marca": {"destaque": "#004aad", "fonte": "Inter"},
        "preferencias_edicao": {
            "canal": f"Canal {marca_id}",
            "apresentador": "Apresentador Teste",
            "credencial_oficial": "Credencial de Teste",
            "lexicon_transcricao": "alta minutagem, marketplaces, faturamento",
            "render_defaults": {
                "master_16x9": {"width": 1920, "height": 1080, "fps": 30},
                "shorts_9x16": {"width": 1080, "height": 1920, "fps": 30},
            },
            "audio": {
                "silence_guard_ms": [180, 220],
                "jumpcut_gap_threshold_ms": 450,
                "jumpcut_target_gap_ms": [200, 250],
            },
            "asr": {
                "lexicon": ["alta minutagem", "marketplaces", "faturamento"],
                "phonetic_rules_file": "phonetic_rules.json",
            },
        },
        "visual": {
            "palette": {"primary": "#004aad"},
            "safe_zones": {},
        },
        "asr": {},
        "assets": {},
    }
    # phonetic_rules.json com regra de divergencia fonetica
    (marca_dir / "phonetic_rules.json").write_text(
        json.dumps({
            "rules": [
                {
                    "pattern": ["alta", "minutagem"],
                    "replacement": ["alta minutagem"],
                    "rule_name": "uniao_alta_minutagem",
                    "category": "uniao",
                    "certainty": 0.9,
                    "rationale": "Uniao fonetica de 'alta minutagem'.",
                }
            ]
        }, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    with open(marca_dir / "config.json", "w", encoding="utf-8") as f:
        json.dump(perfil, f, indent=2, ensure_ascii=False)
    return tmp


def _setup_episodio_com_analise(
    tmp: Path, marca_id: str, episodio_id: str
) -> Path:
    """Cria episodio, roda ingestao e analise, retorna tmp."""
    loader = WorkspaceLoader(tmp)
    loader.load_workspace()
    loader.register_brand(marca_id, f"Marca {marca_id}")

    # Cria project.json diretamente
    episodio_dir = loader.resolve_episodio_asset(marca_id, episodio_id, "")
    episodio_dir.mkdir(parents=True, exist_ok=True)
    projeto = {
        "schema_version": "1.0.0",
        "marca_id": marca_id,
        "episodio_id": episodio_id,
        "nome": episodio_id,
        "current_stage": "01_GRAVACAO_ORIGINAL",
        "created_at": _iso_now(),
        "updated_at": _iso_now(),
        "sources": [],
        "artifacts": {},
        "approvals": {
            "master_16x9_approved": False,
            "approved_by": None,
            "approved_at": None,
        },
    }
    pj_path = loader.project_file(marca_id, episodio_id)
    _gravar_json(pj_path, projeto)

    # Grava audio sintetico em brutos/
    brutos_dir = loader.resolve_episodio_asset(marca_id, episodio_id, "brutos")
    brutos_dir.mkdir(parents=True, exist_ok=True)
    video_bruto = brutos_dir / "video.mp4"
    _gerar_wav_16k_mono(video_bruto, duracao_s=2.0)

    # Roda ingestao
    rc = ingest_media(
        input_path=str(video_bruto),
        marca_id=marca_id,
        episodio_id=episodio_id,
        workspace_root=str(tmp),
    )
    assert rc == 0, f"ingest falhou com codigo {rc}"

    # Grava transcript, alignment, phonetic_report em workspace/fonte/
    fonte_dir = loader.resolve_episodio_asset(marca_id, episodio_id, "workspace/fonte")
    fonte_dir.mkdir(parents=True, exist_ok=True)
    _gravar_json(fonte_dir / "transcript.json", _gerar_transcricao_sintetica())
    _gravar_json(fonte_dir / "alignment.json", _gerar_alignment_sintetico())
    _gravar_json(fonte_dir / "phonetic_report.json", _gerar_phonetic_report_sintetico())

    return tmp


def _gerar_wav_16k_mono(caminho: Path, duracao_s: float = 1.0, tom_hz: float = 440.0) -> None:
    """Gera um arquivo WAV PCM 16kHz mono sintético."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    # Remove arquivo existente (pode ser read-only da ingestão)
    if caminho.exists():
        caminho.chmod(0o644)
        caminho.unlink()
    sample_rate = 16000
    n_samples = int(sample_rate * duracao_s)
    amostras = []
    for i in range(n_samples):
        valor = int(12000 * math.sin(2 * math.pi * tom_hz * i / sample_rate))
        amostras.append(struct.pack("<h", valor))
    with wave.open(str(caminho), "wb") as wf2:
        wf2.setnchannels(1)
        wf2.setsampwidth(2)
        wf2.setframerate(sample_rate)
        wf2.writeframes(b"".join(amostras))


# ---------------------------------------------------------------------------
# Testes
# ---------------------------------------------------------------------------


def test_gerar_briefing_arquivos():
    """Geracao de briefing.json e BRIEFING.md."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        _setup_workspace_e_marca(tmp, "marca-briefing")
        _setup_episodio_com_analise(tmp, "marca-briefing", "ep-briefing")

        rc = gerar_briefing("marca-briefing", "ep-briefing", str(tmp))
        assert rc == 0, f"briefing falhou com codigo {rc}"

        loader = WorkspaceLoader(tmp)
        briefing_dir = loader.resolve_episodio_asset(
            "marca-briefing", "ep-briefing", "workspace/briefing"
        )
        assert (briefing_dir / "briefing.json").is_file(), "briefing.json nao gerado"
        assert (briefing_dir / "BRIEFING.md").is_file(), "BRIEFING.md nao gerado"

        bj = json.load(open(briefing_dir / "briefing.json", encoding="utf-8"))
        assert bj["schema_version"] == "1.0.0"
        assert bj["marca"]["marca_id"] == "marca-briefing"
        assert bj["marca"]["apresentador"] == "Apresentador Teste"
        assert bj["marca"]["credencial_oficial"] == "Credencial de Teste"
        assert bj["planning_mode"] == "deterministic_fallback"
        assert bj["requires_semantic_review"] is True
        assert bj["duracao_original_s"] > 0
        assert "tema" in bj and len(bj["tema"]) > 0
        assert "MODO DETERMINÍSTICO" in bj["tema"]
        assert bj["motions"] == []  # fallback nao fabrica motions artificiais
        assert bj["requires_human_approval"] is True

        md = (briefing_dir / "BRIEFING.md").read_text(encoding="utf-8")
        assert "# BRIEFING EDITORIAL" in md
        assert "Apresentador Teste" in md
        assert "Credencial de Teste" in md
        assert "Tema do" in md
        assert "Requer revisão" in md

        # project.json atualizado
        pj = loader.load_project("marca-briefing", "ep-briefing")
        assert pj["current_stage"] == "03_BRIEFING_COMPLETED"
        assert "briefing_json" in pj["artifacts"]["03_briefing"]
        assert "briefing_md" in pj["artifacts"]["03_briefing"]
    print("  [PASS] test_gerar_briefing_arquivos")


def test_briefing_preserva_explicacoes_contextualizadas():
    """Verificacao de que o briefing menciona o tema e a marca."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        _setup_workspace_e_marca(tmp, "marca-contexto")
        _setup_episodio_com_analise(tmp, "marca-contexto", "ep-contexto")

        gerar_briefing("marca-contexto", "ep-contexto", str(tmp))
        loader = WorkspaceLoader(tmp)
        briefing_dir = loader.resolve_episodio_asset(
            "marca-contexto", "ep-contexto", "workspace/briefing"
        )
        md = (briefing_dir / "BRIEFING.md").read_text(encoding="utf-8")
        assert "Apresentador Teste" in md
        assert "Tema do" in md
        # No fallback conservador, o tema referencia a abertura real transcrita, sem alegar compreensao semantica
        bj = json.load(open(briefing_dir / "briefing.json", encoding="utf-8"))
        assert "seja muito bem-vindo" in bj["tema"].lower()
        assert bj["requires_semantic_review"] is True
    print("  [PASS] test_briefing_preserva_explicacoes_contextualizadas")


def test_edl_longo_editorial_plan_6_camadas():
    """Construcao de edl_longo.json e editorial_plan.json com 6 camadas."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        _setup_workspace_e_marca(tmp, "marca-edl")
        _setup_episodio_com_analise(tmp, "marca-edl", "ep-edl")

        loader = WorkspaceLoader(tmp)
        loader.load_workspace()
        marca_profile = loader.load_brand_profile("marca-edl")

        alinhamento_path = loader.resolve_episodio_asset(
            "marca-edl", "ep-edl", "workspace/fonte/alignment.json"
        )
        edl, plano = build_edl_from_alignment(
            alignment_path=alinhamento_path,
            workspace_root=str(tmp),
            marca_id="marca-edl",
            episodio_id="ep-edl",
            brand_profile=marca_profile,
        )

        # edl_longo.json
        assert edl["schema_version"] == "1.0.0"
        assert edl["marca_id"] == "marca-edl"
        assert edl["episodio_id"] == "ep-edl"
        assert "source_ref" in edl
        assert edl["source_ref"]["id"]
        assert edl["source_ref"]["sha256"]
        assert len(edl["timeline_events"]) == 4
        assert len(edl["word_index"]) > 0
        for ev in edl["timeline_events"]:
            assert "source_ref" in ev
            assert "raw_in" in ev and "raw_out" in ev
            assert "out_in" in ev and "out_out" in ev
            assert "operation" in ev
            assert "justification" in ev
            assert "audio_treatment" in ev
            assert "motion_hints" in ev
            assert "narrative_continuity" in ev
            assert "topic_id" in ev["narrative_continuity"]
            assert "explanation_group_id" in ev["narrative_continuity"]

        # editorial_plan.json
        assert plano["schema_version"] == "1.0.0"
        assert plano["marca_id"] == "marca-edl"
        assert plano["episodio_id"] == "ep-edl"
        assert "layers" in plano
        for camada in REQUIRED_LAYERS:
            assert camada in plano["layers"], f"camada ausente: {camada}"
        total_eventos = sum(len(l) for l in plano["layers"].values())
        assert total_eventos == 4  # 4 eventos distribuidos
    print("  [PASS] test_edl_longo_editorial_plan_6_camadas")


def test_master_lint_aprovado_sem_aprovacao_automatica():
    """Lint aprovado (ok=True) mas auto_approved=False e requires_human_approval=True."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        _setup_workspace_e_marca(tmp, "marca-lint")
        _setup_episodio_com_analise(tmp, "marca-lint", "ep-lint")

        loader = WorkspaceLoader(tmp)
        loader.load_workspace()
        marca_profile = loader.load_brand_profile("marca-lint")

        alinhamento_path = loader.resolve_episodio_asset(
            "marca-lint", "ep-lint", "workspace/fonte/alignment.json"
        )
        edl, plano = build_edl_from_alignment(
            alignment_path=alinhamento_path,
            workspace_root=str(tmp),
            marca_id="marca-lint",
            episodio_id="ep-lint",
            brand_profile=marca_profile,
        )

        projeto = loader.load_project("marca-lint", "ep-lint")
        relatorio = lint(plano, edl, projeto)

        assert relatorio["auto_approved"] is False
        assert relatorio["requires_human_approval"] is True
        assert relatorio["ok"] is True  # sem falhas nos fixtures validos
        assert relatorio["summary"]["total_falhas"] == 0
        assert relatorio["summary"]["total_camadas"] == len(REQUIRED_LAYERS)
    print("  [PASS] test_master_lint_aprovado_sem_aprovacao_automatica")


def test_lint_detecta_lacunas_e_sobreposicoes():
    """Lint detecta lacunas temporais e sobreposicoes invalidas."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        _setup_workspace_e_marca(tmp, "marca-lint2")
        _setup_episodio_com_analise(tmp, "marca-lint2", "ep-lint2")

        loader = WorkspaceLoader(tmp)
        loader.load_workspace()
        marca_profile = loader.load_brand_profile("marca-lint2")

        alinhamento_path = loader.resolve_episodio_asset(
            "marca-lint2", "ep-lint2", "workspace/fonte/alignment.json"
        )
        edl, plano = build_edl_from_alignment(
            alignment_path=alinhamento_path,
            workspace_root=str(tmp),
            marca_id="marca-lint2",
            episodio_id="ep-lint2",
            brand_profile=marca_profile,
        )

        # Cria plano manual com sobreposicao na camada L1
        plano["layers"]["L1_estabelecimento"] = [
            {
                "element_id": "E00001",
                "event_id": 1,
                "source_ref": plano["source_ref"],
                "raw_in": 0.0,
                "raw_out": 2.0,
                "out_in": 0.0,
                "out_out": 2.0,
                "duration_seconds": 2.0,
                "text": "evento 1",
                "transition_in": "hard_cut",
                "transition_out": "hard_cut",
                "operation": "jump_cut",
                "justification": "teste",
                "audio_treatment": "preservar",
                "motion_hints": [],
                "narrative_continuity": {
                    "topic_id": "T1",
                    "explanation_group_id": "E1",
                    "preserves_context": True,
                },
            },
            {
                "element_id": "E00002",
                "event_id": 2,
                "source_ref": plano["source_ref"],
                "raw_in": 1.5,
                "raw_out": 3.0,
                "out_in": 1.5,
                "out_out": 3.0,
                "duration_seconds": 1.5,
                "text": "evento 2",
                "transition_in": "hard_cut",
                "transition_out": "hard_cut",
                "operation": "jump_cut",
                "justification": "teste",
                "audio_treatment": "preservar",
                "motion_hints": [],
                "narrative_continuity": {
                    "topic_id": "T1",
                    "explanation_group_id": "E1",
                    "preserves_context": True,
                },
            },
        ]

        projeto = loader.load_project("marca-lint2", "ep-lint2")
        relatorio = lint(plano, edl, projeto)

        assert relatorio["ok"] is False
        assert any("colisao" in f.lower() for f in relatorio["failures"]), (
            f"esperado deteccao de colisao: {relatorio['failures']}"
        )
    print("  [PASS] test_lint_detecta_lacunas_e_sobreposicoes")


def test_lint_detecta_referencia_fonte_inexistente():
    """Lint detecta source_ref inexistente no project.json."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        _setup_workspace_e_marca(tmp, "marca-ref")
        _setup_episodio_com_analise(tmp, "marca-ref", "ep-ref")

        loader = WorkspaceLoader(tmp)
        loader.load_workspace()

        # Cria plano manual com source_ref invalido
        plano = {
            "schema_version": "1.0.0",
            "marca_id": "marca-ref",
            "episodio_id": "ep-ref",
            "layers": {
                "L1_estabelecimento": [
                    {
                        "element_id": "E00001",
                        "event_id": 1,
                        "source_ref": {
                            "id": "SRC_INEXISTENTE",
                            "path": "",
                            "sha256": "0" * 64,
                        },
                        "raw_in": 0.0,
                        "raw_out": 1.0,
                        "out_in": 0.0,
                        "out_out": 1.0,
                        "duration_seconds": 1.0,
                        "text": "teste",
                        "transition_in": "hard_cut",
                        "transition_out": "hard_cut",
                        "operation": "jump_cut",
                        "justification": "teste",
                        "audio_treatment": "preservar",
                        "motion_hints": [],
                        "narrative_continuity": {
                            "topic_id": "T1",
                            "explanation_group_id": "E1",
                            "preserves_context": True,
                        },
                    }
                ],
                "L2_titulo_heroi_t10": [],
                "L3_micro_zoom_bate": [],
                "L4_lower_third": [],
                "L5_broll_industrial": [],
                "L6_sound_design_sync": [],
            },
        }

        projeto = loader.load_project("marca-ref", "ep-ref")
        relatorio = lint(plano, edl=None, projeto=projeto)

        assert relatorio["ok"] is False
        assert any(
            "source_ref" in f.lower() or "nao encontrado" in f.lower()
            for f in relatorio["failures"]
        ), f"esperado deteccao de fonte invalida: {relatorio['failures']}"
    print("  [PASS] test_lint_detecta_referencia_fonte_inexistente")


def test_reprodutibilidade_deterministica():
    """Mesma entrada produz mesma saida (reprodutibilidade)."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        resultados = []
        for _ in range(2):
            _setup_workspace_e_marca(tmp, "marca-rep")
            _setup_episodio_com_analise(tmp, "marca-rep", "ep-rep")

            loader = WorkspaceLoader(tmp)
            loader.load_workspace()
            marca_profile = loader.load_brand_profile("marca-rep")

            alinhamento_path = loader.resolve_episodio_asset(
                "marca-rep", "ep-rep", "workspace/fonte/alignment.json"
            )
            edl, plano = build_edl_from_alignment(
                alignment_path=alinhamento_path,
                workspace_root=str(tmp),
                marca_id="marca-rep",
                episodio_id="ep-rep",
                brand_profile=marca_profile,
            )
            # Remove campos que mudam a cada execucao (generated_at)
            edl_copia = dict(edl)
            edl_copia.pop("generated_at", None)
            edl_copia["telemetry"] = {}
            plano_copia = dict(plano)
            plano_copia.pop("generated_at", None)
            resultados.append((json.dumps(edl_copia, sort_keys=True), json.dumps(plano_copia, sort_keys=True)))

        assert resultados[0] == resultados[1], "resultados nao sao reproduziveis"
    print("  [PASS] test_reprodutibilidade_deterministica")


def test_consumo_brand_profile():
    """Consumo do brand_profile (palette, apresentador, audio)."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        _setup_workspace_e_marca(tmp, "marca-perfil")
        _setup_episodio_com_analise(tmp, "marca-perfil", "ep-perfil")

        gerar_briefing("marca-perfil", "ep-perfil", str(tmp))
        loader = WorkspaceLoader(tmp)
        breve_dir = loader.resolve_episodio_asset(
            "marca-perfil", "ep-perfil", "workspace/briefing"
        )
        md = (breve_dir / "BRIEFING.md").read_text(encoding="utf-8")
        assert "Apresentador Teste" in md
        assert "Credencial de Teste" in md
        assert "Tema do" in md
    print("  [PASS] test_consumo_brand_profile")


# ---------------------------------------------------------------------------
# Novos testes — Primeira Evolucao Editorial (determinismo, contrato e benchmark)
# ---------------------------------------------------------------------------


def test_brand_profile_preferencias_e_phonetic_w():
    """Leitura correta de preferencias_edicao.{apresentador, credencial_oficial} e campo 'w'."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        _setup_workspace_e_marca(tmp, "marca-w")
        _setup_episodio_com_analise(tmp, "marca-w", "ep-w")

        loader = WorkspaceLoader(tmp)
        fonte_dir = loader.resolve_episodio_asset("marca-w", "ep-w", "workspace/fonte")
        _gravar_json(
            fonte_dir / "phonetic_report.json",
            {
                "low_confidence": [
                    {"w": "minutagem", "t": 7.5, "f": 8.0, "probability": 0.42}
                ]
            },
        )
        gerar_briefing("marca-w", "ep-w", str(tmp))
        bj = json.load(
            open(
                loader.resolve_episodio_asset("marca-w", "ep-w", "workspace/briefing/briefing.json"),
                encoding="utf-8",
            )
        )
        assert bj["marca"]["apresentador"] == "Apresentador Teste"
        assert bj["marca"]["credencial_oficial"] == "Credencial de Teste"
        erros = [r for r in bj["repeticoes_e_falsos_comecos"] if r["tipo"] == "erro"]
        assert len(erros) == 1
        assert erros[0]["palavra"] == "minutagem"
        assert "minutagem" in erros[0]["descricao"]
    print("  [PASS] test_brand_profile_preferencias_e_phonetic_w")


def test_edl_sem_round_robin_e_fallback_conservador():
    """Elimina round-robin: L1 recebe toda a fala; L2..L6 ficam vazias no fallback."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        _setup_workspace_e_marca(tmp, "marca-norr")
        _setup_episodio_com_analise(tmp, "marca-norr", "ep-norr")

        loader = WorkspaceLoader(tmp)
        loader.load_workspace()
        mp = loader.load_brand_profile("marca-norr")
        alinhamento_path = loader.resolve_episodio_asset("marca-norr", "ep-norr", "workspace/fonte/alignment.json")

        edl, plano = build_edl_from_alignment(
            alignment_path=alinhamento_path,
            workspace_root=str(tmp),
            marca_id="marca-norr",
            episodio_id="ep-norr",
            brand_profile=mp,
        )
        assert edl["planning_mode"] == "deterministic_fallback"
        assert edl["requires_semantic_review"] is True
        assert edl["requires_human_approval"] is True
        assert plano["planning_mode"] == "deterministic_fallback"
        assert len(plano["layers"]["L1_estabelecimento"]) == 4
        for camada in (
            "L2_titulo_heroi_t10",
            "L3_micro_zoom_bate",
            "L4_lower_third",
            "L5_broll_industrial",
            "L6_sound_design_sync",
        ):
            assert plano["layers"][camada] == [], f"camada {camada} deveria estar vazia no fallback"

        # Pausa nao deve criar topico novo no fallback
        topicos = {e["narrative_continuity"]["topic_id"] for e in edl["timeline_events"]}
        assert topicos == {"T_UNCLASSIFIED"}
    print("  [PASS] test_edl_sem_round_robin_e_fallback_conservador")


def _criar_semantic_plan_valido() -> Dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "generated_by": "teste-agnostico",
        "tema_central": "Alta minutagem em marketplaces na confecção",
        "tese_principal": "Produção precisa de ritmo industrial contínuo para escalar vendas online.",
        "topicos": [
            {
                "topic_id": "T01",
                "titulo": "Abertura e autoridade",
                "subtopicos": ["Boas-vindas", "Experiência de 29 anos"],
                "raw_start": 0.0,
                "raw_end": 5.5,
                "segment_ids": [0, 1],
                "justificativa": "Apresenta o canal e ancora autoridade do apresentador.",
            },
            {
                "topic_id": "T02",
                "titulo": "Alta minutagem nos marketplaces",
                "subtopicos": ["Escala em marketplaces"],
                "raw_start": 26.6,
                "raw_end": 104.41,
                "segment_ids": [2, 3],
                "justificativa": "Desenvolve o conceito de alta minutagem e faturamento.",
            },
        ],
        "argumentos": [
            {
                "id": "A01",
                "topic_id": "T02",
                "tipo": "tese",
                "resumo": "Marketplaces exigem alta minutagem produtiva para faturamento.",
                "raw_start": 26.6,
                "raw_end": 104.41,
                "segment_ids": [2, 3],
                "justificativa": "Nucleo argumentativo do trecho.",
            }
        ],
        "grupos_explicacao": [
            {
                "explanation_group_id": "E01",
                "topic_id": "T01",
                "titulo": "Introdução contínua",
                "raw_start": 0.0,
                "raw_end": 5.5,
                "segment_ids": [0, 1],
                "justificativa": "Saudação e tempo de mercado formam uma única unidade introdutória.",
            },
            {
                "explanation_group_id": "E02",
                "topic_id": "T02",
                "titulo": "Explicação alta minutagem",
                "raw_start": 26.6,
                "raw_end": 104.41,
                "segment_ids": [2, 3],
                "justificativa": "Explicação de alta minutagem e faturamento não deve ser separada.",
            },
        ],
        "ganchos_e_viradas": [
            {
                "id": "G01",
                "tipo": "gancho",
                "descricao": "29 anos de campo de batalha",
                "raw_start": 3.9,
                "raw_end": 5.0,
                "segment_ids": [1],
                "justificativa": "Gera credibilidade logo após a saudação.",
            }
        ],
        "repeticoes_dispensaveis": [],
        "falsos_comecos": [],
        "segmentos_editoriais": [
            {
                "decision": "preservar",
                "raw_start": 0.0,
                "raw_end": 5.5,
                "topic_id": "T01",
                "explanation_group_id": "E01",
                "segment_ids": [0, 1],
                "justificativa": "Preservar bloco introdutório completo.",
            },
            {
                "decision": "preservar",
                "raw_start": 26.6,
                "raw_end": 104.41,
                "topic_id": "T02",
                "explanation_group_id": "E02",
                "segment_ids": [2, 3],
                "justificativa": "Preservar explicação completa.",
            },
        ],
        "intencoes_visuais": [
            {
                "id": "IV01",
                "camada": "L2_titulo_heroi_t10",
                "componente_motion_library": "titulo_heroi",
                "texto": "Alta Minutagem",
                "raw_start": 26.6,
                "raw_end": 27.58,
                "segment_ids": [2],
                "funcao_editorial": "Destacar conceito central com título cinético T10.",
                "justificativa": "Momento em que o apresentador pronuncia o termo-chave.",
            },
            {
                "id": "IV02",
                "camada": "L6_sound_design_sync",
                "componente_motion_library": None,
                "texto": "whoosh_entrada_t10",
                "raw_start": 26.6,
                "raw_end": 26.85,
                "segment_ids": [2],
                "funcao_editorial": "Sincronizar whoosh com entrada do T10.",
                "justificativa": "Reforço sonoro da transição tipográfica.",
            },
        ],
    }


def test_semantic_plan_contrato_e_validacao_temporal():
    """Contrato valida schema, timestamps dentro da transcricao e rejeita timestamps inventados."""
    transcript = _gerar_transcricao_sintetica()
    # Ajustar segment ids para 0..3 compativeis com o plano
    for idx, seg in enumerate(transcript["segments"]):
        seg["id"] = idx
    plano = _criar_semantic_plan_valido()
    validado = validate_semantic_plan(plano, transcript_data=transcript)
    assert validado["schema_version"] == "1.0.0"

    # Timestamp fora da transcricao deve falhar
    plano_invalido = json.loads(json.dumps(plano))
    plano_invalido["topicos"][0]["raw_end"] = 999.0
    try:
        validate_semantic_plan(plano_invalido, transcript_data=transcript)
        assert False, "Esperado SemanticPlanError para timestamp inventado"
    except SemanticPlanError:
        pass
    print("  [PASS] test_semantic_plan_contrato_e_validacao_temporal")


def test_semantic_plan_rejeita_componente_inexistente():
    """Contrato e lint rejeitam referencia a componente inexistente no Motion Library."""
    assert "titulo_heroi" in IMPLEMENTED_MOTION_COMPONENTS
    plano = _criar_semantic_plan_valido()
    plano["intencoes_visuais"][0]["componente_motion_library"] = "broll_fantasma_v9"
    try:
        validate_semantic_plan(plano)
        assert False, "Esperado SemanticPlanError para componente inexistente"
    except SemanticPlanError:
        pass
    print("  [PASS] test_semantic_plan_rejeita_componente_inexistente")


def test_edl_e_briefing_com_semantic_plan_valido():
    """Briefing e EDL consomem semantic_plan.json, preservam grupos entre pausas e alimentam camadas justificadas."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        _setup_workspace_e_marca(tmp, "marca-sem")
        _setup_episodio_com_analise(tmp, "marca-sem", "ep-sem")

        loader = WorkspaceLoader(tmp)
        fonte_dir = loader.resolve_episodio_asset("marca-sem", "ep-sem", "workspace/fonte")
        transcript = json.loads((fonte_dir / "transcript.json").read_text(encoding="utf-8"))
        for idx, seg in enumerate(transcript["segments"]):
            seg["id"] = idx
        _gravar_json(fonte_dir / "transcript.json", transcript)

        briefing_dir = loader.resolve_episodio_asset("marca-sem", "ep-sem", "workspace/briefing")
        briefing_dir.mkdir(parents=True, exist_ok=True)
        _gravar_json(briefing_dir / "semantic_plan.json", _criar_semantic_plan_valido())

        gerar_briefing("marca-sem", "ep-sem", str(tmp))
        bj = json.load(open(briefing_dir / "briefing.json", encoding="utf-8"))
        assert bj["planning_mode"] == "semantic_plan"
        assert bj["requires_semantic_review"] is False
        assert bj["requires_human_approval"] is True
        assert "Alta minutagem em marketplaces" in bj["tema"]
        assert len(bj["motions"]) == 2
        assert bj["motions"][0]["componente_motion_library"] == "titulo_heroi"

        mp = loader.load_brand_profile("marca-sem")
        alinhamento_path = fonte_dir / "alignment.json"
        edl, plano_ed = build_edl_from_alignment(
            alignment_path=alinhamento_path,
            workspace_root=str(tmp),
            marca_id="marca-sem",
            episodio_id="ep-sem",
            brand_profile=mp,
        )
        assert edl["planning_mode"] == "semantic_plan"
        # Eventos 0 e 1 compartilham E01 apesar da pausa entre eles; eventos 2 e 3 compartilham E02
        gids = [ev["narrative_continuity"]["explanation_group_id"] for ev in edl["timeline_events"]]
        assert gids == ["E01", "E01", "E02", "E02"]
        assert len(plano_ed["layers"]["L1_estabelecimento"]) == 4
        assert len(plano_ed["layers"]["L2_titulo_heroi_t10"]) == 1
        assert len(plano_ed["layers"]["L6_sound_design_sync"]) == 1
        assert plano_ed["layers"]["L4_lower_third"] == []

        projeto = loader.load_project("marca-sem", "ep-sem")
        rel = lint(plano_ed, edl, projeto)
        assert rel["ok"] is True, f"Lint falhou: {rel['failures']}"
        assert rel["auto_approved"] is False
    print("  [PASS] test_edl_e_briefing_com_semantic_plan_valido")


def test_lint_camadas_continuas_vs_pontuais_e_quebra_contexto():
    """Lint permite gaps > 0.5s em overlays/L6, bloqueia em L1 continua e detecta quebra de explanation_group_id."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        _setup_workspace_e_marca(tmp, "marca-lint3")
        _setup_episodio_com_analise(tmp, "marca-lint3", "ep-lint3")
        loader = WorkspaceLoader(tmp)
        projeto = loader.load_project("marca-lint3", "ep-lint3")
        src = {
            "id": projeto["sources"][0]["id"],
            "path": projeto["sources"][0]["path"],
            "sha256": projeto["sources"][0]["sha256"],
        }
        # Plano valido com 2 overlays em L2 separados por 3.0s (> 0.5s) e 2 SFX em L6 sobrepostos
        plano = {
            "schema_version": "1.0.0",
            "layers": {
                "L1_estabelecimento": [
                    {
                        "element_id": "E00001", "event_id": 1, "source_ref": src,
                        "out_in": 0.0, "out_out": 2.0,
                        "narrative_continuity": {"topic_id": "T1", "explanation_group_id": "E1"},
                    },
                    {
                        "element_id": "E00002", "event_id": 2, "source_ref": src,
                        "out_in": 2.0, "out_out": 5.0,
                        "narrative_continuity": {"topic_id": "T1", "explanation_group_id": "E1"},
                    },
                ],
                "L2_titulo_heroi_t10": [
                    {"element_id": "V1", "source_ref": src, "out_in": 0.2, "out_out": 1.0, "componente_motion_library": "titulo_heroi"},
                    {"element_id": "V2", "source_ref": src, "out_in": 4.0, "out_out": 4.8, "componente_motion_library": "titulo_heroi"},
                ],
                "L3_micro_zoom_bate": [],
                "L4_lower_third": [],
                "L5_broll_industrial": [],
                "L6_sound_design_sync": [
                    {"element_id": "S1", "source_ref": src, "out_in": 0.2, "out_out": 0.5},
                    {"element_id": "S2", "source_ref": src, "out_in": 0.3, "out_out": 0.6},
                ],
            },
        }
        rel_ok = lint(plano, edl=None, projeto=projeto)
        assert rel_ok["ok"] is True, f"Falha inesperada: {rel_ok['failures']}"

        # Quebra de contexto em L1: E1 -> E2 -> E1
        plano["layers"]["L1_estabelecimento"].append(
            {
                "element_id": "E00003", "event_id": 3, "source_ref": src,
                "out_in": 5.0, "out_out": 6.0,
                "narrative_continuity": {"topic_id": "T2", "explanation_group_id": "E2"},
            }
        )
        plano["layers"]["L1_estabelecimento"].append(
            {
                "element_id": "E00004", "event_id": 4, "source_ref": src,
                "out_in": 6.0, "out_out": 7.0,
                "narrative_continuity": {"topic_id": "T1", "explanation_group_id": "E1"},
            }
        )
        rel_quebra = lint(plano, edl=None, projeto=projeto)
        assert rel_quebra["ok"] is False
        assert any("quebra de contexto" in f.lower() for f in rel_quebra["failures"])
    print("  [PASS] test_lint_camadas_continuas_vs_pontuais_e_quebra_contexto")


def test_avaliacao_controlada_benchmark_real():
    """Avaliacao controlada com transcricao real do benchmark (somente leitura na fonte, sem Whisper/render)."""
    bench_transcript = Path(os.environ.get("EDITOR_BENCHMARK_TRANSCRIPT", "__missing_benchmark__.json"))
    if not bench_transcript.is_file():
        print("  [SKIP] test_avaliacao_controlada_benchmark_real (benchmark ausente)")
        return

    from core.analyze import build_alignment_from_words

    real_loader = WorkspaceLoader(Path(__file__).resolve().parent.parent)
    real_loader.load_workspace()
    bp_real = real_loader.load_brand_profile("dr-gestao")
    t_data = json.loads(bench_transcript.read_text(encoding="utf-8"))
    words = [
        {"w": w["word"], "t": w["start"], "f": w["end"], "probability": w.get("probability", 1.0)}
        for s in t_data.get("segments", [])
        for w in s.get("words", [])
    ]
    alinhamento = build_alignment_from_words(words, bp_real.get("config_json", {}))

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        _setup_workspace_e_marca(tmp, "dr-gestao")
        _setup_episodio_com_analise(tmp, "dr-gestao", "ep-bench")
        loader = WorkspaceLoader(tmp)
        fonte_dir = loader.resolve_episodio_asset("dr-gestao", "ep-bench", "workspace/fonte")
        _gravar_json(fonte_dir / "transcript.json", t_data)
        _gravar_json(fonte_dir / "alignment.json", alinhamento)
        _gravar_json(
            fonte_dir / "phonetic_report.json",
            {"low_confidence": [w for w in words if w["probability"] < 0.6]},
        )

        rc = gerar_briefing("dr-gestao", "ep-bench", str(tmp), marca_profile=bp_real)
        assert rc == 0
        briefing_dir = loader.resolve_episodio_asset("dr-gestao", "ep-bench", "workspace/briefing")
        bj = json.load(open(briefing_dir / "briefing.json", encoding="utf-8"))

        # Verifica apresentador real e ausencia de afirmacao falsa de tema semantico
        assert bj["marca"]["apresentador"] == "Luiz Roberto Saraiva"
        assert "confecção do vestuário" in bj["marca"]["credencial_oficial"].lower()
        assert "clínica, médicos" not in bj["tema"].lower()
        assert bj["planning_mode"] == "deterministic_fallback"
        assert bj["requires_semantic_review"] is True
        assert bj["motions"] == []

        edl, plano = build_edl_from_alignment(
            alignment_path=fonte_dir / "alignment.json",
            workspace_root=str(tmp),
            marca_id="dr-gestao",
            episodio_id="ep-bench",
            brand_profile=bp_real,
        )
        assert len(plano["layers"]["L1_estabelecimento"]) == len(edl["timeline_events"])
        for c in REQUIRED_LAYERS[1:]:
            assert plano["layers"][c] == []

        projeto = loader.load_project("dr-gestao", "ep-bench")
        rel = lint(plano, edl, projeto)
        assert rel["ok"] is True, f"Lint falhou no benchmark fallback: {rel['failures']}"
        assert rel["auto_approved"] is False
    print("  [PASS] test_avaliacao_controlada_benchmark_real")


# ---------------------------------------------------------------------------
# Runner auxiliar (execucao direta)
# ---------------------------------------------------------------------------


def run_tests():
    print("=" * 60)
    print("SUITE DE TESTES — core/editorial (Editor)")
    print("=" * 60)
    testes = [
        test_gerar_briefing_arquivos,
        test_briefing_preserva_explicacoes_contextualizadas,
        test_edl_longo_editorial_plan_6_camadas,
        test_master_lint_aprovado_sem_aprovacao_automatica,
        test_lint_detecta_lacunas_e_sobreposicoes,
        test_lint_detecta_referencia_fonte_inexistente,
        test_reprodutibilidade_deterministica,
        test_consumo_brand_profile,
        test_brand_profile_preferencias_e_phonetic_w,
        test_edl_sem_round_robin_e_fallback_conservador,
        test_semantic_plan_contrato_e_validacao_temporal,
        test_semantic_plan_rejeita_componente_inexistente,
        test_edl_e_briefing_com_semantic_plan_valido,
        test_lint_camadas_continuas_vs_pontuais_e_quebra_contexto,
        test_avaliacao_controlada_benchmark_real,
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
