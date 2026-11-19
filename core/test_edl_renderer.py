#!/usr/bin/env python3
"""core/test_edl_renderer.py"""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.component_catalog import resolve_component_status  # noqa: E402
from core.master_lint import lint  # noqa: E402
from core.ingest import ingest_media  # noqa: E402
from core.edl_builder import build_edl_from_alignment  # noqa: E402
from core.edl_renderer import render_edl_to_video, verify_rendered_video, EdlRenderError  # noqa: E402
from core.workspace import init_workspace, load_brand_profile  # noqa: E402


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def test_catalog_states():
    assert resolve_component_status("titulo_heroi")["status"] == "implemented"
    assert resolve_component_status("titulo_heroi")["executable"] is True
    assert resolve_component_status("micro_zoom_bate")["status"] == "implemented"
    assert resolve_component_status("micro_zoom_bate")["executable"] is True
    assert resolve_component_status("lower_third")["status"] == "implemented"
    assert resolve_component_status("lower_third")["executable"] is True
    assert resolve_component_status("broll_industrial")["status"] == "implemented"
    assert resolve_component_status("broll_industrial")["executable"] is True
    assert resolve_component_status("sound_design_sync")["status"] == "implemented"
    assert resolve_component_status("sound_design_sync")["executable"] is True
    assert resolve_component_status("hyperframes_cli")["status"] == "implemented"
    assert resolve_component_status("hyperframes_cli")["executable"] is True
    assert resolve_component_status("card_flutuante")["status"] == "implemented"
    assert resolve_component_status("pip_stage")["executable"] is True
    assert resolve_component_status("split_stage")["executable"] is True
    assert resolve_component_status("transicao_marca")["executable"] is True
    assert resolve_component_status({"layer": "L4_lower_third"})["component_id"] == "lower_third"
    print("  [PASS] test_catalog_states")


def test_lint_block():
    plan = {"layers": {"layer_1_camera_micro_zooms": {"keyframes": []}}}
    edl = {"timeline_events": [], "summary": {"final_duration_seconds": 1.0}}
    bp = {"brand_id": "b", "display_name": "B", "presenter": {"name": "N", "credential": "C", "face_anchor_1080p": [980, 420]},
          "visual": {"palette": {}, "font_family": "Inter", "safe_zones": {}},
          "render_defaults": {"master_16x9": {"width": 1920, "height": 1080, "fps": 30}},
          "audio": {"clean_profile": "vehicular_clean", "hpf_hz": 80, "silence_guard_ms": [180, 220],
                    "jumpcut_gap_threshold_ms": 450, "jumpcut_target_gap_ms": [200, 250]},
          "asr": {"regional_profile": "pt", "lexicon": [], "phonetic_rules_file": "r.json"},
          "assets": {"sfx_map": {}}}
    rep = lint(plan, edl, None)
    assert rep.get("ok") is False or rep.get("failures")
    try:
        render_edl_to_video(edl, plan, "dummy.mp4", bp, "out.mp4")
        assert False
    except EdlRenderError:
        pass
    print("  [PASS] test_lint_block")


