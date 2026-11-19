"""
core/semantic_planner.py

Planejador semantico agnostico de IA para o Editor.

Fornece:
  - SemanticPlannerProvider (Protocol) com metodo plan(context) -> Dict[str, Any].
  - Provedores oficiais locais (sem chaves comerciais de API):
      * AntigravityCliProvider: invoca 'agy --print --output-format json
        --json-schema <schema_file>' via subprocess.
      * OpenCodeCliProvider: invoca 'opencode run' via subprocess.
      * CallableMockProvider: provedor mock/injecao de dependencia para testes.
  - Governanca de privacidade e consentimento explicito (SemanticConsent).
  - Validacao obrigatoria via validate_semantic_plan de core/semantic_plan.py.
  - plan_episodio_semantics(): coleta artefatos do episodio, executa com
    consentimento ou fallback conservador, grava semantic_plan.json e
    semantic_consent.json.

Nao depende de API comercial externa. Nao envia midia bruta.
Nao modifica core/semantic_plan.py, core/briefing.py, core/edl_builder.py,
core/master_lint.py.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Protocol, Union, runtime_checkable

try:
    from .workspace import WorkspaceLoader, WorkspaceError
    from .semantic_plan import (
        validate_semantic_plan,
        SemanticPlanError,
        SEMANTIC_PLAN_SCHEMA_VERSION,
        IMPLEMENTED_MOTION_COMPONENTS,
    )
    from .transcript_review import (  # noqa: F401
        resolve_editorial_transcript,
        TranscriptReviewError,
    )
except ImportError:  # execucao direta como script
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from core.workspace import WorkspaceLoader, WorkspaceError  # type: ignore
    from core.semantic_plan import (  # type: ignore
        validate_semantic_plan,
        SemanticPlanError,
        SEMANTIC_PLAN_SCHEMA_VERSION,
        IMPLEMENTED_MOTION_COMPONENTS,
    )
    from core.transcript_review import (  # type: ignore
        resolve_editorial_transcript,
        TranscriptReviewError,
    )


# ---------------------------------------------------------------------------
# Tipos e constantes
# ---------------------------------------------------------------------------

TEXTUAL_DATA_KINDS = (
    "transcript.json",
    "palavras.json",
    "roteiro.txt",
    "alignment.json",
    "phonetic_report.json",
    "media_info.json (resumo)",
    "brand_profile (textual)",
    "user_brief.json (opcional)",
)

FILLER_WORDS = frozenset({"né", "ne", "ééé", "éé", "eee", "ahn", "hum", "hã"})


def load_user_brief(briefing_dir: Path | str) -> Dict[str, Any]:
    """Carrega e normaliza workspace/briefing/user_brief.json quando existir."""
    defaults: Dict[str, Any] = {
        "pedido_usuario": "",
        "modo": "completo",
        "qtd_cortes_desejada": None,
        "correcoes_ortograficas": [],
    }
    path = Path(briefing_dir) / "user_brief.json"
    if not path.is_file():
        return dict(defaults)
    try:
        raw = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (json.JSONDecodeError, OSError):
        return dict(defaults)
    if not isinstance(raw, dict):
        return dict(defaults)

    merged = dict(defaults)
    merged.update(raw)
    modo = str(merged.get("modo") or "completo").strip().lower()
    if modo not in ("completo", "so_cortes"):
        modo = "completo"
    merged["modo"] = modo
    merged["pedido_usuario"] = str(merged.get("pedido_usuario") or "").strip()
    qtd = merged.get("qtd_cortes_desejada")
    if qtd is not None:
        try:
            merged["qtd_cortes_desejada"] = max(1, int(qtd))
        except (TypeError, ValueError):
            merged["qtd_cortes_desejada"] = None
    corr = merged.get("correcoes_ortograficas")
    if not isinstance(corr, list):
        merged["correcoes_ortograficas"] = []
    return merged


class SemanticPlannerError(Exception):
    """Erro do planejador semantico."""


@runtime_checkable
class SemanticPlannerProvider(Protocol):
    """Interface agnostica de provedor de planejamento semantico.

    Implementacoes locais NAO usam chaves comerciais de API e NAO extraem
    tokens/endpoints privados. Toda entrada e saida e textual e auditavel.
    """

    def plan(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Gera um plano semantico a partir do contexto fornecido.

        Retorna um dict compatível com o schema 1.0.0 de semantic_plan.json.
        """


