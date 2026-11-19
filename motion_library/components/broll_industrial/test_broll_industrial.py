# -*- coding: utf-8 -*-
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from broll_industrial import (
    resolve_safe_media_path,
    probe_broll_media,
    resolve_broll_asset,
    build_broll_ffmpeg_filter,
)


def test_traversal_rejected():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "a.txt").write_text("x")
        try:
            resolve_safe_media_path("../fora.mp4", [root])
            assert False
        except ValueError:
            pass
    print("  [PASS] test_traversal_rejected")


def test_absolute_outside_rejected():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td) / "root"
        root.mkdir()
        outside = Path(td) / "outside.txt"
        outside.write_text("x")
        try:
            resolve_safe_media_path(str(outside), [root])
            assert False
        except ValueError:
            pass
    print("  [PASS] test_absolute_outside_rejected")


def test_empty_corrupt_media():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        empty = root / "empty.mp4"
        empty.write_bytes(b"")
        try:
            probe_broll_media(empty)
            assert False
        except ValueError:
            pass
        corrupt = root / "corrupt.png"
        corrupt.write_bytes(b"not an image")
        try:
            probe_broll_media(corrupt)
            assert False
        except ValueError:
            pass
    print("  [PASS] test_empty_corrupt_media")


def test_resolve_hierarchy():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        media = root / "clip.mp4"
        # create a tiny image instead of video
        from PIL import Image
        Image.new("RGB", (10, 10)).save(root / "clip.png")
        media = root / "clip.png"
        # level 1 explicit
        el = {"media_ref": "clip.png"}
        r = resolve_broll_asset(el, [root])
        assert r["resolved"] is True and r["level"] == 1
        # level 2 catalog
        el2 = {"tags": ["industrial"]}
        catalog = [{"media_ref": "clip.png", "tags": ["industrial", "fabrica"]}]
        r2 = resolve_broll_asset(el2, [root], local_catalog=catalog)
        assert r2["resolved"] is True and r2["level"] == 2
        # level 3 unresolved
        r3 = resolve_broll_asset({"tags": ["nope"]}, [root], local_catalog=[])
        assert r3["resolved"] is False
    print("  [PASS] test_resolve_hierarchy")


def test_build_filter_image_video():
    f_img = build_broll_ffmpeg_filter(1, "vbase", "vo", out_in=0.0, out_out=2.0, media_type="image", media_duration_s=None)
    assert "filter_steps" in f_img
    assert f_img["audio_discarded"] is True
    f_vid = build_broll_ffmpeg_filter(2, "vbase", "vo2", out_in=0.0, out_out=2.0, media_type="video", media_duration_s=5.0)
    assert "trim=start=" in f_vid["filter_steps"][0]
    # validation
    try:
        build_broll_ffmpeg_filter(1, "vbase", "vo", out_in=0.0, out_out=0.0, media_type="image", media_duration_s=None)
        assert False
    except ValueError:
        pass
    try:
        build_broll_ffmpeg_filter(1, "vbase", "vo", out_in=0.0, out_out=1.0, media_type="image", media_duration_s=None, ken_burns=0.5)
        assert False
    except ValueError:
        pass
    try:
        build_broll_ffmpeg_filter(1, "vbase", "vo", out_in=0.0, out_out=1.0, media_type="image", media_duration_s=None, mode="x")
        assert False
    except ValueError:
        pass
    print("  [PASS] test_build_filter_image_video")


def run_tests():
    print("=" * 60)
    print("SUITE — broll_industrial")
    print("=" * 60)
    tests = [test_traversal_rejected, test_absolute_outside_rejected, test_empty_corrupt_media,
             test_resolve_hierarchy, test_build_filter_image_video]
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
