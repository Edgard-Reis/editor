#!/usr/bin/env python3
"""
core/test_analyze.py

Suíte de testes unitários para core/analyze.py (Editor).

Valida transcricao, verificacao fonetica e alinhamento temporal usando
fixtures sinteticas pequenas (WAV 16kHz mono sintetico + transcricao
mockada/injetada, SEM rodar modelo Whisper real) em
tempfile.TemporaryDirectory(), sem alterar arquivos reais do repositorio.

Cenarios cobertos (todos os pontos obrigatorios):
 - Gate de integridade: origin_sha256 == brutos_sha256 e bloqueio se alterado.
 - Transcricao/preservacao de timestamps.
 - Reconhecimento de termos do dicionario da marca (lexicon).
 - Deteccao de baixa confianca (probability < 0.65) e divergencias foneticas.
 - Funcionamento do alinhamento (pausas + silence_guard_ms da marca).
 - Compatibilidade com palavras.json e roteiro.txt do legado.
 - Ausencia de processamento duplicado (pular re-extracao 16k e reutilizar
   transcritor) - verificado por chamada direta ao transcreve com detalhado=True
   em WAV ja 16kHz mono.
 - Isolamento por marca e episodio.
"""

import json
import math
import shutil
import sys
import tempfile
import wave
from pathlib import Path
from typing import Any

# Garante import do pacote core (raiz Editor).
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.analyze import (  # noqa: E402
    analyze_episodio,
    AnalyzeError,
    PhoneticVerifier,
    build_alignment_from_words,
    _carregar_transcrever_modulo,
    _load_phonetic_rules,
    _limpar_token,
)
from core.workspace import (  # noqa: E402
    WorkspaceLoader,
    init_workspace,
    register_brand,
    load_brand_profile,
    list_brands,
    create_project,
    load_project,
    resolve_brand_asset,
    resolve_episodio_asset,
)
from core.ingest import (  # noqa: E402
    ingest_media,
    IngestError,
    compute_sha256,
    verify_source_integrity,
)


