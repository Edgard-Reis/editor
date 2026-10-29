#!/usr/bin/env python3
"""1º passo: prepara a gravação, trata o áudio com IA e transcreve palavra a palavra.

Uso:  python3 transcrever.py <gravacao.mp4> <pasta_do_projeto> [--modelo large-v3-turbo] [--idioma pt]
Gera em <projeto>/fonte/:
  video.mp4      a gravação inteira em 1920×1080, 30 fps constante
  voz.wav        a voz limpa (redução de ruído) e normalizada em -18 LUFS (mono, 48 kHz)
  voz_bruta.wav  áudio original extraído sem filtro
  palavras.json  [{"w": palavra, "t": início, "f": fim}, ...] no tempo da gravação
  roteiro.txt    a fala com tempo, frase por frase — é o que se LÊ pra achar erros e repetições

Transcrição padrão: faster-whisper local (large-v3-turbo) com Silero VAD e contexto semântico.
Fallback: ElevenLabs Scribe se houver ELEVENLABS_API_KEY ou openai-whisper clássico.
"""
import argparse, json, os, shutil, subprocess, sys, urllib.request, uuid
from pathlib import Path
import sys as _stdout_sys
if hasattr(_stdout_sys.stdout, "reconfigure"):
    _stdout_sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # trava: saída cp1252 não quebra o script

RAIZ = Path(__file__).resolve().parent
WORKSPACE = RAIZ.parent


def _cache_huggingface():
    """Cache do Whisper/HuggingFace FORA do projeto.

    O modelo large-v3 ocupa ~1.5 GB; dentro do projeto poluía o repo e o gitignore.
    Respeita HF_HOME se o usuário já definiu; senão usa o cache padrão do usuário
    por plataforma (%LOCALAPPDATA% no Windows, ~/.cache no macOS/Linux).
    """
    ja_definido = os.environ.get("HF_HOME")
    if ja_definido:
        return Path(ja_definido)
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "huggingface"
    return Path.home() / ".cache" / "huggingface"


CACHE_HF = _cache_huggingface()
os.environ["HF_HOME"] = str(CACHE_HF)

# Prompt de contexto do Whisper. A marca NÃO fica aqui (motor central deve ser
# genérico): cada projeto define seu lexicon em config.json
# → preferencias_edicao.lexicon_transcricao. Sem isso, usa o genérico abaixo.
PROMPT_GENERICO = (
    "Transcrição de vídeo em português do Brasil, com timestamps de palavra."
)


def prompt_contexto(dir_projeto):
    """Lexicon de transcrição do projeto (config.json), ou prompt genérico.

    `dir_projeto` é a pasta que contém o config.json (a workspace do episódio,
    que herda de branding/config.json). Se ausente/inválido, cai no genérico.
    """
    cfg = Path(dir_projeto) / "config.json"
    if cfg.exists():
        try:
            d = json.load(open(cfg, encoding="utf-8"))
            lex = (d.get("preferencias_edicao") or {}).get("lexicon_transcricao")
            if isinstance(lex, str) and lex.strip():
                return lex.strip()
        except Exception as e:
            print(f"  [Aviso] Não li lexicon_transcricao de {cfg.name} ({e}); usando prompt genérico.")
    return PROMPT_GENERICO


def sh(cmd):
    subprocess.run(cmd, check=True)

def _ler_env(chave):
    """Lê `chave` do ambiente e, se não achar, em .env subindo a árvore de pastas.

    Fonte única: D:\\Drifit\\Editor\\.env (raiz). Os .env duplicados (vortex-edicao/ e
    projetos/dr-gestao/) foram removidos — qualquer script, de qualquer subpasta,
    encontra a mesma chave.
    """
    k = os.environ.get(chave)
    if k:
        return k.strip().strip('"').strip("'")
    for pasta in Path(__file__).resolve().parents:
        env = pasta / ".env"
        if not env.exists():
            continue
        for l in env.read_text(encoding="utf-8", errors="ignore").splitlines():
            if l.strip().startswith(chave + "="):
                v = l.split("=", 1)[1].strip().strip('"').strip("'")
                if v:
                    return v
    return None


def chave_elevenlabs():
    return _ler_env("ELEVENLABS_API_KEY")

