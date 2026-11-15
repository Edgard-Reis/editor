# -*- coding: utf-8 -*-
"""NÚCLEO DE COMPOSIÇÃO AUDIOVISUAL — DRIFIT EDITOR (VÓRTEX)
Módulo: branding/scripts/estagio.py

Implementa:
- StageStateManager: Gerenciamento determinístico de geometria, estados temporais,
  validação de conflitos e cálculo de intervalos dinâmicos de palco (#palco).
- CompositionManager: Orquestração de empilhamento dinâmico (z-index) e
  disponibilidade/geometria de áreas de conteúdo gráfico (slots).
"""

from typing import Dict, List, Tuple, Optional, Any, Set
import copy
import math

class TimelineConflictError(ValueError):
    """Exceção levantada quando há colisões de interpolação na mesma propriedade de um elemento."""
    pass


class ViewportState:
    """Representa a geometria e acabamento da janela do apresentador na tela de 1920x1080."""
    PROPRIEDADES_PADRAO = {
        "left": 0,
        "top": 0,
        "width": 1920,
        "height": 1080,
        "borderRadius": "0px",
        "border": "0px solid transparent",
        "boxShadow": "none",
        "opacity": 1.0,
        "clipPath": "none"
    }

    def __init__(self, **kwargs):
        self.props = dict(self.PROPRIEDADES_PADRAO)
        for k, v in kwargs.items():
            if k in self.PROPRIEDADES_PADRAO:
                self.props[k] = v

    def clone(self) -> 'ViewportState':
        return ViewportState(**self.props)

    def is_solo_fullscreen(self) -> bool:
        """Verifica se a geometria corresponde rigorosamente ao Solo 16:9 Fullscreen padrão."""
        return (
            self.props["left"] == 0 and
            self.props["top"] == 0 and
            self.props["width"] == 1920 and
            self.props["height"] == 1080 and
            self.props["opacity"] == 1.0 and
            self.props["borderRadius"] in ("0px", "0", 0) and
            self.props["clipPath"] in ("none", "")
        )

    def __eq__(self, other):
        if not isinstance(other, ViewportState):
            return False
        return self.props == other.props


class ContentArea:
    """Define a geometria de uma área destinada ao conteúdo gráfico ou motion."""
    def __init__(self, id_area: str, left: int, top: int, width: int, height: int, descricao: str = ""):
        self.id_area = id_area
        self.left = left
        self.top = top
        self.width = width
        self.height = height
        self.descricao = descricao

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id_area,
            "left": self.left,
            "top": self.top,
            "width": self.width,
            "height": self.height,
            "descricao": self.descricao
        }

    def __repr__(self):
        return f"<ContentArea {self.id_area}: {self.width}x{self.height} at ({self.left},{self.top})>"


