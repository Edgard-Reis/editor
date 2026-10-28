#!/usr/bin/env python3
"""Busca e baixa b-roll GRÁTIS do Pixabay (API oficial) pra usar com o broll() do kit de cenas.

Chave configurada no .env da skill: PIXABAY_API_KEY=...

Uso:
  python scripts/broll_pixabay.py "sewing machine" -o media/broll
  python scripts/broll_pixabay.py "garment factory" --orientacao landscape --min 4 --max 20 -n 2 -o media/broll
  python scripts/broll_pixabay.py "textile manufacturing" --dry-run
"""
import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
API_URL = "https://pixabay.com/api/videos/"

# Dicionário estrito de confecção do vestuário e gestão têxtil (PT -> EN)
# Garante que termos como fábrica/indústria/equipamento SEMPRE venham do nicho de vestuário
DICIONARIO_TERMOS = {
    "costura": "sewing machine clothing tailoring",
    "costureira": "sewing seamstress textile worker",
    "fabrica": "garment factory clothing apparel manufacturing",
    "fábrica": "garment factory clothing apparel manufacturing",
    "industria": "clothing manufacturing textile factory",
    "indústria": "clothing manufacturing textile factory",
    "equipamentos": "industrial sewing machine textile equipment",
    "maquinas": "industrial sewing machine textile garment",
    "máquinas": "industrial sewing machine textile garment",
    "galpao": "clothing warehouse apparel distribution",
    "galpão": "clothing warehouse apparel distribution",
    "tecido": "textile fabric clothing rolls",
    "roupas": "clothing garments apparel fashion",
    "confeccao": "garment manufacturing clothing line sewing",
    "confecção": "garment manufacturing clothing line sewing",
    "corte e costura": "fabric cutting textile garment pattern sewing",
    "mesa de corte": "fabric cutting table garment pattern",
    "vendas": "ecommerce clothing retail shipping packages",
    "logistica": "apparel warehouse logistics clothing boxes",
    "logística": "apparel warehouse logistics clothing boxes",
    "dinheiro": "cash counting finance money business",
    "estoque": "clothing apparel warehouse inventory boxes"
}

def carregar_chave():
    """Carrega PIXABAY_API_KEY do ambiente ou dos arquivos .env."""
    k = os.environ.get("PIXABAY_API_KEY")
    if k:
        return k.strip().strip('"').strip("'")
    
    atual = Path(__file__).resolve().parent
    for _ in range(6):
        env = atual / ".env"
        if env.exists():
            for linha in env.read_text(encoding="utf-8", errors="ignore").splitlines():
                if linha.strip().startswith("PIXABAY_API_KEY="):
                    k = linha.split("=", 1)[1].strip().strip('"').strip("'")
                    if k:
                        return k
        atual = atual.parent
    return None

def normalizar_termo(termo):
    """Traduz termos comuns em português ou usa o termo original em inglês."""
    t_clean = termo.strip().lower()
    if t_clean in DICIONARIO_TERMOS:
        return DICIONARIO_TERMOS[t_clean]
    return termo.strip()

def buscar_videos_pixabay(chave, termo, per_page=15, categoria=None, tipo="film"):
    """Consulta a API de vídeos do Pixabay."""
    termo_busca = normalizar_termo(termo)
    params = {
        "key": chave,
        "q": termo_busca,
        "video_type": tipo,  # "film" prioriza gravações reais ao invés de animações
        "safesearch": "true",
        "per_page": max(3, min(per_page, 50))
    }
    if categoria:
        params["category"] = categoria

    url = API_URL + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    })
    
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(f"[ERRO Pixabay] HTTP {e.code}: {e.reason}", file=sys.stderr)
        return {"hits": []}
    except Exception as e:
        print(f"[ERRO Pixabay] Falha na requisição: {e}", file=sys.stderr)
        return {"hits": []}

def escolher_melhor_resolucao(video_dict, orientacao="landscape"):
    """Escolhe o melhor arquivo MP4 disponível no Pixabay mais próximo de 1080p."""
    alvo_w, alvo_h = (1920, 1080) if orientacao == "landscape" else (1080, 1920)
    
    # Ordem de preferência para 1080p
    opcoes = []
    for chave_tamanho in ["large", "medium", "small"]:
        v = video_dict.get(chave_tamanho)
        if not v or not v.get("url"):
            continue
        w = v.get("width", 0)
        h = v.get("height", 0)
        size = v.get("size", 0)
        
        # Alguns itens antigos do Pixabay não reportam width/height no large
        if w == 0 and h == 0 and size > 0:
            w, h = 1920, 1080
            
        if w > 0 and h > 0:
            opcoes.append({
                "tamanho": chave_tamanho,
                "url": v["url"],
                "width": w,
                "height": h,
                "size": size,
                "thumbnail": v.get("thumbnail", "")
            })

    if not opcoes:
        return None

    def pontuar_arquivo(f):
        dw = abs(f["width"] - alvo_w)
        dh = abs(f["height"] - alvo_h)
        # Penaliza arquivos 4K excessivamente pesados (>2560px)
        peso_extra = 500 if f["width"] > 2560 else 0
        return dw + dh + peso_extra

    return min(opcoes, key=pontuar_arquivo)

