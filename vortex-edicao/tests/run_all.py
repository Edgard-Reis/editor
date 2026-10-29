#!/usr/bin/env python3
"""Roda todos os testes do motor (sem pytest).

    .venv\\Scripts\\python.exe vortex-edicao\\tests\\run_all.py

Descobre todo tests/test_*.py e roda cada um. Sai com código 0 se tudo passar.
"""
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

AQUI = Path(__file__).resolve().parent
PY = sys.executable


def main():
    testes = sorted(AQUI.glob("test_*.py"))
    if not testes:
        print("nenhum teste encontrado em", AQUI)
        return 1
    reprovados = []
    for t in testes:
        print(f"\n=== {t.name} ===", flush=True)
        r = subprocess.run([PY, str(t)])
        if r.returncode != 0:
            reprovados.append(t.name)
    print("\n" + "=" * 50, flush=True)
    if reprovados:
        print(f"FALHOU: {', '.join(reprovados)}")
        return 1
    print(f"OK: {len(testes)} arquivo(s) de teste passaram")
    return 0


if __name__ == "__main__":
    sys.exit(main())
