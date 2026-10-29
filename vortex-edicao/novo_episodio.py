#!/usr/bin/env python3
"""Gerenciador Multi-Projetos de Edição de Vídeo
Cria a estrutura de um novo episódio herdando automaticamente a identidade visual do projeto/marca.

Uso:
    python novo_episodio.py <projeto> <episodio> [gravacao.mp4] [--forcar]

Exemplos:
    python novo_episodio.py dr-gestao EP-01
    python novo_episodio.py ozon-tech EP-01 "d:\\gravacoes\\video.mp4"
    python novo_episodio.py dr-gestao EP-00 --forcar

Segurança: arquivos que JÁ existem no workspace nunca são sobrescritos (protege a
linha do tempo editada à mão em build.py/cenas.py). Use --forcar para atualizar
os templates de propósito. Subpastas do branding (ex.: overlays/transicoes/) são
copiadas integralmente.
"""

import argparse
import os
import sys
import shutil
import subprocess
from pathlib import Path
import sys as _stdout_sys
if hasattr(_stdout_sys.stdout, "reconfigure"):
    _stdout_sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # trava: saída cp1252 não quebra o script

ROOT_DIR = Path(__file__).resolve().parent
if ROOT_DIR.name == "vortex-edicao":
    BASE_EDITOR = ROOT_DIR.parent
else:
    BASE_EDITOR = ROOT_DIR

VORTEX_DIR = BASE_EDITOR / "vortex-edicao"
PROJETOS_DIR = BASE_EDITOR / "projetos"

def listar_projetos():
    if not PROJETOS_DIR.exists():
        return []
    return [p.name for p in PROJETOS_DIR.iterdir() if p.is_dir() and (p / "branding").exists()]

