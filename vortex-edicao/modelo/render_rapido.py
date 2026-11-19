#!/usr/bin/env python3
"""Render rápido do HyperFrames, com a mesma qualidade.

1. PARALELO: cada trecho renderiza com --workers N (vários Chromes ao mesmo tempo).
2. SÓ ONDE TEM MOTION: os trechos sem nenhum motion saem direto do base.mp4 (ffmpeg), sem passar pelo navegador.
3. CACHE: cada trecho com motion vira um HTML próprio; o hash dele é a chave do cache. Num ajuste, só os trechos
   que mudaram renderizam de novo.
No fim: UMA compressão só (x264 CRF 16, preset slow) juntando tudo + áudio mixado no ffmpeg (mesmos
data-start/data-duration/data-volume do index.html) + master −14 LUFS / −1 dBTP.

Pré-requisito: python3 build.py (gera index.html e partes.json).
Uso:
  python3 render_rapido.py -o renders/final.mp4 [--workers 4]
  python3 render_rapido.py --so-trechos        # só renderiza/atualiza o cache dos trechos com motion
"""
import argparse, hashlib, json, math, os, re, shutil, subprocess, sys, time
from pathlib import Path
import sys as _stdout_sys
if hasattr(_stdout_sys.stdout, "reconfigure"):
    _stdout_sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # trava: saída cp1252 não quebra o script

AQUI = Path(__file__).parent
CACHE = AQUI / "renders" / ".trechos"
RE_T = re.compile(r'data-start="([\d.]+)"\s+data-duration="([\d.]+)"')

def descobrir_raiz(ponto_partida=__file__, editor_root=None):
    """Localiza a raiz do Drifit Editor subindo a árvore de diretórios ou por env/arg."""
    candidatos = []
    if editor_root is not None:
        candidatos.append(Path(editor_root).resolve())
    env_root = os.environ.get("EDITOR_ROOT")
    if env_root:
        candidatos.append(Path(env_root).resolve())
    for cand in (ponto_partida, __file__):
        cur = Path(cand).resolve()
        if cur.is_file():
            cur = cur.parent
        candidatos.extend([cur, *cur.parents])

    for p in candidatos:
        if (p / "motion_library").is_dir() and (p / "vortex-edicao").is_dir():
            return p

    raise RuntimeError(
        "[Erro] Raiz do Drifit Editor não encontrada. "
        "Certifique-se de que os diretórios 'motion_library' e 'vortex-edicao' existem na estrutura do projeto."
    )

