import os
import sys
import json
import math
import shutil
import subprocess
import argparse
import numpy as np
import soundfile as sf
from PIL import Image, ImageDraw, ImageFont

AQUI = os.path.dirname(os.path.abspath(__file__))
BASE_MP4 = os.path.join(AQUI, "media", "base.mp4")
VOZ_WAV = os.path.join(AQUI, "media", "voz.wav")
PAL_JSON = os.path.join(AQUI, "media", "palavras_saida.json")
LOGOS_DIR = os.path.join(AQUI, "logos")
SONS_DIR = r"d:\Drifit\Editor\vortex-edicao\sons\kit"
OUTRO_MP4 = r"d:\Drifit\Editor\projetos\dr-gestao\branding\overlays\outro_drgestao_shorts_30fps.mp4"
BRAND_LOGOS_DIR = r"d:\Drifit\Editor\projetos\dr-gestao\branding\logos"
OUT_DIR = os.path.join(AQUI, "..", "renders", "cortes_9_16")
os.makedirs(OUT_DIR, exist_ok=True)

FPS = 30
W, H = 1080, 1920

# 1. Carregar Transcrição Geral
with open(PAL_JSON, "r", encoding="utf-8") as f:
    TODAS_PALAVRAS = json.load(f)

# 2. Fontes
font_path_b = "C:\\Windows\\Fonts\\segoeuib.ttf"
font_path_r = "C:\\Windows\\Fonts\\segoeui.ttf"
font_badge = ImageFont.truetype(font_path_b, 24)
font_card_tit = ImageFont.truetype(font_path_b, 46)
font_card_sub = ImageFont.truetype(font_path_r, 28)
font_card_lead = ImageFont.truetype(font_path_b, 28)
font_card_item = ImageFont.truetype(font_path_r, 30)
font_card_item_b = ImageFont.truetype(font_path_b, 30)
font_caption = ImageFont.truetype(font_path_b, 48)
font_caption_hl = ImageFont.truetype(font_path_b, 52)
font_meta = ImageFont.truetype(font_path_b, 22)
font_counter = ImageFont.truetype(font_path_b, 56)

# 3. Logo Oficial Branco
logo_branco_path = os.path.join(LOGOS_DIR, "Logo-Branco.png")
logo_img = None
if os.path.exists(logo_branco_path):
    lg = Image.open(logo_branco_path).convert("RGBA")
    lw = 230
    lh = int(lg.height * (lw / lg.width))
    logo_img = lg.resize((lw, lh), Image.Resampling.LANCZOS)

# 4. Logos de Marketplaces para o Corte 03
mkt_logos = {}
for name in ["mercado-livre", "shopee", "shein"]:
    p = os.path.join(BRAND_LOGOS_DIR, f"{name}.png")
    if os.path.exists(p):
        im = Image.open(p).convert("RGBA")
        mkt_logos[name] = im

# 5. Background Base da Zona Superior (Gradiente Escuro Dr. Gestão)
bg_topo = np.zeros((H, W, 4), dtype=np.uint8)
bg_topo[:, :] = [10, 14, 26, 255]
Y_grid, X_grid = np.ogrid[:980, :W]
dist_topo = np.sqrt((X_grid - 540)**2 + (Y_grid - 300)**2)
r = np.clip(16 + (30 - dist_topo * 0.03), 10, 40).astype(np.uint8)
g = np.clip(24 + (45 - dist_topo * 0.04), 14, 60).astype(np.uint8)
b = np.clip(45 + (85 - dist_topo * 0.07), 26, 110).astype(np.uint8)
bg_topo[:980, :, 0] = r
bg_topo[:980, :, 1] = g
bg_topo[:980, :, 2] = b
bg_topo_img = Image.fromarray(bg_topo, mode="RGBA")

# Máscara dos cantos da câmera
mask_cam = Image.new("L", (1080, 940), 0)
mask_draw = ImageDraw.Draw(mask_cam)
mask_draw.rounded_rectangle([0, 0, 1080, 940], radius=36, fill=255)

# Helper animação de entrada de itens
def calc_item_anim(t_rel, t_appear, dur=0.35, slide_dx=-25, slide_dy=0):
    if t_rel < t_appear:
        return 0.0, slide_dx, slide_dy
    p = min(1.0, (t_rel - t_appear) / dur)
    ease = 1.0 - (1.0 - p)**3
    dx = int(slide_dx * (1.0 - ease))
    dy = int(slide_dy * (1.0 - ease))
    return ease, dx, dy

# Helper ícone vetorial de checkmark esmeralda
def draw_vector_check(draw_ctx, x, y, anim_val):
    draw_ctx.ellipse([x, y+4, x+28, y+32], fill=(16, 185, 129, int(255*anim_val)))
    draw_ctx.line([x+8, y+18, x+13, y+24], fill=(255, 255, 255, int(255*anim_val)), width=3)
    draw_ctx.line([x+13, y+24, x+22, y+12], fill=(255, 255, 255, int(255*anim_val)), width=3)