def trata_e_normaliza_voz(src, dst, limpar=True):
    dst = Path(dst)
    pasta = dst.parent
    raw_wav = pasta / "voz_raw.wav"
    clean_wav = pasta / "voz_denoised.wav"

    # 1. Extrai áudio mono 48kHz cortando frequências abaixo de 75Hz (rumble de ar-condicionado/mesa)
    print("  -> Extraindo áudio e aplicando filtro passa-alta (75 Hz)...")
    sh([
        "ffmpeg", "-y", "-loglevel", "error", "-i", str(src),
        "-vn", "-af", "highpass=f=75",
        "-ar", "48000", "-ac", "1", str(raw_wav)
    ])

    audio_para_normalizar = raw_wav

    # 2. Redução de ruído com noisereduce se habilitado
    if limpar:
        try:
            import noisereduce as nr
            import soundfile as sf
            print("  -> Aplicando isolamento e redução de ruído de fundo (noisereduce)...")
            data, rate = sf.read(str(raw_wav))
            # Reduz ruído estacionário preservando 80% do sinal original para evitar artefatos
            reduced = nr.reduce_noise(y=data, sr=rate, stationary=True, prop_decrease=0.80)
            sf.write(str(clean_wav), reduced, rate)
            audio_para_normalizar = clean_wav
        except Exception as e:
            print(f"  [Aviso] Não foi possível rodar noisereduce ({e}). Continuando com áudio padrão...")
            audio_para_normalizar = raw_wav

    # 3. Mede e aplica normalização de volume (EBU R128 -18 LUFS)
    print("  -> Normalizando voz para -18 LUFS...")
    r = subprocess.run([
        "ffmpeg", "-hide_banner", "-i", str(audio_para_normalizar),
        "-vn", "-af", "loudnorm=I=-18:TP=-2:LRA=11:print_format=json",
        "-f", "null", "-"
    ], capture_output=True, text=True)

    try:
        m = json.loads(r.stderr[r.stderr.rfind("{"): r.stderr.rfind("}") + 1])
        af = (
            f"loudnorm=I=-18:TP=-2:LRA=11:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
            f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true"
        )
    except Exception:
        af = "loudnorm=I=-18:TP=-2:LRA=11"

    sh([
        "ffmpeg", "-y", "-loglevel", "error", "-i", str(audio_para_normalizar),
        "-vn", "-af", af, "-ar", "48000", "-ac", "1", str(dst)
    ])

    # Limpeza de arquivos intermediários
    if raw_wav.exists() and raw_wav != dst:
        raw_wav.unlink()
    if clean_wav.exists() and clean_wav != dst:
        clean_wav.unlink()

def transcreve_faster_whisper(voz, pasta, idioma, modelo_nome="large-v3-turbo"):
    from faster_whisper import WhisperModel
    import soundfile as sf
    import numpy as np

    print(f"Transcrevendo com faster-whisper local (modelo: {modelo_nome})...")
    CACHE_HF.mkdir(parents=True, exist_ok=True)

    # Prepara áudio mono 16 kHz float32 diretamente para o Whisper
    voz_16k = Path(pasta) / "voz_16k.wav"
    sh(["ffmpeg", "-y", "-loglevel", "error", "-i", str(voz), "-ar", "16000", "-ac", "1", str(voz_16k)])
    audio_np, _ = sf.read(str(voz_16k))
    audio_np = audio_np.astype(np.float32)
    
    # Executa com int8 em CPU utilizando número seguro de threads (evita travar o sistema)
    model = WhisperModel(
        modelo_nome,
        device="cpu",
        compute_type="int8",
        cpu_threads=8,
        download_root=str(CACHE_HF)
    )

    segments, info = model.transcribe(
        audio_np,
        language=idioma,
        word_timestamps=True,
        vad_filter=True,
        vad_parameters=dict(min_silence_duration_ms=400),
        initial_prompt=prompt_contexto(pasta.parent)
    )

    out = []
    for s in segments:
        for w in s.words:
            palavra = w.word.strip()
            if palavra:
                out.append({"w": palavra, "t": round(w.start, 3), "f": round(w.end, 3)})

    if voz_16k.exists():
        voz_16k.unlink()

    return out