def _run_vertical_proof(workspace_root: Path):
    workspace_root = workspace_root.resolve()
    src_temp = workspace_root / "src_vertical_proof.mp4"
    # synthetic media
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc2=size=1920x1080:rate=30",
        "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000",
        "-t", "12", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
        "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-shortest", str(src_temp),
    ], check=True, capture_output=True)
    before = _sha256(src_temp)

    # workspace + brand sintetica
    init_workspace(workspace_root)
    marca_id = "marca-sintetica"
    brand_dir = workspace_root / "projetos" / marca_id / "branding"
    brand_dir.mkdir(parents=True, exist_ok=True)
    (brand_dir / "config.json").write_text(json.dumps({
        "rosto": [980, 420],
        "marca": {"destaque": "#004aad", "secundaria": "#8e7de5", "ciano": "#2f97d4", "fonte": "Inter"},
        "preferencias_edicao": {"canal": "Marca Sintetica", "apresentador": "Tester", "credencial_oficial": "Cred",
                                "render_defaults": {"master_16x9": {"width": 1920, "height": 1080, "fps": 30}},
                                "audio": {"clean_profile": "vehicular_clean", "hpf_hz": 80, "silence_guard_ms": [180, 220],
                                          "jumpcut_gap_threshold_ms": 450, "jumpcut_target_gap_ms": [200, 250]},
                                "safe_zones": {}},
        "visual": {"safe_zones": {"master_16x9": {"card_left": [100, 320]}}},
    }), encoding="utf-8")
    episodio_id = "ep-vertical-proof"
    rc = ingest_media(str(src_temp), marca_id, episodio_id, workspace_root)
    assert rc == 0

    ep_dir = workspace_root / "projetos" / marca_id / "episodios" / episodio_id
    ws_dir = ep_dir / "workspace"
    ws_dir.mkdir(parents=True, exist_ok=True)
    transcript = {"segments": [{"start": 0.0, "end": 6.0, "text": "ola mundo foo bar baz qux", "words": [
        {"word": "ola", "start": 0.0, "end": 0.5, "probability": 0.9},
        {"word": "mundo", "start": 0.6, "end": 1.0, "probability": 0.9},
    ]}, {"start": 8.0, "end": 12.0, "text": "teste final extra longo", "words": [
        {"word": "teste", "start": 8.0, "end": 8.5, "probability": 0.9},
    ]}]}
    (ws_dir / "transcript.json").write_text(json.dumps(transcript), encoding="utf-8")
    alignment = {"editorial_units": [
        {"unit_id": 1, "text": "ola mundo foo bar baz qux", "raw_start": 0.0, "raw_end": 5.0, "words": transcript["segments"][0]["words"]},
        {"unit_id": 2, "text": "teste final extra longo", "raw_start": 8.0, "raw_end": 11.0, "words": transcript["segments"][1]["words"]},
    ]}
    (ws_dir / "alignment.json").write_text(json.dumps(alignment), encoding="utf-8")

    from PIL import Image
    import wave, struct
    (ws_dir / "broll.png").parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (64, 64), (255, 0, 0)).save(ws_dir / "broll.png")
    broll_before = _sha256(ws_dir / "broll.png")
    # synthetic wavs (1000Hz sine at high amplitude so L6 window has measurable RMS delta)
    import math
    for name in ("s1.wav", "s2.wav"):
        wf = wave.open(str(ws_dir / name), "wb")
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(48000)
        frames = b"".join(
            struct.pack("<h", int(32767 * 0.9 * math.sin(2.0 * math.pi * 1000.0 * i / 48000.0)))
            for i in range(9600)
        )
        wf.writeframes(frames)
        wf.close()
    s1_before = _sha256(ws_dir / "s1.wav")
    s2_before = _sha256(ws_dir / "s2.wav")

    bp = load_brand_profile(workspace_root, marca_id)
    edl, editorial_plan = build_edl_from_alignment(
        alignment_path=ws_dir / "alignment.json",
        workspace_root=workspace_root,
        marca_id=marca_id,
        episodio_id=episodio_id,
        brand_profile=bp,
    )
    src_ref = edl["timeline_events"][0].get("source_ref") if edl.get("timeline_events") else None
    editorial_plan.setdefault("layers", {})
    for layer_name in ("L4_lower_third", "L2_titulo_heroi_t10", "L3_micro_zoom_bate"):
        editorial_plan["layers"].setdefault(layer_name, [])
    editorial_plan["layers"]["L4_lower_third"].append(
        {"id": "lt1", "component_id": "lower_third", "out_in": 0.0, "out_out": 2.5, "source_ref": src_ref}
    )
    editorial_plan["layers"].setdefault("L5_broll_industrial", [])
    editorial_plan["layers"]["L5_broll_industrial"].append(
        {"id": "br1", "component_id": "broll_industrial", "media_ref": "broll.png", "out_in": 4.5, "out_out": 7.0, "source_ref": src_ref}
    )
    editorial_plan["layers"].setdefault("L6_sound_design_sync", [])
    editorial_plan["layers"]["L6_sound_design_sync"].append(
        {"id": "sd1", "component_id": "sound_design_sync", "sound_ref": "s1.wav", "out_in": 0.5, "out_out": 0.7, "source_ref": src_ref, "volume": 0.5}
    )
    editorial_plan["layers"]["L6_sound_design_sync"].append(
        {"id": "sd2", "component_id": "sound_design_sync", "sound_ref": "s2.wav", "out_in": 2.5, "out_out": 2.7, "source_ref": src_ref, "volume": 0.5}
    )
    if not any(e.get("component_id") == "titulo_heroi" for e in editorial_plan["layers"]["L2_titulo_heroi_t10"]):
        editorial_plan["layers"]["L2_titulo_heroi_t10"].append(
            {"id": "t1", "component_id": "titulo_heroi", "text": "Titulo", "out_in": 2.5, "out_out": 3.5, "source_ref": src_ref}
        )
    if not any(e.get("component_id") == "micro_zoom_bate" for e in editorial_plan["layers"]["L3_micro_zoom_bate"]):
        editorial_plan["layers"]["L3_micro_zoom_bate"].append(
            {"id": "z1", "component_id": "micro_zoom_bate", "out_in": 3.6, "out_out": 4.0, "source_ref": src_ref}
        )

    rep = lint(editorial_plan, edl, None)
    assert rep.get("ok") is True, rep.get("failures")

    out_mp4 = ws_dir / "render_prova_test.mp4"
    report = render_edl_to_video(edl, editorial_plan, src_temp, bp, out_mp4, work_dir=ws_dir)
    assert Path(report["output_path"]).exists()
    v = report["verification"]
    assert v["ok"], v["problems"]
    executed_ids = [e["component_id"] for e in report["executed_events"]]
    assert "titulo_heroi" in executed_ids
    assert "micro_zoom_bate" in executed_ids
    assert "lower_third" in executed_ids
    assert "broll_industrial" in executed_ids
    isolated_ids = [e["component_id"] for e in report["isolated_events"]]
    assert "sound_design_sync" in executed_ids

    # verificacao visual de pixels: frame dentro do L4 vs fora
    frame_in = ws_dir / "frame_in.png"
    frame_out = ws_dir / "frame_out.png"
    subprocess.run(["ffmpeg", "-y", "-ss", "1.5", "-i", str(out_mp4), "-frames:v", "1", str(frame_in)], check=True, capture_output=True)
    subprocess.run(["ffmpeg", "-y", "-ss", "3.5", "-i", str(out_mp4), "-frames:v", "1", str(frame_out)], check=True, capture_output=True)
    from PIL import Image
    with Image.open(frame_in) as im_in, Image.open(frame_out) as im_out:
        px_in = list(im_in.get_flattened_data()) if hasattr(im_in, "get_flattened_data") else list(im_in.getdata())
        px_out = list(im_out.get_flattened_data()) if hasattr(im_out, "get_flattened_data") else list(im_out.getdata())
    diff = sum(abs(a[0]-b[0])+abs(a[1]-b[1])+abs(a[2]-b[2]) for a,b in zip(px_in,px_out))
    assert diff > 0, "Nenhuma diferenca de pixels entre frame dentro e fora do L4"

    # verificacao visual L5: frame dentro da janela vs fora
    frame_l5_in = ws_dir / "frame_l5_in.png"
    frame_l5_out = ws_dir / "frame_l5_out.png"
    subprocess.run(["ffmpeg", "-y", "-ss", "5.75", "-i", str(out_mp4), "-frames:v", "1", str(frame_l5_in)], check=True, capture_output=True)
    subprocess.run(["ffmpeg", "-y", "-ss", "7.5", "-i", str(out_mp4), "-frames:v", "1", str(frame_l5_out)], check=True, capture_output=True)
    with Image.open(frame_l5_in) as im_in, Image.open(frame_l5_out) as im_out:
        px_in = list(im_in.get_flattened_data()) if hasattr(im_in, "get_flattened_data") else list(im_in.getdata())
        px_out = list(im_out.get_flattened_data()) if hasattr(im_out, "get_flattened_data") else list(im_out.getdata())
    diff_l5 = sum(abs(a[0]-b[0])+abs(a[1]-b[1])+abs(a[2]-b[2]) for a,b in zip(px_in,px_out))
    assert diff_l5 > 0

    # containment assertions
    assert src_temp.resolve().relative_to(workspace_root.resolve())
    assert ep_dir.resolve().relative_to(workspace_root.resolve())
    assert Path(report["output_path"]).resolve().relative_to(workspace_root.resolve())

    # astats inside vs outside L6 window
    import re
    r_in = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-ss", "0.5", "-t", "0.2", "-i", str(out_mp4),
                           "-af", "astats=metadata=1:reset=1", "-f", "null", "-"], check=True, capture_output=True, text=True)
    r_out = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-ss", "3.0", "-t", "0.2", "-i", str(out_mp4),
                            "-af", "astats=metadata=1:reset=1", "-f", "null", "-"], check=True, capture_output=True, text=True)
    m_in = re.findall(r"RMS level dB:\s*([-\d.]+)", r_in.stderr)
    m_out = re.findall(r"RMS level dB:\s*([-\d.]+)", r_out.stderr)
    assert m_in and m_out, f"RMS level dB ausente no astats: in={m_in}, out={m_out}"
    rms_in = float(m_in[-1])
    rms_out = float(m_out[-1])
    assert abs(rms_in - rms_out) > 0.1, f"Sem diferenca mensuravel de RMS entre janela L6 ({rms_in}) e fora ({rms_out})"
    # ebur128
    r_ebu = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(out_mp4),
                            "-af", "ebur128=peak=true", "-f", "null", "-"], capture_output=True, text=True)
    assert r_ebu.returncode == 0
    m_i = re.findall(r"\bI:\s+(-?[\d.]+)\s+LUFS", r_ebu.stderr)
    m_p = re.findall(r"\bPeak:\s+(-?[\d.]+)\s+dBFS", r_ebu.stderr)
    if m_i:
        i_lufs = float(m_i[-1])
        assert -18.0 <= i_lufs <= -10.0
    if m_p:
        tp = float(m_p[-1])
        assert tp <= -0.9

    after = _sha256(src_temp)
    broll_after = _sha256(ws_dir / "broll.png")
    assert before == after
    assert broll_before == broll_after
    assert s1_before == _sha256(ws_dir / "s1.wav")
    assert s2_before == _sha256(ws_dir / "s2.wav")
    print("  [PASS] test_vertical_proof")