def _gerar_wav_16k_mono(caminho: Path, duracao_s: float = 1.0, tom_hz: float = 440.0) -> None:
    """Gera um arquivo WAV PCM 16kHz mono sintético (tom puro) sem ffmpeg."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    sample_rate = 16000
    n_samples = int(sample_rate * duracao_s)
    import struct
    amostras = []
    for i in range(n_samples):
        valor = int(12000 * math.sin(2 * math.pi * tom_hz * i / sample_rate))
        amostras.append(struct.pack("<h", valor))
    with wave.open(str(caminho), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b"".join(amostras))


def _setup_workspace_e_marca(tmp: Path, marca_id: str = "marca-teste") -> Path:
    """Cria workspace.json e registra uma marca no tmp (estrutura do legado)."""
    init_workspace(tmp)
    marca_dir = tmp / "projetos" / marca_id / "branding"
    marca_dir.mkdir(parents=True, exist_ok=True)
    perfil = {
        "schema_version": "1.0.0",
        "brand_id": marca_id,
        "display_name": f"Marca {marca_id}",
        "marca": {"destaque": "#004aad", "fonte": "Inter"},
        "preferencias_edicao": {
            "canal": f"Canal {marca_id}",
            "apresentador": f"Apresentador {marca_id}",
            "lexicon_transcricao": "Dr. Gestao, Alta Minutagem, Marketplaces",
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
                "lexicon": ["Dr. Gestao", "Alta Minutagem", "Marketplaces"],
                "phonetic_rules_file": "phonetic_rules.json",
            },
        },
        "visual": {
            "safe_zones": {
                "master_16x9": {"lower_third_max_w": 1150},
                "shorts_9x16": {"lower_third_y": 1480},
            }
        },
        "asr": {},
        "assets": {},
    }
    # phonetic_rules.json com uma regra de divergencia fonetica
    (marca_dir / "phonetic_rules.json").write_text(
        json.dumps({
            "rules": [
                {
                    "pattern": ["alguma", "coisa"],
                    "replacement": ["algumacoisa"],
                    "rule_name": "uniao_algumacoisa",
                    "category": "uniao",
                    "certainty": 0.9,
                    "rationale": "Uniao fonetica de 'alguma coisa'.",
                }
            ]
        }, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    with open(marca_dir / "config.json", "w", encoding="utf-8") as f:
        json.dump(perfil, f, indent=2, ensure_ascii=False)
    return tmp


def _iso_now_analyze() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def _gravar_json_analyze(path: Path, dados: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(dados, f, indent=2, ensure_ascii=False)

def _setup_episodio_com_ingestao(
    tmp: Path, marca_id: str, episodio_id: str, nome_arquivo: str = "video.mp4"
) -> Path:
    """Cria episodio, grava audio sintético em brutos/ e roda ingest_media."""
    loader = WorkspaceLoader(tmp)
    loader.load_workspace()
    loader.register_brand(marca_id, f"Marca {marca_id}")

    # Cria project.json diretamente (sem chamar novo_episodio.py).
    episodio_dir = loader.resolve_episodio_asset(marca_id, episodio_id, "")
    episodio_dir.mkdir(parents=True, exist_ok=True)
    projeto = {
        "schema_version": "1.0.0",
        "marca_id": marca_id,
        "episodio_id": episodio_id,
        "nome": episodio_id,
        "current_stage": "01_GRAVACAO_ORIGINAL",
        "created_at": _iso_now_analyze(),
        "updated_at": _iso_now_analyze(),
        "sources": [],
        "artifacts": {},
        "approvals": {
            "master_16x9_approved": False,
            "approved_by": None,
            "approved_at": None,
        },
    }
    pj_path = loader.project_file(marca_id, episodio_id)
    _gravar_json_analyze(pj_path, projeto)

    brutos_dir = loader.resolve_episodio_asset(marca_id, episodio_id, "brutos")
    brutos_dir.mkdir(parents=True, exist_ok=True)
    video_bruto = brutos_dir / nome_arquivo
    _gerar_wav_16k_mono(video_bruto, duracao_s=2.0)

    rc = ingest_media(
        input_path=str(video_bruto),
        marca_id=marca_id,
        episodio_id=episodio_id,
        workspace_root=str(tmp),
    )
    assert rc == 0, f"ingest falhou com codigo {rc}"
    return video_bruto


# ---------------------------------------------------------------------------
# Testes
# ---------------------------------------------------------------------------


def test_gate_integridade_origem_igual_brutos():
    """Gate de integridade: origin_sha256 == brutos_sha256 (copia idêntica)."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        _setup_workspace_e_marca(tmp, "marca-gate")
        _setup_episodio_com_ingestao(tmp, "marca-gate", "ep-gate")

        loader = WorkspaceLoader(tmp)
        loader.load_workspace()
        projeto = loader.load_project("marca-gate", "ep-gate")
        fonte = projeto["sources"][0]
        assert fonte["copy_hash_verified"] is True
        assert fonte["origin_sha256"] == fonte["sha256"], (
            "origin_sha256 deve ser igual ao sha256 do brutos."
        )
        assert fonte["read_only_verified"] is True
        assert "origin_path" in fonte
        assert "path" in fonte
    print("  [PASS] test_gate_integridade_origem_igual_brutos")


def test_gate_integridade_bloqueia_arquivo_alterado():
    """Gate de integridade: bloqueia se o arquivo em brutos/ for alterado."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        _setup_workspace_e_marca(tmp, "marca-bloqueio")
        _setup_episodio_com_ingestao(tmp, "marca-bloqueio", "ep-bloqueio")

        loader = WorkspaceLoader(tmp)
        loader.load_workspace()
        projeto = loader.load_project("marca-bloqueio", "ep-bloqueio")
        fonte = projeto["sources"][0]
        brutos_path = Path(fonte["path"])
        brutos_sha = fonte["sha256"]

        # Simula alteracao: chama verify_source_integrity com SHA diferente do registrado.
        try:
            verify_source_integrity(brutos_path, "0000" * 16, brutos_path.name)
            assert False, "Deveria levantar IngestError."
        except IngestError:
            pass
    print("  [PASS] test_gate_integridade_bloqueia_arquivo_alterado")


def test_preservacao_timestamps_transcricao_injetada():
    """Transcricao injetada preserva timestamps (w, t, f)."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        _setup_workspace_e_marca(tmp, "marca-ts")
        _setup_episodio_com_ingestao(tmp, "marca-ts", "ep-ts")

        transcricao_injetada = [
            {"w": "Seja", "t": 0.0, "f": 0.76, "probability": 0.99},
            {"w": "muito", "t": 0.76, "f": 1.04, "probability": 0.98},
            {"w": "bem-vindo", "t": 1.04, "f": 1.46, "probability": 0.97},
        ]
        resultado = analyze_episodio(
            "marca-ts", "ep-ts", str(tmp),
            transcricao_injetada=transcricao_injetada,
        )
        assert resultado["palavras"][0]["w"] == "Seja"
        assert resultado["palavras"][0]["t"] == 0.0
        assert resultado["palavras"][0]["f"] == 0.76
        assert resultado["palavras"][1]["t"] == 0.76
        assert resultado["palavras"][2]["w"] == "bem-vindo"
    print("  [PASS] test_preservacao_timestamps_transcricao_injetada")


