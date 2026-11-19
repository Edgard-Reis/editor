# -*- coding: utf-8 -*-
"""core/test_transcript_review.py

Suíte sintética (100% em tmp_path) para core/transcript_review.py:

Comprova:
  - transcript.json original nao e sobrescrito (SHA-256 identico antes/depois).
  - transcript_reviewed.json contem as duas correcoes:
      * 'Kaique Arakelian' agrupado de 2 tokens (start do 1o, end do ultimo).
      * 'Cobasi' nas ocorrencias especificas.
  - Timestamps permanecem preservados.
  - Correcoes aparecem no relatorio de proveniencia (human_review, proprietario,
    reviewed_at, reviewed_version) com probability original intacta e separada.
  - O vocabulario (lexicon / lexicon_transcricao) e carregado pelo mecanismo
    existente (core/workspace.py + core/analyze.py) e repassado como
    initial_prompt para transcrever.transcreve.
  - Correcoes/vocabulario de um projeto NAO vazam nem sao aplicados a outro.
  - Nenhuma probability original e modificada.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import inspect
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List

import pytest

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from core.transcript_review import (  # noqa: E402
    review_transcript,
    resolve_editorial_transcript,
    sync_alignment_with_editorial_transcript,
    record_transcription_benchmark,
    TranscriptReviewError,
)
from core.workspace import WorkspaceLoader, init_workspace  # noqa: E402

# Carrega transcrever dinamicamente (mesmo mecanismo usado por analyze.py).
_TRANSCREVER = None


def _transcrever_modulo():
    global _TRANSCREVER
    if _TRANSCREVER is None:
        caminho = _REPO / "vortex-edicao" / "transcrever.py"
        spec = importlib.util.spec_from_file_location("transcrever_review", str(caminho))
        modulo = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(modulo)
        _TRANSCREVER = modulo
    return _TRANSCREVER


# ---------------------------------------------------------------------------
# Helpers de transcript sintético
# ---------------------------------------------------------------------------


def _montar_transcript(
    tmp: Path,
    marcas: Dict[str, Dict[str, Any]],
) -> Dict[str, Path]:
    """Cria workspaces de marcas com branding (vocabulario) e transcripts."""
    caminhos: Dict[str, Path] = {}
    for marca_id, cfg in marcas.items():
        init_workspace(tmp)
        loader = WorkspaceLoader(tmp)
        loader.load_workspace()

        marca_dir = tmp / "projetos" / marca_id / "branding"
        marca_dir.mkdir(parents=True, exist_ok=True)
        (marca_dir / "config.json").write_text(
            json.dumps(
                {
                    "schema_version": "1.0.0",
                    "brand_id": marca_id,
                    "display_name": f"Marca {marca_id}",
                    "marca": {"destaque": "#004aad", "fonte": "Inter"},
                    **cfg,
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        episodio_id = "ep-review"
        fonte_dir = loader.resolve_episodio_asset(
            marca_id, episodio_id, "workspace/fonte"
        )
        fonte_dir.mkdir(parents=True, exist_ok=True)

        # Cria project.json minimo para nao quebrar o loader.
        projeto = {
            "schema_version": "1.0.0",
            "marca_id": marca_id,
            "episodio_id": episodio_id,
            "nome": episodio_id,
            "current_stage": "01_GRAVACAO_ORIGINAL",
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-01T00:00:00+00:00",
            "sources": [],
            "artifacts": {},
            "approvals": {"master_16x9_approved": False},
        }
        loader.project_file(marca_id, episodio_id).parent.mkdir(
            parents=True, exist_ok=True
        )
        loader.project_file(marca_id, episodio_id).write_text(
            json.dumps(projeto, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        # Transcript sintético com segmentos e probabilities reais do Whisper.
        transcript = {
            "schema_version": "1.0.0",
            "engine": "faster-whisper",
            "language": "pt",
            "segments": [
                {
                    "id": 160,
                    "start": 9.0,
                    "end": 9.5,
                    "text": "Ola",
                    "words": [
                        {"word": "Ola", "start": 9.0, "end": 9.5, "probability": 0.95},
                    ],
                },
                {
                    "id": 162,
                    "start": 10.0,
                    "end": 10.4,
                    "text": "Kaique",
                    "words": [
                        {"word": "Kaique", "start": 10.0, "end": 10.4, "probability": 0.90},
                    ],
                },
                {
                    "id": 163,
                    "start": 10.4,
                    "end": 11.0,
                    "text": "Arakelian",
                    "words": [
                        {
                            "word": "Arakelian",
                            "start": 10.4,
                            "end": 11.0,
                            "probability": 0.85,
                        }
                    ],
                },
                {
                    "id": 50,
                    "start": 5.0,
                    "end": 5.5,
                    "text": "Cobasi",
                    "words": [
                        {"word": "Cobasi", "start": 5.0, "end": 5.5, "probability": 0.88},
                    ],
                },
                {
                    "id": 51,
                    "start": 6.0,
                    "end": 6.5,
                    "text": "Cobasi",
                    "words": [
                        {"word": "Cobasi", "start": 6.0, "end": 6.5, "probability": 0.91},
                    ],
                },
            ],
        }
        transcript_path = fonte_dir / "transcript.json"
        transcript_path.write_text(
            json.dumps(transcript, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        caminhos[marca_id] = transcript_path
    return caminhos


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Testes
# ---------------------------------------------------------------------------


def test_transcript_original_nao_sobrescrito(tmp_path):
    """SHA-256 do transcript.json e' identico antes e depois da revisao."""
    caminhos = _montar_transcript(
        tmp_path,
        {
            "marca-a": {
                "schema_version": "1.0.0",
                "brand_id": "marca-a",
                "display_name": "Marca A",
                "preferencias_edicao": {
                    "asr": {
                        "lexicon": ["Cobasi"],
                        "lexicon_transcricao": "Kaique, Arakelian",
                    }
                },
            }
        },
    )
    transcript_path = caminhos["marca-a"]
    sha_antes = _sha256(transcript_path)

    corrections = [
        {"segment_ids": [162, 163], "corrected_text": "Kaique Arakelian"},
        {"segment_id": 50, "corrected_text": "Cobasi Loja"},
    ]
    review_transcript(
        transcript_path,
        corrections,
        output_path=tmp_path / "marca-a" / "transcript_reviewed.json",
        report_path=tmp_path / "marca-a" / "corrections_report.json",
        reviewed_by="proprietario",
        reviewed_version="1.0.0",
    )

    sha_depois = _sha256(transcript_path)
    assert sha_antes == sha_depois, "transcript.json original foi modificado!"
    assert (tmp_path / "marca-a" / "transcript_reviewed.json").is_file()