def test_vertical_proof(tmp_path=None):
    if tmp_path is None:
        with tempfile.TemporaryDirectory() as td:
            _run_vertical_proof(Path(td))
    else:
        _run_vertical_proof(Path(tmp_path))



def test_broll_unresolved_isolated(tmp_path):
    workspace_root = tmp_path
    src_temp = workspace_root / "src.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc2=size=1920x1080:rate=30",
        "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000",
        "-t", "4", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
        "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-shortest", str(src_temp),
    ], check=True, capture_output=True)
    init_workspace(workspace_root)
    marca_id = "marca-sintetica"
    brand_dir = workspace_root / "projetos" / marca_id / "branding"
    brand_dir.mkdir(parents=True, exist_ok=True)
    (brand_dir / "config.json").write_text(json.dumps({
        "rosto": [980, 420],
        "marca": {"destaque": "#004aad", "secundaria": "#8e7de5", "ciano": "#2f97d4", "fonte": "Inter"},
        "preferencias_edicao": {"canal": "Marca Sintetica", "apresentador": "Tester", "credencial_oficial": "Cred",
                                "render_defaults": {"master_16x9": {"width": 1920, "height": 1080, "fps": 30}},
                                "audio": {"clean_profile": "vehicular_clean", "hpf_hz": 80, "silence_guard_ms": [180, 220],
                                          "jumpcut_gap_threshold_ms": 450, "jumpcut_target_gap_ms": [200, 250]}},
        "visual": {"safe_zones": {"master_16x9": {"card_left": [100, 320]}}},
    }), encoding="utf-8")
    episodio_id = "ep-broll-test"
    rc = ingest_media(str(src_temp), marca_id, episodio_id, workspace_root)
    assert rc == 0
    ep_dir = workspace_root / "projetos" / marca_id / "episodios" / episodio_id
    ws_dir = ep_dir / "workspace"
    ws_dir.mkdir(parents=True, exist_ok=True)
    transcript = {"segments": [{"start": 0.0, "end": 1.0, "text": "ola", "words": [
        {"word": "ola", "start": 0.0, "end": 0.5, "probability": 0.9},
    ]}]}
    (ws_dir / "transcript.json").write_text(json.dumps(transcript), encoding="utf-8")
    alignment = {"editorial_units": [
        {"unit_id": 1, "text": "ola", "raw_start": 0.0, "raw_end": 0.5, "words": transcript["segments"][0]["words"]},
    ]}
    (ws_dir / "alignment.json").write_text(json.dumps(alignment), encoding="utf-8")
    bp = load_brand_profile(workspace_root, marca_id)
    edl, editorial_plan = build_edl_from_alignment(
        alignment_path=ws_dir / "alignment.json",
        workspace_root=workspace_root,
        marca_id=marca_id,
        episodio_id=episodio_id,
        brand_profile=bp,
    )
    src_ref = edl["timeline_events"][0].get("source_ref") if edl.get("timeline_events") else None
    editorial_plan.setdefault("layers", {})
    for layer_name in ("L4_lower_third", "L2_titulo_heroi_t10", "L3_micro_zoom_bate", "L5_broll_industrial"):
        editorial_plan["layers"].setdefault(layer_name, [])
    editorial_plan["layers"]["L5_broll_industrial"].append(
        {"id": "br_bad1", "component_id": "broll_industrial", "media_ref": "../fora.png", "out_in": 0.0, "out_out": 0.25, "source_ref": src_ref}
    )
    editorial_plan["layers"]["L5_broll_industrial"].append(
        {"id": "br_bad2", "component_id": "broll_industrial", "media_ref": "nao_existe.png", "out_in": 0.25, "out_out": 0.5, "source_ref": src_ref}
    )
    rep = lint(editorial_plan, edl, None)
    # lint may fail due to collision/invalid media? render handles isolation
    out_mp4 = ws_dir / "render_test.mp4"
    report = render_edl_to_video(edl, editorial_plan, src_temp, bp, out_mp4, work_dir=ws_dir, strict=False)
    isolated_ids = [e["component_id"] for e in report["isolated_events"]]
    assert isolated_ids.count("broll_industrial") >= 2
    print("  [PASS] test_broll_unresolved_isolated")