def resolver_toolchain_local(ponto_partida=__file__, editor_root=None):
    """Descobre e valida as ferramentas locais (Node.js, HyperFrames 0.9.5, FFmpeg/FFprobe)."""
    raiz = descobrir_raiz(ponto_partida, editor_root=editor_root)

    # 1. Localizar Node.js
    node_bin = shutil.which("node") or shutil.which("node.exe")
    if not node_bin:
        raise RuntimeError(
            "[Erro] Executável do Node.js não foi encontrado no sistema (PATH).\n"
            "       Instale o Node.js v20+ ou configure o executável no ambiente."
        )

    # 2. Localizar HyperFrames 0.9.5 local (tools/, experimental ou cache _npx local)
    candidatos_dirs = []
    if "DRIFIT_TOOLS_DIR" in os.environ and Path(os.environ["DRIFIT_TOOLS_DIR"]).is_dir():
        candidatos_dirs.append(Path(os.environ["DRIFIT_TOOLS_DIR"]))
    candidatos_dirs.append(raiz / "tools" / "hyperframes")
    candidatos_dirs.append(
        raiz / "projetos" / "dr-gestao" / "episodios" / "teste-piloto-parte-02"
        / "fase5_5_integracao_motion_library" / "fase5_6" / "etapa2_implementacao"
        / "candidato" / "tools" / "hyperframes"
    )
    for npx_root in (
        Path(os.environ.get("LOCALAPPDATA", "")) / "npm-cache" / "_npx",
        Path.home() / "AppData" / "Local" / "npm-cache" / "_npx",
        Path.home() / ".npm" / "_npx",
    ):
        if npx_root.is_dir():
            for sub in sorted(npx_root.iterdir()):
                if sub.is_dir() and (sub / "node_modules" / "hyperframes" / "bin" / "hyperframes.mjs").is_file():
                    candidatos_dirs.append(sub)

    hf_tools_dir = None
    hf_mjs = None
    versoes_vistas = []
    for cand_dir in candidatos_dirs:
        cand_mjs = cand_dir / "node_modules" / "hyperframes" / "bin" / "hyperframes.mjs"
        if not cand_mjs.is_file():
            continue
        r_ver = subprocess.run([node_bin, str(cand_mjs), "--version"], capture_output=True, text=True, errors="replace")
        ver_str = r_ver.stdout.strip() if r_ver.returncode == 0 else ""
        versoes_vistas.append((cand_dir, cand_mjs, ver_str))
        if ver_str == "0.9.5":
            hf_tools_dir = cand_dir
            hf_mjs = cand_mjs
            break

    if hf_mjs is None:
        if not versoes_vistas:
            raise RuntimeError(
                f"[Erro] HyperFrames local não encontrado em 'tools/hyperframes/' nem no cache _npx.\n"
                f"       Execute o provisionamento da toolchain local antes de renderizar."
            )
        encontradas = ", ".join(f"{v or '?'} ({p})" for _, p, v in versoes_vistas)
        raise RuntimeError(
            f"[Erro] Versão incompatível do HyperFrames local.\n"
            f"       Esperada: 0.9.5\n"
            f"       Encontrada(s): {encontradas}"
        )

    # 3. Localizar FFmpeg e FFprobe locais
    bin_local_dir = None
    if sys.platform == "win32":
        candidatos_bin = [
            hf_tools_dir / "bin" / "windows-x64",
            hf_tools_dir / "bin",
            raiz / "bin"
        ]
        for c in candidatos_bin:
            if (c / "ffmpeg.exe").is_file() and (c / "ffprobe.exe").is_file():
                bin_local_dir = c
                break

    if not bin_local_dir:
        # Fallback para sistema global se disponível
        ffmpeg_global = shutil.which("ffmpeg")
        ffprobe_global = shutil.which("ffprobe")
        if ffmpeg_global and ffprobe_global:
            ffmpeg_bin = Path(ffmpeg_global)
            ffprobe_bin = Path(ffprobe_global)
            bin_local_dir = ffmpeg_bin.parent
        else:
            raise RuntimeError(
                f"[Erro] Binários locais do FFmpeg e FFprobe não foram encontrados em:\n"
                f"       {hf_tools_dir / 'bin' / 'windows-x64'}\n"
                f"       nem no PATH global do sistema operacional."
            )
    else:
        ffmpeg_bin = bin_local_dir / "ffmpeg.exe"
        ffprobe_bin = bin_local_dir / "ffprobe.exe"

    # Validar execução de FFmpeg e FFprobe
    for b_nome, b_path in [("FFmpeg", ffmpeg_bin), ("FFprobe", ffprobe_bin)]:
        r_b = subprocess.run([str(b_path), "-version"], capture_output=True, text=True, errors="replace")
        if r_b.returncode != 0:
            raise RuntimeError(f"[Erro] Falha ao executar {b_nome} local em: {b_path}")

    # 4. Injetar variáveis de ambiente do subprocesso
    env_exec = os.environ.copy()
    env_exec["FFMPEG_PATH"] = str(ffmpeg_bin)
    env_exec["FFPROBE_PATH"] = str(ffprobe_bin)
    env_exec["PATH"] = str(bin_local_dir) + os.pathsep + env_exec.get("PATH", "")
    env_exec["HYPERFRAMES_SKIP_SKILLS"] = "1"

    return {
        "raiz": raiz,
        "node": node_bin,
        "hf_mjs": hf_mjs,
        "ffmpeg": ffmpeg_bin,
        "ffprobe": ffprobe_bin,
        "env": env_exec,
        "bin_dir": bin_local_dir
    }

# Toolchain resolvida uma única vez na inicialização
_TOOLCHAIN = None
def get_toolchain(ponto_partida=__file__, editor_root=None):
    global _TOOLCHAIN
    if _TOOLCHAIN is None:
        _TOOLCHAIN = resolver_toolchain_local(ponto_partida, editor_root=editor_root)
    return _TOOLCHAIN

