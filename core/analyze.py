"""
core/analyze.py

Orquestracao de transcricao, verificacao fonetica e alinhamento temporal,
adaptada seletivamente de Editor legado/core/{phonetic_verifier.py, aligner.py}
para o Workspace Core e a estrutura canonica do legado
(projetos/<marca>/episodios/<episodio>/).

Fluxo de dados/artefatos:
  projetos/<marca>/episodios/<episodio>/
    workspace/fonte/
      audio_speech_16k_mono.wav   (produzido pela ingestao)
      media_info.json             (produzido pela ingestao)
      transcript.json             (gerado aqui: segments, words, source_ref)
      phonetic_report.json        (gerado aqui: findings, lexicon_hits, low_confidence)
      alignment.json              (gerado aqui: editorial_units, pauses)
      palavras.json               (legado: [{w, t, f}])
      roteiro.txt                 (legado: frase por frase com tempo)
    project.json                  (atualizado: artifacts['02_analyze'],
                                   current_stage='02_ANALYZE_COMPLETED')

Regras de seguranca:
- Roda primeiro o gate verify_source_integrity() da ingestao (SHA-256 do brutos).
- Quando `transcricao_injetada=None`, executa transcricao real LOCAL com
  faster-whisper offline (snapshot via `whisper_model_path` ou
  EDITOR_WHISPER_MODEL_PATH), sem download e sem fallback silencioso.
- `transcricao_injetada` continua suportada para testes/fixtures
  (origem `injected_fixture`).
- Contenca estrita em workspace_root.
- Sem hardcode de marca ou episodio.
"""

from __future__ import annotations

import copy
import importlib.util
import inspect
import json
import logging
import math
import os
import re
import sys
import time
import wave
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Import relativo do pacote core
try:
    from .workspace import WorkspaceLoader, WorkspaceError, _resolve_within
    from .ingest import (  # noqa: F401
        compute_sha256,
        verify_source_integrity,
        IngestError,
    )
    from .transcript_review import (  # noqa: F401
        resolve_editorial_transcript,
        sync_alignment_with_editorial_transcript,
        TranscriptReviewError,
    )
except ImportError:  # execucao direta como script
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from core.workspace import WorkspaceLoader, WorkspaceError, _resolve_within  # type: ignore
    from core.ingest import (  # noqa: F401
        compute_sha256,
        verify_source_integrity,
        IngestError,
    )
    from core.transcript_review import (  # type: ignore
        resolve_editorial_transcript,
        sync_alignment_with_editorial_transcript,
        TranscriptReviewError,
    )

# Transcritor do legado (reuso, nao cria segundo transcritor).
# O diretorio vortex-edicao tem hifen, entao nao e importavel por nome;
# carregamos dinamicamente via importlib.
_transcrever_modulo = None


def _carregar_transcrever_modulo(workspace_root: str | Path):
    """Carrega vortex-edicao/transcrever.py dinamicamente (reuso)."""
    global _transcrever_modulo
    if _transcrever_modulo is not None:
        return _transcrever_modulo
    raiz = Path(workspace_root).resolve()
    caminho = raiz / "vortex-edicao" / "transcrever.py"
    if not caminho.is_file():
        raise AnalyzeError(f"vortex-edicao/transcrever.py nao encontrado: {caminho}")
    spec = importlib.util.spec_from_file_location("transcrever_legado", str(caminho))
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    _transcrever_modulo = modulo
    return modulo


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Excecoes
# ---------------------------------------------------------------------------


class AnalyzeError(Exception):
    """Erro de transcricao/verificacao fonetica/alinhamento."""


# ---------------------------------------------------------------------------
# Modelos de dados
# ---------------------------------------------------------------------------


@dataclass
class CorrectionFinding:
    """Registro de achado e correcao fonetica para auditoria."""
    original_text: str
    corrected_text: str
    start_time: float
    end_time: float
    certainty: float
    category: str
    rule_name: str
    rationale: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Helpers de fonetica (adaptados de Editor legado/core/phonetic_verifier.py)
# ---------------------------------------------------------------------------


