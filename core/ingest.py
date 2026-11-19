"""
core/ingest.py

Modulo de ingestao de audio adaptado seletivamente de
D:\Drifit\Editor\core\ingest.py ao Workspace Core e
a estrutura canonica do legado (projetos/<marca>/episodios/<episodio>/).

Responsabilidades:
- Preservar o original em projetos/<marca>/episodios/<episodio>/brutos/
  (sem duplicar se ja estiver em brutos/ e sem alterar o arquivo de origem).
- Calcular SHA-256 antes e depois (Delta-Hash = 0) e atributo read-only
  quando custody.originals_read_only=True.
- Inspecionar via ffprobe (container, duracao, resolucao, codecs, streams).
- Extrair audio normalizado WAV 16kHz mono para
  episodios/<episodio>/workspace/fonte/audio_speech_16k_mono.wav
  (e media_info.json + ingest.log em workspace/fonte/).
- Atualizar project.json na raiz do episodio (sources, artifacts,
  media_info, derivatives, telemetry, current_stage='01_INGEST_COMPLETED').
- verify_source_integrity() para detectar arquivo alterado por SHA-256.
- Contenca estrita em workspace_root (sem gravacoes externas).
- Aceita episodios legados sem project.json inicializando-o se necessario.

Nao modifica o arquivo original. Nao hardcodeia marca ou episodio.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import shutil
import stat
import subprocess
import sys
import time
import wave
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

# Import relativo do pacote core
try:
    from .workspace import WorkspaceLoader, WorkspaceError, _resolve_within
except ImportError:  # execucao direta como script
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from core.workspace import WorkspaceLoader, WorkspaceError, _resolve_within  # type: ignore


class IngestError(Exception):
    """Erro de ingestao de mídia."""


# ---------------------------------------------------------------------------
# Utilitarios (reutilizados do Editor legado/core/ingest.py)
# ---------------------------------------------------------------------------


def compute_sha256(file_path: Path, chunk_size: int = 65536) -> Tuple[str, float]:
    """Calcula SHA-256 lendo em blocos para manter RAM baixa."""
    hasher = hashlib.sha256()
    t0 = time.perf_counter()
    with open(file_path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            hasher.update(chunk)
    elapsed = time.perf_counter() - t0
    return hasher.hexdigest(), elapsed


def inspect_media_ffprobe(file_path: Path, ffprobe_bin: str) -> Tuple[Dict[str, Any], float]:
    """Inspeciona container/streams via ffprobe."""
    cmd = [
        ffprobe_bin, "-v", "quiet", "-print_format", "json",
        "-show_format", "-show_streams", str(file_path),
    ]
    t0 = time.perf_counter()
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    elapsed = time.perf_counter() - t0
    if result.returncode != 0 or not result.stdout.strip():
        raise IngestError(
            f"Falha na inspecao FFprobe do contêiner. Arquivo pode estar corrompido. "
            f"Erro: {result.stderr.strip()}"
        )
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise IngestError(f"Saída do FFprobe não é JSON válido: {e}")
    return data, elapsed


def check_os_protection(file_path: Path, ensure_readonly: bool = False) -> Dict[str, Any]:
    """Verifica integridade e atributo read-only do arquivo no SO."""
    st = os.stat(file_path)
    is_readonly_attr = False
    if hasattr(st, "st_file_attributes"):
        is_readonly_attr = bool(st.st_file_attributes & stat.FILE_ATTRIBUTE_READONLY)
        if ensure_readonly and not is_readonly_attr:
            try:
                os.chmod(file_path, stat.S_IREAD)
                st = file_path.stat()
                is_readonly_attr = bool(st.st_file_attributes & stat.FILE_ATTRIBUTE_READONLY)
            except Exception:
                pass
    can_write = os.access(file_path, os.W_OK)
    return {
        "file_size_bytes": st.st_size,
        "mtime_epoch": st.st_mtime,
        "is_readonly_attribute": is_readonly_attr,
        "os_write_permission": can_write,
        "read_mode": "rb (Strict Read-Only Binary)",
    }


def extract_speech_audio(
    input_video: Path, output_wav: Path, ffmpeg_bin: str, stream_index: int = 0
) -> Tuple[Dict[str, Any], float]:
    """Extrai áudio da stream selecionada para WAV PCM 16kHz mono."""
    output_wav.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        ffmpeg_bin, "-y", "-i", str(input_video),
        "-map", f"0:a:{stream_index}",
        "-vn", "-acodec", "pcm_s16le",
        "-ar", "16000", "-ac", "1", str(output_wav),
    ]
    t0 = time.perf_counter()
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    elapsed = time.perf_counter() - t0
    if result.returncode != 0 or not output_wav.exists() or output_wav.stat().st_size == 0:
        raise IngestError(f"Falha na extração de áudio via FFmpeg: {result.stderr.strip()}")
    with wave.open(str(output_wav), "rb") as wf:
        nchannels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        framerate = wf.getframerate()
        nframes = wf.getnframes()
        duration = nframes / float(framerate) if framerate > 0 else 0.0
        sample_frames = min(nframes, framerate * 5)
        raw_samples = wf.readframes(sample_frames)
        rms = 0.0
        if raw_samples and sampwidth == 2:
            import struct
            count = len(raw_samples) // 2
            shorts = struct.unpack(f"<{count}h", raw_samples)
            sum_sq = sum(s * s for s in shorts)
            mean_sq = sum_sq / count if count > 0 else 0
            rms = math.sqrt(mean_sq)
    return {
        "channels": nchannels,
        "sample_width_bytes": sampwidth,
        "sample_rate_hz": framerate,
        "duration_seconds": round(duration, 3),
        "file_size_bytes": output_wav.stat().st_size,
        "estimated_rms": round(rms, 2),
        "is_silent_amplitude": bool(rms < 10.0),
    }, elapsed


def check_tool(tool_name: str, workspace_root: str | Path) -> str:
    """Localiza ferramenta essencial no PATH ou dentro do workspace
    em tools/hyperframes/bin/windows-x64/."""
    path = shutil.which(tool_name)
    if path:
        return path
    # Fallback: ferramenta embarcada no workspace (tools/hyperframes/...).
    root = Path(workspace_root).resolve()
    embedded = root / "tools" / "hyperframes" / "bin" / "windows-x64" / tool_name
    if embedded.is_file():
        return str(embedded)
    raise IngestError(
        f"Ferramenta essencial '{tool_name}' não encontrada no PATH nem em "
        f"{embedded}. Instale FFmpeg/FFprobe."
    )


# ---------------------------------------------------------------------------
# Ingestao
# ---------------------------------------------------------------------------


def setup_logger(log_file: Path = None) -> logging.Logger:
    logger = logging.getLogger("CORE-INGEST")
    logger.setLevel(logging.INFO)
    # Fecha handlers existentes para nao deixar arquivos abertos (Windows lock).
    for h in list(logger.handlers):
        try:
            h.close()
        except Exception:
            pass
        logger.removeHandler(h)
    logger.handlers.clear()
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setFormatter(formatter)
        logger.addHandler(fh)
    return logger


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_or_init_project(
    loader: WorkspaceLoader, marca_id: str, episodio_id: str
) -> Tuple[Dict[str, Any], Path]:
    """Carrega project.json do episodio ou inicializa se nao existir (legado)."""
    loader.load_workspace()
    loader.load_brand_profile(marca_id)  # garante marca existente
    pj_path = loader.project_file(marca_id, episodio_id)
    if pj_path.is_file():
        with open(pj_path, "r", encoding="utf-8") as f:
            projeto = json.load(f)
    else:
        # Inicializa project.json minimo (episodio legado).
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
        pj_path.parent.mkdir(parents=True, exist_ok=True)
        with open(pj_path, "w", encoding="utf-8") as f:
            json.dump(projeto, f, indent=2, ensure_ascii=False)
    return projeto, pj_path


def _gravar_project_json(pj_path: Path, projeto: Dict[str, Any]) -> None:
    """Grava project.json na raiz do episodio (caminho absoluto)."""
    pj_path.parent.mkdir(parents=True, exist_ok=True)
    with open(pj_path, "w", encoding="utf-8") as f:
        json.dump(projeto, f, indent=2, ensure_ascii=False)


def _extrair_media_info(probe_data: Dict[str, Any]) -> Dict[str, Any]:
    """Extrai metadados resumidos da saida do ffprobe."""
    fmt = probe_data.get("format", {})
    streams = probe_data.get("streams", [])
    video_streams = [s for s in streams if s.get("codec_type") == "video"]
    audio_streams = [s for s in streams if s.get("codec_type") == "audio"]

    vid_info = {}
    if video_streams:
        v0 = video_streams[0]
        r_fps = v0.get("r_frame_rate", "30/1")
        try:
            num, den = map(float, r_fps.split("/"))
            fps_val = round(num / den, 2) if den > 0 else 30.0
        except Exception:
            fps_val = 30.0
        vid_info = {
            "codec": v0.get("codec_name"),
            "width": v0.get("width"),
            "height": v0.get("height"),
            "fps": fps_val,
            "pix_fmt": v0.get("pix_fmt"),
            "duration_seconds": float(v0.get("duration", fmt.get("duration", 0.0))),
        }

    audio_summary = []
    for idx, a_stream in enumerate(audio_streams):
        audio_summary.append({
            "stream_index": idx,
            "codec": a_stream.get("codec_name"),
            "sample_rate": int(a_stream.get("sample_rate", 48000)),
            "channels": int(a_stream.get("channels", 2)),
            "channel_layout": a_stream.get("channel_layout", "unknown"),
            "duration_seconds": float(a_stream.get("duration", fmt.get("duration", 0.0))),
            "start_time_seconds": float(a_stream.get("start_time", 0.0)),
        })

    return {
        "container_format": fmt.get("format_name"),
        "duration_seconds": float(fmt.get("duration", 0.0)),
        "video": vid_info,
        "audio_streams": audio_summary,
    }


def verify_source_integrity(
    arquivo: Path, sha_esperado: str, nome_arquivo: str
) -> None:
    """Valida o hash atual do arquivo em brutos/ contra o SHA-256 registrado.

    Levanta IngestError se o arquivo em brutos/ foi alterado apos a copia
    (hash atual diferente do registrado no project.json).
    """
    sha_atual, _ = compute_sha256(arquivo)
    if sha_atual != sha_esperado:
        raise IngestError(
            f"INTEGRIDADE COMPROMETIDA: {nome_arquivo} foi alterado apos a "
            f"ingestao (hash registrado={sha_esperado} hash atual={sha_atual})."
        )


def ingest_media(
    input_path: str,
    marca_id: str,
    episodio_id: str,
    workspace_root: str | Path,
    gravacao_ja_copiada: bool = False,
) -> int:
    """
    Executa ingestao completa para um episodio.

    - Preserva o original em projetos/<marca>/episodios/<episodio>/brutos/
      (sem duplicar se ja estiver em brutos/ e sem alterar o arquivo de origem).
    - Calcula SHA-256 antes e depois (Delta-Hash = 0) e atributo read-only
      quando custody.originals_read_only=True.
    - Inspeciona via ffprobe.
    - Extrai audio WAV 16kHz mono para episodios/<episodio>/workspace/fonte/.
    - Atualiza project.json na raiz do episodio.
    Retorna 0 em sucesso, codigo != 0 em falha.
    """
    t_start_total = time.perf_counter()
    loader = WorkspaceLoader(workspace_root)
    loader.load_workspace()
    custody = loader.workspace.get("custody", {})
    originals_read_only = bool(custody.get("originals_read_only", True))

    in_file = Path(input_path).resolve()
    if not in_file.exists() or not in_file.is_file():
        print(f"[ERRO CRÍTICO] Arquivo de entrada não encontrado: {input_path}", file=sys.stderr)
        return 1

    # Contenca: arquivo de entrada deve estar dentro do workspace_root.
    try:
        in_file.relative_to(loader.workspace_root.resolve())
    except ValueError:
        print(
            f"[ERRO CRÍTICO] Arquivo de entrada fora do workspace: {in_file}",
            file=sys.stderr,
        )
        return 1

    # Carrega ou inicializa project.json (episodio legado).
    projeto, pj_path = _load_or_init_project(loader, marca_id, episodio_id)

    # Diretorio brutos do episodio.
    brutos_dir = loader.resolve_episodio_asset(marca_id, episodio_id, "brutos")
    brutos_dir.mkdir(parents=True, exist_ok=True)

    # Destino final no brutos (sem duplicar se ja estiver la).
    brutos_dest = brutos_dir / in_file.name
    copia_necessaria = not brutos_dest.exists() or brutos_dest.resolve() != in_file.resolve()

    # Gate de integridade: hash da origem ANTES de copiar.
    origin_sha256, _ = compute_sha256(in_file)

    # Se ja existe em brutos e é o mesmo arquivo, nao copia.
    if brutos_dest.exists() and not copia_necessaria:
        trabalho = brutos_dest
        # validacao de integridade do brutos existente contra a origem.
        brutos_sha256, _ = compute_sha256(brutos_dest)
        if brutos_sha256 != origin_sha256:
            raise IngestError(
                f"INTEGRIDADE COMPROMETIDA: brutos/{brutos_dest.name} (sha256="
                f"{brutos_sha256}) difere da origem {in_file.name} (sha256="
                f"{origin_sha256})."
            )
        copy_hash_verified = True
    else:
        # Copia o original para brutos (nao altera o arquivo de origem).
        shutil.copy2(str(in_file), str(brutos_dest))
        trabalho = brutos_dest
        # Valida que a copia em brutos e identica à origem (hash a hash).
        brutos_sha256, _ = compute_sha256(brutos_dest)
        if brutos_sha256 != origin_sha256:
            raise IngestError(
                f"INTEGRIDADE COMPROMETIDA: copia em brutos/ (sha256="
                f"{brutos_sha256}) difere da origem {in_file.name} (sha256="
                f"{origin_sha256})."
            )
        copy_hash_verified = True

    # Log de ingestao.
    log_dir = loader.resolve_episodio_asset(marca_id, episodio_id, "workspace/fonte/logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "ingest.log"
    logger = setup_logger(log_file)
    logger.info("=" * 60)
    logger.info("INICIANDO INGESTÃO DE MÍDIA — CORE-INGEST (Editor)")
    logger.info("=" * 60)
    logger.info(f"Arquivo de Origem: {in_file}")
    logger.info(f"Destino brutos: {trabalho}")
    logger.info(f"Marca: {marca_id} | Episodio: {episodio_id}")

    # 1. Binários essenciais (ffmpeg/ffprobe, inclusive embarcado no workspace).
    try:
        ffmpeg_bin = check_tool("ffmpeg", loader.workspace_root)
        ffprobe_bin = check_tool("ffprobe", loader.workspace_root)
    except IngestError as e:
        logger.error(str(e))
        return 1

    # 2. Protecao do SO e hash SHA-256 ANTES.
    pre_prot = check_os_protection(trabalho)
    logger.info(f"Tamanho do Arquivo Bruto: {pre_prot['file_size_bytes']:,} bytes")
    logger.info(f"Protecao Atributo Read-Only: {pre_prot['is_readonly_attribute']}")
    logger.info("Calculando hash SHA-256 do arquivo original (leitura em chunks de 64KB)...")
    pre_sha, t_hash = compute_sha256(trabalho)
    logger.info(f"Hash SHA-256: {pre_sha} (Tempo: {t_hash:.2f}s)")

    # 3. Inspecao via FFprobe.
    logger.info("Inspecionando contêiner e streams de mídia via FFprobe...")
    try:
        probe_data, t_probe = inspect_media_ffprobe(trabalho, ffprobe_bin)
    except IngestError as e:
        logger.error(f"[FALHA NA INSPEÇÃO] {e}")
        return 2

    media_info = _extrair_media_info(probe_data)
    logger.info(
        f"Contêiner: {media_info['container_format']} | "
        f"Streams: {len(media_info['video'])} vídeo, {len(media_info['audio_streams'])} áudio"
    )

    if not media_info["video"] and not media_info["audio_streams"]:
        logger.error("O arquivo não possui streams de vídeo nem de áudio válidos.")
        return 2

    # 4. Extração de derivado de áudio WAV 16kHz mono.
    fonte_dir = loader.resolve_episodio_asset(marca_id, episodio_id, "workspace/fonte")
    fonte_dir.mkdir(parents=True, exist_ok=True)
    target_wav = fonte_dir / "audio_speech_16k_mono.wav"

    t_audio_extract = 0.0
    audio_streams = media_info.get("audio_streams", [])
    if audio_streams:
        logger.info(f"Extraindo derivado de fala para Whisper (Stream 0): {target_wav.name}...")
        try:
            wav_meta, t_audio_extract = extract_speech_audio(
                trabalho, target_wav, ffmpeg_bin, stream_index=0
            )
            logger.info(
                f"Áudio Derivado Gerado: {wav_meta['sample_rate_hz']}Hz, "
                f"{wav_meta['channels']} canal(is), duração: {wav_meta['duration_seconds']}s "
                f"(Tempo extração: {t_audio_extract:.2f}s)"
            )
        except IngestError as e:
            logger.error(f"[FALHA NA EXTRAÇÃO DE ÁUDIO] {e}")
            return 3
    else:
        logger.warning("[AVISO] Nenhuma faixa de áudio encontrada. Derivado de fala não gerado.")
        wav_meta = {}

    # 5. Verificação de integridade pós-processamento (Delta-Hash = 0).
    post_prot = check_os_protection(trabalho, ensure_readonly=True)
    logger.info("Validando integridade pós-ingestão do arquivo original...")
    verify_source_integrity(trabalho, brutos_sha256, trabalho.name)
    logger.info(f"Integridade do Arquivo Original Confirmada (Delta-Hash = 0): {pre_sha}")

    # 6. Aplicar atributo read-only se custody exigir.
    if originals_read_only and not post_prot["is_readonly_attribute"]:
        try:
            os.chmod(trabalho, stat.S_IREAD)
            post_prot = check_os_protection(trabalho, ensure_readonly=True)
            logger.info(f"Atributo read-only aplicado em: {trabalho}")
        except Exception as exc:
            logger.warning(f"Não foi possível aplicar read-only: {exc}")

    # 7. Atualizar project.json.
    t_total = time.perf_counter() - t_start_total
    source_entry = {
        "id": f"SRC_{trabalho.stem.upper()}",
        "origin_path": str(in_file),
        "origin_sha256": origin_sha256,
        "path": str(trabalho),
        "sha256": brutos_sha256,
        "copy_hash_verified": copy_hash_verified,
        "bytes": pre_prot["file_size_bytes"],
        "duration_s": float(media_info.get("duration_seconds", 0.0)),
        "read_only_verified": bool(post_prot["is_readonly_attribute"]),
        "ingested_at": _iso_now(),
    }

    projeto["sources"] = [source_entry]
    projeto["current_stage"] = "01_INGEST_COMPLETED"
    projeto["updated_at"] = _iso_now()
    projeto["artifacts"]["01_ingest"] = {
        "wav_16k": "workspace/fonte/audio_speech_16k_mono.wav",
        "wav_48k": "workspace/fonte/audio_program_48k.wav",
        "ffprobe": "workspace/fonte/media_info.json",
    }
    projeto["media_info"] = media_info
    projeto["telemetry"] = {
        "time_hash_seconds": round(t_hash, 3),
        "time_probe_seconds": round(t_probe, 3),
        "time_audio_extract_seconds": round(t_audio_extract, 3),
        "time_total_wallclock_seconds": round(t_total, 3),
    }
    projeto["derivatives"] = {}
    if audio_streams:
        projeto["derivatives"]["speech_recognition_wav"] = {
            "relative_path": "workspace/fonte/audio_speech_16k_mono.wav",
            "format": "WAV_PCM_S16LE",
            "sample_rate": 16000,
            "channels": 1,
            "duration_seconds": wav_meta.get("duration_seconds"),
            "source_stream_index": 0,
            "is_silent_detected": wav_meta.get("is_silent_amplitude", False),
        }
    projeto["status"] = "INGEST_COMPLETED"

    _gravar_project_json(pj_path, projeto)

    # Grava media_info.json em workspace/fonte/.
    media_info_path = fonte_dir / "media_info.json"
    with open(media_info_path, "w", encoding="utf-8") as f:
        json.dump(probe_data, f, indent=2, ensure_ascii=False)

    # Mensagens finais ANTES de fechar handlers (liberar locks do Windows).
    logger.info(f"project.json atualizado: {pj_path}")
    logger.info("=" * 60)
    logger.info(f"INGESTÃO CONCLUÍDA COM SUCESSO EM {t_total:.2f}s!")
    logger.info("=" * 60)

    # Fecha e remove TODOS os FileHandlers de todos os loggers para liberar
    # arquivos bloqueados no Windows antes de retornar ao chamador.
    for _logger in [logger, logging.getLogger()]:
        for handler in list(_logger.handlers):
            if isinstance(handler, logging.FileHandler):
                try:
                    handler.close()
                except Exception:
                    pass
            try:
                _logger.removeHandler(handler)
            except ValueError:
                pass

    return 0


def main() -> None:
    parser = __import__("argparse").ArgumentParser(
        description="CORE-INGEST: Módulo de Ingestão Agnóstico do Editor (Editor)."
    )
    parser.add_argument("-i", "--input", required=True, help="Caminho do arquivo de vídeo original.")
    parser.add_argument("-m", "--marca-id", required=True, help="ID da marca (ex: dr-gestao).")
    parser.add_argument("-e", "--episodio-id", required=True, help="ID do episódio (ex: EP-01).")
    parser.add_argument("-w", "--workspace-root", default="D:/Drifit/Editor", help="Raiz do workspace.")
    args = parser.parse_args()
    sys.exit(
        ingest_media(args.input, args.marca_id, args.episodio_id, args.workspace_root)
    )


if __name__ == "__main__":
    main()
