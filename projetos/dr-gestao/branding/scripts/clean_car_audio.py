import os
import sys
import subprocess
import soundfile as sf
import noisereduce as nr
import numpy as np

def limpar_audio_drgestao(caminho_video=None, output_wav=None):
    aqui = os.path.dirname(os.path.abspath(__file__))
    
    if caminho_video is None:
        # Tenta localizar no diretório brutos ou media/base.mp4
        brutos_dir = os.path.abspath(os.path.join(aqui, "..", "brutos"))
        if os.path.exists(brutos_dir):
            arquivos = [os.path.join(brutos_dir, f) for f in os.listdir(brutos_dir) if f.lower().endswith(('.mp4', '.mov', '.mkv'))]
            if arquivos:
                caminho_video = arquivos[0]
                
        if not caminho_video or not os.path.exists(caminho_video):
            candidato_base = os.path.join(aqui, "media", "base.mp4")
            if os.path.exists(candidato_base):
                caminho_video = candidato_base

    if not caminho_video or not os.path.exists(caminho_video):
        print(f"[ERRO] Vídeo bruto não encontrado. Especifique o arquivo: python clean_car_audio.py <caminho_video.mp4>")
        sys.exit(1)

    if output_wav is None:
        output_wav = os.path.join(aqui, "temp_cleaned.wav")

    temp_raw = os.path.join(aqui, "temp_raw_audio.wav")
    temp_denoised = os.path.join(aqui, "temp_denoised_audio.wav")

    print(f"=== TRATAMENTO ACÚSTICO DR. GESTÃO ===")
    print(f"Origem: {caminho_video}")
    print(f"Destino: {output_wav}")

    print("\n1. Extraindo áudio bruto PCM 48kHz...")
    subprocess.run([
        "ffmpeg", "-y", "-i", caminho_video,
        "-vn", "-acodec", "pcm_s16le", "-ar", "48000", "-ac", "2",
        temp_raw
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    print("2. Aplicando Spectral Gating Denoise (remoção de ruído de motor/asfalto)...")
    data, sr = sf.read(temp_raw)
    # Coleta ruído dos primeiros 0.5s de silêncio
    sample_len = min(int(0.55 * sr), len(data))
    noise_sample = data[int(0.05 * sr):sample_len]

    reduced = nr.reduce_noise(
        y=data.T,
        sr=sr,
        y_noise=noise_sample.T,
        prop_decrease=0.82,
        n_fft=2048,
        win_length=2048,
        hop_length=512,
        stationary=True
    ).T

    sf.write(temp_denoised, reduced, sr)

    print("3. Aplicando High-Pass 80Hz, EQ de cabine, compressão vocal e Loudnorm -14 LUFS...")
    af_chain = (
        "highpass=f=80,"
        "equalizer=f=320:t=q:w=1.2:g=-2.5,"
        "equalizer=f=3000:t=q:w=1.0:g=+2.0,"
        "acompressor=threshold=-18dB:ratio=2.5:attack=10:release=120,"
        "loudnorm=I=-14:TP=-1.0:LRA=7"
    )

    subprocess.run([
        "ffmpeg", "-y", "-i", temp_denoised,
        "-af", af_chain,
        "-acodec", "pcm_s16le", "-ar", "48000", "-ac", "2",
        output_wav
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # Limpeza dos intermediários
    if os.path.exists(temp_raw):
        os.remove(temp_raw)
    if os.path.exists(temp_denoised):
        os.remove(temp_denoised)

    print(f"[OK] Áudio tratado e masterizado com sucesso: {output_wav}\n")
    return output_wav

if __name__ == "__main__":
    vid = sys.argv[1] if len(sys.argv) > 1 else None
    out = sys.argv[2] if len(sys.argv) > 2 else None
    limpar_audio_drgestao(vid, out)