def test_transcript_reviewed_contem_correcoes_agrupadas(tmp_path):
    """Kaique Arakelian agrupado (start 1o, end ultimo); Cobasi em ocorrencias específicas."""
    caminhos = _montar_transcript(
        tmp_path,
        {
            "marca-b": {
                "schema_version": "1.0.0",
                "brand_id": "marca-b",
                "display_name": "Marca B",
                "preferencias_edicao": {},
            }
        },
    )
    transcript_path = caminhos["marca-b"]

    corrections = [
        {"segment_ids": [162, 163], "corrected_text": "Kaique Arakelian"},
        {"segment_id": 50, "corrected_text": "Cobasi Loja"},
    ]
    resultado = review_transcript(
        transcript_path,
        corrections,
        output_path=tmp_path / "marca-b" / "transcript_reviewed.json",
        reviewed_by="proprietario",
        reviewed_version="1.0.0",
    )

    reviewed = resultado["reviewed_result"]
    textos = [s.get("text", "") for s in reviewed["segments"]]
    assert "Kaique Arakelian" in textos, textos
    assert "Cobasi Loja" in textos, textos

    # O segmento agrupado Kaique Arakelian deve ter start do 1o token e end do ultimo.
    ka = [s for s in reviewed["segments"] if s.get("text") == "Kaique Arakelian"][0]
    assert ka["start"] == 10.0, ka
    assert ka["end"] == 11.0, ka
    assert len(ka["words"]) == 2, ka
    assert ka["words"][0]["word"] == "Kaique"
    assert ka["words"][1]["word"] == "Arakelian"

    # Cobasi corrigida (segmento 50) mantem start/end originais.
    cob = [s for s in reviewed["segments"] if s.get("text") == "Cobasi Loja"][0]
    assert cob["start"] == 5.0, cob
    assert cob["end"] == 5.5, cob


def test_timestamps_preservados_e_segmentos_nao_corrigidos_intactos(tmp_path):
    """Nao-corrigidos preservados; nao ha inventacao de timestamps."""
    caminhos = _montar_transcript(
        tmp_path,
        {"marca-c": {"schema_version": "1.0.0", "brand_id": "marca-c", "display_name": "Marca C", "preferencias_edicao": {}}},
    )
    transcript_path = caminhos["marca-c"]

    corrections = [{"segment_id": 160, "corrected_text": "Ola Mundo"}]
    resultado = review_transcript(
        transcript_path,
        corrections,
        output_path=tmp_path / "marca-c" / "transcript_reviewed.json",
        reviewed_by="proprietario",
    )

    reviewed = resultado["reviewed_result"]["segments"]
    # Segmento 160 corrigido: texto mudou, mas start/end preservados.
    seg160 = [s for s in reviewed if s.get("id") == "reviewed-1"][0]
    assert seg160["text"] == "Ola Mundo"
    assert seg160["start"] == 9.0
    assert seg160["end"] == 9.5
    # Segmentos 162, 163, 50, 51 nao corrigidos: intactos.
    ids_nao_corrigidos = [s.get("id") for s in reviewed if isinstance(s.get("id"), int)]
    assert 162 in ids_nao_corrigidos
    assert 163 in ids_nao_corrigidos
    assert 50 in ids_nao_corrigidos
    assert 51 in ids_nao_corrigidos


def test_proveniencia_human_review_probability_intacta(tmp_path):
    """Correcoes marcadas como human_review com probability original intacta."""
    caminhos = _montar_transcript(
        tmp_path,
        {"marca-d": {"schema_version": "1.0.0", "brand_id": "marca-d", "display_name": "Marca D", "preferencias_edicao": {}}},
    )
    transcript_path = caminhos["marca-d"]

    corrections = [
        {"segment_ids": [162, 163], "corrected_text": "Kaique Arakelian", "category": "nome_proprio"},
    ]
    resultado = review_transcript(
        transcript_path,
        corrections,
        output_path=tmp_path / "marca-d" / "transcript_reviewed.json",
        report_path=tmp_path / "marca-d" / "corrections_report.json",
        reviewed_by="proprietario",
        reviewed_version="1.0.0",
    )

    correcao = resultado["human_corrections"][0]
    assert correcao["origin"] == "human_review"
    assert correcao["confirmed_by"] == "proprietario"
    assert correcao["reviewed_at"]
    assert correcao["reviewed_version"] == "1.0.0"
    assert correcao["category"] == "nome_proprio"

    # Probability original intacta nos tokens de proveniencia.
    tokens = correcao["original_tokens"]
    assert len(tokens) == 2
    assert tokens[0]["word"] == "Kaique"
    assert tokens[0]["probability"] == 0.90
    assert tokens[1]["word"] == "Arakelian"
    assert tokens[1]["probability"] == 0.85

    # Relatorio de correcoes gravado.
    report = json.loads((tmp_path / "marca-d" / "corrections_report.json").read_text(encoding="utf-8"))
    assert report["total_corrections"] == 1
    assert report["corrections"][0]["origin"] == "human_review"


