# -*- coding: utf-8 -*-
"""core/test_whisper_local.py

Suite dedicada ao faster-whisper LOCAL offline no Editor.

Cobre:
  1. Fala sintetica pt-BR gerada no proprio teste com Windows SAPI
     (System.Speech.Synthesis.SpeechSynthesizer, voz "Microsoft Maria
     Desktop" ou qualquer voz pt-BR instalada) em tmp_path.
  2. Transcricao real offline apontando EDITOR_WHISPER_MODEL_PATH para o
     snapshot validado do faster-whisper (local_files_only=True), provando:
     carregamento local, palavras/timestamps, idioma, metadados e zero
     download/ElevenLabs.
  3. Os 8 cenarios negativos obrigatorios, todos em tmp_path e sem fallback
     silencioso.

Nada e escrito fora de tmp_path; o snapshot e apenas LIDO.
"""

from __future__ import annotations

import json
import math
import os
import struct
import subprocess
import sys
import wave
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, Iterable, List, Tuple

import pytest

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from core.analyze import _carregar_transcrever_modulo  # noqa: E402

SNAPSHOT_ENV = "EDITOR_WHISPER_MODEL_PATH"

# Snapshot validado (referencia de leitura; nunca e copiado/modificado).
_SNAPSHOT_PADRAO = Path(
    os.environ.get(SNAPSHOT_ENV)
    or (
        r"D:\Backup\HuggingFace\local-appdata\hub"
        r"\models--mobiuslabsgmbh--faster-whisper-large-v3-turbo"
        r"\snapshots\0a363e9161cbc7ed1431c9597a8ceaf0c4f78fcf"
    )
)

TEXTO_PTBR = (
    "Olá. Este é um teste de transcrição local do editor de pós-produção. "
    "O pipeline precisa reconhecer palavras, identificar pausas e gerar um "
    "alinhamento temporal confiável. No final, o sistema valida as camadas "
    "visuais e a qualidade do áudio do vídeo renderizado."
)

ARQUIVOS_OBRIGATORIOS = (
    "model.bin",
    "config.json",
    "tokenizer.json",
    "preprocessor_config.json",
    "vocabulary.json",
)


# ---------------------------------------------------------------------------
# Helpers de audio (SAPI + WAV sintetico)
# ---------------------------------------------------------------------------


def _sintetizar_fala_ptbr(destino: Path, texto: str) -> bool:
    """Gera fala pt-BR via SAPI no proprio teste. Retorna False se indisponivel."""
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


def _converter_para_16k_mono(origem: Path, destino: Path) -> None:
    proc = subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error", "-i", str(origem),
            "-ar", "16000", "-ac", "1", str(destino),
        ],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg falhou ao converter 16k mono: {proc.stderr[-800:]}")


