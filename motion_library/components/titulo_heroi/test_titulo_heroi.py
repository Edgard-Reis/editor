# -*- coding: utf-8 -*-
"""Suíte de Testes Unitários do Componente T10 — Título Herói por Letra.
Drifit Editor — Fase 5.2 (Homologação).

Testa:
- Geração HTML e individualização de letras (.th-l) e palavras (.th-w).
- Normalização Unicode NFC e integridade de acentos da língua portuguesa.
- Escape seguro contra entidades HTML.
- Preservação de espaços (simples e múltiplos) e quebras de linha explícitas.
- Validação estrita de identificadores (clip_id e elemento_id).
- Rejeição defensiva de parâmetros numéricos inválidos (NaN, infinitos, limites mínimos).
- Validação de easing GSAP.
- Correspondência exata entre o ID do HTML e o seletor da animação GSAP.
- Determinismo de saída para os mesmos parâmetros.
"""

import math
import sys
import unittest
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from titulo_heroi import animar_titulo, gerar_html_titulo


class TestTituloHeroiHTML(unittest.TestCase):
    """Testes de geração de HTML e estruturação de texto."""

    def test_geracao_html_basica_letras_individualizadas(self):
        """Testa geração de container e letras isoladas com .th-l."""
        html = gerar_html_titulo("Chave", clip_id="vc5", elemento_id="t2", classe_container="vc-t2")
        self.assertTrue(html.startswith('<div class="vc-t2" id="vc5-t2">'))
        self.assertTrue(html.endswith("</div>"))
        # Verifica 5 letras individualizadas em .th-l
        for char in "Chave":
            self.assertIn(f'<span class="th-l">{char}</span>', html)
        # Verifica container de palavra .th-w
        self.assertIn('<span class="th-w">', html)

    def test_geracao_sem_classe_container(self):
        """Testa geração sem classe CSS opcional no container."""
        html = gerar_html_titulo("Minutagem", clip_id="cm9", elemento_id="t2")
        self.assertTrue(html.startswith('<div id="cm9-t2">'))
        self.assertTrue(html.endswith("</div>"))
        self.assertNotIn('class=""', html)
        self.assertNotIn('class="None"', html)

    def test_normalizacao_unicode_nfc_acentos_portugues(self):
        """Testa se caracteres decompostos (NFD) são convertidos para NFC sem quebra de acento."""
        # 'Ação' em formato decomposto NFD (A + c + cedilha combinante + a + til combinante + o)
        texto_nfd = unicodedata.normalize("NFD", "Ação Operacional")
        html = gerar_html_titulo(texto_nfd, clip_id="c1", elemento_id="t1")
        # Garante que no HTML resultante as letras 'ç' e 'ã' estão consolidadas em span único
        self.assertIn('<span class="th-l">ç</span>', html)
        self.assertIn('<span class="th-l">ã</span>', html)
        # Verifica outras letras da frase
        self.assertIn('<span class="th-l">A</span>', html)
        self.assertIn('<span class="th-l">o</span>', html)

    def test_caracteres_acentuados_diversos(self):
        """Testa diversos acentos da língua portuguesa (á, é, í, ó, ú, â, ê, ô, ã, õ, ç, À)."""
        texto = "Produção Éficiência Ótimo Café Útil Gestão"
        html = gerar_html_titulo(texto, clip_id="clip_pt", elemento_id="t2")
        for char in ["ç", "ã", "É", "Ó", "é", "Ú", "ã"]:
            self.assertIn(f'<span class="th-l">{char}</span>', html)

    def test_escape_html_caracteres_especiais(self):
        """Testa escape seguro de &, <, >, aspas contra quebra de layout ou XSS."""
        texto = "Preço & Lucro < 100% \"Premium\""
        html = gerar_html_titulo(texto, clip_id="c_esc", elemento_id="t2")
        self.assertIn('<span class="th-l">&amp;</span>', html)
        self.assertIn('<span class="th-l">&lt;</span>', html)
        self.assertIn('<span class="th-l">&quot;</span>', html)
        self.assertNotIn('<span class="th-l">&</span>', html)
        self.assertNotIn('<span class="th-l"><</span>', html)

    def test_preservacao_espacos_simples_e_multiplos(self):
        """Testa que palavras são separadas por espaços simples e múltiplos espaços viram &nbsp;."""
        texto = "Alta  Minutagem"  # dois espaços
        html = gerar_html_titulo(texto, clip_id="c_sp", elemento_id="t2")
        self.assertIn('<span class="th-w">&nbsp;</span>', html)

    def test_quebra_de_linha_explicita(self):
        """Testa que quebras de linha explícitas (\\n) são convertidas em <br/>."""
        texto = "Virada de\nChave"
        html = gerar_html_titulo(texto, clip_id="c_br", elemento_id="t2")
        self.assertIn("<br/>", html)
        # As letras de ambas as linhas devem existir individualizadas em .th-l
        for char in "ViradadeChave":
            self.assertIn(f'<span class="th-l">{char}</span>', html)
        # O elemento <br/> deve separar as linhas
        partes = html.split("<br/>")
        self.assertEqual(len(partes), 2)

    def test_validacao_tipo_texto(self):
        """Testa rejeição de texto não string."""
        with self.assertRaises(TypeError):
            gerar_html_titulo(12345, clip_id="c1", elemento_id="t1")  # type: ignore


