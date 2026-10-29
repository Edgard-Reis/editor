#!/usr/bin/env python3
"""Cria a estrutura de um novo Projeto / Marca / Canal no Editor.

Uso:
    python criar_projeto.py <slug_do_projeto> [Nome de Exibição]

Exemplos:
    python criar_projeto.py ozon-tech "Ozon Tech"
    python criar_projeto.py meu-cliente "Cliente XPTO"
"""

import os
import re
import sys
import json
import shutil
from pathlib import Path
import sys as _stdout_sys
if hasattr(_stdout_sys.stdout, "reconfigure"):
    _stdout_sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # trava: saída cp1252 não quebra o script

BASE_EDITOR = Path(__file__).resolve().parent
if BASE_EDITOR.name == "vortex-edicao":  # rodando de dentro do motor
    BASE_EDITOR = BASE_EDITOR.parent
PROJETOS_DIR = BASE_EDITOR / "projetos"
VORTEX_DIR = BASE_EDITOR / "vortex-edicao"

# slug seguro: minúsculas/dígitos, hífen entre segmentos. Impede acentos, espaços
# residuais, "..", "/" e outros que quebrariam caminhos depois.
_SLUG_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def main():
    if len(sys.argv) < 2:
        print("Uso: python criar_projeto.py <slug_do_projeto> [Nome de Exibição]")
        print("Exemplo: python criar_projeto.py empresa-tech \"Empresa Tech\"")
        sys.exit(1)

    slug = sys.argv[1].strip().lower().replace(" ", "-")
    nome_exibicao = sys.argv[2].strip() if len(sys.argv) > 2 else slug.replace("-", " ").title()

    if not _SLUG_RE.match(slug):
        print(f"[Erro] Slug inválido: '{slug}'")
        print("       Use só letras minúsculas, dígitos e hífens entre segmentos,")
        print("       ex.: empresa-tech, clinica-saude, loja2. Sem acentos, espaços, '.' ou '/'.")
        sys.exit(2)

    proj_dir = PROJETOS_DIR / slug
    if proj_dir.exists():
        # exit 1 (não 0): já existir é falha, não sucesso — scripts podem checar $?
        print(f"[Erro] O projeto '{slug}' já existe em: {proj_dir}")
        print("       Escolha outro slug, ou remova/renomeie a pasta existente antes de continuar.")
        sys.exit(1)

    branding_dir = proj_dir / "branding"
    episodios_dir = proj_dir / "episodios"

    print(f"\n--> Criando nova marca / projeto: {nome_exibicao} ({slug})")
    (branding_dir / "logos").mkdir(parents=True, exist_ok=True)
    (branding_dir / "vinhetas").mkdir(parents=True, exist_ok=True)
    (branding_dir / "sons").mkdir(parents=True, exist_ok=True)
    (branding_dir / "overlays").mkdir(parents=True, exist_ok=True)
    (branding_dir / "referencias").mkdir(parents=True, exist_ok=True)  # prints/frames de referência
    (branding_dir / "scripts").mkdir(parents=True, exist_ok=True)      # helpers específicos da marca
    episodios_dir.mkdir(parents=True, exist_ok=True)

    # Copia kit de sons padrão
    sons_kit = VORTEX_DIR / "sons" / "kit"
    if sons_kit.exists():
        for s in sons_kit.glob("*.wav"):
            shutil.copy2(s, branding_dir / "sons" / s.name)

    # Cria config.json padrão.
    # PALETA NEUTRA (cinza/branco): NÃO herda a identidade de nenhuma marca
    # existente. O usuário preenche as cores reais em preferencias/marca antes
    # do primeiro build — assim um projeto novo nunca "nasce" com a cara de outro.
    cfg = {
        "webcam": None,
        "fundo_gravacao": "#0a0a0a",
        "trechos_tela": None,
        "rosto": [960, 420],
        "marca": {
            "destaque": "#e5e7eb",
            "secundaria": "#9ca3af",
            "ciano": "#6b7280",
            "fundo_card": "rgba(15, 23, 42, 0.85)",
            "fonte": "Inter",
            "_TODO": "Preencha destaque/secundaria/ciano com as cores reais da marca."
        },
        "preferencias_edicao": {
            "canal": nome_exibicao,
            "apresentador": f"Apresentador {nome_exibicao}",
            "credencial_oficial": f"{nome_exibicao} · Oficial",
            "trilha_sonora": False,
            "lexicon_transcricao": (
                f"{nome_exibicao}, vocabulário específico do canal, termos do segmento, "
                "nomes próprios e siglas recorrentes."
            ),
            "broll": {
                "modo_padrao": "tela_cheia",
                "nunca_sobrepor_rosto": True,
                "ken_burns": 1.06,
                "rotulo_rodape": True
            },
            "cards": {
                "alternar_lados": True,
                "pos_esquerda": {"x": 100, "y": 320, "lado": "esq"},
                "pos_direita": {"x": 1220, "y": 320, "lado": "dir"},
                "respeitar_rosto": True,
                "largura_maxima_lower_third": 1150
            },
            "logos_oficiais": {}
        },
        "_ajuda": f"Configurações de identidade visual para {nome_exibicao}. Novos episódios herdam automaticamente."
    }
    with open(branding_dir / "config.json", "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)

    # Cria PREFERENCIAS.md padrão
    manual_content = f"""# Preferências de Edição — {nome_exibicao}

Este documento reúne todas as decisões estéticas, diretrizes de edição e padrões visuais específicos de **{nome_exibicao}**. Todos os episódios criados para este projeto herdam essas definições por padrão.

---

## 1. Identidade Visual da Marca
- **Canal / Projeto:** {nome_exibicao}
- **Proposta Visual:** TODO — descreva a estética (ex.: "moderna, limpa e profissional").
- **Paleta de Cores Oficial:** *(preencha abaixo — os valores são placeholders neutros)*
  - **Destaque Primário:** `#e5e7eb` → TODO
  - **Secundária:** `#9ca3af` → TODO
  - **Ciano/Acento:** `#6b7280` → TODO
  - **Fundo dos Cards:** `rgba(15, 23, 42, 0.85)`
  - **Texto Principal:** `#ffffff`
  - **Texto de Apoio:** `#94a3b8`
- **Tipografia:** **Inter** / **Roboto**

---

## 2. Regras de Lower Thirds & Apresentador
- **Posição:** Canto inferior esquerdo (`x=100`, `y=800`).
- **Composição:** Nome do apresentador + Credencial oficial.
- **Largura Dinâmica:** Auto-ajuste para evitar cortes (`max-width: 1150px`).

---

## 3. Posicionamento de Cards e Motions
- **Alternância Dinâmica:**
  - Esquerda: `x=100`, `y=320`
  - Direita: `x=1220`, `y=320`
- **Zero Obstrução:** Nunca sobrepor o rosto do apresentador.

---

## 4. Regras de B-Rolls
- **Modo Padrão:** Tela Cheia com zoom suave (Ken Burns 1.06).
- **Legenda:** Chip no rodapé identificando o tema do b-roll.

---

## 5. Recursos da Marca
- Coloque os logos SVG/PNG em `branding/logos/`.
- Coloque vinhetas em `branding/vinhetas/`.
- Coloque efeitos sonoros específicos em `branding/sons/`.
- Coloque prints/frames de referência (para bater o estilo) em `branding/referencias/`.
- Helpers/scripts específicos desta marca em `branding/scripts/` (copiados para a raiz de cada episódio).
- Defina o lexicon de transcrição em `branding/config.json → preferencias_edicao.lexicon_transcricao`
  (vocabulário do canal, siglas e nomes próprios — melhora a precisão do Whisper).
"""
    (branding_dir / "PREFERENCIAS.md").write_text(manual_content, encoding="utf-8")

    print(f"\n[OK] Projeto '{nome_exibicao}' criado com sucesso!")
    print(f"     Diretório: {proj_dir}")
    print(f"     Branding:  {branding_dir}")
    print(f"\nPara criar o primeiro episódio:")
    print(f"     python novo_episodio.py {slug} EP-01 [caminho_do_video.mp4]")

if __name__ == "__main__":
    main()