def test_lint_l5_collisions_and_repeat():
    plan = {
        "layers": {
            "L2_titulo_heroi_t10": [{"element_id": "t1", "out_in": 1.0, "out_out": 2.0}],
            "L3_micro_zoom_bate": [{"element_id": "z1", "out_in": 2.5, "out_out": 3.0}],
            "L4_lower_third": [{"element_id": "lt1", "out_in": 3.5, "out_out": 4.0}],
            "L5_broll_industrial": [
                {"element_id": "b1", "media_ref": "a.png", "out_in": 1.2, "out_out": 1.8},
                {"element_id": "b2", "media_ref": "a.png", "out_in": 1.2, "out_out": 1.8},
            ],
        }
    }
    # collision L5 vs L2
    plan2 = json.loads(json.dumps(plan))
    plan2["layers"]["L5_broll_industrial"][0]["out_in"] = 1.2
    plan2["layers"]["L5_broll_industrial"][0]["out_out"] = 1.8
    plan2["layers"]["L2_titulo_heroi_t10"][0]["out_in"] = 1.3
    plan2["layers"]["L2_titulo_heroi_t10"][0]["out_out"] = 1.7
    rep = lint(plan2, {"timeline_events": [], "summary": {"final_duration_seconds": 10.0}}, None)
    assert rep.get("ok") is False
    # consecutive repeat
    plan3 = json.loads(json.dumps(plan))
    rep3 = lint(plan3, {"timeline_events": [], "summary": {"final_duration_seconds": 10.0}}, None)
    assert rep3.get("ok") is False
    print("  [PASS] test_lint_l5_collisions_and_repeat")

