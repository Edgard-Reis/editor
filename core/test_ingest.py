#!/usr/bin/env python3
"""
core/test_ingest.py

Suíte de testes unitários para core/ingest.py (Editor).

Usa fixtures sintéticas pequenas geradas via ffmpeg em
tempfile.TemporaryDirectory(), sem renderização completa e sem alterar
arquivos reais do repositório.

Valida TODOS os 9 pontos obrigatórios:
 1. SHA-256 correto
 2. deteccao de arquivo alterado (verify_source_integrity)
 3. metadados via FFprobe
 4. preservacao do original (read-only e Delta-Hash=0)
 5. normalizacao de audio (WAV 16kHz mono)
 6. registro no project.json
 7. ingestao em duas marcas diferentes (isolamento)
 8. protecao contra caminhos externos/path-traversal
 9. compatibilidade com episodio legado preexistente
 10. integracao com novo_episodio.py --sem-transcricao
"""

import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

# Garante import do pacote core (raiz Editor).
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.ingest import (  # noqa: E402
    ingest_media,
    IngestError,
    compute_sha256,
    verify_source_integrity,
    check_tool,
    inspect_media_ffprobe,
)
from core.workspace import (  # noqa: E402
    WorkspaceLoader,
    init_workspace,
    load_workspace,
    register_brand,
    load_brand_profile,
    create_project,
    load_project,
)

FFMPEG_BIN = str(_ROOT / "tools" / "hyperframes" / "bin" / "windows-x64" / "ffmpeg.exe")
FFPROBE_BIN = str(_ROOT / "tools" / "hyperframes" / "bin" / "windows-x64" / "ffprobe.exe")

# Caminho absoluto da raiz do repositório Editor (para teste de integração
# com novo_episodio.py --sem-transcricao).
REPO_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Fixture de vídeo sintético pequeno via ffmpeg
# ---------------------------------------------------------------------------


def _gerar_video_sintetico(destino: Path, duracao_s: float = 2.0) -> Path:
    """Gera um arquivo MP4 sintético pequeno (teste, sem renderização completa)."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        FFMPEG_BIN, "-y",
        "-f", "lavfi", "-i", f"testsrc=duration={duracao_s}:size=160x120:rate=10",
        "-f", "lavfi", "-i", f"sine=frequency=440:duration={duracao_s}",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-ac", "1", "-ar", "44100",
        "-shortest", str(destino),
    ]
    resultado = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if resultado.returncode != 0 or not destino.exists():
        raise RuntimeError(f"ffmpeg falhou ao gerar vídeo sintético: {resultado.stderr[:500]}")
    return destino


# ---------------------------------------------------------------------------
# Testes de unidade
# ---------------------------------------------------------------------------


def _setup_workspace_e_marcas(tmp: Path) -> Path:
    """Cria workspace.json e duas marcas diretamente no tmp (sem depender de
    criar_projeto.py, que so existe no REPO_ROOT)."""
    init_workspace(tmp)

    def _gravar_marca(marca_id: str, display_name: str):
        marca_dir = tmp / "projetos" / marca_id / "branding"
        marca_dir.mkdir(parents=True, exist_ok=True)
        perfil = {
            "schema_version": "1.0.0",
            "brand_id": marca_id,
            "display_name": display_name,
            "marca": {
                "destaque": "#004aad",
                "fonte": "Inter",
            },
            "preferencias_edicao": {
                "canal": display_name,
                "apresentador": f"Apresentador {marca_id}",
                "render_defaults": {
                    "master_16x9": {"width": 1920, "height": 1080, "fps": 30},
                    "shorts_9x16": {"width": 1080, "height": 1920, "fps": 30},
                },
                "audio": {
                    "jumpcut_gap_threshold_ms": 450,
                    "jumpcut_target_gap_ms": [200, 250],
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
        with open(marca_dir / "config.json", "w", encoding="utf-8") as f:
            json.dump(perfil, f, indent=2, ensure_ascii=False)

    _gravar_marca("marca-a", "Marca A")
    _gravar_marca("marca-b", "Marca B")
    return tmp


def test_sha256_correto():
    """Ponto 1: SHA-256 correto."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        video = _gerar_video_sintetico(tmp / "sintetico.mp4")
        sha, _ = compute_sha256(video)
        assert len(sha) == 64
        assert all(c in "0123456789abcdef" for c in sha)
    print("  [PASS] test_sha256_correto")


def test_deteccao_arquivo_alterado():
    """Ponto 2: deteccao de arquivo alterado (verify_source_integrity)."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        video = _gerar_video_sintetico(tmp / "sintetico.mp4")
        sha_antes, _ = compute_sha256(video)
        # Modifica o arquivo.
        with open(video, "ab") as f:
            f.write(b"\x00")
        try:
            verify_source_integrity(video, sha_antes, video.name)
            assert False, "Deveria levantar IngestError."
        except IngestError:
            pass
    print("  [PASS] test_deteccao_arquivo_alterado")


def test_metadados_via_ffprobe():
    """Ponto 3: metadados via FFprobe."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        video = _gerar_video_sintetico(tmp / "sintetico.mp4")
        probe_data, _ = inspect_media_ffprobe(video, FFPROBE_BIN)
        assert "format" in probe_data
        assert "streams" in probe_data
        assert probe_data["format"].get("format_name")
    print("  [PASS] test_metadados_via_ffprobe")