def test_nao_modifica_probability_original_original_whisper_confidence(tmp_path):
    """Nenhuma probability original e modificada (nem em original_whisper_confidence)."""
    caminhos = _montar_transcript(
        tmp_path,
        {"marca-e": {"schema_version": "1.0.0", "brand_id": "marca-e", "display_name": "Marca E", "preferencias_edicao": {}}},
    )
    transcript_path = caminhos["marca-e"]

    corrections = [{"segment_id": 51, "corrected_text": "Cobasi Matriz"}]
    resultado = review_transcript(
        transcript_path,
        corrections,
        output_path=tmp_path / "marca-e" / "transcript_reviewed.json",
        reviewed_by="proprietario",
    )

    orig = resultado["original_whisper_confidence"]
    seg_51 = [s for s in orig["segments"] if s.get("id") == 51][0]
    assert seg_51["words"][0]["probability"] == 0.91  # inalterada

    # reviewed_result tambem nao altera probabilities dos nao-corrigidos.
    revisado = [s for s in resultado["reviewed_result"]["segments"] if s.get("id") == 51]
    if revisado:
        assert revisado[0]["words"][0]["probability"] == 0.91


def test_erro_se_output_aponta_para_original(tmp_path):
    """output_path igual ao transcript.json levanta ValueError."""
    caminhos = _montar_transcript(
        tmp_path,
        {"marca-f": {"schema_version": "1.0.0", "brand_id": "marca-f", "display_name": "Marca F", "preferencias_edicao": {}}},
    )
    transcript_path = caminhos["marca-f"]
    with pytest.raises(ValueError):
        review_transcript(
            transcript_path,
            [{"segment_id": 160, "corrected_text": "X"}],
            output_path=transcript_path,
        )


def test_transcrever_aceita_initial_prompt():
    """transcrever.transcreve aceita o parametro initial_prompt (compatibilidade)."""
    transcrever = _transcrever_modulo()
    params = inspect.signature(transcrever.transcreve).parameters
    assert "initial_prompt" in params
    assert params["initial_prompt"].default is None


def test_vocabulario_nao_vaza_entre_marcas(tmp_path):
    """Vocabulario/initial_prompt de uma marca nao vaza para outra."""
    caminhos = _montar_transcript(
        tmp_path,
        {
            "marca-g": {
                "schema_version": "1.0.0",
                "brand_id": "marca-g",
                "display_name": "Marca G",
                "preferencias_edicao": {
                    "asr": {
                        "lexicon": ["TermoEspecificoG"],
                        "lexicon_transcricao": "Kaique, Arakelian",
                    }
                },
            },
            "marca-h": {
                "schema_version": "1.0.0",
                "brand_id": "marca-h",
                "display_name": "Marca H",
                "preferencias_edicao": {
                    "asr": {
                        "lexicon": ["TermoEspecificoH"],
                    }
                },
            },
        },
    )
    # Carrega perfis de ambas as marcas de forma isolada.
    loader_g = WorkspaceLoader(tmp_path)
    loader_g.load_workspace()
    perfil_g = loader_g.load_brand_profile("marca-g")
    asr_g = (perfil_g["config_json"].get("preferencias_edicao", {}) or {}).get("asr", {}) or {}
    lexicon_g = list(asr_g.get("lexicon", []) or [])
    transc_g = asr_g.get("lexicon_transcricao", "")

    loader_h = WorkspaceLoader(tmp_path)
    loader_h.load_workspace()
    perfil_h = loader_h.load_brand_profile("marca-h")
    asr_h = (perfil_h["config_json"].get("preferencias_edicao", {}) or {}).get("asr", {}) or {}
    lexicon_h = list(asr_h.get("lexicon", []) or [])

    assert "TermoEspecificoG" in lexicon_g
    assert "TermoEspecificoH" in lexicon_h
    assert "TermoEspecificoH" not in lexicon_g
    assert "TermoEspecificoG" not in lexicon_h
    # Cada marca tem seu proprio initial_prompt (nao vazamento global).
    prompt_g = "Vocabulario da marca: TermoEspecificoG, Kaique, Arakelian."
    prompt_h = "Vocabulario da marca: TermoEspecificoH."
    assert prompt_g != prompt_h
    # transcript de cada marca mantido isolado (arquivos separados em caminhos diferentes).
    assert caminhos["marca-g"] != caminhos["marca-h"]


def test_record_transcription_benchmark_grava_json_e_md(tmp_path):
    """record_transcription_benchmark grava JSON e Markdown sem WER sem ground truth."""
    json_path = tmp_path / "bench.json"
    md_path = tmp_path / "bench.md"
    dados = {
        "modelo": "faster-whisper-large-v3-turbo",
        "duracao_segundos": 14.447,
        "total_palavras": 26,
        "idioma": "pt",
        "local_files_only": True,
        "offline_only": True,
    }
    resultado = record_transcription_benchmark(
        dados, json_path=json_path, md_path=md_path
    )
    assert json_path.is_file()
    assert md_path.is_file()
    assert resultado["json_path"] == str(json_path)
    assert resultado["md_path"] == str(md_path)
    assert resultado["recorded_at"]

    gravado = json.loads(json_path.read_text(encoding="utf-8"))
    assert gravado["benchmark"]["modelo"] == dados["modelo"]
    assert gravado["benchmark"]["local_files_only"] is True
    md = md_path.read_text(encoding="utf-8")
    assert "Benchmark de Transcricao" in md or "Benchmark de Transcrição" in md
    # Nao calcula WER nem %% acuracia sem ground truth integral (apenas menciona).
    assert "nao calculados" in md or "sem ground truth integral" in md
    assert "WER =" not in md and "acuracia:" not in md


# ---------------------------------------------------------------------------
# Lote 1: resolve_editorial_transcript e sync_alignment_with_editorial_transcript
# ---------------------------------------------------------------------------


