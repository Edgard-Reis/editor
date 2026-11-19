# -*- coding: utf-8 -*-
import sys
from pathlib import Path
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lower_third import (gerar_html_lower_third, animar_lower_third, render_lower_third_png)


def test_html_nfc():
    html = gerar_html_lower_third("João", "Cred", clip_id="c1")
    assert "João" in html
    print("  [PASS] test_html_nfc")


def test_render_png():
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "lt.png"
        info = render_lower_third_png("Nome", "Cred", out, sub_itens=["item"])
        assert out.exists()
        from PIL import Image
        with Image.open(out) as im:
            assert im.mode == "RGBA"
        assert info["bbox"]["w"] > 0
        assert info["face_avoided"] in (True, False)
        print("  [PASS] test_render_png")


def test_face_avoid():
    bp = {"presenter": {"face_anchor_1080p": [100, 100]}, "visual": {"palette": {}, "font_family": "Inter", "safe_zones": {"master_16x9": {"lower_third_max_w": 1150}}}}
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "lt.png"
        info = render_lower_third_png("Nome", "Cred", out, brand_profile=bp, x=50, y=50)
        assert info["face_avoided"] is True
        print("  [PASS] test_face_avoid")


def test_entry_exit_duration():
    info = None
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "lt.png"
        info = render_lower_third_png("Nome", "Cred", out, entry_duration_s=0.2, exit_duration_s=0.4, duration_seconds=2.0)
    assert info["entry_duration_s"] == 0.2
    assert info["exit_duration_s"] == 0.4
    assert info["duration_seconds"] == 2.0
    print("  [PASS] test_entry_exit_duration")


def test_long_text_no_clipping():
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "lt.png"
        info = render_lower_third_png("A" * 200, "B" * 200, out, max_width=300)
        assert info["bbox"]["x"] + info["bbox"]["w"] <= 1920
        print("  [PASS] test_long_text_no_clipping")


def test_two_brand_profiles():
    bp1 = {"presenter": {"face_anchor_1080p": [500, 500]},
           "visual": {"palette": {"primary": "#ff0000", "secondary": "#00ff00", "bg_dark": "#111111", "text_primary": "#ffffff"},
                      "font_family": "Arial", "safe_zones": {"master_16x9": {"lower_third_x": 10, "lower_third_y": 20, "lower_third_max_w": 200}}}}
    bp2 = {"presenter": {"face_anchor_1080p": [1800, 900]},
           "visual": {"palette": {"primary": "#0000ff", "secondary": "#ffff00", "bg_dark": "#222222", "text_primary": "#eeeeee"},
                      "font_family": "Courier", "safe_zones": {"master_16x9": {"lower_third_x": 300, "lower_third_y": 400, "lower_third_max_w": 400}}}}
    with tempfile.TemporaryDirectory() as td:
        out1 = Path(td) / "a.png"
        out2 = Path(td) / "b.png"
        info1 = render_lower_third_png("Nome", "Cred", out1, brand_profile=bp1, x=None, y=None, max_width=None)
        info2 = render_lower_third_png("Nome", "Cred", out2, brand_profile=bp2, x=None, y=None, max_width=None)
        assert info1["bbox"]["x"] == 10
        assert info1["bbox"]["y"] == 20
        assert info1["bbox"]["w"] <= 200
        assert info2["bbox"]["x"] == 300
        assert info2["bbox"]["y"] == 400
        assert info2["bbox"]["w"] <= 400
        # anti-face: bp1 face at 500,500, box at 10,20 no intersect -> not avoided maybe
        assert info1["clipped"] is False
        assert info2["clipped"] is False
    print("  [PASS] test_two_brand_profiles")


def test_fallback_minimal_profile():
    bp = {}  # minimal
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "c.png"
        info = render_lower_third_png("Nome", "Cred", out, brand_profile=bp)
        assert info["bbox"]["x"] == 80
        assert info["bbox"]["y"] == 760
        assert info["bbox"]["w"] <= 1150
    print("  [PASS] test_fallback_minimal_profile")


def run_tests():
    print("=" * 60)
    print("SUITE — lower_third")
    print("=" * 60)
    tests = [test_html_nfc, test_render_png, test_face_avoid, test_entry_exit_duration, test_long_text_no_clipping, test_two_brand_profiles, test_fallback_minimal_profile]
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