def _load_phonetic_rules(brand_profile: Dict[str, Any], marcas_dir: Path) -> List[Tuple]:
    """Carrega regras de correcao fonetica de projetos/<marca>/branding/phonetic_rules.json."""
    brand_id = brand_profile.get("brand_id")
    rules_path = marcas_dir / "branding" / "phonetic_rules.json"
    if not rules_path.is_file():
        return []
    with open(rules_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    rules: List[Tuple] = []
    for r in data.get("rules", []):
        pattern = tuple(r.get("pattern", []))
        replacement = list(r.get("replacement", []))
        rule_name = r.get("rule_name", "rule_sem_nome")
        category = r.get("category", "sem_categoria")
        certainty = float(r.get("certainty", 1.0))
        rationale = r.get("rationale", "")
        rules.append((pattern, replacement, rule_name, category, certainty, rationale))
    return rules


def _limpar_token(texto: str) -> str:
    return re.sub(r"[^\w\u00c0-\u024f]", "", texto.strip().lower())


def _coerente_probabilidade(valor: Any) -> Optional[float]:
    """Coerente um valor de probabilidade do Whisper para float em [0, 1].

    NUNCA retorna 1.0 como fallback. Quando o valor estiver ausente, for None,
    NaN, infinito, fora de [0, 1] ou nao numerico, retorna None (serializado
    como null no JSON). Isso evita confundir "probabilidade desconhecida" com
    "alta confianca".
    """
    if valor is None:
        return None
    try:
        v = float(valor)
    except (TypeError, ValueError):
        return None
    if math.isnan(v) or math.isinf(v) or v < 0.0 or v > 1.0:
        return None
    return v


# Limiar de sinalizacao de baixa confianca para revisao humana.
# E uma heuristica de sinalizacao (nao uma probabilidade estatisticamente
# calibrada): palavras com probability < 0.65 são marcadas para revisao.
# Quando probability esta ausente/invalida (None), a palavra entra em
# unknown_confidence_count, nunca em low_confidence.
BAIXA_CONFIANCA_LIMIAR = 0.65


class PhoneticVerifier:
    """Agente de Verificacao Fonetica e Normalizacao de Transcricao ASR."""

    def __init__(self, rules: Optional[List[Tuple]] = None):
        self.rules = rules if rules is not None else []

    def verify_and_correct_words(
        self, words: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], List[CorrectionFinding]]:
        if not words:
            return [], []
        corrected_words: List[Dict[str, Any]] = []
        findings: List[CorrectionFinding] = []
        i = 0
        n = len(words)
        while i < n:
            matched = False
            for pattern, replacement, rule_name, category, certainty, rationale in sorted(
                self.rules, key=lambda r: len(r[0]), reverse=True
            ):
                plen = len(pattern)
                if i + plen <= n:
                    window_tokens = [_limpar_token(w.get("w", w.get("word", ""))) for w in words[i : i + plen]]
                    pattern_tokens = [_limpar_token(p) for p in pattern]
                    if window_tokens == pattern_tokens:
                        matched = True
                        matched_words = words[i : i + plen]
                        start_time = matched_words[0].get("t", matched_words[0].get("start", 0.0))
                        end_time = matched_words[-1].get("f", matched_words[-1].get("end", 0.0))
                        orig_str = " ".join(w.get("w", w.get("word", "")) for w in matched_words)
                        repl_str = " ".join(replacement)
                        probs = [
                            _coerente_probabilidade(w.get("probability"))
                            for w in matched_words
                            if "probability" in w
                        ]
                        probs_validos = [p for p in probs if p is not None]
                        prob = min(probs_validos) if probs_validos else None
                        finding = CorrectionFinding(
                            original_text=orig_str,
                            corrected_text=repl_str,
                            start_time=start_time,
                            end_time=end_time,
                            certainty=certainty,
                            category=category,
                            rule_name=rule_name,
                            rationale=rationale,
                        )
                        findings.append(finding)
                        rlen = len(replacement)
                        total_dur = max(0.01, end_time - start_time)
                        step_dur = total_dur / rlen
                        for r_idx, rep_w in enumerate(replacement):
                            w_start = round(start_time + r_idx * step_dur, 3)
                            w_end = round(start_time + (r_idx + 1) * step_dur, 3) if r_idx < rlen - 1 else end_time
                            corrected_words.append({
                                "w": rep_w,
                                "t": w_start,
                                "f": w_end,
                                "probability": prob,
                                "word": rep_w,
                                "start": w_start,
                                "end": w_end,
                            })
                        i += plen
                        break
            if not matched:
                corrected_words.append(copy.deepcopy(words[i]))
                i += 1
        return corrected_words, findings


