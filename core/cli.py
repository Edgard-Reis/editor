# -*- coding: utf-8 -*-
"""core/cli.py

Interface de linha de comando unificada para o pipeline L1..L6 do Editor.

Executa estritamente as funcoes canonicas existentes (sem duplicar logica):

    python -m core.cli <comando> [opcoes] --workspace <raiz> --marca <id> --episodio <id>

Subcomandos:
    status   - mostra estado do episodio e proxima acao recomendada
    ingest   - recebe --source <video> e chama ingest_media
    analyze  - executa analyze_episodio (--whisper-model-path, --offline/--no-offline,
               --injected-json apenas para testes)
    review   - aplica revisao pontual (--corrections-json) via review_transcript +
               sync_alignment_with_editorial_transcript
    plan     - executa plan_episodio_semantics + gerar_briefing + build_edl_from_alignment
    render   - executa run_episode_pipeline (render/QA), proxima acao: approve
    approve  - aprova o master 16:9 via approve_master_16x9, proxima acao: shorts
    shorts   - derivados 9:16:
        shorts render   --clips-json <arquivo> (ou --clip id:start:end repetivel)
        shorts approve  --short-id <id> --by <nome>

Suporta --json para saida estruturada deterministica.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from .workspace import WorkspaceLoader, init_workspace  # noqa: F401
    from .ingest import ingest_media  # noqa: F401
    from .analyze import analyze_episodio  # noqa: F401
    from .transcript_review import (  # noqa: F401
        review_transcript,
        sync_alignment_with_editorial_transcript,
    )
    from .semantic_planner import (  # noqa: F401
        CallableMockProvider,
        SemanticConsent,
        load_user_brief,
        plan_episodio_semantics,
    )
    from .briefing import gerar_briefing  # noqa: F401
    from .edl_builder import build_edl_from_alignment  # noqa: F401
    from .master_lint import lint as lint_plan  # noqa: F401
    from .pipeline import (  # noqa: F401
        MasterApprovalError,
        PipelineError,
        approve_master_16x9,
        render_existing_episode,
        run_episode_pipeline,
        verify_master_16x9_approval,
    )
    from .shorts_renderer import (  # noqa: F401
        ShortsRenderError,
        approve_short_9x16,
        render_approved_shorts,
        render_shorts_from_master,
        suggest_shorts_opusclip,
    )
except ImportError:  # execucao direta como script
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from core.workspace import WorkspaceLoader, init_workspace  # type: ignore
    from core.ingest import ingest_media  # type: ignore
    from core.analyze import analyze_episodio  # type: ignore
    from core.transcript_review import (  # type: ignore
        review_transcript,
        sync_alignment_with_editorial_transcript,
    )
    from core.semantic_planner import (  # type: ignore
        CallableMockProvider,
        SemanticConsent,
        load_user_brief,
        plan_episodio_semantics,
    )
    from core.briefing import gerar_briefing  # type: ignore
    from core.edl_builder import build_edl_from_alignment  # type: ignore
    from core.master_lint import lint as lint_plan  # type: ignore
    from core.pipeline import (  # type: ignore
        MasterApprovalError,
        PipelineError,
        approve_master_16x9,
        render_existing_episode,
        run_episode_pipeline,
        verify_master_16x9_approval,
    )
    from core.shorts_renderer import (  # type: ignore
        ShortsRenderError,
        approve_short_9x16,
        render_approved_shorts,
        render_shorts_from_master,
        suggest_shorts_opusclip,
    )


class CliError(Exception):
    """Erro de execucao da CLI (saida com codigo != 0, sem traceback cru)."""


def _iso_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def _emit(obj: Any, json_mode: bool) -> None:
    if json_mode:
        print(json.dumps(obj, indent=2, ensure_ascii=False))
    else:
        print(obj)


def _fail(msg: str, json_mode: bool, code: int = 1) -> None:
    """Emite mensagem de erro compreensivel e sai com codigo != 0."""
    if json_mode:
        print(json.dumps({"ok": False, "error": msg}, ensure_ascii=False))
    else:
        print(f"ERRO: {msg}")
    raise SystemExit(code)


def _load_project(loader: WorkspaceLoader, marca_id: str, episodio_id: str) -> Dict[str, Any]:
    try:
        return loader.load_project(marca_id, episodio_id)
    except Exception as exc:
        raise CliError(f"projeto nao encontrado para {marca_id}/{episodio_id}: {exc}") from exc


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------


def cmd_status(args: argparse.Namespace, json_mode: bool) -> Dict[str, Any]:
    root = Path(args.workspace).resolve()
    loader = WorkspaceLoader(root)
    loader.load_workspace()

    projeto = _load_project(loader, args.marca, args.episodio)
    stage = projeto.get("current_stage", "desconhecido")

    fonte_dir = loader.resolve_episodio_asset(
        args.marca, args.episodio, "workspace/fonte"
    )
    transcript_path = fonte_dir / "transcript.json"
    reviewed_path = fonte_dir / "transcript_reviewed.json"
    alignment_path = fonte_dir / "alignment.json"

    transcricao_origem = "ausente"
    if reviewed_path.is_file():
        transcricao_origem = "reviewed"
    elif transcript_path.is_file():
        transcricao_origem = "raw"

    master_aprovado = False
    master_sha = None
    aprovacao = projeto.get("approvals", {}) or {}
    if aprovacao.get("master_16x9_approved"):
        master_aprovado = True
        master_sha = aprovacao.get("master_16x9_sha256")

    derivados = {}
    shorts_dir = loader.resolve_episodio_asset(
        args.marca, args.episodio, "workspace/renders/shorts"
    )
    manifest_path = shorts_dir / "shorts_manifest.json"
    if manifest_path.is_file():
        try:
            derivados = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            derivados = {}

    shorts_aprovados = sum(
        1 for d in derivados.values() if isinstance(d, dict) and d.get("approved")
    )
    shorts_total = len(derivados)

    proxima_acao = _proxima_acao(
        stage, transcricao_origem, master_aprovado, shorts_total, shorts_aprovados
    )

    estado: Dict[str, Any] = {
        "workspace": str(root),
        "marca": args.marca,
        "episodio": args.episodio,
        "current_stage": stage,
        "transcricao": {
            "origem": transcricao_origem,
            "transcript_json": str(transcript_path),
            "transcript_reviewed_json": str(reviewed_path),
            "alignment_json": str(alignment_path),
        },
        "master_16x9": {
            "aprovado": master_aprovado,
            "sha256": master_sha,
            "aprovado_por": aprovacao.get("master_16x9_approved_by"),
            "aprovado_em": aprovacao.get("master_16x9_approved_at"),
        },
        "shorts_9x16": {
            "total": shorts_total,
            "aprovados": shorts_aprovados,
            "manifest": str(manifest_path),
        },
        "proxima_acao": proxima_acao,
    }
    _emit(estado, json_mode)
    return estado


def _proxima_acao(
    stage: str,
    transcricao_origem: str,
    master_aprovado: bool,
    shorts_total: int,
    shorts_aprovados: int,
) -> str:
    if stage in (None, "", "desconhecido", "01_GRAVACAO_ORIGINAL"):
        return "Execute 'ingest --source <video>' para ingerir o video do episodio."
    if stage == "01_INGEST_COMPLETED" or transcricao_origem == "ausente":
        return "Execute 'analyze' para transcrever o episodio (local/offline ou injetado)."
    if transcricao_origem == "raw":
        return ("Execute 'review' para revisar a transcricao e, em seguida, "
                "'plan' para gerar o plano semantico/briefing/EDL.")
    if not master_aprovado:
        return ("Execute 'render' para renderizar o master e, depois, "
                "'approve' para aprovar o master 16:9.")
    if shorts_total == 0:
        return ("Execute 'shorts render --clips-json <arquivo>' para gerar "
                "derivados 9:16 do master aprovado.")
    if shorts_aprovados < shorts_total:
        return ("Execute 'shorts approve --short-id <id> --by <nome>' para "
                "aprovar os derivados pendentes.")
    return "Episodio completo: master aprovado e todos os derivados 9:16 aprovados."


# ---------------------------------------------------------------------------
# ingest
# ---------------------------------------------------------------------------


def cmd_ingest(args: argparse.Namespace, json_mode: bool) -> Dict[str, Any]:
    root = Path(args.workspace).resolve()
    loader = WorkspaceLoader(root)
    loader.load_workspace()
    loader.load_brand_profile(args.marca)  # garante marca existente

    if not args.source:
        raise CliError("--source e obrigatorio para 'ingest'.")
    src = Path(args.source)
    if not src.is_file() or src.stat().st_size <= 0:
        raise CliError(f"arquivo de origem invalido ou vazio: {src}")

    rc = ingest_media(str(src), args.marca, args.episodio, str(root))
    if rc != 0:
        raise CliError(f"ingest_media falhou com codigo {rc}.")

    projeto = loader.load_project(args.marca, args.episodio)
    fonte = (projeto.get("sources", []) or [{}])[0]
    resultado: Dict[str, Any] = {
        "ok": True,
        "comando": "ingest",
        "marca": args.marca,
        "episodio": args.episodio,
        "source": str(fonte.get("path", src)),
        "sha256": fonte.get("sha256"),
        "current_stage": projeto.get("current_stage"),
    }
    _emit(resultado, json_mode)
    return resultado


# ---------------------------------------------------------------------------
# analyze
# ---------------------------------------------------------------------------


def _load_injected_words(injected_json: Optional[str]) -> Optional[List[Dict[str, Any]]]:
    if not injected_json:
        return None
    pj = Path(injected_json)
    if not pj.is_file():
        raise CliError(f"arquivo de transcricao injetada nao encontrado: {pj}")
    try:
        dados = json.loads(pj.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CliError(f"JSON invalido em --injected-json: {exc}") from exc
    if isinstance(dados, list):
        return dados
    if isinstance(dados, dict) and isinstance(dados.get("palavras"), list):
        return dados["palavras"]
    if isinstance(dados, dict) and isinstance(dados.get("segments"), list):
        palavras: List[Dict[str, Any]] = []
        for seg in dados["segments"]:
            for w in seg.get("words", []) or []:
                palavras.append(
                    {
                        "w": w.get("word", w.get("w", "")),
                        "t": w.get("start", w.get("t", 0.0)),
                        "f": w.get("end", w.get("f", 0.0)),
                        "probability": w.get("probability"),
                    }
                )
        return palavras
    raise CliError("--injected-json nao contem palavras/segmentos validos.")


def cmd_analyze(args: argparse.Namespace, json_mode: bool) -> Dict[str, Any]:
    root = Path(args.workspace).resolve()
    loader = WorkspaceLoader(root)
    loader.load_workspace()

    transcricao_injetada = _load_injected_words(args.injected_json)

    offline_only = not getattr(args, "no_offline", False)
    if getattr(args, "offline", False):
        offline_only = True

    analysis = analyze_episodio(
        args.marca,
        args.episodio,
        str(root),
        transcricao_injetada=transcricao_injetada,
        whisper_model_path=args.whisper_model_path,
        offline_only=offline_only,
    )

    resultado: Dict[str, Any] = {
        "ok": True,
        "comando": "analyze",
        "marca": args.marca,
        "episodio": args.episodio,
        "transcription_origin": analysis.get("transcription", {}).get("origin"),
        "language": analysis.get("language"),
        "total_palavras": len(analysis.get("palavras", [])),
        "total_segments": len(analysis.get("segments", [])),
        "local_execution_confirmed": analysis.get("transcription", {}).get(
            "local_execution_confirmed"
        ),
        "local_files_only": analysis.get("transcription", {}).get("local_files_only"),
        "offline_only": analysis.get("transcription", {}).get("offline_only"),
    }
    _emit(resultado, json_mode)
    return resultado


# ---------------------------------------------------------------------------
# review
# ---------------------------------------------------------------------------


def cmd_review(args: argparse.Namespace, json_mode: bool) -> Dict[str, Any]:
    root = Path(args.workspace).resolve()
    loader = WorkspaceLoader(root)
    loader.load_workspace()

    fonte_dir = loader.resolve_episodio_asset(
        args.marca, args.episodio, "workspace/fonte"
    )
    transcript_path = fonte_dir / "transcript.json"
    if not transcript_path.is_file():
        raise CliError(
            "transcript.json nao encontrado. Rode 'analise' primeiro."
        )

    if not args.corrections_json:
        raise CliError("--corrections-json e obrigatorio para 'review'.")
    cj = Path(args.corrections_json)
    if not cj.is_file():
        raise CliError(f"arquivo de correcoes nao encontrado: {cj}")
    try:
        corrections = json.loads(cj.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CliError(f"JSON invalido em --corrections-json: {exc}") from exc
    if not isinstance(corrections, list):
        raise CliError("--corrections-json deve conter uma lista de correcoes.")

    review_result = review_transcript(
        transcript_path,
        corrections,
        reviewed_by=args.reviewed_by or "proprietario",
        reviewed_version="1.0.0",
    )

    # Re-sincroniza alignment.json / palavras.json / roteiro.txt a partir da
    # transcricao editorial resolvida (sem tocar em transcript.json).
    sync_result = sync_alignment_with_editorial_transcript(fonte_dir)

    resultado: Dict[str, Any] = {
        "ok": True,
        "comando": "review",
        "marca": args.marca,
        "episodio": args.episodio,
        "source_kind": sync_result.get("source_kind"),
        "total_corrections": len(review_result.get("human_corrections", [])),
        "reviewed_by": review_result.get("review_metadata", {}).get("reviewed_by"),
        "reviewed_at": review_result.get("review_metadata", {}).get("reviewed_at"),
        "proxima_acao": "Execute 'plan' para gerar o plano semantico/briefing/EDL "
                        "com a transcricao revisada.",
    }
    _emit(resultado, json_mode)
    return resultado


# ---------------------------------------------------------------------------
# plan
# ---------------------------------------------------------------------------


def cmd_plan(args: argparse.Namespace, json_mode: bool) -> Dict[str, Any]:
    root = Path(args.workspace).resolve()
    loader = WorkspaceLoader(root)
    loader.load_workspace()

    projeto = _load_project(loader, args.marca, args.episodio)

    # Fallback local sem consentimento; provedor apenas se autorizado.
    authorized = bool(getattr(args, "authorize", False))
    consent = SemanticConsent(
        destination="cli_local",
        shared_data=["transcript.json", "alignment.json", "phonetic_report.json"],
        authorized=authorized,
        notes="Plano gerado via CLI (fallback local sem consentimento).",
    )

    semantic_result = plan_episodio_semantics(
        marca_id=args.marca,
        episodio_id=args.episodio,
        workspace_root=str(root),
        provider=None,
        authorized=authorized,
        destination=consent.destination,
        shared_data=list(consent.shared_data),
        consent_notes=consent.notes,
    )
    if not semantic_result.get("validated") or not semantic_result.get("plan"):
        raise CliError(
            "semantic_plan invalido: "
            f"{semantic_result.get('validation_error') or semantic_result.get('error')}"
        )

    # Briefing + EDL.
    semantic_plan_path = loader.resolve_episodio_asset(
        args.marca, args.episodio, "workspace/briefing/semantic_plan.json"
    )
    semantic_plan_path.parent.mkdir(parents=True, exist_ok=True)
    semantic_plan_path.write_text(
        json.dumps(semantic_result["plan"], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    rc = gerar_briefing(
        args.marca,
        args.episodio,
        str(root),
        marca_profile=loader.load_brand_profile(args.marca),
        semantic_plan_path=semantic_plan_path,
    )
    if rc != 0:
        raise CliError(f"gerar_briefing falhou com codigo {rc}.")

    loader.load_workspace()  # recarrega apos gravacao de briefing
    edl, editorial_plan = build_edl_from_alignment(
        alignment_path=loader.resolve_episodio_asset(
            args.marca, args.episodio, "workspace/fonte/alignment.json"
        ),
        workspace_root=str(root),
        marca_id=args.marca,
        episodio_id=args.episodio,
        brand_profile=loader.load_brand_profile(args.marca),
        semantic_plan_path=semantic_plan_path,
    )

    resultado: Dict[str, Any] = {
        "ok": True,
        "comando": "plan",
        "marca": args.marca,
        "episodio": args.episodio,
        "provider": semantic_result.get("provider"),
        "fallback": bool(semantic_result.get("fallback")),
        "authorized": authorized,
        "timeline_events": len(edl.get("timeline_events", [])),
        "final_duration_seconds": edl.get("summary", {}).get("final_duration_seconds"),
        "proxima_acao": "Execute 'render' para renderizar o master (L1..L6 + QA).",
    }
    _emit(resultado, json_mode)
    return resultado


# ---------------------------------------------------------------------------
# render
# ---------------------------------------------------------------------------


def cmd_render(args: argparse.Namespace, json_mode: bool) -> Dict[str, Any]:
    root = Path(args.workspace).resolve()
    loader = WorkspaceLoader(root)
    loader.load_workspace()

    # Re-rende o episodio existente (reutiliza artefatos ja gerados),
    # sem re-transcrever com o modelo Whisper durante o render.
    resultado = render_existing_episode(
        str(root),
        args.marca,
        args.episodio,
        strict=True,
    )

    res: Dict[str, Any] = {
        "ok": bool(resultado.get("ok")),
        "comando": "render",
        "marca": args.marca,
        "episodio": args.episodio,
        "master_path": resultado.get("master_path"),
        "master_sha256": resultado.get("master_sha256"),
        "render_expected_duration_seconds": resultado.get(
            "render_expected_duration_seconds"
        ),
        "edl_final_duration_seconds": resultado.get("edl_final_duration_seconds"),
        "integrity_delta_hash_zero": bool(resultado.get("integrity_delta_hash_zero")),
        "qa_ok": bool((resultado.get("qa") or {}).get("ok")),
        "proxima_acao": ("Execute 'approve --by <nome>' para aprovar o master 16:9."
                         if bool(resultado.get("ok")) else "QA reprovado: verifique os problemas."),
    }
    _emit(res, json_mode)
    return res


# ---------------------------------------------------------------------------
# approve
# ---------------------------------------------------------------------------


def cmd_approve(args: argparse.Namespace, json_mode: bool) -> Dict[str, Any]:
    root = Path(args.workspace).resolve()
    if not args.by or not args.by.strip():
        raise CliError("--by e obrigatorio para 'approve'.")

    aprovacao = approve_master_16x9(
        str(root), args.marca, args.episodio, approved_by=args.by.strip()
    )
    res: Dict[str, Any] = {
        "ok": True,
        "comando": "approve",
        "marca": args.marca,
        "episodio": args.episodio,
        "master_16x9_approved": True,
        "master_path": aprovacao.get("master_path"),
        "master_sha256": aprovacao.get("master_sha256"),
        "approved_by": aprovacao.get("approved_by"),
        "approved_at": aprovacao.get("approved_at"),
        "proxima_acao": ("Execute 'shorts render --clips-json <arquivo>' para gerar "
                         "derivados verticais 9:16 do master aprovado."),
    }
    _emit(res, json_mode)
    return res


# ---------------------------------------------------------------------------
# shorts
# ---------------------------------------------------------------------------


def _parse_clips(clips_json: Optional[str], clip_repeat: List[str]) -> List[Dict[str, Any]]:
    clips: List[Dict[str, Any]] = []
    if clips_json:
        pj = Path(clips_json)
        if not pj.is_file():
            raise CliError(f"arquivo de clips nao encontrado: {pj}")
        try:
            dados = json.loads(pj.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise CliError(f"JSON invalido em --clips-json: {exc}") from exc
        if not isinstance(dados, list):
            raise CliError("--clips-json deve conter uma lista de clips.")
        clips = dados
    for item in clip_repeat:
        partes = item.split(":")
        if len(partes) != 3:
            raise CliError(
                f"--clip invalido '{item}': use o formato id:start:end."
            )
        short_id, start_s, end_s = partes
        try:
            start = float(start_s)
            end = float(end_s)
        except ValueError:
            raise CliError(f"start/end invalidos em --clip '{item}'.")
        clips.append({"short_id": short_id, "start": start, "end": end})
    return clips


def cmd_shorts_render(args: argparse.Namespace, json_mode: bool) -> Dict[str, Any]:
    root = Path(args.workspace).resolve()
    loader = WorkspaceLoader(root)
    loader.load_workspace()

    clips = _parse_clips(args.clips_json, args.clip)
    if not clips:
        raise CliError("informe pelo menos um clip (--clips-json ou --clip).")

    resultado = render_shorts_from_master(
        str(root), args.marca, args.episodio, clips
    )

    res: Dict[str, Any] = {
        "ok": True,
        "comando": "shorts render",
        "marca": args.marca,
        "episodio": args.episodio,
        "master_sha256": resultado.get("master_sha256"),
        "output_dir": resultado.get("output_dir"),
        "shorts": [
            {
                "short_id": s["short_id"],
                "output_path": s["output_path"],
                "output_sha256": s["output_sha256"],
                "start": s["start"],
                "end": s["end"],
                "duration_seconds": s["duration_seconds"],
                "qa_ok": bool((s.get("qa") or {}).get("ok")),
                "approved": bool(s.get("approved")),
            }
            for s in resultado.get("shorts", [])
        ],
        "proxima_acao": ("Execute 'shorts approve --short-id <id> --by <nome>' para "
                         "aprovar os derivados gerados."),
    }
    _emit(res, json_mode)
    return res


def cmd_shorts_approve(args: argparse.Namespace, json_mode: bool) -> Dict[str, Any]:
    root = Path(args.workspace).resolve()
    if not args.short_id:
        raise CliError("--short-id e obrigatorio para 'shorts approve'.")
    if not args.by or not args.by.strip():
        raise CliError("--by e obrigatorio para 'shorts approve'.")

    aprovacao = approve_short_9x16(
        str(root), args.marca, args.episodio, args.short_id, approved_by=args.by.strip()
    )
    res: Dict[str, Any] = {
        "ok": True,
        "comando": "shorts approve",
        "marca": args.marca,
        "episodio": args.episodio,
        "short_id": args.short_id,
        "approved": True,
        "output_path": aprovacao.get("output_path"),
        "output_sha256": aprovacao.get("output_sha256"),
        "approved_by": aprovacao.get("approved_by"),
        "approved_at": aprovacao.get("approved_at"),
        "proxima_acao": ("Todos os derivados aprovados. Episodio completo."
                         if _todos_aprovados(root, args.marca, args.episodio)
                         else "Aprove os derivados restantes com 'shorts approve'."),
    }
    _emit(res, json_mode)
    return res


def _todos_aprovados(root: Path, marca_id: str, episodio_id: str) -> bool:
    loader = WorkspaceLoader(root)
    loader.load_workspace()
    shorts_dir = loader.resolve_episodio_asset(
        marca_id, episodio_id, "workspace/renders/shorts"
    )
    manifest_path = shorts_dir / "shorts_manifest.json"
    if not manifest_path.is_file():
        return False
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return False
    if not manifest:
        return False
    return all(bool(d.get("approved")) for d in manifest.values() if isinstance(d, dict))


# ---------------------------------------------------------------------------
# Portoes Humanos (prepare-brief, render-master, suggest-shorts, render-shorts)
# ---------------------------------------------------------------------------


def _collect_low_confidence_words(transcript_path: Path, threshold: float = 0.80) -> List[Dict[str, Any]]:
    if not transcript_path.is_file():
        return []
    try:
        data = json.loads(transcript_path.read_text(encoding="utf-8", errors="replace"))
    except (json.JSONDecodeError, OSError):
        return []
    out: List[Dict[str, Any]] = []
    for seg in data.get("segments", []) or []:
        for w in seg.get("words", []) or []:
            prob = w.get("probability")
            if prob is not None:
                try:
                    p = float(prob)
                except (TypeError, ValueError):
                    continue
                if p < threshold:
                    out.append({
                        "word": w.get("word", w.get("w", "")),
                        "start": w.get("start", w.get("t", 0.0)),
                        "end": w.get("end", w.get("f", 0.0)),
                        "probability": round(p, 3),
                        "context": seg.get("text", ""),
                    })
    return out


def cmd_prepare_brief(args: argparse.Namespace, json_mode: bool) -> Dict[str, Any]:
    """Ingestao + transcricao/revisao + BRIEFING.md + edl_longo.json e PARA (Portao 1)."""
    root = Path(args.workspace).resolve()
    loader = WorkspaceLoader(root)
    loader.load_workspace()
    brand_profile = loader.load_brand_profile(args.marca)

    briefing_dir = loader.resolve_episodio_asset(
        args.marca, args.episodio, "workspace/briefing"
    )
    briefing_dir.mkdir(parents=True, exist_ok=True)
    fonte_dir = loader.resolve_episodio_asset(
        args.marca, args.episodio, "workspace/fonte"
    )

    if getattr(args, "user_brief_json", None):
        ub_src = Path(args.user_brief_json)
        if not ub_src.is_file():
            raise CliError(f"user_brief.json nao encontrado: {ub_src}")
        try:
            ub_data = json.loads(ub_src.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise CliError(f"JSON invalido em --user-brief-json: {exc}") from exc
        if not isinstance(ub_data, dict):
            raise CliError("--user-brief-json deve conter um objeto JSON.")
        (briefing_dir / "user_brief.json").write_text(
            json.dumps(ub_data, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    user_brief = load_user_brief(briefing_dir)

    projeto = None
    try:
        projeto = loader.load_project(args.marca, args.episodio)
    except Exception:
        projeto = None

    # 1. Ingestao (se --source informado ou ainda nao ingerido)
    if getattr(args, "source", None):
        src = Path(args.source)
        if not src.is_file() or src.stat().st_size <= 0:
            raise CliError(f"arquivo de origem invalido ou vazio: {src}")
        rc = ingest_media(str(src), args.marca, args.episodio, str(root))
        if rc != 0:
            raise CliError(f"ingest_media falhou com codigo {rc}.")
        projeto = loader.load_project(args.marca, args.episodio)
    elif projeto is None or not (projeto.get("sources") or []):
        raise CliError("--source e obrigatorio quando o episodio ainda nao foi ingerido.")

    # 2. Analise / Transcricao
    transcript_path = fonte_dir / "transcript.json"
    transcricao_injetada = _load_injected_words(getattr(args, "injected_json", None))
    if transcricao_injetada is not None or not transcript_path.is_file():
        offline_only = not getattr(args, "no_offline", False)
        if getattr(args, "offline", False):
            offline_only = True
        analyze_episodio(
            args.marca,
            args.episodio,
            str(root),
            transcricao_injetada=transcricao_injetada,
            whisper_model_path=getattr(args, "whisper_model_path", None),
            offline_only=offline_only,
        )

    # 3. Revisao pontual (por --corrections-json ou user_brief.correcoes_ortograficas)
    corrections: Optional[List[Dict[str, Any]]] = None
    if getattr(args, "corrections_json", None):
        cj = Path(args.corrections_json)
        if not cj.is_file():
            raise CliError(f"arquivo de correcoes nao encontrado: {cj}")
        try:
            corrections = json.loads(cj.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise CliError(f"JSON invalido em --corrections-json: {exc}") from exc
        if not isinstance(corrections, list):
            raise CliError("--corrections-json deve conter uma lista de correcoes.")
    elif user_brief.get("correcoes_ortograficas") and not (fonte_dir / "transcript_reviewed.json").is_file():
        corrections = user_brief["correcoes_ortograficas"]

    if corrections:
        review_transcript(
            transcript_path,
            corrections,
            reviewed_by=getattr(args, "reviewed_by", None) or "proprietario",
            reviewed_version="1.0.0",
        )
        sync_alignment_with_editorial_transcript(fonte_dir)

    low_conf = _collect_low_confidence_words(transcript_path, threshold=0.80)

    # 4. Roteamento de modo: 'so_cortes' pula Master e vai direto ao Portao 2 (suggest-shorts)
    if user_brief.get("modo") == "so_cortes":
        res_so_cortes: Dict[str, Any] = {
            "ok": True,
            "comando": "prepare-brief",
            "marca": args.marca,
            "episodio": args.episodio,
            "modo": "so_cortes",
            "low_confidence_words": low_conf,
            "requires_human_approval": True,
            "stopped_at_gate": "portao_1_roteamento_so_cortes",
            "proxima_acao": "Modo 'so_cortes': pule Master e execute 'suggest-shorts' para curadoria OpusClip.",
        }
        _emit(res_so_cortes, json_mode)
        return res_so_cortes

    # 5. Modo completo: semantic_plan + BRIEFING.md + edl_longo.json (com Motion Graphics)
    authorized = bool(getattr(args, "authorize", False))
    semantic_result = plan_episodio_semantics(
        marca_id=args.marca,
        episodio_id=args.episodio,
        workspace_root=str(root),
        provider=None,
        authorized=authorized,
        destination="cli_local",
        shared_data=["transcript.json", "alignment.json", "phonetic_report.json", "user_brief.json"],
        consent_notes="Plano gerado via prepare-brief (Portao Humano 1).",
    )
    if not semantic_result.get("validated") or not semantic_result.get("plan"):
        raise CliError(
            "semantic_plan invalido: "
            f"{semantic_result.get('validation_error') or semantic_result.get('error')}"
        )

    semantic_plan_path = briefing_dir / "semantic_plan.json"
    rc = gerar_briefing(
        args.marca,
        args.episodio,
        str(root),
        marca_profile=brand_profile,
        semantic_plan_path=semantic_plan_path,
    )
    if rc != 0:
        raise CliError(f"gerar_briefing falhou com codigo {rc}.")

    edl, editorial_plan = build_edl_from_alignment(
        alignment_path=fonte_dir / "alignment.json",
        workspace_root=str(root),
        marca_id=args.marca,
        episodio_id=args.episodio,
        brand_profile=brand_profile,
        semantic_plan_path=semantic_plan_path,
        ensure_motion_layers=True,
    )

    res: Dict[str, Any] = {
        "ok": True,
        "comando": "prepare-brief",
        "marca": args.marca,
        "episodio": args.episodio,
        "modo": "completo",
        "target_format": edl.get("target_format", {}),
        "briefing_md": str(briefing_dir / "BRIEFING.md"),
        "briefing_json": str(briefing_dir / "briefing.json"),
        "edl_longo": str(briefing_dir / "edl_longo.json"),
        "editorial_plan": str(briefing_dir / "editorial_plan.json"),
        "timeline_events": len(edl.get("timeline_events", [])),
        "final_duration_seconds": edl.get("summary", {}).get("final_duration_seconds"),
        "layer_summary": editorial_plan.get("layer_summary", {}),
        "low_confidence_words": low_conf,
        "requires_human_approval": True,
        "stopped_at_gate": "portao_1_briefing_master",
        "proxima_acao": "Revise BRIEFING.md (Portao Humano 1) e execute 'render-master' apos aprovacao.",
    }
    _emit(res, json_mode)
    return res


def cmd_render_master(args: argparse.Namespace, json_mode: bool) -> Dict[str, Any]:
    """Executa QA (lint_plan) e renderiza o Master aprovado (suporta re-render pos-ajustes)."""
    root = Path(args.workspace).resolve()
    loader = WorkspaceLoader(root)
    loader.load_workspace()

    briefing_dir = loader.resolve_episodio_asset(
        args.marca, args.episodio, "workspace/briefing"
    )
    edl_path = briefing_dir / "edl_longo.json"
    plan_path = briefing_dir / "editorial_plan.json"
    if not edl_path.is_file() or not plan_path.is_file():
        raise CliError("edl_longo.json ou editorial_plan.json ausente. Execute 'prepare-brief' primeiro.")

    edl = json.loads(edl_path.read_text(encoding="utf-8"))
    editorial_plan = json.loads(plan_path.read_text(encoding="utf-8"))
    projeto = _load_project(loader, args.marca, args.episodio)

    lint_report = lint_plan(editorial_plan, edl, projeto)
    if not lint_report.get("ok"):
        raise CliError(
            "lint_plan reprovou antes do render: " + "; ".join(lint_report.get("failures", [])[:6])
        )

    strict = not bool(getattr(args, "no_strict", False))
    resultado = render_existing_episode(
        str(root),
        args.marca,
        args.episodio,
        strict=strict,
    )

    approved_info: Optional[Dict[str, Any]] = None
    if getattr(args, "by", None) and args.by.strip():
        approved_info = approve_master_16x9(
            str(root), args.marca, args.episodio, approved_by=args.by.strip()
        )

    res: Dict[str, Any] = {
        "ok": bool(resultado.get("ok")),
        "comando": "render-master",
        "marca": args.marca,
        "episodio": args.episodio,
        "master_path": resultado.get("master_path"),
        "master_sha256": resultado.get("master_sha256"),
        "target_format": resultado.get("target_format"),
        "render_expected_duration_seconds": resultado.get("render_expected_duration_seconds"),
        "edl_final_duration_seconds": resultado.get("edl_final_duration_seconds"),
        "integrity_delta_hash_zero": bool(resultado.get("integrity_delta_hash_zero")),
        "qa_ok": bool((resultado.get("qa") or {}).get("ok")),
        "approved": bool(approved_info and approved_info.get("approved")),
        "proxima_acao": "Revise o Master. Se desejar cortes curtos, execute 'suggest-shorts'.",
    }
    _emit(res, json_mode)
    return res


def cmd_suggest_shorts(args: argparse.Namespace, json_mode: bool) -> Dict[str, Any]:
    """Analisa arcos narrativos e gera shorts_briefing.md + shorts_plan.json (Portao 2)."""
    root = Path(args.workspace).resolve()
    res_sug = suggest_shorts_opusclip(
        str(root),
        args.marca,
        args.episodio,
        count=getattr(args, "count", None),
        modo=getattr(args, "modo", None),
    )
    res: Dict[str, Any] = {
        **res_sug,
        "comando": "suggest-shorts",
        "marca": args.marca,
        "episodio": args.episodio,
        "proxima_acao": "Revise shorts_briefing.md (Portao Humano 2) e execute 'render-shorts --short-ids ...'.",
    }
    _emit(res, json_mode)
    return res


def cmd_render_shorts(args: argparse.Namespace, json_mode: bool) -> Dict[str, Any]:
    """Renderiza via core/shorts_renderer.py apenas os cortes aprovados."""
    root = Path(args.workspace).resolve()

    clips: Optional[List[Dict[str, Any]]] = None
    if getattr(args, "clips_json", None) or getattr(args, "clip", None):
        clips = _parse_clips(getattr(args, "clips_json", None), getattr(args, "clip", []) or [])

    ids: Optional[List[str]] = None
    raw_ids = []
    if getattr(args, "short_ids", None):
        raw_ids.extend([x.strip() for x in str(args.short_ids).split(",") if x.strip()])
    if getattr(args, "short_id", None):
        raw_ids.extend([x.strip() for x in args.short_id if x and x.strip()])
    if raw_ids:
        ids = raw_ids

    resultado = render_approved_shorts(
        str(root),
        args.marca,
        args.episodio,
        approved_short_ids=ids,
        clips=clips,
        approved_by=getattr(args, "by", None),
    )

    res: Dict[str, Any] = {
        "ok": True,
        "comando": "render-shorts",
        "marca": args.marca,
        "episodio": args.episodio,
        "master_sha256": resultado.get("master_sha256"),
        "output_dir": resultado.get("output_dir"),
        "shorts": [
            {
                "short_id": s["short_id"],
                "output_path": s["output_path"],
                "output_sha256": s["output_sha256"],
                "start": s["start"],
                "end": s["end"],
                "duration_seconds": s["duration_seconds"],
                "qa_ok": bool((s.get("qa") or {}).get("ok")),
            }
            for s in resultado.get("shorts", [])
        ],
    }
    _emit(res, json_mode)
    return res


# ---------------------------------------------------------------------------
# dispatch
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="core.cli",
        description="CLI unificada do pipeline L1..L6 do Editor.",
    )
    parser.add_argument("--workspace", required=True, help="Raiz do workspace.")
    parser.add_argument("--marca", required=True, help="ID da marca.")
    parser.add_argument("--episodio", required=True, help="ID do episodio.")
    parser.add_argument(
        "--json", action="store_true", help="Saida estruturada em JSON."
    )

    sub = parser.add_subparsers(dest="comando", required=True)

    p_status = sub.add_parser("status", help="Estado do episodio e proxima acao.")
    p_status.set_defaults(func=cmd_status)

    p_ingest = sub.add_parser("ingest", help="Ingere o video do episodio.")
    p_ingest.add_argument("--source", required=True, help="Video de origem.")
    p_ingest.set_defaults(func=cmd_ingest)

    p_analyze = sub.add_parser("analyze", help="Transcreve o episodio (local/offline ou injetado).")
    p_analyze.add_argument("--whisper-model-path", default=None, help="Snapshot local do faster-whisper.")
    p_analyze.add_argument("--offline", action="store_true", help="Forca modo offline (default).")
    p_analyze.add_argument("--no-offline", action="store_true", help="Desativa modo offline (nao recomendado).")
    p_analyze.add_argument("--injected-json", default=None, help="Transcricao injetada (apenas testes).")
    p_analyze.set_defaults(func=cmd_analyze)

    p_review = sub.add_parser("review", help="Revisao pontual da transcricao.")
    p_review.add_argument("--corrections-json", required=True, help="Arquivo com lista de correcoes.")
    p_review.add_argument("--reviewed-by", default="proprietario", help="Quem confirma a revisao.")
    p_review.set_defaults(func=cmd_review)

    p_plan = sub.add_parser("plan", help="Plano semantico + briefing + EDL.")
    p_plan.add_argument("--authorize", action="store_true", help="Autoriza provedor semantico.")
    p_plan.set_defaults(func=cmd_plan)

    p_render = sub.add_parser("render", help="Renderiza o master (L1..L6 + QA).")
    p_render.add_argument("--whisper-model-path", default=None, help="Snapshot local do faster-whisper.")
    p_render.add_argument("--no-offline", action="store_true", help="Desativa modo offline.")
    p_render.set_defaults(func=cmd_render)

    p_approve = sub.add_parser("approve", help="Aprova o master 16:9.")
    p_approve.add_argument("--by", required=True, help="Nome de quem aprova.")
    p_approve.set_defaults(func=cmd_approve)

    p_shorts = sub.add_parser("shorts", help="Derivados verticais 9:16.")
    shorts_sub = p_shorts.add_subparsers(dest="acao", required=True)

    p_shorts_render = shorts_sub.add_parser("render", help="Renderiza derivados 9:16.")
    p_shorts_render.add_argument("--clips-json", default=None, help="Arquivo JSON com lista de clips.")
    p_shorts_render.add_argument(
        "--clip", action="append", default=[],
        help="Clip no formato id:start:end (repetivel).",
    )
    p_shorts_render.set_defaults(func=cmd_shorts_render)

    p_shorts_approve = shorts_sub.add_parser("approve", help="Aprova um derivado 9:16.")
    p_shorts_approve.add_argument("--short-id", required=True, help="ID do derivado.")
    p_shorts_approve.add_argument("--by", required=True, help="Nome de quem aprova.")
    p_shorts_approve.set_defaults(func=cmd_shorts_approve)

    p_prep = sub.add_parser("prepare-brief", help="Ingestao + transcricao + BRIEFING.md + EDL (Portao 1).")
    p_prep.add_argument("--source", default=None, help="Video de origem (obrigatorio se nao ingerido).")
    p_prep.add_argument("--whisper-model-path", default=None, help="Snapshot local do faster-whisper.")
    p_prep.add_argument("--offline", action="store_true", help="Forca modo offline (default).")
    p_prep.add_argument("--no-offline", action="store_true", help="Desativa modo offline.")
    p_prep.add_argument("--injected-json", default=None, help="Transcricao injetada (testes).")
    p_prep.add_argument("--corrections-json", default=None, help="Arquivo JSON de correcoes.")
    p_prep.add_argument("--reviewed-by", default="proprietario", help="Responsavel pela revisao.")
    p_prep.add_argument("--user-brief-json", default=None, help="Caminho para user_brief.json.")
    p_prep.add_argument("--authorize", action="store_true", help="Autoriza provedor semantico.")
    p_prep.set_defaults(func=cmd_prepare_brief)

    p_rm = sub.add_parser("render-master", help="Executa QA (lint) e renderiza o Master aprovado.")
    p_rm.add_argument("--by", default=None, help="Aprova automaticamente o Master apos QA com este nome.")
    p_rm.add_argument("--no-strict", action="store_true", help="Nao levanta erro se QA falhar.")
    p_rm.set_defaults(func=cmd_render_master)

    p_ss = sub.add_parser("suggest-shorts", help="Sugere cortes estilo OpusClip com notas (Portao 2).")
    p_ss.add_argument("--count", type=int, default=None, help="Quantidade desejada de cortes.")
    p_ss.add_argument("--modo", choices=["completo", "so_cortes"], default=None, help="Modo de corte.")
    p_ss.set_defaults(func=cmd_suggest_shorts)

    p_rs = sub.add_parser("render-shorts", help="Renderiza apenas os cortes aprovados no Portao 2.")
    p_rs.add_argument("--short-ids", default=None, help="IDs separados por virgula (ou 'all').")
    p_rs.add_argument("--short-id", action="append", default=[], help="ID aprovado (repetivel).")
    p_rs.add_argument("--clips-json", default=None, help="Lista JSON explicita de clips.")
    p_rs.add_argument("--clip", action="append", default=[], help="Clip id:start:end (repetivel).")
    p_rs.add_argument("--by", default=None, help="Aprova o Master se ainda nao estiver aprovado.")
    p_rs.set_defaults(func=cmd_render_shorts)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    json_mode = bool(getattr(args, "json", False))

    try:
        func = args.func
    except AttributeError:
        parser.print_help()
        return 1

    try:
        func(args, json_mode)
    except CliError as exc:
        _fail(str(exc), json_mode)
        return 1
    except (MasterApprovalError, PipelineError, ShortsRenderError) as exc:
        _fail(str(exc), json_mode)
        return 1
    except Exception as exc:  # pragma: no cover - defensivo
        _fail(f"falha inesperada: {type(exc).__name__}: {exc}", json_mode)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