def _run_l6_unresolved_and_dedup_isolated(workspace_root: Path):
    import wave, struct, math
    workspace_root = workspace_root.resolve()
    src_temp = workspace_root / "src_l6.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc2=size=1920x1080:rate=30",
        "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000",
        "-t", "4", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
        "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-shortest", str(src_temp),
    ], check=True, capture_output=True)
    init_workspace(workspace_root)
    marca_id = "marca-sintetica"
    brand_dir = workspace_root / "projetos" / marca_id / "branding"
    brand_dir.mkdir(parents=True, exist_ok=True)
    (brand_dir / "config.json").write_text(json.dumps({
        "rosto": [980, 420],
        "marca": {"destaque": "#004aad", "secundaria": "#8e7de5", "ciano": "#2f97d4", "fonte": "Inter"},
        "preferencias_edicao": {"canal": "Marca Sintetica", "apresentador": "Tester", "credencial_oficial": "Cred",
                                "render_defaults": {"master_16x9": {"width": 1920, "height": 1080, "fps": 30}},
                                "audio": {"clean_profile": "vehicular_clean", "hpf_hz": 80, "silence_guard_ms": [180, 220],
                                          "jumpcut_gap_threshold_ms": 450, "jumpcut_target_gap_ms": [200, 250]}},
        "visual": {"safe_zones": {"master_16x9": {"card_left": [100, 320]}}},
    }), encoding="utf-8")
    episodio_id = "ep-l6-iso"
    rc = ingest_media(str(src_temp), marca_id, episodio_id, workspace_root)
    assert rc == 0
    ep_dir = workspace_root / "projetos" / marca_id / "episodios" / episodio_id
    ws_dir = ep_dir / "workspace"
    ws_dir.mkdir(parents=True, exist_ok=True)
    transcript = {"segments": [{"start": 0.0, "end": 3.5, "text": "ola mundo teste", "words": [
        {"word": "ola", "start": 0.0, "end": 0.5, "probability": 0.9},
        {"word": "mundo", "start": 0.6, "end": 1.0, "probability": 0.9},
    ]}]}
    (ws_dir / "transcript.json").write_text(json.dumps(transcript), encoding="utf-8")
    alignment = {"editorial_units": [
        {"unit_id": 1, "text": "ola mundo teste", "raw_start": 0.0, "raw_end": 3.5, "words": transcript["segments"][0]["words"]},
    ]}
    (ws_dir / "alignment.json").write_text(json.dumps(alignment), encoding="utf-8")

    wf = wave.open(str(ws_dir / "good.wav"), "wb")
    wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(48000)
    wf.writeframes(b"".join(
        struct.pack("<h", int(32767 * 0.8 * math.sin(2.0 * math.pi * 1000.0 * i / 48000.0)))
        for i in range(9600)
    ))
    wf.close()
    (ws_dir / "corrupt.wav").write_bytes(b"not-a-valid-wav-file")

    bp = load_brand_profile(workspace_root, marca_id)
    edl, editorial_plan = build_edl_from_alignment(
        alignment_path=ws_dir / "alignment.json",
        workspace_root=workspace_root,
        marca_id=marca_id,
        episodio_id=episodio_id,
        brand_profile=bp,
    )
    src_ref = edl["timeline_events"][0].get("source_ref") if edl.get("timeline_events") else None
    editorial_plan.setdefault("layers", {})
    editorial_plan["layers"]["L6_sound_design_sync"] = [
        {"id": "sd_missing", "component_id": "sound_design_sync", "sound_ref": "nao_existe.wav", "out_in": 0.1, "out_out": 0.35, "source_ref": src_ref, "volume": 0.5, "justificativa": "teste"},
        {"id": "sd_corrupt", "component_id": "sound_design_sync", "sound_ref": "corrupt.wav", "out_in": 1.2, "out_out": 1.45, "source_ref": src_ref, "volume": 0.5, "justificativa": "teste"},
        {"id": "sd_traversal", "component_id": "sound_design_sync", "sound_ref": "../fora.wav", "out_in": 1.8, "out_out": 2.05, "source_ref": src_ref, "volume": 0.5, "justificativa": "teste"},
        {"id": "sd_rhythm_dup", "component_id": "sound_design_sync", "sound_ref": "good.wav", "out_in": 0.5, "out_out": 0.75, "origin": "rhythm_engine", "dedup_key": "k_dup", "source_ref": src_ref, "volume": 0.5, "justificativa": "teste"},
        {"id": "sd_semantic_win", "component_id": "sound_design_sync", "sound_ref": "good.wav", "out_in": 0.5, "out_out": 0.75, "origin": "semantic_plan", "dedup_key": "k_dup", "source_ref": src_ref, "volume": 0.5, "justificativa": "teste"},
        {"id": "sd_cooldown", "component_id": "sound_design_sync", "sound_ref": "good.wav", "out_in": 0.8, "out_out": 1.05, "origin": "rhythm_engine", "dedup_key": "k_cool", "source_ref": src_ref, "volume": 0.5, "justificativa": "teste"},
    ]

    from unittest.mock import patch
    out_mp4 = ws_dir / "render_l6_iso.mp4"
    with patch("core.edl_renderer.lint_plan", return_value={"ok": True, "failures": [], "warnings": []}):
        report = render_edl_to_video(edl, editorial_plan, src_temp, bp, out_mp4, work_dir=ws_dir, strict=False)
    assert Path(report["output_path"]).exists()
    executed_l6 = [e["element_id"] for e in report["executed_events"] if e["component_id"] == "sound_design_sync"]
    isolated_l6 = {e["element_id"] for e in report["isolated_events"] if e["component_id"] == "sound_design_sync"}
    assert executed_l6 == ["sd_semantic_win"], f"Esperado apenas sd_semantic_win executado, obtido {executed_l6}"
    expected_isolated = {"sd_missing", "sd_corrupt", "sd_traversal", "sd_rhythm_dup", "sd_cooldown"}
    assert expected_isolated.issubset(isolated_l6), f"Faltando isolados: {expected_isolated - isolated_l6}"
    print("  [PASS] test_l6_unresolved_and_dedup_isolated")


