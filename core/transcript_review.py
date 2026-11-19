# -*- coding: utf-8 -*-
"""core/transcript_review.py

Revisao humana de transcriptos do Whisper e registro de benchmark de
transcricao. Tudo sem sobrescrever o `transcript.json` original (leitura
apenas) e sem calcular WER/acuracia quando nao ha ground truth integral.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_REVIEWED_BY = "proprietario"
DEFAULT_REVIEWED_VERSION = "1.0.0"


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _carregar_transcript(transcript_path: Path) -> Dict[str, Any]:
    """Carrega transcript.json apenas para leitura."""
    with open(transcript_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _indice_por_segment_id(segments: List[Dict[str, Any]]) -> Dict[int, int]:
    """Mapeia segment.id -> indice na lista."""
    indice: Dict[int, int] = {}
    for idx, seg in enumerate(segments):
        sid = seg.get("id")
        if sid is not None:
            try:
                indice[int(sid)] = idx
            except (TypeError, ValueError):
                continue
    return indice


def _extrair_tokens(segment: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extrai tokens (palavras) de um segmento, preservando probability."""
    tokens: List[Dict[str, Any]] = []
    for w in segment.get("words", []) or []:
        tokens.append(
            {
                "word": w.get("word", w.get("w", "")),
                "start": float(w.get("start", w.get("t", 0.0))),
                "end": float(w.get("end", w.get("f", 0.0))),
                "probability": w.get("probability"),
            }
        )
    return tokens


class TranscriptReviewError(Exception):
    """Erro na resolucao/validacao de transcrição editorial revisada.

    Levantado quando transcript_reviewed.json está ausente de metadados
    obrigatórios, corrompido, incompatível ou desatualizado em relação ao
    transcript.json original. Nunca cai silenciosamente em dados errados.
    """


# ---------------------------------------------------------------------------
# Helpers internos adicionais
# ---------------------------------------------------------------------------


