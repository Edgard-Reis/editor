#!/usr/bin/env python3
"""Testes de encoding (travas UTF-8 da Fase 1).

Cobre dois riscos reais do pipeline:
  1. round-trip de acentos (ção, ç, é) na escrita/leitura de JSON e texto —
     o que os fixes de `encoding="utf-8"` protegem;
  2. presença da trava de saída UTF-8 nos scripts que imprimem acentos em
     console cp1252 (Windows), sem a qual o script quebra imprimindo "→".

Sem pytest: roda com python puro.
    .venv\\Scripts\\python.exe vortex-edicao\\tests\\test_encoding.py
"""
import json
import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

MOTOR = Path(__file__).resolve().parents[1]

# Scripts que imprimem setas/acentos e precisam da trava de saída UTF-8.
# (Os que a Fase 1 corrigiu + os principais do pipeline.)
COM_TRAVA = [
    "transcrever.py",
    "cortar.py",
    "criar_projeto.py",
    "novo_episodio.py",
    "modelo/build.py",
    "modelo/ilustra.py",
    "modelo/render_rapido.py",
    "modelo/checa_texto.py",
]

# Amostra com os caracteres que quebram em cp1252.
AMOSTRA = "ação — ção, coração, über, vídeo,→,★, \"aspas\",'apostrofo'"


# ---------------- testes ----------------

def test_json_roundtrip_acentos():
    """Grava e relê JSON com ensure_ascii=False + encoding=utf-8 preserva acentos."""
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "palavras.json"
        dados = [{"w": "ação", "t": 1.5}, {"w": "coração", "t": 2.0}, {"w": "vídeo", "t": 3.0}]
        with open(p, "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)
        relido = json.loads(p.read_text(encoding="utf-8"))
        assert relido == dados, f"round-trip JSON divergiu: {relido!r} != {dados!r}"
        assert relido[0]["w"] == "ação"
        assert relido[1]["w"] == "coração"


def test_json_sem_ensure_ascii_nao_escapa():
    """ensure_ascii=False mantém o caractere literal (não \\u00e7) no arquivo."""
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "x.json"
        with open(p, "w", encoding="utf-8") as f:
            json.dump({"w": "ção"}, f, ensure_ascii=False)
        cru = p.read_bytes()
        # "ç" em UTF-8 são os bytes c3 a7; se estivesse escapado seria b"\\u00e7"
        assert "ção".encode("utf-8") in cru, f"acentos escapados/errados no arquivo: {cru!r}"
        assert b"\\u00e7" not in cru, "ensure_ascii deveria estar False"


def test_texto_roundtrip_acentos():
    """write_text/read_text com encoding=utf-8 preservam a amostra completa."""
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "roteiro.txt"
        p.write_text(AMOSTRA, encoding="utf-8")
        assert p.read_text(encoding="utf-8") == AMOSTRA


def test_stdin_stdout_utf8_reconfigure_nao_quebra():
    """A trava reconfigure(encoding='utf-8') permite imprimir acentos sem UnicodeEncodeError."""
    import io
    velho = sys.stdout
    try:
        buf_bytes = io.BytesIO()
        # simula console cp1252 estrito (o problema original no Windows)
        sys.stdout = io.TextIOWrapper(buf_bytes, encoding="cp1252", errors="strict")
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        print("→ ação ção ★")  # não deve levantar exceção
        sys.stdout.flush()
        assert "ção".encode("utf-8") in buf_bytes.getvalue(), "acentos não saíram em UTF-8"
    finally:
        sys.stdout = velho


def test_sem_trava_cp1252_quebraria():
    """Prova o risco: SEM a trava, imprimir acento em cp1252 estrito levanta erro.

    Confirma que a trava testada acima é realmente necessária (não é superstição).
    """
    import io
    velho = sys.stdout
    try:
        # cp1252 NÃO tem "★" → sem reconfigure deve estourar
        sys.stdout = io.TextIOWrapper(io.BytesIO(), encoding="cp1252", errors="strict")
        try:
            print("★")
        except UnicodeEncodeError:
            pass  # esperado: prova que a trava protege
        else:
            raise AssertionError("cp1252 deveria falhar em '★' (a trava é necessária)")
    finally:
        sys.stdout = velho


def test_scripts_com_trava_utf8():
    """Todos os scripts listados carregam a trava de saída UTF-8."""
    faltando = []
    for rel in COM_TRAVA:
        p = MOTOR / rel
        if not p.exists():
            faltando.append(f"{rel} (arquivo ausente)")
            continue
        if 'reconfigure(encoding="utf-8"' not in p.read_text(encoding="utf-8"):
            faltando.append(rel)
    assert not faltando, f"scripts sem trava UTF-8: {faltando}"


def test_fontes_estao_em_utf8():
    """Os .py do motor devem ser legíveis como UTF-8 (Fase 1 padronizou)."""
    alvos = [
        "transcrever.py", "cortar.py", "criar_projeto.py",
        "modelo/build.py", "modelo/ilustra.py", "sons/gerar_sons.py",
    ]
    for rel in alvos:
        p = MOTOR / rel
        if p.exists():
            p.read_text(encoding="utf-8")  # levanta UnicodeDecodeError se não for UTF-8


TESTES = [
    test_json_roundtrip_acentos,
    test_json_sem_ensure_ascii_nao_escapa,
    test_texto_roundtrip_acentos,
    test_stdin_stdout_utf8_reconfigure_nao_quebra,
    test_sem_trava_cp1252_quebraria,
    test_scripts_com_trava_utf8,
    test_fontes_estao_em_utf8,
]


def main():
    falhas = 0
    for t in TESTES:
        try:
            t()
            print(f"  PASS  {t.__name__}")
        except Exception as e:
            falhas += 1
            print(f"  FAIL  {t.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(TESTES) - falhas}/{len(TESTES)} testes de encoding passaram")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