class TestTituloHeroiValidacaoIDs(unittest.TestCase):
    """Testes de validação de identificadores (clip_id e elemento_id)."""

    def test_ids_validos(self):
        """Testa identificadores que atendem a [a-zA-Z0-9_-]+."""
        html = gerar_html_titulo("OK", clip_id="vc-5_scene", elemento_id="t_02")
        self.assertIn('id="vc-5_scene-t_02"', html)

    def test_ids_invalidos_rejeitados(self):
        """Testa rejeição de IDs com espaços, caracteres especiais ou vazios."""
        invalidos = ["", "clip id", "clip.id", "clip#1", "clip/sub", "<tag>"]
        for inv in invalidos:
            with self.subTest(id_invalido=inv):
                with self.assertRaises(ValueError):
                    gerar_html_titulo("Teste", clip_id=inv, elemento_id="t2")
                with self.assertRaises(ValueError):
                    gerar_html_titulo("Teste", clip_id="c1", elemento_id=inv)
                with self.assertRaises(ValueError):
                    animar_titulo(clip_id=inv, elemento_id="t2", t_inicio=1.0)
                with self.assertRaises(ValueError):
                    animar_titulo(clip_id="c1", elemento_id=inv, t_inicio=1.0)


class TestTituloHeroiAnimacao(unittest.TestCase):
    """Testes de geração de comandos GSAP e validação de parâmetros de animação."""

    def test_geracao_gsap_padrao(self):
        """Testa geração de instrução GSAP tl.fromTo com parâmetros nominais."""
        cmd = animar_titulo(
            clip_id="vc5",
            elemento_id="t2",
            t_inicio=25.94,
            duration=0.38,
            stagger=0.04,
            y=44.0,
            blur=14.0,
            ease="power3.out"
        )
        self.assertEqual(
            cmd,
            'tl.fromTo("#vc5-t2 .th-l",{opacity:0,y:44,filter:"blur(14px)"},{opacity:1,y:0,filter:"blur(0px)",duration:0.38,stagger:0.04,ease:"power3.out"},25.94);'
        )

    def test_geracao_gsap_alta_minutagem(self):
        """Testa geração para a cena Alta Minutagem."""
        cmd = animar_titulo(
            clip_id="cm9",
            elemento_id="t2",
            t_inicio=26.90,
            duration=0.36,
            stagger=0.032,
            y=32.0,
            blur=10.0,
            ease="power3.out"
        )
        self.assertEqual(
            cmd,
            'tl.fromTo("#cm9-t2 .th-l",{opacity:0,y:32,filter:"blur(10px)"},{opacity:1,y:0,filter:"blur(0px)",duration:0.36,stagger:0.032,ease:"power3.out"},26.9);'
        )

    def test_rejeicao_parametros_numericos_invalidos(self):
        """Testa rejeição de NaN, Infinito e valores abaixo do mínimo aceito."""
        # t_inicio negativo ou infinito
        with self.assertRaises(ValueError):
            animar_titulo(clip_id="c1", elemento_id="t2", t_inicio=-0.1)
        with self.assertRaises(ValueError):
            animar_titulo(clip_id="c1", elemento_id="t2", t_inicio=float("nan"))
        with self.assertRaises(ValueError):
            animar_titulo(clip_id="c1", elemento_id="t2", t_inicio=float("inf"))

        # duration <= 0 ou inválida
        with self.assertRaises(ValueError):
            animar_titulo(clip_id="c1", elemento_id="t2", t_inicio=1.0, duration=0.0)
        with self.assertRaises(ValueError):
            animar_titulo(clip_id="c1", elemento_id="t2", t_inicio=1.0, duration=-0.5)

        # stagger negativo
        with self.assertRaises(ValueError):
            animar_titulo(clip_id="c1", elemento_id="t2", t_inicio=1.0, stagger=-0.01)

        # blur negativo
        with self.assertRaises(ValueError):
            animar_titulo(clip_id="c1", elemento_id="t2", t_inicio=1.0, blur=-1.0)

        # y infinito
        with self.assertRaises(ValueError):
            animar_titulo(clip_id="c1", elemento_id="t2", t_inicio=1.0, y=float("inf"))

    def test_validacao_easing_gsap(self):
        """Testa aceitação de easings canônicos e rejeição de injeções inválidas."""
        easings_validos = ["power3.out", "power2.out", "power1.inOut", "expo.out", "back.out(1.7)"]
        for ea in easings_validos:
            with self.subTest(easing=ea):
                cmd = animar_titulo(clip_id="c1", elemento_id="t2", t_inicio=1.0, ease=ea)
                self.assertIn(f'ease:"{ea}"', cmd)

        easings_invalidos = ["power3.out; alert(1)", "power3.out\nmalicioso", 'power3.out"', "", "<script>"]
        for ea in easings_invalidos:
            with self.subTest(easing_invalido=ea):
                with self.assertRaises(ValueError):
                    animar_titulo(clip_id="c1", elemento_id="t2", t_inicio=1.0, ease=ea)


