# -*- coding: utf-8 -*-
"""TESTE DE INTEGRAÇÃO — CENAS.PY COM NÚCLEO DE COMPOSIÇÃO E SOUNDBUS
Arquivo: projetos/dr-gestao/branding/scripts/test_integracao_cenas.py

Valida a resolução de som (_som_existe/_som) de forma isolada e autônoma,
não dependendo de WAVs locais ignorados em branding/sons/. Usa
tempfile.TemporaryDirectory() para criar fixtures temporárias de WAV nos
locais esperados: AQUI/sons/ e AQUI.parent/sons/, bem como o fallback para
reserva quando nenhum WAV existe.
"""

import unittest
import tempfile
from pathlib import Path
import sys, types

AQUI = Path(__file__).parent
sys.path.insert(0, str(AQUI))

from estagio import StageStateManager, CompositionManager, CompositionPreset, ContentArea
from som import RobustSoundBus


def _montar_contexto_cenas(aqui_path, stage, comp, audio):
    """Monta o contexto de execução de cenas.py com AQUI apontando para
    `aqui_path` (tempdir), permitindo testar resolução de som isoladamente."""
    return {
        "AQUI": aqui_path,
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
        "STAGE_MGR": stage,
        "COMP_MGR": comp,
        "SOUND_BUS": audio,
    }


def _carregar_cenas_com_aqui(aqui_path, stage, comp, audio):
    """Carrega cenas.py injetando AQUI = aqui_path e conecta o núcleo."""
    cenas_code = (AQUI / "cenas.py").read_text(encoding="utf-8")
    ctx = _montar_contexto_cenas(aqui_path, stage, comp, audio)
    module = {}
    module.update(ctx)
    exec(compile(cenas_code, str(AQUI / "cenas.py"), "exec"), module)
    cn = types.SimpleNamespace(**module)
    cn.conecta_nucleo(stage, comp, audio)
    return cn, ctx


class TestIntegracaoCenas(unittest.TestCase):

    def setUp(self):
        self.dur = 32.5
        self.stage = StageStateManager(duracao_total=self.dur, id_viewport="palco")
        self.comp = CompositionManager(self.stage)
        self.audio = RobustSoundBus(track_base=20)
        self.cn, self.ctx = _carregar_cenas_com_aqui(AQUI, self.stage, self.comp, self.audio)

    def test_01_split_stage_registra_geometria_e_content_area(self):
        sid, area = self.cn.split_stage(5.0, 15.0, proporcao="33/67", lado="esq", com_margem=True, retornar_ao_solo=False)

        self.assertIsNotNone(area)
        self.assertEqual(area.width, 1200)
        self.assertEqual(area.left, 672)

        self.assertTrue(any('class="clip cn-split-area"' in h for h in self.ctx["HTML"]))

        js, ivs, estado = self.stage.compilar()
        self.assertEqual(estado.props["left"], 48)
        self.assertEqual(estado.props["width"], 584)
        self.assertEqual(estado.props["borderRadius"], "24px")

    def test_02_pip_stage_sem_reset_permite_transicao_continua(self):
        self.cn.pip_stage(5.0, 12.0, midia="", pip_pos="inf-dir", retornar_ao_solo=False)

        vp_solo, _ = CompositionPreset.solo_fullscreen()
        self.stage.transicionar(12.0, 0.6, **vp_solo.props)

        js, ivs, estado = self.stage.compilar()
        tweens = [l for l in js if 'tl.to("#palco"' in l]
        self.assertEqual(len(tweens), 2)
        self.assertTrue(estado.is_solo_fullscreen())

    def test_03_bate_anima_base_preservando_palco(self):
        self.stage.transicionar(0.0, 0.0, left=48, width=584)
        self.cn.bate(2.0, s=1.08, segura=0.9)

        js, ivs, estado = self.stage.compilar()

        self.assertTrue(any('tl.fromTo("#base"' in l for l in self.ctx["JS"]))
        self.assertTrue(any('tl.to("#base"' in l for l in self.ctx["JS"]))
        self.assertEqual(estado.props["width"], 584)

    # ------------------------------------------------------------------
    # Autonomia dos testes de áudio (fixtures temporárias via tempfile)
    # ------------------------------------------------------------------

    def _gravar_wav_fixture(self, pasta: Path, nome: str):
        """Cria um arquivo WAV válido (cabeçalho mínimo) em `pasta/nome.wav`."""
        pasta.mkdir(parents=True, exist_ok=True)
        wav = pasta / f"{nome}.wav"
        # Cabeçalho RIFF/WAVE mínimo (44 bytes) + um byte de dados de áudio.
        wav.write_bytes(
            b"RIFF" + (36).to_bytes(4, "little") + b"WAVE"
            + b"fmt " + (16).to_bytes(4, "little") + (1).to_bytes(2, "little")
            + (1).to_bytes(2, "little") + (16000).to_bytes(4, "little")
            + (16000).to_bytes(4, "little") + (2).to_bytes(2, "little")
            + (16).to_bytes(2, "little") + b"data" + (1).to_bytes(4, "little") + b"\x00"
        )
        return wav

    def test_04a_som_resolve_em_aqui_sons(self):
        """(a) Resolução em AQUI/'sons' (branding/scripts/sons)."""
        with tempfile.TemporaryDirectory() as td:
            aqui = Path(td)
            self._gravar_wav_fixture(aqui / "sons", "whoosh_curto")
            cn, _ = _carregar_cenas_com_aqui(aqui, self.stage, self.comp, self.audio)
            cn._som("whoosh_curto", 1.5, vol=0.5, event_id="teste_whoosh_a")
            eventos = self.audio.resolver_eventos()
            self.assertEqual(len(eventos), 1)
            self.assertEqual(eventos[0].som, "whoosh_curto")
            self.assertEqual(eventos[0].t, 1.5)

    def test_04b_som_resolve_em_aqui_parent_sons(self):
        """(b) Resolução em AQUI.parent/'sons' (branding/sons)."""
        with tempfile.TemporaryDirectory() as td:
            aqui = Path(td) / "nested"  # AQUI.parent/sons == td/sons
            self._gravar_wav_fixture(Path(td) / "sons", "whoosh_curto")
            cn, _ = _carregar_cenas_com_aqui(aqui, self.stage, self.comp, self.audio)
            cn._som("whoosh_curto", 2.0, vol=0.5, event_id="teste_whoosh_b")
            eventos = self.audio.resolver_eventos()
            self.assertEqual(len(eventos), 1)
            self.assertEqual(eventos[0].som, "whoosh_curto")
            self.assertEqual(eventos[0].t, 2.0)

    def test_04c_som_fallback_reserva_quando_nao_existe(self):
        """(c) Fallback para reserva ('clique2') quando o WAV não existe."""
        with tempfile.TemporaryDirectory() as td:
            aqui = Path(td)  # sem diretório 'sons' nem WAV
            cn, _ = _carregar_cenas_com_aqui(aqui, self.stage, self.comp, self.audio)
            cn._som("som_inexistente_xyz", 3.0, vol=0.5, event_id="teste_whoosh_c")
            eventos = self.audio.resolver_eventos()
            self.assertEqual(len(eventos), 1)
            self.assertEqual(eventos[0].som, "clique2")
            self.assertEqual(eventos[0].t, 3.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