class CompositionPreset:
    """Presets matematicamente calibrados de layout para canvas 1920x1080."""
    @staticmethod
    def solo_fullscreen() -> Tuple[ViewportState, Optional[ContentArea]]:
        vp = ViewportState(left=0, top=0, width=1920, height=1080, borderRadius="0px", border="0px solid transparent", boxShadow="none", opacity=1.0)
        return vp, None

    @staticmethod
    def split_33_67(com_margem: bool = True) -> Tuple[ViewportState, ContentArea]:
        if com_margem:
            # Apresentador 33% (left: 48, top: 48, w: 584, h: 984)
            # Conteúdo 67% (left: 672, top: 48, w: 1200, h: 984) -> 48 + 584 + 40(gap) + 1200 + 48 = 1920
            vp = ViewportState(left=48, top=48, width=584, height=984, borderRadius="24px",
                               border="2px solid rgba(255,255,255,0.12)",
                               boxShadow="0 25px 60px rgba(0,0,0,0.45)", opacity=1.0)
            area = ContentArea("split_content", left=672, top=48, width=1200, height=984, descricao="Área gráfica direita 67% com margem")
        else:
            # Flush sem margem: 634px + 1286px = 1920px
            vp = ViewportState(left=0, top=0, width=634, height=1080, borderRadius="0px", border="0px solid transparent", boxShadow="none", opacity=1.0)
            area = ContentArea("split_content", left=634, top=0, width=1286, height=1080, descricao="Área gráfica direita 67% flush")
        return vp, area

    @staticmethod
    def split_50_50(com_margem: bool = False) -> Tuple[ViewportState, ContentArea]:
        if com_margem:
            vp = ViewportState(left=48, top=48, width=900, height=984, borderRadius="24px",
                               border="2px solid rgba(255,255,255,0.12)",
                               boxShadow="0 25px 60px rgba(0,0,0,0.45)", opacity=1.0)
            area = ContentArea("split_content", left=972, top=48, width=900, height=984, descricao="Área gráfica 50% com margem")
        else:
            vp = ViewportState(left=0, top=0, width=960, height=1080, borderRadius="0px", border="0px solid transparent", boxShadow="none", opacity=1.0)
            area = ContentArea("split_content", left=960, top=0, width=960, height=1080, descricao="Área gráfica 50% flush")
        return vp, area

    @staticmethod
    def pip(posicao: str = "inf-dir", w: int = 540, h: int = 304, margem: int = 48) -> Tuple[ViewportState, ContentArea]:
        if posicao == "inf-dir":
            left = 1920 - w - margem
            top = 1080 - h - margem
        elif posicao == "inf-esq":
            left = margem
            top = 1080 - h - margem
        elif posicao == "sup-dir":
            left = 1920 - w - margem
            top = margem
        else: # sup-esq
            left = margem
            top = margem

        vp = ViewportState(left=left, top=top, width=w, height=h, borderRadius="24px",
                           border="3px solid rgba(255,255,255,0.25)",
                           boxShadow="0 30px 80px rgba(0,0,0,0.55)", opacity=1.0)
        # No PiP, a área de conteúdo tem disponível a tela inteira (o PiP fica sobreposto em layer superior)
        area = ContentArea("pip_main_content", left=0, top=0, width=1920, height=1080, descricao="Canvas principal sob PiP")
        return vp, area

    @staticmethod
    def motion_fullscreen() -> Tuple[ViewportState, ContentArea]:
        # Apresentador desvanece; área gráfica ocupa tela inteira
        vp = ViewportState(left=0, top=0, width=1920, height=1080, opacity=0.0)
        area = ContentArea("motion_fullscreen", left=0, top=0, width=1920, height=1080, descricao="Motion em tela cheia")
        return vp, area