# Helper badge de alerta com exclamação
def draw_alert_badge(draw_ctx, x, y, anim_val):
    draw_ctx.ellipse([x, y+4, x+28, y+32], fill=(235, 30, 60, int(255*anim_val)))
    draw_ctx.text([x+11, y+3], "!", fill=(255, 255, 255, int(255*anim_val)), font=font_badge)

# Configurações completas dos cortes 01 a 07
CONFIG_CORTES = {
    1: {
        "arquivo": "EP00_corte_01_problema_vendas_minutagem.mp4",
        "tema": "Problema de Vendas e Alta Minutagem",
        "t_ini": 10.70, "t_fim": 42.70,
        "badge_topo": "DIAGNÓSTICO FABRIL",
        "cards": [
            {
                "t_ini": 0.0, "t_fim": 6.5,
                "badge": "MERCADO TÊXTIL", "tit": "VENDAS TRAVADAS?",
                "sub": "A sensação de trabalhar muito e a venda não sair",
                "stepper_idx": 0
            },
            {
                "t_ini": 6.5, "t_fim": 19.0,
                "badge": "DIAGNÓSTICO REAL", "tit": "MINUTAGEM ALTA",
                "sub": "O gargalo invisível que destrói a margem",
                "lead": "O que acontece na produção:",
                "bullets": [
                    "Produtos que demoram demais na esteira",
                    "Complexidade excessiva de costura",
                    "Gargalo que derruba a margem líquida"
                ],
                "stepper_idx": 1
            },
            {
                "t_ini": 19.0, "t_fim": 31.8,
                "badge": "O CAMINHO 2026", "tit": "ESTRUTURA ENXUTA",
                "sub": "O novo jogo da confecção lucrativa",
                "lead": "Metodologia Dr. Gestão:",
                "checks": [
                    "1. Minerar produtos de alta demanda",
                    "2. Modelagem rápida e repetível",
                    "3. Venda direta sem intermediários"
                ],
                "stepper_idx": 2
            }
        ],
        "steppers": ["01. TRAVA", "02. GARGALO", "03. VIRADA"],
        "sfx_triggers": [
            ("whoosh_curto.wav", 0.00, 0.35), ("clique2.wav", 0.15, 0.28),
            ("swish.wav", 6.15, 0.30),
            ("whoosh_curto.wav", 6.50, 0.35), ("clique2.wav", 6.65, 0.28),
            ("check.wav", 7.60, 0.24), ("check.wav", 8.30, 0.24), ("check.wav", 9.00, 0.24),
            ("swish.wav", 18.65, 0.30),
            ("whoosh_curto.wav", 19.00, 0.35), ("clique2.wav", 19.15, 0.28),
            ("check.wav", 20.10, 0.24), ("check.wav", 20.80, 0.24), ("check.wav", 21.50, 0.24),
            ("swish.wav", 31.45, 0.30)
        ]
    },
    2: {
        "arquivo": "EP00_corte_02_dinheiro_na_mesa.mp4",
        "tema": "Deixando Dinheiro na Mesa",
        "t_ini": 56.90, "t_fim": 81.30,
        "badge_topo": "OPORTUNIDADE 2026",
        "cards": [
            {
                "t_ini": 0.0, "t_fim": 11.5,
                "badge": "CHÃO DE FÁBRICA", "tit": "DINHEIRO NA MESA",
                "sub": "O empresário tradicional está perdendo margem",
                "lead": "A transformação obrigatória até 2027:",
                "bullets": [
                    "Estruturas pesadas com giro lento",
                    "Margem corroída por custos fixos",
                    "Resistência aos novos canais de venda"
                ],
                "stepper_idx": 0
            },
            {
                "t_ini": 11.5, "t_fim": 24.0,
                "badge": "PLANO DE AÇÃO", "tit": "O NOVO MODELO",
                "sub": "Os 3 passos para destravar o faturamento",
                "lead": "Metodologia Dr. Gestão aplicada:",
                "checks": [
                    "1. MINERAR: Alta demanda e baixa minutagem",
                    "2. VALIDAR: Giro rápido sem estoque encalhado",
                    "3. VENDER: Margem líquida real direto no canal"
                ],
                "stepper_idx": 1
            }
        ],
        "steppers": ["01. DIAGNÓSTICO", "02. MINERAR", "03. ESCALAR"],
        "sfx_triggers": [
            ("whoosh_curto.wav", 0.00, 0.35), ("clique2.wav", 0.15, 0.28),
            ("check.wav", 1.10, 0.24), ("check.wav", 1.70, 0.24), ("check.wav", 2.30, 0.24),
            ("swish.wav", 11.15, 0.30),
            ("whoosh_curto.wav", 11.50, 0.35), ("clique2.wav", 11.65, 0.28),
            ("check.wav", 12.60, 0.24), ("check.wav", 13.30, 0.24), ("check.wav", 14.00, 0.24),
            ("swish.wav", 23.65, 0.30)
        ]
    },
    3: {
        "arquivo": "EP00_corte_03_virada_marketplaces.mp4",
        "tema": "Virada de Chave nos Marketplaces",
        "t_ini": 78.00, "t_fim": 103.50,
        "badge_topo": "CANAL DE ESCALA",
        "cards": [
            {
                "t_ini": 0.0, "t_fim": 12.5,
                "badge": "ECOSSISTEMA 2026", "tit": "A GRANDE VIRADA",
                "sub": "Onde o consumidor têxtil está comprando agora",
                "tipo_especial": "marketplaces",
                "stepper_idx": 0
            },
            {
                "t_ini": 12.5, "t_fim": 25.1,
                "badge": "RESULTADO PRÁTICO", "tit": "TRAÇÃO DIRETA",
                "sub": "Confecções que saíram da estagnação",
                "lead": "O que muda com a venda direta:",
                "checks": [
                    "Recebimento rápido sem depender de prazo",
                    "Previsibilidade de caixa semana a semana",
                    "Adequação total à legislação tributária 2026/27"
                ],
                "stepper_idx": 2
            }
        ],
        "steppers": ["01. CANAIS", "02. LOGÍSTICA", "03. VOLUME"],
        "sfx_triggers": [
            ("whoosh_curto.wav", 0.00, 0.35), ("clique2.wav", 0.15, 0.28),
            ("check.wav", 1.10, 0.24), ("check.wav", 1.80, 0.24), ("check.wav", 2.50, 0.24),
            ("swish.wav", 12.15, 0.30),
            ("whoosh_curto.wav", 12.50, 0.35), ("clique2.wav", 12.65, 0.28),
            ("check.wav", 13.60, 0.24), ("check.wav", 14.30, 0.24), ("check.wav", 15.00, 0.24),
            ("swish.wav", 24.75, 0.30)
        ]
    },
    4: {
        "arquivo": "EP00_corte_04_ilusao_do_milhao.mp4",
        "tema": "A Ilusão do Milhão Fácil",
        "t_ini": 103.50, "t_fim": 125.00,
        "badge_topo": "SEM ILUSÃO",
        "cards": [
            {
                "t_ini": 0.0, "t_fim": 10.5,
                "badge": "ALERTA DE MERCADO", "tit": "A ILUSÃO DO MILHÃO",
                "sub": "Não existe mágica da noite para o dia",
                "lead": "A armadilha dos falsos atalhos:",
                "alerta": "Promessa fácil destrói indústrias sérias",
                "bullets": [
                    "Ilusão de faturamento gigante sem margem",
                    "Endividamento com maquinário desnecessário",
                    "Estrutura pesada antes de validar a venda"
                ],
                "stepper_idx": 0
            },
            {
                "t_ini": 10.5, "t_fim": 21.1,
                "badge": "GESTÃO RESPONSÁVEL", "tit": "PÉ NO CHÃO",
                "sub": "Crescimento sustentável e lucrativo",
                "lead": "O caminho de quem constrói patrimônio:",
                "checks": [
                    "Custos fixos controlados no centavo",
                    "Minutagem enxuta com equipe motivada",
                    "Escala progressiva baseada em margem real"
                ],
                "stepper_idx": 2
            }
        ],
        "steppers": ["01. REALIDADE", "02. DISCIPLINA", "03. RESULTADO"],
        "sfx_triggers": [
            ("whoosh_curto.wav", 0.00, 0.35), ("clique2.wav", 0.15, 0.28),
            ("check.wav", 1.10, 0.24), ("check.wav", 1.70, 0.24), ("check.wav", 2.30, 0.24),
            ("swish.wav", 10.15, 0.30),
            ("whoosh_curto.wav", 10.50, 0.35), ("clique2.wav", 10.65, 0.28),
            ("check.wav", 11.60, 0.24), ("check.wav", 12.30, 0.24), ("check.wav", 13.00, 0.24),
            ("swish.wav", 20.75, 0.30)
        ]
    },
    5: {
        "arquivo": "EP00_corte_05_faturamento_400k_enxuto.mp4",
        "tema": "Faturando 400k com Estrutura Pequena",
        "t_ini": 124.90, "t_fim": 148.00,
        "badge_topo": "CASOS REAIS",
        "cards": [
            {
                "t_ini": 0.0, "t_fim": 11.5,
                "badge": "ESTRUTURA ENXUTA", "tit": "300K A 500K / MÊS",
                "sub": "Pequenas confecções com resultados gigantes",
                "tipo_especial": "contador_escala",
                "lead": "Sem galpão de 1000m² e sem máquinas paradas",
                "stepper_idx": 0
            },
            {
                "t_ini": 11.5, "t_fim": 22.7,
                "badge": "BLINDAGEM FABRIL", "tit": "ATENÇÃO TRIBUTÁRIA",
                "sub": "A transição 2026/2027 exige planejamento",
                "lead": "O segredo para não quebrar na virada:",
                "checks": [
                    "Adequação fiscal antes da reforma consolidar",
                    "Separação rigorosa entre faturamento e caixa",
                    "Giro rápido sem capital empatado em estoque"
                ],
                "stepper_idx": 1
            }
        ],
        "steppers": ["01. ENXUTO", "02. CONTROLE", "03. ESCALA"],
        "sfx_triggers": [
            ("whoosh_curto.wav", 0.00, 0.35), ("clique2.wav", 0.15, 0.28),
            ("check.wav", 1.20, 0.24), ("check.wav", 2.20, 0.24),
            ("swish.wav", 11.15, 0.30),
            ("whoosh_curto.wav", 11.50, 0.35), ("clique2.wav", 11.65, 0.28),
            ("check.wav", 12.60, 0.24), ("check.wav", 13.30, 0.24), ("check.wav", 14.00, 0.24),
            ("swish.wav", 22.35, 0.30)
        ]
    },
    6: {
        "arquivo": "EP00_corte_06_lucro_vs_faturamento.mp4",
        "tema": "Faturamento vs Lucro Real",
        "t_ini": 201.50, "t_fim": 223.00,
        "badge_topo": "PONTO CRÍTICO",
        "cards": [
            {
                "t_ini": 0.0, "t_fim": 10.5,
                "badge": "O GRANDE ENGANO", "tit": "FATURAMENTO ≠ LUCRO",
                "sub": "Trabalhar muito e sobrar nada no fim do mês",
                "lead": "O que acontece na fábrica tradicional:",
                "bullets": [
                    "Fábrica cheia e caixa no vermelho",
                    "Peças com alta minutagem sem precificação",
                    "Falso faturamento que só alimenta custo fixo"
                ],
                "stepper_idx": 0
            },
            {
                "t_ini": 10.5, "t_fim": 21.1,
                "badge": "GESTÃO INTELIGENTE", "tit": "LUCRO NO BOLSO",
                "sub": "Faturar menos com mais margem ou escalar certo",
                "lead": "A equação que dá lucro de verdade:",
                "checks": [
                    "Redução de minutagem = Mais peças/hora",
                    "Corte de gargalos ocultos no chão de fábrica",
                    "Margem líquida de 15% a 25% garantida no bolso"
                ],
                "stepper_idx": 2
            }
        ],
        "steppers": ["01. SINTOMA", "02. CORREÇÃO", "03. LUCRO"],
        "sfx_triggers": [
            ("whoosh_curto.wav", 0.00, 0.35), ("clique2.wav", 0.15, 0.28),
            ("check.wav", 1.10, 0.24), ("check.wav", 1.70, 0.24), ("check.wav", 2.30, 0.24),
            ("swish.wav", 10.15, 0.30),
            ("whoosh_curto.wav", 10.50, 0.35), ("clique2.wav", 10.65, 0.28),
            ("check.wav", 11.60, 0.24), ("check.wav", 12.30, 0.24), ("check.wav", 13.00, 0.24),
            ("swish.wav", 20.75, 0.30)
        ]
    },
    7: {
        "arquivo": "EP00_corte_07_bastidores_campo_batalha.mp4",
        "tema": "29 Anos no Campo de Batalha",
        "t_ini": 0.00, "t_fim": 24.00,
        "badge_topo": "EXPERIÊNCIA PRÁTICA",
        "cards": [
            {
                "t_ini": 0.0, "t_fim": 11.5,
                "badge": "AUTORIDADE FABRIL", "tit": "LUIZ ROBERTO SARAIVA",
                "sub": "29 anos vivendo o chão de fábrica todos os dias",
                "lead": "O Dr. Gestão na prática:",
                "bullets": [
                    "Consultoria direto na linha de produção",
                    "Recuperação de confecções em crise",
                    "Transformação de modelos arcaicos em lucrativos"
                ],
                "stepper_idx": 0
            },
            {
                "t_ini": 11.5, "t_fim": 23.6,
                "badge": "CONVITE EXCLUSIVO", "tit": "CAMPO DE BATALHA",
                "sub": "Aprenda o método testado na vida real",
                "lead": "O que você vai encontrar no canal:",
                "checks": [
                    "Diagnósticos reais sem teoria de gabinete",
                    "Estratégias de corte, costura e comercial",
                    "Orientação para a virada fabril 2026/2027"
                ],
                "stepper_idx": 1
            }
        ],
        "steppers": ["01. HISTÓRIA", "02. PRÁTICA", "03. RESULTADO"],
        "sfx_triggers": [
            ("whoosh_curto.wav", 0.00, 0.35), ("clique2.wav", 0.15, 0.28),
            ("check.wav", 1.10, 0.24), ("check.wav", 1.70, 0.24), ("check.wav", 2.30, 0.24),
            ("swish.wav", 11.15, 0.30),
            ("whoosh_curto.wav", 11.50, 0.35), ("clique2.wav", 11.65, 0.28),
            ("check.wav", 12.60, 0.24), ("check.wav", 13.30, 0.24), ("check.wav", 14.00, 0.24),
            ("swish.wav", 23.25, 0.30)
        ]
    }
}

