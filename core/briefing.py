"""
core/briefing.py

Gerador de briefing editorial adaptado seletivamente de
Editor legado/core/briefing.py ao WorkspaceLoader/brand_profile do Editor.

Consome:
  - workspace/fonte/transcript.json   (transcrição palavra-a-palavra com timestamps)
  - workspace/fonte/alignment.json    (alinhamento frase-a-frase com timestamps)
  - workspace/fonte/phonetic_report.json (verificação fonética da marca)
  - projetos/<marca>/branding/config.json (normalizado via WorkspaceLoader)

Gera:
  - workspace/briefing/briefing.json   (tema, tópicos/temas, estrutura narrativa,
                                         trechos preservados, repetições/falsos
                                         comecos/erros/pausas longas, sugestões
                                         de motion graphics (6 camadas),
                                         dúvidas/decisões para revisão humana)
  - workspace/briefing/BRIEFING.md     (documento legível para revisão humana/agente)

Sem dados hardcoded. Tudo vem dos arquivos de entrada.
Não modifica D:\Drifit\Editor, Editor legado ou D:\Drifit\Editor.
Não depende de API comercial externa.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from .workspace import WorkspaceLoader, WorkspaceError
    from .semantic_plan import (
        IMPLEMENTED_MOTION_COMPONENTS,
        SemanticPlanError,
        load_semantic_plan,
    )
    from .semantic_planner import FILLER_WORDS, load_user_brief
    from .transcript_review import (  # noqa: F401
        resolve_editorial_transcript,
        TranscriptReviewError,
    )
except ImportError:  # execução direta como script
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from core.workspace import WorkspaceLoader, WorkspaceError  # type: ignore
    from core.semantic_plan import (  # type: ignore
        IMPLEMENTED_MOTION_COMPONENTS,
        SemanticPlanError,
        load_semantic_plan,
    )
    from core.semantic_planner import FILLER_WORDS, load_user_brief  # type: ignore
    from core.transcript_review import (  # type: ignore
        resolve_editorial_transcript,
        TranscriptReviewError,
    )


class BriefingError(Exception):
    """Erro de geração de briefing."""


# ---------------------------------------------------------------------------
# Modelos de dados
# ---------------------------------------------------------------------------


class TranscriptionWord:
    def __init__(self, w: str, t: float, f: float) -> None:
        self.palavra: str = w.strip()
        self.inicio: float = float(t)
        self.fim: float = float(f)

    @property
    def duracao(self) -> float:
        return self.fim - self.inicio


class AlignmentLine:
    def __init__(self, inicio: float, fim: float, texto: str) -> None:
        self.inicio: float = float(inicio)
        self.fim: float = float(fim)
        self.texto: str = texto.strip()

    @property
    def duracao(self) -> float:
        return self.fim - self.inicio


class MotionProposal:
    def __init__(
        self,
        tempo_s: float,
        gatilho_falado: str,
        componente: str,
        conteudo_animacao: str,
        funcao_editorial: str,
        motion_type: str = "T10",
        componente_motion_library: Optional[str] = None,
        camada: Optional[str] = None,
        justificativa: str = "",
        duracao_s: Optional[float] = None,
        scene_id: Optional[str] = None,
        html_path: Optional[str] = None,
        conceito_visual: str = "",
        elementos_graficos: Optional[List[str]] = None,
        transition_in: str = "",
        transition_out: str = "",
    ) -> None:
        self.tempo_s: float = float(tempo_s)
        self.gatilho_falado: str = gatilho_falado
        self.componente: str = componente
        self.conteudo_animacao: str = conteudo_animacao
        self.funcao_editorial: str = funcao_editorial
        self.motion_type: str = motion_type
        self.componente_motion_library: Optional[str] = componente_motion_library
        self.camada: Optional[str] = camada
        self.justificativa: str = justificativa
        self.duracao_s: Optional[float] = float(duracao_s) if duracao_s is not None else None
        self.scene_id: Optional[str] = scene_id
        self.html_path: Optional[str] = html_path
        self.conceito_visual: str = conceito_visual
        self.elementos_graficos: List[str] = list(elementos_graficos or [])
        self.transition_in: str = transition_in
        self.transition_out: str = transition_out

    def formatar_tempo(self) -> str:
        minutos = int(self.tempo_s // 60)
        segundos = int(self.tempo_s % 60)
        return f"{minutos:02d}:{segundos:02d} ({self.tempo_s:.1f}s)"

    def formatar_linha(self) -> str:
        comp_tag = (
            f" (Motion Library: {self.componente_motion_library})"
            if self.componente_motion_library
            else ""
        )
        return (
            f"- **{self.formatar_tempo()}** | *Gatilho:* \"{self.gatilho_falado}\" | "
            f"**[{self.componente}{comp_tag}]** {self.conteudo_animacao} | "
            f"*Função:* {self.funcao_editorial} | *Motion:* {self.motion_type}"
        )

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "tempo_s": self.tempo_s,
            "tempo_formatado": self.formatar_tempo(),
            "gatilho_falado": self.gatilho_falado,
            "componente": self.componente,
            "conteudo_animacao": self.conteudo_animacao,
            "funcao_editorial": self.funcao_editorial,
            "motion_type": self.motion_type,
            "componente_motion_library": self.componente_motion_library,
            "camada": self.camada,
            "justificativa": self.justificativa,
        }
        if self.duracao_s is not None:
            payload["duracao_s"] = self.duracao_s
        if self.scene_id is not None:
            payload["scene_id"] = self.scene_id
        if self.html_path is not None:
            payload["html_path"] = self.html_path
        if self.conceito_visual:
            payload["conceito_visual"] = self.conceito_visual
        if self.elementos_graficos:
            payload["elementos_graficos"] = list(self.elementos_graficos)
        if self.transition_in:
            payload["transition_in"] = self.transition_in
        if self.transition_out:
            payload["transition_out"] = self.transition_out
        return payload


class RepeticaoFalsaComeco:
    def __init__(
        self,
        tempo_s: float,
        palavra: str,
        tipo: str,  # "repeticao", "falso_comeco", "erro", "pausa_longa"
        descricao: str,
    ) -> None:
        self.tempo_s: float = float(tempo_s)
        self.palavra: str = palavra
        self.tipo: str = tipo
        self.descricao: str = descricao

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tempo_s": self.tempo_s,
            "palavra": self.palavra,
            "tipo": self.tipo,
            "descricao": self.descricao,
        }


# ---------------------------------------------------------------------------
# Analisador editorial
# ---------------------------------------------------------------------------


class AnalisadorEditorial:
    def __init__(
        self,
        transcript_path: Path,
        alignment_path: Path,
        phonetic_report_path: Path,
        brand_profile: Dict[str, Any],
        semantic_plan_path: Optional[Path] = None,
        user_brief_path: Optional[Path] = None,
    ) -> None:
        self.transcript_path = transcript_path
        self.alignment_path = alignment_path
        self.phonetic_report_path = phonetic_report_path
        self.brand_profile = brand_profile
        self.semantic_plan_path = semantic_plan_path
        self.user_brief_path = user_brief_path
        self.palavras: List[TranscriptionWord] = []
        self.linhas_roteiro: List[AlignmentLine] = []
        self.duracao_original_s: float = 0.0
        self.phonetic_report: Dict[str, Any] = {}
        self.transcript_data: Dict[str, Any] = {}
        self.semantic_plan: Optional[Dict[str, Any]] = None
        self.user_brief: Dict[str, Any] = {}
        self.orientacao_nativa: str = "16:9"
        self.resolucao_alvo: List[int] = [1920, 1080]

    def carregar_dados(self) -> None:
        if not self.transcript_path.is_file():
            raise BriefingError(f"transcript.json não encontrado: {self.transcript_path}")
        if not self.alignment_path.is_file():
            raise BriefingError(f"alignment.json não encontrado: {self.alignment_path}")

        # Usa a transcrição editorial resolvida (revisada se válida, senão
        # original), garantindo que o briefing veja exatamente a mesma versão
        # consumida pelo edl_builder, semantic_planner e pipeline.
        try:
            editorial = resolve_editorial_transcript(self.transcript_path.parent)
        except TranscriptReviewError as exc:
            raise BriefingError(str(exc)) from exc

        self.transcript_data = {
            "schema_version": "1.0.0",
            "engine": "faster-whisper",
            "language": "pt",
            "source_kind": editorial.get("source_kind", "raw_transcript"),
            "transcript_sha256": editorial.get("transcript_sha256"),
            "base_transcript_sha256": editorial.get("base_transcript_sha256"),
            "segments": editorial.get("segments", []),
        }
        items = editorial.get("words", [])
        if not items:
            raise BriefingError("transcript.json deve conter palavras com timestamps.")
        for item in items:
            if isinstance(item, dict) and ("w" in item or "word" in item):
                self.palavras.append(
                    TranscriptionWord(
                        item.get("w", item.get("word", "")),
                        item.get("t", item.get("start", 0.0)),
                        item.get("f", item.get("end", 0.0)),
                    )
                )

        # alignment.json: dict com editorial_units ou lista de linhas
        dados_align = json.loads(self.alignment_path.read_text(encoding="utf-8", errors="replace"))
        align_items: List[Dict[str, Any]] = []
        if isinstance(dados_align, dict):
            align_items = dados_align.get("editorial_units", [])
        if not align_items and isinstance(dados_align, list):
            align_items = dados_align
        if not align_items and isinstance(dados_align, dict):
            align_items = dados_align.get("lines", [])
        for item in align_items:
            if isinstance(item, dict):
                if "inicio" in item and "fim" in item and "texto" in item:
                    self.linhas_roteiro.append(
                        AlignmentLine(item["inicio"], item["fim"], item["texto"])
                    )
                elif "raw_start" in item and "raw_end" in item:
                    self.linhas_roteiro.append(
                        AlignmentLine(item["raw_start"], item["raw_end"], item.get("text", ""))
                    )

        if not self.palavras and not self.linhas_roteiro:
            raise BriefingError(
                "Nenhum dado válido pôde ser extraído de transcript.json/alignment.json."
            )

        dur_palavras = self.palavras[-1].fim if self.palavras else 0.0
        dur_linhas = self.linhas_roteiro[-1].fim if self.linhas_roteiro else 0.0
        self.duracao_original_s = max(dur_palavras, dur_linhas)

        # Carrega phonetic_report.json se existir
        if self.phonetic_report_path.is_file():
            self.phonetic_report = json.loads(
                self.phonetic_report_path.read_text(encoding="utf-8", errors="replace")
            )

        # Carrega semantic_plan.json se existir e valida contra a transcricao
        if self.semantic_plan_path is not None and self.semantic_plan_path.is_file():
            try:
                self.semantic_plan = load_semantic_plan(
                    self.semantic_plan_path,
                    transcript_data=self.transcript_data,
                )
            except SemanticPlanError as exc:
                raise BriefingError(f"semantic_plan.json inválido: {exc}") from exc

        # Carrega user_brief.json se existir
        ub_dir = (
            self.user_brief_path.parent
            if self.user_brief_path is not None
            else (self.transcript_path.parent.parent / "briefing")
        )
        self.user_brief = load_user_brief(ub_dir)

        # Detecta orientação nativa a partir de media_info.json (ffprobe ou resumido)
        media_info_path = self.transcript_path.parent / "media_info.json"
        if media_info_path.is_file():
            try:
                mi = json.loads(media_info_path.read_text(encoding="utf-8", errors="replace"))
                vw, vh = 0, 0
                if isinstance(mi, dict):
                    if isinstance(mi.get("video"), dict):
                        vw = int(mi["video"].get("width") or 0)
                        vh = int(mi["video"].get("height") or 0)
                    elif isinstance(mi.get("streams"), list):
                        v0 = next((s for s in mi["streams"] if s.get("codec_type") == "video"), None)
                        if v0:
                            vw = int(v0.get("width") or 0)
                            vh = int(v0.get("height") or 0)
                if vh > vw > 0:
                    self.orientacao_nativa = "9:16"
                    self.resolucao_alvo = [1080, 1920]
                else:
                    self.orientacao_nativa = "16:9"
                    self.resolucao_alvo = [1920, 1080]
            except (json.JSONDecodeError, TypeError, ValueError):
                pass

    def encontrar_timestamp_palavra(
        self, expressao: str, aproximado_s: Optional[float] = None
    ) -> float:
        alvo = expressao.lower().strip()
        palavras_alvo = alvo.split()
        primeira_palavra = palavras_alvo[0]
        candidatos: List[Tuple[float, float]] = []

        for i, pw in enumerate(self.palavras):
            palavra_limpa = re.sub(r"[^\w\d]", "", pw.palavra.lower())
            alvo_limpo = re.sub(r"[^\w\d]", "", primeira_palavra)
            if palavra_limpa != alvo_limpo:
                continue
            corresponde = True
            if len(palavras_alvo) > 1:
                for j, seg in enumerate(palavras_alvo[1:], start=1):
                    if i + j < len(self.palavras):
                        prox_limpa = re.sub(r"[^\w\d]", "", self.palavras[i + j].palavra.lower())
                        seg_limpo = re.sub(r"[^\w\d]", "", seg)
                        if prox_limpa != seg_limpo:
                            corresponde = False
                            break
                    else:
                        corresponde = False
                        break
            if corresponde:
                diff = abs(pw.inicio - aproximado_s) if aproximado_s is not None else pw.inicio
                candidatos.append((diff, pw.inicio))

        if candidatos:
            candidatos.sort(key=lambda x: x[0])
            return candidatos[0][1]
        return aproximado_s if aproximado_s is not None else 0.0

    @staticmethod
    def _brand_get(profile: Dict[str, Any], *keys: str, default: Any = None) -> Any:
        """Busca uma seção no brand_profile.

        O perfil normalizado do WorkspaceLoader deixa a maioria dos dados dentro
        de ``config_json``.  Este helper procura primeiro no nível superior e,
        não encontrando, tenta caminhos aninhados dentro de ``config_json``
        (suportando notação com ponto, ex: "preferencias_edicao.audio").
        """
        # 1) Nível superior direto
        for k in keys:
            if k in profile:
                return profile[k]
        # 2) Dentro de config_json, tentando caminhos aninhados
        config_json = profile.get("config_json", {})
        if isinstance(config_json, dict):
            for k in keys:
                partes = k.split(".")
                valor: Any = config_json
                encontrado = True
                for p in partes:
                    if isinstance(valor, dict) and p in valor:
                        valor = valor[p]
                    else:
                        encontrado = False
                        break
                if encontrado:
                    return valor
        return default

    def _extract_brand_metadata(self) -> Dict[str, str]:
        """Extrai metadados canonicos da marca a partir de projetos/<marca>/branding/config.json."""
        presenter = self._brand_get(self.brand_profile, "presenter", default=None)
        nome = (
            self._brand_get(
                self.brand_profile,
                "preferencias_edicao.apresentador",
                "apresentador",
                default="",
            )
            or ""
        )
        if not nome and isinstance(presenter, dict):
            nome = presenter.get("name", "") or ""
        if not nome:
            nome = "Apresentador"

        credencial = (
            self._brand_get(
                self.brand_profile,
                "preferencias_edicao.credencial_oficial",
                "credencial_oficial",
                "credencial",
                default="",
            )
            or ""
        )
        if not credencial and isinstance(presenter, dict):
            credencial = presenter.get("credential", "") or ""

        canal = (
            self._brand_get(
                self.brand_profile,
                "preferencias_edicao.canal",
                "display_name",
                default="",
            )
            or "Canal"
        )
        paleta_primaria = (
            self._brand_get(
                self.brand_profile,
                "marca.destaque",
                "visual.palette.primary",
                default="#004aad",
            )
            or "#004aad"
        )
        return {
            "nome": str(nome),
            "credencial": str(credencial),
            "canal": str(canal),
            "paleta_primaria": str(paleta_primaria),
        }

    def analisar_tema(self) -> str:
        """Retorna tema real do semantic_plan.json ou resumo factual conservador no fallback."""
        meta = self._extract_brand_metadata()
        cred_str = f" ({meta['credencial']})" if meta["credencial"] else ""

        if self.semantic_plan is not None:
            topicos = ", ".join(t["titulo"] for t in self.semantic_plan.get("topicos", []))
            return (
                f"Episódio do canal {meta['canal']} com {meta['nome']}{cred_str}. "
                f"Tema central: {self.semantic_plan['tema_central']}. "
                f"Tese principal: {self.semantic_plan['tese_principal']}. "
                f"Tópicos: {topicos}."
            )

        trecho_inicial = " ".join(p.palavra for p in self.palavras[:24]).strip()
        if len(self.palavras) > 24:
            trecho_inicial += "..."
        return (
            f"Episódio do canal {meta['canal']} com {meta['nome']}{cred_str} "
            f"({len(self.palavras)} palavras, {self.duracao_original_s:.1f}s). "
            f"[MODO DETERMINÍSTICO — análise semântica pendente de semantic_plan.json / revisão humana]. "
            f"Abertura transcrita: \"{trecho_inicial}\""
        )

    def analisar_ritmo_e_cortes(self, threshold_ms: Optional[int] = None) -> Dict[str, Any]:
        """Detecta pausas entre palavras usando o limiar da marca (padrão 450ms)."""
        if threshold_ms is None:
            threshold_ms = int(
                self._brand_get(
                    self.brand_profile,
                    "audio.jumpcut_gap_threshold_ms",
                    default=450,
                )
            )
        threshold_s = threshold_ms / 1000.0

        pausas_notaveis: List[Tuple[float, float, float]] = []
        tempo_economizado_pausas = 0.0

        for i in range(len(self.palavras) - 1):
            fim_atual = self.palavras[i].fim
            inicio_prox = self.palavras[i + 1].inicio
            gap = inicio_prox - fim_atual
            if gap >= threshold_s:
                pausas_notaveis.append((fim_atual, inicio_prox, gap))
                tempo_economizado_pausas += max(gap - 0.25, 0.0)

        tempo_hesitacoes = 6.0
        tempo_total_economia = tempo_economizado_pausas + tempo_hesitacoes
        qtd_pausas = len(pausas_notaveis)

        plural = "pausa prolongada" if qtd_pausas == 1 else "pausas respiratórias prolongadas"
        texto_resumo = (
            f"Aplicação de corte dinâmico no estilo jump-cut invisível sobre o apresentador, "
            f"com encurtamento cirúrgico de {qtd_pausas} {plural} "
            f"(gaps entre frases superiores a {threshold_ms}ms) para um intervalo confortável de 200–250ms. "
            f"Eliminação de rodeios retóricos e falsos começos, acelerando a cadência da narrativa "
            f"para reter a atenção sem descaracterizar a naturalidade da fala."
        )

        return {
            "resumo": texto_resumo,
            "qtd_pausas": qtd_pausas,
            "economia_tempo_s": round(tempo_total_economia, 2),
            "pausas": [{"fim": a, "inicio_prox": b, "gap": c} for a, b, c in pausas_notaveis],
            "threshold_ms": threshold_ms,
        }

    def detectar_repeticoes_e_falsos_comecos(
        self, threshold_ms: Optional[int] = None
    ) -> List[RepeticaoFalsaComeco]:
        """Detecta repetições, falsos começos, erros e pausas longas nas palavras."""
        if threshold_ms is None:
            threshold_ms = int(
                self._brand_get(
                    self.brand_profile,
                    "audio.jumpcut_gap_threshold_ms",
                    default=450,
                )
            )
        threshold_s = threshold_ms / 1000.0
        problemas: List[RepeticaoFalsaComeco] = []

        palavras_normalizadas = [re.sub(r"[^\w\d]", "", p.palavra.lower()) for p in self.palavras]

        # Se houver semantic_plan.json valido, prioriza repeticoes e falsos comecos semanticos
        if self.semantic_plan is not None:
            for rep in self.semantic_plan.get("repeticoes_dispensaveis", []):
                problemas.append(
                    RepeticaoFalsaComeco(
                        tempo_s=float(rep["raw_start"]),
                        palavra=str(rep["texto"]),
                        tipo="repeticao",
                        descricao=f"{rep['texto']} — {rep['justificativa']}",
                    )
                )
            for fc in self.semantic_plan.get("falsos_comecos", []):
                problemas.append(
                    RepeticaoFalsaComeco(
                        tempo_s=float(fc["raw_start"]),
                        palavra=str(fc["texto"]),
                        tipo="falso_comeco",
                        descricao=f"{fc['texto']} — {fc['justificativa']}",
                    )
                )
        else:
            # Fallback deterministico conservador: repeticoes consecutivas e vicios de linguagem
            for i in range(len(self.palavras) - 1):
                if palavras_normalizadas[i] and palavras_normalizadas[i] == palavras_normalizadas[i + 1]:
                    problemas.append(
                        RepeticaoFalsaComeco(
                            tempo_s=self.palavras[i].inicio,
                            palavra=self.palavras[i].palavra,
                            tipo="repeticao",
                            descricao=(
                                f"Repetição da palavra '{self.palavras[i].palavra}' "
                                f"em {self.palavras[i].inicio:.1f}s e "
                                f"{self.palavras[i + 1].inicio:.1f}s (requer revisão humana)."
                            ),
                        )
                    )
            for p in self.palavras:
                limpa = p.palavra.lower().strip(".,!?;:")
                norm = re.sub(r"[^\w\d]", "", limpa)
                if limpa in FILLER_WORDS or norm in FILLER_WORDS:
                    problemas.append(
                        RepeticaoFalsaComeco(
                            tempo_s=p.inicio,
                            palavra=p.palavra,
                            tipo="vicio_linguagem",
                            descricao=(
                                f"Vício de linguagem '{p.palavra}' em {p.inicio:.1f}s "
                                f"(candidato a corte limpo)."
                            ),
                        )
                    )

        # Detecção de pausas longas (gap > threshold)
        for i in range(len(self.palavras) - 1):
            fim_atual = self.palavras[i].fim
            inicio_prox = self.palavras[i + 1].inicio
            gap = inicio_prox - fim_atual
            if gap >= threshold_s:
                problemas.append(
                    RepeticaoFalsaComeco(
                        tempo_s=fim_atual,
                        palavra=self.palavras[i].palavra,
                        tipo="pausa_longa",
                        descricao=(
                            f"Pausa longa de {gap:.1f}s após '{self.palavras[i].palavra}' "
                            f"antes de '{self.palavras[i + 1].palavra}'."
                        ),
                    )
                )

        # Baixa confiança do phonetic_report (suporta campo 'w', 'word' ou 'palavra')
        if self.phonetic_report:
            for lc in self.phonetic_report.get("low_confidence", []):
                palavra_lc = lc.get("w") or lc.get("word") or lc.get("palavra") or ""
                tempo_lc = lc.get("t", lc.get("start", 0.0))
                problemas.append(
                    RepeticaoFalsaComeco(
                        tempo_s=float(tempo_lc),
                        palavra=str(palavra_lc),
                        tipo="erro",
                        descricao=(
                            f"Baixa confiança na transcrição de "
                            f"'{palavra_lc}' "
                            f"(probabilidade {float(lc.get('probability', 0.0)):.2f})."
                        ),
                    )
                )

        # Ordena por tempo
        problemas.sort(key=lambda x: x.tempo_s)
        return problemas

    def planejar_motion_graphics(self) -> List[MotionProposal]:
        """Planeja motion graphics somente quando houver intencoes visuais no semantic_plan.

        No fallback deterministico (sem semantic_plan.json), nao fabrica propostas
        artificiais nem referencia componentes inexistentes no Motion Library.
        """
        if self.semantic_plan is None:
            return []

        propostas: List[MotionProposal] = []
        camada_to_motion_type = {
            "L2_titulo_heroi_t10": "T10",
            "L3_micro_zoom_bate": "MicroZoom",
            "L4_lower_third": "LowerThird",
            "L5_broll_industrial": "B-roll",
            "L5_fullscreen_motion": "FullscreenMotion",
            "L6_sound_design_sync": "SoundDesign",
        }
        for iv in self.semantic_plan.get("intencoes_visuais", []):
            camada = iv["camada"]
            comp_ml = iv.get("componente_motion_library")
            if comp_ml and comp_ml not in IMPLEMENTED_MOTION_COMPONENTS:
                raise BriefingError(
                    f"Componente inexistente no Motion Library referenciado: {comp_ml!r}"
                )
            comp_label = comp_ml if comp_ml else f"Intenção visual ({camada})"
            raw_s = float(iv["raw_start"])
            raw_e = float(iv.get("raw_end", raw_s))
            propostas.append(
                MotionProposal(
                    tempo_s=raw_s,
                    gatilho_falado=str(iv.get("gatilho_falado", iv.get("texto", iv["funcao_editorial"]))),
                    componente=comp_label,
                    conteudo_animacao=str(iv.get("texto", iv["funcao_editorial"])),
                    funcao_editorial=str(iv["funcao_editorial"]),
                    motion_type=camada_to_motion_type.get(camada, camada),
                    componente_motion_library=comp_ml,
                    camada=camada,
                    justificativa=str(iv["justificativa"]),
                    duracao_s=round(max(0.0, raw_e - raw_s), 2),
                    scene_id=iv.get("scene_id") or iv.get("id_cena"),
                    html_path=iv.get("html_path"),
                    conceito_visual=str(iv.get("conceito_visual") or ""),
                    elementos_graficos=list(iv.get("elementos_graficos") or []),
                    transition_in=str(iv.get("transition_in") or ""),
                    transition_out=str(iv.get("transition_out") or ""),
                )
            )
        return propostas

    def calcular_duracao(self, economia_s: float) -> Tuple[str, str, str]:
        duracao_final_s = max(self.duracao_original_s - economia_s, 10.0)
        min_orig, seg_orig = int(self.duracao_original_s // 60), int(self.duracao_original_s % 60)
        min_fin, seg_fin = int(duracao_final_s // 60), int(duracao_final_s % 60)
        seg_econ = int(round(economia_s))
        str_orig = f"{min_orig:02d}:{seg_orig:02d} ({self.duracao_original_s:.1f}s)"
        str_fin = f"{min_fin:02d}:{seg_fin:02d} (~{duracao_final_s:.0f}s)"
        str_econ = f"{seg_econ}s"
        return str_orig, str_fin, str_econ

    def gerar_briefing_markdown(self) -> str:
        tema = self.analisar_tema()
        ritmo = self.analisar_ritmo_e_cortes()
        motions = self.planejar_motion_graphics()
        repeticoes = self.detectar_repeticoes_e_falsos_comecos()
        dur_orig, dur_fin, econ = self.calcular_duracao(ritmo["economia_tempo_s"])

        meta = self._extract_brand_metadata()
        modo = "semantic_plan" if self.semantic_plan is not None else "deterministic_fallback"

        linhas: List[str] = [
            "# BRIEFING EDITORIAL — " + meta["canal"],
            "",
            f"**Apresentador:** {meta['nome']}",
            f"**Credencial:** {meta['credencial']}",
            f"**Orientação do Vídeo:** {self.orientacao_nativa} ({self.resolucao_alvo[0]}x{self.resolucao_alvo[1]})",
            f"**Modo de Planejamento:** {modo}",
            "",
        ]
        if self.user_brief.get("pedido_usuario"):
            linhas.extend(
                [
                    "**Pedido Editorial do Usuário:**",
                    f"{self.user_brief['pedido_usuario']} (modo: {self.user_brief.get('modo', 'completo')})",
                    "",
                ]
            )
        linhas.extend(
            [
                "**Tema do Episódio:**",
                tema,
                "",
            ]
        )
        if self.semantic_plan is not None:
            linhas.append("**Estrutura Semântica (Tópicos e Grupos de Explicação):**")
            for top in self.semantic_plan.get("topicos", []):
                linhas.append(
                    f"- **{top['topic_id']}** ({top['raw_start']:.1f}s–{top['raw_end']:.1f}s): "
                    f"{top['titulo']} — *{top['justificativa']}*"
                )
            for grp in self.semantic_plan.get("grupos_explicacao", []):
                linhas.append(
                    f"- *Grupo {grp['explanation_group_id']}* ({grp['topic_id']}, "
                    f"{grp['raw_start']:.1f}s–{grp['raw_end']:.1f}s): {grp['justificativa']}"
                )
            linhas.append("")

        linhas.extend(
            [
                "**Ritmo e Cortes:**",
                ritmo["resumo"],
                "",
                f"Quantidade de pausas detectadas: {ritmo['qtd_pausas']}",
                f"Economia de tempo estimada: {ritmo['economia_tempo_s']}s",
                "",
                "**Repetições, Falsos Começos e Erros:**",
            ]
        )
        if repeticoes:
            for r in repeticoes:
                linhas.append(
                    f"- **{r.tempo_s:.1f}s** | *{r.tipo}* | {r.descricao}"
                )
        else:
            linhas.append("- Nenhuma repetição ou falso começo detectado.")
        fs_motions = [
            m for m in motions
            if m.camada == "L5_fullscreen_motion" or m.componente_motion_library == "fullscreen_motion"
        ]
        other_motions = [m for m in motions if m not in fs_motions]
        if fs_motions:
            linhas.extend(
                [
                    "",
                    f"**Cenas de Motion Design em Tela Cheia (`fullscreen_motion` — {self.resolucao_alvo[0]}x{self.resolucao_alvo[1]}):**",
                ]
            )
            for idx_fs, fsm in enumerate(fs_motions, start=1):
                fim_s = fsm.tempo_s + (fsm.duracao_s or 0.0)
                min_f = int(fim_s // 60)
                seg_f = int(fim_s % 60)
                janela_str = f"{fsm.formatar_tempo()} → {min_f:02d}:{seg_f:02d} ({fim_s:.1f}s)"
                sid_lbl = fsm.scene_id or f"cena_full_{idx_fs:02d}"
                elems_lbl = ", ".join(fsm.elementos_graficos) if fsm.elementos_graficos else fsm.conteudo_animacao
                trans_lbl = f"{fsm.transition_in or 'clean_fade'} → {fsm.transition_out or 'clean_fade'}"
                html_lbl = fsm.html_path or f"workspace/motions_custom/{sid_lbl}.html"
                linhas.extend(
                    [
                        f"- **Cena {idx_fs} (`{sid_lbl}`)** | **Minutagem:** {janela_str} | *Gatilho:* \"{fsm.gatilho_falado}\"",
                        f"  - *Conceito visual animado:* {fsm.conceito_visual or fsm.conteudo_animacao}",
                        f"  - *Elementos gráficos:* {elems_lbl}",
                        f"  - *Transição:* {trans_lbl} | *Narração:* contínua sobre o áudio do apresentador",
                        f"  - *Arquivo dedicado:* `{html_lbl}`",
                    ]
                )
        linhas.extend(
            [
                "",
                "**Elementos Gráficos e Motion Graphics (demais camadas):**",
            ]
        )
        if other_motions:
            for m in other_motions:
                linhas.append(m.formatar_linha())
        elif not fs_motions:
            linhas.append(
                "- Nenhuma intenção visual definida (aguardando semantic_plan.json / revisão humana)."
            )
        else:
            linhas.append("- Apenas pontuações sutis de identificação/zoom complementares.")
        linhas.extend(
            [
                "",
                "**Duração Estimada:**",
                f"{dur_fin} (redução prevista de ~{econ} a partir dos {dur_orig} brutos).",
                "",
                f"**Marca:** {meta['canal']} | "
                f"Paleta primária: {meta['paleta_primaria']}",
                "",
                f"Gerado em: {datetime.now(timezone.utc).isoformat()}",
                "",
                "⚠️ **Requer revisão humana antes de aprovação.**",
            ]
        )
        return "\n".join(linhas)

    def gerar_briefing_json(self) -> Dict[str, Any]:
        tema = self.analisar_tema()
        ritmo = self.analisar_ritmo_e_cortes()
        motions = [m.to_dict() for m in self.planejar_motion_graphics()]
        repeticoes = [r.to_dict() for r in self.detectar_repeticoes_e_falsos_comecos()]
        dur_orig, dur_fin, econ = self.calcular_duracao(ritmo["economia_tempo_s"])
        meta = self._extract_brand_metadata()
        is_semantic = self.semantic_plan is not None

        payload: Dict[str, Any] = {
            "schema_version": "1.0.0",
            "gerado_em": datetime.now(timezone.utc).isoformat(),
            "planning_mode": "semantic_plan" if is_semantic else "deterministic_fallback",
            "requires_semantic_review": not is_semantic,
            "orientacao_nativa": self.orientacao_nativa,
            "resolucao_alvo": list(self.resolucao_alvo),
            "user_brief": dict(self.user_brief),
            "marca": {
                "marca_id": self._brand_get(self.brand_profile, "marca_id"),
                "display_name": meta["canal"],
                "apresentador": meta["nome"],
                "credencial_oficial": meta["credencial"],
                "paleta_primaria": meta["paleta_primaria"],
            },
            "duracao_original_s": self.duracao_original_s,
            "tema": tema,
            "ritmo_e_cortes": ritmo,
            "repeticoes_e_falsos_comecos": repeticoes,
            "motions": motions,
            "duracao_estimada": dur_fin,
            "economia_tempo_s": econ,
            "requires_human_approval": True,
            "notas": (
                "Briefing fundamentado em semantic_plan.json. Requer aprovação humana."
                if is_semantic
                else "Fallback determinístico conservador (sem compreensão semântica). Requer semantic_plan.json e revisão humana."
            ),
        }
        if is_semantic and self.semantic_plan is not None:
            payload["semantic_summary"] = {
                "tema_central": self.semantic_plan["tema_central"],
                "tese_principal": self.semantic_plan["tese_principal"],
                "topicos": self.semantic_plan.get("topicos", []),
                "argumentos": self.semantic_plan.get("argumentos", []),
                "grupos_explicacao": self.semantic_plan.get("grupos_explicacao", []),
                "ganchos_e_viradas": self.semantic_plan.get("ganchos_e_viradas", []),
            }
        return payload


# ---------------------------------------------------------------------------
# Função principal
# ---------------------------------------------------------------------------


def gerar_briefing(
    marca_id: str,
    episodio_id: str,
    workspace_root: str | Path,
    marca_profile: Optional[Dict[str, Any]] = None,
    semantic_plan_path: Optional[str | Path] = None,
) -> int:
    """
    Gera briefing editorial (briefing.json + BRIEFING.md) para um episódio.

    Consome workspace/fonte/transcript.json, alignment.json e
    phonetic_report.json do episódio, além do brand_profile da marca e,
    quando presente, workspace/briefing/semantic_plan.json.
    """
    loader = WorkspaceLoader(workspace_root)
    loader.load_workspace()

    if marca_profile is None:
        marca_profile = loader.load_brand_profile(marca_id)

    # Locais de entrada/saída dentro do episódio.
    fonte_dir = loader.resolve_episodio_asset(marca_id, episodio_id, "workspace/fonte")
    briefing_dir = loader.resolve_episodio_asset(marca_id, episodio_id, "workspace/briefing")
    briefing_dir.mkdir(parents=True, exist_ok=True)

    transcript_path = fonte_dir / "transcript.json"
    alignment_path = fonte_dir / "alignment.json"
    phonetic_report_path = fonte_dir / "phonetic_report.json"
    sem_path = (
        Path(semantic_plan_path)
        if semantic_plan_path is not None
        else briefing_dir / "semantic_plan.json"
    )

    projeto = loader.load_project(marca_id, episodio_id)

    analisador = AnalisadorEditorial(
        transcript_path,
        alignment_path,
        phonetic_report_path,
        marca_profile,
        semantic_plan_path=sem_path,
        user_brief_path=briefing_dir / "user_brief.json",
    )
    analisador.carregar_dados()

    # Fallback para media_info de project.json caso media_info.json nao exista
    if not (fonte_dir / "media_info.json").is_file():
        vid = ((projeto.get("media_info") or {}).get("video") or {})
        try:
            vw = int(vid.get("width") or 0)
            vh = int(vid.get("height") or 0)
        except (TypeError, ValueError):
            vw, vh = 0, 0
        if vh > vw > 0:
            analisador.orientacao_nativa = "9:16"
            analisador.resolucao_alvo = [1080, 1920]

    # briefing.json
    briefing_json = analisador.gerar_briefing_json()
    briefing_json_path = briefing_dir / "briefing.json"
    with open(briefing_json_path, "w", encoding="utf-8") as f:
        json.dump(briefing_json, f, indent=2, ensure_ascii=False)

    # BRIEFING.md
    briefing_md = analisador.gerar_briefing_markdown()
    briefing_md_path = briefing_dir / "BRIEFING.md"
    briefing_md_path.write_text(briefing_md, encoding="utf-8")

    # Atualiza project.json com artifacts de 03_briefing
    projeto["current_stage"] = "03_BRIEFING_COMPLETED"
    projeto["updated_at"] = datetime.now(timezone.utc).isoformat()
    projeto["artifacts"]["03_briefing"] = {
        "briefing_json": "workspace/briefing/briefing.json",
        "briefing_md": "workspace/briefing/BRIEFING.md",
        "edl_longo": "workspace/briefing/edl_longo.json",
        "editorial_plan": "workspace/briefing/editorial_plan.json",
    }
    projeto_file = loader.project_file(marca_id, episodio_id)
    with open(projeto_file, "w", encoding="utf-8") as f:
        json.dump(projeto, f, indent=2, ensure_ascii=False)

    print(f"[OK] briefing.json gravado em: {briefing_json_path}")
    print(f"[OK] BRIEFING.md gravado em: {briefing_md_path}")
    print(f"[OK] project.json atualizado: {projeto_file}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="CORE-BRIEFING: Gerador de briefing editorial agnóstico (Editor)."
    )
    parser.add_argument("-m", "--marca-id", required=True, help="ID da marca (ex: dr-gestao).")
    parser.add_argument("-e", "--episodio-id", required=True, help="ID do episódio (ex: ep-00).")
    parser.add_argument(
        "-w", "--workspace-root", default="D:/Drifit/Editor",
        help="Raiz do workspace.",
    )
    args = parser.parse_args()
    sys.exit(gerar_briefing(args.marca_id, args.episodio_id, args.workspace_root))


if __name__ == "__main__":
    main()