# ---------------------------------------------------------------------------
# Alinhamento temporal (adaptado de Editor legado/core/aligner.py)
# ---------------------------------------------------------------------------


def classify_pause(duration_seconds: float) -> str:
    """Classifica a natureza da pausa acustica entre palavras."""
    if duration_seconds < 0.20:
        return "micro_pause"
    elif duration_seconds < 0.50:
        return "natural_pause"
    elif duration_seconds < 1.00:
        return "sentence_pause"
    else:
        return "long_silence"


def _carregar_amostras_wav(wav_path: Path):
    """Carrega dados PCM do WAV 16kHz mono para vetor numpy (opcional)."""
    try:
        import numpy as np
        with wave.open(str(wav_path), "rb") as wf:
            n_channels = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            framerate = wf.getframerate()
            n_frames = wf.getnframes()
            raw_bytes = wf.readframes(n_frames)
        duration = n_frames / framerate
        if sampwidth == 2:
            samples = np.frombuffer(raw_bytes, dtype=np.int16)
        else:
            raise ValueError(f"Largura de amostra {sampwidth} bytes nao suportada.")
        return samples, framerate, duration
    except Exception as e:
        logger.warning(f"Nao foi carregar amostras de audio: {e}")
        return None, 16000, 0.0


def _compute_rms(samples) -> float:
    """Calcula RMS de uma janela de amostras."""
    try:
        import numpy as np
        if len(samples) == 0:
            return 0.0
        return float(np.sqrt(np.mean(samples.astype(np.float64) ** 2)))
    except Exception:
        return 0.0


ABBREVIATIONS = frozenset({
    "dr.", "dra.", "sr.", "sra.", "srta.", "prof.", "profa.",
    "eng.", "adv.", "pe.", "st.", "sto.", "sta.", "etc.",
})