def render_corte(cut_id):
    cfg = CONFIG_CORTES[cut_id]
    t_ini = cfg["t_ini"]
    t_fim = cfg["t_fim"]
    dur = t_fim - t_ini
    total_frames = int(dur * FPS)
    out_mp4 = os.path.join(OUT_DIR, cfg["arquivo"])
    
    print(f"\n========================================================")
    print(f"  INICIANDO CORTE {cut_id:02d}: {cfg['tema']}")
    print(f"  Tempo: {t_ini:.2f}s -> {t_fim:.2f}s (Duração: {dur:.1f}s, {total_frames} quadros)")
    print(f"  Destino: {out_mp4}")
    print(f"========================================================")
    
    temp_base = os.path.join(AQUI, f"temp_corte_{cut_id:02d}_base")
    temp_out = os.path.join(AQUI, f"temp_corte_{cut_id:02d}_out")
    os.makedirs(temp_base, exist_ok=True)
    os.makedirs(temp_out, exist_ok=True)
    
    # 1. Extração de quadros da câmera
    print(f"[{cut_id}.1/5] Extraindo quadros da câmera do Dr. Gestão...")
    cmd_extract = [
        "ffmpeg", "-y", "-ss", str(t_ini), "-t", str(dur),
        "-i", BASE_MP4,
        "-q:v", "2",
        os.path.join(temp_base, "f_%04d.jpg")
    ]
    subprocess.run(cmd_extract, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    # 2. Filtrar palavras e agrupar em frases dinâmicas
    palavras = [p for p in TODAS_PALAVRAS if p["f"] >= t_ini and p["t"] <= t_fim]
    frases = []
    cur_frase = []
    for p in palavras:
        cur_frase.append(p)
        if p["w"].endswith((".", ",", "?", "!")) or len(cur_frase) >= 4:
            frases.append(cur_frase)
            cur_frase = []
    if cur_frase:
        frases.append(cur_frase)
        
    # 3. Composição de quadros
    print(f"[{cut_id}.2/5] Compondo {total_frames} quadros em 9:16 com Motion Graphics...")
    card_x0, card_y0, card_x1, card_y1 = 60, 170, 1020, 870
    
    for f in range(total_frames):
        t_atual = t_ini + (f / FPS)
        t_rel = f / FPS
        
        frame_img = bg_topo_img.copy()
        draw = ImageDraw.Draw(frame_img)
        
        # Câmera Dr. Gestão (inferior)
        base_frame_path = os.path.join(temp_base, f"f_{f+1:04d}.jpg")
        if os.path.exists(base_frame_path):
            cam = Image.open(base_frame_path).convert("RGBA")
            cam_crop = cam.crop((180, 0, 1260, 1080))
            cam_crop = cam_crop.resize((1080, 940), Image.Resampling.BILINEAR)
            frame_img.paste(cam_crop, (0, 980), mask_cam)
            
            draw.arc([0, 980, 72, 1052], start=180, end=270, fill=(142, 125, 229, 180), width=3)
            draw.line([36, 980, 1044, 980], fill=(142, 125, 229, 180), width=3)
            draw.arc([1008, 980, 1080, 1052], start=270, end=360, fill=(142, 125, 229, 180), width=3)
            
        # Top Bar (Pill Badge + Logo Oficial Branco)
        badge_txt = cfg["badge_topo"]
        bw = int(draw.textlength(badge_txt, font=font_badge)) + 70
        draw.rounded_rectangle([60, 68, 60 + bw, 122], radius=27, fill=(142, 125, 229, 45), outline=(142, 125, 229, 120), width=2)
        draw.ellipse([84, 90, 100, 106], fill=(142, 125, 229, 255))
        draw.text((116, 80), badge_txt, fill=(210, 200, 255, 255), font=font_badge)
        
        if logo_img:
            frame_img.paste(logo_img, (W - logo_img.width - 60, 74), logo_img)
            
        # Localizar Card Ativo
        card_ativo = None
        for c in cfg["cards"]:
            if c["t_ini"] <= t_rel < c["t_fim"]:
                card_ativo = c
                break
                
        if card_ativo:
            card_img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            cdraw = ImageDraw.Draw(card_img)
            
            c_t_start, c_t_end = card_ativo["t_ini"], card_ativo["t_fim"]
            c_dt_in = t_rel - c_t_start
            c_dt_out = c_t_end - t_rel
            
            if c_dt_in < 0.35:
                p_c = c_dt_in / 0.35
                c_ease = 1.0 - (1.0 - p_c)**3
                card_dy = int(30 * (1.0 - c_ease))
                card_alpha = c_ease
            elif c_dt_out < 0.35:
                p_c = max(0.0, c_dt_out / 0.35)
                c_ease = p_c**2
                card_dy = int(30 * (1.0 - c_ease))
                card_alpha = c_ease
            else:
                card_dy = 0
                card_alpha = 1.0
                
            cdraw.rounded_rectangle([card_x0+8, card_y0+16, card_x1+8, card_y1+16], radius=32, fill=(0, 0, 0, int(90 * card_alpha)))
            cdraw.rounded_rectangle([card_x0, card_y0, card_x1, card_y1], radius=32, fill=(18, 26, 46, int(242 * card_alpha)), outline=(142, 125, 229, int(110 * card_alpha)), width=2)
            
            # Elementos comuns: Pill, Titulo, Sub
            e_pill, _, dy_pill = calc_item_anim(t_rel, c_t_start + 0.15, dur=0.30, slide_dx=0, slide_dy=-15)
            if e_pill > 0:
                p_txt = card_ativo["badge"]
                p_w = int(cdraw.textlength(p_txt, font=font_badge)) + 50
                cdraw.rounded_rectangle([card_x0+40, card_y0+40+dy_pill, card_x0+40+p_w, card_y0+88+dy_pill], radius=24, fill=(0, 74, 173, int(80*e_pill)), outline=(47, 151, 212, int(140*e_pill)), width=1)
                cdraw.text((card_x0+60, card_y0+49+dy_pill), p_txt, fill=(47, 210, 255, int(255*e_pill)), font=font_badge)
                
            e_tit, _, dy_tit = calc_item_anim(t_rel, c_t_start + 0.30, dur=0.35, slide_dx=0, slide_dy=15)
            if e_tit > 0:
                cdraw.text((card_x0+40, card_y0+112+dy_tit), card_ativo["tit"], fill=(255, 255, 255, int(255*e_tit)), font=font_card_tit)
                
            e_sub, dx_sub, _ = calc_item_anim(t_rel, c_t_start + 0.50, dur=0.35, slide_dx=-15)
            if e_sub > 0:
                cdraw.text((card_x0+40+dx_sub, card_y0+180), card_ativo["sub"], fill=(180, 190, 215, int(255*e_sub)), font=font_card_sub)
                
            # Lead
            if "lead" in card_ativo:
                e_lead, dx_lead, _ = calc_item_anim(t_rel, c_t_start + 0.80, dur=0.30)
                if e_lead > 0:
                    cdraw.text((card_x0+40+dx_lead, card_y0+270), card_ativo["lead"], fill=(255, 255, 255, int(255*e_lead)), font=font_card_lead)
                    
            # Alerta opcional
            if "alerta" in card_ativo:
                e_al, dx_al, _ = calc_item_anim(t_rel, c_t_start + 1.00, dur=0.35)
                if e_al > 0:
                    draw_alert_badge(cdraw, card_x0+40+dx_al, card_y0+310, e_al)
                    cdraw.text((card_x0+78+dx_al, card_y0+310), card_ativo["alerta"], fill=(255, 160, 160, int(255*e_al)), font=font_card_sub)
                    
            # Bullets em Coral
            if "bullets" in card_ativo:
                base_y = 360 if "alerta" in card_ativo else 335
                for b_i, b_txt in enumerate(card_ativo["bullets"]):
                    e_b, dx_b, _ = calc_item_anim(t_rel, c_t_start + 1.10 + b_i*0.60, dur=0.35)
                    if e_b > 0:
                        y_pos = base_y + b_i*60
                        cdraw.ellipse([card_x0+40+dx_b, card_y0+y_pos+11, card_x0+56+dx_b, card_y0+y_pos+27], fill=(239, 68, 68, int(255*e_b)))
                        cdraw.text((card_x0+68+dx_b, card_y0+y_pos), b_txt, fill=(255, 110, 110, int(255*e_b)), font=font_card_item)
                        
            # Checks em Esmeralda
            if "checks" in card_ativo:
                base_y = 335
                for c_i, c_txt in enumerate(card_ativo["checks"]):
                    e_c, dx_c, _ = calc_item_anim(t_rel, c_t_start + 1.10 + c_i*0.70, dur=0.35)
                    if e_c > 0:
                        y_pos = base_y + c_i*60
                        draw_vector_check(cdraw, card_x0+40+dx_c, card_y0+y_pos, e_c)
                        cdraw.text((card_x0+80+dx_c, card_y0+y_pos), c_txt, fill=(110, 255, 175, int(255*e_c)), font=font_card_item_b)
                        
            # Especiais: Marketplaces (Corte 03)
            if card_ativo.get("tipo_especial") == "marketplaces":
                mkts = [
                    ("TikTok Shop", "Tráfego viral & tração imediata", (254, 44, 85)),
                    ("Shopee", "Volume massivo de atacado", (238, 77, 45)),
                    ("Mercado Livre", "Logística Full & confiança", (255, 230, 0)),
                    ("SHEIN", "Giro ultrarrápido em confecção", (255, 255, 255))
                ]
                for m_i, (m_nome, m_desc, m_cor) in enumerate(mkts):
                    e_m, dx_m, _ = calc_item_anim(t_rel, c_t_start + 0.90 + m_i*0.55, dur=0.35)
                    if e_m > 0:
                        mx = card_x0 + 40 + (m_i % 2) * 460 + dx_m
                        my = card_y0 + 260 + (m_i // 2) * 135
                        cdraw.rounded_rectangle([mx, my, mx + 430, my + 115], radius=20, fill=(255, 255, 255, int(15*e_m)), outline=(142, 125, 229, int(100*e_m)), width=1)
                        # Pill da marca
                        cdraw.rounded_rectangle([mx+20, my+20, mx+160, my+60], radius=12, fill=(0, 0, 0, int(180*e_m)), outline=(m_cor[0], m_cor[1], m_cor[2], int(160*e_m)), width=1)
                        cdraw.text((mx+32, my+26), m_nome, fill=(255, 255, 255, int(255*e_m)), font=font_meta)
                        cdraw.text((mx+20, my+74), m_desc, fill=(180, 190, 215, int(255*e_m)), font=font_meta)
                        
            # Especiais: Contador de Escala (Corte 05)
            if card_ativo.get("tipo_especial") == "contador_escala":
                e_cnt, _, _ = calc_item_anim(t_rel, c_t_start + 0.80, dur=0.30)
                if e_cnt > 0:
                    p_num = min(1.0, max(0.0, (t_rel - (c_t_start + 0.90)) / 1.8))
                    val_atual = int(300000 + (500000 - 300000) * (1.0 - math.cos(math.pi * p_num)) / 2.0)
                    cdraw.rounded_rectangle([card_x0+40, card_y0+260, card_x1-40, card_y0+420], radius=24, fill=(10, 14, 24, int(210*e_cnt)), outline=(0, 210, 255, int(120*e_cnt)), width=2)
                    cdraw.text((card_x0+80, card_y0+280), "FATURAMENTO MENSAL:", fill=(0, 210, 255, int(255*e_cnt)), font=font_badge)
                    cdraw.text((card_x0+80, card_y0+325), f"R$ {val_atual:,.0f}".replace(",", "."), fill=(255, 255, 255, int(255*e_cnt)), font=font_counter)
                    cdraw.text((card_x0+40, card_y0+450), card_ativo["lead"], fill=(180, 240, 210, int(255*e_cnt)), font=font_card_sub)
                    
            # Steppers na Base do Card
            s_idx = card_ativo["stepper_idx"]
            step_w = 260
            for idx, lbl in enumerate(cfg["steppers"]):
                sx = card_x0 + 40 + idx * (step_w + 30)
                sy = card_y0 + 570
                is_active = (idx == s_idx)
                bg_c = (0, 74, 173, int(255 * card_alpha)) if is_active else (255, 255, 255, int(20 * card_alpha))
                txt_c = (255, 255, 255, int(255 * card_alpha)) if is_active else (160, 168, 190, int(255 * card_alpha))
                cdraw.rounded_rectangle([sx, sy, sx + step_w, sy + 64], radius=32, fill=bg_c, outline=(142, 125, 229, int(120*card_alpha)) if is_active else None, width=2)
                cdraw.text((sx + 32, sy + 18), lbl, fill=txt_c, font=font_meta)
                
            if card_alpha < 0.999:
                r_c, g_c, b_c, a_c = card_img.split()
                a_c = a_c.point(lambda p: int(p * card_alpha))
                card_img.putalpha(a_c)
            frame_img.paste(card_img, (0, card_dy), card_img)
            
        # Legendas Dinâmicas Palavra por Palavra (y = 890 a 960)
        frase_ativa = None
        for fr in frases:
            if fr[0]["t"] - 0.2 <= t_atual <= fr[-1]["f"] + 0.35:
                frase_ativa = fr
                break
                
        if frase_ativa:
            partes_w = []
            for p in frase_ativa:
                w_p = draw.textlength(p["w"].upper() + " ", font=font_caption)
                partes_w.append((p, w_p))
            total_w = sum(w for _, w in partes_w)
            
            box_x0 = max(40, int(540 - total_w / 2 - 30))
            box_x1 = min(W - 40, int(540 + total_w / 2 + 30))
            draw.rounded_rectangle([box_x0, 895, box_x1, 965], radius=24, fill=(0, 0, 0, 200), outline=(142, 125, 229, 80), width=1)
            
            cur_x = box_x0 + 30
            for p, w_p in partes_w:
                eh_palavra_ativa = (p["t"] - 0.05 <= t_atual <= p["f"] + 0.08)
                cor = (0, 210, 255, 255) if eh_palavra_ativa else (255, 255, 255, 255)
                fnt = font_caption_hl if eh_palavra_ativa else font_caption
                draw.text((cur_x + 2, 905 + 2), p["w"].upper(), fill=(0, 0, 0, 230), font=fnt)
                draw.text((cur_x, 905), p["w"].upper(), fill=cor, font=fnt)
                cur_x += int(w_p)
                
        out_frame_path = os.path.join(temp_out, f"f_{f+1:04d}.jpg")
        frame_img.convert("RGB").save(out_frame_path, quality=94)
        
        if f % 180 == 0:
            pct = f / total_frames * 100
            print(f"  Renderizacao [{cut_id:02d}]: {f}/{total_frames} ({pct:.1f}%) | {t_rel:.1f}s / {dur:.1f}s", flush=True)

    # 4. Trilha SFX Sincronizada
    print(f"[{cut_id}.3/5] Construindo mixagem de efeitos sonoros sutis...")
    sr = 48000
    total_samples = int(dur * sr)
    sfx_track = np.zeros(total_samples, dtype=np.float32)
    
    for s_name, s_t, s_gain in cfg["sfx_triggers"]:
        sp = os.path.join(SONS_DIR, s_name)
        if os.path.exists(sp):
            data, _ = sf.read(sp)
            if data.ndim > 1:
                data = data[:, 0]
            data = data.astype(np.float32) * s_gain
            idx = int(s_t * sr)
            n = min(len(data), total_samples - idx)
            if idx < total_samples and n > 0:
                sfx_track[idx:idx+n] += data[:n]
                
    sfx_wav = os.path.join(AQUI, f"temp_sfx_corte_{cut_id:02d}.wav")
    sf.write(sfx_wav, sfx_track, sr)
    
    # 5. Renderizar Vídeo Base (sem outro)
    print(f"[{cut_id}.4/5] Renderizando vídeo base com voz e SFX...")
    corte_base_mp4 = os.path.join(AQUI, f"temp_corte_{cut_id:02d}_sem_outro.mp4")
    cmd_render_part1 = [
        "ffmpeg", "-y",
        "-framerate", str(FPS),
        "-i", os.path.join(temp_out, "f_%04d.jpg"),
        "-ss", str(t_ini), "-t", str(dur),
        "-i", VOZ_WAV,
        "-i", sfx_wav,
        "-filter_complex", "[1:a][2:a]amix=inputs=2:duration=first:dropout_transition=0:weights=1.0 0.85[aout]",
        "-map", "0:v", "-map", "[aout]",
        "-c:v", "libx264", "-preset", "fast", "-crf", "17", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
        corte_base_mp4
    ]
    subprocess.run(cmd_render_part1, check=True)
    
    # 6. Concatenar com Fechamento e Normalizar Loudness (-14 LUFS)
    print(f"[{cut_id}.5/5] Concatenando animação de fechamento e normalizando áudio (-14 LUFS)...")
    cmd_concat = [
        "ffmpeg", "-y",
        "-i", corte_base_mp4,
        "-i", OUTRO_MP4,
        "-filter_complex", 
        "[0:a]aformat=channel_layouts=stereo[a0];[1:a]aformat=channel_layouts=stereo[a1];[0:v][a0][1:v][a1]concat=n=2:v=1:a=1[vcat][acat];[acat]loudnorm=I=-14:TP=-1.0:LRA=7[aout]",
        "-map", "[vcat]", "-map", "[aout]",
        "-c:v", "libx264", "-preset", "slow", "-crf", "17", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        out_mp4
    ]
    subprocess.run(cmd_concat, check=True)
    
    # Limpeza
    shutil.rmtree(temp_base, ignore_errors=True)
    shutil.rmtree(temp_out, ignore_errors=True)
    if os.path.exists(sfx_wav):
        os.remove(sfx_wav)
    if os.path.exists(corte_base_mp4):
        os.remove(corte_base_mp4)
        
    print(f"[OK] Corte {cut_id:02d} gerado com sucesso: {out_mp4}\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--cuts", nargs="+", type=int, default=[1, 2, 3, 4, 5, 6, 7], help="IDs dos cortes para renderizar (1 a 7)")
    args = parser.parse_args()
    
    for c_id in args.cuts:
        if c_id in CONFIG_CORTES:
            render_corte(c_id)
        else:
            print(f"Corte {c_id} não encontrado na configuração.")
    print(">>> TODOS OS CORTES SOLICITADOS FORAM PROCESSADOS COM SUCESSO! <<<")
