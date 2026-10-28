import subprocess
import os

ref_dir = r"d:\Drifit\Editor\projetos\dr-gestao\branding\referencias"
frames_dir = os.path.join(ref_dir, "analise_frames")
os.makedirs(frames_dir, exist_ok=True)

vid1 = os.path.join(ref_dir, "ref01_Vyexi-lzyhc.mp4")
vid2 = os.path.join(ref_dir, "ref02_ybgjJzzsUFE.mp4")

# Extract 12 keyframes across Video 1 (every 20s)
for t in [2, 10, 25, 45, 70, 95, 120, 150, 180, 210, 240, 260]:
    out_img = os.path.join(frames_dir, f"v1_{t:03d}s.jpg")
    subprocess.run([
        "ffmpeg", "-y", "-ss", str(t), "-i", vid1,
        "-vframes", "1", "-vf", "scale=960:540",
        out_img
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

# Extract 10 keyframes across Video 2 (every 20s)
for t in [2, 8, 20, 40, 65, 90, 115, 140, 165, 185]:
    out_img = os.path.join(frames_dir, f"v2_{t:03d}s.jpg")
    subprocess.run([
        "ffmpeg", "-y", "-ss", str(t), "-i", vid2,
        "-vframes", "1", "-vf", "scale=960:540",
        out_img
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

print("Frames extracted to:", frames_dir)