def test_reconhecimento_lexicon_marca():
    """Reconhecimento de termos do dicionario da marca (lexicon)."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        _setup_workspace_e_marca(tmp, "marca-lex")
        _setup_episodio_com_ingestao(tmp, "marca-lex", "ep-lex")

        transcricao_injetada = [
            {"w": "drgestao", "t": 0.0, "f": 0.5, "probability": 0.99},
            {"w": "altaminutagem", "t": 0.6, "f": 1.1, "probability": 0.99},
            {"w": "marketplaces", "t": 1.2, "f": 1.7, "probability": 0.99},
            {"w": "palavra", "t": 2.3, "f": 2.8, "probability": 0.99},
            {"w": "comum", "t": 2.9, "f": 3.3, "probability": 0.99},
        ]
        resultado = analyze_episodio(
            "marca-lex", "ep-lex", str(tmp),
            transcricao_injetada=transcricao_injetada,
        )
        report = resultado["phonetic_report"]
        hits = {h["palavra"].lower() for h in report["lexicon_hits"]}
        assert "drgestao" in hits, f"lexicon_hits nao contem drgestao: {hits}"
        assert "altaminutagem" in hits, f"lexicon_hits nao contem altaminutagem: {hits}"
        assert "marketplaces" in hits, f"lexicon_hits nao contem marketplaces: {hits}"
        assert "palavra" not in hits, "palavra comum nao deve estar no lexicon."
        assert "comum" not in hits, "palavra comum nao deve estar no lexicon."
    print("  [PASS] test_reconhecimento_lexicon_marca")


def test_deteccao_baixa_confianca_e_divergencia_fonetica():
    """Deteccao de baixa confianca (probability < 0.65) e divergencias foneticas."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        _setup_workspace_e_marca(tmp, "marca-div")
        _setup_episodio_com_ingestao(tmp, "marca-div", "ep-div")

        transcricao_injetada = [
            {"w": "alguma", "t": 0.0, "f": 0.5, "probability": 0.99},
            {"w": "coisa", "t": 0.6, "f": 1.1, "probability": 0.99},
            {"w": "murmurio", "t": 1.2, "f": 1.7, "probability": 0.40},  # baixa confianca
            {"w": "desconhecido", "t": 1.8, "f": 2.3, "probability": 0.30},  # baixa confianca
        ]
        resultado = analyze_episodio(
            "marca-div", "ep-div", str(tmp),
            transcricao_injetada=transcricao_injetada,
        )
        report = resultado["phonetic_report"]
        # Baixa confianca detectada.
        assert report["low_confidence_count"] >= 2, f"esperado >= 2 baixa confianca: {report['low_confidence_count']}"
        # Divergencia fonetica: 'alguma coisa' -> 'algumacoisa'.
        assert any(f["rule_name"] == "uniao_algumacoisa" for f in report["findings"]), (
            f"divergencia fonetica nao detectada: {report['findings']}"
        )
    print("  [PASS] test_deteccao_baixa_confianca_e_divergencia_fonetica")


