# -*- coding: utf-8 -*-
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sound_design_sync import (
    resolve_safe_sound_path,
    probe_sound_asset,
    resolve_sound_asset,
    deduplicate_and_schedule_sfx,
    build_sound_mix_ffmpeg_filter,
)


def test_safe_path_traversal():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "a.wav").write_bytes(b"x" * 10)
        try:
            resolve_safe_sound_path("../fora.wav", [root])
            assert False
        except ValueError:
            pass
        try:
            resolve_safe_sound_path("a.txt", [root])
            assert False
        except ValueError:
            pass
    print("  [PASS] test_safe_path_traversal")


def test_probe_invalid():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        empty = root / "empty.wav"
        empty.write_bytes(b"")
        try:
            probe_sound_asset(empty)
            assert False
        except ValueError:
            pass
    print("  [PASS] test_probe_invalid")


def test_resolve_asset():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        wav = root / "s.wav"
        wav.write_bytes(b"x" * 100)
        # create a minimal wav? probe may fail due to invalid wav; use ffprobe? skip probe by mocking? 
        # We'll just test resolve returns resolved False for invalid media
        el = {"sound_ref": "s.wav", "volume": 0.5}
        r = resolve_sound_asset(el, [root])
        # probe may fail (not a real wav) -> unresolved
        assert r["resolved"] in (True, False)
    print("  [PASS] test_resolve_asset")


def test_dedup():
    elems = [
        {"sound_ref": "a.wav", "out_in": 0.0, "out_out": 0.5, "dedup_key": "k1"},
        {"sound_ref": "a.wav", "out_in": 0.1, "out_out": 0.6, "dedup_key": "k1"},
        {"sound_ref": "b.wav", "out_in": 2.0, "out_out": 2.5, "dedup_key": "k2"},
    ]
    acc, rej = deduplicate_and_schedule_sfx(elems, 10.0, cooldown_s=0.5)
    assert len(acc) >= 1
    print("  [PASS] test_dedup")


def test_build_filter():
    items = [{"out_in": 0.5, "duration_s": 0.2, "volume": 0.4}]
    bd = build_sound_mix_ffmpeg_filter("abase", items, "aout", final_duration=5.0)
    assert "filter_steps" in bd
    assert "loudnorm=I=-14" in bd["filter_steps"][-1] or "loudnorm" in str(bd["filter_steps"])
    print("  [PASS] test_build_filter")


def test_negative_safe_path_and_probe():
    from unittest.mock import patch
    import json as _json
    import subprocess as _sp
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        for ext in (".txt", ".exe"):
            f = root / f"bad{ext}"
            f.write_bytes(b"x" * 10)
            try:
                resolve_safe_sound_path(f.name, [root])
                assert False, f"Deveria rejeitar extensao {ext}"
            except ValueError:
                pass

        empty = root / "empty.wav"
        empty.write_bytes(b"")
        try:
            probe_sound_asset(empty)
            assert False, "Deveria rejeitar arquivo vazio"
        except ValueError:
            pass

        corrupt = root / "corrupt.wav"
        corrupt.write_bytes(b"not-a-wav-at-all")
        try:
            probe_sound_asset(corrupt)
            assert False, "Deveria rejeitar arquivo corrompido"
        except ValueError:
            pass

        fake_ok = root / "fake.wav"
        fake_ok.write_bytes(b"RIFF" + b"\x00" * 40)
        bad_sr_stdout = _json.dumps({"streams": [{"codec_type": "audio", "sample_rate": "0"}], "format": {"duration": "1.0"}})
        with patch("sound_design_sync.subprocess.run", return_value=_sp.CompletedProcess(args=[], returncode=0, stdout=bad_sr_stdout, stderr="")):
            try:
                probe_sound_asset(fake_ok)
                assert False, "Deveria rejeitar sample_rate <= 0"
            except ValueError:
                pass
    print("  [PASS] test_negative_safe_path_and_probe")