def janelas(p, junta, margem):
    iv = []
    for h in p["palco"] + p["html"]:
        m = RE_T.search(h)
        if m:
            a, d = float(m.group(1)), float(m.group(2)); iv.append((a, a + d))
    iv += [tuple(z) for z in p["zooms_camera"]]
    iv.sort(); out = []
    for a, b in iv:
        a, b = max(0.0, a - margem), min(p["dur"], b + margem)
        if out and a - out[-1][1] < junta: out[-1][1] = max(out[-1][1], b)
        else: out.append([a, b])
    fps = p["fps"]; tot = round(p["dur"] * fps)
    fr = []
    for a, b in out:
        A, B = max(0, math.floor(a * fps)), min(tot, math.ceil(b * fps))
        if fr and A <= fr[-1][1]: fr[-1][1] = max(fr[-1][1], B)
        else: fr.append([A, B])
    # trecho com no máximo ~90 s: senão o HyperFrames enche o disco com os quadros extraídos da mídia
    MAX = int(90 * fps); sep = []
    for A, B in fr:
        while B - A > MAX:
            sep.append([A, A + MAX]); A += MAX
        sep.append([A, B])
    return sep, tot

def desloca(h, a):
    # Clip que começou ANTES do trecho ganhava data-start negativo, e o HyperFrames o mantinha visível pela
    # duração inteira a partir do 0 (ex.: painel vazio aparecendo fora de hora). Corrige cortando o clip no
    # início do trecho: data-start = 0, duração encurtada e data-media-start avançado no mesmo tanto.
    corte = [0.0]
    def f(m):
        s, d = float(m.group(1)) - a, float(m.group(2))
        if s < 0: corte[0], s, d = -s, 0.0, d + s
        return f'data-start="{round(s, 4)}" data-duration="{round(d, 4)}"'
    h = RE_T.sub(f, h, count=1)
    if corte[0]:
        h = re.sub(r'data-media-start="([\d.]+)"', lambda m: f'data-media-start="{round(float(m.group(1)) + corte[0], 4)}"', h, count=1)
    # +1 ms no início da mídia: o arredondamento do corte (ex. 36,2333 s) fazia pegar o quadro anterior em alguns quadros
    return re.sub(r'data-media-start="([\d.]+)"', lambda m: f'data-media-start="{round(float(m.group(1)) + 0.001, 4)}"', h)

def dentro(h, a, b):
    m = RE_T.search(h)
    if not m: return False
    s, d = float(m.group(1)), float(m.group(2))
    return s < b and s + d > a

def posicoes(linha):
    return [float(x) for x in re.findall(r',(-?[\d.]+)\);', linha)]

def html_trecho(p, A, B, aqui=AQUI):
    fps = p["fps"]; a, b = A / fps, B / fps; dur = round((B - A) / fps, 4)
    w = int(p.get("width", 1920))
    h = int(p.get("height", 1080))
    res_mode = "portrait" if h > w else "landscape"
    palco = [desloca(h_clip, a) for h_clip in p["palco"] if dentro(h_clip, a, b)]
    html = [desloca(h_clip, a) for h_clip in p["html"] if dentro(h_clip, a, b)]
    # entram as animações dentro do trecho E as que começaram antes dele (clip cortado no início ou trecho
    # dividido em 90 s), mas só de elementos que existem no trecho (senão o querySelector volta null e quebra a página)
    ids = set(re.findall(r'id="([^"]+)"', "".join(palco + html)))
    def ok(l):
        ref = re.findall(r'\("#([\w-]+)', l)   # alvo do tween/querySelector (cor "#fff" fica de fora)
        if ref and not all(x in ids or x in ("palco", "base", "root") for x in ref): return False
        ps = posicoes(l)
        return any(a - 1e-3 <= t <= b + 1e-3 for t in ps) or (ref and any(t <= b + 1e-3 for t in ps))
    js = [l for l in p["js"] if ok(l)]
    # Priorizar GSAP local no workspace para renderização offline estrita
    gsap_src = "assets/vendor/gsap.min.js" if (aqui / "assets/vendor/gsap.min.js").is_file() else "https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"
    return f'''<!doctype html>
<html lang="pt-BR" data-resolution="{res_mode}">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width={w}, height={h}" />
<script src="{gsap_src}"></script>
<style>{p["estilo"]}</style>
</head>
<body>
<div id="root" data-composition-id="main" data-start="0" data-duration="{dur}" data-width="{w}" data-height="{h}">
  <div id="palco"><video id="base" class="clip" src="media/base.mp4" muted playsinline data-start="0" data-duration="{dur}" data-media-start="{round(a + 0.001, 4)}" data-track-index="0"></video>{"".join(palco)}</div>
  {chr(10).join(html)}
</div>
<script>
const tl = gsap.timeline({{ paused: true }});
tl.set({{}}, {{}}, {p["dur"]});
tl.set("#palco", {{scale:1,x:0,y:0}}, 0);
{chr(10).join(js)}
const trecho = gsap.timeline({{ paused: true }});
trecho.add(tl.tweenFromTo({round(a, 4)}, {round(b, 4)}, {{ ease: "none" }}));
window.__timelines["main"] = trecho;
trecho.seek(0);
</script>
</body>
</html>'''