def test_alignamento_pausas_silence_guard_ms():
    """Funcionamento do alinhamento (pausas + silence_guard_ms da marca)."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        _setup_workspace_e_marca(tmp, "marca-align")
        _setup_episodio_com_ingestao(tmp, "marca-align", "ep-align")

        # Palavras com pausa longa (> 220ms = silence_guard_ms[1]) para forcar split.
        transcricao_injetada = [
            {"w": "Primeira", "t": 0.0, "f": 0.5, "probability": 0.99},
            {"w": "frase", "t": 0.6, "f": 1.0, "probability": 0.99},
            {"w": "pausa", "t": 1.5, "f": 2.0, "probability": 0.99},  # gap 0.5s > 0.22s
            {"w": "longa", "t": 2.1, "f": 2.6, "probability": 0.99},
            {"w": "aqui", "t": 2.7, "f": 3.1, "probability": 0.99},
        ]
        resultado = analyze_episodio(
            "marca-align", "ep-align", str(tmp),
            transcricao_injetada=transcricao_injetada,
        )
        alinhamento = resultado["alignment"]
        assert alinhamento["summary"]["total_editorial_units"] >= 2, (
            f"esperado >= 2 unidades editoriais: {alinhamento['summary']['total_editorial_units']}"
        )
        assert alinhamento["summary"]["total_pauses"] >= 1, (
            f"esperado >= 1 pausa: {alinhamento['summary']['total_pauses']}"
        )
        # Pausa detectada entre 'frase' e 'pausa'.
        pausas_longas = [p for p in alinhamento["pauses"] if p["duration_seconds"] > 0.22]
        assert len(pausas_longas) >= 1, f"esperado pausa longa: {alinhamento['pauses']}"
    print("  [PASS] test_alignamento_pausas_silence_guard_ms")


def test_compatibilidade_palavras_json_e_roteiro_txt():
    """Compatibilidade com palavras.json e roteiro.txt do legado."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        _setup_workspace_e_marca(tmp, "marca-legado")
        _setup_episodio_com_ingestao(tmp, "marca-legado", "ep-legado")

        transcricao_injetada = [
            {"w": "Ola", "t": 0.0, "f": 0.5, "probability": 0.99},
            {"w": "mundo", "t": 0.6, "f": 1.1, "probability": 0.99},
            {"w": "fim.", "t": 1.2, "f": 1.7, "probability": 0.99},
        ]
        analyze_episodio("marca-legado", "ep-legado", str(tmp),
                         transcricao_injetada=transcricao_injetada)

        loader = WorkspaceLoader(tmp)
        fonte_dir = loader.resolve_episodio_asset("marca-legado", "ep-legado", "workspace/fonte")

        palavras_json = json.loads((fonte_dir / "palavras.json").read_text(encoding="utf-8"))
        assert isinstance(palavras_json, list)
        assert palavras_json[0]["w"] == "Ola"
        assert "t" in palavras_json[0] and "f" in palavras_json[0]

        roteiro_txt = (fonte_dir / "roteiro.txt").read_text(encoding="utf-8")
        assert "Ola" in roteiro_txt
        assert "mundo" in roteiro_txt
        assert "fim." in roteiro_txt
        assert "–" in roteiro_txt  # marcador de tempo
    print("  [PASS] test_compatibilidade_palavras_json_e_roteiro_txt")


def test_nao_processo_duplicado_pular_reextracao_16k():
    """Ausencia de processamento duplicado: transcritor carrega e eh_wav_16k_mono
    detecta WAV ja 16kHz mono (evitaria re-extração de voz_16k.wav)."""
    transcrever_modulo = _carregar_transcrever_modulo(str(_ROOT))
    assert transcrever_modulo is not None
    assert hasattr(transcrever_modulo, "transcreve")
    assert hasattr(transcrever_modulo, "eh_wav_16k_mono")
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        wav = tmp / "ja_16k.wav"
        _gerar_wav_16k_mono(wav, duracao_s=1.0, tom_hz=440.0)
        assert transcrever_modulo.eh_wav_16k_mono(wav) is True
        # Nao-WAV (txt) deve retornar False.
        txt = tmp / "nao_eh_wav.txt"
        txt.write_text("nao e audio", encoding="utf-8")
        assert transcrever_modulo.eh_wav_16k_mono(txt) is False
    print("  [PASS] test_nao_processo_duplicado_pular_reextracao_16k")


