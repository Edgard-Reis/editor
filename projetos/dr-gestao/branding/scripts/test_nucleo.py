# -*- coding: utf-8 -*-
"""SUÍTE DE TESTES UNITÁRIOS — NÚCLEO AUDIOVISUAL DRIFIT EDITOR
Arquivo: projetos/dr-gestao/branding/scripts/test_nucleo.py

Valida os 11 cenários obrigatórios exigidos na Autorização de Implementação - Fase 1.
"""

import unittest
from pathlib import Path
import sys

# Garante importação dos módulos locais
AQUI = Path(__file__).parent
sys.path.insert(0, str(AQUI))

from estagio import (
    StageStateManager, CompositionManager, CompositionPreset,
    ViewportState, TimelineConflictError
)
from som import RobustSoundBus, SoundEvent


class TestNucleoAudiovisual(unittest.TestCase):

    def setUp(self):
        self.duracao_mock = 60.0

    # ---------------------------------------------------------------------------------
    # 1. Estado inicial em tela cheia
    # ---------------------------------------------------------------------------------
    def test_01_estado_inicial_tela_cheia(self):
        sm = StageStateManager(duracao_total=self.duracao_mock)
        js, ivs, estado = sm.compilar()

        # O estado inicial compilado deve ser exatamente Solo Fullscreen
        self.assertTrue(estado.is_solo_fullscreen(), "Estado inicial deve ser Solo Fullscreen")
        self.assertEqual(estado.props["left"], 0)
        self.assertEqual(estado.props["top"], 0)
        self.assertEqual(estado.props["width"], 1920)
        self.assertEqual(estado.props["height"], 1080)
        self.assertEqual(estado.props["opacity"], 1.0)
        # Como permaneceu em solo o tempo todo, nenhum intervalo dinâmico de crop/movimento é emitido
        self.assertEqual(ivs, [], "Trecho exclusivamente solo fullscreen não gera intervalos dinâmicos")

    # ---------------------------------------------------------------------------------
    # 2. Transição de tela cheia para Split 33/67
    # ---------------------------------------------------------------------------------
    def test_02_transicao_tela_cheia_para_split_33_67(self):
        sm = StageStateManager(duracao_total=self.duracao_mock)
        cm = CompositionManager(sm)

        # Transição em t=10.0 com 0.6s de duração
        area = cm.aplicar_preset(10.0, 0.6, "split_33_67", dur_permanencia=10.0, com_margem=True)
        js, ivs, estado = sm.compilar()

        # Valida geometria do apresentador
        self.assertEqual(estado.props["left"], 48)
        self.assertEqual(estado.props["top"], 48)
        self.assertEqual(estado.props["width"], 584)
        self.assertEqual(estado.props["height"], 984)
        self.assertEqual(estado.props["borderRadius"], "24px")

        # Valida área de conteúdo disponível para motion
        self.assertIsNotNone(area)
        self.assertEqual(area.left, 672)
        self.assertEqual(area.width, 1200)
        # Consistência: 48 + 584 + 40(gap) + 1200 + 48 = 1920
        self.assertEqual(48 + 584 + 40 + 1200 + 48, 1920)

        # Verifica se gerou comando GSAP correto para #palco
        self.assertTrue(any('tl.to("#palco"' in l and 'width:584' in l for l in js))

    # ---------------------------------------------------------------------------------
    # 3. Transição direta de Split para PiP (Sem reset intermediário)
    # ---------------------------------------------------------------------------------
    def test_03_transicao_direta_split_para_pip(self):
        sm = StageStateManager(duracao_total=self.duracao_mock)
        cm = CompositionManager(sm)

        # Split em t=10.0
        cm.aplicar_preset(10.0, 0.5, "split_33_67", dur_permanencia=8.0)
        # Transição DIRETA para PiP em t=18.0
        cm.aplicar_preset(18.0, 0.6, "pip", posicao="inf-dir", w=540, h=304, margem=48)

        js, ivs, estado = sm.compilar()

        # O estado final após as duas transições deve ser PiP no canto inferior direito
        self.assertEqual(estado.props["left"], 1920 - 540 - 48) # 1332
        self.assertEqual(estado.props["top"], 1080 - 304 - 48)   # 728
        self.assertEqual(estado.props["width"], 540)
        self.assertEqual(estado.props["height"], 304)

        # Verifica que houve 2 comandos de tween (um pro split e outro direto pro PiP)
        tweens = [l for l in js if 'tl.to("#palco"' in l]
        self.assertEqual(len(tweens), 2, "Devem existir exatamente 2 transições de interpolação")

    # ---------------------------------------------------------------------------------
    # 4. Transição de PiP para tela cheia
    # ---------------------------------------------------------------------------------
    def test_04_transicao_pip_para_tela_cheia(self):
        sm = StageStateManager(duracao_total=self.duracao_mock)
        cm = CompositionManager(sm)

        # Entra em PiP em t=10.0
        cm.aplicar_preset(10.0, 0.5, "pip")
        # Retorna para Solo em t=20.0 com 0.6s de transição
        cm.aplicar_preset(20.0, 0.6, "solo")

        js, ivs, estado = sm.compilar()

        self.assertTrue(estado.is_solo_fullscreen(), "Estado final deve voltar rigorosamente a Solo Fullscreen")
        self.assertEqual(estado.props["width"], 1920)
        self.assertEqual(estado.props["left"], 0)

    # ---------------------------------------------------------------------------------
    # 5. Preservação de propriedades não alteradas (Herança de Estado)
    # ---------------------------------------------------------------------------------
    def test_05_preservacao_propriedades_nao_alteradas(self):
        sm = StageStateManager(duracao_total=self.duracao_mock)

        # Passo 1: Customiza borderRadius e border junto com largura
        sm.transicionar(10.0, 0.5, left=100, top=100, width=800, height=600,
                        borderRadius="32px", border="4px solid #fff")
        # Passo 2: Move apenas posição left/top, sem redeclarar borderRadius nem border
        sm.transicionar(20.0, 0.5, left=200, top=150)

        js, ivs, estado = sm.compilar()

        # O estado após o passo 2 DEVE reter o borderRadius e border configurados no passo 1
        self.assertEqual(estado.props["borderRadius"], "32px")
        self.assertEqual(estado.props["border"], "4px solid #fff")
        self.assertEqual(estado.props["width"], 800)
        self.assertEqual(estado.props["left"], 200)
        self.assertEqual(estado.props["top"], 150)

    # ---------------------------------------------------------------------------------
    # 6. Detecção de conflitos sobre a mesma propriedade do mesmo elemento
    # ---------------------------------------------------------------------------------
    def test_06_deteccao_conflitos_mesma_propriedade(self):
        sm = StageStateManager(duracao_total=self.duracao_mock)

        # Transição 1 em width: [10.0s -> 10.8s]
        sm.transicionar(10.0, 0.8, width=600, label="t1")
        # Transição 2 em width: [10.5s -> 11.2s] (COLISÃO com a Transição 1!)
        sm.transicionar(10.5, 0.7, width=800, label="t2")

        with self.assertRaises(TimelineConflictError):
            sm.compilar()

    # ---------------------------------------------------------------------------------
    # 7. Permissão de animações paralelas em elementos diferentes ou props diferentes
    # ---------------------------------------------------------------------------------
    def test_07_permissao_animacoes_paralelas(self):
        sm = StageStateManager(duracao_total=self.duracao_mock)

        # Viewport do apresentador altera posição 'left': [10.0s -> 10.6s]
        sm.transicionar(10.0, 0.6, left=80, label="palco_move")

        # Elemento externo independente (ex: card de motion) animando simultaneamente: [10.0s -> 10.6s]
        sm.registrar_animacao_externa("split_card", "opacity", 10.0, 0.6)
        sm.registrar_animacao_externa("split_card", "x", 10.0, 0.6)

        # NÃO deve levantar exceção, pois os alvos são distintos
        try:
            js, ivs, estado = sm.compilar()
            sucesso = True
        except TimelineConflictError:
            sucesso = False

        self.assertTrue(sucesso, "Animações simultâneas em elementos distintos devem ser aceitas com sucesso")

    # ---------------------------------------------------------------------------------
    # 8. Ordenação de keyframes independentemente da ordem de chamada
    # ---------------------------------------------------------------------------------
    def test_08_ordenacao_keyframes_independente_ordem_chamada(self):
        sm = StageStateManager(duracao_total=self.duracao_mock)

        # Chamadas propositalmente fora de ordem cronológica:
        sm.transicionar(30.0, 0.5, left=0, top=0, width=1920, height=1080, label="retorno")
        sm.transicionar(10.0, 0.5, left=100, width=800, label="split")
        sm.transicionar(20.0, 0.5, left=500, width=540, label="pip")

        js, ivs, estado = sm.compilar()

        # Extrai os tempos de início dos tweens gerados
        import re
        tempos_tweens = [float(re.search(r',\s*([\d\.]+)\);', l).group(1)) for l in js if 'tl.to(' in l]
        self.assertEqual(tempos_tweens, [10.0, 20.0, 30.0], "Tweens devem ser gerados em ordem cronológica estrita")

    # ---------------------------------------------------------------------------------
    # 9. Cálculo correto dos intervalos dinâmicos, incluindo retorno à tela cheia
    # ---------------------------------------------------------------------------------
    def test_09_calculo_intervalos_dinamicos_render_rapido(self):
        sm = StageStateManager(duracao_total=100.0)

        # Estado especial (Split) de 10.0 a 25.0
        sm.transicionar(10.0, 0.5, width=600)
        # Retorno a tela cheia inicia em 25.0 com duração de 0.6s (termina em 25.6s)
        sm.transicionar(25.0, 0.6, width=1920, left=0, top=0, height=1080)

        js, ivs, estado = sm.compilar()

        # O intervalo dinâmico retornado deve abranger de 10.0 até 25.6s integralmente!
        self.assertEqual(len(ivs), 1)
        self.assertAlmostEqual(ivs[0][0], 10.0, places=2)
        self.assertAlmostEqual(ivs[0][1], 25.6, places=2,
                               msg="Intervalo dinâmico deve incluir a duração integral da transição de retorno")

    # ---------------------------------------------------------------------------------
    # 10. Deduplicação sem eliminar eventos sonoros legítimos
    # ---------------------------------------------------------------------------------
    def test_10_deduplicacao_soundbus_sem_eliminar_eventos_legitimos(self):
        sb = RobustSoundBus(track_base=20)

        # 1. Evento duplicado acidentalmente (mesmo event_id e mesmo som):
        sb.registrar("tr_split_01", "whoosh_curto", t=10.0, modo="auto")
        sb.registrar("tr_split_01", "whoosh_curto", t=10.0, modo="auto")

        # 2. Eventos legítimos distintos que usam o mesmo arquivo .wav em instantes próximos:
        sb.registrar("item_lista_1", "clique2", t=12.0)
        sb.registrar("item_lista_2", "clique2", t=12.1)

        compilados = sb.compilar()

        # Esperado: 3 eventos no total (1 whoosh desduplicado + 2 cliques legítimos preservados)
        self.assertEqual(len(compilados), 3)

        # Verifica que cada áudio recebeu uma track diferente
        tracks = [c["track"] for c in compilados]
        self.assertEqual(len(tracks), len(set(tracks)), "Cada tag de áudio deve ter track index único")
        self.assertEqual(tracks, [20, 21, 22])

    # ---------------------------------------------------------------------------------
    # 11. Prioridade de eventos explícitos sobre automáticos independente da ordem
    # ---------------------------------------------------------------------------------
    def test_11_prioridade_explicito_sobre_automatico(self):
        # Caso A: Registro explícito chamado DEPOIS do automático
        sb1 = RobustSoundBus(track_base=20)
        sb1.registrar_automatico("transicao_abertura", "whoosh_curto", t=5.0, volume=0.3)
        sb1.registrar_explicito("transicao_abertura", "swish", t=5.05, volume=0.6)

        eventos1 = sb1.resolver_eventos()
        self.assertEqual(len(eventos1), 1)
        self.assertEqual(eventos1[0].modo, "explicit")
        self.assertEqual(eventos1[0].som, "swish")
        self.assertEqual(eventos1[0].volume, 0.6)

        # Caso B: Registro explícito chamado ANTES do automático
        sb2 = RobustSoundBus(track_base=20)
        sb2.registrar_explicito("transicao_abertura", "swish", t=5.05, volume=0.6)
        sb2.registrar_automatico("transicao_abertura", "whoosh_curto", t=5.0, volume=0.3)

        eventos2 = sb2.resolver_eventos()
        self.assertEqual(len(eventos2), 1)
        self.assertEqual(eventos2[0].modo, "explicit")
        self.assertEqual(eventos2[0].som, "swish")
        self.assertEqual(eventos2[0].volume, 0.6)


if __name__ == "__main__":
    unittest.main(verbosity=2)