def renderiza_trechos(p, fr, workers, aqui=AQUI, cache=CACHE, editor_root=None):
    tc = get_toolchain(aqui, editor_root=editor_root)
    cache.mkdir(parents=True, exist_ok=True)
    # a versão dos arquivos de mídia e fontes entra no hash (trocou a base ou um logo -> renderiza de novo)
    assinatura = "".join(
        f"{f}:{os.path.getmtime(f)}"
        for f in sorted(map(str, list(aqui.glob("media/*")) + list(aqui.glob("logos/*")) + list(aqui.glob("fonts/*"))))
    )
    fps = int(p.get("fps", 30))
    arquivos, novos = [], 0
    for k, (A, B) in enumerate(fr):
        if B <= A:
            continue
        h = html_trecho(p, A, B, aqui=aqui)
        chave = hashlib.sha1((h + assinatura).encode()).hexdigest()[:16]
        out = cache / f"{A:06d}_{B:06d}_{chave}.mp4"
        arquivos.append(out)
        if out.exists():
            continue
        novos += 1
        tmp = aqui / f"_trecho_{chave}.html"
        tmp.write_text(h, encoding="utf-8")
        t0 = time.time()
        cmd_hf = [
            tc["node"], str(tc["hf_mjs"]), "render",
            "-c", tmp.name, "-o", str(out),
            "-w", str(workers), "-f", str(fps), "--crf", "8", "--quiet",
        ]
        r = subprocess.run(cmd_hf, cwd=aqui, env=tc["env"], capture_output=True, text=True)
        tmp.unlink(missing_ok=True)
        import glob as _g, shutil as _sh, tempfile as _tf   # cache de quadros extraídos: libera o disco a cada trecho
        for d in _g.glob(os.path.join(_tf.gettempdir(), "hyperframes-extract-cache-*")):
            _sh.rmtree(d, ignore_errors=True)
        if r.returncode != 0 or not out.exists():
            raise RuntimeError(f"falhou no trecho {A}-{B}:\n{r.stdout[-2000:]}\n{r.stderr[-2000:]}")
        pr_out = subprocess.run(
            [str(tc["ffprobe"]), "-v", "error", "-count_packets", "-select_streams", "v", "-show_entries", "stream=nb_read_packets", "-of", "csv=p=0", str(out)],
            cwd=aqui, env=tc["env"], capture_output=True, text=True,
        ).stdout.strip()
        n = int(pr_out or "0")
        if n == B - A + 1:
            # duração em float (ex. 13,0667 s × 30 = 392,001): o HyperFrames arredonda pra cima -> tira o quadro extra do fim
            aparado = out.with_suffix(".tmp.mp4")
            subprocess.run([str(tc["ffmpeg"]), "-y", "-loglevel", "error", "-i", str(out), "-map", "0", "-frames:v", str(B - A), "-c", "copy", str(aparado)],
                           cwd=aqui, env=tc["env"], check=True)
            aparado.replace(out)
            n = B - A
        if n != B - A:
            out.unlink(missing_ok=True)
            raise RuntimeError(f"trecho {A}-{B}: {n} quadros, esperado {B - A}")
        print(f"  trecho {k + 1}/{len(fr)} ({(B - A) / fps:.1f} s) em {time.time() - t0:.0f} s", flush=True)
    print(f"{novos} trecho(s) renderizado(s), {len(arquivos) - novos} do cache")
    return arquivos