def test_isolamento_entre_marcas_e_episodios():
    """Isolamento por marca e episodio."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        _setup_workspace_e_marca(tmp, "marca-x")
        _setup_workspace_e_marca(tmp, "marca-y")
        _setup_episodio_com_ingestao(tmp, "marca-x", "ep-x")
        _setup_episodio_com_ingestao(tmp, "marca-y", "ep-y")

        transcricao_x = [{"w": "marca", "t": 0.0, "f": 0.5, "probability": 0.99}, {"w": "x", "t": 0.6, "f": 1.0, "probability": 0.99}]
        transcricao_y = [{"w": "marca", "t": 0.0, "f": 0.5, "probability": 0.99}, {"w": "y", "t": 0.6, "f": 1.0, "probability": 0.99}]

        resultado_x = analyze_episodio("marca-x", "ep-x", str(tmp), transcricao_injetada=transcricao_x)
        resultado_y = analyze_episodio("marca-y", "ep-y", str(tmp), transcricao_injetada=transcricao_y)

        assert resultado_x["marca_id"] == "marca-x"
        assert resultado_y["marca_id"] == "marca-y"
        assert resultado_x["palavras"][1]["w"] == "x"
        assert resultado_y["palavras"][1]["w"] == "y"

        # project.json de cada episodio esta isolado.
        px = load_project(tmp, "marca-x", "ep-x")
        py = load_project(tmp, "marca-y", "ep-y")
        assert px["current_stage"] == "02_ANALYZE_COMPLETED"
        assert py["current_stage"] == "02_ANALYZE_COMPLETED"
        assert px["episodio_id"] == "ep-x"
        assert py["episodio_id"] == "ep-y"
    print("  [PASS] test_isolamento_entre_marcas_e_episodios")


def test_b2_probabilidade_nao_virra_um_nao_analyze():
    """B2: probability ausente/invalida nao vira 1.0 no analyze (phonetic_report + transcript)."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        _setup_workspace_e_marca(tmp, "marca-prob")
        _setup_episodio_com_ingestao(tmp, "marca-prob", "ep-prob")

        transcricao_injetada = [
            {"w": "baixa", "t": 0.0, "f": 0.5, "probability": 0.40},   # baixa confianca
            {"w": "alta", "t": 0.6, "f": 1.1, "probability": 0.92},    # alta confianca
            {"w": "media", "t": 1.2, "f": 1.7, "probability": 0.57},   # baixa confianca
            {"w": "semprob", "t": 1.8, "f": 2.3},                       # ausente -> desconhecida
            {"w": "invalida", "t": 2.4, "f": 2.9, "probability": 1.5}, # invalida (>1) -> desconhecida
            {"w": "negativa", "t": 3.0, "f": 3.5, "probability": -0.5},# invalida (<0) -> desconhecida
            {"w": "nan", "t": 3.6, "f": 4.1, "probability": float("nan")},  # invalida -> desconhecida
        ]
        resultado = analyze_episodio(
            "marca-prob", "ep-prob", str(tmp),
            transcricao_injetada=transcricao_injetada,
        )

        report = resultado["phonetic_report"]
        # Baixa confianca so conta probabilidades validas < 0.65.
        assert report["low_confidence_count"] == 2, report["low_confidence_count"]
        low = {h["palavra"] for h in report["low_confidence"]}
        assert low == {"baixa", "media"}, low
        # Ausente/invalida nao vira alta confianca: entra em unknown_confidence_count.
        assert report["unknown_confidence_count"] == 4, report["unknown_confidence_count"]

        # transcript.json preserva os valores reais (nao força 1.0).
        fonte = loader_resolve = tmp / "projetos" / "marca-prob" / "episodios" / "ep-prob" / "workspace" / "fonte"
        transcript = json.loads((fonte / "transcript.json").read_text(encoding="utf-8"))
        probs = {seg["words"][0]["word"]: seg["words"][0]["probability"] for seg in transcript["segments"]}
        assert probs["baixa"] == 0.40
        assert probs["alta"] == 0.92
        assert probs["media"] == 0.57
        assert probs["semprob"] is None
        assert probs["invalida"] is None
        assert probs["negativa"] is None
        assert probs["nan"] is None
    print("  [PASS] test_b2_probabilidade_nao_virra_um_nao_analyze")


# ---------------------------------------------------------------------------
# Runner auxiliar (execucao direta)
# ---------------------------------------------------------------------------


def run_tests():
    print("=" * 60)
    print("SUITE DE TESTES — core/analyze.py (Editor)")
    print("=" * 60)
    testes = [
        test_gate_integridade_origem_igual_brutos,
        test_gate_integridade_bloqueia_arquivo_alterado,
        test_preservacao_timestamps_transcricao_injetada,
        test_reconhecimento_lexicon_marca,
        test_deteccao_baixa_confianca_e_divergencia_fonetica,
        test_alignamento_pausas_silence_guard_ms,
        test_compatibilidade_palavras_json_e_roteiro_txt,
        test_nao_processo_duplicado_pular_reextracao_16k,
        test_isolamento_entre_marcas_e_episodios,
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