def transcreve(voz, pasta, idioma, modelo_nome="large-v3-turbo"):
    k = chave_elevenlabs()
    if k:
        print("Transcrevendo com ElevenLabs Scribe…")
        lim = "----" + uuid.uuid4().hex; corpo = b""
        cod = {"pt": "por", "en": "eng", "es": "spa"}.get(idioma, idioma)
        for a, v in {"model_id": "scribe_v1", "language_code": cod, "timestamps_granularity": "word", "tag_audio_events": "false"}.items():
            corpo += f"--{lim}\r\nContent-Disposition: form-data; name=\"{a}\"\r\n\r\n{v}\r\n".encode()
        corpo += (f"--{lim}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"voz.wav\"\r\nContent-Type: audio/wav\r\n\r\n".encode()
                  + Path(voz).read_bytes() + f"\r\n--{lim}--\r\n".encode())
        req = urllib.request.Request("https://api.elevenlabs.io/v1/speech-to-text", data=corpo,
                                     headers={"xi-api-key": k, "Content-Type": f"multipart/form-data; boundary={lim}"})
        (pasta / "transcricao_bruta.json").write_bytes(urllib.request.urlopen(req, timeout=1800).read())
        d = json.load(open(pasta / "transcricao_bruta.json", encoding="utf-8"))
        return [{"w": w["text"].strip(), "t": round(w["start"], 3), "f": round(w["end"], 3)}
                for w in d.get("words", []) if w.get("type", "word") == "word" and w.get("text", "").strip()]

    # Tenta faster-whisper primeiro.
    # Captura QUALQUER falha (não só ImportError): download de modelo, CUDA, etc.
    # Sem isso, um erro de download derrubava o script em vez de cair no fallback.
    try:
        import faster_whisper
        return transcreve_faster_whisper(voz, pasta, idioma, modelo_nome)
    except ImportError:
        pass  # pacote ausente mesmo — segue para o fallback abaixo
    except Exception as e:
        print(f"  [Aviso] faster-whisper falhou ({type(e).__name__}: {e}). Tentando Whisper clássico…")

    # Fallback para whisper tradicional da OpenAI.
    # shutil.which("whisper") não acha o .venv/Scripts/whisper.exe se não estiver no PATH,
    # então checamos também o binário da venv atual explicitamente.
    candidatos = [
        shutil.which("whisper"),
        str(RAIZ / ".venv" / "Scripts" / "whisper.exe"),   # Windows
        str(RAIZ / ".venv" / "bin" / "whisper"),           # macOS/Linux
    ]
    exe_whisper = next((c for c in candidatos if c and Path(c).exists()), None)

    if exe_whisper:
        print(f"Transcrevendo com Whisper clássico (modelo {modelo_nome})…")
        sh([exe_whisper, str(voz), "--model", modelo_nome, "--language", idioma, "--word_timestamps", "True",
            "--output_format", "json", "--output_dir", str(pasta)])
        bruto = pasta / (Path(voz).stem + ".json")
        d = json.load(open(bruto, encoding="utf-8"))
        out = [{"w": w["word"].strip(), "t": round(w["start"], 3), "f": round(w["end"], 3)}
               for s in d.get("segments", []) for w in s.get("words", []) if w.get("word", "").strip()]
        return out

    sys.exit("Nenhum motor de transcrição encontrado. Instale: pip install -r requirements.txt")

def roteiro(pal):
    linhas, cur = [], []
    for i, p in enumerate(pal):
        cur.append(p)
        pausa = pal[i + 1]["t"] - p["f"] if i + 1 < len(pal) else 9
        if p["w"][-1:] in ".?!" or pausa > 0.6:
            linhas.append(f'[{cur[0]["t"]:8.2f} – {cur[-1]["f"]:8.2f}]  ' + " ".join(x["w"] for x in cur))
            cur = []
    if cur:
        linhas.append(f'[{cur[0]["t"]:8.2f} – {cur[-1]["f"]:8.2f}]  ' + " ".join(x["w"] for x in cur))
    return "\n".join(linhas) + "\n"

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("gravacao")
    ap.add_argument("projeto")
    ap.add_argument("--modelo", default="large-v3-turbo", help="Modelo Whisper (padrão: large-v3-turbo)")
    ap.add_argument("--idioma", default="pt")
    ap.add_argument("--sem-limpeza", action="store_true", help="Desativa redução de ruído")
    a = ap.parse_args()

    fonte = Path(a.projeto) / "fonte"
    fonte.mkdir(parents=True, exist_ok=True)

    if not (fonte / "video.mp4").exists():
        print("1) Convertendo e padronizando vídeo em 1080p/30 fps...")
        sh([
            "ffmpeg", "-y", "-loglevel", "error", "-i", a.gravacao,
            "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,fps=30",
            "-an", "-c:v", "libx264", "-crf", "16", "-g", "15", "-pix_fmt", "yuv420p",
            str(fonte / "video.mp4")
        ])
    else:
        print("1) video.mp4 já existe em fonte, pulando re-codificação.")

    if not (fonte / "voz.wav").exists():
        print("2) Tratando áudio e isolando voz...")
        trata_e_normaliza_voz(a.gravacao, fonte / "voz.wav", limpar=(not a.sem_limpeza))
    else:
        print("2) voz.wav já existe em fonte, pulando tratamento de áudio.")

    print("3) Transcrevendo com IA...")
    pal = transcreve(fonte / "voz.wav", fonte, a.idioma, a.modelo)
    with open(fonte / "palavras.json", "w", encoding="utf-8") as _f:
        json.dump(pal, _f, ensure_ascii=False, indent=2)
    (fonte / "roteiro.txt").write_text(roteiro(pal), encoding="utf-8")

    print(f"\n[Sucesso] {len(pal)} palavras mapeadas!")
    print(f"Roteiro gerado em: {fonte / 'roteiro.txt'}")
