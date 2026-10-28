import subprocess
import os
import time

ep_dir = r"d:\Drifit\Editor\EP-00"
proj_dir = r"d:\Drifit\Editor\projetos\EP-00"
raw_video = os.path.join(ep_dir, "20260823_203211.mp4")
intro_vinheta = os.path.join(ep_dir, "Intro-Dr-Gestao.mp4")
cleaned_audio = os.path.join(ep_dir, "temp_cleaned.wav")
hook_overlay = os.path.join(ep_dir, "overlays", "hook_vendas.png")
speech_overlay = os.path.join(ep_dir, "overlays", "speech_vendas.png")

part1_mp4 = os.path.join(ep_dir, "part1_hook.mp4")
part2_mp4 = os.path.join(ep_dir, "part2_speech.mp4")
part3_mp4 = os.path.join(ep_dir, "part3_vinheta.mp4")
intro_full_mp4 = os.path.join(ep_dir, "intro_completa.mp4")

final_main_mp4 = os.path.join(proj_dir, "renders", "final.mp4")
final_complete_proj = os.path.join(proj_dir, "renders", "final_completo.mp4")
final_complete_ep00 = os.path.join(ep_dir, "EP00_final_completo.mp4")

# 1. Part 1 (Hook - 2.25s)
print("=== 1. Rendering Part 1: Hook (2.25s) ===")
cmd_part1 = [
    "ffmpeg", "-y",
    "-ss", "7.40", "-t", "2.25", "-i", raw_video,
    "-ss", "7.40", "-t", "2.25", "-i", cleaned_audio,
    "-loop", "1", "-t", "2.25", "-i", hook_overlay,
    "-filter_complex",
    "[0:v]scale=1920:1080:flags=bicubic,fps=30[bg];"
    "[2:v]format=rgba,fade=t=in:st=0.3:d=0.25:alpha=1[ov];"
    "[bg][ov]overlay=0:0[vout];"
    "[1:a]afade=t=in:st=0:d=0.03,afade=t=out:st=2.22:d=0.03[aout]",
    "-map", "[vout]", "-map", "[aout]",
    "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p",
    "-c:a", "aac", "-b:a", "256k", "-ar", "48000",
    "-t", "2.25",
    part1_mp4
]
subprocess.run(cmd_part1, check=True)
print("Part 1 finished.")

# 2. Part 2 (Speech - 28.32s)
print("=== 2. Rendering Part 2: Fala do Carro (28.32s) ===")
cmd_part2 = [
    "ffmpeg", "-y",
    "-ss", "0.60", "-t", "28.32", "-i", raw_video,
    "-ss", "0.60", "-t", "28.32", "-i", cleaned_audio,
    "-loop", "1", "-t", "28.32", "-i", speech_overlay,
    "-filter_complex",
    "[0:v]scale=1920:1080:flags=bicubic,fps=30[bg];"
    "[2:v]format=rgba,fade=t=in:st=6.80:d=0.25:alpha=1,fade=t=out:st=9.10:d=0.25:alpha=1[ov];"
    "[bg][ov]overlay=0:0:enable='between(t,6.80,9.40)'[vout];"
    "[1:a]afade=t=in:st=0:d=0.03,afade=t=out:st=28.29:d=0.03[aout]",
    "-map", "[vout]", "-map", "[aout]",
    "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p",
    "-c:a", "aac", "-b:a", "256k", "-ar", "48000",
    "-t", "28.32",
    part2_mp4
]
subprocess.run(cmd_part2, check=True)
print("Part 2 finished.")

# 3. Part 3 (Vinheta - 7.87s)
print("=== 3. Rendering Part 3: Vinheta Dr. Gestão (7.87s) ===")
cmd_part3 = [
    "ffmpeg", "-y",
    "-i", intro_vinheta,
    "-filter_complex",
    "[0:v]scale=1920:1080:flags=bicubic,fps=30[vout];"
    "[0:a]loudnorm=I=-14:TP=-1.0:LRA=7,aformat=sample_rates=48000:channel_layouts=stereo[aout]",
    "-map", "[vout]", "-map", "[aout]",
    "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p",
    "-c:a", "aac", "-b:a", "256k", "-ar", "48000",
    part3_mp4
]
subprocess.run(cmd_part3, check=True)
print("Part 3 finished.")

# 4. Concatenate Intro
print("=== 4. Concatenating Parts 1, 2, 3 into intro_completa.mp4 ===")
concat_intro_txt = os.path.join(ep_dir, "concat_intro.txt")
with open(concat_intro_txt, "w", encoding="utf-8") as f:
    f.write(f"file '{part1_mp4}'\n")
    f.write(f"file '{part2_mp4}'\n")
    f.write(f"file '{part3_mp4}'\n")

cmd_concat_intro = [
    "ffmpeg", "-y",
    "-f", "concat", "-safe", "0", "-i", concat_intro_txt,
    "-c", "copy",
    intro_full_mp4
]
subprocess.run(cmd_concat_intro, check=True)
print("Intro complete created successfully.")

# 5. Concatenate Intro + Final Main Video
print("=== 5. Merging Intro + Main Video into final_completo.mp4 ===")
concat_all_txt = os.path.join(ep_dir, "concat_all.txt")
with open(concat_all_txt, "w", encoding="utf-8") as f:
    f.write(f"file '{intro_full_mp4}'\n")
    f.write(f"file '{final_main_mp4}'\n")

cmd_concat_all = [
    "ffmpeg", "-y",
    "-f", "concat", "-safe", "0", "-i", concat_all_txt,
    "-c", "copy",
    final_complete_ep00
]
subprocess.run(cmd_concat_all, check=True)

# Also copy/save to renders/final_completo.mp4
import shutil
shutil.copy2(final_complete_ep00, final_complete_proj)
print(f"Full episode rendered to:\n- {final_complete_ep00}\n- {final_complete_proj}")