def mixa_audio(p, saida, aqui=AQUI, editor_root=None):
    tc = get_toolchain(aqui, editor_root=editor_root)
    audio_tags = p.get("audio") or []
    if not audio_tags:
        subprocess.run(
            [str(tc["ffmpeg"]), "-y", "-loglevel", "error", "-f", "lavfi",
             "-i", f"anullsrc=r=48000:cl=stereo:d={p['dur']:.6f}", "-c:a", "pcm_s24le", str(saida)],
            cwd=aqui, env=tc["env"], check=True,
        )
        return
    ins, fil = [], []
    for k, h in enumerate(audio_tags):
        src = re.search(r'src="([^"]+)"', h).group(1)
        s = float(re.search(r'data-start="([\d.]+)"', h).group(1))
        d = float(re.search(r'data-duration="([\d.]+)"', h).group(1))
        v = float(re.search(r'data-volume="([\d.]+)"', h).group(1))
        src_path = Path(src) if Path(src).is_absolute() else (aqui / src)
        ins += ["-i", str(src_path)]
        ms = round(s * 1000)
        _pr = subprocess.run([str(tc["ffprobe"]), "-v", "error", "-show_entries", "stream=channels", "-of", "csv=p=0", str(src_path)],
                             cwd=aqui, env=tc["env"], capture_output=True, text=True)
        _canais = _pr.stdout.split()
        if not _canais:
            raise RuntimeError(
                f"[Erro] ffprobe não achou stream de áudio em: {src_path}\n"
                "       Verifique se o arquivo existe e tem trilha de áudio (ffprobe -hide_banner <arquivo>)."
            )
        ch = int(_canais[0])
        estereo = "pan=stereo|c0=c0|c1=c0" if ch == 1 else "aformat=channel_layouts=stereo"
        out_lbl = "[mix]" if len(audio_tags) == 1 else f"[a{k}]"
        fil.append(f"[{k}:a]aresample=48000,{estereo},atrim=0:{d},volume={v},adelay={ms}|{ms},apad,asetpts=N/SR/TB,atrim=0:{p['dur']}{out_lbl}")
    n = len(audio_tags)
    if n > 1:
        fil.append("".join(f"[a{k}]" for k in range(n)) + f"amix=inputs={n}:duration=longest:dropout_transition=0,volume={n}[mix]")
    subprocess.run([str(tc["ffmpeg"]), "-y", "-loglevel", "error", *ins, "-filter_complex", ";".join(fil), "-map", "[mix]", "-ac", "2", "-ar", "48000", "-c:a", "pcm_s24le", str(saida)],
                   cwd=aqui, env=tc["env"], check=True)

def junta(p, fr, tot, arquivos, saida_video, aqui=AQUI, editor_root=None):
    tc = get_toolchain(aqui, editor_root=editor_root)
    fr_valid = [(A, B) for A, B in fr if B > A]
    pecas, cur = [], 0
    for (A, B), f in zip(fr_valid, arquivos):
        if A > cur: pecas.append(("base", cur, A))
        pecas.append(("trecho", A, B, f)); cur = B
    if cur < tot: pecas.append(("base", cur, tot))
    ins, fil, idx = ["-i", str(aqui / "media/base.mp4")], [], 1
    for k, pc in enumerate(pecas):
        if pc[0] == "base":
            fil.append(f"[0:v]trim=start_frame={pc[1]}:end_frame={pc[2]},setpts=PTS-STARTPTS[v{k}]")
        else:
            ins += ["-i", str(pc[3])]; fil.append(f"[{idx}:v]setpts=PTS-STARTPTS[v{k}]"); idx += 1
    fps = int(p.get("fps", 30))
    fil.append("".join(f"[v{k}]" for k in range(len(pecas))) + f"concat=n={len(pecas)}:v=1:a=0,fps={fps}[v]")
    subprocess.run([str(tc["ffmpeg"]), "-y", "-loglevel", "error", *ins, "-filter_complex", ";".join(fil), "-map", "[v]",
                    "-c:v", "libx264", "-preset", "fast", "-crf", "16", "-pix_fmt", "yuv420p", "-r", str(fps), "-movflags", "+faststart", str(saida_video)],
                   cwd=aqui, env=tc["env"], check=True)
    base = sum(pc[2] - pc[1] for pc in pecas if pc[0] == "base")
    print(f"{len(pecas)} peças · {base / max(tot, 1) * 100:.0f}% do vídeo saiu direto da base (sem navegador)")

