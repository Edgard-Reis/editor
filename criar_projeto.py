#!/usr/bin/env python3
"""Atalho — a implementação canônica fica em vortex-edicao/criar_projeto.py.

Mantida só para conveniência de quem está na raiz do Editor:
    python criar_projeto.py meu-projeto "Nome de Exibição"
Delega por subprocesso para a cópia versionada no motor (vortex-edicao/).
"""
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
_ALVO = _ROOT / "vortex-edicao" / "criar_projeto.py"
if not _ALVO.exists():  # já dentro de vortex-edicao/
    _ALVO = _ROOT / "criar_projeto.py"

sys.exit(subprocess.call([sys.executable, str(_ALVO)] + sys.argv[1:]))