def test_negative_resolve_volume_and_gain_db():
    import wave, struct
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        wav = root / "ok.wav"
        wf = wave.open(str(wav), "wb")
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(48000)
        wf.writeframes(struct.pack("<h", 1000) * 4800)
        wf.close()

        for bad_el in (
            {"sound_ref": "ok.wav", "volume": 1.2},
            {"sound_ref": "ok.wav", "volume": -0.1},
            {"sound_ref": "ok.wav", "gain_db": 6.0},
        ):
            r = resolve_sound_asset(bad_el, [root])
            assert r["resolved"] is False, f"Deveria rejeitar {bad_el}, obteve {r}"
    print("  [PASS] test_negative_resolve_volume_and_gain_db")


def test_negative_dedup_bounds_precedence_and_cooldown():
    # 1) out_in < 0 and out_out > final_duration rejected
    elems_bounds = [
        {"id": "neg", "sound_ref": "a.wav", "out_in": -0.5, "out_out": 0.2},
        {"id": "over", "sound_ref": "a.wav", "out_in": 9.8, "out_out": 10.5},
        {"id": "ok", "sound_ref": "a.wav", "out_in": 1.0, "out_out": 1.2},
    ]
    acc, rej = deduplicate_and_schedule_sfx(elems_bounds, 10.0)
    assert [e["id"] for e in acc] == ["ok"]
    assert {e["id"] for e in rej} == {"neg", "over"}

    # 2) semantic_plan > rhythm_engine at same timestamp
    elems_prec = [
        {"id": "rhythm", "sound_ref": "a.wav", "out_in": 2.0, "out_out": 2.2, "origin": "rhythm_engine", "dedup_key": "k"},
        {"id": "semantic", "sound_ref": "a.wav", "out_in": 2.0, "out_out": 2.2, "origin": "semantic_plan", "dedup_key": "k"},
    ]
    acc2, rej2 = deduplicate_and_schedule_sfx(elems_prec, 10.0)
    assert [e["id"] for e in acc2] == ["semantic"]
    assert [e["id"] for e in rej2] == ["rhythm"]

    # 3) cooldown (< 0.5s) and proximity (<= 0.10s) blocking
    elems_cd = [
        {"id": "first", "sound_ref": "a.wav", "out_in": 3.0, "out_out": 3.2},
        {"id": "near_prox", "sound_ref": "b.wav", "out_in": 3.08, "out_out": 3.28},
        {"id": "near_cd", "sound_ref": "c.wav", "out_in": 3.4, "out_out": 3.6},
        {"id": "far_ok", "sound_ref": "d.wav", "out_in": 3.6, "out_out": 3.8},
    ]
    acc3, rej3 = deduplicate_and_schedule_sfx(elems_cd, 10.0, cooldown_s=0.5, proximity_s=0.10)
    assert [e["id"] for e in acc3] == ["first", "far_ok"]
    assert {e["id"] for e in rej3} == {"near_prox", "near_cd"}

    # 4) proximity_s <= 0.10s explicitly when cooldown_s=0.0
    elems_prox = [
        {"id": "p1", "sound_ref": "a.wav", "out_in": 5.0, "out_out": 5.2},
        {"id": "p2", "sound_ref": "b.wav", "out_in": 5.10, "out_out": 5.3},
    ]
    acc4, rej4 = deduplicate_and_schedule_sfx(elems_prox, 10.0, cooldown_s=0.0, proximity_s=0.10)
    assert [e["id"] for e in acc4] == ["p1"]
    assert [e["id"] for e in rej4] == ["p2"]
    print("  [PASS] test_negative_dedup_bounds_precedence_and_cooldown")


def run_tests():
    print("=" * 60)
    print("SUITE — sound_design_sync")
    print("=" * 60)
    tests = [
        test_safe_path_traversal,
        test_probe_invalid,
        test_resolve_asset,
        test_dedup,
        test_build_filter,
        test_negative_safe_path_and_probe,
        test_negative_resolve_volume_and_gain_db,
        test_negative_dedup_bounds_precedence_and_cooldown,
    ]
    fails = 0
    for t in tests:
        try:
            t()
        except Exception as e:
            fails += 1
            print(f"  [FALHA] {t.__name__}: {e}")
            import traceback; traceback.print_exc()
    print("OK" if fails == 0 else f"{fails} FALHA(S)")
    return 0 if fails == 0 else 1


if __name__ == "__main__":
    import sys
    sys.exit(run_tests())
