# -*- coding: utf-8 -*-
"""TESTE DE INTEGRAÇÃO — CENAS.PY COM NÚCLEO DE COMPOSIÇÃO E SOUNDBUS
Arquivo: projetos/dr-gestao/branding/scripts/test_integracao_cenas.py
"""

import unittest
from pathlib import Path
import sys, types

AQUI = Path(__file__).parent
sys.path.insert(0, str(AQUI))

from estagio import StageStateManager, CompositionManager, CompositionPreset, ContentArea
from som import RobustSoundBus


class TestIntegracaoCenas(unittest.TestCase):

    def setUp(self):
        self.dur = 32.5
        self.stage = StageStateManager(duracao_total=self.dur, id_viewport="palco")
        self.comp = CompositionManager(self.stage)
        self.audio = RobustSoundBus(track_base=20)

        # Contexto simulado do build.py
        sons_dir = Path("projetos/dr-gestao/episodios/teste-piloto-parte-02/workspace/sons")
        self.ctx = {
            "AQUI": sons_dir.parent,
            "CFG": {"rosto": [960, 420], "marca": {"destaque": "#1d7cf2"}},
            "PAL": [{"t": 0.0, "f": 1.0, "w": "teste"}],
            "HTML": [],
            "JS": [],
            "AUD": [],
            "CAMZ": [],
            "PALCO": [],
            "MISS": [],
            "BATES": [],
            "CENAS_B": [],
            "r3": lambda x: round(x, 3),
            "nid": lambda p="e": f"{p}_mock",
            "clip": lambda de, ate, html, estilo="", cls="ov", track=1: "mock_clip",
            "sfx": lambda nome, t, vol=0.5, dur=None: None,
            "conta": lambda sel, t0, t1, a, b, pre="", suf="", casas=0: None,
            "tile": lambda nome, px=84: f"<tile {nome}>",
            "barra_progresso": lambda p, **kw: "<progresso>",
            "stepper": lambda et, at: "<stepper>",
            "STAGE_MGR": self.stage,
            "COMP_MGR": self.comp,
            "SOUND_BUS": self.audio
        }

        # Carrega cenas.py com o contexto
        cenas_code = (AQUI / "cenas.py").read_text(encoding="utf-8")
        self.cn_module = {}
        self.cn_module.update(self.ctx)
        exec(compile(cenas_code, str(AQUI / "cenas.py"), "exec"), self.cn_module)
        self.cn = types.SimpleNamespace(**self.cn_module)
        self.cn.conecta_nucleo(self.stage, self.comp, self.audio)

    def test_01_split_stage_registra_geometria_e_content_area(self):
        sid, area = self.cn.split_stage(5.0, 15.0, proporcao="33/67", lado="esq", com_margem=True, retornar_ao_solo=False)

        self.assertIsNotNone(area)
        self.assertEqual(area.width, 1200)
        self.assertEqual(area.left, 672)

        # Valida que o container DOM foi criado
        self.assertTrue(any('class="clip cn-split-area"' in h for h in self.ctx["HTML"]))

        # Compila a timeline do palco
        js, ivs, estado = self.stage.compilar()
        self.assertEqual(estado.props["left"], 48)
        self.assertEqual(estado.props["width"], 584)
        self.assertEqual(estado.props["borderRadius"], "24px")

    def test_02_pip_stage_sem_reset_permite_transicao_continua(self):
        # 1. Entra em PiP em 5.0s até 12.0s sem reset
        self.cn.pip_stage(5.0, 12.0, midia="", pip_pos="inf-dir", retornar_ao_solo=False)

        # 2. Em 12.0s, transiciona direto para Solo Fullscreen usando o preset oficial
        vp_solo, _ = CompositionPreset.solo_fullscreen()
        self.stage.transicionar(12.0, 0.6, **vp_solo.props)

        js, ivs, estado = self.stage.compilar()
        tweens = [l for l in js if 'tl.to("#palco"' in l]
        # Devem existir exatamente 2 tweens: entrada no PiP e saída para solo
        self.assertEqual(len(tweens), 2)
        self.assertTrue(estado.is_solo_fullscreen())

    def test_03_bate_anima_base_preservando_palco(self):
        # Coloca o palco em split
        self.stage.transicionar(0.0, 0.0, left=48, width=584)
        # Executa bate() em t=2.0s
        self.cn.bate(2.0, s=1.08, segura=0.9)

        js, ivs, estado = self.stage.compilar()

        # O tween do bate() deve ter sido emitido para #base, não para #palco
        self.assertTrue(any('tl.fromTo("#base"' in l for l in self.ctx["JS"]))
        self.assertTrue(any('tl.to("#base"' in l for l in self.ctx["JS"]))
        # A geometria de #palco continua sendo 584px
        self.assertEqual(estado.props["width"], 584)

    def test_04_som_roteia_para_robust_sound_bus(self):
        self.cn._som("whoosh_curto", 1.5, vol=0.5, event_id="teste_whoosh")
        eventos = self.audio.resolver_eventos()

        self.assertEqual(len(eventos), 1)
        self.assertEqual(eventos[0].event_id, "teste_whoosh")
        self.assertEqual(eventos[0].som, "whoosh_curto")
        self.assertEqual(eventos[0].t, 1.5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