class TestTituloHeroiIntegracaoEDeterminismo(unittest.TestCase):
    """Testes de correspondência cruzada e determinismo."""

    def test_correspondencia_id_html_e_seletor_gsap(self):
        """Testa se o ID gerado no HTML é exatamente o mesmo referenciado pelo seletor GSAP."""
        clip_id = "cena_teste_01"
        elem_id = "titulo_principal"

        html = gerar_html_titulo("Texto de Prova", clip_id=clip_id, elemento_id=elem_id, classe_container="classe-c")
        cmd_gsap = animar_titulo(clip_id=clip_id, elemento_id=elem_id, t_inicio=5.0)

        esperado_id = f"{clip_id}-{elem_id}"
        esperado_seletor = f"#{esperado_id} .th-l"

        # Confirma presença do ID exato no HTML
        self.assertIn(f'id="{esperado_id}"', html)
        # Confirma presença do seletor exato no comando GSAP
        self.assertIn(f'tl.fromTo("{esperado_seletor}",', cmd_gsap)

    def test_determinismo_da_saida(self):
        """Garante que sucessivas execuções com mesmos parâmetros geram saídas binariamente idênticas."""
        for _ in range(5):
            h1 = gerar_html_titulo("Determinismo", clip_id="det_clip", elemento_id="t2", classe_container="c-det")
            h2 = gerar_html_titulo("Determinismo", clip_id="det_clip", elemento_id="t2", classe_container="c-det")
            self.assertEqual(h1, h2)

            g1 = animar_titulo(clip_id="det_clip", elemento_id="t2", t_inicio=12.345, duration=0.4, stagger=0.03)
            g2 = animar_titulo(clip_id="det_clip", elemento_id="t2", t_inicio=12.345, duration=0.4, stagger=0.03)
            self.assertEqual(g1, g2)


if __name__ == "__main__":
    unittest.main()