# ---------------------------------------------------------------------------
# Governanca de consentimento
# ---------------------------------------------------------------------------


@dataclass
class SemanticConsent:
    """Registro de consentimento para compartilhamento de dados textuais.

    authorized=False por padrao: nenhuma chamada externa/CLI e executada
    sem autorizacao explicita.
    """

    destination: str
    shared_data: List[str] = field(default_factory=list)
    authorized: bool = False
    timestamp_utc: str = ""
    consent_id: str = ""
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp_utc:
            self.timestamp_utc = datetime.now(timezone.utc).isoformat()
        if not self.consent_id:
            self.consent_id = str(uuid.uuid4())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SemanticConsent":
        return cls(
            destination=data.get("destination", ""),
            shared_data=list(data.get("shared_data", [])),
            authorized=bool(data.get("authorized", False)),
            timestamp_utc=data.get("timestamp_utc", ""),
            consent_id=data.get("consent_id", ""),
            notes=data.get("notes", ""),
        )


def _default_consent(destination: str, shared_data: List[str]) -> SemanticConsent:
    """Cria um consentimento nao-autorizado (padrao seguro)."""
    return SemanticConsent(
        destination=destination,
        shared_data=list(shared_data),
        authorized=False,
        notes="Consentimento nao autorizado por padrao.",
    )


# ---------------------------------------------------------------------------
# Provedores locais
# ---------------------------------------------------------------------------


