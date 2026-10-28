import os
import subprocess
from PIL import Image

svg_path = r"d:\Drifit\Editor\projetos\dr-gestao\branding\logos\Logo-Branco.svg"
png_path = r"d:\Drifit\Editor\projetos\dr-gestao\branding\logos\Logo-Branco.png"

# Check edge paths
edge_paths = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"
]

edge_exe = next((p for p in edge_paths if os.path.exists(p)), None)
print(f"Edge exe: {edge_exe}")

if edge_exe:
    # Use headless Edge with screenshot
    html_content = f"""<!DOCTYPE html>
<html>
<head>
<style>
  body {{
    margin: 0;
    padding: 0;
    background: transparent;
    overflow: hidden;
  }}
  img {{
    width: 1080px;
    height: 1080px;
    display: block;
  }}
</style>
</head>
<body>
  <img src="file:///{svg_path.replace(os.sep, '/')}" />
</body>
</html>"""
    html_path = r"d:\Drifit\Editor\projetos\dr-gestao\branding\logos\temp_render.html"
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    raw_png = r"d:\Drifit\Editor\projetos\dr-gestao\branding\logos\temp_raw.png"
    cmd = [
        edge_exe,
        "--headless",
        "--disable-gpu",
        "--default-background-color=00000000",
        "--window-size=1080,1080",
        f"--screenshot={raw_png}",
        html_path
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    print("Edge run:", res.returncode)
    if os.path.exists(raw_png):
        img = Image.open(raw_png).convert("RGBA")
        bbox = img.getbbox()
        print("Raw size:", img.size, "BBox:", bbox)
        # Crop tight with some padding or keep as needed
        img.save(png_path)
        print("Saved Logo-Branco.png!")
        os.remove(html_path)
        os.remove(raw_png)
