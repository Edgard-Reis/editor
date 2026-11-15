# -*- coding: utf-8 -*-
"""NÚCLEO DE SOUND DESIGN — DRIFIT EDITOR (VÓRTEX)
Módulo: branding/scripts/som.py

Implementa:
- RobustSoundBus: Gerenciador de eventos sonoros com identificação semântica,
  desduplicação inteligente, resolução determinística entre áudio automático/explícito
  e alocação estrita de tracks de áudio compatíveis com o HyperFrames linter.
"""

from typing import Dict, List, Optional, Callable, Set, Any
import math

class SoundEvent:
    """Representa a solicitação de um efeito sonoro atrelado a um evento audiovisual."""
    def __init__(self, event_id: str, som: str, t: float, volume: float = 0.4,
                 dur: Optional[float] = None, origem: str = "sistema", modo: str = "auto"):
        self.event_id = str(event_id).strip()
        self.som = str(som).strip()
        self.t = round(float(t), 3)
        self.volume = round(float(volume), 3)
        self.dur = round(float(dur), 3) if dur is not None else None
        self.origem = str(origem).strip()
        self.modo = str(modo).lower().strip() # "auto" ou "explicit"

    @property
    def chave_idempotencia(self) -> str:
        """Chave semântica única para identificação de duplicatas do mesmo evento."""
        return f"{self.event_id}::{self.som}"

    def __repr__(self):
        return f"<SoundEvent '{self.event_id}' ({self.som}.wav at {self.t}s, modo={self.modo})>"


class RobustSoundBus:
    """
    Barramento central de áudio para sound design de alta precisão.
    Garante:
    1. Resolução determinística: Se um evento explícito for declarado, descarta versões 'auto'.
    2. Desduplicação: Impede disparos acidentais repetidos do mesmo evento semântico.
    3. Preservação de eventos legítimos: Eventos distintos (event_ids diferentes) são sempre mantidos.
    4. Alocação sequencial de tracks: Cumpre o linter HyperFrames evitando colisões de áudio.
    """
    def __init__(self, track_base: int = 20):
        self.track_base = track_base
        self._registros: List[SoundEvent] = []

    def registrar(self, event_id: str, som: str, t: float, volume: float = 0.4,
                  dur: Optional[float] = None, origem: str = "sistema", modo: str = "auto") -> SoundEvent:
        """Registra a intenção de disparo de um efeito sonoro."""
        evento = SoundEvent(event_id, som, t, volume, dur, origem, modo)
        self._registros.append(evento)
        return evento

    def registrar_explicito(self, event_id: str, som: str, t: float, volume: float = 0.4,
                            dur: Optional[float] = None, origem: str = "editorial") -> SoundEvent:
        """Atalho de conveniência para registros de direção editorial com modo 'explicit'."""
        return self.registrar(event_id, som, t, volume, dur, origem, modo="explicit")

    def registrar_automatico(self, event_id: str, som: str, t: float, volume: float = 0.4,
                             dur: Optional[float] = None, origem: str = "componente") -> SoundEvent:
        """Atalho de conveniência para componentes internos com modo 'auto'."""
        return self.registrar(event_id, som, t, volume, dur, origem, modo="auto")

    def resolver_eventos(self) -> List[SoundEvent]:
        """
        Processa e resolve a lista final de eventos:
        - Agrupa por event_id.
        - Se existir qualquer registro 'explicit', descarta TODOS os 'auto' daquele event_id.
        - Elimina duplicatas de som para o mesmo event_id.
        - Retorna a lista ordenada cronologicamente por t.
        """
        por_evento: Dict[str, List[SoundEvent]] = {}
        for reg in self._registros:
            por_evento.setdefault(reg.event_id, []).append(reg)

        eventos_resolvidos: List[SoundEvent] = []

        for eid, lista in por_evento.items():
            # 1. Verifica se há evento explícito registrado
            explicitos = [ev for ev in lista if ev.modo == "explicit"]
            candidatos = explicitos if explicitos else lista

            # 2. Desduplicação por som (preserva apenas a primeira ocorrência única)
            sons_vistos: Set[str] = set()
            for ev in candidatos:
                if ev.som not in sons_vistos:
                    eventos_resolvidos.append(ev)
                    sons_vistos.add(ev.som)

        # 3. Ordenação cronológica estrita
        eventos_resolvidos.sort(key=lambda ev: (ev.t, ev.event_id))
        return eventos_resolvidos

    def compilar(self, duracao_cache_fn: Optional[Callable[[str], float]] = None) -> List[Dict[str, Any]]:
        """
        Compila os eventos resolvidos atribuindo índices de track estritamente sequenciais.
        Retorna dicionários de metadados prontos para geração de tags HTML e JSON do build.
        """
        eventos = self.resolver_eventos()
        resultado = []
        track_atual = self.track_base

        for idx, ev in enumerate(eventos):
            # Obtém a duração real do áudio via cache ou padrão
            dur_real = 1.0
            if duracao_cache_fn:
                try:
                    dur_real = float(duracao_cache_fn(ev.som))
                except Exception:
                    dur_real = 1.0
            d = min(ev.dur or 99.0, dur_real)

            tag_id = f"sfx_{idx+1}_{ev.event_id.replace('-', '_')}"
            tag_html = (
                f'<audio id="{tag_id}" src="sons/{ev.som}.wav" '
                f'data-start="{ev.t:.3f}" data-duration="{d:.3f}" '
                f'data-track-index="{track_atual}" data-volume="{ev.volume:.3f}"></audio>'
            )

            resultado.append({
                "id": tag_id,
                "event_id": ev.event_id,
                "som": ev.som,
                "t": ev.t,
                "dur": d,
                "volume": ev.volume,
                "track": track_atual,
                "tag_html": tag_html
            })

            # Cada efeito sonoro recebe uma track própria sequencial
            track_atual += 1

        return resultado

    def gerar_tags_html(self, duracao_cache_fn: Optional[Callable[[str], float]] = None) -> List[str]:
        """Gera diretamente a lista de strings HTML das tags <audio>."""
        compilados = self.compilar(duracao_cache_fn)
        return [c["tag_html"] for c in compilados]