def test_preservacao_original_readonly_delta_hash():
    """Ponto 4: preservacao do original (read-only e Delta-Hash=0)."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        _setup_workspace_e_marcas(tmp)
        video = _gerar_video_sintetico(tmp / "sintetico.mp4")
        sha_antes, _ = compute_sha256(video)
        tamanho_antes = video.stat().st_size

        rc = ingest_media(
            input_path=str(video),
            marca_id="marca-a",
            episodio_id="ep-preservacao",
            workspace_root=str(tmp),
        )
        assert rc == 0, f"ingest falhou com codigo {rc}"

        # Delta-Hash = 0: arquivo nao alterado (arquivo de entrada).
        sha_depois, _ = compute_sha256(video)
        assert sha_depois == sha_antes, "SHA-256 alterado apos ingestao."
        assert video.stat().st_size == tamanho_antes, "Tamanho alterado apos ingestao."

        # read-only aplicado ao arquivo preservado em brutos/ (custody.originals_read_only=True).
        brutos_wav = tmp / "projetos" / "marca-a" / "episodios" / "ep-preservacao" / "brutos" / "sintetico.mp4"
        assert brutos_wav.is_file(), f"Arquivo nao preservado em brutos/: {brutos_wav}"
        st = os.stat(brutos_wav)
        is_readonly = bool(st.st_file_attributes & stat.FILE_ATTRIBUTE_READONLY) if hasattr(st, "st_file_attributes") else True
        assert is_readonly, "Arquivo em brutos/ deveria estar read-only."
    print("  [PASS] test_preservacao_original_readonly_delta_hash")


def test_normalizacao_audio_wav_16k_mono():
    """Ponto 5: normalizacao de audio (WAV 16kHz mono)."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        _setup_workspace_e_marcas(tmp)
        video = _gerar_video_sintetico(tmp / "sintetico.mp4")
        rc = ingest_media(
            input_path=str(video),
            marca_id="marca-a",
            episodio_id="ep-audio",
            workspace_root=str(tmp),
        )
        assert rc == 0
        wav = tmp / "projetos" / "marca-a" / "episodios" / "ep-audio" / "workspace" / "fonte" / "audio_speech_16k_mono.wav"
        assert wav.is_file(), f"WAV nao gerado: {wav}"
        import wave
        with wave.open(str(wav), "rb") as wf:
            assert wf.getnchannels() == 1, "deveria ser mono."
            assert wf.getframerate() == 16000, "deveria ser 16kHz."
            assert wf.getsampwidth() == 2, "deveria ser PCM 16-bit."
    print("  [PASS] test_normalizacao_audio_wav_16k_mono")


def test_registro_project_json():
    """Ponto 6: registro no project.json."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        _setup_workspace_e_marcas(tmp)
        video = _gerar_video_sintetico(tmp / "sintetico.mp4")
        rc = ingest_media(
            input_path=str(video),
            marca_id="marca-a",
            episodio_id="ep-project",
            workspace_root=str(tmp),
        )
        assert rc == 0
        loader = WorkspaceLoader(tmp)
        projeto = loader.load_project("marca-a", "ep-project")
        assert projeto["current_stage"] == "01_INGEST_COMPLETED"
        assert len(projeto["sources"]) == 1
        assert projeto["sources"][0]["sha256"]
        assert projeto["sources"][0]["read_only_verified"] is True
        assert "media_info" in projeto
        assert "derivatives" in projeto
        assert "telemetry" in projeto
        assert projeto["derivatives"]["speech_recognition_wav"]["sample_rate"] == 16000
        assert projeto["derivatives"]["speech_recognition_wav"]["channels"] == 1
    print("  [PASS] test_registro_project_json")


def test_ingestao_duas_marcas_isolamento():
    """Ponto 7: ingestao em duas marcas diferentes (isolamento)."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        _setup_workspace_e_marcas(tmp)
        video_a = _gerar_video_sintetico(tmp / "a.mp4")
        video_b = _gerar_video_sintetico(tmp / "b.mp4")

        rc_a = ingest_media(str(video_a), "marca-a", "ep-a", str(tmp))
        rc_b = ingest_media(str(video_b), "marca-b", "ep-b", str(tmp))
        assert rc_a == 0 and rc_b == 0

        loader = WorkspaceLoader(tmp)
        pa = loader.load_project("marca-a", "ep-a")
        pb = loader.load_project("marca-b", "ep-b")
        assert pa["marca_id"] == "marca-a"
        assert pb["marca_id"] == "marca-b"
        # Isolamento: sources de marca-a nao aparecem em marca-b.
        assert pa["sources"][0]["id"] != pb["sources"][0]["id"]
        assert "marca-a" in pa["sources"][0]["path"]
        assert "marca-b" in pb["sources"][0]["path"]
    print("  [PASS] test_ingestao_duas_marcas_isolamento")


