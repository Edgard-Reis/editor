import subprocess
import os

ref_dir = r"d:\Drifit\Editor\projetos\dr-gestao\branding\referencias"
frames_dir = os.path.join(ref_dir, "analise_motions")
os.makedirs(frames_dir, exist_ok=True)

vid1 = os.path.join(ref_dir, "ref_motion01_16x9.mp4")
vid2 = os.path.join(ref_dir, "ref_motion02_shorts.mp4")

# Extract 12 frames across 0s - 62s of Video 1
for t in [2, 6, 12, 18, 24, 30, 36, 42, 48, 54, 58, 61]:
    out_img = os.path.join(frames_dir, f"m1_{t:02d}s.jpg")
    subprocess.run([
        "ffmpeg", "-y", "-ss", str(t), "-i", vid1,
        "-vframes", "1", "-vf", "scale=960:540",
        out_img
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

# Extract 10 frames across Video 2 (Shorts)
for t in [1, 4, 8, 12, 16, 20, 24, 28, 32, 36]:
    out_img = os.path.join(frames_dir, f"m2_short_{t:02d}s.jpg")
    subprocess.run([
        "ffmpeg", "-y", "-ss", str(t), "-i", vid2,
        "-vframes", "1", "-vf", "scale=540:960",
        out_img
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

print("Motion frames extracted to:", frames_dir)