class AntigravityCliProvider:
    """Provedor que invoca a CLI 'agy' (Antigravity) via subprocess.

    Comando: agy --input-format stream-json --output-format stream-json
             [--json-schema <schema_file>]
    Entrada: unica linha NDJSON via stdin:
             {"event": "user", "message": {"content": <prompt>}}
    Saida: NDJSON linha por linha, evento terminal 'result' com
           structured_output contendo o semantic_plan.json validado.
    """

    def __init__(
        self,
        schema_file: Optional[Union[str, Path]] = None,
        timeout_s: float = 120.0,
        binary: str = "agy",
        workspace_root: Optional[Union[str, Path]] = None,
    ) -> None:
        self.schema_file = str(schema_file) if schema_file is not None else None
        self.timeout_s = timeout_s
        self.binary = binary
        self.workspace_root = (
            Path(workspace_root).resolve() if workspace_root is not None else None
        )

    def plan(self, context: Dict[str, Any]) -> Dict[str, Any]:
        # Monta argumentos do comando (sem shell=True, sem --print).
        cmd = [
            self.binary,
            "--input-format",
            "stream-json",
            "--output-format",
            "stream-json",
        ]

        schema_path: Optional[Path] = None
        if self.schema_file is not None:
            schema_path = Path(self.schema_file)
            if not schema_path.is_file():
                raise SemanticPlannerError(
                    f"schema_file nao encontrado: {self.schema_file}"
                )
            if self.workspace_root is not None:
                try:
                    schema_path.resolve().relative_to(
                        self.workspace_root.resolve()
                    )
                except ValueError as exc:
                    raise SemanticPlannerError(
                        f"schema_file esta fora do workspace_root: {self.schema_file}"
                    ) from exc
            cmd.extend(["--json-schema", str(schema_path)])

        # Montar prompt textual e enviar via stdin (NDJSON unica linha).
        prompt = (
            "Gere um plano semantico editorial em JSON (schema 1.0.0) a partir do "
            "contexto a seguir. Retorne o resultado como structured_output dentro "
            "de um evento NDJSON 'result'. Contexto: "
            + json.dumps(context, ensure_ascii=False)
        )
        stdin_msg = json.dumps(
            {"event": "user", "message": {"content": prompt}}, ensure_ascii=False
        ) + "\n"

        try:
            proc = subprocess.run(
                cmd,
                input=stdin_msg,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=self.timeout_s,
            )
        except FileNotFoundError as exc:
            raise SemanticPlannerError(
                f"Binario '{self.binary}' nao encontrado no PATH."
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise SemanticPlannerError(
                f"Timeout ({self.timeout_s}s) executando '{self.binary}'."
            ) from exc

        if proc.returncode != 0:
            raise SemanticPlannerError(
                f"'{self.binary}' falhou (codigo {proc.returncode}): "
                f"{proc.stderr.strip()[:500]}"
            )

        # Interpretar stdout como NDJSON (linha por linha).
        result_event: Optional[Dict[str, Any]] = None
        for line in proc.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as exc:
                raise SemanticPlannerError(
                    f"Linha NDJSON malformada na saida de '{self.binary}': {exc}"
                ) from exc
            if isinstance(obj, dict) and (
                obj.get("event") == "result" or obj.get("type") == "result"
            ):
                result_event = obj

        if result_event is None:
            raise SemanticPlannerError(
                f"Evento terminal 'result' nao encontrado na saida de '{self.binary}'."
            )

        # Verificar status == 'SUCCESS'.
        status = result_event.get("status")
        if status is None:
            inner = result_event.get("result")
            if isinstance(inner, dict):
                status = inner.get("status")
        if status != "SUCCESS":
            raise SemanticPlannerError(
                f"Status nao e SUCCESS na saida de '{self.binary}': {status!r}"
            )

        # Extrair structured_output.
        structured = result_event.get("structured_output")
        if not isinstance(structured, dict):
            inner = result_event.get("result")
            if isinstance(inner, dict):
                structured = inner.get("structured_output")
        if not isinstance(structured, dict):
            raise SemanticPlannerError(
                f"structured_output ausente ou invalido na saida de '{self.binary}'."
            )

        return structured


class OpenCodeCliProvider:
    """Provedor que invoca a CLI 'opencode run' via subprocess.

    Comando: opencode run <prompt>
    Entrada: prompt textual via stdin/argumento.
    Saida: JSON no stdout (o agente deve retornar JSON valido).
    """

    def __init__(
        self,
        timeout_s: float = 30.0,
        binary: str = "opencode",
    ) -> None:
        self.timeout_s = timeout_s
        self.binary = binary

    def plan(self, context: Dict[str, Any]) -> Dict[str, Any]:
        prompt = (
            "Gere um plano semantico editorial em JSON (schema 1.0.0) a partir do "
            "contexto a seguir. Responda APENAS com o JSON valido, sem texto extra. "
            f"Contexto: {json.dumps(context, ensure_ascii=False)}"
        )
        try:
            proc = subprocess.run(
                [self.binary, "run", prompt],
                capture_output=True,
                text=True,
                timeout=self.timeout_s,
            )
        except FileNotFoundError as exc:
            raise SemanticPlannerError(
                f"Binario '{self.binary}' nao encontrado no PATH."
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise SemanticPlannerError(
                f"Timeout ({self.timeout_s}s) executando '{self.binary}'."
            ) from exc

        if proc.returncode != 0:
            raise SemanticPlannerError(
                f"'{self.binary}' falhou (codigo {proc.returncode}): "
                f"{proc.stderr.strip()[:500]}"
            )

        stdout = proc.stdout.strip()
        # Tenta extrair um bloco JSON do stdout (remove possíveis wrappers de texto).
        start = stdout.find("{")
        end = stdout.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise SemanticPlannerError(
                f"Nenhum objeto JSON encontrado na saida de '{self.binary}'."
            )
        try:
            return json.loads(stdout[start : end + 1])
        except json.JSONDecodeError as exc:
            raise SemanticPlannerError(
                f"Saida JSON invalida de '{self.binary}': {exc}"
            ) from exc


class CallableMockProvider:
    """Provedor mock/injecao de dependencia para testes e desenvolvimento.

    Chama uma funcao callable fornecida pelo usuario com o contexto.
    """

    def __init__(self, callable_fn: Callable[[Dict[str, Any]], Dict[str, Any]]) -> None:
        self._fn = callable_fn

    def plan(self, context: Dict[str, Any]) -> Dict[str, Any]:
        return self._fn(context)


# ---------------------------------------------------------------------------
# Plano de fallback conservador (sem alegar compreensao semantica)
# ---------------------------------------------------------------------------


def _detect_fallback_cleanups(
    segments: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Detecta vicios de linguagem e repeticoes consecutivas de forma deterministica."""
    repeticoes: List[Dict[str, Any]] = []
    falsos_comecos: List[Dict[str, Any]] = []
    prev_norm = ""
    prev_seg_id: Any = None
    prev_word_ref: Optional[str] = None
    prev_start = 0.0
    prev_end = 0.0
    prev_raw_word = ""

    for seg in segments:
        sid = seg.get("id", seg.get("segment_id"))
        for w in seg.get("words", []) or []:
            raw_w = str(w.get("word", w.get("w", ""))).strip()
            if not raw_w:
                continue
            w_start = float(w.get("start", w.get("t", seg.get("start", 0.0))))
            w_end = float(w.get("end", w.get("f", w_start)))
            if w_end < w_start:
                w_end = w_start
            wid = w.get("word_id")
            norm = "".join(ch for ch in raw_w.lower() if ch.isalnum())

            grounding: Dict[str, Any] = {}
            if sid is not None:
                grounding["segment_ids"] = [sid]
            elif wid is not None:
                grounding["word_refs"] = [str(wid)]
            else:
                prev_norm = norm
                continue

            if norm in FILLER_WORDS or raw_w.lower().strip(".,!?;:") in FILLER_WORDS:
                falsos_comecos.append(
                    {
                        "texto": raw_w,
                        "justificativa": f"Vicio de linguagem detectado ('{raw_w}').",
                        "raw_start": round(max(0.0, w_start), 3),
                        "raw_end": round(max(0.0, w_end), 3),
                        **grounding,
                    }
                )
            elif norm and norm == prev_norm and (w_start - prev_end) <= 1.2:
                rep_grounding = (
                    {"segment_ids": [prev_seg_id]}
                    if prev_seg_id is not None
                    else ({"word_refs": [prev_word_ref]} if prev_word_ref else grounding)
                )
                repeticoes.append(
                    {
                        "texto": prev_raw_word or raw_w,
                        "justificativa": f"Repeticao consecutiva de '{prev_raw_word or raw_w}'.",
                        "raw_start": round(max(0.0, prev_start), 3),
                        "raw_end": round(max(0.0, prev_end), 3),
                        **rep_grounding,
                    }
                )

            prev_norm = norm
            prev_seg_id = sid
            prev_word_ref = str(wid) if wid is not None else None
            prev_start = w_start
            prev_end = w_end
            prev_raw_word = raw_w

    return repeticoes, falsos_comecos


def _fallback_plan(
    marca_id: str,
    episodio_id: str,
    transcript_data: Dict[str, Any],
    brand_profile: Dict[str, Any],
    user_brief: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Construi um plano semantico conservador sem alegar compreensao.

    Usado quando nao ha consentimento autorizado ou quando o provedor falha.
    Referencia apenas segmentos/palavras reais da transcricao.
    """
    segments = transcript_data.get("segments", []) if isinstance(transcript_data, dict) else []
    max_end = max([float(s.get("end", s.get("raw_end", 0.0))) for s in segments] + [0.0])
    all_seg_ids: List[Any] = []
    first_word_ids: List[str] = []

    for seg in segments:
        try:
            float(seg.get("end", seg.get("raw_end", 0.0)))
        except (TypeError, ValueError):
            pass
        sid = seg.get("id", seg.get("segment_id"))
        if sid is not None and sid not in all_seg_ids:
            all_seg_ids.append(sid)
        words = seg.get("words", [])
        for w in words[:3]:
            wid = w.get("word_id")
            if wid is not None:
                first_word_ids.append(str(wid))

    if not segments:
        all_seg_ids = ["seg-0"]
        first_word_ids = ["w-0"]
    elif not all_seg_ids:
        all_seg_ids = ["seg-0"]

    presenter = brand_profile.get("apresentador", "Apresentador") if isinstance(brand_profile, dict) else "Apresentador"
    canal = brand_profile.get("display_name", marca_id) if isinstance(brand_profile, dict) else marca_id
    repeticoes_fb, falsos_fb = _detect_fallback_cleanups(segments)
    pedido = str((user_brief or {}).get("pedido_usuario") or "").strip()
    notas = (
        "Plano de fallback gerado localmente sem chamada a provedor de IA. "
        "Nao faz afirmacoes de analise semantica. Requer revisao humana."
    )
    if pedido:
        notas += f" Pedido do usuario registrado: {pedido}"

    full_end = round(max_end, 3) if max_end > 0.0 else 1.0

    return {
        "schema_version": SEMANTIC_PLAN_SCHEMA_VERSION,
        "tema_central": (
            f"Episodio do canal {canal} apresentado por {presenter}. "
            "Plano de fallback conservador gerado sem autorizacao de IA externa."
        ),
        "tese_principal": (
            "O conteudo deve ser revisado por um editor humano antes de "
            "qualquer decisao de corte ou movimento grafico."
        ),
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "provedor": "fallback_local",
        "autorizado": False,
        "topicos": [
            {
                "topic_id": "T1",
                "titulo": "Abertura e apresentacao",
                "justificativa": (
                    "Referencia aos segmentos da transcricao sem "
                    "interpretacao semantica (fallback conservador)."
                ),
                "raw_start": 0.0,
                "raw_end": full_end,
                "segment_ids": list(all_seg_ids),
                "word_refs": first_word_ids[:3],
            }
        ],
        "argumentos": [],
        "grupos_explicacao": [],
        "ganchos_e_viradas": [],
        "repeticoes_dispensaveis": repeticoes_fb,
        "falsos_comecos": falsos_fb,
        "segmentos_editoriais": [
            {
                "decision": "preservar",
                "topic_id": "T1",
                "justificativa": (
                    "Preservacao conservativa da transcricao "
                    "(fallback, sem decisao semantica automatica)."
                ),
                "raw_start": 0.0,
                "raw_end": full_end,
                "segment_ids": list(all_seg_ids),
                "word_refs": first_word_ids[:3],
            }
        ],
        "intencoes_visuais": [],
        "notas": notas,
    }


# ---------------------------------------------------------------------------
# Coleta de artefatos do episodio
# ---------------------------------------------------------------------------


def _collect_episode_context(
    loader: WorkspaceLoader,
    marca_id: str,
    episodio_id: str,
) -> Dict[str, Any]:
    """Coleta os metadados textuais do episodio para o contexto do planejador.

    Nao retorna midia bruta, apenas informacoes textuais e resumos.
    """
    fonte_dir = loader.resolve_episodio_asset(
        marca_id, episodio_id, "workspace/fonte"
    )

    # Usa a transcrição editorial resolvida (revisada se válida, senão original),
    # garantindo que o provedor semântico veja exatamente a mesma versão
    # consumida pelo edl_builder, briefing e pipeline.
    editorial_transcript = None
    try:
        editorial_transcript = resolve_editorial_transcript(fonte_dir)
    except TranscriptReviewError:
        # Se a revisão estiver desatualizada/corrompida, não cai silenciosamente
        # em dados errados: propaga o erro.
        raise

    transcript_data: Dict[str, Any] = {}
    if editorial_transcript is not None:
        segments = editorial_transcript.get("segments", [])
        transcript_data = {
            "schema_version": "1.0.0",
            "engine": "faster-whisper",
            "language": "pt",
            "source_kind": editorial_transcript.get("source_kind", "raw_transcript"),
            "transcript_sha256": editorial_transcript.get("transcript_sha256"),
            "base_transcript_sha256": editorial_transcript.get(
                "base_transcript_sha256"
            ),
            "segments": segments,
        }

    alignment_data: Dict[str, Any] = {}
    alignment_path = fonte_dir / "alignment.json"
    if alignment_path.is_file():
        alignment_data = json.loads(
            alignment_path.read_text(encoding="utf-8", errors="replace")
        )

    phonetic_data: Dict[str, Any] = {}
    phonetic_path = fonte_dir / "phonetic_report.json"
    if phonetic_path.is_file():
        phonetic_data = json.loads(
            phonetic_path.read_text(encoding="utf-8", errors="replace")
        )

    # Resumo de media_info (apenas textual, nunca o arquivo bruto).
    media_info: Dict[str, Any] = {}
    projeto = loader.load_project(marca_id, episodio_id)
    media_info = projeto.get("media_info", {}) or {}
    vid_info = media_info.get("video", {}) or {}
    try:
        vid_w = int(vid_info.get("width") or 0)
        vid_h = int(vid_info.get("height") or 0)
    except (TypeError, ValueError):
        vid_w, vid_h = 0, 0
    if vid_h > vid_w > 0:
        native_aspect_ratio = "9:16"
        target_resolution = [1080, 1920]
    else:
        native_aspect_ratio = "16:9"
        target_resolution = [1920, 1080]

    briefing_dir = loader.resolve_episodio_asset(
        marca_id, episodio_id, "workspace/briefing"
    )
    user_brief = load_user_brief(briefing_dir)

    # Verificacao de integridade SHA-256 dos arquivos em brutos/ (se disponivel).
    sources = projeto.get("sources", [])
    integrity_ok = True
    integrity_details: List[str] = []
    for src in sources:
        sha = src.get("sha256")
        path = src.get("path")
        if sha and path:
            p = Path(path)
            if p.is_file():
                from core.ingest import compute_sha256

                actual = compute_sha256(str(p))
                if actual != sha:
                    integrity_ok = False
                    integrity_details.append(
                        f"SHA-256 diverge para {path}"
                    )
            else:
                integrity_details.append(f"Arquivo nao encontrado: {path}")

    media_info_summary = {
        k: v for k, v in media_info.items()
        if k not in ("waveform", "samples", "raw_bytes")
    }
    media_info_summary["native_aspect_ratio"] = native_aspect_ratio
    media_info_summary["target_resolution"] = target_resolution

    contexto = {
        "marca_id": marca_id,
        "episodio_id": episodio_id,
        "transcript": transcript_data,
        "alignment": alignment_data,
        "phonetic_report": phonetic_data,
        "user_brief": user_brief,
        "media_info_summary": media_info_summary,
        "sources": [
            {k: v for k, v in src.items() if k != "path"}
            for src in sources
        ],
        "integrity_ok": integrity_ok,
        "integrity_details": integrity_details,
        "editorial_transcript_source": (
            editorial_transcript.get("source_kind") if editorial_transcript else None
        ),
        "brand_profile_textual": {
            k: v
            for k, v in (loader.load_brand_profile(marca_id) or {}).items()
            if k != "config_json"
            and not isinstance(v, (dict, list))
        },
    }
    return contexto


# ---------------------------------------------------------------------------
# Funcao principal
# ---------------------------------------------------------------------------


def plan_episodio_semantics(
    marca_id: str,
    episodio_id: str,
    workspace_root: str | Path,
    provider: Optional[SemanticPlannerProvider] = None,
    authorized: bool = False,
    destination: Optional[str] = None,
    shared_data: Optional[List[str]] = None,
    consent_notes: Optional[str] = None,
    write_files: bool = True,
) -> Dict[str, Any]:
    """Planeja a semantica editorial de um episodio.

    Fluxo:
      1. Carrega workspace, brand_profile e project.json do episodio.
      2. Coleta artefatos textuais (transcript, alignment, phonetic, media_info).
      3. Verifica integridade SHA-256 dos arquivos em brutos/.
      4. Cria registro de SemanticConsent (authorized=False por padrao).
      5. Se authorized=True e provider fornecido: chama provider.plan(contexto).
         Senao: gera plano de fallback conservador.
      6. Valida o plano com validate_semantic_plan (schema 1.0.0).
      7. Grava workspace/briefing/semantic_plan.json e semantic_consent.json
         (quando write_files=True e o plano e valido).
      8. Retorna dicionario com o resultado.

    Nao envia midia bruta. Nao usa chaves comerciais de API.
    """
    loader = WorkspaceLoader(workspace_root)
    loader.load_workspace()

    # Carrega perfil da marca e projeto do episodio.
    try:
        marca_profile = loader.load_brand_profile(marca_id)
    except WorkspaceError as exc:
        raise SemanticPlannerError(f"Marca nao encontrada: {marca_id}") from exc

    try:
        projeto = loader.load_project(marca_id, episodio_id)
    except WorkspaceError as exc:
        raise SemanticPlannerError(
            f"Episodio nao encontrado: {marca_id}/{episodio_id}"
        ) from exc

    # Contexto textual (sem midia bruta).
    contexto = _collect_episode_context(loader, marca_id, episodio_id)
    transcript_data = contexto.get("transcript", {})

    # Registro de consentimento.
    if shared_data is None:
        shared_data = list(TEXTUAL_DATA_KINDS)
    if destination is None:
        destination = "local_provedor_semantico"
    consent = SemanticConsent(
        destination=destination,
        shared_data=list(shared_data),
        authorized=bool(authorized),
        notes=consent_notes or "",
    )

    resultado: Dict[str, Any] = {
        "marca_id": marca_id,
        "episodio_id": episodio_id,
        "workspace_root": str(workspace_root),
        "consent": consent.to_dict(),
        "integrity_ok": contexto.get("integrity_ok", True),
        "integrity_details": contexto.get("integrity_details", []),
        "plan": None,
        "validated": False,
        "provider": None,
        "fallback": False,
        "error": None,
    }

    # Execucao com consentimento ou fallback.
    plano: Optional[Dict[str, Any]] = None
    used_provider = None
    is_fallback = False

    if consent.authorized and provider is not None:
        used_provider = provider.__class__.__name__
        try:
            plano = provider.plan(contexto)
            resultado["provider"] = used_provider
        except SemanticPlannerError as exc:
            # Falha de comunicacao/timeout/JSON invalido: fallback seguro.
            resultado["error"] = str(exc)
            is_fallback = True
    else:
        # Sem consentimento autorizado: NAO chama provedor externo.
        if not consent.authorized:
            resultado["error"] = (
                "Consentimento nao autorizado. Plano de fallback gerado "
                "localmente sem chamada a provedor externo."
            )
        elif provider is None:
            resultado["error"] = (
                "Nenhum provedor informado. Plano de fallback gerado localmente."
            )
        is_fallback = True

    if is_fallback or plano is None:
        plano = _fallback_plan(
            marca_id=marca_id,
            episodio_id=episodio_id,
            transcript_data=transcript_data,
            brand_profile=marca_profile,
            user_brief=contexto.get("user_brief"),
        )
        resultado["provider"] = "fallback_local"
        resultado["fallback"] = True

    # Validacao obrigatoria do plano.
    try:
        validate_semantic_plan(plano, transcript_data=transcript_data)
        resultado["validated"] = True
    except SemanticPlanError as exc:
        # Plano invalido: substitui por fallback conservador e registra o erro.
        resultado["validation_error"] = str(exc)
        plano = _fallback_plan(
            marca_id=marca_id,
            episodio_id=episodio_id,
            transcript_data=transcript_data,
            brand_profile=marca_profile,
            user_brief=contexto.get("user_brief"),
        )
        try:
            validate_semantic_plan(plano, transcript_data=transcript_data)
            resultado["validated"] = True
        except SemanticPlanError as exc2:
            resultado["validation_error"] = (
                f"original: {exc}; fallback: {exc2}"
            )
            resultado["validated"] = False
        resultado["provider"] = "fallback_local"
        resultado["fallback"] = True
        if not resultado["error"]:
            resultado["error"] = str(exc)

    resultado["plan"] = plano

    # Gravacao dos arquivos de saida.
    if write_files and resultado["validated"]:
        briefing_dir = loader.resolve_episodio_asset(
            marca_id, episodio_id, "workspace/briefing"
        )
        briefing_dir.mkdir(parents=True, exist_ok=True)

        plan_path = briefing_dir / "semantic_plan.json"
        with open(plan_path, "w", encoding="utf-8") as f:
            json.dump(plano, f, indent=2, ensure_ascii=False)
        resultado["plan_path"] = str(plan_path)

        consent_path = briefing_dir / "semantic_consent.json"
        with open(consent_path, "w", encoding="utf-8") as f:
            json.dump(consent.to_dict(), f, indent=2, ensure_ascii=False)
        resultado["consent_path"] = str(consent_path)

    return resultado


def load_semantic_consent(
    marca_id: str,
    episodio_id: str,
    workspace_root: str | Path,
) -> Optional[SemanticConsent]:
    """Carrega o semantic_consent.json do episodio, se existir."""
    loader = WorkspaceLoader(workspace_root)
    loader.load_workspace()
    briefing_dir = loader.resolve_episodio_asset(
        marca_id, episodio_id, "workspace/briefing"
    )
    consent_path = briefing_dir / "semantic_consent.json"
    if not consent_path.is_file():
        return None
    try:
        data = json.loads(consent_path.read_text(encoding="utf-8"))
        return SemanticConsent.from_dict(data)
    except (json.JSONDecodeError, TypeError, KeyError):
        return None


def is_semantic_consent_authorized(
    marca_id: str,
    episodio_id: str,
    workspace_root: str | Path,
) -> bool:
    """Retorna True se houver consentimento autorizado gravado."""
    consent = load_semantic_consent(marca_id, episodio_id, workspace_root)
    return consent is not None and consent.authorized