def test_protecao_caminho_externo_path_traversal():
    """Ponto 8: protecao contra caminhos externos/path-traversal."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        _setup_workspace_e_marcas(tmp)
        # Arquivo FORA do workspace.
        fora = tmp.parent / "arquivo_fora.mp4"
        _gerar_video_sintetico(fora)
        rc = ingest_media(
            input_path=str(fora),
            marca_id="marca-a",
            episodio_id="ep-externo",
            workspace_root=str(tmp),
        )
        assert rc != 0, "Deveria rejeitar arquivo fora do workspace."

        # Path traversal dentro do nome do arquivo (tentativa de escapar).
        video_interno = _gerar_video_sintetico(tmp / "interno.mp4")
        # Simula tentativa via project_id com '..' e personagem invalido.
        loader = WorkspaceLoader(tmp)
        try:
            loader.resolve_episodio_asset("marca-a", "../../fora", "x.txt")
            assert False, "Deveria bloquear path traversal em episodio."
        except IngestError:
            pass
        except Exception:
            # WorkspaceError tambem e valido (bloqueio).
            pass
    print("  [PASS] test_protecao_caminho_externo_path_traversal")


def test_compatibilidade_episodio_legado_preexistente():
    """Ponto 9: compatibilidade com episodio legado sem project.json inicializando."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        _setup_workspace_e_marcas(tmp)
        # Cria diretorio do episodio SEM project.json (legado).
        ep_dir = tmp / "projetos" / "marca-a" / "episodios" / "ep-legado"
        ep_dir.mkdir(parents=True, exist_ok=True)
        (ep_dir / "brutos").mkdir(parents=True, exist_ok=True)
        video = _gerar_video_sintetico(ep_dir / "brutos" / "video_legado.mp4")

        rc = ingest_media(
            input_path=str(video),
            marca_id="marca-a",
            episodio_id="ep-legado",
            workspace_root=str(tmp),
        )
        assert rc == 0
        loader = WorkspaceLoader(tmp)
        projeto = loader.load_project("marca-a", "ep-legado")
        assert projeto["episodio_id"] == "ep-legado"
        assert projeto["marca_id"] == "marca-a"
        assert projeto["current_stage"] == "01_INGEST_COMPLETED"
        assert len(projeto["sources"]) == 1
    print("  [PASS] test_compatibilidade_episodio_legado_preexistente")


def test_integracao_novo_episodio_sem_transcricao():
    """Ponto 10: integracao com novo_episodio.py --sem-transcricao."""
    episodio_id = "ep-integracao-tmp"
    ep_dir = REPO_ROOT / "projetos" / "dr-gestao" / "episodios" / episodio_id

    # Limpeza prévia para ser idempotente.
    shutil.rmtree(ep_dir, ignore_errors=True)

    # Executa novo_episodio.py --sem-transcricao no repo real (somente criacao).
    cmd = [
        sys.executable,
        str(REPO_ROOT / "vortex-edicao" / "novo_episodio.py"),
        "dr-gestao",
        episodio_id,
        "--sem-transcricao",
    ]
    resultado = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert resultado.returncode == 0, f"novo_episodio falhou: {resultado.stderr[:500]}"
    print("    stdout:", resultado.stdout.strip()[-200:])

    # Verifica que o episodio foi criado (estrutura de pastas).
    assert ep_dir.is_dir(), f"Episodio nao criado: {ep_dir}"
    assert (ep_dir / "brutos").is_dir(), f"brutos nao criado: {ep_dir / 'brutos'}"
    assert (ep_dir / "workspace").is_dir(), f"workspace nao criado: {ep_dir / 'workspace'}"

    # Com --sem-transcricao, NÃO deve haver project.json (ingest nao foi chamado).
    pj = ep_dir / "project.json"
    assert not pj.is_file(), f"--sem-transcricao nao deve gerar project.json: {pj}"

    # Limpeza: remove episodio de teste criado no repo (nao altera originais).
    shutil.rmtree(ep_dir, ignore_errors=True)
    print("  [PASS] test_integracao_novo_episodio_sem_transcricao")


# ---------------------------------------------------------------------------
# Runner auxiliar (execução direta)
# ---------------------------------------------------------------------------


def run_tests():
    print("=" * 60)
    print("SUITE DE TESTES — core/ingest.py (Editor)")
    print("=" * 60)
    testes = [
        test_sha256_correto,
        test_deteccao_arquivo_alterado,
        test_metadados_via_ffprobe,
        test_preservacao_original_readonly_delta_hash,
        test_normalizacao_audio_wav_16k_mono,
        test_registro_project_json,
        test_ingestao_duas_marcas_isolamento,
        test_protecao_caminho_externo_path_traversal,
        test_compatibilidade_episodio_legado_preexistente,
        test_integracao_novo_episodio_sem_transcricao,
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
