import os
import math
import numpy as np
from PIL import Image, ImageDraw

AQUI = os.path.dirname(os.path.abspath(__file__))
LOGOS_DIR = os.path.join(AQUI, "logos")
SONS_DIR = os.path.join(AQUI, "sons")
OUT_DIR = os.path.join(AQUI, "overlays", "transicoes")
os.makedirs(OUT_DIR, exist_ok=True)

# Cores da identidade visual Dr. Gestao
AZUL_MARCA = (0, 74, 173, 255)       # #004aad
LILAS_MARCA = (142, 125, 229, 255)   # #8e7de5
CIANO_MARCA = (47, 151, 212, 255)    # #2f97d4
BRANCO = (255, 255, 255, 255)

def gerar_logo_branco():
    logo_path = os.path.join(LOGOS_DIR, "Logo-Texto.png")
    out_path = os.path.join(LOGOS_DIR, "Logo-Texto-Branco.png")
    if os.path.exists(logo_path):
        img = Image.open(logo_path).convert("RGBA")
        r, g, b, a = img.split()
        branco = Image.new("RGBA", img.size, (255, 255, 255, 255))
        branco.putalpha(a)
        branco.save(out_path)
        print(f"[OK] Logo branco gerado: {out_path}")
        return out_path
    return None

def render_diagonal_wipe(w=1920, h=1080, fps=30, dur=0.9, out_base="transicao_wipe_drgestao_16x9"):
    total_frames = int(fps * dur)
    temp_frames_dir = os.path.join(OUT_DIR, f"temp_{out_base}")
    os.makedirs(temp_frames_dir, exist_ok=True)
    
    logo_branco_path = os.path.join(LOGOS_DIR, "Logo-Texto-Branco.png")
    logo_img = None
    if os.path.exists(logo_branco_path):
        logo_img = Image.open(logo_branco_path).convert("RGBA")
        lw = int(w * 0.16)
        lh = int(logo_img.height * (lw / logo_img.width))
        logo_img = logo_img.resize((lw, lh), Image.Resampling.LANCZOS)

    # Parametros da diagonal: inclinacao 45 graus (vetor normal unitario: nx, ny)
    # Linha: x + y = D
    # Diagonal vai de x+y = 0 ate x+y = w+h
    diag_total = w + h
    largura_lilas = int(w * 0.18)
    largura_borda = 6
    
    print(f"Gerando {total_frames} frames para {out_base} ({w}x{h})...")
    
    for f in range(total_frames):
        t = f / (total_frames - 1)
        
        # Progresso com curva suave de transicao
        # Entrada: 0.0 a 0.44 (cobre a tela)
        # Seguro (100% opaco): 0.44 a 0.52 (momento ideal para corte seco por baixo)
        # Saida: 0.52 a 1.0 (revela o novo video)
        
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        if t < 0.44:
            # Onda entrando do canto superior direito (x+y maior) em direcao ao inferior esquerdo
            # Ou do canto esquerdo superior (x+y = 0) em direcao a x+y = diag_total
            # Na referencia: faixa diagonal varre da direita/topo para esquerda/baixo
            p = t / 0.44
            # ease-in-out
            p_e = 0.5 - 0.5 * math.cos(math.pi * p)
            # D_lead percorre de -largura_lilas ate diag_total
            D_lead = p_e * (diag_total + largura_lilas)
            
            # Poligono azul (atras do lilas)
            # x + y <= D_lead - largura_lilas
            D_azul = D_lead - largura_lilas
            if D_azul > 0:
                draw.polygon([(0, 0), (min(w, D_azul), 0), (0, min(h, D_azul))], fill=AZUL_MARCA)
                if D_azul > w:
                    draw.polygon([(w, 0), (w, min(h, D_azul - w)), (min(w, D_azul), 0)], fill=AZUL_MARCA)
                if D_azul > h:
                    draw.polygon([(0, h), (min(w, D_azul - h), h), (0, min(h, D_azul))], fill=AZUL_MARCA)
                # simplificado desenhando pontos diagonais
                poly_pts = []
                pts = [(0, 0)]
                if D_azul < w: pts.append((D_azul, 0))
                else: pts.extend([(w, 0), (w, min(h, D_azul - w))])
                if D_azul < h: pts.append((0, D_azul))
                else: pts.extend([(min(w, D_azul - h), h), (0, h)])
                # preenchimento via imagem composta
            
            # Mais facil e perfeitamente anti-aliased: numpy meshgrid
            pass
        
        # Implementacao vetorial limpa com NumPy para velocidade e perfeicao
        X, Y = np.meshgrid(np.arange(w), np.arange(h))
        # Projetar ao longo da diagonal normalizada (canto sup-esq para inf-dir ou sup-dir para inf-esq)
        # Na referencia analisada (t_11, t_12, t_13):
        # A linha vai de canto superior-esquerdo para inferior-direito (inclinacao negativa: Y = X + c ou X + Y = c)
        # t_11: topo-esquerdo e inferior-direito cobertos por lilas, o centro ainda mostra o apresentador.
        # Linha diagonal: x + y
        DIST = X + Y
        
        # Curva de avanço
        # Frente de corte 1 (entrada):
        # Vai de 0 ate diag_total
        # Frente de corte 2 (saida):
        # Segue atras de 0 ate diag_total
        
        # Mapeamento do tempo t em [0, 1]:
        # t_in: 0 a 0.50 (vai de -300 a diag_total + 300)
        # t_out: 0.50 a 1.0 (vai de -300 a diag_total + 300)
        
        # Funcao de easing bezier rapida
        def ease(val):
            return 0.5 - 0.5 * math.cos(math.pi * max(0.0, min(1.0, val)))
        
        band_w = int(diag_total * 0.16)
        border_w = 6
        
        d_lead = ease(t / 0.52) * (diag_total + band_w + border_w) if t <= 0.52 else (diag_total + band_w + border_w)
        d_trail = ease((t - 0.48) / 0.52) * (diag_total + band_w + border_w) if t >= 0.48 else 0
        
        # Mascara do que esta coberto
        # coberto entre d_trail e d_lead
        rgba = np.zeros((h, w, 4), dtype=np.uint8)
        
        # Regiao coberta geral
        mask_active = (DIST >= d_trail) & (DIST <= d_lead)
        
        if np.any(mask_active):
            # 1. Borda ciano lider
            mask_border_lead = (DIST >= d_lead - border_w) & (DIST <= d_lead)
            # 2. Faixa lilas lider
            mask_lilas_lead = (DIST >= d_lead - band_w) & (DIST < d_lead - border_w)
            
            # 3. Borda ciano na cauda
            mask_border_trail = (DIST >= d_trail) & (DIST <= d_trail + border_w)
            # 4. Faixa lilas na cauda
            mask_lilas_trail = (DIST > d_trail + border_w) & (DIST <= d_trail + band_w)
            
            # 5. Miolo azul solido
            mask_azul = mask_active & ~(mask_border_lead | mask_lilas_lead | mask_border_trail | mask_lilas_trail)
            
            rgba[mask_active] = AZUL_MARCA
            rgba[mask_lilas_lead] = LILAS_MARCA
            rgba[mask_lilas_trail] = LILAS_MARCA
            rgba[mask_border_lead] = CIANO_MARCA
            rgba[mask_border_trail] = CIANO_MARCA
            rgba[mask_azul] = AZUL_MARCA
        
        frame_img = Image.fromarray(rgba, mode="RGBA")
        
        # Logo no canto inferior direito quando a tela estiver coberta (entre t=0.3 e t=0.7)
        if logo_img and t >= 0.30 and t <= 0.70:
            # Opacidade do logo
            logo_alpha = 1.0
            if t < 0.42:
                logo_alpha = (t - 0.30) / 0.12
            elif t > 0.58:
                logo_alpha = (0.70 - t) / 0.12
            
            lx = w - logo_img.width - int(w * 0.05)
            ly = h - logo_img.height - int(h * 0.06)
            
            cur_logo = logo_img.copy()
            if logo_alpha < 0.98:
                la = np.array(cur_logo)[:, :, 3]
                la = (la * logo_alpha).astype(np.uint8)
                cur_logo.putalpha(Image.fromarray(la))
            
            frame_img.alpha_composite(cur_logo, (lx, ly))
            
        frame_path = os.path.join(temp_frames_dir, f"f_{f:03d}.png")
        frame_img.save(frame_path)
    
    print(f"Frames salvos. Renderizando videos finais com FFmpeg...")
    
    # 1. MOV ProRes 4444 com canal alfa
    mov_out = os.path.join(OUT_DIR, f"{out_base}.mov")
    # 2. WEBM VP9 com canal alfa
    webm_out = os.path.join(OUT_DIR, f"{out_base}.webm")
    
    # Efeito sonoro swoosh
    swoosh_wav = os.path.join(SONS_DIR, "whoosh_curto.wav")
    has_audio = os.path.exists(swoosh_wav)
    
    # Render MOV ProRes 4444 com canal alfa
    cmd_mov = (
        f'ffmpeg -y -framerate {fps} -i "{temp_frames_dir}/f_%03d.png" '
        + (f'-i "{swoosh_wav}" -c:a aac -b:a 192k ' if has_audio else '')
        + f'-c:v prores_ks -profile:v 4 -pix_fmt yuva444p10le "{mov_out}"'
    )
    os.system(cmd_mov)
    
    # Render WebM VP9 com canal alfa (audio libopus)
    cmd_webm = (
        f'ffmpeg -y -framerate {fps} -i "{temp_frames_dir}/f_%03d.png" '
        + (f'-i "{swoosh_wav}" -c:a libopus -b:a 128k ' if has_audio else '')
        + f'-c:v libvpx-vp9 -pix_fmt yuva420p -b:v 3M -auto-alt-ref 0 "{webm_out}"'
    )
    os.system(cmd_webm)
    
    # Limpeza de frames temporarios
    for f_file in os.listdir(temp_frames_dir):
        os.remove(os.path.join(temp_frames_dir, f_file))
    os.rmdir(temp_frames_dir)
    
    print(f"[CONCLUIDO] Transicoes geradas com sucesso:")
    print(f"  - {mov_out}")
    print(f"  - {webm_out}")

if __name__ == "__main__":
    gerar_logo_branco()
    # 16:9 Landscape (YouTube)
    render_diagonal_wipe(w=1920, h=1080, fps=30, dur=0.9, out_base="transicao_wipe_drgestao_16x9")
    # 9:16 Vertical (Shorts / Reels)
    render_diagonal_wipe(w=1080, h=1920, fps=30, dur=0.9, out_base="transicao_wipe_drgestao_9x16")