def _gerar_wav(
    destino: Path,
    duracao_s: float = 0.8,
    taxa: int = 16000,
    canais: int = 1,
    freq: float = 440.0,
) -> Path:
    """Gera WAV PCM 16-bit sintetico (tom) sem depender de ffmpeg."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    n = int(taxa * duracao_s)
    amostras = []
    for i in range(n):
        valor = int(12000 * math.sin(2 * math.pi * freq * i / taxa))
        amostras.append(struct.pack("<h", valor) * canais)
    with wave.open(str(destino), "wb") as wf:
        wf.setnchannels(canais)
        wf.setsampwidth(2)
        wf.setframerate(taxa)
        wf.writeframes(b"".join(amostras))
    return destino


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def snapshot_local() -> Path:
    p = Path(os.environ.get(SNAPSHOT_ENV) or _SNAPSHOT_PADRAO)
    if not (p / "model.bin").is_file():
        pytest.skip(
            "snapshot faster-whisper local indisponivel; defina "
            f"{SNAPSHOT_ENV} para rodar o teste real offline"
        )
    return p


@pytest.fixture(scope="session")
def fala_ptbr_16k(tmp_path_factory) -> Path:
    base = tmp_path_factory.mktemp("whisper_fala_ptbr")
    bruta = base / "fala_ptbr.wav"
    if not _sintetizar_fala_ptbr(bruta, TEXTO_PTBR):
        pytest.skip(
            "SAPI pt-BR indisponivel (Microsoft Maria Desktop nao instalada); "
            "nao e possivel gerar fala sintetica local"
        )
    destino = base / "fala_ptbr_16k.wav"
    _converter_para_16k_mono(bruta, destino)
    return destino


@pytest.fixture(scope="session")
def transcrever():
    return _carregar_transcrever_modulo(_REPO)


# ---------------------------------------------------------------------------
# Helpers de cenarios negativos
# ---------------------------------------------------------------------------


def _criar_snapshot_fake(
    base: Path,
    *,
    incluir: Iterable[str] = ARQUIVOS_OBRIGATORIOS,
    config: Any = None,
    model_bytes: bytes = b"modelo-fake-para-testes",
) -> Path:
    """Cria um snapshot fake (5 arquivos) para exercitar validacoes/erros."""
    incluir = tuple(incluir)
    base.mkdir(parents=True, exist_ok=True)
    if "model.bin" in incluir:
        (base / "model.bin").write_bytes(model_bytes)
    if "config.json" in incluir:
        cfg = config if config is not None else {
            "alignment_heads": [],
            "lang_ids": [],
            "suppress_ids": [],
        }
        (base / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
    if "tokenizer.json" in incluir:
        (base / "tokenizer.json").write_text('{"version": "1.0"}', encoding="utf-8")
    if "preprocessor_config.json" in incluir:
        (base / "preprocessor_config.json").write_text(
            '{"feature_extractor_type": "WhisperFeatureExtractor"}', encoding="utf-8"
        )
    if "vocabulary.json" in incluir:
        (base / "vocabulary.json").write_text('{"a": 0, "b": 1}', encoding="utf-8")
    return base


def _bloquear_rede(monkeypatch) -> List[Tuple[Any, Any]]:
    """Faz qualquer download/chamada HTTP falhar e registra a tentativa."""
    chamadas: List[Tuple[Any, Any]] = []

    def _boom(*args, **kwargs):
        chamadas.append((args, kwargs))
        raise AssertionError("download/rede proibidos em modo offline")

    import urllib.request

    monkeypatch.setattr(urllib.request, "urlopen", _boom)
    for modulo_nome, atributo in (
        ("faster_whisper.utils", "download_model"),
        ("faster_whisper.transcribe", "download_model"),
    ):
        try:
            modulo = __import__(modulo_nome, fromlist=["*"])
            monkeypatch.setattr(modulo, atributo, _boom, raising=False)
        except Exception:
            pass
    try:
        import huggingface_hub

        monkeypatch.setattr(huggingface_hub, "snapshot_download", _boom, raising=False)
    except Exception:
        pass
    return chamadas


# ---------------------------------------------------------------------------
# 1) Teste real: faster-whisper offline com snapshot validado
# ---------------------------------------------------------------------------


def test_01_transcricao_real_offline_com_snapshot(
    snapshot_local, fala_ptbr_16k, tmp_path, monkeypatch, transcrever
):
    monkeypatch.setenv(SNAPSHOT_ENV, str(snapshot_local))
    monkeypatch.setenv("ELEVENLABS_API_KEY", "chave-simulada-nao-deve-ser-usada")
    chamadas = _bloquear_rede(monkeypatch)

    resultado = transcrever.transcreve(
        str(fala_ptbr_16k), str(tmp_path), "pt", detalhado=True
    )

    assert chamadas == [], f"download/rede foram tentados: {chamadas}"
    assert isinstance(resultado, dict)
    assert resultado["total_words"] > 0
    assert resultado["palavras"], "transcricao offline nao produziu palavras"
    assert resultado["segments"], "transcricao offline nao produziu segmentos"

    # Idioma e metadados de execucao local.
    assert resultado["language"] == "pt"
    assert resultado["language_probability"] > 0
    assert resultado["duration"] > 0
    assert resultado["engine"] == "faster-whisper"
    assert resultado["local_execution_confirmed"] is True
    assert resultado["local_files_only"] is True
    assert resultado["offline_only"] is True
    assert resultado["model_path_kind"] == "local_snapshot"
    identificador = resultado["model_identifier"]
    assert identificador.startswith(
        "mobiuslabsgmbh/faster-whisper-large-v3-turbo@"
    ), identificador
    assert resultado["model_revision"]

    # Palavras/timestamps/probabilidades coerentes.
    palavras = resultado["palavras"]
    assert len(palavras) == resultado["total_words"]
    segment_words = [
        sw
        for s in resultado["segments"]
        for sw in (s.get("words") or [])
    ]
    for i, p in enumerate(palavras):
        assert isinstance(p["w"], str) and p["w"].strip()
        assert float(p["f"]) >= float(p["t"]) >= 0.0
        # probability preservada em palavras[] (igual a segments[...][words]).
        if i < len(segment_words):
            assert p["probability"] == segment_words[i]["probability"], (
                f"palavra[{i}]['probability']={p['probability']} != "
                f"segments words[{i}]['probability']={segment_words[i]['probability']}"
            )
    inicios = [float(p["t"]) for p in palavras]
    assert inicios == sorted(inicios), "timestamps de inicio fora de ordem"
    assert max(float(p["f"]) for p in palavras) <= resultado["duration"] + 0.5

    # Arquivos de saida validos: JSON serializavel e reutilizavel.
    saida = tmp_path / "transcricao_offline.json"
    saida.write_text(
        json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    recarregado = json.loads(saida.read_text(encoding="utf-8"))
    assert recarregado["total_words"] == resultado["total_words"]
    assert recarregado["model_identifier"] == identificador

    # Nenhum caminho absoluto do snapshot vaza nos metadados publicos.
    texto_json = json.dumps(recarregado, ensure_ascii=False)
    assert str(snapshot_local) not in texto_json
    assert "Backup" not in texto_json


# ---------------------------------------------------------------------------
# 2) Caminho de modelo inexistente
# ---------------------------------------------------------------------------


def test_02_modelo_inexistente(tmp_path, transcrever):
    wav = _gerar_wav(tmp_path / "audio.wav")
    inexistente = tmp_path / "snapshot_que_nao_existe"

    with pytest.raises(transcrever.WhisperModelPathError) as exc:
        transcrever.transcreve_faster_whisper_detalhado(
            str(wav), str(tmp_path), "pt", model_path=inexistente, offline_only=True
        )
    assert "inexistente" in str(exc.value).lower()


# ---------------------------------------------------------------------------
# 3) Snapshot sem model.bin
# ---------------------------------------------------------------------------


def test_03_snapshot_sem_model_bin(tmp_path, transcrever):
    wav = _gerar_wav(tmp_path / "audio.wav")
    snapshot = _criar_snapshot_fake(
        tmp_path / "snapshot_sem_model",
        incluir=("config.json", "tokenizer.json", "preprocessor_config.json", "vocabulary.json"),
    )

    with pytest.raises(transcrever.WhisperSnapshotIncompleteError) as exc:
        transcrever.transcreve_faster_whisper_detalhado(
            str(wav), str(tmp_path), "pt", model_path=snapshot, offline_only=True
        )
    assert "model.bin" in str(exc.value)


# ---------------------------------------------------------------------------
# 4) Snapshot incompleto (sem tokenizer.json/config.json)
# ---------------------------------------------------------------------------


def test_04_snapshot_incompleto(tmp_path, transcrever):
    wav = _gerar_wav(tmp_path / "audio.wav")
    snapshot = _criar_snapshot_fake(
        tmp_path / "snapshot_incompleto",
        incluir=("model.bin", "preprocessor_config.json", "vocabulary.json"),
    )

    with pytest.raises(transcrever.WhisperSnapshotIncompleteError) as exc:
        transcrever.transcreve_faster_whisper_detalhado(
            str(wav), str(tmp_path), "pt", model_path=snapshot, offline_only=True
        )
    mensagem = str(exc.value)
    assert "tokenizer.json" in mensagem
    assert "config.json" in mensagem


# ---------------------------------------------------------------------------
# 5) Modelo incompativel/corrompido
# ---------------------------------------------------------------------------


def test_05_modelo_incompativel_ou_corrompido(tmp_path, transcrever):
    wav = _gerar_wav(tmp_path / "audio.wav")

    # config.json quebrado (JSON invalido).
    corrompido = _criar_snapshot_fake(tmp_path / "snapshot_config_quebrado")
    (corrompido / "config.json").write_text("{isto-nao-e-json", encoding="utf-8")
    with pytest.raises(transcrever.WhisperModelIncompatibleError) as exc:
        transcrever.transcreve_faster_whisper_detalhado(
            str(wav), str(tmp_path), "pt", model_path=corrompido, offline_only=True
        )
    assert "config.json" in str(exc.value).lower()

    # config.json valido, mas sem marcadores de Whisper (modelo incompativel).
    incompativel = _criar_snapshot_fake(
        tmp_path / "snapshot_incompativel", config={"foo": "bar"}
    )
    with pytest.raises(transcrever.WhisperModelIncompatibleError) as exc:
        transcrever.transcreve_faster_whisper_detalhado(
            str(wav), str(tmp_path), "pt", model_path=incompativel, offline_only=True
        )
    assert "incompat" in str(exc.value).lower()


# ---------------------------------------------------------------------------
# 6) Offline sem modelo + ELEVENLABS_API_KEY simulada bloqueada
# ---------------------------------------------------------------------------


def test_06_offline_sem_modelo_bloqueia_elevenlabs(tmp_path, monkeypatch, transcrever):
    monkeypatch.delenv(SNAPSHOT_ENV, raising=False)
    monkeypatch.setenv("ELEVENLABS_API_KEY", "chave-simulada-bloqueada")
    chamadas = _bloquear_rede(monkeypatch)
    wav = _gerar_wav(tmp_path / "audio.wav")

    with pytest.raises(transcrever.WhisperOfflineError) as exc:
        transcrever.transcreve(str(wav), str(tmp_path), "pt", offline_only=True)

    assert "offline" in str(exc.value).lower()
    assert SNAPSHOT_ENV in str(exc.value)
    assert chamadas == [], f"ElevenLabs/download tentou rede: {chamadas}"
    assert not (tmp_path / "transcricao_bruta.json").exists()


# ---------------------------------------------------------------------------
# 7) Configuracao de caminho invalida (vazio ou arquivo ao inves de pasta)
# ---------------------------------------------------------------------------


def test_07_configuracao_de_caminho_invalida(tmp_path, transcrever):
    wav = _gerar_wav(tmp_path / "audio.wav")

    with pytest.raises(transcrever.WhisperModelPathError) as exc:
        transcrever.transcreve_faster_whisper_detalhado(
            str(wav), str(tmp_path), "pt", model_path="", offline_only=True
        )
    assert "vazio" in str(exc.value).lower()

    arquivo = tmp_path / "nao_e_diretorio.bin"
    arquivo.write_bytes(b"conteudo")
    with pytest.raises(transcrever.WhisperModelPathError) as exc:
        transcrever.transcreve_faster_whisper_detalhado(
            str(wav), str(tmp_path), "pt", model_path=arquivo, offline_only=True
        )
    assert "nao e diretorio" in str(exc.value).lower()


# ---------------------------------------------------------------------------
# 8) Falha na inicializacao do WhisperModel
# ---------------------------------------------------------------------------


def test_08_falha_na_inicializacao_whisper(tmp_path, monkeypatch, transcrever):
    snapshot = _criar_snapshot_fake(tmp_path / "snapshot_init")
    wav = _gerar_wav(tmp_path / "audio.wav")

    import faster_whisper

    class _ModeloQueFalhaNoInit:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("falha simulada na inicializacao do modelo")

    monkeypatch.setattr(faster_whisper, "WhisperModel", _ModeloQueFalhaNoInit)

    with pytest.raises(transcrever.WhisperInitError) as exc:
        transcrever.transcreve_faster_whisper_detalhado(
            str(wav), str(tmp_path), "pt", model_path=snapshot, offline_only=True
        )
    assert "inicializacao" in str(exc.value).lower()
    assert "falha simulada" in str(exc.value)


# ---------------------------------------------------------------------------
# 9) Falha durante a inferencia (model.transcribe)
# ---------------------------------------------------------------------------


def test_09_falha_na_inferencia(tmp_path, monkeypatch, transcrever):
    snapshot = _criar_snapshot_fake(tmp_path / "snapshot_inferencia")
    wav = _gerar_wav(tmp_path / "audio.wav")

    import faster_whisper

    class _ModeloQueFalhaNaInferencia:
        def __init__(self, *args, **kwargs):
            pass

        def transcribe(self, *args, **kwargs):
            raise RuntimeError("falha simulada na inferencia")

    monkeypatch.setattr(faster_whisper, "WhisperModel", _ModeloQueFalhaNaInferencia)

    with pytest.raises(transcrever.WhisperInferenceError) as exc:
        transcrever.transcreve_faster_whisper_detalhado(
            str(wav), str(tmp_path), "pt", model_path=snapshot, offline_only=True
        )
    assert "inferencia" in str(exc.value).lower()
    assert "falha simulada" in str(exc.value)


# ---------------------------------------------------------------------------
# 10) Bug latente voz_16k: criado para audio nao-16k e removido no finally
# ---------------------------------------------------------------------------


def test_10_voz_16k_criado_e_removido_sem_quebrar(tmp_path, monkeypatch, transcrever):
    snapshot = _criar_snapshot_fake(tmp_path / "snapshot_16k")
    wav_44k = _gerar_wav(tmp_path / "audio_44k.wav", taxa=44100, canais=2)

    import faster_whisper

    class _ModeloVazio:
        def __init__(self, *args, **kwargs):
            pass

        def transcribe(self, audio, **kwargs):
            assert Path(audio).is_file(), "audio temporario deveria existir na inferencia"
            return iter([]), SimpleNamespace(
                language="pt", language_probability=1.0, duration=0.8
            )

    monkeypatch.setattr(faster_whisper, "WhisperModel", _ModeloVazio)

    resultado = transcrever.transcreve_faster_whisper_detalhado(
        str(wav_44k), str(tmp_path), "pt", model_path=snapshot, offline_only=True
    )

    assert resultado["total_words"] == 0
    assert resultado["language"] == "pt"
    assert not (tmp_path / "voz_16k.wav").exists(), "voz_16k temporario nao foi removido"


# ---------------------------------------------------------------------------
# B2: preservacao de probabilidades reais do Whisper
# ---------------------------------------------------------------------------


def test_b2_transcrever_preserva_probabilidades_reais(
    tmp_path, monkeypatch, transcrever
):
    """transcreve_faster_whisper_detalhado preserva probability real (nao vira 1.0)."""
    snapshot = _criar_snapshot_fake(tmp_path / "snapshot_prob")
    wav = _gerar_wav(tmp_path / "audio.wav", taxa=16000, canais=1)

    import faster_whisper

    palavras_controle = [
        ("baixa", 0.0, 0.5, 0.31),
        ("alta", 0.5, 1.0, 0.92),
        ("media", 1.0, 1.5, 0.57),
        ("sem_prob", 1.5, 2.0, None),
        ("invalida_alta", 2.0, 2.5, 1.5),
    ]

    class _Palavra:
        def __init__(self, word, start, end, prob):
            self.word = word
            self.start = start
            self.end = end
            self.probability = prob

    class _Segmento:
        def __init__(self):
            self.words = [_Palavra(*p) for p in palavras_controle]
            self.id = 0
            self.seek = 0
            self.start = 0.0
            self.end = 2.5
            self.text = " ".join(p[0] for p in palavras_controle)
            self.avg_logprob = -0.5
            self.no_speech_prob = 0.1

    class _ModeloComProb:
        def __init__(self, *args, **kwargs):
            pass

        def transcribe(self, audio, **kwargs):
            return iter([_Segmento()]), SimpleNamespace(
                language="pt", language_probability=1.0, duration=2.5
            )

    monkeypatch.setattr(faster_whisper, "WhisperModel", _ModeloComProb)

    resultado = transcrever.transcreve_faster_whisper_detalhado(
        str(wav), str(tmp_path), "pt", model_path=snapshot, offline_only=True
    )

    segment_words = resultado["segments"][0]["words"]
    probs_por_palavra = {sw["word"]: sw["probability"] for sw in segment_words}
    # Valores reais preservados (nao forçados a 1.0).
    assert probs_por_palavra["baixa"] == 0.31
    assert probs_por_palavra["alta"] == 0.92
    assert probs_por_palavra["media"] == 0.57
    # Ausente -> None (null), nunca 1.0.
    assert probs_por_palavra["sem_prob"] is None
    # Invalido (>1) passa pelo transcrever (a coercao ocorre no analyze.py).
    assert probs_por_palavra["invalida_alta"] == 1.5

    # palavras[] deve espelhar a mesma probability de segments[...][words].
    palavras = resultado["palavras"]
    assert len(palavras) == len(segment_words)
    for i, p in enumerate(palavras):
        sw = segment_words[i]
        assert p["w"] == sw["word"]
        assert p["probability"] == sw["probability"], (
            f"palavras[{i}]['probability']={p['probability']} != "
            f"segments[0]['words'][{i}]['probability']={sw['probability']}"
        )