def build_alignment_from_words(
    palavras: List[Dict[str, Any]],
    marca_profile: Dict[str, Any],
    audio_wav_path: Optional[Path] = None,
    pre_roll_ms: int = 80,
    post_roll_ms: int = 200,
    total_audio_duration: Optional[float] = None,
) -> Dict[str, Any]:
    """Executa alinhamento temporal e analise de pausas a partir de palavras
    com timestamps, usando parametros da marca. Nao grava arquivo; retorna o
    dicionario de alinhamento pronto para ser salvo."""
    silence_guard_ms = marca_profile.get("audio", {}).get("silence_guard_ms", [180, 220])
    min_pause_split_s = silence_guard_ms[1] / 1000.0

    # Coletar palavras em lista linear normalizada
    all_words = []
    for w in palavras:
        all_words.append({
            "word": w.get("w", w.get("word", "")),
            "start": float(w.get("t", w.get("start", 0.0))),
            "end": float(w.get("f", w.get("end", 0.0))),
            "probability": _coerente_probabilidade(w.get("probability")),
        })
    if not all_words:
        raise AnalyzeError("Nenhuma palavra com timestamps encontrada na transcricao.")

    total_audio_duration = total_audio_duration or (all_words[-1]["end"] + 1.0)
    audio_samples = None
    sample_rate = 16000
    if audio_wav_path and audio_wav_path.exists():
        audio_samples, sample_rate, total_audio_duration = _carregar_amostras_wav(audio_wav_path)

    pre_roll_s = pre_roll_ms / 1000.0
    post_roll_s = post_roll_ms / 1000.0

    # 1. Analise de pausas inter-palavras
    pauses_detected = []
    for i in range(len(all_words) - 1):
        curr_word = all_words[i]
        next_word = all_words[i + 1]
        gap = next_word["start"] - curr_word["end"]
        if gap > 0.05:
            pauses_detected.append({
                "pause_index": len(pauses_detected) + 1,
                "after_word_index": i,
                "after_word": curr_word["word"],
                "before_word": next_word["word"],
                "start": round(curr_word["end"], 3),
                "end": round(next_word["start"], 3),
                "duration_seconds": round(gap, 3),
                "type": classify_pause(gap),
            })

    # 2. Agrupamento em unidades editoriais
    editorial_units = []
    current_unit_words = []

    def flush_unit(words_group: list):
        if not words_group:
            return
        unit_id = len(editorial_units) + 1
        raw_start = words_group[0]["start"]
        raw_end = words_group[-1]["end"]
        prev_end = editorial_units[-1]["raw_end"] if editorial_units else 0.0
        padded_start = max(0.0, raw_start - pre_roll_s)
        if editorial_units and padded_start < prev_end:
            padded_start = max(prev_end, raw_start - (raw_start - prev_end) / 2.0)
        padded_end = min(total_audio_duration, raw_end + post_roll_s)
        text_str = " ".join(w["word"] for w in words_group)

        rms_start_valley = 0.0
        rms_end_valley = 0.0
        if audio_samples is not None:
            idx_start = int(padded_start * sample_rate)
            idx_end = int(padded_end * sample_rate)
            rms_start_valley = _compute_rms(
                audio_samples[max(0, idx_start):min(len(audio_samples), idx_start + int(0.05 * sample_rate))]
            )
            rms_end_valley = _compute_rms(
                audio_samples[max(0, idx_end - int(0.05 * sample_rate)):min(len(audio_samples), idx_end)]
            )

        editorial_units.append({
            "unit_id": unit_id,
            "text": text_str,
            "word_count": len(words_group),
            "raw_start": round(raw_start, 3),
            "raw_end": round(raw_end, 3),
            "padded_in_point": round(padded_start, 3),
            "padded_out_point": round(padded_end, 3),
            "duration_raw_seconds": round(raw_end - raw_start, 3),
            "duration_padded_seconds": round(padded_end - padded_start, 3),
            "rms_in_point": round(rms_start_valley, 1),
            "rms_out_point": round(rms_end_valley, 1),
            "pause_after_seconds": 0.0,
            "words": words_group,
        })

    terminal_punctuations = (".", "?", "!", "...", ";")
    for i, w in enumerate(all_words):
        current_unit_words.append(w)
        word_clean = w["word"].rstrip()
        is_abbr = word_clean.lower() in ABBREVIATIONS
        is_terminal_punc = (not is_abbr) and any(
            word_clean.endswith(punc) for punc in terminal_punctuations
        )
        next_gap = (all_words[i + 1]["start"] - w["end"]) if i < len(all_words) - 1 else 0.0
        has_long_pause_after = (i < len(all_words) - 1) and (next_gap >= min_pause_split_s)
        has_terminal_break = is_terminal_punc and (i == len(all_words) - 1 or next_gap >= 0.18)
        if has_terminal_break or has_long_pause_after or i == len(all_words) - 1:
            flush_unit(current_unit_words)
            current_unit_words = []

    # Ajustar pausas e limites entre unidades
    for i in range(len(editorial_units)):
        if i < len(editorial_units) - 1:
            next_unit = editorial_units[i + 1]
            gap = next_unit["raw_start"] - editorial_units[i]["raw_end"]
            editorial_units[i]["pause_after_seconds"] = round(max(0.0, gap), 3)
            if editorial_units[i]["padded_out_point"] > next_unit["padded_in_point"]:
                midpoint = (editorial_units[i]["raw_end"] + next_unit["raw_start"]) / 2.0
                editorial_units[i]["padded_out_point"] = round(midpoint, 3)
                next_unit["padded_in_point"] = round(midpoint, 3)

    alignment_data = {
        "schema_version": "1.0.0",
        "status": "COMPLETED",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "parameters": {
            "pre_roll_ms": pre_roll_ms,
            "post_roll_ms": post_roll_ms,
            "min_pause_split_s": min_pause_split_s,
            "silence_guard_ms": silence_guard_ms,
        },
        "summary": {
            "total_words": len(all_words),
            "total_pauses": len(pauses_detected),
            "total_editorial_units": len(editorial_units),
            "audio_duration_seconds": round(total_audio_duration, 3),
        },
        "editorial_units": editorial_units,
        "pauses": pauses_detected,
        "telemetry": {
            "processing_time_seconds": 0.0,
        },
    }
    return alignment_data