def _extrair_words_de_segments(segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Extrai palavras (w, t, f, probability) de uma lista de segmentos.

    Se o segmento foi revisado por humano (human_reviewed=True) e nao tem
    `words` ou elas estao dessincronizadas com `text`, nao prefere tokens
    antigos nao revisados — simplesmente ignora o segmento (nao ha palavras
    confiaveis a extrair) ou recria a partir do texto quando possivel.
    """
    words: List[Dict[str, Any]] = []
    for seg in segments:
        seg_words = seg.get("words", []) or []
        if seg.get("human_reviewed") and not seg_words:
            # Segmento revisado sem words: nao ha tokens antigos confiaveis.
            continue
        for w in seg_words:
            words.append(
                {
                    "w": w.get("word", w.get("w", "")),
                    "t": float(w.get("start", w.get("t", 0.0))),
                    "f": float(w.get("end", w.get("f", 0.0))),
                    "probability": w.get("probability"),
                }
            )
    return words


# ---------------------------------------------------------------------------
# resolve_editorial_transcript
# ---------------------------------------------------------------------------


def resolve_editorial_transcript(fonte_dir: str | Path) -> Dict[str, Any]:
    """Resolve a versao canonica da transcrição editorial para o episódio.

    Verifica transcript.json (obrigatório; calcula SHA-256 atual) e, se
    existir, transcript_reviewed.json. NUNCA sobrescreve transcript.json.

    Se transcript_reviewed.json NAO existir: retorna dados do transcript.json
    original com source_kind="raw_transcript".

    Se existir: valida estritamente:
      - review_metadata.base_transcript_sha256 == SHA-256 atual de transcript.json
        (se divergir -> TranscriptReviewError: revisão desatualizada);
      - estrutura valida com reviewed_result.segments (lista não vazia) e
        review_metadata.reviewed_by / reviewed_version;
      - se corrompido ou incompatível -> TranscriptReviewError.

    Retorna dicionário normalizado com:
      segments, words, source_kind, transcript_path, transcript_sha256,
      base_transcript_sha256, reviewed_by, reviewed_at, reviewed_version.
    """
    fonte_dir = Path(fonte_dir)
    transcript_path = fonte_dir / "transcript.json"
    reviewed_path = fonte_dir / "transcript_reviewed.json"

    if not transcript_path.is_file():
        raise TranscriptReviewError(
            f"transcript.json obrigatório não encontrado: {transcript_path}"
        )

    transcript_sha = _sha256_file(transcript_path)

    # Nenhuma revisão: retorna dados originais do transcript.json.
    if not reviewed_path.is_file():
        transcript_data = _carregar_transcript(transcript_path)
        segments = transcript_data.get("segments", []) if isinstance(transcript_data, dict) else []
        words = _extrair_words_de_segments(segments)
        return {
            "segments": segments,
            "words": words,
            "source_kind": "raw_transcript",
            "transcript_path": str(transcript_path),
            "transcript_sha256": transcript_sha,
        }

    # Existe revisão: validar estritamente.
    try:
        reviewed_data = _carregar_transcript(reviewed_path)
    except (json.JSONDecodeError, OSError) as exc:
        raise TranscriptReviewError(
            f"transcript_reviewed.json corrompido ou ilegível: {reviewed_path} ({exc})"
        ) from exc

    if not isinstance(reviewed_data, dict):
        raise TranscriptReviewError(
            f"transcript_reviewed.json não é um objeto JSON válido: {reviewed_path}"
        )

    # review_metadata / reviewed_result vivem no nível superior do arquivo
    # (estrutura gravada por review_transcript).
    base_sha = reviewed_data.get("source_transcript_sha256")
    if base_sha is None:
        raise TranscriptReviewError(
            f"transcript_reviewed.json sem source_transcript_sha256: {reviewed_path}"
        )
    if str(base_sha) != str(transcript_sha):
        raise TranscriptReviewError(
            "Revisão desatualizada: source_transcript_sha256="
            f"{base_sha} != SHA-256 atual de transcript.json={transcript_sha} "
            f"em {reviewed_path}"
        )

    reviewed_by = reviewed_data.get("reviewed_by")
    reviewed_version = reviewed_data.get("reviewed_version")
    if not reviewed_by or not reviewed_version:
        raise TranscriptReviewError(
            "transcript_reviewed.json com metadados incompletos "
            f"(reviewed_by={reviewed_by!r}, reviewed_version={reviewed_version!r}): "
            f"{reviewed_path}"
        )

    segments = reviewed_data.get("segments")
    if not isinstance(segments, list) or len(segments) == 0:
        raise TranscriptReviewError(
            f"transcript_reviewed.json segments vazia ou inválida: {reviewed_path}"
        )

    # Valida que cada segmento tem start/end/text mínimos.
    for seg in segments:
        if not isinstance(seg, dict):
            raise TranscriptReviewError(
                f"transcript_reviewed.json segmento inválido (não é objeto): {reviewed_path}"
            )
        if "start" not in seg or "end" not in seg:
            raise TranscriptReviewError(
                f"transcript_reviewed.json segmento sem start/end: {reviewed_path}"
            )

    words = _extrair_words_de_segments(segments)

    return {
        "segments": segments,
        "words": words,
        "source_kind": "reviewed_transcript",
        "transcript_path": str(transcript_path),
        "transcript_sha256": transcript_sha,
        "base_transcript_sha256": base_sha,
        "reviewed_by": reviewed_by,
        "reviewed_at": reviewed_data.get("reviewed_at"),
        "reviewed_version": reviewed_version,
    }


# ---------------------------------------------------------------------------
# sync_alignment_with_editorial_transcript
# ---------------------------------------------------------------------------


def sync_alignment_with_editorial_transcript(
    fonte_dir: str | Path,
    silence_guard_ms: int = 200,
) -> Dict[str, Any]:
    """Reconstroi alignment.json (e palavras.json/roteiro.txt) a partir da
    transcrição editorial resolvida, sem nunca sobrescrever transcript.json.

    Usa resolve_editorial_transcript(fonte_dir) para obter as palavras
    (revisadas se válidas, senão originais) e constrói o alinhamento com
    build_alignment_from_words (core/analyze.py).

    Retorna dicionário com:
      alignment, source_kind, transcript_sha256, base_transcript_sha256,
      reviewed_by, reviewed_at, reviewed_version.
    """
    from core.analyze import build_alignment_from_words  # import lazy (evita circular)

    fonte_dir = Path(fonte_dir)
    editorial = resolve_editorial_transcript(fonte_dir)
    words = editorial["words"]

    if not words:
        raise TranscriptReviewError(
            f"Nenhuma palavra encontrada na transcrição editorial de {fonte_dir}"
        )

    marca_profile_config = {
        "audio": {"silence_guard_ms": [silence_guard_ms, silence_guard_ms]}
    }

    wav_path = fonte_dir / "audio_speech_16k_mono.wav"
    alinhamento = build_alignment_from_words(
        words,
        marca_profile_config,
        audio_wav_path=wav_path if wav_path.exists() else None,
        pre_roll_ms=100,
        post_roll_ms=200,
        total_audio_duration=None,
    )

    # Escreve alignment.json (não toca em transcript.json).
    alinhamento_path = fonte_dir / "alignment.json"
    alinhamento_path.parent.mkdir(parents=True, exist_ok=True)
    with open(alinhamento_path, "w", encoding="utf-8") as f:
        json.dump(alinhamento, f, indent=2, ensure_ascii=False)

    # Escreve palavras.json (legado).
    palavras_legacy = [{"w": w["w"], "t": w["t"], "f": w["f"]} for w in words]
    (fonte_dir / "palavras.json").write_text(
        json.dumps(palavras_legacy, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # Escreve roteiro.txt (legado).
    linhas: List[str] = []
    cur: List[Dict[str, Any]] = []
    for i, p in enumerate(palavras_legacy):
        cur.append(p)
        pausa = (
            (palavras_legacy[i + 1]["t"] - p["f"])
            if i + 1 < len(palavras_legacy)
            else 9
        )
        if p["w"][-1:] in ".?!" or pausa > 0.6:
            linhas.append(
                f'[{cur[0]["t"]:8.2f} – {cur[-1]["f"]:8.2f}]  '
                + " ".join(x["w"] for x in cur)
            )
            cur = []
    if cur:
        linhas.append(
            f'[{cur[0]["t"]:8.2f} – {cur[-1]["f"]:8.2f}]  '
            + " ".join(x["w"] for x in cur)
        )
    (fonte_dir / "roteiro.txt").write_text("\n".join(linhas) + "\n", encoding="utf-8")

    return {
        "alignment": alinhamento,
        "source_kind": editorial["source_kind"],
        "transcript_sha256": editorial.get("transcript_sha256"),
        "base_transcript_sha256": editorial.get("base_transcript_sha256"),
        "reviewed_by": editorial.get("reviewed_by"),
        "reviewed_at": editorial.get("reviewed_at"),
        "reviewed_version": editorial.get("reviewed_version"),
    }



def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _carregar_transcript(transcript_path: Path) -> Dict[str, Any]:
    """Carrega transcript.json apenas para leitura."""
    with open(transcript_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _indice_por_segment_id(segments: List[Dict[str, Any]]) -> Dict[int, int]:
    """Mapeia segment.id -> indice na lista."""
    indice: Dict[int, int] = {}
    for idx, seg in enumerate(segments):
        sid = seg.get("id")
        if sid is not None:
            try:
                indice[int(sid)] = idx
            except (TypeError, ValueError):
                continue
    return indice


def _extrair_tokens(segment: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extrai tokens (palavras) de um segmento, preservando probability."""
    tokens: List[Dict[str, Any]] = []
    for w in segment.get("words", []) or []:
        tokens.append(
            {
                "word": w.get("word", w.get("w", "")),
                "start": float(w.get("start", w.get("t", 0.0))),
                "end": float(w.get("end", w.get("f", 0.0))),
                "probability": w.get("probability"),
            }
        )
    return tokens


def _reconstruir_palavras_corrigidas(
    corrected_text: str,
    start: float,
    end: float,
    original_tokens: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Reconstrói a lista de `words` a partir do texto corrigido pelo humano.

    Regras:
      - 1 palavra corrigida + 1 token original -> mapeamento 1:1 seguro:
        usa start/end originais e probability original apenas se a palavra
        nao foi alterada; senao probability=None (não fabrica confiança).
      - N palavras corrigidas em 1 segmento -> distribui no intervalo
        [start, end] do segmento, probability=None (palavras substituídas).
      - Quando o número de palavras corrigidas é igual ao número de tokens
        originais e cada palavra corresponde (case-insensitive), mapeia 1:1
        preservando timestamps e probabilities originais.
      - Nunca inventa probability: usa None quando a palavra foi substituída.
    """
    palavras_corrigidas = [w for w in corrected_text.strip().split() if w]
    if not palavras_corrigidas:
        return []

    n = len(palavras_corrigidas)
    duracao = end - start

    # Caso 1: mapeamento 1:1 com tokens originais (mesmo número de palavras
    # e correspondência case-insensitive). Preserva timestamps e probabilities.
    if n == len(original_tokens) and n > 0:
        palavras: List[Dict[str, Any]] = []
        todos_correspondem = True
        for i, (palavra_corrigida, token_orig) in enumerate(
            zip(palavras_corrigidas, original_tokens)
        ):
            mesma = (
                token_orig["word"].strip().lower()
                == palavra_corrigida.strip().lower()
            )
            if not mesma:
                todos_correspondem = False
                break
        if todos_correspondem:
            for palavra_corrigida, token_orig in zip(
                palavras_corrigidas, original_tokens
            ):
                palavras.append(
                    {
                        "word": palavra_corrigida,
                        "start": token_orig["start"],
                        "end": token_orig["end"],
                        "probability": token_orig["probability"],
                    }
                )
            return palavras

    # Caso 2: 1 palavra corrigida, 1 token original -> mapeamento 1:1 seguro
    # (usa start/end originais; probability original apenas se mesma palavra).
    if n == 1 and len(original_tokens) == 1:
        orig = original_tokens[0]
        mesma_palavra = (
            orig["word"].strip().lower() == palavras_corrigidas[0].strip().lower()
        )
        return [
            {
                "word": palavras_corrigidas[0],
                "start": orig["start"],
                "end": orig["end"],
                "probability": orig["probability"] if mesma_palavra else None,
            }
        ]

    # Caso geral: distribuir palavras no intervalo [start, end].
    palavras: List[Dict[str, Any]] = []
    for i, palavra in enumerate(palavras_corrigidas):
        w_start = round(start + (i / n) * duracao, 3)
        w_end = round(start + ((i + 1) / n) * duracao, 3)
        palavras.append(
            {
                "word": palavra,
                "start": w_start,
                "end": w_end,
                "probability": None,
            }
        )
    return palavras


# ---------------------------------------------------------------------------
# review_transcript
# ---------------------------------------------------------------------------


def review_transcript(
    transcript_path: str | Path,
    corrections: List[Dict[str, Any]],
    *,
    output_path: Optional[str | Path] = None,
    report_path: Optional[str | Path] = None,
    reviewed_by: str = DEFAULT_REVIEWED_BY,
    reviewed_at: Optional[str] = None,
    reviewed_version: str = DEFAULT_REVIEWED_VERSION,
) -> Dict[str, Any]:
    """Aplica correcoes humanas pontuais a um transcript.json (somente leitura).

    NUNCA sobrescreve o `transcript.json` original. Grava
    `transcript_reviewed.json` (ou `output_path` se informado) e, opcionalmente,
    `corrections_report.json` (ou `report_path` se informado).

    Parametros
    ----------
    transcript_path:
        Caminho do transcript.json original (somente leitura).
    corrections:
        Lista de correcoes pontuais. Cada item pode conter:
          - `segment_ids`: lista de ids de segmentos/tokens a agrupar e corrigir
          - `segment_id`: id de um unico segmento/token a corrigir
          - `corrected_text`: texto corrigido (obrigatorio)
          - `reason` / `category`: metadados opcionais da correcao
    output_path:
        Caminho de saida do transcript revisado. Default:
        <pasta do transcript>/transcript_reviewed.json.
        Se apontar para o proprio transcript.json, levanta ValueError.
    report_path:
        Caminho do relatorio de correcoes (JSON). Default:
        <pasta do transcript>/corrections_report.json.
    reviewed_by:
        Quem confirmou a revisao (default: "proprietario").
    reviewed_at:
        Data/hora da revisao (default: agora em ISO UTC).
    reviewed_version:
        Versao do contrato de revisao (default: "1.0.0").

    Retorna dicionario com:
      - review_metadata
      - original_whisper_confidence (copia dos dados originais, probability intacta)
      - human_corrections (lista de correcoes aplicadas com proveniencia)
      - reviewed_result (resultado revisado)
    """
    transcript_path = Path(transcript_path).resolve()
    if not transcript_path.is_file():
        raise FileNotFoundError(f"transcript.json nao encontrado: {transcript_path}")

    transcript_sha = _sha256_file(transcript_path)
    transcript_data = _carregar_transcript(transcript_path)

    segments = list(transcript_data.get("segments", []))
    indice_por_id = _indice_por_segment_id(segments)

    # Saida default: transcript_reviewed.json ao lado do original.
    if output_path is None:
        output_path = transcript_path.parent / "transcript_reviewed.json"
    output_path = Path(output_path).resolve()

    # Nunca sobrescreve o original.
    if output_path == transcript_path:
        raise ValueError(
            "output_path nao pode ser o proprio transcript.json "
            f"({transcript_path}). Use transcript_reviewed.json."
        )

    # reviewed_at default.
    if reviewed_at is None:
        reviewed_at = _iso_now()

    # Estrutura de saida.
    reviewed_result_segments: List[Dict[str, Any]] = []
    human_corrections: List[Dict[str, Any]] = []

    # Copia profunda dos segmentos originais (preserva timestamps e probability).
    original_segments = copy.deepcopy(segments)

    # Conjunto de ids ja consumidos por correcoes (para nao duplicar no resultado).
    consumed_ids: set[int] = set()

    for corr_idx, corr in enumerate(corrections or [], start=1):
        corrected_text = corr.get("corrected_text")
        if not corrected_text or not isinstance(corrected_text, str):
            raise ValueError(
                f"correcoes[{corr_idx-1}]: 'corrected_text' e obrigatorio."
            )

        segment_ids = corr.get("segment_ids")
        segment_id = corr.get("segment_id")

        ids_para_corrigir: List[int] = []
        if segment_ids is not None:
            if not isinstance(segment_ids, list) or not segment_ids:
                raise ValueError(
                    f"correcoes[{corr_idx-1}]: 'segment_ids' deve ser uma lista nao vazia."
                )
            ids_para_corrigir = [int(sid) for sid in segment_ids]
        elif segment_id is not None:
            ids_para_corrigir = [int(segment_id)]
        else:
            raise ValueError(
                f"correcoes[{corr_idx-1}]: informe 'segment_ids' ou 'segment_id'."
            )

        # Resolve indices e valida existencia.
        idxs = []
        for sid in ids_para_corrigir:
            if sid not in indice_por_id:
                raise ValueError(
                    f"correcoes[{corr_idx-1}]: segment_id {sid} nao existe no transcript."
                )
            idxs.append(indice_por_id[sid])

        # Tokens originais dos segmentos corrigidos (proveniencia, probability intacta).
        original_tokens: List[Dict[str, Any]] = []
        start_val: Optional[float] = None
        end_val: Optional[float] = None
        for idx in idxs:
            seg = segments[idx]
            tokens = _extrair_tokens(seg)
            original_tokens.extend(tokens)
            seg_start = float(seg.get("start", seg.get("t", 0.0)))
            seg_end = float(seg.get("end", seg.get("f", 0.0)))
            if start_val is None or seg_start < start_val:
                start_val = seg_start
            if end_val is None or seg_end > end_val:
                end_val = seg_end
            consumed_ids.add(int(seg.get("id", idx)))

        if start_val is None:
            start_val = 0.0
        if end_val is None:
            end_val = 0.0

        human_corrections.append(
            {
                "correction_id": corr_idx,
                "segment_ids": ids_para_corrigir,
                "corrected_text": corrected_text.strip(),
                "start": round(start_val, 3),
                "end": round(end_val, 3),
                "original_tokens": original_tokens,
                "origin": "human_review",
                "confirmed_by": reviewed_by,
                "reviewed_at": reviewed_at,
                "reviewed_version": reviewed_version,
                "reason": corr.get("reason"),
                "category": corr.get("category"),
            }
        )

    # Monta reviewed_result: segmentos nao corrigidos (copia) + segmentos corrigidos.
    # Segmentos corrigidos sao representados pelo agrupamento (start do primeiro,
    # end do ultimo) com o texto corrigido.
    for idx, seg in enumerate(segments):
        sid = seg.get("id", idx)
        if int(sid) in consumed_ids:
            continue
        reviewed_result_segments.append(copy.deepcopy(seg))

    # Insere os segmentos corrigidos agrupados (ordenados por start).
    corrigidos_ordenados = sorted(
        human_corrections, key=lambda c: c["start"]
    )
    for corr in corrigidos_ordenados:
        reviewed_result_segments.append(
            {
                "id": f"reviewed-{corr['correction_id']}",
                "start": corr["start"],
                "end": corr["end"],
                "text": corr["corrected_text"],
                "words": _reconstruir_palavras_corrigidas(
                    corr["corrected_text"], corr["start"], corr["end"],
                    corr["original_tokens"],
                ),
                "human_reviewed": True,
                "correction_id": corr["correction_id"],
            }
        )

    reviewed_result_segments.sort(key=lambda s: float(s.get("start", 0.0)))

    reviewed_result = {
        "schema_version": "1.0.0",
        "origin": "human_review",
        "reviewed_by": reviewed_by,
        "reviewed_at": reviewed_at,
        "reviewed_version": reviewed_version,
        "source_transcript_sha256": transcript_sha,
        "total_segments": len(reviewed_result_segments),
        "total_corrections": len(human_corrections),
        "segments": reviewed_result_segments,
    }

    # Grava transcript_reviewed.json (somente escrita no output_path).
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(reviewed_result, f, indent=2, ensure_ascii=False)

    # Relatorio de correcoes (se solicitado).
    corrections_report: Dict[str, Any] = {
        "schema_version": "1.0.0",
        "review_metadata": {
            "reviewed_by": reviewed_by,
            "reviewed_at": reviewed_at,
            "reviewed_version": reviewed_version,
            "origin": "human_review",
            "source_transcript": str(transcript_path),
            "source_transcript_sha256": transcript_sha,
            "output_transcript": str(output_path),
        },
        "total_corrections": len(human_corrections),
        "corrections": human_corrections,
    }

    if report_path is not None:
        report_path = Path(report_path).resolve()
        report_path.parent.mkdir(parents=True, exist_ok=True)
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(corrections_report, f, indent=2, ensure_ascii=False)

    return {
        "review_metadata": corrections_report["review_metadata"],
        "original_whisper_confidence": {
            "total_segments": len(original_segments),
            "total_words": sum(
                len(s.get("words", []) or []) for s in original_segments
            ),
            "segments": original_segments,
        },
        "human_corrections": human_corrections,
        "reviewed_result": reviewed_result,
        "output_path": str(output_path),
        "report_path": str(report_path) if report_path is not None else None,
    }


# ---------------------------------------------------------------------------
# record_transcription_benchmark
# ---------------------------------------------------------------------------


def record_transcription_benchmark(
    benchmark_data: Dict[str, Any],
    *,
    json_path: str | Path,
    md_path: str | Path,
) -> Dict[str, Any]:
    """Grava registro estruturado de benchmark de transcricao.

    Grava JSON (estruturado) e Markdown (legivel). Nao calcula WER nem %
    de acuracia quando nao ha ground truth integral disponível.

    Retorna dicionario com os caminhos gravados e um resumo.
    """
    json_path = Path(json_path).resolve()
    md_path = Path(md_path).resolve()
    json_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)

    registro = {
        "schema_version": "1.0.0",
        "recorded_at": _iso_now(),
        "benchmark": benchmark_data,
    }

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(registro, f, indent=2, ensure_ascii=False)

    # Relatório Markdown legível.
    lines: List[str] = []
    lines.append("# Relatório de Benchmark de Transcrição")
    lines.append("")
    lines.append(f"Registrado em: {registro['recorded_at']}")
    lines.append("")
    lines.append("## Dados do Benchmark")
    lines.append("")
    if isinstance(benchmark_data, dict):
        for chave, valor in benchmark_data.items():
            lines.append(f"- **{chave}**: {valor}")
    else:
        lines.append(f"- dado: {benchmark_data}")
    lines.append("")
    lines.append("## Observacoes")
    lines.append("")
    lines.append("- WER / % de acuracia nao calculados sem ground truth integral.")
    lines.append("- Todas as probabilidades originais do Whisper sao preservadas.")
    lines.append("")

    md_path.write_text("\n".join(lines), encoding="utf-8")

    return {
        "json_path": str(json_path),
        "md_path": str(md_path),
        "recorded_at": registro["recorded_at"],
    }