def main():
    if len(sys.argv) == 1:
        projetos = listar_projetos()
        print("=" * 60)
        print("  GERENCIADOR DE EPISÓDIOS MULTI-PROJETOS")
        print("=" * 60)
        print("Uso:")
        print("  python novo_episodio.py <projeto> <episodio> [gravacao.mp4]\n")
        print("Projetos disponíveis:")
        for p in projetos:
            print(f"  - {p}")
        print("\nPara criar um novo projeto/marca:")
        print("  python criar_projeto.py <nome-do-projeto> \"Nome de Exibição\"")
        print("=" * 60)
        sys.exit(1)

    ap = argparse.ArgumentParser(
        description="Cria a estrutura de um episódio herdando a identidade visual do projeto/marca.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Exemplos:\n"
               "  python novo_episodio.py dr-gestao EP-01\n"
               "  python novo_episodio.py dr-gestao EP-01 \"D:\\Gravacoes\\estudio.mp4\"\n"
               "  python novo_episodio.py dr-gestao EP-00 --forcar   # atualiza o template do episódio")
    ap.add_argument("projeto", nargs="?", help="slug da marca (ex.: dr-gestao)")
    ap.add_argument("episodio", nargs="?", help="slug do episódio (ex.: EP-01)")
    ap.add_argument("gravacao", nargs="?", help="caminho opcional da gravação bruta (.mp4)")
    ap.add_argument("--forcar", action="store_true",
                    help="sobrescreve arquivos do workspace que já existem (padrão: NUNCA sobrescreve)")
    a = ap.parse_args()

    if not a.projeto or not a.episodio:
        ap.print_help()
        sys.exit(1)

    projeto_slug = a.projeto.strip()
    episodio_slug = a.episodio.strip()
    gravacao_path = Path(a.gravacao).resolve() if a.gravacao else None

    projeto_dir = PROJETOS_DIR / projeto_slug
    if not projeto_dir.exists():
        print(f"\n[ERRO] Projeto '{projeto_slug}' não encontrado em: {PROJETOS_DIR}")
        print("Projetos disponíveis:", listar_projetos())
        print(f"Dica: Crie o projeto primeiro com: python criar_projeto.py {projeto_slug}")
        sys.exit(1)

    branding_dir = projeto_dir / "branding"
    episodio_dir = projeto_dir / "episodios" / episodio_slug
    brutos_dir = episodio_dir / "brutos"
    workspace_dir = episodio_dir / "workspace"
    renders_dir = episodio_dir / "renders"

    print(f"\n--> Configurando episódio: [{episodio_slug}] para o projeto: [{projeto_slug}]")
    print(f"    Destino: {episodio_dir}")

    # 1. Cria diretórios base do episódio
    brutos_dir.mkdir(parents=True, exist_ok=True)
    workspace_dir.mkdir(parents=True, exist_ok=True)
    renders_dir.mkdir(parents=True, exist_ok=True)

    # Subpastas internas do workspace
    (workspace_dir / "media").mkdir(parents=True, exist_ok=True)
    (workspace_dir / "renders").mkdir(parents=True, exist_ok=True)
    (workspace_dir / "logos").mkdir(parents=True, exist_ok=True)
    (workspace_dir / "vinhetas").mkdir(parents=True, exist_ok=True)
    (workspace_dir / "sons").mkdir(parents=True, exist_ok=True)
    (workspace_dir / "overlays").mkdir(parents=True, exist_ok=True)

    # ---- cópias seguras: criam o que falta e NUNCA sobrescrevem um workspace já
    #      editado (build.py/cenas.py com a linha do tempo do episódio). --forcar libera.
    estado = {"novos": 0, "pulados": 0}

    def copia_arquivo(src, dst):
        if dst.exists() and not a.forcar:
            estado["pulados"] += 1
            return
        shutil.copy2(src, dst)
        estado["novos"] += 1

    def copia_pasta(src_dir, dst_dir):
        """Copia TODOS os arquivos, inclusive subpastas (ex.: overlays/transicoes/)."""
        if not src_dir.exists():
            return
        for item in sorted(src_dir.rglob("*")):
            if not item.is_file():
                continue
            destino = dst_dir / item.relative_to(src_dir)
            if destino.exists() and not a.forcar:
                estado["pulados"] += 1
                continue
            destino.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, destino)
            estado["novos"] += 1

    # 2. Copia arquivos base do motor Vortex (modelo)
    modelo_dir = VORTEX_DIR / "modelo"
    arquivos_modelo = [
        "build.py", "estilo.css", "ilustra.py", "ilustra.css",
        "render_rapido.py", "masterizar.sh", "cenas.py", "cenas.css",
        "checa_texto.py", "webcam_fixa.py"
    ]
    for arq in arquivos_modelo:
        src = modelo_dir / arq
        if src.exists():
            copia_arquivo(src, workspace_dir / arq)

    # 3. Herda a Identidade Visual do Projeto (Branding)
    # 3.1 Config e Preferências
    if (branding_dir / "config.json").exists():
        copia_arquivo(branding_dir / "config.json", workspace_dir / "config.json")
    elif (VORTEX_DIR / "config.exemplo.json").exists():
        copia_arquivo(VORTEX_DIR / "config.exemplo.json", workspace_dir / "config.json")

    if (branding_dir / "PREFERENCIAS.md").exists():
        copia_arquivo(branding_dir / "PREFERENCIAS.md", workspace_dir / "PREFERENCIAS.md")

    # 3.2 a 3.5 Logos, vinhetas, sons e overlays (COM subpastas: overlays/transicoes/)
    for sub in ("logos", "vinhetas", "sons", "overlays"):
        copia_pasta(branding_dir / sub, workspace_dir / sub)

    # 3.6 Scripts e Templates específicos da marca (flat, na raiz do workspace)
    if (branding_dir / "scripts").exists():
        for item in sorted((branding_dir / "scripts").iterdir()):
            if item.is_file():
                copia_arquivo(item, workspace_dir / item.name)

    # 4. Fontes do sistema
    copia_pasta(VORTEX_DIR / "fonts", workspace_dir / "fonts")

    # 5. Manifests (só cria se não existir — podem ter sido personalizados)
    if not (workspace_dir / "package.json").exists() or a.forcar:
        (workspace_dir / "package.json").write_text(
            f'{{\n  "name": "{projeto_slug}-{episodio_slug}",\n  "private": true,\n  "type": "module"\n}}\n',
            encoding="utf-8"
        )
    else:
        estado["pulados"] += 1
    if not (workspace_dir / "hyperframes.json").exists() or a.forcar:
        (workspace_dir / "hyperframes.json").write_text(
            '{\n  "$schema": "https://hyperframes.heygen.com/schema/hyperframes.json"\n}\n',
            encoding="utf-8"
        )
    else:
        estado["pulados"] += 1

    print(f"\n[OK] Episódio '{episodio_slug}' configurado com sucesso!")
    print(f"     - Identidade herdada de: {branding_dir}")
    print(f"     - Espaço de trabalho:    {workspace_dir}")
    print(f"     - Arquivos brutos em:   {brutos_dir}")
    print(f"     - Renders finais em:    {renders_dir}")
    print(f"     - Cópias: {estado['novos']} nova(s), {estado['pulados']} já existente(s) mantida(s)"
          + ("" if estado["pulados"] == 0 else "  → use --forcar para atualizar o template"))
    if estado["pulados"] and not a.forcar:
        print("     ⚠ Nada do workspace existente foi sobrescrito (proteção contra perda da linha do tempo).")

    # 6. Gravação opcional
    if gravacao_path:
        if gravacao_path.exists():
            dest_bruto = brutos_dir / gravacao_path.name
            print(f"\n--> Copiando gravação para brutos: {dest_bruto}")
            shutil.copy2(gravacao_path, dest_bruto)

            python_bin = VORTEX_DIR / ".venv" / "Scripts" / "python.exe"
            if not python_bin.exists():
                python_bin = sys.executable

            print(f"--> Iniciando transcrição com áudio limpo para: {dest_bruto.name}...")
            transcrever_script = VORTEX_DIR / "transcrever.py"
            if transcrever_script.exists():
                subprocess.run([str(python_bin), str(transcrever_script), str(dest_bruto), str(workspace_dir)], check=True)
        else:
            print(f"[Aviso] Arquivo de gravação não encontrado: {gravacao_path}")

if __name__ == "__main__":
    main()
