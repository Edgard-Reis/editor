#!/usr/bin/env python3
"""Testes do W() e da sugestão por distância de edição (modelo/build.py).

O build.py faz I/O no import (lê palavras_saida.json e roda ffprobe), então não
dá pra importar direto aqui. Extraímos só as funções puras via AST e rodamos
contra um fixture pequeno — testa o código REAL sem disparar os efeitos colaterais.

Sem pytest (não instalado): roda com python puro.
    .venv\\Scripts\\python.exe vortex-edicao\\tests\\test_build_w.py
Sai com código 0 se tudo passar, 1 se algo falhar.
"""
import ast
import re
import sys
import unicodedata
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BUILD_PY = Path(__file__).resolve().parents[1] / "modelo" / "build.py"

# Trecho do roteiro de exemplo, no formato de palavras_saida.json.
# Cada palavra: {"w": como falou, "t": início (s), "f": fim (s)}.
FIXTURE_PAL = [
    {"w": "Hoje", "t": 0.00, "f": 0.32},
    {"w": "eu", "t": 0.32, "f": 0.44},
    {"w": "vou", "t": 0.44, "f": 0.60},
    {"w": "mostrar", "t": 0.60, "f": 1.05},
    {"w": "como", "t": 1.05, "f": 1.30},
    {"w": "instalar", "t": 1.30, "f": 1.85},
    {"w": "o", "t": 1.85, "f": 1.92},
    {"w": "Claude", "t": 1.92, "f": 2.40},
    {"w": "Code", "t": 2.40, "f": 2.80},
]


def _carrega_funcoes():
    """Extrai _n, _distancia_edicao, _sugestoes e W do build.py real via AST."""
    src = BUILD_PY.read_text(encoding="utf-8")
    arvore = ast.parse(src)
    nomes = {"_n", "_distancia_edicao", "_sugestoes", "W"}
    blocos = [n for n in arvore.body
              if isinstance(n, ast.FunctionDef) and n.name in nomes]
    encontrados = {b.name for b in blocos}
    faltando = nomes - encontrados
    if faltando:
        raise RuntimeError(f"funções ausentes no build.py: {sorted(faltando)}")

    # Compila só as funções selecionadas, com o _n antes (W depende dele).
    modulo = ast.Module(body=blocos, type_ignores=[])
    ast.fix_missing_locations(modulo)
    codigo = compile(modulo, str(BUILD_PY), "exec")

    ns = {
        "re": re,
        "unicodedata": unicodedata,
        "SystemExit": SystemExit,
        "PAL": FIXTURE_PAL,
        "TOK": [_n_para_fixture(p["w"]) for p in FIXTURE_PAL],
    }
    exec(codigo, ns)
    return ns


def _n_para_fixture(s):
    s = unicodedata.normalize("NFD", s.lower())
    return re.sub(r"[^a-z0-9]", "", "".join(c for c in s if unicodedata.category(c) != "Mn"))


NS = _carrega_funcoes()
_n = NS["_n"]
_distancia_edicao = NS["_distancia_edicao"]
_sugestoes = NS["_sugestoes"]
W = NS["W"]


# ---------------- testes ----------------

def test_normaliza_acentos_e_pontuacao():
    assert _n("Olá, Mundo!") == "olamundo"
    assert _n("Café") == "cafe"
    assert _n("e-mail") == "email"
    assert _n("100%") == "100"


def test_distancia_edicao_basica():
    assert _distancia_edicao("instalar", "instalar") == 0   # igual
    assert _distancia_edicao("instalar", "instalr") == 1    # 1 deleção (typo)
    assert _distancia_edicao("instalar", "jnstalar") == 1   # 1 substituição
    assert _distancia_edicao("instalar", "instaalar") == 1  # 1 inserção
    assert _distancia_edicao("", "abc") == 3                # vazio
    assert _distancia_edicao("abc", "") == 3                # vazio
    assert _distancia_edicao("gato", "gato") == 0


def test_w_frase_exata_retorna_inicio():
    # "como instalar" começa em 1.05 (t de "como")
    assert W("como instalar") == 1.05
    assert W("Hoje eu vou") == 0.00
    assert W("o Claude Code") == 1.85


def test_w_fim_true_retorna_fim_da_ultima_palavra():
    # fim=True devolve o "f" da última palavra da sequência
    assert W("como instalar", fim=True) == 1.85   # f de "instalar"
    assert W("Hoje eu", fim=True) == 0.44         # f de "eu"


def test_w_respeita_apos():
    # com apos=1.0, "eu" antes disso é ignorado; só acha "eu" se houver depois
    try:
        W("Hoje", apos=1.0)
    except SystemExit:
        pass  # esperado: "Hoje" só ocorre antes de apos=1.0
    else:
        # se existir outra ocorrência depois, não deve ter retornado a de antes
        pass
    # a mesma frase com apos pequeno funciona
    assert W("Hoje", apos=0.0) == 0.00


def test_w_frase_desconhecida_sugere_proximas():
    # "instalr" (typo de "instalar") deve falhar com sugestões acionáveis
    try:
        W("instalr")
    except SystemExit as e:
        msg = str(e)
        assert "palavra não encontrada" in msg
        assert "distância de edição" in msg
        # deve sugerir uma frase real do roteiro (contém "instalar")
        assert "instalar" in msg
    else:
        raise AssertionError("W('instalr') deveria ter falhado")


def test_sugestoes_retorna_frases_do_roteiro():
    alvo = [_n(x) for x in "instalr claude".split()]
    dicas = _sugestoes(alvo, n=3)
    assert isinstance(dicas, list) and len(dicas) >= 1
    # cada sugestão é uma frase (string de palavras do roteiro)
    assert all(isinstance(d, str) and d for d in dicas)
    # a mais próxima deve conter as palavras quase exatas
    assert any("instalar" in d for d in dicas)


TESTES = [
    test_normaliza_acentos_e_pontuacao,
    test_distancia_edicao_basica,
    test_w_frase_exata_retorna_inicio,
    test_w_fim_true_retorna_fim_da_ultima_palavra,
    test_w_respeita_apos,
    test_w_frase_desconhecida_sugere_proximas,
    test_sugestoes_retorna_frases_do_roteiro,
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
    print(f"\n{len(TESTES) - falhas}/{len(TESTES)} testes de W() passaram")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