def baixar_arquivo(url, destino):
    """Baixa o arquivo binário exibindo progresso."""
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    })
    Path(destino).parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(req, timeout=120) as r, open(destino, "wb") as f:
        tam_total = int(r.headers.get("content-length", 0))
        baixado = 0
        bloco = 1024 * 1024  # 1MB
        while True:
            chunk = r.read(bloco)
            if not chunk:
                break
            f.write(chunk)
            baixado += len(chunk)
            if tam_total > 0:
                pct = int(baixado * 100 / tam_total)
                mb = baixado / (1024 * 1024)
                tot_mb = tam_total / (1024 * 1024)
                sys.stdout.write(f"\r  Baixando: {mb:.1f}MB / {tot_mb:.1f}MB ({pct}%)")
                sys.stdout.flush()
        print()

def sanitizar_nome(texto):
    """Gera um nome de arquivo amigável e limpo."""
    s = re.sub(r"[^\w\s-]", "", texto).strip().lower()
    return re.sub(r"[-\s]+", "_", s)[:40]

def main():
    parser = argparse.ArgumentParser(description="Busca e baixa b-roll grátis do Pixabay")
    parser.add_argument("termo", help='Termo de busca (ex: "sewing machine", "clothing factory", "warehouse")')
    parser.add_argument("-o", "--saida", default="media/broll", help="Pasta de saída (padrão: media/broll)")
    parser.add_argument("-n", "--quantidade", type=int, default=1, help="Número de vídeos para baixar (padrão: 1)")
    parser.add_argument("--orientacao", choices=["landscape", "portrait"], default="landscape", help="Orientação do vídeo")
    parser.add_argument("--min", type=float, default=4.0, help="Duração mínima em segundos (padrão: 4s)")
    parser.add_argument("--max", type=float, default=30.0, help="Duração máxima em segundos (padrão: 30s)")
    parser.add_argument("--categoria", choices=["industry", "business", "computer", "people", "places"], default=None, help="Categoria específica")
    parser.add_argument("--dry-run", action="store_true", help="Apenas exibe os resultados encontrados sem baixar nada")
    args = parser.parse_args()

    chave = carregar_chave()
    if not chave:
        print("[ERRO] PIXABAY_API_KEY não encontrada no .env ou nas variáveis de ambiente.", file=sys.stderr)
        print("Adicione no seu arquivo .env: PIXABAY_API_KEY=sua_chave", file=sys.stderr)
        sys.exit(1)

    termo_efetivo = normalizar_termo(args.termo)
    print(f"=== BUSCA B-ROLL PIXABAY ===")
    print(f"Termo original: '{args.termo}' -> Consulta efetiva: '{termo_efetivo}'")
    print(f"Duração desejada: {args.min:.1f}s a {args.max:.1f}s | Orientação: {args.orientacao}")

    resultado = buscar_videos_pixabay(chave, args.termo, per_page=20, categoria=args.categoria)
    hits = resultado.get("hits", [])
    if not hits:
        print(f"Nenhum vídeo encontrado para o termo '{termo_efetivo}'. Tente um termo em inglês mais amplo.")
        sys.exit(0)

    # Filtrar por duração
    candidatos = []
    for h in hits:
        dur = float(h.get("duration", 0))
        if args.min <= dur <= args.max:
            melhor = escolher_melhor_resolucao(h.get("videos", {}), args.orientacao)
            if melhor:
                candidatos.append({
                    "id": h["id"],
                    "duracao": dur,
                    "tags": h.get("tags", ""),
                    "user": h.get("user", "Pixabay Creator"),
                    "pageURL": h.get("pageURL", ""),
                    "arquivo": melhor
                })

    print(f"Resultados encontrados: {len(hits)} | Compatíveis com duração e resolução: {len(candidatos)}\n")

    if args.dry_run:
        print("Modo --dry-run (nenhum download realizado):")
        for i, c in enumerate(candidatos[:args.quantidade * 3], 1):
            arq = c["arquivo"]
            print(f"[{i}] ID {c['id']} ({c['duracao']:.1f}s) - {arq['width']}x{arq['height']} ({arq['tamanho']})")
            print(f"    Tags: {c['tags']}")
            print(f"    Autor: {c['user']} | {c['pageURL']}\n")
        sys.exit(0)

    if not candidatos:
        print("Nenhum vídeo atende aos critérios de duração e resolução. Experimente afrouxar os limites --min/--max.")
        sys.exit(0)

    pasta_saida = Path(args.saida)
    pasta_saida.mkdir(parents=True, exist_ok=True)
    creditos_path = pasta_saida / "creditos_pixabay.json"
    creditos = []
    if creditos_path.exists():
        try:
            creditos = json.loads(creditos_path.read_text(encoding="utf-8"))
        except Exception:
            creditos = []

    selecionados = candidatos[:args.quantidade]
    for i, c in enumerate(selecionados, 1):
        slug = sanitizar_nome(c['tags'].split(',')[0] if c['tags'] else args.termo)
        nome_arquivo = f"pixabay_{c['id']}_{slug}.mp4"
        destino = pasta_saida / nome_arquivo

        print(f"[{i}/{len(selecionados)}] Baixando: {nome_arquivo} ({c['duracao']:.1f}s, {c['arquivo']['width']}x{c['arquivo']['height']})...")
        baixar_arquivo(c['arquivo']['url'], destino)

        creditos.append({
            "arquivo": nome_arquivo,
            "origem": "pixabay",
            "id": c["id"],
            "tags": c["tags"],
            "autor": c["user"],
            "link": c["pageURL"],
            "licenca": "Pixabay Content License (Livre para uso comercial, sem atribuição obrigatória)"
        })

    creditos_path.write_text(json.dumps(creditos, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n[OK] {len(selecionados)} B-roll(s) baixado(s) com sucesso em: {pasta_saida}")
    print(f"[OK] Metadados e créditos salvos em: {creditos_path}")

if __name__ == "__main__":
    main()
