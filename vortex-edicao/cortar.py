#!/usr/bin/env python3
"""2º passo: corta os erros e os respiros e monta a base da edição.

Uso:  python3 cortar.py <pasta_do_projeto> [--remover 134.3-139.8,158.25-162.7] [--pausa 0.32]
  --remover  trechos (tempo da gravação) com erro, falso começo ou repetição. REGRA: quando a pessoa repete,
             fica sempre a ÚLTIMA tentativa — remova as anteriores.
  --pausa    todo silêncio entre palavras maior que isso vira corte (respiro). Padrão 0,32 s.
Lê <projeto>/fonte/{video.mp4, voz.wav, palavras.json} e grava em <projeto>/media/:
  base.mp4 (30 fps constante, GOP 15), voz.wav, cortes.json, palavras_saida.json (tempo JÁ CORTADO)
"""
import argparse, json, subprocess
from pathlib import Path
import sys as _stdout_sys
if hasattr(_stdout_sys.stdout, "reconfigure"):
    _stdout_sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # trava: saída cp1252 não quebra o script

ap = argparse.ArgumentParser()
ap.add_argument("projeto"); ap.add_argument("--remover", default="")
ap.add_argument("--pausa", type=float, default=0.32)
ap.add_argument("--antes", type=float, default=0.07); ap.add_argument("--depois", type=float, default=0.12)
a = ap.parse_args()

P = Path(a.projeto); SRC = P / "fonte"; OUT = P / "media"; OUT.mkdir(parents=True, exist_ok=True)

_palavras = SRC / "palavras.json"
if not _palavras.exists():
    _stdout_sys.exit(f"[Erro] Não achei {_palavras}.\n"
             "       Rode antes: python transcrever.py <gravacao> <pasta_do_projeto>")
w = json.load(open(_palavras, encoding="utf-8"))
if not w:
    # sem esta guarda, w[0]/w[-1] lá embaixo morriam com IndexError opaco
    _stdout_sys.exit("[Erro] palavras.json está vazio — nada para cortar.\n"
             "       Confira se a transcrição gerou palavras (voz presente? modelo baixou?).")

rem = []
for _trecho in a.remover.split(","):
    if not _trecho:
        continue
    try:
        _ini, _fim = map(float, _trecho.split("-"))
    except ValueError:
        _stdout_sys.exit(f"[Erro] Trecho inválido em --remover: '{_trecho}'.\n"
                 "       Formato esperado: inicio-fim em segundos, ex.: --remover 134.3-139.8,158.25-162.7")
    if _ini >= _fim:
        # sem esta guarda, o ffmpeg recebia um trim invertido e falhava com erro incompreensível
        _stdout_sys.exit(f"[Erro] Trecho com início >= fim em --remover: '{_trecho}' ({_ini} >= {_fim}).\n"
                 "       Corrija para inicio-fim crescente.")
    rem.append((_ini, _fim))
fora = list(rem) + [(p["f"] + a.depois, q["t"] - a.antes) for p, q in zip(w, w[1:]) if q["t"] - p["f"] > a.pausa]
fora.sort(); m = []
for x, y in fora:
    if m and x <= m[-1][1]: m[-1] = (m[-1][0], max(m[-1][1], y))
    else: m.append((x, y))
c, cortes = max(0, w[0]["t"] - 0.15), []
for x, y in m:
    if x > c: cortes.append((c, x))
    c = max(c, y)
cortes.append((c, w[-1]["f"] + 0.35))
FPS = 30
cortes = [(round(x * FPS) / FPS, round(y * FPS) / FPS) for x, y in cortes if y - x > 0.15]

fv, fa = [], []
for i, (x, y) in enumerate(cortes):
    fv.append(f"[0:v]trim={x:.4f}:{y:.4f},setpts=PTS-STARTPTS[v{i}]")
    fa.append(f"[1:a]atrim={x:.4f}:{y:.4f},asetpts=PTS-STARTPTS,afade=t=in:d=0.006,afade=t=out:st={y - x - 0.006:.4f}:d=0.006[a{i}]")
n = len(cortes)
fc = ";".join(fv + fa) + ";" + "".join(f"[v{i}][a{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=1[v][a]"
tmp = OUT / "_base.mov"
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(SRC / "video.mp4"), "-i", str(SRC / "voz.wav"), "-filter_complex", fc,
                "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", "-c:a", "pcm_s16le", str(tmp)], check=True)
# o concat sai com ~29,98 fps; o HyperFrames precisa de fps constante
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(tmp), "-map", "0:v", "-vf", "fps=30", "-c:v", "libx264", "-crf", "16",
                "-g", "15", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(OUT / "base.mp4")], check=True)
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(tmp), "-map", "0:a", "-c:a", "pcm_s16le", "-ar", "48000", str(OUT / "voz.wav")], check=True)
tmp.unlink()

so, acc = [], 0.0
for x, y in cortes:
    for p in w:
        if p["t"] >= x - 0.02 and p["f"] <= y + 0.05:
            so.append({"w": p["w"], "t": round(p["t"] - x + acc, 3), "f": round(min(p["f"], y) - x + acc, 3)})
    acc += y - x
with open(OUT / "palavras_saida.json", "w", encoding="utf-8") as _f:
    json.dump(so, _f, ensure_ascii=False)
with open(OUT / "cortes.json", "w", encoding="utf-8") as _f:
    json.dump([{"de": x, "ate": y} for x, y in cortes], _f)
print(f"{n} cortes | {len(so)}/{len(w)} palavras | {acc:.1f} s de vídeo -> {OUT}")
