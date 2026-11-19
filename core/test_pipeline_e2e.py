# -*- coding: utf-8 -*-
"""core/test_pipeline_e2e.py

Prova ponta a ponta (L1..L6) do pipeline audiovisual local do Editor.

Tudo roda em `tmp_path`/`tmp_path_factory` (nenhum arquivo do repositorio e
alterado), de forma determinística e offline:

    01_INGEST -> 02_ANALYZE -> 03_SEMANTIC -> 03_BRIEFING -> 03_EDL
    -> 03_LINT -> 04_RENDER (L1..L6) -> 04_QA -> traceability_report.json

Cenarios negativos cobertos (14):
     1. brutos alterado apos a ingestao (Delta-Hash != 0)
     2. path traversal em slugs de marca/episodio
     3. componente de motion inexistente no semantic_plan
     4. sem consentimento -> fallback local, provedor NAO e chamado
     5. timestamp inventado alem da duracao do audio
     6. colisao L5 x L2 bloqueada pelo MasterLint
     7. colisao L5 x L4 bloqueada pelo MasterLint
     8. evento fora de [0, final_duration]
     9. media_ref de B-roll com traversal: isolado, sem vazamento
    10. SFX ausente/corrompido: isolado, sem derrubar a fala
    11. L6 duplicado no mesmo timestamp: apenas 1 mixado
    12. render com plano reprovado no lint -> EdlRenderError
    13. Delta-Hash = 0 para video bruto, B-roll e WAVs
    14. video_verify rejeita master sem audio / duracao errada / sample rate errado
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import os
import struct
import subprocess
import sys
import wave
from pathlib import Path
from typing import Any, Dict, List

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image, ImageDraw  # noqa: E402

from core.edl_renderer import EdlRenderError, render_edl_to_video  # noqa: E402
from core.ingest import IngestError, verify_source_integrity  # noqa: E402
from core.master_lint import (  # noqa: E402
    check_colisao_cross_layer_critica,
    check_eventos_fora_timeline,
    lint as lint_plan,
)
from core.pipeline import (  # noqa: E402
    expected_render_duration,
    run_episode_pipeline,
)
from core.semantic_plan import (  # noqa: E402
    SemanticPlanError,
    validate_semantic_plan,
)
from core.semantic_planner import (  # noqa: E402
    CallableMockProvider,
    SemanticConsent,
    plan_episodio_semantics,
)
from core.video_verify import measure_astats, verify_video_av  # noqa: E402
from core.workspace import WorkspaceLoader, WorkspaceError, init_workspace  # noqa: E402

import importlib.util  # noqa: E402

_REPO = Path(__file__).resolve().parent.parent
_BROLL_DIR = _REPO / "motion_library" / "components" / "broll_industrial"
_SOUND_DIR = _REPO / "motion_library" / "components" / "sound_design_sync"


def _load_local_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


broll_industrial = _load_local_module("ml_broll_industrial", _BROLL_DIR / "broll_industrial.py")
sound_design_sync = _load_local_module("ml_sound_design_sync", _SOUND_DIR / "sound_design_sync.py")


# ---------------------------------------------------------------------------
# Fixture sintetica (sem marca real, sem IA, sem rede)
# ---------------------------------------------------------------------------

MARCA = "marca-sintetica"
EPISODIO = "ep-pipeline"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _ffmpeg(cmd: List[str]) -> None:
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"ffmpeg falhou: {' '.join(cmd)}\n{res.stderr[-1500:]}")


def _make_background(path: Path, variant: int = 0) -> None:
    """Fundo estatico de alto contraste (difere de testsrc2: sem ruido temporal)."""
    img = Image.new("RGB", (1920, 1080), (30, 60, 150) if variant == 0 else (200, 120, 20))
    draw = ImageDraw.Draw(img)
    for x in range(0, 1920, 120):
        for y in range(0, 1080, 120):
            if (x // 120 + y // 120) % 2 == 0:
                draw.rectangle(
                    [x, y, x + 119, y + 119],
                    fill=(240, 240, 240) if variant == 0 else (20, 20, 20),
                )
    for i in range(0, 1920, 200):
        draw.line([(i, 0), (i, 1080)], fill=(255, 230, 0), width=5)
    for j in range(0, 1080, 200):
        draw.line([(0, j), (1920, j)], fill=(0, 255, 200), width=5)
    draw.text((120, 120), f"FONTE {variant}", fill=(255, 0, 0))
    img.save(path)


def _make_wav(path: Path, freq: float, duration: float = 0.6, amp: float = 0.9) -> None:
    rate = 48000
    n = int(rate * duration)
    pcm = b"".join(
        struct.pack("<h", int(32767 * amp * math.sin(2 * math.pi * freq * i / rate)))
        for i in range(n)
    )
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(b"".join(pcm[i : i + 2] * 2 for i in range(0, len(pcm), 2)))


def _build_workspace(root: Path) -> Path:
    """Cria workspace.json, marca sintetica, midia de origem e assets do episodio."""
    init_workspace(root, custody={"originals_read_only": False})

    brand_dir = root / "projetos" / MARCA / "branding"
    brand_dir.mkdir(parents=True, exist_ok=True)
    (brand_dir / "config.json").write_text(
        json.dumps(
            {
                "rosto": [980, 420],
                "marca": {
                    "destaque": "#004aad",
                    "secundaria": "#8e7de5",
                    "ciano": "#2f97d4",
                    "fonte": "Inter",
                },
                "preferencias_edicao": {
                    "canal": "Canal Sintetico",
                    "apresentador": "Tester Silva",
                    "credencial_oficial": "Especialista",
                    "audio": {
                        "clean_profile": "vehicular_clean",
                        "hpf_hz": 80,
                        "silence_guard_ms": [180, 220],
                        "jumpcut_gap_threshold_ms": 450,
                        "jumpcut_target_gap_ms": [200, 250],
                    },
                    "render_defaults": {
                        "master_16x9": {"width": 1920, "height": 1080, "fps": 30}
                    },
                },
                "visual": {
                    "palette": {
                        "primary": "#004aad",
                        "secondary": "#8e7de5",
                        "accent_cyan": "#2f97d4",
                        "bg_dark": "#0b1020",
                        "text_primary": "#ffffff",
                    },
                    "safe_zones": {
                        "master_16x9": {
                            "card_left": [100, 180],
                            "card_right": [1220, 180],
                            "lower_third_max_w": 1150,
                        }
                    },
                },
                "assets": {"sfx_map": {}},
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    incoming = root / "incoming"
    incoming.mkdir(parents=True, exist_ok=True)
    background = incoming / "bg.png"
    _make_background(background, 0)
    source = incoming / "source.mp4"
    _ffmpeg(
        [
            "ffmpeg", "-y", "-loop", "1", "-i", str(background),
            "-f", "lavfi", "-i", "sine=frequency=220:sample_rate=48000:duration=12",
            "-t", "12", "-r", "30",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "24", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
            str(source),
        ]
    )

    fonte = root / "projetos" / MARCA / "episodios" / EPISODIO / "workspace" / "fonte"
    fonte.mkdir(parents=True, exist_ok=True)
    _make_background(fonte / "broll.png", 1)
    _make_wav(fonte / "s1.wav", 1000.0)
    _make_wav(fonte / "s2.wav", 1500.0)
    return source


def _build_transcription() -> List[Dict[str, Any]]:
    """36 palavras sinteticas: 20 (0.0..5.665), pausa, 16 (6.8..11.325)."""
    words: List[Dict[str, Any]] = []
    for i in range(20):
        t = round(0.0 + i * 0.285, 3)
        words.append({"w": f"palavra{i + 1}", "t": t, "f": round(t + 0.25, 3), "probability": 0.98})
    for i in range(16):
        t = round(6.8 + i * 0.285, 3)
        words.append({"w": f"termo{i + 1}", "t": t, "f": round(t + 0.25, 3), "probability": 0.97})
    return words


# ---------------------------------------------------------------------------
# Modalidade B: fala pt-BR real (SAPI) + faster-whisper LOCAL offline
# ---------------------------------------------------------------------------

_SNAPSHOT_ENV = "EDITOR_WHISPER_MODEL_PATH"
_SNAPSHOT_WHISPER = Path(
    os.environ.get(_SNAPSHOT_ENV)
    or (
        r"D:\Backup\HuggingFace\local-appdata\hub"
        r"\models--mobiuslabsgmbh--faster-whisper-large-v3-turbo"
        r"\snapshots\0a363e9161cbc7ed1431c9597a8ceaf0c4f78fcf"
    )
)

_TEXTO_FALA_PTBR = (
    "Olá. Este é um teste de transcrição local do editor de pós-produção. "
    "O pipeline precisa reconhecer palavras, identificar pausas e gerar um "
    "alinhamento temporal confiável. No final, o sistema valida as camadas "
    "visuais e a qualidade do áudio do vídeo renderizado."
)


def _snapshot_whisper_local():
    p = Path(os.environ.get(_SNAPSHOT_ENV) or _SNAPSHOT_WHISPER)
    return p if (p / "model.bin").is_file() else None


def _sintetizar_fala_ptbr(destino: Path, texto: str) -> bool:
    """Gera fala pt-BR com Windows SAPI (nenhuma instalacao/rede)."""
    if os.name != "nt":
        return False
    destino.parent.mkdir(parents=True, exist_ok=True)
    texto_path = destino.with_suffix(".txt")
    texto_path.write_text(texto, encoding="utf-8")
    script = destino.with_suffix(".ps1")
    script.write_text(
        "Add-Type -AssemblyName System.Speech\n"
        "$ErrorActionPreference = 'Stop'\n"
        "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer\n"
        "$v = $s.GetInstalledVoices() | Where-Object { "
        "$_.Enabled -and $_.VoiceInfo.Culture.Name -eq 'pt-BR' } | Select-Object -First 1\n"
        "if (-not $v) { $s.Dispose(); exit 3 }\n"
        "$s.SelectVoice($v.VoiceInfo.Name)\n"
        "$s.Rate = 1\n"
        f"$s.SetOutputToWaveFile('{destino.as_posix()}')\n"
        "$texto = [System.IO.File]::ReadAllText("
        f"'{texto_path.as_posix()}', [System.Text.Encoding]::UTF8)\n"
        "$s.Speak($texto)\n"
        "$s.Dispose()\n",
        encoding="utf-8-sig",
    )
    try:
        proc = subprocess.run(
            [
                "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                "-File", str(script),
            ],
            capture_output=True,
            text=True,
            timeout=180,
        )
    except Exception:
        return False
    return proc.returncode == 0 and destino.is_file() and destino.stat().st_size > 0


def _fala_ptbr_16k(destino: Path) -> Path | None:
    bruta = destino.with_suffix(".wav")
    if not _sintetizar_fala_ptbr(bruta, _TEXTO_FALA_PTBR):
        return None
    convertida = destino.with_name(destino.stem + "_16k.wav")
    _ffmpeg(
        [
            "ffmpeg", "-y", "-loglevel", "error", "-i", str(bruta),
            "-ar", "16000", "-ac", "1", str(convertida),
        ]
    )
    return convertida


def _rebuild_source_with_speech(source: Path, background: Path, fala: Path) -> None:
    """Reescreve source.mp4 com a fala real, mantendo fundo/1080p/30fps."""
    _ffmpeg(
        [
            "ffmpeg", "-y", "-loop", "1", "-i", str(background), "-i", str(fala),
            "-t", "16", "-r", "30",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "24", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
            str(source),
        ]
    )


def _build_semantic_plan_from_transcript(context: Dict[str, Any]) -> Dict[str, Any]:
    """Plano deterministico dimensionado pela transcricao local real.

    Todas as janelas sao ancoradas nos timestamps reais (sem inventar tempo)
    e respeitam as duracoes minimas do MasterLint.
    """
    transcript = context.get("transcript") or {}
    segments = transcript.get("segments") or []
    if not segments:
        raise AssertionError("transcricao local vazia: impossivel planejar sem palavras")

    ids = [s.get("id") for s in segments if "id" in s]
    primeiro_id = min(ids) if ids else 0
    fim = max(float(s.get("end", 0.0)) for s in segments)
    assert fim >= 10.5, f"fala curta demais para as 6 camadas (fim={fim:.3f}s)"

    l2_in = 0.0
    l2_out = min(fim * 0.20, 3.0)
    l3_in = min(fim * 0.24, l2_out + 0.15)
    l3_out = min(fim * 0.36, l3_in + 2.0)
    l4_in = min(fim * 0.40, l3_out + 0.15)
    l4_out = min(fim * 0.70, l4_in + 4.0)
    l5_in = min(fim * 0.75, l4_out + 0.15)
    l5_out = min(fim * 0.97, l5_in + 4.0)

    def _r(x: float) -> float:
        return round(max(0.0, x), 3)

    return {
        "schema_version": "1.0.0",
        "tema_central": "Prova integrada com transcricao local real.",
        "tese_principal": "A fala real transcrita offline sustenta L1..L6 com QA.",
        "gerado_em": "2026-01-01T00:00:00+00:00",
        "provedor": "callable_mock",
        "autorizado": True,
        "topicos": [
            {
                "topic_id": "T1",
                "titulo": "Bloco unico",
                "justificativa": "Cobertura integral da transcricao local.",
                "raw_start": 0.0,
                "raw_end": _r(fim),
                "segment_ids": [primeiro_id],
            }
        ],
        "argumentos": [],
        "grupos_explicacao": [],
        "ganchos_e_viradas": [],
        "repeticoes_dispensaveis": [],
        "falsos_comecos": [],
        "segmentos_editoriais": [
            {
                "decision": "preservar",
                "topic_id": "T1",
                "justificativa": "Preservar a fala real transcrita.",
                "raw_start": 0.0,
                "raw_end": _r(fim),
                "segment_ids": [primeiro_id],
            }
        ],
        "intencoes_visuais": [
            {
                "camada": "L2_titulo_heroi_t10",
                "funcao_editorial": "Abertura",
                "justificativa": "Titulo ancorado no inicio da fala real.",
                "componente_motion_library": "titulo_heroi",
                "texto": "MASTER LOCAL",
                "raw_start": _r(l2_in),
                "raw_end": _r(l2_out),
                "segment_ids": [primeiro_id],
            },
            {
                "camada": "L3_micro_zoom_bate",
                "funcao_editorial": "Enfase",
                "justificativa": "Micro zoom em trecho transcrito.",
                "componente_motion_library": "micro_zoom_bate",
                "raw_start": _r(l3_in),
                "raw_end": _r(l3_out),
                "segment_ids": [primeiro_id],
            },
            {
                "camada": "L4_lower_third",
                "funcao_editorial": "Credencial",
                "justificativa": "Lower third com o apresentador sintetico.",
                "componente_motion_library": "lower_third",
                "texto": "Tester Silva",
                "raw_start": _r(l4_in),
                "raw_end": _r(l4_out),
                "segment_ids": [primeiro_id],
            },
            {
                "camada": "L5_broll_industrial",
                "funcao_editorial": "B-roll",
                "justificativa": "B-roll sintetico na parte final da fala.",
                "componente_motion_library": "broll_industrial",
                "media_ref": "broll.png",
                "raw_start": _r(l5_in),
                "raw_end": _r(l5_out),
                "segment_ids": [primeiro_id],
            },
            {
                "camada": "L6_sound_design_sync",
                "funcao_editorial": "SFX abertura",
                "justificativa": "Efeito sincronizado a abertura.",
                "componente_motion_library": "sound_design_sync",
                "sound_ref": "s1.wav",
                "volume": 0.9,
                "raw_start": _r(fim * 0.03),
                "raw_end": _r(fim * 0.07),
                "segment_ids": [primeiro_id],
            },
            {
                "camada": "L6_sound_design_sync",
                "funcao_editorial": "SFX credencial",
                "justificativa": "Efeito sincronizado ao lower third.",
                "componente_motion_library": "sound_design_sync",
                "sound_ref": "s2.wav",
                "volume": 0.9,
                "raw_start": _r(fim * 0.41),
                "raw_end": _r(fim * 0.45),
                "segment_ids": [primeiro_id],
            },
        ],
    }


def _build_semantic_plan(context: Dict[str, Any]) -> Dict[str, Any]:
    """Plano semantico deterministico, com as 5 camadas implementadas (L2..L6)."""
    return {
        "schema_version": "1.0.0",
        "tema_central": "Teste deterministico do pipeline audiovisual.",
        "tese_principal": "Um master local deve comprovar L1..L6 com QA mensuravel.",
        "gerado_em": "2026-01-01T00:00:00+00:00",
        "provedor": "callable_mock",
        "autorizado": True,
        "topicos": [
            {
                "topic_id": "T1",
                "titulo": "Bloco unico",
                "justificativa": "Cobertura textual completa do episodio sintetico.",
                "raw_start": 0.3,
                "raw_end": 11.3,
                "segment_ids": [0, 20],
            }
        ],
        "argumentos": [],
        "grupos_explicacao": [],
        "ganchos_e_viradas": [],
        "repeticoes_dispensaveis": [],
        "falsos_comecos": [],
        "segmentos_editoriais": [
            {
                "decision": "preservar",
                "topic_id": "T1",
                "justificativa": "Preservar todo o conteudo sintetico para o master.",
                "raw_start": 0.3,
                "raw_end": 11.3,
                "segment_ids": [0, 20],
            }
        ],
        "intencoes_visuais": [
            {
                "camada": "L2_titulo_heroi_t10",
                "funcao_editorial": "Abertura",
                "justificativa": "Titulo de abertura ancorado no primeiro segmento.",
                "componente_motion_library": "titulo_heroi",
                "texto": "MASTER L1-L6",
                "raw_start": 0.3,
                "raw_end": 2.5,
                "segment_ids": [0, 1],
            },
            {
                "camada": "L3_micro_zoom_bate",
                "funcao_editorial": "Enfase",
                "justificativa": "Micro zoom para reforcar a transicao do bloco.",
                "componente_motion_library": "micro_zoom_bate",
                "raw_start": 2.6,
                "raw_end": 4.0,
                "segment_ids": [9, 10],
            },
            {
                "camada": "L4_lower_third",
                "funcao_editorial": "Credencial",
                "justificativa": "Lower third com nome e credencial do apresentador.",
                "componente_motion_library": "lower_third",
                "texto": "Tester Silva",
                "raw_start": 4.2,
                "raw_end": 8.085,
                "segment_ids": [15, 20],
            },
            {
                "camada": "L5_broll_industrial",
                "funcao_editorial": "B-roll",
                "justificativa": "B-roll industrial sintetico cobre a segunda metade.",
                "componente_motion_library": "broll_industrial",
                "media_ref": "broll.png",
                "raw_start": 8.285,
                "raw_end": 11.285,
                "segment_ids": [20, 35],
            },
            {
                "camada": "L6_sound_design_sync",
                "funcao_editorial": "SFX abertura",
                "justificativa": "Efeito sonoro sincronizado a abertura.",
                "componente_motion_library": "sound_design_sync",
                "sound_ref": "s1.wav",
                "volume": 0.9,
                "raw_start": 0.4,
                "raw_end": 0.9,
                "segment_ids": [0, 1],
            },
            {
                "camada": "L6_sound_design_sync",
                "funcao_editorial": "SFX credencial",
                "justificativa": "Efeito sonoro sincronizado ao lower third.",
                "componente_motion_library": "sound_design_sync",
                "sound_ref": "s2.wav",
                "volume": 0.9,
                "raw_start": 4.3,
                "raw_end": 4.8,
                "segment_ids": [15, 16],
            },
        ],
    }


def _frame_rgb(path: Path, t: float, out_png: Path, size=(160, 90)) -> List[Any]:
    _ffmpeg(
        [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-ss", f"{t:.3f}", "-i", str(path), "-frames:v", "1", str(out_png),
        ]
    )
    with Image.open(out_png) as im:
        small = im.convert("RGB").resize(size)
        raw = (
            list(small.get_flattened_data())
            if hasattr(small, "get_flattened_data")
            else list(small.getdata())
        )
    if raw and isinstance(raw[0], (int, float)):
        flat = list(raw)
        return [(int(flat[i]), int(flat[i + 1]), int(flat[i + 2])) for i in range(0, len(flat) - 2, 3)]
    return [(int(px[0]), int(px[1]), int(px[2])) for px in raw]


def _mad(a: List[Any], b: List[Any]) -> float:
    if not a or len(a) != len(b):
        return 0.0
    total = sum(
        abs(pa[0] - pb[0]) + abs(pa[1] - pb[1]) + abs(pa[2] - pb[2])
        for pa, pb in zip(a, b)
    )
    return total / (len(a) * 3.0)


# ---------------------------------------------------------------------------
# Fixtures de modulo (pipeline roda uma unica vez)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def env(tmp_path_factory) -> Dict[str, Any]:
    root = tmp_path_factory.mktemp("pipeline_e2e")
    source = _build_workspace(root)

    # Segredo que vive FORA das raizes autorizadas do render.
    secret = root.parent / f"fora_broll_{root.name}.png"
    Image.new("RGB", (48, 48), (255, 0, 255)).save(secret)
    secret_sha = _sha256(secret)

    loader = WorkspaceLoader(root)
    loader.load_workspace()
    brand_profile = loader.load_brand_profile(MARCA)
    fonte = loader.resolve_episodio_asset(MARCA, EPISODIO, "workspace/fonte")
    branding = loader.branding_dir(MARCA)
    ep_dir = loader.episodio_dir(MARCA, EPISODIO)

    broll = fonte / "broll.png"
    s1 = fonte / "s1.wav"
    s2 = fonte / "s2.wav"
    source_sha = _sha256(source)
    asset_hashes = {
        "source": source_sha,
        "broll": _sha256(broll),
        "s1": _sha256(s1),
        "s2": _sha256(s2),
    }

    consent = SemanticConsent(
        destination="mock_local",
        shared_data=["transcript.json"],
        authorized=True,
        notes="Teste deterministico com provedor mock local.",
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

    project = json.loads(loader.project_file(MARCA, EPISODIO).read_text(encoding="utf-8"))
    brutos = Path(project["sources"][0]["path"])

    return {
        "root": root,
        "source": source,
        "secret": secret,
        "secret_sha": secret_sha,
        "brand_profile": brand_profile,
        "fonte": fonte,
        "branding": branding,
        "ep_dir": ep_dir,
        "brutos": brutos,
        "asset_hashes": asset_hashes,
        "result": result,
        "edl": result["edl"],
        "editorial_plan": copy.deepcopy(result["editorial_plan"]),
        "project": project,
        "loader": loader,
    }


@pytest.fixture(scope="module")
def isolation_render(env, tmp_path_factory) -> Dict[str, Any]:
    """Render com B-roll traversal + SFX ausentes: tudo isolado, fala preservada."""
    work = tmp_path_factory.mktemp("pipeline_isolation")
    plan = copy.deepcopy(env["editorial_plan"])

    secret = str(env["secret"].resolve())
    for el in plan["layers"]["L5_broll_industrial"]:
        el["media_ref"] = secret
        el.pop("arquivo", None)
        el.pop("path", None)
    for el in plan["layers"]["L6_sound_design_sync"]:
        el["sound_ref"] = "sfx_inexistente.wav"
        el.pop("sample", None)
        el.pop("media_ref", None)

    out = work / "master_isolado.mp4"
    wd = work / "_work"
    wd.mkdir(parents=True, exist_ok=True)
    report = render_edl_to_video(
        env["edl"],
        plan,
        env["brutos"],
        env["brand_profile"],
        out,
        work_dir=wd,
        authorized_roots=[env["fonte"], env["branding"], env["ep_dir"], wd],
        apply_loudnorm=True,
    )
    return {
        "plan": plan,
        "output": out,
        "work": work,
        "report": report,
        "duration": expected_render_duration(env["edl"]),
    }


# ---------------------------------------------------------------------------
# 0) Prova positiva: L1..L6 em um master real
# ---------------------------------------------------------------------------


def test_01_pipeline_l1_l6_master(env):
    result = env["result"]
    assert result["ok"] is True, result["qa"]["problems"]
    assert result["integrity_delta_hash_zero"] is True

    stages = [s["stage"] for s in result["stages"]]
    assert stages == [
        "01_INGEST",
        "02_ANALYZE",
        "03_SEMANTIC",
        "03_BRIEFING",
        "03_EDL",
        "03_LINT",
        "04_RENDER",
        "04_QA",
    ]

    # --- EDL / duracao ---
    timing = result["edl"]["timeline_events"]
    assert len(timing) >= 2
    render_duration = result["render_expected_duration_seconds"]
    edl_duration = result["edl_final_duration_seconds"]
    assert render_duration > 9.0
    assert edl_duration >= render_duration  # eixo out_* inclui padding

    # --- Plano editorial: 6 camadas, 5 componentes implementados ---
    layers = result["editorial_plan"]["layers"]
    for name in (
        "L1_estabelecimento",
        "L2_titulo_heroi_t10",
        "L3_micro_zoom_bate",
        "L4_lower_third",
        "L5_broll_industrial",
        "L6_sound_design_sync",
    ):
        assert name in layers, f"camada ausente: {name}"
        assert layers[name], f"camada vazia: {name}"

    executed = result["render"]["executed_events"]
    executed_components = {e["component_id"] for e in executed}
    assert executed_components == {
        "titulo_heroi",
        "micro_zoom_bate",
        "lower_third",
        "broll_industrial",
        "sound_design_sync",
    }
    assert result["render"]["isolated_events"] == []

    # --- Master real ---
    master = Path(result["master_path"])
    assert master.is_file() and master.stat().st_size > 0
    assert _sha256(master) == result["master_sha256"]

    # --- QA audiovisual ---
    qa = result["qa"]
    assert qa["ok"] is True, qa["problems"]
    assert qa["loudnorm_count"] == 1, qa["loudnorm_count"]
    assert abs(qa["loudness"]["integrated_lufs"] - (-14.0)) <= 1.5
    assert qa["loudness"]["true_peak_dbtp"] <= -0.8
    assert len(qa["visual_windows"]) >= 4
    for w in qa["visual_windows"]:
        assert w["inside_diff"] > 0.25, w
    assert len(qa["audio_windows"]) >= 2
    for w in qa["audio_windows"]:
        assert w["rms_delta_db"] > 1.0, w

    # --- Lint: nunca aprova automaticamente ---
    assert result["lint"]["ok"] is True
    assert result["lint"]["auto_approved"] is False
    assert result["lint"]["requires_human_approval"] is True

    # --- Rastreabilidade ---
    trace_path = Path(result["traceability_path"])
    assert trace_path.is_file()
    trace = json.loads(trace_path.read_text(encoding="utf-8"))
    assert trace["schema_version"] == "1.0.0"
    assert trace["identification"]["master_sha256"] == result["master_sha256"]
    assert trace["data_origin"]["external_calls"] is False
    assert trace["data_origin"]["deterministic_offline"] is True
    assert trace["data_origin"]["transcription"] == "injected_fixture"
    assert trace["data_origin"]["origins"]["transcription"] == "injected_fixture"
    assert trace["transcription"]["origin"] == "injected_fixture"
    assert trace["transcription"]["local_execution_confirmed"] is False
    assert trace["data_origin"]["semantic_plan"] == "provider"
    assert trace["trace_paths"]
    for path in trace["trace_paths"]:
        assert path["layer"]
        if path["layer"] != "L1_estabelecimento":
            assert path["component"] is not None, path
    assert any(p["segment_ids"] for p in trace["trace_paths"])

    # --- project.json ---
    project = json.loads(
        (Path(result["workspace_root"]) / "projetos" / MARCA / "episodios" / EPISODIO / "project.json")
        .read_text(encoding="utf-8")
    )
    assert project["current_stage"] == "04_RENDER_COMPLETED"
    assert project["approvals"]["master_16x9_approved"] is False
    assert "04_render" in project["artifacts"]


# ---------------------------------------------------------------------------
# 1) Brutros alterado apos a ingestao
# ---------------------------------------------------------------------------


def test_02_brutos_altered_after_ingest_is_rejected(env, tmp_path):
    original = env["brutos"]
    expected_sha = env["asset_hashes"]["source"]
    assert _sha256(original) == expected_sha

    altered = tmp_path / "copia_alterada.mp4"
    altered.write_bytes(original.read_bytes() + b"\x00\x00\x00\x00")

    with pytest.raises(IngestError) as exc:
        verify_source_integrity(altered, expected_sha, original.name)
    assert "INTEGRIDADE COMPROMETIDA" in str(exc.value)


# ---------------------------------------------------------------------------
# 2) Path traversal em slugs
# ---------------------------------------------------------------------------


def test_03_slug_path_traversal_rejected(env):
    loader = WorkspaceLoader(env["root"])
    loader.load_workspace()
    for bad in ("../fora", "..\\fora", "a/../../b", "marca/../x", ""):
        with pytest.raises(WorkspaceError):
            loader.episodio_dir(MARCA, bad)
    with pytest.raises(WorkspaceError):
        loader.load_brand_profile("../fora")

    # Assets: qualquer tentativa de escapar da raiz do workspace e bloqueada.
    ok_asset = loader.resolve_episodio_asset(MARCA, EPISODIO, "workspace/fonte/broll.png")
    assert ok_asset.resolve().relative_to(env["root"].resolve())
    escape = "../../../../../../../../fora_do_workspace.txt"
    with pytest.raises(WorkspaceError):
        loader.resolve_episodio_asset(MARCA, EPISODIO, escape)
    with pytest.raises(WorkspaceError):
        loader.resolve_brand_asset(MARCA, escape)


# ---------------------------------------------------------------------------
# 3) Componente de motion inexistente
# ---------------------------------------------------------------------------


def test_04_unknown_motion_component_rejected():
    transcript = {
        "segments": [
            {
                "id": 0,
                "start": 0.0,
                "end": 2.0,
                "words": [{"word_id": "W1", "start": 0.0, "end": 0.5}],
            }
        ],
        "audio_duration_seconds": 12.0,
    }
    plan = _valid_semantic_plan()
    plan["intencoes_visuais"].append(
        {
            "camada": "L2_titulo_heroi_t10",
            "funcao_editorial": "Abertura",
            "justificativa": "Componente que nao existe no Motion Library.",
            "componente_motion_library": "holograma_quantico",
            "raw_start": 0.0,
            "raw_end": 1.0,
            "segment_ids": [0],
        }
    )
    with pytest.raises(SemanticPlanError) as exc:
        validate_semantic_plan(plan, transcript_data=transcript)
    assert "nao existe no Motion Library" in str(exc.value)


# ---------------------------------------------------------------------------
# 4) Sem consentimento -> fallback local, provedor NAO e chamado
# ---------------------------------------------------------------------------


def test_05_consent_not_granted_uses_fallback_without_provider_call(env):
    calls: List[Dict[str, Any]] = []

    def _must_not_be_called(context: Dict[str, Any]) -> Dict[str, Any]:
        calls.append(context)
        raise AssertionError("provedor externo chamado sem consentimento")

    consent = SemanticConsent(
        destination="mock_externo",
        shared_data=["transcript.json"],
        authorized=False,
        notes="Sem consentimento: deve usar fallback local.",
    )
    result = plan_episodio_semantics(
        marca_id=MARCA,
        episodio_id=EPISODIO,
        workspace_root=env["root"],
        provider=CallableMockProvider(_must_not_be_called),
        authorized=consent.authorized,
        destination=consent.destination,
        shared_data=consent.shared_data,
        consent_notes=consent.notes,
        write_files=False,
    )
    assert calls == [], "nenhum provedor externo pode ser chamado sem consentimento"
    assert result["validated"] is True
    assert result["fallback"] is True
    assert result["provider"] == "fallback_local"
    assert result["consent"]["authorized"] is False
    assert result["plan"]["schema_version"] == "1.0.0"


# ---------------------------------------------------------------------------
# 5) Timestamp inventado alem da duracao do audio
# ---------------------------------------------------------------------------


def test_06_invented_timestamp_beyond_audio_rejected():
    transcript = {"segments": [], "audio_duration_seconds": 12.0}
    plan = _valid_semantic_plan()
    plan["topicos"][0]["raw_end"] = 40.0

    with pytest.raises(SemanticPlanError) as exc:
        validate_semantic_plan(plan, transcript_data=transcript)
    assert "timestamp possivelmente inventado" in str(exc.value)


# ---------------------------------------------------------------------------
# 6/7) Colisoes L5 x L2 e L5 x L4 bloqueadas pelo MasterLint
# ---------------------------------------------------------------------------


def test_07_l5_l2_collision_blocked():
    plan = _minimal_layers_plan(
        l2=[{"element_id": "T1", "out_in": 2.0, "out_out": 4.0}],
        l5=[{"element_id": "B1", "out_in": 1.0, "out_out": 3.0}],
    )
    direct = check_colisao_cross_layer_critica(plan)
    assert any("L2_titulo_heroi_t10" in f for f in direct)
    report = lint_plan(plan)
    assert report["ok"] is False
    assert any("colisao cross-layer critica" in f for f in report["failures"])


def test_08_l5_l4_collision_blocked():
    plan = _minimal_layers_plan(
        l4=[{"element_id": "L1", "out_in": 2.0, "out_out": 4.0}],
        l5=[{"element_id": "B1", "out_in": 1.0, "out_out": 3.0}],
    )
    direct = check_colisao_cross_layer_critica(plan)
    assert any("L4_lower_third" in f for f in direct)
    report = lint_plan(plan)
    assert report["ok"] is False
    assert any("colisao cross-layer critica" in f for f in report["failures"])


# ---------------------------------------------------------------------------
# 8) Evento fora de [0, final_duration]
# ---------------------------------------------------------------------------


def test_09_event_outside_timeline_blocked():
    plan = _minimal_layers_plan(
        l2=[{"element_id": "T1", "out_in": 6.0, "out_out": 7.0}]
    )
    edl = {"summary": {"final_duration_seconds": 5.0}}
    direct = check_eventos_fora_timeline(plan, final_duration=5.0)
    assert any("excede final_duration" in f for f in direct)
    report = lint_plan(plan, edl)
    assert report["ok"] is False
    assert any("excede final_duration" in f for f in report["failures"])

    negative = _minimal_layers_plan(
        l2=[{"element_id": "T2", "out_in": -1.0, "out_out": 1.0}]
    )
    assert any("out_in negativo" in f for f in check_eventos_fora_timeline(negative, 5.0))


# ---------------------------------------------------------------------------
# 9) B-roll com media_ref traversal: isolado, sem vazamento
# ---------------------------------------------------------------------------


def test_10_broll_media_ref_traversal_isolated(env, isolation_render, tmp_path):
    secret = env["secret"]
    assert _sha256(secret) == env["secret_sha"]

    # Resolver: caminho absoluto e relativo fora das raizes -> nao resolvido.
    abs_res = broll_industrial.resolve_broll_asset(
        {"media_ref": str(secret.resolve())}, [env["fonte"]]
    )
    assert abs_res["resolved"] is False
    assert str(secret.resolve()) not in abs_res.get("reason", "")

    rel = os.path.relpath(secret, env["fonte"])
    rel_res = broll_industrial.resolve_broll_asset({"media_ref": rel}, [env["fonte"]])
    assert rel_res["resolved"] is False
    assert str(secret.resolve()) not in rel_res.get("reason", "")

    # Render: o elemento L5 foi isolado, o master existe e o segredo nao foi lido.
    isolated = isolation_render["report"]["isolated_events"]
    assert any(e["component_id"] == "broll_industrial" for e in isolated), isolated
    out = isolation_render["output"]
    assert out.is_file() and out.stat().st_size > 0
    assert _sha256(secret) == env["secret_sha"]

    # Sem B-roll: janela L5 deve ser ~igual ao frame de referencia (sem vazamento).
    ref = _frame_rgb(out, 0.05, tmp_path / "iso_ref.png")
    l5 = _frame_rgb(out, 8.5, tmp_path / "iso_l5.png")
    diff = _mad(ref, l5)
    assert diff < 2.0, f"B-roll com traversal vazou para o master (MAD={diff:.2f})"


# ---------------------------------------------------------------------------
# 10) SFX ausente/corrompido: isolado, sem derrubar a fala
# ---------------------------------------------------------------------------


def test_11_missing_or_corrupt_sfx_isolated_without_dropping_speech(env, isolation_render, tmp_path):
    negative_dir = tmp_path / "sfx_negativos"
    negative_dir.mkdir()

    missing = sound_design_sync.resolve_sound_asset(
        {"sound_ref": "nao_existe.wav", "volume": 0.5}, [negative_dir]
    )
    assert missing["resolved"] is False

    (negative_dir / "vazio.wav").write_bytes(b"")
    empty = sound_design_sync.resolve_sound_asset(
        {"sound_ref": "vazio.wav", "volume": 0.5}, [negative_dir]
    )
    assert empty["resolved"] is False

    (negative_dir / "corrompido.wav").write_bytes(b"RIFF\x00\x00\x00\x00WAVEquebrado")
    corrupt = sound_design_sync.resolve_sound_asset(
        {"sound_ref": "corrompido.wav", "volume": 0.5}, [negative_dir]
    )
    assert corrupt["resolved"] is False

    # Render: cada SFX invalido e isolado individualmente.
    isolated = isolation_render["report"]["isolated_events"]
    sfx_isolated = [e for e in isolated if e["component_id"] == "sound_design_sync"]
    assert len(sfx_isolated) >= 2, isolated
    assert all("reason" in e for e in sfx_isolated)

    # A fala (L1) continua no master, mesmo sem nenhum SFX.
    out = isolation_render["output"]
    verif = isolation_render["report"]["verification"]
    assert verif["ok"] is True, verif["problems"]
    stats = measure_astats(out, start=1.0, duration=0.25)
    assert stats["rms_db"] is not None and stats["rms_db"] > -60.0

    # Grafo de audio sem SFX: base permanece intacta (anull), nada e descartado.
    bd = sound_design_sync.build_sound_mix_ffmpeg_filter(
        "abase", [], "aout", final_duration=10.0
    )
    assert bd["filter_steps"][0] == "[abase]anull[mixed]"


# ---------------------------------------------------------------------------
# 11) L6 duplicado no mesmo timestamp: apenas 1 mixado
# ---------------------------------------------------------------------------


def test_12_duplicate_l6_same_timestamp_single_mix():
    duplicate = {
        "element_id": "SD1",
        "component_id": "sound_design_sync",
        "sound_ref": "s1.wav",
        "origin": "semantic_plan",
        "out_in": 4.3,
        "out_out": 4.8,
    }
    accepted, rejected = sound_design_sync.deduplicate_and_schedule_sfx(
        [dict(duplicate), dict(duplicate)], final_duration=12.0
    )
    assert len(accepted) == 1
    assert len(rejected) == 1

    accepted[0]["input_idx"] = 1
    accepted[0]["duration_s"] = 0.5
    accepted[0]["volume"] = 0.8
    bd = sound_design_sync.build_sound_mix_ffmpeg_filter(
        "abase", accepted, "aout", final_duration=12.0
    )
    graph = "\n".join(bd["filter_steps"])
    assert graph.count("adelay=") == 1
    assert "amix=inputs=1" in graph


# ---------------------------------------------------------------------------
# 12) Render com plano reprovado no lint -> EdlRenderError
# ---------------------------------------------------------------------------


def test_13_render_rejects_lint_failed_plan(env, tmp_path):
    plan = copy.deepcopy(env["editorial_plan"])
    duplicated = copy.deepcopy(plan["layers"]["L2_titulo_heroi_t10"][0])
    duplicated["element_id"] = "DUP-L2"
    duplicated.pop("id", None)
    plan["layers"]["L2_titulo_heroi_t10"].append(duplicated)

    out = tmp_path / "nao_deve_existir.mp4"
    with pytest.raises(EdlRenderError) as exc:
        render_edl_to_video(
            env["edl"],
            plan,
            env["brutos"],
            env["brand_profile"],
            out,
            work_dir=tmp_path,
        )
    assert "Lint falhou" in str(exc.value)
    assert not out.exists()


# ---------------------------------------------------------------------------
# 13) Delta-Hash = 0 para video bruto, B-roll e WAVs
# ---------------------------------------------------------------------------


def test_14_delta_hash_zero_raw_broll_wavs(env):
    result = env["result"]
    assert result["integrity_delta_hash_zero"] is True

    integrity = result["traceability"]["integrity"]["media"]
    assert integrity
    roles = {item["role"] for item in integrity}
    assert {"brutos_copy", "broll_or_image", "sfx_or_audio"} <= roles

    for item in integrity:
        assert item["delta_hash"] == 0, item
        assert item["sha256_before"] == item["sha256_after"], item

    # Verificacao direta por arquivo.
    assert _sha256(env["brutos"]) == env["asset_hashes"]["source"]
    assert _sha256(env["source"]) == env["asset_hashes"]["source"]
    assert _sha256(env["fonte"] / "broll.png") == env["asset_hashes"]["broll"]
    assert _sha256(env["fonte"] / "s1.wav") == env["asset_hashes"]["s1"]
    assert _sha256(env["fonte"] / "s2.wav") == env["asset_hashes"]["s2"]

    for path_str in (env["source"], env["brutos"]):
        assert Path(path_str).resolve().is_file()


# ---------------------------------------------------------------------------
# 14) video_verify rejeita master sem audio / duracao errada / sample rate errado
# ---------------------------------------------------------------------------


def test_15_video_verify_rejects_bad_master(env, tmp_path):
    no_audio = tmp_path / "sem_audio.mp4"
    _ffmpeg(
        [
            "ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=black:s=1920x1080:r=30:d=1",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-t", "1", str(no_audio),
        ]
    )
    rep = verify_video_av(
        no_audio, 1.0, check_black=False, check_loudness=False, check_windows=False
    )
    assert rep["ok"] is False
    assert any("sem stream de audio" in p for p in rep["problems"]), rep["problems"]

    master = Path(env["result"]["master_path"])
    rep = verify_video_av(
        master,
        99.0,
        check_black=False,
        check_loudness=False,
        check_windows=False,
    )
    assert rep["ok"] is False
    assert any("duracao" in p for p in rep["problems"]), rep["problems"]

    wrong_sr = tmp_path / "sample_rate_errado.mp4"
    _ffmpeg(
        [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "color=c=black:s=1920x1080:r=30:d=1",
            "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100:duration=1",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-ar", "44100", "-ac", "2", "-shortest", str(wrong_sr),
        ]
    )
    rep = verify_video_av(
        wrong_sr, 1.0, check_black=False, check_loudness=False, check_windows=False
    )
    assert rep["ok"] is False
    assert any("sample_rate 44100" in p for p in rep["problems"]), rep["problems"]


# ---------------------------------------------------------------------------
# 15) Modalidade B: Whisper local offline (fala pt-BR real + faster-whisper)
# ---------------------------------------------------------------------------


def test_16_pipeline_modalidade_b_whisper_local(tmp_path, monkeypatch):
    """Prova integrada Modalidade B: fala pt-BR real transcrita offline com faster-whisper local."""
    snapshot = _snapshot_whisper_local()
    if snapshot is None:
        pytest.skip("snapshot faster-whisper local nao encontrado (EDITOR_WHISPER_MODEL_PATH)")
    if os.name != "nt":
        pytest.skip("SAPI pt-BR so disponivel no Windows")

    # --- Bloquear qualquer tentativa de rede/download ---
    import urllib.request

    chamadas_rede: List[Tuple[Any, Any]] = []

    def _boom(*args, **kwargs):
        chamadas_rede.append((args, kwargs))
        raise AssertionError("download/rede proibidos em modo offline Modalidade B")

    monkeypatch.setattr(urllib.request, "urlopen", _boom)

    # --- Apontar EDITOR_WHISPER_MODEL_PATH para o snapshot validado ---
    monkeypatch.setenv(_SNAPSHOT_ENV, str(snapshot))

    # --- Sintetizar fala pt-BR localmente (SAPI) ---
    fala_wav = tmp_path / "fala_ptbr.wav"
    assert _sintetizar_fala_ptbr(fala_wav, _TEXTO_FALA_PTBR), "falha na sintese SAPI pt-BR"
    fala_16k = tmp_path / "fala_ptbr_16k.wav"
    _ffmpeg(
        [
            "ffmpeg", "-y", "-loglevel", "error", "-i", str(fala_wav),
            "-ar", "16000", "-ac", "1", str(fala_16k),
        ]
    )

    # --- Workspace sintetico em tmp_path ---
    root = tmp_path / "workspace_b"
    source = _build_workspace(root)

    # --- Substituir source.mp4 por video com fala real pt-BR ---
    background = root / "incoming" / "bg.png"
    _rebuild_source_with_speech(source, background, fala_16k)

    # Hashes de referencia antes do pipeline (origens intocadas)
    fonte = root / "projetos" / MARCA / "episodios" / EPISODIO / "workspace" / "fonte"
    brutos_dir = root / "projetos" / MARCA / "episodios" / EPISODIO / "workspace" / "brutos"
    source_sha_before = _sha256(source)
    broll_sha_before = _sha256(fonte / "broll.png")
    s1_sha_before = _sha256(fonte / "s1.wav")
    s2_sha_before = _sha256(fonte / "s2.wav")

    loader = WorkspaceLoader(root)
    loader.load_workspace()

    # vortex-edicao/transcrever.py e necessario pelo analyze_episodio
    # (reuso do transcritor legado). Symlink dentro do workspace temporario.
    vortex_link = root / "vortex-edicao"
    if not vortex_link.exists():
        vortex_link.symlink_to(_REPO / "vortex-edicao", target_is_directory=True)

    consent = SemanticConsent(
        destination="mock_local",
        shared_data=["transcript.json"],
        authorized=True,
        notes="Modalidade B: transcricao local offline, provedor mock.",
    )

    def _provider_custom(context: Dict[str, Any]) -> Dict[str, Any]:
        """Plano semantic com SFX em posicoes fixas no inicio do audio (fala garantida)."""
        transcript = context.get("transcript") or {}
        segments = transcript.get("segments") or []
        fim = max(float(s.get("end", 0.0)) for s in segments)
        primeiro_id = min([s.get("id") for s in segments if "id" in s] or [0])

        l2_out = min(fim * 0.20, 3.0)
        l3_in = min(fim * 0.24, l2_out + 0.15)
        l3_out = min(fim * 0.36, l3_in + 2.0)
        l4_in = min(fim * 0.40, l3_out + 0.15)
        l4_out = min(fim * 0.70, l4_in + 4.0)
        l5_in = min(fim * 0.75, l4_out + 0.15)
        l5_out = min(fim * 0.97, l5_in + 4.0)

        def _r(x: float) -> float:
            return round(max(0.0, x), 3)

        return {
            "schema_version": "1.0.0",
            "tema_central": "Modalidade B - fala real transcrita offline.",
            "tese_principal": "faster-whisper local sustenta L1..L6 com QA.",
            "gerado_em": "2026-01-01T00:00:00+00:00",
            "provedor": "callable_mock",
            "autorizado": True,
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
                    "raw_start": _r(0.0), "raw_end": _r(l2_out),
                    "segment_ids": [primeiro_id],
                },
                {
                    "camada": "L3_micro_zoom_bate", "funcao_editorial": "Enfase",
                    "justificativa": "Micro zoom em trecho transcrito.",
                    "componente_motion_library": "micro_zoom_bate",
                    "raw_start": _r(l3_in), "raw_end": _r(l3_out),
                    "segment_ids": [primeiro_id],
                },
                {
                    "camada": "L4_lower_third", "funcao_editorial": "Credencial",
                    "justificativa": "Lower third com o apresentador sintetico.",
                    "componente_motion_library": "lower_third", "texto": "Tester Silva",
                    "raw_start": _r(l4_in), "raw_end": _r(l4_out),
                    "segment_ids": [primeiro_id],
                },
                {
                    "camada": "L5_broll_industrial", "funcao_editorial": "B-roll",
                    "justificativa": "B-roll sintetico na parte final da fala.",
                    "componente_motion_library": "broll_industrial",
                    "media_ref": "broll.png",
                    "raw_start": _r(l5_in), "raw_end": _r(l5_out),
                    "segment_ids": [primeiro_id],
                },
                {
                    "camada": "L6_sound_design_sync", "funcao_editorial": "SFX abertura",
                    "justificativa": "Efeito sincronizado a abertura.",
                    "componente_motion_library": "sound_design_sync",
                    "sound_ref": "s1.wav", "volume": 1.0,
                    "raw_start": _r(0.3), "raw_end": _r(0.7),
                    "segment_ids": [primeiro_id],
                },
                {
                    "camada": "L6_sound_design_sync", "funcao_editorial": "SFX credencial",
                    "justificativa": "Efeito sincronizado ao lower third.",
                    "componente_motion_library": "sound_design_sync",
                    "sound_ref": "s2.wav", "volume": 1.0,
                    "raw_start": _r(1.1), "raw_end": _r(1.5),
                    "segment_ids": [primeiro_id],
                },
            ],
        }

    result = run_episode_pipeline(
        root,
        MARCA,
        EPISODIO,
        source_video=source,
        transcricao_injetada=None,
        semantic_provider=CallableMockProvider(_provider_custom),
        consent=consent,
        strict=True,
        whisper_model_path=str(snapshot),
        offline_only=True,
    )

    assert result["ok"] is True, result["qa"]["problems"]

    # --- Delta-Hash = 0 nas midias originais ---
    assert result["integrity_delta_hash_zero"] is True
    assert _sha256(source) == source_sha_before
    assert _sha256(fonte / "broll.png") == broll_sha_before
    assert _sha256(fonte / "s1.wav") == s1_sha_before
    assert _sha256(fonte / "s2.wav") == s2_sha_before

    # --- L1..L6 executadas no mesmo master MP4 ---
    stages = [s["stage"] for s in result["stages"]]
    assert stages == [
        "01_INGEST", "02_ANALYZE", "03_SEMANTIC", "03_BRIEFING",
        "03_EDL", "03_LINT", "04_RENDER", "04_QA",
    ]
    master = Path(result["master_path"])
    assert master.is_file() and master.stat().st_size > 0
    assert _sha256(master) == result["master_sha256"]

    qa = result["qa"]
    assert qa["ok"] is True, qa["problems"]
    assert qa["loudnorm_count"] == 1, qa["loudnorm_count"]

    # Pixels L2/L3/L4/L5
    assert len(qa["visual_windows"]) >= 4
    for w in qa["visual_windows"]:
        assert w["inside_diff"] > 0.25, w

    # astats L6
    assert len(qa["audio_windows"]) >= 1
    for w in qa["audio_windows"]:
        assert w["rms_delta_db"] > 1.0, w

    # ebur128 / loudnorm
    assert abs(qa["loudness"]["integrated_lufs"] - (-14.0)) <= 1.5
    assert qa["loudness"]["true_peak_dbtp"] <= -0.8

    # --- Traceability report ---
    trace_path = Path(result["traceability_path"])
    assert trace_path.is_file()
    trace = json.loads(trace_path.read_text(encoding="utf-8"))
    assert trace["schema_version"] == "1.0.0"
    assert trace["data_origin"]["external_calls"] is False
    assert trace["data_origin"]["deterministic_offline"] is True
    assert trace["data_origin"]["transcription"] == "local_faster_whisper"
    assert trace["data_origin"]["origins"]["transcription"] == "local_faster_whisper"
    assert trace["transcription"]["origin"] == "local_faster_whisper"
    assert trace["transcription"]["local_execution_confirmed"] is True
    assert trace["transcription"]["local_files_only"] is True
    assert trace["transcription"]["offline_only"] is True
    assert trace["transcription"]["model_identifier"] is not None
    assert trace["transcription"]["language"] is not None
    assert trace["transcription"]["duration_seconds"] is not None
    assert trace["transcription"]["analysis_state"] is not None
    assert trace["trace_paths"]

    # NUNCA vazar caminho absoluto do backup no report
    report_text = trace_path.read_text(encoding="utf-8")
    assert "Backup" not in report_text
    assert str(snapshot) not in report_text

    # --- Chamadas de rede devem estar vazias ---
    assert chamadas_rede == [], f"tentativas de rede detectadas: {chamadas_rede}"


# ---------------------------------------------------------------------------
# Helpers de plano
# ---------------------------------------------------------------------------


def _valid_semantic_plan() -> Dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "tema_central": "Tema de teste",
        "tese_principal": "Tese de teste",
        "topicos": [
            {
                "topic_id": "T1",
                "titulo": "Topico",
                "justificativa": "Justificativa do topico.",
                "raw_start": 0.0,
                "raw_end": 2.0,
                "segment_ids": [0],
            }
        ],
        "argumentos": [],
        "grupos_explicacao": [],
        "ganchos_e_viradas": [],
        "repeticoes_dispensaveis": [],
        "falsos_comecos": [],
        "segmentos_editoriais": [
            {
                "decision": "preservar",
                "topic_id": "T1",
                "justificativa": "Preservar o trecho.",
                "raw_start": 0.0,
                "raw_end": 2.0,
                "segment_ids": [0],
            }
        ],
        "intencoes_visuais": [],
    }


def _minimal_layers_plan(**kwargs) -> Dict[str, Any]:
    layers: Dict[str, Any] = {
        "L1_estabelecimento": [],
        "L2_titulo_heroi_t10": [],
        "L3_micro_zoom_bate": [],
        "L4_lower_third": [],
        "L5_broll_industrial": [],
        "L6_sound_design_sync": [],
    }
    mapping = {"l2": "L2_titulo_heroi_t10", "l3": "L3_micro_zoom_bate",
               "l4": "L4_lower_third", "l5": "L5_broll_industrial",
               "l6": "L6_sound_design_sync"}
    for key, elements in kwargs.items():
        layers[mapping[key]] = elements
    return {"schema_version": "1.0.0", "layers": layers}