def master(video, audio, saida, aqui=AQUI, apply_loudnorm=True, editor_root=None):
    tc = get_toolchain(aqui, editor_root=editor_root)
    lim = "alimiter=limit=0.891:attack=5:release=50"
    if apply_loudnorm:
        J = subprocess.run([str(tc["ffmpeg"]), "-hide_banner", "-i", str(audio), "-af", f"{lim},loudnorm=I=-14.0:TP=-1.0:LRA=11:print_format=json", "-f", "null", "-"],
                           cwd=aqui, env=tc["env"], capture_output=True, text=True).stderr
        af = None
        if "{" in J and "}" in J:
            try:
                d = json.loads(J[J.rindex("{"):J.rindex("}") + 1])
                vals = [float(d["input_i"]), float(d["input_tp"]), float(d["input_lra"]), float(d["input_thresh"]), float(d["target_offset"])]
                if all(math.isfinite(v) for v in vals):
                    af = (f"{lim},loudnorm=I=-14.0:TP=-1.0:LRA=11:measured_I={d['input_i']}:measured_TP={d['input_tp']}:measured_LRA={d['input_lra']}"
                          f":measured_thresh={d['input_thresh']}:offset={d['target_offset']}:linear=true")
            except (ValueError, KeyError, json.JSONDecodeError):
                af = None
        if af is None:
            af = f"{lim},loudnorm=I=-14.0:TP=-1.0:LRA=11"
    else:
        af = lim
    subprocess.run([str(tc["ffmpeg"]), "-y", "-loglevel", "error", "-i", str(video), "-i", str(audio), "-map", "0:v", "-map", "1:a", "-c:v", "copy",
                    "-af", af, "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2", "-movflags", "+faststart", str(saida)],
                   cwd=aqui, env=tc["env"], check=True)
    return af

def executar_render(
    aqui=AQUI,
    saida="renders/final.mp4",
    *,
    workers: int = 4,
    junta_gap: float = 2.0,
    margem: float = 0.2,
    so_trechos: bool = False,
    apply_loudnorm: bool = True,
    editor_root=None,
):
    aqui = Path(aqui).resolve()
    cache = aqui / "renders" / ".trechos"
    tc = get_toolchain(aqui, editor_root=editor_root)
    t0 = time.time()
    p = json.load(open(aqui / "partes.json", encoding="utf-8"))
    fr, tot = janelas(p, junta_gap, margem)
    mot = sum(B - A for A, B in fr)
    print(f"{len(fr)} trechos com motion = {mot / max(tot, 1) * 100:.0f}% do vídeo ({mot / p['fps']:.0f} s de {tot / p['fps']:.0f} s)")
    arquivos = renderiza_trechos(p, fr, workers, aqui=aqui, cache=cache, editor_root=editor_root)
    if so_trechos:
        return {"ok": True, "trechos": len(arquivos), "master_filter": None}
    (aqui / "renders").mkdir(exist_ok=True)
    vid, aud = aqui / "renders" / "_video.mp4", aqui / "renders" / "_audio.wav"
    junta(p, fr, tot, arquivos, vid, aqui=aqui, editor_root=editor_root)
    mixa_audio(p, aud, aqui=aqui, editor_root=editor_root)
    saida_final = Path(saida) if Path(saida).is_absolute() else (aqui / saida)
    saida_final.parent.mkdir(parents=True, exist_ok=True)
    master_filter = master(vid, aud, saida_final, aqui=aqui, apply_loudnorm=apply_loudnorm, editor_root=editor_root)
    vid.unlink(missing_ok=True)
    aud.unlink(missing_ok=True)
    print(f"Final: {saida_final} | {time.time() - t0:.0f} s no total")
    return {
        "ok": True,
        "output_path": str(saida_final),
        "trechos": len(arquivos),
        "total_frames": tot,
        "master_filter": master_filter,
    }

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--saida", default="renders/final.mp4")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--junta", type=float, default=2.0, help="junta trechos com motion separados por menos de X s")
    ap.add_argument("--margem", type=float, default=0.2)
    ap.add_argument("--so-trechos", action="store_true")
    a = ap.parse_args()
    try:
        executar_render(AQUI, a.saida, workers=a.workers, junta_gap=a.junta, margem=a.margem, so_trechos=a.so_trechos)
    except Exception as exc:
        sys.exit(str(exc))