def test_l6_unresolved_and_dedup_isolated(tmp_path=None):
    if tmp_path is None:
        with tempfile.TemporaryDirectory() as td:
            _run_l6_unresolved_and_dedup_isolated(Path(td))
    else:
        _run_l6_unresolved_and_dedup_isolated(Path(tmp_path))


def test_lint_l6_errors_and_warnings():
    edl = {"timeline_events": [], "summary": {"final_duration_seconds": 10.0}}
    base_layers = {
        "L2_titulo_heroi_t10": [{"element_id": "t1", "out_in": 1.0, "out_out": 2.0}],
        "L3_micro_zoom_bate": [{"element_id": "z1", "out_in": 2.5, "out_out": 3.0}],
        "L4_lower_third": [{"element_id": "lt1", "out_in": 3.5, "out_out": 4.0}],
        "L5_broll_industrial": [{"element_id": "b1", "media_ref": "a.png", "out_in": 5.0, "out_out": 6.0}],
    }
    # 1) Warning when L6 lacks justificativa
    plan_warn = {"layers": {**base_layers, "L6_sound_design_sync": [
        {"id": "sd_w", "sound_ref": "s.wav", "out_in": 0.5, "out_out": 0.8, "volume": 0.5},
    ]}}
    rep_w = lint(plan_warn, edl, None)
    assert any("justificativa" in w.lower() for w in rep_w.get("warnings", [])), rep_w

    # 2) out_in < 0
    plan_neg = {"layers": {**base_layers, "L6_sound_design_sync": [
        {"id": "sd_neg", "sound_ref": "s.wav", "out_in": -0.2, "out_out": 0.5, "volume": 0.5, "justificativa": "ok"},
    ]}}
    rep_neg = lint(plan_neg, edl, None)
    assert rep_neg.get("ok") is False
    assert any("out_in < 0" in f for f in rep_neg.get("failures", [])), rep_neg

    # 3) out_out > final_duration
    plan_over = {"layers": {**base_layers, "L6_sound_design_sync": [
        {"id": "sd_over", "sound_ref": "s.wav", "out_in": 9.5, "out_out": 10.5, "volume": 0.5, "justificativa": "ok"},
    ]}}
    rep_over = lint(plan_over, edl, None)
    assert rep_over.get("ok") is False
    assert any("out_out > final_duration" in f for f in rep_over.get("failures", [])), rep_over

    # 4) volume > 1.0
    plan_vol = {"layers": {**base_layers, "L6_sound_design_sync": [
        {"id": "sd_vol", "sound_ref": "s.wav", "out_in": 0.5, "out_out": 0.8, "volume": 1.5, "justificativa": "ok"},
    ]}}
    rep_vol = lint(plan_vol, edl, None)
    assert rep_vol.get("ok") is False
    assert any("volume" in f for f in rep_vol.get("failures", [])), rep_vol

    # 5) duplicate dedup_key and duplicate timestamp
    plan_dup = {"layers": {**base_layers, "L6_sound_design_sync": [
        {"id": "sd_d1", "sound_ref": "s.wav", "out_in": 0.5, "out_out": 0.8, "volume": 0.5, "dedup_key": "k1", "justificativa": "ok"},
        {"id": "sd_d2", "sound_ref": "s.wav", "out_in": 0.5, "out_out": 0.8, "volume": 0.5, "dedup_key": "k1", "justificativa": "ok"},
    ]}}
    rep_dup = lint(plan_dup, edl, None)
    assert rep_dup.get("ok") is False
    assert any("dedup_key duplicado" in f for f in rep_dup.get("failures", [])), rep_dup
    assert any("timestamp duplicado" in f for f in rep_dup.get("failures", [])), rep_dup
    print("  [PASS] test_lint_l6_errors_and_warnings")