class StageStateManager:
    """Gerenciador de estado temporal determinístico para a viewport do apresentador (#palco)."""
    def __init__(self, duracao_total: float, id_viewport: str = "palco"):
        self.duracao_total = round(float(duracao_total), 3)
        self.id_viewport = id_viewport
        # Lista de transições registradas: (t, dur, ease, alteracoes_dict, label)
        self._transicoes = []
        # Registros de animações externas adicionais para validação de conflito: (elemento_id, prop, t_ini, t_fim)
        self._animacoes_registradas: List[Tuple[str, str, float, float]] = []

    def definir_estado_inicial(self, **props):
        """Permite customizar o estado em t=0 se necessário (padrão é Solo Fullscreen)."""
        self.transicionar(0.0, 0.0, ease="none", label="inicio", **props)

    def transicionar(self, t: float, duracao: float, ease: str = "power3.inOut", label: str = "", **alteracoes):
        """Agenda uma transição de propriedades para a viewport."""
        t = round(float(t), 3)
        duracao = round(float(duracao), 3)
        self._transicoes.append({
            "t": t,
            "dur": duracao,
            "ease": ease,
            "label": label,
            "alteracoes": alteracoes
        })

    def registrar_animacao_externa(self, elemento_id: str, propriedade: str, t_inicio: float, duracao: float):
        """Registra animação de outros elementos para detecção de conflitos granulares."""
        t_ini = round(float(t_inicio), 3)
        t_fim = round(t_ini + float(duracao), 3)
        self._animacoes_registradas.append((elemento_id, propriedade, t_ini, t_fim))

    def validar_conflitos(self):
        """
        Valida conflitos estritos por par (alvo, propriedade).
        Permite animações simultâneas em elementos distintos ou em propriedades distintas do mesmo elemento.
        Levanta TimelineConflictError se houver sobreposição na mesma propriedade do mesmo elemento.
        """
        # 1. Coleta todas as animações da viewport
        transicoes_ordenadas = sorted(self._transicoes, key=lambda x: x["t"])
        anim_viewport = []
        for tr in transicoes_ordenadas:
            t1 = tr["t"]
            t2 = t1 + tr["dur"]
            for prop in tr["alteracoes"].keys():
                anim_viewport.append((self.id_viewport, prop, t1, t2, tr["label"]))

        # 2. Une com as animações externas registradas
        todas = []
        for elem, prop, t1, t2, lbl in anim_viewport:
            todas.append((elem, prop, t1, t2, lbl))
        for elem, prop, t1, t2 in self._animacoes_registradas:
            todas.append((elem, prop, t1, t2, "externa"))

        # 3. Compara pares
        n = len(todas)
        for i in range(n):
            elem_a, prop_a, ini_a, fim_a, lbl_a = todas[i]
            for j in range(i + 1, n):
                elem_b, prop_b, ini_b, fim_b, lbl_b = todas[j]
                # Conflito só existe se for o MESMO elemento e a MESMA propriedade
                if elem_a == elem_b and prop_a == prop_b:
                    # Verifica sobreposição temporal estrita (além de tolerância de 1ms)
                    sobreposicao = not (fim_a <= ini_b + 0.001 or fim_b <= ini_a + 0.001)
                    if sobreposicao:
                        raise TimelineConflictError(
                            f"Conflito temporal detectado no elemento #{elem_a}, propriedade '{prop_a}': "
                            f"Animação [{ini_a:.3f}s -> {fim_a:.3f}s] ('{lbl_a}') colide com "
                            f"[{ini_b:.3f}s -> {fim_b:.3f}s] ('{lbl_b}')."
                        )

    def compilar(self) -> Tuple[List[str], List[Tuple[float, float]], ViewportState]:
        """
        Compila a timeline:
        - Ordena cronologicamente independentemente da ordem das chamadas.
        - Executa validação de conflitos granulares.
        - Gera comandos GSAP tl.to / tl.set com herança de estado.
        - Calcula os intervalos dinâmicos necessários ao render_rapido.py.
        Retorna: (linhas_js, intervalos_dinamicos, estado_final)
        """
        self.validar_conflitos()

        transicoes_ordenadas = sorted(self._transicoes, key=lambda x: x["t"])
        # Garante estado inicial em t=0 se não tiver sido especificado
        if not transicoes_ordenadas or transicoes_ordenadas[0]["t"] > 0:
            transicoes_ordenadas.insert(0, {
                "t": 0.0,
                "dur": 0.0,
                "ease": "none",
                "label": "solo_base",
                "alteracoes": dict(ViewportState.PROPRIEDADES_PADRAO)
            })

        js_tweens: List[str] = []
        estado_ativo = ViewportState()
        intervalos_brutos: List[Tuple[float, float]] = []

        # Estado inicial garantido usando transforms aceleradas (x, y)
        js_tweens.append(
            f'tl.set("#{self.id_viewport}", {{x:0,y:0,width:1920,height:1080,'
            f'borderRadius:"0px",border:"0px solid transparent",boxShadow:"none",opacity:1}},0);'
        )

        for i in range(len(transicoes_ordenadas)):
            tr = transicoes_ordenadas[i]
            t = tr["t"]
            dur = tr["dur"]
            ease = tr["ease"]
            mudancas = tr["alteracoes"]

            novo_estado = estado_ativo.clone()
            for k, v in mudancas.items():
                if k in novo_estado.props:
                    novo_estado.props[k] = v

            # Detecta propriedades que realmente mudaram
            diff = {k: v for k, v in novo_estado.props.items() if v != estado_ativo.props[k]}

            if diff and dur > 0:
                props_str = []
                for k, v in diff.items():
                    # Traduz left/top para x/y no tween GSAP para cumprir a regra sub-pixel do HyperFrames
                    prop_gsap = "x" if k == "left" else ("y" if k == "top" else k)
                    val = f'"{v}"' if isinstance(v, str) else v
                    props_str.append(f'{prop_gsap}:{val}')
                js_tweens.append(f'tl.to("#{self.id_viewport}", {{{",".join(props_str)}, duration:{dur:.3f}, ease:"{ease}"}},{t:.3f});')
            elif diff and dur == 0 and t > 0:
                props_str = []
                for k, v in diff.items():
                    prop_gsap = "x" if k == "left" else ("y" if k == "top" else k)
                    val = f'"{v}"' if isinstance(v, str) else v
                    props_str.append(f'{prop_gsap}:{val}')
                js_tweens.append(f'tl.set("#{self.id_viewport}", {{{",".join(props_str)}}},{t:.3f});')

            # Cobertura para render_rapido.py:
            t_trans_fim = t + dur
            t_proximo = transicoes_ordenadas[i + 1]["t"] if (i + 1 < len(transicoes_ordenadas)) else self.duracao_total

            if not novo_estado.is_solo_fullscreen():
                # Enquanto estiver fora do solo, o trecho permanece dinâmico até a próxima transição
                fim_intervalo = max(t_trans_fim, t_proximo)
                intervalos_brutos.append((t, fim_intervalo))
            elif dur > 0:
                # Se está retornando para solo fullscreen, apenas a janela da transição em si é dinâmica
                intervalos_brutos.append((t, t_trans_fim))

            estado_ativo = novo_estado

        intervalos_dinamicos = self._fundir_intervalos(intervalos_brutos)
        return js_tweens, intervalos_dinamicos, estado_ativo

    def _fundir_intervalos(self, ivs: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
        if not ivs:
            return []
        ivs_ordenados = sorted(ivs, key=lambda x: x[0])
        fundidos = [list(ivs_ordenados[0])]
        for a, b in ivs_ordenados[1:]:
            # Se sobrepõe ou está a menos de 100ms de distância, funde os trechos
            if a <= fundidos[-1][1] + 0.10:
                fundidos[-1][1] = max(fundidos[-1][1], b)
            else:
                fundidos.append([a, b])
        return [(round(a, 3), round(b, 3)) for a, b in fundidos]


class CompositionManager:
    """Orquestrador de empilhamento de camadas (z-index) e disponibilidade de áreas de conteúdo."""
    def __init__(self, stage_manager: StageStateManager):
        self.stage_manager = stage_manager
        # Registros de slots de conteúdo: (t_inicio, t_fim, ContentArea)
        self._areas_conteudo: List[Tuple[float, float, ContentArea]] = []
        # Regras de empilhamento: (t, {seletor: z_index})
        self._regras_stack: List[Tuple[float, Dict[str, int]]] = []

    def registrar_area_conteudo(self, de: float, ate: float, area: ContentArea):
        """Registra a disponibilidade de uma área geométrica de conteúdo em um intervalo de tempo."""
        self._areas_conteudo.append((round(float(de), 3), round(float(ate), 3), area))

    def definir_empilhamento(self, t: float, camadas: Dict[str, int]):
        """Define os z-indexes específicos de cada seletor ou camada a partir do tempo t."""
        self._regras_stack.append((round(float(t), 3), dict(camadas)))

    def obter_area_conteudo(self, t: float) -> Optional[ContentArea]:
        """Consulta a área de conteúdo ativa para o timestamp t."""
        for de, ate, area in self._areas_conteudo:
            if de <= t <= ate:
                return area
        return None

    def aplicar_preset(self, t: float, dur_transicao: float, tipo_preset: str,
                       dur_permanencia: Optional[float] = None, ease: str = "power3.inOut", **kwargs) -> Optional[ContentArea]:
        """
        Aplica um preset completo coordenando a geometria do palco e a área de conteúdo.
        Retorna a ContentArea correspondente se houver.
        """
        if tipo_preset == "solo":
            vp, area = CompositionPreset.solo_fullscreen()
        elif tipo_preset == "split_33_67":
            vp, area = CompositionPreset.split_33_67(**kwargs)
        elif tipo_preset == "split_50_50":
            vp, area = CompositionPreset.split_50_50(**kwargs)
        elif tipo_preset == "pip":
            vp, area = CompositionPreset.pip(**kwargs)
        elif tipo_preset == "motion_fullscreen":
            vp, area = CompositionPreset.motion_fullscreen()
        else:
            raise ValueError(f"Preset desconhecido: {tipo_preset}")

        self.stage_manager.transicionar(t, dur_transicao, ease=ease, label=tipo_preset, **vp.props)

        if area and dur_permanencia is not None:
            self.registrar_area_conteudo(t, t + dur_permanencia, area)

        return area

    def compilar(self) -> List[str]:
        """Gera os comandos GSAP de empilhamento ordenados temporalmente."""
        regras_ordenadas = sorted(self._regras_stack, key=lambda x: x[0])
        js_stack = []
        for t, camadas in regras_ordenadas:
            for sel, z in camadas.items():
                js_stack.append(f'tl.set("{sel}", {{zIndex:{z}}},{t:.3f});')
        return js_stack
