#!/usr/bin/env python3
"""Compatibilidade e atalho para novo_episodio.py"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
script = ROOT / "novo_episodio.py"
if not script.exists():
    script = ROOT.parent / "novo_episodio.py"

import subprocess
cmd = [sys.executable, str(script)] + sys.argv[1:]
sys.exit(subprocess.call(cmd))