def test_orientacao_dinamica_9x16_e_frames_exatos(tmp_path):
    """Preserva 9:16 nativo (1080x1920), limpa vicio/pausa e zera divergencia de frames."""
    workspace_root = tmp_path / "ws_9x16"
    src_temp = workspace_root / "src_9x16.mp4"
    src_temp.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc2=size=1080x1920:rate=30",
        "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000",
        "-t", "7", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
        "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-shortest", str(src_temp),
    ], check=True, capture_output=True)

    init_workspace(workspace_root)
    marca_id = "marca-vert"
    brand_dir = workspace_root / "projetos" / marca_id / "branding"
    brand_dir.mkdir(parents=True, exist_ok=True)
    (brand_dir / "config.json").write_text(json.dumps({
        "rosto": [540, 600],
        "marca": {"destaque": "#004aad", "fonte": "Inter"},
        "preferencias_edicao": {
            "canal": "Canal Vertical",
            "apresentador": "Tester",
            "credencial_oficial": "Cred",
            "audio": {"jumpcut_gap_threshold_ms": 450, "jumpcut_target_gap_ms": [200, 250]},
        },
        "visual": {"safe_zones": {"master_16x9": {"card_left": [100, 320]}}},
    }), encoding="utf-8")

    episodio_id = "ep-9x16"
    assert ingest_media(str(src_temp), marca_id, episodio_id, workspace_root) == 0

    fonte_dir = workspace_root / "projetos" / marca_id / "episodios" / episodio_id / "workspace" / "fonte"
    fonte_dir.mkdir(parents=True, exist_ok=True)
    words_u1 = [
        {"word": "Ola", "start": 0.0, "end": 0.8, "probability": 0.95},
        {"word": "ééé", "start": 0.85, "end": 1.15, "probability": 0.92},
        {"word": "pessoal", "start": 1.2, "end": 2.4, "probability": 0.95},
    ]
    words_u2 = [
        {"word": "vamos", "start": 3.5, "end": 4.8, "probability": 0.96},
        {"word": "comecar", "start": 4.9, "end": 6.2, "probability": 0.96},
    ]
    transcript = {"segments": [
        {"id": 0, "start": 0.0, "end": 2.4, "text": "Ola ééé pessoal", "words": words_u1},
        {"id": 1, "start": 3.5, "end": 6.2, "text": "vamos comecar", "words": words_u2},
    ]}
    (fonte_dir / "transcript.json").write_text(json.dumps(transcript), encoding="utf-8")
    alignment = {"editorial_units": [
        {"unit_id": 1, "text": "Ola ééé pessoal", "raw_start": 0.0, "raw_end": 2.4, "words": words_u1},
        {"unit_id": 2, "text": "vamos comecar", "raw_start": 3.5, "raw_end": 6.2, "words": words_u2},
    ]}
    (fonte_dir / "alignment.json").write_text(json.dumps(alignment), encoding="utf-8")

    bp = load_brand_profile(workspace_root, marca_id)
    edl, editorial_plan = build_edl_from_alignment(
        alignment_path=fonte_dir / "alignment.json",
        workspace_root=workspace_root,
        marca_id=marca_id,
        episodio_id=episodio_id,
        brand_profile=bp,
        ensure_motion_layers=True,
    )

    assert edl["target_format"]["resolution"] == [1080, 1920]
    assert edl["target_format"]["aspect_ratio"] == "9:16"
    assert any(r["operation"] == "remover_vicio_linguagem" for r in edl["removed_segments"])
    assert len(editorial_plan["layers"]["L2_titulo_heroi_t10"]) >= 1
    assert len(editorial_plan["layers"]["L3_micro_zoom_bate"]) >= 1
    assert edl.get("dynamic_captions")

    out_mp4 = workspace_root / "master_9x16.mp4"
    rep = render_edl_to_video(edl, editorial_plan, src_temp, bp, out_mp4, work_dir=workspace_root / "_w9x16")
    assert rep["verification"]["ok"], rep["verification"]["problems"]
    assert rep["verification"]["video"]["width"] == 1080
    assert rep["verification"]["video"]["height"] == 1920
    expected_d = rep["target_format"]["expected_duration_seconds"]
    assert abs(rep["verification"]["duration"] - expected_d) <= 0.05


def run_tests():
    print("=" * 60)
    print("SUITE — core/test_edl_renderer.py")
    print("=" * 60)
    failures = 0
    for t in (test_catalog_states, test_lint_block, test_broll_unresolved_isolated,
              test_lint_l5_collisions_and_repeat, test_l6_unresolved_and_dedup_isolated,
              test_lint_l6_errors_and_warnings):
        try:
            t()
        except Exception as e:
            failures += 1
            print(f"  [FALHA] {t.__name__}: {e}")
            import traceback; traceback.print_exc()
    try:
        with tempfile.TemporaryDirectory() as td:
            test_vertical_proof(Path(td))
    except Exception as e:
        failures += 1
        print(f"  [FALHA] test_vertical_proof: {e}")
        import traceback; traceback.print_exc()
    print("OK" if failures == 0 else f"{failures} FALHA(S)")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(run_tests())