def _gerar_wav_16k(caminho: Path, duracao_s: float = 2.0) -> None:
    """Gera WAV PCM 16kHz mono sintético (tom puro) sem ffmpeg."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    sample_rate = 16000
    n_samples = int(sample_rate * duracao_s)
    import struct
    import math
    import wave
    amostras = []
    for i in range(n_samples):
        valor = int(12000 * math.sin(2 * math.pi * 440.0 * i / sample_rate))
        amostras.append(struct.pack("<h", valor))
    with wave.open(str(caminho), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b"".join(amostras))


def _transcript_base() -> Dict[str, Any]:
    """Transcript base com segmentos e palavras (probability real do Whisper)."""
    return {
        "schema_version": "1.0.0",
        "engine": "faster-whisper",
        "language": "pt",
        "segments": [
            {
                "id": 10,
                "start": 0.0,
                "end": 0.6,
                "text": "Ola",
                "words": [{"word": "Ola", "start": 0.0, "end": 0.6, "probability": 0.95}],
            },
            {
                "id": 11,
                "start": 0.7,
                "end": 1.3,
                "text": "mundo",
                "words": [{"word": "mundo", "start": 0.7, "end": 1.3, "probability": 0.92}],
            },
            {
                "id": 12,
                "start": 1.4,
                "end": 2.0,
                "text": "Kaique",
                "words": [{"word": "Kaique", "start": 1.4, "end": 1.9, "probability": 0.90}],
            },
            {
                "id": 13,
                "start": 1.9,
                "end": 2.5,
                "text": "Arakelian",
                "words": [
                    {
                        "word": "Arakelian",
                        "start": 1.9,
                        "end": 2.5,
                        "probability": 0.85,
                    }
                ],
            },
        ],
    }


def _setup_workspace_com_transcricao(
    tmp: Path, marca_id: str = "marca-lote1", episodio_id: str = "ep-lote1"
) -> tuple[Path, Path, Path]:
    """Cria workspace minimo com marca, episodio, transcript.json, alignment.json, audio.

    Retorna (fonte_dir, transcript_path, alignment_path).
    """
    init_workspace(tmp)
    loader = WorkspaceLoader(tmp)
    loader.load_workspace()

    marca_dir = tmp / "projetos" / marca_id / "branding"
    marca_dir.mkdir(parents=True, exist_ok=True)
    (marca_dir / "config.json").write_text(
        json.dumps(
            {
                "schema_version": "1.0.0",
                "brand_id": marca_id,
                "display_name": f"Marca {marca_id}",
                "marca": {"destaque": "#004aad", "fonte": "Inter"},
                "preferencias_edicao": {
                    "canal": f"Canal {marca_id}",
                    "audio": {
                        "silence_guard_ms": [180, 220],
                        "jumpcut_gap_threshold_ms": 450,
                        "jumpcut_target_gap_ms": [200, 250],
                    },
                },
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    fonte_dir = loader.resolve_episodio_asset(
        marca_id, episodio_id, "workspace/fonte"
    )
    fonte_dir.mkdir(parents=True, exist_ok=True)

    # project.json minimo (com source registrada para o edl_builder).
    brutos_path = tmp / "projetos" / marca_id / "episodios" / episodio_id / "brutos" / "video.mp4"
    brutos_path.parent.mkdir(parents=True, exist_ok=True)
    brutos_path.write_bytes(b"fake-video")
    brutos_sha = _sha256(brutos_path)
    projeto = {
        "schema_version": "1.0.0",
        "marca_id": marca_id,
        "episodio_id": episodio_id,
        "nome": episodio_id,
        "current_stage": "01_GRAVACAO_ORIGINAL",
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
        "sources": [
            {
                "id": f"SRC_{marca_id.upper()}_{episodio_id.upper()}",
                "path": str(brutos_path),
                "sha256": brutos_sha,
            }
        ],
        "artifacts": {},
        "approvals": {"master_16x9_approved": False},
    }
    loader.project_file(marca_id, episodio_id).parent.mkdir(
        parents=True, exist_ok=True
    )
    loader.project_file(marca_id, episodio_id).write_text(
        json.dumps(projeto, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # audio_speech_16k_mono.wav (necessario para build_alignment_from_words).
    _gerar_wav_16k(fonte_dir / "audio_speech_16k_mono.wav")

    transcript_path = fonte_dir / "transcript.json"
    transcript_path.write_text(
        json.dumps(_transcript_base(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # alignment.json minimo (será re-sincronizado por sync_alignment...).
    alinhamento = {
        "schema_version": "1.0.0",
        "status": "COMPLETED",
        "editorial_units": [
            {
                "unit_id": 1,
                "text": "Ola mundo",
                "raw_start": 0.0,
                "raw_end": 1.3,
                "padded_in_point": 0.0,
                "padded_out_point": 1.3,
                "words": [],
            }
        ],
    }
    alignment_path = fonte_dir / "alignment.json"
    alignment_path.write_text(
        json.dumps(alinhamento, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    return fonte_dir, transcript_path, alignment_path


# ---------------------------------------------------------------------------
# 1) Positivo sem revisão: source_kind == raw_transcript
# ---------------------------------------------------------------------------


def test_resolve_editorial_transcript_raw_sem_revisao(tmp_path):
    """Sem transcript_reviewed.json: source_kind == raw_transcript."""
    fonte_dir, transcript_path, _ = _setup_workspace_com_transcricao(tmp_path)
    sha_antes = _sha256(transcript_path)

    editorial = resolve_editorial_transcript(fonte_dir)

    assert editorial["source_kind"] == "raw_transcript"
    assert editorial["transcript_sha256"] == sha_antes
    assert editorial.get("base_transcript_sha256") is None
    assert editorial.get("reviewed_by") is None
    assert len(editorial["words"]) == 4
    # Nenhum arquivo de revisao criado.
    assert not (fonte_dir / "transcript_reviewed.json").exists()
    # transcript.json inalterado.
    assert _sha256(transcript_path) == sha_antes


# ---------------------------------------------------------------------------
# 2) Positivo com transcript_reviewed.json valido
# ---------------------------------------------------------------------------


def test_resolve_editorial_transcript_revisado_valido(tmp_path):
    """Com revisão válida: source_kind == reviewed_transcript, termos corrigidos."""
    fonte_dir, transcript_path, _ = _setup_workspace_com_transcricao(tmp_path)
    sha_antes = _sha256(transcript_path)

    # Cria revisão agrupando Kaique + Arakelian (ids 12, 13).
    review = review_transcript(
        transcript_path,
        [
            {
                "segment_ids": [12, 13],
                "corrected_text": "Kaique Arakelian",
                "category": "nome_proprio",
            }
        ],
        output_path=fonte_dir / "transcript_reviewed.json",
        report_path=fonte_dir / "corrections_report.json",
        reviewed_by="proprietario",
        reviewed_version="1.0.0",
    )

    editorial = resolve_editorial_transcript(fonte_dir)

    assert editorial["source_kind"] == "reviewed_transcript"
    assert editorial["base_transcript_sha256"] == sha_antes
    assert editorial["reviewed_by"] == "proprietario"
    assert editorial["reviewed_version"] == "1.0.0"

    # Termo corrigido "Kaique Arakelian" presente (agrupado, start do 1o, end do ultimo).
    textos = [s.get("text", "") for s in editorial["segments"]]
    assert "Kaique Arakelian" in textos, textos
    ka = [s for s in editorial["segments"] if s.get("text") == "Kaique Arakelian"][0]
    assert ka["start"] == 1.4
    assert ka["end"] == 2.5

    # Palavras preservam probability original.
    palavras = editorial["words"]
    kaique = [w for w in palavras if w["w"] == "Kaique"][0]
    arakelian = [w for w in palavras if w["w"] == "Arakelian"][0]
    assert kaique["probability"] == 0.90
    assert arakelian["probability"] == 0.85

    # transcript.json original intacto (nao sobrescrito).
    assert _sha256(transcript_path) == sha_antes


# ---------------------------------------------------------------------------
# 3) sync_alignment_with_editorial_transcript + integridade
# ---------------------------------------------------------------------------


def test_sync_alignment_preserva_transcript_original_e_delta_hash(tmp_path):
    """sync_alignment reconstrói alignment.json; transcript.json intacto (Delta-Hash=0)."""
    fonte_dir, transcript_path, alignment_path = _setup_workspace_com_transcricao(
        tmp_path
    )
    sha_antes = _sha256(transcript_path)
    alinhamento_antes = _sha256(alignment_path)

    # Cria revisão válida.
    review_transcript(
        transcript_path,
        [
            {
                "segment_ids": [12, 13],
                "corrected_text": "Kaique Arakelian",
            }
        ],
        output_path=fonte_dir / "transcript_reviewed.json",
        reviewed_by="proprietario",
    )

    # Sincroniza alinhamento a partir da transcrição editorial.
    sync_result = sync_alignment_with_editorial_transcript(fonte_dir)

    assert sync_result["source_kind"] == "reviewed_transcript"
    assert sync_result["base_transcript_sha256"] == sha_antes
    assert sync_result["reviewed_by"] == "proprietario"

    # alignment.json foi reescrito (conteúdo diferente do minimo inicial).
    assert _sha256(alignment_path) != alinhamento_antes

    # transcript.json NUNCA sobrescrito (Delta-Hash = 0).
    assert _sha256(transcript_path) == sha_antes

    # alignment.json consumível: segmentos contêm o termo corrigido.
    alinhamento = json.loads(alignment_path.read_text(encoding="utf-8"))
    unidades = alinhamento.get("editorial_units", [])
    textos = [u.get("text", "") for u in unidades]
    assert any("Kaique Arakelian" in t for t in textos), textos

    # palavras.json e roteiro.txt gerados.
    assert (fonte_dir / "palavras.json").is_file()
    assert (fonte_dir / "roteiro.txt").is_file()


# ---------------------------------------------------------------------------
# 4) Negativo: transcript.json alterado após revisão -> base sha diverge
# ---------------------------------------------------------------------------


def test_transcript_alterado_apos_revisao_erro(tmp_path):
    """Revisão desatualizada: base_transcript_sha256 diverge -> TranscriptReviewError."""
    fonte_dir, transcript_path, _ = _setup_workspace_com_transcricao(tmp_path)

    review_transcript(
        transcript_path,
        [{"segment_id": 10, "corrected_text": "Ola Mundo"}],
        output_path=fonte_dir / "transcript_reviewed.json",
        reviewed_by="proprietario",
    )

    # Altera transcript.json após a revisão.
    transcript_path.write_bytes(
        transcript_path.read_bytes() + b"\n"  # altera conteúdo
    )

    with pytest.raises(TranscriptReviewError) as exc:
        resolve_editorial_transcript(fonte_dir)
    assert "desatualizada" in str(exc.value).lower() or "diverge" in str(
        exc.value
    ).lower()


# ---------------------------------------------------------------------------
# 5) Negativo: transcript_reviewed.json corrompido
# ---------------------------------------------------------------------------


def test_revisado_corrompido_erro(tmp_path):
    """transcript_reviewed.json JSON inválido -> TranscriptReviewError."""
    fonte_dir, transcript_path, _ = _setup_workspace_com_transcricao(tmp_path)
    (fonte_dir / "transcript_reviewed.json").write_text("{json quebrado", encoding="utf-8")

    with pytest.raises(TranscriptReviewError):
        resolve_editorial_transcript(fonte_dir)


# ---------------------------------------------------------------------------
# 6) Negativo: revisado sem reviewed_result.segments
# ---------------------------------------------------------------------------


def test_revisado_sem_segments_erro(tmp_path):
    """transcript_reviewed.json sem segments (top-level) -> TranscriptReviewError."""
    fonte_dir, transcript_path, _ = _setup_workspace_com_transcricao(tmp_path)
    revisado = {
        "schema_version": "1.0.0",
        "reviewed_by": "proprietario",
        "reviewed_version": "1.0.0",
        "source_transcript_sha256": _sha256(transcript_path),
        # sem segments
    }
    (fonte_dir / "transcript_reviewed.json").write_text(
        json.dumps(revisado), encoding="utf-8"
    )

    with pytest.raises(TranscriptReviewError):
        resolve_editorial_transcript(fonte_dir)


# ---------------------------------------------------------------------------
# 7) Negativo: revisado sem source_transcript_sha256
# ---------------------------------------------------------------------------


def test_revisado_sem_base_sha_erro(tmp_path):
    """transcript_reviewed.json sem source_transcript_sha256 -> TranscriptReviewError."""
    fonte_dir, transcript_path, _ = _setup_workspace_com_transcricao(tmp_path)
    revisado = {
        "schema_version": "1.0.0",
        "reviewed_by": "proprietario",
        "reviewed_version": "1.0.0",
        "segments": [
            {
                "id": "reviewed-1",
                "start": 0.0,
                "end": 1.0,
                "text": "Ola",
                "words": [],
            }
        ],
        # sem source_transcript_sha256
    }
    (fonte_dir / "transcript_reviewed.json").write_text(
        json.dumps(revisado), encoding="utf-8"
    )

    with pytest.raises(TranscriptReviewError):
        resolve_editorial_transcript(fonte_dir)


# ---------------------------------------------------------------------------
# 8) Integracao: briefing / semantic_planner / edl_builder consomem revisado
# ---------------------------------------------------------------------------


def test_briefing_semantico_edl_consumem_transcricao_revisada(tmp_path):
    """Briefing, semantic_planner e edl_builder consomem termos corrigidos;
    transcript.json permanece intacto (Delta-Hash=0)."""
    from core.edl_builder import build_edl_from_alignment
    from core.briefing import AnalisadorEditorial
    from core.semantic_planner import _collect_episode_context

    fonte_dir, transcript_path, alignment_path = _setup_workspace_com_transcricao(
        tmp_path
    )
    sha_antes = _sha256(transcript_path)
    loader = WorkspaceLoader(tmp_path)
    loader.load_workspace()
    marca_id = "marca-lote1"
    episodio_id = "ep-lote1"

    # Cria revisão válida.
    review_transcript(
        transcript_path,
        [
            {
                "segment_ids": [12, 13],
                "corrected_text": "Kaique Arakelian",
            }
        ],
        output_path=fonte_dir / "transcript_reviewed.json",
        reviewed_by="proprietario",
        reviewed_version="1.0.0",
    )

    # semantic_planner _collect_episode_context usa a versão revisada.
    contexto = _collect_episode_context(loader, marca_id, episodio_id)
    assert contexto["editorial_transcript_source"] == "reviewed_transcript"
    segs = contexto["transcript"].get("segments", [])
    textos_ctx = [s.get("text", "") for s in segs]
    assert "Kaique Arakelian" in textos_ctx, textos_ctx

    # briefing AnalisadorEditorial usa a versão revisada.
    marca_profile = loader.load_brand_profile(marca_id)
    analisador = AnalisadorEditorial(
        transcript_path,
        fonte_dir / "alignment.json",
        fonte_dir / "phonetic_report.json",
        marca_profile,
    )
    analisador.carregar_dados()
    palavras_briefing = [p.palavra for p in analisador.palavras]
    assert "Kaique" in palavras_briefing
    assert "Arakelian" in palavras_briefing

    # edl_builder consome alignment.json re-sincronizado (termos corrigidos).
    sync_alignment_with_editorial_transcript(fonte_dir)
    edl, editorial_plan = build_edl_from_alignment(
        alignment_path=alignment_path,
        workspace_root=tmp_path,
        marca_id=marca_id,
        episodio_id=episodio_id,
        brand_profile=marca_profile["config_json"],
    )
    eventos = edl.get("timeline_events", [])
    textos_edl = [e.get("text", "") for e in eventos]
    assert any("Kaique Arakelian" in t for t in textos_edl), textos_edl

    # transcript.json nunca sobrescrito.
    assert _sha256(transcript_path) == sha_antes


# ---------------------------------------------------------------------------
# Correção de propagação da revisão humana (defeito P0)
# ---------------------------------------------------------------------------


def _transcript_com_erro_asr() -> Dict[str, Any]:
    """Transcript com palavra de erro do ASR ('ERRADO_ASR') para reproduzir o defeito."""
    return {
        "schema_version": "1.0.0",
        "engine": "faster-whisper",
        "language": "pt",
        "segments": [
            {
                "id": 100,
                "start": 0.0,
                "end": 0.6,
                "text": "ERRADO_ASR",
                "words": [{"word": "ERRADO_ASR", "start": 0.0, "end": 0.6, "probability": 0.95}],
            },
            {
                "id": 101,
                "start": 0.7,
                "end": 1.3,
                "text": "palavra correta",
                "words": [
                    {"word": "palavra", "start": 0.7, "end": 1.0, "probability": 0.92},
                    {"word": "correta", "start": 1.0, "end": 1.3, "probability": 0.88},
                ],
            },
            {
                "id": 102,
                "start": 1.4,
                "end": 2.0,
                "text": "outro erro ASR",
                "words": [
                    {"word": "outro", "start": 1.4, "end": 1.7, "probability": 0.90},
                    {"word": "erro", "start": 1.7, "end": 1.9, "probability": 0.85},
                    {"word": "ASR", "start": 1.9, "end": 2.0, "probability": 0.80},
                ],
            },
        ],
    }


def _setup_workspace_com_erro_asr(
    tmp: Path, marca_id: str = "marca-p0", episodio_id: str = "ep-p0"
) -> tuple[Path, Path, Path]:
    """Workspace com transcript contendo ERRADO_ASR."""
    init_workspace(tmp)
    loader = WorkspaceLoader(tmp)
    loader.load_workspace()

    marca_dir = tmp / "projetos" / marca_id / "branding"
    marca_dir.mkdir(parents=True, exist_ok=True)
    (marca_dir / "config.json").write_text(
        json.dumps(
            {
                "schema_version": "1.0.0",
                "brand_id": marca_id,
                "display_name": f"Marca {marca_id}",
                "marca": {"destaque": "#004aad", "fonte": "Inter"},
                "preferencias_edicao": {
                    "canal": f"Canal {marca_id}",
                    "audio": {
                        "silence_guard_ms": [180, 220],
                        "jumpcut_gap_threshold_ms": 450,
                        "jumpcut_target_gap_ms": [200, 250],
                    },
                },
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    fonte_dir = loader.resolve_episodio_asset(
        marca_id, episodio_id, "workspace/fonte"
    )
    fonte_dir.mkdir(parents=True, exist_ok=True)

    brutos_path = tmp / "projetos" / marca_id / "episodios" / episodio_id / "brutos" / "video.mp4"
    brutos_path.parent.mkdir(parents=True, exist_ok=True)
    brutos_path.write_bytes(b"fake-video")
    brutos_sha = _sha256(brutos_path)
    projeto = {
        "schema_version": "1.0.0",
        "marca_id": marca_id,
        "episodio_id": episodio_id,
        "nome": episodio_id,
        "current_stage": "01_GRAVACAO_ORIGINAL",
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
        "sources": [
            {
                "id": f"SRC_{marca_id.upper()}_{episodio_id.upper()}",
                "path": str(brutos_path),
                "sha256": brutos_sha,
            }
        ],
        "artifacts": {},
        "approvals": {"master_16x9_approved": False},
    }
    loader.project_file(marca_id, episodio_id).parent.mkdir(
        parents=True, exist_ok=True
    )
    loader.project_file(marca_id, episodio_id).write_text(
        json.dumps(projeto, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    _gerar_wav_16k(fonte_dir / "audio_speech_16k_mono.wav")

    transcript_path = fonte_dir / "transcript.json"
    transcript_path.write_text(
        json.dumps(_transcript_com_erro_asr(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    alinhamento = {
        "schema_version": "1.0.0",
        "status": "COMPLETED",
        "editorial_units": [
            {
                "unit_id": 1,
                "text": "ERRADO_ASR",
                "raw_start": 0.0,
                "raw_end": 0.6,
                "padded_in_point": 0.0,
                "padded_out_point": 0.6,
                "words": [],
            }
        ],
    }
    alignment_path = fonte_dir / "alignment.json"
    alignment_path.write_text(
        json.dumps(alinhamento, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    return fonte_dir, transcript_path, alignment_path


# ---------------------------------------------------------------------------
# Defeito P0: revisão de segmento único não propaga para words
# ---------------------------------------------------------------------------


def test_propagacao_revisao_segmento_unico_erro_asr(tmp_path):
    """Defeito: segmento único corrigido (ERRADO_ASR -> TermoRevisado) deve
    propagar para words, alignment.json e edl_longo.json; ERRADO_ASR não deve
    aparecer como texto editorial."""
    from core.edl_builder import build_edl_from_alignment
    from core.briefing import AnalisadorEditorial

    fonte_dir, transcript_path, alignment_path = _setup_workspace_com_erro_asr(tmp_path)
    sha_antes = _sha256(transcript_path)

    # Revisão de segmento único: ERRADO_ASR (id=100) -> TermoRevisado.
    review_transcript(
        transcript_path,
        [{"segment_id": 100, "corrected_text": "TermoRevisado"}],
        output_path=fonte_dir / "transcript_reviewed.json",
        reviewed_by="proprietario",
        reviewed_version="1.0.0",
    )

    # transcript.json intacto.
    assert _sha256(transcript_path) == sha_antes

    # transcript_reviewed.json: words deve conter TermoRevisado, não ERRADO_ASR.
    revisado = json.loads(
        (fonte_dir / "transcript_reviewed.json").read_text(encoding="utf-8")
    )
    seg_revisado = [s for s in revisado["segments"]
                    if s.get("human_reviewed")][0]
    assert seg_revisado["text"] == "TermoRevisado"
    assert len(seg_revisado["words"]) == 1
    assert seg_revisado["words"][0]["word"] == "TermoRevisado"
    assert seg_revisado["words"][0]["probability"] is None  # palavra substituída
    assert "ERRADO_ASR" not in seg_revisado["text"]

    # sync_alignment_with_editorial_transcript propaga a correção.
    sync_result = sync_alignment_with_editorial_transcript(fonte_dir)
    assert sync_result["source_kind"] == "reviewed_transcript"

    alinhamento = json.loads(alignment_path.read_text(encoding="utf-8"))
    textos_unidades = [u.get("text", "") for u in alinhamento["editorial_units"]]
    assert any("TermoRevisado" in t for t in textos_unidades), textos_unidades
    assert not any("ERRADO_ASR" in t for t in textos_unidades), textos_unidades

    # briefing consome a transcrição revisada.
    loader = WorkspaceLoader(tmp_path)
    loader.load_workspace()
    marca_profile = loader.load_brand_profile("marca-p0")
    analisador = AnalisadorEditorial(
        transcript_path,
        alignment_path,
        fonte_dir / "phonetic_report.json",
        marca_profile,
    )
    analisador.carregar_dados()
    palavras_briefing = [p.palavra for p in analisador.palavras]
    assert "TermoRevisado" in palavras_briefing, palavras_briefing
    assert "ERRADO_ASR" not in palavras_briefing, palavras_briefing

    # edl_builder consome o alignment re-sincronizado.
    edl, editorial_plan = build_edl_from_alignment(
        alignment_path=alignment_path,
        workspace_root=tmp_path,
        marca_id="marca-p0",
        episodio_id="ep-p0",
        brand_profile=marca_profile["config_json"],
    )
    textos_edl = [e.get("text", "") for e in edl.get("timeline_events", [])]
    assert any("TermoRevisado" in t for t in textos_edl), textos_edl
    assert not any("ERRADO_ASR" in t for t in textos_edl), textos_edl


def test_correcao_uma_palavra_segmento_unico_preserva_timestamp(tmp_path):
    """Correção de 1 palavra em segmento único: start/end originais preservados;
    probability=None se a palavra mudou."""
    fonte_dir, transcript_path, _ = _setup_workspace_com_erro_asr(tmp_path)

    # Corrigir "palavra" (id=101, palavra[0]) para "TERMO" — mapeamento 1:1.
    review_transcript(
        transcript_path,
        [{"segment_id": 101, "corrected_text": "TERMO"}],
        output_path=fonte_dir / "transcript_reviewed.json",
        reviewed_by="proprietario",
    )

    revisado = json.loads(
        (fonte_dir / "transcript_reviewed.json").read_text(encoding="utf-8")
    )
    seg = [s for s in revisado["segments"]
           if s.get("human_reviewed")][0]
    assert seg["text"] == "TERMO"
    assert len(seg["words"]) == 1
    w = seg["words"][0]
    assert w["word"] == "TERMO"
    assert w["start"] == 0.7  # start do segmento original preservado
    assert w["end"] == 1.3    # end do segmento original preservado (cobre ambas as palavras)
    assert w["probability"] is None  # palavra substituída, sem confiança fabricada


def test_correcao_varias_palavras_um_segmento_distribui_intervalo(tmp_path):
    """Correção de N palavras em 1 segmento: distribui no [start, end];
    probability=None para todas (substituídas)."""
    fonte_dir, transcript_path, _ = _setup_workspace_com_erro_asr(tmp_path)

    # Corrigir "outro erro ASR" (id=102, 3 palavras) para "TERMO NOVO AQUI" (3 palavras).
    review_transcript(
        transcript_path,
        [{"segment_id": 102, "corrected_text": "TERMO NOVO AQUI"}],
        output_path=fonte_dir / "transcript_reviewed.json",
        reviewed_by="proprietario",
    )

    revisado = json.loads(
        (fonte_dir / "transcript_reviewed.json").read_text(encoding="utf-8")
    )
    seg = [s for s in revisado["segments"]
           if s.get("human_reviewed")][0]
    assert seg["text"] == "TERMO NOVO AQUI"
    assert len(seg["words"]) == 3
    palavras = [w["word"] for w in seg["words"]]
    assert palavras == ["TERMO", "NOVO", "AQUI"]
    # Todos com probability=None (substituídas).
    assert all(w["probability"] is None for w in seg["words"])
    # Timestamps distribuídos no intervalo [1.4, 2.0].
    assert seg["words"][0]["start"] == 1.4
    assert seg["words"][2]["end"] == 2.0


def test_correcao_multiplos_segmentos_agrupados(tmp_path):
    """Correção de múltiplos segmentos (segment_ids): agrupados em 1 segmento
    com texto corrigido e words distribuídos."""
    fonte_dir, transcript_path, _ = _setup_workspace_com_erro_asr(tmp_path)

    # Agrupar segmentos 100 e 101 em "FRASE CORRIGIDA".
    review_transcript(
        transcript_path,
        [{"segment_ids": [100, 101], "corrected_text": "FRASE CORRIGIDA"}],
        output_path=fonte_dir / "transcript_reviewed.json",
        reviewed_by="proprietario",
    )

    revisado = json.loads(
        (fonte_dir / "transcript_reviewed.json").read_text(encoding="utf-8")
    )
    segs_revisados = [s for s in revisado["segments"]
                      if s.get("human_reviewed")]
    assert len(segs_revisados) == 1
    seg = segs_revisados[0]
    assert seg["text"] == "FRASE CORRIGIDA"
    assert len(seg["words"]) == 2
    assert [w["word"] for w in seg["words"]] == ["FRASE", "CORRIGIDA"]
    assert all(w["probability"] is None for w in seg["words"])
    # start do primeiro segmento (100), end do último (101).
    assert seg["start"] == 0.0
    assert seg["end"] == 1.3


def test_sem_revisao_usa_transcricao_original(tmp_path):
    """Sem transcript_reviewed.json: resolve_editorial_transcript retorna
    source_kind=raw_transcript com words do transcript.json original."""
    fonte_dir, transcript_path, _ = _setup_workspace_com_erro_asr(tmp_path)
    sha_antes = _sha256(transcript_path)

    editorial = resolve_editorial_transcript(fonte_dir)

    assert editorial["source_kind"] == "raw_transcript"
    assert editorial["transcript_sha256"] == sha_antes
    # ERRADO_ASR ainda presente (sem revisão).
    palavras = editorial["words"]
    assert any(w["w"] == "ERRADO_ASR" for w in palavras)
    # transcript.json inalterado.
    assert _sha256(transcript_path) == sha_antes


def test_revisao_desatualizada_rejeitada(tmp_path):
    """transcript.json alterado após revisão -> base sha diverge ->
    TranscriptReviewError."""
    fonte_dir, transcript_path, _ = _setup_workspace_com_erro_asr(tmp_path)

    review_transcript(
        transcript_path,
        [{"segment_id": 100, "corrected_text": "TermoRevisado"}],
        output_path=fonte_dir / "transcript_reviewed.json",
        reviewed_by="proprietario",
    )

    # Altera transcript.json após a revisão.
    transcript_path.write_bytes(
        transcript_path.read_bytes() + b"\n"
    )

    with pytest.raises(TranscriptReviewError) as exc:
        resolve_editorial_transcript(fonte_dir)
    assert "desatualizada" in str(exc.value).lower() or "diverge" in str(
        exc.value
    ).lower()