# ---------------------------------------------------------------------------
# Orquestracao principal
# ---------------------------------------------------------------------------


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _gravar_json(path: Path, dados: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(dados, f, indent=2, ensure_ascii=False)


def analyze_episodio(
    marca_id: str,
    episodio_id: str,
    workspace_root: str | Path,
    transcricao_injetada: Optional[List[Dict[str, Any]]] = None,
    modelo_whisper: str = "large-v3-turbo",
    idioma: str = "pt",
    *,
    whisper_model_path: Optional[str | Path] = None,
    offline_only: bool = True,
) -> Dict[str, Any]:
    """Orquestra transcricao, verificacao fonetica e alinhamento de um episodio.

    Passos:
      1. Gate de integridade: verify_source_integrity() do brutos/ (SHA-256).
      2. Transcricao via vortex-edicao/transcrever.py usando
         audio_speech_16k_mono.wav + lexicon_transcricao da marca:
           - `transcricao_injetada` informada -> origem `injected_fixture`;
           - caso contrario -> faster-whisper LOCAL offline
             (`whisper_model_path` ou EDITOR_WHISPER_MODEL_PATH), origem
             `local_faster_whisper`, sem download e sem fallback silencioso.
      3. Verificacao fonetica (phonetic_rules.json + asr.lexicon da marca).
      4. Alinhamento temporal com silence_guard_ms da marca.
      5. Grava palavras.json, roteiro.txt (legados), transcript.json,
         phonetic_report.json, alignment.json em workspace/fonte/.
      6. Atualiza project.json (artifacts['02_analyze'],
         current_stage='02_ANALYZE_COMPLETED').

    Retorna o dicionario de resultado da analise, incluindo `transcription`
    (origem, modelo, flags offline e idioma).
    """
    t_start_total = time.perf_counter()
    loader = WorkspaceLoader(workspace_root)
    loader.load_workspace()

    pre_roll_ms = 80
    post_roll_ms = 200

    # 1. Gate de integridade da ingestao (SHA-256 do brutos).
    loader.load_brand_profile(marca_id)  # garante marca existente
    pj_path = loader.project_file(marca_id, episodio_id)
    if not pj_path.is_file():
        raise AnalyzeError(f"project.json nao encontrado: {pj_path}. Rode a ingestao primeiro.")
    with open(pj_path, "r", encoding="utf-8") as f:
        projeto = json.load(f)

    sources = projeto.get("sources", [])
    if not sources:
        raise AnalyzeError("Nenhuma source registrada em project.json. Rode a ingestao primeiro.")
    fonte = sources[0]
    brutos_path = Path(fonte["path"])
    brutos_sha = fonte.get("sha256")
    if not brutos_path.is_file():
        raise AnalyzeError(f"Arquivo em brutos nao encontrado: {brutos_path}")
    verify_source_integrity(brutos_path, brutos_sha, brutos_path.name)

    # Diretorios de saida.
    fonte_dir = loader.resolve_episodio_asset(marca_id, episodio_id, "workspace/fonte")
    fonte_dir.mkdir(parents=True, exist_ok=True)

    # Perfil da marca (para lexicon e silencio).
    perfil_marca = loader.load_brand_profile(marca_id)
    preferencias = perfil_marca["config_json"].get("preferencias_edicao", {})
    lexicon_transcricao = preferencias.get("lexicon_transcricao", "")
    marcas_dir = loader.episodios_dir(marca_id).parent  # projetos/<marca>

    # Monta o initial_prompt (vocabulario da marca) para o Whisper:
    # preferencias.asr.lexicon (lista) + preferencias.asr.lexicon_transcricao
    # (string separada por virgula), deduplicados preservando a ordem.
    asr_cfg = preferencias.get("asr", {}) or {}
    lexicon_list = list(asr_cfg.get("lexicon", []) or [])
    if isinstance(lexicon_transcricao, str) and lexicon_transcricao.strip():
        lexicon_list.extend(
            t.strip() for t in lexicon_transcricao.split(",") if t.strip()
        )
    # Dedup preservando ordem.
    _seen = set()
    _lexicon_dedup = []
    for _t in lexicon_list:
        if _t and _t not in _seen:
            _seen.add(_t)
            _lexicon_dedup.append(_t)
    initial_prompt = (
        "Vocabulario da marca: " + ", ".join(_lexicon_dedup) + "."
        if _lexicon_dedup
        else None
    )

    # 2. Transcricao via vortex-edicao/transcrever.py (reuso, nao cria segundo).
    palavras: List[Dict[str, Any]] = []
    language = idioma
    transcricao_detalhada: Optional[Dict[str, Any]] = None
    if transcricao_injetada is not None:
        # Testes/fixtures: usa transcricao injetada (nao roda modelo).
        palavras = transcricao_injetada
        logger.info("Transcricao injetada (modo teste): %d palavras.", len(palavras))
    else:
        wav_16k = fonte_dir / "audio_speech_16k_mono.wav"
        if not wav_16k.is_file():
            raise AnalyzeError(
                f"audio_speech_16k_mono.wav nao encontrado: {wav_16k}. Rode a ingestao primeiro."
            )
        # transcreve() com detalhado=True para pegar probability/language/modelo.
        # Sem transcricao injetada, NUNCA cai silenciosamente para uma fixture:
        # ou transcreve no snapshot local, ou levanta erro explicito.
        transcrever_modulo = _carregar_transcrever_modulo(workspace_root)
        _transcreve_params = inspect.signature(transcrever_modulo.transcreve).parameters
        _call_kwargs = {
            "detalhado": True,
            "model_path": whisper_model_path,
            "offline_only": offline_only,
        }
        if initial_prompt and "initial_prompt" in _transcreve_params:
            _call_kwargs["initial_prompt"] = initial_prompt
        resultado = transcrever_modulo.transcreve(
            str(wav_16k),
            str(fonte_dir),
            idioma,
            modelo_whisper,
            **_call_kwargs,
        )
        if isinstance(resultado, dict):
            palavras = resultado.get("palavras", [])
            language = resultado.get("language", idioma)
            transcricao_detalhada = resultado
        else:
            # Compatibilidade: retorno legado [{"w","t","f"}]
            palavras = resultado

    # Metadados de origem da transcricao (nunca expoem caminho absoluto de backup).
    if transcricao_injetada is not None:
        transcription_meta: Dict[str, Any] = {
            "origin": "injected_fixture",
            "engine": "injected_fixture",
            "model_identifier": None,
            "model_revision": None,
            "model_path_kind": "injected",
            "local_execution_confirmed": False,
            "local_files_only": False,
            "offline_only": True,
            "language": language,
            "duration_seconds": None,
            "external_calls": False,
        }
    else:
        detalhe = transcricao_detalhada or {}
        if not bool(detalhe.get("local_files_only", False)):
            raise AnalyzeError(
                "transcricao nao-local bloqueada: e obrigatorio usar um snapshot "
                "local (whisper_model_path ou EDITOR_WHISPER_MODEL_PATH) com "
                "local_files_only=True; download/elevenlabs nao sao permitidos."
            )
        transcription_meta = {
            "origin": "local_faster_whisper",
            "engine": detalhe.get("engine", "faster-whisper"),
            "model_identifier": detalhe.get("model_identifier") or modelo_whisper,
            "model_revision": detalhe.get("model_revision"),
            "model_path_kind": detalhe.get("model_path_kind", "local_snapshot"),
            "local_execution_confirmed": bool(detalhe.get("local_execution_confirmed", True)),
            "local_files_only": True,
            "offline_only": bool(detalhe.get("offline_only", True)),
            "language": language,
            "duration_seconds": detalhe.get("duration"),
            "external_calls": False,
        }

    # 3. Verificacao fonetica (phonetic_rules.json + asr.lexicon da marca).
    regras = _load_phonetic_rules(perfil_marca["config_json"], marcas_dir)
    verificador = PhoneticVerifier(rules=regras)
    palavras_corrigidas, findings = verificador.verify_and_correct_words(palavras)

    # Deteccao de baixa confianca (probability < 0.65).
    # probability ausente/invalida (None) NÃO conta como baixa confianca;
    # entra em unknown_confidence_count para nao confundir com alta confianca.
    low_confidence = []
    unknown_confidence_count = 0
    for w in palavras_corrigidas:
        prob = _coerente_probabilidade(w.get("probability"))
        if prob is None:
            unknown_confidence_count += 1
        elif prob < BAIXA_CONFIANCA_LIMIAR:
            low_confidence.append(w)

    # Termos do dicionario da marca encontrados (simples: busca por palavra).
    lexicon = preferencias.get("asr", {}).get("lexicon", [])
    if not lexicon:
        # fallback: lexicon_transcricao como string separada por virgula
        lexicon = [t.strip() for t in lexicon_transcricao.split(",") if t.strip()]
    lexicon_lower = {_limpar_token(t) for t in lexicon if _limpar_token(t)}
    lexicon_hits = []
    for w in palavras_corrigidas:
        palavra_limpa = _limpar_token(w.get("w", w.get("word", "")))
        if palavra_limpa and palavra_limpa in lexicon_lower:
            lexicon_hits.append({
                "palavra": w.get("w", w.get("word", "")),
                "t": w.get("t", w.get("start", 0.0)),
                "f": w.get("f", w.get("end", 0.0)),
            })

    phonetic_report = {
        "schema_version": "1.0.0",
        "marca_id": marca_id,
        "episodio_id": episodio_id,
        "total_palavras": len(palavras_corrigidas),
        "total_findings": len(findings),
        "low_confidence_count": len(low_confidence),
        "unknown_confidence_count": unknown_confidence_count,
        "low_confidence": [
            {"palavra": w.get("w", w.get("word", "")), "t": w.get("t", w.get("start", 0.0)),
             "f": w.get("f", w.get("end", 0.0)), "probability": w.get("probability", 1.0)}
            for w in low_confidence
        ],
        "lexicon_hits": lexicon_hits,
        "findings": [f.to_dict() for f in findings],
        "status": "VERIFIED_AND_CORRECTED" if findings else "VERIFIED_NO_ANOMALIES_DETECTED",
    }

    # 4. Alinhamento temporal com silence_guard_ms da marca.
    wav_path = fonte_dir / "audio_speech_16k_mono.wav"
    alinhamento = build_alignment_from_words(
        palavras_corrigidas,
        perfil_marca["config_json"],
        audio_wav_path=wav_path if wav_path.exists() else None,
        pre_roll_ms=pre_roll_ms,
        post_roll_ms=post_roll_ms,
        total_audio_duration=None,
    )
    alinhamento["telemetry"]["processing_time_seconds"] = round(
        time.perf_counter() - t_start_total, 3
    )

    if transcription_meta.get("duration_seconds") is None:
        transcription_meta["duration_seconds"] = alinhamento["summary"]["audio_duration_seconds"]
    transcription_meta["total_words"] = len(palavras_corrigidas)
    transcription_meta["analysis_state"] = "02_ANALYZE_COMPLETED"

    # 5. Gravar artefatos em workspace/fonte/.
    # transcript.json (com segments, words, source_ref).
    segments = []
    palavras_legacy = []  # [{w, t, f}] para palavras.json
    for i, w in enumerate(palavras_corrigidas):
        palavra = w.get("w", w.get("word", ""))
        t = float(w.get("t", w.get("start", 0.0)))
        f = float(w.get("f", w.get("end", 0.0)))
        palavras_legacy.append({"w": palavra, "t": t, "f": f})
        segments.append({
            "id": i,
            "start": t,
            "end": f,
            "text": palavra,
            "words": [{"word": palavra, "start": t, "end": f,
                       "probability": _coerente_probabilidade(w.get("probability"))}],
        })

    transcript_json = {
        "schema_version": "1.0.0",
        "engine": transcription_meta.get("engine", "faster-whisper"),
        "transcription_origin": transcription_meta["origin"],
        "transcription": copy.deepcopy(transcription_meta),
        "language": language,
        "audio_duration_seconds": alinhamento["summary"]["audio_duration_seconds"],
        "total_segments": len(segments),
        "total_words": len(palavras_legacy),
        "segments": segments,
        "source_ref": {
            "path": str(brutos_path),
            "sha256": brutos_sha,
        },
        "phonetic_verification": phonetic_report["status"],
    }
    _gravar_json(fonte_dir / "transcript.json", transcript_json)

    # Re-sincroniza alignment.json / palavras.json / roteiro.txt a partir da
    # transcrição editorial resolvida (resolve_editorial_transcript), sem nunca
    # sobrescrever transcript.json original. Garante que edl_builder, briefing,
    # semantic_planner e pipeline consumam exatamente a mesma versão selecionada
    # (raw_transcript ou reviewed_transcript).
    _silence_guard_ms = int(
        (perfil_marca["config_json"]
         .get("preferencias_edicao", {})
         .get("audio", {})
         .get("silence_guard_ms", [180, 220])[1])
    )
    _sync_result = sync_alignment_with_editorial_transcript(
        fonte_dir, silence_guard_ms=_silence_guard_ms
    )
    # Usa o alinhamento re-sincronizado (consistente com transcript.json).
    alinhamento = _sync_result["alignment"]
    editorial_source_kind = _sync_result["source_kind"]
    editorial_transcript_sha256 = _sync_result.get("transcript_sha256")
    editorial_base_transcript_sha256 = _sync_result.get("base_transcript_sha256")
    editorial_reviewed_by = _sync_result.get("reviewed_by")
    editorial_reviewed_at = _sync_result.get("reviewed_at")
    editorial_reviewed_version = _sync_result.get("reviewed_version")

    # phonetic_report.json.
    _gravar_json(fonte_dir / "phonetic_report.json", phonetic_report)

    # 6. Atualizar project.json.
    projeto["current_stage"] = "02_ANALYZE_COMPLETED"
    projeto["updated_at"] = _iso_now()
    projeto["artifacts"]["02_analyze"] = {
        "transcript": "workspace/fonte/transcript.json",
        "alignment": "workspace/fonte/alignment.json",
        "palavras": "workspace/fonte/palavras.json",
        "roteiro": "workspace/fonte/roteiro.txt",
        "phonetic_report": "workspace/fonte/phonetic_report.json",
    }
    projeto["analise"] = {
        "status": "COMPLETED",
        "total_palavras": len(palavras_legacy),
        "total_segments": len(segments),
        "total_pauses": alinhamento["summary"]["total_pauses"],
        "total_editorial_units": alinhamento["summary"]["total_editorial_units"],
        "language": language,
        "transcription_origin": transcription_meta["origin"],
        "editorial_transcript_source": editorial_source_kind,
        "editorial_transcript_sha256": editorial_transcript_sha256,
        "editorial_base_transcript_sha256": editorial_base_transcript_sha256,
        "editorial_reviewed_by": editorial_reviewed_by,
        "editorial_reviewed_at": editorial_reviewed_at,
        "editorial_reviewed_version": editorial_reviewed_version,
        "local_execution_confirmed": transcription_meta["local_execution_confirmed"],
        "local_files_only": transcription_meta["local_files_only"],
        "offline_only": transcription_meta["offline_only"],
        "relative_transcript_path": "workspace/fonte/transcript.json",
        "telemetry": alinhamento["telemetry"],
    }
    _gravar_json(pj_path, projeto)

    return {
        "marca_id": marca_id,
        "episodio_id": episodio_id,
        "palavras": palavras_legacy,
        "segments": segments,
        "language": language,
        "transcription": transcription_meta,
        "transcript": transcript_json,
        "phonetic_report": phonetic_report,
        "alignment": alinhamento,
        "project": projeto,
        "editorial_transcript_source": editorial_source_kind,
        "editorial_transcript_sha256": editorial_transcript_sha256,
        "editorial_base_transcript_sha256": editorial_base_transcript_sha256,
        "editorial_reviewed_by": editorial_reviewed_by,
        "editorial_reviewed_at": editorial_reviewed_at,
        "editorial_reviewed_version": editorial_reviewed_version,
    }


# ---------------------------------------------------------------------------
# Funcoes de conveniencia
# ---------------------------------------------------------------------------


def analyze_episodio_wrapper(
    workspace_root: str | Path,
    marca_id: str,
    episodio_id: str,
    transcricao_injetada: Optional[List[Dict[str, Any]]] = None,
    modelo_whisper: str = "large-v3-turbo",
    idioma: str = "pt",
    *,
    whisper_model_path: Optional[str | Path] = None,
    offline_only: bool = True,
) -> Dict[str, Any]:
    return analyze_episodio(
        marca_id, episodio_id, workspace_root,
        transcricao_injetada=transcricao_injetada,
        modelo_whisper=modelo_whisper,
        idioma=idioma,
        whisper_model_path=whisper_model_path,
        offline_only=offline_only,
    )

